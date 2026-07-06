"""Unit tests for services.futures_context (Phase C publisher).

Hermetic: fakeredis (sync, decode_responses). Covers the Redis publication
contract (fields + TTL + stream), composition from live upstream hashes,
per-input degrade, and the disabled no-op.
"""

from __future__ import annotations

from datetime import datetime

import fakeredis

from services.futures_context.config import FuturesContextConfig
from services.futures_context.main import build_state, run_publish

_NOW = datetime(2026, 7, 1, 10, 0)


def _config(**overrides) -> FuturesContextConfig:
    base: dict = {"product": "mini"}
    base.update(overrides)
    return FuturesContextConfig(**base)


def _seed_upstreams(redis, config):
    redis.hset(
        config.inputs.contract_latest_key,
        mapping={
            "front_symbol": "A05607",
            "days_to_expiry": "8",
            "roll_state": "normal",
            "new_entry_front_allowed": "true",
        },
    )
    redis.hset(
        config.inputs.structure_latest_key,
        mapping={
            "basis_dev": "0.50",
            "fut_oi_qty": "250000",
            "fut_foreign_net_qty": "3000",
        },
    )
    redis.hset(
        config.inputs.risk_latest_key,
        mapping={"score": "62.5", "band": "ELEVATED", "regime": "risk_off"},
    )
    redis.hset(
        config.inputs.margin_latest_key,
        mapping={
            "margin_usage_pct": "0.32",
            "liquidation_buffer_ticks": "480.0",
            "risk_level": "ok",
        },
    )


def test_run_publish_composes_and_writes_latest_and_stream():
    config = _config()
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    _seed_upstreams(redis, config)

    ctx = run_publish(config=config, redis=redis, mode="intraday", now=_NOW)
    assert ctx is not None

    latest = redis.hgetall(config.redis.latest_key)
    assert latest["front_symbol"] == "A05607"
    assert latest["roll_state"] == "normal"
    assert latest["basis_regime"] == "contango"
    assert latest["foreign_flow_regime"] == "buy"
    assert latest["market_risk_band"] == "ELEVATED"
    assert latest["margin_risk_level"] == "ok"
    assert float(latest["market_risk_score"]) == 62.5

    ttl = redis.ttl(config.redis.latest_key)
    assert 0 < ttl <= config.redis.latest_ttl_seconds

    entries = redis.xrange(config.redis.stream_key)
    assert len(entries) == 1
    _, event = entries[0]
    assert event["basis_regime"] == "contango"
    assert event["market_risk_band"] == "ELEVATED"


def test_missing_upstream_still_publishes_with_components():
    config = _config()
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    # Only seed risk; contract/structure/margin absent.
    redis.hset(
        config.inputs.risk_latest_key, mapping={"score": "40", "band": "NEUTRAL"}
    )

    ctx = run_publish(config=config, redis=redis, mode="intraday", now=_NOW)
    assert ctx is not None
    latest = redis.hgetall(config.redis.latest_key)
    assert latest["degraded"] == "true"
    missing = latest["missing_components"]
    assert "contract" in missing
    assert "structure" in missing
    assert "margin" in missing
    assert latest["market_risk_band"] == "NEUTRAL"


def test_build_state_reads_all_four_hashes():
    config = _config()
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    _seed_upstreams(redis, config)
    ctx = build_state(config, redis, asof_ts=_NOW)
    assert ctx.days_to_expiry == 8
    assert ctx.fut_oi_qty == 250000
    assert ctx.margin_usage_pct == 0.32


def test_publish_replaces_stale_fields():
    config = _config()
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    _seed_upstreams(redis, config)
    redis.hset(config.redis.latest_key, mapping={"stale_field": "leftover"})
    run_publish(config=config, redis=redis, mode="intraday", now=_NOW)
    latest = redis.hgetall(config.redis.latest_key)
    assert "stale_field" not in latest


def test_disabled_config_is_noop():
    config = _config(enabled=False)
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    _seed_upstreams(redis, config)
    ctx = run_publish(config=config, redis=redis, mode="intraday", now=_NOW)
    assert ctx is None
    assert redis.hgetall(config.redis.latest_key) == {}
