import streamlit as st
import plotly.graph_objects as go
import re

st.set_page_config(page_title="Kalkulator Kalorii i Makro", page_icon="🥗", layout="centered")

st.title("🥗 Twoja Aplikacja Dietetyczna & Trener")

# --- ROZBUDOWANA BAZA PRODUKTÓW ---
# Przeliczniki: wartości na 1g (dla gramatur) lub na 1 sztukę (dla is_unit: True)
FOOD_DATABASE = {
    # Nabiał / Desery
    "skyr": {"kcal": 0.65, "p": 0.11, "f": 0.00, "c": 0.04},
    "monte": {"kcal": 1.95, "p": 0.03, "f": 0.13, "c": 0.16},
    "twarog": {"kcal": 0.90, "p": 0.18, "f": 0.00, "c": 0.035},
    "twaróg": {"kcal": 0.90, "p": 0.18, "f": 0.00, "c": 0.035},
    "mleko": {"kcal": 0.47, "p": 0.03, "f": 0.015, "c": 0.05},
    "ser zolty": {"kcal": 3.50, "p": 0.25, "f": 0.27, "c": 0.01},
    "ser żółty": {"kcal": 3.50, "p": 0.25, "f": 0.27, "c": 0.01},
    "mozzarella": {"kcal": 2.50, "p": 0.18, "f": 0.19, "c": 0.01},
    "jogurt naturalny": {"kcal": 0.60, "p": 0.04, "f": 0.03, "c": 0.04},
    
    # Suplementy / Odżywki
    "shake bialkowy": {"kcal": 120, "p": 24.0, "f": 1.5, "c": 2.0, "is_unit": True},
    "shake białkowy": {"kcal": 120, "p": 24.0, "f": 1.5, "c": 2.0, "is_unit": True},
    "odzywka bialkowa": {"kcal": 120, "p": 24.0, "f": 1.5, "c": 2.0, "is_unit": True},
    "odżywka białkowa": {"kcal": 120, "p": 24.0, "f": 1.5, "c": 2.0, "is_unit": True},
    
    # Węglowodany / Pieczywo / Fast food
    "platkow owsianych": {"kcal": 3.66, "p": 0.13, "f": 0.07, "c": 0.60},
    "platki owsiane": {"kcal": 3.66, "p": 0.13, "f": 0.07, "c": 0.60},
    "płatki owsiane": {"kcal": 3.66, "p": 0.13, "f": 0.07, "c": 0.60},
    "ryz": {"kcal": 3.50, "p": 0.07, "f": 0.01, "c": 0.77}, # surowy/suchy
    "ryż": {"kcal": 3.50, "p": 0.07, "f": 0.01, "c": 0.77},
    "makaron": {"kcal": 3.50, "p": 0.12, "f": 0.015, "c": 0.72}, # surowy/suchy
    "kasza": {"kcal": 3.40, "p": 0.11, "f": 0.02, "c": 0.68},
    "ziemniaki": {"kcal": 0.77, "p": 0.02, "f": 0.00, "c": 0.17},
    "frytki": {"kcal": 2.90, "p": 0.03, "f": 0.14, "c": 0.35},
    "chleb": {"kcal": 2.50, "p": 0.08, "f": 0.01, "c": 0.49},
    "tosty": {"kcal": 150, "p": 6.0, "f": 5.0, "c": 20.0, "is_unit": True}, # 1 tost złożony
    "tost": {"kcal": 150, "p": 6.0, "f": 5.0, "c": 20.0, "is_unit": True},
    "tortilla": {"kcal": 220, "p": 6.0, "f": 5.0, "c": 36.0, "is_unit": True}, # 1 placek
    "pizza": {"kcal": 2.60, "p": 0.11, "f": 0.10, "c": 0.31}, # na gramy
    "kebab": {"kcal": 750, "p": 40.0, "f": 30.0, "c": 75.0, "is_unit": True}, # 1 średni kebab
    "bułka": {"kcal": 160, "p": 5.0, "f": 1.5, "c": 31.0, "is_unit": True},
    "bulka": {"kcal": 160, "p": 5.0, "f": 1.5, "c": 31.0, "is_unit": True},
    
    # Owoce i Warzywa
    "banan": {"kcal": 95, "p": 1.1, "f": 0.3, "c": 23.0, "is_unit": True},
    "banany": {"kcal": 95, "p": 1.1, "f": 0.3, "c": 23.0, "is_unit": True},
    "jablko": {"kcal": 75, "p": 0.4, "f": 0.3, "c": 19.0, "is_unit": True},
    "jabłko": {"kcal": 75, "p": 0.4, "f": 0.3, "c": 19.0, "is_unit": True},
    "pomidor": {"kcal": 20, "p": 1.0, "f": 0.2, "c": 4.0, "is_unit": True},
    "ogorek": {"kcal": 15, "p": 0.7, "f": 0.1, "c": 3.0, "is_unit": True},
    "ogórek": {"kcal": 15, "p": 0.7, "f": 0.1, "c": 3.0, "is_unit": True},
    
    # Mięso / Jaja / Ryby
    "kurczak": {"kcal": 1.65, "p": 0.31, "f": 0.03, "c": 0.00},
    "kurczaka": {"kcal": 1.65, "p": 0.31, "f": 0.03, "c": 0.00},
    "pierś z kurczaka": {"kcal": 1.65, "p": 0.31, "f": 0.03, "c": 0.00},
    "indyk": {"kcal": 1.35, "p": 0.29, "f": 0.02, "c": 0.00},
    "indyka": {"kcal": 1.35, "p": 0.29, "f": 0.02, "c": 0.00},
    "wolowina": {"kcal": 2.50, "p": 0.26, "f": 0.15, "c": 0.00},
    "wołowina": {"kcal": 2.50, "p": 0.26, "f": 0.15, "c": 0.00},
    "mielone": {"kcal": 2.20, "p": 0.19, "f": 0.15, "c": 0.00},
    "jajko": {"kcal": 70, "p": 6.0, "f": 5.0, "c": 0.5, "is_unit": True},
    "jaja": {"kcal": 70, "p": 6.0, "f": 5.0, "c": 0.5, "is_unit": True},
    "tunczyk": {"kcal": 1.30, "p": 0.28, "f": 0.01, "c": 0.00},
    "tuńczyk": {"kcal": 1.30, "p": 0.28, "f": 0.01, "c": 0.00},
    "losos": {"kcal": 2.00, "p": 0.20, "f": 0.13, "c": 0.00},
    "łosoś": {"kcal": 2.00, "p": 0.20, "f": 0.13, "c": 0.00},
    
    # Dodatki / Tłuszcze
    "oliwa": {"kcal": 8.84, "p": 0.00, "f": 1.00, "c": 0.00},
    "maslo": {"kcal": 7.17, "p": 0.01, "f": 0.81, "c": 0.01},
    "masło": {"kcal": 7.17, "p": 0.01, "f": 0.81, "c": 0.01},
    "maslo orzechowe": {"kcal": 6.00, "p": 0.25, "f": 0.50, "c": 0.20},
    "masło orzechowe": {"kcal": 6.00, "p": 0.25, "f": 0.50, "c": 0.20},
    "ketchup": {"kcal": 1.10, "p": 0.01, "f": 0.00, "c": 0.25},
    "majonez": {"kcal": 6.80, "p": 0.01, "f": 0.75, "c": 0.03},
}

