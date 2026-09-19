"""Tests for scripts/ops/f9_observation_harvest.py — observation completeness.

Hermetic: every case is driven from fixture log files written into a tmp report
root. No Redis, no docker, no broker.

The two cases that matter most are ``test_blind_consumer_*`` (the 2026-09-17
reproduction) and ``test_quiet_market_*`` (a genuine quiet market). Under the
old ``Consumers`` column — a count of *running* consumers — those two days
rendered identically: "4" consumers and "0" signals. They must not.

The second family, ``test_*_evidence_*`` / ``test_*_coverage_*``, is the review
of that first fix. Every fixture here used to write a complete, untruncated,
single-container record, which is exactly the space where absent evidence hides:
a missing file, a zero-byte file, a log that starts after the open, a
``--tail``-capped capture, a failed ``docker logs``. None of those may render
``COMPLETE``.

The production ``config/f9_observation.yaml`` patterns are used as-is (only the
report root is redirected), so a typo in a real pattern fails these tests.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

import scripts.ops.f9_observation_harvest as mod

DAY = date(2026, 9, 18)
SESSION_OPEN = datetime(2026, 9, 18, 8, 45, tzinfo=mod.KST)

SCORED = (
    "futures-decision-engine",
    "futures-risk-filter",
    "futures-order-router",
    "futures-monitor",
)
CONSUMERS = SCORED[1:]

#: 08:45-15:45, the window config/market_schedule.yaml defines.
SESSION_MINUTES = 420

#: Which stream each consumer proves itself on.
CONSUMER_STREAMS = {
    "futures-risk-filter": ("signal.candidate.futures.shadow", "risk_filter"),
    "futures-order-router": ("signal.final.futures.shadow", "order_router"),
    "futures-monitor": ("order.fill.futures.shadow", "futures_monitor"),
}


@pytest.fixture
def config(tmp_path: Path) -> mod.ObservationConfig:
    """Production config with the harvest destination redirected to tmp."""
    return replace(mod.load_observation_config(), report_root=tmp_path)


@pytest.fixture
def day_dir(config: mod.ObservationConfig) -> Path:
    directory = config.report_root / DAY.isoformat()
    directory.mkdir(parents=True)
    return directory


def bracket(service: str) -> list[str]:
    """One innocuous line making a harvest file reach back to 08:00.

    It matches no ``observed`` and no ``blind`` pattern — it exists only so the
    file *testifies* from 08:00, the way a real uninterrupted ``--since 08:00``
    harvest does. Coverage is a property of the file, not of the service's
    health, and every case that is not specifically about a coverage hole gets
    it.

    There is deliberately no closing banner. A trailing
    ``2026-09-18 15:55:00 … shutting down`` is what made these fixtures encode
    the defect as correct: two banners plus ONE ``stream_message_processed``
    rendered a whole session ``consumed (COMPLETE)``. The file's coverage now
    reaches its ``<HHMMSS>`` harvest stamp on its own, so proving a service
    *worked* takes proof-of-consumption spread across the session — which is
    what ``observed_through`` writes.
    """
    return [f"2026-09-18 08:00:00,000 INFO __main__ {service} starting worker=w-1"]


def write_log(
    day_dir: Path,
    service: str,
    lines: list[str],
    stamp: str = "155535",
    *,
    cover: bool = True,
) -> Path:
    """Write one harvest file, one ``<asctime> <line>`` record per entry."""
    body = sorted([*lines, *(bracket(service) if cover else [])])
    path = day_dir / f"{service}.{stamp}.log"
    path.write_text(("\n".join(body) + "\n") if body else "", encoding="utf-8")
    return path


def at(minutes: int) -> str:
    """KST asctime *minutes* after the session open, as the daemons log it."""
    return (SESSION_OPEN + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S,000")


def setup_eval(minutes: int, setup: str, reason: str) -> str:
    return f"{at(minutes)} INFO __main__ [{setup}] no signal this cycle: {reason}"


def signal_published(minutes: int, signal_id: str) -> str:
    return (
        f"{at(minutes)} INFO __main__ event=signal_published "
        f"stream=signal.candidate.futures.shadow msg_id=1758{signal_id}-0 "
        f"signal_id={signal_id} setup_type=setup_d_vwap_reversion symbol=A01612 "
        "direction=long"
    )


def processed(minutes: int, stream: str, group: str, msg_id: str) -> str:
    return (
        f"{at(minutes)} INFO shared.streaming.stage "
        f"event=stream_message_processed stream={stream} consumer_group={group} "
        f"worker_id={group}-abc-1 msg_id={msg_id} ack=true claimed=false "
        "duration_ms=3"
    )


def read_error(minutes: int, group: str) -> str:
    return (
        f"{at(minutes)} ERROR services.futures_monitor.daemon "
        "event=monitor_stream_read_error "
        'streams="order.fill.futures.shadow,signal.final.futures.shadow" '
        f"consumer_group={group} worker_id={group}-abc-1 sleep_seconds=0.5"
    )


def verdict_line(minutes: int, verdict: str, msg_id: str) -> str:
    return (
        f"{at(minutes)} INFO __main__ risk_filter verdict={verdict} "
        f"msg_id={msg_id} signal_id=s1 setup_type=setup_d_vwap_reversion "
        "direction=long symbol=A01612 filter=- reason=- size_multiplier=1.0"
    )


def docker_result(
    returncode: int, stdout: bytes = b"", stderr: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    """What ``harvest_logs``' runner returns — the real type, not a stand-in."""
    return subprocess.CompletedProcess(
        args=["docker", "logs"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def decision_engine_tail(config: mod.ObservationConfig) -> int:
    """The configured ``--tail`` cap of the one service harvested that way."""
    tail = next(
        s.harvest_tail for s in config.services if s.name == "futures-decision-engine"
    )
    assert tail is not None, "the decision-engine is the --tail-harvested service"
    return tail


def observe(config: mod.ObservationConfig) -> mod.DayObservation:
    return mod.observe_day(config, DAY)


def row_of(config: mod.ObservationConfig, result: mod.DayObservation) -> str:
    return mod.render_row(result, config.row_counters)


def statuses(result: mod.DayObservation) -> dict[str, str]:
    return {s.name: s.status for s in result.services if s.role != "reference"}


def session_minutes(config: mod.ObservationConfig | None = None) -> list[int]:
    """Minute offsets from the open that satisfy the freshness bound.

    Derived from ``observation_max_gap_seconds`` rather than hardcoded, so
    retuning the configured bound surfaces here instead of silently turning
    every "healthy" fixture into a stale one.
    """
    gap = (config or mod.load_observation_config()).observation_max_gap_seconds // 60
    return list(range(0, SESSION_MINUTES + 1, max(1, gap - 5)))


def consumed_through(service: str) -> list[str]:
    """Proof-of-consumption spread across the session, per the freshness bound."""
    stream, group = CONSUMER_STREAMS[service]
    return [
        processed(minute, stream, group, f"{group}-{minute}")
        for minute in session_minutes()
    ]


def healthy_producer(day_dir: Path, *, candidates: int = 0) -> None:
    """A decision engine that demonstrably evaluated ACROSS the session.

    The real daemon logs one state line per cycle, so a producer that evaluated
    four times in seven hours is not a healthy producer and must not stand in
    for one — that fixture is how "coverage granted by any timestamped line"
    passed for "it was working".
    """
    reasons = ("not_extreme(z=0.4)", "vol_below_gate(0.61)", "outside_time_window")
    setups = (
        "setup_d_vwap_reversion",
        "setup_a_gap_reversion",
        "setup_c_event_reaction",
    )
    lines = [
        setup_eval(minute, setups[index % len(setups)], reasons[index % len(reasons)])
        for index, minute in enumerate(session_minutes())
    ]
    lines += [signal_published(30 + i, f"sig{i}") for i in range(candidates)]
    write_log(day_dir, "futures-decision-engine", lines)


def live_consumers(day_dir: Path, *, skip: tuple[str, ...] = ()) -> None:
    """Consumers that demonstrably handled messages, throughout a covered session."""
    for service in CONSUMERS:
        if service not in skip:
            write_log(day_dir, service, consumed_through(service))


# ---------------------------------------------------------------------------
# 1. A healthy day
# ---------------------------------------------------------------------------


def test_healthy_day_is_complete_and_row_shows_the_consumed_count(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A genuinely healthy day: proof of consumption spread across the session.

    This case used to be three lines per consumer — a startup banner, ONE
    ``stream_message_processed`` half an hour after the open, and a shutdown
    banner — and it rendered ``4/4 consumed (COMPLETE)`` on the strength of the
    two banners. It is now what its name claims: every consumer proving itself
    from the open to the close.
    """
    healthy_producer(day_dir, candidates=3)
    write_log(
        day_dir,
        "futures-risk-filter",
        consumed_through("futures-risk-filter")
        + [
            verdict_line(31, "passed", "m1"),
            verdict_line(32, "rejected", "m2"),
            verdict_line(33, "rejected", "m3"),
        ],
    )
    write_log(day_dir, "futures-order-router", consumed_through("futures-order-router"))
    write_log(day_dir, "futures-monitor", consumed_through("futures-monitor"))

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict == mod.VERDICT_COMPLETE
    assert statuses(result) == dict.fromkeys(SCORED, mod.STATUS_CONSUMED)
    assert all(s.covers_session for s in result.services if s.name in SCORED)
    assert all(s.observation_is_fresh for s in result.services if s.name in SCORED)
    assert "4/4 consumed" in row
    # candidates -> final -> fills, bare because the day is COMPLETE.
    assert f"3 -> 1 -> {len(session_minutes())}" in row
    assert "UNQUALIFIED" not in row


def test_redelivered_candidate_is_not_double_counted(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The runbook's de-duplication rule: last verdict per msg_id wins."""
    healthy_producer(day_dir, candidates=1)
    write_log(
        day_dir,
        "futures-risk-filter",
        [
            processed(31, "signal.candidate.futures.shadow", "risk_filter", "m1"),
            verdict_line(31, "passed", "m1"),
            # Same stream entry redelivered (XAUTOCLAIM) and re-evaluated.
            verdict_line(45, "passed", "m1"),
        ],
    )
    assert observe(config).counters["final"] == 1


# ---------------------------------------------------------------------------
# 2. The 2026-09-17 reproduction — up, RestartCount=0, consuming nothing
# ---------------------------------------------------------------------------


def test_blind_consumer_is_not_complete_and_is_named_in_the_row(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir)
    live_consumers(day_dir, skip=("futures-monitor",))
    # The 09-17/09-18 signature: a vanished-stream NOGROUP loop. The daemon is
    # up and restart-free; it just never reads anything. The real log repeats
    # this line every ~30s for the whole window.
    write_log(
        day_dir,
        "futures-monitor",
        [read_error(minute, "futures_monitor") for minute in range(0, 421)],
    )

    result = observe(config)
    row = row_of(config, result)
    monitor = next(s for s in result.services if s.name == "futures-monitor")

    assert monitor.status == mod.STATUS_BLIND
    assert monitor.observed_count == 0
    assert result.verdict != mod.VERDICT_COMPLETE
    assert "NOT COMPLETE" in row
    assert "futures-monitor BLIND 08:45-15:45" in row
    # The whole point: the count must not read as a measurement.
    assert "0 -> 0 -> 0" in row
    assert "UNQUALIFIED" in row
    assert "lower bound, not a measurement" in row


def test_vanished_consumer_group_recovery_is_blindness_not_health(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A recreated group means the group was GONE — publishes were lost to it.

    Both spellings are evidence: the structured one PR #740 introduced, and the
    prose one in the logs harvested during the blind window itself.
    """
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-risk-filter",
        [
            f"{at(62)} WARNING shared.streaming.stage consumer group missing; "
            "recreated stream=signal.candidate.futures.shadow group=risk_filter",
        ],
    )
    write_log(
        day_dir,
        "futures-order-router",
        [
            f"{at(63)} WARNING shared.streaming.stage "
            "event=consumer_group_recovered stream=signal.final.futures.shadow "
            "consumer_group=order_router",
        ],
    )

    result = observe(config)
    assert statuses(result)["futures-risk-filter"] == mod.STATUS_BLIND
    assert statuses(result)["futures-order-router"] == mod.STATUS_BLIND
    assert result.verdict != mod.VERDICT_COMPLETE


def test_dead_observation_surface_reads_not_observed(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    for service in SCORED:
        write_log(day_dir, service, [read_error(minute, "g") for minute in (0, 60)])

    result = observe(config)
    assert result.verdict == mod.VERDICT_NOT_OBSERVED
    assert "NOT OBSERVED" in row_of(config, result)


# ---------------------------------------------------------------------------
# 3. A partial day — a consumer blind from mid-session
# ---------------------------------------------------------------------------


def test_consumer_blind_from_mid_session_is_partial_with_the_window(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir, candidates=2)
    live_consumers(day_dir, skip=("futures-monitor", "futures-risk-filter"))
    write_log(
        day_dir,
        "futures-risk-filter",
        consumed_through("futures-risk-filter") + [verdict_line(31, "passed", "m1")],
    )
    # Consumes until 11:15 (150 min after open), then goes blind to the close.
    write_log(
        day_dir,
        "futures-monitor",
        [processed(36, "order.fill.futures.shadow", "futures_monitor", "o1")]
        + [read_error(minute, "futures_monitor") for minute in range(150, 421)],
    )

    result = observe(config)
    row = row_of(config, result)
    monitor = next(s for s in result.services if s.name == "futures-monitor")

    assert result.verdict == mod.VERDICT_PARTIAL
    assert monitor.status == mod.STATUS_PARTIALLY_BLIND
    assert monitor.observed_count == 1
    assert [
        (start.strftime("%H:%M"), end.strftime("%H:%M"))
        for start, end in monitor.blind_windows
    ] == [("11:15", "15:45")]
    assert "futures-monitor blind 11:15-15:45" in row
    assert "UNQUALIFIED" in row


def test_two_separate_blind_runs_stay_two_windows(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-monitor",
        [processed(200, "order.fill.futures.shadow", "futures_monitor", "o1")]
        + [read_error(minute, "futures_monitor") for minute in (0, 1, 2)]
        + [read_error(minute, "futures_monitor") for minute in (400, 401)],
    )
    monitor = next(s for s in observe(config).services if s.name == "futures-monitor")
    assert len(monitor.blind_windows) == 2


# ---------------------------------------------------------------------------
# 4. A quiet market — evaluations happened, nothing qualified
# ---------------------------------------------------------------------------


def test_quiet_market_with_zero_candidates_is_not_complete_and_says_why(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A quiet day proves the PRODUCER looked. It proves nothing downstream.

    This case used to render ``4/4 observing (1 consumed, 3 idle - nothing was
    due) (COMPLETE)`` under an exemption that excused silent consumers whenever
    the producer published nothing. The exemption is gone: the healthy idle loop
    emits nothing **at any log level** — ``xreadgroup`` returns no messages,
    ``post_poll``, ``sleep(0)``, ``continue``, with no logging on that path
    (``shared/streaming/stage.py``) — so a healthy idle consumer and one that
    died at the open leave byte-identical records. The binding constraint is
    that code-path gap, not a log level: ``consumer_group_already_present`` is
    DEBUG but also fires only *after* a read has already failed, so raising
    ``LOG_LEVEL`` (which both monitors honour since PR #749) would add no
    idle-liveness evidence. A heartbeat in the idle branch is the only fix, and
    a quiet day can read COMPLETE again once one exists. Until then, calling it
    COMPLETE is the runbook's own INERT-GATE CAVEAT committed one level up.
    """
    healthy_producer(day_dir, candidates=0)
    # The downstream consumers logged nothing during the session. Their files
    # span the session; they are simply silent.
    for service in CONSUMERS:
        write_log(day_dir, service, [])

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict == mod.VERDICT_PARTIAL
    assert statuses(result) == {
        "futures-decision-engine": mod.STATUS_CONSUMED,
        **dict.fromkeys(CONSUMERS, mod.STATUS_NO_EVIDENCE),
    }
    assert "1/4 consumed" in row
    assert "NO EVIDENCE (silent where harvested)" in row
    assert "0 -> 0 -> 0" in row
    # Noisier than the old COMPLETE, and never false.
    assert "UNQUALIFIED" in row
    assert "nothing was due" not in row


def test_quiet_market_and_blind_day_do_not_render_alike(
    config: mod.ObservationConfig, tmp_path: Path
) -> None:
    """The regression this file exists for, stated as one comparison."""
    quiet_dir = tmp_path / "quiet" / DAY.isoformat()
    quiet_dir.mkdir(parents=True)
    healthy_producer(quiet_dir, candidates=0)
    for service in CONSUMERS:
        write_log(quiet_dir, service, [])
    quiet = mod.render_row(
        mod.observe_day(replace(config, report_root=tmp_path / "quiet"), DAY),
        config.row_counters,
    )

    blind_dir = tmp_path / "blind" / DAY.isoformat()
    blind_dir.mkdir(parents=True)
    healthy_producer(blind_dir, candidates=0)
    for service in CONSUMERS:
        write_log(blind_dir, service, [])
    write_log(
        blind_dir,
        "futures-monitor",
        [read_error(minute, "futures_monitor") for minute in range(0, 421)],
        stamp="113330",
        cover=False,
    )
    blind = mod.render_row(
        mod.observe_day(replace(config, report_root=tmp_path / "blind"), DAY),
        config.row_counters,
    )

    assert quiet != blind
    assert "0 -> 0 -> 0" in quiet and "0 -> 0 -> 0" in blind
    # Both are unqualified, but they say different things about WHY.
    assert "futures-monitor NO EVIDENCE (silent where harvested)" in quiet
    assert "futures-monitor BLIND 08:45-15:45" in blind
    assert "BLIND" not in quiet


def test_producer_blind_for_part_of_the_day_cannot_excuse_silent_consumers(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A partly-blind producer cannot establish that nothing was due."""
    write_log(
        day_dir,
        "futures-decision-engine",
        [
            setup_eval(20, "setup_d_vwap_reversion", "not_extreme(z=0.4)"),
            setup_eval(120, "setup_a_gap_reversion", "no_market_context"),
        ],
    )
    result = observe(config)
    assert statuses(result)["futures-decision-engine"] == mod.STATUS_PARTIALLY_BLIND
    assert statuses(result)["futures-risk-filter"] == mod.STATUS_NO_EVIDENCE
    assert result.verdict == mod.VERDICT_PARTIAL
    assert "NO EVIDENCE (no harvest file)" in row_of(config, result)


def test_one_line_producer_cannot_excuse_silent_consumers(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The reviewer's reproduction of CRITICAL 1.

    A producer that emitted ONE line at 15:45 with every consumer silent used
    to render ``4/4 observing (1 consumed, 3 idle - nothing was due)
    (COMPLETE)``: the exemption tested only the producer's *status*, never its
    span, so a producer that stopped at 08:57 excused a consumer dead all day.
    """
    write_log(
        day_dir,
        "futures-decision-engine",
        [setup_eval(420, "setup_d_vwap_reversion", "not_extreme(z=0.4)")],
        cover=False,
    )
    for service in CONSUMERS:
        write_log(day_dir, service, [])

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict != mod.VERDICT_COMPLETE
    assert "COMPLETE" not in row.replace("NOT COMPLETE", "")
    assert "observing" not in row
    # One line at 15:45 covers one instant, not a session.
    producer = next(s for s in result.services if s.name == "futures-decision-engine")
    assert producer.status == mod.STATUS_PARTIAL_COVERAGE
    assert not producer.covers_session
    assert "harvest does not span the session" in row


def test_setup_a_without_a_previous_close_is_blindness(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """``no_prev_close`` means the day proves nothing about Setup A (runbook)."""
    write_log(
        day_dir,
        "futures-decision-engine",
        [
            setup_eval(minute, "setup_a_gap_reversion", "no_prev_close")
            for minute in (5, 9)
        ],
    )
    producer = next(
        s for s in observe(config).services if s.name == "futures-decision-engine"
    )
    assert producer.status == mod.STATUS_BLIND


# ---------------------------------------------------------------------------
# 5. Absent evidence is never laundered into a benign status
# ---------------------------------------------------------------------------


def test_consumer_with_no_harvest_file_is_no_evidence(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The reviewer's reproduction of CRITICAL 2: three consumers, no files.

    This rendered ``4/4 observing (1 consumed, 3 idle - nothing was due)
    (COMPLETE)`` — four-out-of-four "observing" on zero bytes.
    """
    healthy_producer(day_dir, candidates=0)

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict != mod.VERDICT_COMPLETE
    assert "observing" not in row
    for name in CONSUMERS:
        service = next(s for s in result.services if s.name == name)
        assert service.evidence == mod.EVIDENCE_NO_FILE
        assert service.status == mod.STATUS_NO_EVIDENCE
    assert row.count("NO EVIDENCE (no harvest file)") == 3


def test_zero_byte_harvest_is_no_evidence_not_silence(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The real 2026-09-18 order-router: both harvests are 0 bytes."""
    healthy_producer(day_dir, candidates=0)
    for stamp in ("113330", "155535"):
        (day_dir / f"futures-order-router.{stamp}.log").write_bytes(b"")

    result = observe(config)
    router = next(s for s in result.services if s.name == "futures-order-router")

    assert router.evidence == mod.EVIDENCE_EMPTY
    assert router.status == mod.STATUS_NO_EVIDENCE
    assert result.verdict != mod.VERDICT_COMPLETE
    assert (
        "futures-order-router NO EVIDENCE (harvest file present but empty)"
        in row_of(config, result)
    )


def test_unparseable_harvest_is_no_evidence(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """Bytes without a timestamp testify to nothing and to no span."""
    healthy_producer(day_dir, candidates=0)
    (day_dir / "futures-monitor.155535.log").write_text(
        'Traceback (most recent call last):\n  File "x.py", line 1\n', encoding="utf-8"
    )

    result = observe(config)
    monitor = next(s for s in result.services if s.name == "futures-monitor")

    assert monitor.evidence == mod.EVIDENCE_UNPARSEABLE
    assert monitor.status == mod.STATUS_NO_EVIDENCE
    assert result.verdict != mod.VERDICT_COMPLETE
    assert "holds no timestamped line" in row_of(config, result)


def test_failed_docker_logs_capture_is_marked_and_never_scores(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A non-zero ``docker logs`` must not write a daemon error into evidence."""
    failed = docker_result(
        1, stderr=b"Error response from daemon: No such container: kis_paper-x\n"
    )
    outcomes = mod.harvest_logs(config, DAY, stamp="160000", runner=lambda _: failed)

    assert all(not outcome.ok for outcome in outcomes.values())
    assert all(
        outcome.path.name.endswith(mod.HARVEST_FAILED_SUFFIX)
        for outcome in outcomes.values()
    )
    # The daemon's error message is NOT filed as a .log the verdict would scan.
    assert not list(day_dir.glob("*.log"))

    result = observe(config)
    for name in SCORED:
        service = next(s for s in result.services if s.name == name)
        assert service.evidence == mod.EVIDENCE_HARVEST_FAILED
        assert service.status == mod.STATUS_NO_EVIDENCE
    assert result.verdict == mod.VERDICT_NOT_OBSERVED
    assert "NO EVIDENCE (docker logs capture failed)" in row_of(config, result)


def test_a_failed_capture_taints_the_service_even_beside_a_good_one(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A hole of unknown size is not closed by a sibling harvest."""
    healthy_producer(day_dir)
    live_consumers(day_dir)
    (day_dir / f"futures-monitor.160000{mod.HARVEST_FAILED_SUFFIX}").write_text(
        "Error response from daemon: No such container\n", encoding="utf-8"
    )

    result = observe(config)
    monitor = next(s for s in result.services if s.name == "futures-monitor")
    assert monitor.evidence == mod.EVIDENCE_HARVEST_FAILED
    assert monitor.status == mod.STATUS_NO_EVIDENCE
    assert result.verdict != mod.VERDICT_COMPLETE


# ---------------------------------------------------------------------------
# 6. Coverage — what the harvest reaches, vs what the service did
# ---------------------------------------------------------------------------


def test_log_starting_after_the_open_cannot_be_consumed(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """Rotation drops the OLDEST lines, so it destroys early-session blindness.

    The reviewer's reproduction of HIGH 3: a monitor blind all morning whose
    rotated log keeps one late ``stream_message_processed`` used to render
    ``consumed``, day ``COMPLETE``, counts bare.
    """
    healthy_producer(day_dir, candidates=1)
    live_consumers(day_dir, skip=("futures-monitor",))
    write_log(
        day_dir,
        "futures-monitor",
        [
            processed(minute, "order.fill.futures.shadow", "futures_monitor", "o1")
            for minute in (400, 419)
        ],
        cover=False,
    )

    result = observe(config)
    row = row_of(config, result)
    monitor = next(s for s in result.services if s.name == "futures-monitor")

    assert monitor.status == mod.STATUS_PARTIAL_COVERAGE
    assert monitor.observed_count == 2
    assert not monitor.covers_session
    assert result.verdict == mod.VERDICT_PARTIAL
    assert "futures-monitor consumed, harvest does not span the session" in row
    assert "no evidence 08:45-15:25" in row
    assert "UNQUALIFIED" in row


def test_tail_capped_harvest_inside_the_session_cannot_be_consumed(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """``--tail 900`` covers minutes on a chatty day, not a session."""
    tail = decision_engine_tail(config)
    # 900 lines, all inside the last 15 minutes: the cap ate the whole morning.
    write_log(
        day_dir,
        "futures-decision-engine",
        [
            setup_eval(405 + index // 60, "setup_d_vwap_reversion", f"z={index}")
            for index in range(tail)
        ],
        cover=False,
    )
    live_consumers(day_dir)

    result = observe(config)
    producer = next(s for s in result.services if s.name == "futures-decision-engine")

    assert producer.coverage_truncated
    assert producer.status == mod.STATUS_PARTIAL_COVERAGE
    assert result.verdict == mod.VERDICT_PARTIAL
    assert "harvest does not span the session" in row_of(config, result)


def test_tail_capped_harvest_reaching_before_the_open_still_covers(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The real 2026-09-18 producer: 900 lines, oldest from the prior evening.

    The cap is real, but it removed only material OLDER than the open, so the
    surviving span still brackets the session. Truncation is recorded, and it
    does not by itself disqualify.
    """
    tail = decision_engine_tail(config)
    session = session_minutes(config)
    lines = [
        f"2026-09-17 17:54:{index % 60:02d},000 INFO __main__ "
        "[setup_d_vwap_reversion] no signal this cycle: outside_time_window"
        for index in range(tail - len(session) - 1)
    ]
    lines += [
        setup_eval(minute, "setup_d_vwap_reversion", "not_extreme(z=0.4)")
        for minute in session
    ]
    lines += [
        "2026-09-18 15:55:05,000 INFO __main__ [setup_d_vwap_reversion] "
        "no signal this cycle: outside_time_window",
    ]
    write_log(day_dir, "futures-decision-engine", lines, cover=False)
    live_consumers(day_dir)

    result = observe(config)
    producer = next(s for s in result.services if s.name == "futures-decision-engine")

    assert producer.coverage_truncated
    assert producer.covers_session
    assert producer.status == mod.STATUS_CONSUMED
    assert result.verdict == mod.VERDICT_COMPLETE


def test_uncovered_tail_is_named_rather_than_ending_the_window(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The real 2026-09-18 monitor, and the reviewer's HIGH 4.

    ``docker logs`` lost everything before the 15:54 recreate, so the harvest
    reaches 11:33 and stops. The monitor was in fact blind until 12:34. The row
    must not end the blind window where the file ends.
    """
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-monitor",
        [read_error(minute, "futures_monitor") for minute in range(-45, 169)],
        stamp="113330",
        cover=False,
    )
    write_log(
        day_dir,
        "futures-monitor",
        [f"{at(429)} INFO __main__ futures monitor starting worker=w-1"],
        stamp="155535",
        cover=False,
    )

    result = observe(config)
    row = row_of(config, result)
    monitor = next(s for s in result.services if s.name == "futures-monitor")

    assert monitor.status == mod.STATUS_BLIND
    assert "futures-monitor BLIND 08:45-11:33 (no evidence 11:33-15:45)" in row
    assert [
        (start.strftime("%H:%M"), end.strftime("%H:%M"))
        for start, end in monitor.uncovered
    ] == [("11:33", "15:45")]


def test_single_observation_window_renders_open_ended(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The real 2026-09-18 risk-filter: ONE ``group missing; recreated`` line.

    That is evidence of a group gone over an unknown window *ending at* 09:47,
    not of a point event at 09:47.
    """
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-risk-filter",
        [
            f"{at(62)} WARNING shared.streaming.stage consumer group missing; "
            "recreated stream=signal.candidate.futures.shadow group=risk_filter",
        ],
        cover=False,
    )

    row = row_of(config, observe(config))
    assert "futures-risk-filter BLIND <=09:47" in row
    # One gap, not the two adjacent ones a point-coverage span used to produce:
    # the file's span now runs from its line to the 15:55:35 harvest stamp, so
    # only the morning before that line is uncovered.
    assert "no evidence 08:45-09:47" in row
    assert "09:47-15:45" not in row


# ---------------------------------------------------------------------------
# 6b. Observation freshness — coverage says we looked, not that it worked
# ---------------------------------------------------------------------------


def banner(
    service: str, clock: str, what: str = "starting worker=w1 mode=shadow"
) -> str:
    """The real startup/shutdown banner shape, verbatim from the 09-18 harvest.

    ``2026-09-18 15:54:15,555 INFO __main__ futures monitor starting
    worker=futures-monitor-65e86f260dcb-1 mode=shadow symbol=A01612
    suffix=shadow`` — a timestamped line matching no ``observed`` and no
    ``blind`` pattern.
    """
    return f"2026-09-18 {clock},000 INFO __main__ {service} {what} symbol=A01612"


def test_two_banners_and_one_processed_line_are_not_a_consumed_session(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The reviewer's probe, and the defect the coverage commit did not close.

    Coverage is granted by ANY timestamped line, so a startup banner at 08:40
    and a restart banner at 15:50 bracketed the session while the only proof of
    consumption was one line at 08:46. That rendered
    ``4/4 consumed (COMPLETE)``, exit 0, ``counters.qualified: true``, with
    ``last_observed_kst`` seven hours before the close and nothing scoring it.

    It is reachable: ``services/futures_monitor/daemon.py`` creates
    ``_consume_loop`` as a task and only awaits it in ``finally``. If it raises,
    the task dies unretrieved, ``_stop`` is never set, and ``_status_loop``
    keeps the process up — the project's own "asyncio task exceptions SILENT"
    trap. A ``docker restart`` near the close (which preserves the log, unlike a
    recreate) then closes the span over the dead stretch. The real
    ``futures-monitor.155535.log`` holds exactly such a banner.
    """
    write_log(
        day_dir,
        "futures-decision-engine",
        [
            banner("futures decision engine", "08:40:00"),
            setup_eval(1, "setup_d_vwap_reversion", "not_extreme(z=0.4)"),
            banner("futures decision engine", "15:50:00", "starting worker=w1"),
        ],
        cover=False,
    )
    for service in CONSUMERS:
        stream, group = CONSUMER_STREAMS[service]
        write_log(
            day_dir,
            service,
            [
                banner(service, "08:40:00"),
                processed(1, stream, group, "m1"),
                banner(service, "15:50:00"),
            ],
            cover=False,
        )

    result = observe(config)
    row = row_of(config, result)
    monitor = next(s for s in result.services if s.name == "futures-monitor")

    assert result.verdict == mod.VERDICT_PARTIAL
    assert statuses(result) == dict.fromkeys(SCORED, mod.STATUS_STALE_OBSERVATION)
    # The harvest DID span the session — that is exactly why coverage alone
    # could never have caught this.
    assert monitor.covers_session is True
    assert monitor.observation_is_fresh is False
    assert monitor.observed_count == 1
    assert "0/4 consumed" in row
    assert "futures-monitor consumed, but no proof of consumption 08:46-15:45" in row
    assert "UNQUALIFIED" in row
    assert (
        mod.build_sidecar(result, row)["counters"]["qualified"] is False
    ), "the counters must not leave this day qualified"


def test_a_consumer_dead_all_morning_is_not_fresh_either(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The leading gap counts too: waking at 15:40 is as unproven as dying at 08:46."""
    healthy_producer(day_dir)
    live_consumers(day_dir, skip=("futures-monitor",))
    write_log(
        day_dir,
        "futures-monitor",
        [
            banner("futures monitor", "08:40:00"),
            processed(415, "order.fill.futures.shadow", "futures_monitor", "o1"),
        ],
        cover=False,
    )

    monitor = next(s for s in observe(config).services if s.name == "futures-monitor")
    assert monitor.covers_session is True
    assert monitor.status == mod.STATUS_STALE_OBSERVATION
    assert [
        (start.strftime("%H:%M"), end.strftime("%H:%M"))
        for start, end in monitor.unobserved
    ] == [("08:45", "15:40")]


def test_a_gap_inside_the_bound_stays_consumed(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The bound is a threshold, not a demand for continuous chatter."""
    gap = config.observation_max_gap_seconds // 60
    healthy_producer(day_dir)
    live_consumers(day_dir, skip=("futures-monitor",))
    write_log(
        day_dir,
        "futures-monitor",
        [
            processed(
                minute, "order.fill.futures.shadow", "futures_monitor", f"o{minute}"
            )
            for minute in range(0, SESSION_MINUTES + 1, gap)
        ],
    )

    result = observe(config)
    monitor = next(s for s in result.services if s.name == "futures-monitor")
    assert monitor.status == mod.STATUS_CONSUMED
    assert result.verdict == mod.VERDICT_COMPLETE


# ---------------------------------------------------------------------------
# 6c. The close boundary — a file's span ends at the harvest, not its last line
# ---------------------------------------------------------------------------


def test_a_quiet_half_minute_before_the_close_is_not_a_coverage_hole(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The reviewer's HIGH 3: four consuming services, files stopping at 15:44:30.

    That rendered ``NOT COMPLETE (PARTIAL)`` with ``no evidence 15:44-15:45`` on
    every service, while seven hours of interior silence rendered ``COMPLETE``.
    Same epistemic situation, opposite verdicts — and the 30-seconds-short case
    is the common one for a quiet consumer.

    ``docker logs`` returns everything up to the instant it runs, so a file
    stamped ``155535`` testifies to 15:55:35 whatever its last line says.
    """
    healthy_producer(day_dir)
    for service in CONSUMERS:
        stream, group = CONSUMER_STREAMS[service]
        write_log(
            day_dir,
            service,
            [
                processed(minute, stream, group, f"{group}-{minute}")
                for minute in session_minutes(config)
            ]
            # The last line lands 30 seconds short of the 15:45 close.
            + [f"2026-09-18 15:44:30,000 INFO __main__ {service} heartbeat"],
        )

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict == mod.VERDICT_COMPLETE
    assert "4/4 consumed (COMPLETE)" in row
    assert "no evidence" not in row
    assert all(s.covers_session for s in result.services if s.name in SCORED)


def test_a_file_whose_head_was_rotated_away_still_loses_that_head(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The tail reaches the harvest; the HEAD stays at the first surviving line.

    Rotation drops the OLDEST lines, so a head later than the ``--since`` floor
    cannot be told from a quiet start — and treating it as covered would undo
    the rotation defence that makes a late ``stream_message_processed`` stop
    proving an early-session service healthy.
    """
    healthy_producer(day_dir)
    live_consumers(day_dir, skip=("futures-monitor",))
    write_log(
        day_dir,
        "futures-monitor",
        [
            processed(
                minute, "order.fill.futures.shadow", "futures_monitor", f"o{minute}"
            )
            for minute in range(200, SESSION_MINUTES + 1, 20)
        ],
        cover=False,
    )

    monitor = next(s for s in observe(config).services if s.name == "futures-monitor")
    assert monitor.status == mod.STATUS_PARTIAL_COVERAGE
    assert [
        (start.strftime("%H:%M"), end.strftime("%H:%M"))
        for start, end in monitor.uncovered
    ] == [("08:45", "12:05")]


def test_harvest_stamp_is_read_from_the_filename(day_dir: Path) -> None:
    assert mod.harvest_stamp(Path("futures-monitor.155535.log"), DAY) == datetime(
        2026, 9, 18, 15, 55, 35, tzinfo=mod.KST
    )
    assert mod.harvest_stamp(Path("futures-monitor.log"), DAY) is None
    assert mod.harvest_stamp(Path("futures-monitor.996060.log"), DAY) is None


# ---------------------------------------------------------------------------
# 7. Session window, trading day, and harvest mechanics
# ---------------------------------------------------------------------------


def test_session_window_comes_from_market_schedule_yaml() -> None:
    opened, closed = mod.session_window(DAY)
    assert (opened.hour, opened.minute) == (8, 45)
    assert (closed.hour, closed.minute) == (15, 45)
    assert opened.tzinfo is mod.KST


def test_session_window_honours_a_different_schedule_file(tmp_path: Path) -> None:
    schedule = tmp_path / "schedule.yaml"
    schedule.write_text(
        yaml.safe_dump(
            {
                "market_schedule": {
                    "futures": {"regular": {"open": "09:30", "close": "14:00"}}
                }
            }
        ),
        encoding="utf-8",
    )
    opened, closed = mod.session_window(DAY, schedule_path=schedule)
    assert (opened.hour, opened.minute) == (9, 30)
    assert (closed.hour, closed.minute) == (14, 0)


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (None, OSError),
        ({"market_schedule": {}}, KeyError),
        (
            {
                "market_schedule": {
                    "futures": {"regular": {"open": "99:00", "close": "15:45"}}
                }
            },
            ValueError,
        ),
    ],
)
def test_a_wrong_schedule_fails_closed_rather_than_defaulting(
    tmp_path: Path, body: dict | None, error: type[Exception]
) -> None:
    """The loaders never raise — they fall back to 08:45/15:45 after a WARNING.

    Right for a per-tick caller, wrong here: a mistyped ``--schedule`` would
    silently verdict a session nobody checked, while the observation config
    next to it fails closed.
    """
    schedule = tmp_path / "missing.yaml"
    if body is not None:
        schedule.write_text(yaml.safe_dump(body), encoding="utf-8")
    with pytest.raises(error):
        mod.session_window(DAY, schedule_path=schedule)


@pytest.mark.parametrize(
    ("day", "trading"),
    [
        (date(2026, 9, 18), True),  # Friday
        (date(2026, 9, 19), False),  # Saturday
        (date(2026, 9, 25), False),  # 추석, in both holiday sources
        (date(2026, 10, 5), False),  # 대체휴일: only config/market_schedule.yaml
        (date(2026, 10, 6), True),  # the Tuesday after it
    ],
)
def test_is_session_day_reads_both_holiday_sources(day: date, trading: bool) -> None:
    assert mod.is_session_day(day) is trading


def test_non_trading_day_reads_no_session_not_not_observed(
    config: mod.ObservationConfig,
) -> None:
    """A weekend has no session, so there is nothing to have missed."""
    saturday = date(2026, 9, 19)
    (config.report_root / saturday.isoformat()).mkdir(parents=True)

    result = mod.observe_day(config, saturday)
    row = mod.render_row(result, config.row_counters)

    # `verdict` is what the evidence says and is never overwritten; the
    # calendar qualifies it in `reported_verdict`, which is what the row and
    # the exit status read.
    assert result.reported_verdict == mod.VERDICT_NO_SESSION
    assert "no session" in row
    assert "NOT OBSERVED" not in row
    assert "UNQUALIFIED" not in row
    assert "n/a" in row


def test_a_non_trading_day_holding_evidence_keeps_the_evidence_verdict(
    config: mod.ObservationConfig,
) -> None:
    """``NO_SESSION`` is a qualifier, not a replacement.

    It used to be written over the evidence-derived verdict after the scan,
    blanking the counts to ``n/a - no session`` and exiting 0 — so 2026-08-17
    with four genuinely consuming services rendered ``(no session …)`` and
    discarded every harvested fact. Both holiday sources describe themselves as
    provisional (``shared/calendar.py``: ``예상 - 확정 시 업데이트 필요``), so one
    wrong entry silently unscored a real trading day, on a script whose purpose
    is making unscored days visible.
    """
    substitute_holiday = date(2026, 8, 17)
    day_dir = config.report_root / substitute_holiday.isoformat()
    day_dir.mkdir(parents=True)
    # Same shape as a healthy trading day, on a day the calendar calls closed.
    write_log(
        day_dir,
        "futures-decision-engine",
        [
            setup_eval(minute, "setup_d_vwap_reversion", "not_extreme(z=0.4)").replace(
                "2026-09-18", substitute_holiday.isoformat()
            )
            for minute in session_minutes(config)
        ],
        cover=False,
    )
    for service in CONSUMERS:
        stream, group = CONSUMER_STREAMS[service]
        write_log(
            day_dir,
            service,
            [
                processed(minute, stream, group, f"{group}-{minute}").replace(
                    "2026-09-18", substitute_holiday.isoformat()
                )
                for minute in session_minutes(config)
            ],
            cover=False,
        )

    result = mod.observe_day(config, substitute_holiday)
    row = mod.render_row(result, config.row_counters)

    assert result.session_day is False
    assert result.has_evidence is True
    # The evidence is kept AND the calendar disagreement is stated.
    assert result.verdict == mod.VERDICT_COMPLETE
    assert result.reported_verdict == mod.VERDICT_COMPLETE
    assert "no session - 2026-08-17 is not a trading day" in row
    assert "BUT THE HARVEST HOLDS EVIDENCE" in row
    assert "4/4 consumed" in row
    assert "n/a - no session" not in row
    # Counts measured against a session window both sources say did not exist
    # are reported, never bare.
    assert "check the calendar" in row
    assert mod.build_sidecar(result, row)["counters"]["qualified"] is False


def test_a_non_trading_day_with_nothing_to_report_still_reads_no_session(
    config: mod.ObservationConfig,
) -> None:
    """Where the override changes no fact, it still applies — no weekend alarm."""
    saturday = date(2026, 9, 19)
    (config.report_root / saturday.isoformat()).mkdir(parents=True)

    result = mod.observe_day(config, saturday)
    assert result.has_evidence is False
    assert result.reported_verdict == mod.VERDICT_NO_SESSION
    assert result.verdict == mod.VERDICT_NOT_OBSERVED


def test_evidence_outside_the_session_window_is_ignored(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-monitor",
        [
            # 15:54, after the 15:45 close — the restart that ended the real
            # 09-18 blind window did not make that session observed.
            processed(429, "order.fill.futures.shadow", "futures_monitor", "o1"),
        ],
    )
    monitor = next(s for s in observe(config).services if s.name == "futures-monitor")
    assert monitor.observed_count == 0


def test_overlapping_harvests_are_de_duplicated(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """Two harvests of a container that was not recreated share their lines."""
    healthy_producer(day_dir, candidates=1)
    shared_line = processed(36, "order.fill.futures.shadow", "futures_monitor", "o1")
    write_log(day_dir, "futures-monitor", [shared_line], stamp="113330")
    write_log(
        day_dir,
        "futures-monitor",
        [
            shared_line,
            processed(40, "order.fill.futures.shadow", "futures_monitor", "o2"),
        ],
        stamp="155535",
    )
    monitor = next(s for s in observe(config).services if s.name == "futures-monitor")
    assert monitor.observed_count == 2
    assert len(monitor.files) == 2


def test_harvest_writes_timestamped_files_and_never_overwrites(
    config: mod.ObservationConfig,
) -> None:
    calls: list[list[str]] = []
    ok = docker_result(0, stdout=b"2026-09-18 09:00:00,000 INFO x hello\n")

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
        calls.append(list(command))
        return ok

    written = mod.harvest_logs(config, DAY, stamp="153000", runner=runner)

    assert written["futures-monitor"].ok
    assert written["futures-monitor"].path.name == "futures-monitor.153000.log"
    assert (
        written["futures-monitor"].path.read_text(encoding="utf-8").endswith("hello\n")
    )
    assert [c for c in calls if "--tail" in c], "decision-engine needs --tail"
    # The --tail caveat: decision-engine is harvested with --tail 900, the rest
    # with --since the configured KST clock time.
    tail_call = next(c for c in calls if "--tail" in c)
    assert tail_call[tail_call.index("--tail") + 1] == "900"
    assert tail_call[-1] == "kis_paper-futures-decision-engine"
    since_call = next(c for c in calls if "--since" in c)
    assert since_call[since_call.index("--since") + 1].startswith("2026-09-18T08:00")

    with pytest.raises(FileExistsError):
        mod.harvest_logs(config, DAY, stamp="153000", runner=runner)


# ---------------------------------------------------------------------------
# 8. Sidecar and CLI
# ---------------------------------------------------------------------------


def test_sidecar_records_per_consumer_detail_for_audit(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-monitor",
        [read_error(minute, "futures_monitor") for minute in (0, 30)],
    )
    result = observe(config)
    sidecar = mod.build_sidecar(result, row_of(config, result))

    assert sidecar["verdict"] == result.verdict
    monitor = next(s for s in sidecar["services"] if s["name"] == "futures-monitor")
    assert monitor["status"] == mod.STATUS_BLIND
    assert monitor["evidence"] == mod.EVIDENCE_LINES
    assert monitor["blind_count"] == 2
    assert monitor["blind_windows_kst"]
    assert monitor["covers_session"] is True
    assert monitor["coverage_kst"]
    assert monitor["evidence_files"], "the verdict must be auditable from files"


def test_sidecar_counters_carry_their_own_qualification(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """A reader who copies ``counters`` must not end up holding bare numbers."""
    healthy_producer(day_dir)
    result = observe(config)
    counters = mod.build_sidecar(result, row_of(config, result))["counters"]

    assert counters["qualified"] is False
    assert "lower bound" in counters["qualification"]
    assert counters["values"] == dict(result.counters)


def test_sidecar_names_the_uncovered_part_of_the_session(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir)
    write_log(
        day_dir,
        "futures-monitor",
        [processed(400, "order.fill.futures.shadow", "futures_monitor", "o1")],
        cover=False,
    )
    result = observe(config)
    sidecar = mod.build_sidecar(result, row_of(config, result))
    monitor = next(s for s in sidecar["services"] if s["name"] == "futures-monitor")

    # The file testifies from its one line to the 15:55:35 harvest stamp, so
    # the morning before it is uncovered and the rest is watched silence.
    assert monitor["covers_session"] is False
    assert monitor["uncovered_session_kst"] == [
        ["2026-09-18T08:45:00+09:00", "2026-09-18T15:25:00+09:00"],
    ]


def test_main_end_to_end_prints_the_row_and_exits_zero_on_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    day_dir = tmp_path / DAY.isoformat()
    day_dir.mkdir(parents=True)
    healthy_producer(day_dir, candidates=1)
    live_consumers(day_dir)

    code = mod.main(
        [
            "--date",
            DAY.isoformat(),
            "--no-harvest",
            "--no-point-in-time",
            "--report-root",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out.strip()

    assert code == 0
    assert out.startswith("| 2026-09-18 |")
    assert "4/4 consumed (COMPLETE)" in out
    sidecars = list(day_dir.glob("observation-completeness.*.json"))
    assert len(sidecars) == 1
    assert json.loads(sidecars[0].read_text(encoding="utf-8"))["verdict"] == "COMPLETE"


def test_main_exits_one_when_the_surface_could_not_observe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / DAY.isoformat()).mkdir(parents=True)
    code = mod.main(
        [
            "--date",
            DAY.isoformat(),
            "--no-harvest",
            "--no-point-in-time",
            "--report-root",
            str(tmp_path),
        ]
    )
    assert code == 1
    assert "NOT OBSERVED" in capsys.readouterr().out


def test_main_exits_zero_on_a_non_trading_day(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A weekend cron run must not raise a standing false alarm."""
    code = mod.main(
        [
            "--date",
            "2026-09-19",
            "--no-harvest",
            "--no-point-in-time",
            "--report-root",
            str(tmp_path),
        ]
    )
    assert code == 0
    assert "no session" in capsys.readouterr().out


@pytest.mark.parametrize("harvest_tail", [None, 0])
def test_a_tail_harvested_service_must_declare_its_cap(
    harvest_tail: int | None,
) -> None:
    """No hardcoded 900 to diverge from the truncation detector.

    ``str(spec.harvest_tail or 900)`` capped the harvest at a value the
    truncation detector never saw: it gated on ``harvest_tail is not None``, so
    such a service reported ``coverage_truncated: false`` forever — a wrong fact
    in the audit record. ``harvest_tail: 0`` was read as "absent" by the same
    truthiness test, though ``--tail 0`` returns nothing.
    """
    with pytest.raises(ValueError, match="harvest_tail"):
        mod.ServiceSpec(
            name="futures-decision-engine",
            container="futures-decision-engine",
            role=mod.ROLE_PRODUCER,
            harvest_mode=mod.HARVEST_MODE_TAIL,
            harvest_tail=harvest_tail,
            observed=(),
            blind=(),
            counters=(),
        )


def test_a_since_harvested_service_needs_no_cap() -> None:
    spec = mod.ServiceSpec(
        name="futures-monitor",
        container="futures-monitor",
        role=mod.ROLE_CONSUMER,
        harvest_mode=mod.HARVEST_MODE_SINCE,
        harvest_tail=None,
        observed=(),
        blind=(),
        counters=(),
    )
    with pytest.raises(ValueError, match="not harvested with --tail"):
        _ = spec.tail_cap


def test_a_mistyped_report_root_is_refused_rather_than_verdicted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A confident verdict against zero input, and a tree it then created.

    A root missing its ``f9-gate1`` segment rendered ``NOT OBSERVED - 0/4`` ×4,
    then ``mkdir(parents=True)``'d the mistyped tree and filed a sidecar in it,
    which a second run read back as its own evidence. ``--report-root`` also
    resolved against the CWD while the config value resolved against the repo
    root, so the same relative spelling meant two different trees.
    """
    missing = tmp_path / "reports"  # no f9-gate1 segment, nothing harvested
    code = mod.main(
        [
            "--date",
            DAY.isoformat(),
            "--no-harvest",
            "--no-point-in-time",
            "--report-root",
            str(missing),
        ]
    )
    captured = capsys.readouterr()

    assert code == 2, "a missing day directory is an input error, not a verdict"
    assert "NOT OBSERVED" not in captured.out
    assert "no harvest directory" in captured.err
    assert str(missing) in captured.err
    # The resolved root is echoed so a wrong one is visible at a glance.
    assert f"[root] {missing}" in captured.err
    # And nothing was created for a second run to read back as evidence.
    assert not missing.exists()


def test_a_relative_report_root_anchors_at_the_repo_root_not_the_cwd() -> None:
    assert mod.anchored_report_root("reports/f9-gate1") == (
        mod.load_observation_config().report_root
    )
    assert mod.anchored_report_root("/tmp/somewhere") == Path("/tmp/somewhere")


def test_a_non_trading_day_without_a_harvest_directory_is_not_refused(
    tmp_path: Path,
) -> None:
    """The weekend cron case: no session, so no harvest was expected."""
    assert (
        mod.main(
            [
                "--date",
                "2026-09-19",
                "--no-harvest",
                "--no-point-in-time",
                "--report-root",
                str(tmp_path),
            ]
        )
        == 0
    )


def test_report_root_override_keeps_the_configured_root_untouched(
    tmp_path: Path,
) -> None:
    """``--report-root`` redirects harvest AND sidecar away from reports/f9-gate1."""
    day_dir = tmp_path / DAY.isoformat()
    day_dir.mkdir(parents=True)
    healthy_producer(day_dir, candidates=0)

    assert (
        mod.main(
            [
                "--date",
                DAY.isoformat(),
                "--no-harvest",
                "--no-point-in-time",
                "--report-root",
                str(tmp_path),
            ]
        )
        == 1
    )
    sidecars = list(day_dir.glob("observation-completeness.*.json"))
    assert len(sidecars) == 1
    configured = mod.load_observation_config().report_root
    assert configured.resolve() != tmp_path.resolve()
    assert not list(
        (configured / DAY.isoformat()).glob("observation-completeness.*.json")
    )
