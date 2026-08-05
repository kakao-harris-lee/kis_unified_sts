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

The volatility lane is held to the same standard, plus one more.  Its two
operands used to be wirable independently — a live ATR against a ``0.0``
default threshold rejects every entry and halts all trading — so the tests
below pin not only that the production call sites wire the reader, but that the
reader and the *publisher* (in the service that owns the indicator engine) land
on the same Redis key, and that the whole lane stays inert while the config
flag is off.
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

    def __init__(
        self,
        *,
        hexists_result: bool = False,
        raises: bool = False,
        hget_result: str | None = None,
    ) -> None:
        self.hexists_calls: list[tuple[str, str]] = []
        self.hget_calls: list[tuple[str, str]] = []
        self._hexists_result = hexists_result
        self._raises = raises
        self._hget_result = hget_result

    def hexists(self, key: str, field: str) -> bool:
        self.hexists_calls.append((key, field))
        if self._raises:
            raise RuntimeError("redis down")
        return self._hexists_result

    def hget(self, key: str, field: str) -> str | None:
        self.hget_calls.append((key, field))
        if self._raises:
            raise RuntimeError("redis down")
        return self._hget_result

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


# ---------------------------------------------------------------------------
# The volatility lane: both operands, or neither
# ---------------------------------------------------------------------------

_VOLATILITY_CALL_SITES = [
    pytest.param(
        "services.risk_filter.main",
        "FUTURES_RISK_FILTER",
        "FUTURES_MONITOR_POSITIONS_KEY",
        "shared.risk.config",
        "FuturesRiskConfig",
        _FUTURES_VOLATILITY_KEY,
        _FUTURES_SYMBOL,
        id="futures",
    ),
    pytest.param(
        "services.stock_risk_filter.main",
        "STOCK_RISK_FILTER",
        "STOCK_POSITIONS_KEY",
        "shared.risk.config",
        "StockRiskConfig",
        _STOCK_VOLATILITY_KEY,
        _STOCK_CODE,
        id="stock",
    ),
]


def _force_volatility_enabled(
    monkeypatch: pytest.MonkeyPatch, module_path: str, class_name: str
) -> None:
    """Make ``<Config>.from_yaml()`` report ``volatility.enabled = True``.

    The operator flag is off by default (deliberately — the stock chain is live
    production), so the wired path has to be forced open to be tested at all.
    Everything downstream of the flag is the real production wiring.
    """
    config_cls = getattr(importlib.import_module(module_path), class_name)
    original = config_cls.from_yaml.__func__

    def _patched(cls: Any, *args: Any, **kwargs: Any) -> Any:
        config = original(cls, *args, **kwargs)
        return config.model_copy(
            update={
                "volatility": config.volatility.model_copy(update={"enabled": True})
            }
        )

    monkeypatch.setattr(config_cls, "from_yaml", classmethod(_patched))


@pytest.mark.parametrize(
    (
        "module_path",
        "mode_env",
        "key_env",
        "config_module",
        "config_class",
        "volatility_key",
        "symbol",
    ),
    _VOLATILITY_CALL_SITES,
)
def test_production_call_site_wires_volatility_reference_provider(
    monkeypatch: pytest.MonkeyPatch,
    module_path: str,
    mode_env: str,
    key_env: str,
    config_module: str,
    config_class: str,
    volatility_key: str,
    symbol: str,
) -> None:
    """With the flag on, the daemon reads the hash the publisher writes.

    Delete ``volatility_reference_provider=...`` from the call site and this
    fails on the first assertion.  Change the key on either side without the
    other and it fails on the last one — that pairing is the whole point, since
    a reader pointed at a key nobody writes is a filter that silently never
    fires.
    """
    monkeypatch.delenv(key_env, raising=False)
    _force_volatility_enabled(monkeypatch, config_module, config_class)
    fake = _FakeSyncRedis()
    kwargs = _capture_call_site_kwargs(
        importlib.import_module(module_path), mode_env, monkeypatch, fake
    )

    assert "volatility_reference_provider" in kwargs, (
        f"{module_path} builds RiskFilterLayer without a "
        "volatility_reference_provider — VolatilityFilter would stay inert "
        "even with risk[_stock].volatility.enabled = true"
    )
    provider = kwargs["volatility_reference_provider"]
    assert provider is not None

    # Exercising it pins that the reader hits the published hash, keyed by the
    # identifier the risk layer actually passes (signal.symbol).
    assert provider(symbol) is None  # nothing published in this fake
    assert fake.hget_calls == [(volatility_key, symbol)]


