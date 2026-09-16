"""``RiskStateService`` — the production source for step 6/7's decision inputs (TOS risk
state service wave, lane b; ``docs/plans/2026-09-16-tos-risk-state-service-plan.md`` §2.4,
§4; DR-0003).

**What this service does.** :meth:`aggregate_inputs_for` / :meth:`action_flow_inputs_for`
build one :class:`~tos_runtime.risk.aggregate.AggregateRiskDecisionInputs` /
:class:`~tos_runtime.risk.flow.ActionFlowDecisionInputs` per :class:`~tos.engine.records
.StageRequest`, from the field-source table plan §2.1 lays out — **structural derivation** for
every field the runtime can genuinely observe (position usage from durable evidence, command
effect from the live construction, flow observation from the durable inbox/RCL log) and
**governed-policy declaration** for every field a deployment must instead attest (limits,
scope, deployment facts). It authors **no** attestation-only bool
(``all_fields_attributed``/``numerically_safe``/``valuation_ok``/
``limit_source_is_injected_envelope``/``economic_commitment_exclusive``/
``flow_commitment_exclusive``) itself — every one of those stays ``None`` here, so
:mod:`tos_runtime.compose._risk_attestations`'s existing ``_restrictive_merge`` governs them
unchanged (plan §2.1's own "정책은 이 표 밖의 값을 만들지 않는다").

**Two governed-instance boot events, once.** :meth:`__init__` appends
``AGGREGATE_RISK_POLICY_BOUND`` / ``ACTION_FLOW_POLICY_BOUND`` — the SAME "print which
activation admitted this policy" idiom :func:`tos_runtime.venue.record_order_construction_policy_bound`
already establishes, extended to these two new governed instances (plan §2.4).

**Deviation, reported: ``max_attempts`` is an added constructor dependency, not in plan
§4.1's literal list.** :func:`~tos_runtime.riskstate.flow_observation.to_action_cause`'s
``forked_beyond_bound`` is ``None`` (UNKNOWN) whenever ``max_attempts`` is absent, and
``tos.afg.cause_lineage_complete`` requires ``forked_beyond_bound is False`` to ever complete —
so leaving this argument unsupplied would make step 7 GRANT unreachable in EVERY deployment,
not merely an honest gap. The bound already exists as the SAME ``ActionAmplificationEnvelope
.max_attempts`` :class:`~tos_runtime.risk.flow.ActionFlowGovernor` already enforces via
``amplification_bounded`` — this service reads it through the SAME envelope object (never a
second config load, never a re-typed literal), via ``max_attempts_reader`` (an ``int``-or-``None``
zero-arg callable, mirroring this module's every other reader parameter).

**``root_event_id`` is read from ``StageRequest.reference.event_id`` (structural, but not the
durable inbox's own identity — ``root_event_seq`` is resolved independently, below).** No
``StageRequest`` field carries the inbox's own content-addressed
``tos.engine.records.event_identity`` digest; ``reference.event_id`` (threaded from the
DECISION_TICK payload through the gateway's own seal construction) is the best available label
for lineage-tracing purposes (:func:`~tos_runtime.riskstate.flow_observation.InboxFlowReader
.observe`'s own ``_traces_to`` comparison — it compares this SAME label against the identical
label a ``SEND_SEALED`` row's own ``send_seal.reference.event_id`` carries, both sourced from
the one ``StageRequest.reference`` this attempt shares, so lineage tracing itself is sound
regardless of whether the label matches the inbox's real digest).

**``root_event_seq``/``elapsed_monotonic`` are resolved structurally, NOT via identity
matching (team-lead disposition 2026-09-16, fixing an earlier gap).** This runtime's engine
driver handles exactly ONE inbox row at a time (``EngineDriver._process_next``'s own
``_draining`` re-entrancy guard: it pulls ``next_unconsumed()``, marks handling started, THEN
calls ``core.handle`` — the whole 19-step commitment flow — and only marks the row consumed
AFTER that returns), so the row :meth:`~tos_runtime.engine.inbox.SqliteEventInbox
.next_unconsumed` reports DURING step 6/7 processing is genuinely, structurally the current
attempt's own root event — not a guess, not an identity recomputation that might miss. This
service's ``current_seq_reader`` reads exactly that (:mod:`tos_runtime.compose
._riskstate_wiring` wires it straight from the composed inbox) and passes it to
:meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader.observe` as
``root_event_seq=`` — bypassing that reader's own ``root_event_id``-to-``event_identity``
fallback matching entirely. ``elapsed_monotonic`` is then a real, two real-reads difference
(current monotonic reading minus the ``EVENT_HANDLING_STARTED`` marker's own recorded
monotonic reading), never structurally absent.

**Unit bridge: ``monotonic_reader`` is milliseconds, ``appended_at_monotonic_ns`` is
nanoseconds.** ``tos_runtime.time.sources.MonotonicSource`` (this runtime's only injectable
per-process monotonic clock, and ``monotonic_reader``'s own source) reports whole
milliseconds; the durable evidence store's own ``appended_at_monotonic_ns`` column (what
``EVENT_HANDLING_STARTED``'s marker records) is nanoseconds. ``risk.yaml``'s
``max_elapsed_monotonic`` fixture value (``60_000``) reads as a millisecond bound consistent
with every sibling ``*_ms`` config value in this runtime's own config files — this service
therefore converts the nanosecond marker DOWN to whole milliseconds
(``handling_started_monotonic // 1_000_000``) before subtracting, so ``elapsed_monotonic``
stays in the SAME unit as the bound it is compared against.

**Deviation, reported: ``grant_identity``/``attempt_id`` are the proposal id.** No attempt
identity exists yet at step 6/7 (``StageRequest.attempt`` is populated only from step 13
onward, per that model's own docstring) — the best available, genuinely per-attempt structural
identity at this point is ``request.proposal.proposal_id``.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.*`` only (no ``shared.*``, no
``os.environ``/``subprocess``/``importlib.import_module`` — ``tools/tos_firewall_check.py``
applies this ONE allowlist uniformly across ``tos/runtime/**``; this module's own import list is
wider than its sibling ``policies``/``position``/``flow_observation`` modules because it is the
cross-lane assembly point DR-0003 §2.1 describes, not a narrower structural-observation leaf).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from tos.afg import (
    ActionCause,
    ActionClassKind,
    ActionFlowStateSnapshot,
    ObservedAmplification,
)
from tos.are import AdverseScenarioKind, AdverseScenarioSet, ProjectedCell
from tos.canonical import CanonicalizationScheme
from tos.egressgw.records import CandidateConstruction
from tos.engine.records import StageRequest
from tos.ioc import EconomicEffectEnvelope
from tos.rcl import CapacityComponent, CapacityVector
from tos.spg import HardSafetyEnvelope
from tos.venue import ActionClass

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.reservation_identity import scope_reservation_id
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.riskstate.flow_observation import (
    FlowObservation,
    InboxFlowReader,
    committed_flow_vectors,
    to_action_cause,
    to_observed_amplification,
)
from tos_runtime.riskstate.policies import (
    LoadedActionFlowPolicy,
    LoadedAggregateRiskPolicy,
)
from tos_runtime.riskstate.position import (
    EvidencePositionReader,
    PositionObservation,
    conservative_current_usage,
    in_flight_overlap_effect,
)

__all__ = ["RiskStateService"]

_ARE_BOUND_KIND = "AGGREGATE_RISK_POLICY_BOUND"
_AFG_BOUND_KIND = "ACTION_FLOW_POLICY_BOUND"
_OBSERVED_KIND = "RISK_STATE_OBSERVED"


def _envelope_max_vector(
    are_policy: LoadedAggregateRiskPolicy, hse_envelope: HardSafetyEnvelope
) -> CapacityVector:
    """Every ARE-governed dimension id's ``envelope_max`` off the ALREADY-loaded Hard Safety
    Envelope (plan §2.1 "ARE ``injected_envelope_max``") — the wiring-time boot cross-check
    (:mod:`tos_runtime.compose._riskstate_wiring`) already proved every one of these ids
    exists among ``hse_envelope.governed_dimensions``, so a lookup miss here is unreachable in
    production; this function still fails closed (``magnitude=None``, UNKNOWN) rather than
    raise, matching ``CapacityComponent``'s own "``None`` for UNKNOWN" discipline."""
    by_dimension = {
        gdl.dimension: gdl.envelope_max for gdl in hse_envelope.governed_dimensions
    }
    components = tuple(
        CapacityComponent(
            dimension_id=dimension_id, magnitude=by_dimension.get(dimension_id)
        )
        for dimension_id in sorted(set(are_policy.dimension_ids.values()))
    )
    return CapacityVector(components=components)


