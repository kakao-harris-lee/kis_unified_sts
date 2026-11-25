"""tos kernel test-suite wiring — EV-L2 fault-schedule capture only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

L2_FAULT_SEED = 0

OUTCOME_MET = "MET"
OUTCOME_DEVIATION = "DEVIATION"

L2_TIMELINE_FIELDS: tuple[str, ...] = (
    "fault_id",
    "evidence_id",
    "target_component",
    "guard_code_line",
    "fault_kind",
    "seed",
    "input_witness_ref",
    "expected_disposition",
    "observed_disposition",
    "outcome",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register ``--l2-fault-timeline`` (the EV-L2 fault-schedule sink)."""
    parser.addoption(
        "--l2-fault-timeline",
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "append the EV-L2 fault schedule (one JSON object per fault, "
            "VER-002-001 §9.1 append-only) to PATH; omit to run the fault "
            "assertions without producing an evidence artifact"
        ),
    )


class L2FaultTimeline:
    """Append-only sink for EV-L2 fault rows (design §6.1)."""

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
        fault_id: str,
        evidence_id: str,
        target_component: str,
        guard_code_line: str,
        fault_kind: str,
        input_witness_ref: str,
        expected_disposition: str,
        observed_disposition: str,
    ) -> dict[str, Any]:
        """Append one fault row and return it."""
        met = (
            bool(expected_disposition) and observed_disposition == expected_disposition
        )
        row: dict[str, Any] = {
            "fault_id": fault_id,
            "evidence_id": evidence_id,
            "target_component": target_component,
            "guard_code_line": guard_code_line,
            "fault_kind": fault_kind,
            "seed": L2_FAULT_SEED,
            "input_witness_ref": input_witness_ref,
            "expected_disposition": expected_disposition,
            "observed_disposition": observed_disposition,
            "outcome": OUTCOME_MET if met else OUTCOME_DEVIATION,
        }
        assert tuple(row) == L2_TIMELINE_FIELDS
        self.rows.append(row)
        if self._path is not None:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=False, ensure_ascii=False) + "\n")
        return row


@pytest.fixture(scope="session")
def l2_fault_timeline(request: pytest.FixtureRequest) -> L2FaultTimeline:
    """The session-wide EV-L2 fault-schedule sink (design §6.1)."""
    raw = request.config.getoption("--l2-fault-timeline")
    return L2FaultTimeline(Path(raw) if raw else None)
