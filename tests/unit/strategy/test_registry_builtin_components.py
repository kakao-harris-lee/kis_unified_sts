"""Tests for builtin strategy component registration."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from shared.strategy import registry as registry_module
from shared.strategy.registry import EntryRegistry, ExitRegistry, SizerRegistry

#: L6 (docs/plans/2026-11-07-legacy-removal-plan.md §3) deleted every
#: ``shared.strategy.entry.*`` module, so the entry roster is empty. Kept as an
#: explicit set rather than dropping the assertion: an entry reappearing without
#: a module behind it is exactly what this test exists to catch.
EXPECTED_ENTRY_NAMES: set[str] = set()

EXPECTED_EXIT_NAMES = {
    "three_stage",
    "momentum_decay",
    "trix_golden_exit",
    "setup_target_exit",
    "technical_consensus_exit",
}

EXPECTED_SIZER_NAMES = {
    "fixed_fractional_futures",
    "fixed",
    "risk_based",
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


def test_register_builtin_components_registers_core_exits() -> None:
    registry_module.register_builtin_components()

    assert ExitRegistry.get("three_stage").__name__ == "ThreeStageExit"
    assert ExitRegistry.get("setup_target_exit").__name__ == "SetupTargetExit"
    assert SizerRegistry.get("fixed").__name__ == "FixedSizer"


def test_register_builtin_components_registers_all_builtin_keys() -> None:
    registry_module.register_builtin_components()

    assert set(EntryRegistry.list_all()) == EXPECTED_ENTRY_NAMES
    assert set(ExitRegistry.list_all()) == EXPECTED_EXIT_NAMES
    assert set(SizerRegistry.list_all()) == EXPECTED_SIZER_NAMES


def test_register_builtin_components_is_idempotent_for_core_exit() -> None:
    registry_module.register_builtin_components()
    first_exit_class = ExitRegistry.get("three_stage")

    registry_module.register_builtin_components()

    assert ExitRegistry.get("three_stage") is first_exit_class
