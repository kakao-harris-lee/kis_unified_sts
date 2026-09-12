"""``tos_runtime.nontrade`` — the non-trade event consumer OUTSIDE the engine
(Phase 5 W5 plan §2 decision 6, lane f3).

Observes a non-trade event (:class:`~tos_runtime.nontrade.observations.NonTradeObservation`),
folds it through every applicable ``tos.nontrade`` kernel predicate
(:class:`~tos_runtime.nontrade.processor.NonTradeEventProcessor`), and records the
sole :class:`~tos.nontrade.vocabulary.NonTradeDisposition` producer's verdict as
durable evidence. **Applies nothing** — no capacity reservation, commitment,
release, or remap happens anywhere in this package; ``rcl`` is the sole capacity
authority (ADR-002-010 §1 line 19 / §10 line 217). See
:mod:`tos_runtime.nontrade.processor`'s module docstring for the full ownership
account, including what is deliberately left for a different lane to wire
(the new-risk latch entry point and the engine ``EventKind`` dispatch, both out
of scope here).
"""

from __future__ import annotations

from tos_runtime.nontrade.observations import NonTradeObservation
from tos_runtime.nontrade.processor import (
    NONTRADE_DISPOSITION_KIND,
    NONTRADE_MATERIAL_CHANGE_KIND,
    NonTradeEventProcessor,
    NonTradeOutcome,
)

__all__ = [
    "NONTRADE_DISPOSITION_KIND",
    "NONTRADE_MATERIAL_CHANGE_KIND",
    "NonTradeEventProcessor",
    "NonTradeObservation",
    "NonTradeOutcome",
]
