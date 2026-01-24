"""Utility functions for dates, calendars, and day-count conventions.

Design goal:
- QuantLib may be used internally for correctness.
- Public-facing helpers should accept and return standard Python types (e.g., `datetime.date`).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator

# QuantLib is an optional dependency at runtime for these utilities.
# We keep the import isolated here so the rest of the package doesn't need to import QuantLib directly.
try:
    import QuantLib as ql
except Exception as e:  # pragma: no cover
    ql = None  # type: ignore
    _QL_IMPORT_ERROR = e
else:
    _QL_IMPORT_ERROR = None


def _require_ql() -> Any:
    if ql is None:
        raise ImportError(
            "QuantLib is required for calendar/date utilities. Install QuantLib in your environment."
        ) from _QL_IMPORT_ERROR
    return ql


# ----------------------------
# Dates
# ----------------------------

def to_date(value: Any) -> date:
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

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as e:
            raise TypeError(
                "Date string must be ISO format 'YYYY-MM-DD'. "
                f"Got {value!r}."
            ) from e

    # QuantLib.Date support (optional)
    if ql is not None:
        ql_ = _require_ql()
        if isinstance(value, ql_.Date):
            # QuantLib Date has year(), month(), dayOfMonth()
            return date(int(value.year()), int(value.month()), int(value.dayOfMonth()))

    raise TypeError(
        "Date must be datetime.date/datetime, ISO string 'YYYY-MM-DD', "
        "or QuantLib.Date (if installed). "
        f"Got {type(value).__name__}."
    )


def to_ql_date(value: Any) -> Any:
    """Convert common date inputs to `QuantLib.Date`.

    This is an internal bridge when the underlying implementation uses QuantLib.
    Notebooks and user code should prefer `to_date(...)`.
    """
    ql_ = _require_ql()
    d = to_date(value)
    return ql_.Date(d.day, d.month, d.year)


@contextmanager
def evaluation_date(d: Any) -> Iterator[None]:
    """Temporarily set the QuantLib evaluation date within a scoped block."""
    ql_ = _require_ql()
    saved = ql_.SavedSettings()
    ql_.Settings.instance().evaluationDate = to_ql_date(d)
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
    ql_ = _require_ql()

    key = name.strip().upper()

    if key in {"US", "US:NYSE", "NYSE"}:
        return ql_.UnitedStates(ql_.UnitedStates.NYSE)
    if key in {"US:SETTLEMENT", "USSETTLEMENT"}:
        return ql_.UnitedStates(ql_.UnitedStates.Settlement)
    if key in {"TARGET", "EU:TARGET"}:
        return ql_.TARGET()
    if key in {"NULL", "NONE"}:
        return ql_.NullCalendar()

    raise ValueError(
        f"Unknown calendar {name!r}. Supported: US:NYSE, US:SETTLEMENT, TARGET, NULL"
    )


# ----------------------------
# Day count / year fractions
# ----------------------------

def get_day_count(name: str = "ACT365F") -> Any:
    """Return a QuantLib day-count convention."""
    ql_ = _require_ql()

    key = name.replace(" ", "").upper()

    if key in {"ACT365F", "ACT/365F", "ACT365"}:
        return ql_.Actual365Fixed()
    if key in {"ACT360", "ACT/360"}:
        return ql_.Actual360()
    if key in {"30/360", "30_360", "30360"}:
        return ql_.Thirty360(ql_.Thirty360.BondBasis)

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

@dataclass
class Calendar:
    """A small wrapper that accepts/returns Python dates while using QuantLib internally."""

    name: str = "US:NYSE"
    day_count: str = "ACT365F"

    def _ql_calendar(self) -> Any:
        return get_calendar(self.name)

    def _ql_day_count(self) -> Any:
        return get_day_count(self.day_count)

    def set_evaluation_date(self, value: Any) -> None:
        ql_ = _require_ql()
        ql_.Settings.instance().evaluationDate = to_ql_date(value)

    @contextmanager
    def evaluation_date(self, value: Any) -> Iterator[None]:
        with evaluation_date(value):
            yield

    def adjust(self, value: Any, convention: str = "FOLLOWING") -> date:
        ql_ = _require_ql()
        cal = self._ql_calendar()
        d = to_ql_date(value)

        key = convention.replace(" ", "").upper()
        mapping = {
            "FOLLOWING": ql_.Following,
            "MODFOLLOWING": ql_.ModifiedFollowing,
            "MODIFIEDFOLLOWING": ql_.ModifiedFollowing,
            "PRECEDING": ql_.Preceding,
            "UNADJUSTED": ql_.Unadjusted,
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
        tenor: str | None = None,
        *,
        days: int = 0,
        months: int = 0,
        years: int = 0,
    ) -> date:
        """Advance a date.

        Supports two calling styles:
          1) `advance(date, tenor)` where tenor is like '1M', '3M', '1Y'.
          2) `advance(date, days=..., months=..., years=...)`.

        Returns a Python `datetime.date`.
        """
        ql_ = _require_ql()
        cal = self._ql_calendar()
        d = to_ql_date(value)

        # Tenor-style advance (e.g., advance(ref, '3M'))
        if tenor is not None:
            t = parse_tenor(tenor)
            out = cal.advance(d, t.to_ql_period())
            return to_date(out)

        # Keyword-style advance
        if years:
            d = cal.advance(d, ql_.Period(int(years), ql_.Years))
        if months:
            d = cal.advance(d, ql_.Period(int(months), ql_.Months))
        if days:
            d = cal.advance(d, ql_.Period(int(days), ql_.Days))
        return to_date(d)

    def add_tenor(self, value: Any, tenor: str) -> date:
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

@dataclass(frozen=True)
class Tenor:
    n: int
    unit: str  # 'D', 'W', 'M', 'Y'

    def to_ql_period(self) -> Any:
        ql_ = _require_ql()
        u = self.unit.upper()
        if u == "D":
            return ql_.Period(self.n, ql_.Days)
        if u == "W":
            return ql_.Period(self.n, ql_.Weeks)
        if u == "M":
            return ql_.Period(self.n, ql_.Months)
        if u == "Y":
            return ql_.Period(self.n, ql_.Years)
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