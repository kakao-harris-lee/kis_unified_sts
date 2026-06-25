"""Setup D — High-Vol Intraday VWAP Reversion entry signal generator.

Thesis (extends the proven Setup A/C mean-reversion edge)
---------------------------------------------------------
Intraday KOSPI200 futures mean-revert (Setup A/C work). Setup A only fires in a
narrow open-only window (10–60 min after 09:00 KST) and requires an overnight
gap, so on a high-volatility *intraday* day with no overnight gap it produces 0
trades while large intraday reversions go uncaptured. Setup D fades volatility
extremes **throughout the session** (long/short symmetric) and is gated to be
most active on volatile days and quiet on dead days.

Logic overview
--------------
1. **Session window**: ``valid_minutes_min <= minutes_since_open <=
   no_entry_after_minutes_since_open``. Skips the opening-auction noise and
   avoids late entries that would be force-closed near the 15:45 KST session
   close.
2. **High-vol regime gate**: ``atr_14 >= min_atr_ratio * atr_90th_percentile``.
   ``atr_90th_percentile`` is the high-vol reference for the instrument (the
   replay/orchestrator both populate it). A ratio near/above 1.0 means "this bar
   is in the upper tail of the volatility distribution" — i.e. trade only when
   the market is actually moving. This is the filter that keeps the setup quiet
   on dead days.
3. **VWAP extension extreme** (the fade trigger). Measure how far price has
   stretched from the session VWAP in ATR units::

       z = (current_price - vwap) / atr_14

   - ``z >= extreme_atr_mult``  → price stretched far ABOVE VWAP → **short** the
     up-spike (fade back toward VWAP).
   - ``z <= -extreme_atr_mult`` → price stretched far BELOW VWAP → **long** the
     down-spike.
   - otherwise → no signal.
4. **Stall confirmation** (avoid the falling knife / trend-day runaway). Require
   that the spike has *paused* rather than still extending: the current price
   must be within ``stall_buffer_atr_mult * atr_14`` of the prior 15-minute
   extreme on the spike side (``last_15min_high`` for a short, ``last_15min_low``
   for a long). A bar that has blown clean through the 15-min extreme by more
   than the buffer is still trending — we skip it.
5. **Risk bracket** (ATR-scaled, symmetric):

   - stop  = ``entry ± stop_atr_mult * atr_14``     (long ``-``, short ``+``)
   - target = revert toward VWAP, but at least ``min_reward_risk`` × risk away
     so a marginal extension does not produce a near-zero target::

         risk          = stop_atr_mult * atr_14
         vwap_distance  = abs(entry - vwap)
         target_distance = max(vwap_distance, min_reward_risk * risk)
         target = entry ∓ target_distance      (long toward higher, short lower)

Confidence
----------
``confidence = clip(base + vol_bonus + extension_bonus, [0.5, 1.0])`` where a
more extreme z and a higher vol regime both raise confidence::

    base            = 0.5
    extension_bonus = min((abs(z) - extreme_atr_mult) * extension_conf_scale, 0.3)
    vol_bonus       = min((vol_ratio - min_atr_ratio) * vol_conf_scale, 0.2)

Observability
-------------
``last_reject_reason`` records WHY ``check`` returned ``None`` (mirrors Setup
A/C) so "why no Setup D trade this cycle?" is answerable at a glance.

Symmetry
--------
Long and short are exact mirrors — direction follows the sign of the VWAP
extension only. No directional bias is hard-coded (futures long/short symmetry
is a non-negotiable repo rule).
"""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal


