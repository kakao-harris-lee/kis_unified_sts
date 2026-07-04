"""Signals endpoints.

This module remains the public FastAPI facade. Signal models, conversion helpers,
and decision-trace internals are split into route-adjacent modules while the old
private helper names stay available for tests and operator tooling.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query

from services.dashboard.domain.assets import normalize_asset_class, target_assets
from services.dashboard.routes import signals_trace as _trace_helpers
from services.dashboard.routes.signals_data import (
    _as_optional_str,
    _to_signal_response,
)
from services.dashboard.routes.signals_models import (
    DecisionTraceLifecycle,
    DecisionTraceLineage,
    DecisionTraceLlmContext,
    DecisionTraceResponse,
    DecisionTraceRiskOrderability,
    DecisionTraceSignal,
    DecisionTraceStrategyInputs,
    DecisionTraceSummary,
    EvidenceGap,
    SignalHistoryResponse,
    SignalListResponse,
    SignalResponse,
)
from services.dashboard.routes.signals_trace import (
    _build_trace_lifecycle as _default_build_trace_lifecycle,
)
from services.dashboard.routes.signals_trace import (
    _empty_lifecycle,
    _empty_scorecard,
    _gap,
    _load_market_context,
    _load_scorecard,
    _load_signal_decision_payload,
    _market_risk_gate_from_payload,
    _trace_state,
    _trace_summary_text,
)
from shared.exceptions import InfrastructureError

router = APIRouter(prefix="/api/signals", tags=["signals"])


def _get_trace_ledger():
    return _trace_helpers._get_trace_ledger()


def _build_trace_lifecycle(
    signal: SignalResponse,
    ledger: Any | None = None,
) -> DecisionTraceLifecycle:
    return _default_build_trace_lifecycle(signal, ledger=ledger)


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


def _trace_from_signal(signal: SignalResponse) -> DecisionTraceResponse:
    state = _trace_state(signal)
    gaps: list[EvidenceGap] = []
    signal_decision_payload: dict[str, Any] = {}
    llm_context = DecisionTraceLlmContext(status="not_available")
    scorecard = _empty_scorecard()
    lifecycle = _empty_lifecycle()

    try:
        ledger = _get_trace_ledger()
    except Exception:
        ledger = None

    if ledger is None:
        gaps.append(
            _gap(
                "runtime_ledger_not_available",
                "warning",
                "RuntimeLedger is unavailable; trace uses Redis signal fields only.",
            )
        )
        lifecycle = _build_trace_lifecycle(signal)
    else:
        try:
            signal_decision_payload = _load_signal_decision_payload(ledger, signal)
            loaded_context = _load_market_context(
                ledger,
                signal,
                signal_decision_payload,
            )
            if loaded_context is not None:
                llm_context = loaded_context
            scorecard = _load_scorecard(ledger, signal)
            # Reuse the already-open ledger for lifecycle evidence rather than
            # opening (and migrating) a second connection per request.
            lifecycle = _build_trace_lifecycle(signal, ledger=ledger)
        finally:
            close = getattr(ledger, "close", None)
            if callable(close):
                close()

    if llm_context.status != "ok":
        gaps.append(
            _gap(
                "llm_context_not_available",
                "warning",
                "No LLM market context is linked to this signal.",
            )
        )
    if scorecard.status == "missing":
        gaps.append(
            _gap(
                "scorecard_missing",
                "info",
                "No LLM scorecard prediction or score is linked to this signal.",
            )
        )
    elif scorecard.status == "not_scored_yet":
        gaps.append(
            _gap(
                "scorecard_not_scored_yet",
                "info",
                "A prediction exists, but the score has not been recorded yet.",
            )
        )

    if lifecycle.status == "missing":
        gaps.append(
            _gap(
                "no_lifecycle_evidence",
                "info",
                "No order, fill, position, or closed-trade lifecycle evidence is available.",
            )
        )
    elif lifecycle.status == "partial":
        gaps.append(
            _gap(
                "partial_lifecycle",
                "warning",
                "Lifecycle evidence is present but one or more steps are missing.",
            )
        )

    summary_warnings = [gap.code for gap in gaps if gap.severity != "info"]
    for warning in lifecycle.warnings:
        if warning == "no_lifecycle_evidence":
            continue
        if warning not in summary_warnings:
            summary_warnings.append(warning)

    # Signal metadata first (fixed key contract), ledger decision payload as
    # fallback; both absent → None so the UI omits the section.
    market_risk_gate = _market_risk_gate_from_payload(
        signal.market_risk_gate
    ) or _market_risk_gate_from_payload(signal_decision_payload.get("market_risk_gate"))

    return DecisionTraceResponse(
        signal=DecisionTraceSignal(
            id=signal.id,
            asset_class=signal.asset_class,
            symbol=signal.symbol,
            name=signal.name,
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
            text=_trace_summary_text(signal, state, lifecycle.status),
            warnings=summary_warnings,
        ),
        llm_context=llm_context,
        strategy_inputs=DecisionTraceStrategyInputs(
            setup_type=signal.setup_type,
            indicators=(
                signal_decision_payload.get("indicators", {})
                if isinstance(signal_decision_payload.get("indicators"), dict)
                else {}
            ),
            thresholds=(
                signal_decision_payload.get("thresholds", {})
                if isinstance(signal_decision_payload.get("thresholds"), dict)
                else {}
            ),
            event_evidence=(
                signal_decision_payload.get("event_evidence", {})
                if isinstance(signal_decision_payload.get("event_evidence"), dict)
                else {}
            ),
            raw_reason=signal.reason,
        ),
        risk_orderability=DecisionTraceRiskOrderability(
            reject_stage=signal.reject_stage,
            reject_reason=signal.reject_reason,
            orderability_state=signal.orderability_state,
            orderability_details=signal.orderability_details or {},
            risk_state=_as_optional_str(signal_decision_payload.get("risk_state")),
            risk_details=(
                signal_decision_payload.get("risk_details", {})
                if isinstance(signal_decision_payload.get("risk_details"), dict)
                else {}
            ),
        ),
        market_risk_gate=market_risk_gate,
        lineage=DecisionTraceLineage(
            signal_id=signal.id,
            order_id=signal.order_id,
            fill_id=signal.fill_id,
            position_id=signal.position_id,
            trade_id=signal.trade_id,
        ),
        lifecycle=lifecycle,
        scorecard=scorecard,
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
    return _trace_from_signal(signal)
