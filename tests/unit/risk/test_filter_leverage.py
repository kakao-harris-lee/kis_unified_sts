# tests/unit/risk/test_filter_leverage.py
"""Unit tests for LeverageFilter (Phase 4-g).

The filter introduces the repo's first leverage constraint: it computes
``gross_leverage = Σ|quantity · price · multiplier| / equity`` from an injected
position+equity snapshot and rejects new entries above ``max_gross_leverage`` in
``enforce`` mode. It is fail-open by construction (no provider / no cap / mode !=
enforce / equity <= 0 / corrupt snapshot → pass) and side-agnostic — taking the
absolute notional preserves long/short symmetry for free. Applies to both assets
(futures resolve per-contract multipliers via ``spec_for_symbol``; stock use 1).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shared.decision.signal import Signal
from shared.risk.config import LeverageFilterSettings
from shared.risk.filters.leverage import SKIP_LEVERAGE, LeverageFilter
from shared.risk.futures_margin import MarginProductSpec
from shared.risk.state import RiskStateSnapshot

_SYMBOL = "A05603"
#: Deterministic KST-naive clock used as the filter's ``now_provider`` and the
#: base for building snapshot ``asof_ts`` timestamps.
_NOW = datetime(2026, 7, 10, 10, 0, 0)
#: Aware KST timestamp inside the ``09:00-10:30`` window so the from_config chain
#: tests never get rejected by TradingHoursFilter (filter #1).
_IN_WINDOW_KST = datetime(2026, 7, 10, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))

#: A KOSPI200-futures-like spec (multiplier 250,000 KRW/pt) whose prefix matches
#: ``_SYMBOL`` so ``spec_for_symbol`` resolves it. Proves the multiplier is
#: reused from the margin SoT rather than hardcoded.
_FUT_SPEC = MarginProductSpec(
    multiplier_krw_per_point=250_000.0,
    tick_size_points=0.05,
    initial_margin_rate=0.1,
    maintenance_margin_rate=0.075,
    stress_gap_points=5.0,
    symbol_prefixes=("A05", "101"),
)
_PRODUCT_SPECS = {"kospi200": _FUT_SPEC}


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


def _pos(code: str = _SYMBOL, quantity: float = 1, price: float = 100_000.0) -> dict:
    return {"code": code, "quantity": quantity, "current_price": price}


def _snapshot(
    *,
    positions: Sequence | None = None,
    equity: float | str = 1_000_000.0,
    asof: datetime | None = None,
) -> dict:
    snap: dict = {"equity_krw": equity}
    if positions is not None:
        snap["positions"] = positions
    if asof is not None:
        snap["asof_ts"] = asof.isoformat()
    return snap


def _filter(
    *,
    mode: str = "enforce",
    max_gross_leverage: float | None = 3.0,
    provider=None,
    product_specs: Mapping[str, MarginProductSpec] | None = None,
    stale_max_age_seconds: int | None = None,
) -> LeverageFilter:
    return LeverageFilter(
        mode=mode,
        max_gross_leverage=max_gross_leverage,
        snapshot_provider=provider,
        product_specs=product_specs,
        stale_max_age_seconds=stale_max_age_seconds,
        now_provider=lambda: _NOW,
    )


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_filter_name() -> None:
    assert _filter().name == "leverage"


# ---------------------------------------------------------------------------
# (a) No provider injected → fail-open pass (structurally inert)
# ---------------------------------------------------------------------------


def test_no_provider_passes() -> None:
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=None)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# (b) No cap configured → pass, provider never consulted
# ---------------------------------------------------------------------------


def test_no_cap_passes_without_consulting_provider() -> None:
    calls = {"n": 0}

    def provider() -> Mapping[str, object]:
        calls["n"] += 1
        return _snapshot(positions=[_pos(quantity=1000)], equity=1.0)

    f = _filter(mode="enforce", max_gross_leverage=None, provider=provider)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert calls["n"] == 0  # short-circuit before any read


# ---------------------------------------------------------------------------
# (c) equity <= 0 → fail-open pass (0-division guard)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("equity", [0, 0.0, -100.0, "0", ""])
def test_nonpositive_equity_fails_open(equity) -> None:
    # A book that would be wildly over-leveraged, but equity <= 0 → pass.
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: _snapshot(positions=[_pos(quantity=1000)], equity=equity),
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# (d) Corrupt / non-mapping / malformed → fail-open pass (inside the guard)
# ---------------------------------------------------------------------------


def test_provider_exception_fails_open() -> None:
    def boom() -> Mapping[str, object]:
        raise RuntimeError("redis down")

    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=boom)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


@pytest.mark.parametrize("bad_return", [[1, 2, 3], "not-a-mapping", 42, (1, 2)])
def test_provider_non_mapping_fails_open(bad_return: object) -> None:
    """A non-Mapping return must fail OPEN via the isinstance guard — a bare
    ``.get()`` would raise AttributeError, escaping into the guardless
    layer/daemon path (fail-CLOSED)."""
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: bad_return)  # type: ignore[return-value]
    assert f.check(_make_signal(), _snap()).passed is True


@pytest.mark.parametrize("bad_positions", [42, "abc", {"code": "x"}, object()])
def test_positions_non_sequence_fails_open(bad_positions: object) -> None:
    """positions that isn't a list/tuple (mapping, str, scalar) → fail open."""
    f = _filter(
        mode="enforce",
        max_gross_leverage=0.001,
        provider=lambda: {"equity_krw": 1_000_000.0, "positions": bad_positions},
    )
    assert f.check(_make_signal(), _snap()).passed is True


