"""Parse system:daily_watchlist:latest JSON -> capped code list."""

from __future__ import annotations

import json

from services.stock_strategy.universe import (
    _EFFECTIVE_PAYLOAD_KEY,
    _SCREENER_PAYLOAD_KEY,
    build_effective_watchlist,
    effective_universe_to_watchlist,
    merge_screener_universe,
    parse_trade_targets_codes,
    parse_watchlist_codes,
)


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


def test_parse_watchlist_codes_accepts_dict():
    payload = {"strategies": {"s": ["005930", "000660"]}}
    assert parse_watchlist_codes(payload, max_symbols=40) == ["005930", "000660"]


def test_parse_trade_targets_codes():
    raw = json.dumps({"codes": ["005930", "000660", "005930"], "names": {}})
    assert parse_trade_targets_codes(raw, max_symbols=40) == ["005930", "000660"]
    assert parse_trade_targets_codes(raw, max_symbols=1) == ["005930"]
    assert parse_trade_targets_codes(None, max_symbols=40) == []
    assert parse_trade_targets_codes("not json", max_symbols=40) == []
    assert parse_trade_targets_codes(json.dumps({}), max_symbols=40) == []


def test_select_stock_universe_prioritizes_sources_under_cap():
    from shared.stock_universe.selection import select_stock_universe

    assert select_stock_universe(
        trade_targets=["005930", "000660", "035720"],
        watchlist=["000660", "035420", "051910"],
        existing=["051910", "068270"],
        max_symbols=5,
    ) == ["005930", "000660", "035720", "035420", "051910"]


def test_merge_screener_universe_unions_watchlist_and_targets():
    wl = json.dumps({"strategies": {"pattern_pullback": ["105560"]}})
    tt = json.dumps({"codes": ["005930", "000660", "105560"]})
    merged = merge_screener_universe(wl, tt, max_symbols=40)
    codes = parse_watchlist_codes(merged, max_symbols=40)
    # Screener targets lead the capped strategy universe, then watchlist-only codes.
    assert codes[:3] == ["005930", "000660", "105560"]
    assert set(codes) == {"105560", "005930", "000660"}


def test_merge_screener_universe_applies_trade_targets_first_cap_order():
    wl = json.dumps(
        {
            "strategies": {
                "opening_volume_surge": [
                    "105560",
                    "035420",
                    "051910",
                    "068270",
                ]
            }
        }
    )
    tt = json.dumps({"codes": ["005930", "000660", "105560"]})

    merged = merge_screener_universe(wl, tt, max_symbols=4)

    assert parse_watchlist_codes(merged, max_symbols=4) == [
        "005930",
        "000660",
        "105560",
        "035420",
    ]


def test_merge_screener_universe_preserves_trade_target_payload():
    wl = json.dumps({"strategies": {"pattern_pullback": ["105560"]}})
    trade_targets = {
        "codes": ["080220"],
        "names": {"080220": "제주반도체"},
        "scores": {"080220": 0.62},
        "metadata": {
            "080220": {
                "llm_quality": 0.61859,
                "llm_confidence": 1.0,
                "llm_only": True,
            }
        },
    }

    merged = merge_screener_universe(wl, json.dumps(trade_targets), max_symbols=40)

    assert parse_watchlist_codes(merged, max_symbols=40) == ["080220", "105560"]
    assert merged[_SCREENER_PAYLOAD_KEY]["metadata"]["080220"]["llm_only"] is True


def test_merge_screener_universe_handles_empty_sources():
    # No watchlist, only screener targets.
    merged = merge_screener_universe(
        None, json.dumps({"codes": ["005930"]}), max_symbols=40
    )
    assert parse_watchlist_codes(merged, max_symbols=40) == ["005930"]
    # No targets, only watchlist.
    merged = merge_screener_universe(
        json.dumps({"strategies": {"s": ["000660"]}}), None, max_symbols=40
    )
    assert parse_watchlist_codes(merged, max_symbols=40) == ["000660"]
    # Both empty -> empty universe.
    assert (
        parse_watchlist_codes(
            merge_screener_universe(None, None, max_symbols=40), max_symbols=40
        )
        == []
    )


def test_effective_universe_to_watchlist_filters_blocked_trade_target_payload():
    effective = {
        "codes": ["005930"],
        "market_data_codes": ["005930", "000660"],
        "generated_at": "2026-07-02T00:00:00+00:00",
    }
    trade_targets = {
        "codes": ["005930", "000660"],
        "metadata": {
            "005930": {"llm_quality": 0.9},
            "000660": {"llm_quality": 0.95},
        },
        "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
    }

    watchlist = effective_universe_to_watchlist(
        effective,
        watchlist_raw={"strategies": {"pattern_pullback": ["005930", "000660"]}},
        trade_targets_raw=trade_targets,
        max_symbols=40,
    )

    assert parse_watchlist_codes(watchlist, max_symbols=40) == ["005930"]
    assert watchlist[_SCREENER_PAYLOAD_KEY]["codes"] == ["005930"]
    assert "000660" not in watchlist[_SCREENER_PAYLOAD_KEY]["metadata"]
    assert watchlist[_EFFECTIVE_PAYLOAD_KEY]["market_data_codes"] == [
        "005930",
        "000660",
    ]


def test_build_effective_watchlist_honors_manual_exclude_when_no_snapshot():
    watchlist = build_effective_watchlist(
        watchlist_raw={"strategies": {"pattern_pullback": ["005930", "000660"]}},
        trade_targets_raw={"codes": ["005930", "000660"]},
        overrides_raw={
            "manual_exclude": {
                "000660": {
                    "reason": "blocked",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                }
            }
        },
        max_symbols=40,
    )

    assert parse_watchlist_codes(watchlist, max_symbols=40) == ["005930"]
