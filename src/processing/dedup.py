"""Deduplication: canonical URL (DB unique constraint), content hash, fuzzy title match."""

import sqlite3
from difflib import SequenceMatcher

from src.common.config import settings


def title_similar(a: str, b: str, threshold: float) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def find_duplicate(conn: sqlite3.Connection, canonical: str, chash: str, title: str) -> int | None:
    """Return the id of an existing item this one duplicates, else None."""
    row = conn.execute("SELECT id FROM items WHERE canonical_url = ?", (canonical,)).fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT id FROM items WHERE content_hash = ?", (chash,)).fetchone()
    if row:
        return row["id"]
    threshold = settings()["dedup"]["title_similarity_threshold"]
    recent = conn.execute(
        "SELECT id, title FROM items ORDER BY id DESC LIMIT 500"
    ).fetchall()
    for r in recent:
        if title_similar(title, r["title"], threshold):
            return r["id"]
    return None
