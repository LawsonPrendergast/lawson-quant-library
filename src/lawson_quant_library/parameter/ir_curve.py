from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import QuantLib as ql

from lawson_quant_library.util import Calendar, evaluation_date, get_calendar, get_day_count, parse_tenor, to_ql_date

from .parameter import Parameter


@dataclass(frozen=True)
class CurvePoint:
    tenor: str
    date: Any
    discount_factor: float
    zero_rate: float


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
        name: str | None = None,
        *,
        currency: str = "USD",
        calendar: str = "US:NYSE",
        day_count: str = "ACT365F",
        settlement_days: int = 2,
        interpolation: str = "loglinear",
    ):
        super().__init__(name=name)

        self.currency = currency
        self.calendar_name = calendar
        self.day_count_name = day_count
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

    @property
    def handle(self) -> ql.YieldTermStructureHandle:
        return self._handle

    def set_flat_rate(self, rate: float, *, reference_date: Any | None = None) -> None:
        r = float(rate)

        if reference_date is not None:
            cal = Calendar(name=self.calendar_name, day_count=self.day_count_name)
            with cal.evaluation_date(reference_date):
                today = ql.Settings.instance().evaluationDate
                curve = ql.FlatForward(today, r, self._day_count)
        else:
            today = ql.Settings.instance().evaluationDate
            curve = ql.FlatForward(today, r, self._day_count)

        self._curve = curve
        self._helpers = []
        self._quotes = {}
        self._handle.linkTo(curve)

    @classmethod
    def from_deposit_quotes(
        cls,
        quotes: Dict[str, float],
        *,
        name: str | None = None,
        currency: str = "USD",
        calendar: str = "US:NYSE",
        day_count: str = "ACT365F",
        settlement_days: int = 2,
        interpolation: str = "loglinear",
        reference_date: Any | None = None,
    ) -> "IRCurve":
        """Build a first-pass curve from deposit quotes keyed by tenor (e.g. {'1M': 0.05})."""
        if not quotes:
            raise ValueError("quotes must be a non-empty dict of tenor -> rate")

        # Initialize as flat (will be overwritten by bootstrap)
        obj = cls(
            rate=float(next(iter(quotes.values()))),
            name=name,
            currency=currency,
            calendar=calendar,
            day_count=day_count,
            settlement_days=settlement_days,
            interpolation=interpolation,
        )
        obj.set_deposit_quotes(quotes, reference_date=reference_date)
        return obj

    def set_deposit_quotes(self, quotes: Dict[str, float], *, reference_date: Any | None = None) -> None:
        """(Re)build the curve from deposit quotes."""
        cal = self._calendar
        dc = self._day_count

        # evaluation date is assumed already set externally (or defaults inside QL)
        ql_quotes: Dict[str, ql.SimpleQuote] = {}
        helpers: List[Any] = []

        # Sort tenors by increasing maturity
        def _tenor_key(t: str) -> Tuple[int, str]:
            ten = parse_tenor(t)
            return (ten.n, ten.unit)

        for tenor, rate in sorted(quotes.items(), key=lambda kv: _tenor_key(kv[0])):
            sq = ql.SimpleQuote(float(rate))
            qh = ql.QuoteHandle(sq)

            period = parse_tenor(tenor).to_ql_period()

            helper = ql.DepositRateHelper(
                qh,
                period,
                self.settlement_days,
                cal,
                ql.ModifiedFollowing,
                False,
                dc,
            )

            ql_quotes[tenor] = sq
            helpers.append(helper)

        # Build a discount curve (first pass)
        if reference_date is not None:
            cal_wrap = Calendar(name=self.calendar_name, day_count=self.day_count_name)
            with cal_wrap.evaluation_date(reference_date):
                today = ql.Settings.instance().evaluationDate

                if str(self.interpolation).lower() in {"loglinear", "log-linear", "log_linear"}:
                    curve = ql.PiecewiseLogLinearDiscount(today, helpers, dc)
                else:
                    curve = ql.PiecewiseLogLinearDiscount(today, helpers, dc)

                curve.enableExtrapolation()
        else:
            today = ql.Settings.instance().evaluationDate

            if str(self.interpolation).lower() in {"loglinear", "log-linear", "log_linear"}:
                curve = ql.PiecewiseLogLinearDiscount(today, helpers, dc)
            else:
                curve = ql.PiecewiseLogLinearDiscount(today, helpers, dc)

            curve.enableExtrapolation()

        self._quotes = ql_quotes
        self._helpers = helpers
        self._curve = curve
        self._handle.linkTo(curve)

    # --- Curve queries ---
    def discount(self, d: Any) -> float:
        qd = to_ql_date(d)
        return float(self.handle.discount(qd))

    def zero_rate(self, d: Any, *, compounding: str = "cont", freq: int = 1) -> float:
        qd = to_ql_date(d)

        comp = str(compounding).lower()
        if comp in {"cont", "continuous"}:
            zr = self.handle.zeroRate(qd, self._day_count, ql.Continuous, ql.Annual)
        elif comp in {"simple"}:
            zr = self.handle.zeroRate(qd, self._day_count, ql.Simple, ql.Annual)
        else:
            # default to continuous
            zr = self.handle.zeroRate(qd, self._day_count, ql.Continuous, ql.Annual)

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
            fr = self.handle.forwardRate(qd1, qd2, self._day_count, ql.Continuous, ql.Annual)
        else:
            fr = self.handle.forwardRate(qd1, qd2, self._day_count, ql.Simple, ql.Annual)

        return float(fr.rate())

    def table(
        self,
        tenors: Iterable[str],
        *,
        reference_date: Any | None = None,
    ) -> List[CurvePoint]:
        ref = to_ql_date(reference_date) if reference_date is not None else ql.Settings.instance().evaluationDate
        out: List[CurvePoint] = []

        for t in tenors:
            period = parse_tenor(t).to_ql_period()
            d = self._calendar.advance(ref, period)
            df = float(self.handle.discount(d))
            zr = float(self.handle.zeroRate(d, self._day_count, ql.Continuous, ql.Annual).rate())
            out.append(CurvePoint(tenor=str(t).upper(), date=d, discount_factor=df, zero_rate=zr))

        return out