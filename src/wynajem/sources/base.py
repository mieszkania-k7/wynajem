from __future__ import annotations

import json
import re

from selectolax.lexbor import LexborHTMLParser

from ..config import load
from ..http import Fetcher
from ..models import Listing


class BaseSource:
    name = "base"
    label = "Base"     # nazwa do pokazania na stronie

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self.max_pages = load()["pobieranie"]["max_stron"]
        self.problems: list[str] = []
        k = load()["kryteria"]
        self.area_min, self.cost_max = k["metraz_min"], k["koszt_max"]

    def search(self) -> list[Listing]:
        raise NotImplementedError

    def fetch_detail(self, lst: Listing) -> bool:
        """Uzupełnia ogłoszenie danymi ze strony ogłoszenia. → False, gdy ogłoszenie zniknęło."""
        raise NotImplementedError

    def prefilter(self, lst: Listing) -> bool:
        """Odsiew na podstawie samej listy wyników (żeby nie pobierać zbędnych stron)."""
        if lst.area is not None and lst.area < self.area_min:
            return False
        if lst.price is not None and lst.price + (lst.rent or 0) > self.cost_max:
            return False
        return True


def html_to_text(html: str) -> str:
    if not html:
        return ""
    html = re.sub(r"<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", html, flags=re.I)
    text = LexborHTMLParser(f"<div>{html}</div>").text(separator="")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("brak __NEXT_DATA__ na stronie")
    return json.loads(m.group(1))


def ld_json(html: str) -> list:
    out = []
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            out.append(json.loads(m.group(1)))
        except ValueError:
            continue
    return out


def ld_find(data, type_: str) -> list[dict]:
    found = []
    if isinstance(data, dict):
        t = data.get("@type")
        if t == type_ or (isinstance(t, list) and type_ in t):
            found.append(data)
        for v in data.values():
            found += ld_find(v, type_)
    elif isinstance(data, list):
        for v in data:
            found += ld_find(v, type_)
    return found


def to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(re.sub(r"[^\d,.\-]", "", str(v)).replace(",", "."))
    except ValueError:
        return None
