"""Shared DTO for a market-risk-gate reject record (stock + futures parity).

O14-① (operator decision 2026-09-06): a market-risk-gate REJECT in enforce
mode must land in ``RuntimeLedger.signal_decisions``, not only in the
``entry_rejected`` audit-log line. Stock and futures both reject through the
same shared evaluator (``shared.risk.market_risk_gate``); this module gives
both call sites one validated shape so the row ``services/dashboard``'s trace
route reads back (``_load_signal_decision_payload`` /
``_market_risk_gate_from_payload``, ``services/dashboard/routes/signals.py``)
is identical regardless of asset class.

Defensive-DTO directive: raw dicts never cross this boundary — construction
via :meth:`GateDecisionRecord.from_gate_decision` is the only entry point, and
``outcome`` is a closed literal so a typo'd value fails at construction
instead of landing silently in the ledger.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.risk.market_risk_gate import MarketRiskGateDecision, gate_trace_payload

# Scope of O14-①: enforce-mode REJECTS only (shadow would-block stays
# log-only, per the daemon's shadow-observation path). ADMIT rows, if ever
# added, are a separate explicit change — not a silent extension of this set.
# Typed as the Literal itself (not `str`) so it type-checks as the default for
# ``GateDecisionRecord.outcome: Literal["reject"]`` below.
OUTCOME_REJECT: Literal["reject"] = "reject"

KST = ZoneInfo("Asia/Seoul")


class GateDecisionRecord(BaseModel):
    """One market-risk-gate verdict to persist into ``signal_decisions``.

    Field shape mirrors what ``RuntimeLedger.record_signal_decision``
    (``shared/storage/runtime_ledger_records.py``) and the dashboard trace
    route both expect: ``signal_id``/``asset_class``/``symbol``/``strategy``
    are indexed columns; ``market_risk_gate`` is the fixed
    ``gate_trace_payload`` contract nested under that exact key inside
    ``payload_json`` (the dashboard fallback reads
    ``signal_decision_payload.get("market_risk_gate")``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str = Field(min_length=1)
    asset_class: Literal["stock", "futures"]
    symbol: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    outcome: Literal["reject"] = OUTCOME_REJECT
    reason: str = Field(min_length=1)
    created_at: datetime
    market_risk_gate: dict[str, Any]

    @field_validator("created_at")
    @classmethod
    def _require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @classmethod
    def from_gate_decision(
        cls,
        *,
        signal_id: str,
        asset_class: Literal["stock", "futures"],
        symbol: str,
        strategy: str,
        decision: MarketRiskGateDecision,
        created_at: datetime,
    ) -> GateDecisionRecord:
        """Build the record from a fired :class:`MarketRiskGateDecision`.

        ``created_at`` should be the candidate's own generation timestamp
        (e.g. ``Signal.generated_at`` / the stock cycle's ``now``) so the row
        reflects when the gate actually fired, not when the ledger write
        happens.
        """
        return cls(
            signal_id=signal_id,
            asset_class=asset_class,
            symbol=symbol,
            strategy=strategy,
            reason=decision.reason,
            created_at=created_at,
            market_risk_gate=gate_trace_payload(decision),
        )

    def to_ledger_payload(self) -> dict[str, Any]:
        """Shape this record for ``RuntimeLedger.record_signal_decision``.

        Column mapping (``shared/storage/runtime_ledger_records.py``):
        ``signal_id`` / ``asset_class`` / ``symbol`` / ``strategy`` map
        directly; ``outcome`` -> the ``decision`` column
        (``_coalesce(data, "decision", "status")``); ``created_at`` is
        normalized to KST ISO-8601 (CLAUDE.md: KST-native timestamps).
        Everything else, including the nested ``market_risk_gate`` trace,
        rides in ``payload_json``.
        """
        return {
            "signal_id": self.signal_id,
            "asset_class": self.asset_class,
            "symbol": self.symbol,
            "strategy": self.strategy,
            "decision": self.outcome,
            "reason": self.reason,
            "created_at": self.created_at.astimezone(KST).isoformat(),
            "market_risk_gate": self.market_risk_gate,
        }
