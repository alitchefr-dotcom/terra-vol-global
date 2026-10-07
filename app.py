import streamlit as st
import pandas as pd
import os
import requests
import base64
import math
from datetime import date
from io import BytesIO

# ---------------------------------------------------------
# 1. Streamlit Page Configuration
# ---------------------------------------------------------
possible_logo_names = ["logo.png", "logo.png.png", "Logo.png"]
logo_path = None
for name in possible_logo_names:
    full_path = os.path.join(os.path.dirname(__file__), name)
    if os.path.exists(full_path):
        logo_path = full_path
        break

st.set_page_config(
    page_title="Terra Vol - Renewable Energy Budgeting & Supply Chain",
    page_icon=logo_path if logo_path else "⚡",
    layout="wide"
)

from calc import calculate_project_costs

# ---------------------------------------------------------
# Authentication & Secure Login Mechanism
# ---------------------------------------------------------
def check_password():
    def password_entered():
        if (
            st.session_state.get("username") in st.secrets.get("passwords", {})
            and st.session_state.get("password") == st.secrets["passwords"][st.session_state["username"]]
        ):
            st.session_state["password_correct"] = True
            st.session_state.pop("password", None)
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("## 🔐 Terra Vol — Secure Enterprise Login")
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.button("Login", on_click=password_entered)
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 User not found or incorrect password")
    return False

if not check_password():
    st.stop()

if st.sidebar.button("Logout"):
    st.session_state.pop("password_correct", None)
    st.rerun()

# ---------------------------------------------------------
# Logo & Branding (English-Only Interface)
# ---------------------------------------------------------
def get_base64_of_bin_file(bin_file):
    if not bin_file or not os.path.exists(bin_file):
        return ""
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

logo_base64 = get_base64_of_bin_file(logo_path) if logo_path else ""

if logo_base64:
    st.sidebar.markdown(
        f'<div style="text-align: center; margin-bottom: 1.5rem;"><img src="data:image/png;base64,{logo_base64}" style="width: 100px; height: auto;" /></div>',
        unsafe_allow_html=True
    )

st.sidebar.header("🌐 Currency & Settings")

logo_img_tag = f'<img src="data:image/png;base64,{logo_base64}" style="width: 140px; height: auto;" />' if logo_base64 else '⚡'

