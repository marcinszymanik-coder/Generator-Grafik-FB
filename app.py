import os
import urllib.request
import ssl
import requests
from io import BytesIO
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import streamlit as st
import datetime
from zoneinfo import ZoneInfo
import json
import gspread 
import colorsys
import math

from pilmoji import Pilmoji 

# Wyłączenie weryfikacji certyfikatów SSL
ssl._create_default_https_context = ssl._create_unverified_context

# Domyślny tekst stopki (wersje "bez komentarza" dostają pusty string)
STOPKA_DOMYSLNA = "ARTYKUŁ W KOMENTARZU"

# Znacznik wersji
WERSJA_APP = "4.0 – obsługa mniejszego podtytułu oraz generator Coverów FB"

# ==========================================
# FUNKCJA ANALITYCZNA (Zapis do Arkuszy Google w tle)
# ==========================================
def aktualizuj_licznik(styl_grafiki, uzyte_logo):
    nazwa_marki = uzyte_logo if uzyte_logo else "BRAK LOGA"
    
    # Pobieramy czas z uwzględnieniem polskiej strefy czasowej
    teraz = datetime.datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        if "GOOGLE_CREDENTIALS_JSON" in st.secrets:
            creds_json = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
            gc = gspread.service_account_from_dict(creds_json)
            sh = gc.open("Statystyki_Grafik_FB")
            worksheet = sh.sheet1
            
            worksheet.append_row([teraz, styl_grafiki, nazwa_marki])
            print(f"✅ [SUKCES] Zapisano do Arkuszy: {styl_grafiki} | {nazwa_marki}")
    except Exception as e:
        print(f"❌ [BŁĄD ZAPISU DO ARKUSZA]: {e}")

# ==========================================
# FUNKCJE BAZOWE
# ==========================================
def wyczysc_tytul_portalu(tytul_surowy):
    smieci = [
        "- budujemydom.pl", "- budujemydom", "| budujemydom.pl", "- Budujemy Dom", "- BudujemyDom",
        "- czasnawnetrze.pl", "- czasnawnetrze", "| czasnawnetrze.pl", "- Czas na Wnętrze",
        "- audio.com.pl", "- audio", "| audio.com.pl", "- Testy, ceny", "- Test"
    ]
    tytul_czysty = tytul_surowy.strip()
    for s in smieci:
        if tytul_czysty.lower().endswith(s.lower()):
            tytul_czysty = tytul_czysty[:-len(s)].strip()
    return tytul_czysty.strip("- – |").strip()

