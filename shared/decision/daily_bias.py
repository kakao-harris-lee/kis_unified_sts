"""Daily directional bias from LLM market context (compute-once, Redis-persisted).

Intraday refresh (I2 follow-up)
--------------------------------
The original implementation was compute-once: the first valid context after open
set the bias for the day and subsequent calls returned the cached value.

Problem: a NEUTRAL/low-confidence morning read would persist ``flat`` all day,
blocking all entries even if LLM conviction rose later.

Fix: flat biases are re-evaluated after ``bias_refresh_minutes`` (default 60).
Non-flat (directional) biases remain sticky — no intraday direction flip.

Semantics:
- ``bias == flat``  AND ``computed_at > bias_refresh_minutes`` ago → recompute.
- ``bias == flat``  AND within the window                          → return flat.
- ``bias == long/short``                                           → always sticky.

All fail-safe semantics are preserved: Redis unavailable, bad context, or
low-confidence context all return ``flat``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from shared.strategy.gates.adapter_helper import acquire_infra_clients

logger = logging.getLogger(__name__)
DAILY_BIAS_KEY = "trading:futures:daily_bias"
_LONG_SIGNALS = {"STRONG_BULLISH", "BULLISH"}
_SHORT_SIGNALS = {"STRONG_BEARISH", "BEARISH"}
_KST = ZoneInfo("Asia/Seoul")


def bias_from_context(overall_signal_name: str, confidence: float, bias_min_confidence: float = 0.5, non_long_regimes: list[str] | None = None, regime: str = "") -> Literal["long", "short", "flat"]:
    if confidence < bias_min_confidence:
        return "flat"
    signal = overall_signal_name.upper()
    if signal in _LONG_SIGNALS:
        raw: Literal["long", "short", "flat"] = "long"
    elif signal in _SHORT_SIGNALS:
        raw = "short"
    else:
        return "flat"
    if raw == "long" and non_long_regimes and regime in non_long_regimes:
        return "flat"
    return raw


def _eod_ttl_seconds(now: datetime) -> int:
    if now.tzinfo is None:
        now = now.replace(tzinfo=_KST)
    eod = datetime(now.year, now.month, now.day, 15, 45, 0, tzinfo=_KST)
    return max(60, int((eod - now).total_seconds()))


class DailyBiasProvider:
    def __init__(
        self,
        bias_min_confidence: float = 0.5,
        non_long_regimes: list[str] | None = None,
        bias_refresh_minutes: int = 60,
    ) -> None:
        self._bias_min_confidence = bias_min_confidence
        self._non_long_regimes = non_long_regimes or []
        self._bias_refresh_minutes = bias_refresh_minutes

    def get_or_compute_bias(self, market_context: Any | None, now_kst_dt: datetime) -> Literal["long", "short", "flat"]:
        today_str = now_kst_dt.date().isoformat()
        cached_data = self._read_redis_raw(today_str)

        if cached_data is not None:
            cached_bias = cached_data.get("bias")
            if cached_bias not in ("long", "short", "flat"):
                pass  # invalid — fall through to recompute
            elif cached_bias in ("long", "short"):
                # Non-flat directional bias is sticky for the day.
                return cached_bias  # type: ignore[return-value]
            else:
                # cached_bias == "flat": re-evaluate if stale, hold if within window.
                computed_at_str = cached_data.get("computed_at", "")
                try:
                    computed_at = datetime.fromisoformat(computed_at_str)
                    age = now_kst_dt - computed_at
                    if age <= timedelta(minutes=self._bias_refresh_minutes):
                        return "flat"
                    # Stale flat → fall through to recompute below.
                    logger.info(
                        "[DailyBias] stale flat (age=%.0fs > %dm window) — recomputing",
                        age.total_seconds(),
                        self._bias_refresh_minutes,
                    )
                except (ValueError, TypeError):
                    # Cannot parse computed_at — recompute to be safe.
                    pass

        # Acquire Redis client for writing.
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return "flat"
        except Exception:
            return "flat"
        if market_context is None:
            return "flat"
        try:
            name = market_context.overall_signal.name
            confidence = float(market_context.confidence)
            regime = str(getattr(market_context, "regime", ""))
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning("[DailyBias] bad market_context: %s", exc)
            return "flat"
        bias = bias_from_context(name, confidence, self._bias_min_confidence, self._non_long_regimes, regime)
        logger.info("[DailyBias] %s (signal=%s conf=%.2f regime=%s)", bias, name, confidence, regime)
        self._write_redis(bias, now_kst_dt)
        return bias

    def _read_redis_raw(self, today_str: str) -> dict | None:
        """Return the parsed Redis payload dict if it exists and matches today, else None."""
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return None
            raw = redis.get(DAILY_BIAS_KEY)
            if raw is None:
                return None
            data = json.loads(raw)
            if data.get("date") != today_str:
                return None
            return data
        except Exception:
            logger.debug("[DailyBias] read failed", exc_info=True)
            return None

    def _write_redis(self, bias: str, now_kst_dt: datetime) -> None:
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return
            payload = json.dumps({"bias": bias, "computed_at": now_kst_dt.isoformat(), "date": now_kst_dt.date().isoformat()})
            redis.set(DAILY_BIAS_KEY, payload, ex=_eod_ttl_seconds(now_kst_dt))
        except Exception:
            logger.debug("[DailyBias] write failed", exc_info=True)
