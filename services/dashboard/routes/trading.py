"""Trading status and control endpoints."""

import json
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.dashboard.domain import assets as asset_domain
from shared.exceptions import InfrastructureError

VALID_ASSET = asset_domain.VALID_ASSET
ASSET_CLASSES = asset_domain.ASSET_CLASSES
normalize_asset_class = asset_domain.normalize_asset_class
target_assets = asset_domain.target_assets
_normalize_asset_class = asset_domain.normalize_asset_class
_target_assets = asset_domain.target_assets


def _parse_tz_aware(value: str | None) -> datetime:
    """Parse an ISO timestamp into tz-aware UTC, or fall back to now(UTC).

    Same convention as services/dashboard/routes/signals.py and trades.py
    — the dashboard emits tz-aware UTC throughout so downstream
    comparisons never hit "can't compare offset-naive and offset-aware".
    """
    if value is None:
        return datetime.now(UTC)
    try:
        ts = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.now(UTC)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


router = APIRouter(prefix="/api/trading", tags=["trading"])


class AccountSummary(BaseModel):
    """Paper engine 계좌 스냅샷 — Cockpit Equity·Cash 카드 데이터 소스.

    KIS 선물 모의서버는 잔고조회 API(CTFO6118R) 미지원이므로 paper
    engine(VirtualBroker)이 유일한 진실의 원천이다.  Live 모드 또는 broker
    미연결 시에는 상위 ``TradingStatus.account`` 가 ``None`` 으로 응답된다.
    """

    initial_balance: float
    balance: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int


class TradingStatus(BaseModel):
    """Trading system status response."""

    asset_class: str = "futures"
    is_running: bool
    market_status: str
    active_strategies: list[str]
    total_positions: int
    total_pnl: float
    unrealized_pnl: float
    closed_trades: int
    closed_pnl: float
    closed_win_rate: float
    last_update: datetime
    account: AccountSummary | None = None


class PositionResponse(BaseModel):
    """Position response model."""

    asset_class: str
    code: str
    name: str
    side: str
    quantity: int
    entry_price: float
    current_price: float
    market_value_krw: float | None = None
    unrealized_pnl: float
    pnl_pct: float
    entry_time: datetime
    strategy: str


class RiskPortfolio(BaseModel):
    """Portfolio-level risk and exposure snapshot."""

    equity_krw: float | None
    cash_krw: float | None
    gross_exposure_krw: float
    net_exposure_krw: float
    unrealized_pnl_krw: float
    realized_pnl_krw: float | None
    daily_pnl_krw: float
    daily_loss_krw: float
    open_positions: int
    exposure_to_equity_pct: float | None
    last_update: datetime


class RiskStrategyExposure(BaseModel):
    """Strategy-level exposure group."""

    asset_class: str
    strategy: str
    positions: int
    gross_exposure_krw: float
    net_exposure_krw: float
    unrealized_pnl_krw: float
    exposure_to_equity_pct: float | None


class RiskSymbolExposure(BaseModel):
    """Symbol-level exposure row for the dashboard risk board."""

    asset_class: str
    code: str
    name: str
    side: str
    quantity: int
    current_price: float
    market_value_krw: float
    signed_exposure_krw: float
    unrealized_pnl_krw: float
    pnl_pct: float
    strategy: str


class RiskExposureResponse(BaseModel):
    """Risk board response model."""

    asset_class: str
    generated_at: datetime
    portfolio: RiskPortfolio
    by_strategy: list[RiskStrategyExposure]
    by_symbol: list[RiskSymbolExposure]
    notes: list[str]


def _get_reader(asset_class: str | None = None):
    """Get TradingStateReader for the configured asset class."""
    from shared.streaming.trading_state import TradingStateReader

    asset = asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _empty_status(asset_class: str) -> TradingStatus:
    return TradingStatus(
        asset_class=asset_class,
        is_running=False,
        market_status="closed",
        active_strategies=[],
        total_positions=0,
        total_pnl=0.0,
        unrealized_pnl=0.0,
        closed_trades=0,
        closed_pnl=0.0,
        closed_win_rate=0.0,
        last_update=datetime.now(UTC),
    )