def parse_meal(text):
    text = text.lower()
    total_kcal, total_p, total_f, total_c = 0, 0, 0, 0
    found_items = []
    
    for food, data in FOOD_DATABASE.items():
        if food in text:
            if data.get("is_unit"):
                match = re.search(r'(\d+)\s*' + re.escape(food), text)
                qty = int(match.group(1)) if match else 1
                k = qty * data["kcal"]
                p = qty * data["p"]
                f = qty * data["f"]
                c = qty * data["c"]
                found_items.append(f"{qty}x {food} ({int(k)} kcal)")
            else:
                match = re.search(r'(\d+)\s*g?\s*' + re.escape(food), text)
                grams = int(match.group(1)) if match else 100
                k = grams * data["kcal"]
                p = grams * data["p"]
                f = grams * data["f"]
                c = grams * data["c"]
                found_items.append(f"{grams}g {food} ({int(k)} kcal)")
            
            total_kcal += k
            total_p += p
            total_f += f
            total_c += c
            
    return int(total_kcal), int(total_p), int(total_f), int(total_c), found_items

# --- 1. PROFIL UŻYTKOWNIKA ---
st.sidebar.header("👤 Twoje Dane i Styl Życia")
weight = st.sidebar.number_input("Waga (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5)
height = st.sidebar.number_input("Wzrost (cm)", min_value=100.0, max_value=250.0, value=175.0, step=1.0)
age = st.sidebar.number_input("Wiek", min_value=10, max_value=120, value=25)
gender = st.sidebar.selectbox("Płeć", ["Mężczyzna", "Kobieta"])

work_type = st.sidebar.selectbox("Tryb pracy", ["Siedząca", "Mieszana", "Fizyczna"])
workout_type = st.sidebar.selectbox("Treningi", ["Brak", "Siłownia (2-4x)", "Kardio (2-4x)", "Intensywne (5+)"])
walks = st.sidebar.selectbox("Spacery", ["< 5 000 kroków", "5 000 - 10 000 kroków", "> 10 000 kroków"])
goal = st.sidebar.selectbox("Twój Cel", ["Utrzymanie wagi", "Schudnąć (-400 kcal)", "Przybrać (+300 kcal)"])

bmr = (10 * weight + 6.25 * height - 5 * age + 5) if gender == "Mężczyzna" else (10 * weight + 6.25 * height - 5 * age - 161)
pal = 1.2 + (0.1 if work_type == "Mieszana" else 0.25 if work_type == "Fizyczna" else 0)
tdee = bmr * pal

target_cals = int(tdee - 400 if goal == "Schudnąć (-400 kcal)" else tdee + 300 if goal == "Przybrać (+300 kcal)" else tdee)
target_water = int(weight * 35)

# --- 2. STAN APLIKACJI ---
if 'cals_eaten' not in st.session_state: st.session_state.cals_eaten = 0
if 'water_drank' not in st.session_state: st.session_state.water_drank = 0
if 'logs' not in st.session_state: st.session_state.logs = []

# --- 3. PODSUMOWANIE DNIA ---
st.subheader("📊 Dzisiejsze podsumowanie")
col1, col2 = st.columns(2)

def create_circular_chart(current, target, color):
    remaining = max(target - current, 0)
    percent = min(int((current / target) * 100), 100) if target > 0 else 0
    fig = go.Figure(data=[go.Pie(labels=['Zjedzone', 'Pozostało'], values=[current, remaining], hole=0.7, marker_colors=[color, '#E5E7EB'], textinfo='none')])
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=160, annotations=[{'text': f"<b>{percent}%</b><br><span style='font-size:11px;'>{current}/{target}</span>", 'x': 0.5, 'y': 0.5, 'font_size': 16, 'showarrow': False}])
    return fig

