"""``tos_runtime.posttrade`` — SYNTHETIC-transport post-trade finality producer (TOS Phase 3"""

from __future__ import annotations

from tos_runtime.posttrade.config import (
    FinalityConfig,
    FinalityConfigError,
    load_finality_config,
)
from tos_runtime.posttrade.finality import SyntheticFinalityProducer

__all__ = [
    "FinalityConfig",
    "FinalityConfigError",
    "SyntheticFinalityProducer",
    "load_finality_config",
]
