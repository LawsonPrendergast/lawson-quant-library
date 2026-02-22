"""Option instruments.

Keep this package `__init__` free of runtime imports to avoid circular-import
issues during module initialization.

Import concrete classes from their modules, e.g.:
    from lawson_quant_library.instrument.option.option import Option
    from lawson_quant_library.instrument.option.eq_option import EQOption
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .option import Option
    from .eq_option import EQOption

__all__ = ["Option", "EQOption"]