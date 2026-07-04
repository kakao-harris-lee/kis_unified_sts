"""Thin interface contracts for strategy components."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from shared.strategy.entry.mean_reversion import (
    MeanReversionConfig,
    MeanReversionEntry,
)
from shared.strategy.exit.setup_target_exit import (
    SetupTargetExit,
    SetupTargetExitConfig,
)
from shared.strategy.interfaces import (
    EntrySignalGeneratorProtocol,
    ExitSignalGeneratorProtocol,
    PositionSizerProtocol,
)
from shared.strategy.position import FixedSizer, FixedSizerConfig
from shared.strategy.registry import (
    EntryRegistry,
    ExitRegistry,
    SizerRegistry,
    StrategyFactory,
    register_builtin_components,
)


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


def test_existing_strategy_components_satisfy_thin_protocols() -> None:
    entry = MeanReversionEntry(MeanReversionConfig())
    exit_generator = SetupTargetExit(SetupTargetExitConfig(eod_close_enabled=False))
    sizer = FixedSizer(FixedSizerConfig(fixed_quantity=1))

    assert isinstance(entry, EntrySignalGeneratorProtocol)
    assert isinstance(exit_generator, ExitSignalGeneratorProtocol)
    assert isinstance(sizer, PositionSizerProtocol)


def test_strategy_factory_outputs_satisfy_thin_protocols() -> None:
    register_builtin_components()

    strategy = StrategyFactory.create(
        {
            "strategy": {
                "name": "interface_probe",
                "entry": {"type": "mean_reversion", "params": {}},
                "exit": {
                    "type": "setup_target_exit",
                    "params": {"eod_close_enabled": False},
                },
                "position": {
                    "type": "fixed",
                    "params": {"fixed_quantity": 1},
                },
            }
        }
    )

    entry: EntrySignalGeneratorProtocol = strategy.entry
    exit_generator: ExitSignalGeneratorProtocol = strategy.exit
    sizer: PositionSizerProtocol = strategy.position_sizer

    assert isinstance(entry, EntrySignalGeneratorProtocol)
    assert isinstance(exit_generator, ExitSignalGeneratorProtocol)
    assert isinstance(sizer, PositionSizerProtocol)
