"""Owner tests for trading recovery helper functions."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from shared.models.position import PositionSide, PositionState


def test_parse_recovery_entry_time_accepts_iso_timestamp() -> None:
    from services.trading.recovery import parse_recovery_entry_time

    entry_time = parse_recovery_entry_time(
        {"id": "pos-1", "entry_time": "2026-07-04T09:01:02"}
    )

    assert entry_time == datetime(2026, 7, 4, 9, 1, 2)


def test_parse_recovery_entry_time_rejects_missing_or_invalid_timestamp() -> None:
    from services.trading.recovery import parse_recovery_entry_time

    with pytest.raises(ValueError):
        parse_recovery_entry_time({"id": "pos-1", "entry_time": ""})

    with pytest.raises(ValueError):
        parse_recovery_entry_time({"id": "pos-1", "entry_time": "not-a-date"})


def test_evaluate_position_freshness_keeps_same_day_intraday() -> None:
    from services.trading.recovery import evaluate_position_freshness

    freshness = evaluate_position_freshness(
        strategy="setup_a_gap_reversion",
        entry_time=datetime(2026, 7, 4, 9, 30),
        today=date(2026, 7, 4),
        swing_strategies={"bb_reversion"},
        max_swing_age_days=7,
    )

    assert freshness.recoverable is True
    assert freshness.is_swing is False
    assert freshness.age_days == 0


def test_evaluate_position_freshness_filters_old_intraday() -> None:
    from services.trading.recovery import evaluate_position_freshness

    freshness = evaluate_position_freshness(
        strategy="setup_a_gap_reversion",
        entry_time=datetime(2026, 7, 3, 9, 30),
        today=date(2026, 7, 4),
        swing_strategies={"bb_reversion"},
        max_swing_age_days=7,
    )

    assert freshness.recoverable is False
    assert freshness.is_swing is False
    assert freshness.age_days == 1


def test_evaluate_position_freshness_keeps_swing_within_age() -> None:
    from services.trading.recovery import evaluate_position_freshness

    freshness = evaluate_position_freshness(
        strategy="bb_reversion",
        entry_time=datetime(2026, 6, 30, 9, 30),
        today=date(2026, 7, 4),
        swing_strategies={"bb_reversion"},
        max_swing_age_days=7,
    )

    assert freshness.recoverable is True
    assert freshness.is_swing is True
    assert freshness.age_days == 4


def test_evaluate_position_freshness_filters_stale_swing() -> None:
    from services.trading.recovery import evaluate_position_freshness

    freshness = evaluate_position_freshness(
        strategy="bb_reversion",
        entry_time=datetime(2026, 6, 20, 9, 30),
        today=date(2026, 7, 4),
        swing_strategies={"bb_reversion"},
        max_swing_age_days=7,
    )

    assert freshness.recoverable is False
    assert freshness.is_swing is True
    assert freshness.age_days == 14


def test_reconstruct_recovered_position_preserves_short_and_optional_fields() -> None:
    from services.trading.recovery import reconstruct_recovered_position

    position = reconstruct_recovered_position(
        {
            "id": "fut-001",
            "code": "A01603",
            "side": "short",
            "quantity": "1",
            "entry_price": "837.0",
            "current_price": "835.0",
            "entry_time": "2026-07-04T09:30:00",
            "state": "maximize",
            "strategy": "setup_a_gap_reversion",
            "client_order_id": "coid-1",
            "stop_price": "839.0",
        },
        entry_time=datetime(2026, 7, 4, 9, 30),
        symbol_names={"A01603": "KOSPI200 Futures"},
    )

    assert position.id == "fut-001"
    assert position.code == "A01603"
    assert position.name == "KOSPI200 Futures"
    assert position.side == PositionSide.SHORT
    assert position.quantity == 1
    assert position.entry_price == 837.0
    assert position.current_price == 835.0
    assert position.state == PositionState.MAXIMIZE
    assert position.strategy == "setup_a_gap_reversion"
    assert position.metadata["client_order_id"] == "coid-1"
    assert position.stop_price == 839.0


def test_reconstruct_recovered_position_uses_legacy_fallbacks() -> None:
    from services.trading.recovery import reconstruct_recovered_position

    entry_time = datetime.now() - timedelta(minutes=5)
    position = reconstruct_recovered_position(
        {
            "id": "legacy-001",
            "code": "003530",
            "quantity": "10",
            "entry_price": "10000.0",
            "current_price": "10500.0",
            "entry_time": entry_time.isoformat(),
            "strategy": "bb_reversion",
        },
        entry_time=entry_time,
        symbol_names={},
    )

    assert position.name == "003530"
    assert position.highest_price == 10500.0
    assert position.lowest_price == 10000.0
    assert position.fee_rate == 0.003


def test_recovery_helpers_import_without_orchestrator() -> None:
    import subprocess
    import sys
    import textwrap

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import sys
                import services.trading.recovery

                assert "services.trading.orchestrator" not in sys.modules
                """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


