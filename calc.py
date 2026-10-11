from __future__ import annotations
from typing import Dict, Optional
import requests

CATEGORIES = ("bess", "oog", "mvs", "trans", "access", "solar")

DEFAULT_OCEAN_FREIGHT_PER_CONTAINER_USD = 15_000.0
DEFAULT_ORIGIN_CHARGES_CNY = 23_828.0
DEFAULT_CNY_PER_USD = 7.2

DEMURRAGE_CATEGORIES = ("bess", "oog", "mvs", "trans")
DEFAULT_DUTIABLE = ("bess", "oog", "mvs", "trans", "access")
SUPPORTED_INCOTERMS = ("EXW", "FOB", "CFR", "CIF", "DAP", "DDP")

def get_live_exchange_rate(base_currency="USD", target_currency="EUR"):
    try:
        url = f"https://open.er-api.com/v6/latest/{base_currency}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rates = data.get("rates", {})
            if target_currency in rates:
                return float(rates[target_currency])
    except Exception:
        pass
    return 0.92 if target_currency == "EUR" else 1.0

def convert_currency(amount, from_currency, to_currency, usd_to_eur_rate):
    if from_currency == to_currency:
        return amount
    if from_currency == "USD" and to_currency == "EUR":
        return amount * usd_to_eur_rate
    elif from_currency == "EUR" and to_currency == "USD":
        return amount / usd_to_eur_rate if usd_to_eur_rate > 0 else amount
    return amount

def format_currency(amount, currency):
    if currency == "EUR":
        return f"€{amount:,.0f}"
    elif currency == "USD":
        return f"${amount:,.0f}"
    return f"{amount:,.0f}"

