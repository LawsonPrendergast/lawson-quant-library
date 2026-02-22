from __future__ import annotations

from lawson_quant_library.util import to_date, Calendar
from typing import Any, Dict
from datetime import date
from lawson_quant_library.instrument.option.option import Option
from QuantLib import (
    AnalyticEuropeanEngine,
    BlackScholesMertonProcess,
    Date as QLDate,
    EuropeanExercise,              
    PlainVanillaPayoff,
    QuoteHandle,
    SimpleQuote,
    VanillaOption,    
)




class BlackScholesAnalyticModel:
    """Analytic Black–Scholes–Merton model for European equity options."""
    def __init__(self, option: any, **kwargs):
        self.ir_curve = option.ir_curve
        self.div_curve = option.div_curve
        self.vol = option.vol
        self.spot = option.spot

        self._spot_quote = SimpleQuote(float(self.spot))
        self._spot_handle = QuoteHandle(self._spot_quote)
        rf_handle = self.ir_curve.handle
        div_handle = self.div_curve.handle
        vol_handle = self.vol.handle
        



        self._process = BlackScholesMertonProcess(
            self._spot_handle,
            self.div_handle,
            self.rf_handle,
            self.vol_handle,
        )

        self._engine = AnalyticEuropeanEngine(self._process)

    # ---- public API (used by Option.price / Option.greeks) ----
    def set_spot(self, new_spot: float) -> None:
        """Update spot without rebuilding the model."""
        self._spot_quote.setValue(float(new_spot))

    def price(self, option: Option, **kwargs: Any) -> float:
        ql_opt = self._build_ql_option(option)
        ql_opt.setPricingEngine(self._engine)
        return float(ql_opt.NPV())

    def vega(self, option: Option, **_: Any) -> float:
        """Return option vega (dPrice/dVol). Convenience wrapper around `greeks()`."""
        return float(self.greeks(option).get("vega", 0.0))
    
    def delta(self, option: Option, **_: Any) -> float:
        """Return option delat (dPrice/dspot). Convenience wrapper around `greeks()`."""
        return float(self.greeks(option).get("delta", 0.0))
    
    def greeks(self, option: Option, **_: Any) -> Dict[str, float]:
        ql_opt = self._build_ql_option(option)
        ql_opt.setPricingEngine(self._engine)

        return {
            "delta": float(ql_opt.delta()),
            "gamma": float(ql_opt.gamma()),
            "vega": float(ql_opt.vega()),
            "theta": float(ql_opt.theta()),
            "rho": float(ql_opt.rho()),
        }

    # ---- internal helpers ----
    def _build_ql_option(self, option: Option) -> VanillaOption:
        if getattr(option, "style", "European") != "European":
            raise ValueError(
                "BlackScholesAnalyticEQModel only supports European options. "
                f"Got style={getattr(option, 'style', None)!r}."
            )

        maturity_raw = getattr(option, "maturity_date", None)
        maturity = self._to_ql_date(maturity_raw)

        strike = float(getattr(option, "strike"))
        opt_type = str(getattr(option, "option_type")).lower()
        if opt_type not in {"call", "put"}:
            raise ValueError(f"option_type must be 'call' or 'put'. Got {opt_type!r}.")
        ql_type = Option.Call if opt_type == "call" else Option.Put

        payoff = PlainVanillaPayoff(ql_type, strike)
        exercise = EuropeanExercise(maturity)
        return VanillaOption(payoff, exercise)

    @staticmethod
    def _to_ql_date(value: Any) -> QLDate:
        if value is None:
            raise TypeError("maturity_date is required.")

        # Allow passing QuantLib.Date directly.
        if isinstance(value, QLDate):
            return value

        # Normalize common Python inputs (str / datetime / date) to a Python date.
        py_date = to_date(value)
        return QLDate(py_date.day, py_date.month, py_date.year)