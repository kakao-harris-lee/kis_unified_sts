#!/usr/bin/env python3
"""Daily stock paper-trading verification gate.

The report checks the live stock paper path end-to-end:

1. ClickHouse closed-trade records in ``market.stock_trades``.
2. Redis trading-state lists/hashes for status, signals, trades, positions.
3. Redis stock pipeline inputs used by the orchestrator: trade targets,
   universe, daily indicators, and data freshness.
4. Objective metrics: upward equity curve, monthly expected return,
   win rate, max drawdown, and fast same-symbol re-entry churn.

Designed for after-close cron. Exit codes:
  0 = PASS, 1 = FAIL/WARN gate issues, 2 = script error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

KST = ZoneInfo("Asia/Seoul")
CONFIG_PATH = "stock_paper_verification.yaml"


@dataclass(frozen=True)
class VerificationConfig:
    output_dir: Path
    lookback_days: int
    monthly_trading_days: int
    initial_capital: float
    notify_on_issues: bool
    min_daily_signals: int
    min_closed_trades_for_metric_gate: int
    min_monthly_expected_return_pct: float
    min_win_rate_pct: float
    target_win_rate_max_pct: float
    max_mdd_pct: float
    require_positive_equity_slope: bool
    max_reentry_churn_count: int
    reentry_churn_seconds: int
    min_fresh_ratio: float
    require_redis_status: bool
    max_redis_status_age_seconds: float
    require_trade_targets: bool
    require_daily_indicators: bool
    skip_live_redis_gates_on_non_trading_day: bool
    clickhouse_database: str
    clickhouse_table: str
    clickhouse_position_table: str
    redis_keys: dict[str, str]


@dataclass(frozen=True)
class TradeRow:
    id: str
    code: str
    name: str
    strategy: str
    side: str
    entry_date: datetime
    entry_price: float
    exit_date: datetime
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    hold_seconds: int
    exit_reason: str


@dataclass
class TradeMetrics:
    trade_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_pnl_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float | None = None
    realized_return_pct: float = 0.0
    monthly_expected_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    equity_slope_krw_per_trade: float = 0.0
    equity_is_upward: bool = False
    reentry_churn_count: int = 0
    by_strategy: dict[str, dict[str, float]] = field(default_factory=dict)
    by_exit_reason: dict[str, int] = field(default_factory=dict)


@dataclass
class RedisSnapshot:
    report_is_trading_day: bool
    status_exists: bool
    status_ttl_seconds: int
    status_age_seconds: float | None
    status_updated_at: str | None
    status_publisher_pid: str | None
    state: str
    status_config_capital: float | None
    risk_initial_capital: float | None
    configured_symbols: int
    data_provider: dict[str, Any]
    data_freshness: dict[str, Any]
    daily_signal_count: int
    signals_list_len: int
    trades_list_len: int
    open_positions_count: int
    candle_cache_symbols: int
    trade_targets_exists: bool
    trade_targets_count: int
    universe_exists: bool
    universe_count: int
    daily_indicators_exists: bool
    daily_indicators_count: int
    daily_strategy_candidate_count: int
    daily_strategy_counts: dict[str, int]


@dataclass
class ClickHousePositionSnapshot:
    open_positions_count: int = 0
    open_position_samples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GateIssue:
    severity: str
    code: str
    observed: str
    expected: str
    detail: str


@dataclass
class VerificationReport:
    report_date: str
    window_start: str
    window_end: str
    generated_at: str
    verdict: str
    source_errors: list[str]
    issues: list[GateIssue]
    trade_metrics: TradeMetrics
    active_strategy_names: list[str]
    active_daily_strategy_names: list[str]
    active_daily_candidate_count: int
    active_trade_metrics: TradeMetrics
    active_issues: list[GateIssue]
    redis_snapshot: RedisSnapshot
    clickhouse_position_snapshot: ClickHousePositionSnapshot
    json_path: str = ""
    markdown_path: str = ""
    notification_sent: bool = False


def _load_repo_env() -> None:
    """Load repo-local .env for standalone verifier runs.

    Cron wrappers already source .env, but manual invocations should use the
    same credentials/config without requiring the operator to export variables.
    Existing environment values win, matching python-dotenv's default
    ``override=False`` behavior.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        try:
            parts = shlex.split(raw_value, comments=False, posix=True)
            value = parts[0] if parts else ""
        except ValueError:
            value = raw_value.strip().strip("'\"")
        os.environ[key] = value


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _maybe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _load_config() -> VerificationConfig:
    from shared.config.loader import ConfigLoader

    raw = ConfigLoader.load(CONFIG_PATH, use_cache=False)
    report = raw.get("report", {})
    targets = raw.get("targets", {})
    clickhouse = raw.get("clickhouse", {})
    redis_cfg = raw.get("redis", {})

    return VerificationConfig(
        output_dir=_REPO_ROOT
        / str(report.get("output_dir", "reports/daily_verification/stock")),
        lookback_days=max(1, _as_int(report.get("lookback_days"), 22)),
        monthly_trading_days=max(1, _as_int(report.get("monthly_trading_days"), 22)),
        initial_capital=max(
            1.0, _as_float(report.get("initial_capital"), 100_000_000.0)
        ),
        notify_on_issues=_as_bool(report.get("notify_on_issues"), True),
        min_daily_signals=max(0, _as_int(targets.get("min_daily_signals"), 1)),
        min_closed_trades_for_metric_gate=max(
            1, _as_int(targets.get("min_closed_trades_for_metric_gate"), 5)
        ),
        min_monthly_expected_return_pct=_as_float(
            targets.get("min_monthly_expected_return_pct"), 10.0
        ),
        min_win_rate_pct=_as_float(targets.get("min_win_rate_pct"), 55.0),
        target_win_rate_max_pct=_as_float(targets.get("target_win_rate_max_pct"), 60.0),
        max_mdd_pct=max(0.0, _as_float(targets.get("max_mdd_pct"), 10.0)),
        require_positive_equity_slope=_as_bool(
            targets.get("require_positive_equity_slope"), True
        ),
        max_reentry_churn_count=max(
            0, _as_int(targets.get("max_reentry_churn_count"), 0)
        ),
        reentry_churn_seconds=max(
            1, _as_int(targets.get("reentry_churn_seconds"), 3600)
        ),
        min_fresh_ratio=max(
            0.0, min(1.0, _as_float(targets.get("min_fresh_ratio"), 0.5))
        ),
        require_redis_status=_as_bool(targets.get("require_redis_status"), True),
        max_redis_status_age_seconds=float(
            targets.get("max_redis_status_age_seconds", 600.0) or 600.0
        ),
        require_trade_targets=_as_bool(targets.get("require_trade_targets"), True),
        require_daily_indicators=_as_bool(
            targets.get("require_daily_indicators"), True
        ),
        skip_live_redis_gates_on_non_trading_day=_as_bool(
            targets.get("skip_live_redis_gates_on_non_trading_day"), True
        ),
        clickhouse_database=str(clickhouse.get("database", "market")),
        clickhouse_table=str(clickhouse.get("table", "stock_trades")),
        clickhouse_position_table=str(
            clickhouse.get("position_table", "swing_positions")
        ),
        redis_keys={str(k): str(v) for k, v in redis_cfg.items()},
    )


