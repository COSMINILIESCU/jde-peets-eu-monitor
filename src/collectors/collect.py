"""Collection stage: iterate active sources, gather new items, normalize, dedup, store."""

import logging
import sqlite3

from src.collectors.discovery import discover
from src.collectors.fetcher import Fetcher, FetchError, RobotsDisallowed
from src.collectors.html_page import collect_html
from src.collectors.pdf_doc import collect_pdf
from src.collectors.rss import collect_rss
from src.common.config import settings
from src.common.db import now_iso
from src.processing.dedup import find_duplicate
from src.processing.normalize import canonical_url, clean_text, content_hash, detect_lang

log = logging.getLogger("collect")


def _get_state(conn: sqlite3.Connection, source_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM source_state WHERE source_id=?", (source_id,)).fetchone()


def _save_state(conn: sqlite3.Connection, source_id: str, **fields) -> None:
    conn.execute("INSERT OR IGNORE INTO source_state (source_id) VALUES (?)", (source_id,))
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE source_state SET {sets} WHERE source_id=?", (*fields.values(), source_id))
    conn.commit()


def store_item(conn: sqlite3.Connection, source_id: str, item: dict, run_id: int) -> str:
    """Insert one collected item. Returns 'new' | 'duplicate'."""
    canonical = canonical_url(item["url"])
    title = clean_text(item["title"])[:500]
    text = clean_text(item.get("text") or "")
    chash = content_hash(title, text)
    dup_id = find_duplicate(conn, canonical, chash, title)
    if dup_id is not None:
        return "duplicate"
    conn.execute(
        "INSERT OR IGNORE INTO items (source_id, url, canonical_url, title, content_text, content_hash,"
        " lang, published_at, fetched_at, status, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (source_id, item["url"], canonical, title, text, chash,
         detect_lang(text or title), item.get("published_at"), now_iso(), "new", run_id),
    )
    conn.commit()
    return "new"


def collect_source(conn: sqlite3.Connection, fetcher: Fetcher, source: dict, run_id: int) -> dict:
    """Collect one source. Returns per-source stats dict."""
    cfg = settings()["collection"]
    sid = source["id"]
    stats = {"source_id": sid, "new": 0, "duplicates": 0, "status": "ok", "error": ""}
    state = _get_state(conn, sid)
    method = state["method"] if state and state["method"] != "auto" else "auto"
    feed_url = state["feed_url"] if state else ""

    try:
        if method == "auto":
            registry_rss = (source.get("access") or {}).get("rss") or ""
            if registry_rss:
                method, feed_url = "rss", registry_rss
            else:
                method, feed_url = discover(fetcher, source["url"])
            _save_state(conn, sid, method=method, feed_url=feed_url)

        if method == "rss":
            conditional = {"etag": state["etag"], "last_modified": state["last_modified"]} if state else None
            items, new_cond = collect_rss(fetcher, feed_url or source["url"], conditional,
                                          max_items=cfg["max_items_per_source_per_run"])
            _save_state(conn, sid, etag=new_cond["etag"], last_modified=new_cond["last_modified"])
        elif method == "pdf":
            items = [collect_pdf(fetcher, source["url"])]
        else:  # html
            known = {r["canonical_url"] for r in conn.execute(
                "SELECT canonical_url FROM items WHERE source_id=?", (sid,))}
            items = collect_html(fetcher, source["url"], known,
                                 max_items=cfg["max_items_per_source_per_run"])

        for item in items:
            result = store_item(conn, sid, item, run_id)
            stats["new" if result == "new" else "duplicates"] += 1
        _save_state(conn, sid, last_run_at=now_iso(), last_ok_at=now_iso(), fail_count=0, last_error="")
    except RobotsDisallowed:
        stats["status"], stats["error"] = "robots_disallowed", "robots.txt disallows access"
        _mark_fail(conn, sid, state, stats["error"])
    except FetchError as exc:
        stats["status"], stats["error"] = "fetch_error", str(exc)[:300]
        _mark_fail(conn, sid, state, stats["error"])
    except Exception as exc:  # never let one source kill the run
        log.exception("source %s failed", sid)
        stats["status"], stats["error"] = "error", f"{type(exc).__name__}: {exc}"[:300]
        _mark_fail(conn, sid, state, stats["error"])
    return stats


def _mark_fail(conn: sqlite3.Connection, sid: str, state: sqlite3.Row | None, error: str) -> None:
    fail_count = (state["fail_count"] if state else 0) + 1
    _save_state(conn, sid, last_run_at=now_iso(), fail_count=fail_count, last_error=error)


def collect_all(conn: sqlite3.Connection, sources: list[dict], run_id: int) -> list[dict]:
    fetcher = Fetcher()
    results = []
    for i, source in enumerate(sources, 1):
        stats = collect_source(conn, fetcher, source, run_id)
        log.info("[%d/%d] %s: %s (+%d new, %d dup)", i, len(sources), source["id"],
                 stats["status"], stats["new"], stats["duplicates"])
        results.append(stats)
    return results