@pytest.mark.parametrize(
    (
        "module_path",
        "mode_env",
        "key_env",
        "config_module",
        "config_class",
        "volatility_key",
        "symbol",
    ),
    _VOLATILITY_CALL_SITES,
)
def test_volatility_lane_is_inert_while_the_flag_is_off(
    monkeypatch: pytest.MonkeyPatch,
    module_path: str,
    mode_env: str,
    key_env: str,
    config_module: str,  # noqa: ARG001
    config_class: str,  # noqa: ARG001
    volatility_key: str,  # noqa: ARG001
    symbol: str,  # noqa: ARG001
) -> None:
    """Default config ⇒ no provider ⇒ no Redis reads ⇒ no behaviour change.

    The stock chain is live production, so landing this work must be a no-op
    until an operator decides otherwise. ``None`` here means the filter is
    built with nothing to read and passes every signal, exactly as before.
    """
    monkeypatch.delenv(key_env, raising=False)
    fake = _FakeSyncRedis()
    kwargs = _capture_call_site_kwargs(
        importlib.import_module(module_path), mode_env, monkeypatch, fake
    )

    assert kwargs.get("volatility_reference_provider") is None
    assert fake.hget_calls == []


def test_publisher_and_filter_agree_on_the_stock_reference_key() -> None:
    """The writing daemon and the reading daemon target one key.

    ``services/stock_strategy`` owns the only stock indicator engine, so it is
    the publisher; ``services/stock_risk_filter`` is the reader. They are
    separate containers, so nothing but this test stops them drifting apart
    into a permanently-warming, permanently-inert filter.
    """
    from services.stock_strategy.daemon import StockStrategyDaemon
    from shared.risk.config import StockRiskConfig

    settings = StockRiskConfig.from_yaml().volatility.model_copy(
        update={"enabled": True}
    )
    daemon = StockStrategyDaemon(
        redis=object(),
        feed=object(),
        engine=object(),
        resolver=object(),
        manager=object(),
        candidate_stream="signal.candidate.stock.shadow",
        candidate_maxlen=10,
        now_fn=lambda: None,
        volatility_settings=settings,
    )

    assert daemon._volatility_publisher is not None
    assert daemon._volatility_publisher.reference_key == _STOCK_VOLATILITY_KEY


def test_stock_publisher_is_not_built_while_the_flag_is_off() -> None:
    """Both halves stay dark together: no publisher, no reader, no writes."""
    from services.stock_strategy.daemon import StockStrategyDaemon
    from shared.risk.config import StockRiskConfig

    daemon = StockStrategyDaemon(
        redis=object(),
        feed=object(),
        engine=object(),
        resolver=object(),
        manager=object(),
        candidate_stream="signal.candidate.stock.shadow",
        candidate_maxlen=10,
        now_fn=lambda: None,
        volatility_settings=StockRiskConfig.from_yaml().volatility,
    )

    assert daemon._volatility_publisher is None


