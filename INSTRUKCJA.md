# Wyszukiwarka mieszkań na wynajem – instrukcja

## Jak to działa (w skrócie)

1. **Twój Mac** 3 razy dziennie (8:05, 15:05 i 20:05) przegląda Otodom, Morizon i Domiporta.
   Gdy Mac śpi, wyszukiwanie odbędzie się zaraz po jego wybudzeniu.
2. Program odsiewa oferty według `config.yaml`, łączy duplikaty z różnych portali i zapamiętuje,
   co już widziałaś (plik `data/stan.json`).
3. Każda **nowa** oferta = jedno powiadomienie na telefonie (aplikacja **ntfy**).
4. Wyniki trafiają na GitHuba, który pokazuje **stronę z listą** (działa też, gdy Mac jest wyłączony –
   pokazuje wtedy stan z ostatniego wyszukiwania).

Dlaczego Mac, a nie chmura? Portale często blokują serwery w chmurze, a z domowego internetu
działają normalnie. W chmurze GitHuba jest przygotowane wyszukiwanie „zapasowe” (patrz niżej).

## Pliki do klikania (w folderze `wynajem`)

| Plik | Co robi |
|---|---|
| **Szukaj teraz.command** | jedno wyszukiwanie od razu |
| **Wlacz harmonogram.command** | włącza automatyczne wyszukiwanie (8:05, 15:05, 20:05) |
| **Wylacz harmonogram.command** | wyłącza je |

Przy pierwszym dwukliku macOS może zapytać, czy otworzyć plik: kliknij prawym przyciskiem → **Otwórz** → **Otwórz**.

## Jak zmienić kryteria

Otwórz `config.yaml` (np. w TextEdit: prawy przycisk → Otwórz za pomocą → TextEdit) i zmień liczby.
Najczęstsze:

- `metraz_min: 54` – minimalny metraż,
- `koszt_max: 5500` – najem + czynsz,
- `metro_max_m: 500` – Ursynów: odległość do metra,
- `kolej_max_m: 600` – Wawer/Wesoła/Sulejówek/okolice: odległość do stacji,
- `nazwy: [Wawer, Wesoła, Sulejówek, Józefów, Halinów, Zielonka]` – miejscowości przy kolei,
- `odrzuc_slowa` – słowa, po których odrzucamy ogłoszenie (pokoje, najem na doby).

Zapisz plik. Zmiana zadziała przy następnym wyszukiwaniu.
Uwaga: zachowaj wcięcia (spacje na początku linii) – są ważne.

## Oznaczenia

- ⭐ – Kamionek
- ⚠️ czynsz nieznany – ogłoszenie nie podaje czynszu (pokazane, bo sam najem ≤ limitu)
- 📍 lokalizacja przybliżona – portal nie podał dokładnego adresu; odległości są orientacyjne (~)
- 🐕 tak / nie / brak info – czy można ze zwierzętami (z treści ogłoszenia)
- prowizja – ogłoszenie biura (chyba że pisze „bez prowizji”)
- 🏢 instytucjonalny – właścicielem jest firma (np. Heimstaden)
- biuro z Pragi Płd. – Home Point, Metrohouse Wiatraczna, AYCON itd.
- 🚇 / 🚆 – najbliższa stacja metra / kolei (w linii prostej)

Na stronie pod każdą ofertą jest „skąd te informacje” – cytat z ogłoszenia, na podstawie którego
program ustalił czynsz, zwierzęta albo prowizję.

## Jak sprawdzić, czy wszystko działa

1. Na dole strony z listą jest **data ostatniego wyszukiwania** i status każdego źródła (✅ / ❌).
2. Jeśli źródło nie działa 3 razy z rzędu, dostaniesz **jedno** powiadomienie „Źródło X nie działa”.
3. Szczegóły ostatnich przebiegów: plik `cache/przebiegi.log`.

## Gdy przestaną przychodzić powiadomienia

1. Sprawdź datę ostatniego wyszukiwania na dole strony.
   - **Stara data** → Mac nie szukał. Czy był włączony? Kliknij **Szukaj teraz.command**.
     Jeśli to pomoże, kliknij jeszcze raz **Wlacz harmonogram.command**.
   - **Świeża data** → szukanie działa, może po prostu nie ma nowych ofert.
2. W aplikacji ntfy sprawdź, czy subskrybujesz właściwy temat (jest w pliku `sekret_ntfy.txt`).
3. Na iPhonie: Ustawienia → Powiadomienia → ntfy → „Zezwalaj na powiadomienia”.
4. Test: poproś Claude o „wyślij próbne powiadomienie” (polecenie `uv run wynajem test-push`).

## OLX – plan B (alerty mailowe)

OLX blokuje automatyczne pobieranie (także z domowego internetu), więc nie jest czytany bezpośrednio.
Wiele ofert z OLX trafia też na Otodom (ta sama firma). Jeśli chcesz mieć OLX, można
ustawić zapisane wyszukiwanie z powiadomieniem mailowym w OLX, a program będzie czytał te maile.
To wymaga hasła aplikacji do poczty – przeprowadzimy to osobno, krok po kroku.

## Wyszukiwanie w chmurze (zapasowe)

Na GitHubie: zakładka **Actions** → **Szukaj mieszkań** → **Run workflow**. Uruchamia jedno wyszukiwanie
na serwerze GitHuba. Automatyczne wyszukiwanie w chmurze jest wyłączone (szuka Mac). Jak je włączyć,
opisuje plik `.github/workflows/szukaj.yml`.

## Dane mapy

Stacje, granice osiedli i ulice pochodzą z OpenStreetMap (folder `geo/`). Raz na kilka miesięcy można
je odświeżyć poleceniem `uv run --group geo wynajem osm-build`.
