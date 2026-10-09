import pandas as pd

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
    bess_capacity_mwh, decom_cost_per_kwh
):
    # Total containers calculation
    total_containers_project = max(1, bess_count + oog_count + mvs_count + transformer_count + access_count + solar_count)

    # 1. Trended EXW Equipment Cost
    base_exw_total = (
        (bess_count * bess_exw) + (oog_count * oog_exw) + 
        (mvs_count * mvs_exw) + (transformer_count * transformer_exw) + 
        (access_count * access_exw) + (solar_count * solar_exw)
    )
    trended_exw = base_exw_total * trend_multiplier

    # 2. Origin Port Charges based on Hyperstrong quotation (23,828 CNY lumpsum baseline)
    china_origin_charges_cny = 23828.0
    china_origin_charges_usd = (china_origin_charges_cny / 7.2) * trend_multiplier
    
    china_inland_drayage = china_origin_charges_usd * 0.6
    china_origin_thc = china_origin_charges_usd * 0.4

    # 3. Ocean Freight (Quotation baseline: $15,000 per container from Yantian)
    total_base_ocean_freight = (
        (bess_count * 15000.0) +
        (oog_count * 15000.0) +
        (mvs_count * 15000.0) +
        (transformer_count * 15000.0) +
        (access_count * 15000.0) +
        (solar_count * 15000.0)
    ) * trend_multiplier

    # 4. BAF (Bunker Adjustment Factor)
    total_baf_ocean = (
        (bess_count * baf_bess) +
        (oog_count * baf_oog) +
        (mvs_count * baf_mvs) +
        (transformer_count * baf_trans) +
        (access_count * baf_access) +
        (solar_count * baf_solar)
    ) * trend_multiplier

    # 5. Destination THC & Local Charges
    destination_thc_total = (
        (bess_count * dthc_bess) +
        (oog_count * dthc_oog) +
        (mvs_count * dthc_mvs) +
        (transformer_count * dthc_trans) +
        (access_count * dthc_access) +
        (solar_count * dthc_solar)
    ) * trend_multiplier

    # CIF Value for Insurance calculation
    cif_value_base = trended_exw + china_inland_drayage + china_origin_thc + total_base_ocean_freight + total_baf_ocean
    insurance_total_usd = cif_value_base * (insurance_pct / 100.0)

    # Customs Duty
    bess_mvs_exw_val = (bess_count * bess_exw) + (oog_count * oog_exw) + (mvs_count * mvs_exw) + (transformer_count * transformer_exw) + (access_count * access_exw)
    customs_duty_usd = (bess_mvs_exw_val * trend_multiplier) * (customs_duty_pct / 100.0)

    # Inland Drayage (Port to Site)
    inland_drayage_total_usd = (
        (bess_count * drayage_bess) +
        (oog_count * drayage_oog) +
        (mvs_count * drayage_mvs) +
        (transformer_count * drayage_trans) +
        (access_count * drayage_access) +
        (solar_count * drayage_solar)
    ) * trend_multiplier

    # Regulatory and Site Services
    active_regulatory_permits = local_regulatory_permits if include_regulatory else 0.0
    active_mot_approval = mot_total_approval_cost if include_mot_approval else 0.0
    active_site_crane = site_crane_unloading if include_site_crane else 0.0
    active_heavy_lift = heavy_lift_survey_cost if requires_heavy_lift else 0.0

    # Demurrage & Storage calculation
    excess_port_days = max(0, actual_port_days - free_days)
    demurrage_total_usd = excess_port_days * demurrage_daily_rate * float(bess_count + oog_count + mvs_count + transformer_count)
    external_storage_total_usd = (ext_storage_days * ext_storage_daily_rate * float(bess_count + oog_count)) if use_external_storage else 0.0

    # Decommissioning Provision (EU Benchmark)
    decommissioning_total_usd = (bess_count + oog_count) * bess_capacity_mwh * 1000.0 * decom_cost_per_kwh if dest_country_code != "IL" else 0.0

    # Subtotal before contingency
    subtotal_before_contingency = (
        trended_exw + china_inland_drayage + china_origin_thc +
        total_base_ocean_freight + total_baf_ocean + destination_thc_total +
        insurance_total_usd + customs_duty_usd + inland_drayage_total_usd +
        active_regulatory_permits + active_mot_approval + active_site_crane +
        active_heavy_lift + demurrage_total_usd + external_storage_total_usd +
        epr_recycling_total_usd + battery_passport_total_usd
    )

    contingency_usd = subtotal_before_contingency * 0.05
    total_landed_cost_ex_vat = subtotal_before_contingency + contingency_usd

    # Incoterm Scope Adjustments
    if incoterm_code == "EXW":
        supplier_scope_total = trended_exw
    elif incoterm_code == "FOB":
        supplier_scope_total = trended_exw + china_inland_drayage + china_origin_thc
    elif incoterm_code == "CIF":
        supplier_scope_total = trended_exw + china_inland_drayage + china_origin_thc + total_base_ocean_freight + total_baf_ocean + insurance_total_usd
    elif incoterm_code == "DAP":
        supplier_scope_total = total_landed_cost_ex_vat - inland_drayage_total_usd - customs_duty_usd
    else:  # DDP
        supplier_scope_total = total_landed_cost_ex_vat

    economic_cost_ex_vat = total_landed_cost_ex_vat + decommissioning_total_usd

    # VAT Calculation
    vatable_base_for_calculation = total_landed_cost_ex_vat if not vat_paid_by_supplier else 0.0
    total_vat_amount = vatable_base_for_calculation * (applied_vat / 100.0)
    non_recoverable_vat = total_vat_amount * (1.0 - (vat_recovery_pct / 100.0))
    total_cash_requirement_incl_vat = total_landed_cost_ex_vat + non_recoverable_vat

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
        "decommissioning_total_usd": decommissioning_total_usd
    }
