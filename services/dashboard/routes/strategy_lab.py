"""Strategy Lab dashboard endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shared.strategy_lab.config import load_strategy_lab_config
from shared.strategy_lab.evaluator import StrategyLabEvaluator
from shared.strategy_lab.order_bridge import StrategyLabOrderBridge
from shared.strategy_lab.schema import (
    LabSignal,
    MarketSnapshot,
    OrderStatus,
    OrderTicket,
    PaperOrder,
    StrategySpec,
)
from shared.strategy_lab.store import StrategyLabStore

router = APIRouter(prefix="/api/strategy-lab", tags=["strategy-lab"])


class ValidationResponse(BaseModel):
    valid: bool
    draft_id: str
    warnings: list[str] = Field(default_factory=list)
    required_indicators: list[str] = Field(default_factory=list)


class PreviewSignalRequest(BaseModel):
    spec: StrategySpec
    symbols: list[str] = Field(min_length=1)
    market_data: dict[str, MarketSnapshot]
    source: Literal["preview", "backtest", "paper_run"] = "preview"


class PreviewSignalResponse(BaseModel):
    draft_id: str
    signals: list[LabSignal]


class OrderTicketCreateRequest(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    order_amount: float | None = Field(default=None, gt=0)


class PaperOrderSubmitRequest(BaseModel):
    ticket_id: str


def _store() -> StrategyLabStore:
    return StrategyLabStore()


def _evaluator() -> StrategyLabEvaluator:
    return StrategyLabEvaluator()


@router.get("/capabilities")
async def get_capabilities() -> dict:
    """Return builder capabilities and config-driven defaults."""
    config = load_strategy_lab_config()
    return {
        "capabilities": config.get("capabilities", {}),
        "builder_template": config.get("builder_template", {}),
        "default_order_amount": config.get("default_order_amount", 0),
        "ttl_seconds": config.get("ttl_seconds", 86400),
    }


@router.post("/drafts", response_model=ValidationResponse)
async def save_draft(spec: StrategySpec) -> ValidationResponse:
    """Normalize a draft and return its stable draft id."""
    evaluator = _evaluator()
    return _validation_response(spec, evaluator)


@router.post("/validate", response_model=ValidationResponse)
async def validate_strategy(spec: StrategySpec) -> ValidationResponse:
    """Validate a Strategy Lab specification."""
    evaluator = _evaluator()
    return _validation_response(spec, evaluator)


@router.post("/preview-code")
async def preview_code(spec: StrategySpec) -> dict:
    """Return a deterministic preview of the generated strategy module."""
    draft_id = _evaluator().draft_id(spec)
    return {
        "draft_id": draft_id,
        "module_name": f"lab_{draft_id}",
        "python": _python_preview(spec),
        "spec": spec.model_dump(mode="json", exclude_none=True),
    }


@router.post("/preview-signal", response_model=PreviewSignalResponse)
async def preview_signal(request: PreviewSignalRequest) -> PreviewSignalResponse:
    """Generate current-value BUY/SELL/HOLD signal cards for selected symbols."""
    snapshots: list[MarketSnapshot] = []
    missing_symbols: list[str] = []
    for symbol in request.symbols:
        snapshot = request.market_data.get(symbol)
        if snapshot is None:
            missing_symbols.append(symbol)
        else:
            snapshots.append(snapshot)
    if missing_symbols:
        raise HTTPException(
            status_code=400,
            detail=f"market_data missing for symbols: {', '.join(missing_symbols)}",
        )

    evaluator = _evaluator()
    store = _store()
    signals = evaluator.generate_signals(
        request.spec,
        snapshots,
        source=request.source,
    )
    for signal in signals:
        store.store_signal(signal)
    draft_id = evaluator.draft_id(request.spec)
    return PreviewSignalResponse(draft_id=draft_id, signals=signals)


@router.get("/signals/{signal_id}", response_model=LabSignal)
async def get_signal(signal_id: str) -> LabSignal:
    """Return a generated Strategy Lab signal."""
    signal = _store().get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return signal


@router.post("/signals/{signal_id}/order-ticket", response_model=OrderTicket)
async def create_order_ticket(
    signal_id: str,
    request: OrderTicketCreateRequest | None = None,
) -> OrderTicket:
    """Build a paper-only order ticket from a generated signal."""
    store = _store()
    signal = store.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="signal not found")

    request = request or OrderTicketCreateRequest()
    ticket = StrategyLabOrderBridge(store).create_ticket(
        signal,
        quantity=request.quantity,
        order_amount=request.order_amount,
    )
    return ticket


@router.post("/orders/paper", response_model=PaperOrder)
async def submit_paper_order(request: PaperOrderSubmitRequest) -> PaperOrder:
    """Submit a paper order from a Strategy Lab order ticket."""
    store = _store()
    ticket = store.get_ticket(request.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    order = StrategyLabOrderBridge(store).submit_paper_order(ticket)
    if order.status == OrderStatus.REJECTED:
        return order
    return order


def _validation_response(
    spec: StrategySpec,
    evaluator: StrategyLabEvaluator,
) -> ValidationResponse:
    required = sorted(_collect_indicator_names(spec))
    warnings: list[str] = []
    if spec.risk.order_amount is None and spec.risk.quantity is None:
        warnings.append(
            "No explicit order amount or quantity; ticket creation will use Strategy Lab defaults."
        )
    return ValidationResponse(
        valid=True,
        draft_id=evaluator.draft_id(spec),
        warnings=warnings,
        required_indicators=required,
    )


def _collect_indicator_names(spec: StrategySpec) -> set[str]:
    names: set[str] = set()
    for group in (spec.entry, spec.exit):
        _collect_group_indicators(group, names)
    return names


def _collect_group_indicators(group, names: set[str]) -> None:
    for condition in group.conditions:
        for operand in (condition.left, condition.right):
            if operand.kind == "indicator" and operand.name:
                names.add(operand.name)
    for child in group.groups:
        _collect_group_indicators(child, names)


def _python_preview(spec: StrategySpec) -> str:
    return "\n".join(
        [
            f"class LabStrategy_{spec.name.replace(' ', '_')}:",
            f"    name = {spec.name!r}",
            f"    asset_class = {spec.asset_class!r}",
            "",
            "    def generate_signal(self, snapshot):",
            "        # Generated preview only. Runtime execution goes through",
            "        # shared.strategy_lab.evaluator.StrategyLabEvaluator.",
            "        return evaluator.generate_signals(self.spec, [snapshot])[0]",
        ]
    )
