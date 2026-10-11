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

# --- SIDEBAR ---
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

# --- MAIN PAGE HEADER ---
col_title, col_logo = st.columns([4, 1])
with col_title:
    st.title("Terra Vol")
    st.markdown(f"##### *Professional BESS Landed Cost & Logistics Engine — Target Market: {destination_country}*")
with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)

st.markdown("---")

# --- TABS DEFINITION (Full 7 Tabs Suite) ---
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
    st.info(f"All calculations in **{curr_code}** tailored for active BESS deployment in **{destination_country}**.")
    
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
    col_exw1, col_exw2 = st.columns(2)
    with col_exw1:
        bess_exw = st.number_input("EXW Cost per BESS Container (USD):", min_value=10000, value=300000, step=5000)
        mvs_exw = st.number_input("EXW Cost per MVS Unit (USD):", min_value=5000, value=120000, step=5000)
        transformer_exw = st.number_input("EXW Cost per Transformer (USD):", min_value=5000, value=80000, step=5000)
    with col_exw2:
        oog_exw = st.number_input("EXW Cost per OOG Unit (USD):", min_value=10000, value=150000, step=5000)
        access_count_exw = st.number_input("EXW Cost per Accessory Unit (USD):", min_value=1000, value=30000, step=1000)
        solar_exw = st.number_input("EXW Cost per Solar Unit (USD):", min_value=1000, value=50000, step=1000)

    bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh):", min_value=1.0, value=4.0, step=0.5)

with tab2:
    st.subheader("Ocean Freight, BAF & Destination THC")
    
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        shipping_line = st.selectbox(
            "Shipping Line / Carrier:", 
            [
                "MSC", 
                "Maersk", 
                "CMA CGM", 
                "COSCO Shipping", 
                "Hapag-Lloyd", 
                "Evergreen Line", 
                "ONE (Ocean Network Express)", 
                "HMM"
            ]
        )
        origin_port = st.selectbox(
            "Origin Port (China):", 
            [
                "Shanghai, China - Waigaoqiao / Yangshan",
                "Ningbo-Zhoushan, China - Beilun Terminal",
                "Qingdao, China - Qianwan Terminal",
                "Shenzhen, China - Yantian International Container Terminal (YICT)",
                "Shenzhen, China - Shekou Container Terminal (SCT - MSC Call)",
                "Guangzhou, China - Nansha Port"
            ]
        )
    with col_sc2:
        dest_port = st.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=available_ports)
        incoterm_code = st.selectbox("Incoterm:", options=["EXW", "FOB", "CFR", "CIF", "DAP", "DDP"], index=3)

    st.markdown("---")
    st.markdown("#### 1. Ocean Freight per Unit ($)")
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        unit_freight_bess = st.number_input("BESS Freight ($):", min_value=1000, value=15000, step=500)
        unit_freight_oog = st.number_input("OOG Freight ($):", min_value=1000, value=18000, step=500)
    with cf2:
        unit_freight_mvs = st.number_input("MVS Freight ($):", min_value=1000, value=15000, step=500)
        unit_freight_trans = st.number_input("Transformer Freight ($):", min_value=1000, value=15000, step=500)
    with cf3:
        unit_freight_access = st.number_input("Accessory Freight ($):", min_value=1000, value=10000, step=500)
        unit_freight_solar = st.number_input("Solar PV Freight ($):", min_value=1000, value=10000, step=500)

    st.markdown("#### 2. Bunker Adjustment Factor (BAF) per Unit ($)")
    include_baf_in_freight = st.checkbox("Ocean Freight already includes BAF", value=False)
    baf_default = 0.0 if include_baf_in_freight else 1500.0
    
    cb1, cb2, cb3 = st.columns(3)
    with cb1:
        baf_bess = st.number_input("BESS BAF ($):", min_value=0.0, value=baf_default, step=100.0)
        baf_oog = st.number_input("OOG BAF ($):", min_value=0.0, value=baf_default, step=100.0)
    with cb2:
        baf_mvs = st.number_input("MVS BAF ($):", min_value=0.0, value=baf_default, step=100.0)
        baf_trans = st.number_input("Transformer BAF ($):", min_value=0.0, value=baf_default, step=100.0)
    with cb3:
        baf_access = st.number_input("Accessory BAF ($):", min_value=0.0, value=baf_default, step=100.0)
        baf_solar = st.number_input("Solar PV BAF ($):", min_value=0.0, value=baf_default, step=100.0)

    st.markdown("#### 3. Destination Terminal Handling Charges (Destination THC) ($)")
    ct1, ct2, ct3 = st.columns(3)
    with ct1:
        dthc_bess = st.number_input("BESS Destination THC ($):", min_value=100, value=800, step=50)
        dthc_oog = st.number_input("OOG Destination THC ($):", min_value=100, value=1000, step=50)
    with ct2:
        dthc_mvs = st.number_input("MVS Destination THC ($):", min_value=100, value=800, step=50)
        dthc_trans = st.number_input("Transformer THC ($):", min_value=100, value=800, step=50)
    with ct3:
        dthc_access = st.number_input("Accessory THC ($):", min_value=100, value=600, step=50)
        dthc_solar = st.number_input("Solar PV THC ($):", min_value=100, value=600, step=50)

    st.markdown("---")
    cc1, cc2 = st.columns(2)
    with cc1:
        insurance_pct = st.number_input("Marine Insurance Rate (% of CIF):", min_value=0.0, value=0.15, step=0.05)
        customs_duty_pct = st.number_input("Customs Duty Rate (%) - BESS/General:", min_value=0.0, value=2.7, step=0.1)
    with cc2:
        mvs_customs_duty_pct = st.number_input("Customs Duty Rate (%) - MVS / Transformers:", min_value=0.0, value=0.0, step=0.1)
        st.info("💡 Solar PV / Inverters are automatically 0% exempt under EU green energy trade regulations.")

