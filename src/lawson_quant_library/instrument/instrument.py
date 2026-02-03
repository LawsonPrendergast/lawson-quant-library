from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Instrument:
    # Identity
    instrument_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trade_id: Optional[str] = None

    # Common economics / wiring
    notional: float = 1.0

    # Free-form metadata
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.trade_id is None:
            self.trade_id = self.instrument_id