import streamlit as st
import pandas as pd
import os
import io
from datetime import date
from calc import get_live_exchange_rate, convert_currency, format_currency, calculate_project_costs

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
    "Shanghai (CN)": {
        "destinations": {
            "Iepurești (Romania)": {"distance_km": 320, "transit_days": 4, "base_trucking_cost": 4200},
            "Ghimpați (Romania)": {"distance_km": 340, "transit_days": 4, "base_trucking_cost": 4400},
            "Sofia (Bulgaria)": {"distance_km": 380, "transit_days": 4, "base_trucking_cost": 4100},
            "Warsaw (Poland)": {"distance_km": 450, "transit_days": 5, "base_trucking_cost": 4800},
            "Budapest (Hungary)": {"distance_km": 300, "transit_days": 3, "base_trucking_cost": 3900},
            
            
        }
    },
    "Piraeus (GR)": {
        "destinations": {
            "Iepurești (Romania)": {"distance_km": 1150, "transit_days": 12, "base_trucking_cost": 9500},
            "Ghimpați (Romania)": {"distance_km": 1180, "transit_days": 12, "base_trucking_cost": 9800},
            "Sofia (Bulgaria)": {"distance_km": 400, "transit_days": 4, "base_trucking_cost": 4500},
            
           
        }
    },
    "Constanta (RO)": {
        "destinations": {
            "Iepurești (Romania)": {"distance_km": 280, "transit_days": 3, "base_trucking_cost": 3600},
            "Ghimpați (Romania)": {"distance_km": 260, "transit_days": 3, "base_trucking_cost": 3400},
            "Sofia (Bulgaria)": {"distance_km": 290, "transit_days": 3, "base_trucking_cost": 3700},
            "Budapest (Hungary)": {"distance_km": 850, "transit_days": 9, "base_trucking_cost": 7200}
        }
    },
    "Burgas (BG)": {
        "destinations": {
            "Sofia (Bulgaria)": {"distance_km": 380, "transit_days": 4, "base_trucking_cost": 3200},
            "Iepurești (Romania)": {"distance_km": 310, "transit_days": 3, "base_trucking_cost": 3900}
        }
    },
    "Gdańsk / Gdynia (PL)": {
        "destinations": {
            "Warsaw (Poland)": {"distance_km": 350, "transit_days": 4, "base_trucking_cost": 3500},
            "Prague (Czech Republic)": {"distance_km": 620, "transit_days": 6, "base_trucking_cost": 6100}
        }
    },
    "Hamburg (DE)": {
        "destinations": {
            "Berlin (Germany)": {"distance_km": 290, "transit_days": 3, "base_trucking_cost": 3100},
            "Prague (Czech Republic)": {"distance_km": 350, "transit_days": 4, "base_trucking_cost": 3600},
            "Vienna (Austria)": {"distance_km": 750, "transit_days": 8, "base_trucking_cost": 7400}
        }
    },
    "Rotterdam (NL)": {
        "destinations": {
            "Amsterdam (Netherlands)": {"distance_km": 60, "transit_days": 1, "base_trucking_cost": 600},
            "Antwerp (Belgium)": {"distance_km": 100, "transit_days": 1, "base_trucking_cost": 900},
            "Paris (France)": {"distance_km": 450, "transit_days": 5, "base_trucking_cost": 4900}
        }
    },
    "Antwerp (BE)": {
        "destinations": {
            "Brussels (Belgium)": {"distance_km": 50, "transit_days": 1, "base_trucking_cost": 500},
            "Paris (France)": {"distance_km": 310, "transit_days": 3, "base_trucking_cost": 3400}
        }
    },
    "Genoa / Trieste (IT)": {
        "destinations": {
            "Milan (Italy)": {"distance_km": 150, "transit_days": 2, "base_trucking_cost": 1900},
            "Vienna (Austria)": {"distance_km": 520, "transit_days": 5, "base_trucking_cost": 5300},
            "Bratislava (Slovakia)": {"distance_km": 680, "transit_days": 7, "base_trucking_cost": 6800}
        }
    },
    "Koper (SI)": {
        "destinations": {
            "Iepurești (Romania)": {"distance_km": 1050, "transit_days": 11, "base_trucking_cost": 8900},
            "Budapest (Hungary)": {"distance_km": 500, "transit_days": 5, "base_trucking_cost": 5100},
            "Bratislava (Slovakia)": {"distance_km": 480, "transit_days": 5, "base_trucking_cost": 4900}
        }
    },
    "Valencia / Barcelona (ES)": {
        "destinations": {
            "Madrid (Spain)": {"distance_km": 350, "transit_days": 4, "base_trucking_cost": 3800}
        }
    },
    "Marseille / Le Havre (FR)": {
        "destinations": {
            "Paris (France)": {"distance_km": 200, "transit_days": 2, "base_trucking_cost": 2200}
        }
    }
}
    
    # 2. Aegean Sea & Saronic Gulf Ports (Greece)
   "Piraeus (Greece)": {
        "destinations": {
            "Greece (Local - Athens / Larissa)": {"distance_km": 350, "base_trucking_cost": 2800, "transit_days": 1},
            "Bulgaria (Sofia)": {"distance_km": 550, "base_trucking_cost": 4500, "transit_days": 2},
            "North Macedonia (Skopje)": {"distance_km": 500, "base_trucking_cost": 4200, "transit_days": 2}
        }
    },
    "Thessaloniki (Greece)": {
        "destinations": {
            "Greece (Local - North)": {"distance_km": 250, "base_trucking_cost": 2200, "transit_days": 1},
            "Bulgaria (Sofia)": {"distance_km": 300, "base_trucking_cost": 2600, "transit_days": 1},
            "Serbia (Belgrade)": {"distance_km": 600, "base_trucking_cost": 5200, "transit_days": 2}
        }
    },
    "Lavrion / Elefsis (Saronic Gulf, Greece)": {
        "destinations": {
            "Greece (Local Projects)": {"distance_km": 150, "base_trucking_cost": 1800, "transit_days": 1},
            "Balkans Region": {"distance_km": 650, "base_trucking_cost": 5500, "transit_days": 3}
        }
    },
    
    # 3. Adriatic & Central Mediterranean
    "Koper (Slovenia)": {
        "destinations": {
            "Hungary (Budapest)": {"distance_km": 500, "base_trucking_cost": 4500, "transit_days": 2},
            "Austria (Vienna)": {"distance_km": 500, "base_trucking_cost": 4600, "transit_days": 2},
            "Romania (West / Central)": {"distance_km": 1100, "base_trucking_cost": 8500, "transit_days": 4}
        }
    },
    "Trieste / Venice (Italy)": {
        "destinations": {
            "Austria / Central Europe": {"distance_km": 600, "base_trucking_cost": 5000, "transit_days": 2},
            "Hungary (Budapest)": {"distance_km": 700, "base_trucking_cost": 5800, "transit_days": 2}
        }
    },
    
    # 4. Northern Europe Hubs
    "Antwerp / Rotterdam (North Europe)": {
        "destinations": {
            "Romania (Project Sites - e.g. Iepurești)": {"distance_km": 2100, "base_trucking_cost": 12000, "transit_days": 5},
            "Germany (Central)": {"distance_km": 600, "base_trucking_cost": 5000, "transit_days": 2}
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

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📋 Equipment Mix & Quantities",
    "🚢 Supply Chain & Incoterms",
    "📦 Storage, Demurrage & Drayage",
    "⚖️ Regulation & Approvals",
    "🗺️ European Route Options",
    "📂 Infrastructure Projects",
    "📊 Budget & Carbon Report"
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
    st.subheader("European Route & Corridor Analysis")
    st.markdown(f"Corridor Intelligence & Gateway Selection for **{destination_country}** via **{dest_port}**.")
    corridors_data = [{"Gateway Port": dest_port, "Destination Country": destination_country, "Estimated Transit": "30-35 Days", "Corridor Type": "Maritime + Heavy Road / Multimodal", "Status": "Active & Verified"}]
    st.dataframe(pd.DataFrame(corridors_data), use_container_width=True, hide_index=True)

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
