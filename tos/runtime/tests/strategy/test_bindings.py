"""``tos_runtime.strategy.bindings`` tests (TOS Phase 3 슬라이스 D-R
``[D-R-3a]``, docs/plans/2026-09-09-tos-phase3-event-core-plan.md §1.2 finding
#9 disposition).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    LoadedStrategyBindings,
    OneStrategyBindings,
    StrategyBindingsLoadError,
    load_strategy_bindings,
)


def test_missing_file_is_typed_absent_not_an_error(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    result = load_strategy_bindings(path)
    assert isinstance(result, LoadedStrategyBindings)
    assert result.present is False
    assert result.strategies == {}
    assert result.sha256_digest is None


def test_happy_path_loads_one_entry(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    mapping = {
        "strategies": {
            "example.strategy": {
                "config_binding_version": "cfg-bind-1",
                "bindings": {"lower_band_threshold": 4_500_000},
            }
        }
    }
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")

    result = load_strategy_bindings(path)
    assert result.present is True
    assert result.sha256_digest == hashlib.sha256(path.read_bytes()).hexdigest()
    entry = result.strategies["example.strategy"]
    assert isinstance(entry, OneStrategyBindings)
    assert entry.config_binding_version == "cfg-bind-1"
    assert entry.bindings == {"lower_band_threshold": 4_500_000}


def test_empty_strategies_map_is_legitimate(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    path.write_text(yaml.safe_dump({"strategies": {}}), encoding="utf-8")
    result = load_strategy_bindings(path)
    assert result.present is True
    assert result.strategies == {}


def test_not_a_mapping_refuses(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError, match="top-level mapping"):
        load_strategy_bindings(path)


def test_malformed_yaml_refuses(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    path.write_text("not: valid: yaml: [[[", encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError, match="not valid YAML"):
        load_strategy_bindings(path)


def test_null_leaf_at_top_level_refuses_naming_the_field(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    mapping = {
        "strategies": {
            "example.strategy": {"config_binding_version": None, "bindings": {}}
        }
    }
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError) as excinfo:
        load_strategy_bindings(path)
    message = str(excinfo.value)
    assert str(path) in message
    assert "config_binding_version" in message
    # The load-bearing assertion: this exact phrase is ONLY produced by the
    # null-leaf walker, never by pydantic's own ValidationError message —
    # without the null-leaf check, config_binding_version's required `str`
    # type still makes pydantic reject `None`, but with a generic "shape"
    # message that happens to also mention the field name, which would let
    # the assertion above pass for the wrong reason.
    assert "still null (named-TBD)" in message


def test_null_leaf_in_bindings_refuses_naming_the_key(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    mapping = {
        "strategies": {
            "example.strategy": {
                "config_binding_version": "cfg-1",
                "bindings": {"threshold": None},
            }
        }
    }
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError) as excinfo:
        load_strategy_bindings(path)
    message = str(excinfo.value)
    assert "threshold" in message
    assert "still null (named-TBD)" in message


def test_unrecognized_key_refuses(tmp_path: Path) -> None:
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    mapping = {
        "strategies": {
            "example.strategy": {
                "config_binding_version": "cfg-1",
                "bindings": {},
                "not_a_real_field": "x",
            }
        }
    }
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError, match="shape"):
        load_strategy_bindings(path)


def test_nested_mapping_under_bindings_refuses_not_silently_flattened(
    tmp_path: Path,
) -> None:
    """``bindings`` is flat scalar leaves only (module docstring) — a nested
    mapping value is a shape error, never silently flattened."""
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    mapping = {
        "strategies": {
            "example.strategy": {
                "config_binding_version": "cfg-1",
                "bindings": {"nested": {"a": 1}},
            }
        }
    }
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError, match="shape"):
        load_strategy_bindings(path)


def test_example_yaml_is_refused_as_shipped() -> None:
    """``tos/runtime/config/strategy_bindings.example.yaml`` documents the
    shape with every value left as a named-TBD ``null`` — it must be
    refused exactly like any other still-null config file."""
    example_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "strategy_bindings.example.yaml"
    )
    assert example_path.is_file()
    with pytest.raises(StrategyBindingsLoadError, match="null"):
        load_strategy_bindings(example_path)
