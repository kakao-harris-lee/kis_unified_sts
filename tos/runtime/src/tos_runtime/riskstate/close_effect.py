"""The CLOSE risk-credit vocabulary both close authorities share — pure, store-free helpers.

Split out of :mod:`tos_runtime.riskstate.service` to keep that module under the repo's
1000-line module size budget (``tools/tos_size_budget.py``), the same pure decomposition
:mod:`tos_runtime.posttrade.entry_discharge` was split out of ``release_consumer.py`` under.
Nothing here reads a store, consumes a proof, or decides anything: these are the predicate and
the audit-row shape the service calls once it already holds this attempt's facts.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine.records`` +
``tos_runtime.{recon.ports, riskstate.close_bound, riskstate.held_position}`` only. No
``shared.*``, no write call.
"""

from __future__ import annotations

from decimal import Decimal

from tos.engine.records import StageRequest

from tos_runtime.recon.ports import WitnessScope
from tos_runtime.riskstate.close_bound import (
    CloseAuthoritySource,
    CloseBoundRefusal,
    EntryCloseBound,
)
from tos_runtime.riskstate.held_position import (
    HeldPositionProof,
    PositionSide,
    RclTip,
)

__all__ = [
    "ABSENT_BOUND_FIELD",
    "PROOF_BEARING_STATUSES",
    "close_effect_audit",
    "close_proof_matches",
    "refused_bound",
    "tightest_cap",
]

#: The ``close_effect.proof_status`` values that mean "a bound was actually evaluated against a
#: concrete quantity" — as opposed to one of the earlier refusals (no arm, no provider, no
#: proof), where the input the bound needed never arrived at all. Used for two things: which
#: statuses may carry proof metadata in the audit row, and whether step 6's absent-field list
#: names the bound input as missing.
PROOF_BEARING_STATUSES: frozenset[str] = frozenset(
    {
        "PROOF_ACCEPTED",
        "QUANTITY_EXCEEDS_HELD",
        "QUANTITY_EXCEEDS_ENTRY",
        "QUANTITY_UNKNOWN",
    }
)

#: The absent-field name each close authority reports when its own bound input never arrived.
ABSENT_BOUND_FIELD: dict[CloseAuthoritySource, str] = {
    CloseAuthoritySource.BROKER_HELD_PROOF: "held_position_proof",
    CloseAuthoritySource.DURABLE_EVIDENCE: "durable_entry_close_bound",
}


def refused_bound(reason: CloseBoundRefusal) -> EntryCloseBound:
    """A bound the service could not even ask for — scope unknown, so left empty."""
    return EntryCloseBound(
        account="",
        instrument="",
        entry_reservation_id=None,
        entry_attempt_id=None,
        entry_quantity=None,
        prior_closed=None,
        rcl_writer_epoch=None,
        rcl_last_seq=None,
        refusal=reason.value,
    )


def tightest_cap(*caps: Decimal | None) -> Decimal | None:
    """The smallest cap, or ``None`` if ANY of them is unknown — unknown is not absent.

    ``min(held, entry - proven closes)`` (#1012 L3), written so a missing input can never be
    silently dropped out of the minimum: an unknown holding or an unprovable entry remainder
    makes the whole bound unknown, which
    :func:`~tos_runtime.risk.close_quantity.close_within_entry` turns into UNKNOWN.
    """
    if any(cap is None for cap in caps):
        return None
    return min(cap for cap in caps if cap is not None)


def close_proof_matches(
    proof: HeldPositionProof, request: StageRequest, direction: str | None
) -> bool:
    """Check the consumed value is bound to this proposal, instrument, side, and tip."""
    if direction not in (PositionSide.LONG.value, PositionSide.SHORT.value):
        return False
    proposal_id = getattr(request.proposal, "proposal_id", None)
    return (
        type(proof) is HeldPositionProof
        and type(proof.scope) is WitnessScope
        and proof.scope.account == request.instrument_key.account
        and proof.scope.instrument_keys == (request.instrument_key,)
        and proof.scope.attempt_ids == ()
        and type(proof.scope.as_of_generation) is int
        and type(proposal_id) is str
        and proof.proposal_id == proposal_id
        and type(proof.observed_at_generation) is int
        and proof.scope.as_of_generation == proof.observed_at_generation
        and type(proof.rcl_tip) is RclTip
        and proof.rcl_tip.last_seq == proof.observed_at_generation
        and proof.side is PositionSide(direction)
        and type(proof.held_quantity) is Decimal
        and proof.held_quantity.is_finite()
        and proof.held_quantity > 0
        and proof.provenance == "kis-mock-stock"
        and type(proof.trading_date) is str
        and type(proof.age_origin_ms) is int
        and proof.age_origin_ms >= 0
        and type(proof.max_age_ms) is int
        and proof.max_age_ms > 0
    )


def _proof_fields(proof: HeldPositionProof | None) -> dict[str, object]:
    """The broker-held half of the audit row — every field absent when no proof was accepted."""
    tip: RclTip | None = None if proof is None else proof.rcl_tip
    return {
        "proof_provenance": None if proof is None else proof.provenance,
        "held_quantity": None if proof is None else str(proof.held_quantity),
        "proof_trading_date": None if proof is None else proof.trading_date,
        "proof_age_origin_ms": None if proof is None else proof.age_origin_ms,
        "proof_max_age_ms": None if proof is None else proof.max_age_ms,
        "proof_generation": None if proof is None else proof.observed_at_generation,
        "proof_rcl_writer_epoch": None if tip is None else tip.writer_epoch,
        "proof_rcl_last_seq": None if tip is None else tip.last_seq,
    }


def _bound_fields(bound: EntryCloseBound | None) -> dict[str, object]:
    """The durable entry half of the audit row (#1011/#1012 L3)."""
    return {
        "entry_reservation_id": None if bound is None else bound.entry_reservation_id,
        "entry_quantity": (
            None
            if bound is None or bound.entry_quantity is None
            else str(bound.entry_quantity)
        ),
        "entry_prior_closed": (
            None
            if bound is None or bound.prior_closed is None
            else str(bound.prior_closed)
        ),
        "entry_remaining": (
            None if bound is None or bound.remaining is None else str(bound.remaining)
        ),
        "entry_bound_refusal": None if bound is None else bound.refusal,
    }


def close_effect_audit(
    direction: str | None,
    status: str,
    proof: HeldPositionProof | None,
    effect: Decimal | None,
    *,
    bound: EntryCloseBound | None = None,
) -> dict[str, object]:
    """Return bounded proof/bound metadata for the durable risk observation row.

    ``bound`` carries the durable entry cap both authorities now read (#1011/#1012 L3), so a
    refused CLOSE says WHICH cap refused it — the broker holding, or what remains of the TOS
    entry — rather than leaving the reader to guess from the status alone.
    """
    accepted_proof = (
        proof
        if status in PROOF_BEARING_STATUSES and type(proof) is HeldPositionProof
        else None
    )
    return {
        "direction": direction,
        "proof_status": status,
        **_proof_fields(accepted_proof),
        "max_credible_command_effect": str(effect) if effect is not None else None,
        **_bound_fields(bound),
    }
