#!/usr/bin/env python3
"""The LEGACY-driven half of the CP-3 field producer, moved out of B1a."""

from __future__ import annotations

import math
import statistics
import sys
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.backtest.market_context_replay import MarketContextReplay  # noqa: E402
from shared.decision.setups.vwap_reversion import (  # noqa: E402
    SetupDVWAPReversion,
)
from shared.determinism.replay import DEFAULT_WARMUP_BARS  # noqa: E402
from shared.indicators.fields.scaling import (  # noqa: E402
    scaled_int_half_up,
    scaled_int_toward_zero,
)
from shared.instruments.contract_spec import ContractSpec  # noqa: E402
from tools.tos_cp3.produce_fields import (  # noqa: E402
    DEFAULT_MIN_BARS_PER_DAY,
    FIELD_ORDER,
    PRICE_SCALE,
    Z_SCALE,
    FieldRecord,
    OpenAnchor,
    ProducedBars,
    ProduceFieldsError,
    StrategyInputs,
    _assert_scalar_fields,
    _inputs_unusable,
    derive_as_of_ms,
    derive_raw_event_id,
)


def _bar_lookup(df: Any) -> dict[Any, tuple[float, float, float, float]]:
    """Map each bar timestamp to its ``(open, high, low, volume)``."""
    import pandas as pd

    stamps = df["timestamp"]
    if stamps.duplicated().any():
        dupes = stamps[stamps.duplicated()].head(3).tolist()
        raise ProduceFieldsError(
            f"duplicate bar timestamps in the loaded window (e.g. {dupes}); the "
            "OHLCV lookup would be ambiguous — re-run the minute dedup"
        )
    return {
        pd.Timestamp(stamp): (float(bar_open), float(high), float(low), float(volume))
        for stamp, bar_open, high, low, volume in zip(
            stamps, df["open"], df["high"], df["low"], df["volume"]
        )
    }


def produce_bars(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
    emit_days: frozenset[date] | None = None,
    observer: Callable[[datetime, Mapping[str, Any]], None] | None = None,
) -> ProducedBars:
    """Drive the legacy Setup D bar by bar and project its state into fields."""
    import pandas as pd

    setup = SetupDVWAPReversion(config=strategy.entry_config)
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        market_open_hour=anchor.hour,
        market_open_minute=anchor.minute,
        min_volume=0,
    )
    ohlcv = _bar_lookup(df)
    revert_band = strategy.vwap_revert_band
    eod_enabled = strategy.exit_config.eod_close_enabled
    eod_cutoff = strategy.exit_config.eod_close_time

    records: list[FieldRecord] = []
    omitted: list[tuple[str, str]] = []
    bars_replayed = 0
    non_target = 0
    for ctx in replay.iter_contexts():
        setup.check(ctx)  # type: ignore[arg-type]
        ev = setup.last_eval
        if observer is not None:
            observer(ctx.now, MappingProxyType(ev))
        bars_replayed += 1

        now: datetime = ctx.now
        if emit_days is not None and now.date() not in emit_days:
            non_target += 1
            continue
        as_of_ms = derive_as_of_ms(now)
        raw_event_id = derive_raw_event_id(symbol, now)

        close = float(ctx.current_price)
        vwap = float(ctx.vwap)
        atr = float(ctx.atr_14)
        unusable = _inputs_unusable(close, vwap, atr)
        if unusable is not None:
            omitted.append((raw_event_id, unusable))
            continue

        stamp = pd.Timestamp(now).tz_localize(None)
        if stamp not in ohlcv:
            raise ProduceFieldsError(
                f"{raw_event_id}: the replay yielded a bar with no row in the "
                "loaded frame — the OHLCV half cannot be published"
            )
        bar_open, bar_high, bar_low, bar_volume = ohlcv[stamp]
        for name, value in (
            ("open", bar_open),
            ("high", bar_high),
            ("low", bar_low),
            ("volume", bar_volume),
        ):
            if not math.isfinite(value):
                raise ProduceFieldsError(
                    f"{raw_event_id}: non-finite bar {name}={value!r}"
                )

        z = SetupDVWAPReversion.vwap_extension_z(close, vwap, atr)

        fields: dict[str, int | bool | str] = {
            "open_x100": scaled_int_half_up(bar_open, PRICE_SCALE),
            "high_x100": scaled_int_half_up(bar_high, PRICE_SCALE),
            "low_x100": scaled_int_half_up(bar_low, PRICE_SCALE),
            "close_x100": scaled_int_half_up(close, PRICE_SCALE),
            "volume": int(bar_volume),
            "session_token": now.date().isoformat(),
            "vwap_x100": scaled_int_half_up(vwap, PRICE_SCALE),
            "atr14_x100": scaled_int_half_up(atr, PRICE_SCALE),
            "z_x1000": scaled_int_toward_zero(z, Z_SCALE),
            "hi_vol": ev.get("hi_vol") is True,
            "stall_ok": ev.get("stall_ok") is True,
            "reversal_ok": ev.get("reversal_ok") is True,
            "entry_window": ev.get("entry_window") is True,
            "vwap_reverted": abs(z) <= revert_band,
            "eod": eod_enabled and now.time() >= eod_cutoff,
        }
        ordered = {name: fields[name] for name in FIELD_ORDER}
        _assert_scalar_fields(ordered, raw_event_id)
        records.append(
            FieldRecord(
                raw_event_id=raw_event_id,
                instrument=symbol,
                as_of_ms=as_of_ms,
                fields=ordered,
                bar_kst=now,
            )
        )
    if not records:
        raise ProduceFieldsError(
            "replay yielded no publishable bars: a window shorter than the "
            f"{DEFAULT_WARMUP_BARS}-bar replay warmup, a first session with "
            f"no prior-session close, {len(omitted)} unusable-input bars, or "
            f"{non_target} bars outside the stitch manifest's target segment"
        )
    return ProducedBars(
        records=records,
        bars_replayed=bars_replayed,
        omitted=omitted,
        non_target_segment_bars=non_target,
    )