@pytest.mark.parametrize(
    "bad_leg",
    [
        {"code": "A05603", "quantity": "abc", "current_price": 100_000.0},  # bad qty
        {"code": "A05603", "quantity": 10},  # missing price
        {"code": "A05603", "current_price": 100_000.0},  # missing qty
        {"code": "A05603", "quantity": float("nan"), "current_price": 100_000.0},
        42,  # non-mapping leg
    ],
)
def test_malformed_leg_fails_open(bad_leg: object) -> None:
    """A malformed leg would silently under-count notional; the filter fails
    open on the whole snapshot instead of understating leverage."""
    f = _filter(
        mode="enforce",
        max_gross_leverage=0.001,
        provider=lambda: _snapshot(positions=[bad_leg], equity=1_000_000.0),
    )
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (e) mode != enforce → pass (snapshot never even consulted)
# ---------------------------------------------------------------------------


def test_shadow_mode_passes_without_consulting_snapshot() -> None:
    calls = {"n": 0}

    def provider() -> Mapping[str, object]:
        calls["n"] += 1
        return _snapshot(positions=[_pos(quantity=1000)], equity=1.0)

    f = _filter(mode="shadow", max_gross_leverage=1.0, provider=provider)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert calls["n"] == 0  # short-circuit before any read


@pytest.mark.parametrize("mode", ["shadow", "off", "", "ENFORCE_TYPO"])
def test_non_enforce_modes_pass(mode: str) -> None:
    f = _filter(
        mode=mode,
        max_gross_leverage=1.0,
        provider=lambda: _snapshot(positions=[_pos(quantity=1000)], equity=1.0),
    )
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (f) gross > cap + enforce → reject
# ---------------------------------------------------------------------------


def test_over_cap_enforce_rejects() -> None:
    # notional = 11 * 100_000 * 1 = 1_100_000; equity 1_000_000 → 1.1 > cap 1.0.
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=11, price=100_000.0)], equity=1_000_000.0
        ),
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE
    assert result.filter_name == "leverage"


# ---------------------------------------------------------------------------
# (g) gross <= cap + enforce → pass
# ---------------------------------------------------------------------------


def test_under_cap_enforce_passes() -> None:
    # notional = 5 * 100_000 = 500_000; equity 1_000_000 → 0.5 < cap 1.0.
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=5, price=100_000.0)], equity=1_000_000.0
        ),
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


