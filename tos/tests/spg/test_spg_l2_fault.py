"""SPG-EV-002 EV-L2 component-fault suite — the Safety Profile Validator.

**Stage**: EV-L2 (VER-002-001 §5 line 146-148 verbatim — "A component is tested with
controlled failure injection and authoritative state inspection"). Catalog: EV-L2 pilot
design ``docs/plans/2026-07-29-tos-ev-l2-pilot-design.md`` §4, **12 faults**
(``SPG-01/02/03/05/06/08/09/10/11/13/14/15``). One ``@pytest.mark.l2_fault`` test per row.

**Component** (the single component under injection): the Safety Profile Validator —
``tos.spg.predicates.semantic_validation`` + ``profile_within_envelope`` over
``tos.spg.records.GovernedDimensionLimit``. **Authoritative state inspected**: the
component's own ``SemanticValidationResult`` verdict (``valid`` + ``reason_set`` +
``rejected_dimensions``), or the construction-time refusal for the two magnitudes that are
structurally unconstructable — read **structurally**, never self-reported (design §0.5-3).
"before activation" (VER-002-001 line 1549) holds by construction: spg represents, it never
activates (design #12 §4.5).

Unlike STATE-EV-001 this row has **no durable entanglement** — the referent of its Expected
("every unsafe or incomparable semantic mutation is rejected deterministically before
activation") is the validator's verdict, which exists in full at the model layer. This is a
complete EV-L2 for the semantic-validation component (design §2.2), still subject to the
§9 residual gates (VER §2.7 coverage argument, P0-1, independent signature).

**Explicitly out of scope** (design §7, §10): unknown / duplicate / **extension-field**
bypass is ``SPG-EV-003`` (``EV-L1/2+Security``, VER:1553/1555), not this row — so
``SPG-12`` (duplicate) is not in this catalog. ``SPG-04`` (currency) and ``SPG-07``
(overflow / underflow) are §378 **residuals**, not silent omissions: ``GovernedDimensionLimit``
carries no independent ``currency`` field so currency cannot be varied independently, and an
overflow Expected is bound-dependent on the unapproved Verification Profile (P0-1), which
would make it non-falsifiable (design §0.5-4).

**Hardening dependency**: ``SPG-05`` / ``SPG-06`` depend on design §5 **H-1** (the explicit
``allow_inf_nan=False`` pin tos owns on ``FrozenModel``) and ``SPG-08`` on **H-2**
(precision / rounding / boundary comparability + boundary-inclusion-aware comparison).
``SPG-08`` is the seal of a **measured** fail-open: before H-2 both its limbs returned
``valid=True`` with an empty reason set (design §5 C2 / OQ-2).

**Non-duplication** (design §8.3): ``SPG-01/02/03/09/10/11/13/15`` re-frame guards adjacent
EV-L1 nodes already exercise, as fault-schedule rows carrying a **single** mutation on an
otherwise-valid bundle; they are not a second acceptance. ``SPG-05/06/08/14`` are L2-new.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from tos.spg import (
    GovernedDimensionLimit,
    SemanticValidationResult,
    ValidationReason,
)
from tos.spg.predicates import (
    BOUNDARY_EXCLUSIVE,
    BOUNDARY_INCLUSIVE,
    BOUNDARY_TOKENS,
    envelope_not_expanded,
    profile_within_envelope,
    semantic_validation,
)

from ._spg_strategies import (
    envelope_dimension,
    issue_bundle,
    issue_envelope,
    issue_profile,
    over_envelope_profile,
    profile_dimension,
    valid_semantic_inputs,
)

pytestmark = pytest.mark.l2_fault

_EVIDENCE_ID = "SPG-EV-002"
_COMPONENT = (
    "tos.spg.predicates.semantic_validation / profile_within_envelope "
    "(Safety Profile Validator)"
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

_PREDICATES = "tos/src/tos/spg/predicates.py"
_RECORDS = "tos/src/tos/spg/records.py"
_CANONICAL_BASE = "tos/src/tos/canonical/_base.py"

#: fault id -> the **measured** guard sites, each ``(path, line, token-on-that-line)``.
#:
#: design §3 line 163 (v1.2 N3) makes measuring the *real* guard line an implementation
#: obligation. ``token`` is the anti-phantom seal —
#: :func:`test_guard_code_lines_are_measured_not_phantom` re-reads each file and fails if
#: the recorded line no longer carries it.
_GUARD_SITES: dict[str, tuple[tuple[str, int, str], ...]] = {
    "SPG-01": (
        (_PREDICATES, 536, "if getattr(env_gdl, key) != getattr(gdl, key):"),
        (_PREDICATES, 537, "reasons.add(ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH)"),
    ),
    "SPG-02": (
        (_PREDICATES, 536, "if getattr(env_gdl, key) != getattr(gdl, key):"),
        (_PREDICATES, 537, "reasons.add(ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH)"),
    ),
    "SPG-03": (
        (_PREDICATES, 536, "if getattr(env_gdl, key) != getattr(gdl, key):"),
        (_PREDICATES, 537, "reasons.add(ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH)"),
    ),
    "SPG-05": ((_CANONICAL_BASE, 87, "allow_inf_nan=False"),),
    "SPG-06": ((_CANONICAL_BASE, 87, "allow_inf_nan=False"),),
    "SPG-08": (
        (_PREDICATES, 536, "if getattr(env_gdl, key) != getattr(gdl, key):"),
        (_PREDICATES, 200, "return profile_value >= envelope_max"),
    ),
    "SPG-09": ((_PREDICATES, 301, "or _exceeds_envelope_maximum("),),
    "SPG-10": ((_PREDICATES, 293, "if not envelope.declares(dim):"),),
    "SPG-11": ((_PREDICATES, 282, "if profile.value_for(env_dim) is None:"),),
    "SPG-13": (
        (_PREDICATES, 559, "if inputs.cross_field_consistent is not True:"),
        (_PREDICATES, 560, "CROSS_FIELD_CONSTRAINT_VIOLATION"),
    ),
    "SPG-14": (
        (_PREDICATES, 282, "if profile.value_for(env_dim) is None:"),
        (_PREDICATES, 293, "if not envelope.declares(dim):"),
    ),
    "SPG-15": ((_PREDICATES, 300, "or prof_value is None"),),
}

#: The design §4 catalog, in table order. ``SPG-04`` / ``SPG-07`` / ``SPG-12`` are absent
#: by design (residual / residual / SPG-EV-003) and their absence is asserted, not assumed.
_CATALOG: tuple[str, ...] = (
    "SPG-01",
    "SPG-02",
    "SPG-03",
    "SPG-05",
    "SPG-06",
    "SPG-08",
    "SPG-09",
    "SPG-10",
    "SPG-11",
    "SPG-13",
    "SPG-14",
    "SPG-15",
)


def _guard(fault_id: str) -> str:
    """The measured ``path:line`` guard citation(s) for ``fault_id``."""
    return "; ".join(f"{path}:{line}" for path, line, _ in _GUARD_SITES[fault_id])


def _verdict_disposition(result: SemanticValidationResult) -> str:
    """Structural disposition of a validator verdict.

    ``VALID`` for an accepting verdict, otherwise the sorted reason set and the sorted
    rejected dimensions. Derived from the verdict object, so a mutant that keeps rejecting
    but for a *different* reason, or that stops naming the offending dimension, changes the
    observed string and turns the row into a ``DEVIATION``.
    """
    if result.valid:
        return "VALID"
    reasons = ",".join(sorted(reason.value for reason in result.reason_set))
    dims = ",".join(sorted(result.rejected_dimensions))
    return f"REJECTED[{reasons}]{{{dims}}}"


def _construction_disposition(exc: ValidationError) -> str:
    """Structural disposition of a construction-time refusal."""
    parts = sorted(
        f"{err['type']}@{'.'.join(str(part) for part in err['loc'])}"
        for err in exc.errors()
    )
    return f"ValidationError[{','.join(parts)}]"


def _valid_witness_bundle():
    """The otherwise-valid bundle every fault mutates in exactly one place.

    Both-ways canary (design §8.4 (b)): asserted VALID here, so a rejection below is
    attributable to the single injected mutation and is never a vacuous refusal.
    """
    bundle = issue_bundle()
    baseline = semantic_validation(bundle, valid_semantic_inputs())
    assert baseline.valid is True, "the L2 witness bundle must be genuinely valid"
    assert not baseline.reason_set
    return bundle


def _witness_ref(bundle) -> str:
    """A deterministic reference to the otherwise-valid witness."""
    return f"{bundle.bundle_id}@{bundle.canonical_digest}"


# ---------------------------------------------------------------------------
# anti-phantom: the recorded guard lines are measured, not asserted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fault_id", sorted(_GUARD_SITES))
def test_guard_code_lines_are_measured_not_phantom(fault_id: str) -> None:
    """Every ``injection_point`` this suite writes still names the real guard line.

    Anti-phantom drift lock (design §0.5-1): without it, a refactor silently converts the
    whole fault timeline into fabricated provenance.
    """
    for path, line, token in _GUARD_SITES[fault_id]:
        lines = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
        assert 1 <= line <= len(lines), f"{fault_id}: {path}:{line} is past EOF"
        assert token in lines[line - 1], (
            f"{fault_id}: guard citation drifted — {path}:{line} no longer contains "
            f"{token!r} (found {lines[line - 1].strip()!r})"
        )


def test_catalog_is_the_design_section_4_table() -> None:
    """The executed catalog is exactly the design §4 table — 12 faults.

    ``SPG-04`` (currency — no independent field) and ``SPG-07`` (overflow — bound-dependent
    Expected under an unapproved Verification Profile) are §378 residuals; ``SPG-12``
    (duplicate field) belongs to SPG-EV-003. Their absence is a recorded disposition, not
    an omission (design §4 / §0.5-7).
    """
    assert len(_CATALOG) == 12
    assert set(_CATALOG) == set(_GUARD_SITES)
    for deferred in ("SPG-04", "SPG-07", "SPG-12"):
        assert deferred not in _CATALOG


# ---------------------------------------------------------------------------
# SPG-01/02/03 — §11 step 3 comparability metadata (unit / multiplier / sign)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fault_id", "fault_kind", "env_meta", "profile_meta"),
    [
        ("SPG-01", "unit_mismatch", {"unit": "sh"}, {"unit": "lot"}),
        (
            "SPG-02",
            "multiplier_mismatch",
            {"multiplier": "1"},
            {"multiplier": "1000"},
        ),
        ("SPG-03", "sign_mismatch", {"sign": "POSITIVE"}, {"sign": "NEGATIVE"}),
    ],
)
def test_spg_01_02_03_incomparable_unit_metadata_is_rejected(
    l2_fault_timeline,
    fault_id: str,
    fault_kind: str,
    env_meta: dict,
    profile_meta: dict,
) -> None:
    """SPG-01/02/03 — a same-dimension unit / multiplier / sign mismatch.

    Two magnitudes stated in different units, multipliers, or sign conventions are not
    comparable, so no ``value <= max`` comparison between them means anything. The
    validator must say so rather than compare the raw numbers.
    """
    witness = _valid_witness_bundle()
    bundle = issue_bundle(
        envelope=issue_envelope(
            governed_dimensions=(envelope_dimension(**env_meta),),
        ),
        profile=issue_profile(
            governed_dimensions=(profile_dimension(**profile_meta),),
        ),
    )
    result = semantic_validation(bundle, valid_semantic_inputs())
    observed = _verdict_disposition(result)

    l2_fault_timeline.record(
        fault_id=fault_id,
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard(fault_id),
        fault_kind=fault_kind,
        input_witness_ref=_witness_ref(witness),
        expected_disposition="REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}",
        observed_disposition=observed,
    )
    assert observed == "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}"


# ---------------------------------------------------------------------------
# SPG-05 / SPG-06 — non-finite magnitudes (L2-new; §5 H-1 dependent)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fault_id", "fault_kind", "magnitude"),
    [
        ("SPG-05", "nan_magnitude", "NaN"),
        ("SPG-06", "infinity_magnitude", "Infinity"),
    ],
)
def test_spg_05_06_non_finite_magnitude_is_unconstructable(
    l2_fault_timeline, fault_id: str, fault_kind: str, magnitude: str
) -> None:
    """SPG-05/06 — a ``NaN`` / ``Infinity`` governed-dimension magnitude (**L2-new**).

    ADR-002-014 §11 step 3 (line 304) SHALL-validates "NaN, infinity". The disposition is
    *stronger* than a post-hoc reason: the limit is **unconstructable**, so a non-finite
    magnitude never enters an artifact and can never reach a comparison. Design §5 **H-1**
    made that ownership explicit — the ``allow_inf_nan=False`` pin is tos's, so the
    guarantee no longer rests on a third-party default that a future release could flip.
    """
    witness = _valid_witness_bundle()
    with pytest.raises(ValidationError) as caught:
        envelope_dimension(dimension="qty", envelope_max=Decimal(magnitude))

    observed = _construction_disposition(caught.value)
    # both-ways (b): a finite magnitude of the same shape constructs.
    assert envelope_dimension(dimension="qty", envelope_max=Decimal("10")).envelope_max

    l2_fault_timeline.record(
        fault_id=fault_id,
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard(fault_id),
        fault_kind=fault_kind,
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError[finite_number@envelope_max]",
        observed_disposition=observed,
    )
    assert observed == "ValidationError[finite_number@envelope_max]"


# ---------------------------------------------------------------------------
# SPG-08 — precision / rounding / boundary (L2-new; the measured fail-open seal)
# ---------------------------------------------------------------------------


def test_spg_08_precision_rounding_boundary_and_boundary_equality(
    l2_fault_timeline,
) -> None:
    """SPG-08 — precision / rounding / boundary metadata mismatch **and** boundary equality.

    Both limbs of the design §5 **H-2** hardening, and both were **measured fail-opens**
    before it (design §5 C2 / OQ-2 — each returned ``valid=True`` with an empty reason set):

    * **limb A (comparability)** — an envelope stated at ``precision=2`` / ``HALF_UP`` /
      ``INCLUSIVE`` against a profile stated at ``precision=8`` / ``FLOOR`` / ``EXCLUSIVE``.
      The two are not the same quantity even when the raw magnitudes compare, so the
      dimension is incomparable, exactly as for a unit mismatch (ADR §11 step 3 line 304
      "precision, rounding ... boundary inclusion"; SPG-AC-002 line 621).
    * **limb B (boundary equality)** — an envelope whose declared boundary is ``EXCLUSIVE``
      places its own maximum *outside* the permitted set, so ``profile == envelope_max`` is
      already a breach. A boundary-blind ``>`` admitted it.

    Limb B keeps the metadata *agreeing* on both sides, so its rejection is attributable to
    the boundary-aware comparison alone and not to limb A's comparability check.
    """
    witness = _valid_witness_bundle()

    # limb A — incomparable precision / rounding / boundary metadata.
    #
    # Each axis is varied ALONE. Mutating all three at once would be satisfied by a
    # validator that compares only one of them: dropping "rounding" from the compared
    # set would leave the combined case still rejected (on precision) and the fault
    # still MET, so the three-axis form cannot falsify any single axis — measured.
    limb_a_by_axis: dict[str, str] = {}
    for axis, env_meta, prof_meta in (
        ("precision", {"precision": "2"}, {"precision": "8"}),
        ("rounding", {"rounding": "HALF_UP"}, {"rounding": "FLOOR"}),
        ("boundary", {"boundary": "INCLUSIVE"}, {"boundary": "EXCLUSIVE"}),
    ):
        single_axis = issue_bundle(
            envelope=issue_envelope(
                governed_dimensions=(envelope_dimension(**env_meta),),
            ),
            profile=issue_profile(
                governed_dimensions=(profile_dimension(**prof_meta),),
            ),
        )
        limb_a_by_axis[axis] = _verdict_disposition(
            semantic_validation(single_axis, valid_semantic_inputs())
        )
        assert limb_a_by_axis[axis] == "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", (
            f"a {axis}-only mismatch must be rejected on its own — otherwise that axis "
            "is not actually compared"
        )
    limb_a = "+".join(
        f"{axis}={limb_a_by_axis[axis]}" for axis in sorted(limb_a_by_axis)
    )

    # limb B — metadata AGREES (EXCLUSIVE on both sides); the profile sits exactly on the max.
    exclusive_envelope = issue_envelope(
        governed_dimensions=(
            envelope_dimension(envelope_max=Decimal("10"), boundary="EXCLUSIVE"),
        ),
    )
    on_the_boundary = issue_profile(
        governed_dimensions=(
            profile_dimension(profile_value=Decimal("10"), boundary="EXCLUSIVE"),
        ),
    )
    limb_b = _verdict_disposition(
        profile_within_envelope(exclusive_envelope, on_the_boundary)
    )

    # both-ways (b), two directions, so limb B is the boundary SEMANTICS and neither a
    # blanket ban on touching the maximum nor a blanket rejection of EXCLUSIVE:
    #   1. the same equality under INCLUSIVE is admitted;
    #   2. a value strictly BELOW an EXCLUSIVE maximum is admitted.
    # (2) is what makes the EXCLUSIVE token itself load-bearing — without it, a build
    # that no longer recognized "EXCLUSIVE" would reject every EXCLUSIVE dimension and
    # limb B would keep passing for the wrong reason.
    inclusive_envelope = issue_envelope(
        governed_dimensions=(
            envelope_dimension(envelope_max=Decimal("10"), boundary="INCLUSIVE"),
        ),
    )
    at_max_inclusive = issue_profile(
        governed_dimensions=(
            profile_dimension(profile_value=Decimal("10"), boundary="INCLUSIVE"),
        ),
    )
    assert profile_within_envelope(inclusive_envelope, at_max_inclusive).valid is True

    below_exclusive_max = issue_profile(
        governed_dimensions=(
            profile_dimension(profile_value=Decimal("9"), boundary="EXCLUSIVE"),
        ),
    )
    assert (
        profile_within_envelope(exclusive_envelope, below_exclusive_max).valid is True
    )

    observed = f"A={limb_a}|B={limb_b}"
    _rejected_meta = "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}"
    expected = (
        f"A=boundary={_rejected_meta}"
        f"+precision={_rejected_meta}"
        f"+rounding={_rejected_meta}"
        "|B=REJECTED[EXCEEDS_ENVELOPE]{qty}"
    )
    l2_fault_timeline.record(
        fault_id="SPG-08",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-08"),
        fault_kind="precision_rounding_boundary_mismatch+exclusive_boundary_equality",
        input_witness_ref=_witness_ref(witness),
        expected_disposition=expected,
        observed_disposition=observed,
    )
    assert observed == expected


# ---------------------------------------------------------------------------
# SPG-09/10/11/14/15 — envelope dominance faults
# ---------------------------------------------------------------------------


def test_spg_09_over_envelope_value_is_rejected(l2_fault_timeline) -> None:
    """SPG-09 — a profile value strictly above the envelope maximum.

    SPG-INV-001 line 153: no profile "may exceed ... a Hard Safety Envelope constraint".
    """
    witness = _valid_witness_bundle()
    bundle = issue_bundle(profile=over_envelope_profile())
    observed = _verdict_disposition(
        semantic_validation(bundle, valid_semantic_inputs())
    )

    l2_fault_timeline.record(
        fault_id="SPG-09",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-09"),
        fault_kind="over_envelope_value",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="REJECTED[EXCEEDS_ENVELOPE]{qty}",
        observed_disposition=observed,
    )
    assert observed == "REJECTED[EXCEEDS_ENVELOPE]{qty}"


def test_spg_10_undeclared_dimension_is_zero_authority(l2_fault_timeline) -> None:
    """SPG-10 — the profile governs a dimension the envelope never declared.

    An undeclared dimension carries **zero** authority: there is no maximum to be within,
    so it can never be silently admitted (the ∅-seal). The declared dimension in the same
    profile stays clean, so the rejection is attributed to the undeclared one alone.
    """
    witness = _valid_witness_bundle()
    envelope = issue_envelope(
        governed_dimensions=(envelope_dimension(dimension="qty"),),
    )
    profile = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty"),
            profile_dimension(dimension="notional", profile_value=Decimal("1")),
        ),
    )
    observed = _verdict_disposition(profile_within_envelope(envelope, profile))

    l2_fault_timeline.record(
        fault_id="SPG-10",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-10"),
        fault_kind="undeclared_dimension",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="REJECTED[EXCEEDS_ENVELOPE]{notional}",
        observed_disposition=observed,
    )
    assert observed == "REJECTED[EXCEEDS_ENVELOPE]{notional}"


def test_spg_11_omitted_mandatory_dimension_cannot_pass_vacuously(
    l2_fault_timeline,
) -> None:
    """SPG-11 — the profile omits a mandatory (envelope-declared) dimension.

    SPG-INV-001 line 153 forbids a profile that "omits" an envelope constraint: a partial
    profile would otherwise pass dominance vacuously — every dimension it *does* declare is
    within its maximum — while leaving the omitted constraint unenforced.

    This is the §11 **step 6** dominance limb (ADR line 307), not step 12's "omitted
    **fields**" (line 313 / SPG-EV-003): a dropped *dimension* destroys dominance, which is
    the "vector dimension" axis SPG-EV-002's own Injection names (design §4 M5).
    """
    witness = _valid_witness_bundle()
    envelope = issue_envelope(
        governed_dimensions=(
            envelope_dimension(dimension="qty"),
            envelope_dimension(dimension="notional", envelope_max=Decimal("100")),
        ),
    )
    profile = issue_profile(
        governed_dimensions=(profile_dimension(dimension="qty"),),
    )
    observed = _verdict_disposition(profile_within_envelope(envelope, profile))

    l2_fault_timeline.record(
        fault_id="SPG-11",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-11"),
        fault_kind="omitted_mandatory_dimension",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="REJECTED[EXCEEDS_ENVELOPE]{notional}",
        observed_disposition=observed,
    )
    assert observed == "REJECTED[EXCEEDS_ENVELOPE]{notional}"


def test_spg_14_vector_dimension_set_identity_mismatch(l2_fault_timeline) -> None:
    """SPG-14 — same dimension **cardinality**, different dimension **identity** (**L2-new**).

    The sharpest form of the "vector dimension" axis SPG-EV-002's Injection (VER:1548)
    names, and the one a cardinality-only check would miss: the profile declares exactly as
    many dimensions as the envelope, so any comparison keyed on *count* passes, yet the two
    sets share only one member. Both defects are named at once — the envelope dimension the
    profile omitted, **and** the dimension the profile invented — so a validator that
    detected only one direction would produce a different rejected set.
    """
    witness = _valid_witness_bundle()
    envelope = issue_envelope(
        governed_dimensions=(
            envelope_dimension(dimension="qty"),
            envelope_dimension(dimension="notional", envelope_max=Decimal("100")),
        ),
    )
    profile = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty"),
            profile_dimension(dimension="latency", profile_value=Decimal("1")),
        ),
    )
    assert len(envelope.governed_dimensions) == len(profile.governed_dimensions)
    observed = _verdict_disposition(profile_within_envelope(envelope, profile))

    l2_fault_timeline.record(
        fault_id="SPG-14",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-14"),
        fault_kind="vector_dimension_identity_mismatch_equal_cardinality",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="REJECTED[EXCEEDS_ENVELOPE]{latency,notional}",
        observed_disposition=observed,
    )
    assert observed == "REJECTED[EXCEEDS_ENVELOPE]{latency,notional}"


def test_spg_15_none_magnitude_is_not_unbounded(l2_fault_timeline) -> None:
    """SPG-15 — a ``None`` profile magnitude on a declared dimension.

    A missing magnitude is UNKNOWN, never "unbounded". Treating it as unbounded would make
    the cheapest possible mutation — deleting a number — the most permissive one.
    """
    witness = _valid_witness_bundle()
    envelope = issue_envelope(
        governed_dimensions=(envelope_dimension(dimension="qty"),)
    )
    profile = issue_profile(
        governed_dimensions=(
            GovernedDimensionLimit(dimension="qty", profile_value=None, unit="sh"),
        ),
    )
    observed = _verdict_disposition(profile_within_envelope(envelope, profile))

    l2_fault_timeline.record(
        fault_id="SPG-15",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-15"),
        fault_kind="none_magnitude",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="REJECTED[EXCEEDS_ENVELOPE]{qty}",
        observed_disposition=observed,
    )
    assert observed == "REJECTED[EXCEEDS_ENVELOPE]{qty}"


# ---------------------------------------------------------------------------
# SPG-13 — cross-field constraint (injected observation)
# ---------------------------------------------------------------------------


def test_spg_13_cross_field_violation_fails_closed(l2_fault_timeline) -> None:
    """SPG-13 — the §11 step 5 cross-field observation is violated *or* unproven.

    **Limitation, stated in-band** (design §4): the cross-field constraint *set* is a
    Phase-0 instance value, so the observation is **injected** rather than computed here.
    What this fault demonstrates is the validator's disposition of that input, not an
    evaluation of any concrete cross-field rule. Both the negative (``False``) and the
    unproven (``None``) inputs are exercised, because a fail-closed predicate must reject
    "unknown" as firmly as "violated".
    """
    witness = _valid_witness_bundle()
    dispositions = [
        _verdict_disposition(
            semantic_validation(
                witness, valid_semantic_inputs(cross_field_consistent=value)
            )
        )
        for value in (False, None)
    ]
    observed = "|".join(dispositions)
    expected = "|".join(["REJECTED[CROSS_FIELD_CONSTRAINT_VIOLATION]{}"] * 2)

    l2_fault_timeline.record(
        fault_id="SPG-13",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("SPG-13"),
        fault_kind="cross_field_constraint_violated_and_unproven",
        input_witness_ref=_witness_ref(witness),
        expected_disposition=expected,
        observed_disposition=observed,
    )
    assert observed == expected
    assert ValidationReason.CROSS_FIELD_CONSTRAINT_VIOLATION in set(ValidationReason)


# ---------------------------------------------------------------------------
# H-2 hardening seals that are not themselves catalog faults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    ["inclusive", "Inclusive", "INCLUSIVE ", " INCLUSIVE", "", "OPEN", "EXCLUSIV"],
)
def test_an_unreadable_boundary_token_is_never_a_permission(token: str) -> None:
    """An unrecognized boundary declaration fails closed (design #12 §4.1).

    Recognition is **exact** membership in ``BOUNDARY_TOKENS``. Casefolding or stripping
    an unknown token into a known one is how a typo silently becomes a permission: with
    normalization, ``"inclusive"`` would grant the permissive ``>`` arm. Here every token
    outside the closed set leaves containment unproven, so the dimension is rejected even
    though the magnitude is strictly inside the maximum.
    """
    envelope = issue_envelope(
        governed_dimensions=(
            envelope_dimension(envelope_max=Decimal("10"), boundary=token),
        ),
    )
    profile = issue_profile(
        governed_dimensions=(
            profile_dimension(profile_value=Decimal("1"), boundary=token),
        ),
    )
    result = profile_within_envelope(envelope, profile)
    assert result.valid is False
    assert "qty" in result.rejected_dimensions


def test_recognized_boundary_tokens_are_exactly_two() -> None:
    """The closed set is the two ADR §11 step 3 tokens — a drift lock on the vocabulary."""
    assert set(BOUNDARY_TOKENS) == {BOUNDARY_INCLUSIVE, BOUNDARY_EXCLUSIVE}
    assert (BOUNDARY_INCLUSIVE, BOUNDARY_EXCLUSIVE) == ("INCLUSIVE", "EXCLUSIVE")


def test_envelope_expansion_seam_is_boundary_aware() -> None:
    """``envelope_not_expanded`` uses the same boundary test dominance uses.

    This predicate produces the ``envelope_not_expanded`` seam bool that liveauth's
    ``Safe053VariantAttestation`` (``state.py:164``) consumes. A boundary-blind comparison
    here reported "nothing was enlarged" for a profile sitting exactly on an ``EXCLUSIVE``
    maximum — the one value that maximum excludes — so the seam handed ``True`` to the
    re-arm path while ``profile_within_envelope`` was rejecting the very same pair. The
    two must agree; a disagreement between them is the fail-open.
    """
    old_envelope = issue_envelope(
        governed_dimensions=(
            envelope_dimension(envelope_max=Decimal("10"), boundary="EXCLUSIVE"),
        ),
    )
    wider = issue_envelope(
        governed_dimensions=(
            envelope_dimension(envelope_max=Decimal("100"), boundary="EXCLUSIVE"),
        ),
    )
    on_the_boundary = issue_profile(
        governed_dimensions=(
            profile_dimension(profile_value=Decimal("10"), boundary="EXCLUSIVE"),
        ),
    )
    assert envelope_not_expanded(old_envelope, wider, on_the_boundary) is False
    # the two predicates agree on the same pair — no seam-level disagreement
    assert profile_within_envelope(old_envelope, on_the_boundary).valid is False

    # both-ways: a value strictly inside the old EXCLUSIVE maximum enlarges nothing
    inside = issue_profile(
        governed_dimensions=(
            profile_dimension(profile_value=Decimal("9"), boundary="EXCLUSIVE"),
        ),
    )
    assert envelope_not_expanded(old_envelope, wider, inside) is True
    assert profile_within_envelope(old_envelope, inside).valid is True
