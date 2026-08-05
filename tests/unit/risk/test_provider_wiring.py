"""Regression guard: the PRODUCTION RiskFilterLayer call sites must wire real
providers, and an unwired provider must announce itself.

Why this file exists
--------------------
``RiskFilterLayer.from_config`` silently substitutes a no-op stub for three
providers when the caller omits them (``current_atr_provider`` → ``0.0``,
``current_spread_provider`` → ``0.0``, ``has_open_position_provider`` →
``False``).  Two of those stubs merely make a filter inert; the third is
fail-**dangerous** — a stub reporting "no position held" for every symbol
disables the duplicate-entry guard rather than declining to add a filter.  The
futures daemon shipped in exactly that state without any test noticing.

The acceptance criterion for this file is behavioural, not cosmetic:

    Removing ``has_open_position_provider=...`` from a production call site
    must make :func:`test_production_call_site_wires_open_position_provider`
    FAIL.

To meet that criterion these tests execute the **real** ``_build_and_run``
entrypoint of each daemon and capture the kwargs it actually passes, rather
than reconstructing a layer here (which would prove nothing about production).
``RiskFilterLayer.from_config`` is replaced by a spy that raises, so the real
wiring code runs to completion and the daemon itself is never started.  The
only other seam is ``RedisClient.get_client`` — the daemons' own sync-Redis
accessor, which pings on construction and therefore needs a fake in a
Redis-less test environment.

The captured provider is then *exercised* against that fake, which pins the
part a mere "kwarg is present" assertion would miss: that the guard reads the
same hash, keyed by the same identifier, that the position writer writes.  A
symbol/code mismatch there would make the guard silently useless — the very
defect class this file closes.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from types import ModuleType
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

    atr = _filter_of(layer, VolatilityFilter)._current_atr_provider
    spread = _filter_of(layer, SpreadFilter)._current_spread_provider
    open_pos = _filter_of(layer, OpenPositionFilter)._has_open_position_provider

    for label, provider in (("atr", atr), ("spread", spread), ("open", open_pos)):
        assert provider.__qualname__.startswith(_STUB_QUALNAME_PREFIX), label

    assert atr() == 0.0
    assert spread() == 0.0
    # Fail-DANGEROUS: "no position held" for every symbol ever asked about.
    assert open_pos(_FUTURES_SYMBOL) is False


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


def test_volatility_warning_forbids_wiring_the_atr_provider_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The obvious one-line "fix" for the volatility warning halts all trading.

    ``VolatilityFilter`` is broken on BOTH sides of its comparison:
    ``current_atr_provider() > state_snapshot.atr_90th_percentile`` with a
    threshold that defaults to ``0.0`` and has no production writer.  Today
    ``0.0 > 0.0`` is false so everything passes; wiring a live ATR alone makes
    it ``ATR > 0.0`` — true for every signal — and silently blocks every entry.

    The warning must therefore say so explicitly, or it actively invites the
    worst available action.
    """
    (volatility_warning,) = [
        m for m in _warnings_from_build(caplog) if "VolatilityFilter" in m
    ]

    # Names the *other* side of the comparison...
    assert "atr_90th_percentile" in volatility_warning
    # ...says that side has no production writer / default of 0.0...
    assert "0.0" in volatility_warning
    # ...and states the consequence of a partial fix in plain words.
    lowered = volatility_warning.lower()
    assert "alone" in lowered
    assert any(word in lowered for word in ("halt", "block", "reject")), (
        "the warning must state that wiring the ATR provider alone would stop "
        f"all trading, got: {volatility_warning}"
    )


