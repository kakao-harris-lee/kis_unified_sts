"""``tos_runtime.nontrade`` — non-trade event conversion + dry-run evaluation (originally Phase 5
W5 plan §2 decision 6, lane f3; the engine is now the sole stateful path — TOS runtime
operations wiring plan, 2026-09-13, §2 decision 3).

Three pieces:

* :class:`~tos_runtime.nontrade.observations.NonTradeObservation` — the runtime-observed fact
  record, prior to any kernel decision.
* :func:`~tos_runtime.nontrade.convert.payload_from_observation` — converts one into the
  kernel's own :class:`~tos.engine.records.CorporateActionPayload`, the SAME conversion both the
  engine path (:meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`) and the
  kernel/dry-run equivalence test use.
* :class:`~tos_runtime.nontrade.processor.NonTradeEventProcessor` — a DRY-RUN evaluator only
  (:meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.evaluate`); records no evidence,
  touches no durable state. The stateful path — folding a disposition through every applicable
  ``tos.nontrade`` kernel predicate AND latching a new-risk halt when restrictive — now runs
  through the engine (:mod:`tos_runtime.engine.driver`) via
  :func:`~tos_runtime.nontrade.latch.latch_restrictive`, not through this package (this
  package's own structural pin forbids it from importing ``tos_runtime.engine``/``.rcl``/
  ``.recovery``/``.transport`` at all — ``tests/nontrade/test_processor.py``). **Applies
  nothing** either way — no capacity reservation, commitment, release, or remap happens anywhere
  in this package or in the engine's own ``CORPORATE_ACTION`` handler; ``rcl`` is the sole
  capacity authority (ADR-002-010 §1 line 19 / §10 line 217).

See :mod:`tos_runtime.nontrade.processor`'s and :mod:`tos_runtime.nontrade.latch`'s own module
docstrings for the full ownership account.
"""

from __future__ import annotations

from tos_runtime.nontrade.convert import payload_from_observation
from tos_runtime.nontrade.latch import LatchOutcome, latch_restrictive
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
    "LatchOutcome",
    "NonTradeEventProcessor",
    "NonTradeObservation",
    "NonTradeOutcome",
    "latch_restrictive",
    "payload_from_observation",
]
