"""Reporting, Telegram alerts, and training-data persistence.

Functions extracted from UnifiedTradingAnalyzer that handle output:
report saving, Telegram notifications, LLM quality snapshots,
and training-row serialization.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from .data_classes import FuturesTradingPlan, StockTradingPlan

if TYPE_CHECKING:
    from .llm_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Telegram alerts
# ------------------------------------------------------------------


async def send_telegram_alerts(
    analyzer: UnifiedTradingAnalyzer,
    stock_plans: list[StockTradingPlan],
    futures_plan: FuturesTradingPlan | None,
    futures_analysis: dict,
    stock_analysis: dict[str, Any] | None = None,
) -> None:
    """Send Telegram alerts for analysis results."""
    if not analyzer.notifier:
        return

    try:
        header = f"""
🚀 <b>통합 트레이딩 브리핑</b>
━━━━━━━━━━━━━━━━━━━━
📅 {analyzer.datetime_str}
"""
        await analyzer.notifier.send_message(header, is_critical=True)

        missing_sources = (
            futures_analysis.get("missing_sources") if futures_analysis else None
        )
        if missing_sources:
            missing_text = "\n".join(f"  • {m}" for m in missing_sources)
            await analyzer.notifier.send_message(
                f"⚠️ <b>선물 데이터 누락</b>\n{missing_text}",
                is_critical=True,
            )

        if futures_plan:
            await analyzer.notifier.send_message(
                futures_plan.to_telegram_message(), is_critical=True
            )

        if stock_plans:
            stocks_header = f"""
📈 <b>주식 추천 ({len(stock_plans)}개)</b>
━━━━━━━━━━━━━━━━━━━━
"""
            await analyzer.notifier.send_message(stocks_header)

            for plan in stock_plans[:3]:
                await analyzer.notifier.send_message(plan.to_telegram_message())
        else:
            await analyzer.notifier.send_message(_stock_empty_message(stock_analysis))

        checklist = """
📋 <b>체크리스트</b>
━━━━━━━━━━━━━━━━━━━━
☐ 08:30 - 장전 점검
☐ 09:00 - 장 시작
☐ 15:30 - 결과 기록
━━━━━━━━━━━━━━━━━━━━

"""
        await analyzer.notifier.send_message(checklist)

        logger.info("Telegram alerts sent successfully")
    except Exception as e:
        logger.error(f"Failed to send Telegram alerts: {e}")


def _stock_empty_message(stock_analysis: dict[str, Any] | None) -> str:
    status = (
        stock_analysis.get("_analysis_status")
        if isinstance(stock_analysis, dict)
        else None
    )
    if not isinstance(status, dict):
        return (
            "⚠️ <b>주식 추천 없음</b>\n시장 데이터 수집 실패 또는 조건 충족 종목 없음"
        )

    reason = str(status.get("reason") or "unknown")
    detail = status.get("detail")
    if reason == "market_data_unavailable":
        return (
            "🚨 <b>주식 장전 분석 실패</b>\n"
            "KRX 시장 데이터 수집 결과가 비어 있어 추천 생성을 중단했습니다."
        )
    if reason == "market_data_missing_columns":
        return (
            "🚨 <b>주식 장전 분석 실패</b>\n"
            f"KRX 시장 데이터 필수 컬럼 누락: {detail or 'unknown'}"
        )

    reason_labels = {
        "no_stocks_after_screening": "기초 스크리닝 통과 종목 없음",
        "no_candidates_after_analysis": "개별 분석 통과 후보 없음",
        "no_candidates_after_final_filters": "최종 점수 필터 통과 후보 없음",
    }
    return "⚠️ <b>주식 추천 없음</b>\n" f"{reason_labels.get(reason, reason)}"


# ------------------------------------------------------------------
# Report persistence
# ------------------------------------------------------------------


def save_reports(
    analyzer: UnifiedTradingAnalyzer,
    stock_plans: list[StockTradingPlan],
    futures_plan: FuturesTradingPlan | None,
    analysis_data: dict,
    snapshot_id: str,
) -> None:
    """Save JSON reports to disk."""
    json_data = {
        "date": analyzer.date,
        "generated_at": analyzer.datetime_str,
        "stock_plans": [asdict(p) for p in stock_plans],
        "futures_plan": asdict(futures_plan) if futures_plan else None,
        "analysis": analysis_data,
    }

    json_path = os.path.join(
        analyzer.config.output_dir,
        f"unified_data_{analyzer.date}_{snapshot_id[-6:]}.json",
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)

    latest_path = os.path.join(analyzer.config.output_dir, "unified_data_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Report saved: {json_path}")


# ------------------------------------------------------------------
# LLM quality snapshot
# ------------------------------------------------------------------


def build_llm_quality_snapshot(
    analyzer: UnifiedTradingAnalyzer,
    snapshot_id: str,
    stock_plans: list[StockTradingPlan],
    stock_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Build a quality snapshot dict from screening results."""
    screening_scores, risk_flags = _collect_screening_scores(stock_analysis)
    quality = _build_quality_scores(screening_scores)
    excluded_map = _build_excluded_map(stock_analysis)
    names = _build_plan_names(stock_plans)
    metadata = _build_plan_metadata(stock_plans)
    final_codes = [p.code for p in stock_plans]

    return {
        "snapshot_id": snapshot_id,
        "generated_at": analyzer.datetime_str,
        "codes": sorted(quality.keys()),
        "final_codes": final_codes,
        "quality": quality,
        "raw_scores": {c: round(s, 4) for c, s in screening_scores.items()},
        "risk_flags": risk_flags,
        "excluded": excluded_map,
        "names": names,
        "metadata": metadata,
    }