def _validate_identifier(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned or not cleaned.replace("_", "").isalnum():
        raise ValueError(f"Invalid {label}: {value!r}")
    return cleaned


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _parse_report_date(raw: str) -> date:
    if raw:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    return datetime.now(KST).date()


def _window_for(report_date: date, lookback_days: int) -> tuple[date, date]:
    start = report_date - timedelta(days=lookback_days - 1)
    end = report_date + timedelta(days=1)
    return start, end


def _build_clickhouse_client(database: str):
    from clickhouse_driver import Client

    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env(database=database)
    return Client(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        connect_timeout=cfg.connect_timeout,
    )


def fetch_trade_rows(
    config: VerificationConfig,
    window_start: date,
    window_end: date,
) -> list[TradeRow]:
    database = _validate_identifier(config.clickhouse_database, label="database")
    table = _validate_identifier(config.clickhouse_table, label="table")
    start_dt = datetime.combine(window_start, time.min)
    end_dt = datetime.combine(window_end, time.min)
    client = _build_clickhouse_client(database)
    try:
        rows = client.execute(
            f"""
            SELECT
                id,
                code,
                name,
                strategy,
                side,
                entry_date,
                entry_price,
                exit_date,
                exit_price,
                quantity,
                pnl,
                pnl_pct,
                hold_seconds,
                exit_reason
            FROM {database}.{table}
            WHERE exit_date >= %(start)s
              AND exit_date < %(end)s
            ORDER BY exit_date ASC, id ASC
            """,
            {"start": start_dt, "end": end_dt},
        )
    finally:
        client.disconnect()

    return [
        TradeRow(
            id=str(row[0]),
            code=str(row[1]),
            name=str(row[2]),
            strategy=str(row[3]),
            side=str(row[4]),
            entry_date=_coerce_datetime(row[5]),
            entry_price=float(row[6] or 0.0),
            exit_date=_coerce_datetime(row[7]),
            exit_price=float(row[8] or 0.0),
            quantity=int(row[9] or 0),
            pnl=float(row[10] or 0.0),
            pnl_pct=float(row[11] or 0.0),
            hold_seconds=int(row[12] or 0),
            exit_reason=str(row[13] or ""),
        )
        for row in rows
    ]


def fetch_clickhouse_position_snapshot(
    config: VerificationConfig,
) -> ClickHousePositionSnapshot:
    """Fetch open swing-position state from ClickHouse.

    Redis is the runtime source of truth for current paper positions, but stale
    open rows in ``swing_positions`` can pollute recovery/debug paths. Keep this
    as a separate operational snapshot instead of mixing it into trade metrics.
    """
    database = _validate_identifier(config.clickhouse_database, label="database")
    table = _validate_identifier(config.clickhouse_position_table, label="table")
    client = _build_clickhouse_client(database)
    try:
        count_rows = client.execute(
            f"SELECT count() FROM {database}.{table} FINAL WHERE is_open = 1"
        )
        sample_rows = client.execute(f"""
            SELECT code, strategy, entry_date
            FROM {database}.{table} FINAL
            WHERE is_open = 1
            ORDER BY entry_date ASC, code ASC
            LIMIT 10
            """)
    finally:
        client.disconnect()

    count = int(count_rows[0][0] or 0) if count_rows else 0
    samples = []
    for code, strategy, entry_date in sample_rows:
        samples.append(f"{code}:{strategy}:{_coerce_datetime(entry_date).isoformat()}")
    return ClickHousePositionSnapshot(
        open_positions_count=count,
        open_position_samples=samples,
    )


def load_active_stock_strategy_names(*, timeframe: str | None = None) -> list[str]:
    """Return strategy names currently loaded by stock runtime.

    The orchestrator/StrategyManager loads ``strategy.enabled: true`` from
    ``config/strategies/stock``. Mirroring that scope lets the verification
    report distinguish current runtime quality from historical trades created
    by strategies that have since been disabled.
    """
    from shared.config.loader import ConfigLoader

    names: list[str] = []
    expected_timeframe = str(timeframe).strip().lower() if timeframe else None
    for strategy_config in ConfigLoader.load_all_strategies("stock", enabled_only=True):
        strategy = strategy_config.get("strategy", {})
        if not isinstance(strategy, dict):
            continue
        if expected_timeframe:
            actual_timeframe = str(strategy.get("timeframe", "")).strip().lower()
            if actual_timeframe != expected_timeframe:
                continue
        name = str(strategy.get("name", "")).strip()
        if not name:
            continue
        paper = strategy.get("paper") or {}
        if isinstance(paper, dict) and _as_bool(paper.get("enabled"), True) is False:
            continue
        names.append(name)
    return sorted(set(names))


def _equity_slope(equity_points: list[float]) -> float:
    n = len(equity_points)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(equity_points) / n
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(equity_points))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _max_drawdown_pct(equity_points: list[float]) -> float:
    if not equity_points:
        return 0.0
    peak = equity_points[0]
    max_dd = 0.0
    for equity in equity_points:
        peak = max(peak, equity)
        if peak <= 0:
            continue
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return max_dd


