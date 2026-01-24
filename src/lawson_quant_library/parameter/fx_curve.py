from __future__ import annotations

from typing import Any, Optional

import QuantLib as ql

from lawson_quant_library.parameter.parameter import Parameter
from lawson_quant_library.util import Calendar, get_day_count, to_ql_date


class FXCurve(Parameter):
    """FX discount/funding curve.

    For now we support a flat curve. Later we can add true curve construction
    from FX swaps / basis / OIS discounting, etc.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        currency: str,
        calendar: str = "TARGET",
        day_count: str = "ACT365F",
    ) -> None:
        super().__init__(name=name, currency=currency)

        self.calendar = calendar
        self.day_count = day_count
        self._day_count = get_day_count(day_count)

        self._handle = ql.RelinkableYieldTermStructureHandle()
        self._curve: Optional[ql.YieldTermStructure] = None
        self._reference_date: Any = None

    @property
    def handle(self) -> ql.YieldTermStructureHandle:
        return self._handle

    @property
    def reference_date(self) -> Any:
        return self._reference_date

    def set_flat_rate(self, rate: float, *, reference_date: Any) -> None:
        r = float(rate)

        cal = Calendar(name=self.calendar, day_count=self.day_count)
        with cal.evaluation_date(reference_date):
            today = ql.Settings.instance().evaluationDate
            curve = ql.FlatForward(today, r, self._day_count)

        self._curve = curve
        self._handle.linkTo(curve)
        self._reference_date = reference_date

    def discount(self, date: Any) -> float:
        if self._curve is None:
            raise ValueError("FXCurve is not initialized. Call set_flat_rate(...) first.")
        return float(self._curve.discount(to_ql_date(date)))

    def zero_rate(self, date: Any) -> float:
        if self._curve is None:
            raise ValueError("FXCurve is not initialized. Call set_flat_rate(...) first.")
        ql_date = to_ql_date(date)
        zr = self._curve.zeroRate(
            ql_date,
            self._day_count,
            ql.Compounded,
            ql.Annual,
        )
        return float(zr.rate())

    def forward_rate(self, start: Any, end: Any) -> float:
        if self._curve is None:
            raise ValueError("FXCurve is not initialized. Call set_flat_rate(...) first.")
        d1 = to_ql_date(start)
        d2 = to_ql_date(end)
        fwd = self._curve.forwardRate(
            d1,
            d2,
            self._day_count,
            ql.Compounded,
            ql.Annual,
        )
        return float(fwd.rate())

    def table(self, tenors: list[str]) -> list[dict]:
        if self._reference_date is None:
            raise ValueError("Reference date not set on FXCurve.")
        if self._curve is None:
            raise ValueError("FXCurve is not initialized. Call set_flat_rate(...) first.")

        cal = Calendar(name=self.calendar, day_count=self.day_count)
        rows: list[dict] = []

        with cal.evaluation_date(self._reference_date):
            for t in tenors:
                # `Calendar.advance` works with Python dates / strings. QuantLib curve methods
                # need QuantLib.Date, so convert after advancing.
                end_py = cal.advance(self._reference_date, t)
                end_ql = to_ql_date(end_py)

                rows.append(
                    {
                        "tenor": t,
                        "end_date": str(end_py),
                        "df": float(self._curve.discount(end_ql)),
                        "zero_rate": float(
                            self._curve.zeroRate(
                                end_ql,
                                self._day_count,
                                ql.Compounded,
                                ql.Annual,
                            ).rate()
                        ),
                    }
                )

        return rows
  






