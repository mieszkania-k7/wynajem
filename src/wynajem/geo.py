"""Mapa: granice dzielnic/osiedli, stacje metra i kolei, ulice – wszystko z lokalnych plików geo/*.json.

Współrzędne przeliczamy do lokalnego układu w metrach (wokół Warszawy) – dla kilku km błąd < 0,5%.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from functools import lru_cache

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint, Point, shape
from shapely.strtree import STRtree

from .config import GEO

LAT0, LON0 = 52.23, 21.0
KX = 111_320 * math.cos(math.radians(LAT0))
KY = 110_574


def to_xy(lon: float, lat: float) -> tuple[float, float]:
    return (lon - LON0) * KX, (lat - LAT0) * KY


def to_lonlat(x: float, y: float) -> tuple[float, float]:
    return x / KX + LON0, y / KY + LAT0


def _proj(geom):
    return shapely.transform(geom, lambda c: (c - np.array([LON0, LAT0])) * np.array([KX, KY]))


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").replace("ł", "l")


def norm_street(name: str | None) -> str:
    """„ul. gen. Tadeusza Bora-Komorowskiego 56C” → „tadeusza bora-komorowskiego”."""
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"^(ul\.|ulica|al\.|aleja|aleje|pl\.|plac|os\.|osiedle|rondo)\s*", "", s)
    s = re.sub(r"^(al\.|aleja)\s*", "", s)
    s = re.sub(r"\b(gen\.|generała|ks\.|księdza|św\.|świętego|płk\.|pułkownika|marsz\.|marszałka|prof\.|"
               r"profesora|dr\.?|kard\.|kardynała|mjr\.?|majora|kpt\.?|kapitana|por\.|porucznika)\s*", "", s)
    s = re.sub(r"\s+\d+[a-z]?(/\d+)?$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_name(s: str | None) -> str:
    return strip_accents((s or "").lower()).replace("-", " ").replace("  ", " ").strip()


class _Points:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.geoms = [Point(*to_xy(i["lon"], i["lat"])) for i in items]
        self.tree = STRtree(self.geoms) if self.geoms else None

    def nearest(self, x: float, y: float) -> tuple[float, str] | None:
        if not self.tree:
            return None
        idx, dist = self.tree.query_nearest(Point(x, y), return_distance=True)
        return float(dist[0]), self.items[int(idx[0])]["name"]


class Geo:
    def __init__(self) -> None:
        load = lambda n: json.loads((GEO / f"{n}.json").read_text(encoding="utf-8"))
        metro = load("metro")
        named = _Points([m for m in metro if m["name"]])
        for m in metro:   # wejścia do metra zwykle bez nazwy – bierzemy nazwę najbliższej stacji
            if not m["name"]:
                n = named.nearest(*to_xy(m["lon"], m["lat"]))
                m["name"] = n[1] if n and n[0] < 400 else "metro"
            m["name"] = re.sub(r"\s*\(.*\)$", "", m["name"]).replace("Metro ", "")
        self.metro = _Points(metro)
        rail = [r for r in load("kolej") if "WKD" not in r["name"] and "Wąskotorow" not in r["name"]]
        self.rail_items = rail
        self.rail = _Points(rail)

        self.areas: list[tuple[str, str, object]] = []   # (poziom, nazwa, geometria)
        for b in load("granice"):
            self.areas.append((b["admin_level"], b["name"], _proj(shape(b["geometry"]))))
        self._area_tree = STRtree([a[2] for a in self.areas])

        self._streets: dict[str, list[LineString]] = {}
        for r in load("ulice"):
            k = norm_street(r["name"])
            if k and len(r["coords"]) > 1:
                self._streets.setdefault(k, []).append(LineString([to_xy(*c) for c in r["coords"]]))
        self._streets_noacc = {strip_accents(k): k for k in self._streets}

    # --- zapytania ---------------------------------------------------------
    def where(self, x: float, y: float) -> list[str]:
        """Nazwy wszystkich obszarów (dzielnica, osiedla, gmina), w których leży punkt."""
        p = Point(x, y)
        return [self.areas[i][1] for i in self._area_tree.query(p, predicate="within")]

    def where_levels(self, x: float, y: float) -> list[tuple[str, str]]:
        p = Point(x, y)
        return [(self.areas[i][0], self.areas[i][1]) for i in self._area_tree.query(p, predicate="within")]

    def street_min_dist(self, street: str, area: str | None, nearest) -> float | None:
        """Najmniejsza odległość od ulicy (jej odcinka w danym obszarze) do obiektu z funkcji `nearest`.
        Pozwala odrzucić ofertę z przybliżoną lokalizacją, gdy CAŁA ulica jest za daleko od stacji."""
        geoms = self.area_geoms(area) if area else []
        best = None
        for line in self.street_lines(street):
            n = max(2, int(line.length // 50))
            for i in range(n + 1):
                p = line.interpolate(i / n, normalized=True)
                if geoms and not any(g.distance(p) < 100 for g in geoms):
                    continue
                r = nearest(p.x, p.y)
                if r and (best is None or r[0] < best):
                    best = r[0]
        return best

    def area_geoms(self, name: str) -> list:
        return [g for _, n, g in self.areas if norm_name(n) == norm_name(name)]

    def nearest_metro(self, x: float, y: float):
        return self.metro.nearest(x, y)

    def nearest_rail(self, x: float, y: float, names: list[str] | None = None):
        if names:
            pts = [(Point(*to_xy(r["lon"], r["lat"])).distance(Point(x, y)), r["name"])
                   for r in self.rail_items if r["name"] in names]
            return min(pts) if pts else None
        return self.rail.nearest(x, y)

    def dist_to_station(self, name: str, x: float, y: float) -> float | None:
        ds = [Point(*to_xy(r["lon"], r["lat"])).distance(Point(x, y)) for r in self.rail_items if r["name"] == name]
        return min(ds) if ds else None

    def street_lines(self, name: str | None) -> list[LineString]:
        key = norm_street(name)
        if not key:
            return []
        if key in self._streets:
            return self._streets[key]
        k2 = self._streets_noacc.get(strip_accents(key))
        if k2:
            return self._streets[k2]
        last = key.split()[-1]   # „Floriana Znanieckiego” ↔ „Znanieckiego”
        cands = [k for k in self._streets if k.split()[-1] == last] if len(last) > 3 else []
        return [l for k in cands for l in self._streets[k]]

    def dist_to_street(self, name: str, x: float, y: float) -> float | None:
        lines = self.street_lines(name)
        return min(l.distance(Point(x, y)) for l in lines) if lines else None

    def locate_street(self, street: str | None, area: str | None) -> tuple[float, float, int] | None:
        """Gdy portal nie podaje dokładnej pozycji: środek odcinka ulicy w danym obszarze
        i promień przybliżenia = rozpiętość odcinka. → (lat, lng, promień_m) albo None."""
        if not street:
            return None
        geoms = self.area_geoms(area) if area else []
        pts = []
        for line in self.street_lines(street):
            for i in range(21):
                p = line.interpolate(i / 20, normalized=True)
                if not geoms or any(g.contains(p) for g in geoms):
                    pts.append((p.x, p.y))
        if not pts:
            return None
        c = MultiPoint(pts).centroid
        spread = max(math.hypot(px - c.x, py - c.y) for px, py in pts)
        lng, lat = to_lonlat(c.x, c.y)
        return lat, lng, int(min(max(spread, 100), 2000))


@lru_cache
def get() -> Geo:
    return Geo()
