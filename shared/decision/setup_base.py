"""Abstract base class for all signal-generating Setups in the decision engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from shared.decision.interfaces import FuturesMarketView
from shared.decision.signal import Signal


class Setup(ABC):
    """Abstract base for entry-signal generators (Setup A, Setup C, …).

    Subclass contract
    -----------------
    1. Declare a ``CONFIG_CLASS`` class-variable pointing to a
       ``ServiceConfigBase`` subclass that holds the setup's parameters.
    2. Declare a ``REGISTRY_NAME`` class-variable holding the strategy-registry
       name (the ``config/strategies/futures/<name>.yaml`` stem, e.g.
       ``"setup_a_gap_reversion"``). It is what the decoupled decision_engine
       roster keys on and what the setup-eval observability rows are written
       under, so the decoupled chain and the monolith share one identifier.
    3. Implement ``check(ctx) -> Signal | None`` with the entry logic.
    4. Receive a ``config`` instance via the constructor. Passing ``None``
       constructs ``CONFIG_CLASS()`` — the Pydantic FIELD DEFAULTS, NOT a YAML
       load. Production callers must build the config from YAML themselves
       (``services/decision_engine/main.py::_build_setups`` does, via
       ``CONFIG_CLASS.from_yaml()``); the default is a unit-test convenience.
    5. Set ``REQUIRES_VWAP = True`` when ``check`` reads ``ctx.vwap``, so a
       runner can skip the setup (rather than the whole tick) when no session
       VWAP is available yet.

    Example::

        class SetupAGapReversion(Setup):
            CONFIG_CLASS = SetupAConfig
            REGISTRY_NAME = "setup_a_gap_reversion"

            def check(self, ctx: FuturesMarketView) -> Signal | None:
                ...
    """

    CONFIG_CLASS: ClassVar[type[Any]]
    # Annotation only (no value): a subclass that forgets it has no attribute,
    # which the decision_engine's roster/observability treats as "unnamed" and
    # skips rather than silently writing under a wrong key.
    REGISTRY_NAME: ClassVar[str]
    # Does ``check`` read ``ctx.vwap``? Setup A/C do not (locked by
    # tests/unit/strategy/test_setup_ac_field_invariance.py), Setup D does. A
    # runner uses this to skip ONLY the vwap-dependent setups while the session
    # VWAP is missing — darkening A/C too would be a far larger outage than the
    # one being avoided. Has a real default so every Setup carries the flag.
    REQUIRES_VWAP: ClassVar[bool] = False

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
    def check(self, ctx: FuturesMarketView) -> Signal | None:
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