def calculate_project_costs(
    bess_count, bess_exw,
    oog_count, oog_exw,
    mvs_count, mvs_exw,
    transformer_count, transformer_exw,
    access_count, access_exw,
    solar_count, solar_exw,
    unit_freight_bess, unit_freight_oog,
    unit_freight_mvs, unit_freight_trans,
    unit_freight_access, unit_freight_solar,
    baf_bess, baf_oog, baf_mvs, baf_trans, baf_access, baf_solar,
    dthc_bess, dthc_oog, dthc_mvs, dthc_trans, dthc_access, dthc_solar,
    drayage_bess, drayage_oog, drayage_mvs,
    drayage_trans, drayage_access, drayage_solar,
    trend_multiplier, insurance_pct,
    customs_duty_pct, applied_vat, vat_recovery_pct,
    vat_paid_by_supplier, incoterm_code,
    dest_country_code,
    local_regulatory_permits, mot_total_approval_cost,
    include_regulatory, include_mot_approval,
    site_crane_unloading, include_site_crane,
    epr_recycling_total_usd, battery_passport_total_usd,
    requires_heavy_lift, heavy_lift_survey_cost,
    actual_port_days, free_days, demurrage_daily_rate,
    use_external_storage, ext_storage_days,
    ext_storage_daily_rate, include_delay_scenario,
    bess_capacity_mwh, decom_cost_per_kwh,
    *,
    logistics_trend_multiplier: Optional[float] = None,
    origin_charges_cny: float = DEFAULT_ORIGIN_CHARGES_CNY,
    cny_per_usd: float = DEFAULT_CNY_PER_USD,
    origin_charges_per_container: bool = False,
    origin_inland_share: float = 0.6,
    insured_value_factor: float = 1.0,
    duty_rate_by_category: Optional[Dict[str, float]] = None,
    contingency_pct: float = 5.0,
    delay_extra_days: int = 7,
    decom_discount_rate_pct: float = 0.0,
    decom_years: float = 0.0,
):
    counts = dict(zip(CATEGORIES, (bess_count, oog_count, mvs_count,
                                map_transformer := transformer_count, access_count, solar_count))) # adjusted mapping
    # Correcting mapping explicitly:
    counts = dict(zip(CATEGORIES, (bess_count, oog_count, mvs_count, transformer_count, access_count, solar_count)))
    exw_unit = dict(zip(CATEGORIES, (bess_exw, oog_exw, mvs_exw,
                                    transformer_exw, access_exw, solar_exw)))
    freight_unit = dict(zip(CATEGORIES, (unit_freight_bess, unit_freight_oog, unit_freight_mvs,
                                         unit_freight_trans, unit_freight_access, unit_freight_solar)))
    baf_unit = dict(zip(CATEGORIES, (baf_bess, baf_oog, baf_mvs, baf_trans, baf_access, baf_solar)))
    dthc_unit = dict(zip(CATEGORIES, (dthc_bess, dthc_oog, dthc_mvs, dthc_trans, dthc_access, dthc_solar)))
    dray_unit = dict(zip(CATEGORIES, (drayage_bess, drayage_oog, drayage_mvs,
                                         drayage_trans, drayage_access, drayage_solar)))

    incoterm = (incoterm_code or "").upper()
    if incoterm not in SUPPORTED_INCOTERMS:
        raise ValueError(f"Unsupported incoterm {incoterm_code!r}")

    equip_trend = trend_multiplier
    logi_trend = trend_multiplier if logistics_trend_multiplier is None else logistics_trend_multiplier

    def _total(unit_costs):
        return sum(counts[c] * unit_costs[c] for c in CATEGORIES)

    total_containers_project = max(1, sum(counts.values()))

    exw_by_cat = {c: counts[c] * exw_unit[c] * equip_trend for c in CATEGORIES}
    trended_exw = sum(exw_by_cat.values())

    origin_usd = origin_charges_cny / cny_per_usd
    if origin_charges_per_container:
        origin_usd *= total_containers_project
    origin_usd *= logi_trend
    china_inland_drayage = origin_usd * origin_inland_share
    china_origin_thc = origin_usd - china_inland_drayage

    total_base_ocean_freight = _total(freight_unit) * logi_trend
    total_baf_ocean = _total(baf_unit) * logi_trend
    destination_thc_total = _total(dthc_unit) * logi_trend
    inland_drayage_total_usd = _total(dray_unit) * logi_trend

    cfr_value = trended_exw + china_inland_drayage + china_origin_thc + total_base_ocean_freight + total_baf_ocean
    insurance_total_usd = cfr_value * insured_value_factor * (insurance_pct / 100.0)
    customs_value = cfr_value + insurance_total_usd

    duty_rates = {c: (customs_duty_pct if c in DEFAULT_DUTIABLE else 0.0) for c in CATEGORIES}
    if duty_rate_by_category:
        duty_rates.update(duty_rate_by_category)
    if trended_exw > 0:
        customs_duty_usd = sum(
            customs_value * (exw_by_cat[c] / trended_exw) * (duty_rates[c] / 100.0) for c in CATEGORIES
        )
    else:
        customs_duty_usd = 0.0

    active_regulatory_permits = local_regulatory_permits if include_regulatory else 0.0
    active_mot_approval = mot_total_approval_cost if include_mot_approval else 0.0
    active_site_crane = site_crane_unloading if include_site_crane else 0.0
    active_heavy_lift = heavy_lift_survey_cost if requires_heavy_lift else 0.0

    port_days = actual_port_days + (delay_extra_days if include_delay_scenario else 0)
    excess_port_days = max(0, port_days - free_days)
    demurrage_containers = sum(counts[c] for c in DEMURRAGE_CATEGORIES)
    demurrage_total_usd = excess_port_days * demurrage_daily_rate * float(demurrage_containers)
    external_storage_total_usd = (
        ext_storage_days * ext_storage_daily_rate * float(counts["bess"] + counts["oog"])
        if use_external_storage else 0.0
    )

    total_mwh = (counts["bess"] + counts["oog"]) * bess_capacity_mwh
    is_israel = (dest_country_code or "").upper() == "IL"
    decommissioning_total_usd = 0.0 if is_israel else total_mwh * 1000.0 * decom_cost_per_kwh
    if decom_years > 0 and decom_discount_rate_pct > 0:
        decommissioning_pv_usd = decommissioning_total_usd / ((1 + decom_discount_rate_pct / 100.0) ** decom_years)
    else:
        decommissioning_pv_usd = decommissioning_total_usd

    cost_lines = {
        "trended_exw": trended_exw,
        "china_inland_drayage": china_inland_drayage,
        "china_origin_thc": china_origin_thc,
        "ocean_freight": total_base_ocean_freight,
        "baf": total_baf_ocean,
        "destination_thc": destination_thc_total,
        "insurance": insurance_total_usd,
        "customs_duty": customs_duty_usd,
        "inland_drayage": inland_drayage_total_usd,
        "regulatory_permits": active_regulatory_permits,
        "mot_approval": active_mot_approval,
        "site_crane": active_site_crane,
        "heavy_lift_survey": active_heavy_lift,
        "demurrage": demurrage_total_usd,
        "external_storage": external_storage_total_usd,
        "epr_recycling": epr_recycling_total_usd,
        "battery_passport": battery_passport_total_usd,
    }
    subtotal_before_contingency = sum(cost_lines.values())
    contingency_usd = subtotal_before_contingency * (contingency_pct / 100.0)
    total_landed_cost_ex_vat = subtotal_before_contingency + contingency_usd
    economic_cost_ex_vat = total_landed_cost_ex_vat + decommissioning_pv_usd

    origin_scope = trended_exw + china_inland_drayage + china_origin_thc
    cfr_scope = origin_scope + total_base_ocean_freight + total_baf_ocean
    cif_scope = cfr_scope + insurance_total_usd
    dap_scope = cif_scope + destination_thc_total + inland_drayage_total_usd
    scope_by_incoterm = {
        "EXW": trended_exw,
        "FOB": origin_scope,
        "CFR": cfr_scope,
        "CIF": cif_scope,
        "DAP": dap_scope,
        "DDP": dap_scope + customs_duty_usd,
    }
    supplier_scope_total = scope_by_incoterm[incoterm]

    vatable_base = 0.0 if vat_paid_by_supplier else subtotal_before_contingency
    total_vat_amount = vatable_base * (applied_vat / 100.0)
    recoverable_vat = total_vat_amount * (vat_recovery_pct / 100.0)
    non_recoverable_vat = total_vat_amount - recoverable_vat
    total_cash_requirement_incl_vat = total_landed_cost_ex_vat + non_recoverable_vat
    peak_cash_requirement_incl_vat = total_landed_cost_ex_vat + total_vat_amount

    return {
        "total_containers_project": total_containers_project,
        "trended_exw": trended_exw,
        "china_inland_drayage": china_inland_drayage,
        "china_origin_thc": china_origin_thc,
        "total_base_ocean_freight": total_base_ocean_freight,
        "total_baf_ocean": total_baf_ocean,
        "destination_thc_total": destination_thc_total,
        "insurance_total_usd": insurance_total_usd,
        "customs_duty_usd": customs_duty_usd,
        "inland_drayage_total_usd": inland_drayage_total_usd,
        "active_regulatory_permits": active_regulatory_permits + active_mot_approval,
        "active_site_crane": active_site_crane,
        "epr_recycling_total_usd": epr_recycling_total_usd,
        "battery_passport_total_usd": battery_passport_total_usd,
        "active_heavy_lift": active_heavy_lift,
        "demurrage_total_usd": demurrage_total_usd,
        "external_storage_total_usd": external_storage_total_usd,
        "contingency_usd": contingency_usd,
        "total_landed_cost_ex_vat": total_landed_cost_ex_vat,
        "economic_cost_ex_vat": economic_cost_ex_vat,
        "total_cash_requirement_incl_vat": total_cash_requirement_incl_vat,
        "supplier_scope_total": supplier_scope_total,
        "decommissioning_total_usd": decommissioning_total_usd,
        "cost_lines": cost_lines,
        "customs_value_cif": customs_value,
        "total_vat_amount": total_vat_amount,
        "recoverable_vat": recoverable_vat,
        "non_recoverable_vat": non_recoverable_vat,
        "peak_cash_requirement_incl_vat": peak_cash_requirement_incl_vat,
        "decommissioning_pv_usd": decommissioning_pv_usd,
        "total_mwh": total_mwh,
        "landed_cost_per_mwh_ex_vat": (total_landed_cost_ex_vat / total_mwh) if total_mwh > 0 else None,
        "landed_cost_per_container_ex_vat": total_landed_cost_ex_vat / total_containers_project,
    }
