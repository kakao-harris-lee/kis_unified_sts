"""Setup C — Event Reaction entry signal generator.

Logic overview (spec §5.1)
--------------------------
1. Find a qualifying ScheduledEvent within ``window_minutes`` of *now* via
   :meth:`MarketContext.find_recent_event`.
2. Deduplicate via :class:`EventTradeTracker`: if ``event_id`` was already
   traded, return ``None``.
3. 15-minute-range breakout check:

   - **Long**: ``current_price > last_15min_high`` **and**
     ``(current_price - last_15min_high) < breakout_buffer_atr_mult × ATR14``
   - **Short**: ``current_price < last_15min_low`` **and**
     ``(last_15min_low - current_price) < breakout_buffer_atr_mult × ATR14``
   - Otherwise → ``None``

4. Target: ``entry ± target_atr_mult × ATR14`` (long = ``+``, short = ``-``).
5. Confidence: ``0.65 + 0.1 × (3 - impact_tier) / 2``
   (tier 1 → 0.75; tier 2 → 0.70; tier 3 → 0.65).
6. ``reason_tags = [f"event_{event_type}", f"tier_{tier}", "breakout_15m"]``.
7. Mark ``event_id`` via :meth:`EventTradeTracker.mark` **before** returning the
   Signal to prevent duplicate entries on subsequent ticks for the same event.

Persistence note
----------------
:class:`EventTradeTracker` is **in-memory only**.  Phase 3 backtesting does not
require Redis persistence — the tracker lives as long as the setup instance.
Phase 4 will add a Redis-backed variant when live paper-trading is introduced.
"""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.decision.context import MarketContext, ScheduledEvent
from shared.decision.setup_base import Setup
from shared.decision.signal import Signal

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class SetupCConfig(ServiceConfigBase):
    """Configuration for :class:`SetupCEventReaction`.

    All numeric thresholds are read from ``config/decision_engine.yaml`` under
    the ``setup_c_event_reaction`` section.  Defaults match spec §5.2 exactly
    so that unit tests can construct ``SetupCConfig()`` without a YAML file.
    """

    _default_config_file: ClassVar[str] = "decision_engine.yaml"
    _default_section: ClassVar[str] = "setup_c_event_reaction"

    enabled: bool = Field(default=True, description="Enable/disable this setup")
    window_minutes: int = Field(
        default=15,
        description="Look-back window in minutes: events older than this are ignored",
    )
    breakout_buffer_atr_mult: float = Field(
        default=0.5,
        description=(
            "Breakout must be within this many ATRs of the 15-min high/low "
            "(prevents chasing a move that has already extended too far)"
        ),
    )
    target_atr_mult: float = Field(
        default=2.5,
        description="Take-profit = entry ± target_atr_mult × ATR14",
    )
    signal_ttl_minutes: int = Field(
        default=30,
        description="Signal validity window in minutes",
    )
    min_impact_tier: int = Field(
        default=2,
        description=(
            "Ignore events with impact_tier > this value "
            "(1 = top tier, 3 = minor; default=2 means tier-3 events are skipped)"
        ),
    )
    stop_buffer_atr_mult: float = Field(
        default=0.5,
        description=(
            "Extra cushion (in ATRs) placed BEYOND the opposite 15-min range edge "
            "for the protective stop. The raw stop sits at the range edge, which is "
            "only ~1.3× 1-min ATR away → whipsawed out in minutes on a failed "
            "breakout. This buffer widens it so normal post-breakout pullback does "
            "not trigger an immediate stop."
        ),
    )
    no_entry_after_minutes_since_open: int = Field(
        default=360,
        description=(
            "No new entries after this many minutes since the 09:00 KST open "
            "(360 = 15:00 KST). Prevents late-session entries that would be "
            "force-closed at the 15:45 session close → churn/slippage."
        ),
    )


# ---------------------------------------------------------------------------
# In-memory event deduplication tracker
# ---------------------------------------------------------------------------


class EventTradeTracker:
    """In-memory deduplication guard for Setup C.

    Ensures that only one trade is triggered per ``event_id``, even if the
    breakout condition remains true across multiple ticks after the initial
    signal is emitted.

    Implementation note — Phase 3 only
    ------------------------------------
    This is an **in-memory** implementation intended for backtest use.  It does
    **not** persist state to Redis or any external store.  Phase 4 will
    introduce a ``RedisEventTradeTracker`` when live paper-trading requires
    cross-process deduplication.
    """

    def __init__(self) -> None:
        self._traded: set[str] = set()

    def already_traded(self, event_id: str) -> bool:
        """Return ``True`` if *event_id* has already been traded."""
        return event_id in self._traded

    def mark(self, event_id: str) -> None:
        """Mark *event_id* as traded (idempotent)."""
        self._traded.add(event_id)


