"""Fault ⑤ replay coverage of ``committed_vector`` (carryover plan W-B B-1, 2026-09-25).

Before B-1 the kernel round #4 K-4 ``committed_vector`` was written only to the
``reservations.committed_vector_json`` column, so ``verify_replay`` could not see a value
altered there. These tests pin that it now does, that "no vector" and "explicitly empty vector"
stay distinct, and that a pre-K-4 entry (payload without the key, column ``NULL`` after the
v1→v2 migration) still replays clean.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from tos.rcl import (
    AppendReceipt,
    CapacityReservationTransition,
    CapacityState,
    CapacityVector,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.rcl.vector import CapacityComponent
from tos.workload import RuntimeIdentity
from tos_runtime.rcl.gates import fold_reservations_from_entries
from tos_runtime.rcl.log import CommitLogCorruption, SqliteCommitLog

_SCOPE = ReservationScope(account="acct-1", instrument="101S06")
_ONE_CONTRACT = CapacityVector(
    components=(CapacityComponent(dimension_id="CONTRACTS", magnitude=Decimal("1")),)
)


def _commit(
    log: SqliteCommitLog, identity: RuntimeIdentity, vector: CapacityVector | None
) -> None:
    transition = CapacityReservationTransition(
        reservation_id="res-1",
        writer_epoch=log.acquire_epoch(identity),
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=CapacityState.ATTEMPT_BOUND,
        scope=_SCOPE,
        committed_vector=vector,
    )
    result = log.apply_reservation_transition(
        transition,
        TransitionCause.STRONGLY_AUTHORIZED_COMMAND,
        command_type=CommandType.BIND_ATTEMPT,
        command_id="cmd-1",
        command_digest="dig-1",
        expected_seq=-1,
    )
    assert isinstance(result, AppendReceipt)


def _set_column(log: SqliteCommitLog, value: str | None) -> None:
    log._conn.execute(
        "UPDATE reservations SET committed_vector_json = ? WHERE reservation_id = ?",
        (value, "res-1"),
    )


@pytest.mark.parametrize(
    "vector", [None, CapacityVector(), _ONE_CONTRACT], ids=["none", "empty", "one"]
)
def test_legitimate_log_replays_clean(
    log: SqliteCommitLog, identity: RuntimeIdentity, vector: CapacityVector | None
) -> None:
    _commit(log, identity, vector)
    log.verify_replay()


@pytest.mark.parametrize(
    ("vector", "tampered"),
    [
        # value changed
        (_ONE_CONTRACT, CapacityVector().model_dump_json()),
        # a vector erased to "no vector"
        (_ONE_CONTRACT, None),
        # "no vector" turned into an explicitly empty vector — must NOT be conflated
        (None, CapacityVector().model_dump_json()),
        # an explicitly empty vector turned into "no vector"
        (CapacityVector(), None),
        # unparseable text
        (_ONE_CONTRACT, "{not json"),
    ],
    ids=["value", "erased", "none-to-empty", "empty-to-none", "garbage"],
)
def test_committed_vector_column_tamper_raises(
    log: SqliteCommitLog,
    identity: RuntimeIdentity,
    vector: CapacityVector | None,
    tampered: str | None,
) -> None:
    _commit(log, identity, vector)
    log.verify_replay()
    _set_column(log, tampered)
    with pytest.raises(CommitLogCorruption):
        log.verify_replay()


def test_decimal_spelling_is_not_a_disagreement(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """``"1.0"`` and ``"1"`` are the same magnitude — both sides are re-validated before
    comparison, so a re-spelled but equal column must not raise."""
    _commit(log, identity, _ONE_CONTRACT)
    _set_column(log, _ONE_CONTRACT.model_dump_json().replace('"1"', '"1.0"'))
    log.verify_replay()


def test_payload_carries_the_key_explicitly_even_when_none(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """New entries always write the key, so an absent key can only mean a pre-K-4 entry."""
    _commit(log, identity, None)
    (payload_json,) = log._conn.execute(
        "SELECT payload_json FROM entries WHERE is_reservation_transition = 1"
    ).fetchone()
    payload = json.loads(payload_json)
    assert "committed_vector" in payload
    assert payload["committed_vector"] is None


def _rewrite_as_pre_k4(log: SqliteCommitLog) -> None:
    """Make the committed entry look like a pre-K-4 one: payload without the key. ``entries``
    is append-only, so the trigger is dropped for this simulation only."""
    conn = log._conn
    conn.execute("DROP TRIGGER entries_no_update")
    seq, payload_json = conn.execute(
        "SELECT seq, payload_json FROM entries WHERE is_reservation_transition = 1"
    ).fetchone()
    payload = json.loads(payload_json)
    del payload["committed_vector"]
    conn.execute(
        "UPDATE entries SET payload_json = ? WHERE seq = ?",
        (json.dumps(payload, sort_keys=True), seq),
    )


def test_pre_k4_entry_with_null_column_replays_clean(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    _commit(log, identity, None)
    _rewrite_as_pre_k4(log)
    assert (
        fold_reservations_from_entries(log._conn)["res-1"]["committed_vector"] is None
    )
    log.verify_replay()


def test_pre_k4_entry_with_a_vector_in_the_column_raises(
    log: SqliteCommitLog, identity: RuntimeIdentity
) -> None:
    """A pre-K-4 entry could carry no vector, so a non-NULL column against it is tampering."""
    _commit(log, identity, None)
    _rewrite_as_pre_k4(log)
    _set_column(log, _ONE_CONTRACT.model_dump_json())
    with pytest.raises(CommitLogCorruption):
        log.verify_replay()
