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

# --- SIDEBAR WITH LOGO ---
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

# --- MAIN PAGE HEADER WITH PROPORTIONAL BODY LOGO ---
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Terra Vol")
    st.markdown(f"##### *Professional BESS Landed Cost & Logistics Engine — Target Market: {destination_country}*")
with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)

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
        bess_count = st.number_input("כמות מכולות (40' HC DG) BESS:", min_value=0, value=20, step=1)
        mvs_count = st.number_input("כמות תחנות מתח גבוה (MVS):", min_value=0, value=4, step=1)
        transformer_count = st.number_input("כמות שנאים ראשיים:", min_value=0, value=2, step=1)
    with col2:
        oog_count = st.number_input("כמות מכולות חריגות (OOG):", min_value=0, value=0, step=1)
        access_count = st.number_input("מכולות ציוד נלווה / יבש:", min_value=0, value=2, step=1)
        solar_count = st.number_input("יחידות פאנלים סולאריים (PV):", min_value=0, value=0, step=1)

    st.markdown("---")
    col_exw1, col_exw2 = st.columns(2)
    with col_exw1:
        bess_exw = st.number_input("עלות EXW ליחידת BESS ($):", min_value=10000, value=400000, step=5000)
        mvs_exw = st.number_input("עלות EXW ליחידת MVS ($):", min_value=5000, value=250000, step=5000)
        transformer_exw = st.number_input("עלות EXW ליחידת שנאי ($):", min_value=5000, value=120000, step=5000)
    with col_exw2:
        oog_exw = st.number_input("עלות EXW ליחידת OOG ($):", min_value=10000, value=400000, step=5000)
        access_exw = st.number_input("עלות EXW ליחידת ציוד נלווה ($):", min_value=1000, value=50000, step=1000)
        solar_exw = st.number_input("עלות EXW ליחידה סולארית ($):", min_value=1000, value=300000, step=1000)

    bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh):", min_value=1.0, value=4.0, step=0.5)