def _coerce_account(account_raw: object) -> AccountSummary | None:
    if isinstance(account_raw, str):
        try:
            account_raw = json.loads(account_raw)
        except (ValueError, TypeError):
            account_raw = None

    if not isinstance(account_raw, dict):
        return None

    try:
        return AccountSummary(
            initial_balance=float(account_raw.get("initial_balance", 0.0)),
            balance=float(account_raw.get("balance", 0.0)),
            equity=float(account_raw.get("equity", 0.0)),
            realized_pnl=float(account_raw.get("realized_pnl", 0.0)),
            unrealized_pnl=float(account_raw.get("unrealized_pnl", 0.0)),
            open_positions=int(account_raw.get("open_positions", 0)),
        )
    except (TypeError, ValueError):
        return None


def _read_status(asset_class: str) -> dict:
    try:
        reader = _get_reader(asset_class)
        return reader.get_status()
    except InfrastructureError:
        return {}


def _read_positions(asset_class: str) -> list[PositionResponse]:
    try:
        reader = _get_reader(asset_class)
        positions = reader.get_positions()
    except InfrastructureError:
        positions = []

    result: list[PositionResponse] = []
    for p in positions:
        try:
            market_value = (
                p.get("market_value_krw")
                or p.get("market_value")
                or p.get("notional_value_krw")
                or p.get("notional_value")
            )
            result.append(
                PositionResponse(
                    asset_class=asset_class,
                    code=p.get("code", ""),
                    name=p.get("name", ""),
                    side=p.get("side", "long"),
                    quantity=int(p.get("quantity", 0)),
                    entry_price=float(p.get("entry_price", 0)),
                    current_price=float(p.get("current_price", 0)),
                    market_value_krw=(
                        float(market_value) if market_value is not None else None
                    ),
                    unrealized_pnl=float(p.get("unrealized_pnl", 0)),
                    pnl_pct=float(p.get("pnl_pct", 0)),
                    entry_time=_parse_tz_aware(p.get("entry_time")),
                    strategy=p.get("strategy", ""),
                )
            )
        except (ValueError, TypeError, KeyError):
            continue
    return result


def _side_sign(side: str) -> float:
    """Return +1 for long/buy and -1 for short/sell positions."""
    return -1.0 if str(side).strip().lower() in {"short", "sell"} else 1.0


def _raw_position_value(position: PositionResponse) -> float:
    if position.market_value_krw is not None:
        return abs(float(position.market_value_krw))
    return abs(float(position.current_price) * float(position.quantity))


def _status_response_from_raw(asset_class: str, status: dict) -> TradingStatus:
    if not status:
        return _empty_status(asset_class)

    state = status.get("state", "stopped").lower()
    config = status.get("config", {})
    stats = status.get("stats", {})
    positions = status.get("positions", {})

    # config/stats/positions may be JSON strings from Redis HASH
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            config = {}
    if isinstance(stats, str):
        try:
            stats = json.loads(stats)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            stats = {}
    if isinstance(positions, str):
        try:
            positions = json.loads(positions)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            positions = {}

    strategies = [config.get("strategy", "")] if config.get("strategy") else []
    # Collect strategy names from strategies dict if available
    strats_info = status.get("strategies", {})
    if isinstance(strats_info, str):
        try:
            strats_info = json.loads(strats_info)
        except (ValueError, TypeError):
            # Invalid JSON - use empty dict
            strats_info = {}
    if isinstance(strats_info, dict) and strats_info.get("strategies"):
        strategies = strats_info["strategies"]

    start_time = stats.get("start_time")
    updated_at = status.get("updated_at") or start_time

    account_obj = _coerce_account(status.get("account"))

    return TradingStatus(
        asset_class=asset_class,
        is_running=state in ("running", "waiting"),
        market_status=status.get("regime") or "unknown",
        active_strategies=strategies,
        total_positions=(
            positions.get("open_positions", 0) if isinstance(positions, dict) else 0
        ),
        total_pnl=float(stats.get("total_pnl", 0)),
        unrealized_pnl=(
            float(positions.get("unrealized_pnl", 0))
            if isinstance(positions, dict)
            else 0.0
        ),
        closed_trades=(
            int(positions.get("closed_count", 0)) if isinstance(positions, dict) else 0
        ),
        closed_pnl=(
            float(positions.get("closed_pnl", 0))
            if isinstance(positions, dict)
            else 0.0
        ),
        closed_win_rate=(
            float(positions.get("closed_win_rate", 0))
            if isinstance(positions, dict)
            else 0.0
        ),
        last_update=_parse_tz_aware(updated_at),
        account=account_obj,
    )


