from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular imports at runtime
    from lawson_quant_library.model.bs_analytic_eq import BlackScholesAnalyticEQModel
    from lawson_quant_library.parameter import IRCurve, EQVol, DivCurve

from lawson_quant_library.instrument.option.fixedstrikeoption.fixed_strike_option import (
    FixedStrikeOption,
)
from lawson_quant_library.util import Calendar


@dataclass
class VanillaOption(FixedStrikeOption):
    """
    Vanilla (fixed-strike) equity option.

    This class is a specialization of FixedStrikeOption; every vanilla option
    has a strike and standard attributes like expiry, and optionally
    market inputs such as vol, IR curve, and dividend curve.
    """

    calendar: Calendar
    vol: "EQVol"
    ir_curve: "IRCurve"
    div_curve: "DivCurve"

    model: "BlackScholesAnalyticEQModel" | None = None

    def __post_init__(self) -> None:
        super().__post_init__()  # runs FixedStrikeOption + Option base logic

        # Option-specific checks
        if self.vol is None:
            raise ValueError("VanillaOption requires a volatility surface/instance.")
        if self.ir_curve is None:
            raise ValueError("VanillaOption requires an interest rate curve.")
        if self.div_curve is None:
            raise ValueError("VanillaOption requires a dividend curve.")