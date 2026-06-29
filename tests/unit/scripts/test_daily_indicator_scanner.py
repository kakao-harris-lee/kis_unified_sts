import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pandas as pd

import scripts.daily_indicator_scanner as scanner
from scripts.daily_indicator_scanner import (
    _load_dynamic_only_strategies,
    backfill_missing_candidate_candles,
    build_strategy_candidate_watchlist,
    compute_futures_daily_indicators,
    compute_indicators,
    extract_candidate_symbols,
    get_market_data_store,
    is_fresh_daily_data,
    latest_candle_date,
    load_daily_candles,
    load_enabled_daily_strategies,
    load_redis_candidate_symbols,
    load_symbol_indicators,
    publish_to_redis,
    scan_futures_symbols,
)
from shared.collector.historical.calendar import trading_day_lag
from shared.collector.historical.daily_quality import DailyCandleQualityConfig


def test_latest_candle_date_returns_max_date():
    df = pd.DataFrame({"date": [date(2026, 5, 14), date(2026, 5, 15)]})

    assert latest_candle_date(df) == date(2026, 5, 15)


def test_daily_indicator_freshness_allows_weekend_gap():
    df = pd.DataFrame({"date": [date(2026, 5, 15)]})

    assert is_fresh_daily_data(
        df,
        expected_latest=date(2026, 5, 15),
        max_stale_trading_days=0,
    )


def test_daily_indicator_freshness_rejects_old_trading_day():
    df = pd.DataFrame({"date": [date(2026, 5, 13)]})

    assert not is_fresh_daily_data(
        df,
        expected_latest=date(2026, 5, 15),
        max_stale_trading_days=1,
    )


def test_trading_day_lag_skips_weekends():
    assert trading_day_lag(date(2026, 5, 15), date(2026, 5, 18)) == 1


def test_compute_indicators_includes_daily_volume_ratio():
    rows = []
    for i in range(220):
        rows.append(
            {
                "date": date(2026, 1, 1),
                "open": 100.0 + i,
                "high": 102.0 + i,
                "low": 99.0 + i,
                "close": 101.0 + i,
                "volume": 1_000_000 if i < 219 else 2_000_000,
            }
        )
    df = pd.DataFrame(rows)

    indicators = compute_indicators(df, volume_lookback=20)

    assert indicators is not None
    assert "daily_volume_ratio" in indicators
    assert indicators["daily_volume_ratio"] == 2.0


def test_compute_indicators_includes_daily_technical_consensus_fields():
    rows = []
    close = 100.0
    for i in range(220):
        close += 1.0 if i % 3 else -0.5
        rows.append(
            {
                "date": date(2026, 1, 1),
                "open": close - 0.5,
                "high": close + 2.0,
                "low": close - 2.0,
                "close": close,
                "volume": 1_000_000 + i * 1000,
            }
        )
    df = pd.DataFrame(rows)

    indicators = compute_indicators(df)

    assert indicators is not None
    for key in (
        "daily_rsi_14",
        "daily_prev_rsi_14",
        "daily_williams_r_14",
        "daily_prev_williams_r_14",
        "daily_macd_hist",
        "daily_prev_macd_hist",
    ):
        assert key in indicators
        assert isinstance(indicators[key], float)


def test_compute_indicators_allows_partial_history_without_sma200():
    rows = []
    close = 100.0
    for i in range(100):
        close += 1.0 if i % 3 else -0.5
        rows.append(
            {
                "date": date(2026, 1, 1),
                "open": close - 0.5,
                "high": close + 2.0,
                "low": close - 2.0,
                "close": close,
                "volume": 1_000_000,
            }
        )
    df = pd.DataFrame(rows)

    indicators = compute_indicators(df)

    assert indicators is not None
    assert "daily_sma_200" not in indicators
    assert "daily_sma_20" in indicators
    assert "daily_sma_60" in indicators
    assert "daily_rsi_14" in indicators


def test_extract_candidate_symbols_from_pipeline_shapes():
    payload = {
        "codes": ["005930", "000660"],
        "final_codes": ["035420", "005930"],
        "strategies": {
            "trend_pullback": ["006400"],
            "momentum_breakout": ["000660", "066570"],
        },
        "candidates": [{"code": "068270"}, "051910"],
    }

    assert extract_candidate_symbols(payload) == [
        "005930",
        "000660",
        "035420",
        "006400",
        "066570",
        "068270",
        "051910",
    ]


