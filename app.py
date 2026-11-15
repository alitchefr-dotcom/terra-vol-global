import streamlit as st
import pandas as pd
import os
import io
from datetime import date
from calc import get_live_exchange_rate, convert_currency, format_currency, calculate_project_costs
from calc import calculate_shipment_plan, EQUIPMENT_TYPES, SERVICE_TYPES

st.set_page_config(
    page_title="Terra Vol | Global BESS Project Calculator",
    page_icon="⚡",
    layout="wide"
)
# --- MODE SELECTOR ---
st.markdown("---")
app_mode = st.radio(
    "Select Operating Mode:",
    ["⚡ Quick Scenario Showcase (Investor/Marketing View)", "🛠️ Advanced Manual Configuration & Routing Agent"],
    horizontal=True
)
# --- CUSTOM CSS STYLING ---
st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
    }
    div[data-testid="metric-container"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .stButton>button {
        background-color: #0284C7;
        color: white;
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 600;
        border: none;
    }
    div.stDownloadButton>button {
        background-color: #059669;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #F1F5F9;
        border-radius: 6px 6px 0px 0px;
        padding: 10px 16px;
        font-weight: 500;
        color: #475569;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284C7 !important;
        color: white !important;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)
# --- EUROPEAN VAT RATES DICTIONARY ---
EUROPEAN_VAT_RATES = {
    "Romania": 19.0,
    "Poland": 23.0,
    "Hungary": 27.0,
    "Bulgaria": 20.0,
    "Germany": 19.0,
    "Italy": 22.0,
    "Greece": 24.0,
    "Finland": 25.5,
    "France": 20.0,
    "Spain": 21.0,
    "Netherlands": 21.0,
    "Belgium": 21.0,
    "Austria": 20.0,
    "Czech Republic": 21.0,
    "Slovakia": 20.0,
    "Croatia": 25.0
}
# Comprehensive Logistics Network Matrix for Europe, Aegean, Saronic, Black Sea & Adriatic
LOGISTICS_NETWORK = {
    "Shanghai (China)": {
        "destinations": {
            "Amsterdam / Rotterdam (Netherlands)": {"distance_km": 550, "transit_days": 35, "base_trucking_cost": 5200},
            "Padova / Milan (Italy)": {"distance_km": 450, "transit_days": 36, "base_trucking_cost": 4800},
            "Ljubljana / Koper (Slovenia)": {"distance_km": 380, "transit_days": 35, "base_trucking_cost": 4300},
            "Bucharest / Iepurești (Romania)": {"distance_km": 320, "transit_days": 35, "base_trucking_cost": 4200},
            "Warsaw / Central Poland": {"distance_km": 450, "transit_days": 37, "base_trucking_cost": 4800},
            "Budapest (Hungary)": {"distance_km": 300, "transit_days": 35, "base_trucking_cost": 3900},
            "Berlin / Frankfurt (Germany)": {"distance_km": 600, "transit_days": 36, "base_trucking_cost": 5500},
            "Paris / Lyon (France)": {"distance_km": 650, "transit_days": 36, "base_trucking_cost": 5800},
            "Madrid / Barcelona (Spain)": {"distance_km": 900, "transit_days": 38, "base_trucking_cost": 7500},
            "Athens / Piraeus (Greece)": {"distance_km": 800, "transit_days": 32, "base_trucking_cost": 7000}
        }
    },
    "Ningbo (China)": {
        "destinations": {
            "Amsterdam / Rotterdam (Netherlands)": {"distance_km": 550, "transit_days": 35, "base_trucking_cost": 5200},
            "Padova / Milan (Italy)": {"distance_km": 450, "transit_days": 36, "base_trucking_cost": 4800},
            "Ljubljana / Koper (Slovenia)": {"distance_km": 380, "transit_days": 35, "base_trucking_cost": 4300},
            "Bucharest / Iepurești (Romania)": {"distance_km": 320, "transit_days": 35, "base_trucking_cost": 4200},
            "Warsaw / Central Poland": {"distance_km": 450, "transit_days": 37, "base_trucking_cost": 4800},
            "Budapest (Hungary)": {"distance_km": 300, "transit_days": 35, "base_trucking_cost": 3900},
            "Berlin / Frankfurt (Germany)": {"distance_km": 600, "transit_days": 36, "base_trucking_cost": 5500},
            "Paris / Lyon (France)": {"distance_km": 650, "transit_days": 36, "base_trucking_cost": 5800},
            "Madrid / Barcelona (Spain)": {"distance_km": 900, "transit_days": 38, "base_trucking_cost": 7500},
            "Athens / Piraeus (Greece)": {"distance_km": 800, "transit_days": 32, "base_trucking_cost": 7000}
        }
    },
    "Yantian / Shenzhen (China)": {
        "destinations": {
            "Amsterdam / Rotterdam (Netherlands)": {"distance_km": 550, "transit_days": 36, "base_trucking_cost": 5200},
            "Padova / Milan (Italy)": {"distance_km": 450, "transit_days": 37, "base_trucking_cost": 4800},
            "Ljubljana / Koper (Slovenia)": {"distance_km": 380, "transit_days": 36, "base_trucking_cost": 4300},
            "Bucharest / Iepurești (Romania)": {"distance_km": 320, "transit_days": 36, "base_trucking_cost": 4200},
            "Warsaw / Central Poland": {"distance_km": 450, "transit_days": 38, "base_trucking_cost": 4800},
            "Budapest (Hungary)": {"distance_km": 300, "transit_days": 36, "base_trucking_cost": 3900},
            "Berlin / Frankfurt (Germany)": {"distance_km": 600, "transit_days": 37, "base_trucking_cost": 5500},
            "Paris / Lyon (France)": {"distance_km": 650, "transit_days": 37, "base_trucking_cost": 5800},
            "Madrid / Barcelona (Spain)": {"distance_km": 900, "transit_days": 39, "base_trucking_cost": 7500},
            "Athens / Piraeus (Greece)": {"distance_km": 800, "transit_days": 33, "base_trucking_cost": 7000}
        }
    },
    "Qingdao (China)": {
        "destinations": {
            "Amsterdam / Rotterdam (Netherlands)": {"distance_km": 550, "transit_days": 34, "base_trucking_cost": 5200},
            "Padova / Milan (Italy)": {"distance_km": 450, "transit_days": 35, "base_trucking_cost": 4800},
            "Ljubljana / Koper (Slovenia)": {"distance_km": 380, "transit_days": 34, "base_trucking_cost": 4300},
            "Bucharest / Iepurești (Romania)": {"distance_km": 320, "transit_days": 34, "base_trucking_cost": 4200},
            "Warsaw / Central Poland": {"distance_km": 450, "transit_days": 35, "base_trucking_cost": 4800},
            "Budapest (Hungary)": {"distance_km": 300, "transit_days": 34, "base_trucking_cost": 3900},
            "Berlin / Frankfurt (Germany)": {"distance_km": 600, "transit_days": 35, "base_trucking_cost": 5500},
            "Paris / Lyon (France)": {"distance_km": 650, "transit_days": 35, "base_trucking_cost": 5800},
            "Madrid / Barcelona (Spain)": {"distance_km": 900, "transit_days": 37, "base_trucking_cost": 7500},
            "Athens / Piraeus (Greece)": {"distance_km": 800, "transit_days": 31, "base_trucking_cost": 7000}
        }
    },
    "Xingang / Tianjin (China)": {
        "destinations": {
            "Amsterdam / Rotterdam (Netherlands)": {"distance_km": 550, "transit_days": 36, "base_trucking_cost": 5200},
            "Padova / Milan (Italy)": {"distance_km": 450, "transit_days": 36, "base_trucking_cost": 4800},
            "Ljubljana / Koper (Slovenia)": {"distance_km": 380, "transit_days": 36, "base_trucking_cost": 4300},
            "Bucharest / Iepurești (Romania)": {"distance_km": 320, "transit_days": 36, "base_trucking_cost": 4200},
            "Warsaw / Central Poland": {"distance_km": 450, "transit_days": 36, "base_trucking_cost": 4800},
            "Budapest (Hungary)": {"distance_km": 300, "transit_days": 36, "base_trucking_cost": 3900},
            "Berlin / Frankfurt (Germany)": {"distance_km": 600, "transit_days": 37, "base_trucking_cost": 5500},
            "Paris / Lyon (France)": {"distance_km": 650, "transit_days": 37, "base_trucking_cost": 5800},
            "Madrid / Barcelona (Spain)": {"distance_km": 900, "transit_days": 39, "base_trucking_cost": 7500},
            "Athens / Piraeus (Greece)": {"distance_km": 800, "transit_days": 33, "base_trucking_cost": 7000}
        }
    },
    "Rotterdam / Antwerp (Western Europe Gateway)": {
        "destinations": {
            "Amsterdam / Rotterdam (Netherlands)": {"distance_km": 60, "transit_days": 1, "base_trucking_cost": 600},
            "Berlin / Frankfurt (Germany)": {"distance_km": 450, "transit_days": 4, "base_trucking_cost": 4200}
        }
    },
    "Genoa / Trieste / Venice (Mediterranean Hub)": {
        "destinations": {
            "Padova / Milan (Italy)": {"distance_km": 200, "transit_days": 2, "base_trucking_cost": 2100},
            "Ljubljana / Koper (Slovenia)": {"distance_km": 150, "transit_days": 2, "base_trucking_cost": 1800}
        }
    },
    "Koper / Rijeka (Adriatic Hub)": {
        "destinations": {
            "Ljubljana / Koper (Slovenia)": {"distance_km": 80, "transit_days": 1, "base_trucking_cost": 900},
            "Padova / Milan (Italy)": {"distance_km": 300, "transit_days": 3, "base_trucking_cost": 3200}
        }
    },
    "Constanta / Varna (Black Sea Hub)": {
        "destinations": {
            "Bucharest / Iepurești (Romania)": {"distance_km": 280, "transit_days": 3, "base_trucking_cost": 3600}
        }
    }
}
if "usd_eur" not in st.session_state:
    st.session_state.usd_eur = get_live_exchange_rate("USD", "EUR")

def refresh_rate():
    st.session_state.usd_eur = get_live_exchange_rate("USD", "EUR")

# --- SIDEBAR SETTINGS ---
logo_path = "logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=180)

st.sidebar.markdown("### Terra Vol Global")
st.sidebar.markdown("---")

display_currency = st.sidebar.selectbox(
    "Main Display Currency:",
    options=["EUR (€)", "USD ($)"],
    index=0
)
curr_code = "EUR" if "EUR" in display_currency else "USD"
is_eur_display = ("EUR" in display_currency)

delivery_date = st.sidebar.date_input("Delivery Target Date:", value=date(2027, 6, 30))

trend_multiplier = st.sidebar.slider(
    "Equipment Cost Trend Multiplier:",
    min_value=0.8,
    max_value=1.3,
    value=1.0,
    step=0.01
)

st.sidebar.markdown("---")
st.sidebar.markdown("#### Exchange Rates (Dynamic Live)")
st.sidebar.number_input(
    "USD to EUR Exchange Rate:",
    min_value=0.5,
    max_value=2.0,
    step=0.001,
    format="%.4f",
    key="usd_eur"
)
usd_to_eur = st.session_state.usd_eur
st.sidebar.button("Refresh Live Rates", on_click=refresh_rate)

destination_country = st.sidebar.selectbox(
    "Project Destination Country:",
    options=list(EUROPEAN_VAT_RATES.keys()),
    index=0
)

dest_code = destination_country[:2].upper()

all_european_ports = [
    "Constanța, Romania", "Varna, Bulgaria", "Burgas, Bulgaria", 
    "Gdansk, Poland", "Gdynia, Poland", "Koper, Slovenia (Rail Gateway)", 
    "Trieste, Italy", "Venice, Italy", "Genoa, Italy", 
    "Piraeus, Greece", "Thessaloniki, Greece", 
    "Hamburg, Germany", "Bremerhaven, Germany", 
    "Rotterdam, Netherlands", "Antwerp, Belgium", 
    "Helsinki / Kotka, Finland", "Valencia, Spain", "Marseille, France"
]

# --- MAIN PAGE HEADER ---
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Terra Vol")
    st.markdown(f"##### *Professional BESS Landed Cost & Logistics Engine — Target Market: {destination_country}*")
with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📋 Equipment Mix & Quantities",
    "🚢 Supply Chain & Incoterms",
    "📦 Storage, Demurrage & Drayage",
    "⚖️ Regulation & Approvals",
    "🗺️ European Route Options",
    "📂 Infrastructure Projects",
    "📊 Budget & Carbon Report",
    "🧩 Multi-Shipment Planner"
])

