from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from lawson_quant_library.model import BlackScholesAnalyticModel

from ..instrument import Instrument



class Option(Instrument):
    """
    Base option class.

    Design principles:
    - Pricing is delegated to an external model
    - A model may be passed per call or stored on the option instance
    - Greek methods (delta, gamma, vega) fall back to greeks() when unavailable

    Product-specific subclasses (EQOption, FXOption, IROption) inherit from this base.
    """
    

    def __init__(self, instrument_id:str, notional: float, maturity_date, option_type: str, style: str, underlying: str, strike: float, model, **kwargs) -> None:
        super().__init__(instrument_id, notional)
        self.maturity_date = maturity_date
        self.option_type = option_type
        self.strike = strike
        self.style = style
        self.underlying = underlying
        if self.style == "European":
            self.model = BlackScholesAnalyticModel
        else:
            self.model = model


        if self.style not in {"European", "American"}:
            raise ValueError(f"Unsupported option style: {self.style}")
        if self.underlying not in {"Equity", "FX"}:
            raise ValueError(f"Unsupported underlying type: {self.underlying}")
        if self.option_type not in {"call", "put", "Call", "Put"}:
            raise ValueError(f"Unsupported option type: {self.option_type}")





    # price the option using the assigned model
    def price(self, model, **kwargs: Any) -> float:
        return model.price(Option)

    # ---- Reused from your old Instrument.greeks() pattern ----
    def greeks(self, model: Optional[Any] = None, **kwargs: Any) -> Dict[str, float]:
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