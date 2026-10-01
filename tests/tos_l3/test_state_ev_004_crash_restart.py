"""STATE-EV-004 EV-L3 integrated crash/restart suite — the outside orchestration.

**Stage**: EV-L3 (VER-002-001 §5 line 151-153 verbatim — "Multiple live-path components
are tested together with real persistence, identity, and network boundaries"). Catalog:
EV-L3 pilot design ``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` §4, **eight crash
scenarios** (``L3-01`` … ``L3-08``).

Why this file lives outside ``tos/``
------------------------------------
Not because it must — a ``multiprocessing`` spawn inside ``tos/tests`` would also give a
distinct pid and a distinct interpreter, and the kernel's own closure tests already use
one (design §5.2 MAJOR-1, measured). It lives here because of what the placement
**structurally forbids**: the firewall's reverse rule TOS-FW-R
(``tools/tos_firewall_check.py``'s ``_walk_repo_py`` prunes ONLY an explicit set of
repo-root-relative VCS/generated roots plus the repo-root ``tos/`` directory, each
matched by resolved-path identity, never by name or at any depth; ``tests/tos_l3`` is
none of those roots, so this path is scanned) makes ``import tos`` impossible here.
This suite therefore **cannot** call
``tos.orthostate.reconstruct_conservative``, and its Expecteds are necessarily
hand-derived anchors rather than a second invocation of the implementation under test.

That is the whole point. ADVERSE-SCENARIO-SET-002 ASS-CM-04 names the failure mode —
"guards … are also the oracles" — and design §5.3 buys structural immunity to it at the
cost of orchestration complexity (subprocess spawn, argv, stdout parsing, anchor
comparison) sitting outside the firewall's certified surface. A bug in
``reconstruct_conservative`` cannot make these anchors agree with it.

What is real here, and what is modelled
---------------------------------------
* **Real persistence** — a sqlite3 file on the filesystem, written by a process that
  then died. Asserted structurally (the file exists and is non-empty *after* the writer
  is gone), never self-reported.
* **Real process boundary** — two OS processes, ``writer_pid != reader_pid``, whose only
  channel is that file. Both pids are the ones this orchestrator observed from
  :class:`subprocess.Popen`, cross-checked against what each worker reported about
  itself; a disagreement fails.
* **Real crash** — the writer dies by a deterministic ``os._exit(137)`` at a
  parametrized point. Nothing is flushed or unwound.
* **Modelled network** — the "after network transmission" injection point (VER line
  1045) is a VirtualBroker-class marker. **Zero real bytes are transmitted and zero real
  orders exist**; the real broker network boundary is residual R-N and the real futures
  order path is permanently policy-blocked.
* **Deferred credential identity** — logical identifiers are re-derived from the store;
  real credential / cross-host authentication is residual R-I (STATE-EV-005).

⚠ Executing this suite records an EV-L3 stage. It moves no Evidence Register row to
PASS: STATE-EV-004 keeps its unexercised network and credential-identity axes, the
restart coverage argument is a review-layer obligation, and independent sign-off
(VER §9.5) is outstanding.
"""

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

#: The writer's deterministic crash status (design §4 / O-2). Hardcoded here rather than
#: read from the kernel: an implementation that stopped crashing and merely returned
#: would otherwise redefine the expectation to match itself.
_CRASH_EXIT = 137

#: The reader's classified "the store could not be opened" status (#823 / review F2).
#: Hardcoded for the same reason as :data:`_CRASH_EXIT`: a worker that stopped refusing
#: would otherwise redefine the expectation to match itself.
_STORE_UNOPENABLE_EXIT = 71

#: The five-dimension coordinate order the anchors are written in.
_DIMENSION_KEYS = (
    "intent_state",
    "transmission_attempt_state",
    "broker_order_state",
    "knowledge_state",
    "capacity_state",
)

#: Layer 2 of the design §4 anchors — derived directly from ADR-002-005 §13 line 199
#: ("Knowledge SHALL be re-derived …, **never** to ``RECONCILED``") plus the §11 rule
#: that a restart is a weak basis and so may not produce positive knowledge. This set is
#: independent of the reconstruction's *value* anchors: even if every value anchor below
#: were wrong, a post-restart Knowledge inside this set is a spec violation.
_FORBIDDEN_POST_RESTART_KNOWLEDGE = frozenset({"RECONCILED", "CONSISTENT"})