def test_empty_book_passes() -> None:
    # No positions key at all → 0 notional → 0 leverage → pass.
    f = _filter(
        mode="enforce", max_gross_leverage=1.0, provider=lambda: {"equity_krw": 500.0}
    )
    assert f.check(_make_signal(), _snap()).passed is True
    # Explicit empty list → also 0 leverage.
    f2 = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: _snapshot(positions=[], equity=500.0),
    )
    assert f2.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (h) long/short symmetry — identical |notional| ⇒ identical verdict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "equity,expected_pass", [(500_000.0, False), (2_000_000.0, True)]
)
def test_long_short_symmetry(equity: float, expected_pass: bool) -> None:
    """A long and an equal-size short net to the same gross notional, so the
    verdict is direction-independent (gross uses ``abs`` — never reads side).

    equity 500k → gross 2.0 > cap 1.0 → both reject; equity 2M → gross 0.5 → both
    pass. The filter must return the SAME verdict for +10 and -10 quantity.
    """
    long_snap = _snapshot(positions=[_pos(quantity=10, price=100_000.0)], equity=equity)
    short_snap = _snapshot(
        positions=[_pos(quantity=-10, price=100_000.0)], equity=equity
    )
    f_long = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: long_snap)
    f_short = _filter(
        mode="enforce", max_gross_leverage=1.0, provider=lambda: short_snap
    )
    r_long = f_long.check(_make_signal(), _snap())
    r_short = f_short.check(_make_signal(), _snap())
    assert r_long.passed == r_short.passed == expected_pass
    assert r_long.skip_reason == r_short.skip_reason


def test_short_encoded_as_positive_qty_plus_side_symmetric() -> None:
    """A short encoded as positive magnitude (side field, ignored) yields the
    same |notional| as a long — proving the filter never depends on side."""
    long_snap = _snapshot(positions=[_pos(quantity=10)], equity=500_000.0)
    short_snap = _snapshot(
        positions=[
            {
                "code": _SYMBOL,
                "quantity": 10,
                "current_price": 100_000.0,
                "side": "short",
            }
        ],
        equity=500_000.0,
    )
    f_l = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: long_snap)
    f_s = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: short_snap)
    assert (
        f_l.check(_make_signal(), _snap()).passed
        == f_s.check(_make_signal(), _snap()).passed
        is False
    )


# ---------------------------------------------------------------------------
# (i) multiplier reuse — futures spec multiplier vs stock (no specs → 1)
# ---------------------------------------------------------------------------


def test_futures_multiplier_from_spec_rejects() -> None:
    # With the KOSPI200 spec (mult 250_000): notional = 1 * 360 * 250_000 = 90M;
    # equity 1M → gross 90.0 > cap 3.0 → reject. The 250_000 comes from the
    # margin SoT spec, not a hardcoded literal.
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=1, price=360.0)], equity=1_000_000.0
        ),
        product_specs=_PRODUCT_SPECS,
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_stock_no_specs_multiplier_one_passes() -> None:
    # SAME position, but product_specs=None → multiplier 1: notional = 360;
    # equity 1M → gross 0.00036 < cap 3.0 → pass. Proves stock uses multiplier 1.
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=1, price=360.0)], equity=1_000_000.0
        ),
        product_specs=None,
    )
    assert f.check(_make_signal(), _snap()).passed is True


def test_unresolved_futures_symbol_understates_leverage_fails_open() -> None:
    # A symbol not matching any spec prefix → multiplier 1 fallback (understates
    # notional). With specs present but symbol "ZZZ999" unresolved: notional =
    # 1*360*1 = 360 → gross tiny → pass (fail-open-safe, never over-rejects).
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(code="ZZZ999", quantity=1, price=360.0)],
            equity=1_000_000.0,
        ),
        product_specs=_PRODUCT_SPECS,
    )
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (F1) equity key alias — equity_krw and canonical account_equity_krw accepted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("equity_key", ["equity_krw", "account_equity_krw"])
def test_equity_key_alias_over_cap_rejects(equity_key: str) -> None:
    """The canonical futures margin read-model publishes equity as
    ``account_equity_krw`` (futures_margin.margin_state_to_fields), while this
    filter's own key is ``equity_krw``. Both must drive the SAME verdict so a
    follow-up reusing the margin snapshot as the provider is not silently inert
    (review F1). Here gross 1.1 > cap 1.0 → reject under either key."""
    snap = {
        equity_key: 1_000_000.0,
        "positions": [_pos(quantity=11, price=100_000.0)],
    }
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: snap)
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


@pytest.mark.parametrize("equity_key", ["equity_krw", "account_equity_krw"])
def test_equity_key_alias_under_cap_passes(equity_key: str) -> None:
    # gross 0.5 < cap 1.0 → pass under either equity key.
    snap = {
        equity_key: 1_000_000.0,
        "positions": [_pos(quantity=5, price=100_000.0)],
    }
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: snap)
    assert f.check(_make_signal(), _snap()).passed is True