def _aggregate_statuses(statuses: list[TradingStatus]) -> TradingStatus:
    if not statuses:
        return _empty_status("all")

    strategy_names = sorted(
        {s for status in statuses for s in status.active_strategies if s}
    )
    market_statuses = {
        status.market_status for status in statuses if status.market_status
    }
    closed_trades = sum(status.closed_trades for status in statuses)
    closed_pnl = sum(status.closed_pnl for status in statuses)
    winning_estimate = sum(
        status.closed_trades * status.closed_win_rate / 100.0 for status in statuses
    )

    accounts = [status.account for status in statuses if status.account is not None]
    account = None
    if accounts:
        account = AccountSummary(
            initial_balance=sum(a.initial_balance for a in accounts),
            balance=sum(a.balance for a in accounts),
            equity=sum(a.equity for a in accounts),
            realized_pnl=sum(a.realized_pnl for a in accounts),
            unrealized_pnl=sum(a.unrealized_pnl for a in accounts),
            open_positions=sum(a.open_positions for a in accounts),
        )

    return TradingStatus(
        asset_class="all",
        is_running=any(status.is_running for status in statuses),
        market_status=(
            next(iter(market_statuses)) if len(market_statuses) == 1 else "mixed"
        ),
        active_strategies=strategy_names,
        total_positions=sum(status.total_positions for status in statuses),
        total_pnl=sum(status.total_pnl for status in statuses),
        unrealized_pnl=sum(status.unrealized_pnl for status in statuses),
        closed_trades=closed_trades,
        closed_pnl=closed_pnl,
        closed_win_rate=(
            winning_estimate / closed_trades * 100.0 if closed_trades else 0.0
        ),
        last_update=max(
            (status.last_update for status in statuses), default=datetime.now(UTC)
        ),
        account=account,
    )


def _exposure_pct(value: float, equity: float | None) -> float | None:
    if equity is None or equity <= 0:
        return None
    return value / equity * 100.0


def _risk_response_from_state(
    asset_class: str,
    statuses: list[TradingStatus],
    positions: list[PositionResponse],
) -> RiskExposureResponse:
    status = _aggregate_statuses(statuses) if asset_class == "all" else statuses[0]
    account = status.account
    equity = account.equity if account else None
    cash = account.balance if account else None

    by_symbol: list[RiskSymbolExposure] = []
    strategy_rows: dict[tuple[str, str], dict[str, float | int | str]] = {}
    gross_exposure = 0.0
    net_exposure = 0.0
    unrealized_pnl = 0.0
    notes: list[str] = []

    for position in positions:
        market_value = _raw_position_value(position)
        signed_exposure = market_value * _side_sign(position.side)
        gross_exposure += market_value
        net_exposure += signed_exposure
        unrealized_pnl += position.unrealized_pnl

        by_symbol.append(
            RiskSymbolExposure(
                asset_class=position.asset_class,
                code=position.code,
                name=position.name,
                side=position.side,
                quantity=position.quantity,
                current_price=position.current_price,
                market_value_krw=market_value,
                signed_exposure_krw=signed_exposure,
                unrealized_pnl_krw=position.unrealized_pnl,
                pnl_pct=position.pnl_pct,
                strategy=position.strategy or "unknown",
            )
        )

        key = (position.asset_class, position.strategy or "unknown")
        row = strategy_rows.setdefault(
            key,
            {
                "asset_class": position.asset_class,
                "strategy": position.strategy or "unknown",
                "positions": 0,
                "gross_exposure_krw": 0.0,
                "net_exposure_krw": 0.0,
                "unrealized_pnl_krw": 0.0,
            },
        )
        row["positions"] = int(row["positions"]) + 1
        row["gross_exposure_krw"] = float(row["gross_exposure_krw"]) + market_value
        row["net_exposure_krw"] = float(row["net_exposure_krw"]) + signed_exposure
        row["unrealized_pnl_krw"] = (
            float(row["unrealized_pnl_krw"]) + position.unrealized_pnl
        )

    realized_pnl: float | None
    if account:
        realized_pnl = account.realized_pnl
    else:
        realized_pnl = status.closed_pnl
        notes.append("account data is unavailable; realized PnL uses status.closed_pnl")

    if any(
        position.asset_class == "futures" and position.market_value_krw is None
        for position in positions
    ):
        notes.append(
            "futures exposure uses current_price * quantity when no explicit notional is published"
        )

    daily_pnl = (realized_pnl or 0.0) + unrealized_pnl
    by_strategy = [
        RiskStrategyExposure(
            asset_class=str(row["asset_class"]),
            strategy=str(row["strategy"]),
            positions=int(row["positions"]),
            gross_exposure_krw=float(row["gross_exposure_krw"]),
            net_exposure_krw=float(row["net_exposure_krw"]),
            unrealized_pnl_krw=float(row["unrealized_pnl_krw"]),
            exposure_to_equity_pct=_exposure_pct(
                float(row["gross_exposure_krw"]), equity
            ),
        )
        for row in sorted(
            strategy_rows.values(),
            key=lambda r: (str(r["asset_class"]), str(r["strategy"])),
        )
    ]

    return RiskExposureResponse(
        asset_class=asset_class,
        generated_at=datetime.now(UTC),
        portfolio=RiskPortfolio(
            equity_krw=equity,
            cash_krw=cash,
            gross_exposure_krw=gross_exposure,
            net_exposure_krw=net_exposure,
            unrealized_pnl_krw=unrealized_pnl,
            realized_pnl_krw=realized_pnl,
            daily_pnl_krw=daily_pnl,
            daily_loss_krw=min(0.0, daily_pnl),
            open_positions=len(positions),
            exposure_to_equity_pct=_exposure_pct(gross_exposure, equity),
            last_update=status.last_update,
        ),
        by_strategy=by_strategy,
        by_symbol=sorted(
            by_symbol, key=lambda row: (row.asset_class, row.strategy, row.code)
        ),
        notes=notes,
    )


