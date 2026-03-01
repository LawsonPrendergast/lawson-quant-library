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
from lawson_quant_library.instrument.option.eq_option import EQOption
from lawson_quant_library.util import Calendar

def select_moneyness_slice(df: pd.DataFrame, n: int) -> pd.DataFrame:
    '''Return the options across moneyness'''
    return (
        df.sort_values(by="moneyness", key=lambda s: (s - 1).abs())
        .head(n)
        .copy()
    )
    
def ttm_to_tenor(ttm: float) -> str:
    """
    Map time-to-maturity in years to standardized tenor buckets.
    """
    days = float(ttm) * 365.0
    if days <= 2:
        return "1D"
    if days <= 10:
        return "1W"
    if days <= 40:
        return "1M"
    if days <= 120:
        return "3M"
    if days <= 240:
        return "6M"
    return "1Y"


def bucket_moneyness(df: pd.DataFrame, targets: list[float]) -> pd.DataFrame:
    """
    Select the nearest option to each target moneyness bucket and stamp the bucket label
    (so columns are exactly the targets, not rounded values from the chain).
    """
    out = df.copy()
    out["moneyness"] = pd.to_numeric(out["moneyness"], errors="coerce")
    out = out[pd.notna(out["moneyness"])].copy()
    if out.empty:
        return out

    selected = []
    for m in targets:
        idx = (out["moneyness"] - float(m)).abs().idxmin()
        row = out.loc[idx].copy()
        row["bucket"] = float(m)  # force bucket label to the target
        selected.append(row)

    res = pd.DataFrame(selected)

    # If sparse strikes cause two targets to hit the same option, keep one per bucket
    if not res.empty and "bucket" in res.columns and "moneyness" in res.columns:
        res["bucket_dist"] = (res["moneyness"] - res["bucket"]).abs()
        res = (
            res.sort_values(["bucket", "bucket_dist"])
               .drop_duplicates(subset=["bucket"], keep="first")
               .drop(columns=["bucket_dist"])
               .copy()
        )

    return res

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
    moneyness_targets: list[float] | None = None,
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

    rows: list[dict[str, Any]] = []

    if moneyness_targets is None:
        # Bloomberg-style equity display buckets (K/Spot)
        moneyness_targets = [0.8, 0.9, 1.0, 1.1, 1.2]

    for exp in expiries_to_use:
        # a) Pull chain for this expiry
        df = adapter.normalized_chain(exp, option_type)

        # b) Add derived columns used by the surface build
        df = adapter.with_time_to_expiry(df, as_of)
        df = adapter.with_moneyness(df, spot)

        if "moneyness" in df.columns:
            df["moneyness"] = pd.to_numeric(df["moneyness"], errors="coerce")

        # Use Yahoo-provided IVs directly (no solver)
        if "impliedVolatility" in df.columns:
            df["impliedVolatility"] = pd.to_numeric(df["impliedVolatility"], errors="coerce")

        df = df[(df["ttm"].notna()) & (df["strike"].notna()) & (df["ttm"] > 0)].copy()
        if "impliedVolatility" in df.columns:
            df = df[df["impliedVolatility"].notna() & (df["impliedVolatility"] > 0)].copy()

            # Tenor buckets (row index)
            df["tenor"] = df["ttm"].apply(ttm_to_tenor)

            # Moneyness buckets (column labels)
            df = bucket_moneyness(df, moneyness_targets)
            if df.empty:
                continue

        for _, r0 in df.iterrows():
            ttm = float(r0["ttm"])
            mny = float(r0["moneyness"]) if "moneyness" in r0 and pd.notna(r0["moneyness"]) else float("nan")
            iv = float(r0["impliedVolatility"]) if "impliedVolatility" in r0 and pd.notna(r0["impliedVolatility"]) else float("nan")
            if pd.isna(iv) or iv <= 0:
                continue

            bucket = float(r0.get("bucket", mny)) if pd.notna(r0.get("bucket", pd.NA)) else float("nan")
            tenor = str(r0.get("tenor", ttm_to_tenor(ttm)))
            rows.append(
                {
                    "ticker": ticker,
                    "tenor": tenor,
                    "bucket": bucket,
                    "iv": iv,
                    "expiry": exp,
                    "ttm": ttm,
                    "moneyness": mny,
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    surface = out.pivot_table(
        index="tenor",
        columns="bucket",
        values="iv",
        aggfunc="mean",
    )

    # enforce consistent column set/order
    surface = surface.reindex(columns=moneyness_targets)

    # enforce a sensible tenor order if present
    tenor_order = ["1D", "1W", "1M", "3M", "6M", "1Y"]
    surface = surface.reindex(index=[t for t in tenor_order if t in surface.index])

    return surface


def build_surface_points_yahoo(
    ticker: str,
    *,
    as_of: pd.Timestamp,
    r: float = 0.05,
    q: float = 0.0,
    option_type: str = "call",
    n_expiries: int = 4,
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
    )


# Backwards-compatible alias (Yahoo default)
build_surface_points = build_surface_points_yahoo