import streamlit as st
import pandas as pd
import os
import io
import json
import importlib
from datetime import date
import calc as _calc_module
importlib.reload(_calc_module)  # always load the latest calc.py after an update (no app reboot needed)
from calc import get_live_exchange_rate, convert_currency, format_currency, calculate_project_costs
from calc import calculate_shipment_plan, EQUIPMENT_TYPES, SERVICE_TYPES, CONTAINER_SIZES, teu_factor

CARRIERS = ["MSC", "Maersk", "CMA CGM", "COSCO Shipping", "Hapag-Lloyd", "Evergreen Line", "ONE", "HMM",
            "ZIM", "Yang Ming", "OOCL", "Sea Legend"]


def load_baf_rates(path="baf_rates.json"):
    """Monthly fuel-surcharge table (BAF / EFS per TEU) maintained by a scheduled task."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"carriers": {}, "lanes": [], "last_run": None}


def port_to_lane(port):
    """Map a port of destination to the carriers' trade lane (origin China)."""
    p = (port or "").lower()
    if any(k in p for k in ["israel", "haifa", "ashdod", "eilat", "piraeus", "thessaloniki", "greece"]):
        return "China - East Med / Israel"
    if any(k in p for k in ["constan", "varna", "burgas", "romania", "bulgaria", "black sea"]):
        return "China - Black Sea"
    if any(k in p for k in ["koper", "trieste", "venice", "rijeka", "slovenia", "adriatic"]):
        return "China - Adriatic"
    if any(k in p for k in ["genoa", "valencia", "marseille", "barcelona", "spain", "france"]):
        return "China - West Med"
    if any(k in p for k in ["rotterdam", "antwerp", "hamburg", "bremerhaven", "gdansk", "gdynia",
                            "helsinki", "kotka", "netherlands", "germany", "poland", "belgium", "finland"]):
        return "China - North Europe"
    return None


def lookup_surcharge(rates, carrier, port):
    """Return the rates-file entry for a carrier + destination port, or None."""
    lane = port_to_lane(port)
    if not lane:
        return None
    name = (carrier or "").strip().lower()
    for c, lanes in rates.get("carriers", {}).items():
        if c.lower() == name or (name and (name in c.lower() or c.lower() in name)):
            entry = lanes.get(lane)
            if entry and entry.get("baf_usd_per_teu") is not None:
                return dict(entry, carrier=c, lane=lane)
    return None


BAF_RATES = load_baf_rates()

st.set_page_config(
    page_title="Terra Vol | Global BESS Project Calculator",
    page_icon="⚡",
    layout="wide"
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
    "Romania": 21.0,   # 21% since 1 Aug 2025
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
    "Slovakia": 23.0,  # 23% since 1 Jan 2025
    "Croatia": 25.0,
    "Israel": 18.0
}
VAT_TABLE_VERIFIED = "November 2026"  # standard rates checked against published 2026 EU tables / Israel Tax Authority
# Israeli sea ports (Mediterranean + Red Sea)
ISRAEL_PORTS = [
    "Haifa Bay Port (SIPG), Israel",
    "Haifa Port (Adani), Israel",
    "Israel Shipyards Port (Haifa), Israel",
    "Ashdod Port, Israel",
    "TIL - Hadarom South Port (Ashdod), Israel",
    "Eilat Port, Israel",
]
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

COUNTRY_CODES = {"Israel": "IL"}
dest_code = COUNTRY_CODES.get(destination_country, destination_country[:2].upper())
is_israel = (dest_code == "IL")

all_european_ports = [
    "Constanța, Romania", "Varna, Bulgaria", "Burgas, Bulgaria", 
    "Gdansk, Poland", "Gdynia, Poland", "Koper, Slovenia (Rail Gateway)", 
    "Trieste, Italy", "Venice, Italy", "Genoa, Italy", 
    "Piraeus, Greece", "Thessaloniki, Greece", 
    "Hamburg, Germany", "Bremerhaven, Germany", 
    "Rotterdam, Netherlands", "Antwerp, Belgium", 
    "Helsinki / Kotka, Finland", "Valencia, Spain", "Marseille, France"
]
destination_ports = ISRAEL_PORTS if is_israel else all_european_ports

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

