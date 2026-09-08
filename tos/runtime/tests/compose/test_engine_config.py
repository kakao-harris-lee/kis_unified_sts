"""``tos_runtime.compose._engine_config`` tests (F5, pre-merge fix,
2026-09-08). CLAUDE.md non-negotiable: "thresholds ... belong in YAML/env/
config files, not hardcoded branches" — ``dsl_evaluation_budget_steps``/
``max_unresolved_send_per_scope`` were bare literals in
``_wiring.py::_finalize``. Hermetic — real config files under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos_runtime.compose._engine_config import (
    EngineConfigError,
    load_engine_config,
)
from tos_runtime.compose._wiring import _build_engine_configuration

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _write(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def test_a_valid_file_loads(tmp_path: Path) -> None:
    path = tmp_path / "engine.yaml"
    _write(
        path, {"dsl_evaluation_budget_steps": 64, "max_unresolved_send_per_scope": 1}
    )
    config = load_engine_config(path)
    assert config.dsl_evaluation_budget_steps == 64
    assert config.max_unresolved_send_per_scope == 1


def test_missing_key_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "engine.yaml"
    _write(path, {"dsl_evaluation_budget_steps": 64})
    with pytest.raises(EngineConfigError):
        load_engine_config(path)


def test_null_value_refuses_to_load(tmp_path: Path) -> None:
    path = tmp_path / "engine.yaml"
    _write(
        path,
        {"dsl_evaluation_budget_steps": None, "max_unresolved_send_per_scope": 1},
    )
    with pytest.raises(EngineConfigError):
        load_engine_config(path)


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(EngineConfigError):
        load_engine_config(tmp_path / "does-not-exist.yaml")


def test_build_engine_configuration_flows_both_values_from_config(
    tmp_path: Path,
) -> None:
    """(i) Both values flow from the config file into ``EngineConfiguration``."""
    _write(
        tmp_path / "engine.yaml",
        {"dsl_evaluation_budget_steps": 77, "max_unresolved_send_per_scope": 3},
    )
    configuration = _build_engine_configuration(tmp_path)
    assert configuration.dsl_evaluation_budget_steps == 77
    assert configuration.max_unresolved_send_per_scope == 3
