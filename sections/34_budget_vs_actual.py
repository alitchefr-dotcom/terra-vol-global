# Terra Vol Global — section 34_budget_vs_actual: Tab: Budget vs Actual.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# ---------------------------------------------------------------------------
# BUDGET VS ACTUAL — frozen budget per shipment & category vs invoices received
# ---------------------------------------------------------------------------
BUDGET_CATEGORIES = ["Equipment", "Ocean freight & origin", "Marine insurance", "Customs duty",
                     "Destination port & storage", "Inland transport", "Permits & project", "L/C fees", "Other"]
PROJECT_LEVEL = "Project-level"


def _budget_from_plan():
    """Current plan → {(shipment, category): USD} (VAT excluded — it is recovered)."""
    b = {}
    for r in plan["shipments"]:
        n = r["name"]
        b[(n, "Equipment")] = r["goods_value"]
        b[(n, "Ocean freight & origin")] = r["origin_charges"] + r["freight"] + r["baf"] + r["efs"]
        b[(n, "Marine insurance")] = r["insurance"]
        b[(n, "Customs duty")] = r["duty"]
        b[(n, "Destination port & storage")] = r["dthc"] + r["port_delay"] + r["extra"]
        b[(n, "Inland transport")] = r["trucking"]
    b[(PROJECT_LEVEL, "Permits & project")] = plan["project_level_costs"]
    _G = globals()
    if _G.get("pay_kind") == "LC":
        b[(PROJECT_LEVEL, "L/C fees")] = _G.get("lc_fee_total", 0.0) + _G.get("lc_fixed", 0.0)
    return {k: float(v) for k, v in b.items() if abs(v) > 0.5}


