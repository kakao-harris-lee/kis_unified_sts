"""``ComposeContextResolver`` — the composition root's own ``SendBoundaryContext``
lazy resolver (design #40 §5 order 6 / slice plan §4 item 1).

This module is **compose-only glue**. It never judges anything itself: every
admissibility fact it hands the gateway is read either straight off a real
kernel/runtime artifact (structurally, never a caller's claim — 구조 파생 >
자기신고) or off a small number of **reported shims** documented below, each
of which exists only because the corresponding lane (P/Q/R) intentionally
does not retain the one extra bit compose needs and importing across lanes
is forbidden (slice plan §5 "서로의 패키지를 임포트하지 않는다").

**Reported shim 1 — :class:`VerdictRecorder`.** None of
``tos_runtime.authority``/``tos_runtime.risk`` retains the last
:class:`~tos.engine.records.StageVerdict` a Stage produced (each ``Stage`` is
a pure ``(StageRequest) -> StageVerdict`` callable per design #31 §4.1, with
no side-channel). Item 14 (``approval_consumed_for_this_intent`` /
``approval_intent_binding_digest``) and item 15's
``action_flow_commitment_current`` both need exactly that last verdict.
Rather than edit ``tos_runtime.authority.stages`` /
``tos_runtime.risk.ledger_stages`` (out of this lane's write surface, and it
would blur "a Stage is just a callable"), compose wraps the already-built
``Stage`` instances in a thin recording proxy that stores the verdict it
already computed — the real Stage's own judgement is completely unchanged,
compose only reads what it already decided.

**Reported shim 2 — :class:`RecordingAggregateRiskService` /
:class:`RecordingActionFlowGovernor`.** ``AggregateRiskDecisionStage`` /
``ActionFlowDecisionStage`` call ``.decide(...)`` on the real service and
wrap only the *digest*/*identity* of the returned decision into a
:class:`~tos.engine.records.StageVerdict` (design #31 §5.2's own structural-
binding-extraction discipline: the verdict never carries the native object).
But :meth:`~tos_runtime.risk.flow.ActionFlowGovernor.build_permit` needs the
**whole** :class:`~tos.afg.ActionFlowDecision`, not its digest. Compose
subclasses the two services (same public API, same firewall — R1 allowlist
unaffected) purely to retain the last decision it itself produced, so a
later stage in the SAME synchronous flow (design #31 §2.1: "one event is
processed to completion before the next") can read it back.

**Item 16 (Realize, lane R item 2) — issued honestly, not optimistically.**
:meth:`ComposeContextResolver._issue_egress_currentness_proof` issues one
:class:`~tos.cur.EgressCurrentnessProof` per attempt via
:class:`~tos_runtime.currentness.proof.EgressCurrentnessProofIssuer`. The
``result`` it passes is derived from
:meth:`~tos_runtime.currentness.vector.CurrentnessAssembler.is_complete`,
never hardcoded to ``CURRENT``. :func:`tos.cur.predicates.vector_complete`
requires the governing ``CurrentnessPolicy.required_dimensions`` to cover
``MANDATED_DIMENSION_FLOOR`` — every non-conditional
:class:`~tos.cur.DimensionKey` member — and then requires **every** one of
those required dimensions to be positively established in the assembled
vector. This compose root's own live services structurally establish
exactly four of them (``COMMIT_LOG``/``TRUSTWORTHY_TIME``/
``SAFETY_AUTHORITY``/``ACTION_FLOW``); no Phase 2 lane (P/Q/R/S) wires a
real runtime owner for the remaining 17. Per team-lead's explicit follow-up
guidance (2026-09-08), this composition supplies those 17 from **composition
config as explicit, named, operator-attested revisions**
(:mod:`tos_runtime.compose._pending_dimensions` — never a kernel-derived
judgement, and never fabricated silently: a still-null field refuses
composition at startup) so the vector genuinely completes and ``is_complete``
returns ``True`` — see the compose end-to-end test's
``TestPendingDimensionAttestationGatesCompleteness`` for the mechanical
proof that flipping one attestation to ``False`` makes the vector honestly
incomplete again, and ``tos_runtime.compose._pending_dimensions``'s own
module docstring for why supplying these 17 this way (rather than
fabricating them as kernel-derived) is the honest, fail-closed choice.
Reaching an actual transport hand-off ALSO requires step 4
(``INDEPENDENT_APPROVAL``) to admit, which it currently cannot (see
``_wiring.py``'s ``_decision_current_provider`` docstring and the compose
end-to-end test's ``xfail`` reasons on ``TestSyntheticEventDrivesTheChain``)
— that is a SEPARATE gap from this module's own item-16 wiring, which is
itself honest and complete.

Firewall (tools/tos_firewall_check.py R1, runtime scope): stdlib + ``tos.*``
+ ``tos_runtime.*`` only. No ``shared.*``.
"""

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
from tos.venue import (
    ActionClass,
    OrderAdmissibilityDecision,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
)

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    InstanceDocument,
    Item6Item12Fields,
    derive_item6_item12,
)
from tos_runtime.compose._pending_dimensions import (
    PendingDimensionSpec,
    stamp_pending_dimensions,
)
from tos_runtime.compose._request_digest import RequestBytesDigestSource
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.stages import TransmissionCapabilityStage
from tos_runtime.currentness.vector import CurrentnessAssembler
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.rcl.reservation_identity import scope_reservation_id
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
    # TYPE_CHECKING-only: _venue_phase.py imports ConstructionConfig from
    # _types.py, which imports THIS module for ComposeContextResolver — a
    # top-level import here would be circular. Postponed annotations (module
    # docstring's own `from __future__ import annotations`) mean the string
    # form below is all mypy needs.
    from tos_runtime.compose._venue_phase import VenuePhaseStage

