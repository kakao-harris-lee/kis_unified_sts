"""**Mandated L1 property test #1** — ``critical_coverage_complete_or_gap`` (STM-EV-001 yolk 1; §9).

design #30 §13: STM-AC-001 ↔ STM-EV-001 is one of only **two** rows with an ``EV-L1`` slice, and this
file is its mandated model / property verification. It verifies the L1-decidable part **and closes
nothing**: STM-EV-001 is ``EV-L1/3+Security``, so the ``/3`` integration axis and the whole
``+Security`` coverage-forgery / suppression-resistance axis (§22 line 472-479) remain, and the
conservative coverage compiler and requirement/hazard registry are runtime, independently reviewed (§30
gate 2). Authoring is not evidence (ADR §27 line 594).

Both ways for every conjunct (design #30 §7.2): "all conditions hold ⇒ ``True``" **and** "each condition
violated individually ⇒ ``False``". The **C1 fixtures are mandated separately**: ``excluded=None`` is
asserted against *each* of the two conjuncts it touches — the tally filter (conjunct 3) and the
approved-exclusion gate (conjunct 4) — because the contract's own v1.0 wrote ``is not True`` there and
let an unknown exclusion be counted as covered.

Regime tag: coverage-completeness predicate substrate only; closes **no** STM-EV; EV-L1-complete claim
forbidden.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.stm import (
    COVERAGE_CLOSURE_ITEM_COUNT,
    AllFalseMonitoringAuthority,
    CoverageDimension,
    MonitorCoverageManifest,
    TelemetryCriticality,
    coverage_grants_no_authority,
    critical_coverage_complete_or_gap,
    monitored_assumption_intake_closed,
    no_self_exemption,
)

from ._stm_strategies import (
    CLEAN_APPLICABLE_DIMENSIONS,
    CLEAN_APPLICABLE_OBLIGATIONS,
    CLEAN_ASSUMPTION_OBLIGATION,
    CLEAN_OBLIGATION,
    CLEAN_SUBMITTED_ASSUMPTION_IDS,
    TRIBOOL,
    clean_assumption_intake,
    clean_coverage_item,
    clean_coverage_manifest,
)


def _judge(manifest: MonitorCoverageManifest | None, **overrides: object) -> bool:
    """Run the yolk against the clean applicable coordinates unless overridden."""
    return critical_coverage_complete_or_gap(
        manifest,
        overrides.get("obligations", CLEAN_APPLICABLE_OBLIGATIONS),  # type: ignore[arg-type]
        overrides.get("dimensions", CLEAN_APPLICABLE_DIMENSIONS),  # type: ignore[arg-type]
        overrides.get("assumptions", CLEAN_SUBMITTED_ASSUMPTION_IDS),  # type: ignore[arg-type]
    )


# --- direction 1: the clean manifest clears --------------------------------


def test_clean_manifest_is_complete_and_exact() -> None:
    """(both-ways +) A genuinely complete, unexempted, non-authorizing manifest clears."""
    assert _judge(clean_coverage_manifest()) is True


def test_clean_fixture_is_not_vacuous() -> None:
    """(anti-vacuity) The clean fixture really exercises every axis — two obligations, all dimensions."""
    manifest = clean_coverage_manifest()
    assert len(manifest.coverage_items) == 2
    assert len(CLEAN_APPLICABLE_OBLIGATIONS) == 2
    assert frozenset(CoverageDimension) == CLEAN_APPLICABLE_DIMENSIONS
    assert len(CLEAN_APPLICABLE_DIMENSIONS) == 11
    assert manifest.submitted_monitored_assumptions != ()


# --- conjunct 1: ∅ both-ways, applicable side first ------------------------


def test_absent_manifest_denies() -> None:
    """(conjunct 1) ``None`` is undecidable, therefore denied."""
    assert (
        critical_coverage_complete_or_gap(None, frozenset(), frozenset(), frozenset())
        is False
    )


def test_explicit_empty_manifest_against_empty_applicable_set_is_valid() -> None:
    """(conjunct 1, #26 MAJOR-1) A no-obligation scope is a real state — rejecting it would over-seal."""
    manifest = clean_coverage_manifest(
        coverage_items=(), submitted_monitored_assumptions=()
    )
    assert (
        critical_coverage_complete_or_gap(
            manifest, frozenset(), frozenset(), frozenset()
        )
        is True
    )


def test_empty_manifest_against_non_empty_applicable_set_denies() -> None:
    """(conjunct 1) Missing coverage is a **gap, not an exemption** (STM-INV-002 line 163)."""
    manifest = clean_coverage_manifest(
        coverage_items=(), submitted_monitored_assumptions=()
    )
    assert _judge(manifest) is False


def test_non_empty_manifest_against_empty_applicable_set_denies_as_surplus() -> None:
    """(conjunct 1, both ways) Phantom coverage over no applicable obligation denies."""
    assert (
        critical_coverage_complete_or_gap(
            clean_coverage_manifest(), frozenset(), frozenset(), frozenset()
        )
        is False
    )


def test_explicit_empty_requires_a_positive_completeness_claim() -> None:
    """(conjunct 1) The valid explicit-empty still needs ``is_complete is True``."""
    for claim in (False, None):
        manifest = MonitorCoverageManifest(
            coverage_manifest_id="coverage-manifest-1",
            coverage_generation=7,
            policy_digest="policy-digest-1",
            is_complete=claim,
            coverage_score_present=False,
        )
        assert (
            critical_coverage_complete_or_gap(
                manifest, frozenset(), frozenset(), frozenset()
            )
            is False
        )


# --- conjunct 2: all-false authority ---------------------------------------


def test_authority_bearing_manifest_denies() -> None:
    """(conjunct 2, STM-INV-001 line 159) A manifest that grants anything is not coverage."""
    forged = AllFalseMonitoringAuthority.model_construct(issues_authority=True)
    manifest = clean_coverage_manifest().model_copy(update={"authority_effect": forged})
    assert coverage_grants_no_authority(manifest) is False
    assert _judge(manifest) is False


def test_coverage_grants_no_authority_denies_on_absent_manifest() -> None:
    """(conjunct 2) An absent manifest cannot prove non-authority."""
    assert coverage_grants_no_authority(None) is False


# --- the §9 "complete and exact" claim + conjunct 5 ------------------------


@pytest.mark.parametrize("claim", [False, None])
def test_incomplete_claim_denies(claim: bool | None) -> None:
    """(§4.3 positive polarity) ``is_complete`` denies on ``False`` **and** on an unknown ``None``."""
    assert _judge(clean_coverage_manifest(is_complete=claim)) is False


@pytest.mark.parametrize("score", [True, None])
def test_a_score_cannot_replace_item_level_closure(score: bool | None) -> None:
    """(conjunct 5, §9 line 292) A completeness *score* denies — and so does an unknown one."""
    assert _judge(clean_coverage_manifest(coverage_score_present=score)) is False


# --- conjunct 3: completeness both ways, with the C1 tally filter ----------


def test_a_missing_applicable_obligation_denies() -> None:
    """(conjunct 3, STM-INV-002 line 163) One unmapped obligation is a gap."""
    manifest = clean_coverage_manifest(
        coverage_items=(clean_coverage_item(),),
        submitted_monitored_assumptions=(),
    )
    assert (
        critical_coverage_complete_or_gap(
            manifest,
            CLEAN_APPLICABLE_OBLIGATIONS,
            CLEAN_APPLICABLE_DIMENSIONS,
            frozenset(),
        )
        is False
    )


@pytest.mark.parametrize(
    "field",
    [
        "closure_1_to_12_complete",
        "restrictive_response_present",
        "alert_path_present",
        "evidence_path_present",
        "currentness_rule_present",
    ],
)
@pytest.mark.parametrize("value", [False, None])
def test_each_item_level_closure_flag_denies_individually(
    field: str, value: bool | None
) -> None:
    """(conjunct 3, both-ways) Each §9 item flag denies on ``False`` and on an unknown ``None``."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(**{field: value}),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        )
    )
    assert _judge(manifest) is False


def test_c1_excluded_none_is_not_counted_as_covered() -> None:
    """(**C1 mandated, conjunct 3**) An ``excluded=None`` item is NOT in the coverage tally.

    The contract's own v1.0 filtered with ``excluded is not True``, which counted an unknown-exclusion
    item as covered. STM-INV-002 line 163: "Missing or **unknown** coverage is a gap, not an exemption."
    Here the *only* item covering the obligation carries ``excluded=None``, so the obligation is
    genuinely uncovered and the yolk must deny — even though every other flag on that item is clean and
    an approved-exclusion proof is supplied (so conjunct 4 cannot be what denies).
    """
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(excluded=None, approved_exclusion_proof_present=True),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        )
    )
    assert _judge(manifest) is False


def test_c1_excluded_none_fires_the_approved_exclusion_gate() -> None:
    """(**C1 mandated, conjunct 4**) An ``excluded=None`` item without a proof denies the gate itself.

    The second half of the C1 asymmetry: the §9 line 290 gate fires on ``excluded is not False``, so an
    unknown exclusion must be proven exactly like a claimed one. Asserted through
    :func:`no_self_exemption` directly so it cannot be confused with the conjunct-3 tally denial above.
    """
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(
                obligation_ref="obl-other",
                excluded=None,
                approved_exclusion_proof_present=None,
            ),
        )
    )
    assert no_self_exemption(manifest) is False


def test_a_proven_exclusion_is_admissible() -> None:
    """(conjunct 4, both-ways +) A positively proven exclusion clears the §9 line 290 gate."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
            clean_coverage_item(
                obligation_ref="obl-excluded",
                excluded=True,
                approved_exclusion_proof_present=True,
                criticality=TelemetryCriticality.NON_CRITICAL_APPROVED_EXCLUSION,
            ),
        )
    )
    assert no_self_exemption(manifest) is True
    assert _judge(manifest) is True


