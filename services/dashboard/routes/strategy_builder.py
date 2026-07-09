"""Strategy Builder dashboard endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shared.strategy_builder import (
    BuilderCapabilities,
    BuilderSignal,
    BuilderState,
    StrategyBuilderEvaluator,
    StrategyBuilderStore,
    SymbolSeries,
    builder_state_to_yaml,
    load_capabilities,
    preview_python,
    validate_exit_primitive,
    yaml_to_builder_state,
)
from shared.strategy_lab.order_bridge import StrategyLabOrderBridge
from shared.strategy_lab.store import StrategyLabStore

router = APIRouter(prefix="/api/strategy-builder", tags=["strategy-builder"])


class ValidateResponse(BaseModel):
    valid: bool
    draft_id: str
    required_indicators: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Schema v2: hard validation failures (e.g. unknown exit primitive) that
    # would make StrategyFactory skip the strategy at roster-build time.
    errors: list[str] = Field(default_factory=list)


class PreviewYamlResponse(BaseModel):
    draft_id: str
    yaml: str


class PreviewCodeResponse(BaseModel):
    draft_id: str
    python: str


class ImportYamlRequest(BaseModel):
    yaml: str


class ImportYamlResponse(BaseModel):
    state: BuilderState


class PreviewSignalRequest(BaseModel):
    state: BuilderState
    series: list[SymbolSeries] = Field(min_length=1)


class PreviewSignalResponse(BaseModel):
    draft_id: str
    signals: list[BuilderSignal]


class OrderTicketCreateRequest(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    order_amount: float | None = Field(default=None, gt=0)


class PaperOrderSubmitRequest(BaseModel):
    ticket_id: str


def _evaluator() -> StrategyBuilderEvaluator:
    return StrategyBuilderEvaluator()


def _store() -> StrategyBuilderStore:
    return StrategyBuilderStore()


def _lab_store() -> StrategyLabStore:
    return StrategyLabStore()


@router.get("/capabilities", response_model=BuilderCapabilities)
async def get_capabilities() -> BuilderCapabilities:
    return load_capabilities()


@router.post("/drafts", response_model=ValidateResponse)
async def save_draft(state: BuilderState) -> ValidateResponse:
    return _validate_response(state)


@router.post("/validate", response_model=ValidateResponse)
async def validate_state(state: BuilderState) -> ValidateResponse:
    return _validate_response(state)


@router.post("/preview-yaml", response_model=PreviewYamlResponse)
async def preview_yaml(state: BuilderState) -> PreviewYamlResponse:
    evaluator = _evaluator()
    return PreviewYamlResponse(
        draft_id=evaluator.draft_id(state),
        yaml=builder_state_to_yaml(state),
    )


@router.post("/preview-code", response_model=PreviewCodeResponse)
async def preview_code(state: BuilderState) -> PreviewCodeResponse:
    evaluator = _evaluator()
    return PreviewCodeResponse(
        draft_id=evaluator.draft_id(state),
        python=preview_python(state),
    )


@router.post("/import-yaml", response_model=ImportYamlResponse)
async def import_yaml(request: ImportYamlRequest) -> ImportYamlResponse:
    return ImportYamlResponse(state=yaml_to_builder_state(request.yaml))


@router.post("/export-yaml", response_model=PreviewYamlResponse)
async def export_yaml(state: BuilderState) -> PreviewYamlResponse:
    return await preview_yaml(state)


@router.post("/signals/preview", response_model=PreviewSignalResponse)
async def preview_signals(request: PreviewSignalRequest) -> PreviewSignalResponse:
    evaluator = _evaluator()
    builder_store = _store()
    lab_store = _lab_store()
    signals = evaluator.generate_signals(request.state, request.series)
    stored_signals: list[BuilderSignal] = []
    for signal in signals:
        lab_signal = evaluator.to_lab_signal(signal)
        lab_store.store_signal(lab_signal)
        stored_signal = signal.model_copy(
            update={"lab_signal_id": lab_signal.signal_id}
        )
        builder_store.store_signal(stored_signal)
        stored_signals.append(stored_signal)
    return PreviewSignalResponse(
        draft_id=evaluator.draft_id(request.state),
        signals=stored_signals,
    )


@router.get("/signals/{signal_id}", response_model=BuilderSignal)
async def get_signal(signal_id: str) -> BuilderSignal:
    signal = _store().get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="signal not found")
    return signal


@router.post("/signals/{signal_id}/order-ticket")
async def create_order_ticket(
    signal_id: str,
    request: OrderTicketCreateRequest | None = None,
) -> dict:
    signal = _store().get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="signal not found")
    lab_store = _lab_store()
    lab_signal = lab_store.get_signal(signal.lab_signal_id or signal.signal_id)
    if lab_signal is None:
        raise HTTPException(status_code=404, detail="linked signal not found")
    request = request or OrderTicketCreateRequest()
    ticket = StrategyLabOrderBridge(lab_store).create_ticket(
        lab_signal,
        quantity=request.quantity,
        order_amount=request.order_amount,
    )
    return ticket.model_dump(mode="json")


@router.post("/orders/paper")
async def submit_paper_order(request: PaperOrderSubmitRequest) -> dict:
    lab_store = _lab_store()
    ticket = lab_store.get_ticket(request.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    order = StrategyLabOrderBridge(lab_store).submit_paper_order(ticket)
    return order.model_dump(mode="json")


def _validate_response(state: BuilderState) -> ValidateResponse:
    evaluator = _evaluator()
    aliases = sorted({indicator.alias for indicator in state.indicators})
    warnings: list[str] = []
    errors: list[str] = []
    has_short_entries = state.entry_short is not None and bool(
        state.entry_short.conditions
    )
    if not state.entry.conditions and not has_short_entries:
        warnings.append("Entry conditions are empty.")
    if not state.exit.conditions:
        warnings.append("Exit conditions are empty.")
    primitive_error = validate_exit_primitive(state)
    if primitive_error is not None:
        errors.append(primitive_error)
    return ValidateResponse(
        valid=not errors,
        draft_id=evaluator.draft_id(state),
        required_indicators=aliases,
        warnings=warnings,
        errors=errors,
    )
