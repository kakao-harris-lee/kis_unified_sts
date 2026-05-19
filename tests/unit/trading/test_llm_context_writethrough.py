import datetime
import json

from shared.llm.market_context import MarketContext


def _ctx():
    return MarketContext()  # defaults: NEUTRAL / 50.0 / 0.5


def test_redis_published_and_history_appended(monkeypatch):
    from services.trading import llm_context_publisher as mod

    redis_calls, ch_rows = [], []

    class FakePublisher:
        def __init__(self, asset):
            self.asset = asset

        def publish_market_context(self, ctx):
            redis_calls.append(ctx)

    class FakeCH:
        def insert_llm_market_context(self, rows):  # noqa: ARG002
            ch_rows.extend(rows)
            return len(rows)

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher
    )
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client", lambda cfg=None: FakeCH()  # noqa: ARG005
    )

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())

    assert len(redis_calls) == 1
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


def test_clickhouse_failure_does_not_break_redis(monkeypatch):
    from services.trading import llm_context_publisher as mod

    redis_calls = []

    class FakePublisher:
        def __init__(self, asset):
            pass

        def publish_market_context(self, ctx):
            redis_calls.append(ctx)

    class BoomCH:
        def insert_llm_market_context(self, _rows):
            raise RuntimeError("CH down")

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", FakePublisher
    )
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client", lambda cfg=None: BoomCH()  # noqa: ARG005
    )

    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())  # must NOT raise

    assert len(redis_calls) == 1  # Redis still happened


def test_history_appended_even_if_redis_publish_raises(monkeypatch):
    from services.trading import llm_context_publisher as mod

    ch_rows = []

    class BoomPublisher:
        def __init__(self, asset):
            pass

        def publish_market_context(self, _ctx):
            raise RuntimeError("redis down")

    class FakeCH:
        def insert_llm_market_context(self, rows):
            ch_rows.extend(rows)
            return len(rows)

    monkeypatch.setattr(
        "shared.streaming.trading_state.TradingStatePublisher", BoomPublisher
    )
    monkeypatch.setattr(
        "shared.db.client.get_clickhouse_client", lambda cfg=None: FakeCH()  # noqa: ARG005
    )
    pub = mod.LLMContextPublisher.__new__(mod.LLMContextPublisher)
    pub.asset_class = "futures"
    pub.publish_to_redis(_ctx())  # must NOT raise
    assert len(ch_rows) == 1  # history still appended despite Redis failure
