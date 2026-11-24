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

tab_dash, tab0, tab_rfq, tab_sail, tab_quote, tab_permits, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab_cash, tab_budget, tab_scen = st.tabs([
    "🏠 Dashboard",
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
    "🧩 Multi-Shipment Planner",
    "💵 Cash Flow",
    "📒 Budget vs Actual",
    "🔀 Scenarios"
])
