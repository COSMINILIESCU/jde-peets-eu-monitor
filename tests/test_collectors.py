from pathlib import Path
from unittest.mock import MagicMock

from src.collectors.discovery import looks_like_feed
from src.collectors.html_page import extract_links, extract_main_text
from src.collectors.rss import collect_rss

FIXTURES = Path(__file__).parent / "fixtures"


def _fake_fetcher(body: bytes, headers: dict | None = None, status: int = 200):
    fetcher = MagicMock()
    resp = MagicMock()
    resp.content = body
    resp.text = body.decode("utf-8")
    resp.status_code = status
    resp.headers = headers or {}
    resp.url = "https://example.eu/news"
    fetcher.get.return_value = resp
    return fetcher


def test_collect_rss_parses_items_and_skips_untitled():
    body = (FIXTURES / "sample_feed.xml").read_bytes()
    items, cond = collect_rss(_fake_fetcher(body, {"ETag": 'W/"abc"'}), "https://example.eu/feed")
    assert len(items) == 2
    assert items[0]["title"].startswith("Commission proposes")
    assert items[0]["published_at"] == "2026-07-13T09:00:00+00:00"
    assert cond["etag"] == 'W/"abc"'


def test_collect_rss_304_returns_empty():
    items, _ = collect_rss(_fake_fetcher(b"", status=304), "https://example.eu/feed")
    assert items == []


def test_extract_links_filters_noise():
    html = (FIXTURES / "sample_listing.html").read_text(encoding="utf-8")
    links = extract_links(html, "https://example.eu/news")
    urls = [link["url"] for link in links]
    assert "https://example.eu/news/decision-2026-142" in urls
    assert "https://example.eu/news/sector-inquiry-fmcg" in urls
    assert len(urls) == len(set(urls))  # dedup within page
    assert not any("external-site.com" in u for u in urls)  # same-site only
    assert not any("newsletter" in u or "login" in u for u in urls)


def test_extract_main_text_prefers_article():
    html = (FIXTURES / "sample_article.html").read_text(encoding="utf-8")
    text = extract_main_text(html)
    assert "12 million euros" in text
    assert "Site header" not in text
    assert "var x=1" not in text


def test_looks_like_feed():
    assert looks_like_feed('<?xml version="1.0"?><rss version="2.0">')
    assert not looks_like_feed("<!DOCTYPE html><html>")
