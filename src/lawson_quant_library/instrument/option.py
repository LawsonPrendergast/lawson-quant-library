from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .instrument import Instrument


@dataclass
class Option(Instrument):
    """
    Base option class.

    Reuses your old design:
    - delegate pricing to model
    - allow passing model per-call or stored on self
    - greek fallbacks: delta/gamma/vega use greeks() if individual methods missing

    Product-specific subclasses (EQOption, FXOption, IROption) will inherit this.
    """
    strike: float = 0.0
    maturity_date: Any = None  # leave flexible for now (QL Date, datetime.date, etc.)
    option_type: str = "call"  # "call" or "put"
    style: str = "European"    # "European" or "American"
    underlying: str = "Equity" # "Equity" or "FX" (extend later)

    # optional: a string label for engine selection later
    pricing_engine: str = "default"

    def __post_init__(self) -> None:
        self.strike = float(self.strike)
        self.notional = float(self.notional)

        if self.style not in {"European", "American"}:
            raise ValueError(f"Unsupported option style: {self.style}")
        if self.underlying not in {"Equity", "FX"}:
            raise ValueError(f"Unsupported underlying type: {self.underlying}")
        if self.option_type not in {"call", "put", "Call", "Put"}:
            raise ValueError(f"Unsupported option type: {self.option_type}")

    def set_pricing_engine(self, pricing_engine: str) -> None:
        """Set pricing engine by string and clear any cached model.

        Subclasses may override to rebuild a default model when market inputs
        are available.
        """
        self.pricing_engine = str(pricing_engine).lower()
        self.model = None

    def _maybe_build_default_model(self) -> Optional[Any]:
        """Hook for subclasses to build a default model based on pricing_engine + market inputs.

        Base Option does not know how to build a model. Subclasses (e.g. EQOption)
        should override and return an instantiated model when possible.
        """
        return None

    def _resolve_model(self, model: Optional[Any] = None) -> Any:
        """Resolve a pricing model.

        Priority:
          1) explicit `model=...`
          2) `self.model`
          3) attempt to build a default model via `_maybe_build_default_model()`
        """
        mdl = model or self.model
        if mdl is None:
            mdl = self._maybe_build_default_model()
            if mdl is not None:
                self.model = mdl
        if mdl is None:
            raise ValueError(
                "No pricing model available. Pass model=..., call set_model(...), or "
                "set pricing_engine + market inputs so a default model can be built."
            )
        return mdl

    # ---- Reused from your old Instrument.price() pattern ----
    def price(self, model: Optional[Any] = None, **kwargs: Any) -> float:
        mdl = self._resolve_model(model)
        if not hasattr(mdl, "price"):
            raise AttributeError("Model does not implement price().")
        return float(mdl.price(self, **kwargs))

    # ---- Reused from your old Instrument.greeks() pattern ----
    def greeks(self, model: Optional[Any] = None, **kwargs: Any) -> Dict[str, float]:
        mdl = self._resolve_model(model)
        if hasattr(mdl, "greeks"):
            g = mdl.greeks(self, **kwargs)
            if isinstance(g, dict):
                # normalize to float values when possible
                out: Dict[str, float] = {}
                for k, v in g.items():
                    try:
                        out[str(k)] = float(v)
                    except Exception:
                        # leave non-floats out rather than crashing
                        pass
                return out
            raise TypeError("Model.greeks() must return a dict.")
        raise AttributeError("Model does not implement greeks().")

    # ---- Reused from your old delta/gamma/vega fallback logic ----
    def delta(self, model: Optional[Any] = None, **kwargs: Any) -> float:
        mdl = self._resolve_model(model)
        if hasattr(mdl, "delta"):
            return float(mdl.delta(self, **kwargs))
        g = self.greeks(model=mdl, **kwargs)
        if "delta" in g:
            return float(g["delta"])
        raise AttributeError("Model does not implement delta() and greeks() has no 'delta'.")

    def gamma(self, model: Optional[Any] = None, **kwargs: Any) -> float:
        mdl = self._resolve_model(model)
        if hasattr(mdl, "gamma"):
            return float(mdl.gamma(self, **kwargs))
        g = self.greeks(model=mdl, **kwargs)
        if "gamma" in g:
            return float(g["gamma"])
        raise AttributeError("Model does not implement gamma() and greeks() has no 'gamma'.")

    def vega(self, model: Optional[Any] = None, **kwargs: Any) -> float:
        mdl = self._resolve_model(model)
        if hasattr(mdl, "vega"):
            return float(mdl.vega(self, **kwargs))
        g = self.greeks(model=mdl, **kwargs)
        if "vega" in g:
            return float(g["vega"])
        raise AttributeError("Model does not implement vega() and greeks() has no 'vega'.")