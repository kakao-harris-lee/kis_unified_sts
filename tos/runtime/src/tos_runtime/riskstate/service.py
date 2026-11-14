"""``RiskStateService`` — the production source for step 6/7's decision inputs (TOS risk"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from threading import Lock

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
from tos.venue import ActionClass

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.reservation_identity import scope_reservation_id
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.close_quantity import close_within_entry
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.risk.ledger_stages import (
    CloseProofCommitFence,
    SyntheticCloseEntryFence,
)
from tos_runtime.riskstate.close_bound import (
    CloseAuthoritySource,
    CloseBoundRefusal,
    EntryCloseBound,
    synthetic_close_effect,
    synthetic_close_fence,
)
from tos_runtime.riskstate.close_effect import (
    ABSENT_BOUND_FIELD,
    PROOF_BEARING_STATUSES,
    close_effect_audit,
    close_proof_matches,
    refused_bound,
    tightest_cap,
)
from tos_runtime.riskstate.flow_observation import (
    FlowObservation,
    InboxFlowReader,
    committed_flow_vectors,
    to_action_cause,
    to_observed_amplification,
)
from tos_runtime.riskstate.held_position import (
    HeldPositionCurrentness,
    HeldPositionProof,
    PositionSide,
    RclTip,
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


def _envelope_max_vector(are_policy: LoadedAggregateRiskPolicy) -> CapacityVector:
    """Every ARE-governed dimension id's ``injected_envelope_max`` ceiling, off the ARE"""
    by_dimension = {
        component.dimension_id: component.magnitude
        for component in are_policy.envelope_max.components
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
    """One :class:`~tos.are.ProjectedCell` per (governed scope, dimension) pair the policy"""
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
        action_class_reader: Callable[[], ActionClass] | None = None,
        attempt_arm_direction_reader: Callable[[], str | None] | None = None,
        held_position_proof_reader: (
            Callable[[StageRequest, str], HeldPositionProof | None] | None
        ) = None,
        held_position_currentness_reader: (
            Callable[[HeldPositionProof], HeldPositionCurrentness | None] | None
        ) = None,
        close_authority: CloseAuthoritySource = CloseAuthoritySource.BROKER_HELD_PROOF,
        entry_close_bound_reader: Callable[[], EntryCloseBound] | None = None,
    ) -> None:
        """Compose injected policy/readers and append the two boot policy-bound events."""
        self._are_policy = are_policy
        self._afg_policy = afg_policy
        self._scheme = scheme
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
        self._action_class_reader = action_class_reader
        self._attempt_arm_direction_reader = attempt_arm_direction_reader
        self._held_position_proof_reader = held_position_proof_reader
        self._held_position_currentness_reader = held_position_currentness_reader
        self._close_authority = close_authority
        self._entry_close_bound_reader = entry_close_bound_reader
        self._close_proof_lock = Lock()
        self._close_fence_proof: HeldPositionProof | None = None
        self._close_fence_bound: tuple[str, EntryCloseBound, Decimal] | None = None
        self._envelope_max = _envelope_max_vector(are_policy)
        self._snapshot_seq = 0
        self._observation_seq = 0
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
        """The two boot-time ``*_POLICY_BOUND`` rows (module docstring) — split out of"""
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
        """Observe flow state (AND the committed flow vectors — review HIGH-2, 2026-09-16:"""
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
        close_effect: dict[str, object] | None = None,
    ) -> None:
        """Record ONE ``RISK_STATE_OBSERVED`` row carrying BOTH position and flow state"""
        self._observation_seq += 1
        absent = sorted(
            {*extra_absent}
            | {
                name
                for name, value in (
                    ("root_event_seq", flow_obs.root_event_seq),
                    ("handling_started_monotonic", flow_obs.handling_started_monotonic),
                    ("lineage_found", flow_obs.lineage_found),
                )
                if value is None
            }
            | ({"committed_flow_vectors"} if not committed_vectors else set())
        )
        observation: dict[str, object] = {
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
                "replays_definition": flow_obs.replays_definition,
                "root_event_seq": flow_obs.root_event_seq,
                "handling_started_monotonic": flow_obs.handling_started_monotonic,
                "lineage_found": flow_obs.lineage_found,
                "sources": list(flow_obs.sources),
                "committed_flow_vectors_count": len(committed_vectors),
            },
            "absent_fields": absent,
        }
        if close_effect is not None:
            observation["close_effect"] = close_effect
        self._evidence_store.append(
            observation,
            kind=_OBSERVED_KIND,
            record_class=_OBSERVED_KIND,
        )

    def _arm_direction(self) -> tuple[str | None, str | None]:
        """The side token step 2's selected arm carries, or a fail-closed audit status."""
        try:
            direction = (
                None
                if self._attempt_arm_direction_reader is None
                else self._attempt_arm_direction_reader()
            )
        except Exception:  # noqa: BLE001 - direction failures fail closed
            return None, "DIRECTION_ERROR"
        if direction not in (PositionSide.LONG.value, PositionSide.SHORT.value):
            return direction, "DIRECTION_UNAVAILABLE"
        return direction, None

    def _read_close_proof(
        self, request: StageRequest
    ) -> tuple[str | None, HeldPositionProof | None, str]:
        """Consume one cache proof for the selected AttemptArm's held side."""
        direction, failure = self._arm_direction()
        if failure is not None:
            return direction, None, failure
        if self._held_position_proof_reader is None:
            return direction, None, "PROVIDER_NOT_CONFIGURED"
        try:
            proof = self._held_position_proof_reader(request, str(direction))
        except Exception:  # noqa: BLE001 - provider failures cannot grant risk credit
            return direction, None, "PROVIDER_ERROR"
        return (
            direction,
            proof,
            "PROOF_UNAVAILABLE" if proof is None else "PROOF_INVALID",
        )

    def _read_entry_bound(self) -> EntryCloseBound:
        """The durable open-entry bound of this scope, or a typed refusal (#1011)."""
        if self._entry_close_bound_reader is None:
            return refused_bound(CloseBoundRefusal.READER_NOT_CONFIGURED)
        try:
            bound = self._entry_close_bound_reader()
        except Exception:  # noqa: BLE001 - a reader failure cannot grant risk credit
            return refused_bound(CloseBoundRefusal.READER_UNUSABLE)
        if type(bound) is not EntryCloseBound:
            return refused_bound(CloseBoundRefusal.READER_UNUSABLE)
        return bound

    def _close_command_effect(
        self, request: StageRequest, proposed: Decimal | None
    ) -> tuple[Decimal | None, dict[str, object]]:
        """Derive this CLOSE's risk credit under the boot's own close authority (#1011)."""
        with self._close_proof_lock:
            self._close_fence_proof = None
            self._close_fence_bound = None
        bound = self._read_entry_bound()
        if self._close_authority is CloseAuthoritySource.DURABLE_EVIDENCE:
            return self._synthetic_close_effect(request, proposed, bound)
        return self._broker_close_effect(request, proposed, bound)

    def _synthetic_close_effect(
        self, request: StageRequest, proposed: Decimal | None, bound: EntryCloseBound
    ) -> tuple[Decimal | None, dict[str, object]]:
        """SYNTHETIC transport: the durable evidence store is the broker (#1011)."""
        direction, failure = self._arm_direction()
        if failure is not None:
            return None, close_effect_audit(direction, failure, None, None, bound=bound)
        effect, status = synthetic_close_effect(bound, proposed)
        proposal_id = getattr(request.proposal, "proposal_id", None)
        if effect is not None and proposed is not None and type(proposal_id) is str:
            with self._close_proof_lock:
                self._close_fence_bound = (proposal_id, bound, proposed)
        return effect, close_effect_audit(direction, status, None, effect, bound=bound)

    def _broker_close_effect(
        self, request: StageRequest, proposed: Decimal | None, bound: EntryCloseBound
    ) -> tuple[Decimal | None, dict[str, object]]:
        """KIS stock: the broker holding, capped by what remains of the TOS entry (#1012 L3)."""
        direction, proof, status = self._read_close_proof(request)
        effect: Decimal | None = None
        proof_matches = type(proof) is HeldPositionProof and close_proof_matches(
            proof, request, direction
        )
        held_quantity = (
            proof.held_quantity
            if proof_matches and type(proof) is HeldPositionProof
            else None
        )
        bounded = close_within_entry(
            entry=tightest_cap(held_quantity, bound.remaining),
            closed=Decimal(0),
            proposed=proposed,
        )
        if proof_matches and bounded is True and proposed is not None:
            effect = -proposed
            status = "PROOF_ACCEPTED"
        elif proof_matches and bounded is False:
            status = "QUANTITY_EXCEEDS_HELD"
        elif proof_matches:
            status = "QUANTITY_UNKNOWN"
        elif proof is not None:
            status = "PROOF_SCOPE_OR_SIDE_INVALID"

        if effect is not None and type(proof) is HeldPositionProof:
            with self._close_proof_lock:
                self._close_fence_proof = proof
        return effect, close_effect_audit(direction, status, proof, effect, bound=bound)

    def take_close_fence(
        self, request: StageRequest
    ) -> CloseProofCommitFence | SyntheticCloseEntryFence | None:
        """Consume step 6's exact CLOSE bound/proof for the step-9 RCL commit fence."""
        if self._close_authority is CloseAuthoritySource.DURABLE_EVIDENCE:
            return self._synthetic_close_fence(request)
        proposal_id = getattr(request.proposal, "proposal_id", None)
        with self._close_proof_lock:
            proof = self._close_fence_proof
            self._close_fence_proof = None
        if type(proof) is not HeldPositionProof or type(proposal_id) is not str:
            return None
        if not close_proof_matches(proof, request, proof.side.value):
            return None
        if self._held_position_currentness_reader is None:
            return None
        try:
            currentness = self._held_position_currentness_reader(proof)
        except Exception:  # noqa: BLE001 - currentness failures deny commit
            return None
        if type(currentness) is not HeldPositionCurrentness:
            return None
        verified_tip = currentness.rcl_tip
        if (
            type(currentness.current_now_ms) is not int
            or type(currentness.current_trading_date) is not str
            or type(verified_tip) is not RclTip
            or verified_tip.writer_epoch != proof.rcl_tip.writer_epoch
            or proof.rcl_tip.last_seq is None
            or verified_tip.last_seq is None
            or verified_tip.last_seq < proof.rcl_tip.last_seq
            or currentness.current_now_ms < proof.age_origin_ms
            or currentness.current_now_ms - proof.age_origin_ms > proof.max_age_ms
            or currentness.current_trading_date != proof.trading_date
        ):
            return None
        generation = proof.scope.as_of_generation
        if type(generation) is not int:
            return None
        instrument_key = proof.scope.instrument_keys[0]
        return CloseProofCommitFence(
            proposal_id=proof.proposal_id,
            account=proof.scope.account,
            instrument=instrument_key.instrument,
            attempt_ids=proof.scope.attempt_ids,
            as_of_generation=generation,
            observed_at_generation=proof.observed_at_generation,
            trading_date=proof.trading_date,
            age_origin_ms=proof.age_origin_ms,
            rcl_writer_epoch=proof.rcl_tip.writer_epoch,
            rcl_last_seq=proof.rcl_tip.last_seq,
            verified_rcl_writer_epoch=verified_tip.writer_epoch,
            verified_rcl_last_seq=verified_tip.last_seq,
            current_now_ms=currentness.current_now_ms,
            current_trading_date=currentness.current_trading_date,
            max_age_ms=proof.max_age_ms,
        )

    def _synthetic_close_fence(
        self, request: StageRequest
    ) -> SyntheticCloseEntryFence | None:
        """Re-read the durable bound step 6 granted against, and fence step 9 on it (#1011)."""
        with self._close_proof_lock:
            stashed = self._close_fence_bound
            self._close_fence_bound = None
        if stashed is None:
            return None
        proposal_id, bound, proposed = stashed
        return synthetic_close_fence(
            request,
            bound=bound,
            current=self._read_entry_bound(),
            proposed=proposed,
            granted_proposal_id=proposal_id,
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
        action_class = (
            self._action_class
            if self._action_class_reader is None
            else self._action_class_reader()
        )
        close_effect: dict[str, object] | None = None
        if action_class is ActionClass.CLOSE:
            max_credible_command_effect, close_effect = self._close_command_effect(
                request, max_credible_command_effect
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
        absent_fields = tuple(
            name
            for name, value in (
                ("max_credible_command_effect", max_credible_command_effect),
                ("effect_digest", effect_digest),
                ("grant_identity", grant_identity),
                ("lineage_ref", lineage_ref),
            )
            if value is None
        )
        if (
            close_effect is not None
            and close_effect["proof_status"] not in PROOF_BEARING_STATUSES
        ):
            absent_fields = (
                *absent_fields,
                ABSENT_BOUND_FIELD[self._close_authority],
            )
        self._record_observation(
            attempt_id=grant_identity,
            position_obs=position_obs,
            flow_obs=flow_obs,
            committed_vectors=committed_vectors,
            extra_absent=absent_fields,
            close_effect=close_effect,
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
        """Build step 7's inputs for ``request`` (module docstring; plan §2.4). Returns"""
        rcl_tip = self._rcl_tip_reader()
        if rcl_tip is None:
            return None
        action_class = (
            self._action_class
            if self._action_class_reader is None
            else self._action_class_reader()
        )
        action_class_kind = self._afg_policy.action_class_map.get(action_class)
        if action_class_kind is None:
            return None
        flow_obs, committed_vectors = self._observe_flow(request)
        cause = self._action_cause_for(request, flow_obs)
        return self._build_action_flow_inputs(
            request, rcl_tip, action_class_kind, flow_obs, cause, committed_vectors
        )

    def _elapsed_monotonic_ms(self, flow_obs: FlowObservation) -> Decimal | None:
        """``monotonic_reader()`` minus the ``EVENT_HANDLING_STARTED`` marker's own"""
        mono_now_ms = self._monotonic_reader()
        if mono_now_ms is None or flow_obs.handling_started_monotonic is None:
            return None
        return Decimal(mono_now_ms - (flow_obs.handling_started_monotonic // 1_000_000))

    def _afg_digests(
        self, cause: ActionCause, observed: ObservedAmplification
    ) -> tuple[str, str, str]:
        """``(cause_digest, lineage_digest, amplification_envelope_digest)`` — split out of"""
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
        """Split out of :meth:`action_flow_inputs_for` purely for that method's own 100-line"""
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
