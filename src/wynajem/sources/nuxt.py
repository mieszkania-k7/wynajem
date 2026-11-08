"""Dekoder ładunku Nuxt (__NUXT_DATA__ – format devalue: płaska tablica z odwołaniami po indeksach)."""
from __future__ import annotations

import json
import re

_WRAPPERS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}


def unflatten(arr: list):
    cache: dict[int, object] = {}

    def h(i):
        if isinstance(i, int) and i < 0:   # -1 = undefined itp.
            return None
        if i in cache:
            return cache[i]
        v = arr[i]
        if isinstance(v, list):
            tag = v[0] if v and isinstance(v[0], str) else None
            if tag in _WRAPPERS:
                r = h(v[1]) if len(v) > 1 else None
                cache[i] = r
                return r
            if tag == "Date":
                return v[1]
            if tag == "Set":
                return [h(x) for x in v[1:]]
            if tag == "Map":
                return {str(h(v[k])): h(v[k + 1]) for k in range(1, len(v), 2)}
            out: list = []
            cache[i] = out
            out.extend(h(x) for x in v)
            return out
        if isinstance(v, dict):
            out_d: dict = {}
            cache[i] = out_d
            for k, x in v.items():
                out_d[k] = h(x)
            return out_d
        return v

    return h(0)


def nuxt_data(html: str) -> dict:
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("brak __NUXT_DATA__ na stronie")
    return unflatten(json.loads(m.group(1)))
