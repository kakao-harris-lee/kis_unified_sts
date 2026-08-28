"""Vocabulary exhaustiveness + the mutable-name denylist (design #29 §2.2/§0.5-6/§0.5-8).

Every enum member is enumerated **per member** (the NT #21 lesson: a five-member enum needs five
bindings, not "the ones the happy path reaches"), and the mutable-name helper is exercised
**both ways** — a catalogued sentinel / metacharacter / blank is caught, and a genuine exact digest
is *not* falsely rejected (a denylist that rejects everything is not a working denylist).

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given
from hypothesis import strategies as st


def test_admission_result_has_exactly_three_members() -> None:
    """(§5.7 line 127) ADMIT / DENY / UNKNOWN — the complete member set."""
    assert [member.value for member in sci.AdmissionResult] == [
        "ADMIT",
        "DENY",
        "UNKNOWN",
    ]
    assert len(list(sci.AdmissionResult)) == 3


def test_independence_result_has_exactly_three_members() -> None:
    """(SCI-INV-007 line 179) INDEPENDENT / COMMON_MODE / UNKNOWN."""
    assert [member.value for member in sci.IndependenceResult] == [
        "INDEPENDENT",
        "COMMON_MODE",
        "UNKNOWN",
    ]
    assert len(list(sci.IndependenceResult)) == 3


def test_record_pair_kind_has_exactly_five_members() -> None:
    """(§0.5-6) The reused canonical classifier's five members are all bound."""
    assert {member.name for member in sci.RecordPairKind} == {
        "IDEMPOTENT_DUP",
        "CRITICAL_CONFLICT",
        "DIVERGENT_EMISSION",
        "DISTINCT",
        "NOT_COMPARABLE",
    }
    assert len(list(sci.RecordPairKind)) == 5


@pytest.mark.parametrize("member", list(sci.AdmissionResult))
def test_only_admit_passes_the_positive_identity_gate(
    member: sci.AdmissionResult,
) -> None:
    """(§0.5-4) ADMIT is a positive identity; DENY / UNKNOWN never reach it by fall-through."""
    verdict = sci.software_deployment_ok_verdict(member, True, True, False, True)
    assert verdict is (member is sci.AdmissionResult.ADMIT)


@pytest.mark.parametrize("member", list(sci.IndependenceResult))
def test_only_independent_passes_the_independence_gate(
    member: sci.IndependenceResult,
) -> None:
    """(SCI-INV-007) COMMON_MODE and UNKNOWN are both restrictive."""
    assert sci.independence_unproven_is_common_mode(member) is (
        member is sci.IndependenceResult.INDEPENDENT
    )


def test_absent_results_deny_on_both_enums() -> None:
    """(§5.0) ``None`` denies on both tri-states."""
    assert sci.independence_unproven_is_common_mode(None) is False
    assert sci.software_deployment_ok_verdict(None, True, True, False, True) is False


@pytest.mark.parametrize("sentinel", sorted(sci.MUTABLE_NAME_SENTINELS))
def test_every_catalogued_sentinel_is_detected(sentinel: str) -> None:
    """(SCI-INV-002 line 159) Every catalogued mutable name is caught, in any case / padding."""
    assert sci.is_mutable_name_notation(sentinel) is True
    assert sci.is_mutable_name_notation(sentinel.upper()) is True
    assert sci.is_mutable_name_notation(sentinel.capitalize()) is True
    assert sci.is_mutable_name_notation(f"  {sentinel} ") is True


@pytest.mark.parametrize("metacharacter", sorted(sci.MUTABLE_NAME_METACHARACTERS))
def test_every_metacharacter_is_detected(metacharacter: str) -> None:
    """(§1 line 19) A tag / path / registry / glob metacharacter is never exact identity."""
    assert sci.is_mutable_name_notation(f"artifact{metacharacter}v1") is True


def test_blank_is_not_an_identity_but_absent_is_not_a_mutable_name() -> None:
    """(§2.2) Whitespace-only is a mutable name; ``None`` is *absent*, a separate case."""
    assert sci.is_mutable_name_notation("") is True
    assert sci.is_mutable_name_notation("   ") is True
    assert sci.is_mutable_name_notation(None) is False


@given(
    digest=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), max_codepoint=122),
        min_size=8,
        max_size=32,
    )
)
def test_exact_digests_are_not_falsely_rejected(digest: str) -> None:
    """(both-ways) A metacharacter-free non-sentinel token is accepted — the denylist works."""
    if digest.strip().casefold() in {
        s.strip().casefold() for s in sci.MUTABLE_NAME_SENTINELS
    }:
        return
    assert sci.is_mutable_name_notation(digest) is False
    assert sci.mutable_name_is_not_identity(digest) is True


