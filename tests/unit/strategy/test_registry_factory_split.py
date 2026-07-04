"""Tests for registry facade compatibility after factory/builtin extraction."""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest

from shared.strategy.registry import EntryRegistry, ExitRegistry, SizerRegistry


@pytest.fixture(autouse=True)
def restore_registries() -> Iterator[None]:
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


def test_factory_module_exports_registry_facade_strategy_factory() -> None:
    factory_module = importlib.import_module("shared.strategy.factory")
    registry_module = importlib.import_module("shared.strategy.registry")

    assert factory_module.StrategyFactory is registry_module.StrategyFactory


def test_builtin_components_module_exports_registry_facade_registration() -> None:
    builtin_module = importlib.import_module("shared.strategy.builtin_components")
    registry_module = importlib.import_module("shared.strategy.registry")

    assert (
        builtin_module.register_builtin_components
        is registry_module.register_builtin_components
    )

    builtin_module.register_builtin_components()

    assert EntryRegistry.is_registered("mean_reversion")
    assert ExitRegistry.is_registered("three_stage")
    assert SizerRegistry.is_registered("fixed")
