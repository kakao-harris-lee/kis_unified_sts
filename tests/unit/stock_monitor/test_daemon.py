"""StockMonitorDaemon: entry->position, exit->trade(pnl), signal->signals; recovery; MTM."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis
import fakeredis.aioredis
import pytest

import shared.streaming.trading_state as ts
from services.stock_monitor.alerts import AlertSink
from services.stock_monitor.daemon import StockMonitorDaemon
from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader

_KST = ZoneInfo("Asia/Seoul")


class _FakeNotifier:
    """Records dispatched messages so live-mode AlertSink emits can be asserted."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, message: str, **_kwargs: object) -> None:
        self.messages.append(message)


def _kst_at(hour: int, minute: int) -> datetime:
    """Fixed KST datetime on 2026-06-08 (a Monday) for now_fn injection."""
    return datetime(2026, 6, 8, hour, minute, tzinfo=_KST)


def _enc(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _fill(role: str, side: str, price: str, code: str = "005930") -> dict[str, str]:
    return {
        "signal_id": f"sig-{code}",
        "order_id": f"VO-{role}",
        "symbol": code,
        "side": side,
        "order_type": "market",
        "requested_price": price,
        "filled_price": price,
        "tick_size_points": "0.0",
        "slippage_ticks": "0.0",
        "quantity": "10",
        "requested_at_ms": "1700000000000",
        "filled_at_ms": "1700000000000",
        "latency_ms": "0",
        "venue": "KRX",
        "trade_role": role,
        "broker_error_code": "",
    }


def _final(code: str = "005930") -> dict[str, str]:
    return {
        "signal_id": f"sig-{code}",
        "code": code,
        "name": "삼성전자",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": "1700000000000",
        "metadata_json": "{}",
        "size_multiplier": "1.0",
        "filtered_at_ms": "1700000000000",
    }


class _FakeFeed:
    def __init__(self) -> None:
        self.prices: dict[str, dict[str, float]] = {}
        self.staleness: float | None = None

    def update_symbols(self, symbols: list[str]) -> None:
        pass

    async def get_current_price(self, symbol: str) -> dict[str, float]:
        return dict(self.prices.get(symbol, {}))

    def get_staleness_seconds(self) -> float | None:
        return self.staleness

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class _OneMessageRedis:
    def __init__(
        self,
        *,
        stream: bytes,
        msg_id: bytes,
        fields: dict[bytes, bytes],
    ) -> None:
        self.stream = stream
        self.msg_id = msg_id
        self.fields = fields
        self.acks: list[tuple[str, str, bytes]] = []
        self.on_ack = lambda: None
        self.fail_ack = False
        self._returned = False

    async def xreadgroup(self, **_kwargs):
        if self._returned:
            return []
        self._returned = True
        return [(self.stream, [(self.msg_id, self.fields)])]

    async def xack(self, stream: str, group: str, msg_id: bytes) -> None:
        self.acks.append((stream, group, msg_id))
        if self.fail_ack:
            raise ConnectionError("xack down")
        self.on_ack()


class _FailingReadRedis:
    def __init__(self, *, success_on_call: int | None = None) -> None:
        self.calls = 0
        self.success_on_call = success_on_call

    async def xreadgroup(self, **_kwargs):
        self.calls += 1
        if self.success_on_call is not None and self.calls == self.success_on_call:
            return []
        raise ConnectionError("redis down")


@pytest.fixture()
def wired(monkeypatch):
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    # decode_responses=True mirrors production RedisClient.get_client() so the
    # status reader returns str keys (status.get("state")) — not bytes.
    sync = fakeredis.FakeStrictRedis(server=server, db=1, decode_responses=True)
    monkeypatch.setattr(ts, "_get_redis", lambda: sync)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
    daemon = StockMonitorDaemon(
        redis=redis,
        feed=_FakeFeed(),
        publisher=TradingStatePublisher(asset_class="stock"),
        alert_sink=None,
        positions_key="trading:stock:positions",
        fill_stream="order.fill.stock.shadow",
        signal_stream="signal.final.stock.shadow",
        consumer_group="stock_monitor",
        worker_id="test",
        fee_rate=0.003,
        status_interval=5.0,
    )
    return daemon, redis, TradingStateReader(asset_class="stock")


@pytest.fixture()
def alerting(monkeypatch):
    """Daemon wired with a real (live-mode) AlertSink + injectable now/clock.

    Returns (build, redis, feed, notifier): ``build(now_fn=...)`` constructs the
    daemon with that injected clock so health/digest KST windows are testable.
    """
    server = fakeredis.FakeServer()
    redis = fakeredis.aioredis.FakeRedis(server=server, db=1)
    # decode_responses=True mirrors production RedisClient.get_client() so the
    # status reader returns str keys (status.get("state")) — not bytes.
    sync = fakeredis.FakeStrictRedis(server=server, db=1, decode_responses=True)
    monkeypatch.setattr(ts, "_get_redis", lambda: sync)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "shadow")
    notifier = _FakeNotifier()
    sink = AlertSink(notifier=notifier, mode="live", pnl_alert_pct=3.0)
    feed = _FakeFeed()

    def build(now_fn):
        return StockMonitorDaemon(
            redis=redis,
            feed=feed,
            publisher=TradingStatePublisher(asset_class="stock"),
            alert_sink=sink,
            positions_key="trading:stock:positions",
            fill_stream="order.fill.stock.shadow",
            signal_stream="signal.final.stock.shadow",
            consumer_group="stock_monitor",
            worker_id="test",
            fee_rate=0.003,
            status_interval=5.0,
            now_fn=now_fn,
            health_stale_seconds=600.0,
            health_cooldown_seconds=1800.0,
            digest_time_kst="15:40",
        )

    return build, redis, feed, notifier, sink


