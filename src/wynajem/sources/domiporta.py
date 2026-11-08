"""Domiporta (wynajem): lista w HTML (article[data-detail-id]), ogłoszenie w JSON-LD (RealEstateListing).

Współrzędne Domiporty bywają środkiem osiedla – traktujemy je jako przybliżone (ulica rozstrzyga).
"""
from __future__ import annotations

import re

from selectolax.lexbor import LexborHTMLParser

from ..models import Listing
from .base import BaseSource, html_to_text, ld_find, ld_json, to_float

BASE = "https://www.domiporta.pl"
PATHS = ["mazowieckie/warszawa/praga-poludnie", "mazowieckie/warszawa/praga-polnoc", "mazowieckie/warszawa/targowek",
         "mazowieckie/warszawa/mokotow", "mazowieckie/warszawa/ursynow", "mazowieckie/warszawa/wawer",
         "mazowieckie/warszawa/wesola", "mazowieckie/sulejowek", "mazowieckie/jozefow", "mazowieckie/halinow",
         "mazowieckie/zielonka"]


def _num(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"\d[\d\s\xa0]*(?:[.,]\d+)?", text.replace("&nbsp;", " "))
    return to_float(m.group(0).replace(" ", "").replace("\xa0", "")) if m else None


class Domiporta(BaseSource):
    name = "domiporta"
    label = "Domiporta"

    def search_url(self, path: str, page: int) -> str:
        return (f"{BASE}/mieszkanie/wynajme/{path}?Surface.From={self.area_min}&Price.To={self.cost_max}"
                f"&SortingOrder=InsertionDate" + (f"&PageNumber={page}" if page > 1 else ""))

    def search(self) -> list[Listing]:
        found: dict[str, Listing] = {}
        for path in PATHS:
            for page in range(1, self.max_pages + 1):
                status, html = self.fetcher.get(self.search_url(path, page))
                if status != 200:
                    if status != 404:
                        self.problems.append(f"{path} str. {page}: HTTP {status}")
                    break
                items, total = self.parse_search(html)
                new = [s for s in items if s.source_id not in found]
                for s in new:
                    found[s.source_id] = s
                if not new or page * 36 >= total:
                    break
        return list(found.values())

    @staticmethod
    def parse_search(html: str) -> tuple[list[Listing], int]:
        tree = LexborHTMLParser(html)
        m = re.search(r"Zobacz (\d+) ofert", html)
        total = int(m.group(1)) if m else 0
        out = []
        for art in tree.css("article[data-detail-id]"):
            a = art.css_first("a[href^='/nieruchomosci/']")
            if not a:
                continue
            title = a.attributes.get("title") or ""
            price = art.css_first(".sneakpeak__price_value")
            fee = art.css_first(".sneakpeak__price_fee")
            area = art.css_first(".sneakpeak__details_item--area")
            rooms = art.css_first(".sneakpeak__details_item--room")
            img = art.css_first("img")
            parts = [p.strip() for p in title.split(",")]
            street = parts[-1] if len(parts) >= 3 else None
            rent = _num(fee.text()) if fee and "czynsz" in fee.text().lower() else None
            out.append(Listing(
                source="domiporta", source_id=art.attributes["data-detail-id"], url=BASE + a.attributes["href"],
                title=title, price=_num(price.text()) if price else None,
                rent=rent, rent_evidence="pole „czynsz” w Domiporcie" if rent is not None else None,
                area=_num(area.text()) if area else None,
                rooms=int(_num(rooms.text()) or 0) or None if rooms else None, street=street,
                district_hint=", ".join(parts[1:-1]) if len(parts) >= 3 else ", ".join(parts[1:]),
                photo=img.attributes.get("src") if img else None))
        return out, total

    def fetch_detail(self, lst: Listing) -> bool:
        status, html = self.fetcher.get(lst.url)
        if status in (404, 410):
            return False
        rel = next(iter(ld_find(ld_json(html), "RealEstateListing")), None)
        if not rel:
            return False
        item = rel.get("itemOffered") or {}
        geo = item.get("geo") or {}
        if geo.get("latitude"):
            lst.lat, lst.lng = float(geo["latitude"]), float(geo["longitude"])
        lst.approx_m = 1500
        name = rel.get("name") or ""
        if ":" in name:
            lst.street = name.rsplit(":", 1)[1].strip() or lst.street
        if (item.get("floorSize") or {}).get("value"):
            lst.area = lst.area or to_float(item["floorSize"]["value"])
        if rel.get("datePosted"):
            lst.date_created = str(rel["datePosted"])[:10]
        if lst.rent is None:
            m = re.search(r"Czynsz administracyjny[^0-9]{0,200}?(\d[\d\s\xa0]*)\s*zł", html, re.S)
            if m:
                lst.rent, lst.rent_evidence = _num(m.group(1)), "pole „czynsz administracyjny” w Domiporcie"
        tree = LexborHTMLParser(html)
        d = tree.css_first(".description__panel")
        lst.description = html_to_text(d.html) if d else ""
        seller = rel.get("seller") or item.get("seller") or {}
        if isinstance(seller, dict) and seller.get("@type") == "RealEstateAgent" and seller.get("name"):
            lst.agency, lst.private_owner = seller["name"], False
        elif isinstance(seller, dict) and seller.get("@type") == "Person":
            lst.private_owner = True
        lst.detail_ok = True
        return True
