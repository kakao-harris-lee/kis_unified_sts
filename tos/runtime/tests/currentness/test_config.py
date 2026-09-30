"""``load_currentness_config`` tests (design #40 §5 order 6, lane R)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.cur import DimensionKey
from tos_runtime.currentness.config import (
    CurrentnessConfigError,
    load_currentness_config,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "currentness.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(tmp_path / "does-not-exist.yaml")


def test_missing_key_refuses(tmp_path: Path) -> None:
    path = _write(tmp_path, "other_key: 1\n")
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_null_key_refuses(tmp_path: Path) -> None:
    path = _write(tmp_path, "B_capability_claim_to_send: null\n")
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_negative_value_refuses(tmp_path: Path) -> None:
    path = _write(tmp_path, "B_capability_claim_to_send: -1\n")
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_non_int_value_refuses(tmp_path: Path) -> None:
    path = _write(tmp_path, "B_capability_claim_to_send: 'soon'\n")
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_valid_config_loads(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "B_capability_claim_to_send: 500\n"
        "required_dimensions: [COMMIT_LOG, TRUSTWORTHY_TIME]\n",
    )
    config = load_currentness_config(path)
    assert config.max_claim_to_send_bound_ms == 500
    assert config.required_dimensions == (
        DimensionKey.COMMIT_LOG,
        DimensionKey.TRUSTWORTHY_TIME,
    )


def test_example_file_is_all_named_tbd() -> None:
    """The shipped example file must itself refuse to load (every value is
    null/named-TBD) — it is a template, not a usable config."""
    example = (
        Path(__file__).resolve().parents[2] / "config" / "currentness.example.yaml"
    )
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(example)


# ============================================================================
# required_dimensions (W3.1 independent review MEDIUM-3)
# ============================================================================


def test_required_dimensions_missing_key_refuses(tmp_path: Path) -> None:
    path = _write(tmp_path, "B_capability_claim_to_send: 500\n")
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_required_dimensions_null_refuses(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "B_capability_claim_to_send: 500\nrequired_dimensions: null\n"
    )
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_required_dimensions_empty_list_refuses(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "B_capability_claim_to_send: 500\nrequired_dimensions: []\n"
    )
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_required_dimensions_non_list_refuses(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "B_capability_claim_to_send: 500\nrequired_dimensions: COMMIT_LOG\n",
    )
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_required_dimensions_unknown_member_refuses(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "B_capability_claim_to_send: 500\nrequired_dimensions: [NOT_A_REAL_DIMENSION]\n",
    )
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)


def test_required_dimensions_duplicate_member_refuses(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "B_capability_claim_to_send: 500\n"
        "required_dimensions: [COMMIT_LOG, COMMIT_LOG]\n",
    )
    with pytest.raises(CurrentnessConfigError):
        load_currentness_config(path)
