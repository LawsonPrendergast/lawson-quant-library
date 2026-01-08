from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Instrument:
    """
    Base instrument object. Holds identity + metadata.
    Pricing should be delegated to a model/engine in subclasses (e.g., Option).
    """
    instrument_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_id: Optional[str] = None

    notional: float = 1.0
    model: Optional[Any] = None  # model/pricing engine object

    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # If no trade_id is provided, default it to instrument_id
        if self.trade_id is None:
            self.trade_id = self.instrument_id

    def set_model(self, model: Any) -> None:
        self.model = model