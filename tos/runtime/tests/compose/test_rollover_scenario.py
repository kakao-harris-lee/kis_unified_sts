"""Futures rollover + non-trade LIFECYCLE latch compose e2e (TOS Phase 5 W5 plan §2 decision 7;
lane f4, Phase B).

Drives two facts through a FULL composed runtime:

1. **Rollover = calendar phase + kernel membership, never a runtime predicate** (decision 7).
   Once the calendar's own ``futures_expiry`` rule says the instant is past expiry, the
   ``effective_phase_at`` fold (:mod:`tos_runtime.calendar.phase`) supplies the rule's
   ``expired_phase`` token (``"EXPIRED"``) — session_facts observes it, step 3's
   ``VenueConstraintStage`` folds it into the kernel's own ``session_phase_admits``, and the
   kernel refuses membership (``EXPIRED`` is not in the venue policy's admitting set for any
   action) — INADMISSIBLE, zero sends. The runtime never asserts "expired therefore refuse"
   itself; it only supplies the token the kernel already knows how to reject.
2. **The LIFECYCLE non-trade observation latches new risk through the sanctioned door**
   (:meth:`~tos_runtime.compose._types.ComposedRuntime.observe_nontrade`), records an
   ``INCIDENT_CANDIDATE`` row, and — being a runtime-wide, first-call-wins latch — is never
   silently overwritten by a second restrictive observation.
3. **``observe_nontrade``'s engine path shares the SAME real venue-admissibility provider the
   dry-run processor uses** (TOS runtime operations wiring plan §2 decision 3 follow-up —
   scenario (g) below) — proven via the disposition RANK it lands at (rank 3
   ``NONTRADE_TRAPPED`` vs rank 4 ``NONTRADE_BLOCK_NEW_RISK``), since this compose root's
   genuinely-absent ``time_freshness`` source keeps full ``NONTRADE_ADMISSIBLE`` (rank 5)
   unreachable through either lane regardless of admissibility (empirically confirmed, not
   assumed — see scenario (g)'s own module-level comment).

Hermetic (D1.4): real sqlite files under ``tmp_path``, reusing this suite's own
``_compose``/``_reach_trusted``/``write_approval_file``/``_drive_crossing_tick`` helpers
(``test_compose_root.py``/``test_session_wiring.py``) rather than re-deriving compose wiring a
third time.

**No cross-package fixture import.** ``tests/nontrade/fixtures/synthetic_observations.py``
already has a ``futures_lifecycle_expiry()`` builder this file's scenarios closely mirror — but
the tos-firewall AST gate enforces "each package builds its own fixtures" over test files too
(``tos/runtime/tests`` is one scan tree), so :func:`_futures_lifecycle_expiry` /
:func:`_second_restrictive_observation` below are this suite's OWN small, local re-derivations,
never an import of that sibling test package's module.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.nontrade import (
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventClass,
    SplitTransformationKind,
    SplitTransformationSpec,
    TransitionEnvelope,
)
from tos_runtime.calendar import phase as calendar_phase
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.engine.driver import EngineDriverInvariantError
from tos_runtime.nontrade import NonTradeObservation

from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_session_wiring import _drive_crossing_tick

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The second Thursday of September 2026 (a real quarterly expiry month, [3, 6, 9, 12]) —
#: verified directly: `calendar.Calendar().itermonthdates(2026, 9)` filtered to Thursdays gives
#: [09-03, 09-10, 09-17, 09-24]; the second is 2026-09-10.
_EXPIRY_DATE_ISO = "2026-09-10"

#: 2026-09-11 10:00 KST (Friday, the day AFTER expiry) — `today > expiry_date` unconditionally,
#: so `maturity_at(...).expired is True` regardless of the session window's own end time.
_AFTER_EXPIRY_UNIX_MS = 1_789_088_400_000

#: 2026-09-09 10:00 KST (Wednesday, the day BEFORE expiry, inside the regular 09:00-15:45
#: window) — `today < expiry_date`, so `expired is False` and the regular phase admits.
_DAY_BEFORE_EXPIRY_UNIX_MS = 1_788_915_600_000


def _write_futures_calendar(
    config_dir: Path, *, calendar_version: str = "cal-compose-0"
) -> None:
    """Override the shared conftest.py calendar with a REALISTIC narrow window (09:00-15:45
    weekdays) PLUS a real quarterly futures-expiry rule for ``fx.INSTRUMENT_CLASS`` — the shared
    fixture's own ``futures_expiry: {}`` carries no rule at all, so it cannot exercise rollover.
    """
    (config_dir / "calendar.yaml").write_text(
        yaml.safe_dump(
            {
                "calendar_version": calendar_version,
                "tz_id": "Asia/Seoul",
                "holidays": [],
                "sessions": {
                    fx.INSTRUMENT_CLASS: [
                        {
                            "phase": "CONTINUOUS",
                            "start": "09:00",
                            "end": "15:45",
                            "days": ["MON", "TUE", "WED", "THU", "FRI"],
                            "crosses_midnight": False,
                        }
                    ]
                },
                "closed_phase": "CLOSED",
                "futures_expiry": {
                    fx.INSTRUMENT_CLASS: {
                        "weekday": "THU",
                        "ordinal": 2,
                        "months": [3, 6, 9, 12],
                        "expired_phase": "EXPIRED",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_nontrade_config(config_dir: Path) -> None:
    """A real (non-``null``) ``nontrade.yaml`` — ``CORPORATE_ACTION`` only, mirroring
    ``tests/nontrade/fixtures/synthetic_observations.py``'s own
    ``REQUIRED_LEGS_BY_CLASS`` choice; ``LIFECYCLE`` is deliberately left unconfigured (this
    file's own scenarios only observe ``LIFECYCLE``/``CORPORATE_ACTION`` events, and the
    LIFECYCLE fixture is documented to exercise the "no entry -> unevaluated" envelope path
    regardless of what this config says)."""
    (config_dir / "nontrade.yaml").write_text(
        yaml.safe_dump(
            {
                "required_legs_by_class": {
                    "CORPORATE_ACTION": ["PRE_EVENT_POSITION_AND_ORDER"],
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _futures_lifecycle_expiry() -> NonTradeObservation:
    """Local mirror of ``tests/nontrade/fixtures/synthetic_observations.py``'s own
    ``futures_lifecycle_expiry()`` (module docstring — no cross-package fixture import).
    Deliberately minimal: no envelope, no transformation, no correction — the "rollover
    observation" plan §2.7 uses."""
    return NonTradeObservation(
        observation_id="futures-expiry-202609-mini",
        event_class=NonTradeEventClass.LIFECYCLE,
        source_label="synthetic-fixture",
        event_subtype="EXPIRY",
        announcement_time="2026-06-12T00:00:00",
        effective_time="2026-09-11T15:45:00",
        settlement_time="2026-09-14T00:00:00",
        old_instrument_identity="KRX-FUT:202609-MINI",
        new_instrument_identity="KRX-FUT:202609-MINI",
        identity_transition_final=True,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX-FUT:202609-MINI"}),
    )