with tab1:
    st.subheader("Equipment Mix & Quantities Configuration")
    st.info(f"All calculations tailored for active BESS deployment in **{destination_country}** (Display Currency: **{curr_code}**).")
    
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
    st.markdown("#### Site Location & Project Details")
    loc_col1, loc_col2, loc_col3 = st.columns(3)
    with loc_col1:
        site_address = st.text_input("Site Address / Location:", value=f"Industrial Zone, {destination_country}")
    with loc_col2:
        site_postal = st.text_input("Postal Code / Region:", value="10000")
    with loc_col3:
        site_coords = st.text_input("GPS Coordinates:", value="44.4268° N, 26.1025° E")

    st.markdown("---")
    st.markdown(f"#### Equipment EXW Cost ({curr_code})")
    
    col_exw1, col_exw2 = st.columns(2)
    with col_exw1:
      # Currency conversion factor for default values display
        disp_mult = usd_to_eur if (not is_eur_display and usd_to_eur > 0) else 1.0

        bess_exw_input = st.number_input(f"EXW Cost per BESS Container ({curr_code}):", min_value=0, value=int(400000 * disp_mult), step=5000) if bess_count > 0 else 0
        mvs_exw_input = st.number_input(f"EXW Cost per MVS Unit ({curr_code}):", min_value=0, value=int(250000 * disp_mult), step=5000) if mvs_count > 0 else 0
        transformer_exw_input = st.number_input(f"EXW Cost per Transformer ({curr_code}):", min_value=0, value=int(120000 * disp_mult), step=5000) if transformer_count > 0 else 0
