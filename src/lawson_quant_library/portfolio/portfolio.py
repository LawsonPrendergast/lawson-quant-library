

"""Portfolio containers and aggregation utilities.

This module intentionally stays *lightweight* so notebooks can build option structures
as collections of legs, then:
- compute leg prices/greeks externally (e.g., via your BS model)
- aggregate to portfolio-level value and risk

The key design goal: keep notebooks thin and keep reusable aggregation logic here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import pandas as pd

OptionRight = Literal["call", "put"]


@dataclass(frozen=True)
class Leg:
    """One leg in a portfolio."""

    contract_symbol: str
    right: OptionRight
    strike: float
    expiry: str
    qty: float = 1.0

    # Optional metadata (useful for auditing / debug, not required)
    mid: Optional[float] = None
    iv: Optional[float] = None
    ttm: Optional[float] = None
    moneyness: Optional[float] = None


@dataclass(frozen=True)
class Portfolio:
    """A simple portfolio of legs."""

    name: str
    legs: Tuple[Leg, ...]

    # ---------- convenience ----------

    def symbols(self) -> List[str]:
        """Return all contract symbols in this portfolio."""
        return [l.contract_symbol for l in self.legs]

    def to_frame(self) -> pd.DataFrame:
        """Tabular representation for quick inspection in notebooks."""
        return pd.DataFrame([
            {
                "contractSymbol": l.contract_symbol,
                "right": l.right,
                "strike": l.strike,
                "expiry": l.expiry,
                "qty": l.qty,
                "mid": l.mid,
                "iv": l.iv,
                "ttm": l.ttm,
                "moneyness": l.moneyness,
            }
            for l in self.legs
        ])

    # ---------- aggregation ----------

    def value_from_prices(self, prices: Dict[str, float]) -> float:
        """Aggregate portfolio value using a mapping {contractSymbol: price}."""
        missing = [l.contract_symbol for l in self.legs if l.contract_symbol not in prices]
        if missing:
            raise KeyError(f"Missing prices for: {missing}")
        return float(sum(l.qty * float(prices[l.contract_symbol]) for l in self.legs))

    def cost_mid(self) -> float:
        """Aggregate mid-cost from leg metadata.

        Useful for 'inception premium' when legs were built from a snapshot.
        """
        missing = [l.contract_symbol for l in self.legs if l.mid is None]
        if missing:
            raise ValueError(f"Missing mid on legs: {missing}")
        return float(sum(l.qty * float(l.mid) for l in self.legs))

    def aggregate_greeks(self, greeks: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Aggregate greeks using nested mapping:

        greeks = {
            contractSymbol: {"delta": ..., "gamma": ..., "vega": ..., "theta": ...}
        }

        Returns a dict of summed greeks.
        """
        # determine greek keys from first available entry
        first = None
        for l in self.legs:
            if l.contract_symbol in greeks:
                first = greeks[l.contract_symbol]
                break
        if first is None:
            raise KeyError("No greeks provided for any leg.")

        keys = list(first.keys())
        out = {k: 0.0 for k in keys}

        missing = [l.contract_symbol for l in self.legs if l.contract_symbol not in greeks]
        if missing:
            raise KeyError(f"Missing greeks for: {missing}")

        for l in self.legs:
            g = greeks[l.contract_symbol]
            for k in keys:
                out[k] += float(l.qty) * float(g.get(k, 0.0))

        return out


__all__ = ["Leg", "Portfolio", "OptionRight"]