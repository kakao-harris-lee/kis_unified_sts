"""VolatilityFilter — Phase 3 RiskFilterLayer, Filter #6.

Rejects entry signals when the symbol's current ATR exceeds the upper-tail
percentile of its own recent ATR distribution.  Elevated volatility inflates
slippage and makes intraday position sizing unreliable.

Design note — one provider, both sides
--------------------------------------
The filter takes a **single** provider returning a
:class:`~shared.risk.volatility_reference.VolatilityReference`, which carries
the current ATR *and* its threshold together for one symbol.

This is not stylistic.  The filter previously took a bare ``current_atr_provider``
and read its threshold from ``RiskStateSnapshot.atr_90th_percentile`` — a field
that defaulted to ``0.0`` and had no production writer.  Wiring the ATR provider
alone would therefore have made the comparison ``atr > 0.0``, true for every
live reading, rejecting every entry and halting all trading silently.  Splitting
the comparison across two independently-wirable inputs is what made that state
reachable; fusing them into one value object is what makes it unreachable.  The
value object additionally refuses a non-positive threshold at construction, so
even a future caller who hand-builds a reference cannot reconstruct the defect.

Fusing the two sides also fixes a correctness problem the split hid: a
percentile computed from one ATR series compared against a "current" ATR from a
different backend is a units mismatch.  Both sides now come from one publisher,
one series, one convention.

Per-symbol by construction
--------------------------
ATR is in absolute price units, so a threshold is only meaningful against its
own instrument.  The provider is therefore keyed by ``signal.symbol`` (the
stock chain's ``StockRiskSignal`` sets ``symbol == code``), replacing the old
single per-asset-class scalar that could not have been correct for a
multi-symbol stock universe.

Absent / stale reference → SKIP, loudly
---------------------------------------
When no provider is wired, or the provider returns ``None`` (absent, stale, or
corrupt snapshot), or the reference is still in warmup
(``atr_percentile is None``), the filter **passes** the signal and warns on a
throttle.  That is the polarity every sibling snapshot-reading filter in this
layer already uses (``PortfolioMddFilter`` / ``MarginGateFilter`` /
``LeverageFilter`` all pass on absent/stale/corrupt); fail-closed here would
recreate the exact silent trading halt this design exists to prevent.

Configuration: ``config/risk.yaml`` ``risk.volatility`` / ``risk_stock.volatility``
(``enabled`` defaults to ``false`` ⇒ no provider is wired ⇒ this filter is inert
and the chain behaves exactly as it did before).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot
from shared.risk.volatility_reference import (
    DEFAULT_WARN_INTERVAL_SECONDS,
    SymbolWarningThrottle,
)

if TYPE_CHECKING:
    from shared.risk.volatility_reference import VolatilityReference

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_WARN_INTERVAL_SECONDS", "VolatilityFilter"]


class VolatilityFilter(RiskFilter):
    """Reject signals whose current ATR exceeds the symbol's ATR percentile.

    The rejection condition is **strict** (``>``):

    .. code-block:: text

        reference.current_atr > reference.atr_percentile

    A current ATR exactly equal to the threshold does *not* trigger rejection.

    Args:
        reference_provider: Callable mapping a symbol to its
            :class:`~shared.risk.volatility_reference.VolatilityReference`, or
            ``None`` when no usable reference exists.  ``None`` for the
            provider itself means the filter is structurally inert: it reads
            nothing and passes every signal.  There is deliberately no way to
            supply only a current ATR — see the module docstring.
        warn_interval_seconds: Throttle for the "no usable reference" warning.
        clock: Monotonic-ish "now" provider for the warning throttle
            (injectable for tests).

    Example::

        f = VolatilityFilter(
            reference_provider=build_volatility_reference_provider(
                asset_class="stock", settings=config.volatility
            )
        )
    """

    name = "volatility"

    def __init__(
        self,
        *,
        reference_provider: Callable[[str], VolatilityReference | None] | None = None,
        warn_interval_seconds: float = DEFAULT_WARN_INTERVAL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._reference_provider = reference_provider
        # Same throttle implementation the reader uses, so the two layers
        # cannot drift into announcing the same condition at different rates.
        self._throttle = SymbolWarningThrottle(warn_interval_seconds, clock=clock)

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002 — reference is per-symbol
    ) -> FilterResult:
        """Evaluate whether current volatility is within acceptable bounds.

        Args:
            signal: The candidate trading signal; only ``symbol`` is read.
            state_snapshot: Intraday risk metrics.  Unused — the threshold is
                per-symbol and lives in the published volatility reference, not
                in the per-asset-class risk state.

        Returns:
            :class:`FilterResult` with ``passed=False`` and
            ``skip_reason="volatility_too_high"`` when the current ATR exceeds
            the symbol's percentile threshold, otherwise ``passed=True``.
        """
        if self._reference_provider is None:
            # Unwired: inert by construction (announced once at build time by
            # RiskFilterLayer.from_config).
            return self._pass()

        symbol = getattr(signal, "symbol", "") or ""
        try:
            reference = self._reference_provider(symbol)
        except Exception as exc:  # noqa: BLE001 — a read error must not reject
            self._warn(symbol, f"provider raised: {exc}")
            return self._pass()

        if reference is None:
            self._warn(symbol, "no published reference (absent, stale, or corrupt)")
            return self._pass()

        threshold = reference.atr_percentile
        if threshold is None:
            self._warn(
                symbol,
                f"threshold still in warmup ({reference.sample_size} samples)",
            )
            return self._pass()

        if reference.current_atr > threshold:
            return FilterResult(
                passed=False,
                filter_name=self.name,
                skip_reason="volatility_too_high",
            )

        return self._pass()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _pass(self) -> FilterResult:
        return FilterResult(passed=True, filter_name=self.name)

    def _warn(self, symbol: str, reason: str) -> None:
        """Warn that the filter is passing blind, at most once per interval.

        Silence here would be the worst outcome: an operator who enabled the
        filter would believe volatility is being gated while every signal
        sails through.
        """
        if not self._throttle.should_warn(symbol):
            return
        logger.warning(
            "VolatilityFilter is passing %s unchecked — %s. The filter is "
            "wired but has no usable threshold, so it is inert for this symbol.",
            symbol or "<unknown symbol>",
            reason,
        )
