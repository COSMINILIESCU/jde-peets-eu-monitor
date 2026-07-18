import json

import pytest

from src.collectors.collect import store_item
from src.common import db
from src.publish import export_json


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(export_json, "DATA_DIR", tmp_path / "out")
    conn = db.connect(tmp_path / "test.db")
    yield conn
    conn.close()


def _analyzed(conn, url, title, impact="high"):
    store_item(conn, "esm-magazine", {"url": url, "title": title,
               "text": "Body text for " + title, "published_at": "2026-07-15T10:00:00+00:00"}, 1)
    row = conn.execute("SELECT id FROM items WHERE url=?", (url,)).fetchone()
    analysis = {"item_id": row["id"], "relevant": True, "relevance": 0.8,
                "title_en": title, "summary_en": "Summary.", "category": "legislation",
                "categories": [], "countries": ["EU"], "entities": [], "brands": [],
                "impact": impact, "horizon": "short_term", "confidence": "confirmed_fact",
                "keywords": ["k"]}
    conn.execute("UPDATE items SET status='analyzed', relevance=0.8, analysis_json=? WHERE id=?",
                 (json.dumps(analysis), row["id"]))
    conn.commit()


def test_export_all_produces_dashboard_json(conn):
    _analyzed(conn, "https://x.eu/a", "EUDR guidance published")
    _analyzed(conn, "https://x.eu/b", "PPWR vote scheduled", impact="medium")
    stats = export_json.export_all(conn, run_stats={"ok": True},
                                   brief={"week": "2026-W29", "text": "brief"})
    assert stats["items"] == 2
    out = export_json.DATA_DIR
    items = json.loads((out / "items.json").read_text(encoding="utf-8"))
    assert {i["impact"] for i in items} == {"high", "medium"}
    assert all(i["url"].startswith("https://x.eu/") for i in items)
    assert items[0]["week"] == "2026-W29"
    sources = json.loads((out / "sources.json").read_text(encoding="utf-8"))
    assert len(sources) > 400
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["provider_url"].startswith("https://www.pimasociates.ro")
    brief = json.loads((out / "brief.json").read_text(encoding="utf-8"))
    assert brief["week"] == "2026-W29"


def test_new_items_not_exported(conn):
    store_item(conn, "s1", {"url": "https://x.eu/raw", "title": "Unanalyzed item title here",
               "text": "text", "published_at": None}, 1)
    stats = export_json.export_all(conn)
    assert stats["items"] == 0
