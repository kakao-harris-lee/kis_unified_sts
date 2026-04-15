"""TradingStatePublisher running-totals + equity_timeline regression tests."""
from __future__ import annotations

import json
from datetime import date

import pytest

from shared.streaming import trading_state
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


# ---------------------------------------------------------------------------
# Minimal fake-Redis (pipeline + sorted set + hash)
# ---------------------------------------------------------------------------

class _FakePipeline:
    def __init__(self, redis_client: "_FakeRedis") -> None:
        self._r = redis_client
        self._ops: list[tuple] = []

    def hincrbyfloat(self, key: str, field: str, amount: float):
        self._ops.append(("hincrbyfloat", key, field, amount))
        return self

    def hincrby(self, key: str, field: str, amount: int):
        self._ops.append(("hincrby", key, field, amount))
        return self

    def expire(self, key: str, ttl: int):
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self):
        for op in self._ops:
            kind = op[0]
            if kind == "hincrbyfloat":
                _, key, field, amount = op
                bucket = self._r._hashes.setdefault(key, {})
                bucket[field] = str(float(bucket.get(field, 0)) + amount)
            elif kind == "hincrby":
                _, key, field, amount = op
                bucket = self._r._hashes.setdefault(key, {})
                bucket[field] = str(int(bucket.get(field, 0)) + amount)
            elif kind == "expire":
                pass  # TTL not relevant for unit tests
        return []


class _FakeRedis:
    """Minimal Redis double supporting hashes, sorted sets, and pipeline."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._zsets: dict[str, dict[str, float]] = {}  # key -> {member: score}

    def pipeline(self, transaction: bool = False) -> _FakePipeline:
        return _FakePipeline(self)

    # -- Hash ------------------------------------------------------------------

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    # -- Sorted set ------------------------------------------------------------

    def zadd(self, key: str, mapping: dict[str, float]) -> None:
        zset = self._zsets.setdefault(key, {})
        zset.update(mapping)

    def zrange(
        self,
        key: str,
        start: int,
        end: int,
        withscores: bool = False,
    ) -> list[str]:
        zset = self._zsets.get(key, {})
        # Sort members by score ascending
        sorted_members = sorted(zset.items(), key=lambda x: x[1])
        members = [m for m, _ in sorted_members]
        n = len(members)
        # Convert negative indices (Python-like)
        if start < 0:
            start = max(n + start, 0)
        if end < 0:
            end = n + end
        else:
            end = min(end, n - 1)
        if start > end:
            return []
        return members[start : end + 1]

    # -- Generic ---------------------------------------------------------------

    def expire(self, key: str, ttl: int) -> None:
        pass  # TTL not relevant for unit tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture
def publisher(fake_redis, monkeypatch):
    monkeypatch.setattr(trading_state, "_get_redis", lambda: fake_redis)
    return TradingStatePublisher("stock")


@pytest.fixture
def reader(fake_redis, monkeypatch):
    monkeypatch.setattr(trading_state, "_get_redis", lambda: fake_redis)
    return TradingStateReader("stock")


# ---------------------------------------------------------------------------
# Tests: running totals
# ---------------------------------------------------------------------------

def test_running_totals_survive_across_sessions(publisher, reader):
    publisher.increment_running_totals(pnl=150.0, trades=1, win=True)
    publisher.increment_running_totals(pnl=-80.0, trades=1, win=False)

    totals = reader.get_running_totals()
    assert totals["total_trades"] == 2
    assert totals["total_wins"] == 1
    assert totals["total_pnl"] == pytest.approx(70.0)


def test_running_totals_zero_defaults_when_empty(reader):
    totals = reader.get_running_totals()
    assert totals["total_trades"] == 0
    assert totals["total_wins"] == 0
    assert totals["total_pnl"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: equity timeline
# ---------------------------------------------------------------------------

def test_equity_timeline_records_daily_snapshot(publisher, reader):
    today = date(2026, 4, 15)
    publisher.publish_equity_snapshot(
        as_of=today,
        cash_balance=100_000_000.0,
        open_positions_value=5_000_000.0,
        closed_pnl=150.0,
    )

    timeline = reader.get_equity_timeline(days=30)
    assert len(timeline) == 1
    entry = timeline[0]
    assert entry["date"] == "2026-04-15"
    assert entry["total_equity"] == pytest.approx(105_000_150.0)


def test_equity_timeline_multiple_days_sorted(publisher, reader):
    publisher.publish_equity_snapshot(
        as_of=date(2026, 4, 14),
        cash_balance=100_000_000.0,
        open_positions_value=0.0,
        closed_pnl=100.0,
    )
    publisher.publish_equity_snapshot(
        as_of=date(2026, 4, 15),
        cash_balance=100_000_000.0,
        open_positions_value=0.0,
        closed_pnl=200.0,
    )
    timeline = reader.get_equity_timeline(days=7)
    assert len(timeline) == 2
    # oldest first (ascending by score = ascending by date)
    assert timeline[0]["date"] == "2026-04-14"
    assert timeline[1]["date"] == "2026-04-15"


def test_equity_timeline_empty_when_no_data(reader):
    timeline = reader.get_equity_timeline(days=30)
    assert timeline == []


# ---------------------------------------------------------------------------
# Tests: orchestrator running totals integration
# ---------------------------------------------------------------------------

def test_orchestrator_record_running_totals_helper_increments_publisher():
    """_record_running_totals calls publisher.increment_running_totals with pnl/win."""
    from unittest.mock import MagicMock
    from datetime import datetime

    from services.trading.orchestrator import TradingConfig, TradingOrchestrator
    from shared.models.position import Position, PositionSide

    cfg = TradingConfig(
        asset_class="stock",
        strategy_name="momentum_breakout",
        initial_capital=100_000_000.0,
        order_amount_per_trade=1_000_000.0,
    )
    orch = TradingOrchestrator(cfg)
    orch._state_publisher = MagicMock()

    closed = Position(
        id="p1",
        code="005930",
        name="TEST",
        strategy="momentum_breakout",
        side=PositionSide.LONG,
        entry_price=70000.0,
        quantity=10,
        entry_time=datetime(2026, 4, 15, 9, 0),
    )
    closed.exit_price = 71000.0
    closed.current_price = 71000.0  # orchestrator sets this on close

    orch._record_running_totals(closed)

    orch._state_publisher.increment_running_totals.assert_called_once()
    call = orch._state_publisher.increment_running_totals.call_args
    assert call.kwargs["trades"] == 1
    assert call.kwargs["win"] is True
    # pnl = (71000-70000)*10 = 10000 (using unrealized_pnl property)
    assert call.kwargs["pnl"] == pytest.approx(10000.0)
