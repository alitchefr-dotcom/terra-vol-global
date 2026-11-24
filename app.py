import streamlit as st
import pandas as pd
import os
import io
import json
import importlib
from datetime import date, timedelta
import calc as _calc_module
importlib.reload(_calc_module)  # always load the latest calc.py after an update (no app reboot needed)
import comparison_export as _cmp_mod
importlib.reload(_cmp_mod)
import rfq_export as _rfq_mod
importlib.reload(_rfq_mod)
GOOD_FILL, BAD_FILL = _cmp_mod.GOOD, _cmp_mod.BAD
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
                            "helsinki", "kotka", "netherlands", "germany", "poland", "belgium", "finland",
                            "klaip", "riga", "muuga", "tallinn", "lithuania", "latvia", "estonia"]):
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
    "Helsinki / Kotka, Finland": (60.46, 26.95), "Klaipėda, Lithuania": (55.71, 21.12),
    "Riga, Latvia": (57.00, 24.08), "Muuga / Tallinn, Estonia": (59.50, 24.95), "Valencia, Spain": (39.44, -0.32), "Marseille, France": (43.40, 4.90),
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
    "Lithuania": "54.6872, 25.2797", "Latvia": "56.9496, 24.1052", "Estonia": "59.4370, 24.7536",
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
    "Lithuania": 21.0,
    "Latvia": 21.0,
    "Estonia": 24.0,
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
    "Helsinki / Kotka, Finland", "Valencia, Spain", "Marseille, France",
    "Klaipėda, Lithuania", "Riga, Latvia", "Muuga / Tallinn, Estonia"
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

