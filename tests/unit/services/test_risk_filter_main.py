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
from shared.risk.layer import LayerResult, RiskFilterLayer
from shared.streaming.approval_gate import ApprovalGateConfig
from shared.streaming.approval_keys import approval_field_id, pending_approval_key

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
