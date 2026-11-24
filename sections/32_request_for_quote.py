# Terra Vol Global — section 32_request_for_quote: Tab: Request for Quote.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
# ---------------------------------------------------------------------------
# REQUEST FOR QUOTATION — generated from the Project Brief
# ---------------------------------------------------------------------------
with tab_rfq:
    st.subheader("📨 Request for Quotation (RFQ)")
    st.markdown("Generates the RFQ email from the Project Brief and a **response template** for forwarders / carriers. "
                "Filled templates are imported in **Offers Received** with one click, so every offer arrives in the same "
                "structure and the comparison is automatic.")

    r1, r2, r3 = st.columns(3)
    with r1:
        rfq_pol = ui.selectbox("Port of loading:", ["Shanghai", "Ningbo-Zhoushan", "Qingdao", "Shenzhen - Yantian",
                                                    "Shenzhen - Shekou", "Guangzhou - Nansha", "Xingang / Tianjin", "Other"])
        rfq_incoterm = ui.selectbox("Sales terms:", ["FOB", "FCA", "EXW", "CFR", "CIF", "DAP"], index=0)
    with r2:
        rfq_deadline = ui.date_input("Reply by:", value=date.today() + timedelta(days=7))
        rfq_company = ui.text_input("Requesting company:", value="")
    with r3:
        rfq_contact = ui.text_input("Contact name / email:", value="")
        rfq_ref = ui.text_input("RFQ reference:", value=f"RFQ-{date.today().strftime('%Y%m%d')}")
    o1, o2, o3 = st.columns(3)
    with o1:
        rfq_charter_ok = ui.checkbox("Invite part / full charter alternatives", value=True)
    with o2:
        rfq_experience = ui.checkbox("Ask for references of similar heavy Class 9 SOC shipments", value=True)
    with o3:
        rfq_separate = ui.checkbox("Ask for a separate offer per vessel / batch", value=bool(req_split_quotes))

    _pods_txt = " / ".join(p.split(",")[0] + ("" if "," not in p else f" ({p.split(',')[-1].strip()})") for p in brief_pods) \
        or "to be advised"
    _bess_n = bom_totals.get("BESS", 0)
    L = [f"Subject: {rfq_ref} — Ocean transport of {sum(bom_totals.values())} units BESS project cargo — "
         f"{rfq_pol} to {_pods_txt}", "",
         "Dear Sir / Madam,", "",
         f"We are pleased to request your best offer for the ocean transport of the following project cargo"
         + (f" for {project_name}" if project_name else "") + ".", "",
         "CARGO DETAILS"]
    for _, b in bom_edit.iterrows():
        q_ = int(_num(b.get("Qty")))
        if q_ <= 0:
            continue
        dg_ = str(b.get("DG Class") or "").replace("nan", "").strip()
        dims = " x ".join(str(int(_num(b.get(c)))) for c in ("L (mm)", "W (mm)", "H (mm)") if _num(b.get(c)))
        L.append(f"- {b.get('Item')} ({b.get('Model')}): {q_} units, {b.get('Container')}"
                 f"{' SOC' if bool(b.get('SOC')) else ''}" + (f", {dims} mm" if dims else "")
                 + f", approx. {_num(b.get('Gross Weight (t)')):g} t gross each"
                 + (f", {dg_}" if dg_ else ", non-DG"))
    L.append(f"- Total: {sum(bom_totals.values())} units, approx. {total_weight_t:,.0f} t, {total_teu_bom:g} TEU")
    if any("Dangerous goods" in b["Checks"] for b in bom_rows):
        L.append("- SDS / MSDS and UN38.3 test summary attached.")
    if any("DG classification not final" in b["Checks"] for b in bom_rows):
        L.append("- The UN number is still to be confirmed by the manufacturer — please quote for both options if relevant.")
    L += ["", "ROUTING & DATES",
          f"- Port of loading: {rfq_pol}, China ({rfq_incoterm})",
          f"- Port(s) of discharge: {_pods_txt}" + (" — please quote each port separately" if len(brief_pods) > 1 else ""),
          f"- Cargo ready (EXW): {brief_exw_ready.strftime('%d/%m/%Y')} · at port / FOB: {brief_fob_date.strftime('%d/%m/%Y')}",
          f"- Latest departure from China: {brief_must_sail_by.strftime('%d/%m/%Y')}",
          f"- Required on site: {delivery_date.strftime('%d/%m/%Y')}", "",
          "MANDATORY REQUIREMENTS"]
    _n = 1
    if req_direct_only:
        L.append(f"{_n}. Direct sailing without transshipment — no discharge or reloading onto another vessel at any stage. "
                 "Please confirm in writing."); _n += 1
    if req_no_red_sea:
        L.append(f"{_n}. No transit of the Red Sea (Bab el-Mandeb / Suez Canal). Please state the full routing."); _n += 1
    if max_bess_per_vessel and _bess_n > max_bess_per_vessel:
        L.append(f"{_n}. Maximum {max_bess_per_vessel} BESS units per vessel (insurer limit) — at least {min_vessels} vessels."); _n += 1
    if rfq_separate:
        L.append(f"{_n}. A separate offer per vessel / batch."); _n += 1
    if special_handling:
        L.append(f"{_n}. Handling per the manufacturer's instructions: {special_handling.strip()}"); _n += 1
    if insurance_by_client:
        L.append(f"{_n}. Marine insurance is arranged by us — not to be included."); _n += 1
    for p_, g_ in port_group_of.items():
        if g_ in group_cap and p_ in brief_pods:
            L.append(f"{_n}. {p_.split(',')[0]}: max {group_cap[g_]} BESS in port at once — please consider when "
                     "proposing sailings."); _n += 1
    L += ["", "PLEASE QUOTE (one line per vessel / sailing in the attached response template)",
          "1. Freight rate per unit and / or lump sum, with your terms (Liner terms / FIO / FILO / LIFO).",
          "2. Vessel name and type, ETD and ETA, transit time and full routing; confirmation of direct sailing.",
          "3. Confirmation of DG acceptance, proposed stowage (on / under deck) and segregation.",
          "4. Lashing and securing arrangements, including any hot work for D-rings, and who is responsible.",
          "5. Terminal and DG handling at the port of loading (incl. DG yard) and the discharge terminal.",
          "6. All surcharges itemised (BAF, EFS, DG, heavy-lift / overweight, war risk, other) and local charges at "
          "origin and destination.",
          "7. Free time at the port of discharge and offer validity."]
    if rfq_experience:
        L.append("8. References of similar shipments you performed (Class 9, 40 t+ in 20ft SOC, direct sailing), with a contact.")
    if rfq_charter_ok:
        L += ["", "If you can offer a part or full charter instead of a liner parcel, please include it as an alternative."]
    L += ["", f"Please reply by {rfq_deadline.strftime('%d/%m/%Y')}, using the attached response template.", "",
          "Best regards,", rfq_contact or "", rfq_company or ""]
    rfq_text = "\n".join(L).rstrip() + "\n"

    st.text_area("RFQ email (edit and copy):", value=rfq_text, height=520, key=f"rfq_text_{hash(rfq_text)}")
    instructions = [
        "Fill one row per vessel / sailing on the 'Offer' sheet, starting in row 3 (row 2 shows what each column expects).",
        "Charges per unit (one container / one piece): enter the amount; 0 = included in the freight; leave empty only if "
        "the charge does not apply.",
        "BAF per TEU (20ft = 1 TEU, 40ft = 2 TEU). For lump-sum offers fill 'Lump Sum' and 'Lump Sum Units'.",
        "Dates as dd/mm/yyyy. Use the drop-down lists where offered.",
        f"Reply by {rfq_deadline.strftime('%d/%m/%Y')}.",
    ]
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("⬇️ RFQ email (.txt)", data=rfq_text.encode("utf-8"), file_name=f"{rfq_ref}.txt", mime="text/plain")
    with d2:
        st.download_button("⬇️ Response template (Excel) — attach to the RFQ",
                           data=_rfq_mod.build_response_template(project_name, rfq_ref, brief_pods, instructions),
                           file_name=f"{rfq_ref}_Offer_Response.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("When a forwarder returns the template, import it in the Offers Received tab.")