@pytest.mark.parametrize("proof", [False, None])
def test_an_unproven_exclusion_denies(proof: bool | None) -> None:
    """(conjunct 4, §9 line 290) A claimed exclusion without an independent proof denies."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
            clean_coverage_item(
                obligation_ref="obl-excluded",
                excluded=True,
                approved_exclusion_proof_present=proof,
            ),
        )
    )
    assert _judge(manifest) is False


def test_unknown_materiality_can_never_be_excluded_even_with_a_proof() -> None:
    """(conjunct 4, §8 line 249) "Unknown materiality is Critical" — no proof rescues an exclusion."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
            clean_coverage_item(
                obligation_ref="obl-unknown-materiality",
                excluded=True,
                approved_exclusion_proof_present=True,
                criticality=TelemetryCriticality.UNKNOWN_MATERIALITY,
            ),
        )
    )
    assert no_self_exemption(manifest) is False
    assert _judge(manifest) is False


def test_declared_approved_exclusions_are_reconciled_too() -> None:
    """(§4.4 group reconcile) The ``approved_exclusions`` tuple is checked, not just ``coverage_items``."""
    manifest = clean_coverage_manifest(
        approved_exclusions=(
            clean_coverage_item(
                obligation_ref="obl-excluded",
                excluded=True,
                approved_exclusion_proof_present=None,
            ),
        )
    )
    assert no_self_exemption(manifest) is False
    assert _judge(manifest) is False


