"""StockStrategyDaemon x market-risk ENTRY gate (unified roadmap Phase 2C).

Hermetic: fakeredis (sync) backs the shared gate's Redis read; the daemon's
own async Redis is faked in-memory (test_daemon.py conventions). Covers the
fixed Phase 2C contract for M4-P:

* ALL modes attach ``gate_trace_payload`` under ``metadata["market_risk_gate"]``
  (fixed key, /signals trace-lane contract).
* shadow: signals pass; would-block is a throttled log + trace annotation only.
* enforce: HIGH blocks new longs / CRITICAL blocks all (blanket, #483
  reject-reason lane records ``decision.reason``); ELEVATED rejects signals
  whose confidence is below the mapped min-confidence threshold.
* fail-open (missing hash) and unwired construction leave entries untouched.
* the regime publish for M4-X's bear exit is never skipped by a gate block —
  exits stay signal-driven (the gate is entry-only).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import fakeredis
import pytest

from services.stock_strategy.daemon import LLMDiscoverySignalConfig, StockStrategyDaemon
from services.stock_strategy.market_risk import MarketRiskGateWiringConfig
from services.stock_strategy.universe import _SCREENER_PAYLOAD_KEY
from shared.models.signal import Signal
from shared.risk.market_risk_gate import MarketRiskGateConfig
from shared.streaming.stock_regime import StockRegimeConfig
from shared.streaming.stock_signal_eval import (
    REJECT_BEAR_REGIME,
    StockSignalEvalConfig,
)

_NOW = datetime(2026, 6, 5, 0, 30, tzinfo=UTC)  # 09:30 KST — mid-session
_ASOF = datetime(2026, 6, 5, 9, 30)  # KST-naive publication timestamp (fresh)
_LATEST_KEY = "market:risk:latest"

# Representative published score per band (mirrors the shared gate tests).
_BAND_SCORES = {
    "LOW": "12.0000",
    "NEUTRAL": "40.0000",
    "ELEVATED": "60.0000",
    "HIGH": "74.2000",
    "CRITICAL": "90.0000",
}

_EVAL_CFG = StockSignalEvalConfig()


# ---------------------------------------------------------------------------
# Fakes (test_daemon.py conventions)
# ---------------------------------------------------------------------------


class _FakeEngine:
    def __init__(self, warm=("005930",), mfi_values=None):
        self._warm = set(warm)
        self._mfi_values = mfi_values

    def is_warm(self, symbol):
        return symbol in self._warm

    def get_market_mfi_values(self, _active_symbols=None):
        return dict(self._mfi_values or {})

    def get_daily_indicators(self, _symbol):
        return {}


class _FakeResolver:
    def collect_entry_indicators(self, _symbol):
        return {"rsi": 30.0, "atr": 100.0}


class _FakeFeed:
    def update_symbols(self, codes):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    async def get_current_price(self, _symbol):
        return {"code": _symbol, "close": 71000.0, "timestamp": 1.0}


class _StratStub:
    def __init__(self, name):
        self.name = name
        self.required_indicators: list[str] = []


class _Manager:
    """Roster manager firing ``williams_r`` for ``fire_for`` at ``confidence``."""

    def __init__(self, fire_for=("005930",), confidence=0.6):
        self._fire = set(fire_for)
        self._confidence = confidence
        self.strategies = {"williams_r": _StratStub("williams_r")}

    async def check_entries(self, context):
        code = context.market_data.get("code")
        if code in self._fire:
            return [
                Signal(
                    code=code,
                    strategy="williams_r",
                    price=71000.0,
                    confidence=self._confidence,
                )
            ]
        return []


class _FakeRedis:
    """Async in-memory fake for the daemon's own client (streams + kv + hashes)."""

    def __init__(self):
        self.added = []
        self.kv = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.next_id = b"1719876543210-0"

    async def xadd(self, stream, fields, **_kw):
        self.added.append((stream, fields))
        return self.next_id

    async def expire(self, *_a, **_k):
        return True

    async def set(self, key, value, **_kw):
        self.kv[key] = value
        return True

    async def get(self, k):
        return self.kv.get(k)

    async def hkeys(self, _k):
        return []

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(str(field))

    async def hset(self, key, field=None, value=None, mapping=None, **_kw):
        bucket = self.hashes.setdefault(key, {})
        if mapping:
            bucket.update({str(k): str(v) for k, v in mapping.items()})
        elif field is not None:
            bucket[str(field)] = str(value) if value is not None else ""
        return 1


