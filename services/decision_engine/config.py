"""Consumer-side wiring config for services/decision_engine (futures).

The shared market-risk ENTRY gate itself (mode / reaction matrix / staleness
bound / Redis key) lives in ``shared/risk/market_risk_gate.py`` +
``config/market_risk_gate.yaml`` — that file's ``mode`` is the single
off/shadow/enforce switch. This module owns what the shared gate delegates to
the decision_engine daemon (the throttle interval for its shadow-mode
would-block observation log) plus the daemon's own two observability
intervals: the per-setup evaluation log and the liveness heartbeat.

Futures-side mirror of
``services/stock_strategy/market_risk.py::MarketRiskGateWiringConfig``
(stock does additionally map a ``min_confidence`` label onto
``Signal.confidence`` — the futures reaction matrix carries no
``min_confidence`` cells, so that half does not apply here).

Loaded once at daemon startup (``services/decision_engine/main.py``); the hot
path never re-parses YAML.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase

logger = logging.getLogger(__name__)

__all__ = [
    "DecisionEngineLivenessWiring",
    "DecisionEngineMarketRiskGateWiring",
    "DecisionEngineSetupEvalWiring",
]


class DecisionEngineMarketRiskGateWiring(ServiceConfigBase):
    """Shadow-mode would-block log throttle for the futures decision_engine.

    ``would_block_log_interval_seconds`` mirrors
    ``config/stock_market_risk_gate.yaml``'s field of the same name: shadow
    verdicts repeat every eval cycle (~60s tick) for as long as the band
    holds, so the daemon logs at most once per interval per reason (see
    ``shared.risk.log_throttle.ReasonLogThrottle``).
    """

    _default_config_file: ClassVar[str] = "decision_engine.yaml"
    _default_section: ClassVar[str] = "market_risk_gate"

    would_block_log_interval_seconds: float = Field(
        default=300.0,
        gt=0,
        description=(
            "Throttle for the shadow-mode market-risk-gate would-block "
            "log (seconds per reason)"
        ),
    )

    @classmethod
    def load_or_default(
        cls, path: str | None = None
    ) -> DecisionEngineMarketRiskGateWiring:
        """Load from YAML when available; defaults on any read/parse problem.

        Same graceful-degradation contract as
        ``MarketRiskGateConfig.load_or_default`` /
        ``MarketRiskGateWiringConfig.load`` — a missing file, missing
        section, or malformed value never blocks daemon startup.
        """
        try:
            return cls.from_yaml(path)
        except Exception:
            logger.warning(
                "decision_engine.yaml market_risk_gate wiring load failed; "
                "using defaults",
                exc_info=True,
            )
            return cls()


class DecisionEngineSetupEvalWiring(ServiceConfigBase):
    """Per-setup evaluation observability wiring for the futures decision_engine.

    The daemon records one ``reject``/``fired`` evaluation per setup per tick
    (``shared/strategy/entry/setup_eval_publisher.publish_setup_eval``) so
    "0 candidates" is distinguishable from "never evaluated". A reject reason
    holds for as long as its cause does, i.e. every ~60 s tick, so the INFO
    line is throttled per (setup, outcome, reason-kind).

    Its own interval rather than a reuse of the market-risk gate's
    ``would_block_log_interval_seconds``: the two logs answer different
    questions and an operator tuning one must not silently retune the other.
    """

    _default_config_file: ClassVar[str] = "decision_engine.yaml"
    _default_section: ClassVar[str] = "setup_eval"

    log_interval_seconds: float = Field(
        default=300.0,
        gt=0,
        description=(
            "Throttle for the per-setup evaluation INFO line (seconds per "
            "setup/outcome/reason-kind). Redis publishing is never throttled."
        ),
    )

    @classmethod
    def load_or_default(cls, path: str | None = None) -> DecisionEngineSetupEvalWiring:
        """Load from YAML when available; defaults on any read/parse problem.

        Same graceful-degradation contract as
        :meth:`DecisionEngineMarketRiskGateWiring.load_or_default` — a missing
        file, missing section, or malformed value never blocks daemon startup.
        """
        try:
            return cls.from_yaml(path)
        except Exception:
            logger.warning(
                "decision_engine.yaml setup_eval wiring load failed; using defaults",
                exc_info=True,
            )
            return cls()


class DecisionEngineLivenessWiring(ServiceConfigBase):
    """Proof-of-work heartbeat wiring for the futures decision_engine.

    The setup-eval INFO governed by :class:`DecisionEngineSetupEvalWiring` is
    throttled per STATE CHANGE (``setup_eval_throttle_key(name, outcome,
    reason)``): an unchanged verdict logs nothing however many cycles run, so
    its silence says nothing about whether the daemon is alive. Measured on the
    2026-09-18 harvest, a healthy producer emitted 21 in-session lines across
    seven hours, one stretch of 4h44m emitting nothing at all. The daemon
    therefore emits its own per-interval liveness line from the evaluation loop
    (``services/decision_engine/main.py::_maybe_log_liveness``); see
    ``docs/plans/2026-09-19-stream-consumer-liveness-and-monitor-dedup-design.md``
    §2.1 and §4 row 2b.

    ``log_interval_seconds`` MUST stay below
    ``config/f9_observation.yaml::f9_observation.observation_max_gap_seconds``
    — above it a healthy producer would read ``stale_observation`` once that
    file stops exempting this service from freshness scoring (design §4 row 3).
    ``tests/unit/decision_engine/test_liveness_heartbeat.py`` asserts the
    relationship against both real files so the two cannot drift apart
    silently.
    """

    _default_config_file: ClassVar[str] = "decision_engine.yaml"
    _default_section: ClassVar[str] = "liveness"

    log_interval_seconds: float = Field(
        default=60.0,
        gt=0,
        description=(
            "Interval between decision_engine_alive heartbeat lines (seconds). "
            "Must stay below f9_observation.observation_max_gap_seconds."
        ),
    )

    @classmethod
    def load_or_default(cls, path: str | None = None) -> DecisionEngineLivenessWiring:
        """Load from YAML when available; defaults on any read/parse problem.

        Same graceful-degradation contract as
        :meth:`DecisionEngineMarketRiskGateWiring.load_or_default` — a missing
        file, missing section, or malformed value never blocks daemon startup.
        Degrading to the default here is strictly better than degrading to
        silence: the heartbeat is what makes a wedged daemon visible.
        """
        try:
            return cls.from_yaml(path)
        except Exception:
            logger.warning(
                "decision_engine.yaml liveness wiring load failed; using defaults",
                exc_info=True,
            )
            return cls()