def pobierz_dane_z_artykulu(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tytul = "BRAK TYTUŁU"
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            tytul = wyczysc_tytul_portalu(og_title.get('content'))
        else:
            if soup.title:
                tytul = wyczysc_tytul_portalu(soup.title.string)

        img_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image.get('content')

        linki_zdjec = []
        for tag in soup.find_all(['source', 'img']):
            srcset = tag.get('srcset')
            if srcset:
                for czesc in srcset.split(','):
                    podzial = czesc.strip().split()
                    if podzial: linki_zdjec.append(podzial[0])
            src = tag.get('src')
            if src: linki_zdjec.append(src) 

        najlepszy_strzal = None
        for link in linki_zdjec:
            if "/i/" in link and "1050x0" in link:
                najlepszy_strzal = link
                break
        
        if najlepszy_strzal:
            img_url = najlepszy_strzal

        nazwa_zdjecia = None
        if img_url:
            img_url = urljoin(url, img_url) 
            img_data = requests.get(img_url, headers=headers, timeout=10).content
            obrazek_w_pamieci = Image.open(BytesIO(img_data))
            czysty_obrazek_rgb = obrazek_w_pamieci.convert('RGB')
            nazwa_zdjecia = "tymczasowe_zdjecie.jpg"
            czysty_obrazek_rgb.save(nazwa_zdjecia, format='JPEG', quality=100)
        
        return tytul, nazwa_zdjecia
    except Exception as e:
        return None, None

def pobierz_nowoczesne_czcionki():
    czcionki = {
        "Montserrat-Bold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
        "Montserrat-SemiBold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-SemiBold.ttf"
    }
    for nazwa_pliku, url in czcionki.items():
        if not os.path.exists(nazwa_pliku):
            try: urllib.request.urlretrieve(url, nazwa_pliku)
            except Exception: pass

def zawin_tekst(tekst, font, max_szerokosc):
    linie_ostateczne = []
    akapity = tekst.split('\n')
    
    for akapit in akapity:
        slowa = akapit.split()
        if not slowa:
            linie_ostateczne.append("") 
            continue
            
        aktualna_linia = []
        for slowo in slowa:
            linia_testowa = " ".join(aktualna_linia + [slowo])
            szerokosc = font.getlength(linia_testowa) if hasattr(font, 'getlength') else font.getbbox(linia_testowa)[2]
            
            if szerokosc <= max_szerokosc:
                aktualna_linia.append(slowo)
            else:
                linie_ostateczne.append(" ".join(aktualna_linia))
                aktualna_linia = [slowo]
        
        if aktualna_linia:
            linie_ostateczne.append(" ".join(aktualna_linia))
            
    return linie_ostateczne

# ==========================================
# KOLOR DOMINUJĄCY ZE ZDJĘCIA
# ==========================================
def _analiza_barwna(sciezka_zdjecia):
    img = Image.open(sciezka_zdjecia).convert("RGB")
    img = img.resize((120, 120), Image.Resampling.LANCZOS)

    paleta = img.quantize(colors=12, method=Image.Quantize.FASTOCTREE).convert("RGB")
    kolory = paleta.getcolors(120 * 120) or []
    laczna_liczba = sum(licznik for licznik, _ in kolory) or 1

    x = y = waga_odcienia = 0.0
    srednie_nasycenie = 0.0

    for licznik, (r, g, b) in kolory:
        udzial = licznik / laczna_liczba
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

        if v < 0.10 or v > 0.97:
            continue

        srednie_nasycenie += udzial * s

        if s >= 0.12:
            waga = udzial * s
            kat = 2 * math.pi * h
            x += waga * math.cos(kat)
            y += waga * math.sin(kat)
            waga_odcienia += waga

    odcien = 0.0 if waga_odcienia == 0 else (math.atan2(y, x) / (2 * math.pi)) % 1.0
    return odcien, srednie_nasycenie

def _na_podklad(odcien, nasycenie):
    jasnosc = 0.30 if nasycenie >= 0.15 else 0.24
    r, g, b = colorsys.hsv_to_rgb(odcien, nasycenie, jasnosc)
    return (int(r * 255), int(g * 255), int(b * 255))

def znormalizuj_kolor_podkladu(rgb):
    h, s, _v = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    return _na_podklad(h, min(s, 0.75))

def kolor_podkladu_ze_zdjecia(sciezka_zdjecia, maks_nasycenie=0.65):
    if not sciezka_zdjecia or not os.path.exists(sciezka_zdjecia):
        return None
    try:
        odcien, nasycenie = _analiza_barwna(sciezka_zdjecia)
        nasycenie = min(nasycenie * 2.5, maks_nasycenie)
        return _na_podklad(odcien, nasycenie)
    except Exception as e:
        print(f"⚠️ [KOLOR DOMINUJĄCY] Nie udało się wyliczyć koloru: {e}")
        return None

# ==========================================
# GENERATOR 1: MAGAZYN 
# ==========================================
def generuj_grafike_magazyn(sciezka_zdjecia, sciezka_logo, tekst_glowny, tekst_stopki, nazwa_wyjsciowa, is_audio=False, kolor_podkladu=None):
    szerokosc, wysokosc = 1080, 1080
    kolor_bazowy = kolor_podkladu if kolor_podkladu else (0, 0, 0)
    canvas = Image.new("RGBA", (szerokosc, wysokosc), kolor_bazowy + (255,))
    
    if sciezka_zdjecia and os.path.exists(sciezka_zdjecia):
        img = Image.open(sciezka_zdjecia).convert("RGBA")
        
        prop_docelowa = szerokosc / wysokosc
        prop_zdjecia = img.width / img.height
        if prop_zdjecia > prop_docelowa:
            nowa_szer = int(prop_docelowa * img.height)
            margines = (img.width - nowa_szer) // 2
            img = img.crop((margines, 0, margines + nowa_szer, img.height))
        else:
            nowa_wys = int(img.width / prop_docelowa)
            margines = (img.height - nowa_wys) // 2
            img = img.crop((0, margines, img.width, margines + nowa_wys))
        img = img.resize((szerokosc, wysokosc), Image.Resampling.LANCZOS)
            
        enhancer_sharp = ImageEnhance.Sharpness(img)
        img = enhancer_sharp.enhance(1.2)
        canvas.paste(img, (0, 0))

    gradient = Image.new('RGBA', (szerokosc, wysokosc), (0, 0, 0, 0))
    draw_grad = ImageDraw.Draw(gradient)
    start_grad = int(wysokosc * 0.25) 
    
    max_alpha = 245 if is_audio else 235
    for y in range(start_grad, wysokosc):
        alpha = int(max_alpha * ((y - start_grad) / (wysokosc - start_grad)))
        draw_grad.line([(0, y), (szerokosc, y)], fill=kolor_bazowy + (alpha,))
    canvas = Image.alpha_composite(canvas, gradient)
    
    if sciezka_logo and os.path.exists(sciezka_logo):
        logo = Image.open(sciezka_logo).convert("RGBA")
        logo.thumbnail((240, 240), Image.Resampling.LANCZOS)
        canvas.paste(logo, (szerokosc - logo.width - 40, 40), logo)

    czesci_tytulu = tekst_glowny.split('|')
    tekst_duzy = czesci_tytulu[0].strip()
    tekst_maly = czesci_tytulu[1].strip() if len(czesci_tytulu) > 1 else ""

    rozmiar_fontu = 46 if len(tekst_duzy) > 50 else 55
    rozmiar_fontu_maly = int(rozmiar_fontu * 0.65) 
    
    try:
        font_duzy = ImageFont.truetype("Montserrat-Bold.ttf", rozmiar_fontu)
        font_maly = ImageFont.truetype("Montserrat-SemiBold.ttf", rozmiar_fontu_maly)
        font_stopka = ImageFont.truetype("Montserrat-SemiBold.ttf", 24)
    except Exception: return

    kolor_biel = (255, 255, 255, 255)
    
    linie_glowne = zawin_tekst(tekst_duzy.upper(), font_duzy, szerokosc - 140)
    wysokosc_linii = rozmiar_fontu + 16
    
    linie_male = []
    wysokosc_linii_male = rozmiar_fontu_maly + 10
    if tekst_maly:
        linie_male = zawin_tekst(tekst_maly.upper(), font_maly, szerokosc - 140)

    calkowita_wysokosc = (len(linie_glowne) * wysokosc_linii)
    if tekst_maly:
        calkowita_wysokosc += 20 + (len(linie_male) * wysokosc_linii_male) 

    y_tekstu_poczatkowy = (wysokosc - 280) - (calkowita_wysokosc / 2)

    with Pilmoji(canvas) as pilmoji:
        for linia in linie_glowne:
            szer_linii = font_duzy.getlength(linia) if hasattr(font_duzy, 'getlength') else font_duzy.getbbox(linia)[2]
            pilmoji.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_duzy)
            y_tekstu_poczatkowy += wysokosc_linii

        if tekst_maly:
            y_tekstu_poczatkowy += 20
            for linia in linie_male:
                szer_linii = font_maly.getlength(linia) if hasattr(font_maly, 'getlength') else font_maly.getbbox(linia)[2]
                pilmoji.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_maly)
                y_tekstu_poczatkowy += wysokosc_linii_male

        if tekst_stopki:
            tekst_stopki_rozstrzelony = "   ".join(tekst_stopki)
            szer_rozstrzelona = font_stopka.getlength(tekst_stopki_rozstrzelony) if hasattr(font_stopka, 'getlength') else font_stopka.getbbox(tekst_stopki_rozstrzelony)[2]
            pilmoji.text(((szerokosc - szer_rozstrzelona) / 2, wysokosc - 60), tekst_stopki_rozstrzelony, fill=kolor_biel, font=font_stopka)

    canvas = canvas.convert("RGB") 
    canvas.save(nazwa_wyjsciowa, quality=100)

