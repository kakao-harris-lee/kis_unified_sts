"""``SendSeal`` — the immutable pre-``SEND_STARTED`` outbound tuple (Phase 4 작업 6, design"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field, ValidationError, model_validator

from tos.egressgw._base import (
    ArtifactIntegrityError,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
)
from tos.engine import AttemptRequest, InstrumentKey, reference_coordinate_digest
from tos.ordering import OrderingEvent

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
    """The authorized egress coordinates as opaque ordered scalars for the transport (§5.1)."""
    authorized = context.authorized_coordinates
    pairs: list[tuple[str, str | None]] = []
    for name in OUTBOUND_COORDINATE_NAMES:
        value = None if authorized is None else getattr(authorized, name, None)
        pairs.append((name, None if value is None else str(value)))
    return tuple(pairs)


class SendSealUnconstructable(Exception):
    """Raised when :func:`build_send_seal` cannot assemble a :class:`SendSeal`."""

    def __init__(self, reason: str) -> None:
        """Record the reason."""
        self.reason = reason
        super().__init__(reason)


class SendSeal(FrozenModel):
    """The one immutable pre-``SEND_STARTED`` outbound tuple (design §1.1)."""

    attempt_id: str = Field(min_length=1)
    instrument_key: InstrumentKey

    request_bytes_digest: str = Field(min_length=1)
    canonical_command_digest: str = Field(min_length=1)
    capsule_egress_request_digest: str = Field(min_length=1)
    claim_request_digest: str = Field(min_length=1)

    claim_principal: str = Field(min_length=1)
    active_principal: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    account: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    route_identity: str = Field(min_length=1)
    credential_generation: int
    broker_session_generation: int
    egress_generation: int
    action: str = Field(min_length=1)
    method: str = Field(min_length=1)

    capability_nonce: str = Field(min_length=1)
    action_flow_permit_nonce: str = Field(min_length=1)

    outbound_coordinates: tuple[tuple[str, str | None], ...]
    outbound_quantity: CanonicalDecimal
    outbound_price: CanonicalDecimal
    outbound_side: str
    reference: OrderingEvent
    reference_digest: str

    outbound_request_digest: str
    seal_digest: str

    @model_validator(mode="after")
    def _outbound_coordinates_match_sealed_fields(self) -> SendSeal:
        """Each outbound coordinate pair must equal the same-named sealed field (design §1.1)."""
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
        """``claim_principal`` must equal ``active_principal`` (measured-equal, design §5 A2)."""
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
    """Collect every required seal fact from ``context``; an absent fact stays ``None``."""
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
        "claim_request_digest": context.request_digest,
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
        "reference": context.reference,
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
    """Assemble the one immutable pre-``SEND_STARTED`` outbound tuple (design §1.1/§1.2)."""
    fields = _gather_seal_fields(context)
    missing = sorted(name for name, value in fields.items() if value is None)
    if missing:
        raise SendSealUnconstructable(
            "cannot seal an outbound send — missing required fact(s): "
            f"{', '.join(missing)} (RFC-002 §10.8:761; design #34 phase 4 작업 6 §1.1)"
        )

    reference_digest = reference_coordinate_digest(fields["reference"], scheme=scheme)
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
    _nested_model_fields = {"instrument_key", "reference"}
    covered: dict[str, Any] = {
        "attempt_id": attempt.attempt_id,
        **{
            name: (
                value.model_dump(mode="json") if name in _nested_model_fields else value
            )
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
    seal_digest: str | None,
) -> bool:
    """Whether every value about to cross the transport seam is this seal's own (design §1.1)."""
    return (
        seal.outbound_coordinates == coordinates
        and seal.outbound_quantity == quantity
        and seal.outbound_price == price
        and seal.outbound_side == side
        and seal.instrument_key == instrument_key
        and seal.attempt_id == attempt_id
        and seal.seal_digest == seal_digest
    )
