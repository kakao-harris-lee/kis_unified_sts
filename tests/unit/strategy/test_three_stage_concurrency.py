"""
ThreeStageExit Concurrency Tests

Tests for thread-safe state transitions in ThreeStageExit.
Ensures that concurrent updates to the same position don't corrupt state.
"""

import asyncio
from datetime import datetime
from typing import List

import pytest

from shared.models.position import Position, PositionState
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig


@pytest.fixture
def exit_config():
    """기본 ThreeStageExit 설정"""
    return ThreeStageExitConfig(
        stop_loss_pct=-0.02,  # -2%
        breakeven_threshold_pct=0.015,  # +1.5%
        maximize_threshold_pct=0.03,  # +3%
        trailing_stop_pct=-0.03,  # -3%
        overshoot_threshold_pct=0.07,  # +7%
        overshoot_trailing_pct=-0.015,  # -1.5%
        time_cut_minutes=20,
        eod_close_hour=15,
        eod_close_minute=15,
        fee_rate=0.003,
        enable_bear_exit=True,
    )


@pytest.fixture
def exit_strategy(exit_config):
    """ThreeStageExit 인스턴스"""
    return ThreeStageExit(exit_config)


@pytest.fixture
def test_position():
    """테스트용 포지션"""
    return Position(
        id="pos_001",
        code="005930",
        name="Samsung Electronics",
        side="BUY",
        quantity=10,
        entry_price=100.0,
        current_price=100.0,
        entry_time=datetime.now(),
        state=PositionState.SURVIVAL,
        highest_price=100.0,
        stop_price=0.0,
    )


@pytest.mark.asyncio
async def test_concurrent_state_updates_no_corruption(
    exit_strategy: ThreeStageExit, test_position: Position
):
    """동시 상태 업데이트 시 corruption 없어야 함

    다수의 코루틴이 동시에 같은 포지션을 업데이트해도,
    최종 상태는 일관성 있어야 함 (BREAKEVEN 또는 MAXIMIZE).
    """
    # 가격 시퀀스: SURVIVAL → BREAKEVEN → MAXIMIZE로 전이
    prices = [
        100.0,  # 0% - SURVIVAL
        101.0,  # +1% - SURVIVAL
        101.6,  # +1.6% - BREAKEVEN 전이
        102.0,  # +2% - BREAKEVEN
        103.0,  # +3% - MAXIMIZE 전이
        104.0,  # +4% - MAXIMIZE
    ]

    # 동시 업데이트 실행
    tasks = [
        exit_strategy.update_position_state(test_position, price)
        for price in prices
    ]
    results = await asyncio.gather(*tasks)

    # 검증: 최종 상태는 MAXIMIZE여야 함
    assert test_position.state == PositionState.MAXIMIZE, (
        f"Expected MAXIMIZE, got {test_position.state}"
    )

    # 검증: stop_price가 설정되어야 함 (BREAKEVEN 전이 시)
    assert test_position.stop_price > 0, "Stop price should be set"

    # 검증: 상태 전이가 결과에 반영되어야 함
    state_changes = [r for r in results if r is not None]
    assert len(state_changes) >= 2, (
        f"Expected at least 2 state transitions, got {len(state_changes)}"
    )
    assert PositionState.BREAKEVEN in state_changes, "Missing BREAKEVEN transition"
    assert PositionState.MAXIMIZE in state_changes, "Missing MAXIMIZE transition"


@pytest.mark.asyncio
async def test_concurrent_updates_different_positions(
    exit_strategy: ThreeStageExit,
):
    """서로 다른 포지션은 병렬 업데이트 가능

    각 포지션은 독립적인 lock을 가지므로,
    서로 다른 포지션의 업데이트는 블로킹 없이 병렬 실행되어야 함.
    """
    # 두 개의 독립적인 포지션 생성
    position1 = Position(
        id="pos_001",
        code="005930",
        name="Samsung",
        side="BUY",
        quantity=10,
        entry_price=100.0,
        current_price=100.0,
        entry_time=datetime.now(),
        state=PositionState.SURVIVAL,
        highest_price=100.0,
        stop_price=0.0,
    )

    position2 = Position(
        id="pos_002",
        code="000660",
        name="SK Hynix",
        side="BUY",
        quantity=5,
        entry_price=200.0,
        current_price=200.0,
        entry_time=datetime.now(),
        state=PositionState.SURVIVAL,
        highest_price=200.0,
        stop_price=0.0,
    )

    # 각 포지션을 BREAKEVEN으로 전이
    price1 = 103.0  # +3% for position1
    price2 = 206.0  # +3% for position2

    # 병렬 실행 (블로킹 없어야 함)
    start = asyncio.get_event_loop().time()
    _ = await asyncio.gather(
        exit_strategy.update_position_state(position1, price1),
        exit_strategy.update_position_state(position2, price2),
    )
    elapsed = asyncio.get_event_loop().time() - start

    # 검증: 두 포지션 모두 BREAKEVEN 이상으로 전이
    assert position1.state in (PositionState.BREAKEVEN, PositionState.MAXIMIZE)
    assert position2.state in (PositionState.BREAKEVEN, PositionState.MAXIMIZE)

    # 검증: 병렬 실행이므로 빠르게 완료되어야 함 (순차 실행보다 빠름)
    # 각 작업이 0.1초 걸린다면, 병렬은 ~0.1초, 순차는 ~0.2초
    # 여기서는 실제로 빠른 작업이므로 단순히 완료 확인만 함
    assert elapsed < 1.0, f"Parallel execution took too long: {elapsed}s"


