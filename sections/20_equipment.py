# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 20_equipment: Tab: Equipment Mix & Quantities (+ EXW conversion, capacity, unit-cost KPIs).
# Runs in the shared namespace of app.py, in file-name order (see app.py).
with tab1:
    st.subheader("Equipment Mix & Quantities Configuration")
    if bom_sync:
        st.caption("🔗 Quantities and BESS capacity follow the BOM in the Project Brief tab.")
    st.info(f"All calculations tailored for active BESS deployment in **{destination_country}** (Display Currency: **{curr_code}**).")
    
    col1, col2 = st.columns(2)
    with col1:
        bess_count = (st.number_input("BESS Containers (Units):", min_value=0, value=int(bom_totals.get("BESS", 0)), step=1, disabled=True,
                                 key="bom_sync_bess_count_" + str(int(bom_totals.get("BESS", 0))))
                 if bom_sync else ui.number_input("BESS Containers (Units):", min_value=0, value=20, step=1))
        mvs_count = (st.number_input("Medium Voltage Stations (MVS Units):", min_value=0, value=int(bom_totals.get("MVS", 0)), step=1, disabled=True,
                                 key="bom_sync_mvs_count_" + str(int(bom_totals.get("MVS", 0))))
                 if bom_sync else ui.number_input("Medium Voltage Stations (MVS Units):", min_value=0, value=4, step=1))
        transformer_count = (st.number_input("Transformers / Skids:", min_value=0, value=int(bom_totals.get("Transformer", 0)), step=1, disabled=True,
                                 key="bom_sync_transformer_count_" + str(int(bom_totals.get("Transformer", 0))))
                 if bom_sync else ui.number_input("Transformers / Skids:", min_value=0, value=0, step=1))
    with col2:
        oog_count = (st.number_input("OOG / Special Containers:", min_value=0, value=int(bom_totals.get("OOG", 0)), step=1, disabled=True,
                                 key="bom_sync_oog_count_" + str(int(bom_totals.get("OOG", 0))))
                 if bom_sync else ui.number_input("OOG / Special Containers:", min_value=0, value=0, step=1))
        access_count = (st.number_input("Accessory Containers:", min_value=0, value=int(bom_totals.get("Accessory", 0)), step=1, disabled=True,
                                 key="bom_sync_access_count_" + str(int(bom_totals.get("Accessory", 0))))
                 if bom_sync else ui.number_input("Accessory Containers:", min_value=0, value=2, step=1))
        solar_count = (st.number_input("Solar PV / Inverter Containers:", min_value=0, value=int(bom_totals.get("Solar", 0)), step=1, disabled=True,
                                 key="bom_sync_solar_count_" + str(int(bom_totals.get("Solar", 0))))
                 if bom_sync else ui.number_input("Solar PV / Inverter Containers:", min_value=0, value=0, step=1))

    st.markdown("---")
    st.markdown("#### Site Location & Project Details")
    loc_col1, loc_col2, loc_col3 = st.columns(3)
    with loc_col1:
        site_address = ui.text_input("Site Address / Location:", value=f"Industrial Zone, {destination_country}")
    with loc_col2:
        site_postal = ui.text_input("Postal Code / Region:", value="10000")
    with loc_col3:
        site_coords = ui.text_input("GPS Coordinates (lat, lon):", value=DEFAULT_SITE_COORDS.get(destination_country, "44.4268, 26.1025"))
    site_latlon = parse_coords(site_coords)
    if site_latlon is None:
        st.warning("GPS coordinates not recognised — use the format 44.4268, 26.1025")
    else:
        _dists = sorted(((p, road_km(site_latlon, PORT_COORDS[p])) for p in destination_ports if p in PORT_COORDS),
                        key=lambda x: x[1])
        if _dists:
            st.caption("Nearest ports by estimated road distance: " +
                       " · ".join(f"**{p.split(',')[0]}** ≈ {d:,.0f} km" for p, d in _dists[:3]) +
                       f" (straight line × {ROAD_FACTOR}; confirm with a route survey).")

    st.markdown("---")
    st.markdown(f"#### Equipment EXW Cost ({curr_code})")
    
    col_exw1, col_exw2 = st.columns(2)
    with col_exw1:
      # Currency conversion factor for default values display
        disp_mult = usd_to_eur if (not is_eur_display and usd_to_eur > 0) else 1.0

        bess_exw_input = ui.number_input(f"EXW Cost per BESS Container ({curr_code}):", min_value=0, value=int(400000 * disp_mult), step=5000) if bess_count > 0 else 0
        mvs_exw_input = ui.number_input(f"EXW Cost per MVS Unit ({curr_code}):", min_value=0, value=int(250000 * disp_mult), step=5000) if mvs_count > 0 else 0
        transformer_exw_input = ui.number_input(f"EXW Cost per Transformer ({curr_code}):", min_value=0, value=int(120000 * disp_mult), step=5000) if transformer_count > 0 else 0