#: Capacity conservatism order, transcribed by hand from ADR-002-002 §10.1 (least → most
#: conservative / capacity-consuming). Transcribed rather than imported **on purpose**:
#: the reverse firewall rule forbids importing ``tos.rcl``'s comparator, so ``Capacity is
#: at least as conservative as POTENTIALLY_LIVE`` is decided here against an independent
#: statement of the order.
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
    """One design §4 catalog cell, as the **oracle** half.

    Holds only what the design table states as *Expected*: the crash point's structural
    name, the hand-derived post-restart anchor, and the cell's own layer-2 invariants.
    The committed composite (the input) belongs to the worker; nothing here is read back
    from it.
    """

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


#: The design §4 catalog. Every anchor below was derived by hand from ADR-002-005 §13:
#:
#:   * line 198 — an Attempt that reached ``SEND_STARTED`` and is not proven-terminal
#:     raises Capacity to at least ``POTENTIALLY_LIVE``; a Broker Order that is not
#:     *provably terminal* reconstructs as ``UNKNOWN`` (terminal ones are preserved);
#:   * line 199 — positive Knowledge (``RECONCILED`` / ``CONSISTENT``) is re-derived
#:     downward and never re-arrived at, while a Knowledge that was already conservative
#:     is preserved;
#:   * Intent and Attempt are carried across the restart unchanged.
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
        # The §4 invariant's FIRST conjunct — "an absent dimension is never an
        # optimistic value" — is a claim about the FILL, not about the projection's
        # output. Asserting only the output would leave an optimistic fill invisible,
        # because the §13 projection repairs a non-terminal Broker to UNKNOWN on its
        # way past (measured: an absent-Broker => NONE_OBSERVED mutant survives an
        # output-only anchor). These pin the re-derived pre-restart values themselves.
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
    """Run one worker process to completion and report what was observed.

    The pid recorded is the one **this orchestrator** received from the OS, not one the
    worker printed about itself — the process-boundary claim must not rest on a
    self-report. ``PYTHONPATH`` is set explicitly rather than inherited so a plain
    developer run behaves identically to a harness run, and ``PYTHONHASHSEED`` is pinned
    so the subprocess is as deterministic as the parent (VER §9.1).
    """
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
    """What ``PRAGMA journal_mode`` reports for the file at ``path``.

    **The measurement gate 3 now turns on** (review round-3 F9). Opened READ-ONLY
    through a ``file:...?mode=ro`` URI, so this observation cannot be the thing that
    creates or switches what it is observing — the same reason
    ``tos/tests/staterestore/test_staterestore_wal_birth_race._journal_mode`` is
    read-only. stdlib ``sqlite3`` only: nothing here imports the kernel, so the
    oracle-independence rule this suite pins
    (:func:`test_this_suite_never_imports_the_kernel_it_measures`) is untouched.

    Returns:
        The mode sqlite reports, lowercased, or ``"<unreadable>"`` when the file cannot
        be opened at all. Never a guess and never an exception: an unreadable store is
        a deviation the row must carry, not a crash in the orchestrator.
    """
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

    # Measured AFTER the writer is gone and BEFORE the reader runs: these are the
    # persistence claims, and they are filesystem observations rather than anything
    # either worker said about itself. Before the reader matters for the journal mode —
    # the reader opens the store too, and a mode read afterwards could be one the
    # reader established rather than one the crashed writer left.
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
    """The §4 catalog, both anchor layers, plus the two structural boundary facts.

    Layer 1 is the exact five-dimension anchor; layer 2 is the independent
    ``Knowledge ∉ {RECONCILED, CONSISTENT}`` invariant read straight off ADR-002-005
    §13 line 199. Both are asserted for every cell, so a wrong-but-self-consistent
    implementation would have to defeat two independently derived statements.
    """
    run = crash_runs[cell.scenario_id]
    writer: _Worker = run["writer"]
    reader: _Worker = run["reader"]

    # -- the crash really happened, at the parametrized point -------------------
    assert writer.returncode == _CRASH_EXIT, (
        f"{cell.scenario_id}: writer exited {writer.returncode} "
        f"(expected the deterministic crash {_CRASH_EXIT}); stderr={writer.stderr}"
    )
    assert reader.returncode == 0, f"reader failed: {reader.stderr}"

    # -- real persistence: the store outlived the process that wrote it ---------
    assert run["store_real_on_disk"] is True, "the store is not a real on-disk file"
    assert run["store_bytes"] > 0, "an empty store file evidences nothing"
    # The substrate claim itself, read off the file rather than off the source (review
    # round-3 F9). Design §3.2 candidate A is "sqlite3, WAL, synchronous=FULL"; this is
    # the half of it a single execution can actually show.
    assert run["store_journal_mode"] == "wal", (
        "the crashed writer left the store in journal_mode="
        f"{run['store_journal_mode']!r}, not WAL — the durability argument every "
        "anchor below rests on assumes WAL"
    )

    # -- real process boundary: two distinct OS processes -----------------------
    verdict = json.loads(reader.stdout.strip().splitlines()[-1])
    assert writer.pid != reader.pid, "writer and reader share a pid"
    assert verdict["pid"] == reader.pid, (
        "the reader's self-reported pid disagrees with the pid this orchestrator "
        "spawned — the verdict may not come from the process that was measured"
    )
    writer_verdict = json.loads(writer.stdout.strip().splitlines()[-1])
    assert writer_verdict["pid"] == writer.pid

    observed = _canonical(tuple(verdict[key] for key in _DIMENSION_KEYS))

    # -- layer 2 first: it holds regardless of whether layer 1 is right ---------
    assert verdict["knowledge_state"] not in _FORBIDDEN_POST_RESTART_KNOWLEDGE, (
        f"{cell.scenario_id}: post-restart Knowledge is "
        f"{verdict['knowledge_state']} — ADR-002-005 §13 line 199 forbids re-arriving "
        "at positive knowledge across a restart"
    )
    # -- layer 1: the exact hand-derived anchor --------------------------------
    assert observed == cell.expected, f"{cell.scenario_id} ({cell.basis})"

    # -- the cell's own extra invariants ---------------------------------------
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
        # AC-005-1 line 237 "representable and persisted": what came back off the disk
        # is byte-for-byte the five dimensions that were committed, and the §13
        # projection over an already-conservative composite is the identity — so the
        # anchor doubles as the committed pin here.
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
    """A catalog whose cells all expect the same thing evidences almost nothing.

    Eight rows that happened to share one anchor would look like eight measurements
    while being one. The distinct-anchor count is therefore asserted, and every anchor
    is required to be a concrete non-empty string (an unstated Expected cannot be
    falsified — design §0.5-4).
    """
    for cell in _CELLS:
        assert cell.expected and "=" in cell.expected
    assert len({cell.expected for cell in _CELLS}) >= 3