def test_equity_prefers_equity_krw_over_alias() -> None:
    """When BOTH keys are present, ``equity_krw`` wins — the alias is only a
    fallback for a missing/None primary. equity_krw 1M → gross 1.1 > cap → reject;
    the huge account_equity_krw would PASS if it were consulted."""
    snap = {
        "equity_krw": 1_000_000.0,
        "account_equity_krw": 1_000_000_000.0,
        "positions": [_pos(quantity=11, price=100_000.0)],
    }
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: snap)
    assert f.check(_make_signal(), _snap()).passed is False


def test_neither_equity_key_present_fails_open() -> None:
    """No equity under EITHER key → missing denominator → fail-open pass, even
    for a book that would be wildly over-leveraged."""
    snap = {"positions": [_pos(quantity=1000, price=100_000.0)]}
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: snap)
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# (F2) unresolved futures multiplier — 1.0 fallback stays safe but is OBSERVABLE
# ---------------------------------------------------------------------------


def test_unresolved_symbol_warns_once_throttled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """product_specs supplied but the symbol resolves no spec → 1.0 fallback
    (fail-open-safe) AND a throttled one-warning-per-symbol logger.warning, so
    the leverage under-count is observable (mirrors the margin read-model's
    degraded/missing_components convention, memory #601). Repeated evaluations
    of the same symbol emit the warning exactly ONCE (hot-path throttle)."""
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(code="ZZZ999", quantity=1, price=360.0)],
            equity=1_000_000.0,
        ),
        product_specs=_PRODUCT_SPECS,
    )
    with caplog.at_level(logging.WARNING, logger="shared.risk.filters.leverage"):
        for _ in range(3):
            assert f.check(_make_signal(), _snap()).passed is True
    warns = [r for r in caplog.records if "no futures product spec" in r.getMessage()]
    assert len(warns) == 1
    assert "ZZZ999" in warns[0].getMessage()


def test_resolved_symbol_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """A symbol that DOES resolve a spec must not emit the unresolved warning."""
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=1, price=360.0)], equity=1_000_000.0
        ),
        product_specs=_PRODUCT_SPECS,
    )
    with caplog.at_level(logging.WARNING, logger="shared.risk.filters.leverage"):
        f.check(_make_signal(), _snap())
    assert not [
        r for r in caplog.records if "no futures product spec" in r.getMessage()
    ]


def test_stock_chain_no_specs_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """product_specs=None (stock/cash chain) → multiplier 1.0 is the CORRECT
    value, not a degraded fallback → NO warning, even though nothing resolves."""
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(code="005930", quantity=1, price=360.0)],
            equity=1_000_000.0,
        ),
        product_specs=None,
    )
    with caplog.at_level(logging.WARNING, logger="shared.risk.filters.leverage"):
        f.check(_make_signal(), _snap())
    assert not [
        r for r in caplog.records if "no futures product spec" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# (F5) hedge book — gross is a SUM of |notional|, never a self-cancelling NET
# ---------------------------------------------------------------------------


def test_hedge_book_gross_not_net_rejects() -> None:
    """A fully-hedged book (same symbol long +N AND short −N in ONE snapshot) has
    NET quantity 0 but GROSS |N|+|N|. The filter sums absolute notionals, so a
    high-leverage hedge book still breaches the cap and rejects — a NET
    calculation would cancel to 0 and never fire. Regression guard for ``abs``
    removal in ``_gross_notional``."""
    # +6 and -6 @ 100k, mult 1: gross = (|6|+|6|) * 100_000 = 1.2M; NET would be 0.
    # equity 1M → gross leverage 1.2 > cap 1.0 → reject.
    hedge_snap = _snapshot(
        positions=[
            _pos(quantity=6, price=100_000.0),
            _pos(quantity=-6, price=100_000.0),
        ],
        equity=1_000_000.0,
    )
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: hedge_snap)
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_small_hedge_book_under_cap_passes() -> None:
    """Contrast to bound the reject to hedge MAGNITUDE, not the mere presence of
    a short: the same two-legged shape at low notional (gross 0.4) passes — the
    reject above is driven by gross size, and a short never auto-rejects."""
    small_hedge = _snapshot(
        positions=[
            _pos(quantity=2, price=100_000.0),
            _pos(quantity=-2, price=100_000.0),
        ],
        equity=1_000_000.0,
    )  # gross = (|2|+|2|) * 100_000 = 400_000 → 0.4 < cap 1.0 → pass
    f = _filter(mode="enforce", max_gross_leverage=1.0, provider=lambda: small_hedge)
    assert f.check(_make_signal(), _snap()).passed is True


