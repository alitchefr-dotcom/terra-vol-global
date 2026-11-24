# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 10_project_brief: Tab: Project Brief & BOM.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
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

    # ---------------- Cost of delay ----------------
    with st.expander("⏱️ Cost of Delay — what each day after the Required-on-Site date costs", expanded=False):
        st.caption("Used to compare offers on total cost (freight + delay), not only on freight. Enter daily amounts "
                   f"in {curr_code}; leave 0 what does not apply. Example: 100 MW earning 100,000 per MW per year "
                   "≈ 27,400 per day of lost revenue.")
        cd1, cd2, cd3, cd4 = st.columns(4)
        with cd1:
            cod_revenue = ui.number_input(f"Lost revenue per day ({curr_code}):", min_value=0.0, value=0.0, step=1000.0,
                                          help="Revenue the project does not earn while it is not in operation")
        with cd2:
            cod_penalty = ui.number_input(f"Grid / PPA / offtake penalties per day ({curr_code}):", min_value=0.0,
                                          value=0.0, step=1000.0)
        with cd3:
            cod_overhead = ui.number_input(f"Financing & site overhead per day ({curr_code}):", min_value=0.0,
                                           value=0.0, step=500.0,
                                           help="Construction interest, site team, crane and equipment standing time")
        with cd4:
            cod_lds = ui.number_input(f"Supplier delay damages received per day ({curr_code}):", min_value=0.0,
                                      value=0.0, step=500.0,
                                      help="Liquidated damages the supplier pays if its delay causes the late arrival "
                                           "(reduces the cost only when the supplier is responsible)")
        cdx1, cdx2 = st.columns(2)
        with cdx1:
            cod_days_after_eta = ui.number_input("Days from vessel arrival to equipment on site:", min_value=0, value=7,
                                                 step=1, help="Port clearance, permits and inland haul")
        with cdx2:
            cod_lds_apply = ui.checkbox("Count supplier delay damages (delay caused by the supplier)", value=False)
    _cod_to_usd = (1.0 / usd_to_eur) if is_eur_display else 1.0
    delay_cost_per_day_usd = max(0.0, cod_revenue + cod_penalty + cod_overhead - (cod_lds if cod_lds_apply else 0.0)) * _cod_to_usd

    def delay_days(on_site):
        """Days after the Required-on-Site date (0 when on time or no date)."""
        return max(0, (on_site - delivery_date).days) if (on_site and delivery_date) else 0

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
    _blank_if_new("bom_df")
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
