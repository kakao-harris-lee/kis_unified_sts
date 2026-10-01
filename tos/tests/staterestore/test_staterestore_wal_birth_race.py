"""Concurrent FIRST open of a brand-new kernel store file (**#823**).

Two runtimes booted against the same empty ``data_dir`` both reach their first
composite-state write with the store file still non-existent
(``tos_runtime.compose._engine_wiring`` wires the writer over
``data_dir / COMPOSITE_STATE_STORE_FILE_NAME``, and
``tos_runtime.recovery.composite_state_writer`` opens a NEW connection per write). The
window under test is the ``PRAGMA journal_mode=WAL`` switch inside
:class:`~tos.staterestore.store.CompositeStateStore`'s own constructor: switching a
never-yet-WAL file needs an exclusive lock that the PRAGMA does **not** wait for, so
before :func:`~tos.staterestore._wal.enable_wal_journal` a loser died with
``OperationalError: database is locked`` before any schema code ran.

**Why processes, not threads.** The production shape is two OS processes, each with its
own sqlite connection and its own busy handler, over one ``data_dir``. Threads inside
one interpreter share neither of those properties in the way that matters here.

**Why repetition rather than a widened window.** The race is real but probabilistic, and
the window is the PRAGMA itself — there is no later statement to pause inside without
pushing the children PAST each other. Repetition is therefore the whole determinism
budget, and :data:`_BIRTH_RACE_ROUNDS` is sized against a **directly measured per-round
clean rate on the pre-fix code**, not against a per-opener rate raised to a power (see
that constant's own comment for the arithmetic).

**Hermetic.** Every file is under ``tmp_path``; no network, no ambient env. The children
are forked, not spawned, so they inherit the already-imported modules instead of
re-importing the suite eight times per round.
"""

from __future__ import annotations

import multiprocessing as mp
import sqlite3
import time
from collections.abc import Sequence
from multiprocessing.synchronize import Barrier as BarrierType
from pathlib import Path
from queue import Empty

from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState
from tos.staterestore.store import DIMENSION_COMMIT_ORDER, CompositeStateStore

#: How many processes open the same non-existent store path at once. The production
#: scenario needs two; eight is well past it, and the extra parties are what make the
#: pre-fix loss show up in nearly every round rather than occasionally.
_PROCESSES = 8

#: How long the parent waits for a child to REPORT, and how long a child waits at the
#: start barrier. Generous: it is only reached when something is already broken.
_REPORT_TIMEOUT_S = 60.0

#: The budget for ONE phase of bringing the children down, **shared across all of them**
#: rather than spent per child (review F5, then round-2 F6). Given one child that wedges
#: in ``barrier.wait`` or inside sqlite's busy handler — the class of failure this module
#: exists to catch — a per-child timeout of the size above turns "the parent already
#: waited 60 s" into "and now waits up to 8 x 60 s more" before the intended
#: ``AssertionError`` ever surfaces, which is wedging the suite, not failing the test.
#: :func:`_reap` spends at most three of these in total (join, terminate+join,
#: kill+join), so the bound does not grow with the number of children.
_REAP_TIMEOUT_S = 10.0

#: Rounds of :data:`_PROCESSES` openers this test runs.
#:
#: **Sized against a DIRECTLY MEASURED per-round clean rate on the PRE-FIX code**, which
#: is the only quantity that decides whether a broken tree can pass: openers within one
#: round do NOT fail independently (somebody wins the switch, so at most 7 of 8 can
#: lose), and the test only passes when a whole round comes out clean.
#:
#: Measured on this tree with ``CompositeStateStore.__init__`` still running the bare
#: ``PRAGMA journal_mode=WAL``, 40 rounds of 8 openers on a fresh path each round:
#:
#:     96 / 320 losing children (all ``OperationalError: database is locked``),
#:     spread over 34 unclean rounds — **6 / 40 rounds clean, q = 0.150**.
#:
#: A test of N rounds is green on the broken code with probability q**N. Clearing 1 %
#: needs 3 rounds at that point estimate and 4 at its 95 % Wilson UPPER bound
#: (q = 0.291). Ten is the next round number an order of magnitude past both: 5.8e-9 at
#: the point estimate, 4.3e-6 at the upper bound. Measured cost of the whole module
#: (both tests, 10 rounds plus the reopen round): 1.4 / 2.0 / 2.0 s over three runs.
_BIRTH_RACE_ROUNDS = 10

