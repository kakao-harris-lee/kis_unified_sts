"""``SendSeal`` — the immutable pre-``SEND_STARTED`` outbound tuple (Phase 4 작업 6, design
``docs/plans/2026-09-08-tos-phase4-send-seal-plan.md`` §1.1/§1.2).

ADR-002-013 §12 verbatim: "No security-relevant field may be supplied or changed downstream
after the proof comparison … if request bytes differ, no send is permitted." Before this module,
the gateway derived the outbound coordinates (:func:`outbound_coordinates`) **after** the step-16
claim and ``SEND_STARTED`` record, and the economic scalars (quantity / price / side) travelled
from ``SendBoundaryContext`` straight to the transport call with nothing preventing a second,
independent read of ``context`` between the claim and the call from observing a different value.
:class:`SendSeal` closes that gap by being the **sole source** step 18 may read from: every
identity, request-digest, principal / route coordinate, single-use nonce, and outbound economic
scalar the transport call needs is copied onto one frozen tuple *before* anything is claimed, and
the gateway (`gateway.py`) is rewired to read step 18's arguments from the seal alone, never from
``context`` a second time.

**Why a plain ``FrozenModel`` and not a ``DigestBoundArtifact``.** The series' digest-bound
artifacts (``tos.canonical.DigestBoundArtifact`` and its subclasses) exist to let an *externally
issued* digest be re-verified against covered content — they carry a mutable-until-issued
``DRAFT``/``ISSUED`` lifecycle this seal has no use for: a ``SendSeal`` is built and consumed
within a single :meth:`~tos.egressgw.gateway.BrokerEgressGateway.__call__` invocation, is never
serialized, issued, or re-verified later, and every one of its fields is required at construction
(design §1.1 "covered 전부 필수 · None 불허 · 생성 자체가 거부 = 타입 봉인") — pydantic's ordinary
required-field mechanism *is* the type seal here, so no separate ``DRAFT`` state or id-binding
hook is needed.

**A2 measurement (design §5).** Every measured fixture (``tos/tests/egressgw/_egressgw_fixtures.
py::happy_context`` and ``tos/tests/slice/_slice_fixtures.py``) binds
``context.principal == context.authorized_coordinates.active_principal`` (both ``"egressgw-1"`` /
``"egressgw-slice"`` respectively) — so :attr:`SendSeal.claim_principal` and
:attr:`SendSeal.active_principal` are measured-equal everywhere this kernel is exercised, and the
combined validator below **enforces** that equality rather than merely recording it (design §1.1
"다르면 강제하지 말고 둘을 기록만 하고 보고" — measured equal, so enforced).

Firewall (design #34 §0.3, unchanged by this module): ``pydantic`` + stdlib + ``tos.*`` only. No
clock, no RNG, no network. ``tos.egressgw.records`` is imported **only** under ``TYPE_CHECKING``
(a lazy string annotation, ``from __future__ import annotations``) — ``records.py`` imports
:class:`SendSeal` for its own ``GatewayEvidenceRecord.send_seal`` field, so a real runtime import
here would be circular; the type-only edge is enough for :func:`build_send_seal`'s signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError, model_validator

from tos.egressgw._base import (
    ArtifactIntegrityError,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
)
from tos.engine import AttemptRequest, InstrumentKey, reference_coordinate_digest

if (
    TYPE_CHECKING
):  # pragma: no cover - type-only edge; avoids a seal <-> records import cycle
    from tos.egressgw.records import SendBoundaryContext

__all__ = [
    "OUTBOUND_COORDINATE_NAMES",
    "SendSeal",
    "SendSealUnconstructable",
    "build_send_seal",
    "outbound_coordinates",
    "seal_matches_outbound",
]


#: The egress coordinate names handed to the transport, in the fixed order
#: :class:`~tos.egress.EgressCoordinateSet` declares (deterministic — no dict iteration order, no
#: sorting of a mutable set). Moved here (from ``gateway.py``) because :func:`build_send_seal`
#: needs the identical derivation the gateway used to call the transport, and a sibling-module
#: reuse is what keeps the two from drifting apart (single definition, re-exported by
#: ``gateway.py`` for backward-compatible ``tos.egressgw`` call sites).
OUTBOUND_COORDINATE_NAMES: tuple[str, ...] = (
    "endpoint",
    "account",
    "environment",
    "action",
    "method",
    "route_identity",
    "credential_generation",
    "broker_session_generation",
    "egress_generation",
    "active_principal",
)


def outbound_coordinates(
    context: SendBoundaryContext,
) -> tuple[tuple[str, str | None], ...]:
    """The authorized egress coordinates as opaque ordered scalars for the transport (§5.1).

    The transport receives **opaque** coordinates in the fixed
    :data:`OUTBOUND_COORDINATE_NAMES` order — deterministic, and deliberately uninterpreted:
    broker-specific behaviour stays isolated behind the Broker Adapter boundary (RFC-002
    §10.8:739). The *typed* authoritative carriers (the egress ``EgressRequestRecord`` /
    ``EgressCoordinateSet``) stay on this side of the seam, where ``exact_binding_holds`` runs.

    Args:
        context: The send-boundary context.

    Returns:
        The ordered ``(name, value)`` pairs; every value is stringified or ``None``.
    """
    authorized = context.authorized_coordinates
    pairs: list[tuple[str, str | None]] = []
    for name in OUTBOUND_COORDINATE_NAMES:
        value = None if authorized is None else getattr(authorized, name, None)
        pairs.append((name, None if value is None else str(value)))
    return tuple(pairs)


class SendSealUnconstructable(Exception):
    """Raised when :func:`build_send_seal` cannot assemble a :class:`SendSeal`.

    Two distinct causes both land here (design §1.2 — the former
    ``OUTBOUND_COORDINATE_DERIVATION_RAISED`` halt site is absorbed into this one): a required
    fact the context does not carry, or the assembled seal failing its own construction-time
    validation (a coordinate/field mismatch, or a diverging claim/active principal).
    """

    def __init__(self, reason: str) -> None:
        """Record the reason.

        Args:
            reason: A human-readable explanation of why the seal could not be built.
        """
        self.reason = reason
        super().__init__(reason)


class SendSeal(FrozenModel):
    """The one immutable pre-``SEND_STARTED`` outbound tuple (design §1.1).

    Every field is a **required**, non-``None`` value: pydantic's ordinary required-field
    mechanism is the type seal (a missing fact makes the object unconstructable, not merely
    incompletely populated). Grouped exactly as design §1.1 lists them:

    * **identity** — :attr:`attempt_id`, :attr:`instrument_key`;
    * **request** — :attr:`request_bytes_digest` (= the exact outbound egress request's own
      digest), :attr:`canonical_command_digest`, :attr:`capsule_egress_request_digest`;
    * **principal / route (ADR-002-013 §8/§10 coordinates)** — :attr:`claim_principal` (=
      ``context.principal``), :attr:`active_principal`, :attr:`endpoint`, :attr:`account`,
      :attr:`environment`, :attr:`route_identity`, :attr:`credential_generation`,
      :attr:`broker_session_generation`, :attr:`egress_generation`, :attr:`action`,
      :attr:`method`;
    * **single-use** — :attr:`capability_nonce`, :attr:`action_flow_permit_nonce`;
    * **the exact outbound (what step 18 hands the transport)** — :attr:`outbound_coordinates`
      (= :func:`outbound_coordinates`'s own result, unchanged), :attr:`outbound_quantity`,
      :attr:`outbound_price`, :attr:`outbound_side`, :attr:`reference_digest`.

    Two digests close the seal: :attr:`outbound_request_digest` covers only the five "exact
    outbound" fields plus :attr:`attempt_id` / :attr:`instrument_key` — the kernel-side definition
    of "exact outbound bytes" for the synthetic transport (the ``OutboundSendRequest`` canonical
    form is the synthetic stand-in for wire bytes, design §5 A1). :attr:`seal_digest` covers every
    field above, :attr:`outbound_request_digest` included.
    """

    # -- identity ------------------------------------------------------------------------
    attempt_id: str
    instrument_key: InstrumentKey

    # -- request ---------------------------------------------------------------------------
    request_bytes_digest: str
    canonical_command_digest: str
    capsule_egress_request_digest: str

    # -- principal / route (ADR-002-013 §8/§10 coordinates) -------------------------------
    claim_principal: str
    active_principal: str
    endpoint: str
    account: str
    environment: str
    route_identity: str
    credential_generation: int
    broker_session_generation: int
    egress_generation: int
    action: str
    method: str

    # -- single-use --------------------------------------------------------------------------
    capability_nonce: str
    action_flow_permit_nonce: str

    # -- the exact outbound (step 18's sole input source) ---------------------------------
    outbound_coordinates: tuple[tuple[str, str | None], ...]
    outbound_quantity: CanonicalDecimal
    outbound_price: CanonicalDecimal
    outbound_side: str
    reference_digest: str

    # -- the two closing digests -----------------------------------------------------------
    outbound_request_digest: str
    seal_digest: str

    @model_validator(mode="after")
    def _outbound_coordinates_match_sealed_fields(self) -> SendSeal:
        """Each outbound coordinate pair must equal the same-named sealed field (design §1.1).

        Enforced as an exact shape match — the fixed :data:`OUTBOUND_COORDINATE_NAMES` order,
        every name present exactly once — not merely "no mismatch among the names that happen to
        be there": a coordinate this seal has no matching field for is exactly the substitution
        surface the seal exists to close.
        """
        named: dict[str, str] = {
            "endpoint": self.endpoint,
            "account": self.account,
            "environment": self.environment,
            "action": self.action,
            "method": self.method,
            "route_identity": self.route_identity,
            "credential_generation": str(self.credential_generation),
            "broker_session_generation": str(self.broker_session_generation),
            "egress_generation": str(self.egress_generation),
            "active_principal": self.active_principal,
        }
        present = tuple(name for name, _ in self.outbound_coordinates)
        if present != OUTBOUND_COORDINATE_NAMES:
            raise ArtifactIntegrityError(
                f"SendSeal.outbound_coordinates names {present!r} do not match the fixed "
                f"{OUTBOUND_COORDINATE_NAMES!r} order — the seal must carry exactly the "
                "transport's coordinate shape (design #34 phase 4 작업 6 §1.1)"
            )
        for name, value in self.outbound_coordinates:
            expected = named[name]
            if value != expected:
                raise ArtifactIntegrityError(
                    f"SendSeal.outbound_coordinates[{name!r}]={value!r} does not match the "
                    f"sealed field {name}={expected!r} — the exact coordinate about to cross "
                    "the transport seam must be the one this seal binds (design #34 phase 4 "
                    "작업 6 §1.1)"
                )
        return self

    @model_validator(mode="after")
    def _claim_principal_matches_active_principal(self) -> SendSeal:
        """``claim_principal`` must equal ``active_principal`` (measured-equal, design §5 A2).

        Every fixture this kernel is exercised against (``happy_context``, the slice fixtures)
        measures the two identical, so the seal enforces the equality rather than merely
        recording a divergence design §1.1 leaves as an open operator question would.
        """
        if self.claim_principal != self.active_principal:
            raise ArtifactIntegrityError(
                f"SendSeal.claim_principal={self.claim_principal!r} != "
                f"active_principal={self.active_principal!r} — every measured fixture "
                "(happy_context, slice) binds the two identically; a seal that diverges is a "
                "wiring defect the seal must not silently carry forward (design #34 phase 4 "
                "작업 6 §1.1 A2)"
            )
        return self


def _gather_seal_fields(context: SendBoundaryContext) -> dict[str, Any]:
    """Collect every required seal fact from ``context``; an absent fact stays ``None``.

    Args:
        context: The verified send-boundary context.

    Returns:
        A mapping keyed exactly by :class:`SendSeal`'s field names (``instrument_key`` through
        ``outbound_side``) — the caller checks for ``None`` values.
    """
    authorized = context.authorized_coordinates
    egress_request = context.egress_request
    return {
        "instrument_key": context.instrument_key,
        "request_bytes_digest": (
            None if egress_request is None else egress_request.request_bytes_digest
        ),
        "canonical_command_digest": (
            None if egress_request is None else egress_request.canonical_command_digest
        ),
        "capsule_egress_request_digest": context.capsule_egress_request_digest,
        "claim_principal": context.principal,
        "active_principal": None if authorized is None else authorized.active_principal,
        "endpoint": None if authorized is None else authorized.endpoint,
        "account": None if authorized is None else authorized.account,
        "environment": None if authorized is None else authorized.environment,
        "route_identity": None if authorized is None else authorized.route_identity,
        "credential_generation": (
            None if authorized is None else authorized.credential_generation
        ),
        "broker_session_generation": (
            None if authorized is None else authorized.broker_session_generation
        ),
        "egress_generation": (
            None if authorized is None else authorized.egress_generation
        ),
        "action": None if authorized is None else authorized.action,
        "method": None if authorized is None else authorized.method,
        "capability_nonce": context.capability_nonce,
        "action_flow_permit_nonce": context.action_flow_permit_nonce,
        "outbound_quantity": context.outbound_quantity,
        "outbound_price": context.outbound_price,
        "outbound_side": context.outbound_side,
    }


def _outbound_preimage(
    *,
    coordinates: tuple[tuple[str, str | None], ...],
    outbound_quantity: CanonicalDecimal,
    outbound_price: CanonicalDecimal,
    outbound_side: str,
    reference_digest: str,
    attempt_id: str,
    instrument_key: InstrumentKey,
) -> dict[str, Any]:
    """The ``outbound_request_digest`` preimage — the five outbound fields plus identity (§1.1)."""
    return {
        "outbound_coordinates": [[name, value] for name, value in coordinates],
        "outbound_quantity": outbound_quantity,
        "outbound_price": outbound_price,
        "outbound_side": outbound_side,
        "reference_digest": reference_digest,
        "attempt_id": attempt_id,
        "instrument_key": instrument_key.model_dump(mode="json"),
    }


def build_send_seal(
    *,
    context: SendBoundaryContext,
    attempt: AttemptRequest,
    coordinates: tuple[tuple[str, str | None], ...],
    scheme: CanonicalizationScheme,
) -> SendSeal:
    """Assemble the one immutable pre-``SEND_STARTED`` outbound tuple (design §1.1/§1.2).

    Every field is read off ``context`` / ``attempt`` — nothing is re-derived from a look-alike
    and nothing is accepted from a step-18 caller. Runs **before** the step-16 claim, so a
    construction failure here consumes no nonce and starts no send (RFC-002 §10.8:761 "reject
    when a required fact is missing").

    Args:
        context: The verified, binding-checked send-boundary context.
        attempt: The Coordinator's step-12 attempt request.
        coordinates: :func:`outbound_coordinates`'s own result over this same ``context`` —
            passed in rather than recomputed here, so the gateway's own (monkeypatchable) call
            site stays the single place that derivation happens.
        scheme: The injected canonicalization scheme.

    Returns:
        The constructed, self-validated :class:`SendSeal`.

    Raises:
        SendSealUnconstructable: If a required fact is absent, or the assembled seal fails its
            own construction-time validation.
    """
    fields = _gather_seal_fields(context)
    missing = sorted(name for name, value in fields.items() if value is None)
    if missing:
        raise SendSealUnconstructable(
            "cannot seal an outbound send — missing required fact(s): "
            f"{', '.join(missing)} (RFC-002 §10.8:761; design #34 phase 4 작업 6 §1.1)"
        )

    reference_digest = reference_coordinate_digest(context.reference, scheme=scheme)
    outbound_request_digest = scheme.compute_digest(
        _outbound_preimage(
            coordinates=coordinates,
            outbound_quantity=fields["outbound_quantity"],
            outbound_price=fields["outbound_price"],
            outbound_side=fields["outbound_side"],
            reference_digest=reference_digest,
            attempt_id=attempt.attempt_id,
            instrument_key=fields["instrument_key"],
        )
    )
    covered: dict[str, Any] = {
        "attempt_id": attempt.attempt_id,
        **{
            name: (value.model_dump(mode="json") if name == "instrument_key" else value)
            for name, value in fields.items()
        },
        "outbound_coordinates": [[name, value] for name, value in coordinates],
        "reference_digest": reference_digest,
        "outbound_request_digest": outbound_request_digest,
    }
    seal_digest = scheme.compute_digest(covered)

    try:
        return SendSeal(
            attempt_id=attempt.attempt_id,
            outbound_coordinates=coordinates,
            reference_digest=reference_digest,
            outbound_request_digest=outbound_request_digest,
            seal_digest=seal_digest,
            **fields,
        )
    except ValidationError as exc:
        raise SendSealUnconstructable(
            f"the assembled send seal failed its own construction-time validation: {exc}"
        ) from exc


def seal_matches_outbound(
    seal: SendSeal,
    *,
    coordinates: tuple[tuple[str, str | None], ...],
    quantity: CanonicalDecimal | None,
    price: CanonicalDecimal | None,
    side: str | None,
    instrument_key: InstrumentKey | None,
    attempt_id: str | None,
) -> bool:
    """Whether every value about to cross the transport seam is this seal's own (design §1.1).

    A call-site self-check for step 18: everything ``send_once`` is about to receive must equal
    what ``seal`` already carries. Used defensively and by the test suite's mutation checks
    (M-K1/M-K2) to prove the seal is the sole source, not merely a record alongside a second read.

    Args:
        seal: The sealed tuple built before the step-16 claim.
        coordinates: The coordinates about to be handed to the transport.
        quantity: The quantity about to be handed to the transport.
        price: The price about to be handed to the transport.
        side: The side about to be handed to the transport.
        instrument_key: The instrument key about to be handed to the transport.
        attempt_id: The attempt identity about to be handed to the transport.

    Returns:
        ``True`` iff every one of the six values equals the seal's own.
    """
    return (
        seal.outbound_coordinates == coordinates
        and seal.outbound_quantity == quantity
        and seal.outbound_price == price
        and seal.outbound_side == side
        and seal.instrument_key == instrument_key
        and seal.attempt_id == attempt_id
    )
