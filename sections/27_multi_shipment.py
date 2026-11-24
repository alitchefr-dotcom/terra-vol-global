# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 27_multi_shipment: Tab: Multi-Shipment Planner.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
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
             "Daily Rate / Unit after Free Days": 100.0, "Extra Lump Sum": 0.0, "Routing": "Cape of Good Hope"},
            {"Shipment": "Shipment 2", "Carrier": "MPP Operator", "Service": "MPP Vessel",
             "Origin Port": "Shanghai", "POD": POD_OPTIONS[0],
             "ETD": date(2027, 4, 1), "ETA": date(2027, 5, 10), "Currency": "USD",
             "Origin Charges / Unit": 350.0, "Port Days": 4, "Free Days": 3,
             "Daily Rate / Unit after Free Days": 100.0, "Extra Lump Sum": 5000.0, "Routing": "Cape of Good Hope"},
            {"Shipment": "Shipment 3", "Carrier": "MSC", "Service": "Container Line - COC",
             "Origin Port": "Ningbo-Zhoushan", "POD": POD_OPTIONS[0],
             "ETD": date(2027, 3, 15), "ETA": date(2027, 4, 20), "Currency": "USD",
             "Origin Charges / Unit": 350.0, "Port Days": 6, "Free Days": 5,
             "Daily Rate / Unit after Free Days": 150.0, "Extra Lump Sum": 0.0, "Routing": "Cape of Good Hope"},
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
                                 "Daily Rate / Unit after Free Days": 100.0, "Extra Lump Sum": 0.0,
                                 "Routing": sr.get("Routing") if sr.get("Routing") in ROUTINGS else "Cape of Good Hope"})
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

    _blank_if_new("msp_shipments")
    _blank_if_new("msp_lines")
    if "Routing" not in st.session_state.msp_shipments.columns:
        st.session_state.msp_shipments["Routing"] = "Suez Canal / Red Sea" if not req_no_red_sea else "Cape of Good Hope"
        st.session_state.pop("msp_shipments_editor", None)
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
            "Routing": st.column_config.SelectboxColumn("Routing", options=ROUTINGS, required=True,
                                                        help="Used for the route-based carbon footprint"),
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
            "routing": row.get("Routing") if row.get("Routing") in ROUTINGS else "Cape of Good Hope",
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
    _on_sites = [r["eta"] + timedelta(days=_port_days_by_name.get(r["name"], 0) + 2) for r in plan["shipments"]
                 if r["eta"] and r["units"]]
    project_days_late = delay_days(max(_on_sites)) if _on_sites else 0
    project_delay_cost_usd = project_days_late * delay_cost_per_day_usd
    if late_shipments:
        if delay_cost_per_day_usd > 0:
            st.metric("Cost of delay (project complete on site after the required date — not in the landed cost)",
                      _fmt(project_delay_cost_usd), f"{project_days_late} days × {_fmt(delay_cost_per_day_usd)}/day",
                      delta_color="off")
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
    # ---------------- Route-based carbon footprint (GLEC) ----------------
    st.markdown("#### Carbon Footprint by Route (GLEC Framework, well-to-wheel)")
    with st.expander("Emission factors & assumptions"):
        ef1, ef2, ef3, ef4 = st.columns(4)
        with ef1:
            ef_container = ui.number_input("Container vessel (kg CO2e / TEU-km):", min_value=0.0,
                                           value=_carbon_mod.GLEC_FACTORS["container_teu_km"], step=0.001, format="%.4f")
        with ef2:
            ef_mpp = ui.number_input("MPP / general cargo (kg CO2e / t-km):", min_value=0.0,
                                     value=_carbon_mod.GLEC_FACTORS["mpp_t_km"], step=0.001, format="%.4f")
        with ef3:
            ef_truck = ui.number_input("Truck, container (kg CO2e / t-km):", min_value=0.0,
                                       value=_carbon_mod.GLEC_FACTORS["truck_t_km"], step=0.001, format="%.3f")
        with ef4:
            factory_km = ui.number_input("Factory → port of loading (km):", min_value=0, value=400, step=50)
        co2_basis_lbl = ui.selectbox("Container vessel allocation:", ["Per TEU (GLEC default)",
                                                                     "Per tonne (10 t per TEU) — heavier boxes count more"])
        co2_basis = "mass" if co2_basis_lbl.startswith("Per tonne") else "teu"
        st.caption(verified_note("glec"))
        st.caption("Defaults: GLEC v3.1 container vessel (other global) 0.0883 kg/TEU-km; GLEC v3.0 general cargo "
                   "10–20 kdwt VLSFO 0.0192 kg/t-km; GLEC v3.2 articulated truck 34–40 t container 0.101 kg/t-km "
                   "(TTW 0.078 + WTT 0.023). Sea distance estimated along the route (±5–10%); road distance from the "
                   "site GPS (straight line × 1.3). Container vessels are counted per TEU (GLEC method).")
    carbon_factors = {"container_teu_km": ef_container, "mpp_t_km": ef_mpp, "truck_t_km": ef_truck}
    _w_by_type, _teu_by_type = {}, {}
    _q_by_type = {}
    for b in bom_rows:
        q = max(1, b["Qty"])
        _w_by_type[b["Type"]] = _w_by_type.get(b["Type"], 0.0) + q * b["Weight / Unit (t)"]
        _teu_by_type[b["Type"]] = _teu_by_type.get(b["Type"], 0.0) + q * teu_factor(b["Container"], 1.0)
        _q_by_type[b["Type"]] = _q_by_type.get(b["Type"], 0) + q
    _w_by_type = {t: v / _q_by_type[t] for t, v in _w_by_type.items()}
    _teu_by_type = {t: v / _q_by_type[t] for t, v in _teu_by_type.items()}
    _ship_meta = {sh["name"]: sh for sh in msp_shipments}

    def shipment_co2(r, routing=None):
        sh = _ship_meta.get(r["name"], {})
        pod = sh.get("pod") or ""
        pod_xy = PORT_COORDS.get(pod)
        rt = routing or sh.get("routing") or "Cape of Good Hope"
        sea = _carbon_mod.sea_km(sh.get("origin") or "Shanghai", pod, pod_xy, rt)
        tonnes = sum(q * _w_by_type.get(t, 20.0) for t, q in r["units_by_type"].items())
        teu = sum(q * _teu_by_type.get(t, 1.0) for t, q in r["units_by_type"].items())
        road = road_km(site_latlon, pod_xy) if (site_latlon and pod_xy) else 0.0
        kind = "container" if str(sh.get("service", "")).startswith("Container") else "mpp"
        e = _carbon_mod.shipment_emissions(sea, kind, teu, tonnes, road, factory_km, carbon_factors, co2_basis)
        e.update({"sea_km": sea or 0.0, "road_km": road, "tonnes": tonnes, "teu": teu, "routing": rt})
        return e

    co2_rows, co2_total, co2_alt_total = [], 0.0, 0.0
    for r in plan["shipments"]:
        if not r["units"]:
            continue
        e = shipment_co2(r)
        alt_rt = "Suez Canal / Red Sea" if e["routing"] == "Cape of Good Hope" else "Cape of Good Hope"
        e_alt = shipment_co2(r, alt_rt)
        co2_total += e["total_t"]
        co2_alt_total += e_alt["total_t"]
        co2_rows.append({"Shipment": r["name"], "Routing": e["routing"], "Sea (km)": round(e["sea_km"]),
                         "Road (km)": round(e["road_km"] + factory_km), "Cargo (t)": round(e["tonnes"], 1),
                         "TEU": round(e["teu"], 1), "Sea t CO2e": round(e["sea_t"], 1), "Road t CO2e": round(e["road_t"], 1),
                         "Total t CO2e": round(e["total_t"], 1),
                         f"If {alt_rt.split(' /')[0].replace(' of Good Hope', '')} (t)": round(e_alt["total_t"], 1)})
    if co2_rows:
        st.dataframe(pd.DataFrame(co2_rows), use_container_width=True, hide_index=True)
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Transport emissions", f"{co2_total:,.1f} t CO2e")
        cc2.metric("Per MWh (DC)", f"{co2_total / (project_kwh_dc / 1000):,.2f} t CO2e" if project_kwh_dc else "—")
        cc3.metric("Other routing for all shipments", f"{co2_alt_total:,.1f} t CO2e",
                   f"{co2_alt_total - co2_total:+,.1f} t", delta_color="inverse")
    else:
        co2_total = 0.0

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
