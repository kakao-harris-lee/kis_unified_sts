"""``ComposeContextResolver`` — the composition root's own ``SendBoundaryContext``"""

from __future__ import annotations

import functools
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tos.afg import (
    ActionFlowDecision,
    ActionFlowPermit,
    ActionFlowResult,
)
from tos.are import AggregateRiskDecision
from tos.cur import EgressCurrentnessProof, EgressProofCoordinateSet
from tos.egress import (
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressRequestRecord,
    QuorumCommitCertificate,
    credential_route_authority_disjoint,
)
from tos.egressgw import (
    CandidateConstruction,
    ConformanceProofStage,
    OrderConstructionStage,
    SendBoundaryContext,
    TransportNature,
    send_boundary_context,
)
from tos.engine import AttemptRequest, InstrumentKey, StageRequest, StageVerdict
from tos.engine.vocabulary import StageOutcome
from tos.ordering import OrderingEvent
from tos.rcl import TransmissionCapability
from tos.venue import ActionClass

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    InstanceDocument,
    Item6Item12Fields,
    derive_item6_item12,
)
from tos_runtime.brokercap.live_scope import live_scope_valid
from tos_runtime.compose._attempt_arm import attempt_action_class, attempt_side
from tos_runtime.compose._request_digest import RequestBytesDigestSource
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.stages import TransmissionCapabilityStage
from tos_runtime.currentness.vector import CurrentnessAssembler
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.rcl.reservation_identity import attempt_request_reservation_id
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
    AggregateRiskService,
)
from tos_runtime.risk.flow import (
    ActionFlowDecisionInputs,
    ActionFlowGovernor,
)
from tos_runtime.safety.latch import (
    CapacityOwner,
    RestrictiveLatchOwner,
    egress_owner_fields,
)

if TYPE_CHECKING:
    from tos_runtime.compose._venue_wiring import VenueServiceStage

__all__ = [
    "ComposeContextResolver",
    "RecordingActionFlowGovernor",
    "RecordingAggregateRiskService",
    "VerdictRecorder",
    "make_permit_provider",
    "record_egress_identity_observation",
]

_EGRESS_IDENTITY_OBSERVATION_KIND = "EGRESS_IDENTITY_OBSERVATION"


def record_egress_identity_observation(
    evidence_store: SqliteEvidenceStore,
    inventory: tuple[CredentialRouteInventoryEntry, ...],
) -> None:
    """W3.1 independent review MEDIUM-4 disposition: EGRESS_IDENTITY is reverted to"""
    evidence_store.append(
        {
            "credential_route_authority_disjoint": credential_route_authority_disjoint(
                inventory
            )
        },
        kind=_EGRESS_IDENTITY_OBSERVATION_KIND,
        record_class=_EGRESS_IDENTITY_OBSERVATION_KIND,
    )


class VerdictRecorder:
    """Wraps one :class:`~tos.engine.sequencer.Stage`, remembering the last"""

    def __init__(self, inner: Callable[[StageRequest], StageVerdict]) -> None:
        self._inner = inner
        self.last_verdict: StageVerdict | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        verdict = self._inner(request)
        self.last_verdict = verdict
        return verdict


class RecordingAggregateRiskService(AggregateRiskService):
    """:class:`~tos_runtime.risk.aggregate.AggregateRiskService`, additionally"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.last_decision: AggregateRiskDecision | None = None

    def decide(
        self,
        key: Any,
        inputs: AggregateRiskDecisionInputs,
        *,
        snapshot_generation: int,
        decision_generation: int,
    ) -> AggregateRiskDecision:
        decision = super().decide(
            key,
            inputs,
            snapshot_generation=snapshot_generation,
            decision_generation=decision_generation,
        )
        self.last_decision = decision
        return decision


class RecordingActionFlowGovernor(ActionFlowGovernor):
    """:class:`~tos_runtime.risk.flow.ActionFlowGovernor`, additionally"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.last_decision: ActionFlowDecision | None = None
        self.last_permit: ActionFlowPermit | None = None

    def decide(self, inputs: ActionFlowDecisionInputs) -> ActionFlowDecision:
        decision = super().decide(inputs)
        self.last_decision = decision
        return decision


