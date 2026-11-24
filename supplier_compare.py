# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""Delivered-to-site cost per kWh for competing BESS equipment suppliers.

Every supplier is costed on the same project (same required MWh, same route, same rates), so the comparison
shows what the FOB price per kWh does not: unit count, box weight and size, auxiliary equipment, payment terms.
All amounts in USD.
"""
import math

STD_MAX_GROSS_T = 30.48      # ISO max gross for 20ft / 40ft
TRUCK_TARE_T, ROAD_LIMIT_T = 15.0, 44.0
TEU = {"10ft": 1.0, "20ft": 1.0, "20ft HC": 1.0, "40ft": 2.0, "40ft HC": 2.0, "MPP / Breakbulk": 0.0}


def _n(v, d=0.0):
    try:
        f = float(v)
        return d if math.isnan(f) else f
    except (TypeError, ValueError):
        return d


def cost_supplier(s, target_mwh, rates):
    """s: supplier dict; rates: shared project rates. Returns a dict of results (USD)."""
    mwh_u = _n(s.get("mwh_per_unit"))
    if mwh_u <= 0 or target_mwh <= 0:
        return None
    units = math.ceil(round(target_mwh / mwh_u, 6))
    installed_mwh = units * mwh_u
    aux = math.ceil(round(units * _n(s.get("aux_per_bess")), 6))
    w, w_aux = _n(s.get("weight_t")), _n(s.get("aux_weight_t"))
    box, box_aux = s.get("container") or "20ft", s.get("aux_container") or "20ft"

    equip_bess = units * _n(s.get("price_per_unit"))
    equip_aux = aux * _n(s.get("aux_price"))
    equipment = equip_bess + equip_aux
    origin = 0.0
    if str(s.get("basis", "FOB")).upper() == "EXW":
        origin = (units + aux) * (rates["origin_truck"] + rates["origin_thc"])

    def ocean_for(n, size, weight):
        if n <= 0:
            return 0.0, 0.0, 0
        if size == "MPP / Breakbulk":
            return n * rates["mpp_per_unit"], 0.0, 0
        frt = rates["freight_40"] if TEU.get(size, 1.0) >= 2 else rates["freight_20"]
        heavy = n if weight > STD_MAX_GROSS_T else 0
        return n * (frt + TEU.get(size, 1.0) * rates["baf_per_teu"]) + heavy * rates["overweight_surcharge"], \
            n * TEU.get(size, 1.0), heavy

    oc_b, teu_b, heavy_b = ocean_for(units, box, w)
    oc_a, teu_a, heavy_a = ocean_for(aux, box_aux, w_aux)
    ocean = oc_b + oc_a

    cif = equipment + origin + ocean
    insurance = cif * rates["insurance_pct"] / 100.0
    cv = cif + insurance
    share_b = equip_bess / equipment if equipment else 1.0
    duty = cv * (share_b * rates["duty_bess_pct"] + (1 - share_b) * rates["duty_aux_pct"]) / 100.0

    abn_b = units if (w + TRUCK_TARE_T) > ROAD_LIMIT_T else 0
    abn_a = aux if (w_aux + TRUCK_TARE_T) > ROAD_LIMIT_T else 0
    dest = (units + aux) * (rates["dthc"] + rates["trucking"]) + (abn_b + abn_a) * rates["abnormal_surcharge"]

    # carrying cost of supplier payments made before the equipment is on site
    m_ship = rates["months_ship_to_site"]
    m_adv = m_ship + _n(s.get("lead_weeks")) / 4.345
    financing = equipment * (_n(s.get("adv_pct")) / 100.0 * m_adv + _n(s.get("pre_pct")) / 100.0 * m_ship) \
        * rates["fin_rate_pct"] / 100.0 / 12.0

    vat = (cv + duty + dest) * rates["vat_pct"] / 100.0
    vat_cost = vat * (1 - rates["vat_recovery_pct"] / 100.0)

    logistics = origin + ocean + insurance + duty + dest
    total = equipment + logistics + financing + vat_cost
    kwh = installed_mwh * 1000.0
    flags = []
    if heavy_b or heavy_a:
        flags.append(f"Heavy box > {STD_MAX_GROSS_T} t ({heavy_b + heavy_a}) — SOC / heavy-tested boxes")
    if abn_b or abn_a:
        flags.append(f"Abnormal road load ({abn_b + abn_a})")
    if installed_mwh > target_mwh * 1.02:
        flags.append(f"Oversized by {installed_mwh - target_mwh:,.1f} MWh")
    return {
        "units": units, "aux": aux, "installed_mwh": installed_mwh, "teu": teu_b + teu_a,
        "tonnes": units * w + aux * w_aux, "equipment": equipment, "origin": origin, "ocean": ocean,
        "insurance": insurance, "duty": duty, "dest": dest, "financing": financing, "vat_cost": vat_cost,
        "logistics": logistics, "total": total,
        "fob_per_kwh": (equipment / kwh) if kwh else 0.0,
        "site_per_kwh": (total / kwh) if kwh else 0.0,
        "site_per_req_kwh": total / (target_mwh * 1000.0),
        "logistics_per_kwh": (logistics / kwh) if kwh else 0.0,
        "uplift_pct": ((total - equipment) / equipment * 100.0) if equipment else 0.0,
        "flags": flags,
    }
