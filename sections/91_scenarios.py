# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 91_scenarios: Tab: Scenarios.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# ---------------------------------------------------------------------------
# SCENARIOS — snapshots of the whole project, compared side by side
# ---------------------------------------------------------------------------
def _current_kpis():
    """Key results of the project as it is now (all amounts USD)."""
    G = globals()
    ships = [r for r in plan["shipments"]]
    _pdays = {sh["name"]: int(_num(sh.get("port_days"))) for sh in msp_shipments}
    on_site = [r["eta"] + timedelta(days=_pdays.get(r["name"], 0) + 2) for r in ships if r["eta"]]
    kwh = project_kwh_dc or 0
    _monthly = G.get("monthly") if G.get("tx") else None
    _m = usd_to_eur if is_eur_display else 1.0
    return {
        "Destination": destination_country,
        "Vessels / shipments": len(ships),
        "Carriers": ", ".join(sorted({str(r["carrier"]) for r in ships if r["carrier"]})),
        "Units on vessels": sum(r["units"] for r in ships),
        "All equipment allocated": "Yes" if plan["coverage_ok"] else "No",
        "Logistics & import cost (USD)": round(plan["logistics_total_ex_vat"] + plan["project_level_costs"]),
        "Landed cost ex VAT (USD)": round(plan["landed_ex_vat"]),
        "Cash incl. VAT (USD)": round(plan["cash_incl_vat"]),
        "Landed cost per kWh (USD)": round(plan["landed_ex_vat"] / kwh, 2) if kwh else None,
        "Last on site": max(on_site).isoformat() if on_site else None,
        "Days vs required date": ((delivery_date - max(on_site)).days if on_site else None),
        "Cost of delay (USD)": round(G.get("project_delay_cost_usd", 0.0) or 0.0),
        "Logistics + delay (USD)": round(plan["logistics_total_ex_vat"] + plan["project_level_costs"]
                                         + (G.get("project_delay_cost_usd", 0.0) or 0.0)),
        "Payment terms": G.get("pay_preset", ""),
        "Peak cash (USD)": round(float(_monthly["Cumulative"].max()) / _m) if _monthly is not None else None,
        "Peak cash month": str(_monthly["Cumulative"].idxmax()) if _monthly is not None else None,
        "L/C fees (USD)": round(G.get("lc_fee_total", 0.0) + (G.get("lc_fixed", 0.0) if G.get("pay_kind") == "LC" else 0.0)),
        "Import VAT financing (USD)": round((G.get("vat_cost", 0.0) or 0.0) / _m),
        "Transport CO2e (t)": round(G.get("co2_total", 0.0) or 0.0, 1),
    }


