from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from lawson_quant_library.instrument.option.option import Option
from lawson_quant_library.model.bs_analytic_eq import BlackScholesAnalyticModel
from lawson_quant_library.parameter import DivCurve, EQVol, IRCurve
from lawson_quant_library.util import Calendar, year_fraction


class EQOption(Option):
    """Equity option (product-specific Option subclass)."""
    def __init__(
    self,
    maturity_date,
    strike,
    option_type,
    style,
    underlying = 'Equity',
    model = 'bs_analytic',
    ir_curve: Optional[IRCurve] = None,
    div_curve: Optional[DivCurve] = None,
    vol_surface: Optional[EQVol] = None,
    spot: Optional[float] = None,
    calendar: Calendar = Calendar('US:NYSE', '365F'),
    ):
        super().__init__(maturity_date, option_type, strike, style, underlying)
        self.ir_curve = ir_curve
        self.div_curve = div_curve
        self.vol_curve = vol_surface
        self.spot = spot
        self.calendar = calendar
        self.model = model


        if self.underlying not in {"Equity", "EQ"}:
            raise ValueError(
                f"EQOption requires underlying='Equity' (or 'EQ'); got {self.underlying!r}"
            )




        # Only build if market inputs are present; do not raise here.


    # --- quality-of-life helpers ---
    def set_market(
        self,
        *,
        spot: Optional[float] = None,
        ir_curve: Optional[IRCurve] = None,
        div_curve: Optional[DivCurve] = None,
        vol: Optional[EQVol] = None,
        calendar: Optional[Calendar] = None,
    ) -> None:
        if spot is not None:
            self.spot = float(spot)
        if ir_curve is not None:
            self.ir_curve = ir_curve
        if div_curve is not None:
            self.div_curve = div_curve
        if vol is not None:
            self.vol = vol
        if calendar is not None:
            self.calendar = calendar

        # Normalize alias and clear model so it can be rebuilt on demand.
        

    def validate_market(self) -> None:
        missing = []
        if self.spot is None:
            missing.append("spot")
        if self.ir_curve is None:
            missing.append("ir_curve")
        if self.div_curve is None:
            missing.append("div_curve")
        if self.vol is None:
            missing.append("vol")
        if missing:
            raise ValueError("EQOption missing market inputs: " + ", ".join(missing))

    def implied_vol(
        self,
        target_price: float,
        *,
        reference_date: Any,
        initial_vol: float = 0.20,
        tol: float = 1e-6,
        max_iter: int = 100,
    ) -> float:
        """Compute implied volatility via Newton–Raphson (requires a reference_date for QuantLib term structures)."""
        self.validate_market()

        engine = str(getattr(self, "pricing_engine", "bs_analytic")).lower()
        if engine == "default":
            engine = "bs_analytic"
        if engine != "bs_analytic":
            raise ValueError(
                "implied_vol is currently implemented for pricing_engine='bs_analytic' only. "
                f"Got {self.pricing_engine!r}."
            )

        sigma = float(initial_vol)

        for _ in range(max_iter):
            # Build a temporary vol + model each iteration
            tmp_vol = EQVol(currency=getattr(self.vol, "currency", "USD"))
            tmp_vol.set_flat_vol(float(sigma), reference_date=reference_date)

            tmp_model = BlackScholesAnalyticModel(
                spot=float(self.spot),
                ir_curve=self.ir_curve,
                div_curve=self.div_curve,
                vol=tmp_vol,
            )

            price = float(tmp_model.price(self))
            diff = price - float(target_price)

            if abs(diff) < tol:
                return sigma

            vega = float(tmp_model.vega(self))
            if abs(vega) < 1e-8:
                raise RuntimeError("Vega too small for stable IV solve")

            sigma -= diff / vega
            if sigma <= 0.0:
                sigma = 1e-6

        raise RuntimeError("Implied vol solver failed to converge")

    def set_model(self, model: str) -> None:
        """Set pricing model by string and clear model so it can be rebuilt on demand."""
        # If Option defines a base setter, use it.)

        if getattr(self, "model", "default") == "default":
            self.pricing_engine = "bs_analytic"

        # Force rebuild on next pricing call.
        self.model = model