"""Compose end-to-end tests for the TOS tick-source wave
(``docs/plans/2026-09-16-tos-tick-source-plan.md`` §5, lane D).

Proves the chain end to end against the **real** composed runtime — no hand-built
``crossing_event()`` (that fixture stays for every OTHER compose e2e test; this suite is what
finally replaces it for the tick-production half of the chain): a real observation journal line
is polled by :class:`~tos_runtime.marketfeed.scheduler.TickScheduler`, issued as a real
:class:`~tos.capsule.CriticalInputSnapshot`/:class:`~tos.capsule.DecisionContextCapsule` pair
under a governed Critical Input Policy, durably stored
(:class:`~tos_runtime.marketfeed.store.SqliteSnapshotStore`), resolved through the REAL kernel
:class:`~tos.marketfeed.MarketFeedContextResolver`, and driven through the REAL
:class:`~tos_runtime.engine.driver.EngineDriver`.

Hermetic (D1.4): every file lives under ``tmp_path``; no network, no ambient env — enforced by
``conftest.py``'s own autouse guards (``pytestmark`` below).
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.egressgw.construction import admitted_price_from_view
from tos.time import SessionContext
from tos_runtime.calendar.ports import AbsentWallClockReference
from tos_runtime.marketfeed.policy import CriticalInputPolicyConfigError
from tos_runtime.marketfeed.ports import RawObservation, TickOutcome
from tos_runtime.marketfeed.scheduler import MultiInstrumentRefused

from ..recovery.test_drill import _mark_handling_started
from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Generous on purpose: ``SnapshotIssuer``'s freshness check compares against
#: ``TrustworthyTimeService.wall_clock_now()`` — the REAL system clock (``LocalSystemClockReader``
#: via ``boot.infra``), never the injected ``wall_clock`` fixture (that one only feeds
#: ``SessionFactsOwner`` — ``_compose()``'s own docstring). ``_as_of_ms()`` below is therefore
#: computed against the real clock too, with enough headroom here to absorb a slow CI boot.
_MAX_AGE_MS = 600_000
_POLL_INTERVAL_MS = 1_000
_SNAPSHOT_AGE_BOUND = 20
_INTERVAL_WIDTH = 10
_DIRECTION = "LONG"
_QUANTITY_BASIS = "RISK"
_UNIT = "contract"


def _as_of_ms() -> int:
    """A real-clock timestamp just before "now" — see ``_MAX_AGE_MS``'s own docstring on why
    this is real-clock-relative rather than ``fx.DEFAULT_WALL_CLOCK_UNIX_MS``-relative.
    """
    return int(time.time() * 1000) - 100


# ----------------------------------------------------------------------------
# config-file writers
# ----------------------------------------------------------------------------


def _cip_fields() -> list[dict[str, Any]]:
    """The three fields the band-reversion strategy needs (``close``/``lower_band``/
    ``upper_band``, ``_fixtures.py``'s own crossing constants) — one shared shape so an
    admitted observation's ``mapping`` slots agree (``snapshot.py``'s own "Correction 2").
    """
    return [
        {
            "field_key": key,
            "unit": "KRW",
            "scale": "minor",
            "multiplier": "1",
            "sign": "POSITIVE",
            "max_age_ms": _MAX_AGE_MS,
        }
        for key in ("close", "lower_band", "upper_band")
    ]


def _write_critical_input_policy(config_dir: Path) -> None:
    (config_dir / "critical_input_policy.yaml").write_text(
        yaml.safe_dump(
            {
                "policy_id": "cip-tick-source-e2e",
                "policy_version": "v1",
                "policy_generation": 1,
                "issuer_principal_id": "iss-tick-source-e2e",
                "environment": "non-live-test",
                "decision_class": fx.DECISION_CLASS,
                "intended_use": "entry-decision",
                "fields": _cip_fields(),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_marketfeed_config(
    config_dir: Path, *, journal_path: Path, instruments: tuple[str, ...]
) -> None:
    (config_dir / "marketfeed.yaml").write_text(
        yaml.safe_dump(
            {
                "instruments": list(instruments),
                "instrument_class": fx.INSTRUMENT_CLASS,
                "account": fx.ACCOUNT,
                "direction": _DIRECTION,
                "quantity_basis": _QUANTITY_BASIS,
                "unit": _UNIT,
                # W2 lane (2026-09-17) — intake_kind is now required and never defaults
                # (_marketfeed_wiring.py module docstring); this suite exercises the
                # journal-backed intake exclusively, so it is pinned explicitly here.
                "intake_kind": "journal",
                "journal_path": str(journal_path),
                "poll_interval_ms": _POLL_INTERVAL_MS,
                "time_evaluate_closed_interval_ms": 60_000,
                "snapshot_age_bound": _SNAPSHOT_AGE_BOUND,
                "interval_width": _INTERVAL_WIDTH,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _observation_line(
    *,
    raw_event_id: str,
    as_of_ms: int,
    close: int = fx.CROSSING_CLOSE,
    lower_band: int = fx.LOWER_BAND,
    upper_band: int = fx.UPPER_BAND,
) -> str:
    return json.dumps(
        {
            "raw_event_id": raw_event_id,
            "instrument": fx.INSTRUMENT,
            "as_of_ms": as_of_ms,
            "fields": {
                "close": close,
                "lower_band": lower_band,
                "upper_band": upper_band,
            },
            "source_id": "compose-e2e-journal",
            "received_ms": as_of_ms,
        }
    )


def _write_journal(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


# ----------------------------------------------------------------------------
# (1) + (3): a real tick, and the (a') price claim
# ----------------------------------------------------------------------------


def test_tick_once_ticks_with_the_real_resolver_and_the_admitted_price_travels_with_its_digest(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(
        journal_path, [_observation_line(raw_event_id="raw-1", as_of_ms=_as_of_ms())]
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    result = runtime.marketfeed.tick_once()

    assert result.outcome is TickOutcome.TICKED
    assert result.queued_until_recovery is False
    assert result.value_view is not None
    assert result.value_view.values  # not an explicit-empty view

    # (a') the price claim: OrderConstructionStage._price_for (egressgw/construction.py:986-996)
    # prefers the admitted value surface over the injected `price` literal whenever
    # `price_field_key` is set (fx.construction_config() already sets it to "close") AND the
    # tick carries a view — both hold here, so this is the EXACT function `_price_for` calls
    # under the identical precondition; the value and its own ContextValue.payload_digest
    # travel together (admitted_price_from_view's own docstring).
    admitted_price = admitted_price_from_view(
        result.value_view, field_key=fx.PRICE_FIELD_KEY
    )
    assert admitted_price.value == Decimal(fx.CROSSING_CLOSE)
    assert admitted_price.value_payload_digest
    assert admitted_price.snapshot_digest

    # The construction stage itself — mutated in place by the SAME tick, driven through the
    # REAL EngineDriver inside tick_once() above — used this value, not the injected literal
    # PRICE (Decimal("4200")).
    assert runtime.construction_stage.construction is not None
    assert runtime.construction_stage.construction.derivation.price == Decimal(
        fx.CROSSING_CLOSE
    )

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ----------------------------------------------------------------------------
# (2): per-observation distinctness, independent of the journal's own filter
# ----------------------------------------------------------------------------


class _RepeatingIntake:
    """A deliberately LENIENT :class:`~tos_runtime.marketfeed.ports.ObservationIntake` double
    that ignores ``after_as_of_ms`` and always returns the SAME fixed observation.

    Exists to isolate :func:`~tos_runtime.marketfeed.scheduler.decide_tick`'s OWN distinctness
    obligation from the real journal's (``JsonLinesObservationJournal.poll`` already filters
    strictly-newer, so re-polling the SAME unchanged file never lets a stale as-of reach the
    scheduler at all — it would resolve to ``SKIPPED_NO_OBSERVATION``, not
    ``SKIPPED_NOT_NEWER``, and never exercise this obligation e2e). Every OTHER collaborator
    below is the real composed runtime's own live instance — only the intake is a double, and
    only because proving the scheduler's OWN obligation (``ports.py``'s
    ``DurableSnapshotStore.latest_as_of`` docstring: "the tick source reads this and refuses a
    not-newer observation instead of hoping") requires an intake that does NOT already do that
    filtering for it.
    """

    def __init__(self, observation: RawObservation) -> None:
        self._observation = observation

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> tuple[RawObservation, ...]:
        del instrument, after_as_of_ms  # deliberately ignored — see class docstring
        return (self._observation,)


def test_the_same_as_of_again_is_skipped_not_newer_with_zero_ticks(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    as_of_ms = _as_of_ms()
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(
        journal_path, [_observation_line(raw_event_id="raw-1", as_of_ms=as_of_ms)]
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None

    first = runtime.marketfeed.tick_once()
    assert first.outcome is TickOutcome.TICKED

    # Swap in the lenient double intake AFTER the first real tick landed, so the durable store
    # (unchanged) still reports the SAME latest_as_of the first tick just issued — everything
    # else (store, resolver, time projection, session owner, driver) stays the real one. The
    # SAME `as_of_ms` value as the first tick — a genuine resend, not merely a later one the
    # interval gate would also have caught.
    lenient_intake = _RepeatingIntake(
        RawObservation(
            raw_event_id="raw-1-resend",
            instrument=fx.INSTRUMENT,
            as_of_ms=as_of_ms,
            fields=(
                ("close", fx.CROSSING_CLOSE),
                ("lower_band", fx.LOWER_BAND),
                ("upper_band", fx.UPPER_BAND),
            ),
            source_id="compose-e2e-journal",
        )
    )
    runtime.marketfeed._intake = lenient_intake

    second = runtime.marketfeed.tick_once()
    assert second.outcome is TickOutcome.SKIPPED_NOT_NEWER
    assert second.queued_until_recovery is False
    assert second.value_view is None

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ----------------------------------------------------------------------------
# (7): session closed
# ----------------------------------------------------------------------------


def test_session_closed_skips_the_tick(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(
        journal_path, [_observation_line(raw_event_id="raw-1", as_of_ms=_as_of_ms())]
    )
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    # AbsentWallClockReference -> SessionFactsOwner.session_context(...) is None (no wall-clock
    # reading to derive one from) -- test_session_wiring.py's own
    # test_absent_wall_clock_denies_step3_and_records_absent_once already proves
    # runtime.session_facts.phase_for_step3(...) is None under this exact wall clock, while
    # health still reaches TRUSTED (unrelated to the wall clock).
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=AbsentWallClockReference(),
    )
    _reach_trusted(runtime)
    assert runtime.marketfeed is not None
    assert runtime.session_facts.session_context(fx.INSTRUMENT_CLASS) is None

    result = runtime.marketfeed.tick_once()
    assert result.outcome is TickOutcome.SKIPPED_SESSION_CLOSED
    assert result.queued_until_recovery is False
    assert result.value_view is None

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ----------------------------------------------------------------------------
# (10): multi-instrument config is refused at boot
# ----------------------------------------------------------------------------


def test_named_tbd_placeholder_instrument_class_refuses_to_load(
    tmp_path: Path, config_dir: Path
) -> None:
    """W-A A-0 round 2: an operator typing the literal placeholder string ``"TBD"``
    into a ``marketfeed.yaml`` scalar-string field must never be sealed into
    ``MarketFeedConfig`` as though it were a real deployment value."""
    from tos_runtime.compose._marketfeed_wiring import (
        MarketFeedConfigError,
        load_marketfeed_config,
    )

    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )
    raw = yaml.safe_load((config_dir / "marketfeed.yaml").read_text())
    raw["instrument_class"] = "TBD"
    (config_dir / "marketfeed.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))

    with pytest.raises(MarketFeedConfigError, match="template placeholder"):
        load_marketfeed_config(config_dir / "marketfeed.yaml")


def test_a_multi_instrument_config_refuses_boot(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir,
        journal_path=journal_path,
        instruments=(fx.INSTRUMENT, "NQ"),
    )

    with pytest.raises(MultiInstrumentRefused, match="FORWARD-OBLIGATION-MS1"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


# ----------------------------------------------------------------------------
# absent config: marketfeed stays None, every existing e2e test's own happy path is untouched
# ----------------------------------------------------------------------------


def test_marketfeed_stays_none_when_unconfigured(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """No ``marketfeed.yaml``/``critical_input_policy.yaml`` under ``config_dir`` (the plain
    ``config_dir`` fixture, exactly as every OTHER compose e2e test uses it) — a legitimate,
    unconfigured state, never a boot refusal (``ComposedRuntime.marketfeed``'s own docstring).
    """
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    assert runtime.marketfeed is None
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_half_configured_marketfeed_refuses_boot_rather_than_staying_none(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """``marketfeed.yaml`` present, ``critical_input_policy.yaml`` ABSENT — a boot REFUSAL, not
    ``marketfeed is None`` (2026-09-17 defect fix: the module docstring used to claim "absent
    either file -> None, never a boot refusal" for BOTH files, but ``build_tick_scheduler`` only
    ever guards on ``marketfeed.yaml``'s own existence before calling
    ``load_critical_input_policy`` unconditionally, and that loader raises
    ``CriticalInputPolicyConfigError`` on a missing file. An operator who configured a tick
    source but did not govern it must be refused at boot, never handed a runtime with a silently
    absent tick source — this test pins that the CODE's behavior, not the old prose, is correct.
    """
    journal_path = tmp_path / "journal.jsonl"
    _write_journal(journal_path, [])
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )
    # Deliberately NOT calling _write_critical_input_policy(config_dir) — the file under test.
    assert not (config_dir / "critical_input_policy.yaml").exists()

    with pytest.raises(CriticalInputPolicyConfigError, match="not found"):
        _compose(tmp_path, config_dir, data_dir, custody_root)


# ----------------------------------------------------------------------------
# held runtime: recovery barrier HOLD -> queued, not silently dropped or silently run
# ----------------------------------------------------------------------------


def _kind_count(runtime, kind: str) -> int:
    row = runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    count = row[0]
    assert isinstance(count, int), f"COUNT(*) returned {type(count).__name__}"
    return count


def test_a_held_recovery_barrier_queues_the_tick_instead_of_running_or_dropping_it(
    tmp_path: Path, config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Pins the CONSEQUENCE of the held-runtime branch (scheduler.py's own module docstring),
    not the source ordering that produces it — team-lead review finding, 2026-09-16: the
    reviewer deleted the ``driver is None`` branch (replaced it with ``pass``) and separately
    moved ``build_tick_scheduler`` back to BEFORE ``apply_recovery_barrier`` in ``root.py``; the
    full suite stayed green under BOTH mutations because nothing had ever driven
    ``tick_once()`` against a held runtime.

    Holds the barrier the SAME way ``tests/recovery/test_drill.py``'s own
    ``test_crash_marker_only_holds_the_barrier`` does — an ``EVENT_HANDLING_STARTED`` marker
    durable with no matching ``EVENT_CONSUMED`` receipt, discovered on reboot (never a real
    OS-level crash) — then proves FOUR things about the marketfeed scheduler specifically, none
    of which any other test in this suite exercises:

    1. ``runtime2.marketfeed is not None`` — ``build_tick_scheduler`` runs even when
       ``driver`` is ``None`` (a HOLD is a legitimate state to build the scheduler INTO, not a
       reason to skip building it — the whole point is to keep queuing while held).
    2. ``tick_once()`` still reports ``TICKED``/``queued_until_recovery=True`` — never a
       silent no-op and never (mutation: scheduler built before the barrier) a tick that
       actually ran because it captured the live pre-HOLD driver.
    3. The event actually landed in the durable inbox (``inbox.count`` incremented by exactly
       one) — under the deleted branch, ``pass`` leaves it at zero.
    4. The evidence row was actually appended (module's own
       ``MARKETFEED_QUEUED_UNTIL_RECOVERY`` kind, count incremented by exactly one) — same
       failure mode under the deleted branch.
    """
    journal_path = tmp_path / "journal.jsonl"
    _write_critical_input_policy(config_dir)
    _write_marketfeed_config(
        config_dir, journal_path=journal_path, instruments=(fx.INSTRUMENT,)
    )

    runtime1 = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime1)
    _mark_handling_started(runtime1, fx.crossing_event(seq=1))

    runtime1.rcl_log.close()
    runtime1.evidence_store.close()
    runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)

    # The barrier held (the crash-window ambiguity from runtime1 is durable and discovered on
    # this reboot) -- the SAME assertion test_drill.py's own _assert_held makes.
    assert runtime2.driver is None
    assert runtime2.recovery is not None
    assert runtime2.recovery.ready is False

    # (1) built anyway.
    assert runtime2.marketfeed is not None

    _write_journal(
        journal_path,
        [_observation_line(raw_event_id="raw-held-1", as_of_ms=_as_of_ms())],
    )
    inbox_count_before = runtime2.inbox.count
    evidence_count_before = _kind_count(runtime2, "MARKETFEED_QUEUED_UNTIL_RECOVERY")

    result = runtime2.marketfeed.tick_once()

    # (2)
    assert result.outcome is TickOutcome.TICKED
    assert result.queued_until_recovery is True
    # (3)
    assert runtime2.inbox.count == inbox_count_before + 1
    # (4)
    assert (
        _kind_count(runtime2, "MARKETFEED_QUEUED_UNTIL_RECOVERY")
        == evidence_count_before + 1
    )

    runtime2.rcl_log.close()
    runtime2.evidence_store.close()


