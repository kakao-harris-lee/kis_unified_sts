"""``tos_runtime.posttrade`` — SYNTHETIC-transport post-trade finality producer (TOS Phase 3
Wave 2 Lane C-R; plan §2.2).

Everything in this package is scoped to the SYNTHETIC paper transport only: a real broker's
finality evidence is Phase 5 reconciliation work (ADR-002-030 §1 line 21 keeps the Risk Capacity
Ledger the sole capacity mutation authority regardless — this package never touches capacity
itself, it only produces the :class:`~tos.posttrade.records.PostTradeFinalityProof` a release
call site may supply as its ``finality_witness`` input, via :mod:`tos_runtime.rcl.finality_witness`).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``pydantic`` (transitively)
+ ``yaml`` (config only) + ``tos.canonical``/``tos.engine.records``/``tos.engine.vocabulary``/
``tos.posttrade`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

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
