"""Parse system:daily_watchlist:latest JSON -> capped code list."""

from __future__ import annotations

import json

from services.stock_strategy.universe import parse_watchlist_codes


def test_unions_codes_across_strategies():
    payload = json.dumps(
        {
            "strategies": {
                "williams_r": ["005930", "000660"],
                "pattern_pullback": ["000660", "035720"],
            }
        }
    )
    codes = parse_watchlist_codes(payload, max_symbols=40)
    assert set(codes) == {"005930", "000660", "035720"}


def test_caps_at_max_symbols():
    payload = json.dumps({"strategies": {"s": [f"{i:06d}" for i in range(50)]}})
    codes = parse_watchlist_codes(payload, max_symbols=40)
    assert len(codes) == 40


def test_none_or_malformed_returns_empty():
    assert parse_watchlist_codes(None, max_symbols=40) == []
    assert parse_watchlist_codes("not json", max_symbols=40) == []
    assert parse_watchlist_codes(json.dumps({"strategies": {}}), max_symbols=40) == []
