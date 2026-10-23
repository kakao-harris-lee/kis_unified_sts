"""Tests for :mod:`tos_runtime.riskstate.position` (TOS risk state service wave, lane a)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.riskstate.position import (
    EvidencePositionReader,
    PositionObservation,
    conservative_current_usage,
    in_flight_overlap_effect,
    worst_credible_directional_usage,
)

from .conftest import FixedKeyProvider, seed_egress_result, seed_send_sealed

_ACCOUNT = "acct-1"
_INSTRUMENT = "K200F"


def _empty_observation() -> PositionObservation:
    return PositionObservation(
        scope_key=f"{_ACCOUNT}::{_INSTRUMENT}",
        confirmed_net=Decimal(0),
        unknown_buy=Decimal(0),
        unknown_sell=Decimal(0),
        in_flight_buy=Decimal(0),
        in_flight_sell=Decimal(0),
        attempts_seen=0,
        sources=(),
    )


def test_empty_store_yields_all_zero_observation(
    evidence_store: SqliteEvidenceStore,
) -> None:
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs == _empty_observation()
    assert worst_credible_directional_usage(obs) == Decimal(0)
    assert conservative_current_usage(obs) == Decimal(0)
    assert in_flight_overlap_effect(obs) == Decimal(0)


def test_confirmed_fill_signed_by_sealed_side(
    evidence_store: SqliteEvidenceStore,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="3",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="3",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.confirmed_net == Decimal(3)
    assert obs.unknown_buy == Decimal(0) and obs.unknown_sell == Decimal(0)
    assert obs.in_flight_buy == Decimal(0) and obs.in_flight_sell == Decimal(0)
    assert obs.attempts_seen == 1
    assert "evidence:SEND_SEALED" in obs.sources
    assert "evidence:EGRESS_RESULT_CONSUMED" in obs.sources
    assert worst_credible_directional_usage(obs) == Decimal(3)


def test_sell_side_fill_is_negative_net(evidence_store: SqliteEvidenceStore) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="SELL",
        quantity="5",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="5",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.confirmed_net == Decimal(-5)
    assert worst_credible_directional_usage(obs) == Decimal(5)


def test_unmatched_result_is_in_flight_in_full_sealed_quantity(
    evidence_store: SqliteEvidenceStore,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="4",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="RESULT_UNMATCHED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="4",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.confirmed_net == Decimal(0)
    assert obs.unknown_buy == Decimal(0)
    assert obs.unknown_sell == Decimal(0)
    assert obs.in_flight_buy == Decimal(4)
    assert "evidence:RESULT_UNMATCHED" in obs.sources
    assert worst_credible_directional_usage(obs) == Decimal(4)


def test_sealed_with_no_terminal_result_is_in_flight(
    evidence_store: SqliteEvidenceStore,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="2",
        event_id="ev-1",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.confirmed_net == Decimal(0)
    assert obs.unknown_buy == Decimal(0)
    assert obs.in_flight_buy == Decimal(2)
    assert obs.in_flight_sell == Decimal(0)
    assert in_flight_overlap_effect(obs) == Decimal(2)
    # Not part of worst_credible_directional_usage's non-in-flight-only sibling.
    assert conservative_current_usage(obs) == Decimal(0)
    assert worst_credible_directional_usage(obs) == Decimal(2)


def test_consumed_row_governs_over_a_prior_unmatched_row(
    evidence_store: SqliteEvidenceStore,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="6",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="RESULT_UNMATCHED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="6",
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="6",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.confirmed_net == Decimal(6)
    assert obs.unknown_buy == Decimal(0)


def test_zero_fill_terminal_outcome_is_confirmed_not_unknown(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """A TERMINAL zero-fill result (here ``REJECT``; ``tos.engine.TERMINAL_RESULT_KINDS``) is a
    POSITIVELY resolved fact — not an unknown, not in flight — per the module docstring's
    classification table. (A bare ``ACK`` is NOT terminal: see
    ``test_consumed_nonterminal_zero_fill_retains_full_sealed_quantity``.)"""
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="9",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity=None,
        egress_result_kind="REJECT",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.confirmed_net == Decimal(0)
    assert obs.unknown_buy == Decimal(0)
    assert obs.in_flight_buy == Decimal(0)


# ===========================================================================
# Lane A re-review #7 (high) — consumed NON-terminal results keep outstanding exposure
# ===========================================================================

_SIDE_SIGNS = (("BUY", 1), ("SELL", -1))


def _reader(store: SqliteEvidenceStore) -> EvidencePositionReader:
    return EvidencePositionReader(
        store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )


def _seal_ten(store: SqliteEvidenceStore, side: str) -> None:
    seed_send_sealed(
        store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side=side,
        quantity="10",
        event_id="ev-1",
    )


def _consume(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    filled: str | None,
    remaining: str | None,
) -> None:
    seed_egress_result(
        store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity=filled,
        egress_result_kind=kind,
        remaining_quantity=remaining,
    )


def _in_flight_toward(obs: PositionObservation, sign: int) -> Decimal:
    return obs.in_flight_buy if sign > 0 else obs.in_flight_sell


def _in_flight_against(obs: PositionObservation, sign: int) -> Decimal:
    return obs.in_flight_sell if sign > 0 else obs.in_flight_buy


@pytest.mark.parametrize(("side", "sign"), _SIDE_SIGNS)
@pytest.mark.parametrize("kind", ["ACK", "TIMEOUT", "UNKNOWN"])
def test_consumed_nonterminal_zero_fill_retains_full_sealed_quantity(
    evidence_store: SqliteEvidenceStore, kind: str, side: str, sign: int
) -> None:
    """``core.py`` emits ``EGRESS_RESULT_CONSUMED`` for every APPLIED result, including the
    non-terminal ``ACK`` / ``TIMEOUT`` / ``UNKNOWN``. A sealed 10-lot whose only consumed
    result is one of those has resolved NOTHING — the full 10 stays outstanding (in flight,
    the bucket it held before any result arrived), never 0."""
    _seal_ten(evidence_store, side)
    _consume(evidence_store, kind=kind, filled=None, remaining=None)
    obs = _reader(evidence_store).observe()
    assert obs.confirmed_net == Decimal(0)
    assert _in_flight_toward(obs, sign) == Decimal(10)
    assert _in_flight_against(obs, sign) == Decimal(0)
    assert obs.unknown_buy == Decimal(0) and obs.unknown_sell == Decimal(0)
    assert worst_credible_directional_usage(obs) == Decimal(10)
    assert in_flight_overlap_effect(obs) == Decimal(10)


@pytest.mark.parametrize(("side", "sign"), _SIDE_SIGNS)
def test_consumed_partial_fill_confirms_filled_and_retains_remainder(
    evidence_store: SqliteEvidenceStore, side: str, sign: int
) -> None:
    """PARTIAL_FILL 7 filled / 3 remaining: confirmed 7 signed by side, 3 still outstanding —
    worst-credible usage is 10, not 7."""
    _seal_ten(evidence_store, side)
    _consume(evidence_store, kind="PARTIAL_FILL", filled="7", remaining="3")
    obs = _reader(evidence_store).observe()
    assert obs.confirmed_net == Decimal(7 * sign)
    assert _in_flight_toward(obs, sign) == Decimal(3)
    assert _in_flight_against(obs, sign) == Decimal(0)
    assert worst_credible_directional_usage(obs) == Decimal(10)
    assert conservative_current_usage(obs) == Decimal(7)


@pytest.mark.parametrize(("side", "sign"), _SIDE_SIGNS)
def test_consumed_terminal_full_fill_leaves_nothing_outstanding(
    evidence_store: SqliteEvidenceStore, side: str, sign: int
) -> None:
    _seal_ten(evidence_store, side)
    _consume(evidence_store, kind="FULL_FILL", filled="10", remaining="0")
    obs = _reader(evidence_store).observe()
    assert obs.confirmed_net == Decimal(10 * sign)
    assert in_flight_overlap_effect(obs) == Decimal(0)
    assert obs.unknown_buy == Decimal(0) and obs.unknown_sell == Decimal(0)
    assert worst_credible_directional_usage(obs) == Decimal(10)


@pytest.mark.parametrize(("side", "sign"), _SIDE_SIGNS)
@pytest.mark.parametrize("kind", ["REJECT", "CANCEL_ACK", "EXPIRED"])
def test_consumed_terminal_after_partial_confirms_only_the_filled_part(
    evidence_store: SqliteEvidenceStore, kind: str, side: str, sign: int
) -> None:
    """A terminal REJECT / CANCEL_ACK / EXPIRED after a 7/3 partial: the kernel's stored
    reservation still carries ``filled=7, remaining=3`` on the terminal row, but the attempt now
    HAS a terminal result (DR-0003 §2.2) — confirmed 7, nothing outstanding."""
    _seal_ten(evidence_store, side)
    _consume(evidence_store, kind="PARTIAL_FILL", filled="7", remaining="3")
    _consume(evidence_store, kind=kind, filled="7", remaining="3")
    obs = _reader(evidence_store).observe()
    assert obs.confirmed_net == Decimal(7 * sign)
    assert in_flight_overlap_effect(obs) == Decimal(0)
    assert obs.unknown_buy == Decimal(0) and obs.unknown_sell == Decimal(0)


@pytest.mark.parametrize(("side", "sign"), _SIDE_SIGNS)
def test_result_sequence_resolves_by_the_latest_consumed_row(
    evidence_store: SqliteEvidenceStore, side: str, sign: int
) -> None:
    """ACK -> PARTIAL(4/6) -> FULL_FILL(10/0), in commit (``seq``) order: each prefix is
    classified by its own latest row, and the full sequence resolves to confirmed 10."""
    _seal_ten(evidence_store, side)
    _consume(evidence_store, kind="ACK", filled=None, remaining=None)
    obs = _reader(evidence_store).observe()
    assert (obs.confirmed_net, _in_flight_toward(obs, sign)) == (
        Decimal(0),
        Decimal(10),
    )
    _consume(evidence_store, kind="PARTIAL_FILL", filled="4", remaining="6")
    obs = _reader(evidence_store).observe()
    assert (obs.confirmed_net, _in_flight_toward(obs, sign)) == (
        Decimal(4 * sign),
        Decimal(6),
    )
    _consume(evidence_store, kind="FULL_FILL", filled="10", remaining="0")
    obs = _reader(evidence_store).observe()
    assert obs.confirmed_net == Decimal(10 * sign)
    assert in_flight_overlap_effect(obs) == Decimal(0)


@pytest.mark.parametrize(("side", "sign"), _SIDE_SIGNS)
def test_nonterminal_result_after_terminal_reopens_the_remainder(
    evidence_store: SqliteEvidenceStore, side: str, sign: int
) -> None:
    """The latest row governs in BOTH directions: an applied ``ACK`` after a ``REJECT`` (a
    contradictory sequence the kernel's rank machinery still applies, since ``ACK`` moves no
    capacity) leaves the latest result non-terminal, so the unfilled 10 is outstanding again —
    fail-closed, never "some earlier row was terminal"."""
    _seal_ten(evidence_store, side)
    _consume(evidence_store, kind="REJECT", filled=None, remaining=None)
    _consume(evidence_store, kind="ACK", filled=None, remaining=None)
    obs = _reader(evidence_store).observe()
    assert _in_flight_toward(obs, sign) == Decimal(10)


@pytest.mark.parametrize("kind", [None, 7, "", "FILLED_MAYBE"])
def test_unrecognized_result_kind_is_not_terminal(
    evidence_store: SqliteEvidenceStore, kind: object
) -> None:
    """A missing / non-string / unrecognized ``egress_result_kind`` proves no terminality
    (fail-closed) — the full sealed 10 stays outstanding."""
    _seal_ten(evidence_store, "BUY")
    evidence_store.append(
        {
            "attempt_id": "a1",
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": kind,
            "filled_quantity": None,
            "remaining_quantity": None,
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    obs = _reader(evidence_store).observe()
    assert obs.in_flight_buy == Decimal(10)


@pytest.mark.parametrize("kind", ["ACK", "PARTIAL_FILL"])
def test_unrecognized_side_on_nonterminal_consumed_result_is_both_directions(
    evidence_store: SqliteEvidenceStore, kind: str
) -> None:
    """Unrecognized side token + non-terminal consumed result: the filled part fails closed to
    UNKNOWN in both directions, the outstanding remainder to IN-FLIGHT in both directions.
    """
    _seal_ten(evidence_store, "SIDEWAYS")
    filled, remaining = ("7", "3") if kind == "PARTIAL_FILL" else (None, None)
    _consume(evidence_store, kind=kind, filled=filled, remaining=remaining)
    obs = _reader(evidence_store).observe()
    expected_filled = Decimal(7) if kind == "PARTIAL_FILL" else Decimal(0)
    expected_outstanding = Decimal(10) - expected_filled
    assert obs.confirmed_net == Decimal(0)
    assert (obs.unknown_buy, obs.unknown_sell) == (expected_filled, expected_filled)
    assert (obs.in_flight_buy, obs.in_flight_sell) == (
        expected_outstanding,
        expected_outstanding,
    )
    assert worst_credible_directional_usage(obs) == Decimal(10)


def test_out_of_scope_attempt_is_excluded(evidence_store: SqliteEvidenceStore) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account="other-account",
        instrument=_INSTRUMENT,
        side="BUY",
        quantity="10",
        event_id="ev-1",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs == _empty_observation()


def test_unrecognized_side_is_unknown_in_both_directions(
    evidence_store: SqliteEvidenceStore,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="SIDEWAYS",
        quantity="7",
        event_id="ev-1",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    obs = reader.observe()
    assert obs.in_flight_buy == Decimal(7)
    assert obs.in_flight_sell == Decimal(7)


def test_long_short_mirror_symmetry(evidence_store: SqliteEvidenceStore) -> None:
    """NEW_SHORT mirror: negating the side and swapping evidence carriers reproduces the
    negated usage (plan §5 demonstration (7))."""
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side="SELL",
        quantity="3",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="3",
    )
    reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    short_obs = reader.observe()

    long_store = SqliteEvidenceStore(
        evidence_store.path.parent / "mirror.sqlite3",
        key_provider=FixedKeyProvider(),
    )
    try:
        seed_send_sealed(
            long_store,
            attempt_id="a1",
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            side="BUY",
            quantity="3",
            event_id="ev-1",
        )
        seed_egress_result(
            long_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="a1",
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            filled_quantity="3",
        )
        long_reader = EvidencePositionReader(
            long_store,
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            buy_side_token="BUY",
            sell_side_token="SELL",
        )
        long_obs = long_reader.observe()
    finally:
        long_store.close()

    assert short_obs.confirmed_net == -long_obs.confirmed_net
    assert worst_credible_directional_usage(
        short_obs
    ) == worst_credible_directional_usage(long_obs)


# ===========================================================================
# Property tests (hypothesis) — pure functions only
# ===========================================================================

_NONNEG_DECIMAL = st.decimals(
    min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False, places=2
).map(Decimal)


@given(
    confirmed_net=st.decimals(
        min_value=-1_000_000,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ).map(Decimal),
    unknown_buy=_NONNEG_DECIMAL,
    unknown_sell=_NONNEG_DECIMAL,
    in_flight_buy=_NONNEG_DECIMAL,
    in_flight_sell=_NONNEG_DECIMAL,
    extra_unknown_buy=_NONNEG_DECIMAL,
)
def test_adding_unknown_attempt_never_decreases_worst_credible_usage(
    confirmed_net: Decimal,
    unknown_buy: Decimal,
    unknown_sell: Decimal,
    in_flight_buy: Decimal,
    in_flight_sell: Decimal,
    extra_unknown_buy: Decimal,
) -> None:
    base = PositionObservation(
        scope_key="s",
        confirmed_net=confirmed_net,
        unknown_buy=unknown_buy,
        unknown_sell=unknown_sell,
        in_flight_buy=in_flight_buy,
        in_flight_sell=in_flight_sell,
        attempts_seen=1,
        sources=(),
    )
    grown = PositionObservation(
        scope_key="s",
        confirmed_net=confirmed_net,
        unknown_buy=unknown_buy + extra_unknown_buy,
        unknown_sell=unknown_sell,
        in_flight_buy=in_flight_buy,
        in_flight_sell=in_flight_sell,
        attempts_seen=2,
        sources=(),
    )
    assert worst_credible_directional_usage(grown) >= worst_credible_directional_usage(
        base
    )


@given(
    confirmed_net=st.decimals(
        min_value=-1_000_000,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ).map(Decimal),
    unknown_buy=_NONNEG_DECIMAL,
    unknown_sell=_NONNEG_DECIMAL,
    in_flight_buy=_NONNEG_DECIMAL,
    in_flight_sell=_NONNEG_DECIMAL,
)
def test_worst_credible_usage_at_least_confirmed_magnitude(
    confirmed_net: Decimal,
    unknown_buy: Decimal,
    unknown_sell: Decimal,
    in_flight_buy: Decimal,
    in_flight_sell: Decimal,
) -> None:
    obs = PositionObservation(
        scope_key="s",
        confirmed_net=confirmed_net,
        unknown_buy=unknown_buy,
        unknown_sell=unknown_sell,
        in_flight_buy=in_flight_buy,
        in_flight_sell=in_flight_sell,
        attempts_seen=1,
        sources=(),
    )
    assert worst_credible_directional_usage(obs) >= abs(confirmed_net)


@given(
    confirmed_net=st.decimals(
        min_value=-1_000_000,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ).map(Decimal),
    unknown_buy=_NONNEG_DECIMAL,
    unknown_sell=_NONNEG_DECIMAL,
)
def test_long_short_mirror_symmetry_property(
    confirmed_net: Decimal, unknown_buy: Decimal, unknown_sell: Decimal
) -> None:
    """Negating every side (confirmed_net sign flips, buy/sell buckets swap) leaves
    :func:`worst_credible_directional_usage` unchanged (plan §2.2's own symmetry property).
    """
    obs = PositionObservation(
        scope_key="s",
        confirmed_net=confirmed_net,
        unknown_buy=unknown_buy,
        unknown_sell=unknown_sell,
        in_flight_buy=Decimal(0),
        in_flight_sell=Decimal(0),
        attempts_seen=1,
        sources=(),
    )
    mirrored = PositionObservation(
        scope_key="s",
        confirmed_net=-confirmed_net,
        unknown_buy=unknown_sell,
        unknown_sell=unknown_buy,
        in_flight_buy=Decimal(0),
        in_flight_sell=Decimal(0),
        attempts_seen=1,
        sources=(),
    )
    assert worst_credible_directional_usage(obs) == worst_credible_directional_usage(
        mirrored
    )


def _reader(store: SqliteEvidenceStore) -> EvidencePositionReader:
    return EvidencePositionReader(
        store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize(
    "consumed_kind,consumed_fill,confirmed,outstanding",
    [
        ("CANCEL_ACK", None, 0, 10),
        ("CANCEL_ACK", "4", 4, 6),
    ],
)
def test_unmatched_result_after_terminal_consumed_reopens_the_attempt(
    evidence_store: SqliteEvidenceStore,
    side: str,
    consumed_kind: str,
    consumed_fill: str | None,
    confirmed: int,
    outstanding: int,
) -> None:
    seed_send_sealed(
        evidence_store,
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        side=side,
        quantity="10",
        event_id="ev-1",
    )
    seed_egress_result(
        evidence_store,
        kind="EGRESS_RESULT_CONSUMED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity=consumed_fill,
        egress_result_kind=consumed_kind,
    )
    seed_egress_result(
        evidence_store,
        kind="RESULT_UNMATCHED",
        attempt_id="a1",
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        filled_quantity="10",
        egress_result_kind="FULL_FILL",
    )
    obs = _reader(evidence_store).observe()
    sign = 1 if side == "BUY" else -1
    assert obs.confirmed_net == sign * confirmed
    toward, against = (
        (obs.in_flight_buy, obs.in_flight_sell)
        if side == "BUY"
        else (obs.in_flight_sell, obs.in_flight_buy)
    )
    assert toward == Decimal(outstanding)
    assert against == Decimal(0)
    assert (obs.unknown_buy, obs.unknown_sell) == (Decimal(0), Decimal(0))