def _collect_screening_scores(
    stock_analysis: dict[str, Any],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    screening_scores: dict[str, float] = {}
    risk_flags: dict[str, list[str]] = {}

    for code, data in stock_analysis.items():
        if not isinstance(data, dict):
            continue
        if code.startswith("_"):
            continue

        score = data.get("screening", {}).get("score")
        if isinstance(score, (int, float)):
            screening_scores[code] = float(score)

        metrics = data.get("screening", {}).get("metrics", {})
        hits = metrics.get("risk_keywords", [])
        if isinstance(hits, list) and hits:
            risk_flags[code] = [str(h) for h in hits]

    return screening_scores, risk_flags


def _build_quality_scores(screening_scores: dict[str, float]) -> dict[str, float]:
    if not screening_scores:
        return {}
    if len(screening_scores) == 1:
        code = next(iter(screening_scores))
        return {code: 1.0}

    min_score = min(screening_scores.values())
    max_score = max(screening_scores.values())
    span = max(max_score - min_score, 1e-9)
    return {c: round((s - min_score) / span, 6) for c, s in screening_scores.items()}


def _build_excluded_map(stock_analysis: dict[str, Any]) -> dict[str, list[str]]:
    excluded = stock_analysis.get("_excluded", {})
    excluded_map: dict[str, list[str]] = {}
    if isinstance(excluded, dict):
        for code, reasons in excluded.items():
            if isinstance(reasons, list):
                excluded_map[str(code)] = [str(r) for r in reasons]
    return excluded_map


def _build_plan_names(stock_plans: list[StockTradingPlan]) -> dict[str, str]:
    return {p.code: p.name for p in stock_plans}


def _build_plan_metadata(
    stock_plans: list[StockTradingPlan],
) -> dict[str, dict[str, Any]]:
    return {
        p.code: {
            "llm_plan_strategy": p.strategy,
            "entry_price": p.entry_price,
            "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "position_size": p.position_size,
            "plan_confidence": p.confidence,
            "news_sentiment": p.news_sentiment,
        }
        for p in stock_plans
    }


def publish_llm_quality_snapshot(
    analyzer: UnifiedTradingAnalyzer,
    snapshot_id: str,
    stock_plans: list[StockTradingPlan],
    stock_analysis: dict[str, Any],
) -> None:
    """Publish quality snapshot to Redis (best-effort)."""
    if not should_publish_llm_quality_snapshot(stock_analysis):
        logger.info("Skipped LLM quality snapshot publish: stock analysis failed")
        return

    try:
        from shared.streaming.client import RedisClient

        key = os.environ.get("LLM_QUALITY_LATEST_KEY", "system:llm_quality:latest")
        payload = build_llm_quality_snapshot(
            analyzer, snapshot_id, stock_plans, stock_analysis
        )
        redis = RedisClient.get_client()
        redis.set(key, json.dumps(payload, ensure_ascii=False), ex=86400)
        logger.info(
            f"Published LLM quality snapshot: {len(payload.get('codes', []))} symbols"
        )
    except Exception as e:
        logger.warning(f"Failed to publish LLM quality snapshot: {e}")


def should_publish_llm_quality_snapshot(
    stock_analysis: dict[str, Any] | None,
) -> bool:
    if not stock_analysis:
        return False

    status = stock_analysis.get("_analysis_status")
    return not (isinstance(status, dict) and status.get("status") == "failed")


# ------------------------------------------------------------------
# Training rows
# ------------------------------------------------------------------


def save_training_rows(
    analyzer: UnifiedTradingAnalyzer,
    snapshot_id: str,
    stock_plans: list[StockTradingPlan],
    stock_analysis: dict[str, Any],
) -> None:
    """Append JSONL training rows for future model training."""
    try:
        rows = _build_training_rows(
            analyzer,
            snapshot_id,
            stock_plans,
            stock_analysis,
        )
        if not rows:
            return

        training_path = os.path.join(analyzer.config.output_dir, "training_rows.jsonl")
        _write_training_rows(training_path, rows)
        logger.info(f"Training rows appended: {len(rows)} -> {training_path}")
    except Exception as e:
        logger.warning(f"Failed to save training rows: {e}")


def _build_training_rows(
    analyzer: UnifiedTradingAnalyzer,
    snapshot_id: str,
    stock_plans: list[StockTradingPlan],
    stock_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    final_codes = {p.code for p in stock_plans}
    plan_map = {p.code: p for p in stock_plans}
    rows: list[dict[str, Any]] = []

    rows.extend(
        _build_training_rows_for_analysis(
            analyzer,
            snapshot_id,
            stock_analysis,
            plan_map,
            final_codes,
        )
    )
    rows.extend(
        _build_training_rows_for_excluded(analyzer, snapshot_id, stock_analysis)
    )

    return rows


def _build_training_rows_for_analysis(
    analyzer: UnifiedTradingAnalyzer,
    snapshot_id: str,
    stock_analysis: dict[str, Any],
    plan_map: dict[str, StockTradingPlan],
    final_codes: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, data in stock_analysis.items():
        if not isinstance(data, dict):
            continue
        if str(code).startswith("_"):
            continue

        screening = data.get("screening", {})
        metrics = screening.get("metrics", {}) if isinstance(screening, dict) else {}
        score_breakdown = (
            screening.get("score_breakdown", {}) if isinstance(screening, dict) else {}
        )
        technical = data.get("technical", {})
        news = data.get("news", {})
        news_headlines = news.get("mk_headlines", news.get("key_events", []))
        if not isinstance(news_headlines, list):
            news_headlines = []
        plan = plan_map.get(code)

        rows.append(
            {
                "snapshot_id": snapshot_id,
                "date": analyzer.date,
                "generated_at": analyzer.datetime_str,
                "code": code,
                "name": plan.name if plan else "",
                "selected": code in final_codes,
                "decision": {
                    "strategy": getattr(plan, "strategy", ""),
                    "position_size": getattr(plan, "position_size", 0.0),
                    "confidence": getattr(plan, "confidence", ""),
                    "entry_price": getattr(plan, "entry_price", 0.0),
                    "stop_loss": getattr(plan, "stop_loss", 0.0),
                    "take_profit": getattr(plan, "take_profit", 0.0),
                },
                "features": {
                    "screening_metrics": metrics,
                    "screening_score": screening.get("score"),
                    "score_breakdown": score_breakdown,
                    "technical_signal": technical.get("signal"),
                    "news_sentiment": news.get("sentiment"),
                    "news_count": news.get("news_count", 0),
                    "news_headlines": news_headlines[:3],
                    "risk_keywords": metrics.get("risk_keywords", []),
                },
                "labels": _empty_training_labels(),
            }
        )

    return rows


def _build_training_rows_for_excluded(
    analyzer: UnifiedTradingAnalyzer,
    snapshot_id: str,
    stock_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    excluded = stock_analysis.get("_excluded", {})
    excluded_features = stock_analysis.get("_excluded_features", {})
    if not isinstance(excluded, dict):
        return rows

    for code, reasons in excluded.items():
        if not isinstance(reasons, list):
            continue
        ex_feat = (
            excluded_features.get(code, {})
            if isinstance(excluded_features, dict)
            else {}
        )
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "date": analyzer.date,
                "generated_at": analyzer.datetime_str,
                "code": str(code),
                "name": "",
                "selected": False,
                "decision": {"excluded": True},
                "features": {
                    "excluded_reasons": [str(r) for r in reasons],
                    "excluded_features": ex_feat if isinstance(ex_feat, dict) else {},
                },
                "labels": _empty_training_labels(),
            }
        )

    return rows


def _empty_training_labels() -> dict[str, Any]:
    return {
        "horizon_return_1d": None,
        "horizon_return_3d": None,
        "horizon_return_5d": None,
        "trade_pnl": None,
        "trade_pnl_pct": None,
    }


def _write_training_rows(training_path: str, rows: list[dict[str, Any]]) -> None:
    with open(training_path, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