@pytest.mark.asyncio
async def test_cleanup_position_removes_lock(exit_strategy: ThreeStageExit):
    """cleanup_position은 lock을 제거해야 함

    포지션 종료 시 메모리 누수 방지를 위해
    해당 포지션의 lock을 제거해야 함.
    """
    position = Position(
        id="pos_cleanup",
        code="005930",
        name="Samsung",
        side="BUY",
        quantity=10,
        entry_price=100.0,
        current_price=100.0,
        entry_time=datetime.now(),
        state=PositionState.SURVIVAL,
        highest_price=100.0,
        stop_price=0.0,
    )

    # Lock 생성을 위해 상태 업데이트
    await exit_strategy.update_position_state(position, 101.6)

    # Lock이 생성되었는지 확인
    assert position.id in exit_strategy._position_locks, (
        "Lock should be created after first update"
    )

    # Cleanup 호출
    exit_strategy.cleanup_position(position.id)

    # Lock이 제거되었는지 확인
    assert position.id not in exit_strategy._position_locks, (
        "Lock should be removed after cleanup"
    )


@pytest.mark.asyncio
async def test_stress_test_many_concurrent_updates(
    exit_strategy: ThreeStageExit, test_position: Position
):
    """스트레스 테스트: 다수의 동시 업데이트

    50개의 동시 업데이트 요청을 보내도
    상태가 corrupt되지 않아야 함.
    """
    # 50개의 가격 시퀀스 (SURVIVAL → BREAKEVEN → MAXIMIZE)
    prices: List[float] = []
    for i in range(50):
        # 점진적으로 가격 상승 (0% → 5%)
        pct_gain = (i / 50) * 0.05
        price = test_position.entry_price * (1 + pct_gain)
        prices.append(price)

    # 동시 실행
    tasks = [
        exit_strategy.update_position_state(test_position, price)
        for price in prices
    ]
    results = await asyncio.gather(*tasks)

    # 검증: 최종 상태는 MAXIMIZE여야 함 (5% 수익)
    assert test_position.state == PositionState.MAXIMIZE, (
        f"Expected MAXIMIZE, got {test_position.state}"
    )

    # 검증: stop_price가 설정되어야 함
    assert test_position.stop_price > 0, "Stop price should be set"

    # 검증: 상태 전이 결과가 None이 아닌 것들
    state_changes = [r for r in results if r is not None]
    assert len(state_changes) >= 2, (
        f"Expected at least 2 state transitions, got {len(state_changes)}"
    )


@pytest.mark.asyncio
async def test_race_condition_state_consistency(
    exit_strategy: ThreeStageExit,
):
    """레이스 컨디션 테스트: 상태 일관성 검증

    동일한 가격으로 동시에 여러 번 업데이트해도
    상태가 일관되어야 함 (중복 전이 없음).
    """
    # Create fresh position in SURVIVAL state
    position = Position(
        id="pos_race",
        code="005930",
        name="Samsung",
        side="BUY",
        quantity=10,
        entry_price=100.0,
        current_price=100.0,
        entry_time=datetime.now(),
        state=PositionState.SURVIVAL,
        highest_price=100.0,
        stop_price=0.0,
    )

    # BREAKEVEN 전이 가격 (floating point 고려하여 약간 높게)
    breakeven_price = position.entry_price * (
        1 + exit_strategy.config.breakeven_threshold_pct + 0.001
    )

    # 동시에 10번 업데이트 (모두 같은 가격)
    tasks = [
        exit_strategy.update_position_state(position, breakeven_price)
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    # 검증: 상태 전이는 1번 이하로 발생해야 함 (중복 전이 방지)
    # Lock이 제대로 작동하면, 첫 번째 호출만 전이하고 나머지는 None 반환
    state_changes = [r for r in results if r is not None]
    assert len(state_changes) <= 1, (
        f"Expected at most 1 state transition, got {len(state_changes)}"
    )
    if state_changes:
        assert state_changes[0] == PositionState.BREAKEVEN, (
            f"Expected BREAKEVEN transition, got {state_changes[0]}"
        )

    # 검증: 최종 상태는 BREAKEVEN
    assert position.state == PositionState.BREAKEVEN, (
        f"Expected BREAKEVEN, got {position.state}"
    )


@pytest.mark.asyncio
async def test_lock_contention_performance(
    exit_strategy: ThreeStageExit, test_position: Position
):
    """Lock 경합 성능 테스트

    동시성이 높아도 합리적인 시간 내에 완료되어야 함.
    """
    # 100개의 가격 시퀀스
    prices = [
        test_position.entry_price * (1 + i * 0.001)  # 0.1%씩 상승
        for i in range(100)
    ]

    # 시작 시간
    start = asyncio.get_event_loop().time()

    # 동시 실행
    tasks = [
        exit_strategy.update_position_state(test_position, price)
        for price in prices
    ]
    await asyncio.gather(*tasks)

    # 종료 시간
    elapsed = asyncio.get_event_loop().time() - start

    # 검증: 합리적인 시간 내에 완료 (1초 이내)
    assert elapsed < 1.0, (
        f"100 concurrent updates took too long: {elapsed:.3f}s"
    )

    # 검증: 상태 일관성
    assert test_position.state in (
        PositionState.SURVIVAL,
        PositionState.BREAKEVEN,
        PositionState.MAXIMIZE,
    ), f"Invalid state: {test_position.state}"