with col1:
    st.markdown("### 🔥 Kalorie")
    st.plotly_chart(create_circular_chart(st.session_state.cals_eaten, target_cals, "#FF4B4B"), use_container_width=True)
    st.caption(f"Pozostało: **{max(target_cals - st.session_state.cals_eaten, 0)}** kcal")

with col2:
    st.markdown("### 💧 Woda")
    st.plotly_chart(create_circular_chart(st.session_state.water_drank, target_water, "#1C92D2"), use_container_width=True)
    st.caption(f"Pozostało: **{max(target_water - st.session_state.water_drank, 0)}** ml")

# --- 4. KALKULATOR POSIŁKU z TEKSTU ---
st.markdown("---")
st.subheader("➕ Automatyczne przeliczanie posiłku")

meal_input = st.text_input("Wpisz co zjadłeś (np. 1 monte, 200g makaron, 1 shake bialkowy, 2 tosty):", value="1 monte i 150g kurczak")

calc_kcal, calc_p, calc_f, calc_c, items = parse_meal(meal_input)

if items:
    st.success(f"Rozpoznano: {', '.join(items)}")
    st.info(f"📊 Szacowane wartości: **{calc_kcal} kcal** | Białko: {calc_p}g | Tłuszcze: {calc_f}g | Węgle: {calc_c}g")
else:
    st.warning("Nie rozpoznano produktów. Spróbuj wpisać np. '100g ryz', '1 monte', '1 shake bialkowy', '2 tosty', '200g pizza'.")

col_b1, col_b2 = st.columns(2)
with col_b1:
    final_cals = st.number_input("Kalorie do dodania:", value=calc_kcal if calc_kcal > 0 else 300, step=50)
    if st.button("➕ Dodaj do Bilansu"):
        st.session_state.cals_eaten += final_cals
        st.session_state.logs.append(f"Posiłek: +{final_cals} kcal ({meal_input})")
        st.rerun()

with col_b2:
    st.write("Woda:")
    if st.button("🥤 Wypiłem szklankę wody (250 ml)"):
        st.session_state.water_drank += 250
        st.session_state.logs.append("Woda: +250 ml")
        st.rerun()

# --- 5. DZIENNIK WPISÓW ---
if st.session_state.logs:
    st.markdown("---")
    st.write("**Dzisiejsze wpisy:**")
    for log in reversed(st.session_state.logs):
        st.text(f"• {log}")