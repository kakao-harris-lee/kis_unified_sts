"""Tests for services/risk_filter/main.py — Phase 4 Task 11."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.risk_filter.main import (
    RiskFilterDaemon,
    _resolve_mode,
    _signal_from_stream_fields,
    _streams_for,
)
from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult
from shared.risk.layer import LayerResult, RiskFilterLayer
from shared.streaming.approval_gate import ApprovalGateConfig
from shared.streaming.approval_keys import approval_field_id, pending_approval_key
from shared.streaming.trading_state import TradingStateReader

CANDIDATE_STREAM = "signal.candidate.futures"
FINAL_STREAM = "signal.final.futures"
GROUP = "risk_filter"


def _signal(direction: str = "long") -> Signal:
    return Signal(
        setup_type="A_gap_reversion",
        direction=direction,
        symbol="A05603",
        entry_price=331.20,
        stop_loss=330.50,
        take_profit=332.50,
        confidence=0.85,
        valid_until=datetime(2026, 4, 28, 6, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 28, 5, 0, tzinfo=UTC),
    )


class _StubLayer(RiskFilterLayer):
    """Test-only RiskFilterLayer that returns a fixed LayerResult."""

    def __init__(self, result: LayerResult) -> None:
        super().__init__(filters=[])
        self._result = result

    def evaluate(self, signal, snapshot):  # type: ignore[override]  # noqa: ARG002
        return self._result


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(db=1)


@pytest.fixture
def signals_writer():
    return AsyncMock()


def _make_daemon(*, redis, signals_writer, layer, approval_gate_config=None):
    runtime_state = AsyncMock()
    runtime_state.snapshot = AsyncMock(return_value=AsyncMock())
    return RiskFilterDaemon(
        redis=redis,
        layer=layer,
        signals_writer=signals_writer,
        runtime_state=runtime_state,
        candidate_stream=CANDIDATE_STREAM,
        final_stream=FINAL_STREAM,
        consumer_group=GROUP,
        worker_id="test-worker",
        final_maxlen=1000,
        xread_block_ms=10,
        batch_size=10,
        approval_gate_config=approval_gate_config,
    )


async def _publish_candidate(redis, signal: Signal) -> None:
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-1"
    await redis.xadd(CANDIDATE_STREAM, fields)


@pytest.mark.asyncio
async def test_signal_passes_filter_publishes_to_final(redis, signals_writer):
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    sig = _signal("long")
    await _publish_candidate(redis, sig)

    # Run one batch then stop
    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    # Final stream got the entry
    entries = await redis.xrange(FINAL_STREAM)
    assert len(entries) == 1
    fields = entries[0][1]
    assert fields[b"setup_type"] == b"A_gap_reversion"
    assert fields[b"direction"] == b"long"
    # Signals-all row written
    signals_writer.enqueue.assert_awaited_once()
    kwargs = signals_writer.enqueue.call_args
    # First positional is the Signal, second is the LayerResult
    assert kwargs.args[0].setup_type == "A_gap_reversion"
    assert kwargs.kwargs["executed"] is True


@pytest.mark.asyncio
async def test_signal_rejected_writes_signals_all_no_final(redis, signals_writer):
    layer = _StubLayer(
        LayerResult(passed=False, skip_reason="trading_hours", size_multiplier=0.0)
    )
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    # No entry in final stream
    final_entries = await redis.xrange(FINAL_STREAM)
    assert final_entries == []
    # signals_all still gets the row (rejected, executed=False)
    signals_writer.enqueue.assert_awaited_once()
    assert signals_writer.enqueue.call_args.kwargs["executed"] is False


@pytest.mark.asyncio
async def test_final_stream_carries_size_multiplier_and_signal_id(
    redis, signals_writer
):
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=0.5))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    fields = (await redis.xrange(FINAL_STREAM))[0][1]
    assert float(fields[b"size_multiplier"]) == 0.5
    assert fields[b"signal_id"] == b"sig-1"


@pytest.mark.asyncio
async def test_final_stream_has_ttl(redis, signals_writer):
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    ttl = await redis.ttl(FINAL_STREAM)
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_xack_after_both_writes(redis, signals_writer):
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    pending = await redis.xpending(CANDIDATE_STREAM, GROUP)
    # Pending = 0 means all messages acked.
    if isinstance(pending, dict):
        assert int(pending.get("pending", 0)) == 0
    elif pending:
        assert int(pending[0]) == 0


# ---------------------------------------------------------------------------
# F-9 Gate 1b §2-C: ConcurrentPositionsFilter wired via
# _build_open_positions_count_provider, exercised end-to-end through the
# daemon (not the _StubLayer — this is the real RiskFilterLayer + real filter
# + real provider function, only the sync-Redis HLEN source is faked).
# ---------------------------------------------------------------------------


class _FakeSyncRedisForCount:
    """Stand-in for RedisClient.get_client(); only HLEN is exercised here."""

    def __init__(self, count: int) -> None:
        self._count = count

    def hlen(self, key: str) -> int:  # noqa: ARG002
        return self._count


def _concurrent_positions_layer(*, count: int, cap: int) -> RiskFilterLayer:
    from services.risk_filter.main import _build_open_positions_count_provider
    from shared.risk.filters.concurrent_positions import ConcurrentPositionsFilter

    provider = _build_open_positions_count_provider(
        _FakeSyncRedisForCount(count), "futures:monitor:positions"
    )
    return RiskFilterLayer(
        filters=[
            ConcurrentPositionsFilter(
                asset_class="futures",
                open_positions_count_provider=provider,
                max_positions_per_asset=cap,
            )
        ]
    )


@pytest.mark.asyncio
async def test_concurrent_positions_provider_rejects_at_cap(redis, signals_writer):
    """count >= cap: the filter rejects and no signal reaches the final stream."""
    layer = _concurrent_positions_layer(count=2, cap=2)
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    final_entries = await redis.xrange(FINAL_STREAM)
    assert final_entries == []
    signals_writer.enqueue.assert_awaited_once()
    kwargs = signals_writer.enqueue.call_args
    assert kwargs.kwargs["executed"] is False
    layer_result = kwargs.args[1]
    assert layer_result.skip_reason == "max_positions_per_asset"


@pytest.mark.asyncio
async def test_concurrent_positions_provider_passes_below_cap(redis, signals_writer):
    """count < cap: the filter passes and the signal reaches the final stream."""
    layer = _concurrent_positions_layer(count=1, cap=2)
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    final_entries = await redis.xrange(FINAL_STREAM)
    assert len(final_entries) == 1
    signals_writer.enqueue.assert_awaited_once()
    assert signals_writer.enqueue.call_args.kwargs["executed"] is True


@pytest.mark.asyncio
async def test_concurrent_positions_provider_fails_closed_on_redis_error(
    redis, signals_writer
):
    """A Redis HLEN error must reject (fail-closed), not silently pass."""
    from services.risk_filter.main import _build_open_positions_count_provider
    from shared.risk.filters.concurrent_positions import ConcurrentPositionsFilter

    class _RaisingSyncRedis:
        def hlen(self, key: str) -> int:  # noqa: ARG002
            raise RuntimeError("redis down")

    provider = _build_open_positions_count_provider(
        _RaisingSyncRedis(), "futures:monitor:positions"
    )
    layer = RiskFilterLayer(
        filters=[
            ConcurrentPositionsFilter(
                asset_class="futures",
                open_positions_count_provider=provider,
                max_positions_per_asset=2,
            )
        ]
    )
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate(redis, _signal("long"))

    import asyncio

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    final_entries = await redis.xrange(FINAL_STREAM)
    assert final_entries == []
    assert signals_writer.enqueue.call_args.kwargs["executed"] is False


@pytest.mark.asyncio
async def test_signal_id_threaded_to_signals_writer(redis, signals_writer):
    """signals_all rows must use the stream signal_id, not a fresh uuid (spec §5.3)."""
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    sig = _signal("long")
    fields = sig.to_stream_dict()
    fields["signal_id"] = "sig-tracing-99"
    await redis.xadd(CANDIDATE_STREAM, fields)

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    import asyncio

    await asyncio.gather(daemon.run(), _stop_after())

    kwargs = signals_writer.enqueue.call_args.kwargs
    assert kwargs["signal_id"] == "sig-tracing-99"


def test_signal_from_stream_fields_round_trip():
    sig = _signal("short")
    fields = sig.to_stream_dict()
    fields["signal_id"] = "sig-99"
    encoded = {k.encode(): v.encode() for k, v in fields.items()}

    parsed_id, parsed = _signal_from_stream_fields(encoded)
    assert parsed_id == "sig-99"
    assert parsed.setup_type == "A_gap_reversion"
    assert parsed.direction == "short"
    assert parsed.entry_price == 331.20
    assert parsed.confidence == 0.85


def test_resolve_mode_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_RISK_FILTER", raising=False)
    assert _resolve_mode() == "off"


def test_resolve_mode_shadow_and_live(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_RISK_FILTER", "shadow")
    assert _resolve_mode() == "shadow"
    monkeypatch.setenv("FUTURES_RISK_FILTER", "LIVE")
    assert _resolve_mode() == "live"


def test_resolve_mode_unknown_falls_through_to_off(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_RISK_FILTER", "garbage")
    assert _resolve_mode() == "off"


def test_streams_for_shadow_and_live(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_CANDIDATE_STREAM", raising=False)
    monkeypatch.delenv("FUTURES_FINAL_STREAM", raising=False)
    assert _streams_for("shadow") == (
        "signal.candidate.futures.shadow",
        "signal.final.futures.shadow",
    )
    assert _streams_for("live") == (
        "signal.candidate.futures",
        "signal.final.futures",
    )


def test_streams_for_env_override(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_CANDIDATE_STREAM", "custom.candidate")
    monkeypatch.setenv("FUTURES_FINAL_STREAM", "custom.final")
    assert _streams_for("live") == ("custom.candidate", "custom.final")


# ---------------------------------------------------------------------------
# Market-risk gate composition (Phase 2D, roadmap §5.2 track C)
# ---------------------------------------------------------------------------


async def _publish_candidate_with_gate(
    redis, signal: Signal, *, entry_size_factor: str, gate_trace: str
) -> None:
    fields = signal.to_stream_dict()
    fields["signal_id"] = "sig-1"
    fields["entry_size_factor"] = entry_size_factor
    fields["market_risk_gate"] = gate_trace
    await redis.xadd(CANDIDATE_STREAM, fields)


@pytest.mark.asyncio
async def test_final_stream_composes_upstream_entry_size_factor(redis, signals_writer):
    """Multiplicative stacking: gate 0.7 x layer 0.5 -> 0.35 on the final
    stream. The layer factor stands in for any other sizing lane (e.g.
    consecutive-loss or a future LLM size factor) — composition is
    multiplication-only, so factors accumulate conservatively."""
    import asyncio
    import json

    gate_trace = json.dumps({"mode": "enforce", "band": "ELEVATED"})
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=0.5))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    await _publish_candidate_with_gate(
        redis, _signal("long"), entry_size_factor="0.7", gate_trace=gate_trace
    )

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    fields = (await redis.xrange(FINAL_STREAM))[0][1]
    assert float(fields[b"size_multiplier"]) == pytest.approx(0.35)
    # Fixed contract: the market_risk_gate trace is forwarded unchanged for
    # the /signals trace lane.
    assert json.loads(fields[b"market_risk_gate"].decode()) == {
        "mode": "enforce",
        "band": "ELEVATED",
    }


@pytest.mark.asyncio
async def test_final_stream_forwards_futures_context_trace(redis, signals_writer):
    """Phase C: the futures_context trace is forwarded verbatim to the final
    stream (fixed key contract for the /signals trace lane). Without this the
    futures_monitor serializers passthrough would always see None."""
    import asyncio
    import json

    context_trace = json.dumps(
        {"roll_state": "pre_roll", "basis_regime": "contango", "degraded": False}
    )
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)

    fields = _signal("long").to_stream_dict()
    fields["signal_id"] = "sig-ctx"
    fields["futures_context"] = context_trace
    await redis.xadd(CANDIDATE_STREAM, fields)

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    out = (await redis.xrange(FINAL_STREAM))[0][1]
    assert json.loads(out[b"futures_context"].decode()) == {
        "roll_state": "pre_roll",
        "basis_regime": "contango",
        "degraded": False,
    }


@pytest.mark.asyncio
async def test_missing_or_invalid_entry_size_factor_is_neutral(redis, signals_writer):
    """Legacy candidates (no gate fields) and malformed factors keep the
    layer-only size_multiplier."""
    import asyncio

    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=0.5))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)

    # Legacy candidate — no entry_size_factor / market_risk_gate fields.
    await _publish_candidate(redis, _signal("long"))
    # Malformed factor (out of range) — must fail open to neutral 1.0.
    fields = _signal("short").to_stream_dict()
    fields["signal_id"] = "sig-2"
    fields["entry_size_factor"] = "0.0"
    await redis.xadd(CANDIDATE_STREAM, fields)

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(FINAL_STREAM)
    assert len(entries) == 2
    for _msg_id, out in entries:
        assert float(out[b"size_multiplier"]) == pytest.approx(0.5)
        assert b"market_risk_gate" not in out
        assert b"futures_context" not in out


# ---------------------------------------------------------------------------
# Telegram interactive-alerts approval gate (Method A) — 2026-07-07 design doc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gated_signal_recorded_pending_no_final(redis, signals_writer):
    """A signal whose strategy matches the gate is held pending, not XADDed."""
    import asyncio

    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    gate_config = ApprovalGateConfig(
        enabled=True, gated_strategies=["A_gap_reversion"], gated_symbols=[]
    )
    daemon = _make_daemon(
        redis=redis,
        signals_writer=signals_writer,
        layer=layer,
        approval_gate_config=gate_config,
    )
    await _publish_candidate(redis, _signal("long"))

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    # No entry reached the final stream.
    assert await redis.xrange(FINAL_STREAM) == []
    # Pending hash holds the full stream-dict, keyed by "{asset}:{signal_id}".
    key = pending_approval_key("futures")
    field = approval_field_id("futures", "sig-1")
    raw = await redis.hget(key, field)
    assert raw is not None
    stored = json.loads(raw)
    assert stored["setup_type"] == "A_gap_reversion"
    assert stored["signal_id"] == "sig-1"
    # TTL applied per config.pending_ttl_seconds.
    ttl = await redis.ttl(key)
    assert 0 < ttl <= gate_config.pending_ttl_seconds


@pytest.mark.asyncio
async def test_non_gated_signal_flows_to_final_no_pending(redis, signals_writer):
    """A signal that does not match the (enabled) gate flows through unchanged."""
    import asyncio

    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    gate_config = ApprovalGateConfig(
        enabled=True, gated_strategies=["some_other_strategy"], gated_symbols=[]
    )
    daemon = _make_daemon(
        redis=redis,
        signals_writer=signals_writer,
        layer=layer,
        approval_gate_config=gate_config,
    )
    await _publish_candidate(redis, _signal("long"))

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(FINAL_STREAM)
    assert len(entries) == 1
    key = pending_approval_key("futures")
    assert await redis.hlen(key) == 0


@pytest.mark.asyncio
async def test_gate_disabled_flows_to_final_no_pending(redis, signals_writer):
    """Gate disabled (default) — behavior identical to today even if the
    strategy/symbol lists would otherwise match."""
    import asyncio

    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    gate_config = ApprovalGateConfig(
        enabled=False, gated_strategies=["A_gap_reversion"], gated_symbols=[]
    )
    daemon = _make_daemon(
        redis=redis,
        signals_writer=signals_writer,
        layer=layer,
        approval_gate_config=gate_config,
    )
    await _publish_candidate(redis, _signal("long"))

    async def _stop_after():
        await asyncio.sleep(0.05)
        await daemon.stop()

    await asyncio.gather(daemon.run(), _stop_after())

    entries = await redis.xrange(FINAL_STREAM)
    assert len(entries) == 1
    key = pending_approval_key("futures")
    assert await redis.hlen(key) == 0


def test_daemon_defaults_to_inert_approval_gate_config(redis, signals_writer):
    """No approval_gate_config passed -> defaults to a fully-inert config."""
    layer = _StubLayer(LayerResult(passed=True, skip_reason=None, size_multiplier=1.0))
    daemon = _make_daemon(redis=redis, signals_writer=signals_writer, layer=layer)
    assert daemon.approval_gate_config.enabled is False


# ---------------------------------------------------------------------------
# P5-3: LeverageFilter provider wiring (_build_leverage_wiring)
# ---------------------------------------------------------------------------


def test_build_leverage_wiring_disabled_returns_none() -> None:
    """Default (leverage.enabled=False): no provider/specs wired, no config load
    — the disabled path is behaviour-0."""
    from types import SimpleNamespace

    from services.risk_filter.main import _build_leverage_wiring

    cfg = SimpleNamespace(leverage=SimpleNamespace(enabled=False, mode="shadow"))
    assert _build_leverage_wiring(cfg) == (None, None)


def test_build_leverage_wiring_no_leverage_attr_returns_none() -> None:
    """A config object with no ``leverage`` attribute (defensive) → (None, None)."""
    from types import SimpleNamespace

    from services.risk_filter.main import _build_leverage_wiring

    assert _build_leverage_wiring(SimpleNamespace()) == (None, None)


def test_build_leverage_wiring_enabled_wires_provider(monkeypatch) -> None:
    """enabled → reuses the margin read-model sources: TradingStateReader for
    positions + FuturesMarginConfig equity + build_product_specs multiplier map.
    The provider yields the {positions, equity_krw} snapshot the filter reads."""
    from types import SimpleNamespace

    import shared.streaming.trading_state as ts
    from services.risk_filter.main import _build_leverage_wiring

    legs = [{"code": "A05603", "quantity": 2, "current_price": 300.0}]
    monkeypatch.setattr(
        ts.TradingStateReader, "get_positions", lambda self: legs, raising=True
    )
    cfg = SimpleNamespace(leverage=SimpleNamespace(enabled=True, mode="shadow"))
    provider, specs = _build_leverage_wiring(cfg)

    assert provider is not None
    # Futures multiplier map is non-empty (execution.yaml + margin.yaml merge).
    assert specs
    snap = provider()
    assert snap is not None
    assert snap["equity_krw"] > 0  # FuturesMarginConfig fallback equity
    assert list(snap["positions"]) == legs


def test_build_leverage_wiring_provider_fails_open_on_read_error(monkeypatch) -> None:
    """A raising positions read → provider returns None (never propagates)."""
    from types import SimpleNamespace

    import shared.streaming.trading_state as ts
    from services.risk_filter.main import _build_leverage_wiring

    def _boom(self):
        raise RuntimeError("redis down")

    monkeypatch.setattr(ts.TradingStateReader, "get_positions", _boom, raising=True)
    cfg = SimpleNamespace(leverage=SimpleNamespace(enabled=True, mode="enforce"))
    provider, _specs = _build_leverage_wiring(cfg)
    assert provider is not None
    assert provider() is None


# ---------------------------------------------------------------------------
# F-9 Gate 1 gap G3 (2026-09-10): shadow trading-state key isolation
#
# ``shared.streaming.trading_state._key`` reads TRADING_STATE_KEY_SUFFIX at CALL
# time, so a shadow-mode risk_filter that never sets it resolves
# ``trading:futures:positions`` — the monolithic orchestrator's book — as the
# LeverageFilter's position source.
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_state_suffix():
    """Save/restore TRADING_STATE_KEY_SUFFIX around a test.

    ``ensure_state_key_suffix`` writes ``os.environ`` directly (it has to — the
    daemon's own process env is the contract), which monkeypatch cannot undo.
    """
    import os

    before = os.environ.get("TRADING_STATE_KEY_SUFFIX")
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
        else:
            os.environ["TRADING_STATE_KEY_SUFFIX"] = before


def test_shadow_mode_sets_state_key_suffix(restore_state_suffix) -> None:
    import os

    from services.risk_filter.main import ensure_state_key_suffix

    os.environ.pop("TRADING_STATE_KEY_SUFFIX", None)
    ensure_state_key_suffix("shadow", label="futures risk filter")

    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"
    assert (
        TradingStateReader("futures").positions_key
        == "trading:futures:positions:shadow"
    )


def test_shadow_mode_preserves_operator_pinned_suffix(restore_state_suffix) -> None:
    """An explicitly configured suffix wins — never clobbered by the default."""
    import os

    from services.risk_filter.main import ensure_state_key_suffix

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "gate1b"
    ensure_state_key_suffix("shadow", label="futures risk filter")

    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "gate1b"


def test_live_mode_clears_leaked_state_key_suffix(restore_state_suffix, caplog) -> None:
    """live must never read/write a shadow key — a leaked suffix is cleared."""
    import logging as _logging
    import os

    from services.risk_filter.main import ensure_state_key_suffix

    os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"
    with caplog.at_level(_logging.WARNING, logger="shared.streaming.trading_state"):
        ensure_state_key_suffix("live", label="futures risk filter")

    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == ""
    assert TradingStateReader("futures").positions_key == "trading:futures:positions"
    assert any(
        "clearing TRADING_STATE_KEY_SUFFIX for live futures risk filter"
        in r.getMessage()
        for r in caplog.records
    )


def test_suffix_bound_before_leverage_wiring() -> None:
    """Ordering pin: the suffix is bound BEFORE the leverage provider is built.

    ``_build_leverage_wiring`` constructs the ``TradingStateReader`` whose
    positions key the LeverageFilter reads; binding the suffix after it would
    reproduce G3 exactly.

    Compares STATEMENT positions in ``_build_and_run``'s body — the index of
    the statement containing each call, in ``body`` order — rather than raw
    line numbers from an unordered ``ast.walk``, so the assertion actually
    means "this statement executes first".
    """
    import ast
    import inspect

    from services.risk_filter import main as m

    func = ast.parse(inspect.getsource(m._build_and_run)).body[0]
    assert isinstance(func, ast.AsyncFunctionDef)

    targets = ("ensure_state_key_suffix", "_build_leverage_wiring")
    stmt_index: dict[str, int] = {}
    for i, stmt in enumerate(func.body):
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in targets
            ):
                stmt_index.setdefault(node.func.id, i)

    missing = [name for name in targets if name not in stmt_index]
    assert not missing, f"not called at the top level of _build_and_run: {missing}"
    assert stmt_index["ensure_state_key_suffix"] < stmt_index["_build_leverage_wiring"]


# ---------------------------------------------------------------------------
# F-9 Gate 1b gap G2 (2026-09-10): one verdict log line per candidate
# ---------------------------------------------------------------------------


def _stream_fields(signal: Signal, signal_id: str = "sig-1") -> dict[bytes, bytes]:
    fields = signal.to_stream_dict()
    fields["signal_id"] = signal_id
    return {k.encode(): str(v).encode() for k, v in fields.items()}


def _verdict_line(caplog) -> str:
    lines = [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("risk_filter verdict=")
    ]
    assert len(lines) == 1, f"expected exactly one verdict line, got {lines}"
    return lines[0]


@pytest.mark.asyncio
async def test_verdict_log_passed(redis, signals_writer, caplog) -> None:
    import logging as _logging

    result = LayerResult(
        passed=True,
        skip_reason=None,
        size_multiplier=0.5,
        filter_outcomes=[
            FilterResult(passed=True, filter_name="trading_hours"),
            FilterResult(
                passed=True, filter_name="consecutive_loss", size_multiplier=0.5
            ),
        ],
    )
    daemon = _make_daemon(
        redis=redis, signals_writer=signals_writer, layer=_StubLayer(result)
    )
    with caplog.at_level(_logging.INFO, logger="services.risk_filter.main"):
        assert await daemon.handle_message(b"1-1", _stream_fields(_signal("long")))

    line = _verdict_line(caplog)
    assert "verdict=passed" in line
    assert "signal_id=sig-1" in line
    assert "setup_type=A_gap_reversion" in line
    assert "direction=long" in line
    assert "symbol=A05603" in line
    assert "filter=-" in line
    assert "reason=-" in line
    assert "size_multiplier=0.500" in line
    assert "outcomes=trading_hours:pass,consecutive_loss:pass" in line


@pytest.mark.asyncio
async def test_verdict_log_rejected_names_filter_and_reason(
    redis, signals_writer, caplog
) -> None:
    """The G2 payload: WHICH filter rejected and WHY, for every rejection."""
    import logging as _logging

    result = LayerResult(
        passed=False,
        skip_reason="gross_leverage_exceeded",
        size_multiplier=1.0,
        filter_outcomes=[
            FilterResult(passed=True, filter_name="trading_hours"),
            FilterResult(
                passed=False,
                filter_name="leverage",
                skip_reason="gross_leverage_exceeded",
                size_multiplier=1.0,
            ),
        ],
    )
    daemon = _make_daemon(
        redis=redis, signals_writer=signals_writer, layer=_StubLayer(result)
    )
    with caplog.at_level(_logging.INFO, logger="services.risk_filter.main"):
        assert await daemon.handle_message(b"1-1", _stream_fields(_signal("short")))

    line = _verdict_line(caplog)
    assert "verdict=rejected" in line
    assert "direction=short" in line
    assert "filter=leverage" in line
    assert "reason=gross_leverage_exceeded" in line
    assert "outcomes=trading_hours:pass,leverage:fail" in line
    # No final-stream entry — the log is the only record of the rejection.
    assert await redis.xrange(FINAL_STREAM) == []


@pytest.mark.asyncio
async def test_verdict_log_without_outcomes_uses_placeholders(
    redis, signals_writer, caplog
) -> None:
    """Empty filter list (backtest / degraded layer) still logs one line."""
    import logging as _logging

    result = LayerResult(passed=False, skip_reason=None, size_multiplier=1.0)
    daemon = _make_daemon(
        redis=redis, signals_writer=signals_writer, layer=_StubLayer(result)
    )
    with caplog.at_level(_logging.INFO, logger="services.risk_filter.main"):
        assert await daemon.handle_message(b"1-1", _stream_fields(_signal("long")))

    line = _verdict_line(caplog)
    assert "verdict=rejected" in line
    assert "filter=- reason=-" in line
    assert "outcomes=-" in line
