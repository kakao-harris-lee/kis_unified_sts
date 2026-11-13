"""Futures rollover compose e2e (TOS Phase 5 W5 plan §2 decision 7; lane f4, Phase B).

**Rollover = calendar phase + kernel membership, never a runtime predicate** (decision 7).
Once the calendar's own ``futures_expiry`` rule says the instant is past expiry, the
``effective_phase_at`` fold (:mod:`tos_runtime.calendar.phase`) supplies the rule's
``expired_phase`` token (``"EXPIRED"``) — session_facts observes it, step 3's
``VenueConstraintStage`` folds it into the kernel's own ``session_phase_admits``, and the
kernel refuses membership (``EXPIRED`` is not in the venue policy's admitting set for any
action) — INADMISSIBLE, zero sends. The runtime never asserts "expired therefore refuse"
itself; it only supplies the token the kernel already knows how to reject.

Hermetic (D1.4): real sqlite files under ``tmp_path``, reusing this suite's own
``_compose``/``_reach_trusted``/``write_approval_file``/``_drive_crossing_tick`` helpers
(``test_compose_root.py``/``test_session_wiring.py``) rather than re-deriving compose wiring a
third time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from tos_runtime.calendar import phase as calendar_phase
from tos_runtime.calendar.ports import FixedWallClockReference

from . import _fixtures as fx
from .test_compose_root import _compose, _reach_trusted
from .test_session_wiring import _drive_crossing_tick

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: The second Thursday of September 2026 (a real quarterly expiry month, [3, 6, 9, 12]) —
#: verified directly: `calendar.Calendar().itermonthdates(2026, 9)` filtered to Thursdays gives
#: [09-03, 09-10, 09-17, 09-24]; the second is 2026-09-10.
_EXPIRY_DATE_ISO = "2026-09-10"

#: 2026-09-10 19:00 KST — the expiry day itself, AFTER its last regular (non-crossing)
#: session window has ended (09:00-15:45), so `maturity_at(...).expired is True`
#: (plan §2 decision 1), and inside the night window below, so the UNDERLYING session phase
#: is still the admitting `CONTINUOUS` token. Both halves matter: scenario (a) needs a
#: genuinely-expired instant, and the M5 mutation below needs the un-folded phase at that
#: SAME instant to admit, so that removing the maturity fold visibly restores the send.
#:
#: This used to be 2026-09-11 10:00 (the day after expiry), which relied on `maturity_at`
#: reporting the whole instrument CLASS expired for the rest of the rule month — the
#: over-conservative class-level reading the 2026-09-13 wiring plan §7 carried forward as a
#: defect ("클래스 단위 만기(월말까지 EXPIRED)는 계약월 단위 모델로 후속") and this branch
#: fixes: past a rule month's expiry, `maturity_at` now rolls to the next rule month, so the
#: day after expiry is NOT expired and cannot drive this scenario any more.
_AFTER_EXPIRY_UNIX_MS = 1_789_034_400_000

#: 2026-09-09 10:00 KST (Wednesday, the day BEFORE expiry, inside the regular 09:00-15:45
#: window) — `today < expiry_date`, so `expired is False` and the regular phase admits.
_DAY_BEFORE_EXPIRY_UNIX_MS = 1_788_915_600_000


def _write_futures_calendar(
    config_dir: Path, *, calendar_version: str = "cal-compose-0"
) -> None:
    """Override the shared conftest.py calendar with a REALISTIC narrow window (09:00-15:45
    weekdays) PLUS a real quarterly futures-expiry rule for ``fx.INSTRUMENT_CLASS`` — the shared
    fixture's own ``futures_expiry: {}`` carries no rule at all, so it cannot exercise rollover.

    The second window (18:00->05:00, crossing midnight) is what makes
    :data:`_AFTER_EXPIRY_UNIX_MS` expressible at all: ``maturity_at`` flips ``expired`` at the
    end of the last **non-crossing** window, so an instant that is both past expiry AND inside
    an open, admitting session can only sit in a crossing window. It carries the same
    ``CONTINUOUS`` token as the day window (``fx.SESSION_PHASE``, the only phase the venue
    policy admits) so the M5 mutation below still reaches transport. Hours mirror the real KRX
    futures night session the W5 survey recorded.
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
                        },
                        {
                            "phase": "CONTINUOUS",
                            "start": "18:00",
                            "end": "05:00",
                            "days": ["MON", "TUE", "WED", "THU", "FRI"],
                            "crosses_midnight": True,
                        },
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


def _latest_session_facts_observed_payload(runtime) -> dict:
    row = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'SESSION_FACTS_OBSERVED' "
        "ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "expected at least one SESSION_FACTS_OBSERVED row"
    payload = json.loads(row[0])["payload"]
    assert isinstance(
        payload, dict
    ), f"SESSION_FACTS_OBSERVED payload is {type(payload).__name__}"
    return payload


# ============================================================================
# (a) Past expiry -- EXPIRED phase -> step 3 INADMISSIBLE -> send 0
# ============================================================================


def test_past_expiry_instant_is_expired_phase_inadmissible_and_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The instant is past expiry AND inside an open session window (see
    :data:`_AFTER_EXPIRY_UNIX_MS`) — so the zero sends below can only come from the maturity
    fold, never from the session being closed anyway."""
    _write_futures_calendar(config_dir)
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