# ==========================================
# GENERATOR 2: SPLIT SCREEN 
# ==========================================
def generuj_grafike_split(sciezka_zdjecia, sciezka_logo, tekst_glowny, tekst_stopki, nazwa_wyjsciowa, is_audio=False, kolor_podkladu=None):
    szerokosc, wysokosc = 1080, 1080
    wys_zdjecia = int(szerokosc * 9 / 16)
    
    if kolor_podkladu:
        kolor_tla_tekstu = kolor_podkladu
    else:
        kolor_tla_tekstu = (18, 18, 20) if is_audio else (25, 30, 35)
    canvas = Image.new("RGBA", (szerokosc, wysokosc), kolor_tla_tekstu)
    
    if sciezka_zdjecia and os.path.exists(sciezka_zdjecia):
        img = Image.open(sciezka_zdjecia).convert("RGBA")
        
        if is_audio:
            wspolczynnik = min(szerokosc / img.width, wys_zdjecia / img.height)
            nowa_szer = int(img.width * wspolczynnik)
            nowa_wys = int(img.height * wspolczynnik)
            img_resized = img.resize((nowa_szer, nowa_wys), Image.Resampling.LANCZOS)
            kolor_probki = img.getpixel((0, 0))
            tlo = Image.new("RGBA", (szerokosc, wys_zdjecia), kolor_probki)
            offset_x = (szerokosc - nowa_szer) // 2
            offset_y = (wys_zdjecia - nowa_wys) // 2
            tlo.paste(img_resized, (offset_x, offset_y))
            img = tlo
        else:
            prop_docelowa = szerokosc / wys_zdjecia
            prop_zdjecia = img.width / img.height
            if prop_zdjecia > prop_docelowa:
                nowa_szer = int(prop_docelowa * img.height)
                margines = (img.width - nowa_szer) // 2
                img = img.crop((margines, 0, margines + nowa_szer, img.height))
            else:
                nowa_wys = int(img.width / prop_docelowa)
                margines = (img.height - nowa_wys) // 2
                img = img.crop((0, margines, img.width, margines + nowa_wys))
            img = img.resize((szerokosc, wys_zdjecia), Image.Resampling.LANCZOS)
            
        enhancer_sharp = ImageEnhance.Sharpness(img)
        img = enhancer_sharp.enhance(1.2)
        canvas.paste(img, (0, 0))

    draw = ImageDraw.Draw(canvas)

    if is_audio:
        draw.rectangle([0, wys_zdjecia, szerokosc, wys_zdjecia + 4], fill=(215, 40, 40, 255))

    if sciezka_logo and os.path.exists(sciezka_logo):
        logo = Image.open(sciezka_logo).convert("RGBA")
        logo.thumbnail((240, 240), Image.Resampling.LANCZOS)
        canvas.paste(logo, (szerokosc - logo.width - 40, 40), logo)

    czesci_tytulu = tekst_glowny.split('|')
    tekst_duzy = czesci_tytulu[0].strip()
    tekst_maly = czesci_tytulu[1].strip() if len(czesci_tytulu) > 1 else ""

    rozmiar_fontu = 48 if len(tekst_duzy) > 50 else 56
    rozmiar_fontu_maly = int(rozmiar_fontu * 0.65)
    
    try:
        font_duzy = ImageFont.truetype("Montserrat-Bold.ttf", rozmiar_fontu)
        font_maly = ImageFont.truetype("Montserrat-SemiBold.ttf", rozmiar_fontu_maly)
        font_stopka = ImageFont.truetype("Montserrat-SemiBold.ttf", 22)
    except Exception: return

    kolor_biel = (255, 255, 255, 255)
    
    linie_glowne = zawin_tekst(tekst_duzy.upper(), font_duzy, szerokosc - 100)
    wysokosc_linii = rozmiar_fontu + 15

    linie_male = []
    wysokosc_linii_male = rozmiar_fontu_maly + 10
    if tekst_maly:
        linie_male = zawin_tekst(tekst_maly.upper(), font_maly, szerokosc - 100)
        
    calkowita_wysokosc = (len(linie_glowne) * wysokosc_linii)
    if tekst_maly:
        calkowita_wysokosc += 20 + (len(linie_male) * wysokosc_linii_male)

    y_tekstu_poczatkowy = (wys_zdjecia + ((wysokosc - wys_zdjecia) / 2)) - (calkowita_wysokosc / 2) - 20 

    with Pilmoji(canvas) as pilmoji:
        for linia in linie_glowne:
            szer_linii = font_duzy.getlength(linia) if hasattr(font_duzy, 'getlength') else font_duzy.getbbox(linia)[2]
            pilmoji.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_duzy)
            y_tekstu_poczatkowy += wysokosc_linii

        if tekst_maly:
            y_tekstu_poczatkowy += 20
            for linia in linie_male:
                szer_linii = font_maly.getlength(linia) if hasattr(font_maly, 'getlength') else font_maly.getbbox(linia)[2]
                pilmoji.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_maly)
                y_tekstu_poczatkowy += wysokosc_linii_male

        if tekst_stopki:
            tekst_stopki_rozstrzelony = "   ".join(tekst_stopki)
            szer_rozstrzelona = font_stopka.getlength(tekst_stopki_rozstrzelony) if hasattr(font_stopka, 'getlength') else font_stopka.getbbox(tekst_stopki_rozstrzelony)[2]

            if kolor_podkladu:
                kolor_stopki = (235, 235, 235, 255)
            else:
                kolor_stopki = (255, 255, 255, 255) if is_audio else (180, 180, 180, 255)
            pilmoji.text(((szerokosc - szer_rozstrzelona) / 2, wysokosc - 50), tekst_stopki_rozstrzelony, fill=kolor_stopki, font=font_stopka)

    canvas = canvas.convert("RGB") 
    canvas.save(nazwa_wyjsciowa, quality=100)


