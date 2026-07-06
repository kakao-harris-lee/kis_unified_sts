"""Unit tests for services.futures_contract (Phase A contract read-model).

Hermetic: fakeredis (sync, decode_responses). Covers the Redis publication
contract (field names + TTL fallback + stream), night-symbol resolution
priority (override → collector fallback), and the disabled no-op.
"""

from __future__ import annotations

from datetime import date, datetime

import fakeredis

from services.futures_contract.config import (
    ContractNightMasterConfig,
    FuturesContractConfig,
)
from services.futures_contract.main import (
    build_state,
    resolve_night_symbols,
    run_publish,
)

_NOW = datetime(2026, 7, 1, 8, 15)
_DAY = date(2026, 7, 1)


def _config(**overrides) -> FuturesContractConfig:
    base: dict = {"product": "mini"}
    base.update(overrides)
    return FuturesContractConfig(**base)


def test_run_publish_writes_latest_hash_and_stream():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    config = _config(
        night_master=ContractNightMasterConfig(
            enabled=True, night_front_symbol="1A01609"
        )
    )

    rc = run_publish(
        config=config, redis=redis, mode="premarket", trade_date=_DAY, now=_NOW
    )
    assert rc == 0

    latest = redis.hgetall(config.redis.latest_key)
    assert latest["product"] == "mini"
    assert latest["front_symbol"] == "A05607"
    assert latest["next_symbol"] == "A05608"
    assert latest["night_front_symbol"] == "1A01609"
    assert latest["roll_state"] == "normal"
    assert latest["source"] == "manual_override"

    # premarket uses the 48h TTL fallback.
    ttl = redis.ttl(config.redis.latest_key)
    assert 0 < ttl <= config.redis.latest_ttl_fallback_seconds
    assert ttl > config.redis.latest_ttl_seconds

    entries = redis.xrange(config.redis.stream_key)
    assert len(entries) == 1
    _, event = entries[0]
    assert event["roll_state"] == "normal"
    assert event["front_symbol"] == "A05607"


def test_intraday_uses_short_ttl():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    config = _config(
        night_master=ContractNightMasterConfig(
            enabled=True, night_front_symbol="1A01609"
        )
    )
    run_publish(config=config, redis=redis, mode="intraday", trade_date=_DAY, now=_NOW)
    ttl = redis.ttl(config.redis.latest_key)
    assert 0 < ttl <= config.redis.latest_ttl_seconds


def test_publish_replaces_stale_fields():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    config = _config(
        night_master=ContractNightMasterConfig(
            enabled=True, night_front_symbol="1A01609"
        )
    )
    redis.hset(config.redis.latest_key, mapping={"stale_field": "leftover"})
    run_publish(config=config, redis=redis, mode="intraday", trade_date=_DAY, now=_NOW)
    latest = redis.hgetall(config.redis.latest_key)
    assert "stale_field" not in latest


def test_disabled_config_is_noop():
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    config = _config(enabled=False)
    rc = run_publish(
        config=config, redis=redis, mode="intraday", trade_date=_DAY, now=_NOW
    )
    assert rc == 0
    assert redis.hgetall(config.redis.latest_key) == {}


def test_resolve_night_symbols_prefers_override():
    config = _config(
        night_master=ContractNightMasterConfig(
            enabled=True,
            night_front_symbol="1A01699",
            night_next_symbol="1A01712",
        )
    )
    front, nxt = resolve_night_symbols(config)
    assert front == "1A01699"
    assert nxt == "1A01712"


def test_build_state_missing_night_when_required_is_unknown(monkeypatch):
    # No override, and force the collector fallback to fail → unknown.
    config = _config(night_master=ContractNightMasterConfig(enabled=True))
    monkeypatch.setattr(
        "services.futures_contract.main.resolve_night_symbols",
        lambda _cfg: (None, None),
    )
    state = build_state(config, target_date=_DAY, asof_ts=_NOW)
    assert state.roll_state == "unknown"
    assert state.new_entry_front_allowed is False