class SetupDConfig(ServiceConfigBase):
    """Configuration for :class:`SetupDVWAPReversion`.

    All numeric thresholds read from ``config/decision_engine.yaml`` under the
    ``setup_d_vwap_reversion`` section. Defaults are chosen from the Dec2025–
    Apr2026 research spike operating point (extreme≈1.8, vol-ratio≈0.7) where the
    edge is distributed across months and balanced long/short — not the tighter
    single-month-concentrated point. They let unit tests construct
    ``SetupDConfig()`` without a YAML file.
    """

    _default_config_file: ClassVar[str] = "decision_engine.yaml"
    _default_section: ClassVar[str] = "setup_d_vwap_reversion"

    enabled: bool = Field(default=True, description="Enable/disable this setup")
    valid_minutes_min: int = Field(
        default=15,
        description="Earliest minutes after 09:00 KST open to fire (skip open auction)",
    )
    no_entry_after_minutes_since_open: int = Field(
        default=345,
        description=(
            "No new entries after this many minutes since 09:00 KST "
            "(345 = 14:45). Avoids late entries force-closed near the 15:45 close."
        ),
    )
    min_atr_ratio: float = Field(
        default=0.7,
        description=(
            "High-vol regime gate: require atr_14 >= min_atr_ratio * "
            "atr_90th_percentile. Higher = more selective (only the most volatile "
            "bars). 0 disables the gate."
        ),
    )
    extreme_atr_mult: float = Field(
        default=1.8,
        description=(
            "Fade trigger: abs((price - vwap)/atr_14) must reach this many ATRs "
            "for the VWAP extension to count as an extreme."
        ),
    )
    stall_buffer_atr_mult: float = Field(
        default=1.0,
        description=(
            "Trend-day guard: the spike price must be within this many ATRs of "
            "the prior 15-min extreme on the spike side (still near it, i.e. "
            "stalling — not blown clean through and still trending). Set high to "
            "effectively disable."
        ),
    )
    stop_atr_mult: float = Field(
        default=1.5, description="Hard stop = entry ± stop_atr_mult × ATR14"
    )
    min_reward_risk: float = Field(
        default=1.0,
        description=(
            "Floor on the reward/risk of the VWAP-revert target. target_distance "
            "= max(|entry-vwap|, min_reward_risk × risk)."
        ),
    )
    signal_ttl_minutes: int = Field(
        default=10, description="Signal validity window in minutes"
    )
    extension_conf_scale: float = Field(
        default=0.3,
        description="Confidence slope per extra ATR of extension beyond the trigger",
    )
    vol_conf_scale: float = Field(
        default=0.3,
        description="Confidence slope per unit of vol_ratio above min_atr_ratio",
    )


