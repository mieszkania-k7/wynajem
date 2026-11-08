"""Morizon (wynajem): dane z <script id="__NUXT_DATA__">. Czynszu Morizon nie podaje w polu – szukamy w opisie."""
from __future__ import annotations

import base64
import re
from datetime import datetime

from ..models import Listing
from .base import BaseSource, html_to_text, to_float
from .nuxt import nuxt_data

BASE = "https://www.morizon.pl"
PATHS = ["warszawa/praga-poludnie", "warszawa/praga-polnoc", "warszawa/targowek", "warszawa/mokotow",
         "warszawa/ursynow", "warszawa/wawer", "warszawa/wesola", "sulejowek", "jozefow", "halinow", "zielonka"]
GONE_MARKER = "To ogłoszenie nie jest już dostępne"


def _photo(p: dict) -> str | None:
    try:
        return base64.b64decode(p["id"] + "==").decode()
    except Exception:
        return None


def _date(s: str | None) -> str | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


class Morizon(BaseSource):
    name = "morizon"
    label = "Morizon"
    base = BASE

    def search_url(self, path: str, page: int) -> str:
        return (f"{self.base}/do-wynajecia/mieszkania/najnowsze/{path}/?ps[living_area_from]={self.area_min}"
                f"&ps[price_to]={self.cost_max}" + (f"&page={page}" if page > 1 else ""))

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
                for it in items:
                    found.setdefault(it.source_id, it)
                if not items or page * 35 >= total:
                    break
        return list(found.values())

    def parse_search(self, html: str) -> tuple[list[Listing], int]:
        data = nuxt_data(html)["data"]
        block = next(v for k, v in data.items() if k.startswith("property-listing-data"))
        props = block["data"]["searchResult"]["properties"]
        out = []
        for n in props.get("nodes") or []:
            loc = n.get("location") or {}
            photos = n.get("photos") or []
            rooms = re.match(r"(\d+)", n.get("numberOfRooms") or "")
            company = ((n.get("contact") or {}).get("company") or {})
            out.append(Listing(
                source=self.name, source_id=n["idOnFrontend"], url=self.base + n["url"],
                title=n.get("advertisementText") or n.get("title") or "",
                price=to_float((n.get("price") or {}).get("amount")), area=to_float(n.get("area")),
                rooms=int(rooms.group(1)) if rooms else None,
                floor=(n.get("floorFormatted") or "").replace("piętro ", "") or None, street=loc.get("street"),
                district_hint=", ".join((loc.get("location") or [])[1:]), date_created=_date(n.get("addedAt")),
                agency=company.get("name"), private_owner=False if company.get("type") == "AGENCY" else None,
                description=n.get("description") or "",
                photo=_photo(photos[0]) if photos and isinstance(photos[0], dict) else None,
                photos=[u for u in (_photo(p) for p in photos if isinstance(p, dict)) if u][:10]))
        return out, int(props.get("totalCount") or 0)

    def fetch_detail(self, lst: Listing) -> bool:
        status, html = self.fetcher.get(lst.url)
        if status in (404, 410) or GONE_MARKER in html:
            return False
        data = nuxt_data(html)["data"]
        block = next((v for k, v in data.items() if k.startswith("property-details")), None)
        pd = ((block or {}).get("data") or {}).get("propertyData")
        if not pd:
            return GONE_MARKER not in html
        loc = pd.get("location") or {}
        mp = loc.get("map") or {}
        center = mp.get("center") or {}
        lst.lat, lst.lng = center.get("latitude"), center.get("longitude")
        # bez numeru domu pinezka zwykle stoi w środku dzielnicy/ulicy – ulica rozstrzygnie (areas.position)
        lst.approx_m = 0 if (loc.get("number") and (mp.get("zoom") or 0) >= 15) else 1500
        lst.street = loc.get("street") or lst.street
        lst.price = to_float((pd.get("price") or {}).get("amount")) or lst.price
        lst.area = to_float(pd.get("area")) or lst.area
        if pd.get("numberOfRoomsCount"):
            lst.rooms = int(pd["numberOfRoomsCount"])
        params = {}
        for key in ("detailedInformation", "buildingDetailedInformation", "offerDetailedInformation"):
            for item in pd.get(key) or []:
                if item.get("label"):
                    params[item["label"]] = item.get("value")
        for label in ("Czynsz", "Czynsz administracyjny", "Opłaty"):
            if params.get(label):
                lst.rent, lst.rent_evidence = to_float(params[label]), f"pole „{label}” w Morizon"
        lst.date_created = _date(params.get("Data dodania")) or lst.date_created
        lst.description = html_to_text(pd.get("description") or "")
        ph = [u for u in (_photo(p) for p in pd.get("photos") or [] if isinstance(p, dict)) if u]
        lst.photo = lst.photo or (ph[0] if ph else None)
        if len(ph) > len(lst.photos):
            lst.photos = ph[:10]
        lst.detail_ok = True
        return pd.get("presentationType", "ACTIVE") == "ACTIVE"
