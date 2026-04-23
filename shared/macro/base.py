"""Macro snapshot dataclass used across sources."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MacroSnapshot:
    ts_ms: int
    session: str  # "overnight_us_close" | "overnight_fx"
    sp500_close: float | None = None
    sp500_change_pct: float | None = None
    nasdaq_close: float | None = None
    nasdaq_change_pct: float | None = None
    eurex_kospi_close: float | None = None
    eurex_kospi_change_pct: float | None = None
    usdkrw: float | None = None
    usdkrw_change_pct: float | None = None
    dxy: float | None = None
    us10y_yield: float | None = None
    vix: float | None = None
    collected_from: list[str] = field(default_factory=list)
