"""Enforce-flip integration tests — operator flip 2026-07-12 (shadow→enforce).

Proves the shipped ``config/risk.yaml`` ``margin_gate`` + ``leverage`` flip does
exactly what the operator intended: a *real* threshold violation REJECTS a new
entry, while missing / stale / no-provider data still fails OPEN so paper signals
are never spuriously blocked.

These complement the config-load pins in ``test_risk_config`` /
``test_stock_risk_config`` (which assert the YAML values) by exercising the
fully-wired :class:`RiskFilterLayer` built from the **shipped** config with
snapshot providers injected in place of live Redis — so the assertions are on the
real filter chain, not a synthetic config.

Time-robustness: the layer is built with a 24h ``trading_windows`` so the
``TradingHoursFilter`` never short-circuits (avoiding the afternoon-red trap,
memory #437); the ``margin_gate`` / ``leverage`` filters still come from the
shipped config. ``portfolio_snapshot_provider`` / ``core_holdings_provider`` /
``stock_positions_provider`` are stubbed to ``None`` to keep the build hermetic
(no real Redis / ledger file).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from shared.decision.signal import Signal
from shared.risk.config import FuturesRiskConfig, StockRiskConfig
from shared.risk.filters.leverage import SKIP_LEVERAGE
from shared.risk.futures_margin import MarginProductSpec
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot

_MarginProvider = Callable[[], Mapping[str, str] | None] | None
_LeverageProvider = Callable[[], Mapping[str, object] | None] | None
_ProductSpecs = Mapping[str, MarginProductSpec] | None

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
KST = ZoneInfo("Asia/Seoul")
_ALWAYS_OPEN = ["00:00-23:59"]


@pytest.fixture(autouse=True)
def _config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point ConfigLoader at the project config directory (shipped risk.yaml)."""
    monkeypatch.setenv("KIS_CONFIG_DIR", str(_PROJECT_ROOT / "config"))


def _signal() -> Signal:
    now = datetime.now(UTC)
    return Signal(
        setup_type="A_gap_reversion",
        direction="long",
        symbol="A05603",
        entry_price=350.0,
        stop_loss=349.0,
        take_profit=352.0,
        confidence=0.7,
        reason_tags=["test"],
        valid_until=now + timedelta(minutes=10),
        generated_at=now,
    )


def _fresh_asof() -> str:
    """KST-naive ISO timestamp 'now' (fresh for the margin gate staleness gate)."""
    return datetime.now(KST).replace(tzinfo=None).isoformat()


def _stale_asof() -> str:
    """KST-naive ISO timestamp older than stale_max_age_seconds (600s)."""
    return (
        datetime.now(KST).replace(tzinfo=None) - timedelta(seconds=2000)
    ).isoformat()


def _margin_snapshot(*, risk_level: str, asof: str) -> dict[str, str]:
    return {"risk_level": risk_level, "asof_ts": asof, "degraded": "false"}


def _futures_layer(
    *,
    margin_snapshot_provider: _MarginProvider = None,
    leverage_snapshot_provider: _LeverageProvider = None,
    leverage_product_specs: _ProductSpecs = None,
) -> RiskFilterLayer:
    return RiskFilterLayer.from_config(
        FuturesRiskConfig.from_yaml(),
        trading_windows=_ALWAYS_OPEN,
        portfolio_snapshot_provider=lambda: None,
        margin_snapshot_provider=margin_snapshot_provider,
        leverage_snapshot_provider=leverage_snapshot_provider,
        leverage_product_specs=leverage_product_specs,
    )


def _stock_layer(
    *, leverage_snapshot_provider: _LeverageProvider = None
) -> RiskFilterLayer:
    return RiskFilterLayer.from_config(
        StockRiskConfig.from_yaml(),
        trading_windows=_ALWAYS_OPEN,
        portfolio_snapshot_provider=lambda: None,
        core_holdings_provider=lambda: None,
        stock_positions_provider=lambda: None,
        leverage_snapshot_provider=leverage_snapshot_provider,
    )


# ---------------------------------------------------------------------------
# Shipped chain actually contains the enforce filters
# ---------------------------------------------------------------------------


def test_shipped_futures_chain_builds_margin_gate_and_leverage() -> None:
    names = [f.name for f in _futures_layer()._filters]
    assert "margin_gate" in names
    assert "leverage" in names


def test_shipped_stock_chain_builds_leverage_but_not_margin_gate() -> None:
    """Leverage applies to both assets; margin_gate is futures-only even though
    StockRiskConfig inherits the (default-shadow) margin_gate block."""
    names = [f.name for f in _stock_layer()._filters]
    assert "leverage" in names
    assert "margin_gate" not in names


# ---------------------------------------------------------------------------
# margin_gate enforce — real block levels REJECT, everything else PASSES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("risk_level", ["critical", "block_new_entries"])
def test_margin_gate_enforce_rejects_blocking_level(risk_level: str) -> None:
    layer = _futures_layer(
        margin_snapshot_provider=lambda: _margin_snapshot(
            risk_level=risk_level, asof=_fresh_asof()
        )
    )
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is False
    assert result.skip_reason == f"margin_gate_{risk_level}"


@pytest.mark.parametrize("risk_level", ["ok", "watch", "reduce_only"])
def test_margin_gate_enforce_passes_non_blocking_level(risk_level: str) -> None:
    layer = _futures_layer(
        margin_snapshot_provider=lambda: _margin_snapshot(
            risk_level=risk_level, asof=_fresh_asof()
        )
    )
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is True


def test_margin_gate_enforce_absent_snapshot_fails_open() -> None:
    """Dormant publisher / Redis miss → snapshot None → PASS (no spurious block)."""
    layer = _futures_layer(margin_snapshot_provider=lambda: None)
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is True


