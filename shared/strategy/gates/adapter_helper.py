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
from typing import Any

from shared.strategy.gates.live_inputs import LiveVolInputs
from shared.strategy.gates.regime_gate import GateConfig, RegimeGate

logger = logging.getLogger(__name__)


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
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig

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
    get_clickhouse_client(ClickHouseConfig.from_env()).insert_regime_gate_decisions([row])


def _extract_signal_direction(decision_signal: Any) -> str:
    """Pull signal_direction from metadata['signal_direction'] or .side, default 'long'."""
    md = getattr(decision_signal, "metadata", None) or {}
    if isinstance(md, dict) and md.get("signal_direction") in ("long", "short"):
        return md["signal_direction"]
    side = getattr(decision_signal, "side", None)
    if side in ("long", "short"):
        return side
    return "long"


def _extract_regime_pct_from_reason(reason: str) -> float:
    """Extract numeric regime_pct from reason string ('regime_percentile=X.X>max')."""
    if "regime_percentile=" not in reason:
        return 0.0
    try:
        return float(reason.split("regime_percentile=")[1].split(">")[0])
    except (IndexError, ValueError):
        return 0.0


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
    allow, reason = gate.allow(ts=ts_naive, asset=asset, signal_direction=direction)

    try:
        _log_decision(
            ts=ts, strategy=strategy_name, asset=asset,
            signal_direction=direction, allow=bool(allow), reason=reason,
            regime_pct=_extract_regime_pct_from_reason(reason),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "regime_gate_decisions append skipped (verdict preserved): %s",
            e, exc_info=True)

    return not allow