# --- conjunct 6: dependency-closure completeness, inclusion only -----------


def test_an_unrepresented_dependency_dimension_denies() -> None:
    """(conjunct 6, §9 item 2) A dimension missing from the closure is an incompleteness."""
    narrowed = CLEAN_APPLICABLE_DIMENSIONS - {CoverageDimension.CLOCK}
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(dependency_closure_dimensions=narrowed),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        )
    )
    assert _judge(manifest) is False


def test_a_wider_dependency_closure_is_harmless() -> None:
    """(conjunct 6, MINOR-3 inclusion-only) A *wider* closure must not be rejected — over-sealing."""
    manifest = clean_coverage_manifest()
    narrow_applicable = frozenset({CoverageDimension.ACCOUNT})
    assert (
        critical_coverage_complete_or_gap(
            manifest,
            CLEAN_APPLICABLE_OBLIGATIONS,
            narrow_applicable,
            CLEAN_SUBMITTED_ASSUMPTION_IDS,
        )
        is True
    )


# --- conjunct 7: Monitored-Assumption intake (§9 line 288) ----------------


def test_an_out_of_band_assumption_denies() -> None:
    """(conjunct 7, §9 line 288) A submitted assumption with no intake is an out-of-band addition."""
    manifest = clean_coverage_manifest(submitted_monitored_assumptions=())
    assert (
        monitored_assumption_intake_closed(manifest, CLEAN_SUBMITTED_ASSUMPTION_IDS)
        is False
    )
    assert _judge(manifest) is False


def test_an_intake_that_is_not_a_manifest_item_denies() -> None:
    """(conjunct 7, §9 line 288) An intake whose id is no coverage item is out-of-band."""
    manifest = clean_coverage_manifest(
        submitted_monitored_assumptions=(
            clean_assumption_intake(assumption_id="obl-not-a-manifest-item"),
        )
    )
    assert (
        monitored_assumption_intake_closed(
            manifest, frozenset({"obl-not-a-manifest-item"})
        )
        is False
    )


