import datetime as dt
from unittest.mock import MagicMock

import pytest


def _ctx():
    from shared.strategy.base import EntryContext

    return EntryContext(
        market_data={"code": "futures"},
        timestamp=dt.datetime.now(dt.UTC),
    )


def _cfg():
    from shared.strategy.gates.regime_gate import GateConfig

    return GateConfig(
        regime_percentile_max=60.0,
        impact_score_max=70,
        event_window_minutes=15,
        require_overnight_us_direction=False,
        permissive_on_missing=True,
    )


def _stub_infra(monkeypatch, setup_adapters_module):
    """Stub Redis construction so the gate hook is reached deterministically."""
    from shared.streaming.client import RedisClient

    monkeypatch.setattr(
        RedisClient, "get_client", classmethod(lambda _cls: MagicMock())
    )


@pytest.mark.parametrize(
    "adapter_class,cfg_class",
    [
        ("SetupAEntryAdapter", "SetupAEntryConfig"),
        ("SetupCEntryAdapter", "SetupCEntryConfig"),
    ],
)
def test_gate_cfg_none_default(adapter_class, cfg_class):
    """gate_cfg kwarg defaults to None when not passed."""
    from shared.strategy.entry import setup_adapters

    AdapterCls = getattr(setup_adapters, adapter_class)
    CfgCls = getattr(setup_adapters, cfg_class)
    adapter = AdapterCls(CfgCls())
    assert adapter._gate_cfg is None


@pytest.mark.parametrize(
    "adapter_class,cfg_class",
    [
        ("SetupAEntryAdapter", "SetupAEntryConfig"),
        ("SetupCEntryAdapter", "SetupCEntryConfig"),
    ],
)
def test_gate_cfg_stored_when_passed(adapter_class, cfg_class):
    """gate_cfg kwarg is stored on the adapter for use by generate()."""
    from shared.strategy.entry import setup_adapters

    AdapterCls = getattr(setup_adapters, adapter_class)
    CfgCls = getattr(setup_adapters, cfg_class)
    cfg = _cfg()
    adapter = AdapterCls(CfgCls(), gate_cfg=cfg)
    assert adapter._gate_cfg is cfg


@pytest.mark.parametrize(
    "adapter_class,cfg_class",
    [
        ("SetupAEntryAdapter", "SetupAEntryConfig"),
        ("SetupCEntryAdapter", "SetupCEntryConfig"),
    ],
)
@pytest.mark.asyncio
async def test_gate_blocks_returns_none(adapter_class, cfg_class, monkeypatch):
    """When apply_regime_gate returns blocked=True, generate returns None."""
    from shared.strategy.entry import setup_adapters

    AdapterCls = getattr(setup_adapters, adapter_class)
    CfgCls = getattr(setup_adapters, cfg_class)
    adapter = AdapterCls(CfgCls(), gate_cfg=_cfg())
    _stub_infra(monkeypatch, setup_adapters)
    # Force the underlying setup to emit a decision signal
    fake_decision = MagicMock()
    fake_decision.metadata = {"signal_direction": "long"}
    adapter._setup.check = MagicMock(return_value=fake_decision)
    # Bypass LLM block (force allow by stubbing _build_market_context to None)
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    # Force apply_regime_gate to return blocked=True
    monkeypatch.setattr(setup_adapters, "apply_regime_gate", lambda **_kw: True)
    result = await adapter.generate(_ctx())
    assert result is None


@pytest.mark.parametrize(
    "adapter_class,cfg_class",
    [
        ("SetupAEntryAdapter", "SetupAEntryConfig"),
        ("SetupCEntryAdapter", "SetupCEntryConfig"),
    ],
)
@pytest.mark.asyncio
async def test_gate_allows_returns_signal(adapter_class, cfg_class, monkeypatch):
    """When apply_regime_gate returns blocked=False, generate returns the signal."""
    from shared.strategy.entry import setup_adapters

    AdapterCls = getattr(setup_adapters, adapter_class)
    CfgCls = getattr(setup_adapters, cfg_class)
    adapter = AdapterCls(CfgCls(daily_bias_filter_enabled=False), gate_cfg=_cfg())
    _stub_infra(monkeypatch, setup_adapters)
    fake_decision = MagicMock()
    fake_decision.metadata = {"signal_direction": "long"}
    adapter._setup.check = MagicMock(return_value=fake_decision)
    fake_signal = MagicMock()
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(setup_adapters, "apply_regime_gate", lambda **_kw: False)
    monkeypatch.setattr(
        setup_adapters,
        "_decision_signal_to_orchestrator_signal",
        lambda *_a, **_kw: fake_signal,
    )
    result = await adapter.generate(_ctx())
    assert result is fake_signal


@pytest.mark.parametrize(
    "adapter_class,cfg_class",
    [
        ("SetupAEntryAdapter", "SetupAEntryConfig"),
        ("SetupCEntryAdapter", "SetupCEntryConfig"),
    ],
)
@pytest.mark.asyncio
async def test_gate_degrades_permissive_when_redis_unavailable(
    adapter_class,
    cfg_class,
    monkeypatch,
):
    """When Redis/CH client construction raises, the gate hook degrades
    PERMISSIVE and the signal passes through (never silently blocks on
    missing infra — spec §9)."""
    from shared.strategy.entry import setup_adapters
    from shared.streaming.client import RedisClient

    AdapterCls = getattr(setup_adapters, adapter_class)
    CfgCls = getattr(setup_adapters, cfg_class)
    adapter = AdapterCls(CfgCls(daily_bias_filter_enabled=False), gate_cfg=_cfg())

    fake_decision = MagicMock()
    fake_decision.metadata = {"signal_direction": "long"}
    adapter._setup.check = MagicMock(return_value=fake_decision)
    fake_signal = MagicMock()
    monkeypatch.setattr(setup_adapters, "_build_market_context", lambda _c: MagicMock())
    monkeypatch.setattr(
        setup_adapters,
        "_decision_signal_to_orchestrator_signal",
        lambda *_a, **_kw: fake_signal,
    )

    # Force RedisClient.get_client() to raise → triggers the
    # `except Exception: _redis, _ch = None, None` PERMISSIVE branch
    monkeypatch.setattr(
        RedisClient,
        "get_client",
        classmethod(lambda _cls: (_ for _ in ()).throw(RuntimeError("redis down"))),
    )

    # apply_regime_gate must NOT be called when infra is down
    gate_called = []
    monkeypatch.setattr(
        setup_adapters,
        "apply_regime_gate",
        lambda **kw: gate_called.append(kw) or False,
    )

    result = await adapter.generate(_ctx())
    # PERMISSIVE: signal passes through, gate was NOT called
    assert result is fake_signal
    assert gate_called == []
