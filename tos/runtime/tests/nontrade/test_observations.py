"""Tests for :mod:`tos_runtime.nontrade.observations` (Phase 5 W5 plan §2 decision
6, lane f3) — :meth:`~tos_runtime.nontrade.observations.NonTradeObservation
.to_kernel_record` honesty: every carried field is copied verbatim, every
uncarried field stays at the kernel model's own default, the record is
``DRAFT``, and ``workflow_state`` is ``OBSERVED``.
"""

from __future__ import annotations

from decimal import Decimal

from tos.canonical import ArtifactStatus
from tos.nontrade import (
    NonTradeEventClass,
    NonTradeEventWorkflowState,
    SplitTransformationKind,
    SplitTransformationSpec,
)
from tos_runtime.nontrade import NonTradeObservation


def test_to_kernel_record_is_observed_and_draft() -> None:
    obs = NonTradeObservation(
        observation_id="obs-1",
        event_class=NonTradeEventClass.LIFECYCLE,
        source_label="synthetic-fixture",
    )
    record = obs.to_kernel_record()
    assert record.workflow_state is NonTradeEventWorkflowState.OBSERVED
    assert record.status is ArtifactStatus.DRAFT
    assert record.canonical_digest is None


def test_to_kernel_record_copies_identity_and_times_verbatim() -> None:
    obs = NonTradeObservation(
        observation_id="obs-2",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_label="synthetic-fixture",
        event_subtype="CASH_DIVIDEND",
        announcement_time="t0",
        observation_time="t1",
        record_time="t2",
        ex_time="t3",
        effective_time="t4",
        payable_time="t5",
        settlement_time="t6",
        workflow_generation=3,
        idempotency_key="idem-1",
        supersedes_ref="prior-event",
    )
    record = obs.to_kernel_record()
    assert record.event_id == "obs-2"
    assert record.event_class is NonTradeEventClass.CORPORATE_ACTION
    assert record.event_subtype == "CASH_DIVIDEND"
    assert record.source_identities == ("synthetic-fixture",)
    assert record.source_event_ids == ("obs-2",)
    # the seven times stay seven separate fields (§8 line 171 no-collapse)
    assert (
        record.announcement_time,
        record.observation_time,
        record.record_time,
        record.ex_time,
        record.effective_time,
        record.payable_time,
        record.settlement_time,
    ) == ("t0", "t1", "t2", "t3", "t4", "t5", "t6")
    assert record.workflow_generation == 3
    assert record.idempotency_key == "idem-1"
    assert record.supersedes_ref == "prior-event"


def test_to_kernel_record_copies_route_identity_and_transformation() -> None:
    split = SplitTransformationSpec(
        kind=SplitTransformationKind.FORWARD_SPLIT,
        pre_quantity=Decimal("1"),
        post_quantity=Decimal("2"),
        pre_basis=Decimal("2"),
        post_basis=Decimal("1"),
        unit_spec="shares",
        rounding_rule="round-down",
        fractional_residual=Decimal("0"),
        cash_in_lieu=Decimal("0"),
    )
    obs = NonTradeObservation(
        observation_id="obs-3",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_label="synthetic-fixture",
        old_instrument_identity="OLD",
        new_instrument_identity="NEW",
        split_spec=split,
    )
    record = obs.to_kernel_record()
    assert record.old_instrument_identity == "OLD"
    assert record.new_instrument_identity == "NEW"
    assert record.transformation_spec is split
    assert record.transition_envelope is None


def test_to_kernel_record_leaves_uncarried_fields_at_kernel_default() -> None:
    """A field this observation was never given (e.g. broker-treatment profile,
    the profile/calendar/instrument-master versions, the orthogonal axes) stays
    at the kernel record's own default — never a fabricated value (module
    docstring M6 discipline)."""
    obs = NonTradeObservation(
        observation_id="obs-4",
        event_class=NonTradeEventClass.ADMINISTRATIVE_BROKER,
        source_label="synthetic-fixture",
    )
    record = obs.to_kernel_record()
    assert record.broker_treatment_profile is None
    assert record.expected_open_order_behavior is None
    assert record.per_field_confidence == {}
    assert record.safety_profile_version is None
    assert record.broker_capability_profile_version is None
    assert record.verification_profile_version is None
    assert record.calendar_version is None
    assert record.instrument_master_version is None
    assert record.order_state is None
    assert record.exposure_state is None
    assert record.capacity_state is None
    assert record.authority_state is None
    assert record.evidence_confidence_state is None
    assert record.affected_account_scopes == ()
    assert record.eligibility_conditions == ()


def test_to_kernel_record_authority_effect_is_all_false_default() -> None:
    obs = NonTradeObservation(
        observation_id="obs-5",
        event_class=NonTradeEventClass.UNRECOGNIZED_EXTERNAL,
        source_label="synthetic-fixture",
    )
    record = obs.to_kernel_record()
    effect = record.authority_effect
    assert all(getattr(effect, name) is False for name in type(effect).model_fields)
