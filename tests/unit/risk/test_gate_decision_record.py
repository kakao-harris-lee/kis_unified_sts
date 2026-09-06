"""Tests for shared.risk.gate_decision_record.GateDecisionRecord.

O14-① (operator decision 2026-09-06): one shared, validated shape for a
market-risk-gate REJECT row so stock and futures both write the same thing
into ``RuntimeLedger.signal_decisions``. Defensive-DTO directive: construction
must reject bad values rather than silently accepting them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from shared.risk.gate_decision_record import (
    GateDecisionRecord,
    deterministic_reject_signal_id,
)
from shared.risk.market_risk_gate import MarketRiskGateDecision

_KST = timezone(timedelta(hours=9))


def _decision(**overrides) -> MarketRiskGateDecision:
    base = {
        "allow": False,
        "would_block": True,
        "size_factor": 1.0,
        "min_confidence": None,
        "reason": "market_risk band=HIGH score=74.2 rule=block_new_long",
        "band": "HIGH",
        "score": 74.2,
        "regime": "risk_off",
        "degraded": False,
        "stale": False,
        "mode": "enforce",
    }
    base.update(overrides)
    return MarketRiskGateDecision(**base)


def test_from_gate_decision_builds_the_expected_record():
    created_at = datetime(2026, 9, 6, 9, 30, tzinfo=_KST)
    record = GateDecisionRecord.from_gate_decision(
        signal_id="sig-1",
        asset_class="futures",
        symbol="A05603",
        strategy="A_gap_reversion",
        decision=_decision(),
        created_at=created_at,
    )
    assert record.outcome == "reject"
    assert record.reason == "market_risk band=HIGH score=74.2 rule=block_new_long"
    assert record.market_risk_gate["band"] == "HIGH"
    assert record.market_risk_gate["mode"] == "enforce"
    assert record.market_risk_gate["allow"] is False


def test_to_ledger_payload_maps_outcome_to_decision_column_and_kst_timestamp():
    # UTC input must normalize to KST on the wire (CLAUDE.md: KST-native).
    created_at = datetime(2026, 9, 6, 0, 30, tzinfo=UTC)
    record = GateDecisionRecord.from_gate_decision(
        signal_id="sig-2",
        asset_class="futures",
        symbol="A05603",
        strategy="A_gap_reversion",
        decision=_decision(),
        created_at=created_at,
    )
    payload = record.to_ledger_payload()
    assert payload["signal_id"] == "sig-2"
    assert payload["asset_class"] == "futures"
    assert payload["symbol"] == "A05603"
    assert payload["strategy"] == "A_gap_reversion"
    assert payload["decision"] == "reject"
    assert payload["market_risk_gate"]["band"] == "HIGH"
    # 00:30 UTC == 09:30 KST.
    assert payload["created_at"] == "2026-09-06T09:30:00+09:00"


def test_naive_created_at_is_rejected():
    with pytest.raises(ValidationError):
        GateDecisionRecord.from_gate_decision(
            signal_id="sig-3",
            asset_class="futures",
            symbol="A05603",
            strategy="A_gap_reversion",
            decision=_decision(),
            created_at=datetime(2026, 9, 6, 9, 30),
        )


def test_bad_asset_class_is_rejected():
    with pytest.raises(ValidationError):
        GateDecisionRecord.from_gate_decision(
            signal_id="sig-4",
            asset_class="crypto",  # not "stock" | "futures"
            symbol="A05603",
            strategy="A_gap_reversion",
            decision=_decision(),
            created_at=datetime(2026, 9, 6, 9, 30, tzinfo=_KST),
        )


def test_bad_outcome_value_is_rejected():
    with pytest.raises(ValidationError):
        GateDecisionRecord(
            signal_id="sig-5",
            asset_class="futures",
            symbol="A05603",
            strategy="A_gap_reversion",
            outcome="approved",  # only "reject" is a valid literal today
            reason="anything",
            created_at=datetime(2026, 9, 6, 9, 30, tzinfo=_KST),
            market_risk_gate={},
        )


def test_empty_symbol_is_rejected():
    with pytest.raises(ValidationError):
        GateDecisionRecord.from_gate_decision(
            signal_id="sig-6",
            asset_class="futures",
            symbol="",
            strategy="A_gap_reversion",
            decision=_decision(),
            created_at=datetime(2026, 9, 6, 9, 30, tzinfo=_KST),
        )


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        GateDecisionRecord(
            signal_id="sig-7",
            asset_class="futures",
            symbol="A05603",
            strategy="A_gap_reversion",
            outcome="reject",
            reason="anything",
            created_at=datetime(2026, 9, 6, 9, 30, tzinfo=_KST),
            market_risk_gate={},
            unexpected_field="nope",
        )


# ---------------------------------------------------------------------------
# deterministic_reject_signal_id
#
# Review follow-up (carried over from O14-① / commit 16e215eb): a plain
# uuid4() per reject meant every write was uncorrelatable, even a retry of
# the exact same emission. The id must be a pure function of the emission's
# identity + the verdict's STRUCTURAL fields (band/side/mode) — NOT the
# gate's raw score-bearing `reason` string, which changes on every gate-hash
# refresh and would otherwise mint a fresh id for the identical band/side
# verdict. This is NOT cross-tick dedupe: `generated_at` advances every
# tick in production, so the same candidate re-evaluated on the NEXT tick
# gets a different id and a new row, same as the old uuid4() scheme. What
# this buys is narrower: a byte-identical retry/replay of ONE emission
# reproduces the same id and upserts instead of duplicating.
# ---------------------------------------------------------------------------

_GENERATED_AT = datetime(2026, 9, 6, 9, 30, tzinfo=_KST)


def _id_kwargs(**overrides) -> dict:
    base = {
        "asset_class": "futures",
        "symbol": "A05603",
        "strategy": "A_gap_reversion",
        "direction": "long",
        "generated_at": _GENERATED_AT,
        "decision": _decision(),
    }
    base.update(overrides)
    return base


def test_deterministic_reject_signal_id_is_stable_for_the_identical_candidate():
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs())
    assert id1 == id2
    assert isinstance(id1, str)
    assert len(id1) == 32
    # hex digest -> only hex chars, safe as a SQLite TEXT primary key value.
    int(id1, 16)


def test_deterministic_reject_signal_id_changes_with_generated_at():
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(
        **_id_kwargs(generated_at=_GENERATED_AT.replace(minute=31))
    )
    assert id1 != id2


def test_deterministic_reject_signal_id_changes_with_symbol():
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(symbol="A05604"))
    assert id1 != id2


def test_deterministic_reject_signal_id_changes_with_strategy():
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(strategy="C_event_reaction"))
    assert id1 != id2


def test_deterministic_reject_signal_id_changes_with_direction():
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(direction="short"))
    assert id1 != id2


def test_deterministic_reject_signal_id_changes_with_asset_class():
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(asset_class="stock"))
    assert id1 != id2


def test_deterministic_reject_signal_id_changes_with_gate_band():
    other = _decision(
        band="CRITICAL",
        score=90.0,
        reason="market_risk band=CRITICAL score=90.0 rule=block_new_long",
    )
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(decision=other))
    assert id1 != id2


def test_deterministic_reject_signal_id_changes_with_gate_mode():
    other = _decision(mode="shadow")
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(decision=other))
    assert id1 != id2


def test_deterministic_reject_signal_id_is_stable_across_a_same_band_score_refresh():
    """A gate-hash cron refresh changes only the score embedded in `reason`
    (same band, same side) — this must NOT mint a new id, mirroring the
    exact throttle-key discipline `_maybe_log_shadow_gate` already applies
    (O14-③): score is deliberately excluded from the hashed identity."""
    higher_score = _decision(
        reason="market_risk band=HIGH score=91.0 rule=block_new_long", score=91.0
    )
    id1 = deterministic_reject_signal_id(**_id_kwargs())
    id2 = deterministic_reject_signal_id(**_id_kwargs(decision=higher_score))
    assert id1 == id2
