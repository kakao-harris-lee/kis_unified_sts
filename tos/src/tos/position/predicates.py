"""tos.position pure predicates (kernel round #4 K-2)."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from decimal import Decimal

from tos.position.records import ConsumedResult, PositionObservation, SealedSend

__all__ = [
    "worst_credible_directional_usage",
    "conservative_current_usage",
    "in_flight_overlap_effect",
    "sign_of",
    "classify_sealed_sends",
]


def worst_credible_directional_usage(obs: PositionObservation) -> Decimal:
    """The worst-credible directional usage magnitude (plan §2.2, pure function)."""
    long_case = obs.confirmed_net + obs.unknown_buy + obs.in_flight_buy
    short_case = obs.confirmed_net - obs.unknown_sell - obs.in_flight_sell
    return max(abs(long_case), abs(short_case))


def conservative_current_usage(obs: PositionObservation) -> Decimal:
    """Like :func:`worst_credible_directional_usage`, but WITHOUT the in-flight terms (plan"""
    long_case = obs.confirmed_net + obs.unknown_buy
    short_case = obs.confirmed_net - obs.unknown_sell
    return max(abs(long_case), abs(short_case))


def in_flight_overlap_effect(obs: PositionObservation) -> Decimal:
    """The magnitude an ARE ``ProjectedCell.required_concurrent_overlap_effect`` would take"""
    return obs.in_flight_buy + obs.in_flight_sell


def sign_of(
    side: str | None, *, buy_side_token: str, sell_side_token: str
) -> int | None:
    """The directional sign for ``side`` against the two injected tokens, or ``None`` when it"""
    if side == buy_side_token:
        return 1
    if side == sell_side_token:
        return -1
    return None


def _outstanding_after(
    consumed: ConsumedResult,
    sealed_quantity: Decimal,
    *,
    terminal_result_kinds: AbstractSet[str],
    reopened: bool,
) -> Decimal:
    """The still-outstanding quantity of an attempt whose latest applied result is"""
    if (
        not reopened
        and consumed.result_kind is not None
        and consumed.result_kind in terminal_result_kinds
    ):
        return Decimal(0)
    filled = consumed.filled_quantity or Decimal(0)
    remaining = consumed.remaining_quantity or Decimal(0)
    return max(remaining, sealed_quantity - filled, Decimal(0))


def classify_sealed_sends(
    sealed: tuple[SealedSend, ...],
    *,
    consumed_by_attempt: Mapping[str, ConsumedResult],
    unmatched_attempts: AbstractSet[str],
    buy_side_token: str,
    sell_side_token: str,
    terminal_result_kinds: AbstractSet[str],
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, int]:
    """The module docstring's classification table, applied to every sealed send. Returns"""
    confirmed_net = Decimal(0)
    unknown_buy = Decimal(0)
    unknown_sell = Decimal(0)
    in_flight_buy = Decimal(0)
    in_flight_sell = Decimal(0)
    attempts_seen = 0
    for send in sealed:
        attempts_seen += 1
        sign = sign_of(
            send.side, buy_side_token=buy_side_token, sell_side_token=sell_side_token
        )
        quantity = send.quantity if send.quantity is not None else Decimal(0)
        consumed = consumed_by_attempt.get(send.attempt_id)
        if consumed is not None:
            filled = consumed.filled_quantity or Decimal(0)
            outstanding = _outstanding_after(
                consumed,
                quantity,
                terminal_result_kinds=terminal_result_kinds,
                reopened=send.attempt_id in unmatched_attempts,
            )
            if sign is None:
                unknown_buy += filled
                unknown_sell += filled
                in_flight_buy += outstanding
                in_flight_sell += outstanding
                continue
            confirmed_net += sign * filled
            if sign > 0:
                in_flight_buy += outstanding
            else:
                in_flight_sell += outstanding
            continue
        if sign is None:
            in_flight_buy += quantity
            in_flight_sell += quantity
            continue
        if sign > 0:
            in_flight_buy += quantity
        else:
            in_flight_sell += quantity
    return (
        confirmed_net,
        unknown_buy,
        unknown_sell,
        in_flight_buy,
        in_flight_sell,
        attempts_seen,
    )
