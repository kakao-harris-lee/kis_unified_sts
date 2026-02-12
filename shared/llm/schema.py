"""Validation helpers for LLM responses."""

from __future__ import annotations

from typing import Any


ALLOWED_RECOMMENDATIONS = {"강력매수", "매수", "관망", "매도", "강력매도"}
ALLOWED_CONFIDENCE = {"높음", "중간", "낮음"}
ALLOWED_TIME_HORIZON = {"단기(1-3일)", "중기(1-2주)"}


def _to_str_list(v: Any, *, max_len: int) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        s = str(x).strip()
        if s:
            out.append(s)
        if len(out) >= max_len:
            break
    return out


def normalize_analysis_result_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy stock-analysis payload into strict shape."""
    score = int(float(data.get("overall_score", 0)))
    score = max(-100, min(100, score))

    recommendation = str(data.get("recommendation", "관망")).strip()
    if recommendation not in ALLOWED_RECOMMENDATIONS:
        recommendation = "관망"

    confidence = str(data.get("confidence", "중간")).strip()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "중간"

    position_size = float(data.get("position_size", 0.1))
    position_size = max(0.0, min(1.0, position_size))

    time_horizon = str(data.get("time_horizon", "단기(1-3일)")).strip()
    if time_horizon not in ALLOWED_TIME_HORIZON:
        time_horizon = "단기(1-3일)"

    return {
        "overall_score": score,
        "recommendation": recommendation,
        "confidence": confidence,
        "key_reasons": _to_str_list(data.get("key_reasons"), max_len=5),
        "risk_factors": _to_str_list(data.get("risk_factors"), max_len=3),
        "entry_strategy": str(data.get("entry_strategy", "")).strip(),
        "exit_strategy": str(data.get("exit_strategy", "")).strip(),
        "position_size": position_size,
        "time_horizon": time_horizon,
    }


def normalize_market_summary_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize market-summary payload into strict shape."""
    summary = str(data.get("summary", "")).strip()
    strategy = str(data.get("strategy", "")).strip()
    key_points = _to_str_list(data.get("key_points"), max_len=5)

    if not summary:
        summary = "분석 실패"
    if not strategy:
        strategy = "전략 없음"

    return {
        "summary": summary,
        "strategy": strategy,
        "key_points": key_points,
    }
