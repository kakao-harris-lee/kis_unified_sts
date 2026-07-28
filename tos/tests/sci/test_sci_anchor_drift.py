"""§6.2 drift-lock — canonical template ↔ model 1:1, §4 transcription anchors, negative tokens.

The WDR MAJOR-1 defect class: a whole template field group silently absent from the model. This
suite reads the **eight canonical templates from disk** (the single source of truth) and asserts
field-name correspondence in **both** directions, per template and per nested block, so a template
edit or a model edit that diverges fails loudly.

It also locks the §4 verbatim transcription anchors against the ADR text on disk and asserts the
§0.5 anti-phantom **negative tokens** — the failuredomain coordinates, the cur fence names, and the
dsl ``AdmissibilityResult`` — are absent from the sci sources, so a re-authoring cannot creep in
under a different import.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tos.sci as sci

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FOUNDATION_DIR = _REPO_ROOT / "tos-spec" / "src" / "part-1-foundation"
_TEMPLATE_DIR = _FOUNDATION_DIR / "verification"


def _adr_path() -> Path:
    """The ADR-002-029 file, resolved by glob rather than by a transcribed filename.

    The file on disk is mixed-case
    (``ADR-002-029-Software-Supply-Chain-Integrity-...-Governance.md``). Hard-coding a
    lower-cased spelling resolves on a case-insensitive filesystem (macOS default) and **fails on a
    case-sensitive one** (Linux CI) — a latent, environment-dependent break. Globbing the stable
    ``ADR-002-029-*.md`` prefix is immune to both that and to a later rename, and the single-match
    assertion keeps it honest: if the ADR disappears or is duplicated, this fails loudly instead of
    silently skipping every verbatim anchor below.
    """
    matches = sorted(_FOUNDATION_DIR.glob("ADR-002-029-*.md"))
    assert (
        len(matches) == 1
    ), f"expected exactly one ADR-002-029-*.md under {_FOUNDATION_DIR}, found {matches}"
    return matches[0]


_SCI_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "sci"

#: template name -> sci model.
_TEMPLATE_MODELS = {
    "SOFTWARE-RELEASE-POLICY": sci.SoftwareReleasePolicy,
    "SOURCE-REVISION-MANIFEST": sci.SourceRevisionManifest,
    "DEPENDENCY-AND-TOOLCHAIN-CLOSURE-MANIFEST": sci.DependencyToolchainClosureManifest,
    "BUILD-PROVENANCE-ATTESTATION": sci.BuildProvenanceAttestation,
    "RELEASE-ARTIFACT-MANIFEST": sci.ReleaseArtifactManifest,
    "ARTIFACT-ADMISSION-DECISION": sci.ArtifactAdmissionDecision,
    "ADMITTED-RELEASE-SET": sci.AdmittedReleaseSet,
    "RUNTIME-ARTIFACT-ATTESTATION": sci.RuntimeArtifactAttestation,
}

#: Template-side keys deliberately not modelled (design #29 §2.4): ``artifact_type`` and
#: ``schema_version`` are template meta the tos base carries through the model class and
#: ``canonicalization_version``; ``authorization_notice`` is prose restated in the docstrings.
_TEMPLATE_META_KEYS = frozenset(
    {"artifact_type", "schema_version", "authorization_notice"}
)
#: Model-side fields the templates have no key for (the tos digest base's own meta).
_MODEL_BASE_ONLY = frozenset({"canonicalization_version"})

#: Nested block -> the value model it maps to, per template.
_NESTED_MODELS = {
    "scope": sci.SupplyChainScope,
    "policy_binding": sci.PolicyBinding,
    "release_artifact_binding": sci.ReleaseArtifactBinding,
    "source_revision_manifest_binding": sci.SourceRevisionManifestBinding,
    "dependency_and_toolchain_binding": sci.DependencyAndToolchainBinding,
    "build_provenance_binding": sci.BuildProvenanceBinding,
    "release_binding": sci.ReleaseBinding,
    "verification_profile_binding": sci.VerificationProfileBinding,
}


def _template_text(name: str) -> str:
    return (_TEMPLATE_DIR / f"{name}-template.yaml").read_text(encoding="utf-8")


def _top_level_keys(name: str) -> set[str]:
    """The top-level keys of one canonical template."""
    return {
        match.group(1)
        for line in _template_text(name).splitlines()
        if (match := re.match(r"^([a-z_][a-z0-9_]*):", line))
    }


def _nested_blocks(name: str) -> dict[str, list[str]]:
    """The two-space-indented sub-keys of every nested block in one canonical template.

    An **empty** block is kept, not dropped. Filtering ``{block: keys for ... if keys}`` would make
    the worst drift — every sub-key of a block deleted — vanish from the comparison instead of
    failing it, which is the same "silently absent field group" defect (WDR MAJOR-1) this suite
    exists to catch, one level down.
    """
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in _template_text(name).splitlines():
        header = re.match(r"^([a-z_][a-z0-9_]*):\s*$", line)
        if header:
            current = header.group(1)
            blocks[current] = []
            continue
        if re.match(r"^[a-z_]", line):
            current = None
            continue
        sub = re.match(r"^  ([a-z_][a-z0-9_]*):", line)
        if sub and current is not None:
            blocks[current].append(sub.group(1))
    return blocks


def test_all_eight_templates_exist_on_disk() -> None:
    """(anti-phantom) Every template this suite reads actually exists."""
    for name in _TEMPLATE_MODELS:
        assert (_TEMPLATE_DIR / f"{name}-template.yaml").is_file()
    assert len(_TEMPLATE_MODELS) == 8
    assert _adr_path().is_file()


def test_adr_is_resolved_case_exactly_not_by_a_lowercased_guess() -> None:
    """(MAJOR-3) The ADR filename is mixed-case; a lower-cased literal is not a directory entry.

    ``Path(lowercased).exists()`` returns ``True`` on a case-insensitive filesystem (macOS default)
    and ``False`` on a case-sensitive one (Linux CI), so a hard-coded lower-cased spelling is a
    latent environment-dependent break that local runs cannot surface. This asserts the property
    that is **filesystem-independent**: the lower-cased spelling is not among the directory's actual
    entries, therefore only the glob resolution is safe everywhere.
    """
    entries = {path.name for path in _FOUNDATION_DIR.iterdir()}
    actual = _adr_path().name
    assert actual in entries
    assert actual != actual.lower(), "the ADR filename is expected to be mixed-case"
    assert actual.lower() not in entries, (
        "a lower-cased ADR filename is not a real directory entry — resolving the ADR by a "
        "transcribed lower-case literal would fail on a case-sensitive filesystem"
    )


@pytest.mark.parametrize("name", sorted(_TEMPLATE_MODELS))
def test_template_and_model_fields_match_one_to_one(name: str) -> None:
    """(§6.2 / M1) Template keys == model fields, modulo the three documented meta exclusions.

    Both directions matter: a template-only key is a dropped field group (WDR MAJOR-1) and a
    model-only field is an invented one (the phantom-field defect class).
    """
    template_keys = _top_level_keys(name) - _TEMPLATE_META_KEYS
    model_fields = set(_TEMPLATE_MODELS[name].model_fields) - _MODEL_BASE_ONLY
    assert template_keys == model_fields, (
        f"{name} drifted — template-only={sorted(template_keys - model_fields)} "
        f"model-only={sorted(model_fields - template_keys)}"
    )


@pytest.mark.parametrize("name", sorted(_TEMPLATE_MODELS))
def test_nested_blocks_match_their_value_models(name: str) -> None:
    """(§6.2) Every nested template block maps 1:1 onto its value model.

    The one documented variation is the RUNTIME-ARTIFACT-ATTESTATION ``scope:`` block, which
    carries **eight** dimensions (no ``legal_portfolio``) against
    :class:`~tos.sci.state.SupplyChainScope`'s nine (design #29 §4.10 / M9); it is checked against
    ``RUNTIME_SCOPE_DIMENSIONS`` instead.
    """
    for block, keys in _nested_blocks(name).items():
        if block == "authority":
            continue  # covered exhaustively in test_sci_authority.py
        if block == "scope" and name == "RUNTIME-ARTIFACT-ATTESTATION":
            assert set(keys) == set(sci.SupplyChainScope.RUNTIME_SCOPE_DIMENSIONS)
            assert set(keys) < set(sci.SupplyChainScope.SCOPE_DIMENSIONS)
            assert "legal_portfolio" not in keys
            continue
        if block == "trustworthy_time_binding":
            model = (
                sci.DecisionTimeBinding
                if name == "ARTIFACT-ADMISSION-DECISION"
                else sci.AttestationTimeBinding
            )
        else:
            model = _NESTED_MODELS[block]
        assert set(keys) == set(model.model_fields), (
            f"{name}.{block} drifted from {model.__name__}: "
            f"template-only={sorted(set(keys) - set(model.model_fields))} "
            f"model-only={sorted(set(model.model_fields) - set(keys))}"
        )


def test_scope_anchor_is_nine_and_runtime_is_eight() -> None:
    """(§4.10 / M9) The scope anchors carry the documented nine / eight dimensions."""
    assert len(sci.SupplyChainScope.SCOPE_DIMENSIONS) == 9
    assert len(sci.SupplyChainScope.RUNTIME_SCOPE_DIMENSIONS) == 8
    assert set(sci.SupplyChainScope.SCOPE_DIMENSIONS) == set(
        sci.SupplyChainScope.model_fields
    )


def test_policy_field_group_anchor_matches_the_template() -> None:
    """(§4.3) The seventeen ``*_policy_digest`` fields plus the two approved-set digests."""
    anchor = set(sci.SoftwareReleasePolicyFieldGroups.model_fields)
    assert len(anchor) == 19
    assert len([name for name in anchor if name.endswith("_policy_digest")]) == 17
    assert anchor <= _top_level_keys("SOFTWARE-RELEASE-POLICY")
    assert anchor <= set(sci.SoftwareReleasePolicy.model_fields)


def test_closure_digest_anchor_matches_the_template() -> None:
    """(§4.9) The seventeen §11 closure set digests are template names, all on the manifest."""
    anchor = set(sci.DependencyClosureDigestSet.model_fields)
    assert len(anchor) == 17
    assert anchor <= _top_level_keys("DEPENDENCY-AND-TOOLCHAIN-CLOSURE-MANIFEST")
    assert anchor <= set(sci.DependencyToolchainClosureManifest.model_fields)


def test_admission_binding_anchor_matches_the_template() -> None:
    """(§4.4) The nine §15 step 1-7 scalar digest bindings are template names on the decision."""
    anchor = set(sci.AdmissionBindingSet.model_fields)
    assert len(anchor) == 9
    assert anchor <= _top_level_keys("ARTIFACT-ADMISSION-DECISION")
    assert anchor <= set(sci.ArtifactAdmissionDecision.model_fields)


def test_mandated_admit_binding_anchor_is_template_resolvable() -> None:
    """(§2.3) Every mandated-binding path resolves against the template, not an invented name."""
    decision_keys = _top_level_keys("ARTIFACT-ADMISSION-DECISION")
    nested = _nested_blocks("ARTIFACT-ADMISSION-DECISION")
    for path in sci.ArtifactAdmissionDecision.MANDATED_ADMIT_BINDINGS:
        head, _, tail = path.partition(".")
        assert (
            head in decision_keys
        ), f"{head} is not an ARTIFACT-ADMISSION-DECISION key"
        if tail:
            assert tail in nested[head], f"{path} is not a template sub-key"


# --- §4 ADR transcription anchors --------------------------------------------------------------


def _adr_text() -> str:
    return _adr_path().read_text(encoding="utf-8")


def test_invariant_titles_are_verbatim() -> None:
    """(§4.1) All sixteen SCI-INV titles appear verbatim in the ADR."""
    text = _adr_text()
    for index, title in enumerate(sci.SCI_INVARIANT_TITLES, start=1):
        assert (
            f"SCI-INV-{index:03d} — {title}" in text
        ), f"SCI-INV-{index:03d} title drifted from the ADR: {title!r}"


def test_acceptance_case_titles_are_verbatim() -> None:
    """(§4.7) All twelve SCI-AC titles appear verbatim in the ADR."""
    text = _adr_text()
    for index, title in enumerate(sci.SCI_ACCEPTANCE_CASE_TITLES, start=1):
        assert (
            f"SCI-AC-{index:03d} — {title}" in text
        ), f"SCI-AC-{index:03d} title drifted from the ADR: {title!r}"


def test_authority_ownership_actions_are_verbatim() -> None:
    """(§4.2) All seventeen §7 ``Action`` cells appear verbatim as table rows."""
    text = _adr_text()
    for action in sci.AUTHORITY_OWNERSHIP_ACTIONS:
        assert f"| {action} |" in text, f"§7 action drifted from the ADR: {action!r}"


def test_partition_failure_modes_are_verbatim() -> None:
    """(§4.6) All twelve §21 ``Failure`` cells appear verbatim as table rows."""
    text = _adr_text()
    for failure in sci.PARTITION_FAILURE_MODES:
        assert (
            f"| {failure} |" in text
        ), f"§21 failure drifted from the ADR: {failure!r}"


def test_admission_protocol_steps_are_verbatim() -> None:
    """(§4.4) All ten §15 steps appear verbatim in the ADR's ordered list."""
    text = _adr_text()
    for step in sci.ADMISSION_PROTOCOL_STEPS:
        assert step in text, f"§15 step drifted from the ADR: {step!r}"


