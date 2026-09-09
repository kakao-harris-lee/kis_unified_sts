"""``RecordedTransmit`` — a side-effect-free ``Transmit`` stand-in for boot-time replay
(TOS Phase 3, dispatch CR5, 2026-09-09).

**The bug this fixes.** Kernel lane KW3-RD (``783fadf0``) gave ``EGRESS_RESULT`` events a real,
non-``None`` ``outcome_digest`` (derived from disposition/capacity/knowledge/quantities — see
:mod:`tos.engine.records`'s ``EgressResultOutcome``), which finally made the replay comparison for
result events non-vacuous. That exposed a genuine replay-fidelity gap: replay has always composed
its core with ``transmit=None`` (:mod:`tos_runtime.engine.replay`'s own hermetic test suite, and
this module's own callers). ``tos.engine.sequencer.run_commitment_flow`` treats a ``None``
transmit as an unconditional stop — ``HaltReason.TRANSMIT_UNAVAILABLE`` — reached BEFORE
``ledger.mark_potentially_live`` ever runs (``sequencer.py:519-546``). The LIVE run, with a real
(or fake) transmit injected, advances the reservation projection to ``POTENTIALLY_LIVE`` before
ever calling it. Replaying the identical ``EGRESS_RESULT`` against the two different prior
projections (``ATTEMPT_BOUND`` on replay vs. ``POTENTIALLY_LIVE`` live) computes a genuinely
different ``EgressResultOutcome`` — and therefore a genuinely different digest — for the exact
same event, byte for byte.

**What this class does NOT do.** It never calls a real transport, never constructs a new attempt,
never calls ``tos.brokeradapter``'s ``send_once`` or any network/synthetic transport
implementation, and it never re-derives an outcome from first principles. It answers exactly one
question — "does the DURABLE EVIDENCE this runtime already recorded show that THIS EXACT
``attempt_id`` was handed off to the send boundary?" — by reading the same
``EvidenceKind.SEND_HANDED_OFF`` record (``tos.engine.sequencer.run_commitment_flow``'s own
``sink.record(...)`` call, durably persisted by :class:`~tos_runtime.evidence.sinks
.EngineEvidenceSinkAdapter` under the kind string ``"SEND_HANDED_OFF"``) that the LIVE run itself
already wrote. If that evidence exists for the attempt being replayed, it returns a
:class:`~tos.engine.records.SendHandoff` — reproducing "hand-off happened" so
``ledger.mark_potentially_live`` (already invoked by the sequencer, unconditionally, the instant
``transmit is not None`` — see the module-level note below) leaves the SAME reservation state the
live run left. If NO such evidence exists for this attempt, it refuses to guess: it raises
:class:`ReplayTransmitEvidenceMissing` (fail-closed, per the CR5 dispatch's own instruction —
never silently assume a hand-off the evidence does not corroborate).

**Measured, not assumed: raising vs. returning normally are EQUIVALENT for the ledger state a
later ``EGRESS_RESULT`` reads (2026-09-09).** ``run_commitment_flow`` calls
``ledger.mark_potentially_live(instrument_key)`` BEFORE the ``try``/``except`` around
``transmit(attempt)`` — so once ``transmit`` is non-``None`` at all, the reservation reaches
``POTENTIALLY_LIVE`` whether the call subsequently succeeds OR raises (``HaltReason
.TRANSMIT_RAISED``); a direct probe against the real driver confirms both paths leave the
identical ``(capacity_state=POTENTIALLY_LIVE, knowledge=SENT_UNCONFIRMED)`` reservation. This
means the ONLY lever that changes the ledger-relevant outcome is whether a caller installs a
non-``None`` transmit AT ALL for the whole replay run — a decision this class cannot make for
itself (it is invoked per-attempt, strictly AFTER the sequencer's own ``transmit is None`` check
already ran) — see :func:`any_recorded_hand_off` for the run-wide signal a caller uses to decide
between installing this stand-in and leaving ``transmit=None`` (matching a recorded run that
never configured a send boundary either). The per-attempt evidence check this class performs is
therefore NOT what protects the ledger-state fidelity this fix targets; it is a SEPARATE,
independently-valuable fail-closed guard against a different failure mode — an attempt whose
content-addressed identity does not match anything the live run ever actually sent (a genuine
anomaly worth a hard failure, not a silently-fabricated success).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``json``) + ``tos.engine``
+ ``tos_runtime.evidence.store`` only. No ``shared.*``, no transport, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from tos.engine.records import AttemptRequest, SendHandoff

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "ReplayTransmitEvidenceMissing",
    "RecordedTransmit",
    "any_recorded_hand_off",
]

#: The kernel evidence kind ``tos.engine.sequencer.run_commitment_flow`` records via
#: ``EvidenceKind.SEND_HANDED_OFF`` — durably persisted under this exact string
#: (``EngineEvidenceSinkAdapter.record`` stores ``record.kind.value``).
_SEND_HANDED_OFF_KIND = "SEND_HANDED_OFF"


class ReplayTransmitEvidenceMissing(RuntimeError):
    """Raised by :class:`RecordedTransmit` when no ``SEND_HANDED_OFF`` evidence exists for the
    attempt being replayed.

    Caught by ``tos.engine.sequencer.run_commitment_flow``'s own ``except Exception`` around the
    ``transmit(attempt)`` call — surfaces as an ordinary ``HaltReason.TRANSMIT_RAISED``, exactly
    as any other transmit failure would (this class constructs no special kernel-side handling;
    the kernel firewall forbids ``tos_runtime`` from reaching back into kernel control flow
    beyond the ``Transmit`` Protocol's own single call/return/raise contract).
    """


def _attempt_was_handed_off(
    evidence_store: SqliteEvidenceStore, attempt_id: str
) -> bool:
    """Whether a ``SEND_HANDED_OFF`` evidence record names exactly ``attempt_id``."""
    cur = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ?", (_SEND_HANDED_OFF_KIND,)
    )
    for (payload_json,) in cur:
        payload = json.loads(payload_json).get("payload", {})
        if payload.get("attempt_id") == attempt_id:
            return True
    return False


def any_recorded_hand_off(evidence_store: SqliteEvidenceStore) -> bool:
    """Whether ANY attempt in this evidence store's history was ever handed off.

    The run-wide signal a caller (a test's own ``build_core`` factory, or a future compose-level
    replay wiring) uses to decide whether to install :class:`RecordedTransmit` at all, versus
    leaving ``transmit=None`` — matching a recorded run whose own core never had a send boundary
    configured either (module docstring's "measured, not assumed" note: per-attempt fidelity
    cannot substitute for this run-wide choice, since ``ledger.mark_potentially_live`` fires the
    instant ``transmit`` is non-``None`` at all, regardless of what is later returned or raised).
    """
    cur = evidence_store.connection.execute(
        "SELECT 1 FROM entries WHERE kind = ? LIMIT 1", (_SEND_HANDED_OFF_KIND,)
    )
    return cur.fetchone() is not None


@dataclass
class RecordedTransmit:
    """A ``Transmit`` (``tos.engine.sequencer.Transmit`` Protocol) stand-in that reproduces the
    LOCAL send-boundary effect the live run's own durable evidence already recorded — never a
    real transport call (module docstring).

    Attributes:
        evidence_store: The durable evidence store the LIVE run wrote
            ``EvidenceKind.SEND_HANDED_OFF`` records into — read-only from this class's own
            perspective (it never appends to it; see :class:`ReplayTransmitEvidenceMissing` for
            why a missing-evidence case is a raised exception, not a durable write from here).
    """

    evidence_store: SqliteEvidenceStore

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Reproduce the recorded hand-off for ``attempt``, or refuse (fail-closed).

        Returns:
            A :class:`~tos.engine.records.SendHandoff` with ``accepted_for_transmission=True``
            when ``SEND_HANDED_OFF`` evidence names this exact ``attempt.attempt_id`` — the
            handoff's own field values are never compared by anything downstream (module
            docstring: ``EventResult.outcome_digest`` is the decision pipeline's own digest,
            fixed before the commitment flow ever runs), so no further fidelity is claimed here
            beyond "a hand-off, not a refusal, is what happened".

        Raises:
            ReplayTransmitEvidenceMissing: If no such evidence exists for this attempt.
        """
        if not _attempt_was_handed_off(self.evidence_store, attempt.attempt_id):
            raise ReplayTransmitEvidenceMissing(
                f"no SEND_HANDED_OFF evidence recorded for attempt {attempt.attempt_id!r} — "
                "replay refuses to guess a hand-off the live run's own evidence does not "
                "corroborate (fail-closed, CR5 dispatch 2026-09-09)"
            )
        return SendHandoff(
            accepted_for_transmission=True, handoff_reference=attempt.attempt_id
        )
