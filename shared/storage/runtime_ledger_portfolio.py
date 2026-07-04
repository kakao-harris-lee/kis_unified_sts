"""Portfolio equity and hedge-advice methods for RuntimeLedger."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .runtime_ledger_errors import RuntimeLedgerError
from .runtime_ledger_helpers import (
    _as_mapping,
    _coalesce,
    _json_payload,
    _json_safe,
    _utc_now_iso,
)


class RuntimeLedgerPortfolioMixin:
    def record_portfolio_equity_daily(self, row: Mapping[str, Any] | Any) -> str:
        data = _as_mapping(row)
        trade_date = str(_coalesce(data, "trade_date", "date") or "")
        if not trade_date:
            raise RuntimeLedgerError("portfolio equity row requires trade_date")
        now = _utc_now_iso()

        def _optional_float(*keys: str) -> float | None:
            value = _coalesce(data, *keys)
            return None if value is None else float(value)

        missing = _coalesce(data, "missing_components", default=[])
        if not isinstance(missing, str):
            missing = json.dumps(_json_safe(missing), ensure_ascii=False)

        params = (
            trade_date,
            _optional_float("track_a_equity"),
            _optional_float("track_b_equity"),
            _optional_float("track_c_equity"),
            float(_coalesce(data, "total_equity", default=0.0)),
            float(_coalesce(data, "month_start_equity", default=0.0)),
            float(_coalesce(data, "month_peak_equity", default=0.0)),
            float(_coalesce(data, "monthly_mdd_pct", default=0.0)),
            str(_coalesce(data, "stage", default="NORMAL")),
            str(_coalesce(data, "mode", default="shadow")),
            int(bool(_coalesce(data, "degraded", default=False))),
            missing,
            now,
            now,
            _json_payload(data),
        )
        with self._lock:
            self._require_conn().execute(
                """
                INSERT INTO portfolio_equity_daily (
                    trade_date, track_a_equity, track_b_equity, track_c_equity,
                    total_equity, month_start_equity, month_peak_equity,
                    monthly_mdd_pct, stage, mode, degraded, missing_components,
                    created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    track_a_equity = excluded.track_a_equity,
                    track_b_equity = excluded.track_b_equity,
                    track_c_equity = excluded.track_c_equity,
                    total_equity = excluded.total_equity,
                    month_start_equity = excluded.month_start_equity,
                    month_peak_equity = excluded.month_peak_equity,
                    monthly_mdd_pct = excluded.monthly_mdd_pct,
                    stage = excluded.stage,
                    mode = excluded.mode,
                    degraded = excluded.degraded,
                    missing_components = excluded.missing_components,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return trade_date

    def query_portfolio_equity_daily(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        sql = "SELECT * FROM portfolio_equity_daily WHERE 1=1"
        params: list[Any] = []

        if month := _coalesce(filters, "month"):
            sql += " AND substr(trade_date, 1, 7) = ?"
            params.append(str(month))
        if start := _coalesce(filters, "start", "start_date", "from"):
            sql += " AND trade_date >= ?"
            params.append(str(start))
        if end := _coalesce(filters, "end", "end_date", "to"):
            sql += " AND trade_date <= ?"
            params.append(str(end))

        sql += " ORDER BY trade_date ASC"
        limit = int(_coalesce(filters, "limit", default=0))
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def record_hedge_advice(self, row: Mapping[str, Any] | Any) -> int:
        data = _as_mapping(row)
        trade_date = str(_coalesce(data, "trade_date", "date") or "")
        if not trade_date:
            raise RuntimeLedgerError("hedge advice row requires trade_date")

        def _optional_float(*keys: str) -> float | None:
            value = _coalesce(data, *keys)
            return None if value is None else float(value)

        def _optional_int(*keys: str) -> int | None:
            value = _coalesce(data, *keys)
            return None if value is None else int(value)

        missing = _coalesce(data, "missing_components", default=[])
        if not isinstance(missing, str):
            missing = json.dumps(_json_safe(missing), ensure_ascii=False)

        params = (
            trade_date,
            str(_coalesce(data, "asof_ts", default="") or ""),
            str(_coalesce(data, "product", default="") or ""),
            int(bool(_coalesce(data, "advisory_active", default=False))),
            int(_coalesce(data, "recommended_short_contracts", default=0)),
            _optional_float("net_beta_exposure"),
            _optional_float("beta_notional"),
            _optional_float("stock_long_notional"),
            _optional_float("portfolio_beta"),
            _optional_int("futures_net_contracts"),
            _optional_float("futures_net_notional"),
            _optional_float("futures_price"),
            _optional_float("residual_exposure_after"),
            _coalesce(data, "band"),
            _optional_float("score"),
            str(_coalesce(data, "reason", default="") or ""),
            int(bool(_coalesce(data, "degraded", default=False))),
            missing,
            _utc_now_iso(),
            _json_payload(data),
        )
        with self._lock:
            cursor = self._require_conn().execute(
                """
                INSERT INTO hedge_advice (
                    trade_date, asof_ts, product, advisory_active,
                    recommended_short_contracts, net_beta_exposure,
                    beta_notional, stock_long_notional, portfolio_beta,
                    futures_net_contracts, futures_net_notional, futures_price,
                    residual_exposure_after, band, score, reason, degraded,
                    missing_components, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        return int(cursor.lastrowid or 0)

    def query_hedge_advice(
        self, filters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        sql = "SELECT * FROM hedge_advice WHERE 1=1"
        params: list[Any] = []

        if start := _coalesce(filters, "start", "start_date", "from"):
            sql += " AND trade_date >= ?"
            params.append(str(start))
        if end := _coalesce(filters, "end", "end_date", "to"):
            sql += " AND trade_date <= ?"
            params.append(str(end))

        sql += " ORDER BY row_id ASC"
        limit = int(_coalesce(filters, "limit", default=0))
        if limit > 0:
            sql += " LIMIT ?"
            params.append(limit)

        with self._lock:
            rows = self._require_conn().execute(sql, params).fetchall()
        return [self._row_to_dict(row) for row in rows]
