"""One-off Stage-2 merge: inventar + catalog PDF extractions -> sources/registry.yaml.

Kept in the repo for provenance; the registry is maintained by the pipeline and the
monthly-source-scout afterwards.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]


def dedup_key(url: str) -> str:
    p = urlparse(url)
    host = p.netloc.lower().removeprefix("www.")
    first_seg = p.path.strip("/").split("/")[0] if p.path.strip("/") else ""
    return f"{host}/{first_seg}"


def main(inventar_path: str, catalog_path: str) -> None:
    inventar = yaml.safe_load(Path(inventar_path).read_text(encoding="utf-8"))
    catalog = yaml.safe_load(Path(catalog_path).read_text(encoding="utf-8"))

    by_key = {dedup_key(e["url"]): e for e in inventar}
    ids = {e["id"] for e in inventar}
    added, merged = [], []
    for entry in catalog:
        key = dedup_key(entry["url"])
        if key in by_key:
            existing = by_key[key]
            existing["origin"] = "pdf_inventar+pdf_catalog"
            # catalog carries curated focus/exclusion info; keep the stricter status
            if entry["status"] in ("excluded", "review") and existing.get("status") == "active":
                existing["status"] = entry["status"]
                if entry.get("exclusion_reason"):
                    existing["exclusion_reason"] = entry["exclusion_reason"]
            merged.append(f'{entry["id"]} -> {existing["id"]}')
        else:
            while entry["id"] in ids:
                entry["id"] += "-cat"
            ids.add(entry["id"])
            added.append(entry["id"])
            by_key[key] = entry

    sources = inventar + [e for e in catalog if e["id"] in added]
    registry = {
        "registry_version": 1,
        "updated": "2026-07-18",
        "policy": {
            "auto_add_types": [
                "eu_institution", "national_authority", "court", "official_register", "regulator",
            ],
            "approval_required": "all other types (see config/settings.yaml source_policy)",
        },
        "sources": sources,
    }
    out = ROOT / "sources" / "registry.yaml"
    out.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False, width=110),
        encoding="utf-8",
    )
    statuses: dict[str, int] = {}
    for e in sources:
        statuses[e["status"]] = statuses.get(e["status"], 0) + 1
    print(f"inventar: {len(inventar)}  catalog: {len(catalog)}")
    print(f"merged into existing: {len(merged)}  ->  {merged}")
    print(f"added new from catalog: {len(added)}  ->  {added}")
    print(f"TOTAL registry: {len(sources)}  statuses: {statuses}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
