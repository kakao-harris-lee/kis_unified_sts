"""DRY adapter-integration helper for RegimeGate (P2-③ T3).

All three adapters (SetupAEntryAdapter, SetupCEntryAdapter,
MeanReversionEntry) call apply_regime_gate() after their LLM-veto /
entry-decision logic but before returning the orchestrator Signal.

Single locus for:
  - Constructing a per-call RegimeGate from the per-strategy GateConfig
    + a fresh LiveVolInputs (Redis + CH).
  - Calling gate.allow() with (ts, asset, signal_direction).
  - Best-effort logging of every decision to regime_gate_decisions
    for weekly counterfactual review.

The gate_cfg=None branch is the no-op shortcut for strategies that
have not opted in (per-strategy YAML `regime_gate.enabled: false`).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any

from shared.strategy.gates.live_inputs import LiveVolInputs
from shared.strategy.gates.regime_gate import GateConfig, RegimeGate

logger = logging.getLogger(__name__)


def _futures_clickhouse_database() -> str:
    """Resolve the futures ClickHouse DB name.

    The system splits stocks (`market`, default) from futures (`kospi`,
    per CLICKHOUSE_FUTURES_DATABASE in .env). RegimeGate is a futures-
    only feature so audit rows + event_scores SELECTs must target the
    futures DB. Without this, the stock-DB default would land
    regime_gate_decisions rows in `market` while the counterfactual
    digest reads from `kospi` (silent feature dud).
    """
    return os.environ.get("CLICKHOUSE_FUTURES_DATABASE", "kospi")


def futures_clickhouse_client() -> Any | None:
    """Return a ClickHouseClient bound to the futures DB, or None on failure.

    Hot-path safe: any construction failure returns None (caller takes
    PERMISSIVE degrade branch — never propagates to trading hot path).
    """
    try:
        from shared.storage import get_clickhouse_client_wrapper

        return get_clickhouse_client_wrapper(_futures_clickhouse_database())
    except Exception as e:  # noqa: BLE001
        logger.debug("futures_clickhouse_client construction failed: %s", e)
        return None


def acquire_infra_clients() -> tuple[Any | None, Any | None]:
    """Acquire (redis, ch_sync_client) pair for the gate hot path.

    Returns (None, None) on any construction failure — caller takes
    the PERMISSIVE degrade branch (signal passes through). Hot-path
    safe: never raises.

    The CH client is bound to the futures DB
    (CLICKHOUSE_FUTURES_DATABASE, default ``kospi``) via
    :func:`futures_clickhouse_client` — symmetric with where
    audit rows land in :func:`_log_decision`.
    """
    try:
        from shared.streaming.client import RedisClient
        redis_cli = RedisClient.get_client()
    except Exception as e:  # noqa: BLE001
        logger.debug("acquire_infra_clients: redis acquire failed: %s", e)
        return None, None
    futures_cli = futures_clickhouse_client()
    if futures_cli is None:
        return None, None
    try:
        ch = futures_cli.get_sync_client()
    except Exception as e:  # noqa: BLE001
        logger.debug("acquire_infra_clients: ch sync_client failed: %s", e)
        return None, None
    return redis_cli, ch


def _log_decision(
    *,
    ts: dt.datetime,
    strategy: str,
    asset: str,
    signal_direction: str,
    allow: bool,
    reason: str,
    regime_pct: float,
) -> None:
    """Best-effort append to regime_gate_decisions. Any exception → swallowed."""
    ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
    row = {
        "ts": ts_n,
        "strategy": strategy,
        "asset": asset or "unknown",
        "signal_direction": signal_direction,
        "allow": bool(allow),
        "reason": reason or "",
        "regime_pct": regime_pct,
    }
    client = futures_clickhouse_client()
    if client is None:
        return
    client.insert_regime_gate_decisions([row])


def _extract_signal_direction(decision_signal: Any) -> str:
    """Pull signal_direction from metadata['signal_direction'] or .side, default 'long'."""
    md = getattr(decision_signal, "metadata", None) or {}
    if isinstance(md, dict) and md.get("signal_direction") in ("long", "short"):
        return md["signal_direction"]
    side = getattr(decision_signal, "side", None)
    if side in ("long", "short"):
        return side
    return "long"



def apply_regime_gate(
    *,
    gate_cfg: GateConfig | None,
    decision_signal: Any,
    context: Any,
    strategy_name: str,
    redis: Any,
    ch_client: Any,
) -> bool:
    """Apply the RegimeGate to a candidate signal. Returns True iff blocked.

    Args:
        gate_cfg: per-strategy GateConfig from regime_gate_from_yaml(),
            or None when the strategy has not opted in (no-op shortcut).
        decision_signal: the candidate signal (any object with metadata
            dict containing 'signal_direction', or a .side attribute).
        context: EntryContext (uses .timestamp and .market_data['code']).
        strategy_name: for the audit log.
        redis: Redis client (decode_responses=True).
        ch_client: ClickHouse sync client (for LiveVolInputs.events_within).

    Returns:
        True if the signal should be SUPPRESSED (blocked).
        False if allowed (or if gate_cfg is None).

    Decision logging is best-effort. Logging failure NEVER changes
    the gate verdict and is silently swallowed (§6 C2 contract).
    """
    if gate_cfg is None:
        return False

    # Defensive tz handling — mirror Setup A/C pattern
    ts = getattr(context, "timestamp", None)
    if ts is None:
        ts = dt.datetime.now(dt.UTC)

    md = getattr(context, "market_data", None) or {}
    asset = str(md.get("code", md.get("symbol", "")))
    direction = _extract_signal_direction(decision_signal)

    inputs = LiveVolInputs(redis=redis, ch_client=ch_client)
    gate = RegimeGate(config=gate_cfg, inputs=inputs)
    # RegimeGate.allow compares ts against naive datetimes from LiveVolInputs;
    # strip tz-info to avoid offset-naive vs offset-aware TypeError.
    ts_naive = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
    allow, reason, regime_pct = gate.allow(ts=ts_naive, asset=asset, signal_direction=direction)

    try:
        _log_decision(
            ts=ts, strategy=strategy_name, asset=asset,
            signal_direction=direction, allow=bool(allow), reason=reason,
            regime_pct=regime_pct,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "regime_gate_decisions append skipped (verdict preserved): %s",
            e, exc_info=True)

    return not allow
