"""Lightweight portfolio advisory interfaces.

These Protocols let hedge-advisory callers depend on structural contracts
without importing the full hedge implementation or any execution/order path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

PositionMapping = Mapping[str, Any]


@runtime_checkable
class HedgeBetaEstimateView(Protocol):
    """Structural view of one symbol beta estimate."""

    beta: float
    observations: int
    fallback: bool


@runtime_checkable
class HedgeAdviceView(Protocol):
    """Structural view of one hedge-advisory result."""

    product: str
    multiplier: int
    futures_price: float | None
    stock_long_notional: float
    portfolio_beta: float | None
    beta_notional: float
    futures_net_contracts: int
    futures_net_notional: float
    net_beta_exposure: float
    recommended_short_contracts: int
    residual_exposure_after: float
    band: str | None
    score: float | None
    advisory_active: bool
    reason: str
    degraded: bool
    missing_components: tuple[str, ...]
    asof_ts: datetime


@runtime_checkable
class HedgeExposureView(Protocol):
    """Structural input view required by a hedge advisor."""

    stock_positions: Sequence[PositionMapping]
    futures_positions: Sequence[PositionMapping]
    betas: Mapping[str, HedgeBetaEstimateView]
    multipliers: Mapping[str, float]
    futures_price: float | None
    futures_price_fresh: bool
    band: str | None
    score: float | None
    asof_ts: datetime
    extra_missing: Sequence[str]


@runtime_checkable
class HedgeAdvisorProtocol(Protocol):
    """Small callable surface for computing advisory-only hedge advice."""

    def advise(self, exposure: HedgeExposureView) -> HedgeAdviceView:
        """Return hedge advice for the supplied exposure view."""
        ...


__all__ = [
    "HedgeAdvisorProtocol",
    "HedgeAdviceView",
    "HedgeBetaEstimateView",
    "HedgeExposureView",
    "PositionMapping",
]
