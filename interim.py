# © Terra Vol. All rights reserved. Proprietary and confidential — see LICENSE.
"""Site readiness and interim storage: what to do with equipment that arrives before the site can receive it.

For each shipment the gap = days between "equipment could be on site" and "site can receive it" (site-ready date,
pushed past months in which heavy trucks cannot reach the site). Options for the gap, all in USD:
  A. Hold at the factory (delay the sailing)       B. Keep in the port
  C. Interim storage yard (bonded or duty-paid)     D. Deliver to the site anyway (temporary pad)
"""
import math
from datetime import date, timedelta

OPTIONS = ["A. Hold at factory (later sailing)", "B. Keep in port", "C. Interim storage yard", "D. Deliver to site (temporary pad)"]


def effective_ready(site_ready, no_go_months):
    """First date on or after site_ready that is not in a no-go month (1-12)."""
    if not site_ready:
        return None
    d = site_ready
    for _ in range(13):
        if d.month not in no_go_months:
            return d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return d


def soc_cost(gap, n, interval_days, per_visit):
    if gap <= 0 or interval_days <= 0:
        return 0.0
    return math.floor(gap / interval_days) * n * per_visit


def options_for(gap, n_bess, n_other, value_per_unit, vat_per_unit, r, already_sailed, port_days_base):
    """Cost and feasibility of each option for one shipment. r = rates dict (USD). Returns list of dicts."""
    n = n_bess + n_other
    out = []
    if gap <= 0 or n <= 0:
        return out
    soc = soc_cost(gap, n_bess, r["soc_interval"], r["soc_cost"])

    # A. factory
    a_cost = n * r["factory_day"] * max(0, gap - r["factory_free_days"]) + n * r["rebook_per_unit"]
    a_notes = []
    if already_sailed:
        a_notes.append("vessel already sailed / ETD passed")
    if r["pay_on_original_date"]:
        a_notes.append("supplier payment still due on the original date")
    if gap < 7:
        a_notes.append("wait shorter than one weekly sailing — not worth re-booking")
    a_notes.append("a later vessel with space is not guaranteed")
    out.append({"option": OPTIONS[0], "cost": a_cost, "feasible": (not already_sailed) and gap >= 7, "notes": a_notes})

    # B. port
    port_total = port_days_base + gap
    b_cost = n * r["port_day"] * max(0, port_total - r["port_free_days"]) - n * r["port_day"] * max(0, port_days_base - r["port_free_days"])
    b_cost += soc
    b_notes = [f"{port_total} days in port"]
    b_ok = True
    if r["port_max_days"] and port_total > r["port_max_days"]:
        b_ok = False
        b_notes.append(f"port allows dangerous goods for {r['port_max_days']} days only")
    if r["port_unit_limit"] and n_bess > r["port_unit_limit"]:
        b_ok = False
        b_notes.append(f"port limit {r['port_unit_limit']} BESS at a time")
    out.append({"option": OPTIONS[1], "cost": b_cost, "feasible": b_ok, "notes": b_notes})

    # C. interim yard
    months = math.ceil(gap / 30.0)
    c_fixed = n_bess * r["yard_haul_bess"] + n_other * r["yard_haul_other"] + n * 2 * r["yard_lift"] + n * r["yard_extra_permit"]
    c_store = gap * (n_bess * r["yard_day_bess"] + n_other * r["yard_day_other"])
    c_ins = months * n * value_per_unit * r["yard_ins_permille"] / 1000.0
    c_cost = c_fixed + c_store + c_ins + soc
    c_notes = []
    stored_value = n * value_per_unit
    if r["yard_ins_cap"] and stored_value > r["yard_ins_cap"]:
        c_notes.append(f"stored value exceeds the yard's insurance limit — extend the cover "
                       f"({stored_value / r['yard_ins_cap']:.1f}× the limit)")
    if r["bonded"] and vat_per_unit > 0:
        benefit = n * vat_per_unit * r["fin_rate"] / 100.0 * gap / 365.0
        c_cost -= benefit
        c_notes.append(f"stored under customs bond: import VAT deferred (financing benefit {benefit:,.0f} USD deducted)")
    c_notes.append("yard does not cover inherent vice (battery self-discharge) or war damage — check the contract")
    out.append({"option": OPTIONS[2], "cost": c_cost, "feasible": True, "notes": c_notes,
                "breakdown": {"haul in, lifts & permits": c_fixed, "storage": c_store, "insurance": c_ins, "SoC maintenance": soc}})

    # D. site temporary pad
    d_cost = r["pad_lump"] + gap * r["pad_security_day"] + soc
    d_ok = r["site_access_ok"]
    out.append({"option": OPTIONS[3], "cost": d_cost, "feasible": d_ok,
                "notes": [] if d_ok else ["heavy-load access to the site is not ready"]})
    return out


def deliver(start, units, per_day, no_go_months):
    """Deliver `units` from `start` at `per_day`, skipping no-go months. Returns (first day, last day)."""
    day = effective_ready(start, no_go_months)
    first, left = day, units
    while True:
        day = effective_ready(day, no_go_months)
        left -= per_day
        if left <= 0:
            return first, day
        day = day + timedelta(days=1)


def best(options):
    ok = [o for o in options if o["feasible"]]
    return min(ok, key=lambda o: o["cost"]) if ok else None


def breakeven_days(r, port_days_base):
    """Days of waiting after which the interim yard is cheaper than the port (per BESS unit, ignoring SoC & insurance)."""
    port_extra = r["port_day"] - r["yard_day_bess"]
    if port_extra <= 0:
        return None
    fixed = r["yard_haul_bess"] + 2 * r["yard_lift"] + r["yard_extra_permit"]
    free_left = max(0, r["port_free_days"] - port_days_base)
    return free_left + math.ceil(fixed / port_extra)
