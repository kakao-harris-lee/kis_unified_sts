#!/usr/bin/env python3
"""The LEGACY-driven half of the CP-3 field producer, moved out of B1a.

What this is
------------
``tools/tos_cp3/produce_fields.py`` used to hold two producers: the one that
drives the legacy
:class:`~shared.decision.setups.vwap_reversion.SetupDVWAPReversion` bar by bar
and reads its own evaluation trace, and — since P2-c slice 1 — the declarative
one that runs a tenant's ``fields.yaml``. This module is the first of those,
moved verbatim so that the second can be the only one the PRODUCTION path
loads (plan ``docs/plans/2026-11-11-tos-p2-declarative-fields.md`` §5.2:
``SetupDVWAPReversion`` import 0 in ``produce_fields.py``).

Nothing here changed in the move. The bodies are the same bodies, the
docstrings are the same docstrings, and the omission gate, the record shape,
the scaling and the ``raw_event_id``/``as_of_ms`` derivation are still
:mod:`~tools.tos_cp3.produce_fields`'s — imported from there rather than
restated, so the legacy and declarative producers keep answering one question
with one function.

Who still drives the legacy
---------------------------
Measurement, and only measurement:

* ``tools/tos_cp3/fields_equivalence.py`` — the P2-b comparison's legacy side.
  It reads the setup's own ``last_eval`` through the ``observer`` hook, which a
  declarative evaluator has no equivalent of; that hook is why this driver
  could not simply be replaced in place.
* ``tools/tos_cp3/stitch_measure.py`` (S1b — the ATR window across a splice)
  and ``tools/tos_cp3/minute_probe.py``, for the same reason.
* :func:`measure_moving_vs_frozen_exit` — declared difference D7, which
  measures the legacy's frozen entry-time exit target against the moving VWAP
  the TOS rules compare. It is a measurement of the legacy, so it drives the
  legacy by definition.

The LIVE producer does not (P2-c slice 2). While the B3 witness stays
byte-frozen until ``TOS_PAPER_READY`` (CLAUDE.md, legacy-removal plan §2) this
module is what keeps the witness reachable without putting it in the
production path's import closure.

Firewall
--------
``tools/`` is inside the reverse scan of ``tools/tos_firewall_check.py``
(TOS-FW-R), so this module imports nothing from ``tos`` or ``tos_runtime``.
"""

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
    """Map each bar timestamp to its ``(open, high, low, volume)``.

    ``MarketContext`` carries only the close, so the OHLCV half of a published
    line is read back from the frame the replay was built from. A duplicated
    timestamp would make that lookup ambiguous (the #516 minute-dedup defect),
    so it is refused rather than resolved arbitrarily.
    """
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
    """Drive the legacy Setup D bar by bar and project its state into fields.

    ``check()`` is called exactly once per replayed bar — that single call is
    what advances the setup's causal ATR / close / VWAP windows, so calling it
    more or fewer times than the orchestrator would change ``hi_vol`` and
    ``stall_ok``. Nothing in this function recomputes a threshold or a formula
    that the setup owns.

    A bar whose inputs cannot carry their published meaning
    (:func:`_inputs_unusable`) is still EVALUATED — the legacy replay evaluates
    every bar, and the causal deques must advance identically — but is not
    emitted. Its id and reason go into the lineage.

    Args:
        emit_days: when given, only bars on these KST dates are EMITTED. Every
            other bar is still replayed — the whole point of a stitched seed is
            that the previous month's sessions advance ATR, the vol-window
            percentile and ``prev_close`` — but produces no record, because a
            previous-month bar carrying a ``raw_event_id`` named after this
            symbol would be a label error (plan §3.2a). ``None`` keeps the
            pre-stitch behaviour: every replayed bar is a candidate.
        observer: read-only hook called with ``(bar_kst, last_eval)`` after
            ``check()`` on EVERY replayed bar — the non-emitted previous-month
            bars included, which is the point: the causal ATR window is filled
            by bars this function does not publish, so a measurement of that
            window (``tools/tos_cp3/stitch_measure.py`` S1b, plan §3.2a's
            「``_atr_window`` 내용과 백분위 기준값」) cannot read it from the
            records. It observes the setup's own trace — nothing here is
            recomputed — and takes no part in the decision: it is handed a
            :class:`~types.MappingProxyType` over ``last_eval``, so a write
            raises instead of leaking into the next bar, and the returned
            records are identical with and without it
            (``tests/tools/test_cp3_produce_fields.py``).
    """
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
        # `arg-type` 억제 사유는 `emit_legacy_decisions.py` 의 같은 호출에 적었다 —
        # frozen `MarketContext` 대 쓰기 가능 멤버를 선언한 `FuturesMarketView`
        # 프로토콜의 기존 간극(`shared/backtest/decision_harness.py:262`).
        setup.check(ctx)  # type: ignore[arg-type]
        ev = setup.last_eval
        if observer is not None:
            # Read-only by construction, not by convention: the proxy raises on
            # any write, so "it takes no part in the decision" is enforced here
            # rather than only asserted in a test. The default path keeps the
            # `is not None` guard, so it allocates no proxy at all.
            observer(ctx.now, MappingProxyType(ev))
        bars_replayed += 1

        now: datetime = ctx.now
        if emit_days is not None and now.date() not in emit_days:
            # Replayed (the windows advanced on the check() above) and then
            # dropped BEFORE a join key is derived — see the docstring.
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

        # ONE definition of z, shared with check() (see the accessor's
        # docstring). Published on every bar because the session-exit fields
        # outlive the entry window, where check() returns early.
        z = SetupDVWAPReversion.vwap_extension_z(close, vwap, atr)

        fields: dict[str, int | bool | str] = {
            "open_x100": scaled_int_half_up(bar_open, PRICE_SCALE),
            "high_x100": scaled_int_half_up(bar_high, PRICE_SCALE),
            "low_x100": scaled_int_half_up(bar_low, PRICE_SCALE),
            "close_x100": scaled_int_half_up(close, PRICE_SCALE),
            "volume": int(bar_volume),
            # Opaque session identifier — a tos Bar reads no market hours from
            # it. Futures is day-only, so the KST date IS the session.
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


# ---------------------------------------------------------------------------
# D7 measurement (moving VWAP vs the legacy frozen target)
# ---------------------------------------------------------------------------


def measure_moving_vs_frozen_exit(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
) -> dict[str, Any]:
    """Measure D7: when does a moving-VWAP exit differ from the legacy target?

    For every bar the legacy setup FIRES on, walk the remaining bars of that
    session and record the first bar at which

    * the **frozen** rule triggers — the legacy ``take_profit`` price (fixed on
      the signal) is reached, exactly as ``SetupTargetExit`` compares it, and
    * the **moving** rule triggers — price is back at the session VWAP on the
      entry's side (``z >= 0`` for a long fade, ``z <= 0`` for a short), which
      is the strongest form a tenant policy can write on the published fields.

    Returns the counts the lineage's D7 entry quotes. Kept beside the producer
    rather than in a scratch script so the number in the sidecar can be
    regenerated by the same code that documents it: ``--measure-d7`` prints the
    :data:`D7_MEASUREMENT` literal from this function's output.

    The buckets are disjoint and exhaustive — ``earlier + identical + later +
    never_either == entries`` — and every lead is session-bounded, because the
    inner walk stops at the session boundary.
    """
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
    entries: list[tuple[int, str, float]] = []  # (index, direction, take_profit)
    for ctx in replay.iter_contexts():
        # 같은 프로토콜 간극 — 위 호출의 주석 참조.
        signal = setup.check(ctx)  # type: ignore[arg-type]
        contexts.append(ctx)
        if signal is not None:
            entries.append((len(contexts) - 1, signal.direction, signal.take_profit))

    # Buckets are disjoint and exhaustive, and a "lead" is a number only when
    # BOTH rules triggered inside the session. The first draft measured the
    # frozen-never case to the end of the whole SERIES and reported a
    # 32591-bar maximum — not a quantity about any session.
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
