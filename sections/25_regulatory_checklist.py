# Terra Vol Global — section 25_regulatory_checklist: Tab: Regulatory Checklist.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
with tab6:
    st.subheader(f"✅ Regulatory & Compliance Checklist — {destination_country}")
    st.markdown(
        "What must be in place to ship BESS from China to the site, **who is responsible** and **when**. "
        "Update the status as the project moves — the checklist is saved in the project file."
    )

    # (requirement, authority / rule, responsible party, stage, indicative lead time)
    REQ_COMMON = [
        ("UN38.3 test summary for each battery type", "UN Manual of Tests & Criteria (transport of lithium batteries)",
         "Manufacturer", "Before booking", "Existing test report"),
        ("Safety Data Sheet (SDS / MSDS)", "IMDG Code / carrier DG desk", "Manufacturer", "Before booking", "Existing document"),
        ("Dangerous-goods declaration — Class 9, UN3536 (batteries installed in cargo transport unit)",
         "IMDG Code", "Manufacturer / Forwarder", "Booking", "1–3 days"),
        ("Carrier DG acceptance & port of discharge DG approval", "Shipping line DG desk / destination terminal",
         "Forwarder", "Before booking", "1–2 weeks"),
        ("Container / SOC certificates (CSC plate, survey) for shipper-owned boxes", "CSC Convention",
         "Manufacturer", "Before stuffing", "Existing"),
        ("Commercial invoice, packing list, bill of lading, certificate of origin, insurance certificate",
         "Customs / bank / buyer", "Manufacturer / Forwarder", "At shipment", "At sailing"),
        ("Customs import declaration & HS classification (8507.60 Li-ion; 8504 transformers)",
         "Destination customs", "Importer / Customs broker", "On arrival", "1–5 days"),
        ("Oversize / heavy transport permit for port-to-site haul", "National road authority",
         "Haulier / Forwarder", "Before arrival", "1–4 weeks"),
        ("Site readiness: access road, crane, foundations, unloading plan", "EPC method statement",
         "EPC / Developer", "Before delivery", "Project plan"),
    ]
    REQ_EU = [
        ("EORI number of the importer", "EU Customs Code", "Importer", "Before import", "1–5 days"),
        ("CE marking & EU Declaration of Conformity (LVD, EMC) for BESS / PCS", "EU product legislation",
         "Manufacturer", "Before placing on market", "Existing"),
        ("EU Battery Regulation 2023/1542 — producer / EPR registration in the member state", "Regulation (EU) 2023/1542",
         "Manufacturer / Importer", "Before placing on market", "2–8 weeks"),
        ("EU Battery Passport for industrial batteries > 2 kWh (applies from 18 Feb 2027)", "Regulation (EU) 2023/1542",
         "Manufacturer", "Before placing on market", "Plan ahead"),
        ("ADR dangerous-goods rules for road transport (Class 9)", "ADR", "Haulier", "Inland transport", "Driver / vehicle compliance"),
    ]
    REQ_IL = [
        ("Toxins Permit — importer / consignee", "Ministry of Environmental Protection (Hazardous Substances Law)",
         "Importer", "Before release from port / external storage", "Weeks–months"),
        ("Toxins Permit — project site", "Ministry of Environmental Protection (Hazardous Substances Law)",
         "Developer / Site operator", "Before delivery to site", "Weeks–months"),
        ("Ministry of Transport transport permit — one per BESS container", "Israel Ministry of Transport",
         "Haulier / Forwarder", "Before port-to-site haul", "Apply early"),
        ("Battery / e-waste recycling body arrangement — check applicability", "Israeli e-waste & batteries law",
         "Importer", "Before placing on market", "2–6 weeks"),
    ]
    _reqs = REQ_COMMON + (REQ_IL if is_israel else REQ_EU)
    _saved_status = st.session_state.get("_reg_status", {})

    def _default_status(req):
        if req in _saved_status:
            return _saved_status[req].get("Status", "Not started")
        if is_israel and req.startswith("Toxins Permit — importer"):
            return "Done" if has_importer_permit else "Not started"
        if is_israel and req.startswith("Toxins Permit — project site"):
            return "Done" if has_site_permit else "Not started"
        return "Not started"

    reg_df = pd.DataFrame([
        {"Requirement": r, "Authority / Rule": a, "Responsible": who, "When": when, "Lead Time (indicative)": lt,
         "Status": _default_status(r), "Notes": _saved_status.get(r, {}).get("Notes", "")}
        for r, a, who, when, lt in _reqs
    ])
    reg_edit = st.data_editor(
        reg_df, key=f"reg_checklist_{destination_country}", hide_index=True, use_container_width=True,
        disabled=["Requirement", "Authority / Rule", "Responsible", "When", "Lead Time (indicative)"],
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status", options=["Not started", "In progress", "Done", "Not applicable"], required=True),
            "Notes": st.column_config.TextColumn("Notes"),
        },
    )
    reg_status_now = {row["Requirement"]: {"Status": row["Status"], "Notes": row["Notes"] or ""}
                      for _, row in reg_edit.iterrows()}

    _open = reg_edit[~reg_edit["Status"].isin(["Done", "Not applicable"])]
    c_done, c_open = st.columns(2)
    c_done.metric("Completed", f"{len(reg_edit) - len(_open)} / {len(reg_edit)}")
    c_open.metric("Open items", len(_open))
    if len(_open):
        by_party = _open.groupby("Responsible")["Requirement"].count().sort_values(ascending=False)
        st.markdown("**Open items by responsible party:** " +
                    " · ".join(f"{party}: {n}" for party, n in by_party.items()))
    st.caption("Indicative checklist for planning — confirm the exact requirements with the authorities, "
               "your customs broker and the carrier for each project.")
