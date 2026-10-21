"""tos.position pure predicates — ported from tos_runtime.riskstate.position (kernel round #4
K-2; DR-0003 §2.2). These tests exercise the kernel package directly (no evidence-store I/O —
that stays runtime-side); the runtime's own ``tos_runtime/tests/riskstate/test_position.py``
covers the I/O + wiring end to end and must keep passing unchanged (K-2 end condition).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.position import (
    ConsumedResult,
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
#: The terminal result-kind tokens — injected exactly as the runtime reader injects
#: ``tos.engine.TERMINAL_RESULT_KINDS``'s values (pinned against it below).
_TERMINAL = frozenset({"FULL_FILL", "REJECT", "CANCEL_ACK", "EXPIRED"})


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
        consumed_by_attempt={
            "a1": ConsumedResult(
                result_kind="CANCEL_ACK",
                filled_quantity=Decimal(7),
                remaining_quantity=Decimal(3),
            )
        },
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
        terminal_result_kinds=_TERMINAL,
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
        terminal_result_kinds=_TERMINAL,
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
        terminal_result_kinds=_TERMINAL,
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
        consumed_by_attempt={
            "a1": ConsumedResult(result_kind="FULL_FILL", filled_quantity=Decimal(9))
        },
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
        terminal_result_kinds=_TERMINAL,
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
        terminal_result_kinds=_TERMINAL,
    )
    _, _, _, in_flight_buy, in_flight_sell, _ = result
    assert in_flight_buy == Decimal(0)
    assert in_flight_sell == Decimal(0)


# ===========================================================================
# Lane A re-review #7 (high): a CONSUMED result is not necessarily a TERMINAL one
# ===========================================================================

_SIDES = ((_BUY, 1), (_SELL, -1))


def _classify_one(
    side: str, consumed: ConsumedResult
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, int]:
    return classify_sealed_sends(
        (SealedSend(attempt_id="a1", side=side, quantity=Decimal(10)),),
        consumed_by_attempt={"a1": consumed},
        unmatched_attempts=frozenset(),
        buy_side_token=_BUY,
        sell_side_token=_SELL,
        terminal_result_kinds=_TERMINAL,
    )


def _as_obs(
    result: tuple[Decimal, Decimal, Decimal, Decimal, Decimal, int],
) -> PositionObservation:
    confirmed_net, unknown_buy, unknown_sell, in_flight_buy, in_flight_sell, seen = (
        result
    )
    return _obs(
        confirmed_net=confirmed_net,
        unknown_buy=unknown_buy,
        unknown_sell=unknown_sell,
        in_flight_buy=in_flight_buy,
        in_flight_sell=in_flight_sell,
        attempts_seen=seen,
    )


def _toward(obs: PositionObservation, sign: int) -> Decimal:
    return obs.in_flight_buy if sign > 0 else obs.in_flight_sell


def _against(obs: PositionObservation, sign: int) -> Decimal:
    return obs.in_flight_sell if sign > 0 else obs.in_flight_buy


def _partial(kind: str = "PARTIAL_FILL", remaining: int = 3) -> ConsumedResult:
    return ConsumedResult(
        result_kind=kind,
        filled_quantity=Decimal(7),
        remaining_quantity=Decimal(remaining),
    )


def test_terminal_tokens_match_the_engine_vocabulary() -> None:
    """The literal this suite injects is the kernel's own terminal set, not a second copy."""
    from tos.engine import TERMINAL_RESULT_KINDS

    assert {kind.value for kind in TERMINAL_RESULT_KINDS} == _TERMINAL


@pytest.mark.parametrize(("side", "sign"), _SIDES)
@pytest.mark.parametrize("kind", ["ACK", "TIMEOUT", "UNKNOWN"])
def test_nonterminal_zero_fill_keeps_full_sealed_quantity_outstanding(
    kind: str, side: str, sign: int
) -> None:
    """The reproduced defect: a sealed 10-lot with one consumed ACK / TIMEOUT / UNKNOWN result
    had worst-credible usage 0. It must stay 10 — the attempt has no terminal result."""
    obs = _as_obs(_classify_one(side, ConsumedResult(result_kind=kind)))
    assert obs.confirmed_net == Decimal(0)
    assert _toward(obs, sign) == Decimal(10)
    assert _against(obs, sign) == Decimal(0)
    assert (obs.unknown_buy, obs.unknown_sell) == (Decimal(0), Decimal(0))
    assert worst_credible_directional_usage(obs) == Decimal(10)


@pytest.mark.parametrize(("side", "sign"), _SIDES)
def test_partial_fill_confirms_filled_and_keeps_remainder_outstanding(
    side: str, sign: int
) -> None:
    """The reproduced defect: PARTIAL 7 filled / 3 remaining gave worst-credible 7, not 10."""
    obs = _as_obs(_classify_one(side, _partial()))
    assert obs.confirmed_net == Decimal(7 * sign)
    assert _toward(obs, sign) == Decimal(3)
    assert _against(obs, sign) == Decimal(0)
    assert worst_credible_directional_usage(obs) == Decimal(10)