@pytest.mark.asyncio
async def test_signal_then_entry_then_exit(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_signal(_enc(_final()))
    assert reader.get_signals()[0]["strategy"] == "vr_composite"

    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    positions = reader.get_positions()
    assert len(positions) == 1 and positions[0]["strategy"] == "vr_composite"

    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    assert reader.get_positions() == []
    trades = reader.get_trades()
    assert len(trades) == 1
    # pnl = (73000-71000)*10 - (71000+73000)*10*0.0015 = 20000 - 2160 = 17840
    assert round(trades[0]["pnl"], 0) == 17840.0
    assert trades[0]["strategy"] == "vr_composite"


@pytest.mark.asyncio
async def test_exit_without_entry_skips_trade(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    assert reader.get_trades() == []


@pytest.mark.asyncio
async def test_recover_open_from_positions_hash(wired) -> None:
    daemon, redis, reader = wired
    await redis.hset(
        "trading:stock:positions",
        "005930",
        json.dumps(
            {
                "code": "005930",
                "entry_price": 71000.0,
                "quantity": 10,
                "opened_at_ms": 1_700_000_000_000,
                "state": "SURVIVAL",
                "signal_id": "sig-005930",
            }
        ),
    )
    await daemon.recover_open_positions()
    await daemon.handle_fill(_enc(_fill("exit", "SELL", "73000.0")))
    trades = reader.get_trades()
    assert len(trades) == 1 and trades[0]["entry_price"] == 71000.0


@pytest.mark.asyncio
async def test_recover_reconciles_dashboard_clears_orphans(wired) -> None:
    """Recovery purges a stale/foreign dashboard field, keeps the real one.

    Reproduces the cutover-orphan case: a UUID-keyed position left in the
    dashboard hash by the retired monolithic orchestrator (the code-keyed
    decoupled pipeline never rewrites UUID fields) must be dropped, while the
    position recovered from the authoritative working-store is republished.
    """
    daemon, redis, reader = wired
    # Orphan UUID-keyed field already in the dashboard positions hash.
    daemon.publisher.publish_raw_position(
        "77f7c951-orphan",
        {"id": "77f7c951-orphan", "code": "086520", "name": "에코프로"},
    )
    assert {p["id"] for p in reader.get_positions()} == {"77f7c951-orphan"}

    # Authoritative working-store holds a different, valid (code-keyed) position.
    await redis.hset(
        "trading:stock:positions",
        "005930",
        json.dumps(
            {
                "code": "005930",
                "entry_price": 71000.0,
                "quantity": 10,
                "opened_at_ms": 1_700_000_000_000,
                "state": "SURVIVAL",
                "signal_id": "sig-005930",
            }
        ),
    )

    await daemon.recover_open_positions()

    # Orphan purged; only the recovered working-store position remains.
    assert {p["id"] for p in reader.get_positions()} == {"005930"}


@pytest.mark.asyncio
async def test_recover_skips_foreign_records(wired) -> None:
    daemon, redis, reader = wired
    # orchestrator-style record: no opened_at_ms -> must be skipped
    await redis.hset(
        "trading:stock:positions",
        "uuid-1",
        json.dumps(
            {
                "id": "uuid-1",
                "code": "000660",
                "entry_price": 50000.0,
                "quantity": 5,
                "entry_time": "2026-06-06T00:00:00+00:00",
            }
        ),
    )
    await daemon.recover_open_positions()
    assert "000660" not in daemon._open


@pytest.mark.asyncio
async def test_mark_to_market(wired) -> None:
    daemon, redis, reader = wired
    await daemon.handle_signal(_enc(_final()))
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    daemon.feed.prices["005930"] = {"close": 72000.0}
    await daemon.publish_status_and_mtm()
    pos = reader.get_positions()[0]
    assert pos["current_price"] == 72000.0
    assert pos["unrealized_pnl"] == (72000.0 - 71000.0) * 10


@pytest.mark.asyncio
async def test_status_reports_running_with_aggregates(wired) -> None:
    """Status row carries state=running + nested positions/strategies aggregates.

    Regression: the decoupled stock pipeline previously published only
    {open_positions, worker_id, source}, so the dashboard's
    _status_response_from_raw defaulted state -> "stopped" and the cockpit
    stock tab rendered a halted/empty system while the daemon was live.
    """
    daemon, redis, reader = wired
    await daemon.handle_signal(_enc(_final()))
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    daemon.feed.prices["005930"] = {"close": 72000.0}

    await daemon.publish_status_and_mtm()

    status = reader.get_status()
    assert status["state"] == "running"
    assert status["source"] == "stock_monitor"
    assert status["open_positions"] == 1
    assert status["positions"]["open_positions"] == 1
    assert status["positions"]["unrealized_pnl"] == (72000.0 - 71000.0) * 10
    assert status["positions"]["winning_positions"] == 1
    assert status["strategies"]["strategies"] == ["vr_composite"]
    assert status["strategies"]["strategy_count"] == 1


@pytest.mark.asyncio
async def test_status_reports_running_when_flat(wired) -> None:
    """A flat daemon (no open positions) still reports state=running, not stopped."""
    daemon, redis, reader = wired

    await daemon.publish_status_and_mtm()

    status = reader.get_status()
    assert status["state"] == "running"
    assert status["open_positions"] == 0
    assert status["positions"]["open_positions"] == 0
    assert status["positions"]["unrealized_pnl"] == 0.0
    assert status["strategies"]["strategies"] == []


@pytest.mark.asyncio
async def test_mtm_survives_concurrent_mutation(wired) -> None:
    """A fill arriving mid-MTM (yielded on the price await) must not crash."""
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0", code="005930")))
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "50000.0", code="000660")))

    class _MutatingFeed:
        prices = {"005930": {"close": 72000.0}, "000660": {"close": 51000.0}}

        async def get_current_price(self, symbol: str) -> dict[str, float]:
            # Simulate a concurrent exit fill popping _open during iteration.
            daemon._open.pop("000660", None)
            return dict(self.prices.get(symbol, {}))

    daemon.feed = _MutatingFeed()
    # Iterates a snapshot -> no "dictionary changed size during iteration".
    await daemon.publish_status_and_mtm()
    assert "000660" not in daemon._open