def make_permit_provider(
    governor: RecordingActionFlowGovernor,
    *,
    permit_generation_provider: Callable[[StageRequest], int],
    command_identity_provider: Callable[[StageRequest], str],
) -> Callable[[StageRequest], ActionFlowPermit | None]:
    """Build the ``permit_provider`` callable"""

    def _provider(request: StageRequest) -> ActionFlowPermit | None:
        decision = governor.last_decision
        if decision is None or decision.result is not ActionFlowResult.GRANT:
            return None
        try:
            generation = permit_generation_provider(request)
        except (StaleEpochRead, sqlite3.Error, OSError):
            return None
        permit = governor.build_permit(
            decision,
            permit_generation=generation,
            command_identity=command_identity_provider(request),
        )
        governor.last_permit = permit
        return permit

    return _provider


def item14_fields_from_verdict(
    verdict: StageVerdict | None,
) -> tuple[bool | None, str | None]:
    """``(approval_consumed_for_this_intent, approval_intent_binding_digest)``"""
    if verdict is None:
        return None, None
    consumed = verdict.outcome is StageOutcome.ADMIT
    return consumed, (verdict.bound_digest if consumed else None)


def item15_fields_from(
    permit: ActionFlowPermit | None, step9_verdict: StageVerdict | None
) -> tuple[str | None, bool | None]:
    """``(action_flow_permit_identity, action_flow_commitment_current)`` —"""
    identity = None if permit is None else permit.permit_id
    commitment_current = (
        None if step9_verdict is None else step9_verdict.outcome is StageOutcome.ADMIT
    )
    return identity, commitment_current


