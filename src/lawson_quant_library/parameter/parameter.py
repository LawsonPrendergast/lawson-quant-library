# src/lawson_quant_library/parameter/parameter.py

from __future__ import annotations

from typing import Any


class Parameter:
    """Base class for market parameters (curves, vols, etc.)."""

    def __init__(self, name: str, **kwargs) -> None:
        self.name = name
        