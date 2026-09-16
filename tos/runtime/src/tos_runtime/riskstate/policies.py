"""tos_runtime.riskstate.policies — Aggregate Risk Policy / Action Flow Policy INSTANCE
document loaders (TOS risk state service wave, plan §2.1/§4.1;
``docs/plans/2026-09-16-tos-risk-state-service-plan.md``; DR-0003 §2.1 — "An Aggregate Risk
Policy instance and an Action Flow Policy instance follow DR-0002 §2.1 and §2.2 verbatim").

**A thin re-export shim** (team-lead disposition 2026-09-16, review of PR #704 item T1: split
this module the same way :mod:`tos_runtime.venue.config` was split, rather than register a new
size-budget exception). The actual loader implementations live in three sibling modules, split
out purely for this module's own size budget (``config/tos_size_budget.yaml`` — module
ceiling 1000 lines; no behavioural difference from having them all inline here):
:mod:`tos_runtime.riskstate._riskstate_primitives` (the handful of YAML-parsing helpers
genuinely shared between the two loaders), :mod:`tos_runtime.riskstate
._aggregate_risk_policy_loader` (:func:`load_aggregate_risk_policy` +
:class:`LoadedAggregateRiskPolicy`), and :mod:`tos_runtime.riskstate
._action_flow_policy_loader` (:func:`load_action_flow_policy` + :class:`LoadedActionFlowPolicy`
+ :class:`DeploymentFlowFacts`). This module re-exports every public name those three modules
define — every existing ``from tos_runtime.riskstate.policies import ...`` call site is
unchanged. Both loader sibling modules also reuse :mod:`tos_runtime.venue._policy_primitives`
by import (fail-closed YAML primitives, the ``status: ISSUED``-only rule, the
``canonical_digest`` TBD-or-exact cross-check, presence-only template rule-list/mapping-key
shape fidelity) — no primitive is copied.

**An INSTANCE document is** the FULL key set of
``tos-spec/src/part-1-foundation/verification/AGGREGATE-RISK-POLICY-template.yaml`` /
``ACTION-FLOW-POLICY-template.yaml`` (every template key present; rule lists are data neither
loader interprets) plus two sibling blocks NEITHER template declares — ``_model_view`` (the
kernel record's own ``_COVERED_FIELDS``) and ``_runtime`` (runtime-only facts the kernel
record does not carry) — the same DR-0002 idiom :mod:`tos_runtime.venue._venue_policy_loader`
/ ``_order_construction_policy_loader`` already realize for the Venue Constraint Policy /
Order Construction Policy (those two blocks are NOT part of the tos-spec template file
itself; they are a runtime config-authoring convention, as :mod:`tests.venue._documents`'s
own module docstring confirms for the venue pair).

**What neither loader does (lane a boundary, plan §4.1).** Neither issues its policy against
a Hard Safety Envelope — the ARE ``injected_envelope_max``/HSE dimension cross-check
(plan §2.1 row "ARE ``injected_envelope_max``") is a LANE B wiring-time responsibility
(:mod:`tos_runtime.compose._riskstate_wiring`), run once both the policy AND the HSE are
loaded; neither loader has an HSE input and performs no such check. Neither activates its
policy (``tos_runtime.venue.activation.require_member_activated`` is lane b's job, called
with the ``AGGREGATE_RISK_POLICY``/``ACTION_FLOW_POLICY`` member kinds).

**Dimension-id convention (plan §0 survey "픽스처 관용구", reused not invented).** ARE
dimension ids are ``f"{scope}::{dimension}"`` (matching
``tos_runtime/tests/compose/conftest.py``'s own ``safety_envelope.yaml`` convention the ARE
loader's ``_runtime.dimension_ids`` keys are cross-checked against) — see
:mod:`tos_runtime.riskstate._aggregate_risk_policy_loader`'s own module docstring for detail.

Firewall (R1, runtime scope): stdlib + ``pyyaml`` (transitively, via the reused primitives) +
``tos.*`` + ``tos_runtime.venue._policy_primitives`` + ``tos_runtime.riskstate
._riskstate_primitives`` only — no ``shared.*``, no
``os.environ``/``subprocess``/``importlib.import_module`` (``tools/tos_firewall_check.py``
scans tests too).
"""

from __future__ import annotations

from tos_runtime.riskstate._action_flow_policy_loader import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    DeploymentFlowFacts,
    LoadedActionFlowPolicy,
    load_action_flow_policy,
)
from tos_runtime.riskstate._aggregate_risk_policy_loader import (
    AGGREGATE_RISK_POLICY_CONFIG_NAME,
    LoadedAggregateRiskPolicy,
    load_aggregate_risk_policy,
)
from tos_runtime.venue._policy_primitives import VenuePolicyConfigError

__all__ = [
    "VenuePolicyConfigError",
    "AGGREGATE_RISK_POLICY_CONFIG_NAME",
    "ACTION_FLOW_POLICY_CONFIG_NAME",
    "LoadedAggregateRiskPolicy",
    "load_aggregate_risk_policy",
    "DeploymentFlowFacts",
    "LoadedActionFlowPolicy",
    "load_action_flow_policy",
]
