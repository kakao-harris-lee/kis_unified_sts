"""Shared valid-artifact builders + strategies for the replacement property tests (§7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #18 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must
be *genuinely* admissible, never a permissive shortcut):

* a **clean** :class:`~tos.replacement.OverlapReservationClaim` reserves **all nine**
  credible intermediate outcomes and carries the three no-netting magnitudes as separate
  **non-negative** values (so :func:`~tos.replacement.netting_absent` holds structurally,
  not by a flag), with a positive injected ``within_hard_envelope``;
* a **clean** :class:`~tos.replacement.CancelFirstConditions` proves **all eight** §6.3
  preconditions positively ``True`` — never ``None``;
* a **clean** authorization / workflow record fills every ``_REQUIRED_COVERED`` path with
  a concrete value (never the reserved ``"TBD"`` placeholder);
* the **∅ strategies** deliberately generate empty sets / empty magnitude maps so the
  ∅-void guards are actually exercised (the #10 lesson — a strategy that never emits an
  empty set leaves the ∅ branch untested);
* the **forgery strategies** deliberately generate raw member *strings*, truthy
  non-``bool`` values, and nonsense tokens (the #16 lesson — a strategy that only samples
  safe enum members cannot catch a fall-through gate).

Every magnitude is an explicit fixture value: nothing here is a *policy* number — the real
gap / overlap / timing / aggregate-risk bounds are Verification-Profile and
Broker-Capability-Profile injected and are **all null in Phase 1** (design #18 §8.1).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.replacement import (
    CANCEL_FIRST_ADMISSION_CONDITIONS,
    NO_NETTING_MAGNITUDE_KINDS,
    REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES,
    REQUIRED_REEVALUATION_TARGETS,
    CancelFirstConditions,
    CredibleIntermediateOutcomeKind,
    OverlapReservationClaim,
    ProtectionObligation,
    ReevaluationTargetKind,
    ReplacementAuthorization,
    ReplacementMode,
    ReplacementOutcome,
    ReplacementWorkflowRecord,
    ReplacementWorkflowState,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

# ---------------------------------------------------------------------------
# Scalar strategies
# ---------------------------------------------------------------------------

#: Injected ``bool | None`` flag. ``None`` is UNKNOWN — never a soft pass.
TRIBOOL = st.sampled_from([True, False, None])

#: A finite non-negative magnitude (NaN / infinity are unconstructable, §3.1).
FINITE_NON_NEGATIVE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A finite **negative** magnitude — netting suspicion (design #18 §4.7 row 4).
FINITE_NEGATIVE = st.decimals(
    min_value=Decimal("-1000"),
    max_value=Decimal("-0.01"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A magnitude slot that may be absent (``None`` = UNKNOWN), negative, or non-negative —
#: the three cases the structural no-netting derivation must discriminate.
MAGNITUDE_SLOT = st.one_of(st.none(), FINITE_NEGATIVE, FINITE_NON_NEGATIVE)

#: Credible-intermediate-outcome subsets **including the empty set** (∅ must be reachable).
OUTCOME_SETS = st.frozensets(
    st.sampled_from(list(CredibleIntermediateOutcomeKind)), min_size=0, max_size=9
)

#: Re-evaluation-target subsets **including the empty set**.
TARGET_SETS = st.frozensets(
    st.sampled_from(list(ReevaluationTargetKind)), min_size=0, max_size=6
)

#: The four replacement modes.
REPLACEMENT_MODES = st.sampled_from(list(ReplacementMode))

#: The five replacement outcomes.
REPLACEMENT_OUTCOMES = st.sampled_from(list(ReplacementOutcome))

#: The nine workflow states.
WORKFLOW_STATES = st.sampled_from(list(ReplacementWorkflowState))

#: Leg-admissibility sets **including the empty set** and ``None`` members — the mode
#: composition point must trap on both (design #18 §5.3 M1 / §4.7 row 9).
LEG_ADMISSIBILITY_SETS = st.frozensets(TRIBOOL, min_size=0, max_size=3)

#: Values that are **not** the ``ReplacementOutcome.REPLACEMENT_ADMISSIBLE`` member but
#: which a fall-through gate would admit: the raw member *strings* (a ``StrEnum`` compares
#: equal to its value but is not the member under ``is``), a nonsense token, and the
#: falsy / ``None`` cases. Annotations say ``ReplacementMode`` / ``ReplacementOutcome``;
#: Python enforces nothing at runtime, so a caller bug or a forged payload can put any of
#: these on the wire (the #16 CRITICAL lesson).
MODE_FORGERIES: list[object] = [
    "OVERLAP_FIRST",
    "CANCEL_FIRST",
    "BROKER_PROVEN_ATOMIC",
    "NO_SAFE_MODE",
    "BANANA",
    "",
    None,
    0,
    1,
    True,
    [1],
]

#: The real modes **plus** the forgeries — used by the fall-through regression property.
MODE_OR_FORGERY = st.one_of(
    st.sampled_from(list(ReplacementMode)), st.sampled_from(MODE_FORGERIES)
)

#: Truthy non-``bool`` values that pass an ``if not X:`` gate but are not the singleton
#: ``True``. Every positive-polarity premise is ``bool | None``-annotated only, so an
#: ``is True`` gate is the sole structural defence (design #18 §0.1(j)).
TRUTHY_NON_BOOL: list[object] = ["UNKNOWN", "False", 1, 1.0, [1], {"a": 1}, object()]

#: Values that are **not** the singleton ``False`` but which an ``is not True`` gate would
#: wrongly clear on a **negative-polarity** field. ``None`` is the v1.0 fail-open itself.
NON_FALSE_VALUES: list[object] = [None, 0, "", [], "False", "no", 0.0]

#: Truthy non-``bool`` values a forged (``model_construct``) authority flag can carry.
#: Each is truthy but is not the singleton ``False``, so an ``is not True`` re-check would
#: wrongly clear them (design #18 §5.3 / the afg M3 regression).
FORGED_AUTHORITY_VALUES: list[object] = [True, 1, 1.0, "yes", [1], {"granted": True}]

#: Injected protective ``Admissibility`` verdict tokens **plus** ``None`` and forgeries —
#: every real member is truthy, so only the ``ADMISSIBLE`` token may pass (§4.7 row 11).
ADMISSIBILITY_TOKENS_OR_FORGERY = st.sampled_from(
    ["ADMISSIBLE", "TRAPPED", "PROHIBITED", None, "", "admissible", 1, True, [1]]
)


# ---------------------------------------------------------------------------
# Value-model builders
# ---------------------------------------------------------------------------


def clean_magnitudes(
    **overrides: Decimal | None,
) -> dict[CredibleIntermediateOutcomeKind, Decimal | None]:
    """The three no-netting magnitudes as separate non-negative values (§0.4d).

    Old-order-remaining, new-order-remaining, and simultaneous-fill magnitudes coexist —
    which is exactly what netting would have destroyed. Overrides are keyed by the enum
    member's *name* so a test can knock one slot to ``None`` / negative.
    """
    base: dict[CredibleIntermediateOutcomeKind, Decimal | None] = {
        CredibleIntermediateOutcomeKind.OLD_ORDER_REMAINING_EXECUTABLE: Decimal("7"),
        CredibleIntermediateOutcomeKind.NEW_ORDER_REMAINING_EXECUTABLE: Decimal("5"),
        CredibleIntermediateOutcomeKind.SIMULTANEOUS_OLD_AND_NEW_FILLS: Decimal("12"),
    }
    for name, value in overrides.items():
        base[CredibleIntermediateOutcomeKind[name]] = value
    return base


def clean_claim(**overrides: Any) -> OverlapReservationClaim:
    """A genuinely complete overlap-first claim: all 9 outcomes + structural no-netting."""
    base: dict[str, Any] = {
        "claim_id": "repl-claim-1",
        "reserved_outcome_kinds": REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES,
        "magnitudes": clean_magnitudes(),
        "within_hard_envelope": True,
        "aggregate_risk_magnitude": Decimal("12"),
        "hard_envelope_limit": Decimal("100"),
        "capacity_commitment_ref": "rcl-commit-1",
    }
    base.update(overrides)
    return OverlapReservationClaim(**base)


def clean_conditions(**overrides: Any) -> CancelFirstConditions:
    """All eight §6.3 line 166-174 preconditions positively proven ``True``."""
    base: dict[str, Any] = dict.fromkeys(CANCEL_FIRST_ADMISSION_CONDITIONS, True)
    base.update(overrides)
    return CancelFirstConditions(**base)


def clean_obligation(**overrides: Any) -> ProtectionObligation:
    """A versioned protective obligation (§4.1 line 77); both §15 bounds stay null."""
    base: dict[str, Any] = {
        "obligation_id": "repl-obl-1",
        "obligation_version": 3,
        "scope_identity": "cell-1/acct-1/pf-1/strat-1/broker-1/env-1",
        "protected_side": "PROTECTED_SIDE_A",
        "protected_quantity": Decimal("10"),
        "trigger_or_price_semantics": "trigger-semantics-1",
        "duration_basis": "session",
        "venue_identity": "venue-1",
        # §15 bounds stay None: VP-002 B_protection_gap / B_protection_overlap are real
        # and null in Phase 1 (design #18 §8.1) — never defaulted to a number.
        "max_protection_gap": None,
        "max_protection_overlap": None,
        "ownership_identity": "safety-owned",
        "policy_identity": "policy-1",
    }
    base.update(overrides)
    return ProtectionObligation(**base)


# ---------------------------------------------------------------------------
# Digest-bound artifact builders
# ---------------------------------------------------------------------------


def issue_authorization(**overrides: Any) -> ReplacementAuthorization:
    """Issue a valid :class:`ReplacementAuthorization` (all required covered concrete)."""
    base: dict[str, Any] = {
        "authorization_id": "repl-auth-1",
        "authorization_generation": 1,
        "workflow_id": "repl-wf-1",
        "scope_identity": "cell-1/acct-1/pf-1/strat-1/broker-1/env-1",
        "safety_cell_identity": "cell-1",
        "account_identity": "acct-1",
        "portfolio_identity": "pf-1",
        "strategy_identity": "strat-1",
        "broker_identity": "broker-1",
        "environment_identity": "env-1",
        "old_intent_id": "intent-old-1",
        "new_intent_id": "intent-new-1",
        "intent_lineage": ("intent-old-1", "intent-new-1"),
        "protection_obligation": clean_obligation(),
        "current_exposure_version": 4,
        "replacement_mode": ReplacementMode.OVERLAP_FIRST,
        "capacity_commitment_id": "rcl-commit-1",
        "broker_capability_profile_version": "bcp-v1",
        "broker_session_profile_ref": "session-profile-1",
        "writer_epoch": 2,
        "authority_epoch": 3,
        "revocation_generation": 0,
        "egress_identity": "egress-1",
        "time_health_generation": 5,
        "profile_version": "artifact-v1",
        "safety_profile_version": "sp-v1",
        "verification_profile_version": "vp-002",
        "completion_conditions": ("new-protection-proven", "old-finality-proven"),
        "failure_conditions": ("proof-stale", "bound-exceeded"),
        "containment_conditions": ("retain-safest-protection", "block-new-risk"),
    }
    base.update(overrides)
    return ReplacementAuthorization.issue(scheme=SCHEME, **base)


def issue_workflow_record(**overrides: Any) -> ReplacementWorkflowRecord:
    """Issue a valid :class:`ReplacementWorkflowRecord` with all five axes separate."""
    base: dict[str, Any] = {
        "record_id": "repl-wf-rec-1",
        "workflow_generation": 1,
        "workflow_id": "repl-wf-1",
        "owner_epoch": 3,
        "workflow_state": ReplacementWorkflowState.INTERMEDIATE_STATE,
        "old_intent_id": "intent-old-1",
        "new_intent_id": "intent-new-1",
        "transmission_attempt_id": "attempt-1",
        "broker_order_lineage": ("broker-order-old-1", "broker-order-new-1"),
        "rcl_reservation_id": "rcl-res-1",
        "obligation_version": 3,
        "cancellation_authorization_id": "cancel-authz-1",
        "exposure_basis": "exposure-basis-1",
        # §5 line 107 orthogonal axes — five SEPARATE injected coordinate tokens.
        "broker_order_state": "WORKING",
        "transmission_attempt_state": "SENT_UNCONFIRMED",
        "knowledge_confidence": "PARTIAL",
        "capacity_state": "COMMITTED",
        "protection_state": "PROTECTED",
    }
    base.update(overrides)
    return ReplacementWorkflowRecord.issue(scheme=SCHEME, **base)


# ---------------------------------------------------------------------------
# Composite helpers used across several test modules
# ---------------------------------------------------------------------------


def clean_sequencing_inputs(**overrides: Any) -> dict[str, Any]:
    """The four §5.1 sequencing conjuncts, all positively ``True``."""
    base: dict[str, Any] = {
        "new_protection_sufficiency_current": True,
        "protective_classification_present": True,
        "cancellation_admissible": True,
        "leg_admissibility": True,
    }
    base.update(overrides)
    return base


def clean_mode_inputs(**overrides: Any) -> dict[str, Any]:
    """The §5.3 mode premises for a genuinely admissible ``OVERLAP_FIRST``."""
    base: dict[str, Any] = {
        "atomic_proven": True,
        "overlap_reservation_complete": True,
        "overlap_sequencing_valid": True,
        "cancel_first_gate_passed": True,
        "leg_admissibilities": frozenset({True}),
        "bound_exceeded": False,
    }
    base.update(overrides)
    return base


#: The full re-evaluation universe, re-exported for convenience in the target tests.
ALL_TARGETS = REQUIRED_REEVALUATION_TARGETS
#: The full credible-outcome universe, re-exported for convenience.
ALL_OUTCOMES = REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES
#: The three magnitude kinds whose coexistence proves no-netting.
NETTING_KINDS = NO_NETTING_MAGNITUDE_KINDS
