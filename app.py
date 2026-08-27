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
    Przeanalizuj wypowiedź użytkownika o zjedzonym posiłku: "{tekst_glosowy}".
    Rozpoznaj składniki, oszacuj ich wagę oraz wylicz wartości odżywcze.
    Zwróć wynik WYŁĄCZNIE jako czysty JSON w tym formacie:
    {{
        "nazwa": "Nazwa posiłku",
        "kcal": 0,
        "bialko": 0,
        "tluszcz": 0,
        "wegle": 0
    }}
    """
    modele = ['gemini-3.6-flash', 'gemini-2.5-flash']

    for model_name in modele:
        for proba in range(2): # próbuje 2 razy dla każdego modelu
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
                    time.sleep(1) # odczekaj sekundę przed ponowną próbą
                    continue
                break

    st.error("Serwery AI są przeciążone. Spróbuj kliknąć nagrywanie jeszcze raz za chwilę.")
    return None

# --- 2. FUNKCJA POBIERANIA MAKRO Z KODU KRESKOWEGO ---
def pobierz_dane_z_kodu(kod_kreskowy):
    kod_clean = str(kod_kreskowy).strip()
    url = f"https://world.openfoodfacts.org/api/v0/product/{kod_clean}.json"
    headers = {'User-Agent': 'RodzinnaDietaApp - Web - Version 1.0'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == 1:
                product = data.get("product", {})
                nutriments = product.get("nutriments", {})
                nazwa = (product.get("product_name_pl") or product.get("product_name") or "Nieznany produkt")
                kcal = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal_value") or 0
                bialko = nutriments.get("proteins_100g") or nutriments.get("proteins_value") or 0
                tluszcz = nutriments.get("fat_100g") or nutriments.get("fat_value") or 0
                wegle = nutriments.get("carbohydrates_100g") or nutriments.get("carbohydrates_value") or 0
                return {
                    "nazwa": nazwa,
                    "kcal_100g": round(float(kcal), 1),
                    "bialko_100g": round(float(bialko), 1),
                    "tluszcz_100g": round(float(tluszcz), 1),
                    "wegle_100g": round(float(wegle), 1)
                }
    except Exception:
        pass
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
    data_teraz = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('''
        INSERT INTO posilki (osoba, dzien, typ_posilku, opis, kcal, bialko, tluszcz, wegle, data_wpisu)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (osoba, dzien, typ_posilku, opis, kcal, bialko, tluszcz, wegle, data_teraz))
    conn.commit()
    conn.close()

init_db()

# --- 4. USTAWIENIA STRONY ---
st.set_page_config(page_title="Rodzinny Asystent Diety", page_icon="🥗", layout="wide")
st.title("🥗 Rodzinny Asystent Diety i Zdrowia")

col_prof1, col_prof2 = st.columns(2)
with col_prof1:
    osoba = st.selectbox("👤 Profil użytkownika:", ["Janek", "Justyna", "Mama", "Seba","gość","gość2"])
with col_prof2:
    wybrany_dzien = st.selectbox("📅 Dzień tygodnia:", ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"])

st.divider()

# --- 5. KALKULATOR ZAPOTRZEBOWANIA (WIEK, PRACA, WODA, BMI) ---
st.subheader("⚙️ Twoje Parametry & Cel Kaloryczny")

c1, c2, c3, c4 = st.columns(4)
plec = c1.radio("Płeć:", ["Mężczyzna", "Kobieta"])
wiek = c2.number_input("Wiek (lata):", min_value=10, max_value=100, value=30)
waga = c3.number_input("Waga (kg):", min_value=30.0, max_value=200.0, value=80.0)
wzrost = c4.number_input("Wzrost (cm):", min_value=100, max_value=230, value=175)

c_praca, c_cel = st.columns(2)
tryb_pracy = c_praca.selectbox("💼 Tryb pracy / Aktywność:", [
    "Siedząca (biuro, brak ćwiczeń)",
    "Lekka (praca mieszana, spacery)",
    "Fizyczna (praca na nogach / na budowie)",
    "Bardzo ciężka fizyczna / intensywne treningi"
])
cel = c_cel.selectbox("🎯 Cel:", ["Redukcja (Schudnąć)", "Utrzymanie wagi", "Masa (Przytyć)"])

if plec == "Mężczyzna":
    bmr = 10 * waga + 6.25 * wzrost - 5 * wiek + 5
else:
    bmr = 10 * waga + 6.25 * wzrost - 5 * wiek - 161

mnozniki = {
    "Siedząca (biuro, brak ćwiczeń)": 1.2,
    "Lekka (praca mieszana, spacery)": 1.4,
    "Fizyczna (praca na nogach / na budowie)": 1.6,
    "Bardzo ciężka fizyczna / intensywne treningi": 1.8
}
cpm = bmr * mnozniki[tryb_pracy]

if cel == "Redukcja (Schudnąć)":
    target_kcal = cpm - 400
elif cel == "Masa (Przytyć)":
    target_kcal = cpm + 300
else:
    target_kcal = cpm

target_kcal = round(target_kcal)
woda_litry = round(waga * 0.035, 1)
bmi = round(waga / ((wzrost/100)**2), 1)

m1, m2, m3 = st.columns(3)
m1.metric("🎯 Cel kaloryczny", f"{target_kcal} kcal")
m2.metric("💧 Zapotrzebowanie na wodę", f"{woda_litry} L / dzień")
m3.metric("📊 Twoje BMI", f"{bmi}")

st.divider()

# --- 6. DODAWANIE POSIŁKU (SKANER / AI GŁOS / RĘCZNIE) ---
st.subheader("➕ Dodaj posiłek")

c_cam, c_voice = st.columns(2)

with c_cam:
    st.write("📷 **Skaner kodu kreskowego:**")
    zdjecie_kodu = st.camera_input("Nakieruj aparat na kod")
    wykryty_kod = ""
    if zdjecie_kodu:
        img = Image.open(zdjecie_kodu)
        decoded_objects = decode(img)
        if decoded_objects:
            wykryty_kod = decoded_objects[0].data.decode('utf-8')
            st.success(f"✅ Odczytano kod: **{wykryty_kod}**")
        else:
            st.warning("⚠️ Nie odczytano kodu. Spróbuj zbliżyć obiektyw.")
    kod_input = st.text_input("Kod kreskowy (lub wpisz ręcznie):", value=wykryty_kod)

dane_z_kodu = None
if kod_input:
    dane_z_kodu = pobierz_dane_z_kodu(kod_input)

dane_z_ai = None
with c_voice:
    st.write("🎙️ **Dyktuj posiłek głosem (AI przeliczy makro):**")
    tekst_z_głosu = speech_to_text(language='pl', start_prompt="🔴 Nagraj głos", stop_prompt="🟢 Stop", key='stt')
    if tekst_z_głosu:
        st.info(f"Rozpoznano: *{tekst_z_głosu}*")
        with st.spinner("🤖 Gemini AI analizuje posiłek..."):
            dane_z_ai = przelicz_glos_na_makro(tekst_z_głosu)

# Wyznaczenie domyślnych wartości w formularzu
if dane_z_ai:
    domyslna_nazwa = dane_z_ai.get('nazwa', '')
    def_kcal = float(dane_z_ai.get('kcal', 0.0))
    def_b = float(dane_z_ai.get('bialko', 0.0))
    def_t = float(dane_z_ai.get('tluszcz', 0.0))
    def_w = float(dane_z_ai.get('wegle', 0.0))
elif dane_z_kodu:
    domyslna_nazwa = dane_z_kodu['nazwa']
    def_kcal = dane_z_kodu['kcal_100g']
    def_b = dane_z_kodu['bialko_100g']
    def_t = dane_z_kodu['tluszcz_100g']
    def_w = dane_z_kodu['wegle_100g']
else:
    domyslna_nazwa = ""
    def_kcal, def_b, def_t, def_w = 0.0, 0.0, 0.0, 0.0

typ_posilku = st.selectbox("Typ posiłku:", ["Śniadanie", "Drugie śniadanie", "Obiad", "Kolacja", "Przekąska"])
opis_input = st.text_input("Nazwa posiłku:", value=domyslna_nazwa)

if dane_z_kodu and not dane_z_ai:
    gramatura = st.number_input("Waga porcji z kodu (g):", min_value=1, value=100)
    przelicznik = gramatura / 100.0
    calc_kcal = round(def_kcal * przelicznik, 1)
    calc_b = round(def_b * przelicznik, 1)
    calc_t = round(def_t * przelicznik, 1)
    calc_w = round(def_w * przelicznik, 1)
else:
    calc_kcal, calc_b, calc_t, calc_w = def_kcal, def_b, def_t, def_w

col_k, col_b, col_t, col_w = st.columns(4)
input_kcal = col_k.number_input("Kcal", value=calc_kcal)
input_b = col_b.number_input("Białko (g)", value=calc_b)
input_t = col_t.number_input("Tłuszcz (g)", value=calc_t)
input_w = col_w.number_input("Węgle (g)", value=calc_w)

if st.button("💾 Zapisz posiłek w dzienniku", type="primary"):
    if opis_input:
        dodaj_posilek(osoba, wybrany_dzien, typ_posilku, opis_input, input_kcal, input_b, input_t, input_w)
        st.success(f"Dodano posiłek dla {osoba}!")
        st.rerun()

st.divider()

# --- 7. DZIENNIK I PASEK POSTĘPU ---
st.subheader(f"📊 Dziennik posiłków: {osoba} ({wybrany_dzien})")

conn = sqlite3.connect('dziennik_zywieniowy.db')
df = pd.read_sql_query("SELECT typ_posilku, opis, kcal, bialko, tluszcz, wegle FROM posilki WHERE osoba = ? AND dzien = ?", conn, params=(osoba, wybrany_dzien))
conn.close()

zjedzone_kcal = df['kcal'].sum() if not df.empty else 0
zostalo_kcal = target_kcal - zjedzone_kcal

st.progress(min(max(zjedzone_kcal / target_kcal, 0.0), 1.0))
st.write(f"Zjedzono: **{zjedzone_kcal:.1f}** / **{target_kcal} kcal** (Zostało: **{zostalo_kcal:.1f} kcal**)")

if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.info("Brak posiłków zapisanych na ten dzień.")

st.divider()

#--- 8. PROPOZYCJE DAŃ ZE ZDJĘCIAMI ---
st.subheader(" Pomysł na posiłek")

if zostalo_kcal > 0:
    st.write(f" Zostało Ci jeszcze {zostalo_kcal:.0f} kcal. Oto propozycja dania dla Ciebie:")

# Logika wyboru posiłku w zależności od kalorii
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
        st.markdown(f"###  {nazwa}")
        st.write(f"Kaloryczność: {kcal_str}")
        st.write(f"Składniki: {skladniki}")
        st.write(f"Przygotowanie: {przepis}")
else:
    st.warning("Przekroczyłeś dzisiejszy limit kalorii! Odpocznij i pij dużo wody ")
