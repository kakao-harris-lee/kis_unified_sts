from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import scripts.analysis.reconcile_stock_swing_positions as mod


def _ch_position(**overrides):
    base = {
        "id": "pos-1",
        "code": "108490",
        "name": "로보티즈",
        "entry_date": datetime(2026, 5, 13, 12, 34, 44),
        "entry_price": 354750.0,
        "quantity": 10,
        "strategy": "external",
        "execution_venue": "KRX",
        "stop_loss_price": 0.0,
        "high_since_entry": 354750.0,
        "current_state": "survival",
        "side": "long",
        "fee_rate": 0.0,
        "updated_at": datetime(2026, 5, 13, 12, 34, 44),
    }
    base.update(overrides)
    return mod.SwingOpenPosition(**base)


def _redis_position(**overrides):
    base = {
        "id": "redis-1",
        "code": "005930",
    }
    base.update(overrides)
    return mod.RedisOpenPosition(**base)


def test_plan_reconciliation_selects_clickhouse_only_old_position():
    position = _ch_position()

    candidates = mod.plan_reconciliation(
        [position],
        [],
        now=datetime(2026, 5, 17, tzinfo=UTC),
        min_age_days=1,
    )

    assert len(candidates) == 1
    assert candidates[0].position is position
    assert candidates[0].age_days == 4
    assert candidates[0].reason == "redis_absent_id_and_code"


def test_plan_reconciliation_skips_when_redis_has_same_id_or_code():
    by_id = _ch_position(id="same-id", code="108490")
    by_code = _ch_position(id="other-id", code="005930")

    candidates = mod.plan_reconciliation(
        [by_id, by_code],
        [
            _redis_position(id="same-id", code="000660"),
            _redis_position(id="redis-2", code="005930"),
        ],
        now=datetime(2026, 5, 17, tzinfo=UTC),
        min_age_days=1,
    )

    assert candidates == []


def test_plan_reconciliation_honors_min_age_and_filters():
    old_target = _ch_position(id="target", code="108490")
    old_other = _ch_position(id="other", code="000660")
    fresh_target = _ch_position(
        id="fresh",
        code="005930",
        entry_date=datetime(2026, 5, 17, 9, 0, 0),
    )

    candidates = mod.plan_reconciliation(
        [old_target, old_other, fresh_target],
        [],
        now=datetime(2026, 5, 17, tzinfo=UTC),
        min_age_days=1,
        code_filter={"108490", "005930"},
        id_filter={"target", "fresh"},
    )

    assert [candidate.position.id for candidate in candidates] == ["target"]


def test_close_replacement_row_marks_position_closed_at_entry_price():
    candidate = mod.ReconciliationCandidate(
        position=_ch_position(id="target"),
        age_days=4,
        reason="redis_absent_id_and_code",
    )
    closed_at = datetime(2026, 5, 17, 3, 30, 0)

    row = mod.close_replacement_row(
        candidate,
        closed_at=closed_at,
        exit_reason="reconciled_redis_absent",
    )

    assert row[0] == "target"
    assert row[7] == "KRX"
    assert row[11] == 0
    assert row[12] == closed_at
    assert row[13] == 354750.0
    assert row[14] == "reconciled_redis_absent"
    assert row[15] == 0.0


def test_apply_replacements_inserts_expected_rows():
    candidate = mod.ReconciliationCandidate(
        position=_ch_position(id="target"),
        age_days=4,
        reason="redis_absent_id_and_code",
    )
    client = MagicMock()
    closed_at = datetime(2026, 5, 17, 3, 30, 0)

    applied = mod.apply_replacements(
        client,
        "market",
        "swing_positions",
        [candidate],
        closed_at=closed_at,
        exit_reason="reconciled_redis_absent",
    )

    assert applied == 1
    sql, rows = client.execute.call_args.args
    assert "INSERT INTO market.swing_positions" in sql
    assert rows[0][0] == "target"
    assert rows[0][11] == 0
