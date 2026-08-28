"""consumption_transition — single-use consumption state machine (design #15 §6.2; IAP-EV-005 substrate, predicate-only).

The state-machine property (§12 line 306-314): registration -> consumption -> spent.
ELIGIBLE + current APPROVE + equivalent envelope => CONSUMED + one record; a duplicate identical
command => same record (idempotent); a conflicting command => reject; a distinct second
consumption => reject (single-use, at most one Intent). No revival path (a CONSUMED decision never
returns to ELIGIBLE). Uses classify_record_pair REUSE for the duplicate-vs-conflict distinction.

Regime tag: predicate / model substrate only; IAP-EV-005 NOT_IMPLEMENTED (real linearizable
serialization / writer-fence is +Security runtime, §12 line 316); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.iap import (
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    consumption_transition,
)

from ._iap_strategies import TRIBOOL


def _consume(**overrides: object) -> tuple[ConsumptionStatus, ConsumptionOutcome]:
    base: dict[str, object] = {
        "current_status": ConsumptionStatus.ELIGIBLE,
        "decision_result": ApprovalResult.APPROVE,
        "decision_current": True,
        "approved_intent_envelope_equivalent": True,
        "command_identity": "cmd-1",
        "command_digest": "cmd-digest-1",
    }
    base.update(overrides)
    return consumption_transition(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# registration -> consumption (ELIGIBLE branch)
# ---------------------------------------------------------------------------


def test_first_consumption_consumes() -> None:
    """(§12 line 306-309, positive side) ELIGIBLE + current APPROVE + equivalent envelope => CONSUMED_NEW."""
    status, outcome = _consume()
    assert status is ConsumptionStatus.CONSUMED
    assert outcome is ConsumptionOutcome.CONSUMED_NEW


def test_non_approve_decision_does_not_consume() -> None:
    """(fail-closed) A non-APPROVE decision is not consumable — stays ELIGIBLE, REJECTED_INELIGIBLE."""
    for result in (ApprovalResult.DENY, ApprovalResult.UNKNOWN):
        status, outcome = _consume(decision_result=result)
        assert status is ConsumptionStatus.ELIGIBLE
        assert outcome is ConsumptionOutcome.REJECTED_INELIGIBLE


def test_stale_or_nonequivalent_does_not_consume() -> None:
    """(§12 line 307-309) A non-current decision / non-equivalent envelope does not consume (fail-closed)."""
    for kwargs in (
        {"decision_current": False},
        {"decision_current": None},
        {"approved_intent_envelope_equivalent": False},
        {"approved_intent_envelope_equivalent": None},
    ):
        status, outcome = _consume(**kwargs)
        assert status is ConsumptionStatus.ELIGIBLE
        assert outcome is ConsumptionOutcome.REJECTED_INELIGIBLE


# ---------------------------------------------------------------------------
# consumption -> spent (CONSUMED branch): duplicate / conflict / reuse
# ---------------------------------------------------------------------------


def test_duplicate_identical_is_idempotent_same_record() -> None:
    """(§12 line 313) A duplicate identical command against CONSUMED => IDEMPOTENT_REPLAY (same record)."""
    status, outcome = _consume(
        current_status=ConsumptionStatus.CONSUMED,
        command_identity="cmd-1",
        command_digest="cmd-digest-1",
        prior_command_identity="cmd-1",
        prior_command_digest="cmd-digest-1",
    )
    assert status is ConsumptionStatus.CONSUMED
    assert outcome is ConsumptionOutcome.IDEMPOTENT_REPLAY


def test_conflicting_command_is_rejected() -> None:
    """(§12 line 313) A same-id / different-bytes command against CONSUMED => REJECTED_CONFLICT."""
    status, outcome = _consume(
        current_status=ConsumptionStatus.CONSUMED,
        command_identity="cmd-1",
        command_digest="DIFFERENT-BYTES",
        prior_command_identity="cmd-1",
        prior_command_digest="cmd-digest-1",
    )
    assert status is ConsumptionStatus.CONSUMED
    assert outcome is ConsumptionOutcome.REJECTED_CONFLICT


def test_distinct_reuse_is_rejected() -> None:
    """(§12 / IAP-INV-006 line 154) A distinct second consumption => REJECTED_REUSE (single-use)."""
    status, outcome = _consume(
        current_status=ConsumptionStatus.CONSUMED,
        command_identity="cmd-2",
        command_digest="cmd-digest-2",
        prior_command_identity="cmd-1",
        prior_command_digest="cmd-digest-1",
    )
    assert status is ConsumptionStatus.CONSUMED
    assert outcome is ConsumptionOutcome.REJECTED_REUSE


def test_reuse_with_missing_digest_fails_closed_to_reject() -> None:
    """(fail-closed) An unprovable pair (missing digest) against CONSUMED => REJECTED_REUSE, never replay."""
    status, outcome = _consume(
        current_status=ConsumptionStatus.CONSUMED,
        command_identity="cmd-1",
        command_digest=None,
        prior_command_identity="cmd-1",
        prior_command_digest="cmd-digest-1",
    )
    assert status is ConsumptionStatus.CONSUMED
    assert outcome is ConsumptionOutcome.REJECTED_REUSE


# ---------------------------------------------------------------------------
# state-machine properties (§12) — at most one consumption, no revival
# ---------------------------------------------------------------------------


@given(
    decision_result=st.sampled_from(list(ApprovalResult)),
    decision_current=TRIBOOL,
    envelope_equivalent=TRIBOOL,
)
def test_consumed_never_reverts_to_eligible(
    decision_result: ApprovalResult,
    decision_current: bool | None,
    envelope_equivalent: bool | None,
) -> None:
    """(§20 no-revival) A CONSUMED decision NEVER transitions back to ELIGIBLE, whatever the inputs."""
    status, _ = _consume(
        current_status=ConsumptionStatus.CONSUMED,
        decision_result=decision_result,
        decision_current=decision_current,
        approved_intent_envelope_equivalent=envelope_equivalent,
        prior_command_identity="cmd-1",
        prior_command_digest="cmd-digest-1",
    )
    assert status is ConsumptionStatus.CONSUMED


@given(
    decision_result=st.sampled_from(list(ApprovalResult)),
    decision_current=TRIBOOL,
    envelope_equivalent=TRIBOOL,
)
def test_only_admissible_first_consumption_creates_new(
    decision_result: ApprovalResult,
    decision_current: bool | None,
    envelope_equivalent: bool | None,
) -> None:
    """(§12 line 306-309 property) CONSUMED_NEW iff (APPROVE + current + equivalent) — else stays ELIGIBLE."""
    status, outcome = _consume(
        decision_result=decision_result,
        decision_current=decision_current,
        approved_intent_envelope_equivalent=envelope_equivalent,
    )
    admissible = (
        decision_result is ApprovalResult.APPROVE
        and decision_current is True
        and envelope_equivalent is True
    )
    if admissible:
        assert (status, outcome) == (
            ConsumptionStatus.CONSUMED,
            ConsumptionOutcome.CONSUMED_NEW,
        )
    else:
        assert (status, outcome) == (
            ConsumptionStatus.ELIGIBLE,
            ConsumptionOutcome.REJECTED_INELIGIBLE,
        )


def test_second_consumption_creates_no_new_intent() -> None:
    """(§12 / IAP-INV-006) After a first CONSUMED_NEW, no further command yields another CONSUMED_NEW."""
    status, outcome = _consume()
    assert outcome is ConsumptionOutcome.CONSUMED_NEW
    # Any subsequent attempt (identical, conflicting, or distinct) is never a fresh CONSUMED_NEW.
    for cmd_id, cmd_digest in (
        ("cmd-1", "cmd-digest-1"),  # identical -> replay
        ("cmd-1", "OTHER"),  # conflict
        ("cmd-9", "cmd-digest-9"),  # distinct reuse
    ):
        _, next_outcome = _consume(
            current_status=status,
            command_identity=cmd_id,
            command_digest=cmd_digest,
            prior_command_identity="cmd-1",
            prior_command_digest="cmd-digest-1",
        )
        assert next_outcome is not ConsumptionOutcome.CONSUMED_NEW
