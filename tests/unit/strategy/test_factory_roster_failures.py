"""A strategy missing from the roster must never be *silently* missing.

``StrategyFactory.create_all`` tolerates individual construction failures on
purpose. It is how the stock and futures paper pipelines build their entire
roster (``services/stock_strategy/main.py`` -> ``StrategyManager`` ->
``StrategyManager._load_strategies``), so one broken YAML must not leave a
running system with an empty roster. That tolerance is kept here; what these
tests pin is its price -- every absence is loud, classified, and handed back to
the caller -- and the distinction an operator needs when a strategy emits no
signals:

    "I turned it off"   -> ``enabled: false``; ConfigLoader filters it out and
                           the factory never sees it, so it is never a failure.
    "It was supposed to run and could not be built" -> a build failure, which
                           must be visible at ERROR and enumerable by the caller.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from shared.config.loader import ConfigLoader
from shared.strategy.factory import StrategyDeliberatelyExcluded, StrategyFactory
from shared.strategy.registry import (
    EntryRegistry,
    ExitRegistry,
    SizerRegistry,
    register_builtin_components,
)

# Entry component names registered only for these tests.
HEALTHY_ENTRY = "mean_reversion"  # a real, registered built-in
MISCONFIGURED_ENTRY = "roster_probe_misconfigured_entry"
EXCLUDED_ENTRY = "roster_probe_excluded_entry"

# A distinctive message so the assertions cannot pass on a generic log line.
MISCONFIG_MESSAGE = (
    "forecast_integration.enabled is true but no forecast client was supplied"
)
EXCLUSION_MESSAGE = "uses operators the streaming runtime cannot evaluate"


class _MisconfiguredEntry:
    """Fails at construction, exactly like ``SetupCEntryAdapter._validate_config``."""

    def __init__(self, params: dict[str, Any]) -> None:
        raise ValueError(MISCONFIG_MESSAGE)


class _DeliberatelyExcludedEntry:
    """Opts itself out of the roster; not an operator error."""

    def __init__(self, params: dict[str, Any]) -> None:
        raise StrategyDeliberatelyExcluded(EXCLUSION_MESSAGE)


@pytest.fixture(autouse=True)
def registries() -> Iterator[None]:
    """Register the probe components, restore the global registries afterwards."""
    snapshots = {
        EntryRegistry: dict(EntryRegistry._components),
        ExitRegistry: dict(ExitRegistry._components),
        SizerRegistry: dict(SizerRegistry._components),
    }
    register_builtin_components()
    EntryRegistry.register_class(MISCONFIGURED_ENTRY, _MisconfiguredEntry)
    EntryRegistry.register_class(EXCLUDED_ENTRY, _DeliberatelyExcludedEntry)
    yield
    for registry, snapshot in snapshots.items():
        registry.clear()
        registry._components.update(snapshot)


@pytest.fixture
def strategies_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point ConfigLoader at an empty temp config tree for the duration."""
    directory = tmp_path / "strategies" / "stock"
    directory.mkdir(parents=True)
    monkeypatch.setattr(ConfigLoader, "_config_dir", tmp_path)
    ConfigLoader.clear_cache()
    yield directory
    ConfigLoader.clear_cache()


def _write_strategy(
    directory: Path, name: str, entry_type: str, *, enabled: bool = True
) -> None:
    (directory / f"{name}.yaml").write_text(
        yaml.dump(
            {
                "strategy": {
                    "name": name,
                    "asset_class": "stock",
                    "enabled": enabled,
                    "entry": {"type": entry_type, "params": {}},
                    "exit": {
                        "type": "setup_target_exit",
                        "params": {"eod_close_enabled": False},
                    },
                    "position": {"type": "fixed", "params": {"fixed_quantity": 1}},
                }
            }
        ),
        encoding="utf-8",
    )


def _records_about(
    caplog: pytest.LogCaptureFixture, name: str
) -> list[logging.LogRecord]:
    """Records the *factory* emitted about one strategy.

    Filtered to the factory's logger so that ConfigLoader's own debug chatter
    ("Config loaded: ...") is not mistaken for the factory reporting a problem.
    """
    return [
        record
        for record in caplog.records
        if record.name == "shared.strategy.registry" and name in record.getMessage()
    ]


