"""Golden pin: strategy outputs BEFORE/AFTER the P1-b2 embedded-math delegation.

``p1b2_embedded_math_golden.json`` captures ``generate()`` / ``should_exit()``
outputs (including every signal-metadata number) of the strategies whose inline
indicator math is being moved behind the indicator package
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3 P1-b item 2):

* ``macd_ema_crossover``  — inline EMA regime filter + volume-MA confirmation
* ``trix_golden``         — inline SMA / RVOL / rolling return-std filters
* ``opening_volume_surge``— stateful 1-min return + RVOL spike-hit window
* ``TRIX_GOLDEN_EXIT``    — swing-low (rolling extrema) stop
* ``track_a_exit``        — rolling-window max-adverse-move (crash guard)

Scenarios use seeded synthetic data and are asserted for EXACT equality (the
refactor must be bit-identical; JSON float round-trip is exact for float64).

Regenerate (only when intentionally re-pinning, from repo root):

    PYTHONPATH=$PWD python tests/unit/strategy/test_p1b2_embedded_math_golden.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import MACDCalculator, calculate_all_momentum
from shared.models.position import Position, PositionSide, PositionState
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.macd_ema_crossover import (
    MACDEMACrossoverConfig,
    MACDEMACrossoverEntry,
)
from shared.strategy.entry.opening_volume_surge import (
    OpeningVolumeSurgeConfig,
    OpeningVolumeSurgeEntry,
)
from shared.strategy.entry.trix_golden import TrixGoldenConfig, TrixGoldenEntry
from shared.strategy.exit.track_a_exit import TrackAExit, TrackAExitConfig
from shared.strategy.exit.trix_golden_exit import TrixGoldenExit, TrixGoldenExitConfig

_KST = ZoneInfo("Asia/Seoul")
_GOLDEN_PATH = Path(__file__).parent / "p1b2_embedded_math_golden.json"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _trading_timestamps(n: int, step_minutes: int) -> list[datetime]:
    """KST bar timestamps inside every touched strategy's entry window.

    09:30 <= t <= 14:30 on weekdays, ``step_minutes`` apart, rolling to the
    next weekday when the day is exhausted. Deterministic.
    """
    out: list[datetime] = []
    day = datetime(2026, 3, 16, tzinfo=_KST)  # Monday
    t = day.replace(hour=9, minute=30)
    while len(out) < n:
        if t.hour > 14 or (t.hour == 14 and t.minute > 30):
            day = day + timedelta(days=1)
            while day.weekday() >= 5:
                day = day + timedelta(days=1)
            t = day.replace(hour=9, minute=30)
        out.append(t)
        t = t + timedelta(minutes=step_minutes)
    return out


def _random_walk_ohlcv(seed: int, n: int, start: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = np.maximum(start + np.cumsum(rng.normal(0.0, 0.6, n)), 5.0)
    spread = np.abs(rng.normal(0.0, 0.4, n))
    volume = rng.lognormal(mean=9.5, sigma=0.6, size=n)
    return pd.DataFrame(
        {
            "open": close - rng.normal(0.0, 0.2, n),
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": volume,
        }
    )


def _signal_event(i: int, sig: Any) -> dict[str, Any]:
    return {
        "bar": i,
        "price": float(sig.price),
        "confidence": float(sig.confidence),
        "metadata": {
            k: v
            for k, v in sig.metadata.items()
            if isinstance(v, (int, float, str, bool))
        },
    }


# ---------------------------------------------------------------------------
# Scenario builders (each returns a JSON-serialisable pin)
# ---------------------------------------------------------------------------


def _scenario_macd_ema_crossover() -> list[dict[str, Any]]:
    """Sliding generate() over a seeded walk; pins EMA regime + volume-MA gate."""
    n = 260
    df = _random_walk_ohlcv(seed=42, n=n)
    MACDCalculator(fast=12, slow=26, signal=9).calculate(df)
    cfg = MACDEMACrossoverConfig(
        volume_confirm=True,
        volume_threshold=0.8,
        signal_cooldown_seconds=0,
        min_candles=60,
        allow_short=True,
    )
    gen = MACDEMACrossoverEntry(cfg)
    timestamps = _trading_timestamps(n, step_minutes=15)
    events: list[dict[str, Any]] = []
    for i in range(60, n):
        ctx = EntryContext(
            market_data={
                "code": "005930",
                "name": "GOLDEN",
                "close": float(df["close"].iloc[i]),
            },
            indicators={"momentum_15m": {"df": df.iloc[: i + 1]}},
            timestamp=timestamps[i],
        )
        sig = asyncio.run(gen.generate(ctx))
        if sig is not None:
            events.append(_signal_event(i, sig))
    return events


def _scenario_trix_golden() -> list[dict[str, Any]]:
    """Acceleration mode with SMA / RVOL / return-vol / ATR%% filters active."""
    n = 400
    df = calculate_all_momentum(_random_walk_ohlcv(seed=7, n=n))
    cfg = TrixGoldenConfig(
        trix_entry_mode="acceleration",
        use_uncorrelated_filters=True,
        require_above_sma=True,
        rvol_filter=True,
        rvol_threshold=1.0,
        max_atr_pct=0.02,
        max_return_vol=0.02,
        signal_cooldown_seconds=0,
        max_signals_per_day=0,
        min_candles=60,
        obv_filter=True,
    )
    gen = TrixGoldenEntry(cfg)
    timestamps = _trading_timestamps(n, step_minutes=5)
    events: list[dict[str, Any]] = []
    for i in range(60, n):
        ctx = EntryContext(
            market_data={
                "code": "005930",
                "name": "GOLDEN",
                "close": float(df["close"].iloc[i]),
            },
            indicators={"momentum_5m": {"df": df.iloc[: i + 1]}},
            timestamp=timestamps[i],
        )
        sig = asyncio.run(gen.generate(ctx))
        if sig is not None:
            events.append(_signal_event(i, sig))
    return events


def _scenario_opening_volume_surge() -> list[dict[str, Any]]:
    """Minute-quote sequence; pins 1-min return, spike-hit window, score."""
    cfg = OpeningVolumeSurgeConfig(
        volume_gate_mode="either",
        volume_multiplier=1.0,
        min_rvol=1.2,
        min_change_pct=0.3,
        min_range_position=0.2,
        min_day_range_pct=0.1,
        min_return_1m_pct=0.02,
        rvol_spike_threshold=1.8,
        spike_lookback_minutes=5,
        min_spike_hits=2,
        min_signal_score=0.4,
    )
    gen = OpeningVolumeSurgeEntry(cfg)
    rng = np.random.default_rng(11)
    prev_day_volume = 1_000_000
    events: list[dict[str, Any]] = []
    for code in ("123450", "678900"):
        close = 10_000.0
        open_ = 10_000.0
        high = close
        low = close
        cum_volume = 0
        for minute in range(60):
            ts = datetime(2026, 3, 16, 9, 5, tzinfo=_KST) + timedelta(minutes=minute)
            close = max(close * (1.0 + rng.normal(0.0012, 0.004)), 1.0)
            high = max(high, close)
            low = min(low, close)
            cum_volume += int(rng.integers(10_000, 80_000))
            rvol = float(np.abs(rng.normal(1.6, 0.8)))
            change_pct = (close / open_ - 1.0) * 100.0
            ctx = EntryContext(
                market_data={
                    "code": code,
                    "name": "GOLDEN",
                    "close": close,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "volume": cum_volume,
                    "prev_day_volume": prev_day_volume,
                    "rvol": rvol,
                    "change_pct": change_pct,
                },
                timestamp=ts,
            )
            sig = asyncio.run(gen.generate(ctx))
            if sig is not None:
                event = _signal_event(minute, sig)
                event["code"] = code
                events.append(event)
    return events


def _exit_position(
    entry_price: float,
    *,
    side: PositionSide = PositionSide.LONG,
    entry_time: datetime,
    metadata: dict[str, Any] | None = None,
) -> Position:
    return Position(
        id="golden-pos-1",
        code="005930",
        name="GOLDEN",
        side=side,
        quantity=10,
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=PositionState.SURVIVAL,
        strategy="golden",
        metadata=metadata or {},
    )


def _scenario_trix_golden_exit() -> list[dict[str, Any]]:
    """Sliding should_exit(); pins the swing-low stop bar and its value."""
    n = 120
    rng = np.random.default_rng(23)
    # Mild sideways noise for 60 bars (clustered lows), then a steady decline
    # so the swing-low stop (priority 3) fires before the divergence check.
    close = np.concatenate(
        [
            100.0 + rng.normal(0.0, 0.3, 60),
            100.0 - 1.2 * np.arange(1, n - 60 + 1) + rng.normal(0.0, 0.1, n - 60),
        ]
    )
    spread = np.abs(rng.normal(0.0, 0.4, n))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.lognormal(mean=9.5, sigma=0.6, size=n),
        }
    )
    df = calculate_all_momentum(df)
    cfg = TrixGoldenExitConfig(
        stop_loss_pct=-0.5,  # keep the hard stop out of the way
        min_hold_minutes=0,
        trailing_stop_enabled=False,
        partial_exit_enabled=False,
        eod_close_enabled=False,
        use_swing_low_stop=True,
        swing_lookback=10,
    )
    gen = TrixGoldenExit(cfg)
    entry_time = datetime(2026, 3, 16, 9, 30)
    position = _exit_position(float(df["close"].iloc[60]), entry_time=entry_time)
    events: list[dict[str, Any]] = []
    for i in range(61, n):
        price = float(df["close"].iloc[i])
        ctx = ExitContext(
            position=position,
            market_data={
                "005930": {"close": price, "momentum_5m": {"df": df.iloc[: i + 1]}}
            },
            timestamp=datetime(2026, 3, 16, 11, 0) + timedelta(minutes=5 * (i - 60)),
        )
        fired, sig = asyncio.run(gen.should_exit(ctx))
        if fired and sig is not None:
            events.append(
                {
                    "bar": i,
                    "reason": sig.reason.value,
                    "profit_pct": float(sig.profit_pct),
                    "quantity": int(sig.quantity),
                    "metadata": {
                        k: v
                        for k, v in sig.metadata.items()
                        if isinstance(v, (int, float, str, bool))
                    },
                }
            )
            break  # position exits; state beyond this is undefined
    return events


def _scenario_track_a_exit() -> list[dict[str, Any]]:
    """Tick sequence; pins the rolling-window crash-guard trigger tick."""
    cfg = TrackAExitConfig(
        crash_atr_mult=3.0,
        catastrophic_atr_mult=6.0,
        eod_close_enabled=False,
    )
    gen = TrackAExit(cfg)
    entry_time = datetime(2026, 1, 5, tzinfo=UTC)
    rng = np.random.default_rng(31)
    events: list[dict[str, Any]] = []
    for side in (PositionSide.LONG, PositionSide.SHORT):
        position = _exit_position(
            100.0,
            side=side,
            entry_time=entry_time,
            metadata={"entry_atr": 2.0, "prev_price": 100.0},
        )
        price = 100.0
        for tick in range(40):
            # Gradual adverse grind (< single-tick threshold per tick) so only
            # the WINDOWED path can fire; seeded noise keeps values non-trivial.
            adverse = float(rng.uniform(0.55, 0.75))
            price = price - adverse if side == PositionSide.LONG else price + adverse
            ts = datetime(2026, 3, 16, 10, 0, tzinfo=_KST) + timedelta(seconds=5 * tick)
            ctx = ExitContext(
                position=position,
                market_data={"close": price, "atr": 2.0},
                timestamp=ts,
            )
            fired, sig = asyncio.run(gen.should_exit(ctx))
            if fired and sig is not None:
                events.append(
                    {
                        "side": side.value,
                        "tick": tick,
                        "price": float(price),
                        "reason": sig.reason.value,
                        "profit_pct": float(sig.profit_pct),
                        "metadata": {
                            k: v
                            for k, v in sig.metadata.items()
                            if isinstance(v, (int, float, str, bool))
                        },
                    }
                )
                break
    return events


_SCENARIOS = {
    "macd_ema_crossover": _scenario_macd_ema_crossover,
    "trix_golden": _scenario_trix_golden,
    "opening_volume_surge": _scenario_opening_volume_surge,
    "trix_golden_exit": _scenario_trix_golden_exit,
    "track_a_exit": _scenario_track_a_exit,
}


def build_golden() -> dict[str, Any]:
    return {name: fn() for name, fn in _SCENARIOS.items()}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    return json.loads(_GOLDEN_PATH.read_text())


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_scenario_matches_golden(name: str, golden: dict[str, Any]) -> None:
    got = _SCENARIOS[name]()
    # Exact equality: the delegation refactor must be bit-identical, and JSON
    # float64 round-trips are exact.
    assert json.loads(json.dumps(got)) == golden[name], name


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_scenario_is_non_trivial(name: str, golden: dict[str, Any]) -> None:
    """Guard against a silently-empty pin (a scenario that never fires)."""
    assert golden[name], f"golden scenario '{name}' pinned no events"


if __name__ == "__main__":
    _GOLDEN_PATH.write_text(json.dumps(build_golden(), indent=2) + "\n")
    print(f"wrote {_GOLDEN_PATH}")
