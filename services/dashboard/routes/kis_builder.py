"""Compatibility API for the upstream KIS Strategy Builder UI.

The imported UI keeps its upstream /api/* contract. Next.js rewrites route
those calls here under /api/kis-builder/* so the existing dashboard API
contracts are not changed.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from services.dashboard.routes.kis_builder_compat import router as compat_router
from services.dashboard.routes.kis_builder_experiments import (
    router as experiments_router,
)
from services.dashboard.routes.kis_builder_models import (
    ActivityResponse,
    EnableRequest,
    ExecuteOrderRequest,
    ExecuteStrategyRequest,
    RegisteredListResponse,
    RegisteredStrategy,
    RegisterPaperRequest,
    StrategyActivity,
)
from shared.strategy_builder.runtime_support import streaming_support_reason
from shared.strategy_builder.schema import BuilderState

router = APIRouter(prefix="/api/kis-builder", tags=["kis-builder"])
router.include_router(compat_router)
router.include_router(experiments_router)

__all__ = [
    "ActivityResponse",
    "EnableRequest",
    "ExecuteOrderRequest",
    "ExecuteStrategyRequest",
    "RegisterPaperRequest",
    "RegisteredListResponse",
    "RegisteredStrategy",
    "StrategyActivity",
    "account_balance",
    "account_holdings",
    "account_info",
    "auth_status",
    "build_strategy",
    "buyable_amount",
    "cancel_order",
    "clear_account_cache",
    "collect_symbols",
    "current_price",
    "download_template",
    "execute_order",
    "execute_strategy",
    "file_template",
    "file_templates",
    "import_file",
    "list_custom_strategies",
    "list_indicators",
    "list_registered_strategies",
    "list_strategies",
    "login",
    "logout",
    "orderbook",
    "orders_account",
    "pending_orders",
    "preview_code_from_state",
    "preview_strategy",
    "register_paper_strategy",
    "registered_activity",
    "router",
    "search_symbols",
    "stock_builder_preset_experiment_report",
    "switch_mode",
    "symbol_by_code",
    "symbol_status",
    "toggle_registered_strategy",
    "unregister_strategy",
]

from services.dashboard.routes.kis_builder_compat import (  # noqa: E402,F401
    account_balance,
    account_holdings,
    account_info,
    auth_status,
    build_strategy,
    buyable_amount,
    cancel_order,
    clear_account_cache,
    collect_symbols,
    current_price,
    download_template,
    execute_order,
    execute_strategy,
    file_template,
    file_templates,
    import_file,
    list_custom_strategies,
    list_indicators,
    list_strategies,
    login,
    logout,
    orderbook,
    orders_account,
    pending_orders,
    preview_code_from_state,
    preview_strategy,
    search_symbols,
    switch_mode,
    symbol_by_code,
    symbol_status,
)
from services.dashboard.routes.kis_builder_experiments import (  # noqa: E402,F401
    stock_builder_preset_experiment_report,
)

_BUILT_STRATEGIES_DIR = Path(
    os.environ.get("KIS_BUILT_STRATEGIES_DIR", "config/strategies/built")
)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def _safe_id(raw: str) -> str:
    """Reject ids that would escape the built-strategies directory."""
    if not _ID_PATTERN.match(raw):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid strategy id: must be 3-64 chars of "
                "alphanumeric/underscore/hyphen"
            ),
        )
    return raw


def _strategy_path(strategy_id: str) -> Path:
    return _BUILT_STRATEGIES_DIR / f"{strategy_id}.yaml"


def _load_strategy_file(strategy_id: str) -> dict[str, Any]:
    path = _strategy_path(strategy_id)
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"Strategy not registered: {strategy_id}"
        )
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _streaming_unsupported_reason(strategy: dict[str, Any]) -> str | None:
    """Return why a built strategy cannot fire in the streaming runtime.

    Inspects the persisted ``builder_state`` (under entry.params) for
    streaming-unsupported operators (cross_above/cross_below). Returns ``None``
    when the strategy is safe to enable, or when the doc is not a builder_v1
    strategy / has no parseable state (don't block non-builder strategies).
    """
    entry = strategy.get("entry", {})
    if entry.get("type") != "builder_v1":
        return None
    raw_state = entry.get("params", {}).get("builder_state")
    if not isinstance(raw_state, dict):
        return None
    try:
        state = BuilderState.model_validate(raw_state)
    except Exception:  # noqa: BLE001 — a corrupt state shouldn't block disabling
        return None
    return streaming_support_reason(state)


def _validate_builder_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Reuse the schema validator from shared.strategy_builder.

    Raises HTTPException(400) on parse failure so the operator sees a clean
    message instead of a 500.
    """
    try:
        from shared.strategy_builder.schema import BuilderState

        state = BuilderState.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Invalid BuilderState: {exc}"
        ) from exc
    # Builder→paper supports stock and (long-only, paper) futures. Futures
    # live activation stays behind config/futures_live.yaml + the Redis
    # suspend flag — registration only materializes a paper YAML.
    if state.asset_class not in ("stock", "futures"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported asset_class: {state.asset_class!r} "
                "(expected 'stock' or 'futures')."
            ),
        )
    # `mode="json"` dumps StrEnum values as plain strings so yaml.safe_dump
    # can serialize the result without a custom representer. Datetimes/UUIDs
    # are similarly coerced into strings.
    return state.model_dump(mode="json")