def produce_records(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
) -> list[FieldRecord]:
    """:func:`produce_bars` when only the emitted records are wanted."""
    return produce_bars(
        df,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
    ).records


def measure_moving_vs_frozen_exit(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
) -> dict[str, Any]:
    """Measure D7: when does a moving-VWAP exit differ from the legacy target?"""
    setup = SetupDVWAPReversion(config=strategy.entry_config)
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        market_open_hour=anchor.hour,
        market_open_minute=anchor.minute,
        min_volume=0,
    )

    contexts: list[Any] = []
    entries: list[tuple[int, str, float]] = []
    for ctx in replay.iter_contexts():
        signal = setup.check(ctx)  # type: ignore[arg-type]
        contexts.append(ctx)
        if signal is not None:
            entries.append((len(contexts) - 1, signal.direction, signal.take_profit))

    earlier = identical = later = never_either = 0
    earlier_frozen_never = later_moving_never = 0
    leads: list[int] = []
    for index, direction, take_profit in entries:
        session = contexts[index].now.date()
        frozen_at: int | None = None
        moving_at: int | None = None
        for offset in range(index + 1, len(contexts)):
            later_ctx = contexts[offset]
            if later_ctx.now.date() != session:
                break
            price = float(later_ctx.current_price)
            atr = float(later_ctx.atr_14)
            if frozen_at is None:
                reached = (
                    price >= take_profit
                    if direction == "long"
                    else price <= take_profit
                )
                if reached:
                    frozen_at = offset
            if moving_at is None and atr > 0:
                z_now = SetupDVWAPReversion.vwap_extension_z(
                    price, float(later_ctx.vwap), atr
                )
                reverted = z_now >= 0 if direction == "long" else z_now <= 0
                if reverted:
                    moving_at = offset
            if frozen_at is not None and moving_at is not None:
                break
        if frozen_at is None and moving_at is None:
            never_either += 1
        elif moving_at is None:
            later += 1
            later_moving_never += 1
        elif frozen_at is None:
            earlier += 1
            earlier_frozen_never += 1
        elif moving_at < frozen_at:
            earlier += 1
            leads.append(frozen_at - moving_at)
        elif moving_at == frozen_at:
            identical += 1
        else:
            later += 1

    return {
        "window": f"{symbol} {df['timestamp'].dt.date.iloc[0]}"
        f"..{df['timestamp'].dt.date.iloc[-1]}",
        "market_open_kst": anchor.kst,
        "min_bars_per_day": DEFAULT_MIN_BARS_PER_DAY,
        "entries": len(entries),
        "earlier": earlier,
        "earlier_frozen_never_reached_in_session": earlier_frozen_never,
        "identical": identical,
        "later": later,
        "later_moving_never_reached_in_session": later_moving_never,
        "never_either": never_either,
        "median_lead_bars": int(statistics.median(leads)) if leads else 0,
        "max_lead_bars": max(leads) if leads else 0,
        "lead_bars_measured_over": len(leads),
    }
