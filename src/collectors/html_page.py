"""Generic HTML collector: extract candidate article links from a listing page,
then extract main text from each article page."""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.collectors.fetcher import Fetcher, FetchError, RobotsDisallowed

SKIP_URL_PATTERNS = re.compile(
    r"(login|signin|signup|register|subscribe|newsletter|cookie|privacy|terms|contact|"
    r"facebook\.com|twitter\.com|x\.com|linkedin\.com|instagram\.com|youtube\.com|mailto:|javascript:|#$)",
    re.IGNORECASE,
)


def extract_links(page_html: str, base_url: str, max_links: int = 40) -> list[dict]:
    """Candidate article links: same-site anchors with substantial link text."""
    soup = BeautifulSoup(page_html, "html.parser")
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.")
    seen: set[str] = set()
    out: list[dict] = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(base_url, a["href"])
        host = urlparse(href).netloc.lower().removeprefix("www.")
        if len(text) < 35 or host != base_host or SKIP_URL_PATTERNS.search(href):
            continue
        if href.rstrip("/") == base_url.rstrip("/") or href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "title": text})
        if len(out) >= max_links:
            break
    return out


def extract_main_text(page_html: str) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all(["p", "li", "h1", "h2", "h3"])]
    text = "\n".join(p for p in paragraphs if len(p) > 2)
    if len(text) < 200:  # fallback: whole container text
        text = container.get_text("\n", strip=True)
    return text[:60000]


def collect_html(fetcher: Fetcher, url: str, known_urls: set[str],
                 max_items: int = 40, fetch_articles: bool = True) -> list[dict]:
    """Collect new article links from a listing page; optionally fetch each article's text."""
    resp = fetcher.get(url)
    links = [link for link in extract_links(resp.text, resp.url, max_links=max_items)
             if link["url"] not in known_urls]
    items = []
    for link in links:
        text = ""
        if fetch_articles:
            try:
                text = extract_main_text(fetcher.get(link["url"]).text)
            except (FetchError, RobotsDisallowed):
                continue
        items.append({"url": link["url"], "title": link["title"], "text": text, "published_at": None})
    return items
