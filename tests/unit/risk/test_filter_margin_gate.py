# tests/unit/risk/test_filter_margin_gate.py
"""Unit tests for MarginGateFilter (Phase 4-f).

The filter wires the futures margin read-model (``futures:risk:latest``, from
``services/futures_margin_risk``) into the decoupled World-B ``RiskFilterLayer``
as a new-entry gate. It is fail-open by construction (mode != enforce / snapshot
absent / stale / corrupt / unknown level → pass) and only rejects when the
published ``risk_level`` is ``block_new_entries``/``critical`` in ``enforce``
mode. It is FUTURES-ONLY (built only for ``_asset_class == 'futures'``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shared.decision.signal import Signal
from shared.risk.config import MarginGateFilterSettings
from shared.risk.filters.margin_gate import MarginGateFilter
from shared.risk.state import RiskStateSnapshot

_SYMBOL = "A05603"
#: Deterministic KST-naive clock used both as the filter's ``now_provider`` and
#: as the base for building snapshot ``asof_ts`` timestamps.
_NOW = datetime(2026, 7, 10, 10, 0, 0)
#: Aware KST timestamp inside the ``09:00-10:30`` window so the from_config chain
#: tests never get rejected by TradingHoursFilter (filter #1).
_IN_WINDOW_KST = datetime(2026, 7, 10, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))


def _make_signal(symbol: str = _SYMBOL, generated_at: datetime | None = None) -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol=symbol,
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
        generated_at=generated_at,
    )


def _snap() -> RiskStateSnapshot:
    return RiskStateSnapshot()


def _snapshot(
    *,
    risk_level: str = "critical",
    asof: datetime | None = None,
) -> dict[str, str]:
    """Build a decoded ``futures:risk:latest`` hash (only consumed fields)."""
    asof = asof if asof is not None else _NOW
    return {
        "risk_level": risk_level,
        "asof_ts": asof.isoformat(),
        "degraded": "false",
    }


def _filter(
    *,
    mode: str = "enforce",
    provider=None,
    stale_max_age_seconds: int = 1200,
) -> MarginGateFilter:
    return MarginGateFilter(
        mode=mode,
        latest_key="futures:risk:latest",
        stale_max_age_seconds=stale_max_age_seconds,
        snapshot_provider=provider if provider is not None else (lambda: None),
        now_provider=lambda: _NOW,
    )


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_filter_name() -> None:
    assert _filter().name == "margin_gate"


# ---------------------------------------------------------------------------
# (a) Snapshot absent (dormant publisher) → fail-open pass
# ---------------------------------------------------------------------------


def test_no_snapshot_passes() -> None:
    f = _filter(mode="enforce", provider=lambda: None)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# (b) Stale snapshot → fail-open pass (even if risk_level is critical)
# ---------------------------------------------------------------------------


def test_stale_snapshot_passes() -> None:
    stale = _snapshot(risk_level="critical", asof=_NOW - timedelta(seconds=1201))
    f = _filter(mode="enforce", provider=lambda: stale)
    assert f.check(_make_signal(), _snap()).passed is True


def test_fresh_boundary_not_stale() -> None:
    # age == stale_max_age_seconds is NOT stale (> boundary), so a fresh
    # critical snapshot at exactly the age bound still rejects.
    edge = _snapshot(risk_level="critical", asof=_NOW - timedelta(seconds=1200))
    f = _filter(mode="enforce", provider=lambda: edge)
    assert f.check(_make_signal(), _snap()).passed is False


# ---------------------------------------------------------------------------
# (c) Corrupt / deserialization failure → fail-open pass (inside the guard)
# ---------------------------------------------------------------------------


def test_provider_exception_fails_open() -> None:
    def boom() -> Mapping[str, str]:
        raise RuntimeError("redis down")

    f = _filter(mode="enforce", provider=boom)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


@pytest.mark.parametrize("bad_return", [[1, 2, 3], "not-a-mapping", 42, (1, 2)])
def test_provider_non_mapping_fails_open(bad_return: object) -> None:
    """A non-Mapping return must fail OPEN via the isinstance guard — a bare
    ``.get()`` would raise AttributeError otherwise, escaping into the guardless
    layer/daemon path (fail-CLOSED)."""
    f = _filter(mode="enforce", provider=lambda: bad_return)  # type: ignore[return-value]
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (d) mode != enforce → pass (snapshot never even consulted)
# ---------------------------------------------------------------------------


def test_shadow_mode_passes_without_consulting_snapshot() -> None:
    calls = {"n": 0}

    def provider() -> Mapping[str, str]:
        calls["n"] += 1
        return _snapshot(risk_level="critical")

    f = _filter(mode="shadow", provider=provider)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert calls["n"] == 0  # short-circuit before any read


@pytest.mark.parametrize("mode", ["shadow", "off", "", "ENFORCE_TYPO"])
def test_non_enforce_modes_pass(mode: str) -> None:
    f = _filter(mode=mode, provider=lambda: _snapshot(risk_level="critical"))
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (e) risk_level == critical + enforce → reject
# ---------------------------------------------------------------------------


def test_critical_enforce_rejects() -> None:
    f = _filter(mode="enforce", provider=lambda: _snapshot(risk_level="critical"))
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == "margin_gate_critical"
    assert result.filter_name == "margin_gate"


# ---------------------------------------------------------------------------
# (f) risk_level == block_new_entries + enforce → reject
# ---------------------------------------------------------------------------


def test_block_new_entries_enforce_rejects() -> None:
    f = _filter(
        mode="enforce", provider=lambda: _snapshot(risk_level="block_new_entries")
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == "margin_gate_block_new_entries"


# ---------------------------------------------------------------------------
# (g) risk_level ok/watch + enforce → pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["ok", "watch"])
def test_ok_and_watch_enforce_pass(level: str) -> None:
    f = _filter(mode="enforce", provider=lambda: _snapshot(risk_level=level))
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# reduce_only + enforce → pass (observation-only in this landing; no soft
# size factor is invented — see filter docstring / plan §6(d))
# ---------------------------------------------------------------------------


def test_reduce_only_enforce_passes() -> None:
    f = _filter(mode="enforce", provider=lambda: _snapshot(risk_level="reduce_only"))
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# (h) unknown risk_level → fail-open pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["", "meltdown", "OK", "unknown", "None"])
def test_unknown_risk_level_passes(level: str) -> None:
    f = _filter(mode="enforce", provider=lambda: _snapshot(risk_level=level))
    assert f.check(_make_signal(), _snap()).passed is True


def test_missing_risk_level_key_passes() -> None:
    # asof present + fresh, but no risk_level field at all → unknown → pass.
    f = _filter(mode="enforce", provider=lambda: {"asof_ts": _NOW.isoformat()})
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (i) missing / unparseable timestamp → stale → pass (positive-form, #458)
# ---------------------------------------------------------------------------


def test_missing_timestamp_treated_stale_passes() -> None:
    # A fresh-looking critical level with NO asof_ts must be treated as stale
    # (fail open), never as a live block signal.
    f = _filter(mode="enforce", provider=lambda: {"risk_level": "critical"})
    assert f.check(_make_signal(), _snap()).passed is True


def test_unparseable_timestamp_treated_stale_passes() -> None:
    bad = {"risk_level": "critical", "asof_ts": "not-a-timestamp"}
    f = _filter(mode="enforce", provider=lambda: bad)
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# Settings — defaults keep the filter structurally inert
# ---------------------------------------------------------------------------


def test_settings_defaults_disabled_and_shadow() -> None:
    s = MarginGateFilterSettings()
    assert s.enabled is False
    assert s.mode == "shadow"
    assert s.latest_key == "futures:risk:latest"
    assert s.stale_max_age_seconds == 1200


def test_settings_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        MarginGateFilterSettings(mode="live")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# from_config wiring — futures-only + inert no-op equivalence
# ---------------------------------------------------------------------------


def _futures_cfg(*, enabled: bool, mode: str = "shadow"):
    from shared.risk.config import FuturesRiskConfig

    cfg = FuturesRiskConfig()
    cfg.margin_gate.enabled = enabled
    cfg.margin_gate.mode = mode  # type: ignore[assignment]
    return cfg


def test_from_config_disabled_does_not_build_filter() -> None:
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _futures_cfg(enabled=False),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    names = [f.name for f in layer._filters]
    assert "margin_gate" not in names


def test_from_config_shadow_builds_but_passes() -> None:
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _futures_cfg(enabled=True, mode="shadow"),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        # A critical snapshot that WOULD reject in enforce — proves shadow passes.
        margin_snapshot_provider=lambda: _snapshot(risk_level="critical", asof=None),
    )
    names = [f.name for f in layer._filters]
    assert "margin_gate" in names
    result = layer.evaluate(_make_signal(generated_at=_IN_WINDOW_KST), _snap())
    assert result.passed is True


def test_from_config_stock_never_builds_margin_gate() -> None:
    """Futures-only: StockRiskConfig inherits the margin_gate field but the
    stock chain must never build the filter (asset_class gate)."""
    from shared.risk.config import StockRiskConfig
    from shared.risk.layer import RiskFilterLayer

    cfg = StockRiskConfig()
    cfg.margin_gate.enabled = True
    cfg.margin_gate.mode = "enforce"  # type: ignore[assignment]

    layer = RiskFilterLayer.from_config(
        cfg,
        trading_windows=["09:00-15:30"],
        portfolio_snapshot_provider=lambda: None,
        # Even a critical snapshot must not matter — the filter isn't built.
        margin_snapshot_provider=lambda: _snapshot(risk_level="critical"),
    )
    names = [f.name for f in layer._filters]
    assert "margin_gate" not in names


def test_from_config_enforce_chain_rejects_on_fresh_critical() -> None:
    from shared.risk.layer import RiskFilterLayer

    # Fresh relative to the filter's real (default) now_provider used inside the
    # chain: asof = now → age ≈ 0 < stale bound.
    now_kst = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    layer = RiskFilterLayer.from_config(
        _futures_cfg(enabled=True, mode="enforce"),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        margin_snapshot_provider=lambda: _snapshot(risk_level="critical", asof=now_kst),
    )
    result = layer.evaluate(_make_signal(generated_at=_IN_WINDOW_KST), _snap())
    assert result.passed is False
    assert result.skip_reason == "margin_gate_critical"


def test_from_config_enforce_no_snapshot_equivalent_to_no_filter() -> None:
    """Inert proof: adding the margin gate in enforce mode with an absent
    snapshot yields the SAME layer verdict as not having the filter at all."""
    from shared.risk.layer import RiskFilterLayer

    signal = _make_signal(generated_at=_IN_WINDOW_KST)

    baseline = RiskFilterLayer.from_config(
        _futures_cfg(enabled=False),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    with_gate = RiskFilterLayer.from_config(
        _futures_cfg(enabled=True, mode="enforce"),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        margin_snapshot_provider=lambda: None,  # dormant publisher
    )

    r_base = baseline.evaluate(signal, _snap())
    r_gate = with_gate.evaluate(signal, _snap())

    assert r_base.passed == r_gate.passed is True
    assert r_base.size_multiplier == r_gate.size_multiplier
    # The gate is present-but-inert: baseline has no margin_gate outcome, the
    # with-gate layer has exactly one, and it passed.
    base_names = [o.filter_name for o in r_base.filter_outcomes]
    gate_outcomes = [
        o for o in r_gate.filter_outcomes if o.filter_name == "margin_gate"
    ]
    assert "margin_gate" not in base_names
    assert len(gate_outcomes) == 1 and gate_outcomes[0].passed is True
