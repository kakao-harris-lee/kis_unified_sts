# tests/unit/risk/test_filter_concurrent_positions.py
"""Unit tests for ConcurrentPositionsFilter (Phase 4-e).

The filter ports the World-A ``RiskManager`` total + per-asset concurrency caps
into the decoupled World-B ``RiskFilterLayer``. It is fail-open by construction
(no provider / no cap / provider error → pass) and uses the exact ``>=``
boundary the monolithic RiskManager uses.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from shared.decision.signal import Signal
from shared.risk.config import ConcurrentPositionsFilterSettings
from shared.risk.filters.concurrent_positions import (
    SKIP_PER_ASSET,
    SKIP_TOTAL,
    ConcurrentPositionsFilter,
)
from shared.risk.state import RiskStateSnapshot

_SYMBOL = "A05603"


def _make_signal(symbol: str = _SYMBOL) -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol=symbol,
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


def _snap() -> RiskStateSnapshot:
    return RiskStateSnapshot()


def _counts(mapping: Mapping[str, int]):
    return lambda: dict(mapping)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_filter_name() -> None:
    f = ConcurrentPositionsFilter(asset_class="stock")
    assert f.name == "concurrent_positions"


# ---------------------------------------------------------------------------
# (a) No provider injected → fail-open pass
# ---------------------------------------------------------------------------


def test_no_provider_passes() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=None,
        max_total_positions=1,
        max_positions_per_asset=1,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# (b) Both caps unset → fail-open pass (provider never consulted)
# ---------------------------------------------------------------------------


def test_no_caps_passes_without_consulting_provider() -> None:
    calls = {"n": 0}

    def provider() -> Mapping[str, int]:
        calls["n"] += 1
        return {"stock": 100}

    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=provider,
        max_total_positions=None,
        max_positions_per_asset=None,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert calls["n"] == 0  # short-circuit before any read


# ---------------------------------------------------------------------------
# (c) Total cap — boundary is >= (RiskManager parity)
# ---------------------------------------------------------------------------


def test_total_cap_reached_rejects_at_boundary() -> None:
    # 12 + 8 == 20 == cap → reject (RiskManager blocks at total >= cap).
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=_counts({"stock": 12, "futures": 8}),
        max_total_positions=20,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_TOTAL
    assert result.filter_name == "concurrent_positions"


def test_total_cap_below_boundary_passes() -> None:
    # sum == 19 == cap - 1 → pass.
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=_counts({"stock": 11, "futures": 8}),
        max_total_positions=20,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


def test_total_cap_above_boundary_rejects() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="futures",
        open_positions_count_provider=_counts({"stock": 15, "futures": 10}),
        max_total_positions=20,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_TOTAL


# ---------------------------------------------------------------------------
# (d) Per-asset cap — boundary is >= and looks up the bound asset_class
# ---------------------------------------------------------------------------


def test_per_asset_cap_reached_rejects() -> None:
    # futures count 5 == cap; total (5+3=8) below total cap → per-asset fires.
    f = ConcurrentPositionsFilter(
        asset_class="futures",
        open_positions_count_provider=_counts({"futures": 5, "stock": 3}),
        max_total_positions=20,
        max_positions_per_asset=5,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_PER_ASSET


def test_per_asset_cap_only_counts_bound_asset() -> None:
    # stock is at its cap but this filter guards futures → the stock overflow
    # must not reject a futures entry (per-asset is asset-scoped).
    f = ConcurrentPositionsFilter(
        asset_class="futures",
        open_positions_count_provider=_counts({"futures": 1, "stock": 99}),
        max_positions_per_asset=5,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True


def test_missing_asset_key_treated_as_zero() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="futures",
        open_positions_count_provider=_counts({"stock": 3}),
        max_positions_per_asset=5,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True


# ---------------------------------------------------------------------------
# (e) Below both caps → pass
# ---------------------------------------------------------------------------


def test_below_all_caps_passes() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=_counts({"stock": 2, "futures": 1}),
        max_total_positions=20,
        max_positions_per_asset=15,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# Total cap takes precedence over per-asset (RiskManager check order)
# ---------------------------------------------------------------------------


def test_total_cap_checked_before_per_asset() -> None:
    # Both caps breached; RiskManager checks total first → SKIP_TOTAL wins.
    f = ConcurrentPositionsFilter(
        asset_class="futures",
        open_positions_count_provider=_counts({"futures": 10, "stock": 15}),
        max_total_positions=20,
        max_positions_per_asset=5,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_TOTAL


# ---------------------------------------------------------------------------
# (f) Provider raises / returns None → fail-open pass
# ---------------------------------------------------------------------------


def test_provider_exception_fails_open() -> None:
    def boom() -> Mapping[str, int]:
        raise RuntimeError("redis down")

    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=boom,
        max_total_positions=1,
        max_positions_per_asset=1,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


def test_provider_returns_none_fails_open() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=lambda: None,
        max_total_positions=1,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True


# ---------------------------------------------------------------------------
# Only one cap configured — the unset dimension never rejects
# ---------------------------------------------------------------------------


def test_only_total_cap_configured() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=_counts({"stock": 99}),
        max_total_positions=20,
        max_positions_per_asset=None,
    )
    assert f.check(_make_signal(), _snap()).passed is False  # total breached


def test_only_per_asset_cap_configured() -> None:
    f = ConcurrentPositionsFilter(
        asset_class="stock",
        open_positions_count_provider=_counts({"stock": 3, "futures": 99}),
        max_total_positions=None,
        max_positions_per_asset=15,
    )
    # futures overflow ignored (unset total cap); stock below per-asset → pass.
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# Settings validation — caps must be > 0 (World-A MIN_POSITIONS=1 parity)
# ---------------------------------------------------------------------------


def test_settings_defaults_disabled() -> None:
    s = ConcurrentPositionsFilterSettings()
    assert s.enabled is False
    assert s.max_total_positions is None
    assert s.max_positions_per_asset is None


@pytest.mark.parametrize("bad", [0, -1])
def test_settings_reject_non_positive_caps(bad: int) -> None:
    with pytest.raises(ValueError):
        ConcurrentPositionsFilterSettings(max_total_positions=bad)
    with pytest.raises(ValueError):
        ConcurrentPositionsFilterSettings(max_positions_per_asset=bad)
