"""Invoke the difficult-source-specialist for sources that failed standard collection.

Called automatically at the end of the weekly run (if enabled in settings), or manually:
    python scripts/run_specialist.py [source_id ...]
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import db  # noqa: E402
from src.common.config import settings  # noqa: E402
from src.common.headless import run_agent  # noqa: E402

log = logging.getLogger("specialist")


def failing_sources(conn, limit: int) -> list[dict]:
    rows = conn.execute(
        "SELECT source_id, method, fail_count, last_error FROM source_state "
        "WHERE fail_count >= 1 ORDER BY fail_count DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def run_for(sources: list[dict]) -> tuple[bool, str]:
    lines = "\n".join(
        f"- {s['source_id']}: method={s.get('method', '?')}, fails={s.get('fail_count', '?')}, "
        f"error={s.get('last_error', '')[:150]}" for s in sources)
    prompt = (
        "Invoke the difficult-source-specialist subagent for the following failing sources of the "
        "JDE Peet's EU/EEA monitor, following its instructions exactly, and report its per-source "
        f"verdicts.\n\nFailing sources:\n{lines}"
    )
    cfg = settings().get("specialist", {})
    return run_agent(prompt, 'WebSearch,WebFetch,Read,Edit,Grep,Glob,Bash(python*)', timeout=3600,
                     model=cfg.get("model", ""), effort=cfg.get("effort", ""))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    conn = db.connect()
    cfg = settings().get("specialist", {"enabled": True, "max_sources_per_run": 5})
    if len(sys.argv) > 1:
        targets = [{"source_id": sid} for sid in sys.argv[1:]]
    else:
        targets = failing_sources(conn, cfg.get("max_sources_per_run", 5))
    if not targets:
        log.info("no failing sources - nothing to do")
        return 0
    db.audit(conn, "specialist", "specialist_start", ",".join(t["source_id"] for t in targets))
    ok, output = run_for(targets)
    db.audit(conn, "specialist", "specialist_finish", "ok" if ok else f"failed: {output[:200]}")
    conn.close()
    print(output[-3000:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
