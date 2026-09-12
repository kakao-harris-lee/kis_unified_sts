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
from pathlib import Path

import pytest
import yaml
from tos.nontrade import NonTradeEventClass
from tos_runtime.calendar import phase as calendar_phase
from tos_runtime.calendar.ports import FixedWallClockReference
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
# (c) LIFECYCLE observation latches new risk, records INCIDENT_CANDIDATE once
#     per restrictive call, first-call-wins on the latch itself, and a
#     subsequent tick is genuinely refused.
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
    assert outcome.latch_reason is not None

    halt = runtime.inbox.new_risk_halt()
    assert halt is not None
    assert halt["reason"] == outcome.latch_reason
    assert halt["event_id"] == obs.observation_id
    assert _incident_candidate_count(runtime) == 1

    # a second, DIFFERENT restrictive observation must NOT overwrite the first latch reason
    # (record_new_risk_halt is a first-call-wins singleton, engine/inbox.py:574). Both fixtures
    # land at NONTRADE_TRAPPED here — rank 3 ("the admissibility token is neither ADMISSIBLE nor
    # RESTRICTED_PROTECTIVE_ONLY -- UNCONDITIONALLY -> NONTRADE_TRAPPED", tos.nontrade.predicates
    # .nontrade_disposition) dominates for BOTH once the honestly-wired venue_admissibility_
    # provider reports the venue is EXPIRED/INADMISSIBLE at this instant, so the same-string
    # disposition is expected, not a test bug. The proof of first-call-wins is therefore on
    # IDENTITY (the exact halt row, including `event_id`), not on the dispositions differing —
    # an INCIDENT_CANDIDATE row is still appended for the second call (every restrictive
    # disposition is evidenced independently), but the underlying halt row is untouched.
    second_obs = _second_restrictive_observation()
    assert second_obs.observation_id != obs.observation_id
    second_outcome = runtime.observe_nontrade(second_obs)
    assert second_outcome.restrictive is True
    halt_after_second = runtime.inbox.new_risk_halt()
    assert (
        halt_after_second == halt
    ), "first-call-wins: the second call must not change the row"
    assert (
        halt_after_second["event_id"] == obs.observation_id
    ), "the latched event_id must still be the FIRST observation's, never the second's"
    assert _incident_candidate_count(runtime) == 2

    # a subsequent DECISION_TICK is genuinely refused by the durable latch (engine/driver.py's
    # own new-risk-halt refusal path — never a runtime re-derivation of the refusal).
    refused_tick = runtime.driver.enqueue_and_run(fx.crossing_event(seq=99))
    assert repr(obs.observation_id) in (refused_tick.detail or "")
    assert refused_tick.outcome_digest is None

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
# (e) Mutation lens M7: bypass the sanctioned door -- calling the processor
#     directly (never through ComposedRuntime.observe_nontrade) must NOT
#     latch anything, proving scenario (c)'s halt assertions genuinely depend
#     on observe_nontrade's own wiring, not on the processor alone.
# ============================================================================


def test_m7_mutation_bypassing_observe_nontrade_never_latches(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """M7: "nontrade restrictive 에서 래치 생략 → red". Calls
    :meth:`~tos_runtime.nontrade.processor.NonTradeEventProcessor.process` DIRECTLY —
    ``runtime.nontrade.process(obs)``, bypassing :meth:`ComposedRuntime.observe_nontrade`
    entirely — and asserts the disposition is STILL genuinely restrictive (the kernel predicate
    itself is unaffected) while the durable new-risk halt latch stays completely untouched. This
    is the exact gap :meth:`observe_nontrade` exists to close; a caller that reached for the
    processor directly instead of the sanctioned door would silently lose the latch scenario
    (c) proves exists.
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
    bypassed_outcome = runtime.nontrade.process(obs)
    assert bypassed_outcome.restrictive is True, (
        "the kernel disposition itself must still be restrictive -- what M7 removes is the "
        "LATCH call, never the processor's own honest verdict"
    )
    assert runtime.inbox.new_risk_halt() is None, (
        "M7 mutation check: calling the processor directly (bypassing "
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
