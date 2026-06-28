"""Signals endpoints."""

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.dashboard.domain.assets import normalize_asset_class, target_assets
from services.dashboard.routes.trades import _parse_optional_tz_aware
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


def _trace_summary_text(
    signal: SignalResponse,
    state: str,
    lifecycle_status: str,
) -> str:
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
    # Reflect the lifecycle evidence that was actually loaded, rather than
    # asserting it is missing for every downstream state.
    if state in {"submitted", "orderable", "filled", "closed"}:
        if lifecycle_status == "ok":
            parts.append("lifecycle evidence is available")
        elif lifecycle_status == "partial":
            parts.append("lifecycle evidence is partially available")
        else:
            parts.append("lifecycle evidence is not available")
    return " ".join(parts) + "."


def _empty_lifecycle() -> DecisionTraceLifecycle:
    return DecisionTraceLifecycle(
        status="missing",
        steps=[],
        warnings=["no_lifecycle_evidence"],
    )


def _empty_scorecard() -> DecisionTraceScorecard:
    return DecisionTraceScorecard(status="missing")


KST = ZoneInfo("Asia/Seoul")

# Shared tz-aware ISO parser (see services/dashboard/routes/trades.py); the
# dashboard emits tz-aware UTC throughout so downstream comparisons never mix
# offset-naive and offset-aware datetimes.
_parse_dt = _parse_optional_tz_aware


def _date_kst(value: datetime | None) -> str | None:
    ts = _parse_dt(value)
    if ts is None:
        return None
    return ts.astimezone(KST).date().isoformat()


def _json_payload(row: Any, key: str = "payload_json") -> dict[str, Any]:
    if row is None:
        return {}
    try:
        data = dict(row)
    except (TypeError, ValueError):
        return {}
    raw = data.get(key)
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    payload = data.get("payload")
    return payload if isinstance(payload, dict) else {}


def _get_trace_ledger():
    from services.dashboard.routes.trades import _get_runtime_ledger

    return _get_runtime_ledger()


def _as_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_signal_decision_payload(
    ledger: Any,
    signal: SignalResponse,
) -> dict[str, Any]:
    try:
        row = (
            ledger._require_conn()  # noqa: SLF001
            .execute(
                # Match either column: a decision row may be keyed by the signal
                # id in the ``id`` column with ``signal_id`` NULL/different. This
                # mirrors the lifecycle batch's ``(id = ? OR signal_id = ?)``.
                "SELECT * FROM signal_decisions "
                "WHERE (id = ? OR signal_id = ?) AND asset_class = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (signal.id, signal.id, signal.asset_class),
            )
            .fetchone()
        )
    except Exception:
        return {}
    return _json_payload(row)


def _llm_context_from_payload(
    payload: dict[str, Any],
) -> DecisionTraceLlmContext | None:
    candidate = payload.get("llm_context") or payload.get("market_context")
    if not isinstance(candidate, dict):
        candidate = payload
    if not any(
        key in candidate
        for key in ("overall_signal", "risk_mode", "regime", "risk_score")
    ):
        return None
    return DecisionTraceLlmContext(
        status="ok",
        overall_signal=_as_optional_str(candidate.get("overall_signal")),
        confidence=_as_optional_float(candidate.get("confidence")),
        risk_mode=_as_optional_str(candidate.get("risk_mode")),
        regime=_as_optional_str(candidate.get("regime")),
        risk_score=_as_optional_float(candidate.get("risk_score")),
        captured_at=_parse_dt(
            candidate.get("captured_at") or candidate.get("created_at")
        ),
        source=_as_optional_str(candidate.get("source")),
    )


def _load_market_context(
    ledger: Any,
    signal: SignalResponse,
    payload: dict[str, Any],
) -> DecisionTraceLlmContext | None:
    from_payload = _llm_context_from_payload(payload)
    if from_payload is not None:
        return from_payload

    try:
        signal_ts = _parse_dt(signal.timestamp)
        if signal_ts is not None:
            row = (
                ledger._require_conn()  # noqa: SLF001
                .execute(
                    "SELECT * FROM market_context_history "
                    "WHERE asset_class = ? AND created_at <= ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (signal.asset_class, signal_ts.isoformat()),
                )
                .fetchone()
            )
        else:
            row = (
                ledger._require_conn()  # noqa: SLF001
                .execute(
                    "SELECT * FROM market_context_history "
                    "WHERE asset_class = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (signal.asset_class,),
                )
                .fetchone()
            )
    except Exception:
        return None

    if row is None:
        return None
    data = dict(row)
    context = _json_payload(row)
    context.setdefault("created_at", data.get("created_at"))
    return _llm_context_from_payload(context)