# ---------------------------------------------------------------------------
# Setup C — Event Reaction
# ---------------------------------------------------------------------------


class SetupCEventReaction(Setup):
    """Event-reaction entry signal generator (Setup C).

    Fires when a high-impact macro event occurred recently and the price
    subsequently breaks out of the 15-minute post-announcement trading range —
    acting as a momentum confirmation of the market's reaction direction.

    Usage::

        setup = SetupCEventReaction()                        # uses YAML defaults
        setup = SetupCEventReaction(config=my_cfg)           # inject config
        setup = SetupCEventReaction(config=my_cfg,
                                     tracker=my_tracker)    # inject both

        signal = setup.check(ctx)   # returns Signal | None
    """

    CONFIG_CLASS = SetupCConfig

    def __init__(
        self,
        *,
        config: SetupCConfig | None = None,
        tracker: EventTradeTracker | None = None,
    ) -> None:
        """Initialise with optional pre-built config and/or tracker.

        Parameters
        ----------
        config:
            A :class:`SetupCConfig` instance.  If ``None``, ``SetupCConfig()``
            is instantiated with its spec defaults (no YAML load).
        tracker:
            An :class:`EventTradeTracker` instance.  If ``None``, a fresh
            in-memory tracker is created automatically.
        """
        super().__init__(config=config)
        self._tracker = tracker if tracker is not None else EventTradeTracker()

    # Expose tracker for external inspection / injection (e.g. tests)
    @property
    def tracker(self) -> EventTradeTracker:
        return self._tracker

    # ------------------------------------------------------------------
    # Core entry check
    # ------------------------------------------------------------------

    def check(self, ctx: MarketContext) -> Signal | None:  # noqa: PLR0911
        """Evaluate *ctx* and return a Signal when all conditions are met.

        Returns ``None`` as soon as any condition fails (early-return pattern).
        """
        c = self.config

        # 0. Late-session entry cutoff (KST-anchored via minutes_since_open).
        #    No new entries after no_entry_after_minutes_since_open (360 = 15:00
        #    KST) so a late breakout isn't opened minutes before the 15:45 close
        #    and force-liquidated → churn.
        if ctx.minutes_since_open() > c.no_entry_after_minutes_since_open:
            return None

        # 1. Look for a qualifying scheduled event within the window
        recent_event: ScheduledEvent | None = ctx.find_recent_event(
            window_minutes=c.window_minutes,
            min_tier=c.min_impact_tier,
        )
        if recent_event is None:
            return None

        # 2. Deduplication guard — one trade per event_id
        if self._tracker.already_traded(recent_event.event_id):
            return None

        # 3. 15-minute-range breakout check
        atr = ctx.atr_14
        buffer = c.breakout_buffer_atr_mult * atr

        stop_cushion = c.stop_buffer_atr_mult * atr
        if (
            ctx.current_price > ctx.last_15min_high
            and (ctx.current_price - ctx.last_15min_high) < buffer
        ):
            direction = "long"
            entry = ctx.current_price
            # Stop below the opposite (low) edge, with a cushion so a normal
            # pullback into the range doesn't immediately trigger it.
            stop = ctx.last_15min_low - stop_cushion
        elif (
            ctx.current_price < ctx.last_15min_low
            and (ctx.last_15min_low - ctx.current_price) < buffer
        ):
            direction = "short"
            entry = ctx.current_price
            stop = ctx.last_15min_high + stop_cushion
        else:
            return None

        # 4. Take-profit target
        if direction == "long":
            target = entry + c.target_atr_mult * atr
        else:
            target = entry - c.target_atr_mult * atr

        # 5. Confidence: 0.65 + 0.1 * (3 - tier) / 2
        confidence = 0.65 + 0.1 * (3 - recent_event.impact_tier) / 2

        # 6. Reason tags
        reason_tags = [
            f"event_{recent_event.event_type}",
            f"tier_{recent_event.impact_tier}",
            "breakout_15m",
        ]

        # 7. Mark as traded BEFORE returning the signal
        self._tracker.mark(recent_event.event_id)

        return Signal(
            setup_type="C_event_reaction",
            direction=direction,
            symbol=ctx.symbol,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=confidence,
            reason_tags=reason_tags,
            valid_until=ctx.now + timedelta(minutes=c.signal_ttl_minutes),
            generated_at=ctx.now,
        )
