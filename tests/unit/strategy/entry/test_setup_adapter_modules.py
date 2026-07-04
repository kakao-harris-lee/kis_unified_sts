"""Contract tests for the decomposed futures setup adapter modules."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext, ScheduledEvent
from shared.strategy.base import EntryContext
from shared.strategy.entry import setup_adapters

KST = ZoneInfo("Asia/Seoul")


def test_setup_adapter_classes_have_owner_modules_and_facade_identity():
    """Adapter class imports should work from owner modules and the old facade."""
    from shared.strategy.entry import (
        setup_a_adapter,
        setup_c_adapter,
        setup_d_adapter,
    )

    assert setup_a_adapter.SetupAEntryAdapter is setup_adapters.SetupAEntryAdapter
    assert setup_a_adapter.SetupAEntryAdapter.__module__.endswith(".setup_a_adapter")
    assert setup_c_adapter.SetupCEntryAdapter is setup_adapters.SetupCEntryAdapter
    assert setup_c_adapter.SetupCEntryAdapter.__module__.endswith(".setup_c_adapter")
    assert setup_d_adapter.SetupDEntryAdapter is setup_adapters.SetupDEntryAdapter
    assert setup_d_adapter.SetupDEntryAdapter.__module__.endswith(".setup_d_adapter")


def test_setup_adapter_facade_reexports_decomposed_config_models():
    """Existing setup_adapters imports must remain stable after config extraction."""
    from shared.strategy.entry import setup_entry_configs

    assert setup_adapters.LLMTuningConfig is setup_entry_configs.LLMTuningConfig
    assert (
        setup_adapters.SetupAForecastIntegrationConfig
        is setup_entry_configs.SetupAForecastIntegrationConfig
    )
    assert (
        setup_adapters.SetupCForecastIntegrationConfig
        is setup_entry_configs.SetupCForecastIntegrationConfig
    )
    assert setup_adapters.SetupAEntryConfig is setup_entry_configs.SetupAEntryConfig
    assert setup_adapters.SetupCEntryConfig is setup_entry_configs.SetupCEntryConfig
    assert setup_adapters.SetupDEntryConfig is setup_entry_configs.SetupDEntryConfig

    cfg = setup_entry_configs.SetupAEntryConfig(
        llm_tuning={"enabled": True, "min_context_confidence": 0.7},
        forecast_integration={"enabled": True, "gap_threshold_vol_mult": 1.8},
    )

    assert cfg.llm_tuning.enabled is True
    assert cfg.llm_tuning.min_context_confidence == 0.7
    assert cfg.forecast_integration.enabled is True
    assert cfg.forecast_integration.gap_threshold_vol_mult == 1.8
    assert cfg._default_config_file == "strategies/futures/setup_a_gap_reversion.yaml"
    assert cfg._default_section == "strategy.entry.params"


def test_setup_context_builder_has_facade_compatible_api():
    """Context conversion should be usable directly and through the old facade."""
    from shared.strategy.entry import setup_context_builder

    assert (
        setup_adapters._build_market_context
        is setup_context_builder.build_setup_market_context
    )

    existing = MarketContext(
        now=datetime(2026, 4, 23, 9, 15, tzinfo=KST),
        symbol="A05603",
        current_price=100.0,
        prev_close=99.0,
        today_open=100.5,
        vwap=100.2,
        atr_14=1.4,
        atr_90th_percentile=2.1,
        last_15min_high=101.0,
        last_15min_low=99.5,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )

    assert (
        setup_context_builder.build_setup_market_context(
            EntryContext(market_context=existing)
        )
        is existing
    )

    event = ScheduledEvent(
        event_id="cpi",
        event_type="CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 5, tzinfo=KST),
        impact_tier=1,
    )
    macro = SimpleNamespace(sp500_change_pct=-0.4)
    built = setup_context_builder.build_setup_market_context(
        EntryContext(
            market_data={
                "close": "100.25",
                "prev_close": "99.5",
                "open": "100.0",
                "code": "A05603",
            },
            indicators={"atr_14": "1.2"},
            timestamp=datetime(2026, 4, 23, 0, 10, tzinfo=UTC),
            metadata={"scheduled_events": [event, object()], "macro_overnight": macro},
        )
    )

    assert built is not None
    assert built.now == datetime(2026, 4, 23, 9, 10, tzinfo=KST)
    assert built.symbol == "A05603"
    assert built.current_price == 100.25
    assert built.vwap == 100.25
    assert built.atr_14 == 1.2
    assert built.atr_90th_percentile == pytest.approx(1.8)
    assert built.scheduled_events == [event]
    assert built.macro_overnight is macro


def test_signal_mapper_has_facade_compatible_api():
    """Signal mapping must keep timestamp, metadata, and valid_until contracts."""
    from shared.models.signal import SignalType
    from shared.strategy.entry import setup_signal_mapper

    assert (
        setup_adapters._decision_signal_to_orchestrator_signal
        is setup_signal_mapper.decision_signal_to_orchestrator_signal
    )

    valid_until = datetime(2026, 4, 23, 9, 30, tzinfo=KST)
    decision_signal = SimpleNamespace(
        symbol="A05603",
        direction="long",
        confidence=0.4,
        setup_type="setup_a",
        stop_loss=98.5,
        take_profit=103.0,
        reason_tags=("gap", "reversion"),
        entry_price=100.5,
        valid_until=valid_until,
    )

    signal = setup_signal_mapper.decision_signal_to_orchestrator_signal(
        decision_signal,
        strategy_name="setup_a_gap_reversion",
        timestamp=datetime(2026, 4, 23, 0, 15),
        confidence_override=0.65,
        entry_atr=1.2,
        extra_metadata={"source": "unit"},
    )

    assert signal.code == "A05603"
    assert signal.signal_type is SignalType.ENTRY
    assert signal.strategy == "setup_a_gap_reversion"
    assert signal.price == 100.5
    assert signal.confidence == 0.65
    assert signal.timestamp == datetime(2026, 4, 23, 0, 15, tzinfo=UTC)
    assert signal.metadata["direction"] == "long"
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["entry_atr"] == 1.2
    assert signal.metadata["valid_until"] is valid_until
    assert signal.metadata["reason_tags"] == ["gap", "reversion"]
    assert signal.metadata["source"] == "unit"


def test_llm_gate_helpers_have_facade_compatible_api():
    """Adapter-local LLM gates can move without changing old private imports."""
    from shared.strategy.entry import setup_llm_gate

    assert setup_adapters._get_llm_context is setup_llm_gate.get_llm_context
    assert (
        setup_adapters._normalise_regime_label is setup_llm_gate.normalise_regime_label
    )
    assert setup_adapters._resolve_regime_label is setup_llm_gate.resolve_regime_label
    assert (
        setup_adapters._apply_llm_tuning_setup_a
        is setup_llm_gate.apply_llm_tuning_setup_a
    )
    assert (
        setup_adapters._apply_llm_tuning_setup_c
        is setup_llm_gate.apply_llm_tuning_setup_c
    )
    assert setup_adapters._apply_llm_veto is setup_llm_gate.apply_llm_veto

    enum_like = SimpleNamespace(name="BEAR_STRONG", value="bear")
    assert setup_llm_gate.normalise_regime_label(enum_like) == "BEAR_STRONG"
    assert (
        setup_llm_gate.resolve_regime_label(
            EntryContext(metadata={"market_state": "Regime.BULL_STRONG"})
        )
        == "BULL_STRONG"
    )
