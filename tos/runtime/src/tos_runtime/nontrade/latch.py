"""``latch_restrictive`` — the SOLE shared implementation of "a restrictive non-trade
disposition latches a durable new-risk halt" (TOS runtime operations wiring plan, 2026-09-13, §2
decision 3).

**Why this exists.** Before this module, exactly one caller
(:meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`) reached the new-risk
halt latch from the non-trade side, wired directly against the dry-run
:class:`~tos_runtime.nontrade.processor.NonTradeEventProcessor`. Kernel round #3 gave the
ENGINE its own judged outcome (``EventResult.nontrade_outcome`` —
:class:`~tos.engine.records.NonTradeOutcome`), so :mod:`tos_runtime.engine.driver` now needs to
latch too. Rather than two independently-written latch call sites (the exact defect class the
kernel-engine/dry-run-processor equivalence test exists to catch on the JUDGEMENT side — see
``tests/nontrade/test_engine_processor_equivalence.py``), this module is the one implementation
both call sites use.

**Duck-typed ``inbox`` — no ``tos_runtime.engine`` import here.** This package's own structural
pin (``tests/nontrade/test_processor.py``'s
``test_no_forbidden_capacity_or_engine_imports_under_nontrade``) forbids importing
``tos_runtime.engine``/``.rcl``/``.recovery``/``.transport`` anywhere under
``tos_runtime/nontrade`` — satisfied here by typing ``inbox`` against the local
:class:`_RiskHaltPort` Protocol (the exact two methods this module calls), never the concrete
:class:`~tos_runtime.engine.inbox.SqliteEventInbox` (mirrors
:meth:`~tos_runtime.engine.driver.EngineDriver.bind_gateway`'s own "never imported by type here"
discipline for the send boundary it drains).

**Evidence-before-state-change** (mirrors :meth:`~tos_runtime.compose._types.ComposedRuntime
.clear_new_risk_halt`'s own discipline): the ``INCIDENT_CANDIDATE`` row is appended FIRST, every
restrictive call, so a crash between the two leaves a durable trace of the disposition that was
ABOUT to latch, never a bare halt row with no explanation reachable from it — and so a SECOND
restrictive call (a different event, after the latch is already held) still leaves its own
candidate trace even though ``record_new_risk_halt``'s first-call-wins singleton leaves the
underlying halt row untouched.

**Only sanctioned caller of ``record_new_risk_halt`` from the non-trade side.** Both
:mod:`tos_runtime.engine.driver` (the new engine path) and, previously,
:mod:`tos_runtime.compose._types` (now retired — that module routes through the engine instead)
call this function rather than the storage-layer method directly — mirrors
``tests/engine/test_no_direct_latch_clear.py``'s "one sanctioned door" idiom for the CLEAR side.
``tests/nontrade/test_latch.py`` pins the callers of ``record_new_risk_halt(`` under
``tos_runtime/src`` to this module, its own definition, and the pre-existing callers the survey
found (``tos_runtime.engine.orthostate_projection``, ``tos_runtime.safety.shutdown``) — never
widened silently.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.evidence.ports``
only. No ``tos_runtime.engine`` / ``.rcl`` / ``.recovery`` / ``.transport`` (this package's own
structural pin) — every caller-owned type is duck-typed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tos_runtime.evidence.ports import EvidenceAppendPort

__all__ = ["LatchOutcome", "latch_restrictive"]

#: This module's own evidence kind constant — never a kernel ``EvidenceKind`` (the kernel
#: authors no evidence at all; ADR-002-010 §10 line 217 "the event processor ... SHALL NOT
#: update capacity independently" applies to durable writes generally, not only capacity ones).
_INCIDENT_CANDIDATE_KIND = "INCIDENT_CANDIDATE"


class _RiskHaltPort(Protocol):
    """The exact two :class:`~tos_runtime.engine.inbox.SqliteEventInbox` methods this module
    calls — declared locally so this module never imports ``tos_runtime.engine`` (module
    docstring)."""

    def record_new_risk_halt(
        self, *, reason: str, event_id: str | None, evidence_seq: int | None
    ) -> None: ...

    def new_risk_halt(self) -> dict[str, object] | None: ...


@dataclass(frozen=True)
class LatchOutcome:
    """One :func:`latch_restrictive` call's result.

    Attributes:
        latched: ``True`` iff, after this call, the durable latch's own ``event_id`` equals THIS
            call's ``event_id`` — i.e. this specific call is the one currently in effect (only
            ever true for the very first restrictive call the runtime ever makes, since
            ``record_new_risk_halt`` is a first-call-wins singleton).
        first_call: ``True`` iff no halt existed before this call ran (this call was the first
            restrictive disposition this runtime has ever observed).
        incident_candidate_seq: The durable ``INCIDENT_CANDIDATE`` evidence row's own seq —
            appended unconditionally on every call, even when the halt itself was already
            latched by an earlier event (module docstring).
    """

    latched: bool
    first_call: bool
    incident_candidate_seq: int


def latch_restrictive(
    *,
    inbox: _RiskHaltPort,
    evidence_store: EvidenceAppendPort,
    disposition: str,
    latch_reason: str,
    event_id: str,
    evidence_seq: int | None,
    source: str,
) -> LatchOutcome:
    """Append an ``INCIDENT_CANDIDATE`` row, then latch a new-risk halt (first-call-wins).

    Args:
        inbox: The durable new-risk-halt latch port (module docstring — duck-typed).
        evidence_store: Where the ``INCIDENT_CANDIDATE`` row lands.
        disposition: The judged disposition's own vocabulary string (e.g. a kernel
            ``NonTradeDisposition.value`` or a dry-run processor's own), recorded verbatim.
        latch_reason: The reason string passed to ``record_new_risk_halt`` — the caller's own
            halt-reason vocabulary (e.g. :mod:`tos_runtime.engine.driver`'s own
            ``NONTRADE_<disposition>`` convention for the engine path).
        event_id: The event this disposition was judged for.
        evidence_seq: The evidence row the caller judged this disposition under (e.g. the
            engine's own ``EVENT_CONSUMED`` receipt seq), so an operator can cross-reference —
            ``None`` when the caller has none to offer.
        source: A free-text caller label (e.g. ``"engine"``) recorded on the
            ``INCIDENT_CANDIDATE`` row only — never read back by any predicate.

    Returns:
        :class:`LatchOutcome`.
    """
    before = inbox.new_risk_halt()
    receipt = evidence_store.append(
        {
            "event_id": event_id,
            "disposition": disposition,
            "latch_reason": latch_reason,
            "source": source,
            "referenced_evidence_seq": evidence_seq,
        },
        kind=_INCIDENT_CANDIDATE_KIND,
        record_class=_INCIDENT_CANDIDATE_KIND,
    )
    assert receipt.seq is not None  # a successful append never returns a None seq
    inbox.record_new_risk_halt(
        reason=latch_reason, event_id=event_id, evidence_seq=evidence_seq
    )
    after = inbox.new_risk_halt()
    first_call = before is None
    latched = after is not None and after.get("event_id") == event_id
    return LatchOutcome(
        latched=latched, first_call=first_call, incident_candidate_seq=receipt.seq
    )
