"""Market-data storage interfaces and Parquet/DuckDB implementation.

Runtime services can keep using Redis/KIS fallbacks, while backtest and ML
paths can choose a serverless Parquet dataset instead of requiring ClickHouse.
ClickHouse adapters stay behind this module so callers can switch by config.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

import yaml

from shared.storage.config import MarketDataStorageConfig, StorageConfig

AssetClass = Literal["stock", "futures"]
Timeframe = Literal["minute", "daily"]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BAR_COLUMNS = ["code", "datetime", "open", "high", "low", "close", "volume"]


class MarketDataStoreError(RuntimeError):
    """Raised when market-data store operations fail."""


class MarketDataStore(Protocol):
    """Historical OHLCV backend contract."""

    def get_minute_bars(
        self,
        symbol: str,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int | None = None,
    ) -> "Any":
        """Load minute bars as a pandas DataFrame."""
        ...

    def get_daily_bars(
        self,
        symbol: str,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int | None = None,
    ) -> "Any":
        """Load daily bars as a pandas DataFrame."""
        ...

    def append_minute_bars(self, rows: Iterable[Mapping[str, Any]] | "Any") -> int:
        """Append minute bars and return the row count written."""
        ...

    def append_daily_bars(self, rows: Iterable[Mapping[str, Any]] | "Any") -> int:
        """Append daily bars and return the row count written."""
        ...

    def dataset_manifest(self) -> dict[str, Any]:
        """Return manifest metadata for this dataset."""
        ...


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - pandas is a core dependency.
        raise MarketDataStoreError(
            "pandas is required for market-data storage"
        ) from exc
    return pd


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - exercised without dependency.
        raise MarketDataStoreError(
            "duckdb is required for Parquet market-data queries"
        ) from exc
    return duckdb


def _empty_frame():
    pd = _require_pandas()
    return pd.DataFrame(columns=_BAR_COLUMNS)


def _normalize_frame(rows: Iterable[Mapping[str, Any]] | "Any") -> "Any":
    pd = _require_pandas()
    if hasattr(rows, "copy") and hasattr(rows, "columns"):
        df = rows.copy()
    else:
        df = pd.DataFrame(list(rows))

    if df.empty:
        return _empty_frame()

    rename_map = {}
    if "symbol" in df.columns and "code" not in df.columns:
        rename_map["symbol"] = "code"
    if "timestamp" in df.columns and "datetime" not in df.columns:
        rename_map["timestamp"] = "datetime"
    if "date" in df.columns and "datetime" not in df.columns:
        rename_map["date"] = "datetime"
    if rename_map:
        df = df.rename(columns=rename_map)

    missing = [column for column in _BAR_COLUMNS if column not in df.columns]
    if missing:
        raise MarketDataStoreError(
            f"market-data rows missing required columns: {', '.join(missing)}"
        )

    df = df[_BAR_COLUMNS].copy()
    df["code"] = df["code"].astype(str)
    df["datetime"] = pd.to_datetime(df["datetime"])
    for column in ("open", "high", "low", "close"):
        df[column] = pd.to_numeric(df[column], errors="raise")
    df["volume"] = pd.to_numeric(df["volume"], errors="raise").astype("int64")
    return df.sort_values("datetime").reset_index(drop=True)


def _normalize_boundary(value: date | datetime | None, *, end: bool = False) -> Any:
    if value is None:
        return None

    pd = _require_pandas()
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    elif isinstance(value, date) and not isinstance(value, datetime):
        ts = ts + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else ts
    return ts.to_pydatetime()


def _validate_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value or ""):
        raise MarketDataStoreError(f"Invalid {label}: {value!r}")
    return value


class ParquetMarketDataStore:
    """File-based market-data store queried through DuckDB."""

    def __init__(
        self,
        root: str | Path,
        *,
        asset_class: AssetClass = "stock",
    ):
        self.root = Path(root)
        self.asset_class = asset_class

    def get_minute_bars(
        self,
        symbol: str,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int | None = None,
    ) -> "Any":
        return self._query_bars("minute", symbol, start=start, end=end, limit=limit)

    def get_daily_bars(
        self,
        symbol: str,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int | None = None,
    ) -> "Any":
        return self._query_bars("daily", symbol, start=start, end=end, limit=limit)

    def append_minute_bars(self, rows: Iterable[Mapping[str, Any]] | "Any") -> int:
        return self._append_bars("minute", rows)

    def append_daily_bars(self, rows: Iterable[Mapping[str, Any]] | "Any") -> int:
        return self._append_bars("daily", rows)

    def dataset_manifest(self) -> dict[str, Any]:
        manifest_path = self.root / "manifest.yaml"
        if manifest_path.exists():
            loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                return loaded

        files = list(self.root.rglob("*.parquet"))
        manifest: dict[str, Any] = {
            "root": str(self.root),
            "parquet_files": len(files),
            "row_count": 0,
            "min_datetime": None,
            "max_datetime": None,
        }
        if not files:
            return manifest

        duckdb = _require_duckdb()
        con = duckdb.connect(database=":memory:")
        try:
            row = con.execute(
                """
                SELECT count(*) AS row_count,
                       min(datetime) AS min_datetime,
                       max(datetime) AS max_datetime
                FROM read_parquet(?, union_by_name = true, hive_partitioning = true)
                """,
                [list(map(str, files))],
            ).fetchone()
        finally:
            con.close()

        if row:
            manifest["row_count"] = int(row[0] or 0)
            manifest["min_datetime"] = str(row[1]) if row[1] is not None else None
            manifest["max_datetime"] = str(row[2]) if row[2] is not None else None
        return manifest

    def _query_bars(
        self,
        timeframe: Timeframe,
        symbol: str,
        *,
        start: date | datetime | None,
        end: date | datetime | None,
        limit: int | None,
    ) -> "Any":
        files = self._files(timeframe, symbol)
        if not files:
            return _empty_frame()

        conditions = ["code = ?"]
        params: list[Any] = [list(map(str, files)), symbol]

        start_value = _normalize_boundary(start)
        if start_value is not None:
            conditions.append("datetime >= ?")
            params.append(start_value)

        end_value = _normalize_boundary(end, end=True)
        if end_value is not None:
            conditions.append("datetime <= ?")
            params.append(end_value)

        sql = f"""
            SELECT code, datetime, open, high, low, close, volume
            FROM read_parquet(?, union_by_name = true, hive_partitioning = true)
            WHERE {" AND ".join(conditions)}
            ORDER BY datetime ASC
        """
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params.append(int(limit))

        duckdb = _require_duckdb()
        con = duckdb.connect(database=":memory:")
        try:
            df = con.execute(sql, params).fetchdf()
        finally:
            con.close()
        return _normalize_frame(df)

    def _append_bars(
        self,
        timeframe: Timeframe,
        rows: Iterable[Mapping[str, Any]] | "Any",
    ) -> int:
        df = _normalize_frame(rows)
        if df.empty:
            return 0

        dt = df["datetime"]
        for (code, year, month), group in df.groupby(
            [df["code"], dt.dt.year, dt.dt.month],
            sort=True,
        ):
            directory = self._partition_dir(
                timeframe,
                code=str(code),
                year=int(year),
                month=int(month),
            )
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"part-{uuid4().hex}.parquet"
            group[_BAR_COLUMNS].to_parquet(path, index=False)
        return int(len(df))

    def _files(self, timeframe: Timeframe, symbol: str) -> list[Path]:
        symbol_dir = self.root / self.asset_class / timeframe / f"code={symbol}"
        if symbol_dir.exists():
            return sorted(symbol_dir.rglob("*.parquet"))

        dataset_dir = self.root / self.asset_class / timeframe
        if not dataset_dir.exists():
            return []
        return sorted(dataset_dir.rglob("*.parquet"))

    def _partition_dir(
        self,
        timeframe: Timeframe,
        *,
        code: str,
        year: int,
        month: int,
    ) -> Path:
        base = (
            self.root / self.asset_class / timeframe / f"code={code}" / f"year={year}"
        )
        if timeframe == "daily":
            return base
        return base / f"month={month:02d}"


class ClickHouseMarketDataStore:
    """ClickHouse-backed adapter kept explicit for research/rollback paths."""

    def __init__(
        self,
        *,
        asset_class: AssetClass = "stock",
        stock_database: str = "market",
        futures_database: str = "kospi",
        futures_table: str | None = None,
    ):
        self.asset_class = asset_class
        self.stock_database = _validate_identifier(stock_database, "stock database")
        self.futures_database = _validate_identifier(
            futures_database, "futures database"
        )
        self.futures_table = (
            _validate_identifier(futures_table, "futures table")
            if futures_table
            else None
        )

    def get_minute_bars(
        self,
        symbol: str,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int | None = None,
    ) -> "Any":
        start_date = _date_only(start)
        end_date = _date_only(end)
        if self.asset_class == "futures":
            from shared.collector.historical import load_futures_minute_from_clickhouse

            df = load_futures_minute_from_clickhouse(
                symbol,
                start_date,
                end_date,
                table_name=self.futures_table,
            )
        else:
            from shared.collector.historical.stock import (
                load_stock_minute_from_clickhouse,
            )

            df = load_stock_minute_from_clickhouse(symbol, start_date, end_date)
        return _limit_frame(df, limit)

    def get_daily_bars(
        self,
        symbol: str,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        limit: int | None = None,
    ) -> "Any":
        if self.asset_class != "stock":
            raise MarketDataStoreError(
                "daily ClickHouse adapter currently supports stock only"
            )
        from shared.backtest.daily_adapter import load_stock_daily_from_clickhouse

        df = load_stock_daily_from_clickhouse(
            symbol, _date_only(start), _date_only(end)
        )
        return _limit_frame(df, limit)

    def append_minute_bars(self, rows: Iterable[Mapping[str, Any]] | "Any") -> int:
        raise MarketDataStoreError(
            "ClickHouseMarketDataStore append is not implemented"
        )

    def append_daily_bars(self, rows: Iterable[Mapping[str, Any]] | "Any") -> int:
        raise MarketDataStoreError(
            "ClickHouseMarketDataStore append is not implemented"
        )

    def dataset_manifest(self) -> dict[str, Any]:
        return {
            "source": "clickhouse",
            "asset_class": self.asset_class,
            "stock_database": self.stock_database,
            "futures_database": self.futures_database,
            "futures_table": self.futures_table,
        }


def _date_only(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _limit_frame(df: "Any", limit: int | None) -> "Any":
    if limit is not None and limit > 0:
        return df.head(int(limit)).reset_index(drop=True)
    return df


def create_market_data_store(
    config: MarketDataStorageConfig | StorageConfig | None = None,
    *,
    asset_class: AssetClass = "stock",
    futures_table: str | None = None,
) -> MarketDataStore:
    """Create a market-data store from storage configuration."""
    if config is None:
        market_config = StorageConfig.load_or_default().market_data
    elif isinstance(config, StorageConfig):
        market_config = config.market_data
    else:
        market_config = config

    if market_config.source == "clickhouse":
        return ClickHouseMarketDataStore(
            asset_class=asset_class,
            stock_database=market_config.clickhouse.stock_database,
            futures_database=market_config.clickhouse.futures_database,
            futures_table=futures_table,
        )
    return ParquetMarketDataStore(market_config.parquet.root, asset_class=asset_class)


def load_market_bars_for_backtest(
    *,
    symbol: str,
    asset_class: AssetClass,
    timeframe: str = "minute",
    start: date | datetime | None = None,
    end: date | datetime | None = None,
    config: StorageConfig | None = None,
    futures_table: str | None = None,
) -> "Any":
    """Load configured market data for backtest symbol mode."""
    store = create_market_data_store(
        config,
        asset_class=asset_class,
        futures_table=futures_table,
    )
    if timeframe == "daily":
        return store.get_daily_bars(symbol, start=start, end=end)
    return store.get_minute_bars(symbol, start=start, end=end)
