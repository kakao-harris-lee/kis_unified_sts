"""S-1 — the durable per-dimension marker store (design #39 §5.1; ADR-002-005 §13:197).

Both ways for every property: the store really persists what was committed **and**
really withholds what was not. A store that returned the right answer for a complete
commit while also inventing markers for an incomplete one would pass a happy-path-only
suite and fail the EV-L3 catalog's whole incomplete-store limb.
"""

from __future__ import annotations

import sqlite3

import pytest
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState
from tos.staterestore import (
    DIMENSION_COMMIT_ORDER,
    CompositeStateStore,
    StoreIntegrityError,
)

_IDENTITY = "INTENT-STORE-TEST"


def _composite(**overrides) -> CompositeState:
    """An otherwise-valid five-dimension witness (single-mutation discipline)."""
    kwargs = {
        "intent_identity": _IDENTITY,
        "intent_state": IntentState.ACTIVE,
        "transmission_attempt_state": TransmissionAttemptState.SEND_STARTED,
        "broker_order_state": BrokerOrderState.UNKNOWN,
        "knowledge_state": KnowledgeState.UNOBSERVED,
        "capacity_state": CapacityState.POTENTIALLY_LIVE,
    }
    kwargs.update(overrides)
    return CompositeState(**kwargs)


# --------------------------------------------------------------------------
# durable round-trip
# --------------------------------------------------------------------------


def test_a_committed_composite_reads_back_dimension_for_dimension(tmp_path) -> None:
    """AC-005-1 line 237 — "representable **and persisted**"."""
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        committed = store.commit_composite(_composite())
    assert committed == DIMENSION_COMMIT_ORDER

    with CompositeStateStore(path) as reopened:
        markers = reopened.read_markers(_IDENTITY)
    assert markers == {
        StateDimension.INTENT: IntentState.ACTIVE,
        StateDimension.CAPACITY: CapacityState.POTENTIALLY_LIVE,
        StateDimension.TRANSMISSION_ATTEMPT: TransmissionAttemptState.SEND_STARTED,
        StateDimension.BROKER_ORDER: BrokerOrderState.UNKNOWN,
        StateDimension.KNOWLEDGE: KnowledgeState.UNOBSERVED,
    }


def test_the_store_survives_a_closed_connection_and_a_new_one(tmp_path) -> None:
    """The durability claim is about the file, not about a live handle."""
    path = tmp_path / "store.sqlite3"
    store = CompositeStateStore(path)
    store.commit_composite(_composite(knowledge_state=KnowledgeState.CONFLICTED))
    store.close()

    assert path.is_file() and path.stat().st_size > 0
    with CompositeStateStore(path) as reopened:
        markers = reopened.read_markers(_IDENTITY)
    assert markers[StateDimension.KNOWLEDGE] is KnowledgeState.CONFLICTED


#: ``PRAGMA synchronous`` return codes (sqlite: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA).
_SYNCHRONOUS_FULL = 2


def test_the_substrate_is_wal_with_synchronous_full(tmp_path) -> None:
    """design #39 §3.2 A — the pilot substrate decision, measured on the open handle.

    Both halves of the decision are asserted, and they have to be read from different
    places because they are different kinds of setting:

      * ``journal_mode`` is a **database** property written into the file header, so a
        fresh connection to the file reports it — which is the stronger observation
        (the mode survived the writer);
      * ``synchronous`` is a **per-connection** property. A fresh probe would report its
        own default and say nothing about the store, so it is read off the store's own
        live handle. Asserting only ``journal_mode`` (as this test first did) let the
        name over-state its scope: the real ``PRAGMA synchronous=FULL`` could be
        lowered with no executable check failing anywhere (measured).
    """
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(_composite())
        synchronous = store._conn.execute(  # noqa: SLF001 — the handle IS the subject
            "PRAGMA synchronous"
        ).fetchone()[0]
    assert synchronous == _SYNCHRONOUS_FULL, (
        f"the store connection runs at PRAGMA synchronous={synchronous}, not "
        f"{_SYNCHRONOUS_FULL} (FULL) — the design §3.2 substrate decision is not in "
        "force on the connection that actually writes"
    )
    probe = sqlite3.connect(str(path))
    try:
        assert probe.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        probe.close()


