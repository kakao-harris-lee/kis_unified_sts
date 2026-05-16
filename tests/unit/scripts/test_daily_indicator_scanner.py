import asyncio
import json
from datetime import date

import pandas as pd

import scripts.daily_indicator_scanner as scanner
from scripts.daily_indicator_scanner import (
    build_strategy_candidate_watchlist,
    compute_indicators,
    extract_candidate_symbols,
    get_clickhouse_client,
    is_fresh_daily_data,
    latest_candle_date,
    load_daily_candles,
    load_redis_candidate_symbols,
    publish_to_redis,
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
            self.value = None
            self.ttl = None

        def set(self, key, value, ex=None):
            self.key = key
            self.value = value
            self.ttl = ex

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

    payload = json.loads(fake.value)
    assert payload["symbol_count"] == 1
    assert payload["requested_symbol_count"] == 2
    assert payload["redis_candidate_count"] == 1
    assert payload["strategies"] == {"daily_pullback": ["005930"]}


def test_get_clickhouse_client_loads_repo_env(tmp_path, monkeypatch):
    calls = {}

    def fake_load_dotenv(path, override=False):
        calls["dotenv"] = (path, override)

    def fake_get_client(**kwargs):
        calls["client"] = kwargs
        return object()

    monkeypatch.setattr(scanner, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(scanner, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv("CLICKHOUSE_USER", "u")
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "p")
    monkeypatch.setattr("clickhouse_connect.get_client", fake_get_client)

    get_clickhouse_client()

    assert calls["dotenv"] == (tmp_path / ".env", False)
    assert calls["client"]["username"] == "u"
    assert calls["client"]["password"] == "p"


def test_load_daily_candles_fetches_extra_and_filters_placeholder_run():
    class Result:
        result_rows = [
            ("005930", date(2026, 1, 1), 50500, 50500, 50500, 50500, 1_000_000),
            ("005930", date(2026, 1, 2), 50500, 50500, 50500, 50500, 1_000_000),
            ("005930", date(2026, 1, 3), 50500, 50500, 50500, 50500, 1_000_000),
            ("005930", date(2026, 1, 4), 100, 105, 95, 102, 900_000),
            ("005930", date(2026, 1, 5), 102, 108, 101, 107, 950_000),
        ]

    class Client:
        def __init__(self):
            self.parameters = None

        def query(self, _query, parameters):
            self.parameters = parameters
            return Result()

    client = Client()
    cfg = DailyCandleQualityConfig(fetch_multiplier=3, repeated_ohlcv_run_min=3)

    df = load_daily_candles(client, "005930", days=2, quality_config=cfg)

    assert client.parameters == {"code": "005930", "limit": 6}
    assert df["date"].tolist() == [date(2026, 1, 4), date(2026, 1, 5)]
