"""Adapter-local LLM gate helpers for futures setup entry adapters."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from importlib.util import find_spec
from typing import Any

from shared.strategy.base import EntryContext

if find_spec("shared.strategy.entry.setup_entry_configs") is not None:
    from shared.strategy.entry.setup_entry_configs import LLMTuningConfig
else:
    LLMTuningConfig = Any

logger = logging.getLogger(__name__)

__all__ = [
    "apply_llm_tuning_setup_a",
    "apply_llm_tuning_setup_c",
    "apply_llm_veto",
    "get_llm_context",
    "normalise_regime_label",
    "resolve_regime_label",
    "send_veto_alert_background",
]


def get_llm_context(context: EntryContext) -> Any | None:
    """Return the LLM market context from ``context.market_context`` if present.

    The decision-engine market context is never returned here. Only the LLM
    variant carries the ``regime``, ``risk_score``, and ``confidence`` fields.
    This stays duck-typed to avoid importing shared LLM classes in the adapter
    layer.
    """
    mc = context.market_context
    if mc is None:
        return None
    if (
        hasattr(mc, "regime")
        and hasattr(mc, "risk_score")
        and hasattr(mc, "confidence")
    ):
        return mc
    return None


def normalise_regime_label(value: Any) -> str | None:
    """Return a YAML-comparable regime label from strings or enum-like objects."""
    if value is None:
        return None
    name = getattr(value, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    text = str(value).strip()
    if not text:
        return None
    if "." in text:
        suffix = text.rsplit(".", 1)[-1].strip()
        if suffix:
            return suffix
    return text


def resolve_regime_label(context: EntryContext) -> str | None:
    """Resolve the active regime label for entry adapter direction gates.

    Setup A/C use the LLM market context directly. Setup D is normally
    indicator-only, but the live orchestrator still injects the current market
    regime into ``EntryContext.metadata``. Read that metadata fallback so
    configured direction blocks work even without an attached LLM context.
    """
    llm_ctx = get_llm_context(context)
    if llm_ctx is not None:
        return normalise_regime_label(getattr(llm_ctx, "regime", None))

    metadata = context.metadata or {}
    for key in ("regime", "market_state"):
        regime = normalise_regime_label(metadata.get(key))
        if regime is not None:
            return regime
    return None


def apply_llm_tuning_setup_a(
    decision_signal: Any,
    llm_ctx: Any,
    tuning: LLMTuningConfig,
    min_signal_confidence: float = 0.0,
) -> tuple[float | None, str | None]:
    """Apply LLM threshold adjustments for Setup A.

    Returns ``(adjusted_confidence, skip_reason)``. When ``skip_reason`` is not
    ``None``, the caller must drop the signal.
    """
    regime: str = str(llm_ctx.regime)
    direction: str = str(decision_signal.direction)
    risk_mode_raw = llm_ctx.risk_mode
    risk_mode: str = (
        risk_mode_raw.name if hasattr(risk_mode_raw, "name") else str(risk_mode_raw)
    )
    risk_score: float = float(llm_ctx.risk_score)

    if direction == "long" and regime in tuning.long_blocked_regimes:
        logger.debug(
            "SetupA LLM gating: long signal dropped; regime=%s is in "
            "long_blocked_regimes",
            regime,
        )
        return None, "llm_long_blocked"

    if direction == "short" and regime in tuning.short_blocked_regimes:
        logger.debug(
            "SetupA LLM gating: short signal dropped; regime=%s is in "
            "short_blocked_regimes",
            regime,
        )
        return None, "llm_short_blocked"

    adjusted_confidence = float(decision_signal.confidence)
    if risk_score > tuning.risk_off_threshold and risk_mode == "RISK_OFF":
        adjusted_confidence = (
            adjusted_confidence * tuning.risk_off_confidence_multiplier
        )
        logger.debug(
            "SetupA LLM tuning: confidence scaled %.3f to %.3f "
            "(risk_score=%.1f > %.1f, RISK_OFF)",
            decision_signal.confidence,
            adjusted_confidence,
            risk_score,
            tuning.risk_off_threshold,
        )
        if adjusted_confidence < min_signal_confidence:
            logger.debug(
                "SetupA LLM tuning: scaled confidence %.3f < min %.3f; "
                "signal dropped",
                adjusted_confidence,
                min_signal_confidence,
            )
            return None, "llm_threshold_unmet"

    return adjusted_confidence, None


def apply_llm_tuning_setup_c(
    decision_signal: Any,
    llm_ctx: Any,
    tuning: LLMTuningConfig,
) -> tuple[float | None, str | None]:
    """Apply LLM threshold adjustments for Setup C.

    Returns ``(adjusted_confidence, skip_reason)``. When ``skip_reason`` is not
    ``None``, the caller must drop the signal.
    """
    regime: str = str(llm_ctx.regime)
    direction: str = str(decision_signal.direction)
    risk_mode_raw = llm_ctx.risk_mode
    risk_mode: str = (
        risk_mode_raw.name if hasattr(risk_mode_raw, "name") else str(risk_mode_raw)
    )

    if direction == "long" and regime in tuning.long_blocked_regimes:
        logger.debug(
            "SetupC LLM gating: long signal dropped; regime=%s is in "
            "long_blocked_regimes",
            regime,
        )
        return None, "llm_long_blocked"

    if direction == "short" and regime in tuning.short_blocked_regimes:
        logger.debug(
            "SetupC LLM gating: short signal dropped; regime=%s is in "
            "short_blocked_regimes",
            regime,
        )
        return None, "llm_short_blocked"

    adjusted_confidence = float(decision_signal.confidence)
    if regime == tuning.bull_strong_regime and risk_mode == "RISK_ON":
        boosted = adjusted_confidence / tuning.atr_loose_factor
        adjusted_confidence = min(boosted, 1.0)
        logger.debug(
            "SetupC LLM tuning: ATR loose-factor applied; confidence %.3f to %.3f "
            "(regime=%s, RISK_ON, atr_loose_factor=%.2f)",
            decision_signal.confidence,
            adjusted_confidence,
            regime,
            tuning.atr_loose_factor,
        )

    return adjusted_confidence, None


def apply_llm_veto(
    decision_signal: Any,
    llm_ctx: Any,
    tuning: LLMTuningConfig,
    *,
    setup_name: str,
    symbol: str,
    ts: datetime,
) -> tuple[bool, str | None]:
    """Evaluate whether the LLM can veto an entry signal.

    This helper is entry-only. Exit and stop signals must not reach it.
    """
    if not tuning.enabled or not tuning.veto_enabled:
        return False, None

    if float(llm_ctx.confidence) < tuning.veto_min_confidence:
        return False, None

    direction: str = str(decision_signal.direction)
    overall_signal_raw = getattr(llm_ctx, "overall_signal", "")
    overall_signal: str = (
        overall_signal_raw.name
        if hasattr(overall_signal_raw, "name")
        else str(overall_signal_raw)
    )
    regime: str = str(llm_ctx.regime)

    veto_triggered = (
        direction == "long" and overall_signal == tuning.veto_long_block_signal
    ) or (direction == "short" and overall_signal == tuning.veto_short_block_signal)

    if not veto_triggered:
        return False, None

    logger.info(
        "LLM veto: %s %s signal dropped; overall_signal=%s confidence=%.3f "
        "veto_min_confidence=%.3f setup=%s symbol=%s",
        direction,
        setup_name,
        overall_signal,
        float(llm_ctx.confidence),
        tuning.veto_min_confidence,
        setup_name,
        symbol,
    )

    ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)

    from shared.strategy.llm_veto_logger import record_veto

    record_veto(
        {
            "ts": ts,
            "symbol": symbol,
            "direction": direction,
            "regime": regime,
            "overall_signal": overall_signal,
            "confidence": float(llm_ctx.confidence),
            "setup": setup_name,
        }
    )

    send_veto_alert_background(
        symbol=symbol,
        direction=direction,
        regime=regime,
        overall_signal=overall_signal,
        confidence=float(llm_ctx.confidence),
        setup_name=setup_name,
        ts=ts,
    )

    return True, "llm_veto"


def send_veto_alert_background(
    *,
    symbol: str,
    direction: str,
    regime: str,
    overall_signal: str,
    confidence: float,
    setup_name: str,
    ts: datetime,
) -> None:
    """Schedule a Telegram veto alert without blocking the caller."""
    import asyncio

    from shared.notification.telegram import notifier_for_domain

    notifier = notifier_for_domain("futures")
    if notifier is None:
        logger.debug("llm_veto Telegram alert skipped; futures notifier unavailable")
        return

    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = (
        "<b>LLM Veto</b> - entry blocked\n"
        f"Setup: {setup_name}\n"
        f"Symbol: {symbol}\n"
        f"Direction: {direction}\n"
        f"Regime: {regime}\n"
        f"Overall signal: {overall_signal}\n"
        f"LLM confidence: {confidence:.2f}\n"
        f"Time: {ts_str}"
    )

    async def _send() -> None:
        try:
            await notifier.send_message(msg, is_critical=True)
        except Exception as exc:
            logger.warning("llm_veto Telegram alert failed: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        logger.debug(
            "llm_veto Telegram alert not scheduled; no running event loop; "
            "message: %s",
            msg,
        )
