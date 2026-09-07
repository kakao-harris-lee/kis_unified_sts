"""``tos_runtime.evidence.outbox`` tests — same-transaction enqueue + at-least-once drain."""

from __future__ import annotations

from tos_runtime.evidence import outbox as ob
from tos_runtime.evidence.store import SqliteEvidenceStore


class _RecordingConsumer:
    def __init__(self, succeed_targets: frozenset[str] = frozenset()) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self._succeed_targets = succeed_targets

    def deliver(self, delivery: ob.OutboxDelivery) -> bool:
        self.calls.append((delivery.target, delivery.idempotency_key))
        return delivery.target in self._succeed_targets


def test_enqueue_happens_in_the_same_transaction_as_append(
    store: SqliteEvidenceStore,
) -> None:
    row_count_before = store.connection.execute(
        "SELECT COUNT(*) FROM outbox"
    ).fetchone()[0]

    def crash_hook(point: str) -> None:
        if point == "before_commit":
            raise RuntimeError("simulated failure inside the append transaction")

    store._crash_hook = crash_hook
    try:
        store.append(
            {"x": 1}, kind="TEST", record_class="TESTCLASS", outbox_targets=("t1",)
        )
    except RuntimeError:
        pass
    store._crash_hook = None

    row_count_after = store.connection.execute(
        "SELECT COUNT(*) FROM outbox"
    ).fetchone()[0]
    assert (
        row_count_after == row_count_before
    ), "a failed append must not leave an outbox row"


def test_successful_append_enqueues_outbox_rows_for_every_target(
    store: SqliteEvidenceStore,
) -> None:
    store.append(
        {"x": 1}, kind="TEST", record_class="TESTCLASS", outbox_targets=("a", "b")
    )
    row_count = store.connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    assert row_count == 2


def test_drain_delivers_pending_rows_and_marks_them_delivered(
    store: SqliteEvidenceStore,
) -> None:
    store.append(
        {"x": 1}, kind="TEST", record_class="TESTCLASS", outbox_targets=("a", "b")
    )
    consumer = _RecordingConsumer(succeed_targets=frozenset({"a", "b"}))
    delivered = ob.drain(store, consumer)
    assert delivered == 2
    assert len(consumer.calls) == 2
    # a second drain call finds nothing pending
    delivered_again = ob.drain(store, consumer)
    assert delivered_again == 0
    assert len(consumer.calls) == 2


def test_drain_is_at_least_once_a_failed_delivery_is_retried(
    store: SqliteEvidenceStore,
) -> None:
    store.append(
        {"x": 1}, kind="TEST", record_class="TESTCLASS", outbox_targets=("a", "b")
    )
    failing_consumer = _RecordingConsumer(succeed_targets=frozenset({"a"}))
    first_pass = ob.drain(store, failing_consumer)
    assert first_pass == 1  # only "a" succeeded
    assert len(failing_consumer.calls) == 2  # both were attempted

    succeeding_consumer = _RecordingConsumer(succeed_targets=frozenset({"b"}))
    second_pass = ob.drain(store, succeeding_consumer)
    assert second_pass == 1  # "b" retried and now succeeds
    assert succeeding_consumer.calls == [("b", (None, 0))]


def test_idempotency_key_is_segment_id_and_entry_seq(
    store: SqliteEvidenceStore,
) -> None:
    store.append(
        {"x": 1},
        kind="TEST",
        record_class="TESTCLASS",
        segment_id="seg-1",
        outbox_targets=("a",),
    )
    consumer = _RecordingConsumer(succeed_targets=frozenset({"a"}))
    ob.drain(store, consumer)
    assert consumer.calls == [("a", ("seg-1", 0))]