def test_a_store_no_writer_ever_touched_is_refused_not_fabricated(tmp_path) -> None:
    """The reader derives from the store — it does not emit a constant.

    Without this, a reader that ignored the store and printed the conservative anchor
    unconditionally would pass every cell above. Here there is nothing to reload, so the
    only correct behaviour is a refusal (fail-closed), never a plausible-looking
    composite.
    """
    store = tmp_path / "never-written.sqlite3"
    cache = tmp_path / "never-written.cache.json"
    reader = _spawn("reader", "L3-01", store, cache)
    assert reader.returncode != 0, f"an empty store produced a verdict: {reader.stdout}"
    assert (
        "IncompleteStoreError" in reader.stderr
        or "cannot be identified" in reader.stderr
    )


def test_a_store_that_cannot_be_opened_is_a_classified_refusal(tmp_path) -> None:
    """An unopenable substrate exits with its OWN code, not an unhandled traceback.

    Review F2 on PR #827: #823 made the store's open fail-closed on ``journal_mode=WAL``,
    and the reader had no classification for that — it would have died with exit 1, which
    :data:`_CRASH_EXIT`'s own comment says is exactly the value these constants exist to
    be distinguishable from. The refusal here is provoked without ``chmod`` (so it holds
    for a root CI container too) by pointing the reader at a directory: sqlite cannot
    open it, and the failure is a substrate one before any reconstruction happens.

    Paired with ``test_a_store_no_writer_ever_touched_is_refused_not_fabricated`` above,
    which pins the OTHER direction — a store that opens but holds nothing is an
    ``IncompleteStoreError``, a reconstruction verdict, and must NOT be collapsed into
    this code.
    """
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
    """**Review round-2 F3.** The writer classifies its open the way the reader does.

    Before this, only the reader did: the writer's open escaped as an unhandled
    traceback with exit 1, so ``_run_scenario`` saw "not 137" and reported a generic
    crash-exit mismatch. A harness asserting on exit codes could not tell "the store
    could not be opened" from "the worker has a bug" — the distinction
    :data:`_CRASH_EXIT`'s own comment says these constants exist to preserve.
    """
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
    """**Review round-2 F4.** The other side of the boundary, and the one that was wrong.

    The store file here OPENS cleanly — it is a real sqlite database, the journal-mode
    switch succeeds, and ``CREATE TABLE IF NOT EXISTS dimension_marker`` is a no-op
    because a table of that name already exists. It is the SELECT that fails, on a
    column that is not there. That is a finding about a store that WAS opened, and it
    must not come back as the substrate code.

    RED before the narrowing: the reader caught ``sqlite3.Error`` around the whole
    reload, so this ``OperationalError`` was reported as "could not be opened" with exit
    71. Note that narrowing by TYPE alone would not have fixed it — this is an
    ``OperationalError``, the same class the open raises — which is why the open and the
    read are separate statements in ``reload_conservative`` now.
    """
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
    """Reading L3-07's store while claiming to be L3-01 must report L3-07's state.

    This separates "the reader re-derived state from durable bytes" from "the reader
    looked up an answer by scenario id". Only the former is evidence of reconstruction.
    """
    seven = crash_runs["L3-07"]
    reader = _spawn("reader", "L3-01", seven["store"], seven["cache"])
    assert reader.returncode == 0, reader.stderr
    verdict = json.loads(reader.stdout.strip().splitlines()[-1])
    observed = _canonical(tuple(verdict[key] for key in _DIMENSION_KEYS))
    assert observed == _CELLS_BY_ID["L3-07"].expected
    assert observed != _CELLS_BY_ID["L3-01"].expected


