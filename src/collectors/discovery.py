"""Resolve a source's access method: find an RSS/Atom feed, else fall back to HTML."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.collectors.fetcher import Fetcher, FetchError, RobotsDisallowed

COMMON_FEED_PATHS = ["feed", "rss", "feed.xml", "rss.xml", "atom.xml", "feeds/all.atom.xml", "?feed=rss2"]


def looks_like_feed(text: str) -> bool:
    head = text.lstrip()[:300].lower()
    return "<rss" in head or "<feed" in head or "<rdf" in head


def discover(fetcher: Fetcher, url: str) -> tuple[str, str]:
    """Return (method, feed_url). method: 'rss' | 'html' | 'pdf'."""
    if url.lower().endswith(".pdf"):
        return "pdf", ""
    try:
        resp = fetcher.get(url)
    except (FetchError, RobotsDisallowed):
        raise
    ctype = resp.headers.get("Content-Type", "")
    if "pdf" in ctype:
        return "pdf", ""
    if looks_like_feed(resp.text) or "xml" in ctype and looks_like_feed(resp.text):
        return "rss", url
    # <link rel="alternate"> advertised feeds
    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("link", rel=lambda v: v and "alternate" in v):
        if "rss" in (link.get("type") or "") or "atom" in (link.get("type") or ""):
            href = link.get("href")
            if href:
                return "rss", urljoin(resp.url, href)
    # probe common feed paths (best-effort, first hit wins)
    for path in COMMON_FEED_PATHS:
        candidate = urljoin(resp.url.rstrip("/") + "/", path)
        try:
            probe = fetcher.get(candidate)
            if probe.status_code == 200 and looks_like_feed(probe.text):
                return "rss", candidate
        except (FetchError, RobotsDisallowed):
            continue
    return "html", ""
