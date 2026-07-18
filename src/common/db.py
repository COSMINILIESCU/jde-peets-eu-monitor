"""SQLite storage — full local archive; docs/data JSON is generated from here."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.common.config import ROOT

DB_PATH = ROOT / "data" / "monitor.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    content_text TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',      -- new|duplicate|triaged_out|analyzed|published|archived|error
    relevance REAL,
    analysis_json TEXT,                      -- validated AI output (AnalyzedItem)
    run_id INTEGER,
    UNIQUE(canonical_url)
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
CREATE INDEX IF NOT EXISTS idx_items_hash ON items(content_hash);

CREATE TABLE IF NOT EXISTS source_state (
    source_id TEXT PRIMARY KEY,
    method TEXT NOT NULL DEFAULT 'auto',     -- resolved access method: rss|html|pdf|api
    feed_url TEXT NOT NULL DEFAULT '',
    etag TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    last_run_at TEXT,
    last_ok_at TEXT,
    fail_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'weekly',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    stats_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,                     -- pipeline|scout|specialist|human
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def audit(conn: sqlite3.Connection, actor: str, action: str, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (at, actor, action, detail) VALUES (?,?,?,?)",
        (now_iso(), actor, action, detail),
    )
    conn.commit()


def start_run(conn: sqlite3.Connection, kind: str = "weekly") -> int:
    cur = conn.execute("INSERT INTO runs (kind, started_at) VALUES (?,?)", (kind, now_iso()))
    conn.commit()
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, stats: dict) -> None:
    conn.execute(
        "UPDATE runs SET finished_at=?, stats_json=? WHERE id=?",
        (now_iso(), json.dumps(stats, ensure_ascii=False), run_id),
    )
    conn.commit()