def test_futures_publisher_and_filter_agree_on_the_reference_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same pairing for the futures chain (publisher: decision_engine)."""
    import services.decision_engine.main as decision_main
    from shared.risk.config import FuturesRiskConfig

    _force_volatility_enabled(monkeypatch, "shared.risk.config", "FuturesRiskConfig")
    publisher = decision_main._build_volatility_publisher(
        object(), lambda: {_FUTURES_SYMBOL: 1.0}
    )

    assert publisher is not None
    assert publisher.reference_key == _FUTURES_VOLATILITY_KEY

    # And with the flag off (real config), nothing is published at all.
    monkeypatch.undo()
    assert FuturesRiskConfig.from_yaml().volatility.enabled is False
    assert (
        decision_main._build_volatility_publisher(
            object(), lambda: {_FUTURES_SYMBOL: 1.0}
        )
        is None
    )


def test_futures_publisher_is_absent_without_an_indicator_engine() -> None:
    """``off`` mode builds no engine, so there is nothing to sample."""
    import services.decision_engine.main as decision_main

    assert decision_main._build_volatility_publisher(object(), None) is None


# ---------------------------------------------------------------------------
# Which ATR accessor the publishers sample
# ---------------------------------------------------------------------------

#: An absolute-unit ATR (price points / KRW) and the same reading normalised by
#: close. Both engines expose them under the SAME flat ``"atr"`` key, one via
#: get_indicators and one via get_indicator_features, so a swap is invisible at
#: the call site and produces a plausible-looking number either way.
_ABSOLUTE_ATR = 1234.5
_NORMALISED_ATR = 0.0035


class _TwoAccessorEngine:
    """Indicator engine exposing both the absolute and the normalised ATR."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_indicators(self, _symbol: str) -> dict[str, float]:
        self.calls.append("get_indicators")
        return {"atr": _ABSOLUTE_ATR}

    def get_indicator_features(self, _symbol: str) -> dict[str, float]:
        self.calls.append("get_indicator_features")
        return {"atr": _NORMALISED_ATR}

    def is_warm(self, _symbol: str) -> bool:
        return True


def test_stock_publisher_samples_the_absolute_atr_accessor() -> None:
    """The stock publisher must read get_indicators, not get_indicator_features.

    Both return an ``"atr"`` key, so the swap type-checks and keeps the gate
    working — the fused reference puts both operands on whichever scale is
    sampled, so it cannot fail open.  What it silently changes is the *meaning*
    of the gate: "absolute price movement" becomes "movement as a fraction of
    price", a different risk question with different rejections.
    """
    from services.stock_strategy.daemon import StockStrategyDaemon

    engine = _TwoAccessorEngine()
    daemon = StockStrategyDaemon(
        redis=object(),
        feed=object(),
        engine=engine,
        resolver=object(),
        manager=object(),
        candidate_stream="signal.candidate.stock.shadow",
        candidate_maxlen=10,
        now_fn=lambda: None,
    )
    daemon._universe = [_STOCK_CODE]

    readings = daemon._atr_readings()

    assert readings == {_STOCK_CODE: _ABSOLUTE_ATR}
    assert engine.calls == ["get_indicators"]
    assert "get_indicator_features" not in engine.calls


def test_futures_publisher_samples_the_absolute_atr_accessor() -> None:
    """Same accessor contract on the futures side (decision_engine)."""
    from services.decision_engine.main import build_atr_readings

    engine = _TwoAccessorEngine()
    readings = build_atr_readings(engine, _FUTURES_SYMBOL)()

    assert readings == {_FUTURES_SYMBOL: _ABSOLUTE_ATR}
    assert engine.calls == ["get_indicators"]
    assert "get_indicator_features" not in engine.calls


def test_futures_publisher_matches_the_context_providers_atr() -> None:
    """The published ATR is the value Setup A/C actually see, not a second one.

    ``FuturesContextProvider`` computes ``atr_14`` with the same expression; if
    the publisher ever diverged, the percentile would describe a series the
    setups do not trade on.
    """
    from services.decision_engine.main import build_atr_readings

    engine = _TwoAccessorEngine()
    published = build_atr_readings(engine, _FUTURES_SYMBOL)()[_FUTURES_SYMBOL]
    context_side = float(
        (engine.get_indicators(_FUTURES_SYMBOL) or {}).get("atr", 0.0) or 0.0
    )

    assert published == context_side
