from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional



class Instrument:
    # base class instrument is used to assign specific random instrument id and notional; allows other reference data to be passed in

    def __init__(self, instrument_id: str, notional: float = 1.0, **kwargs) -> None:
        self.instrument_id = instrument_id or uuid.uuid4().hex
        self.notional = notional
        self.meta = {}

        