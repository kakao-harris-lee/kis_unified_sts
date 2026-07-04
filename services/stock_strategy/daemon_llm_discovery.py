"""LLM-discovery signal methods for StockStrategyDaemon."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.models.signal import Signal
from shared.risk.market_risk_gate import MarketRiskGateDecision
from shared.streaming.stock_signal_eval import (
    OUTCOME_REJECT,
    OUTCOME_SIGNAL,
    REJECT_LLM_CONFIDENCE_BELOW_MIN,
    REJECT_LLM_COOLDOWN,
    REJECT_LLM_EXCLUDED,
    REJECT_LLM_METADATA_MISSING,
    REJECT_LLM_NO_PRICE,
    REJECT_LLM_NOT_ALLOWED,
    REJECT_LLM_QUALITY_BELOW_MIN,
    SignalEvalCollector,
)

logger = logging.getLogger("services.stock_strategy.daemon")
_STREAM_TTL_SECONDS = 86400
_KST = ZoneInfo("Asia/Seoul")


class StockStrategyLLMDiscoveryMixin:
    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _llm_reference_price(
        self,
        symbol: str,
        metadata: dict[str, Any],
        scanner_indicators: dict[str, dict[str, Any]],
    ) -> float | None:
        for key in (
            "reference_price",
            "entry_price",
            "current_price",
            "price",
            "close",
            "daily_close",
        ):
            price = self._as_float(metadata.get(key))
            if price is not None and price > 0:
                return price

        scanner = scanner_indicators.get(symbol)
        if isinstance(scanner, dict):
            price = self._as_float(scanner.get("daily_close"))
            if price is not None and price > 0:
                return price
        return None

    @staticmethod
    def _record_llm_reject(
        evaluator: SignalEvalCollector | None,
        strategy: str,
        symbol: str,
        reason: str,
    ) -> None:
        if evaluator is None:
            return
        evaluator.record(strategy, symbol, OUTCOME_REJECT, reason)

    def _log_llm_skip(
        self,
        *,
        symbol: str,
        reason: str,
        now_ts: float,
        detail: str = "",
    ) -> None:
        interval = self._llm_signal_config.skip_log_interval_seconds
        cache_key = (symbol, reason)
        last_logged = self._llm_skip_log_cache.get(cache_key)
        if last_logged is not None and now_ts - last_logged < interval:
            return
        self._llm_skip_log_cache[cache_key] = now_ts
        suffix = f" {detail}" if detail else ""
        logger.info(
            "LLM discovery candidate skipped code=%s reason=%s%s",
            symbol,
            reason,
            suffix,
        )

    async def _publish_llm_discovery_signals(
        self,
        *,
        scanner_indicators: dict[str, dict[str, Any]],
        now: datetime,
        evaluator: SignalEvalCollector | None,
        allowed_codes: set[str] | None = None,
        excluded_codes: set[str] | None = None,
        gate_decision: MarketRiskGateDecision | None = None,
        gate_trace: dict[str, Any] | None = None,
    ) -> int:
        cfg = self._llm_signal_config
        if not cfg.enabled or cfg.max_per_cycle <= 0:
            return 0

        payload = self._trade_targets_payload
        if not payload:
            return 0

        codes_raw = payload.get("codes", [])
        metadata_raw = payload.get("metadata", {})
        names_raw = payload.get("names", {})
        scores_raw = payload.get("scores", {})
        if not isinstance(codes_raw, list) or not isinstance(metadata_raw, dict):
            return 0

        names = names_raw if isinstance(names_raw, dict) else {}
        scores = scores_raw if isinstance(scores_raw, dict) else {}
        excluded = excluded_codes or set()
        published = 0
        now_ts = now.timestamp()

        for raw_code in codes_raw:
            symbol = str(raw_code).strip()
            if not symbol:
                continue
            if allowed_codes is not None and symbol not in allowed_codes:
                self._record_llm_reject(
                    evaluator, cfg.strategy_name, symbol, REJECT_LLM_NOT_ALLOWED
                )
                continue
            if symbol in excluded:
                self._record_llm_reject(
                    evaluator, cfg.strategy_name, symbol, REJECT_LLM_EXCLUDED
                )
                continue

            metadata = metadata_raw.get(symbol, {})
            if not isinstance(metadata, dict):
                self._record_llm_reject(
                    evaluator, cfg.strategy_name, symbol, REJECT_LLM_METADATA_MISSING
                )
                continue

            quality = self._as_float(metadata.get("llm_quality"))
            if quality is None or quality < cfg.min_llm_quality:
                self._record_llm_reject(
                    evaluator, cfg.strategy_name, symbol, REJECT_LLM_QUALITY_BELOW_MIN
                )
                continue

            # NOTE on the confidence gate: for LLM-only symbols the fused
            # ``llm_confidence`` is typically 1.0 (no screener risk flags elevate
            # the penalty), so ``min_llm_confidence`` is a weak filter here.
            # ``min_llm_quality`` is the operative gate for LLM-only admissions.
            # The missing-confidence → 1.0 default is intentional best-effort
            # (treats no risk-flag information as full confidence).
            confidence = self._as_float(metadata.get("llm_confidence"))
            if confidence is None:
                confidence = 1.0
            if confidence < cfg.min_llm_confidence:
                self._record_llm_reject(
                    evaluator,
                    cfg.strategy_name,
                    symbol,
                    REJECT_LLM_CONFIDENCE_BELOW_MIN,
                )
                continue

            # Cooldown check — Redis-backed so a daemon restart does not reset
            # the 24h cooldown and cause duplicate emissions for the same symbol.
            # Redis DB1 hash stock:daemon:llm_cooldown maps symbol → epoch float.
            # In-memory cache is a fast-path for the same process; Redis is the
            # source of truth (survives restarts).
            in_cooldown = False
            cooldown_until_ts: float | None = None
            try:
                stored_raw = await self.redis.hget(self._llm_cooldown_key, symbol)
                if stored_raw is not None:
                    stored_ts = float(stored_raw)
                    if now_ts - stored_ts < cfg.cooldown_seconds:
                        in_cooldown = True
                        cooldown_until_ts = stored_ts + cfg.cooldown_seconds
                    else:
                        # Stale entry in Redis — also clear local cache
                        self._llm_last_published_cache.pop(symbol, None)
                elif symbol in self._llm_last_published_cache:
                    # Local cache hit (same process, Redis missed write earlier)
                    if (
                        now_ts - self._llm_last_published_cache[symbol]
                        < cfg.cooldown_seconds
                    ):
                        in_cooldown = True
                        cooldown_until_ts = (
                            self._llm_last_published_cache[symbol]
                            + cfg.cooldown_seconds
                        )
            except Exception:
                # Redis read failed — fall back to in-memory cache (best-effort).
                # Log at warning so ops can diagnose but do NOT crash the loop.
                logger.warning(
                    "llm cooldown redis read failed for symbol=%s; using in-memory fallback",
                    symbol,
                    exc_info=True,
                )
                cached = self._llm_last_published_cache.get(symbol)
                if cached is not None and now_ts - cached < cfg.cooldown_seconds:
                    in_cooldown = True
                    cooldown_until_ts = cached + cfg.cooldown_seconds
            if in_cooldown:
                self._record_llm_reject(
                    evaluator, cfg.strategy_name, symbol, REJECT_LLM_COOLDOWN
                )
                cooldown_until = (
                    datetime.fromtimestamp(cooldown_until_ts, tz=_KST).isoformat()
                    if cooldown_until_ts is not None
                    else ""
                )
                self._log_llm_skip(
                    symbol=symbol,
                    reason=REJECT_LLM_COOLDOWN,
                    now_ts=now_ts,
                    detail=(
                        f"cooldown_until_kst={cooldown_until}" if cooldown_until else ""
                    ),
                )
                continue

            price = self._llm_reference_price(symbol, metadata, scanner_indicators)
            # Prefer a live tick when one is available so the (paper) fill is
            # anchored to the current market rather than a possibly-stale plan
            # entry_price / prior-day daily_close. Falls back to the reference
            # price when the symbol has no live tick yet (e.g. not yet warmed).
            price_source = "target_metadata_or_daily_close"
            try:
                live_md = await self.feed.get_current_price(symbol)
            except Exception:
                live_md = None
            if isinstance(live_md, dict):
                live_price = self._as_float(live_md.get("close")) or self._as_float(
                    live_md.get("price")
                )
                if live_price is not None and live_price > 0:
                    price = live_price
                    price_source = "live_tick"
            if price is None:
                self._record_llm_reject(
                    evaluator, cfg.strategy_name, symbol, REJECT_LLM_NO_PRICE
                )
                continue

            score = self._as_float(scores.get(symbol))
            signal = Signal(
                code=symbol,
                name=str(names.get(symbol, "")),
                strategy=cfg.strategy_name,
                price=price,
                quantity=cfg.quantity,
                confidence=max(0.0, min(1.0, confidence)),
                timestamp=now,
                metadata={
                    "source": "trade_targets_llm",
                    "signal_direction": "long",
                    "llm_quality": quality,
                    "llm_confidence": confidence,
                    "llm_effective_quality": metadata.get("llm_effective_quality"),
                    "llm_snapshot_id": metadata.get("llm_snapshot_id"),
                    "llm_only": bool(metadata.get("llm_only")),
                    "llm_final": bool(metadata.get("llm_final")),
                    "risk_flags": metadata.get("risk_flags", []),
                    "trade_target_score": score,
                    "entry_price": metadata.get("entry_price"),
                    "stop_loss": metadata.get("stop_loss"),
                    "take_profit": metadata.get("take_profit"),
                    "position_size": metadata.get("position_size"),
                    "plan_confidence": metadata.get("plan_confidence"),
                    "llm_plan_strategy": metadata.get("llm_plan_strategy"),
                    "reference_price_source": price_source,
                },
            )

            # LLM-discovery candidates are NEW entries too: same gate trace
            # contract and the same enforce-mode min-confidence admission as
            # the technical loop (blanket allow=False blocks never reach here
            # — the cycle already early-returned).
            self._attach_market_risk_trace(signal, gate_trace)
            if not self._market_risk_gate_admits(signal, gate_decision):
                self._record_llm_reject(
                    evaluator,
                    cfg.strategy_name,
                    symbol,
                    gate_decision.reason,  # type: ignore[union-attr]
                )
                self._log_llm_skip(
                    symbol=symbol,
                    reason="market_risk_gate",
                    now_ts=now_ts,
                    detail=gate_decision.reason,  # type: ignore[union-attr]
                )
                continue

            await self._publish(signal)
            # Persist cooldown to Redis (source of truth) and local cache.
            # TTL on the hash is refreshed to cooldown_seconds so stale entries
            # self-expire if the daemon stops emitting for a symbol.
            self._llm_last_published_cache[symbol] = now_ts
            try:
                await self.redis.hset(self._llm_cooldown_key, symbol, str(now_ts))
                await self.redis.expire(
                    self._llm_cooldown_key,
                    int(cfg.cooldown_seconds) + 60,
                )
            except Exception:
                logger.warning(
                    "llm cooldown redis write failed for symbol=%s; "
                    "in-memory fallback active until restart",
                    symbol,
                    exc_info=True,
                )
            self._eval_record(
                evaluator,
                cfg.strategy_name,
                symbol,
                OUTCOME_SIGNAL,
                "long",
            )
            published += 1
            if published >= cfg.max_per_cycle:
                break

        return published
