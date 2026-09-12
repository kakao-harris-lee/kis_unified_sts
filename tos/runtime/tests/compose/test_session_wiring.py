"""Compose e2e tests for :mod:`tos_runtime.compose._session_wiring` /
:class:`~tos_runtime.calendar.owner.SessionFactsOwner` (TOS Phase 5 W5 plan §2
decisions 1-5, ``docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md``).

Isolated owner-only unit tests live in ``tests/calendar/test_owner.py`` — this
file proves the same facts wired through a FULL composed runtime: step 3's
``VenueConstraintStage`` fold, item 12's kernel gate, and the boot refusals
(``SessionCalendarMismatch``, ``RetiredConfigPresent``).

Hermetic (D1.4): real sqlite files under ``tmp_path``, real custody files this
suite's own ``conftest.py``/``_fixtures.py`` create with 0600 + uid.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar.owner import SessionCalendarMismatch
from tos_runtime.calendar.ports import AbsentWallClockReference, FixedWallClockReference
from tos_runtime.compose._session_wiring import RetiredConfigPresent

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_RUNTIME_ROOT = Path(__file__).resolve().parents[2]  # tos/runtime
_SRC = _RUNTIME_ROOT / "src"

#: A fixed weekday instant OUTSIDE the shared conftest.py calendar's window,
#: but still a real Monday (not that it matters for the permissive fixture,
#: whose window covers every hour of every day) -- used for a calendar THIS
#: file overrides locally to test the negative paths.
_MONDAY_2026_09_14_10_00_KST_UNIX_MS = fx.DEFAULT_WALL_CLOCK_UNIX_MS
#: Same date, 22:00 KST -- well after a real 09:00-15:30-style regular window.
_MONDAY_2026_09_14_22_00_KST_UNIX_MS = 1_789_390_800_000
#: Saturday 2026-09-19 10:00 KST -- outside any weekday-only window.
_SATURDAY_2026_09_19_10_00_KST_UNIX_MS = 1_789_779_600_000


def _write_narrow_calendar(
    config_dir: Path, *, calendar_version: str = "cal-compose-0"
) -> None:
    """Override the shared conftest.py calendar with a REALISTIC narrow window
    (09:00-15:30 weekdays only) for this file's negative-path scenarios --
    the shared fixture is deliberately permissive (open 24/7) so it cannot
    exercise a closed/INADMISSIBLE phase."""
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
                            "end": "15:30",
                            "days": ["MON", "TUE", "WED", "THU", "FRI"],
                            "crosses_midnight": False,
                        }
                    ]
                },
                "closed_phase": "CLOSED",
                "futures_expiry": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _verify_item_payloads(runtime) -> list[dict]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'VERIFY_ITEM' ORDER BY rowid"
    ).fetchall()
    return [json.loads(row[0])["payload"] for row in rows]


def _kind_count(runtime, kind: str) -> int:
    return runtime.evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()[0]


def _drive_crossing_tick(runtime, custody_root: Path):
    """Two-``run_once`` admission dance (mirrors every other compose e2e test
    in this suite): construct the proposal/intent, write the matching
    approval file, then re-drive so the flow reaches the send boundary."""
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    results2 = runtime.run_once((event,))
    return results2[0]


# ============================================================================
# (1) Fixed weekday 10:00 KST -- ADMISSIBLE step 3, SATISFIED item 12
# ============================================================================


def test_fixed_weekday_admits_step3_and_satisfies_item12(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """``_compose()``'s own default (module docstring in test_compose_root.py)
    already IS this scenario -- the shared conftest.py calendar is open 24/7,
    and the SYNTHETIC scope is non-broker-reaching, so item 12 should reach a
    genuine SATISFIED."""
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    assert runtime.session_facts is not None
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CONTINUOUS"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None and result.flow.handoff is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "ADMIT"

    verdicts = _verify_item_payloads(runtime)
    (item12,) = (
        v
        for v in verdicts
        if v["item"] == "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION"
    )
    assert item12["outcome"] == "SATISFIED"

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (2) Holiday / after-hours -- closed_phase -> INADMISSIBLE step 3, send 0
# ============================================================================


def test_after_hours_instant_denies_step3_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_narrow_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_MONDAY_2026_09_14_22_00_KST_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CLOSED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"
    assert runtime.transport.requests == ()

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_weekend_instant_denies_step3_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    _write_narrow_calendar(config_dir)
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=FixedWallClockReference(_SATURDAY_2026_09_19_10_00_KST_UNIX_MS),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) == "CLOSED"

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value != "ADMIT"
    assert runtime.transport.requests == ()

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (3) Absent wall clock -- phase None -> step 3 UNKNOWN, send 0,
#     SESSION_FACTS_SOURCE_ABSENT exactly once
# ============================================================================


def test_absent_wall_clock_denies_step3_and_records_absent_once(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(
        tmp_path,
        config_dir,
        data_dir,
        custody_root,
        wall_clock=AbsentWallClockReference(),
    )
    _reach_trusted(runtime)
    assert runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS) is None

    result = _drive_crossing_tick(runtime, custody_root)
    assert result.flow is not None
    verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
    assert verdict_by_step["VENUE_ADMISSIBILITY_DECISION"].outcome.value == "UNKNOWN"
    assert runtime.transport.requests == ()
    assert _kind_count(runtime, "SESSION_FACTS_SOURCE_ABSENT") == 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (4) calendar_version mismatch -> SessionCalendarMismatch at boot (M4)
# ============================================================================


def test_calendar_version_mismatch_refuses_to_boot(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """``time.yaml``'s ``trading_calendar_version`` is ``"cal-compose-0"``
    (conftest.py) -- a disagreeing ``calendar.yaml`` refuses composition
    entirely (mutation M4: skipping this check would let the two configs
    silently drift)."""
    _write_narrow_calendar(config_dir, calendar_version="a-different-calendar-version")
    with pytest.raises(SessionCalendarMismatch):
        _compose(tmp_path, config_dir, data_dir, custody_root)


# ============================================================================
# (5) A leftover egress_attestations.yaml refuses to boot (M9)
# ============================================================================


def test_leftover_egress_attestations_file_refuses_to_boot(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Mutation M9: a stale ``egress_attestations.yaml`` (retired, plan §2
    decision 4) left in ``config_dir`` must never be silently ignored -- an
    operator could otherwise believe an attestation is still read."""
    (config_dir / "egress_attestations.yaml").write_text(
        yaml.safe_dump({"venue_session_account_facts_current": {"attested": True}}),
        encoding="utf-8",
    )
    with pytest.raises(RetiredConfigPresent):
        _compose(tmp_path, config_dir, data_dir, custody_root)