tab0, tab_rfq, tab_sail, tab_quote, tab_permits, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Project Brief & BOM",
    "📨 Request for Quote",
    "⛴️ Offers Received",
    "⚖️ Offer Comparison",
    "🛂 Permits & Documents",
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
            "DG Class": st.column_config.TextColumn("DG Class", help="e.g. UN3536 Class 9; empty if not dangerous goods; "
                                                    "add 'TBC' if the UN number is not confirmed"),
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
            if any(x in dg.lower() for x in ("tbc", "to be confirmed", "confirm", "/", "?")):
                flags.append("DG classification not final — confirm the UN number with the manufacturer before booking")
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
    st.subheader("⛴️ Offers Received — Sailings Offered by Forwarders & Carriers")
    st.markdown("Enter every offer you received (one row per vessel / sailing; several forwarders, carriers, MPP / charter "
                "vessels and weeks). Each offer is checked automatically against the Project Brief.")

    VESSEL_TYPES = ["Container vessel", "MPP vessel", "Charter (dedicated)"]
    ROUTINGS = ["Cape of Good Hope", "Suez Canal / Red Sea", "Other"]
    SAIL_POD_OPTIONS = destination_ports + [p for p in ISRAEL_PORTS + all_european_ports if p not in destination_ports]

    if "sail_df" not in st.session_state:
        _haifa = "Haifa Port (Adani), Israel" if is_israel else destination_ports[0]
        _ashdod = "Ashdod Port, Israel" if is_israel else destination_ports[min(1, len(destination_ports) - 1)]
        _bay = "Haifa Bay Port (SIPG), Israel" if is_israel else destination_ports[0]
        _yard = "Israel Shipyards Port (Haifa), Israel" if is_israel else destination_ports[0]
        _base = {"Offered By": "Forwarder 1", "Quote Ref": "", "POL": "Shanghai", "Currency": "USD", "DG Surcharge / Unit": 450.0, "Heavy-Lift / Unit": 1200.0,
                 "DG Yard Origin / Unit": 300.0, "Lashing / Unit": 250.0, "BAF / TEU (if not incl.)": 0.0,
                 "Origin Local / Unit": 350.0, "Dest. Local / Unit": 400.0, "Free Days": 5,
                 "Valid Until": date(2027, 1, 15), "Transshipment Port": "",
                 "Price Basis": "Per unit", "Lump Sum": None, "Lump Sum Units": None, "Terms": "Liner terms",
                 "Loading Cost / Unit": None, "Discharge Cost / Unit": None, "DG Acceptance": "Confirmed",
                 "Stowage": "TBC", "Hot Work / D-rings": "Not required", "War Risk & Other / Unit": 0.0,
                 "Load Terminal": "", "Discharge Terminal": ""}
        st.session_state.sail_df = pd.DataFrame([
            dict(_base, **{"Option": "A1", "Carrier": "Sample Line A", "Vessel": "Sample Vessel 1", "Vessel Type": "Container vessel",
                           "POD": _haifa, "ETD": date(2026, 12, 26), "ETA": date(2027, 2, 8), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8500.0, "Freight / 40ft": 12000.0}),
            dict(_base, **{"Offered By": "Forwarder 2", "Option": "B1", "Carrier": "Sample Line B", "Vessel": "Sample Vessel 2", "Vessel Type": "Container vessel",
                           "POD": _ashdod, "ETD": date(2026, 12, 29), "ETA": date(2027, 2, 14), "Direct": False,
                           "Transshipment Port": "Piraeus", "Routing": "Cape of Good Hope", "Capacity (units)": 30,
                           "Max Gross / Box (t)": 45.0, "Freight / 20ft": 7200.0, "Freight / 40ft": 10500.0}),
            dict(_base, **{"Offered By": "Forwarder 3", "Option": "C1", "Carrier": "Sample Line C", "Vessel": "Sample Vessel 3", "Vessel Type": "Container vessel",
                           "POD": _bay, "ETD": date(2026, 12, 27), "ETA": date(2027, 1, 22), "Direct": True,
                           "Routing": "Suez Canal / Red Sea", "Capacity (units)": 30, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 6800.0, "Freight / 40ft": 9800.0}),
            dict(_base, **{"Offered By": "Forwarder 3", "Option": "D1", "Carrier": "Sample MPP Operator", "Vessel": "Sample MPP 1", "Vessel Type": "MPP vessel",
                           "POD": _haifa, "ETD": date(2026, 12, 30), "ETA": date(2027, 2, 12), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 30, "Max Gross / Box (t)": 60.0,
                           "Freight / 20ft": 19000.0, "Freight / 40ft": 22000.0, "DG Surcharge / Unit": 0.0,
                           "Heavy-Lift / Unit": 0.0, "Lashing / Unit": 600.0, "Terms": "FIO", "Stowage": "Under deck",
                           "Hot Work / D-rings": "By shipper", "DG Acceptance": "Pending"}),
            dict(_base, **{"Offered By": "Forwarder 4", "Option": "F1", "Carrier": "Sample Charter Owner", "Vessel": "Sample Charter 1",
                           "Vessel Type": "Charter (dedicated)", "POD": _haifa, "ETD": date(2026, 12, 28), "ETA": date(2027, 2, 9),
                           "Direct": True, "Routing": "Cape of Good Hope", "Capacity (units)": 60, "Max Gross / Box (t)": 60.0,
                           "Freight / 20ft": None, "Freight / 40ft": None, "Price Basis": "Lump sum", "Lump Sum": 980000.0,
                           "Lump Sum Units": 54, "Terms": "FIO", "Loading Cost / Unit": 300.0, "Discharge Cost / Unit": 350.0,
                           "DG Surcharge / Unit": 0.0, "Heavy-Lift / Unit": 0.0, "Lashing / Unit": 0.0, "Stowage": "Under deck",
                           "Hot Work / D-rings": "Included", "War Risk & Other / Unit": 120.0}),
            dict(_base, **{"Option": "A2", "Carrier": "Sample Line A", "Vessel": "Sample Vessel 4", "Vessel Type": "Container vessel",
                           "POD": _haifa, "ETD": date(2027, 1, 2), "ETA": date(2027, 2, 15), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8300.0, "Freight / 40ft": 11800.0}),
            dict(_base, **{"Offered By": "Forwarder 2", "Option": "E1", "Carrier": "Sample Line E", "Vessel": "Sample Vessel 5", "Vessel Type": "Container vessel",
                           "POD": _yard, "ETD": date(2026, 12, 28), "ETA": date(2027, 2, 10), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8000.0, "Freight / 40ft": 11500.0}),
            dict(_base, **{"Offered By": "Forwarder 2", "Option": "B2", "Carrier": "Sample Line B", "Vessel": "Sample Vessel 6",
                           "Vessel Type": "Container vessel",
                           "POD": _ashdod, "ETD": date(2026, 12, 30), "ETA": date(2027, 2, 13), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 24, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8300.0, "Freight / 40ft": 11800.0, "DG Yard Origin / Unit": None,
                           "Heavy-Lift / Unit": None}),
        ])
    st.caption("Sample offers are pre-filled for illustration — replace them with the real offers. Charges are per unit "
               "(one container / one piece): **a number = separate charge · 0 = included in the freight · empty = not "
               "stated or excluded** (filled in and flagged in the comparison). Add rows at the bottom of the table.")

    sail_edit = st.data_editor(
        st.session_state.sail_df, key="sail_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_order=["Offered By", "Quote Ref", "Option", "Carrier", "Vessel", "Vessel Type", "POL", "POD", "ETD", "ETA", "Direct",
                      "Transshipment Port", "Routing", "Capacity (units)", "Max Gross / Box (t)", "Currency",
                      "Freight / 20ft", "Freight / 40ft", "BAF / TEU (if not incl.)", "DG Surcharge / Unit",
                      "Heavy-Lift / Unit", "DG Yard Origin / Unit", "Lashing / Unit", "Origin Local / Unit",
                      "Dest. Local / Unit", "Price Basis", "Lump Sum", "Lump Sum Units", "Terms", "Loading Cost / Unit",
                      "Discharge Cost / Unit", "War Risk & Other / Unit", "DG Acceptance", "Stowage", "Hot Work / D-rings",
                      "Load Terminal", "Discharge Terminal", "Free Days", "Valid Until"],
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
            "Price Basis": st.column_config.SelectboxColumn("Price Basis", options=["Per unit", "Lump sum"], required=True),
            "Lump Sum": st.column_config.NumberColumn("Lump Sum", min_value=0.0, step=10000.0, format="%.0f",
                                                      help="Total freight for the parcel / charter"),
            "Lump Sum Units": st.column_config.NumberColumn("Lump Sum Units", min_value=0, step=1,
                                                            help="Units covered by the lump sum"),
            "Terms": st.column_config.SelectboxColumn("Terms", options=["Liner terms", "FIO", "FILO", "LIFO", "FIOS"], required=True,
                                                      help="FIO = loading & discharge not included; FILO = loading not included; "
                                                           "LIFO = discharge not included"),
            "Loading Cost / Unit": st.column_config.NumberColumn("Loading Cost / Unit", min_value=0.0, step=50.0,
                                                                 help="Stevedoring at the port of loading, if not included in the terms"),
            "Discharge Cost / Unit": st.column_config.NumberColumn("Discharge Cost / Unit", min_value=0.0, step=50.0,
                                                                   help="Stevedoring at the port of discharge, if not included in the terms"),
            "War Risk & Other / Unit": st.column_config.NumberColumn("War Risk & Other / Unit", min_value=0.0, step=10.0),
            "DG Acceptance": st.column_config.SelectboxColumn("DG Acceptance", options=["Confirmed", "Pending", "Refused", "Not stated"]),
            "Stowage": st.column_config.SelectboxColumn("Stowage", options=["Under deck", "On deck", "Mixed", "TBC"]),
            "Hot Work / D-rings": st.column_config.SelectboxColumn("Hot Work / D-rings",
                                                                   options=["Included", "By shipper", "Not required", "TBC"]),
        },
    )

    _imp = st.file_uploader("⬆️ Import offer responses (filled RFQ response templates, .xlsx)", type=["xlsx"],
                            accept_multiple_files=True, key="offer_import")
    if _imp:
        _done = st.session_state.setdefault("_imported_offers", set())
        _new = []
        for _f in _imp:
            _fid = f"{_f.name}-{_f.size}"
            if _fid in _done:
                continue
            try:
                _df = _rfq_mod.read_response(_f.getvalue())
            except Exception as _e:
                st.error(f"Could not read {_f.name}: {_e}")
                continue
            _done.add(_fid)
            if len(_df):
                _new.append(_df)
        if _new:
            _add = pd.concat(_new, ignore_index=True)
            _existing = set(str(x) for x in sail_edit["Option"])
            _k = 1
            _opts = []
            for _, _r in _add.iterrows():
                while f"R{_k}" in _existing:
                    _k += 1
                _opts.append(f"R{_k}")
                _existing.add(f"R{_k}")
            _add["Option"] = _opts
            _defaults = {"Vessel Type": "Container vessel", "Routing": "Other", "Currency": "USD", "Price Basis": "Per unit",
                         "Terms": "Liner terms", "DG Acceptance": "Not stated", "Stowage": "TBC", "Hot Work / D-rings": "TBC",
                         "Direct": False}
            for _c, _v in _defaults.items():
                if _c not in _add.columns:
                    _add[_c] = _v
                else:
                    _add[_c] = _add[_c].where(_add[_c].notna() & (_add[_c].astype(str) != "nan"), _v)
            st.session_state.sail_df = pd.concat([sail_edit, _add], ignore_index=True)
            st.session_state.pop("sail_editor", None)
            st.success(f"Imported {len(_add)} offer line(s).")
            st.rerun()

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

    CHARGE_COLS = {"baf": "BAF / TEU (if not incl.)", "dg": "DG Surcharge / Unit", "heavy": "Heavy-Lift / Unit",
                   "dg_yard": "DG Yard Origin / Unit", "lashing": "Lashing / Unit",
                   "origin": "Origin Local / Unit", "dest": "Dest. Local / Unit"}
    CHARGE_LABELS = {"baf": "BAF", "dg": "DG surcharge", "heavy": "Heavy-lift", "dg_yard": "DG yard at origin",
                     "lashing": "Lashing", "origin": "Origin local charges", "dest": "Destination local charges"}

    def _fx_usd(row):
        return (1.0 / usd_to_eur) if str(row.get("Currency")).upper().startswith("EUR") else 1.0

    def _stated(row, col):
        v = pd.to_numeric(row.get(col), errors="coerce")
        return None if pd.isna(v) else float(v)

    def _vclass(row):
        return "container" if (row.get("Vessel Type") or "Container vessel") == "Container vessel" else "mpp"

    # Highest stated value per charge and vessel class — used to fill charges an offer does not state
    _fill = {}
    for _, _r in sail_edit.iterrows():
        for _k, _c in CHARGE_COLS.items():
            _v = _stated(_r, _c)
            if _v is not None:
                _key = (_vclass(_r), _k)
                _fill[_key] = max(_fill.get(_key, 0.0), _v * _fx_usd(_r))

    _any_dg = any("Dangerous goods" in b["Checks"] for b in _bom_valid)
    _any_heavy = any("Heavy box" in b["Checks"] for b in _bom_valid)

    def _applies(key, bom_row=None):
        if key in ("dg", "dg_yard"):
            return ("Dangerous goods" in bom_row["Checks"]) if bom_row else _any_dg
        if key == "heavy":
            return ("Heavy box" in bom_row["Checks"]) if bom_row else _any_heavy
        return True

    TERM_COLS = {"loading": "Loading Cost / Unit", "discharge": "Discharge Cost / Unit"}
    CHARGE_LABELS.update({"loading": "Loading (terms)", "discharge": "Discharge (terms)"})
    _bom_units_total = sum(b["Qty"] for b in _bom_valid) or 1

    def _term_applies(row, key):
        t = str(row.get("Terms") or "Liner terms")
        if key == "loading":
            return t in ("FIO", "FILO", "FIOS")
        return t in ("FIO", "LIFO", "FIOS")

    _fill_terms = {}
    for _, _r in sail_edit.iterrows():
        for _k, _c in TERM_COLS.items():
            _v = _stated(_r, _c)
            if _v is not None:
                _fill_terms[_k] = max(_fill_terms.get(_k, 0.0), _v * _fx_usd(_r))

    def offer_freight(row, size):
        """Freight per unit in the offer currency — per-unit rate, or lump sum spread over the units it covers."""
        if row.get("Price Basis") == "Lump sum" and _num(row.get("Lump Sum")) > 0:
            return _num(row.get("Lump Sum")) / max(1.0, _num(row.get("Lump Sum Units"), default=_bom_units_total))
        return _num(row.get("Freight / 40ft")) if size in ("40ft", "40ft HC") else _num(row.get("Freight / 20ft"))

    def offer_unit_cost_usd(row, bom_row, normalized=True):
        """Ocean + local cost for one unit of a BOM line (USD). normalized=True fills charges the offer does not state."""
        fx = _fx_usd(row)
        size = bom_row["Container"]
        total = offer_freight(row, size) * fx + _num(row.get("War Risk & Other / Unit")) * fx
        for k, col in TERM_COLS.items():
            if _term_applies(row, k):
                v = _stated(row, col)
                total += v * fx if v is not None else (_fill_terms.get(k, 0.0) if normalized else 0.0)
        for k, col in CHARGE_COLS.items():
            if not _applies(k, bom_row):
                continue
            v = _stated(row, col)
            v = v * fx if v is not None else (_fill.get((_vclass(row), k), 0.0) if normalized else 0.0)
            total += v * (teu_factor(size, 1.0) if k == "baf" else 1.0)
        return total

    def offer_missing(row):
        miss = [CHARGE_LABELS[k] for k, col in CHARGE_COLS.items() if _applies(k) and _stated(row, col) is None]
        miss += [CHARGE_LABELS[k] for k, col in TERM_COLS.items() if _term_applies(row, k) and _stated(row, col) is None]
        return miss

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
        # cost per equipment type = quantity-weighted average over all BOM lines of that type
        # (several BESS models with different weights / sizes / DG status are each priced on their own)
        costs, quoted, _qty_t = {}, {}, {}
        for b in _bom_valid:
            q = max(1, b["Qty"])
            costs[b["Type"]] = costs.get(b["Type"], 0.0) + q * offer_unit_cost_usd(row, b, normalized=True)
            quoted[b["Type"]] = quoted.get(b["Type"], 0.0) + q * offer_unit_cost_usd(row, b, normalized=False)
            _qty_t[b["Type"]] = _qty_t.get(b["Type"], 0) + q
        costs = {t: v / _qty_t[t] for t, v in costs.items()}
        quoted = {t: v / _qty_t[t] for t, v in quoted.items()}
        missing = offer_missing(row)
        if offer_freight(row, "20ft") <= 0 and offer_freight(row, "40ft") <= 0:
            warns.append("Freight not stated")
        _dga = str(row.get("DG Acceptance") or "Not stated")
        if _dga == "Refused":
            fails.append("DG cargo refused by the carrier")
            status = "❌ Not eligible"
        elif _dga in ("Pending", "Not stated", "nan") and _any_dg:
            warns.append(f"DG acceptance {_dga.lower()}")
            if status == "✅ Eligible":
                status = "⚠️ Eligible — check"
            status = "❌ Not eligible" if fails else "⚠️ Eligible — check"
        sail_results.append({
            "Option": opt, "Carrier": row.get("Carrier"), "Vessel": row.get("Vessel"), "Type": vtype,
            "POD": pod, "ETD": etd, "ETA": eta,
            "Transit (d)": (eta - etd).days if (eta and etd) else None,
            "Capacity": int(_num(row.get("Capacity (units)"))),
            "Status": status, "Issues": " · ".join(fails + warns),
            "cost_usd": costs, "quoted_usd": quoted, "missing": missing,
            "offered_by": str(row.get("Offered By") or "").replace("nan", ""),
            "quote_ref": str(row.get("Quote Ref") or "").replace("nan", ""),
            "valid_until": valid, "routing": row.get("Routing"), "direct": bool(row.get("Direct")),
            "terms": str(row.get("Terms") or "Liner terms"), "stowage": str(row.get("Stowage") or "TBC"),
            "dg_acceptance": _dga, "hot_work": str(row.get("Hot Work / D-rings") or "TBC"),
            "price_basis": str(row.get("Price Basis") or "Per unit"),
            "free_days": int(_num(row.get("Free Days"))), "eligible": not fails,
        })

    _mult = usd_to_eur if is_eur_display else 1.0
    _sym = "€" if is_eur_display else "$"
    st.markdown("#### Compliance Check vs. Project Brief")
    if sail_results:
        _types = list(dict.fromkeys(b["Type"] for b in _bom_valid))
        st.dataframe(pd.DataFrame([
            dict({"Status": r["Status"], "Offered By": r["offered_by"]},
                 **{k: r[k] for k in ["Option", "Carrier", "Vessel", "Type", "POD"]},
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
        st.caption("All-in / unit = freight + lashing + origin & destination local charges + BAF + DG surcharge & DG yard "
                   "(DG cargo) + heavy-lift (boxes above 30.48 t). Charges an offer does not state are filled with the highest "
                   "value stated in the other offers (see Offer Comparison). On site ≈ ETA + 4 days.")
    else:
        st.info("Add sailing options to check them against the Project Brief.")


    # =====================================================================
    # PORT RULES & ALLOCATION PLAN (decision support — the carrier decides)
    # =====================================================================
    st.markdown("---")
    st.markdown("#### Port Rules — Limits at the Port of Discharge")
    st.caption("Limits set by ports / terminals for BESS (DG Class 9). Ports sharing a 'Limit Group' share one limit. "
               "Leave empty when there is no known limit. Update when the port changes its rules.")
    if "port_rules_df" not in st.session_state:
        _rules = []
        for p in destination_ports:
            ashdod = is_israel and p.startswith("Ashdod Port")   # government Ashdod Port only (not Hadarom / TIL)
            _rules.append({"Port": p, "Limit Group": p.split(",")[0],
                           "Max BESS in Port at Once": 30 if ashdod else None,
                           "Limit Type": "Temporary" if ashdod else "Firm",
                           "Max DG Dwell (days)": None, "Direct Delivery Required": False,
                           "Notes / Source": "New limit reported Nov 2026 — temporary note, confirm with the port before booking" if ashdod else "",
                           "Last Updated": "2026-11" if ashdod else ""})
        st.session_state.port_rules_df = pd.DataFrame(_rules)
    port_rules_edit = st.data_editor(
        st.session_state.port_rules_df, key="port_rules_editor", hide_index=True, use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Max BESS in Port at Once": st.column_config.NumberColumn(min_value=0, step=1),
            "Limit Type": st.column_config.SelectboxColumn(options=["Firm", "Temporary"], required=True,
                                                           help="Temporary limits give a warning; firm limits block the plan"),
            "Max DG Dwell (days)": st.column_config.NumberColumn(min_value=0, step=1),
            "Direct Delivery Required": st.column_config.CheckboxColumn(),
        },
    )
    port_group_of, group_cap, port_dwell_cap, group_temp = {}, {}, {}, {}
    for _, r in port_rules_edit.iterrows():
        p = r.get("Port")
        if not p or (not isinstance(p, str)):
            continue
        g = str(r.get("Limit Group") or p).strip() or p
        port_group_of[p] = g
        cap = _num(r.get("Max BESS in Port at Once"), default=0)
        if cap > 0:
            group_cap[g] = int(cap) if g not in group_cap else min(group_cap[g], int(cap))
            group_temp[g] = (r.get("Limit Type") == "Temporary")
        dw = _num(r.get("Max DG Dwell (days)"), default=0)
        if dw > 0:
            port_dwell_cap[p] = int(dw)

    st.markdown("#### Allocation Plan — Requested vs. Confirmed by the Carrier")
    st.caption("You decide the split and request it; the carrier confirms, reduces or rolls it. "
               "Effective quantity = Confirmed for Confirmed / Reduced lines, Requested while pending, 0 if Rolled / Cancelled. "
               "For MPP / charter vessels, 'Confirmed' means contracted.")
    PLAN_STATUSES = ["Requested", "Confirmed", "Reduced", "Rolled", "Cancelled"]
    _sail_by_opt = {r["Option"]: r for r in sail_results}
    _bom_types = list(dict.fromkeys(b["Type"] for b in _bom_valid))

    if "plan_df" not in st.session_state:
        st.session_state.plan_df = pd.DataFrame(columns=["Option", "Equipment", "Requested", "Confirmed", "Status", "Port Days"])

    if st.button("📝 Draft a starting plan (optional)",
                 help="Fills the table with a first split on eligible sailings, cheapest first, within the insurer limit "
                      "and the capacity offered. Edit it freely — it is only a starting point."):
        _rows, _remaining = [], dict(bom_totals)
        # lump-sum (charter) offers are left out of the draft — a charter is a decision for the whole parcel
        _elig = sorted([r for r in sail_results if r["eligible"] and r["price_basis"] != "Lump sum"],
                       key=lambda r: r["cost_usd"].get("BESS", 0))
        for r in _elig:
            room = r["Capacity"] or 0
            for t in sorted(_remaining, key=lambda x: x != "BESS"):
                if room <= 0 or _remaining[t] <= 0:
                    continue
                q = min(_remaining[t], room)
                if t == "BESS" and max_bess_per_vessel:
                    q = min(q, max_bess_per_vessel)
                if q > 0:
                    _rows.append({"Option": r["Option"], "Equipment": t, "Requested": int(q), "Confirmed": None,
                                  "Status": "Requested", "Port Days": 3})
                    _remaining[t] -= q
                    room -= q
        st.session_state.plan_df = pd.DataFrame(_rows, columns=["Option", "Equipment", "Requested", "Confirmed", "Status", "Port Days"])
        st.session_state.pop("plan_editor", None)
        st.rerun()

    plan_edit = st.data_editor(
        st.session_state.plan_df, key="plan_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config={
            "Option": st.column_config.SelectboxColumn("Option", options=list(_sail_by_opt.keys()), required=True),
            "Equipment": st.column_config.SelectboxColumn("Equipment", options=_bom_types or EQUIPMENT_TYPES, required=True),
            "Requested": st.column_config.NumberColumn("Requested", min_value=0, step=1),
            "Confirmed": st.column_config.NumberColumn("Confirmed", min_value=0, step=1,
                                                       help="Quantity confirmed by the carrier (or contracted on MPP / charter)"),
            "Status": st.column_config.SelectboxColumn("Status", options=PLAN_STATUSES, required=True),
            "Port Days": st.column_config.NumberColumn("Port Days", min_value=0, step=1,
                                                       help="Planned days in the port of discharge before pick-up"),
        },
    )

    _rows_by_opt_plan = {str(x.get("Option")): x for _, x in sail_edit.iterrows()}
    # ---- effective quantities
    plan_lines = []
    for _, r in plan_edit.iterrows():
        opt = r.get("Option")
        if opt not in _sail_by_opt:
            continue
        req = int(_num(r.get("Requested")))
        conf_raw = pd.to_numeric(r.get("Confirmed"), errors="coerce")
        status = r.get("Status") if r.get("Status") in PLAN_STATUSES else "Requested"
        if status in ("Rolled", "Cancelled"):
            eff = 0
        elif status in ("Confirmed", "Reduced") and not pd.isna(conf_raw):
            eff = int(conf_raw)
        else:
            eff = req
        plan_lines.append({"Option": opt, "Equipment": r.get("Equipment"), "Requested": req,
                           "Confirmed": None if pd.isna(conf_raw) else int(conf_raw), "Status": status,
                           "Effective": eff, "Port Days": int(_num(r.get("Port Days"), default=3))})

    if plan_lines:
        st.markdown("#### Plan Check")
        problems, warnings_, infos_ = [], [], []

        # 1. coverage
        eff_by_type = {}
        for l in plan_lines:
            eff_by_type[l["Equipment"]] = eff_by_type.get(l["Equipment"], 0) + l["Effective"]
        cov_rows = []
        for t in sorted(set(bom_totals) | set(eff_by_type)):
            need, have = bom_totals.get(t, 0), eff_by_type.get(t, 0)
            cov_rows.append({"Equipment": t, "In BOM": need, "On vessels (effective)": have,
                             "Without a vessel": max(0, need - have), "Over-allocated": max(0, have - need)})
            if have < need:
                problems.append(f"{need - have} {t} unit(s) have no vessel yet")
            elif have > need:
                warnings_.append(f"{have - need} {t} unit(s) more than in the BOM")

        # 2. per vessel: insurer limit, capacity, eligibility, carrier changes, arrival
        by_opt = {}
        for l in plan_lines:
            by_opt.setdefault(l["Option"], []).append(l)
        vessel_rows = []
        for opt, ls in by_opt.items():
            s_ = _sail_by_opt[opt]
            bess = sum(l["Effective"] for l in ls if l["Equipment"] == "BESS")
            tot = sum(l["Effective"] for l in ls)
            req_tot = sum(l["Requested"] for l in ls)
            pdays = max(l["Port Days"] for l in ls)
            cost = sum(l["Effective"] * s_["cost_usd"].get(l["Equipment"], 0) for l in ls)
            _srow = _rows_by_opt_plan.get(opt)
            _ls_flag = False
            if s_["price_basis"] == "Lump sum" and _srow is not None and tot > 0:
                # the lump sum is due in full whatever the quantity loaded
                _ls_usd = _num(_srow.get("Lump Sum")) * _fx_usd(_srow)
                _per_unit_ls = offer_freight(_srow, "20ft") * _fx_usd(_srow)
                cost = cost - tot * _per_unit_ls + _ls_usd
                _ls_flag = True
            notes = ["ℹ️ lump sum in full"] if _ls_flag else []
            if not s_["eligible"]:
                problems.append(f"{opt}: sailing does not meet the Project Brief ({s_['Issues']})")
                notes.append("❌ not eligible")
            if max_bess_per_vessel and bess > max_bess_per_vessel:
                problems.append(f"{opt}: {bess} BESS > insurer limit {max_bess_per_vessel}")
                notes.append("❌ insurer limit")
            if s_["Capacity"] and tot > s_["Capacity"]:
                problems.append(f"{opt}: {tot} units > capacity offered {s_['Capacity']}")
                notes.append("❌ capacity")
            for l in ls:
                if l["Status"] in ("Reduced", "Rolled", "Cancelled") and l["Requested"] > l["Effective"]:
                    warnings_.append(f"{opt}: carrier {l['Status'].lower()} {l['Equipment']} by {l['Requested'] - l['Effective']} "
                                     "— re-allocate to another eligible sailing")
            if any(l["Status"] == "Requested" for l in ls):
                infos_.append(f"{opt}: awaiting carrier confirmation")
            pod = s_["POD"]
            if pod in port_dwell_cap and pdays > port_dwell_cap[pod]:
                problems.append(f"{opt}: {pdays} port days > max DG dwell {port_dwell_cap[pod]} at {pod.split(',')[0]}")
            on_site = (s_["ETA"] + timedelta(days=pdays + 2)) if s_["ETA"] else None
            if on_site and on_site > delivery_date:
                warnings_.append(f"{opt}: on site ≈ {on_site.strftime('%d/%m/%Y')}, after the required date")
            vessel_rows.append({"Option": opt, "Carrier": s_["Carrier"], "Vessel": s_["Vessel"], "Type": s_["Type"],
                                "POD": pod.split(",")[0], "ETA": s_["ETA"].strftime("%d/%m/%Y") if s_["ETA"] else "",
                                "BESS": bess, "All units": tot, "Requested": req_tot,
                                "Est. ocean + local cost": f"{_sym} {cost * _mult:,.0f}",
                                "Flags": " ".join(notes) or "✅"})

        # 3. port limit over time (BESS present in each port group per day)
        peak_rows = []
        for g, cap in group_cap.items():
            daily = {}
            for opt, ls in by_opt.items():
                s_ = _sail_by_opt[opt]
                if not s_["ETA"] or port_group_of.get(s_["POD"]) != g:
                    continue
                bess = sum(l["Effective"] for l in ls if l["Equipment"] == "BESS")
                pdays = max(1, max(l["Port Days"] for l in ls))
                for k in range(pdays):
                    d = s_["ETA"] + timedelta(days=k)
                    daily[d] = daily.get(d, 0) + bess
            if daily:
                peak_day = max(daily, key=daily.get)
                peak = daily[peak_day]
                peak_rows.append({"Limit Group": g, "Limit": f"{cap}" + (" (temporary)" if group_temp.get(g) else ""),
                                  "Peak BESS in port": peak, "Peak date": peak_day.strftime("%d/%m/%Y"),
                                  "OK": "✅" if peak <= cap else ("⚠️" if group_temp.get(g) else "❌")})
                if peak > cap:
                    (warnings_ if group_temp.get(g) else problems).append(f"Port limit {g}: {peak} BESS in port on {peak_day.strftime('%d/%m/%Y')} > limit {cap} "
                                    "— spread the arrivals, shorten port days or use another port")

        st.dataframe(pd.DataFrame(vessel_rows), use_container_width=True, hide_index=True)
        cc1, cc2 = st.columns([3, 2])
        with cc1:
            st.dataframe(pd.DataFrame(cov_rows), use_container_width=True, hide_index=True)
        with cc2:
            if peak_rows:
                st.dataframe(pd.DataFrame(peak_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No port limits set for the ports in this plan.")

        if problems:
            st.error("**Plan not feasible yet:**\n\n" + "\n".join(f"* {p}" for p in problems))
        if warnings_:
            st.warning("\n".join(f"* {w}" for w in warnings_))
        if infos_:
            st.info("\n".join(f"* {i}" for i in infos_))
        if not problems and not warnings_:
            st.success("✅ Plan meets the Project Brief, the insurer limit, capacity and port limits.")

        if st.button("➡️ Send this plan to the Multi-Shipment Planner",
                     help="Creates one shipment per vessel with the effective quantities and the sailing's rates."):
            st.session_state["_plan_to_msp"] = {"lines": plan_lines, "sailings": _df_records(sail_edit)}
            st.success("Plan sent — open the Multi-Shipment Planner tab to see the full landed cost.")

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
    _BOX_SIZES = [x for x in CONTAINER_SIZES if x != "MPP / Breakbulk"]
    st.caption("Carriers publish BAF / EFS per TEU: 20ft = 1 TEU, 40ft / 40ft HC = 2 TEU. "
               "A 10ft SOC normally takes a 20ft slot and is billed as 1 TEU (adjustable below).")
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1:
        size_bess = ui.selectbox("BESS container size:", _BOX_SIZES, index=_BOX_SIZES.index("20ft"))
        size_oog = ui.selectbox("OOG unit size:", _BOX_SIZES, index=_BOX_SIZES.index("40ft"))
    with cs2:
        size_mvs = ui.selectbox("MVS container size:", _BOX_SIZES, index=_BOX_SIZES.index("20ft"))
        size_trans = ui.selectbox("Transformer size:", _BOX_SIZES, index=_BOX_SIZES.index("20ft"))
    with cs3:
        size_access = ui.selectbox("Accessory container size:", _BOX_SIZES, index=_BOX_SIZES.index("40ft HC"))
        size_solar = ui.selectbox("Solar PV container size:", _BOX_SIZES, index=_BOX_SIZES.index("40ft HC"))
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

    _sent = st.session_state.pop("_plan_to_msp", None)
    if _sent:
        _sails = {str(r.get("Option")): r for r in _sent["sailings"]}
        _bom_size = {b["Type"]: b["Container"] for b in bom_rows}
        _bom_soc = {}
        for _, _b in bom_edit.iterrows():
            _bom_soc[_b.get("Equipment Type")] = bool(_b.get("SOC"))
        _dray = {"BESS": dray_bess, "OOG": dray_oog, "MVS": dray_mvs, "Transformer": dray_trans,
                 "Accessory": dray_access, "Solar": dray_solar}
        _dray_usd = {k: (v / usd_to_eur if is_eur_display else v) for k, v in _dray.items()}
        _sh_rows, _ln_rows, _seen = [], [], set()
        for l in _sent["lines"]:
            if l["Effective"] <= 0:
                continue
            sr = _sails.get(l["Option"], {})
            name = f"{l['Option']} - {sr.get('Vessel') or ''}".strip(" -")
            vtype = sr.get("Vessel Type") or "Container vessel"
            soc = _bom_soc.get(l["Equipment"], True)
            service = "MPP Vessel" if vtype != "Container vessel" else ("Container Line - SOC" if soc else "Container Line - COC")
            cur = sr.get("Currency") or "USD"
            if name not in _seen:
                _seen.add(name)
                _sh_rows.append({"Shipment": name, "Carrier": sr.get("Carrier") or "Other", "Service": service,
                                 "Origin Port": sr.get("POL") if sr.get("POL") in ["Shanghai", "Ningbo-Zhoushan", "Qingdao",
                                     "Shenzhen - Yantian", "Shenzhen - Shekou", "Guangzhou - Nansha", "Xingang / Tianjin"] else "Other",
                                 "POD": sr.get("POD"),
                                 "ETD": date.fromisoformat(sr["ETD"]) if sr.get("ETD") else None,
                                 "ETA": date.fromisoformat(sr["ETA"]) if sr.get("ETA") else None,
                                 "Currency": "USD", "Origin Charges / Unit": round(float(sr.get("Origin Local / Unit") or 0)
                                     * (1 / usd_to_eur if str(cur).upper().startswith("EUR") else 1), 2),
                                 "Port Days": int(l["Port Days"]), "Free Days": int(sr.get("Free Days") or 0),
                                 "Daily Rate / Unit after Free Days": 100.0, "Extra Lump Sum": 0.0})
            size = _bom_size.get(l["Equipment"], "20ft")
            _sres = _sail_by_opt.get(l["Option"], {})
            _all_in = _sres.get("cost_usd", {}).get(l["Equipment"], 0.0)
            _o_loc = float(sr.get("Origin Local / Unit") or 0) * (1 / usd_to_eur if str(cur).upper().startswith("EUR") else 1)
            _d_loc = float(sr.get("Dest. Local / Unit") or 0) * (1 / usd_to_eur if str(cur).upper().startswith("EUR") else 1)
            _ln_rows.append({"Shipment": name, "Equipment": l["Equipment"], "Qty": int(l["Effective"]),
                             "Container Size": "MPP / Breakbulk" if service == "MPP Vessel" else size, "Currency": "USD",
                             "Freight / Unit": round(max(0.0, _all_in - _o_loc - _d_loc), 2), "BAF / TEU": 0.0,
                             "Apply EFS": False, "EFS / TEU": 0.0, "Dest. THC / Unit": round(_d_loc, 2),
                             "Trucking / Unit": round(_dray_usd.get(l["Equipment"], 0.0), 2)})
        if _sh_rows:
            st.session_state.msp_shipments = pd.DataFrame(_sh_rows)
            st.session_state.msp_lines = pd.DataFrame(_ln_rows)
            st.session_state.pop("msp_shipments_editor", None)
            st.session_state.pop("msp_lines_editor", None)
            st.success(f"Loaded the allocation plan: {len(_sh_rows)} shipment(s) from the Sailing Options tab.")

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
# ---------------------------------------------------------------------------
# OFFER COMPARISON — compare the offers received on a like-for-like basis
# ---------------------------------------------------------------------------
with tab_quote:
    st.subheader("⚖️ Offer Comparison — Like-for-Like View of the Offers Received")
    st.markdown("Compares every offer on the **same basis**: the full BOM shipped at each offer's rates, with charges an "
                "offer does not state filled in (and flagged), plus compliance with the Project Brief and risk flags.")

    cmp_only_eligible = ui.checkbox("Show only offers that meet the Project Brief", value=False)
    _cmp_cur = "EUR" if is_eur_display else "USD"
    _cm = usd_to_eur if is_eur_display else 1.0
    _kwh = _bess_mwh_sum * 1000.0
    _units_total = sum(bom_totals.values())
    _per_vessel_need = -(-_units_total // max(1, min_vessels)) if _units_total else 0

    cmp = []
    for r in sail_results:
        if cmp_only_eligible and not r["eligible"]:
            continue
        full_norm = sum(bom_totals.get(t, 0) * r["cost_usd"].get(t, 0) for t in bom_totals)
        full_quoted = sum(bom_totals.get(t, 0) * r["quoted_usd"].get(t, 0) for t in bom_totals)
        risks = []
        if r["missing"]:
            risks.append("Not stated: " + ", ".join(r["missing"]))
        if r["Capacity"] and _per_vessel_need and r["Capacity"] < min(_per_vessel_need, _units_total):
            risks.append(f"Capacity {r['Capacity']} < ~{_per_vessel_need} units per vessel needed")
        g_ = port_group_of.get(r["POD"])
        if g_ in group_cap:
            risks.append(f"Port limit {group_cap[g_]} BESS at {r['POD'].split(',')[0]}")
        if r["free_days"] and r["free_days"] < 3:
            risks.append(f"Only {r['free_days']} free days")
        if r["valid_until"] and r["ETD"] and r["valid_until"] < r["ETD"]:
            risks.append("Validity ends before ETD")
        if _any_dg and r["dg_acceptance"] != "Confirmed":
            risks.append(f"DG acceptance {r['dg_acceptance'].lower()}")
        if r["stowage"] in ("On deck", "Mixed"):
            risks.append(f"{r['stowage']} stowage — check with insurer & manufacturer")
        if r["hot_work"] in ("By shipper", "TBC"):
            risks.append(f"D-ring hot work {'by shipper' if r['hot_work'] == 'By shipper' else 'TBC'}")
        if r["terms"] != "Liner terms":
            risks.append(f"{r['terms']} terms — stevedoring {'not included' if r['terms'] in ('FIO', 'FIOS') else 'partly excluded'}")
        cmp.append({"r": r, "full_norm": full_norm, "full_quoted": full_quoted, "risks": risks})

    if not cmp:
        st.info("No offers to compare yet — add them in the Offers Received tab.")
    else:
        elig = [c for c in cmp if c["r"]["eligible"]]
        cheapest = min(elig, key=lambda c: c["full_norm"]) if elig else None
        fastest = min([c for c in elig if c["r"]["ETA"]], key=lambda c: c["r"]["ETA"], default=None) if elig else None
        cmp.sort(key=lambda c: (not c["r"]["eligible"], c["full_norm"]))

        h1, h2, h3 = st.columns(3)
        if cheapest:
            h1.metric("Cheapest eligible offer", f"{cheapest['r']['Option']} · {cheapest['r']['offered_by'] or cheapest['r']['Carrier']}",
                      f"{_cmp_cur} {cheapest['full_norm'] * _cm:,.0f} for the full BOM", delta_color="off")
        if fastest:
            h2.metric("Fastest eligible offer", f"{fastest['r']['Option']} · {fastest['r']['offered_by'] or fastest['r']['Carrier']}",
                      f"ETA {fastest['r']['ETA'].strftime('%d/%m/%Y')}", delta_color="off")
        if cheapest and fastest and cheapest is not fastest:
            _dd = (cheapest["r"]["ETA"] - fastest["r"]["ETA"]).days if cheapest["r"]["ETA"] else 0
            h3.metric("Price of speed", f"{_cmp_cur} {(fastest['full_norm'] - cheapest['full_norm']) * _cm:,.0f}",
                      f"{_dd} days earlier", delta_color="off")
        elif cheapest:
            h3.metric("Price of speed", "—", "Cheapest is also the fastest", delta_color="off")
        if not elig:
            st.error("No offer meets the Project Brief yet.")

        headers = ["Rank", "Offered by", "Quote ref", "Carrier", "Vessel", "Type", "POD", "ETD", "ETA", "Transit",
                   "Free days", "Valid until", "Terms", "Stowage", "DG accept.", "Compliance", f"Per BESS unit ({_cmp_cur})",
                   f"Full BOM — quoted ({_cmp_cur})", f"Full BOM — like-for-like ({_cmp_cur})",
                   f"Per kWh ({_cmp_cur})", "vs cheapest", "Risk flags"]
        rows_out, fills, rank = [], [], 0
        for c in cmp:
            r = c["r"]
            if r["eligible"]:
                rank += 1
            delta = (c["full_norm"] - cheapest["full_norm"]) / cheapest["full_norm"] * 100 if (cheapest and cheapest["full_norm"]) else 0
            rows_out.append({
                "Rank": rank if r["eligible"] else "—", "Offered by": r["offered_by"], "Quote ref": r["quote_ref"],
                "Carrier": r["Carrier"], "Vessel": r["Vessel"], "Type": r["Type"].replace(" vessel", ""),
                "POD": r["POD"].split(",")[0],
                "ETD": r["ETD"].strftime("%d/%m/%Y") if r["ETD"] else "", "ETA": r["ETA"].strftime("%d/%m/%Y") if r["ETA"] else "",
                "Transit": r["Transit (d)"], "Free days": r["free_days"],
                "Valid until": r["valid_until"].strftime("%d/%m/%Y") if r["valid_until"] else "",
                "Terms": r["terms"] + (" · lump sum" if r["price_basis"] == "Lump sum" else ""),
                "Stowage": r["stowage"], "DG accept.": r["dg_acceptance"],
                "Compliance": r["Status"] + ("" if r["eligible"] else f" — {r['Issues']}"),
                f"Per BESS unit ({_cmp_cur})": round(r["cost_usd"].get("BESS", 0) * _cm),
                f"Full BOM — quoted ({_cmp_cur})": round(c["full_quoted"] * _cm),
                f"Full BOM — like-for-like ({_cmp_cur})": round(c["full_norm"] * _cm),
                f"Per kWh ({_cmp_cur})": round(c["full_norm"] * _cm / _kwh, 2) if _kwh else "",
                "vs cheapest": ("cheapest" if c is cheapest else f"+{delta:.1f}%") if r["eligible"] else "—",
                "Risk flags": " · ".join(c["risks"]),
            })
            fills.append(GOOD_FILL if (c is cheapest or c is fastest) else (BAD_FILL if not r["eligible"] else None))
        st.dataframe(pd.DataFrame(rows_out), use_container_width=True, hide_index=True)
        st.caption(f"Full BOM = all {_units_total} units of the BOM at the offer's rates (a common yardstick, even though "
                   "the cargo will be split between vessels). 'Like-for-like' fills charges an offer does not state with the "
                   "highest value stated in the other offers for the same vessel type.")

        # charge breakdown per offer (per BESS unit, or first BOM type)
        _bt = "BESS" if "BESS" in bom_totals else (next(iter(bom_totals), None))
        b_rows = []
        _rows_by_opt = {str(x.get("Option")): x for _, x in sail_edit.iterrows()}
        if _bt:
            _bom_line = next(b for b in _bom_valid if b["Type"] == _bt)
            lines = ([("Freight", None)] + [(CHARGE_LABELS[k], k) for k in CHARGE_COLS if _applies(k, _bom_line)]
                     + [(CHARGE_LABELS[k], k) for k in TERM_COLS] + [("War risk & other", "other")])
            b_headers = [f"Charge per {_bt} unit"] + [c["r"]["Option"] for c in cmp]
            for label, key in lines:
                rr = {f"Charge per {_bt} unit": label}
                for c in cmp:
                    row = _rows_by_opt.get(c["r"]["Option"])
                    fx = _fx_usd(row) * _cm
                    size = _bom_line["Container"]
                    if key is None:
                        v = offer_freight(row, size)
                        rr[c["r"]["Option"]] = f"{v * fx:,.0f}" + (" (lump sum)" if row.get("Price Basis") == "Lump sum" else "")
                    elif key == "other":
                        rr[c["r"]["Option"]] = f"{_num(row.get('War Risk & Other / Unit')) * fx:,.0f}"
                    elif key in TERM_COLS:
                        if not _term_applies(row, key):
                            rr[c["r"]["Option"]] = "in terms"
                        else:
                            v = _stated(row, TERM_COLS[key])
                            rr[c["r"]["Option"]] = (f"{v * fx:,.0f}" if v is not None
                                                   else f"not stated → {_fill_terms.get(key, 0.0) * _cm:,.0f}")
                    else:
                        v = _stated(row, CHARGE_COLS[key])
                        mult = teu_factor(size, 1.0) if key == "baf" else 1.0
                        if v is None:
                            rr[c["r"]["Option"]] = f"not stated → {_fill.get((_vclass(row), key), 0.0) * _cm * mult:,.0f}"
                        else:
                            rr[c["r"]["Option"]] = "included" if v == 0 else f"{v * fx * mult:,.0f}"
                b_rows.append(rr)
            with st.expander(f"Charge breakdown per {_bt} unit ({_cmp_cur})"):
                st.dataframe(pd.DataFrame(b_rows), use_container_width=True, hide_index=True)

        basis = [
            f"Project: {project_name}",
            f"Cargo: " + ", ".join(f"{q} × {t}" for t, q in bom_totals.items()) +
            (f" · {_bess_mwh_sum:,.1f} MWh DC" if _bess_mwh_sum else ""),
            f"Sailing window: {brief_fob_date.strftime('%d/%m/%Y')} – {brief_must_sail_by.strftime('%d/%m/%Y')}; "
            f"required on site {delivery_date.strftime('%d/%m/%Y')}",
            "Requirements: " + ", ".join(x for x in [
                "direct sailing only" if req_direct_only else "",
                "no Red Sea / Suez routing" if req_no_red_sea else "",
                f"max {max_bess_per_vessel} BESS per vessel" if max_bess_per_vessel else "",
                "marine insurance by the client" if insurance_by_client else ""] if x),
            "Full BOM = all units of the BOM priced at each offer's per-unit rates (common yardstick).",
            "Like-for-like = charges not stated in an offer are filled with the highest value stated in the other offers "
            "for the same vessel type (container vs MPP / charter). 0 in an offer = included in the freight.",
            "Lump-sum offers are spread over the units they cover. Under FIO / FILO / LIFO terms the excluded loading and / "
            "or discharge (stevedoring) cost is added — stated, or filled from the other offers and flagged.",
            "DG surcharge and DG yard apply to dangerous-goods units only; heavy-lift applies to boxes above 30.48 t gross.",
            "Ocean and local charges only — inland transport, duties, VAT and permits are not part of this comparison.",
        ]
        _xlsx = _cmp_mod.build_comparison_xlsx(
            {"project": project_name, "currency": _cmp_cur,
             "units_text": f"{_units_total} units, {_bess_mwh_sum:,.1f} MWh DC"},
            rows_out, headers,
            money_cols={f"Per BESS unit ({_cmp_cur})", f"Full BOM — quoted ({_cmp_cur})", f"Full BOM — like-for-like ({_cmp_cur})"},
            fills=fills, breakdown_rows=b_rows, breakdown_headers=b_headers if _bt else [], basis_lines=basis)
        st.download_button("⬇️ Download comparison report (Excel)", data=_xlsx,
                           file_name=f"Offer_Comparison_{_re.sub(r'[^A-Za-z0-9]+', '_', project_name)}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------------------
# PERMITS & DOCUMENTS — per-unit road-transport permits and document packages
# ---------------------------------------------------------------------------
# Country templates. Indicative — confirm with the authority / haulier for each project.
EU_PERMIT_AUTHORITY = {
    "Germany": "VEMAGS online system — state road authority (Großraum- und Schwertransport permit)",
    "Romania": "CNAIR — special transport authorisation for abnormal loads (confirm)",
    "Italy": "Exceptional transport authorisation — ANAS / region / province depending on the route",
    "Netherlands": "RDW — exemption (ontheffing) for abnormal transport",
    "France": "Préfecture — exceptional transport permit (TESEO online)",
    "Poland": "GDDKiA / district authority — abnormal vehicle permit (category by weight)",
    "Spain": "DGT — complementary traffic authorisation",
    "Bulgaria": "Road Infrastructure Agency — abnormal load permit (confirm)",
}
PERMIT_TEMPLATES = {
    "Israel": {
        "permit": "Ministry of Transport transport permit (one request per BESS unit)",
        "opened_by": "Haulier (opens the online request; a request number is issued)",
        "lead_days": 21,
        "fixed_docs": [
            ("Manufacturer SDS / MSDS", "Manufacturer"),
            ("Transport & emergency response instructions", "Manufacturer"),
            ("Declaration that the system is integral and cannot be dismantled", "Manufacturer"),
            ("Technical specification & manufacturer instructions for the model", "Manufacturer"),
            ("Transport configuration signed by an engineer (per trailer)", "Haulier / Engineer"),
            ("Haulier licence for dangerous goods transport", "Haulier"),
            ("Driver licences & permits", "Haulier"),
            ("Police permit (only if required by the transport configuration)", "Haulier"),
        ],
        "unique_docs": ["Importer letter describing the transport", "MoT application form",
                        "Container & serial numbers", "Bill of lading showing the model",
                        "Packing list & supplier invoice", "Transport safety officer declaration incl. route"],
    },
    "EU": {
        "permit": "National abnormal-load road permit (per transport / route)",
        "opened_by": "Haulier (applies to the national authority of each country crossed)",
        "lead_days": 28,
        "fixed_docs": [
            ("Safety Data Sheet (SDS)", "Manufacturer"),
            ("UN38.3 test summary", "Manufacturer"),
            ("Indivisibility declaration (load cannot be dismantled)", "Manufacturer"),
            ("Technical specification, lifting & transport instructions", "Manufacturer"),
            ("Vehicle combination data — registration, axle loads, dimensions", "Haulier"),
            ("ADR driver training certificates", "Haulier"),
            ("ADR vehicle equipment & orange plates / Class 9 marking", "Haulier"),
            ("Haulier liability insurance", "Haulier"),
        ],
        "unique_docs": ["Permit application form", "Route plan incl. bridges / restrictions",
                        "Load data (weight, dimensions, centre of gravity)", "ADR transport document",
                        "Escort booking (if required by the permit)", "Container & serial numbers"],
    },
}
PERMIT_STATUSES = ["Not opened", "Opened", "Documents sent", "Approved", "Rejected"]

with tab_permits:
    tmpl_key = "Israel" if is_israel else "EU"
    tmpl = PERMIT_TEMPLATES[tmpl_key]
    st.subheader(f"🛂 Permits & Documents — {destination_country}")
    _auth = tmpl["permit"] if is_israel else EU_PERMIT_AUTHORITY.get(destination_country, "National road authority — abnormal load permit (confirm)")
    st.markdown(f"**Permit:** {tmpl['permit']}  \n**Authority:** {_auth}  \n**Opened by:** {tmpl['opened_by']}  \n"
                f"**Indicative lead time:** ~{tmpl['lead_days']} days")
    if not is_israel:
        st.caption("EU: road transport of BESS falls under ADR (Class 9, UN3536 — from 2027 lithium-metal and sodium-ion "
                   "units get their own UN numbers). A 42 t+ box on a truck exceeds the 40 t (44 t intermodal) limit, so an "
                   "abnormal-load permit is needed in every country crossed — each country issues its own permit.")

    # ---------------- 1. Fixed document library ----------------
    st.markdown("#### 1. Fixed Documents — reused in every request")
    st.caption("Keep one set per manufacturer / importer / haulier. Add where the file is kept (link) and its expiry date.")
    _lib_key = f"doclib_{tmpl_key}"
    if _lib_key not in st.session_state:
        st.session_state[_lib_key] = pd.DataFrame([
            {"Document": d, "Provided by": who, "Company": "", "Link / Location": "", "Valid Until": None, "Have it": False}
            for d, who in tmpl["fixed_docs"]])
    lib_edit = st.data_editor(
        st.session_state[_lib_key], key=f"{_lib_key}_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config={"Valid Until": st.column_config.DateColumn("Valid Until", format="DD/MM/YYYY"),
                       "Have it": st.column_config.CheckboxColumn("Have it")},
    )

    # ---------------- 2. Permit requests per unit ----------------
    st.markdown("#### 2. Permit Requests — one row per unit")
    _site = site_address if "site_address" in globals() else ""
    _units_from_plan = []
    for l in (plan_lines or []):
        _abn = any(b["Type"] == l["Equipment"] and "Abnormal road load" in b["Checks"] for b in bom_rows)
        if l["Effective"] > 0 and (_abn or (is_israel and l["Equipment"] == "BESS")):
            s_ = _sail_by_opt.get(l["Option"])
            for _ in range(l["Effective"]):
                _units_from_plan.append((l["Option"], l["Equipment"], s_))
    _src = "allocation plan" if _units_from_plan else "BOM"
    if not _units_from_plan:
        for b in bom_rows:
            if "Abnormal road load" in b["Checks"] or (is_israel and b["Type"] == "BESS"):
                for _ in range(b["Qty"]):
                    _units_from_plan.append(("", b["Type"], None))

    _req_key = f"permit_req_{tmpl_key}"
    _sig = f"{len(_units_from_plan)}-" + "-".join(sorted({u[0] for u in _units_from_plan}))
    if st.button(f"🔄 Build request list from the {_src} ({len(_units_from_plan)} units)") or _req_key not in st.session_state:
        rows = []
        for i, (opt, typ, s_) in enumerate(_units_from_plan, 1):
            eta = s_["ETA"] if s_ else None
            rows.append(dict({"Unit": f"{typ}-{i:03d}", "Vessel": f"{opt} {s_['Vessel']}" if s_ else "",
                              "POD": s_["POD"].split(",")[0] if s_ else "", "ETA": eta, "B/L No.": "", "Container No.": "",
                              "Serial No.": "", "Request No.": "", "Route / Stops": f"{s_['POD'].split(',')[0] if s_ else 'Port'} → {_site}",
                              "Status": "Not opened"}, **{d: False for d in tmpl["unique_docs"]}))
        st.session_state[_req_key] = pd.DataFrame(rows)
        st.session_state.pop(f"{_req_key}_editor", None)
    st.caption("Fill B/L, container and serial numbers as they become known, the request number once the haulier opens the "
               "request, and tick the unique documents sent. Rebuild only when the plan changes (it resets the table).")
    req_edit = st.data_editor(
        st.session_state[_req_key], key=f"{_req_key}_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config=dict({"ETA": st.column_config.DateColumn("ETA", format="DD/MM/YYYY"),
                            "Status": st.column_config.SelectboxColumn("Status", options=PERMIT_STATUSES, required=True)},
                           **{d: st.column_config.CheckboxColumn(d) for d in tmpl["unique_docs"]}),
    )

    # ---------------- 3. Dashboard ----------------
    st.markdown("#### 3. Readiness by Vessel")
    _today = date.today()
    _lib_missing, _lib_expiring = [], []
    _last_eta = max([_d(x) for x in req_edit["ETA"] if _d(x)] or [None]) if len(req_edit) else None
    for _, d in lib_edit.iterrows():
        if not bool(d.get("Have it")):
            _lib_missing.append(d.get("Document"))
        vu = _d(d.get("Valid Until"))
        if vu and (vu < _today or (_last_eta and vu < _last_eta)):
            _lib_expiring.append(f"{d.get('Document')} (valid until {vu.strftime('%d/%m/%Y')})")
    dash = []
    for vessel, grp in req_edit.groupby("Vessel", dropna=False):
        etas = [_d(x) for x in grp["ETA"] if _d(x)]
        eta = min(etas) if etas else None
        approved = int((grp["Status"] == "Approved").sum())
        opened = int(grp["Request No."].astype(str).str.strip().replace("nan", "").ne("").sum())
        docs_done = int(grp[tmpl["unique_docs"]].all(axis=1).sum()) if len(grp) else 0
        days_left = (eta - _today).days if eta else None
        if approved == len(grp):
            flag = "✅ All approved"
        elif days_left is not None and days_left <= tmpl["lead_days"]:
            flag = f"🔴 ETA in {days_left} d — {len(grp) - approved} not approved"
        elif days_left is not None and days_left <= tmpl["lead_days"] * 2:
            flag = "🟠 Start now"
        else:
            flag = "⏳ On track"
        dash.append({"Vessel": vessel or "(no vessel)", "ETA": eta.strftime("%d/%m/%Y") if eta else "", "Units": len(grp),
                     "Requests opened": opened, "Unique docs complete": docs_done, "Approved": approved,
                     "Days to ETA": days_left if days_left is not None else "", "Status": flag})
    if dash:
        st.dataframe(pd.DataFrame(dash), use_container_width=True, hide_index=True)
    if is_israel or any(group_cap.values()):
        st.caption("Permits must be in hand **before the ETA** — several ports require BESS to leave the port right after discharge.")
    if _lib_missing:
        st.warning("Fixed documents missing: " + ", ".join(_lib_missing))
    if _lib_expiring:
        st.error("Fixed documents expired or expiring before the last ETA: " + ", ".join(_lib_expiring))

    # ---------------- 4. Document package text ----------------
    st.markdown("#### 4. Document Package for a Request")
    _req_nos = [str(x).strip() for x in req_edit["Request No."] if str(x).strip() not in ("", "nan", "None")]
    if not _req_nos:
        st.info("Enter a request number in the table above to generate its document package.")
    else:
        pk1, pk2 = st.columns([2, 1])
        with pk1:
            sel_req = st.selectbox("Request:", _req_nos, key="pkg_request")
        with pk2:
            pkg_lang = st.selectbox("Language:", ["Hebrew", "English"] if is_israel else ["English"], key="pkg_lang")
        rr = req_edit[req_edit["Request No."].astype(str).str.strip() == sel_req].iloc[0]
        _importer = next((str(x.get("Company")) for _, x in lib_edit.iterrows()
                          if "Manufacturer" not in str(x.get("Provided by")) and str(x.get("Company")) not in ("", "nan")), "")
        _maker = next((str(x.get("Company")) for _, x in lib_edit.iterrows()
                       if str(x.get("Provided by")) == "Manufacturer" and str(x.get("Company")) not in ("", "nan")), "")
        route = str(rr.get("Route / Stops") or "")
        fixed = [str(d.get("Document")) for _, d in lib_edit.iterrows()]
        unique = tmpl["unique_docs"]
        if pkg_lang == "Hebrew":
            HE_FIXED = {
                "Manufacturer SDS / MSDS": "גיליון MSDS של היצרן",
                "Transport & emergency response instructions": "הוראות שינוע ותגובה בחירום",
                "Declaration that the system is integral and cannot be dismantled": "הצהרה שהמערכת אחודה ואינטגרלית ואינה ניתנת לפירוק",
                "Technical specification & manufacturer instructions for the model": "מפרט טכני והוראות יצרן לדגם",
                "Transport configuration signed by an engineer (per trailer)": "תצורת שינוע חתומה על ידי מהנדס, לכל עגלה",
                "Haulier licence for dangerous goods transport": "רישיון מוביל להובלת חומרים מסוכנים",
                "Driver licences & permits": "רישיונות והיתרים של הנהגים",
                "Police permit (only if required by the transport configuration)": "היתר משטרה (אם נדרש בתצורת ההובלה)",
            }
            HE_UNIQUE = {
                "Importer letter describing the transport": "מכתב היבואן המתאר את ההובלה המבוקשת",
                "MoT application form": "טופס הפנייה ומסמכי הבקשה למשרד התחבורה",
                "Container & serial numbers": "מספרי המכולות והמספרים הסידוריים של המערכת",
                "Bill of lading showing the model": "שטר מטען שבו מצוין דגם המערכת",
                "Packing list & supplier invoice": "רשימת אריזה וחשבון ספק",
                "Transport safety officer declaration incl. route": "הצהרת קצין הבטיחות בתעבורה, כולל תיאור מסלול הנסיעה",
            }
            lines = [f"שלום רב,", "",
                     f"מצורפים המסמכים לבקשה מס' {sel_req} במערכת משרד התחבורה.",
                     f"הבקשה היא לשינוע יחידת אגירה {rr.get('Unit')}"
                     + (f" של היצרן {_maker}" if _maker else "") + (f" עבור {_importer}" if _importer else "")
                     + f", במסלול: {route}.", "",
                     "א. מסמכים קבועים, זהים בכל הבקשות:"]
            lines += [f"{i}. {HE_FIXED.get(d, d)}" for i, d in enumerate(fixed, 1)]
            lines += ["", f"ב. מסמכים ייחודיים לבקשה מס' {sel_req}:"]
            lines += [f"{i}. {HE_UNIQUE.get(d, d)}" for i, d in enumerate(unique, 1)]
            lines += ["", f"מכולה: {rr.get('Container No.') or '—'} | מס' סידורי: {rr.get('Serial No.') or '—'} | "
                          f"שטר מטען: {rr.get('B/L No.') or '—'}"]
            if _d(rr.get("ETA")):
                lines += ["", f"האונייה צפויה להגיע ב-{_d(rr.get('ETA')).strftime('%d/%m/%Y')}; נבקש שאישור ההובלה יהיה בידינו לפני כן."]
            lines += ["", "תודה רבה,"]
        else:
            lines = ["Dear Sir / Madam,", "",
                     f"Please find attached the documents for permit request no. {sel_req}.",
                     f"The request covers the transport of unit {rr.get('Unit')}" + (f" made by {_maker}" if _maker else "")
                     + (f" for {_importer}" if _importer else "") + f", route: {route}.", "",
                     "A. Fixed documents (identical for all requests):"]
            lines += [f"{i}. {d}" for i, d in enumerate(fixed, 1)]
            lines += ["", f"B. Documents specific to request no. {sel_req}:"]
            lines += [f"{i}. {d}" for i, d in enumerate(unique, 1)]
            lines += ["", f"Container: {rr.get('Container No.') or '—'} | Serial no.: {rr.get('Serial No.') or '—'} | "
                          f"B/L: {rr.get('B/L No.') or '—'}"]
            if _d(rr.get("ETA")):
                lines += ["", f"The vessel is expected on {_d(rr.get('ETA')).strftime('%d/%m/%Y')}; we kindly ask to receive "
                              "the permit before that date."]
            lines += ["", "Kind regards,"]
        _missing_u = [d for d in unique if not bool(rr.get(d))]
        if _missing_u:
            st.warning("Not yet ticked as ready for this request: " + ", ".join(_missing_u))
        st.text_area("Email text (copy):", value="\n".join(lines), height=360, key=f"pkg_text_{sel_req}_{pkg_lang}")


# ---------------------------------------------------------------------------
# REQUEST FOR QUOTATION — generated from the Project Brief
# ---------------------------------------------------------------------------
with tab_rfq:
    st.subheader("📨 Request for Quotation (RFQ)")
    st.markdown("Generates the RFQ email from the Project Brief and a **response template** for forwarders / carriers. "
                "Filled templates are imported in **Offers Received** with one click, so every offer arrives in the same "
                "structure and the comparison is automatic.")

    r1, r2, r3 = st.columns(3)
    with r1:
        rfq_pol = ui.selectbox("Port of loading:", ["Shanghai", "Ningbo-Zhoushan", "Qingdao", "Shenzhen - Yantian",
                                                    "Shenzhen - Shekou", "Guangzhou - Nansha", "Xingang / Tianjin", "Other"])
        rfq_incoterm = ui.selectbox("Sales terms:", ["FOB", "FCA", "EXW", "CFR", "CIF", "DAP"], index=0)
    with r2:
        rfq_deadline = ui.date_input("Reply by:", value=date.today() + timedelta(days=7))
        rfq_company = ui.text_input("Requesting company:", value="")
    with r3:
        rfq_contact = ui.text_input("Contact name / email:", value="")
        rfq_ref = ui.text_input("RFQ reference:", value=f"RFQ-{date.today().strftime('%Y%m%d')}")
    o1, o2, o3 = st.columns(3)
    with o1:
        rfq_charter_ok = ui.checkbox("Invite part / full charter alternatives", value=True)
    with o2:
        rfq_experience = ui.checkbox("Ask for references of similar heavy Class 9 SOC shipments", value=True)
    with o3:
        rfq_separate = ui.checkbox("Ask for a separate offer per vessel / batch", value=bool(req_split_quotes))

    _pods_txt = " / ".join(p.split(",")[0] + ("" if "," not in p else f" ({p.split(',')[-1].strip()})") for p in brief_pods) \
        or "to be advised"
    _bess_n = bom_totals.get("BESS", 0)
    L = [f"Subject: {rfq_ref} — Ocean transport of {sum(bom_totals.values())} units BESS project cargo — "
         f"{rfq_pol} to {_pods_txt}", "",
         "Dear Sir / Madam,", "",
         f"We are pleased to request your best offer for the ocean transport of the following project cargo"
         + (f" for {project_name}" if project_name else "") + ".", "",
         "CARGO DETAILS"]
    for _, b in bom_edit.iterrows():
        q_ = int(_num(b.get("Qty")))
        if q_ <= 0:
            continue
        dg_ = str(b.get("DG Class") or "").replace("nan", "").strip()
        dims = " x ".join(str(int(_num(b.get(c)))) for c in ("L (mm)", "W (mm)", "H (mm)") if _num(b.get(c)))
        L.append(f"- {b.get('Item')} ({b.get('Model')}): {q_} units, {b.get('Container')}"
                 f"{' SOC' if bool(b.get('SOC')) else ''}" + (f", {dims} mm" if dims else "")
                 + f", approx. {_num(b.get('Gross Weight (t)')):g} t gross each"
                 + (f", {dg_}" if dg_ else ", non-DG"))
    L.append(f"- Total: {sum(bom_totals.values())} units, approx. {total_weight_t:,.0f} t, {total_teu_bom:g} TEU")
    if any("Dangerous goods" in b["Checks"] for b in bom_rows):
        L.append("- SDS / MSDS and UN38.3 test summary attached.")
    if any("DG classification not final" in b["Checks"] for b in bom_rows):
        L.append("- The UN number is still to be confirmed by the manufacturer — please quote for both options if relevant.")
    L += ["", "ROUTING & DATES",
          f"- Port of loading: {rfq_pol}, China ({rfq_incoterm})",
          f"- Port(s) of discharge: {_pods_txt}" + (" — please quote each port separately" if len(brief_pods) > 1 else ""),
          f"- Cargo ready (EXW): {brief_exw_ready.strftime('%d/%m/%Y')} · at port / FOB: {brief_fob_date.strftime('%d/%m/%Y')}",
          f"- Latest departure from China: {brief_must_sail_by.strftime('%d/%m/%Y')}",
          f"- Required on site: {delivery_date.strftime('%d/%m/%Y')}", "",
          "MANDATORY REQUIREMENTS"]
    _n = 1
    if req_direct_only:
        L.append(f"{_n}. Direct sailing without transshipment — no discharge or reloading onto another vessel at any stage. "
                 "Please confirm in writing."); _n += 1
    if req_no_red_sea:
        L.append(f"{_n}. No transit of the Red Sea (Bab el-Mandeb / Suez Canal). Please state the full routing."); _n += 1
    if max_bess_per_vessel and _bess_n > max_bess_per_vessel:
        L.append(f"{_n}. Maximum {max_bess_per_vessel} BESS units per vessel (insurer limit) — at least {min_vessels} vessels."); _n += 1
    if rfq_separate:
        L.append(f"{_n}. A separate offer per vessel / batch."); _n += 1
    if special_handling:
        L.append(f"{_n}. Handling per the manufacturer's instructions: {special_handling.strip()}"); _n += 1
    if insurance_by_client:
        L.append(f"{_n}. Marine insurance is arranged by us — not to be included."); _n += 1
    for p_, g_ in port_group_of.items():
        if g_ in group_cap and p_ in brief_pods:
            L.append(f"{_n}. {p_.split(',')[0]}: max {group_cap[g_]} BESS in port at once — please consider when "
                     "proposing sailings."); _n += 1
    L += ["", "PLEASE QUOTE (one line per vessel / sailing in the attached response template)",
          "1. Freight rate per unit and / or lump sum, with your terms (Liner terms / FIO / FILO / LIFO).",
          "2. Vessel name and type, ETD and ETA, transit time and full routing; confirmation of direct sailing.",
          "3. Confirmation of DG acceptance, proposed stowage (on / under deck) and segregation.",
          "4. Lashing and securing arrangements, including any hot work for D-rings, and who is responsible.",
          "5. Terminal and DG handling at the port of loading (incl. DG yard) and the discharge terminal.",
          "6. All surcharges itemised (BAF, EFS, DG, heavy-lift / overweight, war risk, other) and local charges at "
          "origin and destination.",
          "7. Free time at the port of discharge and offer validity."]
    if rfq_experience:
        L.append("8. References of similar shipments you performed (Class 9, 40 t+ in 20ft SOC, direct sailing), with a contact.")
    if rfq_charter_ok:
        L += ["", "If you can offer a part or full charter instead of a liner parcel, please include it as an alternative."]
    L += ["", f"Please reply by {rfq_deadline.strftime('%d/%m/%Y')}, using the attached response template.", "",
          "Best regards,", rfq_contact or "", rfq_company or ""]
    rfq_text = "\n".join(L).rstrip() + "\n"

    st.text_area("RFQ email (edit and copy):", value=rfq_text, height=520, key=f"rfq_text_{hash(rfq_text)}")
    instructions = [
        "Fill one row per vessel / sailing on the 'Offer' sheet, starting in row 3 (row 2 shows what each column expects).",
        "Charges per unit (one container / one piece): enter the amount; 0 = included in the freight; leave empty only if "
        "the charge does not apply.",
        "BAF per TEU (20ft = 1 TEU, 40ft = 2 TEU). For lump-sum offers fill 'Lump Sum' and 'Lump Sum Units'.",
        "Dates as dd/mm/yyyy. Use the drop-down lists where offered.",
        f"Reply by {rfq_deadline.strftime('%d/%m/%Y')}.",
    ]
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("⬇️ RFQ email (.txt)", data=rfq_text.encode("utf-8"), file_name=f"{rfq_ref}.txt", mime="text/plain")
    with d2:
        st.download_button("⬇️ Response template (Excel) — attach to the RFQ",
                           data=_rfq_mod.build_response_template(project_name, rfq_ref, brief_pods, instructions),
                           file_name=f"{rfq_ref}_Offer_Response.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("When a forwarder returns the template, import it in the Offers Received tab.")


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
    "port_rules": _df_records(port_rules_edit),
    "allocation_plan": _df_records(plan_edit),
    "permit_template": tmpl_key,
    "document_library": _df_records(lib_edit),
    "permit_requests": _df_records(req_edit),
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
            if _data.get("permit_template") and _data.get("document_library") is not None:
                _tk = _data["permit_template"]
                st.session_state[f"doclib_{_tk}"] = _records_df(_data["document_library"], date_cols=("Valid Until",))
                st.session_state.pop(f"doclib_{_tk}_editor", None)
                if _data.get("permit_requests") is not None:
                    st.session_state[f"permit_req_{_tk}"] = _records_df(_data["permit_requests"], date_cols=("ETA",))
                    st.session_state.pop(f"permit_req_{_tk}_editor", None)
            if _data.get("port_rules") is not None:
                st.session_state["port_rules_df"] = _records_df(_data["port_rules"])
                st.session_state.pop("port_rules_editor", None)
            if _data.get("allocation_plan") is not None:
                st.session_state["plan_df"] = _records_df(_data["allocation_plan"])
                st.session_state.pop("plan_editor", None)
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
