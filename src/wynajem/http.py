"""Grzeczne pobieranie: przerwa między zapytaniami do portalu, krótki cache na dysku, wykrywanie blokad.

Tylko odczyt (GET). Nie logujemy się i nie omijamy blokad – blokada = wyjątek SourceBlocked.
"""
from __future__ import annotations

import hashlib
import time
from urllib.parse import urlparse

import httpx

from .config import CACHE, load
from .models import SourceBlocked

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
_BLOCK_MARKERS = ("captcha", "Request blocked", "Access Denied", "cf-challenge", "px-captcha")


class Fetcher:
    def __init__(self, cache_minutes: float = 90) -> None:
        self.delay = load()["pobieranie"]["odstep_s"]
        self.cache_s = cache_minutes * 60
        self._last: dict[str, float] = {}
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.5",
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            follow_redirects=True, timeout=40)
        self.requests = 0

    @staticmethod
    def _domain(url: str) -> str:
        return ".".join(urlparse(url).netloc.split(".")[-2:])

    def get(self, url: str, use_cache: bool = True) -> tuple[int, str]:
        """→ (status, html). 404/410 zwracane normalnie (ogłoszenie zniknęło)."""
        path = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".html")
        if use_cache and path.exists() and time.time() - path.stat().st_mtime < self.cache_s:
            return 200, path.read_text(encoding="utf-8")
        host = self._domain(url)
        wait = self._last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.client.get(url)
        except httpx.HTTPError as e:
            raise SourceBlocked(f"{host}: błąd połączenia ({type(e).__name__})") from e
        finally:
            self._last[host] = time.monotonic()
            self.requests += 1
        text = r.text
        if r.status_code in (403, 429) or (r.status_code == 200 and len(text) < 5000
                                           and any(m in text for m in _BLOCK_MARKERS)):
            raise SourceBlocked(f"{host}: HTTP {r.status_code}")
        if r.status_code == 200:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return r.status_code, text
