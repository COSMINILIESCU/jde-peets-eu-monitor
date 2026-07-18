"""Normalization: canonical URLs, clean text, content hashing, language detection."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source",
}


def canonical_url(url: str) -> str:
    p = urlparse(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING_PARAMS])
    host = p.netloc.lower()
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower() or "https", host, path, "", query, ""))


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def content_hash(title: str, text: str) -> str:
    basis = (title.strip().lower() + "\n" + clean_text(text).lower())[:20000]
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def detect_lang(text: str) -> str:
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0
        sample = clean_text(text)[:2000]
        return detect(sample) if len(sample) >= 20 else ""
    except Exception:
        return ""