@dataclass
class ComposeContextResolver:
    """The gateway's lazy ``contexts`` resolver (design #35 §3.1 (3)),"""

    construction_stage: OrderConstructionStage
    proof_stage: ConformanceProofStage
    venue_stage: VenueServiceStage
    step4_recorder: VerdictRecorder
    step9_recorder: VerdictRecorder
    step14_stage: TransmissionCapabilityStage
    flow_governor: RecordingActionFlowGovernor
    currentness_assembler: CurrentnessAssembler
    proof_issuer: EgressCurrentnessProofIssuer
    session_facts_current_reader: Callable[[], bool | None]
    tradability_facts_current_reader: Callable[[], bool | None]
    account_facts_current_reader: Callable[[], bool | None]
    mock_generation_reader: Callable[[], bool | None]
    broker_scopes: BrokerScopesConfig
    instance_document: InstanceDocument | None
    transport_nature: TransportNature
    environment_label: str
    principal: str
    credential_route_inventory: tuple[CredentialRouteInventoryEntry, ...]
    authorized_coordinates: EgressCoordinateSet
    transport_endpoint: str | None
    request_bytes_digest_source: RequestBytesDigestSource
    outbound_side: str
    action_class: ActionClass
    observed_session_phase_reader: Callable[[], str | None]
    continuity_id: str
    instrument_key: InstrumentKey
    authority_epoch_service: SafetyAuthorityEpochService
    latch: RestrictiveLatchOwner
    capacity: CapacityOwner
    contexts: tuple[SendBoundaryContext, ...] = field(default_factory=tuple)
    _yield_seq: int = 0
    _bound_authority_epoch: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._bound_authority_epoch = self.authority_epoch_service.current_epoch()

    def _egress_request_for_command(
        self, command_digest: str | None, *, request_bytes_digest: str | None
    ) -> EgressRequestRecord | None:
        if command_digest is None or request_bytes_digest is None:
            return None
        from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

        scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
        coordinates = self.authorized_coordinates
        issued = EgressRequestRecord.issue(
            scheme=scheme,
            request_id=f"ereq-{command_digest[:16]}",
            request_bytes_digest=request_bytes_digest,
            canonical_command_digest=command_digest,
            endpoint=coordinates.endpoint,
            account=coordinates.account,
            environment=coordinates.environment,
            action=coordinates.action,
            method=coordinates.method,
            side=attempt_side(self.construction_stage, self.outbound_side),
            route_identity=coordinates.route_identity,
            credential_generation=coordinates.credential_generation,
            broker_session_generation=coordinates.broker_session_generation,
            egress_generation=coordinates.egress_generation,
            active_principal=coordinates.active_principal,
        )
        assert isinstance(issued, EgressRequestRecord)
        return issued

    def _resolve_request_bytes_digest(
        self, construction: CandidateConstruction
    ) -> str | None:
        """The ONE per-attempt request-bytes digest, computed once and shared by both"""
        quantity = construction.derivation.quantity
        price = construction.derivation.price
        account = self.authorized_coordinates.account
        if quantity is None or price is None or account is None:
            return None
        return self.request_bytes_digest_source(
            account=account,
            instrument=self.instrument_key.instrument,
            quantity=quantity,
            price=price,
        )

    def _quorum_certificate_for_command(
        self, command_digest: str | None
    ) -> QuorumCommitCertificate | None:
        if command_digest is None:
            return None
        from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

        scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
        issued = QuorumCommitCertificate.issue(
            scheme=scheme,
            qcc_id=f"qcc-{command_digest[:16]}",
            cluster_identity="single-node",
            capacity_domain=self.environment_label,
            membership_generation=1,
            restore_generation=1,
            writer_epoch=1,
            committed_revision=1,
            canonical_command_digest=command_digest,
            resulting_state_digest=command_digest,
            egress_generation=self.authorized_coordinates.egress_generation,
            active_egress_principal=self.principal,
        )
        assert isinstance(issued, QuorumCommitCertificate)
        return issued

    def _reconstruct_transmission_capability(
        self, attempt: AttemptRequest
    ) -> TransmissionCapability | None:
        """Item 1's ``transmission_capability`` object (reported seam, never"""
        nonce = self.step14_stage.nonce_for(attempt.attempt_id)
        if nonce is None:
            return None
        log = self.step14_stage._log  # noqa: SLF001 - reported shim, see docstring
        writer_epoch = self.step14_stage._writer_epoch  # noqa: SLF001
        scheme = self.step14_stage._scheme  # noqa: SLF001
        view = log.read_linearizable(writer_epoch=writer_epoch)
        if not view.epoch:
            return None
        capability = TransmissionCapability.issue(
            scheme=scheme,
            capability_id=f"cap-{attempt.attempt_id}",
            nonce=nonce,
            single_use=True,
            reservation_identity=attempt_request_reservation_id(
                self.instrument_key, attempt
            ),
            attempt_identity=attempt.attempt_id,
            account_scope=self.instrument_key.account,
            instrument_scope=self.instrument_key.instrument,
            side_action_scope=attempt_side(self.construction_stage, self.outbound_side),
            ledger_epoch=view.epoch,
            bound_reservation_revision=view.last_seq,
        )
        assert isinstance(capability, TransmissionCapability)
        return capability

    def _issue_egress_currentness_proof(
        self, attempt: AttemptRequest
    ) -> EgressCurrentnessProof | None:
        """Item 16 (Realize, lane R item 2): currentness vector assembly +"""
        vector = self.currentness_assembler.assemble()
        if vector is None or vector.currentness_revision is None:
            return None
        bound_generations = tuple(
            d.bound_generation
            for d in vector.dimensions
            if d.bound_generation is not None
        )
        restrictive_floors = tuple(
            d.restrictive_floor
            for d in vector.dimensions
            if d.restrictive_floor is not None
        )
        return self.proof_issuer.issue(
            attempt,
            vector,
            bound_generations=bound_generations,
            restrictive_floors=restrictive_floors,
            egress_coordinates=EgressProofCoordinateSet(
                principal=self.principal, local_latch_clear=True
            ),
        )

    def _egress_gate_stand_in_fields(
        self,
        construction: CandidateConstruction | None,
        derived: Item6Item12Fields,
    ) -> dict[str, Any]:
        """Items 6/12/16's ``SendBoundaryContext`` stand-in fields."""
        return {
            "account_instrument_action_allowed": (
                derived.account_instrument_action_allowed
            ),
            "max_quantity_within_allowance": (
                None if construction is None else construction.no_silent_widening_ok
            ),
            "session_facts_current": self.session_facts_current_reader(),
            "tradability_facts_current": self.tradability_facts_current_reader(),
            "account_facts_current": self.account_facts_current_reader(),
            "broker_constraint_generation_current": (
                derived.broker_constraint_generation_current
            ),
            **egress_owner_fields(self.latch, self.capacity).fields(),
        }

    def _deferred_mesh_fields(self) -> dict[str, Any]:
        """Items 4/5/7/8/9/10's ``SendBoundaryContext`` deferred-mesh fields (Phase 5"""
        return {
            "safety_authority_epoch_current": self.authority_epoch_service.epoch_current(
                self._bound_authority_epoch
            ),
            "live_scope_valid": live_scope_valid(
                self.broker_scopes,
                self.instance_document,
                sealed=self.authorized_coordinates,
                gateway_principal=self.principal,
                inventory=self.credential_route_inventory,
                transport_endpoint=self.transport_endpoint,
                environment_label=self.environment_label,
            ),
        }

    def _capability_scope_fields(self) -> dict[str, Any]:
        """The active scope's tuples — the kernel judges item 6's option (a) skip from them"""
        return {"capability_tuples": self.broker_scopes.active_scope.capability_tuples}

    def _attempt_action_class(self) -> ActionClass:
        """THIS attempt's action class: step 2's selected arm, or the boot class when step 2"""
        return attempt_action_class(self.construction_stage, self.action_class)

    def _item6_item12_fields(self) -> Item6Item12Fields:
        """Items 6/12's derived fields (TOS Phase 4 plan §2 decision 4) —"""
        return derive_item6_item12(
            self.broker_scopes.active_scope,
            self.broker_scopes,
            self.instance_document,
            mock_generation_current=self.mock_generation_reader(),
        )

    def __call__(self, attempt: AttemptRequest) -> SendBoundaryContext | None:
        """Resolve this attempt's send-boundary context from the live flow"""
        construction = self.construction_stage.construction
        proof = self.proof_stage.proof
        if construction is None:
            return None

        self._yield_seq += 1

        item3 = self.currentness_assembler.item3_fields()

        approval_consumed, approval_digest = item14_fields_from_verdict(
            self.step4_recorder.last_verdict
        )
        permit_identity, commitment_current = item15_fields_from(
            self.flow_governor.last_permit, self.step9_recorder.last_verdict
        )

        egress_currentness_proof = self._issue_egress_currentness_proof(attempt)
        item16 = self.proof_issuer.item16_fields(attempt.attempt_id)
        item6item12 = self._item6_item12_fields()
        request_bytes_digest = self._resolve_request_bytes_digest(construction)

        context = send_boundary_context(
            attempt=attempt,
            construction=construction,
            conformance_proof=proof,
            reference=OrderingEvent(
                event_id=f"{self.continuity_id}-send-{self._yield_seq}",
                source_continuity_id=self.continuity_id,
                source_native_sequence=self._yield_seq,
            ),
            egress_request_for_command=functools.partial(
                self._egress_request_for_command,
                request_bytes_digest=request_bytes_digest,
            ),
            quorum_certificate_for_command=self._quorum_certificate_for_command,
            instrument_key=self.instrument_key,
            transport_nature=self.transport_nature,
            non_live_test_environment_token=self.environment_label,
            scope_environment=self.environment_label,
            evidence_environment=self.environment_label,
            environment_inherited=False,
            credential_route_inventory=self.credential_route_inventory,
            transmission_capability=self._reconstruct_transmission_capability(attempt),
            capability_nonce=self.step14_stage.nonce_for(attempt.attempt_id),
            action_flow_permit_nonce=(
                None
                if self.flow_governor.last_permit is None
                else self.flow_governor.last_permit.claim_nonce
            ),
            prior_claims=(),
            principal=self.principal,
            request_digest=attempt.attempt_id,
            venue_snapshot=self.venue_stage.last_snapshot,
            venue_policy=self.venue_stage.policy,
            venue_decision=self.venue_stage.last_decision,
            observed_session_phase=self.observed_session_phase_reader(),
            action_class=self._attempt_action_class(),
            order_shape=self.venue_stage.resolved_shape,
            venue_shape_constraints=self.venue_stage.shape_constraints,
            commitment_epoch_current=item3.commitment_epoch_current,
            broker_capability_profile=item6item12.broker_capability_profile,
            required_capability_set=item6item12.required_capability_set,
            broker_profile_version_current=(item6item12.broker_profile_version_current),
            **self._capability_scope_fields(),
            idempotency_proven=None,
            **self._egress_gate_stand_in_fields(construction, item6item12),
            approval_consumed_for_this_intent=approval_consumed,
            action_flow_permit_identity=permit_identity,
            action_flow_commitment_current=commitment_current,
            egress_currentness_proof=egress_currentness_proof,
            egress_currentness_result=item16.egress_currentness_result,
            authorized_coordinates=self.authorized_coordinates,
            capsule_egress_request_digest=request_bytes_digest,
            outbound_side=attempt_side(self.construction_stage, self.outbound_side),
            **self._deferred_mesh_fields(),
        )
        self.contexts += (context,)
        return context
