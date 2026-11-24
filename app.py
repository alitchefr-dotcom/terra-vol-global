import streamlit as st
import pandas as pd
import os
import io
import json
import importlib
from datetime import date, timedelta
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


# ---------------------------------------------------------------------------
# PROJECT SAVE / LOAD — every input goes through `ui` so its value can be saved
# to a project file and restored later.
# ---------------------------------------------------------------------------
import re as _re

_LOADED = st.session_state.get("_loaded_project_values", {})
_SAVED = {}


def _pid(kind, label):
    """Stable field id: widget type + label without parentheses (currency etc.)."""
    return kind + ":" + _re.sub(r"\s*\([^)]*\)", "", str(label)).strip()


class _UI:
    def __init__(self, container):
        self.c = container

    def _call(self, kind, label, args, kw):
        pid = _pid(kind, label)
        if pid in _LOADED and "key" not in kw:
            v = _LOADED[pid]
            if kind in ("selectbox", "radio"):
                opts = list(args[0]) if args else list(kw.get("options", []))
                if v in opts:
                    kw["index"] = opts.index(v)
            elif kind == "multiselect":
                opts = list(args[0]) if args else list(kw.get("options", []))
                kw["default"] = [x for x in (v or []) if x in opts]
            elif kind == "date_input":
                try:
                    kw["value"] = date.fromisoformat(v)
                except (TypeError, ValueError):
                    pass
            else:
                kw["value"] = v
        res = getattr(self.c, kind)(label, *args, **kw)
        _SAVED[pid] = res.isoformat() if isinstance(res, date) else res
        return res

    def number_input(self, label, *a, **k): return self._call("number_input", label, a, k)
    def selectbox(self, label, *a, **k): return self._call("selectbox", label, a, k)
    def checkbox(self, label, *a, **k): return self._call("checkbox", label, a, k)
    def text_input(self, label, *a, **k): return self._call("text_input", label, a, k)
    def date_input(self, label, *a, **k): return self._call("date_input", label, a, k)
    def slider(self, label, *a, **k): return self._call("slider", label, a, k)
    def radio(self, label, *a, **k): return self._call("radio", label, a, k)
    def multiselect(self, label, *a, **k): return self._call("multiselect", label, a, k)
    def text_area(self, label, *a, **k): return self._call("text_area", label, a, k)


ui = _UI(st)
ui_sidebar = _UI(st.sidebar)


# ---------------------------------------------------------------------------
# GEO — port coordinates and site distance estimate
# ---------------------------------------------------------------------------
import math

PORT_COORDS = {
    "Constanța, Romania": (44.17, 28.65), "Varna, Bulgaria": (43.19, 27.93), "Burgas, Bulgaria": (42.49, 27.48),
    "Gdansk, Poland": (54.40, 18.67), "Gdynia, Poland": (54.53, 18.56), "Koper, Slovenia (Rail Gateway)": (45.55, 13.73),
    "Trieste, Italy": (45.63, 13.77), "Venice, Italy": (45.44, 12.26), "Genoa, Italy": (44.41, 8.90),
    "Piraeus, Greece": (37.94, 23.62), "Thessaloniki, Greece": (40.63, 22.93),
    "Hamburg, Germany": (53.54, 9.97), "Bremerhaven, Germany": (53.56, 8.56),
    "Rotterdam, Netherlands": (51.95, 4.14), "Antwerp, Belgium": (51.28, 4.30),
    "Helsinki / Kotka, Finland": (60.46, 26.95), "Valencia, Spain": (39.44, -0.32), "Marseille, France": (43.40, 4.90),
    "Haifa Bay Port (SIPG), Israel": (32.82, 35.03), "Haifa Port (Adani), Israel": (32.82, 35.00),
    "Israel Shipyards Port (Haifa), Israel": (32.81, 35.04), "Ashdod Port, Israel": (31.82, 34.64),
    "TIL - Hadarom South Port (Ashdod), Israel": (31.80, 34.62), "Eilat Port, Israel": (29.54, 34.95),
}
DEFAULT_SITE_COORDS = {
    "Romania": "44.4268, 26.1025", "Poland": "52.2297, 21.0122", "Hungary": "47.4979, 19.0402",
    "Bulgaria": "42.6977, 23.3219", "Germany": "51.3397, 12.3731", "Italy": "41.9028, 12.4964",
    "Greece": "37.9838, 23.7275", "Finland": "60.1699, 24.9384", "France": "45.7640, 4.8357",
    "Spain": "40.4168, -3.7038", "Netherlands": "52.0907, 5.1214", "Belgium": "50.8503, 4.3517",
    "Austria": "48.2082, 16.3738", "Czech Republic": "50.0755, 14.4378", "Slovakia": "48.1486, 17.1077",
    "Croatia": "45.8150, 15.9819", "Israel": "31.2518, 34.7913",
}
ROAD_FACTOR = 1.3  # straight-line distance x 1.3 ~ typical road distance


def parse_coords(text):
    """Accepts '44.43, 26.10' or '44.4268° N, 26.1025° E' (S / W give negative values)."""
    try:
        parts = [p.strip() for p in str(text).replace(";", ",").split(",")]
        if len(parts) != 2:
            return None
        vals = []
        for p in parts:
            neg = p.upper().endswith(("S", "W"))
            num = float(_re.sub(r"[^0-9.\-]", "", p))
            vals.append(-num if neg else num)
        lat, lon = vals
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (ValueError, TypeError):
        pass
    return None