@pytest.mark.parametrize(
    "field", ["admitted_as_coverage_item", "runtime_falsity_invalidates_property"]
)
@pytest.mark.parametrize("value", [False, None])
def test_each_intake_flag_denies_individually(field: str, value: bool | None) -> None:
    """(conjunct 7, both-ways) Both §9 line 288 intake flags are positive polarity."""
    manifest = clean_coverage_manifest(
        submitted_monitored_assumptions=(clean_assumption_intake(**{field: value}),)
    )
    assert (
        monitored_assumption_intake_closed(manifest, CLEAN_SUBMITTED_ASSUMPTION_IDS)
        is False
    )
    assert _judge(manifest) is False


def test_intake_closure_denies_on_absent_manifest() -> None:
    """(conjunct 7) An absent manifest cannot close an intake."""
    assert monitored_assumption_intake_closed(None, frozenset()) is False


# --- properties -----------------------------------------------------------


@given(
    excluded=TRIBOOL,
    proof=TRIBOOL,
    closure=TRIBOOL,
)
def test_only_the_fully_positive_shape_clears(
    excluded: bool | None, proof: bool | None, closure: bool | None
) -> None:
    """(property) The yolk clears only on the exact positive shape — every other tri-bool denies."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(
                excluded=excluded,
                approved_exclusion_proof_present=proof,
                closure_1_to_12_complete=closure,
            ),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        )
    )
    expected = excluded is False and closure is True
    assert _judge(manifest) is expected


@given(order=st.permutations([0, 1, 2]))
def test_item_order_does_not_change_the_verdict(order: list[int]) -> None:
    """(§4.4 reconcile) The judgement is order-independent — never first-entry."""
    items = [
        clean_coverage_item(),
        clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        clean_coverage_item(
            obligation_ref="obl-excluded",
            excluded=True,
            approved_exclusion_proof_present=True,
        ),
    ]
    manifest = clean_coverage_manifest(coverage_items=tuple(items[i] for i in order))
    assert _judge(manifest) is True


def test_the_transcribed_closure_anchor_is_twelve_items() -> None:
    """(§7.2 drift) The §9 line 275-286 closure is exactly twelve items (過 0 · 不 0)."""
    assert COVERAGE_CLOSURE_ITEM_COUNT == 12


def test_obligation_ref_none_items_never_count_as_coverage() -> None:
    """(fail-closed) An item with no obligation reference covers nothing."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(obligation_ref=None),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
        ),
        is_complete=None,
    )
    assert (
        critical_coverage_complete_or_gap(
            manifest,
            frozenset({CLEAN_OBLIGATION, CLEAN_ASSUMPTION_OBLIGATION}),
            CLEAN_APPLICABLE_DIMENSIONS,
            CLEAN_SUBMITTED_ASSUMPTION_IDS,
        )
        is False
    )


@pytest.mark.parametrize(
    "criticality", [None, TelemetryCriticality.UNKNOWN_MATERIALITY]
)
def test_undeclared_or_unknown_materiality_can_never_be_excluded(criticality) -> None:
    """(**MAJOR-2 regression**, §8 line 249) An *undeclared* criticality is Critical too.

    "Unknown materiality is Critical" is about the state of knowledge, not about the act of declaring
    it. Admitting ``criticality=None`` would invert the incentive completely: honestly reporting
    ``UNKNOWN_MATERIALITY`` would block the exclusion while simply omitting the field bought one. Both
    deny, and no approved-exclusion proof rescues either.
    """
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(),
            clean_coverage_item(obligation_ref=CLEAN_ASSUMPTION_OBLIGATION),
            clean_coverage_item(
                obligation_ref="obl-excluded",
                excluded=True,
                approved_exclusion_proof_present=True,
                criticality=criticality,
            ),
        )
    )
    assert no_self_exemption(manifest) is False
    assert _judge(manifest) is False


def test_an_undeclared_criticality_is_harmless_when_nothing_is_excluded() -> None:
    """(MAJOR-2, both ways) The gate fires on an *exclusion attempt*, never on the field alone."""
    manifest = clean_coverage_manifest(
        coverage_items=(
            clean_coverage_item(criticality=None),
            clean_coverage_item(
                obligation_ref=CLEAN_ASSUMPTION_OBLIGATION, criticality=None
            ),
        )
    )
    assert no_self_exemption(manifest) is True
    assert _judge(manifest) is True
