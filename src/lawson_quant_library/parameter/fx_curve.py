from typing import Any, Optional
import QuantLib as ql

from lawson_quant_library.parameter.parameter import Parameter
from lawson_quant_library.util import (
    Calendar,
    get_calendar,
    get_day_count,
    to_ql_date,
)


class FXCurve(Parameter):
    """
    FX discount or funding curve placeholder.

    This class represents a yield curve used in FX pricing
    (domestic or foreign). Forward construction will be added later.
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

        self._calendar = get_calendar(calendar)
        self._day_count = get_day_count(day_count)

        self._handle = ql.RelinkableYieldTermStructureHandle()
        self._curve = None

    @property
    def handle(self) -> ql.YieldTermStructureHandle:
        return self._handle

    def set_flat_rate(self, rate: float, *, reference_date: Any) -> None:
        r = float(rate)

        cal = Calendar(name=self.calendar, day_count=self.day_count)
        with cal.evaluation_date(reference_date):
            today = ql.Settings.instance().evaluationDate
            curve = ql.FlatForward(today, r, self._day_count)

        self._curve = curve
        self._handle.linkTo(curve)