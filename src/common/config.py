"""Load config/settings.yaml and sources/registry.yaml."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def load_registry() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "sources" / "registry.yaml").read_text(encoding="utf-8"))


def active_sources() -> list[dict[str, Any]]:
    return [s for s in load_registry()["sources"] if s.get("status") == "active"]
