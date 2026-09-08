"""Tests for services/decision_engine/main.py — Phase 4 Task 10."""

import asyncio
import logging
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import fakeredis.aioredis
import pytest
import yaml

from services.decision_engine.main import (
    DecisionEngineDaemon,
    _build_setups,
    _candidate_stream_for,
    _setup_eval_key_suffix_for,
)
from shared.config.loader import ConfigLoader
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal
from shared.streaming.audit import decode_stream_id

CANDIDATE_STREAM = "signal.candidate.futures"


def _ctx(now=None) -> MarketContext:
    return MarketContext(
        now=now or datetime(2026, 4, 28, 9, 30, tzinfo=timezone(timedelta(hours=9))),
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


from datetime import timedelta  # noqa: E402


class _AlwaysSetup(Setup):
    CONFIG_CLASS = type("_StubConfig", (), {})

    def check(self, ctx):
        return Signal(
            setup_type="A_gap_reversion",
            direction="long",
            symbol=ctx.symbol,
            entry_price=ctx.current_price,
            stop_loss=ctx.current_price - 1.0,
            take_profit=ctx.current_price + 2.0,
            confidence=0.8,
            valid_until=ctx.now + timedelta(hours=1),
            generated_at=ctx.now,
        )


class _NeverSetup(Setup):
    CONFIG_CLASS = type("_StubConfig", (), {})

    def check(self, ctx):  # noqa: ARG002 — abstract signature requires ctx
        return None


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def context_provider():
    """Returns a fresh context on each tick."""
    contexts = [_ctx()]

    async def _provider():
        return contexts.pop(0) if contexts else None

    return _provider


def _make_daemon(*, redis, setups, context_provider):
    return DecisionEngineDaemon(
        redis=redis,
        setups=setups,
        context_provider=context_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
    )


@pytest.mark.asyncio
async def test_setup_fires_publishes_candidate(redis, context_provider):
    daemon = _make_daemon(
        redis=redis, setups=[_AlwaysSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) >= 1
    fields = entries[0][1]
    assert fields[b"setup_type"] == b"A_gap_reversion"
    assert fields[b"direction"] == b"long"
    assert b"signal_id" in fields


@pytest.mark.asyncio
async def test_no_setup_fires_no_candidate(redis, context_provider):
    daemon = _make_daemon(
        redis=redis, setups=[_NeverSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert entries == []


@pytest.mark.asyncio
async def test_candidate_stream_has_ttl(redis, context_provider):
    daemon = _make_daemon(
        redis=redis, setups=[_AlwaysSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    ttl = await redis.ttl(CANDIDATE_STREAM)
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_publish_logs_signal_published_audit_record(
    redis, context_provider, caplog
):
    daemon = _make_daemon(redis=redis, setups=[], context_provider=context_provider)
    signal = _AlwaysSetup().check(_ctx())

    with caplog.at_level(logging.INFO, logger="services.decision_engine.main"):
        await daemon._publish(signal)

    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) == 1
    msg_id = decode_stream_id(entries[0][0])
    signal_id = entries[0][1][b"signal_id"].decode()

    records = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO
        and "event=signal_published" in record.getMessage()
    ]
    assert len(records) == 1
    message = records[0].getMessage()
    assert f"stream={CANDIDATE_STREAM}" in message
    assert f"msg_id={msg_id}" in message
    assert f"signal_id={signal_id}" in message
    assert "setup_type=A_gap_reversion" in message
    assert "symbol=A05603" in message
    assert "direction=long" in message


@pytest.mark.asyncio
async def test_publish_attaches_futures_context_trace_when_wired(redis):
    import json

    import fakeredis

    sync = fakeredis.FakeStrictRedis(decode_responses=True)
    sync.hset(
        "futures:context:latest",
        mapping={
            "roll_state": "pre_roll",
            "days_to_expiry": "4",
            "new_entry_front_allowed": "true",
            "basis_regime": "contango",
            "foreign_flow_regime": "buy",
            "market_risk_band": "ELEVATED",
            "margin_risk_level": "watch",
            "margin_usage_pct": "0.5",
            "degraded": "false",
            "asof_ts": "2026-07-01T10:00:00",
        },
    )
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[],
        context_provider=lambda: None,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        futures_context_redis=sync,
    )
    await daemon._publish(_AlwaysSetup().check(_ctx()))

    entries = await redis.xrange(CANDIDATE_STREAM)
    trace = json.loads(entries[0][1][b"futures_context"].decode())
    assert trace["roll_state"] == "pre_roll"
    assert trace["days_to_expiry"] == 4
    assert trace["basis_regime"] == "contango"
    assert trace["margin_risk_level"] == "watch"
    assert trace["degraded"] is False


@pytest.mark.asyncio
async def test_publish_no_futures_context_field_when_unwired(redis, context_provider):
    daemon = _make_daemon(redis=redis, setups=[], context_provider=context_provider)
    await daemon._publish(_AlwaysSetup().check(_ctx()))
    entries = await redis.xrange(CANDIDATE_STREAM)
    assert b"futures_context" not in entries[0][1]


@pytest.mark.asyncio
async def test_publish_futures_context_missing_key_is_noop(redis):
    import fakeredis

    sync = fakeredis.FakeStrictRedis(decode_responses=True)  # empty — no key
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[],
        context_provider=lambda: None,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        futures_context_redis=sync,
    )
    await daemon._publish(_AlwaysSetup().check(_ctx()))
    entries = await redis.xrange(CANDIDATE_STREAM)
    assert b"futures_context" not in entries[0][1]


@pytest.mark.asyncio
async def test_publish_does_not_log_success_when_ttl_refresh_fails(
    redis, context_provider, caplog, monkeypatch
):
    daemon = _make_daemon(redis=redis, setups=[], context_provider=context_provider)
    signal = _AlwaysSetup().check(_ctx())

    async def fail_expire(*_args, **_kwargs):
        raise ConnectionError("expire failed")

    monkeypatch.setattr(redis, "expire", fail_expire)

    with caplog.at_level(logging.INFO, logger="services.decision_engine.main"):
        with pytest.raises(ConnectionError):
            await daemon._publish(signal)

    assert not any(
        "event=signal_published" in record.getMessage() for record in caplog.records
    )


@pytest.mark.asyncio
async def test_signal_id_is_stable_uuid_per_signal(redis, context_provider):
    """Each emitted signal gets a fresh UUID — not deterministic per ctx."""
    contexts = [_ctx(), _ctx(now=_ctx().now + timedelta(minutes=1))]

    async def _provider():
        return contexts.pop(0) if contexts else None

    daemon = _make_daemon(
        redis=redis, setups=[_AlwaysSetup()], context_provider=_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(CANDIDATE_STREAM)
    if len(entries) >= 2:
        assert entries[0][1][b"signal_id"] != entries[1][1][b"signal_id"]


@pytest.mark.asyncio
async def test_setup_exception_does_not_kill_daemon(redis, context_provider):
    class _RaisingSetup(Setup):
        CONFIG_CLASS = type("_StubConfig", (), {})

        def check(self, ctx):  # noqa: ARG002 — abstract signature requires ctx
            raise RuntimeError("test")

    contexts = [_ctx(), _ctx()]

    async def _provider():
        return contexts.pop(0) if contexts else None

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_RaisingSetup(), _AlwaysSetup()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    # Should not raise
    await asyncio.gather(daemon.run(), _stop_after())
    # And the AlwaysSetup still fired
    entries = await redis.xrange(CANDIDATE_STREAM)
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# Roster + parameters from config/strategies/futures/*.yaml (plan §3-A)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
SHIPPED_STRATEGIES_DIR = REPO_ROOT / "config" / "strategies" / "futures"


def _shipped_params(registry_name: str) -> dict:
    document = yaml.safe_load(
        (SHIPPED_STRATEGIES_DIR / f"{registry_name}.yaml").read_text(encoding="utf-8")
    )
    return document["strategy"]["entry"]["params"]


def _write_strategy(
    config_dir: Path, registry_name: str, *, enabled: bool, params: dict | None = None
) -> None:
    """Write a minimal futures strategy file the roster loader can read."""
    target = config_dir / "strategies" / "futures"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{registry_name}.yaml").write_text(
        yaml.safe_dump(
            {
                "strategy": {
                    "name": registry_name,
                    "asset_class": "futures",
                    "enabled": enabled,
                    "entry": {"type": registry_name, "params": params or {}},
                }
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def strategies_config_dir(tmp_path, monkeypatch):
    """A tmp config dir the roster loader (ConfigLoader) resolves against."""
    monkeypatch.setenv("KIS_CONFIG_DIR", str(tmp_path))
    ConfigLoader.set_config_dir(tmp_path)
    return tmp_path


def test_build_setups_loads_the_shipped_roster_and_parameters(monkeypatch):
    """Against the real config dir: roster + values come from the strategy YAML.

    The expected values are READ from the same YAML rather than hardcoded, so
    this test tracks an operator retune instead of blocking it; the point is
    that the daemon no longer runs Pydantic defaults (plan §0-2).
    """
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    setups = {setup.REGISTRY_NAME: setup for setup in _build_setups()}

    assert set(setups) == {
        "setup_a_gap_reversion",
        "setup_c_event_reaction",
        "setup_d_vwap_reversion",
    }
    a_params = _shipped_params("setup_a_gap_reversion")
    d_params = _shipped_params("setup_d_vwap_reversion")
    assert (
        setups["setup_a_gap_reversion"].config.stop_atr_mult
        == a_params["stop_atr_mult"]
    )
    assert (
        setups["setup_a_gap_reversion"].config.valid_minutes_max
        == a_params["valid_minutes_max"]
    )
    assert (
        setups["setup_d_vwap_reversion"].config.min_confidence
        == d_params["min_confidence"]
    )
    assert (
        setups["setup_d_vwap_reversion"].config.reversal_confirm_enabled
        == d_params["reversal_confirm_enabled"]
    )


def test_build_setups_honours_strategy_enabled(strategies_config_dir, monkeypatch):
    """``strategy.enabled`` is the roster switch — the same one the monolith reads."""
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    _write_strategy(strategies_config_dir, "setup_a_gap_reversion", enabled=False)
    _write_strategy(strategies_config_dir, "setup_c_event_reaction", enabled=True)
    _write_strategy(strategies_config_dir, "setup_d_vwap_reversion", enabled=True)

    names = [setup.REGISTRY_NAME for setup in _build_setups()]
    assert names == ["setup_c_event_reaction", "setup_d_vwap_reversion"]


def test_build_setups_drops_a_setup_whose_strategy_is_disabled(
    strategies_config_dir, monkeypatch
):
    """Rollback path: flipping Setup D's strategy.enabled off removes it."""
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    _write_strategy(strategies_config_dir, "setup_a_gap_reversion", enabled=True)
    _write_strategy(strategies_config_dir, "setup_c_event_reaction", enabled=True)
    _write_strategy(strategies_config_dir, "setup_d_vwap_reversion", enabled=False)

    names = [setup.REGISTRY_NAME for setup in _build_setups()]
    assert "setup_d_vwap_reversion" not in names
    assert names == ["setup_a_gap_reversion", "setup_c_event_reaction"]


def test_build_setups_reads_parameters_from_the_strategy_yaml(
    strategies_config_dir, monkeypatch
):
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    _write_strategy(strategies_config_dir, "setup_a_gap_reversion", enabled=False)
    _write_strategy(strategies_config_dir, "setup_c_event_reaction", enabled=False)
    _write_strategy(
        strategies_config_dir,
        "setup_d_vwap_reversion",
        enabled=True,
        params={
            "min_confidence": 0.42,
            "extreme_atr_mult": 2.75,
            # An adapter-only key the core config must ignore, not choke on.
            "short_blocked_regimes": ["BULL_STRONG"],
        },
    )

    (setup,) = _build_setups()
    assert setup.config.min_confidence == 0.42
    assert setup.config.extreme_atr_mult == 2.75


def test_build_setups_subset_env_narrows_the_daemon_roster(
    strategies_config_dir, monkeypatch
):
    """The daemon-only subset never touches the shared strategy.enabled switch."""
    for name in (
        "setup_a_gap_reversion",
        "setup_c_event_reaction",
        "setup_d_vwap_reversion",
    ):
        _write_strategy(strategies_config_dir, name, enabled=True)
    monkeypatch.setenv(
        "FUTURES_DECISION_ENGINE_SETUPS",
        " setup_d_vwap_reversion , setup_a_gap_reversion ",
    )

    names = [setup.REGISTRY_NAME for setup in _build_setups()]
    assert names == ["setup_a_gap_reversion", "setup_d_vwap_reversion"]


def test_build_setups_empty_subset_env_means_every_enabled_setup(
    strategies_config_dir, monkeypatch
):
    for name in (
        "setup_a_gap_reversion",
        "setup_c_event_reaction",
        "setup_d_vwap_reversion",
    ):
        _write_strategy(strategies_config_dir, name, enabled=True)
    monkeypatch.setenv("FUTURES_DECISION_ENGINE_SETUPS", "   ")

    assert len(_build_setups()) == 3


def test_build_setups_disables_a_setup_whose_file_is_missing(
    strategies_config_dir, monkeypatch, caplog
):
    """An unreadable strategy file disables THAT setup; the daemon still starts."""
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    _write_strategy(strategies_config_dir, "setup_a_gap_reversion", enabled=True)
    # C and D files are absent entirely.

    with caplog.at_level(logging.INFO):
        names = [setup.REGISTRY_NAME for setup in _build_setups()]

    assert names == ["setup_a_gap_reversion"]
    assert "setup_c_event_reaction" in caplog.text


def test_build_setups_logs_the_roster_and_each_parameter_summary(
    strategies_config_dir, monkeypatch, caplog
):
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    _write_strategy(strategies_config_dir, "setup_a_gap_reversion", enabled=True)
    _write_strategy(strategies_config_dir, "setup_c_event_reaction", enabled=False)
    _write_strategy(
        strategies_config_dir,
        "setup_d_vwap_reversion",
        enabled=True,
        params={"min_confidence": 0.42},
    )

    with caplog.at_level(logging.INFO):
        _build_setups()

    roster_lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("decision_engine setups:")
    ]
    assert len(roster_lines) == 1
    assert "setup_a_gap_reversion" in roster_lines[0]
    assert "setup_d_vwap_reversion" in roster_lines[0]
    assert "disabled: ['setup_c_event_reaction']" in roster_lines[0]

    param_lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("decision_engine setup ")
    ]
    assert len(param_lines) == 2
    assert any("min_confidence=0.42" in line for line in param_lines)


def test_build_setups_warns_about_unknown_subset_names(
    strategies_config_dir, monkeypatch, caplog
):
    _write_strategy(strategies_config_dir, "setup_d_vwap_reversion", enabled=True)
    monkeypatch.setenv(
        "FUTURES_DECISION_ENGINE_SETUPS", "setup_d_vwap_reversion,setup_z_typo"
    )

    with caplog.at_level(logging.WARNING):
        names = [setup.REGISTRY_NAME for setup in _build_setups()]

    assert names == ["setup_d_vwap_reversion"]
    assert "setup_z_typo" in caplog.text


# ---------------------------------------------------------------------------
# Setup-level evaluation observability (plan §3-D)
# ---------------------------------------------------------------------------
# Real reject-reason shapes emitted by the Setup cores. Every one of them
# embeds a live measurement, which is exactly why the throttle/dedup key must
# be structural (shared.risk.log_throttle.setup_eval_throttle_key).
_REAL_REJECT_REASONS = [
    "not_extreme(z=+0.42,need±1.8)",
    "vol_below_gate(0.85<0.9)",
    "outside_time_window(297m∉[10,60])",
]


class _NamedNeverSetup(_NeverSetup):
    REGISTRY_NAME = "setup_d_vwap_reversion"
    last_reject_reason = "not_extreme(z=+0.42,need±1.8)"


class _NamedAlwaysSetup(_AlwaysSetup):
    REGISTRY_NAME = "setup_a_gap_reversion"


class _VwapDependentSetup(_NeverSetup):
    """Stands in for Setup D: declares the vwap dependency and records calls."""

    REGISTRY_NAME = "setup_d_vwap_reversion"
    REQUIRES_VWAP = True

    def __init__(self) -> None:
        super().__init__()
        self.checked = 0

    def check(self, ctx: MarketContext) -> None:  # noqa: ARG002
        self.checked += 1
        return None


class _VwapIndependentSetup(_AlwaysSetup):
    """Stands in for Setup A/C: never reads vwap, must keep running."""

    REGISTRY_NAME = "setup_a_gap_reversion"
    REQUIRES_VWAP = False


@pytest.fixture
def eval_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Capture publish_setup_eval calls made by the daemon loop."""
    calls: list[tuple] = []

    def _record(name: str, outcome: str, reason: str, **kwargs: object) -> None:
        calls.append((name, outcome, reason, kwargs))

    monkeypatch.setattr(
        "shared.strategy.entry.setup_eval_publisher.publish_setup_eval", _record
    )
    return calls


@pytest.fixture
def clean_eval_state() -> Iterator[None]:
    """Isolate the publisher's process-global state and RESTORE it afterwards."""
    from shared.strategy.entry import setup_eval_publisher

    saved_log = dict(setup_eval_publisher._last_eval_log)
    saved_history = dict(setup_eval_publisher._history_state)
    setup_eval_publisher._last_eval_log.clear()
    setup_eval_publisher._history_state.clear()
    try:
        yield
    finally:
        setup_eval_publisher._last_eval_log.clear()
        setup_eval_publisher._last_eval_log.update(saved_log)
        setup_eval_publisher._history_state.clear()
        setup_eval_publisher._history_state.update(saved_history)


async def _run_briefly(daemon: DecisionEngineDaemon, seconds: float = 0.02) -> None:
    async def _stop_after() -> None:
        await asyncio.sleep(seconds)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())


@pytest.mark.asyncio
async def test_reject_publishes_the_setup_reject_reason(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    """ "0 candidates" must be distinguishable from "never evaluated"."""
    daemon = _make_daemon(
        redis=redis, setups=[_NamedNeverSetup()], context_provider=context_provider
    )
    await _run_briefly(daemon)

    assert eval_calls
    name, outcome, reason, kwargs = eval_calls[0]
    assert name == "setup_d_vwap_reversion"
    assert outcome == "reject"
    assert reason == "not_extreme(z=+0.42,need±1.8)"
    # The daemon's own sync Redis client is reused rather than a second one.
    assert kwargs["acquire_clients"]() == (None, None)


@pytest.mark.asyncio
async def test_reject_without_a_reason_falls_back_to_setup_rejected(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    class _Silent(_NeverSetup):
        REGISTRY_NAME = "setup_c_event_reaction"

    daemon = _make_daemon(
        redis=redis, setups=[_Silent()], context_provider=context_provider
    )
    await _run_briefly(daemon)
    assert eval_calls[0][:3] == ("setup_c_event_reaction", "reject", "setup_rejected")


@pytest.mark.asyncio
async def test_fired_publishes_the_signal_direction(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    daemon = _make_daemon(
        redis=redis, setups=[_NamedAlwaysSetup()], context_provider=context_provider
    )
    await _run_briefly(daemon)

    assert eval_calls[0][:3] == ("setup_a_gap_reversion", "fired", "long")
    # …and the candidate still reached the stream.
    assert len(await redis.xrange(CANDIDATE_STREAM)) >= 1


@pytest.mark.asyncio
async def test_setup_without_registry_name_publishes_nothing(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    """Test doubles / future setups without a registry name are skipped, not guessed."""
    daemon = _make_daemon(
        redis=redis, setups=[_NeverSetup()], context_provider=context_provider
    )
    await _run_briefly(daemon)
    assert eval_calls == []


@pytest.mark.asyncio
async def test_publish_failure_does_not_stop_the_candidate(
    redis, context_provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Observability must never affect signal emission."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(
        "shared.strategy.entry.setup_eval_publisher.publish_setup_eval", _boom
    )
    daemon = _make_daemon(
        redis=redis, setups=[_NamedAlwaysSetup()], context_provider=context_provider
    )
    await _run_briefly(daemon)
    assert len(await redis.xrange(CANDIDATE_STREAM)) >= 1


class _FlakySyncRedis:
    """Sync Redis whose writes fail while ``broken`` is set.

    Injected instead of monkeypatching ``publish_setup_eval`` itself: the
    publisher swallows Redis errors by contract, so patching the function away
    tested a path the daemon can never take and left the real failure reporting
    unexercised (it was silently DEBUG-only).
    """

    def __init__(self) -> None:
        self.broken = True
        self.hashes: dict[str, dict[str, str]] = {}

    def hset(self, key: str, field: str, value: str) -> None:
        if self.broken:
            raise ConnectionError("redis down")
        self.hashes.setdefault(key, {})[field] = value

    def expire(self, *_args: object, **_kwargs: object) -> None:
        if self.broken:
            raise ConnectionError("redis down")

    def rpush(self, *_args: object, **_kwargs: object) -> None:
        if self.broken:
            raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_redis_failure_warns_once_and_logs_one_recovery(
    redis, clean_eval_state, caplog
) -> None:
    """A real Redis outage must be reported once, and its recovery once.

    Drives the actual publisher (no monkeypatch of it) so the reporting path
    under test is the one production takes.
    """
    fake_sync = _FlakySyncRedis()
    ticks = 6
    contexts = [_ctx() for _ in range(ticks)]
    seen = 0

    async def _provider() -> MarketContext | None:
        nonlocal seen
        seen += 1
        # Heal midway so the recovery line is exercised too.
        if seen == 4:
            fake_sync.broken = False
        return contexts.pop(0) if contexts else None

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_NamedNeverSetup()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        market_risk_redis=fake_sync,
        setup_eval_key_suffix=":shadow",
    )
    with caplog.at_level(logging.INFO):
        await _run_briefly(daemon, seconds=0.12)

    warned = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "publish" in r.getMessage()
    ]
    assert len(warned) == 1, [r.getMessage() for r in warned]

    recovered = [r for r in caplog.records if "recover" in r.getMessage().lower()]
    assert len(recovered) == 1, [r.getMessage() for r in recovered]

    # …and the writes landed once Redis came back.
    assert fake_sync.hashes["trading:futures:setup_eval:shadow"]
    # The daemon also tracks it machine-readably (no log scraping needed).
    assert daemon._setup_eval_failure_state["setup_d_vwap_reversion"] is True


@pytest.mark.asyncio
async def test_redis_failure_does_not_stop_the_loop(
    redis, context_provider, clean_eval_state
) -> None:
    fake_sync = _FlakySyncRedis()
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_NamedAlwaysSetup()],
        context_provider=context_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        market_risk_redis=fake_sync,
        setup_eval_key_suffix=":shadow",
    )
    await _run_briefly(daemon)
    assert len(await redis.xrange(CANDIDATE_STREAM)) >= 1


@pytest.mark.asyncio
async def test_no_market_context_is_recorded_per_setup(
    redis, eval_calls: list[tuple]
) -> None:
    """A suppressed tick is an EVALUATION outcome, not silence."""

    async def _provider() -> MarketContext | None:
        return None

    daemon = _make_daemon(
        redis=redis,
        setups=[_NamedNeverSetup(), _NamedAlwaysSetup()],
        context_provider=_provider,
    )
    await _run_briefly(daemon)

    recorded = {(name, reason) for name, _outcome, reason, _kw in eval_calls}
    assert ("setup_d_vwap_reversion", "no_market_context") in recorded
    assert ("setup_a_gap_reversion", "no_market_context") in recorded


@pytest.mark.asyncio
async def test_setup_exception_is_recorded_as_an_evaluation(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    class _Raising(Setup):
        CONFIG_CLASS = type("_StubConfig", (), {})
        REGISTRY_NAME = "setup_c_event_reaction"

        def check(self, ctx: MarketContext) -> None:  # noqa: ARG002
            raise RuntimeError("boom")

    daemon = _make_daemon(
        redis=redis, setups=[_Raising()], context_provider=context_provider
    )
    await _run_briefly(daemon)
    assert eval_calls[0][:3] == ("setup_c_event_reaction", "reject", "setup_exception")


# ---------------------------------------------------------------------------
# VWAP availability gates only the setups that read it (review finding 3)
# ---------------------------------------------------------------------------


def _ctx_without_vwap() -> MarketContext:
    ctx = _ctx()
    return replace(ctx, vwap=0.0)


@pytest.mark.asyncio
async def test_missing_vwap_skips_only_the_vwap_dependent_setup(
    redis, eval_calls: list[tuple]
) -> None:
    """Setup A/C must keep trading when the session VWAP is not available yet."""
    contexts = [_ctx_without_vwap()]

    async def _provider() -> MarketContext | None:
        return contexts.pop(0) if contexts else None

    dependent = _VwapDependentSetup()
    daemon = _make_daemon(
        redis=redis,
        setups=[dependent, _VwapIndependentSetup()],
        context_provider=_provider,
    )
    await _run_briefly(daemon)

    assert dependent.checked == 0, "Setup D must not be evaluated against vwap=0"
    assert ("setup_d_vwap_reversion", "reject", "no_vwap") in [
        call[:3] for call in eval_calls
    ]
    # The vwap-independent setup ran and published its candidate.
    assert ("setup_a_gap_reversion", "fired", "long") in [
        call[:3] for call in eval_calls
    ]
    assert len(await redis.xrange(CANDIDATE_STREAM)) >= 1


@pytest.mark.asyncio
async def test_vwap_dependent_setup_runs_once_vwap_is_present(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    dependent = _VwapDependentSetup()
    daemon = _make_daemon(
        redis=redis, setups=[dependent], context_provider=context_provider
    )
    await _run_briefly(daemon)

    assert dependent.checked >= 1
    assert "no_vwap" not in [call[2] for call in eval_calls]


def test_setup_d_core_declares_the_vwap_dependency() -> None:
    """The flag must live on the real Setup D, not only on the test double."""
    from shared.decision.setups.event_reaction import SetupCEventReaction
    from shared.decision.setups.gap_reversion import SetupAGapReversion
    from shared.decision.setups.vwap_reversion import SetupDVWAPReversion

    assert SetupDVWAPReversion.REQUIRES_VWAP is True
    assert SetupAGapReversion.REQUIRES_VWAP is False
    assert SetupCEventReaction.REQUIRES_VWAP is False


# ---------------------------------------------------------------------------
# Log throttling + Redis key isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_reason_log_is_throttled_across_changing_measurements(
    redis, clean_eval_state, caplog
) -> None:
    """One cause = one log line, however much its embedded numbers move.

    The daemon sees a NEW reason string on every tick because the reason carries
    live measurements. Keying the throttle on the raw string would log every
    tick (and grow the throttle cache without bound), so the key is structural.
    """
    reasons = iter(
        [
            "not_extreme(z=+0.42,need±1.8)",
            "not_extreme(z=+0.91,need±1.8)",
            "not_extreme(z=+1.55,need±1.8)",
            "vol_below_gate(0.85<0.9)",
        ]
    )

    class _Cycling(_NeverSetup):
        REGISTRY_NAME = "setup_d_vwap_reversion"

        def check(self, ctx: MarketContext) -> None:  # noqa: ARG002
            self.last_reject_reason = next(reasons, "vol_below_gate(0.85<0.9)")
            return None

    contexts = [_ctx() for _ in range(4)]

    async def _provider() -> MarketContext | None:
        return contexts.pop(0) if contexts else None

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_Cycling()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        setup_eval_log_interval_seconds=300.0,
    )

    with caplog.at_level(logging.INFO):
        await _run_briefly(daemon, seconds=0.06)

    # Ignore the trailing no_market_context line the drained provider produces.
    logged = [
        r.getMessage()
        for r in caplog.records
        if "no signal this cycle" in r.getMessage()
        and "no_market_context" not in r.getMessage()
    ]
    # Two structural causes were seen (not_extreme, vol_below_gate) → two lines,
    # not one per tick and not one per distinct z value.
    kinds = {msg.split(": ", 1)[1].split("(", 1)[0] for msg in logged}
    assert kinds == {"not_extreme", "vol_below_gate"}, logged
    assert len(logged) == 2, logged


@pytest.mark.asyncio
async def test_throttled_ticks_still_publish_to_redis(
    redis, clean_eval_state, eval_calls: list[tuple]
) -> None:
    """Throttling silences the LOG only — Redis stays the durable record."""
    contexts = [_ctx(), _ctx(), _ctx()]

    async def _provider() -> MarketContext | None:
        return contexts.pop(0) if contexts else None

    daemon = _make_daemon(
        redis=redis, setups=[_NamedNeverSetup()], context_provider=_provider
    )
    await _run_briefly(daemon, seconds=0.05)

    same_reason = [c for c in eval_calls if c[2] == "not_extreme(z=+0.42,need±1.8)"]
    assert len(same_reason) >= 3, "every tick must still be published"


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("live", ""),
        ("shadow", ":shadow"),
        # Inert modes are suffixed too: only a live daemon may own the
        # orchestrator's keys, and off/unknown must never touch them.
        ("off", ":shadow"),
        ("", ":shadow"),
        ("typo", ":shadow"),
    ],
)
def test_only_live_mode_writes_the_unsuffixed_eval_keys(
    mode: str, expected: str
) -> None:
    assert _setup_eval_key_suffix_for(mode) == expected