@router.get("/status", response_model=TradingStatus)
async def get_trading_status(
    asset_class: str = Query(default="futures"),
):
    """Get current trading system status for one asset class or the merged view."""
    asset = _normalize_asset_class(asset_class)
    statuses = [
        _status_response_from_raw(target, _read_status(target))
        for target in _target_assets(asset)
    ]
    return _aggregate_statuses(statuses) if asset == "all" else statuses[0]


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    asset_class: str = Query(default="futures"),
):
    """Get all open positions."""
    asset = _normalize_asset_class(asset_class)
    result: list[PositionResponse] = []
    for target in _target_assets(asset):
        result.extend(_read_positions(target))
    return result


@router.get("/risk-exposure", response_model=RiskExposureResponse)
async def get_risk_exposure(
    asset_class: str = Query(default="all"),
):
    """Get risk/exposure snapshot for the dashboard risk board."""
    asset = _normalize_asset_class(asset_class)
    targets = _target_assets(asset)
    statuses = [
        _status_response_from_raw(target, _read_status(target)) for target in targets
    ]
    positions: list[PositionResponse] = []
    for target in targets:
        positions.extend(_read_positions(target))
    return _risk_response_from_state(asset, statuses, positions)


@router.post("/start")
async def start_trading(
    asset_class: str = Query(default="futures"),
):
    """Start trading system (placeholder — orchestrator runs as CLI)."""
    _normalize_asset_class(asset_class)
    return {"status": "use CLI: sts trade start"}


@router.post("/stop")
async def stop_trading(
    asset_class: str = Query(default="futures"),
):
    """Stop trading system (placeholder — orchestrator runs as CLI)."""
    _normalize_asset_class(asset_class)
    return {"status": "use CLI: sts trade stop"}


@router.post("/kill-switch")
async def trigger_kill_switch() -> dict:
    """Manually trigger kill switch from dashboard UI.

    Publishes ``kill_switch:force_flatten:requested`` on Redis so the
    kill-switch service flattens all positions. If Redis is unavailable
    we return ``triggered: false`` instead of raising — the UI should
    surface the error but the API itself must not blow up.
    """
    try:
        from shared.streaming.client import RedisClient

        redis = RedisClient.get_client()
        redis.publish("kill_switch:force_flatten:requested", "manual_dashboard")
        return {"triggered": True, "at": datetime.now(UTC).isoformat()}
    except Exception as e:  # noqa: BLE001 — keep UI resilient on infra failure
        return {
            "triggered": False,
            "error": str(e),
            "at": datetime.now(UTC).isoformat(),
        }
