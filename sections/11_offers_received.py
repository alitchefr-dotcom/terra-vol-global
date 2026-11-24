# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 11_offers_received: Tab: Offers Received — offers, compliance checks, port rules, allocation plan.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
with tab_sail:
    st.subheader("⛴️ Offers Received — Sailings Offered by Forwarders & Carriers")
    st.markdown("Enter every offer you received (one row per vessel / sailing; several forwarders, carriers, MPP / charter "
                "vessels and weeks). Each offer is checked automatically against the Project Brief.")

    VESSEL_TYPES = ["Container vessel", "MPP vessel", "Charter (dedicated)"]
    ROUTINGS = ["Cape of Good Hope", "Suez Canal / Red Sea", "Other"]
    SAIL_POD_OPTIONS = destination_ports + [p for p in ISRAEL_PORTS + all_european_ports if p not in destination_ports]

    if "sail_df" not in st.session_state:
        _haifa = "Haifa Port (Adani), Israel" if is_israel else destination_ports[0]
        _ashdod = "Ashdod Port, Israel" if is_israel else destination_ports[min(1, len(destination_ports) - 1)]
        _bay = "Haifa Bay Port (SIPG), Israel" if is_israel else destination_ports[0]
        _yard = "Israel Shipyards Port (Haifa), Israel" if is_israel else destination_ports[0]
        _base = {"Offered By": "Forwarder 1", "Quote Ref": "", "POL": "Shanghai", "Currency": "USD", "DG Surcharge / Unit": 450.0, "Heavy-Lift / Unit": 1200.0,
                 "DG Yard Origin / Unit": 300.0, "Lashing / Unit": 250.0, "BAF / TEU (if not incl.)": 0.0,
                 "Origin Local / Unit": 350.0, "Dest. Local / Unit": 400.0, "Free Days": 5,
                 "Valid Until": date(2027, 1, 15), "Transshipment Port": "",
                 "Price Basis": "Per unit", "Lump Sum": None, "Lump Sum Units": None, "Terms": "Liner terms",
                 "Loading Cost / Unit": None, "Discharge Cost / Unit": None, "DG Acceptance": "Confirmed",
                 "Stowage": "TBC", "Hot Work / D-rings": "Not required", "War Risk & Other / Unit": 0.0,
                 "Load Terminal": "", "Discharge Terminal": ""}
        st.session_state.sail_df = pd.DataFrame([
            dict(_base, **{"Option": "A1", "Carrier": "Sample Line A", "Vessel": "Sample Vessel 1", "Vessel Type": "Container vessel",
                           "POD": _haifa, "ETD": date(2026, 12, 26), "ETA": date(2027, 2, 8), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8500.0, "Freight / 40ft": 12000.0}),
            dict(_base, **{"Offered By": "Forwarder 2", "Option": "B1", "Carrier": "Sample Line B", "Vessel": "Sample Vessel 2", "Vessel Type": "Container vessel",
                           "POD": _ashdod, "ETD": date(2026, 12, 29), "ETA": date(2027, 2, 14), "Direct": False,
                           "Transshipment Port": "Piraeus", "Routing": "Cape of Good Hope", "Capacity (units)": 30,
                           "Max Gross / Box (t)": 45.0, "Freight / 20ft": 7200.0, "Freight / 40ft": 10500.0}),
            dict(_base, **{"Offered By": "Forwarder 3", "Option": "C1", "Carrier": "Sample Line C", "Vessel": "Sample Vessel 3", "Vessel Type": "Container vessel",
                           "POD": _bay, "ETD": date(2026, 12, 27), "ETA": date(2027, 1, 22), "Direct": True,
                           "Routing": "Suez Canal / Red Sea", "Capacity (units)": 30, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 6800.0, "Freight / 40ft": 9800.0}),
            dict(_base, **{"Offered By": "Forwarder 3", "Option": "D1", "Carrier": "Sample MPP Operator", "Vessel": "Sample MPP 1", "Vessel Type": "MPP vessel",
                           "POD": _haifa, "ETD": date(2026, 12, 30), "ETA": date(2027, 2, 12), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 30, "Max Gross / Box (t)": 60.0,
                           "Freight / 20ft": 19000.0, "Freight / 40ft": 22000.0, "DG Surcharge / Unit": 0.0,
                           "Heavy-Lift / Unit": 0.0, "Lashing / Unit": 600.0, "Terms": "FIO", "Stowage": "Under deck",
                           "Hot Work / D-rings": "By shipper", "DG Acceptance": "Pending"}),
            dict(_base, **{"Offered By": "Forwarder 4", "Option": "F1", "Carrier": "Sample Charter Owner", "Vessel": "Sample Charter 1",
                           "Vessel Type": "Charter (dedicated)", "POD": _haifa, "ETD": date(2026, 12, 28), "ETA": date(2027, 2, 9),
                           "Direct": True, "Routing": "Cape of Good Hope", "Capacity (units)": 60, "Max Gross / Box (t)": 60.0,
                           "Freight / 20ft": None, "Freight / 40ft": None, "Price Basis": "Lump sum", "Lump Sum": 980000.0,
                           "Lump Sum Units": 54, "Terms": "FIO", "Loading Cost / Unit": 300.0, "Discharge Cost / Unit": 350.0,
                           "DG Surcharge / Unit": 0.0, "Heavy-Lift / Unit": 0.0, "Lashing / Unit": 0.0, "Stowage": "Under deck",
                           "Hot Work / D-rings": "Included", "War Risk & Other / Unit": 120.0}),
            dict(_base, **{"Option": "A2", "Carrier": "Sample Line A", "Vessel": "Sample Vessel 4", "Vessel Type": "Container vessel",
                           "POD": _haifa, "ETD": date(2027, 1, 2), "ETA": date(2027, 2, 15), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8300.0, "Freight / 40ft": 11800.0}),
            dict(_base, **{"Offered By": "Forwarder 2", "Option": "E1", "Carrier": "Sample Line E", "Vessel": "Sample Vessel 5", "Vessel Type": "Container vessel",
                           "POD": _yard, "ETD": date(2026, 12, 28), "ETA": date(2027, 2, 10), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 25, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8000.0, "Freight / 40ft": 11500.0}),
            dict(_base, **{"Offered By": "Forwarder 2", "Option": "B2", "Carrier": "Sample Line B", "Vessel": "Sample Vessel 6",
                           "Vessel Type": "Container vessel",
                           "POD": _ashdod, "ETD": date(2026, 12, 30), "ETA": date(2027, 2, 13), "Direct": True,
                           "Routing": "Cape of Good Hope", "Capacity (units)": 24, "Max Gross / Box (t)": 45.0,
                           "Freight / 20ft": 8300.0, "Freight / 40ft": 11800.0, "DG Yard Origin / Unit": None,
                           "Heavy-Lift / Unit": None}),
        ])
    st.caption("Sample offers are pre-filled for illustration — replace them with the real offers. Charges are per unit "
               "(one container / one piece): **a number = separate charge · 0 = included in the freight · empty = not "
               "stated or excluded** (filled in and flagged in the comparison). Add rows at the bottom of the table.")

    sail_edit = st.data_editor(
        st.session_state.sail_df, key="sail_editor", num_rows="dynamic", hide_index=True, use_container_width=True,
        column_order=["Offered By", "Quote Ref", "Option", "Carrier", "Vessel", "Vessel Type", "POL", "POD", "ETD", "ETA", "Direct",
                      "Transshipment Port", "Routing", "Capacity (units)", "Max Gross / Box (t)", "Currency",
                      "Freight / 20ft", "Freight / 40ft", "BAF / TEU (if not incl.)", "DG Surcharge / Unit",
                      "Heavy-Lift / Unit", "DG Yard Origin / Unit", "Lashing / Unit", "Origin Local / Unit",
                      "Dest. Local / Unit", "Price Basis", "Lump Sum", "Lump Sum Units", "Terms", "Loading Cost / Unit",
                      "Discharge Cost / Unit", "War Risk & Other / Unit", "DG Acceptance", "Stowage", "Hot Work / D-rings",
                      "Load Terminal", "Discharge Terminal", "Free Days", "Valid Until"],
        column_config={
            "Vessel Type": st.column_config.SelectboxColumn("Vessel Type", options=VESSEL_TYPES, required=True),
            "POD": st.column_config.SelectboxColumn("POD", options=SAIL_POD_OPTIONS, required=True),
            "ETD": st.column_config.DateColumn("ETD", format="DD/MM/YYYY"),
            "ETA": st.column_config.DateColumn("ETA", format="DD/MM/YYYY"),
            "Valid Until": st.column_config.DateColumn("Valid Until", format="DD/MM/YYYY"),
            "Direct": st.column_config.CheckboxColumn("Direct", help="Direct sailing, no transshipment"),
            "Routing": st.column_config.SelectboxColumn("Routing", options=ROUTINGS, required=True),
            "Currency": st.column_config.SelectboxColumn("Currency", options=["USD", "EUR"], required=True),
            "Capacity (units)": st.column_config.NumberColumn("Capacity (units)", min_value=0, step=1,
                                                              help="Units / slots offered on this sailing"),
            "Max Gross / Box (t)": st.column_config.NumberColumn("Max Gross / Box (t)", min_value=0.0, step=0.5,
                                                                 help="Heaviest container the carrier accepts on this sailing"),
            "Free Days": st.column_config.NumberColumn("Free Days", min_value=0, step=1),
            "Price Basis": st.column_config.SelectboxColumn("Price Basis", options=["Per unit", "Lump sum"], required=True),
            "Lump Sum": st.column_config.NumberColumn("Lump Sum", min_value=0.0, step=10000.0, format="%.0f",
                                                      help="Total freight for the parcel / charter"),
            "Lump Sum Units": st.column_config.NumberColumn("Lump Sum Units", min_value=0, step=1,
                                                            help="Units covered by the lump sum"),
            "Terms": st.column_config.SelectboxColumn("Terms", options=["Liner terms", "FIO", "FILO", "LIFO", "FIOS"], required=True,
                                                      help="FIO = loading & discharge not included; FILO = loading not included; "
                                                           "LIFO = discharge not included"),
            "Loading Cost / Unit": st.column_config.NumberColumn("Loading Cost / Unit", min_value=0.0, step=50.0,
                                                                 help="Stevedoring at the port of loading, if not included in the terms"),
            "Discharge Cost / Unit": st.column_config.NumberColumn("Discharge Cost / Unit", min_value=0.0, step=50.0,
                                                                   help="Stevedoring at the port of discharge, if not included in the terms"),
            "War Risk & Other / Unit": st.column_config.NumberColumn("War Risk & Other / Unit", min_value=0.0, step=10.0),
            "DG Acceptance": st.column_config.SelectboxColumn("DG Acceptance", options=["Confirmed", "Pending", "Refused", "Not stated"]),
            "Stowage": st.column_config.SelectboxColumn("Stowage", options=["Under deck", "On deck", "Mixed", "TBC"]),
            "Hot Work / D-rings": st.column_config.SelectboxColumn("Hot Work / D-rings",
                                                                   options=["Included", "By shipper", "Not required", "TBC"]),
        },
    )

    def _append_offers(_add, msg):
        """Append offer lines to the Offers table: new option codes R1, R2…, defaults for empty list fields."""
        _existing = set(str(x) for x in sail_edit["Option"])
        _k = 1
        _opts = []
        for _ in range(len(_add)):
            while f"R{_k}" in _existing:
                _k += 1
            _opts.append(f"R{_k}")
            _existing.add(f"R{_k}")
        _add = _add.copy()
        _add["Option"] = _opts
        _defaults = {"Vessel Type": "Container vessel", "Routing": "Other", "Currency": "USD", "Price Basis": "Per unit",
                     "Terms": "Liner terms", "DG Acceptance": "Not stated", "Stowage": "TBC", "Hot Work / D-rings": "TBC",
                     "Direct": False}
        for _c, _v in _defaults.items():
            if _c not in _add.columns:
                _add[_c] = _v
            else:
                _add[_c] = _add[_c].where(_add[_c].notna() & (_add[_c].astype(str) != "nan"), _v)
        _add = _add[[c for c in _add.columns if c in sail_edit.columns or c == "Option"]]
        st.session_state.sail_df = pd.concat([sail_edit, _add], ignore_index=True)
        st.session_state.pop("sail_editor", None)
        st.success(msg.format(n=len(_add)))
        st.rerun()

    _imp = st.file_uploader("⬆️ Import offer responses (filled RFQ response templates, .xlsx)", type=["xlsx"],
                            accept_multiple_files=True, key="offer_import")
    if _imp:
        _done = st.session_state.setdefault("_imported_offers", set())
        _new = []
        for _f in _imp:
            _fid = f"{_f.name}-{_f.size}"
            if _fid in _done:
                continue
            try:
                _df = _rfq_mod.read_response(_f.getvalue())
            except Exception as _e:
                st.error(f"Could not read {_f.name}: {_e}")
                continue
            _done.add(_fid)
            if len(_df):
                _new.append(_df)
        if _new:
            _append_offers(pd.concat(_new, ignore_index=True), "Imported {n} offer line(s).")

    # ---------------- AI import from PDF / e-mail / image / pasted text ----------------
    def _ai_key():
        try:
            k = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            k = None
        return k or os.environ.get("ANTHROPIC_API_KEY")

    with st.expander("🤖 Import offers with AI — PDF, e-mail (.eml), screenshot, spreadsheet or pasted text"):
        _key = _ai_key()
        _ai_ok, _ai_msg, _ai_left = ai_allowance()
        if not _ai_ok:
            st.info(_ai_msg)
        elif not _key:
            st.info("AI import is not configured. Add ANTHROPIC_API_KEY to the app secrets "
                    "(Streamlit Cloud › App settings › Secrets).")
        else:
            st.caption(f"AI reads left today: {_ai_left}.")
            st.caption("The files are sent to the AI service (Anthropic Claude API) only to read the offers; they are "
                       "not stored by the app and not used to train AI models. Every line is shown for review before "
                       "it is added — always check prices and dates against the original.")
            _ai_files = st.file_uploader("Offer documents", type=["pdf", "eml", "png", "jpg", "jpeg", "webp", "xlsx",
                                                                  "xls", "csv", "txt", "html", "msg"],
                                         accept_multiple_files=True, key="ai_offer_files")
            _ai_text = st.text_area("…or paste the e-mail / quotation text:", value="", key="ai_offer_text", height=120)
            if st.button("🔎 Read offers", key="ai_read"):
                _blocks, _warns = [], []
                for _f in (_ai_files or [])[:10]:
                    _b, _w = _ai_mod.file_to_blocks(_f.name, _f.getvalue())
                    _blocks += _b
                    _warns += _w
                if _ai_text.strip():
                    _blocks.append({"type": "text", "text": "Pasted text:\n" + _ai_text[:100000]})
                for _w in _warns:
                    st.warning(_w)
                _ctx = (f"Project: {project_name}. Destination: {destination_country}. Cargo: "
                        + "; ".join(f"{b['Qty']} x {b['Item']} {b['Container']} {b['Weight / Unit (t)']} t"
                                    for b in bom_rows) +
                        f". Ports in the app: {', '.join(SAIL_POD_OPTIONS)}.")
                try:
                    with st.spinner("Reading the offers…"):
                        AUTH_GUARD.ai_add(current_user["username"])
                        _rows, _summary, _usage = _ai_mod.extract_offers(_key, _blocks, SAIL_POD_OPTIONS, _ctx)
                    st.session_state["_ai_preview"] = {"rows": _rows, "summary": _summary, "usage": _usage}
                except RuntimeError as _e:
                    st.error(str(_e))
            _prev = st.session_state.get("_ai_preview")
            if _prev:
                _u = _prev["usage"]
                st.markdown(f"**{len(_prev['rows'])} offer line(s) found.** {_prev['summary']}")
                st.caption(f"AI usage: {_u['input_tokens']:,} + {_u['output_tokens']:,} tokens ≈ ${_u['cost_usd']:.3f}"
                           + (" · ⚠️ answer was cut off — upload fewer documents at a time"
                              if _u.get("stop_reason") == "max_tokens" else ""))
                if _prev["rows"]:
                    _pv = pd.DataFrame(_prev["rows"])
                    _first = ["AI Notes", "Offered By", "Carrier", "Vessel", "Vessel Type", "POD", "ETD", "ETA",
                              "Currency", "Freight / 20ft", "Freight / 40ft", "Lump Sum"]
                    _pv = _pv[[c for c in _first if c in _pv.columns] + [c for c in _pv.columns if c not in _first]]
                    _pv.insert(0, "Add", True)
                    _pv_edit = st.data_editor(_pv, key="ai_preview_editor", hide_index=True, use_container_width=True,
                                              column_config={"Add": st.column_config.CheckboxColumn("Add"),
                                                             "POD": st.column_config.SelectboxColumn("POD", options=SAIL_POD_OPTIONS)})
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        if st.button("➕ Add selected lines to the offers", key="ai_add"):
                            _sel = _pv_edit[_pv_edit["Add"] == True].drop(columns=["Add"])  # noqa: E712
                            _notes = _sel.pop("AI Notes") if "AI Notes" in _sel.columns else None
                            st.session_state.pop("_ai_preview", None)
                            st.session_state.pop("ai_preview_editor", None)
                            if len(_sel):
                                _append_offers(_sel.reset_index(drop=True), "Added {n} offer line(s) from the AI import.")
                    with _c2:
                        if st.button("✖ Discard", key="ai_discard"):
                            st.session_state.pop("_ai_preview", None)
                            st.session_state.pop("ai_preview_editor", None)
                            st.rerun()

    # --- heaviest / DG cargo from the BOM, used by the checks
    _bom_valid = [r for r in bom_rows]
    _max_box_t = max([r["Weight / Unit (t)"] for r in _bom_valid if r["Container"] != "MPP / Breakbulk"] or [0.0])

    def _num(v, default=0.0):
        v = pd.to_numeric(v, errors="coerce")
        return default if pd.isna(v) else float(v)

    def _d(v):
        if v is None or (not isinstance(v, (date,)) and pd.isna(v)):
            return None
        return v.date() if hasattr(v, "date") and callable(getattr(v, "date")) else v

    CHARGE_COLS = {"baf": "BAF / TEU (if not incl.)", "dg": "DG Surcharge / Unit", "heavy": "Heavy-Lift / Unit",
                   "dg_yard": "DG Yard Origin / Unit", "lashing": "Lashing / Unit",
                   "origin": "Origin Local / Unit", "dest": "Dest. Local / Unit"}
    CHARGE_LABELS = {"baf": "BAF", "dg": "DG surcharge", "heavy": "Heavy-lift", "dg_yard": "DG yard at origin",
                     "lashing": "Lashing", "origin": "Origin local charges", "dest": "Destination local charges"}

    def _fx_usd(row):
        return (1.0 / usd_to_eur) if str(row.get("Currency")).upper().startswith("EUR") else 1.0

    def _stated(row, col):
        v = pd.to_numeric(row.get(col), errors="coerce")
        return None if pd.isna(v) else float(v)

    def _vclass(row):
        return "container" if (row.get("Vessel Type") or "Container vessel") == "Container vessel" else "mpp"

    # Highest stated value per charge and vessel class — used to fill charges an offer does not state
    _fill = {}
    for _, _r in sail_edit.iterrows():
        for _k, _c in CHARGE_COLS.items():
            _v = _stated(_r, _c)
            if _v is not None:
                _key = (_vclass(_r), _k)
                _fill[_key] = max(_fill.get(_key, 0.0), _v * _fx_usd(_r))

    _any_dg = any("Dangerous goods" in b["Checks"] for b in _bom_valid)
    _any_heavy = any("Heavy box" in b["Checks"] for b in _bom_valid)

    def _applies(key, bom_row=None):
        if key in ("dg", "dg_yard"):
            return ("Dangerous goods" in bom_row["Checks"]) if bom_row else _any_dg
        if key == "heavy":
            return ("Heavy box" in bom_row["Checks"]) if bom_row else _any_heavy
        return True

    TERM_COLS = {"loading": "Loading Cost / Unit", "discharge": "Discharge Cost / Unit"}
    CHARGE_LABELS.update({"loading": "Loading (terms)", "discharge": "Discharge (terms)"})
    _bom_units_total = sum(b["Qty"] for b in _bom_valid) or 1

    def _term_applies(row, key):
        t = str(row.get("Terms") or "Liner terms")
        if key == "loading":
            return t in ("FIO", "FILO", "FIOS")
        return t in ("FIO", "LIFO", "FIOS")

    _fill_terms = {}
    for _, _r in sail_edit.iterrows():
        for _k, _c in TERM_COLS.items():
            _v = _stated(_r, _c)
            if _v is not None:
                _fill_terms[_k] = max(_fill_terms.get(_k, 0.0), _v * _fx_usd(_r))

    def offer_freight(row, size):
        """Freight per unit in the offer currency — per-unit rate, or lump sum spread over the units it covers."""
        if row.get("Price Basis") == "Lump sum" and _num(row.get("Lump Sum")) > 0:
            return _num(row.get("Lump Sum")) / max(1.0, _num(row.get("Lump Sum Units"), default=_bom_units_total))
        return _num(row.get("Freight / 40ft")) if size in ("40ft", "40ft HC") else _num(row.get("Freight / 20ft"))

    def offer_unit_cost_usd(row, bom_row, normalized=True):
        """Ocean + local cost for one unit of a BOM line (USD). normalized=True fills charges the offer does not state."""
        fx = _fx_usd(row)
        size = bom_row["Container"]
        total = offer_freight(row, size) * fx + _num(row.get("War Risk & Other / Unit")) * fx
        for k, col in TERM_COLS.items():
            if _term_applies(row, k):
                v = _stated(row, col)
                total += v * fx if v is not None else (_fill_terms.get(k, 0.0) if normalized else 0.0)
        for k, col in CHARGE_COLS.items():
            if not _applies(k, bom_row):
                continue
            v = _stated(row, col)
            v = v * fx if v is not None else (_fill.get((_vclass(row), k), 0.0) if normalized else 0.0)
            total += v * (teu_factor(size, 1.0) if k == "baf" else 1.0)
        return total

    def offer_missing(row):
        miss = [CHARGE_LABELS[k] for k, col in CHARGE_COLS.items() if _applies(k) and _stated(row, col) is None]
        miss += [CHARGE_LABELS[k] for k, col in TERM_COLS.items() if _term_applies(row, k) and _stated(row, col) is None]
        return miss

    sail_results = []
    for _, row in sail_edit.iterrows():
        opt = str(row.get("Option") or "").strip()
        if not opt or opt.lower() == "nan":
            continue
        etd, eta, valid = _d(row.get("ETD")), _d(row.get("ETA")), _d(row.get("Valid Until"))
        pod = row.get("POD") or ""
        vtype = row.get("Vessel Type") or "Container vessel"
        fails, warns = [], []
        if req_direct_only and not bool(row.get("Direct")):
            ts = str(row.get("Transshipment Port") or "").strip()
            fails.append("Transshipment" + (f" via {ts}" if ts and ts.lower() != "nan" else ""))
        if req_no_red_sea and row.get("Routing") == "Suez Canal / Red Sea":
            fails.append("Routes via Red Sea / Suez")
        if etd is None:
            fails.append("No ETD")
        else:
            if etd < brief_fob_date:
                fails.append(f"Sails before cargo is at port ({brief_fob_date.strftime('%d/%m')})")
            if etd > brief_must_sail_by:
                fails.append(f"Sails after the latest ETD ({brief_must_sail_by.strftime('%d/%m')})")
        max_gross = _num(row.get("Max Gross / Box (t)"))
        if _max_box_t and max_gross and max_gross < _max_box_t:
            fails.append(f"Max gross {max_gross:g} t < heaviest box {_max_box_t:g} t")
        elif _max_box_t and not max_gross:
            warns.append("Max gross per box not confirmed")
        if pod in ISRAEL_PORT_INFO:
            needs = "container" if vtype == "Container vessel" else "charter"
            if not ISRAEL_PORT_INFO[pod][needs]:
                fails.append(f"{pod.split(',')[0]} does not receive {'container' if needs == 'container' else 'charter / MPP'} vessels")
        if brief_pods and pod not in brief_pods:
            warns.append("POD not in the client's requested ports")
        on_site = (eta + timedelta(days=4)) if eta else None
        if on_site and on_site > delivery_date:
            warns.append(f"On site ≈ {on_site.strftime('%d/%m/%Y')}, after required date")
        if valid and valid < date.today():
            warns.append("Quote expired")
        elif valid and etd and valid < etd:
            warns.append("Quote validity ends before ETD — reconfirm")
        if _num(row.get("Capacity (units)")) <= 0:
            warns.append("Capacity not stated")

        status = "❌ Not eligible" if fails else ("⚠️ Eligible — check" if warns else "✅ Eligible")
        # cost per equipment type = quantity-weighted average over all BOM lines of that type
        # (several BESS models with different weights / sizes / DG status are each priced on their own)
        costs, quoted, _qty_t = {}, {}, {}
        for b in _bom_valid:
            q = max(1, b["Qty"])
            costs[b["Type"]] = costs.get(b["Type"], 0.0) + q * offer_unit_cost_usd(row, b, normalized=True)
            quoted[b["Type"]] = quoted.get(b["Type"], 0.0) + q * offer_unit_cost_usd(row, b, normalized=False)
            _qty_t[b["Type"]] = _qty_t.get(b["Type"], 0) + q
        costs = {t: v / _qty_t[t] for t, v in costs.items()}
        quoted = {t: v / _qty_t[t] for t, v in quoted.items()}
        missing = offer_missing(row)
        if offer_freight(row, "20ft") <= 0 and offer_freight(row, "40ft") <= 0:
            warns.append("Freight not stated")
        _dga = str(row.get("DG Acceptance") or "Not stated")
        if _dga == "Refused":
            fails.append("DG cargo refused by the carrier")
            status = "❌ Not eligible"
        elif _dga in ("Pending", "Not stated", "nan") and _any_dg:
            warns.append(f"DG acceptance {_dga.lower()}")
            if status == "✅ Eligible":
                status = "⚠️ Eligible — check"
            status = "❌ Not eligible" if fails else "⚠️ Eligible — check"
        sail_results.append({
            "Option": opt, "Carrier": row.get("Carrier"), "Vessel": row.get("Vessel"), "Type": vtype,
            "POD": pod, "ETD": etd, "ETA": eta,
            "Transit (d)": (eta - etd).days if (eta and etd) else None,
            "Capacity": int(_num(row.get("Capacity (units)"))),
            "Status": status, "Issues": " · ".join(fails + warns),
            "cost_usd": costs, "quoted_usd": quoted, "missing": missing,
            "offered_by": str(row.get("Offered By") or "").replace("nan", ""),
            "quote_ref": str(row.get("Quote Ref") or "").replace("nan", ""),
            "valid_until": valid, "routing": row.get("Routing"), "direct": bool(row.get("Direct")),
            "terms": str(row.get("Terms") or "Liner terms"), "stowage": str(row.get("Stowage") or "TBC"),
            "dg_acceptance": _dga, "hot_work": str(row.get("Hot Work / D-rings") or "TBC"),
            "price_basis": str(row.get("Price Basis") or "Per unit"),
            "free_days": int(_num(row.get("Free Days"))), "eligible": not fails,
        })

    _mult = usd_to_eur if is_eur_display else 1.0
    _sym = "€" if is_eur_display else "$"
    st.markdown("#### Compliance Check vs. Project Brief")
    if sail_results:
        _types = list(dict.fromkeys(b["Type"] for b in _bom_valid))
        st.dataframe(pd.DataFrame([
            dict({"Status": r["Status"], "Offered By": r["offered_by"]},
                 **{k: r[k] for k in ["Option", "Carrier", "Vessel", "Type", "POD"]},
                 **{"ETD": r["ETD"].strftime("%d/%m/%Y") if r["ETD"] else "",
                    "ETA": r["ETA"].strftime("%d/%m/%Y") if r["ETA"] else "",
                    "Transit (d)": r["Transit (d)"], "Capacity": r["Capacity"]},
                 **{f"All-in / {t} unit": f"{_sym} {r['cost_usd'].get(t, 0) * _mult:,.0f}" for t in _types},
                 **{"Issues": r["Issues"]})
            for r in sail_results]), use_container_width=True, hide_index=True)

        eligible = [r for r in sail_results if r["eligible"]]
        _need_bess = bom_totals.get("BESS", 0)
        _cap = sum(r["Capacity"] for r in eligible)
        e1, e2, e3 = st.columns(3)
        e1.metric("Eligible sailings", f"{len(eligible)} / {len(sail_results)}")
        e2.metric("Eligible capacity", f"{_cap} units", help="Sum of the capacity offered on eligible sailings")
        e3.metric("Units to ship", f"{sum(bom_totals.values())}")
        if len(eligible) < min_vessels:
            st.error(f"Only {len(eligible)} eligible sailing(s) — at least {min_vessels} vessels are needed "
                     f"(insurer limit {max_bess_per_vessel} BESS per vessel). Look for more options.")
        elif _cap < sum(bom_totals.values()):
            st.warning("Eligible capacity is lower than the units to ship — add sailings or confirm more capacity.")
        else:
            st.success("Enough eligible sailings and capacity to ship the whole BOM. Allocation comes next.")
        st.caption("All-in / unit = freight + lashing + origin & destination local charges + BAF + DG surcharge & DG yard "
                   "(DG cargo) + heavy-lift (boxes above 30.48 t). Charges an offer does not state are filled with the highest "
                   "value stated in the other offers (see Offer Comparison). On site ≈ ETA + 4 days.")
    else:
        st.info("Add sailing options to check them against the Project Brief.")


    # =====================================================================
    # PORT RULES & ALLOCATION PLAN (decision support — the carrier decides)
    # =====================================================================
    st.markdown("---")
    st.markdown("#### Port Rules — Limits at the Port of Discharge")
    st.caption("Limits set by ports / terminals for BESS (DG Class 9). Ports sharing a 'Limit Group' share one limit. "
               "Leave empty when there is no known limit. Update when the port changes its rules.")
    if "port_rules_df" not in st.session_state:
        _rules = []
        for p in destination_ports:
            ashdod = is_israel and p.startswith("Ashdod Port")   # government Ashdod Port only (not Hadarom / TIL)
            _rules.append({"Port": p, "Limit Group": p.split(",")[0],
                           "Max BESS in Port at Once": 30 if ashdod else None,
                           "Limit Type": "Temporary" if ashdod else "Firm",
                           "Max DG Dwell (days)": None, "Direct Delivery Required": False,
                           "Notes / Source": "New limit reported Nov 2026 — temporary note, confirm with the port before booking" if ashdod else "",
                           "Last Updated": "2026-11" if ashdod else ""})
        st.session_state.port_rules_df = pd.DataFrame(_rules)
    port_rules_edit = st.data_editor(
        st.session_state.port_rules_df, key="port_rules_editor", hide_index=True, use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Max BESS in Port at Once": st.column_config.NumberColumn(min_value=0, step=1),
            "Limit Type": st.column_config.SelectboxColumn(options=["Firm", "Temporary"], required=True,
                                                           help="Temporary limits give a warning; firm limits block the plan"),
            "Max DG Dwell (days)": st.column_config.NumberColumn(min_value=0, step=1),
            "Direct Delivery Required": st.column_config.CheckboxColumn(),
        },
    )
    port_group_of, group_cap, port_dwell_cap, group_temp = {}, {}, {}, {}
    for _, r in port_rules_edit.iterrows():
        p = r.get("Port")
        if not p or (not isinstance(p, str)):
            continue
        g = str(r.get("Limit Group") or p).strip() or p
        port_group_of[p] = g
        cap = _num(r.get("Max BESS in Port at Once"), default=0)
        if cap > 0:
            group_cap[g] = int(cap) if g not in group_cap else min(group_cap[g], int(cap))
            group_temp[g] = (r.get("Limit Type") == "Temporary")
        dw = _num(r.get("Max DG Dwell (days)"), default=0)
        if dw > 0:
            port_dwell_cap[p] = int(dw)

    st.markdown("#### Allocation Plan — Requested vs. Confirmed by the Carrier")
    st.caption("You decide the split and request it; the carrier confirms, reduces or rolls it. "
               "Effective quantity = Confirmed for Confirmed / Reduced lines, Requested while pending, 0 if Rolled / Cancelled. "
               "For MPP / charter vessels, 'Confirmed' means contracted.")
    PLAN_STATUSES = ["Requested", "Confirmed", "Reduced", "Rolled", "Cancelled"]
    _sail_by_opt = {r["Option"]: r for r in sail_results}
    _bom_types = list(dict.fromkeys(b["Type"] for b in _bom_valid))

    if "plan_df" not in st.session_state:
        st.session_state.plan_df = pd.DataFrame(columns=["Option", "Equipment", "Requested", "Confirmed", "Status", "Port Days"])

    if st.button("📝 Draft a starting plan (optional)",
                 help="Fills the table with a first split on eligible sailings, cheapest first, within the insurer limit "
                      "and the capacity offered. Edit it freely — it is only a starting point."):
        _rows, _remaining = [], dict(bom_totals)
        # lump-sum (charter) offers are left out of the draft — a charter is a decision for the whole parcel
        _elig = sorted([r for r in sail_results if r["eligible"] and r["price_basis"] != "Lump sum"],
                       key=lambda r: r["cost_usd"].get("BESS", 0))
        for r in _elig:
            room = r["Capacity"] or 0
            for t in sorted(_remaining, key=lambda x: x != "BESS"):
                if room <= 0 or _remaining[t] <= 0:
                    continue
                q = min(_remaining[t], room)
                if t == "BESS" and max_bess_per_vessel:
                    q = min(q, max_bess_per_vessel)
                if q > 0:
                    _rows.append({"Option": r["Option"], "Equipment": t, "Requested": int(q), "Confirmed": None,
                                  "Status": "Requested", "Port Days": 3})
                    _remaining[t] -= q
                    room -= q
        st.session_state.plan_df = pd.DataFrame(_rows, columns=["Option", "Equipment", "Requested", "Confirmed", "Status", "Port Days"])
        st.session_state.pop("plan_editor", None)
        st.rerun()

    plan_edit = st.data_editor(
        st.session_state.plan_df, key="plan_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config={
            "Option": st.column_config.SelectboxColumn("Option", options=list(_sail_by_opt.keys()), required=True),
            "Equipment": st.column_config.SelectboxColumn("Equipment", options=_bom_types or EQUIPMENT_TYPES, required=True),
            "Requested": st.column_config.NumberColumn("Requested", min_value=0, step=1),
            "Confirmed": st.column_config.NumberColumn("Confirmed", min_value=0, step=1,
                                                       help="Quantity confirmed by the carrier (or contracted on MPP / charter)"),
            "Status": st.column_config.SelectboxColumn("Status", options=PLAN_STATUSES, required=True),
            "Port Days": st.column_config.NumberColumn("Port Days", min_value=0, step=1,
                                                       help="Planned days in the port of discharge before pick-up"),
        },
    )

    _rows_by_opt_plan = {str(x.get("Option")): x for _, x in sail_edit.iterrows()}
    # ---- effective quantities
    plan_lines = []
    for _, r in plan_edit.iterrows():
        opt = r.get("Option")
        if opt not in _sail_by_opt:
            continue
        req = int(_num(r.get("Requested")))
        conf_raw = pd.to_numeric(r.get("Confirmed"), errors="coerce")
        status = r.get("Status") if r.get("Status") in PLAN_STATUSES else "Requested"
        if status in ("Rolled", "Cancelled"):
            eff = 0
        elif status in ("Confirmed", "Reduced") and not pd.isna(conf_raw):
            eff = int(conf_raw)
        else:
            eff = req
        plan_lines.append({"Option": opt, "Equipment": r.get("Equipment"), "Requested": req,
                           "Confirmed": None if pd.isna(conf_raw) else int(conf_raw), "Status": status,
                           "Effective": eff, "Port Days": int(_num(r.get("Port Days"), default=3))})

    if plan_lines:
        st.markdown("#### Plan Check")
        problems, warnings_, infos_ = [], [], []

        # 1. coverage
        eff_by_type = {}
        for l in plan_lines:
            eff_by_type[l["Equipment"]] = eff_by_type.get(l["Equipment"], 0) + l["Effective"]
        cov_rows = []
        for t in sorted(set(bom_totals) | set(eff_by_type)):
            need, have = bom_totals.get(t, 0), eff_by_type.get(t, 0)
            cov_rows.append({"Equipment": t, "In BOM": need, "On vessels (effective)": have,
                             "Without a vessel": max(0, need - have), "Over-allocated": max(0, have - need)})
            if have < need:
                problems.append(f"{need - have} {t} unit(s) have no vessel yet")
            elif have > need:
                warnings_.append(f"{have - need} {t} unit(s) more than in the BOM")

        # 2. per vessel: insurer limit, capacity, eligibility, carrier changes, arrival
        by_opt = {}
        for l in plan_lines:
            by_opt.setdefault(l["Option"], []).append(l)
        vessel_rows = []
        for opt, ls in by_opt.items():
            s_ = _sail_by_opt[opt]
            bess = sum(l["Effective"] for l in ls if l["Equipment"] == "BESS")
            tot = sum(l["Effective"] for l in ls)
            req_tot = sum(l["Requested"] for l in ls)
            pdays = max(l["Port Days"] for l in ls)
            cost = sum(l["Effective"] * s_["cost_usd"].get(l["Equipment"], 0) for l in ls)
            _srow = _rows_by_opt_plan.get(opt)
            _ls_flag = False
            if s_["price_basis"] == "Lump sum" and _srow is not None and tot > 0:
                # the lump sum is due in full whatever the quantity loaded
                _ls_usd = _num(_srow.get("Lump Sum")) * _fx_usd(_srow)
                _per_unit_ls = offer_freight(_srow, "20ft") * _fx_usd(_srow)
                cost = cost - tot * _per_unit_ls + _ls_usd
                _ls_flag = True
            notes = ["ℹ️ lump sum in full"] if _ls_flag else []
            if not s_["eligible"]:
                problems.append(f"{opt}: sailing does not meet the Project Brief ({s_['Issues']})")
                notes.append("❌ not eligible")
            if max_bess_per_vessel and bess > max_bess_per_vessel:
                problems.append(f"{opt}: {bess} BESS > insurer limit {max_bess_per_vessel}")
                notes.append("❌ insurer limit")
            if s_["Capacity"] and tot > s_["Capacity"]:
                problems.append(f"{opt}: {tot} units > capacity offered {s_['Capacity']}")
                notes.append("❌ capacity")
            for l in ls:
                if l["Status"] in ("Reduced", "Rolled", "Cancelled") and l["Requested"] > l["Effective"]:
                    warnings_.append(f"{opt}: carrier {l['Status'].lower()} {l['Equipment']} by {l['Requested'] - l['Effective']} "
                                     "— re-allocate to another eligible sailing")
            if any(l["Status"] == "Requested" for l in ls):
                infos_.append(f"{opt}: awaiting carrier confirmation")
            pod = s_["POD"]
            if pod in port_dwell_cap and pdays > port_dwell_cap[pod]:
                problems.append(f"{opt}: {pdays} port days > max DG dwell {port_dwell_cap[pod]} at {pod.split(',')[0]}")
            on_site = (s_["ETA"] + timedelta(days=pdays + 2)) if s_["ETA"] else None
            if on_site and on_site > delivery_date:
                warnings_.append(f"{opt}: on site ≈ {on_site.strftime('%d/%m/%Y')}, after the required date")
            vessel_rows.append({"Option": opt, "Carrier": s_["Carrier"], "Vessel": s_["Vessel"], "Type": s_["Type"],
                                "POD": pod.split(",")[0], "ETA": s_["ETA"].strftime("%d/%m/%Y") if s_["ETA"] else "",
                                "BESS": bess, "All units": tot, "Requested": req_tot,
                                "Est. ocean + local cost": f"{_sym} {cost * _mult:,.0f}",
                                "Flags": " ".join(notes) or "✅"})

        # 3. port limit over time (BESS present in each port group per day)
        peak_rows = []
        for g, cap in group_cap.items():
            daily = {}
            for opt, ls in by_opt.items():
                s_ = _sail_by_opt[opt]
                if not s_["ETA"] or port_group_of.get(s_["POD"]) != g:
                    continue
                bess = sum(l["Effective"] for l in ls if l["Equipment"] == "BESS")
                pdays = max(1, max(l["Port Days"] for l in ls))
                for k in range(pdays):
                    d = s_["ETA"] + timedelta(days=k)
                    daily[d] = daily.get(d, 0) + bess
            if daily:
                peak_day = max(daily, key=daily.get)
                peak = daily[peak_day]
                peak_rows.append({"Limit Group": g, "Limit": f"{cap}" + (" (temporary)" if group_temp.get(g) else ""),
                                  "Peak BESS in port": peak, "Peak date": peak_day.strftime("%d/%m/%Y"),
                                  "OK": "✅" if peak <= cap else ("⚠️" if group_temp.get(g) else "❌")})
                if peak > cap:
                    (warnings_ if group_temp.get(g) else problems).append(f"Port limit {g}: {peak} BESS in port on {peak_day.strftime('%d/%m/%Y')} > limit {cap} "
                                    "— spread the arrivals, shorten port days or use another port")

        st.dataframe(pd.DataFrame(vessel_rows), use_container_width=True, hide_index=True)
        cc1, cc2 = st.columns([3, 2])
        with cc1:
            st.dataframe(pd.DataFrame(cov_rows), use_container_width=True, hide_index=True)
        with cc2:
            if peak_rows:
                st.dataframe(pd.DataFrame(peak_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No port limits set for the ports in this plan.")

        if problems:
            st.error("**Plan not feasible yet:**\n\n" + "\n".join(f"* {p}" for p in problems))
        if warnings_:
            st.warning("\n".join(f"* {w}" for w in warnings_))
        if infos_:
            st.info("\n".join(f"* {i}" for i in infos_))
        if not problems and not warnings_:
            st.success("✅ Plan meets the Project Brief, the insurer limit, capacity and port limits.")

        if st.button("➡️ Send this plan to the Multi-Shipment Planner",
                     help="Creates one shipment per vessel with the effective quantities and the sailing's rates."):
            st.session_state["_plan_to_msp"] = {"lines": plan_lines, "sailings": _df_records(sail_edit)}
            st.success("Plan sent — open the Multi-Shipment Planner tab to see the full landed cost.")