class SetupDVWAPReversion(Setup):
    """High-vol intraday VWAP-reversion entry signal generator (Setup D).

    Fires when, on a volatile intraday bar, price has stretched an extreme
    distance (in ATR units) from the session VWAP and stalled near a recent
    extreme — fading the spike back toward VWAP. Long/short symmetric.

    Usage::

        setup = SetupDVWAPReversion()               # uses defaults
        setup = SetupDVWAPReversion(config=my_cfg)   # inject config
        signal = setup.check(ctx)                    # returns Signal | None
    """

    CONFIG_CLASS = SetupDConfig

    # Why the last check() returned None (observability; None after a fired
    # signal). Mirrors Setup A/C.
    last_reject_reason: str | None = None

    def _reject(self, reason: str) -> None:
        """Record the rejection reason and return None (early-return helper)."""
        self.last_reject_reason = reason
        return None

    def check(self, ctx: MarketContext) -> Signal | None:  # noqa: PLR0911
        """Evaluate *ctx* and return a Signal when all conditions are met.

        Returns ``None`` as soon as any condition fails (early-return pattern).
        """
        c = self.config

        # 1. Session window guard
        minutes_since_open = ctx.minutes_since_open()
        if minutes_since_open < c.valid_minutes_min:
            return self._reject(
                f"before_window({minutes_since_open:.0f}m<{c.valid_minutes_min})"
            )
        if minutes_since_open > c.no_entry_after_minutes_since_open:
            return self._reject(
                f"after_cutoff({minutes_since_open:.0f}m>"
                f"{c.no_entry_after_minutes_since_open})"
            )

        # 2. Inputs must be usable
        atr = ctx.atr_14
        if atr <= 0:
            return self._reject("no_atr")
        if ctx.current_price <= 0:
            return self._reject("no_price")

        # 3. High-vol regime gate
        if c.min_atr_ratio > 0:
            if ctx.atr_90th_percentile <= 0:
                return self._reject("no_vol_reference")
            vol_ratio = atr / ctx.atr_90th_percentile
            if vol_ratio < c.min_atr_ratio:
                return self._reject(
                    f"vol_below_gate({vol_ratio:.2f}<{c.min_atr_ratio})"
                )
        else:
            vol_ratio = (
                atr / ctx.atr_90th_percentile if ctx.atr_90th_percentile > 0 else 0.0
            )

        # 4. VWAP extension extreme (the fade trigger)
        z = (ctx.current_price - ctx.vwap) / atr
        if z >= c.extreme_atr_mult:
            direction = "short"  # fade the up-spike back toward VWAP
        elif z <= -c.extreme_atr_mult:
            direction = "long"  # fade the down-spike back toward VWAP
        else:
            return self._reject(f"not_extreme(z={z:+.2f},need±{c.extreme_atr_mult})")

        # 5. Stall confirmation — spike must be near (not blown through) the
        #    prior 15-min extreme on its side, so we fade a stalling spike, not
        #    a still-trending runaway.
        buffer = c.stall_buffer_atr_mult * atr
        if direction == "short":
            # price above the band; require it to be within `buffer` ABOVE the
            # prior 15-min high (close to it / just poking through, not far past)
            if ctx.current_price - ctx.last_15min_high > buffer:
                return self._reject(
                    f"still_trending_up(px={ctx.current_price:.2f}-"
                    f"hi={ctx.last_15min_high:.2f}>{buffer:.2f})"
                )
        else:
            if ctx.last_15min_low - ctx.current_price > buffer:
                return self._reject(
                    f"still_trending_down(lo={ctx.last_15min_low:.2f}-"
                    f"px={ctx.current_price:.2f}>{buffer:.2f})"
                )

        # 6. Risk bracket (ATR-scaled, symmetric)
        entry = ctx.current_price
        risk = c.stop_atr_mult * atr
        vwap_distance = abs(entry - ctx.vwap)
        target_distance = max(vwap_distance, c.min_reward_risk * risk)

        if direction == "long":
            stop = entry - risk
            target = entry + target_distance
        else:
            stop = entry + risk
            target = entry - target_distance

        confidence = self._compute_confidence(z, vol_ratio)

        self.last_reject_reason = None  # fired — clear any prior reject reason
        return Signal(
            setup_type="D_vwap_reversion",
            direction=direction,
            symbol=ctx.symbol,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            reason_tags=[
                f"vwap_z_{z:+.2f}",
                f"vol_ratio_{vol_ratio:.2f}",
                "highvol_vwap_reversion",
            ],
            valid_until=ctx.now + timedelta(minutes=c.signal_ttl_minutes),
            generated_at=ctx.now,
        )

    def _compute_confidence(self, z: float, vol_ratio: float) -> float:
        """Compute a [0.5, 1.0] confidence score.

        Components
        ----------
        base            = 0.5
        extension_bonus = min((|z| - extreme_atr_mult) * extension_conf_scale, 0.3)
        vol_bonus       = min((vol_ratio - min_atr_ratio) * vol_conf_scale, 0.2)

        A more extreme stretch from VWAP and a higher vol regime both raise
        confidence; both bonuses are clamped at 0 so an edge-of-band signal does
        not depress the base.
        """
        c = self.config
        base = 0.5
        extension_bonus = max(
            0.0,
            min((abs(z) - c.extreme_atr_mult) * c.extension_conf_scale, 0.3),
        )
        vol_bonus = max(0.0, min((vol_ratio - c.min_atr_ratio) * c.vol_conf_scale, 0.2))
        return min(1.0, base + extension_bonus + vol_bonus)
