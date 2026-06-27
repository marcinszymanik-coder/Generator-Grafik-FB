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
import json
import gspread 

# NOWOŚĆ: Biblioteka do renderowania emotikon na obrazkach!
from pilmoji import Pilmoji 

# Wyłączenie weryfikacji certyfikatów SSL
ssl._create_default_https_context = ssl._create_unverified_context

# ==========================================
# FUNKCJA ANALITYCZNA (Zapis do Arkuszy Google w tle)
# ==========================================
def aktualizuj_licznik(styl_grafiki, uzyte_logo):
    nazwa_marki = uzyte_logo if uzyte_logo else "BRAK LOGA"
    teraz = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
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
# GENERATOR 1: MAGAZYN 
# ==========================================
def generuj_grafike_magazyn(sciezka_zdjecia, sciezka_logo, tekst_glowny, tekst_stopki, nazwa_wyjsciowa, is_audio=False):
    szerokosc, wysokosc = 1080, 1080
    canvas = Image.new("RGBA", (szerokosc, wysokosc), (0, 0, 0, 255))
    
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
        draw_grad.line([(0, y), (szerokosc, y)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, gradient)
    
    if sciezka_logo and os.path.exists(sciezka_logo):
        logo = Image.open(sciezka_logo).convert("RGBA")
        logo.thumbnail((240, 240), Image.Resampling.LANCZOS)
        canvas.paste(logo, (szerokosc - logo.width - 40, 40), logo)

    rozmiar_fontu = 46 if len(tekst_glowny) > 50 else 55
    try:
        font_duzy = ImageFont.truetype("Montserrat-Bold.ttf", rozmiar_fontu)
        font_stopka = ImageFont.truetype("Montserrat-SemiBold.ttf", 24)
    except Exception: return

    kolor_biel = (255, 255, 255, 255)
    linie_glowne = zawin_tekst(tekst_glowny.upper(), font_duzy, szerokosc - 140)
    wysokosc_linii = rozmiar_fontu + 16
    y_tekstu_poczatkowy = (wysokosc - 280) - ((len(linie_glowne) * wysokosc_linii) / 2)

    # NOWOŚĆ: Używamy Pilmoji zamiast standardowego draw, aby obsłużyć emoji
    with Pilmoji(canvas) as pilmoji:
        for linia in linie_glowne:
            szer_linii = font_duzy.getlength(linia) if hasattr(font_duzy, 'getlength') else font_duzy.getbbox(linia)[2]
            pilmoji.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_duzy)
            y_tekstu_poczatkowy += wysokosc_linii

        tekst_stopki_rozstrzelony = "   ".join(tekst_stopki) 
        szer_rozstrzelona = font_stopka.getlength(tekst_stopki_rozstrzelony) if hasattr(font_stopka, 'getlength') else font_stopka.getbbox(tekst_stopki_rozstrzelony)[2]
        pilmoji.text(((szerokosc - szer_rozstrzelona) / 2, wysokosc - 60), tekst_stopki_rozstrzelony, fill=kolor_biel, font=font_stopka)

    canvas = canvas.convert("RGB") 
    canvas.save(nazwa_wyjsciowa, quality=100)

# ==========================================
# GENERATOR 2: SPLIT SCREEN 
# ==========================================
def generuj_grafike_split(sciezka_zdjecia, sciezka_logo, tekst_glowny, tekst_stopki, nazwa_wyjsciowa, is_audio=False):
    szerokosc, wysokosc = 1080, 1080
    wys_zdjecia = int(szerokosc * 9 / 16)
    
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

    rozmiar_fontu = 48 if len(tekst_glowny) > 50 else 56
    try:
        font_duzy = ImageFont.truetype("Montserrat-Bold.ttf", rozmiar_fontu)
        font_stopka = ImageFont.truetype("Montserrat-SemiBold.ttf", 22)
    except Exception: return

    kolor_biel = (255, 255, 255, 255)
    linie_glowne = zawin_tekst(tekst_glowny.upper(), font_duzy, szerokosc - 100)
    wysokosc_linii = rozmiar_fontu + 15
    y_tekstu_poczatkowy = (wys_zdjecia + ((wysokosc - wys_zdjecia) / 2)) - ((len(linie_glowne) * wysokosc_linii) / 2) - 20 

    # NOWOŚĆ: Używamy Pilmoji zamiast standardowego draw, aby obsłużyć emoji
    with Pilmoji(canvas) as pilmoji:
        for linia in linie_glowne:
            szer_linii = font_duzy.getlength(linia) if hasattr(font_duzy, 'getlength') else font_duzy.getbbox(linia)[2]
            pilmoji.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_duzy)
            y_tekstu_poczatkowy += wysokosc_linii

        tekst_stopki_rozstrzelony = "   ".join(tekst_stopki) 
        szer_rozstrzelona = font_stopka.getlength(tekst_stopki_rozstrzelony) if hasattr(font_stopka, 'getlength') else font_stopka.getbbox(tekst_stopki_rozstrzelony)[2]
        
        kolor_stopki = (255, 255, 255, 255) if is_audio else (180, 180, 180, 255)
        pilmoji.text(((szerokosc - szer_rozstrzelona) / 2, wysokosc - 50), tekst_stopki_rozstrzelony, fill=kolor_stopki, font=font_stopka) 

    canvas = canvas.convert("RGB") 
    canvas.save(nazwa_wyjsciowa, quality=100)