with tab3:
    st.subheader("Storage, Demurrage & Inland Drayage")
    
    st.markdown("#### 1. Port-to-Site Inland Drayage per Unit ($)")
    cd1, cd2, cd3 = st.columns(3)
    with cd1:
        drayage_bess = st.number_input("BESS Trucking per unit ($):", min_value=500, value=4500, step=500)
        drayage_oog = st.number_input("OOG Trucking per unit ($):", min_value=500, value=5500, step=500)
    with cd2:
        drayage_mvs = st.number_input("MVS Trucking per unit ($):", min_value=500, value=4500, step=500)
        drayage_trans = st.number_input("Transformer Trucking per unit ($):", min_value=500, value=4500, step=500)
    with cd3:
        drayage_access = st.number_input("Accessory Trucking per unit ($):", min_value=500, value=3000, step=500)
        drayage_solar = st.number_input("Solar PV Trucking per unit ($):", min_value=500, value=3000, step=500)

    st.markdown("---")
    st.markdown("#### 2. Port Demurrage & External Storage")
    col_st1, col_st2 = st.columns(2)
    with col_st1:
        free_days = st.number_input("Port Free Days (BESS often 0):", min_value=0, value=0, step=1)
        actual_port_days = st.number_input("Actual Port Days before clearance:", min_value=1, value=5, step=1)
        demurrage_daily_rate = st.number_input("Demurrage Daily Rate ($):", min_value=50, value=450, step=50)
    with col_st2:
        use_external_storage = st.checkbox("Use External Storage Yard", value=False)
        ext_storage_days = st.number_input("External Storage Days:", min_value=0, value=10, step=1) if use_external_storage else 0
        ext_storage_daily_rate = 250.0

    include_delay_scenario = st.checkbox("Include Custom Delay Contingency Scenario (+7 Days)", value=True)

    st.markdown("---")
    st.markdown("#### 3. Site Crane & Unloading")
    include_site_crane = st.checkbox("Include Site Crane & Unloading", value=True)
    site_crane_unloading = st.number_input("Total Crane & Unloading Cost ($):", min_value=0, value=12000, step=1000) if include_site_crane else 0.0