def _count_reentry_churn(rows: list[TradeRow], max_seconds: int) -> int:
    ordered = sorted(rows, key=lambda r: r.entry_date)
    churn = 0
    for closed in sorted(rows, key=lambda r: r.exit_date):
        for candidate in ordered:
            if candidate.id == closed.id:
                continue
            if candidate.code != closed.code or candidate.strategy != closed.strategy:
                continue
            delta = (candidate.entry_date - closed.exit_date).total_seconds()
            if 0 <= delta <= max_seconds:
                churn += 1
                break
    return churn


def summarize_trades(
    rows: list[TradeRow],
    *,
    initial_capital: float,
    lookback_days: int,
    monthly_trading_days: int,
    reentry_churn_seconds: int,
) -> TradeMetrics:
    metrics = TradeMetrics()
    if not rows:
        return metrics

    metrics.trade_count = len(rows)
    metrics.winning_trades = sum(1 for r in rows if r.pnl > 0)
    metrics.losing_trades = sum(1 for r in rows if r.pnl < 0)
    metrics.win_rate_pct = metrics.winning_trades / len(rows) * 100.0
    metrics.total_pnl = sum(r.pnl for r in rows)
    metrics.avg_pnl = metrics.total_pnl / len(rows)
    metrics.avg_pnl_pct = sum(r.pnl_pct for r in rows) / len(rows)
    metrics.gross_profit = sum(r.pnl for r in rows if r.pnl > 0)
    metrics.gross_loss = abs(sum(r.pnl for r in rows if r.pnl < 0))
    if metrics.gross_loss > 0:
        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
    elif metrics.gross_profit > 0:
        metrics.profit_factor = None

    metrics.realized_return_pct = metrics.total_pnl / initial_capital * 100.0
    metrics.monthly_expected_return_pct = (
        metrics.realized_return_pct * monthly_trading_days / max(1, lookback_days)
    )

    equity = initial_capital
    equity_points = [equity]
    for row in sorted(rows, key=lambda r: r.exit_date):
        equity += row.pnl
        equity_points.append(equity)
        metrics.by_exit_reason[row.exit_reason or "unknown"] = (
            metrics.by_exit_reason.get(row.exit_reason or "unknown", 0) + 1
        )

        bucket = metrics.by_strategy.setdefault(
            row.strategy or "unknown",
            {
                "trades": 0,
                "wins": 0,
                "total_pnl": 0.0,
                "win_rate_pct": 0.0,
                "avg_pnl": 0.0,
            },
        )
        bucket["trades"] += 1
        bucket["wins"] += 1 if row.pnl > 0 else 0
        bucket["total_pnl"] += row.pnl

    for bucket in metrics.by_strategy.values():
        trades = bucket["trades"]
        bucket["win_rate_pct"] = bucket["wins"] / trades * 100.0 if trades else 0.0
        bucket["avg_pnl"] = bucket["total_pnl"] / trades if trades else 0.0

    metrics.max_drawdown_pct = _max_drawdown_pct(equity_points)
    metrics.equity_slope_krw_per_trade = _equity_slope(equity_points)
    metrics.equity_is_upward = (
        equity_points[-1] >= equity_points[0] and metrics.equity_slope_krw_per_trade > 0
    )
    metrics.reentry_churn_count = _count_reentry_churn(rows, reentry_churn_seconds)
    return metrics


def _filter_active_strategy_rows(
    rows: list[TradeRow], active_strategy_names: list[str]
) -> list[TradeRow]:
    active = {name for name in active_strategy_names if name}
    if not active:
        return []
    return [row for row in rows if row.strategy in active]


_TRADE_METRIC_ISSUE_CODES = {
    "no_closed_trades",
    "insufficient_closed_trades",
    "monthly_expected_return_below_target",
    "win_rate_below_target",
    "win_rate_above_target_band",
    "mdd_above_target",
    "equity_curve_not_upward",
    "reentry_churn_above_target",
}


def _is_trade_metric_issue(issue: GateIssue) -> bool:
    return issue.code.removeprefix("active_") in _TRADE_METRIC_ISSUE_CODES


def _select_verdict_issues(
    issues: list[GateIssue],
    active_issues: list[GateIssue],
    active_strategy_names: list[str],
) -> list[GateIssue]:
    """Return only issues that should decide the operational verdict.

    Once enabled stock strategies are known, stale trade metrics from disabled
    strategies remain useful context but should not keep the daily paper gate in
    FAIL. Source/Redis issues still gate regardless of strategy scope.
    """
    if not active_strategy_names:
        return issues + active_issues
    operational_issues = [
        issue for issue in issues if not _is_trade_metric_issue(issue)
    ]
    return operational_issues + active_issues


def _issues_for_verdict(report: VerificationReport) -> list[GateIssue]:
    return _select_verdict_issues(
        report.issues,
        report.active_issues,
        report.active_strategy_names,
    )


def _verdict_from_issues(issues: list[GateIssue]) -> str:
    if any(issue.severity == "FAIL" for issue in issues):
        return "FAIL"
    if issues:
        return "WARN"
    return "PASS"


def _safe_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _parse_signal_date(raw_ts: Any) -> date | None:
    if not raw_ts:
        return None
    try:
        ts = datetime.fromisoformat(str(raw_ts))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(KST).date()


