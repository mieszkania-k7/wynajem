"""Fakty z treści ogłoszenia: czynsz, zwierzęta, prowizja, typ oferty. Każdy z krótkim cytatem-dowodem."""
from __future__ import annotations

import re

from .models import Listing


def _quote(text: str, m: re.Match, before: int = 30, after: int = 40) -> str:
    s, e = max(0, m.start() - before), min(len(text), m.end() + after)
    q = re.sub(r"\s+", " ", text[s:e]).strip()
    return ("…" if s > 0 else "") + q + ("…" if e < len(text) else "")


def _num(s: str) -> float | None:
    s = re.sub(r"[\s\xa0.]", "", s).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# --- czynsz administracyjny ------------------------------------------------------
_RENT_INCLUDED = re.compile(
    r"czynsz\w*\s+(administracyjny\s+)?(jest\s+)?(wliczony|w\s+cenie|zawarty)|"
    r"(cena|kwota)\s+(najmu\s+)?(zawiera|obejmuje|uwzględnia)\s+(już\s+)?(czynsz|opłaty)|"
    r"(w\s+tym|wraz\s+z)\s+czynsz\w*|z\s+czynszem\s+(administracyjnym\s+)?(w\s+cenie|wliczonym)|"
    r"all\s*inclusive|opłaty\s+(administracyjne\s+)?(wliczone|w\s+cenie)", re.I)
_RENT = re.compile(
    r"(\+\s*|plus\s+|oraz\s+)?(czynsz\w*(\s+administracyjn\w*|\s+do\s+(spółdzielni|wspólnoty|administracji)|"
    r"\s+dla\s+(spółdzielni|wspólnoty|administracji))?|opłat\w*(\s+administracyjn\w*|\s+eksploatacyjn\w*|"
    r"\s+do\s+(spółdzielni|wspólnoty|administracji))?|administracj\w*)"
    r"[\s:=\-–(]*(wynosi\s+|około\s+|ok\.?\s*|ok\s+|w\s+wysokości\s+|to\s+|ca\.?\s*|~\s*)?"
    r"(\d{1,2}[\s\xa0.]?\d{3}|\d{3,4})(,\d{1,2})?\s*(zł|pln|złotych|,-)?", re.I)


def rent_from_text(text: str, price: float | None) -> tuple[float | None, str | None]:
    """Czynsz administracyjny z opisu. → (kwota, cytat) albo (None, None). 0 = czynsz w cenie."""
    if not text:
        return None, None
    for m in _RENT.finditer(text):
        word = m.group(2).lower()
        # „czynsz najmu 4500 zł” to cena najmu, nie czynsz administracyjny
        after_word = text[m.end(2):m.end(2) + 12].lower()
        if "najm" in after_word or "najm" in word:
            continue
        v = _num(re.search(r"(\d{1,2}[\s\xa0.]?\d{3}|\d{3,4})", m.group(0)).group(1))
        if v is None or not 100 <= v <= 3000:
            continue
        if price and abs(v - price) < 1:
            continue
        ctx_before = text[max(0, m.start() - 25):m.start()].lower()
        if "kaucj" in ctx_before or "depozyt" in ctx_before:
            continue
        if re.search(r"(zawiera|w\s+tym|wliczon\w*|obejmuje|uwzględnia|łącznie\s+z)\s*\(?\s*$",
                     text[max(0, m.start() - 30):m.start()], re.I):
            return 0.0, _quote(text, m)      # „cena zawiera czynsz (1000 zł)” – czynsz już w cenie
        return v, _quote(text, m)
    m = _RENT_INCLUDED.search(text)
    if m:
        return 0.0, _quote(text, m)
    return None, None


# --- zwierzęta --------------------------------------------------------------------
_PETS_NO = re.compile(
    r"(bez\s+zwierz|nie\s+(akceptuj\w*|przyjmuj\w*|wynajm\w*\s+osobom\s+ze?)\s+(\w+\s+)?zwierz|"
    r"zwierz\w*\s+(\w+\s+)?(nie\s+(są\s+)?(akceptowan|dozwolon|mile|wchodz|przyjmowan)|niedozwolon|wykluczon)|"
    r"(brak\s+zgody|zakaz)\s+(na\s+)?(posiadani\w+\s+)?zwierz|nie\s+dla\s+(osób\s+)?(ze?\s+)?zwierz|"
    r"no\s+pets|pets\s+not\s+allowed|bez\s+psów|bez\s+kotów|bez\s+pupili)", re.I)
