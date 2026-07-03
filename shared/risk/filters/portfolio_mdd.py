"""PortfolioMddFilter — unified monthly-MDD circuit-breaker gate (Phase 3B).

RiskFilterLayer filter #9 (appended after the eight Phase 3 filters). Reads
the ``portfolio:equity:latest`` hash published by the daily
``services/portfolio_monitor`` batch and, ONLY when the published breaker
``mode`` is ``enforce``:

* stage ``REDUCE``     → pass with ``size_multiplier`` = configured factor
  (``config/portfolio.yaml::circuit_breaker.monthly_mdd_stages.reduce
  .new_entry_size_factor``, default 0.5);
* stage ``HALT_NEW``   → reject (``portfolio_mdd_halt_new``);
* stage ``FULL_STOP``  → reject (``portfolio_mdd_full_stop``).

Fail-OPEN design (shadow-first rollout): missing key, Redis errors, stale
``asof_ts``, unknown stage, or ``mode`` ∈ {off, shadow} all pass the signal
unchanged. Enforcement must never depend on the monitor being healthy — the
FULL_STOP hard latch is carried by the kill-switch sentinel file instead.

Configuration: ``config/risk.yaml`` ``risk.portfolio_mdd`` /
``risk_stock.portfolio_mdd`` (read side) + ``config/portfolio.yaml`` (stage
semantics). No thresholds are hardcoded here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.decision.signal import Signal
from shared.portfolio.equity import (
    BLOCKING_STAGES,
    STAGE_REDUCE,
    STAGE_SEVERITY,
)
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: The published mode value that arms enforcement. Anything else fails open.
_ENFORCE_MODE = "enforce"


def _default_snapshot_provider(
    latest_key: str,
) -> Callable[[], Mapping[str, str] | None]:
    """Lazy sync-Redis reader for the portfolio equity hash.

    ``RiskFilterLayer.evaluate`` is synchronous, so the filter keeps its own
    sync client (same pattern as the stock daemon's open-position provider).
    The client is created on first use and reused afterwards.
    """
    client: Any = None

    def _read() -> Mapping[str, str] | None:
        nonlocal client
        if client is None:
            import redis as redis_lib

            from shared.config.runtime_defaults import redis_url_from_env

            client = redis_lib.Redis.from_url(
                redis_url_from_env(), decode_responses=True
            )
        raw = client.hgetall(latest_key)
        if not raw:
            return None
        return {str(key): str(value) for key, value in dict(raw).items()}

    return _read


class PortfolioMddFilter(RiskFilter):
    """Gate new entries on the unified portfolio monthly-MDD stage.

    Args:
        reduce_size_factor: Soft size multiplier applied while the published
            stage is ``REDUCE`` (from ``config/portfolio.yaml``).
        latest_key: Redis hash key published by services/portfolio_monitor.
        stale_max_age_seconds: Fail-open when the snapshot ``asof_ts`` is
            older than this (KST naive comparison).
        snapshot_provider: Zero-arg callable returning the decoded hash (or
            ``None``). Defaults to a lazy sync-Redis reader; inject in tests.
        now_provider: KST-naive clock override for staleness tests.
    """

    name = "portfolio_mdd"

    def __init__(
        self,
        *,
        reduce_size_factor: float,
        latest_key: str,
        stale_max_age_seconds: int,
        snapshot_provider: Callable[[], Mapping[str, str] | None] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if not (0.0 < reduce_size_factor <= 1.0):
            raise ValueError(
                f"reduce_size_factor must be in (0.0, 1.0], got {reduce_size_factor!r}"
            )
        self.reduce_size_factor: float = reduce_size_factor
        self.latest_key: str = latest_key
        self.stale_max_age_seconds: int = stale_max_age_seconds
        self._snapshot_provider = snapshot_provider or _default_snapshot_provider(
            latest_key
        )
        self._now_provider = now_provider or (
            lambda: datetime.now(KST).replace(tzinfo=None)
        )

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002 — global gate; signal content unused
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        snapshot = self._read_snapshot()
        if snapshot is None:
            return self._pass()

        mode = str(snapshot.get("mode", "")).strip().lower()
        if mode != _ENFORCE_MODE:
            return self._pass()

        if self._is_stale(snapshot.get("asof_ts")):
            return self._pass()

        stage = str(snapshot.get("stage", "")).strip().upper()
        if stage not in STAGE_SEVERITY:
            # Unknown stage value — fail open rather than guess.
            logger.warning("portfolio_mdd: unknown stage %r; failing open", stage)
            return self._pass()

        if stage in BLOCKING_STAGES:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason=f"portfolio_mdd_{stage.lower()}",
            )
        if stage == STAGE_REDUCE:
            return FilterResult(
                passed=True,
                filter_name=self.name,
                size_multiplier=self.reduce_size_factor,
            )
        return self._pass()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _pass(self) -> FilterResult:
        return FilterResult(passed=True, filter_name=self.name)

    def _read_snapshot(self) -> Mapping[str, str] | None:
        try:
            return self._snapshot_provider()
        except Exception as exc:  # noqa: BLE001 — fail-open on any read error
            logger.warning("portfolio_mdd snapshot read failed: %s", exc)
            return None

    def _is_stale(self, asof_raw: str | None) -> bool:
        """True when asof_ts is missing/unparseable/too old (→ fail open)."""
        if not asof_raw:
            return True
        try:
            asof = datetime.fromisoformat(str(asof_raw))
        except ValueError:
            logger.warning("portfolio_mdd: unparseable asof_ts %r", asof_raw)
            return True
        if asof.tzinfo is not None:
            asof = asof.astimezone(KST).replace(tzinfo=None)
        age = (self._now_provider() - asof).total_seconds()
        return age > self.stale_max_age_seconds
