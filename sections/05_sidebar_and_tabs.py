# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 05_sidebar_and_tabs: Sidebar settings, page header and the tab layout.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# --- SIDEBAR SETTINGS ---
logo_path = "logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=180)

st.sidebar.markdown("### Terra Vol Global")
st.sidebar.markdown("---")

st.sidebar.markdown("### 📁 Project")
project_name = ui_sidebar.text_input("Project Name:", value="New BESS Project")
if st.session_state.get("_empty_project"):
    if st.sidebar.button("🎓 Show the demo project", help="Reload the sample data to explore the app"):
        for _k, _ek in _DEMO_TABLES.items():
            st.session_state.pop(_k, None)
            st.session_state.pop(_ek, None)
        st.session_state["_empty_project"] = False
        st.session_state.pop("_blanked", None)
        st.rerun()
else:
    st.sidebar.info("Demo data is shown to explore the app.")
    if st.sidebar.button("🆕 Start an empty project", help="Removes the sample BOM, offers, shipments and suppliers"):
        st.session_state["_empty_project"] = True
        st.session_state["_blanked"] = set()
        for _ek in _DEMO_TABLES.values():
            st.session_state.pop(_ek, None)
        st.rerun()
st.sidebar.markdown("---")
# Country and currency survive a page refresh through the page address (?country=Israel&currency=USD);
# otherwise the user's default from the Secrets is used.
def _start_choice(param, options, user_key):
    try:
        v = st.query_params.get(param)
    except Exception:
        v = None
    if not v and current_user:
        v = current_user.get(user_key)
    for i, o in enumerate(options):
        if v and (o == v or o.startswith(str(v))):
            return i
    return 0


def _remember(param, value):
    try:
        if st.query_params.get(param) != value:
            st.query_params[param] = value
    except Exception:
        pass


_CURRENCIES = ["EUR (€)", "USD ($)"]
display_currency = ui_sidebar.selectbox(
    "Main Display Currency:",
    options=_CURRENCIES,
    index=_start_choice("currency", _CURRENCIES, "default_currency")
)
_remember("currency", display_currency[:3])
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

_COUNTRIES = list(EUROPEAN_VAT_RATES.keys())
destination_country = ui_sidebar.selectbox(
    "Project Destination Country:",
    options=_COUNTRIES,
    index=_start_choice("country", _COUNTRIES, "default_country")
)
_remember("country", destination_country)

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

# ---------------- Views: which tabs each role sees ----------------
# Every tab is always computed (the tabs feed each other); a view only decides which ones are shown.
_TAB_DEFS = [
    ("tab_dash", "🏠 Dashboard"), ("tab0", "📝 Project Brief & BOM"), ("tab_rfq", "📨 Request for Quote"),
    ("tab_sail", "⛴️ Offers Received"), ("tab_quote", "⚖️ Offer Comparison"), ("tab_supp", "🏭 Supplier Comparison"),
    ("tab_permits", "🛂 Permits & Documents"), ("tab1", "📋 Equipment Mix & Quantities"),
    ("tab2", "🚢 Supply Chain & Incoterms"), ("tab3", "📦 Storage, Demurrage & Drayage"),
    ("tab4", "⚖️ Regulation & Approvals"), ("tab5", "🗺️ Route Options"), ("tab6", "✅ Regulatory Checklist"),
    ("tab7", "📊 Budget & Carbon Report"), ("tab8", "🧩 Multi-Shipment Planner"),
    ("tab_site", "🏗️ Site Readiness & Storage"), ("tab_cash", "💵 Cash Flow"), ("tab_budget", "📒 Budget vs Actual"),
    ("tab_scen", "🔀 Scenarios"),
]
VIEWS = {
    "Guided (start here)": ["tab0", "tab_sail", "tab_quote", "tab8", "tab_dash"],
    "Finance": ["tab_dash", "tab0", "tab_quote", "tab_supp", "tab8", "tab_cash", "tab_budget", "tab_scen", "tab7"],
    "Logistics": ["tab_dash", "tab0", "tab_rfq", "tab_sail", "tab_quote", "tab8", "tab_site", "tab_permits", "tab2",
                  "tab3", "tab5"],
    "Country project manager": ["tab_dash", "tab0", "tab_permits", "tab6", "tab4", "tab_site", "tab8", "tab5",
                                "tab_budget"],
    "Environment / ESG": ["tab_dash", "tab0", "tab_quote", "tab_supp", "tab8", "tab7", "tab6", "tab4"],
    "Procurement / Equipment": ["tab_dash", "tab0", "tab_supp", "tab1", "tab_quote", "tab_cash", "tab_scen"],
    "All tabs": [k for k, _ in _TAB_DEFS],
}
_VIEW_NAMES = list(VIEWS.keys())
app_view = ui_sidebar.selectbox("View:", _VIEW_NAMES, index=_start_choice("view", _VIEW_NAMES, "default_view"),
                                help="Shows the tabs for your role. All calculations stay connected in every view.")
_remember("view", app_view.split(" (")[0])
with st.sidebar.expander("📚 Data sources & last verified"):
    for _k, _item, _ver, _src in DATA_SOURCES:
        st.markdown(f"**{_item}**  \n{_ver} — {_src}")
    st.caption("Rates and rules change. Check them with the authority, carrier or adviser before you commit.")
_guide_box = st.container() if app_view.startswith("Guided") else None
_shown = VIEWS[app_view]
_hidden = [k for k, _ in _TAB_DEFS if k not in _shown]
_labels = dict(_TAB_DEFS)
_shown_tabs = st.tabs([_labels[k] for k in _shown])
for _k, _t in zip(_shown, _shown_tabs):
    globals()[_k] = _t
if _hidden:
    # hidden tabs are still built (their inputs and results feed the visible tabs) inside an invisible container
    st.markdown("<style>.st-key-tv_hidden_tabs{display:none !important;}</style>", unsafe_allow_html=True)
    with st.container(key="tv_hidden_tabs"):
        for _k, _t in zip(_hidden, st.tabs([_labels[k] for k in _hidden])):
            globals()[_k] = _t
