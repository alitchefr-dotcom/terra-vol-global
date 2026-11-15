import requests

DECOM_SCENARIOS_USD_PER_KWH = {"low": 59.0, "base": 75.0, "high": 90.0}

def calculate_decommissioning(
    bess_count, oog_count, bess_capacity_mwh, decom_cost_per_kwh,
    apply_decommissioning,
    include_oog_in_decom=False,
    cost_currency="USD",
    usd_to_eur=0.92,
    years_to_decom=20,
    discount_rate=0.0,
    residual_value_per_kwh=0.0,
):
    if not apply_decommissioning or bess_count <= 0:
        return {"units": 0, "nominal_usd": 0.0, "pv_usd": 0.0}

    units = bess_count + (oog_count if include_oog_in_decom else 0)
    kwh_per_unit = bess_capacity_mwh * 1000.0
    net_per_kwh = decom_cost_per_kwh - residual_value_per_kwh
    nominal_native = units * kwh_per_unit * net_per_kwh

    if cost_currency == "EUR":
        nominal_usd = nominal_native / usd_to_eur if usd_to_eur > 0 else nominal_native
    else:
        nominal_usd = nominal_native

    pv_usd = nominal_usd / ((1 + discount_rate) ** years_to_decom) if years_to_decom > 0 else nominal_usd
    return {"units": units, "nominal_usd": nominal_usd, "pv_usd": pv_usd}

def decommissioning_scenarios(
    bess_count, oog_count, bess_capacity_mwh, apply_decommissioning,
    include_oog_in_decom=False, years_to_decom=20, discount_rate=0.0,
    residual_value_per_kwh=0.0,
):
    out = {}
    for name, cost in DECOM_SCENARIOS_USD_PER_KWH.items():
        r = calculate_decommissioning(
            bess_count, oog_count, bess_capacity_mwh, cost, apply_decommissioning,
            include_oog_in_decom=include_oog_in_decom, cost_currency="USD",
            years_to_decom=years_to_decom, discount_rate=discount_rate,
            residual_value_per_kwh=residual_value_per_kwh,
        )
        out[name] = {"cost_per_kwh_usd": cost, "nominal_usd": r["nominal_usd"], "pv_usd": r["pv_usd"]}
    return out


def get_live_exchange_rate(base_currency="USD", target_currency="EUR"):
    try:
        url = f"https://open.er-api.com/v6/latest/{base_currency}"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            rate = data.get("rates", {}).get(target_currency)
            if rate:
                return float(rate)
    except Exception:
        pass
    fallbacks = {"EUR": 0.92, "USD": 1.0}
    return fallbacks.get(target_currency, 1.0)


def convert_currency(amount_in_usd, from_curr="USD", to_curr="EUR", custom_rate=0.92):
    if "EUR" in to_curr or to_curr == "EUR":
        return amount_in_usd * custom_rate
    return amount_in_usd


def format_currency(amount, curr_code="EUR"):
    symbol = "€" if "EUR" in curr_code else "$"
    return f"{symbol} {amount:,.2f}"


