"""Utility functions for dates, calendars, and day-count conventions.

Design goal:
- QuantLib may be used internally for correctness.
- Public-facing helpers should accept and return standard Python types (e.g., `datetime.date`).
"""

from __future__ import annotations
import datetime as dt
from contextlib import contextmanager
from typing import Any, Iterator
import QuantLib as ql
from QuantLib import (
    # Dates & settings
    Date,
    Settings,
    SavedSettings,

    # Calendars
    UnitedStates,
    TARGET,
    NullCalendar,

    # Business day conventions
    Following,
    ModifiedFollowing,
    Preceding,
    Unadjusted,

    # Day count conventions
    Actual365Fixed,
    Actual360,
    Thirty360,
    

    # Periods / tenors
    Period,
    Days,
    Weeks,
    Months,
    Years,
)


# ----------------------------
# Dates
# ----------------------------




def to_date(value: Any) -> dt.date:
    """Convert common date inputs to a Python `datetime.date`.

    Accepts:
      - datetime.date
      - datetime.datetime
      - ISO string 'YYYY-MM-DD'
      - QuantLib.Date (if QuantLib is installed)

    Returns:
      - datetime.date
    """
    if value is None:
        raise TypeError("date value is required")

    if isinstance(value, dt.datetime):
        return value.date()

    if isinstance(value, dt.date):
        return value

    if isinstance(value, str):
        try:
            return dt.datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as e:
            raise TypeError(
                "Date string must be ISO format 'YYYY-MM-DD'. "
                f"Got {value!r}."
            ) from e
        
    if isinstance(value, ql.Date):
        return dt.date(value.year(), value.month(), value.dayOfMonth())

    raise TypeError(
        "Date must be datetime.date/datetime, ISO string 'YYYY-MM-DD', "
        "or QuantLib.Date"
        f"Got {type(value).__name__}."
    )


def to_ql_date(value: Any) -> ql.Date:
    # ✅ already a QuantLib.Date → return as-is
    if isinstance(value, ql.Date):
        return value

    d = to_date(value)
    return ql.Date(d.day, d.month, d.year)


@contextmanager
def evaluation_date(d: Any) -> Iterator[None]:
    """Temporarily set the QuantLib evaluation date within a scoped block."""
    
    saved = ql.SavedSettings()
    ql.Settings.instance().evaluationDate = to_ql_date(d)
    try:
        yield
    finally:
        # SavedSettings restores on destruction
        del saved


# ----------------------------
# Calendars
# ----------------------------

def get_calendar(name: str = "US:NYSE") -> Any:
    """Return a QuantLib calendar by a simple name."""

    key = name

    if key in {"US", "US:NYSE", "NYSE"}:
        return ql.UnitedStates(ql.UnitedStates.NYSE)
    if key in {"US:SETTLEMENT", "USSETTLEMENT"}:
        return ql.UnitedStates(ql.UnitedStates.Settlement)
    if key in {"TARGET", "EU:TARGET"}:
        return ql.TARGET()
    if key in {"NULL", "NONE"}:
        return ql.NullCalendar()

    raise ValueError(
        f"Unknown calendar {name!r}. Supported: US:NYSE, US:SETTLEMENT, TARGET, NULL"
    )


# ----------------------------
# Day count / year fractions
# ----------------------------

def get_day_count(name: str = "ACT365F") -> Any:
    """Return a QuantLib day-count convention."""

    key = name.replace(" ", "").upper()

    if key in {"ACT365F", "ACT/365F", "ACT365"}:
        return ql.Actual365Fixed()
    if key in {"ACT360", "ACT/360"}:
        return ql.Actual360()
    if key in {"30/360", "30_360", "30360"}:
        return ql.Thirty360(ql.Thirty360.BondBasis)

    raise ValueError(f"Unknown day count {name!r}. Supported: ACT365F, ACT360, 30/360")


def year_fraction(
    start: Any,
    end: Any,
    *,
    day_count: str = "ACT365F",
) -> float:
    """Compute year fraction between two dates using a day-count convention."""
    dc = get_day_count(day_count)
    d1 = to_ql_date(start)
    d2 = to_ql_date(end)
    return float(dc.yearFraction(d1, d2))


# ----------------------------
# Python-facing Calendar wrapper
# ----------------------------


