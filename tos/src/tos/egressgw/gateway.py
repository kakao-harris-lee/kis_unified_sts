"""The Broker Egress Gateway (design #34 §4) — ADR-002-002 §11.4 steps 15-19."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from tos.brokercap import (
    Admissibility,
    BrokerEnvironment,
    UncertainSendVerdict,
    capability_admissible,
    environment_binding_ok,
    mock_order_without_position_or_cash,
    same_order_retry_allowed,
    uncertain_send_policy,
)
from tos.canonical import CanonicalDecimal
from tos.cur import (
    broker_reachable_not_authority,
    proof_admissible,
    proof_structurally_complete,
    unknown_preserves_capacity,
)
from tos.egress import (
    ClaimObservation,
    RestrictiveLatchState,
    capability_and_permit_single_use,
    exact_binding_holds,
    monotonic_denial_no_revival,
)
from tos.egressgw._base import (
    EV_L1_PROVISIONAL_VERSION,
    ArtifactIntegrityError,
    CanonicalizationScheme,
    _positive,
    get_scheme,
)
from tos.egressgw.mesh import deferred_item_verdict, resolve_broker_applicability
from tos.egressgw.records import (
    GatewayEvidenceRecord,
    SendBoundaryContext,
    SendBoundaryVerification,
    VerifyItemVerdict,
    _verdict,
)
from tos.egressgw.seal import (
    OUTBOUND_COORDINATE_NAMES,
    SendSeal,
    build_send_seal,
    outbound_coordinates,
)
from tos.egressgw.venuefacts import venue_generation_item_verdict
from tos.egressgw.vocabulary import (
    ADMITTING_VERIFY_OUTCOMES,
    DEFERRED_ITEMS,
    SEND_VERIFY_ITEMS,
    BrokerApplicability,
    SendHaltReason,
    SendVerifyItem,
    VerifyOutcome,
)
from tos.engine import (
    AttemptRequest,
    CommitmentStep,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
    SendHandoff,
    StageOutcome,
    egress_currentness_verdict,
    transmission_capability_verdict,
)
from tos.ioc import ConformanceAxis, mutation_fence_holds
from tos.ordering import OrderingEvent

__all__ = [
    "OUTBOUND_COORDINATE_NAMES",
    "UNCERTAIN_RESULT_KINDS",
    "BrokerEgressGateway",
    "GatewayEvidenceSink",
    "NullGatewayEvidenceSink",
    "RecordingGatewayEvidenceSink",
    "SendAttemptLedger",
    "SendTransport",
    "outbound_binding_mismatch",
    "outbound_coordinates",
    "verify_send_boundary",
]


UNCERTAIN_RESULT_KINDS: frozenset[EgressResultKind] = frozenset(
    {EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT}
)


def _reachability_rejection_anchor() -> None:
    """Anchor cur's unconditional "reachability is never authority" rejection (§7 / §4.2)."""
    if broker_reachable_not_authority(True) is not False:
        raise ArtifactIntegrityError(
            "cur.broker_reachable_not_authority is no longer an unconditional rejection — the "
            "gateway's applicability resolution relies on reachability never establishing "
            "authority (ADR-002-024 §15:358; design #34 §7)"
        )
    if broker_reachable_not_authority(False) is not False:
        raise ArtifactIntegrityError(
            "cur.broker_reachable_not_authority is no longer an unconditional rejection"
        )


_reachability_rejection_anchor()


@runtime_checkable
class SendTransport(Protocol):
    """The injected step-18 transport port (design #34 §5.1 firewall seam)."""

    def send_once(
        self,
        attempt: AttemptRequest,
        *,
        instrument_key: InstrumentKey,
        coordinates: tuple[tuple[str, str | None], ...],
        quantity: CanonicalDecimal | None = None,
        price: CanonicalDecimal | None = None,
        side: str | None = None,
        reference: OrderingEvent = OrderingEvent(),
        seal_digest: str | None = None,
    ) -> EgressResultPayload:
        """Transmit the verified outbound exactly once and return the typed result."""
        ...


