"""Tests for the shared per-strategy daily-watchlist gate."""
from shared.strategy.entry.daily_watchlist_gate import daily_watchlist_allows


def _meta(strategies):
    return {"daily_watchlist": {"strategies": strategies}}


def test_non_empty_list_membership_allows():
    assert daily_watchlist_allows(_meta({"s": ["005930"]}), "s", "005930") is True


def test_non_empty_list_absent_code_blocks():
    # Static mode: a populated list excludes non-members.
    assert daily_watchlist_allows(_meta({"s": ["005930"]}), "s", "000660") is False


def test_empty_list_is_dynamic_allow():
    assert daily_watchlist_allows(_meta({"s": []}), "s", "000660") is True


def test_absent_strategy_key_is_dynamic_allow():
    assert daily_watchlist_allows(_meta({"peer": ["005930"]}), "s", "000660") is True


def test_populated_peer_does_not_gate_empty_strategy():
    # Reproduces the live payload: {trend_pullback: [1], momentum_breakout: []}.
    meta = _meta({"peer": ["005930"], "s": []})
    assert daily_watchlist_allows(meta, "s", "000660") is True


def test_missing_metadata_allows():
    assert daily_watchlist_allows(None, "s", "000660") is True
    assert daily_watchlist_allows({}, "s", "000660") is True


def test_malformed_watchlist_allows():
    # A bad payload degrades to dynamic mode, never blocks the live universe.
    assert daily_watchlist_allows({"daily_watchlist": "oops"}, "s", "x") is True
    assert (
        daily_watchlist_allows({"daily_watchlist": {"strategies": "oops"}}, "s", "x")
        is True
    )


def test_non_list_codes_is_dynamic_not_substring_match():
    # A bare-string list value must not substring-match (→ dynamic, not block).
    assert daily_watchlist_allows(_meta({"s": "005930"}), "s", "0059") is True
    assert daily_watchlist_allows(_meta({"s": 12345}), "s", "x") is True
