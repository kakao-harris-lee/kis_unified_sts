"""Signals route response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    """Signal response model."""

    id: str
    asset_class: str
    symbol: str
    name: str = ""
    side: str
    signal_type: str
    strategy: str
    price: float
    confidence: float
    strength: float
    timestamp: datetime
    executed: bool
    setup_type: str | None = None
    status: str | None = None
    reason: str | None = None
    reject_stage: str | None = None
    reject_reason: str | None = None
    orderability_state: str | None = None
    orderability_details: dict[str, Any] | None = None
    order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    trade_id: str | None = None
    # Market Risk Gate verdict attached by the Phase 2 entry lanes
    # (gate_trace_payload schema, shared/risk/market_risk_gate.py). Signals
    # generated before the gate wiring simply omit it (None).
    market_risk_gate: dict[str, Any] | None = None


class SignalListResponse(BaseModel):
    """Signal list response."""

    signals: list[SignalResponse]
    total: int
    page: int
    limit: int


class SignalHistoryResponse(BaseModel):
    """Signal history response."""

    history: list[dict]
    total_signals: int
    days: int


class EvidenceGap(BaseModel):
    """One missing or degraded evidence source for the decision trace."""

    code: str
    severity: str
    message: str


class DecisionTraceSignal(BaseModel):
    """Signal identity and basic decision fields."""

    id: str
    asset_class: str
    symbol: str
    name: str = ""
    strategy: str
    side: str
    signal_type: str | None = None
    status: str | None = None
    reason: str | None = None
    confidence: float | None = None
    strength: float | None = None
    price: float | None = None
    timestamp: datetime | None = None


class DecisionTraceSummary(BaseModel):
    """Deterministic operator summary."""

    state: str
    text: str
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceLlmContext(BaseModel):
    """Market context associated with the signal decision."""

    status: str
    overall_signal: str | None = None
    confidence: float | None = None
    risk_mode: str | None = None
    regime: str | None = None
    risk_score: float | None = None
    captured_at: datetime | None = None
    source: str | None = None


class DecisionTraceStrategyInputs(BaseModel):
    """Strategy-native inputs available for the signal."""

    setup_type: str | None = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    event_evidence: dict[str, Any] = Field(default_factory=dict)
    raw_reason: str | None = None


class DecisionTraceRiskOrderability(BaseModel):
    """Risk and orderability status for the signal."""

    reject_stage: str | None = None
    reject_reason: str | None = None
    orderability_state: str | None = None
    orderability_details: dict[str, Any] = Field(default_factory=dict)
    risk_state: str | None = None
    risk_details: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceLineage(BaseModel):
    """Known downstream runtime identifiers."""

    signal_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    trade_id: str | None = None


class DecisionTraceLifecycle(BaseModel):
    """Compact lifecycle block embedded in the signal trace."""

    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DecisionTraceMarketRiskGate(BaseModel):
    """Market Risk Gate verdict linked to the signal (roadmap Phase 2E).

    Mirrors the ``gate_trace_payload`` key contract from
    ``shared/risk/market_risk_gate.py``. Every field is optional so partially
    populated payloads from the entry lanes still render; the whole block is
    ``None`` when the signal carries no ``market_risk_gate`` metadata (signals
    generated before the gate wiring, monolithic futures path, ...).
    """

    mode: str | None = None
    band: str | None = None
    score: float | None = None
    regime: str | None = None
    would_block: bool | None = None
    allow: bool | None = None
    size_factor: float | None = None
    min_confidence: str | None = None
    reason: str | None = None
    degraded: bool | None = None
    stale: bool | None = None


class DecisionTraceScorecard(BaseModel):
    """LLM prediction scorecard evidence linked to the signal."""

    status: str
    facet: str | None = None
    date_kst: str | None = None
    captured_at: datetime | None = None
    confidence: float | None = None
    correct: bool | None = None
    value: float | None = None
    economic_proxy: float | None = None
    baseline_value: float | None = None
    edge: float | None = None
    scored_at: datetime | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceResponse(BaseModel):
    """Read-only signal decision trace for the dashboard."""

    signal: DecisionTraceSignal
    summary: DecisionTraceSummary
    llm_context: DecisionTraceLlmContext
    strategy_inputs: DecisionTraceStrategyInputs
    risk_orderability: DecisionTraceRiskOrderability
    # None when the signal has no market_risk_gate metadata — the UI hides
    # the section instead of rendering an empty block.
    market_risk_gate: DecisionTraceMarketRiskGate | None = None
    lineage: DecisionTraceLineage
    lifecycle: DecisionTraceLifecycle
    scorecard: DecisionTraceScorecard
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
