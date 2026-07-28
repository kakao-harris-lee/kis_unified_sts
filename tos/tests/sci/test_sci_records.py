"""Digest-bound artifact invariants — identity, conflict, coordinate non-collapse, malformed-model
seals (design #29 §2.1/§2.3/§6).

Independent identity (``id != f(digest)``) is what makes a same-id / different-covered-bytes
forgery, re-issue, or replay a detectable ``CRITICAL_CONFLICT`` (§21 line 416); a pre-issuance pair
is ``NOT_COMPARABLE``; a mutable lifecycle coordinate must **not** collapse into the digest (a lawful
transition must not look like a conflict); and the three coexistence seals make a positive claim
with an incomplete binding unconstructable.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from tos.sci import ArtifactIntegrityError, RecordPairKind, classify_record_pair

from ._sci_strategies import (
    SCHEME,
    admit_args,
    clean_closure_manifest,
    clean_decision,
    clean_policy,
    clean_provenance,
    clean_release_artifact_manifest,
    clean_release_set,
    clean_restriction,
    clean_runtime_attestation,
    clean_source_manifest,
)

_ARTIFACTS = (
    (sci.SoftwareReleasePolicy, clean_policy),
    (sci.SourceRevisionManifest, clean_source_manifest),
    (sci.DependencyToolchainClosureManifest, clean_closure_manifest),
    (sci.BuildProvenanceAttestation, clean_provenance),
    (sci.ReleaseArtifactManifest, clean_release_artifact_manifest),
    (sci.ArtifactAdmissionDecision, clean_decision),
    (sci.AdmittedReleaseSet, clean_release_set),
    (sci.RuntimeArtifactAttestation, clean_runtime_attestation),
    (sci.ReleaseRestriction, clean_restriction),
)


def _issue(builder, **overrides):  # type: ignore[no-untyped-def]
    """Issue a clean artifact through the provisional canonicalizer."""
    draft = builder(**overrides)
    content = {
        name: getattr(draft, name)
        for name in type(draft).model_fields
        if name not in {"canonical_digest", "status", "canonicalization_version"}
    }
    return type(draft).issue(scheme=SCHEME, **content)


@pytest.mark.parametrize(
    "model,builder", _ARTIFACTS, ids=lambda x: getattr(x, "__name__", "")
)
def test_issued_artifact_binds_its_digest(model: type, builder: object) -> None:
    """(§4.1) An issued artifact carries a digest equal to ``H(canonicalize(covered))``."""
    issued = _issue(builder)
    assert issued.canonical_digest is not None
    assert issued.status is sci.ArtifactStatus.ISSUED
    assert issued.canonical_digest == SCHEME.compute_digest(issued.covered_content())


@pytest.mark.parametrize(
    "model,builder", _ARTIFACTS, ids=lambda x: getattr(x, "__name__", "")
)
def test_id_is_independent_of_the_digest(model: type, builder: object) -> None:
    """(§0.4c) The id is separately issued — it is not a function of the digest."""
    issued = _issue(builder)
    artifact_id = getattr(issued, model._ID_FIELD)
    assert artifact_id is not None
    assert issued.canonical_digest not in artifact_id
    assert model._ID_FIELD not in model._COVERED_FIELDS


def _classify(left: object, right: object, id_field: str) -> RecordPairKind:
    """Classify two artifacts by their independent id and canonical digest."""
    return classify_record_pair(
        getattr(left, id_field),
        left.canonical_digest,  # type: ignore[attr-defined]
        getattr(right, id_field),
        right.canonical_digest,  # type: ignore[attr-defined]
    )


@pytest.mark.parametrize(
    "model,builder", _ARTIFACTS, ids=lambda x: getattr(x, "__name__", "")
)
def test_same_id_different_bytes_is_a_critical_conflict(
    model: type, builder: object
) -> None:
    """(§2.1 / §21 line 416) A forged same-id record with different covered bytes is detected."""
    original = _issue(builder)
    perturbed_field = next(
        name
        for name in sorted(model._COVERED_FIELDS - {"authority"})
        if isinstance(getattr(original, name, None), str)
    )
    forged = _issue(
        builder,
        **{
            model._ID_FIELD: getattr(original, model._ID_FIELD),
            perturbed_field: "d-forged-value",
        },
    )
    assert original.canonical_digest != forged.canonical_digest
    assert (
        _classify(original, forged, model._ID_FIELD) is RecordPairKind.CRITICAL_CONFLICT
    )


@pytest.mark.parametrize(
    "model,builder", _ARTIFACTS, ids=lambda x: getattr(x, "__name__", "")
)
def test_pre_issuance_pair_is_not_comparable(model: type, builder: object) -> None:
    """(§3.1) A DRAFT pair (digest ``None``) is ``NOT_COMPARABLE``, never a false conflict."""
    left = builder()  # type: ignore[operator]
    right = builder()  # type: ignore[operator]
    assert left.canonical_digest is None
    assert _classify(left, right, model._ID_FIELD) is RecordPairKind.NOT_COMPARABLE


@pytest.mark.parametrize(
    "model,builder", _ARTIFACTS, ids=lambda x: getattr(x, "__name__", "")
)
def test_identical_issued_records_are_an_idempotent_duplicate(
    model: type, builder: object
) -> None:
    """(§3.1) A byte-identical re-emission is an idempotent duplicate, not a conflict."""
    original = _issue(builder)
    replay = _issue(builder, **{model._ID_FIELD: getattr(original, model._ID_FIELD)})
    assert _classify(original, replay, model._ID_FIELD) is RecordPairKind.IDEMPOTENT_DUP


@pytest.mark.parametrize(
    "model,builder", _ARTIFACTS, ids=lambda x: getattr(x, "__name__", "")
)
def test_missing_required_covered_blocks_issuance(model: type, builder: object) -> None:
    """(§3.2) Every ``_REQUIRED_COVERED`` path is genuinely load-bearing at issuance."""
    for path in model._REQUIRED_COVERED:
        head = path.split(".")[0]
        if head in {"canonical_digest"}:
            continue  # verified by the base digest check, not by a null override
        with pytest.raises((ArtifactIntegrityError, ValueError)):
            _issue(builder, **{head: None})


def test_decision_lifecycle_coordinates_do_not_collapse_into_the_digest() -> None:
    """(§2.3) Consuming a decision is a lawful transition — it must not change the digest."""
    issued = _issue(clean_decision)
    for coordinate, value in (
        ("consumed", True),
        ("consumption_permitted", False),
        ("current", False),
    ):
        assert coordinate not in sci.ArtifactAdmissionDecision._COVERED_FIELDS
        transitioned = _issue(
            clean_decision,
            **{"decision_id": issued.decision_id, coordinate: value},
        )
        assert transitioned.canonical_digest == issued.canonical_digest
        assert (
            _classify(issued, transitioned, "decision_id")
            is RecordPairKind.IDEMPOTENT_DUP
        )


def test_release_set_injected_coordinates_do_not_collapse_into_the_digest() -> None:
    """(§2.3) The set's ``current`` and injected cur ``restriction_state`` stay outside the digest."""
    issued = _issue(clean_release_set)
    for coordinate, value in (("current", False), ("restriction_state", "RESTRICTED")):
        assert coordinate not in sci.AdmittedReleaseSet._COVERED_FIELDS
        transitioned = _issue(
            clean_release_set,
            **{"release_set_id": issued.release_set_id, coordinate: value},
        )
        assert transitioned.canonical_digest == issued.canonical_digest


