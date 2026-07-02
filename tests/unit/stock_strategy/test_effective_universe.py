"""Effective trading-universe builder tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from shared.stock_universe.effective import (
    build_effective_universe_snapshot,
    parse_effective_universe_codes,
)


def test_effective_universe_applies_manual_block_and_preserves_positions():
    now = datetime(2026, 7, 2, 1, 0, tzinfo=UTC)
    overrides = {
        "manual_exclude": {
            "000660": {
                "reason": "operator block",
                "expires_at": (now + timedelta(hours=2)).isoformat(),
            }
        }
    }

    snapshot = build_effective_universe_snapshot(
        trade_targets_raw=json.dumps(
            {
                "codes": ["005930", "000660"],
                "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
                "scores": {"005930": 0.9, "000660": 0.8},
            }
        ),
        daily_watchlist_raw=json.dumps({"strategies": {"s": ["035720"]}}),
        daily_indicators_raw=json.dumps({"indicators": {"005930": {}, "035720": {}}}),
        overrides_raw=json.dumps(overrides),
        existing_symbols=["000660"],
        existing_names={"000660": "SK하이닉스"},
        max_symbols=3,
        now=now,
    )

    assert snapshot["codes"] == ["005930", "035720"]
    assert snapshot["market_data_codes"] == ["005930", "035720", "000660"]

    rows = {row["code"]: row for row in snapshot["rows"]}
    assert rows["000660"]["new_entries_allowed"] is False
    assert rows["000660"]["market_data_required"] is True
    assert rows["000660"]["override"] == "manual_exclude"
    assert rows["005930"]["daily_indicator"] == "available"


def test_effective_universe_manual_include_leads_cap_order():
    now = datetime(2026, 7, 2, 1, 0, tzinfo=UTC)
    overrides = {
        "manual_include": {
            "111111": {
                "reason": "focus",
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "name": "수동종목",
            }
        }
    }

    snapshot = build_effective_universe_snapshot(
        trade_targets_raw={"codes": ["005930", "000660"]},
        daily_watchlist_raw={"strategies": {"s": ["035720"]}},
        overrides_raw=overrides,
        max_symbols=2,
        now=now,
    )

    assert snapshot["codes"] == ["111111", "005930"]
    rows = {row["code"]: row for row in snapshot["rows"]}
    assert rows["111111"]["name"] == "수동종목"
    assert rows["000660"]["blocked_reason"] == "cap_exceeded"


def test_manual_exclude_does_not_consume_universe_cap():
    now = datetime(2026, 7, 2, 1, 0, tzinfo=UTC)
    overrides = {
        "manual_exclude": {
            "000660": {
                "reason": "blocked",
                "expires_at": (now + timedelta(hours=1)).isoformat(),
            }
        }
    }

    snapshot = build_effective_universe_snapshot(
        trade_targets_raw={"codes": ["005930", "000660", "035720"]},
        overrides_raw=overrides,
        max_symbols=2,
        now=now,
    )

    assert snapshot["codes"] == ["005930", "035720"]


def test_parse_effective_universe_codes_reads_requested_field():
    raw = json.dumps(
        {
            "codes": ["005930", "000660"],
            "market_data_codes": ["005930", "000660", "035720"],
        }
    )

    assert parse_effective_universe_codes(raw, max_symbols=5) == ["005930", "000660"]
    assert parse_effective_universe_codes(
        raw,
        max_symbols=2,
        field="market_data_codes",
    ) == ["005930", "000660"]


def test_parse_effective_universe_codes_ignores_expired_override_snapshot():
    now = datetime(2026, 7, 2, 1, 0, tzinfo=UTC)
    raw = json.dumps(
        {
            "codes": ["005930"],
            "overrides": {
                "manual_exclude": {
                    "000660": {"expires_at": (now - timedelta(seconds=1)).isoformat()}
                }
            },
        }
    )

    assert parse_effective_universe_codes(raw, max_symbols=5, now=now) == []
