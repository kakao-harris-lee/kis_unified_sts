"""Forecasting dataclasses — VolForecast, EventScore."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Literal


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
        return cls(**d)