@pytest.mark.asyncio
async def test_signal_meta_fifo_eviction(wired) -> None:
    """Pushing > signal_meta_max signals evicts the oldest (FIFO)."""
    daemon, redis, reader = wired
    daemon.signal_meta_max = 3
    for i in range(5):
        await daemon.handle_signal(_enc(_final(code=f"00000{i}")))
    assert len(daemon._signal_meta) == 3
    # oldest two evicted, newest three retained
    assert "sig-000000" not in daemon._signal_meta
    assert "sig-000001" not in daemon._signal_meta
    assert "sig-000004" in daemon._signal_meta


@pytest.mark.asyncio
async def test_entry_without_signal_meta_is_graceful(wired) -> None:
    """Entry fill with no prior signal -> position with empty strategy/name."""
    daemon, redis, reader = wired
    await daemon.handle_fill(_enc(_fill("entry", "BUY", "71000.0")))
    pos = reader.get_positions()[0]
    assert pos["strategy"] == ""
    assert pos["name"] == ""
    assert pos["entry_price"] == 71000.0


@pytest.mark.asyncio
async def test_consume_loop_logs_audit_context_before_poison_pill_ack(
    wired, caplog
) -> None:
    daemon, _redis, _reader = wired
    fields = {
        b"signal_id": b"sig-stock-1",
        b"code": b"005930",
        b"strategy": b"vr_composite",
        b"account_number": b"secret",
    }
    redis = _OneMessageRedis(
        stream=b"signal.final.stock.shadow",
        msg_id=b"1700000000000-7",
        fields=fields,
    )
    daemon.redis = redis
    redis.on_ack = daemon._stop.set

    async def fail_handler(_fields):
        raise RuntimeError("bad stock signal")

    daemon.handle_signal = fail_handler
    caplog.set_level(logging.ERROR, logger="services.stock_monitor.daemon")

    await daemon._consume_loop()

    assert redis.acks == [
        ("signal.final.stock.shadow", "stock_monitor", b"1700000000000-7")
    ]
    messages = [record.getMessage() for record in caplog.records]
    drop_log = next(
        message for message in messages if "event=stream_message_dropped" in message
    )
    assert "stream=signal.final.stock.shadow" in drop_log
    assert "consumer_group=stock_monitor" in drop_log
    assert "worker_id=test" in drop_log
    assert "msg_id=1700000000000-7" in drop_log
    assert "ack=true" in drop_log
    assert "reason=handler_exception" in drop_log
    assert "signal_id=sig-stock-1" in drop_log
    assert "code=005930" in drop_log
    assert "strategy=vr_composite" in drop_log
    assert "account_number=secret" not in drop_log


