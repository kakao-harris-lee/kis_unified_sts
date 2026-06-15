"""Setup A — Gap Reversion entry signal generator.

Logic overview (spec §4.1)
--------------------------
1. Time window: signal only fires between ``valid_minutes_min`` and
   ``valid_minutes_max`` minutes after the 09:00 KST market open.
2. Overnight macro confirmation: ``macro_overnight`` must be present and
   ``abs(sp500_change_pct) >= min_sp500_gap_pct``.
3. Korean open gap: ``abs(gap_pct) >= min_kr_gap_pct`` where
   ``gap_pct = (today_open - prev_close) / prev_close * 100``.
4. Direction alignment: sign of SP500 overnight change must match sign of the
   Korean open gap.
5. Retrace in band ``[retrace_min, retrace_max]``:
   - Gap-UP  (``gap_pct > 0``): retrace from the high;  direction = "long"
   - Gap-DOWN (``gap_pct < 0``): retrace from the low;  direction = "short"
6. Emit :class:`shared.decision.signal.Signal` with entry/stop/target computed
   from the ATR and gap-fill target.

Confidence formula (spec §4.3)
-------------------------------
``confidence = min(1.0, 0.5 + gap_strength + retrace_centrality)``

where::

    gap_strength    = min(abs(sp500_pct) / 1.5, 0.3)                # up to +0.3
    retrace_cent    = 0.2 * (1 - abs(retrace - mid) / half)         # up to +0.2
    mid             = (retrace_min + retrace_max) / 2               # band centre
    half            = (retrace_max - retrace_min) / 2               # band half-width
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.decision.context import MarketContext
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal


class SetupAConfig(ServiceConfigBase):
    """Configuration for :class:`SetupAGapReversion`.

    All numeric thresholds read from ``config/decision_engine.yaml`` under the
    ``setup_a_gap_reversion`` section.  Defaults match spec §4.2 exactly so
    that unit-tests can construct ``SetupAConfig()`` without a YAML file.
    """

    _default_config_file: ClassVar[str] = "decision_engine.yaml"
    _default_section: ClassVar[str] = "setup_a_gap_reversion"

    enabled: bool = Field(default=True, description="Enable/disable this setup")
    valid_minutes_min: int = Field(
        default=10, description="Earliest minutes after open to fire (inclusive)"
    )
    valid_minutes_max: int = Field(
        default=120, description="Latest minutes after open to fire (inclusive)"
    )
    min_sp500_gap_pct: float = Field(
        default=0.3, description="Minimum absolute S&P 500 overnight gap (%)"
    )
    min_kr_gap_pct: float = Field(
        default=0.2, description="Minimum absolute Korean open gap vs prev close (%)"
    )
    retrace_min: float = Field(
        default=0.20, description="Minimum retrace ratio of the gap (fraction)"
    )
    retrace_max: float = Field(
        default=0.70, description="Maximum retrace ratio of the gap (fraction)"
    )
    stop_atr_mult: float = Field(
        default=1.5, description="ATR multiplier for the hard stop-loss"
    )
    target_gap_fill_ratio: float = Field(
        default=0.9,
        description="Fraction of the gap to fill as the take-profit target",
    )
    signal_ttl_minutes: int = Field(
        default=10, description="Signal validity window in minutes"
    )


class SetupAGapReversion(Setup):
    """Gap-reversion entry signal generator.

    Fires when an overnight macro shock drove the Korean index to gap open in
    the same direction, and the price has partially retraced (meaning mean-
    reversion is beginning) but not yet filled the gap.

    Usage::

        setup = SetupAGapReversion()                # uses YAML defaults
        setup = SetupAGapReversion(config=my_cfg)   # inject pre-built config

        signal = setup.check(ctx)   # returns Signal | None
    """

    CONFIG_CLASS = SetupAConfig

    # Why the last check() returned None (observability — answers "why no
    # Setup A trade today"). Set at every reject gate; None after a fired signal.
    last_reject_reason: str | None = None

    # ------------------------------------------------------------------
    # Core entry check
    # ------------------------------------------------------------------

    def _reject(self, reason: str) -> None:
        """Record the rejection reason and return None (early-return helper)."""
        self.last_reject_reason = reason
        return None

    def check(self, ctx: MarketContext) -> Signal | None:  # noqa: PLR0911
        """Evaluate *ctx* and return a Signal when all conditions are met.

        Returns ``None`` as soon as any condition fails (early-return pattern).
        """
        c = self.config

        # 1. Time window guard
        minutes_since_open = ctx.minutes_since_open()
        if not (c.valid_minutes_min <= minutes_since_open <= c.valid_minutes_max):
            return self._reject(
                f"outside_time_window({minutes_since_open:.0f}m"
                f"∉[{c.valid_minutes_min},{c.valid_minutes_max}])"
            )

        # 2. Overnight macro confirmation
        if ctx.macro_overnight is None:
            return self._reject("no_macro_overnight")
        sp500_pct: float = ctx.macro_overnight.sp500_change_pct  # type: ignore[union-attr]
        if sp500_pct is None:
            return self._reject("no_sp500_data")
        if abs(sp500_pct) < c.min_sp500_gap_pct:
            return self._reject(
                f"sp500_gap_below_min({abs(sp500_pct):.2f}<{c.min_sp500_gap_pct})"
            )

        # 3. Korean open gap
        if ctx.prev_close <= 0:
            return self._reject("no_prev_close")
        gap_pct = (ctx.today_open - ctx.prev_close) / ctx.prev_close * 100
        if abs(gap_pct) < c.min_kr_gap_pct:
            return self._reject(
                f"kr_gap_below_min({abs(gap_pct):.2f}<{c.min_kr_gap_pct})"
            )

        # 4. Alignment check: overnight SP500 direction must match the KR gap
        if math.copysign(1.0, sp500_pct) != math.copysign(1.0, gap_pct):
            return self._reject(
                f"sp500_kr_gap_misaligned(sp500={sp500_pct:+.2f},gap={gap_pct:+.2f})"
            )

        # 5. Retrace band check
        if gap_pct > 0:
            # Gap-UP: price fell back from the high → buy the dip ("long")
            gap_magnitude = ctx.today_open - ctx.prev_close  # positive
            if gap_magnitude <= 0:
                return self._reject("no_gap_up_magnitude")
            retrace = (ctx.today_open - ctx.current_price) / gap_magnitude
            direction = "long"
        else:
            # Gap-DOWN: price bounced up from the low → short the bounce ("short")
            gap_magnitude = ctx.prev_close - ctx.today_open  # positive
            if gap_magnitude <= 0:
                return self._reject("no_gap_down_magnitude")
            retrace = (ctx.current_price - ctx.today_open) / gap_magnitude
            direction = "short"

        if not (c.retrace_min <= retrace <= c.retrace_max):
            return self._reject(
                f"retrace_out_of_band({retrace:.2f}∉[{c.retrace_min},{c.retrace_max}])"
            )

        # 6. Build Signal
        atr = ctx.atr_14
        entry = ctx.current_price

        if direction == "long":
            stop = entry - c.stop_atr_mult * atr
        else:
            stop = entry + c.stop_atr_mult * atr

        # Target: fill ``target_gap_fill_ratio`` of the gap back toward prev_close
        # formula: prev_close + (today_open - prev_close) * target_gap_fill_ratio
        target = (
            ctx.prev_close + (ctx.today_open - ctx.prev_close) * c.target_gap_fill_ratio
        )

        confidence = self._compute_confidence(retrace, sp500_pct)

        self.last_reject_reason = None  # fired — clear any prior reject reason
        return Signal(
            setup_type="A_gap_reversion",
            direction=direction,
            symbol=ctx.symbol,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            reason_tags=[
                f"sp500_gap_{sp500_pct:+.2f}%",
                f"kr_gap_{gap_pct:+.2f}%",
                f"retrace_{retrace:.2%}",
            ],
            valid_until=ctx.now + timedelta(minutes=c.signal_ttl_minutes),
            generated_at=ctx.now,
        )

    # ------------------------------------------------------------------
    # Confidence formula (spec §4.3)
    # ------------------------------------------------------------------

    def _compute_confidence(self, retrace: float, sp500_pct: float) -> float:
        """Compute a [0.5, 1.0] confidence score.

        Components
        ----------
        base            = 0.5
        gap_strength    = min(abs(sp500_pct) / 1.5, 0.3)           # max +0.3
        retrace_cent    = 0.2 * (1 - abs(retrace - mid) / half)    # max +0.2

        The retrace midpoint and half-width are derived from the config's
        retrace band [retrace_min, retrace_max] so that confidence peaks at
        the band centre and tapers linearly toward the edges.
        """
        base = 0.5
        gap_strength = min(abs(sp500_pct) / 1.5, 0.3)

        # Derive centrality from the configured retrace band
        mid = (self.config.retrace_min + self.config.retrace_max) / 2.0
        half = (self.config.retrace_max - self.config.retrace_min) / 2.0
        if half <= 0:
            half = 0.125  # fallback to original

        retrace_centrality = 0.2 * (1 - abs(retrace - mid) / half)
        # Clamp retrace_centrality at 0 to avoid penalizing the base score
        # for edge-band retraces (defensive, belt-and-suspenders).
        retrace_centrality = max(0.0, retrace_centrality)
        return min(1.0, base + gap_strength + retrace_centrality)
