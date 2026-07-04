"""SQLite schema migration helpers for RuntimeLedger."""

from __future__ import annotations

import sqlite3

from .runtime_ledger_helpers import (
    _utc_now_iso,
)


class RuntimeLedgerSchemaMixin:
    def _migrate(self) -> None:
        with self._lock:
            conn = self._require_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ledger_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    asset_class TEXT,
                    symbol TEXT,
                    side TEXT,
                    order_type TEXT,
                    quantity INTEGER,
                    price REAL,
                    status TEXT,
                    strategy TEXT,
                    broker_order_id TEXT,
                    client_order_id TEXT,
                    track_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    order_id TEXT,
                    asset_class TEXT,
                    symbol TEXT,
                    side TEXT,
                    quantity INTEGER,
                    price REAL,
                    filled_at TEXT NOT NULL,
                    broker_fill_id TEXT,
                    venue TEXT,
                    track_id TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    asset_class TEXT,
                    symbol TEXT,
                    name TEXT,
                    side TEXT,
                    strategy TEXT,
                    entry_time TEXT,
                    entry_price REAL,
                    exit_time TEXT,
                    exit_price REAL,
                    quantity INTEGER,
                    pnl REAL,
                    pnl_pct REAL,
                    hold_seconds INTEGER,
                    exit_reason TEXT,
                    track_id TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS position_snapshots (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT UNIQUE,
                    position_id TEXT NOT NULL,
                    asset_class TEXT,
                    symbol TEXT,
                    name TEXT,
                    side TEXT,
                    strategy TEXT,
                    quantity INTEGER,
                    entry_time TEXT,
                    entry_price REAL,
                    current_price REAL,
                    high_since_entry REAL,
                    low_since_entry REAL,
                    stop_price REAL,
                    state TEXT,
                    is_open INTEGER NOT NULL,
                    exit_time TEXT,
                    exit_price REAL,
                    exit_reason TEXT,
                    pnl REAL,
                    snapshot_time TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_position_snapshots_latest
                    ON position_snapshots(position_id, row_id);
                CREATE INDEX IF NOT EXISTS idx_position_snapshots_asset_open
                    ON position_snapshots(asset_class, is_open);
                CREATE INDEX IF NOT EXISTS idx_trades_query
                    ON trades(asset_class, symbol, strategy, exit_time);

                CREATE TABLE IF NOT EXISTS risk_events (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    event_type TEXT,
                    asset_class TEXT,
                    severity TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS signal_decisions (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    signal_id TEXT,
                    asset_class TEXT,
                    symbol TEXT,
                    strategy TEXT,
                    decision TEXT,
                    track_id TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_context_history (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    asset_class TEXT,
                    symbol TEXT,
                    context_type TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS llm_predictions (
                    date_kst TEXT NOT NULL,
                    facet TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confidence REAL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (date_kst, facet)
                );

                CREATE TABLE IF NOT EXISTS prediction_scores (
                    date_kst TEXT NOT NULL,
                    facet TEXT NOT NULL,
                    correct INTEGER,
                    value REAL NOT NULL,
                    economic_proxy REAL NOT NULL,
                    baseline_value REAL NOT NULL,
                    edge REAL NOT NULL,
                    detail_json TEXT NOT NULL,
                    scored_at TEXT NOT NULL,
                    PRIMARY KEY (date_kst, facet)
                );

                CREATE TABLE IF NOT EXISTS portfolio_equity_daily (
                    trade_date TEXT PRIMARY KEY,
                    track_a_equity REAL,
                    track_b_equity REAL,
                    track_c_equity REAL,
                    total_equity REAL NOT NULL,
                    month_start_equity REAL NOT NULL,
                    month_peak_equity REAL NOT NULL,
                    monthly_mdd_pct REAL NOT NULL,
                    stage TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    degraded INTEGER NOT NULL DEFAULT 0,
                    missing_components TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hedge_advice (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL,
                    asof_ts TEXT NOT NULL,
                    product TEXT NOT NULL,
                    advisory_active INTEGER NOT NULL DEFAULT 0,
                    recommended_short_contracts INTEGER NOT NULL DEFAULT 0,
                    net_beta_exposure REAL,
                    beta_notional REAL,
                    stock_long_notional REAL,
                    portfolio_beta REAL,
                    futures_net_contracts INTEGER,
                    futures_net_notional REAL,
                    futures_price REAL,
                    residual_exposure_after REAL,
                    band TEXT,
                    score REAL,
                    reason TEXT,
                    degraded INTEGER NOT NULL DEFAULT 0,
                    missing_components TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_hedge_advice_trade_date
                    ON hedge_advice(trade_date);
                """)
            for table in self._TRACK_TAGGED_TABLES:
                self._ensure_column(conn, table, "track_id", "track_id TEXT")
            self._upsert_metadata("schema_version", self.SCHEMA_VERSION)
            self._upsert_metadata("ledger_path", str(self.path))

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection, table: str, column: str, ddl: str
    ) -> None:
        """Idempotently add a column to an existing table.

        ``ALTER TABLE ... ADD COLUMN`` in SQLite is a metadata-only change
        (no table rewrite), so the WAL write lock window is minimal. Skips
        when the column already exists — safe to run on every startup.
        """
        existing = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    def _upsert_metadata(self, key: str, value: str) -> None:
        self._require_conn().execute(
            """
            INSERT INTO ledger_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, _utc_now_iso()),
        )
