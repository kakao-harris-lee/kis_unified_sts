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
) -> tuple[float | None, str | None, dict[str, Any]]:
    """Apply LLM threshold adjustments for Setup A.

    Returns ``(adjusted_confidence, skip_reason, telemetry)``. When
    ``skip_reason`` is not ``None``, the caller must drop the signal.

    ``telemetry`` carries the RISK_OFF-boost evidence that the 1.0 cap would
    otherwise erase. Before the cap, a persisted ``confidence > 1.0`` was itself
    an unambiguous fingerprint that the multiplier had fired; capping removes
    that fingerprint. The operator review of the old 1.3 default was SETTLED on
    2026-08-05 by neutralising it to 1.0 — which makes these keys the only
    fingerprint left at all, since at 1.0 the emitted confidence is identical to
    an unadjusted one. They are also the evidence base for any future,
    deliberate re-tuning away from neutral.
    Keys (present only when the direction gates below did not drop the signal):

    ``llm_risk_off_boost_applied``
        ``True`` when the RISK_OFF branch ran, ``False`` when it did not. An
        absent key means this helper never ran at all (LLM tuning disabled, no
        LLM context, or context confidence below ``min_context_confidence``) —
        so absence and ``False`` stay distinguishable.
    ``llm_risk_off_base_confidence``
        The pre-boost Setup A confidence. Not recoverable from any other
        surface once the product is capped.
    ``llm_risk_off_raw_confidence``
        The uncapped product ``base * risk_off_confidence_multiplier``. The cap
        bit iff this exceeds 1.0.

    Reach: the caller threads this onto ``Signal.metadata``. That dict is
    in-memory only for the futures orchestrator path — see the OBSERVABILITY
    REACH note on ``SetupAEntryAdapter.generate`` for the enumerated surfaces
    and the one ``services/`` change that would make it queryable — so the
    ``logger.info`` below is currently the only surface that observes the event
    at the shipped ``LOG_LEVEL=INFO``.
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
        return None, "llm_long_blocked", {}

    if direction == "short" and regime in tuning.short_blocked_regimes:
        logger.debug(
            "SetupA LLM gating: short signal dropped; regime=%s is in "
            "short_blocked_regimes",
            regime,
        )
        return None, "llm_short_blocked", {}

    adjusted_confidence = float(decision_signal.confidence)
    telemetry: dict[str, Any] = {"llm_risk_off_boost_applied": False}
    if risk_score > tuning.risk_off_threshold and risk_mode == "RISK_OFF":
        # Cap at the documented Signal.confidence ceiling, mirroring the Setup C
        # branch below. shared/models/signal.py documents 확신도 (0.0 ~ 1.0) but
        # has no validator, so an uncapped multiplier above 1.0 (the shipped
        # value was 1.3 until the 2026-08-05 neutralisation) emitted
        # out-of-range values for any base above 1/1.3 ≈ 0.769. Setup A's base
        # is in [0.5, 1.0] by construction; under the LIVE gate
        # (min_sp500_gap_pct: 0.30) it is the narrower [0.70, 1.00], so the
        # live below-crossover band is only [0.70, 0.7692).
        #
        # Capping only ever lowers the emitted value, so it cannot loosen
        # admission (confidence >= min_confidence) nor promote a signal in the
        # descending-confidence entry contention.
        #
        # It can, however, DEMOTE once an operator tunes the multiplier above
        # 1.0 (at the shipped neutral 1.0 the cap never bites), and that
        # consequence is benign only by accident. The cap collapses the whole
        # previously-ordered band [1.0, multiplier] onto the single value 1.0,
        # so resolution falls through to
        # the next key of services/trading/entry_runtime.py::
        # entry_signal_priority, which is (priority, -confidence, strategy,
        # code). Setup A carries no ``entry_priority``, so a tie resolves by
        # STRATEGY NAME. "setup_a_gap_reversion" happens to sort before
        # "setup_c_event_reaction" and "setup_d_vwap_reversion", so no outcome
        # changes right now. Enabling any futures strategy whose registry name
        # sorts earlier — bb_reversion_15m, llm_directed_indicator,
        # macd_ema_crossover_15m, momentum_breakout_futures (all currently
        # enabled: false) — would hand priority to it in cases where pre-cap
        # Setup A won outright. That is a naming coincidence, not a design:
        # give Setup A an explicit ``entry_priority`` if the ordering must be
        # guaranteed rather than inherited from alphabetical luck.
        base_confidence = adjusted_confidence
        scaled = base_confidence * tuning.risk_off_confidence_multiplier
        adjusted_confidence = min(scaled, 1.0)
        telemetry = {
            "llm_risk_off_boost_applied": True,
            "llm_risk_off_base_confidence": base_confidence,
            "llm_risk_off_raw_confidence": scaled,
        }
        # INFO, not DEBUG: .env.example ships LOG_LEVEL=INFO, and once the
        # product is capped this line is the only surface at the shipped level
        # that records the boost fired at all (see the telemetry note above).
        logger.info(
            "SetupA LLM tuning: RISK_OFF confidence boost applied; "
            "base=%.6f multiplier=%.3f raw=%.6f emitted=%.6f capped=%s "
            "(risk_score=%.1f > %.1f)",
            base_confidence,
            tuning.risk_off_confidence_multiplier,
            scaled,
            adjusted_confidence,
            scaled > 1.0,
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
            return None, "llm_threshold_unmet", telemetry

    return adjusted_confidence, None, telemetry


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
    # Deliberate asymmetry (long/short symmetry rule, CLAUDE.md).
    # The bull-strong boost divides confidence by atr_loose_factor (< 1.0), so
    # it LOOSENS admission. It is long-only by design: a bullish LLM read must
    # never make a SHORT candidate easier to admit. There is intentionally NO
    # symmetric bear-strong boost for shorts — adding one would be new trading
    # behaviour. Net effect: no path in this helper loosens short admission;
    # shorts can only be blocked (above) or pass through unchanged.
    if (
        direction == "long"
        and regime == tuning.bull_strong_regime
        and risk_mode == "RISK_ON"
    ):
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
