"""``from_yaml()`` must read the shipped setup YAML, not fall back to defaults.

These configs declare ``_default_section = "strategy.entry.params"`` — a dotted
path, never a literal top-level key.  Before the dotted-path fix the section
lookup fell through to "use the whole document", every key mismatched the model
fields, ``extra="ignore"`` dropped them, and ``from_yaml()`` returned pure
Pydantic defaults *without raising*.

The production path (``StrategyFactory`` -> ``EntryRegistry.create``) hands the
already-extracted ``params`` dict to the model and was never affected; these
tests pin the ``from_yaml()`` diagnostic path against the real shipped files.
"""

from __future__ import annotations

import os

import pytest
import yaml

from shared.config.base import ConfigLoader
from shared.strategy.entry.setup_entry_configs import (
    SetupAEntryConfig,
    SetupCEntryConfig,
    SetupDEntryConfig,
)

SETUP_CONFIGS = [
    pytest.param(SetupAEntryConfig, id="setup_a"),
    pytest.param(SetupCEntryConfig, id="setup_c"),
    pytest.param(SetupDEntryConfig, id="setup_d"),
]


def _shipped_params(config_cls: type) -> dict:
    """Read ``strategy.entry.params`` straight out of the shipped YAML file."""
    path = os.path.join(
        str(ConfigLoader.get_config_dir()), config_cls._default_config_file
    )
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return raw["strategy"]["entry"]["params"]


def test_setup_c_from_yaml_reads_shipped_values() -> None:
    """The three fields the silent-fallback bug was measured against."""
    cfg = SetupCEntryConfig.from_yaml()

    assert cfg.no_entry_after_minutes_since_open == 375  # default is 360
    assert cfg.daily_bias_filter_enabled is False  # default is True
    assert cfg.llm_tuning.enabled is True  # default is False


@pytest.mark.parametrize("config_cls", SETUP_CONFIGS)
def test_from_yaml_matches_every_shipped_param(config_cls: type) -> None:
    """Every modelled key in the YAML must survive the round trip.

    Guards against a partial fix that resolves the section but drops values.
    """
    cfg = config_cls.from_yaml()
    fields = type(cfg).model_fields

    checked = 0
    for key, expected in _shipped_params(config_cls).items():
        if key not in fields:
            continue  # e.g. regime_gate, consumed by StrategyFactory, not the model
        actual = getattr(cfg, key)
        if hasattr(actual, "model_dump"):
            actual = {k: v for k, v in actual.model_dump().items() if k in expected}
        assert actual == expected, f"{config_cls.__name__}.{key}"
        checked += 1

    assert checked > 0, "no modelled params compared — YAML shape changed?"


@pytest.mark.parametrize("config_cls", SETUP_CONFIGS)
def test_from_yaml_differs_from_bare_defaults(config_cls: type) -> None:
    """Anti-phantom: the shipped file must actually override *something*.

    If this ever passes trivially the test above proves nothing.
    """
    assert config_cls.from_yaml().model_dump() != config_cls().model_dump()