def test_misconfigured_strategy_is_surfaced_at_error_level(
    strategies_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A validation error at construction reaches the operator, with its cause."""
    _write_strategy(strategies_dir, "broken_one", MISCONFIGURED_ENTRY)
    _write_strategy(strategies_dir, "healthy_one", HEALTHY_ENTRY)

    with caplog.at_level(logging.DEBUG):
        StrategyFactory.create_all(asset_class="stock", enabled_only=True)

    about_broken = _records_about(caplog, "broken_one")
    assert about_broken, "the dropped strategy was not mentioned in the logs at all"
    assert [r for r in about_broken if r.levelno >= logging.ERROR], (
        "a misconfigured strategy was reported below ERROR; that is the "
        "swallow-and-warn behaviour this change removes"
    )
    assert any(MISCONFIG_MESSAGE in r.getMessage() for r in about_broken), (
        "the original validation message was dropped, leaving the operator "
        "without the reason"
    )


def test_one_broken_strategy_does_not_take_the_roster_down(
    strategies_dir: Path,
) -> None:
    """Tolerance is deliberate: the healthy strategies still load and are returned."""
    _write_strategy(strategies_dir, "broken_one", MISCONFIGURED_ENTRY)
    _write_strategy(strategies_dir, "healthy_one", HEALTHY_ENTRY)

    strategies = StrategyFactory.create_all(asset_class="stock", enabled_only=True)

    assert [s.name for s in strategies] == ["healthy_one"]


def test_normal_roster_builds_with_no_failures(strategies_dir: Path) -> None:
    """The ordinary case: everything builds, nothing is reported."""
    _write_strategy(strategies_dir, "alpha", HEALTHY_ENTRY)
    _write_strategy(strategies_dir, "beta", HEALTHY_ENTRY)

    report = StrategyFactory.build_roster(asset_class="stock", enabled_only=True)

    assert sorted(s.name for s in report.strategies) == ["alpha", "beta"]
    assert report.failures == []
    # The existing caller (StrategyManager._load_strategies) iterates a plain list.
    assert [s.name for s in StrategyFactory.create_all("stock")] == [
        s.name for s in report.strategies
    ]


def test_caller_receives_an_actionable_failure_list(strategies_dir: Path) -> None:
    """From the caller's side: the absence is data, not just a log line."""
    _write_strategy(strategies_dir, "broken_one", MISCONFIGURED_ENTRY)
    _write_strategy(strategies_dir, "healthy_one", HEALTHY_ENTRY)

    report = StrategyFactory.build_roster(asset_class="stock", enabled_only=True)

    assert [s.name for s in report.strategies] == ["healthy_one"]
    assert [f.name for f in report.misconfigured] == ["broken_one"]

    failure = report.misconfigured[0]
    assert failure.asset_class == "stock"
    assert failure.error_type == "ValueError"
    assert MISCONFIG_MESSAGE in failure.message
    assert failure.deliberate is False


def test_disabled_strategy_is_absent_without_being_a_failure(
    strategies_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The deliverable: "I turned it off" is not confused with "it broke"."""
    _write_strategy(strategies_dir, "turned_off", HEALTHY_ENTRY, enabled=False)
    _write_strategy(strategies_dir, "broken_one", MISCONFIGURED_ENTRY)
    _write_strategy(strategies_dir, "healthy_one", HEALTHY_ENTRY)

    with caplog.at_level(logging.DEBUG):
        report = StrategyFactory.build_roster(asset_class="stock", enabled_only=True)

    assert [s.name for s in report.strategies] == ["healthy_one"]
    # Absent because the operator disabled it: no failure record, nothing to fix.
    assert "turned_off" not in [f.name for f in report.failures]
    # Absent because it is broken: recorded, and separable from the disabled one.
    assert [f.name for f in report.misconfigured] == ["broken_one"]
    assert not _records_about(caplog, "turned_off")


def test_deliberate_exclusion_is_not_reported_as_misconfiguration(
    strategies_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A strategy the factory excludes by design is not an operator error."""
    _write_strategy(strategies_dir, "excluded_one", EXCLUDED_ENTRY)
    _write_strategy(strategies_dir, "healthy_one", HEALTHY_ENTRY)

    with caplog.at_level(logging.DEBUG):
        report = StrategyFactory.build_roster(asset_class="stock", enabled_only=True)

    assert [f.name for f in report.deliberately_excluded] == ["excluded_one"]
    assert report.misconfigured == []

    about_excluded = _records_about(caplog, "excluded_one")
    assert about_excluded, "a deliberate exclusion must still be visible"
    assert not [r for r in about_excluded if r.levelno >= logging.ERROR], (
        "a designed exclusion was escalated to ERROR, which is exactly the "
        "confusion this classification exists to prevent"
    )


def test_empty_roster_caused_by_failures_is_critical(
    strategies_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Configured strategies, none built: the runtime will trade nothing."""
    _write_strategy(strategies_dir, "broken_one", MISCONFIGURED_ENTRY)
    _write_strategy(strategies_dir, "broken_two", MISCONFIGURED_ENTRY)

    with caplog.at_level(logging.DEBUG):
        report = StrategyFactory.build_roster(asset_class="stock", enabled_only=True)

    assert report.strategies == []
    assert len(report.misconfigured) == 2
    assert [
        r for r in caplog.records if r.levelno >= logging.CRITICAL
    ], "an empty roster caused by build failures was not raised to CRITICAL"


def test_empty_config_tree_is_not_reported_as_a_failure(
    strategies_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No strategies configured is a valid state, not a degraded roster."""
    with caplog.at_level(logging.DEBUG):
        report = StrategyFactory.build_roster(asset_class="stock", enabled_only=True)

    assert report.strategies == []
    assert report.failures == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_create_from_file_still_propagates(strategies_dir: Path) -> None:
    """The single-strategy entry point keeps raising; only create_all tolerates."""
    _write_strategy(strategies_dir, "broken_one", MISCONFIGURED_ENTRY)

    with pytest.raises(ValueError, match=MISCONFIG_MESSAGE):
        StrategyFactory.create_from_file("stock", "broken_one")


def test_deliberate_exclusion_is_catchable_as_a_configuration_error() -> None:
    """Existing ``except ConfigurationError`` callers keep working unchanged."""
    from shared.exceptions import ConfigurationError

    assert issubclass(StrategyDeliberatelyExcluded, ConfigurationError)
