"""Shared valid-artifact builders + strategies for the posttrade property tests (§7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #24 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be
*genuinely* admissible, never a permissive shortcut):

* a **clean** :class:`~tos.posttrade.EconomicObligationRecord` fills every
  ``_REQUIRED_COVERED`` path with a concrete value (never the reserved ``"TBD"``
  placeholder) and carries an all-false consequence block;
* a **clean** :class:`~tos.posttrade.PostTradeFinalityProof` carries a **fully specified**
  six-component scope whose finality class equals the proof's, a present amount, a bound
  generation, and a non-empty ``does_not_prove``;
* a **clean** :class:`~tos.posttrade.StatementCoverageManifest` is ``FINAL``, has every
  expected set a subset of its received set with at least one non-empty axis, matching record
  counts, no missing interval, and a full period / revision / cutoff identity;
* a **clean** collateral ladder is exclusively free **or** encumbered per unit, pledges within
  the available magnitude, and reuses a unit only after a positively declared
  ``CONFIRMED_RELEASE``;
* the **∅ strategies** deliberately generate empty required-leg sets, empty coverage sets,
  empty dependency sets, empty allocation sequences, and empty proof maps so the ∅-void
  guards are actually exercised (the #10 lesson — a strategy that never emits an empty set
  leaves the ∅ branch untested);
* the **forgery strategies** deliberately generate **both** truthy and **falsy** non-``bool``
  values (``1`` / ``0`` / ``""`` / ``"yes"`` / ``[]`` / ``[1]``), raw member strings, ``None``,
  and nonsense tokens (the #16 lesson — a strategy that only samples safe enum members cannot
  catch a fall-through gate; the falsy axis additionally catches a guard that leans on
  truthiness instead of ``is True``).

Every magnitude is an explicit fixture value: nothing here is a *policy* number — the real
post-trade timing, age, and currentness bounds are Verification-Profile injected and are
**all null (and ``owner: TBD``) in Phase 1** (design #24 §8.1, all 19 keys). No concrete
broker, clearing house, custodian, or bank is named anywhere.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.posttrade import (
    CashKind,
    CollateralAllocation,
    EconomicObligationRecord,
    EventObligationLegKind,
    FinalityDimensionKind,
    MarginCollateralState,
    MonetaryLeg,
    ObligationCommitOutcome,
    ObligationLeg,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeBreakRecord,
    PostTradeDisposition,
    PostTradeFinalityProof,
    PostTradeObligationLifecycleState,
    StatementClass,
    StatementCoverageManifest,
)
from tos.posttrade.vocabulary import FIELD_CONFIDENCE_CORROBORATED

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

# ---------------------------------------------------------------------------
# Scalar strategies
# ---------------------------------------------------------------------------

#: Injected ``bool | None`` flag. ``None`` is UNKNOWN — never a soft pass.
TRIBOOL = st.sampled_from([True, False, None])

#: A **forged** flag value: the three legitimate ``bool | None`` values plus truthy **and
#: falsy** non-``bool`` values that a truthiness-based gate would mis-read in either
#: direction (design #24 §7 — the forgery strategy must carry a falsy axis).
FORGED_FLAG = st.sampled_from([True, False, None, 1, 0, "", "yes", "", [], [1], "True"])

#: A finite non-negative magnitude (NaN / infinity are unconstructable, §3.1).
FINITE_NON_NEGATIVE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A finite **positive** magnitude (strictly above the structural zero).
FINITE_POSITIVE = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A finite **negative** magnitude — a sign error on the gross obligation / collateral axes.
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

#: The twelve obligation lifecycle states (8 linear + 4 branch).
LIFECYCLE_STATES = st.sampled_from(list(PostTradeObligationLifecycleState))

#: The ten orthogonal finality dimensions.
FINALITY_DIMENSIONS = st.sampled_from(list(FinalityDimensionKind))

#: The eight obligation leg directions.
LEG_DIRECTIONS = st.sampled_from(list(ObligationLegDirection))

#: Leg-direction subsets **including the empty set** (∅ must be reachable — it is the
#: structural guard of ``obligation_leg_set_complete``).
LEG_DIRECTION_SETS = st.frozensets(LEG_DIRECTIONS, min_size=0, max_size=8)

#: The nine event obligation leg kinds.
EVENT_LEG_KINDS = st.sampled_from(list(EventObligationLegKind))

#: Event-leg subsets **including the empty set**.
EVENT_LEG_SETS = st.frozensets(EVENT_LEG_KINDS, min_size=0, max_size=9)

#: The six cash kinds.
CASH_KINDS = st.sampled_from(list(CashKind))

#: The eight margin / collateral states.
MARGIN_STATES = st.sampled_from(list(MarginCollateralState))

#: The three statement classes **plus** ``None`` (an undeclared classification).
STATEMENT_CLASSES_OR_NONE = st.sampled_from([*StatementClass, None])

#: The six commit outcomes.
COMMIT_OUTCOMES = st.sampled_from(list(ObligationCommitOutcome))

#: The five dispositions.
DISPOSITIONS = st.sampled_from(list(PostTradeDisposition))

#: The three real recon ``FieldConfidenceClass`` tokens this package reads, plus the two it
#: does not (``SINGLE_SOURCE`` / ``STALE`` are non-empty truthy strings and are **not**
#: corroboration), plus ``None`` and a forged token.
FIELD_CONFIDENCE_TOKENS_OR_NONE: list[str | None] = [
    "CORROBORATED",
    "UNKNOWN",
    "CONFLICTED",
    "SINGLE_SOURCE",
    "STALE",
    "",
    "corroborated",
    "FORGED",
    None,
]
FIELD_CONFIDENCE_TOKENS = st.sampled_from(FIELD_CONFIDENCE_TOKENS_OR_NONE)

#: Injected nontrade ``NonTradeEventWorkflowState`` tokens plus forged / falsy ones. Every
#: one of them must leave ``event_state_not_obligation_finality`` unchanged.
EVENT_STATE_TOKENS = st.sampled_from(
    [
        "APPLIED_LOCAL",
        "RECONCILED",
        "OBSERVED",
        "QUARANTINED_UNKNOWN",
        "",
        "applied_local",
        "FINALITY_PROVEN",
        None,
    ]
)

#: Dependency-name sets **including the empty set** (∅ on either side must fail closed).
DEPENDENCY_SETS = st.frozensets(
    st.sampled_from(
        ["book", "parser", "administrator", "transport", "feed", "archive"]
    ),
    min_size=0,
    max_size=4,
)


# ---------------------------------------------------------------------------
# Per-dimension finality proof maps
# ---------------------------------------------------------------------------


def proof_map_only(
    dimension: FinalityDimensionKind,
) -> dict[FinalityDimensionKind, bool]:
    """A proof map in which exactly one dimension is proven and the other nine are not.

    The FQP non-implication fixture: ``proof_map_only(ORDER_FQP)`` is the state ADR §12 line
    340-345 describes — a final quantity proof and nothing else.

    Args:
        dimension: The single proven dimension.

    Returns:
        A ten-entry map with ``True`` on ``dimension`` and ``False`` elsewhere.
    """
    return {member: member is dimension for member in FinalityDimensionKind}


#: Proof maps over the ten dimensions with ``True`` / ``False`` / ``None`` entries, **plus**
#: the empty map (the ∅ guard of both ``finality_dimensions_orthogonal`` and
#: ``event_state_not_obligation_finality``).
PROOF_MAPS = st.dictionaries(
    FINALITY_DIMENSIONS,
    st.sampled_from([True, False, None]),
    min_size=0,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Clean artifact builders
# ---------------------------------------------------------------------------

#: The **single source of truth** for a genuinely complete issue-content dict per digest-bound
#: citizen. Every ``clean_*`` builder copies its entry, and the review MINOR-2 canary in
#: ``test_posttrade_records`` knocks one required field out of the *same* dict at a time — so
#: a builder and the canary can never disagree about what "complete" means.
CLEAN_ISSUE_CONTENT: dict[type, dict[str, Any]] = {
    EconomicObligationRecord: {
        "obligation_id": "OBL-1",
        "obligation_type": "SETTLEMENT_LEG",
        "obligation_version": "V1",
        "obligation_generation": 1,
        "idempotency_key": "IDEM-1",
        "lifecycle_state": PostTradeObligationLifecycleState.DUE,
        "account_scope": "ACCOUNT-A",
        "currency": "CUR-A",
    },
    PostTradeFinalityProof: {
        "proof_id": "PRF-1",
        "obligation_ref": "OBL-1",
        "obligation_version": "V1",
        "leg_scope": ObligationLegScope(
            leg=ObligationLegDirection.DEBIT,
            account="ACCOUNT-A",
            currency="CUR-A",
            value_date="VD-1",
            source_revision="REV-1",
            finality_class=FinalityDimensionKind.SETTLEMENT,
        ),
        "amount": Decimal("10.00"),
        "finality_class": FinalityDimensionKind.SETTLEMENT,
        "bound_generation": 1,
        "does_not_prove": ("CASH_AVAILABILITY", "CUSTODY_TITLE"),
        "proof_recipe_id": "RECIPE-1",
        "source_revision": "REV-1",
        "idempotency_key": "IDEM-P1",
    },
    StatementCoverageManifest: {
        "manifest_id": "MAN-1",
        "source_identity": "SOURCE-A",
        "period_start": "P-START",
        "period_end": "P-END",
        "revision": "R1",
        "issue_id": "ISS-1",
        "cutoff": "CUTOFF-1",
        "statement_class": StatementClass.FINAL,
        "expected_pages": frozenset({"p1", "p2"}),
        "received_pages": frozenset({"p1", "p2"}),
        "expected_files": frozenset({"f1"}),
        "received_files": frozenset({"f1"}),
        "expected_sections": frozenset({"s1"}),
        "received_sections": frozenset({"s1"}),
        "expected_cursors": frozenset({"c1"}),
        "received_cursors": frozenset({"c1"}),
        "expected_checksums": frozenset({"h1"}),
        "received_checksums": frozenset({"h1"}),
        "expected_record_count": 2,
        "received_record_count": 2,
        "missing_intervals": (),
        "shared_dependencies": frozenset({"book-a", "transport-a"}),
        "manifest_generation": 1,
        "idempotency_key": "IDEM-M1",
    },
    PostTradeBreakRecord: {
        "break_id": "BRK-1",
        "break_scope": "ACCOUNT-A",
        "source_revision": "REV-1",
        "old_obligation_version": "V1",
        "new_obligation_version": "V2",
        "affected_obligation_refs": ("OBL-1",),
        "break_generation": 1,
        "idempotency_key": "IDEM-B1",
    },
}


def clean_scope(**overrides: Any) -> ObligationLegScope:
    """A fully specified six-component :class:`ObligationLegScope`.

    Args:
        **overrides: Field overrides (used to build the *illegal* under-specified and
            cross-leg variants).

    Returns:
        The scope value model.
    """
    fields: dict[str, Any] = {
        "leg": ObligationLegDirection.DEBIT,
        "account": "ACCOUNT-A",
        "currency": "CUR-A",
        "value_date": "VD-1",
        "source_revision": "REV-1",
        "finality_class": FinalityDimensionKind.SETTLEMENT,
    }
    fields.update(overrides)
    return ObligationLegScope(**fields)


def clean_obligation_record(**overrides: Any) -> EconomicObligationRecord:
    """An ISSUED :class:`EconomicObligationRecord` with every required covered field concrete.

    Args:
        **overrides: Covered-content overrides (an override that changes covered content
            changes the digest, which is exactly how the forgery fixtures are built).

    Returns:
        The issued, digest-verified obligation record.
    """
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[EconomicObligationRecord])
    content.update(overrides)
    record = EconomicObligationRecord.issue(scheme=SCHEME, **content)
    assert isinstance(record, EconomicObligationRecord)
    return record


def clean_finality_proof(**overrides: Any) -> PostTradeFinalityProof:
    """An ISSUED :class:`PostTradeFinalityProof` that satisfies the §5.7 conjunction.

    Args:
        **overrides: Covered-content overrides.

    Returns:
        The issued, digest-verified finality proof.
    """
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[PostTradeFinalityProof])
    content.update(overrides)
    proof = PostTradeFinalityProof.issue(scheme=SCHEME, **content)
    assert isinstance(proof, PostTradeFinalityProof)
    return proof


def clean_statement_manifest(**overrides: Any) -> StatementCoverageManifest:
    """An ISSUED :class:`StatementCoverageManifest` with proven complete coverage.

    Args:
        **overrides: Covered-content overrides.

    Returns:
        The issued, digest-verified coverage manifest.
    """
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[StatementCoverageManifest])
    content.update(overrides)
    manifest = StatementCoverageManifest.issue(scheme=SCHEME, **content)
    assert isinstance(manifest, StatementCoverageManifest)
    return manifest


def clean_break_record(**overrides: Any) -> PostTradeBreakRecord:
    """An ISSUED :class:`PostTradeBreakRecord` (substrate only — no break judgment exists).

    Args:
        **overrides: Covered-content overrides.

    Returns:
        The issued, digest-verified break record.
    """
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[PostTradeBreakRecord])
    content.update(overrides)
    record = PostTradeBreakRecord.issue(scheme=SCHEME, **content)
    assert isinstance(record, PostTradeBreakRecord)
    return record


def clean_monetary_leg(**overrides: Any) -> MonetaryLeg:
    """A conservative :class:`MonetaryLeg` (present, finite, explicitly classified amount).

    Args:
        **overrides: Field overrides.

    Returns:
        The monetary leg value model.
    """
    fields: dict[str, Any] = {
        "monetary_type": "FEE",
        "amount": Decimal("3.50"),
        "basis": "NOTIONAL",
        "period": "PERIOD-1",
        "amount_status": "BROKER_BOOKED",
        "booked_zero": None,
        "source_confidence": FIELD_CONFIDENCE_CORROBORATED,
    }
    fields.update(overrides)
    return MonetaryLeg(**fields)


def clean_leg(
    direction: ObligationLegDirection = ObligationLegDirection.CREDIT,
    magnitude: Decimal | None = Decimal("5.00"),
    **overrides: Any,
) -> ObligationLeg:
    """A gross :class:`ObligationLeg` with a present non-negative magnitude.

    Args:
        direction: The leg direction.
        magnitude: The gross magnitude (``None`` builds the UNKNOWN variant).
        **overrides: Further field overrides.

    Returns:
        The obligation leg value model.
    """
    fields: dict[str, Any] = {
        "direction": direction,
        "magnitude": magnitude,
        "scope": clean_scope(leg=direction),
    }
    fields.update(overrides)
    return ObligationLeg(**fields)


def clean_allocation(
    unit_id: str = "UNIT-1",
    *,
    encumbered: bool = False,
    **overrides: Any,
) -> CollateralAllocation:
    """A conserved :class:`CollateralAllocation` — exclusively free or exclusively encumbered.

    Args:
        unit_id: The collateral unit identity.
        encumbered: When ``True`` the unit is encumbered against exactly one obligation;
            otherwise it is free and pledges nothing.
        **overrides: Further field overrides (used to build the illegal variants).

    Returns:
        The collateral allocation value model.
    """
    if encumbered:
        fields: dict[str, Any] = {
            "unit_id": unit_id,
            "free_magnitude": Decimal("0"),
            "encumbered_magnitude": Decimal("4.00"),
            "pledged_magnitude": Decimal("4.00"),
            "available_magnitude": Decimal("10.00"),
            "pledged_obligation_ids": ("OBL-1",),
            "release_state": MarginCollateralState.PLEDGED_COLLATERAL,
        }
    else:
        fields = {
            "unit_id": unit_id,
            "free_magnitude": Decimal("10.00"),
            "encumbered_magnitude": Decimal("0"),
            "pledged_magnitude": Decimal("0"),
            "available_magnitude": Decimal("10.00"),
            "pledged_obligation_ids": (),
            "release_state": MarginCollateralState.AVAILABLE_EXCESS,
        }
    fields.update(overrides)
    return CollateralAllocation(**fields)


def clean_disposition_kwargs(**overrides: Any) -> dict[str, Any]:
    """The nineteen ``post_trade_disposition`` inputs in their fully proven configuration.

    This is the **only** configuration that reaches ``POST_TRADE_ADMISSIBLE``, and it needs a
    simulated ``availability_proven=True`` — an L1-only caller always passes ``None`` there
    and lands on ``POST_TRADE_TRAPPED`` at best (design #24 §5.8 honest disclosure). Every
    void-table canary is this dict with exactly one entry flipped.

    Args:
        **overrides: Input overrides.

    Returns:
        The keyword-argument mapping.
    """
    kwargs: dict[str, Any] = {
        "leg_set_complete": True,
        "finality_orthogonal": True,
        "monetary_conservative": True,
        "netting_proof_ok": True,
        "counterleg_established": True,
        "collateral_conserved": True,
        "margin_states_distinct": True,
        "cash_kind_ok": True,
        "event_legs_complete": True,
        "event_state_not_final_ok": True,
        "statement_coverage_ok": True,
        "sources_independent": True,
        "absence_gate_ok": True,
        "proof_class_specific": True,
        "proof_non_transferable": True,
        "proof_current": True,
        "commit_outcome": ObligationCommitOutcome.COMMITTED_ONCE,
        "field_confidence": FIELD_CONFIDENCE_CORROBORATED,
        "availability_proven": True,
    }
    kwargs.update(overrides)
    return kwargs
