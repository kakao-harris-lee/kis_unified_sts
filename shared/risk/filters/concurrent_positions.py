"""ConcurrentPositionsFilter — total + per-asset open-position caps (Phase 4-e).

Ports the World-A monolithic ``RiskManager`` concurrent-entry caps
(``shared/risk/manager.py``: ``max_total_positions`` and per-asset
``get_asset_limits().max_positions``) into the surviving decoupled World-B
``RiskFilterLayer``. Before this filter the decoupled chain only enforced a
*per-symbol* one-position rule (``OpenPositionFilter``); the total and
per-asset concurrency caps existed only in the retired monolith.

Concern separation
------------------
This is a **separate filter** from ``OpenPositionFilter``, not an extension of
it. ``OpenPositionFilter`` answers "is *this symbol* already open?" with a
``Callable[[str], bool]`` provider; this filter answers "how many positions are
open in total / in this asset class?" with a count provider. Keeping them apart
avoids polluting the boolean per-symbol seam with count semantics (설계 2.8).

Fail-OPEN design (shadow-first rollout)
--------------------------------------
The filter is *inert* by construction unless an operator wires it:

* no ``open_positions_count_provider`` injected → pass;
* both caps unset (``None``) → pass;
* the provider returns ``None``, a non-mapping, or a value that cannot be
  coerced to ``int`` (``None`` / ``NaN`` / non-numeric string), or raises → pass.

It therefore cannot change the existing pass-through behaviour of the two
shadow-mode daemons (``services/risk_filter``, ``services/stock_risk_filter``)
until a provider *and* a cap are deliberately configured. This mirrors the
``PortfolioMddFilter`` fail-open contract (missing/stale snapshot → pass).

Snapshot schema is untouched
----------------------------
``RiskStateSnapshot`` carries no position counts (only ``daily_trade_count``),
so the counts arrive through the injected provider rather than a schema
extension — the same seam ``OpenPositionFilter`` uses for its boolean provider.

Boundary semantics
------------------
The reject boundary is ``>=`` (at-or-above the cap), bit-for-bit identical to
the monolithic ``RiskManager`` checks it replaces:

* ``metrics.total_positions >= config.max_total_positions`` → block;
* ``get_position_count(asset) >= asset_limits.max_positions`` → block.

Configuration: ``config/risk.yaml`` ``risk.concurrent_positions`` /
``risk_stock.concurrent_positions`` (``enabled`` + ``max_total_positions`` +
``max_positions_per_asset``). Cap key names are kept aligned with the World-A
``max_total_positions`` / per-asset ``max_positions`` so the P4-h2 two-world
config unification can converge on one source. No thresholds are hardcoded.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot

logger = logging.getLogger(__name__)

#: Rejection tag emitted when the portfolio-wide concurrency cap blocks entry.
SKIP_TOTAL = "max_total_positions"
#: Rejection tag emitted when this asset class's concurrency cap blocks entry.
SKIP_PER_ASSET = "max_positions_per_asset"


class ConcurrentPositionsFilter(RiskFilter):
    """Reject new entries once the total / per-asset open-position cap is hit.

    Args:
        asset_class: The asset class this filter guards (e.g. ``"stock"`` /
            ``"futures"``). Each decoupled daemon is single-asset, so this is
            fixed at construction and used to look up the incoming asset's
            count in the provider mapping for the per-asset cap.
        open_positions_count_provider: Zero-arg callable returning a mapping of
            ``{asset_class: open_position_count}``. ``None`` (not injected),
            a ``None`` return, a non-mapping return, a non-int-coercible value,
            or any raised exception all fail OPEN. The total is
            ``sum(counts.values())``; the per-asset count is
            ``counts.get(asset_class, 0)``. See **Provider contract** below.
        max_total_positions: Portfolio-wide concurrency cap. ``None`` disables
            the total check (fail-open on that dimension).
        max_positions_per_asset: Per-asset-class concurrency cap. ``None``
            disables the per-asset check.

    Provider contract:
        Two invariants the count provider MUST satisfy for this filter to match
        the World-A ``RiskManager`` semantics it ports. They are documented here
        (not yet enforceable) because no provider is wired today — the P4-h2 /
        P4-f wiring must honour them:

        1. **Already-open positions only.** The returned counts must EXCLUDE the
           pending candidate currently being evaluated — they are the positions
           already open. The reject boundary is ``>=``, so counting the in-flight
           candidate would block one entry early (off-by-one) and break parity
           with the monolithic ``RiskManager`` (which compares the *current* open
           count against the cap).
        2. **All asset classes for the total cap.** For ``max_total_positions``
           to behave as a *portfolio-wide* cap the provider must return counts for
           every asset class (e.g. ``{"stock": …, "futures": …}``). A single-asset
           daemon that returns only its own count silently shrinks the "total" to
           a per-asset total, under-counting the portfolio so the cross-asset cap
           never fires.

    Example::

        f = ConcurrentPositionsFilter(
            asset_class="stock",
            open_positions_count_provider=lambda: {"stock": 3, "futures": 1},
            max_total_positions=20,
            max_positions_per_asset=15,
        )
    """

    name = "concurrent_positions"

    def __init__(
        self,
        *,
        asset_class: str,
        open_positions_count_provider: (
            Callable[[], Mapping[str, int] | None] | None
        ) = None,
        max_total_positions: int | None = None,
        max_positions_per_asset: int | None = None,
    ) -> None:
        self.asset_class: str = asset_class
        self._count_provider = open_positions_count_provider
        self.max_total_positions: int | None = max_total_positions
        self.max_positions_per_asset: int | None = max_positions_per_asset

    # ------------------------------------------------------------------
    # RiskFilter interface
    # ------------------------------------------------------------------

    def check(
        self,
        signal: Signal,  # noqa: ARG002 — portfolio-level gate; signal content unused
        state_snapshot: RiskStateSnapshot,  # noqa: ARG002
    ) -> FilterResult:
        # Fail-open: no provider, or no cap configured at all → nothing to check.
        if self._count_provider is None:
            return self._pass()
        if self.max_total_positions is None and self.max_positions_per_asset is None:
            return self._pass()

        # _read_counts normalizes to a plain {asset: int} dict inside the
        # fail-open guard (or returns None ⇒ pass), so every mapping access and
        # int coercion below is on already-validated data — nothing here can
        # raise out of check() into the guardless layer/daemon path.
        counts = self._read_counts()
        if counts is None:
            return self._pass()

        # Total across all asset classes (>= boundary matches RiskManager).
        if self.max_total_positions is not None:
            total = sum(counts.values())
            if total >= self.max_total_positions:
                return FilterResult(
                    passed=False,
                    filter_name=self.name,
                    skip_reason=SKIP_TOTAL,
                )

        # This asset class's own concurrency cap (>= boundary).
        if self.max_positions_per_asset is not None:
            asset_count = counts.get(self.asset_class, 0)
            if asset_count >= self.max_positions_per_asset:
                return FilterResult(
                    passed=False,
                    filter_name=self.name,
                    skip_reason=SKIP_PER_ASSET,
                )

        return self._pass()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _pass(self) -> FilterResult:
        return FilterResult(passed=True, filter_name=self.name)

    def _read_counts(self) -> dict[str, int] | None:
        """Read + normalize the provider's count mapping, failing OPEN on any error.

        The *entire* provider contact surface lives inside one fail-open guard:
        the call itself, the ``Mapping`` type check, and every ``int`` coercion.
        A corrupt return therefore can never raise out of :meth:`check` into the
        guardless ``RiskFilterLayer.evaluate`` → daemon path, where an unhandled
        exception would fail *closed* (the poison message is never XACK'd and the
        pipeline stalls) — the opposite of this filter's fail-open intent.

        Returns a plain ``{asset_class: int}`` dict, or ``None`` (⇒ pass) when the
        provider raises, returns ``None`` or a non-``Mapping``, or yields any value
        that cannot be coerced to ``int``. Redis stores counts as strings, so
        numeric strings coerce cleanly while ``None`` / ``NaN`` / non-numeric
        strings all fail open rather than crash the daemon.
        """
        assert self._count_provider is not None  # guarded by check()
        try:
            raw = self._count_provider()
            if not isinstance(raw, Mapping):
                if raw is not None:
                    logger.warning(
                        "concurrent_positions provider returned %s, not a mapping; "
                        "failing open",
                        type(raw).__name__,
                    )
                return None
            return {str(key): int(value) for key, value in raw.items()}
        except Exception as exc:  # noqa: BLE001 — fail-open on any read/coercion error
            logger.warning("concurrent_positions count read failed: %s", exc)
            return None
