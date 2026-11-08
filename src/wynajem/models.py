from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Listing:
    """Jedno ogłoszenie z jednego portalu."""
    source: str
    source_id: str
    url: str
    title: str = ""
    price: float | None = None          # cena najmu (zł/mies.)
    rent: float | None = None           # czynsz administracyjny (zł/mies.); 0 = „w cenie”
    rent_evidence: str | None = None    # skąd wiemy (pole portalu albo cytat z opisu)
    area: float | None = None
    rooms: int | None = None
    floor: str | None = None
    street: str | None = None
    district_hint: str | None = None    # tekst z portalu, np. „Praga-Południe, Kamionek”
    lat: float | None = None
    lng: float | None = None
    approx_m: int | None = None         # promień przybliżenia lokalizacji (0 = dokładna)
    date_created: str | None = None     # ISO
    agency: str | None = None
    private_owner: bool | None = None
    description: str = ""
    photo: str | None = None
    photos: list[str] = field(default_factory=list)   # do 10 zdjęć (miniatury na stronie)
    pets: str | None = None             # „tak” / „nie” / None = brak info
    pets_evidence: str | None = None
    commission: bool | None = None
    commission_evidence: str | None = None
    detail_ok: bool = False             # czy pobrano stronę ogłoszenia

    @property
    def key(self) -> str:
        return f"{self.source}-{self.source_id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("description")
        return d


@dataclass
class SourceResult:
    name: str
    listings: list[Listing] = field(default_factory=list)
    ok: bool = True
    error: str | None = None
    problems: list[str] = field(default_factory=list)


class SourceBlocked(Exception):
    """Źródło blokuje dostęp (403, captcha) – pomijamy je w tym przebiegu."""
