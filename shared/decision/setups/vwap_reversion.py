"""Setup D — High-Vol Intraday VWAP Reversion entry signal generator.

Thesis (extends the proven Setup A/C mean-reversion edge)
---------------------------------------------------------
Intraday KOSPI200 futures mean-revert (Setup A/C work). Setup A only fires in a
narrow open-only window (10–90 min after 08:45 KST) and requires an overnight
gap, so on a high-volatility *intraday* day with no overnight gap it produces 0
trades while large intraday reversions go uncaptured. Setup D fades volatility
extremes **throughout the session** (long/short symmetric) and is gated to be
most active on volatile days and quiet on dead days.

Logic overview
--------------
1. **Session window**: ``valid_minutes_min <= minutes_since_open <=
   no_entry_after_minutes_since_open``. Skips the opening-auction noise (first
   15 min = 08:45–09:00 KST) and avoids late entries that would be force-closed
   near the 15:45 KST session close.
2. **High-vol regime gate**: ``atr_14 >= min_atr_ratio * vol_reference``, where
   ``vol_reference`` is the **causal** ``vol_percentile`` (default 90th) of a
   rolling window of recent ATRs that the setup computes **itself** from the
   ``atr_14`` it receives each bar (``vol_window_bars``, reset per KST day). The
   reference uses only ATRs observed at or BEFORE the current bar — no
   look-ahead — and the gate is permissive during warmup (< ``vol_warmup_bars``
   observations) so the setup is never silently dead. A ratio near/above 1.0
   means "this bar is in the upper tail of the session's volatility" — trade
   only when the market is actually moving; quiet on dead days. The setup owns
   this computation end to end (it does NOT read the context's
   ``atr_90th_percentile`` — that field is look-ahead in the backtest replay and
   has no live producer), so the gate behaves identically in backtest and live.
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
   must be within ``stall_buffer_atr_mult * atr_14`` of the prior recent extreme
   on the spike side (the recent high for a short, the recent low for a long). A
   bar that has blown clean through that extreme by more than the buffer is still
   trending — we skip it. The recent extreme is a **causal self-computed** range
   over the last ``range_window_bars`` closes (``_self_range``) — the setup does
   NOT read ``ctx.last_15min_high/low``, which has no producer in the live
   orchestrator path (it would default to ``current_price`` → the guard would
   silently never fire live while it was active in backtest). Closes are used
   rather than bar highs/lows because the ``MarketContext`` carries no per-bar
   high/low; this keeps the guard identical in backtest and live.
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

from collections import deque
from datetime import date, timedelta
from typing import ClassVar

import numpy as np
from pydantic import Field

from shared.config.base import ServiceConfigBase
from shared.decision.interfaces import FuturesMarketView
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
        description="Earliest minutes after 08:45 KST open to fire (15 = 09:00 KST; skip open auction)",
    )
    no_entry_after_minutes_since_open: int = Field(
        default=360,
        description=(
            "No new entries after this many minutes since 08:45 KST "
            "(360 = 14:45 KST). Avoids late entries force-closed near the 15:45 close."
        ),
    )
    min_atr_ratio: float = Field(
        default=0.9,
        description=(
            "High-vol regime gate: require atr_14 >= min_atr_ratio * "
            "vol_reference, where vol_reference is the CAUSAL trailing "
            "vol_percentile of recent ATRs (self-computed by the setup from the "
            "atr_14 it receives each bar — see vol_window_bars / vol_warmup_bars). "
            "Higher = more selective (only the most volatile bars). 0 disables "
            "the gate."
        ),
    )
    vol_window_bars: int = Field(
        default=780,
        description=(
            "Causal trailing window (bars) over which the high-vol reference "
            "percentile is computed from past ATRs. ~780 = two KOSPI day sessions. "
            "The window holds only ATRs observed at or before the current bar "
            "(no look-ahead) and is NOT reset per day (a per-day reset leaves too "
            "few early-session observations to be a meaningful percentile)."
        ),
    )
    vol_warmup_bars: int = Field(
        default=120,
        description=(
            "Minimum past-ATR observations before the high-vol gate activates. "
            "Below this the gate is PERMISSIVE (does not block) so the setup is "
            "not silently dead during warmup."
        ),
    )
    vol_percentile: float = Field(
        default=90.0,
        ge=0.0,
        le=100.0,
        description=(
            "Percentile of the causal ATR window used as the high-vol reference "
            "(90 = upper-tail volatility). Mirrors the legacy atr_90th_percentile."
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
    range_window_bars: int = Field(
        default=15,
        description=(
            "Number of PRIOR 1-min closes used for the self-computed recent-range "
            "(stall guard). ~15 = a 15-minute range. The setup self-computes this "
            "from the per-bar close (current_price) — it does NOT read the "
            "context's last_15min_high/low, which has no live producer in the "
            "orchestrator path. Closes (not bar highs/lows) are used because the "
            "MarketContext carries no per-bar high/low; this keeps the guard "
            "identical in backtest and live."
        ),
    )
    range_warmup_bars: int = Field(
        default=5,
        description=(
            "Minimum prior closes before the stall guard activates. Below this "
            "the guard is PERMISSIVE (does not block) — there is no meaningful "
            "recent range yet (e.g. first minutes after the open)."
        ),
    )
    extension_conf_scale: float = Field(
        default=0.3,
        description="Confidence slope per extra ATR of extension beyond the trigger",
    )
    vol_conf_scale: float = Field(
        default=0.3,
        description="Confidence slope per unit of vol_ratio above min_atr_ratio",
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum confidence gate applied after _compute_confidence(). "
            "Signals below this threshold are rejected with low_confidence. "
            "0.0 disables the gate."
        ),
    )
    reversal_confirm_enabled: bool = Field(
        default=False,
        description=(
            "Require the VWAP extension to start reverting before firing. "
            "This turns the setup from an immediate fade into an armed-then-confirmed "
            "fade while preserving long/short symmetry."
        ),
    )
    reversal_confirm_atr_mult: float = Field(
        default=0.2,
        ge=0.0,
        description=(
            "Minimum improvement in abs(z) versus the prior close before a confirmed "
            "signal can fire. z is measured in ATR units."
        ),
    )
    reversal_confirm_requires_price_turn: bool = Field(
        default=True,
        description=(
            "When reversal confirmation is enabled, require price to move back "
            "toward VWAP versus the prior close."
        ),
    )
    trend_filter_enabled: bool = Field(
        default=False,
        description=(
            "Master switch for the session-VWAP-slope trend gate. When enabled, "
            "a COUNTER-trend fade on a strongly trending session is blocked "
            "unless the VWAP stretch is climactic (see "
            "against_trend_extreme_atr_mult). Ships off so activation is an "
            "explicit, validated config flip. Long/short symmetric."
        ),
    )
    trend_window_bars: int = Field(
        default=30,
        description=(
            "Trailing window (bars) of session VWAP values over which the trend "
            "score (net VWAP drift in ATR units) is computed. ~30 = 30 minutes. "
            "Reset per KST session date (day-only futures)."
        ),
    )
    trend_warmup_bars: int = Field(
        default=10,
        description=(
            "Minimum VWAP observations before the trend gate activates. Below "
            "this the gate is PERMISSIVE (does not block) — no meaningful "
            "session trend yet (e.g. the first minutes after the open)."
        ),
    )
    trend_block_threshold: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Block a counter-trend fade only when abs(trend_score) >= this many "
            "ATRs of net VWAP drift over the window. Higher = only block on the "
            "strongest trend days."
        ),
    )
    against_trend_extreme_atr_mult: float = Field(
        default=2.6,
        description=(
            "Climax override: a counter-trend fade is allowed anyway when "
            "abs(z) >= this many ATRs (a climactic flush = the mean-reversion "
            "edge). Effectively clamped to >= extreme_atr_mult at runtime so the "
            "override can never be looser than the fade trigger itself."
        ),
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

    def __init__(self, *, config: SetupDConfig | None = None) -> None:
        super().__init__(config=config)
        # Why the last check() returned None (observability; None after a fired
        # signal). Mirrors Setup A/C.
        self.last_reject_reason: str | None = None
        # Causal rolling ATR history for the self-computed high-vol reference.
        # Holds only ATRs observed at or before the current bar (no look-ahead),
        # as a trailing window that spans ~2 sessions so the reference is a
        # stable recent-volatility baseline (a per-day reset leaves too few
        # early-session observations to be a meaningful percentile).
        self._atr_window: deque[float] = deque(maxlen=self.config.vol_window_bars)
        # Causal rolling window of recent CLOSES for the self-computed recent
        # range (stall guard). Holds only closes observed at or before the
        # current bar — the current close is appended AFTER reading the range, so
        # the range never includes the bar it is evaluating (strictly causal).
        # Closes are used (not bar high/low) because the MarketContext exposes no
        # per-bar high/low; this is the only range definition reproducible in the
        # orchestrator path, where last_15min_high/low has no live producer.
        self._close_window: deque[float] = deque(maxlen=self.config.range_window_bars)
        # Causal rolling window of session VWAP values for the trend gate. Holds
        # only VWAPs observed at or before the current bar (appended AFTER the
        # read) and is reset per KST session date (day-only futures) so the
        # overnight gap never enters the slope. See ``_trend_score``.
        self._vwap_window: deque[float] = deque(maxlen=self.config.trend_window_bars)
        self._trend_session_date: date | None = None
        self.last_signal_details: dict[str, float | int | bool | str | None] = {}

    def _reject(self, reason: str) -> None:
        """Record the rejection reason and return None (early-return helper)."""
        self.last_reject_reason = reason
        return None

    def _vol_reference(self, atr: float) -> float | None:
        """Return the causal high-vol reference for the gate, or None during warmup.

        Self-computes the ``vol_percentile`` (default 90th) of a trailing window
        of recent ATRs built from PAST bars only (``vol_window_bars`` ≈ 2
        sessions; no per-day reset — that leaves too few early-session
        observations to be a meaningful percentile). During warmup (fewer than
        ``vol_warmup_bars`` observations) returns ``None`` so the caller treats
        the gate as permissive (does not block) rather than silently dead.

        The current bar's ATR is appended AFTER reading the reference, so the
        reference never includes the bar it is gating — strictly causal, and
        identical in backtest and live (it does not read the context's
        ``atr_90th_percentile``, which is look-ahead in the replay and has no
        live producer; the setup owns this computation end to end).
        """
        if len(self._atr_window) >= self.config.vol_warmup_bars:
            ref: float | None = float(
                np.percentile(self._atr_window, self.config.vol_percentile)
            )
        else:
            ref = None  # warmup — permissive

        # Append AFTER reading (strictly causal: reference excludes this bar).
        self._atr_window.append(atr)
        return ref

    def _self_range(self, close: float) -> tuple[float, float] | None:
        """Return the causal recent (high, low) from prior closes, or None during warmup.

        Computes max/min over the trailing ``range_window_bars`` closes seen at or
        before the current bar (the current close is appended AFTER reading, so
        the range excludes it). Returns ``None`` until ``range_warmup_bars`` prior
        closes exist — there is no meaningful recent range yet (e.g. the first
        minutes after the open), and the caller treats the stall guard as
        permissive in that case.

        This is the live-reproducible replacement for ``ctx.last_15min_high/low``,
        which has no producer in the orchestrator path (so it defaults to
        ``current_price`` live → the stall guard would silently never fire).
        """
        if len(self._close_window) >= self.config.range_warmup_bars:
            rng: tuple[float, float] | None = (
                max(self._close_window),
                min(self._close_window),
            )
        else:
            rng = None  # warmup — permissive

        # Append AFTER reading (strictly causal: range excludes the current bar).
        self._close_window.append(close)
        return rng

    def _trend_score(self, vwap: float, atr: float, session_date: date) -> float | None:
        """Return the causal session-VWAP trend score, or None during warmup.

        The score is the net drift of the session VWAP over the trailing
        ``trend_window_bars`` observations, in ATR units:
        ``(vwap_now - vwap_oldest) / atr``. Positive → VWAP grinding up,
        negative → grinding down. The window is reset whenever ``session_date``
        changes (futures is day-only, so the KST date boundary is the session
        boundary) to keep the overnight gap out of the slope. The current VWAP is
        appended AFTER the read (strictly causal — the score never includes the
        bar it gates). Returns ``None`` until ``trend_warmup_bars`` observations
        exist, so the caller treats the gate as permissive (never silently dead).
        """
        if self._trend_session_date != session_date:
            self._vwap_window.clear()
            self._trend_session_date = session_date

        if len(self._vwap_window) >= self.config.trend_warmup_bars and atr > 0:
            score: float | None = (vwap - self._vwap_window[0]) / atr
        else:
            score = None  # warmup — permissive

        # Append AFTER reading (strictly causal: score excludes the current bar).
        self._vwap_window.append(vwap)
        return score

    def check(self, ctx: FuturesMarketView) -> Signal | None:  # noqa: PLR0911
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

        # 3. High-vol regime gate (causal, self-computed — see _vol_reference).
        #    _vol_reference and _self_range are called on EVERY in-window bar (and
        #    BEFORE any later early-return) so the rolling ATR/close histories stay
        #    continuous. Both return None during warmup → the corresponding gate is
        #    permissive (never silently dead).
        prev_close = self._close_window[-1] if self._close_window else None
        vol_ref = self._vol_reference(atr)
        recent_range = self._self_range(ctx.current_price)
        # Causal session-VWAP trend score (None during warmup → gate permissive).
        # Computed on EVERY in-window bar so the VWAP history stays continuous,
        # exactly like the vol/close windows above.
        trend_score = self._trend_score(ctx.vwap, atr, ctx.now.date())
        gate_active = vol_ref is not None and vol_ref > 0
        vol_ratio = atr / vol_ref if gate_active else 0.0
        if c.min_atr_ratio > 0 and gate_active and vol_ratio < c.min_atr_ratio:
            return self._reject(f"vol_below_gate({vol_ratio:.2f}<{c.min_atr_ratio})")

        # 4. VWAP extension extreme (the fade trigger)
        z = (ctx.current_price - ctx.vwap) / atr
        if z >= c.extreme_atr_mult:
            direction = "short"  # fade the up-spike back toward VWAP
        elif z <= -c.extreme_atr_mult:
            direction = "long"  # fade the down-spike back toward VWAP
        else:
            return self._reject(f"not_extreme(z={z:+.2f},need±{c.extreme_atr_mult})")

        # 4.5 Trend-day guard (optional, config-gated, long/short symmetric).
        #     Block a COUNTER-trend fade (long while the session VWAP is grinding
        #     down / short while it grinds up) when the trend is strong, UNLESS
        #     the stretch is climactic — a climactic flush is the mean-reversion
        #     edge we want to keep. trend_score is the causal net VWAP drift over
        #     trend_window_bars in ATR units (None during warmup → permissive).
        trend_override = False
        if c.trend_filter_enabled and trend_score is not None:
            against_trend = (direction == "long" and trend_score < 0) or (
                direction == "short" and trend_score > 0
            )
            if against_trend and abs(trend_score) >= c.trend_block_threshold:
                # Clamp so the override can never be looser than the fade trigger.
                override_mult = max(
                    c.against_trend_extreme_atr_mult, c.extreme_atr_mult
                )
                if abs(z) >= override_mult:
                    trend_override = True  # climactic flush → allow
                else:
                    return self._reject(
                        f"against_trend(score={trend_score:+.2f},z={z:+.2f})"
                    )

        # 5. Stall confirmation — spike must be near (not blown through) the
        #    self-computed recent extreme on its side, so we fade a stalling
        #    spike, not a still-trending runaway. recent_range is the causal
        #    (high, low) of prior closes (None during warmup → guard permissive).
        recent_high: float | None = None
        recent_low: float | None = None
        stall_distance: float | None = None
        stall_buffer: float | None = None
        if recent_range is not None:
            recent_high, recent_low = recent_range
            buffer = c.stall_buffer_atr_mult * atr
            stall_buffer = buffer
            if direction == "short":
                # require price within `buffer` ABOVE the prior recent high
                # (close to it / just poking through, not far past = still trending)
                stall_distance = ctx.current_price - recent_high
                if stall_distance > buffer:
                    return self._reject(
                        f"still_trending_up(px={ctx.current_price:.2f}-"
                        f"hi={recent_high:.2f}>{buffer:.2f})"
                    )
            else:
                stall_distance = recent_low - ctx.current_price
            if direction == "long" and stall_distance > buffer:
                return self._reject(
                    f"still_trending_down(lo={recent_low:.2f}-"
                    f"px={ctx.current_price:.2f}>{buffer:.2f})"
                )

        # 6. Optional reversal confirmation — arm on the extreme, fire only once
        #    price starts moving back toward VWAP. This avoids treating a fresh
        #    one-way impulse as a completed stall.
        reversal_price_turn: bool | None = None
        reversal_z_improvement: float | None = None
        prev_z: float | None = None
        if c.reversal_confirm_enabled:
            if prev_close is None:
                return self._reject("awaiting_reversal_confirm(no_prev_close)")
            prev_z = (prev_close - ctx.vwap) / atr
            reversal_z_improvement = abs(prev_z) - abs(z)
            reversal_price_turn = (
                ctx.current_price > prev_close
                if direction == "long"
                else ctx.current_price < prev_close
            )
            if c.reversal_confirm_requires_price_turn and not reversal_price_turn:
                return self._reject(
                    f"awaiting_reversal_confirm(price_turn={direction})"
                )
            if reversal_z_improvement < c.reversal_confirm_atr_mult:
                return self._reject(
                    "awaiting_reversal_confirm("
                    f"z_improve={reversal_z_improvement:.2f}<"
                    f"{c.reversal_confirm_atr_mult:.2f})"
                )

        # 7. Risk bracket (ATR-scaled, symmetric)
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
        if c.min_confidence > 0.0 and confidence < c.min_confidence:
            return self._reject(f"low_confidence({confidence:.2f}<{c.min_confidence})")

        target_rr = target_distance / risk if risk > 0 else 0.0
        self.last_signal_details = {
            "strategy": "setup_d_vwap_reversion",
            "entry_price": entry,
            "vwap": ctx.vwap,
            "atr_14": atr,
            "z": z,
            "abs_z": abs(z),
            "direction": direction,
            "vol_ref": vol_ref,
            "vol_ratio": vol_ratio,
            "vol_gate_active": gate_active,
            "vol_window_count": len(self._atr_window),
            "recent_high": recent_high,
            "recent_low": recent_low,
            "stall_distance": stall_distance,
            "stall_buffer": stall_buffer,
            "prev_close": prev_close,
            "prev_z": prev_z,
            "trend_filter_active": c.trend_filter_enabled and trend_score is not None,
            "trend_score": trend_score,
            "trend_window_count": len(self._vwap_window),
            "against_trend_override": trend_override,
            "reversal_confirm_enabled": c.reversal_confirm_enabled,
            "reversal_price_turn": reversal_price_turn,
            "reversal_z_improvement": reversal_z_improvement,
            "risk_points": risk,
            "vwap_distance": vwap_distance,
            "target_distance": target_distance,
            "target_rr": target_rr,
            "stop_atr_mult": c.stop_atr_mult,
            "min_reward_risk": c.min_reward_risk,
        }

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
                f"target_R_{target_rr:.2f}",
                "highvol_vwap_reversion",
                *(["reversal_confirmed"] if c.reversal_confirm_enabled else []),
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