def _gate_redis(band=None, **overrides):
    """Sync fakeredis holding the Phase 1 ``market:risk:latest`` hash."""
    client = fakeredis.FakeRedis(decode_responses=True)
    if band is not None:
        mapping = {
            "score": _BAND_SCORES.get(band, "40.0000"),
            "band": band,
            "regime": "NEUTRAL",
            "degraded": "false",
            "asof_ts": _ASOF.isoformat(),
        }
        mapping.update(overrides)
        client.hset(_LATEST_KEY, mapping=mapping)
    return client


def _daemon(**kw):
    defaults = {
        "redis": _FakeRedis(),
        "feed": _FakeFeed(),
        "engine": _FakeEngine(),
        "resolver": _FakeResolver(),
        "manager": _Manager(),
        "candidate_stream": "signal.candidate.stock.shadow",
        "candidate_maxlen": 10_000,
        "now_fn": lambda: _NOW,
        "signal_eval_config": _EVAL_CFG,
    }
    defaults.update(kw)
    daemon = StockStrategyDaemon(**defaults)
    daemon._universe = ["005930"]
    return daemon


def _gated_daemon(mode, band, **kw):
    kw.setdefault("market_risk_gate_config", MarketRiskGateConfig(mode=mode))
    kw.setdefault("market_risk_gate_redis", _gate_redis(band))
    return _daemon(**kw)


def _published_metadata(redis, index=0):
    _stream, fields = redis.added[index]
    return json.loads(fields["metadata_json"])


def _eval_summary(redis):
    raw = redis.hashes.get(_EVAL_CFG.redis_key, {})
    return {k: json.loads(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Trace contract — metadata["market_risk_gate"] in ALL modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_high_band_publishes_with_would_block_trace():
    redis = _FakeRedis()
    d = _gated_daemon("shadow", "HIGH", redis=redis)

    published = await d.evaluate_once()

    assert published == 1  # shadow is observation-only: signal still passes
    trace = _published_metadata(redis)["market_risk_gate"]
    assert trace["mode"] == "shadow"
    assert trace["band"] == "HIGH"
    assert trace["would_block"] is True
    assert trace["allow"] is True
    assert trace["reason"] == "market_risk band=HIGH score=74.2 rule=block_new_long"


@pytest.mark.asyncio
async def test_mode_off_trace_still_attached():
    """ALL modes attach the trace — off mode carries the fail_open reason."""
    redis = _FakeRedis()
    d = _gated_daemon("off", "CRITICAL", redis=redis)

    published = await d.evaluate_once()

    assert published == 1
    trace = _published_metadata(redis)["market_risk_gate"]
    assert trace["mode"] == "off"
    assert trace["allow"] is True
    assert trace["reason"] == "fail_open:mode_off"


@pytest.mark.asyncio
async def test_unwired_gate_leaves_metadata_untouched():
    """No gate config (legacy construction) → pre-gate behavior bit-for-bit."""
    redis = _FakeRedis()
    d = _daemon(redis=redis)  # no market_risk_gate_config / redis

    published = await d.evaluate_once()

    assert published == 1
    assert "market_risk_gate" not in _published_metadata(redis)


# ---------------------------------------------------------------------------
# Shadow mode — never rejects; throttled would-block log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_would_block_logged_once_per_interval(caplog):
    d = _gated_daemon("shadow", "HIGH")

    with caplog.at_level(logging.INFO, logger="services.stock_strategy.daemon"):
        await d.evaluate_once()
        await d.evaluate_once()  # same frozen clock → within throttle interval

    shadow_logs = [
        r for r in caplog.records if "market risk gate (shadow)" in r.getMessage()
    ]
    assert len(shadow_logs) == 1  # throttled: one log, not one per cycle
    assert "block_new_long" in shadow_logs[0].getMessage()


@pytest.mark.asyncio
async def test_shadow_elevated_low_confidence_still_publishes():
    """Shadow reports min_confidence in the trace but must never reject."""
    redis = _FakeRedis()
    d = _gated_daemon(
        "shadow", "ELEVATED", redis=redis, manager=_Manager(confidence=0.6)
    )

    published = await d.evaluate_once()

    assert published == 1
    trace = _published_metadata(redis)["market_risk_gate"]
    assert trace["min_confidence"] == "HIGH"
    assert trace["would_block"] is False


# ---------------------------------------------------------------------------
# Enforce mode — blanket band blocks (#483 reject-reason lane)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enforce_high_band_blocks_new_long_entries():
    redis = _FakeRedis()
    d = _gated_daemon("enforce", "HIGH", redis=redis)

    published = await d.evaluate_once()

    assert published == 0
    assert redis.added == []  # nothing reaches the candidate stream
    summary = _eval_summary(redis)
    assert summary["williams_r"]["outcome"] == "reject"
    assert summary["williams_r"]["reason"] == (
        "market_risk band=HIGH score=74.2 rule=block_new_long"
    )


@pytest.mark.asyncio
async def test_enforce_critical_band_blocks_all_entries():
    redis = _FakeRedis()
    d = _gated_daemon("enforce", "CRITICAL", redis=redis)

    published = await d.evaluate_once()

    assert published == 0
    summary = _eval_summary(redis)
    assert summary["williams_r"]["reason"] == (
        "market_risk band=CRITICAL score=90.0 rule=block_all_entries"
    )


@pytest.mark.asyncio
async def test_enforce_block_still_publishes_regime_for_m4x():
    """A gate block must never skip the regime publish M4-X's bear exit reads —
    exits stay signal-driven (the gate is entry-only by contract)."""
    redis = _FakeRedis()
    regime_cfg = StockRegimeConfig(min_mfi_symbols=2)
    d = _gated_daemon(
        "enforce",
        "HIGH",
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 55.0, "000660": 60.0}),
        regime_config=regime_cfg,
    )

    published = await d.evaluate_once()

    assert published == 0  # entries blocked ...
    payload = json.loads(redis.kv[regime_cfg.redis_key])
    assert payload["regime"] == "BULL_STRONG"  # ... but the M4-X feed persists


