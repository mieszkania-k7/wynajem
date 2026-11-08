from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"            # stan wyszukiwania (w repozytorium)
CACHE = ROOT / "cache"          # kopie stron z bieżącego dnia (poza repozytorium)
GEO = ROOT / "geo"              # dane mapy
SITE = ROOT / "docs"            # strona z listą (GitHub Pages publikuje folder docs/)


@lru_cache
def load() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def ntfy_topic() -> str | None:
    """Temat ntfy: na GitHubie z sekretu NTFY_TOPIC, na Macu z pliku sekret_ntfy.txt (nie trafia do repo)."""
    t = os.environ.get("NTFY_TOPIC")
    if t:
        return t.strip()
    f = ROOT / "sekret_ntfy.txt"
    return f.read_text().strip() if f.exists() and f.read_text().strip() else None
