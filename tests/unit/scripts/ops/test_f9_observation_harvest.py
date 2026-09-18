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
    """Two innocuous lines making one harvest file span the whole session.

    Neither matches an ``observed`` or a ``blind`` pattern — they exist only so
    the file *testifies* to 08:00-15:55, the way a real uninterrupted harvest
    does. Coverage is a property of the file, not of the service's health, and
    every case that is not specifically about a coverage hole gets it.
    """
    return [
        f"2026-09-18 08:00:00,000 INFO __main__ {service} starting worker=w-1",
        f"2026-09-18 15:55:00,000 INFO __main__ {service} shutting down",
    ]


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


def healthy_producer(day_dir: Path, *, candidates: int = 0) -> None:
    """A decision engine that demonstrably evaluated across the session."""
    lines = [
        setup_eval(5, "setup_a_gap_reversion", "outside_time_window"),
        setup_eval(20, "setup_d_vwap_reversion", "not_extreme(z=0.4)"),
        setup_eval(300, "setup_d_vwap_reversion", "vol_below_gate(0.61)"),
        setup_eval(400, "setup_c_event_reaction", "no_event_in_window"),
    ]
    lines += [signal_published(30 + i, f"sig{i}") for i in range(candidates)]
    write_log(day_dir, "futures-decision-engine", lines)


def live_consumers(day_dir: Path, *, skip: tuple[str, ...] = ()) -> None:
    """Consumers that demonstrably handled a message, across a covered session."""
    evidence = {
        "futures-risk-filter": processed(
            31, "signal.candidate.futures.shadow", "risk_filter", "m1"
        ),
        "futures-order-router": processed(
            34, "signal.final.futures.shadow", "order_router", "f1"
        ),
        "futures-monitor": processed(
            36, "order.fill.futures.shadow", "futures_monitor", "o1"
        ),
    }
    for service, line in evidence.items():
        if service not in skip:
            write_log(day_dir, service, [line])


# ---------------------------------------------------------------------------
# 1. A healthy day
# ---------------------------------------------------------------------------


def test_healthy_day_is_complete_and_row_shows_the_consumed_count(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    healthy_producer(day_dir, candidates=3)
    write_log(
        day_dir,
        "futures-risk-filter",
        [
            processed(31, "signal.candidate.futures.shadow", "risk_filter", "m1"),
            verdict_line(31, "passed", "m1"),
            processed(32, "signal.candidate.futures.shadow", "risk_filter", "m2"),
            verdict_line(32, "rejected", "m2"),
            processed(33, "signal.candidate.futures.shadow", "risk_filter", "m3"),
            verdict_line(33, "rejected", "m3"),
        ],
    )
    write_log(
        day_dir,
        "futures-order-router",
        [processed(34, "signal.final.futures.shadow", "order_router", "f1")],
    )
    write_log(
        day_dir,
        "futures-monitor",
        [processed(36, "order.fill.futures.shadow", "futures_monitor", "o1")],
    )

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict == mod.VERDICT_COMPLETE
    assert statuses(result) == dict.fromkeys(SCORED, mod.STATUS_CONSUMED)
    assert all(s.covers_session for s in result.services if s.name in SCORED)
    assert "4/4 consumed" in row
    # candidates -> final -> fills, bare because the day is COMPLETE.
    assert "3 -> 1 -> 1" in row
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
    write_log(
        day_dir,
        "futures-risk-filter",
        [
            processed(31, "signal.candidate.futures.shadow", "risk_filter", "m1"),
            verdict_line(31, "passed", "m1"),
        ],
    )
    write_log(
        day_dir,
        "futures-order-router",
        [processed(34, "signal.final.futures.shadow", "order_router", "f1")],
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
    the producer published nothing. The exemption is gone: an idle consumer
    emits nothing at all (the one line that would prove liveness without
    traffic, ``consumer_group_already_present``, is DEBUG and the deployed
    monitors hardcode INFO), so a healthy idle consumer and one that died at
    the open leave byte-identical records. Calling that COMPLETE is the
    runbook's own INERT-GATE CAVEAT committed one level up.
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
    write_log(
        day_dir,
        "futures-risk-filter",
        [processed(31, "signal.candidate.futures.shadow", "risk_filter", "m1")],
    )
    write_log(
        day_dir,
        "futures-order-router",
        [processed(34, "signal.final.futures.shadow", "order_router", "f1")],
    )
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
    lines = [
        f"2026-09-17 17:54:{index % 60:02d},000 INFO __main__ "
        "[setup_d_vwap_reversion] no signal this cycle: outside_time_window"
        for index in range(tail - 2)
    ]
    lines += [
        setup_eval(20, "setup_d_vwap_reversion", "not_extreme(z=0.4)"),
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
    assert "no evidence 08:45-09:47, 09:47-15:45" in row


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

    assert result.verdict == mod.VERDICT_NO_SESSION
    assert "no session" in row
    assert "NOT OBSERVED" not in row
    assert "UNQUALIFIED" not in row
    assert "n/a" in row


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

    # One line at 15:25 covers one instant: the session is uncovered on BOTH
    # sides of it, and neither side is silence.
    assert monitor["covers_session"] is False
    assert monitor["uncovered_session_kst"] == [
        ["2026-09-18T08:45:00+09:00", "2026-09-18T15:25:00+09:00"],
        ["2026-09-18T15:25:00+09:00", "2026-09-18T15:45:00+09:00"],
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
