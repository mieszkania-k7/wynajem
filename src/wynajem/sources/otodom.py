"""Otodom (wynajem): dane z <script id="__NEXT_DATA__"> – lista: searchAds, ogłoszenie: ad.

Na liście jest już cena najmu (totalPrice) i czynsz (rentPrice); ze strony ogłoszenia bierzemy
współrzędne, opis (zwierzęta, prowizja) i zdjęcie.
"""
from __future__ import annotations

from ..models import Listing
from .base import BaseSource, html_to_text, next_data, to_float

BASE = "https://www.otodom.pl"
PATHS = [
    "warszawa/warszawa/warszawa/praga--poludnie",
    "warszawa/warszawa/warszawa/praga--polnoc",
    "warszawa/warszawa/warszawa/targowek",
    "warszawa/warszawa/warszawa/mokotow/siekierki",
    "warszawa/warszawa/warszawa/ursynow",
    "warszawa/warszawa/warszawa/wawer",
    "warszawa/warszawa/warszawa/wesola",
    "minski/sulejowek/sulejowek",
    "otwocki/jozefow/jozefow",
    "minski/halinow",
    "wolominski/zielonka/zielonka",
]
FLOORS = {"CELLAR": "suterena", "GROUND": "parter", "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4",
          "FIFTH": "5", "SIXTH": "6", "SEVENTH": "7", "EIGHTH": "8", "NINTH": "9", "TENTH": "10",
          "ABOVE_TENTH": "10+", "GARRET": "poddasze"}
ROOMS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9,
         "TEN": 10, "MORE": 10}


class Otodom(BaseSource):
    name = "otodom"
    label = "Otodom"

    def search_url(self, path: str, page: int) -> str:
        return (f"{BASE}/pl/wyniki/wynajem/mieszkanie/mazowieckie/{path}"
                f"?priceMax={self.cost_max}&areaMin={self.area_min}&by=LATEST&direction=DESC&limit=72&page={page}")

    def search(self) -> list[Listing]:
        found: dict[str, Listing] = {}
        for path in PATHS:
            for page in range(1, self.max_pages + 1):
                status, html = self.fetcher.get(self.search_url(path, page))
                if status != 200:
                    self.problems.append(f"{path} str. {page}: HTTP {status}")
                    break
                items, pages = self.parse_search(html)
                for it in items:
                    found.setdefault(it.source_id, it)   # promowane powtarzają się – dedup po id
                if page >= pages:
                    break
        return list(found.values())

    @staticmethod
    def parse_search(html: str) -> tuple[list[Listing], int]:
        sa = next_data(html)["props"]["pageProps"]["data"]["searchAds"]
        out = []
        for it in sa.get("items") or []:
            slug = it.get("slug") or ""
            if "-ID" not in slug or it.get("estate") != "FLAT" or it.get("transaction") != "RENT":
                continue
            loc = it.get("location") or {}
            street = ((loc.get("address") or {}).get("street") or {}).get("name")
            names = [l.get("name") for l in ((loc.get("reverseGeocoding") or {}).get("locations") or [])]
            imgs = it.get("images") or []
            rent = to_float((it.get("rentPrice") or {}).get("value"))
            out.append(Listing(
                source="otodom", source_id="ID" + slug.rsplit("-ID", 1)[1], url=f"{BASE}/pl/oferta/{slug}",
                title=it.get("title") or "",
                price=to_float((it.get("totalPrice") or {}).get("value")),
                rent=rent, rent_evidence="pole „czynsz” w Otodom" if rent is not None else None,
                area=to_float(it.get("areaInSquareMeters")), rooms=ROOMS.get(it.get("roomsNumber")),
                floor=FLOORS.get(it.get("floorNumber")), street=street,
                district_hint=", ".join(n for n in names[1:] if n),
                approx_m=(loc.get("mapDetails") or {}).get("radius"),
                date_created=it.get("createdAtFirst") or it.get("dateCreated"),
                private_owner=it.get("isPrivateOwner"), agency=(it.get("agency") or {}).get("name"),
                photo=(imgs[0].get("medium") or imgs[0].get("large")) if imgs else None))
        pag = sa.get("pagination") or {}
        return out, int(pag.get("totalPages") or 1)

    def fetch_detail(self, lst: Listing) -> bool:
        status, html = self.fetcher.get(lst.url)
        if status in (404, 410):
            return False
        ad = next_data(html)["props"]["pageProps"].get("ad")
        if not ad or ad.get("status") != "active" or ad.get("shouldShowExpiredAdPage"):
            return False
        chars = {c["key"]: c.get("value") for c in ad.get("characteristics") or []}
        loc = ad.get("location") or {}
        coords = loc.get("coordinates") or {}
        lst.lat, lst.lng = coords.get("latitude"), coords.get("longitude")
        radius = (loc.get("mapDetails") or {}).get("radius")
        lst.approx_m = int(radius) if radius is not None else lst.approx_m
        street = ((loc.get("address") or {}).get("street") or {}).get("name")
        lst.street = street or lst.street
        lst.price = to_float(chars.get("price")) or lst.price
        if chars.get("rent"):
            lst.rent, lst.rent_evidence = to_float(chars["rent"]), "pole „czynsz” w Otodom"
        lst.area = to_float(chars.get("m")) or lst.area
        if chars.get("rooms_num"):
            lst.rooms = int(to_float(chars["rooms_num"]) or 0) or lst.rooms
        lst.description = html_to_text(ad.get("description") or "")
        imgs = [i.get("medium") or i.get("large") for i in ad.get("images") or [] if isinstance(i, dict)]
        lst.photo = lst.photo or (imgs[0] if imgs else None)
        lst.date_created = lst.date_created or ad.get("createdAt")
        lst.detail_ok = True
        return True