class Calendar:
    """A small wrapper that accepts/returns Python dates while using QuantLib internally."""

    def __init__(self, name : str, day_count : str):

        self.name = name
        self.day_count = day_count
        self._calendar = get_calendar(name)
        self._day_counter = get_day_count(day_count)

    def _ql_calendar(self) -> Any:
        return self._calendar

    def _ql_day_count(self) -> Any:
        return self._day_counter

    def set_evaluation_date(self, value: Any) -> None:
        ql.Settings.instance().evaluationDate = to_ql_date(value)

    @contextmanager
    def evaluation_date(self, value: Any) -> Iterator[None]:
        with evaluation_date(value):
            yield

    def adjust(self, value: Any, convention: str = "FOLLOWING") -> dt.date:
        cal = self._ql_calendar()
        d = to_ql_date(value)

        key = convention.replace(" ", "").upper()
        mapping = {
            "FOLLOWING": ql.Following,
            "MODFOLLOWING": ql.ModifiedFollowing,
            "MODIFIEDFOLLOWING": ql.ModifiedFollowing,
            "PRECEDING": ql.Preceding,
            "UNADJUSTED": ql.Unadjusted,
        }
        if key not in mapping:
            raise ValueError(
                f"Unknown convention {convention!r}. Supported: FOLLOWING, MODFOLLOWING, PRECEDING, UNADJUSTED"
            )

        out = cal.adjust(d, mapping[key])
        return to_date(out)

    def is_business_day(self, value: Any) -> bool:
        cal = self._ql_calendar()
        d = to_ql_date(value)
        return bool(cal.isBusinessDay(d))

    def advance(
        self,
        value: Any,
        tenor,
        *,
        days: int = 0,
        months: int = 0,
        years: int = 0,
    ) -> dt.date:
        """Advance a date.

        Supports two calling styles:
          1) `advance(date, tenor)` where tenor is like '1M', '3M', '1Y'.
          2) `advance(date, days=..., months=..., years=...)`.

        Returns a Python `datetime.date`.
        """
        
        cal = self._ql_calendar()
        d = to_ql_date(value)

        # Tenor-style advance (e.g., advance(ref, '3M'))
        if isinstance(tenor, ql.Period):
            period = tenor
        elif isinstance(tenor, Tenor):
            period = tenor.to_ql_period()
        elif isinstance(tenor, str):
            period = parse_tenor(tenor).to_ql_period()
        else:
            raise TypeError("tenor must be str, Tenor, or ql.Period")

        out = cal.advance(d, period)
        
        return to_date(out)

    def add_tenor(self, value: Any, tenor: str) -> dt.date:
        cal = self._ql_calendar()
        d = to_ql_date(value)
        t = parse_tenor(tenor)
        out = cal.advance(d, t.to_ql_period())
        return to_date(out)

    def year_fraction(self, start: Any, end: Any) -> float:
        dc = self._ql_day_count()
        d1 = to_ql_date(start)
        d2 = to_ql_date(end)
        return float(dc.yearFraction(d1, d2))


# ----------------------------
# Optional: simple tenor parsing
# ----------------------------


class Tenor:
    def __init__(self, n : int, unit :str):
        self.n = n
        self.unit= unit # 'D', 'W', 'M', 'Y'

    def to_ql_period(self) -> Any:

        u = self.unit.upper()
        if u == "D":
            return ql.Period(self.n, ql.Days)
        if u == "W":
            return ql.Period(self.n, ql.Weeks)
        if u == "M":
            return ql.Period(self.n, ql.Months)
        if u == "Y":
            return ql.Period(self.n, ql.Years)
        raise ValueError(f"Invalid tenor unit {self.unit!r}. Expected one of D/W/M/Y")


def parse_tenor(value: str) -> Tenor:
        """Parse a tenor like '1D', '2W', '3M', '5Y' into a Tenor."""
        if not isinstance(value, str) or len(value.strip()) < 2:
            raise TypeError("tenor must be a string like '1D', '3M', '5Y'")

        s = value.strip().upper()
        unit = s[-1]
        num = s[:-1]

        if unit not in {"D", "W", "M", "Y"}:
            raise ValueError(f"Invalid tenor unit in {value!r}. Expected one of D/W/M/Y")

        try:
            n = int(num)
        except ValueError as e:
            raise ValueError(f"Invalid tenor number in {value!r}") from e

        if n <= 0:
            raise ValueError(f"Tenor must be positive. Got {value!r}")

        return Tenor(n=n, unit=unit)    