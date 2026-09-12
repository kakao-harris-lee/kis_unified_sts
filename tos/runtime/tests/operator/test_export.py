"""Hermetic tests for :class:`tos_runtime.operator.export.ProjectionExporter` (TOS Phase 5 W4
plan §2 decision 7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos_runtime.operator.export import ProjectionExporter
from tos_runtime.operator.projection import OperatorProjection

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_GROUP_NAMES = (
    "runtime",
    "recovery",
    "driver",
    "time",
    "safety_mesh",
    "currentness",
    "rcl",
    "inbox",
    "evidence",
    "release",
    "protective",
    "operations",
)


def _projection() -> OperatorProjection:
    readers = {
        f"read_{name}": (lambda n=name: {"populated": n}) for name in _GROUP_NAMES
    }
    return OperatorProjection(
        read_unresolved_stm_alert_candidate_seqs=lambda: (),
        read_resolved_stm_alert_seqs=lambda: (),
        **readers,
    )


def test_export_writes_a_document_that_round_trips_through_json_load(
    tmp_path: Path,
) -> None:
    path = tmp_path / "operator_projection.json"
    exporter = ProjectionExporter(path=path, projection=_projection())

    exporter.export()

    assert path.is_file()
    loaded = json.loads(path.read_text())
    assert loaded["schema_version"] == 1
    assert loaded["projection_generation"] == 1
    assert loaded["non_authorizing"] is True
    assert exporter.failures == 0
    assert exporter.last_error is None


def test_export_is_atomic_no_tmp_file_survives_a_successful_export(
    tmp_path: Path,
) -> None:
    path = tmp_path / "operator_projection.json"
    exporter = ProjectionExporter(path=path, projection=_projection())

    exporter.export()

    tmp_path_candidate = path.with_suffix(".tmp")
    assert not tmp_path_candidate.exists()


def test_export_creates_missing_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / "operator_projection.json"
    exporter = ProjectionExporter(path=path, projection=_projection())

    exporter.export()

    assert path.is_file()


def test_export_repeated_calls_increment_projection_generation_in_the_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "operator_projection.json"
    projection = _projection()
    exporter = ProjectionExporter(path=path, projection=projection)

    exporter.export()
    first_generation = json.loads(path.read_text())["projection_generation"]
    exporter.export()
    second_generation = json.loads(path.read_text())["projection_generation"]

    assert second_generation > first_generation


def test_export_failure_is_counted_and_never_raises(tmp_path: Path) -> None:
    """An unwritable destination directory (its parent path is actually a FILE, not a directory,
    so ``mkdir(parents=True)`` cannot create it) must be caught, counted, and must never raise
    out of :meth:`ProjectionExporter.export` (module docstring's "failure never reaches the
    caller")."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    path = blocker / "sub" / "operator_projection.json"
    exporter = ProjectionExporter(path=path, projection=_projection())

    exporter.export()  # must not raise

    assert exporter.failures == 1
    assert exporter.last_error is not None
    assert not path.exists()


def test_export_failure_leaves_no_partial_file_at_the_real_path(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    path = blocker / "sub" / "operator_projection.json"
    exporter = ProjectionExporter(path=path, projection=_projection())

    exporter.export()

    assert not path.exists()
    assert exporter.failures == 1


def test_as_after_turn_callback_returns_a_zero_argument_callable_bound_to_export(
    tmp_path: Path,
) -> None:
    path = tmp_path / "operator_projection.json"
    exporter = ProjectionExporter(path=path, projection=_projection())

    callback = exporter.as_after_turn_callback()
    assert callback() is None
    assert path.is_file()
