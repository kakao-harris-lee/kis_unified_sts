"""Backtest=paper parity + blind resubmit 0 (TOS Phase 3 Wave 3 Lane F-R; plan §3.2 bullets 2-3,
§5 — 종료 조건: "백테스트와 paper 가 같은 코어·시퀀서" / "유실·지연·역전 ⇒ blind resubmit 0").

**Parity adapter statement (deliverable 1's own required disclosure).** The two paths cannot be
fed literally byte-identical ``EngineEvent`` objects, and the difference is exactly the injected
seam the plan says parity must tolerate (design #31 §12 "차이는 EventSource/Transmit 주입뿐"):

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
* the re-injected ``EGRESS_RESULT`` KIND differs (``FULL_FILL`` from
  :class:`~tos.backtest.fills.DeterministicFillModel` vs ``ACK`` from
  ``fx.FakeGateway``'s auto-ack) — a Transmit-local choice, not a business fact either.

**Why none of this breaks the parity claim.** ``EventResult.outcome_digest`` is
``EventResult.pipeline.outcome_digest`` — populated ONLY for a ``DECISION_TICK`` that reaches
:mod:`tos.engine.pipeline` (``core.py``'s own ``EventResult.outcome_digest`` property) — and for a
``DECISION_TICK`` that digest is the emitted :class:`tos.dsl.Proposal`'s own ``canonical_digest``,
whose covered field set (``Proposal._COVERED_FIELDS`` — ``proposer``, ``target_kind``, ``account``,
``instrument``, ``direction``, ``position_effect``, ``quantity_basis``, ``edge_or_confidence``,
``timing_and_execution_constraints``, ``rationale``, ``decision_context_capsule``, ``dsl_version``,
``config_version``, ``authority``) includes NEITHER ``reference`` NOR ``time`` — so as long as both
sides register the byte-identical :class:`~tos.dsl.AuthoredStrategy` (same policy content, same
``dsl_version``/``config_binding_version`` — both sides call ``fx.registry_with()``, which issues
the strategy fresh each time but from IDENTICAL literal content, and ``AuthoredStrategy.issue`` is
content-addressed with no RNG) against the byte-identical
:class:`~tos.capsule.DecisionContextCapsule` (both sides use ``fx.issue_capsule(seq=1)``), the
emitted Proposal's digest is provably reference/time-independent and must match exactly.
:class:`~tos.engine.core.EventResult` for an ``EGRESS_RESULT`` never sets ``pipeline`` at all
(``core.py::_handle_egress_result`` — every returned branch omits it), so its ``outcome_digest`` is
honestly ``None`` on BOTH sides regardless of the differing result kind above — the sequence being
compared is ``(proposal_digest, None)`` on both paths.

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

    # -- (b) the compose-shaped EngineDriver over a durable SqliteEventInbox ------------------
    gateway = (
        fx.FakeGateway()
    )  # auto_ack=True — synchronous ACK, mirroring BacktestDriver's
    # own same-bar settlement timing (module docstring: the KIND differs, ACK vs FULL_FILL, but
    # both are honestly outcome_digest=None).
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
    assert backtest_digests[0] is not None
    assert tick_result.outcome_digest is not None

    # -- exactly one tick + one re-injected egress result on each side ------------------------
    assert len(backtest_digests) == 2
    assert len(engine_digests) == 2

    # -- the parity claim itself: byte-identical outcome_digest sequences ---------------------
    assert tick_result.outcome_digest == backtest_digests[0]
    assert backtest_digests == engine_digests
