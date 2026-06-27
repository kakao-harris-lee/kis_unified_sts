from __future__ import annotations

from dataclasses import dataclass, field

import yaml


@dataclass
class ScorecardConfig:
    enabled_facets: list[str] = field(default_factory=lambda: ["direction"])
    rolling_windows: list[int] = field(default_factory=lambda: [20, 60])
    facet_params: dict = field(default_factory=dict)
    report_daily: bool = True
    report_weekly: bool = True
    telegram_domain: str = "briefing"

    @classmethod
    def from_yaml(cls, path: str | None = None) -> ScorecardConfig:
        data: dict = {}
        try:
            with open(path or "config/llm_scorecard.yaml") as f:
                data = (yaml.safe_load(f) or {}).get("llm_scorecard", {}) or {}
        except (FileNotFoundError, OSError):
            data = {}
        return cls(
            enabled_facets=data.get("enabled_facets", ["direction"]),
            rolling_windows=data.get("rolling_windows", [20, 60]),
            facet_params=data.get("facet_params", {}),
            report_daily=bool(data.get("report_daily", True)),
            report_weekly=bool(data.get("report_weekly", True)),
            telegram_domain=data.get("telegram_domain", "briefing"),
        )
