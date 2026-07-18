"""Triage the source registry down to a focused set for the target reader
(CEE Head of Legal & Corporate Affairs at JDE Peet's).

Sources that don't make the focused cut are marked status: excluded with an
exclusion_reason (never deleted, so the monthly scout / a future decision can revive them).

Usage:
    python scripts/triage_sources.py --inspect       # print entries by type (craft rules)
    python scripts/triage_sources.py --dry-run       # show keep/drop counts + samples
    python scripts/triage_sources.py --apply         # write status changes to registry.yaml
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "sources" / "registry.yaml"

# Markets whose national authorities/registers we keep broadly:
# CEE core + JDE home (NL) + big Western markets + EU institutional seats.
# Markets whose national competition/food/register sources we keep: CEE + JDE home + big
# Western markets + EU seats. Elsewhere we rely on EU-level coverage.
KEY_MARKETS = {
    "NL", "DE", "FR", "IT", "ES", "BE", "AT", "GR",
    "PL", "RO", "CZ", "HU", "BG", "HR", "SK", "SI", "EE", "LT", "LV",
}
FOOD_KW = ("food safety", "food standards", "aliment", "sanitar", "veterin", "efsa",
           "food authority", "siguran")
COMP_KW = ("competition", "concuren", "antitrust", "cartel", "kartell", "mededing",
           "concurrence", "concorrenza", "competencia", "konkuren", "verseny",
           "competit", "state aid")
ASSOC_KW = ("coffee", "tea", "caf", "food", "beverage", "drink", "fmcg", "retail",
            "grocery", "packaging", "sustainab", "eudr", "deforest", "commodit",
            "vending", "horeca", "roaster", "brand")


def text(s):
    return " ".join([s.get("name", ""), s.get("monitoring_focus", "")]).lower()


def keep(s):
    """Return (keep_bool, reason)."""
    t = s["type"]
    c = s.get("country", "")
    tx = text(s)
    cats = set(s.get("categories", []))

    if t in ("procurement", "recruitment"):
        return False, "out-of-scope (procurement/recruitment)"
    if t in ("eu_institution", "court", "trade_press", "market_data",
             "ngo", "consumer_org", "union", "law_firm_blog", "press", "academic"):
        return True, "core value for the reader"
    if t == "association":
        if any(k in tx for k in ASSOC_KW):
            return True, "sector association (coffee/food/retail/sustainability)"
        return False, "generic association (off-topic)"
    if t == "national_authority":
        if any(k in tx for k in COMP_KW):
            return True, "competition authority"
        if c in KEY_MARKETS and any(k in tx for k in FOOD_KW):
            return True, "food-safety authority (key market)"
        return False, "national authority (non-competition / peripheral)"
    if t == "official_register":
        if c == "EU" or c in KEY_MARKETS:
            return True, "official gazette (EU / key market)"
        return False, "official register (peripheral market)"
    if t == "regulator":
        if c in ("EU", "EEA"):
            return True, "EU/EEA-level regulator (IP, chemicals/packaging, competition)"
        return False, "national data-protection/environment regulator (low signal)"
    if t == "corporate":
        if s.get("id", "").startswith("jdepeets") or "jde peet" in tx or "keurig" in tx:
            return True, "JDE Peet's / KDP channel"
        if "competitors_direct" in cats:
            return True, "direct competitor corporate channel"
        return False, "brand microsite / adjacent (rarely publishes legal-corporate news)"
    return True, "kept (uncategorized type)"


def apply_keeplist(path):
    """Mark every active source NOT in the curated keep-list as excluded (reversible)."""
    import json
    data = yaml.safe_load(REG.read_text(encoding="utf-8"))
    keep = set(json.loads(Path(path).read_text(encoding="utf-8"))["keep"])
    active = [s for s in data["sources"] if s.get("status") == "active"]
    all_ids = {s["id"] for s in data["sources"]}
    missing = keep - all_ids
    if missing:
        print("ERROR: keep-list has unknown ids:", sorted(missing)[:10])
        sys.exit(1)
    excluded = 0
    for s in data["sources"]:
        if s.get("status") == "active" and s["id"] not in keep:
            s["status"] = "excluded"
            s["exclusion_reason"] = ("triage: outside focused Legal & Corporate Affairs set "
                                     "(CEE reader); reversible via monthly scout")
            excluded += 1
    REG.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110),
                   encoding="utf-8")
    from collections import Counter
    now_active = [s for s in data["sources"] if s.get("status") == "active"]
    print(f"Applied. Was active: {len(active)}  ->  now active: {len(now_active)}  (excluded {excluded})")
    for t, n in Counter(s["type"] for s in now_active).most_common():
        print(f"  {n:4}  {t}")


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--apply-keeplist":
        apply_keeplist(sys.argv[2])
        return
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    data = yaml.safe_load(REG.read_text(encoding="utf-8"))
    active = [s for s in data["sources"] if s.get("status") == "active"]

    if mode == "--inspect":
        by_type = {}
        for s in active:
            by_type.setdefault(s["type"], []).append(s)
        for t in ("regulator", "corporate", "association", "national_authority", "official_register"):
            print(f"\n===== {t} ({len(by_type.get(t, []))}) =====")
            for s in by_type.get(t, []):
                print(f"  {s.get('country','?'):3} | {s['name'][:50]:50} | {','.join(s.get('categories',[])[:2])}")
        return

    kept, dropped = [], []
    for s in active:
        k, reason = keep(s)
        (kept if k else dropped).append((s, reason))

    print(f"ACTIVE now: {len(active)}  ->  KEEP: {len(kept)}   DROP: {len(dropped)}")
    from collections import Counter
    print("\n--- kept by type ---")
    for t, n in Counter(s["type"] for s, _ in kept).most_common():
        print(f"  {n:4}  {t}")
    print("\n--- dropped by reason ---")
    for r, n in Counter(reason for _, reason in dropped).most_common():
        print(f"  {n:4}  {r}")

    if "--show" in sys.argv:
        for t in ("national_authority", "corporate", "association", "eu_institution"):
            print(f"\n--- KEPT {t} ---")
            for s, _ in kept:
                if s["type"] == t:
                    print(f"  {s.get('country','?'):3} | {s['name'][:56]}")

    if mode == "--apply":
        drop_ids = {s["id"] for s, _ in dropped}
        reasons = {s["id"]: r for s, r in dropped}
        for s in data["sources"]:
            if s["id"] in drop_ids:
                s["status"] = "excluded"
                s["exclusion_reason"] = "triage (focused Legal&Corporate set): " + reasons[s["id"]]
        REG.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110),
                       encoding="utf-8")
        print(f"\nAPPLIED: {len(drop_ids)} sources marked excluded. Active now: {len(kept)}")


if __name__ == "__main__":
    main()
