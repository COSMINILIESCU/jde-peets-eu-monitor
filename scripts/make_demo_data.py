"""Build DEMO dashboard data from the smoke-test DB (synthetic classifications).

Used only to preview the dashboard before the first real AI run. Deterministic.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.schemas import CATEGORIES  # noqa: E402
from src.common import db  # noqa: E402
from src.publish.export_json import export_all  # noqa: E402

IMPACTS = ["high", "medium", "low", "low", "medium"]
CONF = ["confirmed_fact", "company_statement", "analysis", "third_party_claim", "analysis"]


def main() -> None:
    conn = db.connect(db.ROOT / "data" / "smoke.db")
    rows = conn.execute("SELECT id, title, lang, source_id FROM items").fetchall()
    for i, r in enumerate(rows):
        cat = CATEGORIES[i % len(CATEGORIES)]
        analysis = {
            "item_id": r["id"], "relevant": True, "relevance": 0.5 + (i % 5) / 10,
            "title_en": r["title"] + (" [DEMO translation]" if r["lang"] != "en" else ""),
            "summary_en": "[DEMO DATA] Synthetic summary used only for layout preview. "
                          "This paragraph shows how a one-to-two-paragraph factual summary will look.\n\n"
                          "A second short paragraph notes potential relevance for JDE Peet's in the EU/EEA.",
            "category": cat, "categories": [CATEGORIES[(i + 3) % len(CATEGORIES)]],
            "countries": [["EU", "RO", "DE", "NL", "FR", "IT"][i % 6]],
            "entities": [["JDE Peet's", "Nestlé", "European Commission", "Lavazza", "Carrefour"][i % 5]],
            "brands": [["L'OR", "Senseo", "Nespresso", "Jacobs", "Tassimo"][i % 5]],
            "impact": IMPACTS[i % 5], "horizon": "short_term",
            "confidence": CONF[i % 5],
            "keywords": ["demo", "coffee", "eu"],
        }
        conn.execute("UPDATE items SET status='analyzed', relevance=?, analysis_json=? WHERE id=?",
                     (analysis["relevance"], json.dumps(analysis, ensure_ascii=False), r["id"]))
    conn.commit()
    brief = {
        "week": "2026-W29", "generated_at": db.now_iso(),
        "text": "[DEMO] This is where the weekly executive brief will appear: 3-5 paragraphs in English "
                "summarising the most consequential developments of the week for JDE Peet's in the EU/EEA, "
                "generated automatically and traceable to the underlying items.",
    }
    stats = export_all(conn, run_stats={"note": "demo data"}, brief=brief)
    print("exported:", stats)


if __name__ == "__main__":
    main()
