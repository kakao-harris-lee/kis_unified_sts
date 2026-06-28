"""Deterministic paper-only theme leader scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from shared.payloads import clamp01 as _clamp01

ThemeCandidateState = Literal["active", "watch", "quarantine"]

# Default hard-risk flags. Operators may override via ThemeScoringConfig so the
# blocking taxonomy is configuration-driven rather than hardcoded.
HARD_RISK_FLAGS = frozenset(
    {
        "investment_warning",
        "investment_risk",
        "trading_halt",
        "administrative_issue",
        "preferred_share",
    }
)


@dataclass(frozen=True)
class ThemeScoringWeights:
    """Relative weights for each theme leader scoring component."""

    relative_strength: float = 0.25
    trading_value: float = 0.20
    volume_surge: float = 0.15
    catalyst: float = 0.15
    theme_breadth: float = 0.10
    intraday_persistence: float = 0.10
    freshness: float = 0.05


@dataclass(frozen=True)
class ThemeScoringConfig:
    """Configuration knobs for :func:`classify_theme_candidate`.

    Defaults preserve the historical behavior; callers (e.g. the theme
    discovery service) build this from YAML so weights/thresholds/risk values
    are configuration-driven per the repo's non-negotiable rules.
    """

    weights: ThemeScoringWeights = field(default_factory=ThemeScoringWeights)
    active_threshold: float = 0.70
    soft_penalty_per_flag: float = 0.08
    soft_penalty_cap: float = 0.35
    hard_risk_flags: frozenset[str] = HARD_RISK_FLAGS


_DEFAULT_SCORING_CONFIG = ThemeScoringConfig()


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


def classify_theme_candidate(
    score_input: ThemeScoreInput,
    config: ThemeScoringConfig | None = None,
) -> ThemeScoreResult:
    cfg = config or _DEFAULT_SCORING_CONFIG
    weights = cfg.weights
    risk_flags = {str(flag) for flag in (score_input.risk_flags or [])}
    hard_blocked = bool(risk_flags & set(cfg.hard_risk_flags))
    soft_penalty = min(
        max(0.0, cfg.soft_penalty_cap),
        max(0.0, cfg.soft_penalty_per_flag) * len(risk_flags),
    )
    risk_penalty = 1.0 if hard_blocked else soft_penalty
    raw = (
        weights.relative_strength * _clamp01(score_input.relative_strength)
        + weights.trading_value * _clamp01(score_input.trading_value_score)
        + weights.volume_surge * _clamp01(score_input.volume_surge_score)
        + weights.catalyst * _clamp01(score_input.catalyst_score)
        + weights.theme_breadth * _clamp01(score_input.theme_breadth_score)
        + weights.intraday_persistence * _clamp01(score_input.intraday_persistence)
        + weights.freshness * _clamp01(score_input.freshness_score)
    )
    leader_score = round(max(0.0, min(1.0, raw - risk_penalty)), 6)
    has_required_evidence = (
        score_input.market_signal_count > 0 and score_input.catalyst_signal_count > 0
    )
    if hard_blocked:
        state: ThemeCandidateState = "quarantine"
    elif leader_score >= cfg.active_threshold and has_required_evidence:
        state = "active"
    else:
        state = "watch"
    return ThemeScoreResult(
        leader_score=leader_score,
        state=state,
        hard_blocked=hard_blocked,
        risk_penalty=round(risk_penalty, 6),
    )
