"""Polarity exhaustive regression — ``None`` ⇒ deny convergence + the ``is not True`` absence grep
(design #29 §5.0 / §0.5-5; the #18/#22/#23/#25 MAJOR-2 fail-open lesson).

The defect class: a ``bool | None`` field read with the *other* polarity's normalization fails open
on ``None``. A **negative**-polarity field (``consumed``, ``*_permitted``, ``history_rewrite_
detected``, ``mutable_tag_is_identity``, ``restriction_present``, ``revival_claimed``,
``supplies_*``) is cleared **only** by an explicit ``is False``; reading it as ``is not True`` would
read an unknown as "not consumed" / "not permitted" / "not restricted". A **positive**-polarity
field is cleared only by ``is True``.

This suite does two things a per-predicate test cannot: it converges **every** negative-polarity
field's ``None`` to deny across the whole surface, and it **greps the shipped source** so the
forbidden normalization cannot reappear in a future edit.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tos.sci as sci
from hypothesis import given

from ._sci_strategies import (
    CREDIBLE_SCOPE_DIMENSIONS,
    TRIBOOL,
    admit_args,
    admitted_set_args,
    clean_closure_manifest,
    clean_decision,
    clean_provenance,
    clean_release_artifact_manifest,
    clean_release_set,
    clean_restriction,
    clean_scope,
    clean_source_manifest,
)

_PREDICATES_SRC = (
    Path(__file__).resolve().parents[2] / "src" / "tos" / "sci" / "predicates.py"
)
_STATE_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "sci" / "state.py"

#: Every negative-polarity coordinate the §5 predicates consume (design #29 §5.0 table).
_NEGATIVE_POLARITY = (
    "history_rewrite_detected",
    "favorable_output_selection_permitted",
    "floating_version_permitted",
    "undeclared_network_resolution_permitted",
    "runtime_dynamic_resolution_permitted",
    "mutable_tag_is_identity",
    "consumed",
    "decision_patch_permitted",
    "decision_union_permitted",
    "scope_widening_permitted",
    "automatic_readmission_permitted",
    "partial_set_permitted",
    "set_union_permitted",
    "favorable_subset_permitted",
    "historical_generation_reuse_permitted",
    "restriction_present",
    "revival_claimed",
    "supplies_capacity",
    "supplies_authority",
    "supplies_protection",
    "supplies_approval",
    "supplies_admissibility",
    "supplies_permission",
)

#: Every positive-polarity coordinate the §5 predicates consume.
_POSITIVE_POLARITY = (
    "closure_complete",
    "review_current",
    "transitive_closure_complete",
    "all_content_digests_verified",
    "all_sources_approved",
    "all_corrections_and_revocations_current",
    "all_inputs_declared",
    "builder_identity_current",
    "reproducibility_requirement_satisfied",
    "provenance_complete",
    "lineage_complete",
    "registry_custody_current",
    "compatibility_complete",
    "scope_complete",
    "committed",
    "complete",
    "restriction_floor_resolved",
    "scope_resolved",
    "manifest_resolved",
    "applicable_set_resolved",
    "restriction_state_resolved",
    "currentness_current",
    "runtime_attestation_matches",
    "active_currentness_current",
)


def _source() -> str:
    """The shipped predicate + state source, concatenated."""
    return _PREDICATES_SRC.read_text(encoding="utf-8") + _STATE_SRC.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("field", _NEGATIVE_POLARITY)
def test_negative_polarity_field_is_never_read_with_is_not_true(field: str) -> None:
    """(§0.5-5) ``<negative field> is not True`` never appears — it would read ``None`` as clear.

    This is the exact #18 / #22 / #23 / #25 regression: the polarity discipline is only real if the
    forbidden normalization cannot silently reappear.
    """
    pattern = re.compile(rf"\b{re.escape(field)}\s+is\s+not\s+True\b")
    offenders = [
        f"line {index}: {line.strip()}"
        for index, line in enumerate(_source().splitlines(), start=1)
        if pattern.search(line)
    ]
    assert offenders == [], (
        f"negative-polarity field {field!r} is read with `is not True` — a None would be treated "
        f"as clear (design #29 §5.0): {offenders}"
    )


@pytest.mark.parametrize("field", _POSITIVE_POLARITY)
def test_positive_polarity_field_is_never_read_with_is_not_false(field: str) -> None:
    """(§5.0) The mirror rule: a positive-polarity field read as ``is not False`` fails open too."""
    pattern = re.compile(rf"\b{re.escape(field)}\s+is\s+not\s+False\b")
    offenders = [
        f"line {index}: {line.strip()}"
        for index, line in enumerate(_source().splitlines(), start=1)
        if pattern.search(line)
    ]
    assert offenders == [], (
        f"positive-polarity field {field!r} is read with `is not False` (design #29 §5.0): "
        f"{offenders}"
    )


def test_grep_detects_a_planted_polarity_inversion(tmp_path: Path) -> None:
    """(both-ways) The grep catches a planted inversion — green means the check works."""
    planted = tmp_path / "planted.py"
    planted.write_text("x = decision.consumed is not True\n", encoding="utf-8")
    pattern = re.compile(r"\bconsumed\s+is\s+not\s+True\b")
    assert pattern.search(planted.read_text(encoding="utf-8"))


# --- None ⇒ deny convergence across the whole surface -----------------------------------------


@given(flag=TRIBOOL)
def test_source_identity_negative_fields_converge(flag: bool | None) -> None:
    """(§5.1) The source manifest's negative-polarity field admits only on explicit ``False``."""
    manifest = clean_source_manifest(history_rewrite_detected=flag)
    assert sci.source_identity_exact_and_reviewed(manifest) is (flag is False)


