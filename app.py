import os
import urllib.request
import ssl
import requests
from io import BytesIO
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import streamlit as st

# Wyłączenie weryfikacji certyfikatów SSL
ssl._create_default_https_context = ssl._create_unverified_context

# ==========================================
# FUNKCJE BAZOWE (Logika pozostaje ta sama)
# ==========================================
def wyczysc_tytul_portalu(tytul_surowy):
    smieci = ["- budujemydom.pl", "- budujemydom", "| budujemydom.pl", "- Budujemy Dom", "- BudujemyDom"]
    tytul_czysty = tytul_surowy.strip()
    for s in smieci:
        if tytul_czysty.lower().endswith(s.lower()):
            tytul_czysty = tytul_czysty[:-len(s)].strip()
    return tytul_czysty.strip("- – |").strip()

def pobierz_dane_z_artykulu(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tytuł
        tytul = "BRAK TYTUŁU"
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            tytul = wyczysc_tytul_portalu(og_title.get('content'))
        else:
            if soup.title:
                tytul = wyczysc_tytul_portalu(soup.title.string)

        # Zdjęcie
        img_url = None
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
        if not najlepszy_strzal:
            for link in linki_zdjec:
                if "/i/" in link and ("budujemydompl" in link or "klimatyzacja" in link or "garderoba" in link):
                    najlepszy_strzal = link
                    break
        if najlepszy_strzal:
            img_url = urljoin(url, najlepszy_strzal)

        nazwa_zdjecia = None
        if img_url:
            img_data = requests.get(img_url, headers=headers).content
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
    slowa = tekst.split()
    linie = []
    aktualna_linia = []
    for slowo in slowa:
        linia_testowa = " ".join(aktualna_linia + [slowo])
        szerokosc = font.getlength(linia_testowa) if hasattr(font, 'getlength') else font.getbbox(linia_testowa)[2]
        if szerokosc <= max_szerokosc:
            aktualna_linia.append(slowo)
        else:
            linie.append(" ".join(aktualna_linia))
            aktualna_linia = [slowo]
    if aktualna_linia:
        linie.append(" ".join(aktualna_linia))
    return linie

def generuj_grafike_magazyn(sciezka_zdjecia, sciezka_logo, tekst_glowny, tekst_stopki, nazwa_wyjsciowa):
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
    for y in range(start_grad, wysokosc):
        alpha = int(235 * ((y - start_grad) / (wysokosc - start_grad)))
        draw_grad.line([(0, y), (szerokosc, y)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, gradient)
    draw = ImageDraw.Draw(canvas)

    if sciezka_logo and os.path.exists(sciezka_logo):
        logo = Image.open(sciezka_logo).convert("RGBA")
        logo.thumbnail((240, 240), Image.Resampling.LANCZOS)
        x_logo = szerokosc - logo.width - 40
        y_logo = 40
        canvas.paste(logo, (x_logo, y_logo), logo)

    rozmiar_fontu = 46 if len(tekst_glowny) > 50 else 55
    try:
        font_duzy = ImageFont.truetype("Montserrat-Bold.ttf", rozmiar_fontu)
        font_stopka = ImageFont.truetype("Montserrat-SemiBold.ttf", 24)
    except Exception: return

    kolor_biel = (255, 255, 255, 255)
    linie_glowne = zawin_tekst(tekst_glowny.upper(), font_duzy, szerokosc - 140)
    wysokosc_linii = rozmiar_fontu + 16
    y_tekstu_poczatkowy = (wysokosc - 280) - ((len(linie_glowne) * wysokosc_linii) / 2)

    for linia in linie_glowne:
        szer_linii = font_duzy.getlength(linia) if hasattr(font_duzy, 'getlength') else font_duzy.getbbox(linia)[2]
        draw.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_duzy)
        y_tekstu_poczatkowy += wysokosc_linii

    tekst_stopki_rozstrzelony = "   ".join(tekst_stopki) 
    szer_rozstrzelona = font_stopka.getlength(tekst_stopki_rozstrzelony) if hasattr(font_stopka, 'getlength') else font_stopka.getbbox(tekst_stopki_rozstrzelony)[2]
    draw.text(((szerokosc - szer_rozstrzelona) / 2, wysokosc - 60), tekst_stopki_rozstrzelony, fill=kolor_biel, font=font_stopka)

    canvas = canvas.convert("RGB") 
    canvas.save(nazwa_wyjsciowa, quality=100)

def generuj_grafike_split(sciezka_zdjecia, sciezka_logo, tekst_glowny, tekst_stopki, nazwa_wyjsciowa):
    szerokosc, wysokosc = 1080, 1080
    wys_zdjecia = int(szerokosc * 9 / 16)
    canvas = Image.new("RGBA", (szerokosc, wysokosc), (25, 30, 35))
    
    if sciezka_zdjecia and os.path.exists(sciezka_zdjecia):
        img = Image.open(sciezka_zdjecia).convert("RGBA")
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

    for linia in linie_glowne:
        szer_linii = font_duzy.getlength(linia) if hasattr(font_duzy, 'getlength') else font_duzy.getbbox(linia)[2]
        draw.text(((szerokosc - szer_linii) / 2, y_tekstu_poczatkowy), linia, fill=kolor_biel, font=font_duzy)
        y_tekstu_poczatkowy += wysokosc_linii

    tekst_stopki_rozstrzelony = "   ".join(tekst_stopki) 
    szer_rozstrzelona = font_stopka.getlength(tekst_stopki_rozstrzelony) if hasattr(font_stopka, 'getlength') else font_stopka.getbbox(tekst_stopki_rozstrzelony)[2]
    draw.text(((szerokosc - szer_rozstrzelona) / 2, wysokosc - 50), tekst_stopki_rozstrzelony, fill=(180, 180, 180, 255), font=font_stopka) 

    canvas = canvas.convert("RGB") 
    canvas.save(nazwa_wyjsciowa, quality=100)

# ==========================================
# INTERFEJS STREAMLIT
# ==========================================
st.set_page_config(page_title="Generator Postów FB", page_icon="🎨", layout="centered")

st.title("🎨 Automatyczny Generator Grafik")
st.write("Wklej link do artykułu, wybierz logo i pobierz gotowe grafiki na Facebooka.")

# Pobieranie czcionek przy starcie aplikacji
pobierz_nowoczesne_czcionki()

# Skanowanie folderu "logotypy"
if not os.path.exists("logotypy"):
    os.makedirs("logotypy")
dostepne_loga = [f for f in os.listdir("logotypy") if f.endswith(('.png', '.jpg'))]

# Formularz UI
with st.container():
    if not dostepne_loga:
        st.warning("⚠️ Folder 'logotypy' jest pusty. Dodaj pliki .png przed wdrożeniem.")
        wybrane_logo = None
    else:
        wybrane_logo = st.selectbox("Wybierz markę (logo):", dostepne_loga)
    
    url_input = st.text_input("🔗 Link do artykułu:")
    
    if st.button("🚀 Generuj Grafiki", type="primary"):
        if url_input:
            with st.spinner("Pobieram dane ze strony i renderuję obrazy... To zajmie kilka sekund."):
                sciezka_do_logo = os.path.join("logotypy", wybrane_logo) if wybrane_logo else None
                
                tytul, zdjecie_tmp = pobierz_dane_z_artykulu(url_input)
                
                if tytul and zdjecie_tmp:
                    # Generowanie
                    generuj_grafike_magazyn(zdjecie_tmp, sciezka_do_logo, tytul, "ARTYKUŁ W KOMENTARZU", "magazyn.jpg")
                    generuj_grafike_split(zdjecie_tmp, sciezka_do_logo, tytul, "ARTYKUŁ W KOMENTARZU", "split.jpg")
                    
                    st.success(f"Udało się! Tytuł: {tytul}")
                    
                    # Wyświetlanie i przyciski pobierania
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.image("magazyn.jpg", caption="Styl Magazyn", use_column_width=True)
                        with open("magazyn.jpg", "rb") as file:
                            st.download_button(label="📥 Pobierz Magazyn", data=file, file_name="fb_magazyn.jpg", mime="image/jpeg", use_container_width=True)
                            
                    with col2:
                        st.image("split.jpg", caption="Styl Split Screen", use_column_width=True)
                        with open("split.jpg", "rb") as file:
                            st.download_button(label="📥 Pobierz Split Screen", data=file, file_name="fb_split.jpg", mime="image/jpeg", use_container_width=True)
                    
                    # Sprzątanie
                    if os.path.exists(zdjecie_tmp):
                        os.remove(zdjecie_tmp)
                else:
                    st.error("Wystąpił błąd podczas pobierania danych z tego linku.")
        else:
            st.warning("Wpisz link przed kliknięciem przycisku!")