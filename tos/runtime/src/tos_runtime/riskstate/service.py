"""``RiskStateService`` — the production source for step 6/7's decision inputs (TOS risk
state service wave, lane b; ``docs/plans/2026-09-16-tos-risk-state-service-plan.md`` §2.4,
§4; DR-0003).

**What this service does.** :meth:`aggregate_inputs_for` / :meth:`action_flow_inputs_for`
build one :class:`~tos_runtime.risk.aggregate.AggregateRiskDecisionInputs` /
:class:`~tos_runtime.risk.flow.ActionFlowDecisionInputs` per :class:`~tos.engine.records
.StageRequest`, from the field-source table plan §2.1 lays out — **structural derivation** for
every field the runtime can genuinely observe (position usage from durable evidence, OPEN
command effect from the live construction, flow observation from the durable inbox/RCL log) and
**governed-policy declaration** for every field a deployment must instead attest (limits,
scope, deployment facts). It authors **no** attestation-only bool
(``all_fields_attributed``/``numerically_safe``/``valuation_ok``/
``limit_source_is_injected_envelope``/``economic_commitment_exclusive``/
``flow_commitment_exclusive``) itself — every one of those stays ``None`` here, so
:mod:`tos_runtime.compose._risk_attestations`'s existing ``_restrictive_merge`` governs them
unchanged (plan §2.1's own "정책은 이 표 밖의 값을 만들지 않는다").

**CLOSE effects require broker-held proof (#1004).** A close may reduce aggregate risk only when
the optional injected reader returns a one-use, complete, fresh, independent, per-attempt KIS
stock holding proof for the exact current ``AttemptArm.direction``. The held-position cell issuing
that proof rechecks trusted date and RCL tip. Local fills and ``POSITION_CONSUMED`` rows never
stand in for current holdings. When the reader, direction, or proof is absent or invalid, the
effect stays ``None`` and ARE returns ``UNKNOWN``; a composition that does not wire a proof reader
therefore blocks all CLOSEs at step 6.

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
from tos.spg import HardSafetyEnvelope
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
        """Compose injected policy/readers and append the two boot policy-bound events.

        The optional CLOSE readers consume and revalidate the one-use held-position proof.
        Without them, or when any proof input is unavailable, CLOSE remains UNKNOWN.
        ``close_authority`` selects which bound a CLOSE rests on (#1011 — the composition root
        derives it from the boot's transport kind), and ``entry_close_bound_reader`` supplies
        the durable entry/proven-close magnitudes BOTH authorities need: the synthetic one as
        its whole bound, the broker one as the extra TOS-entry cap (#1012 L3). Other argument
        contracts follow the named runtime ports and the module-level plan references.
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
        self._action_class_reader = action_class_reader
        self._attempt_arm_direction_reader = attempt_arm_direction_reader
        self._held_position_proof_reader = held_position_proof_reader
        self._held_position_currentness_reader = held_position_currentness_reader
        self._close_authority = close_authority
        self._entry_close_bound_reader = entry_close_bound_reader
        self._close_proof_lock = Lock()
        self._close_fence_proof: HeldPositionProof | None = None
        #: The step-6 synthetic bound and the quantity it admitted, held for the step-9 fence
        #: exactly as ``_close_fence_proof`` holds the broker-held one — one use, per attempt.
        self._close_fence_bound: tuple[str, EntryCloseBound, Decimal] | None = None
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
        close_effect: dict[str, object] | None = None,
    ) -> None:
        """Record ONE ``RISK_STATE_OBSERVED`` row carrying BOTH position and flow state
        (plan §2.4's own "position 관측 + flow 관측 + absent_fields" shape) — split out of
        :meth:`aggregate_inputs_for` purely for that method's own 100-line size budget.
        ``absent_fields`` is SORTED — deterministic, review HIGH-2 (2026-09-16) — never an
        encounter-order artifact a caller could mistake for significance. ``duplicates_rejected``/
        ``replays`` are deliberately NOT in this None-check table (TOS action-flow observation
        completion wave, 2026-09-16): :meth:`~tos_runtime.riskstate.flow_observation
        .InboxFlowReader.observe` now always populates both from a completed durable-evidence
        scan (never ``None``), so they are observed, not absent — see that module's own docstring.
        """
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
        # The STEP-6 proposal id travels with the stash, exactly as the broker path carries
        # `proof.proposal_id` (review-1015 L1). Without it `synthetic_close_fence` would copy
        # step 9's own id into the fence and `synthetic_close_fence_valid` would compare that
        # value with itself — a check that cannot fail is not a check.
        proposal_id = getattr(request.proposal, "proposal_id", None)
        if effect is not None and proposed is not None and type(proposal_id) is str:
            with self._close_proof_lock:
                self._close_fence_bound = (proposal_id, bound, proposed)
        return effect, close_effect_audit(direction, status, None, effect, bound=bound)

    def _broker_close_effect(
        self, request: StageRequest, proposed: Decimal | None, bound: EntryCloseBound
    ) -> tuple[Decimal | None, dict[str, object]]:
        """KIS stock: the broker holding, capped by what remains of the TOS entry (#1012 L3).

        The cap is ``min(held, entry - proven closes)``. Before it, a scope holding shares
        bought outside TOS admitted a close of the whole holding; the entry then refused to
        discharge (``CLOSED_OVER_ENTRY``) and the scope sealed itself.
        """
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
        """Re-read the durable bound step 6 granted against, and fence step 9 on it (#1011).

        The synthetic counterpart of the broker-held currentness recheck above: a SECOND,
        independent read of the RCL + evidence store, required to name the same entry with the
        same magnitudes at a tip no older. The fence then carries that re-read tip, which step 9
        pins its CAS to. The stashed STEP-6 proposal id is what the fence is minted under
        (review-1015 L1), so step 9 compares its own request against a value step 6 wrote.
        """
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
        """Build step 7's inputs for ``request`` (module docstring; plan §2.4). Returns
        ``None`` (UNKNOWN — never a fabricated grant) when the RCL tip is unreadable or this
        attempt's action class (#960) is not among the policy's own
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
