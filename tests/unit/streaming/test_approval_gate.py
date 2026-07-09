"""Tests for shared/streaming/approval_gate.py — gate matching + pending record."""

from __future__ import annotations

import json

import fakeredis.aioredis
import pytest

from shared.streaming.approval_gate import (
    ApprovalGateConfig,
    is_gated,
    log_gate_config,
    record_pending,
)
from shared.streaming.approval_keys import (
    APPROVAL_EVENTS_CHANNEL,
    approval_field_id,
    pending_approval_key,
)


def _config(**overrides) -> ApprovalGateConfig:
    defaults = {
        "enabled": True,
        "gated_strategies": [],
        "gated_symbols": [],
        "pending_ttl_seconds": 86400,
    }
    defaults.update(overrides)
    return ApprovalGateConfig(**defaults)


class TestIsGated:
    def test_disabled_gate_never_gates(self):
        config = _config(enabled=False, gated_strategies=["setup_a_gap_reversion"])
        assert is_gated("setup_a_gap_reversion", "005930", config) is False

    def test_empty_lists_gate_nothing_even_when_enabled(self):
        config = _config(enabled=True)
        assert is_gated("bb_reversion", "005930", config) is False

    def test_matches_on_gated_strategy(self):
        config = _config(gated_strategies=["setup_a_gap_reversion"])
        assert is_gated("setup_a_gap_reversion", "A05603", config) is True

    def test_matches_on_gated_symbol(self):
        config = _config(gated_symbols=["005930"])
        assert is_gated("bb_reversion", "005930", config) is True

    def test_non_matching_strategy_and_symbol_not_gated(self):
        config = _config(
            gated_strategies=["setup_a_gap_reversion"], gated_symbols=["005930"]
        )
        assert is_gated("bb_reversion", "000660", config) is False

    def test_strategy_list_does_not_match_on_symbol(self):
        config = _config(gated_strategies=["005930"])
        # "005930" only matches on the strategy field, not the symbol field.
        assert is_gated("bb_reversion", "005930", config) is False

    def test_matches_strategy_case_insensitively(self):
        config = _config(gated_strategies=["A_gap_reversion"])
        assert is_gated("a_gap_reversion", "A05603", config) is True

    def test_matches_symbol_case_insensitively(self):
        config = _config(gated_symbols=["A05603"])
        assert is_gated("bb_reversion", "a05603", config) is True

    def test_matches_strategy_ignoring_surrounding_whitespace(self):
        config = _config(gated_strategies=[" A_gap_reversion "])
        assert is_gated("A_gap_reversion", "A05603", config) is True


class TestApprovalGateConfigDefaults:
    def test_defaults_are_fully_inert(self):
        config = ApprovalGateConfig()
        assert config.enabled is False
        assert config.gated_strategies == []
        assert config.gated_symbols == []
        assert config.pending_ttl_seconds == 86400


class TestLogGateConfig:
    """Startup safeguard: an operator should see exactly what's gated in logs."""

    def test_logs_when_enabled_with_gated_strategies(self, caplog):
        config = _config(gated_strategies=["A_gap_reversion"])
        with caplog.at_level("INFO"):
            log_gate_config(config, asset="futures")
        assert any("A_gap_reversion" in record.message for record in caplog.records)
        assert any("futures" in record.message for record in caplog.records)

    def test_logs_when_enabled_with_gated_symbols(self, caplog):
        config = _config(gated_symbols=["005930"])
        with caplog.at_level("INFO"):
            log_gate_config(config, asset="stock")
        assert any("005930" in record.message for record in caplog.records)

    def test_no_log_when_disabled(self, caplog):
        config = _config(enabled=False, gated_strategies=["A_gap_reversion"])
        with caplog.at_level("INFO"):
            log_gate_config(config, asset="futures")
        assert caplog.records == []

    def test_no_log_when_lists_empty(self, caplog):
        config = _config(enabled=True)
        with caplog.at_level("INFO"):
            log_gate_config(config, asset="futures")
        assert caplog.records == []


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.mark.asyncio
async def test_record_pending_stores_fields_and_returns_approval_id(redis):
    fields = {
        "setup_type": "setup_a_gap_reversion",
        "symbol": "A05603",
        "entry_price": "331.2",
    }
    approval_id = await record_pending(redis, "futures", "sig-1", fields, ttl=86400)

    assert approval_id == approval_field_id("futures", "sig-1")
    key = pending_approval_key("futures")
    stored_raw = await redis.hget(key, approval_id)
    assert json.loads(stored_raw) == fields


@pytest.mark.asyncio
async def test_record_pending_sets_ttl_on_hash(redis):
    key = pending_approval_key("stock")
    await record_pending(redis, "stock", "sig-2", {"code": "005930"}, ttl=86400)

    ttl = await redis.ttl(key)
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_record_pending_publishes_approval_event(redis):
    pubsub = redis.pubsub()
    await pubsub.subscribe(APPROVAL_EVENTS_CHANNEL)
    # Drain the subscribe-confirmation message before publishing.
    await pubsub.get_message(timeout=1)

    approval_id = await record_pending(
        redis, "stock", "sig-3", {"code": "005930"}, ttl=86400
    )

    message = await pubsub.get_message(timeout=1)
    payload = json.loads(message["data"])
    assert payload["asset_class"] == "stock"
    assert payload["approval_id"] == approval_id
    assert payload["signal_id"] == "sig-3"


@pytest.mark.asyncio
async def test_record_pending_replay_compatible_field_dict(redis):
    """Stored value is the exact fields dict, replayable verbatim on approval."""
    fields_out = {
        "setup_type": "A_gap_reversion",
        "direction": "long",
        "symbol": "A05603",
        "entry_price": "331.2",
        "stop_loss": "330.5",
        "take_profit": "332.5",
        "confidence": "0.85",
        "signal_id": "sig-4",
        "size_multiplier": "1.0",
        "filtered_at_ms": "1781136000000",
    }
    approval_id = await record_pending(redis, "futures", "sig-4", fields_out, ttl=86400)

    stored_raw = await redis.hget(pending_approval_key("futures"), approval_id)
    assert json.loads(stored_raw) == fields_out