__all__ = [
    "ComposeContextResolver",
    "RecordingActionFlowGovernor",
    "RecordingAggregateRiskService",
    "VerdictRecorder",
    "make_permit_provider",
    "record_egress_identity_observation",
]

#: W3.1 independent review MEDIUM-4 evidence kind — see
#: :func:`record_egress_identity_observation`.
_EGRESS_IDENTITY_OBSERVATION_KIND = "EGRESS_IDENTITY_OBSERVATION"


def record_egress_identity_observation(
    evidence_store: SqliteEvidenceStore,
    inventory: tuple[CredentialRouteInventoryEntry, ...],
) -> None:
    """W3.1 independent review MEDIUM-4 disposition: EGRESS_IDENTITY is reverted to
    pending (:mod:`tos_runtime.compose._pending_dimensions` — no dimension verdict is
    authored from partial predicate coverage). The ONE kernel predicate this
    composition CAN honestly evaluate —
    :func:`~tos.egress.predicates.credential_route_authority_disjoint`, over the
    composed (boot-time-static) credential-route inventory — is still worth recording,
    as an EVIDENCE-ONLY OBSERVATION, never a currentness verdict: this function writes
    it once at boot and never feeds it back into any admission decision.

    Moved here from ``_wiring.py`` (team-lead review follow-up, 2026-09-12) purely for
    that module's own size budget — no behavioural difference from having it there;
    :func:`~tos_runtime.compose._wiring._build_context_resolver` is still the one
    caller."""
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
    """Wraps one :class:`~tos.engine.sequencer.Stage`, remembering the last
    :class:`~tos.engine.records.StageVerdict` it returned (module docstring,
    "Reported shim 1"). Delegates every call unchanged — the wrapped Stage's
    own judgement is not altered in any way, only observed afterward.
    """

    def __init__(self, inner: Callable[[StageRequest], StageVerdict]) -> None:
        self._inner = inner
        self.last_verdict: StageVerdict | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        verdict = self._inner(request)
        self.last_verdict = verdict
        return verdict


