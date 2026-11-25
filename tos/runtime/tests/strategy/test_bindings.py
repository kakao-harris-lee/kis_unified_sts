"""Tests for ``tos_runtime.strategy.bindings``."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

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
    mapping: dict[str, Any] = {
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


def test_named_tbd_placeholder_in_bindings_refuses_naming_the_key(
    tmp_path: Path,
) -> None:
    """The null-only leaf walk must also catch the literal placeholder"""
    path = tmp_path / STRATEGY_BINDINGS_FILE_NAME
    mapping = {
        "strategies": {
            "example.strategy": {
                "config_binding_version": "cfg-1",
                "bindings": {"threshold": "TBD"},
            }
        }
    }
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    with pytest.raises(StrategyBindingsLoadError) as excinfo:
        load_strategy_bindings(path)
    message = str(excinfo.value)
    assert "threshold" in message
    assert "template placeholder" in message


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
    """``bindings`` is flat scalar leaves only (module docstring) — a nested"""
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
    """``tos/runtime/config/strategy_bindings.example.yaml`` documents the"""
    example_path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "strategy_bindings.example.yaml"
    )
    assert example_path.is_file()
    with pytest.raises(StrategyBindingsLoadError, match="null"):
        load_strategy_bindings(example_path)