def _parse_status_updated_at(raw_ts: Any) -> datetime | None:
    if not raw_ts:
        return None
    try:
        ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _count_codes_from_payload(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    for key in ("codes", "symbols", "ranked_codes"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    indicators = payload.get("indicators")
    if isinstance(indicators, dict):
        return len(indicators)
    strategies = payload.get("strategies")
    if isinstance(strategies, dict):
        return len(
            {
                str(code).strip()
                for values in strategies.values()
                if isinstance(values, list)
                for code in values
                if str(code).strip()
            }
        )
    return 0


def _strategy_counts_from_payload(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("strategy_counts")
    if isinstance(raw, dict):
        counts: dict[str, int] = {}
        for name, value in raw.items():
            strategy = str(name).strip()
            if not strategy:
                continue
            counts[strategy] = max(0, _as_int(value, 0))
        return counts

    strategies = payload.get("strategies")
    if not isinstance(strategies, dict):
        return {}
    counts = {}
    for name, values in strategies.items():
        strategy = str(name).strip()
        if not strategy:
            continue
        counts[strategy] = len(values) if isinstance(values, list) else 0
    return counts


def fetch_redis_snapshot(
    config: VerificationConfig, report_date: date
) -> RedisSnapshot:
    from shared.collector.historical.calendar import is_trading_day
    from shared.streaming.client import RedisClient

    redis_client = RedisClient.get_client()
    keys = config.redis_keys
    status_key = keys["status_key"]
    status_raw = redis_client.hgetall(status_key) or {}
    status: dict[str, Any] = {}
    for key, value in status_raw.items():
        key_s = key.decode() if isinstance(key, bytes) else str(key)
        try:
            status[key_s] = _safe_json(value)
        except (TypeError, ValueError):
            status[key_s] = value.decode() if isinstance(value, bytes) else value

    status_ttl = int(redis_client.ttl(status_key) or -1)
    status_updated_at = (
        str(status.get("updated_at")) if status.get("updated_at") else None
    )
    parsed_updated_at = _parse_status_updated_at(status_updated_at)
    status_age = None
    if parsed_updated_at is not None:
        status_age = max(
            0.0,
            (datetime.now(UTC) - parsed_updated_at).total_seconds(),
        )

    signals_raw = redis_client.lrange(keys["signals_key"], 0, 199) or []
    daily_signals = 0
    for raw in signals_raw:
        try:
            signal = _safe_json(raw)
        except (TypeError, ValueError):
            continue
        if (
            isinstance(signal, dict)
            and _parse_signal_date(signal.get("timestamp")) == report_date
        ):
            daily_signals += 1

    def load_payload(name: str) -> tuple[bool, dict[str, Any]]:
        raw = redis_client.get(keys[name])
        if raw is None:
            return False, {}
        try:
            payload = _safe_json(raw)
        except (TypeError, ValueError):
            return True, {}
        return True, payload if isinstance(payload, dict) else {}

    def load_counted_key(name: str) -> tuple[bool, int]:
        exists, payload = load_payload(name)
        return exists, _count_codes_from_payload(payload)

    trade_targets_exists, trade_targets_count = load_counted_key("trade_targets_key")
    universe_exists, universe_count = load_counted_key("universe_key")
    daily_indicators_exists, daily_indicators_payload = load_payload(
        "daily_indicators_key"
    )
    daily_indicators_count = _count_codes_from_payload(daily_indicators_payload)
    daily_strategy_counts = _strategy_counts_from_payload(daily_indicators_payload)
    daily_strategy_candidate_count = sum(daily_strategy_counts.values())

    freshness = {}
    raw_freshness = redis_client.get(keys["data_freshness_key"])
    if raw_freshness is not None:
        try:
            parsed = _safe_json(raw_freshness)
            if isinstance(parsed, dict):
                freshness = parsed
        except (TypeError, ValueError):
            freshness = {}

    status_config = (
        status.get("config") if isinstance(status.get("config"), dict) else {}
    )
    status_risk = status.get("risk") if isinstance(status.get("risk"), dict) else {}

    return RedisSnapshot(
        report_is_trading_day=is_trading_day(report_date),
        status_exists=bool(status_raw),
        status_ttl_seconds=status_ttl,
        status_age_seconds=status_age,
        status_updated_at=status_updated_at,
        status_publisher_pid=(
            str(status.get("publisher_pid")) if status.get("publisher_pid") else None
        ),
        state=str(status.get("state", "")),
        status_config_capital=_maybe_float(status_config.get("capital")),
        risk_initial_capital=_maybe_float(status_risk.get("initial_capital")),
        configured_symbols=int(status_config.get("symbols", 0) or 0),
        data_provider=status.get("data_provider") or {},
        data_freshness=freshness,
        daily_signal_count=daily_signals,
        signals_list_len=int(redis_client.llen(keys["signals_key"]) or 0),
        trades_list_len=int(redis_client.llen(keys["trades_key"]) or 0),
        open_positions_count=int(redis_client.hlen(keys["positions_key"]) or 0),
        candle_cache_symbols=int(redis_client.hlen(keys["candle_cache_key"]) or 0),
        trade_targets_exists=trade_targets_exists,
        trade_targets_count=trade_targets_count,
        universe_exists=universe_exists,
        universe_count=universe_count,
        daily_indicators_exists=daily_indicators_exists,
        daily_indicators_count=daily_indicators_count,
        daily_strategy_candidate_count=daily_strategy_candidate_count,
        daily_strategy_counts=daily_strategy_counts,
    )


def evaluate_report(
    config: VerificationConfig,
    metrics: TradeMetrics,
    redis_snapshot: RedisSnapshot,
    clickhouse_position_snapshot: ClickHousePositionSnapshot | None = None,
    source_errors: list[str] | None = None,
) -> list[GateIssue]:
    issues: list[GateIssue] = []

    def add(
        severity: str, code: str, observed: str, expected: str, detail: str
    ) -> None:
        issues.append(GateIssue(severity, code, observed, expected, detail))

    for error in source_errors or []:
        code = error.split(":", 1)[0]
        add(
            "FAIL",
            code,
            error,
            "source query succeeds",
            "A verification data source failed.",
        )

    if (
        clickhouse_position_snapshot is not None
        and clickhouse_position_snapshot.open_positions_count
        > redis_snapshot.open_positions_count
    ):
        samples = ",".join(clickhouse_position_snapshot.open_position_samples[:3])
        add(
            "FAIL",
            "clickhouse_open_positions_exceed_redis",
            (
                f"clickhouse={clickhouse_position_snapshot.open_positions_count} "
                f"redis={redis_snapshot.open_positions_count} samples={samples}"
            ),
            "ClickHouse open swing positions <= Redis runtime open positions",
            "ClickHouse has open swing-position rows that are absent from the runtime Redis position state.",
        )

    live_redis_gates_enabled = (
        redis_snapshot.report_is_trading_day
        or not config.skip_live_redis_gates_on_non_trading_day
    )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and not redis_snapshot.status_exists
    ):
        add(
            "FAIL",
            "redis_status_missing",
            "missing",
            "trading:stock:status present",
            "Stock orchestrator status is not available in Redis.",
        )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and redis_snapshot.status_exists
        and not redis_snapshot.status_updated_at
    ):
        add(
            "FAIL",
            "redis_status_updated_at_missing",
            "missing",
            "trading:stock:status updated_at present",
            "Stock orchestrator status uses an old schema or was not published by the timestamped publisher.",
        )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and redis_snapshot.status_exists
        and redis_snapshot.status_updated_at
        and redis_snapshot.status_age_seconds is None
    ):
        add(
            "FAIL",
            "redis_status_updated_at_invalid",
            str(redis_snapshot.status_updated_at),
            "ISO-8601 timestamp",
            "Stock orchestrator status updated_at cannot be parsed.",
        )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and redis_snapshot.status_age_seconds is not None
        and redis_snapshot.status_age_seconds > config.max_redis_status_age_seconds
    ):
        add(
            "FAIL",
            "redis_status_stale",
            f"{redis_snapshot.status_age_seconds:.1f}s",
            f"<= {config.max_redis_status_age_seconds:.1f}s",
            "Stock orchestrator status has not been refreshed recently.",
        )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and redis_snapshot.status_exists
        and redis_snapshot.status_config_capital is not None
        and abs(redis_snapshot.status_config_capital - config.initial_capital) > 1.0
    ):
        add(
            "FAIL",
            "runtime_capital_mismatch",
            f"{redis_snapshot.status_config_capital:,.0f}",
            f"{config.initial_capital:,.0f}",
            "Stock orchestrator runtime capital differs from verification baseline.",
        )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and redis_snapshot.status_exists
        and redis_snapshot.risk_initial_capital is None
    ):
        add(
            "FAIL",
            "risk_initial_capital_missing",
            "missing",
            "risk.initial_capital present in trading:stock:status",
            "Stock orchestrator status does not expose RiskManager capital.",
        )

    if (
        live_redis_gates_enabled
        and config.require_redis_status
        and redis_snapshot.status_exists
        and redis_snapshot.risk_initial_capital is not None
    ):
        expected_risk_capital = (
            redis_snapshot.status_config_capital
            if redis_snapshot.status_config_capital is not None
            else config.initial_capital
        )
        if abs(redis_snapshot.risk_initial_capital - expected_risk_capital) > 1.0:
            add(
                "FAIL",
                "risk_initial_capital_mismatch",
                f"{redis_snapshot.risk_initial_capital:,.0f}",
                f"{expected_risk_capital:,.0f}",
                "RiskManager capital differs from the active orchestrator capital.",
            )

    if (
        live_redis_gates_enabled
        and redis_snapshot.daily_signal_count < config.min_daily_signals
    ):
        add(
            "FAIL",
            "daily_signals_below_target",
            str(redis_snapshot.daily_signal_count),
            f">= {config.min_daily_signals}",
            "No stock entry/exit activity is visible in today's Redis signal list.",
        )

    if (
        live_redis_gates_enabled
        and config.require_trade_targets
        and not redis_snapshot.trade_targets_exists
        and redis_snapshot.daily_strategy_candidate_count <= 0
    ):
        add(
            "FAIL",
            "trade_targets_missing",
            "missing",
            "trade target snapshot or daily strategy watchlist present",
            "Fusion/screener trade target snapshot is missing and no daily strategy watchlist is available as an active-runtime fallback.",
        )

    if (
        live_redis_gates_enabled
        and config.require_daily_indicators
        and not redis_snapshot.daily_indicators_exists
    ):
        add(
            "FAIL",
            "daily_indicators_missing",
            "missing",
            "present",
            "Daily indicator snapshot is missing; stock strategies may lack daily context.",
        )

    provider = redis_snapshot.data_provider or {}
    total_symbols = int(
        provider.get("total_symbols", redis_snapshot.configured_symbols) or 0
    )
    fresh_count = int(provider.get("fresh_count", 0) or 0)
    fresh_ratio = fresh_count / total_symbols if total_symbols > 0 else 0.0
    if (
        live_redis_gates_enabled
        and total_symbols > 0
        and fresh_ratio < config.min_fresh_ratio
    ):
        add(
            "FAIL",
            "fresh_ratio_below_target",
            f"{fresh_ratio:.2f}",
            f">= {config.min_fresh_ratio:.2f}",
            "DataProvider fresh-symbol ratio is below the silent-stall guard target.",
        )

    issues.extend(evaluate_trade_metric_gates(config, metrics))
    return issues