with tab2:
    st.subheader("Supply Chain & Incoterms Management")
    
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        shipping_line = st.selectbox("Shipping Line / Carrier:", ["MSC", "Maersk", "CMA CGM", "COSCO Shipping", "Hapag-Lloyd", "Evergreen Line", "ONE", "HMM"])
        origin_port = st.selectbox("Origin Port (China):", ["Shanghai, China", "Ningbo, China", "Shenzhen, China"])
    with col_sc2:
        dest_port = st.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=available_ports)
        incoterm_code = st.selectbox("Incoterm:", options=["EXW", "FOB", "CFR", "CIF", "DAP", "DDP"], index=3)

    st.markdown("---")
    col_fr1, col_fr2 = st.columns(2)
    with col_fr1:
        unit_freight = st.number_input("Base Ocean Freight per Container (USD):", min_value=1000, value=15000, step=500)
        baf_val = st.number_input("BAF per Container (USD):", min_value=0, value=1500, step=100)
        dthc_val = st.number_input("Destination THC per Container (USD):", min_value=100, value=800, step=50)
    with col_fr2:
        insurance_pct = st.number_input("Marine Insurance Rate (% of CFR):", min_value=0.0, value=0.15, step=0.05)
        customs_duty_pct = st.number_input("Customs Duty Rate (%) - BESS/General:", min_value=0.0, value=2.7, step=0.1)

    st.markdown("#### European Route & Corridor Analysis")
    st.dataframe(corridors_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Storage, Demurrage & Drayage Optimization")
    
    col_st1, col_st2 = st.columns(2)
    with col_st1:
        free_days = st.number_input("Port Free Days (BESS often 0):", min_value=0, value=0, step=1)
        actual_port_days = st.number_input("Actual Port Days before clearance:", min_value=1, value=5, step=1)
        demurrage_daily_rate = st.number_input("Demurrage / Storage Daily Rate per Container (USD):", min_value=50, value=450, step=50)
    with col_st2:
        drayage_unit = st.number_input("Inland Drayage (Port to Site) per Container (USD):", min_value=500, value=4500, step=500)
        use_external_storage = st.checkbox("Use External Safe Storage Yard", value=False)
        ext_storage_days = st.number_input("External Storage Days:", min_value=0, value=10, step=1) if use_external_storage else 0
        ext_storage_daily_rate = 250.0

    include_delay_scenario = st.checkbox("Include Custom Delay Contingency Scenario (+7 Days)", value=True)

with tab4:
    st.subheader("Regulatory, Taxes & Complete Landed Cost Summary")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        applied_vat = st.number_input("Import VAT Rate (%):", min_value=0.0, value=19.0, step=0.5)
        vat_recovery_pct = st.number_input("VAT Recovery Rate (%):", min_value=0.0, value=100.0, step=5.0)
        vat_paid_by_supplier = st.checkbox("Import VAT Paid Directly by Supplier", value=False)
    with col_t2:
        contingency_pct = st.number_input("Contingency Reserve (%):", min_value=0.0, value=5.0, step=1.0)
        epr_recycling_total_usd = st.number_input("EPR & Recycling Compliance Total (USD):", min_value=0, value=15000, step=1000)
        battery_passport_total_usd = st.number_input("EU Battery Passport Total (USD):", min_value=0, value=10000, step=1000)

    # --- RUN CALCULATION ENGINE ---
    results = calculate_project_costs(
        bess_count=bess_count, bess_exw=bess_exw,
        oog_count=oog_count, oog_exw=oog_exw,
        mvs_count=mvs_count, mvs_exw=mvs_exw,
        transformer_count=transformer_count, transformer_exw=transformer_exw,
        access_count=access_count, access_exw=access_exw,
        solar_count=solar_count, solar_exw=solar_exw,
        unit_freight_bess=unit_freight, unit_freight_oog=unit_freight, unit_freight_mvs=unit_freight,
        unit_freight_trans=unit_freight, unit_freight_access=unit_freight, unit_freight_solar=unit_freight,
        baf_bess=baf_val, baf_oog=baf_val, baf_mvs=baf_val, baf_trans=baf_val, baf_access=baf_val, baf_solar=baf_val,
        dthc_bess=dthc_val, dthc_oog=dthc_val, dthc_mvs=dthc_val, dthc_trans=dthc_val, dthc_access=dthc_val, dthc_solar=dthc_val,
        drayage_bess=drayage_unit, drayage_oog=drayage_unit, drayage_mvs=drayage_unit,
        drayage_trans=drayage_unit, drayage_access=drayage_unit, drayage_solar=drayage_unit,
        trend_multiplier=trend_multiplier, insurance_pct=insurance_pct,
        customs_duty_pct=customs_duty_pct, applied_vat=applied_vat, vat_recovery_pct=vat_recovery_pct,
        vat_paid_by_supplier=vat_paid_by_supplier, incoterm_code=incoterm_code,
        dest_country_code=dest_code,
        local_regulatory_permits=5000.0, mot_total_approval_cost=3000.0,
        include_regulatory=True, include_mot_approval=True,
        site_crane_unloading=12000.0, include_site_crane=True,
        epr_recycling_total_usd=epr_recycling_total_usd, battery_passport_total_usd=battery_passport_total_usd,
        requires_heavy_lift=True, heavy_lift_survey_cost=4500.0,
        actual_port_days=actual_port_days, free_days=free_days, demurrage_daily_rate=demurrage_daily_rate,
        use_external_storage=use_external_storage, ext_storage_days=ext_storage_days,
        ext_storage_daily_rate=ext_storage_daily_rate, include_delay_scenario=include_delay_scenario,
        bess_capacity_mwh=bess_capacity_mwh, decom_cost_per_kwh=15.0
    )

    st.markdown("---")
    st.subheader("📊 Financial Summary & Landed Cost Breakdown")

    landed_usd = results["total_landed_cost_ex_vat"]
    landed_display = convert_currency(landed_usd, "USD", curr_code, usd_to_eur)
    
    exw_display = convert_currency(results["trended_exw"], "USD", curr_code, usd_to_eur)
    supplier_display = convert_currency(results["supplier_scope_total"], "USD", curr_code, usd_to_eur)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Landed Cost (Ex. VAT)", format_currency(landed_display, curr_code))
    m2.metric("Total Equipment EXW", format_currency(exw_display, curr_code))
    m3.metric(f"Supplier Scope ({incoterm_code})", format_currency(supplier_display, curr_code))

    st.markdown("#### Detailed Cost Breakdown (USD)")
    breakdown_df = pd.DataFrame([
        {"Cost Element": k.replace("_", " ").title(), "Amount (USD)": v}
        for k, v in results["cost_lines"].items() if v > 0
    ])
    st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption(f"© {date.today().year} Terra Vol. Advanced Renewable Energy & Infrastructure Venture.")
