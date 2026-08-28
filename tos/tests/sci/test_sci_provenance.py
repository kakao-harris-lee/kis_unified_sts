"""Yolk 2 — ``provenance_is_not_admission`` both-ways canaries (§10/§12/SCI-INV-004; design #29 §5.2).

The load-bearing clause is the structural one: a build provenance attestation that could itself
prove semantic correctness or create artifact admission would collapse §15 step 4 into step 8, so
both authority flags are read and both are individually fatal.

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — SCI-EV-002 is
``EV-L1/2/3+Security``; hermetic build, independent reproduction, and common-mode analysis are
+L2 / +Security.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given

from ._sci_strategies import TRIBOOL, clean_provenance


def test_clean_attestation_passes() -> None:
    """(both-ways) The genuinely complete fixture passes."""
    assert sci.provenance_is_not_admission(clean_provenance()) is True


def test_absent_attestation_denies() -> None:
    """(§5.2 item 1 ∅-seal) A ``None`` attestation denies."""
    assert sci.provenance_is_not_admission(None) is False


@pytest.mark.parametrize(
    "field",
    [
        "builder_identity_current",
        "all_inputs_declared",
        "reproducibility_requirement_satisfied",
        "provenance_complete",
    ],
)
@given(flag=TRIBOOL)
def test_positive_polarity_fields(field: str, flag: bool | None) -> None:
    """(§5.2 items 2-4) Every positive-polarity claim clears only on an explicit ``True``."""
    attestation = clean_provenance(**{field: flag})
    assert sci.provenance_is_not_admission(attestation) is (flag is True)


@given(flag=TRIBOOL)
def test_favorable_output_selection_is_negative_polarity(flag: bool | None) -> None:
    """(§12 line 299) "the release process cannot select the favorable artifact" — ``is False`` only."""
    attestation = clean_provenance(favorable_output_selection_permitted=flag)
    assert sci.provenance_is_not_admission(attestation) is (flag is False)


def test_provenance_cannot_prove_semantic_correctness() -> None:
    """(SCI-INV-004 line 167) A ``proves_semantic_correctness`` claim is fatal.

    The flag cannot be set through the normal path (the authority block rejects it), so the check
    is exercised through the validator-skipping copy — which is exactly the second layer §2.3 asks
    for.
    """
    smuggled = clean_provenance().model_copy(
        update={
            "authority": sci.AllFalseSupplyChainAuthority.model_construct(
                proves_semantic_correctness=True
            )
        }
    )
    assert sci.provenance_is_not_admission(smuggled) is False


def test_provenance_cannot_create_artifact_admission() -> None:
    """(§2.4 M2) Without reading ``creates_artifact_admission`` the SCI-INV-004 argument is vacuous."""
    smuggled = clean_provenance().model_copy(
        update={
            "authority": sci.AllFalseSupplyChainAuthority.model_construct(
                creates_artifact_admission=True
            )
        }
    )
    assert sci.provenance_is_not_admission(smuggled) is False


def test_absent_authority_block_denies() -> None:
    """(§5.2 item 4) A missing authority block is not proof of harmlessness."""
    smuggled = clean_provenance().model_copy(update={"authority": None})
    assert sci.provenance_is_not_admission(smuggled) is False


def test_provenance_result_is_opaque_not_an_admission_result() -> None:
    """(§2.2 MINOR-2 / §7 line 232) "attestation is a fact, not permission".

    The template ``result`` field is typed ``str | None``, never ``AdmissionResult``: a provenance
    attestation must not be able to carry an ``ADMIT``.
    """
    annotation = sci.BuildProvenanceAttestation.model_fields["result"].annotation
    assert annotation == (str | None)
    assert sci.RuntimeArtifactAttestation.model_fields["result"].annotation == (
        str | None
    )
    # ...while the two admission-carrying artifacts *are* AdmissionResult-typed.
    assert sci.ArtifactAdmissionDecision.model_fields["result"].annotation == (
        sci.AdmissionResult | None
    )
    assert sci.AdmittedReleaseSet.model_fields["result"].annotation == (
        sci.AdmissionResult | None
    )


def test_a_valid_provenance_alone_does_not_admit() -> None:
    """(SCI-INV-004) The clean attestation passes §5.2 yet supplies no admission verdict.

    ``provenance_is_not_admission`` returning ``True`` is a *necessary input* to §15 step 4 — it is
    not, and cannot become, an ``ADMIT``: the admission verdict is
    :func:`~tos.sci.predicates.admission_admits_only_positive`'s alone, and it reads a decision
    record, never an attestation.
    """
    attestation = clean_provenance()
    assert sci.provenance_is_not_admission(attestation) is True
    assert not hasattr(attestation, "result_is_admission")
    assert sci.supply_chain_artifact_not_authority(attestation.authority) is True
