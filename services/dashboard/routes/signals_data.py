"""Signals route conversion helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from services.dashboard.routes.signals_models import SignalResponse


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


def _clean_display_name(value: Any) -> str:
    if value is None:
        return ""
    name = str(value).strip()
    if not name or name.lower() in {"none", "null"}:
        return ""
    return name


def _as_optional_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _as_optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _market_risk_gate_source(s: dict, trace: dict) -> dict[str, Any] | None:
    """Locate the gate_trace_payload block attached by the entry lanes.

    The Phase 2 lanes attach it under the fixed ``market_risk_gate`` key —
    either on the signal itself, inside ``metadata``, or inside the trace
    block. Absent (pre-gate signals, monolithic futures path) → None.
    """
    metadata = s.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    payload = _as_optional_dict(
        _first_present(
            s.get("market_risk_gate"),
            metadata.get("market_risk_gate"),
            trace.get("market_risk_gate"),
        )
    )
    return payload or None


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
            name=_clean_display_name(
                s.get("name") or s.get("stock_name") or s.get("prdt_name")
            ),
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
            market_risk_gate=_market_risk_gate_source(s, trace),
        )
    except (ValueError, TypeError, KeyError):
        # Invalid signal data - skip this record
        return None
