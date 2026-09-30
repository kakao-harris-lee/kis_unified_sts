"""tos.position pure predicates — ported from tos_runtime.riskstate.position (kernel round #4
K-2; DR-0003 §2.2). These tests exercise the kernel package directly (no evidence-store I/O —
that stays runtime-side); the runtime's own ``tos_runtime/tests/riskstate/test_position.py``
covers the I/O + wiring end to end and must keep passing unchanged (K-2 end condition).
"""

from __future__ import annotations

from decimal import Decimal

from tos.position import (
    PositionObservation,
    SealedSend,
    classify_sealed_sends,
    conservative_current_usage,
    in_flight_overlap_effect,
    sign_of,
    worst_credible_directional_usage,
)

_BUY = "BUY"
_SELL = "SELL"


def _obs(**overrides: object) -> PositionObservation:
    base: dict[str, object] = {
        "scope_key": "acct-1::K200F",
        "confirmed_net": Decimal(0),
        "unknown_buy": Decimal(0),
        "unknown_sell": Decimal(0),
        "in_flight_buy": Decimal(0),
        "in_flight_sell": Decimal(0),
        "attempts_seen": 0,
        "sources": (),
    }
    base.update(overrides)
    return PositionObservation(**base)  # type: ignore[arg-type]


def test_worst_credible_usage_pushes_unknowns_to_the_larger_direction() -> None:
    """(plan §2.2) UNKNOWN consumes conservative capacity — never assumed safe."""
    obs = _obs(
        confirmed_net=Decimal(5),
        unknown_buy=Decimal(3),
        unknown_sell=Decimal(1),
        in_flight_buy=Decimal(2),
        in_flight_sell=Decimal(0),
    )
    # long_case = 5+3+2=10, short_case = |5-1-0| = 4 -> worst is 10.
    assert worst_credible_directional_usage(obs) == Decimal(10)


def test_conservative_current_usage_excludes_in_flight() -> None:
    obs = _obs(
        confirmed_net=Decimal(5),
        unknown_buy=Decimal(3),
        unknown_sell=Decimal(1),
        in_flight_buy=Decimal(100),
        in_flight_sell=Decimal(100),
    )
    # long_case = 5+3=8, short_case=|5-1|=4 -> 8, unaffected by in-flight.
    assert conservative_current_usage(obs) == Decimal(8)


def test_in_flight_overlap_effect_sums_both_buckets_never_nets() -> None:
    obs = _obs(in_flight_buy=Decimal(3), in_flight_sell=Decimal(4))
    assert in_flight_overlap_effect(obs) == Decimal(7)


def test_sign_of_unrecognized_side_is_none_fail_closed() -> None:
    assert sign_of(_BUY, buy_side_token=_BUY, sell_side_token=_SELL) == 1
    assert sign_of(_SELL, buy_side_token=_BUY, sell_side_token=_SELL) == -1
    assert sign_of("SHORT", buy_side_token=_BUY, sell_side_token=_SELL) is None
    assert sign_of(None, buy_side_token=_BUY, sell_side_token=_SELL) is None


def test_classify_confirmed_fill_signed_by_side() -> None:
    sealed = (SealedSend(attempt_id="a1", side=_BUY, quantity=Decimal(10)),)
    result = classify_sealed_sends(
        sealed,
        consumed_by_attempt={"a1": Decimal(7)},
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
    )
    confirmed_net, unknown_buy, unknown_sell, in_flight_buy, in_flight_sell, seen = (
        result
    )
    assert confirmed_net == Decimal(7)
    assert (unknown_buy, unknown_sell, in_flight_buy, in_flight_sell) == (
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal(0),
    )
    assert seen == 1


def test_classify_unmatched_result_counts_full_sealed_quantity_as_unknown() -> None:
    sealed = (SealedSend(attempt_id="a1", side=_SELL, quantity=Decimal(10)),)
    result = classify_sealed_sends(
        sealed,
        consumed_by_attempt={},
        unmatched_attempts=frozenset({"a1"}),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
    )
    confirmed_net, unknown_buy, unknown_sell, in_flight_buy, in_flight_sell, seen = (
        result
    )
    assert confirmed_net == Decimal(0)
    assert unknown_sell == Decimal(10)
    assert unknown_buy == Decimal(0)
    assert (in_flight_buy, in_flight_sell) == (Decimal(0), Decimal(0))


def test_classify_no_terminal_result_is_in_flight() -> None:
    sealed = (SealedSend(attempt_id="a1", side=_BUY, quantity=Decimal(5)),)
    result = classify_sealed_sends(
        sealed,
        consumed_by_attempt={},
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
    )
    _, unknown_buy, unknown_sell, in_flight_buy, in_flight_sell, _ = result
    assert in_flight_buy == Decimal(5)
    assert (unknown_buy, unknown_sell, in_flight_sell) == (
        Decimal(0),
        Decimal(0),
        Decimal(0),
    )


def test_classify_unrecognized_side_on_confirmed_fill_is_unknown_both_directions() -> (
    None
):
    """An unrecognized side token on a CONFIRMED fill must not silently drop the confirmed
    magnitude — it fails closed into UNKNOWN in BOTH directions (never a guessed direction).
    """
    sealed = (SealedSend(attempt_id="a1", side="MYSTERY", quantity=Decimal(9)),)
    result = classify_sealed_sends(
        sealed,
        consumed_by_attempt={"a1": Decimal(9)},
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
    )
    confirmed_net, unknown_buy, unknown_sell, _, _, _ = result
    assert confirmed_net == Decimal(0)
    assert unknown_buy == Decimal(9)
    assert unknown_sell == Decimal(9)


def test_classify_missing_quantity_treated_as_zero_never_guessed() -> None:
    sealed = (SealedSend(attempt_id="a1", side=_BUY, quantity=None),)
    result = classify_sealed_sends(
        sealed,
        consumed_by_attempt={},
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
    )
    _, _, _, in_flight_buy, in_flight_sell, _ = result
    assert in_flight_buy == Decimal(0)
    assert in_flight_sell == Decimal(0)
