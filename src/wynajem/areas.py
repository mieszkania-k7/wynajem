"""Czy oferta leży w jednej z lokalizacji z config.yaml? Sprawdzane po współrzędnych i granicach z OSM.

Zasada: przy lokalizacji przybliżonej NIE odrzucamy w obszarach z limitem odległości – oznaczamy „📍”.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import geo as geomod
from .config import load
from .geo import norm_name, norm_street, to_xy
from .models import Listing


@dataclass
class Verdict:
    ok: bool
    area: str | None = None          # nazwa obszaru do pokazania, np. „Praga-Południe · Kamionek”
    zone: str | None = None          # klucz obszaru z config.yaml
    star: bool = False
    approx: bool = False
    reason: str | None = None        # dlaczego odpada
    stations: list[str] = field(default_factory=list)   # np. ["🚇 Kabaty 320 m"]
    lat: float | None = None
    lng: float | None = None


def _fmt(icon: str, d: float, name: str, approx: bool) -> str:
    return f"{icon} {name.replace('Warszawa ', '')} {'~' if approx else ''}{int(round(d / 10) * 10)} m"


def position(lst: Listing, threshold: int) -> tuple[float | None, float | None, int, bool]:
    """(lat, lng, promień, przybliżona?) – gdy portal daje tylko środek dzielnicy, próbujemy ulicę."""
    g = geomod.get()
    approx = lst.approx_m if lst.approx_m is not None else 1500
    lat, lng = lst.lat, lst.lng
    if lat is None or approx > threshold:
        hint_parts = [p.strip() for p in (lst.district_hint or "").split(",") if p.strip()]
        for area in reversed(hint_parts or [None]):
            loc = g.locate_street(lst.street, area)
            if loc and loc[2] < approx:
                lat, lng, approx = loc
                break
    return lat, lng, approx, (lat is None or approx > threshold)


def evaluate(lst: Listing) -> Verdict:
    cfg = load()
    z = cfg["obszary"]
    ex = cfg["wykluczenia"]
    g = geomod.get()
    lat, lng, radius, approx = position(lst, cfg["przyblizenie_m"])
    hint = [p.strip() for p in (lst.district_hint or "").split(",") if p.strip()]

    names: list[str] = []
    levels: list[tuple[str, str]] = []
    x = y = None
    if lat is not None:
        x, y = to_xy(lng, lat)
        levels = g.where_levels(x, y)
        names = [n for _, n in levels]
    if approx:
        names = names + hint            # przy przybliżeniu ufamy też opisowi portalu
    have = {norm_name(n) for n in names}
    has = lambda n: norm_name(n) in have

    v = Verdict(ok=False, approx=approx, lat=lat, lng=lng)
    if x is not None:
        # najbliższa stacja zawsze, druga (metro/kolej) tylko gdy też jest w zasięgu spaceru
        cands = [("🚇", *m) for m in [g.nearest_metro(x, y)] if m] + [("🚆", *r) for r in [g.nearest_rail(x, y)] if r]
        cands.sort(key=lambda c: c[1])
        for i, (icon, d, name) in enumerate(cands):
            if i == 0 or d <= 1500:
                v.stations.append(_fmt(icon, d, name, approx))

    # --- wykluczenia (zawsze) ---
    for s in ex["ulice"]:
        if lst.street and norm_street(lst.street) == norm_street(s):
            v.reason = f"ulica {s}"
            return v
        if x is not None and not approx:
            d = g.dist_to_street(s, x, y)
            if d is not None and d <= ex["ulica_promien_m"]:
                v.reason = f"{int(d)} m od ul. {s}"
                return v
    if x is not None and not approx:
        for st in ex["dworce"]:
            d = g.dist_to_station(st, x, y)
            if d is not None and d <= ex["dworzec_promien_m"]:
                v.reason = f"{int(d)} m od dworca {st}"
                return v

    def ok(zone: str, label: str, star: bool = False) -> Verdict:
        v.ok, v.zone, v.area, v.star = True, zone, label, star
        return v

    sub = [n for n in names if norm_name(n) not in {norm_name(k) for k in (
        "Warszawa", "Praga-Południe", "Praga-Północ", "Targówek", "Mokotów", "Ursynów", "Wawer", "Wesoła",
        "mazowieckie")}]
    def detail(base: str) -> str:
        extra = [n for n in sub if norm_name(n) != norm_name(base)]
        return base + (f" · {extra[0]}" if extra else "")

    def street_too_far(area: str, limit: int, nearest) -> float | None:
        """Przybliżona lokalizacja, ale znana ulica: gdy CAŁA ulica jest dalej niż limit – pewne odrzucenie."""
        if not lst.street:
            return None
        d = g.street_min_dist(lst.street, area, nearest)
        return d if d is not None and d > limit else None

    pp = z["praga_poludnie"]
    if has(pp["nazwa"]):
        # gwiazdka tylko dla właściwego osiedla (poziom 10 MSI) albo gdy portal tak opisuje lokalizację
        stars = {norm_name(s) for s in pp.get("gwiazdka", [])}
        star = any(lvl == "10" and norm_name(n) in stars for lvl, n in levels) or \
            (approx and any(norm_name(h) in stars for h in hint))
        label = f"{pp['nazwa']} · {pp['gwiazdka'][0]}" if star else detail(pp["nazwa"])
        return ok("praga_poludnie", label, star)
    if has(z["praga_polnoc"]["nazwa"]):
        return ok("praga_polnoc", detail(z["praga_polnoc"]["nazwa"]))
    if has(z["targowek_mieszkaniowy"]["nazwa"]):
        return ok("targowek_mieszkaniowy", "Targówek Mieszkaniowy")
    if has(z["siekierki"]["nazwa"]):
        return ok("siekierki", "Mokotów · Siekierki")

    u = z["ursynow"]
    if has(u["nazwa"]):
        if x is None or approx:
            d = street_too_far("Ursynów", u["metro_max_m"], g.nearest_metro)
            if d:
                v.reason = f"Ursynów: cała ul. {lst.street} ≥ {int(d)} m od metra"
                return v
            return ok("ursynow", detail("Ursynów"))
        m = g.nearest_metro(x, y)
        if m and m[0] <= u["metro_max_m"]:
            return ok("ursynow", detail("Ursynów"))
        v.reason = f"Ursynów: metro {int(m[0])} m (limit {u['metro_max_m']} m)" if m else "Ursynów: brak metra"
        return v

    k = z["kolej"]
    for name in k["nazwy"]:
        if has(name):
            if x is None or approx:
                d = street_too_far(name, k["kolej_max_m"], g.nearest_rail)
                if d:
                    v.reason = f"{name}: cała ul. {lst.street} ≥ {int(d)} m od stacji"
                    return v
                return ok("kolej", detail(name))
            r = g.nearest_rail(x, y)
            if r and r[0] <= k["kolej_max_m"]:
                return ok("kolej", detail(name))
            v.reason = f"{name}: stacja {int(r[0])} m (limit {k['kolej_max_m']} m)" if r else f"{name}: brak stacji"
            return v

    w = z["osiedle_wilno"]
    if has(w["dzielnica"]) and x is not None:
        r = g.nearest_rail(x, y, w["stacje"])
        far = approx and street_too_far(w["dzielnica"], w["kolej_max_m"],
                                        lambda px, py: g.nearest_rail(px, py, w["stacje"]))
        if r and not far and (r[0] <= w["kolej_max_m"] or (approx and r[0] - radius <= w["kolej_max_m"])):
            return ok("osiedle_wilno", "Targówek · os. Wilno" if not approx else "Targówek (sprawdź, czy os. Wilno)")
        v.reason = f"Targówek (nie Mieszkaniowy): stacja Zacisze-Wilno {int(r[0])} m" if r else "Targówek"
        return v

    v.reason = "poza lokalizacjami: " + (", ".join(names[:3]) or "nieznana lokalizacja")
    return v
