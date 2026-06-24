from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class FacetPrediction:
    facet: str
    date_kst: str
    captured_at: datetime
    payload: dict
    confidence: float | None = None


@dataclass
class FacetScore:
    facet: str
    date_kst: str
    correct: bool | None
    value: float
    economic_proxy: float
    baseline_value: float
    edge: float
    detail: dict = field(default_factory=dict)
    scored_at: datetime | None = None


@dataclass
class CaptureContext:
    date_kst: str
    now_kst: datetime
    market_context: dict | None = None
    screener: dict | None = None
    redis: Any = None


@runtime_checkable
class PredictionFacet(Protocol):
    name: str
    outcome_horizon: str
    outcome_source: str

    def capture(self, ctx: CaptureContext) -> FacetPrediction | None: ...
    def score(self, pred: FacetPrediction, mkt: Any) -> FacetScore: ...
    def baseline(self, pred: FacetPrediction, mkt: Any) -> float: ...


FACET_REGISTRY: dict[str, Any] = {}


def register_facet(facet: Any) -> None:
    FACET_REGISTRY[facet.name] = facet


def enabled_facets(cfg: Any) -> list[Any]:
    return [FACET_REGISTRY[n] for n in cfg.enabled_facets if n in FACET_REGISTRY]