class RecordingAggregateRiskService(AggregateRiskService):
    """:class:`~tos_runtime.risk.aggregate.AggregateRiskService`, additionally
    retaining the last :class:`~tos.are.AggregateRiskDecision` it produced
    (module docstring, "Reported shim 2"). No override of judgement — this
    subclass calls the parent's own ``decide`` unchanged and only stores its
    return value.
    """

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
    """:class:`~tos_runtime.risk.flow.ActionFlowGovernor`, additionally
    retaining the last :class:`~tos.afg.ActionFlowDecision` it produced and
    the last :class:`~tos.afg.ActionFlowPermit` compose built from it (module
    docstring, "Reported shim 2"). No override of judgement.
    """

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
    """Build the ``permit_provider`` callable
    :class:`~tos_runtime.risk.ledger_stages.AtomicCommitStage` (step 9) needs.

    Reads back :attr:`RecordingActionFlowGovernor.last_decision` (step 7's
    own output, this same synchronous flow) and, only when it is a positive
    ``GRANT``, calls the governor's own
    :meth:`~tos_runtime.risk.flow.ActionFlowGovernor.build_permit` — never
    inventing a permit for a non-GRANT decision (restrictive, never a
    fall-through admit).

    ``permit_generation_provider`` (``_rcl_tip_generation_provider``, an RCL
    log read) can raise ``StaleEpochRead``/``sqlite3.Error`` — re-review
    finding F2, 2026-09-08. Unlike step 6's ``AggregateRiskDecisionStage``,
    :class:`~tos_runtime.risk.ledger_stages.AtomicCommitStage` calls this
    ``permit_provider`` with NO enclosing ``try/except``, so a propagated
    failure here is caught at this exact call site and reported as "no
    permit available" (``None``) — the Stage already maps that to
    ``UNKNOWN`` (fail-closed), never a fabricated ``generation=0``.
    """

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
    """``(approval_consumed_for_this_intent, approval_intent_binding_digest)``
    derived structurally from step 4's recorded
    :class:`~tos.engine.records.StageVerdict` — mirrors
    ``tos_runtime.authority.stages.item14_fields``'s own field mapping
    (``ConsumeResult`` -> the same two fields) without needing the
    :class:`~tos_runtime.authority.iap.ConsumeResult` object itself, which
    ``IndependentApprovalStage.__call__`` does not expose (module docstring,
    "Reported shim 1").
    """
    if verdict is None:
        return None, None
    consumed = verdict.outcome is StageOutcome.ADMIT
    return consumed, (verdict.bound_digest if consumed else None)


def item15_fields_from(
    permit: ActionFlowPermit | None, step9_verdict: StageVerdict | None
) -> tuple[str | None, bool | None]:
    """``(action_flow_permit_identity, action_flow_commitment_current)`` —
    the identity comes from the live permit object (module docstring,
    "Reported shim 2"); ``commitment_current`` is step 9's own recorded
    ADMIT/DENY/UNKNOWN outcome (structurally, never a caller's claim)."""
    identity = None if permit is None else permit.permit_id
    commitment_current = (
        None if step9_verdict is None else step9_verdict.outcome is StageOutcome.ADMIT
    )
    return identity, commitment_current


