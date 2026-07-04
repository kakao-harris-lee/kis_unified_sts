"""Market-risk gate methods for StockStrategyDaemon."""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from typing import Any

from shared.models.signal import Signal
from shared.risk.market_risk_gate import (
    MarketRiskGateDecision,
    evaluate_market_risk_gate,
)

logger = logging.getLogger("services.stock_strategy.daemon")


class StockStrategyMarketRiskMixin:
    def _evaluate_market_risk_gate(
        self, now: datetime
    ) -> MarketRiskGateDecision | None:
        """Evaluate the shared market-risk ENTRY gate once per eval cycle.

        The decision depends only on ``(asset="stock", side="long")`` and the
        cycle clock, so one evaluation covers every candidate this cycle
        (mirrors the once-per-cycle bear regime gate). Stock is long-only,
        hence ``side="long"``. The Redis hash read happens inside the shared
        evaluator (sync client) and it never raises — every failure path is
        fail-open by contract. ENTRY ONLY: never consulted by any exit path.

        Returns ``None`` when the gate is unwired (no config / no sync redis)
        so legacy construction keeps pre-gate behavior bit-for-bit.
        """
        cfg = self._market_risk_gate_config
        if cfg is None or self._market_risk_gate_redis is None:
            return None
        return evaluate_market_risk_gate(
            self._market_risk_gate_redis,
            cfg,
            asset="stock",
            side="long",
            now=now,
        )

    def _log_market_risk_would_block(
        self, decision: MarketRiskGateDecision, now_ts: float
    ) -> None:
        """Shadow-mode observation log, throttled per reason.

        The shadow verdict repeats every eval cycle (~60s) for as long as the
        band holds, so this logs at most once per configured interval per
        reason (same pattern as the throttled setup-eval / LLM-skip logs).
        """
        interval = self._market_risk_wiring.would_block_log_interval_seconds
        last_logged = self._market_risk_log_cache.get(decision.reason)
        if last_logged is not None and now_ts - last_logged < interval:
            return
        self._market_risk_log_cache[decision.reason] = now_ts
        logger.info(
            "market risk gate (shadow): would block new stock entries — %s "
            "(band=%s score=%s regime=%s)",
            decision.reason,
            decision.band,
            decision.score,
            decision.regime,
        )

    @staticmethod
    def _attach_market_risk_trace(
        signal: Signal, gate_trace: dict[str, Any] | None
    ) -> None:
        """Attach the fixed-key gate trace as ``metadata["market_risk_gate"]``.

        Applied in ALL modes (off/shadow/enforce) — fixed contract with the
        downstream /signals trace lane; the payload keys come verbatim from
        ``gate_trace_payload``. Best-effort, like the ``bear_override`` tag.
        """
        if gate_trace is None:
            return
        with contextlib.suppress(Exception):
            signal.metadata["market_risk_gate"] = dict(gate_trace)

    def _market_risk_gate_admits(
        self, signal: Signal, decision: MarketRiskGateDecision | None
    ) -> bool:
        """Per-signal enforce-mode min-confidence admission.

        Only ``mode == "enforce"`` applies matrix values — in shadow the
        observed ``min_confidence`` rides along in the trace but must never
        reject (shared-gate contract). Blanket ``allow=False`` blocks are
        handled at cycle level, not here. Unknown labels and unreadable
        confidences fail open.
        """
        if decision is None or decision.mode != "enforce":
            return True
        threshold = self._market_risk_wiring.min_confidence_threshold(
            decision.min_confidence
        )
        if threshold is None:
            if decision.min_confidence:
                logger.warning(
                    "market risk gate: unknown min_confidence label %r — "
                    "admitting (fail-open)",
                    decision.min_confidence,
                )
            return True
        try:
            return float(signal.confidence) >= threshold
        except (TypeError, ValueError):
            return True
