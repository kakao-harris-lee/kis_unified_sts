"""The RFC-003 §7 four-phase decision pipeline (design #31 §3.1) — accept, interpret, decide, emit.

Phase 1 ("accept context", §7:201-204) carries the safety weight: *a missing, stale, incomplete, or
invalid Capsule forbids a decision*. So the pipeline confirms — **positively** — that the Capsule is
issued, digest-bound, required-covered complete, and scoped to the event, and that the injected
:mod:`tos.time` verdicts admit; and only then is ``evaluate`` called at all. Each of those gates is
exercised here in isolation, and the "``evaluate`` was not called" half is asserted by the absence
of any emitted outcome, not merely by the halt reason.

Phase 3 ("decide", §7:208-212) has one slice-specific rule: a ``DecisionKind.VECTOR`` outcome
violates the per-instrument premise (RFC-003 §9:327-339) and is **fail-closed** — no progress,
restrictive no-action, recorded. The vector folding rule belongs to a later multi-symbol cycle
(design #31 §3.1 MINOR-1).

A hypothesis property closes the freshness gate over arbitrary injected coordinates: an absent
bound, an absent session context, or a non-``TRUSTED`` health state can never admit.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from tos.capsule.capsule import CapsuleScope, DecisionContextCapsule
from tos.dsl import PortfolioVector
from tos.engine import (
    EvidenceKind,
    HaltReason,
    TimeAdmissionInputs,
    capsule_admitted,
    time_admits,
)
from tos.time import HealthState, SessionContext, UncertaintyInterval

from ._engine_fixtures import (
    ACCOUNT,
    DECISION_CLASS,
    RecordingTransmit,
    admitting_time_inputs,
    build_core,
    capsule_gated_policy,
    decision_tick,
    instrument_key,
    issue_capsule,
    issue_strategy,
    registry_with,
    vector_policy,
)


def _tick_result(**kwargs):
    """Run one decision tick through a freshly wired core; return (result, sink, transmit)."""
    transmit = RecordingTransmit()
    core, sink = build_core(transmit=transmit, **kwargs.pop("core_kwargs", {}))
    return core.handle(decision_tick(**kwargs)), sink, transmit


# ---------------------------------------------------------------------------
# phase 1 — accept context (RFC-003 §7:201-204)
# ---------------------------------------------------------------------------


def test_a_draft_capsule_forbids_a_decision() -> None:
    """(§3.1 phase 1) A pre-issuance Capsule has no digest — evaluation is not attempted."""
    draft = DecisionContextCapsule(issuer_principal_id="iss-1")
    result, sink, transmit = _tick_result(sequence=1, capsule=draft)

    assert result.halt_reason is HaltReason.CAPSULE_NOT_ISSUED
    assert result.pipeline is not None and result.pipeline.outcome is None
    assert transmit.attempts == []
    withheld = [r for r in sink.records if r.kind is EvidenceKind.DECISION_WITHHELD]
    assert len(withheld) == 1
    assert withheld[0].outcome_digest is None, (
        "a withheld decision constructs no artifact bound to the Capsule it just rejected"
    )


def test_an_incomplete_capsule_forbids_a_decision() -> None:
    """(§3.1 phase 1) The ``_REQUIRED_COVERED`` completeness gate is checked positively.

    Defence in depth, and deliberately reached through ``model_construct``: an incomplete Capsule
    is already **unconstructable** as an ISSUED artifact (``tos.capsule`` verifies the digest and
    the required-covered set at construction), and the ``DecisionTickPayload`` model re-validates
    the nested Capsule, so this branch cannot be reached through ordinary construction. It is kept
    because "the outer model happens to revalidate" is not a guarantee the pipeline should rely on.
    """
    from tos.engine.records import DecisionTickPayload

    capsule = issue_capsule()
    incomplete = capsule.model_copy(update={"issuer_principal_id": None})
    payload = DecisionTickPayload.model_construct(
        instrument_key=instrument_key(),
        capsule=incomplete,
        time=admitting_time_inputs(),
    )
    halt, detail = capsule_admitted(payload)
    assert halt is HaltReason.CAPSULE_INCOMPLETE
    assert detail is not None and "issuer_principal_id" in detail


def test_a_tampered_capsule_cannot_even_enter_an_event() -> None:
    """(§3.1 phase 1) The digest binding is re-verified when the Capsule enters the payload."""
    from pydantic import ValidationError

    capsule = issue_capsule()
    tampered = capsule.model_copy(update={"issuer_principal_id": "someone-else"})
    with pytest.raises(ValidationError, match="canonical_digest does not match"):
        decision_tick(sequence=1, capsule=tampered)


def test_a_capsule_scoped_elsewhere_forbids_a_decision() -> None:
    """(§3.1 phase 1 / §3.3) The Capsule's own scope is the third leg of the agreement."""
    mismatched = issue_capsule(
        scope=CapsuleScope(
            environment="non-live-test",
            account="acct-other",
            instrument="ES",
            decision_class=DECISION_CLASS,
        )
    )
    result, _, transmit = _tick_result(sequence=1, capsule=mismatched)
    assert result.halt_reason is HaltReason.CAPSULE_SCOPE_MISMATCH
    assert transmit.attempts == []