# ---------------------------------------------------------------------------
# Enforce mode — ELEVATED min-confidence admission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enforce_elevated_rejects_below_min_confidence():
    redis = _FakeRedis()
    d = _gated_daemon(
        "enforce", "ELEVATED", redis=redis, manager=_Manager(confidence=0.6)
    )

    published = await d.evaluate_once()

    assert published == 0  # 0.6 < HIGH threshold (0.7)
    assert redis.added == []
    summary = _eval_summary(redis)
    assert summary["williams_r"]["reason"] == (
        "market_risk band=ELEVATED score=60.0 rule=min_confidence:HIGH"
    )


@pytest.mark.asyncio
async def test_enforce_elevated_admits_high_confidence():
    redis = _FakeRedis()
    d = _gated_daemon(
        "enforce", "ELEVATED", redis=redis, manager=_Manager(confidence=0.9)
    )

    published = await d.evaluate_once()

    assert published == 1  # 0.9 >= HIGH threshold (0.7)
    trace = _published_metadata(redis)["market_risk_gate"]
    assert trace["mode"] == "enforce"
    assert trace["min_confidence"] == "HIGH"
    assert trace["allow"] is True


@pytest.mark.asyncio
async def test_enforce_low_band_publishes_normally():
    redis = _FakeRedis()
    d = _gated_daemon("enforce", "LOW", redis=redis)

    published = await d.evaluate_once()

    assert published == 1
    trace = _published_metadata(redis)["market_risk_gate"]
    assert trace["reason"] == "market_risk band=LOW score=12.0 rule=allow"


# ---------------------------------------------------------------------------
# Fail-open — the gate can never break the entry path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enforce_fail_open_on_missing_hash_publishes():
    redis = _FakeRedis()
    d = _gated_daemon(
        "enforce",
        None,  # no market:risk:latest hash at all
        redis=redis,
        market_risk_gate_redis=_gate_redis(band=None),
    )

    published = await d.evaluate_once()

    assert published == 1
    trace = _published_metadata(redis)["market_risk_gate"]
    assert trace["allow"] is True
    assert trace["reason"] == "fail_open:missing"


# ---------------------------------------------------------------------------
# Coexistence with the bear regime gate (regression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bear_gate_precedence_unchanged_with_gate_wired():
    """A bear blanket block keeps its own reject reason — the market-risk gate
    is additive and must not disturb the existing bear-gate decision."""
    redis = _FakeRedis()
    d = _gated_daemon(
        "shadow",
        "NEUTRAL",
        redis=redis,
        engine=_FakeEngine(mfi_values={"005930": 28.0, "000660": 30.0}),
        regime_config=StockRegimeConfig(min_mfi_symbols=2),
    )

    published = await d.evaluate_once()

    assert published == 0
    summary = _eval_summary(redis)
    assert summary["williams_r"]["reason"] == REJECT_BEAR_REGIME