@runtime_checkable
class GatewayEvidenceSink(Protocol):
    """The injected provisional sink the gateway writes its step-19 records to (§4.6)."""

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Accept one gateway evidence record."""
        ...


class RecordingGatewayEvidenceSink:
    """An in-memory provisional sink that keeps every record in arrival order."""

    def __init__(self) -> None:
        """Create an empty sink."""
        self._records: list[GatewayEvidenceRecord] = []

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Append one record (arrival order is preserved)."""
        self._records.append(record)

    @property
    def records(self) -> tuple[GatewayEvidenceRecord, ...]:
        """Every record received so far, in arrival order."""
        return tuple(self._records)

    @property
    def kinds(self) -> tuple[str, ...]:
        """The record kinds in arrival order — the observable step ordering (§4.6)."""
        return tuple(record.kind for record in self._records)


class NullGatewayEvidenceSink:
    """A sink that discards records — for callers supplying their own observation path."""

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Discard the record."""


class SendAttemptLedger:
    """⚠ **NON-AUTHORITATIVE PROVISIONAL** single-use ledger (design #34 §4.6/§6)."""

    def __init__(self, prior_claims: tuple[ClaimObservation, ...] = ()) -> None:
        """Create the ledger over any injected already-recorded claims."""
        self._claims: list[ClaimObservation] = list(prior_claims)
        self._consumed_attempts: set[str] = set()

    @property
    def claims(self) -> tuple[ClaimObservation, ...]:
        """Every claim observation recorded so far (append-only)."""
        return tuple(self._claims)

    def attempt_consumed(self, attempt_id: str) -> bool:
        """Whether this exact attempt identity was already consumed."""
        return attempt_id in self._consumed_attempts

    def claim(
        self,
        *,
        attempt_id: str,
        capability_nonce: str | None,
        action_flow_permit_nonce: str | None,
        principal: str | None,
        request_digest: str | None,
    ) -> bool:
        """Consume the attempt identity and both nonces exactly once (fail-closed)."""
        if attempt_id in self._consumed_attempts:
            return False
        if not capability_and_permit_single_use(
            capability_nonce,
            action_flow_permit_nonce,
            tuple(self._claims),
            principal=principal,
            request_digest=request_digest,
        ):
            return False
        self._consumed_attempts.add(attempt_id)
        self._claims.append(
            ClaimObservation(
                nonce=capability_nonce,
                principal=principal,
                request_digest=request_digest,
            )
        )
        self._claims.append(
            ClaimObservation(
                nonce=action_flow_permit_nonce,
                principal=principal,
                request_digest=request_digest,
            )
        )
        return True


def verify_send_boundary(
    *,
    attempt: AttemptRequest,
    context: SendBoundaryContext,
) -> SendBoundaryVerification:
    """Run the RFC-002 §10.8:741-759 verify list for one attempt (design #34 §4.1)."""
    applicability = resolve_broker_applicability(context.transport_nature, context)
    verdicts: list[VerifyItemVerdict] = []
    for item in SEND_VERIFY_ITEMS:
        if item in DEFERRED_ITEMS:
            verdicts.append(deferred_item_verdict(item, applicability, context))
        else:
            verdicts.append(_ITEM_CHECKS[item](attempt, context, applicability))

    judged = tuple(verdicts)
    covered = {verdict.item for verdict in judged}
    if covered != set(SEND_VERIFY_ITEMS) or len(judged) != len(SEND_VERIFY_ITEMS):
        return SendBoundaryVerification(
            attempt_id=attempt.attempt_id,
            applicability=applicability,
            verdicts=judged,
            halt_reason=SendHaltReason.VERIFY_LIST_INCOMPLETE,
            detail=(
                "the verify list did not cover every item this gateway carries — an "
                "unevaluated item is a stop, never a skip (RFC-002 §10.8:761)"
            ),
        )
    for verdict in judged:
        if verdict.outcome not in ADMITTING_VERIFY_OUTCOMES:
            return SendBoundaryVerification(
                attempt_id=attempt.attempt_id,
                applicability=applicability,
                verdicts=judged,
                halt_item=verdict.item,
                halt_reason=(
                    SendHaltReason.VERIFY_ITEM_UNKNOWN
                    if verdict.outcome is VerifyOutcome.UNKNOWN
                    else SendHaltReason.VERIFY_ITEM_DENIED
                ),
                detail=verdict.reason,
            )
    if (
        applicability is BrokerApplicability.UNKNOWN
    ):  # pragma: no cover - defence in depth
        return SendBoundaryVerification(
            attempt_id=attempt.attempt_id,
            applicability=applicability,
            verdicts=judged,
            halt_reason=SendHaltReason.BROKER_APPLICABILITY_UNRESOLVED,
            detail="the transport's broker applicability was never established",
        )
    return SendBoundaryVerification(
        attempt_id=attempt.attempt_id,
        applicability=applicability,
        verdicts=judged,
        admitted=True,
    )


def _check_capability(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 1 — a valid and **unused** Transmission Capability (Realize; §10.8:743)."""
    del applicability
    item = SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY
    capability_verdict = transmission_capability_verdict(
        context.transmission_capability
    )
    if capability_verdict.outcome is not StageOutcome.ADMIT:
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=capability_verdict.reason
            or "no single-use Transmission Capability identity was issued",
        )
    if not capability_and_permit_single_use(
        context.capability_nonce,
        context.action_flow_permit_nonce,
        context.prior_claims,
        principal=context.principal,
        request_digest=context.request_digest,
    ):
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the capability / permit nonces are not provably claimed exactly once for this "
                "principal and request — a replay or a transplant (ADR-002-013 §11.2 step 17; "
                f"attempt {attempt.attempt_id})"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="single-use capability + permit nonces are unclaimed for this exact bind",
    )


def _mock_class_bound_to_profile(context: SendBoundaryContext) -> bool:
    """Option (a)'s profile-check skip, bound to the attached profile's OWN class."""
    profile = context.broker_capability_profile
    if profile is None or profile.environment_class is not (
        BrokerEnvironment.BROKER_SIMULATION
    ):
        return False
    if not mock_order_without_position_or_cash(context.capability_tuples):
        return False
    return all(
        capability_tuple.environment is profile.environment_class
        for capability_tuple in context.capability_tuples
    )


def _check_allowance(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 6 — allowed account / instrument / action class / max quantity (provisional; :748)."""
    del attempt
    item = SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY
    if applicability is not BrokerApplicability.NON_BROKER_SYNTHETIC:
        if not _mock_class_bound_to_profile(context):
            admissibility = capability_admissible(
                context.broker_capability_profile,
                None if context.action_class is None else context.action_class.value,
                context.required_capability_set,
                version_current=context.broker_profile_version_current,
            )
            if admissibility is not Admissibility.ADMISSIBLE:
                return _verdict(
                    item,
                    (
                        VerifyOutcome.UNKNOWN
                        if admissibility is Admissibility.REDUCED
                        else VerifyOutcome.DENIED
                    ),
                    reason=(
                        f"brokercap capability_admissible is {admissibility.value} for this "
                        "broker-resource-consuming send — a profile with no VERIFIED dimension "
                        "cannot authorize any action class (ADR-002-004 §1:32; design #34 §1.1-3)"
                    ),
                    native=admissibility,
                    native_value=admissibility.value,
                )
    elif not environment_binding_ok(
        context.evidence_environment,
        context.scope_environment,
        context.environment_inherited,
    ):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the evidence does not bind to the scope environment — sandbox / paper evidence "
                "never automatically establishes another environment's capability "
                "(BC-INV-009:223)"
            ),
        )
    if not _positive(context.account_instrument_action_allowed):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the account / instrument / action class allowance is not positively "
                "established — the caller is responsible for deriving this flag from the "
                "scope table + INSTANCE (Phase 4 plan §2 decision 4); this gate judges only "
                "the supplied flag's positivity (kernel round #2 §2 decision 4)"
            ),
        )
    if not _positive(context.max_quantity_within_allowance):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the maximum-quantity allowance is not positively established; the derived "
                "size's own bound is enclosed in the Authorized Construction Envelope "
                "(design #34 §3.1)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="account / instrument / action / quantity allowance held",
    )


