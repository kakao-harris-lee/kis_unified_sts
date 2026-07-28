"""Yolk 4 — ``admission_admits_only_positive`` both-ways canaries (§15; design #29 §5.4).

Eleven clauses, each fired individually. The C1 clauses are the sharp ones: the four §15 step 5-6
digest bindings (signature / custody / compatibility / scan) must be *consumed*, the §15 step 7
restriction floor must be compared with ``Ordering.AMBIGUOUS`` denying, and ``ADMIT`` must be a
positive identity rather than "not DENY".

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — SCI-EV-006 is
``EV-L1/3+Security``; common-mode review and self-approval resistance are +Security.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given

from ._sci_strategies import (
    ACTIVE_RESTRICTION_FLOOR,
    CANDIDATE_GENERATION,
    PREDECESSOR_GENERATION,
    TRIBOOL,
    admit_args,
    clean_decision,
    clean_release_artifact_manifest,
    clean_scope,
)

_SCALAR_BINDINGS = sorted(sci.AdmissionBindingSet.model_fields)


def test_clean_admission_passes() -> None:
    """(both-ways) A genuine, fully bound ``ADMIT`` passes."""
    assert sci.admission_admits_only_positive(**admit_args()) is True


def test_absent_decision_denies() -> None:
    """(§5.4 item 1 ∅-seal) A ``None`` decision denies."""
    assert sci.admission_admits_only_positive(**admit_args(decision=None)) is False


@pytest.mark.parametrize(
    "gate", ["restriction_floor_resolved", "scope_resolved", "manifest_resolved"]
)
@given(flag=TRIBOOL)
def test_unresolved_lookups_deny(gate: str, flag: bool | None) -> None:
    """(§5.4 item 1) Each resolution gate is positive polarity — a failed lookup denies."""
    assert sci.admission_admits_only_positive(**admit_args(**{gate: flag})) is (
        flag is True
    )


@pytest.mark.parametrize("result", [*list(sci.AdmissionResult), None])
def test_admit_is_a_positive_identity(result: sci.AdmissionResult | None) -> None:
    """(§5.4 item 2 / AFG C1) Only ``ADMIT`` passes; ``DENY``/``UNKNOWN``/absent never fall through.

    The decision is built with the same complete bindings in every case, so the *only* difference
    is the result token — a "not DENY" implementation would let ``UNKNOWN`` and ``None`` through.
    """
    decision = clean_decision(result=result)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is (
        result is sci.AdmissionResult.ADMIT
    )


@pytest.mark.parametrize("binding", _SCALAR_BINDINGS)
@pytest.mark.parametrize("bad", [None, "TBD", "latest", "registry/image:tag"])
def test_every_scalar_binding_is_individually_load_bearing(
    binding: str, bad: str | None
) -> None:
    """(§5.4 item 3 / C1) Each of the nine §15 step 1-6 digest bindings denies on its own.

    The four C1 bindings (``artifact_signature_and_key_status_digest``,
    ``registry_custody_proof_digest``, ``compatibility_graph_digest``,
    ``scan_test_and_finding_evidence_digest``) are included: an earlier draft carried invented
    ``*_verified`` booleans and never read these digests at all.
    """
    decision = clean_decision(result=sci.AdmissionResult.DENY, **{binding: bad})
    decision = decision.model_copy(update={"result": sci.AdmissionResult.ADMIT})
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


def test_scalar_binding_anchor_is_nine() -> None:
    """(§4.4) The §15 step 1-7 scalar binding anchor has exactly nine members."""
    assert len(_SCALAR_BINDINGS) == 9
    assert set(_SCALAR_BINDINGS) <= set(sci.ArtifactAdmissionDecision.model_fields)


@pytest.mark.parametrize(
    "path",
    [
        ("policy_binding", "software_release_policy_id"),
        ("release_artifact_binding", "release_artifact_manifest_id"),
        ("release_artifact_binding", "release_artifact_manifest_digest"),
    ],
)
def test_structured_bindings_are_load_bearing(path: tuple[str, str]) -> None:
    """(§5.4 item 3) The two structured bindings are consumed field-by-field."""
    block_name, field = path
    clean = clean_decision()
    block = getattr(clean, block_name)
    blanked = type(block)(**{**block.model_dump(), field: None})
    decision = clean.model_copy(update={block_name: blanked})
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


def test_absent_structured_binding_denies() -> None:
    """(§5.4 item 3) A missing binding block denies rather than raising."""
    for block_name in ("policy_binding", "release_artifact_binding"):
        decision = clean_decision().model_copy(update={block_name: None})
        assert (
            sci.admission_admits_only_positive(**admit_args(decision=decision)) is False
        )


# --- item 4: the §15 step 7 restriction floor -------------------------------------------------


def test_equal_floor_is_admissible() -> None:
    """(§5.4 item 4 / §6.3 (i)) An equal floor is at-or-ahead — the decision saw the current fact."""
    assert (
        sci.admission_admits_only_positive(
            **admit_args(active_restriction_floor=ACTIVE_RESTRICTION_FLOOR)
        )
        is True
    )


def test_floor_ahead_of_the_active_one_is_admissible() -> None:
    """(§5.4 item 4) A decision that observed a *newer* floor is at-or-ahead."""
    decision = clean_decision(
        current_release_restriction_floor=ACTIVE_RESTRICTION_FLOOR + 1
    )
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is True


def test_floor_behind_the_active_one_denies() -> None:
    """(§5.4 item 4 / §16 line 348) A decision behind the active floor has not seen the newest fact."""
    decision = clean_decision(
        current_release_restriction_floor=ACTIVE_RESTRICTION_FLOOR - 1
    )
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


def test_absent_floor_on_either_side_denies() -> None:
    """(§5.4 item 4) An absent floor is unknown ordering — denial."""
    decision = clean_decision(
        result=sci.AdmissionResult.DENY, current_release_restriction_floor=None
    ).model_copy(update={"result": sci.AdmissionResult.ADMIT})
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False
    assert (
        sci.admission_admits_only_positive(**admit_args(active_restriction_floor=None))
        is False
    )


# --- items 5-11 -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verdict",
    [sci.IndependenceResult.COMMON_MODE, sci.IndependenceResult.UNKNOWN, None],
)
def test_unproven_independence_denies(verdict: sci.IndependenceResult | None) -> None:
    """(§5.4 item 5 / §15 step 2) Only a positive ``INDEPENDENT`` passes."""
    decision = clean_decision(effective_principal_independence_result=verdict)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


@given(flag=TRIBOOL)
def test_scope_complete_is_positive_polarity(flag: bool | None) -> None:
    """(§5.4 item 6 / SCI-INV-006 line 175) Incomplete or unknown scope denies."""
    scope = clean_scope(scope_complete=flag)
    assert sci.admission_admits_only_positive(**admit_args(target_scope=scope)) is (
        flag is True
    )


def test_absent_scope_denies() -> None:
    """(§5.4 item 6 / NEW-2) The injected scope is reachable and load-bearing."""
    assert sci.admission_admits_only_positive(**admit_args(target_scope=None)) is False


@pytest.mark.parametrize(
    "field",
    [
        "decision_patch_permitted",
        "decision_union_permitted",
        "scope_widening_permitted",
        "automatic_readmission_permitted",
    ],
)
@given(flag=TRIBOOL)
def test_permission_flags_are_negative_polarity(field: str, flag: bool | None) -> None:
    """(§5.4 item 7 / §15 line 338) Patch / union / widen / readmit clear only on ``is False``."""
    decision = clean_decision(**{field: flag})
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is (
        flag is False
    )


def test_equal_generation_is_a_reuse_and_denies() -> None:
    """(§5.4 item 8 / §5.8 line 131) A candidate that reuses the predecessor generation denies."""
    decision = clean_decision(
        result=sci.AdmissionResult.DENY,
        candidate_release_generation=PREDECESSOR_GENERATION,
    ).model_copy(update={"result": sci.AdmissionResult.ADMIT})
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


def test_regressing_generation_denies() -> None:
    """(§5.4 item 8) A candidate behind its predecessor denies."""
    decision = clean_decision(candidate_release_generation=PREDECESSOR_GENERATION - 1)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


def test_advancing_generation_passes() -> None:
    """(both-ways) A strictly advancing candidate passes."""
    decision = clean_decision(candidate_release_generation=CANDIDATE_GENERATION + 5)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is True


@pytest.mark.parametrize("bad", [None, "TBD"])
def test_absent_predecessor_set_digest_denies(bad: str | None) -> None:
    """(§5.4 item 8 / §16) The predecessor Admitted Release Set digest is load-bearing."""
    decision = clean_decision(predecessor_admitted_release_set_digest=bad)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is False


@given(flag=TRIBOOL)
def test_consumed_is_negative_polarity(flag: bool | None) -> None:
    """(§5.4 item 9 / §15 step 10) A consumed — or unknown — single-use decision cannot admit."""
    decision = clean_decision(consumed=flag)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is (
        flag is False
    )


@given(flag=TRIBOOL)
def test_decision_current_is_positive_polarity(flag: bool | None) -> None:
    """(§5.4 item 10) A non-current decision is not an admission basis."""
    decision = clean_decision(current=flag)
    assert sci.admission_admits_only_positive(**admit_args(decision=decision)) is (
        flag is True
    )


@pytest.mark.parametrize(
    "field",
    [
        "mutable_tag_is_identity",
        "lineage_complete",
        "registry_custody_current",
        "compatibility_complete",
    ],
)
@given(flag=TRIBOOL)
def test_item_11_release_artifact_identity_is_wired(
    field: str, flag: bool | None
) -> None:
    """(§5.4 item 11 / MINOR-1) The supporting predicate is genuinely consumed, not dangling."""
    manifest = clean_release_artifact_manifest(**{field: flag})
    negative_polarity = field == "mutable_tag_is_identity"
    expected = (flag is False) if negative_polarity else (flag is True)
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=manifest)
        )
        is expected
    )


def test_absent_manifest_denies() -> None:
    """(§5.4 item 11) A missing release-artifact manifest denies."""
    assert (
        sci.admission_admits_only_positive(**admit_args(release_artifact_manifest=None))
        is False
    )


def test_compatibility_verdict_is_not_double_judged_here() -> None:
    """(§5.4 NEW-4d) This predicate binds the compatibility digest; §5.5 judges the verdict.

    The decision's ``compatibility_graph_digest`` is a *binding*: it is checked for presence only.
    The ``compatibility_complete`` **verdict** on the admitted release set is
    :func:`~tos.sci.predicates.admitted_set_no_permissive_union`'s clause, never duplicated here.
    """
    assert "compatibility_graph_digest" in sci.AdmissionBindingSet.model_fields
    assert "compatibility_complete" not in sci.ArtifactAdmissionDecision.model_fields
    assert "compatibility_complete" in sci.AdmittedReleaseSet.model_fields


# --- MAJOR-1: item 11 must be coupled to the decision's binding, not merely well-formed ---------


def test_a_different_clean_manifest_cannot_satisfy_item_11() -> None:
    """(§5.4 item 11 / §5.7 line 127) Cross-decision manifest substitution denies.

    Before the coupling gate, *any* well-formed manifest satisfied item 11: an attacker (or a
    careless caller) could pair a decision that binds ``ram-1`` with an unrelated, perfectly clean
    ``ram-999`` and admit. §5.7 line 127 issues a decision "for **one exact** Release Artifact
    Manifest", and §14 line 317 is explicit that mirrors, replicas, and restores "cannot make
    unavailable or historical bytes current" — so the injected manifest must be *the* bound one.
    """
    other = clean_release_artifact_manifest(manifest_id="ram-999")
    assert (
        sci.release_artifact_identity_exact(other) is True
    )  # it is genuinely well-formed
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=other)
        )
        is False
    )


def test_matching_manifest_id_still_passes() -> None:
    """(both-ways) The coupling denies substitution without denying the legitimate pairing."""
    bound = clean_release_artifact_manifest(manifest_id="ram-1")
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=bound)
        )
        is True
    )


def test_absent_manifest_id_denies() -> None:
    """(§5.4 item 11) A manifest with no id cannot be proven to be the bound one."""
    anonymous = clean_release_artifact_manifest(manifest_id=None)
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=anonymous)
        )
        is False
    )


def test_issued_manifest_digest_must_match_the_binding() -> None:
    """(§5.4 item 11) When the manifest carries a digest it must equal the bound digest.

    A pre-issuance (``DRAFT``) manifest carries ``canonical_digest is None`` and is exempt; an
    issued one whose digest disagrees with ``release_artifact_binding.release_artifact_manifest_digest``
    is a substitution and denies.
    """
    mismatched = clean_release_artifact_manifest().model_copy(
        update={"canonical_digest": "d-some-other-digest"}
    )
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=mismatched)
        )
        is False
    )
    matching = clean_release_artifact_manifest().model_copy(
        update={"canonical_digest": "d-release-artifact-manifest"}
    )
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=matching)
        )
        is True
    )


def test_require_manifest_digest_match_is_an_opt_in_strengthening() -> None:
    """(§5.4 item 11 / PTF #24 kwargs precedent) The opt-in demands a concrete digest.

    Default ``False`` keeps a pre-issuance manifest admissible (backward compatible); ``True``
    additionally requires the digest to be present and non-placeholder.
    """
    draft = clean_release_artifact_manifest()
    assert draft.canonical_digest is None
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=draft)
        )
        is True
    )
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=draft),
            require_manifest_digest_match=True,
        )
        is False
    )
    issued = draft.model_copy(
        update={"canonical_digest": "d-release-artifact-manifest"}
    )
    assert (
        sci.admission_admits_only_positive(
            **admit_args(release_artifact_manifest=issued),
            require_manifest_digest_match=True,
        )
        is True
    )


def test_target_scope_coupling_is_explicitly_deferred() -> None:
    """(§5.4 item 6) The scope object cannot be tied to ``target_scope_digest`` at L1 — stated.

    :class:`~tos.sci.state.SupplyChainScope` is a value model with no digest field, so unlike the
    manifest there is nothing to compare the decision's ``target_scope_digest`` against. The
    deferral is documented rather than faked; asserting it here keeps the gap visible if a digest
    field is ever added.
    """
    assert "canonical_digest" not in sci.SupplyChainScope.model_fields
    doc = sci.admission_admits_only_positive.__doc__ or ""
    assert "not** coupled to" in doc
    assert "Phase-0 / +Security responsibility" in doc
