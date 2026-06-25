"""Tests for builtin strategy component registration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from shared.strategy import registry as registry_module
from shared.strategy.registry import EntryRegistry, ExitRegistry, SizerRegistry


EXPECTED_ENTRY_NAMES = {
    "stochrsi_trend",
    "mean_reversion",
    "breakout",
    "opening_volume_surge",
    "volume_accumulation",
    "trix_golden",
    "williams_r",
    "macd_ema_crossover",
    "builder_v1",
    "technical_consensus",
    "llm_directed_indicator",
    "trend_pullback",
    "momentum_breakout",
    "trend_continuation_vwap",
    "daily_pullback",
    "pattern_pullback",
    "setup_a_gap_reversion",
    "setup_c_event_reaction",
    "vr_composite",
}

EXPECTED_EXIT_NAMES = {
    "three_stage",
    "momentum_decay",
    "builder_v1_exit",
    "trix_golden_exit",
    "williams_r_exit",
    "llm_directed_indicator_exit",
    "mean_reversion_exit",
    "atr_dynamic",
    "setup_target_exit",
    "track_a_exit",
    "chandelier_exit",
    "technical_consensus_exit",
    "vr_composite_exit",
}

EXPECTED_SIZER_NAMES = {
    "fixed_fractional_futures",
    "fixed",
    "risk_based",
    "llm_adaptive",
}


@pytest.fixture(autouse=True)
def restore_registries() -> Iterator[None]:
    """Keep registry globals isolated for this test module."""
    snapshots = {
        EntryRegistry: dict(EntryRegistry._components),
        ExitRegistry: dict(ExitRegistry._components),
        SizerRegistry: dict(SizerRegistry._components),
    }

    EntryRegistry.clear()
    ExitRegistry.clear()
    SizerRegistry.clear()
    yield

    for registry, snapshot in snapshots.items():
        registry.clear()
        registry._components.update(snapshot)


def _table_names(
    table: tuple[tuple[str, tuple[tuple[str, str], ...], str], ...],
) -> set[str]:
    return {
        name
        for _module_path, registrations, _debug_label in table
        for name, _class_name in registrations
    }


def test_builtin_component_tables_preserve_existing_component_keys() -> None:
    assert (
        _table_names(registry_module._BUILTIN_ENTRY_COMPONENTS)
        == EXPECTED_ENTRY_NAMES
    )
    assert _table_names(registry_module._BUILTIN_EXIT_COMPONENTS) == EXPECTED_EXIT_NAMES
    assert (
        _table_names(registry_module._BUILTIN_SIZER_COMPONENTS)
        == EXPECTED_SIZER_NAMES
    )


def test_register_builtin_components_registers_core_entries() -> None:
    registry_module.register_builtin_components()

    assert EntryRegistry.get("mean_reversion").__name__ == "MeanReversionEntry"
    assert EntryRegistry.get("momentum_breakout").__name__ == "MomentumBreakoutEntry"
    assert EntryRegistry.get("williams_r").__name__ == "WilliamsREntry"


def test_register_builtin_components_registers_all_builtin_keys() -> None:
    registry_module.register_builtin_components()

    assert set(EntryRegistry.list_all()) == EXPECTED_ENTRY_NAMES
    assert set(ExitRegistry.list_all()) == EXPECTED_EXIT_NAMES
    assert set(SizerRegistry.list_all()) == EXPECTED_SIZER_NAMES


def test_register_builtin_components_is_idempotent_for_core_entry() -> None:
    registry_module.register_builtin_components()
    first_entry_class = EntryRegistry.get("mean_reversion")

    registry_module.register_builtin_components()

    assert EntryRegistry.get("mean_reversion") is first_entry_class
