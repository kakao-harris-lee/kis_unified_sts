"""The Broker Egress Gateway (design #34 §4) — ADR-002-002 §11.4 steps 15-19.

This is the object D-E1's ``Transmit`` slot (``engine/sequencer.py:104-116``) was left open for.
It satisfies ``(AttemptRequest) -> SendHandoff`` and runs, in the ADR's own order:

* **step 15** (:class:`~tos.engine.CommitmentStep.SEND_BOUNDARY_VERIFICATION`,
  :func:`verify_send_boundary`) — the RFC-002 §10.8:741-759 17-item verify list, then (still
  step 15's own output, Phase 3 wave 3 KW3-GW — the closed 19-step
  :class:`~tos.engine.CommitmentStep` enum gains no "step 15½" member for this)
  :func:`~tos.egressgw.seal.build_send_seal` builds the one immutable pre-``SEND_STARTED``
  :class:`~tos.egressgw.seal.SendSeal`. A seal-construction failure halts under
  ``SEND_SEAL_UNCONSTRUCTABLE``, stamped step 15, **before** anything is claimed;
* **step 16** (``SEND_STARTED_DURABLE``) — the single-use capability / permit claim (sourced
  from the seal alone) and the ``SEND_STARTED`` record, written **before** the transport is
  called (RFC-005 §12:360 claim / ``SEND_STARTED`` / first-byte ordering); the ``SEND_SEALED``
  record itself is stamped step 15, not 16, since it is step 15's own artifact;
* **step 17** (``POTENTIALLY_LIVE_TRANSITION``) — the ``POTENTIALLY_LIVE`` projection is
  *observed*, not performed: D-E1's sequencer already advanced it before calling this interface
  (``sequencer.py:531``), and the authoritative transition is RCL's (deferred);
* **step 18** (``NETWORK_CALL``) — a ``NETWORK_CALL_ENTERED`` write-ahead record immediately
  before delegation to the **injected** transport (:class:`SendTransport`), with every argument
  read from the seal alone (Phase 4 작업 6 — the seal is step 18's sole input source, never a
  second, independent read of ``context``);
* **step 19** (``EVIDENCE_RECORD``) — the result recorded as provisional evidence and retained
  for ``EGRESS_RESULT`` re-injection.

Every :class:`~tos.egressgw.records.GatewayEvidenceRecord` this gateway emits is stamped with
the :class:`~tos.engine.CommitmentStep` it belongs to (Phase 3 wave 3 KW3-GW — a mutation-matrix
finding that the executable Send Boundary order was not auditable from evidence because ``kind``
alone carried no step identity). ``SEND_REFUSED`` is the one kind with no single fixed step: it
is emitted from whichever step's own check actually failed, so every ``_halt`` call site states
its own step explicitly.

Four structural seals carry the design's weight:

1. **The broker-applicability positive gate runs first** (design #34 §4.2, MAJOR-2). The six
   deferred safety-governance mesh items are *neither* silently skipped (fail-open) *nor*
   unconditionally denied (which would also block the synthetic path this slice runs). They are
   **required** — and therefore ``UNKNOWN``-denying — for a broker-reaching or risk-relevant-live
   send, and explicitly ``NOT_APPLICABLE`` only when the send is *positively established* as a
   synthetic non-broker one. An unresolved transport nature is conservatively broker-consuming.
   The justification is "**no broker route was reached**", never "no live scope was armed"
   (design #34 §4.7): a real paper-account API call is non-live **and** broker-resource-consuming,
   so it does not pass this gate either.
2. **Admission is positive membership in a closed set.** Every item must land in
   :data:`~tos.egressgw.vocabulary.ADMITTING_VERIFY_OUTCOMES`, the item set must be exactly the
   normative 17, and a missing item is a stop rather than a skip (RFC-002 §10.8:761). A failed
   verification returns ``SendHandoff(accepted_for_transmission=None)`` and calls no transport.
3. **No blind resubmit is unrepresentable, not merely unwritten** (design #34 §5.4/§6). The
   transport port has exactly one single-shot method; the gateway calls it exactly once and never
   inside a loop; and the provisional :class:`SendAttemptLedger` consumes the attempt identity and
   both nonces *before* the call, so a second gateway invocation for the same
   (proof, permit, coordinate) triple — which content-addresses to the same ``attempt_id`` — is
   refused. On an ``UNKNOWN`` / ``TIMEOUT`` outcome the gateway records brokercap's structurally
   all-restrictive ``uncertain_send_policy`` ladder and brokercap's ``same_order_retry_allowed``
   (``False`` for any unproven idempotency): no retry, no capacity release, no assumed rejection.
4. **The seal is step 18's sole input source, with zero exceptions** (Phase 4 작업 6, design
   §0/§1.2). Every argument the transport call needs — the coordinates, the outbound quantity /
   price / side, the instrument key, the attempt identity, and even the causal-ordering
   ``reference`` event — is copied onto one immutable :class:`~tos.egressgw.seal.SendSeal` *before*
   the step-16 claim, and step 18 reads only the seal, never ``context`` again. A substitution
   between the seal and the transport call is therefore structurally unrepresentable rather than
   merely untested (ADR-002-013 §12 "No security-relevant field may be supplied or changed
   downstream after the proof comparison"; design §0 makes the seal the *only* source, not only
   the source for the fields that happen to be security-relevant).

⚠ **Honest scope (design #34 §1.1 — closes no EV).** Six of the seventeen items are verified by
shipped predicates over *structure and coordinates*; five are non-authoritative provisional
stand-ins; six are deferred. ``SEND_STARTED`` durability, the RCL atomic claim / consume, the QCC
quorum, byte-level outbound reconstruction, route confinement, and real credential-inventory
enumeration are **not** claimed here. Passing this gate is not evidence of currentness, QCC,
single-use, or credential isolation acceptance.

**``tos.egress`` is consumed, never encroached upon** (design #34 §0.3/§11-3): every egress
symbol used here is imported and called; no egress kernel behaviour is re-authored.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #34 §0.3). No clock, no RNG, **no
network** — the network lives beyond the injected transport port, outside ``tos/`` (design #34
§5.1). ``tos.brokeradapter`` is deliberately **absent** from this package's import closure: the
transport arrives by injection through a structural :class:`SendTransport` port, exactly as D-E1
reaches this gateway through its own ``Transmit`` port.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from tos.brokercap import (
    Admissibility,
    UncertainSendVerdict,
    capability_admissible,
    environment_binding_ok,
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
    credential_route_authority_disjoint,
    exact_binding_holds,
    monotonic_denial_no_revival,
)
from tos.egressgw._base import (
    EV_L1_PROVISIONAL_VERSION,
    ArtifactIntegrityError,
    CanonicalizationScheme,
    get_scheme,
)
from tos.egressgw.construction import fold_venue_admissibility
from tos.egressgw.records import (
    GatewayEvidenceRecord,
    SendBoundaryContext,
    SendBoundaryVerification,
    TransportNature,
    VerifyItemVerdict,
)
from tos.egressgw.seal import (
    OUTBOUND_COORDINATE_NAMES,
    SendSeal,
    build_send_seal,
    outbound_coordinates,
)
from tos.egressgw.vocabulary import (
    ADMITTING_VERIFY_OUTCOMES,
    DEFERRED_ITEMS,
    PROVISIONAL_ITEMS,
    REALIZED_ITEMS,
    SEND_VERIFY_ITEMS,
    BrokerApplicability,
    SendHaltReason,
    SendVerifyItem,
    VerifyDisposition,
    VerifyOutcome,
    verify_item_number,
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
from tos.ioc import ConformanceAxis, ConformanceResult, mutation_fence_holds
from tos.ordering import OrderingEvent
from tos.venue import OrderAdmissibilityResult

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
    "resolve_broker_applicability",
    "verify_send_boundary",
]


#: The two outcome kinds whose fate is genuinely unknown (RFC-005 §11:322-328): a missing
#: acknowledgement is **not** a non-acceptance, and neither is safe to retry.
UNCERTAIN_RESULT_KINDS: frozenset[EgressResultKind] = frozenset(
    {EgressResultKind.UNKNOWN, EgressResultKind.TIMEOUT}
)


def _reachability_rejection_anchor() -> None:
    """Anchor cur's unconditional "reachability is never authority" rejection (§7 / §4.2).

    ``broker_reachable_not_authority`` (ADR-002-024 §15:358) is an unconditional ``False``: a
    reachable broker never establishes send authority. This gate *relies* on that — the
    applicability resolution reads structural facts about credentials and routes, never "the
    broker answered". Checking the imported predicate at import time makes the reliance explicit
    and turns a future semantic drift into a loud failure rather than a silent one.

    Raises:
        ArtifactIntegrityError: If the rejection is no longer unconditional.
    """
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


# ===========================================================================
# ports — the injected transport and the provisional evidence sink
# ===========================================================================


@runtime_checkable
class SendTransport(Protocol):
    """The injected step-18 transport port (design #34 §5.1 firewall seam).

    ``tos.egressgw`` may not import ``tos.brokeradapter`` (design #34 §0.3 closure), so the
    adapter arrives through this **structural** port — the same shape D-E1 uses to reach this
    gateway. ``tos.brokeradapter.Transport`` declares the identical signature and satisfies it
    structurally; a signature drift between the two is caught by the seam canary in the tests.

    **Single shot by construction.** There is exactly one method, it takes one attempt, and it
    returns one result. There is no retry count, no idempotency key, no "resend" parameter, and
    no second method — so ``shared/execution/executor.py``'s three-attempt resend loop
    (Q-IDEMP-1, ``executor.py:225-232``) and its token-expiry resend wrapper (Q-IDEMP-2,
    ``executor.py:403``) are **unrepresentable** against this port, not merely unwritten
    (design #34 §5.4/§13). A retry is a *new attempt*: a new permit, a new currentness proof, and
    therefore a new content-addressed attempt identity through the whole 19-step flow.

    ``seal_digest`` (Phase 4 작업 6) is the sealed :class:`~tos.egressgw.seal.SendSeal`'s own
    digest, carried for the transport to echo back on its own evidence if it chooses — it is
    **not** a credential, session, or retry parameter (design #34 phase 4 작업 6 §1.3); the
    forbidden-parameter pins in ``tos.brokeradapter``'s test suite continue to police those.
    """

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
    """An in-memory provisional sink that keeps every record in arrival order.

    ⚠ Not an Evidence Store: no durability, no custody, no integrity anchor, no retention
    (ADR-002-016 deferred, design #34 §0.2-5). It exists so the send boundary's decisions and —
    critically — their **order** are observable, which is the whole demonstrable content of the
    slice (design #34 §1.1/§4.6).
    """

    def __init__(self) -> None:
        """Create an empty sink."""
        self._records: list[GatewayEvidenceRecord] = []

    def record(self, record: GatewayEvidenceRecord) -> None:
        """Append one record (arrival order is preserved).

        Args:
            record: The gateway evidence record.
        """
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
        """Discard the record.

        Args:
            record: The gateway evidence record (ignored).
        """


class SendAttemptLedger:
    """⚠ **NON-AUTHORITATIVE PROVISIONAL** single-use ledger (design #34 §4.6/§6).

    The send-side half of at-most-one (SAFE-021, RFC-005 §11:319-343). D-E1 owns the *retention*
    half — an unresolved ``POTENTIALLY_LIVE`` reservation denies an overlapping economic effect
    at the capacity stage (``sequencer.py:382-401``). This ledger owns the *consumption* half:
    the attempt identity and both nonces are consumed **before** the external call, so a repeat
    of the same (proof, permit, coordinate) triple — which content-addresses to the very same
    ``attempt_id`` (``sequencer.py:186-231``) — is refused rather than resent.

    **What this is not**: the real Risk Capacity Ledger. There is no linearizable transaction, no
    fencing epoch, and no compare-and-set here (ADR-002-002 §8.1:403 / §8.3:434 / §8.4:449), so
    this claims **no** concurrency property and closes no capacity EV (design #34 §4.6/§6).
    """

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
        """Consume the attempt identity and both nonces exactly once (fail-closed).

        Delegates the single-use judgement to egress
        :func:`~tos.egress.capability_and_permit_single_use` — the nonce ledger semantics are
        rcl's and egress's, and nothing about them is re-authored here.

        Args:
            attempt_id: The content-addressed attempt identity.
            capability_nonce: The Transmission Capability nonce.
            action_flow_permit_nonce: The Action Flow Permit nonce.
            principal: The exact runtime principal this claim binds.
            request_digest: The exact request digest this claim binds.

        Returns:
            ``True`` iff the claim succeeded; ``False`` leaves the ledger untouched.
        """
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


# ===========================================================================
# §4.2 — the broker-applicability positive gate (runs BEFORE the per-item gates)
# ===========================================================================


def resolve_broker_applicability(
    nature: TransportNature | None,
    context: SendBoundaryContext,
) -> BrokerApplicability:
    """Positively establish whether this send consumes a broker resource (design #34 §4.2).

    RFC-002 §10.8:741 triggers the verify list "before any risk-relevant **or**
    broker-resource-consuming transmission", so this — not live / non-live — is the axis that
    decides whether the deferred safety-governance mesh is required (design #34 MAJOR-1).

    Returns :attr:`~tos.egressgw.vocabulary.BrokerApplicability.NON_BROKER_SYNTHETIC` **only**
    when every one of the following positively holds:

    1. the declared :class:`~tos.egressgw.records.TransportNature` names a principal and carries
       ``reaches_broker is False``, ``credential_bearing is False``, ``route_bearing is False``,
       and ``risk_relevant_live is False`` — **explicit ``False``**, because a ``None`` is an
       unestablished nature and is conservatively broker-consuming (negative polarity, §4.2);
    2. that declaration is **structurally corroborated**: the transport principal is explicitly
       represented in the injected credential-route inventory holding neither a usable credential
       (``usable_credential is False``) nor a broker route (``broker_route is False``). A
       self-report alone never establishes it — the structural fact is that a synthetic transport
       does not constitute the ADR-002-013 §1 Final Egress Trust Boundary at all, and that is
       what the inventory shows (design #34 §1.1-1 / §4.5);
    3. egress :func:`~tos.egress.credential_route_authority_disjoint` holds over the whole
       inventory — an ∅ inventory is ``False`` there (disjointness unproven), so an empty
       inventory can never produce a synthetic verdict;
    4. the environment binds positively to the injected non-live-test scope token through
       brokercap :func:`~tos.brokercap.environment_binding_ok` (profile- and VERIFIED-independent
       — BC-INV-009 §4.7).

    Any positively-established broker-reaching or risk-relevant-live flag returns
    ``BROKER_RESOURCE_CONSUMING``; anything unestablished returns ``UNKNOWN``. **Both** make the
    deferred mesh required, so the fail-closed behaviour is identical — the distinction exists so
    the recorded evidence says which it was.

    Args:
        nature: The declared transport nature (``None`` ⇒ ``UNKNOWN``).
        context: The send-boundary context carrying the inventory and environment coordinates.

    Returns:
        The :class:`~tos.egressgw.vocabulary.BrokerApplicability` verdict.
    """
    if nature is None:
        return BrokerApplicability.UNKNOWN
    if (
        nature.reaches_broker is True
        or nature.credential_bearing is True
        or nature.route_bearing is True
        or nature.risk_relevant_live is True
    ):
        return BrokerApplicability.BROKER_RESOURCE_CONSUMING
    if not (
        nature.reaches_broker is False
        and nature.credential_bearing is False
        and nature.route_bearing is False
        and nature.risk_relevant_live is False
    ):
        return BrokerApplicability.UNKNOWN
    principal = nature.principal
    if principal is None or not principal.strip():
        return BrokerApplicability.UNKNOWN
    inventory = context.credential_route_inventory
    if not credential_route_authority_disjoint(inventory):
        return BrokerApplicability.UNKNOWN
    corroborated = False
    for entry in inventory:
        if entry.principal == principal:
            if entry.usable_credential is False and entry.broker_route is False:
                corroborated = True
            else:
                # The principal is represented but holds (or may hold) a credential or a route:
                # that is a broker-reaching transport whatever it declared about itself.
                return BrokerApplicability.BROKER_RESOURCE_CONSUMING
    if not corroborated:
        return BrokerApplicability.UNKNOWN
    if context.non_live_test_environment_token is None:
        return BrokerApplicability.UNKNOWN
    if context.scope_environment != context.non_live_test_environment_token:
        return BrokerApplicability.UNKNOWN
    if not environment_binding_ok(
        context.evidence_environment,
        context.scope_environment,
        context.environment_inherited,
    ):
        return BrokerApplicability.UNKNOWN
    return BrokerApplicability.NON_BROKER_SYNTHETIC


# ===========================================================================
# §4.1 — the 17-item verify list
# ===========================================================================


def _verdict(
    item: SendVerifyItem,
    outcome: VerifyOutcome,
    *,
    reason: str | None = None,
    native: object | None = None,
    native_value: str | None = None,
    preserved_worst_credible_capacity: int | None = None,
    preserved_obligation_magnitude_unknown: bool = False,
) -> VerifyItemVerdict:
    """Assemble one item verdict, deriving its disposition from the design §4.1 partition."""
    if item in REALIZED_ITEMS:
        disposition = VerifyDisposition.REALIZED_STRUCTURAL
    elif item in PROVISIONAL_ITEMS:
        disposition = VerifyDisposition.PROVISIONAL_STAND_IN
    else:
        disposition = VerifyDisposition.DEFERRED_APPLICABILITY
    return VerifyItemVerdict(
        item=item,
        disposition=disposition,
        outcome=outcome,
        reason=reason,
        native_verdict_type=None if native is None else type(native).__name__,
        native_verdict_value=native_value,
        preserved_worst_credible_capacity=preserved_worst_credible_capacity,
        preserved_obligation_magnitude_unknown=preserved_obligation_magnitude_unknown,
    )


def _positive(flag: bool | None) -> bool:
    """Positive-polarity read of an injected stand-in flag (``None`` / ``False`` ⇒ not admitted)."""
    return flag is True


def _deferred_item_verdict(
    item: SendVerifyItem, applicability: BrokerApplicability
) -> VerifyItemVerdict:
    """Judge one deferred safety-governance mesh item (design #34 §4.2 MAJOR-2).

    ``NOT_APPLICABLE`` **only** for a positively established synthetic non-broker send — a
    recorded positive judgement, never a silent skip. Everything else (a broker-reaching send, a
    risk-relevant-live send, or an unresolved nature) makes the item *required*, and because its
    owning runtime has not landed the required fact is unverifiable ⇒ ``UNKNOWN`` ⇒ deny
    (RFC-002 §10.8:741 trigger → :761 "reject … missing, stale, conflicting, or unverifiable").
    """
    if applicability is BrokerApplicability.NON_BROKER_SYNTHETIC:
        return _verdict(
            item,
            VerifyOutcome.NOT_APPLICABLE,
            reason=(
                f"item {verify_item_number(item)} is not applicable: the send was positively "
                "established as synthetic and non-broker-reaching, so no broker resource is "
                "consumed and no live scope is in play. The justification is 'no broker route "
                "was reached', NOT 'no live scope was armed' — a real paper-account API call is "
                "non-live and still broker-resource-consuming, and would be denied here "
                "(design #34 §4.2/§4.7)"
            ),
            native_value=applicability.value,
        )
    return _verdict(
        item,
        VerifyOutcome.UNKNOWN,
        reason=(
            f"item {verify_item_number(item)} is required for a "
            f"{applicability.value} send and its owning runtime has not landed — the required "
            "fact is unverifiable, which is a rejection (RFC-002 §10.8:741 → :761); "
            "design #34 §4.1 records this item as Deferred"
        ),
        native_value=applicability.value,
    )


def verify_send_boundary(
    *,
    attempt: AttemptRequest,
    context: SendBoundaryContext,
) -> SendBoundaryVerification:
    """Run the RFC-002 §10.8:741-759 17-item verify list for one attempt (design #34 §4.1).

    The broker-applicability gate (:func:`resolve_broker_applicability`) runs **first**, because
    it decides whether the six deferred mesh items are required or explicitly N/A. Then every
    item is judged in the normative order and the whole verification admits only when **all
    seventeen** land in :data:`~tos.egressgw.vocabulary.ADMITTING_VERIFY_OUTCOMES`.

    Args:
        attempt: The Coordinator's step-12 attempt request.
        context: Every injected fact the verify list consumes.

    Returns:
        The :class:`~tos.egressgw.records.SendBoundaryVerification`.
    """
    applicability = resolve_broker_applicability(context.transport_nature, context)
    verdicts: list[VerifyItemVerdict] = []
    for item in SEND_VERIFY_ITEMS:
        if item in DEFERRED_ITEMS:
            verdicts.append(_deferred_item_verdict(item, applicability))
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
                "the verify list did not cover the normative 17 items — an unevaluated item is "
                "a stop, never a skip (RFC-002 §10.8:761)"
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


# -- item 1 ------------------------------------------------------------------------------


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


# -- item 2 ------------------------------------------------------------------------------


def _check_identities(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 2 — matching intent and reservation identities (Realize; §10.8:744)."""
    del applicability
    item = SendVerifyItem.MATCHING_INTENT_AND_RESERVATION_IDENTITIES
    pairs = (
        ("attempt identity", attempt.attempt_id, context.reservation_attempt_id),
        (
            "conformance proof digest",
            attempt.conformance_proof_digest,
            context.reservation_conformance_proof_digest,
        ),
        (
            "Action Flow Permit identity",
            attempt.action_flow_permit_identity,
            context.reservation_action_flow_permit_identity,
        ),
    )
    for label, left, right in pairs:
        if left is None or right is None or not str(right).strip():
            return _verdict(
                item,
                VerifyOutcome.UNKNOWN,
                reason=f"the reservation carries no {label} to match against",
            )
        if left != right:
            return _verdict(
                item,
                VerifyOutcome.DENIED,
                reason=(
                    f"{label} mismatch between the attempt and the reservation — a result may "
                    "only ever be applied to the exact attempt it names (design #31 §2.1(ii))"
                ),
            )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="attempt, proof, and permit identities match the reservation exactly",
    )


# -- item 3 ------------------------------------------------------------------------------


def _check_commitment_epoch(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 3 — a current commitment epoch (⚠ **provisional** RCL stand-in; §10.8:745)."""
    del attempt, applicability
    item = SendVerifyItem.CURRENT_COMMITMENT_EPOCH
    if not _positive(context.commitment_epoch_current):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the commitment epoch is not positively current — ⚠ this is a NON-AUTHORITATIVE "
                "provisional stand-in; real epoch fencing is RCL's and is deferred "
                "(design #34 §4.1 item 3)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason=(
            "⚠ provisional stand-in: the commitment epoch is reported current. No linearizable "
            "ledger, fencing epoch, or CAS is claimed (design #34 §4.6)"
        ),
    )


# -- item 6 ------------------------------------------------------------------------------


def _check_allowance(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 6 — allowed account / instrument / action class / max quantity (provisional; :748).

    Two honest paths, split on the same axis §4.2 uses:

    * a **synthetic, non-broker** send routes through brokercap
      :func:`~tos.brokercap.environment_binding_ok`, which is profile- and VERIFIED-independent
      (BC-INV-009; design #34 §4.7) — that is what makes the non-live-test path admissible at all;
    * anything else must clear brokercap :func:`~tos.brokercap.capability_admissible`, which for a
      profile carrying zero ``VERIFIED`` dimensions is structurally ``PROHIBITED``
      (design #34 §1.1-3). The gateway therefore admits **no** live send, by construction rather
      than by policy.

    The allowance flags themselves are ⚠ provisional stand-ins: the approved Broker Capability
    Profile INSTANCE is P0-2-blocked (design #34 §4.1 item 6).
    """
    del attempt
    item = SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY
    if applicability is not BrokerApplicability.NON_BROKER_SYNTHETIC:
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
                "established — ⚠ provisional stand-in pending the P0-2 approved Profile INSTANCE"
            ),
        )
    if not _positive(context.max_quantity_within_allowance):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the maximum-quantity allowance is not positively established — ⚠ provisional "
                "stand-in; the derived size's own bound is enclosed in the Authorized "
                "Construction Envelope (design #34 §3.1)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="⚠ provisional stand-in: account / instrument / action / quantity allowance held",
    )


# -- item 11 -----------------------------------------------------------------------------


def _check_venue(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 11 — Venue Constraint Snapshot + Order Admissibility Decision binding (Realize; :753).

    RFC-002 §9.1:554 splits the roles: step 3 *produces* the non-authorizing decision, and the
    gateway *enforces* "the exact current result" here. This check therefore re-evaluates venue's
    own predicates against the current snapshot and additionally requires the issued decision to
    carry the same ``ADMISSIBLE`` result — a decision that disagrees with the current snapshot is
    stale, and staleness is a rejection (§10.8:761).
    """
    del attempt, applicability
    item = SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION
    if context.venue_decision is None:
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason="no Order Admissibility Decision is bound to this send",
        )
    current = fold_venue_admissibility(
        observed_session_phase=context.observed_session_phase,
        action_class=context.action_class,
        snapshot=context.venue_snapshot,
        policy=context.venue_policy,
        shape=context.order_shape,
        constraints=context.venue_shape_constraints,
    )
    if current is OrderAdmissibilityResult.UNKNOWN:
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason="venue admissibility is UNKNOWN — restrictive (ADR-002-019 §8:245)",
            native=current,
            native_value=current.value,
        )
    if current is not OrderAdmissibilityResult.ADMISSIBLE:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                f"the current venue result is {current.value}; a RESTRICTED_PROTECTIVE_ONLY "
                "path proceeds only through venue's own protective_label_no_bypass and this "
                "gate self-classifies nothing as protective (RFC-005 §12:371)"
            ),
            native=current,
            native_value=current.value,
        )
    if context.venue_decision.result is not OrderAdmissibilityResult.ADMISSIBLE:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the bound Order Admissibility Decision does not itself admit — the gateway "
                "enforces the exact current result and unions nothing (RFC-002 §9.1:554)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="the current venue result and the bound decision both admit exactly",
        native=current,
        native_value=current.value,
    )


# -- item 12 -----------------------------------------------------------------------------


def _check_venue_generations(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 12 — venue / session / account / broker-constraint generation currency (provisional)."""
    del attempt, applicability
    item = SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION
    if not _positive(context.venue_session_account_facts_current):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the venue / session / halt / tradability / account / margin / settlement facts "
                "are not positively current — ⚠ provisional stand-in (design #34 §4.1 item 12)"
            ),
        )
    if not _positive(context.broker_constraint_generation_current):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the broker-constraint generation is not positively current — ⚠ provisional; "
                "the versioned Profile is P0-2-blocked (RFC-002 §10.8:765)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="⚠ provisional stand-in: venue / account / broker-constraint generations current",
    )


# -- item 13 -----------------------------------------------------------------------------


def _check_construction(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 13 — Order Construction policy / envelope / command / proof / effect (Realize; :755)."""
    del attempt, applicability
    item = SendVerifyItem.ORDER_CONSTRUCTION
    construction = context.construction
    if construction is None or construction.command is None:
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason="no candidate Canonical Broker Command is bound to this send",
        )
    # ★ TOS-GAP-001: ``conformance_result`` is ``ConformanceResult | None`` — the
    # CandidateConstruction shape validator (records.py) now denies a *constructed* bundle from
    # carrying ``command is not None`` alongside a ``None`` verdict, but this verify item stays
    # defense-in-depth against any bundle that reaches the gateway some other way. An
    # unestablished (``None``) result is treated exactly like the native ``UNKNOWN`` value —
    # never a pass, never an ``AttributeError`` from a bare ``.value`` on ``None`` — so both
    # collapse to the same restrictive ``UNKNOWN`` outcome the design already assigns to a
    # native ``UNKNOWN`` (ADR-002-020 §14:374).
    if construction.conformance_result is None or (
        construction.conformance_result is ConformanceResult.UNKNOWN
    ):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "order conformance is UNKNOWN — denial (ADR-002-020 §14:374)"
                if construction.conformance_result is not None
                else "order conformance was never established — an absent result is UNKNOWN, "
                "never a pass (TOS-GAP-001)"
            ),
            native=construction.conformance_result,
            native_value=(
                None
                if construction.conformance_result is None
                else str(construction.conformance_result.value)
            ),
        )
    if construction.conformance_result is not ConformanceResult.CONFORMANT:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason="the bound command is NON_CONFORMANT to its approved intent",
            native=construction.conformance_result,
            native_value=str(construction.conformance_result.value),
        )
    # Same None/UNKNOWN-collapses-to-UNKNOWN discipline for the numerical-safety verdict — the
    # positive-admit polarity is "only CONFORMANT passes; UNKNOWN (native or absent) is UNKNOWN;
    # anything else (NON_CONFORMANT) is DENIED", matching the conformance_result branch above.
    if construction.numerical_result is None or (
        construction.numerical_result is ConformanceResult.UNKNOWN
    ):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "numerical safety is UNKNOWN — denial (ADR-002-020 §14:423)"
                if construction.numerical_result is not None
                else "numerical safety was never established — an absent result is UNKNOWN, "
                "never a pass (TOS-GAP-001)"
            ),
            native=construction.numerical_result,
            native_value=(
                None
                if construction.numerical_result is None
                else str(construction.numerical_result.value)
            ),
        )
    if construction.numerical_result is not ConformanceResult.CONFORMANT:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason="numerical safety is not CONFORMANT (ADR-002-020 §14:423)",
            native=construction.numerical_result,
            native_value=str(construction.numerical_result.value),
        )
    if construction.no_silent_widening_ok is not True:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the construction did not positively witness no-silent-widening "
                "(IOC-INV-006:177)"
            ),
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
        reason="policy / envelope / command / proof / effect are bound and CONFORMANT",
        native=construction.conformance_result,
        native_value=str(construction.conformance_result.value),
    )


# -- item 14 -----------------------------------------------------------------------------


def _check_approval(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 14 — Trading Approval consumption + Intent binding (⚠ provisional iap stand-in)."""
    del attempt, applicability
    item = SendVerifyItem.TRADING_APPROVAL
    if not _positive(context.approval_consumed_for_this_intent):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "no approval consumption is positively recorded for this intent — ⚠ provisional "
                "stand-in; no independent approver runtime exists (design #34 §4.1 item 14)"
            ),
        )
    intent = None if context.construction is None else context.construction.intent
    intent_digest = None if intent is None else intent.canonical_digest
    if (
        intent_digest is None
        or context.approval_intent_binding_digest is None
        or context.approval_intent_binding_digest != intent_digest
    ):
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the approval does not bind the exact Approved Intent Contract digest — an "
                "approval of a different intent is not an approval of this one"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="⚠ provisional stand-in: approval consumed and bound to this exact intent digest",
    )


# -- item 15 -----------------------------------------------------------------------------


def _check_action_flow(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 15 — Action Flow decision / RCL commitment / Permit (⚠ provisional afg stand-in)."""
    del applicability
    item = SendVerifyItem.ACTION_FLOW
    permit = context.action_flow_permit_identity
    if permit is None or not permit.strip():
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "no Action Flow Permit identity is bound — ⚠ provisional stand-in; no Action "
                "Flow Governor runtime exists (design #34 §4.1 item 15)"
            ),
        )
    if permit != attempt.action_flow_permit_identity:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the bound Action Flow Permit is not the one the attempt request binds "
                "(ADR-002-002 §11.3:599)"
            ),
        )
    if not _positive(context.action_flow_commitment_current):
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason="the Action Flow RCL commitment is not positively current — ⚠ provisional",
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason="⚠ provisional stand-in: Action Flow Permit bound to this exact attempt",
    )


# -- item 16 -----------------------------------------------------------------------------


def _check_currentness(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 16 — Currentness policy / vector / fence / latch / Egress Currentness Proof (Realize).

    Consumes cur's own predicates (``proof_structurally_complete`` / ``proof_admissible``) and
    D-E1's ``egress_currentness_verdict`` hand-off adapter — only ``CURRENT`` satisfies, and
    ``CURRENT`` itself grants no authority (ADR-002-024 §12:316). The egress-owned Local
    Restrictive Latch is resolved through egress's own monotonic resolver: once denied it never
    revives, and a ``None`` latch state is ``DENY_LATCHED`` (fail-closed).

    ⚠ The *facts* inside the Safety Currentness Vector are upstream owner submissions and are
    provisional / D-E2-dependent: this verifies the proof's **structure and coordinates**, and
    closes no CUR-EV (design #34 §4.3).

    The returned verdict's ``preserved_worst_credible_capacity`` is ``None`` on every branch but
    the final non-ADMIT one below (review round #1 finding #9): the latch and
    structurally-incomplete-proof branches compute no obligation at all, and the SATISFIED
    branch has nothing to preserve. On the non-ADMIT branch itself, the field carries a concrete
    number only when ``context.worst_credible_capacity`` was actually observed; otherwise
    ``preserved_obligation_magnitude_unknown`` is set instead (kernel round #1 review #4 —
    UNKNOWN is restrictive, CUR-INV-011:183).
    """
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


# -- item 17 -----------------------------------------------------------------------------


def _check_actual_outbound(
    attempt: AttemptRequest,
    context: SendBoundaryContext,
    applicability: BrokerApplicability,
) -> VerifyItemVerdict:
    """Item 17 — conformance of the actual outbound representation (Realize, coordinates only).

    RFC-005 §7:213 gives the Broker Adapter the actual-outbound comparison; egress
    :func:`~tos.egress.exact_binding_holds` is the shipped realization: every egress coordinate
    must equal the injected authorized value (EGRESS-INV-004:155-157 "No field may be substituted
    after validation"), the request-bytes digest must equal the capsule chain terminus, the QCC's
    command digest must equal the request's, and the injected ioc verdict must be ``CONFORMANT``.

    ⚠ **Over-realization boundary** (design #34 §4.4, egress ``predicates.py:356-359``): this is
    injected **coordinate equality plus the ioc verdict**. Byte-level outbound reconstruction,
    §10 route confinement, and §8 environment non-interchangeability are ``+Security``
    (EGRESS-EV-003, not-Phase-1). Nothing here claims the wire bytes were rebuilt and compared —
    on a synthetic transport the wire itself is synthetic — so the Q-WIRE-1 numeric-encoding
    asymmetry stays only *partially* sealed (design #34 §13).
    """
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


#: Item → check dispatch. Built from named functions (never a chain of ``if``) so a missing item
#: is a ``KeyError`` at the call site rather than a silently skipped verification.
_ITEM_CHECKS = {
    SendVerifyItem.VALID_UNUSED_TRANSMISSION_CAPABILITY: _check_capability,
    SendVerifyItem.MATCHING_INTENT_AND_RESERVATION_IDENTITIES: _check_identities,
    SendVerifyItem.CURRENT_COMMITMENT_EPOCH: _check_commitment_epoch,
    SendVerifyItem.ALLOWED_ACCOUNT_INSTRUMENT_ACTION_AND_MAX_QUANTITY: _check_allowance,
    SendVerifyItem.VENUE_SNAPSHOT_AND_ADMISSIBILITY_DECISION: _check_venue,
    SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION: (
        _check_venue_generations
    ),
    SendVerifyItem.ORDER_CONSTRUCTION: _check_construction,
    SendVerifyItem.TRADING_APPROVAL: _check_approval,
    SendVerifyItem.ACTION_FLOW: _check_action_flow,
    SendVerifyItem.CURRENTNESS: _check_currentness,
    SendVerifyItem.ACTUAL_OUTBOUND_CONFORMANCE: _check_actual_outbound,
}


def _check_dispatch_anchor() -> None:
    """Prove every non-deferred item has a named check (drift anchor, §4.1).

    Raises:
        ArtifactIntegrityError: If a non-deferred verify item has no check, or a check exists
            for a deferred item (which is judged by the applicability gate instead).
    """
    expected = set(SEND_VERIFY_ITEMS) - DEFERRED_ITEMS
    if set(_ITEM_CHECKS) != expected:
        raise ArtifactIntegrityError(
            "the gateway's verify-item dispatch drifted from the non-deferred item set: "
            f"missing={sorted(expected - set(_ITEM_CHECKS))}, "
            f"surplus={sorted(set(_ITEM_CHECKS) - expected)} — an item with no check would be "
            "skipped (design #34 §4.1)"
        )


_check_dispatch_anchor()


# ===========================================================================
# §4.6 / §5.3 — the gateway itself (D-E1 ``Transmit`` slot)
# ===========================================================================
#
# ``outbound_coordinates`` / ``OUTBOUND_COORDINATE_NAMES`` now live in
# :mod:`tos.egressgw.seal` (Phase 4 작업 6) — :func:`~tos.egressgw.seal.build_send_seal` needs
# the identical derivation this gateway calls, and a single definition is what keeps the two from
# drifting apart. Imported above and re-exported here so existing ``tos.egressgw.gateway`` /
# ``tos.egressgw`` call sites (including the test suite's monkeypatch of this module attribute)
# are unchanged.


def outbound_binding_mismatch(context: SendBoundaryContext) -> str | None:
    """Why the scalars about to cross the transport seam are not the constructed ones (MINOR-2).

    The verify list checks that a *conformant* construction exists (item 13) and that the egress
    **coordinates** equal their authorized values (item 17), but the economic scalars the gateway
    actually hands the transport — quantity, price, side — and the command digest the outbound
    request carries are a separate binding. Leaving them unchecked would make the seam's safety
    depend on whoever assembles the context wiring it consistently, which is precisely the
    "trust the caller" shape the series refuses (RFC-005 §7:213 gives the Broker Adapter the
    actual-outbound comparison; adversarial review MINOR-2).

    So every scalar is re-derived from the artifacts the gateway **already holds**:

    * ``outbound_quantity`` / ``outbound_price`` must equal the step-2
      :class:`~tos.egressgw.records.QuantityDerivation` values — not an independently supplied
      number that merely looks right;
    * ``outbound_side`` must equal the ``SIDE`` axis the compiled Canonical Broker Command
      **declares**, and both must be concrete: an undeclared side cannot authorize a side
      (ADR-002-020 §11:301 — direction / side / position effect are independent axes and a
      value may not be substituted for a missing one);
    * ``egress_request.canonical_command_digest`` must equal the compiled command's canonical
      digest, so the request whose coordinates item 17 compared is provably a request for
      *this* command (EGRESS-INV-004:155-157 "No field may be substituted after validation").

    Every comparison is a positive equality between two concrete values; a ``None`` on either
    side is a mismatch, never a skipped check (fail-closed).

    Args:
        context: The send-boundary context.

    Returns:
        ``None`` when every binding holds, else the recorded mismatch reason.
    """
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
    """Item 16's preserved-capacity obligation, independent of which item halted.

    All 17 verify items are always evaluated (design #34 §4.1), and only afterwards does the
    loop pick the **first** non-admitting one as ``halt_item``. Item 16's own verdict — and any
    obligation it authored — therefore exists regardless of which item that is. Transferring the
    obligation only when ``verification.halt_item is SendVerifyItem.CURRENTNESS`` was the
    reviewed fail-silent hole (independent review round #1, finding #1): when an earlier item
    (e.g. ``ORDER_CONSTRUCTION``) halted alongside a non-ADMIT item 16, item 16 still computed
    and stored the obligation on its own verdict, but the ``SEND_REFUSED`` evidence recorded
    ``None`` — and ``CapacityObligationRecorder`` no-ops on ``None``
    (``tos_runtime/rcl/obligation.py``), so no evidence row, no kernel verdict, no halt was ever
    produced for that obligation. This scans for item 16's own verdict unconditionally.

    Args:
        verification: The whole step-15 verify result.

    Returns:
        The ``(preserved_worst_credible_capacity, preserved_obligation_magnitude_unknown)`` pair
        from item 16's own verdict (kernel round #1 review #4), or ``(None, False)`` if item 16
        has no verdict (should not occur — all 17 items are always evaluated).
    """
    for verdict in verification.verdicts:
        if verdict.item is SendVerifyItem.CURRENTNESS:
            return (
                verdict.preserved_worst_credible_capacity,
                verdict.preserved_obligation_magnitude_unknown,
            )
    return None, False


class BrokerEgressGateway:
    """The Broker Egress Gateway — D-E1's ``Transmit`` implementation (design #34 §4).

    Satisfies ``(AttemptRequest) -> SendHandoff`` and returns **immediately**: the core never
    blocks on the network (design #31 §2.1 D5). The returned
    :class:`~tos.engine.SendHandoff` is an acknowledgement *of the hand-off*, not an order
    result; the order result is retained on :attr:`results` for ``EGRESS_RESULT`` re-injection
    (design #34 §5.3).

    Its polarity is the one D-E1 declares: only ``accepted_for_transmission is True`` records an
    accepted hand-off, and every refusal returns ``None`` — never ``False`` — because a refusal
    at this boundary is "the send did not proceed", which the engine reads positively.
    """

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
        """Wire the gateway.

        Args:
            contexts: Either a mapping attempt-id →
                :class:`~tos.egressgw.records.SendBoundaryContext`, or a **lazy resolver**
                ``(AttemptRequest) -> SendBoundaryContext | None`` (design #35 §3.1). The
                resolver exists because ``attempt_id`` is content-addressed at step 12 from
                (proof digest, permit identity, reference-coordinate digest), and under an
                event-driven driver the reference coordinate is a yield-order counter decoupled
                from any bar index — so a caller cannot populate the mapping ahead of the run
                without predicting the driver's yield order. Either way a missing context is the
                **same stop** it has always been: the verify list's facts are absent, and an
                absent required fact is a rejection (RFC-002 §10.8:761).
            transport: The injected step-18 transport. ``None`` is a stop, never a skip.
            sink: The provisional evidence sink (design #34 §4.6).
            ledger: The provisional single-use ledger; a fresh one is created when omitted.
            scheme: The canonicalization scheme :func:`~tos.egressgw.seal.build_send_seal` uses
                to compute the seal's two digests. ``None`` resolves to
                ``get_scheme(EV_L1_PROVISIONAL_VERSION)`` — the same provisional-version pin
                ``tos_runtime.compose.context`` already uses; not a silent fallback, a version
                pin (Phase 4 작업 6, design §1.2).
        """
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
        """Resolve this attempt's send-boundary context (design #35 §3.1).

        Both admitted shapes are recognised by **positive membership**, never by elimination: a
        ``Mapping`` is looked up by the content-addressed attempt id, a callable is asked, and
        anything that is neither resolves to ``None`` — which is the same recorded
        ``CONTEXT_MISSING`` stop an absent mapping entry has always been. There is no branch in
        which an unrecognised ``contexts`` argument admits a send.

        Args:
            attempt: The Coordinator's step-12 attempt request.

        Returns:
            The bound context, or ``None`` when none is bound (fail-closed).
        """
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
        """Record a recorded-reason halt and refuse the hand-off (design #34 §4.2).

        ⚠ **If the evidence sink itself raises while recording this halt, that exception is not
        caught here — it propagates.** A "halt" this method could not actually record would be
        exactly the silent stop the ``SendHaltReason`` vocabulary rules out ("a restrictive
        termination without a recorded reason is a silent stop, not a fail-closed one"). No
        retry is attempted (design #34 §5.4 — no retries anywhere): this call *is* the one
        recorded attempt. Any claim already made on the attempt is untouched — the ledger never
        releases a claim on a halt — and once the ``POTENTIALLY_LIVE_OBSERVED`` record has been
        written, the reservation projection stays possibly-live regardless of what this method
        does next, so a caller-visible crash from here on is the design's expected outcome, not
        an unhandled bug (design #34 §4.6: "a crash from here on is deliberately treated as
        possibly-live").

        ``step`` is **required**, never defaulted (Phase 3 wave 3 KW3-GW): ``SEND_REFUSED`` is
        emitted from many different points in the flow, so every call site must state which
        :class:`~tos.engine.CommitmentStep` it actually failed at — there is no single fixed
        mapping ``GatewayEvidenceRecord`` could derive from the kind alone (contrast the other
        kinds' fixed mapping, ``GatewayEvidenceRecord.FIXED_KIND_STEPS``).
        """
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
        """Build the pre-``SEND_STARTED`` seal, then claim its nonces (Phase 4 작업 6 §1.2).

        Runs after step 15 verify and the outbound-binding check, before anything is consumed.
        A seal-construction failure — including a coordinate-derivation fault, which used to
        surface only from inside step 18 — claims nothing (design #34 phase 4 작업 6 §1.2). The
        coordinate derivation happens here, through this module's own (monkeypatchable)
        ``outbound_coordinates`` name, exactly where it ran before this change — only its
        position in ``__call__``'s step order moved.

        **Which "request" identity the step-16 claim binds (independent review finding #3).**
        The ledger claims ``request_digest=seal.claim_request_digest`` — the item-1 single-use
        identity (``context.request_digest``), the same one item 1's own
        ``capability_and_permit_single_use`` check verifies against. This is **not**
        ``seal.request_bytes_digest`` — the item-17 Capsule/exact-binding identity — which is a
        different value by design: in the composed runtime the claim identity is per-attempt
        while the exact-binding identity is per account+instrument (identical across every
        attempt on the same egress request). Binding the ledger claim to the wrong one of the
        two would record an admission decision the verify list never actually made.

        Args:
            attempt_id: The attempt identity (for the halt record).
            attempt: The Coordinator's step-12 attempt request.
            context: The verified, binding-checked send-boundary context.

        Returns:
            ``(seal, None)`` on success, or ``(None, handoff)`` where ``handoff`` is the refusal
            :meth:`__call__` must return unchanged.
        """
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
                # The seal is step 15's output (design §1.2 survey note) — a construction
                # failure is a Send Boundary Verification failure, not a step of its own
                # (the 19-step CommitmentStep enum stays closed; there is no "step 15½").
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
        """Emit one evidence record, stamped with its :class:`~tos.engine.CommitmentStep`.

        A thin de-duplicating wrapper (Phase 3 wave 3 KW3-GW — extracted rather than letting
        ``__call__``'s already-registered size-budget exception grow further): every one of
        ``__call__``'s straight-line, fire-and-forget emissions goes through here instead of
        repeating ``self._sink.record(GatewayEvidenceRecord(...))`` at each site. The one
        exception is the step-19 ``EGRESS_RESULT_RECORDED`` write, which is deliberately
        deferred past this point (see the comment at its own call site) and so still builds and
        records its own :class:`~tos.egressgw.records.GatewayEvidenceRecord` directly.

        Args:
            kind: The evidence record kind.
            attempt_id: The attempt identity.
            step: The :class:`~tos.engine.CommitmentStep` this record belongs to.
            **fields: Any other :class:`~tos.egressgw.records.GatewayEvidenceRecord` field.
        """
        self._sink.record(
            GatewayEvidenceRecord(kind=kind, attempt_id=attempt_id, step=step, **fields)
        )

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Run send-boundary steps 15-19 for one bound attempt.

        Args:
            attempt: The Coordinator's step-12 attempt request.

        Returns:
            The :class:`~tos.engine.SendHandoff` — accepted only when every step succeeded.
        """
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
                # Already-consumed is fundamentally a single-use-claim fact (step 16's own
                # concern), checked defensively up front before doing any other work.
                step=CommitmentStep.SEND_STARTED_DURABLE,
                detail=(
                    "this attempt identity was already consumed — the same (proof, permit, "
                    "coordinate) triple content-addresses to the same attempt, so a repeat is a "
                    "blind resubmission and is refused. A retry is a NEW attempt with a new "
                    "permit and a new currentness proof (RFC-005 §11:326-328; §12:362 item 6)"
                ),
            )

        # -- step 15: the 17-item verify list ------------------------------------------
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

        # -- outbound binding: the seam scalars must be the constructed ones (MINOR-2) ----
        # Checked here — after the verify list, **before** the claim — so a mis-wired context
        # cannot burn a single-use capability / permit on a send that was never going to be
        # admissible. It is still, and load-bearingly, before the transport call. Still step
        # 15's own territory (the binding a conformant construction must satisfy).
        mismatch = outbound_binding_mismatch(context)
        if mismatch is not None:
            return self._halt(
                attempt_id=attempt_id,
                reason=SendHaltReason.OUTBOUND_NOT_BOUND_TO_CONSTRUCTION,
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                detail=mismatch,
            )

        # -- build the pre-SEND_STARTED seal (step 15's own output), then the step-16 claim --
        # (Phase 4 작업 6.) A seal-construction failure — including a coordinate-derivation
        # fault, which used to surface from inside step 18 as OUTBOUND_COORDINATE_DERIVATION_
        # RAISED — halts here, before the claim, so nothing is consumed.
        seal, halted = self._seal_and_claim(
            attempt_id=attempt_id, attempt=attempt, context=context
        )
        if halted is not None:
            return halted
        assert seal is not None  # narrowed by _seal_and_claim's own contract

        # The seal is step 15's own artifact (design §1.2 survey note) — not a "step 15½"; the
        # closed 19-step CommitmentStep enum gains no member for it.
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

        # -- step 17: the POTENTIALLY_LIVE projection is observed, never performed --------
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

        # -- step 18: exactly one delegation to the injected transport --------------------
        # Every argument below is read from ``seal`` alone — never from ``context`` again, with
        # ZERO exceptions (design §0 "봉인이 유일 입력 원천이어야 한다"; the M-K1 AST pin in the
        # test suite enforces this literally). ``reference`` (the causal-ordering tag) is sealed
        # too — ``seal.reference`` — even though it is not itself a security-relevant scalar,
        # because the rule the seal exists to satisfy is "the seal is the ONLY source", not
        # "the seal is the only source for the fields that matter".
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
        # Write-ahead mark (Phase 3 wave 3 KW3-GW): recorded immediately BEFORE send_once, so
        # "was the network call entered" is auditable from evidence even if send_once itself
        # never returns (RFC-002 §10.8 send boundary). Carries the seal digest / attempt id
        # like its SEND_STARTED / EGRESS_RESULT_RECORDED neighbours.
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

        # -- step 19: evidence ------------------------------------------------------------
        # send_once above is now the *only* transport call this attempt will ever make
        # (single-shot by construction, §5.4) — everything below only reads and records what
        # already happened. A fault reading the result is UNKNOWN-restrictive (§4.2 "unknown
        # preserves capacity, deny"), so it halts under its own recorded reason rather than
        # being misread as a transport failure.
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
        # ⚠ The write below is the one recorded attempt at the terminal, disposition-bearing
        # evidence for a completed send (result.attempt_id already matched and every field
        # above was readable — the send genuinely happened). If the sink itself raises here,
        # recording a SEND_REFUSED in its place would fabricate a refusal for something that
        # was, in fact, accepted and sent — the recorded-reason discipline forbids that
        # fabrication as firmly as it forbids a silent skip. Retrying the same write is not an
        # option either (no retries anywhere, design #34 §5.4). So the exception propagates
        # uncaught: the caller sees a crash, which design #34 §4.6 treats as the deliberate,
        # expected outcome from this point on ("a crash from here on is deliberately treated as
        # possibly-live") — the same "a missing acknowledgement is NOT a non-acceptance"
        # principle RFC-005 §11:322-323 states for a raised transport, applied here to a raised
        # evidence write instead of a raised send.
        self._sink.record(result_record)

        if result.kind in UNCERTAIN_RESULT_KINDS:
            # Same reasoning: EGRESS_RESULT_RECORDED has already been written, so the
            # disposition is already on record. A failure recording the supplementary
            # uncertain-send ladder is not silently dropped (that would misreport the ladder as
            # recorded when it was not) and is not repainted as a refusal (the send already
            # went out) — it propagates uncaught, same as the write above.
            self._record_uncertain(attempt_id, context)
        return SendHandoff(accepted_for_transmission=True, handoff_reference=attempt_id)

    def _record_uncertain(self, attempt_id: str, context: SendBoundaryContext) -> None:
        """Record brokercap's all-restrictive uncertain-send ladder (design #34 §5.4).

        ``uncertain_send_policy`` returns a **structurally** all-restrictive verdict — a
        permissive combination is unrepresentable (ADR-002-004 §12.4:640-646) — and
        ``same_order_retry_allowed`` is ``False`` for any profile whose ``SUBMISSION_IDEMPOTENCY``
        is not ``VERIFIED``. The gateway records both and does nothing else: there is no retry
        path to take.
        """
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
