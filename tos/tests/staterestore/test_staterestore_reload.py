"""S-2 / S-3 — conservative fill and no-stale re-derivation (design #39 §5.1)."""

from __future__ import annotations

import json

import pytest
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
    reconstruct_conservative,
)
from tos.rcl import CapacityState
from tos.staterestore import (
    ABSENT_DIMENSION_FILL,
    CompositeStateStore,
    IncompleteStoreError,
    StoreOpenRefused,
    discard_caches,
    open_store,
    reload_conservative,
)

_IDENTITY = "INTENT-RELOAD-TEST"

_FORBIDDEN_POST_RESTART_KNOWLEDGE = frozenset(
    {KnowledgeState.RECONCILED, KnowledgeState.CONSISTENT}
)


def _composite(**overrides) -> CompositeState:
    kwargs = {
        "intent_identity": _IDENTITY,
        "intent_state": IntentState.ACTIVE,
        "transmission_attempt_state": TransmissionAttemptState.SEND_STARTED,
        "broker_order_state": BrokerOrderState.UNKNOWN,
        "knowledge_state": KnowledgeState.UNOBSERVED,
        "capacity_state": CapacityState.POTENTIALLY_LIVE,
    }
    kwargs.update(overrides)
    return CompositeState.model_validate(kwargs)


def _write(tmp_path, composite: CompositeState, *, stop_after: int | None = None):
    path = tmp_path / "store.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(composite, stop_after=stop_after)
    return path


def test_a_complete_store_needs_no_fill(tmp_path) -> None:
    """The happy direction: nothing is filled, and the flag says so."""
    path = _write(tmp_path, _composite())
    outcome = reload_conservative(path, _IDENTITY)
    assert outcome.store_complete is True
    assert outcome.filled_dimensions == ()
    assert outcome.pre_restart.knowledge_state is KnowledgeState.UNOBSERVED


def test_an_incomplete_store_fills_the_absent_dimensions_conservatively(
    tmp_path,
) -> None:
    """VER:1045 "incomplete stores" — absent Broker => UNKNOWN, absent Knowledge => UNOBSERVED."""
    path = _write(tmp_path, _composite(), stop_after=3)
    outcome = reload_conservative(path, _IDENTITY)
    assert outcome.store_complete is False
    assert outcome.filled_dimensions == (
        StateDimension.BROKER_ORDER,
        StateDimension.KNOWLEDGE,
    )
    assert outcome.pre_restart.broker_order_state is BrokerOrderState.UNKNOWN
    assert outcome.pre_restart.knowledge_state is KnowledgeState.UNOBSERVED
    assert outcome.composite.knowledge_state not in _FORBIDDEN_POST_RESTART_KNOWLEDGE


def test_an_absent_attempt_marker_reads_as_no_attempt_started(tmp_path) -> None:
    """§6 line 96 — ``SEND_STARTED`` is durable *before* the external call."""
    path = _write(tmp_path, _composite(), stop_after=2)
    outcome = reload_conservative(path, _IDENTITY)
    assert (
        outcome.pre_restart.transmission_attempt_state is TransmissionAttemptState.NONE
    )


def test_an_absent_capacity_marker_reads_as_potentially_live(tmp_path) -> None:
    """CPL-1 (§10 line 156) — the minimum capacity a possibly-live effect demands."""
    path = _write(tmp_path, _composite(), stop_after=1)
    outcome = reload_conservative(path, _IDENTITY)
    assert outcome.pre_restart.capacity_state is CapacityState.POTENTIALLY_LIVE


def test_an_absent_intent_marker_is_refused_not_filled(tmp_path) -> None:
    """Fail-closed: there is no conservative value for "which intent is this"."""
    path = _write(tmp_path, _composite(), stop_after=0)
    with pytest.raises(IncompleteStoreError, match="cannot be identified"):
        reload_conservative(path, _IDENTITY)


def test_the_fill_table_has_no_intent_entry() -> None:
    """The refusal above is structural, not a branch someone can 'complete'."""
    assert StateDimension.INTENT not in ABSENT_DIMENSION_FILL
    assert set(ABSENT_DIMENSION_FILL) == {
        StateDimension.TRANSMISSION_ATTEMPT,
        StateDimension.BROKER_ORDER,
        StateDimension.KNOWLEDGE,
        StateDimension.CAPACITY,
    }


def test_no_fill_value_is_an_optimistic_one() -> None:
    """§13 line 199 / §7 line 120 — absence never becomes good news."""
    assert ABSENT_DIMENSION_FILL[StateDimension.KNOWLEDGE] is KnowledgeState.UNOBSERVED
    assert (
        ABSENT_DIMENSION_FILL[StateDimension.KNOWLEDGE]
        not in _FORBIDDEN_POST_RESTART_KNOWLEDGE
    )
    assert (
        ABSENT_DIMENSION_FILL[StateDimension.BROKER_ORDER] is BrokerOrderState.UNKNOWN
    )
    assert (
        ABSENT_DIMENSION_FILL[StateDimension.BROKER_ORDER]
        is not BrokerOrderState.NONE_OBSERVED
    )


