"""Daily directional bias from LLM market context (compute-once, Redis-persisted)."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo
from shared.strategy.gates.adapter_helper import acquire_infra_clients

logger = logging.getLogger(__name__)
DAILY_BIAS_KEY = "trading:futures:daily_bias"
_LONG_SIGNALS = {"STRONG_BULLISH", "BULLISH"}
_SHORT_SIGNALS = {"STRONG_BEARISH", "BEARISH"}
_KST = ZoneInfo("Asia/Seoul")


def bias_from_context(overall_signal_name, confidence, bias_min_confidence=0.5, non_long_regimes=None, regime=""):
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
    eod = datetime(now.year, now.month, now.day, 15, 45, 0, tzinfo=_KST)
    return max(60, int((eod - now).total_seconds()))


class DailyBiasProvider:
    def __init__(self, bias_min_confidence: float = 0.5, non_long_regimes: list[str] | None = None) -> None:
        self._bias_min_confidence = bias_min_confidence
        self._non_long_regimes = non_long_regimes or []

    def get_or_compute_bias(self, market_context: Any | None, now_kst_dt: datetime) -> Literal["long", "short", "flat"]:
        today_str = now_kst_dt.date().isoformat()
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return "flat"
        except Exception:
            return "flat"
        cached = self._read_redis(today_str)
        if cached is not None:
            return cached
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

    def _read_redis(self, today_str):
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
            bias = data.get("bias")
            return bias if bias in ("long", "short", "flat") else None
        except Exception:
            logger.debug("[DailyBias] read failed", exc_info=True)
            return None

    def _write_redis(self, bias, now_kst_dt):
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return
            payload = json.dumps({"bias": bias, "computed_at": now_kst_dt.isoformat(), "date": now_kst_dt.date().isoformat()})
            redis.set(DAILY_BIAS_KEY, payload, ex=_eod_ttl_seconds(now_kst_dt))
        except Exception:
            logger.debug("[DailyBias] write failed", exc_info=True)
