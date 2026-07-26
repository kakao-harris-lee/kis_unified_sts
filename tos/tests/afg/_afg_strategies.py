"""Shared valid-artifact builders + strategies for the afg property tests (design #16 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #16 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must
be *genuinely* admissible, never a permissive shortcut):

* a **clean** snapshot covers every required scope and carries positive five-axis
  independence evidence per scope, with the local-counter / scheduler-priority bases
  positively ``False``;
* a **clean** amplification envelope declares **every** axis (an undeclared axis is
  unbounded => denial, §5.8 line 141) and the clean observation sits strictly inside it;
* a **clean** cause carries a concrete root identity, a non-empty attested parent lineage,
  and all three defect witnesses positively ``False``;
* a **clean** permit is structurally complete (generation + command identity + claim
  nonce) and single-use, with an unclaimed / unambiguous / unlost / unconflicting
  consumption state;
* the **∅ strategies** deliberately generate empty sets / tuples so the ∅-void guards are
  actually exercised (the #10 lesson — a strategy that never emits an empty set leaves the
  ∅ branch untested).

Every magnitude / bound is an explicit fixture value: nothing here is a *policy* number —
the real rate / burst / queue / age / amplification bounds are Verification-Profile and
Broker-Capability-Profile injected and are all null in Phase 1 (design #16 §8).

The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.afg import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionClassKind,
    ActionFlowDecision,
    ActionFlowDimensionKind,
    ActionFlowPermit,
    ActionFlowPolicy,
    ActionFlowResult,
    ActionFlowScopeKind,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    CurrentnessTrigger,
    MaterialChangeKind,
    ObservedAmplification,
    PermitConsumptionState,
    ProtectiveFlowReserveClaim,
    ScopeIndependenceEvidence,
    action_flow_dimension_id,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rcl import CapacityComponent, CapacityVector

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: A finite non-negative magnitude (NaN / infinity are unconstructable, §3.1).
FINITE_MAGNITUDE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: The applicable shared scopes used across the scope-graph tests.
REQUIRED_SCOPES: frozenset[ActionFlowScopeKind] = frozenset(
    {
        ActionFlowScopeKind.BROKER,
        ActionFlowScopeKind.ACCOUNT,
        ActionFlowScopeKind.CREDENTIAL,
        ActionFlowScopeKind.SESSION,
        ActionFlowScopeKind.ROUTE,
    }
)

#: The governed afg dimension used across the vector tests (Gap-1 namespace token).
BROKER_REQUEST_DIM: str = action_flow_dimension_id(
    ActionFlowDimensionKind.BROKER_REQUEST
)
CANCEL_DIM: str = action_flow_dimension_id(ActionFlowDimensionKind.CANCEL_AMEND_REPLACE)

# ---------------------------------------------------------------------------
# Hypothesis strategies (∅ deliberately reachable — the #10 lesson)
# ---------------------------------------------------------------------------

#: Scope sets **including the empty set** (the ∅-void branch must be exercised).
SCOPE_SETS = st.one_of(
    st.just(frozenset()),
    st.frozensets(st.sampled_from(list(ActionFlowScopeKind)), min_size=0, max_size=5),
)
#: Action-class sets **including the empty set**.
ACTION_CLASS_SETS = st.one_of(
    st.just(frozenset()),
    st.frozensets(st.sampled_from(list(ActionClassKind)), min_size=0, max_size=4),
)
#: Documented-scope status tokens including ``None`` and non-verified members.
DOCUMENTED_STATUSES = st.sampled_from(
    [
        None,
        "VERIFIED_COMPLETE",  # a bare string is NOT the enum member (fail-closed)
    ]
)
#: Injected ``ActionFlowResult`` values (all three are truthy StrEnum members).
ACTION_FLOW_RESULTS = st.sampled_from(list(ActionFlowResult))

#: Values that are **not** the ``ActionFlowResult.GRANT`` member but which a fall-through
#: gate would grant: the raw member *strings* (a ``StrEnum`` compares equal to its value
#: but is not the member under ``is``), a nonsense token, and the falsy / ``None`` cases.
#: Annotation says ``ActionFlowResult``; Python enforces nothing at runtime, so a caller
#: bug or a forged payload can put any of these on the wire.
NON_GRANT_FORGERIES: list[object] = [
    "GRANT",
    "DENY",
    "UNKNOWN",
    "BANANA",
    "",
    None,
    0,
    1,
    True,
    [1],
]

#: The real members **plus** the forgeries — used by the C1 regression property to prove
#: that only the ``GRANT`` member itself can ever produce a ``GRANT`` decision.
ACTION_FLOW_RESULT_OR_FORGERY = st.one_of(
    st.sampled_from(list(ActionFlowResult)),
    st.sampled_from(NON_GRANT_FORGERIES),
)

#: Truthy non-``bool`` values that pass an ``if not X:`` gate but are not the singleton
#: ``True``. The five decision premises are ``bool``-annotated only, so an ``is not True``
#: gate is the sole structural defence (design #16 §2.2-1 / M2 regression).
TRUTHY_NON_BOOL: list[object] = ["UNKNOWN", "False", 1, 1.0, [1], {"a": 1}, object()]

#: Values a forged (``model_construct``) authority flag can carry. Each is truthy but is
#: not the singleton ``False``, so a ``is not True`` check would wrongly clear them
#: (design #16 M3 regression).
FORGED_AUTHORITY_VALUES: list[object] = [True, 1, 1.0, "yes", [1], {"granted": True}]


# ---------------------------------------------------------------------------
# Value-model builders
# ---------------------------------------------------------------------------


def independent_evidence(
    scope: ActionFlowScopeKind, **overrides: Any
) -> ScopeIndependenceEvidence:
    """Positive **six**-axis independence evidence for ``scope`` (§10 line 278)."""
    base: dict[str, Any] = {
        "scope": scope,
        "allocation_separated": True,
        "refill_separated": True,
        "broker_enforcement_separated": True,
        "credential_session_state_separated": True,
        "failure_domain_separated": True,
        "final_route_separated": True,
        "basis_is_local_counter_only": False,
        "basis_is_scheduler_priority_only": False,
    }
    base.update(overrides)
    return ScopeIndependenceEvidence(**base)


def clean_cause(**overrides: Any) -> ActionCause:
    """A cause with a concrete root, an attested lineage, and no defect witnesses."""
    base: dict[str, Any] = {
        "root_cause_identity": "cause-root-1",
        "parent_lineage": ("cause-root-1", "cause-child-1"),
        "lineage_attested": True,
        "cyclic": False,
        "forked_beyond_bound": False,
        "inconsistent": False,
        "command_identity": "cmd-1",
        "command_digest": "cmd-digest-1",
    }
    base.update(overrides)
    return ActionCause(**base)


def full_envelope(**overrides: Any) -> ActionAmplificationEnvelope:
    """An amplification envelope declaring **every** axis (nothing left unbounded)."""
    base: dict[str, Any] = {
        "max_fan_out": 4,
        "max_depth": 3,
        "max_attempts": 2,
        "max_mutations": 2,
        "max_queries": 5,
        "max_queue_depth": 10,
        "max_in_flight": 6,
        "max_elapsed_monotonic": Decimal("1000"),
        "max_duplicate_redelivery_expansion": 1,
        "max_failover_reconnect_replay_expansion": 1,
        "max_amplification_per_cause": Decimal("8"),
    }
    base.update(overrides)
    return ActionAmplificationEnvelope(**base)


def within_observation(**overrides: Any) -> ObservedAmplification:
    """An observation strictly inside :func:`full_envelope` with positive §11:294 witnesses."""
    base: dict[str, Any] = {
        "fan_out": 2,
        "depth": 1,
        "attempts": 1,
        "mutations": 1,
        "queries": 2,
        "queue_depth": 3,
        "in_flight": 2,
        "elapsed_monotonic": Decimal("100"),
        "duplicate_redelivery_expansion": 0,
        "failover_reconnect_replay_expansion": 0,
        "amplification_per_cause": Decimal("4"),
        "duplicate_event_created_new_allowance": False,
        "envelope_reset_on_duplicate": False,
        "concurrent_consumers_share_one_envelope": True,
    }
    base.update(overrides)
    return ObservedAmplification(**base)


def reserve_claim(**overrides: Any) -> ProtectiveFlowReserveClaim:
    """A protective flow reserve claim on a governed afg dimension."""
    base: dict[str, Any] = {
        "dimension_id": BROKER_REQUEST_DIM,
        "scope": ActionFlowScopeKind.BROKER,
        "reserved_magnitude": Decimal("5"),
        "guarantee_level_token": "PHYSICALLY_RESERVED",
        "exclusive_capacity_present": True,
        "high_priority_queue": False,
    }
    base.update(overrides)
    return ProtectiveFlowReserveClaim(**base)


def unclaimed_consumption(**overrides: Any) -> PermitConsumptionState:
    """A permit consumption state that is unclaimed / unambiguous / unlost / unconflicting."""
    base: dict[str, Any] = {
        "claimed": False,
        "ambiguous": False,
        "lost": False,
        "conflicting": False,
        "never_claimed_and_unreachable_proven": False,
    }
    base.update(overrides)
    return PermitConsumptionState(**base)


def trigger(**overrides: Any) -> CurrentnessTrigger:
    """A currentness trigger (defaults: a POLICY change with materiality known)."""
    base: dict[str, Any] = {
        "kind": MaterialChangeKind.POLICY,
        "materiality_known": True,
    }
    base.update(overrides)
    return CurrentnessTrigger(**base)


def flow_vector(
    dimension_id: str = BROKER_REQUEST_DIM,
    magnitude: Decimal | None = Decimal("3"),
) -> ActionFlowVector:
    """A one-dimension action-flow vector (the rcl ``CapacityVector`` type, §0.4c)."""
    return ActionFlowVector(
        components=(CapacityComponent(dimension_id=dimension_id, magnitude=magnitude),)
    )


def limit_vector(
    dimension_id: str = BROKER_REQUEST_DIM,
    magnitude: Decimal | None = Decimal("100"),
) -> CapacityVector:
    """A one-dimension limit vector (hard or runtime)."""
    return CapacityVector(
        components=(CapacityComponent(dimension_id=dimension_id, magnitude=magnitude),)
    )


# ---------------------------------------------------------------------------
# Digest-bound artifact builders
# ---------------------------------------------------------------------------


def issue_policy(**overrides: Any) -> ActionFlowPolicy:
    """Issue a valid :class:`ActionFlowPolicy` (all required covered fields concrete)."""
    base: dict[str, Any] = {
        "policy_id": "afg-pol-1",
        "policy_generation": 1,
        "policy_version": "v1",
        "governed_dimensions": (ActionFlowDimensionKind.BROKER_REQUEST,),
        "governed_scopes": tuple(sorted(REQUIRED_SCOPES)),
        "governed_action_classes": (ActionClassKind.NORMAL_NEW_RISK,),
        "bundle_member_kind": "ACTION_FLOW_POLICY",
    }
    base.update(overrides)
    return ActionFlowPolicy.issue(scheme=SCHEME, **base)


def issue_snapshot(**overrides: Any) -> ActionFlowStateSnapshot:
    """Issue a snapshot covering every :data:`REQUIRED_SCOPES` scope with independence."""
    base: dict[str, Any] = {
        "snapshot_id": "afg-snap-1",
        "snapshot_generation": 1,
        "consistency_cut_identity": "afg-cut-1",
        "covered_scopes": tuple(sorted(REQUIRED_SCOPES)),
        "covered_dimension_ids": (BROKER_REQUEST_DIM,),
        "scope_independence": tuple(
            independent_evidence(scope) for scope in sorted(REQUIRED_SCOPES)
        ),
        "committed_usage": flow_vector(magnitude=Decimal("1")),
        "hard_envelope_limit": limit_vector(),
        "runtime_profile_limit": limit_vector(),
    }
    base.update(overrides)
    return ActionFlowStateSnapshot.issue(scheme=SCHEME, **base)


def issue_decision(**overrides: Any) -> ActionFlowDecision:
    """Issue a valid :class:`ActionFlowDecision` (concrete id + generation + result)."""
    base: dict[str, Any] = {
        "decision_id": "afg-dec-1",
        "decision_generation": 1,
        "result": ActionFlowResult.GRANT,
        "applicable_action_flow_scopes": (ActionFlowScopeKind.BROKER.value,),
        "action_class": ActionClassKind.NORMAL_NEW_RISK,
        "action_flow_vector": flow_vector(),
        "command_identity": "cmd-1",
        "command_digest": "cmd-digest-1",
    }
    base.update(overrides)
    return ActionFlowDecision.issue(scheme=SCHEME, **base)


def issue_permit(**overrides: Any) -> ActionFlowPermit:
    """Issue a structurally complete, single-use :class:`ActionFlowPermit`."""
    base: dict[str, Any] = {
        "permit_id": "afg-permit-1",
        "permit_generation": 1,
        "command_identity": "cmd-1",
        "claim_nonce": "nonce-1",
        "rcl_commitment_ref": "rcl-commit-1",
        "economic_capacity_commitment_ref": "econ-commit-1",
        "resource_vector": flow_vector(),
        "single_use": True,
    }
    base.update(overrides)
    return ActionFlowPermit.issue(scheme=SCHEME, **base)
