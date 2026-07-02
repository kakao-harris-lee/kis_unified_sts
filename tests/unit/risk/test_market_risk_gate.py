"""Unit tests for shared.risk.market_risk_gate (unified roadmap Phase 2A).

Hermetic: fakeredis (sync), fixed KST-naive reference clock. Covers the full
§4.2 asset x band x side reaction matrix, mode semantics (off / shadow /
enforce), every fail-open path (missing / parse failure / degraded / stale /
redis error / unknown asset-side-band), the staleness boundary, the fixed
``gate_trace_payload`` key contract, and the YAML <-> code-default mirror.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import fakeredis
import pytest

from shared.risk.market_risk_gate import (
    MarketRiskGateConfig,
    MarketRiskGateDecision,
    evaluate_market_risk_gate,
    gate_trace_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_YAML = REPO_ROOT / "config" / "market_risk_gate.yaml"

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 7, 3, 10, 30)  # KST-naive reference clock
LATEST_KEY = "market:risk:latest"

# Representative published score per band (the gate keys rules on the band
# field; scores only flow into decision.score / reason).
BAND_SCORES = {
    "LOW": "12.0000",
    "NEUTRAL": "40.0000",
    "ELEVATED": "60.0000",
    "HIGH": "74.2000",
    "CRITICAL": "90.0000",
}


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


def publish(redis, band: str = "NEUTRAL", **overrides: str) -> None:
    """Write a ``market:risk:latest`` hash mirroring the Phase 1 §4.3 contract."""
    mapping = {
        "score": BAND_SCORES.get(band, "40.0000"),
        "score_ema3": BAND_SCORES.get(band, "40.0000"),
        "band": band,
        "regime": "NEUTRAL",
        "degraded": "false",
        "coverage_ratio": "1.0000",
        "missing_components": "[]",
        "asof_ts": NOW.isoformat(),
        "kind": "close",
        "components": "{}",
    }
    mapping.update(overrides)
    redis.delete(LATEST_KEY)
    redis.hset(LATEST_KEY, mapping=mapping)


def evaluate(redis, mode: str, asset: str, side: str, **kwargs):
    config = kwargs.pop("config", None) or MarketRiskGateConfig(mode=mode)
    kwargs.setdefault("now", NOW)
    return evaluate_market_risk_gate(redis, config, asset=asset, side=side, **kwargs)


# ---------------------------------------------------------------------------
# §4.2 reaction matrix — exhaustive asset x band x side
# ---------------------------------------------------------------------------

# (asset, band, side) -> (would_block, size_factor, min_confidence)
MATRIX = [
    ("stock", "LOW", "long", False, 1.0, None),
    ("stock", "LOW", "short", False, 1.0, None),
    ("stock", "NEUTRAL", "long", False, 1.0, None),
    ("stock", "NEUTRAL", "short", False, 1.0, None),
    ("stock", "ELEVATED", "long", False, 1.0, "HIGH"),
    ("stock", "ELEVATED", "short", False, 1.0, "HIGH"),
    ("stock", "HIGH", "long", True, 1.0, None),
    ("stock", "HIGH", "short", False, 1.0, None),
    ("stock", "CRITICAL", "long", True, 1.0, None),
    ("stock", "CRITICAL", "short", True, 1.0, None),
    ("futures", "LOW", "long", False, 1.0, None),
    ("futures", "LOW", "short", False, 1.0, None),
    ("futures", "NEUTRAL", "long", False, 1.0, None),
    ("futures", "NEUTRAL", "short", False, 1.0, None),
    ("futures", "ELEVATED", "long", False, 0.7, None),
    ("futures", "ELEVATED", "short", False, 0.7, None),
    ("futures", "HIGH", "long", True, 0.5, None),
    ("futures", "HIGH", "short", False, 0.5, None),
    ("futures", "CRITICAL", "long", True, 1.0, None),
    ("futures", "CRITICAL", "short", True, 1.0, None),
]

_MATRIX_PARAMS = (
    "asset",
    "band",
    "side",
    "would_block",
    "size_factor",
    "min_confidence",
)


@pytest.mark.parametrize(_MATRIX_PARAMS, MATRIX)
def test_reaction_matrix_enforce(
    redis, asset, band, side, would_block, size_factor, min_confidence
):
    publish(redis, band=band)
    decision = evaluate(redis, "enforce", asset, side)
    assert isinstance(decision, MarketRiskGateDecision)
    assert decision.would_block is would_block
    assert decision.allow is (not would_block)
    assert decision.size_factor == pytest.approx(size_factor)
    assert decision.min_confidence == min_confidence
    assert decision.band == band
    assert decision.regime == "NEUTRAL"
    assert decision.mode == "enforce"
    assert decision.degraded is False
    assert decision.stale is False
    assert decision.reason.startswith(f"market_risk band={band} ")


@pytest.mark.parametrize(_MATRIX_PARAMS, MATRIX)
def test_reaction_matrix_shadow_never_blocks(
    redis, asset, band, side, would_block, size_factor, min_confidence
):
    publish(redis, band=band)
    decision = evaluate(redis, "shadow", asset, side)
    assert decision.allow is True  # shadow is observation-only
    assert decision.would_block is would_block
    assert decision.size_factor == pytest.approx(size_factor)
    assert decision.min_confidence == min_confidence
    assert decision.mode == "shadow"


# ---------------------------------------------------------------------------
# Reason strings (machine-readable rule labels)
# ---------------------------------------------------------------------------


def test_block_new_long_reason_format(redis):
    publish(redis, band="HIGH")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert decision.reason == "market_risk band=HIGH score=74.2 rule=block_new_long"


def test_block_all_entries_reason(redis):
    publish(redis, band="CRITICAL")
    for side in ("long", "short"):
        decision = evaluate(redis, "enforce", "futures", side)
        assert decision.reason == (
            "market_risk band=CRITICAL score=90.0 rule=block_all_entries"
        )


def test_min_confidence_reason(redis):
    publish(redis, band="ELEVATED")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert decision.reason == (
        "market_risk band=ELEVATED score=60.0 rule=min_confidence:HIGH"
    )


def test_size_factor_reason(redis):
    publish(redis, band="ELEVATED")
    decision = evaluate(redis, "shadow", "futures", "long")
    assert decision.reason == (
        "market_risk band=ELEVATED score=60.0 rule=size_factor:0.7"
    )


def test_plain_allow_reason(redis):
    publish(redis, band="LOW")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert decision.reason == "market_risk band=LOW score=12.0 rule=allow"


def test_missing_score_reports_na(redis):
    publish(redis, band="HIGH", score="")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert decision.score is None
    assert decision.would_block is True
    assert decision.reason == "market_risk band=HIGH score=na rule=block_new_long"


# ---------------------------------------------------------------------------
# Mode semantics
# ---------------------------------------------------------------------------


def test_mode_off_short_circuits(redis):
    publish(redis, band="CRITICAL")
    decision = evaluate(redis, "off", "stock", "long")
    assert decision.allow is True
    assert decision.would_block is False
    assert decision.size_factor == 1.0
    assert decision.min_confidence is None
    assert decision.reason == "fail_open:mode_off"
    assert decision.mode == "off"
    assert decision.band is None


def test_default_mode_is_shadow():
    assert MarketRiskGateConfig().mode == "shadow"


# ---------------------------------------------------------------------------
# Fail-open paths (enforce mode: fail-open beats enforcement)
# ---------------------------------------------------------------------------


def assert_fail_open(decision, reason_prefix: str) -> None:
    assert decision.allow is True
    assert decision.would_block is False
    assert decision.size_factor == 1.0
    assert decision.min_confidence is None
    assert decision.reason.startswith(reason_prefix)


def test_fail_open_missing_key(redis):
    decision = evaluate(redis, "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:missing")
    assert decision.band is None


def test_fail_open_invalid_asof(redis):
    publish(redis, band="CRITICAL", asof_ts="not-a-timestamp")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:invalid_asof")
    assert decision.band == "CRITICAL"  # observed fields still surfaced


def test_fail_open_empty_band(redis):
    publish(redis, band="")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:invalid_band")


def test_fail_open_unknown_band(redis):
    publish(redis, band="PANIC")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:unknown_band:PANIC")


def test_fail_open_degraded(redis):
    publish(redis, band="CRITICAL", degraded="true")
    decision = evaluate(redis, "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:degraded")
    assert decision.degraded is True
    assert decision.stale is False


def test_fail_open_stale(redis):
    stale_asof = NOW - timedelta(seconds=21601)
    publish(redis, band="CRITICAL", asof_ts=stale_asof.isoformat())
    decision = evaluate(redis, "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:stale")
    assert decision.stale is True
    assert decision.degraded is False
    assert decision.band == "CRITICAL"


def test_stale_boundary_exact_age_is_fresh(redis):
    boundary_asof = NOW - timedelta(seconds=21600)
    publish(redis, band="HIGH", asof_ts=boundary_asof.isoformat())
    decision = evaluate(redis, "enforce", "stock", "long")
    assert decision.stale is False
    assert decision.would_block is True  # normal matrix evaluation
    assert decision.allow is False


def test_fail_open_redis_error():
    class Boom:
        def hgetall(self, key):
            raise ConnectionError("redis down")

    decision = evaluate(Boom(), "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:redis_error:ConnectionError")


def test_fail_open_unknown_asset(redis):
    publish(redis, band="CRITICAL")
    decision = evaluate(redis, "enforce", "crypto", "long")
    assert_fail_open(decision, "fail_open:unknown_asset:crypto")


def test_fail_open_invalid_side(redis):
    publish(redis, band="CRITICAL")
    decision = evaluate(redis, "enforce", "futures", "both")
    assert_fail_open(decision, "fail_open:invalid_side:both")


def test_missing_hgetall_attribute_fails_open():
    decision = evaluate(object(), "enforce", "stock", "long")  # no hgetall
    assert_fail_open(decision, "fail_open:redis_error:AttributeError")


def test_never_raises_on_unparseable_hash_payload():
    class Weird:
        def hgetall(self, key):
            return 5  # not a mapping → TypeError past the redis-read guard

    decision = evaluate(Weird(), "enforce", "stock", "long")
    assert_fail_open(decision, "fail_open:error:TypeError")


# ---------------------------------------------------------------------------
# Input normalization / clock handling
# ---------------------------------------------------------------------------


def test_bytes_redis_responses():
    raw = fakeredis.FakeRedis(decode_responses=False)
    publish(raw, band="HIGH")
    decision = evaluate(raw, "enforce", "futures", "long")
    assert decision.would_block is True
    assert decision.size_factor == pytest.approx(0.5)
    assert decision.band == "HIGH"


def test_asset_and_side_are_normalized(redis):
    publish(redis, band="HIGH")
    decision = evaluate(redis, "enforce", " STOCK ", "Long")
    assert decision.would_block is True
    assert decision.allow is False


def test_aware_now_is_converted_to_kst(redis):
    publish(redis, band="HIGH", asof_ts=NOW.isoformat())
    aware_now = NOW.replace(tzinfo=KST)  # same instant, tz-aware
    decision = evaluate(redis, "enforce", "futures", "long", now=aware_now)
    assert decision.stale is False
    assert decision.would_block is True


def test_default_clock_when_now_omitted(redis):
    fresh_asof = datetime.now(KST).replace(tzinfo=None)
    publish(redis, band="HIGH", asof_ts=fresh_asof.isoformat())
    decision = evaluate_market_risk_gate(
        redis, MarketRiskGateConfig(mode="enforce"), asset="stock", side="long"
    )
    assert decision.stale is False
    assert decision.would_block is True


# ---------------------------------------------------------------------------
# Trace payload (fixed key contract)
# ---------------------------------------------------------------------------


def test_gate_trace_payload_fixed_keys(redis):
    publish(redis, band="ELEVATED", regime="NEUTRAL")
    decision = evaluate(redis, "shadow", "futures", "long")
    payload = gate_trace_payload(decision)
    assert set(payload) == {
        "mode",
        "band",
        "score",
        "regime",
        "would_block",
        "allow",
        "size_factor",
        "min_confidence",
        "reason",
        "degraded",
        "stale",
    }
    assert payload["mode"] == "shadow"
    assert payload["band"] == "ELEVATED"
    assert payload["score"] == pytest.approx(60.0)
    assert payload["regime"] == "NEUTRAL"
    assert payload["would_block"] is False
    assert payload["allow"] is True
    assert payload["size_factor"] == pytest.approx(0.7)
    assert payload["min_confidence"] is None
    assert payload["degraded"] is False
    assert payload["stale"] is False
    json.dumps(payload)  # must stay serializable for trace/signal metadata


def test_gate_trace_payload_fail_open(redis):
    decision = evaluate(redis, "enforce", "stock", "long")  # missing hash
    payload = gate_trace_payload(decision)
    assert payload["reason"] == "fail_open:missing"
    assert payload["allow"] is True
    assert payload["band"] is None


def test_decision_is_frozen(redis):
    publish(redis, band="LOW")
    decision = evaluate(redis, "enforce", "stock", "long")
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allow = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Config fallback: code defaults must mirror the shipped YAML
# ---------------------------------------------------------------------------


def test_yaml_mirrors_code_defaults():
    from_yaml = MarketRiskGateConfig.from_yaml(str(GATE_YAML))
    assert from_yaml.model_dump() == MarketRiskGateConfig().model_dump()


def test_load_or_default_falls_back_when_yaml_absent(tmp_path):
    config = MarketRiskGateConfig.load_or_default(str(tmp_path / "absent.yaml"))
    assert config.mode == "shadow"
    assert config.staleness_max_age_seconds == 21600
    assert config.redis.latest_key == "market:risk:latest"
    assert set(config.assets) == {"stock", "futures"}
    for bands in config.assets.values():
        assert set(bands) == {"LOW", "NEUTRAL", "ELEVATED", "HIGH", "CRITICAL"}


def test_config_rejects_empty_assets():
    with pytest.raises(ValueError):
        MarketRiskGateConfig(assets={})


def test_config_rejects_unknown_mode():
    with pytest.raises(ValueError):
        MarketRiskGateConfig(mode="dry_run")