def road_km(a, b):
    """Estimated road distance in km between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h)) * ROAD_FACTOR

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
# Which vessel types each Israeli port / berth can receive
ISRAEL_PORT_INFO = {
    "Haifa Bay Port (SIPG), Israel": {"container": True, "charter": False},
    "Haifa Port (Adani), Israel": {"container": True, "charter": True},
    "Israel Shipyards Port (Haifa), Israel": {"container": False, "charter": True},
    "Ashdod Port, Israel": {"container": True, "charter": True},
    "TIL - Hadarom South Port (Ashdod), Israel": {"container": True, "charter": False},
    "Eilat Port, Israel": {"container": False, "charter": True},
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

st.sidebar.markdown("### 📁 Project")
project_name = ui_sidebar.text_input("Project Name:", value="New BESS Project")
st.sidebar.markdown("---")
display_currency = ui_sidebar.selectbox(
    "Main Display Currency:",
    options=["EUR (€)", "USD ($)"],
    index=0
)
curr_code = "EUR" if "EUR" in display_currency else "USD"
is_eur_display = ("EUR" in display_currency)

delivery_date = ui_sidebar.date_input("Required-on-Site Date:", value=date(2027, 6, 30),
                                      help="Date the equipment must be on site. Shipments arriving later are flagged.")

trend_multiplier = ui_sidebar.slider(
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

destination_country = ui_sidebar.selectbox(
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

tab0, tab_sail, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Project Brief & BOM",
    "⛴️ Sailing Options",
    "📋 Equipment Mix & Quantities",
    "🚢 Supply Chain & Incoterms",
    "📦 Storage, Demurrage & Drayage",
    "⚖️ Regulation & Approvals",
    "🗺️ European Route Options",
    "✅ Regulatory Checklist",
    "📊 Budget & Carbon Report",
    "🧩 Multi-Shipment Planner"
])

with tab0:
    st.subheader("📝 Project Brief — Requirements, Constraints & Bill of Materials")
    st.markdown("Capture the client's requirements once. They drive the equipment quantities, "
                "the checks on every sailing option and the quote.")

    # ---------------- Dates ----------------
    st.markdown("#### 1. Key Dates")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        brief_exw_ready = ui.date_input("EXW Ready at Factory:", value=date(2026, 12, 18))
    with d2:
        brief_fob_date = ui.date_input("Planned FOB / Cargo at Port of Loading:", value=date(2026, 12, 24))
    with d3:
        brief_must_sail_by = ui.date_input("Must Sail By (latest ETD):", value=date(2026, 12, 31),
                                           help="Latest departure date from the port of loading allowed by the client.")
    with d4:
        st.markdown(f"**Required on Site:**  \n{delivery_date.strftime('%d/%m/%Y')}")
        st.caption("Set in the sidebar")
    if brief_fob_date < brief_exw_ready:
        st.warning("FOB date is earlier than the EXW ready date.")
    if brief_must_sail_by < brief_fob_date:
        st.error("'Must sail by' is earlier than the planned FOB date — no sailing can meet both.")
    else:
        st.caption(f"Sailing window: **{brief_fob_date.strftime('%d/%m/%Y')} – {brief_must_sail_by.strftime('%d/%m/%Y')}** "
                   f"({(brief_must_sail_by - brief_fob_date).days} days).")

    # ---------------- Constraints ----------------
    st.markdown("#### 2. Client Requirements & Constraints")
    c1, c2, c3 = st.columns(3)
    with c1:
        req_direct_only = ui.checkbox("Direct sailing only — no transshipment", value=True)
        req_no_red_sea = ui.checkbox("No Red Sea / Suez Canal routing (Cape of Good Hope)", value=True)
    with c2:
        insurance_by_client = ui.checkbox("Marine insurance arranged by the client (exclude from costs)", value=True)
        req_split_quotes = ui.checkbox("Separate quote per vessel / batch", value=True)
    with c3:
        max_bess_per_vessel = ui.number_input("Max BESS units per vessel (insurer limit, 0 = none):",
                                              min_value=0, value=23, step=1)
    special_handling = ui.text_area(
        "Special handling instructions (manufacturer):",
        value="Vertical lift only, no dragging. Container upright and level throughout transport. "
              "Secured with suitable twist-locks and lashings on board.", height=80)

    # ---------------- Ports ----------------
    st.markdown("#### 3. Ports of Discharge to Quote")
    brief_pods = ui.multiselect("Ports of discharge (POD):", options=destination_ports,
                                default=[p for p in destination_ports if "Haifa Port" in p or p.startswith("Ashdod Port")]
                                or destination_ports[:1])
    if is_israel:
        st.dataframe(pd.DataFrame([
            {"Port / Berth": p.replace(", Israel", ""),
             "Container vessels": "✅" if ISRAEL_PORT_INFO[p]["container"] else "—",
             "Charter / MPP / breakbulk": "✅" if ISRAEL_PORT_INFO[p]["charter"] else "—",
             "Selected": "⭐" if p in brief_pods else ""}
            for p in ISRAEL_PORTS]), use_container_width=True, hide_index=True)
        st.caption("Israel: 4 container ports (Haifa Bay, Haifa/Adani, Ashdod, Hadarom/TIL) plus berths for charter "
                   "and MPP vessels. Sailing options are checked against the vessel type each port can receive.")

    # ---------------- BOM ----------------
    st.markdown("#### 4. Bill of Materials (BOM)")
    st.caption("One line per model. 'Equipment Type' links the line to the cost engine. Weight = gross weight per unit "
               "incl. container. Energy only for BESS lines.")
    if "bom_df" not in st.session_state:
        st.session_state.bom_df = pd.DataFrame([
            {"Item": "BESS container, 4h", "Model": "BESS-5MWh-20SOC", "Equipment Type": "BESS", "Qty": 45,
             "Container": "20ft", "SOC": True, "L (mm)": 6058, "W (mm)": 2438, "H (mm)": 2896,
             "Gross Weight (t)": 42.5, "DG Class": "UN3536 Class 9", "Energy per Unit (MWh)": 5.015},
            {"Item": "Medium Voltage Station", "Model": "MVS-5MW-20SOC", "Equipment Type": "MVS", "Qty": 9,
             "Container": "20ft", "SOC": True, "L (mm)": 6058, "W (mm)": 2438, "H (mm)": 2896,
             "Gross Weight (t)": 17.4, "DG Class": "", "Energy per Unit (MWh)": 0.0},
        ])
    bom_edit = st.data_editor(
        st.session_state.bom_df, key="bom_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "Equipment Type": st.column_config.SelectboxColumn("Equipment Type", options=EQUIPMENT_TYPES, required=True),
            "Container": st.column_config.SelectboxColumn("Container", options=CONTAINER_SIZES, required=True),
            "SOC": st.column_config.CheckboxColumn("SOC", help="Shipper-owned container"),
            "Qty": st.column_config.NumberColumn("Qty", min_value=0, step=1),
            "Gross Weight (t)": st.column_config.NumberColumn("Gross Weight (t)", min_value=0.0, step=0.1, format="%.1f"),
            "Energy per Unit (MWh)": st.column_config.NumberColumn("Energy per Unit (MWh)", min_value=0.0, step=0.1, format="%.3f"),
            "DG Class": st.column_config.TextColumn("DG Class", help="e.g. UN3536 Class 9; empty if not dangerous goods"),
        },
    )
    bom_sync = ui.checkbox("Use BOM quantities in all calculations", value=True)

    # Totals per equipment type and checks
    bom_totals, bom_rows, _bess_mwh_sum, _bess_units = {}, [], 0.0, 0
    STD_MAX_GROSS_T = 30.48   # ISO standard max gross for 20ft / 40ft
    TRUCK_TARE_T, ROAD_LIMIT_T = 15.0, 44.0
    total_weight_t = total_teu_bom = 0.0
    for _, r in bom_edit.iterrows():
        typ = r.get("Equipment Type")
        qty = int(pd.to_numeric(r.get("Qty"), errors="coerce") or 0) if not pd.isna(pd.to_numeric(r.get("Qty"), errors="coerce")) else 0
        if typ not in EQUIPMENT_TYPES or qty <= 0:
            continue
        w = float(pd.to_numeric(r.get("Gross Weight (t)"), errors="coerce") or 0) if not pd.isna(pd.to_numeric(r.get("Gross Weight (t)"), errors="coerce")) else 0.0
        mwh = float(pd.to_numeric(r.get("Energy per Unit (MWh)"), errors="coerce") or 0) if not pd.isna(pd.to_numeric(r.get("Energy per Unit (MWh)"), errors="coerce")) else 0.0
        size = r.get("Container") if r.get("Container") in CONTAINER_SIZES else "20ft"
        bom_totals[typ] = bom_totals.get(typ, 0) + qty
        if typ == "BESS":
            _bess_mwh_sum += qty * mwh
            _bess_units += qty
        total_weight_t += qty * w
        total_teu_bom += qty * teu_factor(size, 1.0)
        flags = []
        if size != "MPP / Breakbulk" and w > STD_MAX_GROSS_T:
            flags.append(f"Heavy box ({w:g} t > {STD_MAX_GROSS_T} t standard) — needs carrier & terminal heavy acceptance, "
                         "heavy-lift surcharge, special-rated SOC")
        if w + TRUCK_TARE_T > ROAD_LIMIT_T:
            flags.append("Abnormal road load — " + ("MoT transport permit per unit" if is_israel else "national abnormal-load permit"))
        dg = str(r.get("DG Class") or "").strip()
        if dg and dg.lower() not in ("nan", "none", "—", "-"):
            flags.append(f"Dangerous goods ({dg}) — DG declaration, DG acceptance, DG yard at origin")
        bom_rows.append({"Item": r.get("Item"), "Qty": qty, "Type": typ, "Container": size, "Weight / Unit (t)": w,
                         "Checks": " · ".join(flags) if flags else "✅ Standard"})
    bom_bess_mwh = round(_bess_mwh_sum / _bess_units, 3) if _bess_units else 0.0

    if bom_rows:
        st.dataframe(pd.DataFrame(bom_rows), use_container_width=True, hide_index=True)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Units", f"{sum(bom_totals.values())}")
    s2.metric("Total Gross Weight", f"{total_weight_t:,.1f} t")
    s3.metric("Volume", f"{total_teu_bom:g} TEU")
    s4.metric("BESS Energy (DC)", f"{_bess_mwh_sum:,.1f} MWh")

    _bess_total = bom_totals.get("BESS", 0)
    if max_bess_per_vessel and _bess_total:
        import math as _m
        min_vessels = _m.ceil(_bess_total / max_bess_per_vessel)
        st.info(f"Insurer limit {max_bess_per_vessel} BESS per vessel → **at least {min_vessels} vessels** for "
                f"{_bess_total} BESS units (e.g. " +
                " + ".join(str(x) for x in [(_bess_total // min_vessels) + (1 if i < _bess_total % min_vessels else 0)
                                            for i in range(min_vessels)]) + ").")
    else:
        min_vessels = 1

with tab_sail:
    st.subheader("⛴️ Sailing Options — All Available Vessels, Carriers & Dates")
    st.markdown("Enter every sailing option you have (different carriers, container lines, MPP / charter vessels, "
                "different weeks). Each option is checked automatically against the Project Brief.")

    VESSEL_TYPES = ["Container vessel", "MPP vessel", "Charter (dedicated)"]
    ROUTINGS = ["Cape of Good Hope", "Suez Canal / Red Sea", "Other"]
    SAIL_POD_OPTIONS = destination_ports + [p for p in ISRAEL_PORTS + all_european_ports if p not in destination_ports]

    if "sail_df" not in st.session_state:
        _haifa = "Haifa Port (Adani), Israel" if is_israel else destination_ports[0]
        _ashdod = "Ashdod Port, Israel" if is_israel else destination_ports[min(1, len(destination_ports) - 1)]
        _bay = "Haifa Bay Port (SIPG), Israel" if is_israel else destination_ports[0]
        _yard = "Israel Shipyards Port (Haifa), Israel" if is_israel else destination_ports[0]
        _base = {"POL": "Shanghai", "Currency": "USD", "DG Surcharge / Unit": 450.0, "Heavy-Lift / Unit": 1200.0,
                 "DG Yard Origin / Unit": 300.0, "Lashing / Unit": 250.0, "BAF / TEU (if not incl.)": 0.0,
                 "Origin Local / Unit": 350.0, "Dest. Local / Unit": 400.0, "Free Days": 5,
                 "Valid Until": date(2027, 1, 15), "Transshipment Port": ""}
        st.session_state.sail_df = pd.DataFrame([
            dict(_base, **{"Option": "A1", "Carrier": "Sample Line A", "Vessel": "Sample Vessel 1", "Vessel Type": "Container vessel",
                           "POD": _haifa, "ETD": date(2026, 12, 26), "ETA": date(2027, 2, 8), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8500.0, "Freight / 40ft": 12000.0}),
            dict(_base, **{"Option": "B1", "Carrier": "Sample Line B", "Vessel": "Sample Vessel 2", "Vessel Type": "Container vessel",
                           "POD": _ashdod, "ETD": date(2026, 12, 29), "ETA": date(2027, 2, 14), "Direct": False,
                           "Transshipment Port": "Piraeus", "Routing": "Cape of Good Hope", "Capacity (units)": 30,
                           "Max Gross / Box (t)": 45.0, "Freight / 20ft": 7200.0, "Freight / 40ft": 10500.0}),
            dict(_base, **{"Option": "C1", "Carrier": "Sample Line C", "Vessel": "Sample Vessel 3", "Vessel Type": "Container vessel",
                           "POD": _bay, "ETD": date(2026, 12, 27), "ETA": date(2027, 1, 22), "Direct": True,
                           "Routing": "Suez Canal / Red Sea", "Capacity (units)": 30, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 6800.0, "Freight / 40ft": 9800.0}),
            dict(_base, **{"Option": "D1", "Carrier": "Sample MPP Operator", "Vessel": "Sample MPP 1", "Vessel Type": "MPP vessel",
                           "POD": _haifa, "ETD": date(2026, 12, 30), "ETA": date(2027, 2, 12), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 30, "Max Gross / Box (t)": 60.0,
                           "Freight / 20ft": 19000.0, "Freight / 40ft": 22000.0, "DG Surcharge / Unit": 0.0,
                           "Heavy-Lift / Unit": 0.0, "Lashing / Unit": 600.0}),
            dict(_base, **{"Option": "A2", "Carrier": "Sample Line A", "Vessel": "Sample Vessel 4", "Vessel Type": "Container vessel",
                           "POD": _haifa, "ETD": date(2027, 1, 2), "ETA": date(2027, 2, 15), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8300.0, "Freight / 40ft": 11800.0}),
            dict(_base, **{"Option": "E1", "Carrier": "Sample Line E", "Vessel": "Sample Vessel 5", "Vessel Type": "Container vessel",
                           "POD": _yard, "ETD": date(2026, 12, 28), "ETA": date(2027, 2, 10), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8000.0, "Freight / 40ft": 11500.0}),
            dict(_base, **{"Option": "B2", "Carrier": "Sample Line B", "Vessel": "Sample Vessel 6", "Vessel Type": "Container vessel",
                           "POD": _ashdod, "ETD": date(2026, 12, 30), "ETA": date(2027, 2, 13), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 24, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8800.0, "Freight / 40ft": 12300.0}),
        ])
    st.caption("Sample options are pre-filled for illustration — replace them with the real offers. "
               "Costs are per unit (one container / one piece). Add rows at the bottom of the table.")

    sail_edit = st.data_editor(
        st.session_state.sail_df, key="sail_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_order=["Option", "Carrier", "Vessel", "Vessel Type", "POL", "POD", "ETD", "ETA", "Direct",
                      "Transshipment Port", "Routing", "Capacity (units)", "Max Gross / Box (t)", "Currency",
                      "Freight / 20ft", "Freight / 40ft", "BAF / TEU (if not incl.)", "DG Surcharge / Unit",
                      "Heavy-Lift / Unit", "DG Yard Origin / Unit", "Lashing / Unit", "Origin Local / Unit",
                      "Dest. Local / Unit", "Free Days", "Valid Until"],
        column_config={
            "Vessel Type": st.column_config.SelectboxColumn("Vessel Type", options=VESSEL_TYPES, required=True),
            "POD": st.column_config.SelectboxColumn("POD", options=SAIL_POD_OPTIONS, required=True),
            "ETD": st.column_config.DateColumn("ETD", format="DD/MM/YYYY"),
            "ETA": st.column_config.DateColumn("ETA", format="DD/MM/YYYY"),
            "Valid Until": st.column_config.DateColumn("Valid Until", format="DD/MM/YYYY"),
            "Direct": st.column_config.CheckboxColumn("Direct", help="Direct sailing, no transshipment"),
            "Routing": st.column_config.SelectboxColumn("Routing", options=ROUTINGS, required=True),
            "Currency": st.column_config.SelectboxColumn("Currency", options=["USD", "EUR"], required=True),
            "Capacity (units)": st.column_config.NumberColumn("Capacity (units)", min_value=0, step=1,
                                                              help="Units / slots offered on this sailing"),
            "Max Gross / Box (t)": st.column_config.NumberColumn("Max Gross / Box (t)", min_value=0.0, step=0.5,
                                                                 help="Heaviest container the carrier accepts on this sailing"),
            "Free Days": st.column_config.NumberColumn("Free Days", min_value=0, step=1),
        },
    )

    # --- heaviest / DG cargo from the BOM, used by the checks
    _bom_valid = [r for r in bom_rows]
    _max_box_t = max([r["Weight / Unit (t)"] for r in _bom_valid if r["Container"] != "MPP / Breakbulk"] or [0.0])

    def _num(v, default=0.0):
        v = pd.to_numeric(v, errors="coerce")
        return default if pd.isna(v) else float(v)

    def _d(v):
        if v is None or (not isinstance(v, (date,)) and pd.isna(v)):
            return None
        return v.date() if hasattr(v, "date") and callable(getattr(v, "date")) else v

    def sailing_unit_cost_usd(row, bom_row):
        """All-in ocean + local cost for one unit of a BOM line on this sailing (USD)."""
        fx = (1.0 / usd_to_eur) if str(row.get("Currency")).upper().startswith("EUR") else 1.0
        size = bom_row["Container"]
        freight = _num(row.get("Freight / 40ft")) if size in ("40ft", "40ft HC") else _num(row.get("Freight / 20ft"))
        c = freight + _num(row.get("Lashing / Unit")) + _num(row.get("Origin Local / Unit")) + _num(row.get("Dest. Local / Unit"))
        c += _num(row.get("BAF / TEU (if not incl.)")) * teu_factor(size, 1.0)
        if "Dangerous goods" in bom_row["Checks"]:
            c += _num(row.get("DG Surcharge / Unit")) + _num(row.get("DG Yard Origin / Unit"))
        if "Heavy box" in bom_row["Checks"]:
            c += _num(row.get("Heavy-Lift / Unit"))
        return c * fx

    sail_results = []
    for _, row in sail_edit.iterrows():
        opt = str(row.get("Option") or "").strip()
        if not opt or opt.lower() == "nan":
            continue
        etd, eta, valid = _d(row.get("ETD")), _d(row.get("ETA")), _d(row.get("Valid Until"))
        pod = row.get("POD") or ""
        vtype = row.get("Vessel Type") or "Container vessel"
        fails, warns = [], []
        if req_direct_only and not bool(row.get("Direct")):
            ts = str(row.get("Transshipment Port") or "").strip()
            fails.append("Transshipment" + (f" via {ts}" if ts and ts.lower() != "nan" else ""))
        if req_no_red_sea and row.get("Routing") == "Suez Canal / Red Sea":
            fails.append("Routes via Red Sea / Suez")
        if etd is None:
            fails.append("No ETD")
        else:
            if etd < brief_fob_date:
                fails.append(f"Sails before cargo is at port ({brief_fob_date.strftime('%d/%m')})")
            if etd > brief_must_sail_by:
                fails.append(f"Sails after the latest ETD ({brief_must_sail_by.strftime('%d/%m')})")
        max_gross = _num(row.get("Max Gross / Box (t)"))
        if _max_box_t and max_gross and max_gross < _max_box_t:
            fails.append(f"Max gross {max_gross:g} t < heaviest box {_max_box_t:g} t")
        elif _max_box_t and not max_gross:
            warns.append("Max gross per box not confirmed")
        if pod in ISRAEL_PORT_INFO:
            needs = "container" if vtype == "Container vessel" else "charter"
            if not ISRAEL_PORT_INFO[pod][needs]:
                fails.append(f"{pod.split(',')[0]} does not receive {'container' if needs == 'container' else 'charter / MPP'} vessels")
        if brief_pods and pod not in brief_pods:
            warns.append("POD not in the client's requested ports")
        on_site = (eta + timedelta(days=4)) if eta else None
        if on_site and on_site > delivery_date:
            warns.append(f"On site ≈ {on_site.strftime('%d/%m/%Y')}, after required date")
        if valid and valid < date.today():
            warns.append("Quote expired")
        elif valid and etd and valid < etd:
            warns.append("Quote validity ends before ETD — reconfirm")
        if _num(row.get("Capacity (units)")) <= 0:
            warns.append("Capacity not stated")

        status = "❌ Not eligible" if fails else ("⚠️ Eligible — check" if warns else "✅ Eligible")
        costs = {}
        for b in _bom_valid:
            if b["Type"] not in costs:
                costs[b["Type"]] = sailing_unit_cost_usd(row, b)
        sail_results.append({
            "Option": opt, "Carrier": row.get("Carrier"), "Vessel": row.get("Vessel"), "Type": vtype,
            "POD": pod, "ETD": etd, "ETA": eta,
            "Transit (d)": (eta - etd).days if (eta and etd) else None,
            "Capacity": int(_num(row.get("Capacity (units)"))),
            "Status": status, "Issues": " · ".join(fails + warns),
            "cost_usd": costs, "free_days": int(_num(row.get("Free Days"))), "eligible": not fails,
        })

    _mult = usd_to_eur if is_eur_display else 1.0
    _sym = "€" if is_eur_display else "$"
    st.markdown("#### Compliance Check vs. Project Brief")
    if sail_results:
        _types = list(dict.fromkeys(b["Type"] for b in _bom_valid))
        st.dataframe(pd.DataFrame([
            dict({k: r[k] for k in ["Status", "Option", "Carrier", "Vessel", "Type", "POD"]},
                 **{"ETD": r["ETD"].strftime("%d/%m/%Y") if r["ETD"] else "",
                    "ETA": r["ETA"].strftime("%d/%m/%Y") if r["ETA"] else "",
                    "Transit (d)": r["Transit (d)"], "Capacity": r["Capacity"]},
                 **{f"All-in / {t} unit": f"{_sym} {r['cost_usd'].get(t, 0) * _mult:,.0f}" for t in _types},
                 **{"Issues": r["Issues"]})
            for r in sail_results]), use_container_width=True, hide_index=True)

        eligible = [r for r in sail_results if r["eligible"]]
        _need_bess = bom_totals.get("BESS", 0)
        _cap = sum(r["Capacity"] for r in eligible)
        e1, e2, e3 = st.columns(3)
        e1.metric("Eligible sailings", f"{len(eligible)} / {len(sail_results)}")
        e2.metric("Eligible capacity", f"{_cap} units", help="Sum of the capacity offered on eligible sailings")
        e3.metric("Units to ship", f"{sum(bom_totals.values())}")
        if len(eligible) < min_vessels:
            st.error(f"Only {len(eligible)} eligible sailing(s) — at least {min_vessels} vessels are needed "
                     f"(insurer limit {max_bess_per_vessel} BESS per vessel). Look for more options.")
        elif _cap < sum(bom_totals.values()):
            st.warning("Eligible capacity is lower than the units to ship — add sailings or confirm more capacity.")
        else:
            st.success("Enough eligible sailings and capacity to ship the whole BOM. Allocation comes next.")
        st.caption("All-in / unit = freight + lashing + origin & destination local charges + BAF (if not included) "
                   "+ DG surcharge & DG yard (DG cargo) + heavy-lift (boxes above 30.48 t). On site ≈ ETA + 4 days.")
    else:
        st.info("Add sailing options to check them against the Project Brief.")

with tab1:
    st.subheader("Equipment Mix & Quantities Configuration")
    if bom_sync:
        st.caption("🔗 Quantities and BESS capacity follow the BOM in the Project Brief tab.")
    st.info(f"All calculations tailored for active BESS deployment in **{destination_country}** (Display Currency: **{curr_code}**).")
    
    col1, col2 = st.columns(2)
    with col1:
        bess_count = (st.number_input("BESS Containers (Units):", min_value=0, value=int(bom_totals.get("BESS", 0)), step=1, disabled=True,
                                 key="bom_sync_bess_count_" + str(int(bom_totals.get("BESS", 0))))
                 if bom_sync else ui.number_input("BESS Containers (Units):", min_value=0, value=20, step=1))
        mvs_count = (st.number_input("Medium Voltage Stations (MVS Units):", min_value=0, value=int(bom_totals.get("MVS", 0)), step=1, disabled=True,
                                 key="bom_sync_mvs_count_" + str(int(bom_totals.get("MVS", 0))))
                 if bom_sync else ui.number_input("Medium Voltage Stations (MVS Units):", min_value=0, value=4, step=1))
        transformer_count = (st.number_input("Transformers / Skids:", min_value=0, value=int(bom_totals.get("Transformer", 0)), step=1, disabled=True,
                                 key="bom_sync_transformer_count_" + str(int(bom_totals.get("Transformer", 0))))
                 if bom_sync else ui.number_input("Transformers / Skids:", min_value=0, value=0, step=1))
    with col2:
        oog_count = (st.number_input("OOG / Special Containers:", min_value=0, value=int(bom_totals.get("OOG", 0)), step=1, disabled=True,
                                 key="bom_sync_oog_count_" + str(int(bom_totals.get("OOG", 0))))
                 if bom_sync else ui.number_input("OOG / Special Containers:", min_value=0, value=0, step=1))
        access_count = (st.number_input("Accessory Containers:", min_value=0, value=int(bom_totals.get("Accessory", 0)), step=1, disabled=True,
                                 key="bom_sync_access_count_" + str(int(bom_totals.get("Accessory", 0))))
                 if bom_sync else ui.number_input("Accessory Containers:", min_value=0, value=2, step=1))
        solar_count = (st.number_input("Solar PV / Inverter Containers:", min_value=0, value=int(bom_totals.get("Solar", 0)), step=1, disabled=True,
                                 key="bom_sync_solar_count_" + str(int(bom_totals.get("Solar", 0))))
                 if bom_sync else ui.number_input("Solar PV / Inverter Containers:", min_value=0, value=0, step=1))

    st.markdown("---")
    st.markdown("#### Site Location & Project Details")
    loc_col1, loc_col2, loc_col3 = st.columns(3)
    with loc_col1:
        site_address = ui.text_input("Site Address / Location:", value=f"Industrial Zone, {destination_country}")
    with loc_col2:
        site_postal = ui.text_input("Postal Code / Region:", value="10000")
    with loc_col3:
        site_coords = ui.text_input("GPS Coordinates (lat, lon):", value=DEFAULT_SITE_COORDS.get(destination_country, "44.4268, 26.1025"))
    site_latlon = parse_coords(site_coords)
    if site_latlon is None:
        st.warning("GPS coordinates not recognised — use the format 44.4268, 26.1025")
    else:
        _dists = sorted(((p, road_km(site_latlon, PORT_COORDS[p])) for p in destination_ports if p in PORT_COORDS),
                        key=lambda x: x[1])
        if _dists:
            st.caption("Nearest ports by estimated road distance: " +
                       " · ".join(f"**{p.split(',')[0]}** ≈ {d:,.0f} km" for p, d in _dists[:3]) +
                       f" (straight line × {ROAD_FACTOR}; confirm with a route survey).")

    st.markdown("---")
    st.markdown(f"#### Equipment EXW Cost ({curr_code})")
    
    col_exw1, col_exw2 = st.columns(2)
    with col_exw1:
      # Currency conversion factor for default values display
        disp_mult = usd_to_eur if (not is_eur_display and usd_to_eur > 0) else 1.0

        bess_exw_input = ui.number_input(f"EXW Cost per BESS Container ({curr_code}):", min_value=0, value=int(400000 * disp_mult), step=5000) if bess_count > 0 else 0
        mvs_exw_input = ui.number_input(f"EXW Cost per MVS Unit ({curr_code}):", min_value=0, value=int(250000 * disp_mult), step=5000) if mvs_count > 0 else 0
        transformer_exw_input = ui.number_input(f"EXW Cost per Transformer ({curr_code}):", min_value=0, value=int(120000 * disp_mult), step=5000) if transformer_count > 0 else 0
with col_exw2:
        oog_exw_input = ui.number_input(f"EXW Cost per OOG Unit ({curr_code}):", min_value=0, value=int(300000 * disp_mult), step=5000) if oog_count > 0 else 0
        access_exw_input = ui.number_input(f"EXW Cost per Accessory Unit ({curr_code}):", min_value=0, value=int(30000 * disp_mult), step=1000) if access_count > 0 else 0
        solar_exw_input = ui.number_input(f"EXW Cost per Solar Unit ({curr_code}):", min_value=0, value=int(50000 * disp_mult), step=1000) if solar_count > 0 else 0

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
        if bom_sync and bom_bess_mwh > 0:
            bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh, DC nameplate):", min_value=0.5,
                                                value=float(bom_bess_mwh), step=0.5, disabled=True,
                                                key=f"bom_sync_mwh_{bom_bess_mwh}")
        else:
            bess_capacity_mwh = ui.number_input("BESS Capacity per Container (MWh, DC nameplate):", min_value=0.5, value=4.0, step=0.5)
    with ec2:
        project_mwac = ui.number_input("Project Power (MWac) — optional:", min_value=0.0, value=0.0, step=1.0,
                                       help="Inverter / PCS AC rating at the point of interconnection. Leave 0 to hide $/kW.")
    with ec3:
        project_mwh_ac = ui.number_input("Usable Energy at POI (MWh AC) — optional:", min_value=0.0, value=0.0, step=1.0,
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
        shipping_line = ui.selectbox("Shipping Line / Carrier:", CARRIERS)
        origin_port = ui.selectbox("Origin Port (China):", [
            "Shanghai, China - SIPG (Waigaoqiao / Yangshan)",
            "Ningbo-Zhoushan, China - Beilun Terminal",
            "Qingdao, China - Qianwan Terminal",
            "Shenzhen, China - Yantian International Container Terminal (YICT)",
            "Shenzhen, China - Shekou Container Terminal (SCT)",
            "Guangzhou, China - Nansha Port"
        ])
    with col_sc2:
        dest_port = ui.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=destination_ports, index=0)
        incoterm_code = ui.selectbox("Incoterm:", options=["EXW", "FOB", "CFR", "CIF", "DAP", "DDP"], index=3)

    st.markdown("---")
    st.markdown(f"#### 1. Ocean Freight per Unit ({curr_code})")
    f_mult = usd_to_eur if is_eur_display else 1.0
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        f_bess = ui.number_input(f"BESS Freight ({curr_code}):", min_value=0, value=int(18000 * f_mult), step=500)
        f_oog = ui.number_input(f"OOG Freight ({curr_code}):", min_value=0, value=int(18000 * f_mult), step=500)
    with cf2:
        f_mvs = ui.number_input(f"MVS Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
        f_trans = ui.number_input(f"Transformer Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
    with cf3:
        f_access = ui.number_input(f"Accessory Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
        f_solar = ui.number_input(f"Solar PV Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)

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
        size_bess = ui.selectbox("BESS container size:", CONTAINER_SIZES[:4], index=1)
        size_oog = ui.selectbox("OOG unit size:", CONTAINER_SIZES[:4], index=2)
    with cs2:
        size_mvs = ui.selectbox("MVS container size:", CONTAINER_SIZES[:4], index=1)
        size_trans = ui.selectbox("Transformer size:", CONTAINER_SIZES[:4], index=1)
    with cs3:
        size_access = ui.selectbox("Accessory container size:", CONTAINER_SIZES[:4], index=3)
        size_solar = ui.selectbox("Solar PV container size:", CONTAINER_SIZES[:4], index=3)
    with cs4:
        ten_ft_teu = ui.number_input("10ft container billed as (TEU):", min_value=0.5, max_value=1.0, value=1.0, step=0.5)

    st.markdown(f"#### 3. Fuel Surcharges per TEU — BAF & EFS ({curr_code})")
    auto_baf = lookup_surcharge(BAF_RATES, shipping_line, dest_port)
    if auto_baf:
        st.caption(f"📡 Auto-filled from the monthly surcharge table: **{auto_baf['carrier']} — {auto_baf['lane']}** · "
                   f"{auto_baf.get('baf_name') or 'BAF'} effective {auto_baf.get('effective_from') or '-'} · "
                   f"checked {auto_baf.get('verified_on') or '-'}"
                   + (f" · [source]({auto_baf['source_url']})" if auto_baf.get('source_url') else ""))
    else:
        st.caption(f"No published surcharge on file for **{shipping_line}** to this port yet — enter the BAF from your quote.")
    include_baf_in_freight = ui.checkbox("Ocean Freight already includes BAF", value=False)
    auto_baf_usd = float(auto_baf["baf_usd_per_teu"]) if auto_baf else 600.0
    auto_efs_usd = float(auto_baf["efs_usd_per_teu"]) if (auto_baf and auto_baf.get("efs_usd_per_teu") is not None) else 0.0

    bf1, bf2, bf3 = st.columns(3)
    with bf1:
        baf_per_teu_in = ui.number_input(f"BAF per TEU ({curr_code}):", min_value=-2000.0,
                                         value=0.0 if include_baf_in_freight else round(auto_baf_usd * f_mult, 2),
                                         step=10.0, disabled=include_baf_in_freight)
    with bf2:
        apply_efs = ui.checkbox("Apply Emergency Fuel Surcharge (EFS)", value=bool(auto_efs_usd))
    with bf3:
        efs_per_teu_in = ui.number_input(f"EFS per TEU ({curr_code}):", min_value=0.0,
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
        dthc_bess = ui.number_input(f"BESS Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_oog = ui.number_input(f"OOG Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
    with ct2:
        dthc_mvs = ui.number_input(f"MVS Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_trans = ui.number_input(f"Transformer THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
    with ct3:
        dthc_access = ui.number_input(f"Accessory THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_solar = ui.number_input(f"Solar PV THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)

    if is_eur_display:
        dthc_bess /= usd_to_eur; dthc_oog /= usd_to_eur; dthc_mvs /= usd_to_eur
        dthc_trans /= usd_to_eur; dthc_access /= usd_to_eur; dthc_solar /= usd_to_eur

    st.markdown(f"#### 5. Origin Charges in China per Container ({curr_code})")
    oc1, oc2 = st.columns(2)
    with oc1:
        origin_truck_in = ui.number_input(f"Factory-to-port trucking per container ({curr_code}):", min_value=0.0,
                                          value=round(220.0 * f_mult, 2), step=10.0)
    with oc2:
        origin_thc_in = ui.number_input(f"Origin THC & export handling per container ({curr_code}):", min_value=0.0,
                                        value=round(130.0 * f_mult, 2), step=10.0)
    origin_truck_usd = origin_truck_in / usd_to_eur if is_eur_display else origin_truck_in
    origin_thc_usd = origin_thc_in / usd_to_eur if is_eur_display else origin_thc_in

    st.markdown("---")
    cc1, cc2 = st.columns(2)
    with cc1:
        insurance_pct = ui.number_input("Marine Insurance Rate (% of CIF):", min_value=0.0, value=0.15, step=0.05)
        if insurance_by_client:
            insurance_pct = 0.0
            st.caption("Marine insurance is arranged by the client (Project Brief) — excluded from the costs.")
        customs_duty_pct = ui.number_input("Customs Duty Rate (%) - BESS/General:", min_value=0.0, value=(0.0 if is_israel else 2.7), step=0.1)
    with cc2:
        mvs_customs_duty_pct = ui.number_input("Customs Duty Rate (%) - MVS / Transformers:", min_value=0.0, value=0.0, step=0.1)
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
        dray_bess = ui.number_input(f"BESS Trucking per unit (Heavy/Hazmat) ({curr_code}):", min_value=0.0, value=5500.0 * dr_mult, step=500.0)
        dray_oog = ui.number_input(f"OOG Trucking per unit ({curr_code}):", min_value=0.0, value=6500.0 * dr_mult, step=500.0)
    with cd2:
        dray_mvs = ui.number_input(f"MVS Trucking per unit ({curr_code}):", min_value=0.0, value=4500.0 * dr_mult, step=500.0)
        dray_trans = ui.number_input(f"Transformer Trucking per unit ({curr_code}):", min_value=0.0, value=4800.0 * dr_mult, step=500.0)
    with cd3:
        dray_access = ui.number_input(f"Accessory Trucking per unit ({curr_code}):", min_value=0.0, value=3000.0 * dr_mult, step=200.0)
        dray_solar = ui.number_input(f"Solar PV Trucking per unit ({curr_code}):", min_value=0.0, value=3000.0 * dr_mult, step=200.0)

    if is_eur_display:
        dray_bess /= usd_to_eur; dray_oog /= usd_to_eur; dray_mvs /= usd_to_eur
        dray_trans /= usd_to_eur; dray_access /= usd_to_eur; dray_solar /= usd_to_eur

    st.markdown("---")
    st.markdown("#### 2. Port Demurrage (Shipping Line) & Port Storage (Terminal)")
    col_st1, col_st2 = st.columns(2)
    with col_st1:
        free_days = ui.number_input("Port Free Days (Demurrage):", min_value=0, value=3, step=1)
        actual_port_days = ui.number_input("Actual Port Days before clearance:", min_value=1, value=6, step=1)
        demurrage_daily_rate = ui.number_input(f"Shipping Line Demurrage Daily Rate per unit ({curr_code}):", min_value=0.0, value=450.0 * dr_mult, step=50.0)
    with col_st2:
        use_external_storage = ui.checkbox("Use External Storage Yard / Buffer", value=False)
        ext_storage_days = ui.number_input("External Storage Days:", min_value=0, value=10, step=1) if use_external_storage else 0
        ext_storage_daily_rate = 250.0

    if is_eur_display:
        demurrage_daily_rate /= usd_to_eur

    include_delay_scenario = ui.checkbox("Include Customs Delay Contingency Scenario (+7 Days)", value=True)

    st.markdown("---")
    st.markdown(f"#### 3. Site Crane & Heavy Unloading ({curr_code})")
    include_site_crane = ui.checkbox("Include Site Crane & Unloading", value=True)
    site_crane_val = ui.number_input(f"Total Crane & Unloading Cost ({curr_code}):", min_value=0.0, value=15000.0 * dr_mult, step=1000.0) if include_site_crane else 0.0
    site_crane_unloading = site_crane_val / usd_to_eur if is_eur_display else site_crane_val

    st.markdown(f"#### 4. Heavy-Lift Route Survey ({curr_code})")
    requires_heavy_lift = ui.checkbox("Include heavy-lift / route survey (bridges, axle loads, turning radius)", value=True)
    heavy_lift_val = ui.number_input(f"Route survey cost ({curr_code}):", min_value=0.0, value=round(2500.0 * dr_mult, 2),
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
            has_importer_permit = ui.checkbox("Importer / consignee holds a valid Toxins Permit", value=False)
        with tp2:
            has_site_permit = ui.checkbox("Project site holds a valid Toxins Permit", value=False)
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
        toxins_val = ui.number_input(f"Toxins Permits — one-time cost, importer + site (application, consultant, toxins officer) ({curr_code}):",
                                     min_value=0.0, value=0.0, step=500.0)

        st.markdown("##### 2. Ministry of Transport — Oversize / Heavy Transport Permit per BESS Container (Hebrew: היתר הובלה)")
        st.info(
            f"Every BESS container requires a transport permit from the Israel Ministry of Transport "
            f"for the port-to-site haul — **{bess_count} permit(s)** for this project. "
            "Currently there is no fee, but submit the requests early so trucks are not held at the port."
        )
        mot_per_unit_val = ui.number_input(f"MoT transport permit cost per BESS container ({curr_code}):",
                                           min_value=0.0, value=0.0, step=50.0)
        include_mot_approval = True
        mot_val = mot_per_unit_val * bess_count

        st.markdown("##### 3. Site Permits & Other Costs")
        st.caption("Site works permits (building, fire department, electrical, etc.) are normally the EPC / site contractor's "
                   "responsibility and are not included unless entered below.")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            other_permits_val = ui.number_input(f"Other permits / consultants ({curr_code}):", min_value=0.0, value=0.0, step=500.0)
        with col_t2:
            epr_val = ui.number_input(
                f"Battery recycling / EPR fee per BESS unit ({curr_code}):", min_value=0.0, value=0.0, step=50.0,
                help="Israeli e-waste & batteries law — recycling through a recognised body (e.g. M.A.I / T.M.I). "
                     "Check with the recycling body whether it applies to your BESS units.")
        include_regulatory = True
        perm_val = toxins_val + other_permits_val
        bp_val = 0.0  # EU Battery Passport does not apply in Israel
    else:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            bp_val = ui.number_input(f"Total Battery Passport Cost ({curr_code}):", min_value=0.0, value=10000.0 * dr_mult, step=1000.0)
            epr_val = ui.number_input(f"Ongoing EPR Fee per BESS unit ({curr_code}):", min_value=0.0, value=450.0 * dr_mult, step=50.0)
        with col_t2:
            include_regulatory = ui.checkbox("Include local site entry permits", value=True)
            perm_val = ui.number_input(f"Local Permits Cost ({curr_code}):", min_value=0.0, value=5000.0 * dr_mult, step=500.0) if include_regulatory else 0.0
            include_mot_approval = ui.checkbox("Include National/Local Approval Fees", value=False)
            mot_val = ui.number_input(f"Approval Fees Cost ({curr_code}):", min_value=0.0, value=3000.0 * dr_mult, step=500.0) if include_mot_approval else 0.0

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
        include_decom_israel = ui.checkbox(
            "Include a decommissioning provision in the Israel budget (optional — EU framework does not apply)", value=False)
    st.info("Future Provision (Benchmark 59–90 USD/kWh)")
    
    decom_scenario_choice = ui.selectbox("Decommissioning Scenario Preset:", options=["Custom", "low (59 $/kWh)", "base (75 $/kWh)", "high (90 $/kWh)"], index=2)
    if "low" in decom_scenario_choice:
        decom_cost_per_kwh = 59.0
    elif "base" in decom_scenario_choice:
        decom_cost_per_kwh = 75.0
    elif "high" in decom_scenario_choice:
        decom_cost_per_kwh = 90.0
    else:
        decom_cost_per_kwh = ui.number_input("Decommissioning Cost per kWh ($/kWh):", min_value=0.0, value=75.0, step=5.0)

    dc1, dc2 = st.columns(2)
    with dc1:
        years_to_decom = ui.number_input("Years to Decommissioning:", min_value=1, value=20, step=1)
        decom_discount_rate = ui.number_input("Discount Rate for PV (%):", min_value=0.0, value=4.0, step=0.5) / 100.0
    with dc2:
        decom_residual_per_kwh = ui.number_input("Residual Material Recovery Value ($/kWh):", min_value=0.0, value=0.0, step=5.0)
        include_oog_in_decom = ui.checkbox("Include OOG Units in Decommissioning Provision", value=False)

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
        applied_vat = ui.number_input("Import VAT Rate (%):", min_value=0.0, value=default_vat, step=0.5)
        st.caption(f"Default: standard VAT rate of {destination_country} ({default_vat:g}%), verified {VAT_TABLE_VERIFIED}. "
                   "Confirm with your customs broker for the specific HS code.")
        vat_recovery_pct = ui.number_input("VAT Recovery Rate (%):", min_value=0.0, value=100.0, step=5.0)
    with vc2:
        vat_paid_by_supplier = ui.checkbox("Import VAT Paid Directly by Supplier", value=False)
        contingency_pct = ui.number_input("Contingency Reserve (%):", min_value=0.0, value=5.0, step=1.0)

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
            il_region = ui.selectbox("Project Site Region (Israel):", list(ISRAEL_REGIONS.keys()))
        with ir2:
            il_base_cost = ui.number_input("Heavy-haul base cost per BESS unit (USD):", min_value=0.0, value=1500.0, step=100.0)
        with ir3:
            il_km_rate = ui.number_input("Heavy-haul rate per km per BESS unit (USD):", min_value=0.0, value=12.0, step=1.0)

        _gps_in_israel = bool(site_latlon and 29.0 <= site_latlon[0] <= 33.5 and 34.0 <= site_latlon[1] <= 36.0)
        if _gps_in_israel:
            st.caption(f"📍 Road distances estimated from the site GPS ({site_coords}) entered in the Equipment tab.")
        st.caption("Ocean transit days and road distances are **indicative defaults** — edit them in the table to match "
                   "current carrier schedules (Suez vs. Cape routing) and the exact site location. "
                   "Check that the Eilat port currently has a service for your cargo before relying on it.")

        il_defaults = pd.DataFrame([
            {"Israeli Port": port,
             "Ocean Transit from China (Days)": days,
             "Road Distance to Site (km)": (round(road_km(site_latlon, PORT_COORDS[port])) if _gps_in_israel
                                            else ISRAEL_REGIONS[il_region][cluster])}
            for port, (cluster, days) in ISRAEL_PORT_CLUSTER.items()
        ])
        il_edit = st.data_editor(
            il_defaults, key=f"il_routes_{il_region}_{site_coords}", hide_index=True, use_container_width=True,
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

        def gateway_site_km(gw_name):
            """Estimated road km from the site GPS to the nearest known port named in the gateway."""
            if not site_latlon:
                return None
            norm = gw_name.lower().replace("ț", "t").replace("ș", "s")
            kms = [road_km(site_latlon, xy) for port, xy in PORT_COORDS.items()
                   if port.split(",")[0].split(" /")[0].lower().replace("ț", "t") in norm]
            return round(min(kms)) if kms else None

        if site_latlon:
            st.caption(f"📍 'Distance from Your Site' is estimated from the site GPS ({site_coords}) entered in the Equipment tab; "
                       "'Inland Trucking Distance' is the reference hub distance.")
        routing_results = []
        for gw in country_info["gateways"]:
            for china_port in china_ports:
                routing_results.append({
                    "Origin Port (China)": china_port,
                    "European Gateway": gw["port"],
                    "Destination Site": country_info["site_name"],
                    "Ocean Transit (Days)": gw["ocean_days"],
                    "Inland Trucking Distance (km)": gw["inland_dist_km"],
                    "Distance from Your Site (km, est.)": gateway_site_km(gw["port"]),
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
    st.subheader(f"✅ Regulatory & Compliance Checklist — {destination_country}")
    st.markdown(
        "What must be in place to ship BESS from China to the site, **who is responsible** and **when**. "
        "Update the status as the project moves — the checklist is saved in the project file."
    )

    # (requirement, authority / rule, responsible party, stage, indicative lead time)
    REQ_COMMON = [
        ("UN38.3 test summary for each battery type", "UN Manual of Tests & Criteria (transport of lithium batteries)",
         "Manufacturer", "Before booking", "Existing test report"),
        ("Safety Data Sheet (SDS / MSDS)", "IMDG Code / carrier DG desk", "Manufacturer", "Before booking", "Existing document"),
        ("Dangerous-goods declaration — Class 9, UN3536 (batteries installed in cargo transport unit)",
         "IMDG Code", "Manufacturer / Forwarder", "Booking", "1–3 days"),
        ("Carrier DG acceptance & port of discharge DG approval", "Shipping line DG desk / destination terminal",
         "Forwarder", "Before booking", "1–2 weeks"),
        ("Container / SOC certificates (CSC plate, survey) for shipper-owned boxes", "CSC Convention",
         "Manufacturer", "Before stuffing", "Existing"),
        ("Commercial invoice, packing list, bill of lading, certificate of origin, insurance certificate",
         "Customs / bank / buyer", "Manufacturer / Forwarder", "At shipment", "At sailing"),
        ("Customs import declaration & HS classification (8507.60 Li-ion; 8504 transformers)",
         "Destination customs", "Importer / Customs broker", "On arrival", "1–5 days"),
        ("Oversize / heavy transport permit for port-to-site haul", "National road authority",
         "Haulier / Forwarder", "Before arrival", "1–4 weeks"),
        ("Site readiness: access road, crane, foundations, unloading plan", "EPC method statement",
         "EPC / Developer", "Before delivery", "Project plan"),
    ]
    REQ_EU = [
        ("EORI number of the importer", "EU Customs Code", "Importer", "Before import", "1–5 days"),
        ("CE marking & EU Declaration of Conformity (LVD, EMC) for BESS / PCS", "EU product legislation",
         "Manufacturer", "Before placing on market", "Existing"),
        ("EU Battery Regulation 2023/1542 — producer / EPR registration in the member state", "Regulation (EU) 2023/1542",
         "Manufacturer / Importer", "Before placing on market", "2–8 weeks"),
        ("EU Battery Passport for industrial batteries > 2 kWh (applies from 18 Feb 2027)", "Regulation (EU) 2023/1542",
         "Manufacturer", "Before placing on market", "Plan ahead"),
        ("ADR dangerous-goods rules for road transport (Class 9)", "ADR", "Haulier", "Inland transport", "Driver / vehicle compliance"),
    ]
    REQ_IL = [
        ("Toxins Permit — importer / consignee", "Ministry of Environmental Protection (Hazardous Substances Law)",
         "Importer", "Before release from port / external storage", "Weeks–months"),
        ("Toxins Permit — project site", "Ministry of Environmental Protection (Hazardous Substances Law)",
         "Developer / Site operator", "Before delivery to site", "Weeks–months"),
        ("Ministry of Transport transport permit — one per BESS container", "Israel Ministry of Transport",
         "Haulier / Forwarder", "Before port-to-site haul", "Apply early"),
        ("Battery / e-waste recycling body arrangement — check applicability", "Israeli e-waste & batteries law",
         "Importer", "Before placing on market", "2–6 weeks"),
    ]
    _reqs = REQ_COMMON + (REQ_IL if is_israel else REQ_EU)
    _saved_status = st.session_state.get("_reg_status", {})

    def _default_status(req):
        if req in _saved_status:
            return _saved_status[req].get("Status", "Not started")
        if is_israel and req.startswith("Toxins Permit — importer"):
            return "Done" if has_importer_permit else "Not started"
        if is_israel and req.startswith("Toxins Permit — project site"):
            return "Done" if has_site_permit else "Not started"
        return "Not started"

    reg_df = pd.DataFrame([
        {"Requirement": r, "Authority / Rule": a, "Responsible": who, "When": when, "Lead Time (indicative)": lt,
         "Status": _default_status(r), "Notes": _saved_status.get(r, {}).get("Notes", "")}
        for r, a, who, when, lt in _reqs
    ])
    reg_edit = st.data_editor(
        reg_df, key=f"reg_checklist_{destination_country}", hide_index=True, use_container_width=True,
        disabled=["Requirement", "Authority / Rule", "Responsible", "When", "Lead Time (indicative)"],
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status", options=["Not started", "In progress", "Done", "Not applicable"], required=True),
            "Notes": st.column_config.TextColumn("Notes"),
        },
    )
    reg_status_now = {row["Requirement"]: {"Status": row["Status"], "Notes": row["Notes"] or ""}
                      for _, row in reg_edit.iterrows()}

    _open = reg_edit[~reg_edit["Status"].isin(["Done", "Not applicable"])]
    c_done, c_open = st.columns(2)
    c_done.metric("Completed", f"{len(reg_edit) - len(_open)} / {len(reg_edit)}")
    c_open.metric("Open items", len(_open))
    if len(_open):
        by_party = _open.groupby("Responsible")["Requirement"].count().sort_values(ascending=False)
        st.markdown("**Open items by responsible party:** " +
                    " · ".join(f"{party}: {n}" for party, n in by_party.items()))
    st.caption("Indicative checklist for planning — confirm the exact requirements with the authorities, "
               "your customs broker and the carrier for each project.")

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
    carbon_per_unit = ui.number_input(
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
    late_shipments = []
    _port_days_by_name = {sh["name"]: int(pd.to_numeric(sh.get("port_days"), errors="coerce") or 0)
                          if not pd.isna(pd.to_numeric(sh.get("port_days"), errors="coerce")) else 0
                          for sh in msp_shipments}
    for r in plan["shipments"]:
        # Estimated on-site date = ETA + port days + 2 days inland haul & unloading
        _on_site = (r["eta"] + timedelta(days=_port_days_by_name.get(r["name"], 0) + 2)) if r["eta"] else None
        if _on_site and delivery_date and _on_site > delivery_date:
            _status = f"⚠️ Late {(_on_site - delivery_date).days}d"
            late_shipments.append(f"{r['name']} ({(_on_site - delivery_date).days} days)")
        elif _on_site and delivery_date:
            _status = f"✅ {(delivery_date - _on_site).days}d buffer"
        else:
            _status = "—"
        rows.append({
            "Shipment": r["name"],
            "Carrier": r["carrier"],
            "Service": r["service"],
            "Units": r["units"],
            "ETD": r["etd"].strftime("%d/%m/%Y") if r["etd"] else "",
            "ETA": r["eta"].strftime("%d/%m/%Y") if r["eta"] else "",
            "Transit (Days)": r["transit_days"] if r["transit_days"] is not None else "",
            "Est. on Site": _on_site.strftime("%d/%m/%Y") if _on_site else "",
            "vs Required Date": _status,
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
    if late_shipments:
        st.error(f"⚠️ Arriving after the required-on-site date ({delivery_date.strftime('%d/%m/%Y')}): "
                 + ", ".join(late_shipments) + ". Move the sailing earlier or change the required date in the sidebar.")
    elif rows:
        st.success(f"✅ All dated shipments are estimated on site before {delivery_date.strftime('%d/%m/%Y')}.")
    st.caption("Est. on Site = ETA + port days + 2 days for inland haul and unloading.")
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
# ---------------------------------------------------------------------------
# PROJECT FILE — save / load (sidebar)
# ---------------------------------------------------------------------------
def _df_records(df):
    out = []
    for rec in df.to_dict(orient="records"):
        clean = {}
        for k, v in rec.items():
            if hasattr(v, "isoformat"):
                v = v.isoformat()[:10]
            elif v is not None and not isinstance(v, (str, bool)) and pd.isna(v):
                v = None
            elif hasattr(v, "item"):
                v = v.item()
            clean[k] = v
        out.append(clean)
    return out


def _records_df(records, date_cols=()):
    df = pd.DataFrame(records)
    for c in date_cols:
        if c in df.columns:
            df[c] = [date.fromisoformat(v) if isinstance(v, str) and v else None for v in df[c]]
    return df


st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Save / Load Project")
_project_file = {
    "app": "Terra Vol Global",
    "file_version": 1,
    "saved_at": date.today().isoformat(),
    "project_name": project_name,
    "usd_eur": st.session_state.get("usd_eur"),
    "values": _SAVED,
    "shipments": _df_records(edited_shipments),
    "shipment_lines": _df_records(edited_lines),
    "regulatory_checklist": reg_status_now,
    "bom": _df_records(bom_edit),
    "sailings": _df_records(sail_edit),
}
_slug = _re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_") or "project"
st.sidebar.download_button(
    "⬇️ Save project file",
    data=json.dumps(_project_file, ensure_ascii=False, indent=1, default=str),
    file_name=f"{_slug}.terravol.json",
    mime="application/json",
    help="Downloads all inputs, shipments and permits of this project. Load it later or send it to a partner.",
)
_upload = st.sidebar.file_uploader("⬆️ Load project file", type=["json"], key="project_upload")
if _upload is not None:
    _upload_id = f"{_upload.name}-{_upload.size}"
    if st.session_state.get("_loaded_upload_id") != _upload_id:
        try:
            _data = json.loads(_upload.getvalue().decode("utf-8"))
            if _data.get("app") != "Terra Vol Global" or "values" not in _data:
                raise ValueError("not a Terra Vol project file")
            st.session_state["_loaded_project_values"] = _data["values"]
            if _data.get("usd_eur"):
                st.session_state["usd_eur"] = float(_data["usd_eur"])
            if _data.get("shipments") is not None:
                st.session_state["msp_shipments"] = _records_df(_data["shipments"], date_cols=("ETD", "ETA"))
                st.session_state["msp_lines"] = _records_df(_data.get("shipment_lines", []))
                for _k in ("msp_shipments_editor", "msp_lines_editor"):
                    st.session_state.pop(_k, None)
            if _data.get("sailings") is not None:
                st.session_state["sail_df"] = _records_df(_data["sailings"], date_cols=("ETD", "ETA", "Valid Until"))
                st.session_state.pop("sail_editor", None)
            if _data.get("bom") is not None:
                st.session_state["bom_df"] = _records_df(_data["bom"])
                st.session_state.pop("bom_editor", None)
            if _data.get("regulatory_checklist"):
                st.session_state["_reg_status"] = _data["regulatory_checklist"]
                for _k in [k for k in st.session_state.keys() if str(k).startswith("reg_checklist_")]:
                    st.session_state.pop(_k, None)
            st.session_state["_loaded_upload_id"] = _upload_id
            st.session_state["_loaded_project_name"] = _data.get("project_name", "")
            st.rerun()
        except Exception as _e:
            st.sidebar.error(f"Could not load this file: {_e}")
if st.session_state.get("_loaded_project_name"):
    st.sidebar.success(f"Loaded: {st.session_state['_loaded_project_name']}")

st.markdown("---")
st.caption(f"© {date.today().year} Terra Vol. Advanced Renewable Energy & Infrastructure Venture.")