@given(flag=TRIBOOL)
def test_provenance_negative_field_converges(flag: bool | None) -> None:
    """(§5.2) ``favorable_output_selection_permitted`` admits only on explicit ``False``."""
    attestation = clean_provenance(favorable_output_selection_permitted=flag)
    assert sci.provenance_is_not_admission(attestation) is (flag is False)


@pytest.mark.parametrize(
    "field",
    [
        "floating_version_permitted",
        "undeclared_network_resolution_permitted",
        "runtime_dynamic_resolution_permitted",
    ],
)
@given(flag=TRIBOOL)
def test_closure_negative_fields_converge(field: str, flag: bool | None) -> None:
    """(§5.3) Every closure policy permission admits only on explicit ``False``."""
    manifest = clean_closure_manifest(**{field: flag})
    assert sci.closure_complete_or_restrictive(manifest) is (flag is False)


@pytest.mark.parametrize(
    "field",
    [
        "consumed",
        "decision_patch_permitted",
        "decision_union_permitted",
        "scope_widening_permitted",
        "automatic_readmission_permitted",
    ],
)
@given(flag=TRIBOOL)
def test_decision_negative_fields_converge(field: str, flag: bool | None) -> None:
    """(§5.4) Every decision negative-polarity field admits only on explicit ``False``."""
    decision = clean_decision(**{field: flag})
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is (
        flag is False
    )


@given(flag=TRIBOOL)
def test_release_artifact_negative_field_converges(flag: bool | None) -> None:
    """(§5.4 item 11 / SCI-INV-002) ``mutable_tag_is_identity`` admits only on explicit ``False``."""
    manifest = clean_release_artifact_manifest(mutable_tag_is_identity=flag)
    assert sci.release_artifact_identity_exact(manifest) is (flag is False)


@pytest.mark.parametrize(
    "field",
    [
        "partial_set_permitted",
        "set_union_permitted",
        "favorable_subset_permitted",
        "historical_generation_reuse_permitted",
    ],
)
@given(flag=TRIBOOL)
def test_release_set_negative_fields_converge(field: str, flag: bool | None) -> None:
    """(§5.5) Every release-set negative-polarity field admits only on explicit ``False``."""
    release_set = clean_release_set(**{field: flag})
    assert sci.admitted_set_no_permissive_union(
        **admitted_set_args(release_set=release_set)
    ) is (flag is False)


@given(flag=TRIBOOL)
def test_restriction_revival_converges(flag: bool | None) -> None:
    """(§5.6c / SCI-INV-016) ``revival_claimed`` admits only on explicit ``False``."""
    assert sci.restriction_is_monotonic_non_revival(
        clean_restriction(), CREDIBLE_SCOPE_DIMENSIONS, True, flag
    ) is (flag is False)


@given(flag=TRIBOOL)
def test_deployment_verdict_restriction_converges(flag: bool | None) -> None:
    """(§5.6e / SCI-INV-014) ``restriction_present`` admits only on explicit ``False``."""
    assert sci.software_deployment_ok_verdict(
        sci.AdmissionResult.ADMIT, True, True, flag, True
    ) is (flag is False)


@given(flag=TRIBOOL)
def test_positive_scope_completeness_converges(flag: bool | None) -> None:
    """(§5.4 item 6) The positive mirror: ``scope_complete`` admits only on explicit ``True``."""
    assert sci.admission_admits_only_positive(
        **admit_args(target_scope=clean_scope(scope_complete=flag))
    ) is (flag is True)


def test_every_predicate_denies_on_an_all_none_call() -> None:
    """(§5.0) With every argument absent, every predicate denies — the total fail-closed floor."""
    assert sci.source_identity_exact_and_reviewed(None) is False
    assert sci.provenance_is_not_admission(None) is False
    assert sci.closure_complete_or_restrictive(None) is False
    assert (
        sci.admission_admits_only_positive(None, None, None, None, None, None, None)
        is False
    )
    assert sci.admitted_set_no_permissive_union(None, None, frozenset(), None) is False
    assert sci.supply_chain_artifact_not_authority(None) is False
    assert sci.release_generation_monotonic(None, None) is False
    assert sci.rollback_is_new_generation(None, None, None) is False
    assert sci.restriction_is_monotonic_non_revival(None, None, None, None) is False
    assert (
        sci.active_currentness_is_negative_gate(
            None, None, None, None, None, None, None
        )
        is False
    )
    assert sci.software_deployment_ok_verdict(None, None, None, None, None) is False
    assert sci.mutable_name_is_not_identity(None) is False
    assert sci.independence_unproven_is_common_mode(None) is False
    assert sci.release_artifact_identity_exact(None) is False
    assert sci.restriction_floor_not_behind(None, None) is False
    assert sci.generation_strictly_advances(None, None) is False
