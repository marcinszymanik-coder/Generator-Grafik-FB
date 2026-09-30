# ==========================================
# GENERATOR 3: COVER NA FB (NOWOŚĆ Z CIENIEM I WIĘKSZYM LOGO)
# ==========================================
def generuj_cover_fb(sciezka_okladki, sciezka_logo, tekst_gora, tekst_dol, nazwa_wyjsciowa, kolor_tla):
    szerokosc, wysokosc = 1640, 624 
    canvas = Image.new("RGBA", (szerokosc, wysokosc), kolor_tla + (255,))
    
    # --- 1. Obsługa okładki z CIENIEM ---
    pozycja_x_okladki = szerokosc - 400 
    if sciezka_okladki and os.path.exists(sciezka_okladki):
        okladka = Image.open(sciezka_okladki).convert("RGBA")
        
        docelowa_wys = wysokosc - 80 
        wspolczynnik = docelowa_wys / okladka.height
        docelowa_szer = int(okladka.width * wspolczynnik)
        okladka = okladka.resize((docelowa_szer, docelowa_wys), Image.Resampling.LANCZOS)
        
        pozycja_x_okladki = szerokosc - docelowa_szer - 150 
        pozycja_y_okladki = (wysokosc - docelowa_wys) // 2

        # Generowanie cienia
        cien = Image.new('RGBA', (docelowa_szer, docelowa_wys), (0, 0, 0, 255))
        warstwa_cienia = Image.new('RGBA', (szerokosc, wysokosc), (0, 0, 0, 0))
        przesuniecie_cienia_x = 20
        przesuniecie_cienia_y = 20
        warstwa_cienia.paste(cien, (pozycja_x_okladki + przesuniecie_cienia_x, pozycja_y_okladki + przesuniecie_cienia_y))
        
        warstwa_cienia = warstwa_cienia.filter(ImageFilter.GaussianBlur(25))
        dane_cienia = warstwa_cienia.getdata()
        nowe_dane_cienia = []
        for item in dane_cienia:
            nowe_dane_cienia.append((item[0], item[1], item[2], int(item[3] * 0.4)))
        warstwa_cienia.putdata(nowe_dane_cienia)

        canvas = Image.alpha_composite(canvas, warstwa_cienia)
        canvas.paste(okladka, (pozycja_x_okladki, pozycja_y_okladki), okladka)


    # --- 2. Inicjalizacja czcionek ---
    try:
        font_gora = ImageFont.truetype("Montserrat-SemiBold.ttf", 40)
        font_dol = ImageFont.truetype("Montserrat-Bold.ttf", 48)
    except Exception:
        return

    # --- 3. Obliczanie wysokości bloku (Logo + Teksty) i pozycjonowanie ---
    wysokosc_bloku = 0
    logo = None
    if sciezka_logo and os.path.exists(sciezka_logo):
        logo = Image.open(sciezka_logo).convert("RGBA")
        # ZWIĘKSZONE LOGO: z (500, 180) na (750, 260)
        logo.thumbnail((750, 260), Image.Resampling.LANCZOS)
        # Zwiększony odstęp pod logiem
        wysokosc_bloku += logo.height + 25 
    
    wysokosc_bloku += 40 + 48 + 15 
    y_tekstu = (wysokosc - wysokosc_bloku) // 2

    # Prawa krawędź do wyrównania (odsunięta o 50px w lewo od okładki)
    prawa_krawedz_tekstu = pozycja_x_okladki - 50

    kolor_tekstu = (30, 30, 30, 255) 
    draw = ImageDraw.Draw(canvas)

    if logo:
        poz_logo_x = prawa_krawedz_tekstu - logo.width
        canvas.paste(logo, (poz_logo_x, y_tekstu), logo)
        y_tekstu += logo.height + 25

    szer_gora = font_gora.getlength(tekst_gora) if hasattr(font_gora, 'getlength') else font_gora.getbbox(tekst_gora)[2]
    draw.text((prawa_krawedz_tekstu - szer_gora, y_tekstu), tekst_gora, fill=kolor_tekstu, font=font_gora)
    
    y_tekstu += 60 
    
    szer_dol = font_dol.getlength(tekst_dol) if hasattr(font_dol, 'getlength') else font_dol.getbbox(tekst_dol)[2]
    draw.text((prawa_krawedz_tekstu - szer_dol, y_tekstu), tekst_dol.upper(), fill=kolor_tekstu, font=font_dol)

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
    st.info("💡 Ta zakładka wygeneruje dla Ciebie grafikę o wymiarach 1640x624 px z prawostronnym wyrównaniem tekstu i wklejoną okładką z cieniem po prawej stronie.")
    
    cnw_logo_index = next((i for i, v in enumerate(dostepne_loga) if "czas" in v.lower() or "wnetrze" in v.lower()), 0)
    
    col1, col2 = st.columns(2)
    with col1:
        wybrane_logo_cover = st.selectbox("Wybierz logo:", dostepne_loga, index=cnw_logo_index, key="logo_cover")
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
                
                if kolor_reczny == "#E5D1D4": 
                    kolor_tla = kolor_pastelowy_ze_zdjecia(sciezka_okladki) 
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
