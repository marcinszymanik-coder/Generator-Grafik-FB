import os
import json
import math
import socket
import ipaddress
import colorsys
import datetime
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests
import gspread
import streamlit as st

from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo
from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)

try:
    from pilmoji import Pilmoji
    PILMOJI_DOSTEPNE = True
except ImportError:
    PILMOJI_DOSTEPNE = False


# ============================================================
# KONFIGURACJA
# ============================================================

STOPKA_DOMYSLNA = "ARTYKUŁ W KOMENTARZU"

WERSJA_APP = (
    "5.6 – możliwość świadomego przełamywania linii w coverze"
)

SZEROKOSC_POSTA = 1080
WYSOKOSC_POSTA = 1080

SZEROKOSC_COVERA = 1640
WYSOKOSC_COVERA = 720

MAKS_ROZMIAR_HTML = 5 * 1024 * 1024
MAKS_ROZMIAR_OBRAZU = 25 * 1024 * 1024
MAKS_LICZBA_PIKSELI = 45_000_000

Image.MAX_IMAGE_PIXELS = MAKS_LICZBA_PIKSELI

NAGLOWKI_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
}

KATALOG_FONTOW = os.path.join(
    "assets",
    "fonts",
)

SCIEZKA_FONT_BOLD = os.path.join(
    KATALOG_FONTOW,
    "Montserrat-Bold.ttf",
)

SCIEZKA_FONT_SEMIBOLD = os.path.join(
    KATALOG_FONTOW,
    "Montserrat-SemiBold.ttf",
)

FONTY_DO_POBRANIA = {
    SCIEZKA_FONT_BOLD: (
        "https://raw.githubusercontent.com/JulietaUla/"
        "Montserrat/master/fonts/ttf/Montserrat-Bold.ttf"
    ),
    SCIEZKA_FONT_SEMIBOLD: (
        "https://raw.githubusercontent.com/JulietaUla/"
        "Montserrat/master/fonts/ttf/Montserrat-SemiBold.ttf"
    ),
}


# ============================================================
# PODSTAWOWE NARZĘDZIA
# ============================================================

def ogranicz(wartosc, minimum, maksimum):
    return max(
        minimum,
        min(maksimum, wartosc),
    )


