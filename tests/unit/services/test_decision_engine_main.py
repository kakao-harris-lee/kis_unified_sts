"""Tests for services/decision_engine/main.py — Phase 4 Task 10."""

import asyncio
import logging
from datetime import datetime, timezone

import fakeredis.aioredis
import pytest

from services.decision_engine.main import DecisionEngineDaemon
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal
from shared.streaming.audit import decode_stream_id

CANDIDATE_STREAM = "signal.candidate.futures"


def _ctx(now=None) -> MarketContext:
    return MarketContext(
        now=now or datetime(2026, 4, 28, 9, 30, tzinfo=timezone(timedelta(hours=9))),
        symbol="A05603",
        current_price=331.20,
        prev_close=331.00,
        today_open=331.10,
        vwap=331.15,
        atr_14=0.5,
        atr_90th_percentile=0.7,
        last_15min_high=331.30,
        last_15min_low=331.00,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )


from datetime import timedelta  # noqa: E402


class _AlwaysSetup(Setup):
    CONFIG_CLASS = type("_StubConfig", (), {})

    def check(self, ctx):
        return Signal(
            setup_type="A_gap_reversion",
            direction="long",
            symbol=ctx.symbol,
            entry_price=ctx.current_price,
            stop_loss=ctx.current_price - 1.0,
            take_profit=ctx.current_price + 2.0,
            confidence=0.8,
            valid_until=ctx.now + timedelta(hours=1),
            generated_at=ctx.now,
        )


class _NeverSetup(Setup):
    CONFIG_CLASS = type("_StubConfig", (), {})

    def check(self, ctx):  # noqa: ARG002 — abstract signature requires ctx
        return None


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def context_provider():
    """Returns a fresh context on each tick."""
    contexts = [_ctx()]

    async def _provider():
        return contexts.pop(0) if contexts else None

    return _provider


def _make_daemon(*, redis, setups, context_provider):
    return DecisionEngineDaemon(
        redis=redis,
        setups=setups,
        context_provider=context_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
    )


@pytest.mark.asyncio
async def test_setup_fires_publishes_candidate(redis, context_provider):
    daemon = _make_daemon(
        redis=redis, setups=[_AlwaysSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) >= 1
    fields = entries[0][1]
    assert fields[b"setup_type"] == b"A_gap_reversion"
    assert fields[b"direction"] == b"long"
    assert b"signal_id" in fields


@pytest.mark.asyncio
async def test_no_setup_fires_no_candidate(redis, context_provider):
    daemon = _make_daemon(
        redis=redis, setups=[_NeverSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert entries == []


@pytest.mark.asyncio
async def test_candidate_stream_has_ttl(redis, context_provider):
    daemon = _make_daemon(
        redis=redis, setups=[_AlwaysSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    ttl = await redis.ttl(CANDIDATE_STREAM)
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_publish_logs_signal_published_audit_record(
    redis, context_provider, caplog
):
    daemon = _make_daemon(redis=redis, setups=[], context_provider=context_provider)
    signal = _AlwaysSetup().check(_ctx())

    with caplog.at_level(logging.INFO, logger="services.decision_engine.main"):
        await daemon._publish(signal)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    msg_id = decode_stream_id(entries[0][0])
    signal_id = entries[0][1][b"signal_id"].decode()

    records = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO
        and "event=signal_published" in record.getMessage()
    ]
    assert len(records) == 1
    message = records[0].getMessage()
    assert f"stream={CANDIDATE_STREAM}" in message
    assert f"msg_id={msg_id}" in message
    assert f"signal_id={signal_id}" in message
    assert "setup_type=A_gap_reversion" in message
    assert "symbol=A05603" in message
    assert "direction=long" in message


@pytest.mark.asyncio
async def test_publish_attaches_futures_context_trace_when_wired(redis):
    import json

    import fakeredis

    sync = fakeredis.FakeStrictRedis(decode_responses=True)
    sync.hset(
        "futures:context:latest",
        mapping={
            "roll_state": "pre_roll",
            "days_to_expiry": "4",
            "new_entry_front_allowed": "true",
            "basis_regime": "contango",
            "foreign_flow_regime": "buy",
            "market_risk_band": "ELEVATED",
            "margin_risk_level": "watch",
            "margin_usage_pct": "0.5",
            "degraded": "false",
            "asof_ts": "2026-07-01T10:00:00",
        },
    )
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[],
        context_provider=lambda: None,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        futures_context_redis=sync,
    )
    await daemon._publish(_AlwaysSetup().check(_ctx()))

    entries = await redis.xrange(CANDIDATE_STREAM)
    trace = json.loads(entries[0][1][b"futures_context"].decode())
    assert trace["roll_state"] == "pre_roll"
    assert trace["days_to_expiry"] == 4
    assert trace["basis_regime"] == "contango"
    assert trace["margin_risk_level"] == "watch"
    assert trace["degraded"] is False


@pytest.mark.asyncio
async def test_publish_no_futures_context_field_when_unwired(redis, context_provider):
    daemon = _make_daemon(redis=redis, setups=[], context_provider=context_provider)
    await daemon._publish(_AlwaysSetup().check(_ctx()))
    entries = await redis.xrange(CANDIDATE_STREAM)
    assert b"futures_context" not in entries[0][1]


@pytest.mark.asyncio
async def test_publish_futures_context_missing_key_is_noop(redis):
    import fakeredis

    sync = fakeredis.FakeStrictRedis(decode_responses=True)  # empty — no key
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[],
        context_provider=lambda: None,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        futures_context_redis=sync,
    )
    await daemon._publish(_AlwaysSetup().check(_ctx()))
    entries = await redis.xrange(CANDIDATE_STREAM)
    assert b"futures_context" not in entries[0][1]


@pytest.mark.asyncio
async def test_publish_does_not_log_success_when_ttl_refresh_fails(
    redis, context_provider, caplog, monkeypatch
):
    daemon = _make_daemon(redis=redis, setups=[], context_provider=context_provider)
    signal = _AlwaysSetup().check(_ctx())

    async def fail_expire(*_args, **_kwargs):
        raise ConnectionError("expire failed")

    monkeypatch.setattr(redis, "expire", fail_expire)

    with caplog.at_level(logging.INFO, logger="services.decision_engine.main"):
        with pytest.raises(ConnectionError):
            await daemon._publish(signal)

    assert not any(
        "event=signal_published" in record.getMessage() for record in caplog.records
    )


@pytest.mark.asyncio
async def test_signal_id_is_stable_uuid_per_signal(redis, context_provider):
    """Each emitted signal gets a fresh UUID — not deterministic per ctx."""
    contexts = [_ctx(), _ctx(now=_ctx().now + timedelta(minutes=1))]

    async def _provider():
        return contexts.pop(0) if contexts else None

    daemon = _make_daemon(
        redis=redis, setups=[_AlwaysSetup()], context_provider=_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(CANDIDATE_STREAM)
    if len(entries) >= 2:
        assert entries[0][1][b"signal_id"] != entries[1][1][b"signal_id"]


@pytest.mark.asyncio
async def test_setup_exception_does_not_kill_daemon(redis, context_provider):
    class _RaisingSetup(Setup):
        CONFIG_CLASS = type("_StubConfig", (), {})

        def check(self, ctx):  # noqa: ARG002 — abstract signature requires ctx
            raise RuntimeError("test")

    contexts = [_ctx(), _ctx()]

    async def _provider():
        return contexts.pop(0) if contexts else None

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_RaisingSetup(), _AlwaysSetup()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    # Should not raise
    await asyncio.gather(daemon.run(), _stop_after())
    # And the AlwaysSetup still fired
    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) >= 1
