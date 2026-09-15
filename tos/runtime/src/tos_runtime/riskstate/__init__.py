"""tos_runtime.riskstate — the risk state observation package (TOS risk state service wave,
lane a; ``docs/plans/2026-09-16-tos-risk-state-service-plan.md`` §2, §4.1).

Three modules, three owners (mirroring :mod:`tos_runtime.venue`'s own "three modules, three
owners" split):

* :mod:`tos_runtime.riskstate.policies` — loads the Aggregate Risk Policy / Action Flow Policy
  INSTANCE documents and issues ``AggregateRiskPolicy``/``ActionFlowPolicy`` through the
  kernel's own ``.issue()`` constructors (DR-0003 §2.1: "follow DR-0002 §2.1 and §2.2
  verbatim"). No admissibility judgement; no activation (that stays
  :mod:`tos_runtime.venue.activation`'s job, called by lane b with the new
  ``AGGREGATE_RISK_POLICY``/``ACTION_FLOW_POLICY`` member kinds).
* :mod:`tos_runtime.riskstate.position` — folds the durable evidence store into a
  single-source, conservative position observation (DR-0003 §2.2). Pure aggregation, never a
  risk judgement, never a broker read.
* :mod:`tos_runtime.riskstate.flow_observation` — folds the durable inbox/evidence store into
  an Action Flow observation, plus the pure transforms onto the kernel's own
  ``ActionCause``/``ObservedAmplification`` shapes (DR-0003 §2.3).

Referenced design: ADR-002-021 §9/§12/ARE-INV-006, ADR-002-022 §5.8/§12, DR-0003 §2.2/§2.3.

Firewall (R1, runtime scope): stdlib + ``pyyaml`` (transitively) + ``tos.*`` +
``tos_runtime.{venue._policy_primitives, evidence.store, engine.inbox, rcl.log, recon}`` only —
no ``shared.*``, no ``os.environ``, no ``subprocess``, no ``importlib.import_module``
(``tools/tos_firewall_check.py`` scans tests too).
"""

from __future__ import annotations

from tos_runtime.riskstate.flow_observation import (
    FlowObservation,
    InboxFlowReader,
    committed_flow_vectors,
    to_action_cause,
    to_observed_amplification,
)
from tos_runtime.riskstate.policies import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    AGGREGATE_RISK_POLICY_CONFIG_NAME,
    DeploymentFlowFacts,
    LoadedActionFlowPolicy,
    LoadedAggregateRiskPolicy,
    VenuePolicyConfigError,
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.riskstate.position import (
    EvidencePositionReader,
    PositionObservation,
    conservative_current_usage,
    in_flight_overlap_effect,
    worst_credible_directional_usage,
)

__all__ = [
    "ACTION_FLOW_POLICY_CONFIG_NAME",
    "AGGREGATE_RISK_POLICY_CONFIG_NAME",
    "DeploymentFlowFacts",
    "EvidencePositionReader",
    "FlowObservation",
    "InboxFlowReader",
    "LoadedActionFlowPolicy",
    "LoadedAggregateRiskPolicy",
    "PositionObservation",
    "VenuePolicyConfigError",
    "committed_flow_vectors",
    "conservative_current_usage",
    "in_flight_overlap_effect",
    "load_action_flow_policy",
    "load_aggregate_risk_policy",
    "to_action_cause",
    "to_observed_amplification",
    "worst_credible_directional_usage",
]
