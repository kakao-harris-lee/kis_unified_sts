"""``BrokerFinalityProducer`` — the post-trade finality proof producer for a fill the broker
reported (PR-3b, rescope plan §3 M2).

**What is different from the SYNTHETIC producer, and what is not.** The proof is the same
``ORDER_FQP`` artifact (:func:`~tos_runtime.posttrade.finality.build_order_fqp_result`, shared):
quantity only, one ``RECEIPT`` leg, every other finality dimension in ``does_not_prove``. What
changes is where the ``FULL_FILL`` came from — the KIS 모의투자 주식일별주문체결조회 (``VTTC0081R``)
row the post-ACK fill observer (:mod:`tos_runtime.posttrade.fill_observer`) attributed to this
attempt's ODNO — and so the artifact says so: ``obligation_type = "BROKER_ORDER_FQP"`` and the
``broker-fqp-*`` id/idempotency prefixes. Nothing here is labelled ``SYNTHETIC``.

**One extra precondition for a fill proof.** A broker-sourced ``FULL_FILL`` must name the
broker's order (``broker_execution_id``, the ODNO) and its trading date — the pair the
reconciliation join (:mod:`tos_runtime.recon.service`) identifies a KIS order by. A payload
without both is not a broker fill this producer can vouch for, so it yields no proof.

**This does not decide release.** Producing the artifact is all it does; the release consumer
(:mod:`tos_runtime.posttrade.release_consumer`) still requires the reconciliation against the
real KIS witness to say ``MATCHED`` before any RCL transition.

Firewall: stdlib + ``tos.canonical``/``tos.engine`` + ``tos_runtime.posttrade`` only.
"""

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

#: Same three kinds as the SYNTHETIC producer's non-execution path — the release consumer only
#: calls it after reconciliation corroborates that nothing executed.
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
        """The proof for a broker ``FULL_FILL``, or ``None``.

        ``None`` unless the kind is ``FULL_FILL``, ``filled_quantity`` is positive,
        ``remaining_quantity`` is exactly zero (the ``ORDER_FQP`` claim, checked on the payload
        rather than inferred from the kind), and the payload names the broker order
        (``broker_execution_id``) and its ``trading_date``.
        """
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
        """The zero-executed proof for ``CANCEL_ACK``/``EXPIRED``/``REJECT`` — built only; the
        release consumer calls this after reconciliation corroborates non-execution."""
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