class _ReaderStub:
    def __init__(self, positions: list[dict[str, object]]) -> None:
        self.positions = positions
        self.removed: list[str] = []

    def get_positions(self) -> list[dict[str, object]]:
        return self.positions

    def remove_position(self, position_id: str) -> None:
        self.removed.append(position_id)


class _TrackerStub:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.positions: list[Any] = []
        self.loaded_from_db = False

    def add_recovered_position(self, position: Any) -> bool:
        self.events.append("redis")
        position_id = position.id
        if any(existing.id == position_id for existing in self.positions):
            return False
        self.positions.append(position)
        return True

    async def load_from_db(self) -> int:
        self.events.append("sqlite")
        self.loaded_from_db = True
        return 0


def _owner_config(*, asset_class: str = "stock") -> SimpleNamespace:
    return SimpleNamespace(
        asset_class=asset_class,
        symbols=["005930"],
        swing_recovery_max_age_days=7,
    )


def _redis_position(**overrides: object) -> dict[str, object]:
    position = {
        "id": "redis-001",
        "code": "003530",
        "name": "Recovery Target",
        "side": "long",
        "quantity": 3,
        "entry_price": 100.0,
        "current_price": 101.0,
        "entry_time": datetime.now().isoformat(),
        "state": "survival",
        "strategy": "bb_reversion",
    }
    position.update(overrides)
    return position


@pytest.mark.asyncio
async def test_position_recovery_service_preserves_futures_order_fields() -> None:
    from services.trading.recovery import PositionRecoveryService

    reader = _ReaderStub(
        [
            _redis_position(
                id="fut-short-001",
                code="A01603",
                name="KOSPI200 Futures",
                side="short",
                quantity=1,
                entry_price=837.0,
                current_price=835.0,
                strategy="setup_a_gap_reversion",
                client_order_id="coid-fut-1",
                stop_price=839.0,
            )
        ]
    )
    tracker = _TrackerStub()
    symbols_seen: dict[str, datetime] = {}
    service = PositionRecoveryService(
        config=_owner_config(asset_class="futures"),
        position_tracker=tracker,
        symbol_names={},
        symbol_last_seen=symbols_seen,
        swing_strategies={"bb_reversion"},
        reader_factory=lambda _asset_class: reader,
    )

    recovered = await service.recover_positions_from_redis()

    assert recovered == 1
    position = tracker.positions[0]
    assert position.side == PositionSide.SHORT
    assert position.metadata["client_order_id"] == "coid-fut-1"
    assert position.stop_price == 839.0
    assert reader.removed == []


@pytest.mark.asyncio
async def test_position_recovery_service_runs_redis_before_sqlite_fallback() -> None:
    from services.trading.recovery import PositionRecoveryService

    events: list[str] = []
    tracker = _TrackerStub(events)
    service = PositionRecoveryService(
        config=_owner_config(),
        position_tracker=tracker,
        symbol_names={},
        symbol_last_seen={},
        swing_strategies={"bb_reversion"},
        reader_factory=lambda _asset_class: _ReaderStub([_redis_position()]),
    )

    recovered = await service.recover_open_positions()

    assert recovered == 1
    assert events == ["redis", "sqlite"]
    assert tracker.loaded_from_db is True
    assert len(tracker.positions) == 1


@pytest.mark.asyncio
async def test_position_recovery_service_disabled_skips_redis_and_sqlite() -> None:
    from services.trading.recovery import PositionRecoveryService

    def fail_reader_factory(_asset_class: str) -> _ReaderStub:
        raise AssertionError("redis reader should not be initialized")

    tracker = _TrackerStub()
    service = PositionRecoveryService(
        config=_owner_config(),
        position_tracker=tracker,
        symbol_names={},
        symbol_last_seen={},
        swing_strategies={"bb_reversion"},
        reader_factory=fail_reader_factory,
    )

    recovered = await service.recover_open_positions(recovery_disabled=True)

    assert recovered == 0
    assert tracker.loaded_from_db is False
    assert tracker.positions == []


@pytest.mark.asyncio
async def test_position_recovery_service_injects_recovered_symbol_subscription() -> (
    None
):
    from services.trading.recovery import PositionRecoveryService

    config = _owner_config()
    symbols_seen: dict[str, datetime] = {}
    service = PositionRecoveryService(
        config=config,
        position_tracker=_TrackerStub(),
        symbol_names={},
        symbol_last_seen=symbols_seen,
        swing_strategies={"bb_reversion"},
        reader_factory=lambda _asset_class: _ReaderStub(
            [_redis_position(code="003530")]
        ),
    )

    recovered = await service.recover_positions_from_redis()

    assert recovered == 1
    assert config.symbols == ["005930", "003530"]
    assert isinstance(symbols_seen["003530"], datetime)