def test_template_placeholder_is_not_an_identity() -> None:
    """(§4 §3.2) The reserved ``"TBD"`` placeholder is absent, never a concrete identity.

    It is deliberately **not** a mutable-name *notation* (it carries no metacharacter and is not a
    catalogued sentinel) — the placeholder rejection lives in
    :func:`~tos.sci.predicates.mutable_name_is_not_identity`, which is the gate the predicates use.
    """
    assert sci.is_mutable_name_notation("TBD") is False
    assert sci.mutable_name_is_not_identity("TBD") is False
    assert sci.mutable_name_is_not_identity(None) is False


#: Case and padding variants of the reserved placeholder. An exact ``== "TBD"`` comparison accepts
#: every one of them as a concrete identity — the same defect class the mutable-name denylist
#: normalizes away (design #29 §0.5-8 / the RLP #25 ``"All"`` lesson).
PLACEHOLDER_VARIANTS = ("TBD", "tbd", " TBD ", "Tbd", "TBD  ", "\ttbd\n", "tBd")


@pytest.mark.parametrize("variant", PLACEHOLDER_VARIANTS)
def test_placeholder_variants_are_never_a_concrete_identity(variant: str) -> None:
    """(CRITICAL-1) ``"tbd"`` / ``" TBD "`` / ``"Tbd"`` are the placeholder, not an identity.

    Without the ``strip().casefold()`` normalization a producer emitting a lower-cased placeholder
    would satisfy every mandated-binding check at once — the three §2.3 coexistence seals and the
    yolk predicates that mirror them would all pass on a record whose bindings are entirely unset.
    """
    assert sci.mutable_name_is_not_identity(variant) is False


@pytest.mark.parametrize("variant", PLACEHOLDER_VARIANTS)
def test_placeholder_variants_are_rejected_by_the_model_layer(variant: str) -> None:
    """(CRITICAL-1 / §2.3) The model-layer seal normalizes identically — two layers, one rule.

    Two layers that normalize a placeholder differently collapse into one layer; this asserts the
    construction-time seal rejects exactly what the predicate layer rejects.
    """
    from tos.sci.records import _binding_absent

    assert _binding_absent(variant) is True


def test_placeholder_normalization_does_not_reject_lookalikes() -> None:
    """(both-ways) Only the placeholder itself is rejected — ``"tbd-1"`` stays a usable identity."""
    for lookalike in ("tbd-1", "TBDX", "a-tbd", "tb d"):
        assert sci.mutable_name_is_not_identity(lookalike) is True


def test_denylist_honesty_is_documented() -> None:
    """(§0.5-8 / RLP #25) The non-exhaustiveness is stated, not implied."""
    doc = sci.is_mutable_name_notation.__doc__ or ""
    assert "non-exhaustive" in doc
    assert "+Security" in doc


def test_unknown_restriction_state_token_is_the_template_value() -> None:
    """(§5.0) The denied restriction-state sentinel is the template's ``UNKNOWN``, not invented."""
    assert sci.UNKNOWN_RESTRICTION_STATE == "UNKNOWN"


def test_adr_transcription_anchor_counts() -> None:
    """(§6.2 / §4) The §4 verbatim transcription counts are locked to the ADR."""
    assert len(sci.SCI_INVARIANT_TITLES) == 16
    assert len(sci.AUTHORITY_OWNERSHIP_ACTIONS) == 17
    assert len(sci.SOFTWARE_RELEASE_POLICY_FIELD_GROUPS) == 9
    assert len(sci.ADMISSION_PROTOCOL_STEPS) == 10
    assert len(sci.ACTIVE_CURRENTNESS_ITEMS) == 8
    assert len(sci.PARTITION_FAILURE_MODES) == 12
    assert len(sci.SCI_ACCEPTANCE_CASE_TITLES) == 12
    assert len(sci.APPROVAL_GATE_ITEMS) == 14


def test_adr_transcription_anchors_have_no_duplicates() -> None:
    """(§6.2) A duplicated entry would hide a dropped row behind a correct count."""
    for anchor in (
        sci.SCI_INVARIANT_TITLES,
        sci.AUTHORITY_OWNERSHIP_ACTIONS,
        sci.SOFTWARE_RELEASE_POLICY_FIELD_GROUPS,
        sci.ADMISSION_PROTOCOL_STEPS,
        sci.ACTIVE_CURRENTNESS_ITEMS,
        sci.PARTITION_FAILURE_MODES,
        sci.SCI_ACCEPTANCE_CASE_TITLES,
        sci.APPROVAL_GATE_ITEMS,
    ):
        assert len(set(anchor)) == len(anchor)
