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

import hashlib
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.risk.log_throttle import gate_log_throttle_key
from shared.risk.market_risk_gate import MarketRiskGateDecision, gate_trace_payload

# Scope of O14-①: enforce-mode REJECTS only (shadow would-block stays
# log-only, per the daemon's shadow-observation path). ADMIT rows, if ever
# added, are a separate explicit change — not a silent extension of this set.
# Typed as the Literal itself (not `str`) so it type-checks as the default for
# ``GateDecisionRecord.outcome: Literal["reject"]`` below.
OUTCOME_REJECT: Literal["reject"] = "reject"

KST = ZoneInfo("Asia/Seoul")


def deterministic_reject_signal_id(
    *,
    asset_class: Literal["stock", "futures"],
    symbol: str,
    strategy: str,
    direction: str,
    generated_at: datetime,
    decision: MarketRiskGateDecision,
) -> str:
    """Derive a reproducible ``signal_id`` for one rejected-candidate emission.

    A rejected candidate never reaches the publish step (rejected upstream
    of signal_id assignment), so unlike an admitted signal there is no
    natural id to key its ``signal_decisions`` row on. This derives one
    instead from the emission's identity: asset class, symbol, strategy
    (setup type), the candidate's own generation timestamp
    (``generated_at``), the gate ``mode``, and the gate verdict's
    STRUCTURAL identity — band + side, via :func:`gate_log_throttle_key`
    (``shared/risk/log_throttle.py``) — rather than the gate's raw
    free-text ``reason``. ``reason`` embeds ``score`` (e.g. ``"market_risk
    band=HIGH score=74.2 rule=block_new_long"``) and changes on every
    gate-hash refresh; including it verbatim would mint a different id for
    the identical band/side verdict depending on exactly when the score
    last ticked. This is the same trap ``_maybe_log_shadow_gate``
    (``services/decision_engine/main.py``, O14-③) already avoids by keying
    its own throttle on ``gate_log_throttle_key`` instead of ``reason``.
    ``direction`` feeds ``gate_log_throttle_key``'s ``side`` parameter, so it
    is not a separate component of the hashed key.

    Consequence — what this id IS: stable for one emission across a
    same-band score refresh (e.g. a gate-hash cron tick landing between
    candidate construction and the ledger write), and reproducible for a
    byte-identical retry/replay of that exact emission, which then upserts
    the existing row instead of duplicating it (see repeat-write behavior
    below).

    What this id is NOT: cross-tick dedupe. ``generated_at`` advances on
    every decision-loop tick (``context_provider`` supplies a fresh ``now``
    each tick, and both Setup A and Setup C stamp
    ``generated_at=ctx.now``), so the SAME candidate rejected again on the
    NEXT tick gets a DIFFERENT id and a NEW row — row count per tick is
    unchanged from the previous ``uuid4()`` scheme this replaces.

    Both call sites (stock and futures reject lanes) should reuse this
    function so the two asset classes derive ids the same way.

    Repeat-write behavior: ``RuntimeLedger.record_signal_decision``
    (``shared/storage/runtime_ledger_records.py``) derives its row's primary
    key AND its upsert key from this ``signal_id`` whenever no separate
    ``id``/``decision_id`` is supplied in the payload
    (``shared/storage/runtime_ledger_helpers.py:_record_id`` falls back to
    the ``signal_id`` field, and ``idempotency_key`` falls back to that same
    derived id) — the insert is an
    ``ON CONFLICT(idempotency_key) DO UPDATE`` upsert. So a repeat write
    with the same derived id safely updates the existing row in place; it
    never raises a uniqueness violation and never creates a duplicate row.
    """
    key = "\x1f".join(
        (
            asset_class,
            symbol,
            strategy,
            generated_at.isoformat(),
            decision.mode,
            gate_log_throttle_key(
                band=decision.band, reason=decision.reason, side=direction
            ),
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


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