def calculate_project_costs(
    bess_count, bess_exw,
    oog_count, oog_exw,
    mvs_count, mvs_exw,
    transformer_count, transformer_exw,
    access_count, access_exw,
    solar_count, solar_exw,
    unit_freight_bess, unit_freight_oog, unit_freight_mvs, unit_freight_trans, unit_freight_access, unit_freight_solar,
    baf_bess, baf_oog, baf_mvs, baf_trans, baf_access, baf_solar,
    dthc_bess, dthc_oog, dthc_mvs, dthc_trans, dthc_access, dthc_solar,
    drayage_bess, drayage_oog, drayage_mvs, drayage_trans, drayage_access, drayage_solar,
    trend_multiplier, insurance_pct, customs_duty_pct, mvs_customs_duty_pct, applied_vat, vat_recovery_pct,
    vat_paid_by_supplier, incoterm_code, dest_country_code,
    local_regulatory_permits, mot_total_approval_cost, include_regulatory, include_mot_approval,
    site_crane_unloading, include_site_crane,
    epr_recycling_total_usd, battery_passport_total_usd,
    requires_heavy_lift, heavy_lift_survey_cost,
    actual_port_days, free_days, demurrage_daily_rate, use_external_storage, ext_storage_days, ext_storage_daily_rate, include_delay_scenario,
    bess_capacity_mwh, decom_cost_per_kwh,
    include_oog_in_decom=False,
    decom_cost_currency="USD",
    decom_scenario=None,
    usd_to_eur=0.92,
    years_to_decom=20,
    decom_discount_rate=0.0,
    decom_residual_per_kwh=0.0,
    apply_decommissioning=None,
    contingency_pct=5.0,
    origin_trucking_per_unit=220.0,
    origin_thc_per_unit=130.0,
):
    total_containers_project = max(1, bess_count + oog_count + mvs_count + transformer_count + access_count + solar_count)

    # STRICT MULTIPLICATION BY ACTUAL QUANTITY (0 units = 0 cost)
    total_exw_project = (
        (bess_count * bess_exw) + (oog_count * oog_exw) + 
        (mvs_count * mvs_exw) + (transformer_count * transformer_exw) + 
        (access_count * access_exw) + (solar_count * solar_exw)
    )

    trended_exw = total_exw_project * trend_multiplier

    total_base_ocean_freight = (
        (bess_count * unit_freight_bess) + (oog_count * unit_freight_oog) +
        (mvs_count * unit_freight_mvs) + (transformer_count * unit_freight_trans) +
        (access_count * unit_freight_access) + (solar_count * unit_freight_solar)
    )
    total_baf_ocean = (
        (bess_count * baf_bess) + (oog_count * baf_oog) +
        (mvs_count * baf_mvs) + (transformer_count * baf_trans) +
        (access_count * baf_access) + (solar_count * baf_solar)
    )
    total_destination_thc = (
        (bess_count * dthc_bess) + (oog_count * dthc_oog) +
        (mvs_count * dthc_mvs) + (transformer_count * dthc_trans) +
        (access_count * dthc_access) + (solar_count * dthc_solar)
    )

    # Origin (China) pre-carriage and origin THC per container — defaults 220 + 130 USD (= 2,200 / 1,300 per 10 units)
    china_inland_drayage = origin_trucking_per_unit * total_containers_project
    china_origin_thc = origin_thc_per_unit * total_containers_project

    inland_drayage_total_base = (
        (bess_count * drayage_bess) + (oog_count * drayage_oog) +
        (mvs_count * drayage_mvs) + (transformer_count * drayage_trans) +
        (access_count * drayage_access) + (solar_count * drayage_solar)
    )

    trended_ocean_freight = (total_base_ocean_freight + total_baf_ocean) * trend_multiplier
    trended_drayage = inland_drayage_total_base * trend_multiplier

    total_ocean_freight = trended_ocean_freight
    inland_drayage_total_usd = trended_drayage

    cif_valuation_base = trended_exw + china_inland_drayage + china_origin_thc + total_ocean_freight
    insurance_total_usd = cif_valuation_base * (insurance_pct / 100.0)

    total_solar_exw = solar_count * solar_exw * trend_multiplier
    total_mvs_trans_exw = ((mvs_count * mvs_exw) + (transformer_count * transformer_exw)) * trend_multiplier
    general_non_solar_exw = trended_exw - total_solar_exw - total_mvs_trans_exw

    customs_valuation_base_usd = cif_valuation_base + insurance_total_usd
    
    general_ratio = (general_non_solar_exw / trended_exw) if trended_exw > 0 else 0.0
    mvs_trans_ratio = (total_mvs_trans_exw / trended_exw) if trended_exw > 0 else 0.0

    customs_duty_usd = (customs_valuation_base_usd * general_ratio * (customs_duty_pct / 100.0)) + \
                       (customs_valuation_base_usd * mvs_trans_ratio * (mvs_customs_duty_pct / 100.0))

    destination_thc_total = total_destination_thc  

    is_european_dest = (dest_country_code != "IL")
    if is_european_dest:
        indicative_vat_base_import_usd = customs_valuation_base_usd + customs_duty_usd + destination_thc_total + inland_drayage_total_usd
    else:
        indicative_vat_base_import_usd = customs_valuation_base_usd + customs_duty_usd + destination_thc_total

    vat_total_usd = indicative_vat_base_import_usd * (applied_vat / 100.0)

    is_ddp = (incoterm_code == "DDP")
    supplier_vat_component = vat_total_usd if (vat_paid_by_supplier and is_ddp) else 0.0

    active_regulatory_permits = (local_regulatory_permits if include_regulatory else 0.0) + (mot_total_approval_cost if include_mot_approval else 0.0)
    active_site_crane = site_crane_unloading if include_site_crane else 0.0
    active_heavy_lift = heavy_lift_survey_cost if requires_heavy_lift else 0.0

    overdue_days = max(0, actual_port_days - free_days)
    demurrage_total_usd = float(overdue_days) * demurrage_daily_rate * float(total_containers_project)
    external_storage_total_usd = (float(ext_storage_days) * ext_storage_daily_rate * float(total_containers_project)) if use_external_storage else 0.0
    effective_delay_cost = (demurrage_total_usd + external_storage_total_usd) if include_delay_scenario else 0.0

    if apply_decommissioning is None:
        apply_decommissioning = (dest_country_code != "IL")

    if decom_scenario is not None:
        decom_cost_per_kwh = DECOM_SCENARIOS_USD_PER_KWH[decom_scenario]
        decom_cost_currency = "USD"

    decom = calculate_decommissioning(
        bess_count, oog_count, bess_capacity_mwh, decom_cost_per_kwh,
        apply_decommissioning=apply_decommissioning,
        include_oog_in_decom=include_oog_in_decom,
        cost_currency=decom_cost_currency, usd_to_eur=usd_to_eur,
        years_to_decom=years_to_decom, discount_rate=decom_discount_rate,
        residual_value_per_kwh=decom_residual_per_kwh,
    )
    decommissioning_total_usd = decom["nominal_usd"]
    decommissioning_pv_usd = decom["pv_usd"]
    decom_scenarios = decommissioning_scenarios(
        bess_count, oog_count, bess_capacity_mwh, apply_decommissioning,
        include_oog_in_decom=include_oog_in_decom, years_to_decom=years_to_decom,
        discount_rate=decom_discount_rate, residual_value_per_kwh=decom_residual_per_kwh,
    )
    decom_epr_overlap_warning = bool(apply_decommissioning and epr_recycling_total_usd > 0 and decommissioning_total_usd > 0)

    project_delivery_cost = (
        trended_exw + 
        china_inland_drayage + 
        china_origin_thc + 
        total_ocean_freight + 
        insurance_total_usd + 
        customs_duty_usd + 
        destination_thc_total + 
        inland_drayage_total_usd + 
        active_site_crane + 
        active_regulatory_permits + 
        epr_recycling_total_usd + 
        battery_passport_total_usd + 
        active_heavy_lift + 
        effective_delay_cost
    )

    supplier_commercial_price_options = {
        "EXW": trended_exw,
        "FOB": trended_exw + china_inland_drayage + china_origin_thc,
        "CFR": trended_exw + china_inland_drayage + china_origin_thc + total_ocean_freight,
        "CIF": trended_exw + china_inland_drayage + china_origin_thc + total_ocean_freight + insurance_total_usd,
        "DAP": trended_exw + china_inland_drayage + china_origin_thc + total_ocean_freight + insurance_total_usd + destination_thc_total + inland_drayage_total_usd,
        "DDP": trended_exw + china_inland_drayage + china_origin_thc + total_ocean_freight + insurance_total_usd + customs_duty_usd + destination_thc_total + inland_drayage_total_usd + supplier_vat_component,
    }

    supplier_scope_total = supplier_commercial_price_options.get(incoterm_code, trended_exw)
    buyer_direct_payment_usd = max(0.0, project_delivery_cost - supplier_scope_total)

    effective_vat_cash = 0.0 if (vat_paid_by_supplier and is_ddp) else vat_total_usd
    recoverable_vat = vat_total_usd * (vat_recovery_pct / 100.0)
    effective_non_recoverable_vat = 0.0 if (vat_paid_by_supplier and is_ddp) else (vat_total_usd - recoverable_vat)

    buyer_supply_chain_total = project_delivery_cost
    contingency_usd = buyer_supply_chain_total * (contingency_pct / 100.0)
    total_landed_cost_ex_vat = buyer_supply_chain_total + contingency_usd
    
    economic_cost_ex_vat = total_landed_cost_ex_vat + effective_non_recoverable_vat + decommissioning_pv_usd
    total_cash_requirement_incl_vat = total_landed_cost_ex_vat + effective_vat_cash

    return {
        "total_containers_project": total_containers_project,
        "trended_exw": trended_exw,
        "china_inland_drayage": china_inland_drayage,
        "china_origin_thc": china_origin_thc,
        "total_base_ocean_freight": total_base_ocean_freight * trend_multiplier,
        "total_baf_ocean": total_baf_ocean * trend_multiplier,
        "destination_thc_total": destination_thc_total,
        "insurance_total_usd": insurance_total_usd,
        "customs_duty_usd": customs_duty_usd,
        "inland_drayage_total_usd": inland_drayage_total_usd,
        "active_regulatory_permits": active_regulatory_permits,
        "active_site_crane": active_site_crane,
        "epr_recycling_total_usd": epr_recycling_total_usd,
        "battery_passport_total_usd": battery_passport_total_usd,
        "active_heavy_lift": active_heavy_lift,
        "decommissioning_total_usd": decommissioning_total_usd,
        "decommissioning_pv_usd": decommissioning_pv_usd,
        "decom_units": decom["units"],
        "decom_scenarios": decom_scenarios,
        "decom_epr_overlap_warning": decom_epr_overlap_warning,
        "contingency_usd": contingency_usd,
        "total_landed_cost_ex_vat": total_landed_cost_ex_vat,
        "supplier_scope_total": supplier_scope_total,
        "buyer_direct_payment_usd": buyer_direct_payment_usd,
        "recoverable_vat": recoverable_vat,
        "economic_cost_ex_vat": economic_cost_ex_vat,
        "total_cash_requirement_incl_vat": total_cash_requirement_incl_vat,
        "demurrage_total_usd": demurrage_total_usd if include_delay_scenario else 0.0,
        "external_storage_total_usd": external_storage_total_usd if include_delay_scenario else 0.0
    }


