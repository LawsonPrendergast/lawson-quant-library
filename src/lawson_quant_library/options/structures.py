

"""Option structure builders.

Goal: provide notebook-friendly builders that work directly on a normalized options chain
DataFrame (e.g., from YahooOptionsAdapter.snapshot(..., add_analytics=True)).

Design principles
- Keep builders thin and deterministic.
- Return a simple Portfolio object (list of Legs) that can be priced/greeked elsewhere.
- Do not couple to a specific data adapter; operate on DataFrames.

Expected chain columns (minimum)
- contractSymbol (str)
- strike (float)
- optionType / type / right  (call/put indicator)
- mid (float)  [or lastPrice fallback already applied by adapter]
- moneyness (float)  strike / spot
- ttm (float)  time-to-maturity in years
- as_of (datetime-like) optional

You can pass a mapping of column names if your adapter differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

OptionRight = Literal["call", "put"]


# -----------------------------
# Core data containers
# -----------------------------


@dataclass(frozen=True)
class Leg:
    """One option leg in a structure."""

    contract_symbol: str
    right: OptionRight
    strike: float
    expiry: str
    qty: float = 1.0

    # Optional metadata (useful for audit/debug)
    mid: Optional[float] = None
    iv: Optional[float] = None
    ttm: Optional[float] = None
    moneyness: Optional[float] = None


@dataclass(frozen=True)
class Portfolio:
    """A simple portfolio of option legs."""

    name: str
    legs: Tuple[Leg, ...]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "contractSymbol": l.contract_symbol,
            "right": l.right,
            "strike": l.strike,
            "expiry": l.expiry,
            "qty": l.qty,
            "mid": l.mid,
            "iv": l.iv,
            "ttm": l.ttm,
            "moneyness": l.moneyness,
        } for l in self.legs])


# -----------------------------
# Column normalization helpers
# -----------------------------


_DEFAULT_COLS: Dict[str, str] = {
    "symbol": "contractSymbol",
    "strike": "strike",
    "right": "optionType",  # will also look for type/right
    "mid": "mid",
    "moneyness": "moneyness",
    "ttm": "ttm",
}


def _infer_right_col(chain: pd.DataFrame, cols: Dict[str, str]) -> str:
    """Infer which column holds call/put indicator."""
    # User override
    if cols.get("right") in chain.columns:
        return cols["right"]

    for c in ("optionType", "type", "right"):
        if c in chain.columns:
            return c

    raise ValueError("Could not infer option right column (call/put).")


def _standardize_right(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.lower().str.strip()
    return s.replace({"c": "call", "p": "put"})


def _require_cols(chain: pd.DataFrame, required: Sequence[str]) -> None:
    missing = [c for c in required if c not in chain.columns]
    if missing:
        raise ValueError(f"Chain missing required columns: {missing}")


# -----------------------------
# Chain selection helpers (anchors)
# -----------------------------


def pick_by_moneyness(
    chain: pd.DataFrame,
    *,
    right: OptionRight,
    target_moneyness: float,
    cols: Optional[Dict[str, str]] = None,
) -> pd.Series:
    """Pick the row closest to a target moneyness for the specified right."""
    cols = {**_DEFAULT_COLS, **(cols or {})}
    sym_col = cols["symbol"]
    strike_col = cols["strike"]
    mid_col = cols["mid"]
    mny_col = cols["moneyness"]

    _require_cols(chain, [sym_col, strike_col, mid_col, mny_col])
    rcol = _infer_right_col(chain, cols)

    df = chain.copy()
    df[rcol] = _standardize_right(df[rcol])

    df = df[df[rcol] == right].copy()
    if df.empty:
        raise ValueError(f"No rows found for right={right}")

    # prefer non-null mid
    df = df.dropna(subset=[mid_col, mny_col, strike_col])
    if df.empty:
        raise ValueError(f"No usable rows (null mid/moneyness/strike) for right={right}")

    # choose closest moneyness
    idx = (df[mny_col] - float(target_moneyness)).abs().idxmin()
    return df.loc[idx]


def pick_atm_strike(
    chain: pd.DataFrame,
    *,
    target_moneyness: float = 1.0,
    cols: Optional[Dict[str, str]] = None,
) -> float:
    """Pick an ATM strike by closest moneyness using the whole chain."""
    cols = {**_DEFAULT_COLS, **(cols or {})}
    strike_col = cols["strike"]
    mny_col = cols["moneyness"]
    _require_cols(chain, [strike_col, mny_col])

    df = chain.dropna(subset=[strike_col, mny_col]).copy()
    if df.empty:
        raise ValueError("No usable rows to pick ATM strike.")

    idx = (df[mny_col] - float(target_moneyness)).abs().idxmin()
    return float(df.loc[idx, strike_col])


def pick_by_strike(
    chain: pd.DataFrame,
    *,
    right: OptionRight,
    strike: float,
    cols: Optional[Dict[str, str]] = None,
) -> pd.Series:
    """Pick the best row for a given right and exact strike (closest if multiple)."""
    cols = {**_DEFAULT_COLS, **(cols or {})}
    sym_col = cols["symbol"]
    strike_col = cols["strike"]
    mid_col = cols["mid"]
    _require_cols(chain, [sym_col, strike_col, mid_col])

    rcol = _infer_right_col(chain, cols)
    df = chain.copy()
    df[rcol] = _standardize_right(df[rcol])
    df = df[df[rcol] == right].copy()

    df = df.dropna(subset=[mid_col, strike_col])
    if df.empty:
        raise ValueError(f"No usable rows for right={right}")

    # If exact strike exists, pick the one with highest volume/openInterest not guaranteed.
    # For now choose closest strike.
    idx = (df[strike_col] - float(strike)).abs().idxmin()
    return df.loc[idx]


# -----------------------------
# Structure builders
# -----------------------------


def make_atm_straddle(
    chain: pd.DataFrame,
    *,
    expiry: str,
    qty: float = 1.0,
    atm_moneyness: float = 1.0,
    name: str = "ATM Straddle",
    cols: Optional[Dict[str, str]] = None,
) -> Portfolio:
    """Long 1 ATM call + long 1 ATM put."""
    cols = {**_DEFAULT_COLS, **(cols or {})}
    sym_col = cols["symbol"]
    strike_col = cols["strike"]
    mid_col = cols["mid"]
    mny_col = cols["moneyness"]
    ttm_col = cols["ttm"]

    K = pick_atm_strike(chain, target_moneyness=atm_moneyness, cols=cols)

    call_row = pick_by_strike(chain, right="call", strike=K, cols=cols)
    put_row = pick_by_strike(chain, right="put", strike=K, cols=cols)

    legs = (
        Leg(
            contract_symbol=str(call_row[sym_col]),
            right="call",
            strike=float(call_row[strike_col]),
            expiry=expiry,
            qty=float(qty),
            mid=float(call_row[mid_col]) if pd.notna(call_row[mid_col]) else None,
            ttm=float(call_row[ttm_col]) if ttm_col in call_row.index and pd.notna(call_row[ttm_col]) else None,
            moneyness=float(call_row[mny_col]) if pd.notna(call_row[mny_col]) else None,
        ),
        Leg(
            contract_symbol=str(put_row[sym_col]),
            right="put",
            strike=float(put_row[strike_col]),
            expiry=expiry,
            qty=float(qty),
            mid=float(put_row[mid_col]) if pd.notna(put_row[mid_col]) else None,
            ttm=float(put_row[ttm_col]) if ttm_col in put_row.index and pd.notna(put_row[ttm_col]) else None,
            moneyness=float(put_row[mny_col]) if pd.notna(put_row[mny_col]) else None,
        ),
    )

    return Portfolio(name=name, legs=legs)


def make_vertical_spread(
    chain: pd.DataFrame,
    *,
    expiry: str,
    right: OptionRight,
    k_long: float,
    k_short: float,
    qty: float = 1.0,
    name: Optional[str] = None,
    cols: Optional[Dict[str, str]] = None,
) -> Portfolio:
    """Vertical spread: long K_long, short K_short for a given right."""
    cols = {**_DEFAULT_COLS, **(cols or {})}
    sym_col = cols["symbol"]
    strike_col = cols["strike"]
    mid_col = cols["mid"]
    mny_col = cols["moneyness"]
    ttm_col = cols["ttm"]

    long_row = pick_by_strike(chain, right=right, strike=k_long, cols=cols)
    short_row = pick_by_strike(chain, right=right, strike=k_short, cols=cols)

    spread_name = name or f"{right.title()} Vertical {k_long:g}/{k_short:g}"

    legs = (
        Leg(
            contract_symbol=str(long_row[sym_col]),
            right=right,
            strike=float(long_row[strike_col]),
            expiry=expiry,
            qty=float(qty),
            mid=float(long_row[mid_col]) if pd.notna(long_row[mid_col]) else None,
            ttm=float(long_row[ttm_col]) if ttm_col in long_row.index and pd.notna(long_row[ttm_col]) else None,
            moneyness=float(long_row[mny_col]) if pd.notna(long_row[mny_col]) else None,
        ),
        Leg(
            contract_symbol=str(short_row[sym_col]),
            right=right,
            strike=float(short_row[strike_col]),
            expiry=expiry,
            qty=-float(qty),
            mid=float(short_row[mid_col]) if pd.notna(short_row[mid_col]) else None,
            ttm=float(short_row[ttm_col]) if ttm_col in short_row.index and pd.notna(short_row[ttm_col]) else None,
            moneyness=float(short_row[mny_col]) if pd.notna(short_row[mny_col]) else None,
        ),
    )

    return Portfolio(name=spread_name, legs=legs)


def make_collar(
    chain: pd.DataFrame,
    *,
    expiry: str,
    put_moneyness: float = 0.95,
    call_moneyness: float = 1.05,
    qty: float = 1.0,
    name: str = "Collar",
    cols: Optional[Dict[str, str]] = None,
) -> Portfolio:
    """Collar (options-only): long put (OTM) + short call (OTM).

    Note: This is the common options overlay. If you want 'covered' collar, model the
    underlying position separately in your portfolio layer.
    """
    cols = {**_DEFAULT_COLS, **(cols or {})}
    sym_col = cols["symbol"]
    strike_col = cols["strike"]
    mid_col = cols["mid"]
    mny_col = cols["moneyness"]
    ttm_col = cols["ttm"]

    put_row = pick_by_moneyness(chain, right="put", target_moneyness=put_moneyness, cols=cols)
    call_row = pick_by_moneyness(chain, right="call", target_moneyness=call_moneyness, cols=cols)

    legs = (
        Leg(
            contract_symbol=str(put_row[sym_col]),
            right="put",
            strike=float(put_row[strike_col]),
            expiry=expiry,
            qty=float(qty),
            mid=float(put_row[mid_col]) if pd.notna(put_row[mid_col]) else None,
            ttm=float(put_row[ttm_col]) if ttm_col in put_row.index and pd.notna(put_row[ttm_col]) else None,
            moneyness=float(put_row[mny_col]) if pd.notna(put_row[mny_col]) else None,
        ),
        Leg(
            contract_symbol=str(call_row[sym_col]),
            right="call",
            strike=float(call_row[strike_col]),
            expiry=expiry,
            qty=-float(qty),
            mid=float(call_row[mid_col]) if pd.notna(call_row[mid_col]) else None,
            ttm=float(call_row[ttm_col]) if ttm_col in call_row.index and pd.notna(call_row[ttm_col]) else None,
            moneyness=float(call_row[mny_col]) if pd.notna(call_row[mny_col]) else None,
        ),
    )

    return Portfolio(name=name, legs=legs)


def make_risk_reversal(
    chain: pd.DataFrame,
    *,
    expiry: str,
    put_moneyness: float = 0.95,
    call_moneyness: float = 1.05,
    qty: float = 1.0,
    direction: Literal["bullish", "bearish"] = "bullish",
    name: Optional[str] = None,
    cols: Optional[Dict[str, str]] = None,
) -> Portfolio:
    """Risk reversal using moneyness anchors.

    - bullish: long OTM call, short OTM put
    - bearish: long OTM put, short OTM call

    (Delta-based selection can be added later; moneyness-based works well with Yahoo.)
    """
    cols = {**_DEFAULT_COLS, **(cols or {})}
    sym_col = cols["symbol"]
    strike_col = cols["strike"]
    mid_col = cols["mid"]
    mny_col = cols["moneyness"]
    ttm_col = cols["ttm"]

    put_row = pick_by_moneyness(chain, right="put", target_moneyness=put_moneyness, cols=cols)
    call_row = pick_by_moneyness(chain, right="call", target_moneyness=call_moneyness, cols=cols)

    rr_name = name or ("Risk Reversal (Bullish)" if direction == "bullish" else "Risk Reversal (Bearish)")

    if direction == "bullish":
        # long call, short put
        legs = (
            Leg(
                contract_symbol=str(call_row[sym_col]),
                right="call",
                strike=float(call_row[strike_col]),
                expiry=expiry,
                qty=float(qty),
                mid=float(call_row[mid_col]) if pd.notna(call_row[mid_col]) else None,
                ttm=float(call_row[ttm_col]) if ttm_col in call_row.index and pd.notna(call_row[ttm_col]) else None,
                moneyness=float(call_row[mny_col]) if pd.notna(call_row[mny_col]) else None,
            ),
            Leg(
                contract_symbol=str(put_row[sym_col]),
                right="put",
                strike=float(put_row[strike_col]),
                expiry=expiry,
                qty=-float(qty),
                mid=float(put_row[mid_col]) if pd.notna(put_row[mid_col]) else None,
                ttm=float(put_row[ttm_col]) if ttm_col in put_row.index and pd.notna(put_row[ttm_col]) else None,
                moneyness=float(put_row[mny_col]) if pd.notna(put_row[mny_col]) else None,
            ),
        )
    else:
        # long put, short call
        legs = (
            Leg(
                contract_symbol=str(put_row[sym_col]),
                right="put",
                strike=float(put_row[strike_col]),
                expiry=expiry,
                qty=float(qty),
                mid=float(put_row[mid_col]) if pd.notna(put_row[mid_col]) else None,
                ttm=float(put_row[ttm_col]) if ttm_col in put_row.index and pd.notna(put_row[ttm_col]) else None,
                moneyness=float(put_row[mny_col]) if pd.notna(put_row[mny_col]) else None,
            ),
            Leg(
                contract_symbol=str(call_row[sym_col]),
                right="call",
                strike=float(call_row[strike_col]),
                expiry=expiry,
                qty=-float(qty),
                mid=float(call_row[mid_col]) if pd.notna(call_row[mid_col]) else None,
                ttm=float(call_row[ttm_col]) if ttm_col in call_row.index and pd.notna(call_row[ttm_col]) else None,
                moneyness=float(call_row[mny_col]) if pd.notna(call_row[mny_col]) else None,
            ),
        )

    return Portfolio(name=rr_name, legs=legs)


__all__ = [
    "Leg",
    "Portfolio",
    "pick_by_moneyness",
    "pick_atm_strike",
    "pick_by_strike",
    "make_atm_straddle",
    "make_vertical_spread",
    "make_collar",
    "make_risk_reversal",
]