"""``load_release_config`` tests (design #40 §5 order 6, lane R item 4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.sci import AdmissionResult
from tos_runtime.release.config import ReleaseAdmissionConfigError, load_release_config

_VALID = """
expected_code_digest: "digest-abc"
admission_result: "ADMIT"
restriction_state_resolved: true
restriction_present: false
restriction:
  restriction_id: null
  restriction_generation: null
  trigger_class: null
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "release.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(tmp_path / "does-not-exist.yaml")


def test_valid_config_loads(tmp_path: Path) -> None:
    path = _write(tmp_path, _VALID)
    config = load_release_config(path)
    assert config.expected_code_digest == "digest-abc"
    assert config.admission_result is AdmissionResult.ADMIT
    assert config.restriction_state_resolved is True
    assert config.restriction_present is False
    assert config.restriction is None


def test_null_expected_code_digest_refuses(tmp_path: Path) -> None:
    text = _VALID.replace(
        'expected_code_digest: "digest-abc"', "expected_code_digest: null"
    )
    path = _write(tmp_path, text)
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(path)


def test_null_admission_result_refuses(tmp_path: Path) -> None:
    text = _VALID.replace('admission_result: "ADMIT"', "admission_result: null")
    path = _write(tmp_path, text)
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(path)


def test_invalid_admission_result_string_refuses(tmp_path: Path) -> None:
    text = _VALID.replace(
        'admission_result: "ADMIT"', 'admission_result: "NOT_A_RESULT"'
    )
    path = _write(tmp_path, text)
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(path)


def test_null_restriction_state_resolved_refuses(tmp_path: Path) -> None:
    text = _VALID.replace(
        "restriction_state_resolved: true", "restriction_state_resolved: null"
    )
    path = _write(tmp_path, text)
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(path)


def test_null_restriction_present_refuses(tmp_path: Path) -> None:
    text = _VALID.replace("restriction_present: false", "restriction_present: null")
    path = _write(tmp_path, text)
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(path)


def test_restriction_present_true_with_unfilled_restriction_refuses(
    tmp_path: Path,
) -> None:
    text = _VALID.replace("restriction_present: false", "restriction_present: true")
    path = _write(tmp_path, text)
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(path)


def test_restriction_present_true_with_filled_restriction_loads(tmp_path: Path) -> None:
    text = _VALID.replace("restriction_present: false", "restriction_present: true")
    text = text.replace("restriction_id: null", 'restriction_id: "r-1"')
    text = text.replace("restriction_generation: null", "restriction_generation: 1")
    path = _write(tmp_path, text)
    config = load_release_config(path)
    assert config.restriction_present is True
    assert config.restriction is not None
    assert config.restriction.restriction_id == "r-1"
    assert config.restriction.canonical_digest is not None


def test_example_file_is_all_named_tbd() -> None:
    """The shipped example file must itself refuse to load."""
    example = Path(__file__).resolve().parents[2] / "config" / "release.example.yaml"
    with pytest.raises(ReleaseAdmissionConfigError):
        load_release_config(example)
