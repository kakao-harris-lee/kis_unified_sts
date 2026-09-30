"""Hermetic tests for :class:`tos_runtime.marketfeed.store.SqliteSnapshotStore`.

Mutation coverage (plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §5, this store's own
scope): M3 (digest re-check on ``__call__``) and M4 (preimage durability across a restart, proven
through the REAL kernel publication gate). Every sqlite file lives under ``tmp_path`` — no network,
no ambient env (the ``tos/runtime/tests/conftest.py`` autouse hermetic guard covers both).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.engine import InstrumentKey
from tos.marketfeed import MarketFeedContextResolver
from tos.marketfeed.vocabulary import ValueViewDisposition
from tos_runtime.marketfeed.store import InjectedCrash, SqliteSnapshotStore

from ._store_fixtures import (
    ACCOUNT,
    AS_OF_MS,
    INSTRUMENT,
    INSTRUMENT_KEY,
    OTHER_INSTRUMENT,
    SCHEME,
    issue_snapshot,
    observation,
    one_bar,
    preimage,
)


def test_put_and_call_round_trip(tmp_path: Path) -> None:
    """A put snapshot resolves back byte-identical (as JSON) through ``__call__``."""
    capsule, snapshot, payload = one_bar()
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    store.put(snapshot, {"raw-1": payload})

    resolved = store(
        snapshot_id=snapshot.snapshot_id, canonical_digest=snapshot.canonical_digest
    )

    assert resolved is not None
    assert resolved.model_dump_json() == snapshot.model_dump_json()
    store.close()


def test_call_missing_snapshot_returns_none(tmp_path: Path) -> None:
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    assert store(snapshot_id="cis-does-not-exist", canonical_digest="whatever") is None
    assert store(snapshot_id=None, canonical_digest=None) is None
    store.close()


def test_call_digest_mismatch_returns_none_never_the_body(tmp_path: Path) -> None:
    """Mutation M3: a right id + wrong digest request must never yield the stored body."""
    capsule, snapshot, payload = one_bar()
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    store.put(snapshot, {"raw-1": payload})

    resolved = store(
        snapshot_id=snapshot.snapshot_id, canonical_digest="not-the-real-digest"
    )

    assert resolved is None, (
        "a stored body under a live snapshot_id must never be returned for a mismatched "
        "canonical_digest — this is exactly what mutation M3 removes"
    )
    store.close()


def test_candidates_one_admitted_value_per_key_per_observation(tmp_path: Path) -> None:
    payload = preimage(close=100, session="REGULAR")
    obs = observation(raw_event_id="raw-1", payload=payload)
    snapshot = issue_snapshot(observations=(obs,))
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    store.put(snapshot, {"raw-1": payload})

    candidates = store.candidates(snapshot, instrument_key=INSTRUMENT_KEY)

    assert len(candidates) == 2
    by_key = {c.field_key: c for c in candidates}
    assert by_key["close"].observation_ref == "raw-1"
    assert by_key["close"].preimage == payload
    assert by_key["session"].observation_ref == "raw-1"
    store.close()


def test_candidates_outside_scope_returns_empty(tmp_path: Path) -> None:
    """Mirrors ``BandBarBook.candidate_source``'s instrument-scope filter."""
    capsule, snapshot, payload = one_bar()
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    store.put(snapshot, {"raw-1": payload})

    wrong_instrument = store.candidates(
        snapshot,
        instrument_key=InstrumentKey(account=ACCOUNT, instrument=OTHER_INSTRUMENT),
    )
    wrong_account = store.candidates(
        snapshot,
        instrument_key=InstrumentKey(account="other-acct", instrument=INSTRUMENT),
    )

    assert wrong_instrument == ()
    assert wrong_account == ()
    store.close()


def test_latest_as_of_empty_store_is_none(tmp_path: Path) -> None:
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    assert store.latest_as_of(instrument=INSTRUMENT) is None
    store.close()


def test_latest_as_of_returns_true_max(tmp_path: Path) -> None:
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")

    payload_1 = preimage(close=100)
    snapshot_1 = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-1", payload=payload_1, as_of=1_000),
        )
    )
    store.put(snapshot_1, {"raw-1": payload_1})

    payload_2 = preimage(close=200)
    snapshot_2 = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-2", payload=payload_2, as_of=2_000),
        )
    )
    store.put(snapshot_2, {"raw-2": payload_2})

    assert store.latest_as_of(instrument=INSTRUMENT) == 2_000
    assert store.latest_as_of(instrument=OTHER_INSTRUMENT) is None
    store.close()


