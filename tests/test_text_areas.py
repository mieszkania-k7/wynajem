from wynajem import areas
from wynajem.models import Listing
from wynajem.text import commission, pets_from_text, rejected_type, rent_from_text


def test_rent_from_text():
    assert rent_from_text("Cena 4600 zł + czynsz 800 zł", 4600)[0] == 800
    assert rent_from_text("opłaty ok. 700 zł miesięcznie", 4000)[0] == 700
    assert rent_from_text("Czynsz najmu: 3 000 zł + Czynsz administracyjny : 860 zł", 3000)[0] == 860
    assert rent_from_text("3800 PLN miesięcznie zawiera czynsz administracyjny (1000 PLN).", 3800)[0] == 0
    assert rent_from_text("Kaucja 5000 zł, czynsz w cenie najmu", 4000)[0] == 0
    assert rent_from_text("Ładne mieszkanie, kaucja 4000 zł", 4000) == (None, None)


def test_pets():
    assert pets_from_text("Zwierzęta mile widziane")[0] == "tak"
    assert pets_from_text("Oferta dla osób bez zwierząt")[0] == "nie"
    assert pets_from_text("Zwierzęta nie są akceptowane.")[0] == "nie"
    assert pets_from_text("Mieszkanie pet-friendly")[0] == "tak"
    assert pets_from_text("Duży balkon, piwnica")[0] is None


def test_commission():
    assert commission("BEZ PROWIZJI", "Biuro X", False)[0] is False
    assert commission("Oferty opatrzone są znacznikiem \"bez prowizji\".", "Biuro X", False)[0] is True
    assert commission("Najemca nie płaci prowizji", "Biuro X", False)[0] is False
    assert commission("", None, True)[0] is False


def test_rejected_type():
    words = ["pokój do wynajęcia", "na doby"]
    assert rejected_type(Listing("x", "1", "u", title="Pokój do wynajęcia Grochów"), words)
    assert rejected_type(Listing("x", "1", "u", title="Mieszkanie", description="Wynajem na doby"), words)
    assert rejected_type(Listing("x", "1", "u", title="3 pokoje Kamionek", description="Najem długoterminowy"), words) is None


def L(lat, lng, approx=0, street=None, hint=None):
    return Listing("t", "1", "u", lat=lat, lng=lng, approx_m=approx, street=street, district_hint=hint)


def test_areas():
    v = areas.evaluate(L(52.2440, 21.0560))          # Kamionek, okolice Grochowskiej/Mińskiej
    assert v.ok and v.zone == "praga_poludnie" and v.star
    v = areas.evaluate(L(52.2556, 21.0390))          # przy Dworcu Wileńskim
    assert not v.ok
    v = areas.evaluate(L(52.2484, 21.0465))          # ul. Targowa, odcinek w Pradze-Południe
    assert not v.ok and "Targowa" in v.reason
    v = areas.evaluate(L(52.1302, 21.0656))          # przy stacji metra Kabaty
    assert v.ok and v.zone == "ursynow"
    v = areas.evaluate(L(52.1450, 21.0300))          # zachodni Ursynów, daleko od metra
    assert not v.ok
    v = areas.evaluate(L(52.2190, 21.0870))          # Gocław
    assert v.ok and not v.star
    v = areas.evaluate(L(52.2300, 20.9800))          # Wola – poza lokalizacjami
    assert not v.ok
    v = areas.evaluate(L(None, None, 1500, None, "Warszawa, Wawer"))   # przybliżona → nie odrzucamy
    assert v.ok and v.approx


def test_placeholder_rent():
    from wynajem.text import enrich
    lst = Listing("x", "1", "u", price=5300, rent=1, rent_evidence="pole")
    enrich(lst)
    assert lst.rent is None
