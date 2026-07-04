"""Signal conversion helpers for futures setup entry adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.models.signal import Signal as OrchestratorSignal


def decision_signal_to_orchestrator_signal(
    decision_signal: Any,
    *,
    strategy_name: str,
    timestamp: datetime,
    confidence_override: float | None = None,
    entry_atr: float = 0.0,
    extra_metadata: dict[str, Any] | None = None,
) -> OrchestratorSignal:
    """Convert a decision-engine Signal to an orchestrator Signal.

    ``timestamp`` is authoritative and is normalized to timezone-aware UTC.
    This preserves the orchestrator timestamp contract even when the setup
    signal was generated from KST-native decision context.
    """
    from shared.models.signal import Signal as OrchestratorSignal
    from shared.models.signal import SignalType

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)

    direction = decision_signal.direction
    effective_confidence = (
        confidence_override
        if confidence_override is not None
        else decision_signal.confidence
    )

    valid_until = getattr(decision_signal, "valid_until", None)
    metadata: dict[str, Any] = {
        "signal_direction": direction,
        "direction": direction,
        "setup_type": decision_signal.setup_type,
        "stop_loss": decision_signal.stop_loss,
        "take_profit": decision_signal.take_profit,
        "entry_atr": entry_atr,
        "reason_tags": list(decision_signal.reason_tags),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    if valid_until is not None:
        metadata["valid_until"] = valid_until

    return OrchestratorSignal(
        code=decision_signal.symbol,
        name=decision_signal.symbol,
        signal_type=SignalType.ENTRY,
        strategy=strategy_name,
        price=decision_signal.entry_price,
        confidence=effective_confidence,
        timestamp=timestamp,
        metadata=metadata,
    )


_decision_signal_to_orchestrator_signal = decision_signal_to_orchestrator_signal

__all__ = [
    "_decision_signal_to_orchestrator_signal",
    "decision_signal_to_orchestrator_signal",
]