with tab1:
    st.markdown("---")
    st.markdown("#### Energy & Power Capacity")
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh, DC nameplate):", min_value=0.5, value=4.0, step=0.5)
    with ec2:
        project_mwac = st.number_input("Project Power (MWac) — optional:", min_value=0.0, value=0.0, step=1.0,
                                       help="Inverter / PCS AC rating at the point of interconnection. Leave 0 to hide $/kW.")
    with ec3:
        project_mwh_ac = st.number_input("Usable Energy at POI (MWh AC) — optional:", min_value=0.0, value=0.0, step=1.0,
                                         help="Contracted usable AC energy at the point of interconnection. Leave 0 to hide $/kWh AC.")
    project_kwh_dc = bess_count * bess_capacity_mwh * 1000.0
    st.caption(f"Project DC nameplate energy: **{project_kwh_dc / 1000.0:,.1f} MWh** "
               f"({bess_count} BESS × {bess_capacity_mwh:g} MWh). Cost-per-kWh metrics use this as the default basis.")


def render_unit_cost_metrics(logistics_usd, landed_usd, exw_usd, mult, code, label_suffix=""):
    """Industry KPIs: cost per kWh / MWh on DC nameplate, plus optional AC usable energy and $/kW."""
    sym = "€" if code == "EUR" else "$"
    if project_kwh_dc <= 0:
        st.info("Add BESS containers and capacity (Equipment tab) to see cost per kWh / MWh.")
        return
    st.markdown(f"##### Unit Cost KPIs — basis: DC nameplate {project_kwh_dc / 1000.0:,.1f} MWh{label_suffix}")
    k1, k2, k3 = st.columns(3)
    for col, title, val in [
        (k1, "Logistics & Import Cost", logistics_usd),
        (k2, "Total Landed Cost", landed_usd),
        (k3, "Equipment EXW", exw_usd),
    ]:
        per_kwh = val * mult / project_kwh_dc
        col.metric(f"{title} per kWh (DC)", f"{sym} {per_kwh:,.2f}", help=f"{sym} {per_kwh * 1000:,.0f} per MWh")
        col.caption(f"= {sym} {per_kwh * 1000:,.0f} / MWh")
    if project_mwh_ac > 0 or project_mwac > 0:
        a1, a2, a3 = st.columns(3)
        if project_mwh_ac > 0:
            a1.metric("Landed Cost per kWh (AC usable at POI)", f"{sym} {landed_usd * mult / (project_mwh_ac * 1000):,.2f}")
            a2.metric("Logistics & Import per kWh (AC usable)", f"{sym} {logistics_usd * mult / (project_mwh_ac * 1000):,.2f}")
        if project_mwac > 0:
            a3.metric("Landed Cost per kW (AC)", f"{sym} {landed_usd * mult / (project_mwac * 1000):,.0f}")


