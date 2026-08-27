import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode
from streamlit_mic_recorder import speech_to_text

# --- 1. FUNKCJA POBIERANIA MAKRO Z KODU KRESKOWEGO ---
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

# --- 2. BAZA DANYCH LOKALNA ---
def init_db():
    conn = sqlite3.connect('dziennik_zywieniowy.db')
    c = conn.cursor()
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
            wegle REAL,
            data_wpisu TEXT
        )
    ''')
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

# --- 3. USTAWIENIA STRONY ---
st.set_page_config(page_title="Rodzinny Asystent Diety", page_icon="🥗", layout="wide")
st.title("🥗 Rodzinny Asystent Diety i Zdrowia")

# Wybór profilu i dnia
col_prof1, col_prof2 = st.columns(2)
with col_prof1:
    osoba = st.selectbox("👤 Profil użytkownika:", ["Janek", "Justyna", "Mama", "Seba"])
with col_prof2:
    wybrany_dzien = st.selectbox("📅 Dzień tygodnia:", ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"])

st.divider()

# --- 4. KALKULATOR ZAPOTRZEBOWANIA (WIEK, PRACA, WODA, BMI) ---
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

# Obliczenia BMR i CPM
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

# Wyświetlanie celów i grafik
m1, m2, m3 = st.columns(3)
m1.metric("🎯 Cel kaloryczny", f"{target_kcal} kcal")
m2.metric("💧 Zapotrzebowanie na wodę", f"{woda_litry} L / dzień")
m3.metric("📊 Twoje BMI", f"{bmi}")

st.divider()

# --- 5. SKANOWANIE KODU & DYKTOWANIE GŁOSEM ---
st.subheader("➕ Dodaj posiłek (Skaner / Głos / Ręcznie)")

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

with c_voice:
    st.write("🎙️ **Dyktuj posiłek głosem:**")
    tekst_z_głosu = speech_to_text(language='pl', start_prompt="🔴 Nagraj głos", stop_prompt="🟢 Stop", key='stt')
    if tekst_z_głosu:
        st.info(f"Rozpoznano: {tekst_z_głosu}")

# Sprawdzanie makro w bazie z kodu
dane_z_kodu = None
if kod_input:
    dane_z_kodu = pobierz_dane_z_kodu(kod_input)
    if dane_z_kodu:
        st.success(f"🔎 Znaleziono: **{dane_z_kodu['nazwa']}** (100g = {dane_z_kodu['kcal_100g']} kcal)")

typ_posilku = st.selectbox("Typ posiłku:", ["Śniadanie", "Drugie śniadanie", "Obiad", "Kolacja", "Przekąska"])

domyslna_nazwa = dane_z_kodu['nazwa'] if dane_z_kodu else (tekst_z_głosu if tekst_z_głosu else "")
opis_input = st.text_input("Nazwa posiłku:", value=domyslna_nazwa)

gramatura = st.number_input("Waga porcji (g):", min_value=1, value=100)

if dane_z_kodu:
    przelicznik = gramatura / 100.0
    calc_kcal = round(dane_z_kodu['kcal_100g'] * przelicznik, 1)
    calc_b = round(dane_z_kodu['bialko_100g'] * przelicznik, 1)
    calc_t = round(dane_z_kodu['tluszcz_100g'] * przelicznik, 1)
    calc_w = round(dane_z_kodu['wegle_100g'] * przelicznik, 1)
else:
    calc_kcal, calc_b, calc_t, calc_w = 0.0, 0.0, 0.0, 0.0

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

# --- 6. DZIENNIK I PASEK POSTĘPU ---
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

# --- 7. PROPOZYCJE DAŃ ZE ZDJĘCIAMI (GIF / JPG) ---
st.subheader("🥪 Pomysł na posiłek (Ze zdjęciem)")

if zostalo_kcal > 0:
    st.write(f"💡 Zostało Ci jeszcze **{zostalo_kcal:.0f} kcal**. Oto propozycja dania dla Ciebie:")
    
    # Przykładowe gotowe przepisy ze zdjęciami
    col_img, col_txt = st.columns([1, 2])
    with col_img:
        st.image("https://images.unsplash.com/photo-1525351484163-7529414344d8?w=500", caption="Tosty z serem i szynką", use_column_width=True)
    with col_txt:
        st.markdown("### 🍞 Tosty z serem, szynką i warzywami")
        st.write("**Kaloryczność:** ~450 kcal | **Białko:** 22g | **Tłuszcz:** 18g")
        st.write("**Składniki:** 2 kromki chleba tostowego, 2 plastry sera żółtego, 2 plastry szynki, pomidor, ogórek.")
        st.write("**Przygotowanie:** Złóż tosty z serem i szynką, zapiecz w opiekaczu. Podawaj z pokrojonym w plastry pomidorem i ogórkiem.")
else:
    st.warning("Przekroczyłeś dzisiejszy limit kalorii! Odpocznij i pij dużo wody 💧")