def evaluate_active_daily_watchlist_gates(
    config: VerificationConfig,
    redis_snapshot: RedisSnapshot,
    active_daily_strategy_names: list[str],
) -> tuple[list[GateIssue], int]:
    """Check daily-strategy candidate readiness for the active stock runtime."""
    active_daily_names = sorted(set(active_daily_strategy_names))
    if not active_daily_names:
        return [], 0

    active_candidate_count = sum(
        redis_snapshot.daily_strategy_counts.get(name, 0) for name in active_daily_names
    )

    issues: list[GateIssue] = []
    missing = [
        name
        for name in active_daily_names
        if name not in redis_snapshot.daily_strategy_counts
    ]
    if redis_snapshot.daily_indicators_exists and missing:
        issues.append(
            GateIssue(
                "FAIL",
                "active_daily_watchlist_missing",
                ",".join(missing),
                "all active daily strategies represented in system:daily_indicators:latest strategies",
                "Daily indicator snapshot exists but does not include candidate watchlists for every active daily strategy.",
            )
        )
    elif active_candidate_count == 0:
        issues.append(
            GateIssue(
                "WARN",
                "active_daily_no_candidates",
                "0",
                "> 0",
                "Enabled daily strategies have no precomputed candidates; paper trading may legitimately stay idle, but objective evidence cannot accumulate.",
            )
        )

    return issues, active_candidate_count


