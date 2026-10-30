"""Tests for the one-use, broker-sourced held-position proof cache."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal

import pytest
from tos.engine.records import InstrumentKey
from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)
from tos_runtime.riskstate.held_position import (
    HeldPositionCell,
    HeldPositionConfig,
    HeldPositionCurrentness,
    HeldPositionProof,
    PositionSide,
    RclTip,
)

_ACCOUNT = "acct-1"
_INSTRUMENT = "005930"
_DATE = "20261029"
_GENERATION = 23
_PROPOSAL_ID = "close-proposal-1"
_RCL_TIP = RclTip(writer_epoch=4, last_seq=23)
_SCOPE = WitnessScope(
    account=_ACCOUNT,
    instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),),
    as_of_generation=_GENERATION,
)


class _Clock:
    def __init__(
        self,
        now_ms: int = 1_000,
        today: str | None = _DATE,
        rcl_tip: RclTip | None = _RCL_TIP,
    ) -> None:
        self.now = now_ms
        self.date = today
        self.tip = rcl_tip

    def now_ms(self) -> int:
        return self.now

    def today(self) -> str | None:
        return self.date


def _snapshot(
    *,
    positions: tuple[tuple[str, Decimal], ...] = ((_INSTRUMENT, Decimal("12")),),
    positions_complete: bool = True,
    independent: bool = True,
    provenance: str = "kis-mock-stock",
    generation: int | None = _GENERATION,
    inquiry_date: str | None = _DATE,
    orders: tuple[WitnessOrder, ...] = (),
) -> WitnessSnapshot:
    return WitnessSnapshot(
        observed_at_generation=generation,
        orders=orders,
        positions=positions,
        positions_complete=positions_complete,
        provenance=provenance,
        independent_of_evidence_store=independent,
        order_inquiry_date=inquiry_date,
    )


def _cell(
    clock: _Clock | None = None,
    tip_compatible: Callable[[RclTip, RclTip], bool] | None = None,
) -> tuple[HeldPositionCell, _Clock]:
    active_clock = clock or _Clock()
    return (
        HeldPositionCell(
            config=HeldPositionConfig(max_age_ms=500),
            clock=active_clock,
            rcl_tip_reader=lambda: active_clock.tip,
            tip_compatible=tip_compatible,
        ),
        active_clock,
    )


def _publish(
    cell: HeldPositionCell,
    snapshot: WitnessSnapshot | None = None,
    *,
    confirming_snapshot: WitnessSnapshot | None = _snapshot(),
    scope: WitnessScope = _SCOPE,
    age_origin_ms: int | None = 900,
    confirming_age_origin_ms: int | None = 950,
    trading_date: str = _DATE,
    rcl_tip_at_start: RclTip | None = _RCL_TIP,
) -> bool:
    pending_token = cell.mark_pending(scope)
    return cell.publish(
        scope,
        snapshot if snapshot is not None else _snapshot(),
        confirming_snapshot=confirming_snapshot,
        age_origin_ms=age_origin_ms,
        confirming_age_origin_ms=confirming_age_origin_ms,
        trading_date=trading_date,
        rcl_tip_at_start=rcl_tip_at_start,
        pending_token=pending_token,
    )


def _consume(
    cell: HeldPositionCell,
    scope: WitnessScope = _SCOPE,
    side: PositionSide = PositionSide.LONG,
    proposal_id: str | None = _PROPOSAL_ID,
) -> HeldPositionProof | None:
    return cell.consume(scope, side, proposal_id=proposal_id)


def test_fresh_independent_complete_stock_proof_is_scoped_and_one_use() -> None:
    cell, _ = _cell()

    assert _publish(cell)
    proof = _consume(cell, _SCOPE, PositionSide.LONG)

    assert proof is not None
    assert proof.scope == _SCOPE
    assert proof.proposal_id == _PROPOSAL_ID
    assert proof.side is PositionSide.LONG
    assert proof.held_quantity == Decimal("12")
    assert proof.trading_date == _DATE
    assert proof.age_origin_ms == 900
    assert proof.max_age_ms == 500
    assert cell.validate_consumed(proof) == HeldPositionCurrentness(
        current_now_ms=1_000,
        current_trading_date=_DATE,
        rcl_tip=_RCL_TIP,
    )
    assert cell.validate_consumed(proof) is None
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_scope_mismatch_cannot_consume_or_relabel_a_published_snapshot() -> None:
    cell, _ = _cell()
    other_scope = replace(
        _SCOPE,
        instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument="000660"),),
    )

    assert _publish(cell)
    assert _consume(cell, other_scope, PositionSide.LONG) is None
    assert _consume(cell, _SCOPE, PositionSide.LONG) is not None

    bound_scope = replace(_SCOPE, attempt_ids=(_PROPOSAL_ID,))
    assert not _publish(cell, scope=bound_scope)


def test_publish_rejects_snapshot_generation_mismatched_from_captured_tip() -> None:
    cell, _ = _cell()
    mismatched_scope = replace(_SCOPE, as_of_generation=_GENERATION + 1)

    assert not _publish(
        cell,
        _snapshot(generation=_GENERATION + 1),
        confirming_snapshot=_snapshot(generation=_GENERATION + 1),
        scope=mismatched_scope,
    )


def test_publish_rejects_known_empty_rcl_tip_without_inventing_zero_generation() -> (
    None
):
    empty_tip = RclTip(writer_epoch=4, last_seq=None)
    cell, _ = _cell(_Clock(rcl_tip=empty_tip))

    assert not _publish(cell, rcl_tip_at_start=empty_tip)


def test_missing_proposal_id_burns_the_matching_snapshot() -> None:
    cell, _ = _cell()
    assert _publish(cell)

    assert _consume(cell, _SCOPE, PositionSide.LONG, proposal_id=None) is None
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_consume_for_accepts_verified_tip_gap_without_relabeling_snapshot() -> None:
    current_tip = RclTip(writer_epoch=4, last_seq=24)
    cell, clock = _cell(
        tip_compatible=lambda origin, current: origin == _RCL_TIP
        and current == current_tip
    )
    assert _publish(cell)
    clock.tip = current_tip

    proof = cell.consume_for(
        _ACCOUNT, _INSTRUMENT, PositionSide.LONG, proposal_id=_PROPOSAL_ID
    )

    assert proof is not None
    assert proof.scope == _SCOPE
    assert proof.scope.as_of_generation == _GENERATION
    assert proof.observed_at_generation == _GENERATION
    assert proof.rcl_tip == _RCL_TIP
    assert cell.validate_consumed(proof) == HeldPositionCurrentness(
        current_now_ms=1_000,
        current_trading_date=_DATE,
        rcl_tip=current_tip,
    )


@pytest.mark.parametrize(
    "current_tip",
    [
        pytest.param(RclTip(writer_epoch=5, last_seq=24), id="epoch-changed"),
        pytest.param(RclTip(writer_epoch=4, last_seq=25), id="unverified-next-row"),
    ],
)
def test_consume_for_rejects_unverified_tip_gap_and_burns_matching_proof(
    current_tip: RclTip,
) -> None:
    cell, clock = _cell(
        tip_compatible=lambda origin, current: origin == _RCL_TIP
        and current == RclTip(writer_epoch=4, last_seq=24)
    )
    assert _publish(cell)
    clock.tip = current_tip

    assert (
        cell.consume_for(
            _ACCOUNT, _INSTRUMENT, PositionSide.LONG, proposal_id=_PROPOSAL_ID
        )
        is None
    )
    clock.tip = _RCL_TIP
    assert (
        cell.consume_for(
            _ACCOUNT, _INSTRUMENT, PositionSide.LONG, proposal_id=_PROPOSAL_ID
        )
        is None
    )


def test_step9_rechecks_gap_and_returns_verified_cas_tip() -> None:
    verified_tip = RclTip(writer_epoch=4, last_seq=24)
    cell, clock = _cell(
        tip_compatible=lambda origin, current: origin == _RCL_TIP
        and current == verified_tip
    )
    assert _publish(cell)
    clock.tip = verified_tip
    proof = cell.consume_for(
        _ACCOUNT, _INSTRUMENT, PositionSide.LONG, proposal_id=_PROPOSAL_ID
    )
    assert proof is not None

    clock.tip = RclTip(writer_epoch=4, last_seq=25)
    assert cell.validate_consumed(proof) is None


def test_consume_for_requires_exact_base_identity_and_dates() -> None:
    cell, _ = _cell()
    historical_scope = replace(_SCOPE, order_dates=(_DATE,))
    assert _publish(cell, scope=historical_scope)

    assert (
        cell.consume_for(
            _ACCOUNT, _INSTRUMENT, PositionSide.LONG, proposal_id=_PROPOSAL_ID
        )
        is None
    )
    assert cell.consume(historical_scope, PositionSide.LONG, proposal_id=_PROPOSAL_ID)


@pytest.mark.parametrize(
    "snapshot",
    [
        pytest.param(_snapshot(positions_complete=False), id="incomplete"),
        pytest.param(_snapshot(independent=False), id="not-independent"),
        pytest.param(_snapshot(provenance="synthetic-ledger"), id="synthetic"),
        pytest.param(_snapshot(generation=None), id="generation-missing"),
        pytest.param(_snapshot(generation=_GENERATION + 1), id="wrong-generation"),
        pytest.param(_snapshot(inquiry_date=None), id="date-missing"),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="order-1",
                        quantity=Decimal("12"),
                        remaining=Decimal("2"),
                        state=WitnessOrderState.PARTIAL,
                        order_date=_DATE,
                    ),
                )
            ),
            id="competing-partial-order",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="order-unknown",
                        quantity=None,
                        remaining=None,
                        state=WitnessOrderState.UNKNOWN,
                        order_date=_DATE,
                    ),
                )
            ),
            id="unknown-order",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="cancelled-order",
                        quantity=Decimal("1"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.CANCELLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="cancel-terminal-unproven",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="filled-no-remaining",
                        quantity=Decimal("1"),
                        remaining=None,
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="filled-missing-remaining",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="",
                        quantity=Decimal("1"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="filled-identity-missing",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="duplicate-id",
                        quantity=Decimal("1"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="duplicate-id",
                        quantity=Decimal("1"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="filled-identity-duplicate",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="order-cancelled",
                        quantity=Decimal("12"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.CANCELLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="cancel-terminal-unproven",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="order-filled-missing-remaining",
                        quantity=Decimal("12"),
                        remaining=None,
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="filled-missing-remaining",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="",
                        quantity=Decimal("12"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="filled-identity-missing",
        ),
        pytest.param(
            _snapshot(
                orders=(
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="duplicate-id",
                        quantity=Decimal("12"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                    WitnessOrder(
                        attempt_id=None,
                        broker_execution_id="duplicate-id",
                        quantity=Decimal("12"),
                        remaining=Decimal(0),
                        state=WitnessOrderState.FILLED,
                        order_date=_DATE,
                    ),
                )
            ),
            id="filled-identity-duplicate",
        ),
        pytest.param(
            _snapshot(positions=(("000660", Decimal("12")),)),
            id="out-of-scope-position",
        ),
        pytest.param(
            _snapshot(positions=((_INSTRUMENT, Decimal("NaN")),)),
            id="non-finite-position",
        ),
    ],
)
def test_untrusted_or_incomplete_snapshot_never_publishes(
    snapshot: WitnessSnapshot,
) -> None:
    cell, _ = _cell()

    assert not _publish(cell, snapshot)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_stale_or_cross_date_snapshot_is_burned_and_unavailable() -> None:
    cell, clock = _cell()
    assert _publish(cell)
    clock.now = 1_401  # age is beyond the injected 500 ms freshness bound
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None

    assert _publish(
        cell,
        age_origin_ms=1_400,
        confirming_age_origin_ms=1_400,
    )
    clock.date = "20261030"
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_a_scheduled_refresh_keeps_the_previous_proof_until_a_newer_one_publishes() -> (
    None
):
    """Issue #1010's failing input: a CLOSE proposed right after a new plan marked the
    refresh pending. Burning the proof there left the cache empty for the ~6.7 s the four
    paced GETs need, so that CLOSE spent its one standing-approval use and then read
    PROOF_UNAVAILABLE. The retained reading keeps its own age origin; a newer publish
    replaces it."""
    cell, clock = _cell()
    assert _publish(cell)

    cell.mark_pending(_SCOPE)  # the next plan; its paced GETs have not answered yet
    clock.now = 1_300  # 400 ms into the refresh, inside the retained reading's 500 ms
    proof = _consume(cell, _SCOPE, PositionSide.LONG)
    assert proof is not None
    assert proof.age_origin_ms == 900

    assert _publish(cell, age_origin_ms=1_250, confirming_age_origin_ms=1_280)
    replacing = _consume(cell, _SCOPE, PositionSide.LONG)
    assert replacing is not None
    assert replacing.age_origin_ms == 1_250


def test_a_retained_proof_is_still_refused_once_it_is_past_max_age() -> None:
    """Retention is not an extension: the bound is the reading's own age origin against the
    one configured ``max_age_ms``, pending refresh or not."""
    cell, clock = _cell()
    assert _publish(cell)

    cell.mark_pending(_SCOPE)
    clock.now = 1_401  # 501 ms past the retained reading's age origin
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_a_scheduled_refresh_keeps_a_proof_awaiting_its_commit_fence() -> None:
    """The step-9 fence outlives the next plan too: only the consumed proof's own age, date
    and tip may refuse it."""
    cell, _ = _cell()
    assert _publish(cell)
    proof = _consume(cell, _SCOPE, PositionSide.LONG)
    assert proof is not None

    cell.mark_pending(_SCOPE)
    assert cell.validate_consumed(proof) is not None


def test_failed_refresh_invalidates_previous_proof() -> None:
    cell, _ = _cell()
    assert _publish(cell)
    token = cell.mark_pending(_SCOPE)
    assert cell.reject(token)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None

    assert _publish(cell)
    cell.invalidate()
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None

    # A refresh that answers with an unusable snapshot is a failed refresh as well.
    assert _publish(cell)
    assert not _publish(cell, _snapshot(positions=()))
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_stock_witness_cannot_claim_short_position_side() -> None:
    cell, _ = _cell()
    assert _publish(cell)

    assert _consume(cell, _SCOPE, PositionSide.SHORT) is None
    # A matching CLOSE attempt burns its proof even when the stock witness cannot prove its
    # requested side; denial cannot leave a reusable balance read behind.
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_complete_flat_stock_snapshot_cannot_supply_positive_close_quantity() -> None:
    cell, _ = _cell()

    assert not _publish(cell, _snapshot(positions=()))
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_bad_time_origin_or_untrusted_current_date_invalidates() -> None:
    clock = _Clock(today=None)
    cell, _ = _cell(clock)

    assert not _publish(cell)
    clock.date = _DATE
    assert not _publish(cell, age_origin_ms=clock.now + 1)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_missing_or_changed_rcl_tip_refuses_publication() -> None:
    cell, clock = _cell()
    assert not _publish(cell, rcl_tip_at_start=None)
    clock.tip = None
    assert not _publish(cell)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_rcl_tip_is_rechecked_at_publish_and_consumption() -> None:
    cell, clock = _cell()
    clock.tip = RclTip(writer_epoch=4, last_seq=24)
    assert not _publish(cell, rcl_tip_at_start=_RCL_TIP)

    clock.tip = _RCL_TIP
    assert _publish(cell)
    clock.tip = RclTip(writer_epoch=4, last_seq=24)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_missing_age_origin_is_unknown() -> None:
    cell, _ = _cell()

    assert not _publish(cell, age_origin_ms=None)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_missing_or_earlier_confirmation_view_is_unknown() -> None:
    cell, _ = _cell()

    assert not _publish(cell, confirming_snapshot=None)
    assert not _publish(cell, confirming_age_origin_ms=None)
    assert not _publish(cell, confirming_age_origin_ms=899)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_balance_10_then_external_flatten_then_balance_0_is_refused() -> None:
    cell, _ = _cell()

    first = _snapshot(positions=((_INSTRUMENT, Decimal("10")),))
    confirming = _snapshot(positions=())

    assert not _publish(cell, first, confirming_snapshot=confirming)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


def test_changed_terminal_order_rows_between_reads_are_refused() -> None:
    cell, _ = _cell()
    first = _snapshot()
    confirming = _snapshot(
        orders=(
            WitnessOrder(
                attempt_id=None,
                broker_execution_id="new-fill",
                quantity=Decimal("1"),
                remaining=Decimal(0),
                state=WitnessOrderState.FILLED,
                order_date=_DATE,
            ),
        )
    )

    assert not _publish(cell, first, confirming_snapshot=confirming)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is None


@pytest.mark.parametrize(
    "state", [WitnessOrderState.FILLED, WitnessOrderState.CANCELLED]
)
def test_only_fully_filled_order_is_proven_terminal(state: WitnessOrderState) -> None:
    cell, _ = _cell()
    snapshot = _snapshot(
        orders=(
            WitnessOrder(
                attempt_id=None,
                broker_execution_id="terminal-order",
                quantity=Decimal("1"),
                remaining=Decimal(0),
                state=state,
                order_date=_DATE,
            ),
        )
    )

    published = _publish(cell, snapshot, confirming_snapshot=snapshot)
    if state is WitnessOrderState.CANCELLED:
        assert not published
        assert _consume(cell, _SCOPE, PositionSide.LONG) is None
    else:
        assert published
        assert _consume(cell, _SCOPE, PositionSide.LONG) is not None


def test_stale_fetch_token_cannot_publish_over_a_newer_pending_refresh() -> None:
    cell, _ = _cell()
    old_token = cell.mark_pending(_SCOPE)
    current_token = cell.mark_pending(_SCOPE)

    assert not cell.publish(
        _SCOPE,
        _snapshot(),
        confirming_snapshot=_snapshot(),
        age_origin_ms=900,
        confirming_age_origin_ms=950,
        trading_date=_DATE,
        rcl_tip_at_start=_RCL_TIP,
        pending_token=old_token,
    )
    assert cell.publish(
        _SCOPE,
        _snapshot(),
        confirming_snapshot=_snapshot(),
        age_origin_ms=900,
        confirming_age_origin_ms=950,
        trading_date=_DATE,
        rcl_tip_at_start=_RCL_TIP,
        pending_token=current_token,
    )
    assert _consume(cell, _SCOPE, PositionSide.LONG) is not None


def test_rejecting_stale_worker_token_does_not_clear_newer_proof() -> None:
    cell, _ = _cell()
    stale_token = cell.mark_pending(_SCOPE)
    current_token = cell.mark_pending(_SCOPE)
    assert cell.publish(
        _SCOPE,
        _snapshot(),
        confirming_snapshot=_snapshot(),
        age_origin_ms=900,
        confirming_age_origin_ms=950,
        trading_date=_DATE,
        rcl_tip_at_start=_RCL_TIP,
        pending_token=current_token,
    )

    assert not cell.reject(stale_token)
    assert _consume(cell, _SCOPE, PositionSide.LONG) is not None


def test_commit_validation_rechecks_and_burns_currentness() -> None:
    cell, clock = _cell()
    assert _publish(cell)
    proof = _consume(cell, _SCOPE, PositionSide.LONG)
    assert proof is not None

    clock.now = proof.age_origin_ms + proof.max_age_ms + 1
    assert cell.validate_consumed(proof) is None
    assert cell.validate_consumed(proof) is None

    clock.now = 1_000
    assert _publish(cell)
    proof = _consume(cell, _SCOPE, PositionSide.LONG)
    assert proof is not None
    clock.date = "20261030"
    assert cell.validate_consumed(proof) is None


def test_consumption_is_atomic_across_callers() -> None:
    from concurrent.futures import ThreadPoolExecutor

    cell, _ = _cell()
    assert _publish(cell)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(lambda _index: _consume(cell, _SCOPE, PositionSide.LONG), range(2))
        )
    assert sum(result is not None for result in results) == 1
