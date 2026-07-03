"""Unit tests for services.portfolio_monitor (Phase 3B).

Hermetic: fakeredis (sync, decode_responses) + tmp_path SQLite ledger + stub
calendar/notifier/positions providers. Pins:

* the FIXED 3D-UI Redis contract (field names + TTLs) on
  ``portfolio:equity:latest`` / ``stream:portfolio.equity``;
* equity composition (capital_base + track realized PnL + unrealized);
* month peak / stage / latch persistence across days + idempotent re-runs;
* SHADOW MODE NEVER ACTS — no sentinel, no suspend flag, no size gating;
* enforce-mode FULL_STOP trips the (tmp) sentinel + suspend flag + audit.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import fakeredis
import pytest

from services.portfolio_monitor.main import run_snapshot, trip_full_stop
from shared.portfolio.config import (
    TRACK_FUTURES,
    TRACK_STOCK,
    PortfolioConfig,
)
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

DAY1 = date(2026, 7, 6)  # Monday
DAY2 = date(2026, 7, 7)
NOW1 = datetime(2026, 7, 6, 19, 0)
NOW2 = datetime(2026, 7, 7, 19, 0)

LATEST_KEY = "portfolio:equity:latest"
STREAM_KEY = "stream:portfolio.equity"
SUSPEND_KEY = "futures:live:suspended"

# Fixed contract with the 3D UI lane — exact field-name set.
_CONTRACT_FIELDS = {
    "total_equity",
    "track_b_equity",
    "track_c_equity",
    "track_a_equity",
    "month_start_equity",
    "month_peak_equity",
    "monthly_mdd_pct",
    "stage",
    "mode",
    "degraded",
    "missing_components",
    "asof_ts",
}


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


class _ClosedCalendar:
    def is_market_day(self, _day: date) -> bool:
        return False


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, message: str, **_kwargs) -> None:
        self.messages.append(message)


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def ledger(tmp_path):
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    yield ledger
    ledger.close()


def _config(mode: str = "shadow", **overrides) -> PortfolioConfig:
    config = PortfolioConfig()  # defaults: B=10M, C=5M, A=None
    config.circuit_breaker.mode = mode
    for key, value in overrides.items():
        setattr(config.circuit_breaker, key, value)
    return config


def _seed_trade(ledger, track_id: str, pnl: float, day: date, seq: int = 0) -> None:
    ledger.record_trade(
        {
            "trade_id": f"{track_id}-{day.isoformat()}-{seq}",
            "asset_class": "stock" if track_id == TRACK_STOCK else "futures",
            "symbol": "TEST",
            "side": "sell",
            "pnl": pnl,
            "exit_time": f"{day.isoformat()}T15:30:00",
        },
        track_id=track_id,
    )


def _run(
    config,
    ledger,
    redis,
    *,
    day=DAY1,
    now=NOW1,
    positions=None,
    notifier=None,
    sentinel_path="/nonexistent/never-written",
    suspend_key=SUSPEND_KEY,
    calendar=None,
):
    return run_snapshot(
        config=config,
        ledger=ledger,
        redis=redis,
        positions_providers=positions
        or {TRACK_STOCK: lambda: [], TRACK_FUTURES: lambda: []},
        calendar=calendar or _AlwaysOpenCalendar(),
        notifier=notifier,
        trade_date=day,
        now=now,
        sentinel_path=sentinel_path,
        suspend_key=suspend_key,
    )


# ---------------------------------------------------------------------------
# Redis contract
# ---------------------------------------------------------------------------


class TestRedisContract:
    def test_latest_hash_fields_and_ttl(self, ledger, redis):
        assert _run(_config(), ledger, redis) == 0

        raw = redis.hgetall(LATEST_KEY)
        assert set(raw) == _CONTRACT_FIELDS
        assert raw["stage"] == "NORMAL"
        assert raw["mode"] == "shadow"
        assert raw["degraded"] == "false"
        # Track A missing pre-Phase 5 → "" + coverage in missing_components.
        assert raw["track_a_equity"] == ""
        assert "track_a" in json.loads(raw["missing_components"])
        assert float(raw["total_equity"]) == pytest.approx(15_000_000.0)
        assert datetime.fromisoformat(raw["asof_ts"]) == NOW1

        ttl = redis.ttl(LATEST_KEY)
        assert 0 < ttl <= 86400

    def test_stream_event_and_ttl(self, ledger, redis):
        _run(_config(), ledger, redis)
        entries = redis.xrange(STREAM_KEY)
        assert len(entries) == 1
        _, fields = entries[0]
        assert fields["stage"] == "NORMAL"
        assert fields["stage_changed"] == "false"
        assert fields["trade_date"] == DAY1.isoformat()
        assert 0 < redis.ttl(STREAM_KEY) <= 86400

    def test_stale_fields_never_linger(self, ledger, redis):
        redis.hset(LATEST_KEY, mapping={"legacy_field": "1"})
        _run(_config(), ledger, redis)
        assert "legacy_field" not in redis.hgetall(LATEST_KEY)


# ---------------------------------------------------------------------------
# Equity composition
# ---------------------------------------------------------------------------


class TestEquityComposition:
    def test_capital_realized_unrealized_sum(self, ledger, redis):
        _seed_trade(ledger, TRACK_STOCK, 100_000.0, DAY1)
        _seed_trade(ledger, TRACK_FUTURES, -50_000.0, DAY1)
        positions = {
            TRACK_STOCK: lambda: [{"unrealized_pnl": 10_000.0}],
            TRACK_FUTURES: lambda: [{"unrealized_pnl": -5_000.0}],
        }
        _run(_config(), ledger, redis, positions=positions)

        raw = redis.hgetall(LATEST_KEY)
        assert float(raw["track_b_equity"]) == pytest.approx(10_110_000.0)
        assert float(raw["track_c_equity"]) == pytest.approx(4_945_000.0)
        assert float(raw["total_equity"]) == pytest.approx(15_055_000.0)

    def test_daily_row_persisted_idempotently(self, ledger, redis):
        _run(_config(), ledger, redis)
        _run(_config(), ledger, redis)  # same-day re-run
        rows = ledger.query_portfolio_equity_daily()
        assert len(rows) == 1
        assert rows[0]["trade_date"] == DAY1.isoformat()
        assert rows[0]["month_peak_equity"] == pytest.approx(15_000_000.0)

    def test_non_market_day_skips_entirely(self, ledger, redis):
        assert _run(_config(), ledger, redis, calendar=_ClosedCalendar()) == 0
        assert redis.hgetall(LATEST_KEY) == {}
        assert ledger.query_portfolio_equity_daily() == []


# ---------------------------------------------------------------------------
# Stage transitions across days (peak / latch through the persisted rows)
# ---------------------------------------------------------------------------


class TestStageProgression:
    def test_loss_drives_reduce_stage_next_day(self, ledger, redis):
        _run(_config(), ledger, redis, day=DAY1, now=NOW1)  # peak 15.0M
        _seed_trade(ledger, TRACK_STOCK, -900_000.0, DAY2)  # -6% of total
        _run(_config(), ledger, redis, day=DAY2, now=NOW2)

        raw = redis.hgetall(LATEST_KEY)
        assert raw["stage"] == "REDUCE"
        assert float(raw["monthly_mdd_pct"]) == pytest.approx(-0.06)
        assert float(raw["month_peak_equity"]) == pytest.approx(15_000_000.0)

        events = redis.xrange(STREAM_KEY)
        assert events[-1][1]["stage_changed"] == "true"
        assert events[-1][1]["prev_stage"] == "NORMAL"

    def test_latch_holds_reduce_after_recovery(self, ledger, redis):
        _run(_config(), ledger, redis, day=DAY1, now=NOW1)
        _seed_trade(ledger, TRACK_STOCK, -900_000.0, DAY2)
        _run(_config(), ledger, redis, day=DAY2, now=NOW2)
        # full recovery next day
        _seed_trade(ledger, TRACK_STOCK, 900_000.0, date(2026, 7, 8))
        _run(
            _config(),
            ledger,
            redis,
            day=date(2026, 7, 8),
            now=datetime(2026, 7, 8, 19, 0),
        )
        assert redis.hgetall(LATEST_KEY)["stage"] == "REDUCE"  # latched

    def test_latch_off_relaxes_after_recovery(self, ledger, redis):
        config = _config(stage_latch=False)
        _run(config, ledger, redis, day=DAY1, now=NOW1)
        _seed_trade(ledger, TRACK_STOCK, -900_000.0, DAY2)
        _run(config, ledger, redis, day=DAY2, now=NOW2)
        _seed_trade(ledger, TRACK_STOCK, 900_000.0, date(2026, 7, 8))
        _run(
            config,
            ledger,
            redis,
            day=date(2026, 7, 8),
            now=datetime(2026, 7, 8, 19, 0),
        )
        assert redis.hgetall(LATEST_KEY)["stage"] == "NORMAL"

    def test_transition_records_risk_event_and_alert(self, ledger, redis):
        notifier = FakeNotifier()
        _run(_config(), ledger, redis, day=DAY1, now=NOW1, notifier=notifier)
        assert notifier.messages == []  # NORMAL start: nothing owed

        _seed_trade(ledger, TRACK_STOCK, -1_300_000.0, DAY2)  # ~-8.7% → HALT_NEW
        _run(_config(), ledger, redis, day=DAY2, now=NOW2, notifier=notifier)

        assert len(notifier.messages) == 1
        assert "HALT_NEW" in notifier.messages[0]
        assert "shadow" in notifier.messages[0]

        events = (
            ledger._require_conn()
            .execute("SELECT event_type, severity FROM risk_events")
            .fetchall()
        )
        assert [tuple(event) for event in events] == [
            ("portfolio_mdd_stage_transition", "warning")
        ]


# ---------------------------------------------------------------------------
# Shadow never acts / enforce FULL_STOP trips
# ---------------------------------------------------------------------------


class TestEnforcement:
    def _drive_full_stop(self, config, ledger, redis, tmp_path, notifier=None):
        sentinel = tmp_path / "sentinel" / "kis_kill_switch.tripped"
        _run(config, ledger, redis, day=DAY1, now=NOW1)
        _seed_trade(ledger, TRACK_STOCK, -2_000_000.0, DAY2)  # ~-13.3% → FULL_STOP
        _run(
            config,
            ledger,
            redis,
            day=DAY2,
            now=NOW2,
            notifier=notifier,
            sentinel_path=str(sentinel),
        )
        return sentinel

    def test_shadow_full_stop_never_trips_anything(self, ledger, redis, tmp_path):
        sentinel = self._drive_full_stop(_config("shadow"), ledger, redis, tmp_path)

        assert redis.hgetall(LATEST_KEY)["stage"] == "FULL_STOP"  # observed
        assert not sentinel.exists()  # …but no sentinel
        assert redis.get(SUSPEND_KEY) is None  # …and no suspend flag
        trip_events = (
            ledger._require_conn()
            .execute(
                "SELECT id FROM risk_events WHERE event_type='portfolio_mdd_full_stop_trip'"
            )
            .fetchall()
        )
        assert trip_events == []

    def test_off_mode_publishes_but_never_alerts_or_acts(self, ledger, redis, tmp_path):
        notifier = FakeNotifier()
        sentinel = self._drive_full_stop(
            _config("off"), ledger, redis, tmp_path, notifier=notifier
        )
        raw = redis.hgetall(LATEST_KEY)
        assert raw["mode"] == "off"
        assert raw["stage"] == "FULL_STOP"
        assert notifier.messages == []
        assert not sentinel.exists()
        assert redis.get(SUSPEND_KEY) is None

    def test_enforce_full_stop_trips_sentinel_flag_and_audit(
        self, ledger, redis, tmp_path
    ):
        sentinel = self._drive_full_stop(_config("enforce"), ledger, redis, tmp_path)

        assert sentinel.exists()
        assert "portfolio_mdd_full_stop" in sentinel.read_text()
        assert redis.get(SUSPEND_KEY) == "1"

        trip_events = (
            ledger._require_conn()
            .execute(
                "SELECT severity FROM risk_events "
                "WHERE event_type='portfolio_mdd_full_stop_trip'"
            )
            .fetchall()
        )
        assert [tuple(event) for event in trip_events] == [("critical",)]

    def test_enforce_reduce_does_not_trip(self, ledger, redis, tmp_path):
        sentinel = tmp_path / "sentinel.tripped"
        config = _config("enforce")
        _run(config, ledger, redis, day=DAY1, now=NOW1)
        _seed_trade(ledger, TRACK_STOCK, -900_000.0, DAY2)  # REDUCE only
        _run(
            config,
            ledger,
            redis,
            day=DAY2,
            now=NOW2,
            sentinel_path=str(sentinel),
        )
        assert redis.hgetall(LATEST_KEY)["stage"] == "REDUCE"
        assert not sentinel.exists()
        assert redis.get(SUSPEND_KEY) is None

    def test_trip_is_idempotent_when_sentinel_exists(self, ledger, redis, tmp_path):
        sentinel = tmp_path / "sentinel.tripped"
        sentinel.write_text("reason=pre_existing\n")

        from shared.portfolio.equity import PortfolioEquitySnapshot

        snapshot = PortfolioEquitySnapshot(
            trade_date=DAY2,
            track_a_equity=None,
            track_b_equity=8_000_000.0,
            track_c_equity=5_000_000.0,
            total_equity=13_000_000.0,
            month_start_equity=15_000_000.0,
            month_peak_equity=15_000_000.0,
            monthly_mdd_pct=-0.1333,
            raw_stage="FULL_STOP",
            stage="FULL_STOP",
            prev_stage="HALT_NEW",
            stage_changed=True,
            latched=False,
            mode="enforce",
            degraded=False,
            missing_components=(),
            asof_ts=NOW2,
        )
        actions = trip_full_stop(
            redis=redis,
            ledger=ledger,
            snapshot=snapshot,
            sentinel_path=str(sentinel),
            suspend_key=SUSPEND_KEY,
        )
        assert "sentinel_written" not in actions  # pre-existing → not overwritten
        assert "suspend_flag_set" in actions
        assert sentinel.read_text() == "reason=pre_existing\n"
