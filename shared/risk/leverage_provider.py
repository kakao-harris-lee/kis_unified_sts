"""Leverage-filter snapshot provider factory (P5-3).

Builds the zero-arg ``snapshot_provider`` that
:class:`shared.risk.filters.leverage.LeverageFilter` consumes, combining an
injected open-position source and an equity source into the
``{positions, equity_krw}`` mapping the filter's provider contract expects.

Asset-agnostic — each daemon injects its own already-normalized position source
(each position a mapping carrying ``code`` / ``quantity`` / ``current_price``)
and equity source, so no asset-specific knowledge leaks into this shared seam:

* the futures chain (``services/risk_filter``) reuses the margin read-model's
  ``trading:futures:positions`` reader + ``fallback_account_equity_krw``;
* the stock chain (``services/stock_risk_filter``) reuses the M4
  ``stock_daemon_positions_key`` hash + ``account_equity_krw``.

**No new Redis key is introduced** — both sources are already published by the
existing pipelines; this factory only reads them.

Fail-OPEN by construction: the returned provider swallows *every* error and
returns ``None`` so a Redis/parse failure can never raise into the guardless
``RiskFilterLayer.evaluate`` -> daemon path (:class:`LeverageFilter` treats a
``None`` snapshot as "no reading" -> pass). This mirrors — and stacks on top of
— the fail-open contract already documented in
``shared/risk/filters/leverage.py`` (that filter independently re-guards a
malformed/None snapshot, so a corrupt read is fail-open at both layers).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)


def build_leverage_snapshot_provider(
    *,
    positions_provider: Callable[[], Sequence[Mapping[str, Any]]],
    equity_provider: Callable[[], float | None],
) -> Callable[[], Mapping[str, Any] | None]:
    """Combine a positions source + an equity source into a leverage snapshot.

    Args:
        positions_provider: Zero-arg callable returning the open-position
            sequence, each element a mapping carrying ``code`` / ``quantity`` /
            ``current_price`` (the :class:`LeverageFilter` provider contract). It
            MUST exclude the pending candidate (leverage is measured on the
            current book, not the hypothetical post-entry book).
        equity_provider: Zero-arg callable returning account equity in KRW (the
            leverage denominator) or ``None``.

    Returns:
        A zero-arg callable returning
        ``{"positions": [...], "equity_krw": <equity>}``, or ``None`` when the
        equity read is ``None`` or *any* read raises (fail-open — the filter
        treats ``None`` as no snapshot and passes). The returned callable never
        raises, so it is safe to hand to the guardless daemon evaluate path.
    """

    def _read() -> Mapping[str, Any] | None:
        try:
            equity = equity_provider()
            if equity is None:
                # No equity denominator -> no leverage reading. Fail open (the
                # filter also guards a missing/non-positive equity itself).
                return None
            positions = list(positions_provider())
            return {"positions": positions, "equity_krw": equity}
        except Exception as exc:  # noqa: BLE001 — fail-open; never raise into daemon
            logger.warning("leverage snapshot provider read failed: %s", exc)
            return None

    return _read
