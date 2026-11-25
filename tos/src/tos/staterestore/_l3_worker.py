"""S-4 — the ``python -m`` crash/restart worker (design #39 §5.1 / §5.2)."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    CouplingSideConditions,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransmissionAttemptState,
    coupling_violations,
)
from tos.rcl import CapacityState
from tos.staterestore.reload import (
    StoreOpenRefused,
    open_store,
    reload_conservative,
)

CRASH_EXIT = 137

CPL_MISMATCH_EXIT = 70

USAGE_EXIT = 64

STORE_UNOPENABLE_EXIT = 71

INTENT_IDENTITY = "STATE-EV-004-L3-PILOT-INTENT"

COMMIT_SIDE_CONDITIONS = CouplingSideConditions(authority_epoch_current=True)


@dataclass(frozen=True)
class CrashScenario:
    """One design #39 §4 catalog cell, as the worker's *input* half."""

    scenario_id: str
    intent_state: IntentState
    transmission_attempt_state: TransmissionAttemptState
    broker_order_state: BrokerOrderState
    knowledge_state: KnowledgeState
    capacity_state: CapacityState
    commit_dimension_count: int
    expected_cpl: frozenset[str]
    note: str
    write_stale_cache: bool = False
    uncommitted_knowledge: KnowledgeState | None = None

    def composite(self) -> CompositeState:
        """The pinned five-dimension composite this scenario makes durable."""
        return CompositeState(
            intent_identity=INTENT_IDENTITY,
            intent_state=self.intent_state,
            transmission_attempt_state=self.transmission_attempt_state,
            broker_order_state=self.broker_order_state,
            knowledge_state=self.knowledge_state,
            capacity_state=self.capacity_state,
        )


_CPL5 = frozenset({"CPL-5"})
_CPL_CLEAN: frozenset[str] = frozenset()

SCENARIOS: dict[str, CrashScenario] = {
    "L3-01": CrashScenario(
        scenario_id="L3-01",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
        broker_order_state=BrokerOrderState.UNKNOWN,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=5,
        expected_cpl=_CPL5,
        note="crash after durable SEND_STARTED, before the broker received anything",
    ),
    "L3-02": CrashScenario(
        scenario_id="L3-02",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=BrokerOrderState.UNKNOWN,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=5,
        expected_cpl=_CPL5,
        note=(
            "crash after the (modelled) network transmission — the transmission is a "
            "VirtualBroker-class marker, zero real bytes; real broker network is "
            "residual R-N"
        ),
    ),
    "L3-03": CrashScenario(
        scenario_id="L3-03",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
        broker_order_state=BrokerOrderState.UNKNOWN,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=5,
        uncommitted_knowledge=KnowledgeState.RECONCILED,
        expected_cpl=_CPL5,
        note=(
            "crash BEFORE evidence persistence: an in-memory ACK had already produced "
            "an optimistic RECONCILED that was never made durable"
        ),
    ),
    "L3-04": CrashScenario(
        scenario_id="L3-04",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=BrokerOrderState.WORKING,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=5,
        expected_cpl=_CPL_CLEAN,
        note="crash at a NON-terminal broker-order boundary (WORKING)",
    ),
    "L3-05": CrashScenario(
        scenario_id="L3-05",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
        broker_order_state=BrokerOrderState.UNKNOWN,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=3,
        expected_cpl=_CPL5,
        note=(
            "INCOMPLETE STORE: crash between per-dimension transactions, so Broker and "
            "Knowledge never became durable at all"
        ),
    ),
    "L3-06": CrashScenario(
        scenario_id="L3-06",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=BrokerOrderState.WORKING,
        knowledge_state=KnowledgeState.UNOBSERVED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=5,
        write_stale_cache=True,
        expected_cpl=_CPL_CLEAN,
        note=(
            "STALE CACHE: an optimistic RECONCILED cache file survives the crash beside "
            "the conservative store"
        ),
    ),
    "L3-07": CrashScenario(
        scenario_id="L3-07",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
        broker_order_state=BrokerOrderState.FILLED,
        knowledge_state=KnowledgeState.RECONCILED,
        capacity_state=CapacityState.POSITION_CONSUMED,
        commit_dimension_count=5,
        expected_cpl=_CPL_CLEAN,
        note=(
            "positive canary: ADR-002-005 §14 line 211 verbatim — a terminal broker "
            "order with positive knowledge, so the §13 line 199 downgrade must FIRE"
        ),
    ),
    "L3-08": CrashScenario(
        scenario_id="L3-08",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=BrokerOrderState.UNKNOWN,
        knowledge_state=KnowledgeState.CONFLICTED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
        commit_dimension_count=5,
        expected_cpl=_CPL5,
        note=(
            "durability mechanism: ADR-002-005 §14 line 208 verbatim, already "
            "conservative, so the projection is the identity and the reload must be a "
            "lossless round-trip of the committed five dimensions"
        ),
    ),
}

STALE_CACHE_KNOWLEDGE = KnowledgeState.RECONCILED


