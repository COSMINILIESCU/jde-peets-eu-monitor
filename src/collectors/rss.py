"""RSS/Atom collector."""

import calendar
from datetime import UTC, datetime

import feedparser

from src.collectors.fetcher import Fetcher


def parse_feed_datetime(entry) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            # feedparser normalizes struct_time to UTC -> use timegm, not mktime (local tz)
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC).isoformat(timespec="seconds")
    return None


def collect_rss(fetcher: Fetcher, feed_url: str, conditional: dict | None = None,
                max_items: int = 40) -> tuple[list[dict], dict]:
    """Return (items, new_conditional). Items: url/title/summary/published_at."""
    resp = fetcher.get(feed_url, conditional=conditional)
    new_conditional = {
        "etag": resp.headers.get("ETag", ""),
        "last_modified": resp.headers.get("Last-Modified", ""),
    }
    if resp.status_code == 304:
        return [], new_conditional
    parsed = feedparser.parse(resp.content)
    items = []
    for entry in parsed.entries[:max_items]:
        url = getattr(entry, "link", "") or ""
        title = (getattr(entry, "title", "") or "").strip()
        if not url or not title:
            continue
        summary = (getattr(entry, "summary", "") or "")
        items.append({
            "url": url,
            "title": title,
            "text": summary,
            "published_at": parse_feed_datetime(entry),
        })
    return items, new_conditional