def test_load_redis_candidate_symbols_merges_keys_in_order():
    class FakeRedis:
        def __init__(self):
            self.data = {
                "targets": b'{"codes":["005930","000660"]}',
                "watchlist": '{"strategies":{"daily_pullback":["035420"]}}',
                "bad": "not-json",
                "llm": '{"final_codes":["000660","068270"]}',
            }

        def get(self, key):
            return self.data.get(key)

    assert load_redis_candidate_symbols(
        redis_client=FakeRedis(),
        keys=["targets", "watchlist", "bad", "llm"],
    ) == ["005930", "000660", "035420", "068270"]


def test_build_strategy_candidate_watchlist_uses_strategy_logic():
    class FakeStrategy:
        name = "daily_pullback"

        async def check_entry(self, context):
            if context.market_data["code"] == "005930":
                return object()
            return None

    watchlist = asyncio.run(
        build_strategy_candidate_watchlist(
            {
                "005930": {"daily_close": 70000},
                "000660": {"daily_close": 120000},
            },
            strategies=[FakeStrategy()],
            max_candidates=1,
        )
    )

    assert watchlist == {"daily_pullback": ["005930"]}


def test_publish_to_redis_includes_coverage_metadata():
    class FakeRedis:
        def __init__(self):
            self.values = {}
            self.ttls = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex=None):
            self.values[key] = value
            self.ttls[key] = ex

    fake = FakeRedis()

    publish_to_redis(
        {"005930": {"daily_sma_20": 100.0}},
        redis_client=fake,
        metadata={
            "requested_symbol_count": 2,
            "redis_candidate_count": 1,
            "strategies": {"daily_pullback": ["005930"]},
        },
    )

    payload = json.loads(fake.values[scanner.REDIS_KEY])
    assert payload["symbol_count"] == 1
    assert payload["requested_symbol_count"] == 2
    assert payload["redis_candidate_count"] == 1
    assert payload["strategies"] == {"daily_pullback": ["005930"]}

    compat = json.loads(fake.values[scanner.DAILY_WATCHLIST_COMPAT_KEY])
    assert compat["source"] == scanner.REDIS_KEY
    assert compat["strategies"] == {"daily_pullback": ["005930"]}
    assert compat["counts"] == {"daily_pullback": 1}
    assert fake.ttls[scanner.DAILY_WATCHLIST_COMPAT_KEY] == scanner.REDIS_TTL


def test_publish_to_redis_merges_same_day_strategy_watchlist():
    class FakeRedis:
        def __init__(self):
            self.values = {
                scanner.DAILY_WATCHLIST_COMPAT_KEY: json.dumps(
                    {
                        "timestamp": date.today().isoformat(),
                        "strategies": {
                            "trend_pullback": ["005930"],
                            "momentum_breakout": ["000660"],
                        },
                    }
                )
            }
            self.ttls = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex=None):
            self.values[key] = value
            self.ttls[key] = ex

    fake = FakeRedis()

    publish_to_redis(
        {"086790": {"daily_sma_20": 100.0}},
        redis_client=fake,
        metadata={"strategies": {"pattern_pullback": ["086790"]}},
    )

    compat = json.loads(fake.values[scanner.DAILY_WATCHLIST_COMPAT_KEY])
    assert compat["strategies"] == {
        "trend_pullback": ["005930"],
        "momentum_breakout": ["000660"],
        "pattern_pullback": ["086790"],
    }
    assert compat["counts"] == {
        "trend_pullback": 1,
        "momentum_breakout": 1,
        "pattern_pullback": 1,
    }


def test_publish_to_redis_ignores_stale_strategy_watchlist():
    class FakeRedis:
        def __init__(self):
            self.values = {
                scanner.DAILY_WATCHLIST_COMPAT_KEY: json.dumps(
                    {
                        "timestamp": "2026-01-01",
                        "strategies": {"trend_pullback": ["005930"]},
                    }
                )
            }
            self.ttls = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ex=None):
            self.values[key] = value
            self.ttls[key] = ex

    fake = FakeRedis()

    publish_to_redis(
        {"086790": {"daily_sma_20": 100.0}},
        redis_client=fake,
        metadata={"strategies": {"pattern_pullback": ["086790"]}},
    )

    compat = json.loads(fake.values[scanner.DAILY_WATCHLIST_COMPAT_KEY])
    assert compat["strategies"] == {"pattern_pullback": ["086790"]}
    assert compat["counts"] == {"pattern_pullback": 1}