def _cells_for(
    are_policy: LoadedAggregateRiskPolicy,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
    *,
    conservative_usage: Decimal,
    overlap_effect: Decimal,
    max_credible_command_effect: Decimal | None,
) -> tuple[ProjectedCell, ...]:
    """One :class:`~tos.are.ProjectedCell` per (governed scope, dimension) pair the policy
    declares, crossed with every required scenario kind (plan §2.4 "producer 표") — split out
    of :meth:`RiskStateService.aggregate_inputs_for` purely for that method's own 100-line size
    budget; no behavioural difference from having this inline."""
    cells: list[ProjectedCell] = []
    for (scope, dimension), dimension_id in sorted(
        are_policy.dimension_ids.items(), key=lambda item: item[1]
    ):
        effective_limit = are_policy.effective_limits.magnitude(dimension_id)
        for scenario in sorted(required_scenario_kinds, key=lambda k: k.value):
            cells.append(
                ProjectedCell(
                    scope=scope,
                    dimension=dimension,
                    scenario=scenario,
                    conservative_current_usage=conservative_usage,
                    max_credible_command_effect=max_credible_command_effect,
                    required_concurrent_overlap_effect=overlap_effect,
                    conservative_current_usage_already_committed=conservative_usage,
                    effective_limit=effective_limit,
                )
            )
    return tuple(cells)


