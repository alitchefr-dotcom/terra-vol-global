import streamlit as st
import pandas as pd
import os
from datetime import date
from calc import get_live_exchange_rate, convert_currency, format_currency, calculate_project_costs

st.set_page_config(
    page_title="Terra Vol | Global BESS Project Calculator",
    page_icon="⚡",
    layout="wide"
)

# Session State for live exchange rate refresh
if "usd_eur" not in st.session_state:
    st.session_state.usd_eur = get_live_exchange_rate("USD", "EUR")

def refresh_rate():
    st.session_state.usd_eur = get_live_exchange_rate("USD", "EUR")

# --- SIDEBAR WITH LOGO RESTORED ---
logo_path = "logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=180)

st.sidebar.markdown("### ⚡ Terra Vol Global")
st.sidebar.markdown("---")

display_currency = st.sidebar.selectbox(
    "Main Display Currency:",
    options=["EUR (€)", "USD ($)"],
    index=0
)
curr_code = "EUR" if "EUR" in display_currency else "USD"

delivery_date = st.sidebar.date_input("Delivery Target Date:", value=date(2027, 6, 30))

trend_multiplier = st.sidebar.slider(
    "Equipment Cost Trend Multiplier:",
    min_value=0.8,
    max_value=1.3,
    value=1.0,
    step=0.01
)

st.sidebar.markdown("---")
st.sidebar.markdown("#### 💱 Exchange Rates (Dynamic Live)")

st.sidebar.number_input(
    "USD to EUR Exchange Rate:",
    min_value=0.5,
    max_value=2.0,
    step=0.001,
    format="%.4f",
    key="usd_eur"
)
usd_to_eur = st.session_state.usd_eur

st.sidebar.button("🔄 Refresh Live Rates", on_click=refresh_rate)

destination_country = st.sidebar.selectbox(
    "Project Destination Country:",
    options=["Italy", "Romania", "Finland", "Germany", "Greece"],
    index=0
)
dest_code = destination_country[:2].upper()

# Smart Port & Corridor Intelligence mapped to active BESS markets
country_logistics_data = {
    "Italy": {
        "ports": ["Koper, Slovenia (Optimal Gateway)", "Trieste, Italy", "Venice, Italy", "Genoa, Italy"],
        "corridors": [
            {"Route": "Asia via Koper (Slovenia) to Northern Italy", "Transit": "26-29 Days", "Advantage": "Avoids congested southern Italian ports & direct rail", "Suitability": "High for BESS"},
            {"Route": "Asia via Trieste / Venice to Central Italy", "Transit": "28-31 Days", "Advantage": "Strategic Adriatic entry with strong heavy-haul road access", "Suitability": "High"}
        ]
    },
    "Romania": {
        "ports": ["Constanța, Romania", "Koper, Slovenia (Multimodal via Rail)", "Piraeus, Greece"],
        "corridors": [
            {"Route": "Asia via Constanța (Black Sea)", "Transit": "32-35 Days", "Advantage": "Optimal for Eastern Europe / Balkan & Romanian utility-scale BESS", "Suitability": "High for Solar + BESS"}
        ]
    },
    "Finland": {
        "ports": ["Helsinki / Kotka, Finland", "Hamburg, Germany"],
        "corridors": [
            {"Route": "Asia via Baltic Hubs (Kotka / Helsinki)", "Transit": "35-38 Days", "Advantage": "Direct Northern European discharge, specialized heavy-lift cranes", "Suitability": "Essential for Finnish BESS"}
        ]
    },
    "Germany": {
        "ports": ["Hamburg, Germany", "Bremerhaven, Germany", "Rotterdam, Netherlands"],
        "corridors": [
            {"Route": "Asia via Hamburg / Bremerhaven", "Transit": "28-31 Days", "Advantage": "Direct North Range mega-port entry, world-class heavy rail connections", "Suitability": "Primary BESS Corridor"}
        ]
    },
    "Greece": {
        "ports": ["Piraeus, Greece", "Thessaloniki, Greece"],
        "corridors": [
            {"Route": "Asia via Piraeus (Main Hub)", "Transit": "25-28 Days", "Advantage": "Fastest entry from Suez / Asia, excellent Mediterranean distribution", "Suitability": "Optimal for Greek & Balkan BESS"}
        ]
    }
}

current_market = country_logistics_data.get(destination_country, country_logistics_data["Romania"])
available_ports = current_market["ports"]
corridors_df = pd.DataFrame(current_market["corridors"])

# --- MAIN PAGE HEADER ---
st.title("Terra Vol")
st.markdown(f"##### *Professional BESS Landed Cost & Logistics Engine — Target Market: {destination_country}*")
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "📦 Equipment Mix & Quantities",
    "🚢 Supply Chain & Incoterms",
    "🏗️ Storage, Demurrage & Drayage",
    "⚖️ Regulation & Landed Cost Summary"
])

with tab1:
    st.subheader("Equipment Mix & Quantities Configuration")
    st.info(f"All calculations in **{curr_code}** tailored for active BESS deployment in **{destination_country}**.")
    
    col1, col2 = st.columns(2)
    with col1:
        bess_count = st.number_input("BESS Containers (Units):", min_value=0, value=20, step=1)
        mvs_count = st.number_input("Medium Voltage Stations (MVS Units):", min_value=0, value=4, step=1)
        transformer_count = st.number_input("Transformers / Skids:", min_value=0, value=0, step=1)
    with col2:
        oog_count = st.number_input("OOG / Special Containers:", min_value=0, value=0, step=1)
        access_count = st.number_input("Accessory Containers:", min_value=0, value=2, step=1)
        solar_count = st.number_input("Solar PV / Inverter Containers:", min_value=0, value=0, step=1)

    st.markdown("---")
    col_exw1, col_exw2 = st.columns(2)
    with col_exw1:
        bess_exw = st.number_input("EXW Cost per BESS Container (USD):", min_value=10000, value=300000, step=5000)
        mvs_exw = st.number_input("EXW Cost per MVS Unit (USD):", min_value=5000, value=120000, step=5000)
        transformer_exw = st.number_input("EXW Cost per Transformer (USD):", min_value=5000, value=80000, step=5000)
    with col_exw2:
        oog_exw = st.number_input("EXW Cost per OOG Unit (USD):", min_value=10000, value=150000, step=5000)
        access_exw = st.number_input("EXW Cost per Accessory Unit (USD):", min_value=1000, value=30000, step=1000)
        solar_exw = st.number_input("EXW Cost per Solar Unit (USD):", min_value=1000, value=50000, step=1000)

    bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh):", min_value=1.0, value=4.0, step=0.5)

with tab2:
    st.subheader("Supply Chain & Incoterms Management")
    
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        shipping_line = st.selectbox("Shipping Line / Carrier:", ["MSC", "Maersk", "CMA CGM", "COSCO Shipping", "Hapag-Lloyd", "Evergreen Line", "ONE", "HMM"])
        origin_port = st.selectbox("Origin Port (China):", ["Shanghai, China", "Ningbo, China", "Shenzhen, China"])
    with col_sc2:
        dest_port = st.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=available_ports)
        incoterm_code = st.selectbox("In
