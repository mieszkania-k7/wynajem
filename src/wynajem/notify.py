"""Powiadomienia push przez ntfy.sh (darmowe, bez konta). Temat = długi losowy ciąg trzymany w sekrecie."""
from __future__ import annotations

import httpx

from .config import load, ntfy_topic

NTFY = "https://ntfy.sh"


def zl(v: float | None) -> str:
    return f"{int(round(v)):,}".replace(",", " ") + " zł" if v is not None else "?"


def send(title: str, message: str, click: str | None = None, attach: str | None = None,
         tags: list[str] | None = None, priority: int = 3) -> bool:
    topic = ntfy_topic()
    if not topic:
        print("  (brak tematu ntfy – powiadomienie pominięte)")
        return False
    body = {"topic": topic, "title": title, "message": message, "priority": priority}
    if click:
        body["click"] = click
    if attach:
        body["attach"] = attach
    if tags:
        body["tags"] = tags
    site = load().get("strona_url")
    if site:
        body["actions"] = [{"action": "view", "label": "Lista ofert", "url": site}]
    try:
        r = httpx.post(NTFY, json=body, timeout=20)
        return r.status_code == 200
    except httpx.HTTPError as e:
        print(f"  ntfy: błąd {e}")
        return False


def offer_message(o: dict) -> tuple[str, str]:
    """Treść pusha dla jednej oferty (format z zamówienia)."""
    star = "⭐ " if o.get("star") else ""
    place = o["area_label"].split(" · ")[-1]
    rooms = f" · {o['rooms']} pok." if o.get("rooms") else ""
    title = f"{star}{place} · {o['area']:g} m²{rooms}"
    if o.get("rent") is None:
        cost = f"{zl(o['price'])} + czynsz ? ⚠️ czynsz nieznany"
    elif o["rent"] == 0:
        cost = f"{zl(o['price'])} (czynsz w cenie)"
    else:
        cost = f"{zl(o['price'])} + czynsz {zl(o['rent'])} = {zl(o['total'])}"
    pets = {"tak": "🐕 tak", "nie": "🐕 nie"}.get(o.get("pets"), "🐕 brak info")
    line2 = [(o["street"] if o["street"].startswith(("al.", "pl.", "os.", "rondo")) else f"ul. {o['street']}")
             if o.get("street") else None, pets,
             "prowizja" if o.get("commission") else None, "📍 lok. przybliżona" if o.get("approx") else None]
    line3 = " · ".join(o.get("stations") or [])
    srcs = ", ".join(dict.fromkeys(l["label"] for l in o["links"]))
    if o.get("institutional"):
        srcs += " · 🏢 instytucjonalny"
    if o.get("praga_agency"):
        srcs += " · biuro z Pragi Płd."
    msg = "\n".join(x for x in (cost, " · ".join(p for p in line2 if p), line3, srcs) if x)
    return title, msg


def push_offer(o: dict) -> bool:
    title, msg = offer_message(o)
    return send(title, msg, click=o["links"][0]["url"], attach=o.get("photo"), tags=["house"])


def test_push() -> None:
    ok = send("Test – wyszukiwarka mieszkań", "Jeśli to widzisz, powiadomienia działają 🎉", tags=["tada"])
    print("Wysłano ✅" if ok else "Nie udało się wysłać ❌ (sprawdź temat ntfy)")
