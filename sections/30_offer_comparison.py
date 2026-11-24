# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 30_offer_comparison: Tab: Offer Comparison.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# ---------------------------------------------------------------------------
# PROJECT FILE — save / load (sidebar)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# OFFER COMPARISON — compare the offers received on a like-for-like basis
# ---------------------------------------------------------------------------
with tab_quote:
    st.subheader("⚖️ Offer Comparison — Like-for-Like View of the Offers Received")
    st.markdown("Compares every offer on the **same basis**: the full BOM shipped at each offer's rates, with charges an "
                "offer does not state filled in (and flagged), plus compliance with the Project Brief and risk flags.")

    cmp_only_eligible = ui.checkbox("Show only offers that meet the Project Brief", value=False)
    _cmp_cur = "EUR" if is_eur_display else "USD"
    _cm = usd_to_eur if is_eur_display else 1.0
    _kwh = _bess_mwh_sum * 1000.0
    _units_total = sum(bom_totals.values())
    _per_vessel_need = -(-_units_total // max(1, min_vessels)) if _units_total else 0

    _rows_by_opt_c = {str(x.get("Option")): x for _, x in sail_edit.iterrows()}
    _bom_t = sum(b["Qty"] * b["Weight / Unit (t)"] for b in bom_rows)
    _bom_teu = sum(b["Qty"] * teu_factor(b["Container"], 1.0) for b in bom_rows)

    def offer_co2(r):
        row = _rows_by_opt_c.get(r["Option"])
        pol = str(row.get("POL") or "Shanghai") if row is not None else "Shanghai"
        pod_xy = PORT_COORDS.get(r["POD"])
        sea = _carbon_mod.sea_km(pol, r["POD"], pod_xy, r.get("routing") or "Cape of Good Hope")
        road = road_km(site_latlon, pod_xy) if (site_latlon and pod_xy) else 0.0
        kind = "container" if r["Type"] == "Container vessel" else "mpp"
        return _carbon_mod.shipment_emissions(sea, kind, _bom_teu, _bom_t, road, factory_km, carbon_factors,
                                              co2_basis)["total_t"]

    cmp = []
    for r in sail_results:
        if cmp_only_eligible and not r["eligible"]:
            continue
        full_norm = sum(bom_totals.get(t, 0) * r["cost_usd"].get(t, 0) for t in bom_totals)
        full_quoted = sum(bom_totals.get(t, 0) * r["quoted_usd"].get(t, 0) for t in bom_totals)
        risks = []
        if r["missing"]:
            risks.append("Not stated: " + ", ".join(r["missing"]))
        if r["Capacity"] and _per_vessel_need and r["Capacity"] < min(_per_vessel_need, _units_total):
            risks.append(f"Capacity {r['Capacity']} < ~{_per_vessel_need} units per vessel needed")
        g_ = port_group_of.get(r["POD"])
        if g_ in group_cap:
            risks.append(f"Port limit {group_cap[g_]} BESS at {r['POD'].split(',')[0]}")
        if r["free_days"] and r["free_days"] < 3:
            risks.append(f"Only {r['free_days']} free days")
        if r["valid_until"] and r["ETD"] and r["valid_until"] < r["ETD"]:
            risks.append("Validity ends before ETD")
        if _any_dg and r["dg_acceptance"] != "Confirmed":
            risks.append(f"DG acceptance {r['dg_acceptance'].lower()}")
        if r["stowage"] in ("On deck", "Mixed"):
            risks.append(f"{r['stowage']} stowage — check with insurer & manufacturer")
        if r["hot_work"] in ("By shipper", "TBC"):
            risks.append(f"D-ring hot work {'by shipper' if r['hot_work'] == 'By shipper' else 'TBC'}")
        if r["terms"] != "Liner terms":
            risks.append(f"{r['terms']} terms — stevedoring {'not included' if r['terms'] in ('FIO', 'FIOS') else 'partly excluded'}")
        cmp.append({"r": r, "full_norm": full_norm, "full_quoted": full_quoted, "risks": risks, "co2": offer_co2(r)})

    if not cmp:
        st.info("No offers to compare yet — add them in the Offers Received tab.")
    else:
        elig = [c for c in cmp if c["r"]["eligible"]]
        cheapest = min(elig, key=lambda c: c["full_norm"]) if elig else None
        fastest = min([c for c in elig if c["r"]["ETA"]], key=lambda c: c["r"]["ETA"], default=None) if elig else None
        cmp.sort(key=lambda c: (not c["r"]["eligible"], c["full_norm"]))

        h1, h2, h3 = st.columns(3)
        if cheapest:
            h1.metric("Cheapest eligible offer", f"{cheapest['r']['Option']} · {cheapest['r']['offered_by'] or cheapest['r']['Carrier']}",
                      f"{_cmp_cur} {cheapest['full_norm'] * _cm:,.0f} for the full BOM", delta_color="off")
        if fastest:
            h2.metric("Fastest eligible offer", f"{fastest['r']['Option']} · {fastest['r']['offered_by'] or fastest['r']['Carrier']}",
                      f"ETA {fastest['r']['ETA'].strftime('%d/%m/%Y')}", delta_color="off")
        if cheapest and fastest and cheapest is not fastest:
            _dd = (cheapest["r"]["ETA"] - fastest["r"]["ETA"]).days if cheapest["r"]["ETA"] else 0
            h3.metric("Price of speed", f"{_cmp_cur} {(fastest['full_norm'] - cheapest['full_norm']) * _cm:,.0f}",
                      f"{_dd} days earlier", delta_color="off")
        elif cheapest:
            h3.metric("Price of speed", "—", "Cheapest is also the fastest", delta_color="off")
        if not elig:
            st.error("No offer meets the Project Brief yet.")

        headers = ["Rank", "Offered by", "Quote ref", "Carrier", "Vessel", "Type", "POD", "ETD", "ETA", "Transit",
                   "Free days", "Valid until", "Terms", "Stowage", "DG accept.", "Compliance", f"Per BESS unit ({_cmp_cur})",
                   f"Full BOM — quoted ({_cmp_cur})", f"Full BOM — like-for-like ({_cmp_cur})",
                   f"Per kWh ({_cmp_cur})", "CO2e full BOM (t)", "vs cheapest", "Risk flags"]
        rows_out, fills, rank = [], [], 0
        for c in cmp:
            r = c["r"]
            if r["eligible"]:
                rank += 1
            delta = (c["full_norm"] - cheapest["full_norm"]) / cheapest["full_norm"] * 100 if (cheapest and cheapest["full_norm"]) else 0
            rows_out.append({
                "Rank": rank if r["eligible"] else "—", "Offered by": r["offered_by"], "Quote ref": r["quote_ref"],
                "Carrier": r["Carrier"], "Vessel": r["Vessel"], "Type": r["Type"].replace(" vessel", ""),
                "POD": r["POD"].split(",")[0],
                "ETD": r["ETD"].strftime("%d/%m/%Y") if r["ETD"] else "", "ETA": r["ETA"].strftime("%d/%m/%Y") if r["ETA"] else "",
                "Transit": r["Transit (d)"], "Free days": r["free_days"],
                "Valid until": r["valid_until"].strftime("%d/%m/%Y") if r["valid_until"] else "",
                "Terms": r["terms"] + (" · lump sum" if r["price_basis"] == "Lump sum" else ""),
                "Stowage": r["stowage"], "DG accept.": r["dg_acceptance"],
                "Compliance": r["Status"] + ("" if r["eligible"] else f" — {r['Issues']}"),
                f"Per BESS unit ({_cmp_cur})": round(r["cost_usd"].get("BESS", 0) * _cm),
                f"Full BOM — quoted ({_cmp_cur})": round(c["full_quoted"] * _cm),
                f"Full BOM — like-for-like ({_cmp_cur})": round(c["full_norm"] * _cm),
                f"Per kWh ({_cmp_cur})": round(c["full_norm"] * _cm / _kwh, 2) if _kwh else "",
                "CO2e full BOM (t)": round(c["co2"], 1),
                "vs cheapest": ("cheapest" if c is cheapest else f"+{delta:.1f}%") if r["eligible"] else "—",
                "Risk flags": " · ".join(c["risks"]),
            })
            fills.append(GOOD_FILL if (c is cheapest or c is fastest) else (BAD_FILL if not r["eligible"] else None))
        st.dataframe(pd.DataFrame(rows_out), use_container_width=True, hide_index=True)
        st.caption(f"Full BOM = all {_units_total} units of the BOM at the offer's rates (a common yardstick, even though "
                   "the cargo will be split between vessels). 'Like-for-like' fills charges an offer does not state with the "
                   "highest value stated in the other offers for the same vessel type.")

        # charge breakdown per offer (per BESS unit, or first BOM type)
        _bt = "BESS" if "BESS" in bom_totals else (next(iter(bom_totals), None))
        b_rows = []
        _rows_by_opt = {str(x.get("Option")): x for _, x in sail_edit.iterrows()}
        if _bt:
            _bom_line = next(b for b in _bom_valid if b["Type"] == _bt)
            lines = ([("Freight", None)] + [(CHARGE_LABELS[k], k) for k in CHARGE_COLS if _applies(k, _bom_line)]
                     + [(CHARGE_LABELS[k], k) for k in TERM_COLS] + [("War risk & other", "other")])
            b_headers = [f"Charge per {_bt} unit"] + [c["r"]["Option"] for c in cmp]
            for label, key in lines:
                rr = {f"Charge per {_bt} unit": label}
                for c in cmp:
                    row = _rows_by_opt.get(c["r"]["Option"])
                    fx = _fx_usd(row) * _cm
                    size = _bom_line["Container"]
                    if key is None:
                        v = offer_freight(row, size)
                        rr[c["r"]["Option"]] = f"{v * fx:,.0f}" + (" (lump sum)" if row.get("Price Basis") == "Lump sum" else "")
                    elif key == "other":
                        rr[c["r"]["Option"]] = f"{_num(row.get('War Risk & Other / Unit')) * fx:,.0f}"
                    elif key in TERM_COLS:
                        if not _term_applies(row, key):
                            rr[c["r"]["Option"]] = "in terms"
                        else:
                            v = _stated(row, TERM_COLS[key])
                            rr[c["r"]["Option"]] = (f"{v * fx:,.0f}" if v is not None
                                                   else f"not stated → {_fill_terms.get(key, 0.0) * _cm:,.0f}")
                    else:
                        v = _stated(row, CHARGE_COLS[key])
                        mult = teu_factor(size, 1.0) if key == "baf" else 1.0
                        if v is None:
                            rr[c["r"]["Option"]] = f"not stated → {_fill.get((_vclass(row), key), 0.0) * _cm * mult:,.0f}"
                        else:
                            rr[c["r"]["Option"]] = "included" if v == 0 else f"{v * fx * mult:,.0f}"
                b_rows.append(rr)
            with st.expander(f"Charge breakdown per {_bt} unit ({_cmp_cur})"):
                st.dataframe(pd.DataFrame(b_rows), use_container_width=True, hide_index=True)

        basis = [
            f"Project: {project_name}",
            f"Cargo: " + ", ".join(f"{q} × {t}" for t, q in bom_totals.items()) +
            (f" · {_bess_mwh_sum:,.1f} MWh DC" if _bess_mwh_sum else ""),
            f"Sailing window: {brief_fob_date.strftime('%d/%m/%Y')} – {brief_must_sail_by.strftime('%d/%m/%Y')}; "
            f"required on site {delivery_date.strftime('%d/%m/%Y')}",
            "Requirements: " + ", ".join(x for x in [
                "direct sailing only" if req_direct_only else "",
                "no Red Sea / Suez routing" if req_no_red_sea else "",
                f"max {max_bess_per_vessel} BESS per vessel" if max_bess_per_vessel else "",
                "marine insurance by the client" if insurance_by_client else ""] if x),
            "Full BOM = all units of the BOM priced at each offer's per-unit rates (common yardstick).",
            "Like-for-like = charges not stated in an offer are filled with the highest value stated in the other offers "
            "for the same vessel type (container vs MPP / charter). 0 in an offer = included in the freight.",
            "Lump-sum offers are spread over the units they cover. Under FIO / FILO / LIFO terms the excluded loading and / "
            "or discharge (stevedoring) cost is added — stated, or filled from the other offers and flagged.",
            "DG surcharge and DG yard apply to dangerous-goods units only; heavy-lift applies to boxes above 30.48 t gross.",
            "Ocean and local charges only — inland transport, duties, VAT and permits are not part of this comparison.",
        ]
        _xlsx = _cmp_mod.build_comparison_xlsx(
            {"project": project_name, "currency": _cmp_cur,
             "units_text": f"{_units_total} units, {_bess_mwh_sum:,.1f} MWh DC"},
            rows_out, headers,
            money_cols={f"Per BESS unit ({_cmp_cur})", f"Full BOM — quoted ({_cmp_cur})", f"Full BOM — like-for-like ({_cmp_cur})"},
            fills=fills, breakdown_rows=b_rows, breakdown_headers=b_headers if _bt else [], basis_lines=basis)
        st.download_button("⬇️ Download comparison report (Excel)", data=_xlsx,
                           file_name=f"Offer_Comparison_{_re.sub(r'[^A-Za-z0-9]+', '_', project_name)}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
