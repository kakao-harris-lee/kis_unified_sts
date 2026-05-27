"""Compatibility API for the upstream KIS Strategy Builder UI.

The imported UI keeps its upstream /api/* contract. Next.js rewrites route
those calls here under /api/kis-builder/* so the existing dashboard API
contracts are not changed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
            {"name": "ma", "label": "이동평균", "params": ["period"], "example": "ma(20)"},
            {"name": "ema", "label": "지수이동평균", "params": ["period"], "example": "ema(12)"},
            {"name": "rsi", "label": "RSI", "params": ["period"], "example": "rsi(14)"},
            {"name": "macd", "label": "MACD", "params": ["fast", "slow", "signal"], "example": "macd(12,26,9)"},
            {"name": "williams_r", "label": "Williams %R", "params": ["period"], "example": "williams_r(14)"},
            {"name": "stochastic", "label": "스토캐스틱", "params": ["k_period", "d_period"], "example": "stochastic(14,3)"},
            {"name": "bollinger", "label": "볼린저 밴드", "params": ["period", "std"], "example": "bollinger(20,2)"},
            {"name": "vwap", "label": "VWAP", "params": [], "example": "vwap()"},
            {"name": "adx", "label": "ADX", "params": ["period"], "example": "adx(14)"},
            {"name": "donchian", "label": "돈치안 채널", "params": ["period"], "example": "donchian(20)"},
            {"name": "ichimoku", "label": "이치모쿠", "params": ["conversion", "base", "span_b"], "example": "ichimoku(9,26,52)"},
            {"name": "supertrend", "label": "SuperTrend", "params": ["period", "multiplier"], "example": "supertrend(10,3)"},
            {"name": "keltner", "label": "켈트너 채널", "params": ["period", "multiplier"], "example": "keltner(20,2)"},
            {"name": "cci", "label": "CCI", "params": ["period"], "example": "cci(20)"},
            {"name": "mfi", "label": "MFI", "params": ["period"], "example": "mfi(14)"},
            {"name": "obv", "label": "OBV", "params": [], "example": "obv()"},
            {"name": "trix", "label": "TRIX", "params": ["period"], "example": "trix(15)"},
            {"name": "engulfing", "label": "장악형 캔들", "params": [], "example": "engulfing()"},
            {"name": "disparity", "label": "이격도", "params": ["period"], "example": "disparity(20)"},
            {"name": "breakout_margin", "label": "돌파 여유율", "params": ["period"], "example": "breakout_margin(252)"},
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
        return {"status": "success", "code": preview_python(state), "buy_dsl": "", "sell_dsl": ""}
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
        return {"status": "error", "results": [], "logs": logs, "message": "종목을 입력해주세요"}

    if request.builder_state:
        source_state = request.builder_state
        strategy_name = source_state.get("metadata", {}).get("name", request.strategy_id)
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
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    state = kis_state_to_builder_state(preset.get("builder_state", {}))
    return {
        "success": True,
        "data": {"id": template_id, "name": preset.get("name"), "yaml": builder_state_to_yaml(state)},
    }


@router.get("/files/templates/{template_id}/download")
async def download_template(template_id: str) -> StreamingResponse:
    preset = get_kis_preset(template_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    state = kis_state_to_builder_state(preset.get("builder_state", {}))
    content = builder_state_to_yaml(state).encode("utf-8")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{template_id}.kis.yaml"'},
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
    return {"success": True, "kospi_count": 0, "kosdaq_count": 0, "total_count": 0, "errors": []}


@router.get("/symbols/search")
async def search_symbols(q: str = "", limit: int = 20, exchange: str | None = None) -> dict[str, Any]:
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