@pytest.mark.parametrize(("side", "sign"), _SIDES)
def test_terminal_full_fill_leaves_nothing_outstanding(side: str, sign: int) -> None:
    obs = _as_obs(
        _classify_one(
            side,
            ConsumedResult(
                result_kind="FULL_FILL",
                filled_quantity=Decimal(10),
                remaining_quantity=Decimal(0),
            ),
        )
    )
    assert obs.confirmed_net == Decimal(10 * sign)
    assert in_flight_overlap_effect(obs) == Decimal(0)
    assert (obs.unknown_buy, obs.unknown_sell) == (Decimal(0), Decimal(0))


@pytest.mark.parametrize(("side", "sign"), _SIDES)
@pytest.mark.parametrize("kind", ["REJECT", "CANCEL_ACK", "EXPIRED"])
def test_terminal_zero_or_partial_fill_releases_the_unfilled_remainder(
    kind: str, side: str, sign: int
) -> None:
    """DR-0003 §2.2 counts in full only attempts with NO terminal result; a terminal
    REJECT / CANCEL_ACK / EXPIRED resolves the unfilled remainder (confirmed = filled).
    """
    zero = _as_obs(_classify_one(side, ConsumedResult(result_kind=kind)))
    assert zero.confirmed_net == Decimal(0)
    assert in_flight_overlap_effect(zero) == Decimal(0)
    after_partial = _as_obs(_classify_one(side, _partial(kind)))
    assert after_partial.confirmed_net == Decimal(7 * sign)
    assert in_flight_overlap_effect(after_partial) == Decimal(0)


@pytest.mark.parametrize("kind", [None, "", "FILLED_MAYBE", "full_fill"])
def test_unrecognized_result_kind_is_not_terminal(kind: str | None) -> None:
    """A missing / unrecognized kind proves no terminality — fail-closed, 10 outstanding."""
    obs = _as_obs(_classify_one(_BUY, ConsumedResult(result_kind=kind)))
    assert obs.in_flight_buy == Decimal(10)


def test_outstanding_is_never_below_sealed_minus_filled() -> None:
    """A non-terminal row whose ``remaining_quantity`` under-reports (or omits) the unfilled
    part never shrinks it below ``sealed - filled``; an over-report is kept (the larger of the
    two governs)."""
    under = _as_obs(_classify_one(_BUY, _partial(remaining=1)))
    assert under.in_flight_buy == Decimal(3)
    omitted = _as_obs(
        _classify_one(
            _BUY, ConsumedResult(result_kind="ACK", filled_quantity=Decimal(4))
        )
    )
    assert omitted.in_flight_buy == Decimal(6)
    over = _as_obs(_classify_one(_BUY, _partial(remaining=5)))
    assert over.in_flight_buy == Decimal(5)


def test_unrecognized_side_on_nonterminal_result_is_both_directions() -> None:
    obs = _as_obs(_classify_one("MYSTERY", _partial()))
    assert obs.confirmed_net == Decimal(0)
    assert (obs.unknown_buy, obs.unknown_sell) == (Decimal(7), Decimal(7))
    assert (obs.in_flight_buy, obs.in_flight_sell) == (Decimal(3), Decimal(3))
    assert worst_credible_directional_usage(obs) == Decimal(10)


@pytest.mark.parametrize("kind", ["ACK", "TIMEOUT", "UNKNOWN"])
@pytest.mark.parametrize("side", [_BUY, _SELL])
@pytest.mark.parametrize("prior_net", [-10, 0, 10])
def test_zero_fill_nonterminal_result_never_lowers_the_decision_sum(
    kind: str, side: str, prior_net: int
) -> None:
    """The bucket choice's own justification, made mechanical. ARE grants iff
    ``requested_increment <= headroom``, i.e. ``conservative_current_usage + command + overlap
    <= limit``. A zero-fill NON-terminal result must leave ``conservative + overlap`` exactly
    where the same attempt with NO result at all (sealed, in flight) left it — against a prior
    confirmed position in either direction. (Routing the remainder to UNKNOWN instead would
    fail this for an opposite-side attempt: prior +10 and an unknown 10-lot sell give 10, not
    the 20 the sealed-in-flight state gives.)"""
    prior_side = _BUY if prior_net >= 0 else _SELL
    sealed = (
        SealedSend(
            attempt_id="prior", side=prior_side, quantity=Decimal(abs(prior_net))
        ),
        SealedSend(attempt_id="a1", side=side, quantity=Decimal(10)),
    )
    prior = ConsumedResult(
        result_kind="FULL_FILL",
        filled_quantity=Decimal(abs(prior_net)),
        remaining_quantity=Decimal(0),
    )

    def decision_sum(consumed_by_attempt: dict[str, ConsumedResult]) -> Decimal:
        obs = _as_obs(
            classify_sealed_sends(
                sealed,
                consumed_by_attempt=consumed_by_attempt,
                unmatched_attempts=frozenset(),
                buy_side_token=_BUY,
                sell_side_token=_SELL,
                terminal_result_kinds=_TERMINAL,
            )
        )
        return conservative_current_usage(obs) + in_flight_overlap_effect(obs)

    no_result = decision_sum({"prior": prior})
    with_result = decision_sum({"prior": prior, "a1": ConsumedResult(result_kind=kind)})
    assert with_result == no_result