def _check_venue_generations(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 12 — venue / session / account / broker-constraint generation currency."""
    del attempt, applicability
    return venue_generation_item_verdict(context)


def _check_construction(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Order Construction — the bound command exists and the proof fences its exact digest."""
    del attempt, applicability
    item = SendVerifyItem.ORDER_CONSTRUCTION
    construction = context.construction
    if construction is None or construction.command is None:
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason="no candidate Canonical Broker Command is bound to this send",
        )
    if not mutation_fence_holds(construction.command, context.conformance_proof):
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the Order Conformance Proof does not fence the exact command digest — a "
                "post-proof mutation is a new command identity and a new proof "
                "(ADR-002-020 §6.2 / §16:429)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="the bound command is present and the conformance proof fences its digest",
    )


def _check_currentness(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 16 — Currentness policy / vector / fence / latch / Egress Currentness Proof (Realize)."""
    del attempt, applicability
    item = SendVerifyItem.CURRENTNESS
    latch = monotonic_denial_no_revival(context.restrictive_latch_state, ())
    if latch is not RestrictiveLatchState.CLEAR:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the Local Restrictive Latch is DENY_LATCHED (or unknown, which is latched) — "
                "deny is monotonic and no recovery / reconnect / refresh event revives it "
                "(ADR-002-013 §13:393)"
            ),
            native=latch,
            native_value=latch.value,
        )
    proof = context.egress_currentness_proof
    if not proof_structurally_complete(proof):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason="the Egress Currentness Proof is structurally incomplete (ADR-002-024 §12)",
        )
    if not proof_admissible(proof):
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the Egress Currentness Proof is not admissible for one send — consumed, "
                "expired, non-CURRENT, or its latch is not positively CLEAR "
                "(ADR-002-024 §6.6)"
            ),
        )
    currentness = egress_currentness_verdict(context.egress_currentness_result, proof)
    if currentness.outcome is not StageOutcome.ADMIT:
        preserved = unknown_preserves_capacity(False, context.worst_credible_capacity)
        magnitude_unknown = context.worst_credible_capacity is None
        return _verdict(
            item,
            (
                VerifyOutcome.UNKNOWN
                if currentness.outcome is StageOutcome.UNKNOWN
                else VerifyOutcome.DENIED
            ),
            reason=(
                f"{currentness.reason or 'egress currentness did not admit'} — the "
                f"worst-credible capacity obligation {preserved!r} stays preserved and nothing "
                "is resubmitted (CUR-INV-011:183)"
            ),
            native_value=currentness.native_verdict_value,
            preserved_worst_credible_capacity=preserved,
            preserved_obligation_magnitude_unknown=magnitude_unknown,
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason=(
            "the Egress Currentness Proof is structurally complete, admissible for exactly one "
            "send, and CURRENT; the latch is positively CLEAR"
        ),
        native_value=currentness.native_verdict_value,
    )


def _check_actual_outbound(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 17 — conformance of the actual outbound representation (Realize, coordinates only)."""
    del attempt, applicability
    item = SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE
    construction = context.construction
    verdict_token = (
        None
        if construction is None or construction.conformance_result is None
        else str(construction.conformance_result.value)
    )
    if not exact_binding_holds(
        context.egress_request,
        context.quorum_commit_certificate,
        context.authorized_coordinates,
        verdict_token,
        context.capsule_egress_request_digest,
    ):
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the actual outbound representation does not bind exactly to the authorized "
                "coordinates, the capsule chain terminus, and the committed command digest "
                "(EGRESS-INV-004:155-157). Coordinate equality only — byte-level outbound "
                "reconstruction and route confinement are +Security (EGRESS-EV-003)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason=(
            "every egress coordinate equals its authorized value and the ioc verdict is "
            "CONFORMANT — coordinate equivalence only, byte reconstruction deferred"
        ),
    )


