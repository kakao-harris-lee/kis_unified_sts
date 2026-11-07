"""Regression guard: an unwired RiskFilterLayer provider must announce itself.

Why this file exists
--------------------
``RiskFilterLayer.from_config`` silently substitutes a no-op stub for three
providers when the caller omits them (``current_atr_provider`` -> ``0.0``,
``current_spread_provider`` -> ``0.0``, ``has_open_position_provider`` ->
``False``).  Two of those stubs merely make a filter inert; the third is
fail-**dangerous** - a stub reporting "no position held" for every symbol
disables the duplicate-entry guard rather than declining to add a filter.  The
futures daemon shipped in exactly that state without any test noticing.

What this file used to also do, and no longer can: it executed the **real**
``_build_and_run`` of each production daemon (``services/risk_filter``,
``services/stock_risk_filter``, ``services/decision_engine``,
``services/stock_strategy``) and captured the kwargs it passed, so that
dropping ``has_open_position_provider=...`` from a call site failed here.
Those daemons were removed with the legacy runtime
(``docs/plans/2026-11-07-legacy-removal-plan.md``, L2), so there is no
production call site left to pin and those tests went with them.  What remains
is the builder-side half: the stub substitution itself, and the warning that
announces it.  Whatever wires ``from_config`` next needs its own call-site
test - this file no longer provides one.
"""


from __future__ import annotations

import logging
from typing import Any

import pytest

from shared.risk.config import FuturesRiskConfig
from shared.risk.filters.open_position import OpenPositionFilter
from shared.risk.filters.spread import SpreadFilter
from shared.risk.filters.volatility import VolatilityFilter
from shared.risk.layer import RiskFilterLayer

#: Qualname prefix of every fallback stub defined inside ``from_config``.
#: This is the discriminator that separates "a real provider was injected"
#: from "the builder quietly substituted a no-op".
_STUB_QUALNAME_PREFIX = "RiskFilterLayer.from_config.<locals>"

_LAYER_LOGGER = "shared.risk.layer"

#: A representative KOSPI200 futures contract code (same one the order_router
#: tests use).  The exact value does not matter — what matters is that it
#: reaches the positions hash verbatim as the field name.
_FUTURES_SYMBOL = "A05603"
_STOCK_CODE = "005930"

#: Deliberately hardcoded rather than imported from the modules under test:
#: an independent anchor cannot drift in lockstep with the code it pins.
#: ``futures:monitor:positions`` is written by services/futures_monitor
#: (HSET field=symbol on entry, HDEL on exit) and already read back by
#: services/order_router's close path.  ``stock:daemon:positions`` is the M4
#: stock daemon working store.
_FUTURES_POSITIONS_KEY = "futures:monitor:positions"
_STOCK_POSITIONS_KEY = "stock:daemon:positions"

#: Same rule for the volatility reference hash: hardcoded here so a rename in
#: shared/risk/volatility_reference.py that misses one side is caught, rather
#: than both sides moving together into a silently inert filter.
_FUTURES_VOLATILITY_KEY = "risk:volatility:reference:futures"
_STOCK_VOLATILITY_KEY = "risk:volatility:reference:stock"


def _futures_cfg() -> FuturesRiskConfig:
    return FuturesRiskConfig(
        account_equity_krw=5_000_000,
        daily_mdd_limit_pct=0.03,
        weekly_mdd_limit_pct=0.07,
        max_position_risk_pct=0.015,
        max_daily_trades=3,
        max_position_size_contracts=2,
        consecutive_loss_soft_threshold=4,
        consecutive_loss_hard_threshold=6,
        max_spread_ticks=2,
    )


def _filter_of(layer: RiskFilterLayer, filter_type: type) -> Any:
    matches = [f for f in layer._filters if isinstance(f, filter_type)]
    assert len(matches) == 1, f"expected exactly one {filter_type.__name__}"
    return matches[0]


# ---------------------------------------------------------------------------
# Anchor: what an unwired provider actually looks like
# ---------------------------------------------------------------------------


