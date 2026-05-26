import datetime as dt


def test_schema_entry_exists_and_formats():
    from shared.db.client import SCHEMAS

    assert "llm_market_context" in SCHEMAS
    ddl = SCHEMAS["llm_market_context"].format(database="market")
    assert "CREATE TABLE IF NOT EXISTS market.llm_market_context" in ddl
    assert "ORDER BY (asset, ts)" in ddl
    assert "PARTITION BY toYYYYMM(ts)" in ddl
    assert "TTL" in ddl and "INTERVAL 2 YEAR" in ddl


def test_insert_builds_expected_sql_and_tuples(monkeypatch):
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(
        ClickHouseConfig(
            host="localhost", port=9000, database="market", user="default", password=""
        )
    )

    captured = {"calls": []}

    class FakeSync:
        def execute(self, sql, data=None):
            captured["sql"] = sql
            captured["data"] = data
            captured["calls"].append((sql, data))
            return len(data) if data else 0

    monkeypatch.setattr(client, "get_sync_client", lambda: FakeSync())

    rows = [
        {
            "ts": dt.datetime(2026, 5, 19, 1, 0, 0),
            "asset": "futures",
            "regime": "NEUTRAL",
            "overall_signal": "NEUTRAL",
            "risk_mode": "NEUTRAL",
            "risk_score": 50.0,
            "confidence": 0.5,
            "generated_at": dt.datetime(2026, 5, 19, 0, 59, 0),
            "metadata_json": "{}",
        }
    ]
    n = client.insert_llm_market_context(rows)
    assert n == 1
    assert any(
        "CREATE TABLE IF NOT EXISTS market.llm_market_context" in sql
        for sql, _data in captured["calls"]
    )
    assert "INSERT INTO market.llm_market_context" in captured["sql"]
    assert captured["data"] == [
        (
            dt.datetime(2026, 5, 19, 1, 0, 0),
            "futures",
            "NEUTRAL",
            "NEUTRAL",
            "NEUTRAL",
            50.0,
            0.5,
            dt.datetime(2026, 5, 19, 0, 59, 0),
            "{}",
        )
    ]


def test_insert_empty_returns_zero():
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(
        ClickHouseConfig(
            host="localhost", port=9000, database="market", user="default", password=""
        )
    )
    assert client.insert_llm_market_context([]) == 0