with tab4:
    st.subheader("Regulation, Sustainability & Approvals")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        battery_passport_total_usd = st.number_input("Total Battery Passport Cost ($):", min_value=0, value=10000, step=1000)
        epr_recycling_total_usd = st.number_input("Ongoing EPR Fee per BESS unit ($):", min_value=0, value=450, step=50)
    with col_t2:
        include_regulatory = st.checkbox("Include local site entry permits", value=True)
        local_regulatory_permits = st.number_input("Local Permits Cost ($):", min_value=0, value=5000, step=500) if include_regulatory else 0.0
        mot_total_approval_cost = 3000.0
        include_mot_approval = True

    st.markdown("---")
    st.markdown("#### 🔄 Decommissioning & End-of-Life Financial Provision")
    st.info("📌 Future Provision (EU Benchmark 60–90 €/kWh)")
    decom_cost_per_kwh = st.number_input("Decommissioning & Recycling Cost per kWh (Benchmark 75):", min_value=0.0, value=75.0, step=5.0)

    # Calculate preview info
    preview_decom_per_bess = bess_capacity_mwh * 1000.0 * decom_cost_per_kwh
    preview_total_decom = preview_decom_per_bess * float(bess_count + oog_count)
    st.success(f"✅ **{bess_capacity_mwh} MWh** × **${decom_cost_per_kwh}/kWh** = **${preview_decom_per_bess:,.2f}** per container. Total provision for {bess_count} BESS containers: **${preview_total_decom:,.2f}**")

    st.markdown("---")
    st.markdown("#### 💰 VAT & Contingency Settings")
    vc1, vc2 = st.columns(2)
    with vc1:
        applied_vat = st.number_input("Import VAT Rate (%):", min_value=0.0, value=19.0, step=0.5)
        vat_recovery_pct = st.number_input("VAT Recovery Rate (%):", min_value=0.0, value=100.0, step=5.0)
    with vc2:
        vat_paid_by_supplier = st.checkbox("Import VAT Paid Directly by Supplier", value=False)
        contingency_pct = st.number_input("Contingency Reserve (%):", min_value=0.0, value=5.0, step=1.0)

