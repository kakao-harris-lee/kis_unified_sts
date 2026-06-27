"""Signals endpoints."""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.dashboard.domain.assets import normalize_asset_class, target_assets
from shared.exceptions import InfrastructureError

router = APIRouter(prefix="/api/signals", tags=["signals"])


class SignalResponse(BaseModel):
    """Signal response model."""

    id: str
    asset_class: str
    symbol: str
    side: str
    signal_type: str
    strategy: str
    price: float
    confidence: float
    strength: float
    timestamp: datetime
    executed: bool
    setup_type: str | None = None
    status: str | None = None
    reason: str | None = None
    reject_stage: str | None = None
    reject_reason: str | None = None
    orderability_state: str | None = None
    orderability_details: dict[str, Any] | None = None
    order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    trade_id: str | None = None


class SignalListResponse(BaseModel):
    """Signal list response."""

    signals: list[SignalResponse]
    total: int
    page: int
    limit: int


class SignalHistoryResponse(BaseModel):
    """Signal history response."""

    history: list[dict]
    total_signals: int
    days: int


class EvidenceGap(BaseModel):
    """One missing or degraded evidence source for the decision trace."""

    code: str
    severity: str
    message: str


class DecisionTraceSignal(BaseModel):
    """Signal identity and basic decision fields."""

    id: str
    asset_class: str
    symbol: str
    strategy: str
    side: str
    signal_type: str | None = None
    status: str | None = None
    reason: str | None = None
    confidence: float | None = None
    strength: float | None = None
    price: float | None = None
    timestamp: datetime | None = None


class DecisionTraceSummary(BaseModel):
    """Deterministic operator summary."""

    state: str
    text: str
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceLlmContext(BaseModel):
    """Market context associated with the signal decision."""

    status: str
    overall_signal: str | None = None
    confidence: float | None = None
    risk_mode: str | None = None
    regime: str | None = None
    risk_score: float | None = None
    captured_at: datetime | None = None
    source: str | None = None


class DecisionTraceStrategyInputs(BaseModel):
    """Strategy-native inputs available for the signal."""

    setup_type: str | None = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    event_evidence: dict[str, Any] = Field(default_factory=dict)
    raw_reason: str | None = None


class DecisionTraceRiskOrderability(BaseModel):
    """Risk and orderability status for the signal."""

    reject_stage: str | None = None
    reject_reason: str | None = None
    orderability_state: str | None = None
    orderability_details: dict[str, Any] = Field(default_factory=dict)
    risk_state: str | None = None
    risk_details: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceLineage(BaseModel):
    """Known downstream runtime identifiers."""

    signal_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    trade_id: str | None = None


class DecisionTraceLifecycle(BaseModel):
    """Compact lifecycle block embedded in the signal trace."""

    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceScorecard(BaseModel):
    """LLM prediction scorecard evidence linked to the signal."""

    status: str
    facet: str | None = None
    date_kst: str | None = None
    captured_at: datetime | None = None
    confidence: float | None = None
    correct: bool | None = None
    value: float | None = None
    economic_proxy: float | None = None
    baseline_value: float | None = None
    edge: float | None = None
    scored_at: datetime | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceResponse(BaseModel):
    """Read-only signal decision trace for the dashboard."""

    signal: DecisionTraceSignal
    summary: DecisionTraceSummary
    llm_context: DecisionTraceLlmContext
    strategy_inputs: DecisionTraceStrategyInputs
    risk_orderability: DecisionTraceRiskOrderability
    lineage: DecisionTraceLineage
    lifecycle: DecisionTraceLifecycle
    scorecard: DecisionTraceScorecard
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)


def _get_reader(asset_class: str | None = None):
    from shared.streaming.trading_state import TradingStateReader

    asset = asset_class or os.environ.get("TRADING_ASSET_CLASS", "stock")
    return TradingStateReader(asset)


def _load_signals(asset_class: str) -> list[dict]:
    try:
        reader = _get_reader(asset_class)
        return reader.get_signals(start=0, count=200)
    except InfrastructureError:
        # Redis unavailable - return empty list
        return []