class RiskStateService:
    """The production step 6/7 decision-inputs source (module docstring)."""

    def __init__(
        self,
        *,
        are_policy: LoadedAggregateRiskPolicy,
        afg_policy: LoadedActionFlowPolicy,
        scheme: CanonicalizationScheme,
        hse_envelope: HardSafetyEnvelope,
        scenario_set: AdverseScenarioSet,
        required_scenario_kinds: frozenset[AdverseScenarioKind],
        position_reader: EvidencePositionReader,
        flow_reader: InboxFlowReader,
        rcl_log: SqliteCommitLog,
        construction_stage_reader: Callable[[], CandidateConstruction | None],
        effect_envelope_reader: Callable[[], EconomicEffectEnvelope | None],
        rcl_tip_reader: Callable[[], int | None],
        monotonic_reader: Callable[[], int | None],
        max_attempts_reader: Callable[[], int | None],
        current_seq_reader: Callable[[], int | None],
        evidence_store: SqliteEvidenceStore,
        environment_label: str,
        action_class: ActionClass,
        activated_member_digests: tuple[str, str],
    ) -> None:
        """Compose the service over its injected readers and record the two boot-time
        ``*_POLICY_BOUND`` evidence rows (module docstring).

        Args:
            are_policy: The loaded, activated Aggregate Risk Policy instance.
            afg_policy: The loaded, activated Action Flow Policy instance.
            scheme: The registered canonicalization scheme.
            hse_envelope: The already-loaded Hard Safety Envelope
                (:attr:`~tos_runtime.safety.profile.SafetyProfileService.envelope`) — the
                ``injected_envelope_max`` source (plan §2.1).
            scenario_set: The loaded ``AdverseScenarioSet`` (``risk.yaml``) — carried for
                interface symmetry with the caller's own construction; this service does not
                read it directly (the kernel's ``adverse_increment`` consumes it, not this
                producer, plan §0's own layering table).
            required_scenario_kinds: The loaded coverage floor (``risk.yaml``).
            position_reader: The single-source position observation reader (DR-0003 §2.2).
            flow_reader: The inbox/evidence/RCL-log flow observation reader (DR-0003 §2.3).
            rcl_log: The RCL commit log — :func:`~tos_runtime.riskstate.flow_observation
                .committed_flow_vectors`'s own port.
            construction_stage_reader: The current attempt's step-2 construction, or ``None``
                before step 2 has run.
            effect_envelope_reader: The current attempt's step-5 economic effect envelope, or
                ``None`` before step 5 has run.
            rcl_tip_reader: The RCL log's current linearizable tip, or ``None`` on a read
                failure (never raises).
            monotonic_reader: The time service's current monotonic reading, or ``None``.
            max_attempts_reader: The governing ``ActionAmplificationEnvelope.max_attempts``
                bound (module docstring's own "added dependency" deviation).
            current_seq_reader: The inbox's currently-being-handled row seq, or ``None``
                when nothing is pending (module docstring's own "resolved structurally"
                section) — sourced from ``SqliteEventInbox.next_unconsumed()``.
            evidence_store: The durable evidence append port.
            environment_label: Used to compose this service's own snapshot/observation ids.
            action_class: This composition's fixed, per-attempt :class:`~tos.venue.ActionClass`.
            activated_member_digests: ``(are_activation_digest, afg_activation_digest)`` —
                recorded on the boot evidence rows (module docstring).
        """
        self._are_policy = are_policy
        self._afg_policy = afg_policy
        self._scheme = scheme
        self._hse_envelope = hse_envelope
        self._scenario_set = scenario_set
        self._required_scenario_kinds = required_scenario_kinds
        self._position_reader = position_reader
        self._flow_reader = flow_reader
        self._rcl_log = rcl_log
        self._construction_stage_reader = construction_stage_reader
        self._effect_envelope_reader = effect_envelope_reader
        self._rcl_tip_reader = rcl_tip_reader
        self._monotonic_reader = monotonic_reader
        self._max_attempts_reader = max_attempts_reader
        self._current_seq_reader = current_seq_reader
        self._evidence_store = evidence_store
        self._environment_label = environment_label
        self._action_class = action_class
        self._envelope_max = _envelope_max_vector(are_policy, hse_envelope)
        self._snapshot_seq = 0
        self._observation_seq = 0
        #: One (attempt_id, FlowObservation, committed_flow_vectors) slot, filled by whichever
        #: of :meth:`aggregate_inputs_for` / :meth:`action_flow_inputs_for` observes flow state
        #: FIRST for a given attempt, and reused by the other — so exactly ONE
        #: ``RISK_STATE_OBSERVED`` evidence row (carrying position, flow, AND the committed
        #: flow vector count — review HIGH-2, 2026-09-16) is recorded per attempt, never two,
        #: and the durable inbox/evidence/RCL-log reads underlying
        #: :meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader.observe` /
        #: :func:`~tos_runtime.riskstate.flow_observation.committed_flow_vectors` happen once.
        self._flow_obs_cache: (
            tuple[str | None, FlowObservation, tuple[CapacityVector, ...]] | None
        ) = None
        self._record_boot_evidence(are_policy, afg_policy, activated_member_digests)

    def _record_boot_evidence(
        self,
        are_policy: LoadedAggregateRiskPolicy,
        afg_policy: LoadedActionFlowPolicy,
        activated_member_digests: tuple[str, str],
    ) -> None:
        """The two boot-time ``*_POLICY_BOUND`` rows (module docstring) — split out of
        :meth:`__init__` purely for that method's own 100-line size budget."""
        are_digest, afg_digest = activated_member_digests
        self._record_policy_bound(
            _ARE_BOUND_KIND,
            are_policy.policy.policy_id,
            are_policy.policy.policy_generation,
            are_policy.policy.canonical_digest,
            are_digest,
        )
        self._record_policy_bound(
            _AFG_BOUND_KIND,
            afg_policy.policy.policy_id,
            afg_policy.policy.policy_generation,
            afg_policy.policy.canonical_digest,
            afg_digest,
        )

    def _record_policy_bound(
        self,
        kind: str,
        policy_id: str | None,
        policy_generation: int | None,
        canonical_digest: str | None,
        activated_member_digest: str,
    ) -> None:
        self._evidence_store.append(
            {
                "policy_id": policy_id,
                "policy_generation": policy_generation,
                "canonical_digest": canonical_digest,
                "activated_member_digest": activated_member_digest,
            },
            kind=kind,
            record_class=kind,
        )

    def _observe_flow(
        self, request: StageRequest
    ) -> tuple[FlowObservation, tuple[CapacityVector, ...]]:
        """Observe flow state (AND the committed flow vectors — review HIGH-2, 2026-09-16:
        both need to land in the SAME evidence row, so both are resolved here, together, once
        per attempt) for ``request``'s own attempt (module docstring's own ``_flow_obs_cache``
        note) — whichever of :meth:`aggregate_inputs_for` / :meth:`action_flow_inputs_for`
        calls this FIRST for a given attempt id does the real inbox/evidence/RCL-log read; the
        other reuses the cached result."""
        attempt_id = getattr(request.proposal, "proposal_id", None)
        if self._flow_obs_cache is not None and self._flow_obs_cache[0] == attempt_id:
            return self._flow_obs_cache[1], self._flow_obs_cache[2]
        obs = self._flow_reader.observe(
            root_event_id=request.reference.event_id or "",
            attempt_id=attempt_id or "",
            root_event_seq=self._current_seq_reader(),
        )
        vectors = committed_flow_vectors(
            self._rcl_log, flow_dimension_id=self._afg_policy.flow_dimension_id
        )
        self._flow_obs_cache = (attempt_id, obs, vectors)
        return obs, vectors

    def _record_observation(
        self,
        *,
        attempt_id: str | None,
        position_obs: PositionObservation,
        flow_obs: FlowObservation,
        committed_vectors: tuple[CapacityVector, ...],
        extra_absent: tuple[str, ...],
    ) -> None:
        """Record ONE ``RISK_STATE_OBSERVED`` row carrying BOTH position and flow state
        (plan §2.4's own "position 관측 + flow 관측 + absent_fields" shape) — split out of
        :meth:`aggregate_inputs_for` purely for that method's own 100-line size budget.
        ``absent_fields`` is SORTED — deterministic, review HIGH-2 (2026-09-16) — never an
        encounter-order artifact a caller could mistake for significance.
        """
        self._observation_seq += 1
        absent = sorted(
            {*extra_absent}
            | {
                name
                for name, value in (
                    ("duplicates_rejected", flow_obs.duplicates_rejected),
                    ("replays", flow_obs.replays),
                    ("root_event_seq", flow_obs.root_event_seq),
                    ("handling_started_monotonic", flow_obs.handling_started_monotonic),
                    ("lineage_found", flow_obs.lineage_found),
                )
                if value is None
            }
            | ({"committed_flow_vectors"} if not committed_vectors else set())
        )
        self._evidence_store.append(
            {
                "attempt_id": attempt_id,
                "position": {
                    "scope_key": position_obs.scope_key,
                    "confirmed_net": str(position_obs.confirmed_net),
                    "unknown_buy": str(position_obs.unknown_buy),
                    "unknown_sell": str(position_obs.unknown_sell),
                    "in_flight_buy": str(position_obs.in_flight_buy),
                    "in_flight_sell": str(position_obs.in_flight_sell),
                    "attempts_seen": position_obs.attempts_seen,
                    "sources": list(position_obs.sources),
                },
                "flow": {
                    "queue_depth": flow_obs.queue_depth,
                    "in_flight": flow_obs.in_flight,
                    "attempts_for_cause": flow_obs.attempts_for_cause,
                    "duplicates_rejected": flow_obs.duplicates_rejected,
                    "replays": flow_obs.replays,
                    "root_event_seq": flow_obs.root_event_seq,
                    "handling_started_monotonic": flow_obs.handling_started_monotonic,
                    "lineage_found": flow_obs.lineage_found,
                    "sources": list(flow_obs.sources),
                    "committed_flow_vectors_count": len(committed_vectors),
                },
                "absent_fields": absent,
            },
            kind=_OBSERVED_KIND,
            record_class=_OBSERVED_KIND,
        )

    def aggregate_inputs_for(
        self, request: StageRequest
    ) -> AggregateRiskDecisionInputs | None:
        """Build step 6's inputs for ``request`` (module docstring; plan §2.4)."""
        position_obs = self._position_reader.observe()
        flow_obs, committed_vectors = self._observe_flow(request)
        conservative_usage = conservative_current_usage(position_obs)
        overlap_effect = in_flight_overlap_effect(position_obs)
        construction = self._construction_stage_reader()
        max_credible_command_effect = (
            None if construction is None else construction.derivation.quantity
        )
        effect_envelope = self._effect_envelope_reader()
        effect_digest = (
            None
            if effect_envelope is None
            else self._scheme.compute_digest(effect_envelope.model_dump(mode="json"))
        )
        cells = _cells_for(
            self._are_policy,
            self._required_scenario_kinds,
            conservative_usage=conservative_usage,
            overlap_effect=overlap_effect,
            max_credible_command_effect=max_credible_command_effect,
        )
        grant_identity = getattr(request.proposal, "proposal_id", None)
        lineage_ref = request.reference.event_id
        absent = tuple(
            name
            for name, value in (
                ("max_credible_command_effect", max_credible_command_effect),
                ("effect_digest", effect_digest),
                ("grant_identity", grant_identity),
                ("lineage_ref", lineage_ref),
            )
            if value is None
        )
        self._record_observation(
            attempt_id=grant_identity,
            position_obs=position_obs,
            flow_obs=flow_obs,
            committed_vectors=committed_vectors,
            extra_absent=absent,
        )
        return AggregateRiskDecisionInputs(
            cells=cells,
            required_scenario_kinds=self._required_scenario_kinds,
            applicable_risk_scopes=self._are_policy.applicable_risk_scopes,
            all_fields_attributed=None,
            required_scopes=self._are_policy.required_scopes,
            numerically_safe=None,
            valuation_ok=None,
            injected_envelope_max=self._envelope_max,
            limit_source_is_injected_envelope=None,
            effective_limit=self._are_policy.effective_limits,
            policy=self._are_policy.policy,
            grant_identity=grant_identity,
            effect_digest=effect_digest,
            lineage_ref=lineage_ref,
        )

    def _action_cause_for(
        self, request: StageRequest, flow_obs: FlowObservation
    ) -> ActionCause:
        construction = self._construction_stage_reader()
        command = None if construction is None else construction.command
        command_identity = None if command is None else command.command_id
        command_digest = None if command is None else command.canonical_digest
        return to_action_cause(
            flow_obs,
            root_event_id=request.reference.event_id or "",
            proposal_id=getattr(request.proposal, "proposal_id", None) or "",
            command_identity=command_identity,
            command_digest=command_digest,
            max_attempts=self._max_attempts_reader(),
        )

    def _snapshot_for(self, rcl_tip: int) -> ActionFlowStateSnapshot:
        self._snapshot_seq += 1
        snapshot = ActionFlowStateSnapshot.issue(
            scheme=self._scheme,
            snapshot_id=f"afg-snap-{self._environment_label}-{self._snapshot_seq}",
            snapshot_generation=rcl_tip,
            consistency_cut_identity=f"rcl-tip-{rcl_tip}",
            covered_scopes=self._afg_policy.covered_scopes,
            scope_independence=(self._afg_policy.scope_independence,),
        )
        assert isinstance(snapshot, ActionFlowStateSnapshot)
        return snapshot

    def action_flow_inputs_for(
        self, request: StageRequest
    ) -> ActionFlowDecisionInputs | None:
        """Build step 7's inputs for ``request`` (module docstring; plan §2.4). Returns
        ``None`` (UNKNOWN — never a fabricated grant) when the RCL tip is unreadable or this
        composition's fixed :attr:`_action_class` is not among the policy's own
        ``action_class_map``.

        Emits no evidence of its own — :meth:`aggregate_inputs_for` (step 6) always runs
        first for the same attempt in the real commitment flow (a step-6 DENY/UNKNOWN halts
        the sequencer before step 7's stage is ever invoked at all), so ONE
        ``RISK_STATE_OBSERVED`` row per attempt, recorded there, already covers both position
        and flow state (module docstring's own ``_flow_obs_cache`` note); this method reuses
        that SAME cached :class:`~tos_runtime.riskstate.flow_observation.FlowObservation`
        rather than reading the inbox/evidence store a second time.
        """
        rcl_tip = self._rcl_tip_reader()
        if rcl_tip is None:
            return None
        action_class_kind = self._afg_policy.action_class_map.get(self._action_class)
        if action_class_kind is None:
            return None
        flow_obs, committed_vectors = self._observe_flow(request)
        cause = self._action_cause_for(request, flow_obs)
        return self._build_action_flow_inputs(
            request, rcl_tip, action_class_kind, flow_obs, cause, committed_vectors
        )

    def _elapsed_monotonic_ms(self, flow_obs: FlowObservation) -> Decimal | None:
        """``monotonic_reader()`` minus the ``EVENT_HANDLING_STARTED`` marker's own
        recorded monotonic reading, in whole milliseconds — split out of
        :meth:`_build_action_flow_inputs` purely for that method's own 100-line size
        budget.

        Unit bridge (module docstring): ``flow_obs.handling_started_monotonic`` is
        nanoseconds (the evidence store's own ``appended_at_monotonic_ns`` column);
        ``monotonic_reader`` is milliseconds (this runtime's only injectable per-process
        monotonic clock, ``tos_runtime.time.sources.MonotonicSource.now_ms``). Converted
        down to whole milliseconds here so ``elapsed_monotonic`` stays in the SAME unit as
        ``risk.yaml``'s own ``max_elapsed_monotonic`` bound.
        """
        mono_now_ms = self._monotonic_reader()
        if mono_now_ms is None or flow_obs.handling_started_monotonic is None:
            return None
        return Decimal(mono_now_ms - (flow_obs.handling_started_monotonic // 1_000_000))

    def _afg_digests(
        self, cause: ActionCause, observed: ObservedAmplification
    ) -> tuple[str, str, str]:
        """``(cause_digest, lineage_digest, amplification_envelope_digest)`` — split out of
        :meth:`_build_action_flow_inputs` purely for that method's own 100-line size
        budget."""
        cause_digest = self._scheme.compute_digest(
            {
                "root_cause_identity": cause.root_cause_identity,
                "parent_lineage": list(cause.parent_lineage),
                "command_identity": cause.command_identity,
                "command_digest": cause.command_digest,
            }
        )
        lineage_digest = self._scheme.compute_digest(
            {"parent_lineage": list(cause.parent_lineage)}
        )
        amplification_envelope_digest = self._scheme.compute_digest(
            observed.model_dump(mode="json")
        )
        return cause_digest, lineage_digest, amplification_envelope_digest

    def _build_action_flow_inputs(
        self,
        request: StageRequest,
        rcl_tip: int,
        action_class_kind: ActionClassKind,
        flow_obs: FlowObservation,
        cause: ActionCause,
        committed_vectors: tuple[CapacityVector, ...],
    ) -> ActionFlowDecisionInputs:
        """Split out of :meth:`action_flow_inputs_for` purely for that method's own 100-line
        size budget; no behavioural difference from having this inline. ``committed_vectors``
        is the SAME value :meth:`_observe_flow` already resolved (and recorded absence of, if
        empty, on the shared ``RISK_STATE_OBSERVED`` row) — never a second, independent RCL
        log read here."""
        observed = to_observed_amplification(
            flow_obs,
            self._afg_policy.deployment_facts,
            elapsed_monotonic=self._elapsed_monotonic_ms(flow_obs),
            fan_out=flow_obs.attempts_for_cause,
            depth=(None if flow_obs.lineage_found is None else 1),
        )
        snapshot = self._snapshot_for(rcl_tip)
        flow_vector = CapacityVector(
            components=(
                CapacityComponent(
                    dimension_id=self._afg_policy.flow_dimension_id,
                    magnitude=Decimal(1),
                ),
            )
        )
        economic_ref = scope_reservation_id(
            request.instrument_key.account, request.instrument_key.instrument
        )
        cause_digest, lineage_digest, amplification_envelope_digest = self._afg_digests(
            cause, observed
        )
        return ActionFlowDecisionInputs(
            cause=cause,
            snapshot=snapshot,
            required_scopes=self._afg_policy.required_scopes,
            # DERIVED from how `snapshot` (above) was actually built, not a separate
            # attestation: `_snapshot_for` sets `covered_scopes` EXCLUSIVELY from
            # `self._afg_policy.covered_scopes` — the activated, governed policy document —
            # and takes no argument through which `request`/`cause`/any producer-supplied
            # value could substitute or narrow it. Since this snapshot's own scope coverage
            # structurally cannot have come from a producer, `producer_self_declared_scope`
            # is positively `False` by construction, not a guess or a hardcoded admission
            # literal. `False` is required here (not merely permitted):
            # `scope_graph_complete` treats `None` the same as a producer-declared scope,
            # both fail-closed (tos.afg.predicates `scope_graph_complete`'s own docstring,
            # point 3).
            producer_self_declared_scope=False,
            observed_amplification=observed,
            requested_limit=flow_vector,
            injected_envelope_max=self._afg_policy.limits["envelope_max"],
            limit_source_is_injected_envelope=None,
            economic_ref=economic_ref,
            flow_vector=flow_vector,
            committed_flow_vectors=committed_vectors,
            hard_limit=self._afg_policy.limits["hard_limit"],
            runtime_limit=self._afg_policy.limits["runtime_limit"],
            economic_commitment_exclusive=None,
            flow_commitment_exclusive=None,
            generation_current=False,
            applicable_action_flow_scopes=self._afg_policy.applicable_action_flow_scopes,
            decision_generation=rcl_tip,
            policy=self._afg_policy.policy,
            action_class=action_class_kind,
            decision_effective_limit=self._afg_policy.limits[
                "decision_effective_limit"
            ],
            command_identity=cause.command_identity,
            command_digest=cause.command_digest,
            cause_digest=cause_digest,
            lineage_digest=lineage_digest,
            amplification_envelope_digest=amplification_envelope_digest,
        )