with col_exw2:
        oog_exw_input = ui.number_input(f"EXW Cost per OOG Unit ({curr_code}):", min_value=0, value=int(300000 * disp_mult), step=5000) if oog_count > 0 else 0
        access_exw_input = ui.number_input(f"EXW Cost per Accessory Unit ({curr_code}):", min_value=0, value=int(30000 * disp_mult), step=1000) if access_count > 0 else 0
        solar_exw_input = ui.number_input(f"EXW Cost per Solar Unit ({curr_code}):", min_value=0, value=int(50000 * disp_mult), step=1000) if solar_count > 0 else 0

to_usd_factor = (1.0 / usd_to_eur) if is_eur_display and usd_to_eur > 0 else 1.0
bess_exw = bess_exw_input * to_usd_factor
oog_exw = oog_exw_input * to_usd_factor
mvs_exw = mvs_exw_input * to_usd_factor
transformer_exw = transformer_exw_input * to_usd_factor
access_exw = access_exw_input * to_usd_factor
solar_exw = solar_exw_input * to_usd_factor

with tab1:
    st.markdown("---")
    st.markdown("#### Energy & Power Capacity")
    ec1, ec2, ec3 = st.columns(3)
    with ec1:
        if bom_sync and bom_bess_mwh > 0:
            bess_capacity_mwh = st.number_input("BESS Capacity per Container (MWh, DC nameplate):", min_value=0.5,
                                                value=float(bom_bess_mwh), step=0.5, disabled=True,
                                                key=f"bom_sync_mwh_{bom_bess_mwh}")
        else:
            bess_capacity_mwh = ui.number_input("BESS Capacity per Container (MWh, DC nameplate):", min_value=0.5, value=4.0, step=0.5)
    with ec2:
        project_mwac = ui.number_input("Project Power (MWac) — optional:", min_value=0.0, value=0.0, step=1.0,
                                       help="Inverter / PCS AC rating at the point of interconnection. Leave 0 to hide $/kW.")
    with ec3:
        project_mwh_ac = ui.number_input("Usable Energy at POI (MWh AC) — optional:", min_value=0.0, value=0.0, step=1.0,
                                         help="Contracted usable AC energy at the point of interconnection. Leave 0 to hide $/kWh AC.")
    project_kwh_dc = bess_count * bess_capacity_mwh * 1000.0
    st.caption(f"Project DC nameplate energy: **{project_kwh_dc / 1000.0:,.1f} MWh** "
               f"({bess_count} BESS × {bess_capacity_mwh:g} MWh). Cost-per-kWh metrics use this as the default basis.")


def render_unit_cost_metrics(logistics_usd, landed_usd, exw_usd, mult, code, label_suffix=""):
    """Industry KPIs: cost per kWh / MWh on DC nameplate, plus optional AC usable energy and $/kW."""
    sym = "€" if code == "EUR" else "$"
    if project_kwh_dc <= 0:
        st.info("Add BESS containers and capacity (Equipment tab) to see cost per kWh / MWh.")
        return
    st.markdown(f"##### Unit Cost KPIs — basis: DC nameplate {project_kwh_dc / 1000.0:,.1f} MWh{label_suffix}")
    k1, k2, k3 = st.columns(3)
    for col, title, val in [
        (k1, "Logistics & Import Cost", logistics_usd),
        (k2, "Total Landed Cost", landed_usd),
        (k3, "Equipment EXW", exw_usd),
    ]:
        per_kwh = val * mult / project_kwh_dc
        col.metric(f"{title} per kWh (DC)", f"{sym} {per_kwh:,.2f}", help=f"{sym} {per_kwh * 1000:,.0f} per MWh")
        col.caption(f"= {sym} {per_kwh * 1000:,.0f} / MWh")
    if project_mwh_ac > 0 or project_mwac > 0:
        a1, a2, a3 = st.columns(3)
        if project_mwh_ac > 0:
            a1.metric("Landed Cost per kWh (AC usable at POI)", f"{sym} {landed_usd * mult / (project_mwh_ac * 1000):,.2f}")
            a2.metric("Logistics & Import per kWh (AC usable)", f"{sym} {logistics_usd * mult / (project_mwh_ac * 1000):,.2f}")
        if project_mwac > 0:
            a3.metric("Landed Cost per kW (AC)", f"{sym} {landed_usd * mult / (project_mwac * 1000):,.0f}")