def test_eval_key_suffix_uses_the_redis_key_convention_not_the_stream_one() -> None:
    """Redis KEYS take ``:shadow``; STREAMS take ``.shadow``. Different rules."""
    assert _setup_eval_key_suffix_for("shadow") == ":shadow"
    assert _candidate_stream_for("shadow").endswith(".shadow")


@pytest.mark.asyncio
async def test_daemon_passes_its_key_suffix_to_the_publisher(
    redis, context_provider, eval_calls: list[tuple]
) -> None:
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_NamedNeverSetup()],
        context_provider=context_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        setup_eval_key_suffix=":shadow",
    )
    await _run_briefly(daemon)
    assert eval_calls[0][3]["key_suffix"] == ":shadow"


@pytest.mark.asyncio
async def test_shadow_daemon_writes_only_the_shadow_keys(
    redis, context_provider, clean_eval_state
) -> None:
    """End-to-end through the REAL publisher against a fake sync Redis."""
    import fakeredis

    fake_sync = fakeredis.FakeStrictRedis(decode_responses=True)
    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_NamedNeverSetup()],
        context_provider=context_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        market_risk_redis=fake_sync,
        setup_eval_key_suffix=":shadow",
    )
    await _run_briefly(daemon)

    assert fake_sync.hget(
        "trading:futures:setup_eval:shadow", "setup_d_vwap_reversion"
    ), fake_sync.keys("*")
    # The orchestrator's key is untouched — that separation is what makes the
    # Gate 1 check able to attribute a row to the daemon.
    assert fake_sync.exists("trading:futures:setup_eval") == 0
    history = [k for k in fake_sync.keys("*") if "history" in k]
    assert history and all(":shadow:" in k for k in history), history


