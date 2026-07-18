import pytest

from src.collectors.collect import store_item
from src.common import db


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    yield conn
    conn.close()


def _item(url="https://example.eu/news/a", title="Commission fines coffee cartel members in Germany",
          text="Long article text about the cartel decision and fines imposed on roasters."):
    return {"url": url, "title": title, "text": text, "published_at": None}


def test_store_new_then_exact_duplicate(conn):
    assert store_item(conn, "s1", _item(), run_id=1) == "new"
    assert store_item(conn, "s1", _item(), run_id=1) == "duplicate"


def test_store_duplicate_by_tracking_url_variant(conn):
    assert store_item(conn, "s1", _item(), run_id=1) == "new"
    variant = _item(url="https://example.eu/news/a?utm_source=rss")
    assert store_item(conn, "s1", variant, run_id=1) == "duplicate"


def test_store_duplicate_by_similar_title_other_source(conn):
    assert store_item(conn, "s1", _item(), run_id=1) == "new"
    republished = _item(url="https://other.eu/x",
                        title="Commission fines coffee cartel members in Germany today",
                        text="Different rewrite of the same news story text.")
    assert store_item(conn, "s2", republished, run_id=1) == "duplicate"


def test_distinct_items_both_stored(conn):
    assert store_item(conn, "s1", _item(), run_id=1) == "new"
    other = _item(url="https://example.eu/news/b", title="EUDR guidance for importers published",
                  text="Guidance text.")
    assert store_item(conn, "s1", other, run_id=1) == "new"
    count = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
    assert count == 2


def test_run_lifecycle(conn):
    run_id = db.start_run(conn, "weekly")
    db.finish_run(conn, run_id, {"new": 5})
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    assert row["finished_at"] is not None
    assert '"new": 5' in row["stats_json"]
