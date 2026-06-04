import datetime
import json
import sqlite3

from shared.llm.market_context import MarketContext


def _ctx():
    return MarketContext()  # defaults: NEUTRAL / 50.0 / 0.5


def _configure_runtime_ledger(monkeypatch, db_path, *, mirror_enabled=False):
    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(db_path))
    monkeypatch.setenv(
        "RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED",
        "true" if mirror_enabled else "false",
    )


def _market_context_rows(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("""
            SELECT asset_class, context_type, created_at, payload_json
            FROM market_context_history
            ORDER BY created_at
            """).fetchall()


def test_redis_published_and_history_appended(monkeypatch, tmp_path):
    from services.trading import llm_context_publisher as mod

    db_path = tmp_path / "runtime.db"
    _configure_runtime_ledger(monkeypatch, db_path)
    redis_calls = []

    class FakePublisher:
        def __init__(self, asset):
            self.asset = asset

        def publish_market_context(self, ctx):
            redis_calls.append(ctx)

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher
    )

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())

    assert len(redis_calls) == 1
    rows = _market_context_rows(db_path)
    assert len(rows) == 1
    assert rows[0][0] == "futures"
    assert rows[0][1] == "llm_market_context"
    payload = json.loads(rows[0][3])
    assert payload["asset_class"] == "futures"
    assert payload["overall_signal"] == "중립"
    assert payload["risk_mode"] == "중립"
    assert payload["confidence"] == 0.5
    assert payload["regime"] == "NEUTRAL"
    assert payload["risk_score"] == 50.0
    assert payload["metadata"] == {}
    assert "generated_at" in payload


def test_runtime_ledger_failure_does_not_break_redis(monkeypatch):
    from services.trading import llm_context_publisher as mod

    redis_calls = []

    class FakePublisher:
        def __init__(self, asset):
            pass

        def publish_market_context(self, ctx):
            redis_calls.append(ctx)

    class BoomLedger:
        def record_market_context(self, _context):
            raise RuntimeError("ledger down")

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher
    )

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub._runtime_ledger = BoomLedger()
    pub.publish_to_redis(_ctx())  # must NOT raise

    assert len(redis_calls) == 1  # Redis still happened


def test_history_appended_even_if_redis_publish_raises(monkeypatch, tmp_path):
    from services.trading import llm_context_publisher as mod

    db_path = tmp_path / "runtime.db"
    _configure_runtime_ledger(monkeypatch, db_path)

    class BoomPublisher:
        def __init__(self, asset):
            pass

        def publish_market_context(self, _ctx):
            raise RuntimeError("redis down")

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", BoomPublisher
    )
    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())  # must NOT raise
    assert len(_market_context_rows(db_path)) == 1


def test_clickhouse_mirror_appends_only_when_enabled(monkeypatch, tmp_path):
    from services.trading import llm_context_publisher as mod

    db_path = tmp_path / "runtime.db"
    _configure_runtime_ledger(monkeypatch, db_path, mirror_enabled=True)
    redis_calls, ch_rows = [], []

    class FakePublisher:
        def __init__(self, asset):
            pass

        def publish_market_context(self, ctx):
            redis_calls.append(ctx)

    class FakeCH:
        def insert_llm_market_context(self, rows):
            ch_rows.extend(rows)
            return len(rows)

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher
    )
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client",
        lambda cfg=None: FakeCH(),  # noqa: ARG005
    )

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())

    assert len(redis_calls) == 1
    assert len(_market_context_rows(db_path)) == 1
    assert len(ch_rows) == 1
    assert ch_rows[0]["asset"] == "futures"
    assert ch_rows[0]["overall_signal"] == "중립"
    assert ch_rows[0]["risk_mode"] == "중립"
    assert ch_rows[0]["confidence"] == 0.5

    row = ch_rows[0]
    assert row["regime"] == "NEUTRAL"
    assert row["risk_score"] == 50.0
    assert json.loads(row["metadata_json"]) == {}
    assert isinstance(row["ts"], datetime.datetime) and row["ts"].tzinfo is None
    assert (
        isinstance(row["generated_at"], datetime.datetime)
        and row["generated_at"].tzinfo is None
    )