def evaluate_trade_metric_gates(
    config: VerificationConfig,
    metrics: TradeMetrics,
    *,
    code_prefix: str = "",
    no_trades_severity: str = "FAIL",
    insufficient_trades_severity: str = "WARN",
    detail_prefix: str = "",
) -> list[GateIssue]:
    issues: list[GateIssue] = []

    def add(
        severity: str, code: str, observed: str, expected: str, detail: str
    ) -> None:
        issues.append(
            GateIssue(
                severity,
                f"{code_prefix}{code}",
                observed,
                expected,
                f"{detail_prefix}{detail}",
            )
        )

    if metrics.trade_count == 0:
        add(
            no_trades_severity,
            "no_closed_trades",
            "0",
            "> 0",
            "No closed stock trades in the verification window.",
        )
        return issues

    if metrics.trade_count < config.min_closed_trades_for_metric_gate:
        add(
            insufficient_trades_severity,
            "insufficient_closed_trades",
            str(metrics.trade_count),
            f">= {config.min_closed_trades_for_metric_gate}",
            "Metric gates are weak with too few closed trades; continue collecting evidence.",
        )
        return issues

    if metrics.monthly_expected_return_pct < config.min_monthly_expected_return_pct:
        add(
            "FAIL",
            "monthly_expected_return_below_target",
            f"{metrics.monthly_expected_return_pct:.2f}%",
            f">= {config.min_monthly_expected_return_pct:.2f}%",
            "Monthly expected return is below the active objective.",
        )

    if metrics.win_rate_pct < config.min_win_rate_pct:
        add(
            "FAIL",
            "win_rate_below_target",
            f"{metrics.win_rate_pct:.2f}%",
            f">= {config.min_win_rate_pct:.2f}%",
            "Closed-trade win rate is below the active objective.",
        )
    elif metrics.win_rate_pct > config.target_win_rate_max_pct:
        add(
            "WARN",
            "win_rate_above_target_band",
            f"{metrics.win_rate_pct:.2f}%",
            f"{config.min_win_rate_pct:.2f}% to {config.target_win_rate_max_pct:.2f}%",
            "Win rate is above the target band; check whether exits are too tight or profits are being capped.",
        )

    if metrics.max_drawdown_pct > config.max_mdd_pct:
        add(
            "FAIL",
            "mdd_above_target",
            f"{metrics.max_drawdown_pct:.2f}%",
            f"<= {config.max_mdd_pct:.2f}%",
            "Max drawdown is above the active objective.",
        )

    if config.require_positive_equity_slope and not metrics.equity_is_upward:
        add(
            "FAIL",
            "equity_curve_not_upward",
            f"slope={metrics.equity_slope_krw_per_trade:.0f}",
            "positive slope and ending equity >= starting equity",
            "Equity curve is not upward over the verification window.",
        )

    if metrics.reentry_churn_count > config.max_reentry_churn_count:
        add(
            "FAIL",
            "reentry_churn_above_target",
            str(metrics.reentry_churn_count),
            f"<= {config.max_reentry_churn_count}",
            "Same-symbol same-strategy re-entry occurred too soon after an exit.",
        )

    return issues


def _render_markdown(report: VerificationReport, config: VerificationConfig) -> str:
    m = report.trade_metrics
    active = report.active_trade_metrics
    r = report.redis_snapshot
    lines = [
        f"# Stock Paper Daily Verification ({report.report_date})",
        "",
        f"- Verdict: `{report.verdict}`",
        f"- Verdict basis: `{'active strategies + operational gates' if report.active_strategy_names else 'all strategy trades + operational gates'}`",
        f"- Window: `{report.window_start}` to `{report.window_end}`",
        f"- Generated at: `{report.generated_at}`",
        "",
        "## All-Strategy Objective Metrics",
        "",
        f"- Trades: `{m.trade_count}`",
        f"- Total PnL: `{m.total_pnl:,.0f}` KRW",
        f"- Monthly expected return: `{m.monthly_expected_return_pct:.2f}%` (target `>= {config.min_monthly_expected_return_pct:.2f}%`)",
        f"- Win rate: `{m.win_rate_pct:.2f}%` (target `{config.min_win_rate_pct:.2f}% to {config.target_win_rate_max_pct:.2f}%`)",
        f"- Max drawdown: `{m.max_drawdown_pct:.2f}%` (target `<= {config.max_mdd_pct:.2f}%`)",
        f"- Equity slope: `{m.equity_slope_krw_per_trade:,.0f}` KRW/trade",
        f"- Re-entry churn count: `{m.reentry_churn_count}`",
        "",
        "## Active Strategy Metrics",
        "",
        f"- Active strategies: `{', '.join(report.active_strategy_names) or 'none'}`",
        f"- Active daily strategies: `{', '.join(report.active_daily_strategy_names) or 'none'}`",
        f"- Active daily candidates: `{report.active_daily_candidate_count}`",
        f"- Trades: `{active.trade_count}`",
        f"- Total PnL: `{active.total_pnl:,.0f}` KRW",
        f"- Monthly expected return: `{active.monthly_expected_return_pct:.2f}%` (target `>= {config.min_monthly_expected_return_pct:.2f}%`)",
        f"- Win rate: `{active.win_rate_pct:.2f}%` (target `{config.min_win_rate_pct:.2f}% to {config.target_win_rate_max_pct:.2f}%`)",
        f"- Max drawdown: `{active.max_drawdown_pct:.2f}%` (target `<= {config.max_mdd_pct:.2f}%`)",
        f"- Equity slope: `{active.equity_slope_krw_per_trade:,.0f}` KRW/trade",
        f"- Re-entry churn count: `{active.reentry_churn_count}`",
        "",
        "## Redis Pipeline",
        "",
        f"- Report trading day: `{r.report_is_trading_day}`",
        f"- Status exists: `{r.status_exists}` state=`{r.state}` ttl=`{r.status_ttl_seconds}` age_s=`{r.status_age_seconds}` updated_at=`{r.status_updated_at}` pid=`{r.status_publisher_pid}`",
        f"- Runtime capital: config=`{r.status_config_capital}` risk=`{r.risk_initial_capital}` verifier=`{config.initial_capital}`",
        f"- Signals today/list: `{r.daily_signal_count}` / `{r.signals_list_len}`",
        f"- Trades list len: `{r.trades_list_len}`",
        f"- Open positions: `{r.open_positions_count}`",
        f"- Candle cache symbols: `{r.candle_cache_symbols}`",
        f"- Trade targets: `{r.trade_targets_exists}` count=`{r.trade_targets_count}`",
        f"- Universe: `{r.universe_exists}` count=`{r.universe_count}`",
        f"- Daily indicators: `{r.daily_indicators_exists}` count=`{r.daily_indicators_count}`",
        f"- Daily strategy candidates: total=`{r.daily_strategy_candidate_count}` counts=`{r.daily_strategy_counts}`",
        "",
        "## ClickHouse Position State",
        "",
        f"- Open swing positions: `{report.clickhouse_position_snapshot.open_positions_count}`",
        f"- Open swing samples: `{report.clickhouse_position_snapshot.open_position_samples}`",
        "",
    ]
    if report.source_errors:
        lines.extend(["## Source Errors", ""])
        for error in report.source_errors:
            lines.append(f"- `{error}`")
        lines.append("")

    lines.extend(["## All-Strategy / Operational Issues", ""])

    if report.issues:
        for issue in report.issues:
            lines.append(
                f"- `{issue.severity}` `{issue.code}` observed=`{issue.observed}` expected=`{issue.expected}` - {issue.detail}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Active Strategy Issues", ""])

    if report.active_issues:
        for issue in report.active_issues:
            lines.append(
                f"- `{issue.severity}` `{issue.code}` observed=`{issue.observed}` expected=`{issue.expected}` - {issue.detail}"
            )
    else:
        lines.append("- None")

    if m.by_strategy:
        lines.extend(["", "## By Strategy", ""])
        for strategy, bucket in sorted(m.by_strategy.items()):
            lines.append(
                f"- `{strategy}` trades=`{int(bucket['trades'])}` win_rate=`{bucket['win_rate_pct']:.2f}%` pnl=`{bucket['total_pnl']:,.0f}`"
            )

    if active.by_strategy:
        lines.extend(["", "## Active By Strategy", ""])
        for strategy, bucket in sorted(active.by_strategy.items()):
            lines.append(
                f"- `{strategy}` trades=`{int(bucket['trades'])}` win_rate=`{bucket['win_rate_pct']:.2f}%` pnl=`{bucket['total_pnl']:,.0f}`"
            )

    if m.by_exit_reason:
        lines.extend(["", "## By Exit Reason", ""])
        for reason, count in sorted(
            m.by_exit_reason.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"- `{reason}`: `{count}`")

    if active.by_exit_reason:
        lines.extend(["", "## Active By Exit Reason", ""])
        for reason, count in sorted(
            active.by_exit_reason.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"- `{reason}`: `{count}`")

    return "\n".join(lines) + "\n"