def _is_futures_setup_ac_value(value: Any) -> bool:
    raw = _as_optional_str(value)
    if raw is None:
        return False
    normalized = raw.strip().lower().replace("-", "_")
    return normalized in {"a", "c", "setup_a", "setup_c"} or normalized.startswith(
        ("a_", "c_", "setup_a_", "setup_c_")
    )


def _scorecard_facet(signal: SignalResponse) -> str | None:
    if (signal.asset_class or "").lower() != "futures":
        return None
    if any(
        _is_futures_setup_ac_value(value)
        for value in (signal.strategy, signal.setup_type)
    ):
        return "direction"
    return None


def _load_scorecard(ledger: Any, signal: SignalResponse) -> DecisionTraceScorecard:
    date_kst = _date_kst(signal.timestamp)
    facet = _scorecard_facet(signal)
    if date_kst is None or facet is None:
        return _empty_scorecard()

    try:
        predictions = ledger.query_predictions(
            facet=facet, start=date_kst, end=date_kst
        )
        scores = ledger.query_scores(facet=facet, start=date_kst, end=date_kst)
    except Exception:
        return _empty_scorecard()

    prediction = predictions[-1] if predictions else None
    score = scores[-1] if scores else None
    if prediction is None and score is None:
        return _empty_scorecard()
    if score is None:
        prediction_payload = prediction.get("payload", {}) if prediction else {}
        return DecisionTraceScorecard(
            status="not_scored_yet",
            facet=facet,
            date_kst=date_kst,
            captured_at=_parse_dt(
                prediction.get("captured_at") if prediction else None
            ),
            confidence=_as_optional_float(
                prediction.get("confidence") if prediction else None
            ),
            detail=prediction_payload if isinstance(prediction_payload, dict) else {},
        )

    return DecisionTraceScorecard(
        status="ok",
        facet=facet,
        date_kst=date_kst,
        captured_at=_parse_dt(prediction.get("captured_at") if prediction else None),
        confidence=_as_optional_float(
            prediction.get("confidence") if prediction else None
        ),
        correct=score.get("correct"),
        value=_as_optional_float(score.get("value")),
        economic_proxy=_as_optional_float(score.get("economic_proxy")),
        baseline_value=_as_optional_float(score.get("baseline_value")),
        edge=_as_optional_float(score.get("edge")),
        scored_at=_parse_dt(score.get("scored_at")),
        detail=score.get("detail", {}) if isinstance(score.get("detail"), dict) else {},
    )


def _lifecycle_status(warnings: list[str], steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "missing"
    if "no_lifecycle_evidence" in warnings:
        return "missing"
    evidence_steps = [step for step in steps if step.get("source") != "not_available"]
    if not evidence_steps:
        return "missing"
    downstream_evidence = [
        step for step in evidence_steps if step.get("stage") != "signal"
    ]
    if not downstream_evidence:
        return "missing"
    has_unavailable_step = any(
        step.get("source") == "not_available"
        or step.get("status") in {"unknown", "not_available"}
        for step in steps
    )
    if has_unavailable_step:
        return "partial"
    if warnings:
        return "partial"
    return "ok"


def _build_trace_lifecycle(
    signal: SignalResponse,
    ledger: Any | None = None,
) -> DecisionTraceLifecycle:
    from services.dashboard.routes.trades import (
        _build_lifecycle_response,
        _load_lifecycle_ledger_rows,
        _load_lifecycle_redis_rows,
    )

    ledger_rows, ledger_available = _load_lifecycle_ledger_rows(
        signal.asset_class,
        symbol=None,
        signal_id=signal.id or None,
        order_id=signal.order_id,
        fill_id=signal.fill_id,
        trade_id=signal.trade_id,
        position_id=signal.position_id,
        allow_symbol_lookup=False,
        ledger=ledger,
    )
    # Bound the Redis scan to this signal's symbol instead of pulling the full
    # trade/signal/position history that is then discarded.
    redis_rows = _load_lifecycle_redis_rows(
        signal.asset_class,
        symbol=signal.symbol or None,
    )
    response = _build_lifecycle_response(
        asset_class=signal.asset_class,
        signal_id=signal.id or None,
        order_id=signal.order_id,
        fill_id=signal.fill_id,
        trade_id=signal.trade_id,
        position_id=signal.position_id,
        symbol=None,
        ledger_rows=ledger_rows,
        redis_rows=redis_rows,
        ledger_available=ledger_available,
        allow_symbol_fallback=False,
    )
    steps = [step.model_dump(mode="json") for step in response.steps]
    return DecisionTraceLifecycle(
        status=_lifecycle_status(response.warnings, steps),
        steps=steps,
        warnings=response.warnings,
    )


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
