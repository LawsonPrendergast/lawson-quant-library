import pytest
import pandas as pd

from lawson_quant_library.portfolio.portfolio import Leg, Portfolio

def test_portfolio_symbols():
    legs = (Leg('OPT1', "call", 100.0, '2025-01-17', qty=1), Leg('OPT2', 'PUT', 100.0, '2025-01-17', qty=1))
    p = Portfolio(name='test', legs=legs)

    assert p.symbols() == ['OPT1', 'OPT2']


def test_portfolio_value_from_prices():
    legs = (
        Leg("OPT1", "call", 100.0, "2025-01-17", qty=1),
        Leg("OPT2", "put", 100.0, "2025-01-17", qty=-1),
    )
    p = Portfolio(name="test", legs=legs)

    prices = {
        "OPT1": 5.0,
        "OPT2": 2.0,
    }

    assert p.value_from_prices(prices) == pytest.approx(3.0)



def test_portfolio_cost_mid():
    legs = (
        Leg("OPT1", "call", 100.0, "2025-01-17", qty=1, mid=5.0),
        Leg("OPT2", "put", 100.0, "2025-01-17", qty=-1, mid=2.0),
    )
    p = Portfolio(name="test", legs=legs)

    assert p.cost_mid() == pytest.approx(3.0)


def test_portfolio_aggregate_greeks():
    legs = (
        Leg("OPT1", "call", 100.0, "2025-01-17", qty=1),
        Leg("OPT2", "put", 100.0, "2025-01-17", qty=-1),
    )
    p = Portfolio(name="test", legs=legs)

    greeks = {
        "OPT1": {"delta": 0.6, "gamma": 0.02},
        "OPT2": {"delta": -0.4, "gamma": 0.01},
    }

    out = p.aggregate_greeks(greeks)

    assert out["delta"] == pytest.approx(1.0)
    assert out["gamma"] == pytest.approx(0.01)