"""RiskFilterLayer — sequential orchestrator for Phase 3 risk filters.

The layer runs each :class:`~shared.risk.filters.base.RiskFilter` in order:

* If any filter returns ``passed=False`` the chain short-circuits immediately.
  The :class:`LayerResult` carries that filter's ``skip_reason`` and a
  ``size_multiplier`` of ``1.0`` (size reduction is irrelevant on rejection).
* Filters that pass may return a ``size_multiplier < 1.0`` to request a
  proportional reduction in position size (e.g. ``ConsecutiveLossFilter``).
  Multipliers are compounded multiplicatively across all passing filters.
* When the filter list is empty the layer passes every signal unchanged.

Design notes
------------
``LayerResult`` mirrors :class:`~shared.risk.filters.base.FilterResult` in
being a **frozen** dataclass, making it safe to cache, log, or pass across
thread boundaries without defensive copying.

The ``evaluate`` method is **synchronous** — all current filters perform only
in-memory arithmetic.  An async wrapper (``aevaluate``) can be added once a
filter requires I/O, without changing the public sync API.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shared.risk.filters.base import FilterResult, RiskFilter

if TYPE_CHECKING:
    from shared.decision.signal import Signal
    from shared.portfolio.core_holdings import CoreHoldings
    from shared.risk.config import FuturesRiskConfig
    from shared.risk.futures_margin import MarginProductSpec
    from shared.risk.state import RiskStateSnapshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayerResult:
    """Immutable result returned by :class:`RiskFilterLayer`.

    Attributes:
        passed: ``True`` when all filters approved the signal.
        skip_reason: The first rejection tag encountered, or ``None`` when
            *passed* is ``True``.
        size_multiplier: Product of every passing filter's ``size_multiplier``.
            Always ``1.0`` when *passed* is ``False`` (size reduction is
            meaningless for a rejected signal).
        filter_outcomes: Ordered list of :class:`FilterResult` objects for
            every filter that was actually called.  Filters after a rejector
            are absent (short-circuit semantics).
    """

    passed: bool
    skip_reason: str | None
    size_multiplier: float
    filter_outcomes: list[FilterResult] = field(default_factory=list)


class RiskFilterLayer:
    """Sequential orchestrator that runs a list of :class:`RiskFilter` in order.

    Args:
        filters: Ordered sequence of risk filters.  The order determines both
            evaluation priority and short-circuit behaviour.

    Example::

        layer = RiskFilterLayer(filters=[
            TradingHoursFilter(config),
            DailyMDDFilter(config),
            ConsecutiveLossFilter(config),
        ])
        result = layer.evaluate(signal, state_snapshot)
        if not result.passed:
            logger.info("Signal rejected: %s", result.skip_reason)
        else:
            size = base_size * result.size_multiplier
    """

    def __init__(self, filters: list[RiskFilter]) -> None:
        self._filters: list[RiskFilter] = list(filters)

    @classmethod
    def from_config(
        cls,
        config: FuturesRiskConfig,
        trading_windows: list[str],
        *,
        current_atr_provider: Callable[[], float] | None = None,
        current_spread_provider: Callable[[], float] | None = None,
        has_open_position_provider: Callable[[str], bool] | None = None,
        open_positions_count_provider: (
            Callable[[], Mapping[str, int] | None] | None
        ) = None,
        portfolio_snapshot_provider: Callable[[], dict | None] | None = None,
        margin_snapshot_provider: Callable[[], Mapping[str, str] | None] | None = None,
        leverage_snapshot_provider: (
            Callable[[], Mapping[str, object] | None] | None
        ) = None,
        leverage_product_specs: Mapping[str, MarginProductSpec] | None = None,
        core_holdings_provider: Callable[[], CoreHoldings | None] | None = None,
        stock_positions_provider: (
            Callable[[], Mapping[str, float] | None] | None
        ) = None,
    ) -> RiskFilterLayer:
        """Build a fully-wired RiskFilterLayer from a FuturesRiskConfig + providers.

        All 8 Phase 3 filters are assembled in the spec §6.1 order:

        1. :class:`TradingHoursFilter` — KST trading-window whitelist.
        2. :class:`DailyMDDFilter`.
        3. :class:`WeeklyMDDFilter`.
        4. :class:`ConsecutiveLossFilter` (may return size_multiplier=0.5).
        5. :class:`DailyTradeCountFilter`.
        6. :class:`VolatilityFilter` — uses ``current_atr_provider`` if given,
           else a stub that returns 0.0 (never rejects on volatility).
        7. :class:`SpreadFilter` — uses ``current_spread_provider`` if given,
           else a stub that returns 0.0 (never rejects on spread).
        8. :class:`OpenPositionFilter` — uses ``has_open_position_provider``
           if given, else a stub that always returns False (never rejects
           for duplicate positions).

        Phase 3B appends filter #9 when ``config.portfolio_mdd.enabled``:

        9. :class:`PortfolioMddFilter` — unified monthly-MDD circuit-breaker
           gate. Fail-open by design (missing/stale Redis snapshot or mode
           ≠ enforce passes), so enabling it under the default shadow mode
           is a no-op. ``portfolio_snapshot_provider`` overrides the default
           lazy sync-Redis reader (tests / backtests).

        Phase 4-e optionally appends the total + per-asset concurrency gate
        when ``config.concurrent_positions.enabled`` (default ``False`` ⇒ never
        built): :class:`ConcurrentPositionsFilter` ports the World-A
        ``RiskManager`` ``max_total_positions`` / per-asset caps into World-B.
        Fail-open — without ``open_positions_count_provider`` or a configured
        cap it passes every signal, so it is inert until an operator wires it.

        Phase 4-f optionally appends the futures-only margin-risk new-entry gate
        when ``config.margin_gate.enabled`` AND ``config._asset_class`` is
        ``"futures"`` (so the block inherited by ``StockRiskConfig`` never grows
        a stock-chain filter): :class:`MarginGateFilter` reads the
        ``futures:risk:latest`` snapshot and rejects new entries when its
        published ``risk_level`` is ``block_new_entries``/``critical`` — but only
        in ``enforce`` mode. Default ``mode='shadow'`` passes every signal, and
        even in ``enforce`` a missing/stale/corrupt snapshot fails open, so while
        the ``services/futures_margin_risk`` publisher is dormant it is inert.
        ``margin_snapshot_provider`` overrides the default lazy sync-Redis reader
        (tests / backtests).

        Phase 4-g optionally appends the gross-leverage cap for BOTH assets when
        ``config.leverage.enabled`` (default ``False`` ⇒ never built):
        :class:`LeverageFilter` rejects new entries when
        ``Σ|notional| / equity`` exceeds ``max_gross_leverage`` — but only in
        ``enforce`` mode with a wired ``leverage_snapshot_provider``. No daemon
        wires a provider in this landing, so it is structurally inert.
        ``leverage_product_specs`` supplies the per-contract multipliers for the
        futures chain (stock uses multiplier 1); both are follow-up wiring.

        Phase 5B appends the stock-only Track A/B correlation filters when
        the config object carries a ``core_correlation`` block (i.e. for
        :class:`~shared.risk.config.StockRiskConfig`; the futures config has
        no such attribute, keeping the futures chain untouched):

        10. :class:`TrackAOverlapFilter` — reject candidates already held in
            the Track A manual ledger (fail-open; empty ledger → no-op).
        11. :class:`CoreSectorCapFilter` — sector cap on Track B open-position
            notional (fail-open; empty ledger → no-op).
            ``core_holdings_provider`` / ``stock_positions_provider`` override
            the default mtime-reloading ledger loader and lazy sync-Redis
            positions reader (tests / backtests).

        The stubs let the backtest run the layer in a reproducible way
        without wiring real position / ATR / LOB sources; Phase 4 overrides
        them with live providers.
        """
        from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
        from shared.risk.filters.daily_mdd import DailyMDDFilter
        from shared.risk.filters.daily_trade_count import DailyTradeCountFilter
        from shared.risk.filters.open_position import OpenPositionFilter
        from shared.risk.filters.spread import SpreadFilter
        from shared.risk.filters.trading_hours import TradingHoursFilter
        from shared.risk.filters.volatility import VolatilityFilter
        from shared.risk.filters.weekly_mdd import WeeklyMDDFilter

        if current_atr_provider is None:

            def current_atr_provider() -> float:
                return 0.0

        if current_spread_provider is None:

            def current_spread_provider() -> float:
                return 0.0

        if has_open_position_provider is None:

            def has_open_position_provider(_symbol: str) -> bool:
                return False

        filters: list[RiskFilter] = [
            TradingHoursFilter(trading_windows=trading_windows),
            DailyMDDFilter(
                account_equity_krw=config.account_equity_krw,
                daily_mdd_limit_pct=config.daily_mdd_limit_pct,
            ),
            WeeklyMDDFilter(
                account_equity_krw=config.account_equity_krw,
                weekly_mdd_limit_pct=config.weekly_mdd_limit_pct,
            ),
            ConsecutiveLossFilter(
                soft_threshold=config.consecutive_loss_soft_threshold,
                hard_threshold=config.consecutive_loss_hard_threshold,
                reduce_blocks_at_floor=config.reduce_blocks_at_floor,
            ),
            DailyTradeCountFilter(max_daily_trades=config.max_daily_trades),
            VolatilityFilter(current_atr_provider=current_atr_provider),
            SpreadFilter(
                max_spread_ticks=config.max_spread_ticks,
                current_spread_provider=current_spread_provider,
            ),
            OpenPositionFilter(has_open_position_provider=has_open_position_provider),
        ]

        portfolio_settings = getattr(config, "portfolio_mdd", None)
        if portfolio_settings is not None and portfolio_settings.enabled:
            from shared.portfolio.config import PortfolioConfig
            from shared.risk.filters.portfolio_mdd import PortfolioMddFilter

            portfolio_config = PortfolioConfig.load_or_default()
            filters.append(
                PortfolioMddFilter(
                    reduce_size_factor=(
                        portfolio_config.circuit_breaker.monthly_mdd_stages.reduce.new_entry_size_factor
                    ),
                    latest_key=portfolio_settings.latest_key,
                    stale_max_age_seconds=portfolio_settings.stale_max_age_seconds,
                    snapshot_provider=portfolio_snapshot_provider,
                )
            )

        # Phase 4-e: total + per-asset concurrency caps (World-A RiskManager
        # capability ported to World-B). Structurally inert unless
        # ``concurrent_positions.enabled`` — even then it fails open without an
        # injected count provider or a configured cap, so the shadow daemons'
        # pass-through behaviour is unchanged by default.
        concurrent_settings = getattr(config, "concurrent_positions", None)
        if concurrent_settings is not None and concurrent_settings.enabled:
            from shared.risk.filters.concurrent_positions import (
                ConcurrentPositionsFilter,
            )

            # Fail-fast on the per-asset binding: every FuturesRiskConfig (and
            # its StockRiskConfig subclass) declares ``_asset_class``, so a
            # missing/blank value means a future subclass forgot to — raise
            # loudly rather than silently mis-bind the per-asset cap to
            # "futures" (which would gate stock entries against the futures cap).
            asset_class = getattr(config, "_asset_class", None)
            if not asset_class:
                raise ValueError(
                    f"{type(config).__name__} has no _asset_class; "
                    "ConcurrentPositionsFilter cannot bind its per-asset cap. "
                    "Every FuturesRiskConfig subclass must declare _asset_class "
                    "(e.g. 'futures' / 'stock')."
                )

            # Observability: an enabled filter with no count provider is a
            # silent fail-open no-op. Log once at build time so operators can
            # tell 'inert because unwired' apart from 'active and passing'
            # (provider wiring lands in P4-h2 / P4-f).
            if open_positions_count_provider is None:
                logger.warning(
                    "ConcurrentPositionsFilter enabled for asset_class=%s but no "
                    "count provider wired — filter is inert (fail-open pass on "
                    "every signal)",
                    asset_class,
                )

            filters.append(
                ConcurrentPositionsFilter(
                    asset_class=asset_class,
                    open_positions_count_provider=open_positions_count_provider,
                    max_total_positions=concurrent_settings.max_total_positions,
                    max_positions_per_asset=(
                        concurrent_settings.max_positions_per_asset
                    ),
                )
            )

        # Phase 4-f: futures margin-risk new-entry gate (World-B wiring of the
        # shared/risk/futures_margin.py read-model). FUTURES-ONLY — built only
        # when the config's asset class is 'futures', so the field inherited by
        # StockRiskConfig never grows a stock-chain filter. Structurally inert:
        # ``margin_gate.enabled`` defaults False (never built) and ``mode``
        # defaults 'shadow' (built but passes every signal). Even in enforce
        # mode it fails open on a missing/stale/corrupt snapshot, so while the
        # ``services/futures_margin_risk`` publisher is dormant (no compose
        # profile) the gate has no effect. Effective activation = P5 (publisher
        # live) + operator flip of ``mode`` to 'enforce'.
        margin_settings = getattr(config, "margin_gate", None)
        margin_asset_class = getattr(config, "_asset_class", None)
        if (
            margin_settings is not None
            and margin_settings.enabled
            and margin_asset_class == "futures"
        ):
            from shared.risk.filters.margin_gate import MarginGateFilter

            # Observability: distinguish 'inert because unwired/dormant' from
            # 'armed and passing'. In enforce mode the gate depends on the
            # futures_margin_risk publisher being live; if that service is
            # dormant the snapshot is always absent and the gate fails open.
            if margin_settings.mode == "enforce":
                logger.warning(
                    "MarginGateFilter armed (mode=enforce) — depends on the "
                    "services/futures_margin_risk publisher; while that service "
                    "is dormant (compose profile absent) futures:risk:latest is "
                    "absent and the gate fails open (inert)"
                )
            else:
                logger.info(
                    "MarginGateFilter built in shadow mode — observation-only, "
                    "passes every signal (effective enforcement needs mode=enforce)"
                )

            filters.append(
                MarginGateFilter(
                    mode=margin_settings.mode,
                    latest_key=margin_settings.latest_key,
                    stale_max_age_seconds=margin_settings.stale_max_age_seconds,
                    snapshot_provider=margin_snapshot_provider,
                )
            )

        # Phase 4-g: gross notional / equity leverage cap. BOTH ASSETS (unlike
        # the futures-only margin gate) — the stock chain caps a cash account at
        # leverage 1.0, the futures chain at e.g. 3.0. Structurally inert:
        # ``leverage.enabled`` defaults False (never built) and ``mode`` defaults
        # 'shadow' (built but passes every signal). Even in enforce mode it fails
        # open without a wired snapshot provider, so while no daemon injects one
        # (this landing) the gate has no effect. Effective activation = a
        # follow-up wiring a position+equity provider (and, for futures, the real
        # ``leverage_product_specs``) + operator flip of ``mode`` to 'enforce'.
        leverage_settings = getattr(config, "leverage", None)
        if leverage_settings is not None and leverage_settings.enabled:
            from shared.risk.filters.leverage import LeverageFilter

            # Observability: an enabled filter with no snapshot provider is a
            # silent fail-open no-op. Log once at build time so operators can
            # tell 'inert because unwired' apart from 'armed and passing'
            # (provider wiring lands in a follow-up).
            if leverage_snapshot_provider is None:
                logger.warning(
                    "LeverageFilter enabled (mode=%s) but no snapshot provider "
                    "wired — filter is inert (fail-open pass on every signal)",
                    leverage_settings.mode,
                )

            filters.append(
                LeverageFilter(
                    mode=leverage_settings.mode,
                    max_gross_leverage=leverage_settings.max_gross_leverage,
                    snapshot_provider=leverage_snapshot_provider,
                    product_specs=leverage_product_specs,
                    stale_max_age_seconds=leverage_settings.stale_max_age_seconds,
                )
            )

        # Phase 5B: Track A/B correlation filters — stock chain only (the
        # futures FuturesRiskConfig carries no core_correlation attribute).
        core_settings = getattr(config, "core_correlation", None)
        if core_settings is not None and (
            core_settings.overlap_enabled or core_settings.sector_cap.enabled
        ):
            from shared.risk.filters.core_correlation import (
                CoreHoldingsProvider,
                CoreSectorCapFilter,
                TrackAOverlapFilter,
            )

            # Both filters share one reloading ledger loader (single stat/
            # parse cadence) unless a provider is injected.
            holdings_provider = core_holdings_provider or CoreHoldingsProvider(
                reload_interval_seconds=core_settings.reload_interval_seconds
            )
            if core_settings.overlap_enabled:
                filters.append(
                    TrackAOverlapFilter(core_holdings_provider=holdings_provider)
                )
            if core_settings.sector_cap.enabled:
                filters.append(
                    CoreSectorCapFilter(
                        core_holdings_provider=holdings_provider,
                        sector_key=core_settings.sector_cap.sector_key,
                        cap=core_settings.sector_cap.cap,
                        skip_reason=core_settings.sector_cap.skip_reason,
                        positions_provider=stock_positions_provider,
                    )
                )

        return cls(filters=filters)

    def evaluate(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,
    ) -> LayerResult:
        """Run all filters sequentially and return an aggregated :class:`LayerResult`.

        Args:
            signal: The candidate trading signal to evaluate.
            state_snapshot: Current intraday risk metrics loaded from Redis.

        Returns:
            A :class:`LayerResult` with the aggregated pass/fail decision,
            compounded size multiplier, and per-filter observability data.
        """
        outcomes: list[FilterResult] = []
        size_multiplier: float = 1.0

        for risk_filter in self._filters:
            result = risk_filter.check(signal, state_snapshot)
            outcomes.append(result)

            if not result.passed:
                # Short-circuit: reject immediately, reset multiplier to 1.0.
                return LayerResult(
                    passed=False,
                    skip_reason=result.skip_reason,
                    size_multiplier=1.0,
                    filter_outcomes=outcomes,
                )

            size_multiplier *= result.size_multiplier

        return LayerResult(
            passed=True,
            skip_reason=None,
            size_multiplier=size_multiplier,
            filter_outcomes=outcomes,
        )
