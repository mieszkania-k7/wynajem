"""Jedno pełne wyszukiwanie: źródła → filtry → duplikaty → powiadomienia → strona."""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import areas, site, text
from . import notify as ntfy
from .config import DATA, load
from .dedup import same_flat
from .http import Fetcher
from .models import Listing, SourceBlocked
from .sources.domiporta import Domiporta
from .sources.morizon import Morizon
from .sources.otodom import Otodom

TZ = ZoneInfo("Europe/Warsaw")
SOURCES = {"otodom": Otodom, "morizon": Morizon, "domiporta": Domiporta}
STATE = DATA / "stan.json"
MAX_PUSHES = 15          # więcej nowych naraz → jedno zbiorcze powiadomienie
KEEP_GONE_DAYS = 14      # tyle dni zniknięte oferty wiszą w sekcji „nieaktualne”


def now() -> datetime:
    return datetime.now(TZ)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"first_run_done": False, "listings": {}, "groups": {}, "sources": {}}


def save_state(st: dict) -> None:
    DATA.mkdir(exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def in_schedule() -> bool:
    h = load()["harmonogram"]
    return h["godzina_od"] <= now().hour <= h["godzina_do"]


def _too_old(date: str | None, days: int) -> bool:
    if not date:
        return False
    try:
        d = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except ValueError:
        return False
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d < now() - timedelta(days=days)


def judge(lst: Listing, src_label: str) -> dict:
    """Ocenia jedno (już uzupełnione) ogłoszenie. → rekord do zapisania w stanie."""
    cfg = load()
    k = cfg["kryteria"]
    text.enrich(lst)
    rec = lst.to_dict()
    rec["label"] = src_label
    reason = text.rejected_type(lst, cfg["odrzuc_slowa"])
    if not reason and lst.area is not None and lst.area < k["metraz_min"]:
        reason = f"metraż {lst.area:g} m²"
    total = (lst.price or 0) + (lst.rent or 0) if lst.price is not None else None
    rec["total"] = total
    if not reason and lst.price is None:
        reason = "brak ceny"
    if not reason and total is not None and total > k["koszt_max"]:
        reason = f"koszt {total:.0f} zł"
    v = areas.evaluate(lst)
    rec.update(area_label=v.area, zone=v.zone, star=v.star, approx=v.approx, stations=v.stations)
    if v.lat is not None:            # pozycja mogła zostać doprecyzowana po ulicy
        rec["lat"], rec["lng"] = v.lat, v.lng
    if not reason and not v.ok:
        reason = v.reason
    agencies = [a.lower() for a in cfg.get("biura_praga_pld", [])]
    rec["praga_agency"] = bool(lst.agency and any(a in lst.agency.lower() for a in agencies))
    inst = [a.lower() for a in cfg.get("instytucjonalni", [])]
    rec["institutional"] = bool(lst.agency and any(a in lst.agency.lower() for a in inst))
    rec["status"] = "odrzucona" if reason else "ok"
    rec["reason"] = reason
    return rec


def run(notify: bool = True, only: list[str] | None = None, force: bool = False) -> int:
    notify_on = notify
    if not force and not in_schedule():
        print("Poza godzinami wyszukiwania – nic nie robię.")
        return 0
    cfg = load()
    st = load_state()
    first_run = not st["first_run_done"]
    ts = now().isoformat(timespec="seconds")
    fetcher = Fetcher()
    t0 = time.time()
    print(f"Wyszukiwanie {ts}{' (pierwsze)' if first_run else ''}")

    for name, cls in SOURCES.items():
        if only and name not in only:
            continue
        if not cfg["zrodla"].get(name, False):
            continue
        src = cls(fetcher)
        sst = st["sources"].setdefault(name, {"label": src.label, "failures": 0, "alerted": False})
        sst["label"] = src.label
        try:
            stubs = src.search()
            if not stubs:
                raise RuntimeError("brak wyników – możliwa zmiana wyglądu strony")
        except Exception as e:
            sst.update(ok=False, error=str(e)[:200], failures=sst.get("failures", 0) + 1, last_try=ts)
            print(f"  ✗ {src.label}: {e}")
            if not isinstance(e, (SourceBlocked, RuntimeError)):
                traceback.print_exc()
            continue

        seen_now = set()
        new_count = details = 0
        blocked = None
        for lst in stubs:
            key = lst.key
            seen_now.add(key)
            old = st["listings"].get(key)
            if old and (old.get("price") == lst.price or lst.price is None):
                old.update(last_seen=ts, missing=0, active=True)
                old.pop("gone_at", None)
                continue
            if not src.prefilter(lst):
                st["listings"][key] = {**lst.to_dict(), "label": src.label, "status": "odrzucona",
                                       "reason": "cena/metraż z listy", "first_seen": ts, "last_seen": ts,
                                       "missing": 0, "active": True}
                continue
            if first_run and _too_old(lst.date_created, cfg["kryteria"]["pierwsze_uruchomienie_dni"]):
                st["listings"][key] = {**lst.to_dict(), "label": src.label, "status": "stara",
                                       "reason": "dodana ponad 2 mies. temu", "first_seen": ts,
                                       "last_seen": ts, "missing": 0, "active": True}
                continue
            if blocked is None:
                try:
                    if not src.fetch_detail(lst):
                        seen_now.discard(key)
                        continue
                    details += 1
                except SourceBlocked as e:
                    blocked = str(e)       # dalsze szczegóły w tym przebiegu pomijamy
                except Exception as e:
                    src.problems.append(f"{key}: {type(e).__name__}: {e}"[:200])
            if first_run and _too_old(lst.date_created, cfg["kryteria"]["pierwsze_uruchomienie_dni"]):
                rec = {**lst.to_dict(), "label": src.label, "status": "stara", "reason": "dodana ponad 2 mies. temu"}
            else:
                rec = judge(lst, src.label)
            if old:
                rec["first_seen"] = old.get("first_seen", ts)
                rec["group"] = old.get("group")
                rec["price_before"] = old.get("price")
            else:
                rec["first_seen"] = ts
                new_count += rec["status"] == "ok"
            rec.update(last_seen=ts, missing=0, active=True)
            st["listings"][key] = rec

        # zniknięcia (tylko gdy źródło zadziałało): 2 przebiegi z rzędu bez ogłoszenia = nieaktualne
        for key, rec in st["listings"].items():
            if rec.get("source") == name and key not in seen_now and rec.get("active"):
                rec["missing"] = rec.get("missing", 0) + 1
                if rec["missing"] >= 2:
                    rec["active"] = False
                    rec["gone_at"] = ts
        if blocked:
            src.problems.append(f"szczegóły przerwane: {blocked}")
        sst.update(ok=True, error=None, failures=0, alerted=False, last_ok=ts, last_try=ts,
                   count=sum(1 for r in st["listings"].values()
                             if r.get("source") == name and r.get("active") and r.get("status") == "ok"),
                   found=len(stubs), problems=src.problems[:10])
        print(f"  ✓ {src.label}: {len(stubs)} na listach, pobrano {details} ogłoszeń, nowych pasujących: {new_count}"
              + (f" | problemy: {len(src.problems)}" if src.problems else ""))

    new_groups = assign_groups(st)
    offers = site.build_offers(st)
    pushes = 0
    if notify_on:
        if first_run:
            n = len(offers["active"])
            if n:
                ntfy.send(f"Znaleziono {n} ofert", "Pierwsze wyszukiwanie zakończone. Kolejne nowe oferty "
                            "będą przychodzić pojedynczo.", click=cfg.get("strona_url") or None, tags=["house"])
            for g in new_groups:
                st["groups"][g]["notified"] = True
        else:
            fresh = [o for o in offers["active"] if o["id"] in new_groups]
            if len(fresh) > MAX_PUSHES:
                ntfy.send(f"{len(fresh)} nowych ofert", "Dużo nowych naraz – zobacz listę.",
                            click=cfg.get("strona_url") or None, tags=["house"])
            else:
                for o in fresh:
                    pushes += ntfy.push_offer(o)
            for g in new_groups:
                st["groups"][g]["notified"] = True
        for name, sst in st["sources"].items():
            if sst.get("failures", 0) >= cfg["pobieranie"]["awarie_do_alertu"] and not sst.get("alerted"):
                ntfy.send(f"Źródło {sst['label']} nie działa",
                            f"{sst['failures']} nieudane przebiegi z rzędu. Ostatni błąd: {sst.get('error')}",
                            tags=["warning"], priority=4)
                sst["alerted"] = True

    st["first_run_done"] = True
    st["last_run"] = ts
    st["last_run_seconds"] = round(time.time() - t0)
    prune(st)
    save_state(st)
    site.write(st, offers)
    print(f"Gotowe: {len(offers['active'])} aktualnych ofert, nowych: {len(new_groups)}, "
          f"wysłanych pushy: {pushes}, zapytań: {fetcher.requests}, czas: {round(time.time() - t0)} s")
    return 0


def assign_groups(st: dict) -> list[str]:
    """Łączy duplikaty w grupy. → identyfikatory NOWYCH grup (= nowe mieszkania do powiadomienia)."""
    ok = {k: r for k, r in st["listings"].items() if r.get("status") == "ok"}
    grouped = [r for r in ok.values() if r.get("group") in st["groups"]]
    new: list[str] = []
    for key, r in sorted(ok.items(), key=lambda kv: kv[1].get("first_seen", "")):
        if r.get("group") in st["groups"] or not r.get("active"):
            continue
        match = next((g for g in grouped if same_flat(r, g)), None)
        if match:
            r["group"] = match["group"]
        else:
            r["group"] = key
            st["groups"][key] = {"first_seen": r.get("first_seen"), "notified": False}
            new.append(key)
        grouped.append(r)
    return [g for g in new if not st["groups"][g].get("notified")]


def prune(st: dict) -> None:
    """Usuwa bardzo stare wpisy, żeby plik stanu nie rósł bez końca."""
    limit = (now() - timedelta(days=120)).isoformat()
    for k in [k for k, r in st["listings"].items() if not r.get("active") and r.get("gone_at", "") < limit]:
        del st["listings"][k]
    used = {r.get("group") for r in st["listings"].values()}
    for g in [g for g in st["groups"] if g not in used]:
        del st["groups"][g]