#: The identity every child commits under. Fixed so the reopen assertion below is a
#: value comparison rather than a "something is there" one.
_IDENTITY = "intent-birth-race"

#: The five markers every child writes, one per dimension. Named individually rather
#: than only as a dict: the dict's inferred value type is their common base
#: (``StrEnum``), which :class:`~tos.orthostate.CompositeState`'s per-dimension fields
#: rightly refuse — each dimension's field takes its OWN enum, and that is the
#: distinctness the store's reload path depends on.
_INTENT = IntentState.ACTIVE
_CAPACITY = CapacityState.POTENTIALLY_LIVE
_ATTEMPT = TransmissionAttemptState.SEND_STARTED
_BROKER_ORDER = BrokerOrderState.NONE_OBSERVED
_KNOWLEDGE = KnowledgeState.UNOBSERVED

#: What :meth:`~tos.staterestore.store.CompositeStateStore.read_markers` must hand back
#: afterwards — typed as it types its own return, so the comparison is between the same
#: two things.
_EXPECTED_MARKERS: dict[StateDimension, object] = {
    StateDimension.INTENT: _INTENT,
    StateDimension.CAPACITY: _CAPACITY,
    StateDimension.TRANSMISSION_ATTEMPT: _ATTEMPT,
    StateDimension.BROKER_ORDER: _BROKER_ORDER,
    StateDimension.KNOWLEDGE: _KNOWLEDGE,
}


def _composite() -> CompositeState:
    """The one composite every child writes — all five dimensions, one known identity."""
    return CompositeState(
        intent_identity=_IDENTITY,
        intent_state=_INTENT,
        capacity_state=_CAPACITY,
        transmission_attempt_state=_ATTEMPT,
        broker_order_state=_BROKER_ORDER,
        knowledge_state=_KNOWLEDGE,
    )


def _child(
    path_str: str, barrier: BarrierType, queue: mp.Queue[str]
) -> None:  # pragma: no cover - runs in a forked child
    """Open the store over ``path_str`` in lockstep with every sibling; report the outcome.

    The outcome is REPORTED, never raised, and the whole body — the barrier wait
    included — is inside the ``try``: a child that died before its ``queue.put`` would
    leave the parent blocked on ``queue.get`` for the full timeout and then fail with
    "never reported an outcome", which says nothing about WHY. Every path ends in
    exactly one ``queue.put``.

    The write is the point, not just the open: this models the recovery writer's
    ``with CompositeStateStore(path) as store: store.commit_composite(...)``, which is
    the ONLY way this file is ever created in production.
    """
    try:
        barrier.wait(timeout=_REPORT_TIMEOUT_S)
        with CompositeStateStore(Path(path_str)) as store:
            store.commit_composite(_composite())
        queue.put("OK")
    except BaseException as exc:  # noqa: BLE001 - the exception IS this child's result
        queue.put(f"{type(exc).__name__}: {exc}")


def _join_all(children: Sequence[mp.process.BaseProcess]) -> None:
    """Join every child against ONE deadline shared by the whole set."""
    deadline = time.monotonic() + _REAP_TIMEOUT_S
    for child in children:
        child.join(timeout=max(0.0, deadline - time.monotonic()))