# ---------------------------------------------------------------------------
# (j) boundary — exactly at cap passes, just above rejects (strict '>')
# ---------------------------------------------------------------------------


def test_leverage_exactly_at_cap_passes() -> None:
    # notional = 3 * 1_000_000 = 3_000_000; equity 1_000_000 → gross 3.0 == cap.
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=3, price=1_000_000.0)], equity=1_000_000.0
        ),
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is True
    assert result.skip_reason is None


def test_leverage_just_above_cap_rejects() -> None:
    # notional = 3 * 1_000_001 = 3_000_003; equity 1_000_000 → gross 3.000003 > 3.0.
    f = _filter(
        mode="enforce",
        max_gross_leverage=3.0,
        provider=lambda: _snapshot(
            positions=[_pos(quantity=3, price=1_000_001.0)], equity=1_000_000.0
        ),
    )
    result = f.check(_make_signal(), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


# ---------------------------------------------------------------------------
# Staleness (positive-form, #458) — only when stale_max_age_seconds configured
# ---------------------------------------------------------------------------


def test_stale_snapshot_fails_open() -> None:
    # 1s past the 600s bound → stale → pass, even though gross 11.0 >> cap.
    stale = _snapshot(
        positions=[_pos(quantity=11)],
        equity=100_000.0,
        asof=_NOW - timedelta(seconds=601),
    )
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: stale,
        stale_max_age_seconds=600,
    )
    assert f.check(_make_signal(), _snap()).passed is True


def test_fresh_within_bound_still_enforces() -> None:
    fresh = _snapshot(
        positions=[_pos(quantity=11)],
        equity=100_000.0,
        asof=_NOW - timedelta(seconds=599),
    )
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: fresh,
        stale_max_age_seconds=600,
    )
    assert f.check(_make_signal(), _snap()).passed is False


@pytest.mark.parametrize("asof_field", [None, "not-a-timestamp"])
def test_missing_or_unparseable_timestamp_treated_stale(asof_field) -> None:
    snap = {
        "positions": [_pos(quantity=11)],
        "equity_krw": 100_000.0,
    }
    if asof_field is not None:
        snap["asof_ts"] = asof_field
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: snap,
        stale_max_age_seconds=600,
    )
    assert f.check(_make_signal(), _snap()).passed is True


def test_no_stale_gate_ignores_timestamp() -> None:
    # stale_max_age_seconds=None → staleness never checked; an ancient asof still
    # enforces (the snapshot is trusted current by contract).
    ancient = _snapshot(
        positions=[_pos(quantity=11)],
        equity=100_000.0,
        asof=_NOW - timedelta(days=30),
    )
    f = _filter(
        mode="enforce",
        max_gross_leverage=1.0,
        provider=lambda: ancient,
        stale_max_age_seconds=None,
    )
    assert f.check(_make_signal(), _snap()).passed is False


# ---------------------------------------------------------------------------
# Settings — defaults keep the filter structurally inert
# ---------------------------------------------------------------------------


def test_settings_defaults_disabled_and_shadow() -> None:
    s = LeverageFilterSettings()
    assert s.enabled is False
    assert s.mode == "shadow"
    assert s.max_gross_leverage is None
    assert s.stale_max_age_seconds is None


def test_settings_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        LeverageFilterSettings(mode="live")  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0, -1.0, 0.0])
def test_settings_reject_non_positive_cap(bad: float) -> None:
    with pytest.raises(ValueError):
        LeverageFilterSettings(max_gross_leverage=bad)


# ---------------------------------------------------------------------------
# from_config wiring — both assets, inert no-op equivalence
# ---------------------------------------------------------------------------


def _cfg(asset: str = "futures", *, enabled: bool, mode: str = "enforce", cap=3.0):
    from shared.risk.config import FuturesRiskConfig, StockRiskConfig

    cfg = FuturesRiskConfig() if asset == "futures" else StockRiskConfig()
    cfg.leverage.enabled = enabled
    cfg.leverage.mode = mode  # type: ignore[assignment]
    cfg.leverage.max_gross_leverage = cap
    return cfg