@pytest.mark.asyncio
async def test_consume_loop_logs_ack_failed_when_poison_pill_xack_fails(
    wired, caplog
) -> None:
    daemon, _redis, _reader = wired
    fields = {
        b"signal_id": b"sig-stock-ack",
        b"code": b"005930",
        b"strategy": b"vr_composite",
    }
    redis = _OneMessageRedis(
        stream=b"signal.final.stock.shadow",
        msg_id=b"1700000000000-8",
        fields=fields,
    )
    redis.fail_ack = True
    daemon.redis = redis

    async def fail_handler(_fields):
        raise RuntimeError("bad stock signal")

    daemon.handle_signal = fail_handler
    caplog.set_level(logging.ERROR, logger="services.stock_monitor.daemon")

    with pytest.raises(ConnectionError):
        await daemon._consume_loop()

    messages = [record.getMessage() for record in caplog.records]
    assert not any("event=stream_message_dropped" in message for message in messages)
    ack_log = next(
        message for message in messages if "event=stream_message_ack_failed" in message
    )
    assert "stream=signal.final.stock.shadow" in ack_log
    assert "consumer_group=stock_monitor" in ack_log
    assert "worker_id=test" in ack_log
    assert "msg_id=1700000000000-8" in ack_log
    assert "reason=handler_exception" in ack_log
    assert "signal_id=sig-stock-ack" in ack_log
    assert "code=005930" in ack_log
    assert "strategy=vr_composite" in ack_log


@pytest.mark.asyncio
async def test_consume_loop_rate_limits_repeated_read_errors(
    wired, monkeypatch, caplog
) -> None:
    daemon, _redis, _reader = wired
    redis = _FailingReadRedis()
    daemon.redis = redis
    caplog.set_level(logging.ERROR, logger="services.stock_monitor.daemon")
    real_sleep = asyncio.sleep

    async def fast_sleep(_seconds=0):
        await real_sleep(0)

    monkeypatch.setattr("services.stock_monitor.daemon.asyncio.sleep", fast_sleep)

    async def stop_after_errors():
        while redis.calls < 3:
            await asyncio.sleep(0)
        await daemon.stop()

    await asyncio.gather(daemon._consume_loop(), stop_after_errors())

    messages = [
        record.getMessage()
        for record in caplog.records
        if "event=monitor_stream_read_error" in record.getMessage()
    ]
    assert messages == [
        'event=monitor_stream_read_error streams="order.fill.stock.shadow,signal.final.stock.shadow" consumer_group=stock_monitor worker_id=test sleep_seconds=0.5'
    ]


@pytest.mark.asyncio
async def test_consume_loop_read_error_logs_again_after_success(
    wired, monkeypatch, caplog
) -> None:
    daemon, _redis, _reader = wired
    redis = _FailingReadRedis(success_on_call=2)
    daemon.redis = redis
    caplog.set_level(logging.ERROR, logger="services.stock_monitor.daemon")
    real_sleep = asyncio.sleep

    async def fast_sleep(_seconds=0):
        await real_sleep(0)

    monkeypatch.setattr("services.stock_monitor.daemon.asyncio.sleep", fast_sleep)

    async def stop_after_errors():
        while redis.calls < 3:
            await asyncio.sleep(0)
        await daemon.stop()

    await asyncio.gather(daemon._consume_loop(), stop_after_errors())

    messages = [
        record.getMessage()
        for record in caplog.records
        if "event=monitor_stream_read_error" in record.getMessage()
    ]
    assert messages == [
        'event=monitor_stream_read_error streams="order.fill.stock.shadow,signal.final.stock.shadow" consumer_group=stock_monitor worker_id=test sleep_seconds=0.5',
        'event=monitor_stream_read_error streams="order.fill.stock.shadow,signal.final.stock.shadow" consumer_group=stock_monitor worker_id=test sleep_seconds=0.5',
    ]