with tab_scen:
    st.subheader("🔀 Scenarios — Compare Alternatives Side by Side")
    st.markdown("Save the project as it is now as a **scenario** (e.g. *2 container vessels, T/T*), change the plan, terms or "
                "offers, save again (e.g. *1 charter, L/C 90 days*) and compare. Each scenario is a full snapshot and can be "
                "reloaded. Scenarios are saved in the project file.")
    scen = st.session_state.setdefault("_scenarios", [])
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        _scn_name = st.text_input("Scenario name:", value=f"Scenario {len(scen) + 1}", key=f"scn_name_{len(scen)}")
    with sc2:
        st.markdown("&nbsp;")
        if st.button("💾 Save current as scenario"):
            _snap = json.loads(json.dumps(_project_file, ensure_ascii=False, default=str))
            _snap.pop("scenarios", None)
            scen.append({"name": _scn_name.strip() or f"Scenario {len(scen) + 1}", "saved_at": date.today().isoformat(),
                         "kpis": _current_kpis(), "data": _snap})
            st.success(f"Saved '{scen[-1]['name']}'.")

    if not scen:
        st.info("No scenarios yet — save the current project as the first scenario.")
    else:
        _m = usd_to_eur if is_eur_display else 1.0
        _sym = "€" if is_eur_display else "$"
        money_keys = [k for k in scen[0]["kpis"] if k.endswith("(USD)")]
        lower_better = set(money_keys)
        table = {}
        for k in scen[0]["kpis"]:
            label = k.replace("(USD)", f"({curr_code})")
            row = {}
            for sc_ in scen:
                v = sc_["kpis"].get(k)
                if k in money_keys and isinstance(v, (int, float)):
                    v = f"{_sym} {v * _m:,.2f}" if "per kWh" in k else f"{_sym} {v * _m:,.0f}"
                row[sc_["name"]] = v if v is not None else "—"
            table[label] = row
        cmp_df = pd.DataFrame(table).T
        # best value per money metric
        best = {}
        for k in money_keys:
            vals = [(sc_["name"], sc_["kpis"].get(k)) for sc_ in scen if isinstance(sc_["kpis"].get(k), (int, float))]
            vals = [v for v in vals if v[1] > 0 or "fees" not in k]
            if len(vals) > 1:
                best[k.replace("(USD)", f"({curr_code})")] = min(vals, key=lambda x: x[1])[0]
        cmp_df["Best"] = [best.get(i, "") for i in cmp_df.index]
        st.dataframe(cmp_df, use_container_width=True)

        if len(scen) > 1:
            base = scen[0]
            st.markdown(f"**Difference vs. '{base['name']}'** (positive = more expensive / later)")
            diff_rows = []
            for sc_ in scen[1:]:
                d = {"Scenario": sc_["name"]}
                for k in ["Landed cost ex VAT (USD)", "Logistics & import cost (USD)", "Peak cash (USD)"]:
                    a, b = base["kpis"].get(k), sc_["kpis"].get(k)
                    d[k.replace("(USD)", f"({curr_code})")] = f"{_sym} {(b - a) * _m:+,.0f}" if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "—"
                a, b = base["kpis"].get("Last on site"), sc_["kpis"].get("Last on site")
                d["Last on site (days)"] = (date.fromisoformat(b) - date.fromisoformat(a)).days if a and b else "—"
                diff_rows.append(d)
            st.dataframe(pd.DataFrame(diff_rows), use_container_width=True, hide_index=True)
            _chart = pd.DataFrame({sc_["name"]: {"Landed cost ex VAT": (sc_["kpis"].get("Landed cost ex VAT (USD)") or 0) * _m,
                                                 "Peak cash": (sc_["kpis"].get("Peak cash (USD)") or 0) * _m}
                                   for sc_ in scen}).T
            st.bar_chart(_chart)

        a1, a2, a3 = st.columns([2, 1, 1])
        with a1:
            _pick = st.selectbox("Scenario:", [sc_["name"] for sc_ in scen], key="scn_pick")
        with a2:
            st.markdown("&nbsp;")
            if st.button("↩️ Load this scenario"):
                _sel = next(sc_ for sc_ in scen if sc_["name"] == _pick)
                _apply_project_data(_sel["data"])
                st.session_state["_loaded_project_name"] = f"scenario '{_pick}'"
                st.rerun()
        with a3:
            st.markdown("&nbsp;")
            if st.button("🗑️ Delete this scenario"):
                st.session_state["_scenarios"] = [sc_ for sc_ in scen if sc_["name"] != _pick]
                st.rerun()

        _out = io.BytesIO()
        with pd.ExcelWriter(_out, engine="openpyxl") as _w:
            cmp_df.to_excel(_w, sheet_name="Scenarios")
        st.download_button("⬇️ Download scenario comparison (Excel)", data=_out.getvalue(),
                           file_name=f"Scenarios_{_re.sub(r'[^A-Za-z0-9]+', '_', project_name)}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.caption("Scenario results are stored when the scenario is saved. Load a scenario and save it again to refresh "
                   "its results after changing offers or rates.")

_project_file["scenarios"] = st.session_state.get("_scenarios", [])