with col_exw2:
        oog_exw_input = st.number_input(f"EXW Cost per OOG Unit ({curr_code}):", min_value=0, value=int(300000 * disp_mult), step=5000) if oog_count > 0 else 0
        access_exw_input = st.number_input(f"EXW Cost per Accessory Unit ({curr_code}):", min_value=0, value=int(30000 * disp_mult), step=1000) if access_count > 0 else 0
        solar_exw_input = st.number_input(f"EXW Cost per Solar Unit ({curr_code}):", min_value=0, value=int(50000 * disp_mult), step=1000) if solar_count > 0 else 0

to_usd_factor = (1.0 / usd_to_eur) if is_eur_display and usd_to_eur > 0 else 1.0
bess_exw = bess_exw_input * to_usd_factor
oog_exw = oog_exw_input * to_usd_factor
mvs_exw = mvs_exw_input * to_usd_factor
transformer_exw = transformer_exw_input * to_usd_factor
access_exw = access_exw_input * to_usd_factor
solar_exw = solar_exw_input * to_usd_factor

bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh):", min_value=0.5, value=4.0, step=0.5)
with tab2:
    st.subheader("Ocean Freight, BAF & Destination THC")
    
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        shipping_line = st.selectbox("Shipping Line / Carrier:", ["MSC", "Maersk", "CMA CGM", "COSCO Shipping", "Hapag-Lloyd", "Evergreen Line", "ONE", "HMM"])
        origin_port = st.selectbox("Origin Port (China):", [
            "Shanghai, China - SIPG (Waigaoqiao / Yangshan)",
            "Ningbo-Zhoushan, China - Beilun Terminal",
            "Qingdao, China - Qianwan Terminal",
            "Shenzhen, China - Yantian International Container Terminal (YICT)",
            "Shenzhen, China - Shekou Container Terminal (SCT)",
            "Guangzhou, China - Nansha Port"
        ])
    with col_sc2:
        dest_port = st.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=all_european_ports, index=0)
        incoterm_code = st.selectbox("Incoterm:", options=["EXW", "FOB", "CFR", "CIF", "DAP", "DDP"], index=3)

    st.markdown("---")
    st.markdown(f"#### 1. Ocean Freight per Unit ({curr_code})")
    f_mult = usd_to_eur if is_eur_display else 1.0
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        f_bess = st.number_input(f"BESS Freight ({curr_code}):", min_value=0, value=int(18000 * f_mult), step=500)
        f_oog = st.number_input(f"OOG Freight ({curr_code}):", min_value=0, value=int(18000 * f_mult), step=500)
    with cf2:
        f_mvs = st.number_input(f"MVS Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
        f_trans = st.number_input(f"Transformer Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
    with cf3:
        f_access = st.number_input(f"Accessory Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
        f_solar = st.number_input(f"Solar PV Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)

    unit_freight_bess = f_bess / usd_to_eur if is_eur_display else f_bess
    unit_freight_oog = f_oog / usd_to_eur if is_eur_display else f_oog
    unit_freight_mvs = f_mvs / usd_to_eur if is_eur_display else f_mvs
    unit_freight_trans = f_trans / usd_to_eur if is_eur_display else f_trans
    unit_freight_access = f_access / usd_to_eur if is_eur_display else f_access
    unit_freight_solar = f_solar / usd_to_eur if is_eur_display else f_solar

    st.markdown(f"#### 2. Bunker Adjustment Factor (BAF) per TEU / Unit ({curr_code})")
    include_baf_in_freight = st.checkbox("Ocean Freight already includes BAF", value=False)
    baf_base_val = 0.0 if include_baf_in_freight else (1500.0 * f_mult)
    
    cb1, cb2, cb3 = st.columns(3)
    with cb1:
        baf_bess = st.number_input(f"BESS BAF ({curr_code}):", min_value=0.0, value=baf_base_val, step=100.0)
        baf_oog = st.number_input(f"OOG BAF ({curr_code}):", min_value=0.0, value=baf_base_val, step=100.0)
    with cb2:
        baf_mvs = st.number_input(f"MVS BAF ({curr_code}):", min_value=0.0, value=baf_base_val, step=100.0)
        baf_trans = st.number_input(f"Transformer BAF ({curr_code}):", min_value=0.0, value=baf_base_val, step=100.0)
    with cb3:
        baf_access = st.number_input(f"Accessory BAF ({curr_code}):", min_value=0.0, value=baf_base_val, step=100.0)
        baf_solar = st.number_input(f"Solar PV BAF ({curr_code}):", min_value=0.0, value=baf_base_val, step=100.0)

    if is_eur_display:
        baf_bess /= usd_to_eur; baf_oog /= usd_to_eur; baf_mvs /= usd_to_eur
        baf_trans /= usd_to_eur; baf_access /= usd_to_eur; baf_solar /= usd_to_eur

    st.markdown(f"#### 3. Destination Terminal Handling Charges (Destination THC) per Unit ({curr_code})")
    thc_mult = f_mult
    ct1, ct2, ct3 = st.columns(3)
    with ct1:
        dthc_bess = st.number_input(f"BESS Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_oog = st.number_input(f"OOG Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
    with ct2:
        dthc_mvs = st.number_input(f"MVS Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_trans = st.number_input(f"Transformer THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
    with ct3:
        dthc_access = st.number_input(f"Accessory THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_solar = st.number_input(f"Solar PV THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)

    if is_eur_display:
        dthc_bess /= usd_to_eur; dthc_oog /= usd_to_eur; dthc_mvs /= usd_to_eur
        dthc_trans /= usd_to_eur; dthc_access /= usd_to_eur; dthc_solar /= usd_to_eur

    st.markdown("---")
    cc1, cc2 = st.columns(2)
    with cc1:
        insurance_pct = st.number_input("Marine Insurance Rate (% of CIF):", min_value=0.0, value=0.15, step=0.05)
        customs_duty_pct = st.number_input("Customs Duty Rate (%) - BESS/General:", min_value=0.0, value=2.7, step=0.1)
    with cc2:
        mvs_customs_duty_pct = st.number_input("Customs Duty Rate (%) - MVS / Transformers:", min_value=0.0, value=0.0, step=0.1)
        st.info("Solar PV / Inverters are automatically 0% exempt under EU green energy trade regulations.")

with tab3:
    st.subheader("Port Storage, Demurrage & Inland Drayage (Heavy & Hazardous)")
    st.info("BESS transport reflects heavy oversized units (24-55t) carrying Class 9 Hazardous Materials.")
    
    st.markdown(f"#### 1. Port-to-Site Inland Drayage per Unit ({curr_code}) — Heavy Haulage / OOG")
    dr_mult = f_mult
    cd1, cd2, cd3 = st.columns(3)
    with cd1:
        dray_bess = st.number_input(f"BESS Trucking per unit (Heavy/Hazmat) ({curr_code}):", min_value=0.0, value=5500.0 * dr_mult, step=500.0)
        dray_oog = st.number_input(f"OOG Trucking per unit ({curr_code}):", min_value=0.0, value=6500.0 * dr_mult, step=500.0)
    with cd2:
        dray_mvs = st.number_input(f"MVS Trucking per unit ({curr_code}):", min_value=0.0, value=4500.0 * dr_mult, step=500.0)
        dray_trans = st.number_input(f"Transformer Trucking per unit ({curr_code}):", min_value=0.0, value=4800.0 * dr_mult, step=500.0)
    with cd3:
        dray_access = st.number_input(f"Accessory Trucking per unit ({curr_code}):", min_value=0.0, value=3000.0 * dr_mult, step=200.0)
        dray_solar = st.number_input(f"Solar PV Trucking per unit ({curr_code}):", min_value=0.0, value=3000.0 * dr_mult, step=200.0)

    if is_eur_display:
        dray_bess /= usd_to_eur; dray_oog /= usd_to_eur; dray_mvs /= usd_to_eur
        dray_trans /= usd_to_eur; dray_access /= usd_to_eur; dray_solar /= usd_to_eur

    st.markdown("---")
    st.markdown("#### 2. Port Demurrage (Shipping Line) & Port Storage (Terminal)")
    col_st1, col_st2 = st.columns(2)
    with col_st1:
        free_days = st.number_input("Port Free Days (Demurrage):", min_value=0, value=3, step=1)
        actual_port_days = st.number_input("Actual Port Days before clearance:", min_value=1, value=6, step=1)
        demurrage_daily_rate = st.number_input(f"Shipping Line Demurrage Daily Rate per unit ({curr_code}):", min_value=0.0, value=450.0 * dr_mult, step=50.0)
    with col_st2:
        use_external_storage = st.checkbox("Use External Storage Yard / Buffer", value=False)
        ext_storage_days = st.number_input("External Storage Days:", min_value=0, value=10, step=1) if use_external_storage else 0
        ext_storage_daily_rate = 250.0

    if is_eur_display:
        demurrage_daily_rate /= usd_to_eur

    include_delay_scenario = st.checkbox("Include Customs Delay Contingency Scenario (+7 Days)", value=True)

    st.markdown("---")
    st.markdown(f"#### 3. Site Crane & Heavy Unloading ({curr_code})")
    include_site_crane = st.checkbox("Include Site Crane & Unloading", value=True)
    site_crane_val = st.number_input(f"Total Crane & Unloading Cost ({curr_code}):", min_value=0.0, value=15000.0 * dr_mult, step=1000.0) if include_site_crane else 0.0
    site_crane_unloading = site_crane_val / usd_to_eur if is_eur_display else site_crane_val
with tab4:
    st.subheader("Regulation, Sustainability & Decommissioning")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        bp_val = st.number_input(f"Total Battery Passport Cost ({curr_code}):", min_value=0.0, value=10000.0 * dr_mult, step=1000.0)
        epr_val = st.number_input(f"Ongoing EPR Fee per BESS unit ({curr_code}):", min_value=0.0, value=450.0 * dr_mult, step=50.0)
    with col_t2:
        include_regulatory = st.checkbox("Include local site entry permits", value=True)
        perm_val = st.number_input(f"Local Permits Cost ({curr_code}):", min_value=0.0, value=5000.0 * dr_mult, step=500.0) if include_regulatory else 0.0
        include_mot_approval = st.checkbox("Include National/Local Approval Fees", value=False)
        mot_val = st.number_input(f"Approval Fees Cost ({curr_code}):", min_value=0.0, value=3000.0 * dr_mult, step=500.0) if include_mot_approval else 0.0

    if is_eur_display:
        battery_passport_total_usd = bp_val / usd_to_eur
        epr_recycling_total_usd = (epr_val / usd_to_eur) * bess_count
        local_regulatory_permits = perm_val / usd_to_eur
        mot_total_approval_cost = mot_val / usd_to_eur
    else:
        battery_passport_total_usd = bp_val
        epr_recycling_total_usd = epr_val * bess_count
        local_regulatory_permits = perm_val
        mot_total_approval_cost = mot_val

    st.markdown("---")
    st.markdown("#### Decommissioning & End-of-Life Financial Provision (EU Regulation Framework)")
    st.info("Future Provision (Benchmark 59–90 USD/kWh)")
    
    decom_scenario_choice = st.selectbox("Decommissioning Scenario Preset:", options=["Custom", "low (59 $/kWh)", "base (75 $/kWh)", "high (90 $/kWh)"], index=2)
    if "low" in decom_scenario_choice:
        decom_cost_per_kwh = 59.0
    elif "base" in decom_scenario_choice:
        decom_cost_per_kwh = 75.0
    elif "high" in decom_scenario_choice:
        decom_cost_per_kwh = 90.0
    else:
        decom_cost_per_kwh = st.number_input("Decommissioning Cost per kWh ($/kWh):", min_value=0.0, value=75.0, step=5.0)

    dc1, dc2 = st.columns(2)
    with dc1:
        years_to_decom = st.number_input("Years to Decommissioning:", min_value=1, value=20, step=1)
        decom_discount_rate = st.number_input("Discount Rate for PV (%):", min_value=0.0, value=4.0, step=0.5) / 100.0
    with dc2:
        decom_residual_per_kwh = st.number_input("Residual Material Recovery Value ($/kWh):", min_value=0.0, value=0.0, step=5.0)
        include_oog_in_decom = st.checkbox("Include OOG Units in Decommissioning Provision", value=False)

    net_decom_rate = max(0.0, decom_cost_per_kwh - decom_residual_per_kwh)
    preview_decom_per_bess = bess_capacity_mwh * 1000.0 * net_decom_rate
    preview_units_count = bess_count + (oog_count if include_oog_in_decom else 0)
    preview_total_decom = preview_decom_per_bess * float(preview_units_count)
    preview_pv_decom = preview_total_decom / ((1 + decom_discount_rate) ** years_to_decom) if years_to_decom > 0 else preview_total_decom
    
    st.success(f"**{bess_capacity_mwh} MWh** Per **{net_decom_rate:.1f} $/kWh** = **${preview_decom_per_bess:,.2f}** per container.\n* **Nominal Total:** ${preview_total_decom:,.2f} | **Present Value (PV):** ${preview_pv_decom:,.2f}")

    st.markdown("---")
    st.markdown("#### VAT & Contingency Settings")
    vc1, vc2 = st.columns(2)
    with vc1:
        default_vat = EUROPEAN_VAT_RATES.get(destination_country, 19.0)
        applied_vat = st.number_input("Import VAT Rate (%):", min_value=0.0, value=default_vat, step=0.5)
        vat_recovery_pct = st.number_input("VAT Recovery Rate (%):", min_value=0.0, value=100.0, step=5.0)
    with vc2:
        vat_paid_by_supplier = st.checkbox("Import VAT Paid Directly by Supplier", value=False)
        contingency_pct = st.number_input("Contingency Reserve (%):", min_value=0.0, value=5.0, step=1.0)

with tab5:
    st.subheader("🧭 Multi-Option Port-to-Door Routing Agent")
    
    # Value proposition explanation for the routing table
    st.markdown("""
    > **Module Value Proposition:** This routing agent scans international sea basins and European gateway hubs to present **complete port-to-door supply chain alternatives** (from Chinese origin ports to project destination sites). 
    > It allows easy comparison between ocean transit times, inland trucking distances, transit durations, and base costs to determine the most cost-effective routing strategy for renewable energy projects.
    """)

    EUROPEAN_LOGISTICS_HUB = {
        "Romania": {
            "site_name": "Bucharest / Ilfov / Ploiești Energy Hub (Romania)",
            "gateways": [
                {"port": "Constanta (Black Sea Main Gateway)", "ocean_days": 32, "inland_dist_km": 280, "inland_days": 3, "cost": 3600},
                {"port": "Varna / Burgas (Black Sea Secondary)", "ocean_days": 34, "inland_dist_km": 380, "inland_days": 4, "cost": 4100},
                {"port": "Koper (Adriatic Multimodal Gateway)", "ocean_days": 35, "inland_dist_km": 1100, "inland_days": 7, "cost": 6500},
                {"port": "Hamburg / Rotterdam (North Sea Corridor)", "ocean_days": 35, "inland_dist_km": 1800, "inland_days": 10, "cost": 8200}
            ]
        },
        "Germany": {
            "site_name": "Berlin / Frankfurt / Rhine-Ruhr Hub (Germany)",
            "gateways": [
                {"port": "Hamburg / Bremen (North Sea Main Gateway)", "ocean_days": 35, "inland_dist_km": 350, "inland_days": 3, "cost": 3800},
                {"port": "Rotterdam / Antwerp (Western Europe Gateway)", "ocean_days": 35, "inland_dist_km": 550, "inland_days": 4, "cost": 5200},
                {"port": "Koper (Adriatic Gateway)", "ocean_days": 35, "inland_dist_km": 850, "inland_days": 6, "cost": 6800}
            ]
        },
        "Italy": {
            "site_name": "Padova / Milan / Northern Italy Energy Hub",
            "gateways": [
                {"port": "Genoa / Trieste / Venice (Med/Adriatic Hub)", "ocean_days": 34, "inland_dist_km": 200, "inland_days": 2, "cost": 2100},
                {"port": "Koper / Rijeka (Adriatic Gateway)", "ocean_days": 35, "inland_dist_km": 300, "inland_days": 3, "cost": 3200},
                {"port": "Rotterdam / Antwerp (Northern Corridor)", "ocean_days": 35, "inland_dist_km": 1100, "inland_days": 7, "cost": 7500}
            ]
        },
        "Netherlands": {
            "site_name": "Amsterdam / Rotterdam Industrial & Energy Zone",
            "gateways": [
                {"port": "Rotterdam / Antwerp (Local Western Gateway)", "ocean_days": 35, "inland_dist_km": 60, "inland_days": 1, "cost": 600},
                {"port": "Hamburg / Bremen (North Sea Hub)", "ocean_days": 36, "inland_dist_km": 450, "inland_days": 4, "cost": 4200}
            ]
        },
        "Greece": {
            "site_name": "Athens / Attica / Central Greece Energy Hub",
            "gateways": [
                {"port": "Piraeus / Thessaloniki (Hellenic Main Gateway)", "ocean_days": 32, "inland_dist_km": 40, "inland_days": 1, "cost": 600},
                {"port": "Constanta / Black Sea Feeder", "ocean_days": 35, "inland_dist_km": 950, "inland_days": 8, "cost": 7200}
            ]
        }
    }

    selected_country = st.selectbox(
        "Select Target Project Destination Country:",
        list(EUROPEAN_LOGISTICS_HUB.keys()),
        key="smart_destination_country"
    )

    country_info = EUROPEAN_LOGISTICS_HUB[selected_country]
    
    routing_results = []
    china_ports = [
        "Shanghai (China)", 
        "Ningbo (China)", 
        "Yantian / Shenzhen (China)", 
        "Qingdao (China)", 
        "Xingang / Tianjin (China)"
    ]

    for gw in country_info["gateways"]:
        for china_port in china_ports:
            routing_results.append({
                "Origin Port (China)": china_port,
                "European Gateway": gw["port"],
                "Destination Site": country_info["site_name"],
                "Ocean Transit (Days)": gw["ocean_days"],
                "Inland Trucking Distance (km)": gw["inland_dist_km"],
                "Inland Trucking Days": gw["inland_days"],
                "Total Transit (Days)": gw["ocean_days"] + gw["inland_days"],
                "Base Trucking Cost (€)": gw["cost"],
                "Status": "Active & Verified"
            })

    if routing_results:
        df_routes = pd.DataFrame(routing_results)
        st.dataframe(df_routes, use_container_width=True, hide_index=True)
        st.success(f"Smart Agent successfully mapped routing alternatives for {selected_country}.")
    else:
        st.info("No routing options available for this selection.")
with tab6:
    st.subheader("Infrastructure & Energy Projects Intelligence")
    st.markdown(f"**Target Market Strategy:** Active infrastructure planning and logistics intelligence for **{destination_country}**.")
    st.markdown("""
    * **Heavy-Lift Corridor Management:** Ensuring axle-load compliance and bridge engineering surveys across main European corridors.
    * **Grid Connection Synchronisation:** Aligning MVS and transformer delivery schedules with high-voltage substation commissioning dates.
    * **Customs Compliance:** Strict adherence to EU TARIC classification for UN3536 Class 9 Lithium-Ion battery shipments.
    """)

with tab7:
    st.subheader("Financial & Environmental Control Report (Carbon & Cost)")
    
    results = calculate_project_costs(
        bess_count=bess_count, bess_exw=bess_exw,
        oog_count=oog_count, oog_exw=oog_exw,
        mvs_count=mvs_count, mvs_exw=mvs_exw,
        transformer_count=transformer_count, transformer_exw=transformer_exw,
        access_count=access_count, access_exw=access_exw,
        solar_count=solar_count, solar_exw=solar_exw,
        unit_freight_bess=unit_freight_bess, unit_freight_oog=unit_freight_oog, unit_freight_mvs=unit_freight_mvs,
        unit_freight_trans=unit_freight_trans, unit_freight_access=unit_freight_access, unit_freight_solar=unit_freight_solar,
        baf_bess=baf_bess, baf_oog=baf_oog, baf_mvs=baf_mvs, baf_trans=baf_trans, baf_access=baf_access, baf_solar=baf_solar,
        dthc_bess=dthc_bess, dthc_oog=dthc_oog, dthc_mvs=dthc_mvs, dthc_trans=dthc_trans, dthc_access=dthc_access, dthc_solar=dthc_solar,
        drayage_bess=dray_bess, drayage_oog=dray_oog, drayage_mvs=dray_mvs,
        drayage_trans=dray_trans, drayage_access=dray_access, drayage_solar=dray_solar,
        trend_multiplier=trend_multiplier, insurance_pct=insurance_pct,
        customs_duty_pct=customs_duty_pct, mvs_customs_duty_pct=mvs_customs_duty_pct,
        applied_vat=applied_vat, vat_recovery_pct=vat_recovery_pct,
        vat_paid_by_supplier=vat_paid_by_supplier, incoterm_code=incoterm_code,
        dest_country_code=dest_code,
        local_regulatory_permits=local_regulatory_permits, mot_total_approval_cost=mot_total_approval_cost,
        include_regulatory=include_regulatory, include_mot_approval=include_mot_approval,
        site_crane_unloading=site_crane_unloading, include_site_crane=include_site_crane,
        epr_recycling_total_usd=epr_recycling_total_usd, battery_passport_total_usd=battery_passport_total_usd,
        requires_heavy_lift=True, heavy_lift_survey_cost=2500.0,
        actual_port_days=actual_port_days, free_days=free_days, demurrage_daily_rate=demurrage_daily_rate,
        use_external_storage=use_external_storage, ext_storage_days=ext_storage_days,
        ext_storage_daily_rate=ext_storage_daily_rate, include_delay_scenario=include_delay_scenario,
        bess_capacity_mwh=bess_capacity_mwh, decom_cost_per_kwh=net_decom_rate,
        include_oog_in_decom=include_oog_in_decom, decom_cost_currency="USD",
        usd_to_eur=usd_to_eur, years_to_decom=years_to_decom, decom_discount_rate=decom_discount_rate,
        decom_residual_per_kwh=decom_residual_per_kwh, contingency_pct=contingency_pct
    )

    if results["decom_epr_overlap_warning"]:
        st.warning("⚠️ **Notice:** Both EPR recycling fees and Decommissioning provisions are active. Ensure there is no double-counting of end-of-life recycling scope.")

    disp_mult = usd_to_eur if is_eur_display else 1.0

    landed_disp = results["total_landed_cost_ex_vat"] * disp_mult
    economic_disp = results["economic_cost_ex_vat"] * disp_mult
    cash_disp = results["total_cash_requirement_incl_vat"] * disp_mult

    total_units_carbon = results["total_containers_project"]
    total_carbon_tons = total_units_carbon * 9.1

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Total Landed Cost ({curr_code})", format_currency(landed_disp, curr_code))
    m2.metric(f"Total Economic Cost ({curr_code})", format_currency(economic_disp, curr_code))
    m3.metric(f"Total Cash Requirement ({curr_code})", format_currency(cash_disp, curr_code))
    m4.metric("Estimated Carbon Footprint", f"{total_carbon_tons:,.1f} t CO2")

    st.markdown("---")
    st.markdown("#### Project Budget & Carbon Footprint Breakdown")
    
    raw_breakdown_data = [
        {"Cost Item": "Equipment EXW Value", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["trended_exw"] * disp_mult},
        {"Cost Item": "China Inland & Origin THC", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": (results["china_inland_drayage"] + results["china_origin_thc"]) * disp_mult},
        {"Cost Item": "Ocean Freight (Base)", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["total_base_ocean_freight"] * disp_mult},
        {"Cost Item": "Bunker Adjustment Factor (BAF)", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["total_baf_ocean"] * disp_mult},
        {"Cost Item": "Destination THC", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["destination_thc_total"] * disp_mult},
        {"Cost Item": "Marine Insurance", "Basis / Qty": f"{insurance_pct}% CIF", "RawAmount": results["insurance_total_usd"] * disp_mult},
        {"Cost Item": "Customs Duty", "Basis / Qty": f"Mixed Rates", "RawAmount": results["customs_duty_usd"] * disp_mult},
        {"Cost Item": "Inland Drayage (Port to Site)", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["inland_drayage_total_usd"] * disp_mult},
        {"Cost Item": "Regulatory & Local Permits", "Basis / Qty": "Expense", "RawAmount": results["active_regulatory_permits"] * disp_mult},
        {"Cost Item": "Site Crane & Heavy Unloading", "Basis / Qty": "Expense", "RawAmount": results["active_site_crane"] * disp_mult},
        {"Cost Item": "Shipping Line Demurrage", "Basis / Qty": f"{max(0, actual_port_days - free_days)} Days", "RawAmount": results["demurrage_total_usd"] * disp_mult},
        {"Cost Item": "Port Storage (External/Buffer)", "Basis / Qty": f"{ext_storage_days if use_external_storage else 0} Days", "RawAmount": results["external_storage_total_usd"] * disp_mult},
        {"Cost Item": "EPR / Recycling Fees", "Basis / Qty": f"{bess_count} BESS", "RawAmount": results["epr_recycling_total_usd"] * disp_mult},
        {"Cost Item": "EU Battery Passport", "Basis / Qty": "Global Compliance", "RawAmount": results["battery_passport_total_usd"] * disp_mult},
        {"Cost Item": "Heavy-Lift Survey", "Basis / Qty": "Survey", "RawAmount": results["active_heavy_lift"] * disp_mult},
        {"Cost Item": "Contingency Reserve", "Basis / Qty": f"{contingency_pct}%", "RawAmount": results["contingency_usd"] * disp_mult},
        {"Cost Item": "Decommissioning Provision (PV)", "Basis / Qty": f"{bess_capacity_mwh} MWh / unit", "RawAmount": results["decommissioning_pv_usd"] * disp_mult},
    ]

    breakdown_df = pd.DataFrame(raw_breakdown_data)
    
    display_df = breakdown_df.copy()
    display_df["Amount"] = display_df["RawAmount"].apply(lambda x: f"{'€' if is_eur_display else '$'} {x:,.2f}" if x > 0 else "-")
    display_df = display_df[["Cost Item", "Basis / Qty", "Amount"]]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    excel_export_df = breakdown_df[["Cost Item", "Basis / Qty", "RawAmount"]].copy()
    excel_export_df.rename(columns={"RawAmount": "Amount"}, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        excel_export_df.to_excel(writer, index=False, sheet_name='Budget Report')
    excel_data = output.getvalue()

    st.download_button(
        label="Download Budget & Carbon Report to Excel (.xlsx)",
        data=excel_data,
        file_name=f"Terra_Vol_Landed_Cost_Report_{dest_code}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with tab8:
    st.subheader("🧩 Multi-Shipment Planner — Carriers, SOC / COC & MPP")
    st.markdown(
        "Split the project into several shipments (different carriers, container lines or MPP vessels, "
        "different sailing dates). Each shipment is costed separately and summed into one project total. "
        "Edit the tables directly — use the **+** row at the bottom of a table to add a shipment or line."
    )

    CHINA_ORIGIN_PORTS = [
        "Shanghai", "Ningbo-Zhoushan", "Qingdao", "Shenzhen - Yantian",
        "Shenzhen - Shekou", "Guangzhou - Nansha", "Xingang / Tianjin", "Other"
    ]
    POD_OPTIONS = all_european_ports + ["Other"]

    if "msp_shipments" not in st.session_state:
        st.session_state.msp_shipments = pd.DataFrame([
            {"Shipment": "Shipment 1", "Carrier": "COSCO", "Service": "Container Line - SOC",
             "Origin Port": "Shanghai", "POD": POD_OPTIONS[0],
             "ETD": date(2027, 3, 1), "ETA": date(2027, 4, 5), "Currency": "USD",
             "Origin Charges / Unit": 350.0, "Port Days": 6, "Free Days": 3,
             "Daily Rate / Unit after Free Days": 100.0, "Extra Lump Sum": 0.0},
            {"Shipment": "Shipment 2", "Carrier": "MPP Operator", "Service": "MPP Vessel",
             "Origin Port": "Shanghai", "POD": POD_OPTIONS[0],
             "ETD": date(2027, 4, 1), "ETA": date(2027, 5, 10), "Currency": "USD",
             "Origin Charges / Unit": 350.0, "Port Days": 4, "Free Days": 3,
             "Daily Rate / Unit after Free Days": 100.0, "Extra Lump Sum": 5000.0},
            {"Shipment": "Shipment 3", "Carrier": "MSC", "Service": "Container Line - COC",
             "Origin Port": "Ningbo-Zhoushan", "POD": POD_OPTIONS[0],
             "ETD": date(2027, 3, 15), "ETA": date(2027, 4, 20), "Currency": "USD",
             "Origin Charges / Unit": 350.0, "Port Days": 6, "Free Days": 5,
             "Daily Rate / Unit after Free Days": 150.0, "Extra Lump Sum": 0.0},
        ])
        st.session_state.msp_lines = pd.DataFrame([
            {"Shipment": "Shipment 1", "Equipment": "BESS", "Qty": 10, "Currency": "USD",
             "Freight / Unit": 18000.0, "BAF / Unit": 0.0, "Dest. THC / Unit": 400.0, "Trucking / Unit": 5500.0},
            {"Shipment": "Shipment 2", "Equipment": "BESS", "Qty": 10, "Currency": "USD",
             "Freight / Unit": 21000.0, "BAF / Unit": 0.0, "Dest. THC / Unit": 0.0, "Trucking / Unit": 5500.0},
            {"Shipment": "Shipment 2", "Equipment": "MVS", "Qty": 4, "Currency": "USD",
             "Freight / Unit": 6000.0, "BAF / Unit": 0.0, "Dest. THC / Unit": 0.0, "Trucking / Unit": 4500.0},
            {"Shipment": "Shipment 3", "Equipment": "Accessory", "Qty": 2, "Currency": "USD",
             "Freight / Unit": 4000.0, "BAF / Unit": 1500.0, "Dest. THC / Unit": 400.0, "Trucking / Unit": 3000.0},
        ])

    st.markdown("#### 1. Shipments")
    st.caption(
        "Daily Rate after Free Days = carrier **demurrage** for COC containers, or terminal **port storage** "
        "for SOC containers and MPP cargo (no carrier demurrage on shipper-owned boxes). "
        "Extra Lump Sum = any one-off cost for the shipment (e.g. MPP port charges, lashing, surveys)."
    )
    edited_shipments = st.data_editor(
        st.session_state.msp_shipments,
        key="msp_shipments_editor",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "Shipment": st.column_config.TextColumn("Shipment", required=True),
            "Carrier": st.column_config.TextColumn("Carrier"),
            "Service": st.column_config.SelectboxColumn("Service", options=SERVICE_TYPES, required=True),
            "Origin Port": st.column_config.SelectboxColumn("Origin Port", options=CHINA_ORIGIN_PORTS),
            "POD": st.column_config.SelectboxColumn("POD", options=POD_OPTIONS),
            "ETD": st.column_config.DateColumn("ETD", format="DD/MM/YYYY"),
            "ETA": st.column_config.DateColumn("ETA", format="DD/MM/YYYY"),
            "Currency": st.column_config.SelectboxColumn("Currency", options=["USD", "EUR"], required=True),
            "Origin Charges / Unit": st.column_config.NumberColumn("Origin Charges / Unit", min_value=0.0, step=50.0, format="%.0f"),
            "Port Days": st.column_config.NumberColumn("Port Days", min_value=0, step=1),
            "Free Days": st.column_config.NumberColumn("Free Days", min_value=0, step=1),
            "Daily Rate / Unit after Free Days": st.column_config.NumberColumn("Daily Rate / Unit after Free Days", min_value=0.0, step=10.0, format="%.0f"),
            "Extra Lump Sum": st.column_config.NumberColumn("Extra Lump Sum", min_value=0.0, step=500.0, format="%.0f"),
        },
    )

    shipment_names = [str(n).strip() for n in edited_shipments["Shipment"].tolist()
                      if n is not None and str(n).strip() not in ("", "nan", "None")]
    if len(shipment_names) != len(set(shipment_names)):
        st.warning("⚠️ Two or more shipments have the same name. Please give each shipment a unique name.")

    st.markdown("#### 2. Equipment on Each Shipment")
    st.caption("One line per equipment type per shipment. Rates are per unit, in the currency selected on the line.")
    edited_lines = st.data_editor(
        st.session_state.msp_lines,
        key="msp_lines_editor",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "Shipment": st.column_config.SelectboxColumn("Shipment", options=sorted(set(shipment_names)), required=True),
            "Equipment": st.column_config.SelectboxColumn("Equipment", options=EQUIPMENT_TYPES, required=True),
            "Qty": st.column_config.NumberColumn("Qty", min_value=0, step=1),
            "Currency": st.column_config.SelectboxColumn("Currency", options=["USD", "EUR"], required=True),
            "Freight / Unit": st.column_config.NumberColumn("Freight / Unit", min_value=0.0, step=500.0, format="%.0f"),
            "BAF / Unit": st.column_config.NumberColumn("BAF / Unit", min_value=0.0, step=100.0, format="%.0f"),
            "Dest. THC / Unit": st.column_config.NumberColumn("Dest. THC / Unit", min_value=0.0, step=50.0, format="%.0f"),
            "Trucking / Unit": st.column_config.NumberColumn("Trucking / Unit", min_value=0.0, step=500.0, format="%.0f"),
        },
    )

    def _clean_date(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(v, "date") and callable(getattr(v, "date")):
            return v.date()
        return v

    msp_shipments = []
    for _, row in edited_shipments.iterrows():
        name = row.get("Shipment")
        if name is None or str(name).strip() in ("", "nan", "None"):
            continue
        msp_shipments.append({
            "name": str(name).strip(),
            "carrier": "" if pd.isna(row.get("Carrier")) else str(row.get("Carrier")),
            "service": row.get("Service") if row.get("Service") in SERVICE_TYPES else "Container Line - COC",
            "origin": "" if pd.isna(row.get("Origin Port")) else str(row.get("Origin Port")),
            "pod": "" if pd.isna(row.get("POD")) else str(row.get("POD")),
            "etd": _clean_date(row.get("ETD")),
            "eta": _clean_date(row.get("ETA")),
            "currency": row.get("Currency") or "USD",
            "origin_charges_per_unit": row.get("Origin Charges / Unit"),
            "port_days": row.get("Port Days"),
            "free_days": row.get("Free Days"),
            "daily_rate_per_unit": row.get("Daily Rate / Unit after Free Days"),
            "extra_lump_sum": row.get("Extra Lump Sum"),
        })

    msp_lines = []
    for _, row in edited_lines.iterrows():
        sh = row.get("Shipment")
        if sh is None or (not isinstance(sh, str) and pd.isna(sh)):
            continue
        msp_lines.append({
            "shipment": str(sh).strip(),
            "equipment": row.get("Equipment"),
            "qty": row.get("Qty"),
            "currency": row.get("Currency") or "USD",
            "freight_per_unit": row.get("Freight / Unit"),
            "baf_per_unit": row.get("BAF / Unit"),
            "dthc_per_unit": row.get("Dest. THC / Unit"),
            "trucking_per_unit": row.get("Trucking / Unit"),
        })

    msp_exw = {"BESS": bess_exw, "OOG": oog_exw, "MVS": mvs_exw, "Transformer": transformer_exw,
               "Accessory": access_exw, "Solar": solar_exw}
    msp_required = {"BESS": bess_count, "OOG": oog_count, "MVS": mvs_count, "Transformer": transformer_count,
                    "Accessory": access_count, "Solar": solar_count}
    msp_project_level = (
        results["active_regulatory_permits"] + results["active_site_crane"] +
        results["epr_recycling_total_usd"] + results["battery_passport_total_usd"] +
        results["active_heavy_lift"]
    )

    plan = calculate_shipment_plan(
        msp_shipments, msp_lines, msp_exw, msp_required,
        usd_to_eur=usd_to_eur, trend_multiplier=trend_multiplier,
        insurance_pct=insurance_pct, customs_duty_pct=customs_duty_pct,
        mvs_customs_duty_pct=mvs_customs_duty_pct,
        applied_vat=applied_vat, vat_recovery_pct=vat_recovery_pct, dest_country_code=dest_code,
        project_level_costs_usd=msp_project_level, contingency_pct=contingency_pct,
        decommissioning_pv_usd=results["decommissioning_pv_usd"],
    )

    msp_mult = usd_to_eur if is_eur_display else 1.0
    msp_sym = "€" if is_eur_display else "$"

    def _fmt(x):
        return f"{msp_sym} {x * msp_mult:,.0f}" if x else "-"

    # --- Coverage check ---
    st.markdown("#### 3. Equipment Coverage Check")
    if plan["coverage"]:
        cov_df = pd.DataFrame(plan["coverage"]).rename(columns={
            "equipment": "Equipment", "required": "Required (Tab 1)", "allocated": "On Shipments",
            "difference": "Difference", "status": "Status"})
        st.dataframe(cov_df, use_container_width=True, hide_index=True)
    if plan["coverage_ok"]:
        st.success("✅ All project equipment is allocated to shipments exactly once.")
    else:
        st.warning("⚠️ Equipment allocation does not match the quantities in the Equipment Mix tab. "
                   "The totals below only include what is on the shipments.")
    if plan["orphan_lines"]:
        st.warning(f"⚠️ {len(plan['orphan_lines'])} equipment line(s) point to a shipment name that no longer exists "
                   "and are not counted. Re-select the shipment on those lines.")

    # --- Per-shipment costs ---
    st.markdown(f"#### 4. Cost per Shipment ({curr_code})")
    rows = []
    for r in plan["shipments"]:
        rows.append({
            "Shipment": r["name"],
            "Carrier": r["carrier"],
            "Service": r["service"],
            "Units": r["units"],
            "ETD": r["etd"].strftime("%d/%m/%Y") if r["etd"] else "",
            "ETA": r["eta"].strftime("%d/%m/%Y") if r["eta"] else "",
            "Transit (Days)": r["transit_days"] if r["transit_days"] is not None else "",
            "Equipment Value": _fmt(r["goods_value"]),
            "Origin Charges": _fmt(r["origin_charges"]),
            "Ocean Freight + BAF": _fmt(r["freight"] + r["baf"]),
            "Insurance": _fmt(r["insurance"]),
            "Customs Duty": _fmt(r["duty"]),
            "Dest. THC": _fmt(r["dthc"]),
            "Inland Trucking": _fmt(r["trucking"]),
            "Demurrage / Storage": (f"{_fmt(r['port_delay'])} ({r['delay_label']}, {r['overdue_days']}d)"
                                    if r["port_delay"] else "-"),
            "Extra": _fmt(r["extra"]),
            "Logistics Total (ex VAT)": _fmt(r["logistics_ex_vat"]),
            "Shipment Total (ex VAT)": _fmt(r["total_ex_vat"]),
            "Import VAT": _fmt(r["vat"]),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Add at least one shipment and one equipment line to see costs.")

    # --- Project totals ---
    st.markdown(f"#### 5. Project Total — All Shipments ({curr_code})")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Logistics Cost (all shipments, ex VAT)", format_currency(plan["logistics_total_ex_vat"] * msp_mult, curr_code))
    t2.metric("Total Landed Cost (ex VAT)", format_currency(plan["landed_ex_vat"] * msp_mult, curr_code))
    t3.metric("Total Cash Requirement (incl. VAT)", format_currency(plan["cash_incl_vat"] * msp_mult, curr_code))
    t4.metric("Total Economic Cost", format_currency(plan["economic_cost"] * msp_mult, curr_code))

    summary_rows = [
        {"Item": "Equipment value (EXW × trend)", "Amount": _fmt(plan["goods_total"])},
        {"Item": "Logistics, insurance & duty — all shipments", "Amount": _fmt(plan["logistics_total_ex_vat"])},
        {"Item": "Project-level costs (permits, site crane, EPR, battery passport, heavy-lift survey)", "Amount": _fmt(plan["project_level_costs"])},
        {"Item": f"Contingency ({contingency_pct}%)", "Amount": _fmt(plan["contingency"])},
        {"Item": "Total Landed Cost (ex VAT)", "Amount": _fmt(plan["landed_ex_vat"])},
        {"Item": f"Import VAT ({applied_vat}%) — recoverable {vat_recovery_pct}%", "Amount": _fmt(plan["vat_total"])},
    ]
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Insurance, duty, VAT, contingency and project-level costs use the settings from the other tabs. "
        "Freight rates entered here are treated as actual quotes, so the trend multiplier is applied to equipment value only."
    )
st.markdown("---")
st.markdown("---")
st.markdown("### 🤖 Multi-Option Port-to-Door Routing Agent")

# Collect all unique destination project sites across all ports in the matrix
all_destinations = sorted(list(set(
    dest 
    for port_data in LOGISTICS_NETWORK.values() 
    for dest in port_data["destinations"].keys()
)))

selected_target_dest = st.selectbox("Select Target Project Destination / Site:", all_destinations)

st.markdown(f"#### Available Routing Alternatives for: **{selected_target_dest}**")

# Scan all ports and find which ones can reach this destination
routes_found = []
for port_name, port_data in LOGISTICS_NETWORK.items():
    if selected_target_dest in port_data["destinations"]:
        route_info = port_data["destinations"][selected_target_dest]
        routes_found.append({
            "Origin Port": port_name,
            "Destination": selected_target_dest,
            "Inland Distance (km)": route_info["distance_km"],
            "Inland Transit (Days)": route_info["transit_days"],
            "Base Trucking Cost (USD)": route_info["base_trucking_cost"]
        })

if routes_found:
    routes_df = pd.DataFrame(routes_found)
    # Sort options by cheapest trucking cost first
    routes_df = routes_df.sort_values(by="Base Trucking Cost (USD)")
    
    st.dataframe(routes_df, use_container_width=True, hide_index=True)
    st.success("💡 Agent scanned all sea basins and presented all possible origin ports for this destination, sorted by cost-effectiveness.")
else:
    st.warning("No direct routes found for this destination in the current network matrix.")

st.markdown("---")
st.caption(f"© {date.today().year} Terra Vol. Advanced Renewable Energy & Infrastructure Venture.")
