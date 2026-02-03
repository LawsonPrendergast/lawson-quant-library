from dataclasses import dataclass
from typing import Optional

from lawson_quant_library.instrument.option.option import Option


@dataclass
class FixedStrikeOption(Option):
    """
    Base class for options with a fixed strike.

    This adds a strike attribute, representing the exercise price,
    which is not present on the generic Option base class.  
    Most vanilla and fixed-strike exotic options derive from this.
    """

    strike: float

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.strike <= 0:
            raise ValueError("FixedStrikeOption requires a positive strike.")