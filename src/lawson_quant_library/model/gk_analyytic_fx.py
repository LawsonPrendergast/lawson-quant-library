import math
from dataclasses import dataclass
from typing import Any, Optional


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using erf (no scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _to_ymd(date_like: Any) -> str:
    """Return YYYY-MM-DD string for common date inputs."""
    if date_like is None:
        raise ValueError("Date is None")

    # Already a YYYY-MM-DD string
    if isinstance(date_like, str):
        s = date_like.strip()
        # Accept ISO already
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        # Accept common US format MM/DD/YYYY
        if "/" in s and len(s.split("/")) == 3:
            mm, dd, yyyy = s.split("/")
            return f"{int(yyyy):04d}-{int(mm):02d}-{int(dd):02d}"
        raise ValueError(f"Unrecognized date string format: {date_like!r}")

    # QuantLib.Date-like: has year(), month(), dayOfMonth()
    if all(hasattr(date_like, a) for a in ("year", "month", "dayOfMonth")):
        return f"{int(date_like.year()):04d}-{int(date_like.month()):02d}-{int(date_like.dayOfMonth()):02d}"

    # datetime/date-like: has year, month, day
    if all(hasattr(date_like, a) for a in ("year", "month", "day")):
        return f"{int(date_like.year):04d}-{int(date_like.month):02d}-{int(date_like.day):02d}"

    raise ValueError(f"Unsupported date type: {type(date_like).__name__}")


def _year_fraction_act365(start: Any, end: Any) -> float:
    """ACT/365F year fraction for strings, datetime/date, or QuantLib.Date."""
    s = _to_ymd(start)
    e = _to_ymd(end)

    # Parse without importing pandas
    sy, sm, sd = int(s[:4]), int(s[5:7]), int(s[8:10])
    ey, em, ed = int(e[:4]), int(e[5:7]), int(e[8:10])

    import datetime as _dt

    d0 = _dt.date(sy, sm, sd)
    d1 = _dt.date(ey, em, ed)
    days = (d1 - d0).days
    return max(0.0, float(days) / 365.0)


def _get_curve_rate(curve: Any, t: float) -> float:
    """Best-effort read of a (possibly flat) rate from your curve objects."""
    if curve is None:
        return 0.0

    # Common methods
    for fn in ("rate", "zero_rate", "get_rate", "get_zero_rate"):
        if hasattr(curve, fn):
            try:
                return float(getattr(curve, fn)(t))
            except TypeError:
                # Some APIs require tenor/args; fall through
                pass

    # Common attributes
    for attr in ("flat_rate", "value", "level", "r"):
        if hasattr(curve, attr):
            return float(getattr(curve, attr))

    # As a last resort, try float(curve)
    try:
        return float(curve)
    except Exception as exc:
        raise TypeError(
            f"Could not infer a rate from curve object of type {type(curve).__name__}."
        ) from exc


def _get_vol(vol: Any) -> float:
    """Best-effort read of volatility from your EQVol/FXVol-style objects."""
    if vol is None:
        raise ValueError("vol is required")

    for fn in ("value", "get_value", "flat_vol", "get_flat_vol"):
        if hasattr(vol, fn):
            v = getattr(vol, fn)
            try:
                return float(v() if callable(v) else v)
            except TypeError:
                pass

    for attr in ("sigma", "vol", "level", "value"):
        if hasattr(vol, attr):
            return float(getattr(vol, attr))

    try:
        return float(vol)
    except Exception as exc:
        raise TypeError(f"Could not infer vol from object {type(vol).__name__}") from exc


@dataclass
class _GKInputs:
    s: float
    k: float
    t: float
    rd: float
    rf: float
    sigma: float
    is_call: bool


class GarmanKohlhagenAnalyticFXModel:
    """Garman-Kohlhagen analytic model for European FX options.

    This implementation is intentionally dependency-light (no QuantLib required).
    It expects the option to carry enough information to infer:
    - spot, strike, maturity_date
    - domestic and foreign (or dividend) rates/curves
    - volatility (flat) for now

    Convention: ACT/365F for time-to-expiry unless your option provides `year_fraction`.
    """

    def _inputs(self, option: Any, *, reference_date: Optional[Any] = None) -> _GKInputs:
        s = float(getattr(option, "spot"))
        k = float(getattr(option, "strike"))

        maturity = getattr(option, "maturity_date", None)
        if maturity is None:
            raise ValueError("Option is missing maturity_date")

        # Reference date: prefer explicit kwarg, then option.reference_date, then option.valuation_date
        ref = reference_date
        if ref is None:
            ref = getattr(option, "reference_date", None) or getattr(option, "valuation_date", None)
        if ref is None:
            # If nothing provided, assume pricing is at t=0 (but then greeks/price may be nonsensical)
            raise ValueError(
                "reference_date is required for GK model (pass reference_date=... or set option.reference_date)."
            )

        # If the option provides its own year fraction, use it
        if hasattr(option, "year_fraction") and callable(getattr(option, "year_fraction")):
            t = float(option.year_fraction(ref, maturity))
        else:
            t = _year_fraction_act365(ref, maturity)

        if t <= 0.0:
            raise ValueError(f"Non-positive time to expiry T={t}. Check reference_date/maturity_date.")

        # Rates: support a few naming conventions
        rd_curve = getattr(option, "rd_curve", None) or getattr(option, "domestic_curve", None) or getattr(option, "ir_curve", None)
        rf_curve = getattr(option, "rf_curve", None) or getattr(option, "foreign_curve", None) or getattr(option, "div_curve", None)

        rd = _get_curve_rate(rd_curve, t)
        rf = _get_curve_rate(rf_curve, t)

        vol_obj = getattr(option, "vol", None) or getattr(option, "fx_vol", None)
        sigma = _get_vol(vol_obj)
        if sigma <= 0.0:
            raise ValueError(f"Vol must be positive. Got sigma={sigma}.")

        opt_type = str(getattr(option, "option_type", "call")).lower()
        is_call = opt_type.startswith("c")

        return _GKInputs(s=s, k=k, t=t, rd=rd, rf=rf, sigma=sigma, is_call=is_call)

    @staticmethod
    def _d1_d2(inp: _GKInputs) -> tuple[float, float]:
        s, k, t, rd, rf, sigma = inp.s, inp.k, inp.t, inp.rd, inp.rf, inp.sigma
        st = sigma * math.sqrt(t)
        if st <= 0.0:
            raise ValueError("sigma*sqrt(T) must be > 0")
        d1 = (math.log(s / k) + (rd - rf + 0.5 * sigma * sigma) * t) / st
        d2 = d1 - st
        return d1, d2

    def price(self, option: Any, **kwargs: Any) -> float:
        inp = self._inputs(option, reference_date=kwargs.get("reference_date"))
        d1, d2 = self._d1_d2(inp)

        df_d = math.exp(-inp.rd * inp.t)
        df_f = math.exp(-inp.rf * inp.t)

        if inp.is_call:
            return inp.s * df_f * _norm_cdf(d1) - inp.k * df_d * _norm_cdf(d2)
        return inp.k * df_d * _norm_cdf(-d2) - inp.s * df_f * _norm_cdf(-d1)

    def delta(self, option: Any, **kwargs: Any) -> float:
        """Spot delta (not premium-adjusted)."""
        inp = self._inputs(option, reference_date=kwargs.get("reference_date"))
        d1, _ = self._d1_d2(inp)
        df_f = math.exp(-inp.rf * inp.t)
        if inp.is_call:
            return df_f * _norm_cdf(d1)
        return df_f * (_norm_cdf(d1) - 1.0)

    def vega(self, option: Any, **kwargs: Any) -> float:
        """Vega per 1.0 vol (i.e., dPrice/dSigma)."""
        inp = self._inputs(option, reference_date=kwargs.get("reference_date"))
        d1, _ = self._d1_d2(inp)
        df_f = math.exp(-inp.rf * inp.t)
        return inp.s * df_f * _norm_pdf(d1) * math.sqrt(inp.t)

    def gamma(self, option: Any, **kwargs: Any) -> float:
        """Spot gamma."""
        inp = self._inputs(option, reference_date=kwargs.get("reference_date"))
        d1, _ = self._d1_d2(inp)
        df_f = math.exp(-inp.rf * inp.t)
        return df_f * _norm_pdf(d1) / (inp.s * inp.sigma * math.sqrt(inp.t))