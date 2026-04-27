"""V3 migration creates kospi.order_fills with the right schema."""

from pathlib import Path

V3_PATH = Path("infra/clickhouse/migrations/V3__create_order_fills.sql")


def test_v3_file_exists():
    assert V3_PATH.is_file(), "V3 migration file missing"


def test_v3_declares_required_columns():
    sql = V3_PATH.read_text()
    for column in (
        "signal_id",
        "order_id",
        "symbol",
        "side",
        "order_type",
        "requested_price",
        "filled_price",
        "tick_size_points",
        "slippage_ticks",
        "quantity",
        "requested_at",
        "filled_at",
        "latency_ms",
        "venue",
        "trade_role",
        "broker_error_code",
    ):
        assert column in sql, f"V3 missing column: {column}"


def test_v3_declares_ttl_and_partition():
    sql = V3_PATH.read_text()
    assert "PARTITION BY toYYYYMM(filled_at)" in sql
    assert "INTERVAL 5 YEAR" in sql
    assert "MergeTree" in sql


def test_v3_uses_correct_order_key():
    sql = V3_PATH.read_text()
    assert "ORDER BY (filled_at, order_id)" in sql


def test_v3_timestamps_use_utc_datetime64():
    sql = V3_PATH.read_text()
    assert "DateTime64(3, 'UTC')" in sql
    assert "requested_at DateTime64(3, 'UTC')" in sql
    assert "filled_at DateTime64(3, 'UTC')" in sql
