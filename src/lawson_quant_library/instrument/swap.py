from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from lawson_quant_library.instrument.instrument import Instrument
from lawson_quant_library.util import Calendar


@dataclass
class Swap(Instrument):
    """Interest rate swap placeholder (pricing to be implemented)."""

    # Core economics
    pay_receive: str = "pay"  # "pay" fixed / receive float by convention
    effective_date: Optional[Any] = None
    maturity_date: Optional[Any] = None
    notional: float = 1.0

    # Fixed leg
    fixed_rate: Optional[float] = None
    fixed_frequency: str = "6M"

    # Floating leg
    float_index: Optional[str] = None  # e.g., "SOFR", "USD-LIBOR-3M"
    float_frequency: str = "3M"

    # Market wiring (placeholders)
    discount_curve: Optional[Any] = None
    forward_curve: Optional[Any] = None
    calendar: Optional[Calendar] = None

    # Engine wiring
    pricing_engine: str = "default"

    def __init__(self) -> None:
        if self.calendar is None:
            self.calendar = Calendar()

    def validate(self) -> None:
        pr = str(self.pay_receive).lower()
        if pr not in {"pay", "receive"}:
            raise ValueError(f"pay_receive must be 'pay' or 'receive'; got {self.pay_receive!r}")
        if self.maturity_date is None:
            raise ValueError("maturity_date is required")

    def price(self, *args: Any, **kwargs: Any) -> float:
        """Return NPV (not implemented yet)."""
        raise NotImplementedError("Swap pricing not implemented yet.")