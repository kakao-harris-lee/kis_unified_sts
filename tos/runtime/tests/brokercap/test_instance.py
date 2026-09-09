"""Tests for the Broker Capability Profile INSTANCE loader (plan §2 decision 3).

Loads the REAL, byte-immutable KIS draft instance
(``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml``) via a
repo-relative path resolved from this test file's own location — never a
hardcoded absolute path, never a copy checked into the runtime distribution
(plan §2 decision 3: "YAML 은 docs/broker-profiles/ 에 그대로 ... 이동 금지").

**Both documents now load end-to-end (2026-09-10 instance-authoring act,
operator-approved).** The REAL_PROD document used to be missing BOTH
`profile_identity._model_view` and `live_scope._model_view` (this suite
used to pin that gap as an expected `BrokerInstanceConfigError`). The
operator approved adding exactly those two annotation blocks to the
byte-immutable draft — every value is a re-spelling of a value REAL_PROD's
own template already carried, never a newly declared value — so
`load_instance_documents(_DRAFT_PATH)` now returns both documents. REAL_PROD
stays `status: DRAFT` with `approvers: []`, so `verified_dimensions ==
frozenset()`, `instance_version_current` is `False`, and
`capability_admissible` is `PROHIBITED` for it — a template annotation is
not an approval act, and this suite exercises that honest, unapproved
verdict directly rather than pinning a load failure. The rest of this suite
exercises full instance-document semantics against the MOCK_VTS document,
sliced out of the same real file's bytes with no edits
(`_mock_vts_only_text`), unaffected by this change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from tos.brokercap.predicates import capability_admissible
from tos.brokercap.records import RequiredCapabilitySet
from tos.brokercap.routing import ClaimKind, ProvenanceClass, provenance_admits_claim
from tos.brokercap.vocabulary import (
    AssuranceLevel,
    CapabilityDimension,
)
from tos_runtime.brokercap import instance as instance_module
from tos_runtime.brokercap.instance import (
    BrokerInstanceConfigError,
    InstanceDocument,
    instance_version_current,
    load_instance_document,
    load_instance_documents,
    select_document,
)

# tos/runtime/tests/brokercap/test_instance.py -> repo root is 4 parents up.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DRAFT_PATH = (
    _REPO_ROOT / "docs" / "broker-profiles" / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mock_vts_only_text() -> str:
    """Slice out just the MOCK_VTS YAML document from the real draft file's bytes.

    No content is edited — this is a byte-range slice between the file's two
    ``---`` document separators, used so the rest of this suite can exercise
    full instance-document semantics against MOCK_VTS alone (single-document
    scenarios, e.g. ``select_document``) without depending on REAL_PROD's own
    declaration set, and without ever writing back to the byte-immutable
    source file.
    """
    lines = _DRAFT_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    separator_indices = [
        i for i, line in enumerate(lines) if line.rstrip("\n") == "---"
    ]
    assert len(separator_indices) == 2, (
        "expected exactly 2 '---' document separators in the real draft file "
        f"(found {len(separator_indices)}) — the slice logic assumes the "
        "file's known 2-document shape"
    )
    start, end = separator_indices
    return "".join(lines[start:end])


def _independent_declared_dimension_count(yaml_text: str) -> int:
    """Recompute the expected declared-dimension count directly from YAML.

    Independent of `instance.py`'s own logic: counts capability blocks that
    carry a `_model_view` whose `dimension` is not null.
    """
    raw = yaml.safe_load(yaml_text)
    count = 0
    for block in raw["capabilities"].values():
        model_view = block.get("_model_view") if isinstance(block, dict) else None
        if isinstance(model_view, dict) and model_view.get("dimension") is not None:
            count += 1
    return count


def _minimal_document_yaml(*, environment: str, artifact_id: str) -> str:
    """A small, fully synthetic (not real-file-derived) valid instance document."""
    return f"""
profile_identity:
  artifact_id: {artifact_id}
  environment: {environment}
  status: DRAFT
  approvers: []
  profile_version: 0.0.1
  effective_from: null
  expires_at: null
  evidence_package_version: TBD
  superseded_version_link: null
  change_reason: TBD
  _model_view:
    broker_id: null
    api_product: null
    api_version: null
    environment: {environment}
    account_type: null
    market: null
    instrument_class: null
    order_type: null
    session_type: null
    credential_scope: null
live_scope:
  _model_view:
    account_scope: null
    instrument_scope: null
    order_type_scope: null
    quantity_risk_limit: null
    session_scope: null
    action_classes: []
    mode: null
    reduced_off_unattended_partition_protection: null
