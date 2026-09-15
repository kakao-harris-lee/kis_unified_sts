"""``tos_runtime.compose._cli_ops`` — the SECOND sanctioned door onto the storage-layer
new-risk-halt clear, for the operator CLI (team-lead directive, runtime operations
wiring plan (2026-09-13) follow-up).

**Why a second door, not just "wait for a live runtime."** :meth:`~tos_runtime.compose
._types.ComposedRuntime.clear_new_risk_halt` (``compose/_types.py:365-455``) is THE
sanctioned door when a live, fully-composed :class:`~tos_runtime.compose._types
.ComposedRuntime` exists — but ``compose/cli.py``'s own module docstring names the
canonical blocker list for why no such runtime is ever reachable from the CLI today
(``run`` is parse-only: ``ConstructionConfig`` and the two risk-input providers have no
production source). An operator running ``rearm`` from the CLI therefore has no live
runtime to hand a clear request to at all — "wire it through a live compose call" is not
a path that exists. :func:`rearm_and_clear` is that second door: it goes through the
IDENTICAL HAG two-person quorum evaluation
(:func:`~tos_runtime.safety.rearm.prepare_new_risk_halt_clear`) the live-runtime door
uses, and clears the storage-layer latch itself ONLY on an ``APPROVED`` outcome — never
bypassing the quorum gate the machine pin
(``tests/engine/test_no_direct_latch_clear.py``) exists to protect.

**The post-approval sequence is DUPLICATED here, not imported (compose/_types.py is a
different lane's own file).** It mirrors ``ComposedRuntime.clear_new_risk_halt``'s own
body (``compose/_types.py:430-453``) exactly:

1. Append ``NEW_RISK_HALT_CLEARED_BY_OPERATOR`` evidence — BEFORE the storage clear
   (``compose/_types.py:430-439``).
2. Call :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt` with the
   SAME ``latched_evidence_seq`` and the workflow's own non-secret attestation marker
   text (``compose/_types.py:440-443``).
3. On any non-``CLEARED`` storage outcome (the disclosed storage-layer TOCTOU window —
   a concurrent relatch changing the seq between the pre-check and the clear),
   append ``NEW_RISK_HALT_CLEAR_REFUSED`` evidence (``compose/_types.py:444-453``).

The evidence-kind string constants below are duplicated from ``compose/_types.py``'s own
private ``ComposedRuntime._NEW_RISK_HALT_CLEARED_KIND`` /
``_NEW_RISK_HALT_CLEAR_REFUSED_KIND`` (module-private there, not exported, and that file
is a different lane's own file — the same "duplicate the literal, do not reach across a
file another lane owns" discipline ``compose/cli.py`` already applies elsewhere) — kept
IDENTICAL so a durable reader (an operator grep, a future dashboard) sees the same kind
regardless of which door cleared a given halt.

**Machine pin.** ``tests/engine/test_no_direct_latch_clear.py`` allows exactly TWO files
to call ``SqliteEventInbox.clear_new_risk_halt(`` directly: ``compose/_types.py`` (the
live-runtime door) and THIS file (the CLI-only door) — both go through the SAME HAG
quorum gate via :func:`~tos_runtime.safety.rearm.prepare_new_risk_halt_clear`; neither
bypasses it. A separate AST-level pin in ``tests/compose/test_cli.py`` proves this
module contains exactly one such call site, reachable only past a guard clause that
already returned on any non-``APPROVED`` :func:`~tos_runtime.safety.rearm
.prepare_new_risk_halt_clear` outcome.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``hashlib``) +
``tos_runtime.engine.inbox`` + ``tos_runtime.evidence.store`` +
``tos_runtime.safety.rearm`` + ``tos_runtime.time.service`` only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tos_runtime.engine.inbox import NewRiskHaltClearOutcome, SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.safety.rearm import prepare_new_risk_halt_clear
from tos_runtime.time.service import TrustworthyTimeService

__all__ = ["RearmCliOutcome", "rearm_and_clear"]

#: Duplicated from :mod:`tos_runtime.compose._types`'s own private
#: ``ComposedRuntime._NEW_RISK_HALT_CLEARED_KIND`` (module docstring — not exported, and
#: that file is a different lane's own file).
_NEW_RISK_HALT_CLEARED_KIND = "NEW_RISK_HALT_CLEARED_BY_OPERATOR"
#: Duplicated from :mod:`tos_runtime.compose._types`'s own private
#: ``ComposedRuntime._NEW_RISK_HALT_CLEAR_REFUSED_KIND`` (module docstring).
_NEW_RISK_HALT_CLEAR_REFUSED_KIND = "NEW_RISK_HALT_CLEAR_REFUSED"


@dataclass(frozen=True)
class RearmCliOutcome:
    """The result of one :func:`rearm_and_clear` call.

    Attributes:
        cleared: ``True`` only when the storage-layer latch was actually cleared by
            THIS call.
        outcome: The underlying :class:`~tos_runtime.engine.inbox.NewRiskHaltClearOutcome`
            once the storage clear was attempted (``CLEARED`` or ``STORAGE_REFUSED``), or
            ``None`` when refused before ever reaching that call (``NO_LATCH`` /
            ``SEQ_MISMATCH`` / ``QUORUM_REFUSED`` — the HAG quorum pre-checks/evaluation
            own these three; see :func:`~tos_runtime.safety.rearm
            .prepare_new_risk_halt_clear`'s own ``NewRiskHaltDoorDecision.refusal``).
        reason: A short, non-secret, human-readable disclosure of what happened — never
            file content, never a principal's raw identity beyond what the operator's own
            approval file already named.
    """

    cleared: bool
    outcome: NewRiskHaltClearOutcome | None
    reason: str


def rearm_and_clear(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    approvals_dir: Path,
    environment_label: str,
    expected_owner_uid: int,
    latched_evidence_seq: int,
) -> RearmCliOutcome:
    """Evaluate the HAG two-person re-arm quorum for ``latched_evidence_seq`` and, only on
    an ``APPROVED`` outcome, clear the storage-layer latch (module docstring).

    Args:
        inbox: The runtime's event inbox — read for the current latch, and the ONLY
            other caller (besides ``compose/_types.py``) permitted to call its
            :meth:`~tos_runtime.engine.inbox.SqliteEventInbox.clear_new_risk_halt`
            directly (machine pin).
        evidence_store: Where the HAG workflow's own ``REARM_APPROVED``/``REARM_REFUSED``
            evidence lands (via :func:`~tos_runtime.safety.rearm
            .prepare_new_risk_halt_clear`), and where this function's own
            ``NEW_RISK_HALT_CLEARED_BY_OPERATOR``/``NEW_RISK_HALT_CLEAR_REFUSED`` rows
            land.
        time_service: Carried through to :class:`~tos_runtime.safety.rearm.ReArmWorkflow`
            for interface symmetry only — that class never actually consults it (its own
            docstring: hag reads no clock).
        approvals_dir: The directory ``rearm/<latched_evidence_seq>.yaml`` (decision) and
            ``rearm/roster.yaml`` are resolved under.
        environment_label: This runtime's own boot-argument environment label; the
            approval/roster files' own labels must match byte-exact.
        expected_owner_uid: The uid both the approval/roster files' owner and the calling
            process itself are expected to be (file-custody's 0600 rule).
        latched_evidence_seq: The ``evidence_seq`` of the currently-latched violation the
            operator reviewed. Must equal the CURRENTLY-latched row's own seq — a stale
            value is refused.

    Returns:
        The :class:`RearmCliOutcome`.
    """
    current = inbox.new_risk_halt()
    decision = prepare_new_risk_halt_clear(
        current=current,
        latched_evidence_seq=latched_evidence_seq,
        approvals_dir=approvals_dir,
        evidence_store=evidence_store,
        inbox=inbox,
        time_service=time_service,
        environment_label=environment_label,
        expected_owner_uid=expected_owner_uid,
        refused_kind=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
    )
    if decision.refusal is not None:
        return RearmCliOutcome(
            cleared=False, outcome=None, reason=f"refused: {decision.refusal.value}"
        )

    # decision.refusal is None only past the NO_LATCH/SEQ_MISMATCH pre-checks AND a
    # satisfied HAG quorum (prepare_new_risk_halt_clear's own contract) — current and
    # attestation_text are therefore both guaranteed non-None here.
    assert current is not None
    attestation_text = decision.attestation_text
    assert attestation_text is not None
    attestation_sha256 = hashlib.sha256(attestation_text.encode("utf-8")).hexdigest()

    evidence_store.append(
        {
            "latched_evidence_seq": latched_evidence_seq,
            "latched_reason": current.get("reason"),
            "latched_event_id": current.get("event_id"),
            "operator_attestation_sha256": attestation_sha256,
        },
        kind=_NEW_RISK_HALT_CLEARED_KIND,
        record_class=_NEW_RISK_HALT_CLEARED_KIND,
    )
    storage_outcome = inbox.clear_new_risk_halt(
        latched_evidence_seq=latched_evidence_seq,
        operator_attestation=attestation_text,
    )
    if storage_outcome is not NewRiskHaltClearOutcome.CLEARED:
        evidence_store.append(
            {
                "outcome": NewRiskHaltClearOutcome.STORAGE_REFUSED.value,
                "requested_evidence_seq": latched_evidence_seq,
                "current_latched_evidence_seq": current.get("evidence_seq"),
            },
            kind=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
            record_class=_NEW_RISK_HALT_CLEAR_REFUSED_KIND,
        )
        return RearmCliOutcome(
            cleared=False,
            outcome=NewRiskHaltClearOutcome.STORAGE_REFUSED,
            reason="refused: STORAGE_REFUSED (concurrent relatch TOCTOU window)",
        )
    return RearmCliOutcome(
        cleared=True, outcome=NewRiskHaltClearOutcome.CLEARED, reason="cleared"
    )