with tab5:
    st.subheader("European Route & Corridor Analysis")
    st.warning("⚠ Indicative data only, subject to freight forwarder verification.")
    st.dataframe(corridors_df, width="stretch", hide_index=True)

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
    
    # --- RUN CALCULATION ENGINE ---
    results = calculate_project_costs(
        bess_count=bess_count, bess_exw=bess_exw,
        oog_count=oog_count, oog_exw=oog_exw,
        mvs_count=mvs_count, mvs_exw=mvs_exw,
        transformer_count=transformer_count, transformer_exw=transformer_exw,
        access_count=access_count, access_exw=access_count_exw,
        solar_count=solar_count, solar_exw=solar_exw,
        unit_freight_bess=unit_freight_bess, unit_freight_oog=unit_freight_oog, unit_freight_mvs=unit_freight_mvs,
        unit_freight_trans=unit_freight_trans, unit_freight_access=unit_freight_access, unit_freight_solar=unit_freight_solar,
        baf_bess=baf_bess, baf_oog=baf_oog, baf_mvs=baf_mvs, baf_trans=baf_trans, baf_access=baf_access, baf_solar=baf_solar,
        dthc_bess=dthc_bess, dthc_oog=dthc_oog, dthc_mvs=dthc_mvs, dthc_trans=dthc_trans, dthc_access=dthc_access, dthc_solar=dthc_solar,
        drayage_bess=drayage_bess, drayage_oog=drayage_oog, drayage_mvs=drayage_mvs,
        drayage_trans=drayage_trans, drayage_access=drayage_access, drayage_solar=drayage_solar,
        trend_multiplier=trend_multiplier, insurance_pct=insurance_pct,
        customs_duty_pct=customs_duty_pct, applied_vat=applied_vat, vat_recovery_pct=vat_recovery_pct,
        vat_paid_by_supplier=vat_paid_by_supplier, incoterm_code=incoterm_code,
        dest_country_code=dest_code,
        local_regulatory_permits=local_regulatory_permits, mot_total_approval_cost=mot_total_approval_cost,
        include_regulatory=include_regulatory, include_mot_approval=include_mot_approval,
        site_crane_unloading=site_crane_unloading, include_site_crane=include_site_crane,
        epr_recycling_total_usd=epr_recycling_total_usd * bess_count, battery_passport_total_usd=battery_passport_total_usd,
        requires_heavy_lift=True, heavy_lift_survey_cost=2500.0,
        actual_port_days=actual_port_days, free_days=free_days, demurrage_daily_rate=demurrage_daily_rate,
        use_external_storage=use_external_storage, ext_storage_days=ext_storage_days,
        ext_storage_daily_rate=ext_storage_daily_rate, include_delay_scenario=include_delay_scenario,
        bess_capacity_mwh=bess_capacity_mwh, decom_cost_per_kwh=decom_cost_per_kwh
    )

    # Convert totals to display currency (EUR or USD)
    landed_usd = results["total_landed_cost_ex_vat"]
    landed_display = convert_currency(landed_usd, "USD", curr_code, usd_to_eur)
    
    economic_usd = results["economic_cost_ex_vat"]
    economic_display = convert_currency(economic_usd, "USD", curr_code, usd_to_eur)

    cash_usd = results["total_cash_requirement_incl_vat"]
    cash_display = convert_currency(cash_usd, "USD", curr_code, usd_to_eur)

    # Carbon Footprint Estimate (approx 9.1 tons CO2 per container ocean+road)
    total_units_carbon = results["total_containers_project"]
    total_carbon_tons = total_units_carbon * 9.1

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Landed Cost (Ex. VAT)", format_currency(landed_display, curr_code))
    m2.metric("Total Economic Cost", format_currency(economic_display, curr_code))
    m3.metric("Total Cash Requirement", format_currency(cash_display, curr_code))
    m4.metric("Estimated Carbon Footprint", f"{total_carbon_tons:,.1f} t CO2")

    st.markdown("---")
    st.markdown("#### 📋 Project Budget & Carbon Footprint Breakdown")
    
    breakdown_data = [
        {"Cost Item": "Equipment EXW Value", "Basis / Qty": f"{results['total_containers_project']} Units", "Amount (USD)": results["trended_exw"]},
        {"Cost Item": "China Inland & Origin THC", "Basis / Qty": f"{results['total_containers_project']} Units", "Amount (USD)": results["china_inland_drayage"] + results["china_origin_thc"]},
        {"Cost Item": "Ocean Freight (Base)", "Basis / Qty": f"{results['total_containers_project']} Units", "Amount (USD)": results["total_base_ocean_freight"]},
        {"Cost Item": "Bunker Adjustment Factor (BAF)", "Basis / Qty": f"{results['total_containers_project']} Units", "Amount (USD)": results["total_baf_ocean"]},
        {"Cost Item": "Destination THC", "Basis / Qty": f"{results['total_containers_project']} Units", "Amount (USD)": results["destination_thc_total"]},
        {"Cost Item": "Marine Insurance", "Basis / Qty": f"{insurance_pct}% CIF", "Amount (USD)": results["insurance_total_usd"]},
        {"Cost Item": "Customs Duty", "Basis / Qty": f"{customs_duty_pct}% Rate", "Amount (USD)": results["customs_duty_usd"]},
        {"Cost Item": "Inland Drayage (Port to Site)", "Basis / Qty": f"{results['total_containers_project']} Units", "Amount (USD)": results["inland_drayage_total_usd"]},
        {"Cost Item": "Regulatory & Local Permits", "Basis / Qty": "Expense", "Amount (USD)": results["active_regulatory_permits"]},
        {"Cost Item": "Site Crane & Unloading", "Basis / Qty": "Expense", "Amount (USD)": results["active_site_crane"]},
        {"Cost Item": "Port Demurrage", "Basis / Qty": f"{max(0, actual_port_days - free_days)} Days", "Amount (USD)": results["demurrage_total_usd"]},
        {"Cost Item": "External Storage", "Basis / Qty": f"{ext_storage_days if use_external_storage else 0} Days", "Amount (USD)": results["external_storage_total_usd"]},
        {"Cost Item": "EPR / Recycling Fees", "Basis / Qty": f"{bess_count} BESS", "Amount (USD)": results["epr_recycling_total_usd"]},
        {"Cost Item": "EU Battery Passport", "Basis / Qty": "Global Compliance", "Amount (USD)": results["battery_passport_total_usd"]},
        {"Cost Item": "Heavy-Lift Survey", "Basis / Qty": "Survey", "Amount (USD)": results["active_heavy_lift"]},
        {"Cost Item": "Contingency Reserve", "Basis / Qty": f"{contingency_pct}%", "Amount (USD)": results["contingency_usd"]},
        {"Cost Item": "Decommissioning Provision", "Basis / Qty": f"{bess_capacity_mwh} MWh / unit", "Amount (USD)": results["decommissioning_total_usd"]},
        {"Cost Item": "Total Carbon Footprint", "Basis / Qty": f"{total_units_carbon} units (9.1 t/unit)", "Amount (USD)": 0.0} # Placeholder row for carbon
    ]

    breakdown_df = pd.DataFrame(breakdown_data)
    st.dataframe(breakdown_df, width="stretch", hide_index=True)

    # --- EXCEL DOWNLOAD BUTTON ---
    csv_data = breakdown_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Budget & Carbon Report to CSV/Excel",
        data=csv_data,
        file_name=f"Terra_Vol_Landed_Cost_Report_{dest_code}.csv",
        mime="text/csv",
    )

st.markdown("---")
st.caption(f"© {date.today().year} Terra Vol. Advanced Renewable Energy & Infrastructure Venture.")