# ---------------------------------------------------------------------------
# LLM-discovery candidates are NEW entries too
# ---------------------------------------------------------------------------


def _llm_watchlist_payload(llm_confidence=1.0):
    return {
        "strategies": {"_screener_trade_targets": ["080220"]},
        _SCREENER_PAYLOAD_KEY: {
            "codes": ["080220"],
            "names": {"080220": "TestCo"},
            "metadata": {
                "080220": {
                    "llm_quality": 0.9,
                    "llm_confidence": llm_confidence,
                    "entry_price": 10000.0,
                }
            },
        },
    }


def _llm_daemon(mode, band, *, llm_confidence, redis):
    return _gated_daemon(
        mode,
        band,
        redis=redis,
        engine=_FakeEngine(warm=()),
        manager=_Manager(fire_for=()),
        llm_signal_config=LLMDiscoverySignalConfig(
            enabled=True, min_llm_confidence=0.0, skip_log_interval_seconds=0.0
        ),
    )


@pytest.mark.asyncio
async def test_llm_discovery_signal_carries_gate_trace():
    redis = _FakeRedis()
    d = _llm_daemon("shadow", "HIGH", llm_confidence=1.0, redis=redis)
    await d._apply_watchlist(_llm_watchlist_payload())

    published = await d.evaluate_once()

    assert published == 1
    metadata = _published_metadata(redis)
    assert metadata["source"] == "trade_targets_llm"
    assert metadata["market_risk_gate"]["band"] == "HIGH"
    assert metadata["market_risk_gate"]["would_block"] is True


@pytest.mark.asyncio
async def test_enforce_elevated_rejects_llm_signal_below_min_confidence():
    redis = _FakeRedis()
    d = _llm_daemon("enforce", "ELEVATED", llm_confidence=0.6, redis=redis)
    await d._apply_watchlist(_llm_watchlist_payload(llm_confidence=0.6))

    published = await d.evaluate_once()

    assert published == 0
    assert redis.added == []
    summary = _eval_summary(redis)
    assert summary["llm_discovered"]["reason"] == (
        "market_risk band=ELEVATED score=60.0 rule=min_confidence:HIGH"
    )


@pytest.mark.asyncio
async def test_enforce_high_blocks_llm_discovery_too():
    redis = _FakeRedis()
    d = _llm_daemon("enforce", "HIGH", llm_confidence=1.0, redis=redis)
    await d._apply_watchlist(_llm_watchlist_payload())

    published = await d.evaluate_once()

    assert published == 0  # blanket block early-returns before LLM publishing
    assert redis.added == []


# ---------------------------------------------------------------------------
# Wiring config (consumer-side min-confidence mapping)
# ---------------------------------------------------------------------------


def test_wiring_defaults_map_labels():
    wiring = MarketRiskGateWiringConfig()
    assert wiring.min_confidence_threshold("HIGH") == pytest.approx(0.7)
    assert wiring.min_confidence_threshold("MEDIUM") == pytest.approx(0.5)
    assert wiring.min_confidence_threshold("LOW") == pytest.approx(0.3)


def test_wiring_label_is_normalized():
    wiring = MarketRiskGateWiringConfig()
    assert wiring.min_confidence_threshold(" high ") == pytest.approx(0.7)


def test_wiring_unknown_and_empty_labels_fail_open():
    wiring = MarketRiskGateWiringConfig()
    assert wiring.min_confidence_threshold("ULTRA") is None
    assert wiring.min_confidence_threshold(None) is None
    assert wiring.min_confidence_threshold("") is None


def test_wiring_load_mirrors_shipped_yaml():
    """config/stock_market_risk_gate.yaml must mirror the code defaults."""
    assert MarketRiskGateWiringConfig.load() == MarketRiskGateWiringConfig()


@pytest.mark.asyncio
async def test_unknown_min_confidence_label_admits_signal():
    """An unmapped matrix label must fail open (admit), never reject."""
    redis = _FakeRedis()
    d = _gated_daemon(
        "enforce",
        "ELEVATED",
        redis=redis,
        manager=_Manager(confidence=0.1),
        market_risk_wiring=MarketRiskGateWiringConfig(confidence_levels={}),
    )

    published = await d.evaluate_once()

    assert published == 1  # label "HIGH" unmapped → fail-open admission