with tab2:
    st.subheader("Ocean Freight, BAF & Destination THC")
    
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        shipping_line = st.selectbox("Shipping Line / Carrier:", CARRIERS)
        origin_port = st.selectbox("Origin Port (China):", [
            "Shanghai, China - SIPG (Waigaoqiao / Yangshan)",
            "Ningbo-Zhoushan, China - Beilun Terminal",
            "Qingdao, China - Qianwan Terminal",
            "Shenzhen, China - Yantian International Container Terminal (YICT)",
            "Shenzhen, China - Shekou Container Terminal (SCT)",
            "Guangzhou, China - Nansha Port"
        ])
    with col_sc2:
        dest_port = st.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=destination_ports, index=0)
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

    st.markdown("#### 2. Container Size per Equipment Type")
    st.caption("Carriers publish BAF / EFS per TEU: 20ft = 1 TEU, 40ft / 40ft HC = 2 TEU. "
               "A 10ft SOC normally takes a 20ft slot and is billed as 1 TEU (adjustable below).")
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1:
        size_bess = st.selectbox("BESS container size:", CONTAINER_SIZES[:4], index=1, key="size_bess")
        size_oog = st.selectbox("OOG unit size:", CONTAINER_SIZES[:4], index=2, key="size_oog")
    with cs2:
        size_mvs = st.selectbox("MVS container size:", CONTAINER_SIZES[:4], index=1, key="size_mvs")
        size_trans = st.selectbox("Transformer size:", CONTAINER_SIZES[:4], index=1, key="size_trans")
    with cs3:
        size_access = st.selectbox("Accessory container size:", CONTAINER_SIZES[:4], index=3, key="size_access")
        size_solar = st.selectbox("Solar PV container size:", CONTAINER_SIZES[:4], index=3, key="size_solar")
    with cs4:
        ten_ft_teu = st.number_input("10ft container billed as (TEU):", min_value=0.5, max_value=1.0, value=1.0, step=0.5,
                                     key="ten_ft_teu")

    st.markdown(f"#### 3. Fuel Surcharges per TEU — BAF & EFS ({curr_code})")
    auto_baf = lookup_surcharge(BAF_RATES, shipping_line, dest_port)
    if auto_baf:
        st.caption(f"📡 Auto-filled from the monthly surcharge table: **{auto_baf['carrier']} — {auto_baf['lane']}** · "
                   f"{auto_baf.get('baf_name') or 'BAF'} effective {auto_baf.get('effective_from') or '-'} · "
                   f"checked {auto_baf.get('verified_on') or '-'}"
                   + (f" · [source]({auto_baf['source_url']})" if auto_baf.get('source_url') else ""))
    else:
        st.caption(f"No published surcharge on file for **{shipping_line}** to this port yet — enter the BAF from your quote.")
    include_baf_in_freight = st.checkbox("Ocean Freight already includes BAF", value=False)
    auto_baf_usd = float(auto_baf["baf_usd_per_teu"]) if auto_baf else 600.0
    auto_efs_usd = float(auto_baf["efs_usd_per_teu"]) if (auto_baf and auto_baf.get("efs_usd_per_teu") is not None) else 0.0

    bf1, bf2, bf3 = st.columns(3)
    with bf1:
        baf_per_teu_in = st.number_input(f"BAF per TEU ({curr_code}):", min_value=-2000.0,
                                         value=0.0 if include_baf_in_freight else round(auto_baf_usd * f_mult, 2),
                                         step=10.0, disabled=include_baf_in_freight)
    with bf2:
        apply_efs = st.checkbox("Apply Emergency Fuel Surcharge (EFS)", value=bool(auto_efs_usd))
    with bf3:
        efs_per_teu_in = st.number_input(f"EFS per TEU ({curr_code}):", min_value=0.0,
                                         value=round(auto_efs_usd * f_mult, 2), step=10.0, disabled=not apply_efs)

    baf_per_teu_usd = 0.0 if include_baf_in_freight else (baf_per_teu_in / usd_to_eur if is_eur_display else baf_per_teu_in)
    efs_per_teu_usd = (efs_per_teu_in / usd_to_eur if is_eur_display else efs_per_teu_in) if apply_efs else 0.0

    teu_bess, teu_oog = teu_factor(size_bess, ten_ft_teu), teu_factor(size_oog, ten_ft_teu)
    teu_mvs, teu_trans = teu_factor(size_mvs, ten_ft_teu), teu_factor(size_trans, ten_ft_teu)
    teu_access, teu_solar = teu_factor(size_access, ten_ft_teu), teu_factor(size_solar, ten_ft_teu)

    # Per-unit fuel surcharges in USD (BAF + EFS) passed to the cost engine
    fuel_per_teu_usd = baf_per_teu_usd + efs_per_teu_usd
    baf_bess, baf_oog = fuel_per_teu_usd * teu_bess, fuel_per_teu_usd * teu_oog
    baf_mvs, baf_trans = fuel_per_teu_usd * teu_mvs, fuel_per_teu_usd * teu_trans
    baf_access, baf_solar = fuel_per_teu_usd * teu_access, fuel_per_teu_usd * teu_solar
    project_teu = (bess_count * teu_bess + oog_count * teu_oog + mvs_count * teu_mvs +
                   transformer_count * teu_trans + access_count * teu_access + solar_count * teu_solar)
    st.info(f"Project volume: **{project_teu:g} TEU** · fuel surcharges = {project_teu:g} TEU × "
            f"({'BAF' + (' + EFS' if apply_efs else '')}) per TEU.")

    st.markdown(f"#### 4. Destination Terminal Handling Charges (Destination THC) per Unit ({curr_code})")
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

    st.markdown(f"#### 5. Origin Charges in China per Container ({curr_code})")
    oc1, oc2 = st.columns(2)
    with oc1:
        origin_truck_in = st.number_input(f"Factory-to-port trucking per container ({curr_code}):", min_value=0.0,
                                          value=round(220.0 * f_mult, 2), step=10.0)
    with oc2:
        origin_thc_in = st.number_input(f"Origin THC & export handling per container ({curr_code}):", min_value=0.0,
                                        value=round(130.0 * f_mult, 2), step=10.0)
    origin_truck_usd = origin_truck_in / usd_to_eur if is_eur_display else origin_truck_in
    origin_thc_usd = origin_thc_in / usd_to_eur if is_eur_display else origin_thc_in

    st.markdown("---")
    cc1, cc2 = st.columns(2)
    with cc1:
        insurance_pct = st.number_input("Marine Insurance Rate (% of CIF):", min_value=0.0, value=0.15, step=0.05)
        customs_duty_pct = st.number_input("Customs Duty Rate (%) - BESS/General:", min_value=0.0, value=(0.0 if is_israel else 2.7), step=0.1)
    with cc2:
        mvs_customs_duty_pct = st.number_input("Customs Duty Rate (%) - MVS / Transformers:", min_value=0.0, value=0.0, step=0.1)
        if is_israel:
            st.info("🇮🇱 Israel: no customs duty on BESS, MVS or transformers (default 0%). "
                    "Solar PV / Inverters are calculated at 0%. Verify the HS classification with your customs broker.")
        else:
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

    st.markdown(f"#### 4. Heavy-Lift Route Survey ({curr_code})")
    requires_heavy_lift = st.checkbox("Include heavy-lift / route survey (bridges, axle loads, turning radius)", value=True)
    heavy_lift_val = st.number_input(f"Route survey cost ({curr_code}):", min_value=0.0, value=round(2500.0 * dr_mult, 2),
                                     step=500.0) if requires_heavy_lift else 0.0
    heavy_lift_usd = heavy_lift_val / usd_to_eur if is_eur_display else heavy_lift_val