def cache_payload(scenario: CrashScenario) -> str:
    """The optimistic cache bytes for ``scenario`` (S-3 target)."""
    return json.dumps(
        {
            "intent_identity": INTENT_IDENTITY,
            "scenario_id": scenario.scenario_id,
            "knowledge_state": str(STALE_CACHE_KNOWLEDGE),
            "note": "optimistic resume cache — must be discarded, never consumed",
        },
        sort_keys=True,
    )


def _fail(message: str, code: int) -> NoReturn:
    """Print ``message`` on stderr and exit ``code`` without unwinding."""
    sys.stderr.write(f"tos-l3-worker: {message}\n")
    sys.stderr.flush()
    os._exit(code)


def run_writer(scenario: CrashScenario, store_path: Path, cache_path: Path) -> None:
    """Commit the scenario's durable markers, then crash deterministically."""
    composite = scenario.composite()

    observed_cpl = coupling_violations(composite, COMMIT_SIDE_CONDITIONS)
    if observed_cpl != scenario.expected_cpl:
        _fail(
            f"{scenario.scenario_id}: committed composite raises CPL "
            f"{sorted(observed_cpl)} but the catalog pins "
            f"{sorted(scenario.expected_cpl)} — refusing to commit",
            CPL_MISMATCH_EXIT,
        )

    try:
        store = open_store(store_path)
    except StoreOpenRefused as exc:
        _fail(str(exc), STORE_UNOPENABLE_EXIT)
    with contextlib.closing(store):
        committed = store.commit_composite(
            composite, stop_after=scenario.commit_dimension_count
        )

    if scenario.write_stale_cache:
        cache_path.write_text(cache_payload(scenario), encoding="utf-8")

    if scenario.uncommitted_knowledge is not None:
        sys.stderr.write(
            f"tos-l3-worker: {scenario.scenario_id}: holding UNPERSISTED knowledge "
            f"{scenario.uncommitted_knowledge} in memory at crash time\n"
        )

    sys.stdout.write(
        json.dumps(
            {
                "role": "writer",
                "scenario_id": scenario.scenario_id,
                "pid": os.getpid(),
                "committed_dimensions": [str(d) for d in committed],
                "store_path": str(store_path),
                "crash_exit": CRASH_EXIT,
            },
            sort_keys=True,
        )
        + "\n"
    )
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(CRASH_EXIT)


def run_reader(scenario: CrashScenario, store_path: Path, cache_path: Path) -> int:
    """Reload from the store in this fresh process and print the verdict."""
    try:
        outcome = reload_conservative(
            store_path,
            INTENT_IDENTITY,
            cache_paths=(cache_path,),
        )
    except StoreOpenRefused as exc:
        _fail(str(exc), STORE_UNOPENABLE_EXIT)
    post = outcome.composite
    verdict = {
        "role": "reader",
        "scenario_id": scenario.scenario_id,
        "pid": os.getpid(),
        "store_path": str(store_path),
        "store_exists": Path(store_path).is_file(),
        "store_complete": outcome.store_complete,
        "filled_dimensions": [str(d) for d in outcome.filled_dimensions],
        "discarded_caches": list(outcome.discarded_caches),
        "cache_present_after_reload": cache_path.is_file(),
        "intent_identity": post.intent_identity,
        "intent_state": str(post.intent_state),
        "transmission_attempt_state": str(post.transmission_attempt_state),
        "broker_order_state": str(post.broker_order_state),
        "knowledge_state": str(post.knowledge_state),
        "capacity_state": str(post.capacity_state),
        "committed_dimensions_readback": {
            str(dimension): str(getattr(outcome.pre_restart, attribute))
            for dimension, attribute in (
                (StateDimension.INTENT, "intent_state"),
                (StateDimension.CAPACITY, "capacity_state"),
                (StateDimension.TRANSMISSION_ATTEMPT, "transmission_attempt_state"),
                (StateDimension.BROKER_ORDER, "broker_order_state"),
                (StateDimension.KNOWLEDGE, "knowledge_state"),
            )
        },
    }
    sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
    sys.stdout.flush()
    return 0


_USAGE = (
    "usage: python -m tos.staterestore._l3_worker "
    "{writer|reader} <scenario-id> <store-path> <cache-path>"
)


def main(argv: list[str]) -> int:
    """Dispatch on argv (design #39 S-4 — argv only, never ``os.environ``)."""
    if len(argv) != 4:
        _fail(f"expected 4 arguments, got {len(argv)}. {_USAGE}", USAGE_EXIT)
    mode, scenario_id, store_raw, cache_raw = argv
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        _fail(
            f"unknown scenario {scenario_id!r}; known: {sorted(SCENARIOS)}", USAGE_EXIT
        )
    store_path, cache_path = Path(store_raw), Path(cache_raw)
    if mode == "writer":
        run_writer(scenario, store_path, cache_path)
    if mode == "reader":
        return run_reader(scenario, store_path, cache_path)
    _fail(f"unknown mode {mode!r}. {_USAGE}", USAGE_EXIT)
    return USAGE_EXIT


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