def test_a_stale_optimistic_cache_is_discarded_and_never_consulted(tmp_path) -> None:
    """VER:1045 "stale caches" + §13 line 199 "re-derived from evidence"."""
    path = _write(tmp_path, _composite())
    cache = tmp_path / "resume.cache.json"
    cache.write_text(
        json.dumps({"knowledge_state": str(KnowledgeState.RECONCILED)}),
        encoding="utf-8",
    )

    outcome = reload_conservative(path, _IDENTITY, cache_paths=(cache,))

    assert outcome.discarded_caches == (str(cache),)
    assert cache.exists() is False, "the cache survived — it must be discarded"
    assert outcome.composite.knowledge_state is KnowledgeState.UNOBSERVED
    assert outcome.composite.knowledge_state not in _FORBIDDEN_POST_RESTART_KNOWLEDGE


def test_a_refused_open_leaves_the_caches_alone(tmp_path) -> None:
    """**Review round-3 F4.** Discarding is irreversible; a refused open must not do it."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    cache = tmp_path / "resume.cache.json"
    cache.write_text("{}", encoding="utf-8")

    with pytest.raises(StoreOpenRefused, match="could not be opened"):
        reload_conservative(blocker / "store.sqlite3", _IDENTITY, cache_paths=(cache,))

    assert cache.exists(), "a refused open discarded the caches anyway"


def test_a_parent_that_cannot_be_created_is_a_classified_open_refusal(
    tmp_path,
) -> None:
    """**Review round-3 F3.** ``mkdir`` fails before sqlite, and used to escape raw."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(StoreOpenRefused) as refusal:
        open_store(blocker / "store.sqlite3")

    assert isinstance(refusal.value.__cause__, OSError)
    assert type(refusal.value.__cause__).__name__ in str(refusal.value)
    assert "could not be opened" in str(refusal.value)


def test_the_store_value_is_what_flows_through_not_a_constant(tmp_path) -> None:
    """The other way: a *different* durable Knowledge produces a different result."""
    path = _write(tmp_path, _composite(knowledge_state=KnowledgeState.QUARANTINED))
    outcome = reload_conservative(path, _IDENTITY)
    assert outcome.composite.knowledge_state is KnowledgeState.QUARANTINED


def test_discarding_an_absent_cache_is_a_no_op(tmp_path) -> None:
    """Idempotent: a cache that was never written is not reported as discarded."""
    assert discard_caches((tmp_path / "nothing-here.json",)) == ()


@pytest.mark.parametrize("broker", list(BrokerOrderState))
@pytest.mark.parametrize("knowledge", list(KnowledgeState))
def test_reload_equals_the_ratified_projection_over_the_whole_cross_product(
    tmp_path, broker: BrokerOrderState, knowledge: KnowledgeState
) -> None:
    """9 × 7 = 63 combinations: the reload adds nothing to, and removes nothing from, §13."""
    committed = _composite(broker_order_state=broker, knowledge_state=knowledge)
    path = tmp_path / f"store-{broker}-{knowledge}.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(committed)

    outcome = reload_conservative(path, _IDENTITY)
    expected = reconstruct_conservative(committed)

    assert outcome.composite.intent_state is expected.intent_state
    assert (
        outcome.composite.transmission_attempt_state
        is expected.transmission_attempt_state
    )
    assert outcome.composite.broker_order_state is expected.broker_order_state
    assert outcome.composite.knowledge_state is expected.knowledge_state
    assert outcome.composite.capacity_state is expected.capacity_state
    assert outcome.composite.knowledge_state not in _FORBIDDEN_POST_RESTART_KNOWLEDGE


@pytest.mark.parametrize(
    "positive", [KnowledgeState.RECONCILED, KnowledgeState.CONSISTENT]
)
def test_both_positive_knowledge_values_are_downgraded_across_a_restart(
    tmp_path, positive: KnowledgeState
) -> None:
    """design §4 L3-07 and its ``CONSISTENT`` sub-case, on the real durable path."""
    committed = _composite(
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.FILLED,
        knowledge_state=positive,
        capacity_state=CapacityState.POSITION_CONSUMED,
    )
    path = tmp_path / f"store-{positive}.sqlite3"
    with CompositeStateStore(path) as store:
        store.commit_composite(committed)

    outcome = reload_conservative(path, _IDENTITY)
    assert outcome.composite.knowledge_state is KnowledgeState.CONFLICTED
    assert outcome.composite.broker_order_state is BrokerOrderState.FILLED


def test_the_identity_is_re_derived_from_the_store(tmp_path) -> None:
    '"real identity (logical)" — the reconstruction carries the stored intent identity.'
    path = _write(tmp_path, _composite())
    outcome = reload_conservative(path, _IDENTITY)
    assert outcome.composite.intent_identity == _IDENTITY
    assert outcome.pre_restart.intent_identity == _IDENTITY