# -- spec §7 ②/③: health anomaly + session digest --------------------------- #


@pytest.mark.asyncio
async def test_digest_emits_once_per_day_after_digest_time(alerting) -> None:
    """At/after 15:40 KST with ≥1 trade -> one digest; a 2nd check same day no-op.

    Follows the real daily lifecycle: the 09:00 tick resets first, THEN trades
    accumulate, THEN the 15:40+ tick emits (a same-day 09:00 reset never wipes
    intraday trades because reset is once/day, guarded by ``_digest_reset_date``).
    """
    build, redis, feed, notifier, sink = alerting
    clock = {"now": _kst_at(9, 0)}
    daemon = build(now_fn=lambda: clock["now"])

    # 09:00 reset tick (clears any carryover)
    await daemon._check_health_and_digest()

    # intraday: accumulate one trade via the AlertSink exit path (on_exit -> add)
    await sink.on_exit(code="005930", pnl=17840.0, pnl_pct=2.82)
    assert sink.digest.trades == 1

    # 15:41 digest tick (same day -> reset guard prevents a second reset)
    clock["now"] = _kst_at(15, 41)
    await daemon._check_health_and_digest()
    digests = [m for m in notifier.messages if "세션 다이제스트" in m]
    assert len(digests) == 1

    # second check the same day must NOT re-emit
    await daemon._check_health_and_digest()
    digests = [m for m in notifier.messages if "세션 다이제스트" in m]
    assert len(digests) == 1


@pytest.mark.asyncio
async def test_empty_digest_does_not_emit(alerting) -> None:
    """0 trades at 15:41 KST -> digest is skipped (and date still marked)."""
    build, redis, feed, notifier, sink = alerting
    daemon = build(now_fn=lambda: _kst_at(15, 41))
    assert sink.digest.trades == 0

    await daemon._check_health_and_digest()
    assert [m for m in notifier.messages if "세션 다이제스트" in m] == []
    # marked emitted so it won't recheck all day
    assert daemon._digest_emitted_date == _kst_at(15, 41).date().isoformat()


@pytest.mark.asyncio
async def test_digest_resets_at_market_open(alerting) -> None:
    """09:01 KST tick resets yesterday's accumulator (digest.trades -> 0)."""
    build, redis, feed, notifier, sink = alerting
    daemon = build(now_fn=lambda: _kst_at(9, 1))
    sink.digest.add(pnl=1000.0)  # stale carryover from "yesterday"
    assert sink.digest.trades == 1

    await daemon._check_health_and_digest()
    assert sink.digest.trades == 0


@pytest.mark.asyncio
async def test_health_alert_during_market_hours_cooldown_gated(alerting) -> None:
    """Stale feed (700s > 600s) at 10:00 KST -> one health alert; 2nd within cooldown no-op."""
    build, redis, feed, notifier, sink = alerting
    daemon = build(now_fn=lambda: _kst_at(10, 0))
    feed.staleness = 700.0

    await daemon._check_health_and_digest()
    health = [m for m in notifier.messages if "헬스 이상" in m]
    assert len(health) == 1

    # second check within the cooldown window must not re-send
    await daemon._check_health_and_digest()
    health = [m for m in notifier.messages if "헬스 이상" in m]
    assert len(health) == 1


@pytest.mark.asyncio
async def test_health_alert_suppressed_outside_market_and_when_fresh(alerting) -> None:
    """No health alert outside market hours, nor when staleness is None/below threshold."""
    build, redis, feed, notifier, sink = alerting

    # outside market hours (16:00 KST) even with a very stale feed
    feed.staleness = 9999.0
    daemon = build(now_fn=lambda: _kst_at(16, 0))
    await daemon._check_health_and_digest()
    assert [m for m in notifier.messages if "헬스 이상" in m] == []

    # in market hours but no ticks yet (None) -> no alert
    feed.staleness = None
    daemon = build(now_fn=lambda: _kst_at(10, 0))
    await daemon._check_health_and_digest()
    assert [m for m in notifier.messages if "헬스 이상" in m] == []

    # in market hours but below threshold (300s < 600s) -> no alert
    feed.staleness = 300.0
    await daemon._check_health_and_digest()
    assert [m for m in notifier.messages if "헬스 이상" in m] == []