def test_from_config_disabled_does_not_build_filter() -> None:
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _cfg(enabled=False),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    assert "leverage" not in [f.name for f in layer._filters]


def test_from_config_builds_for_both_assets() -> None:
    from shared.risk.layer import RiskFilterLayer

    futures = RiskFilterLayer.from_config(
        _cfg("futures", enabled=True, mode="shadow"),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    stock = RiskFilterLayer.from_config(
        _cfg("stock", enabled=True, mode="shadow"),
        trading_windows=["09:00-15:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    assert "leverage" in [f.name for f in futures._filters]
    assert "leverage" in [f.name for f in stock._filters]


def test_from_config_stock_leverage_precedes_core_correlation() -> None:
    """Stock core_correlation filters must stay LAST; leverage sits before them."""
    from shared.risk.filters.core_correlation import (
        CoreSectorCapFilter,
        TrackAOverlapFilter,
    )
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _cfg("stock", enabled=True, mode="shadow"),
        trading_windows=["09:00-15:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    names = [f.name for f in layer._filters]
    assert names.index("leverage") < names.index(TrackAOverlapFilter.name)
    assert isinstance(layer._filters[-1], CoreSectorCapFilter)


def test_from_config_shadow_builds_but_passes() -> None:
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _cfg("futures", enabled=True, mode="shadow", cap=1.0),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        # A wildly over-leveraged snapshot that WOULD reject in enforce.
        leverage_snapshot_provider=lambda: _snapshot(
            positions=[_pos(quantity=1000)], equity=1.0
        ),
    )
    assert "leverage" in [f.name for f in layer._filters]
    result = layer.evaluate(_make_signal(generated_at=_IN_WINDOW_KST), _snap())
    assert result.passed is True


def test_from_config_enforce_chain_rejects_on_breach() -> None:
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _cfg("futures", enabled=True, mode="enforce", cap=3.0),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        # notional 11*100_000 = 1.1M; equity 100k → gross 11.0 > cap 3.0.
        leverage_snapshot_provider=lambda: _snapshot(
            positions=[_pos(quantity=11, price=100_000.0)], equity=100_000.0
        ),
    )
    result = layer.evaluate(_make_signal(generated_at=_IN_WINDOW_KST), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_from_config_futures_product_specs_wired() -> None:
    """leverage_product_specs must reach the filter so the futures multiplier
    applies through the chain (understates without it)."""
    from shared.risk.layer import RiskFilterLayer

    layer = RiskFilterLayer.from_config(
        _cfg("futures", enabled=True, mode="enforce", cap=3.0),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        leverage_product_specs=_PRODUCT_SPECS,
        # notional 1*360*250_000 = 90M; equity 1M → gross 90.0 > cap 3.0.
        leverage_snapshot_provider=lambda: _snapshot(
            positions=[_pos(quantity=1, price=360.0)], equity=1_000_000.0
        ),
    )
    result = layer.evaluate(_make_signal(generated_at=_IN_WINDOW_KST), _snap())
    assert result.passed is False
    assert result.skip_reason == SKIP_LEVERAGE


def test_from_config_enforce_no_provider_equivalent_to_no_filter() -> None:
    """Inert proof: adding the leverage filter in enforce mode with NO snapshot
    provider yields the SAME layer verdict as not having the filter at all."""
    from shared.risk.layer import RiskFilterLayer

    signal = _make_signal(generated_at=_IN_WINDOW_KST)

    baseline = RiskFilterLayer.from_config(
        _cfg(enabled=False),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
    )
    with_filter = RiskFilterLayer.from_config(
        _cfg(enabled=True, mode="enforce"),
        trading_windows=["09:00-10:30"],
        portfolio_snapshot_provider=lambda: None,
        leverage_snapshot_provider=None,  # unwired → inert
    )

    r_base = baseline.evaluate(signal, _snap())
    r_with = with_filter.evaluate(signal, _snap())

    assert r_base.passed == r_with.passed is True
    assert r_base.skip_reason == r_with.skip_reason
    assert r_base.size_multiplier == r_with.size_multiplier
    # Present-but-inert: baseline has no leverage outcome, the with-filter layer
    # has exactly one, and it passed.
    assert "leverage" not in [o.filter_name for o in r_base.filter_outcomes]
    lev = [o for o in r_with.filter_outcomes if o.filter_name == "leverage"]
    assert len(lev) == 1 and lev[0].passed is True
