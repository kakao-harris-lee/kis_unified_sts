"""Validation helpers for LLM responses."""

from __future__ import annotations

from typing import Any

ALLOWED_RECOMMENDATIONS = {"강력매수", "매수", "관망", "매도", "강력매도"}
ALLOWED_CONFIDENCE = {"높음", "중간", "낮음"}
ALLOWED_TIME_HORIZON = {"단기(1-3일)", "중기(1-2주)"}

# Score / position-size bounds
SCORE_MIN = -100
SCORE_MAX = 100
POSITION_SIZE_MIN = 0.0
POSITION_SIZE_MAX = 1.0
DEFAULT_POSITION_SIZE = 0.1

# List truncation limits
MAX_KEY_REASONS = 5
MAX_RISK_FACTORS = 3
MAX_KEY_POINTS = 5


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
    score = max(SCORE_MIN, min(SCORE_MAX, score))

    recommendation = str(data.get("recommendation", "관망")).strip()
    if recommendation not in ALLOWED_RECOMMENDATIONS:
        recommendation = "관망"

    confidence = str(data.get("confidence", "중간")).strip()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "중간"

    position_size = float(data.get("position_size", DEFAULT_POSITION_SIZE))
    position_size = max(POSITION_SIZE_MIN, min(POSITION_SIZE_MAX, position_size))

    time_horizon = str(data.get("time_horizon", "단기(1-3일)")).strip()
    if time_horizon not in ALLOWED_TIME_HORIZON:
        time_horizon = "단기(1-3일)"

    return {
        "overall_score": score,
        "recommendation": recommendation,
        "confidence": confidence,
        "key_reasons": _to_str_list(data.get("key_reasons"), max_len=MAX_KEY_REASONS),
        "risk_factors": _to_str_list(
            data.get("risk_factors"), max_len=MAX_RISK_FACTORS
        ),
        "entry_strategy": str(data.get("entry_strategy", "")).strip(),
        "exit_strategy": str(data.get("exit_strategy", "")).strip(),
        "position_size": position_size,
        "time_horizon": time_horizon,
    }


# LLM Scoring bounds
CONFIDENCE_FACTOR_MIN = 0.5
CONFIDENCE_FACTOR_MAX = 1.5
ALLOWED_CONVICTION = {"high", "medium", "low"}
ALLOWED_OVERRIDE = {"strong_buy", "buy", "hold", "sell"}


def normalize_scoring_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM scoring response into strict shape."""
    cf = max(
        CONFIDENCE_FACTOR_MIN,
        min(CONFIDENCE_FACTOR_MAX, float(data.get("confidence_factor", 1.0))),
    )
    conviction = str(data.get("conviction", "medium")).strip().lower()
    if conviction not in ALLOWED_CONVICTION:
        conviction = "medium"
    key_insight = str(data.get("key_insight", "")).strip()[:200]
    risk_concern = data.get("risk_concern")
    if risk_concern is not None:
        risk_concern = str(risk_concern).strip()[:200] or None
    override = data.get("override_recommendation")
    if override is not None:
        override = str(override).strip().lower()
        if override not in ALLOWED_OVERRIDE:
            override = None
    return {
        "confidence_factor": cf,
        "conviction": conviction,
        "key_insight": key_insight,
        "risk_concern": risk_concern,
        "override_recommendation": override,
    }


def normalize_market_summary_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize market-summary payload into strict shape."""
    summary = str(data.get("summary", "")).strip()
    strategy = str(data.get("strategy", "")).strip()
    key_points = _to_str_list(data.get("key_points"), max_len=MAX_KEY_POINTS)

    if not summary:
        summary = "분석 실패"
    if not strategy:
        strategy = "전략 없음"

    return {
        "summary": summary,
        "strategy": strategy,
        "key_points": key_points,
    }