header_html = f"""
<div style="display: flex; justify-content: space-between; align-items: center; width: 100%; direction: ltr; margin-bottom: 0rem;">
    <h1 style="margin: 0; font-size: 3rem; font-weight: 700; color: #1e3d59;">Terra Vol</h1>
    <div>{logo_img_tag}</div>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)
st.caption("Professional Project Calculator for Target Costs, Incoterms, Regulation & Sustainability")

ORIGIN_PORTS = {
    "SHA": "Shanghai, China",
    "NGB": "Ningbo, China",
    "SZX": "Shenzhen, China",
    "TAO": "Qingdao, China"
}

# Extended European & Global Destination Ports Database
DESTINATION_PORTS = {
    "RO": [("CT", "Constanța, Romania"), ("BOJ", "Burgas, Bulgaria")],
    "PL": [("GDN", "Gdansk, Poland"), ("GDY", "Gdynia, Poland")],
    "DE": [("HAM", "Hamburg, Germany"), ("BRV", "Bremerhaven, Germany")],
    "SE": [("GOT", "Gothenburg, Sweden"), ("STO", "Stockholm, Sweden")],
    "GR": [("PIR", "Piraeus, Greece"), ("THE", "Thessaloniki, Greece")],
    "ES": [("VLC", "Valencia, Spain"), ("BCN", "Barcelona, Spain")],
    "IT": [("GOA", "Genoa, Italy"), ("TRS", "Trieste, Italy")],
    "BG": [("VAR", "Varna, Bulgaria"), ("BOJ", "Burgas, Bulgaria")],
    "HU": [("BUD", "Budapest, Hungary (Rail/Multimodal)")],
    "FI": [("HEL", "Helsinki, Finland"), ("KTK", "Kotka, Finland")],
    "FR": [("LEH", "Le Havre, France"), ("MRS", "Marseille, France")],
    "UK": [("FXT", "Felixstowe, United Kingdom"), ("SOU", "Southampton, United Kingdom")],
    "IL": [("HAIF", "Haifa Port"), ("ASHD", "Ashdod Port")],
    "OTHER": [("RTM", "Rotterdam, Netherlands"), ("ANR", "Antwerp, Belgium")]
}

PORT_COORDINATES = {
    "HAIF": (32.8192, 34.9900), "ASHD": (31.8333, 34.6500),
    "CT": (44.1792, 28.6500), "BOJ": (42.5048, 27.4626),
    "GDN": (54.3520, 18.6466), "GDY": (54.5189, 18.5305),
    "HAM": (53.5511, 9.9937), "BRV": (53.5705, 8.5771),
    "GOT": (57.7089, 11.9746), "STO": (59.3293, 18.0686),
    "PIR": (37.9475, 23.6378), "THE": (40.6401, 22.9444),
    "VLC": (39.4699, -0.3763), "BCN": (41.3851, 2.1734),
    "GOA": (44.4056, 8.9463), "TRS": (45.6495, 13.7768),
    "VAR": (43.2141, 27.9147), "BUD": (47.4979, 19.0402),
    "HEL": (60.1699, 24.9384), "KTK": (60.4667, 26.9333),
    "LEH": (49.4944, 0.1079), "MRS": (43.2965, 5.3698),
    "FXT": (51.9567, 1.3514), "SOU": (50.9097, -1.4044),
    "RTM": (51.9244, 4.4777), "ANR": (51.2194, 4.4025)
}

def calculate_road_distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c * 1.3

VAT_RATES = {
    "RO": 19.0, "PL": 23.0, "DE": 19.0, "SE": 25.0, 
    "GR": 24.0, "ES": 21.0, "IT": 22.0, "BG": 20.0, "HU": 27.0,
    "FI": 25.5, "FR": 20.0, "UK": 20.0, "IL": 18.0, "OTHER": 0.0
}
DEFAULT_INSURANCE_RATES = {code: 0.15 for code in VAT_RATES}
DEFAULT_FREE_DAYS = {code: 7 for code in VAT_RATES}

COUNTRY_CODES = list(VAT_RATES.keys())
COUNTRY_NAMES = {
    "RO": "Romania", "PL": "Poland", "DE": "Germany", "SE": "Sweden",
    "GR": "Greece", "ES": "Spain", "IT": "Italy", "BG": "Bulgaria",
    "HU": "Hungary", "FI": "Finland", "FR": "France", "UK": "United Kingdom",
    "IL": "Israel", "OTHER": "Other / Custom"
}

incoterm_map = {
    "DDP": "DDP (Delivered Duty Paid — Full Scope)",
    "DAP": "DAP (Delivered at Place — Excl. Unloading, Duty & Import VAT)",
    "CIF": "CIF (Cost, Insurance and Freight)",
    "FOB": "FOB (Free On Board)",
    "EXW": "EXW (Ex Works — Factory Pickup)"
}

selected_incoterm_code = st.sidebar.selectbox("Commercial Incoterm (Supplier Scope):", list(incoterm_map.keys()), format_func=lambda k: incoterm_map[k], key="sidebar_incoterm_code")
display_currency = st.sidebar.selectbox("Main Display Currency:", ["USD ($)", "EUR (€)", "ILS (₪)"], key="sidebar_currency")

forecast_date = st.sidebar.date_input("Delivery Target Date:", value=date(2027, 6, 30), key="sidebar_forecast_date")
market_scenario_map = {
    "CONS": "Conservative (+8.0% p.a.)",
    "BASE": "Baseline (+4.5% p.a.)",
    "STABLE": "Stable / No Change (0.0%)"
}
selected_market_code = st.sidebar.selectbox("Inflation & Market Trend Scenario:", list(market_scenario_map.keys()), format_func=lambda k: market_scenario_map[k], key="sidebar_market_code")

today_date = date.today()
delta_days = (forecast_date - today_date).days
years_diff = max(0.0, delta_days / 365.25)
annual_inflation = 0.08 if selected_market_code == "CONS" else (0.045 if selected_market_code == "BASE" else 0.0)
trend_multiplier = (1.0 + annual_inflation) ** years_diff

@st.cache_data(ttl=300)
def fetch_live_exchange_rates():
    try:
        response = requests.get("https://api.frankfurter.dev/v1/latest?from=USD&to=EUR,ILS", timeout=5)
        if response.status_code == 200:
            data = response.json()
            rates = data.get("rates", {})
            return rates.get("EUR", 0.92), rates.get("ILS", 3.70)
    except Exception:
        pass
    return None, None

live_eur, live_ils = fetch_live_exchange_rates()
if live_eur is None or live_ils is None:
    live_eur, live_ils = 0.92, 3.70

if "fx_eur" not in st.session_state:
    st.session_state["fx_eur"] = live_eur
if "fx_ils" not in st.session_state:
    st.session_state["fx_ils"] = live_ils

usd_to_eur = st.sidebar.number_input("USD to EUR Exchange Rate:", step=0.01, min_value=0.0001, format="%.4f", key="fx_eur")
usd_to_ils = st.sidebar.number_input("USD to ILS Exchange Rate:", step=0.01, min_value=0.0001, format="%.4f", key="fx_ils")

def refresh_fx():
    fetch_live_exchange_rates.clear()
    ne, ni = fetch_live_exchange_rates()
    if ne and ni:
        st.session_state["fx_eur"] = ne
        st.session_state["fx_ils"] = ni

st.sidebar.button("🔄 Refresh Rates", on_click=refresh_fx)

def convert_from_usd(amount_usd, target_curr):
    if target_curr == "USD ($)": return amount_usd, "$"
    if target_curr == "EUR (€)": return amount_usd * usd_to_eur, "€"
    if target_curr == "ILS (₪)": return amount_usd * usd_to_ils, "₪"
    return amount_usd, "$"

curr_symbol = "$" if "USD" in display_currency else ("€" if "EUR" in display_currency else "₪")

if "sidebar_dest_country_code" not in st.session_state:
    st.session_state["sidebar_dest_country_code"] = "RO"

dest_country_code = st.sidebar.selectbox(
    "Project Destination Country:",
    COUNTRY_CODES,
    format_func=lambda k: COUNTRY_NAMES[k],
    key="sidebar_dest_country_code"
)
dest_country_name = COUNTRY_NAMES[dest_country_code]
is_european_dest = (dest_country_code != "IL")

CARRIER_FUEL_SURCHARGES = {
    "ZIM": {"name": "ZIM (Preferred DG & Flexible Service)", "bess_mult": 1.0, "dthc_mult": 1.0},
    "MSC": {"name": "MSC (Preferred European Tariffs)", "bess_mult": 0.82, "dthc_mult": 0.90},
    "CMA": {"name": "CMA CGM (Core West/Central Europe Service)", "bess_mult": 0.92, "dthc_mult": 0.92},
    "COSCO": {"name": "COSCO Shipping (Direct Asia-Europe Service)", "bess_mult": 0.88, "dthc_mult": 0.88},
    "HAPAG": {"name": "Hapag-Lloyd (Standard East-West)", "bess_mult": 0.95, "dthc_mult": 0.95},
    "SPOT": {"name": "Spot Market / Free Carrier", "bess_mult": 0.90, "dthc_mult": 0.90}
}

tab1, tab2, tab3, tab4, tab5_eu, tab_summary = st.tabs([
    "📋 Equipment Mix & Quantities",
    "⚓ Supply Chain & Incoterms",
    "📦 Storage, Demurrage & Drayage",
    "⚖️ Regulation & Sustainability",
    "🗺️ European Route Options",
    "📊 Budget & Carbon Report"
])

with tab1:
    st.subheader("Equipment Mix & Quantities Configuration")
    st.info("Enter BESS container quantities, inverters, transformers, and factory EXW production costs.")

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        origin_port_code = st.selectbox("Origin Port:", list(ORIGIN_PORTS.keys()), format_func=lambda k: ORIGIN_PORTS[k], key="tab1_origin_port_code")
        available_dest_tuples = DESTINATION_PORTS.get(dest_country_code, DESTINATION_PORTS["OTHER"])
        dest_port_code = st.selectbox(
            "Destination Port:",
            [t[0] for t in available_dest_tuples],
            format_func=lambda code: next(t[1] for t in available_dest_tuples if t[0] == code),
            key=f"tab1_dest_port_{dest_country_code}"
        )
        site_address = st.text_input("Project Site Name:", key="site_name_input", placeholder="Alpha Project / Site Name")

        st.markdown("##### 📍 Detailed Project Site Location:")
        site_street_address = st.text_input("Full Street Address:", key="site_street_address_input")
        site_postal_code = st.text_input("Postal Code:", key="site_postal_code_input")
        site_coordinates = st.text_input("GPS Coordinates (Lat, Long):", key="site_coordinates_input", placeholder="44.4268, 26.1025")

        calculated_distance_km = 50.0
        if site_coordinates:
            try:
                lat_str, lon_str = site_coordinates.replace("°", "").split(",")
                s_lat = float(lat_str.strip())
                s_lon = float(lon_str.strip())
                if dest_port_code in PORT_COORDINATES:
                    p_lat, p_lon = PORT_COORDINATES[dest_port_code]
                    calculated_distance_km = calculate_road_distance_km(p_lat, p_lon, s_lat, s_lon)
                    st.info(f"📍 Calculated road distance from port ({dest_port_code}): ~{calculated_distance_km:,.1f} km")
                else:
                    st.warning("⚠️ Port not in coordinate dictionary. Default 50 km applied.")
            except Exception:
                st.warning("⚠️ Invalid coordinates format. Please use: `44.4268, 26.1025`")

    with col_meta2:
        applied_vat = st.number_input(f"VAT Rate ({dest_country_name}) %:", value=float(VAT_RATES[dest_country_code]), step=0.5, min_value=0.0, max_value=100.0, key=f"tab1_vat_{dest_country_code}")
        vat_recovery_pct = st.number_input("VAT Recovery Rate (%)", value=100.0, min_value=0.0, max_value=100.0, step=1.0, key="tab1_vat_rec")
        vat_paid_by_supplier = st.checkbox("VAT paid by supplier under commercial terms", value=False, key="tab1_vat_supplier")

    st.markdown("---")
    col_q1, col_q2, col_q3 = st.columns(3)
    
    with col_q1:
        st.markdown("#### BESS Containers")
        bess_count = st.number_input("BESS Containers (40' HC DG):", min_value=0, value=20, step=1, key="proj_bess_count")
        bess_exw = st.number_input("EXW Unit Cost per BESS ($):", min_value=0.0, value=400000.0, step=10000.0, key="proj_bess_exw")

        oog_count = st.number_input("OOG Containers:", min_value=0, value=0, step=1, key="proj_oog_count")
        oog_exw = st.number_input("EXW Unit Cost per OOG ($):", min_value=0.0, value=400000.0, step=10000.0, key="proj_oog_exw")

    with col_q2:
        st.markdown("#### MVS & Transformers")
        mvs_count = st.number_input("MVS Stations:", min_value=0, value=4, step=1, key="proj_mvs_count")
        mvs_exw = st.number_input("EXW Unit Cost per MVS ($):", min_value=0.0, value=250000.0, step=10000.0, key="proj_mvs_exw")

        transformer_count = st.number_input("Main Transformers:", min_value=0, value=2, step=1, key="proj_trans_count")
        transformer_exw = st.number_input("EXW Unit Cost per Transformer ($):", min_value=0.0, value=120000.0, step=10000.0, key="proj_trans_exw")

    with col_q3:
        st.markdown("#### Accessories & PV")
        access_count = st.number_input("Accessory Containers:", min_value=0, value=2, step=1, key="proj_access_count")
        access_exw = st.number_input("EXW Unit Cost per Accessory Container ($):", min_value=0.0, value=50000.0, step=5000.0, key="proj_access_exw")

        solar_count = st.number_input("Solar PV Units:", min_value=0, value=0, step=1, key="proj_solar_count")
        solar_exw = st.number_input("EXW Unit Cost per Solar Unit ($):", min_value=0.0, value=300000.0, step=10000.0, key="proj_solar_exw")

    total_containers_project = max(1, bess_count + oog_count + mvs_count + transformer_count + access_count + solar_count)
    total_exw_project = (
        (bess_count * bess_exw) + (oog_count * oog_exw) + 
        (mvs_count * mvs_exw) + (transformer_count * transformer_exw) + 
        (access_count * access_exw) + (solar_count * solar_exw)
    )
    is_bess = (bess_count > 0 or oog_count > 0)
    is_dg = is_bess

    exw_display_val, _ = convert_from_usd(total_exw_project, display_currency)
    st.success(f'📊 Project Units: {total_containers_project:,} | Total Factory EXW Value: {curr_symbol} {exw_display_val:,.2f}')

with tab2:
    st.subheader("🚢 Ocean Freight, BAF & Destination THC")
    
    selected_carrier_code = st.selectbox("Shipping Line / Carrier:", list(CARRIER_FUEL_SURCHARGES.keys()), format_func=lambda k: CARRIER_FUEL_SURCHARGES[k]["name"], key="tab2_carrier_code")
    carrier_data = CARRIER_FUEL_SURCHARGES[selected_carrier_code]

    baf_included = st.checkbox("Bunker Adjustment Factor (BAF) included in ocean freight", value=False, key="tab2_baf_incl")
    include_baf_calculation = not baf_included

    st.markdown("##### 1. Ocean Freight per Unit:")
    oc_col1, oc_col2, oc_col3 = st.columns(3)
    with oc_col1:
        unit_freight_bess = st.number_input("BESS Freight ($):", value=21000.0 * carrier_data["bess_mult"], step=500.0, key=f"freight_bess_{selected_carrier_code}")
        unit_freight_oog = st.number_input("OOG Freight ($):", value=29900.0, step=500.0, key=f"freight_oog_{selected_carrier_code}")
    with oc_col2:
        unit_freight_mvs = st.number_input("MVS Freight ($):", value=4200.0, step=200.0, key=f"freight_mvs_{selected_carrier_code}")
        unit_freight_trans = st.number_input("Transformer Freight ($):", value=5500.0, step=200.0, key=f"freight_trans_{selected_carrier_code}")
    with oc_col3:
        unit_freight_access = st.number_input("Accessory Freight ($):", value=3200.0, step=200.0, key=f"freight_access_{selected_carrier_code}")
        unit_freight_solar = st.number_input("Solar PV Freight ($):", value=3360.0, step=200.0, key=f"freight_solar_{selected_carrier_code}")

    st.markdown("---")
    if include_baf_calculation:
        st.markdown("##### 2. Bunker Adjustment Factor (BAF) per TEU:")
        baf_mult = carrier_data["dthc_mult"]
        base_baf_per_teu = st.number_input("Base BAF Rate per TEU ($):", value=420.0 * baf_mult, step=20.0, key=f"baf_per_teu_{selected_carrier_code}")

        teu_bess, teu_oog, teu_mvs, teu_trans, teu_access, teu_solar = 2.0, 2.0, 1.0, 1.0, 1.0, 1.0
        baf_bess = (base_baf_per_teu * teu_bess)
        baf_oog = (base_baf_per_teu * teu_oog)
        baf_mvs = (base_baf_per_teu * teu_mvs)
        baf_trans = (base_baf_per_teu * teu_trans)
        baf_access = (base_baf_per_teu * teu_access)
        baf_solar = (base_baf_per_teu * teu_solar)
    else:
        baf_bess, baf_oog, baf_mvs, baf_trans, baf_access, baf_solar = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    st.markdown("---")
    st.markdown("##### 3. Destination Terminal Handling Charges (Destination THC):")
    dthc_mult = carrier_data["dthc_mult"]
    
    dh_col1, dh_col2, dh_col3 = st.columns(3)
    with dh_col1:
        dthc_bess = st.number_input("BESS Destination THC ($):", value=650.0 * dthc_mult, step=50.0, key=f"dthc_bess_{selected_carrier_code}")
        dthc_oog = st.number_input("OOG Destination THC ($):", value=850.0 * dthc_mult, step=50.0, key=f"dthc_oog_{selected_carrier_code}")
    with dh_col2:
        dthc_mvs = st.number_input("MVS Destination THC ($):", value=420.0 * dthc_mult, step=30.0, key=f"dthc_mvs_{selected_carrier_code}")
        dthc_trans = st.number_input("Transformer Destination THC ($):", value=480.0 * dthc_mult, step=30.0, key=f"dthc_trans_{selected_carrier_code}")
    with dh_col3:
        dthc_access = st.number_input("Accessory Destination THC ($):", value=280.0 * dthc_mult, step=20.0, key=f"dthc_access_{selected_carrier_code}")
        dthc_solar = st.number_input("Solar PV Destination THC ($):", value=300.0 * dthc_mult, step=20.0, key=f"dthc_solar_{selected_carrier_code}")

    customs_duty_pct_default = 0.0 if dest_country_code == "IL" else 2.7
    customs_duty_pct = st.number_input(
        "General Import Customs Duty Rate (%) for BESS/MVS (Solar PV is automatically 0% exempt):",
        value=float(customs_duty_pct_default), min_value=0.0, max_value=100.0, step=0.1,
        key=f"customs_duty_input_{dest_country_code}"
    )
    insurance_pct = DEFAULT_INSURANCE_RATES.get(dest_country_code, 0.15)

with tab3:
    st.subheader("📦 Storage, Demurrage & Inland Drayage")
    
    dk = int(calculated_distance_km * 100)
    distance_factor = max(1.0, calculated_distance_km / 50.0)

    st.markdown("##### 1. Port-to-Site Inland Drayage")
    dr_col1, dr_col2, dr_col3 = st.columns(3)
    with dr_col1:
        drayage_bess = st.number_input("BESS Trucking per unit ($):", value=4500.0 * distance_factor, step=200.0, key=f"dray_bess_{dk}")
        drayage_oog = st.number_input("OOG Trucking per unit ($):", value=4800.0 * distance_factor, step=200.0, key=f"dray_oog_{dk}")
    with dr_col2:
        drayage_mvs = st.number_input("MVS Trucking per unit ($):", value=1400.0 * distance_factor, step=100.0, key=f"dray_mvs_{dk}")
        drayage_trans = st.number_input("Transformer Trucking per unit ($):", value=1800.0 * distance_factor, step=100.0, key=f"dray_trans_{dk}")
    with dr_col3:
        drayage_access = st.number_input("Accessory Trucking per unit ($):", value=850.0 * distance_factor, step=100.0, key=f"dray_access_{dk}")
        drayage_solar = st.number_input("Solar PV Trucking per unit ($):", value=950.0 * distance_factor, step=100.0, key=f"dray_solar_{dk}")

    st.markdown("---")
    st.markdown("##### 2. Port Demurrage & External Storage")
    st_col1, st_col2 = st.columns(2)
    with st_col1:
        actual_port_days = st.number_input("Actual Port Days:", value=12, min_value=1, step=1, key="tab3_actual_days")
        free_days = st.number_input("Free Days:", value=int(DEFAULT_FREE_DAYS.get(dest_country_code, 7)), min_value=0, step=1, key=f"tab3_free_days_{dest_country_code}")
        demurrage_daily_rate = st.number_input("Demurrage Daily Rate ($):", value=250.0 if is_dg else 150.0, step=25.0, key=f"tab3_dem_rate_{is_dg}")
    with st_col2:
        use_external_storage = st.checkbox("Use External Storage", value=True, key="tab3_ext_storage_toggle")
        ext_storage_days = st.number_input("External Storage Days:", value=15, min_value=0, step=1, key="tab3_ext_days")
        ext_storage_daily_rate = st.number_input("Daily External Storage Rate ($):", value=65.0 if is_dg else 45.0, step=10.0, key=f"tab3_ext_rate_{is_dg}")

    st.markdown("---")
    st.markdown("##### 3. Site Crane & Unloading")
    cr_col1, cr_col2 = st.columns(2)
    with cr_col1:
        include_site_crane = st.checkbox("Include Site Crane & Unloading", value=True, key="tab3_crane_toggle")
    with cr_col2:
        site_crane_unloading = st.number_input("Total Crane & Unloading Cost ($):", value=8500.0, step=500.0, key="tab3_crane_cost")

    include_delay_scenario = False

with tab4:
    st.subheader("⚖️ Regulation & Sustainability")

    bess_capacity_mwh = 4.0
    decom_cost_per_kwh = 0.0 if dest_country_code == "IL" else 75.0

    if dest_country_code == "IL":
        mot_fee_per_bess = st.number_input("MOT approval fee per BESS unit ($):", value=350.0, step=50.0, key="mot_fee_input_il")
        mot_total_approval_cost = mot_fee_per_bess * float(bess_count + oog_count)
        local_regulatory_permits = st.number_input("Port hazmat permits cost ($):", value=1500.0, step=100.0, key="reg_cost_input_il")
        
        epr_recycling_total_usd = 0.0
        battery_passport_total_usd = 0.0
        include_mot_approval = True
        include_regulatory = True
    else:
        battery_passport_flat = st.number_input("Total Battery Passport Cost ($):", value=1200.0, step=100.0, key="bp_cost_input_eu")
        battery_passport_total_usd = battery_passport_flat

        epr_fee_per_unit = st.number_input("Ongoing EPR Fee per BESS unit ($):", value=450.0, step=50.0, key="epr_unit_input_eu")
        epr_recycling_total_usd = epr_fee_per_unit * float(bess_count + oog_count)

        include_regulatory = st.checkbox("Include local site entry permits", value=True, key="reg_permits_toggle_eu")
        local_regulatory_permits = st.number_input("Local Permits Cost ($):", value=600.0, step=100.0, key="reg_cost_input_eu") if include_regulatory else 0.0

        mot_total_approval_cost = 0.0
        include_mot_approval = False

        st.markdown("---")
        st.markdown("### 🔄 Decommissioning & End-of-Life Financial Provision")
        with st.expander("📌 Future Provision (EU Benchmark $60–$90/kWh)", expanded=True):
            decom_col1, decom_col2 = st.columns(2)
            with decom_col1:
                bess_capacity_mwh = st.number_input("Average BESS Container Capacity (MWh):", min_value=0.1, value=4.0, step=0.5, key="decom_capacity_mwh")
            with decom_col2:
                decom_cost_per_kwh = st.number_input("Decommissioning & Recycling Cost per kWh ($) [Benchmark $75]:", min_value=0.0, value=75.0, step=5.0, key="decom_cost_per_kwh")
            
            decom_cost_per_bess = bess_capacity_mwh * 1000.0 * decom_cost_per_kwh
            decom_per_unit_disp, _ = convert_from_usd(decom_cost_per_bess, display_currency)
            decom_total_disp, _ = convert_from_usd(decom_cost_per_bess * float(bess_count + oog_count), display_currency)
            st.info(f'✅ {bess_capacity_mwh:.1f} MWh × ${decom_cost_per_kwh:,.0f}/kWh = **{curr_symbol} {decom_per_unit_disp:,.2f}** per container. Total provision: **{curr_symbol} {decom_total_disp:,.2f}**')

    st.markdown("---")
    requires_heavy_lift = st.checkbox("Heavy-Lift Survey Required", value=is_bess, key="hl_survey_toggle")
    heavy_lift_survey_cost = st.number_input("Heavy-Lift Survey Cost ($):", value=2500.0, step=250.0, key="hl_cost_input") if requires_heavy_lift else 0.0

with tab5_eu:
    st.subheader("🗺️ European Route & Corridor Analysis")
    st.warning("⚠️ Indicative data only, subject to freight forwarder verification.")
    eu_route_data = [
        {"Route": "Asia via Constanța (Romania)", "Transit": "32-35 Days", "Advantage": "Optimal for Eastern Europe / Balkan projects", "Suitability": "High for Solar + BESS"},
        {"Route": "Asia via Piraeus (Greece)", "Transit": "28-31 Days", "Advantage": "Fastest maritime entry to Southern/Central Europe", "Suitability": "High"},
        {"Route": "Asia via Rotterdam / Antwerp (North Europe)", "Transit": "30-33 Days", "Advantage": "Unmatched heavy-lift and barge infrastructure", "Suitability": "Maximum Flexibility"},
        {"Route": "Multimodal via Hamburg to Central Europe", "Transit": "35-38 Days", "Advantage": "Direct rail/multimodal forwarding to hubs", "Suitability": "Standard Grid Projects"}
    ]
    st.dataframe(pd.DataFrame(eu_route_data), use_container_width=False, hide_index=True)

calc_results = calculate_project_costs(
    bess_count=bess_count, bess_exw=bess_exw,
    oog_count=oog_count, oog_exw=oog_exw,
    mvs_count=mvs_count, mvs_exw=mvs_exw,
    transformer_count=transformer_count, transformer_exw=transformer_exw,
    access_count=access_count, access_exw=access_exw,
    solar_count=solar_count, solar_exw=solar_exw,
    unit_freight_bess=unit_freight_bess, unit_freight_oog=unit_freight_oog,
    unit_freight_mvs=unit_freight_mvs, unit_freight_trans=unit_freight_trans,
    unit_freight_access=unit_freight_access, unit_freight_solar=unit_freight_solar,
    baf_bess=baf_bess, baf_oog=baf_oog, baf_mvs=baf_mvs, baf_trans=baf_trans, baf_access=baf_access, baf_solar=baf_solar,
    dthc_bess=dthc_bess, dthc_oog=dthc_oog, dthc_mvs=dthc_mvs, dthc_trans=dthc_trans, dthc_access=dthc_access, dthc_solar=dthc_solar,
    drayage_bess=drayage_bess, drayage_oog=drayage_oog, drayage_mvs=drayage_mvs,
    drayage_trans=drayage_trans, drayage_access=drayage_access, drayage_solar=drayage_solar,
    trend_multiplier=trend_multiplier, insurance_pct=insurance_pct,
    customs_duty_pct=customs_duty_pct, applied_vat=applied_vat, vat_recovery_pct=vat_recovery_pct,
    vat_paid_by_supplier=vat_paid_by_supplier, incoterm_code=selected_incoterm_code,
    dest_country_code=dest_country_code,
    local_regulatory_permits=local_regulatory_permits, mot_total_approval_cost=mot_total_approval_cost,
    include_regulatory=include_regulatory, include_mot_approval=include_mot_approval,
    site_crane_unloading=site_crane_unloading, include_site_crane=include_site_crane,
    epr_recycling_total_usd=epr_recycling_total_usd, battery_passport_total_usd=battery_passport_total_usd,
    requires_heavy_lift=requires_heavy_lift, heavy_lift_survey_cost=heavy_lift_survey_cost,
    actual_port_days=actual_port_days, free_days=free_days, demurrage_daily_rate=demurrage_daily_rate,
    use_external_storage=use_external_storage, ext_storage_days=ext_storage_days,
    ext_storage_daily_rate=ext_storage_daily_rate, include_delay_scenario=include_delay_scenario,
    bess_capacity_mwh=bess_capacity_mwh, decom_cost_per_kwh=decom_cost_per_kwh
)

total_landed_cost_ex_vat = calc_results["total_landed_cost_ex_vat"]
economic_cost_ex_vat = calc_results["economic_cost_ex_vat"]
total_cash_requirement_incl_vat = calc_results["total_cash_requirement_incl_vat"]
supplier_scope_total = calc_results["supplier_scope_total"]

display_val, curr_symbol = convert_from_usd(total_landed_cost_ex_vat, display_currency)
supplier_val, _ = convert_from_usd(supplier_scope_total, display_currency)
cash_val, _ = convert_from_usd(total_cash_requirement_incl_vat, display_currency)
econ_val, _ = convert_from_usd(economic_cost_ex_vat, display_currency)

with tab_summary:
    st.subheader(f"📊 Financial & Environmental Control Report — {incoterm_map[selected_incoterm_code]} ({display_currency})")
    
    total_units_for_calc = calc_results["total_containers_project"]
    ocean_distance_approx_km = 18000.0
    carbon_ocean_tons = (total_units_for_calc * 25.0 * ocean_distance_approx_km * 0.02) / 1000.0
    carbon_road_tons = (total_units_for_calc * 25.0 * calculated_distance_km * 0.08) / 1000.0
    total_carbon_footprint_tons = carbon_ocean_tons + carbon_road_tons

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.markdown(f'<div class="metric-container"><div class="metric-title">Total Landed Cost (Excl. VAT)</div><div class="metric-value"><span class="ltr-val">{curr_symbol} {display_val:,.2f}</span></div></div>', unsafe_allow_html=True)
    with m_col2:
        st.markdown(f'<div class="metric-container"><div class="metric-title">Total Economic Cost</div><div class="metric-value"><span class="ltr-val">{curr_symbol} {econ_val:,.2f}</span></div></div>', unsafe_allow_html=True)
    with m_col3:
        st.markdown(f'<div class="metric-container"><div class="metric-title">Total Cash Requirement</div><div class="metric-value"><span class="ltr-val">{curr_symbol} {cash_val:,.2f}</span></div></div>', unsafe_allow_html=True)
    with m_col4:
        st.markdown(f'<div class="metric-container"><div class="metric-title">Estimated Carbon Footprint</div><div class="metric-value"><span class="ltr-val">{total_carbon_footprint_tons:,.1f} t CO2</span></div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📋 Project Budget & Carbon Footprint Breakdown")

    bess_oog_units = max(1.0, float(bess_count + oog_count))

    ex_exw, _ = convert_from_usd(calc_results["trended_exw"], display_currency)
    u_bess_exw, _ = convert_from_usd(bess_exw * trend_multiplier, display_currency)

    ex_ch_inland, _ = convert_from_usd(calc_results["china_inland_drayage"] + calc_results["china_origin_thc"], display_currency)
    u_ch_inland, _ = convert_from_usd((calc_results["china_inland_drayage"] + calc_results["china_origin_thc"]) / total_units_for_calc, display_currency)

    ex_ocean, _ = convert_from_usd(calc_results["total_base_ocean_freight"], display_currency)
    u_ocean_bess, _ = convert_from_usd(unit_freight_bess * trend_multiplier, display_currency)

    ex_baf, _ = convert_from_usd(calc_results["total_baf_ocean"], display_currency)
    ex_dthc, _ = convert_from_usd(calc_results["destination_thc_total"], display_currency)
    ex_insur, _ = convert_from_usd(calc_results["insurance_total_usd"], display_currency)
    ex_customs, _ = convert_from_usd(calc_results["customs_duty_usd"], display_currency)

    ex_drayage, _ = convert_from_usd(calc_results["inland_drayage_total_usd"], display_currency)
    u_drayage_bess, _ = convert_from_usd(drayage_bess * trend_multiplier, display_currency)

    ex_reg, _ = convert_from_usd(calc_results["active_regulatory_permits"], display_currency)
    ex_crane, _ = convert_from_usd(calc_results["active_site_crane"], display_currency)
    
    ex_epr, _ = convert_from_usd(calc_results["epr_recycling_total_usd"], display_currency)
    u_epr, _ = convert_from_usd(calc_results["epr_recycling_total_usd"] / bess_oog_units, display_currency)

    ex_bp, _ = convert_from_usd(calc_results["battery_passport_total_usd"], display_currency)
    ex_hl, _ = convert_from_usd(calc_results["active_heavy_lift"], display_currency)
    
    ex_decom, _ = convert_from_usd(calc_results["decommissioning_total_usd"], display_currency)
    u_decom, _ = convert_from_usd(calc_results["decommissioning_total_usd"] / bess_oog_units, display_currency)

    ex_cont, _ = convert_from_usd(calc_results["contingency_usd"], display_currency)
    ex_total, _ = convert_from_usd(total_landed_cost_ex_vat, display_currency)

    decom_row_html = f'<tr style="background-color: #fbf8f0;"><td>Decommissioning Provision ({bess_capacity_mwh}MWh)</td><td class="center">{int(bess_count + oog_count):,} BESS</td><td class="left"><span class="ltr-val">{curr_symbol} {u_decom:,.2f}</span></td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_decom:,.2f}</span></b></td></tr>' if dest_country_code != "IL" else ""
    carbon_row_html = f'<tr style="background-color: #f0fdf4;"><td>Total Carbon Footprint (Ocean + Road)</td><td class="center">{int(total_units_for_calc):,} units</td><td class="left"><span class="ltr-val">{(total_carbon_footprint_tons/total_units_for_calc):,.2f} t/unit</span></td><td class="left"><b><span class="ltr-val">{total_carbon_footprint_tons:,.1f} t CO2</span></b></td></tr>'

    html_table = f"""
    <table class="custom-finance-table" style="direction: ltr; text-align: left;">
        <thead>
            <tr>
                <th style="width: 40%; text-align: left;">Project Cost Item</th>
                <th class="center" style="width: 20%;">Basis / Qty</th>
                <th class="left" style="width: 20%;">Unit Cost</th>
                <th class="left" style="width: 20%;">Total Amount</th>
            </tr>
        </thead>
        <tbody>
            <tr><td>Equipment EXW Value</td><td class="center">{int(total_units_for_calc):,}</td><td class="left"><span class="ltr-val">BESS: {curr_symbol} {u_bess_exw:,.2f}</span></td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_exw:,.2f}</span></b></td></tr>
            <tr><td>China Inland & Origin THC</td><td class="center">{int(total_units_for_calc):,}</td><td class="left"><span class="ltr-val">{curr_symbol} {u_ch_inland:,.2f}</span></td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_ch_inland:,.2f}</span></b></td></tr>
            <tr><td>Ocean Freight (Base)</td><td class="center">{int(total_units_for_calc):,}</td><td class="left"><span class="ltr-val">BESS: {curr_symbol} {u_ocean_bess:,.2f}</span></td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_ocean:,.2f}</span></b></td></tr>
            <tr><td>Bunker Adjustment Factor (BAF)</td><td class="center">{int(total_units_for_calc):,}</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_baf:,.2f}</span></b></td></tr>
            <tr><td>Destination THC</td><td class="center">{int(total_units_for_calc):,}</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_dthc:,.2f}</span></b></td></tr>
            <tr><td>Marine Insurance</td><td class="center">% CIF</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_insur:,.2f}</span></b></td></tr>
            <tr><td>Differential Customs Duty ({customs_duty_pct}% BESS | 0% PV)</td><td class="center">Differential</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_customs:,.2f}</span></b></td></tr>
            <tr><td>Inland Drayage (Port to Site)</td><td class="center">{int(total_units_for_calc):,}</td><td class="left"><span class="ltr-val">BESS: {curr_symbol} {u_drayage_bess:,.2f}</span></td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_drayage:,.2f}</span></b></td></tr>
            <tr><td>Regulatory & Local Permits</td><td class="center">Expense</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_reg:,.2f}</span></b></td></tr>
            <tr><td>Site Crane & Unloading</td><td class="center">Expense</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_crane:,.2f}</span></b></td></tr>
            <tr><td>EPR / Recycling Fees</td><td class="center">{int(bess_count + oog_count):,} BESS</td><td class="left"><span class="ltr-val">{curr_symbol} {u_epr:,.2f}</span></td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_epr:,.2f}</span></b></td></tr>
            <tr><td>EU Battery Passport</td><td class="center">Global</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_bp:,.2f}</span></b></td></tr>
            <tr><td>Heavy-Lift Survey</td><td class="center">Survey</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_hl:,.2f}</span></b></td></tr>
            <tr><td>Contingency (5%)</td><td class="center">5%</td><td class="left">-</td><td class="left"><b><span class="ltr-val">{curr_symbol} {ex_cont:,.2f}</span></b></td></tr>
            <tr class="total-row"><td>Total Landed Cost (Excl. VAT)</td><td class="center">-</td><td class="left">-</td><td class="left" style="color: #1e3d59;"><b><span class="ltr-val">{curr_symbol} {ex_total:,.2f}</span></b></td></tr>
            {decom_row_html}
            {carbon_row_html}
        </tbody>
    </table>
    """
    st.markdown(html_table, unsafe_allow_html=True)

    st.markdown("---")
    
    excel_summary_data = [
        ["Project Cost Item", "Basis / Qty", f"Total Amount ({display_currency})"],
        ["Equipment EXW Value", f"{int(total_units_for_calc):,} units", ex_exw],
        ["China Inland & Origin THC", f"{int(total_units_for_calc):,} units", ex_ch_inland],
        ["Ocean Freight (Base)", f"{int(total_units_for_calc):,} containers", ex_ocean],
        ["Bunker Adjustment Factor (BAF)", f"{int(total_units_for_calc):,} units", ex_baf],
        ["Destination THC", f"{int(total_units_for_calc):,} units", ex_dthc],
        ["Marine Insurance", "% of CIF", ex_insur],
        ["Differential Customs Duty", "Differential", ex_customs],
        ["Inland Drayage (Port to Site)", f"{int(total_units_for_calc):,} trucks", ex_drayage],
        ["Regulatory & Local Permits", "Expense", ex_reg],
        ["Site Crane & Unloading", "Expense", ex_crane],
        ["EPR / Recycling Fees", f"{int(bess_count + oog_count):,} BESS", ex_epr],
        ["EU Battery Passport", "Global", ex_bp],
        ["Heavy-Lift Survey", "Survey", ex_hl],
        ["Contingency (5%)", "5%", ex_cont],
        ["Total Landed Cost (Excl. VAT)", "-", ex_total]
    ]
    if dest_country_code != "IL":
        excel_summary_data.append([f"Decommissioning Provision ({bess_capacity_mwh}MWh)", f"{int(bess_count + oog_count):,} BESS", ex_decom])
    excel_summary_data.append(["Total Carbon Footprint", f"{int(total_units_for_calc):,} units", f"{total_carbon_footprint_tons:,.1f} tons CO2"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export = pd.DataFrame(excel_summary_data[1:], columns=excel_summary_data[0])
        df_export.to_excel(writer, sheet_name='Cost Summary', index=False)
        ws = writer.sheets['Cost Summary']
        ws.views.sheetView[0].rightToLeft = False

        for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
            if isinstance(row[0].value, (int, float)):
                row[0].number_format = '#,##0.00'

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 5, 15)

    excel_data = output.getvalue()
    st.download_button(
        label="📥 Download Full Excel Report",
        data=excel_data,
        file_name=f"TerraVol_Commercial_Report_{dest_country_code}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )