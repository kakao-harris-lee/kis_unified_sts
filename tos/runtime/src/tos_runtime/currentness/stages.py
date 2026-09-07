"""Engine ``Stage`` realizations for steps 13 (Attempt Bind Verification) and
14 (Transmission Capability) — design #40 §5 order 6, lane R item 3
(`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 3). Replaces the ``tos.engine.standins.
ProvisionalStandIn`` entries for these two steps with real,
``AVAILABLE_PURE_PREDICATE`` stages that call kernel predicates over live
RCL/afg/iap facts.

Both stages read their comparison inputs from **injected callables**, never
a caller-supplied claim carried on the request — the same "구조 파생 >
자기신고" discipline ``tos.engine.sequencer._bindings_from`` already applies
to step 12's own bindings, and the same discipline the slice plan's §0
common rule states directly ("판정은 커널 술어만 한다").

**Review fix (independent review of 39dd3993, LOW-D).**
:class:`TransmissionCapabilityStage`'s durable RCL entry used to key
``command_id`` on ``txcap-{capability_id}`` — and ``capability_id`` was
itself derived from ``attempt.attempt_id``, not the nonce — so a genuine
nonce collision across two different attempts would never be caught by the
log's own UNIQUE constraint, even though the fault contract (mirroring
``tos_runtime.currentness.proof``'s own "nonce reuse refused by the log")
says nonce reuse is exactly what must be refused. The entry now keys on
``txcap-{nonce}``. Nonce-level single-use and attempt-level single-issuance
are two *different* invariants and are enforced two different ways: the
RCL's own ``command_id`` UNIQUE constraint refuses a **reused nonce**
(``__call__`` never reaches this stage's own memory for that check); this
stage's own ``_nonces`` cache additionally refuses a **second capability
request for an attempt that already has one** (checked first, in memory,
before any RCL append is attempted) — an attempt is never issued two
capabilities, and a nonce is never durably reused, and neither guard
substitutes for the other.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass

from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    CanonicalizationScheme,
    get_scheme,
)
from tos.engine.records import AttemptRequest, StageRequest, StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.iap import ApprovalResult, exact_binding_holds
from tos.rcl import (
    AppendReceipt,
    AppendRefusal,
    CommandType,
    CommitEntry,
    TransmissionCapability,
)
from tos.rcl.commitlog import CommitLog, LogView, WriterEpoch

__all__ = [
    "AttemptBindVerificationStage",
    "TransmissionCapabilityContext",
    "TransmissionCapabilityStage",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _prior_bound_digest(
    prior_verdicts: tuple[StageVerdict, ...], step: CommitmentStep
) -> str | None:
    """Structurally read a prior step's ``bound_digest`` off recorded
    verdicts (mirrors ``tos.engine.sequencer._bindings_from`` — never trust a
    caller-supplied claim for what an earlier step bound)."""
    for verdict in prior_verdicts:
        if verdict.step is step:
            return verdict.bound_digest
    return None


class AttemptBindVerificationStage:
    """Step 13 — binds the attempt's digest chain against reservation /
    permit / approval digests read live (``tos.iap.exact_binding_holds``,
    IAP-INV-004/IAP-AC-004).

    Args:
        reservation_digest_reader: Returns the reservation/order-conformance
            digest **currently** bound to ``attempt``, or ``None`` if
            unknown.
        permit_digest_reader: Returns the Action Flow Permit digest
            **currently** bound to ``attempt``, or ``None`` if unknown.
        approval_digest_reader: Returns the Independent Approval consumption
            digest **currently** bound to ``attempt``, or ``None`` if
            unknown.
    """

    def __init__(
        self,
        *,
        reservation_digest_reader: Callable[[AttemptRequest], str | None],
        permit_digest_reader: Callable[[AttemptRequest], str | None],
        approval_digest_reader: Callable[[AttemptRequest], str | None],
    ) -> None:
        self._reservation_digest_reader = reservation_digest_reader
        self._permit_digest_reader = permit_digest_reader
        self._approval_digest_reader = approval_digest_reader

    def __call__(self, request: StageRequest) -> StageVerdict:
        attempt = request.attempt
        if attempt is None:
            return StageVerdict(
                step=CommitmentStep.ATTEMPT_BIND_VERIFICATION,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="no attempt request is bound yet — UNKNOWN, never a pass",
            )

        approval_bound = _prior_bound_digest(
            request.prior_verdicts, CommitmentStep.INDEPENDENT_APPROVAL
        )
        bound_chain = {
            "conformance_proof": attempt.conformance_proof_digest,
            "action_flow_permit": attempt.action_flow_permit_identity,
            "approval": approval_bound,
        }
        actual_chain = {
            "conformance_proof": self._reservation_digest_reader(attempt),
            "action_flow_permit": self._permit_digest_reader(attempt),
            "approval": self._approval_digest_reader(attempt),
        }
        result = exact_binding_holds(bound_chain, actual_chain)

        if result is ApprovalResult.APPROVE:
            outcome = StageOutcome.ADMIT
        elif result is ApprovalResult.UNKNOWN:
            outcome = StageOutcome.UNKNOWN
        else:
            outcome = StageOutcome.DENY

        return StageVerdict(
            step=CommitmentStep.ATTEMPT_BIND_VERIFICATION,
            outcome=outcome,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type=type(result).__name__,
            native_verdict_value=result.value,
            bound_identity=attempt.attempt_id,
            reason=f"exact_binding_holds -> {result.value}",
        )


@dataclass(frozen=True)
class TransmissionCapabilityContext:
    """Injected facts a :class:`~tos.rcl.TransmissionCapability` needs beyond
    the attempt itself (design #40 §5 order 6, lane R item 3). Supplied by
    the composition root; a missing field is a stop, never a fabricated
    default (RFC-002 §10.8:761)."""

    reservation_identity: str | None
    account_scope: str | None
    instrument_scope: str | None
    side_action_scope: str | None


class TransmissionCapabilityStage:
    """Step 14 — issues a single-use :class:`~tos.rcl.TransmissionCapability`
    as a durable RCL entry (ADR-002-002 §12) and hands its nonce to the
    gateway via :meth:`nonce_for`.

    Args:
        log: The injected RCL ``CommitLog`` port.
        writer_epoch: The Writer Epoch this process holds.
        context_reader: Returns the :class:`TransmissionCapabilityContext`
            for ``request``, or ``None`` when unavailable.
        scheme: The canonicalization scheme.
        nonce_factory: Produces the per-issuance nonce — defaults to
            ``secrets.token_hex(16)`` (a real random token). Overridable only
            so a test can force a nonce collision and observe the RCL log's
            own duplicate-command refusal (LOW-D); production callers should
            never override this.
    """

    def __init__(
        self,
        log: CommitLog,
        *,
        writer_epoch: WriterEpoch,
        context_reader: Callable[[StageRequest], TransmissionCapabilityContext | None],
        scheme: CanonicalizationScheme = _SCHEME,
        nonce_factory: Callable[[], str] = lambda: secrets.token_hex(16),
    ) -> None:
        self._log = log
        self._writer_epoch = writer_epoch
        self._context_reader = context_reader
        self._scheme = scheme
        self._nonce_factory = nonce_factory
        self._nonces: dict[str, str] = {}

    def nonce_for(self, attempt_id: str) -> str | None:
        """The nonce this stage most recently issued + committed for
        ``attempt_id``, if any — read by the composition root when it fills
        ``SendBoundaryContext.capability_nonce`` (item 1)."""
        return self._nonces.get(attempt_id)

    @staticmethod
    def _context_incomplete(
        context: TransmissionCapabilityContext | None,
    ) -> bool:
        """Whether ``context`` is absent or missing a required field — split
        out of :meth:`__call__` to stay under the module size budget."""
        return (
            context is None
            or context.reservation_identity is None
            or context.account_scope is None
            or context.instrument_scope is None
            or context.side_action_scope is None
        )

    def _commit_capability(
        self,
        attempt: AttemptRequest,
        context: TransmissionCapabilityContext,
        view: LogView,
    ) -> StageVerdict:
        """Issue + durably commit the capability — split out of
        :meth:`__call__` to stay under the module size budget."""
        nonce = self._nonce_factory()
        capability = TransmissionCapability.issue(
            scheme=self._scheme,
            capability_id=f"cap-{attempt.attempt_id}",
            nonce=nonce,
            single_use=True,
            reservation_identity=context.reservation_identity,
            attempt_identity=attempt.attempt_id,
            account_scope=context.account_scope,
            instrument_scope=context.instrument_scope,
            side_action_scope=context.side_action_scope,
            ledger_epoch=view.epoch,
            bound_reservation_revision=view.last_seq,
        )
        assert isinstance(capability, TransmissionCapability)

        expected_seq = -1 if view.last_seq is None else view.last_seq
        entry = CommitEntry(
            # LOW-D: the RCL idempotency key is the NONCE itself, not the
            # capability/attempt id — single-use is enforced by the log's
            # own command_id UNIQUE constraint, mirroring
            # tos_runtime.currentness.proof's own convention.
            command_id=f"txcap-{nonce}",
            command_digest=capability.canonical_digest,
            kind=CommandType.AUTHORIZE_TRANSMISSION_CAPABILITY,
            payload_digest=capability.canonical_digest,
        )
        receipt = self._log.append_cas(
            entry, expected_seq=expected_seq, writer_epoch=self._writer_epoch
        )
        if isinstance(receipt, AppendRefusal):
            return StageVerdict(
                step=CommitmentStep.TRANSMISSION_CAPABILITY,
                outcome=StageOutcome.DENY,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=f"RCL append refused: {receipt.reason}",
            )
        assert isinstance(receipt, AppendReceipt)

        self._nonces[attempt.attempt_id] = nonce
        return StageVerdict(
            step=CommitmentStep.TRANSMISSION_CAPABILITY,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type=type(capability).__name__,
            bound_digest=capability.canonical_digest,
            bound_identity=capability.capability_id,
            reason="single-use TransmissionCapability committed to the RCL",
        )

    def __call__(self, request: StageRequest) -> StageVerdict:
        attempt = request.attempt
        if attempt is None:
            return StageVerdict(
                step=CommitmentStep.TRANSMISSION_CAPABILITY,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="no attempt request is bound yet — UNKNOWN, never a pass",
            )

        # LOW-D: an attempt is single-use for a TransmissionCapability too —
        # a second request for an attempt that already has one is refused
        # in memory, before any RCL append is even attempted (a distinct
        # invariant from the nonce-reuse guard the RCL append enforces
        # inside _commit_capability).
        if attempt.attempt_id in self._nonces:
            return StageVerdict(
                step=CommitmentStep.TRANSMISSION_CAPABILITY,
                outcome=StageOutcome.DENY,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=(
                    "a TransmissionCapability was already issued for this "
                    "attempt — single-use, never re-issued"
                ),
            )

        context = self._context_reader(request)
        if self._context_incomplete(context):
            return StageVerdict(
                step=CommitmentStep.TRANSMISSION_CAPABILITY,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason=(
                    "TransmissionCapabilityContext is absent or incomplete — a "
                    "missing required fact is a stop, never a skip "
                    "(RFC-002 §10.8:761)"
                ),
            )
        assert context is not None  # narrowed by _context_incomplete

        view = self._log.read_linearizable(writer_epoch=self._writer_epoch)
        if (
            not view.epoch
        ):  # None or 0 (unacquired sentinel, tos_runtime.rcl.log.SqliteCommitLog.current_epoch)
            return StageVerdict(
                step=CommitmentStep.TRANSMISSION_CAPABILITY,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="no Writer Epoch has been acquired — UNKNOWN, never a pass",
            )

        return self._commit_capability(attempt, context, view)