def _second_restrictive_observation() -> NonTradeObservation:
    """A second, DIFFERENT non-trade observation for the first-call-wins proof (scenario (c)).

    Any distinct ``CORPORATE_ACTION`` event is enough here: with the venue INADMISSIBLE at this
    scenario's own instant (the calendar is past expiry), ``nontrade_disposition``'s rank 3 —
    "the admissibility token is neither ADMISSIBLE nor RESTRICTED_PROTECTIVE_ONLY —
    UNCONDITIONALLY -> NONTRADE_TRAPPED" — dominates regardless of this observation's own
    envelope/transformation content, so a full split-mutation replica is unnecessary; only a
    genuinely different ``observation_id`` matters for the identity proof below.
    """
    return NonTradeObservation(
        observation_id="cash-dividend-005930-2026Q3-second",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_label="synthetic-fixture",
        event_subtype="CASH_DIVIDEND",
        old_instrument_identity="KRX:005930",
        new_instrument_identity="KRX:005930",
        identity_transition_final=True,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX:005930"}),
    )


def _admissible_corporate_action() -> NonTradeObservation:
    """A "happy path" ``CORPORATE_ACTION`` observation — every rank-5 conjunct THIS runtime CAN
    positively prove, mirroring ``tests/nontrade/fixtures/synthetic_observations.py
    ::stock_split_forward`` (module docstring — no cross-package fixture import, this is a
    local re-derivation). Its envelope carries only ``PRE_EVENT_POSITION_AND_ORDER`` — the ONE
    leg ``_write_nontrade_config``'s own ``nontrade.yaml`` requires for ``CORPORATE_ACTION`` in
    this suite. At an ADMISSIBLE-venue instant this lands at ``NONTRADE_BLOCK_NEW_RISK``, not
    ``NONTRADE_ADMISSIBLE`` — this compose root's genuinely-absent ``time_freshness`` source
    (module docstring section (g)) keeps rank 5 unreachable regardless of admissibility.
    """
    split = SplitTransformationSpec(
        kind=SplitTransformationKind.FORWARD_SPLIT,
        pre_quantity=Decimal("100"),
        post_quantity=Decimal("200"),
        pre_basis=Decimal("20"),
        post_basis=Decimal("10"),
        unit_spec="shares",
        rounding_rule="round-down",
        fractional_residual=Decimal("0"),
        cash_in_lieu=Decimal("0"),
    )
    envelope = TransitionEnvelope(
        present_legs=frozenset(
            {CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER}
        ),
        pre_event_exposure=Decimal("2000"),
        post_event_credible_exposure=Decimal("2000"),
    )
    return NonTradeObservation(
        observation_id="stock-split-005930-2026Q3-admissible",
        event_class=NonTradeEventClass.CORPORATE_ACTION,
        source_label="synthetic-fixture",
        event_subtype="FORWARD_SPLIT",
        old_instrument_identity="KRX:005930",
        new_instrument_identity="KRX:005930",
        identity_transition_final=True,
        transition_envelope=envelope,
        split_spec=split,
        event_is_material=True,
        change_triggers=frozenset({"instrument:KRX:005930"}),
        earliest_credible_boundary="2026-09-08T00:00:00",
        latest_completion_boundary="2026-09-10T00:00:00",
        source_disagreement_bounded=True,
        field_confidences=frozenset({"CORROBORATED"}),
        injected_worst_intermediate_risk=Decimal("5"),
        injected_credible_space_bounded=True,
        injected_union_capacity_known=True,
    )


