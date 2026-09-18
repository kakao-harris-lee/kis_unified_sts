"""Tests for scripts/ops/f9_observation_harvest.py — observation completeness.

Hermetic: every case is driven from fixture log files written into a tmp report
root. No Redis, no docker, no broker.

The two cases that matter most are ``test_blind_consumer_*`` (the 2026-09-17
reproduction) and ``test_quiet_market_*`` (a genuine quiet market). Under the
old ``Consumers`` column — a count of *running* consumers — those two days
rendered identically: "4" consumers and "0" signals. They must not.

The production ``config/f9_observation.yaml`` patterns are used as-is (only the
report root is redirected), so a typo in a real pattern fails these tests.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import scripts.ops.f9_observation_harvest as mod

DAY = date(2026, 9, 18)
SESSION_OPEN = datetime(2026, 9, 18, 8, 45, tzinfo=mod.KST)


@pytest.fixture
def config(tmp_path: Path) -> mod.ObservationConfig:
    """Production config with the harvest destination redirected to tmp."""
    return replace(mod.load_observation_config(), report_root=tmp_path)


@pytest.fixture
def day_dir(config: mod.ObservationConfig) -> Path:
    directory = config.report_root / DAY.isoformat()
    directory.mkdir(parents=True)
    return directory


def write_log(day_dir: Path, service: str, lines: list[str], stamp: str = "155535"):
    """Write one harvest file, one ``<asctime> <line>`` record per entry."""
    (day_dir / f"{service}.{stamp}.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


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


def observe(config: mod.ObservationConfig) -> mod.DayObservation:
    return mod.observe_day(config, DAY)


def row_of(config: mod.ObservationConfig, result: mod.DayObservation) -> str:
    return mod.render_row(result, config.row_counters)


def healthy_producer(day_dir: Path, *, candidates: int = 0) -> None:
    """A decision engine that demonstrably evaluated across the session."""
    lines = [
        setup_eval(5, "setup_a_gap_reversion", "outside_time_window"),
        setup_eval(20, "setup_d_vwap_reversion", "not_extreme(z=0.4)"),
        setup_eval(300, "setup_d_vwap_reversion", "vol_below_gate(0.61)"),
        setup_eval(400, "setup_c_event_reaction", "no_event_in_window"),
    ]
    lines += [signal_published(30 + i, f"sig{i}") for i in range(candidates)]
    write_log(day_dir, "futures-decision-engine", sorted(lines))


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
    assert {s.name: s.status for s in result.services if s.role != "reference"} == {
        "futures-decision-engine": mod.STATUS_CONSUMED,
        "futures-risk-filter": mod.STATUS_CONSUMED,
        "futures-order-router": mod.STATUS_CONSUMED,
        "futures-monitor": mod.STATUS_CONSUMED,
    }
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
    assert "futures-monitor BLIND" in row
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
    statuses = {s.name: s.status for s in result.services}
    assert statuses["futures-risk-filter"] == mod.STATUS_BLIND
    assert statuses["futures-order-router"] == mod.STATUS_BLIND
    assert result.verdict != mod.VERDICT_COMPLETE


def test_dead_observation_surface_reads_not_observed(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    for service in (
        "futures-decision-engine",
        "futures-risk-filter",
        "futures-order-router",
        "futures-monitor",
    ):
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
# 4. A genuine quiet market — evaluations happened, nothing qualified
# ---------------------------------------------------------------------------


def test_quiet_market_with_zero_candidates_is_complete_and_not_flagged(
    config: mod.ObservationConfig, day_dir: Path
) -> None:
    """The input test 2 used to render identically to. It must NOT be flagged."""
    healthy_producer(day_dir, candidates=0)
    # The downstream consumers logged nothing during the session because the
    # producer published nothing for them to consume.
    for service in ("futures-risk-filter", "futures-order-router", "futures-monitor"):
        write_log(day_dir, service, [])

    result = observe(config)
    row = row_of(config, result)

    assert result.verdict == mod.VERDICT_COMPLETE
    assert {s.name: s.status for s in result.services if s.role != "reference"} == {
        "futures-decision-engine": mod.STATUS_CONSUMED,
        "futures-risk-filter": mod.STATUS_IDLE_NO_TRAFFIC,
        "futures-order-router": mod.STATUS_IDLE_NO_TRAFFIC,
        "futures-monitor": mod.STATUS_IDLE_NO_TRAFFIC,
    }
    assert "0 -> 0 -> 0" in row
    assert "UNQUALIFIED" not in row
    assert "NOT COMPLETE" not in row
    assert "nothing was due" in row


def test_quiet_market_and_blind_day_do_not_render_alike(
    config: mod.ObservationConfig, tmp_path: Path
) -> None:
    """The regression this file exists for, stated as one comparison."""
    quiet_dir = tmp_path / "quiet" / DAY.isoformat()
    quiet_dir.mkdir(parents=True)
    healthy_producer(quiet_dir, candidates=0)
    quiet = mod.render_row(
        mod.observe_day(replace(config, report_root=tmp_path / "quiet"), DAY),
        config.row_counters,
    )

    blind_dir = tmp_path / "blind" / DAY.isoformat()
    blind_dir.mkdir(parents=True)
    write_log(
        blind_dir,
        "futures-monitor",
        [read_error(minute, "futures_monitor") for minute in range(0, 421)],
    )
    blind = mod.render_row(
        mod.observe_day(replace(config, report_root=tmp_path / "blind"), DAY),
        config.row_counters,
    )

    assert quiet != blind
    assert "0 -> 0 -> 0" in quiet and "0 -> 0 -> 0" in blind
    assert "UNQUALIFIED" not in quiet
    assert "UNQUALIFIED" in blind


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
    statuses = {s.name: s.status for s in result.services}
    assert statuses["futures-decision-engine"] == mod.STATUS_PARTIALLY_BLIND
    assert statuses["futures-risk-filter"] == mod.STATUS_NO_EVIDENCE
    assert result.verdict == mod.VERDICT_PARTIAL
    assert "NO EVIDENCE (could not observe)" in row_of(config, result)


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
# Window, de-duplication and harvest mechanics
# ---------------------------------------------------------------------------


def test_session_window_comes_from_market_schedule_yaml() -> None:
    opened, closed = mod.session_window(DAY)
    assert (opened.hour, opened.minute) == (8, 45)
    assert (closed.hour, closed.minute) == (15, 45)
    assert opened.tzinfo is mod.KST


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

    class _Result:
        returncode = 0
        stdout = b"2026-09-18 09:00:00,000 INFO x hello\n"
        stderr = b""

    def runner(command):
        calls.append(list(command))
        return _Result()

    written = mod.harvest_logs(config, DAY, stamp="153000", runner=runner)

    assert written["futures-monitor"].name == "futures-monitor.153000.log"
    assert written["futures-monitor"].read_text(encoding="utf-8").endswith("hello\n")
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
    assert sidecar["counters_qualified"] is False
    monitor = next(s for s in sidecar["services"] if s["name"] == "futures-monitor")
    assert monitor["status"] == mod.STATUS_BLIND
    assert monitor["blind_count"] == 2
    assert monitor["blind_windows_kst"]
    assert monitor["evidence_files"], "the verdict must be auditable from files"
