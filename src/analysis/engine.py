"""AI engine: run the analysis prompt through Claude Code headless (or the API later).

The engine is swappable via config (analysis.engine); everything else in the pipeline only sees
validated AnalyzedItem objects.
"""

import json
import logging
import re
import subprocess

from pydantic import ValidationError

from src.analysis.prompt import build_prompt
from src.analysis.schemas import AnalyzedItem, BatchResult
from src.common.config import settings

log = logging.getLogger("analysis")


class EngineError(Exception):
    pass


def _run_claude_headless(prompt: str, model: str, timeout: int = 900) -> str:
    """Invoke `claude -p` with no tools; prompt via stdin (avoids cmdline length limits)."""
    cmd = [settings()["analysis"].get("claude_cmd", "claude"), "-p",
           "--output-format", "json", "--max-turns", "1", "--tools", ""]
    if model:
        cmd += ["--model", model]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout, shell=False)
    except FileNotFoundError as exc:
        raise EngineError("Claude Code CLI not found — install it or set analysis.claude_cmd") from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError(f"claude -p timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise EngineError(f"claude -p failed (rc={proc.returncode}): {proc.stderr[:500]}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise EngineError(f"claude -p returned error: {str(envelope.get('result'))[:500]}")
    return envelope["result"]


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text, flags=re.MULTILINE).strip()
    start = text.find("{")
    if start == -1:
        raise EngineError("no JSON object in model output")
    return json.loads(text[start:text.rfind("}") + 1])


def _validate(raw: dict, expected_ids: set[int]) -> list[AnalyzedItem]:
    result = BatchResult.model_validate(raw)
    got_ids = {it.item_id for it in result.items}
    missing = expected_ids - got_ids
    if missing:
        raise EngineError(f"model output missing item_ids: {sorted(missing)}")
    return [it for it in result.items if it.item_id in expected_ids]


def analyze_batch(items: list[dict], runner=None) -> list[AnalyzedItem]:
    """Analyze one batch. `runner` is injectable for tests. Retries once on invalid output."""
    cfg = settings()["analysis"]
    runner = runner or (lambda p: _run_claude_headless(p, cfg.get("model") or ""))
    prompt = build_prompt(items)
    expected = {it["id"] for it in items}
    last_error = None
    for attempt in (1, 2):
        try:
            return _validate(_extract_json(runner(prompt)), expected)
        except (EngineError, ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            log.warning("analysis attempt %d invalid: %s", attempt, str(exc)[:300])
            prompt = build_prompt(items) + (
                f"\n\nYour previous output was invalid ({str(exc)[:200]}). "
                "Return ONLY the corrected JSON object."
            )
    raise EngineError(f"analysis failed after retry: {last_error}")


def analyze_new_items(conn, run_id: int, runner=None) -> dict:
    """Analyze all 'new' items in batches; store validated results. Returns stats."""
    cfg = settings()["analysis"]
    batch_size = cfg["batch_size"]
    threshold = cfg["relevance_threshold"]
    max_pub = cfg["max_published_items_per_run"]
    rows = conn.execute(
        "SELECT i.id, i.url, i.title, i.content_text, i.lang, i.source_id "
        "FROM items i WHERE i.status='new' ORDER BY i.id"
    ).fetchall()
    from src.common.config import load_registry
    sources = {s["id"]: s for s in load_registry()["sources"]}
    stats = {"analyzed": 0, "relevant": 0, "triaged_out": 0, "errors": 0}
    published = 0
    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start:start + batch_size]
        batch = [{
            "id": r["id"], "url": r["url"], "title": r["title"], "text": r["content_text"],
            "lang": r["lang"],
            "source_name": sources.get(r["source_id"], {}).get("name", r["source_id"]),
            "source_type": sources.get(r["source_id"], {}).get("type", "other"),
        } for r in batch_rows]
        try:
            results = analyze_batch(batch, runner=runner)
        except EngineError as exc:
            # leave items as 'new' so the next run retries them
            log.error("batch failed permanently (items stay queued): %s", str(exc)[:300])
            stats["errors"] += len(batch_rows)
            continue
        for res in results:
            stats["analyzed"] += 1
            if res.relevant and res.relevance >= threshold and published < max_pub:
                conn.execute(
                    "UPDATE items SET status='analyzed', relevance=?, analysis_json=? WHERE id=?",
                    (res.relevance, res.model_dump_json(), res.item_id),
                )
                stats["relevant"] += 1
                published += 1
            else:
                conn.execute(
                    "UPDATE items SET status='triaged_out', relevance=? WHERE id=?",
                    (res.relevance, res.item_id),
                )
                stats["triaged_out"] += 1
        conn.commit()
        log.info("analyzed %d/%d items", min(start + batch_size, len(rows)), len(rows))
    return stats