_ITEM_CHECKS = {
    SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY: _check_capability,
    SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY: _check_allowance,
    SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION: (
        _check_venue_generations
    ),
    SendVerifyItem.ORDER_CONSTRUCTION: _check_construction,
    SendVerifyItem.CURRENTNESS: _check_currentness,
    SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE: _check_actual_outbound,
}


def _check_dispatch_anchor() -> None:
    """Prove every non-deferred item has a named check (drift anchor, §4.1)."""
    expected = set(SEND_VERIFY_ITEMS) - DEFERRED_ITEMS
    if set(_ITEM_CHECKS) != expected:
        raise ArtifactIntegrityError(
            "the gateway's verify-item dispatch drifted from the non-deferred item set: "
            f"missing={sorted(expected - set(_ITEM_CHECKS))}, "
            f"surplus={sorted(set(_ITEM_CHECKS) - expected)} — an item with no check would be "
            "skipped (design #34 §4.1)"
        )


_check_dispatch_anchor()


def outbound_binding_mismatch(context: SendBoundaryContext) -> str | None:
    """Why the scalars about to cross the transport seam are not the constructed ones (MINOR-2)."""
    construction = context.construction
    if construction is None or construction.command is None:
        return (
            "no constructed command is bound to this send — the outbound scalars would be "
            "unbound values (design #34 §4.4)"
        )
    derivation = construction.derivation
    for label, outbound, constructed in (
        ("quantity", context.outbound_quantity, derivation.quantity),
        ("price", context.outbound_price, derivation.price),
    ):
        if outbound is None or constructed is None:
            return (
                f"the outbound {label} or the derived {label} is absent — an unbound economic "
                "scalar may not cross the transport seam (RFC-005 §7:211-213)"
            )
        if outbound != constructed:
            return (
                f"the outbound {label} {outbound} is not the derived {label} {constructed} — "
                "a substituted economic scalar is exactly the field substitution "
                "EGRESS-INV-004:155-157 forbids"
            )
    declared_side = construction.command.axis_value(ConformanceAxis.SIDE)
    if declared_side is None or context.outbound_side is None:
        return (
            "the command declares no SIDE axis, or no outbound side was bound — an undeclared "
            "side cannot authorize a side (ADR-002-020 §11:301)"
        )
    if declared_side != context.outbound_side:
        return (
            f"the outbound side {context.outbound_side!r} is not the side the command declares "
            f"({declared_side!r}) — a signed quantity or a route default may not silently flip "
            "a side (ADR-002-020 §11:301)"
        )
    request = context.egress_request
    command_digest = construction.command.canonical_digest
    if (
        request is None
        or request.canonical_command_digest is None
        or command_digest is None
    ):
        return (
            "the outbound egress request carries no command digest to compare against the "
            "compiled command (EGRESS-INV-004:155-157)"
        )
    if request.canonical_command_digest != command_digest:
        return (
            "the outbound egress request transmits a different command digest than the one "
            "step 2 compiled and step 11 fenced — the coordinates item 17 compared belong to "
            "another command (EGRESS-INV-004:155-157; ADR-002-020 §6.2)"
        )
    return None


