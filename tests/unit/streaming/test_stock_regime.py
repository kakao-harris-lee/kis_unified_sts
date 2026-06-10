"""Stock regime contract (M4-P → M4-X): payload compute + staleness-gated parse."""

from __future__ import annotations

import json

import pytest

from shared.streaming.stock_regime import (
    BEAR_REGIMES,
    StockRegimeConfig,
    compute_regime_payload,
    is_bear_regime,
    parse_market_state,
)

_NOW_MS = 1_781_136_000_000
_CFG = StockRegimeConfig(min_mfi_symbols=3, max_age_seconds=300.0)


# ---------------------------------------------------------------------------
# is_bear_regime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("regime", BEAR_REGIMES)
def test_is_bear_regime_true_for_bear_values(regime: str) -> None:
    assert is_bear_regime(regime)


@pytest.mark.parametrize("regime", ["BULL_STRONG", "SIDEWAYS_DOWN", "UNKNOWN", None])
def test_is_bear_regime_false_otherwise(regime: str | None) -> None:
    assert not is_bear_regime(regime)


# ---------------------------------------------------------------------------
# compute_regime_payload
# ---------------------------------------------------------------------------


def test_compute_bear_payload_with_sufficient_coverage() -> None:
    # median MFI 30 < 34 -> BEAR_STRONG (MarketClassifier threshold)
    payload = compute_regime_payload(
        {"A": 28.0, "B": 30.0, "C": 33.0}, config=_CFG, now_ms=_NOW_MS
    )
    assert payload["regime"] == "BEAR_STRONG"
    assert payload["raw_regime"] == "BEAR_STRONG"
    assert payload["mfi"] == 30.0
    assert payload["mfi_symbols"] == 3
    assert payload["low_confidence"] is False
    assert payload["computed_at_ms"] == _NOW_MS


def test_compute_low_confidence_publishes_fallback_not_bear() -> None:
    # 2 symbols < min_mfi_symbols=3 -> UNKNOWN published, raw preserved
    payload = compute_regime_payload(
        {"A": 28.0, "B": 30.0}, config=_CFG, now_ms=_NOW_MS
    )
    assert payload["regime"] == "UNKNOWN"
    assert payload["raw_regime"] == "BEAR_STRONG"
    assert payload["low_confidence"] is True
    assert not is_bear_regime(payload["regime"])


def test_compute_empty_mfi_is_unknown() -> None:
    payload = compute_regime_payload({}, config=_CFG, now_ms=_NOW_MS)
    assert payload["regime"] == "UNKNOWN"
    assert payload["raw_regime"] == "UNKNOWN"
    assert payload["mfi"] is None
    assert payload["low_confidence"] is True


def test_compute_bull_payload() -> None:
    payload = compute_regime_payload(
        {"A": 55.0, "B": 60.0, "C": 52.0}, config=_CFG, now_ms=_NOW_MS
    )
    assert payload["regime"] == "BULL_STRONG"
    assert payload["low_confidence"] is False


# ---------------------------------------------------------------------------
# parse_market_state
# ---------------------------------------------------------------------------


def _fresh_payload(regime: str = "BEAR_STRONG", age_seconds: float = 0.0) -> str:
    return json.dumps(
        {"regime": regime, "computed_at_ms": _NOW_MS - int(age_seconds * 1000)}
    )


def test_parse_fresh_payload_yields_market_state() -> None:
    state = parse_market_state(
        _fresh_payload(age_seconds=10), config=_CFG, now_ms=_NOW_MS
    )
    assert state is not None
    assert state.regime == "BEAR_STRONG"


def test_parse_accepts_bytes() -> None:
    raw = _fresh_payload("BULL_STRONG").encode()
    state = parse_market_state(raw, config=_CFG, now_ms=_NOW_MS)
    assert state is not None
    assert state.regime == "BULL_STRONG"


def test_parse_stale_payload_is_none() -> None:
    raw = _fresh_payload(age_seconds=_CFG.max_age_seconds + 1)
    assert parse_market_state(raw, config=_CFG, now_ms=_NOW_MS) is None


def test_parse_future_timestamp_is_none() -> None:
    # negative age (clock skew / corrupt data) must not enable bear logic
    raw = _fresh_payload(age_seconds=-60)
    assert parse_market_state(raw, config=_CFG, now_ms=_NOW_MS) is None


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not json",
        json.dumps([1, 2]),
        json.dumps({"regime": "BEAR_STRONG"}),  # missing computed_at_ms
        json.dumps({"computed_at_ms": _NOW_MS}),  # missing regime
        json.dumps({"regime": 1, "computed_at_ms": _NOW_MS}),  # wrong type
    ],
)
def test_parse_malformed_is_none(raw: object) -> None:
    assert parse_market_state(raw, config=_CFG, now_ms=_NOW_MS) is None


# ---------------------------------------------------------------------------
# Config contract
# ---------------------------------------------------------------------------


def test_config_yaml_loads_and_is_coherent() -> None:
    """config/stock_regime.yaml parses and its fallback regime is never bear."""
    cfg = StockRegimeConfig.load()
    assert cfg.redis_key
    assert cfg.publish_ttl_seconds > 0
    assert cfg.max_age_seconds > 0
    # low-confidence classification must never trigger liquidation
    assert not is_bear_regime(cfg.low_confidence_regime)
