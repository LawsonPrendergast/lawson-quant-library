

import pandas as pd
import pytest

from lawson_quant_library.instrument.option.structures import (
    pick_expiry_closest,
    pick_atm_strike,
    pick_by_moneyness,
    pick_by_strike,
    make_atm_straddle,
    make_vertical_spread,
    make_collar,
    make_risk_reversal,
)


@pytest.fixture()
def sample_chain() -> pd.DataFrame:
    """Small, deterministic chain for unit tests.

    Columns match what structures.py expects by default.
    """
    rows = []

    # A simple spot=100 setup with moneyness = strike/spot
    spot = 100.0
    strikes = [90.0, 95.0, 100.0, 105.0, 110.0]

    # Simple mids: calls increase with strike proximity, puts similar; just deterministic.
    # Not economically perfect, but stable for selection tests.
    call_mids = {90.0: 11.0, 95.0: 7.0, 100.0: 4.0, 105.0: 2.0, 110.0: 1.0}
    put_mids = {90.0: 1.0, 95.0: 2.0, 100.0: 4.0, 105.0: 7.0, 110.0: 11.0}

    for k in strikes:
        rows.append(
            {
                "contractSymbol": f"TSTC_{int(k)}",
                "optionType": "call",
                "strike": float(k),
                "mid": float(call_mids[k]),
                "moneyness": float(k) / spot,
                "ttm": 30 / 365,
            }
        )
        rows.append(
            {
                "contractSymbol": f"TSTP_{int(k)}",
                "optionType": "put",
                "strike": float(k),
                "mid": float(put_mids[k]),
                "moneyness": float(k) / spot,
                "ttm": 30 / 365,
            }
        )

    return pd.DataFrame(rows)


def test_pick_expiry_closest_formats():
    expiries = [
        "2026-02-01",
        pd.Timestamp("2026-02-15 00:00:00"),
        "2026-03-15",
        pd.Timestamp("2026-06-20"),
    ]
    as_of = pd.Timestamp("2026-01-01")

    # 30D target: closest is 2026-02-01 (31 days)
    assert pick_expiry_closest(expiries, 30, as_of=as_of) == "2026-02-01"


def test_pick_atm_strike(sample_chain: pd.DataFrame):
    # spot=100 => ATM moneyness=1.0 should select strike=100
    k = pick_atm_strike(sample_chain, target_moneyness=1.0)
    assert k == 100.0


def test_pick_by_moneyness_call(sample_chain: pd.DataFrame):
    row = pick_by_moneyness(sample_chain, right="call", target_moneyness=1.05)
    assert row["optionType"] == "call"
    assert float(row["strike"]) == 105.0


def test_pick_by_moneyness_put(sample_chain: pd.DataFrame):
    row = pick_by_moneyness(sample_chain, right="put", target_moneyness=0.95)
    assert row["optionType"] == "put"
    assert float(row["strike"]) == 95.0


def test_pick_by_strike(sample_chain: pd.DataFrame):
    row = pick_by_strike(sample_chain, right="call", strike=110.0)
    assert row["optionType"] == "call"
    assert float(row["strike"]) == 110.0


def test_make_atm_straddle(sample_chain: pd.DataFrame):
    p = make_atm_straddle(sample_chain, expiry="2026-02-01", qty=2.0)

    assert p.name == "ATM Straddle"
    assert len(p.legs) == 2

    legs = {l.right: l for l in p.legs}
    assert legs["call"].qty == pytest.approx(2.0)
    assert legs["put"].qty == pytest.approx(2.0)
    assert legs["call"].strike == pytest.approx(100.0)
    assert legs["put"].strike == pytest.approx(100.0)


def test_make_vertical_spread(sample_chain: pd.DataFrame):
    p = make_vertical_spread(
        sample_chain,
        expiry="2026-02-01",
        right="call",
        k_long=100.0,
        k_short=105.0,
        qty=1.0,
    )

    assert len(p.legs) == 2
    long_leg = p.legs[0]
    short_leg = p.legs[1]

    assert long_leg.right == "call"
    assert short_leg.right == "call"
    assert long_leg.strike == pytest.approx(100.0)
    assert short_leg.strike == pytest.approx(105.0)
    assert long_leg.qty == pytest.approx(1.0)
    assert short_leg.qty == pytest.approx(-1.0)


def test_make_collar(sample_chain: pd.DataFrame):
    p = make_collar(
        sample_chain,
        expiry="2026-02-01",
        put_moneyness=0.95,
        call_moneyness=1.05,
        qty=3.0,
    )

    assert p.name == "Collar"
    assert len(p.legs) == 2

    # collar: long put (qty +), short call (qty -)
    put_leg = next(l for l in p.legs if l.right == "put")
    call_leg = next(l for l in p.legs if l.right == "call")

    assert put_leg.strike == pytest.approx(95.0)
    assert call_leg.strike == pytest.approx(105.0)
    assert put_leg.qty == pytest.approx(3.0)
    assert call_leg.qty == pytest.approx(-3.0)


def test_make_risk_reversal_bullish(sample_chain: pd.DataFrame):
    p = make_risk_reversal(
        sample_chain,
        expiry="2026-02-01",
        put_moneyness=0.95,
        call_moneyness=1.05,
        qty=1.0,
        direction="bullish",
    )

    assert "Bullish" in p.name
    assert len(p.legs) == 2

    # bullish RR: long call, short put
    call_leg = next(l for l in p.legs if l.right == "call")
    put_leg = next(l for l in p.legs if l.right == "put")

    assert call_leg.strike == pytest.approx(105.0)
    assert put_leg.strike == pytest.approx(95.0)
    assert call_leg.qty == pytest.approx(1.0)
    assert put_leg.qty == pytest.approx(-1.0)


def test_make_risk_reversal_bearish(sample_chain: pd.DataFrame):
    p = make_risk_reversal(
        sample_chain,
        expiry="2026-02-01",
        put_moneyness=0.95,
        call_moneyness=1.05,
        qty=2.0,
        direction="bearish",
    )

    assert "Bearish" in p.name
    assert len(p.legs) == 2

    # bearish RR: long put, short call
    call_leg = next(l for l in p.legs if l.right == "call")
    put_leg = next(l for l in p.legs if l.right == "put")

    assert put_leg.strike == pytest.approx(95.0)
    assert call_leg.strike == pytest.approx(105.0)
    assert put_leg.qty == pytest.approx(2.0)
    assert call_leg.qty == pytest.approx(-2.0)