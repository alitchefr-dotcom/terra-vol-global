# Terra Vol Global — section 33_cash_flow: Tab: Cash Flow.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# ---------------------------------------------------------------------------
# CASH FLOW — payments over time from the shipments of the Multi-Shipment Planner
# ---------------------------------------------------------------------------
# Import VAT: "postponed" = accounted for in the VAT return (no cash outflow at import) for registered importers
# with the national scheme / licence; otherwise paid at import and recovered after N months. Indicative — confirm locally.
IMPORT_VAT_DEFAULTS = {
    "Israel": ("Paid at import, recovered later", 2),
    "Netherlands": ("Postponed (VAT return)", 0), "Belgium": ("Postponed (VAT return)", 0),
    "France": ("Postponed (VAT return)", 0), "Finland": ("Postponed (VAT return)", 0),
}
PAYMENT_PRESETS = {
    "T/T 30 / 60 / 10 (advance / before shipment / after commissioning)": {"kind": "TT", "adv": 30, "pre": 60, "ret": 10},
    "T/T 30 / 70 (advance / before shipment)": {"kind": "TT", "adv": 30, "pre": 70, "ret": 0},
    "L/C at sight (10% T/T advance, 90% L/C, paid on presentation of shipping documents)":
        {"kind": "LC", "adv": 10, "lc": 90, "ret": 0, "usance": 0},
    "L/C 90 days usance (10% T/T advance, 90% L/C deferred)": {"kind": "LC", "adv": 10, "lc": 90, "ret": 0, "usance": 90},
    "Custom": {"kind": "TT", "adv": 30, "pre": 60, "ret": 10},
}

