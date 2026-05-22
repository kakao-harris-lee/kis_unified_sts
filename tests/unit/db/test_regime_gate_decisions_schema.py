import datetime as dt


def test_schema_entry_exists_and_formats():
    from shared.db.client import SCHEMAS
    assert "regime_gate_decisions" in SCHEMAS
    ddl = SCHEMAS["regime_gate_decisions"].format(database="market")
    assert "CREATE TABLE IF NOT EXISTS market.regime_gate_decisions" in ddl
    assert "ORDER BY (strategy, ts)" in ddl
    assert "PARTITION BY toYYYYMM(ts)" in ddl
    assert "INTERVAL 90 DAY" in ddl


def test_insert_builds_expected_sql_and_tuples(monkeypatch):
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(ClickHouseConfig(
        host="localhost", port=9000, database="market",
        user="default", password=""))

    captured = {}

    class FakeSync:
        def execute(self, sql, data=None):
            captured["sql"] = sql
            captured["data"] = data
            return len(data) if data else 0

    monkeypatch.setattr(client, "get_sync_client", lambda: FakeSync())

    rows = [{
        "ts": dt.datetime(2026, 5, 22, 9, 0, 0),
        "strategy": "setup_a_gap_reversion",
        "asset": "futures",
        "signal_direction": "long",
        "allow": False,
        "reason": "regime_percentile=72.5>max",
        "regime_pct": 72.5,
    }]
    n = client.insert_regime_gate_decisions(rows)
    assert n == 1
    assert "INSERT INTO market.regime_gate_decisions" in captured["sql"]
    assert captured["data"] == [(
        dt.datetime(2026, 5, 22, 9, 0, 0), "setup_a_gap_reversion",
        "futures", "long", 0, "regime_percentile=72.5>max", 72.5,
    )]


def test_insert_empty_returns_zero():
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig
    ClickHouseClient.reset_singleton()
    client = ClickHouseClient(ClickHouseConfig(
        host="localhost", port=9000, database="market",
        user="default", password=""))
    assert client.insert_regime_gate_decisions([]) == 0
