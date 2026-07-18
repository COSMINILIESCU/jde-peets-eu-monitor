from src.processing.dedup import title_similar
from src.processing.normalize import canonical_url, clean_text, content_hash, detect_lang


def test_canonical_url_strips_tracking_and_normalizes():
    assert canonical_url("https://Example.EU/news/x/?utm_source=rss&utm_medium=feed") == \
        "https://example.eu/news/x"
    assert canonical_url("https://example.eu/news/x#section") == "https://example.eu/news/x"
    assert canonical_url("https://example.eu/news?page=2") == "https://example.eu/news?page=2"


def test_content_hash_stable_across_whitespace():
    a = content_hash("Title", "Some  text\n\n\n\nhere")
    b = content_hash("Title", "Some text\n\nhere")
    assert a == b
    assert a != content_hash("Other title", "Some text here")


def test_clean_text_collapses_whitespace():
    assert clean_text("a   b\t c\n\n\n\nd") == "a b c\n\nd"


def test_title_similarity():
    assert title_similar(
        "Commission proposes revision of packaging waste rules",
        "Commission proposes revision of packaging waste rules for capsules", 0.85)
    assert not title_similar("Coffee prices rise", "New EUDR guidance published", 0.85)


def test_detect_lang():
    assert detect_lang("The European Commission proposed new rules on packaging waste today.") == "en"
    assert detect_lang("short") == ""