def test_get_market_data_store_loads_repo_env(tmp_path, monkeypatch):
    calls = {}

    def fake_load_dotenv(path, override=False):
        calls["dotenv"] = (path, override)

    def fake_load_or_default():
        calls["storage"] = True
        return SimpleNamespace(
            market_data=SimpleNamespace(parquet=SimpleNamespace(root=str(tmp_path)))
        )

    monkeypatch.setattr(scanner, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(scanner, "load_dotenv", fake_load_dotenv)
    monkeypatch.setattr(scanner.StorageConfig, "load_or_default", fake_load_or_default)

    store = get_market_data_store()

    assert calls["dotenv"] == (tmp_path / ".env", False)
    assert calls["storage"] is True
    assert str(store.root) == str(tmp_path)


def test_load_daily_candles_fetches_extra_and_filters_placeholder_run():
    class Client:
        def __init__(self):
            self.calls = []

        def get_daily_bars(self, symbol, limit):
            self.calls.append((symbol, limit))
            return pd.DataFrame(
                [
                    ("005930", date(2026, 1, 1), 50500, 50500, 50500, 50500, 1_000_000),
                    ("005930", date(2026, 1, 2), 50500, 50500, 50500, 50500, 1_000_000),
                    ("005930", date(2026, 1, 3), 50500, 50500, 50500, 50500, 1_000_000),
                    ("005930", date(2026, 1, 4), 100, 105, 95, 102, 900_000),
                    ("005930", date(2026, 1, 5), 102, 108, 101, 107, 950_000),
                ],
                columns=["code", "datetime", "open", "high", "low", "close", "volume"],
            )

    client = Client()
    cfg = DailyCandleQualityConfig(fetch_multiplier=3, repeated_ohlcv_run_min=3)

    df = load_daily_candles(client, "005930", days=2, quality_config=cfg)

    assert client.calls == [("005930", 6)]
    assert df["date"].tolist() == [date(2026, 1, 4), date(2026, 1, 5)]


def test_load_symbol_indicators_reports_no_data():
    class Client:
        def get_daily_bars(self, symbol, limit):
            assert symbol == "005930"
            assert limit > 0
            return pd.DataFrame()

    indicators, reason = load_symbol_indicators(
        Client(),
        "005930",
        days=250,
        quality_config=DailyCandleQualityConfig(),
        expected_latest=date(2026, 5, 15),
        max_stale_trading_days=1,
    )

    assert indicators is None
    assert reason == "no_data"


def test_backfill_missing_candidate_candles_limits_and_dedupes(monkeypatch):
    calls = {}

    async def fake_collect_daily_candles(codes, days, verbose):
        calls["codes"] = codes
        calls["days"] = days
        calls["verbose"] = verbose
        return 123

    import shared.collector.historical.daily_stock as daily_stock

    monkeypatch.setattr(
        daily_stock,
        "collect_daily_candles",
        fake_collect_daily_candles,
    )

    rows = asyncio.run(
        backfill_missing_candidate_candles(
            ["005930", "005930", "000660"],
            days=100,
            max_symbols=1,
        )
    )

    assert rows == 123
    assert calls == {"codes": ["005930"], "days": 100, "verbose": False}


def test_compute_futures_daily_indicators_returns_required_keys():
    # 80 synthetic days with mild uptrend + small daily noise so RSI is well
    # defined (purely monotonic series would yield avg_loss == 0 → NaN RSI).
    closes = [1000.0 + i * 1.25 + (5.0 if i % 3 else -3.0) for i in range(80)]
    df = pd.DataFrame(
        {
            "date": [date(2026, 1, 1)] * 80,  # placeholder; not used by compute
            "open": closes,
            "high": [c + 5.0 for c in closes],
            "low": [c - 5.0 for c in closes],
            "close": closes,
            "volume": [1000] * 80,
        }
    )

    result = compute_futures_daily_indicators(df)
    assert result is not None
    # daily_regime_trend_filter consumes exactly these keys (see
    # shared/strategy/gates/daily_regime_trend_gate.py defaults).
    for key in (
        "daily_close",
        "daily_ema_20",
        "daily_ema_20_prev",
        "daily_ema_60",
        "daily_rsi_14",
    ):
        assert key in result, f"missing required key {key}"
    # Sanity: rising series → ema_20 > ema_60 (BULL regime), rsi > 50
    assert result["daily_ema_20"] > result["daily_ema_60"]
    assert result["daily_rsi_14"] > 50.0


def test_compute_futures_daily_indicators_insufficient_history_returns_none():
    df = pd.DataFrame(
        {
            "date": [date(2026, 1, 1)] * 30,
            "open": [1000.0] * 30,
            "high": [1001.0] * 30,
            "low": [999.0] * 30,
            "close": [1000.0] * 30,
            "volume": [1000] * 30,
        }
    )
    assert compute_futures_daily_indicators(df) is None


def test_scan_futures_symbols_aggregates_per_symbol():
    """scan_futures_symbols uses ParquetMarketDataStore.get_minute_bars API.

    The client must expose get_minute_bars(symbol) returning a DataFrame with
    datetime and OHLCV columns; the function aggregates to daily candles itself.
    At least 60 distinct trading days with >=30 bars each are needed for
    compute_futures_daily_indicators to return a result.
    """
    # Build 80 synthetic trading days × 35 bars each to pass the
    # _FUTURES_MIN_BARS_PER_DAY=30 gate and the >=60-day indicator minimum.
    import pytz

    kst = pytz.timezone("Asia/Seoul")
    rows = []
    base_close = 1000.0
    bdate_range = pd.bdate_range("2026-01-02", periods=80, tz=kst)
    for day_ts in bdate_range:
        close = base_close
        for minute in range(35):
            ts = day_ts.normalize() + pd.Timedelta(hours=9, minutes=minute)
            rows.append(
                {
                    "datetime": ts.tz_convert("UTC"),
                    "open": close,
                    "high": close + 2.0,
                    "low": close - 2.0,
                    "close": close,
                    "volume": 1000 + minute,
                }
            )
        base_close += 1.25

    minute_df = pd.DataFrame(rows)

    class Client:
        def __init__(self):
            self.calls: list[str] = []

        def get_minute_bars(self, symbol: str) -> pd.DataFrame:
            self.calls.append(symbol)
            return minute_df.copy()

    client = Client()
    out = scan_futures_symbols(client, ["101S6000"])
    assert "101S6000" in out
    assert "daily_ema_20" in out["101S6000"]
    assert client.calls == ["101S6000"]


# ---------------------------------------------------------------------------
# dynamic_only_strategies exclusion tests (fix/momentum-breakout-dynamic-prescreen)
# ---------------------------------------------------------------------------


def test_load_dynamic_only_strategies_reads_config(monkeypatch):
    """_load_dynamic_only_strategies returns names from daily_scanner.yaml."""

    def fake_load(path):
        assert path == "daily_scanner.yaml"
        return {"dynamic_only_strategies": ["momentum_breakout", "other_strategy"]}

    monkeypatch.setattr(scanner, "_load_dynamic_only_strategies", lambda: frozenset())
    # Bypass the scanner module-level cache by calling the real function with a
    # monkeypatched ConfigLoader instead.
    import shared.config.loader as loader_mod

    monkeypatch.setattr(loader_mod.ConfigLoader, "load", staticmethod(fake_load))
    result = _load_dynamic_only_strategies()
    assert result == frozenset({"momentum_breakout", "other_strategy"})


def test_load_dynamic_only_strategies_fallback_on_error(monkeypatch):
    """_load_dynamic_only_strategies returns empty frozenset when config missing."""
    import shared.config.loader as loader_mod

    def bad_load(path):
        raise FileNotFoundError("no config")

    monkeypatch.setattr(loader_mod.ConfigLoader, "load", staticmethod(bad_load))
    result = _load_dynamic_only_strategies()
    assert result == frozenset()


def test_load_enabled_daily_strategies_excludes_dynamic_only(monkeypatch):
    """A strategy listed in dynamic_only is NOT returned, so no key is emitted."""

    class _FakeStrategy:
        def __init__(self, name):
            self.name = name

    # Patch StrategyFactory and ConfigLoader so no filesystem I/O is needed.
    # Two configs: trend_pullback (daily) and momentum_breakout (daily).
    fake_configs = [
        {"strategy": {"name": "trend_pullback", "timeframe": "daily"}},
        {"strategy": {"name": "momentum_breakout", "timeframe": "daily"}},
    ]

    monkeypatch.setattr(
        scanner,
        "load_enabled_daily_strategies",
        scanner.load_enabled_daily_strategies,  # keep real function; patch internals
    )

    import shared.config.loader as loader_mod
    import shared.strategy.registry as registry_mod

    monkeypatch.setattr(
        loader_mod.ConfigLoader,
        "load_all_strategies",
        staticmethod(lambda *_a, **_kw: fake_configs),
    )
    monkeypatch.setattr(registry_mod, "register_builtin_components", lambda: None)
    monkeypatch.setattr(
        registry_mod.StrategyFactory,
        "create",
        staticmethod(lambda cfg: _FakeStrategy(cfg["strategy"]["name"])),
    )

    strategies = load_enabled_daily_strategies(
        dynamic_only=frozenset({"momentum_breakout"})
    )
    names = [s.name for s in strategies]
    assert "momentum_breakout" not in names
    assert "trend_pullback" in names


def test_load_enabled_daily_strategies_keeps_non_excluded(monkeypatch):
    """A strategy NOT in dynamic_only passes through normally."""

    class _FakeStrategy:
        def __init__(self, name):
            self.name = name

    fake_configs = [
        {"strategy": {"name": "trend_pullback", "timeframe": "daily"}},
        {"strategy": {"name": "pattern_pullback", "timeframe": "daily"}},
    ]

    import shared.config.loader as loader_mod
    import shared.strategy.registry as registry_mod

    monkeypatch.setattr(
        loader_mod.ConfigLoader,
        "load_all_strategies",
        staticmethod(lambda *_a, **_kw: fake_configs),
    )
    monkeypatch.setattr(registry_mod, "register_builtin_components", lambda: None)
    monkeypatch.setattr(
        registry_mod.StrategyFactory,
        "create",
        staticmethod(lambda cfg: _FakeStrategy(cfg["strategy"]["name"])),
    )

    # Neither strategy is in dynamic_only → both returned
    strategies = load_enabled_daily_strategies(dynamic_only=frozenset())
    names = [s.name for s in strategies]
    assert "trend_pullback" in names
    assert "pattern_pullback" in names


def test_excluded_strategy_absent_key_yields_dynamic_gate():
    """End-to-end: excluded strategy → no key in strategies dict → gate dynamic.

    When the scanner emits no key for momentum_breakout, the
    daily_watchlist_allows gate returns True for any code, confirming the
    strategy runs in dynamic mode against the full live universe.
    """
    from shared.strategy.entry.daily_watchlist_gate import daily_watchlist_allows

    # Payload that the scanner produces when momentum_breakout is excluded:
    # trend_pullback has a non-empty list, momentum_breakout key is absent.
    metadata = {
        "daily_watchlist": {
            "strategies": {
                "trend_pullback": ["005930"],
                # momentum_breakout intentionally absent
            }
        }
    }

    # trend_pullback in static mode: only 005930 allowed
    assert daily_watchlist_allows(metadata, "trend_pullback", "005930") is True
    assert daily_watchlist_allows(metadata, "trend_pullback", "000660") is False

    # momentum_breakout absent → dynamic mode → any code passes
    assert daily_watchlist_allows(metadata, "momentum_breakout", "005930") is True
    assert daily_watchlist_allows(metadata, "momentum_breakout", "000660") is True
    assert daily_watchlist_allows(metadata, "momentum_breakout", "066570") is True


def test_excluded_strategy_empty_list_also_yields_dynamic_gate():
    """Absent and empty list are both dynamic mode per daily_watchlist_allows."""
    from shared.strategy.entry.daily_watchlist_gate import daily_watchlist_allows

    metadata = {
        "daily_watchlist": {
            "strategies": {
                "trend_pullback": ["005930"],
                "momentum_breakout": [],  # explicit empty list
            }
        }
    }

    # Empty list → dynamic (same as absent)
    assert daily_watchlist_allows(metadata, "momentum_breakout", "000660") is True
    assert daily_watchlist_allows(metadata, "momentum_breakout", "066570") is True