def test_unwired_from_config_installs_silent_stubs() -> None:
    """Pin the defect being guarded: omitted providers become no-op stubs.

    This is the anchor the call-site tests below lean on — it proves the
    ``from_config.<locals>`` qualname really does identify a substituted stub,
    and it documents each stub's return value.
    """
    layer = RiskFilterLayer.from_config(_futures_cfg(), ["09:00-15:30"])

    spread = _filter_of(layer, SpreadFilter)._current_spread_provider
    open_pos = _filter_of(layer, OpenPositionFilter)._has_open_position_provider

    for label, provider in (("spread", spread), ("open", open_pos)):
        assert provider.__qualname__.startswith(_STUB_QUALNAME_PREFIX), label

    assert spread() == 0.0
    # Fail-DANGEROUS: "no position held" for every symbol ever asked about.
    assert open_pos(_FUTURES_SYMBOL) is False


def test_unwired_volatility_filter_gets_no_stub_at_all() -> None:
    """The volatility lane is inert by *absence*, not by a 0.0-returning stub.

    A stub returning ``0.0`` was exactly how this filter used to be inert, and
    it is what made "just wire the ATR provider" a plausible-looking one-line
    fix that would have rejected every entry.  There is now no ATR-shaped seam
    to fill: the unwired filter holds ``None`` and reads nothing.
    """
    layer = RiskFilterLayer.from_config(_futures_cfg(), ["09:00-15:30"])
    volatility = _filter_of(layer, VolatilityFilter)

    assert volatility._reference_provider is None
    assert not hasattr(volatility, "_current_atr_provider")


# ---------------------------------------------------------------------------
# Change B: an inert provider must announce itself
# ---------------------------------------------------------------------------


def _warnings_from_build(
    caplog: pytest.LogCaptureFixture, **providers: Any
) -> list[str]:
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger=_LAYER_LOGGER):
        RiskFilterLayer.from_config(_futures_cfg(), ["09:00-15:30"], **providers)
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == _LAYER_LOGGER and record.levelno >= logging.WARNING
    ]


@pytest.mark.parametrize(
    "filter_name",
    ["VolatilityFilter", "SpreadFilter", "OpenPositionFilter"],
)
def test_unwired_provider_is_announced(
    caplog: pytest.LogCaptureFixture, filter_name: str
) -> None:
    """Each of the three silent stubs warns at build time, like its siblings.

    ``ConcurrentPositionsFilter`` and ``LeverageFilter`` have logged their own
    inertness since they landed; these three imported no logging at all.
    """
    messages = _warnings_from_build(caplog)
    matching = [m for m in messages if filter_name in m]
    assert len(matching) == 1, f"expected exactly one {filter_name} warning: {messages}"
    assert "inert" in matching[0]


def test_volatility_warning_points_at_the_single_arming_flag(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The warning must route an operator to the safe action, not a partial fix.

    The historical hazard was that the two operands were separately wirable: a
    live ATR against a ``0.0`` default threshold is true for every reading, so
    the "obvious" one-line fix would have rejected every entry and halted all
    trading.  That shape is gone — but the warning is what an operator reads
    first, so it must name the one flag that arms BOTH sides together and say
    plainly that no ATR-only route exists.
    """
    (volatility_warning,) = [
        m for m in _warnings_from_build(caplog) if "VolatilityFilter" in m
    ]
    lowered = volatility_warning.lower()

    # Points at the single flag that arms publisher + reader together...
    assert "volatility" in lowered
    assert "risk.yaml" in lowered
    # ...states that an ATR-only wiring is not offered...
    assert "atr-only" in lowered or "atr only" in lowered
    # ...and keeps the consequence of the historical half-wiring on the record.
    assert any(word in lowered for word in ("halt", "block", "reject")), (
        "the warning must still say what arming only the ATR side did, got: "
        f"{volatility_warning}"
    )


def test_wired_providers_produce_no_inertness_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The warnings are about wiring, not noise — supplying all three silences them."""
    messages = _warnings_from_build(
        caplog,
        volatility_reference_provider=lambda _symbol: None,
        current_spread_provider=lambda: 1.0,
        has_open_position_provider=lambda _symbol: False,
    )
    for filter_name in ("VolatilityFilter", "SpreadFilter", "OpenPositionFilter"):
        assert not [m for m in messages if filter_name in m], messages
