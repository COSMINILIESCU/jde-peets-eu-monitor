"""Small real end-to-end probe: collect a few sources + real AI analysis (no publish)."""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from src.analysis.engine import analyze_new_items  # noqa: E402
from src.collectors.collect import collect_all  # noqa: E402
from src.common import db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

if os.path.exists(db.DB_PATH):
    os.remove(db.DB_PATH)

reg = yaml.safe_load(open(db.ROOT / "sources" / "registry.yaml", encoding="utf-8"))["sources"]
ids = ["comunicaffe", "esm-magazine", "revista-progresiv", "ico-coffee"]
sample = [s for s in reg if s["id"] in ids]

conn = db.connect()
run = db.start_run(conn, "probe")
collect_all(conn, sample, run)
n = conn.execute("SELECT COUNT(*) c FROM items WHERE status='new'").fetchone()["c"]
print("NEW ITEMS:", n)
stats = analyze_new_items(conn, run)
print("ANALYSIS STATS:", stats)
db.finish_run(conn, run, stats)

print("\n--- sample analyzed items ---")
rows = conn.execute(
    "SELECT source_id, relevance, analysis_json FROM items WHERE status='analyzed' "
    "ORDER BY relevance DESC LIMIT 4"
).fetchall()
import json  # noqa: E402

for r in rows:
    a = json.loads(r["analysis_json"])
    print(f"\n[{a['impact']}/{a['confidence']}/{r['relevance']:.2f}] {a['category']} | {a.get('countries')}")
    print(" T:", a["title_en"][:90])
    print(" S:", (a["summary_en"][:180] + "…") if a["summary_en"] else "(none)")
conn.close()
