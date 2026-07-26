"""Shared valid-artifact builders + strategies for the nontrade property tests (§7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #21 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must
be *genuinely* admissible, never a permissive shortcut):

* a **clean** :class:`~tos.nontrade.TransitionEnvelope` declares **all ten** credible
  transition legs and carries the pre-event and post-event exposures as separate
  **non-negative** magnitudes (so :func:`~tos.nontrade.favorable_netting_absent` holds
  structurally, not by a flag);
* a **clean** :class:`~tos.nontrade.SplitTransformationSpec` is a genuine forward split —
  its declared kind matches the directions **derived** from its pre/post magnitudes — with
  an explicit unit spec, rounding rule, and both residuals;
* a **clean** event / correction record fills every ``_REQUIRED_COVERED`` path with a
  concrete value (never the reserved ``"TBD"`` placeholder);
* the **∅ strategies** deliberately generate empty leg sets, empty trigger sets, and empty
  field-confidence sets so the ∅-void guards are actually exercised (the #10 lesson — a
  strategy that never emits an empty set leaves the ∅ branch untested);
* the **forgery strategies** deliberately generate raw member *strings*, truthy
  non-``bool`` values, ``None``, and nonsense tokens (the #16 lesson — a strategy that only
  samples safe enum members cannot catch a fall-through gate).

Every magnitude is an explicit fixture value: nothing here is a *policy* number — the real
event-detect / transition-apply / reconcile bounds are Verification-Profile and
Broker-Capability-Profile injected and are **all null (and ``owner: TBD``) in Phase 1**
(design #21 §8.1). In particular **no split ratio is used as a constant**: the polarity
fixtures move a magnitude up or down, and the predicate derives the direction.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.nontrade import (
    CREDIBLE_TRANSITION_LEG_MINIMUM_SET,
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    FRESHNESS_VERDICT_FRESH,
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_UNKNOWN,
    CorrectionReversalOutcome,
    CorrectionReversalRecord,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventClass,
    NonTradeEventRecord,
    NonTradeEventWorkflowState,
    SplitTransformationKind,
    SplitTransformationSpec,
    TransformationDirection,
    TransitionEnvelope,
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

#: A finite **negative** magnitude — a sign error on the exposure / residual / polarity
#: axes (design #21 §4.7 rows 2/3/5).
FINITE_NEGATIVE = st.decimals(
    min_value=Decimal("-1000"),
    max_value=Decimal("-0.01"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A magnitude slot that may be absent (``None`` = UNKNOWN), negative, or non-negative —
#: the three cases every structural derivation must discriminate.
MAGNITUDE_SLOT = st.one_of(st.none(), FINITE_NEGATIVE, FINITE_NON_NEGATIVE)

#: Credible-transition-leg subsets **including the empty set** (∅ must be reachable — it is
#: the C1 structural guard of ``transition_envelope_complete``).
LEG_SETS = st.frozensets(
    st.sampled_from(list(CredibleTransitionLegKind)), min_size=0, max_size=10
)

#: The five event classes.
EVENT_CLASSES = st.sampled_from(list(NonTradeEventClass))

#: The eleven workflow states (8 linear + 3 branch).
WORKFLOW_STATES = st.sampled_from(list(NonTradeEventWorkflowState))

#: The three transformation directions.
DIRECTIONS = st.sampled_from(list(TransformationDirection))

#: The two declared split kinds **plus** ``None`` (the identity no-op row).
SPLIT_KINDS_OR_NONE = st.sampled_from([*SplitTransformationKind, None])

#: The six correction outcomes.
CORRECTION_OUTCOMES = st.sampled_from(list(CorrectionReversalOutcome))

#: The five dispositions.
DISPOSITIONS = st.sampled_from(list(NonTradeDisposition))

#: The four real venue ``OrderAdmissibilityResult`` tokens plus ``None`` — the exhaustive
#: three-way fold domain (design #21 §6.1 M6).
ADMISSIBILITY_TOKENS_OR_NONE: list[str | None] = [
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_UNKNOWN,
    None,
]

#: The three admissibility tokens (and ``None``) that are **not** an ordinary pass.
NON_ADMISSIBLE_TOKENS: list[str | None] = [
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
    ORDER_ADMISSIBILITY_INADMISSIBLE,
    ORDER_ADMISSIBILITY_UNKNOWN,
    None,
]

#: Admissibility values that are **not** any real token — a forged / drifted payload. The
#: annotation says ``str | None``; Python enforces nothing at runtime, so a caller bug or a
#: forged wire payload can put any of these on the seam (the #16 CRITICAL lesson).
ADMISSIBILITY_FORGERIES: list[Any] = [
    "admissible",
    "Admissible",
    "BANANA",
    "",
    0,
    1,
    True,
    [1],
    object(),
]

#: The whole admissibility domain used by the fall-through regression property.
ADMISSIBILITY_OR_FORGERY = st.one_of(
    st.sampled_from(ADMISSIBILITY_TOKENS_OR_NONE),
    st.sampled_from(ADMISSIBILITY_FORGERIES),
)

#: recon ``FieldConfidenceClass`` token sets **including the empty set** (∅ must be
#: reachable — "no field has any evidence" must never read as "every field is
#: corroborated").
FIELD_CONFIDENCE_SETS = st.frozensets(
    st.sampled_from(
        [
            FIELD_CONFIDENCE_CORROBORATED,
            FIELD_CONFIDENCE_UNKNOWN,
            FIELD_CONFIDENCE_CONFLICTED,
            "SINGLE_SOURCE",
            "STALE",
        ]
    ),
    min_size=0,
    max_size=5,
)

#: Change-trigger sets **including the empty set** (the §6.3 M3 fail-open direction).
CHANGE_TRIGGER_SETS = st.frozensets(
    st.sampled_from(
        ["venue-snapshot-1", "admissibility-decision-1", "route-binding-1"]
    ),
    min_size=0,
    max_size=3,
)

#: Truthy non-``bool`` values that pass an ``if X:`` gate but are not the singleton
#: ``True``. Every positive-polarity premise is ``bool | None``-annotated only, so an
#: ``is True`` gate is the sole structural defence (design #21 §0.1(8)).
TRUTHY_NON_BOOL: list[Any] = ["UNKNOWN", "False", 1, 1.0, [1], {"a": 1}, object()]

#: Values that are **not** the singleton ``False`` but which an ``is not True`` gate would
#: wrongly clear on a relaxation-condition field. ``None`` is the fail-open itself —
#: "Unknown materiality is material".
NON_FALSE_VALUES: list[Any] = [None, 0, "", [], "False", "no", 0.0]

#: Values a forged (``model_construct``) authority flag can carry, on **both** polarity
#: axes — none of them is the singleton ``False``, which is the only value
#: :func:`~tos.nontrade.nontrade_authority_effect_all_false` accepts (design #21 §5.4).
#:
#: * the **truthy** half (``True`` / ``1`` / ``1.0`` / ``"yes"`` / ``[1]`` / a dict) is what
#:   an ``is not True`` re-check would wrongly clear (the afg M3 regression);
#: * the **falsy** half (``None`` / ``0`` / ``""`` / ``[]`` / ``0.0``) is what a bare
#:   ``not getattr(...)`` re-check would wrongly clear — a forged ``None`` "unknown" flag
#:   is not a proof that the label grants nothing, and ``0 is False`` is ``False`` in
#:   Python, so only the identity test rejects it.
#:
#: Locking both halves is what makes the ``is False`` singleton test structurally
#: necessary rather than merely stylistic.
FORGED_AUTHORITY_VALUES: list[Any] = [
    # truthy forgeries
    True,
    1,
    1.0,
    "yes",
    [1],
    {"granted": True},
    # falsy forgeries — not the singleton ``False`` either
    None,
    0,
    "",
    [],
    0.0,
]

#: The **phantom** negative-polarity / netting-flag field names design #21 M7 deleted (or
#: never authored). Phase-1 nontrade has **zero** negative-polarity fields, and a §7
#: property asserts these names never reappear on any model — a forgeable flag must not
#: sneak back in on the very axes the design closed structurally. ``netting_applied`` is
#: included because it is the *positive* spelling of the same forgeable no-netting flag the
#: replacement design removed at the source (design #18 M6 / #21 §0.4d): no-netting is
#: proven by two coexisting non-negative magnitudes, never by a boolean in either polarity.
PHANTOM_NEGATIVE_POLARITY_FIELDS: tuple[str, ...] = (
    "favorable_netted",
    "netting_applied",
    "destructive_overwrite",
    "released_on_transformation",
)


# ---------------------------------------------------------------------------
# Value-model builders
# ---------------------------------------------------------------------------


def clean_leg_magnitudes(
    **overrides: Decimal | None,
) -> dict[CredibleTransitionLegKind, Decimal | None]:
    """Per-leg magnitudes for all ten legs, keyed by the enum member *name* for overrides."""
    base: dict[CredibleTransitionLegKind, Decimal | None] = {
        leg: Decimal("1") for leg in CredibleTransitionLegKind
    }
    for name, value in overrides.items():
        base[CredibleTransitionLegKind[name]] = value
    return base


def clean_envelope(**overrides: Any) -> TransitionEnvelope:
    """A genuinely complete envelope: all 10 legs + two coexisting non-negative exposures.

    The two exposures coexist because netting would have erased or reduced one of them —
    the structural no-netting proof (design #21 §0.4d), never a flag.
    """
    base: dict[str, Any] = {
        "present_legs": tuple(CredibleTransitionLegKind),
        "leg_magnitudes": clean_leg_magnitudes(),
        # old and new are BOTH counted (§9 line 187 / §12 line 248): double counting is the
        # conservative requirement, and rcl / are do the summation and projection.
        "pre_event_exposure": Decimal("7"),
        "post_event_credible_exposure": Decimal("5"),
    }
    base.update(overrides)
    return TransitionEnvelope(**base)


def clean_spec(**overrides: Any) -> SplitTransformationSpec:
    """A genuine forward split: derived directions match the declared kind.

    Quantity rises and basis falls, so :func:`~tos.nontrade.split_polarity_coherent`
    derives ``(AMPLIFY, ATTENUATE)`` and truth table B matches ``FORWARD_SPLIT``. The
    magnitudes are fixture values, **not** a ratio constant — the predicate compares them,
    it never multiplies by a hardcoded factor.
    """
    base: dict[str, Any] = {
        "kind": SplitTransformationKind.FORWARD_SPLIT,
        "pre_quantity": Decimal("10"),
        "post_quantity": Decimal("30"),
        "pre_basis": Decimal("9"),
        "post_basis": Decimal("3"),
        "unit_spec": "shares/contract; executable-order-quantity separate",
        "rounding_rule": "round-down-to-whole; residual explicit",
        "fractional_residual": Decimal("0.5"),
        "cash_in_lieu": Decimal("4"),
    }
    base.update(overrides)
    return SplitTransformationSpec(**base)


def spec_for_directions(
    quantity: TransformationDirection,
    basis: TransformationDirection,
    **overrides: Any,
) -> SplitTransformationSpec:
    """Build a spec whose **derived** directions are exactly ``(quantity, basis)``.

    Used to walk the 3x3 truth table A exhaustively without ever declaring a direction: the
    fixture moves each magnitude up, down, or not at all, and the predicate derives.
    """

    def _pair(direction: TransformationDirection) -> tuple[Decimal, Decimal]:
        if direction is TransformationDirection.AMPLIFY:
            return Decimal("10"), Decimal("30")
        if direction is TransformationDirection.ATTENUATE:
            return Decimal("30"), Decimal("10")
        return Decimal("10"), Decimal("10")

    pre_quantity, post_quantity = _pair(quantity)
    pre_basis, post_basis = _pair(basis)
    base: dict[str, Any] = {
        "pre_quantity": pre_quantity,
        "post_quantity": post_quantity,
        "pre_basis": pre_basis,
        "post_basis": post_basis,
    }
    base.update(overrides)
    return clean_spec(**base)


# ---------------------------------------------------------------------------
# Digest-bound artifact builders
# ---------------------------------------------------------------------------


def issue_event(**overrides: Any) -> NonTradeEventRecord:
    """Issue a valid :class:`NonTradeEventRecord` (all required covered concrete)."""
    base: dict[str, Any] = {
        "event_id": "nt-event-1",
        "event_class": NonTradeEventClass.CORPORATE_ACTION,
        "event_subtype": "split",
        "source_identities": ("issuer-1", "venue-1", "broker-1", "clearing-1"),
        "source_event_ids": ("src-evt-1",),
        "source_event_versions": ("v1",),
        # the seven §5 line 106 times stay SEVEN fields (§8 line 171 no-collapse)
        "announcement_time": "t-announcement",
        "observation_time": "t-observation",
        "record_time": "t-record",
        "ex_time": "t-ex",
        "effective_time": "t-effective",
        "payable_time": "t-payable",
        "settlement_time": "t-settlement",
        "affected_account_scopes": ("acct-1",),
        "affected_portfolio_scopes": ("pf-1",),
        "affected_instrument_scopes": ("instr-old-1", "instr-new-1"),
        "affected_currency_scopes": ("ccy-1",),
        "affected_broker_scopes": ("broker-1",),
        "old_instrument_identity": "canonical-instrument-old-1",
        "new_instrument_identity": "canonical-instrument-new-1",
        "transformation_spec": clean_spec(),
        "transition_envelope": clean_envelope(),
        "eligibility_conditions": ("holder-of-record",),
        "election_conditions": ("default-election",),
        "broker_treatment_profile": "corporate-administrative-events-profile-1",
        "expected_open_order_behavior": "open-order-query-supported",
        "per_field_confidence": {
            "INSTRUMENT_IDENTITY": FIELD_CONFIDENCE_CORROBORATED,
            "EXTERNAL_UNATTRIBUTED_ACTIVITY": FIELD_CONFIDENCE_CORROBORATED,
        },
        "safety_profile_version": "sp-v1",
        "broker_capability_profile_version": "bcp-v1",
        "verification_profile_version": "vp-002",
        "calendar_version": "cal-v1",
        "instrument_master_version": "im-v1",
        "workflow_generation": 1,
        "idempotency_key": "nt-idem-1",
        "supersedes_ref": None,
        "lineage_refs": (),
        "workflow_state": NonTradeEventWorkflowState.OBSERVED,
        # §6 line 123 orthogonal axes — five SEPARATE injected coordinate tokens
        "order_state": "WORKING",
        "exposure_state": "OPEN",
        "capacity_state": "COMMITTED",
        "authority_state": "ARMED",
        "evidence_confidence_state": FIELD_CONFIDENCE_CORROBORATED,
    }
    base.update(overrides)
    return NonTradeEventRecord.issue(scheme=SCHEME, **base)


def issue_correction(**overrides: Any) -> CorrectionReversalRecord:
    """Issue a valid :class:`CorrectionReversalRecord` (lineage + retained original)."""
    base: dict[str, Any] = {
        "correction_id": "nt-corr-1",
        "correction_generation": 1,
        "correction_kind": "CORRECTION",
        "corrected_event_id": "nt-event-1",
        "supersedes_ref": "nt-event-1",
        "lineage_refs": ("nt-event-1",),
        "original_observation_ref": "nt-obs-1",
        "idempotency_key": "nt-corr-idem-1",
        "economic_effect_scopes": ("acct-1",),
        "corrected_transition_envelope": clean_envelope(),
        "safety_profile_version": "sp-v1",
        "verification_profile_version": "vp-002",
        "capacity_state": "COMMITTED",
        "evidence_confidence_state": FIELD_CONFIDENCE_CORROBORATED,
    }
    base.update(overrides)
    return CorrectionReversalRecord.issue(scheme=SCHEME, **base)


# ---------------------------------------------------------------------------
# Composite helpers used across several test modules
# ---------------------------------------------------------------------------


def clean_disposition_inputs(**overrides: Any) -> dict[str, Any]:
    """Every §5.5 conjunct positively proven — the genuine ``NONTRADE_ADMISSIBLE`` fixture.

    The availability side of the both-ways discipline: if this fixture did not reach
    ``NONTRADE_ADMISSIBLE`` the whole suite would be a vacuous-block, which is as much a
    defect as a vacuous-admit (design #21 §4.7).
    """
    base: dict[str, Any] = {
        "envelope_complete": True,
        "netting_absent": True,
        "polarity_coherent": True,
        "units_and_rounding_explicit": True,
        "residual_conservative": True,
        "correction_outcome": CorrectionReversalOutcome.APPLIED_ONCE,
        "lineage_preserved": True,
        "effective_window_blocks": True,
        "material_change_triggers_present": True,
        "event_is_material": True,
        "field_confidences": frozenset({FIELD_CONFIDENCE_CORROBORATED}),
        "admissibility": ORDER_ADMISSIBILITY_ADMISSIBLE,
        "protective_action_may_proceed": None,
        "injected_worst_intermediate_risk": Decimal("12"),
        "injected_credible_space_bounded": True,
        "injected_union_capacity_known": True,
    }
    base.update(overrides)
    return base


def clean_lineage_inputs(**overrides: Any) -> dict[str, Any]:
    """The §6.1 instrument-lineage conjuncts, all positively satisfied."""
    base: dict[str, Any] = {
        "old_route_identity": "canonical-instrument-old-1",
        "new_route_identity": "canonical-instrument-new-1",
        "admissibility": ORDER_ADMISSIBILITY_ADMISSIBLE,
        "protective_action_may_proceed": None,
        "identity_transition_final": None,
    }
    base.update(overrides)
    return base


def clean_window_inputs(**overrides: Any) -> dict[str, Any]:
    """The §6.2 effective-time-window conjuncts, all positively satisfied."""
    base: dict[str, Any] = {
        "earliest_credible_boundary": "t-earliest",
        "latest_completion_boundary": "t-latest",
        "time_freshness": FRESHNESS_VERDICT_FRESH,
        "source_disagreement_bounded": True,
    }
    base.update(overrides)
    return base


#: The full ten-leg universe, re-exported for convenience in the envelope tests.
ALL_LEGS = CREDIBLE_TRANSITION_LEG_MINIMUM_SET
