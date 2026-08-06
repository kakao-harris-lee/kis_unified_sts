"""S-4 — the ``python -m`` crash/restart worker (design #39 §5.1 / §5.2).

Two modes, one process each::

    python -m tos.staterestore._l3_worker writer <scenario-id> <store-path> <cache-path>
    python -m tos.staterestore._l3_worker reader <scenario-id> <store-path> <cache-path>

The **writer** commits the scenario's durable markers and then dies at the scenario's
parametrized crash point via ``os._exit(137)`` — a *deterministic* application crash,
not a racy externally-delivered ``SIGKILL`` (design #39 O-2 / OQ-3). Nothing is flushed,
unwound, or finalized: whatever sqlite had already committed is all that survives.

The **reader** is a *fresh* process. Its only channel to the writer is the on-disk store,
which is precisely what VER-002-001 §5 line 151-153 means by "real persistence …
boundaries". It reloads through :func:`tos.staterestore.reload_conservative` and prints
one JSON verdict object on stdout.

Parametrization is **argv only.** ``os.environ`` / ``os.getenv`` is forbidden anywhere
under ``tos/`` by the firewall's TOS-FW-C rule (``tools/tos_firewall_check.py`` lines
214-216 / 237-240), because capability must not be reachable through ambient env. The
same AST gate detects **only** ``environ``/``getenv`` on ``os``, so the ``os._exit``
below is gate-clean; the ``tos/tests`` convention of avoiding ``os`` entirely
(``tos/tests/test_import_closure.py`` line 6) is an *import-closure isolation* practice
for those tests, not a firewall rule (design #39 §5.1, measured).

Oracle independence
-------------------
This module owns the crash scenarios' **inputs** (which composite is committed, and
where the crash lands). It does **not** own their expected outputs. The Expected
reconstructions live in the outside orchestration
(``tests/tos_l3/test_state_ev_004_crash_restart.py``) as hand-derived hardcoded anchors,
which the firewall's reverse rule (TOS-FW-R) structurally prevents from calling
``reconstruct_conservative`` at all (design #39 §5.3 / O-3). A bug in the implementation
therefore cannot make the oracle agree with it.

Commit-composite legality
-------------------------
Several §4 cells pin composites that ADR-002-005 §14 lists as valid *observations* while
the static CPL predicate flags them (``Broker=UNKNOWN`` forces CPL-5's exact
``QUARANTINED_UNKNOWN``). Design #39 §4 makes checking that legality an implementation
obligation, so every scenario carries its **expected CPL violation set** and the writer
compares :func:`tos.orthostate.coupling_violations` against it before committing
anything. A disagreement aborts loudly with exit code
:data:`CPL_MISMATCH_EXIT` — never a silent commit (see
:data:`SCENARIOS` for the per-cell justification).
"""

from __future__ import annotations

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
from tos.staterestore.reload import reload_conservative
from tos.staterestore.store import CompositeStateStore

#: The deterministic crash status. 137 is the conventional "killed" code; the value is a
#: constant so the outside orchestration can assert the crash was *the parametrized one*
#: and not an ordinary interpreter failure (which exits 1) or a refusal (see below).
CRASH_EXIT = 137

#: The writer aborts with this code when a scenario's committed composite does not carry
#: the CPL violation set the scenario pins. A wrong-but-committed composite would make
#: every downstream anchor meaningless, so this is loud and terminal.
CPL_MISMATCH_EXIT = 70

#: Usage / unknown-scenario refusal.
USAGE_EXIT = 64

#: The intent identity every scenario uses. Fixed, so a run is reproducible from argv
#: alone (VER §9.1 seed/schedule reproducibility).
INTENT_IDENTITY = "STATE-EV-004-L3-PILOT-INTENT"

#: The side-conditions the committed composites are evaluated under. ``authority_epoch_
#: current=True`` is the *only* positive flag: every §4 cell has an attempt at or beyond
#: ``SEND_STARTED``, and CPL-6 requires a current authority epoch for exactly those. The
#: remaining flags stay ``None`` (fail-closed), so no proof is asserted that the scenario
#: does not actually establish.
COMMIT_SIDE_CONDITIONS = CouplingSideConditions(authority_epoch_current=True)


