# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 31_permits_documents: Tab: Permits & Documents.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# ---------------------------------------------------------------------------
# PERMITS & DOCUMENTS — per-unit road-transport permits and document packages
# ---------------------------------------------------------------------------
# Country templates. Indicative — confirm with the authority / haulier for each project.
EU_PERMIT_AUTHORITY = {
    "Germany": "VEMAGS online system — state road authority (Großraum- und Schwertransport permit)",
    "Romania": "CNAIR — special transport authorisation for abnormal loads (confirm)",
    "Italy": "Exceptional transport authorisation — ANAS / region / province depending on the route",
    "Netherlands": "RDW — exemption (ontheffing) for abnormal transport",
    "France": "Préfecture — exceptional transport permit (TESEO online)",
    "Poland": "GDDKiA / district authority — abnormal vehicle permit (category by weight)",
    "Spain": "DGT — complementary traffic authorisation",
    "Bulgaria": "Road Infrastructure Agency — abnormal load permit (confirm)",
}
PERMIT_TEMPLATES = {
    "Israel": {
        "permit": "Ministry of Transport transport permit (one request per BESS unit)",
        "opened_by": "Haulier (opens the online request; a request number is issued)",
        "lead_days": 21,
        "fixed_docs": [
            ("Manufacturer SDS / MSDS", "Manufacturer"),
            ("Transport & emergency response instructions", "Manufacturer"),
            ("Declaration that the system is integral and cannot be dismantled", "Manufacturer"),
            ("Technical specification & manufacturer instructions for the model", "Manufacturer"),
            ("Transport configuration signed by an engineer (per trailer)", "Haulier / Engineer"),
            ("Haulier licence for dangerous goods transport", "Haulier"),
            ("Driver licences & permits", "Haulier"),
            ("Police permit (only if required by the transport configuration)", "Haulier"),
        ],
        "unique_docs": ["Importer letter describing the transport", "MoT application form",
                        "Container & serial numbers", "Bill of lading showing the model",
                        "Packing list & supplier invoice", "Transport safety officer declaration incl. route"],
    },
    "EU": {
        "permit": "National abnormal-load road permit (per transport / route)",
        "opened_by": "Haulier (applies to the national authority of each country crossed)",
        "lead_days": 28,
        "fixed_docs": [
            ("Safety Data Sheet (SDS)", "Manufacturer"),
            ("UN38.3 test summary", "Manufacturer"),
            ("Indivisibility declaration (load cannot be dismantled)", "Manufacturer"),
            ("Technical specification, lifting & transport instructions", "Manufacturer"),
            ("Vehicle combination data — registration, axle loads, dimensions", "Haulier"),
            ("ADR driver training certificates", "Haulier"),
            ("ADR vehicle equipment & orange plates / Class 9 marking", "Haulier"),
            ("Haulier liability insurance", "Haulier"),
        ],
        "unique_docs": ["Permit application form", "Route plan incl. bridges / restrictions",
                        "Load data (weight, dimensions, centre of gravity)", "ADR transport document",
                        "Escort booking (if required by the permit)", "Container & serial numbers"],
    },
}
PERMIT_STATUSES = ["Not opened", "Opened", "Documents sent", "Approved", "Rejected"]

