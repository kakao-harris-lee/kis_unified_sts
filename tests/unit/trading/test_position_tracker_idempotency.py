"""Tests for PositionTracker idempotency-key (client_order_id) handling.

Covers the retry-safety contract added for the runtime trading path:

* A second call to ``add_position`` with the same ``client_order_id`` must
  return the existing position rather than open a duplicate.
* The idempotency key must propagate through ``add_from_signal`` when the
  caller has stamped one onto ``Signal.metadata``.
* The key must survive the Redis round-trip used by the orchestrator's
  recovery path, so a retry after a crash still dedupes.
* The index must be cleared when the position is fully closed, so that
  closed positions cannot be "re-opened" via a stale retry.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from services.trading.position_tracker import (
    PositionTracker,
    PositionTrackerConfig,
)
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import Signal, SignalType
from shared.streaming.trading_state import TradingStatePublisher


@pytest.fixture
def tracker() -> PositionTracker:
    # 2 positions per symbol so we can confirm the duplicate is suppressed by
    # idempotency, not by the per-symbol cap.
    return PositionTracker(
        PositionTrackerConfig(max_positions=10, max_positions_per_symbol=2)
    )


class TestAddPositionIdempotency:
    def test_duplicate_client_order_id_returns_existing(self, tracker):
        first = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        second = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71500,  # different price — must be ignored
            quantity=99,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )

        assert first is not None
        assert second is not None
        assert second is first, "Retry must return the same Position instance"
        assert tracker.position_count == 1
        # The retry's payload must not silently overwrite the original fields.
        assert first.entry_price == 71000
        assert first.quantity == 10

    def test_no_client_order_id_keeps_legacy_behavior(self, tracker):
        first = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
        )
        second = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71500,
            quantity=5,
            strategy="bb_reversion",
        )

        assert first is not None
        assert second is not None
        assert first is not second
        assert tracker.position_count == 2

    def test_empty_or_whitespace_coid_is_ignored(self, tracker):
        p1 = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="   ",
        )
        p2 = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="",
        )
        assert p1 is not None and p2 is not None
        assert p1 is not p2
        assert tracker.position_count == 2

    def test_distinct_coids_open_distinct_positions(self, tracker):
        a = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-A",
        )
        b = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-B",
        )
        assert a is not None and b is not None
        assert a is not b
        assert tracker.position_count == 2

    def test_idempotency_bypasses_per_symbol_cap_for_retry(self):
        # max_positions_per_symbol=1 — a retry must NOT be rejected by the cap.
        t = PositionTracker(
            PositionTrackerConfig(max_positions=10, max_positions_per_symbol=1)
        )
        first = t.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        retry = t.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert retry is first
        assert t.position_count == 1

    def test_client_order_id_stored_in_metadata(self, tracker):
        pos = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert pos is not None
        assert pos.metadata.get("client_order_id") == "coid-001"

    def test_explicit_client_order_id_param_wins_over_metadata(self, tracker):
        # When both metadata['client_order_id'] and the param are supplied,
        # the param is authoritative so the in-memory idempotency index and
        # the persisted record never disagree.
        pos = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            metadata={"client_order_id": "from-metadata"},
            client_order_id="coid-001",
        )
        assert pos is not None
        assert pos.metadata["client_order_id"] == "coid-001"

        # A retry under the authoritative key dedupes.
        retry = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert retry is pos


class TestAddFromSignalIdempotency:
    def _make_signal(self, *, code="005930", coid: str | None = None) -> Signal:
        meta: dict = {}
        if coid is not None:
            meta["client_order_id"] = coid
        return Signal(
            code=code,
            name="삼성전자",
            signal_type=SignalType.ENTRY,
            strategy="bb_reversion",
            price=71000,
            quantity=10,
            metadata=meta,
        )

    def test_retry_of_same_signal_dedupes(self, tracker):
        sig = self._make_signal(coid="sig-001")
        first = tracker.add_from_signal(sig, quantity=10)
        second = tracker.add_from_signal(sig, quantity=10)
        assert first is second
        assert tracker.position_count == 1

    def test_explicit_client_order_id_overrides_metadata(self, tracker):
        sig = self._make_signal(coid="from-meta")
        first = tracker.add_from_signal(sig, quantity=10, client_order_id="override")
        retry_with_meta = tracker.add_from_signal(sig, quantity=10)
        retry_with_override = tracker.add_from_signal(
            sig, quantity=10, client_order_id="override"
        )

        assert first is not None
        assert (
            retry_with_meta is not first
        ), "Different idempotency keys must open distinct positions"
        assert retry_with_override is first
        assert tracker.position_count == 2

    def test_signal_without_idempotency_key_keeps_legacy_behavior(self, tracker):
        sig = self._make_signal()  # no coid
        first = tracker.add_from_signal(sig, quantity=10)
        second = tracker.add_from_signal(sig, quantity=10)
        assert first is not None and second is not None
        assert first is not second
        assert tracker.position_count == 2


class TestRecoveryIdempotency:
    def test_recovered_position_registers_coid(self, tracker):
        recovered = Position(
            id="abc-123",
            code="005930",
            name="삼성전자",
            side=PositionSide.LONG,
            quantity=10,
            entry_price=71000,
            entry_time=datetime.now(),
            current_price=71500,
            state=PositionState.SURVIVAL,
            strategy="bb_reversion",
            metadata={"client_order_id": "coid-001"},
        )
        assert tracker.add_recovered_position(recovered) is True

        # A retry of the same signal after recovery must dedupe.
        retry = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert retry is recovered
        assert tracker.position_count == 1

    def test_close_clears_idempotency_index(self, tracker):
        pos = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert pos is not None
        closed = tracker.close_position(pos.id, exit_price=72000, reason="TEST")
        assert closed is not None

        # After close, a fresh add with the same coid must open a NEW position
        # (a closed leg cannot be retroactively "re-opened" by retry).
        reopened = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=72500,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert reopened is not None
        assert reopened.id != pos.id
        assert tracker.position_count == 1


class TestRedisRoundTrip:
    """Verifies the idempotency key survives the Redis serialize/deserialize cycle."""

    def test_serialize_position_includes_client_order_id(self):
        pos = Position(
            id="abc-123",
            code="005930",
            name="삼성전자",
            side=PositionSide.LONG,
            quantity=10,
            entry_price=71000,
            entry_time=datetime.now(),
            current_price=71500,
            state=PositionState.SURVIVAL,
            strategy="bb_reversion",
            metadata={"client_order_id": "coid-001"},
        )
        data = TradingStatePublisher._serialize_position(pos)
        assert data["client_order_id"] == "coid-001"

    def test_serialize_position_handles_missing_metadata(self):
        pos = Position(
            id="abc-123",
            code="005930",
            name="삼성전자",
            side=PositionSide.LONG,
            quantity=10,
            entry_price=71000,
            entry_time=datetime.now(),
            current_price=71500,
            state=PositionState.SURVIVAL,
            strategy="bb_reversion",
        )
        data = TradingStatePublisher._serialize_position(pos)
        # Field is always present but empty when no key was registered.
        assert data["client_order_id"] == ""

    def test_recovery_round_trip_dedupes_retry(self, tracker):
        # Simulate the full orchestrator round-trip without touching Redis:
        # 1. open a position with a coid
        # 2. serialize via TradingStatePublisher  (== what gets written to Redis)
        # 3. drop the tracker (== orchestrator restart)
        # 4. reconstruct Position from the serialized dict  (mirrors
        #    orchestrator._recover_positions_from_redis)
        # 5. add_recovered_position
        # 6. retry the original add_position with the same coid
        # The retry must dedupe to the recovered instance.
        original = tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert original is not None
        serialized = TradingStatePublisher._serialize_position(original)

        # Fresh tracker simulating a restart.
        new_tracker = PositionTracker(PositionTrackerConfig(max_positions=10))

        recovered = Position(
            id=serialized["id"],
            code=serialized["code"],
            name=serialized["name"],
            side=PositionSide(serialized["side"]),
            quantity=int(serialized["quantity"]),
            entry_price=float(serialized["entry_price"]),
            entry_time=datetime.fromisoformat(serialized["entry_time"]),
            current_price=float(serialized["current_price"]),
            highest_price=float(serialized["highest_price"]),
            lowest_price=float(serialized["lowest_price"]),
            state=PositionState(serialized["state"]),
            strategy=serialized["strategy"],
            fee_rate=float(serialized["fee_rate"]),
        )
        coid = serialized["client_order_id"]
        if coid:
            recovered.metadata["client_order_id"] = coid

        assert new_tracker.add_recovered_position(recovered) is True

        retry = new_tracker.add_position(
            code="005930",
            name="삼성전자",
            entry_price=71000,
            quantity=10,
            strategy="bb_reversion",
            client_order_id="coid-001",
        )
        assert retry is recovered
        assert new_tracker.position_count == 1