@dataclass
class ComposeContextResolver:
    """The gateway's lazy ``contexts`` resolver (design #35 §3.1 (3)),
    assembling one :class:`~tos.egressgw.SendBoundaryContext` per attempt
    from the live P/Q/R + kernel construction artifacts.

    Every field below is either an injected, environment-scoped constant
    (transport nature, principal, credential-route inventory, authorized
    coordinates — the same kind of facts ``tests/slice/_slice_fixtures.py``
    injects for the kernel e2e test) or a live object read off one of the
    composed services, never rebuilt as a look-alike.
    """

    construction_stage: OrderConstructionStage
    proof_stage: ConformanceProofStage
    venue_stage: VenuePhaseStage
    step4_recorder: VerdictRecorder
    step9_recorder: VerdictRecorder
    step14_stage: TransmissionCapabilityStage
    flow_governor: RecordingActionFlowGovernor
    currentness_assembler: CurrentnessAssembler
    proof_issuer: EgressCurrentnessProofIssuer
    #: The 17 operator-attested pending currentness dimensions (team-lead
    #: follow-up guidance, 2026-09-08) — see
    #: :mod:`tos_runtime.compose._pending_dimensions`'s own module docstring
    #: for why these exist and what they honestly are (an interim operator
    #: sign-off, never a fabricated kernel-derived verdict).
    pending_dimension_specs: tuple[PendingDimensionSpec, ...]
    #: Item 12's three venue-half sub-facts (kernel round #3 §2 decision 4,
    #: replacing the single ``venue_session_account_facts_reader`` this
    #: resolver used to carry) — three zero-argument reads off the composed
    #: :class:`~tos_runtime.calendar.owner.SessionFactsOwner`
    #: (:mod:`tos_runtime.compose._session_wiring`), each evaluated fresh on
    #: every call (never cached here). The kernel's own
    #: :func:`~tos.egressgw.venuefacts.venue_session_account_facts_current`
    #: composes these three, replacing the retired
    #: ``tos_runtime.compose._egress_attestations`` operator attestation. Items
    #: 6/12's OTHER two fields are derived, not attested — see
    #: ``broker_scopes``/``instance_document`` below.
    session_facts_current_reader: Callable[[], bool | None]
    tradability_facts_current_reader: Callable[[], bool | None]
    account_facts_current_reader: Callable[[], bool | None]
    #: The runtime-configured Broker Scope table (TOS Phase 4 plan §2
    #: decision 4) — feeds :func:`~tos_runtime.brokercap.derive_item6_item12`
    #: for items 6/12, replacing two of the former egress attestations.
    broker_scopes: BrokerScopesConfig
    #: The Broker Capability Profile INSTANCE document bound to
    #: ``broker_scopes.active_scope`` (``None`` for a scope with no
    #: ``instance`` block, e.g. the SYNTHETIC default scope) — see
    #: :func:`~tos_runtime.brokercap.load_active_instance_document`.
    instance_document: InstanceDocument | None
    transport_nature: TransportNature
    environment_label: str
    principal: str
    credential_route_inventory: tuple[CredentialRouteInventoryEntry, ...]
    authorized_coordinates: EgressCoordinateSet
    #: Computes the ONE per-attempt request-bytes digest shared by
    #: ``EgressRequestRecord.request_bytes_digest`` and
    #: ``SendBoundaryContext.capsule_egress_request_digest`` (T2 lane A — see
    #: :mod:`tos_runtime.compose._request_digest`'s own module docstring for the gap this
    #: closes). Defaults to the unchanged capsule-terminus stand-in
    #: (:class:`~tos_runtime.compose._request_digest.CapsuleStandInDigest`) at every call site
    #: today (:mod:`tos_runtime.compose._wiring`); a later lane injects
    #: :class:`~tos_runtime.compose._request_digest.KisWireCodecDigest`.
    request_bytes_digest_source: RequestBytesDigestSource
    outbound_side: str
    action_class: ActionClass
    #: TOS Phase 5 W5 plan §2 decision 5 — a zero-argument read off the SAME
    #: :class:`~tos_runtime.calendar.owner.SessionFactsOwner` step 3's
    #: ``VenueConstraintStage`` reads (its own per-tick cache means both reads
    #: agree within one attempt), replacing the retired
    #: ``ConstructionConfig.observed_session_phase`` literal.
    observed_session_phase_reader: Callable[[], str | None]
    continuity_id: str
    instrument_key: InstrumentKey
    #: Item 4's deferred-mesh owner (Phase 5 W3-b, plan §2 decision 4) — the SAME
    #: composed :class:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService` the
    #: Coordinator's ``RuntimeCoordinatorPreconditions.authority_epoch_current`` already
    #: reads (:mod:`tos_runtime.compose._preconditions`), never a second service.
    authority_epoch_service: SafetyAuthorityEpochService
    #: Items 7/8/9/10's deferred egress-mesh fields (Phase 5 W3-b, plan §2 decision 8) —
    #: :attr:`~tos_runtime.compose._safety_wiring._SafetyMesh.deferred_fields`, evaluated
    #: fresh on every call (never cached), never a second judgement authored here.
    safety_mesh_deferred_fields: Callable[[], dict[str, Any]]
    #: Item 16's restrictive-latch owner (W3-c) — the composed
    #: :class:`~tos_runtime.compose._safety_wiring._SafetyMesh.latch`.
    latch: RestrictiveLatchOwner
    #: Item 16's worst-credible-capacity owner (W3-c) — built once ``instrument_key`` is
    #: known (:func:`~tos_runtime.compose._safety_wiring.build_capacity_owner`), unlike
    #: :attr:`latch` which needs the late-bound inbox cell instead.
    capacity: CapacityOwner
    #: The exact venue facts step 3 folded — passed straight through to item 11
    #: rather than rebuilt, so item 11's re-fold cannot silently disagree with
    #: the fold ``VenueConstraintStage`` (step 3) already performed.
    venue_snapshot: VenueConstraintSnapshot | None = None
    venue_policy: VenueConstraintPolicy | None = None
    venue_decision: OrderAdmissibilityDecision | None = None

    contexts: tuple[SendBoundaryContext, ...] = field(default_factory=tuple)
    _yield_seq: int = 0
    #: Item 4's CLAIMED Safety Authority epoch, bound ONCE at construction time — never
    #: re-read per attempt (the same "claim fixed at composition, never re-derived"
    #: discipline :class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions`
    #: already documents for its own ``_bound_epoch``). Set in :meth:`__post_init__`.
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
            side=self.outbound_side,
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
        """The ONE per-attempt request-bytes digest, computed once and shared by both
        :meth:`_egress_request_for_command` (item 17's ``EgressRequestRecord.
        request_bytes_digest``) and :meth:`__call__`'s own ``send_boundary_context``
        ``capsule_egress_request_digest`` kwarg — the exact two fields the kernel's
        ``exact_binding_holds`` (``tos/src/tos/egress/predicates.py``) requires to agree
        (T2 lane A, plan §8 "설계 정정 ①").

        Reads the SAME per-attempt sources the kernel itself later seals: ``self.
        authorized_coordinates.account`` (-> ``SendSeal.account``, ``build_send_seal``'s
        ``_gather_seal_fields``), ``self.instrument_key.instrument`` (-> ``SendSeal.
        instrument_key.instrument``), and ``construction.derivation.quantity``/``.price`` (->
        ``SendBoundaryContext.outbound_quantity``/``.outbound_price`` — ``tos.egressgw.records.
        send_boundary_context`` reads these off this SAME ``construction`` object, via
        ``construction.derivation.quantity``/``.price``). A codec-based
        ``request_bytes_digest_source`` therefore digests EXACTLY the bytes ``SendSeal`` itself
        carries, never a look-alike.

        Returns ``None`` when the derivation produced no value, or when ``authorized_coordinates
        .account`` is unset (``EgressCoordinateSet.account: str | None`` — unlike
        ``InstrumentKey.instrument``, which is required/non-empty by construction, design #31
        §3.3). ``tos.egressgw.construction.construct_candidate_command`` only ever compiles a
        ``command`` when ``derivation.outcome is DerivationOutcome.DERIVED`` — the ONE case
        ``QuantityDerivation``'s own validator guarantees carries non-``None`` ``quantity``/
        ``price`` — so ``quantity``/``price`` being ``None`` here means ``construction.command``
        is also ``None`` (an early, un-compiled denial), which already makes
        :meth:`_egress_request_for_command` return ``None`` unconditionally (its own
        ``command_digest is None`` guard) regardless of this digest's value; likewise, an unset
        ``account`` already makes the ``EgressRequestRecord.issue(...)`` call inside
        :meth:`_egress_request_for_command` carry ``account=None``, which is refused there by
        the SAME fail-closed discipline every other absent authorized coordinate already gets.
        Returning ``None`` here is therefore honest — never a fabricated digest for values that
        do not exist — and has no effect on either attempt's outcome (``exact_binding_holds``
        already short-circuits ``False`` on an absent ``request``, independent of
        ``capsule_egress_request_digest``).
        """
        quantity = construction.derivation.quantity
        price = construction.derivation.price
        account = self.authorized_coordinates.account
        if quantity is None or price is None or account is None:
            return None
        # Independent review LOW-1: self.authorized_coordinates.account and
        # self.instrument_key.account are the SAME value at every compose root this codebase
        # wires today (tos_runtime.compose._wiring._build_context_resolver sets both from the
        # SAME construction.account) — a mutation swapping the account source below is
        # unfalsifiable through this class's own tests for that reason, not because the
        # distinction does not matter. The distinction review F2 actually cares about (account
        # is a SEALED outbound coordinate, never a custody-loaded value) is pinned one layer
        # down, at the codec (tos_runtime.transport.kis_mock.codec's own
        # test_account_is_the_seal_field_never_instrument_key_account).
        return self.request_bytes_digest_source(
            account=account,
            instrument=self.instrument_key.instrument,
            quantity=quantity,
            price=price,
        )

    def _quorum_certificate_for_command(
        self, command_digest: str | None
    ) -> QuorumCommitCertificate | None:
        # ⚠ provisional (item 17, R-RCL-F0): only the command-digest axis is
        # consumed — this compose root claims no quorum-runtime replication.
        #
        # ``membership_generation``, ``restore_generation``, ``writer_epoch``,
        # ``committed_revision``, and ``cluster_identity`` below are slice-#3
        # PROVISIONAL STAND-INS (review finding #5, 2026-09-09) — this
        # compose root has no real quorum-runtime replication yet, so there
        # is no live source to read them from. They are replaced by a
        # genuine issued QCC in Phase 5. None of the kernel's 17 items
        # compares them: ``exact_binding_holds``
        # (``tos/src/tos/egress/predicates.py``) checks only the QCC's
        # *command* digest against the request record, never these fields —
        # so, unlike ``egress_generation`` below, leaving them as fixed
        # stand-ins is not currently load-bearing.
        #
        # ``egress_generation`` is DIFFERENT: it is one of the
        # ``EgressCoordinateSet`` authorized-coordinate values the seal now
        # makes load-bearing (``SendSeal.egress_generation``,
        # ``outbound_coordinates``, ``seal_digest``), and
        # ``authorized_coordinates.egress_generation`` is operator-configured
        # (``tos_runtime.compose._egress_coordinates``). A second hardcoded
        # ``1`` here used to silently drift from a non-default configured
        # value with nothing to catch it. Read it from the SAME config value
        # instead of a second literal.
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
        """Item 1's ``transmission_capability`` object (reported seam, never
        edited into lane R's ``currentness/stages.py``): step 14's
        ``TransmissionCapabilityStage`` builds + durably commits a real
        :class:`~tos.rcl.TransmissionCapability` internally, but exposes
        only its nonce (:meth:`~tos_runtime.currentness.stages.
        TransmissionCapabilityStage.nonce_for`) — there is no public
        accessor for the object itself.

        This reconstructs a capability with the SAME identity formula step
        14 uses (``f"cap-{attempt.attempt_id}"``) and the SAME already-
        durably-committed nonce, epoch, and scope facts this resolver
        already holds or can independently re-read from the log — never a
        fabricated identity. It is safe for
        ``tos.engine.adapters.transmission_capability_verdict`` (item 1's
        only consumer of this object), which admits on ``capability_id``
        presence alone and does not compare digests against a second
        source; ``capability_and_permit_single_use`` (item 1's OTHER half)
        checks the nonce independently, via ``context.capability_nonce``,
        not through this object. Reaches into
        ``TransmissionCapabilityStage``'s private ``_log``/``_writer_epoch``/
        ``_scheme`` attributes — reported, not a public seam either lane
        R or this module invented cleanly.

        Returns:
            The reconstructed capability, or ``None`` when step 14 issued
            no nonce for this attempt (never fabricated).
        """
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
            reservation_identity=scope_reservation_id(
                self.instrument_key.account, self.instrument_key.instrument
            ),
            attempt_identity=attempt.attempt_id,
            account_scope=self.instrument_key.account,
            instrument_scope=self.instrument_key.instrument,
            side_action_scope=self.outbound_side,
            ledger_epoch=view.epoch,
            bound_reservation_revision=view.last_seq,
        )
        assert isinstance(capability, TransmissionCapability)
        return capability

    def _issue_egress_currentness_proof(
        self, attempt: AttemptRequest
    ) -> EgressCurrentnessProof | None:
        """Item 16 (Realize, lane R item 2): two-pass currentness vector
        assembly + honest proof issuance.

        HIGH-2 fix (independent review of 39dd3993): the issuer itself
        derives ``result`` from its own injected ``is_complete`` (== this
        assembler's ``is_complete``, wired at compose time — see
        ``tos_runtime.compose.root``) — this resolver never computes
        ``vector_complete``/``currentness_result`` itself, so it cannot
        drift from what the issuer actually checks.

        Two-pass assemble (team-lead follow-up guidance, 2026-09-08): the
        first pass gets a REAL ``CurrentnessRevision`` this process's own
        owned dimensions actually sit at (never re-derived from the RCL
        log's own internal revision formula, which stays private to
        ``CurrentnessAssembler.assemble``); the pending dimensions are then
        stamped with that SAME revision (``single_revision_consistent``
        requires every dimension to share exactly one) and the second pass
        folds them in via the shipped ``extra_dimensions`` seam.

        Returns ``None`` only when the base vector itself is not yet
        assemblable (no owned dimension has produced a revision yet) —
        never a fabricated proof.
        """
        base_vector = self.currentness_assembler.assemble()
        if base_vector is None or base_vector.currentness_revision is None:
            return None
        pending_dimensions = stamp_pending_dimensions(
            self.pending_dimension_specs,
            at_revision=base_vector.currentness_revision,
        )
        vector = self.currentness_assembler.assemble(
            extra_dimensions=pending_dimensions
        )
        if vector is None:
            return None
        # §12 line 307-313 (tos.cur.predicates.proof_structurally_complete):
        # bound_generations must be non-empty -- structurally derived from
        # the SAME assembled vector's own per-dimension bound generations
        # (never invented), one entry per dimension that carries one.
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
        """Items 6/12/16's ``SendBoundaryContext`` stand-in fields.

        ``account_instrument_action_allowed`` / ``broker_constraint_generation_current``
        (items 6/12) are STRUCTURALLY DERIVED (TOS Phase 4 plan §2 decision
        4) via :func:`~tos_runtime.brokercap.derive_item6_item12`, never an
        attestation any more — see :meth:`_item6_item12_fields`.
        Item 12's three venue-half sub-facts (kernel round #3 §2 decision 4,
        superseding TOS Phase 5 W5 plan §2 decision 3's single pre-composed
        field) are now real runtime-owner reads too
        (:attr:`session_facts_current_reader` /
        :attr:`tradability_facts_current_reader` /
        :attr:`account_facts_current_reader` —
        :class:`~tos_runtime.calendar.owner.SessionFactsOwner`, replacing the
        retired ``tos_runtime.compose._egress_attestations`` operator
        attestation); the kernel's own
        :func:`~tos.egressgw.venuefacts.venue_session_account_facts_current`
        composes them, never this compose layer. ``restrictive_latch_state`` /
        ``worst_credible_capacity`` (item 16) are Phase 5 W3 real runtime
        owners too (:mod:`tos_runtime.safety.latch`, plan §2 decision 6) —
        never an attestation any more; see :attr:`latch` / :attr:`capacity`.
        ``max_quantity_within_allowance`` is the one exception: it HAS a real
        Phase 2 producer (step 2's own
        ``CandidateConstruction.no_silent_widening_ok``) and is derived
        from that live value instead of an attestation or a derivation."""
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
        """Items 4/5/7/8/9/10's ``SendBoundaryContext`` deferred-mesh fields (Phase 5
        W3-b, plan §2 decision 4 — kernel round #2 §2 decision 2's closed item↔field
        table: ``True`` ⇒ SATISFIED, ``False`` ⇒ DENIED, ``None`` ⇒ UNKNOWN, the
        kernel judges positivity only).

        Item 4 (``safety_authority_epoch_current``) is the only one this composition
        can honestly supply today: the Safety Authority epoch service's own
        :meth:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService.epoch_current`,
        checked against :attr:`_bound_authority_epoch` — the claim fixed ONCE at this
        resolver's construction, never re-derived per attempt (same discipline as
        :class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions`'s
        own ``_bound_epoch``) — never a second currentness/authorization comparison
        authored here.

        Items 7/8/9/10 come from :attr:`safety_mesh_deferred_fields` — the four W3-a1/a2
        safety-mesh services' own ``clear().clear`` (:mod:`tos_runtime.compose
        ._safety_wiring`'s own ``build_safety_mesh``), evaluated fresh on every call.

        Item 5 (``live_scope_valid``) is deliberately ABSENT (never a key in the
        returned dict, so ``send_boundary_context`` leaves it at its own ``None``
        default) — it stays UNKNOWN per plan §2 decision 4's operator confirmation ③
        (a), Phase 5's own committed posture until a live authorization runtime exists.
        """
        return {
            "safety_authority_epoch_current": self.authority_epoch_service.epoch_current(
                self._bound_authority_epoch
            ),
            **self.safety_mesh_deferred_fields(),
        }

    def _item6_item12_fields(self) -> Item6Item12Fields:
        """Items 6/12's derived fields (TOS Phase 4 plan §2 decision 4) —
        the ONE call site :meth:`_egress_gate_stand_in_fields` and
        :meth:`__call__` both read from, so the two consumers can never
        drift from each other's view of the same active scope."""
        return derive_item6_item12(
            self.broker_scopes.active_scope, self.broker_scopes, self.instance_document
        )

    def __call__(self, attempt: AttemptRequest) -> SendBoundaryContext | None:
        """Resolve this attempt's send-boundary context from the live flow
        artifacts (design #35 §3.1). Returns ``None`` (an absent required
        fact, RFC-002 §10.8:761) when step 2/step 11 produced nothing yet."""
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
        # T2 lane A: ONE digest, computed once, shared by egress_request_for_command below
        # (item 17's EgressRequestRecord.request_bytes_digest) and the
        # capsule_egress_request_digest kwarg further down — see
        # _resolve_request_bytes_digest's own docstring.
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
            venue_snapshot=self.venue_snapshot,
            venue_policy=self.venue_policy,
            venue_decision=self.venue_decision,
            observed_session_phase=self.observed_session_phase_reader(),
            action_class=self.action_class,
            order_shape=self.venue_stage.resolved_shape,
            venue_shape_constraints=self.venue_stage.shape_constraints,
            commitment_epoch_current=item3.commitment_epoch_current,
            # Items 6/12 (TOS Phase 4 plan §2 decision 4): the three
            # broker-reaching-admissibility fields the kernel gateway's own
            # capability_admissible(...) call consumes — derived from the
            # SAME active-scope/INSTANCE judgement as the two stand-in
            # fields below (_item6_item12_fields, one call site).
            broker_capability_profile=item6item12.broker_capability_profile,
            required_capability_set=item6item12.required_capability_set,
            broker_profile_version_current=(item6item12.broker_profile_version_current),
            idempotency_proven=None,
            # Items 6/12/16 stand-ins: real runtime owners now (item 12 --
            # tos_runtime.calendar.owner.SessionFactsOwner, TOS Phase 5 W5;
            # item 16 -- tos_runtime.safety.latch, TOS Phase 5 W3), except
            # max_quantity_within_allowance which HAS a real Phase 2 producer
            # (step 2's own CandidateConstruction.no_silent_widening_ok).
            **self._egress_gate_stand_in_fields(construction, item6item12),
            approval_consumed_for_this_intent=approval_consumed,
            action_flow_permit_identity=permit_identity,
            action_flow_commitment_current=commitment_current,
            egress_currentness_proof=egress_currentness_proof,
            egress_currentness_result=item16.egress_currentness_result,
            authorized_coordinates=self.authorized_coordinates,
            capsule_egress_request_digest=request_bytes_digest,
            outbound_side=self.outbound_side,
            **self._deferred_mesh_fields(),
        )
        self.contexts += (context,)
        return context
