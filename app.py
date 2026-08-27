import streamlit as st
import sqlite3
import pandas as pd
import requests
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode
from streamlit_mic_recorder import speech_to_text

# --- 1. FUNKCJA POBIERANIA MAKRO Z BAZY OPEN FOOD FACTS ---
def pobierz_dane_z_kodu(kod_kreskowy):
    url = f"https://world.openfoodfacts.org/api/v0/product/{kod_kreskowy}.json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == 1:
            product = data.get("product", {})
            nutriments = product.get("nutriments", {})
            return {
                "nazwa": product.get("product_name_pl") or product.get("product_name") or "Nieznany produkt",
                "kcal_100g": nutriments.get("energy-kcal_100g", 0),
                "bialko_100g": nutriments.get("proteins_100g", 0),
                "tluszcz_100g": nutriments.get("fat_100g", 0),
                "wegle_100g": nutriments.get("carbohydrates_100g", 0)
            }
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

# --- 3. INTERFEJS APLIKACJI ---
st.set_page_config(page_title="Rodzinny Dziennik Diety", page_icon="🥗")
st.title("🥗 Rodzinny Dziennik Diety & Skaner")

# Wybór osoby i dnia
col1, col2 = st.columns(2)
with col1:
    osoba = st.selectbox("👤 Wybierz osobę:", ["Janek", "Kasia", "Mama", "Tata"])
with col2:
    wybrany_dzien = st.selectbox("📅 Dzień tygodnia:", ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"])

st.divider()

# --- 4. SKANOWANIE KODU KRESKOWEGO ---
st.subheader("📷 Skanuj produkt lub powiedz co zjadłeś")

zdjecie_kodu = st.camera_input("Zrób zdjęcie kodu kreskowego z opakowania")
wykryty_kod = ""

if zdjecie_kodu:
    img = Image.open(zdjecie_kodu)
    decoded_objects = decode(img)
    if decoded_objects:
        wykryty_kod = decoded_objects[0].data.decode('utf-8')
        st.success(f"✅ Zeskanowano kod: **{wykryty_kod}**")
    else:
        st.warning("⚠️ Nie odczytano kodu. Spróbuj zbliżyć aparat.")

kod_input = st.text_input("Wpisz kod ręcznie (jeśli aparat nie wykrył):", value=wykryty_kod)

# Przetwarzanie kodu z bazy Open Food Facts
dane_z_kodu = None
if kod_input:
    dane_z_kodu = pobierz_dane_z_kodu(kod_input)
    if dane_z_kodu:
        st.info(f"🔎 Odnaleziono w bazie: **{dane_z_kodu['nazwa']}** (100g = {dane_z_kodu['kcal_100g']} kcal)")
    else:
        st.error("Nie znaleziono produktu w bazie. Wpisz dane ręcznie.")

# --- 5. MODUŁ GŁOSOWY I DANE POSIŁKU ---
typ_posilku = st.selectbox("Typ posiłku:", ["Śniadanie", "Drugie śniadanie", "Obiad", "Kolacja", "Przekąska"])

st.write("🎙️ **Możesz też dyktować głosem:**")
tekst_z_głosu = speech_to_text(language='pl', start_prompt="🔴 Nagraj głos", stop_prompt="🟢 Stop", key='stt')

domyslna_nazwa = dane_z_kodu['nazwa'] if dane_z_kodu else (tekst_z_głosu if tekst_z_głosu else "")
opis_input = st.text_input("Nazwa / Opis posiłku:", value=domyslna_nazwa)

# Wyliczenia makro na podstawie wagi
gramatura = st.number_input("Waga porcji (w gramach):", min_value=1, value=100 if dane_z_kodu else 100)

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

if st.button("💾 Zapisz do dziennika", type="primary"):
    if opis_input:
        dodaj_posilek(osoba, wybrany_dzien, typ_posilku, opis_input, input_kcal, input_b, input_t, input_w)
        st.success(f"Dodano posiłek dla: {osoba}!")
        st.rerun()

st.divider()

# --- 6. PODGLĄD DZIENNIKA DLA OSOBY ---
st.subheader(f"📊 Dziennik: {osoba} ({wybrany_dzien})")

conn = sqlite3.connect('dziennik_zywieniowy.db')
df = pd.read_sql_query("SELECT typ_posilku, opis, kcal, bialko, tluszcz, wegle FROM posilki WHERE osoba = ? AND dzien = ?", conn, params=(osoba, wybrany_dzien))
conn.close()

if not df.empty:
    st.dataframe(df, use_container_width=True)
    st.metric("Suma Kalorii", f"{df['kcal'].sum()} kcal")
else:
    st.info("Brak posiłków zapisanych na ten dzień.")
