from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict

from QuantLib import (
    AnalyticEuropeanEngine,
    BlackScholesMertonProcess,
    Date as QLDate,
    EuropeanExercise,
    Option,              
    PlainVanillaPayoff,
    QuoteHandle,
    SimpleQuote,
    VanillaOption,     
)

from lawson_quant_library.parameter import DivCurve, EQVol, IRCurve


@dataclass
class BlackScholesAnalyticEQModel:
    """Analytic Black–Scholes (Merton) model for European equity options.

    This model is intentionally small and explicit so you can learn the flow:
      1) Build a stochastic process (spot + q + r + vol)
      2) Build payoff/exercise from the Option
      3) Attach the analytic engine
      4) Read NPV and greeks from QuantLib

    Notes:
      - This engine supports EUROPEAN exercise only.
      - QuantLib objects live ONLY in the model layer (this file).
      - Notebooks should call your library API (EQOption.price/greeks), not QuantLib.
      - Maturity can be passed as QuantLib.Date, datetime.date/datetime, or ISO string (YYYY-MM-DD).
    """

    spot: float
    ir_curve: IRCurve
    div_curve: DivCurve
    vol: EQVol

    def __post_init__(self) -> None:
        self._spot_quote = SimpleQuote(float(self.spot))
        self._spot_handle = QuoteHandle(self._spot_quote)

        self._process = BlackScholesMertonProcess(
            self._spot_handle,
            self.div_curve.handle,
            self.ir_curve.handle,
            self.vol.handle,
        )

        self._engine = AnalyticEuropeanEngine(self._process)

    # ---- public API (used by Option.price / Option.greeks) ----
    def set_spot(self, new_spot: float) -> None:
        """Update spot without rebuilding the model."""
        self._spot_quote.setValue(float(new_spot))

    def price(self, option: Any, **_: Any) -> float:
        ql_opt = self._build_ql_option(option)
        ql_opt.setPricingEngine(self._engine)
        return float(ql_opt.NPV())

    def greeks(self, option: Any, **_: Any) -> Dict[str, float]:
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
    def _build_ql_option(self, option: Any) -> VanillaOption:
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
        """Convert common date inputs to QuantLib.Date."""
        if value is None:
            raise TypeError("maturity_date is required.")

        if isinstance(value, QLDate):
            return value

        if isinstance(value, datetime):
            value = value.date()

        if isinstance(value, date):
            return QLDate(value.day, value.month, value.year)

        if isinstance(value, str):
            try:
                dt = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError as e:
                raise TypeError(
                    "maturity_date string must be ISO format 'YYYY-MM-DD'. "
                    f"Got {value!r}."
                ) from e
            return QLDate(dt.day, dt.month, dt.year)

        raise TypeError(
            "maturity_date must be QuantLib.Date, datetime.date/datetime, or ISO string 'YYYY-MM-DD'. "
            f"Got {type(value).__name__}."
        )