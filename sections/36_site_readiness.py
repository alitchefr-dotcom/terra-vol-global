# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 36_site_readiness: Tab: Site Readiness & Interim Storage.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
import math as _math

with tab_site:
    st.subheader("🏗️ Site Readiness & Interim Storage")
    st.markdown("When the site cannot receive the equipment on arrival (site works, heavy-load access, rainy season, "
                "permits), the units must wait somewhere. This tab compares **holding at the factory, keeping them in "
                "the port, an interim storage yard or a temporary pad on site** for every shipment.")
    _cm = usd_to_eur if is_eur_display else 1.0
    _to_usd = (1.0 / usd_to_eur) if is_eur_display else 1.0
    _MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # ---------------- 1. site ----------------
    st.markdown("#### 1. Site Readiness")
    sr1, sr2, sr3 = st.columns(3)
    with sr1:
        site_ready_date = ui.date_input("Site ready to receive equipment (expected):", value=delivery_date,
                                        help="Date the site can take the first unit: access road, foundations / pads, "
                                             "crane. Can be later than the Required-on-Site date.")
    with sr2:
        site_no_go = ui.multiselect("Months heavy trucks cannot reach the site:", _MONTHS, default=[],
                                    help="E.g. rainy season on unpaved access. Deliveries move to the next allowed month.")
    with sr3:
        site_units_per_day = ui.number_input("Units the site can receive per day:", min_value=1, value=6, step=1,
                                             help="Limited by crane, laydown area, team and escort / night-move windows")

    if "site_check_df" not in st.session_state:
        st.session_state.site_check_df = pd.DataFrame([
            {"Condition": "Heavy-load access road (≥ 45 t per axle group) to the unloading point", "Status": "Open", "Owner": "", "Due": None},
            {"Condition": "Crane pad / crane booked", "Status": "Open", "Owner": "", "Due": None},
            {"Condition": "Foundations / plinths for BESS and MVS ready", "Status": "Open", "Owner": "", "Due": None},
            {"Condition": "Site permits for storing dangerous goods / batteries", "Status": "Open", "Owner": "", "Due": None},
            {"Condition": "Fire-safety arrangements (spacing, extinguishing, emergency plan)", "Status": "Open", "Owner": "", "Due": None},
            {"Condition": "Temporary power for SoC maintenance / auxiliary supply", "Status": "Open", "Owner": "", "Due": None},
            {"Condition": "Security / fencing of the laydown area", "Status": "Open", "Owner": "", "Due": None},
        ])
    st.session_state.site_check_df["Due"] = pd.to_datetime(st.session_state.site_check_df["Due"], errors="coerce").dt.date
    site_check = st.data_editor(
        st.session_state.site_check_df, key="site_check_editor", num_rows="dynamic", hide_index=True,
        use_container_width=True,
        column_config={"Status": st.column_config.SelectboxColumn("Status", options=["Open", "In progress", "Done", "N/A"],
                                                                  required=True),
                       "Due": st.column_config.DateColumn("Due", format="DD/MM/YYYY")})
    st.session_state.site_check_df = site_check
    site_open_items = [str(r["Condition"]) for _, r in site_check.iterrows()
                       if str(r.get("Status")) in ("Open", "In progress") and str(r.get("Condition") or "").strip()]
    _access = site_check[site_check["Condition"].astype(str).str.lower().str.contains("access")]
    site_access_ok = bool(len(_access)) and all(str(s) in ("Done", "N/A") for s in _access["Status"])

    # ---------------- 2. rates ----------------
    st.markdown("#### 2. Rates for the Waiting Options")
    _lib = {}
    if current_user and current_user.get("role") == "admin":
        try:
            _lib = {k: dict(v) for k, v in dict(st.secrets.get("rate_library") or {}).items()}
        except Exception:
            _lib = {}
    _lib_pick = None
    if _lib:
        _lib_pick = ui.selectbox("Load yard rates from your private library (admin only):", ["—"] + list(_lib.keys()))
    _src = _lib.get(_lib_pick) if _lib_pick and _lib_pick != "—" else None
    if _src:
        _yd = {k: float(_src.get(k, 0) or 0) for k in ("haul_bess", "haul_other", "lift", "day_bess", "day_other",
                                                       "ins_permille", "ins_cap", "extra_permit")}
        _ycur = str(_src.get("currency", "ILS"))
        _yd_note = f"Loaded from the private library: {_lib_pick}."
    elif is_israel:
        _yd = {"haul_bess": 3000.0, "haul_other": 500.0, "lift": 250.0, "day_bess": 150.0, "day_other": 90.0,
               "ins_permille": 0.9, "ins_cap": 2_000_000.0, "extra_permit": 0.0}
        _ycur = "ILS"
        _yd_note = ("Indicative Israel 2026 values (rounded market ranges: port → yard haul for a 40–48 t DG BESS box "
                    "ILS 2,500–3,500; non-stackable storage ILS 120–180 per day; lift ILS 200–300 per move; insurance "
                    "≈ 1‰ of value per month). Replace them with the quote you received.")
    else:
        _yd = {"haul_bess": 700.0, "haul_other": 250.0, "lift": 75.0, "day_bess": 30.0, "day_other": 15.0,
               "ins_permille": 1.0, "ins_cap": 1_000_000.0, "extra_permit": 0.0}
        _ycur = "EUR"
        _yd_note = "Placeholder values — enter the storage yard's quote."
    _yard_cur_opts = ["ILS", "EUR", "USD"]
    with st.expander("C. Interim storage yard", expanded=True):
        st.caption(_yd_note)
        if not _src:
            st.caption(verified_note("yard"))
        y0, y1, y2, y3 = st.columns(4)
        with y0:
            yard_cur = ui.selectbox("Yard quote currency:", _yard_cur_opts, index=_yard_cur_opts.index(_ycur))
            yard_fx = ui.number_input("1 USD = ILS:", min_value=0.5, value=3.0, step=0.01, format="%.3f",
                                      help="Check today's rate") if yard_cur == "ILS" else None
        with y1:
            yh_b = ui.number_input(f"Haul port → yard, BESS / DG box ({yard_cur}):", min_value=0.0, value=_yd["haul_bess"], step=100.0)
            yh_o = ui.number_input(f"Haul port → yard, other box ({yard_cur}):", min_value=0.0, value=_yd["haul_other"], step=50.0)
            y_lift = ui.number_input(f"Lift on / off per move ({yard_cur}):", min_value=0.0, value=_yd["lift"], step=10.0)
        with y2:
            yd_b = ui.number_input(f"Storage per BESS per day, not stackable ({yard_cur}):", min_value=0.0, value=_yd["day_bess"], step=5.0)
            yd_o = ui.number_input(f"Storage per other box per day ({yard_cur}):", min_value=0.0, value=_yd["day_other"], step=5.0)
            y_permit = ui.number_input(f"Extra transport permits / escort per unit ({yard_cur}):", min_value=0.0,
                                       value=_yd["extra_permit"], step=50.0, help="Second road move: yard → site")
        with y3:
            y_ins = ui.number_input("Insurance (‰ of declared value per month or part):", min_value=0.0,
                                    value=_yd["ins_permille"], step=0.1, format="%.2f")
            y_cap = ui.number_input(f"Yard insurance limit ({yard_cur}):", min_value=0.0, value=_yd["ins_cap"], step=100000.0)
            yard_bonded = ui.checkbox("Store under customs bond (duty & import VAT paid on release)", value=False)
    _y2usd = (1.0 / yard_fx) if yard_cur == "ILS" else ((1.0 / usd_to_eur) if yard_cur == "EUR" else 1.0)

    with st.expander("A. Factory · B. Port · D. Site pad · Battery maintenance"):
        o1, o2, o3, o4 = st.columns(4)
        with o1:
            f_day = ui.number_input("Factory storage per unit per day (USD):", min_value=0.0, value=10.0, step=1.0)
            f_free = ui.number_input("Free storage days at the factory:", min_value=0, value=14, step=1)
            f_rebook = ui.number_input("Re-booking / cancellation cost per unit (USD):", min_value=0.0, value=300.0, step=50.0,
                                       help="Moving the booking to a later vessel; decide before the cut-off")
            f_pay = ui.checkbox("Supplier payment still due on the original shipment date", value=True)
        with o2:
            p_day = ui.number_input(f"Port storage per unit per day after free days ({curr_code}):", min_value=0.0,
                                    value=round(demurrage_daily_rate * _cm), step=50.0)
            p_free = ui.number_input("Port free days:", min_value=0, value=int(free_days), step=1)
            p_max = ui.number_input("Max days dangerous goods may stay in the port (0 = no limit):", min_value=0,
                                    value=3 if is_israel else 0, step=1,
                                    help="Some ports require immediate removal of DG / BESS units after discharge")
        with o3:
            pad_lump = ui.number_input(f"Temporary pad on site, one-off ({curr_code}):", min_value=0.0,
                                       value=round(15000 * _cm), step=1000.0)
            pad_sec = ui.number_input(f"Site security per day ({curr_code}):", min_value=0.0, value=round(300 * _cm), step=50.0)
        with o4:
            soc_int = ui.number_input("Battery SoC maintenance every (days):", min_value=0, value=60, step=10,
                                      help="Per the manufacturer's storage manual; 0 = not needed")
            soc_cost_u = ui.number_input(f"SoC maintenance per BESS per visit ({curr_code}):", min_value=0.0,
                                         value=round(250 * _cm), step=50.0)

    _vat_paid = str(globals().get("vat_mode", "Paid")).startswith("Paid")
    rates_i = {
        "factory_day": f_day, "factory_free_days": f_free, "pay_on_original_date": f_pay, "rebook_per_unit": f_rebook,
        "port_day": p_day * _to_usd, "port_free_days": p_free, "port_max_days": p_max, "port_unit_limit": 0,
        "yard_haul_bess": yh_b * _y2usd, "yard_haul_other": yh_o * _y2usd, "yard_lift": y_lift * _y2usd,
        "yard_day_bess": yd_b * _y2usd, "yard_day_other": yd_o * _y2usd, "yard_extra_permit": y_permit * _y2usd,
        "yard_ins_permille": y_ins, "yard_ins_cap": y_cap * _y2usd, "bonded": yard_bonded and _vat_paid,
        "fin_rate": fin_rate, "pad_lump": pad_lump * _to_usd, "pad_security_day": pad_sec * _to_usd,
        "site_access_ok": site_access_ok, "soc_interval": soc_int, "soc_cost": soc_cost_u * _to_usd,
    }

    # ---------------- 3. per shipment ----------------
    st.markdown("#### 3. Waiting Time & Best Option per Shipment")
    _nogo = {_MONTHS.index(m) + 1 for m in site_no_go}
    eff_ready = _interim_mod.effective_ready(site_ready_date, _nogo)
    if eff_ready and eff_ready != site_ready_date:
        st.warning(f"Site ready {site_ready_date.strftime('%d/%m/%Y')} falls in a no-go month — first deliveries "
                   f"{eff_ready.strftime('%d/%m/%Y')}.")
    _pd = {sh["name"]: int(_num(sh.get("port_days"))) for sh in msp_shipments}
    _ships = sorted([r for r in plan["shipments"] if r["units"] and r["eta"]], key=lambda r: r["eta"])
    site_rows, interim_total_usd, _cursor, site_last_on_site = [], 0.0, None, None
    site_details = []
    for r in _ships:
        arrive = r["eta"] + timedelta(days=_pd.get(r["name"], 0) + 2)
        start, finish = _interim_mod.deliver(max(arrive, site_ready_date or arrive, _cursor or arrive), r["units"],
                                             max(1, site_units_per_day), _nogo)
        _cursor = finish + timedelta(days=1)
        site_last_on_site = finish
        avg_wait = max(0, (start - arrive).days) + max(0, (finish - start).days) / 2.0
        gap = int(round(avg_wait))
        n_b = r["units_by_type"].get("BESS", 0)
        n_o = r["units"] - n_b
        rates_i["port_unit_limit"] = group_cap.get(port_group_of.get(r["pod"]), 0) if r["pod"] in port_group_of else 0
        opts = _interim_mod.options_for(gap, n_b, n_o, r["goods_value"] / r["units"], r["vat"] / r["units"],
                                        rates_i, bool(r["etd"] and r["etd"] <= date.today() + timedelta(days=7)),
                                        _pd.get(r["name"], 0))
        b = _interim_mod.best(opts)
        interim_total_usd += b["cost"] if b else 0.0
        site_details.append((r, gap, opts, b))
        site_rows.append({"Shipment": r["name"], "Units": r["units"], "Could be on site": arrive.strftime("%d/%m/%Y"),
                          "Delivered to site": f"{start.strftime('%d/%m/%Y')} – {finish.strftime('%d/%m/%Y')}",
                          "Avg. wait (days)": gap,
                          "Best option": b["option"] if b else ("No wait" if gap <= 0 else "⚠️ No feasible option"),
                          f"Cost ({curr_code})": round((b["cost"] if b else 0) * _cm)})
    if site_rows:
        st.dataframe(pd.DataFrame(site_rows), use_container_width=True, hide_index=True)
        site_days_late = delay_days(site_last_on_site)
        _site_caused = max(0, site_days_late - globals().get("project_days_late", 0))
        k1, k2, k3 = st.columns(3)
        k1.metric("Waiting cost (best options)", format_currency(interim_total_usd * _cm, curr_code))
        k2.metric("All units on site", site_last_on_site.strftime("%d/%m/%Y") if site_last_on_site else "—",
                  f"{site_days_late} days after the required date" if site_days_late else "on time", delta_color="off")
        k3.metric("Delay caused by the site", f"{_site_caused} days",
                  (f"{format_currency(_site_caused * delay_cost_per_day_usd * _cm, curr_code)} cost of delay"
                   if delay_cost_per_day_usd and _site_caused else None), delta_color="off")
        site_delay_cost_usd = _site_caused * delay_cost_per_day_usd
        _be = _interim_mod.breakeven_days(rates_i, 0)
        if _be is not None:
            st.caption(f"Rule of thumb: a BESS unit waiting more than about **{_be} days** is cheaper in the interim yard "
                       f"than in the port (haul, lifts and permits vs port storage after free days).")
        for r, gap, opts, b in site_details:
            if gap <= 0:
                continue
            with st.expander(f"{r['name']} — {gap} days average wait: compare the options"):
                st.dataframe(pd.DataFrame([{
                    "Option": o["option"], f"Cost ({curr_code})": round(o["cost"] * _cm),
                    "Possible": "✅" if o["feasible"] else "❌", "Notes": " · ".join(o["notes"])} for o in opts]),
                    use_container_width=True, hide_index=True)
                _c = next((o for o in opts if o["option"].startswith("C.")), None)
                if _c and _c.get("breakdown"):
                    st.caption("Interim yard: " + " · ".join(f"{k} {format_currency(v * _cm, curr_code)}"
                                                             for k, v in _c["breakdown"].items()))
    else:
        site_days_late, site_delay_cost_usd = 0, 0.0
        st.info("Add shipments with ETA in the Multi-Shipment Planner.")
    if site_open_items:
        st.warning(f"{len(site_open_items)} site condition(s) still open: " + "; ".join(site_open_items[:4])
                   + ("…" if len(site_open_items) > 4 else ""))
    st.caption("Waiting cost is shown separately from the landed cost. Average wait accounts for the site receiving "
               f"{site_units_per_day} units per day. Delay caused by the site = days late beyond the delay already "
               "caused by the sailings.")
