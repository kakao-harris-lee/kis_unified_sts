"""tos kernel test-suite wiring — EV-L2 fault-schedule capture only.

The tos suite is otherwise conftest-free by design (``tos/pyproject.toml`` resolves
the rootdir to ``tos/`` precisely so the repo-root ``tests/conftest.py`` — which loads
``.env`` and scrubs credentials — is never an ancestor). This file adds **one** thing
and touches nothing else: the append-only EV-L2 **fault schedule** artifact required by
VER-002-001 §9.1 ("test identity, baseline, seed, and fault schedule SHALL be
append-only") and by the EV-L2 pilot design §6.1.

Why a pytest option and not an environment variable: ``os.environ`` / ``os.getenv`` is
forbidden anywhere under ``tos/`` — src *and* tests — by the import firewall (TOS-FW-C,
``tools/tos_firewall_check.py``), because capability must not be reachable via ambient
env. The evidence harness therefore passes ``--l2-fault-timeline=<run-dir>/
fault-timeline.jsonl`` as an ordinary pytest flag, and the run package closes over the
resulting file through ``sha256sums.txt``.

When the option is absent (a plain ``pytest tos/tests`` developer run) **no file is
written and nothing is skipped** — the fault assertions still execute. The timeline is
an evidence artifact, never a precondition of the tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

#: The fixed seed the EV-L2 fault schedule is executed under (design §3/§4 "seed=0"
#: + §6.1). Recorded on every row so the schedule is reproducible from the artifact
#: alone; the harness independently passes ``--hypothesis-seed=0`` and
#: ``PYTHONHASHSEED=0``.
L2_FAULT_SEED = 0

#: Outcome vocabulary (design §6.1). A single ``DEVIATION`` forbids a GREEN run.
OUTCOME_MET = "MET"
OUTCOME_DEVIATION = "DEVIATION"

#: The exact ordered field set of one fault-timeline row (design §6.1).
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
    """Append-only sink for EV-L2 fault rows (design §6.1).

    Each :meth:`record` call appends exactly one JSON object — the file is opened in
    append mode per row, so a row that has been written is never rewritten and an
    aborted session still leaves every fault it reached (VER §9.1 / §2.2: a failed run
    is preserved, not replaced).

    ``outcome`` is **derived**, never passed in: a row is ``MET`` only when the expected
    disposition is a concrete non-empty string **and** the observed disposition equals
    it. An absent / empty expected disposition is therefore structurally a
    ``DEVIATION`` and can never be silently counted as met (design §0.5-2 / §0.5-4:
    only falsifiable Expecteds are admissible, and "0 faults injected" is not "no
    violations").
    """

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
        """Append one fault row and return it.

        Args:
            fault_id: The catalog id (design §3 ``ST-*`` / §4 ``SPG-*``).
            evidence_id: The Evidence Register row this fault belongs to.
            target_component: The single component under controlled failure injection
                (VER-002-001 §5 EV-L2 line 146-148).
            guard_code_line: The **measured** ``path:line`` of the guard that realizes
                the expected disposition (design §3 line 163 v1.2: the fault timeline
                records the real guard line, never a docstring anchor).
            fault_kind: A short structural name for the injection.
            input_witness_ref: A deterministic reference to the otherwise-valid witness
                the single mutation was applied to.
            expected_disposition: The falsifiable expected fail-closed disposition.
            observed_disposition: The **runtime-observed** disposition, derived from the
                structure of the result (never self-reported by the code under test).

        Returns:
            The appended row.
        """
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