def test_put_requires_issued_snapshot(tmp_path: Path) -> None:
    from tos.capsule import CriticalInputSnapshot

    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    with pytest.raises(ValueError):
        store.put(CriticalInputSnapshot(), {})
    store.close()


def test_put_requires_exactly_one_scope_instrument(tmp_path: Path) -> None:
    payload = preimage(close=1)
    obs = observation(raw_event_id="raw-1", payload=payload)
    snapshot = issue_snapshot(
        observations=(obs,), instruments=(INSTRUMENT, OTHER_INSTRUMENT)
    )
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    with pytest.raises(ValueError):
        store.put(snapshot, {"raw-1": payload})
    store.close()


def test_put_requires_a_dateable_observation(tmp_path: Path) -> None:
    payload = preimage(close=1)
    snapshot = issue_snapshot(observations=())
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    with pytest.raises(ValueError):
        store.put(snapshot, {"raw-1": payload})
    store.close()


def test_put_is_idempotent_for_a_retried_identical_snapshot(tmp_path: Path) -> None:
    capsule, snapshot, payload = one_bar()
    store = SqliteSnapshotStore(tmp_path / "store.sqlite3")
    store.put(snapshot, {"raw-1": payload})
    store.put(snapshot, {"raw-1": payload})  # retry — must not raise a UNIQUE violation

    assert store.latest_as_of(instrument=INSTRUMENT) == AS_OF_MS
    assert len(store.candidates(snapshot, instrument_key=INSTRUMENT_KEY)) == 1
    store.close()


def test_put_is_atomic_a_crash_before_commit_leaves_no_partial_rows(
    tmp_path: Path,
) -> None:
    """Mutation-style proof of the atomicity contract: an injected failure before COMMIT must
    leave BOTH tables exactly as they were — never a snapshot row with only some (or none) of
    its preimages durably recorded."""
    path = tmp_path / "store.sqlite3"
    capsule, snapshot, payload = one_bar()

    def crash_hook(point: str) -> None:
        if point == "before_commit":
            raise InjectedCrash("simulated failure before COMMIT")

    crashing_store = SqliteSnapshotStore(path, crash_hook=crash_hook)
    with pytest.raises(InjectedCrash):
        crashing_store.put(snapshot, {"raw-1": payload})
    crashing_store.close()

    reopened = SqliteSnapshotStore(path)
    assert (
        reopened(
            snapshot_id=snapshot.snapshot_id, canonical_digest=snapshot.canonical_digest
        )
        is None
    )
    assert reopened.latest_as_of(instrument=INSTRUMENT) is None
    assert reopened.candidates(snapshot, instrument_key=INSTRUMENT_KEY) == ()
    reopened.close()


def test_restart_durability_real_resolver_still_admits(tmp_path: Path) -> None:
    """Mutation M4: preimages held only in memory could not survive a restart. This proves the
    durability is real by constructing a FRESH store over the SAME file after the producing store
    is discarded, and publishing a view through it via the REAL kernel resolver — not a fixture
    double."""
    path = tmp_path / "store.sqlite3"
    capsule, snapshot, payload = one_bar()

    producer = SqliteSnapshotStore(path)
    producer.put(snapshot, {"raw-1": payload})
    producer.close()
    del producer  # the producing process/object is gone — only the file remains

    reopened = SqliteSnapshotStore(path)
    resolver = MarketFeedContextResolver(
        snapshot_store=reopened, candidate_source=reopened.candidates, scheme=SCHEME
    )

    resolved = resolver.resolve(capsule, instrument_key=INSTRUMENT_KEY)

    assert resolved.resolution.disposition == ValueViewDisposition.RESOLVED
    assert resolved.value_surface_published is True
    assert resolved.resolution.view is not None
    values_by_key = {
        value.field_key: value for value in resolved.resolution.view.values
    }
    assert values_by_key["close"].value == 4_512_500
    assert (
        values_by_key["close"].payload_digest
        == snapshot.observations[0].raw.payload_digest
    )
    reopened.close()
