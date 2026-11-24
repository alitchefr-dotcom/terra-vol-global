# Terra Vol Global — section 21_supply_chain: Tab: Supply Chain & Incoterms.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
with tab2:
    st.subheader("Ocean Freight, BAF & Destination THC")
    
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        shipping_line = ui.selectbox("Shipping Line / Carrier:", CARRIERS)
        origin_port = ui.selectbox("Origin Port (China):", [
            "Shanghai, China - SIPG (Waigaoqiao / Yangshan)",
            "Ningbo-Zhoushan, China - Beilun Terminal",
            "Qingdao, China - Qianwan Terminal",
            "Shenzhen, China - Yantian International Container Terminal (YICT)",
            "Shenzhen, China - Shekou Container Terminal (SCT)",
            "Guangzhou, China - Nansha Port"
        ])
    with col_sc2:
        dest_port = ui.selectbox(f"Selected Port of Destination (POD) for {destination_country}:", options=destination_ports, index=0)
        incoterm_code = ui.selectbox("Incoterm:", options=["EXW", "FOB", "CFR", "CIF", "DAP", "DDP"], index=3)

    st.markdown("---")
    st.markdown(f"#### 1. Ocean Freight per Unit ({curr_code})")
    f_mult = usd_to_eur if is_eur_display else 1.0
    cf1, cf2, cf3 = st.columns(3)
    with cf1:
        f_bess = ui.number_input(f"BESS Freight ({curr_code}):", min_value=0, value=int(18000 * f_mult), step=500)
        f_oog = ui.number_input(f"OOG Freight ({curr_code}):", min_value=0, value=int(18000 * f_mult), step=500)
    with cf2:
        f_mvs = ui.number_input(f"MVS Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
        f_trans = ui.number_input(f"Transformer Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
    with cf3:
        f_access = ui.number_input(f"Accessory Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)
        f_solar = ui.number_input(f"Solar PV Freight ({curr_code}):", min_value=0, value=int(4000 * f_mult), step=500)

    unit_freight_bess = f_bess / usd_to_eur if is_eur_display else f_bess
    unit_freight_oog = f_oog / usd_to_eur if is_eur_display else f_oog
    unit_freight_mvs = f_mvs / usd_to_eur if is_eur_display else f_mvs
    unit_freight_trans = f_trans / usd_to_eur if is_eur_display else f_trans
    unit_freight_access = f_access / usd_to_eur if is_eur_display else f_access
    unit_freight_solar = f_solar / usd_to_eur if is_eur_display else f_solar

    st.markdown("#### 2. Container Size per Equipment Type")
    _BOX_SIZES = [x for x in CONTAINER_SIZES if x != "MPP / Breakbulk"]
    st.caption("Carriers publish BAF / EFS per TEU: 20ft = 1 TEU, 40ft / 40ft HC = 2 TEU. "
               "A 10ft SOC normally takes a 20ft slot and is billed as 1 TEU (adjustable below).")
    cs1, cs2, cs3, cs4 = st.columns(4)
    with cs1:
        size_bess = ui.selectbox("BESS container size:", _BOX_SIZES, index=_BOX_SIZES.index("20ft"))
        size_oog = ui.selectbox("OOG unit size:", _BOX_SIZES, index=_BOX_SIZES.index("40ft"))
    with cs2:
        size_mvs = ui.selectbox("MVS container size:", _BOX_SIZES, index=_BOX_SIZES.index("20ft"))
        size_trans = ui.selectbox("Transformer size:", _BOX_SIZES, index=_BOX_SIZES.index("20ft"))
    with cs3:
        size_access = ui.selectbox("Accessory container size:", _BOX_SIZES, index=_BOX_SIZES.index("40ft HC"))
        size_solar = ui.selectbox("Solar PV container size:", _BOX_SIZES, index=_BOX_SIZES.index("40ft HC"))
    with cs4:
        ten_ft_teu = ui.number_input("10ft container billed as (TEU):", min_value=0.5, max_value=1.0, value=1.0, step=0.5)

    st.markdown(f"#### 3. Fuel Surcharges per TEU — BAF & EFS ({curr_code})")
    auto_baf = lookup_surcharge(BAF_RATES, shipping_line, dest_port)
    if auto_baf:
        st.caption(f"📡 Auto-filled from the monthly surcharge table: **{auto_baf['carrier']} — {auto_baf['lane']}** · "
                   f"{auto_baf.get('baf_name') or 'BAF'} effective {auto_baf.get('effective_from') or '-'} · "
                   f"checked {auto_baf.get('verified_on') or '-'}"
                   + (f" · [source]({auto_baf['source_url']})" if auto_baf.get('source_url') else ""))
    else:
        st.caption(f"No published surcharge on file for **{shipping_line}** to this port yet — enter the BAF from your quote.")
    include_baf_in_freight = ui.checkbox("Ocean Freight already includes BAF", value=False)
    auto_baf_usd = float(auto_baf["baf_usd_per_teu"]) if auto_baf else 600.0
    auto_efs_usd = float(auto_baf["efs_usd_per_teu"]) if (auto_baf and auto_baf.get("efs_usd_per_teu") is not None) else 0.0

    bf1, bf2, bf3 = st.columns(3)
    with bf1:
        baf_per_teu_in = ui.number_input(f"BAF per TEU ({curr_code}):", min_value=-2000.0,
                                         value=0.0 if include_baf_in_freight else round(auto_baf_usd * f_mult, 2),
                                         step=10.0, disabled=include_baf_in_freight)
    with bf2:
        apply_efs = ui.checkbox("Apply Emergency Fuel Surcharge (EFS)", value=bool(auto_efs_usd))
    with bf3:
        efs_per_teu_in = ui.number_input(f"EFS per TEU ({curr_code}):", min_value=0.0,
                                         value=round(auto_efs_usd * f_mult, 2), step=10.0, disabled=not apply_efs)

    baf_per_teu_usd = 0.0 if include_baf_in_freight else (baf_per_teu_in / usd_to_eur if is_eur_display else baf_per_teu_in)
    efs_per_teu_usd = (efs_per_teu_in / usd_to_eur if is_eur_display else efs_per_teu_in) if apply_efs else 0.0

    teu_bess, teu_oog = teu_factor(size_bess, ten_ft_teu), teu_factor(size_oog, ten_ft_teu)
    teu_mvs, teu_trans = teu_factor(size_mvs, ten_ft_teu), teu_factor(size_trans, ten_ft_teu)
    teu_access, teu_solar = teu_factor(size_access, ten_ft_teu), teu_factor(size_solar, ten_ft_teu)

    # Per-unit fuel surcharges in USD (BAF + EFS) passed to the cost engine
    fuel_per_teu_usd = baf_per_teu_usd + efs_per_teu_usd
    baf_bess, baf_oog = fuel_per_teu_usd * teu_bess, fuel_per_teu_usd * teu_oog
    baf_mvs, baf_trans = fuel_per_teu_usd * teu_mvs, fuel_per_teu_usd * teu_trans
    baf_access, baf_solar = fuel_per_teu_usd * teu_access, fuel_per_teu_usd * teu_solar
    project_teu = (bess_count * teu_bess + oog_count * teu_oog + mvs_count * teu_mvs +
                   transformer_count * teu_trans + access_count * teu_access + solar_count * teu_solar)
    st.info(f"Project volume: **{project_teu:g} TEU** · fuel surcharges = {project_teu:g} TEU × "
            f"({'BAF' + (' + EFS' if apply_efs else '')}) per TEU.")

    st.markdown(f"#### 4. Destination Terminal Handling Charges (Destination THC) per Unit ({curr_code})")
    thc_mult = f_mult
    ct1, ct2, ct3 = st.columns(3)
    with ct1:
        dthc_bess = ui.number_input(f"BESS Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_oog = ui.number_input(f"OOG Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
    with ct2:
        dthc_mvs = ui.number_input(f"MVS Destination THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_trans = ui.number_input(f"Transformer THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
    with ct3:
        dthc_access = ui.number_input(f"Accessory THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)
        dthc_solar = ui.number_input(f"Solar PV THC ({curr_code}):", min_value=0.0, value=400.0 * thc_mult, step=50.0)

    if is_eur_display:
        dthc_bess /= usd_to_eur; dthc_oog /= usd_to_eur; dthc_mvs /= usd_to_eur
        dthc_trans /= usd_to_eur; dthc_access /= usd_to_eur; dthc_solar /= usd_to_eur

    st.markdown(f"#### 5. Origin Charges in China per Container ({curr_code})")
    oc1, oc2 = st.columns(2)
    with oc1:
        origin_truck_in = ui.number_input(f"Factory-to-port trucking per container ({curr_code}):", min_value=0.0,
                                          value=round(220.0 * f_mult, 2), step=10.0)
    with oc2:
        origin_thc_in = ui.number_input(f"Origin THC & export handling per container ({curr_code}):", min_value=0.0,
                                        value=round(130.0 * f_mult, 2), step=10.0)
    origin_truck_usd = origin_truck_in / usd_to_eur if is_eur_display else origin_truck_in
    origin_thc_usd = origin_thc_in / usd_to_eur if is_eur_display else origin_thc_in

    st.markdown("---")
    cc1, cc2 = st.columns(2)
    with cc1:
        insurance_pct = ui.number_input("Marine Insurance Rate (% of CIF):", min_value=0.0, value=0.15, step=0.05)
        if insurance_by_client:
            insurance_pct = 0.0
            st.caption("Marine insurance is arranged by the client (Project Brief) — excluded from the costs.")
        customs_duty_pct = ui.number_input("Customs Duty Rate (%) - BESS/General:", min_value=0.0, value=(0.0 if is_israel else 2.7), step=0.1)
    with cc2:
        mvs_customs_duty_pct = ui.number_input("Customs Duty Rate (%) - MVS / Transformers:", min_value=0.0, value=0.0, step=0.1)
        if is_israel:
            st.info("🇮🇱 Israel: no customs duty on BESS, MVS or transformers (default 0%). "
                    "Solar PV / Inverters are calculated at 0%. Verify the HS classification with your customs broker.")
        else:
            st.info("Solar PV / Inverters are automatically 0% exempt under EU green energy trade regulations.")
