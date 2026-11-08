"""Jednorazowe przygotowanie danych mapy z OpenStreetMap (ekstrakt Geofabrik, mazowieckie).

Wynik: małe pliki JSON w folderze geo/ (trzymane w repozytorium, więc wyszukiwanie ich nie pobiera).
Uruchomienie (rzadko, np. raz na pół roku): uv run --group geo wynajem osm-build [ścieżka.osm.pbf]
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import osmium
import shapely.wkb
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from .config import ROOT

GEOFABRIK_URL = "https://download.geofabrik.de/europe/poland/mazowieckie-latest.osm.pbf"
BBOX = (20.84, 52.05, 21.45, 52.40)   # Warszawa + Józefów, Halinów, Sulejówek, Zielonka
ZONE_NAMES = {"Praga-Południe", "Praga-Północ", "Targówek", "Mokotów", "Ursynów", "Wawer", "Wesoła",
              "Sulejówek", "Józefów", "Halinów", "Zielonka"}
ROAD_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
                "living_street", "pedestrian", "service"}


def _in_bbox(lon: float, lat: float) -> bool:
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


class _Handler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.wkb = osmium.geom.WKBFactory()
        self.bbox = box(*BBOX)
        self.metro: list[dict] = []
        self.rail: list[dict] = []
        self.roads: list[dict] = []
        self.boundaries: list[dict] = []

    def _point(self, tags, lon: float, lat: float, osm_id: str) -> None:
        rec = {"id": osm_id, "name": tags.get("name", ""), "lon": round(lon, 6), "lat": round(lat, 6)}
        rw = tags.get("railway")
        if rw == "subway_entrance" or (rw == "station" and tags.get("station") == "subway") \
                or (tags.get("public_transport") == "station" and tags.get("subway") == "yes"):
            self.metro.append(rec)
        elif rw in ("station", "halt") and tags.get("station") not in ("subway", "light_rail", "tram") \
                and tags.get("tram") != "yes" and rec["name"]:
            self.rail.append(rec)

    def node(self, n) -> None:
        if n.tags and n.location.valid() and _in_bbox(n.location.lon, n.location.lat):
            self._point(n.tags, n.location.lon, n.location.lat, f"n{n.id}")

    def way(self, w) -> None:
        hw = w.tags.get("highway")
        name = w.tags.get("name", "")
        if hw not in ROAD_CLASSES or not name:
            return
        try:
            coords = [(round(nd.lon, 6), round(nd.lat, 6)) for nd in w.nodes]
        except osmium.InvalidLocationError:
            return
        if any(_in_bbox(*c) for c in coords):
            self.roads.append({"name": name, "coords": coords})

    def area(self, a) -> None:
        t = a.tags
        is_boundary = t.get("boundary") == "administrative" and t.get("admin_level") in ("7", "8", "9", "10", "11")
        is_station = t.get("railway") in ("station", "halt")
        if not (is_boundary or is_station):
            return
        try:
            geom = shapely.wkb.loads(self.wkb.create_multipolygon(a), hex=True)
        except Exception:
            return
        if not geom.intersects(self.bbox):
            return
        if is_station:
            c = geom.representative_point()
            self._point(t, c.x, c.y, f"a{a.orig_id()}")
        else:
            self.boundaries.append({"name": t.get("name", ""), "admin_level": t.get("admin_level"),
                                    "geometry": mapping(geom.simplify(0.00002))})


def download(pbf: Path) -> None:
    pbf.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", GEOFABRIK_URL, follow_redirects=True, timeout=600) as r:
        r.raise_for_status()
        with pbf.with_suffix(".part").open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    pbf.with_suffix(".part").replace(pbf)


def build(pbf: Path | None = None) -> dict[str, int]:
    if pbf is None:
        pbf = ROOT / "cache" / "mazowieckie-latest.osm.pbf"
        if not pbf.exists():
            download(pbf)
    h = _Handler()
    h.apply_file(str(pbf), locations=True, idx="flex_mem")

    # granice: tylko te, które dotykają naszych obszarów (dzielnice, osiedla, gminy) – mniejszy plik
    zones = unary_union([shape(b["geometry"]) for b in h.boundaries if b["name"] in ZONE_NAMES
                         and b["admin_level"] in ("7", "8", "9")]).buffer(0.01)
    bounds = [b for b in h.boundaries if shape(b["geometry"]).intersects(zones)]
    # ulice: tylko w naszych obszarach (do ustalania położenia po nazwie ulicy i do wykluczeń)
    roads = [r for r in h.roads if any(zones.contains(shapely.Point(c)) for c in r["coords"][::3] + r["coords"][-1:])]

    out = ROOT / "geo"
    out.mkdir(exist_ok=True)
    for name, items in (("metro", h.metro), ("kolej", h.rail), ("granice", bounds), ("ulice", roads)):
        (out / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, separators=(",", ":")))
    (out / "_meta.json").write_text(json.dumps({"zbudowano": time.strftime("%Y-%m-%d"), "bbox": BBOX}))
    return {"metro": len(h.metro), "kolej": len(h.rail), "granice": len(bounds), "ulice": len(roads)}