# ==========================================
# GENERATOR 3: COVER NA FB (NOWOŚĆ)
# ==========================================
def generuj_cover_fb(sciezka_okladki, sciezka_logo, tekst_gora, tekst_dol, nazwa_wyjsciowa, kolor_tla):
    szerokosc, wysokosc = 1640, 624 
    canvas = Image.new("RGBA", (szerokosc, wysokosc), kolor_tla + (255,))
    
    # 1. Wklejanie okładki magazynu (prawa strona)
    if sciezka_okladki and os.path.exists(sciezka_okladki):
        okladka = Image.open(sciezka_okladki).convert("RGBA")
        docelowa_wys = wysokosc - 80
        wspolczynnik = docelowa_wys / okladka.height
        docelowa_szer = int(okladka.width * wspolczynnik)
        okladka = okladka.resize((docelowa_szer, docelowa_wys), Image.Resampling.LANCZOS)
        
        pozycja_x_okladki = szerokosc - docelowa_szer - 100
        pozycja_y_okladki = 40
        canvas.paste(okladka, (pozycja_x_okladki, pozycja_y_okladki))
    else:
        pozycja_x_okladki = szerokosc - 400 # domyślnie gdyby nie było okładki

    # 2. Dodawanie Logo
    y_tekstu = 150
    srodek_lewej_strony = pozycja_x_okladki // 2

    if sciezka_logo and os.path.exists(sciezka_logo):
        logo = Image.open(sciezka_logo).convert("RGBA")
        logo.thumbnail((500, 200), Image.Resampling.LANCZOS)
        poz_logo_x = srodek_lewej_strony - (logo.width // 2)
        canvas.paste(logo, (poz_logo_x, y_tekstu), logo)
        y_tekstu += logo.height + 40
    else:
        y_tekstu += 100

    # 3. Dodawanie tekstów
    try:
        font_gora = ImageFont.truetype("Montserrat-SemiBold.ttf", 45)
        font_dol = ImageFont.truetype("Montserrat-Bold.ttf", 60)
    except Exception:
        return

    jasnosc_tla = (kolor_tla[0] * 299 + kolor_tla[1] * 587 + kolor_tla[2] * 114) / 1000
    kolor_tekstu = (255, 255, 255, 255) if jasnosc_tla < 130 else (30, 30, 30, 255)

    draw = ImageDraw.Draw(canvas)
    
    szer_gora = font_gora.getlength(tekst_gora) if hasattr(font_gora, 'getlength') else font_gora.getbbox(tekst_gora)[2]
    draw.text((srodek_lewej_strony - (szer_gora // 2), y_tekstu), tekst_gora, fill=kolor_tekstu, font=font_gora)
    
    y_tekstu += 65
    
    szer_dol = font_dol.getlength(tekst_dol) if hasattr(font_dol, 'getlength') else font_dol.getbbox(tekst_dol)[2]
    draw.text((srodek_lewej_strony - (szer_dol // 2), y_tekstu), tekst_dol.upper(), fill=kolor_tekstu, font=font_dol)

    canvas = canvas.convert("RGB")
    canvas.save(nazwa_wyjsciowa, quality=100)


# ==========================================
# GENEROWANIE WSZYSTKICH WARIANTÓW (POSTY)
# ==========================================
WARIANTY = {
    "magazyn":       ("magazyn.jpg",       "magazyn", STOPKA_DOMYSLNA, False),
    "split":         ("split.jpg",         "split",   STOPKA_DOMYSLNA, False),
    "magazyn_bez":   ("magazyn_bez.jpg",   "magazyn", "",              False),
    "split_bez":     ("split_bez.jpg",     "split",   "",              False),
    "magazyn_kolor": ("magazyn_kolor.jpg", "magazyn", STOPKA_DOMYSLNA, True),
    "split_kolor":   ("split_kolor.jpg",   "split",   STOPKA_DOMYSLNA, True),
    "magazyn_kolor_bez": ("magazyn_kolor_bez.jpg", "magazyn", "", True),
    "split_kolor_bez":   ("split_kolor_bez.jpg",   "split",   "", True),
}

KARTY = {
    "magazyn":     ("Styl Magazyn",                        "📥 Pobierz Magazyn",                  "fb_magazyn.jpg",                 "Magazyn"),
    "split":       ("Styl Split Screen",                   "📥 Pobierz Split Screen",             "fb_split.jpg",                   "Split Screen"),
    "magazyn_bez": ("Styl Magazyn – bez komentarza",       "📥 Pobierz Magazyn (bez kom.)",       "fb_magazyn_bez_komentarza.jpg",  "Magazyn - bez komentarza"),
    "split_bez":   ("Styl Split Screen – bez komentarza",  "📥 Pobierz Split Screen (bez kom.)",  "fb_split_bez_komentarza.jpg",    "Split Screen - bez komentarza"),
    "magazyn_kolor": ("Magazyn – kolor ze zdjęcia",        "📥 Pobierz Magazyn (kolor)",          "fb_magazyn_kolor.jpg",           "Magazyn - kolor dominujący"),
    "split_kolor":   ("Split Screen – kolor ze zdjęcia",   "📥 Pobierz Split Screen (kolor)",     "fb_split_kolor.jpg",             "Split Screen - kolor dominujący"),
    "magazyn_kolor_bez": ("Magazyn – kolor ze zdjęcia",      "📥 Pobierz Magazyn (kolor, bez kom.)",      "fb_magazyn_kolor_bez_komentarza.jpg", "Magazyn - kolor dominujący - bez komentarza"),
    "split_kolor_bez":   ("Split Screen – kolor ze zdjęcia", "📥 Pobierz Split Screen (kolor, bez kom.)", "fb_split_kolor_bez_komentarza.jpg",   "Split Screen - kolor dominujący - bez komentarza"),
}

def wygeneruj_grafiki(sciezka_zdjecia, sciezka_do_logo, tytul, is_audio, kolor_wymuszony=None):
    gotowe = {}
    if kolor_wymuszony:
        kolor_ze_zdjecia = znormalizuj_kolor_podkladu(kolor_wymuszony)
    else:
        kolor_ze_zdjecia = kolor_podkladu_ze_zdjecia(sciezka_zdjecia)

    for klucz, (plik_roboczy, styl, stopka, kolorowa) in WARIANTY.items():
        generator = generuj_grafike_magazyn if styl == "magazyn" else generuj_grafike_split
        kolor = kolor_ze_zdjecia if kolorowa else None
        generator(sciezka_zdjecia, sciezka_do_logo, tytul, stopka, plik_roboczy, is_audio=is_audio, kolor_podkladu=kolor)
        with open(plik_roboczy, "rb") as f:
            gotowe[klucz] = f.read()
    return gotowe, kolor_ze_zdjecia

# ==========================================
# INTERFEJS STREAMLIT 
# ==========================================
st.set_page_config(page_title="Generator Postów FB", page_icon="🎨", layout="centered")

st.title("🎨 Automatyczny Generator Grafik")
st.write("Wybierz rodzaj grafiki, którą chcesz stworzyć w zakładkach poniżej.")
st.caption(f"wersja {WERSJA_APP}")

pobierz_nowoczesne_czcionki()

if not os.path.exists("logotypy"):
    os.makedirs("logotypy")

OPCJA_BEZ_LOGA = "❌ Bez loga"
dostepne_loga = [f for f in os.listdir("logotypy") if f.endswith(('.png', '.jpg'))]

if dostepne_loga:
    dostepne_loga.sort()
    bd_logo_index = next((i for i, v in enumerate(dostepne_loga) if "budujemydom" in v.lower()), None)
    
    if bd_logo_index is not None:
        bd_logo = dostepne_loga.pop(bd_logo_index)
        dostepne_loga.insert(0, bd_logo)
        dostepne_loga.insert(1, OPCJA_BEZ_LOGA)
    else:
        dostepne_loga.insert(0, OPCJA_BEZ_LOGA)
else:
    dostepne_loga = [OPCJA_BEZ_LOGA]

if 'wygenerowano' not in st.session_state:
    st.session_state.wygenerowano = False


tab1, tab2 = st.tabs(["📲 Posty do artykułu", "🖼️ Cover na Facebooka (Top)"])

# ----------------------------------------------------
# ZAKŁADKA 1: POSTY Z LINKU
# ----------------------------------------------------
with tab1:
    wybrane_logo = st.selectbox("Wybierz markę (logo):", dostepne_loga, key="logo_posty")
    url_input = st.text_input("🔗 Link do artykułu:")
    
    if st.button("🚀 Pobierz i Generuj Grafiki", type="primary"):
        if url_input:
            with st.spinner("Pobieram dane ze strony i renderuję domyślne grafiki..."):
                sciezka_do_logo = None if wybrane_logo == OPCJA_BEZ_LOGA else os.path.join("logotypy", wybrane_logo)
                is_audio_brand = bool(wybrane_logo and wybrane_logo != OPCJA_BEZ_LOGA and "audio" in wybrane_logo.lower())
                
                tytul, zdjecie_tmp = pobierz_dane_z_artykulu(url_input)
                
                if tytul and zdjecie_tmp:
                    st.session_state.sciezka_zdjecia_tmp = zdjecie_tmp
                    st.session_state.aktualny_tytul = tytul
                    st.session_state.sciezka_do_logo = sciezka_do_logo
                    st.session_state.is_audio_brand = is_audio_brand
                    st.session_state.logo_nazwa = wybrane_logo
                    st.session_state.kolor_reczny = None  
                    
                    st.session_state.grafiki, st.session_state.kolor_uzyty = wygeneruj_grafiki(
                        zdjecie_tmp, sciezka_do_logo, tytul, is_audio_brand
                    )
                    st.session_state.wygenerowano = True
                else:
                    st.error("Wystąpił błąd podczas pobierania danych. Sprawdź, czy link jest poprawny.")
        else:
            st.warning("Najpierw wklej link!")

    if st.session_state.get('wygenerowano', False):
        bezpieczny_tytul = st.session_state.get('aktualny_tytul', 'Twojego artykułu')
        st.success(f"Oto Twoje grafiki dla: {bezpieczny_tytul}")
        
        def pokaz_pare(klucze):
            kolumny = st.columns(2)
            for kolumna, klucz in zip(kolumny, klucze):
                podpis, etykieta, nazwa_pliku, nazwa_statystyki = KARTY[klucz]
                with kolumna:
                    st.image(st.session_state.grafiki[klucz], caption=podpis)
                    st.download_button(
                        label=etykieta,
                        data=st.session_state.grafiki[klucz],
                        file_name=nazwa_pliku,
                        mime="image/jpeg",
                        width="stretch",
                        key=f"pobierz_{klucz}",
                        on_click=aktualizuj_licznik,
                        args=(nazwa_statystyki, st.session_state.get('logo_nazwa'))
                    )

        z_komentarzem = st.toggle(
            "Napis „ARTYKUŁ W KOMENTARZU”",
            value=True,
            help="Wyłącz, żeby te same 4 grafiki pokazały się w wersji bez stopki."
        )
        sufiks = "" if z_komentarzem else "_bez"

        st.subheader("🎨 Kolor ze zdjęcia")
        st.caption("Podlewka w kolorze wyliczonym z całego zdjęcia (ważonym powierzchnią). Zdjęcie bez wyraźnej barwy – np. szara łazienka – da ciemny grafit, a nie przypadkowy kolor.")
        pokaz_pare([f"magazyn_kolor{sufiks}", f"split_kolor{sufiks}"])

        kolor_uzyty = st.session_state.get('kolor_uzyty')
        if kolor_uzyty:
            hex_uzyty = "#{:02x}{:02x}{:02x}".format(*kolor_uzyty)
            with st.expander(f"🎚️ Kolor podlewki: {hex_uzyty} – zmień ręcznie"):
                st.caption("Wybrany kolor i tak zostanie przyciemniony do poziomu, przy którym biały napis pozostaje czytelny.")
                nowy_kolor = st.color_picker("Wybierz kolor:", value=hex_uzyty)
                kol_a, kol_b = st.columns(2)

                def przelicz(kolor_wymuszony):
                    st.session_state.kolor_reczny = kolor_wymuszony
                    st.session_state.grafiki, st.session_state.kolor_uzyty = wygeneruj_grafiki(
                        st.session_state.sciezka_zdjecia_tmp,
                        st.session_state.sciezka_do_logo,
                        st.session_state.aktualny_tytul,
                        st.session_state.is_audio_brand,
                        kolor_wymuszony=kolor_wymuszony
                    )

                if kol_a.button("🎨 Zastosuj ten kolor", width="stretch"):
                    with st.spinner("Przeliczam..."):
                        przelicz(tuple(int(nowy_kolor.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)))
                    st.rerun()

                if kol_b.button("↩️ Wróć do koloru ze zdjęcia", width="stretch"):
                    with st.spinner("Przeliczam..."):
                        przelicz(None)
                    st.rerun()

        st.markdown("---")
        st.subheader("⬛ Klasyczne, czarne")
        pokaz_pare([f"magazyn{sufiks}", f"split{sufiks}"])

        st.markdown("---")
        st.subheader("✍️ Chcesz coś poprawić?")
        
        nowy_tytul = st.text_area("Edytuj tytuł (użyj Enter by złamać linię. Wstaw znak '|', by tekst po nim był mniejszym podtytułem):", value=st.session_state.aktualny_tytul, height=100)
        
        if st.button("🔄 Zaktualizuj napisy"):
            with st.spinner("Odświeżam grafiki..."):
                st.session_state.grafiki, st.session_state.kolor_uzyty = wygeneruj_grafiki(
                    st.session_state.sciezka_zdjecia_tmp,
                    st.session_state.sciezka_do_logo,
                    nowy_tytul,
                    st.session_state.is_audio_brand,
                    kolor_wymuszony=st.session_state.get('kolor_reczny')
                )
                st.session_state.aktualny_tytul = nowy_tytul
                st.rerun()

# ----------------------------------------------------
# ZAKŁADKA 2: COVER NA FB
# ----------------------------------------------------
with tab2:
    st.info("💡 Ta zakładka wygeneruje dla Ciebie grafikę o wymiarach 1640x624 px z odpowiednim wyśrodkowaniem tekstu oraz wklejoną okładką po prawej stronie.")
    
    col1, col2 = st.columns(2)
    with col1:
        wybrane_logo_cover = st.selectbox("Wybierz logo:", dostepne_loga, key="logo_cover")
        wgrana_okladka = st.file_uploader("Wgraj plik okładki (JPG/PNG):", type=['jpg', 'jpeg', 'png'])
    with col2:
        tekst_gora = st.text_input("Tekst górny:", value="Najnowsze wydanie już dostępne")
        tekst_dol = st.text_input("Tekst dolny (np. data):", value="PAŹDZIERNIK 2026")
        kolor_reczny = st.color_picker("Wymuś kolor tła (zostaw domyślny, aby pobrać z okładki):", value="#E5D1D4")

    if st.button("🎨 Generuj Cover", type="primary"):
        if wgrana_okladka is not None:
            with st.spinner("Przetwarzam cover..."):
                sciezka_okladki = "tymczasowa_okladka.jpg"
                with open(sciezka_okladki, "wb") as f:
                    f.write(wgrana_okladka.getbuffer())
                
                sciezka_do_logo_cover = None if wybrane_logo_cover == OPCJA_BEZ_LOGA else os.path.join("logotypy", wybrane_logo_cover)
                
                # Obliczanie koloru tła 
                if kolor_reczny == "#E5D1D4": 
                    kolor_tla = kolor_podkladu_ze_zdjecia(sciezka_okladki, maks_nasycenie=0.3) 
                    if not kolor_tla:
                        kolor_tla = (245, 235, 240) # Fallback, np. przy problemach z otwarciem obrazka
                else:
                    kolor_tla = tuple(int(kolor_reczny.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

                nazwa_covera = "wygenerowany_cover.jpg"
                generuj_cover_fb(sciezka_okladki, sciezka_do_logo_cover, tekst_gora, tekst_dol, nazwa_covera, kolor_tla)
                
                st.success("Cover wygenerowany pomyślnie!")
                st.image(nazwa_covera, use_container_width=True)
                
                with open(nazwa_covera, "rb") as file:
                    st.download_button(
                        label="📥 Pobierz Cover",
                        data=file,
                        file_name="Cover_FB.jpg",
                        mime="image/jpeg"
                    )
        else:
            st.warning("Najpierw wgraj plik z okładką!")