# ---------------------------------------------------------------------------
# MULTI-SHIPMENT PLANNER
# ---------------------------------------------------------------------------
# A project is split into shipments (container line SOC / COC, or MPP vessel).
# Each shipment carries one or more "lines" (equipment type + quantity + rates).
# All amounts are converted to USD internally.

EQUIPMENT_TYPES = ["BESS", "OOG", "MVS", "Transformer", "Accessory", "Solar"]
# Duty group per equipment type: "general" -> general duty %, "mvs" -> MVS/transformer duty %, "solar" -> 0%
EQUIPMENT_DUTY_GROUP = {
    "BESS": "general", "OOG": "general", "Accessory": "general",
    "MVS": "mvs", "Transformer": "mvs", "Solar": "solar",
}
SERVICE_TYPES = ["Container Line - SOC", "Container Line - COC", "MPP Vessel"]

# Container sizes and how many TEU a carrier bills for each (BAF / EFS are published per TEU).
# A 10' box normally takes a 20' slot on a container vessel, so it is billed as 1 TEU by default.
CONTAINER_SIZES = ["10ft", "20ft", "40ft", "40ft HC", "MPP / Breakbulk"]
DEFAULT_TEU_FACTORS = {"10ft": 1.0, "20ft": 1.0, "40ft": 2.0, "40ft HC": 2.0, "MPP / Breakbulk": 1.0}


