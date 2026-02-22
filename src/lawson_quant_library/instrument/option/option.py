from __future__ import annotations


from typing import Any, Dict, Optional

from lawson_quant_library.instrument.instrument import Instrument



class Option(Instrument):
    """
    Base option class.

    Design principles:
    - Pricing is delegated to an external model
    - A model may be passed per call or stored on the option instance
    - Greek methods (delta, gamma, vega) fall back to greeks() when unavailable

    Product-specific subclasses (EQOption, FXOption, IROption) inherit from this base.
    """
    

    def __init__(self, instrument_id:str, notional: float, maturity_date, option_type: str, style: str, underlying: str, strike: float,  **kwargs) -> None:
        super().__init__(instrument_id, notional)
        self.maturity_date = maturity_date
        self.option_type = option_type
        self.strike = strike
        self.style = style
        self.underlying = underlying


        if self.style not in {"European", "American"}:
            raise ValueError(f"Unsupported option style: {self.style}")
        if self.underlying not in {"Equity", "FX"}:
            raise ValueError(f"Unsupported underlying type: {self.underlying}")
        if self.option_type not in {"call", "put", "Call", "Put"}:
            raise ValueError(f"Unsupported option type: {self.option_type}")