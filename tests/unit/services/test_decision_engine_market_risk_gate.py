"""Tests for the market-risk ENTRY gate wiring in services/decision_engine.

Phase 2D (roadmap §5.2 track C): the DecisionEngineDaemon evaluates the
shared market-risk gate per fired entry candidate (side = signal_direction),
attaches the ``market_risk_gate`` trace payload in every mode, rejects
blocked entries only in enforce mode, and seeds the enforce-mode size factor
into the candidate's ``entry_size_factor`` field for downstream
multiplicative composition (risk_filter x order_router).

Hermetic: fakeredis only — async client for the candidate stream, sync
client for the market:risk:latest hash (the shared evaluator is sync).
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import fakeredis
import fakeredis.aioredis
import pytest

from services.decision_engine.main import DecisionEngineDaemon
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal
from shared.risk.market_risk_gate import MarketRiskGateConfig
from shared.risk.market_risk_score import KST

CANDIDATE_STREAM = "signal.candidate.futures"
GATE_HASH_KEY = "market:risk:latest"
FILL_STREAM = "order.fill.futures"
FINAL_STREAM = "signal.final.futures"
LOGGER_NAME = "services.decision_engine.main"

_KST_TZ = timezone(timedelta(hours=9))


def _ctx(now=None) -> MarketContext:
    return MarketContext(
        now=now or datetime(2026, 4, 28, 9, 30, tzinfo=_KST_TZ),
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


class _DirectionSetup(Setup):
    """Always fires a signal in the configured direction."""

    CONFIG_CLASS = type("_StubConfig", (), {})

    def __init__(self, direction: str = "long") -> None:
        super().__init__()
        self._direction = direction

    def check(self, ctx):
        long = self._direction == "long"
        return Signal(
            setup_type="A_gap_reversion",
            direction=self._direction,
            symbol=ctx.symbol,
            entry_price=ctx.current_price,
            stop_loss=ctx.current_price + (-1.0 if long else 1.0),
            take_profit=ctx.current_price + (2.0 if long else -2.0),
            confidence=0.8,
            valid_until=ctx.now + timedelta(hours=1),
            generated_at=ctx.now,
        )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def gate_redis():
    return fakeredis.FakeRedis(db=1, decode_responses=True)


def _seed_gate_hash(gate_redis, band: str, *, score: float = 75.0) -> None:
    """Publish a fresh (non-stale, non-degraded) market-risk hash."""
    gate_redis.hset(
        GATE_HASH_KEY,
        mapping={
            "score": str(score),
            "band": band,
            "regime": "risk_off",
            "degraded": "false",
            "asof_ts": datetime.now(KST).replace(tzinfo=None).isoformat(),
        },
    )


def _provider_for(count: int = 1):
    contexts = [_ctx(now=_ctx().now + timedelta(minutes=i)) for i in range(count)]

    async def _provider():
        return contexts.pop(0) if contexts else None

    return _provider


def _make_daemon(*, redis, setups, provider, mode: str, gate_redis):
    return DecisionEngineDaemon(
        redis=redis,
        setups=setups,
        context_provider=provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        market_risk_gate_config=MarketRiskGateConfig(mode=mode),
        market_risk_redis=gate_redis,
    )


async def _run_until_drained(daemon, duration: float = 0.05) -> None:
    async def _stop_after():
        await asyncio.sleep(duration)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())


def _gate_payload(fields: dict[bytes, bytes]) -> dict:
    return json.loads(fields[b"market_risk_gate"].decode())


# ---------------------------------------------------------------------------
# shadow mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_high_long_publishes_with_trace_and_no_size_change(
    redis, gate_redis, caplog
):
    """Shadow never rejects/resizes; would_block + observed factor in trace."""
    _seed_gate_hash(gate_redis, "HIGH")
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        provider=_provider_for(),
        mode="shadow",
        gate_redis=gate_redis,
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    fields = entries[0][1]
    payload = _gate_payload(fields)
    assert payload["mode"] == "shadow"
    assert payload["allow"] is True
    assert payload["would_block"] is True
    assert payload["size_factor"] == 0.5
    assert payload["band"] == "HIGH"
    # Shadow never applies the size factor — downstream sees neutral 1.0.
    assert float(fields[b"entry_size_factor"]) == 1.0
    shadow_logs = [
        r.getMessage()
        for r in caplog.records
        if "event=market_risk_gate_shadow" in r.getMessage()
    ]
    assert len(shadow_logs) == 1
    assert "would_block=true" in shadow_logs[0]
    assert "size_factor=0.5" in shadow_logs[0]


@pytest.mark.asyncio
async def test_shadow_observation_log_is_throttled(redis, gate_redis, caplog):
    """Repeated shadow observations within the interval log only once."""
    _seed_gate_hash(gate_redis, "HIGH")
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        provider=_provider_for(count=3),
        mode="shadow",
        gate_redis=gate_redis,
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 3  # every candidate still published
    shadow_logs = [
        r for r in caplog.records if "event=market_risk_gate_shadow" in r.getMessage()
    ]
    assert len(shadow_logs) == 1  # default 300 s interval >> test runtime


# ---------------------------------------------------------------------------
# enforce mode — reaction matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enforce_high_blocks_long_and_records_reason(redis, gate_redis, caplog):
    _seed_gate_hash(gate_redis, "HIGH", score=74.2)
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=gate_redis,
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await _run_until_drained(daemon)

    assert await redis.xrange(CANDIDATE_STREAM) == []
    rejects = [
        r.getMessage()
        for r in caplog.records
        if "event=entry_rejected" in r.getMessage()
    ]
    assert len(rejects) == 1
    assert "stage=market_risk_gate" in rejects[0]
    assert "band=HIGH" in rejects[0]
    assert "block_new_long" in rejects[0]
    assert "direction=long" in rejects[0]


@pytest.mark.asyncio
async def test_enforce_high_allows_short_with_half_size(redis, gate_redis):
    """Long/short symmetry: HIGH blocks only new longs; shorts get 0.5x."""
    _seed_gate_hash(gate_redis, "HIGH")
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("short")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=gate_redis,
    )

    await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    fields = entries[0][1]
    assert fields[b"direction"] == b"short"
    assert float(fields[b"entry_size_factor"]) == 0.5
    payload = _gate_payload(fields)
    assert payload["allow"] is True
    assert payload["would_block"] is False
    assert payload["mode"] == "enforce"


@pytest.mark.asyncio
async def test_enforce_elevated_seeds_size_factor_for_composition(redis, gate_redis):
    """ELEVATED 0.7 rides entry_size_factor; risk_filter multiplies it into
    the RiskFilterLayer size_multiplier product downstream (see
    test_risk_filter_main.py composition test)."""
    _seed_gate_hash(gate_redis, "ELEVATED", score=62.0)
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=gate_redis,
    )

    await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    fields = entries[0][1]
    assert float(fields[b"entry_size_factor"]) == 0.7
    payload = _gate_payload(fields)
    assert payload["size_factor"] == 0.7
    assert payload["band"] == "ELEVATED"


@pytest.mark.asyncio
async def test_enforce_critical_blocks_both_sides(redis, gate_redis, caplog):
    _seed_gate_hash(gate_redis, "CRITICAL", score=90.0)
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long"), _DirectionSetup("short")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=gate_redis,
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await _run_until_drained(daemon)

    assert await redis.xrange(CANDIDATE_STREAM) == []
    rejects = [
        r.getMessage()
        for r in caplog.records
        if "event=entry_rejected" in r.getMessage()
    ]
    assert len(rejects) == 2
    assert all("block_all_entries" in msg for msg in rejects)


# ---------------------------------------------------------------------------
# fail-open behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_hash_fails_open_in_enforce(redis, gate_redis):
    """No market:risk:latest hash — entry passes with neutral size."""
    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=gate_redis,  # empty — hash never seeded
    )

    await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    fields = entries[0][1]
    assert float(fields[b"entry_size_factor"]) == 1.0
    payload = _gate_payload(fields)
    assert payload["allow"] is True
    assert payload["reason"] == "fail_open:missing"


@pytest.mark.asyncio
async def test_gate_redis_error_fails_open(redis):
    """A broken gate-redis client can never block the entry path."""

    class _BrokenRedis:
        def hgetall(self, _key):
            raise ConnectionError("gate redis down")

    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=_BrokenRedis(),
    )

    await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    payload = _gate_payload(entries[0][1])
    assert payload["allow"] is True
    assert payload["reason"].startswith("fail_open:redis_error")


@pytest.mark.asyncio
async def test_unwired_gate_keeps_legacy_candidate_shape(redis):
    """Without gate config the candidate carries no gate fields (back-compat)."""
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_DirectionSetup("long")],
        context_provider=_provider_for(),
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
    )

    await _run_until_drained(daemon)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    fields = entries[0][1]
    assert b"market_risk_gate" not in fields
    assert b"entry_size_factor" not in fields


# ---------------------------------------------------------------------------
# entry-only invariant — exit / kill_switch lanes untouched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_critical_enforce_leaves_exit_streams_untouched(redis, gate_redis):
    """The gate blocks NEW entries only: pre-existing fill/final streams
    (the exit lane feeding pseudo-OCO / kill_switch) are never touched."""
    _seed_gate_hash(gate_redis, "CRITICAL")
    await redis.xadd(
        FILL_STREAM,
        {"signal_id": "sig-old", "trade_role": "stop_loss", "symbol": "A05603"},
    )
    await redis.xadd(
        FINAL_STREAM,
        {"signal_id": "sig-old", "setup_type": "A_gap_reversion"},
    )
    fill_before = await redis.xrange(FILL_STREAM)
    final_before = await redis.xrange(FINAL_STREAM)

    daemon = _make_daemon(
        redis=redis,
        setups=[_DirectionSetup("long"), _DirectionSetup("short")],
        provider=_provider_for(),
        mode="enforce",
        gate_redis=gate_redis,
    )
    await _run_until_drained(daemon)

    assert await redis.xrange(CANDIDATE_STREAM) == []  # entries blocked
    assert await redis.xrange(FILL_STREAM) == fill_before  # exits untouched
    assert await redis.xrange(FINAL_STREAM) == final_before
