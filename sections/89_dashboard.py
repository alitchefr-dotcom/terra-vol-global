# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 89_dashboard: project control dashboard (shown as the first tab).
# Runs after all other tabs so it can summarise their results. Runs in the shared namespace of app.py.

with tab_dash:
    _G = globals()
    _today = date.today()
    _cm = usd_to_eur if is_eur_display else 1.0
    _mwh_unit = bess_capacity_mwh if bess_capacity_mwh else 0.0

    st.subheader(f"🏠 Project Dashboard — {project_name}")
    st.caption(f"{destination_country} · {sum(bom_totals.values())} units · {_bess_mwh_sum:,.1f} MWh DC · "
               f"required on site {delivery_date.strftime('%d/%m/%Y')} · today {_today.strftime('%d/%m/%Y')}")

    # ---------------- headline KPIs ----------------
    _monthly = _G.get("monthly") if _G.get("tx") else None
    _fcast = _G.get("tot_f")
    _budget_tot = _G.get("tot_b")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Landed cost (ex VAT)", format_currency(plan["landed_ex_vat"] * _cm, curr_code),
              f"{(plan['landed_ex_vat'] * _cm / project_kwh_dc):,.2f} {curr_code}/kWh" if project_kwh_dc else None,
              delta_color="off")
    k2.metric("Logistics & import", format_currency((plan["logistics_total_ex_vat"] + plan["project_level_costs"]) * _cm, curr_code),
              f"{((plan['logistics_total_ex_vat'] + plan['project_level_costs']) * _cm / project_kwh_dc):,.2f} {curr_code}/kWh"
              if project_kwh_dc else None, delta_color="off")
    k3.metric("Transport emissions", f"{_G.get('co2_total', 0.0):,.0f} t CO2e",
              f"{_G.get('co2_total', 0.0) * 1000 / project_kwh_dc:,.2f} kg/kWh" if project_kwh_dc else None, delta_color="off")
    if _monthly is not None:
        k4.metric("Peak cash requirement", format_currency(float(_monthly["Cumulative"].max()), curr_code),
                  f"in {_monthly['Cumulative'].idxmax()}", delta_color="off")
    else:
        k4.metric("Peak cash requirement", "—", "add shipment dates", delta_color="off")
    if _fcast is not None and _budget_tot:
        b1, b2, b3, _ = st.columns(4)
        b1.metric("Budget (frozen)" if st.session_state.get("_budget_baseline") else "Budget (current plan)",
                  format_currency(_budget_tot * _cm, curr_code))
        b2.metric("Forecast at completion", format_currency(_fcast * _cm, curr_code),
                  f"{(_fcast - _budget_tot) * _cm:+,.0f}", delta_color="inverse")
        b3.metric("Contingency left", format_currency((contingency_budget - max(0.0, _fcast - _budget_tot)) * _cm, curr_code))

    # ---------------- MWh by status ----------------
    st.markdown("#### Where Is the Equipment? (MWh by status)")
    _pdays = {sh["name"]: int(_num(sh.get("port_days"))) for sh in msp_shipments}
    status_rows, by_status = [], {}
    for r in plan["shipments"]:
        if not r["units"]:
            continue
        bess = r["units_by_type"].get("BESS", 0)
        mwh = bess * _mwh_unit
        etd, eta = r["etd"], r["eta"]
        on_site = (eta + timedelta(days=_pdays.get(r["name"], 0) + 2)) if eta else None
        if not etd or not eta:
            stt = "Dates not set"
        elif _today < etd:
            stt = "At factory / awaiting sailing"
        elif _today < eta:
            stt = "At sea"
        elif on_site and _today < on_site:
            stt = "In port / on the road"
        else:
            stt = "On site"
        by_status[stt] = by_status.get(stt, 0.0) + mwh
        status_rows.append({"Shipment": r["name"], "Carrier": r["carrier"], "Status": stt, "Units": r["units"],
                            "BESS": bess, "MWh": round(mwh, 1), "ETD": etd.strftime("%d/%m/%Y") if etd else "",
                            "ETA": eta.strftime("%d/%m/%Y") if eta else "",
                            "Est. on site": on_site.strftime("%d/%m/%Y") if on_site else "",
                            "Days to ETA": (eta - _today).days if eta and eta >= _today else ""})
    _alloc_bess = sum(r["units_by_type"].get("BESS", 0) for r in plan["shipments"])
    _unbooked = max(0, bom_totals.get("BESS", 0) - _alloc_bess)
    if _unbooked:
        by_status["Not booked on a vessel"] = _unbooked * _mwh_unit
    order = ["Not booked on a vessel", "Dates not set", "At factory / awaiting sailing", "At sea", "In port / on the road", "On site"]
    ms = pd.DataFrame({"MWh": [round(by_status.get(o, 0.0), 1) for o in order]}, index=order)
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        st.dataframe(ms, use_container_width=True)
    with sc2:
        st.bar_chart(ms)
    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    # ---------------- key dates ----------------
    st.markdown("#### Key Dates")
    events = [(brief_exw_ready, "EXW ready at factory"), (brief_fob_date, "Cargo at port of loading (FOB)"),
              (brief_must_sail_by, "Latest departure allowed"), (delivery_date, "Required on site")]
    for r in plan["shipments"]:
        if r["etd"]:
            events.append((r["etd"], f"ETD — {r['name']}"))
        if r["eta"]:
            events.append((r["eta"], f"ETA — {r['name']} at {r['pod'].split(',')[0]}"))
    for r in sail_results:
        if r["valid_until"] and r["eligible"]:
            events.append((r["valid_until"], f"Offer validity ends — {r['Option']} ({r['offered_by'] or r['Carrier']})"))
    _ev = sorted([e for e in events if e[0]], key=lambda x: x[0])
    _next = [e for e in _ev if e[0] >= _today][:12]
    if _next:
        st.dataframe(pd.DataFrame([{"Date": d.strftime("%d/%m/%Y"), "In (days)": (d - _today).days, "Event": t}
                                   for d, t in _next]), use_container_width=True, hide_index=True)

    # ---------------- alerts ----------------
    st.markdown("#### Open Alerts")
    alerts = []   # (level, area, text)
    if not plan["coverage_ok"]:
        alerts.append(("🔴", "Allocation", "Not all BOM equipment is on a shipment (Multi-Shipment Planner)."))
    for p_ in (_G.get("problems") or []):
        alerts.append(("🔴", "Allocation plan", p_))
    for w_ in (_G.get("warnings_") or []):
        alerts.append(("🟠", "Allocation plan", w_))
    for l_ in (_G.get("late_shipments") or []):
        alerts.append(("🔴", "Schedule", f"Arrives after the required-on-site date: {l_}"))
    if is_israel and not _G.get("has_toxins_permit", True):
        alerts.append(("🔴", "Permits", f"Toxins Permit missing for the {_G.get('toxins_missing_text', '')}."))
    for d_ in (_G.get("dash") or []):
        if str(d_.get("Status", "")).startswith("🔴"):
            alerts.append(("🔴", "Transport permits", f"{d_['Vessel']}: {d_['Status']}"))
        elif str(d_.get("Status", "")).startswith("🟠"):
            alerts.append(("🟠", "Transport permits", f"{d_['Vessel']}: start the permit requests now"))
    for x_ in (_G.get("_lib_expiring") or []):
        alerts.append(("🔴", "Documents", f"Expired / expiring: {x_}"))
    if _G.get("_lib_missing"):
        alerts.append(("🟠", "Documents", f"{len(_G['_lib_missing'])} fixed document(s) not yet collected."))
    for b in bom_rows:
        if "DG classification not final" in b["Checks"]:
            alerts.append(("🟠", "Cargo", f"{b['Item']}: UN number not confirmed."))
    for r in sail_results:
        if r["eligible"] and r["valid_until"] and 0 <= (r["valid_until"] - _today).days <= 7:
            alerts.append(("🟠", "Offers", f"Offer {r['Option']} expires on {r['valid_until'].strftime('%d/%m/%Y')}."))
    if _fcast is not None and _budget_tot and (_fcast - _budget_tot) > contingency_budget:
        alerts.append(("🔴", "Budget", "Forecast overrun exceeds the contingency reserve."))
    if _G.get("_open") is not None and len(_G["_open"]):
        alerts.append(("🟠", "Compliance", f"{len(_G['_open'])} regulatory checklist item(s) open."))
    alerts.sort(key=lambda a: a[0] != "🔴")
    if alerts:
        st.dataframe(pd.DataFrame([{"": a[0], "Area": a[1], "Alert": a[2]} for a in alerts]),
                     use_container_width=True, hide_index=True)
    else:
        st.success("No open alerts.")
