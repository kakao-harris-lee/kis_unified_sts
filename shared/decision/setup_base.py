"""Abstract base class for all signal-generating Setups in the decision engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from shared.decision.context import MarketContext
from shared.decision.signal import Signal


class Setup(ABC):
    """Abstract base for entry-signal generators (Setup A, Setup C, …).

    Subclass contract
    -----------------
    1. Declare a ``CONFIG_CLASS`` class-variable pointing to a
       ``ServiceConfigBase`` subclass that holds the setup's parameters.
    2. Implement ``check(ctx) -> Signal | None`` with the entry logic.
    3. Receive a ``config`` instance via the constructor (or let the
       default constructor load it from the YAML default path).

    Example::

        class SetupAGapReversion(Setup):
            CONFIG_CLASS = SetupAConfig

            def check(self, ctx: MarketContext) -> Signal | None:
                ...
    """

    CONFIG_CLASS: ClassVar[type[Any]]

    def __init__(self, *, config: Any | None = None) -> None:
        """Initialise the setup with an optional pre-built config.

        If *config* is ``None`` the class-level ``CONFIG_CLASS`` is
        instantiated with its defaults (no YAML load is required for
        unit-test usage).
        """
        if config is None:
            config = self.__class__.CONFIG_CLASS()
        self.config = config

    @abstractmethod
    def check(self, ctx: MarketContext) -> Signal | None:
        """Evaluate market context and optionally emit a trading signal.

        Parameters
        ----------
        ctx:
            Current market state snapshot.

        Returns
        -------
        Signal
            A candidate trading signal when all entry conditions are met.
        None
            When any entry condition fails.
        """
        ...