with tab_budget:
    st.subheader("📒 Budget vs Actual — Invoices against the Approved Budget")
    st.markdown("Freeze the budget once the plan is approved, then record the invoices as they arrive. The app shows the "
                "variance per shipment and category, the forecast at completion and how much contingency is left.")

    _bl = st.session_state.get("_budget_baseline")
    bb1, bb2 = st.columns([3, 1])
    with bb1:
        if _bl:
            st.success(f"Budget frozen on {_bl['frozen_on']} — {_bl.get('label', '')}")
        else:
            st.info("No frozen budget yet — the current plan is shown as the budget until you freeze it.")
    with bb2:
        if st.button("🔒 Freeze current plan as budget" if not _bl else "🔁 Re-freeze budget from current plan"):
            st.session_state["_budget_baseline"] = {
                "frozen_on": date.today().isoformat(), "label": project_name,
                "contingency_usd": float(plan["contingency"]),
                "lines": [{"Shipment": k[0], "Category": k[1], "USD": v} for k, v in _budget_from_plan().items()]}
            st.rerun()
    _bl = st.session_state.get("_budget_baseline")
    budget = ({(l["Shipment"], l["Category"]): float(l["USD"]) for l in _bl["lines"]} if _bl else _budget_from_plan())
    contingency_budget = float(_bl["contingency_usd"]) if _bl else float(plan["contingency"])
    _ship_names = sorted({k[0] for k in budget if k[0] != PROJECT_LEVEL}) + [PROJECT_LEVEL]

    st.markdown("#### Invoices / Actual Costs")
    st.caption("One line per invoice (or invoice line). Tick 'Final' when the category is complete for that shipment — "
               "the forecast then uses the actual amount instead of the budget.")
    if "actuals_df" not in st.session_state:
        st.session_state.actuals_df = pd.DataFrame(columns=["Date", "Shipment", "Category", "Supplier", "Invoice No.",
                                                            "Currency", "Amount", "Paid", "Final", "Notes"])
    act_edit = st.data_editor(
        st.session_state.actuals_df, key="actuals_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "Shipment": st.column_config.SelectboxColumn("Shipment", options=_ship_names, required=True),
            "Category": st.column_config.SelectboxColumn("Category", options=BUDGET_CATEGORIES, required=True),
            "Currency": st.column_config.SelectboxColumn("Currency", options=["USD", "EUR"], required=True),
            "Amount": st.column_config.NumberColumn("Amount", step=100.0, format="%.2f"),
            "Paid": st.column_config.CheckboxColumn("Paid"),
            "Final": st.column_config.CheckboxColumn("Final", help="No more invoices expected for this shipment & category"),
        },
    )

    actual, final = {}, set()
    for _, a in act_edit.iterrows():
        sh_, cat_ = a.get("Shipment"), a.get("Category")
        amt = _num(a.get("Amount"))
        if not sh_ or not cat_ or (isinstance(sh_, float) and pd.isna(sh_)) or not amt:
            continue
        usd = amt / usd_to_eur if str(a.get("Currency")).upper().startswith("EUR") else amt
        actual[(sh_, cat_)] = actual.get((sh_, cat_), 0.0) + usd
        if bool(a.get("Final")) and not pd.isna(a.get("Final")):
            final.add((sh_, cat_))

    _m = usd_to_eur if is_eur_display else 1.0
    keys = sorted(set(budget) | set(actual), key=lambda k: (k[0] == PROJECT_LEVEL, k[0], BUDGET_CATEGORIES.index(k[1])
                                                           if k[1] in BUDGET_CATEGORIES else 99))
    rows, tot_b, tot_a, tot_f = [], 0.0, 0.0, 0.0
    for k in keys:
        b_, a_ = budget.get(k, 0.0), actual.get(k, 0.0)
        f_ = a_ if k in final else max(a_, b_)
        var = f_ - b_
        tot_b += b_; tot_a += a_; tot_f += f_
        flag = ""
        if b_ and var / b_ > 0.05:
            flag = "🔴 over budget"
        elif not b_ and a_:
            flag = "🟠 not in budget"
        elif k in final and var < 0:
            flag = "🟢 under budget"
        rows.append({"Shipment": k[0], "Category": k[1], f"Budget ({curr_code})": round(b_ * _m),
                     f"Actual to date ({curr_code})": round(a_ * _m),
                     f"Forecast at completion ({curr_code})": round(f_ * _m),
                     f"Variance ({curr_code})": round(var * _m),
                     "Variance %": f"{var / b_ * 100:+.1f}%" if b_ else "—", "Status": "Final" if k in final else "Open",
                     "Flag": flag})

    overrun = tot_f - tot_b
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Budget (excl. VAT & contingency)", format_currency(tot_b * _m, curr_code))
    m2.metric("Actual to date", format_currency(tot_a * _m, curr_code), f"{tot_a / tot_b * 100:.0f}% of budget" if tot_b else None,
              delta_color="off")
    m3.metric("Forecast at completion", format_currency(tot_f * _m, curr_code),
              f"{overrun * _m:+,.0f} vs budget", delta_color="inverse")
    m4.metric("Contingency left", format_currency((contingency_budget - max(0.0, overrun)) * _m, curr_code),
              f"of {format_currency(contingency_budget * _m, curr_code)}", delta_color="off")
    if overrun > contingency_budget:
        st.error("Forecast overrun exceeds the contingency reserve — escalate / re-approve the budget.")

    view = st.radio("View:", ["By category", "By shipment", "Detail"], horizontal=True, key="bva_view")
    det = pd.DataFrame(rows)
    if len(det):
        num_cols = [c for c in det.columns if c.endswith(f"({curr_code})")]
        if view == "Detail":
            st.dataframe(det, use_container_width=True, hide_index=True)
        else:
            by = "Category" if view == "By category" else "Shipment"
            agg = det.groupby(by)[num_cols].sum()
            _bcol, _vcol = f"Budget ({curr_code})", f"Variance ({curr_code})"
            agg["Variance %"] = [f"{v / b * 100:+.1f}%" if b else "—" for b, v in zip(agg[_bcol], agg[_vcol])]
            st.dataframe(agg, use_container_width=True)
            st.bar_chart(agg[[f"Budget ({curr_code})", f"Forecast at completion ({curr_code})"]])

        _out = io.BytesIO()
        with pd.ExcelWriter(_out, engine="openpyxl") as _w:
            det.to_excel(_w, sheet_name="Budget vs Actual", index=False)
            act_edit.to_excel(_w, sheet_name="Invoices", index=False)
        st.download_button("⬇️ Download budget vs actual (Excel)", data=_out.getvalue(),
                           file_name=f"Budget_vs_Actual_{_re.sub(r'[^A-Za-z0-9]+', '_', project_name)}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Import VAT is excluded (recovered). EUR invoices are converted at the current exchange rate in the sidebar. "
               "Forecast = actual for 'Final' lines, otherwise the higher of actual and budget.")
