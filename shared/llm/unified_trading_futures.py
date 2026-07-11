"""Futures analysis methods for ``UnifiedTradingAnalyzer``."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from .data_classes import FuturesTradingPlan, MarketBias
from .errors import DataUnavailableError

logger = logging.getLogger("shared.llm.llm_analyzer")


class FuturesAnalysisMixin:
    async def _analyze_futures(self) -> tuple[FuturesTradingPlan | None, dict]:
        """선물 분석"""
        logger.info("Starting futures analysis")

        missing_sources: list[str] = []

        def _record_missing(err: DataUnavailableError):
            label = err.source if not err.detail else f"{err.source}:{err.detail}"
            missing_sources.append(label)

        global_data = self._collect_futures_global(_record_missing)
        events, high_events = self._collect_futures_events(_record_missing)
        flow_data = self._collect_futures_flow(_record_missing, missing_sources)
        technical = self._collect_futures_technical(_record_missing)
        overall_score = self._compute_futures_score(
            global_data, flow_data, technical, high_events
        )
        overall_bias = self._determine_futures_bias(overall_score)

        direction, confidence, entry, stop_loss, take_profit, entry_cond = (
            self._build_futures_strategy(overall_score, technical)
        )

        position = (
            "풀" if confidence == "높음" else "하프" if confidence == "중간" else "쿼터"
        )
        time_horizon = "장중" if high_events else "오버나이트"

        catalysts, risks = self._build_futures_catalysts_and_risks(
            global_data,
            flow_data,
            high_events,
            technical,
            missing_sources,
        )

        plan = self._build_futures_plan(
            technical,
            direction,
            confidence,
            entry_cond,
            entry,
            stop_loss,
            take_profit,
            position,
            time_horizon,
            risks,
            catalysts,
        )

        analysis_data = self._build_futures_analysis_data(
            overall_score,
            overall_bias,
            global_data,
            flow_data,
            technical,
            events,
            missing_sources,
        )

        logger.info(f"Futures recommendation: {direction} ({confidence})")
        return plan, analysis_data

    def _collect_futures_global(
        self,
        record_missing,
    ) -> Any | None:
        try:
            return self.futures_global_collector.collect()
        except DataUnavailableError as e:
            record_missing(e)
        return None

    def _collect_futures_events(
        self,
        record_missing,
    ) -> tuple[list[Any], list[Any]]:
        try:
            events = self.futures_event_collector.collect()
            high_events = [e for e in events if e.importance == "높음"]
            return events, high_events
        except DataUnavailableError as e:
            record_missing(e)
        return [], []

    def _collect_futures_flow(
        self,
        record_missing,
        missing_sources: list[str],
    ) -> Any | None:
        try:
            flow_data, flow_missing = self.futures_flow_collector.collect()
            missing_sources.extend([f"futures_flow:{m}" for m in flow_missing])
            return flow_data
        except DataUnavailableError as e:
            record_missing(e)
        return None

    def _collect_futures_technical(
        self,
        record_missing,
    ) -> dict[str, Any] | None:
        try:
            return self.futures_tech_analyzer.analyze()
        except DataUnavailableError as e:
            record_missing(e)
        return None

    def _compute_futures_score(
        self,
        global_data,
        flow_data,
        technical,
        high_events: list[Any],
    ) -> float:
        score_components: list[tuple[float, float]] = []
        if global_data is not None:
            score_components.append(
                (global_data.global_score, self.config.futures_weight_global)
            )
        if flow_data is not None:
            score_components.append(
                (flow_data.flow_score, self.config.futures_weight_flow)
            )
        if technical is not None:
            score_components.append(
                (technical["score"], self.config.futures_weight_technical)
            )

        if score_components:
            total_weight = sum(w for _s, w in score_components) or 1.0
            overall_score = sum(s * w for s, w in score_components) / total_weight
        else:
            overall_score = 0.0

        if high_events:
            overall_score *= 0.8
        return overall_score

    def _determine_futures_bias(overall_score: float) -> MarketBias:
        if overall_score >= 30:
            return MarketBias.STRONG_BULLISH
        if overall_score >= 15:
            return MarketBias.BULLISH
        if overall_score <= -30:
            return MarketBias.STRONG_BEARISH
        if overall_score <= -15:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    def _build_futures_strategy(
        self,
        overall_score: float,
        technical: dict[str, Any] | None,
    ) -> tuple[str, str, float, float, float, str]:
        insufficient_data = technical is None
        entry = technical["index_price"] if technical else 0.0
        if insufficient_data:
            return "관망", "낮음", entry, 0, 0, "데이터 부족으로 관망"

        if overall_score >= 25:
            confidence = "높음" if overall_score >= 40 else "중간"
            stop_loss = entry - self.config.futures_stop_loss_pt
            take_profit = entry + self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 돌파 또는 시가 진입"
            return "롱", confidence, entry, stop_loss, take_profit, entry_cond

        if overall_score <= -25:
            confidence = "높음" if overall_score <= -40 else "중간"
            stop_loss = entry + self.config.futures_stop_loss_pt
            take_profit = entry - self.config.futures_take_profit_pt
            entry_cond = f"5일선({technical['ma5']:.2f}) 이탈 또는 시가 진입"
            return "숏", confidence, entry, stop_loss, take_profit, entry_cond

        return "관망", "낮음", entry, 0, 0, "조건 충족 시까지 대기"

    def _build_futures_catalysts_and_risks(
        self,
        global_data,
        flow_data,
        high_events: list[Any],
        technical: dict[str, Any] | None,
        missing_sources: list[str],
    ) -> tuple[list[str], list[str]]:
        catalysts: list[str] = []
        risks: list[str] = []

        self._append_global_catalysts(global_data, catalysts)
        self._append_flow_catalysts(
            flow_data,
            catalysts,
            self.config.futures_flow_foreign_catalyst_cum20_threshold,
        )
        self._append_flow_risks(flow_data, risks)
        self._append_market_risks(global_data, high_events, technical, risks)
        self._append_missing_source_risks(missing_sources, risks)

        return catalysts, risks

    @staticmethod
    def _append_global_catalysts(global_data: Any, catalysts: list[str]) -> None:
        if global_data and global_data.sp500_change_pct > 0.5:
            catalysts.append(f"미국 증시 강세 ({global_data.sp500_change_pct:+.1f}%)")

    @staticmethod
    def _append_flow_catalysts(
        flow_data: Any,
        catalysts: list[str],
        cum20_threshold: float,
    ) -> None:
        # Re-pointed off the always-None ``foreign_futures_5d`` (F2): the flow
        # collector never sources a 5-day figure, so that catalyst could never
        # fire. The live multi-day figure from market:structure is the 20-day
        # cumulative foreign net (``foreign_futures_cum20``), which preserves the
        # original "sustained foreign accumulation" intent. The threshold is
        # window-scaled + config-driven; ``None`` (no source) → no catalyst.
        if (
            flow_data
            and flow_data.foreign_futures_cum20 is not None
            and flow_data.foreign_futures_cum20 > cum20_threshold
        ):
            catalysts.append(
                f"외국인 20일 누적 순매수 ({flow_data.foreign_futures_cum20:+,.0f})"
            )
        if flow_data and flow_data.basis is not None and flow_data.basis < -1:
            catalysts.append(f"선물 저평가 (베이시스 {flow_data.basis:.2f}pt)")

    @staticmethod
    def _append_flow_risks(flow_data: Any, risks: list[str]) -> None:
        if not flow_data or flow_data.microstructure_score is None:
            return
        if flow_data.microstructure_score <= -6:
            risks.append(
                f"단기 주문흐름 매도 우위 (점수 {flow_data.microstructure_score:+.1f})"
            )

    @staticmethod
    def _append_market_risks(
        global_data: Any,
        high_events: list[Any],
        technical: dict[str, Any] | None,
        risks: list[str],
    ) -> None:
        if global_data and global_data.vix > 20:
            risks.append(f"VIX {global_data.vix:.1f} 상승")
        if high_events:
            risks.append(f"주요 이벤트: {high_events[0].event}")
        if technical and technical["rsi"] > 70:
            risks.append(f"RSI {technical['rsi']:.0f} 과매수")
        elif technical and technical["rsi"] < 30:
            risks.append(f"RSI {technical['rsi']:.0f} 과매도")

    @staticmethod
    def _append_missing_source_risks(
        missing_sources: list[str], risks: list[str]
    ) -> None:
        if missing_sources:
            risks.append(f"데이터 누락: {', '.join(missing_sources)}")

    def _build_futures_plan(
        self,
        technical: dict[str, Any] | None,
        direction: str,
        confidence: str,
        entry_cond: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        position: str,
        time_horizon: str,
        risks: list[str],
        catalysts: list[str],
    ) -> FuturesTradingPlan | None:
        if technical is None:
            return None
        return FuturesTradingPlan(
            direction=direction,
            confidence=confidence,
            entry_condition=entry_cond,
            entry_price=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            position_size=position,
            time_horizon=time_horizon,
            key_levels=[
                technical["pivot"],
                technical["support_1"],
                technical["resistance_1"],
            ],
            risk_factors=risks,
            catalysts=catalysts,
        )

    def _build_futures_analysis_data(
        overall_score: float,
        overall_bias: MarketBias,
        global_data,
        flow_data,
        technical,
        events: list[Any],
        missing_sources: list[str],
    ) -> dict[str, Any]:
        return {
            "overall_score": round(overall_score, 1),
            "overall_bias": overall_bias.value,
            "global": asdict(global_data) if global_data else None,
            "flow": asdict(flow_data) if flow_data else None,
            "technical": technical,
            "events": [asdict(e) for e in events[:5]] if events else [],
            "missing_sources": missing_sources,
        }
