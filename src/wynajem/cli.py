"""Polecenia: uv run wynajem <polecenie>

  szukaj        – jedno pełne wyszukiwanie (pobranie, filtry, powiadomienia, strona)
  szukaj --bez-powiadomien – to samo, ale bez wysyłania pushy (do testów)
  przelicz      – ponowna ocena znanych ofert po zmianie config.yaml (bez pobierania)
  test-push     – wysyła próbne powiadomienie na telefon
  osm-build     – przebudowanie danych mapy (rzadko)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(prog="wynajem")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("szukaj")
    s.add_argument("--bez-powiadomien", action="store_true")
    s.add_argument("--tylko", help="tylko te źródła, np. otodom,morizon")
    s.add_argument("--wymus", action="store_true", help="uruchom też poza godzinami z harmonogramu")
    sub.add_parser("test-push")
    sub.add_parser("zdjecia", help="dopobranie zdjęć dla znanych ofert")
    sub.add_parser("przelicz", help="ponowna ocena znanych ofert po zmianie config.yaml")
    b = sub.add_parser("osm-build")
    b.add_argument("pbf", nargs="?")
    a = p.parse_args()

    if a.cmd == "osm-build":
        from .osm_build import build
        print(build(Path(a.pbf) if a.pbf else None))
    elif a.cmd == "zdjecia":
        from .run import backfill_photos
        sys.exit(backfill_photos())
    elif a.cmd == "przelicz":
        from .run import recompute
        sys.exit(recompute())
    elif a.cmd == "test-push":
        from .notify import test_push
        test_push()
    elif a.cmd == "szukaj":
        from .run import run
        sys.exit(run(notify=not a.bez_powiadomien, only=a.tylko.split(",") if a.tylko else None,
                     force=a.wymus))