@pytest.mark.parametrize(
    ("override", "label"),
    [
        ({"source_age": None}, "unknown source age"),
        ({"max_age_bound": None}, "no freshness threshold"),
        ({"delay_bounds": (None,)}, "unestablished delay bound"),
        ({"snapshot_age_bound": None}, "unknown snapshot age"),
        ({"maximum_consumer_age_ms": None}, "unestablished consumer max"),
        ({"session_context": None}, "no session context"),
        ({"uncertainty_interval": None}, "no uncertainty interval"),
        ({"health_state": None}, "no health state"),
        ({"health_state": HealthState.DEGRADED_HOLDOVER}, "degraded holdover"),
        ({"health_state": HealthState.UNTRUSTED}, "untrusted"),
    ],
)
def test_every_time_gate_denies_on_its_own(override, label) -> None:
    """(§2.3) Each injected time coordinate denies independently — absence is never permission."""
    admitted, reason = time_admits(admitting_time_inputs(**override))
    assert admitted is False, f"{label} must not admit"
    assert reason is not None


def test_a_session_that_is_not_positively_open_denies() -> None:
    """(§2.3; ADR-002-008 §12:319) A boundary inside the uncertainty window straddles — deny."""
    straddling = admitting_time_inputs(
        session_context=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase="CONTINUOUS",
            is_open=True,
            boundary_value=1,
        ),
        uncertainty_interval=UncertaintyInterval(lo=0, hi=2),
    )
    admitted, reason = time_admits(straddling)
    assert admitted is False
    assert reason is not None and "positively" in reason


def test_the_admitting_coordinates_really_admit() -> None:
    """The fixture is not vacuously failing — the positive path is exercised too."""
    admitted, reason = time_admits(admitting_time_inputs())
    assert admitted is True
    assert reason is None


def test_a_stale_snapshot_stops_the_tick() -> None:
    """(§2.3) The freshness gate runs before ``evaluate`` — nothing is emitted."""
    result, sink, transmit = _tick_result(
        sequence=1, time_inputs=admitting_time_inputs(max_age_bound=None)
    )
    assert result.halt_reason is HaltReason.TIME_NOT_ADMITTED
    assert result.pipeline is not None and result.pipeline.outcome is None
    assert transmit.attempts == []
    assert [r for r in sink.records if r.kind is EvidenceKind.DECISION_OUTCOME_EMITTED] == []


@settings(max_examples=50)
@given(
    source_age=st.one_of(st.none(), st.integers(min_value=-10_000, max_value=10_000)),
    max_age_bound=st.none(),
    health_state=st.sampled_from(list(HealthState)),
)
def test_an_unestablished_threshold_never_admits(source_age, max_age_bound, health_state) -> None:
    """(§2.3 property) With no freshness threshold, no combination of coordinates admits."""
    admitted, _ = time_admits(
        admitting_time_inputs(
            source_age=source_age, max_age_bound=max_age_bound, health_state=health_state
        )
    )
    assert admitted is False


