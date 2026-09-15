"""Tests for :mod:`tos_runtime.riskstate.position` (TOS risk state service wave, lane a)."""

from __future__ import annotations

from decimal import Decimal

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


def test_unmatched_result_is_unknown_in_full_sealed_quantity(
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
    assert obs.unknown_buy == Decimal(4)
    assert obs.unknown_sell == Decimal(0)
    assert obs.in_flight_buy == Decimal(0)
    assert "evidence:RESULT_UNMATCHED" in obs.sources
    # GRANT->DENY boundary: the full unconfirmed quantity counts toward worst-credible usage.
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
    """A plain ACK/CANCEL/REJECT (no fill quantity) is a POSITIVELY resolved fact — not an
    unknown — per the module docstring's classification table."""
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