with tab4:
    st.subheader("Regulation, Sustainability & Decommissioning")
    
    has_toxins_permit = True  # only relevant for Israel
    toxins_missing_text = ""
    include_decom_israel = False
    if is_israel:
        st.markdown("#### 🇮🇱 Israel — Import & Transport Regulation")

        st.markdown("##### 1. Toxins Permit (Hebrew: היתר רעלים) — Israel Ministry of Environmental Protection")
        st.caption("Lithium-ion BESS are regulated under the Israeli Hazardous Substances Law. "
                   "The Ministry now requires a Toxins Permit both from the **importer / consignee** and for the **project site**.")
        tp1, tp2 = st.columns(2)
        with tp1:
            has_importer_permit = st.checkbox("Importer / consignee holds a valid Toxins Permit", value=False)
        with tp2:
            has_site_permit = st.checkbox("Project site holds a valid Toxins Permit", value=False)
        has_toxins_permit = has_importer_permit and has_site_permit
        missing = []
        if not has_importer_permit:
            missing.append(
                "* **Importer / consignee permit missing** — BESS units **cannot be released from an external storage "
                "terminal** (e.g. a bonded or off-port yard). Israel Customs also requires the importer's permit — "
                "**not yet enforced, but enforcement may start at any time.**")
        if not has_site_permit:
            missing.append(
                "* **Site permit missing** — the project site (developer / site operator) needs its own Toxins Permit "
                "to receive and store the BESS on site. Coordinate with the developer / EPC before the first delivery.")
        if missing:
            st.error("⚠️ **Toxins Permit — action required before the BESS arrive.**\n\n" + "\n".join(missing) +
                     "\n\n* Apply well before the first vessel arrives; a missing permit means extra storage days and demurrage.")
        else:
            st.success("✅ Toxins Permits confirmed for importer and site. Make sure both are valid for the whole delivery "
                       "period and cover lithium-ion batteries.")
        toxins_missing_text = " and ".join(
            ([] if has_importer_permit else ["importer / consignee"]) + ([] if has_site_permit else ["project site"]))
        toxins_val = st.number_input(f"Toxins Permits — one-time cost, importer + site (application, consultant, toxins officer) ({curr_code}):",
                                     min_value=0.0, value=0.0, step=500.0)

        st.markdown("##### 2. Ministry of Transport — Oversize / Heavy Transport Permit per BESS Container (Hebrew: היתר הובלה)")
        st.info(
            f"Every BESS container requires a transport permit from the Israel Ministry of Transport "
            f"for the port-to-site haul — **{bess_count} permit(s)** for this project. "
            "Currently there is no fee, but submit the requests early so trucks are not held at the port."
        )
        mot_per_unit_val = st.number_input(f"MoT transport permit cost per BESS container ({curr_code}):",
                                           min_value=0.0, value=0.0, step=50.0)
        include_mot_approval = True
        mot_val = mot_per_unit_val * bess_count

        st.markdown("##### 3. Site Permits & Other Costs")
        st.caption("Site works permits (building, fire department, electrical, etc.) are normally the EPC / site contractor's "
                   "responsibility and are not included unless entered below.")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            other_permits_val = st.number_input(f"Other permits / consultants ({curr_code}):", min_value=0.0, value=0.0, step=500.0)
        with col_t2:
            epr_val = st.number_input(
                f"Battery recycling / EPR fee per BESS unit ({curr_code}):", min_value=0.0, value=0.0, step=50.0,
                help="Israeli e-waste & batteries law — recycling through a recognised body (e.g. M.A.I / T.M.I). "
                     "Check with the recycling body whether it applies to your BESS units.")
        include_regulatory = True
        perm_val = toxins_val + other_permits_val
        bp_val = 0.0  # EU Battery Passport does not apply in Israel
    else:
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
    if is_israel:
        include_decom_israel = st.checkbox(
            "Include a decommissioning provision in the Israel budget (optional — EU framework does not apply)", value=False)
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
        st.caption(f"Default: standard VAT rate of {destination_country} ({default_vat:g}%), verified {VAT_TABLE_VERIFIED}. "
                   "Confirm with your customs broker for the specific HS code.")
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

    route_countries = list(EUROPEAN_LOGISTICS_HUB.keys()) + ["Israel"]
    # Always follow the destination country chosen in the sidebar (single source of truth)
    selected_country = destination_country
    st.markdown(f"**Destination country:** {destination_country} *(change it in the sidebar)*")

    china_ports = [
        "Shanghai (China)", 
        "Ningbo (China)", 
        "Yantian / Shenzhen (China)", 
        "Qingdao (China)", 
        "Xingang / Tianjin (China)"
    ]

    if selected_country == "Israel":
        # Road distance (km) from each port cluster to each site region — indicative, editable below
        ISRAEL_REGIONS = {
            "North — Haifa / Galilee / Jezreel Valley": {"Haifa": 40, "Ashdod": 160, "Eilat": 400},
            "Center — Sharon / Gush Dan / Shfela": {"Haifa": 100, "Ashdod": 50, "Eilat": 330},
            "South — Negev / Be'er Sheva / Dimona": {"Haifa": 210, "Ashdod": 90, "Eilat": 230},
            "Arava / Eilat": {"Haifa": 400, "Ashdod": 300, "Eilat": 30},
        }
        ISRAEL_PORT_CLUSTER = {
            "Haifa Bay Port (SIPG), Israel": ("Haifa", 38),
            "Haifa Port (Adani), Israel": ("Haifa", 38),
            "Israel Shipyards Port (Haifa), Israel": ("Haifa", 38),
            "Ashdod Port, Israel": ("Ashdod", 38),
            "TIL - Hadarom South Port (Ashdod), Israel": ("Ashdod", 38),
            "Eilat Port, Israel": ("Eilat", 22),
        }

        ir1, ir2, ir3 = st.columns(3)
        with ir1:
            il_region = st.selectbox("Project Site Region (Israel):", list(ISRAEL_REGIONS.keys()), key="il_route_region")
        with ir2:
            il_base_cost = st.number_input("Heavy-haul base cost per BESS unit (USD):", min_value=0.0, value=1500.0, step=100.0, key="il_base_cost")
        with ir3:
            il_km_rate = st.number_input("Heavy-haul rate per km per BESS unit (USD):", min_value=0.0, value=12.0, step=1.0, key="il_km_rate")

        st.caption("Ocean transit days and road distances are **indicative defaults** — edit them in the table to match "
                   "current carrier schedules (Suez vs. Cape routing) and the exact site location. "
                   "Check that the Eilat port currently has a service for your cargo before relying on it.")

        il_defaults = pd.DataFrame([
            {"Israeli Port": port,
             "Ocean Transit from China (Days)": days,
             "Road Distance to Site (km)": ISRAEL_REGIONS[il_region][cluster]}
            for port, (cluster, days) in ISRAEL_PORT_CLUSTER.items()
        ])
        il_edit = st.data_editor(
            il_defaults, key=f"il_routes_{il_region}", hide_index=True, use_container_width=True,
            disabled=["Israeli Port"],
            column_config={
                "Ocean Transit from China (Days)": st.column_config.NumberColumn(min_value=0, step=1),
                "Road Distance to Site (km)": st.column_config.NumberColumn(min_value=0, step=5),
            },
        )

        il_rows = []
        for _, r in il_edit.iterrows():
            km = float(r["Road Distance to Site (km)"] or 0)
            ocean = int(r["Ocean Transit from China (Days)"] or 0)
            inland_days = 1 if km <= 150 else 2
            cost_unit = il_base_cost + il_km_rate * km
            il_rows.append({
                "Israeli Port": r["Israeli Port"],
                "Destination Site": il_region,
                "Ocean Transit (Days)": ocean,
                "Road Distance (km)": int(km),
                "Inland Days (night convoy)": inland_days,
                "Total Transit (Days)": ocean + inland_days,
                "Trucking per BESS (USD)": round(cost_unit),
                f"Trucking — {bess_count} BESS (USD)": round(cost_unit * bess_count),
                "MoT Transport Permits": f"{bess_count} required",
            })
        il_df = pd.DataFrame(il_rows).sort_values(by=["Trucking per BESS (USD)", "Total Transit (Days)"])
        st.markdown("#### Port-to-Site Options — sorted by trucking cost")
        st.dataframe(il_df, use_container_width=True, hide_index=True)
        best = il_df.iloc[0]
        st.success(f"Lowest trucking cost: **{best['Israeli Port']}** — {best['Road Distance (km)']} km to site, "
                   f"total transit ≈ {best['Total Transit (Days)']} days.")
        if not has_toxins_permit:
            st.warning(f"Reminder: Toxins Permit missing for the {toxins_missing_text} — without the importer's permit BESS "
                       "cannot be released from an external storage terminal; keep this in mind when comparing ports with off-port yards.")
    elif selected_country not in EUROPEAN_LOGISTICS_HUB:
        st.info(f"Route options for **{selected_country}** are not available yet. "
                f"Currently covered: {', '.join(route_countries)}. "
                "Use the Multi-Shipment Planner to cost specific routes for this country.")
    else:
        country_info = EUROPEAN_LOGISTICS_HUB[selected_country]
        routing_results = []
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
    if is_israel:
        st.markdown("""
    * **Israel — Toxins Permits:** required by the Ministry of Environmental Protection from the importer / consignee and for the project site.
    * **Israel — MoT Transport Permits:** one oversize/heavy transport permit per BESS container for the port-to-site haul.
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
        requires_heavy_lift=requires_heavy_lift, heavy_lift_survey_cost=heavy_lift_usd,
        actual_port_days=actual_port_days, free_days=free_days, demurrage_daily_rate=demurrage_daily_rate,
        use_external_storage=use_external_storage, ext_storage_days=ext_storage_days,
        ext_storage_daily_rate=ext_storage_daily_rate, include_delay_scenario=include_delay_scenario,
        bess_capacity_mwh=bess_capacity_mwh, decom_cost_per_kwh=net_decom_rate,
        include_oog_in_decom=include_oog_in_decom, decom_cost_currency="USD",
        usd_to_eur=usd_to_eur, years_to_decom=years_to_decom, decom_discount_rate=decom_discount_rate,
        decom_residual_per_kwh=decom_residual_per_kwh, contingency_pct=contingency_pct,
        apply_decommissioning=(include_decom_israel if is_israel else None),
        origin_trucking_per_unit=origin_truck_usd, origin_thc_per_unit=origin_thc_usd,
    )

    if is_israel and not has_toxins_permit:
        st.error(f"⚠️ **Israel — Toxins Permit missing for the {toxins_missing_text}.** Without the importer's permit BESS "
                 "cannot be released from an external storage terminal; without the site permit they cannot be received "
                 "and stored on site. See the Regulation tab.")

    if results["decom_epr_overlap_warning"]:
        st.warning("⚠️ **Notice:** Both EPR recycling fees and Decommissioning provisions are active. Ensure there is no double-counting of end-of-life recycling scope.")

    disp_mult = usd_to_eur if is_eur_display else 1.0
    efs_total_usd = project_teu * efs_per_teu_usd * trend_multiplier

    landed_disp = results["total_landed_cost_ex_vat"] * disp_mult
    economic_disp = results["economic_cost_ex_vat"] * disp_mult
    cash_disp = results["total_cash_requirement_incl_vat"] * disp_mult

    total_units_carbon = results["total_containers_project"]
    carbon_per_unit = st.number_input(
        "Transport CO2 factor (t CO2 per container, origin to site):", min_value=0.0, value=9.1, step=0.1,
        help="Indicative well-to-wheel estimate for one heavy container China → Europe/Israel incl. trucking. "
             "Replace with your carrier's emission report (e.g. GLEC-based) when available.")
    total_carbon_tons = total_units_carbon * carbon_per_unit

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Total Landed Cost ({curr_code})", format_currency(landed_disp, curr_code))
    m2.metric(f"Total Economic Cost ({curr_code})", format_currency(economic_disp, curr_code))
    m3.metric(f"Total Cash Requirement ({curr_code})", format_currency(cash_disp, curr_code))
    m4.metric("Estimated Carbon Footprint", f"{total_carbon_tons:,.1f} t CO2")

    _pdc_usd = results["total_landed_cost_ex_vat"] / (1 + contingency_pct / 100.0)
    render_unit_cost_metrics(
        logistics_usd=_pdc_usd - results["trended_exw"],
        landed_usd=results["total_landed_cost_ex_vat"],
        exw_usd=results["trended_exw"],
        mult=disp_mult, code=curr_code)
    st.caption("Logistics & Import Cost = origin charges, ocean freight & surcharges, insurance, duty, port, inland "
               "transport, permits and compliance — excluding equipment value, contingency and VAT.")

    st.markdown("---")
    st.markdown("#### Project Budget & Carbon Footprint Breakdown")
    
    raw_breakdown_data = [
        {"Cost Item": "Equipment EXW Value", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["trended_exw"] * disp_mult},
        {"Cost Item": "China Inland & Origin THC", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": (results["china_inland_drayage"] + results["china_origin_thc"]) * disp_mult},
        {"Cost Item": "Ocean Freight (Base)", "Basis / Qty": f"{results['total_containers_project']} Units", "RawAmount": results["total_base_ocean_freight"] * disp_mult},
        {"Cost Item": "Bunker Adjustment Factor (BAF)", "Basis / Qty": f"{project_teu:g} TEU", "RawAmount": (results["total_baf_ocean"] - efs_total_usd) * disp_mult},
        {"Cost Item": "Emergency Fuel Surcharge (EFS)", "Basis / Qty": f"{project_teu:g} TEU" if apply_efs else "Not applied", "RawAmount": efs_total_usd * disp_mult},
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
    POD_OPTIONS = destination_ports + [p for p in ISRAEL_PORTS + all_european_ports if p not in destination_ports] + ["Other"]
    if is_israel and not has_toxins_permit:
        st.error(f"⚠️ **Israel — Toxins Permit missing for the {toxins_missing_text}.** Plan extra port storage days in "
                 "the shipments below until both permits are in place.")

    if "msp_shipments" not in st.session_state or "Container Size" not in st.session_state.get("msp_lines", pd.DataFrame()).columns:
        st.session_state.msp_shipments = pd.DataFrame([
            {"Shipment": "Shipment 1", "Carrier": "COSCO Shipping", "Service": "Container Line - SOC",
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
            {"Shipment": "Shipment 1", "Equipment": "BESS", "Qty": 10, "Container Size": "20ft", "Currency": "USD",
             "Freight / Unit": 18000.0, "BAF / TEU": None, "Apply EFS": False, "EFS / TEU": None,
             "Dest. THC / Unit": 400.0, "Trucking / Unit": 5500.0},
            {"Shipment": "Shipment 2", "Equipment": "BESS", "Qty": 10, "Container Size": "MPP / Breakbulk", "Currency": "USD",
             "Freight / Unit": 21000.0, "BAF / TEU": 0.0, "Apply EFS": False, "EFS / TEU": 0.0,
             "Dest. THC / Unit": 0.0, "Trucking / Unit": 5500.0},
            {"Shipment": "Shipment 2", "Equipment": "MVS", "Qty": 4, "Container Size": "MPP / Breakbulk", "Currency": "USD",
             "Freight / Unit": 6000.0, "BAF / TEU": 0.0, "Apply EFS": False, "EFS / TEU": 0.0,
             "Dest. THC / Unit": 0.0, "Trucking / Unit": 4500.0},
            {"Shipment": "Shipment 3", "Equipment": "Accessory", "Qty": 2, "Container Size": "40ft HC", "Currency": "USD",
             "Freight / Unit": 4000.0, "BAF / TEU": None, "Apply EFS": False, "EFS / TEU": None,
             "Dest. THC / Unit": 400.0, "Trucking / Unit": 3000.0},
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
            "Carrier": st.column_config.SelectboxColumn("Carrier", options=CARRIERS + ["MPP Operator", "Other"]),
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
    st.caption("One line per equipment type per shipment, in the currency selected on the line. Freight, THC and trucking are "
               "per unit. **BAF and EFS are per TEU** (20ft = 1 TEU, 40ft = 2 TEU, 10ft = "
               f"{ten_ft_teu:g} TEU) — leave BAF / EFS **empty** to use the monthly surcharge table for the shipment's carrier "
               "and POD. For MPP / Breakbulk lines BAF / EFS are per unit (usually included in the MPP rate).")
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
            "Container Size": st.column_config.SelectboxColumn("Container Size", options=CONTAINER_SIZES, required=True),
            "BAF / TEU": st.column_config.NumberColumn("BAF / TEU", help="Empty = auto from monthly table", step=10.0, format="%.0f"),
            "Apply EFS": st.column_config.CheckboxColumn("Apply EFS", help="Emergency Fuel Surcharge"),
            "EFS / TEU": st.column_config.NumberColumn("EFS / TEU", help="Empty = auto from monthly table", min_value=0.0, step=10.0, format="%.0f"),
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
            "container_size": row.get("Container Size") if row.get("Container Size") in CONTAINER_SIZES else "20ft",
            "baf_per_teu": row.get("BAF / TEU"),
            "apply_efs": bool(row.get("Apply EFS")) if not pd.isna(row.get("Apply EFS")) else False,
            "efs_per_teu": row.get("EFS / TEU"),
            "dthc_per_unit": row.get("Dest. THC / Unit"),
            "trucking_per_unit": row.get("Trucking / Unit"),
        })

    # Auto-fill empty BAF / EFS from the monthly surcharge table (by shipment carrier + POD)
    _ship_by_name = {sh["name"]: sh for sh in msp_shipments}
    msp_auto_notes = []
    for l in msp_lines:
        sh = _ship_by_name.get(l["shipment"])
        if not sh:
            continue
        baf_empty = l["baf_per_teu"] is None or pd.isna(l["baf_per_teu"])
        efs_empty = l["efs_per_teu"] is None or pd.isna(l["efs_per_teu"])
        if not (baf_empty or efs_empty):
            continue
        entry = lookup_surcharge(BAF_RATES, sh["carrier"], sh["pod"]) if l["container_size"] != "MPP / Breakbulk" else None
        if entry:
            # table is in USD; convert to the line currency
            fx = usd_to_eur if str(l["currency"]).upper().startswith("EUR") else 1.0
            if baf_empty:
                l["baf_per_teu"] = float(entry["baf_usd_per_teu"]) * fx
            if efs_empty:
                l["efs_per_teu"] = float(entry.get("efs_usd_per_teu") or 0.0) * fx
            msp_auto_notes.append(f"{l['shipment']} / {l['equipment']}: {entry['carrier']} {entry['lane']} — "
                                  f"{entry.get('baf_name') or 'BAF'} ${entry['baf_usd_per_teu']}/TEU"
                                  + (f", EFS ${entry['efs_usd_per_teu']}/TEU" if entry.get('efs_usd_per_teu') else "")
                                  + f" (effective {entry.get('effective_from') or '-'})")
        else:
            if baf_empty:
                l["baf_per_teu"] = 0.0
                msp_auto_notes.append(f"{l['shipment']} / {l['equipment']}: no surcharge on file for "
                                      f"{sh['carrier'] or 'this carrier'} to this POD — BAF set to 0, please enter it.")
            if efs_empty:
                l["efs_per_teu"] = 0.0
    if msp_auto_notes:
        with st.expander(f"📡 Fuel surcharges auto-filled from the monthly table ({len(msp_auto_notes)})"):
            for n in msp_auto_notes:
                st.markdown(f"- {n}")

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
        ten_ft_teu_factor=ten_ft_teu,
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
            "TEU": f"{r['teu']:g}",
            "Ocean Freight": _fmt(r["freight"]),
            "BAF": _fmt(r["baf"]),
            "EFS": _fmt(r["efs"]),
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
    render_unit_cost_metrics(
        logistics_usd=plan["logistics_total_ex_vat"] + plan["project_level_costs"],
        landed_usd=plan["landed_ex_vat"],
        exw_usd=plan["goods_total"],
        mult=msp_mult, code=curr_code, label_suffix=" (all shipments)")

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
st.caption(f"© {date.today().year} Terra Vol. Advanced Renewable Energy & Infrastructure Venture.")
