# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 00_setup: Imports, constants, helpers (save/load wrapper, geo, surcharge table), page config & styling.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
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
import carbon as _carbon_mod
importlib.reload(_carbon_mod)
import supplier_compare as _sup_mod
importlib.reload(_sup_mod)
import ai_import as _ai_mod
importlib.reload(_ai_mod)
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
        if kind == "number_input" and not args:
            # Streamlit refuses a mix of int and float in min / max / value / step: use float if any is float
            _nk = [k for k in ("min_value", "max_value", "value", "step") if isinstance(kw.get(k), (int, float))
                   and not isinstance(kw.get(k), bool)]
            if any(isinstance(kw[k], float) for k in _nk):
                for k in _nk:
                    kw[k] = float(kw[k])
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