def test_runtime_attestation_lifecycle_coordinates_do_not_collapse() -> None:
    """(§2.3) ``current`` / ``invalidated`` are lifecycle coordinates, outside the digest."""
    issued = _issue(clean_runtime_attestation)
    for coordinate, value in (("current", False), ("invalidated", True)):
        assert coordinate not in sci.RuntimeArtifactAttestation._COVERED_FIELDS
        transitioned = _issue(
            clean_runtime_attestation,
            **{"attestation_id": issued.attestation_id, coordinate: value},
        )
        assert transitioned.canonical_digest == issued.canonical_digest


# --- malformed-model coexistence seals (§2.3) ------------------------------------------------


@pytest.mark.parametrize(
    "binding", sorted(sci.ArtifactAdmissionDecision.MANDATED_ADMIT_BINDINGS)
)
def test_admit_with_any_absent_mandated_binding_is_unconstructable(
    binding: str,
) -> None:
    """(§2.3 central seal) An ``ADMIT`` missing any §15 mandated binding cannot exist."""
    head, _, tail = binding.partition(".")
    if tail:
        block = getattr(clean_decision(), head)
        override = {head: type(block)(**{**block.model_dump(), tail: None})}
    else:
        override = {head: None}
    with pytest.raises((ArtifactIntegrityError, ValueError), match="ADMIT"):
        clean_decision(**override)


@pytest.mark.parametrize("bad_value", ["TBD", "latest", "registry/image:tag"])
def test_admit_with_a_placeholder_or_mutable_binding_is_unconstructable(
    bad_value: str,
) -> None:
    """(§2.3 / SCI-INV-002) A ``"TBD"`` or mutable-name binding is as absent as ``None``."""
    with pytest.raises((ArtifactIntegrityError, ValueError), match="ADMIT"):
        clean_decision(source_revision_manifest_digest=bad_value)


@pytest.mark.parametrize(
    "result", [sci.AdmissionResult.DENY, sci.AdmissionResult.UNKNOWN, None]
)
def test_non_admit_decisions_may_carry_incomplete_bindings(
    result: sci.AdmissionResult | None,
) -> None:
    """(both-ways) The seal is scoped to ``ADMIT`` — a DENY/UNKNOWN record stays constructable."""
    decision = clean_decision(result=result, source_revision_manifest_digest=None)
    assert decision.result is result


