"""StockRiskFilterDaemon.handle_message: pass -> final XADD; reject -> no XADD; poison-pill drop."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import fakeredis.aioredis
import pytest

from services.stock_risk_filter.main import StockRiskFilterDaemon
from shared.risk.config import StockRiskConfig
from shared.risk.layer import RiskFilterLayer
from shared.risk.runtime_state import RuntimeRiskState
from shared.streaming.approval_gate import ApprovalGateConfig
from shared.streaming.approval_keys import approval_field_id, pending_approval_key


def _encode(d: dict[str, str]) -> dict[bytes, bytes]:
    return {k.encode(): v.encode() for k, v in d.items()}


def _candidate(
    code: str = "005930", generated_at_ms: str | None = None
) -> dict[str, str]:
    if generated_at_ms is None:
        # 09:30 KST = 00:30 UTC — inside the 09:00-15:30 stock window.
        generated_at_ms = str(
            int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000)
        )
    return {
        "signal_id": "sig-1",
        "code": code,
        "name": "n",
        "strategy": "vr_composite",
        "direction": "long",
        "price": "71000.0",
        "quantity": "10",
        "confidence": "0.62",
        "generated_at_ms": generated_at_ms,
        "metadata_json": "{}",
    }


def _build_daemon(
    redis: fakeredis.aioredis.FakeRedis,
    layer: RiskFilterLayer | None = None,
    approval_gate_config: ApprovalGateConfig | None = None,
) -> StockRiskFilterDaemon:
    if layer is None:
        layer = RiskFilterLayer.from_config(
            config=StockRiskConfig(),
            trading_windows=["09:00-15:30"],
        )
    return StockRiskFilterDaemon(
        redis=redis,
        layer=layer,
        runtime_state=RuntimeRiskState(redis=redis, asset_class="stock"),
        candidate_stream="signal.candidate.stock.shadow",
        final_stream="signal.final.stock.shadow",
        consumer_group="stock_risk_filter",
        worker_id="test-worker",
        final_maxlen=1000,
        xread_block_ms=100,
        batch_size=10,
        approval_gate_config=approval_gate_config,
    )


@pytest.mark.asyncio
async def test_passing_candidate_emits_final_with_size_multiplier() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True
    entries = await redis.xrange("signal.final.stock.shadow")
    assert len(entries) == 1
    _id, fields = entries[0]
    assert fields[b"code"] == b"005930"
    assert b"size_multiplier" in fields
    assert b"filtered_at_ms" in fields


@pytest.mark.asyncio
async def test_outside_session_rejected_no_final() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    # 20:00 KST = 11:00 UTC — outside 09:00-15:30.
    off = str(int(datetime(2026, 6, 5, 11, 0, tzinfo=UTC).timestamp() * 1000))
    ack = await daemon.handle_message(b"1-0", _encode(_candidate(generated_at_ms=off)))
    assert ack is True  # rejected is audit-only consume
    entries = await redis.xrange("signal.final.stock.shadow")
    assert entries == []


@pytest.mark.asyncio
async def test_unparseable_is_poison_pill_drop() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", {b"price": b"not-a-float", b"code": b"x"})
    assert ack is True  # consumed, not retried
    assert await redis.xrange("signal.final.stock.shadow") == []


@pytest.mark.asyncio
async def test_filter_eval_raises_leaves_pending() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)

    class _Boom:
        def evaluate(self, *a: object, **k: object) -> object:  # noqa: ARG002
            raise RuntimeError("boom")

    daemon.layer = _Boom()  # type: ignore[assignment]
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is False  # NO XACK -> message stays pending for retry
    assert await redis.xrange("signal.final.stock.shadow") == []


@pytest.mark.asyncio
async def test_final_stream_has_ttl() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True
    ttl = await redis.ttl("signal.final.stock.shadow")
    assert 0 < ttl <= 86400


# ---------------------------------------------------------------------------
# Phase 5B — Track A/B correlation rules through the full daemon path
# ---------------------------------------------------------------------------


def _correlation_layer(
    ledger: object, positions: dict[str, float] | None
) -> RiskFilterLayer:
    return RiskFilterLayer.from_config(
        config=StockRiskConfig(),
        trading_windows=["09:00-15:30"],
        core_holdings_provider=lambda: ledger,
        stock_positions_provider=lambda: positions,
    )


def _semi_ledger():
    """Ledger holding one Track A semiconductor symbol + one watch candidate."""
    from shared.portfolio.core_holdings import (
        CoreCandidate,
        CoreHolding,
        CoreHoldings,
    )

    return CoreHoldings(
        holdings=[
            CoreHolding(
                symbol="005930",
                sector="semiconductor_equipment",
                kill_criteria=["k"],
            )
        ],
        candidates=[
            CoreCandidate(
                symbol="000660",
                sector="semiconductor_equipment",
                kill_criteria=["k"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_track_a_overlap_rejected_no_final() -> None:
    """Rule 1: a candidate already HELD in Track A is consumed without final."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, layer=_correlation_layer(_semi_ledger(), {}))
    ack = await daemon.handle_message(b"1-0", _encode(_candidate(code="005930")))
    assert ack is True  # rejected is audit-only consume
    assert await redis.xrange("signal.final.stock.shadow") == []


