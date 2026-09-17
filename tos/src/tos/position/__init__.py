"""tos.position — pure position-observation records + predicates (kernel round #4 K-2).

Ported out of ``tos_runtime.riskstate.position`` (TOS risk state service wave, DR-0003 §2.2):
the pure value type (:class:`PositionObservation`), the per-attempt sealed-send fact
(:class:`SealedSend`), and the pure predicates over them (magnitude functions + the
classification table) are promoted to the kernel; the durable-evidence I/O (reading the
``SqliteEvidenceStore``, JSON decoding, ``(account, instrument)`` scope filtering) stays in the
runtime's ``EvidencePositionReader``, which now calls into this package instead of carrying the
pure logic itself (kernel round #4 plan K-2 — "런타임의 I/O 는 그대로 두고, 런타임은 새 커널
패키지를 호출하도록만 바꾼다").

Pure module: ``pydantic`` + stdlib (``decimal``, ``collections.abc``) + ``tos.canonical`` only;
no ``shared.*``, no sibling ``tos.*``.
"""

from __future__ import annotations

from tos.position.predicates import (
    classify_sealed_sends,
    conservative_current_usage,
    in_flight_overlap_effect,
    sign_of,
    worst_credible_directional_usage,
)
from tos.position.records import PositionObservation, SealedSend

__all__ = [
    "PositionObservation",
    "SealedSend",
    "worst_credible_directional_usage",
    "conservative_current_usage",
    "in_flight_overlap_effect",
    "sign_of",
    "classify_sealed_sends",
]
