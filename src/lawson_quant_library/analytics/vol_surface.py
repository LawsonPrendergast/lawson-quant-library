"""
Vol surface analytics utilities.

This module intentionally sits ABOVE the data adaptors and pricing models.
It combines:
- option chain data (from a data adaptor)
- pricing model / implied vol solver (from instruments/models)
to produce surface "points" suitable for plotting in a notebook.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from lawson_quant_library.data.yahoo_options import YahooOptionsAdapter
from lawson_quant_library.parameter.ir_curve import IRCurve
from lawson_quant_library.parameter.div_curve import DivCurve
from lawson_quant_library.parameter.vol import EQVol
from lawson_quant_library.instrument.option.vanilla_option import EQOption


def _select_atm_slice(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Return the n rows with moneyness closest to 1.0 (ATM-ish slice).

    We start with an ATM-focused slice because Newton IV solves are most stable
    when vega is not tiny.
    """
    return (
        df.sort_values(by="moneyness", key=lambda s: (s - 1).abs())
        .head(n)
        .copy()
    )


def build_surface_points_from_adapter(
    adapter: Any,
    *,
    ticker: str,
    as_of: pd.Timestamp,
    spot: float,
    r: float = 0.05,
    q: float = 0.0,
    option_type: str = "call",
    expiries: list[Any] | None = None,
    n_expiries: int = 4,
    n_atm: int = 30,
) -> pd.DataFrame:
    """Build implied vol surface points using a provided options data adapter.

    The adapter is expected to provide:
      - normalized_chain(expiry, option_type)
      - with_time_to_expiry(df, as_of)
      - with_moneyness(df, spot)
      - expiries() if `expiries` is not provided

    Returns long-format DataFrame with: ticker, expiry, ttm, moneyness, iv
    """
    # Determine expiries to use
    if expiries is not None:
        expiries_to_use = expiries
    else:
        expiries_to_use = adapter.expiries()[:n_expiries]

    # Create flat market objects (IR, div, base vol) ONCE per ticker
    ir_curve = IRCurve(rate=r, currency="USD")
    # Dividend curve has no currency attribute by design
    div_curve = DivCurve(div_yield=q)
    base_vol = EQVol(currency="USD")

    rows: list[dict[str, Any]] = []

    for exp in expiries_to_use:
        # a) Pull chain for this expiry
        df = adapter.normalized_chain(exp, option_type)

        # b) Add derived columns used by the surface build
        df = adapter.with_time_to_expiry(df, as_of)
        df = adapter.with_moneyness(df, spot)

        # c) Basic sanity filters
        df = df[(df["ttm"] > 0) & (df["mid"] > 0)].copy()
        if df.empty:
            continue

        # d) Focus on an ATM-ish slice for solver stability
        df = _select_atm_slice(df, n_atm)

        for _, r0 in df.iterrows():
            strike = float(r0["strike"])
            maturity_date = pd.to_datetime(r0["expiry"])
            price = float(r0["mid"])
            ttm = float(r0["ttm"])
            mny = float(r0["moneyness"])

            opt = EQOption(
                strike=strike,
                maturity_date=maturity_date,
                option_type=option_type,
            )
            opt.set_market(
                spot=spot,
                ir_curve=ir_curve,
                div_curve=div_curve,
                vol=base_vol,
            )

            try:
                iv = float(
                    opt.implied_vol(
                        target_price=price,
                        reference_date=as_of,
                        initial_vol=0.30,
                    )
                )
            except Exception:
                continue

            rows.append(
                {"ticker": ticker, "expiry": exp, "ttm": ttm, "moneyness": mny, "iv": iv}
            )

    return pd.DataFrame(rows)


def build_surface_points_yahoo(
    ticker: str,
    *,
    as_of: pd.Timestamp,
    r: float = 0.05,
    q: float = 0.0,
    option_type: str = "call",
    n_expiries: int = 4,
    n_atm: int = 30,
) -> pd.DataFrame:
    """Yahoo-specific convenience wrapper around `build_surface_points_from_adapter`."""
    adapter = YahooOptionsAdapter(ticker)
    spot = float(adapter._yf.fast_info["lastPrice"])
    expiries = adapter.expiries()[:n_expiries]
    return build_surface_points_from_adapter(
        adapter,
        ticker=ticker,
        as_of=as_of,
        spot=spot,
        r=r,
        q=q,
        option_type=option_type,
        expiries=expiries,
        n_expiries=n_expiries,
        n_atm=n_atm,
    )


# Backwards-compatible alias (Yahoo default)
build_surface_points = build_surface_points_yahoo