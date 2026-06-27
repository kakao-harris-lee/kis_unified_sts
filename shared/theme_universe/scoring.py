"""Deterministic paper-only theme leader scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ThemeCandidateState = Literal["active", "watch", "quarantine"]

HARD_RISK_FLAGS = {
    "investment_warning",
    "investment_risk",
    "trading_halt",
    "administrative_issue",
    "preferred_share",
}


@dataclass(frozen=True)
class ThemeScoreInput:
    relative_strength: float = 0.0
    trading_value_score: float = 0.0
    volume_surge_score: float = 0.0
    catalyst_score: float = 0.0
    theme_breadth_score: float = 0.0
    intraday_persistence: float = 0.0
    freshness_score: float = 0.0
    market_signal_count: int = 0
    catalyst_signal_count: int = 0
    risk_flags: list[str] | None = None


@dataclass(frozen=True)
class ThemeScoreResult:
    leader_score: float
    state: ThemeCandidateState
    hard_blocked: bool
    risk_penalty: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def classify_theme_candidate(score_input: ThemeScoreInput) -> ThemeScoreResult:
    risk_flags = {str(flag) for flag in (score_input.risk_flags or [])}
    hard_blocked = bool(risk_flags & HARD_RISK_FLAGS)
    soft_penalty = min(0.35, 0.08 * len(risk_flags))
    risk_penalty = 1.0 if hard_blocked else soft_penalty
    raw = (
        0.25 * _clamp01(score_input.relative_strength)
        + 0.20 * _clamp01(score_input.trading_value_score)
        + 0.15 * _clamp01(score_input.volume_surge_score)
        + 0.15 * _clamp01(score_input.catalyst_score)
        + 0.10 * _clamp01(score_input.theme_breadth_score)
        + 0.10 * _clamp01(score_input.intraday_persistence)
        + 0.05 * _clamp01(score_input.freshness_score)
    )
    leader_score = round(max(0.0, min(1.0, raw - risk_penalty)), 6)
    has_required_evidence = (
        score_input.market_signal_count > 0 and score_input.catalyst_signal_count > 0
    )
    if hard_blocked:
        state: ThemeCandidateState = "quarantine"
    elif leader_score >= 0.70 and has_required_evidence:
        state = "active"
    else:
        state = "watch"
    return ThemeScoreResult(
        leader_score=leader_score,
        state=state,
        hard_blocked=hard_blocked,
        risk_penalty=round(risk_penalty, 6),
    )