def _reap(children: Sequence[mp.process.BaseProcess]) -> None:
    """Bring every child down in at most THREE shared deadlines, never one per child.

    Three phases, each with its own whole-set budget: join, then ``terminate`` whatever
    is still alive and join again, then ``kill`` whatever survived that and join a last
    time. Worst case is ``3 * _REAP_TIMEOUT_S`` no matter how many children wedge —
    review round-2 F6 caught the previous cut still multiplying by the child count in
    its straggler loop (``terminate`` then a full per-child join), which is a smaller
    version of the shape F5 was filed against in the first place.

    ``terminate`` runs only AFTER the first join: on the healthy path every child has
    already exited by then, so the exit-code assertion downstream never sees a
    ``-SIGTERM`` this helper caused.
    """
    _join_all(children)
    stragglers = [child for child in children if child.is_alive()]
    if not stragglers:  # the healthy path, every time
        return
    for child in stragglers:  # pragma: no cover - only on a wedged child
        child.terminate()
    _join_all(stragglers)  # pragma: no cover - only on a wedged child
    survivors = [  # pragma: no cover - only on a child that ignores SIGTERM
        child for child in stragglers if child.is_alive()
    ]
    for child in survivors:  # pragma: no cover - only on a wedged child
        child.kill()
    _join_all(survivors)  # pragma: no cover - only on a wedged child


def _run_concurrent_first_open(path: Path) -> list[str]:
    """Release :data:`_PROCESSES` children onto the same non-existent ``path``."""
    context = mp.get_context("fork")
    barrier = context.Barrier(_PROCESSES)
    queue: mp.Queue[str] = context.Queue()
    children = [
        context.Process(target=_child, args=(str(path), barrier, queue))
        for _ in range(_PROCESSES)
    ]
    for child in children:
        child.start()
    try:
        outcomes = [queue.get(timeout=_REPORT_TIMEOUT_S) for _ in range(_PROCESSES)]
    except Empty as exc:  # pragma: no cover - only on a wedged child
        _reap(children)
        raise AssertionError(
            f"a child never reported an outcome within {_REPORT_TIMEOUT_S}s"
        ) from exc
    _reap(children)
    assert all(
        child.exitcode == 0 for child in children
    ), f"a child exited abnormally: {[child.exitcode for child in children]}"
    return outcomes


def _journal_mode(path: Path) -> str:
    """The file's own journal mode, read through a ``mode=ro`` connection.

    Read-only so this evidence-gathering helper cannot itself perform the switch it is
    checking for.
    """
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        conn.close()


def test_concurrent_first_open_of_a_brand_new_store_admits_every_process(
    tmp_path: Path,
) -> None:
    """Eight processes open the same NON-EXISTENT store path at once: all eight succeed.

    RED on the pre-#823 code with no mutation needed — the losers report
    ``OperationalError: database is locked`` out of the constructor's own journal-mode
    switch. Measured on this tree with the bare PRAGMA restored: 96/320 losing children
    over 34 unclean rounds of 40, i.e. only 6/40 rounds clean. :data:`_BIRTH_RACE_ROUNDS`
    is sized against that per-ROUND rate; its own comment carries the arithmetic and the
    confidence bound.

    The journal mode is the second half of the claim and is not implied by the first: a
    "fix" that swallowed the lock error and left the file on the rollback journal would
    make every child report OK while quietly abandoning the substrate this package's
    durability argument assumes.
    """
    for round_index in range(_BIRTH_RACE_ROUNDS):
        path = tmp_path / f"composite-{round_index}.sqlite3"
        assert not path.exists()

        outcomes = _run_concurrent_first_open(path)

        assert outcomes == ["OK"] * _PROCESSES, (
            f"every concurrent first open of a BRAND-NEW store file must succeed "
            f"(round {round_index}); failures: "
            f"{sorted(outcome for outcome in outcomes if outcome != 'OK')}"
        )
        assert (
            _journal_mode(path) == "wal"
        ), f"the raced store file must be in WAL mode (round {round_index})"


def test_a_store_created_by_a_race_is_an_ordinary_store(tmp_path: Path) -> None:
    """The file a concurrent first open leaves behind reopens and reads back normally.

    "Nobody crashed" is not the whole property. A race that left a half-created file
    would satisfy the test above and then refuse, or return nothing, on the very next
    ordinary open. This reopens the raced file through the real constructor and pins
    that all five dimensions are there, at the values the children committed.
    """
    path = tmp_path / "composite.sqlite3"
    assert _run_concurrent_first_open(path) == ["OK"] * _PROCESSES

    with CompositeStateStore(path) as reopened:
        markers = reopened.read_markers(_IDENTITY)

    assert set(markers) == set(DIMENSION_COMMIT_ORDER)
    assert markers == _EXPECTED_MARKERS
