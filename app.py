import time
import streamlit as st
import sqlite3
import pandas as pd
import requests
import json
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode
from streamlit_mic_recorder import speech_to_text
from google import genai
from google.genai import types

# --- 1. INICJALIZACJA GEMINI AI ---
GEMINI_KEY = st.secrets["GEMINI_KEY"]
client = genai.Client(api_key=GEMINI_KEY)

def przelicz_glos_na_makro(tekst_glosowy):
    prompt = f"""
    Tekst: "{tekst_glosowy}".
    Przelicz makro i zwróć TYLKO JSON:
    {{
        "nazwa": "Krótka nazwa posiłku",
        "kcal": 0,
        "bialko": 0,
        "tluszcz": 0,
        "wegle": 0
    }}
    """
    modele = ['gemini-1.5-flash', 'gemini-2.5-flash']
    
    for model_name in modele:
        for proba in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                if "503" in str(e):
                    time.sleep(1)
                    continue
                break
                
    st.error("Serwery AI są przeciążone. Spróbuj ponownie.")
    return None

# --- 2. BAZA DANYCH (POSIŁKI I PROFILE OSOBNE DLA KAŻDEGO) ---
def init_db():
    conn = sqlite3.connect('dziennik_zywieniowy.db')
    c = conn.cursor()
    
    # Tabela posiłków
    c.execute('''
        CREATE TABLE IF NOT EXISTS posilki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            osoba TEXT,
            dzien TEXT,
            typ_posilku TEXT,
            opis TEXT,
            kcal REAL,
            bialko REAL,
            tluszcz REAL,
            wegle REAL
        )
    ''')
    
    # Tabela z profilami użytkowników (Waga, Wzrost, BMI, Cel Kcal)
    c.execute('''
        CREATE TABLE IF NOT EXISTS profile (
            osoba TEXT PRIMARY KEY,
            waga REAL,
            wzrost REAL,
            wiek INTEGER,
            plec TEXT,
            aktywnosc REAL,
            target_kcal REAL
        )
    ''')
    conn.commit()
    conn.close()

