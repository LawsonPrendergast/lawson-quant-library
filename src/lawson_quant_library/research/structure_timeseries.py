

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, Optional

import pandas as pd

from lawson_quant_library.parameter.ir_curve import IRCurve
from lawson_quant_library.parameter.div_curve import DivCurve
from lawson_quant_library.parameter.vol import EQVol
from lawson_quant_library.portfolio.portfolio import Portfolio, Leg


# -----------------------------
# Lightweight option view
# -----------------------------

@dataclass(frozen=True)
class SimpleEuropeanOption:
    """Minimal option representation expected by BS model."""

    strike: float
    expiry: str
    right: Literal["call", "put"]


# -----------------------------
# Price time series
# -----------------------------

def build_leg_price_timeseries(
    *,
    adapter: Any,
    portfolio: Portfolio,
    start: Any,
    end: Any,
    freq: str = "B",
) -> pd.DataFrame:
    """Build per-leg and portfolio value time series using pseudo_chain_as_of.

    Returns DataFrame indexed by date with:
      - one column per leg price
      - structure_value
    """

    dates = pd.date_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq=freq)
    symbols = portfolio.symbols()

    rows = []
    for d in dates:
        chain = adapter.pseudo_chain_as_of(symbols, d)
        if chain is None or chain.empty:
            continue

        px = {}
        for _, r in chain.iterrows():
            if pd.notna(r.get("price")):
                px[str(r["contractSymbol"])] = float(r["price"])

        # require all legs
        if any(s not in px for s in symbols):
            continue

        row = {"date": d}
        for leg in portfolio.legs:
            row[f"{leg.contract_symbol}__px"] = px[leg.contract_symbol]

        row["structure_value"] = portfolio.value_from_prices(px)
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("date").sort_index()


# -----------------------------
# Risk / Greeks time series
# -----------------------------

def build_portfolio_risk_timeseries(
    *,
    adapter: Any,
    portfolio: Portfolio,
    start: Any,
    end: Any,
    spot: pd.Series,
    bs_model: Callable[..., Any],
    r: float = 0.0,
    q: float = 0.0,
    vol_mode: Literal["snapshot_iv", "flat"] = "snapshot_iv",
    flat_vol: float = 0.20,
    option_factory: Optional[Callable[[Leg], Any]] = None,
    freq: str = "B",
) -> pd.DataFrame:
    """Build portfolio value + net Greeks time series.

    bs_model must be callable as:
      model = bs_model(spot=S, ir_curve=ir, div_curve=div, vol=vol)
      greeks = model.greeks(option)
    """

    prices = build_leg_price_timeseries(
        adapter=adapter,
        portfolio=portfolio,
        start=start,
        end=end,
        freq=freq,
    )
    if prices.empty:
        return prices

    spot = spot.copy()
    spot.index = pd.to_datetime(spot.index)
    spot = spot.reindex(prices.index).dropna()
    prices = prices.loc[spot.index]

    if option_factory is None:
        def option_factory(leg: Leg) -> Any:
            return SimpleEuropeanOption(
                strike=float(leg.strike),
                expiry=str(leg.expiry),
                right=leg.right,
            )

    rows = []
    for d in prices.index:
        S = float(spot.loc[d])

        ir = IRCurve(rate=float(r), currency="USD")
        ir.set_flat_rate(float(r), reference_date=d)

        div = DivCurve(div_yield=float(q), currency="USD")
        div.set_div(float(q))

        vol = EQVol(currency="USD")

        leg_greeks: Dict[str, Dict[str, float]] = {}
        for leg in portfolio.legs:
            if vol_mode == "flat":
                sigma = float(flat_vol)
            else:
                sigma = float(leg.iv) if leg.iv is not None else float(flat_vol)

            vol.set_flat_vol(sigma, reference_date=d)
            model = bs_model(spot=S, ir_curve=ir, div_curve=div, vol=vol)
            opt = option_factory(leg)

            g = model.greeks(opt)
            leg_greeks[leg.contract_symbol] = {k: float(v) for k, v in dict(g).items()}

        net = portfolio.aggregate_greeks(leg_greeks)

        row = {
            "date": d,
            "spot": S,
            "structure_value": float(prices.loc[d, "structure_value"]),
        }
        for k, v in net.items():
            row[f"net_{k}"] = float(v)

        rows.append(row)

    return pd.DataFrame(rows).set_index("date").sort_index()


__all__ = [
    "build_leg_price_timeseries",
    "build_portfolio_risk_timeseries",
]