"""tos.ordering — shared causal-ordering primitive (time design §0.4b/§5 PROMOTE).

The §11 / §10 causal-ordering law promoted out of ``tos.evidence.predicates`` so
both ``tos.evidence`` and ``tos.time`` share it in one direction, with no
evidence <-> time import (time design §5 layering). ``tos.evidence.predicates``
re-exports these symbols through a thin shim, so existing
``from tos.evidence.predicates import Ordering / OrderingEvent / compare_order``
(and ``from tos.evidence import ...``) paths are unchanged and ERI-EV-006 stays
green.

Depends only on ``tos.canonical`` (for :class:`~tos.canonical.FrozenModel`); it
imports no other ``tos`` package.

Pure package: ``pydantic`` + stdlib + ``tos.canonical`` only (time design §0.3).
"""

from __future__ import annotations

from tos.ordering._ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "Ordering",
    "OrderingEvent",
    "compare_order",
]
