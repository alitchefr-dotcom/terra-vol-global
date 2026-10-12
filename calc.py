import requests

from decommissioning import (
    calculate_decommissioning,
    decommissioning_scenarios,
    DECOM_SCENARIOS_USD_PER_KWH,
)


def get_live_exchange_rate(base_currency="USD", target_currency="EUR"):
    """Fetches live exchange rate using a free public API with fallback."""
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

    # Fallback default rates if offline or API fails
    fallbacks = {"EUR": 0.92, "USD": 1.0}
    return fallbacks.get(target_currency, 1.0)


def convert_currency(amount_in_usd, from_curr="USD", to_curr="EUR", custom_rate=0.92):
    """Converts amount between USD and EUR."""
    if "EUR" in to_curr or to_curr == "EUR":
        return amount_in_usd * custom_rate
    return amount_in_usd


def format_currency(amount, curr_code="EUR"):
    """Formats amount into a clean currency string."""
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
    trend_multiplier, insurance_pct, customs_duty_pct, applied_vat, vat_recovery_pct,
    vat_paid_by_supplier, incoterm_code, dest_country_code,
    local_regulatory_permits, mot_total_approval_cost, include_regulatory, include_mot_approval,
    site_crane_unloading, include_site_crane,
    epr_recycling_total_usd, battery_passport_total_usd,
    requires_heavy_lift, heavy_lift_survey_cost,
    actual_port_days, free_days, demurrage_daily_rate, use_external_storage, ext_storage_days, ext_storage_daily_rate, include_delay_scenario,
    bess_capacity_mwh, decom_cost_per_kwh,
    # --- decommissioning params (defaults keep existing calls working) ---
    include_oog_in_decom=False,
    decom_cost_currency="USD",
    decom_scenario=None,            # "low" / "base" / "high" overrides decom_cost_per_kwh (USD presets)
    usd_to_eur=0.92,
    years_to_decom=20,
    decom_discount_rate=0.0,
    decom_residual_per_kwh=0.0,
    apply_decommissioning=None,
):
    total_containers_project = max(1, bess_count + oog_count + mvs_count + transformer_count + access_count + solar_count)

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

    china_inland_drayage = 2200.0 * (total_containers_project / 10)
    china_origin_thc = 1300.0 * (total_containers_project / 10)

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
    non_solar_exw = trended_exw - total_solar_exw
    customs_valuation_base_usd = cif_valuation_base + insurance_total_usd
    non_solar_ratio = (non_solar_exw / trended_exw) if trended_exw > 0 else 1.0

    customs_duty_usd = (customs_valuation_base_usd * non_solar_ratio) * (customs_duty_pct / 100.0)
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

    # Decommissioning / end-of-life provision (not applied in Israel by default)
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
    # EPR recycling and decommissioning may both include recycling cost: flag possible double counting.
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
    ddp_contingency_pct = 5.0
    contingency_usd = buyer_supply_chain_total * (ddp_contingency_pct / 100.0)
    total_landed_cost_ex_vat = buyer_supply_chain_total + contingency_usd

    # Economic cost includes the (discounted) decommissioning provision;
    # operational cash requirement does not (future provision).
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
        "external_storage_total_usd": external_storage_total_usd if include_delay_scenario else 0.0,
    }