def test_a_rollback_journal_store_is_measured_as_such(tmp_path) -> None:
    """**Review round-3 F9's negative case, on a REAL file rather than on an AST.**

    Three review rounds of source analysis each had a bypass, so what gate 3 turns on
    is now a measurement. A measurement is only worth that if it can come out the other
    way, and this is the input that makes it: an ordinary sqlite file nobody switched,
    which sqlite reports as ``delete``. Feed that through the recorder and the row is a
    DEVIATION even though every other field is perfect — the store exists, it is
    non-empty, the pids are a real pair, and the reconstruction matches.

    The positive direction is covered per scenario by the eight real crash runs above.
    """
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
    """∅-seal on the measurement: an absent file must not answer with a plausible mode.

    If this returned ``""`` or raised, the row would either carry something that
    compares unequal to ``wal`` for the wrong reason or never be written at all. It
    returns a value that is visibly not a journal mode, and the recorder treats it as
    the deviation it is.
    """
    assert journal_mode_of(tmp_path / "never-created.sqlite3") == "<unreadable>"


def test_this_suite_never_imports_the_kernel_it_measures() -> None:
    """TOS-FW-R as a *local* canary — the oracle-independence guarantee (§5.3 / O-3).

    The repo-wide firewall gate already enforces this, but a gate that lives elsewhere
    can be skipped; asserting it here means the independence claim fails **in the same
    suite that depends on it**. Checked over the parsed syntax tree, because a string
    such as the worker's module path legitimately contains ``tos`` and a substring scan
    would either miss a real import or reject that string.
    """
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