def write_report(
    report: VerificationReport, config: VerificationConfig
) -> tuple[Path, Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    stem = report.report_date
    json_path = config.output_dir / f"{stem}.json"
    md_path = config.output_dir / f"{stem}.md"
    report.json_path = str(json_path)
    report.markdown_path = str(md_path)
    json_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(_render_markdown(report, config), encoding="utf-8")
    return json_path, md_path


def _format_notification(report: VerificationReport) -> str:
    m = report.trade_metrics
    active = report.active_trade_metrics
    lines = [
        f"<b>Stock paper verification {report.verdict}</b>",
        f"date: <code>{report.report_date}</code>",
        f"trades: <code>{m.trade_count}</code>, pnl: <code>{m.total_pnl:,.0f}</code>",
        f"monthly_expected: <code>{m.monthly_expected_return_pct:.2f}%</code>, win_rate: <code>{m.win_rate_pct:.2f}%</code>, mdd: <code>{m.max_drawdown_pct:.2f}%</code>",
        f"active_trades: <code>{active.trade_count}</code>, active_monthly_expected: <code>{active.monthly_expected_return_pct:.2f}%</code>, active_win_rate: <code>{active.win_rate_pct:.2f}%</code>",
        f"active_daily_candidates: <code>{report.active_daily_candidate_count}</code>",
        f"ch_open_positions: <code>{report.clickhouse_position_snapshot.open_positions_count}</code>",
    ]
    verdict_issues = _issues_for_verdict(report)
    if verdict_issues:
        lines.append("<b>Verdict issues</b>")
        for issue in verdict_issues[:8]:
            lines.append(
                f"- {issue.severity} {issue.code}: {issue.observed} vs {issue.expected}"
            )
    if report.active_strategy_names and report.issues:
        ignored_metric_count = sum(
            1 for issue in report.issues if _is_trade_metric_issue(issue)
        )
        if ignored_metric_count:
            lines.append(
                f"historical all-strategy metric issues ignored for verdict: <code>{ignored_metric_count}</code>"
            )
    lines.append(f"report: <code>{report.markdown_path}</code>")
    return "\n".join(lines)


async def _send_notification(report: VerificationReport) -> bool:
    try:
        from shared.notification.telegram import notifier_for_domain

        notifier = notifier_for_domain("briefing")
        if notifier is None:
            return False
        await notifier.send_message(_format_notification(report), is_critical=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] telegram notification failed: {exc}", file=sys.stderr)
        return False


def build_report(
    *,
    config: VerificationConfig,
    report_date: date,
    rows: list[TradeRow],
    redis_snapshot: RedisSnapshot,
    clickhouse_position_snapshot: ClickHousePositionSnapshot | None = None,
    source_errors: list[str] | None = None,
    active_strategy_names: list[str] | None = None,
    active_daily_strategy_names: list[str] | None = None,
) -> VerificationReport:
    window_start, window_end = _window_for(report_date, config.lookback_days)
    metrics = summarize_trades(
        rows,
        initial_capital=config.initial_capital,
        lookback_days=config.lookback_days,
        monthly_trading_days=config.monthly_trading_days,
        reentry_churn_seconds=config.reentry_churn_seconds,
    )
    clickhouse_snapshot = clickhouse_position_snapshot or ClickHousePositionSnapshot()
    active_names = sorted(set(active_strategy_names or []))
    active_rows = _filter_active_strategy_rows(rows, active_names)
    active_metrics = summarize_trades(
        active_rows,
        initial_capital=config.initial_capital,
        lookback_days=config.lookback_days,
        monthly_trading_days=config.monthly_trading_days,
        reentry_churn_seconds=config.reentry_churn_seconds,
    )
    errors = source_errors or []
    issues = evaluate_report(
        config,
        metrics,
        redis_snapshot,
        clickhouse_position_snapshot=clickhouse_snapshot,
        source_errors=errors,
    )
    active_daily_names = sorted(set(active_daily_strategy_names or []))
    daily_issues, active_daily_candidate_count = evaluate_active_daily_watchlist_gates(
        config,
        redis_snapshot,
        active_daily_names,
    )
    active_issues: list[GateIssue] = []
    if active_names:
        active_metric_gates_enabled = (
            redis_snapshot.report_is_trading_day
            or not config.skip_live_redis_gates_on_non_trading_day
            or active_metrics.trade_count > 0
        )
        if active_metric_gates_enabled:
            active_issues = evaluate_trade_metric_gates(
                config,
                active_metrics,
                code_prefix="active_",
                no_trades_severity="WARN",
                insufficient_trades_severity="WARN",
                detail_prefix="Enabled-strategy scope: ",
            )
        active_issues.extend(daily_issues)
    verdict = _verdict_from_issues(
        _select_verdict_issues(issues, active_issues, active_names)
    )
    return VerificationReport(
        report_date=report_date.isoformat(),
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        generated_at=datetime.now(UTC).isoformat(),
        verdict=verdict,
        source_errors=errors,
        issues=issues,
        trade_metrics=metrics,
        active_strategy_names=active_names,
        active_daily_strategy_names=active_daily_names,
        active_daily_candidate_count=active_daily_candidate_count,
        active_trade_metrics=active_metrics,
        active_issues=active_issues,
        redis_snapshot=redis_snapshot,
        clickhouse_position_snapshot=clickhouse_snapshot,
    )


def empty_redis_snapshot(report_date: date) -> RedisSnapshot:
    from shared.collector.historical.calendar import is_trading_day

    return RedisSnapshot(
        report_is_trading_day=is_trading_day(report_date),
        status_exists=False,
        status_ttl_seconds=-1,
        status_age_seconds=None,
        status_updated_at=None,
        status_publisher_pid=None,
        state="",
        status_config_capital=None,
        risk_initial_capital=None,
        configured_symbols=0,
        data_provider={},
        data_freshness={},
        daily_signal_count=0,
        signals_list_len=0,
        trades_list_len=0,
        open_positions_count=0,
        candle_cache_symbols=0,
        trade_targets_exists=False,
        trade_targets_count=0,
        universe_exists=False,
        universe_count=0,
        daily_indicators_exists=False,
        daily_indicators_count=0,
        daily_strategy_candidate_count=0,
        daily_strategy_counts={},
    )


def empty_clickhouse_position_snapshot() -> ClickHousePositionSnapshot:
    return ClickHousePositionSnapshot()


def _source_error(code: str, exc: Exception) -> str:
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    detail = next(
        (line for line in lines if "DB::Exception" in line),
        lines[0] if lines else str(exc),
    )
    return f"{code}: {type(exc).__name__}: {detail[:500]}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", default="", help="KST report date in YYYY-MM-DD. Default: today."
    )
    parser.add_argument(
        "--no-telegram", action="store_true", help="Do not send Telegram notifications."
    )
    parser.add_argument(
        "--print-json", action="store_true", help="Print full JSON report to stdout."
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        _load_repo_env()
        config = _load_config()
        report_date = _parse_report_date(args.date)
        window_start, window_end = _window_for(report_date, config.lookback_days)
        source_errors: list[str] = []
        try:
            active_strategy_names = load_active_stock_strategy_names()
            active_daily_strategy_names = load_active_stock_strategy_names(
                timeframe="daily"
            )
        except Exception as exc:  # noqa: BLE001
            active_strategy_names = []
            active_daily_strategy_names = []
            source_errors.append(_source_error("active_strategy_config_failed", exc))
        try:
            rows = fetch_trade_rows(config, window_start, window_end)
        except Exception as exc:  # noqa: BLE001
            rows = []
            source_errors.append(_source_error("clickhouse_query_failed", exc))
        try:
            clickhouse_position_snapshot = fetch_clickhouse_position_snapshot(config)
        except Exception as exc:  # noqa: BLE001
            clickhouse_position_snapshot = empty_clickhouse_position_snapshot()
            source_errors.append(
                _source_error("clickhouse_open_positions_query_failed", exc)
            )
        try:
            redis_snapshot = fetch_redis_snapshot(config, report_date)
        except Exception as exc:  # noqa: BLE001
            redis_snapshot = empty_redis_snapshot(report_date)
            source_errors.append(_source_error("redis_query_failed", exc))
        report = build_report(
            config=config,
            report_date=report_date,
            rows=rows,
            redis_snapshot=redis_snapshot,
            clickhouse_position_snapshot=clickhouse_position_snapshot,
            source_errors=source_errors,
            active_strategy_names=active_strategy_names,
            active_daily_strategy_names=active_daily_strategy_names,
        )
        write_report(report, config)
        if (
            report.verdict != "PASS"
            and config.notify_on_issues
            and not args.no_telegram
        ):
            report.notification_sent = asyncio.run(_send_notification(report))
            write_report(report, config)

        if args.print_json:
            print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        else:
            print(
                f"{report.verdict}: trades={report.trade_metrics.trade_count} "
                f"monthly_expected={report.trade_metrics.monthly_expected_return_pct:.2f}% "
                f"win_rate={report.trade_metrics.win_rate_pct:.2f}% "
                f"mdd={report.trade_metrics.max_drawdown_pct:.2f}% "
                f"issues={len(report.issues)}"
            )
            print(
                "active: "
                f"strategies={','.join(report.active_strategy_names) or 'none'} "
                f"daily_candidates={report.active_daily_candidate_count} "
                f"trades={report.active_trade_metrics.trade_count} "
                f"monthly_expected={report.active_trade_metrics.monthly_expected_return_pct:.2f}% "
                f"win_rate={report.active_trade_metrics.win_rate_pct:.2f}% "
                f"issues={len(report.active_issues)}"
            )
            print(f"report: {report.markdown_path}")
        return 0 if report.verdict == "PASS" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
