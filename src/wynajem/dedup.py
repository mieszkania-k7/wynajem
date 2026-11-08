"""Duplikaty: to samo mieszkanie z kilku portali (albo od kilku biur) = jedna pozycja.

Dopasowanie: metraż ±1,5 m² i cena najmu ±3% oraz bliskość: współrzędne ≤ 150 m (gdy obie dokładne)
albo ta sama ulica (albo, przy przybliżeniu bez ulicy, ten sam obszar i identyczny metraż i cena).
"""
from __future__ import annotations

import math

from .geo import norm_street

_KX = 111_320 * math.cos(math.radians(52.23))
_KY = 110_574


def _dist(a: dict, b: dict) -> float | None:
    if a.get("lat") is None or b.get("lat") is None:
        return None
    return math.hypot((a["lng"] - b["lng"]) * _KX, (a["lat"] - b["lat"]) * _KY)


def same_flat(a: dict, b: dict, exact_m: int = 150) -> bool:
    if a.get("area") is None or b.get("area") is None or a.get("price") is None or b.get("price") is None:
        return False
    if abs(a["area"] - b["area"]) > 1.5:
        return False
    if abs(a["price"] - b["price"]) > 0.03 * max(a["price"], b["price"]):
        return False
    sa, sb = norm_street(a.get("street")), norm_street(b.get("street"))
    if sa and sb:
        if sa != sb and sa.split()[-1] != sb.split()[-1]:
            return False
        d = _dist(a, b)
        exact = not a.get("approx") and not b.get("approx")
        return not (exact and d is not None and d > exact_m)
    d = _dist(a, b)
    if d is not None and not a.get("approx") and not b.get("approx"):
        return d <= exact_m
    # bez ulic i bez dokładnych współrzędnych – tylko przy identycznych parametrach w tym samym obszarze
    return (a.get("area_label") == b.get("area_label") and abs(a["area"] - b["area"]) <= 0.5
            and a["price"] == b["price"])