# ============================================================================
# (6) SESSION_FACTS_OBSERVED -- unchanged across two same-phase ticks
#     (compose-level corroboration; tests/calendar/test_owner.py has the
#     exhaustive isolated-owner version, including the +1-on-boundary-cross
#     case, which needs a stepping wall clock a full compose run cannot
#     inject without a second FixedWallClockReference-per-tick seam).
# ============================================================================


def test_session_facts_observed_does_not_grow_across_repeated_reads(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    # Same tick generation (no event has been driven) -- the observation is
    # cached; at most one SESSION_FACTS_OBSERVED row exists.
    assert _kind_count(runtime, "SESSION_FACTS_OBSERVED") <= 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ============================================================================
# (7) SESSION_OPEN_EXPECTATION -- recorded, zero consumers (negative-grep)
# ============================================================================


def test_session_open_expectation_is_recorded_and_never_consumed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    runtime.session_facts.phase_for_step3(fx.INSTRUMENT_CLASS)
    assert _kind_count(runtime, "SESSION_OPEN_EXPECTATION") >= 1

    runtime.rcl_log.close()
    runtime.evidence_store.close()


#: Matches a read of the SESSION_OPEN_EXPECTATION evidence kind by NAME (a
#: consumer would have to name the kind to filter/query for it) -- the sole
#: producer, calendar/owner.py, is excluded below.
_SESSION_OPEN_EXPECTATION_MENTION = re.compile(r"SESSION_OPEN_EXPECTATION")


def test_no_runtime_module_consumes_session_open_expectation_for_admission() -> None:
    """Plan §2 decision 3 (b): ``SESSION_OPEN_EXPECTATION`` is recorded but
    NON-authoritative -- nothing in the runtime reads this evidence kind back
    to make an admission decision. A grep-pin canary (mirrors
    ``tests/engine/test_no_direct_latch_clear.py``'s own idiom): scoped to
    ``tos_runtime/src`` only, the sole producer (``calendar/owner.py``, which
    defines and appends the kind) is the only allowed mention."""
    allowed = {_SRC / "tos_runtime" / "calendar" / "owner.py"}
    offenders = []
    for path in _SRC.rglob("*.py"):
        if path in allowed:
            continue
        if _SESSION_OPEN_EXPECTATION_MENTION.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert offenders == []