def test_wired_providers_produce_no_inertness_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The warnings are about wiring, not noise — supplying all three silences them."""
    messages = _warnings_from_build(
        caplog,
        current_atr_provider=lambda: 1.0,
        current_spread_provider=lambda: 1.0,
        has_open_position_provider=lambda _symbol: False,
    )
    for filter_name in ("VolatilityFilter", "SpreadFilter", "OpenPositionFilter"):
        assert not [m for m in messages if filter_name in m], messages


# ---------------------------------------------------------------------------
# Change I: the production call sites themselves
# ---------------------------------------------------------------------------


class _CapturedBuild(Exception):
    """Raised by the ``from_config`` spy to unwind the real daemon builder."""

    def __init__(self, kwargs: dict[str, Any]) -> None:
        super().__init__("captured RiskFilterLayer.from_config kwargs")
        self.kwargs = kwargs


class _FakeSyncRedis:
    """Stand-in for ``RedisClient.get_client()`` (which pings on construction)."""

    def __init__(self, *, hexists_result: bool = False, raises: bool = False) -> None:
        self.hexists_calls: list[tuple[str, str]] = []
        self._hexists_result = hexists_result
        self._raises = raises

    def hexists(self, key: str, field: str) -> bool:
        self.hexists_calls.append((key, field))
        if self._raises:
            raise RuntimeError("redis down")
        return self._hexists_result

    def hgetall(self, key: str) -> dict[str, str]:  # noqa: ARG002
        return {}


def _capture_call_site_kwargs(
    module: ModuleType,
    env_key: str,
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeSyncRedis,
) -> dict[str, Any]:
    """Run the daemon's real ``_build_and_run`` and capture the layer kwargs.

    The spy raises instead of returning a layer, so execution stops at the
    construction site: every line of production wiring before it has run, and
    nothing after it (no daemon, no stream consumer) ever starts.
    """
    import shared.streaming.client as client_mod

    monkeypatch.setenv(env_key, "shadow")
    monkeypatch.setattr(
        client_mod.RedisClient, "get_client", classmethod(lambda cls: fake_redis)
    )

    def _spy(*_args: Any, **kwargs: Any) -> RiskFilterLayer:
        raise _CapturedBuild(kwargs)

    monkeypatch.setattr(RiskFilterLayer, "from_config", _spy)

    with pytest.raises(_CapturedBuild) as excinfo:
        asyncio.run(module._build_and_run())
    return excinfo.value.kwargs


_CALL_SITES = [
    pytest.param(
        "services.risk_filter.main",
        "FUTURES_RISK_FILTER",
        "FUTURES_MONITOR_POSITIONS_KEY",
        _FUTURES_POSITIONS_KEY,
        _FUTURES_SYMBOL,
        id="futures",
    ),
    pytest.param(
        "services.stock_risk_filter.main",
        "STOCK_RISK_FILTER",
        "STOCK_POSITIONS_KEY",
        _STOCK_POSITIONS_KEY,
        _STOCK_CODE,
        id="stock",
    ),
]


@pytest.mark.parametrize(
    ("module_path", "mode_env", "key_env", "positions_key", "symbol"), _CALL_SITES
)
def test_production_call_site_wires_open_position_provider(
    monkeypatch: pytest.MonkeyPatch,
    module_path: str,
    mode_env: str,
    key_env: str,
    positions_key: str,
    symbol: str,
) -> None:
    """The duplicate-entry guard is armed in production, on the right hash.

    Delete ``has_open_position_provider=...`` from the call site and this test
    fails on the first assertion — that is the whole point of the file.
    """
    monkeypatch.delenv(key_env, raising=False)
    fake = _FakeSyncRedis(hexists_result=False)
    kwargs = _capture_call_site_kwargs(
        importlib.import_module(module_path), mode_env, monkeypatch, fake
    )

    assert "has_open_position_provider" in kwargs, (
        f"{module_path} builds RiskFilterLayer without a "
        "has_open_position_provider — from_config will substitute a stub that "
        "reports 'no position held' for every symbol, disabling the "
        "duplicate-entry guard"
    )
    provider = kwargs["has_open_position_provider"]
    assert provider is not None
    assert not provider.__qualname__.startswith(_STUB_QUALNAME_PREFIX)

    # Exercising it proves the guard reads the hash the position writer writes,
    # keyed by the identifier the risk layer actually passes (signal.symbol).
    assert provider(symbol) is False
    assert fake.hexists_calls == [(positions_key, symbol)]


@pytest.mark.parametrize(
    ("module_path", "mode_env", "key_env", "positions_key", "symbol"), _CALL_SITES
)
def test_production_open_position_provider_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    module_path: str,
    mode_env: str,
    key_env: str,
    positions_key: str,  # noqa: ARG001
    symbol: str,
) -> None:
    """A Redis error must block re-entry, not wave it through.

    Both chains agree on this polarity: uncertainty about whether a position is
    open is resolved as "open", because a duplicated entry is the more
    expensive mistake.
    """
    monkeypatch.delenv(key_env, raising=False)
    fake = _FakeSyncRedis(raises=True)
    kwargs = _capture_call_site_kwargs(
        importlib.import_module(module_path), mode_env, monkeypatch, fake
    )

    provider = kwargs["has_open_position_provider"]
    assert provider(symbol) is True