def _build_strategy_yaml(
    *,
    state: dict[str, Any],
    stop_loss_pct: float,
    take_profit_pct: float,
    trailing_stop_pct: float,
    order_amount: int,
    contracts: int = 1,
    cooldown_seconds: int,
    min_confidence: float,
    enabled: bool = False,
) -> dict[str, Any]:
    """Materialize the YAML dict the builder_v1 classes will consume."""
    metadata = state.get("metadata", {})
    asset_class = state.get("asset_class", "stock")
    if asset_class == "futures":
        position = {"type": "fixed", "params": {"fixed_quantity": contracts}}
    else:
        position = {"type": "fixed", "params": {"order_amount_per_stock": order_amount}}
    return {
        "strategy": {
            "name": metadata.get("id", "built"),
            "asset_class": state.get("asset_class", "stock"),
            "enabled": enabled,
            "description": metadata.get("description") or metadata.get("name", ""),
            "entry": {
                "type": "builder_v1",
                "params": {
                    "builder_state": state,
                    "cooldown_seconds": cooldown_seconds,
                    "min_confidence": min_confidence,
                },
            },
            "exit": {
                "type": "builder_v1_exit",
                "params": {
                    "builder_state": state,
                    "stop_loss_pct": stop_loss_pct,
                    "take_profit_pct": take_profit_pct,
                    "trailing_stop_pct": trailing_stop_pct,
                    "min_confidence": min_confidence,
                },
            },
            "position": position,
            "_builder_meta": {
                "registered_at": datetime.now(UTC).isoformat(),
                "schema_version": "builder_v1",
                "source": "kis-builder/register-paper",
            },
        }
    }


@router.post("/register-paper", response_model=RegisteredStrategy)
async def register_paper_strategy(body: RegisterPaperRequest) -> RegisteredStrategy:
    """Materialize a BuilderState as config/strategies/built/<id>.yaml."""
    state = _validate_builder_state(body.builder_state)
    metadata = state.get("metadata", {})
    raw_id = str(metadata.get("id") or "")
    strategy_id = _safe_id(raw_id)

    # Trailing stop: explicit request value wins; otherwise honor the draft's
    # risk.trailing_stop toggle (enabled → percent, disabled → 0 = off).
    if body.trailing_stop_pct is not None:
        trailing_stop_pct = body.trailing_stop_pct
    else:
        trailing = state.get("risk", {}).get("trailing_stop", {})
        trailing_stop_pct = (
            float(trailing.get("percent", 0.0)) if trailing.get("enabled") else 0.0
        )

    _BUILT_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    yaml_doc = _build_strategy_yaml(
        state=state,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
        trailing_stop_pct=trailing_stop_pct,
        order_amount=body.order_amount,
        contracts=body.contracts,
        cooldown_seconds=body.cooldown_seconds,
        min_confidence=body.min_confidence,
        enabled=False,  # Phase-1 safe default
    )
    path = _strategy_path(strategy_id)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(yaml_doc, fh, allow_unicode=True, sort_keys=False)

    return RegisteredStrategy(
        id=strategy_id,
        name=metadata.get("name") or strategy_id,
        description=metadata.get("description") or None,
        asset_class=state.get("asset_class", "stock"),
        enabled=False,
        registered_at=yaml_doc["strategy"]["_builder_meta"]["registered_at"],
        path=str(path),
    )


