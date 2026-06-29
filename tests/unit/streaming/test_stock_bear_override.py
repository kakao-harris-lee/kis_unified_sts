"""Tests for the stock bear-gate override Redis contract.

6 cases covering: defaults, round-trip (fresh payload), stale rejection,
missing/malformed rejection, NaN rejection, and load() defaults-on-failure.
"""

import json

from shared.streaming.stock_bear_override import (
    BearOverrideConfig,
    compute_override_payload,
    parse_strong_set,
)


def test_defaults():
    c = BearOverrideConfig()
    assert c.enabled is False
    assert c.redis_key == "stock:daemon:bear_override"
    assert c.max_age_seconds == 300.0
    assert c.max_override_positions == 3
    assert c.criteria.rsi_min == 55.0


def test_payload_round_trip_fresh():
    cfg = BearOverrideConfig()
    payload = compute_override_payload({"AAA", "BBB"}, now_ms=1_000_000)
    raw = json.dumps(payload)
    out = parse_strong_set(raw, config=cfg, now_ms=1_000_000 + 1000)  # 1s old
    assert out == {"AAA", "BBB"}


def test_stale_payload_returns_empty():
    cfg = BearOverrideConfig()
    payload = compute_override_payload({"AAA"}, now_ms=1_000_000)
    raw = json.dumps(payload)
    out = parse_strong_set(raw, config=cfg, now_ms=1_000_000 + 400_000)  # 400s > 300
    assert out == set()


def test_missing_or_malformed_returns_empty():
    cfg = BearOverrideConfig()
    assert parse_strong_set(None, config=cfg, now_ms=1) == set()
    assert parse_strong_set("not json", config=cfg, now_ms=1) == set()
    assert (
        parse_strong_set(json.dumps({"strong": ["A"]}), config=cfg, now_ms=1) == set()
    )  # no computed_at_ms


def test_nan_age_returns_empty():
    cfg = BearOverrideConfig()
    raw = json.dumps({"strong": ["A"], "computed_at_ms": float("nan")})
    assert parse_strong_set(raw, config=cfg, now_ms=1_000) == set()


def test_load_defaults_on_missing(monkeypatch):
    from shared.config import loader as loader_mod

    monkeypatch.setattr(loader_mod.ConfigLoader, "load", staticmethod(lambda _f: {}))
    assert BearOverrideConfig.load().enabled is False


def test_min_change_pct_for_rs_default():
    """Default is 0.0 (gate disabled)."""
    assert BearOverrideConfig().min_change_pct_for_rs == 0.0


def test_min_change_pct_for_rs_loaded(monkeypatch):
    from shared.config import loader as loader_mod

    monkeypatch.setattr(
        loader_mod.ConfigLoader,
        "load",
        staticmethod(
            lambda _f: {"stock_bear_override": {"min_change_pct_for_rs": 0.3}}
        ),
    )
    cfg = BearOverrideConfig.load()
    assert cfg.min_change_pct_for_rs == 0.3