@settings(max_examples=50)
@given(health_state=st.sampled_from([s for s in HealthState if s is not HealthState.TRUSTED]))
def test_only_a_trusted_health_state_admits(health_state) -> None:
    """(§2.3 property) Only ``TRUSTED`` permits new normal risk (ADR-002-008 §6.1-6.3)."""
    admitted, _ = time_admits(admitting_time_inputs(health_state=health_state))
    assert admitted is False


def test_an_empty_time_input_block_denies() -> None:
    """(§2.3) A default (all-absent) coordinate block is restrictive, not permissive."""
    admitted, reason = time_admits(TimeAdmissionInputs())
    assert admitted is False
    assert reason is not None


# ---------------------------------------------------------------------------
# phase 3 — decide (RFC-003 §7:208-212)
# ---------------------------------------------------------------------------


def test_a_vector_outcome_is_fail_closed() -> None:
    """(§3.1 MINOR-1) A ``VECTOR`` outcome violates the per-instrument premise — no progress."""
    core, sink = build_core(
        registry=registry_with(issue_strategy(vector_policy())), transmit=RecordingTransmit()
    )
    result = core.handle(decision_tick(sequence=1))

    assert result.halt_reason is HaltReason.VECTOR_OUTCOME_UNSUPPORTED
    assert result.flow is None
    assert result.pipeline is not None
    assert isinstance(result.pipeline.outcome, PortfolioVector)
    assert core.ledger.outstanding(instrument_key()) is None
    withheld = [r for r in sink.records if r.kind is EvidenceKind.DECISION_WITHHELD]
    assert len(withheld) == 1
    assert withheld[0].outcome_type == "PortfolioVector"


def test_a_no_action_outcome_starts_no_flow() -> None:
    """(§3.1 phase 4 / §7:217-220) Emission ends the pipeline; no-action begins no commitment."""
    core, sink = build_core(
        registry=registry_with(issue_strategy(capsule_gated_policy(fires=False))),
        transmit=RecordingTransmit(),
    )
    result = core.handle(decision_tick(sequence=1))

    assert result.halt_reason is HaltReason.NO_ACTION_OUTCOME
    assert result.flow is None
    assert result.pipeline is not None and result.pipeline.proposal is None
    assert core.ledger.outstanding(instrument_key()) is None


def test_a_firing_policy_emits_a_proposal_bound_to_the_exact_capsule() -> None:
    """(§3.1 phase 4) The outcome binds the consumed Capsule's identity + digest."""
    capsule = issue_capsule()
    result, _, _ = _tick_result(sequence=1, capsule=capsule)
    assert result.pipeline is not None
    proposal = result.pipeline.proposal
    assert proposal is not None
    assert proposal.decision_context_capsule.capsule_id == capsule.capsule_id
    assert proposal.decision_context_capsule.canonical_digest == capsule.canonical_digest
    assert proposal.account == ACCOUNT


def test_a_proposal_whose_scope_left_the_key_is_refused() -> None:
    """(§3.3 삼자 일치) The emitted proposal's own scope is cross-checked against the key.

    The registry key is derived from the strategy's declared scope, so agreement is normally
    structural. This asserts the *check exists* rather than relying on that: a proposal whose scope
    is not the dispatch key never reaches the sequencer.
    """
    from tos.engine.pipeline import run_decision_pipeline
    from tos.engine.records import DecisionTickPayload
    from tos.engine.sink import RecordingEvidenceSink

    from ._engine_fixtures import SCHEME, authored_config, engine_configuration

    registry = registry_with(issue_strategy(capsule_gated_policy(instrument="NQ")))
    entry = registry.declared_keys()[0]
    registered = registry.resolve(entry).entries[0]

    # The capsule + event agree with each other but not with the registered strategy's key.
    payload = DecisionTickPayload(
        instrument_key=instrument_key(),
        capsule=issue_capsule(),
        time=admitting_time_inputs(),
    )
    result = run_decision_pipeline(
        entry=registered,
        payload=payload,
        configuration=engine_configuration(),
        scheme=SCHEME,
        sink=RecordingEvidenceSink(),
    )
    assert result.halt_reason is HaltReason.EVENT_STRATEGY_KEY_MISMATCH
    assert result.proposal is None
    assert authored_config().config_version == "cfg-0"