with tab_cash:
    st.subheader("💵 Cash Flow — When the Money Goes Out")
    st.markdown("Monthly payments for the whole project, built from the shipments in the **Multi-Shipment Planner** "
                "(ETD / ETA of each vessel), the supplier payment terms and the import VAT regime of the country.")

    # ---------------- supplier payment terms ----------------
    st.markdown("#### 1. Supplier Payment Terms")
    cf1, cf2, cf3 = st.columns([2, 1, 1])
    with cf1:
        pay_preset = ui.selectbox("Payment terms:", list(PAYMENT_PRESETS.keys()), index=0)
    with cf2:
        po_date = ui.date_input("Purchase order date:", value=brief_exw_ready - timedelta(days=120))
    with cf3:
        cod_date = ui.date_input("Commissioning date:", value=delivery_date + timedelta(days=60))
    _p = PAYMENT_PRESETS[pay_preset]
    pay_kind = _p["kind"] if pay_preset != "Custom" else ui.selectbox("Instrument:", ["TT", "LC"], index=0)
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        pct_adv = ui.number_input("Advance at PO (%):", min_value=0.0, max_value=100.0, value=float(_p["adv"]), step=5.0) if pay_preset == "Custom" else float(_p["adv"])
    if pay_kind == "TT":
        with pc2:
            pct_pre = ui.number_input("Before shipment (%):", min_value=0.0, max_value=100.0, value=float(_p.get("pre", 60)),
                                      step=5.0) if pay_preset == "Custom" else float(_p["pre"])
        pct_lc, usance = 0.0, 0
    else:
        with pc2:
            pct_lc = ui.number_input("Under L/C (%):", min_value=0.0, max_value=100.0, value=float(_p.get("lc", 90)),
                                     step=5.0) if pay_preset == "Custom" else float(_p["lc"])
        with pc3:
            usance = ui.selectbox("L/C usance (days):", [0, 30, 60, 90, 120, 180],
                                  index=[0, 30, 60, 90, 120, 180].index(int(_p.get("usance", 0))))
        pct_pre = 0.0
    with pc4:
        pct_ret = ui.number_input("After commissioning (%):", min_value=0.0, max_value=100.0, value=float(_p.get("ret", 10)),
                                  step=5.0) if pay_preset == "Custom" else float(_p["ret"])
    if abs(pct_adv + pct_pre + pct_lc + pct_ret - 100) > 0.01:
        st.warning(f"Payment terms add up to {pct_adv + pct_pre + pct_lc + pct_ret:g}% — should be 100%.")
    if pay_kind == "LC":
        lc1, lc2, lc3, lc4 = st.columns(4)
        with lc1:
            lc_issue_pct = ui.number_input("L/C issuance fee (% per quarter):", min_value=0.0, value=0.25, step=0.05)
        with lc2:
            lc_conf_pct = ui.number_input("L/C confirmation fee (% per quarter):", min_value=0.0, value=0.15, step=0.05)
        with lc3:
            lc_fixed = ui.number_input("L/C fixed bank charges (USD):", min_value=0.0, value=1500.0, step=250.0)
        with lc4:
            lc_presentation = ui.number_input("Documents presented after ETD (days):", min_value=0, value=10, step=1)
        lc_open_date = po_date + timedelta(days=30)
        st.caption(f"L/C assumed opened 30 days after the PO ({lc_open_date.strftime('%d/%m/%Y')}). Fees are charged at opening "
                   "for the number of quarters until payment.")

    # ---------------- import VAT ----------------
    st.markdown("#### 2. Import VAT Cash Impact")
    _vat_def = IMPORT_VAT_DEFAULTS.get(destination_country, ("Paid at import, recovered later", 2))
    vv1, vv2, vv3 = st.columns(3)
    with vv1:
        vat_mode = ui.selectbox("Import VAT regime:", ["Paid at import, recovered later", "Postponed (VAT return)"],
                                index=0 if _vat_def[0].startswith("Paid") else 1)
    with vv2:
        vat_lag_m = ui.number_input("Months until import VAT is recovered:", min_value=0, max_value=24, value=_vat_def[1],
                                    step=1, disabled=vat_mode.startswith("Postponed"))
    with vv3:
        fin_rate = ui.number_input("Financing cost (% per year):", min_value=0.0, value=6.0, step=0.5)
    st.caption("Indicative defaults per country — postponed import VAT accounting usually requires VAT registration and a "
               "licence / authorisation. Confirm the regime and the refund timing with your tax adviser.")

    # ---------------- build transactions ----------------
    tx = []  # (date, category, usd, currency_side)
    eq_total = plan["goods_total"]
    ships = [r for r in plan["shipments"] if r["etd"] and r["eta"]]
    skipped = [r["name"] for r in plan["shipments"] if not (r["etd"] and r["eta"])]
    if skipped:
        st.warning("Shipments without ETD / ETA are left out of the timeline: " + ", ".join(skipped))
    _pd_by = {sh["name"]: int(_num(sh.get("port_days"))) for sh in msp_shipments}

    if eq_total > 0:
        tx.append((po_date, "Equipment — supplier", eq_total * pct_adv / 100, "Foreign"))
        if pct_ret:
            tx.append((cod_date, "Equipment — supplier", eq_total * pct_ret / 100, "Foreign"))
    lc_fee_total = 0.0
    for r in ships:
        gv = r["goods_value"]
        if pay_kind == "TT" and pct_pre:
            tx.append((max(brief_exw_ready, r["etd"] - timedelta(days=7)), "Equipment — supplier", gv * pct_pre / 100, "Foreign"))
        if pay_kind == "LC" and pct_lc:
            pay_d = r["etd"] + timedelta(days=int(lc_presentation) + int(usance))
            amt = gv * pct_lc / 100
            tx.append((pay_d, "Equipment — supplier", amt, "Foreign"))
            quarters = max(1, -(-((pay_d - lc_open_date).days) // 90))
            lc_fee_total += amt * (lc_issue_pct + lc_conf_pct) / 100 * quarters
        tx.append((r["etd"], "Ocean freight & origin", r["origin_charges"] + r["freight"] + r["baf"] + r["efs"] + r["insurance"], "Foreign"))
        tx.append((r["eta"], "Customs duty", r["duty"], "Local"))
        pdays = _pd_by.get(r["name"], 0)
        tx.append((r["eta"] + timedelta(days=pdays), "Destination port & storage", r["dthc"] + r["port_delay"] + r["extra"], "Local"))
        tx.append((r["eta"] + timedelta(days=pdays + 2), "Inland transport", r["trucking"], "Local"))
        if not vat_mode.startswith("Postponed") and r["vat"]:
            tx.append((r["eta"], "Import VAT paid", r["vat"], "Local"))
            refund_d = r["eta"] + timedelta(days=int(round(30.4 * vat_lag_m)))
            tx.append((refund_d, "Import VAT recovered", -r["vat"] * vat_recovery_pct / 100, "Local"))
    if pay_kind == "LC" and pct_lc:
        tx.append((lc_open_date, "L/C bank fees", lc_fee_total + lc_fixed, "Foreign"))
    if ships and plan["project_level_costs"]:
        first_eta = min(r["eta"] for r in ships)
        tx.append((first_eta - timedelta(days=30), "Permits & project costs", plan["project_level_costs"], "Local"))

    tx = [t for t in tx if abs(t[2]) > 0.5]
    if not tx:
        st.info("No payments yet — add shipments with ETD / ETA in the Multi-Shipment Planner (or send the allocation plan there).")
    else:
        _m = usd_to_eur if is_eur_display else 1.0
        tdf = pd.DataFrame(tx, columns=["Date", "Category", "USD", "Side"])
        tdf["Amount"] = tdf["USD"] * _m
        tdf["Month"] = pd.to_datetime(tdf["Date"]).dt.to_period("M").astype(str)
        monthly = tdf.pivot_table(index="Month", columns="Category", values="Amount", aggfunc="sum", fill_value=0.0)
        monthly["Total"] = monthly.sum(axis=1)
        monthly["Cumulative"] = monthly["Total"].cumsum()
        peak_month = monthly["Cumulative"].idxmax()
        peak = monthly["Cumulative"].max()

        vat_cost = 0.0
        if not vat_mode.startswith("Postponed"):
            vat_cost = sum(r["vat"] for r in ships) * vat_recovery_pct / 100 * (fin_rate / 100) * (vat_lag_m / 12.0) * _m
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Peak cash requirement", format_currency(peak, curr_code), f"in {peak_month}", delta_color="off")
        k2.metric("Total paid out (net of VAT recovered)", format_currency(monthly["Total"].sum(), curr_code))
        k3.metric("Import VAT financing cost", format_currency(vat_cost, curr_code),
                  f"{vat_lag_m} months at {fin_rate:g}%" if vat_cost else "postponed / none", delta_color="off")
        if pay_kind == "LC":
            k4.metric("L/C bank fees", format_currency((lc_fee_total + lc_fixed) * _m, curr_code))
        else:
            k4.metric("Payment terms", "T/T")

        st.markdown(f"#### 3. Monthly Payments ({curr_code})")
        _cats = [c for c in monthly.columns if c not in ("Total", "Cumulative")]
        st.bar_chart(monthly[_cats])
        st.line_chart(monthly[["Cumulative"]])
        st.dataframe(monthly.round(0), use_container_width=True)

        side = tdf.pivot_table(index="Month", columns="Side", values="Amount", aggfunc="sum", fill_value=0.0)
        st.markdown("#### 4. Currency Exposure")
        st.caption("Foreign = paid to the supplier, carriers and the L/C bank (usually USD). Local = duties, VAT, port, inland "
                   "transport and permits in the destination country's currency.")
        st.dataframe(side.round(0), use_container_width=True)

        _out = io.BytesIO()
        with pd.ExcelWriter(_out, engine="openpyxl") as _w:
            monthly.round(2).to_excel(_w, sheet_name="Monthly")
            tdf.sort_values("Date")[["Date", "Category", "Side", "Amount"]].to_excel(_w, sheet_name="Payments", index=False)
            side.round(2).to_excel(_w, sheet_name="Currency exposure")
        st.download_button("⬇️ Download cash flow (Excel)", data=_out.getvalue(),
                           file_name=f"Cash_Flow_{_re.sub(r'[^A-Za-z0-9]+', '_', project_name)}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.caption("Contingency and the decommissioning provision are reserves, not scheduled payments, and are not shown.")