@pytest.mark.asyncio
async def test_sector_cap_rejected_no_final() -> None:
    """Rule 2: semiconductor share at the cap blocks a new semiconductor entry."""
    redis = fakeredis.aioredis.FakeRedis()
    # Track B already holds 005930 notional (semiconductor, 100%) — a new
    # semiconductor candidate (ledger watchlist symbol 000660) must be blocked.
    layer = _correlation_layer(_semi_ledger(), {"005930": 1_000_000.0})
    daemon = _build_daemon(redis, layer=layer)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate(code="000660")))
    assert ack is True
    assert await redis.xrange("signal.final.stock.shadow") == []


@pytest.mark.asyncio
async def test_empty_ledger_keeps_candidate_flowing() -> None:
    """Empty Track A ledger → both correlation rules are no-ops (final emitted)."""
    from shared.portfolio.core_holdings import CoreHoldings

    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis, layer=_correlation_layer(CoreHoldings(), {}))
    ack = await daemon.handle_message(b"1-0", _encode(_candidate(code="005930")))
    assert ack is True
    assert len(await redis.xrange("signal.final.stock.shadow")) == 1


# ---------------------------------------------------------------------------
# Telegram interactive-alerts approval gate (Method A) — 2026-07-07 design doc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gated_candidate_recorded_pending_no_final() -> None:
    """A candidate whose strategy matches the gate is held pending, not XADDed."""
    redis = fakeredis.aioredis.FakeRedis()
    gate_config = ApprovalGateConfig(
        enabled=True, gated_strategies=["vr_composite"], gated_symbols=[]
    )
    daemon = _build_daemon(redis, approval_gate_config=gate_config)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True  # consumed: held pending, not left for retry

    assert await redis.xrange("signal.final.stock.shadow") == []
    key = pending_approval_key("stock")
    field = approval_field_id("stock", "sig-1")
    raw = await redis.hget(key, field)
    assert raw is not None
    stored = json.loads(raw)
    assert stored["code"] == "005930"
    assert stored["signal_id"] == "sig-1"
    ttl = await redis.ttl(key)
    assert 0 < ttl <= gate_config.pending_ttl_seconds


@pytest.mark.asyncio
async def test_non_gated_candidate_flows_to_final_no_pending() -> None:
    """A candidate that does not match the (enabled) gate flows through unchanged."""
    redis = fakeredis.aioredis.FakeRedis()
    gate_config = ApprovalGateConfig(
        enabled=True, gated_strategies=["some_other_strategy"], gated_symbols=[]
    )
    daemon = _build_daemon(redis, approval_gate_config=gate_config)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True

    entries = await redis.xrange("signal.final.stock.shadow")
    assert len(entries) == 1
    key = pending_approval_key("stock")
    assert await redis.hlen(key) == 0


@pytest.mark.asyncio
async def test_gate_disabled_flows_to_final_no_pending() -> None:
    """Gate disabled (default) — behavior identical to today even if the
    strategy/symbol lists would otherwise match."""
    redis = fakeredis.aioredis.FakeRedis()
    gate_config = ApprovalGateConfig(
        enabled=False, gated_strategies=["vr_composite"], gated_symbols=[]
    )
    daemon = _build_daemon(redis, approval_gate_config=gate_config)
    ack = await daemon.handle_message(b"1-0", _encode(_candidate()))
    assert ack is True

    entries = await redis.xrange("signal.final.stock.shadow")
    assert len(entries) == 1
    key = pending_approval_key("stock")
    assert await redis.hlen(key) == 0


def test_daemon_defaults_to_inert_approval_gate_config() -> None:
    """No approval_gate_config passed -> defaults to a fully-inert config."""
    redis = fakeredis.aioredis.FakeRedis()
    daemon = _build_daemon(redis)
    assert daemon.approval_gate_config.enabled is False
