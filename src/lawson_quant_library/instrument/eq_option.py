from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from lawson_quant_library.instrument.option import Option
from lawson_quant_library.model.bs_analytic_eq import BlackScholesAnalyticEQModel
from lawson_quant_library.parameter import DivCurve, EQVol, IRCurve


@dataclass
class EQOption(Option):
    """Equity option (product-specific Option subclass)."""

    ir_curve: Optional[IRCurve] = None
    div_curve: Optional[DivCurve] = None
    vol: Optional[EQVol] = None
    spot: Optional[float] = None

    def __post_init__(self) -> None:
        super().__post_init__()

        if self.underlying not in {"Equity", "EQ"}:
            raise ValueError(
                f"EQOption requires underlying='Equity' (or 'EQ'); got {self.underlying!r}"
            )

        # Normalize engine naming: treat "default" as the first supported engine.
        if getattr(self, "pricing_engine", None) == "default":
            self.pricing_engine = "bs_analytic"

        # Do not force-build the model here; market may be set later via set_market().
        if self.model is None:
            self.model = self._maybe_build_default_model()

        

    def _maybe_build_default_model(self) -> Optional[Any]:
        """Map `pricing_engine` -> concrete model.

        Returns None if the engine is unsupported or if required market inputs
        are not yet set.
        """
        # Normalize engine naming defensively.
        if self.pricing_engine == "default":
            self.pricing_engine = "bs_analytic"

        if self.pricing_engine != "bs_analytic":
            return None

        # Only build if market inputs are present; do not raise here.
        if self.spot is None or self.ir_curve is None or self.div_curve is None or self.vol is None:
            return None

        return BlackScholesAnalyticEQModel(
            spot=float(self.spot),
            ir_curve=self.ir_curve,
            div_curve=self.div_curve,
            vol=self.vol,
        )

    # --- quality-of-life helpers ---
    def set_market(
        self,
        *,
        spot: Optional[float] = None,
        ir_curve: Optional[IRCurve] = None,
        div_curve: Optional[DivCurve] = None,
        vol: Optional[EQVol] = None,
    ) -> None:
        if spot is not None:
            self.spot = float(spot)
        if ir_curve is not None:
            self.ir_curve = ir_curve
        if div_curve is not None:
            self.div_curve = div_curve
        if vol is not None:
            self.vol = vol

        # refresh model if we are using the default engine wiring
        if self.pricing_engine == "default":
            self.pricing_engine = "bs_analytic"
        if self.model is None and self.pricing_engine == "bs_analytic":
            self.model = self._maybe_build_default_model()

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

        engine = "bs_analytic" if self.pricing_engine == "default" else self.pricing_engine
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

            tmp_model = BlackScholesAnalyticEQModel(
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

    def set_pricing_engine(self, pricing_engine: str) -> None:
        """Set pricing engine by string and rebuild default model if possible."""
        self.pricing_engine = str(pricing_engine).lower()

        # Normalize alias
        if self.pricing_engine == "default":
            self.pricing_engine = "bs_analytic"

        # Clear any existing model
        self.model = None

        # Rebuild if market is already present
        if self.pricing_engine == "bs_analytic":
            self.model = self._maybe_build_default_model()