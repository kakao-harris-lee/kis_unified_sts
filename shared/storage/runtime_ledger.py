"""Runtime ledger interface and SQLite implementation.

The ledger stores durable operational records that must survive process
restart: orders, fills, trades, position snapshots, risk events, signal
decisions, and market context history. SQLite is the default runtime backend.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from shared.storage.config import SQLiteStorageConfig
from shared.storage.runtime_ledger_errors import RuntimeLedgerError
from shared.storage.runtime_ledger_portfolio import RuntimeLedgerPortfolioMixin
from shared.storage.runtime_ledger_predictions import RuntimeLedgerPredictionMixin
from shared.storage.runtime_ledger_records import RuntimeLedgerRecordMixin
from shared.storage.runtime_ledger_schema import RuntimeLedgerSchemaMixin


class RuntimeLedger(Protocol):
    """Durable runtime ledger contract.

    ``track_id`` tags rows with the unified-portfolio track ("A" core /
    "B" stock / "C" futures — see ``shared.portfolio.config``). It is
    optional everywhere: omitted (None) keeps legacy callers unchanged and
    leaves the column NULL. When None, implementations fall back to a
    ``track_id`` key in the record mapping itself.
    """

    def record_order(
        self, order: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
        """Record an order submission/router decision and return record id."""
        ...

    def record_fill(
        self, fill: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
        """Record a broker/mock fill and return record id."""
        ...

    def record_trade(
        self, trade: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
        """Record a closed trade summary and return record id."""
        ...

    def record_position_snapshot(self, snapshot: Mapping[str, Any] | Any) -> int:
        """Record an open/closed position state snapshot and return row id."""
        ...

    def record_risk_event(self, event: Mapping[str, Any] | Any) -> str:
        """Record an operational risk/audit event and return record id."""
        ...

    def record_signal_decision(
        self, decision: Mapping[str, Any] | Any, *, track_id: str | None = None
    ) -> str:
        """Record generated/filtered/vetoed signal history and return record id."""
        ...

    def record_market_context(self, context: Mapping[str, Any] | Any) -> str:
        """Record an LLM/market context snapshot and return record id."""
        ...

    def save_prediction(
        self,
        date_kst: str,
        facet: str,
        captured_at: str,
        payload: dict,
        confidence: float | None,
    ) -> None:
        """Idempotent upsert of an LLM prediction (per date_kst+facet)."""
        ...

    def load_predictions(self, date_kst: str) -> list[dict]:
        """Return all LLM predictions recorded for the given trading date (KST)."""
        ...

    def query_predictions(
        self,
        facet: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Query LLM predictions with optional facet and date range filters."""
        ...

    def save_score(self, s: dict) -> None:
        """Idempotent upsert of a prediction score (per date_kst+facet)."""
        ...

    def query_scores(
        self,
        facet: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Query prediction scores with optional facet and date range filters."""
        ...

    def load_open_positions(
        self, asset_class: str | None = None
    ) -> list[dict[str, Any]]:
        """Load latest open position snapshots."""
        ...

    def query_position_snapshots_daily(
        self,
        asset_class: str | None = None,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Latest position snapshot per (position_id, day) for exposure history."""
        ...

    def query_trades(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Query closed trades by common filters.

        Supported filter keys: ``asset_class``, ``symbol``/``code``,
        ``strategy``, ``side``, ``track_id``/``track``, ``start``, ``end``,
        ``limit``. Per-track realized-PnL aggregation filters on ``track_id``.
        """
        ...

    def query_fills(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Query order fills by common filters.

        Supported filter keys: ``asset_class``, ``symbol``/``code``,
        ``side``, ``order_id``, ``track_id``/``track``, ``start``, ``end``,
        ``limit``.
        """
        ...

    def record_portfolio_equity_daily(self, row: Mapping[str, Any] | Any) -> str:
        """Upsert one daily portfolio-equity row (Phase 3B monitor).

        Keyed by ``trade_date`` (KST ``YYYY-MM-DD``) — same-day re-runs
        replace the row idempotently. Returns the trade date.
        """
        ...

    def query_portfolio_equity_daily(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Query daily portfolio-equity rows ordered by trade date ASC.

        Supported filter keys: ``month`` (``YYYY-MM``), ``start``, ``end``
        (trade-date bounds), ``limit`` (0 disables).
        """
        ...

    def record_hedge_advice(self, row: Mapping[str, Any] | Any) -> int:
        """Append one hedge-advisory history row (Phase 4A, advisory only).

        Rows are appended ONLY on advisory_active transitions or recommended
        contract-count changes (dedup is the caller's contract). Returns the
        inserted row id.
        """
        ...

    def query_hedge_advice(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Query hedge-advisory history ordered by row id ASC.

        Supported filter keys: ``start``, ``end`` (trade-date bounds),
        ``limit`` (0 disables).
        """
        ...

    def flush(self) -> None:
        """Flush pending writes."""
        ...

    def close(self) -> None:
        """Close the ledger backend."""
        ...


class SQLiteRuntimeLedger(
    RuntimeLedgerSchemaMixin,
    RuntimeLedgerRecordMixin,
    RuntimeLedgerPortfolioMixin,
    RuntimeLedgerPredictionMixin,
):
    """SQLite WAL runtime ledger implementation."""

    # v3: adds the portfolio_equity_daily table (Phase 3B unified MDD monitor).
    # v4: adds the hedge_advice history table (Phase 4A hedge advisor —
    #     advisory only; rows appended on advisory transitions/changes).
    SCHEMA_VERSION = "4"

    # Tables carrying the unified-portfolio track tag (schema v2). Existing
    # databases are migrated in place via idempotent ALTER TABLE ADD COLUMN;
    # pre-migration rows keep track_id NULL (no retroactive tagging).
    _TRACK_TAGGED_TABLES = ("orders", "fills", "trades", "signal_decisions")

    def __init__(self, path: str | Path | SQLiteStorageConfig):
        if isinstance(path, SQLiteStorageConfig):
            self.config = path
            self.path = Path(path.path)
        else:
            self.path = Path(path)
            self.config = SQLiteStorageConfig(path=str(self.path))

        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._connect()

    def _connect(self) -> None:
        try:
            if self.path.exists() and self.path.is_dir():
                raise RuntimeLedgerError(
                    f"SQLite ledger path is a directory: {self.path}"
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            self._initialize_connection()
            self._migrate()
        except RuntimeLedgerError:
            raise
        except Exception as exc:
            raise RuntimeLedgerError(
                f"Failed to open SQLite runtime ledger at {self.path}: {exc}"
            ) from exc

    def _initialize_connection(self) -> None:
        conn = self._require_conn()
        conn.execute(f"PRAGMA busy_timeout={self.config.busy_timeout_ms}")
        conn.execute("PRAGMA foreign_keys=ON")
        if self.config.wal:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA synchronous={self.config.synchronous}")

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeLedgerError("SQLite runtime ledger is closed")
        return self._conn

    def flush(self) -> None:
        with self._lock:
            self._require_conn().commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.commit()
                self._conn.close()
                self._conn = None

    def __enter__(self) -> SQLiteRuntimeLedger:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
