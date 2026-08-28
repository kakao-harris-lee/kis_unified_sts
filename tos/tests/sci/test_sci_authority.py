"""All-false supply-chain authority (SCI-INV-001 line 155; design #29 §2.4 M2 / §5.6a).

The twenty declared flags are the **union of the ``authority:`` block of the eight canonical
templates** — asserted against the templates on disk, so an invented flag or a dropped one fails.
Every artifact carries an all-false block, any ``True`` flag makes the artifact unconstructable, and
the §5.6a predicate re-derives the property so a ``model_construct`` bypass is still caught.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tos.sci as sci
from tos.sci import AllFalseSupplyChainAuthority, ArtifactIntegrityError

from ._sci_strategies import (
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

_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[3]
    / "tos-spec"
    / "src"
    / "part-1-foundation"
    / "verification"
)

_TEMPLATES = (
    "SOFTWARE-RELEASE-POLICY",
    "SOURCE-REVISION-MANIFEST",
    "DEPENDENCY-AND-TOOLCHAIN-CLOSURE-MANIFEST",
    "BUILD-PROVENANCE-ATTESTATION",
    "RELEASE-ARTIFACT-MANIFEST",
    "ARTIFACT-ADMISSION-DECISION",
    "ADMITTED-RELEASE-SET",
    "RUNTIME-ARTIFACT-ATTESTATION",
)

_ARTIFACT_BUILDERS = (
    clean_policy,
    clean_source_manifest,
    clean_closure_manifest,
    clean_provenance,
    clean_release_artifact_manifest,
    clean_decision,
    clean_release_set,
    clean_runtime_attestation,
    clean_restriction,
)


def _template_authority_keys(name: str) -> set[str]:
    """The ``authority:`` block keys of one canonical template (read from disk)."""
    text = (_TEMPLATE_DIR / f"{name}-template.yaml").read_text(encoding="utf-8")
    keys: set[str] = set()
    inside = False
    for line in text.splitlines():
        if re.match(r"^authority:\s*$", line):
            inside = True
            continue
        if inside:
            match = re.match(r"^  ([a-z_][a-z0-9_]*):", line)
            if match:
                keys.add(match.group(1))
                continue
            if re.match(r"^[a-z_]", line):
                break
    return keys


def test_declared_flags_are_exactly_twenty() -> None:
    """(§2.4 M2) The union carries exactly twenty flags."""
    assert len(AllFalseSupplyChainAuthority.model_fields) == 20


def test_declared_flags_equal_the_template_union() -> None:
    """(§2.4 M2 / §6.2) No invented flag, no dropped flag — the union is read from the templates."""
    union: set[str] = set()
    for name in _TEMPLATES:
        keys = _template_authority_keys(name)
        assert keys, f"{name} has no authority block on disk"
        union |= keys
    declared = set(AllFalseSupplyChainAuthority.model_fields)
    assert declared == union, (
        "AllFalseSupplyChainAuthority must be exactly the union of the eight templates' "
        f"authority blocks — invented={sorted(declared - union)} "
        f"missing={sorted(union - declared)}"
    )


@pytest.mark.parametrize("template", _TEMPLATES)
def test_each_template_authority_block_is_covered(template: str) -> None:
    """(§6.2) Every per-template authority block is a subset of the declared union."""
    assert _template_authority_keys(template) <= set(
        AllFalseSupplyChainAuthority.model_fields
    )


def test_creates_artifact_admission_is_present() -> None:
    """(§2.4 M2) Without this flag the SCI-INV-004 argument in §5.2 would be vacuous."""
    assert "creates_artifact_admission" in AllFalseSupplyChainAuthority.model_fields
    assert "proves_semantic_correctness" in AllFalseSupplyChainAuthority.model_fields


def test_default_block_is_entirely_false() -> None:
    """(SCI-INV-001) A default block grants nothing."""
    authority = AllFalseSupplyChainAuthority()
    for name in AllFalseSupplyChainAuthority.model_fields:
        assert getattr(authority, name) is False
    assert sci.supply_chain_artifact_not_authority(authority) is True


@pytest.mark.parametrize("flag", sorted(AllFalseSupplyChainAuthority.model_fields))
def test_any_true_flag_is_unconstructable(flag: str) -> None:
    """(SCI-INV-001) Each of the twenty flags individually blocks construction when ``True``."""
    with pytest.raises((ArtifactIntegrityError, ValueError), match="must be false"):
        AllFalseSupplyChainAuthority(**{flag: True})


@pytest.mark.parametrize("builder", _ARTIFACT_BUILDERS)
def test_every_clean_artifact_carries_an_all_false_authority(builder: object) -> None:
    """(§2.4) All nine artifacts carry the all-false block by default."""
    artifact = builder()  # type: ignore[operator]
    assert sci.supply_chain_artifact_not_authority(artifact.authority) is True


@pytest.mark.parametrize("builder", _ARTIFACT_BUILDERS)
def test_an_artifact_with_a_true_authority_flag_is_unconstructable(
    builder: object,
) -> None:
    """(SCI-INV-001) A granting artifact cannot exist — the block rejects at construction."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        builder(  # type: ignore[operator]
            authority=AllFalseSupplyChainAuthority(deploys_software=True)
        )


def test_predicate_denies_an_absent_block() -> None:
    """(§5.6a) ``None`` denies — an absent authority claim is not proof of harmlessness."""
    assert sci.supply_chain_artifact_not_authority(None) is False


@pytest.mark.parametrize("flag", sorted(AllFalseSupplyChainAuthority.model_fields))
def test_predicate_catches_a_model_construct_bypass(flag: str) -> None:
    """(§2.3 two-layer) A validator-skipping ``model_construct`` block is caught by the predicate."""
    smuggled = AllFalseSupplyChainAuthority.model_construct(**{flag: True})
    assert sci.supply_chain_artifact_not_authority(smuggled) is False


def test_predicate_denies_a_none_valued_flag() -> None:
    """(§5.0) A ``None`` flag is not ``False`` — an unknown grant claim denies."""
    smuggled = AllFalseSupplyChainAuthority.model_construct(deploys_software=None)
    assert sci.supply_chain_artifact_not_authority(smuggled) is False