def test_setup_eval_log_interval_comes_from_its_own_yaml_section() -> None:
    """The interval is config-driven and NOT the market-risk gate's field."""
    from services.decision_engine.config import (
        DecisionEngineMarketRiskGateWiring,
        DecisionEngineSetupEvalWiring,
    )

    shipped = DecisionEngineSetupEvalWiring.from_yaml(
        str(REPO_ROOT / "config" / "decision_engine.yaml")
    )
    assert shipped.log_interval_seconds == 300.0
    # Distinct classes/sections, so retuning one cannot retune the other.
    assert DecisionEngineSetupEvalWiring._default_section == "setup_eval"
    assert DecisionEngineMarketRiskGateWiring._default_section == "market_risk_gate"


def test_build_daemon_wires_the_setup_eval_interval_and_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fakeredis
    import fakeredis.aioredis

    from services.decision_engine.config import DecisionEngineSetupEvalWiring
    from services.decision_engine.main import _build_daemon

    monkeypatch.setattr(
        DecisionEngineSetupEvalWiring,
        "load_or_default",
        classmethod(lambda cls: cls(log_interval_seconds=13.0)),
    )

    async def _provider() -> MarketContext | None:
        return None

    daemon = _build_daemon(
        redis_client=fakeredis.aioredis.FakeRedis(db=1),
        setups=[],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        market_risk_redis=fakeredis.FakeStrictRedis(decode_responses=True),
        volatility_publisher=None,
        setup_eval_key_suffix=":shadow",
    )
    assert daemon._setup_eval_log_throttle.interval_seconds == 13.0
    assert daemon.setup_eval_key_suffix == ":shadow"


