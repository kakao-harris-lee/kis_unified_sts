"""Unit tests for the LeverageFilter snapshot provider factory (P5-3).

``build_leverage_snapshot_provider`` combines an injected open-position source
and an equity source into the ``{positions, equity_krw}`` mapping that
:class:`shared.risk.filters.leverage.LeverageFilter` consumes. It is fail-open by
construction — a ``None`` equity or ANY raised read returns ``None`` (the filter
treats ``None`` as "no snapshot" -> pass) and the returned callable never raises
into the guardless daemon evaluate path.

The final block wires a factory-built provider into a real LeverageFilter to
prove the computation path actually runs end-to-end (enforce blocks over the cap;
shadow computes but always passes — the state this PR ships in).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from shared.decision.signal import Signal
from shared.risk.filters.leverage import SKIP_LEVERAGE, LeverageFilter
from shared.risk.futures_margin import MarginProductSpec
from shared.risk.leverage_provider import build_leverage_snapshot_provider
from shared.risk.state import RiskStateSnapshot

_SYMBOL = "A05603"
_NOW = datetime(2026, 7, 10, 10, 0, 0)


def _pos(code: str = _SYMBOL, quantity: float = 1, price: float = 100_000.0) -> dict:
    return {"code": code, "quantity": quantity, "current_price": price}


def _signal(symbol: str = _SYMBOL) -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol=symbol,
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


# ---------------------------------------------------------------------------
# (a) Positions + equity present -> normalized {positions, equity_krw}
# ---------------------------------------------------------------------------


def test_combines_positions_and_equity() -> None:
    positions = [_pos(quantity=2), _pos(code="105V3000", quantity=3)]
    provider = build_leverage_snapshot_provider(
        positions_provider=lambda: positions,
        equity_provider=lambda: 1_000_000.0,
    )
    snap = provider()
    assert snap is not None
    assert snap["equity_krw"] == 1_000_000.0
    # A fresh list copy is returned (list(...)), carrying the injected legs.
    assert list(snap["positions"]) == positions


def test_empty_book_still_returns_snapshot() -> None:
    """An empty position book is a valid (zero-leverage) snapshot, not None."""
    provider = build_leverage_snapshot_provider(
        positions_provider=list,
        equity_provider=lambda: 5_000_000.0,
    )
    snap = provider()
    assert snap == {"positions": [], "equity_krw": 5_000_000.0}


# ---------------------------------------------------------------------------
# (b) Missing/failed source -> None (fail-open)
# ---------------------------------------------------------------------------


def test_none_equity_fails_open() -> None:
    calls = {"positions": 0}

    def _positions() -> list:
        calls["positions"] += 1
        return [_pos()]

    provider = build_leverage_snapshot_provider(
        positions_provider=_positions,
        equity_provider=lambda: None,
    )
    assert provider() is None
    # Equity is read first; a None equity short-circuits before the positions read.
    assert calls["positions"] == 0


def test_positions_read_error_fails_open() -> None:
    def _boom() -> list:
        raise RuntimeError("redis down")

    provider = build_leverage_snapshot_provider(
        positions_provider=_boom,
        equity_provider=lambda: 1_000_000.0,
    )
    assert provider() is None


def test_equity_read_error_fails_open() -> None:
    def _boom() -> float:
        raise RuntimeError("equity source down")

    provider = build_leverage_snapshot_provider(
        positions_provider=lambda: [_pos()],
        equity_provider=_boom,
    )
    assert provider() is None


# ---------------------------------------------------------------------------
# (c) Provider never raises into the daemon
# ---------------------------------------------------------------------------


def test_provider_never_raises() -> None:
    def _boom() -> list:
        raise ValueError("corrupt")

    provider = build_leverage_snapshot_provider(
        positions_provider=_boom,
        equity_provider=_boom,
    )
    # Must swallow the error and return None rather than propagate.
    try:
        result = provider()
    except Exception as exc:  # pragma: no cover — a raise here is the failure
        pytest.fail(f"provider raised instead of failing open: {exc!r}")
    assert result is None


# ---------------------------------------------------------------------------
# (d) End-to-end: a factory-built provider drives real gross-leverage compute
# ---------------------------------------------------------------------------


def _leverage_filter(*, mode: str, provider, product_specs=None) -> LeverageFilter:
    return LeverageFilter(
        mode=mode,
        max_gross_leverage=3.0,
        snapshot_provider=provider,
        product_specs=product_specs,
        now_provider=lambda: _NOW,
    )


def test_enforce_blocks_when_over_cap_via_factory_provider() -> None:
    """Stock-style wiring (product_specs=None -> multiplier 1): 5 * 100k = 500k
    notional on 100k equity = 5.0x > 3.0 cap -> reject in enforce mode."""
    provider = build_leverage_snapshot_provider(
        positions_provider=lambda: [_pos(quantity=5, price=100_000.0)],
        equity_provider=lambda: 100_000.0,
    )
    f = _leverage_filter(mode="enforce", provider=provider)
    result = f.check(_signal(), RiskStateSnapshot())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_shadow_computes_but_passes_over_cap() -> None:
    """The state this PR ships in: provider wired + filter built, but mode=shadow
    -> the same over-cap book that enforce blocks still PASSES (observation-only).
    Proves wiring a provider does not change trading behaviour under shadow."""
    provider = build_leverage_snapshot_provider(
        positions_provider=lambda: [_pos(quantity=5, price=100_000.0)],
        equity_provider=lambda: 100_000.0,
    )
    f = _leverage_filter(mode="shadow", provider=provider)
    result = f.check(_signal(), RiskStateSnapshot())
    assert result.passed is True
    assert result.skip_reason is None


def test_enforce_passes_at_or_under_cap_via_factory_provider() -> None:
    """3 * 100k = 300k on 100k equity = exactly 3.0x == cap -> passes (strict >)."""
    provider = build_leverage_snapshot_provider(
        positions_provider=lambda: [_pos(quantity=3, price=100_000.0)],
        equity_provider=lambda: 100_000.0,
    )
    f = _leverage_filter(mode="enforce", provider=provider)
    result = f.check(_signal(), RiskStateSnapshot())
    assert result.passed is True


def test_enforce_uses_futures_multiplier_from_product_specs() -> None:
    """Futures-style wiring: the per-contract multiplier (250k/pt) is applied,
    so even 1 contract at price 100 = 1 * 100 * 250k = 25M on 10M equity = 2.5x
    (under the 3.0 cap -> pass), proving product_specs feed the compute path."""
    spec = MarginProductSpec(
        multiplier_krw_per_point=250_000.0,
        tick_size_points=0.05,
        initial_margin_rate=0.1,
        maintenance_margin_rate=0.075,
        stress_gap_points=5.0,
        symbol_prefixes=("A05", "101"),
    )
    provider = build_leverage_snapshot_provider(
        positions_provider=lambda: [_pos(quantity=1, price=100.0)],
        equity_provider=lambda: 10_000_000.0,
    )
    f = _leverage_filter(
        mode="enforce", provider=provider, product_specs={"kospi200": spec}
    )
    assert f.check(_signal(), RiskStateSnapshot()).passed is True

    # Same book on a thinner equity (5M) -> 25M / 5M = 5.0x > 3.0 -> reject.
    provider_thin = build_leverage_snapshot_provider(
        positions_provider=lambda: [_pos(quantity=1, price=100.0)],
        equity_provider=lambda: 5_000_000.0,
    )
    f_thin = _leverage_filter(
        mode="enforce", provider=provider_thin, product_specs={"kospi200": spec}
    )
    blocked = f_thin.check(_signal(), RiskStateSnapshot())
    assert blocked.passed is False
    assert blocked.skip_reason == SKIP_LEVERAGE
