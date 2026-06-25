"""Tests for the screener volume-surge flag accumulator (update_volume_surge_flags).

The producer accumulates intraday volume-surge flags (codes hit by the KIS
``volume_power`` ranking source) into a code->{code, flag_time, flag_price}
dict and publishes them to Redis for the LLM scorecard ``volume_surge`` facet.

``update_volume_surge_flags`` is a pure helper (no Redis, no clock — caller
passes ``now_kst_iso``) so it is hermetically testable.
"""

from __future__ import annotations

from services.screener import (
    extract_surge_swing_metadata,
    update_volume_surge_flags,
)

_NOW_1 = "2026-06-25T09:05:00+09:00"
_NOW_2 = "2026-06-25T09:35:00+09:00"


def _info(price):
    return {"name": "테스트", "price": price, "change_pct": 5.0}


def test_volume_power_hit_is_flagged_with_now_and_flag_price():
    info_by_code = {"005930": _info(70000)}
    swing_metadata = {"005930": {"volume_power": 1.5, "volume_power_rank": 3}}

    result = update_volume_surge_flags(
        {},
        info_by_code=info_by_code,
        swing_metadata=swing_metadata,
        now_kst_iso=_NOW_1,
        min_volume_power=0.0,
    )

    assert result["005930"] == {
        "code": "005930",
        "flag_time": _NOW_1,
        "flag_price": 70000.0,
    }


def test_first_flag_wins_does_not_overwrite():
    swing_metadata = {"005930": {"volume_power": 1.5, "volume_power_rank": 3}}

    existing = update_volume_surge_flags(
        {},
        info_by_code={"005930": _info(70000)},
        swing_metadata=swing_metadata,
        now_kst_iso=_NOW_1,
        min_volume_power=0.0,
    )

    # Second call: different now + different price. Original flag must persist.
    result = update_volume_surge_flags(
        existing,
        info_by_code={"005930": _info(99999)},
        swing_metadata=swing_metadata,
        now_kst_iso=_NOW_2,
        min_volume_power=0.0,
    )

    assert result["005930"]["flag_time"] == _NOW_1
    assert result["005930"]["flag_price"] == 70000.0


def test_below_threshold_not_flagged():
    result = update_volume_surge_flags(
        {},
        info_by_code={"005930": _info(70000)},
        swing_metadata={"005930": {"volume_power": 0.5, "volume_power_rank": 3}},
        now_kst_iso=_NOW_1,
        min_volume_power=1.0,
    )

    assert result == {}


def test_no_volume_power_rank_not_flagged():
    # Code present in swing_metadata via another source (e.g. near_new_high)
    # but NOT actually hit by the volume_power source → must not flag.
    result = update_volume_surge_flags(
        {},
        info_by_code={"005930": _info(70000)},
        swing_metadata={"005930": {"near_new_high_rank": 2, "near_high_rate": 98.0}},
        now_kst_iso=_NOW_1,
        min_volume_power=0.0,
    )

    assert result == {}


def test_non_positive_flag_price_skipped():
    swing_metadata = {
        "005930": {"volume_power": 1.5, "volume_power_rank": 3},
        "000660": {"volume_power": 2.0, "volume_power_rank": 1},
    }
    info_by_code = {
        "005930": _info(0),  # price 0 → skip
        "000660": _info(-5),  # negative → skip
    }

    result = update_volume_surge_flags(
        {},
        info_by_code=info_by_code,
        swing_metadata=swing_metadata,
        now_kst_iso=_NOW_1,
        min_volume_power=0.0,
    )

    assert result == {}


def test_threshold_boundary_is_inclusive():
    result = update_volume_surge_flags(
        {},
        info_by_code={"005930": _info(70000)},
        swing_metadata={"005930": {"volume_power": 1.0, "volume_power_rank": 3}},
        now_kst_iso=_NOW_1,
        min_volume_power=1.0,
    )

    assert "005930" in result


def test_missing_volume_power_value_treated_as_not_qualifying():
    # rank present but volume_power None → cannot compare to threshold → skip.
    result = update_volume_surge_flags(
        {},
        info_by_code={"005930": _info(70000)},
        swing_metadata={"005930": {"volume_power": None, "volume_power_rank": 3}},
        now_kst_iso=_NOW_1,
        min_volume_power=0.0,
    )

    assert result == {}


# ---------------------------------------------------------------------------
# extract_surge_swing_metadata — the priority_metadata → flat unwrap. Guards the
# silent-dormancy class: if _select_top_codes stops nesting under
# "swing_discovery", these tests fail loudly instead of the feed going empty.
# ---------------------------------------------------------------------------


def test_extract_unwraps_swing_discovery():
    priority_metadata = {
        "005930": {
            "score": 0.9,
            "swing_discovery": {"volume_power": 12.5, "volume_power_rank": 1},
        },
        "000660": {
            "score": 0.7,
            "swing_discovery": {"volume_power": 8.0, "volume_power_rank": 4},
        },
    }
    flat = extract_surge_swing_metadata(priority_metadata)
    assert flat == {
        "005930": {"volume_power": 12.5, "volume_power_rank": 1},
        "000660": {"volume_power": 8.0, "volume_power_rank": 4},
    }
    # And the flattened shape feeds straight into the accumulator.
    flags = update_volume_surge_flags(
        {},
        info_by_code={"005930": _info(70000)},
        swing_metadata=flat,
        now_kst_iso=_NOW_1,
        min_volume_power=0.0,
    )
    assert flags["005930"]["flag_price"] == 70000.0


def test_extract_skips_entries_without_swing_discovery():
    # A code surfaced only via a non-swing source (no swing_discovery) is skipped.
    priority_metadata = {
        "005930": {"score": 0.9, "swing_discovery": {"volume_power_rank": 1}},
        "000660": {"score": 0.7},  # no swing_discovery → skipped
        "035720": {"score": 0.5, "swing_discovery": None},  # non-dict → skipped
    }
    flat = extract_surge_swing_metadata(priority_metadata)
    assert set(flat) == {"005930"}


def test_extract_tolerates_non_dict_entries():
    flat = extract_surge_swing_metadata({"005930": "oops", "000660": None})
    assert flat == {}