def test_active_currentness_items_are_verbatim() -> None:
    """(§4.5) All eight §19 Safety Currentness Vector items appear verbatim."""
    text = _adr_text()
    for item in sci.ACTIVE_CURRENTNESS_ITEMS:
        assert item in text, f"§19 currentness item drifted from the ADR: {item!r}"


def test_policy_field_groups_are_verbatim() -> None:
    """(§4.3) All nine §8 prose field groups appear verbatim."""
    text = _adr_text()
    for group in sci.SOFTWARE_RELEASE_POLICY_FIELD_GROUPS:
        assert group in text, f"§8 field group drifted from the ADR: {group!r}"


def test_adr_status_is_still_proposed() -> None:
    """(§1 / §30 line 658) The ADR remains ``Proposed`` — Phase 1 promotes nothing."""
    assert "- **Status:** Proposed" in _adr_text()
    assert (
        "This ADR authorizes architecture and implementation planning only."
        in _adr_text()
    )


# --- §0.5 anti-phantom negative tokens ---------------------------------------------------------

#: Names owned by a sibling that must appear **nowhere** in the sci sources — not as an import, not
#: as a re-authored symbol, not even as a stray identifier (design #29 §6.2 negative-token).
_NEGATIVE_TOKENS = (
    "FailureDomainKind",
    "SOURCE_REPOSITORY",
    "BUILD_TOOLCHAIN",
    "ARTIFACT_SIGNING",
    "ARTIFACT_REGISTRY",
    "RestrictiveFenceRecord",
    "AdmissibilityResult",
    "CapacityVector",
    "SemanticValidationInputs",
    "HardSafetyEnvelope",
)


