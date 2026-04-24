"""Abstract base classes for the Phase 3 RiskFilterLayer.

``FilterResult`` is the single return type for every concrete filter.
``RiskFilter`` is the ABC that all eight filters must extend.

Design notes
------------
* ``FilterResult`` is a **frozen** dataclass so filter results are safely
  hashable and cannot be accidentally mutated by downstream code.
* ``size_multiplier`` defaults to ``1.0`` (full size).  Filters that wish to
  *reduce* position size without outright rejecting the signal may return a
  value in ``[0.0, 1.0)``.  Values above ``1.0`` are rejected by
  ``__post_init__`` — filters must never *increase* the base size.
* ``RiskFilter.name`` is a **class attribute** that subclasses override with a
  short snake_case identifier (e.g. ``"trading_hours"``).  The abstract
  sentinel value ``""`` will cause assertion errors in the base
  ``__init_subclass__`` hook if a subclass forgets to set it.
* Task 11 will use ``size_multiplier`` on ``ConsecutiveLossFilter``; the field
  is added here so all downstream code compiles without modification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.decision.signal import Signal
    from shared.risk.state import RiskStateSnapshot


@dataclass(frozen=True)
class FilterResult:
    """Immutable result returned by a single :class:`RiskFilter` check.

    Attributes:
        passed: ``True`` if the signal passes this filter, ``False`` to reject.
        filter_name: Short identifier matching :attr:`RiskFilter.name`.
        skip_reason: Human-readable rejection tag; ``None`` when *passed* is
            ``True``.  Persisted to ``signals_all`` for observability.
        size_multiplier: Scalar in ``[0.0, 1.0]``.  A filter may pass the
            signal but reduce the intended position size (e.g.
            ``ConsecutiveLossFilter`` returns ``0.5`` after two losses).
            Defaults to ``1.0`` (no reduction).
    """

    passed: bool
    filter_name: str
    skip_reason: str | None = None
    size_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.size_multiplier <= 1.0):
            raise ValueError(
                f"size_multiplier must be in [0.0, 1.0], got {self.size_multiplier!r}"
            )


class RiskFilter(ABC):
    """Abstract base for all Phase 3 risk filters.

    Subclasses must:

    1. Set the ``name`` class attribute to a unique snake_case identifier.
    2. Implement :meth:`check` to return a :class:`FilterResult`.

    Example::

        class TradingHoursFilter(RiskFilter):
            name = "trading_hours"

            def check(self, signal: Signal, state_snapshot: RiskStateSnapshot) -> FilterResult:
                ...
    """

    #: Unique snake_case identifier overridden by every concrete subclass.
    name: str = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Skip validation for abstract intermediate classes (those that still
        # define check() as abstract).  Only enforce on fully concrete classes.
        if not getattr(cls, "__abstractmethods__", None) and not cls.name:
            raise TypeError(
                f"Concrete RiskFilter subclass {cls.__name__!r} must set "
                "the 'name' class attribute to a non-empty string."
            )

    @abstractmethod
    def check(
        self,
        signal: Signal,
        state_snapshot: RiskStateSnapshot,
    ) -> FilterResult:
        """Evaluate *signal* against the current risk state.

        Args:
            signal: The candidate trading signal to be evaluated.
            state_snapshot: Mutable snapshot of intraday risk metrics loaded
                from Redis before the filter chain runs.

        Returns:
            A :class:`FilterResult` indicating whether the signal passes this
            filter, and an optional size reduction multiplier.
        """
