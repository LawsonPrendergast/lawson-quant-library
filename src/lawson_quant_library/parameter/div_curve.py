from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import QuantLib as ql

from lawson_quant_library.util import Calendar, evaluation_date, get_calendar, get_day_count, parse_tenor, to_ql_date

from .parameter import Parameter



class CurvePoint:
    def __init__(
    self,
    tenor: str,
    date: Any,
    discount_factor: float,
    zero_rate: float,
    ):
        self.tenor = tenor
        self.date = date
        self.discount_factor = discount_factor
        self.zero_rate = zero_rate



class DivCurve(Parameter):
    """Flat dividend yield curve (equity carry)."""

    def __init__(
        self,
        div_yield: float = 0.0,
        name: str | None = None,
        *,
        calendar: str = "US:NYSE",
        day_count: str = "ACT365F",
    ):
        super().__init__(name=name)

        self.q = float(div_yield)
        self.calendar_name = calendar
        self.day_count_name = day_count

        self._calendar = get_calendar(calendar)
        self._day_count = get_day_count(day_count)

        today = ql.Settings.instance().evaluationDate
        self._handle = ql.RelinkableYieldTermStructureHandle()
        self._curve = ql.FlatForward(today, self.q, self._day_count)
        self._handle.linkTo(self._curve)

    @property
    def handle(self) -> ql.YieldTermStructureHandle:
        return self._handle

    def set_div(self, new_q: float) -> None:
        self.q = float(new_q)
        today = ql.Settings.instance().evaluationDate
        self._curve = ql.FlatForward(today, self.q, self._day_count)
        self._handle.linkTo(self._curve)