# --------------------------------------------------------------------------
# per-dimension transactions => a legitimate incomplete store
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stop_after", [0, 1, 2, 3, 4, 5])
def test_stopping_between_transactions_leaves_exactly_that_prefix(
    tmp_path, stop_after: int
) -> None:
    """VER:1045 "incomplete stores" — the crash boundary is the transaction boundary.

    The dimensions that were committed are present and the ones that were not are
    **absent keys**, not defaulted values: the store never fills in on the read side.
    """
    path = tmp_path / f"store-{stop_after}.sqlite3"
    with CompositeStateStore(path) as store:
        committed = store.commit_composite(_composite(), stop_after=stop_after)
    assert committed == DIMENSION_COMMIT_ORDER[:stop_after]

    with CompositeStateStore(path) as reopened:
        markers = reopened.read_markers(_IDENTITY)
    assert set(markers) == set(DIMENSION_COMMIT_ORDER[:stop_after])
    for absent in DIMENSION_COMMIT_ORDER[stop_after:]:
        assert absent not in markers


def test_the_commit_order_is_the_write_ahead_order(tmp_path) -> None:
    """§6 line 96 — the attempt marker is durable BEFORE anything broker-side.

    Pinned as an order, not as prose: an edit that moved the broker marker ahead of the
    attempt marker would make "durable SEND_STARTED before the external call"
    unrepresentable, and every incomplete-store anchor would silently change meaning.
    """
    assert DIMENSION_COMMIT_ORDER == (
        StateDimension.INTENT,
        StateDimension.CAPACITY,
        StateDimension.TRANSMISSION_ATTEMPT,
        StateDimension.BROKER_ORDER,
        StateDimension.KNOWLEDGE,
    )
    attempt = DIMENSION_COMMIT_ORDER.index(StateDimension.TRANSMISSION_ATTEMPT)
    broker = DIMENSION_COMMIT_ORDER.index(StateDimension.BROKER_ORDER)
    knowledge = DIMENSION_COMMIT_ORDER.index(StateDimension.KNOWLEDGE)
    assert attempt < broker < knowledge


def test_a_later_commit_supersedes_an_earlier_marker(tmp_path) -> None:
    """A dimension transition is a new durable value for that dimension, not a duplicate."""
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(_composite())
        store.commit_dimension(
            _IDENTITY,
            StateDimension.BROKER_ORDER,
            str(BrokerOrderState.FILLED),
        )
        markers = store.read_markers(_IDENTITY)
    assert markers[StateDimension.BROKER_ORDER] is BrokerOrderState.FILLED


# --------------------------------------------------------------------------
# negative: an unreadable store is never summarised as an empty one
# --------------------------------------------------------------------------


def test_an_unidentified_composite_is_refused(tmp_path) -> None:
    """Fail-closed: a record with no identity cannot be reconstructed later."""
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        with pytest.raises(StoreIntegrityError, match="intent_identity is required"):
            store.commit_composite(_composite(intent_identity=None))


def test_a_marker_that_is_not_a_member_of_its_dimension_is_a_corruption(
    tmp_path,
) -> None:
    """A dimension-swapped marker is an integrity error, never a silent absence.

    Global string-value distinctness across the five dimension enums (design #8 §2.2) is
    what makes this detectable: ``FILLED`` is not an ``IntentState``. Reporting the row
    as *absent* instead would let the conservative fill quietly repair a corrupt store,
    which is the wiring-level fail-open design #39 O-1 warns about.
    """
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(_composite())
        store.commit_dimension(_IDENTITY, StateDimension.INTENT, "FILLED")
        with pytest.raises(StoreIntegrityError, match="not a member of IntentState"):
            store.read_markers(_IDENTITY)


def test_a_row_naming_an_unknown_dimension_is_a_corruption(tmp_path) -> None:
    """A sixth dimension cannot exist; a row claiming one is refused, not ignored."""
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(_composite())
        store._conn.execute(  # noqa: SLF001 — planting the corruption is the point
            "INSERT INTO dimension_marker VALUES (?, ?, ?)",
            (_IDENTITY, "SENTIMENT", "BULLISH"),
        )
        with pytest.raises(StoreIntegrityError, match="unknown dimension"):
            store.read_markers(_IDENTITY)


def test_markers_are_scoped_to_their_intent_identity(tmp_path) -> None:
    """SAFE-020 (§5 line 76) — one intent's durable state never answers for another's."""
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(_composite())
        assert store.read_markers("SOME-OTHER-INTENT") == {}
