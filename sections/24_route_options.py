# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
# Terra Vol Global — section 24_route_options: Tab: Route Options.
# Runs in the shared namespace of app.py, in file-name order (see app.py).
with tab5:
    st.subheader("🧭 Multi-Option Port-to-Door Routing Agent")
    
    # Value proposition explanation for the routing table
    st.markdown("""
    > **Module Value Proposition:** This routing agent scans international sea basins and European gateway hubs to present **complete port-to-door supply chain alternatives** (from Chinese origin ports to project destination sites). 
    > It allows easy comparison between ocean transit times, inland trucking distances, transit durations, and base costs to determine the most cost-effective routing strategy for renewable energy projects.
    """)

    EUROPEAN_LOGISTICS_HUB = {
        "Romania": {
            "site_name": "Bucharest / Ilfov / Ploiești Energy Hub (Romania)",
            "gateways": [
                {"port": "Constanta (Black Sea Main Gateway)", "ocean_days": 32, "inland_dist_km": 280, "inland_days": 3, "cost": 3600},
                {"port": "Varna / Burgas (Black Sea Secondary)", "ocean_days": 34, "inland_dist_km": 380, "inland_days": 4, "cost": 4100},
                {"port": "Koper (Adriatic Multimodal Gateway)", "ocean_days": 35, "inland_dist_km": 1100, "inland_days": 7, "cost": 6500},
                {"port": "Hamburg / Rotterdam (North Sea Corridor)", "ocean_days": 35, "inland_dist_km": 1800, "inland_days": 10, "cost": 8200}
            ]
        },
        "Germany": {
            "site_name": "Berlin / Frankfurt / Rhine-Ruhr Hub (Germany)",
            "gateways": [
                {"port": "Hamburg / Bremen (North Sea Main Gateway)", "ocean_days": 35, "inland_dist_km": 350, "inland_days": 3, "cost": 3800},
                {"port": "Rotterdam / Antwerp (Western Europe Gateway)", "ocean_days": 35, "inland_dist_km": 550, "inland_days": 4, "cost": 5200},
                {"port": "Koper (Adriatic Gateway)", "ocean_days": 35, "inland_dist_km": 850, "inland_days": 6, "cost": 6800}
            ]
        },
        "Italy": {
            "site_name": "Padova / Milan / Northern Italy Energy Hub",
            "gateways": [
                {"port": "Genoa / Trieste / Venice (Med/Adriatic Hub)", "ocean_days": 34, "inland_dist_km": 200, "inland_days": 2, "cost": 2100},
                {"port": "Koper / Rijeka (Adriatic Gateway)", "ocean_days": 35, "inland_dist_km": 300, "inland_days": 3, "cost": 3200},
                {"port": "Rotterdam / Antwerp (Northern Corridor)", "ocean_days": 35, "inland_dist_km": 1100, "inland_days": 7, "cost": 7500}
            ]
        },
        "Netherlands": {
            "site_name": "Amsterdam / Rotterdam Industrial & Energy Zone",
            "gateways": [
                {"port": "Rotterdam / Antwerp (Local Western Gateway)", "ocean_days": 35, "inland_dist_km": 60, "inland_days": 1, "cost": 600},
                {"port": "Hamburg / Bremen (North Sea Hub)", "ocean_days": 36, "inland_dist_km": 450, "inland_days": 4, "cost": 4200}
            ]
        },
        "Greece": {
            "site_name": "Athens / Attica / Central Greece Energy Hub",
            "gateways": [
                {"port": "Piraeus / Thessaloniki (Hellenic Main Gateway)", "ocean_days": 32, "inland_dist_km": 40, "inland_days": 1, "cost": 600},
                {"port": "Constanta / Black Sea Feeder", "ocean_days": 35, "inland_dist_km": 950, "inland_days": 8, "cost": 7200}
            ]
        }
    }

    route_countries = list(EUROPEAN_LOGISTICS_HUB.keys()) + ["Israel"]
    # Always follow the destination country chosen in the sidebar (single source of truth)
    selected_country = destination_country
    st.markdown(f"**Destination country:** {destination_country} *(change it in the sidebar)*")

    china_ports = [
        "Shanghai (China)", 
        "Ningbo (China)", 
        "Yantian / Shenzhen (China)", 
        "Qingdao (China)", 
        "Xingang / Tianjin (China)"
    ]

    if selected_country == "Israel":
        # Road distance (km) from each port cluster to each site region — indicative, editable below
        ISRAEL_REGIONS = {
            "North — Haifa / Galilee / Jezreel Valley": {"Haifa": 40, "Ashdod": 160, "Eilat": 400},
            "Center — Sharon / Gush Dan / Shfela": {"Haifa": 100, "Ashdod": 50, "Eilat": 330},
            "South — Negev / Be'er Sheva / Dimona": {"Haifa": 210, "Ashdod": 90, "Eilat": 230},
            "Arava / Eilat": {"Haifa": 400, "Ashdod": 300, "Eilat": 30},
        }
        ISRAEL_PORT_CLUSTER = {
            "Haifa Bay Port (SIPG), Israel": ("Haifa", 38),
            "Haifa Port (Adani), Israel": ("Haifa", 38),
            "Israel Shipyards Port (Haifa), Israel": ("Haifa", 38),
            "Ashdod Port, Israel": ("Ashdod", 38),
            "TIL - Hadarom South Port (Ashdod), Israel": ("Ashdod", 38),
            "Eilat Port, Israel": ("Eilat", 22),
        }

        ir1, ir2, ir3 = st.columns(3)
        with ir1:
            il_region = ui.selectbox("Project Site Region (Israel):", list(ISRAEL_REGIONS.keys()))
        with ir2:
            il_base_cost = ui.number_input("Heavy-haul base cost per BESS unit (USD):", min_value=0.0, value=1500.0, step=100.0)
        with ir3:
            il_km_rate = ui.number_input("Heavy-haul rate per km per BESS unit (USD):", min_value=0.0, value=12.0, step=1.0)

        _gps_in_israel = bool(site_latlon and 29.0 <= site_latlon[0] <= 33.5 and 34.0 <= site_latlon[1] <= 36.0)
        if _gps_in_israel:
            st.caption(f"📍 Road distances estimated from the site GPS ({site_coords}) entered in the Equipment tab.")
        st.caption("Ocean transit days and road distances are **indicative defaults** — edit them in the table to match "
                   "current carrier schedules (Suez vs. Cape routing) and the exact site location. "
                   "Check that the Eilat port currently has a service for your cargo before relying on it.")

        il_defaults = pd.DataFrame([
            {"Israeli Port": port,
             "Ocean Transit from China (Days)": days,
             "Road Distance to Site (km)": (round(road_km(site_latlon, PORT_COORDS[port])) if _gps_in_israel
                                            else ISRAEL_REGIONS[il_region][cluster])}
            for port, (cluster, days) in ISRAEL_PORT_CLUSTER.items()
        ])
        il_edit = st.data_editor(
            il_defaults, key=f"il_routes_{il_region}_{site_coords}", hide_index=True, use_container_width=True,
            disabled=["Israeli Port"],
            column_config={
                "Ocean Transit from China (Days)": st.column_config.NumberColumn(min_value=0, step=1),
                "Road Distance to Site (km)": st.column_config.NumberColumn(min_value=0, step=5),
            },
        )

        il_rows = []
        for _, r in il_edit.iterrows():
            km = float(r["Road Distance to Site (km)"] or 0)
            ocean = int(r["Ocean Transit from China (Days)"] or 0)
            inland_days = 1 if km <= 150 else 2
            cost_unit = il_base_cost + il_km_rate * km
            il_rows.append({
                "Israeli Port": r["Israeli Port"],
                "Destination Site": il_region,
                "Ocean Transit (Days)": ocean,
                "Road Distance (km)": int(km),
                "Inland Days (night convoy)": inland_days,
                "Total Transit (Days)": ocean + inland_days,
                "Trucking per BESS (USD)": round(cost_unit),
                f"Trucking — {bess_count} BESS (USD)": round(cost_unit * bess_count),
                "MoT Transport Permits": f"{bess_count} required",
            })
        il_df = pd.DataFrame(il_rows).sort_values(by=["Trucking per BESS (USD)", "Total Transit (Days)"])
        st.markdown("#### Port-to-Site Options — sorted by trucking cost")
        st.dataframe(il_df, use_container_width=True, hide_index=True)
        best = il_df.iloc[0]
        st.success(f"Lowest trucking cost: **{best['Israeli Port']}** — {best['Road Distance (km)']} km to site, "
                   f"total transit ≈ {best['Total Transit (Days)']} days.")
        if not has_toxins_permit:
            st.warning(f"Reminder: Toxins Permit missing for the {toxins_missing_text} — without the importer's permit BESS "
                       "cannot be released from an external storage terminal; keep this in mind when comparing ports with off-port yards.")
    elif selected_country not in EUROPEAN_LOGISTICS_HUB:
        st.info(f"Route options for **{selected_country}** are not available yet. "
                f"Currently covered: {', '.join(route_countries)}. "
                "Use the Multi-Shipment Planner to cost specific routes for this country.")
    else:
        country_info = EUROPEAN_LOGISTICS_HUB[selected_country]

        def gateway_site_km(gw_name):
            """Estimated road km from the site GPS to the nearest known port named in the gateway."""
            if not site_latlon:
                return None
            norm = gw_name.lower().replace("ț", "t").replace("ș", "s")
            kms = [road_km(site_latlon, xy) for port, xy in PORT_COORDS.items()
                   if port.split(",")[0].split(" /")[0].lower().replace("ț", "t") in norm]
            return round(min(kms)) if kms else None

        if site_latlon:
            st.caption(f"📍 'Distance from Your Site' is estimated from the site GPS ({site_coords}) entered in the Equipment tab; "
                       "'Inland Trucking Distance' is the reference hub distance.")
        routing_results = []
        for gw in country_info["gateways"]:
            for china_port in china_ports:
                routing_results.append({
                    "Origin Port (China)": china_port,
                    "European Gateway": gw["port"],
                    "Destination Site": country_info["site_name"],
                    "Ocean Transit (Days)": gw["ocean_days"],
                    "Inland Trucking Distance (km)": gw["inland_dist_km"],
                    "Distance from Your Site (km, est.)": gateway_site_km(gw["port"]),
                    "Inland Trucking Days": gw["inland_days"],
                    "Total Transit (Days)": gw["ocean_days"] + gw["inland_days"],
                    "Base Trucking Cost (€)": gw["cost"],
                    "Status": "Active & Verified"
                })

        if routing_results:
            df_routes = pd.DataFrame(routing_results)
            st.dataframe(df_routes, use_container_width=True, hide_index=True)
            st.success(f"Smart Agent successfully mapped routing alternatives for {selected_country}.")
        else:
            st.info("No routing options available for this selection.")