def _item16_obligation(
    verification: SendBoundaryVerification,
) -> tuple[int | None, bool]:
    """Item 16's preserved-capacity obligation, independent of which item halted."""
    for verdict in verification.verdicts:
        if verdict.item is SendVerifyItem.CURRENTNESS:
            return (
                verdict.preserved_worst_credible_capacity,
                verdict.preserved_obligation_magnitude_unknown,
            )
    return None, False


class BrokerEgressGateway:
    """The Broker Egress Gateway — D-E1's ``Transmit`` implementation (design #34 §4)."""

    def __init__(
        self,
        *,
        contexts: (
            Mapping[str, SendBoundaryContext]
            | Callable[[AttemptRequest], SendBoundaryContext | None]
        ),
        transport: SendTransport | None,
        sink: GatewayEvidenceSink,
        ledger: SendAttemptLedger | None = None,
        scheme: CanonicalizationScheme | None = None,
    ) -> None:
        """Wire the gateway."""
        self._contexts = contexts
        self._transport = transport
        self._sink = sink
        self._ledger = ledger if ledger is not None else SendAttemptLedger()
        self._scheme = (
            scheme if scheme is not None else get_scheme(EV_L1_PROVISIONAL_VERSION)
        )
        self.results: tuple[EgressResultPayload, ...] = ()
        self.verifications: tuple[SendBoundaryVerification, ...] = ()

    @property
    def ledger(self) -> SendAttemptLedger:
        """The provisional single-use ledger this gateway consumes."""
        return self._ledger

    def _bound_context(self, attempt: AttemptRequest) -> SendBoundaryContext | None:
        """Resolve this attempt's send-boundary context (design #35 §3.1)."""
        contexts = self._contexts
        if isinstance(contexts, Mapping):
            return contexts.get(attempt.attempt_id)
        if callable(contexts):
            return contexts(attempt)
        return None

    def _halt(
        self,
        *,
        attempt_id: str,
        reason: SendHaltReason,
        detail: str | None,
        step: CommitmentStep,
        item: SendVerifyItem | None = None,
        preserved_worst_credible_capacity: int | None = None,
        preserved_obligation_magnitude_unknown: bool = False,
    ) -> SendHandoff:
        """Record a recorded-reason halt and refuse the hand-off (design #34 §4.2)."""
        self._sink.record(
            GatewayEvidenceRecord(
                kind="SEND_REFUSED",
                attempt_id=attempt_id,
                item=item,
                halt_reason=reason,
                detail=detail,
                step=step,
                preserved_worst_credible_capacity=preserved_worst_credible_capacity,
                preserved_obligation_magnitude_unknown=preserved_obligation_magnitude_unknown,
            )
        )
        return SendHandoff(accepted_for_transmission=None)

    def _seal_and_claim(
        self,
        *,
        attempt_id: str,
        attempt: AttemptRequest,
        context: SendBoundaryContext,
    ) -> tuple[SendSeal | None, SendHandoff | None]:
        """Build the pre-``SEND_STARTED`` seal, then claim its nonces (Phase 4 작업 6 §1.2)."""
        try:
            coordinates = outbound_coordinates(context)
            seal = build_send_seal(
                context=context,
                attempt=attempt,
                coordinates=coordinates,
                scheme=self._scheme,
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 - a seal fault precedes the claim entirely
            return None, self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.SEND_SEAL_UNCONSTRUCTABLE,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                detail=(
                    f"cannot build the pre-SEND_STARTED send seal: {type(exc).__name__}: "
                    f"{exc} — this happens before the step-16 claim, so nothing is consumed "
                    "(design #34 phase 4 작업 6 §1.2; absorbs the former "
                    "OUTBOUND_COORDINATE_DERIVATION_RAISED site)"
                ),
            )
        if not self._ledger.claim(
            attempt_id=attempt_id,
            capability_nonce=seal.capability_nonce,
            action_flow_permit_nonce=seal.action_flow_permit_nonce,
            principal=seal.claim_principal,
            request_digest=seal.claim_request_digest,
        ):
            return None, self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.SINGLE_USE_CLAIM_REFUSED,
                step=CommitmentStep.SEND_STARTED_DURABLE,
                detail=(
                    "the capability / permit claim was refused — a nonce is claimed exactly "
                    "once for this principal and request (ADR-002-013 §11.2 step 17)"
                ),
            )
        return seal, None

    def _record(
        self, *, kind: str, attempt_id: str, step: CommitmentStep, **fields: Any
    ) -> None:
        """Emit one evidence record, stamped with its :class:`~tos.engine.CommitmentStep`."""
        self._sink.record(
            GatewayEvidenceRecord(kind=kind, attempt_id=attempt_id, step=step, **fields)
        )

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Run send-boundary steps 15-19 for one bound attempt."""
        attempt_id = attempt.attempt_id
        context = self._bound_context(attempt)
        if context is None:
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.CONTEXT_MISSING,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                detail=(
                    "no send-boundary context is bound to this attempt — the verify list's "
                    "facts are missing, and a missing required fact is a rejection "
                    "(RFC-002 §10.8:761)"
                ),
            )
        if context.instrument_key is None:
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.CONTEXT_MISSING,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                detail=(
                    "the send-boundary context carries no instrument key — the send's scope is "
                    "a required fact, and a missing required fact is a rejection "
                    "(RFC-002 §10.8:761)"
                ),
            )
        if self._ledger.attempt_consumed(attempt_id):
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.ATTEMPT_ALREADY_CONSUMED,
                step=CommitmentStep.SEND_STARTED_DURABLE,
                detail=(
                    "this attempt identity was already consumed — the same (proof, permit, "
                    "coordinate) triple content-addresses to the same attempt, so a repeat is a "
                    "blind resubmission and is refused. A retry is a NEW attempt with a new "
                    "permit and a new currentness proof (RFC-005 §11:326-328; §12:362 item 6)"
                ),
            )

        verification = verify_send_boundary(attempt=attempt, context=context)
        self.verifications += (verification,)
        for verdict in verification.verdicts:
            self._record(
                kind="VERIFY_ITEM",
                attempt_id=attempt_id,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                item=verdict.item,
                outcome=verdict.outcome,
                applicability=verification.applicability,
                detail=verdict.reason,
            )
        if verification.admitted is not True:
            (
                preserved_worst_credible_capacity,
                preserved_obligation_magnitude_unknown,
            ) = _item16_obligation(verification)
            return self._halt(
                attempt_id=attempt_id,
                reason=verification.halt_reason or SendHaltReason.VERIFY_ITEM_UNKNOWN,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                detail=verification.detail,
                item=verification.halt_item,
                preserved_worst_credible_capacity=preserved_worst_credible_capacity,
                preserved_obligation_magnitude_unknown=preserved_obligation_magnitude_unknown,
            )

        mismatch = outbound_binding_mismatch(context)
        if mismatch is not None:
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                detail=mismatch,
            )

        seal, halted = self._seal_and_claim(
            attempt_id=attempt_id, attempt=attempt, context=context
        )
        if halted is not None:
            return halted
        assert seal is not None

        self._record(
            kind="SEND_SEALED",
            attempt_id=attempt_id,
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            applicability=verification.applicability,
            send_seal=seal,
            detail=(
                "the pre-SEND_STARTED SendSeal — step 18's sole input source (Phase 4 작업 "
                "6, design §1.2); recorded BEFORE SEND_STARTED and before the transport is "
                "ever called"
            ),
        )
        self._record(
            kind="SEND_STARTED",
            attempt_id=attempt_id,
            step=CommitmentStep.SEND_STARTED_DURABLE,
            applicability=verification.applicability,
            send_seal_digest=seal.seal_digest,
            detail=(
                "⚠ provisional: recorded BEFORE the external call, preserving the claim / "
                "SEND_STARTED / first-byte order (RFC-005 §12:360; ADR-002-002 §11.4:606). "
                "Durability is NOT claimed — the Evidence Store runtime (ADR-002-016) is "
                "deferred (design #34 §4.6)"
            ),
        )

        self._record(
            kind="POTENTIALLY_LIVE_OBSERVED",
            attempt_id=attempt_id,
            step=CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
            detail=(
                "the reservation projection was advanced to POTENTIALLY_LIVE by D-E1 "
                "*before* this interface was called (engine sequencer, ADR-002-002 §11.4 "
                "step 17 / CommitmentStep.POTENTIALLY_LIVE_TRANSITION); the authoritative "
                "transition is RCL-owned and deferred. A crash from here on is "
                "deliberately treated as possibly-live (§11.4:611)"
            ),
        )

        if self._transport is None:
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.TRANSPORT_UNAVAILABLE,
                step=CommitmentStep.NETWORK_CALL,
                detail=(
                    "no transport is injected — an absent transport is a stop, never a skip, "
                    "and the attempt stays consumed so nothing is resent"
                ),
            )
        self._record(
            kind="NETWORK_CALL_ENTERED",
            attempt_id=attempt_id,
            step=CommitmentStep.NETWORK_CALL,
            send_seal_digest=seal.seal_digest,
            detail=(
                "the network call is about to be entered — recorded before send_once, not "
                "after, so a call that never returns is still auditable as 'entered'"
            ),
        )
        try:
            result = self._transport.send_once(
                attempt,
                instrument_key=seal.instrument_key,
                coordinates=seal.outbound_coordinates,
                quantity=seal.outbound_quantity,
                price=seal.outbound_price,
                side=seal.outbound_side,
                reference=seal.reference,
                seal_digest=seal.seal_digest,
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 - a failed call is not proof of "not sent"
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.TRANSPORT_RAISED,
                step=CommitmentStep.NETWORK_CALL,
                detail=(
                    f"the transport raised {type(exc).__name__}: {exc} — a missing "
                    "acknowledgement is NOT a non-acceptance (RFC-005 §11:322-323). The "
                    "reservation stays POTENTIALLY_LIVE, the attempt stays consumed, and "
                    "nothing is resubmitted"
                ),
            )

        try:
            attempt_identity_mismatch = result.attempt_id != attempt_id
        except (
            Exception
        ) as exc:  # noqa: BLE001 - an unreadable result is UNKNOWN, not "not sent"
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.RESULT_UNREADABLE,
                step=CommitmentStep.EVIDENCE_RECORD,
                detail=(
                    f"reading the transport result's identity raised {type(exc).__name__}: "
                    f"{exc} — the send already happened (single send_once call, never "
                    "repeated) and the reservation stays POTENTIALLY_LIVE; this is its own "
                    "recorded cause rather than a transport failure"
                ),
            )
        if attempt_identity_mismatch:
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.RESULT_ATTEMPT_IDENTITY_MISMATCH,
                step=CommitmentStep.EVIDENCE_RECORD,
                detail=(
                    f"the transport returned a result for {result.attempt_id!r} — a result is "
                    "applied only to the exact attempt it names, so a late or reordered result "
                    "can never transition another reservation (design #31 §2.1(ii))"
                ),
            )

        try:
            result_record = GatewayEvidenceRecord(
                kind="EGRESS_RESULT_RECORDED",
                attempt_id=attempt_id,
                send_seal_digest=seal.seal_digest,
                step=CommitmentStep.EVIDENCE_RECORD,
                detail=(
                    f"kind={result.kind.value} filled={result.filled_quantity!r} "
                    f"remaining={result.remaining_quantity!r} — a partial fill stays a partial "
                    "fill and the filled part is never re-requested (RFC-005 §11:338-339)"
                ),
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 - unreadable result fields, same conservative halt
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.RESULT_UNREADABLE,
                step=CommitmentStep.EVIDENCE_RECORD,
                detail=(
                    f"reading the transport result's fields raised {type(exc).__name__}: {exc} "
                    "while building the EGRESS_RESULT_RECORDED evidence — the send already "
                    "happened, is never repeated, and the reservation stays POTENTIALLY_LIVE"
                ),
            )

        self.results += (result,)
        self._sink.record(result_record)

        if result.kind in UNCERTAIN_RESULT_KINDS:
            self._record_uncertain(attempt_id, context)
        return SendHandoff(accepted_for_transmission=True, handoff_reference=attempt_id)

    def _record_uncertain(self, attempt_id: str, context: SendBoundaryContext) -> None:
        """Record brokercap's all-restrictive uncertain-send ladder (design #34 §5.4)."""
        ladder: UncertainSendVerdict = uncertain_send_policy()
        resend_allowed = same_order_retry_allowed(
            context.broker_capability_profile,
            idempotency_proven_for_identity_and_window=context.idempotency_proven,
        )
        self._sink.record(
            GatewayEvidenceRecord(
                kind="UNCERTAIN_SEND",
                attempt_id=attempt_id,
                step=CommitmentStep.EVIDENCE_RECORD,
                detail=(
                    f"no_retry={ladder.no_retry} "
                    f"no_capacity_release={ladder.no_capacity_release} "
                    f"no_assume_rejection={ladder.no_assume_rejection} "
                    f"start_reconciliation={ladder.start_reconciliation} "
                    f"enter_unknown_or_contained={ladder.enter_unknown_or_contained}; "
                    f"same_order_retry_allowed={resend_allowed}. A timeout never releases "
                    "capacity and an UNKNOWN is neither a rejection nor safe to retry "
                    "(ADR-002-004 §1:43; RFC-005 §11:325-328)"
                ),
            )
        )
