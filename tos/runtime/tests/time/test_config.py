"""Hermetic tests for ``tos_runtime.time.config``."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos_runtime.time.config import TimeConfigError, load_time_config

_FULLY_VALUED: dict[str, object] = {
    "MAX_time_source_precision_ms": 5,
    "MAX_time_transport_and_queue_uncertainty_ms": 50,
    "MAX_time_conservative_freshness_age_ms": 1000,
    "MAX_future_timestamp_tolerance_ms": 200,
    "MAX_process_suspension_ms": 0,
    "MAX_time_source_disagreement_ms": 100,
    "MIN_time_independent_reference_count": 1,
    "MAX_clock_domain_conversion_uncertainty_ms": 50,
    "MAX_send_result_wait_ms": 5000,
    "MAX_critical_input_consumer_receipt_age_ms": 1000,
    "MAX_time_source_sequence_gap_ms": 50,
    "tz_db_version": "2026a",
    "trading_calendar_version": "cal-1",
    "verification_profile_version": "vp-0",
    "safety_profile_version": "sp-0",
    "time_health_snapshot_heartbeat_ms": 60_000,
}


def _write_yaml(path: Path, content: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TimeConfigError, match="not found"):
        load_time_config(tmp_path / "does-not-exist.yaml")


def test_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "time.yaml"
    path.write_text(yaml.safe_dump([1, 2, 3]), encoding="utf-8")
    with pytest.raises(TimeConfigError, match="mapping"):
        load_time_config(path)


def test_invalid_yaml_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "time.yaml"
    path.write_text("key: [unterminated", encoding="utf-8")
    with pytest.raises(TimeConfigError, match="not valid YAML"):
        load_time_config(path)


def test_missing_required_key_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    del content["MAX_time_source_precision_ms"]
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="missing required keys"):
        load_time_config(path)


def test_null_named_tbd_bound_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    content["MAX_time_conservative_freshness_age_ms"] = None
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="unfilled"):
        load_time_config(path)


def test_null_version_string_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    content["tz_db_version"] = None
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="non-blank string"):
        load_time_config(path)


def test_named_tbd_placeholder_version_string_is_rejected(tmp_path: Path) -> None:
    """A version string literally ``"TBD"`` is a template placeholder an"""
    content = dict(_FULLY_VALUED)
    content["tz_db_version"] = "TBD"
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="template placeholder"):
        load_time_config(path)


def test_negative_bound_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    content["MAX_process_suspension_ms"] = -1
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="non-negative"):
        load_time_config(path)


def test_zero_send_result_wait_bound_is_rejected(tmp_path: Path) -> None:
    """Every OTHER bound key accepts ``0``"""
    content = dict(_FULLY_VALUED)
    content["MAX_send_result_wait_ms"] = 0
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="positive int"):
        load_time_config(path)


def test_negative_send_result_wait_bound_is_also_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    content["MAX_send_result_wait_ms"] = -1
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="positive int"):
        load_time_config(path)


@pytest.mark.parametrize("value", [0, -1, "soon", True])
def test_bad_snapshot_heartbeat_is_rejected(tmp_path: Path, value: object) -> None:
    """``time_health_snapshot_heartbeat_ms`` is an operational key, not a VER-002 bound, and"""
    content = dict(_FULLY_VALUED)
    content["time_health_snapshot_heartbeat_ms"] = value
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="positive int"):
        load_time_config(path)


def test_missing_snapshot_heartbeat_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    del content["time_health_snapshot_heartbeat_ms"]
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="missing required keys"):
        load_time_config(path)


def test_null_snapshot_heartbeat_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    content["time_health_snapshot_heartbeat_ms"] = None
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="unfilled"):
        load_time_config(path)


def test_non_int_bound_is_rejected(tmp_path: Path) -> None:
    content = dict(_FULLY_VALUED)
    content["MAX_process_suspension_ms"] = "soon"
    path = _write_yaml(tmp_path / "time.yaml", content)
    with pytest.raises(TimeConfigError, match="non-negative int"):
        load_time_config(path)


def test_fully_valued_config_loads(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path / "time.yaml", _FULLY_VALUED)
    config = load_time_config(path)
    assert config.max_time_source_precision_ms == 5
    assert config.max_time_transport_and_queue_uncertainty_ms == 50
    assert config.max_time_conservative_freshness_age_ms == 1000
    assert config.max_future_timestamp_tolerance_ms == 200
    assert config.max_process_suspension_ms == 0
    assert config.max_time_source_disagreement_ms == 100
    assert config.min_time_independent_reference_count == 1
    assert config.tz_db_version == "2026a"
    assert config.trading_calendar_version == "cal-1"
    assert config.verification_profile_version == "vp-0"
    assert config.safety_profile_version == "sp-0"
    assert config.time_health_snapshot_heartbeat_ms == 60_000


def test_example_yaml_shape_matches_loader_keys() -> None:
    """The committed example file's keys must exactly match the loader's"""
    example_path = Path(__file__).resolve().parents[2] / "config" / "time.example.yaml"
    raw = yaml.safe_load(example_path.read_text(encoding="utf-8"))
    assert set(raw) == set(_FULLY_VALUED)
    assert all(value is None for value in raw.values())
