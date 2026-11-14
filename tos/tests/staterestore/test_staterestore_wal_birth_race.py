"""Concurrent FIRST open of a brand-new kernel store file (**#823**)."""

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

_PROCESSES = 8

_REPORT_TIMEOUT_S = 60.0

_REAP_TIMEOUT_S = 10.0

#: ``PRAGMA journal_mode=WAL``, 40 rounds of 8 openers on a fresh path each round:
_BIRTH_RACE_ROUNDS = 10

_IDENTITY = "intent-birth-race"

_INTENT = IntentState.ACTIVE
_CAPACITY = CapacityState.POTENTIALLY_LIVE
_ATTEMPT = TransmissionAttemptState.SEND_STARTED
_BROKER_ORDER = BrokerOrderState.NONE_OBSERVED
_KNOWLEDGE = KnowledgeState.UNOBSERVED

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
    """Open the store over ``path_str`` in lockstep with every sibling; report the outcome."""
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
    """Bring every child down in at most THREE shared deadlines, never one per child."""
    _join_all(children)
    stragglers = [child for child in children if child.is_alive()]
    if not stragglers:
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
    """The file's own journal mode, read through a ``mode=ro`` connection."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        conn.close()


def test_concurrent_first_open_of_a_brand_new_store_admits_every_process(
    tmp_path: Path,
) -> None:
    """Eight processes open the same NON-EXISTENT store path at once: all eight succeed."""
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
    """The file a concurrent first open leaves behind reopens and reads back normally."""
    path = tmp_path / "composite.sqlite3"
    assert _run_concurrent_first_open(path) == ["OK"] * _PROCESSES

    with CompositeStateStore(path) as reopened:
        markers = reopened.read_markers(_IDENTITY)

    assert set(markers) == set(DIMENSION_COMMIT_ORDER)
    assert markers == _EXPECTED_MARKERS
