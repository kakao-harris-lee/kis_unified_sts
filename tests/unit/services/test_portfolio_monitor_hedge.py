"""Unit tests for services.portfolio_monitor.hedge_advisor (Phase 4A glue).

Hermetic: fakeredis (sync, decode_responses) + tmp_path SQLite ledger +
injected providers/notifier — no real Redis, no Parquet, no network. Pins:

* the FIXED 4B-UI Redis publication (18-field ``portfolio:hedge:latest``
  hash + TTL, ``stream:portfolio.hedge`` maxlen/expire);
* ledger dedup — history rows ONLY on advisory transitions or
  recommended-contract changes;
* the Telegram advisory rising edge (one message per activation, message
  always states no automated orders);
* ``run_snapshot(hedge=...)`` / ``_cli`` wiring — an advisory failure never
  fails the equity snapshot;
* RuntimeLedger ``hedge_advice`` roundtrip + idempotent v3→v4 migration.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, timedelta

import fakeredis
import pytest

import services.portfolio_monitor.hedge_advisor as hedge_advisor_module
import services.portfolio_monitor.main as monitor_main
from services.portfolio_monitor.hedge_advisor import (
    HedgeRunContext,
    _dispatch_alert,
    advisory_message,
    build_betas,
    read_market_inputs,
    run_hedge_advice,
)
from shared.portfolio.config import TRACK_FUTURES, TRACK_STOCK, PortfolioConfig
from shared.portfolio.hedge import HedgeAdvisorConfig
from shared.storage.runtime_ledger import RuntimeLedgerError, SQLiteRuntimeLedger

DAY = date(2026, 7, 6)  # Monday
NOW = datetime(2026, 7, 6, 19, 0)

HEDGE_KEY = "portfolio:hedge:latest"
HEDGE_STREAM = "stream:portfolio.hedge"
STRUCTURE_KEY = "market:structure:latest"
RISK_KEY = "market:risk:latest"
EQUITY_KEY = "portfolio:equity:latest"
CONTRACT_KEY = "futures:contract:latest"
MARGIN_KEY = "futures:risk:latest"

#: Product constants mirror config/execution.yaml::futures_contract_spec.
EXEC_SPECS = {
    "kospi200_mini": {"multiplier_krw_per_point": 50_000, "tick_size_points": 0.02},
    "kospi200_full": {"multiplier_krw_per_point": 250_000, "tick_size_points": 0.05},
}

# Fixed contract with the 4B UI lane — exact field-name set (18 fields).
_CONTRACT_FIELDS = {
    "product",
    "multiplier",
    "futures_price",
    "stock_long_notional",
    "portfolio_beta",
    "beta_notional",
    "futures_net_contracts",
    "futures_net_notional",
    "net_beta_exposure",
    "recommended_short_contracts",
    "residual_exposure_after",
    "band",
    "score",
    "advisory_active",
    "reason",
    "degraded",
    "missing_components",
    "asof_ts",
}

#: HedgeAdvisorV2 append-only fields (published alongside the fixed 18).
_V2_FIELDS = {
    "target_hedge_ratio",
    "current_hedge_ratio",
    "delta_short_contracts",
    "max_contracts_by_margin",
    "margin_after_hedge_pct",
    "estimated_slippage_ticks",
    "roll_adjustment",
    "execution_feasibility",
    "operator_action",
}

#: Deterministic daily-return pattern shared by symbol/market series (β = 1).
_RETURN_PATTERN = [0.01, -0.005, 0.007, -0.012, 0.004]


def _synthetic_closes(base: float = 100.0, n_returns: int = 130):
    closes = [(date(2026, 1, 5), base)]
    day, value = date(2026, 1, 5), base
    for i in range(n_returns):
        day += timedelta(days=1)
        value *= 1.0 + _RETURN_PATTERN[i % len(_RETURN_PATTERN)]
        closes.append((day, value))
    return closes


_MARKET_CLOSES = _synthetic_closes()
_SYMBOL_CLOSES = _synthetic_closes(base=50_000.0)


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, message: str, **_kwargs) -> None:
        self.messages.append(message)


class BrokenNotifier:
    async def send_message(self, message: str, **_kwargs) -> None:
        raise RuntimeError("telegram down")


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def ledger(tmp_path):
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    yield ledger
    ledger.close()


def _stock_position(quantity=1000.0, price=60_000.0, code="005930"):
    return {"code": code, "side": "long", "quantity": quantity, "current_price": price}


def _context(
    *,
    stock=None,
    futures=None,
    notifier=None,
    config=None,
    execution_specs=None,
    daily=None,
    market=None,
):
    return HedgeRunContext(
        config=config or HedgeAdvisorConfig(),
        execution_specs=EXEC_SPECS if execution_specs is None else execution_specs,
        stock_positions_provider=lambda: list(stock or []),
        futures_positions_provider=lambda: list(futures or []),
        daily_closes_provider=daily or (lambda symbol, start, end: _SYMBOL_CLOSES),
        market_closes_provider=market or (lambda start, end: _MARKET_CLOSES),
        notifier=notifier,
    )


def _publish_inputs(redis, *, price="400.0", asof=NOW, band="HIGH", score="80.0"):
    """Upstream engine hashes read by the advisor (structure + risk)."""
    redis.delete(STRUCTURE_KEY, RISK_KEY)
    if price is not None:
        redis.hset(
            STRUCTURE_KEY, mapping={"fut_close": price, "asof_ts": asof.isoformat()}
        )
    if band is not None:
        redis.hset(RISK_KEY, mapping={"band": band, "score": score})


def _run(context, ledger, redis, *, day=DAY, now=NOW):
    return run_hedge_advice(
        context=context, ledger=ledger, redis=redis, trade_date=day, now=now
    )


# ---------------------------------------------------------------------------
# Redis publication contract
# ---------------------------------------------------------------------------


class TestPublication:
    def test_latest_hash_fields_and_ttl(self, ledger, redis):
        _publish_inputs(redis)
        advice = _run(_context(stock=[_stock_position()]), ledger, redis)

        assert advice is not None
        raw = redis.hgetall(HEDGE_KEY)
        # Base 18-field contract preserved as a subset; v2 adds 9 append-only.
        assert set(raw) >= _CONTRACT_FIELDS
        assert set(raw) >= _V2_FIELDS
        assert set(raw) == _CONTRACT_FIELDS | _V2_FIELDS
        assert raw["product"] == "mini_kospi200"
        assert raw["multiplier"] == "50000"
        # ₩60M long × β1.0 ÷ (400pt × ₩50k) = 3.0 → floor → 3 contracts.
        assert raw["recommended_short_contracts"] == "3"
        assert raw["advisory_active"] == "true"
        assert raw["degraded"] == "false"
        assert json.loads(raw["missing_components"]) == []
        assert float(raw["portfolio_beta"]) == pytest.approx(1.0)
        assert datetime.fromisoformat(raw["asof_ts"]) == NOW
        assert 0 < redis.ttl(HEDGE_KEY) <= 86400

    def test_v2_feasibility_from_operational_reads(self, ledger, redis):
        # Seed the Phase A/B read-models so the v2 layer folds them in.
        _publish_inputs(redis)  # HIGH band → target ratio 0.50
        redis.hset(
            CONTRACT_KEY,
            mapping={"roll_state": "normal", "hedge_front_allowed": "true"},
        )
        redis.hset(
            MARGIN_KEY,
            mapping={
                "risk_level": "ok",
                "margin_usage_pct": "0.1000",
                "max_additional_contracts": "10",
                "per_contract_initial_margin_krw": "1600000.0000",
                "account_equity_krw": "50000000.0000",
                "initial_margin_required_krw": "5000000.0000",
            },
        )
        advice = _run(_context(stock=[_stock_position()]), ledger, redis)
        assert advice is not None

        raw = redis.hgetall(HEDGE_KEY)
        assert raw["target_hedge_ratio"] == "0.5000"
        # feasible add recommended (advisory only).
        assert raw["execution_feasibility"] == "feasible"
        assert raw["operator_action"] == "place_manual_hedge"
        assert int(raw["delta_short_contracts"]) >= 1

    def test_v2_degrades_when_operational_reads_missing(self, ledger, redis):
        # No contract/margin hashes → v2 degrades to a no-op recommendation.
        _publish_inputs(redis)
        advice = _run(_context(stock=[_stock_position()]), ledger, redis)
        assert advice is not None
        raw = redis.hgetall(HEDGE_KEY)
        assert raw["execution_feasibility"] == "degraded"
        assert raw["operator_action"] == "review"
        # Base 18-field recommendation is still published unchanged.
        assert raw["recommended_short_contracts"] == "3"

    def test_stream_entry_maxlen_and_expire(self, ledger, redis):
        _publish_inputs(redis)
        xadd_kwargs = {}
        original_xadd = redis.xadd

        def _spy_xadd(key, fields, **kwargs):
            xadd_kwargs.update(kwargs)
            return original_xadd(key, fields, **kwargs)

        redis.xadd = _spy_xadd
        _run(_context(stock=[_stock_position()]), ledger, redis)

        assert xadd_kwargs == {"maxlen": 5000, "approximate": True}
        entries = redis.xrange(HEDGE_STREAM)
        assert len(entries) == 1
        assert entries[0][1] == redis.hgetall(HEDGE_KEY)
        assert 0 < redis.ttl(HEDGE_STREAM) <= 86400

    def test_stale_fields_never_linger(self, ledger, redis):
        _publish_inputs(redis)
        redis.hset(HEDGE_KEY, mapping={"legacy_field": "1"})
        _run(_context(), ledger, redis)
        assert "legacy_field" not in redis.hgetall(HEDGE_KEY)

    def test_disabled_config_publishes_nothing(self, ledger, redis):
        _publish_inputs(redis)
        config = HedgeAdvisorConfig(enabled=False)
        assert _run(_context(config=config), ledger, redis) is None
        assert redis.hgetall(HEDGE_KEY) == {}
        assert ledger.query_hedge_advice() == []

    def test_positions_read_failure_degrades_but_publishes(self, ledger, redis):
        _publish_inputs(redis)
        context = _context()

        def _boom():
            raise RuntimeError("state hash down")

        context.stock_positions_provider = _boom
        advice = _run(context, ledger, redis)

        assert advice is not None
        assert "stock_positions" in advice.missing_components
        assert redis.hgetall(HEDGE_KEY)["degraded"] == "true"

    @pytest.mark.parametrize(
        ("band", "stock_quantity", "expected"),
        [
            ("HIGH", 1000.0, "true"),  # band ≥ trigger AND rec ≥ 1
            ("CRITICAL", 1000.0, "true"),
            ("ELEVATED", 1000.0, "false"),  # band below trigger
            ("HIGH", 100.0, "false"),  # net 6M → rec 0
        ],
    )
    def test_advisory_active_conditions(
        self, ledger, redis, band, stock_quantity, expected
    ):
        _publish_inputs(redis, band=band)
        _run(_context(stock=[_stock_position(quantity=stock_quantity)]), ledger, redis)
        assert redis.hgetall(HEDGE_KEY)["advisory_active"] == expected

    def test_product_spec_mismatch_fails_loudly(self, ledger, redis):
        _publish_inputs(redis)
        bad_specs = {
            "kospi200_mini": {
                "multiplier_krw_per_point": 250_000,
                "tick_size_points": 0.02,
            }
        }
        with pytest.raises(ValueError, match="multiplier"):
            _run(_context(execution_specs=bad_specs), ledger, redis)
        assert redis.hgetall(HEDGE_KEY) == {}  # failed before any publish


# ---------------------------------------------------------------------------
# Market inputs (Redis DB 1 hashes)
# ---------------------------------------------------------------------------


class TestReadMarketInputs:
    def test_fresh_inputs_parse(self, redis):
        _publish_inputs(redis, price="401.5", band="HIGH", score="77.0")
        price, fresh, band, score = read_market_inputs(redis, HedgeAdvisorConfig(), NOW)
        assert price == pytest.approx(401.5)
        assert fresh is True
        assert band == "HIGH"
        assert score == pytest.approx(77.0)

    def test_stale_price_asof_marks_not_fresh(self, redis):
        _publish_inputs(redis, asof=NOW - timedelta(hours=25))
        price, fresh, _, _ = read_market_inputs(redis, HedgeAdvisorConfig(), NOW)
        assert price == pytest.approx(400.0)
        assert fresh is False

    def test_absent_hashes_return_nothing(self, redis):
        assert read_market_inputs(redis, HedgeAdvisorConfig(), NOW) == (
            None,
            False,
            None,
            None,
        )

    def test_garbage_values_coerce_to_none(self, redis):
        redis.hset(STRUCTURE_KEY, mapping={"fut_close": "abc", "asof_ts": "not-a-ts"})
        redis.hset(RISK_KEY, mapping={"band": "  ", "score": "nan"})
        assert read_market_inputs(redis, HedgeAdvisorConfig(), NOW) == (
            None,
            False,
            None,
            None,
        )


# ---------------------------------------------------------------------------
# β inputs
# ---------------------------------------------------------------------------


class TestBuildBetas:
    def test_synthetic_series_yield_unit_beta(self):
        betas = build_betas(_context(), [_stock_position()], DAY)
        assert set(betas) == {"005930"}
        assert betas["005930"].beta == pytest.approx(1.0, abs=1e-9)
        assert betas["005930"].fallback is False

    def test_shorts_and_blank_codes_excluded(self):
        positions = [
            {"code": "005930", "side": "short", "quantity": 1, "current_price": 1.0},
            {"code": "  ", "side": "long", "quantity": 1, "current_price": 1.0},
        ]
        assert build_betas(_context(), positions, DAY) == {}

    def test_provider_failure_degrades_to_fallback(self):
        def _boom(start, end):
            raise RuntimeError("parquet down")

        context = _context(market=_boom)
        betas = build_betas(context, [_stock_position()], DAY)
        assert betas["005930"].fallback is True
        assert betas["005930"].beta == pytest.approx(1.0)  # default_beta


# ---------------------------------------------------------------------------
# Ledger dedup — history rows only on transitions/changes
# ---------------------------------------------------------------------------


class TestLedgerDedup:
    def test_identical_reruns_record_once(self, ledger, redis):
        _publish_inputs(redis)
        context = _context(stock=[_stock_position()])
        _run(context, ledger, redis)
        _run(context, ledger, redis)

        rows = ledger.query_hedge_advice()
        assert len(rows) == 1
        assert rows[0]["recommended_short_contracts"] == 3
        assert bool(rows[0]["advisory_active"]) is True

    def test_contract_change_records_again(self, ledger, redis):
        _publish_inputs(redis)
        _run(_context(stock=[_stock_position(quantity=1000)]), ledger, redis)
        # ₩84M → raw 4.2 → 4 contracts: count changed → new history row.
        _run(_context(stock=[_stock_position(quantity=1400)]), ledger, redis)

        rows = ledger.query_hedge_advice()
        assert [row["recommended_short_contracts"] for row in rows] == [3, 4]

    def test_advisory_transition_records_deactivation(self, ledger, redis):
        context = _context(stock=[_stock_position()])
        _publish_inputs(redis, band="HIGH")
        _run(context, ledger, redis)
        _publish_inputs(redis, band="NEUTRAL")  # same contracts, active flips
        _run(context, ledger, redis)

        rows = ledger.query_hedge_advice()
        assert [bool(row["advisory_active"]) for row in rows] == [True, False]
        assert [row["recommended_short_contracts"] for row in rows] == [3, 3]

    def test_inactive_zero_baseline_records_nothing(self, ledger, redis):
        _publish_inputs(redis)
        _run(_context(), ledger, redis)  # no positions → rec 0, inactive
        assert ledger.query_hedge_advice() == []
        assert redis.hgetall(HEDGE_KEY) != {}  # …but the publish still happened

    def test_history_read_failure_degrades_without_killing_run(self, redis, tmp_path):
        _publish_inputs(redis)

        class _BrokenHistoryLedger:
            def query_hedge_advice(self, filters=None):
                raise RuntimeError("ledger down")

            def record_hedge_advice(self, row):
                raise RuntimeError("ledger down")

        advice = _run(
            _context(stock=[_stock_position()]), _BrokenHistoryLedger(), redis
        )
        assert advice is not None
        assert redis.hgetall(HEDGE_KEY)["recommended_short_contracts"] == "3"


# ---------------------------------------------------------------------------
# Telegram advisory — rising edge only, never an order
# ---------------------------------------------------------------------------


class TestTelegramRisingEdge:
    def test_one_message_per_activation(self, ledger, redis):
        notifier = FakeNotifier()
        context = _context(stock=[_stock_position()], notifier=notifier)

        _publish_inputs(redis, band="HIGH")
        _run(context, ledger, redis)  # inactive → active: 1 message
        assert len(notifier.messages) == 1

        _run(context, ledger, redis)  # active → active (unchanged): none
        assert len(notifier.messages) == 1

        _publish_inputs(redis, band="NEUTRAL")
        _run(context, ledger, redis)  # falling edge: none
        assert len(notifier.messages) == 1

        _publish_inputs(redis, band="HIGH")
        _run(context, ledger, redis)  # re-activation: second message
        assert len(notifier.messages) == 2

    def test_message_states_advisory_never_automated(self, ledger, redis):
        notifier = FakeNotifier()
        _publish_inputs(redis)
        _run(_context(stock=[_stock_position()], notifier=notifier), ledger, redis)

        assert len(notifier.messages) == 1
        message = notifier.messages[0]
        assert "권고" in message
        assert "3계약 숏" in message
        assert "자동 주문" in message
        assert "절대 실행되지 않습니다" in message

    def test_active_to_active_contract_change_sends_nothing(self, ledger, redis):
        notifier = FakeNotifier()
        _publish_inputs(redis)
        _run(
            _context(stock=[_stock_position(quantity=1000)], notifier=notifier),
            ledger,
            redis,
        )
        _run(
            _context(stock=[_stock_position(quantity=1400)], notifier=notifier),
            ledger,
            redis,
        )
        assert len(ledger.query_hedge_advice()) == 2  # recorded…
        assert len(notifier.messages) == 1  # …but no second alert

    def test_notifier_none_is_safe(self, ledger, redis):
        _publish_inputs(redis)
        advice = _run(_context(stock=[_stock_position()]), ledger, redis)
        assert advice is not None
        assert advice.advisory_active is True

    def test_notifier_failure_never_fails_the_run(self, ledger, redis):
        _publish_inputs(redis)
        advice = _run(
            _context(stock=[_stock_position()], notifier=BrokenNotifier()),
            ledger,
            redis,
        )
        assert advice is not None
        assert redis.hgetall(HEDGE_KEY)["advisory_active"] == "true"

    def test_dispatch_alert_none_notifier_returns(self):
        _dispatch_alert(None, "message")  # no raise

    def test_advisory_message_content(self, ledger, redis):
        _publish_inputs(redis, band="CRITICAL", score="91.0")
        advice = _run(_context(stock=[_stock_position()]), ledger, redis)
        message = advisory_message(advice)
        assert "CRITICAL" in message
        assert "score 91" in message
        assert "자동 주문은 절대 실행되지 않습니다" in message


# ---------------------------------------------------------------------------
# run_snapshot / _cli wiring — advisory failures never kill the equity batch
# ---------------------------------------------------------------------------


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


def _snapshot(config, ledger, redis, *, hedge=None, notifier=None):
    return monitor_main.run_snapshot(
        config=config,
        ledger=ledger,
        redis=redis,
        positions_providers={TRACK_STOCK: lambda: [], TRACK_FUTURES: lambda: []},
        calendar=_AlwaysOpenCalendar(),
        notifier=notifier,
        trade_date=DAY,
        now=NOW,
        sentinel_path="/nonexistent/never-written",
        suspend_key="futures:live:suspended",
        hedge=hedge,
    )


class TestRunSnapshotWiring:
    def test_hedge_failure_never_fails_the_equity_run(self, ledger, redis):
        _publish_inputs(redis)
        # Empty execution specs → verify_product_spec raises inside the hedge
        # lane; the equity snapshot must still persist/publish and return 0.
        bad_hedge = _context(execution_specs={})
        assert _snapshot(PortfolioConfig(), ledger, redis, hedge=bad_hedge) == 0

        assert redis.hgetall(EQUITY_KEY) != {}
        assert len(ledger.query_portfolio_equity_daily()) == 1
        assert redis.hgetall(HEDGE_KEY) == {}  # hedge lane failed before publish

    def test_hedge_runs_after_equity_when_context_given(self, ledger, redis):
        _publish_inputs(redis)
        hedge = _context(stock=[_stock_position()])
        assert _snapshot(PortfolioConfig(), ledger, redis, hedge=hedge) == 0

        assert redis.hgetall(EQUITY_KEY) != {}
        assert redis.hgetall(HEDGE_KEY)["recommended_short_contracts"] == "3"

    def test_hedge_none_skips_the_advisory_lane(self, ledger, redis):
        assert _snapshot(PortfolioConfig(), ledger, redis, hedge=None) == 0
        assert redis.hgetall(EQUITY_KEY) != {}
        assert redis.hgetall(HEDGE_KEY) == {}


class _StubLedger:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TestCliWiring:
    @pytest.fixture
    def cli_env(self, monkeypatch):
        """Hermetic _cli: stub config/ledger/redis/notifier + spy run_snapshot."""
        import redis as redis_lib

        captured: dict = {}
        stub_ledger = _StubLedger()

        class _StubPortfolioConfigCls:
            @staticmethod
            def load_or_default(path=None):
                return PortfolioConfig()

        monkeypatch.setattr(monitor_main, "PortfolioConfig", _StubPortfolioConfigCls)
        monkeypatch.setattr(monitor_main, "_default_ledger", lambda: stub_ledger)
        monkeypatch.setattr(monitor_main, "_default_notifier", lambda config: None)

        def _spy_run_snapshot(**kwargs):
            captured.update(kwargs)
            return 0

        monkeypatch.setattr(monitor_main, "run_snapshot", _spy_run_snapshot)

        # Descriptor-level save/restore: monkeypatch would put back a *bound*
        # method for a classmethod, so restore the raw descriptor ourselves.
        original_from_url = redis_lib.Redis.__dict__["from_url"]
        redis_lib.Redis.from_url = staticmethod(
            lambda url, **kwargs: fakeredis.FakeRedis(decode_responses=True)
        )
        try:
            yield captured, stub_ledger
        finally:
            redis_lib.Redis.from_url = original_from_url

    def test_cli_proceeds_with_hedge_none_when_context_fails(
        self, monkeypatch, cli_env
    ):
        captured, stub_ledger = cli_env

        def _boom(config=None):
            raise RuntimeError("hedge config unavailable")

        monkeypatch.setattr(hedge_advisor_module, "default_hedge_context", _boom)

        args = argparse.Namespace(date="2026-07-06", dry_run=True)
        assert monitor_main._cli(args) == 0  # snapshot still ran

        assert captured["hedge"] is None
        assert captured["trade_date"] == DAY
        assert captured["dry_run"] is True
        assert stub_ledger.closed is True

    def test_cli_passes_default_hedge_context_through(self, monkeypatch, cli_env):
        captured, _ = cli_env
        sentinel_context = object()
        monkeypatch.setattr(
            hedge_advisor_module,
            "default_hedge_context",
            lambda config=None: sentinel_context,
        )

        args = argparse.Namespace(date=None, dry_run=False)
        assert monitor_main._cli(args) == 0
        assert captured["hedge"] is sentinel_context


# ---------------------------------------------------------------------------
# RuntimeLedger hedge_advice — roundtrip + v3→v4 migration
# ---------------------------------------------------------------------------


def _ledger_row(**overrides) -> dict:
    row = {
        "trade_date": "2026-07-06",
        "asof_ts": "2026-07-06T19:00:00",
        "product": "mini_kospi200",
        "advisory_active": True,
        "recommended_short_contracts": 3,
        "net_beta_exposure": 60_000_000.0,
        "beta_notional": 60_000_000.0,
        "stock_long_notional": 60_000_000.0,
        "portfolio_beta": 1.0,
        "futures_net_contracts": -1,
        "futures_net_notional": -20_000_000.0,
        "futures_price": 400.0,
        "residual_exposure_after": 0.0,
        "band": "HIGH",
        "score": 80.0,
        "reason": "β-notional ₩60,000,000 …",
        "degraded": False,
        "missing_components": ["risk_score"],
    }
    row.update(overrides)
    return row


def _equity_row() -> dict:
    return {
        "trade_date": "2026-07-06",
        "total_equity": 15_000_000.0,
        "month_start_equity": 15_000_000.0,
        "month_peak_equity": 15_000_000.0,
        "monthly_mdd_pct": 0.0,
        "stage": "NORMAL",
        "mode": "shadow",
    }


class TestLedgerHedgeAdvice:
    def test_record_query_roundtrip(self, ledger):
        row_id = ledger.record_hedge_advice(_ledger_row())
        assert row_id > 0

        row = ledger.query_hedge_advice()[0]
        assert row["trade_date"] == "2026-07-06"
        assert row["product"] == "mini_kospi200"
        assert bool(row["advisory_active"]) is True
        assert row["recommended_short_contracts"] == 3
        assert row["net_beta_exposure"] == pytest.approx(60_000_000.0)
        assert row["portfolio_beta"] == pytest.approx(1.0)
        assert row["futures_net_contracts"] == -1
        assert row["band"] == "HIGH"
        assert row["score"] == pytest.approx(80.0)
        assert bool(row["degraded"]) is False
        assert json.loads(row["missing_components"]) == ["risk_score"]

    def test_nullable_fields_roundtrip(self, ledger):
        ledger.record_hedge_advice(
            _ledger_row(band=None, score=None, futures_price=None, portfolio_beta=None)
        )
        row = ledger.query_hedge_advice()[0]
        assert row["band"] is None
        assert row["score"] is None
        assert row["futures_price"] is None
        assert row["portfolio_beta"] is None

    def test_missing_trade_date_rejected(self, ledger):
        with pytest.raises(RuntimeLedgerError):
            ledger.record_hedge_advice({"product": "mini_kospi200"})

    def test_rows_append_in_insertion_order_with_date_filters(self, ledger):
        for day, contracts in [
            ("2026-07-06", 3),
            ("2026-07-07", 4),
            ("2026-07-08", 0),
        ]:
            ledger.record_hedge_advice(
                _ledger_row(trade_date=day, recommended_short_contracts=contracts)
            )

        rows = ledger.query_hedge_advice({"start": "2026-07-07"})
        assert [row["trade_date"] for row in rows] == ["2026-07-07", "2026-07-08"]
        assert len(ledger.query_hedge_advice({"limit": 2})) == 2

    def test_reopen_preserves_history(self, tmp_path):
        path = tmp_path / "runtime.db"
        first = SQLiteRuntimeLedger(path)
        first.record_hedge_advice(_ledger_row())
        first.close()

        second = SQLiteRuntimeLedger(path)
        try:
            assert len(second.query_hedge_advice()) == 1
        finally:
            second.close()

    def test_v3_db_without_hedge_table_migrates_idempotently(self, tmp_path):
        """Opening a pre-4A (v3) ledger must add hedge_advice and keep data."""
        path = tmp_path / "runtime.db"
        first = SQLiteRuntimeLedger(path)
        first.record_portfolio_equity_daily(_equity_row())
        first.close()

        # Rewind to the v3 shape: no hedge_advice table, version metadata 3.
        conn = sqlite3.connect(path)
        conn.execute("DROP TABLE hedge_advice")
        conn.execute("UPDATE ledger_metadata SET value='3' WHERE key='schema_version'")
        conn.commit()
        conn.close()

        second = SQLiteRuntimeLedger(path)
        try:
            assert second.query_hedge_advice() == []
            second.record_hedge_advice(_ledger_row())
            assert len(second.query_hedge_advice()) == 1
            version = (
                second._require_conn()
                .execute("SELECT value FROM ledger_metadata WHERE key='schema_version'")
                .fetchone()[0]
            )
            assert version == SQLiteRuntimeLedger.SCHEMA_VERSION == "4"
            assert len(second.query_portfolio_equity_daily()) == 1  # v3 data intact
        finally:
            second.close()
