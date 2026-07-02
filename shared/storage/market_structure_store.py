"""Daily market-structure storage (Parquet/DuckDB).

Sister store to ``shared/storage/market_data_store.py`` for the daily
market-structure time series behind the Market Risk Score (unified investment
roadmap, Phase 0). It follows the same conventions: hive-style partitions,
``part-<uuid>.parquet`` files, idempotent replace-day writes, and DuckDB
``read_parquet(..., union_by_name = true)`` queries over naive-KST timestamps.

Rows are keyed by ``(trade_date, snapshot)``. Snapshots default to
``premarket`` (pre-open knowledge) and ``close`` (finalized after the KRX
publication cutoff); intraday provisional values are Redis-only and must never
be written here. The column schema is intentionally loose: only meta columns
are enforced so new component columns can be added over time and unioned by
name on read.

Layout::

    <parquet root>/market_structure/daily/year=YYYY/day=YYYY-MM-DD/part-<uuid>.parquet

The parquet root is shared with the market-data store
(``config/storage.yaml::market_data.parquet.root``); dataset subpath, schema
version, snapshot names, and publication cutoffs live in
``config/market_structure.yaml``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, time
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError
from shared.storage.config import StorageConfig

# Reuse the sister store's dependency guards (same package, same deps).
from shared.storage.market_data_store import _require_duckdb, _require_pandas

KST = ZoneInfo("Asia/Seoul")

_META_COLUMNS = ["trade_date", "snapshot", "asof_ts", "finalized", "schema_version"]


class MarketStructureStoreError(RuntimeError):
    """Raised when market-structure store operations fail."""


class MarketStructureStorageSettings(BaseModel):
    """Dataset location and logical schema versioning."""

    subdir: str = Field(
        default="market_structure/daily",
        description="Dataset subdirectory under the market-data parquet root",
    )
    schema_version: int = Field(
        default=1,
        ge=1,
        le=32767,
        description="Logical schema version stamped into every row (SMALLINT)",
    )

    @field_validator("subdir")
    @classmethod
    def _validate_subdir(cls, value: str) -> str:
        subdir = str(value).strip().strip("/")
        if not subdir:
            raise ValueError("storage.subdir must not be empty")
        if ".." in PurePosixPath(subdir).parts:
            raise ValueError("storage.subdir must not contain '..'")
        return subdir


class MarketStructureSnapshotSettings(BaseModel):
    """Snapshot naming, finalization defaults, and KST publication cutoffs."""

    names: list[str] = Field(
        default_factory=lambda: ["premarket", "close"],
        description="Allowed snapshot names for (trade_date, snapshot) rows",
    )
    finalized: list[str] = Field(
        default_factory=lambda: ["close"],
        description="Snapshots whose rows default to finalized=true",
    )
    cutoffs_kst: dict[str, str] = Field(
        default_factory=lambda: {"premarket": "08:00", "close": "18:40"},
        description="Publication cutoff per snapshot (KST, HH:MM)",
    )

    @field_validator("names", "finalized")
    @classmethod
    def _validate_snapshot_names(cls, value: list[str]) -> list[str]:
        names = [str(item).strip() for item in value]
        if any(not name for name in names):
            raise ValueError("snapshot names must be non-empty strings")
        if len(set(names)) != len(names):
            raise ValueError("snapshot names must be unique")
        return names

    @model_validator(mode="after")
    def _validate_membership(self) -> MarketStructureSnapshotSettings:
        if not self.names:
            raise ValueError("snapshots.names must not be empty")
        unknown_finalized = [name for name in self.finalized if name not in self.names]
        if unknown_finalized:
            raise ValueError(
                f"snapshots.finalized entries not in names: {unknown_finalized}"
            )
        unknown_cutoffs = [name for name in self.cutoffs_kst if name not in self.names]
        if unknown_cutoffs:
            raise ValueError(
                f"snapshots.cutoffs_kst entries not in names: {unknown_cutoffs}"
            )
        for name, raw in self.cutoffs_kst.items():
            try:
                time.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(
                    f"snapshots.cutoffs_kst[{name!r}] must be HH:MM, got {raw!r}"
                ) from exc
        return self

    def cutoff_time(self, snapshot: str) -> time | None:
        """Return the KST publication cutoff for a snapshot, if configured."""
        raw = self.cutoffs_kst.get(snapshot)
        if raw is None:
            return None
        return time.fromisoformat(raw)


class MarketStructureConfig(ServiceConfigBase):
    """Top-level config loaded from ``config/market_structure.yaml``."""

    _default_config_file: ClassVar[str] = "market_structure.yaml"

    storage: MarketStructureStorageSettings = Field(
        default_factory=MarketStructureStorageSettings
    )
    snapshots: MarketStructureSnapshotSettings = Field(
        default_factory=MarketStructureSnapshotSettings
    )

    @classmethod
    def load_or_default(cls, path: str | None = None) -> MarketStructureConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()


def _empty_frame() -> Any:
    pd = _require_pandas()
    return pd.DataFrame(columns=_META_COLUMNS)


def _now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _to_kst_naive(value: Any) -> datetime:
    """Coerce a timestamp to a naive-KST datetime.

    Timezone-aware inputs are converted to Asia/Seoul before dropping tzinfo;
    naive inputs are assumed to already be KST.
    """
    pd = _require_pandas()
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(KST).tz_localize(None)
    return ts.to_pydatetime()


def _coerce_day(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    pd = _require_pandas()
    return pd.Timestamp(value).date()


def _day_from_path(path: Path) -> date | None:
    name = path.parent.name
    if not name.startswith("day="):
        return None
    try:
        return date.fromisoformat(name[len("day=") :])
    except ValueError:
        return None


class ParquetMarketStructureStore:
    """(trade_date, snapshot) market-structure rows on Parquet/DuckDB."""

    def __init__(
        self,
        root: str | Path,
        *,
        config: MarketStructureConfig | None = None,
    ):
        self.root = Path(root)
        self.config = config or MarketStructureConfig()

    @property
    def dataset_dir(self) -> Path:
        """Dataset directory under the shared parquet root."""
        return self.root / Path(self.config.storage.subdir)

    # -- write ------------------------------------------------------------

    def replace_day(
        self,
        trade_date: date | datetime,
        snapshot: str,
        row: Mapping[str, Any],
    ) -> int:
        """Replace one (trade_date, snapshot) row with an idempotent write.

        Existing files for the same snapshot within the day partition are
        removed before the new file is written; other snapshots of the same
        day are untouched. There is deliberately no append API.
        """
        day = _coerce_day(trade_date)
        if day is None:
            raise MarketStructureStoreError("trade_date is required")
        self._validate_snapshot(snapshot)

        df = self._normalize_row(day, snapshot, row)

        directory = self._day_dir(day)
        if directory.exists():
            for path in sorted(directory.glob("*.parquet")):
                if self._file_holds_snapshot(path, snapshot):
                    path.unlink()

        directory.mkdir(parents=True, exist_ok=True)
        df.to_parquet(directory / f"part-{uuid4().hex}.parquet", index=False)
        return int(len(df))

    # -- read -------------------------------------------------------------

    def read_range(
        self,
        start: date | datetime | None = None,
        end: date | datetime | None = None,
        snapshot: str | None = None,
    ) -> Any:
        """Load rows for a trade-date range as a pandas DataFrame.

        ``snapshot=None`` returns both snapshots; pass ``"premarket"`` or
        ``"close"`` to restrict. Columns are unioned by name across files, so
        older files without newer component columns yield nulls.
        """
        start_day = _coerce_day(start)
        end_day = _coerce_day(end)
        if snapshot is not None:
            self._validate_snapshot(snapshot)

        files = self._files(start=start_day, end=end_day)
        if not files:
            return _empty_frame()

        conditions: list[str] = []
        params: list[Any] = [list(map(str, files))]
        if start_day is not None:
            conditions.append("trade_date >= ?")
            params.append(start_day)
        if end_day is not None:
            conditions.append("trade_date <= ?")
            params.append(end_day)
        if snapshot is not None:
            conditions.append("snapshot = ?")
            params.append(snapshot)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            "SELECT * FROM read_parquet(?, union_by_name = true,"
            " hive_partitioning = false)"
            f"{where} ORDER BY trade_date ASC, snapshot ASC"
        )
        return self._normalize_read_frame(self._fetchdf(sql, params))

    def read_latest(
        self,
        snapshot: str | None = None,
        *,
        finalized_only: bool = True,
    ) -> dict[str, Any] | None:
        """Return the most recent row as a dict, or ``None`` when absent.

        Defaults to finalized rows only (the "latest confirmed" view); pass
        ``finalized_only=False`` to include provisional snapshots such as
        ``premarket``.
        """
        if snapshot is not None:
            self._validate_snapshot(snapshot)

        files = self._files()
        if not files:
            return None

        conditions: list[str] = []
        params: list[Any] = [list(map(str, files))]
        if snapshot is not None:
            conditions.append("snapshot = ?")
            params.append(snapshot)
        if finalized_only:
            conditions.append("finalized = true")

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            "SELECT * FROM read_parquet(?, union_by_name = true,"
            " hive_partitioning = false)"
            f"{where} ORDER BY trade_date DESC, asof_ts DESC LIMIT 1"
        )
        df = self._normalize_read_frame(self._fetchdf(sql, params))
        if df.empty:
            return None

        pd = _require_pandas()
        record: dict[str, Any] = df.iloc[0].to_dict()
        asof = record.get("asof_ts")
        if isinstance(asof, pd.Timestamp):
            record["asof_ts"] = asof.to_pydatetime()
        return record

    def query(self, sql: str, params: list[Any] | None = None) -> Any:
        """Run SQL against a ``market_structure`` DuckDB view of the dataset."""
        files = self._files()
        if not files:
            raise MarketStructureStoreError(
                "market-structure dataset has no parquet files"
            )

        duckdb = _require_duckdb()
        con = duckdb.connect(database=":memory:")
        try:
            con.read_parquet(list(map(str, files)), union_by_name=True).create_view(
                "market_structure"
            )
            return con.execute(sql, params or []).fetchdf()
        finally:
            con.close()

    def dataset_manifest(self) -> dict[str, Any]:
        """Return manifest metadata for this dataset."""
        files = self._files()
        manifest: dict[str, Any] = {
            "root": str(self.dataset_dir),
            "parquet_files": len(files),
            "row_count": 0,
            "min_trade_date": None,
            "max_trade_date": None,
        }
        if not files:
            return manifest

        row = self._fetch_one(
            """
            SELECT count(*) AS row_count,
                   min(trade_date) AS min_trade_date,
                   max(trade_date) AS max_trade_date
            FROM read_parquet(?, union_by_name = true, hive_partitioning = false)
            """,
            [list(map(str, files))],
        )
        if row:
            manifest["row_count"] = int(row[0] or 0)
            manifest["min_trade_date"] = str(row[1]) if row[1] is not None else None
            manifest["max_trade_date"] = str(row[2]) if row[2] is not None else None
        return manifest

    # -- internals ----------------------------------------------------------

    def _validate_snapshot(self, snapshot: str) -> str:
        if snapshot not in self.config.snapshots.names:
            raise MarketStructureStoreError(
                f"unknown snapshot {snapshot!r};"
                f" configured snapshots: {self.config.snapshots.names}"
            )
        return snapshot

    def _normalize_row(self, day: date, snapshot: str, row: Mapping[str, Any]) -> Any:
        pd = _require_pandas()
        if not isinstance(row, Mapping):
            raise MarketStructureStoreError(
                "market-structure row must be a mapping of column values"
            )
        data = dict(row)

        provided_day = _coerce_day(data.get("trade_date"))
        if provided_day is not None and provided_day != day:
            raise MarketStructureStoreError(
                f"row trade_date {provided_day.isoformat()} does not match"
                f" replace_day target {day.isoformat()}"
            )
        provided_snapshot = data.get("snapshot")
        if provided_snapshot is not None and str(provided_snapshot) != snapshot:
            raise MarketStructureStoreError(
                f"row snapshot {provided_snapshot!r} does not match"
                f" replace_day target {snapshot!r}"
            )

        data["trade_date"] = day
        data["snapshot"] = snapshot
        asof = data.get("asof_ts")
        data["asof_ts"] = _to_kst_naive(asof) if asof is not None else _now_kst_naive()
        if data.get("finalized") is None:
            data["finalized"] = snapshot in self.config.snapshots.finalized
        if data.get("schema_version") is None:
            data["schema_version"] = self.config.storage.schema_version

        # JSON-encode structured payloads (e.g. missing_components) so their
        # parquet columns stay VARCHAR and union_by_name stays stable.
        for key, value in data.items():
            if isinstance(value, list | tuple | dict):
                data[key] = json.dumps(value, ensure_ascii=False)

        ordered = _META_COLUMNS + [key for key in data if key not in set(_META_COLUMNS)]
        df = pd.DataFrame([{key: data[key] for key in ordered}], columns=ordered)
        df["snapshot"] = df["snapshot"].astype(str)
        df["finalized"] = df["finalized"].astype(bool)
        df["schema_version"] = pd.to_numeric(
            df["schema_version"], errors="raise"
        ).astype("int16")
        return df

    def _normalize_read_frame(self, df: Any) -> Any:
        pd = _require_pandas()
        if df.empty:
            return _empty_frame()
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        df["snapshot"] = df["snapshot"].astype(str)
        return df.reset_index(drop=True)

    def _file_holds_snapshot(self, path: Path, snapshot: str) -> bool:
        pd = _require_pandas()
        try:
            frame = pd.read_parquet(path, columns=["snapshot"])
        except Exception as exc:
            raise MarketStructureStoreError(
                f"unreadable market-structure parquet file: {path}"
            ) from exc
        return snapshot in set(frame["snapshot"].astype(str))

    def _fetchdf(self, sql: str, params: list[Any]) -> Any:
        duckdb = _require_duckdb()
        con = duckdb.connect(database=":memory:")
        try:
            return con.execute(sql, params).fetchdf()
        finally:
            con.close()

    def _fetch_one(self, sql: str, params: list[Any]) -> Any:
        duckdb = _require_duckdb()
        con = duckdb.connect(database=":memory:")
        try:
            return con.execute(sql, params).fetchone()
        finally:
            con.close()

    def _files(self, start: date | None = None, end: date | None = None) -> list[Path]:
        dataset_dir = self.dataset_dir
        if not dataset_dir.exists():
            return []
        files = sorted(dataset_dir.rglob("*.parquet"))
        if start is None and end is None:
            return files

        selected: list[Path] = []
        for path in files:
            day = _day_from_path(path)
            if day is None:
                # Unknown layout: keep the file and let SQL predicates filter.
                selected.append(path)
                continue
            if start is not None and day < start:
                continue
            if end is not None and day > end:
                continue
            selected.append(path)
        return selected

    def _day_dir(self, day: date) -> Path:
        return self.dataset_dir / f"year={day.year}" / f"day={day.isoformat()}"


def create_market_structure_store(
    storage_config: StorageConfig | None = None,
    *,
    config: MarketStructureConfig | None = None,
) -> ParquetMarketStructureStore:
    """Create a market-structure store from storage + market-structure config."""
    storage = storage_config or StorageConfig.load_or_default()
    structure_config = config or MarketStructureConfig.load_or_default()
    return ParquetMarketStructureStore(
        storage.market_data.parquet.root,
        config=structure_config,
    )
