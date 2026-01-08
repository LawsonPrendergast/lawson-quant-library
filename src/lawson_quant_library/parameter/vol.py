from __future__ import annotations

from typing import Any, Optional, Sequence
import QuantLib as ql

from lawson_quant_library.parameter.parameter import Parameter
from lawson_quant_library.util import (
    Calendar,
    get_calendar,
    get_day_count,
)


class EQVol(Parameter):
    """Equity volatility parameter (flat vol first pass)."""

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

        self._handle = ql.RelinkableBlackVolTermStructureHandle()
        self._vol = None

    @property
    def handle(self) -> ql.BlackVolTermStructureHandle:
        return self._handle

    def set_flat_vol(self, vol: float, *, reference_date: Any) -> None:
        sigma = float(vol)

        cal = Calendar(name=self.calendar, day_count=self.day_count)
        with cal.evaluation_date(reference_date):
            today = ql.Settings.instance().evaluationDate
            vol_ts = ql.BlackConstantVol(
                today,
                self._calendar,
                sigma,
                self._day_count,
            )

        self._vol = vol_ts
        self._handle.linkTo(vol_ts)

    def set_surface_vol(
        self,
        *,
        strikes: Sequence[float],
        tenors: Sequence[str],
        vols: Sequence[Sequence[float]],
        reference_date: Any,
        extrapolate: bool = True,
    ) -> None:
        """
        Build a Black vol surface from a simple grid.

        Inputs:
          - tenors: e.g. ["1M","3M","6M","1Y"]
          - strikes: e.g. [80,90,100,110,120]
          - vols: shape (len(tenors), len(strikes)) where vols[t][k] is the vol for tenors[t] and strikes[k]
        """
        if len(tenors) == 0 or len(strikes) == 0:
            raise ValueError("tenors and strikes must be non-empty.")
        if len(vols) != len(tenors):
            raise ValueError("vols must have one row per tenor (len(vols) == len(tenors)).")
        for row in vols:
            if len(row) != len(strikes):
                raise ValueError("Each vols row must have length len(strikes).")

        cal = Calendar(name=self.calendar, day_count=self.day_count)
        with cal.evaluation_date(reference_date):
            today = ql.Settings.instance().evaluationDate

            # Build expiry dates by advancing from reference_date by each tenor.
            expiry_dates = [cal.add_tenor(reference_date, t) for t in tenors]
            strike_list = [float(k) for k in strikes]

            # QuantLib expects a Matrix with dimensions [strikes x dates]
            m = ql.Matrix(len(strike_list), len(expiry_dates))
            for j in range(len(expiry_dates)):          # tenor/date index
                for i in range(len(strike_list)):       # strike index
                    m[i][j] = float(vols[j][i])

            surface = ql.BlackVarianceSurface(
                today,
                self._calendar,
                list(expiry_dates),
                strike_list,
                m,
                self._day_count,
            )

            # Smoothness / interpolation choice (bilinear is fine for a first pass).
            surface.setInterpolation("bilinear")

            if extrapolate:
                surface.enableExtrapolation()

        self._vol = surface
        self._handle.linkTo(surface)