with tab_permits:
    tmpl_key = "Israel" if is_israel else "EU"
    tmpl = PERMIT_TEMPLATES[tmpl_key]
    st.subheader(f"🛂 Permits & Documents — {destination_country}")
    _auth = tmpl["permit"] if is_israel else EU_PERMIT_AUTHORITY.get(destination_country, "National road authority — abnormal load permit (confirm)")
    st.markdown(f"**Permit:** {tmpl['permit']}  \n**Authority:** {_auth}  \n**Opened by:** {tmpl['opened_by']}  \n"
                f"**Indicative lead time:** ~{tmpl['lead_days']} days")
    if not is_israel:
        st.caption("EU: road transport of BESS falls under ADR (Class 9, UN3536 — from 2027 lithium-metal and sodium-ion "
                   "units get their own UN numbers). A 42 t+ box on a truck exceeds the 40 t (44 t intermodal) limit, so an "
                   "abnormal-load permit is needed in every country crossed — each country issues its own permit.")

    # ---------------- 1. Fixed document library ----------------
    st.markdown("#### 1. Fixed Documents — reused in every request")
    st.caption("Keep one set per manufacturer / importer / haulier. Add where the file is kept (link) and its expiry date.")
    _lib_key = f"doclib_{tmpl_key}"
    if _lib_key not in st.session_state:
        st.session_state[_lib_key] = pd.DataFrame([
            {"Document": d, "Provided by": who, "Company": "", "Link / Location": "", "Valid Until": None, "Have it": False}
            for d, who in tmpl["fixed_docs"]])
    lib_edit = st.data_editor(
        st.session_state[_lib_key], key=f"{_lib_key}_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config={"Valid Until": st.column_config.DateColumn("Valid Until", format="DD/MM/YYYY"),
                       "Have it": st.column_config.CheckboxColumn("Have it")},
    )

    # ---------------- 2. Permit requests per unit ----------------
    st.markdown("#### 2. Permit Requests — one row per unit")
    _site = site_address if "site_address" in globals() else ""
    _units_from_plan = []
    for l in (plan_lines or []):
        _abn = any(b["Type"] == l["Equipment"] and "Abnormal road load" in b["Checks"] for b in bom_rows)
        if l["Effective"] > 0 and (_abn or (is_israel and l["Equipment"] == "BESS")):
            s_ = _sail_by_opt.get(l["Option"])
            for _ in range(l["Effective"]):
                _units_from_plan.append((l["Option"], l["Equipment"], s_))
    _src = "allocation plan" if _units_from_plan else "BOM"
    if not _units_from_plan:
        for b in bom_rows:
            if "Abnormal road load" in b["Checks"] or (is_israel and b["Type"] == "BESS"):
                for _ in range(b["Qty"]):
                    _units_from_plan.append(("", b["Type"], None))

    _req_key = f"permit_req_{tmpl_key}"
    _sig = f"{len(_units_from_plan)}-" + "-".join(sorted({u[0] for u in _units_from_plan}))
    if st.button(f"🔄 Build request list from the {_src} ({len(_units_from_plan)} units)") or _req_key not in st.session_state:
        rows = []
        for i, (opt, typ, s_) in enumerate(_units_from_plan, 1):
            eta = s_["ETA"] if s_ else None
            rows.append(dict({"Unit": f"{typ}-{i:03d}", "Vessel": f"{opt} {s_['Vessel']}" if s_ else "",
                              "POD": s_["POD"].split(",")[0] if s_ else "", "ETA": eta, "B/L No.": "", "Container No.": "",
                              "Serial No.": "", "Request No.": "", "Route / Stops": f"{s_['POD'].split(',')[0] if s_ else 'Port'} → {_site}",
                              "Status": "Not opened"}, **{d: False for d in tmpl["unique_docs"]}))
        st.session_state[_req_key] = pd.DataFrame(rows)
        st.session_state.pop(f"{_req_key}_editor", None)
    st.caption("Fill B/L, container and serial numbers as they become known, the request number once the haulier opens the "
               "request, and tick the unique documents sent. Rebuild only when the plan changes (it resets the table).")
    req_edit = st.data_editor(
        st.session_state[_req_key], key=f"{_req_key}_editor", hide_index=True, use_container_width=True, num_rows="dynamic",
        column_config=dict({"ETA": st.column_config.DateColumn("ETA", format="DD/MM/YYYY"),
                            "Status": st.column_config.SelectboxColumn("Status", options=PERMIT_STATUSES, required=True)},
                           **{d: st.column_config.CheckboxColumn(d) for d in tmpl["unique_docs"]}),
    )

    # ---------------- 3. Dashboard ----------------
    st.markdown("#### 3. Readiness by Vessel")
    _today = date.today()
    _lib_missing, _lib_expiring = [], []
    _last_eta = max([_d(x) for x in req_edit["ETA"] if _d(x)] or [None]) if len(req_edit) else None
    for _, d in lib_edit.iterrows():
        if not bool(d.get("Have it")):
            _lib_missing.append(d.get("Document"))
        vu = _d(d.get("Valid Until"))
        if vu and (vu < _today or (_last_eta and vu < _last_eta)):
            _lib_expiring.append(f"{d.get('Document')} (valid until {vu.strftime('%d/%m/%Y')})")
    dash = []
    for vessel, grp in req_edit.groupby("Vessel", dropna=False):
        etas = [_d(x) for x in grp["ETA"] if _d(x)]
        eta = min(etas) if etas else None
        approved = int((grp["Status"] == "Approved").sum())
        opened = int(grp["Request No."].astype(str).str.strip().replace("nan", "").ne("").sum())
        docs_done = int(grp[tmpl["unique_docs"]].all(axis=1).sum()) if len(grp) else 0
        days_left = (eta - _today).days if eta else None
        if approved == len(grp):
            flag = "✅ All approved"
        elif days_left is not None and days_left <= tmpl["lead_days"]:
            flag = f"🔴 ETA in {days_left} d — {len(grp) - approved} not approved"
        elif days_left is not None and days_left <= tmpl["lead_days"] * 2:
            flag = "🟠 Start now"
        else:
            flag = "⏳ On track"
        dash.append({"Vessel": vessel or "(no vessel)", "ETA": eta.strftime("%d/%m/%Y") if eta else "", "Units": len(grp),
                     "Requests opened": opened, "Unique docs complete": docs_done, "Approved": approved,
                     "Days to ETA": days_left if days_left is not None else "", "Status": flag})
    if dash:
        st.dataframe(pd.DataFrame(dash), use_container_width=True, hide_index=True)
    if is_israel or any(group_cap.values()):
        st.caption("Permits must be in hand **before the ETA** — several ports require BESS to leave the port right after discharge.")
    if _lib_missing:
        st.warning("Fixed documents missing: " + ", ".join(_lib_missing))
    if _lib_expiring:
        st.error("Fixed documents expired or expiring before the last ETA: " + ", ".join(_lib_expiring))

    # ---------------- 4. Document package text ----------------
    st.markdown("#### 4. Document Package for a Request")
    _req_nos = [str(x).strip() for x in req_edit["Request No."] if str(x).strip() not in ("", "nan", "None")]
    if not _req_nos:
        st.info("Enter a request number in the table above to generate its document package.")
    else:
        pk1, pk2 = st.columns([2, 1])
        with pk1:
            sel_req = st.selectbox("Request:", _req_nos, key="pkg_request")
        with pk2:
            pkg_lang = st.selectbox("Language:", ["Hebrew", "English"] if is_israel else ["English"], key="pkg_lang")
        rr = req_edit[req_edit["Request No."].astype(str).str.strip() == sel_req].iloc[0]
        _importer = next((str(x.get("Company")) for _, x in lib_edit.iterrows()
                          if "Manufacturer" not in str(x.get("Provided by")) and str(x.get("Company")) not in ("", "nan")), "")
        _maker = next((str(x.get("Company")) for _, x in lib_edit.iterrows()
                       if str(x.get("Provided by")) == "Manufacturer" and str(x.get("Company")) not in ("", "nan")), "")
        route = str(rr.get("Route / Stops") or "")
        fixed = [str(d.get("Document")) for _, d in lib_edit.iterrows()]
        unique = tmpl["unique_docs"]
        if pkg_lang == "Hebrew":
            HE_FIXED = {
                "Manufacturer SDS / MSDS": "גיליון MSDS של היצרן",
                "Transport & emergency response instructions": "הוראות שינוע ותגובה בחירום",
                "Declaration that the system is integral and cannot be dismantled": "הצהרה שהמערכת אחודה ואינטגרלית ואינה ניתנת לפירוק",
                "Technical specification & manufacturer instructions for the model": "מפרט טכני והוראות יצרן לדגם",
                "Transport configuration signed by an engineer (per trailer)": "תצורת שינוע חתומה על ידי מהנדס, לכל עגלה",
                "Haulier licence for dangerous goods transport": "רישיון מוביל להובלת חומרים מסוכנים",
                "Driver licences & permits": "רישיונות והיתרים של הנהגים",
                "Police permit (only if required by the transport configuration)": "היתר משטרה (אם נדרש בתצורת ההובלה)",
            }
            HE_UNIQUE = {
                "Importer letter describing the transport": "מכתב היבואן המתאר את ההובלה המבוקשת",
                "MoT application form": "טופס הפנייה ומסמכי הבקשה למשרד התחבורה",
                "Container & serial numbers": "מספרי המכולות והמספרים הסידוריים של המערכת",
                "Bill of lading showing the model": "שטר מטען שבו מצוין דגם המערכת",
                "Packing list & supplier invoice": "רשימת אריזה וחשבון ספק",
                "Transport safety officer declaration incl. route": "הצהרת קצין הבטיחות בתעבורה, כולל תיאור מסלול הנסיעה",
            }
            lines = [f"שלום רב,", "",
                     f"מצורפים המסמכים לבקשה מס' {sel_req} במערכת משרד התחבורה.",
                     f"הבקשה היא לשינוע יחידת אגירה {rr.get('Unit')}"
                     + (f" של היצרן {_maker}" if _maker else "") + (f" עבור {_importer}" if _importer else "")
                     + f", במסלול: {route}.", "",
                     "א. מסמכים קבועים, זהים בכל הבקשות:"]
            lines += [f"{i}. {HE_FIXED.get(d, d)}" for i, d in enumerate(fixed, 1)]
            lines += ["", f"ב. מסמכים ייחודיים לבקשה מס' {sel_req}:"]
            lines += [f"{i}. {HE_UNIQUE.get(d, d)}" for i, d in enumerate(unique, 1)]
            lines += ["", f"מכולה: {rr.get('Container No.') or '—'} | מס' סידורי: {rr.get('Serial No.') or '—'} | "
                          f"שטר מטען: {rr.get('B/L No.') or '—'}"]
            if _d(rr.get("ETA")):
                lines += ["", f"האונייה צפויה להגיע ב-{_d(rr.get('ETA')).strftime('%d/%m/%Y')}; נבקש שאישור ההובלה יהיה בידינו לפני כן."]
            lines += ["", "תודה רבה,"]
        else:
            lines = ["Dear Sir / Madam,", "",
                     f"Please find attached the documents for permit request no. {sel_req}.",
                     f"The request covers the transport of unit {rr.get('Unit')}" + (f" made by {_maker}" if _maker else "")
                     + (f" for {_importer}" if _importer else "") + f", route: {route}.", "",
                     "A. Fixed documents (identical for all requests):"]
            lines += [f"{i}. {d}" for i, d in enumerate(fixed, 1)]
            lines += ["", f"B. Documents specific to request no. {sel_req}:"]
            lines += [f"{i}. {d}" for i, d in enumerate(unique, 1)]
            lines += ["", f"Container: {rr.get('Container No.') or '—'} | Serial no.: {rr.get('Serial No.') or '—'} | "
                          f"B/L: {rr.get('B/L No.') or '—'}"]
            if _d(rr.get("ETA")):
                lines += ["", f"The vessel is expected on {_d(rr.get('ETA')).strftime('%d/%m/%Y')}; we kindly ask to receive "
                              "the permit before that date."]
            lines += ["", "Kind regards,"]
        _missing_u = [d for d in unique if not bool(rr.get(d))]
        if _missing_u:
            st.warning("Not yet ticked as ready for this request: " + ", ".join(_missing_u))
        st.text_area("Email text (copy):", value="\n".join(lines), height=360, key=f"pkg_text_{sel_req}_{pkg_lang}")