capabilities: {{}}
"""


@pytest.fixture
def mock_vts_document(tmp_path: Path) -> InstanceDocument:
    path = tmp_path / "mock-vts-only.yaml"
    path.write_text(_mock_vts_only_text(), encoding="utf-8")
    documents = load_instance_documents(path)
    assert len(documents) == 1
    return documents[0]


# ===========================================================================
# The real file: 2 raw YAML documents, sha256 unchanged, both documents load
# ===========================================================================


def test_real_file_has_exactly_two_raw_yaml_documents() -> None:
    raw_docs = list(yaml.safe_load_all(_DRAFT_PATH.read_text(encoding="utf-8")))
    assert len(raw_docs) == 2
    assert (
        raw_docs[0]["profile_identity"]["artifact_id"] == "KIS-BCP-MOCK-VTS-DRAFT-0001"
    )
    assert raw_docs[0]["profile_identity"]["environment"] == "MOCK_VTS"
    assert (
        raw_docs[1]["profile_identity"]["artifact_id"] == "KIS-BCP-REAL-PROD-DRAFT-0001"
    )
    assert raw_docs[1]["profile_identity"]["environment"] == "REAL_PROD"


def test_real_file_loads_both_documents_via_load_instance_documents() -> None:
    """2026-09-10 instance-authoring act (module docstring): REAL_PROD now
    carries both `_model_view` blocks, so the real file's both documents
    load end-to-end through the strict, "every document must be valid"
    loader — no partial-success path is exercised any more."""
    documents = load_instance_documents(_DRAFT_PATH)
    assert len(documents) == 2
    mock_doc, real_doc = documents
    assert mock_doc.artifact_id == "KIS-BCP-MOCK-VTS-DRAFT-0001"
    assert mock_doc.environment == "MOCK_VTS"
    assert real_doc.artifact_id == "KIS-BCP-REAL-PROD-DRAFT-0001"
    assert real_doc.environment == "REAL_PROD"


def test_real_prod_document_is_draft_with_zero_verified_dimensions() -> None:
    """The new `_model_view` blocks re-spell REAL_PROD's own existing
    template values in kernel vocabulary — they declare no new value and are
    not an approval act. REAL_PROD therefore stays `status: DRAFT`,
    `approvers: ()`, and `verified_dimensions == frozenset()` (plan §2
    decision 3's VERIFIED-0 honesty), exactly like MOCK_VTS."""
    real_doc = load_instance_document(_DRAFT_PATH, environment="REAL_PROD")
    assert real_doc.status == "DRAFT"
    assert real_doc.approvers == ()
    assert real_doc.verified_dimensions == frozenset()
    assert len(real_doc.declared_dimensions) == 17


def test_real_prod_instance_version_current_is_false() -> None:
    real_doc = load_instance_document(_DRAFT_PATH, environment="REAL_PROD")
    assert (
        instance_version_current(real_doc, degraded_since_authorization=None) is False
    )
    assert (
        instance_version_current(real_doc, degraded_since_authorization=False) is False
    )


def test_real_prod_capability_admissible_is_prohibited() -> None:
    """REAL_PROD now loads, but DRAFT + approvers=[] + VERIFIED-0 still make
    every broker-reaching admissibility check PROHIBITED — the honest
    verdict for an unapproved draft (module docstring), not a defect."""
    from tos.brokercap.vocabulary import Admissibility

    real_doc = load_instance_document(_DRAFT_PATH, environment="REAL_PROD")
    required = RequiredCapabilitySet(
        required_dimensions=frozenset({CapabilityDimension.ORDER_IDENTITY}),
        required_level=AssuranceLevel.LEVEL_1_DOCUMENTED,
        minimum_live_gate_satisfied=True,
    )
    verdict = capability_admissible(
        real_doc.profile,
        "ORDER_SEND",
        required,
        version_current=instance_version_current(
            real_doc, degraded_since_authorization=None
        ),
    )
    assert verdict is Admissibility.PROHIBITED


def test_real_file_sha256_unchanged_after_full_load() -> None:
    before = _sha256(_DRAFT_PATH)
    load_instance_documents(_DRAFT_PATH)
    after = _sha256(_DRAFT_PATH)
    assert before == after


def test_real_file_sha256_unchanged_after_successful_slice_load(tmp_path: Path) -> None:
    before = _sha256(_DRAFT_PATH)
    path = tmp_path / "mock-vts-only.yaml"
    path.write_text(_mock_vts_only_text(), encoding="utf-8")
    load_instance_documents(path)
    after = _sha256(_DRAFT_PATH)
    assert before == after


# ===========================================================================
# The MOCK_VTS document (complete, loads cleanly)
# ===========================================================================


def test_mock_vts_identity_fields(mock_vts_document: InstanceDocument) -> None:
    assert mock_vts_document.artifact_id == "KIS-BCP-MOCK-VTS-DRAFT-0001"
    assert mock_vts_document.environment == "MOCK_VTS"
    assert mock_vts_document.status == "DRAFT"
    assert mock_vts_document.approvers == ()


def test_mock_vts_verified_dimensions_is_empty(
    mock_vts_document: InstanceDocument,
) -> None:
    """VERIFIED 0 honesty (plan §2 decision 3) — no probe/spec ever verified a dimension."""
    assert mock_vts_document.verified_dimensions == frozenset()


def test_mock_vts_declared_dimensions_matches_independent_yaml_count(
    mock_vts_document: InstanceDocument,
) -> None:
    expected = _independent_declared_dimension_count(_mock_vts_only_text())
    assert expected == 17  # all 17 CapabilityDimension members are declared
    assert len(mock_vts_document.declared_dimensions) == expected
    assert mock_vts_document.declared_dimensions == frozenset(CapabilityDimension)


def test_mock_vts_capability_admissible_prohibited_regardless_of_version_current(
    mock_vts_document: InstanceDocument,
) -> None:
    required = RequiredCapabilitySet(
        required_dimensions=frozenset({CapabilityDimension.ORDER_IDENTITY}),
        required_level=AssuranceLevel.LEVEL_1_DOCUMENTED,
        minimum_live_gate_satisfied=True,
    )
    from tos.brokercap.vocabulary import Admissibility

    verdict_natural = capability_admissible(
        mock_vts_document.profile,
        "ORDER_SEND",
        required,
        version_current=instance_version_current(
            mock_vts_document, degraded_since_authorization=None
        ),
    )
    assert verdict_natural is Admissibility.PROHIBITED

    # Even force-feeding version_current=True must still PROHIBIT — VERIFIED 0
    # means no declaration can ever authorize, independent of version currency.
    verdict_forced_current = capability_admissible(
        mock_vts_document.profile, "ORDER_SEND", required, version_current=True
    )
    assert verdict_forced_current is Admissibility.PROHIBITED


def test_mock_vts_instance_version_current_is_false(
    mock_vts_document: InstanceDocument,
) -> None:
    """DRAFT + approvers=[] => no approved active version => not current,
    regardless of ``degraded_since_authorization`` (independent-review
    finding F5): with no approved version at all, the predicate's
    ``active_version is None`` branch already denies before the
    degradation gate is even reached."""
    assert (
        instance_version_current(mock_vts_document, degraded_since_authorization=None)
        is False
    )
    assert (
        instance_version_current(mock_vts_document, degraded_since_authorization=False)
        is False
    )


def test_instance_version_current_degraded_flag_is_load_bearing(
    tmp_path: Path,
) -> None:
    """Independent-review finding F5 mutation M6: before this fix,
    ``degraded_since_authorization`` was hardcoded ``None`` inside
    ``instance_version_current``, making the kernel predicate's
    degradation gate unconditionally deny — the approvers gate was
    therefore dead code (M6: 0 tests ever went red for it). With a
    document that DOES carry an approved version (non-empty ``approvers``,
    so ``active_version == presented_version``), the degraded flag is now
    the ONLY thing separating ``True`` from ``False`` — proving it is
    genuinely consumed, not a decorative parameter."""
    text = _minimal_document_yaml(environment="ENV_APPROVED", artifact_id="APPROVED-1")
    text = text.replace(
        "approvers: []\n  profile_version: 0.0.1",
        "approvers: [ops-approver-1]\n  profile_version: 0.0.1",
    )
    path = tmp_path / "approved.yaml"
    path.write_text(text, encoding="utf-8")
    documents = load_instance_documents(path)
    assert len(documents) == 1
    document = documents[0]
    assert document.approvers == ("ops-approver-1",)
    assert document.status != "EXPIRED"

    assert (
        instance_version_current(document, degraded_since_authorization=False) is True
    )
    assert (
        instance_version_current(document, degraded_since_authorization=None) is False
    )
    assert (
        instance_version_current(document, degraded_since_authorization=True) is False
    )


def test_mock_vts_select_document_by_environment(
    mock_vts_document: InstanceDocument,
) -> None:
    selected = select_document((mock_vts_document,), environment="MOCK_VTS")
    assert selected is mock_vts_document


def test_mock_vts_select_document_unknown_environment_errors(
    mock_vts_document: InstanceDocument,
) -> None:
    with pytest.raises(BrokerInstanceConfigError, match="REAL_PROD"):
        select_document((mock_vts_document,), environment="REAL_PROD")


# ===========================================================================
# Provenance mapping (closed AssuranceSource -> ProvenanceClass table)
# ===========================================================================


def test_official_specification_sources_map_to_official_document(
    mock_vts_document: InstanceDocument,
) -> None:
    assert mock_vts_document.provenance, "expected at least one produced provenance"
    assert {p.provenance_class for p in mock_vts_document.provenance} == {
        ProvenanceClass.OFFICIAL_DOCUMENT
    }


def test_produced_provenance_never_admits_real_order_capability(
    mock_vts_document: InstanceDocument,
) -> None:
    for provenance in mock_vts_document.provenance:
        assert (
            provenance_admits_claim(provenance, ClaimKind.REAL_ORDER_CAPABILITY)
            is False
        )


def test_controlled_sandbox_test_source_is_reported_unmapped(
    mock_vts_document: InstanceDocument,
) -> None:
    """`credentials_and_revocation` cites CONTROLLED_SANDBOX_TEST (an order-emitting
    dedup probe) — the closed table refuses to launder it into CONTROLLED_GET_PROBE
    (module docstring: that class's ProbeManifest asserts `emits_orders: False`)."""
    assert "CONTROLLED_SANDBOX_TEST" in mock_vts_document.unmapped_sources


# ===========================================================================
# select_document — synthetic multi-document scenarios
# ===========================================================================


def test_select_document_zero_matches(tmp_path: Path) -> None:
    path = tmp_path / "one-doc.yaml"
    path.write_text(
        _minimal_document_yaml(environment="ENV_A", artifact_id="A-1"), encoding="utf-8"
    )
    documents = load_instance_documents(path)
    with pytest.raises(BrokerInstanceConfigError, match="found 0"):
        select_document(documents, environment="ENV_B")


def test_select_document_multiple_matches(tmp_path: Path) -> None:
    text = "\n---\n".join(
        [
            _minimal_document_yaml(environment="ENV_A", artifact_id="A-1"),
            _minimal_document_yaml(environment="ENV_A", artifact_id="A-2"),
        ]
    )
    path = tmp_path / "dup-env.yaml"
    path.write_text(text, encoding="utf-8")
    documents = load_instance_documents(path)
    assert len(documents) == 2
    with pytest.raises(BrokerInstanceConfigError, match="found 2"):
        select_document(documents, environment="ENV_A")


def test_select_document_exact_match_among_several(tmp_path: Path) -> None:
    text = "\n---\n".join(
        [
            _minimal_document_yaml(environment="ENV_A", artifact_id="A-1"),
            _minimal_document_yaml(environment="ENV_B", artifact_id="B-1"),
        ]
    )
    path = tmp_path / "two-envs.yaml"
    path.write_text(text, encoding="utf-8")
    documents = load_instance_documents(path)
    selected = select_document(documents, environment="ENV_B")
    assert selected.artifact_id == "B-1"


# ===========================================================================
# Fail-closed refusals — synthetic, deliberately malformed documents
# ===========================================================================


def test_capability_block_missing_model_view_is_refused(tmp_path: Path) -> None:
    text = _minimal_document_yaml(environment="ENV_A", artifact_id="A-1").replace(
        "capabilities: {}",
        "capabilities:\n  some_capability:\n    status: UNKNOWN\n",
    )
    path = tmp_path / "missing-model-view.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="capabilities.some_capability"):
        load_instance_documents(path)


def test_misspelled_status_value_is_named_in_the_error(tmp_path: Path) -> None:
    text = _minimal_document_yaml(environment="ENV_A", artifact_id="A-1").replace(
        "capabilities: {}",
        "capabilities:\n"
        "  order_identity_capability:\n"
        "    _model_view:\n"
        "      dimension: ORDER_IDENTITY\n"
        "      status: NOT_A_REAL_STATUS\n"
        "      assurance_level: null\n"
        "      evidence_reference: null\n"
        "      restriction: null\n"
        "      restriction_approved: null\n"
        "      fallback_reference: null\n"
        "      assurance_sources: []\n",
    )
    path = tmp_path / "bad-status.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="NOT_A_REAL_STATUS"):
        load_instance_documents(path)


def test_missing_live_scope_model_view_is_refused(tmp_path: Path) -> None:
    text = _minimal_document_yaml(environment="ENV_A", artifact_id="A-1")
    text = text.replace(
        "live_scope:\n  _model_view:",
        "live_scope:\n  not_a_model_view:",
    )
    path = tmp_path / "missing-live-scope.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError, match="live_scope"):
        load_instance_documents(path)


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BrokerInstanceConfigError):
        load_instance_documents(tmp_path / "does-not-exist.yaml")


def test_non_mapping_document_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "not-a-mapping.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(BrokerInstanceConfigError):
        load_instance_documents(path)


# ===========================================================================
# Negative-grep — module discipline (no os.environ, no validator bypasses)
# ===========================================================================


def test_module_never_reads_os_environ() -> None:
    source = Path(instance_module.__file__).read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "os.getenv" not in source
    assert "import os" not in source


def test_module_never_bypasses_pydantic_validators() -> None:
    source = Path(instance_module.__file__).read_text(encoding="utf-8")
    assert "model_construct" not in source
    assert "model_copy(update=" not in source