_PETS_YES = re.compile(
    r"(zwierz\w*\s+(\w+\s+)?(mile\s+widzian|akceptowan|dozwolon|są\s+ok|ok\b|przyjmowan|nie\s+stanowi\w*\s+problem)|"
    r"(akceptuj\w*|przyjmuj\w*|dopuszcza\w*)\s+(\w+\s+)?zwierz|pet[\s-]?friendly|pets?\s+(are\s+)?(welcome|allowed)|"
    r"przyjazn\w*\s+zwierz|(można|możliwość\s+zamieszkania)\s+(\w+\s+)?ze?\s+zwierz|zgoda\s+na\s+zwierz|"
    r"(pies|psa|kot|kota)\s+(\w+\s+)?(mile\s+widzian|akceptowan|dozwolon|ok\b))", re.I)


def pets_from_text(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    m = _PETS_NO.search(text)
    if m:
        return "nie", _quote(text, m)
    m = _PETS_YES.search(text)
    if m:
        return "tak", _quote(text, m)
    return None, None


# --- prowizja -----------------------------------------------------------------------
_NO_COMMISSION = re.compile(r"(bez\s+(żadnej\s+)?prowizji|0\s*%\s*prowizji|prowizj\w*\s*(:|-|–)?\s*0\s*(%|zł)?(?!\d)|"
                            r"nie\s+pobiera\w*\s+prowizji|nie\s+płaci\w*\s+(żadnej\s+)?prowizji|"
                            r"prowizj\w*\s+(płaci|pokrywa)\s+właściciel|brak\s+prowizji|prowizj\w*\s+(nie\s+ma|brak)|"
                            r"bezpośrednio\s+od\s+właściciela|bez\s+pośrednik)", re.I)
_COMMISSION = re.compile(r"prowizj\w*", re.I)


def commission(text: str, agency: str | None, private_owner: bool | None) -> tuple[bool | None, str | None]:
    for m in _NO_COMMISSION.finditer(text or ""):
        # formułka biura „oferty opatrzone znacznikiem «bez prowizji»…” nie dotyczy tej oferty
        if re.search(r"znacznik|oznaczon", text[max(0, m.start() - 40):m.start()], re.I):
            continue
        return False, _quote(text, m)
    m = _COMMISSION.search(text or "")
    if m:
        return True, _quote(text, m)
    if agency or private_owner is False:
        return True, f"ogłoszenie biura{': ' + agency if agency else ''}"
    if private_owner:
        return False, "ogłoszenie prywatne"
    return None, None


# --- typ oferty -----------------------------------------------------------------------
def rejected_type(lst: Listing, words: list[str]) -> str | None:
    """Pokój / najem krótkoterminowy / lokal użytkowy → powód, w przeciwnym razie None."""
    t = (lst.title or "").lower()
    d = (lst.description or "").lower()
    for w in words:
        if w.lower() in t:
            return f"tytuł: „{w}”"
    for pat in (r"wynajm\w*\s+(na\s+)?(pok[oó]j|pokoje)\b(?!\w)", r"najem\s+krótkoterminow", r"na\s+doby\b",
                r"\bza\s+dob[ęe]\b", r"cena\s+za\s+noc", r"tylko\s+na\s+(kilka\s+)?(dni|tygodni)\b"):
        m = re.search(pat, d)
        if m and not re.search(r"(nie|bez)\s+(\w+\s+)?$", d[max(0, m.start() - 15):m.start()]):
            return f"opis: „{_quote(lst.description, m, 15, 15)}”"
    return None


def enrich(lst: Listing) -> None:
    """Uzupełnia czynsz (gdy portal nie podał), zwierzęta i prowizję na podstawie opisu."""
    text = (lst.title or "") + "\n" + (lst.description or "")
    if lst.rent is not None and 0 < lst.rent < 50:      # „1 zł” wpisane przez biuro jako zaślepka
        lst.rent, lst.rent_evidence = None, None
    if lst.rent is None:
        lst.rent, lst.rent_evidence = rent_from_text(text, lst.price)
    lst.pets, lst.pets_evidence = pets_from_text(text)
    lst.commission, lst.commission_evidence = commission(text, lst.agency, lst.private_owner)