# ==========================================
# INTERFEJS STREAMLIT 
# ==========================================
st.set_page_config(page_title="Generator Postów FB", page_icon="🎨", layout="centered")

st.title("🎨 Automatyczny Generator Grafik")
st.write("Wklej link, zobacz gotowe grafiki, a potem edytuj tekst, dodawaj emotikony 🔥 i pobieraj!")

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

with st.container():
    wybrane_logo = st.selectbox("Wybierz markę (logo):", dostepne_loga)
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
                    
                    generuj_grafike_magazyn(zdjecie_tmp, sciezka_do_logo, tytul, "ARTYKUŁ W KOMENTARZU", "magazyn.jpg", is_audio=is_audio_brand)
                    generuj_grafike_split(zdjecie_tmp, sciezka_do_logo, tytul, "ARTYKUŁ W KOMENTARZU", "split.jpg", is_audio=is_audio_brand)
                    
                    with open("magazyn.jpg", "rb") as f:
                        st.session_state.magazyn_bytes = f.read()
                    with open("split.jpg", "rb") as f:
                        st.session_state.split_bytes = f.read()
                        
                    st.session_state.wygenerowano = True
                else:
                    st.error("Wystąpił błąd podczas pobierania danych. Sprawdź, czy link jest poprawny.")
        else:
            st.warning("Najpierw wklej link!")

if st.session_state.get('wygenerowano', False):
    bezpieczny_tytul = st.session_state.get('aktualny_tytul', 'Twojego artykułu')
    st.success(f"Oto Twoje grafiki dla: {bezpieczny_tytul}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.image(st.session_state.magazyn_bytes, caption="Styl Magazyn")
        st.download_button(
            label="📥 Pobierz Magazyn", 
            data=st.session_state.magazyn_bytes, 
            file_name="fb_magazyn.jpg", 
            mime="image/jpeg", 
            width="stretch",
            on_click=aktualizuj_licznik,
            args=("Magazyn", st.session_state.get('logo_nazwa'))
        )
            
    with col2:
        st.image(st.session_state.split_bytes, caption="Styl Split Screen")
        st.download_button(
            label="📥 Pobierz Split Screen", 
            data=st.session_state.split_bytes, 
            file_name="fb_split.jpg", 
            mime="image/jpeg", 
            width="stretch",
            on_click=aktualizuj_licznik,
            args=("Split Screen", st.session_state.get('logo_nazwa'))
        )
        
    st.markdown("---")
    st.subheader("✍️ Chcesz coś poprawić?")
    
    nowy_tytul = st.text_area("Edytuj tytuł i wygeneruj ponownie (użyj klawisza Enter, by wymusić przełamanie linii):", value=st.session_state.aktualny_tytul, height=100)
    
    if st.button("🔄 Zaktualizuj napisy"):
        with st.spinner("Odświeżam grafiki..."):
            generuj_grafike_magazyn(
                st.session_state.sciezka_zdjecia_tmp, 
                st.session_state.sciezka_do_logo, 
                nowy_tytul, 
                "ARTYKUŁ W KOMENTARZU", 
                "magazyn.jpg", 
                is_audio=st.session_state.is_audio_brand
            )
            generuj_grafike_split(
                st.session_state.sciezka_zdjecia_tmp, 
                st.session_state.sciezka_do_logo, 
                nowy_tytul, 
                "ARTYKUŁ W KOMENTARZU", 
                "split.jpg", 
                is_audio=st.session_state.is_audio_brand
            )
            
            with open("magazyn.jpg", "rb") as f:
                st.session_state.magazyn_bytes = f.read()
            with open("split.jpg", "rb") as f:
                st.session_state.split_bytes = f.read()
            
            st.session_state.aktualny_tytul = nowy_tytul
            st.rerun()