def test_margin_gate_enforce_stale_snapshot_fails_open() -> None:
    """A critical-but-stale snapshot must NOT block (positive-form staleness)."""
    layer = _futures_layer(
        margin_snapshot_provider=lambda: _margin_snapshot(
            risk_level="critical", asof=_stale_asof()
        )
    )
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is True


# ---------------------------------------------------------------------------
# leverage enforce — futures (cap 3.0). Over cap REJECTS; fail-open PASSES.
# ---------------------------------------------------------------------------


def test_futures_leverage_enforce_over_cap_rejects() -> None:
    """gross/equity = 30_000_000 / 5_000_000 = 6.0 > 3.0 → reject. (Multiplier 1.0
    via product_specs=None keeps the arithmetic explicit; per-contract multiplier
    resolution is covered in test_filter_leverage.)"""
    snapshot = {
        "positions": [{"code": "A05603", "quantity": 100, "current_price": 300000.0}],
        "equity_krw": 5_000_000.0,
    }
    layer = _futures_layer(
        margin_snapshot_provider=lambda: None,  # margin gate fails open → reach leverage
        leverage_snapshot_provider=lambda: snapshot,
    )
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_futures_leverage_enforce_under_cap_passes() -> None:
    snapshot = {
        "positions": [{"code": "A05603", "quantity": 10, "current_price": 300000.0}],
        "equity_krw": 5_000_000.0,  # 3_000_000 / 5_000_000 = 0.6 <= 3.0
    }
    layer = _futures_layer(
        margin_snapshot_provider=lambda: None,
        leverage_snapshot_provider=lambda: snapshot,
    )
    assert layer.evaluate(_signal(), RiskStateSnapshot()).passed is True


# ---------------------------------------------------------------------------
# leverage enforce — stock (cap 1.0). Over cap REJECTS; fail-open PASSES.
# ---------------------------------------------------------------------------


def test_stock_leverage_enforce_over_cap_rejects() -> None:
    """gross/equity = 21_300_000 / 10_000_000 = 2.13 > 1.0 → reject."""
    snapshot = {
        "positions": [{"code": "A005930", "quantity": 300, "current_price": 71000.0}],
        "equity_krw": 10_000_000.0,
    }
    layer = _stock_layer(leverage_snapshot_provider=lambda: snapshot)
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_stock_leverage_enforce_under_cap_passes() -> None:
    snapshot = {
        "positions": [{"code": "A005930", "quantity": 100, "current_price": 71000.0}],
        "equity_krw": 10_000_000.0,  # 7_100_000 / 10_000_000 = 0.71 <= 1.0
    }
    layer = _stock_layer(leverage_snapshot_provider=lambda: snapshot)
    assert layer.evaluate(_signal(), RiskStateSnapshot()).passed is True


# ---------------------------------------------------------------------------
# leverage enforce fail-open — no provider / empty book / equity<=0 all PASS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layer_factory", ["futures", "stock"])
def test_leverage_enforce_no_provider_fails_open(layer_factory: str) -> None:
    """enforce + NO snapshot provider wired → PASS (structurally inert)."""
    layer = (
        _futures_layer(margin_snapshot_provider=lambda: None)
        if layer_factory == "futures"
        else _stock_layer()
    )
    assert layer.evaluate(_signal(), RiskStateSnapshot()).passed is True


@pytest.mark.parametrize("layer_factory", ["futures", "stock"])
def test_leverage_enforce_empty_book_fails_open(layer_factory: str) -> None:
    snapshot = {"positions": [], "equity_krw": 5_000_000.0}
    layer = (
        _futures_layer(
            margin_snapshot_provider=lambda: None,
            leverage_snapshot_provider=lambda: snapshot,
        )
        if layer_factory == "futures"
        else _stock_layer(leverage_snapshot_provider=lambda: snapshot)
    )
    assert layer.evaluate(_signal(), RiskStateSnapshot()).passed is True


@pytest.mark.parametrize("layer_factory", ["futures", "stock"])
def test_leverage_enforce_nonpositive_equity_fails_open(layer_factory: str) -> None:
    """equity <= 0 → fail open (also the 0-division guard) even with a huge book."""
    snapshot = {
        "positions": [{"code": "A05603", "quantity": 100, "current_price": 300000.0}],
        "equity_krw": 0.0,
    }
    layer = (
        _futures_layer(
            margin_snapshot_provider=lambda: None,
            leverage_snapshot_provider=lambda: snapshot,
        )
        if layer_factory == "futures"
        else _stock_layer(leverage_snapshot_provider=lambda: snapshot)
    )
    assert layer.evaluate(_signal(), RiskStateSnapshot()).passed is True


# ---------------------------------------------------------------------------
# Spurious-block regression — enforce + total data absence must PASS (paper safe)
# ---------------------------------------------------------------------------


def test_futures_enforce_all_providers_absent_no_spurious_block() -> None:
    """The core paper-safety invariant: the SHIPPED enforce chain with every
    data source absent (dormant margin publisher + no leverage snapshot) still
    passes a clean signal — enabling enforce did NOT start blocking paper."""
    layer = _futures_layer(
        margin_snapshot_provider=lambda: None,
        leverage_snapshot_provider=None,
    )
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is True
    assert result.skip_reason is None


def test_stock_enforce_all_providers_absent_no_spurious_block() -> None:
    layer = _stock_layer(leverage_snapshot_provider=None)
    result = layer.evaluate(_signal(), RiskStateSnapshot())
    assert result.passed is True
    assert result.skip_reason is None
