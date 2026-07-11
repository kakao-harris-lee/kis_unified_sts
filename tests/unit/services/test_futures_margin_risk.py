"""Unit tests for services.futures_margin_risk (Phase B publisher).

Hermetic: fakeredis (sync, decode_responses), injected providers. Covers the
Redis publication contract (fields + TTL + stream), execution-spec merge,
config-fallback account path (degraded), and the disabled no-op.
"""

from __future__ import annotations

from datetime import datetime

import fakeredis

from services.futures_margin_risk.config import (
    FuturesMarginConfig,
    MarginProductDefault,
)
from services.futures_margin_risk.main import (
    MarginRunContext,
    build_product_specs,
    run_margin_risk,
)
from shared.risk.futures_margin import spec_for_symbol
from shared.risk.product_specs import load_execution_contract_specs

_NOW = datetime(2026, 7, 1, 10, 0)

_EXECUTION_SPECS = {
    "kospi200_mini": {"multiplier_krw_per_point": 50000, "tick_size_points": 0.02},
    "kospi200_full": {"multiplier_krw_per_point": 250000, "tick_size_points": 0.05},
}


def _config(**overrides) -> FuturesMarginConfig:
    base: dict = {
        "product": "mini",
        "product_defaults": {
            "kospi200_mini": MarginProductDefault(symbol_prefixes=["A05", "105"]),
            "kospi200_full": MarginProductDefault(symbol_prefixes=["A01", "101"]),
        },
    }
    base.update(overrides)
    return FuturesMarginConfig(**base)


def _context(
    config, *, positions, snapshot=(50_000_000, None, True), atr=None, fail_closed=False
):
    specs = build_product_specs(config, _EXECUTION_SPECS)
    return MarginRunContext(
        config=config,
        product_specs=specs,
        positions_provider=lambda: positions,
        account_snapshot_provider=lambda: snapshot,
        atr_provider=lambda _syms: atr or {},
        fail_closed=fail_closed,
    )


def _redis_with_price(price="400.0"):
    redis = fakeredis.FakeStrictRedis(decode_responses=True)
    redis.hset("market:structure:latest", mapping={"fut_close": price})
    return redis


def test_build_product_specs_merges_execution_constants():
    config = _config()
    specs = build_product_specs(config, _EXECUTION_SPECS)
    assert specs["kospi200_mini"].multiplier_krw_per_point == 50000
    assert specs["kospi200_mini"].tick_size_points == 0.02
    assert specs["kospi200_mini"].initial_margin_rate == 0.08
    assert specs["kospi200_full"].multiplier_krw_per_point == 250000


def test_shipped_config_resolves_live_codes_to_nonunit_multiplier():
    """F4 (#601 class): the SHIPPED execution.yaml + futures_margin.yaml must
    resolve representative live/backtest trade codes to a real per-contract
    multiplier — never the 1.0 fallback a prefix drift would silently produce.

    The other build_product_specs tests use hand-made ``_EXECUTION_SPECS`` dicts,
    so they cannot catch a drift between the shipped ``futures_contract_spec``
    keys and the margin ``product_defaults`` ``symbol_prefixes``. If either
    drifts, ``spec_for_symbol`` returns ``None`` → LeverageFilter multiplier 1.0
    (~250,000x understatement, gate ineffective) with only a log line. This test
    is the regression pin for that class of silent understatement.
    """
    config = FuturesMarginConfig.load_or_default()
    specs = build_product_specs(config, load_execution_contract_specs())
    assert specs, "shipped config resolved 0 product specs (spec/prefix drift)"

    # kospi200_mini prefixes: A05 (live), 105 (backtest) → 50,000 KRW/pt.
    mini = spec_for_symbol("A05603", specs)
    assert mini is not None, "A05603 resolved no spec (mini prefix drift)"
    assert mini.multiplier_krw_per_point == 50_000.0
    assert mini.multiplier_krw_per_point != 1.0

    # kospi200_full prefixes: A01 (live near-month), 101 (연결선물) → 250,000 KRW/pt.
    for code in ("101S6000", "A01V3000"):
        full = spec_for_symbol(code, specs)
        assert full is not None, f"{code} resolved no spec (full prefix drift)"
        assert full.multiplier_krw_per_point == 250_000.0
        assert full.multiplier_krw_per_point != 1.0