def teu_factor(size, ten_ft_factor=1.0):
    """TEU billed per container. MPP / Breakbulk returns 1.0 (surcharge entered per unit)."""
    if size == "10ft":
        return ten_ft_factor
    return DEFAULT_TEU_FACTORS.get(size, 1.0)


def _num(value, default=0.0):
    try:
        v = float(value)
        if v != v:  # NaN
            return default
        return v
    except (TypeError, ValueError):
        return default


def to_usd(amount, currency, usd_to_eur):
    if str(currency).upper().startswith("EUR") and usd_to_eur > 0:
        return amount / usd_to_eur
    return amount


def calculate_shipment_plan(
    shipments, lines, exw_usd_per_type, required_units,
    usd_to_eur=0.92, trend_multiplier=1.0,
    insurance_pct=0.15, customs_duty_pct=2.7, mvs_customs_duty_pct=0.0,
    applied_vat=19.0, vat_recovery_pct=100.0, dest_country_code="RO",
    project_level_costs_usd=0.0, contingency_pct=5.0, decommissioning_pv_usd=0.0,
    ten_ft_teu_factor=1.0,
):
    """
    shipments: list of dicts with keys
        name, carrier, service, origin, pod, etd, eta, currency,
        origin_charges_per_unit, port_days, free_days, daily_rate_per_unit, extra_lump_sum
    lines: list of dicts with keys
        shipment, equipment, qty, currency, container_size, freight_per_unit,
        baf_per_teu, apply_efs, efs_per_teu, dthc_per_unit, trucking_per_unit
        (BAF / EFS are per TEU and multiplied by the TEU factor of the container size;
         for "MPP / Breakbulk" they are per unit.)
    exw_usd_per_type: {equipment_type: EXW value per unit in USD}
    required_units:   {equipment_type: units required by the project}
    """
    is_european_dest = (dest_country_code != "IL")
    names = [s["name"] for s in shipments]
    results = []
    allocated = {t: 0 for t in EQUIPMENT_TYPES}
    orphan_lines = []

    for s in shipments:
        s_lines = [l for l in lines if l.get("shipment") == s["name"]]
        cur_s = s.get("currency", "USD")

        units = 0
        goods_value = 0.0
        value_general = value_mvs = 0.0
        freight = baf = efs = dthc = trucking = 0.0
        teu_total = 0.0
        units_by_type = {}

        for l in s_lines:
            eq = l.get("equipment")
            qty = int(_num(l.get("qty")))
            if eq not in EQUIPMENT_TYPES or qty <= 0:
                continue
            cur_l = l.get("currency", "USD")
            units += qty
            allocated[eq] += qty
            units_by_type[eq] = units_by_type.get(eq, 0) + qty

            v = qty * exw_usd_per_type.get(eq, 0.0) * trend_multiplier
            goods_value += v
            grp = EQUIPMENT_DUTY_GROUP[eq]
            if grp == "general":
                value_general += v
            elif grp == "mvs":
                value_mvs += v

            freight += qty * to_usd(_num(l.get("freight_per_unit")), cur_l, usd_to_eur)
            teu = teu_factor(l.get("container_size", "20ft"), ten_ft_teu_factor)
            teu_total += qty * teu
            baf += qty * teu * to_usd(_num(l.get("baf_per_teu")), cur_l, usd_to_eur)
            if l.get("apply_efs"):
                efs += qty * teu * to_usd(_num(l.get("efs_per_teu")), cur_l, usd_to_eur)
            dthc += qty * to_usd(_num(l.get("dthc_per_unit")), cur_l, usd_to_eur)
            trucking += qty * to_usd(_num(l.get("trucking_per_unit")), cur_l, usd_to_eur)

        origin_charges = units * to_usd(_num(s.get("origin_charges_per_unit")), cur_s, usd_to_eur)
        ocean_total = freight + baf + efs

        cif_base = goods_value + origin_charges + ocean_total
        insurance = cif_base * (insurance_pct / 100.0)
        customs_base = cif_base + insurance
        general_ratio = (value_general / goods_value) if goods_value > 0 else 0.0
        mvs_ratio = (value_mvs / goods_value) if goods_value > 0 else 0.0
        duty = customs_base * (general_ratio * customs_duty_pct + mvs_ratio * mvs_customs_duty_pct) / 100.0

        overdue_days = max(0, int(_num(s.get("port_days"))) - int(_num(s.get("free_days"))))
        port_delay = overdue_days * units * to_usd(_num(s.get("daily_rate_per_unit")), cur_s, usd_to_eur)
        # COC -> carrier demurrage; SOC / MPP -> terminal port storage (no carrier demurrage on own boxes)
        delay_label = "Demurrage" if s.get("service") == "Container Line - COC" else "Port Storage"

        extra = to_usd(_num(s.get("extra_lump_sum")), cur_s, usd_to_eur)

        if is_european_dest:
            vat_base = customs_base + duty + dthc + trucking
        else:
            vat_base = customs_base + duty + dthc
        vat = vat_base * (applied_vat / 100.0)

        total_ex_vat = (goods_value + origin_charges + ocean_total + insurance + duty +
                        dthc + trucking + port_delay + extra)
        logistics_ex_vat = total_ex_vat - goods_value

        etd, eta = s.get("etd"), s.get("eta")
        transit_days = None
        try:
            if etd is not None and eta is not None:
                transit_days = (eta - etd).days
        except Exception:
            transit_days = None

        results.append({
            "name": s["name"], "carrier": s.get("carrier", ""), "service": s.get("service", ""),
            "origin": s.get("origin", ""), "pod": s.get("pod", ""),
            "etd": etd, "eta": eta, "transit_days": transit_days,
            "units": units, "units_by_type": units_by_type,
            "goods_value": goods_value, "origin_charges": origin_charges,
            "freight": freight, "baf": baf, "efs": efs, "teu": teu_total, "insurance": insurance, "duty": duty,
            "dthc": dthc, "trucking": trucking,
            "overdue_days": overdue_days, "port_delay": port_delay, "delay_label": delay_label,
            "extra": extra, "vat": vat,
            "logistics_ex_vat": logistics_ex_vat, "total_ex_vat": total_ex_vat,
        })

    for l in lines:
        if l.get("shipment") not in names and int(_num(l.get("qty"))) > 0:
            orphan_lines.append(l)

    coverage = []
    for t in EQUIPMENT_TYPES:
        req = int(required_units.get(t, 0))
        alloc = allocated[t]
        if req == 0 and alloc == 0:
            continue
        diff = alloc - req
        status = "OK" if diff == 0 else ("Missing" if diff < 0 else "Over-allocated")
        coverage.append({"equipment": t, "required": req, "allocated": alloc, "difference": diff, "status": status})

    shipments_total = sum(r["total_ex_vat"] for r in results)
    vat_total = sum(r["vat"] for r in results)
    subtotal = shipments_total + project_level_costs_usd
    contingency = subtotal * (contingency_pct / 100.0)
    landed_ex_vat = subtotal + contingency
    recoverable_vat = vat_total * (vat_recovery_pct / 100.0)
    non_recoverable_vat = vat_total - recoverable_vat

    return {
        "shipments": results,
        "coverage": coverage,
        "coverage_ok": all(c["status"] == "OK" for c in coverage),
        "orphan_lines": orphan_lines,
        "shipments_total_ex_vat": shipments_total,
        "logistics_total_ex_vat": sum(r["logistics_ex_vat"] for r in results),
        "goods_total": sum(r["goods_value"] for r in results),
        "port_delay_total": sum(r["port_delay"] for r in results),
        "efs_total": sum(r["efs"] for r in results),
        "project_level_costs": project_level_costs_usd,
        "contingency": contingency,
        "landed_ex_vat": landed_ex_vat,
        "vat_total": vat_total,
        "recoverable_vat": recoverable_vat,
        "cash_incl_vat": landed_ex_vat + vat_total,
        "economic_cost": landed_ex_vat + non_recoverable_vat + decommissioning_pv_usd,
    }
