# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 23_regulation: Tab: Regulation & Approvals.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
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
