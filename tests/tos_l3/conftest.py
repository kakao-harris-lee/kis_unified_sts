"""EV-L3 crash-schedule capture — the outside orchestration's only wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

L3_CRASH_SEED = 0

OUTCOME_MET = "MET"
OUTCOME_DEVIATION = "DEVIATION"

L3_REQUIRED_JOURNAL_MODE = "wal"

L3_TIMELINE_FIELDS: tuple[str, ...] = (
    "scenario_id",
    "evidence_id",
    "target_component",
    "crash_point",
    "crash_exit_status",
    "seed",
    "writer_pid",
    "reader_pid",
    "store_real_on_disk",
    "store_bytes",
    "store_journal_mode",
    "expected_reconstruction",
    "observed_reconstruction",
    "outcome",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register ``--l3-crash-timeline`` (the EV-L3 crash-schedule sink)."""
    parser.addoption(
        "--l3-crash-timeline",
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "append the EV-L3 crash schedule (one JSON object per crash scenario, "
            "VER-002-001 §9.1 append-only) to PATH; omit to run the crash "
            "assertions without producing an evidence artifact"
        ),
    )


class L3CrashTimeline:
    """Append-only sink for EV-L3 crash rows (design §6.1)."""

    def __init__(self, path: Path | None) -> None:
        """Bind the sink to ``path`` (``None`` => in-memory only)."""
        self._path = path
        self.rows: list[dict[str, Any]] = []

    @property
    def path(self) -> Path | None:
        """The artifact path, or ``None`` when no artifact is being produced."""
        return self._path

    def record(
        self,
        *,
        scenario_id: str,
        evidence_id: str,
        target_component: str,
        crash_point: str,
        crash_exit_status: int,
        writer_pid: int,
        reader_pid: int,
        store_real_on_disk: bool,
        store_bytes: int,
        store_journal_mode: str,
        expected_reconstruction: str,
        observed_reconstruction: str,
    ) -> dict[str, Any]:
        """Append one crash row and return it."""
        boundary_real = writer_pid > 0 and reader_pid > 0 and writer_pid != reader_pid
        met = (
            bool(expected_reconstruction)
            and observed_reconstruction == expected_reconstruction
            and boundary_real
            and store_real_on_disk
            and store_bytes > 0
            and store_journal_mode.lower() == L3_REQUIRED_JOURNAL_MODE
        )
        row: dict[str, Any] = {
            "scenario_id": scenario_id,
            "evidence_id": evidence_id,
            "target_component": target_component,
            "crash_point": crash_point,
            "crash_exit_status": crash_exit_status,
            "seed": L3_CRASH_SEED,
            "writer_pid": writer_pid,
            "reader_pid": reader_pid,
            "store_real_on_disk": store_real_on_disk,
            "store_bytes": store_bytes,
            "store_journal_mode": store_journal_mode,
            "expected_reconstruction": expected_reconstruction,
            "observed_reconstruction": observed_reconstruction,
            "outcome": OUTCOME_MET if met else OUTCOME_DEVIATION,
        }
        assert tuple(row) == L3_TIMELINE_FIELDS
        self.rows.append(row)
        if self._path is not None:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=False, ensure_ascii=False) + "\n")
        return row


@pytest.fixture(scope="session")
def l3_crash_timeline(request: pytest.FixtureRequest) -> L3CrashTimeline:
    """The session-wide EV-L3 crash-schedule sink (design §6.1)."""
    raw = request.config.getoption("--l3-crash-timeline")
    return L3CrashTimeline(Path(raw) if raw else None)
