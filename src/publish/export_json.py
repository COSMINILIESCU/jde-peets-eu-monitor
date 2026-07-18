"""Export dashboard JSON files (docs/data/) from the local SQLite archive."""

import json
from datetime import UTC, datetime, timedelta

from src.common.config import ROOT, load_registry, settings
from src.common.db import connect, now_iso

DATA_DIR = ROOT / "docs" / "data"


def _week_of(iso_date: str) -> str:
    d = datetime.fromisoformat(iso_date)
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def export_items(conn) -> int:
    months = settings()["retention"]["dashboard_months_visible"]
    cutoff = (datetime.now(UTC) - timedelta(days=months * 31)).isoformat()
    rows = conn.execute(
        "SELECT i.*, COALESCE(i.published_at, i.fetched_at) AS display_date FROM items i "
        "WHERE i.status IN ('analyzed','published') AND COALESCE(i.published_at, i.fetched_at) >= ? "
        "ORDER BY display_date DESC", (cutoff,),
    ).fetchall()
    sources = {s["id"]: s for s in load_registry()["sources"]}
    items = []
    for r in rows:
        analysis = json.loads(r["analysis_json"]) if r["analysis_json"] else {}
        src = sources.get(r["source_id"], {})
        items.append({
            "id": r["id"],
            "url": r["url"],
            "title": r["title"],
            "title_en": analysis.get("title_en") or r["title"],
            "summary_en": analysis.get("summary_en", ""),
            "source_id": r["source_id"],
            "source_name": src.get("name", r["source_id"]),
            "source_type": src.get("type", "other"),
            "trust_tier": src.get("trust_tier", ""),
            "lang": r["lang"],
            "countries": analysis.get("countries", []),
            "category": analysis.get("category"),
            "categories": analysis.get("categories", []),
            "entities": analysis.get("entities", []),
            "brands": analysis.get("brands", []),
            "impact": analysis.get("impact", "low"),
            "horizon": analysis.get("horizon", ""),
            "confidence": analysis.get("confidence", "unconfirmed"),
            "keywords": analysis.get("keywords", []),
            "relevance": r["relevance"],
            "published_at": r["published_at"],
            "fetched_at": r["fetched_at"],
            "week": _week_of(r["display_date"]),
        })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "items.json").write_text(
        json.dumps(items, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)


def export_sources(conn) -> int:
    states = {r["source_id"]: dict(r) for r in conn.execute("SELECT * FROM source_state")}
    out = []
    for s in load_registry()["sources"]:
        st = states.get(s["id"], {})
        out.append({
            "id": s["id"], "name": s["name"], "url": s["url"], "type": s["type"],
            "country": s.get("country", ""), "language": s.get("language", []),
            "trust_tier": s.get("trust_tier", ""), "status": s.get("status", ""),
            "exclusion_reason": s.get("exclusion_reason", ""),
            "method": st.get("method", ""), "last_ok_at": st.get("last_ok_at"),
            "fail_count": st.get("fail_count", 0), "last_error": st.get("last_error", ""),
        })
    (DATA_DIR / "sources.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(out)


def export_meta(conn, run_stats: dict | None = None, brief: dict | None = None) -> None:
    proj = settings()["project"]
    counts = {r["k"]: r["n"] for r in conn.execute(
        "SELECT status k, COUNT(*) n FROM items GROUP BY status")}
    meta = {
        "generated_at": now_iso(),
        "project": proj["name"],
        "provider_name": proj["provider_name"],
        "provider_url": proj["provider_url"],
        "repo_url": proj.get("repo_url", ""),
        "week": _week_of(now_iso()),
        "db_counts": counts,
        "last_run": run_stats or {},
    }
    (DATA_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    if brief is not None:
        (DATA_DIR / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1),
                                             encoding="utf-8")


def export_all(conn=None, run_stats: dict | None = None, brief: dict | None = None) -> dict:
    own = conn is None
    conn = conn or connect()
    try:
        n_items = export_items(conn)
        n_sources = export_sources(conn)
        export_meta(conn, run_stats, brief)
        return {"items": n_items, "sources": n_sources}
    finally:
        if own:
            conn.close()
