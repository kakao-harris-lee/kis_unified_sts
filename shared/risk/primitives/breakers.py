"""Loss-breaker predicate primitives (P4-d).

Single source for the *boolean threshold math* that was independently
re-implemented by two families of consumers:

* ``services/kill_switch`` — catastrophic force-flatten conditions
  (``DailyLossCondition`` / ``WeeklyLossCondition`` / ``MonthlyLossCondition`` /
  ``ConsecutiveLossesCondition``).
* ``shared/risk/filters`` — soft entry filters (``DailyMDDFilter`` /
  ``WeeklyMDDFilter`` / ``ConsecutiveLossFilter``).

These two families share the *same arithmetic* (loss-as-fraction-of-equity,
raw consecutive-count comparison) but deliberately keep **different actions
and boundary semantics**. This module extracts only the shared arithmetic as
pure, stateless predicates. It does NOT — and must never — merge:

* the kill-switch **force-flatten / sentinel-latch action** (catastrophic), or
* the filter's **soft size-reduction / KST persist window / floor policy**
  (``consecutive_loss.py`` keeps all of that).

Only the boolean predicate is shared; **the decision is not**. Each consumer
still owns its own thresholds, actions, and control flow, and calls these
predicates with the boundary/guard arguments that reproduce its prior
behavior exactly (behavior-0).

#600 invariant: the loss-streak breaker structurally conflicts with mean
reversion (catastrophic-only ``consec``/``points`` thresholds). This module
performs a *raw* threshold comparison only — it does not encode any streak
policy, so it cannot regress the catastrophic-only separation. The soft
(size-reduce) and hard (block) filter tiers, and the catastrophic kill tier,
remain three distinct thresholds owned by their consumers.

This module is pure and stateless: no I/O, no config, no hardcoded thresholds.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["consecutive_exceeds", "loss_fraction_exceeds"]

EquityNonPositive = Literal["safe", "raise"]
"""Policy for how a consumer's predicate handles ``equity_krw <= 0``.

* ``"safe"``: return ``False`` (never trip) — reproduces the kill-switch
  conditions' explicit ``if equity <= 0: return False`` guard.
* ``"raise"``: no guard; the ``pnl / equity`` division runs unconditionally,
  reproducing the MDD filters' guardless division. ``equity == 0`` raises
  ``ZeroDivisionError``; ``equity < 0`` computes (sign-flipped) without error,
  exactly as the filters do today.
"""


def loss_fraction_exceeds(
    pnl_krw: float,
    equity_krw: float,
    limit_pct: float,
    *,
    inclusive: bool,
    equity_nonpositive: EquityNonPositive,
) -> bool:
    """Return True when a loss (as a fraction of equity) breaches ``limit_pct``.

    The loss fraction is ``pnl_krw / equity_krw``; a *loss* makes ``pnl_krw``
    negative. The same magnitude comparison underlies both consumer families,
    which differ only at the boundary:

    * **Kill-switch conditions** (``inclusive=True``): trip when
      ``-pnl/equity >= limit`` — a loss *at or beyond* the limit fires. This
      is exactly ``DailyLossCondition`` / ``WeeklyLossCondition`` /
      ``MonthlyLossCondition``.
    * **MDD filters** (``inclusive=False``): reject when
      ``pnl/equity < -limit`` (strict) — a loss *exactly equal* to the limit
      still passes. This is exactly ``DailyMDDFilter`` / ``WeeklyMDDFilter``.

    ``-pnl/equity >= limit`` and ``pnl/equity < -limit`` are the same
    magnitude test with opposite boundary treatment; ``inclusive`` selects
    which. IEEE-754 negation is exact, so each branch is bitwise-identical to
    the corresponding legacy expression (behavior-0).

    Args:
        pnl_krw: Realised + unrealised P&L over the window, in KRW. Negative
            means a loss.
        equity_krw: Account equity in KRW used to normalize the loss.
        limit_pct: Loss limit as a positive fraction of equity (e.g. ``0.03``
            for 3%).
        inclusive: Boundary operator. ``True`` fires at ``loss == limit``
            (kill-switch); ``False`` fires only when ``loss > limit`` (filters).
        equity_nonpositive: Non-positive-equity policy — ``"safe"`` returns
            ``False`` (kill-switch guard), ``"raise"`` divides without a guard
            (filter behavior; ``equity == 0`` raises ``ZeroDivisionError``).

    Returns:
        ``True`` when the loss breaches ``limit_pct`` per ``inclusive``.

    Raises:
        ValueError: If ``equity_nonpositive`` is not ``"safe"`` or ``"raise"``.
        ZeroDivisionError: If ``equity_krw == 0`` and
            ``equity_nonpositive == "raise"`` (guardless filter behavior).
    """
    if equity_nonpositive not in ("safe", "raise"):
        raise ValueError(
            "equity_nonpositive must be 'safe' or 'raise', "
            f"got {equity_nonpositive!r}"
        )
    if equity_krw <= 0 and equity_nonpositive == "safe":
        return False
    loss_fraction = pnl_krw / equity_krw
    if inclusive:
        # Kill-switch form: ``-pnl/equity >= limit`` (== at-or-beyond limit).
        return -loss_fraction >= limit_pct
    # Filter form: ``pnl/equity < -limit`` (strict — equality passes).
    return loss_fraction < -limit_pct


def consecutive_exceeds(
    count: int,
    threshold: int,
    *,
    inclusive: bool = True,
) -> bool:
    """Return True when a raw consecutive-loss count reaches ``threshold``.

    A raw ``>=`` comparison, shared verbatim by every consumer:
    ``ConsecutiveLossesCondition`` (kill), and both the hard *and* soft
    threshold checks inside ``ConsecutiveLossFilter``. Each consumer supplies
    its own threshold; the soft/hard/catastrophic tiers stay distinct.

    This predicate performs *only* the threshold comparison. The filter's
    size-reduction multiplier, KST persist window, and floor policy are NOT
    part of the shared math — they remain in ``consecutive_loss.py``.

    Args:
        count: Current consecutive-loss streak.
        threshold: Streak threshold to compare against.
        inclusive: ``True`` (default) fires at ``count >= threshold`` (all
            three current callers). ``False`` fires only at ``count >
            threshold``; provided for symmetry with
            :func:`loss_fraction_exceeds`.

    Returns:
        ``True`` when the streak reaches (``inclusive``) or exceeds the
        threshold.
    """
    if inclusive:
        return count >= threshold
    return count > threshold
