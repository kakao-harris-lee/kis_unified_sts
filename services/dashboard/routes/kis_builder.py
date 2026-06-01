"""Compatibility API for the upstream KIS Strategy Builder UI.

The imported UI keeps its upstream /api/* contract. Next.js rewrites route
those calls here under /api/kis-builder/* so the existing dashboard API
contracts are not changed.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from shared.config.loader import ConfigLoader
from shared.strategy_builder.evaluator import StrategyBuilderEvaluator
from shared.strategy_builder.kis_compat import (
    apply_kis_preset_params,
    build_sample_series_for_state,
    get_kis_preset,
    kis_state_to_builder_state,
    list_kis_strategy_infos,
)
from shared.strategy_builder.yaml_io import (
    builder_state_to_yaml,
    preview_python,
    yaml_to_builder_state,
)

router = APIRouter(prefix="/api/kis-builder", tags=["kis-builder"])


class ExecuteStrategyRequest(BaseModel):
    strategy_id: str
    stocks: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    builder_state: dict[str, Any] | None = None


class ExecuteOrderRequest(BaseModel):
    stock_code: str
    stock_name: str | None = None
    action: str
    order_type: str = "limit"
    price: float = 0
    quantity: int = Field(default=1, ge=1)
    signal_reason: str | None = None


def _log(level: str, message: str) -> dict[str, str]:
    return {
        "type": level,
        "message": message,
        "timestamp": datetime.now(UTC).strftime("%H:%M:%S"),
    }


@router.get("/auth/status")
async def auth_status() -> dict[str, Any]:
    return {
        "authenticated": True,
        "mode": "vps",
        "mode_display": "모의투자",
        "can_switch_mode": False,
        "cooldown_remaining": 0,
    }


@router.post("/auth/login")
async def login(request: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = request or {}
    return {
        "status": "success",
        "authenticated": True,
        "mode": "vps",
        "mode_display": "모의투자",
        "can_switch_mode": False,
        "cooldown_remaining": 0,
    }


@router.post("/auth/switch-mode")
async def switch_mode(request: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = request or {}
    return {
        "status": "success",
        "message": "STS Strategy Builder는 모의투자/페이퍼 실행만 지원합니다.",
        "authenticated": True,
        "mode": "vps",
        "mode_display": "모의투자",
        "can_switch_mode": False,
        "cooldown_remaining": 0,
    }


@router.post("/auth/logout")
async def logout() -> dict[str, str]:
    return {"status": "success", "message": "paper session retained"}


@router.get("/strategies")
async def list_strategies() -> dict[str, Any]:
    strategies = list_kis_strategy_infos()
    return {"strategies": strategies, "total": len(strategies)}


@router.get("/strategies/custom")
async def list_custom_strategies() -> dict[str, list[Any]]:
    return {"strategies": []}


@router.get("/strategies/indicators")
async def list_indicators() -> dict[str, Any]:
    return {
        "indicators": [
            {
                "name": "ma",
                "label": "이동평균",
                "params": ["period"],
                "example": "ma(20)",
            },
            {
                "name": "ema",
                "label": "지수이동평균",
                "params": ["period"],
                "example": "ema(12)",
            },
            {"name": "rsi", "label": "RSI", "params": ["period"], "example": "rsi(14)"},
            {
                "name": "macd",
                "label": "MACD",
                "params": ["fast", "slow", "signal"],
                "example": "macd(12,26,9)",
            },
            {
                "name": "williams_r",
                "label": "Williams %R",
                "params": ["period"],
                "example": "williams_r(14)",
            },
            {
                "name": "stochastic",
                "label": "스토캐스틱",
                "params": ["k_period", "d_period"],
                "example": "stochastic(14,3)",
            },
            {
                "name": "bollinger",
                "label": "볼린저 밴드",
                "params": ["period", "std"],
                "example": "bollinger(20,2)",
            },
            {"name": "vwap", "label": "VWAP", "params": [], "example": "vwap()"},
            {"name": "adx", "label": "ADX", "params": ["period"], "example": "adx(14)"},
            {
                "name": "donchian",
                "label": "돈치안 채널",
                "params": ["period"],
                "example": "donchian(20)",
            },
            {
                "name": "ichimoku",
                "label": "이치모쿠",
                "params": ["conversion", "base", "span_b"],
                "example": "ichimoku(9,26,52)",
            },
            {
                "name": "supertrend",
                "label": "SuperTrend",
                "params": ["period", "multiplier"],
                "example": "supertrend(10,3)",
            },
            {
                "name": "keltner",
                "label": "켈트너 채널",
                "params": ["period", "multiplier"],
                "example": "keltner(20,2)",
            },
            {"name": "cci", "label": "CCI", "params": ["period"], "example": "cci(20)"},
            {"name": "mfi", "label": "MFI", "params": ["period"], "example": "mfi(14)"},
            {"name": "obv", "label": "OBV", "params": [], "example": "obv()"},
            {
                "name": "trix",
                "label": "TRIX",
                "params": ["period"],
                "example": "trix(15)",
            },
            {
                "name": "engulfing",
                "label": "장악형 캔들",
                "params": [],
                "example": "engulfing()",
            },
            {
                "name": "disparity",
                "label": "이격도",
                "params": ["period"],
                "example": "disparity(20)",
            },
            {
                "name": "breakout_margin",
                "label": "돌파 여유율",
                "params": ["period"],
                "example": "breakout_margin(252)",
            },
        ],
        "variables": ["close", "open", "high", "low", "volume", "change"],
        "operators": {
            "comparison": [">", "<", ">=", "<=", "=="],
            "crossover": ["crosses_above", "crosses_below"],
            "logical": ["AND", "OR"],
        },
    }


@router.post("/strategies/preview-code")
async def preview_code_from_state(request: dict[str, Any]) -> dict[str, Any]:
    try:
        state = kis_state_to_builder_state(request.get("builder_state", {}))
        return {
            "status": "success",
            "code": preview_python(state),
            "buy_dsl": "",
            "sell_dsl": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}


@router.post("/strategies/preview")
async def preview_strategy(request: dict[str, Any]) -> dict[str, Any]:
    name = str(request.get("name") or "custom_strategy")
    return {
        "status": "success",
        "code": f"# DSL preview for {name}\n# Use the visual Builder YAML preview for full strategy state.\n",
        "required_days": 2,
    }


@router.post("/strategies/build")
async def build_strategy(request: dict[str, Any]) -> dict[str, Any]:
    name = str(request.get("name") or "custom_strategy")
    return {
        "status": "success",
        "message": f"{name} strategy preview generated. Persistent file writes are disabled.",
        "strategy_name": name,
    }


@router.post("/strategies/execute")
async def execute_strategy(request: ExecuteStrategyRequest) -> dict[str, Any]:
    logs: list[dict[str, str]] = []
    if not request.stocks:
        return {
            "status": "error",
            "results": [],
            "logs": logs,
            "message": "종목을 입력해주세요",
        }

    if request.builder_state:
        source_state = request.builder_state
        strategy_name = source_state.get("metadata", {}).get(
            "name", request.strategy_id
        )
    else:
        preset = get_kis_preset(request.strategy_id)
        if preset is None:
            return {
                "status": "error",
                "results": [],
                "logs": [_log("error", f"알 수 없는 전략: {request.strategy_id}")],
                "message": f"알 수 없는 전략: {request.strategy_id}",
            }
        source_state = apply_kis_preset_params(preset, request.params)
        strategy_name = str(preset.get("name") or request.strategy_id)

    state = kis_state_to_builder_state(source_state)
    evaluator = StrategyBuilderEvaluator()
    logs.append(_log("info", f"페이퍼 전략: {strategy_name}"))
    logs.append(_log("info", f"종목: {', '.join(request.stocks)}"))

    results: list[dict[str, Any]] = []
    for symbol in request.stocks:
        series = build_sample_series_for_state(state, symbol=symbol, name=symbol)
        signal = evaluator.generate_signals(state, [series])[0]
        results.append(
            {
                "code": symbol,
                "name": symbol,
                "action": signal.side.value,
                "strength": signal.strength,
                "reason": signal.reason,
                "target_price": int(signal.reference_price),
            }
        )
        logs.append(
            _log(
                "success" if signal.side.value == "BUY" else "info",
                f"{symbol}: {signal.side.value} | 강도 {signal.strength:.2f} | {signal.reason}",
            )
        )

    return {"status": "success", "results": results, "logs": logs}


@router.get("/account/info")
async def account_info() -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "account_no": "PAPER",
            "account_no_full": "PAPER-STRATEGY-BUILDER",
            "account_type": "paper",
            "prod_code": "01",
            "is_vps": True,
            "mode": "vps",
        },
    }


@router.get("/account/holdings")
async def account_holdings() -> dict[str, Any]:
    return {"status": "success", "data": []}


@router.get("/account/balance")
async def account_balance() -> dict[str, Any]:
    balance = {
        "deposit": 10_000_000,
        "total_eval": 10_000_000,
        "purchase_amount": 0,
        "eval_amount": 0,
        "profit_loss": 0,
        "deposit_formatted": "10,000,000원",
        "total_eval_formatted": "10,000,000원",
        "profit_loss_formatted": "0원",
    }
    return {"status": "success", "data": balance}


@router.get("/account/buyable/{stock_code}")
async def buyable_amount(stock_code: str, price: float = 0) -> dict[str, Any]:
    amount = 10_000_000
    quantity = int(amount // price) if price > 0 else 0
    return {
        "status": "success",
        "data": {
            "stock_code": stock_code,
            "price": price,
            "amount": amount,
            "quantity": quantity,
            "amount_formatted": "10,000,000원",
        },
    }


@router.post("/orders/execute")
async def execute_order(request: ExecuteOrderRequest) -> dict[str, Any]:
    order_id = f"paper_{uuid4().hex[:16]}"
    return {
        "status": "success",
        "message": "페이퍼 주문이 접수되었습니다.",
        "data": {"order_id": order_id, "status": "filled", "message": "paper filled"},
        "logs": [
            _log(
                "success",
                f"{request.action} {request.stock_code} x {request.quantity} paper order filled",
            )
        ],
    }


@router.get("/orders/account")
async def orders_account() -> dict[str, Any]:
    return {
        "status": "success",
        "deposit": {
            "deposit": 10_000_000,
            "total_eval": 10_000_000,
            "purchase_amount": 0,
            "eval_amount": 0,
            "profit_loss": 0,
        },
        "holdings": [],
        "holdings_count": 0,
        "cached_at": datetime.now(UTC).isoformat(),
    }


@router.post("/orders/account/clear-cache")
async def clear_account_cache() -> dict[str, str]:
    return {"status": "success", "message": "paper account cache cleared"}


@router.get("/orders/pending")
async def pending_orders() -> dict[str, Any]:
    return {"status": "success", "orders": [], "total_count": 0}


@router.post("/orders/cancel")
async def cancel_order(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "success",
        "success": True,
        "order_no": str(request.get("order_no") or ""),
        "message": "paper order cancellation accepted",
    }


@router.get("/market/price/{stock_code}")
async def current_price(stock_code: str, env_dv: str = "vps") -> dict[str, Any]:
    _ = env_dv
    return {
        "status": "success",
        "data": {
            "price": 100_000,
            "change": 0,
            "change_rate": 0.0,
            "high": 101_000,
            "low": 99_000,
            "volume": 1_000_000,
            "w52_high": 120_000,
            "w52_low": 80_000,
        },
        "message": f"paper quote for {stock_code}",
    }


@router.get("/market/orderbook/{stock_code}")
async def orderbook(stock_code: str, env_dv: str = "vps") -> dict[str, Any]:
    _ = env_dv
    price = 100_000
    return {
        "status": "success",
        "data": {
            "stock_code": stock_code,
            "stock_name": stock_code,
            "current_price": price,
            "ask_prices": [price + 100 * i for i in range(1, 6)],
            "ask_volumes": [1000] * 5,
            "bid_prices": [price - 100 * i for i in range(1, 6)],
            "bid_volumes": [1000] * 5,
            "total_ask_volume": 5000,
            "total_bid_volume": 5000,
            "expected_price": price,
            "expected_volume": 1000,
        },
    }


@router.get("/files/templates")
async def file_templates() -> dict[str, Any]:
    templates = [
        {
            "id": item["id"],
            "name": item["name"],
            "description": item.get("description", ""),
            "category": item.get("category", "custom"),
            "tags": item.get("builder_state", {}).get("metadata", {}).get("tags", []),
        }
        for item in list_kis_strategy_infos()
    ]
    return {"success": True, "data": templates, "total": len(templates)}


@router.get("/files/templates/{template_id}")
async def file_template(template_id: str) -> dict[str, Any]:
    preset = get_kis_preset(template_id)
    if preset is None:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )
    state = kis_state_to_builder_state(preset.get("builder_state", {}))
    return {
        "success": True,
        "data": {
            "id": template_id,
            "name": preset.get("name"),
            "yaml": builder_state_to_yaml(state),
        },
    }


@router.get("/files/templates/{template_id}/download")
async def download_template(template_id: str) -> StreamingResponse:
    preset = get_kis_preset(template_id)
    if preset is None:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )
    state = kis_state_to_builder_state(preset.get("builder_state", {}))
    content = builder_state_to_yaml(state).encode("utf-8")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{template_id}.kis.yaml"'
        },
    )


@router.post("/files/import")
async def import_file(request: dict[str, Any]) -> dict[str, Any]:
    content = str(request.get("yaml") or request.get("content") or "")
    if not content:
        raise HTTPException(status_code=400, detail="yaml content is required")
    state = yaml_to_builder_state(content)
    return {
        "success": True,
        "data": {
            "id": state.metadata.id,
            "name": state.metadata.name,
            "category": state.metadata.category,
            "description": state.metadata.description,
        },
        "message": "imported",
    }


@router.get("/symbols/status")
async def symbol_status() -> dict[str, Any]:
    return {
        "kospi_count": 0,
        "kosdaq_count": 0,
        "total_count": 0,
        "kospi_updated": None,
        "kosdaq_updated": None,
        "needs_update": True,
    }


@router.post("/symbols/collect")
async def collect_symbols() -> dict[str, Any]:
    return {
        "success": True,
        "kospi_count": 0,
        "kosdaq_count": 0,
        "total_count": 0,
        "errors": [],
    }


@router.get("/symbols/search")
async def search_symbols(
    q: str = "", limit: int = 20, exchange: str | None = None
) -> dict[str, Any]:
    _ = exchange
    item = _symbol_item(q) if q else None
    items = [item] if item else []
    return {"query": q, "total": len(items[:limit]), "items": items[:limit]}


@router.get("/symbols/{code}")
async def symbol_by_code(code: str) -> dict[str, Any]:
    return {"status": "success", "data": _symbol_item(code)}


def _symbol_item(code_or_query: str) -> dict[str, str]:
    code = code_or_query.strip()
    if not code:
        code = "000000"
    return {
        "code": code,
        "name": code,
        "exchange": "kospi",
        "exchange_name": "KOSPI",
    }


# ============================================================================
# Builder → Paper trading registration (Phase 2 of 4)
# ============================================================================
#
# A strategy "registered" here is materialized as a YAML file under
# config/strategies/built/<id>.yaml that uses the builder_v1 / builder_v1_exit
# entry/exit classes added in #356. The orchestrator picks it up exactly like
# any other strategy in config/strategies/{stock,futures}/, with `enabled:
# false` by default so registration is non-destructive.
#
# Stock-only enforced at the API boundary; futures BuilderState gets a 400
# instead of silently no-opping at runtime.


# Persist under the dashboard container's mounted ./config (read-write for
# this endpoint family even though most of config/ is mounted read-only on
# kis-trade-app — dashboard's mount is rw). Path resolved relative to the
# config root so backtest/CLI tooling reads the same files.
_BUILT_STRATEGIES_DIR = Path(
    os.environ.get("KIS_BUILT_STRATEGIES_DIR", "config/strategies/built")
)
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_KST = ZoneInfo("Asia/Seoul")
_REPO_ROOT = Path(__file__).resolve().parents[3]


class RegisterPaperRequest(BaseModel):
    """Body of POST /register-paper."""

    builder_state: dict[str, Any] = Field(
        ...,
        description="Full BuilderState JSON (matching shared/strategy_builder/schema.py)",
    )
    stop_loss_pct: float = Field(default=5.0, ge=0)
    take_profit_pct: float = Field(default=10.0, ge=0)
    order_amount: int = Field(default=1_000_000, ge=0)
    cooldown_seconds: int = Field(default=0, ge=0)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RegisteredStrategy(BaseModel):
    """A built strategy listed by GET /registered."""

    id: str
    name: str
    description: str | None = None
    asset_class: str
    enabled: bool
    registered_at: str | None = None
    path: str


class RegisteredListResponse(BaseModel):
    """GET /registered response."""

    strategies: list[RegisteredStrategy]
    total: int


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
    if state.asset_class != "stock":
        raise HTTPException(
            status_code=400,
            detail=(
                "builder→paper registration is stock-only in Phase 1. "
                "Futures strategies stay on the dedicated entry classes "
                "(setup_a/setup_c/bb_reversion_15m)."
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
    order_amount: int,
    cooldown_seconds: int,
    min_confidence: float,
    enabled: bool = False,
) -> dict[str, Any]:
    """Materialize the YAML dict the builder_v1 classes will consume."""
    metadata = state.get("metadata", {})
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
                    "min_confidence": min_confidence,
                },
            },
            "position": {
                "type": "fixed",
                "params": {
                    "order_amount_per_stock": order_amount,
                },
            },
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

    _BUILT_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    yaml_doc = _build_strategy_yaml(
        state=state,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
        order_amount=body.order_amount,
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


class EnableRequest(BaseModel):
    enabled: bool


@router.post("/registered/{strategy_id}/enable", response_model=RegisteredStrategy)
async def toggle_registered_strategy(
    strategy_id: str, body: EnableRequest
) -> RegisteredStrategy:
    """Flip strategy.enabled and write back."""
    safe_id = _safe_id(strategy_id)
    doc = _load_strategy_file(safe_id)
    strategy = doc.setdefault("strategy", {})
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


# ============================================================================
# Builder preset experiment reports
# ============================================================================


def _resolve_project_path(raw: str | Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return _REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _load_experiment_config() -> dict[str, Any]:
    raw_path = os.environ.get(
        "STOCK_BUILDER_PRESET_EXPERIMENT_CONFIG",
        "stock_builder_preset_experiment.yaml",
    )
    path = Path(raw_path)
    if path.is_absolute() or path.exists():
        cfg_path = _resolve_project_path(path)
        if not cfg_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Experiment config not found: {_display_path(cfg_path)}",
            )
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    else:
        data = ConfigLoader.load(raw_path, use_cache=False)

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Experiment config is invalid")
    exp = data.get("experiment", data)
    if not isinstance(exp, dict):
        raise HTTPException(status_code=500, detail="Experiment config is invalid")
    return exp


def _parse_config_date(value: Any) -> date:
    if hasattr(value, "isoformat"):
        return date.fromisoformat(value.isoformat())
    return date.fromisoformat(str(value))


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        raw = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _weekdays(start: date, end: date) -> list[date]:
    if end < start:
        return []
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    return days


def _read_report(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _list_experiment_reports(output_dir: Path) -> list[dict[str, Any]]:
    if not output_dir.exists():
        return []

    reports: list[dict[str, Any]] = []
    paths = sorted(
        output_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    for path in paths:
        data = _read_report(path)
        if data is None:
            continue
        exp = (
            data.get("experiment", {})
            if isinstance(data.get("experiment"), dict)
            else {}
        )
        reports.append(
            {
                "filename": path.name,
                "path": _display_path(path),
                "mtime": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=UTC
                ).isoformat(),
                "generated_at": exp.get("generated_at"),
                "start_date": exp.get("start_date"),
                "end_date": exp.get("end_date"),
                "summary_count": len(data.get("summaries") or []),
                "trade_count": len(data.get("trades") or []),
            }
        )
    return reports


def _latest_log_tail(log_dir: Path, *, max_lines: int = 80) -> dict[str, Any] | None:
    files = sorted(
        log_dir.glob("stock_builder_preset_experiment_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None
    path = files[0]
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return {
        "path": _display_path(path),
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
        "lines": lines[-max_lines:],
    }


def _experiment_progress(
    config: dict[str, Any], reports: list[dict[str, Any]]
) -> dict[str, Any]:
    start = _parse_config_date(config["start_date"])
    end = _parse_config_date(config["end_date"])
    scheduled_days = _weekdays(start, end)
    report_dates: set[date] = set()
    for report in reports:
        generated = _parse_dt(report.get("generated_at")) or _parse_dt(
            report.get("mtime")
        )
        if generated is None:
            continue
        local_day = generated.astimezone(_KST).date()
        if start <= local_day <= end and local_day.weekday() < 5:
            report_dates.add(local_day)

    today = datetime.now(_KST).date()
    completed = len(report_dates)
    total = len(scheduled_days)
    if today < start:
        status = "upcoming"
    elif today > end and completed >= total:
        status = "completed"
    elif today > end:
        status = "ended_incomplete"
    elif completed > 0:
        status = "running"
    else:
        status = "waiting_first_run"

    next_run_date = next(
        (day for day in scheduled_days if day not in report_dates and day >= today),
        None,
    )
    return {
        "status": status,
        "total_scheduled_days": total,
        "completed_report_days": completed,
        "completion_pct": round((completed / total) * 100, 1) if total else 0.0,
        "report_dates": [day.isoformat() for day in sorted(report_dates)],
        "next_run_at_kst": (
            f"{next_run_date.isoformat()}T16:35:00+09:00"
            if next_run_date is not None
            else None
        ),
        "last_report_at": reports[0].get("generated_at") if reports else None,
    }


@router.get("/experiments/stock-builder-preset")
async def stock_builder_preset_experiment_report() -> dict[str, Any]:
    """Return status and latest report for the stock builder preset experiment."""
    config = _load_experiment_config()
    output_dir = _resolve_project_path(
        str(config.get("output_dir") or "reports/stock_builder_preset_experiment")
    )
    reports = _list_experiment_reports(output_dir)
    latest_payload: dict[str, Any] | None = None
    if reports:
        latest_payload = _read_report(_resolve_project_path(reports[0]["path"]))

    log_dir = _resolve_project_path(os.environ.get("KIS_LOG_DIR", "logs"))
    preset_ids = [
        str(item.get("id"))
        for item in config.get("presets", [])
        if isinstance(item, dict) and item.get("id")
    ]
    return {
        "experiment": {
            "id": str(config.get("id") or "stock_builder_preset_experiment"),
            "description": str(config.get("description") or ""),
            "start_date": _parse_config_date(config["start_date"]).isoformat(),
            "end_date": _parse_config_date(config["end_date"]).isoformat(),
            "output_dir": _display_path(output_dir),
            "daily_run_time_kst": "16:35",
            "presets": preset_ids,
            "fallback_symbols": config.get("fallback_symbols") or [],
            "basket_source": config.get("basket_source") or {},
        },
        "progress": _experiment_progress(config, reports),
        "reports": reports,
        "latest_report": latest_payload,
        "latest_log": _latest_log_tail(log_dir),
    }
