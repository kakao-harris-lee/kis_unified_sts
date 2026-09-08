"""Tests for services/decision_engine/main.py — Phase 4 Task 10."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import fakeredis.aioredis
import pytest
import yaml

from services.decision_engine.main import DecisionEngineDaemon, _build_setups
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


class _NamedNeverSetup(_NeverSetup):
    REGISTRY_NAME = "setup_d_vwap_reversion"
    last_reject_reason = "vwap_stretch_below_extreme"


class _NamedAlwaysSetup(_AlwaysSetup):
    REGISTRY_NAME = "setup_a_gap_reversion"


@pytest.fixture
def eval_calls(monkeypatch):
    """Capture publish_setup_eval calls made by the daemon loop."""
    calls: list[tuple] = []

    def _record(name, outcome, reason, **kwargs):
        calls.append((name, outcome, reason, kwargs))

    monkeypatch.setattr(
        "shared.strategy.entry.setup_eval_publisher.publish_setup_eval", _record
    )
    return calls


@pytest.mark.asyncio
async def test_reject_publishes_the_setup_reject_reason(
    redis, context_provider, eval_calls
):
    """ "0 candidates" must be distinguishable from "never evaluated"."""
    daemon = _make_daemon(
        redis=redis, setups=[_NamedNeverSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    assert eval_calls
    name, outcome, reason, kwargs = eval_calls[0]
    assert name == "setup_d_vwap_reversion"
    assert outcome == "reject"
    assert reason == "vwap_stretch_below_extreme"
    # The daemon's own sync Redis client is reused rather than a second one.
    assert kwargs["acquire_clients"]() == (None, None)


@pytest.mark.asyncio
async def test_reject_without_a_reason_falls_back_to_setup_rejected(
    redis, context_provider, eval_calls
):
    class _Silent(_NeverSetup):
        REGISTRY_NAME = "setup_c_event_reaction"

    daemon = _make_daemon(
        redis=redis, setups=[_Silent()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())
    assert eval_calls[0][:3] == (
        "setup_c_event_reaction",
        "reject",
        "setup_rejected",
    )


@pytest.mark.asyncio
async def test_fired_publishes_the_signal_direction(
    redis, context_provider, eval_calls
):
    daemon = _make_daemon(
        redis=redis, setups=[_NamedAlwaysSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    assert eval_calls[0][:3] == ("setup_a_gap_reversion", "fired", "long")
    # …and the candidate still reached the stream.
    assert len(await redis.xrange(CANDIDATE_STREAM)) >= 1


@pytest.mark.asyncio
async def test_setup_without_registry_name_publishes_nothing(
    redis, context_provider, eval_calls
):
    """Test doubles / future setups without a registry name are skipped, not guessed."""
    daemon = _make_daemon(
        redis=redis, setups=[_NeverSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())
    assert eval_calls == []


@pytest.mark.asyncio
async def test_publish_failure_does_not_stop_the_candidate(
    redis, context_provider, monkeypatch
):
    """Observability must never affect signal emission."""

    def _boom(*_args, **_kwargs):
        raise RuntimeError("redis down")

    monkeypatch.setattr(
        "shared.strategy.entry.setup_eval_publisher.publish_setup_eval", _boom
    )
    daemon = _make_daemon(
        redis=redis, setups=[_NamedAlwaysSetup()], context_provider=context_provider
    )

    async def _stop_after():
        await asyncio.sleep(0.02)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())
    assert len(await redis.xrange(CANDIDATE_STREAM)) >= 1


@pytest.mark.asyncio
async def test_reject_reason_log_is_throttled_per_setup_and_reason(redis, caplog):
    """A reason repeating every 60 s tick may log at most once per interval.

    Reasons alternate A → B → A so the publisher's own state-change gate would
    log all three; only the daemon's ReasonLogThrottle suppresses the repeat.
    """
    from shared.strategy.entry import setup_eval_publisher

    setup_eval_publisher._last_eval_log.clear()
    setup_eval_publisher._history_state.clear()

    reasons = iter(["reason_a", "reason_b", "reason_a"])

    class _Cycling(_NeverSetup):
        REGISTRY_NAME = "setup_d_vwap_reversion"

        def check(self, ctx):  # noqa: ARG002
            self.last_reject_reason = next(reasons, "reason_a")
            return None

    contexts = [_ctx(), _ctx(), _ctx()]

    async def _provider():
        return contexts.pop(0) if contexts else None

    daemon = DecisionEngineDaemon(
        redis=redis,
        setups=[_Cycling()],
        context_provider=_provider,
        candidate_stream=CANDIDATE_STREAM,
        candidate_maxlen=1000,
        tick_interval_seconds=0.001,
        shadow_gate_log_interval_seconds=300.0,
    )

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    with caplog.at_level(logging.INFO):
        await asyncio.gather(daemon.run(), _stop_after())

    logged = [
        record.getMessage()
        for record in caplog.records
        if "no signal this cycle" in record.getMessage()
    ]
    assert len(logged) == 2, logged
    assert any("reason_a" in line for line in logged)
    assert any("reason_b" in line for line in logged)
