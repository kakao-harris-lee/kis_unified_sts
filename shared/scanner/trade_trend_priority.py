"""Trade-trend based priority adjustment for stock screeners.

This module only adjusts candidate ordering. It must not decide whether a
candidate is tradable, and it intentionally fails open when macro data is
missing, stale, or malformed.
"""

from __future__ import annotations

import json
import logging
import math
import time
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPORTED_SUFFIXES = {".parquet", ".json", ".jsonl", ".csv"}

_SECTOR_COLUMNS = (
    "sector",
    "theme",
    "industry",
    "category",
    "item",
    "hs_name",
    "product",
)
_SYMBOL_COLUMNS = ("code", "symbol", "ticker")
_SCORE_COLUMNS = (
    "trade_trend_score",
    "priority_score",
    "sector_score",
    "symbol_score",
    "score",
)
_EXPORT_YOY_COLUMNS = (
    "export_yoy_pct",
    "exports_yoy_pct",
    "export_growth_yoy_pct",
    "exp_yoy_pct",
)
_EXPORT_MOM_COLUMNS = (
    "export_mom_pct",
    "exports_mom_pct",
    "export_mo_m_pct",
    "exp_mom_pct",
)
_IMPORT_YOY_COLUMNS = (
    "import_yoy_pct",
    "imports_yoy_pct",
    "import_growth_yoy_pct",
    "imp_yoy_pct",
)
_BALANCE_YOY_COLUMNS = (
    "trade_balance_yoy_pct",
    "balance_yoy_pct",
    "surplus_yoy_pct",
)
_DATE_COLUMNS = (
    "as_of_date",
    "published_at",
    "publication_date",
    "revision_date",
    "date",
    "period",
    "yyyymm",
    "month",
)


class TradeTrendPriorityConfig(ServiceConfigBase):
    """Configuration for trade-trend priority adjustment."""

    _default_config_file: ClassVar[str] = "trade_trend_priority.yaml"

    enabled: bool = Field(default=True)
    snapshot_path: str = Field(default="data/macro/trade_trends/latest.parquet")
    cache_seconds: int = Field(default=3600, ge=0)
    stale_after_days: int = Field(default=75, ge=0)
    max_bonus: float = Field(default=0.15, ge=0.0)
    pct_scale: float = Field(default=20.0, gt=0.0)
    export_yoy_weight: float = Field(default=0.7)
    export_mom_weight: float = Field(default=0.2)
    import_yoy_weight: float = Field(default=-0.1)
    balance_yoy_weight: float = Field(default=0.0)
    symbol_sectors: dict[str, list[str]] = Field(default_factory=dict)
    sector_aliases: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def load_or_default(cls) -> "TradeTrendPriorityConfig":
        try:
            return cls.from_yaml()
        except ConfigNotFoundError:
            logger.debug("trade trend priority config not found; feature disabled")
            return cls(enabled=False)


@dataclass(frozen=True)
class TradeTrendSnapshot:
    """Normalized trade-trend score snapshot."""

    status: str
    source_path: str = ""
    as_of_date: date | None = None
    sector_scores: dict[str, float] | None = None
    symbol_scores: dict[str, float] | None = None
    sector_details: dict[str, dict[str, Any]] | None = None
    symbol_details: dict[str, dict[str, Any]] | None = None
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.status == "loaded" and (
            bool(self.sector_scores) or bool(self.symbol_scores)
        )


@dataclass(frozen=True)
class TradeTrendRankResult:
    codes: list[str]
    scores: dict[str, float]
    metadata: dict[str, dict[str, Any]]
    summary: dict[str, Any]


def _resolve_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = _REPO_ROOT / resolved
    return resolved


