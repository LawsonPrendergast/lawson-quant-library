from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import QuantLib as ql

from lawson_quant_library.util import Calendar, Tenor
from .parameter import Parameter


class CurvePoint:

    def __init__(
    self,
    tenor: str,
    date: Any,
    discount_factor: float,
    zero_rate: float
    ):
        self.tenor = tenor
        self.date = date
        self.discount_factor = discount_factor
        self.zero_rate = zero_rate



class IRCurve(Parameter):
    """Interest-rate discount curve.

    Current implementation supports:
      - Flat curve (FlatForward)
      - Simple bootstrapped curve from deposit quotes by tenor (first pass)

    Notes:
      - Inputs are designed so notebooks can pass strings like '2026-06-15' or tenors like '3M'.
    """

    def __init__(
        self,
        rate: float,
        calendar: Calendar,
        name: str | None = None,
        *,
        currency: str = "USD",
        day_count: str = "ACT365F",
        settlement_days: int = 2,
        interpolation: str = "loglinear", **kwargs
    ):
        super().__init__(name=name)

        self.currency = currency
        self.calendar = calendar
        self.day_count = day_count
        self.settlement_days = int(settlement_days)
        self.interpolation = interpolation

        self._calendar = get_calendar(calendar)
        self._day_count = get_day_count(day_count)

        # Curve state
        self._handle = ql.RelinkableYieldTermStructureHandle()
        self._curve = None
        self._quotes: Dict[str, ql.SimpleQuote] = {}
        self._helpers: List[Any] = []

        # Default to flat curve
        self.set_flat_rate(rate)

    def handle(self) -> ql.YieldTermStructureHandle:
        return self._handle

    def set_flat_rate(self, rate: float, *, reference_date: Any | None = None) -> None:
        r = float(rate)
        today = evaluation_date(reference_date)
        curve = ql.FlatForward(self.settlement_days, self._calendar, r, self._day_count)

        self._curve = curve
        self._helpers = []
        self._quotes = {}
        self.handle().linkTo(curve)


    def set_deposit_quotes(self, quotes: Dict[str, float], *, reference_date: Any) -> None:
        """(Re)build the curve from deposit quotes."""
        cal = self._calendar
        day_count = self._day_count

        # evaluation date is assumed already set externally (or defaults inside QL)
        ql_quotes: Dict[str, ql.SimpleQuote] = {}
        helpers: List[Any] = []

        # Sort tenors by increasing maturity
        def _tenor_key(t: str) -> Tuple[int, str]:
            tenor = parse_tenor(t)
            return (tenor.n, tenor.unit)

        for tenor, rate in sorted(quotes.items(), key=lambda kv: _tenor_key(kv[0])):
            rate_quote = ql.SimpleQuote(float(rate))
            rate_handle = ql.QuoteHandle(rate_quote)

            period = parse_tenor(tenor).to_ql_period()

            helper = ql.DepositRateHelper(
                rate_handle,
                period,
                self.settlement_days,
                cal,
                ql.ModifiedFollowing,
                False,
                day_count,
            )

            ql_quotes[tenor] = rate_quote
            helpers.append(helper)

        # Build a discount curve (first pass)
        today = evaluation_date(reference_date)

        curve = ql.PiecewiseLogLinearDiscount(today, helpers, day_count)
        curve.enableExtrapolation()

        self._quotes = ql_quotes
        self._helpers = helpers
        self._curve = curve
        self.handle().linkTo(curve)

    # --- Curve queries ---
    def discount(self, d: Any) -> float:
        qd = to_ql_date(d)
        return float(self.handle().discount(qd))

    def zero_rate(self, d: Any, *, compounding: str = "cont", freq: int = 1) -> float:
        qd = to_ql_date(d)

        comp = str(compounding).lower()
        if comp in {"cont", "continuous"}:
            zr = self.handle().zeroRate(qd, self._day_count, ql.Continuous, ql.Annual)
        elif comp in {"simple"}:
            zr = self.handle().zeroRate(qd, self._day_count, ql.Simple, ql.Annual)
        else:
            # default to continuous
            zr = self.handle().zeroRate(qd, self._day_count, ql.Continuous, ql.Annual)

        return float(zr.rate())

    def forward_rate(
        self,
        d1: Any,
        d2: Any,
        *,
        compounding: str = "simple",
    ) -> float:
        qd1 = to_ql_date(d1)
        qd2 = to_ql_date(d2)

        comp = str(compounding).lower()
        if comp in {"cont", "continuous"}:
            fr = self.handle().forwardRate(qd1, qd2, self._day_count, ql.Continuous, ql.Annual)
        else:
            fr = self.handle().forwardRate(qd1, qd2, self._day_count, ql.Simple, ql.Annual)

        return float(fr.rate())

    def table(
        self,
        tenors: Iterable[str],
        *,
        reference_date: Any | None = None,
    ) -> List[CurvePoint]:
        ref = to_ql_date(reference_date)
        out: List[CurvePoint] = []

        for t in tenors:
            period = parse_tenor(t).to_ql_period()
            d = self._calendar.advance(ref, period)
            df = float(self.handle().discount(d))
            zr = float(self.handle().zeroRate(d, self._day_count, ql.Continuous, ql.Annual).rate())
            out.append(CurvePoint(tenor=str(t).upper(), date=d, discount_factor=df, zero_rate=zr))

        return out