# ---------------------------------------------------------------------------
# Roster edge cases (review findings 10)
# ---------------------------------------------------------------------------


def test_missing_enabled_key_means_enabled(
    strategies_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Matches ConfigLoader.load_all_strategies, and therefore the orchestrator.

    One strategy file must not read as "on" to trader-futures and "off" here.
    """
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    target = strategies_config_dir / "strategies" / "futures"
    target.mkdir(parents=True, exist_ok=True)
    (target / "setup_d_vwap_reversion.yaml").write_text(
        yaml.safe_dump(
            {
                "strategy": {
                    "name": "setup_d_vwap_reversion",
                    "asset_class": "futures",
                    # no `enabled` key at all
                    "entry": {"type": "setup_d_vwap_reversion", "params": {}},
                }
            }
        ),
        encoding="utf-8",
    )

    assert [s.REGISTRY_NAME for s in _build_setups()] == ["setup_d_vwap_reversion"]


def test_malformed_strategy_document_stays_disabled(
    strategies_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `strategy` mapping = no roster switch to read → stay off."""
    monkeypatch.delenv("FUTURES_DECISION_ENGINE_SETUPS", raising=False)
    target = strategies_config_dir / "strategies" / "futures"
    target.mkdir(parents=True, exist_ok=True)
    (target / "setup_d_vwap_reversion.yaml").write_text(
        "just: a scalar mapping with no strategy key\n", encoding="utf-8"
    )

    assert _build_setups() == []


def test_subset_env_that_names_nothing_falls_back_to_every_enabled_setup(
    strategies_config_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """`,` is a mis-edited env file, not a request for an empty roster."""
    for name in (
        "setup_a_gap_reversion",
        "setup_c_event_reaction",
        "setup_d_vwap_reversion",
    ):
        _write_strategy(strategies_config_dir, name, enabled=True)
    monkeypatch.setenv("FUTURES_DECISION_ENGINE_SETUPS", " , , ")

    with caplog.at_level(logging.WARNING):
        setups = _build_setups()

    assert len(setups) == 3
    assert "names no setup" in caplog.text


# ---------------------------------------------------------------------------
# Inert modes must not touch the orchestrator's keys (review finding 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_off_mode_publishes_no_evaluations(
    redis, eval_calls: list[tuple]
) -> None:
    """An inert daemon emits no candidates, so it must record no evaluations.

    It also must not WRITE: with only live unsuffixed, an inert daemon that
    published would be reaching for keys the orchestrator owns.
    """

    async def _provider() -> MarketContext | None:
        return None  # the inert stub's behaviour

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_NamedNeverSetup(), _NamedAlwaysSetup()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        setup_eval_enabled=False,
    )
    await _run_briefly(daemon, seconds=0.05)
    assert eval_calls == []


