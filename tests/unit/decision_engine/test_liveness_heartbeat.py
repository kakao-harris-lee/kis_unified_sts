"""Producer liveness heartbeat — ``event=decision_engine_alive``.

Design: ``docs/plans/2026-09-19-stream-consumer-liveness-and-monitor-dedup-design.md``
§2.1 / §4 row 2b.

The defect being closed: ``services/decision_engine`` had exactly one
proof-of-work line, the setup-evaluation INFO, and
``shared/strategy/entry/setup_eval_publisher.py`` throttles it by
``setup_eval_throttle_key(name, outcome, reason)`` — per STATE CHANGE, not per
cycle. An unchanged verdict therefore logs nothing however many cycles run, and
silence carries no information at any timescale. Measured on the 2026-09-18
harvest, a HEALTHY producer emitted 21 in-session lines across seven hours with
one 4h44m stretch emitting nothing, which is why ``config/f9_observation.yaml``
used to exempt the service from freshness scoring by name. This line is what
removed the premise for that exemption, and design step 3 lifted it: the
producer is scored like every other service now, on a ``liveness`` group that
reads ``event=decision_engine_alive``.

Every test here drives the loop for an exact number of cycles by binding the
stop to the context provider — the loop re-checks ``_stop`` at the top of each
turn, so "exactly N cycles" is a fact of construction rather than a wall-clock
race (CLAUDE.md test discipline: fixed wall-clock drains are time-fragile).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import fakeredis
import fakeredis.aioredis
import pytest
import yaml

import scripts.ops.f9_observation_harvest as harvest_mod
from services.decision_engine.config import DecisionEngineLivenessWiring
from services.decision_engine.main import DecisionEngineDaemon, _build_daemon
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup

REPO_ROOT = Path(__file__).resolve().parents[3]
DECISION_ENGINE_YAML = REPO_ROOT / "config" / "decision_engine.yaml"
F9_OBSERVATION_YAML = REPO_ROOT / "config" / "f9_observation.yaml"

CANDIDATE_STREAM = "signal.candidate.futures"
KST = timezone(timedelta(hours=9))
HEARTBEAT_EVENT = "event=decision_engine_alive"
DAEMON_LOGGER = "services.decision_engine.main"


def _ctx() -> MarketContext:
    return MarketContext(
        now=datetime(2026, 9, 18, 9, 30, tzinfo=KST),
        symbol="A05603",
        current_price=331.20,
        prev_close=331.00,
        today_open=331.10,
        vwap=331.15,
        atr_14=0.5,
        atr_90th_percentile=0.7,
        last_15min_high=331.30,
        last_15min_low=331.00,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
    )


class _NeverSetup(Setup):
    """A setup on the roster that always declines.

    Deliberately carries no ``REGISTRY_NAME``: ``_publish_setup_eval`` returns
    before its lazy ``setup_eval_publisher`` import (which pulls TA-Lib), so
    these tests exercise the loop without paying for the publisher.
    """

    CONFIG_CLASS = type("_StubConfig", (), {})

    def check(self, ctx):  # noqa: ARG002 — abstract signature requires ctx
        return None


class _FakeClock:
    """Stand-in for the ``time`` module as ``main.py`` uses it.

    ``main.py`` reaches the clock only through ``time.monotonic()`` (the two
    other ``ReasonLogThrottle`` call sites included), so a stub with that one
    attribute is a complete substitute — and it makes throttle boundaries exact
    instead of timing-dependent.
    """

    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _Driver:
    """Context provider that stops the daemon on its ``cycles``-th call.

    ``mode`` selects which of the loop's three paths the cycle takes:
    ``"context"`` (normal evaluation), ``"none"`` (provider suppressed the
    tick — what a weekend or a stale feed produces), ``"raise"`` (provider
    broken).
    """

    def __init__(
        self,
        cycles: int,
        *,
        mode: str = "context",
        clock: _FakeClock | None = None,
        clock_step: float = 0.0,
    ) -> None:
        self.cycles = cycles
        self.mode = mode
        self.calls = 0
        self._clock = clock
        self._clock_step = clock_step
        self._daemon: DecisionEngineDaemon | None = None

    def bind(self, daemon: DecisionEngineDaemon) -> DecisionEngineDaemon:
        self._daemon = daemon
        daemon.context_provider = self
        return daemon

    async def __call__(self) -> MarketContext | None:
        self.calls += 1
        if self._clock is not None:
            self._clock.advance(self._clock_step)
        assert self._daemon is not None, "bind() the driver before running"
        if self.calls >= self.cycles:
            await self._daemon.stop()
        if self.mode == "raise":
            raise RuntimeError("context provider down")
        if self.mode == "none":
            return None
        return _ctx()


async def _unbound_provider() -> MarketContext | None:  # pragma: no cover
    raise AssertionError("driver was not bound")


def _make_daemon(
    *,
    liveness_log_interval_seconds: float,
    setups: list[Any] | None = None,
) -> DecisionEngineDaemon:
    return DecisionEngineDaemon(
        redis=fakeredis.aioredis.FakeRedis(db=1),
        setups=[_NeverSetup()] if setups is None else setups,
        context_provider=_unbound_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.0,
        liveness_log_interval_seconds=liveness_log_interval_seconds,
    )


def _heartbeats(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.INFO and HEARTBEAT_EVENT in record.getMessage()
    ]


# ---------------------------------------------------------------------------
# Every path of the loop emits. A heartbeat that only fired on the fully
# evaluated path would go silent in exactly the degraded conditions where
# liveness is the open question.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_fires_on_the_normal_evaluation_path(caplog):
    daemon = _Driver(1).bind(_make_daemon(liveness_log_interval_seconds=3600.0))

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    lines = _heartbeats(caplog)
    assert len(lines) == 1
    assert "cycles=1" in lines[0]
    assert "context_cycles=1" in lines[0]
    assert "context_errors=0" in lines[0]
    # The roster size is carried so that an EMPTY roster — alive, evaluating
    # nothing, and otherwise invisible — is readable off the heartbeat.
    assert "setups=1" in lines[0]


@pytest.mark.asyncio
async def test_heartbeat_fires_when_context_is_none(caplog):
    daemon = _Driver(1, mode="none").bind(
        _make_daemon(liveness_log_interval_seconds=3600.0)
    )

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    lines = _heartbeats(caplog)
    assert len(lines) == 1
    assert "cycles=1" in lines[0]
    assert "context_cycles=0" in lines[0]
    # None is not an error: a closed or cold market is not a broken daemon.
    assert "context_errors=0" in lines[0]


@pytest.mark.asyncio
async def test_heartbeat_fires_when_context_provider_raises(caplog):
    daemon = _Driver(1, mode="raise").bind(
        _make_daemon(liveness_log_interval_seconds=3600.0)
    )

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    lines = _heartbeats(caplog)
    assert len(lines) == 1
    assert "cycles=1" in lines[0]
    assert "context_cycles=0" in lines[0]
    assert "context_errors=1" in lines[0]


@pytest.mark.asyncio
async def test_evaluating_and_blind_intervals_do_not_render_the_same(
    caplog, monkeypatch
):
    """The whole point of the counters.

    "The loop turned 4 times and had no context 4 times" and "turned 4 times,
    evaluated 4 times" are both alive, but only one of them is working.
    """
    clock = _FakeClock()
    monkeypatch.setattr("services.decision_engine.main.time", clock)
    rendered = {}
    for mode in ("context", "none"):
        clock.value = 0.0
        caplog.clear()
        daemon = _Driver(5, mode=mode, clock=clock, clock_step=3.0).bind(
            _make_daemon(liveness_log_interval_seconds=10.0)
        )
        with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
            await daemon.run()
        rendered[mode] = _heartbeats(caplog)[-1]

    assert "cycles=4 context_cycles=0" in rendered["none"]
    assert "cycles=4 context_cycles=4" in rendered["context"]
    assert rendered["none"] != rendered["context"]


# ---------------------------------------------------------------------------
# Throttling and the counts' window.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_is_not_emitted_more_than_once_per_interval(caplog):
    daemon = _Driver(25).bind(_make_daemon(liveness_log_interval_seconds=3600.0))

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    # 25 cycles, one interval: the startup line and nothing more.
    lines = _heartbeats(caplog)
    assert len(lines) == 1
    assert "cycles=1" in lines[0]


@pytest.mark.asyncio
async def test_counts_cover_only_the_cycles_since_the_previous_line(
    caplog, monkeypatch
):
    """Each line describes exactly the cycles it covers — counters reset on emit.

    Clock: the provider advances it 3s per cycle, the throttle interval is 10s.
    ``run()`` stamps the span start at t=0, so cycle 1 lands at t=3 and emits
    (a reason's first observation always logs); cycles 2-4 land at t=6/9/12,
    all within 10s of that emission; cycle 5 lands at t=15, 12s later, and
    emits the four cycles that accumulated.
    """
    clock = _FakeClock()
    monkeypatch.setattr("services.decision_engine.main.time", clock)
    daemon = _Driver(5, clock=clock, clock_step=3.0).bind(
        _make_daemon(liveness_log_interval_seconds=10.0)
    )

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    lines = _heartbeats(caplog)
    assert len(lines) == 2
    assert "cycles=1 context_cycles=1" in lines[0]
    assert "interval_seconds=3.0" in lines[0]
    assert "cycles=4 context_cycles=4" in lines[1]
    assert "interval_seconds=12.0" in lines[1]


@pytest.mark.asyncio
async def test_a_wedged_loop_reports_few_cycles_over_a_long_span(caplog, monkeypatch):
    """``interval_seconds`` is what makes a slow loop distinguishable from a fast one.

    A bare cycle count cannot: 2 cycles is healthy over 120s and a stall over
    600s.
    """
    clock = _FakeClock()
    monkeypatch.setattr("services.decision_engine.main.time", clock)
    daemon = _Driver(2, clock=clock, clock_step=300.0).bind(
        _make_daemon(liveness_log_interval_seconds=60.0)
    )

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    lines = _heartbeats(caplog)
    assert len(lines) == 2
    assert "cycles=1" in lines[1]
    assert "interval_seconds=300.0" in lines[1]


@pytest.mark.asyncio
async def test_heartbeat_survives_an_unexpected_error_inside_the_cycle(caplog):
    """The ``finally`` covers paths the three known ones do not.

    ``_publish_volatility_reference`` swallows its own failures today, so this
    injects a raise past every guard the cycle has. Liveness must be reported
    before the exception leaves the loop; otherwise the one failure mode that
    kills the daemon is also the one that reports nothing.
    """
    daemon = _Driver(1).bind(_make_daemon(liveness_log_interval_seconds=3600.0))

    async def _boom() -> None:
        raise RuntimeError("volatility publisher exploded")

    daemon._publish_volatility_reference = _boom  # type: ignore[method-assign]

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        with pytest.raises(RuntimeError, match="exploded"):
            await daemon.run()

    lines = _heartbeats(caplog)
    assert len(lines) == 1
    assert "cycles=1" in lines[0]
    assert "context_cycles=0" in lines[0]


@pytest.mark.asyncio
async def test_nothing_is_emitted_when_the_loop_never_turns(caplog):
    """Absence is the alarm. A daemon stopped before its first cycle says nothing."""
    daemon = _Driver(1).bind(_make_daemon(liveness_log_interval_seconds=3600.0))
    await daemon.stop()

    with caplog.at_level(logging.INFO, logger=DAEMON_LOGGER):
        await daemon.run()

    assert _heartbeats(caplog) == []


def test_reset_moves_the_span_stamp_and_the_counts_together():
    """The window is reset in one place, never half of it.

    A line whose counts predate its own ``interval_seconds`` would be a quiet
    lie of exactly the kind this heartbeat exists to stop shipping.
    """
    daemon = _make_daemon(liveness_log_interval_seconds=10.0)
    daemon._liveness_cycles = 7
    daemon._liveness_context_cycles = 4
    daemon._liveness_context_errors = 2

    daemon._reset_liveness_window(123.0)

    assert daemon._liveness_last_emit_monotonic == 123.0
    assert daemon._liveness_cycles == 0
    assert daemon._liveness_context_cycles == 0
    assert daemon._liveness_context_errors == 0


# ---------------------------------------------------------------------------
# Configuration (CLAUDE.md: configuration-driven only).
# ---------------------------------------------------------------------------


def test_default_interval():
    assert DecisionEngineLivenessWiring().log_interval_seconds == 60.0


def test_loads_the_shipped_yaml_section():
    config = DecisionEngineLivenessWiring.from_yaml(str(DECISION_ENGINE_YAML))
    assert config.log_interval_seconds == 60.0


def test_load_or_default_falls_back_when_yaml_absent(tmp_path):
    config = DecisionEngineLivenessWiring.load_or_default(str(tmp_path / "absent.yaml"))
    assert config.log_interval_seconds == 60.0


def test_load_or_default_reads_a_custom_interval(tmp_path):
    custom_yaml = tmp_path / "decision_engine.yaml"
    custom_yaml.write_text("liveness:\n  log_interval_seconds: 45.0\n")
    config = DecisionEngineLivenessWiring.load_or_default(str(custom_yaml))
    assert config.log_interval_seconds == 45.0


def test_build_daemon_carries_the_loaded_interval_into_the_throttle(monkeypatch):
    """The construction seam. Deleting the ctor argument must fail a test.

    Same guard as ``test_market_risk_gate_wiring.py``'s: that file records that
    dropping ``shadow_gate_log_interval_seconds=`` at the call site once left
    every test green.
    """
    monkeypatch.setattr(
        DecisionEngineLivenessWiring,
        "load_or_default",
        classmethod(lambda cls: cls(log_interval_seconds=77.0)),
    )

    async def _stub_context_provider() -> MarketContext | None:
        return None

    daemon = _build_daemon(
        redis_client=fakeredis.aioredis.FakeRedis(db=1),
        setups=[],
        context_provider=_stub_context_provider,
        candidate_stream=CANDIDATE_STREAM,
        market_risk_redis=fakeredis.FakeRedis(db=1, decode_responses=True),
        volatility_publisher=None,
    )

    assert daemon._liveness_log_throttle.interval_seconds == 77.0


# ---------------------------------------------------------------------------
# The cross-constraint. These two numbers live in different files and must know
# about each other: a heartbeat interval above the observation bound makes a
# HEALTHY producer read `stale_observation` the moment f9_observation.yaml
# stops exempting this service from freshness scoring (design §4 row 3).
# ---------------------------------------------------------------------------


def test_liveness_interval_stays_under_the_f9_observation_gap_bound():
    interval = DecisionEngineLivenessWiring.from_yaml(
        str(DECISION_ENGINE_YAML)
    ).log_interval_seconds
    bound = harvest_mod.load_observation_config(
        F9_OBSERVATION_YAML
    ).observation_max_gap_seconds

    assert interval < bound, (
        f"liveness.log_interval_seconds={interval} is not below "
        f"f9_observation.observation_max_gap_seconds={bound}: a healthy "
        "producer would read stale_observation once the freshness-scoring "
        "exemption is lifted"
    )


def test_heartbeat_line_is_not_swallowed_by_an_existing_f9_pattern():
    """The heartbeat must not be misread as blindness or as a setup evaluation.

    ``f9_observation.yaml`` checks ``blind`` BEFORE ``observed``, so a
    heartbeat caught by a blind regex would turn proof-of-life into evidence of
    the opposite. It matches neither group today: adding a ``liveness`` group
    is step 3 of the design and owns that file — this test only guarantees the
    line arrives uncommitted.
    """
    document = yaml.safe_load(F9_OBSERVATION_YAML.read_text(encoding="utf-8"))
    service = next(
        entry
        for entry in document["f9_observation"]["services"]
        if entry["name"] == "futures-decision-engine"
    )
    line = (
        "2026-09-18 09:30:00 KST INFO services.decision_engine.main "
        "event=decision_engine_alive cycles=60 context_cycles=60 "
        "context_errors=0 setups=3 interval_seconds=60.0"
    )

    for group in ("blind", "observed"):
        for pattern in service.get(group, []):
            assert not re.search(
                pattern, line
            ), f"heartbeat line matches the `{group}` pattern {pattern!r}"
    for counter in service.get("counters", {}).values():
        assert not re.search(counter["pattern"], line)
