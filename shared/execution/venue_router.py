"""Smart order router for KRX vs ATS venue selection.

Implements configuration-driven routing logic:
- Price improvement threshold
- Liquidity depth requirements
- Spread comparison
- Fill rate modeling
- Time-of-day preferences
- Stock filters (market cap, sector exclusions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time

from shared.execution.config import ATSRoutingConfig, ExecutionVenuePreference
from shared.execution.models import ExecutionVenue, OrderRequest, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class MarketData:
    """Market data snapshot for routing decision."""

    symbol: str
    krx_bid: float
    krx_ask: float
    krx_bid_qty: float
    krx_ask_qty: float
    ats_bid: float = 0.0
    ats_ask: float = 0.0
    ats_bid_qty: float = 0.0
    ats_ask_qty: float = 0.0
    market_cap: float = 0.0
    sector: str = ""
    timestamp: datetime | None = None

    @property
    def krx_spread(self) -> float:
        """KRX bid-ask spread."""
        return self.krx_ask - self.krx_bid

    @property
    def krx_spread_bps(self) -> float:
        """KRX spread in basis points."""
        mid = (self.krx_ask + self.krx_bid) / 2.0
        if mid <= 0:
            return 0.0
        return (self.krx_spread / mid) * 10000.0

    @property
    def ats_spread(self) -> float:
        """ATS bid-ask spread."""
        return self.ats_ask - self.ats_bid

    @property
    def ats_spread_bps(self) -> float:
        """ATS spread in basis points."""
        mid = (self.ats_ask + self.ats_bid) / 2.0
        if mid <= 0:
            return 0.0
        return (self.ats_spread / mid) * 10000.0

    def has_ats_quote(self) -> bool:
        """Check if ATS quote is available."""
        return self.ats_bid > 0 and self.ats_ask > 0 and self.ats_ask > self.ats_bid

    def price_improvement_bps(self, side: OrderSide) -> float:
        """Calculate price improvement from ATS vs KRX (in basis points).

        Args:
            side: BUY or SELL

        Returns:
            Price improvement in bps (positive = better price on ATS)
        """
        if not self.has_ats_quote():
            return 0.0

        if side == OrderSide.BUY:
            # For BUY, lower price is better
            krx_price = self.krx_ask
            ats_price = self.ats_ask
            if krx_price <= 0:
                return 0.0
            # Positive if ATS is cheaper
            return ((krx_price - ats_price) / krx_price) * 10000.0
        else:  # SELL
            # For SELL, higher price is better
            krx_price = self.krx_bid
            ats_price = self.ats_bid
            if krx_price <= 0:
                return 0.0
            # Positive if ATS pays more
            return ((ats_price - krx_price) / krx_price) * 10000.0

    def available_depth(self, side: OrderSide, venue: ExecutionVenue) -> float:
        """Get available depth for order side and venue.

        Args:
            side: BUY or SELL
            venue: KRX or ATS

        Returns:
            Available quantity
        """
        if venue == ExecutionVenue.KRX:
            return self.krx_ask_qty if side == OrderSide.BUY else self.krx_bid_qty
        else:  # ATS
            return self.ats_ask_qty if side == OrderSide.BUY else self.ats_bid_qty


@dataclass
class RoutingDecision:
    """Venue routing decision with reasoning."""

    venue: ExecutionVenue
    reason: str
    price_improvement_bps: float = 0.0
    krx_spread_bps: float = 0.0
    ats_spread_bps: float = 0.0
    liquidity_check_passed: bool = False
    fill_rate_estimate: float = 1.0
    time_preference: str = "AUTO"


class VenueRouter:
    """Smart order router for KRX vs ATS venue selection.

    Implements configurable routing rules based on price improvement,
    liquidity, spread, fill rate, time-of-day, and stock filters.
    """

    def __init__(self, config: ATSRoutingConfig):
        """Initialize venue router.

        Args:
            config: ATS routing configuration
        """
        self.config = config
        self._time_windows: dict[tuple[time, time], ExecutionVenuePreference] = {}
        self._parse_time_preferences()

    def _parse_time_preferences(self) -> None:
        """Parse time-of-day preferences into time ranges."""
        for window, pref_str in self.config.time_of_day_preferences.items():
            try:
                start_str, end_str = window.split("-")
                start = _parse_hhmm(start_str.strip())
                end = _parse_hhmm(end_str.strip())
                pref = ExecutionVenuePreference(pref_str)
                self._time_windows[(start, end)] = pref
            except Exception as e:
                logger.warning(
                    f"Failed to parse time window {window!r} -> {pref_str!r}: {e}"
                )

    def select_venue(
        self,
        order: OrderRequest,
        market_data: MarketData | None = None,
        current_time: datetime | None = None,
    ) -> RoutingDecision:
        """Select execution venue for order.

        Args:
            order: Order request
            market_data: Current market data snapshot (optional)
            current_time: Current time (defaults to now)

        Returns:
            RoutingDecision with venue and reasoning
        """
        if not self.config.enabled:
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason="ATS routing disabled",
            )

        if current_time is None:
            current_time = datetime.now()

        # Rule 5: Time-of-day preference
        time_pref = self._get_time_preference(current_time.time())
        if time_pref == ExecutionVenuePreference.KRX:
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"Time preference: KRX at {current_time.time()}",
                time_preference="KRX",
            )
        elif time_pref == ExecutionVenuePreference.ATS:
            return RoutingDecision(
                venue=ExecutionVenue.ATS,
                reason=f"Time preference: ATS at {current_time.time()}",
                time_preference="ATS",
            )

        # If no market data, use default venue
        if market_data is None:
            return RoutingDecision(
                venue=ExecutionVenue(self.config.default_venue),
                reason="No market data available, using default venue",
            )

        # Rule 6: Stock filters (market cap, sector exclusions)
        if not self._passes_stock_filters(market_data):
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"Stock filter failed: market_cap={market_data.market_cap:.0f}, sector={market_data.sector}",
            )

        # Check if ATS quote is available
        if not market_data.has_ats_quote():
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason="No ATS quote available",
                krx_spread_bps=market_data.krx_spread_bps,
            )

        # Rule 1: Price improvement threshold
        price_improvement = market_data.price_improvement_bps(order.side)
        if price_improvement < self.config.price_improvement_threshold_bps:
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"Price improvement insufficient: {price_improvement:.2f} bps < {self.config.price_improvement_threshold_bps:.2f} bps",
                price_improvement_bps=price_improvement,
                krx_spread_bps=market_data.krx_spread_bps,
                ats_spread_bps=market_data.ats_spread_bps,
            )

        # Rule 2: Liquidity requirements
        liquidity_ok = self._check_liquidity(order, market_data)
        if not liquidity_ok:
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"ATS liquidity insufficient: {market_data.available_depth(order.side, ExecutionVenue.ATS):.0f} < {self.config.min_depth_multiplier * order.quantity:.0f}",
                price_improvement_bps=price_improvement,
                krx_spread_bps=market_data.krx_spread_bps,
                ats_spread_bps=market_data.ats_spread_bps,
                liquidity_check_passed=False,
            )

        # Rule 3: Spread limits
        if market_data.ats_spread_bps > self.config.max_spread_bps:
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"ATS spread too wide: {market_data.ats_spread_bps:.2f} bps > {self.config.max_spread_bps:.2f} bps",
                price_improvement_bps=price_improvement,
                krx_spread_bps=market_data.krx_spread_bps,
                ats_spread_bps=market_data.ats_spread_bps,
                liquidity_check_passed=True,
            )

        # Rule 3b: Spread comparison (if enabled)
        if (
            self.config.spread_comparison_enabled
            and market_data.ats_spread_bps > market_data.krx_spread_bps * self.config.spread_comparison_multiplier
        ):
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"ATS spread significantly wider than KRX: {market_data.ats_spread_bps:.2f} bps vs {market_data.krx_spread_bps:.2f} bps",
                price_improvement_bps=price_improvement,
                krx_spread_bps=market_data.krx_spread_bps,
                ats_spread_bps=market_data.ats_spread_bps,
                liquidity_check_passed=True,
            )

        # Rule 4: Fill rate model
        fill_rate = self._estimate_fill_rate(market_data, order)
        if (
            self.config.prefer_certainty
            and fill_rate < self.config.ats_fill_rate_threshold
        ):
            return RoutingDecision(
                venue=ExecutionVenue.KRX,
                reason=f"ATS fill rate too low: {fill_rate:.2%} < {self.config.ats_fill_rate_threshold:.2%}",
                price_improvement_bps=price_improvement,
                krx_spread_bps=market_data.krx_spread_bps,
                ats_spread_bps=market_data.ats_spread_bps,
                liquidity_check_passed=True,
                fill_rate_estimate=fill_rate,
            )

        # All checks passed - route to ATS
        side_str = order.side.value if hasattr(order.side, 'value') else str(order.side)
        logger.info(
            f"Routing to ATS: {order.code} {side_str} {order.quantity} - "
            f"price_improvement={price_improvement:.2f}bps, fill_rate={fill_rate:.2%}"
        )
        return RoutingDecision(
            venue=ExecutionVenue.ATS,
            reason=f"All routing rules passed: price_improvement={price_improvement:.2f}bps, fill_rate={fill_rate:.2%}",
            price_improvement_bps=price_improvement,
            krx_spread_bps=market_data.krx_spread_bps,
            ats_spread_bps=market_data.ats_spread_bps,
            liquidity_check_passed=True,
            fill_rate_estimate=fill_rate,
            time_preference=time_pref.value,
        )

    def _get_time_preference(self, current: time) -> ExecutionVenuePreference:
        """Get time-of-day venue preference.

        Args:
            current: Current time

        Returns:
            Venue preference (KRX, ATS, or AUTO)
        """
        for (start, end), pref in self._time_windows.items():
            if _time_in_window(current, start, end):
                return pref
        return ExecutionVenuePreference.AUTO

    def _passes_stock_filters(self, market_data: MarketData) -> bool:
        """Check if stock passes market cap and sector filters.

        Args:
            market_data: Market data snapshot

        Returns:
            True if stock passes filters
        """
        # Market cap filter
        if market_data.market_cap > 0:
            if market_data.market_cap < self.config.min_market_cap:
                return False

        # Sector exclusion filter
        return not (market_data.sector and market_data.sector in self.config.excluded_sectors)

    def _check_liquidity(self, order: OrderRequest, market_data: MarketData) -> bool:
        """Check if ATS has sufficient liquidity for order.

        Args:
            order: Order request
            market_data: Market data snapshot

        Returns:
            True if liquidity requirements met
        """
        ats_depth = market_data.available_depth(order.side, ExecutionVenue.ATS)

        # Check absolute minimum
        if ats_depth < self.config.min_liquidity_depth:
            return False

        # Check relative to order size
        required_depth = order.quantity * self.config.min_depth_multiplier
        return not ats_depth < required_depth

    def _estimate_fill_rate(
        self, market_data: MarketData, order: OrderRequest
    ) -> float:
        """Estimate fill probability on ATS.

        Uses a simple heuristic based on:
        - Depth vs order size ratio
        - Spread width
        - Simulation config fill rate

        Args:
            market_data: Market data snapshot
            order: Order request

        Returns:
            Estimated fill rate (0.0 to 1.0)
        """
        base_fill_rate = self.config.simulation.ats_fill_rate

        # Adjust for depth
        ats_depth = market_data.available_depth(order.side, ExecutionVenue.ATS)
        depth_ratio = ats_depth / max(order.quantity, 1)
        if depth_ratio < 1.0:
            # Insufficient depth - lower fill rate
            depth_penalty = 0.3 * (1.0 - depth_ratio)
            base_fill_rate -= depth_penalty
        elif depth_ratio > 5.0:
            # Ample depth - higher fill rate
            depth_bonus = min(0.1, 0.02 * (depth_ratio - 5.0))
            base_fill_rate += depth_bonus

        # Adjust for spread
        if market_data.ats_spread_bps > self.config.max_spread_bps * 0.8:
            # Wide spread - lower fill rate
            spread_penalty = 0.15
            base_fill_rate -= spread_penalty

        # Clamp to [0, 1]
        return max(0.0, min(1.0, base_fill_rate))


def _parse_hhmm(s: str) -> time:
    """Parse HH:MM string to time object.

    Args:
        s: Time string in HH:MM format

    Returns:
        time object

    Raises:
        ValueError: If format is invalid
    """
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {s!r}, expected HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    return time(hour=hour, minute=minute)


def _time_in_window(current: time, start: time, end: time) -> bool:
    """Check if current time is within window.

    Args:
        current: Current time
        start: Window start time
        end: Window end time

    Returns:
        True if current is in [start, end]
    """
    if start <= end:
        # Normal window (e.g. 09:00-15:00)
        return start <= current <= end
    else:
        # Overnight window (e.g. 23:00-01:00)
        return current >= start or current <= end
