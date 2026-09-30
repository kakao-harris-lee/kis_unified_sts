"""``NonTradeObservation`` — a runtime-observed non-trade event, prior to any kernel
decision (Phase 5 W5 plan §2 decision 6, lane f3).

This is a **runtime record, not a kernel type**: :mod:`tos.nontrade` authors zero
runtime consumer (survey ``w5-survey-kernel.md`` §3 "런타임 소비자 0"), so this
module is the first place a non-trade event is represented outside a test file.
It carries exactly the raw facts a caller (a synthetic fixture today; a future
corporate-action / broker-administrative feed later) can observe, plus the
sibling-owned coordinates (venue admissibility, recon field confidence, are risk,
rcl capacity-known, time freshness/window) the kernel's
:func:`~tos.nontrade.predicates.nontrade_disposition` needs as **injected**
arguments (design #21 §0.2 — nontrade re-authors none of them). A field this
observation was never given stays ``None`` (or, for the two frozenset fields,
empty) — never a fabricated constant (project lesson
``tos-phase4-scopes-round-2026-09-09`` M6: "a constant fed where a real fact
belongs silences the predicate it is fed to").

:meth:`NonTradeObservation.to_kernel_record` builds the kernel's
:class:`~tos.nontrade.records.NonTradeEventRecord` **honestly**: every kernel
field this observation carries is copied verbatim (spec terms = code terms), and
every field it does not carry is left at the kernel model's own ``None``/``()``
default. The record is left at its default ``DRAFT``
:class:`~tos.canonical.ArtifactStatus` (no digest is computed and no
issuance-time required-field check runs — this observation is not a durable
ledger citizen, only an input the processor folds through kernel predicates that
read fields directly) with ``workflow_state`` set to
:attr:`~tos.nontrade.vocabulary.NonTradeEventWorkflowState.OBSERVED`, the state a
freshly-observed event is in before any corroboration (ADR-002-010 §6 line 127).

Pure module: stdlib + ``tos.nontrade`` (+ ``tos.canonical`` for ``CanonicalDecimal``
via the kernel's own record fields) only. No ``shared.*``, no sibling
``tos_runtime.rcl`` / ``.engine`` / ``.recovery`` / ``.transport`` import (this
package's structural pin, ``tests/nontrade/test_no_write_port.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tos.nontrade import (
    CorrectionReversalRecord,
    NonTradeEventClass,
    NonTradeEventRecord,
    NonTradeEventWorkflowState,
    SplitTransformationSpec,
    TransitionEnvelope,
)

__all__ = ["NonTradeObservation"]


@dataclass(frozen=True)
class NonTradeObservation:
    """One observed non-trade event, before any kernel predicate has run.

    Field groups mirror the kernel record's own §5 item numbering (see
    :data:`tos.nontrade.vocabulary.EVENT_IDENTITY_FIELD_GROUPS`) plus the
    sibling-injected coordinates :func:`~tos.nontrade.predicates.nontrade_disposition`
    and its supporting predicates need. Nothing here is a kernel type except the
    three nested kernel value/record models this observation is allowed to carry
    directly (:class:`~tos.nontrade.records.TransitionEnvelope`,
    :class:`~tos.nontrade.records.SplitTransformationSpec`,
    :class:`~tos.nontrade.records.CorrectionReversalRecord`).
    """

    # -- identity (§5 items 1 / 3 / 12) --------------------------------------
    observation_id: str
    event_class: NonTradeEventClass
    source_label: str
    event_subtype: str | None = None
    workflow_generation: int | None = None
    idempotency_key: str | None = None
    supersedes_ref: str | None = None

    # -- the seven separate times (§5 item 4; §8 line 171 no-collapse) ------
    announcement_time: str | None = None
    observation_time: str | None = None
    record_time: str | None = None
    ex_time: str | None = None
    effective_time: str | None = None
    payable_time: str | None = None
    settlement_time: str | None = None

    # -- instrument route identity (§5 item 6; §12 old/new coexistence) -----
    old_instrument_identity: str | None = None
    new_instrument_identity: str | None = None
    identity_transition_final: bool | None = None

    # -- transformation / envelope / correction (§5 item 7; §16) -------------
    transition_envelope: TransitionEnvelope | None = None
    split_spec: SplitTransformationSpec | None = None
    correction: CorrectionReversalRecord | None = None
    prior_correction: CorrectionReversalRecord | None = None
    original_retained: bool | None = None

    # -- materiality (§10 line 221 — "Unknown materiality is material") -----
    event_is_material: bool | None = None
    change_triggers: frozenset[str] = frozenset()

    # -- effective-time window (§8) — opaque injected boundary tokens -------
    earliest_credible_boundary: str | None = None
    latest_completion_boundary: str | None = None
    source_disagreement_bounded: bool | None = None

    # -- sibling-injected disposition coordinates (design #21 §0.2) ---------
    # None of these is owned or derived by this lane; a real recon/are/rcl
    # producer does not exist yet in this runtime (survey §3/§4), so a
    # synthetic caller (today's fixtures) supplies them directly, and a
    # future producer would populate the same fields.
    field_confidences: frozenset[str] = frozenset()
    protective_action_may_proceed: bool | None = None
    injected_worst_intermediate_risk: Decimal | None = None
    injected_credible_space_bounded: bool | None = None
    injected_union_capacity_known: bool | None = None

    def to_kernel_record(self) -> NonTradeEventRecord:
        """Build the kernel :class:`~tos.nontrade.records.NonTradeEventRecord` honestly.

        Every field this observation carries is copied verbatim; every field it
        does not carry is left at the kernel model's own default (``None`` or
        ``()``) — never fabricated. The record stays ``DRAFT`` (the kernel
        model's own default :class:`~tos.canonical.ArtifactStatus`): this
        observation is not issuing a durable ledger citizen, only building the
        object the processor's kernel predicates read fields from directly.

        Returns:
            A freshly-``OBSERVED`` :class:`~tos.nontrade.records.NonTradeEventRecord`.
        """
        return NonTradeEventRecord(
            event_id=self.observation_id,
            event_class=self.event_class,
            event_subtype=self.event_subtype,
            source_identities=(self.source_label,),
            source_event_ids=(self.observation_id,),
            announcement_time=self.announcement_time,
            observation_time=self.observation_time,
            record_time=self.record_time,
            ex_time=self.ex_time,
            effective_time=self.effective_time,
            payable_time=self.payable_time,
            settlement_time=self.settlement_time,
            old_instrument_identity=self.old_instrument_identity,
            new_instrument_identity=self.new_instrument_identity,
            transformation_spec=self.split_spec,
            transition_envelope=self.transition_envelope,
            workflow_generation=self.workflow_generation,
            idempotency_key=self.idempotency_key,
            supersedes_ref=self.supersedes_ref,
            workflow_state=NonTradeEventWorkflowState.OBSERVED,
        )
