"""Forecasting dataclasses — VolForecast, EventScore."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Literal

# Default impact-score → tier band edges (0-100 score). Overridable per-call so
# the scorer can drive them from EventScorerConfig. Tier 1 = top impact,
# Tier 3 = minor — mirrors ScheduledEvent.impact_tier so LLM/rule events render
# on the same tier axis as the scheduled-event calendar.
_DEFAULT_TIER1_MIN_SCORE = 75.0
_DEFAULT_TIER2_MIN_SCORE = 50.0


def tier_for_impact_score(
    impact_score: float,
    tier1_min: float = _DEFAULT_TIER1_MIN_SCORE,
    tier2_min: float = _DEFAULT_TIER2_MIN_SCORE,
) -> int:
    """Map a 0-100 impact score to a discrete impact tier (1=top, 3=minor).

    ``>=tier1_min`` → 1, ``>=tier2_min`` → 2, else 3. Always returns 1, 2, or 3
    — never 0, which EventScore reserves as its "derive me" sentinel. Pure; no
    clamping (callers pass bounded scores). Mirrors ScheduledEvent.impact_tier
    so the dashboard can aggregate rule/LLM events on the same tier axis as
    scheduled events.
    """
    if impact_score >= tier1_min:
        return 1
    if impact_score >= tier2_min:
        return 2
    return 3


@dataclass
class VolForecast:
    """Single 15-min volatility forecast snapshot.

    forecast_pct      annualized %, e.g. 18.5
    forecast_atr_equivalent
                     ATR-unit equivalent so Setup A/C can swap it for ATR.
    regime_percentile
                     0-100, where current forecast sits in 30d distribution.
    confidence       0-1, from latest fit's OOS R².
    """

    asof: datetime
    horizon_minutes: int
    forecast_pct: float
    forecast_atr_equivalent: float
    regime_percentile: float
    model_version: str
    confidence: float

    def is_fresh(self, now: datetime, max_age_s: int = 120) -> bool:
        return (now - self.asof).total_seconds() <= max_age_s

    def to_json(self) -> str:
        d = asdict(self)
        d["asof"] = self.asof.isoformat()
        return json.dumps(d)

    @classmethod
    def from_json(cls, blob: str | bytes) -> VolForecast:
        if isinstance(blob, bytes):
            blob = blob.decode()
        d = json.loads(blob)
        d["asof"] = datetime.fromisoformat(d["asof"])
        return cls(**d)


@dataclass
class EventScore:
    """Macro/news event impact magnitude (0-100, direction-agnostic)."""

    asof: datetime
    impact_score: float          # 0-100
    event_type: str              # taxonomy key or "UNKNOWN_LLM_SCORED"
    source: Literal["rule", "llm"]
    raw_text: str | None         # only retained for LLM-sourced events
    ttl_minutes: int
    # Discrete impact tier (1=top, 3=minor). 0 is a sentinel meaning "derive
    # from impact_score with default bands" — used for direct construction and
    # for backward-compat when loading pre-tier JSON. The scorer passes an
    # explicit config-driven tier, so production payloads carry 1/2/3.
    impact_tier: int = 0

    def __post_init__(self) -> None:
        if not self.impact_tier:
            self.impact_tier = tier_for_impact_score(self.impact_score)

    def is_expired(self, now: datetime) -> bool:
        return now > self.asof + timedelta(minutes=self.ttl_minutes)

    def to_json(self) -> str:
        d = asdict(self)
        d["asof"] = self.asof.isoformat()
        return json.dumps(d)

    @classmethod
    def from_json(cls, blob: str | bytes) -> EventScore:
        if isinstance(blob, bytes):
            blob = blob.decode()
        d = json.loads(blob)
        d["asof"] = datetime.fromisoformat(d["asof"])
        # Pre-tier payloads omit impact_tier → __post_init__ derives it.
        return cls(**d)
