"""Unit tests for PortfolioMddFilter (Phase 3B circuit-breaker gate).

Hermetic: snapshot/now providers injected — no Redis client is ever built.
Pins the fail-open contract: missing key, provider errors, stale asof_ts,
unknown stages, and every non-enforce mode MUST pass the signal unchanged.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.risk.filters.portfolio_mdd import PortfolioMddFilter

NOW = datetime(2026, 7, 6, 10, 0)
FRESH_ASOF = (NOW - timedelta(hours=15)).isoformat()  # previous 19:00 KST run


def _make_filter(snapshot, **kwargs) -> PortfolioMddFilter:
    params = {
        "reduce_size_factor": 0.5,
        "latest_key": "portfolio:equity:latest",
        "stale_max_age_seconds": 93600,
        "snapshot_provider": lambda: snapshot,
        "now_provider": lambda: NOW,
    }
    params.update(kwargs)
    return PortfolioMddFilter(**params)


def _snapshot(stage: str, mode: str = "enforce", asof: str = FRESH_ASOF) -> dict:
    return {"stage": stage, "mode": mode, "asof_ts": asof}


def _check(filter_: PortfolioMddFilter):
    # Signal / state snapshot are not inspected by this filter.
    return filter_.check(None, None)  # type: ignore[arg-type]


class TestFailOpen:
    def test_missing_key_passes(self):
        result = _check(_make_filter(None))
        assert result.passed and result.size_multiplier == 1.0

    def test_provider_error_passes(self):
        def _boom():
            raise ConnectionError("redis down")

        filter_ = _make_filter(None, snapshot_provider=_boom)
        result = _check(filter_)
        assert result.passed and result.size_multiplier == 1.0

    @pytest.mark.parametrize("mode", ["shadow", "off", "", "SHADOW"])
    def test_non_enforce_mode_passes_even_at_full_stop(self, mode: str):
        """Shadow/off must never block or shrink anything (Phase 3 pin)."""
        result = _check(_make_filter(_snapshot("FULL_STOP", mode=mode)))
        assert result.passed
        assert result.size_multiplier == 1.0
        assert result.skip_reason is None

    def test_stale_snapshot_passes(self):
        stale = (NOW - timedelta(hours=27)).isoformat()
        result = _check(_make_filter(_snapshot("HALT_NEW", asof=stale)))
        assert result.passed

    def test_missing_asof_passes(self):
        result = _check(_make_filter({"stage": "HALT_NEW", "mode": "enforce"}))
        assert result.passed

    def test_unparseable_asof_passes(self):
        result = _check(_make_filter(_snapshot("HALT_NEW", asof="not-a-date")))
        assert result.passed

    def test_unknown_stage_passes(self):
        result = _check(_make_filter(_snapshot("MELTDOWN")))
        assert result.passed


class TestEnforce:
    def test_normal_stage_passes_full_size(self):
        result = _check(_make_filter(_snapshot("NORMAL")))
        assert result.passed and result.size_multiplier == 1.0

    def test_reduce_stage_shrinks_size(self):
        result = _check(_make_filter(_snapshot("REDUCE")))
        assert result.passed
        assert result.size_multiplier == pytest.approx(0.5)

    def test_reduce_factor_comes_from_config(self):
        filter_ = _make_filter(_snapshot("REDUCE"), reduce_size_factor=0.25)
        assert _check(filter_).size_multiplier == pytest.approx(0.25)

    def test_halt_new_blocks(self):
        result = _check(_make_filter(_snapshot("HALT_NEW")))
        assert not result.passed
        assert result.skip_reason == "portfolio_mdd_halt_new"

    def test_full_stop_blocks(self):
        result = _check(_make_filter(_snapshot("FULL_STOP")))
        assert not result.passed
        assert result.skip_reason == "portfolio_mdd_full_stop"

    def test_stage_is_case_insensitive(self):
        result = _check(_make_filter(_snapshot("halt_new")))
        assert not result.passed

    def test_aware_asof_is_normalized_to_kst(self):
        aware = (NOW - timedelta(hours=15)).isoformat() + "+09:00"
        result = _check(_make_filter(_snapshot("HALT_NEW", asof=aware)))
        assert not result.passed  # fresh once normalized → enforced


class TestConstruction:
    def test_invalid_reduce_factor_rejected(self):
        with pytest.raises(ValueError):
            _make_filter(None, reduce_size_factor=0.0)
        with pytest.raises(ValueError):
            _make_filter(None, reduce_size_factor=1.5)

    def test_filter_name_registered(self):
        assert _make_filter(None).name == "portfolio_mdd"
