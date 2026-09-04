"""EV-L3 crash-schedule capture — the outside orchestration's only wiring.

Isomorphic to ``tos/tests/conftest.py`` (the EV-L2 fault-schedule sink), extended to the
EV-L3 integrated crash/restart stage per the ratified design contract
``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` §6.1: the append-only schedule
artifact VER-002-001 §9.1 requires ("test identity, baseline, seed, and fault schedule
SHALL be append-only").

Why a pytest option and not an environment variable: the option is how the evidence
harness (``tools/tos_evidence_run.py``) hands the run-scoped sink path to the suite,
exactly as ``--l2-fault-timeline`` already does. When the option is absent (a plain
developer ``pytest tests/tos_l3``) **no file is written and nothing is skipped** — the
crash assertions still execute. The timeline is an evidence artifact, never a
precondition of the tests.

⚠ This directory is **outside** ``tos/``. The firewall's forward rules (allowlist /
forbidden stdlib / ``os.environ``) do not apply here — ``subprocess`` is legitimate —
but the **reverse** rule TOS-FW-R does: ``tools/tos_firewall_check.py``'s
``_walk_repo_py`` prunes ONLY an explicit set of repo-root-relative VCS/generated
roots plus the repo-root ``tos/`` directory (each matched by resolved-path identity,
never by name or at any depth); ``tests/tos_l3`` is none of those roots, so nothing
here may ``import tos``. That prohibition is not an inconvenience, it is the design's
structural oracle-independence guarantee (§5.3 / O-3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

#: The fixed seed the EV-L3 crash schedule is executed under (design §4 "seed=0"). The
#: catalog is a deterministic enumeration rather than a sampled one, so the seed is
#: recorded for reproducibility of the surrounding property assertions and of the run
#: record itself (VER §9.1), not because the crash points are randomised.
L3_CRASH_SEED = 0

#: Outcome vocabulary (design §6.1, inherited from the EV-L2 schedule). A single
#: ``DEVIATION`` forbids a GREEN run.
OUTCOME_MET = "MET"
OUTCOME_DEVIATION = "DEVIATION"

#: The exact ordered field set of one crash-timeline row (design §6.2 — the harness's
#: six gates must each be re-derivable from these fields alone).
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
    """Append-only sink for EV-L3 crash rows (design §6.1).

    Each :meth:`record` call appends exactly one JSON object — the file is opened in
    append mode per row, so a row that has been written is never rewritten and an
    aborted session still leaves every scenario it reached (VER §9.1 / §2.2: a failed
    run is preserved, not replaced).

    ``outcome`` is **derived**, never passed in: a row is ``MET`` only when the expected
    reconstruction is a concrete non-empty string, the observed reconstruction equals
    it, **and** the two structural boundary facts hold (a real process boundary —
    distinct positive pids — and a real on-disk store). A missing expectation is
    therefore structurally a ``DEVIATION`` and can never be silently counted as met
    (design §0.5-2 / §0.5-4: only falsifiable Expecteds are admissible, and "0 crashes
    injected" is not "no violations").
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
        scenario_id: str,
        evidence_id: str,
        target_component: str,
        crash_point: str,
        crash_exit_status: int,
        writer_pid: int,
        reader_pid: int,
        store_real_on_disk: bool,
        store_bytes: int,
        expected_reconstruction: str,
        observed_reconstruction: str,
    ) -> dict[str, Any]:
        """Append one crash row and return it.

        Args:
            scenario_id: The design §4 catalog id (``L3-01`` … ``L3-08``).
            evidence_id: The Evidence Register row this crash scenario belongs to.
            target_component: The integrated components under crash injection.
            crash_point: Where the deterministic crash landed, named structurally.
            crash_exit_status: The writer process's **observed** exit status.
            writer_pid: The crashed writer's OS pid, observed by this orchestrator.
            reader_pid: The fresh reader's OS pid, observed by this orchestrator.
            store_real_on_disk: Whether the store file existed on the filesystem after
                the writer died — measured with :meth:`pathlib.Path.is_file`, never
                self-reported by the worker.
            store_bytes: The store file's size after the crash.
            expected_reconstruction: The hand-derived §4 anchor, as the canonical
                five-dimension string. Derived independently of the implementation:
                nothing outside ``tos/`` can call ``reconstruct_conservative``.
            observed_reconstruction: The same string built from the fresh reader's
                stdout verdict.

        Returns:
            The appended row.
        """
        boundary_real = writer_pid > 0 and reader_pid > 0 and writer_pid != reader_pid
        met = (
            bool(expected_reconstruction)
            and observed_reconstruction == expected_reconstruction
            and boundary_real
            and store_real_on_disk
            and store_bytes > 0
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
