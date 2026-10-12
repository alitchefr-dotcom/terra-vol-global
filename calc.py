import pytest
from decommissioning import calculate_decommissioning as f

def test_basic_eur_no_conversion_effect():
    # 20 x 4MWh x 75 = 6,000,000 EUR ; usd_to_eur=1 -> same number
    r = f(20, 0, 4.0, 75.0, True, usd_to_eur=1.0)
    assert r["units"] == 20
    assert r["nominal_usd"] == pytest.approx(6_000_000)
    assert r["pv_usd"] == pytest.approx(6_000_000)

def test_old_behavior_reproduces_7_5M():
    # 20 BESS + 5 OOG counted, USD, no discount -> 7.5M (the original discrepancy)
    r = f(20, 5, 4.0, 75.0, True, include_oog_in_decom=True, cost_currency="USD")
    assert r["units"] == 25
    assert r["nominal_usd"] == pytest.approx(7_500_000)

def test_oog_excluded_by_default():
    r = f(20, 5, 4.0, 75.0, True, cost_currency="USD")
    assert r["units"] == 20
    assert r["nominal_usd"] == pytest.approx(6_000_000)

def test_eur_to_usd_conversion():
    # usd_to_eur=0.92 -> 1 USD = 0.92 EUR -> 6M EUR = 6M/0.92 USD
    r = f(20, 0, 4.0, 75.0, True, cost_currency="EUR", usd_to_eur=0.92)
    assert r["nominal_usd"] == pytest.approx(6_000_000 / 0.92)

def test_discounting():
    r = f(20, 0, 4.0, 75.0, True, cost_currency="USD", discount_rate=0.04, years_to_decom=20)
    assert r["pv_usd"] == pytest.approx(6_000_000 / 1.04**20)
    assert r["pv_usd"] < r["nominal_usd"]

def test_residual_value():
    r = f(20, 0, 4.0, 75.0, True, cost_currency="USD", residual_value_per_kwh=15.0)
    assert r["nominal_usd"] == pytest.approx(20 * 4000 * 60)

def test_disabled():
    r = f(20, 5, 4.0, 75.0, False)
    assert r == {"units": 0, "nominal_usd": 0.0, "pv_usd": 0.0}

def test_zero_discount_pv_equals_nominal():
    r = f(3, 0, 5.0, 60.0, True, discount_rate=0.0)
    assert r["pv_usd"] == r["nominal_usd"]

def test_default_currency_is_usd_no_conversion():
    r = f(20, 0, 4.0, 75.0, True)
    assert r["nominal_usd"] == pytest.approx(6_000_000)

def test_scenarios():
    from decommissioning import decommissioning_scenarios as sc
    r = sc(20, 0, 4.0, True)
    assert r["low"]["nominal_usd"] == pytest.approx(20*4000*59)
    assert r["base"]["nominal_usd"] == pytest.approx(6_000_000)
    assert r["high"]["nominal_usd"] == pytest.approx(20*4000*90)
    assert sc(20, 0, 4.0, False)["base"]["nominal_usd"] == 0.0