@pytest.mark.asyncio
async def test_disabled_eval_never_imports_the_publisher(redis) -> None:
    """The lazy import must not happen in an inert daemon.

    ``shared.strategy`` is a ~1.4 s eager package init; the whole point of the
    lazy import is that a daemon which never evaluates never pays for it.
    """
    import sys

    sentinel = object()
    module = sys.modules.pop("shared.strategy.entry.setup_eval_publisher", sentinel)

    async def _provider() -> MarketContext | None:
        return None

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_NamedNeverSetup()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        setup_eval_enabled=False,
    )
    try:
        await _run_briefly(daemon, seconds=0.03)
        assert "shared.strategy.entry.setup_eval_publisher" not in sys.modules
    finally:
        if module is not sentinel:
            sys.modules["shared.strategy.entry.setup_eval_publisher"] = module


def test_build_daemon_disables_eval_outside_producing_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wiring, not just the flag: off/unknown → disabled, shadow/live → on."""
    import fakeredis
    import fakeredis.aioredis

    from services.decision_engine.main import _build_daemon, _is_producing_mode

    async def _provider() -> MarketContext | None:
        return None

    for mode, expected in (
        ("off", False),
        ("typo", False),
        ("shadow", True),
        ("live", True),
    ):
        daemon = _build_daemon(
            redis_client=fakeredis.aioredis.FakeRedis(db=1),
            setups=[],
            context_provider=_provider,
            candidate_stream=CANDIDATE_STREAM,
            market_risk_redis=fakeredis.FakeStrictRedis(decode_responses=True),
            volatility_publisher=None,
            setup_eval_enabled=_is_producing_mode(mode),
        )
        assert daemon.setup_eval_enabled is expected, mode