def pobierz_profil(osoba):
    conn = sqlite3.connect('dziennik_zywieniowy.db')
    c = conn.cursor()
    c.execute("SELECT waga, wzrost, wiek, plec, aktywnosc, target_kcal FROM profile WHERE osoba = ?", (osoba,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "waga": row[0], "wzrost": row[1], "wiek": row[2],
            "plec": row[3], "aktywnosc": row[4], "target_kcal": row[5]
        }
    else:
        # Domyślna płeć w zależności od imienia
        domyslna_plec = "Kobieta" if osoba in ["Justyna", "Mama"] else "Mężczyzna"
        return {"waga": 70.0, "wzrost": 170.0, "wiek": 30, "plec": domyslna_plec, "aktywnosc": 1.4, "target_kcal": 2000.0}

def zapisz_profil(osoba, waga, wzrost, wiek, plec, aktywnosc, target_kcal):
    conn = sqlite3.connect('dziennik_zywieniowy.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO profile (osoba, waga, wzrost, wiek, plec, aktywnosc, target_kcal)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(osoba) DO UPDATE SET
            waga=excluded.waga,
            wzrost=excluded.wzrost,
            wiek=excluded.wiek,
            plec=excluded.plec,
            aktywnosc=excluded.aktywnosc,
            target_kcal=excluded.target_kcal
    ''', (osoba, waga, wzrost, wiek, plec, aktywnosc, target_kcal))
    conn.commit()
    conn.close()

def dodaj_posilek(osoba, dzien, typ_posilku, opis, kcal, bialko, tluszcz, wegle):
    conn = sqlite3.connect('dziennik_zywieniowy.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO posilki (osoba, dzien, typ_posilku, opis, kcal, bialko, tluszcz, wegle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (osoba, dzien, typ_posilku, opis, kcal, bialko, tluszcz, wegle))
    conn.commit()
    conn.close()

init_db()

# --- 3. INTERFEJS STRONY I SEKCJA PROFILE ---
st.title("🥗 Dziennik Żywieniowy & AI")

st.sidebar.header("👤 Profil Użytkownika")
wybrana_osoba = st.sidebar.selectbox("Wybierz profil:", ["Janusz", "Justyna", "Mama"])
wybrany_dzien = st.sidebar.date_input("Dzień:", datetime.now())

# Wczytanie zapisanych danych z bazy dla wybranej osoby
dane_p = pobierz_profil(wybrana_osoba)

with st.sidebar.expander(f"⚙️ Ustawienia kalkulatora ({wybrana_osoba})"):
    with st.form("form_profil"):
        waga_in = st.number_input("Waga (kg)", value=float(dane_p["waga"]), step=0.5)
        wzrost_in = st.number_input("Wzrost (cm)", value=float(dane_p["wzrost"]), step=1.0)
        wiek_in = st.number_input("Wiek", value=int(dane_p["wiek"]), step=1)
        plec_in = st.selectbox("Płeć", ["Mężczyzna", "Kobieta"], index=0 if dane_p["plec"] == "Mężczyzna" else 1)
        
        akt_opcje = {
            "Siedzący tryb życia (praca biurowa)": 1.2,
            "Umiarkowana aktywność (trening 2-3 razy/tydz.)": 1.4,
            "Duża aktywność (praca fizyczna / trening codziennie)": 1.6
        }
        
        # Znalezienie zapisanego indeksu aktywności
        default_akt_idx = 1
        for idx, val in enumerate(akt_opcje.values()):
            if val == dane_p["aktywnosc"]:
                default_akt_idx = idx
                
        akt_label = st.selectbox("Poziom aktywności", list(akt_opcje.keys()), index=default_akt_idx)
        akt_val = akt_opcje[akt_label]
        
        submit_profil = st.form_submit_button("💾 Zapisz profil")
        
        if submit_profil:
            # Obliczenie zapotrzebowania BMR i TDEE
            bmr = (10 * waga_in) + (6.25 * wzrost_in) - (5 * wiek_in) + (5 if plec_in == "Mężczyzna" else -161)
            target_kcal = bmr * akt_val
            
            zapisz_profil(wybrana_osoba, waga_in, wzrost_in, wiek_in, plec_in, akt_val, target_kcal)
            st.sidebar.success(f"Zapisano dane dla: {wybrana_osoba}!")
            st.rerun()

# Wyliczenie aktualnego BMI i Kcal dla wybranej osoby
bmi = dane_p["waga"] / ((dane_p["wzrost"] / 100) ** 2)
target_kcal = dane_p["target_kcal"]

st.sidebar.markdown(f"**BMI:** `{bmi:.1f}`")
st.sidebar.markdown(f"**Cel dzienny:** `{target_kcal:.0f} kcal`")

st.divider()

# --- 4. DODAWANIE POSIŁKU (GŁOS / TEKST) ---
st.subheader(f"🎙️ Dodaj posiłek dla: {wybrana_osoba}")
tekst_glosowy = speech_to_text(language='pl', start_prompt="🔴 Dotknij i mów", stop_prompt="⏹️ Zakończ", key='speech')

if tekst_glosowy:
    st.info(f"Rozpoznano: {tekst_glosowy}")
    with st.spinner("Przeliczanie kalorii przez AI..."):
        wynik = przelicz_glos_na_makro(tekst_glosowy)
        if wynik:
            dodaj_posilek(
                wybrana_osoba,
                wybrany_dzien.strftime("%Y-%m-%d"),
                "Posiłek",
                wynik.get("nazwa", tekst_glosowy),
                wynik.get("kcal", 0),
                wynik.get("bialko", 0),
                wynik.get("tluszcz", 0),
                wynik.get("wegle", 0)
            )
            st.success(f"Dodano dla {wybrana_osoba}: {wynik.get('nazwa')} ({wynik.get('kcal')} kcal)")
            st.rerun()

st.divider()

# --- 5. DZIENNIK I PODSUMOWANIE DZIAŁANIA ---
st.subheader(f"📊 Dziennik: {wybrana_osoba} ({wybrany_dzien})")

conn = sqlite3.connect('dziennik_zywieniowy.db')
df = pd.read_sql_query("SELECT typ_posilku, opis, kcal, bialko, tluszcz, wegle FROM posilki WHERE osoba = ? AND dzien = ?", 
                       conn, params=(wybrana_osoba, wybrany_dzien.strftime("%Y-%m-%d")))
conn.close()

zjedzone_kcal = df['kcal'].sum() if not df.empty else 0
zostalo_kcal = target_kcal - zjedzone_kcal

st.progress(min(max(zjedzone_kcal / target_kcal, 0.0), 1.0))
st.write(f"Zjedzono: **{zjedzone_kcal:.0f}** / **{target_kcal:.0f} kcal** (Zostało: **{zostalo_kcal:.0f} kcal**)")

if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.info("Brak posiłków zapisanych na ten dzień.")

st.divider()

# --- 6. PROPOZYCJE DAŃ ZE ZDJĘCIAMI ---
st.subheader("🥪 Pomysł na posiłek")

if zostalo_kcal > 0:
    st.write(f"💡 Zostało Ci jeszcze **{zostalo_kcal:.0f} kcal**. Oto propozycja dania dla Ciebie:")
    
    if zostalo_kcal < 250:
        nazwa = "Jogurt naturalny z garścią borówek"
        kcal_str = "~150 kcal | Białko: 10g | Tłuszcz: 4g"
        skladniki = "150g jogurtu naturalnego/greckiego skyr, 50g świeżych borówek lub malin"
        przepis = "Wymieszaj jogurt z owocami. Możesz posypać szczyptą cynamonu."
        foto_url = "https://images.unsplash.com/photo-1488477181946-6428a0291777"
    elif zostalo_kcal < 500:
        nazwa = "Tosty z serem, szynką i warzywami"
        kcal_str = "~450 kcal | Białko: 22g | Tłuszcz: 18g"
        skladniki = "2 kromki chleba tostowego, 2 plastry sera, 2 plastry szynki, pomidor"
        przepis = "Złóż tosty z serem i szynką, zapiecz w opiekaczu. Podawaj z warzywami."
        foto_url = "https://images.unsplash.com/photo-1528735602780-2552fd46c7af"
    else:
        nazwa = "Kurczak z ryżem i warzywami na parze"
        kcal_str = "~650 kcal | Białko: 45g | Tłuszcz: 12g"
        skladniki = "150g piersi z kurczaka, 80g ryżu basmati, mix ulubionych warzyw"
        przepis = "Ugotuj ryż. Kurczaka usmaż na odrobinie oliwy i podawaj z ugotowanymi warzywami."
        foto_url = "https://images.unsplash.com/photo-1546069901-ba9599a7e63c"

    col_img, col_txt = st.columns([1, 2])
    
    with col_img:
        st.image(foto_url, use_container_width=True)
            
    with col_txt:
        st.markdown(f"### {nazwa}")
        st.write(f"**Kaloryczność:** {kcal_str}")
        st.write(f"**Składniki:** {skladniki}")
        st.write(f"**Przygotowanie:** {przepis}")
else:
    st.warning("Przekroczyłeś dzisiejszy limit kalorii! Odpocznij i pij dużo wody 💧")
