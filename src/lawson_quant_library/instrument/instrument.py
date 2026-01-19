from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Instrument:
    # Identity
    instrument_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trade_id: Optional[str] = None

    # Generic template fields (subclasses may use/override as needed)
    instrument_type: Optional[str] = None
    currency: Optional[str] = None
    strike: Optional[float] = None
    maturity_date: Optional[Any] = None

    # Common economics / wiring
    notional: float = 1.0
    model_type: Optional[str] = None
    model: Optional[Any] = None

    # Free-form metadata
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.trade_id is None:
            self.trade_id = self.instrument_id

    def set_model(self, model: Any) -> None:
        self.model = model