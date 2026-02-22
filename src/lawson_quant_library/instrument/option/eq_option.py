from __future__ import annotations

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
    instrument_id: Optional[str] = None,
    notional: float = 1.0,
    underlying = 'Equity',
    model = 'bs_analytic',
    ir_curve: Optional[IRCurve] = None,
    div_curve: Optional[DivCurve] = None,
    vol_surface: Optional[EQVol] = None,
    spot: Optional[float] = None,
    calendar: Calendar = Calendar('US:NYSE', 'ACT365F'),
    ):

        super().__init__(instrument_id=instrument_id, notional=notional, maturity_date=maturity_date, option_type=option_type, strike=strike, style=style, underlying=underlying)
        self.ir_curve = ir_curve
        self.div_curve = div_curve
        self.vol = vol_surface
        self.spot = float(spot)
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

        engine = self.model
        if engine != "bs_analytic":
            raise ValueError(
                "implied_vol is currently implemented for pricing_engine='bs_analytic' only. "
                f"Got {self.model!r}."
            )

        sigma = float(initial_vol)

        for _ in range(max_iter):
            # Build a temporary vol + model each iteration
            tmp_vol = EQVol(currency=getattr(self.vol, "currency", "USD"))
            tmp_vol.set_flat_vol(float(sigma), reference_date=reference_date)

            tmp_model = BlackScholesAnalyticModel(self,
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