def _identifier_occurrences(token: str) -> list[str]:
    """Occurrences of ``token`` as a bare identifier in the sci sources, excluding prose."""
    pattern = re.compile(rf"(?<![\w`.]){re.escape(token)}(?![\w`])")
    hits: list[str] = []
    for path in sorted(_SCI_SRC.rglob("*.py")):
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.name}:{index}: {line.strip()}")
    return hits


@pytest.mark.parametrize("token", _NEGATIVE_TOKENS)
def test_sibling_owned_token_is_absent_as_an_identifier(token: str) -> None:
    """(§0.5 anti-phantom / §3.5) A sibling-owned name is never re-authored or bound here.

    The prose *may* name a sibling symbol inside double backticks to state the ownership split —
    that is the honesty requirement, not a violation — so the pattern excludes backticked
    references and dotted attribute access and looks only for bare identifiers.
    """
    assert _identifier_occurrences(token) == [], (
        f"{token} appears as a bare identifier in tos.sci — it is sibling-owned and must be "
        f"re-authored NOT AT ALL (design #29 §3.5): {_identifier_occurrences(token)}"
    )


def test_negative_token_scanner_finds_real_identifiers_and_ignores_prose() -> None:
    """(both-ways) The **production** scanner is exercised on the real corpus, not a regex copy.

    Re-declaring the pattern inside the canary would let the scanner and its own proof drift apart,
    so the same :func:`_identifier_occurrences` every negative-token assertion depends on is called
    here. ``AdmissionResult`` is a genuine bare identifier in the sci sources and **must** be found
    (a scanner that finds nothing proves nothing); ``fence_advances_floor`` appears only inside
    double backticks as an ownership note and **must not** be — which is exactly the discrimination
    the negative-token assertions rely on.
    """
    assert _identifier_occurrences(
        "AdmissionResult"
    ), "the scanner found no occurrence of a name that is definitely present — it is neutered"
    assert _identifier_occurrences("fence_advances_floor") == []
    assert _identifier_occurrences("ThisNameIsNowhereInTheSources") == []


def test_fence_advance_ownership_is_stated_not_reauthored() -> None:
    """(§3.5 M4) The cur floor-advance split is *documented*, and its symbols are absent as code."""
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(_SCI_SRC.rglob("*.py"))
    )
    assert "``fence_advances_floor``" in source  # the ownership note (prose)
    assert _identifier_occurrences("fence_advances_floor") == []