def _trace_source(s: dict) -> dict:
    trace = s.get("trace")
    if isinstance(trace, dict):
        return trace
    metadata = s.get("metadata")
    if isinstance(metadata, dict):
        nested_trace = metadata.get("trace")
        if isinstance(nested_trace, dict):
            return nested_trace
    return {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _as_optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _as_optional_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _to_signal_response(s: dict, asset_class: str) -> SignalResponse | None:
    if not isinstance(s, dict):
        return None

    try:
        # Always emit tz-aware UTC timestamps so callers (e.g.
        # /history's cutoff comparison) can mix freely without
        # "can't compare offset-naive and offset-aware" crashes.
        if "timestamp" in s:
            ts = datetime.fromisoformat(s["timestamp"])
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
        else:
            ts = datetime.now(UTC)
        confidence = float(s.get("confidence", s.get("strength", 0)) or 0)
        trace = _trace_source(s)
        orderability = _first_present(s.get("orderability"), trace.get("orderability"))
        orderability_details = _as_optional_dict(
            _first_present(
                s.get("orderability_details"),
                trace.get("orderability_details"),
                orderability,
            )
        )
        return SignalResponse(
            id=s.get("id", ""),
            asset_class=asset_class,
            symbol=s.get("symbol", ""),
            side=s.get("side", ""),
            signal_type=s.get("signal_type", ""),
            strategy=s.get("strategy", ""),
            price=float(s.get("price", 0)),
            confidence=confidence,
            strength=confidence,
            timestamp=ts,
            executed=bool(s.get("executed", False)),
            setup_type=s.get("setup_type") or s.get("stage") or None,
            status=_as_optional_str(
                _first_present(s.get("status"), trace.get("status"))
            ),
            reason=_as_optional_str(
                _first_present(s.get("reason"), trace.get("reason"))
            ),
            reject_stage=_as_optional_str(
                _first_present(
                    s.get("reject_stage"),
                    s.get("rejected_stage"),
                    trace.get("reject_stage"),
                    trace.get("rejected_stage"),
                )
            ),
            reject_reason=_as_optional_str(
                _first_present(
                    s.get("reject_reason"),
                    s.get("rejection_reason"),
                    trace.get("reject_reason"),
                    trace.get("rejection_reason"),
                )
            ),
            orderability_state=_as_optional_str(
                _first_present(
                    s.get("orderability_state"),
                    trace.get("orderability_state"),
                    (
                        orderability.get("state")
                        if isinstance(orderability, dict)
                        else orderability
                    ),
                )
            ),
            orderability_details=orderability_details,
            order_id=_as_optional_str(
                _first_present(s.get("order_id"), trace.get("order_id"))
            ),
            fill_id=_as_optional_str(
                _first_present(s.get("fill_id"), trace.get("fill_id"))
            ),
            position_id=_as_optional_str(
                _first_present(s.get("position_id"), trace.get("position_id"))
            ),
            trade_id=_as_optional_str(
                _first_present(s.get("trade_id"), trace.get("trade_id"))
            ),
        )
    except (ValueError, TypeError, KeyError):
        # Invalid signal data - skip this record
        return None


def _gap(code: str, severity: str, message: str) -> EvidenceGap:
    return EvidenceGap(code=code, severity=severity, message=message)


def _trace_state(signal: SignalResponse) -> str:
    status = (signal.status or "").lower()
    orderable = (signal.orderability_state or "").lower()
    if signal.trade_id:
        return "closed"
    if signal.fill_id:
        return "filled"
    if signal.order_id:
        return "submitted"
    if status in {"rejected", "blocked"} or signal.reject_reason:
        return "rejected"
    if orderable in {"paper_orderable", "orderable", "passed"}:
        return "orderable"
    if status:
        return status
    return "generated"


def _trace_summary_text(signal: SignalResponse, state: str) -> str:
    parts = [
        signal.strategy or "unknown_strategy",
        "generated",
        signal.side or "unknown_side",
        signal.symbol or "unknown_symbol",
    ]
    if signal.reason:
        parts.append(f"from {signal.reason}")
    if signal.orderability_state:
        parts.append(f"orderability {signal.orderability_state}")
    if state in {"filled", "closed"}:
        parts.append("lineage id is present; lifecycle evidence is not loaded yet")
    elif state == "submitted":
        parts.append("order lineage id is present; fill evidence is not available")
    elif state == "orderable":
        parts.append("fill evidence is not available")
    return " ".join(parts) + "."


def _empty_lifecycle() -> DecisionTraceLifecycle:
    return DecisionTraceLifecycle(
        status="missing",
        steps=[],
        warnings=["no_lifecycle_evidence"],
    )


def _empty_scorecard() -> DecisionTraceScorecard:
    return DecisionTraceScorecard(status="missing")


def _basic_trace_from_signal(signal: SignalResponse) -> DecisionTraceResponse:
    state = _trace_state(signal)
    gaps = [
        _gap(
            "llm_context_not_available",
            "warning",
            "No LLM market context is linked to this signal.",
        ),
        _gap(
            "scorecard_missing",
            "info",
            "No LLM scorecard prediction or score is linked to this signal.",
        ),
        _gap(
            "no_lifecycle_evidence",
            "info",
            "No order, fill, position, or closed-trade lifecycle evidence is available.",
        ),
    ]
    return DecisionTraceResponse(
        signal=DecisionTraceSignal(
            id=signal.id,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            strategy=signal.strategy,
            side=signal.side,
            signal_type=signal.signal_type,
            status=signal.status,
            reason=signal.reason,
            confidence=signal.confidence,
            strength=signal.strength,
            price=signal.price,
            timestamp=signal.timestamp,
        ),
        summary=DecisionTraceSummary(
            state=state,
            text=_trace_summary_text(signal, state),
            warnings=[gap.code for gap in gaps if gap.severity != "info"],
        ),
        llm_context=DecisionTraceLlmContext(status="not_available"),
        strategy_inputs=DecisionTraceStrategyInputs(
            setup_type=signal.setup_type,
            raw_reason=signal.reason,
        ),
        risk_orderability=DecisionTraceRiskOrderability(
            reject_stage=signal.reject_stage,
            reject_reason=signal.reject_reason,
            orderability_state=signal.orderability_state,
            orderability_details=signal.orderability_details or {},
        ),
        lineage=DecisionTraceLineage(
            signal_id=signal.id,
            order_id=signal.order_id,
            fill_id=signal.fill_id,
            position_id=signal.position_id,
            trade_id=signal.trade_id,
        ),
        lifecycle=_empty_lifecycle(),
        scorecard=_empty_scorecard(),
        evidence_gaps=gaps,
    )


def _find_signal_for_trace(signal_id: str, asset_class: str) -> SignalResponse | None:
    for target in target_assets(asset_class):
        for raw_signal in _load_signals(target):
            signal = _to_signal_response(raw_signal, target)
            if signal is not None and signal.id == signal_id:
                return signal
    return None


@router.get("", response_model=SignalListResponse)
async def get_signals(
    strategy: str | None = Query(None, description="Filter by strategy"),
    side: str | None = Query(None, description="Filter by side (BUY/SELL)"),
    limit: int = Query(50, ge=1, le=100, description="Number of signals"),
    page: int = Query(1, ge=1, description="Page number"),
    asset_class: str = Query(default="futures"),
):
    """Get list of signals with optional filters."""
    asset = normalize_asset_class(asset_class)
    raw_by_asset = [
        (target, signal)
        for target in target_assets(asset)
        for signal in _load_signals(target)
    ]
    signals = [_to_signal_response(s, target) for target, s in raw_by_asset]
    signals = [s for s in signals if s is not None]
    signals.sort(key=lambda s: s.timestamp, reverse=True)

    if strategy:
        signals = [s for s in signals if s.strategy == strategy]
    if side:
        signals = [s for s in signals if s.side == side]

    total = len(signals)
    start = (page - 1) * limit
    end = start + limit
    paginated = signals[start:end]

    return SignalListResponse(signals=paginated, total=total, page=page, limit=limit)


@router.get("/history", response_model=SignalHistoryResponse)
async def get_signal_history(
    days: int = Query(7, ge=1, le=30, description="Number of days"),
    asset_class: str = Query(default="futures"),
):
    """Get signal history statistics."""
    asset = normalize_asset_class(asset_class)
    raw_by_asset = [
        (target, signal)
        for target in target_assets(asset)
        for signal in _load_signals(target)
    ]
    signals = [_to_signal_response(s, target) for target, s in raw_by_asset]
    signals = [s for s in signals if s is not None]

    # _to_signal_response always emits tz-aware UTC; cutoff must match.
    cutoff = datetime.now(UTC) - timedelta(days=days)
    recent = [s for s in signals if s.timestamp >= cutoff]

    history: dict[str, dict] = {}
    for signal in recent:
        date_key = signal.timestamp.strftime("%Y-%m-%d")
        if date_key not in history:
            history[date_key] = {"date": date_key, "count": 0, "buy": 0, "sell": 0}
        history[date_key]["count"] += 1
        if signal.side == "BUY" or signal.side == "entry":
            history[date_key]["buy"] += 1
        else:
            history[date_key]["sell"] += 1

    return SignalHistoryResponse(
        history=list(history.values()),
        total_signals=len(recent),
        days=days,
    )


@router.get("/{signal_id}/trace", response_model=DecisionTraceResponse)
async def get_signal_trace(
    signal_id: str,
    asset_class: str = Query(default="futures"),
) -> DecisionTraceResponse:
    """Return a read-only decision trace for a single signal."""
    asset = normalize_asset_class(asset_class)
    signal = _find_signal_for_trace(signal_id, asset)
    if signal is None:
        return DecisionTraceResponse(
            signal=DecisionTraceSignal(
                id=signal_id,
                asset_class=asset,
                symbol="",
                strategy="",
                side="",
            ),
            summary=DecisionTraceSummary(
                state="unknown",
                text=f"Signal {signal_id} was not found in current Redis signal state.",
                warnings=["signal_not_found"],
            ),
            llm_context=DecisionTraceLlmContext(status="unknown"),
            strategy_inputs=DecisionTraceStrategyInputs(),
            risk_orderability=DecisionTraceRiskOrderability(),
            lineage=DecisionTraceLineage(signal_id=signal_id),
            lifecycle=_empty_lifecycle(),
            scorecard=_empty_scorecard(),
            evidence_gaps=[
                _gap(
                    "signal_not_found",
                    "error",
                    "The selected signal is not present in current signal state.",
                )
            ],
        )
    return _basic_trace_from_signal(signal)
