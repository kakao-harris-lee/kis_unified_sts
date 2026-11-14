"""The synthetic paper transport (design #34 §5.2) — network 0, credentials 0, route 0."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from pydantic import model_validator

from tos.brokeradapter.protocol import OutboundSendRequest
from tos.canonical import ArtifactIntegrityError, CanonicalDecimal, FrozenModel
from tos.engine import (
    FILL_RESULT_KINDS,
    AttemptRequest,
    EgressResultKind,
    EgressResultPayload,
    InstrumentKey,
)
from tos.ordering import OrderingEvent

__all__ = [
    "NON_FILL_DECLARABLE_KINDS",
    "SyntheticFillPolicy",
    "SyntheticPaperTransport",
    "synthetic_transport_nature_fields",
]


FILL_CONTEXT: Context = Context(prec=28, rounding=ROUND_HALF_EVEN)

NON_FILL_DECLARABLE_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.ACK,
        EgressResultKind.REJECT,
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
    }
)


_SYNTHETIC_EXECUTION_ID_PREFIX = "syn-exec"


def _synthetic_execution_id(attempt_id: str, kind: EgressResultKind) -> str:
    """The deterministic **SYNTHETIC** execution id ``send_once`` stamps on every result."""
    return f"{_SYNTHETIC_EXECUTION_ID_PREFIX}:{attempt_id}:{kind.value}"


class SyntheticFillPolicy(FrozenModel):
    """The injected, deterministic paper fill band (design #34 §5.2)."""

    declared_kind: EgressResultKind | None = None
    fill_numerator: int | None = None
    fill_denominator: int | None = None
    lot_size: CanonicalDecimal | None = None

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> SyntheticFillPolicy:
        """Reject a policy that declares both modes, neither, or a derivable kind."""
        has_band = self.fill_numerator is not None or self.fill_denominator is not None
        if self.declared_kind is not None:
            if self.declared_kind not in NON_FILL_DECLARABLE_KINDS:
                if self.declared_kind in FILL_RESULT_KINDS:
                    raise ArtifactIntegrityError(
                        f"SyntheticFillPolicy.declared_kind={self.declared_kind.value} is a "
                        "fill kind — a fill / partial-fill outcome is DERIVED from the "
                        "magnitudes and may never be declared (구조 파생 > 자기신고; RFC-005 "
                        "§11:338-339)"
                    )
                raise ArtifactIntegrityError(
                    f"SyntheticFillPolicy.declared_kind={self.declared_kind.value} is outside "
                    "this transport's supported declarable outcomes "
                    f"({sorted(k.value for k in NON_FILL_DECLARABLE_KINDS)}) — this single-shot "
                    "send/settle transport has no cancel-request or expiry-observation entry "
                    "point at all (Phase 3 wave 2 KW2-C1; module NON_FILL_DECLARABLE_KINDS "
                    "docstring)"
                )
            if has_band:
                raise ArtifactIntegrityError(
                    "SyntheticFillPolicy declares both an outcome and a fill band — a policy "
                    "with two modes has no single deterministic answer"
                )
            return self
        if self.fill_numerator is None or self.fill_denominator is None:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy declares neither an outcome nor a complete fill band — an "
                "undetermined transport is not a transport (fail-closed)"
            )
        if self.fill_denominator <= 0:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy.fill_denominator must be positive"
            )
        if self.fill_numerator < 0 or self.fill_numerator > self.fill_denominator:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy.fill_numerator must lie in [0, fill_denominator]"
            )
        if self.lot_size is None or self.lot_size <= 0:
            raise ArtifactIntegrityError(
                "SyntheticFillPolicy.lot_size must be a positive injected lot — a fill is "
                "floored to whole lots, never silently rounded"
            )
        return self


def synthetic_transport_nature_fields() -> dict[str, bool]:
    """The three negative-polarity nature flags a synthetic transport can honestly declare."""
    return {
        "reaches_broker": False,
        "credential_bearing": False,
        "route_bearing": False,
    }


class SyntheticPaperTransport:
    """A deterministic, network-free paper transport (design #34 §5.2)."""

    def __init__(self, policy: SyntheticFillPolicy) -> None:
        """Configure the transport with its injected deterministic fill policy."""
        self._policy = policy
        self.requests: tuple[OutboundSendRequest, ...] = ()

    @property
    def policy(self) -> SyntheticFillPolicy:
        """The injected fill policy."""
        return self._policy

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
        """Produce the deterministic result for exactly one verified outbound."""
        request = OutboundSendRequest(
            attempt=attempt,
            instrument_key=instrument_key,
            coordinates=coordinates,
            quantity=quantity,
            price=price,
            side=side,
            reference=reference,
            seal_digest=seal_digest,
        )
        self.requests += (request,)
        if self._policy.declared_kind is not None:
            return EgressResultPayload(
                instrument_key=instrument_key,
                attempt_id=attempt.attempt_id,
                kind=self._policy.declared_kind,
                broker_execution_id=_synthetic_execution_id(
                    attempt.attempt_id, self._policy.declared_kind
                ),
                reference=reference,
            )
        if quantity is None or not quantity.is_finite() or quantity <= 0:
            return EgressResultPayload(
                instrument_key=instrument_key,
                attempt_id=attempt.attempt_id,
                kind=EgressResultKind.UNKNOWN,
                broker_execution_id=_synthetic_execution_id(
                    attempt.attempt_id, EgressResultKind.UNKNOWN
                ),
                reference=reference,
            )
        filled = self._filled_quantity(quantity)
        remaining = quantity - filled
        if filled <= 0:
            return EgressResultPayload(
                instrument_key=instrument_key,
                attempt_id=attempt.attempt_id,
                kind=EgressResultKind.ACK,
                broker_execution_id=_synthetic_execution_id(
                    attempt.attempt_id, EgressResultKind.ACK
                ),
                reference=reference,
            )
        kind = (
            EgressResultKind.PARTIAL_FILL
            if remaining > 0
            else EgressResultKind.FULL_FILL
        )
        return EgressResultPayload(
            instrument_key=instrument_key,
            attempt_id=attempt.attempt_id,
            kind=kind,
            filled_quantity=filled,
            remaining_quantity=remaining,
            broker_execution_id=_synthetic_execution_id(attempt.attempt_id, kind),
            reference=reference,
        )

    def _filled_quantity(self, quantity: Decimal) -> Decimal:
        """The exact, lot-floored filled magnitude for ``quantity`` (pure integer ratio math)."""
        numerator = self._policy.fill_numerator
        denominator = self._policy.fill_denominator
        lot = self._policy.lot_size
        assert numerator is not None
        assert denominator is not None
        assert lot is not None
        with localcontext(FILL_CONTEXT):
            raw = (quantity * Decimal(numerator)) / Decimal(denominator)
            return (raw // lot) * lot
