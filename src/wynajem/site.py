"""Dane dla strony z listą (docs/dane.js) – jedna pozycja na mieszkanie, z linkami do wszystkich źródeł."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import SITE, load

TZ = ZoneInfo("Europe/Warsaw")


def clean_street(s: str | None) -> str | None:
    """„ul. Poligonowa” → „Poligonowa”, „al. Aleja Stanów Zjednoczonych” → „al. Stanów Zjednoczonych”."""
    if not s:
        return s
    s = re.sub(r"^(ul\.|ulica)\s*", "", s.strip(), flags=re.I)
    s = re.sub(r"^(al\.\s*)?aleja\s+", "al. ", s, flags=re.I)
    return s


def _first(recs: list[dict], field: str):
    for r in recs:
        if r.get(field) is not None:
            return r[field], r
    return None, None


def merge_group(recs: list[dict]) -> dict:
    # najpierw ogłoszenia z dokładną lokalizacją i podanym czynszem
    recs = sorted(recs, key=lambda r: (bool(r.get("approx")), r.get("rent") is None, r.get("first_seen", "")))
    main = recs[0]
    rent, rr = _first(recs, "rent")
    pets = next((r for r in recs if r.get("pets") == "nie"), None) or next((r for r in recs if r.get("pets")), None)
    comm = next((r for r in recs if r.get("commission")), None) or next(
        (r for r in recs if r.get("commission") is not None), None)
    dates = sorted(d for d in (r.get("date_created") for r in recs) if d)
    price = main.get("price")
    o = {
        "id": main["group"],
        "title": main.get("title") or "",
        "area_label": next((r["area_label"] for r in recs if r.get("star")), None) if any(r.get("star") for r in recs)
        else (main.get("area_label") or "?"),
        "zone": main.get("zone"),
        "star": any(r.get("star") for r in recs),
        "approx": all(r.get("approx") for r in recs),
        "area": main.get("area"),
        "rooms": main.get("rooms") or _first(recs, "rooms")[0],
        "floor": main.get("floor") or _first(recs, "floor")[0],
        "street": clean_street(main.get("street") or _first(recs, "street")[0]),
        "price": price,
        "rent": rent,
        "rent_evidence": rr.get("rent_evidence") if rr else None,
        "total": (price or 0) + (rent or 0),
        "stations": main.get("stations") or [],
        "pets": pets.get("pets") if pets else None,
        "pets_evidence": pets.get("pets_evidence") if pets else None,
        "commission": comm.get("commission") if comm else None,
        "commission_evidence": comm.get("commission_evidence") if comm else None,
        "praga_agency": any(r.get("praga_agency") for r in recs),
        "institutional": any(r.get("institutional") for r in recs),
        "agencies": sorted({r["agency"] for r in recs if r.get("agency")}),
        "photo": next((r["photo"] for r in recs if r.get("photo")), None),
        "photos": max((r.get("photos") or [] for r in recs), key=len, default=[])[:10],
        "date_created": dates[0][:10] if dates else None,
        "first_seen": min(r.get("first_seen", "") for r in recs),
        "lat": main.get("lat"), "lng": main.get("lng"),
        "links": [{"source": r["source"], "label": r.get("label") or r["source"], "url": r["url"],
                   "active": r.get("active", True)} for r in recs],
        "gone_at": max((r.get("gone_at") or "") for r in recs) if not any(r.get("active") for r in recs) else None,
    }
    return o


def build_offers(st: dict) -> dict:
    groups: dict[str, list[dict]] = {}
    for r in st["listings"].values():
        if r.get("status") == "ok" and r.get("group"):
            groups.setdefault(r["group"], []).append(r)
    active, gone = [], []
    cutoff = (datetime.now(TZ) - timedelta(days=14)).isoformat()
    long_cutoff = (datetime.now(TZ) - timedelta(days=120)).isoformat()
    try:   # statusy ustawione na stronie (❤️ zapisana / 👀 obejrzana) – takie oferty zostają dłużej
        statuses = json.loads((SITE / "statusy.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        statuses = {}
    for recs in groups.values():
        o = merge_group(recs)
        if o["gone_at"] is None:
            o["links"] = [l for l in o["links"] if l["active"]] or o["links"]
            active.append(o)
        elif o["gone_at"] >= cutoff or (o["gone_at"] >= long_cutoff and
                                        (statuses.get(o["id"]) or {}).get("status") in ("zapisana", "obejrzana")):
            gone.append(o)
    key = lambda o: (o.get("date_created") or o["first_seen"][:10], o["first_seen"])
    active.sort(key=key, reverse=True)
    gone.sort(key=lambda o: o["gone_at"], reverse=True)
    return {"active": active, "gone": gone}


def write(st: dict, offers: dict) -> None:
    cfg = load()
    data = {
        "generated": st.get("last_run"),
        "koszt_max": cfg["kryteria"]["koszt_max"],
        "sources": [{"name": n, "label": s.get("label", n), "ok": s.get("ok", False), "count": s.get("count", 0),
                     "last_ok": s.get("last_ok"), "error": s.get("error"), "failures": s.get("failures", 0)}
                    for n, s in st["sources"].items()],
        "offers": offers["active"],
        "gone": offers["gone"],
    }
    SITE.mkdir(exist_ok=True)
    js = "window.DANE = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (SITE / "dane.js").write_text(js, encoding="utf-8")
