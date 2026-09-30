"""tos.position pure records — the position-observation value substrate (kernel round #4 K-2).

Ported from ``tos_runtime.riskstate.position`` (TOS risk state service wave, DR-0003 §2.2 "The
position observation is a single-source, conservative fill sum"), unchanged in shape and
arithmetic — this module carries **no I/O**; the durable evidence-store read (which durable
kind carried which fact, JSON decoding, scope filtering) stays in the runtime, which is the only
side of this boundary that ever touches ``sqlite3`` / ``json`` (kernel round #4 plan K-2 "런타임
의 I/O 는 그대로").

:class:`PositionObservation` is a pydantic v2 frozen model (kernel convention — every artifact
is ``ConfigDict(frozen=True, extra="forbid")``, design #19 §2.0), not the runtime's original
plain ``@dataclass(frozen=True)``: same field names, same types, same immutability, promoted to
the kernel's own schema-strict substrate. All magnitudes are contract counts (never a
valuation/notional dimension — DR-0003 §2.2 "it is contract-count only"). ``sources`` names
only the evidence kinds actually read by the runtime reader, never a blanket corroboration
claim.

:class:`SealedSend` is the pure per-attempt fact :func:`~tos.position.predicates
.classify_sealed_sends` folds over — one durably sealed send's ``(attempt_id, side, quantity)``,
with ``side`` left as a bare ``str | None`` (never a closed kernel enum — CLAUDE.md "Futures
must preserve long/short symmetry"; the recognized tokens are injected by the caller, exactly
as the runtime's own ``EvidencePositionReader`` requires them as constructor arguments, never a
literal this package invents).

Pure module: ``pydantic`` + stdlib (``decimal``) + ``tos.canonical`` only; no ``shared.*``, no
sibling ``tos.*`` (mirrors every other kernel package's §0.3 pure-module discipline).
"""

from __future__ import annotations

from decimal import Decimal

from tos.canonical import FrozenModel

__all__ = [
    "PositionObservation",
    "SealedSend",
]


class PositionObservation(FrozenModel):
    """One (account, instrument) scope's conservative position observation (DR-0003 §2.2 /
    plan §4.1). All magnitudes are contract counts. ``sources`` names only the evidence kinds
    actually read, never a blanket claim of corroboration."""

    scope_key: str
    confirmed_net: Decimal
    unknown_buy: Decimal
    unknown_sell: Decimal
    in_flight_buy: Decimal
    in_flight_sell: Decimal
    attempts_seen: int
    sources: tuple[str, ...] = ()


class SealedSend(FrozenModel):
    """One durably-sealed send's ``(attempt_id, side, quantity)`` (runtime docstring's
    ``_SealedSend``), the exact input :func:`~tos.position.predicates.classify_sealed_sends`
    folds — ``side`` is an injected token, never a closed enum; ``quantity`` may be ``None``
    (an unrecorded seal quantity, treated as zero by the classifier, never guessed)."""

    attempt_id: str
    side: str | None = None
    quantity: Decimal | None = None
