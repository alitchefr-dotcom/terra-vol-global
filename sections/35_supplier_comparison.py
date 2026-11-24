# Terra Vol Global — section 35_supplier_comparison: Tab: Supplier Comparison (delivered-to-site cost per kWh).
# Runs in the shared namespace of app.py, in file-name order (see app.py).

with tab_supp:
    st.subheader("🏭 Supplier Comparison — Delivered-to-Site Cost per kWh")
    st.markdown("Compare BESS equipment suppliers on the **same project, route and rates**. The FOB price per kWh "
                "hides differences in unit count, box weight and size, auxiliary equipment (MVS / PCS) and payment "
                "terms — this table shows the cost per kWh once the equipment is on site.")
    _cm = usd_to_eur if is_eur_display else 1.0
    _to_usd = (1.0 / usd_to_eur) if is_eur_display else 1.0

    # ---------------- project & shared rates ----------------
    st.markdown("#### 1. Project & Shared Rates")
    sp1, sp2, sp3 = st.columns(3)
    with sp1:
        sup_target_mwh = ui.number_input("Required energy (MWh DC nameplate):", min_value=0.0,
                                         value=float(round(_bess_mwh_sum, 1)) if _bess_mwh_sum else 100.0, step=10.0)
        sup_routing = ui.selectbox("Routing (for CO2):", ["Cape of Good Hope", "Suez Canal / Red Sea"],
                                   index=0 if req_no_red_sea else 1)
    with sp2:
        _c20 = [r for _, r in sail_edit.iterrows() if r.get("Vessel Type") == "Container vessel"
                and _num(r.get("Freight / 20ft")) > 0]
        _c40 = [r for _, r in sail_edit.iterrows() if r.get("Vessel Type") == "Container vessel"
                and _num(r.get("Freight / 40ft")) > 0]
        _med = lambda xs: float(pd.Series(xs).median()) if xs else None
        _d20 = _med([_num(r["Freight / 20ft"]) * _fx_usd(r) for r in _c20]) or unit_freight_bess
        _d40 = _med([_num(r["Freight / 40ft"]) * _fx_usd(r) for r in _c40]) or unit_freight_bess * 1.5
        sup_f20 = ui.number_input(f"Ocean freight per 20ft ({curr_code}):", min_value=0.0, value=round(_d20 * _cm), step=500.0,
                                  help="Default: median of the container offers received, otherwise the Supply Chain tab")
        sup_f40 = ui.number_input(f"Ocean freight per 40ft / 40HC ({curr_code}):", min_value=0.0, value=round(_d40 * _cm),
                                  step=500.0)
        sup_mpp = ui.number_input(f"MPP / breakbulk freight per unit ({curr_code}):", min_value=0.0,
                                  value=round(20000 * _cm), step=1000.0)
    with sp3:
        sup_overweight = ui.number_input(f"Heavy-box surcharge per box > 30.48 t ({curr_code}):", min_value=0.0,
                                         value=round(800 * _cm), step=100.0)
        sup_abnormal = ui.number_input(f"Abnormal road load surcharge per unit ({curr_code}):", min_value=0.0,
                                       value=round(1500 * _cm), step=250.0,
                                       help="Escort, special trailer and permit, on top of normal trucking")
        sup_trucking = ui.number_input(f"Port-to-site trucking + destination THC per unit ({curr_code}):", min_value=0.0,
                                       value=round((dray_bess * _to_usd + dthc_bess * _to_usd) * _cm), step=250.0)
    _m_ship = max(1.0, (delivery_date - brief_fob_date).days / 30.4) if (delivery_date and brief_fob_date) else 2.0
    st.caption(f"Also used from the project: BAF {format_currency(baf_per_teu_usd * _cm, curr_code)}/TEU, insurance "
               f"{insurance_pct:g}%, duty {customs_duty_pct:g}% (BESS) / {mvs_customs_duty_pct:g}% (MVS), import VAT "
               f"{applied_vat:g}% with {vat_recovery_pct:g}% recovered, financing {fin_rate:g}%/yr, FOB → site "
               f"{_m_ship:.1f} months (from the Project Brief dates).")

    # ---------------- suppliers ----------------
    st.markdown("#### 2. Supplier Offers")
    _SUP_COLS = ["Supplier", "Model", "MWh / Unit", "Price / Unit (USD)", "Basis", "Weight / Unit (t)", "Container",
                 "Aux Units per BESS", "Aux Price / Unit (USD)", "Aux Weight (t)", "Aux Container",
                 "Advance (%)", "Before Shipment (%)", "Lead Time (weeks)", "EXW Ready", "Warranty (years)", "Notes"]
    if "sup_df" not in st.session_state:
        st.session_state.sup_df = pd.DataFrame([
            {"Supplier": "Supplier A", "Model": "5 MWh 20ft", "MWh / Unit": 5.016, "Price / Unit (USD)": 430000.0,
             "Basis": "FOB", "Weight / Unit (t)": 42.5, "Container": "20ft", "Aux Units per BESS": 0.2,
             "Aux Price / Unit (USD)": 120000.0, "Aux Weight (t)": 18.0, "Aux Container": "20ft",
             "Advance (%)": 30.0, "Before Shipment (%)": 60.0, "Lead Time (weeks)": 16.0, "EXW Ready": None,
             "Warranty (years)": 10.0, "Notes": ""},
            {"Supplier": "Supplier B", "Model": "3.44 MWh 20ft", "MWh / Unit": 3.44, "Price / Unit (USD)": 290000.0,
             "Basis": "FOB", "Weight / Unit (t)": 27.0, "Container": "20ft", "Aux Units per BESS": 0.25,
             "Aux Price / Unit (USD)": 110000.0, "Aux Weight (t)": 16.0, "Aux Container": "20ft",
             "Advance (%)": 10.0, "Before Shipment (%)": 90.0, "Lead Time (weeks)": 12.0, "EXW Ready": None,
             "Warranty (years)": 10.0, "Notes": ""},
            {"Supplier": "Supplier C", "Model": "6.25 MWh 40ft", "MWh / Unit": 6.25, "Price / Unit (USD)": 520000.0,
             "Basis": "EXW", "Weight / Unit (t)": 48.0, "Container": "40ft HC", "Aux Units per BESS": 0.0,
             "Aux Price / Unit (USD)": 0.0, "Aux Weight (t)": 0.0, "Aux Container": "20ft",
             "Advance (%)": 30.0, "Before Shipment (%)": 70.0, "Lead Time (weeks)": 20.0, "EXW Ready": None,
             "Warranty (years)": 15.0, "Notes": "PCS integrated"},
        ])
    for _c in _SUP_COLS:
        if _c not in st.session_state.sup_df.columns:
            st.session_state.sup_df[_c] = None
    st.session_state.sup_df["EXW Ready"] = pd.to_datetime(st.session_state.sup_df["EXW Ready"], errors="coerce").dt.date
    sup_edit = st.data_editor(
        st.session_state.sup_df[_SUP_COLS], num_rows="dynamic", use_container_width=True, key="sup_editor",
        column_config={
            "MWh / Unit": st.column_config.NumberColumn("MWh / Unit", min_value=0.0, step=0.01, format="%.3f",
                                                        help="DC nameplate energy per BESS unit"),
            "Price / Unit (USD)": st.column_config.NumberColumn("Price / Unit (USD)", min_value=0.0, step=1000.0, format="%.0f"),
            "Basis": st.column_config.SelectboxColumn("Basis", options=["FOB", "EXW"], required=True,
                                                      help="EXW adds factory trucking and origin THC from the Supply Chain tab"),
            "Container": st.column_config.SelectboxColumn("Container", options=CONTAINER_SIZES, required=True),
            "Aux Container": st.column_config.SelectboxColumn("Aux Container", options=CONTAINER_SIZES),
            "Aux Units per BESS": st.column_config.NumberColumn("Aux Units per BESS", min_value=0.0, step=0.05, format="%.2f",
                                                                help="MVS / PCS skids per BESS unit, e.g. 0.25 = 1 per 4"),
            "Aux Price / Unit (USD)": st.column_config.NumberColumn("Aux Price / Unit (USD)", min_value=0.0, step=1000.0, format="%.0f"),
            "Advance (%)": st.column_config.NumberColumn("Advance (%)", min_value=0.0, max_value=100.0, step=5.0),
            "Before Shipment (%)": st.column_config.NumberColumn("Before Shipment (%)", min_value=0.0, max_value=100.0, step=5.0),
            "EXW Ready": st.column_config.DateColumn("EXW Ready", format="DD/MM/YYYY"),
        })
    st.session_state.sup_df = sup_edit

    sup_rates = {
        "origin_truck": origin_truck_usd, "origin_thc": origin_thc_usd,
        "freight_20": sup_f20 * _to_usd, "freight_40": sup_f40 * _to_usd, "mpp_per_unit": sup_mpp * _to_usd,
        "baf_per_teu": baf_per_teu_usd, "overweight_surcharge": sup_overweight * _to_usd,
        "insurance_pct": insurance_pct, "duty_bess_pct": customs_duty_pct, "duty_aux_pct": mvs_customs_duty_pct,
        "dthc": 0.0, "trucking": sup_trucking * _to_usd, "abnormal_surcharge": sup_abnormal * _to_usd,
        "months_ship_to_site": _m_ship, "fin_rate_pct": fin_rate,
        "vat_pct": applied_vat, "vat_recovery_pct": vat_recovery_pct,
    }
    _pod_xy = PORT_COORDS.get(dest_port)
    _sea_km = _carbon_mod.sea_km(origin_port, dest_port, _pod_xy, sup_routing)
    _road = road_km(site_latlon, _pod_xy) if (site_latlon and _pod_xy) else 0.0

    sup_results = []
    for _, s in sup_edit.iterrows():
        if not str(s.get("Supplier") or "").strip():
            continue
        r = _sup_mod.cost_supplier({
            "mwh_per_unit": s.get("MWh / Unit"), "price_per_unit": s.get("Price / Unit (USD)"), "basis": s.get("Basis"),
            "weight_t": s.get("Weight / Unit (t)"), "container": s.get("Container"),
            "aux_per_bess": s.get("Aux Units per BESS"), "aux_price": s.get("Aux Price / Unit (USD)"),
            "aux_weight_t": s.get("Aux Weight (t)"), "aux_container": s.get("Aux Container"),
            "adv_pct": s.get("Advance (%)"), "pre_pct": s.get("Before Shipment (%)"), "lead_weeks": s.get("Lead Time (weeks)"),
        }, sup_target_mwh, sup_rates)
        if r is None:
            continue
        _kind = "mpp" if s.get("Container") == "MPP / Breakbulk" else "container"
        r["co2"] = _carbon_mod.shipment_emissions(_sea_km, _kind, r["teu"], r["tonnes"], _road, factory_km,
                                                  carbon_factors, co2_basis)["total_t"]
        _ready = s.get("EXW Ready")
        if _ready and not pd.isna(_ready) and brief_must_sail_by and _ready > brief_must_sail_by:
            r["flags"].append(f"EXW ready {_ready.strftime('%d/%m/%Y')} is after the latest departure date")
        r["name"] = f"{s.get('Supplier')} — {s.get('Model') or ''}".strip(" —")
        r["warranty"] = s.get("Warranty (years)")
        sup_results.append(r)

    # ---------------- results ----------------
    st.markdown("#### 3. Delivered-to-Site Comparison")
    if not sup_results:
        st.info("Enter at least one supplier with MWh / Unit and a price.")
    else:
        best = min(sup_results, key=lambda r: r["site_per_kwh"])
        best_fob = min(sup_results, key=lambda r: r["fob_per_kwh"])
        sup_rows = []
        for r in sorted(sup_results, key=lambda r: r["site_per_kwh"]):
            sup_rows.append({
                "Supplier": r["name"], "BESS units": r["units"], "Aux units": r["aux"],
                "Installed MWh": round(r["installed_mwh"], 1), "Boxes TEU": round(r["teu"], 1),
                "Cargo (t)": round(r["tonnes"]),
                f"Equipment FOB / kWh ({curr_code})": round(r["fob_per_kwh"] * _cm, 2),
                f"Logistics & import / kWh ({curr_code})": round(r["logistics_per_kwh"] * _cm, 2),
                f"Financing / kWh ({curr_code})": round(r["financing"] / (r["installed_mwh"] * 1000) * _cm, 2),
                f"On site / kWh ({curr_code})": round(r["site_per_kwh"] * _cm, 2),
                f"Project total ({curr_code})": round(r["total"] * _cm),
                "Uplift over FOB (%)": round(r["uplift_pct"], 1),
                "CO2e (t)": round(r["co2"], 1),
                "vs best on site": f"{(r['site_per_kwh'] / best['site_per_kwh'] - 1) * 100:+.1f}%" if r is not best else "best",
                "Flags": " · ".join(r["flags"]),
            })
        sup_df_out = pd.DataFrame(sup_rows)
        st.dataframe(sup_df_out, use_container_width=True, hide_index=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("Lowest on-site cost", best["name"], f"{format_currency(best['site_per_kwh'] * _cm, curr_code)}/kWh",
                  delta_color="off")
        m2.metric("Lowest FOB price", best_fob["name"], f"{format_currency(best_fob['fob_per_kwh'] * _cm, curr_code)}/kWh",
                  delta_color="off")
        if best_fob is not best:
            m3.metric("Ranking changes after delivery", "Yes",
                      f"{best_fob['name']} costs {format_currency((best_fob['total'] - best['total']) * _cm, curr_code)} more on site",
                      delta_color="off")
        else:
            m3.metric("Ranking changes after delivery", "No", delta_color="off")
        st.caption("Per kWh = per installed kWh DC nameplate. Financing = carrying cost of the advance and the "
                   "pre-shipment payment until the equipment is on site; non-recoverable import VAT is included. "
                   "Equipment prices are taken as quoted — check scope (PCS, EMS, transformers, spares, "
                   "commissioning) is the same before comparing.")

        bd = pd.DataFrame({r["name"]: {"Equipment": r["equipment"] * _cm / (r["installed_mwh"] * 1000),
                                       "Logistics & import": r["logistics"] * _cm / (r["installed_mwh"] * 1000),
                                       "Financing & VAT": (r["financing"] + r["vat_cost"]) * _cm / (r["installed_mwh"] * 1000)}
                           for r in sup_results}).T
        st.markdown(f"##### Cost per kWh by component ({curr_code})")
        st.bar_chart(bd)

        _buf = io.BytesIO()
        with pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
            sup_df_out.to_excel(_xw, sheet_name="Comparison", index=False)
            sup_edit.to_excel(_xw, sheet_name="Supplier inputs", index=False)
            pd.DataFrame([{"Item": k, "Value": v} for k, v in {
                "Project": project_name, "Destination": f"{dest_port}, {destination_country}",
                "Required MWh DC": sup_target_mwh, "Currency": curr_code, "Routing": sup_routing,
                "Freight / 20ft": sup_f20, "Freight / 40ft": sup_f40, "MPP / unit": sup_mpp,
                "Heavy-box surcharge": sup_overweight, "Abnormal-load surcharge": sup_abnormal,
                "Trucking + DTHC / unit": sup_trucking, "Insurance %": insurance_pct,
                "Duty BESS %": customs_duty_pct, "Duty MVS %": mvs_customs_duty_pct, "VAT %": applied_vat,
                "VAT recovered %": vat_recovery_pct, "Financing %/yr": fin_rate,
                "FOB to site (months)": round(_m_ship, 1)}.items()]).to_excel(_xw, sheet_name="Assumptions", index=False)
            for _ws in _xw.book.worksheets:
                for _col in _ws.columns:
                    _ws.column_dimensions[_col[0].column_letter].width = min(48, max(10, max(len(str(c.value or "")) for c in _col) + 2))
        st.download_button("⬇️ Download supplier comparison (Excel)", _buf.getvalue(),
                           file_name=f"{project_name.replace(' ', '_')}_supplier_comparison.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
