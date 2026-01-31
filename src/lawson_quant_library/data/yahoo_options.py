from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple, Union

import pandas as pd
import yfinance as yf

OptionType = Literal["call", "put"]


@dataclass(frozen=True)
class OptionChainSnapshot:
    ticker: str
    expiry: pd.Timestamp
    as_of: pd.Timestamp
    calls: pd.DataFrame
    puts: pd.DataFrame


class YahooOptionsAdapter:
    """Yahoo (yfinance) options adapter.

    What this *can* do reliably:
    - Current option chain snapshot for an expiry
    - Historical OHLCV for an individual option contract *symbol* (contractSymbol)

    What this *cannot* do directly:
    - A true historical chain/surface as-of a past date. Yahoo only gives per-contract
      history; you must choose which contracts to track (e.g., today’s chain) and build
      your own store.

    This file implements the practical approach you asked for:
    - Pull current chain(s) -> get contractSymbol list
    - For each contractSymbol, pull .history() and store locally (parquet)
    - Later, build “as-of” pseudo-chains from the stored contract histories

    NOTE: This will have survivorship/selection bias if you use today’s chain to backfill
    the past. It is still useful for prototyping notebooks and getting structure plumbing right.
    """

    def __init__(self, ticker: str):
        self.ticker = ticker
        self._yf = yf.Ticker(ticker)

    # -----------------------------
    # Chain snapshot
    # -----------------------------
    def expiries(self) -> List[str]:
        return list(self._yf.options)

    def option_chain(self, expiry: str) -> Dict[str, pd.DataFrame]:
        chain = self._yf.option_chain(expiry)
        return {"calls": chain.calls, "puts": chain.puts}

    def normalize_chain(self, df: pd.DataFrame, expiry: str, option_type: OptionType) -> pd.DataFrame:
        out = df.copy()
        out["expiry"] = pd.to_datetime(expiry)
        out["type"] = option_type
        out["mid"] = (out["bid"] + out["ask"]) / 2
        bad_mid = out["mid"].isna() | (out["mid"] <= 0)
        if "lastPrice" in out.columns:
            out.loc[bad_mid, "mid"] = out.loc[bad_mid, "lastPrice"]
        return out

    def normalized_chain(self, expiry: str, option_type: OptionType) -> pd.DataFrame:
        chain = self.option_chain(expiry)
        df = chain["calls"] if option_type == "call" else chain["puts"]
        return self.normalize_chain(df, expiry, option_type)

    def with_moneyness(self, df: pd.DataFrame, spot: float) -> pd.DataFrame:
        out = df.copy()
        out["moneyness"] = out["strike"] / float(spot)
        return out

    def with_time_to_expiry(self, df: pd.DataFrame, valuation_date: Union[str, pd.Timestamp]) -> pd.DataFrame:
        out = df.copy()
        val = pd.to_datetime(valuation_date)
        expiry = pd.to_datetime(out["expiry"])
        out["ttm"] = (expiry - val).dt.total_seconds() / (365.25 * 24 * 60 * 60)
        return out

    def filter_liquid(self, df: pd.DataFrame, min_oi: int = 10, min_volume: int = 1) -> pd.DataFrame:
        out = df.copy()
        filtered = (
            (out.get("openInterest", 0) >= min_oi)
            & (out.get("volume", 0) >= min_volume)
            & (out.get("mid", 0) > 0)
        )
        return out.loc[filtered]

    def spot(self) -> float:
        fast = getattr(self._yf, "fast_info", None)
        if fast and "last_price" in fast and fast["last_price"] is not None:
            return float(fast["last_price"])
        hist = self._yf.history(period="5d", interval="1d")
        if hist is None or hist.empty:
            raise RuntimeError(f"Unable to fetch spot for {self.ticker}")
        return float(hist["Close"].iloc[-1])

    def snapshot(self, expiry: str, as_of: Optional[Union[str, pd.Timestamp]] = None, add_analytics: bool = True):
        calls = self.normalized_chain(expiry, "call")
        puts = self.normalized_chain(expiry, "put")
        as_of_ts = pd.Timestamp.utcnow() if as_of is None else pd.to_datetime(as_of)
        if add_analytics:
            s = self.spot()
            calls = self.with_moneyness(calls, s)
            puts = self.with_moneyness(puts, s)
            calls = self.with_time_to_expiry(calls, as_of_ts)
            puts = self.with_time_to_expiry(puts, as_of_ts)
        calls = calls.copy()
        puts = puts.copy()
        calls["as_of"] = as_of_ts
        puts["as_of"] = as_of_ts
        return {
            "ticker": self.ticker,
            "expiry": expiry,
            "as_of": as_of_ts,
            "calls": calls,
            "puts": puts,
        }

    # -----------------------------
    # Contract-level history (the key piece)
    # -----------------------------
    def list_contracts(
        self,
        expiry: str,
        option_type: OptionType,
        strikes: Optional[Sequence[float]] = None,
    ) -> pd.DataFrame:
        """Return a dataframe containing at least contractSymbol + strike for an expiry/type."""
        df = self.normalized_chain(expiry, option_type)
        # contractSymbol is the Yahoo option identifier used by yfinance
        if "contractSymbol" not in df.columns:
            raise RuntimeError("yfinance did not return contractSymbol; cannot fetch contract history")

        if strikes is not None:
            strikes_set = set(float(x) for x in strikes)
            df = df[df["strike"].astype(float).isin(strikes_set)]

        return df.reset_index(drop=True)

    def option_contract_history(
        self,
        contract_symbol: str,
        start: Optional[Union[str, pd.Timestamp]] = None,
        end: Optional[Union[str, pd.Timestamp]] = None,
        interval: str = "1d",
        period: Optional[str] = None,
    ) -> pd.DataFrame:
        """Historical OHLCV for a single option contract symbol.

        Notes:
        - Yahoo often provides daily OHLCV across the contract life.
        - Use period="max" if you want the full available history.
        """
        t = yf.Ticker(contract_symbol)
        kwargs = {"interval": interval}

        if period is not None:
            kwargs["period"] = period
        else:
            if start is not None:
                kwargs["start"] = pd.to_datetime(start)
            if end is not None:
                kwargs["end"] = pd.to_datetime(end)

        df = t.history(**kwargs)
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df.index.name = "date"

        # Stamp identifiers for downstream joins
        df["contractSymbol"] = contract_symbol
        return df

    # -----------------------------
    # Local store (parquet)
    # -----------------------------
    @staticmethod
    def _parquet_path(
        root: Union[str, Path],
        ticker: str,
        expiry: Union[str, pd.Timestamp],
        option_type: OptionType,
        contract_symbol: str,
    ) -> Path:
        rootp = Path(root)
        exp = pd.to_datetime(expiry).strftime("%Y-%m-%d")
        # Keep filenames safe
        fname = f"{contract_symbol}.parquet"
        return rootp / "provider=yahoo" / f"ticker={ticker}" / f"expiry={exp}" / f"type={option_type}" / fname

    def save_contract_history(self, df: pd.DataFrame, root: Union[str, Path], expiry: str, option_type: OptionType):
        if df is None or df.empty:
            return
        if "contractSymbol" not in df.columns:
            raise ValueError("Expected 'contractSymbol' column in contract history df")
        contract = str(df["contractSymbol"].iloc[0])
        path = self._parquet_path(root, self.ticker, expiry, option_type, contract)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=True)

    def load_contract_history(
        self,
        root: Union[str, Path],
        expiry: str,
        option_type: OptionType,
        contract_symbol: str,
    ) -> pd.DataFrame:
        path = self._parquet_path(root, self.ticker, expiry, option_type, contract_symbol)
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path)
        # ensure index is datetime
        if df.index.name != "date":
            df.index = pd.to_datetime(df.index)
            df.index.name = "date"
        return df

    # -----------------------------
    # Bulk backfill (selected contracts)
    # -----------------------------
    def backfill_expiry_contract_histories(
        self,
        expiry: str,
        option_type: OptionType,
        root: Union[str, Path],
        strikes: Optional[Sequence[float]] = None,
        period: str = "max",
        interval: str = "1d",
        sleep_s: float = 0.25,
        max_contracts: Optional[int] = None,
    ) -> pd.DataFrame:
        """Backfill and store histories for the selected contracts on an expiry.

        Returns a small summary dataframe (contractSymbol, rows, first_date, last_date).
        """
        contracts_df = self.list_contracts(expiry, option_type, strikes=strikes)
        if max_contracts is not None:
            contracts_df = contracts_df.head(int(max_contracts))

        summary_rows: List[Dict[str, object]] = []

        for _, row in contracts_df.iterrows():
            contract = str(row["contractSymbol"])

            # Skip if already stored
            existing = self.load_contract_history(root, expiry, option_type, contract)
            if existing is not None and not existing.empty:
                summary_rows.append(
                    {
                        "contractSymbol": contract,
                        "stored": True,
                        "rows": int(existing.shape[0]),
                        "first_date": existing.index.min(),
                        "last_date": existing.index.max(),
                    }
                )
                continue

            # Fetch and store
            df = self.option_contract_history(contract, period=period, interval=interval)
            self.save_contract_history(df, root=root, expiry=expiry, option_type=option_type)

            if df is None or df.empty:
                summary_rows.append({"contractSymbol": contract, "stored": False, "rows": 0})
            else:
                summary_rows.append(
                    {
                        "contractSymbol": contract,
                        "stored": True,
                        "rows": int(df.shape[0]),
                        "first_date": df.index.min(),
                        "last_date": df.index.max(),
                    }
                )

            if sleep_s and sleep_s > 0:
                time.sleep(float(sleep_s))

        return pd.DataFrame(summary_rows)

    # -----------------------------
    # Reconstruct a pseudo-chain "as of" a date from stored per-contract histories
    # -----------------------------
    def pseudo_chain_as_of(
        self,
        root: Union[str, Path],
        as_of: Union[str, pd.Timestamp],
        expiry: str,
        option_type: OptionType,
        contracts: Optional[Sequence[str]] = None,
        price_field: str = "Close",
    ) -> pd.DataFrame:
        """Build a pseudo-chain for an expiry/type at a given as-of date.

        This uses stored per-contract OHLCV and selects `price_field` on the as-of date.
        If the as-of date is missing for a contract, it will use the last available date
        <= as_of (common for non-trading days).

        Output columns: contractSymbol, price, date_used

        NOTE: This is not a true historical chain (no historical bid/ask/IV). It is a
        practical prototype for structure PnL and basic analytics.
        """
        as_of_ts = pd.to_datetime(as_of)

        # Determine contracts to load
        if contracts is None:
            # Scan local directory for stored contracts
            base = Path(root) / "provider=yahoo" / f"ticker={self.ticker}" / f"expiry={pd.to_datetime(expiry).strftime('%Y-%m-%d')}" / f"type={option_type}"
            if not base.exists():
                return pd.DataFrame()
            contracts = [p.stem for p in base.glob("*.parquet")]

        rows: List[Dict[str, object]] = []
        for c in contracts:
            df = self.load_contract_history(root, expiry, option_type, c)
            if df is None or df.empty or price_field not in df.columns:
                continue

            # choose last available date <= as_of
            df2 = df.loc[df.index <= as_of_ts]
            if df2.empty:
                continue
            last_idx = df2.index.max()
            price = df2.loc[last_idx, price_field]
            rows.append({"contractSymbol": c, "price": float(price), "date_used": last_idx})

        out = pd.DataFrame(rows)
        if out.empty:
            return out

        out["as_of"] = as_of_ts
        out["expiry"] = pd.to_datetime(expiry)
        out["type"] = option_type
        return out