@dataclass(frozen=True)
class CrashScenario:
    """One design #39 §4 catalog cell, as the worker's *input* half.

    Attributes:
        scenario_id: The catalog id (``L3-01`` … ``L3-08``).
        intent_state: Pinned Intent dimension.
        transmission_attempt_state: Pinned Transmission Attempt dimension.
        broker_order_state: Pinned Broker Order dimension.
        knowledge_state: Pinned Knowledge dimension — the value that is made **durable**.
        capacity_state: Pinned Capacity dimension.
        commit_dimension_count: How many of :data:`DIMENSION_COMMIT_ORDER`'s five
            dimensions are committed before the crash. ``5`` = complete store; anything
            less produces the line 1045 "incomplete store" by crashing between two
            per-dimension transactions.
        write_stale_cache: Whether an *optimistic* cache file is written after the
            markers (line 1045 "stale caches"). Its content is deliberately the most
            favourable knowledge value there is.
        uncommitted_knowledge: An in-memory knowledge value the process held but never
            persisted — the "crash **before evidence persistence**" limb of line 1045.
            It dies with the process, which is the whole point: the reader must not
            resurrect it.
        expected_cpl: The CPL invariant ids the committed composite is expected to
            raise. See :data:`SCENARIOS` for why several cells are non-empty.
        note: Why this cell exists, in one line.
    """

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


#: ``{CPL-5}`` — ADR-002-005 §10 line 160 makes ``Broker=UNKNOWN`` (or Knowledge in
#: ``{CONFLICTED, QUARANTINED}``) demand ``Capacity=QUARANTINED_UNKNOWN`` *exactly*,
#: while §14 lists ``Broker=UNKNOWN`` with ``Capacity=POTENTIALLY_LIVE`` among its "all
#: valid" composites (line 208, verbatim). The repository already resolves that tension
#: the same way — ``tos/tests/orthostate/_orthostate_strategies.py`` lines 147 and 167
#: label the two affected §14 rows "representable BUT coupling-negative (… fires CPL-5)"
#: — so these composites are *representable observations that carry a flagged coupling*,
#: which is exactly the state a crash can leave behind. Pinning the expected set (rather
#: than demanding ``∅``) keeps the check loud: a composite whose CPL status differs from
#: this pin aborts the writer.
_CPL5 = frozenset({"CPL-5"})
_CPL_CLEAN: frozenset[str] = frozenset()

#: The design #39 §4 catalog, eight cells. Every dimension is pinned (§4 MAJOR-2): the
#: outside anchors are derived from these by hand, so an unpinned dimension would make
#: an anchor underdetermined.
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

#: What the optimistic cache file claims. The most favourable knowledge value there is,
#: so a reader that trusted it would be caught by the ``never RECONCILED`` invariant.
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
    """Print ``message`` on stderr and exit ``code`` without unwinding.

    Typed ``NoReturn`` so callers do not need a narrowing assertion after it: the
    refusal really is terminal, and saying so in the signature is what makes the code
    after a refusal unreachable rather than merely unreached.
    """
    sys.stderr.write(f"tos-l3-worker: {message}\n")
    sys.stderr.flush()
    os._exit(code)


def run_writer(scenario: CrashScenario, store_path: Path, cache_path: Path) -> None:
    """Commit the scenario's durable markers, then crash deterministically.

    Never returns: the last statement is ``os._exit``.
    """
    composite = scenario.composite()

    # Commit-composite legality (design #39 §4). Measured, then compared against the
    # scenario's own pin — a mismatch is a defect in the catalog or in the predicate,
    # and either way must not be committed silently.
    observed_cpl = coupling_violations(composite, COMMIT_SIDE_CONDITIONS)
    if observed_cpl != scenario.expected_cpl:
        _fail(
            f"{scenario.scenario_id}: committed composite raises CPL "
            f"{sorted(observed_cpl)} but the catalog pins "
            f"{sorted(scenario.expected_cpl)} — refusing to commit",
            CPL_MISMATCH_EXIT,
        )

    with CompositeStateStore(store_path) as store:
        committed = store.commit_composite(
            composite, stop_after=scenario.commit_dimension_count
        )

    if scenario.write_stale_cache:
        cache_path.write_text(cache_payload(scenario), encoding="utf-8")

    # The in-memory optimistic knowledge (L3-03) exists only here and is about to be
    # destroyed by the crash. Naming it on stderr makes the "lost ACK" observable in the
    # run log without ever making it durable.
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
    """Reload from the store in this fresh process and print the verdict.

    Returns:
        The process exit code (``0``).
    """
    outcome = reload_conservative(
        store_path,
        INTENT_IDENTITY,
        cache_paths=(cache_path,),
    )
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
    """Dispatch on argv (design #39 S-4 — argv only, never ``os.environ``).

    Args:
        argv: ``[mode, scenario_id, store_path, cache_path]``.

    Returns:
        The reader's exit code. The writer never returns.
    """
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
    return USAGE_EXIT  # unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