def test_complete_release_set_without_a_member_digest_is_unconstructable() -> None:
    """(§2.3 / §16 line 346) A "complete" set with no membership digest cannot exist."""
    with pytest.raises((ArtifactIntegrityError, ValueError), match="complete"):
        clean_release_set(release_artifact_manifest_set_digest=None)
    with pytest.raises((ArtifactIntegrityError, ValueError), match="complete"):
        clean_release_set(release_artifact_manifest_set_digest="TBD")


def test_incomplete_release_set_without_a_member_digest_is_constructable() -> None:
    """(both-ways) The seal is scoped to ``complete is True`` — an incomplete set is honest."""
    assert (
        clean_release_set(
            complete=False, release_artifact_manifest_set_digest=None
        ).complete
        is False
    )


def test_independent_source_manifest_without_a_reviewer_set_is_unconstructable() -> (
    None
):
    """(§2.3 / §9 line 267) Independence is credited only over an exact reviewer set."""
    with pytest.raises((ArtifactIntegrityError, ValueError), match="INDEPENDENT"):
        clean_source_manifest(reviewer_effective_principal_set_digest=None)
    with pytest.raises((ArtifactIntegrityError, ValueError), match="INDEPENDENT"):
        clean_source_manifest(reviewer_effective_principal_set_digest="TBD")


@pytest.mark.parametrize(
    "verdict",
    [sci.IndependenceResult.COMMON_MODE, sci.IndependenceResult.UNKNOWN, None],
)
def test_non_independent_source_manifest_without_a_reviewer_set_is_constructable(
    verdict: sci.IndependenceResult | None,
) -> None:
    """(both-ways) The seal is scoped to ``INDEPENDENT``."""
    manifest = clean_source_manifest(
        effective_principal_independence_result=verdict,
        reviewer_effective_principal_set_digest=None,
    )
    assert manifest.effective_principal_independence_result is verdict


def test_validator_bypass_is_caught_by_the_predicate_layer() -> None:
    """(§2.3 two-layer) A validator-skipping ``ADMIT`` with a blank binding still fails §5.4.

    ``model_copy(update=...)`` on a frozen model applies the update **without** re-running the
    validators — the same escape hatch ``model_construct`` opens. The §5 predicate layer re-derives
    binding completeness structurally, so the smuggled record is still denied.
    """
    smuggled = clean_decision().model_copy(
        update={"source_revision_manifest_digest": None}
    )
    assert smuggled.result is sci.AdmissionResult.ADMIT
    assert sci.admission_admits_only_positive(**admit_args(decision=smuggled)) is False


@pytest.mark.parametrize("variant", ["tbd", " TBD ", "Tbd", "TBD  "])
@pytest.mark.parametrize(
    "binding", sorted(sci.ArtifactAdmissionDecision.MANDATED_ADMIT_BINDINGS)
)
def test_admit_with_a_case_variant_placeholder_is_unconstructable(
    binding: str, variant: str
) -> None:
    """(CRITICAL-1 / §2.3) A lower-cased or padded ``"TBD"`` is the placeholder, not a binding.

    With an exact ``== "TBD"`` comparison this passed for every mandated binding at once, so all
    three coexistence seals *and* the yolk predicates that mirror them could be walked through by a
    record whose bindings were entirely unset. Only the string-valued bindings are exercised (the
    two ordering scalars are ``int``-typed and reject a string at validation).
    """
    head, _, tail = binding.partition(".")
    if binding in {
        "predecessor_release_generation",
        "current_release_restriction_floor",
    }:
        return
    if tail:
        block = getattr(clean_decision(), head)
        override = {head: type(block)(**{**block.model_dump(), tail: variant})}
    else:
        override = {head: variant}
    with pytest.raises((ArtifactIntegrityError, ValueError), match="ADMIT"):
        clean_decision(**override)


@pytest.mark.parametrize("variant", ["tbd", " TBD ", "Tbd"])
def test_complete_set_with_a_case_variant_placeholder_is_unconstructable(
    variant: str,
) -> None:
    """(CRITICAL-1 / §2.3) The admitted-set seal normalizes the placeholder identically."""
    with pytest.raises((ArtifactIntegrityError, ValueError), match="complete"):
        clean_release_set(release_artifact_manifest_set_digest=variant)


@pytest.mark.parametrize("variant", ["tbd", " TBD ", "Tbd"])
def test_independent_manifest_with_a_case_variant_placeholder_is_unconstructable(
    variant: str,
) -> None:
    """(CRITICAL-1 / §2.3) The source-manifest seal normalizes the placeholder identically."""
    with pytest.raises((ArtifactIntegrityError, ValueError), match="INDEPENDENT"):
        clean_source_manifest(reviewer_effective_principal_set_digest=variant)
