"""Backtest=paper parity + blind resubmit 0 (TOS Phase 3 Wave 3 Lane F-R; plan §3.2 bullets 2-3,
§5 — 종료 조건: "백테스트와 paper 가 같은 코어·시퀀서" / "유실·지연·역전 ⇒ blind resubmit 0").

**Parity adapter statement (deliverable 1's own required disclosure; revised for ``[KW3-RD]``,
2026-09-09 — see "F-R-3" below).** The two paths cannot be fed literally byte-identical
``EngineEvent`` objects, and the surviving difference is exactly the injected seam the plan says
parity must tolerate (design #31 §12 "차이는 EventSource/Transmit 주입뿐"):

* ``reference`` (the ``OrderingEvent`` coordinate) always differs — each driver owns its own
  monotone yield-order counter on its own continuity
  (:class:`tos.backtest.driver.YieldOrderCounter` vs
  :class:`tos_runtime.engine.driver._YieldOrderCounter`), by design (module docstrings of both:
  "there is no reset/rewind" / "one monotone counter stamps every yielded event"). This is
  EventSource-local plumbing, never business content.
* ``time`` (``TimeAdmissionInputs``) always differs in its exact bound VALUES — the backtest side
  derives it from :class:`tos.backtest.resolver.BarTimeProjection` projecting a synthetic bar's
  opaque coordinate, the engine-driver side carries ``fx.admitting_time_inputs()``'s fixed
  literals — because each side must independently satisfy the SAME structural requirement
  ("admit, do not withhold on freshness") through its own injected bound set, not because the
  runs disagree about anything.

Neither of these is covered by ``Proposal.canonical_digest`` (see below), so neither affects the
``DECISION_TICK`` half of the comparison.

**F-R-3 (2026-09-09): the ``EGRESS_RESULT`` KIND must now be the SAME on both sides too.** Kernel
commit ``[KW3-RD]`` gave ``EGRESS_RESULT`` events a real ``outcome_digest``
(``tos.engine.records.EgressResultOutcome`` — covers ``disposition``, ``capacity_state``,
``knowledge``, ``filled_quantity``, ``remaining_quantity``, ``pre_quarantine_capacity``). Before
that landed, this test's engine-driver side used ``fx.FakeGateway``'s synchronous auto-``ACK``
while the backtest side settled a ``FULL_FILL`` — "harmless" only because an ``EGRESS_RESULT``'s
``outcome_digest`` used to be unconditionally ``None`` either way, which made the comparison
*vacuous* for the result event (``None == None`` reads as "uncompared", not "verified identical" —
exactly the gap ``[KW3-RD]`` closed). An ``ACK`` and a ``FULL_FILL`` legitimately hash to different
values now (different ``capacity_state``/``knowledge``), so "차이는 EventSource/Transmit 주입뿐"
requires the SAME Transmit *semantics*, not merely "a Transmit of some kind". The engine-driver
side now drives :class:`~tos_runtime.tests.engine._parity_fixtures.SyntheticBrokerGateway` — a
thin ``Transmit``-protocol adapter REUSING (never reimplementing) the kernel's own, already-shipped
:class:`~tos.brokeradapter.synthetic.SyntheticPaperTransport` (design #34 §5.2), the same
deterministic synthetic-broker path ``tos_runtime.compose._wiring`` wires for the real paper core.
**Injected, shared magnitude:** :data:`~tos_runtime.tests.engine._parity_fixtures.PARITY_QUANTITY`
(``Decimal(1)``) is the SAME literal fed to the backtest side's ``FillParameters.scenario_quantity``
and to the synthetic broker's ``send_once(..., quantity=PARITY_QUANTITY)`` call — both fill it in
full via their own kernel fill-band arithmetic and land on identical ``filled_quantity=Decimal(1)``
/ ``remaining_quantity=Decimal(0)`` / ``kind=FULL_FILL``. ``broker_execution_id`` still differs
(the synthetic broker stamps one, the backtest fill model never does) — irrelevant, because
``EgressResultOutcome`` does not cover it.

**Why the rest doesn't break the parity claim.** ``EventResult.outcome_digest`` is
``EventResult.pipeline.outcome_digest`` when ``pipeline`` is set (a ``DECISION_TICK`` that reached
:mod:`tos.engine.pipeline` — ``core.py``'s own ``EventResult.outcome_digest`` property), else
``EventResult.result_outcome_digest`` (an ``EGRESS_RESULT``'s applied-outcome digest, ``[KW3-RD]``).
For a ``DECISION_TICK`` that digest is the emitted :class:`tos.dsl.Proposal`'s own
``canonical_digest``, whose covered field set (``Proposal._COVERED_FIELDS`` — ``proposer``,
``target_kind``, ``account``, ``instrument``, ``direction``, ``position_effect``,
``quantity_basis``, ``edge_or_confidence``, ``timing_and_execution_constraints``, ``rationale``,
``decision_context_capsule``, ``dsl_version``, ``config_version``, ``authority``) includes NEITHER
``reference`` NOR ``time`` — so as long as both sides register the byte-identical
:class:`~tos.dsl.AuthoredStrategy` (same policy content, same
``dsl_version``/``config_binding_version`` — both sides call ``fx.registry_with()``, which issues
the strategy fresh each time but from IDENTICAL literal content, and ``AuthoredStrategy.issue`` is
content-addressed with no RNG) against the byte-identical
:class:`~tos.capsule.DecisionContextCapsule` (both sides use ``fx.issue_capsule(seq=1)``), the
emitted Proposal's digest is provably reference/time-independent and must match exactly. For the
``EGRESS_RESULT`` half, both sides now apply the SAME ``FULL_FILL`` payload (same
``filled_quantity``/``remaining_quantity``) against a fresh reservation through the SAME kernel
ledger logic (``ProvisionalReservationLedger.apply_egress_result``), so the resulting
``EgressResultOutcome`` — and therefore ``result_outcome_digest`` — is provably identical too; the
compared sequence is now ``(proposal_digest, result_outcome_digest)`` on both paths, with BOTH
entries genuinely non-``None`` (asserted explicitly below — the whole point of ``[KW3-RD]``).

**Blind resubmit 0 (deliverable 2).** Three scenarios drive the SAME real, wired
:class:`~tos_runtime.engine.driver.EngineDriver` (durable :class:`~tos_runtime.engine.inbox
.SqliteEventInbox`, a real :class:`~tos.engine.EngineCore` with the durable
:class:`~tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter` so kernel-recorded
``ATTEMPT_REQUEST_CREATED``/``SEND_HANDED_OFF`` receipts are queryable) with a counting
``fx.FakeGateway`` transport double: lost result (TIMEOUT), late result (TIMEOUT then FULL_FILL),
and a reversed reference (a FULL_FILL crossing an already-applied CANCEL_ACK ->
``NON_MONOTONIC_PROJECTION``). In every scenario the transport call count never advances beyond
what a genuinely NEW decision authorizes — RFC-005 §11 "retry is a new send", never a resend of an
old attempt.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, EngineEvent
from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore

from . import _fixtures as fx
from . import _parity_fixtures as pfx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


# =================================================================================================
# Deliverable 1 — backtest=paper parity (plan §3.2 bullet 2)
# =================================================================================================


def test_backtest_and_engine_driver_outcome_digests_match_for_the_same_strategy(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
) -> None:
    """The same admitted strategy, the same event sequence (module docstring's adapter statement
    notwithstanding), driven through (a) :class:`~tos.backtest.driver.BacktestDriver` and (b) the
    real, durable :class:`~tos_runtime.engine.driver.EngineDriver` — the ``outcome_digest``
    sequences must be identical.
    """
    # -- (a) BacktestDriver.run(core, bars) --------------------------------------------------
    backtest_driver, backtest_core, _fill_model = pfx.build_backtest_driver_and_core()
    backtest_run = backtest_driver.run(backtest_core, pfx.one_bar())
    backtest_digests = tuple(r.outcome_digest for r in backtest_run.event_results)

    # -- (b) the compose-shaped EngineDriver over a durable SqliteEventInbox, settling through
    # -- the SAME kernel synthetic-broker path (F-R-3) with the SAME injected quantity -----------
    gateway = pfx.SyntheticBrokerGateway(quantity=pfx.PARITY_QUANTITY)
    engine_driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
    )
    engine_driver.bind_gateway(gateway)
    tick_result = engine_driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    engine_digests = pfx.ordered_consumed_outcome_digests(evidence_store)

    # -- both sides actually reached a real ACTION proposal + a hand-off, not a vacuous WITHHELD --
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    assert backtest_run.handoff_count == 1
    assert tick_result.outcome_digest is not None

    # -- exactly one tick + one re-injected egress result on each side ------------------------
    assert len(backtest_digests) == 2
    assert len(engine_digests) == 2

    # -- F-R-3: the result event's own digest is now genuinely non-None on BOTH sides — this is
    # -- the whole point of [KW3-RD] (before it, both were None and the comparison was vacuous) --
    assert backtest_digests[0] is not None and backtest_digests[1] is not None
    assert engine_digests[0] is not None and engine_digests[1] is not None

    # -- the parity claim itself: byte-identical outcome_digest sequences, tick AND result -------
    assert tick_result.outcome_digest == backtest_digests[0]
    assert backtest_digests == engine_digests


# =================================================================================================
# Deliverable 2 — blind resubmit 0 (plan §3.2 bullet 3)
# =================================================================================================


def test_blind_resubmit_lost_then_late_result_then_a_fresh_decision_uses_a_new_attempt(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
) -> None:
    """Scenarios 1 (lost result -> TIMEOUT) and 2 (late result -> FULL_FILL after TIMEOUT),
    chained into a fresh decision that must use a NEW attempt.

    **Finding, measured directly (2026-09-09, this lane).** ``ProvisionalReservationLedger`` has
    no release path in this Phase (``tos.engine.state.PROJECTION_ORDER`` carries no ``RELEASED``
    member — release is the RCL's, RFC-002 §9.1:557): a genuinely ``APPLIED`` ``FULL_FILL``
    advances the SAME scope's outstanding reservation only to ``CapacityState.POSITION_CONSUMED``,
    which is STILL counted against the scope's ``max_unresolved_send_per_scope`` bound. A second
    ``DECISION_TICK`` on the SAME ``InstrumentKey``, issued after this scenario's own FULL_FILL is
    durably ``APPLIED``, was confirmed (RED, before this test's own final wiring) to be refused at
    the capacity stage every time — "resolve the first before the second decision" does not, by
    itself, free that scope's slot in this Phase; only a genuinely DIFFERENT scope has room. So
    the "fresh decision, new attempt" half below drives ``pfx.second_decision_tick_event`` (a
    SECOND ``InstrumentKey`` in the SAME registry/core/driver — see ``_parity_fixtures.py``'s own
    module-level finding) rather than a second tick on the first scope, which this Phase's kernel
    can never admit again once occupied.

    **RED-first evidence (recorded, not merely asserted here).** ``assert len(gateway.attempts)
    == 1`` after the TIMEOUT injection was verified to actually discriminate a regression:
    temporarily lowering ``max_send_result_wait_ms`` while leaving a (hypothetical) blind-resend
    path wired would make this count 2 immediately after the timeout fires, before any new
    decision — the assertion fails loudly rather than passing vacuously. With the real,
    already-landed ``EngineDriver``/``ResultDisposition`` wiring (TOS Phase 3 Wave 1/2,
    independently reviewed and approved — plan §7), the count stays 1 through both the TIMEOUT
    and the late FILL, and only advances to 2 once the second scope's genuinely NEW
    ``DECISION_TICK`` is admitted.
    """
    gateway = fx.FakeGateway(
        auto_ack=False
    )  # no synchronous result — "lost result" scenario 1
    sink = pfx.durable_engine_sink(evidence_store)
    driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
        sink=sink,
        max_send_result_wait_ms=1000,
        registry=pfx.registry_with_two_scopes(),
    )
    driver.bind_gateway(gateway)

    # -- scenario 1: lost result -> TIMEOUT ----------------------------------------------------
    first_tick = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert first_tick.flow is not None and first_tick.flow.handed_off is True
    first_attempt_id = first_tick.flow.attempt.attempt_id  # type: ignore[union-attr]
    assert (
        len(gateway.attempts) == 1
    )  # exactly one transport call for the hand-off itself

    monotonic_source.advance(1500)  # type: ignore[attr-defined]  # past the 1000ms bound
    timeout_result = driver.run_once()
    assert timeout_result is not None
    assert timeout_result.reservation is not None
    assert timeout_result.reservation.knowledge.value == "UNKNOWN"
    assert timeout_result.reservation.capacity_state.value == "QUARANTINED_UNKNOWN"
    assert len(gateway.attempts) == 1  # <-- blind resubmit 0: TIMEOUT never re-sends

    # it fires exactly once — no repeated TIMEOUT spam for the same pending attempt
    assert driver.run_once() is None

    # -- scenario 2: late result -> FULL_FILL, after the TIMEOUT -------------------------------
    late_fill = EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=EgressResultPayload(
            instrument_key=fx.instrument_key(),
            attempt_id=first_attempt_id,
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
        ),
    )
    fill_result = driver.enqueue_and_run(late_fill)
    assert fill_result.result_disposition is ResultDisposition.APPLIED
    assert fill_result.reservation is not None
    assert fill_result.reservation.knowledge.value == "FILLED"
    assert (
        len(gateway.attempts) == 1
    )  # <-- still one: the late FILL is consumption, not a resend

    # -- a fresh decision, on a SECOND scope (module docstring's own finding: the first scope's
    # -- slot is never freed in this Phase, resolved or not) — it can ONLY reach the send boundary
    # -- through a fresh kernel-recorded ATTEMPT_REQUEST_CREATED -> SEND_HANDED_OFF pair, never a
    # -- resend of the first scope's own (already-resolved) attempt -------------------------------
    second_tick = driver.enqueue_and_run(pfx.second_decision_tick_event(seq=2))
    assert second_tick.flow is not None and second_tick.flow.handed_off is True
    second_attempt_id = second_tick.flow.attempt.attempt_id  # type: ignore[union-attr]
    assert second_attempt_id != first_attempt_id
    assert (
        len(gateway.attempts) == 2
    )  # exactly one NEW transport call for the NEW decision

    created_ids = pfx.attempt_ids_for_kind(evidence_store, "ATTEMPT_REQUEST_CREATED")
    handed_off_ids = pfx.attempt_ids_for_kind(evidence_store, "SEND_HANDED_OFF")
    assert created_ids == [first_attempt_id, second_attempt_id]
    assert handed_off_ids == [first_attempt_id, second_attempt_id]


def test_blind_resubmit_reversed_reference_latches_new_risk_and_refuses_the_next_decision(
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    monotonic_source: object,
) -> None:
    """Scenario 3: a result whose reference regresses (a ``FULL_FILL`` crossing an already-applied
    ``CANCEL_ACK``) yields ``NON_MONOTONIC_PROJECTION`` and durably latches a runtime-wide new-risk
    halt (ADR-002-005 §10 "an invariant violation ... is an immediate new-risk halt condition") —
    the compose root's own single-``InstrumentKey`` + ``max_unresolved_send_per_scope=1`` bound is
    not what blocks the next decision here (there is no second instrument or relaxed bound in
    this test's wiring either); the NEW-RISK LATCH is what refuses it, and that refusal — not a
    resend of the reversed attempt — is the expected, asserted outcome.
    """
    gateway = fx.FakeGateway(auto_ack=False)
    sink = pfx.durable_engine_sink(evidence_store)
    driver, _core = pfx.build_engine_driver(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        monotonic_source=monotonic_source,
        transmit=gateway,
        sink=sink,
        max_send_result_wait_ms=pfx.NO_TIMEOUT_WITHIN_TEST,
    )
    driver.bind_gateway(gateway)

    tick_result = driver.enqueue_and_run(fx.decision_tick_event(seq=1))
    assert tick_result.flow is not None and tick_result.flow.handed_off is True
    attempt_id = tick_result.flow.attempt.attempt_id  # type: ignore[union-attr]
    assert len(gateway.attempts) == 1

    cancel_result = driver.enqueue_and_run(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.CANCEL_ACK,
            ),
        )
    )
    assert cancel_result.result_disposition is ResultDisposition.APPLIED
    assert (
        inbox.new_risk_halt() is None
    )  # not latched yet — the crossing fill is what violates

    reversed_result = driver.enqueue_and_run(
        EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.FULL_FILL,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("0"),
            ),
        )
    )
    assert (
        reversed_result.result_disposition is ResultDisposition.NON_MONOTONIC_PROJECTION
    )
    assert (
        len(gateway.attempts) == 1
    )  # neither result triggered any transport call at all

    halt = inbox.new_risk_halt()
    assert halt is not None  # the coupling violation durably latched a new-risk halt

    # -- a subsequent NEW decision is REFUSED by the latch — core.handle is never even called for
    # -- it (no pipeline, no outcome_digest) — never a blind resend of the reversed attempt ------
    refused = driver.enqueue_and_run(fx.decision_tick_event(seq=2))
    assert refused.pipeline is None
    assert refused.outcome_digest is None
    assert "NEW_RISK_HALTED_BY_COUPLING_VIOLATION" in (refused.detail or "")
    assert len(gateway.attempts) == 1  # the refusal produced no transport call at all

    # -- and the refusal touched neither of the two send-permit kinds: no new attempt was ever
    # -- authored for the refused tick.
    created_ids = pfx.attempt_ids_for_kind(evidence_store, "ATTEMPT_REQUEST_CREATED")
    handed_off_ids = pfx.attempt_ids_for_kind(evidence_store, "SEND_HANDED_OFF")
    assert created_ids == [attempt_id]
    assert handed_off_ids == [attempt_id]
