"""Per-(symbol, strategy) signal-evaluation observability for stock M4-P.

The decoupled stock daemon (``StockStrategyDaemon``) logs only
``"Signal cycle: N signals from [...]"`` — there is NO per-(symbol, strategy)
reject visibility, so "why 0 signals" is invisible live (the 2026-06-24
no-trade diagnosis had to reproduce it offline). Futures already has this via
``trading:futures:setup_eval`` + the reject-reason pattern from PR #483.

This module mirrors that for stock:

  * ``StockSignalEvalConfig`` — toggle/TTL/key, loaded from
    ``config/stock_signal_eval.yaml`` (default ON).
  * ``SignalEvalCollector`` — accumulates per-(symbol, strategy) outcomes for
    one evaluation cycle and renders an aggregate hash keyed by strategy:
    ``{strategy -> JSON{outcome, reason, reason_counts, evaluated, signals,
    rejects, ts_kst, strategy}}`` so the operator reads, for each strategy,
    how many symbols rejected and the dominant reason.

It is **read-only telemetry**: it records what the daemon already decided and
never influences signal/entry decisions. Publishing (Redis ``hset`` + ``expire``)
and once-per-cycle throttling live in the daemon, mirroring the daemon's regime
publisher.

Payload schema (JSON string per strategy field at ``redis_key``)::

    {"strategy": "pattern_pullback", "outcome": "reject",
     "reason": "no_sma_200", "reason_counts": {"no_sma_200": 17, ...},
     "evaluated": 20, "signals": 0, "rejects": 20,
     "ts_kst": "2026-06-24T10:42:03.123456+09:00"}
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_signal_eval.yaml"
_CONFIG_SECTION = "stock_signal_eval"

# Outcome tokens.
OUTCOME_SIGNAL = "signal"
OUTCOME_REJECT = "reject"

# Canonical reject reasons captured at the daemon boundary. These are the
# distinctions the diagnosis named: the warmth dead-zone, the daily-missing
# (no_sma_200) case, the daily-watchlist gate, and the residual
# "generator returned None" bucket must all be separable.
REJECT_COLD = "cold"  # symbol not yet warm (skipped before generators ran)
REJECT_NO_MARKET_DATA = "no_market_data"  # feed had no current price
REJECT_BEAR_REGIME = "bear_regime"  # bear gate skipped entry evaluation
REJECT_BEAR_CAP_REACHED = "bear_cap_reached"  # bear override cap blocked new entries
REJECT_BEAR_RS_GATE = "bear_rs_gate"  # symbol not up ≥ min_change_pct_for_rs today
REJECT_NO_SMA_200 = "no_sma_200"  # SMA(200)-dependent strategy, daily SMA absent
# daily-gated strategy, this symbol not on its watchlist
REJECT_NO_DAILY_WATCHLIST = "no_daily_watchlist"
REJECT_CONDITIONS_NOT_MET = "conditions_not_met"  # generator returned None
REJECT_LLM_COOLDOWN = "llm_cooldown"
REJECT_LLM_QUALITY_BELOW_MIN = "llm_quality_below_min"
REJECT_LLM_CONFIDENCE_BELOW_MIN = "llm_confidence_below_min"
REJECT_LLM_NO_PRICE = "llm_no_price"
REJECT_LLM_METADATA_MISSING = "llm_metadata_missing"
REJECT_LLM_EXCLUDED = "llm_excluded"
REJECT_LLM_NOT_ALLOWED = "llm_not_allowed"

__all__ = [
    "OUTCOME_REJECT",
    "OUTCOME_SIGNAL",
    "REJECT_BEAR_CAP_REACHED",
    "REJECT_BEAR_REGIME",
    "REJECT_BEAR_RS_GATE",
    "REJECT_COLD",
    "REJECT_CONDITIONS_NOT_MET",
    "REJECT_LLM_CONFIDENCE_BELOW_MIN",
    "REJECT_LLM_COOLDOWN",
    "REJECT_LLM_EXCLUDED",
    "REJECT_LLM_METADATA_MISSING",
    "REJECT_LLM_NOT_ALLOWED",
    "REJECT_LLM_NO_PRICE",
    "REJECT_LLM_QUALITY_BELOW_MIN",
    "REJECT_NO_DAILY_WATCHLIST",
    "REJECT_NO_MARKET_DATA",
    "REJECT_NO_SMA_200",
    "SignalEvalCollector",
    "StockSignalEvalConfig",
]


@dataclass(frozen=True)
class StockSignalEvalConfig:
    """Publisher settings for the stock signal-eval contract."""

    enabled: bool = True
    redis_key: str = "stock:daemon:signal_eval"
    # Repo convention: new operational keys carry a 24h TTL.
    publish_ttl_seconds: int = 86_400

    @classmethod
    def load(cls) -> StockSignalEvalConfig:
        """Load from ``config/stock_signal_eval.yaml`` (defaults on any failure)."""
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            return cls(
                enabled=bool(raw.get("enabled", cls.enabled)),
                redis_key=str(raw.get("redis_key", cls.redis_key)),
                publish_ttl_seconds=int(
                    raw.get("publish_ttl_seconds", cls.publish_ttl_seconds)
                ),
            )
        except Exception:
            logger.warning("stock_signal_eval.yaml load failed; using defaults")
            return cls()


@dataclass
class _StrategyTally:
    """Per-strategy accumulator for one evaluation cycle."""

    signals: int = 0
    rejects: int = 0
    reason_counts: Counter[str] = field(default_factory=Counter)

    @property
    def evaluated(self) -> int:
        return self.signals + self.rejects

    def dominant_reason(self) -> str | None:
        if not self.reason_counts:
            return None
        # most_common is stable for ties on insertion order in CPython 3.7+.
        return self.reason_counts.most_common(1)[0][0]


class SignalEvalCollector:
    """Accumulate per-(symbol, strategy) outcomes; render the aggregate payload.

    Pure (no Redis): the daemon builds one collector per evaluate cycle, records
    each evaluated (symbol, strategy), then calls :meth:`to_payload` once and
    publishes it. Read-only telemetry — recording never alters any decision.
    """

    def __init__(self) -> None:
        self._tallies: dict[str, _StrategyTally] = {}

    def record(
        self,
        strategy: str,
        symbol: str,  # noqa: ARG002 — part of the (symbol, strategy) contract; aggregated by count
        outcome: str,
        reason: str,
    ) -> None:
        """Record one (symbol, strategy) evaluation outcome.

        Args:
            strategy: Entry-strategy name (hash field).
            symbol: Evaluated symbol — part of the per-(symbol, strategy)
                contract the caller iterates; aggregated by count (not stored
                individually) so the payload stays bounded for ~40-symbol
                universes.
            outcome: ``"signal"`` or ``"reject"``.
            reason: For ``signal`` the direction (e.g. ``"long"``); for
                ``reject`` a canonical reason token.
        """
        tally = self._tallies.setdefault(strategy, _StrategyTally())
        if outcome == OUTCOME_SIGNAL:
            tally.signals += 1
        else:
            tally.rejects += 1
            tally.reason_counts[reason] += 1

    def to_payload(self, *, now: datetime) -> dict[str, str]:
        """Render ``{strategy -> JSON-string}`` for one ``hset`` of the eval hash.

        ``now`` is normalized to KST (Asia/Seoul) for the ``ts_kst`` field, so
        the operator reads Korean-market-native timestamps regardless of the
        daemon's wall-clock tz.
        """
        ts_kst = to_kst(now).isoformat()
        payload: dict[str, str] = {}
        for strategy, tally in self._tallies.items():
            fired = tally.signals > 0
            outcome = OUTCOME_SIGNAL if fired else OUTCOME_REJECT
            # When the strategy fired we report the signal; otherwise the modal
            # reject reason is the "why 0 signals" answer for this strategy.
            reason: str | None = "fired" if fired else tally.dominant_reason()
            payload[strategy] = json.dumps(
                {
                    "strategy": strategy,
                    "outcome": outcome,
                    "reason": reason,
                    "reason_counts": dict(tally.reason_counts),
                    "evaluated": tally.evaluated,
                    "signals": tally.signals,
                    "rejects": tally.rejects,
                    "ts_kst": ts_kst,
                }
            )
        return payload

    def is_empty(self) -> bool:
        return not self._tallies


def make_signal_eval_summary(payload: dict[str, str]) -> dict[str, Any]:
    """Decode a published eval hash into a plain dict (operator/dashboard read).

    Best-effort: malformed JSON fields are skipped. Returns
    ``{strategy: {outcome, reason, rejects, ...}}``.
    """
    summary: dict[str, Any] = {}
    for strategy, raw in (payload or {}).items():
        key = (
            strategy.decode() if isinstance(strategy, (bytes, bytearray)) else strategy
        )
        value = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
        try:
            summary[key] = json.loads(value)
        except (ValueError, TypeError):
            continue
    return summary
