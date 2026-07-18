"""PDF collector: download a PDF and extract its text."""

import fitz

from src.collectors.fetcher import Fetcher


def collect_pdf(fetcher: Fetcher, url: str) -> dict:
    resp = fetcher.get(url)
    doc = fitz.open(stream=resp.content, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    title = (doc.metadata.get("title") or url.rsplit("/", 1)[-1]).strip()
    return {"url": url, "title": title, "text": text[:60000], "published_at": None}
