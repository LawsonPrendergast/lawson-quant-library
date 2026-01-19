

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from lawson_quant_library.model.gk_analytic_fx import GarmanKohlhagenAnalyticFXModel
from lawson_quant_library.instrument.option import Option
from lawson_quant_library.util import Calendar


@dataclass
class FXOption(Option):
    """FX option instrument (placeholder; pricing engines to be added)."""

    # Underlying / economics
    spot: Optional[float] = None
    strike: Optional[float] = None
    maturity_date: Optional[Any] = None
    option_type: str = "call"  # "call" or "put"
    style: str = "european"  # keep consistent with EQOption usage

    # FX specifics
    domestic_ccy: Optional[str] = None  # e.g., "USD"
    foreign_ccy: Optional[str] = None  # e.g., "EUR"

    # Market parameters (placeholders)
    domestic_curve: Optional[Any] = None
    foreign_curve: Optional[Any] = None
    vol: Optional[Any] = None

    calendar: Optional[Calendar] = None

    # Engine wiring
    pricing_engine: str = "default"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.calendar is None:
            self.calendar = Calendar()

        # Default the underlying for this product type.
        if getattr(self, "underlying", None) in (None, ""):
            self.underlying = "FX"

        self.validate()

    def validate(self) -> None:
        if self.underlying not in {"FX"}:
            raise ValueError(f"FXOption requires underlying='FX'; got {self.underlying!r}")

        ot = str(self.option_type).lower()
        if ot not in {"call", "put"}:
            raise ValueError(f"option_type must be 'call' or 'put'; got {self.option_type!r}")

        st = str(self.style).lower()
        if st not in {"european"}:
            raise ValueError(f"Only european style supported for now; got {self.style!r}")

        if self.maturity_date is None:
            raise ValueError("maturity_date is required")

    # Pricing API (placeholder)
    def price(self, model: Any = None, **kwargs: Any) -> float:
        """Return the option price using the selected pricing engine.

        If `model` is provided, it is used directly. Otherwise, this dispatches
        to a model based on `self.pricing_engine`.
        """
        if model is not None:
            return float(model.price(self, **kwargs))

        engine = str(self.pricing_engine).lower()
        if engine in {"default", "gk_analytic"}:
            return float(GarmanKohlhagenAnalyticFXModel().price(self, **kwargs))

        raise ValueError(f"Unknown pricing engine {self.pricing_engine!r}")

    def delta(self, *args: Any, **kwargs: Any) -> float:
        raise NotImplementedError("FXOption greeks not implemented yet.")

    def vega(self, *args: Any, **kwargs: Any) -> float:
        raise NotImplementedError("FXOption greeks not implemented yet.")