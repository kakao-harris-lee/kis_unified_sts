"""``BrokerFinalityProducer`` — the post-trade finality proof producer for a fill the broker"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from tos.canonical import CanonicalizationScheme
from tos.engine.records import EgressResultPayload
from tos.engine.vocabulary import EgressResultKind

from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import FinalityResult, build_order_fqp_result

__all__ = [
    "BROKER_FULL_FILL_OBLIGATION_ID_PREFIX",
    "BROKER_FULL_FILL_PROOF_ID_PREFIX",
    "BROKER_NON_EXECUTION_OBLIGATION_ID_PREFIX",
    "BROKER_NON_EXECUTION_PROOF_ID_PREFIX",
    "BrokerFinalityProducer",
]

BROKER_FULL_FILL_OBLIGATION_ID_PREFIX = "broker-fqp-obligation"
BROKER_FULL_FILL_PROOF_ID_PREFIX = "broker-fqp-proof"
BROKER_NON_EXECUTION_OBLIGATION_ID_PREFIX = "broker-fqp-nonexec-obligation"
BROKER_NON_EXECUTION_PROOF_ID_PREFIX = "broker-fqp-nonexec-proof"

_NON_EXECUTION_KINDS: frozenset[EgressResultKind] = frozenset(
    {EgressResultKind.CANCEL_ACK, EgressResultKind.EXPIRED, EgressResultKind.REJECT}
)


@dataclass(frozen=True)
class BrokerFinalityProducer:
    """``ORDER_FQP`` proofs for broker-reported results (module docstring)."""

    config: FinalityConfig
    scheme: CanonicalizationScheme

    full_fill_obligation_prefix: ClassVar[str] = BROKER_FULL_FILL_OBLIGATION_ID_PREFIX
    full_fill_proof_prefix: ClassVar[str] = BROKER_FULL_FILL_PROOF_ID_PREFIX
    non_execution_obligation_prefix: ClassVar[str] = (
        BROKER_NON_EXECUTION_OBLIGATION_ID_PREFIX
    )
    non_execution_proof_prefix: ClassVar[str] = BROKER_NON_EXECUTION_PROOF_ID_PREFIX
    obligation_type: ClassVar[str] = "BROKER_ORDER_FQP"

    def produce(self, payload: EgressResultPayload) -> FinalityResult | None:
        """The proof for a broker ``FULL_FILL``, or ``None``."""
        if payload.kind is not EgressResultKind.FULL_FILL:
            return None
        filled = payload.filled_quantity
        if filled is None or filled <= 0:
            return None
        if payload.remaining_quantity is None or payload.remaining_quantity != 0:
            return None
        if not payload.broker_execution_id or payload.trading_date is None:
            return None
        return self._build(payload, quantity=filled, full_fill=True)

    def produce_non_execution(
        self, payload: EgressResultPayload
    ) -> FinalityResult | None:
        """The zero-executed proof for ``CANCEL_ACK``/``EXPIRED``/``REJECT`` — built only; the"""
        if payload.kind not in _NON_EXECUTION_KINDS:
            return None
        return self._build(payload, quantity=Decimal("0"), full_fill=False)

    def _build(
        self, payload: EgressResultPayload, *, quantity: Decimal, full_fill: bool
    ) -> FinalityResult | None:
        return build_order_fqp_result(
            payload,
            config=self.config,
            scheme=self.scheme,
            quantity=quantity,
            obligation_id_prefix=(
                self.full_fill_obligation_prefix
                if full_fill
                else self.non_execution_obligation_prefix
            ),
            proof_id_prefix=(
                self.full_fill_proof_prefix
                if full_fill
                else self.non_execution_proof_prefix
            ),
            obligation_type=self.obligation_type,
        )