@router.get("/registered", response_model=RegisteredListResponse)
async def list_registered_strategies() -> RegisteredListResponse:
    """List all built strategies (registered + enable status)."""
    if not _BUILT_STRATEGIES_DIR.exists():
        return RegisteredListResponse(strategies=[], total=0)

    items: list[RegisteredStrategy] = []
    for path in sorted(_BUILT_STRATEGIES_DIR.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
        except Exception:  # noqa: BLE001 — skip corrupt files
            continue
        strategy = doc.get("strategy", {})
        meta = strategy.get("_builder_meta", {})
        items.append(
            RegisteredStrategy(
                id=path.stem,
                name=strategy.get("name", path.stem),
                description=strategy.get("description") or None,
                asset_class=strategy.get("asset_class", "stock"),
                enabled=bool(strategy.get("enabled", False)),
                registered_at=meta.get("registered_at"),
                path=str(path),
            )
        )
    return RegisteredListResponse(strategies=items, total=len(items))


@router.post("/registered/{strategy_id}/enable", response_model=RegisteredStrategy)
async def toggle_registered_strategy(
    strategy_id: str, body: EnableRequest
) -> RegisteredStrategy:
    """Flip strategy.enabled and write back.

    Enabling is refused for builder_v1 strategies whose conditions use
    cross_above/cross_below: the decoupled streaming runtime cannot detect
    those (no cross-cycle history series), so the strategy would be enabled but
    permanently silent. Disabling is always allowed.
    """
    safe_id = _safe_id(strategy_id)
    doc = _load_strategy_file(safe_id)
    strategy = doc.setdefault("strategy", {})

    if bool(body.enabled):
        reason = _streaming_unsupported_reason(strategy)
        if reason is not None:
            raise HTTPException(status_code=400, detail=reason)

    strategy["enabled"] = bool(body.enabled)
    with _strategy_path(safe_id).open("w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False)

    meta = strategy.get("_builder_meta", {})
    return RegisteredStrategy(
        id=safe_id,
        name=strategy.get("name", safe_id),
        description=strategy.get("description") or None,
        asset_class=strategy.get("asset_class", "stock"),
        enabled=strategy["enabled"],
        registered_at=meta.get("registered_at"),
        path=str(_strategy_path(safe_id)),
    )


@router.delete("/registered/{strategy_id}")
async def unregister_strategy(strategy_id: str) -> dict[str, Any]:
    """Delete the YAML file for a built strategy."""
    safe_id = _safe_id(strategy_id)
    path = _strategy_path(safe_id)
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"Strategy not registered: {safe_id}"
        )
    path.unlink()
    return {"id": safe_id, "deleted": True}


def _registered_ids() -> list[str]:
    if not _BUILT_STRATEGIES_DIR.exists():
        return []
    return [path.stem for path in sorted(_BUILT_STRATEGIES_DIR.glob("*.yaml"))]


def _signal_counts() -> dict[str, int]:
    """Count recent stock signals grouped by strategy (Redis).

    Returns {} if Redis is unavailable so the panel degrades to zero counts
    rather than 500-ing. The Redis list is a recent window (capped), so this
    is a recent-activity indicator, not a lifetime total.
    """
    try:
        from shared.streaming.trading_state import TradingStateReader

        signals = TradingStateReader("stock").get_signals(start=0, count=500)
    except Exception:  # noqa: BLE001 — degrade gracefully on infra failure
        return {}
    counts: dict[str, int] = {}
    for sig in signals:
        strat = str(sig.get("strategy") or "")
        if strat:
            counts[strat] = counts.get(strat, 0) + 1
    return counts


def _trade_counts(ids: list[str]) -> dict[str, int]:
    """Count closed stock trades per strategy from RuntimeLedger.

    Only the given ids are queried. Returns {} on any failure so the panel still
    renders.
    """
    if not ids:
        return {}
    try:
        from shared.storage.config import StorageConfig
        from shared.storage.runtime_ledger import SQLiteRuntimeLedger

        config = StorageConfig.load_or_default()
        db_path = Path(config.runtime_storage.sqlite.path)
        if not db_path.exists() or db_path.is_dir():
            return {}
        ledger = SQLiteRuntimeLedger(config.runtime_storage.sqlite)
        try:
            rows = ledger.query_trades({"asset_class": "stock", "limit": 10_000})
        finally:
            ledger.close()
    except Exception:  # noqa: BLE001 — degrade gracefully on infra failure
        return {}
    wanted = set(ids)
    counts: dict[str, int] = {}
    for row in rows:
        strategy = str(row.get("strategy") or "")
        if strategy in wanted:
            counts[strategy] = counts.get(strategy, 0) + 1
    return counts


@router.get("/registered/activity", response_model=ActivityResponse)
async def registered_activity() -> ActivityResponse:
    """Per-strategy recent signal + closed-trade counts for the panel.

    Signals come from Redis (recent window), trades from RuntimeLedger. Both
    sources degrade to zero on infra failure so the panel always renders.
    """
    ids = _registered_ids()
    signal_counts = _signal_counts()
    trade_counts = _trade_counts(ids)
    return ActivityResponse(
        activity=[
            StrategyActivity(
                id=sid,
                signals=signal_counts.get(sid, 0),
                trades=trade_counts.get(sid, 0),
            )
            for sid in ids
        ]
    )
