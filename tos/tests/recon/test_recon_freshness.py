"""freshness_ok / freshness_lost: horizon + time-confidence + generation (§6.3).

RECON-EV-004 predicate substrate. Both-ways: fresh + time-held + same-generation => ok;
aged / time-lost / generation-changed / any-None => not ok. A time service that recovers
to a NEW generation does not auto-refresh an old marker. No hardcoded horizon — all injected.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from tos.recon import FreshnessMarker, freshness_lost, freshness_ok

from ._recon_strategies import fresh_marker, markers


def test_fresh_positive() -> None:
    """(positive) In-horizon + time held + same generation => fresh."""
    assert freshness_ok(fresh_marker()) is True
    assert freshness_lost(fresh_marker()) is False


@pytest.mark.parametrize("value", [False, None])
def test_aged_horizon_fails(value: bool | None) -> None:
    """(fail-closed) fresh_within_horizon not True => STALE (not fresh)."""
    assert freshness_ok(fresh_marker(fresh_within_horizon=value)) is False


@pytest.mark.parametrize("value", [False, None])
def test_time_confidence_loss_fails(value: bool | None) -> None:
    """(ADR §7 line 103) Loss of time confidence fails all time-dependent freshness closed."""
    assert freshness_ok(fresh_marker(time_confidence_held=value)) is False


def test_new_generation_does_not_auto_refresh() -> None:
    """(canary RECON-EV-004) An old marker (anchored gen 1) is not fresh once time is gen 2."""
    restarted = fresh_marker(time_generation=2, anchored_generation=1)
    assert freshness_ok(restarted) is False
    assert freshness_lost(restarted) is True


@pytest.mark.parametrize(
    "gen_override",
    [
        {"time_generation": None},
        {"anchored_generation": None},
        {"time_generation": None, "anchored_generation": None},
    ],
)
def test_none_generation_fails_closed(gen_override: dict) -> None:
    """(fail-closed) A None generation (untracked restart) fails closed."""
    assert freshness_ok(fresh_marker(**gen_override)) is False


def test_default_marker_is_not_fresh() -> None:
    """(no vacuous permit) The all-None default marker is never fresh."""
    assert freshness_ok(FreshnessMarker()) is False
    assert freshness_lost(FreshnessMarker()) is True


_FRESH_FLAGS = ["fresh_within_horizon", "time_confidence_held"]


@pytest.mark.parametrize("flag", _FRESH_FLAGS)
@pytest.mark.parametrize("value", [False, None])
def test_drop_one_freshness_flag_fails(flag: str, value: bool | None) -> None:
    """(drop-one) Dropping ANY single freshness flag from the positive marker fails closed."""
    assert freshness_ok(fresh_marker(**{flag: value})) is False


@given(marker=markers())
def test_freshness_lost_is_exact_negation(marker: FreshnessMarker) -> None:
    """(property) freshness_lost is exactly the negation of freshness_ok."""
    assert freshness_lost(marker) is (not freshness_ok(marker))