# ----------------------------------------------------------------------------
# _time_pacer_pass — the compose-side open/closed/unknown predicate (plan 2026-09-26 W1,
# review finding PR #806: unknown must not be treated as closed)
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("context", "expected_evaluations"),
    [
        (None, 5),  # unknown (time untrusted) -> every pass, like open
        (SessionContext(phase="CONTINUOUS", is_open=True), 5),  # open -> every pass
        (SessionContext(phase="CLOSED", is_open=False), 1),  # known closed -> interval
    ],
)
def test_time_pacer_backs_off_only_when_the_session_is_known_closed(
    context: SessionContext | None, expected_evaluations: int
) -> None:
    """Mutation: treat a missing session context as closed -> the unknown row evaluates once
    (60 s back-off mid-session) -> red."""
    from types import SimpleNamespace

    from tos_runtime.compose._marketfeed_wiring import _time_pacer_pass

    evaluations = 0

    def evaluate() -> None:
        nonlocal evaluations
        evaluations += 1

    now = {"ms": 0}
    before_pass = _time_pacer_pass(
        SimpleNamespace(  # type: ignore[arg-type]
            instrument_class="krx-index-futures",
            time_evaluate_closed_interval_ms=60_000,
        ),
        SimpleNamespace(evaluate=evaluate),  # type: ignore[arg-type]
        SimpleNamespace(session_context=lambda _cls: context),  # type: ignore[arg-type]
        SimpleNamespace(now_ms=lambda: now["ms"]),
    )
    for _ in range(5):
        assert before_pass() is True
        now["ms"] += 1_000
    assert evaluations == expected_evaluations
