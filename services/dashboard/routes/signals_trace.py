"""Signal decision-trace helper logic."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from services.dashboard.routes.signals_data import (
    _as_optional_bool,
    _as_optional_str,
)
from services.dashboard.routes.signals_models import (
    DecisionTraceLifecycle,
    DecisionTraceLlmContext,
    DecisionTraceMarketRiskGate,
    DecisionTraceScorecard,
    EvidenceGap,
    SignalResponse,
)
from services.dashboard.routes.trades import _parse_optional_tz_aware


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


def _signal_label(signal: SignalResponse) -> str:
    symbol = signal.symbol or "unknown_symbol"
    return f"{signal.name} {symbol}" if signal.name else symbol


def _trace_summary_text(
    signal: SignalResponse,
    state: str,
    lifecycle_status: str,
) -> str:
    parts = [
        signal.strategy or "unknown_strategy",
        "generated",
        signal.side or "unknown_side",
        _signal_label(signal),
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


def _market_risk_gate_from_payload(
    payload: Any,
) -> DecisionTraceMarketRiskGate | None:
    """Coerce a gate_trace_payload dict into the trace block (lenient)."""
    if not isinstance(payload, dict) or not payload:
        return None
    return DecisionTraceMarketRiskGate(
        mode=_as_optional_str(payload.get("mode")),
        band=_as_optional_str(payload.get("band")),
        score=_as_optional_float(payload.get("score")),
        regime=_as_optional_str(payload.get("regime")),
        would_block=_as_optional_bool(payload.get("would_block")),
        allow=_as_optional_bool(payload.get("allow")),
        size_factor=_as_optional_float(payload.get("size_factor")),
        min_confidence=_as_optional_str(payload.get("min_confidence")),
        reason=_as_optional_str(payload.get("reason")),
        degraded=_as_optional_bool(payload.get("degraded")),
        stale=_as_optional_bool(payload.get("stale")),
    )


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