def test_run_publishes_latest_hash_and_stream():
    config = _config()
    redis = _redis_with_price()
    context = _context(
        config,
        positions=[
            {"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}
        ],
        atr={"A05607": 5.0},
    )

    state = run_margin_risk(context=context, redis=redis, now=_NOW)
    assert state is not None

    latest = redis.hgetall(config.redis.latest_key)
    assert latest["risk_level"] == "ok"
    assert latest["schema_version"] == "1"
    assert float(latest["initial_margin_required_krw"]) == 1_600_000
    assert latest["stress_loss_1atr_krw"] == "250000.0000"

    ttl = redis.ttl(config.redis.latest_key)
    assert 0 < ttl <= config.redis.latest_ttl_seconds

    entries = redis.xrange(config.redis.stream_key)
    assert len(entries) == 1
    _, event = entries[0]
    assert event["risk_level"] == "ok"


def test_config_fallback_snapshot_marks_degraded_paper():
    config = _config()
    redis = _redis_with_price()
    # snapshot_ok=False (config fallback) in paper → degraded, not critical.
    context = _context(
        config,
        positions=[
            {"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}
        ],
        snapshot=(config.fallback_account_equity_krw, None, False),
        atr={"A05607": 5.0},
        fail_closed=False,
    )
    state = run_margin_risk(context=context, redis=redis, now=_NOW)
    assert state.degraded is True
    assert state.risk_level != "critical"
    latest = redis.hgetall(config.redis.latest_key)
    assert latest["degraded"] == "true"


def test_live_stale_snapshot_is_critical():
    config = _config()
    redis = _redis_with_price()
    context = _context(
        config,
        positions=[
            {"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}
        ],
        snapshot=(50_000_000, None, False),
        atr={"A05607": 5.0},
        fail_closed=True,
    )
    state = run_margin_risk(context=context, redis=redis, now=_NOW)
    assert state.risk_level == "critical"


def test_publish_replaces_stale_fields():
    config = _config()
    redis = _redis_with_price()
    redis.hset(config.redis.latest_key, mapping={"stale_field": "leftover"})
    context = _context(config, positions=[], atr={})
    run_margin_risk(context=context, redis=redis, now=_NOW)
    latest = redis.hgetall(config.redis.latest_key)
    assert "stale_field" not in latest


def test_disabled_config_is_noop():
    config = _config(enabled=False)
    redis = _redis_with_price()
    context = _context(config, positions=[], atr={})
    state = run_margin_risk(context=context, redis=redis, now=_NOW)
    assert state is None
    assert redis.hgetall(config.redis.latest_key) == {}


class _FakeLedger:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_risk_event(self, event) -> str:
        self.events.append(dict(event))
        return "risk-1"


def _critical_context(config, ledger):
    # Live + stale snapshot forces critical regardless of positions.
    specs = build_product_specs(config, _EXECUTION_SPECS)
    return MarginRunContext(
        config=config,
        product_specs=specs,
        positions_provider=lambda: [
            {"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}
        ],
        account_snapshot_provider=lambda: (50_000_000, None, False),
        atr_provider=lambda _syms: {"A05607": 5.0},
        fail_closed=True,
        ledger=ledger,
    )


def test_escalation_records_ledger_and_sets_prev_level():
    config = _config()
    redis = _redis_with_price()
    ledger = _FakeLedger()
    context = _critical_context(config, ledger)

    run_margin_risk(context=context, redis=redis, now=_NOW)

    assert len(ledger.events) == 1
    assert ledger.events[0]["event_type"] == "futures_margin_risk_escalation"
    assert ledger.events[0]["risk_level"] == "critical"
    assert redis.get("futures:risk:prev_level") == "critical"


def test_no_duplicate_ledger_on_same_level_rerun():
    config = _config()
    redis = _redis_with_price()
    ledger = _FakeLedger()
    context = _critical_context(config, ledger)

    run_margin_risk(context=context, redis=redis, now=_NOW)
    run_margin_risk(context=context, redis=redis, now=_NOW)

    # Second run stays at critical → no second escalation row.
    assert len(ledger.events) == 1


def test_ok_level_records_no_escalation():
    config = _config()
    redis = _redis_with_price()
    ledger = _FakeLedger()
    context = _context(
        config,
        positions=[
            {"code": "A05607", "side": "long", "quantity": 1, "current_price": 400.0}
        ],
        atr={"A05607": 5.0},
    )
    context.ledger = ledger

    run_margin_risk(context=context, redis=redis, now=_NOW)

    assert ledger.events == []
