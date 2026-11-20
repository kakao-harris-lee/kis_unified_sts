"""STATE-EV-004 EV-L3 integrated crash/restart suite — the outside orchestration."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_KERNEL_SRC = _REPO_ROOT / "tos" / "src"

_EVIDENCE_ID = "STATE-EV-004"
_WORKER_MODULE = "tos.staterestore._l3_worker"
_COMPONENT = (
    "CompositeState + durable staterestore store + restart reload + "
    "reconstruct_conservative, across a real process boundary"
)

_CRASH_EXIT = 137

_STORE_UNOPENABLE_EXIT = 71

_DIMENSION_KEYS = (
    "intent_state",
    "transmission_attempt_state",
    "broker_order_state",
    "knowledge_state",
    "capacity_state",
)

_FORBIDDEN_POST_RESTART_KNOWLEDGE = frozenset({"RECONCILED", "CONSISTENT"})

_CAPACITY_ORDER = (
    "RELEASED",
    "COMMITTED_UNBOUND",
    "ATTEMPT_BOUND",
    "POTENTIALLY_LIVE",
    "PARTIALLY_CONSUMED",
    "POSITION_CONSUMED",
    "RELEASE_PENDING_PROOF",
    "TRAPPED_CONSUMED",
    "QUARANTINED_UNKNOWN",
)


def _canonical(values: tuple[str, str, str, str, str]) -> str:
    """The five dimensions as one comparable string (the schedule's Expected/Observed)."""
    labels = ("INTENT", "ATTEMPT", "BROKER", "KNOWLEDGE", "CAPACITY")
    return "|".join(f"{label}={value}" for label, value in zip(labels, values))


class _Cell:
    """One design §4 catalog cell, as the **oracle** half."""

    def __init__(
        self,
        scenario_id: str,
        crash_point: str,
        anchor: tuple[str, str, str, str, str],
        *,
        min_capacity: str | None = None,
        required_broker: str | None = None,
        required_knowledge: str | None = None,
        expect_store_complete: bool = True,
        expect_filled: tuple[str, ...] = (),
        expect_fill_values: tuple[tuple[str, str], ...] = (),
        expect_cache_discarded: bool = False,
        expect_lossless_roundtrip: bool = False,
        basis: str = "",
    ) -> None:
        self.scenario_id = scenario_id
        self.crash_point = crash_point
        self.anchor = anchor
        self.min_capacity = min_capacity
        self.required_broker = required_broker
        self.required_knowledge = required_knowledge
        self.expect_store_complete = expect_store_complete
        self.expect_filled = expect_filled
        self.expect_fill_values = expect_fill_values
        self.expect_cache_discarded = expect_cache_discarded
        self.expect_lossless_roundtrip = expect_lossless_roundtrip
        self.basis = basis

    @property
    def expected(self) -> str:
        """The canonical Expected string for the schedule row."""
        return _canonical(self.anchor)


_CELLS: tuple[_Cell, ...] = (
    _Cell(
        "L3-01",
        "AFTER_DURABLE_SEND_STARTED_BEFORE_BROKER",
        ("ACTIVE", "SEND_STARTED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
        min_capacity="POTENTIALLY_LIVE",
        required_broker="UNKNOWN",
        basis="§13:198 — durable SEND_STARTED implies a possibly-live send",
    ),
    _Cell(
        "L3-02",
        "AFTER_MODELLED_NETWORK_TRANSMISSION",
        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
        min_capacity="POTENTIALLY_LIVE",
        required_broker="UNKNOWN",
        basis="VER:1045 'after network transmission' (MODELLED marker; residual R-N)",
    ),
    _Cell(
        "L3-03",
        "BEFORE_EVIDENCE_PERSISTENCE",
        ("ACTIVE", "SEND_STARTED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
        required_knowledge="UNOBSERVED",
        basis=(
            "VER:1046 'never defaults to RECONCILED' — the in-memory ACK that was "
            "never persisted must not be resurrected"
        ),
    ),
    _Cell(
        "L3-04",
        "AT_NON_TERMINAL_BROKER_ORDER_BOUNDARY",
        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
        min_capacity="POTENTIALLY_LIVE",
        required_broker="UNKNOWN",
        basis="§13:198 — a broker order that is not provably terminal is UNKNOWN",
    ),
    _Cell(
        "L3-05",
        "BETWEEN_DIMENSION_TRANSACTIONS_INCOMPLETE_STORE",
        ("ACTIVE", "SEND_STARTED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
        min_capacity="POTENTIALLY_LIVE",
        required_broker="UNKNOWN",
        expect_store_complete=False,
        expect_filled=("BROKER_ORDER", "KNOWLEDGE"),
        expect_fill_values=(("BROKER_ORDER", "UNKNOWN"), ("KNOWLEDGE", "UNOBSERVED")),
        basis="VER:1045 'incomplete stores' — absent dimensions fill conservatively",
    ),
    _Cell(
        "L3-06",
        "AFTER_STALE_OPTIMISTIC_CACHE",
        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
        required_knowledge="UNOBSERVED",
        expect_cache_discarded=True,
        basis="VER:1045 'stale caches' + §13:199 re-derive — the cache never flows in",
    ),
    _Cell(
        "L3-07",
        "AFTER_TERMINAL_FILL_WITH_POSITIVE_KNOWLEDGE",
        ("ACTIVE", "ACK_OBSERVED", "FILLED", "CONFLICTED", "POSITION_CONSUMED"),
        min_capacity="POTENTIALLY_LIVE",
        required_broker="FILLED",
        required_knowledge="CONFLICTED",
        basis=(
            "§13:198 terminal broker preserved + §13:199 positive knowledge downgraded "
            "(the both-ways positive canary: this cell FIRES the downgrade)"
        ),
    ),
    _Cell(
        "L3-08",
        "AFTER_COMPLETE_DURABLE_COMMIT",
        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "CONFLICTED", "POTENTIALLY_LIVE"),
        min_capacity="POTENTIALLY_LIVE",
        required_broker="UNKNOWN",
        expect_lossless_roundtrip=True,
        basis=(
            "§13:197 durable + AC-005-1:237 'representable and persisted' — an already "
            "conservative composite round-trips losslessly and the projection is the "
            "identity"
        ),
    ),
)

_CELLS_BY_ID = {cell.scenario_id: cell for cell in _CELLS}


class _Worker(NamedTuple):
    """One finished worker process, as observed from outside it."""

    pid: int
    returncode: int
    stdout: str
    stderr: str


def _spawn(mode: str, scenario_id: str, store: Path, cache: Path) -> _Worker:
    """Run one worker process to completion and report what was observed."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONPATH": str(_KERNEL_SRC),
        "PYTHONHASHSEED": "0",
        "LC_ALL": "C",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            _WORKER_MODULE,
            mode,
            scenario_id,
            str(store),
            str(cache),
        ],
        cwd=str(_REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = proc.communicate()
    return _Worker(proc.pid, proc.returncode, stdout, stderr)


def journal_mode_of(path: Path) -> str:
    """What ``PRAGMA journal_mode`` reports for the file at ``path``."""
    if not path.is_file():
        return "<unreadable>"
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:  # pragma: no cover - only on an unopenable file
        return "<unreadable>"
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
    except sqlite3.Error:  # pragma: no cover - only on a corrupt file
        return "<unreadable>"
    finally:
        conn.close()
    return "<unreadable>" if row is None else str(row[0]).lower()


def _run_scenario(scenario_id: str, workdir: Path) -> dict:
    """Crash a writer, then reload in a fresh process. Returns the measured facts."""
    store = workdir / f"{scenario_id}.sqlite3"
    cache = workdir / f"{scenario_id}.cache.json"

    writer = _spawn("writer", scenario_id, store, cache)

    store_exists = store.is_file()
    store_bytes = store.stat().st_size if store_exists else 0
    store_journal_mode = journal_mode_of(store)

    reader = _spawn("reader", scenario_id, store, cache)

    return {
        "store": store,
        "cache": cache,
        "writer": writer,
        "reader": reader,
        "store_real_on_disk": store_exists,
        "store_bytes": store_bytes,
        "store_journal_mode": store_journal_mode,
    }


@pytest.fixture(scope="module")
def crash_runs(tmp_path_factory) -> dict[str, dict]:
    """Execute all eight §4 crash scenarios once, in catalog order (deterministic)."""
    workdir = tmp_path_factory.mktemp("tos-l3-crash")
    return {
        cell.scenario_id: _run_scenario(cell.scenario_id, workdir) for cell in _CELLS
    }


@pytest.mark.parametrize("cell", _CELLS, ids=lambda c: c.scenario_id)
def test_crash_restart_reconstructs_the_hand_derived_anchor(
    cell: _Cell, crash_runs: dict[str, dict], l3_crash_timeline
) -> None:
    """The §4 catalog, both anchor layers, plus the two structural boundary facts."""
    run = crash_runs[cell.scenario_id]
    writer: _Worker = run["writer"]
    reader: _Worker = run["reader"]

    assert writer.returncode == _CRASH_EXIT, (
        f"{cell.scenario_id}: writer exited {writer.returncode} "
        f"(expected the deterministic crash {_CRASH_EXIT}); stderr={writer.stderr}"
    )
    assert reader.returncode == 0, f"reader failed: {reader.stderr}"

    assert run["store_real_on_disk"] is True, "the store is not a real on-disk file"
    assert run["store_bytes"] > 0, "an empty store file evidences nothing"
    assert run["store_journal_mode"] == "wal", (
        "the crashed writer left the store in journal_mode="
        f"{run['store_journal_mode']!r}, not WAL — the durability argument every "
        "anchor below rests on assumes WAL"
    )

    verdict = json.loads(reader.stdout.strip().splitlines()[-1])
    assert writer.pid != reader.pid, "writer and reader share a pid"
    assert verdict["pid"] == reader.pid, (
        "the reader's self-reported pid disagrees with the pid this orchestrator "
        "spawned — the verdict may not come from the process that was measured"
    )
    writer_verdict = json.loads(writer.stdout.strip().splitlines()[-1])
    assert writer_verdict["pid"] == writer.pid

    observed = _canonical(tuple(verdict[key] for key in _DIMENSION_KEYS))

    assert verdict["knowledge_state"] not in _FORBIDDEN_POST_RESTART_KNOWLEDGE, (
        f"{cell.scenario_id}: post-restart Knowledge is "
        f"{verdict['knowledge_state']} — ADR-002-005 §13 line 199 forbids re-arriving "
        "at positive knowledge across a restart"
    )
    assert observed == cell.expected, f"{cell.scenario_id} ({cell.basis})"

    if cell.min_capacity is not None:
        assert _CAPACITY_ORDER.index(
            verdict["capacity_state"]
        ) >= _CAPACITY_ORDER.index(
            cell.min_capacity
        ), f"{cell.scenario_id}: capacity is less conservative than {cell.min_capacity}"
    if cell.required_broker is not None:
        assert verdict["broker_order_state"] == cell.required_broker
    if cell.required_knowledge is not None:
        assert verdict["knowledge_state"] == cell.required_knowledge
    assert verdict["store_complete"] is cell.expect_store_complete
    assert tuple(verdict["filled_dimensions"]) == cell.expect_filled
    for dimension, expected_fill in cell.expect_fill_values:
        assert verdict["committed_dimensions_readback"][dimension] == expected_fill, (
            f"{cell.scenario_id}: the absent {dimension} was filled with "
            f"{verdict['committed_dimensions_readback'][dimension]} — VER:1045 "
            "requires an incomplete store to fill conservatively, and an optimistic "
            "fill is a fail-open even when a later projection happens to mask it"
        )
    if cell.expect_cache_discarded:
        assert verdict["discarded_caches"], "the stale cache was never written"
        assert (
            verdict["cache_present_after_reload"] is False
        ), "the optimistic cache survived the reload — it must be discarded, not kept"
    if cell.expect_lossless_roundtrip:
        readback = tuple(
            verdict["committed_dimensions_readback"][dimension]
            for dimension in (
                "INTENT",
                "TRANSMISSION_ATTEMPT",
                "BROKER_ORDER",
                "KNOWLEDGE",
                "CAPACITY",
            )
        )
        assert (
            readback == cell.anchor
        ), "the durable round-trip lost or altered a committed dimension"

    l3_crash_timeline.record(
        scenario_id=cell.scenario_id,
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        crash_point=cell.crash_point,
        crash_exit_status=writer.returncode,
        writer_pid=writer.pid,
        reader_pid=reader.pid,
        store_real_on_disk=run["store_real_on_disk"],
        store_bytes=run["store_bytes"],
        store_journal_mode=run["store_journal_mode"],
        expected_reconstruction=cell.expected,
        observed_reconstruction=observed,
    )


def test_the_catalog_is_the_eight_design_cells_and_no_row_is_silently_dropped(
    crash_runs: dict[str, dict],
) -> None:
    """∅-seal, both directions (design §0.5-2): the catalog size is itself pinned."""
    assert [cell.scenario_id for cell in _CELLS] == [
        "L3-01",
        "L3-02",
        "L3-03",
        "L3-04",
        "L3-05",
        "L3-06",
        "L3-07",
        "L3-08",
    ]
    assert set(crash_runs) == set(_CELLS_BY_ID)


def test_every_anchor_is_falsifiable_and_no_two_cells_are_the_same_observation(
    crash_runs: dict[str, dict],
) -> None:
    """A catalog whose cells all expect the same thing evidences almost nothing."""
    for cell in _CELLS:
        assert cell.expected and "=" in cell.expected
    assert len({cell.expected for cell in _CELLS}) >= 3


def test_a_store_no_writer_ever_touched_is_refused_not_fabricated(tmp_path) -> None:
    """The reader derives from the store — it does not emit a constant."""
    store = tmp_path / "never-written.sqlite3"
    cache = tmp_path / "never-written.cache.json"
    reader = _spawn("reader", "L3-01", store, cache)
    assert reader.returncode != 0, f"an empty store produced a verdict: {reader.stdout}"
    assert (
        "IncompleteStoreError" in reader.stderr
        or "cannot be identified" in reader.stderr
    )


def test_a_store_that_cannot_be_opened_is_a_classified_refusal(tmp_path) -> None:
    """An unopenable substrate exits with its OWN code, not an unhandled traceback."""
    store = tmp_path / "a-directory-not-a-store"
    store.mkdir()
    cache = tmp_path / "unused.cache.json"

    reader = _spawn("reader", "L3-01", store, cache)

    assert reader.returncode == _STORE_UNOPENABLE_EXIT, (
        f"expected the classified substrate refusal {_STORE_UNOPENABLE_EXIT}, got "
        f"{reader.returncode}; stderr={reader.stderr}"
    )
    assert "could not be opened" in reader.stderr


def test_a_writer_that_cannot_open_the_store_is_a_classified_refusal(tmp_path) -> None:
    """**Review round-2 F3.** The writer classifies its open the way the reader does."""
    store = tmp_path / "a-directory-not-a-store"
    store.mkdir()
    cache = tmp_path / "unused.cache.json"

    writer = _spawn("writer", "L3-01", store, cache)

    assert writer.returncode == _STORE_UNOPENABLE_EXIT, (
        f"expected the classified substrate refusal {_STORE_UNOPENABLE_EXIT}, got "
        f"{writer.returncode}; stderr={writer.stderr}"
    )
    assert "could not be opened" in writer.stderr


def test_a_read_error_after_a_successful_open_is_not_the_substrate_code(
    tmp_path,
) -> None:
    """**Review round-2 F4.** The other side of the boundary, and the one that was wrong."""
    store = tmp_path / "wrong-shape.sqlite3"
    conn = sqlite3.connect(str(store))
    try:
        conn.execute("CREATE TABLE dimension_marker (unexpected TEXT)")
        conn.commit()
    finally:
        conn.close()
    cache = tmp_path / "unused.cache.json"

    reader = _spawn("reader", "L3-01", store, cache)

    assert reader.returncode != _STORE_UNOPENABLE_EXIT, (
        "a read-time error was reported as a substrate refusal; stderr="
        f"{reader.stderr}"
    )
    assert reader.returncode != 0
    assert "could not be opened" not in reader.stderr
    assert "no such column" in reader.stderr


def test_the_verdict_follows_the_store_not_the_scenario_argument(
    crash_runs: dict[str, dict],
) -> None:
    """Reading L3-07's store while claiming to be L3-01 must report L3-07's state."""
    seven = crash_runs["L3-07"]
    reader = _spawn("reader", "L3-01", seven["store"], seven["cache"])
    assert reader.returncode == 0, reader.stderr
    verdict = json.loads(reader.stdout.strip().splitlines()[-1])
    observed = _canonical(tuple(verdict[key] for key in _DIMENSION_KEYS))
    assert observed == _CELLS_BY_ID["L3-07"].expected
    assert observed != _CELLS_BY_ID["L3-01"].expected


def test_a_rollback_journal_store_is_measured_as_such(tmp_path) -> None:
    """**Review round-3 F9's negative case, on a REAL file rather than on an AST.**"""
    rollback = tmp_path / "rollback.sqlite3"
    conn = sqlite3.connect(str(rollback))
    try:
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.commit()
    finally:
        conn.close()

    assert journal_mode_of(rollback) == "delete"
    assert rollback.stat().st_size > 0

    switched = tmp_path / "wal.sqlite3"
    conn = sqlite3.connect(str(switched))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.commit()
    finally:
        conn.close()

    assert journal_mode_of(switched) == "wal"


def test_a_missing_store_reads_as_unreadable_not_as_a_mode(tmp_path) -> None:
    """∅-seal on the measurement: an absent file must not answer with a plausible mode."""
    assert journal_mode_of(tmp_path / "never-created.sqlite3") == "<unreadable>"


def test_this_suite_never_imports_the_kernel_it_measures() -> None:
    """TOS-FW-R as a *local* canary — the oracle-independence guarantee (§5.3 / O-3)."""
    import ast

    for path in sorted(Path(__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not (
                        alias.name == "tos" or alias.name.startswith("tos.")
                    ), f"{path.name}:{node.lineno} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not (
                    not node.level and (module == "tos" or module.startswith("tos."))
                ), f"{path.name}:{node.lineno} imports from {module}"