def hex_na_rgb(kolor_hex):
    kolor_hex = kolor_hex.strip().lstrip("#")

    if len(kolor_hex) != 6:
        raise ValueError(
            "Kolor musi mieć format #RRGGBB."
        )

    return tuple(
        int(kolor_hex[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def rgb_na_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        *rgb
    )


def mieszaj_kolory(kolor_a, kolor_b, udzial_b):
    udzial_b = ogranicz(
        udzial_b,
        0.0,
        1.0,
    )

    udzial_a = 1.0 - udzial_b

    return tuple(
        int(
            kolor_a[i] * udzial_a
            + kolor_b[i] * udzial_b
        )
        for i in range(3)
    )


def pobierz_czcionke(sciezka, rozmiar):
    return ImageFont.truetype(
        sciezka,
        rozmiar,
    )


def szerokosc_tekstu(font, tekst):
    if hasattr(font, "getlength"):
        return font.getlength(tekst)

    bbox = font.getbbox(tekst)
    return bbox[2] - bbox[0]


def obraz_do_jpeg_bytes(obraz, jakosc=95):
    bufor = BytesIO()

    obraz.convert("RGB").save(
        bufor,
        format="JPEG",
        quality=jakosc,
        optimize=True,
        subsampling=0,
    )

    bufor.seek(0)
    return bufor.getvalue()


def wczytaj_obraz(zrodlo):
    if zrodlo is None:
        return None

    if isinstance(zrodlo, Image.Image):
        obraz = zrodlo.copy()

    elif isinstance(zrodlo, (bytes, bytearray)):
        obraz = Image.open(
            BytesIO(zrodlo)
        )

    elif hasattr(zrodlo, "read"):
        dane = zrodlo.read()

        try:
            zrodlo.seek(0)
        except Exception:
            pass

        obraz = Image.open(
            BytesIO(dane)
        )

    elif isinstance(zrodlo, str):
        obraz = Image.open(zrodlo)

    else:
        raise TypeError(
            "Nieobsługiwany typ źródła obrazu."
        )

    obraz.load()
    obraz = ImageOps.exif_transpose(obraz)

    liczba_pikseli = (
        obraz.width * obraz.height
    )

    if liczba_pikseli > MAKS_LICZBA_PIKSELI:
        raise ValueError(
            "Obraz ma zbyt dużą rozdzielczość. "
            f"Maksymalnie {MAKS_LICZBA_PIKSELI:,} pikseli."
        )

    return obraz.convert("RGBA")


def kadruj_cover(obraz, szerokosc, wysokosc):
    obraz = obraz.convert("RGBA")

    proporcja_docelowa = (
        szerokosc / wysokosc
    )

    proporcja_obrazu = (
        obraz.width / obraz.height
    )

    if proporcja_obrazu > proporcja_docelowa:
        nowa_szerokosc = int(
            obraz.height * proporcja_docelowa
        )

        lewy = (
            obraz.width - nowa_szerokosc
        ) // 2

        obraz = obraz.crop(
            (
                lewy,
                0,
                lewy + nowa_szerokosc,
                obraz.height,
            )
        )

    else:
        nowa_wysokosc = int(
            obraz.width / proporcja_docelowa
        )

        gora = (
            obraz.height - nowa_wysokosc
        ) // 2

        obraz = obraz.crop(
            (
                0,
                gora,
                obraz.width,
                gora + nowa_wysokosc,
            )
        )

    return obraz.resize(
        (szerokosc, wysokosc),
        Image.Resampling.LANCZOS,
    )


# ============================================================
# FONTY
# ============================================================

@st.cache_resource(show_spinner=False)
def przygotuj_czcionki():
    os.makedirs(
        KATALOG_FONTOW,
        exist_ok=True,
    )

    bledy = []

    for sciezka, url in FONTY_DO_POBRANIA.items():
        if (
            os.path.exists(sciezka)
            and os.path.getsize(sciezka) > 10_000
        ):
            continue

        try:
            odpowiedz = requests.get(
                url,
                timeout=(5, 30),
            )

            odpowiedz.raise_for_status()

            if len(odpowiedz.content) < 10_000:
                raise ValueError(
                    "Pobrany plik fontu jest zbyt mały."
                )

            with open(sciezka, "wb") as plik:
                plik.write(
                    odpowiedz.content
                )

        except Exception as blad:
            bledy.append(
                f"{os.path.basename(sciezka)}: {blad}"
            )

    brakujace = [
        sciezka
        for sciezka in FONTY_DO_POBRANIA
        if (
            not os.path.exists(sciezka)
            or os.path.getsize(sciezka) < 10_000
        )
    ]

    if brakujace:
        szczegoly = "; ".join(bledy)

        raise RuntimeError(
            "Nie udało się przygotować fontów Montserrat. "
            f"Szczegóły: {szczegoly}"
        )

    return True


# ============================================================
# BEZPIECZNE POBIERANIE STRON
# ============================================================

def sprawdz_publiczny_url(url):
    try:
        parsed = urlparse(url)
    except Exception as blad:
        raise ValueError(
            f"Nieprawidłowy adres URL: {blad}"
        )

    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            "Dozwolone są wyłącznie adresy HTTP i HTTPS."
        )

    if not parsed.hostname:
        raise ValueError(
            "Adres URL nie zawiera prawidłowej domeny."
        )

    if parsed.username or parsed.password:
        raise ValueError(
            "Adres URL nie może zawierać loginu ani hasła."
        )

    try:
        port = parsed.port
    except ValueError:
        raise ValueError(
            "Adres URL zawiera nieprawidłowy port."
        )

    if port not in (None, 80, 443):
        raise ValueError(
            "Dozwolone są wyłącznie porty 80 i 443."
        )

    try:
        rekordy = socket.getaddrinfo(
            parsed.hostname,
            port or (
                443
                if parsed.scheme == "https"
                else 80
            ),
            type=socket.SOCK_STREAM,
        )

    except socket.gaierror:
        raise ValueError(
            "Nie udało się odnaleźć domeny."
        )

    if not rekordy:
        raise ValueError(
            "Domena nie zwróciła żadnego adresu IP."
        )

    for rekord in rekordy:
        adres_ip = rekord[4][0].split("%")[0]
        ip = ipaddress.ip_address(adres_ip)

        if not ip.is_global:
            raise ValueError(
                "Adres prowadzi do sieci lokalnej "
                "lub zastrzeżonej."
            )

    return True


def bezpieczne_pobranie(
    url,
    maks_rozmiar,
    oczekiwany_typ=None,
    maks_przekierowan=5,
):
    aktualny_url = url

    for _ in range(maks_przekierowan + 1):
        sprawdz_publiczny_url(
            aktualny_url
        )

        odpowiedz = requests.get(
            aktualny_url,
            headers=NAGLOWKI_HTTP,
            timeout=(7, 25),
            stream=True,
            allow_redirects=False,
        )

        if odpowiedz.status_code in (
            301,
            302,
            303,
            307,
            308,
        ):
            lokalizacja = odpowiedz.headers.get(
                "Location"
            )

            if not lokalizacja:
                raise ValueError(
                    "Serwer zwrócił przekierowanie "
                    "bez adresu docelowego."
                )

            aktualny_url = urljoin(
                aktualny_url,
                lokalizacja,
            )

            continue

        odpowiedz.raise_for_status()

        content_type = (
            odpowiedz.headers
            .get("Content-Type", "")
            .split(";")[0]
            .strip()
            .lower()
        )

        if oczekiwany_typ == "html":
            dozwolone = {
                "text/html",
                "application/xhtml+xml",
                "application/xml",
                "text/xml",
                "",
            }

            if content_type not in dozwolone:
                raise ValueError(
                    "Adres nie zwrócił strony HTML. "
                    f"Typ: {content_type}"
                )

        if oczekiwany_typ == "image":
            if (
                content_type
                and not content_type.startswith("image/")
            ):
                raise ValueError(
                    "Adres nie zwrócił obrazu. "
                    f"Typ: {content_type}"
                )

        dlugosc = odpowiedz.headers.get(
            "Content-Length"
        )

        if dlugosc:
            try:
                rozmiar = int(dlugosc)

                if rozmiar > maks_rozmiar:
                    raise ValueError(
                        "Pobierany plik jest zbyt duży."
                    )

            except TypeError:
                pass

        fragmenty = []
        pobrano = 0

        for fragment in odpowiedz.iter_content(
            chunk_size=64 * 1024
        ):
            if not fragment:
                continue

            pobrano += len(fragment)

            if pobrano > maks_rozmiar:
                raise ValueError(
                    "Pobierany plik przekroczył limit rozmiaru."
                )

            fragmenty.append(fragment)

        return (
            b"".join(fragmenty),
            aktualny_url,
            content_type,
        )

    raise ValueError(
        "Adres zawiera zbyt wiele przekierowań."
    )


# ============================================================
# POBIERANIE ARTYKUŁU
# ============================================================

def wyczysc_tytul_portalu(tytul_surowy):
    if not tytul_surowy:
        return "BRAK TYTUŁU"

    smieci = [
        "- budujemydom.pl",
        "- budujemydom",
        "| budujemydom.pl",
        "- Budujemy Dom",
        "- BudujemyDom",
        "- czasnawnetrze.pl",
        "- czasnawnetrze",
        "| czasnawnetrze.pl",
        "- Czas na Wnętrze",
        "- audio.com.pl",
        "- audio",
        "| audio.com.pl",
        "- Testy, ceny",
        "- Test",
    ]

    tytul_czysty = tytul_surowy.strip()

    for smiec in smieci:
        if tytul_czysty.lower().endswith(
            smiec.lower()
        ):
            tytul_czysty = tytul_czysty[
                :-len(smiec)
            ].strip()

    return tytul_czysty.strip(
        "- – |"
    ).strip()


def znajdz_adres_zdjecia(soup, url_artykulu):
    kandydaci = []
    preferowane = []

    og_image = soup.find(
        "meta",
        property="og:image",
    )

    if og_image and og_image.get("content"):
        kandydaci.append(
            og_image.get("content")
        )

    twitter_image = soup.find(
        "meta",
        attrs={"name": "twitter:image"},
    )

    if (
        twitter_image
        and twitter_image.get("content")
    ):
        kandydaci.append(
            twitter_image.get("content")
        )

    for tag in soup.find_all(
        ["source", "img"]
    ):
        srcset = tag.get("srcset")

        if srcset:
            for czesc in srcset.split(","):
                elementy = czesc.strip().split()

                if elementy:
                    adres = elementy[0]

                    if (
                        "/i/" in adres
                        and "1050x0" in adres
                    ):
                        preferowane.append(adres)
                    else:
                        kandydaci.append(adres)

        for atrybut in (
            "src",
            "data-src",
            "data-lazy-src",
        ):
            adres = tag.get(atrybut)

            if not adres:
                continue

            if (
                "/i/" in adres
                and "1050x0" in adres
            ):
                preferowane.append(adres)
            else:
                kandydaci.append(adres)

    for adres in preferowane + kandydaci:
        if not adres:
            continue

        pelny_adres = urljoin(
            url_artykulu,
            adres.strip(),
        )

        if pelny_adres.startswith(
            ("http://", "https://")
        ):
            return pelny_adres

    return None


def pobierz_dane_z_artykulu(url):
    html_bytes, finalny_url, _ = bezpieczne_pobranie(
        url=url,
        maks_rozmiar=MAKS_ROZMIAR_HTML,
        oczekiwany_typ="html",
    )

    html = html_bytes.decode(
        "utf-8",
        errors="replace",
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    tytul = "BRAK TYTUŁU"

    og_title = soup.find(
        "meta",
        property="og:title",
    )

    if og_title and og_title.get("content"):
        tytul = wyczysc_tytul_portalu(
            og_title.get("content")
        )

    elif soup.title:
        tytul = wyczysc_tytul_portalu(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

    adres_zdjecia = znajdz_adres_zdjecia(
        soup,
        finalny_url,
    )

    if not adres_zdjecia:
        raise ValueError(
            "Nie udało się odnaleźć głównego "
            "zdjęcia artykułu."
        )

    obraz_bytes, _, _ = bezpieczne_pobranie(
        url=adres_zdjecia,
        maks_rozmiar=MAKS_ROZMIAR_OBRAZU,
        oczekiwany_typ="image",
    )

    obraz = wczytaj_obraz(
        obraz_bytes
    )

    if obraz.width < 300 or obraz.height < 200:
        raise ValueError(
            "Pobrane zdjęcie jest zbyt małe."
        )

    return tytul, obraz_bytes


# ============================================================
# ZAWIJANIE TEKSTU
# ============================================================

def podziel_dlugie_slowo(
    slowo,
    font,
    maks_szerokosc,
):
    fragmenty = []
    aktualny = ""

    for znak in slowo:
        test = aktualny + znak

        if (
            szerokosc_tekstu(font, test)
            <= maks_szerokosc
            or not aktualny
        ):
            aktualny = test

        else:
            fragmenty.append(
                aktualny
            )

            aktualny = znak

    if aktualny:
        fragmenty.append(
            aktualny
        )

    return fragmenty


def zawin_tekst(
    tekst,
    font,
    maks_szerokosc,
):
    linie_ostateczne = []

    for akapit in tekst.splitlines() or [""]:
        slowa = akapit.split()

        if not slowa:
            linie_ostateczne.append("")
            continue

        aktualna_linia = []

        for slowo in slowa:
            if (
                szerokosc_tekstu(font, slowo)
                > maks_szerokosc
            ):
                if aktualna_linia:
                    linie_ostateczne.append(
                        " ".join(aktualna_linia)
                    )

                    aktualna_linia = []

                fragmenty = podziel_dlugie_slowo(
                    slowo,
                    font,
                    maks_szerokosc,
                )

                linie_ostateczne.extend(
                    fragmenty[:-1]
                )

                if fragmenty:
                    aktualna_linia = [
                        fragmenty[-1]
                    ]

                continue

            test = " ".join(
                aktualna_linia + [slowo]
            )

            if (
                szerokosc_tekstu(font, test)
                <= maks_szerokosc
            ):
                aktualna_linia.append(
                    slowo
                )

            else:
                if aktualna_linia:
                    linie_ostateczne.append(
                        " ".join(aktualna_linia)
                    )

                aktualna_linia = [slowo]

        if aktualna_linia:
            linie_ostateczne.append(
                " ".join(aktualna_linia)
            )

    return linie_ostateczne


def dopasuj_tekst(
    tekst,
    sciezka_fontu,
    maks_rozmiar,
    min_rozmiar,
    maks_szerokosc,
    maks_wysokosc,
    odstep_linii=10,
    maks_linii=None,
):
    for rozmiar in range(
        maks_rozmiar,
        min_rozmiar - 1,
        -1,
    ):
        font = pobierz_czcionke(
            sciezka_fontu,
            rozmiar,
        )

        linie = zawin_tekst(
            tekst,
            font,
            maks_szerokosc,
        )

        wysokosc_linii = (
            rozmiar + odstep_linii
        )

        wysokosc_bloku = (
            len(linie) * wysokosc_linii
        )

        if (
            maks_linii
            and len(linie) > maks_linii
        ):
            continue

        if wysokosc_bloku <= maks_wysokosc:
            return (
                font,
                linie,
                wysokosc_linii,
            )

    font = pobierz_czcionke(
        sciezka_fontu,
        min_rozmiar,
    )

    linie = zawin_tekst(
        tekst,
        font,
        maks_szerokosc,
    )

    if maks_linii:
        linie = linie[:maks_linii]

        if len(linie) == maks_linii:
            ostatnia = linie[-1]

            while (
                ostatnia
                and szerokosc_tekstu(
                    font,
                    ostatnia + "…",
                ) > maks_szerokosc
            ):
                ostatnia = ostatnia[:-1]

            linie[-1] = (
                ostatnia.rstrip() + "…"
            )

    return (
        font,
        linie,
        min_rozmiar + odstep_linii,
    )


def rysuj_tekst(
    obraz,
    pozycja,
    tekst,
    font,
    fill,
):
    if PILMOJI_DOSTEPNE:
        try:
            with Pilmoji(obraz) as pilmoji:
                pilmoji.text(
                    pozycja,
                    tekst,
                    font=font,
                    fill=fill,
                )

            return

        except Exception:
            pass

    draw = ImageDraw.Draw(obraz)

    draw.text(
        pozycja,
        tekst,
        font=font,
        fill=fill,
    )


# ============================================================
# ANALIZA KOLORU
# ============================================================

def analiza_barwna(zrodlo_obrazu):
    obraz = wczytaj_obraz(
        zrodlo_obrazu
    ).convert("RGB")

    obraz.thumbnail(
        (160, 160),
        Image.Resampling.LANCZOS,
    )

    paleta = obraz.quantize(
        colors=16,
        method=Image.Quantize.FASTOCTREE,
    ).convert("RGB")

    kolory = paleta.getcolors(
        paleta.width * paleta.height
    ) or []

    laczna_liczba = sum(
        licznik
        for licznik, _ in kolory
    ) or 1

    x = 0.0
    y = 0.0
    waga_odcienia = 0.0
    suma_nasycenia = 0.0

    for licznik, (r, g, b) in kolory:
        udzial = (
            licznik / laczna_liczba
        )

        h, s, v = colorsys.rgb_to_hsv(
            r / 255,
            g / 255,
            b / 255,
        )

        if v < 0.08 or v > 0.98:
            continue

        suma_nasycenia += (
            udzial * s
        )

        if s >= 0.10:
            waga = (
                udzial * max(s, 0.15)
            )

            kat = (
                2 * math.pi * h
            )

            x += (
                waga * math.cos(kat)
            )

            y += (
                waga * math.sin(kat)
            )

            waga_odcienia += waga

    if waga_odcienia == 0:
        odcien = 0.0

    else:
        odcien = (
            math.atan2(y, x)
            / (2 * math.pi)
        ) % 1.0

    return odcien, suma_nasycenia


def na_ciemny_podklad(
    odcien,
    nasycenie,
):
    jasnosc = (
        0.30
        if nasycenie >= 0.15
        else 0.23
    )

    r, g, b = colorsys.hsv_to_rgb(
        odcien,
        nasycenie,
        jasnosc,
    )

    return (
        int(r * 255),
        int(g * 255),
        int(b * 255),
    )


def znormalizuj_kolor_podkladu(rgb):
    h, s, _ = colorsys.rgb_to_hsv(
        rgb[0] / 255,
        rgb[1] / 255,
        rgb[2] / 255,
    )

    return na_ciemny_podklad(
        h,
        min(s, 0.75),
    )


def kolor_podkladu_ze_zdjecia(
    zrodlo_obrazu,
    maks_nasycenie=0.65,
):
    try:
        odcien, nasycenie = analiza_barwna(
            zrodlo_obrazu
        )

        nasycenie = min(
            nasycenie * 2.5,
            maks_nasycenie,
        )

        return na_ciemny_podklad(
            odcien,
            nasycenie,
        )

    except Exception:
        return (28, 30, 34)


def kolor_pastelowy_ze_zdjecia(
    zrodlo_obrazu,
):
    try:
        odcien, nasycenie = analiza_barwna(
            zrodlo_obrazu
        )

        nasycenie_docelowe = ogranicz(
            0.12 + nasycenie * 0.20,
            0.12,
            0.24,
        )

        r, g, b = colorsys.hsv_to_rgb(
            odcien,
            nasycenie_docelowe,
            0.94,
        )

        return (
            int(r * 255),
            int(g * 255),
            int(b * 255),
        )

    except Exception:
        return (229, 209, 212)


def kolor_akcentowy_ze_zdjecia(
    zrodlo_obrazu,
):
    try:
        obraz = wczytaj_obraz(
            zrodlo_obrazu
        ).convert("RGB")

        obraz.thumbnail(
            (150, 150),
            Image.Resampling.LANCZOS,
        )

        paleta = obraz.quantize(
            colors=20,
            method=Image.Quantize.FASTOCTREE,
        ).convert("RGB")

        kolory = paleta.getcolors(
            paleta.width * paleta.height
        ) or []

        laczna_liczba = sum(
            licznik
            for licznik, _ in kolory
        ) or 1

        najlepszy_kolor = None
        najlepszy_wynik = -1

        for licznik, rgb in kolory:
            r, g, b = rgb

            h, s, v = colorsys.rgb_to_hsv(
                r / 255,
                g / 255,
                b / 255,
            )

            if (
                s < 0.20
                or v < 0.22
                or v > 0.94
            ):
                continue

            udzial = (
                licznik / laczna_liczba
            )

            wynik = (
                (0.25 + udzial)
                * (s ** 1.7)
                * (
                    1.0
                    - abs(v - 0.65) * 0.55
                )
            )

            if wynik > najlepszy_wynik:
                najlepszy_wynik = wynik
                najlepszy_kolor = (
                    h,
                    s,
                    v,
                )

        if najlepszy_kolor is None:
            return (177, 55, 121)

        h, s, v = najlepszy_kolor

        s = ogranicz(
            s * 1.08,
            0.48,
            0.82,
        )

        v = ogranicz(
            v,
            0.48,
            0.76,
        )

        r, g, b = colorsys.hsv_to_rgb(
            h,
            s,
            v,
        )

        return (
            int(r * 255),
            int(g * 255),
            int(b * 255),
        )

    except Exception:
        return (177, 55, 121)


# ============================================================
# GENERATOR POSTA – MAGAZYN
# ============================================================

def generuj_grafike_magazyn(
    zrodlo_zdjecia,
    sciezka_logo,
    tekst_glowny,
    tekst_stopki,
    is_audio=False,
    kolor_podkladu=None,
):
    szerokosc = SZEROKOSC_POSTA
    wysokosc = WYSOKOSC_POSTA

    kolor_bazowy = (
        kolor_podkladu or (0, 0, 0)
    )

    canvas = Image.new(
        "RGBA",
        (szerokosc, wysokosc),
        kolor_bazowy + (255,),
    )

    if zrodlo_zdjecia:
        obraz = wczytaj_obraz(
            zrodlo_zdjecia
        )

        obraz = kadruj_cover(
            obraz,
            szerokosc,
            wysokosc,
        )

        obraz = ImageEnhance.Sharpness(
            obraz
        ).enhance(1.15)

        canvas.alpha_composite(
            obraz
        )

    gradient = Image.new(
        "RGBA",
        (szerokosc, wysokosc),
        (0, 0, 0, 0),
    )

    draw_gradient = ImageDraw.Draw(
        gradient
    )

    start_gradientu = int(
        wysokosc * 0.22
    )

    maks_alpha = (
        246 if is_audio else 235
    )

    for y in range(
        start_gradientu,
        wysokosc,
    ):
        postep = (
            (y - start_gradientu)
            / (
                wysokosc
                - start_gradientu
            )
        )

        alpha = int(
            maks_alpha
            * (postep ** 1.15)
        )

        draw_gradient.line(
            [(0, y), (szerokosc, y)],
            fill=kolor_bazowy + (alpha,),
        )

    canvas = Image.alpha_composite(
        canvas,
        gradient,
    )

    if (
        sciezka_logo
        and os.path.exists(sciezka_logo)
    ):
        logo = wczytaj_obraz(
            sciezka_logo
        )

        logo.thumbnail(
            (260, 180),
            Image.Resampling.LANCZOS,
        )

        canvas.alpha_composite(
            logo,
            (
                szerokosc - logo.width - 40,
                40,
            ),
        )

    tekst_duzy, separator, tekst_maly = (
        tekst_glowny.partition("|")
    )

    tekst_duzy = (
        tekst_duzy.strip().upper()
    )

    tekst_maly = (
        tekst_maly.strip().upper()
        if separator
        else ""
    )

    (
        font_duzy,
        linie_duze,
        wysokosc_linii,
    ) = dopasuj_tekst(
        tekst=tekst_duzy,
        sciezka_fontu=SCIEZKA_FONT_BOLD,
        maks_rozmiar=58,
        min_rozmiar=34,
        maks_szerokosc=szerokosc - 140,
        maks_wysokosc=330,
        odstep_linii=14,
        maks_linii=5,
    )

    linie_male = []
    font_maly = None
    wysokosc_linii_male = 0

    if tekst_maly:
        (
            font_maly,
            linie_male,
            wysokosc_linii_male,
        ) = dopasuj_tekst(
            tekst=tekst_maly,
            sciezka_fontu=SCIEZKA_FONT_SEMIBOLD,
            maks_rozmiar=38,
            min_rozmiar=26,
            maks_szerokosc=szerokosc - 140,
            maks_wysokosc=150,
            odstep_linii=10,
            maks_linii=3,
        )

    calkowita_wysokosc = (
        len(linie_duze)
        * wysokosc_linii
    )

    if linie_male:
        calkowita_wysokosc += (
            22
            + len(linie_male)
            * wysokosc_linii_male
        )

    y = int(
        (wysokosc - 275)
        - calkowita_wysokosc / 2
    )

    kolor_bialy = (
        255,
        255,
        255,
        255,
    )

    for linia in linie_duze:
        szer_linii = szerokosc_tekstu(
            font_duzy,
            linia,
        )

        rysuj_tekst(
            canvas,
            (
                (szerokosc - szer_linii) / 2,
                y,
            ),
            linia,
            font_duzy,
            kolor_bialy,
        )

        y += wysokosc_linii

    if linie_male and font_maly:
        y += 22

        for linia in linie_male:
            szer_linii = szerokosc_tekstu(
                font_maly,
                linia,
            )

            rysuj_tekst(
                canvas,
                (
                    (szerokosc - szer_linii) / 2,
                    y,
                ),
                linia,
                font_maly,
                kolor_bialy,
            )

            y += wysokosc_linii_male

    if tekst_stopki:
        font_stopka = pobierz_czcionke(
            SCIEZKA_FONT_SEMIBOLD,
            22,
        )

        tekst_rozstrzelony = "   ".join(
            tekst_stopki
        )

        szer_stopki = szerokosc_tekstu(
            font_stopka,
            tekst_rozstrzelony,
        )

        rysuj_tekst(
            canvas,
            (
                (szerokosc - szer_stopki) / 2,
                wysokosc - 58,
            ),
            tekst_rozstrzelony,
            font_stopka,
            kolor_bialy,
        )

    return obraz_do_jpeg_bytes(
        canvas
    )


# ============================================================
# GENERATOR POSTA – SPLIT SCREEN
# ============================================================

def generuj_grafike_split(
    zrodlo_zdjecia,
    sciezka_logo,
    tekst_glowny,
    tekst_stopki,
    is_audio=False,
    kolor_podkladu=None,
):
    szerokosc = SZEROKOSC_POSTA
    wysokosc = WYSOKOSC_POSTA

    wysokosc_zdjecia = int(
        szerokosc * 9 / 16
    )

    kolor_tla = kolor_podkladu or (
        (18, 18, 20)
        if is_audio
        else (25, 30, 35)
    )

    canvas = Image.new(
        "RGBA",
        (szerokosc, wysokosc),
        kolor_tla + (255,),
    )

    if zrodlo_zdjecia:
        obraz = wczytaj_obraz(
            zrodlo_zdjecia
        )

        if is_audio:
            obraz.thumbnail(
                (
                    szerokosc,
                    wysokosc_zdjecia,
                ),
                Image.Resampling.LANCZOS,
            )

            probka = (
                obraz.convert("RGB")
                .resize(
                    (1, 1),
                    Image.Resampling.LANCZOS,
                )
                .getpixel((0, 0))
            )

            tlo = Image.new(
                "RGBA",
                (
                    szerokosc,
                    wysokosc_zdjecia,
                ),
                probka + (255,),
            )

            offset_x = (
                szerokosc - obraz.width
            ) // 2

            offset_y = (
                wysokosc_zdjecia
                - obraz.height
            ) // 2

            tlo.alpha_composite(
                obraz,
                (offset_x, offset_y),
            )

            obraz = tlo

        else:
            obraz = kadruj_cover(
                obraz,
                szerokosc,
                wysokosc_zdjecia,
            )

        obraz = ImageEnhance.Sharpness(
            obraz
        ).enhance(1.15)

        canvas.alpha_composite(
            obraz
        )

    draw = ImageDraw.Draw(canvas)

    if is_audio:
        draw.rectangle(
            [
                0,
                wysokosc_zdjecia,
                szerokosc,
                wysokosc_zdjecia + 4,
            ],
            fill=(215, 40, 40, 255),
        )

    if (
        sciezka_logo
        and os.path.exists(sciezka_logo)
    ):
        logo = wczytaj_obraz(
            sciezka_logo
        )

        logo.thumbnail(
            (260, 180),
            Image.Resampling.LANCZOS,
        )

        canvas.alpha_composite(
            logo,
            (
                szerokosc - logo.width - 40,
                40,
            ),
        )

    tekst_duzy, separator, tekst_maly = (
        tekst_glowny.partition("|")
    )

    tekst_duzy = (
        tekst_duzy.strip().upper()
    )

    tekst_maly = (
        tekst_maly.strip().upper()
        if separator
        else ""
    )

    dostepna_wysokosc = (
        wysokosc
        - wysokosc_zdjecia
        - 95
    )

    (
        font_duzy,
        linie_duze,
        wysokosc_linii,
    ) = dopasuj_tekst(
        tekst=tekst_duzy,
        sciezka_fontu=SCIEZKA_FONT_BOLD,
        maks_rozmiar=55,
        min_rozmiar=30,
        maks_szerokosc=szerokosc - 110,
        maks_wysokosc=dostepna_wysokosc * 0.72,
        odstep_linii=12,
        maks_linii=4,
    )

    linie_male = []
    font_maly = None
    wysokosc_linii_male = 0

    if tekst_maly:
        (
            font_maly,
            linie_male,
            wysokosc_linii_male,
        ) = dopasuj_tekst(
            tekst=tekst_maly,
            sciezka_fontu=SCIEZKA_FONT_SEMIBOLD,
            maks_rozmiar=34,
            min_rozmiar=23,
            maks_szerokosc=szerokosc - 110,
            maks_wysokosc=110,
            odstep_linii=8,
            maks_linii=2,
        )

    calkowita_wysokosc = (
        len(linie_duze)
        * wysokosc_linii
    )

    if linie_male:
        calkowita_wysokosc += (
            16
            + len(linie_male)
            * wysokosc_linii_male
        )

    srodek_obszaru = (
        wysokosc_zdjecia
        + (
            wysokosc - wysokosc_zdjecia
        ) / 2
        - 12
    )

    y = int(
        srodek_obszaru
        - calkowita_wysokosc / 2
    )

    kolor_bialy = (
        255,
        255,
        255,
        255,
    )

    for linia in linie_duze:
        szer_linii = szerokosc_tekstu(
            font_duzy,
            linia,
        )

        rysuj_tekst(
            canvas,
            (
                (szerokosc - szer_linii) / 2,
                y,
            ),
            linia,
            font_duzy,
            kolor_bialy,
        )

        y += wysokosc_linii

    if linie_male and font_maly:
        y += 16

        for linia in linie_male:
            szer_linii = szerokosc_tekstu(
                font_maly,
                linia,
            )

            rysuj_tekst(
                canvas,
                (
                    (szerokosc - szer_linii) / 2,
                    y,
                ),
                linia,
                font_maly,
                kolor_bialy,
            )

            y += wysokosc_linii_male

    if tekst_stopki:
        font_stopka = pobierz_czcionke(
            SCIEZKA_FONT_SEMIBOLD,
            21,
        )

        tekst_rozstrzelony = "   ".join(
            tekst_stopki
        )

        szer_stopki = szerokosc_tekstu(
            font_stopka,
            tekst_rozstrzelony,
        )

        kolor_stopki = (
            (235, 235, 235, 255)
            if kolor_podkladu
            else (
                (255, 255, 255, 255)
                if is_audio
                else (185, 185, 190, 255)
            )
        )

        rysuj_tekst(
            canvas,
            (
                (szerokosc - szer_stopki) / 2,
                wysokosc - 48,
            ),
            tekst_rozstrzelony,
            font_stopka,
            kolor_stopki,
        )

    return obraz_do_jpeg_bytes(
        canvas
    )


# ============================================================
# NARZĘDZIA COVERA
# ============================================================

def przytnij_przezroczyste_marginesy(
    obraz,
):
    obraz = obraz.convert("RGBA")
    kanal_alpha = obraz.getchannel("A")
    bbox = kanal_alpha.getbbox()

    if bbox:
        return obraz.crop(bbox)

    return obraz


def przygotuj_duze_logo(
    obraz,
    maks_szerokosc=590,
    maks_wysokosc=150,
):
    obraz = przytnij_przezroczyste_marginesy(
        obraz
    )

    if obraz.width <= 0 or obraz.height <= 0:
        return obraz

    skala = min(
        maks_szerokosc / obraz.width,
        maks_wysokosc / obraz.height,
    )

    nowa_szerokosc = max(
        1,
        int(obraz.width * skala),
    )

    nowa_wysokosc = max(
        1,
        int(obraz.height * skala),
    )

    return obraz.resize(
        (
            nowa_szerokosc,
            nowa_wysokosc,
        ),
        Image.Resampling.LANCZOS,
    )


# ============================================================
# NOWOCZESNY COVER FACEBOOK
# ============================================================

def generuj_cover_fb(
    zrodlo_okladki,
    sciezka_logo,
    tekst_gora,
    tekst_dol,
    kolor_tla,
):
    szerokosc = SZEROKOSC_COVERA
    wysokosc = WYSOKOSC_COVERA

    # Kolor akcentowy pobrany bezpośrednio z okładki.
    kolor_akcentowy = kolor_akcentowy_ze_zdjecia(
        zrodlo_okladki
    )

    # Jeżeli ręcznie wskazano nasycony kolor,
    # używamy go jako akcentu.
    _, nasycenie_reczne, _ = colorsys.rgb_to_hsv(
        kolor_tla[0] / 255,
        kolor_tla[1] / 255,
        kolor_tla[2] / 255,
    )

    if nasycenie_reczne > 0.32:
        kolor_akcentowy = kolor_tla

    # Neutralne tło, tylko lekko zabarwione.
    kolor_lewy = mieszaj_kolory(
        (248, 247, 244),
        kolor_tla,
        0.05,
    )

    kolor_prawy = mieszaj_kolory(
        (242, 241, 238),
        kolor_akcentowy,
        0.05,
    )

    canvas = Image.new(
        "RGBA",
        (szerokosc, wysokosc),
        kolor_lewy + (255,),
    )

    draw = ImageDraw.Draw(canvas)

    for x in range(szerokosc):
        postep = (
            x / max(1, szerokosc - 1)
        )

        kolor = mieszaj_kolory(
            kolor_lewy,
            kolor_prawy,
            postep,
        )

        draw.line(
            [(x, 0), (x, wysokosc)],
            fill=kolor + (255,),
        )

    # ========================================================
    # LOGO
    # ========================================================

    tekst_x = 205
    y = 62

    if (
        sciezka_logo
        and os.path.exists(sciezka_logo)
    ):
        logo = wczytaj_obraz(
            sciezka_logo
        )

        logo = przygotuj_duze_logo(
            logo,
            maks_szerokosc=590,
            maks_wysokosc=150,
        )

        canvas.alpha_composite(
            logo,
            (
                tekst_x,
                y,
            ),
        )

        y += logo.height + 42

    else:
        y = 150

    # ========================================================
    # ETYKIETA
    # ========================================================

    kolor_tekstu = (
        27,
        27,
        31,
        255,
    )

    kolor_pomocniczy_rgb = mieszaj_kolory(
        kolor_akcentowy,
        (27, 27, 31),
        0.34,
    )

    kolor_pomocniczy = (
        kolor_pomocniczy_rgb + (255,)
    )

    poczatek_linii = y

    font_etykieta = pobierz_czcionke(
        SCIEZKA_FONT_SEMIBOLD,
        23,
    )

    draw.text(
        (tekst_x, y),
        "NOWE WYDANIE",
        font=font_etykieta,
        fill=kolor_pomocniczy,
    )

    y += 53

    # ========================================================
    # GŁÓWNY TEKST
    # ========================================================

    tekst_gora = (
        tekst_gora.strip()
        or "Nowy numer już dostępny"
    )

    (
        font_glowny,
        linie_glowne,
        wysokosc_linii,
    ) = dopasuj_tekst(
        tekst=tekst_gora,
        sciezka_fontu=SCIEZKA_FONT_BOLD,
        maks_rozmiar=61,
        min_rozmiar=38,
        maks_szerokosc=690,
        maks_wysokosc=220,
        odstep_linii=10,
        maks_linii=3,
    )

    for linia in linie_glowne:
        draw.text(
            (tekst_x, y),
            linia,
            font=font_glowny,
            fill=kolor_tekstu,
        )

        y += wysokosc_linii

    # ========================================================
    # DATA
    # ========================================================

    y += 27

    tekst_dol = (
        tekst_dol.strip().upper()
    )

    if tekst_dol:
        font_badge = pobierz_czcionke(
            SCIEZKA_FONT_SEMIBOLD,
            24,
        )

        szerokosc_napisu = szerokosc_tekstu(
            font_badge,
            tekst_dol,
        )

        padding_x = 29
        wysokosc_badge = 55

        szerokosc_badge = int(
            szerokosc_napisu
            + padding_x * 2
        )

        szerokosc_badge = min(
            szerokosc_badge,
            530,
        )

        draw.rounded_rectangle(
            (
                tekst_x,
                y,
                tekst_x + szerokosc_badge,
                y + wysokosc_badge,
            ),
            radius=28,
            fill=kolor_akcentowy + (255,),
        )

        draw.text(
            (
                tekst_x + szerokosc_badge / 2,
                y + wysokosc_badge / 2,
            ),
            tekst_dol,
            font=font_badge,
            fill=(255, 255, 255, 255),
            anchor="mm",
        )

        koniec_linii = (
            y + wysokosc_badge
        )

    else:
        koniec_linii = y

    # Pionowa linia dopasowana do tekstu.
    draw.rounded_rectangle(
        (
            160,
            poczatek_linii,
            168,
            koniec_linii,
        ),
        radius=4,
        fill=kolor_akcentowy + (255,),
    )

    # ========================================================
    # OKŁADKA
    # ========================================================

    okladka = wczytaj_obraz(
        zrodlo_okladki
    )

    # Większa okładka – niemal do granic bezpiecznego obszaru.
    # Bezpieczny obszar ma wysokość 624 px: od Y=48 do Y=672.
    okladka.thumbnail(
        (455, 600),
        Image.Resampling.LANCZOS,
    )

    okladka_z_ramka = ImageOps.expand(
        okladka,
        border=4,
        fill=(255, 255, 255, 255),
    )

    okladka_z_ramka = okladka_z_ramka.rotate(
        -0.25,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )

    # Wyśrodkowanie pionowe.
    pozycja_y = int(
        (
            wysokosc
            - okladka_z_ramka.height
        ) / 2
    )

    # Prawa krawędź bezpiecznego obszaru Facebooka.
    prawa_krawedz_bezpieczna = 1460

    pozycja_x = (
        prawa_krawedz_bezpieczna
        - okladka_z_ramka.width
    )

    # Dodatkowe zabezpieczenie pionowe.
    pozycja_y = max(
        48,
        pozycja_y,
    )

    if (
        pozycja_y
        + okladka_z_ramka.height
        > 672
    ):
        pozycja_y = (
            672
            - okladka_z_ramka.height
        )

    # ========================================================
    # CIEŃ
    # ========================================================

    maska_okladki = (
        okladka_z_ramka.getchannel("A")
    )

    element_cienia = Image.new(
        "RGBA",
        okladka_z_ramka.size,
        (12, 12, 18, 0),
    )

    maska_cienia = maska_okladki.point(
        lambda alfa: int(
            alfa * 0.40
        )
    )

    element_cienia.putalpha(
        maska_cienia
    )

    warstwa_cienia = Image.new(
        "RGBA",
        canvas.size,
        (0, 0, 0, 0),
    )

    warstwa_cienia.alpha_composite(
        element_cienia,
        (
            pozycja_x + 21,
            pozycja_y + 25,
        ),
    )

    warstwa_cienia = warstwa_cienia.filter(
        ImageFilter.GaussianBlur(26)
    )

    canvas = Image.alpha_composite(
        canvas,
        warstwa_cienia,
    )

    canvas.alpha_composite(
        okladka_z_ramka,
        (
            pozycja_x,
            pozycja_y,
        ),
    )

    return obraz_do_jpeg_bytes(
        canvas,
        jakosc=96,
    )


def dodaj_podglad_strefy_bezpiecznej(
    cover_bytes,
):
    obraz = wczytaj_obraz(
        cover_bytes
    )

    nakladka = Image.new(
        "RGBA",
        obraz.size,
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(
        nakladka
    )

    draw.rectangle(
        (
            180,
            48,
            1460,
            672,
        ),
        outline=(255, 70, 70, 230),
        width=4,
    )

    font = pobierz_czcionke(
        SCIEZKA_FONT_SEMIBOLD,
        22,
    )

    draw.rounded_rectangle(
        (
            195,
            60,
            510,
            105,
        ),
        radius=12,
        fill=(255, 70, 70, 220),
    )

    draw.text(
        (215, 70),
        "BEZPIECZNY OBSZAR",
        fill=(255, 255, 255, 255),
        font=font,
    )

    wynik = Image.alpha_composite(
        obraz,
        nakladka,
    )

    return obraz_do_jpeg_bytes(
        wynik,
        jakosc=93,
    )


# ============================================================
# WARIANTY POSTÓW
# ============================================================

WARIANTY = {
    "magazyn": (
        "magazyn",
        STOPKA_DOMYSLNA,
        False,
    ),
    "split": (
        "split",
        STOPKA_DOMYSLNA,
        False,
    ),
    "magazyn_bez": (
        "magazyn",
        "",
        False,
    ),
    "split_bez": (
        "split",
        "",
        False,
    ),
    "magazyn_kolor": (
        "magazyn",
        STOPKA_DOMYSLNA,
        True,
    ),
    "split_kolor": (
        "split",
        STOPKA_DOMYSLNA,
        True,
    ),
    "magazyn_kolor_bez": (
        "magazyn",
        "",
        True,
    ),
    "split_kolor_bez": (
        "split",
        "",
        True,
    ),
}

KARTY = {
    "magazyn": (
        "Styl Magazyn",
        "📥 Pobierz Magazyn",
        "fb_magazyn.jpg",
        "Magazyn",
    ),
    "split": (
        "Styl Split Screen",
        "📥 Pobierz Split Screen",
        "fb_split.jpg",
        "Split Screen",
    ),
    "magazyn_bez": (
        "Styl Magazyn – bez komentarza",
        "📥 Pobierz Magazyn (bez kom.)",
        "fb_magazyn_bez_komentarza.jpg",
        "Magazyn - bez komentarza",
    ),
    "split_bez": (
        "Styl Split Screen – bez komentarza",
        "📥 Pobierz Split Screen (bez kom.)",
        "fb_split_bez_komentarza.jpg",
        "Split Screen - bez komentarza",
    ),
    "magazyn_kolor": (
        "Magazyn – kolor ze zdjęcia",
        "📥 Pobierz Magazyn (kolor)",
        "fb_magazyn_kolor.jpg",
        "Magazyn - kolor dominujący",
    ),
    "split_kolor": (
        "Split Screen – kolor ze zdjęcia",
        "📥 Pobierz Split Screen (kolor)",
        "fb_split_kolor.jpg",
        "Split Screen - kolor dominujący",
    ),
    "magazyn_kolor_bez": (
        "Magazyn – kolor ze zdjęcia",
        "📥 Pobierz Magazyn (kolor, bez kom.)",
        "fb_magazyn_kolor_bez_komentarza.jpg",
        "Magazyn - kolor dominujący - bez komentarza",
    ),
    "split_kolor_bez": (
        "Split Screen – kolor ze zdjęcia",
        "📥 Pobierz Split Screen (kolor, bez kom.)",
        "fb_split_kolor_bez_komentarza.jpg",
        "Split Screen - kolor dominujący - bez komentarza",
    ),
}


def wygeneruj_grafiki(
    zrodlo_zdjecia,
    sciezka_do_logo,
    tytul,
    is_audio,
    kolor_wymuszony=None,
):
    if kolor_wymuszony is not None:
        kolor_ze_zdjecia = (
            znormalizuj_kolor_podkladu(
                kolor_wymuszony
            )
        )

    else:
        kolor_ze_zdjecia = (
            kolor_podkladu_ze_zdjecia(
                zrodlo_zdjecia
            )
        )

    gotowe = {}

    for klucz, (
        styl,
        stopka,
        kolorowa,
    ) in WARIANTY.items():

        kolor = (
            kolor_ze_zdjecia
            if kolorowa
            else None
        )

        if styl == "magazyn":
            wynik = generuj_grafike_magazyn(
                zrodlo_zdjecia=zrodlo_zdjecia,
                sciezka_logo=sciezka_do_logo,
                tekst_glowny=tytul,
                tekst_stopki=stopka,
                is_audio=is_audio,
                kolor_podkladu=kolor,
            )

        else:
            wynik = generuj_grafike_split(
                zrodlo_zdjecia=zrodlo_zdjecia,
                sciezka_logo=sciezka_do_logo,
                tekst_glowny=tytul,
                tekst_stopki=stopka,
                is_audio=is_audio,
                kolor_podkladu=kolor,
            )

        gotowe[klucz] = wynik

    return (
        gotowe,
        kolor_ze_zdjecia,
    )


# ============================================================
# ANALITYKA
# ============================================================

def aktualizuj_licznik(
    styl_grafiki,
    uzyte_logo,
):
    nazwa_marki = (
        uzyte_logo
        if uzyte_logo
        else "BRAK LOGA"
    )

    teraz = datetime.datetime.now(
        ZoneInfo("Europe/Warsaw")
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    try:
        if (
            "GOOGLE_CREDENTIALS_JSON"
            not in st.secrets
        ):
            return

        creds_json = json.loads(
            st.secrets[
                "GOOGLE_CREDENTIALS_JSON"
            ]
        )

        gc = gspread.service_account_from_dict(
            creds_json
        )

        arkusz = gc.open(
            "Statystyki_Grafik_FB"
        )

        arkusz.sheet1.append_row(
            [
                teraz,
                styl_grafiki,
                nazwa_marki,
            ],
            value_input_option="RAW",
        )

    except Exception as blad:
        print(
            "Błąd zapisu statystyki:",
            blad,
        )


# ============================================================
# STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Generator Postów FB",
    page_icon="🎨",
    layout="centered",
)

st.title(
    "🎨 Automatyczny Generator Grafik"
)

st.write(
    "Wybierz rodzaj grafiki, którą chcesz stworzyć."
)

st.caption(
    f"Wersja {WERSJA_APP}"
)

try:
    przygotuj_czcionki()

except Exception as blad:
    st.error(str(blad))
    st.stop()


# ============================================================
# LOGOTYPY
# ============================================================

KATALOG_LOGOTYPOW = "logotypy"
OPCJA_BEZ_LOGA = "❌ Bez loga"

os.makedirs(
    KATALOG_LOGOTYPOW,
    exist_ok=True,
)

dostepne_loga = [
    plik
    for plik in os.listdir(
        KATALOG_LOGOTYPOW
    )
    if plik.lower().endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        )
    )
]

dostepne_loga.sort(
    key=str.lower
)

if dostepne_loga:
    indeks_bd = next(
        (
            i
            for i, nazwa in enumerate(
                dostepne_loga
            )
            if "budujemydom" in nazwa.lower()
        ),
        None,
    )

    if indeks_bd is not None:
        logo_bd = dostepne_loga.pop(
            indeks_bd
        )

        dostepne_loga.insert(
            0,
            logo_bd,
        )

        dostepne_loga.insert(
            1,
            OPCJA_BEZ_LOGA,
        )

    else:
        dostepne_loga.insert(
            0,
            OPCJA_BEZ_LOGA,
        )

else:
    dostepne_loga = [
        OPCJA_BEZ_LOGA
    ]


if "wygenerowano" not in st.session_state:
    st.session_state.wygenerowano = False


tab1, tab2 = st.tabs(
    [
        "📲 Posty do artykułu",
        "🖼️ Nowoczesny cover FB",
    ]
)


# ============================================================
# ZAKŁADKA 1
# ============================================================

with tab1:
    wybrane_logo = st.selectbox(
        "Wybierz markę (logo):",
        dostepne_loga,
        key="logo_posty",
    )

    url_input = st.text_input(
        "🔗 Link do artykułu:",
        placeholder="https://...",
    )

    if st.button(
        "🚀 Pobierz i generuj grafiki",
        type="primary",
        use_container_width=True,
    ):
        if not url_input.strip():
            st.warning(
                "Najpierw wklej link."
            )

        else:
            with st.spinner(
                "Pobieram artykuł i generuję grafiki..."
            ):
                try:
                    sciezka_do_logo = (
                        None
                        if wybrane_logo == OPCJA_BEZ_LOGA
                        else os.path.join(
                            KATALOG_LOGOTYPOW,
                            wybrane_logo,
                        )
                    )

                    is_audio_brand = bool(
                        wybrane_logo
                        != OPCJA_BEZ_LOGA
                        and "audio"
                        in wybrane_logo.lower()
                    )

                    (
                        tytul,
                        obraz_bytes,
                    ) = pobierz_dane_z_artykulu(
                        url_input.strip()
                    )

                    (
                        grafiki,
                        kolor_uzyty,
                    ) = wygeneruj_grafiki(
                        zrodlo_zdjecia=obraz_bytes,
                        sciezka_do_logo=sciezka_do_logo,
                        tytul=tytul,
                        is_audio=is_audio_brand,
                    )

                    st.session_state.obraz_artykulu = (
                        obraz_bytes
                    )

                    st.session_state.aktualny_tytul = (
                        tytul
                    )

                    st.session_state.sciezka_do_logo = (
                        sciezka_do_logo
                    )

                    st.session_state.is_audio_brand = (
                        is_audio_brand
                    )

                    st.session_state.logo_nazwa = (
                        wybrane_logo
                    )

                    st.session_state.kolor_reczny = None
                    st.session_state.grafiki = grafiki
                    st.session_state.kolor_uzyty = kolor_uzyty
                    st.session_state.wygenerowano = True

                except Exception as blad:
                    st.session_state.wygenerowano = False

                    st.error(
                        "Nie udało się pobrać artykułu "
                        "lub wygenerować grafik."
                    )

                    st.caption(
                        str(blad)
                    )

    if st.session_state.get(
        "wygenerowano",
        False,
    ):
        st.success(
            "Grafiki zostały wygenerowane."
        )

        def pokaz_pare(klucze):
            kolumny = st.columns(2)

            for kolumna, klucz in zip(
                kolumny,
                klucze,
            ):
                (
                    podpis,
                    etykieta,
                    nazwa_pliku,
                    nazwa_statystyki,
                ) = KARTY[klucz]

                with kolumna:
                    st.image(
                        st.session_state.grafiki[
                            klucz
                        ],
                        caption=podpis,
                        use_container_width=True,
                    )

                    st.download_button(
                        label=etykieta,
                        data=st.session_state.grafiki[
                            klucz
                        ],
                        file_name=nazwa_pliku,
                        mime="image/jpeg",
                        use_container_width=True,
                        key=f"pobierz_{klucz}",
                        on_click=aktualizuj_licznik,
                        args=(
                            nazwa_statystyki,
                            st.session_state.get(
                                "logo_nazwa"
                            ),
                        ),
                    )

        z_komentarzem = st.toggle(
            "Napis „ARTYKUŁ W KOMENTARZU”",
            value=True,
        )

        sufiks = (
            ""
            if z_komentarzem
            else "_bez"
        )

        st.subheader(
            "🎨 Kolor ze zdjęcia"
        )

        pokaz_pare(
            [
                f"magazyn_kolor{sufiks}",
                f"split_kolor{sufiks}",
            ]
        )

        kolor_uzyty = st.session_state.get(
            "kolor_uzyty"
        )

        if kolor_uzyty:
            hex_uzyty = rgb_na_hex(
                kolor_uzyty
            )

            with st.expander(
                f"🎚️ Kolor podlewki: {hex_uzyty}"
            ):
                nowy_kolor = st.color_picker(
                    "Wybierz kolor:",
                    value=hex_uzyty,
                )

                kol_a, kol_b = st.columns(2)

                def przelicz_posty(
                    kolor_wymuszony
                ):
                    (
                        st.session_state.grafiki,
                        st.session_state.kolor_uzyty,
                    ) = wygeneruj_grafiki(
                        zrodlo_zdjecia=(
                            st.session_state.obraz_artykulu
                        ),
                        sciezka_do_logo=(
                            st.session_state.sciezka_do_logo
                        ),
                        tytul=(
                            st.session_state.aktualny_tytul
                        ),
                        is_audio=(
                            st.session_state.is_audio_brand
                        ),
                        kolor_wymuszony=kolor_wymuszony,
                    )

                    st.session_state.kolor_reczny = (
                        kolor_wymuszony
                    )

                if kol_a.button(
                    "🎨 Zastosuj kolor",
                    use_container_width=True,
                ):
                    przelicz_posty(
                        hex_na_rgb(nowy_kolor)
                    )

                    st.rerun()

                if kol_b.button(
                    "↩️ Kolor ze zdjęcia",
                    use_container_width=True,
                ):
                    przelicz_posty(None)
                    st.rerun()

        st.markdown("---")

        st.subheader(
            "⬛ Klasyczne, czarne"
        )

        pokaz_pare(
            [
                f"magazyn{sufiks}",
                f"split{sufiks}",
            ]
        )

        st.markdown("---")

        nowy_tytul = st.text_area(
            (
                "Edytuj tytuł. Enter wymusza nową linię. "
                "Znak „|” rozpoczyna mniejszy podtytuł:"
            ),
            value=st.session_state.aktualny_tytul,
            height=110,
        )

        if st.button(
            "🔄 Zaktualizuj napisy",
            use_container_width=True,
        ):
            try:
                (
                    st.session_state.grafiki,
                    st.session_state.kolor_uzyty,
                ) = wygeneruj_grafiki(
                    zrodlo_zdjecia=(
                        st.session_state.obraz_artykulu
                    ),
                    sciezka_do_logo=(
                        st.session_state.sciezka_do_logo
                    ),
                    tytul=nowy_tytul,
                    is_audio=(
                        st.session_state.is_audio_brand
                    ),
                    kolor_wymuszony=(
                        st.session_state.get(
                            "kolor_reczny"
                        )
                    ),
                )

                st.session_state.aktualny_tytul = (
                    nowy_tytul
                )

                st.rerun()

            except Exception as blad:
                st.error(
                    f"Nie udało się zaktualizować grafik: {blad}"
                )


# ============================================================
# ZAKŁADKA 2 – COVER
# ============================================================

with tab2:
    st.info(
        "Cover jest generowany w rozmiarze "
        "1640 × 720 px z bezpiecznym obszarem "
        "dla komputerów i telefonów."
    )

    indeks_cnw = next(
        (
            i
            for i, nazwa in enumerate(
                dostepne_loga
            )
            if (
                "czas" in nazwa.lower()
                or "wnetrze" in nazwa.lower()
                or "wnętrze" in nazwa.lower()
            )
        ),
        0,
    )

    col1, col2 = st.columns(2)

    with col1:
        wybrane_logo_cover = st.selectbox(
            "Wybierz logo:",
            dostepne_loga,
            index=indeks_cnw,
            key="logo_cover",
        )

        wgrana_okladka = st.file_uploader(
            "Wgraj okładkę JPG, PNG lub WEBP:",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp",
            ],
            key="okladka_cover",
        )

    with col2:
        tekst_gora = st.text_area(
            "Główny tekst (użyj Enter, aby przełamać linię):",
            value="Nowy numer już dostępny",
            height=68,
        )

        tekst_dol = st.text_input(
            "Data lub krótka informacja:",
            value="PAŹDZIERNIK 2026",
        )

        auto_kolor_covera = st.checkbox(
            "Automatycznie dobierz kolor z okładki",
            value=True,
        )

        kolor_reczny_covera = st.color_picker(
            "Ręczny kolor akcentu:",
            value="#B13779",
            disabled=auto_kolor_covera,
        )

        pokaz_strefe = st.checkbox(
            "Pokaż strefę bezpieczną w podglądzie",
            value=False,
        )

    if st.button(
        "🎨 Generuj nowoczesny cover",
        type="primary",
        use_container_width=True,
    ):
        if wgrana_okladka is None:
            st.warning(
                "Najpierw wgraj plik z okładką."
            )

        else:
            with st.spinner(
                "Projektuję nowoczesny cover..."
            ):
                try:
                    dane_okladki = (
                        wgrana_okladka.getvalue()
                    )

                    wczytaj_obraz(
                        dane_okladki
                    )

                    sciezka_logo_cover = (
                        None
                        if (
                            wybrane_logo_cover
                            == OPCJA_BEZ_LOGA
                        )
                        else os.path.join(
                            KATALOG_LOGOTYPOW,
                            wybrane_logo_cover,
                        )
                    )

                    if auto_kolor_covera:
                        kolor_tla = (
                            kolor_pastelowy_ze_zdjecia(
                                dane_okladki
                            )
                        )

                    else:
                        kolor_tla = hex_na_rgb(
                            kolor_reczny_covera
                        )

                    cover_bytes = generuj_cover_fb(
                        zrodlo_okladki=dane_okladki,
                        sciezka_logo=sciezka_logo_cover,
                        tekst_gora=tekst_gora,
                        tekst_dol=tekst_dol,
                        kolor_tla=kolor_tla,
                    )

                    st.session_state.cover_bytes = (
                        cover_bytes
                    )

                    st.session_state.cover_wygenerowany = (
                        True
                    )

                    st.success(
                        "Cover został wygenerowany."
                    )

                except Exception as blad:
                    st.session_state.cover_wygenerowany = (
                        False
                    )

                    st.error(
                        "Nie udało się wygenerować covera."
                    )

                    st.caption(
                        str(blad)
                    )

    if st.session_state.get(
        "cover_wygenerowany",
        False,
    ):
        cover_bytes = (
            st.session_state.cover_bytes
        )

        if pokaz_strefe:
            podglad_covera = (
                dodaj_podglad_strefy_bezpiecznej(
                    cover_bytes
                )
            )

        else:
            podglad_covera = cover_bytes

        st.image(
            podglad_covera,
            caption=(
                "Podgląd covera"
                + (
                    " ze strefą bezpieczną"
                    if pokaz_strefe
                    else ""
                )
            ),
            use_container_width=True,
        )

        st.download_button(
            label="📥 Pobierz Cover FB",
            data=cover_bytes,
            file_name="Cover_FB_1640x720.jpg",
            mime="image/jpeg",
            use_container_width=True,
            on_click=aktualizuj_licznik,
            args=(
                "Nowoczesny Cover FB",
                wybrane_logo_cover,
            ),
        )