def _latest_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    if not path.is_dir():
        return None

    candidates = [
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in _SUPPORTED_SUFFIXES
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _read_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        frame = pd.read_parquet(path)
        return frame.to_dict(orient="records")
    if suffix == ".csv":
        frame = pd.read_csv(path)
        return frame.to_dict(orient="records")
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
        return rows
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return _json_payload_to_records(payload)
    return []


def _json_payload_to_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("rows", "records", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            base = {
                date_key: payload.get(date_key)
                for date_key in _DATE_COLUMNS
                if payload.get(date_key) is not None
            }
            records = []
            for item in value:
                if isinstance(item, dict):
                    records.append({**base, **item})
            return records

    records: list[dict[str, Any]] = []
    for key, score_key in (
        ("sector_scores", "sector"),
        ("symbol_scores", "code"),
    ):
        scores = payload.get(key)
        if not isinstance(scores, dict):
            continue
        for name, score in scores.items():
            row = {score_key: name, "trade_trend_score": score}
            for date_key in _DATE_COLUMNS:
                if payload.get(date_key) is not None:
                    row[date_key] = payload[date_key]
            records.append(row)
    return records


def _value(row: dict[str, Any], columns: tuple[str, ...]) -> Any:
    for column in columns:
        value = row.get(column)
        if value is not None and value != "":
            return value
    return None


def _float_value(row: dict[str, Any], columns: tuple[str, ...]) -> float | None:
    value = _value(row, columns)
    if value is None:
        return None
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _normalize_token(value: Any, aliases: dict[str, str]) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    key = token.lower()
    return aliases.get(token, aliases.get(key, key))


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        try:
            return datetime.strptime(digits[:8], "%Y%m%d").date()
        except ValueError:
            pass
    if len(digits) == 6:
        try:
            year = int(digits[:4])
            month = int(digits[4:6])
            return date(year, month, monthrange(year, month)[1])
        except ValueError:
            pass

    date_part = text.replace("/", "-").split("T", maxsplit=1)[0].split()[0]
    if len(date_part) >= 10:
        try:
            return datetime.strptime(date_part[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    if len(date_part) >= 7:
        try:
            parsed = datetime.strptime(date_part[:7], "%Y-%m")
            last_day = monthrange(parsed.year, parsed.month)[1]
            return date(parsed.year, parsed.month, last_day)
        except ValueError:
            pass
    return None


def _latest_record_date(records: list[dict[str, Any]]) -> date | None:
    latest: date | None = None
    for row in records:
        for column in _DATE_COLUMNS:
            parsed = _parse_date(row.get(column))
            if parsed and (latest is None or parsed > latest):
                latest = parsed
    return latest


def _score_from_row(row: dict[str, Any], config: TradeTrendPriorityConfig) -> float:
    explicit = _float_value(row, _SCORE_COLUMNS)
    if explicit is not None:
        return max(min(explicit, 1.0), -1.0)

    export_yoy = _float_value(row, _EXPORT_YOY_COLUMNS) or 0.0
    export_mom = _float_value(row, _EXPORT_MOM_COLUMNS) or 0.0
    import_yoy = _float_value(row, _IMPORT_YOY_COLUMNS) or 0.0
    balance_yoy = _float_value(row, _BALANCE_YOY_COLUMNS) or 0.0

    raw = (
        config.export_yoy_weight * export_yoy
        + config.export_mom_weight * export_mom
        + config.import_yoy_weight * import_yoy
        + config.balance_yoy_weight * balance_yoy
    ) / config.pct_scale
    return max(min(raw, 1.0), -1.0)


def load_trade_trend_snapshot(
    config: TradeTrendPriorityConfig,
    *,
    today: date | None = None,
) -> TradeTrendSnapshot:
    """Load and normalize a trade-trend snapshot from configured storage."""
    if not config.enabled:
        return TradeTrendSnapshot(status="disabled", reason="disabled")

    source = _latest_file(_resolve_path(config.snapshot_path))
    if source is None:
        return TradeTrendSnapshot(
            status="missing",
            source_path=str(_resolve_path(config.snapshot_path)),
            reason="snapshot_missing",
        )

    try:
        records = _read_records(source)
    except Exception as exc:  # noqa: BLE001 - fail-open runtime path
        logger.warning("Failed to load trade trend snapshot %s: %s", source, exc)
        return TradeTrendSnapshot(
            status="error", source_path=str(source), reason=type(exc).__name__
        )

    if not records:
        return TradeTrendSnapshot(
            status="empty", source_path=str(source), reason="empty_snapshot"
        )

    as_of = _latest_record_date(records)
    today = today or date.today()
    if (
        as_of is not None
        and config.stale_after_days > 0
        and (today - as_of).days > config.stale_after_days
    ):
        return TradeTrendSnapshot(
            status="stale",
            source_path=str(source),
            as_of_date=as_of,
            reason=f"stale_after_{config.stale_after_days}_days",
        )

    sector_scores: dict[str, float] = {}
    symbol_scores: dict[str, float] = {}
    sector_details: dict[str, dict[str, Any]] = {}
    symbol_details: dict[str, dict[str, Any]] = {}

    for row in records:
        score = _score_from_row(row, config)
        sector = _normalize_token(_value(row, _SECTOR_COLUMNS), config.sector_aliases)
        symbol = str(_value(row, _SYMBOL_COLUMNS) or "").strip()
        detail = {
            "score": round(score, 6),
            "source_path": str(source),
        }
        row_date = _latest_record_date([row])
        if row_date:
            detail["as_of_date"] = row_date.isoformat()

        if sector:
            if sector not in sector_scores or score > sector_scores[sector]:
                sector_scores[sector] = score
                sector_details[sector] = dict(detail)
        if symbol:
            if symbol not in symbol_scores or score > symbol_scores[symbol]:
                symbol_scores[symbol] = score
                symbol_details[symbol] = dict(detail)

    status = "loaded" if sector_scores or symbol_scores else "empty"
    return TradeTrendSnapshot(
        status=status,
        source_path=str(source),
        as_of_date=as_of,
        sector_scores=sector_scores,
        symbol_scores=symbol_scores,
        sector_details=sector_details,
        symbol_details=symbol_details,
        reason="" if status == "loaded" else "no_scores",
    )


class TradeTrendPriorityRanker:
    """Cached priority ranker for screener loops."""

    def __init__(self, config: TradeTrendPriorityConfig | None = None) -> None:
        self.config = config or TradeTrendPriorityConfig.load_or_default()
        self._snapshot: TradeTrendSnapshot | None = None
        self._loaded_at: float = 0.0

    @classmethod
    def from_default_config(cls) -> "TradeTrendPriorityRanker":
        return cls(TradeTrendPriorityConfig.load_or_default())

    def snapshot(self) -> TradeTrendSnapshot:
        now = time.time()
        if (
            self._snapshot is None
            or self.config.cache_seconds <= 0
            or now - self._loaded_at >= self.config.cache_seconds
        ):
            self._snapshot = load_trade_trend_snapshot(self.config)
            self._loaded_at = now
        return self._snapshot

    def rank_codes(
        self,
        codes: list[str],
        base_scores: dict[str, float] | None = None,
    ) -> TradeTrendRankResult:
        """Return codes ordered by base score plus bounded trade-trend bonus."""
        if not codes:
            return TradeTrendRankResult([], {}, {}, self.summary())

        if base_scores is None:
            count = len(codes)
            base_scores = {
                code: (count - idx) / max(1, count) for idx, code in enumerate(codes)
            }

        snapshot = self.snapshot()
        if not snapshot.available or self.config.max_bonus <= 0:
            ordered_scores = {code: float(base_scores.get(code, 0.0)) for code in codes}
            return TradeTrendRankResult(
                codes=list(codes),
                scores=ordered_scores,
                metadata={},
                summary=self.summary(snapshot),
            )

        metadata: dict[str, dict[str, Any]] = {}
        adjusted_scores: dict[str, float] = {}
        original_index = {code: idx for idx, code in enumerate(codes)}

        for code in codes:
            base = float(base_scores.get(code, 0.0) or 0.0)
            priority_score, matched_sector, detail = self._score_for_code(
                code, snapshot
            )
            bonus = priority_score * self.config.max_bonus
            adjusted = base + bonus
            adjusted_scores[code] = adjusted
            if priority_score != 0.0:
                metadata[code] = {
                    "trade_trend_priority": {
                        "score": round(priority_score, 6),
                        "bonus": round(bonus, 6),
                        "base_score": round(base, 6),
                        "adjusted_score": round(adjusted, 6),
                        "matched_sector": matched_sector,
                        **detail,
                    }
                }

        ranked_codes = sorted(
            codes,
            key=lambda code: (
                adjusted_scores.get(code, 0.0),
                -original_index.get(code, 0),
            ),
            reverse=True,
        )
        return TradeTrendRankResult(
            codes=ranked_codes,
            scores=adjusted_scores,
            metadata=metadata,
            summary=self.summary(snapshot),
        )

    def rank_watchlists(
        self, watchlists: dict[str, list[str]]
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]], dict[str, Any]]:
        ranked: dict[str, list[str]] = {}
        merged_metadata: dict[str, dict[str, Any]] = {}
        summary: dict[str, Any] = self.summary()

        for name, codes in watchlists.items():
            result = self.rank_codes(list(codes))
            ranked[name] = result.codes
            summary = result.summary
            for code, metadata in result.metadata.items():
                current = merged_metadata.setdefault(code, {})
                current.update(metadata)
        return ranked, merged_metadata, summary

    def _score_for_code(
        self,
        code: str,
        snapshot: TradeTrendSnapshot,
    ) -> tuple[float, str, dict[str, Any]]:
        symbol_scores = snapshot.symbol_scores or {}
        if code in symbol_scores:
            detail = dict((snapshot.symbol_details or {}).get(code, {}))
            return symbol_scores[code], "", detail

        best_score = 0.0
        best_sector = ""
        best_detail: dict[str, Any] = {}
        sectors = self.config.symbol_sectors.get(code, [])
        for raw_sector in sectors:
            sector = _normalize_token(raw_sector, self.config.sector_aliases)
            if not sector:
                continue
            score = (snapshot.sector_scores or {}).get(sector, 0.0)
            if abs(score) > abs(best_score):
                best_score = score
                best_sector = sector
                best_detail = dict((snapshot.sector_details or {}).get(sector, {}))
        return best_score, best_sector, best_detail

    def summary(self, snapshot: TradeTrendSnapshot | None = None) -> dict[str, Any]:
        snapshot = snapshot or self._snapshot
        if snapshot is None:
            return {"enabled": bool(self.config.enabled), "status": "not_loaded"}
        return {
            "enabled": bool(self.config.enabled),
            "status": snapshot.status,
            "reason": snapshot.reason,
            "source_path": snapshot.source_path,
            "as_of_date": (
                snapshot.as_of_date.isoformat() if snapshot.as_of_date else None
            ),
            "sector_count": len(snapshot.sector_scores or {}),
            "symbol_count": len(snapshot.symbol_scores or {}),
            "max_bonus": self.config.max_bonus,
        }