def _incident_candidate_count(runtime) -> int:
    return runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'INCIDENT_CANDIDATE'"
    ).fetchone()[0]


def _latest_session_facts_observed_payload(runtime) -> dict:
    row = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SESSION_FACTS_OBSERVED' "
        "ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "expected at least one SESSION_FACTS_OBSERVED row"
    return json.loads(row[0])["payload"]


# ============================================================================
# (a) Past expiry -- EXPIRED phase -> step 3 INADMISSIBLE -> send 0
# ============================================================================


def test_past_expiry_instant_is_expired_phase_inadmissible_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts is not None
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "EXPIRED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"
    assert runtime.transport.requests == ()

    payload = _latest_session_facts_observed_payload(runtime)
    assert payload["phase"] == "EXPIRED"
    assert payload["expired"] is True

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (b) One day before expiry -- regular phase -> step 3 admits, reaches transport
# ============================================================================


def test_day_before_expiry_is_regular_phase_admitted_and_reaches_transport(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_DAY_BEFORE_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CONTINUOUS"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "ADMIT"
    assert len(runtime.transport.requests) == 1

    payload = _latest_session_facts_observed_payload(runtime)
    assert payload["phase"] == "CONTINUOUS"
    assert payload["expired"] is False

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (c) LIFECYCLE observation, routed through the ENGINE's own CORPORATE_ACTION handler
#     (TOS runtime operations wiring plan §2 decision 3), latches new risk, records
#     INCIDENT_CANDIDATE once per restrictive call, first-call-wins on the latch itself,
#     and a subsequent tick is genuinely refused.
# ============================================================================


def test_lifecycle_expiry_observation_latches_new_risk_first_call_wins(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.nontrade is not None
    assert runtime.inbox.new_risk_halt() is None

    obs = _futures_lifecycle_expiry()
    outcome = runtime.observe_nontrade(obs)
    assert outcome.restrictive is True
    assert outcome.queued is False
    assert outcome.latch_reason is not None
    # evidence_seq now names the ENGINE's own EVENT_CONSUMED receipt (the driver's
    # last_nontrade_evidence_seq()), never a dry-run NONTRADE_DISPOSITION seq — the dry-run
    # processor (still wired at runtime.nontrade for the nontrade-eval CLI) records nothing.
    assert outcome.evidence_seq == runtime.driver.last_nontrade_evidence_seq()
    assert outcome.evidence_seq is not None

    halt = runtime.inbox.new_risk_halt()
    assert halt is not None
    assert halt["reason"] == outcome.latch_reason
    # The latched event_id is now the ENGINE's own content-addressed event identity (the
    # stamped EngineEvent's), never obs.observation_id directly — the kernel disposition still
    # authors the SAME reason/disposition string either way; only the identity coordinate
    # changed shape (this is the exact rerouting this scenario now proves).
    assert halt["event_id"] is not None
    assert _incident_candidate_count(runtime) == 1

    # a second, DIFFERENT restrictive observation must NOT overwrite the first latch reason
    # (record_new_risk_halt is a first-call-wins singleton, engine/inbox.py:574). Both fixtures
    # land at NONTRADE_TRAPPED here — rank 3 ("the admissibility token is neither ADMISSIBLE nor
    # RESTRICTED_PROTECTIVE_ONLY -- UNCONDITIONALLY -> NONTRADE_TRAPPED", tos.nontrade.predicates
    # .nontrade_disposition) dominates for BOTH: observe_nontrade's engine path now shares the
    # SAME real, honest venue-admissibility provider the dry-run processor uses
    # (ComposedRuntime.nontrade_admissibility_provider), and the venue is EXPIRED (hence
    # INADMISSIBLE) at this instant for every corporate action it judges here — "neither
    # ADMISSIBLE nor RESTRICTED_PROTECTIVE_ONLY", so the same disposition is expected, not a
    # test bug. The proof of first-call-wins is therefore on IDENTITY (the exact halt row is
    # untouched), not on the dispositions differing — an INCIDENT_CANDIDATE row is still
    # appended for the second call (every restrictive disposition is evidenced independently).
    second_obs = _second_restrictive_observation()
    assert second_obs.observation_id != obs.observation_id
    second_outcome = runtime.observe_nontrade(second_obs)
    assert second_outcome.restrictive is True
    halt_after_second = runtime.inbox.new_risk_halt()
    assert (
        halt_after_second == halt
    ), "first-call-wins: the second call must not change the row"
    assert _incident_candidate_count(runtime) == 2

    # a subsequent DECISION_TICK is genuinely refused by the durable latch (engine/driver.py's
    # own new-risk-halt refusal path — never a runtime re-derivation of the refusal).
    refused_tick = runtime.driver.enqueue_and_run(fx.crossing_event(seq=99))
    assert repr(halt["event_id"]) in (refused_tick.detail or "")
    assert refused_tick.outcome_digest is None

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_m3_mutation_an_unbound_latch_refuses_loudly_rather_than_silently_skipping(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation lens M3 ("driver hook ignores restrictive → red"), at the compose e2e level —
    complements ``tests/engine/test_driver_nontrade_latch.py``'s own unit-level M3 proof.
    Detaching the bound latch AFTER a normal compose (mirrors ``bind_nontrade_latch(None)``
    never being reachable through any real wiring path — this monkeypatches the driver's own
    private attribute directly, the only way to reach the "never bound" state post-compose)
    must make the very next restrictive ``observe_nontrade`` call raise
    ``EngineDriverInvariantError`` rather than silently completing with no halt."""
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.driver is not None
    runtime.driver._nontrade_latch = (
        None  # noqa: SLF001 -- mutation lens, not production code
    )

    obs = _futures_lifecycle_expiry()
    with pytest.raises(EngineDriverInvariantError):
        runtime.observe_nontrade(obs)

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (d) Mutation lens M5: supply the REGULAR phase instead of EXPIRED past the
#     expiry instant -- (a)'s send-0 pin must go red under this mutation.
# ============================================================================


def test_m5_mutation_regular_phase_past_expiry_would_send_and_pin_a_red(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves scenario (a) actually depends on the ``EXPIRED`` token reaching step 3, not on
    some OTHER reason the send happened to be zero. Monkeypatches
    :func:`tos_runtime.calendar.owner.effective_phase_at` (the exact seam
    :mod:`tos_runtime.calendar.owner` imports and calls) to always report the regular,
    non-expired phase — mutation M5, "``EXPIRED`` 대신 정규 위상 공급". Under that mutation, the
    SAME instant/calendar/config that produces zero sends in scenario (a) now sends — so this
    test asserts the RED scenario (a) would show, proving the un-mutated fixture (a) is a real
    pin, not a vacuous one.
    """
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)

    real_effective_phase_at = calendar_phase.effective_phase_at

    def _mutated_never_expired(instant_unix_ms: int, instrument_class: str, cfg):
        """M5: ignore maturity entirely and always return the ordinary session phase."""
        return calendar_phase.session_phase_at(instant_unix_ms, instrument_class, cfg)

    # `tos_runtime.calendar.owner` imports `effective_phase_at` by name (`from
    # tos_runtime.calendar.phase import effective_phase_at, maturity_at`), so the owner module's
    # own bound name, not the source module's, is what a real call site reads.
    monkeypatch.setattr(
        "tos_runtime.calendar.owner.effective_phase_at", _mutated_never_expired
    )

    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    # Under the mutation, phase_for_step3 no longer reports EXPIRED at the same instant that
    # scenario (a) uses -- the exact assertion (a) makes would now be false.
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) != "EXPIRED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handed_off is True
    assert len(runtime.transport.requests) == 1, (
        "M5 mutation check: with the phase mutated to never report EXPIRED, the SAME instant "
        "that scenario (a) drives to zero sends now sends once -- proving (a)'s zero-send "
        "assertion is a genuine pin on the EXPIRED token, not an artifact of something else"
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()
    assert real_effective_phase_at is calendar_phase.effective_phase_at, (
        "monkeypatch must not leak past this test (pytest's own fixture teardown handles "
        "this; asserted here as an explicit, positive confirmation)"
    )


# ============================================================================
# (e) Mutation lens M7/M8: bypass the sanctioned door -- calling the DRY-RUN evaluator
#     directly (never through ComposedRuntime.observe_nontrade) must NOT latch anything,
#     proving scenario (c)'s halt assertions genuinely depend on observe_nontrade's own
#     engine-routed wiring, not on the (now evidence-free, structurally latch-incapable)
#     processor module alone. M8 ("observe_nontrade reintroduces the out-of-engine
#     processor latch") is pinned structurally instead of behaviorally here: this
#     package's own grep/AST pins (tests/nontrade/test_processor.py's
#     test_no_forbidden_capacity_or_engine_imports_under_nontrade /
#     test_no_capacity_write_receiver_call_shapes_under_nontrade) already prove
#     tos_runtime.nontrade never imports tos_runtime.engine and never calls a capacity/
#     engine receiver shape at all -- NonTradeEventProcessor.evaluate() cannot reach
#     record_new_risk_halt even if a future edit tried to reintroduce the call, because the
#     import itself is refused.
# ============================================================================


def test_m7_mutation_bypassing_observe_nontrade_never_latches(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """M7: "nontrade restrictive 에서 래치 생략 → red". Calls
    :meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.evaluate` DIRECTLY —
    ``runtime.nontrade.evaluate(obs)``, bypassing :meth:`ComposedRuntime.observe_nontrade`
    entirely — and asserts the disposition is STILL genuinely restrictive (the kernel predicate
    itself is unaffected) while the durable new-risk halt latch stays completely untouched. This
    is the exact gap :meth:`observe_nontrade` exists to close; a caller that reached for the
    dry-run evaluator directly instead of the sanctioned door would silently lose the latch
    scenario (c) proves exists.
    """
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.nontrade is not None
    assert runtime.inbox.new_risk_halt() is None

    obs = _futures_lifecycle_expiry()
    bypassed_outcome = runtime.nontrade.evaluate(obs)
    assert bypassed_outcome.restrictive is True, (
        "the kernel disposition itself must still be restrictive -- what M7 removes is the "
        "LATCH call, never the processor's own honest verdict"
    )
    assert bypassed_outcome.evidence_seq is None, (
        "the dry-run evaluator records zero evidence (TOS runtime operations wiring plan §2 "
        "decision 3) -- there is no evidence_seq to report"
    )
    assert runtime.inbox.new_risk_halt() is None, (
        "M7 mutation check: calling the evaluator directly (bypassing "
        "ComposedRuntime.observe_nontrade) must leave the new-risk halt latch completely "
        "untouched -- if this were non-None here, scenario (c)'s own latch assertions would be "
        "proving nothing about observe_nontrade specifically"
    )
    assert _incident_candidate_count(runtime) == 0, (
        "the INCIDENT_CANDIDATE row is observe_nontrade's own act too -- bypassing it must "
        "leave zero candidate rows, not just zero halt rows"
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (f) Recovery barrier held: observe_nontrade queues (never judges), and the queued
#     event is drained + judged/latched once a real driver exists again.
# ============================================================================


def _queued_until_recovery_count(runtime) -> int:
    return runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = 'NONTRADE_QUEUED_UNTIL_RECOVERY'"
    ).fetchone()[0]


def test_barrier_held_queues_the_observation_then_drains_and_latches_once_recovered(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """No compose e2e fixture in this suite drives a genuinely-HELD recovery barrier (every
    existing scenario reaches TRUSTED/READY) — this test simulates the held state the same way
    scenario (a)'s M3 sibling simulates an unbound latch: composing normally, then detaching
    ``runtime.driver`` to ``None`` (the exact post-``_recovery_wiring`` shape a real HOLD
    verdict leaves — ``compose/_types.py``'s own :attr:`~tos_runtime.compose._types
    .ComposedRuntime.driver` docstring), never re-deriving the barrier's own judgement.
    """
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_AFTER_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    real_driver = runtime.driver
    assert real_driver is not None
    runtime.driver = None
    assert runtime.inbox.new_risk_halt() is None
    inbox_count_before = runtime.inbox.count

    obs = _futures_lifecycle_expiry()
    outcome = runtime.observe_nontrade(obs)
    assert outcome.queued is True
    assert outcome.disposition is None
    assert outcome.restrictive is False
    assert outcome.latch_reason is None
    assert outcome.evidence_seq is None
    assert _queued_until_recovery_count(runtime) == 1
    assert runtime.inbox.count == inbox_count_before + 1
    assert (
        runtime.inbox.new_risk_halt() is None
    ), "queued (not judged) must never latch -- nothing has evaluated the disposition yet"

    # "recovery": a real driver exists again and drains the durably-queued event -- the SAME
    # discipline every other crash-window-recovered row already gets (module docstring of
    # tos_runtime.engine.driver's own _process_next).
    runtime.driver = real_driver
    real_driver.run_until_idle()
    halt = runtime.inbox.new_risk_halt()
    assert halt is not None, (
        "the queued LIFECYCLE observation is restrictive (rank 3 -- the venue is EXPIRED, "
        "hence not ADMISSIBLE, at this instant) -- draining it must judge and latch it, "
        "exactly like observe_nontrade's own driver-wired path does"
    )
    assert _incident_candidate_count(runtime) == 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (g) TOS runtime operations wiring plan §2 decision 3 follow-up: observe_nontrade's
#     engine path shares the SAME real venue-admissibility provider the dry-run
#     processor uses. **Ceiling fact, empirically confirmed, not assumed:** this compose
#     root's time_freshness_provider is genuinely None (no real source exists anywhere in
#     this runtime -- module docstring of _session_wiring.py), so
#     effective_window_blocks_new_risk (kernel predicates.py:873) can NEVER return True here
#     (it requires time_freshness == "FRESH" exactly) -- rank 5 (NONTRADE_ADMISSIBLE) is
#     therefore UNREACHABLE through either lane in this runtime regardless of admissibility,
#     and every corporate action processed here is restrictive and latches. The real,
#     observable effect of a genuine admissibility source is the RANK the disposition lands
#     at: rank 3 (NONTRADE_TRAPPED, admissibility unconditionally not ADMISSIBLE/
#     RESTRICTED_PROTECTIVE_ONLY -- scenario (c) above, at the EXPIRED instant) versus rank 4
#     (NONTRADE_BLOCK_NEW_RISK, every OTHER conjunct positively proven except the window --
#     this scenario, at a CONTINUOUS/admissible instant). Both lanes must agree on this rank,
#     and a mutation forcing the shared provider back to a constant None must collapse the
#     admissible-instant case back to rank 3.
# ============================================================================


def test_admissible_venue_instant_reaches_block_new_risk_not_trapped_through_both_lanes(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """At a regular (non-expired, admissible-venue) instant, with a "happy path" observation,
    BOTH the dry-run evaluator and observe_nontrade's engine path must land at rank 4
    (``NONTRADE_BLOCK_NEW_RISK``) rather than rank 3 (``NONTRADE_TRAPPED``) -- the equivalence
    the follow-up restores: ``nontrade_admissibility_provider`` is the SAME shared instance
    both lanes read (``build_nontrade_admissibility_provider``'s own docstring), resolved
    against this observation's own route identity exactly like the dry-run processor's
    ``_resolve_admissibility`` does. Full ``NONTRADE_ADMISSIBLE`` (rank 5) is unreachable in
    this compose root regardless (module docstring section (g)) -- both dispositions ARE
    restrictive and DO latch; the pin is on WHICH restrictive rank, not on latching at all.
    """
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_DAY_BEFORE_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CONTINUOUS"
    assert runtime.nontrade is not None
    assert runtime.nontrade_admissibility_provider is not None
    assert runtime.inbox.new_risk_halt() is None

    obs = _admissible_corporate_action()

    dry_run_outcome = runtime.nontrade.evaluate(obs)
    assert dry_run_outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    assert (
        dry_run_outcome.predicate_results["effective_window_blocks_new_risk"] is False
    ), (
        "confirms the ceiling fact this module docstring states: no time_freshness source "
        "means the window conjunct can never positively establish, so rank 5 is unreachable "
        "here regardless of admissibility"
    )

    engine_outcome = runtime.observe_nontrade(obs)
    assert engine_outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK, (
        "the engine path must land at the SAME rank as the dry-run evaluator now that both "
        "share the same real admissibility provider -- NONTRADE_TRAPPED here would mean the "
        "engine path is still seeing admissibility=None"
    )
    assert engine_outcome.restrictive is True
    assert engine_outcome.queued is False
    assert engine_outcome.latch_reason == "NONTRADE_NONTRADE_BLOCK_NEW_RISK"

    halt = runtime.inbox.new_risk_halt()
    assert halt is not None
    assert halt["reason"] == "NONTRADE_NONTRADE_BLOCK_NEW_RISK"
    assert _incident_candidate_count(runtime) == 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_mutation_forcing_the_admissibility_provider_to_none_flips_the_rank_to_trapped(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation lens: force ``runtime.nontrade_admissibility_provider`` to always return
    ``None`` (the exact regression the follow-up fixes) -- the SAME observation/instant the
    prior test pins at rank 4 (``NONTRADE_BLOCK_NEW_RISK``) must collapse back to rank 3
    (``NONTRADE_TRAPPED``, admissibility unconditionally not ADMISSIBLE) through the engine
    path, proving that test's rank pin genuinely depends on the shared provider being real,
    not an artifact of something else."""
    _write_futures_calendar(config_dir)
    _write_nontrade_config(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_DAY_BEFORE_EXPIRY_UNIX_MS),
    )
    _reach_trusted(runtime)
    runtime.nontrade_admissibility_provider = lambda _route_key: None

    obs = _admissible_corporate_action()
    engine_outcome = runtime.observe_nontrade(obs)
    assert engine_outcome.disposition is NonTradeDisposition.NONTRADE_TRAPPED, (
        "M-follow-up: forcing the shared provider to None must flip the prior test's "
        "NONTRADE_BLOCK_NEW_RISK pin to NONTRADE_TRAPPED -- proving it is not vacuously true"
    )
    assert engine_outcome.restrictive is True
    assert runtime.inbox.new_risk_halt() is not None

    runtime.rcl_log.close()
    runtime.evidence_store.close()
