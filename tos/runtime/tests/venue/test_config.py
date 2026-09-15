"""tos_runtime.venue.config — loader unit tests (hermetic, tmp_path only)."""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.ioc import OrderConstructionPolicy
from tos.venue import ActionClass, VenueConstraintPolicy, classify_record_pair
from tos_runtime.venue.config import (
    LoadedOrderConstructionPolicy,
    LoadedVenuePolicy,
    VenuePolicyConfigError,
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from .conftest import (
    SCHEME,
    ocp_yaml,
    venue_policy_yaml,
    write_fixture_ocp,
    write_fixture_venue_policy,
)

# ===========================================================================
# venue_constraint_policy.yaml — happy path
# ===========================================================================


def test_load_venue_constraint_policy_happy_path(tmp_path: Path) -> None:
    path = write_fixture_venue_policy(tmp_path)
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    assert isinstance(loaded, LoadedVenuePolicy)
    assert isinstance(loaded.policy, VenueConstraintPolicy)
    assert loaded.policy.policy_id == "vcp-fixture-1"
    assert loaded.policy.policy_generation == 1
    assert loaded.policy.canonical_digest is not None
    assert loaded.scope.instrument == "K200F"
    assert loaded.scope.instrument_class == "krx-futures"
    assert loaded.null_shape_bounds == ("max_quantity",)
    assert loaded.quantity_constraint.lot_size == 1
    assert loaded.quantity_constraint.max_quantity is None
    assert loaded.policy.admitting_phases_for(ActionClass.NEW_LONG) == frozenset(
        {"REGULAR"}
    )


def test_load_venue_constraint_policy_scope_identity_composed(tmp_path: Path) -> None:
    path = write_fixture_venue_policy(tmp_path)
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    assert loaded.policy.scope == "paper/kis/acct-1/krx/futures/K200F"


def test_load_venue_constraint_policy_all_shape_bounds_null(tmp_path: Path) -> None:
    text = venue_policy_yaml().replace("price_min: 100", "price_min: null")
    text = text.replace("price_max: 500", "price_max: null")
    text = text.replace("tick_size: 5", "tick_size: null")
    text = text.replace("lot_size: 1", "lot_size: null")
    text = text.replace("min_quantity: 1", "min_quantity: null")
    path = write_fixture_venue_policy(tmp_path, text)
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    assert set(loaded.null_shape_bounds) == {
        "price_min",
        "price_max",
        "tick_size",
        "lot_size",
        "min_quantity",
        "max_quantity",
    }


def test_load_venue_constraint_policy_canonical_digest_tbd_accepted_and_reload_matches(
    tmp_path: Path,
) -> None:
    """``canonical_digest: TBD`` (the fixture default) passes; reloading the
    SAME document with the freshly computed digest substituted in must also
    pass and produce the identical digest (module docstring's tamper/stale
    cross-check, positive side)."""
    path = write_fixture_venue_policy(tmp_path)
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    text_with_real_digest = venue_policy_yaml().replace(
        "canonical_digest: TBD", f'canonical_digest: "{loaded.policy.canonical_digest}"'
    )
    path2 = tmp_path / "reload2.yaml"
    path2.write_text(text_with_real_digest, encoding="utf-8")
    loaded2 = load_venue_constraint_policy(path2, scheme=SCHEME)
    assert loaded2.policy.canonical_digest == loaded.policy.canonical_digest


# ===========================================================================
# venue_constraint_policy.yaml — negative / fail-closed cases
# ===========================================================================


def test_load_venue_constraint_policy_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VenuePolicyConfigError, match="not found"):
        load_venue_constraint_policy(tmp_path / "nope.yaml", scheme=SCHEME)


def test_load_venue_constraint_policy_not_a_mapping(tmp_path: Path) -> None:
    path = write_fixture_venue_policy(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(VenuePolicyConfigError, match="top-level mapping"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_wrong_artifact_type_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        "artifact_type: VENUE_CONSTRAINT_POLICY",
        "artifact_type: ORDER_CONSTRUCTION_POLICY",
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="artifact_type"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_wrong_schema_version_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        'schema_version: "1.0-DRAFT"', 'schema_version: "2.0"'
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="schema_version"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_draft_status_refused(tmp_path: Path) -> None:
    text = venue_policy_yaml(status="DRAFT")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ISSUED"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_policy_id(tmp_path: Path) -> None:
    text = venue_policy_yaml().replace('policy_id: "vcp-fixture-1"\n', "")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="policy_id"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_tbd_policy_id_refused(tmp_path: Path) -> None:
    text = venue_policy_yaml().replace('policy_id: "vcp-fixture-1"', "policy_id: TBD")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="policy_id"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_null_policy_id_refused(tmp_path: Path) -> None:
    text = venue_policy_yaml().replace('policy_id: "vcp-fixture-1"', "policy_id: null")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="policy_id"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_tampered_digest_refused(tmp_path: Path) -> None:
    text = venue_policy_yaml(canonical_digest='"deadbeef"')
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="canonical_digest"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_scope_empty_singleton_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace('environments: ["paper"]', "environments: []")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="EXACTLY one"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_scope_two_entry_singleton_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        'environments: ["paper"]', 'environments: ["paper", "live"]'
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="EXACTLY one"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_scope_action_classes_unknown_token_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml(action_classes='["NOT_A_REAL_ACTION", "NEW_SHORT"]')
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ActionClass"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_action_outside_declared_scope_refused(
    tmp_path: Path,
) -> None:
    """The cross-check: an ``admitting_phase_rules`` action not present in
    ``scope.action_classes`` must refuse (a scope-declaration bug)."""
    text = venue_policy_yaml(action_classes='["NEW_SHORT"]')
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="not in scope.action_classes"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_model_view_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml()
    idx = text.index("_model_view:")
    end_idx = text.index("_runtime:")
    text = text[:idx] + text[end_idx:]
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="_model_view"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_runtime_block_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml()
    idx = text.index("_runtime:")
    text = text[:idx]
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="_runtime"):
        load_venue_constraint_policy(path, scheme=SCHEME)


_ADMITTING_PHASE_RULES_BLOCK = (
    '_model_view:\n  admitting_phase_rules:\n    - action: "NEW_LONG"\n'
    '      admitting_phases: ["REGULAR"]\n    - action: "NEW_SHORT"\n'
    '      admitting_phases: ["REGULAR"]\n'
)


def test_load_venue_constraint_policy_null_admitting_phase_rules_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        _ADMITTING_PHASE_RULES_BLOCK, "_model_view:\n  admitting_phase_rules: null\n"
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="admitting_phase_rules"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_empty_admitting_phase_rules_is_accepted(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml(action_classes="[]").replace(
        _ADMITTING_PHASE_RULES_BLOCK, "_model_view:\n  admitting_phase_rules: []\n"
    )
    path = write_fixture_venue_policy(tmp_path, text)
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    assert loaded.policy.admitting_phase_rules == ()


def test_load_venue_constraint_policy_unknown_action_token_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        'action: "NEW_LONG"', 'action: "NOT_A_REAL_ACTION"'
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ActionClass"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_unknown_constraint_class_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        "required_constraint_classes: []",
        'required_constraint_classes: ["NOT_A_CLASS"]',
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ConstraintClass"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_unknown_quantity_unit_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        'quantity_unit: "CONTRACTS"', 'quantity_unit: "BOGUS_UNIT"'
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="QuantityUnitKind"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_shape_constraint_key_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace("    max_quantity: null\n", "")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="max_quantity"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_null_allowed_order_types_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        'allowed_order_types: ["LIMIT"]', "allowed_order_types: null"
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="allowed_order_types"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_empty_allowed_order_types_is_accepted(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        'allowed_order_types: ["LIMIT"]', "allowed_order_types: []"
    )
    path = write_fixture_venue_policy(tmp_path, text)
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    assert loaded.policy.shape_constraints.allowed_order_types == frozenset()


def test_load_venue_constraint_policy_null_dependency_closure_edges_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace(
        "dependency_closure:\n    edges: []\n", "dependency_closure:\n    edges: null\n"
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="edges"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_template_list_key_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace("approved_sources: []\n", "")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="approved_sources"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_authority_mapping_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml()
    start = text.index("authority:\n")
    end = text.index("evidence:\n")
    text = text[:start] + text[end:]
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="authority"):
        load_venue_constraint_policy(path, scheme=SCHEME)


# ===========================================================================
# order_construction_policy.yaml — happy path
# ===========================================================================


def test_load_order_construction_policy_happy_path(tmp_path: Path) -> None:
    path = write_fixture_ocp(tmp_path)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert isinstance(loaded, LoadedOrderConstructionPolicy)
    assert isinstance(loaded.policy, OrderConstructionPolicy)
    assert loaded.policy.policy_id == "ocp-fixture-1"
    assert loaded.policy.signer_identity is None
    assert loaded.policy.approval_identity is None
    assert loaded.policy.evidence_package_ref is None
    assert loaded.wire_codec_kind is None
    assert loaded.wire_fields == frozenset()
    assert loaded.construction_generation == 1


def test_load_order_construction_policy_null_construction_generation_accepted(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(construction_generation="null")
    path = write_fixture_ocp(tmp_path, text)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.construction_generation is None


def test_load_order_construction_policy_digest_matches_kernel_issuance(
    tmp_path: Path,
) -> None:
    """The loader's own OCP digest must equal the digest a bare kernel
    ``OrderConstructionPolicy.issue`` call from the same three coordinates
    produces — classify_record_pair on the pair must be IDEMPOTENT_DUP,
    never CRITICAL_CONFLICT (plan §2 decision 6)."""
    path = write_fixture_ocp(tmp_path)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    kernel_issued = OrderConstructionPolicy.issue(
        scheme=SCHEME,
        policy_id="ocp-fixture-1",
        policy_generation=1,
        policy_version="1.0.0",
        signer_identity=None,
        approval_identity=None,
        evidence_package_ref=None,
    )
    assert isinstance(kernel_issued, OrderConstructionPolicy)
    assert loaded.policy.canonical_digest == kernel_issued.canonical_digest
    verdict = classify_record_pair(
        loaded.policy.policy_id,
        loaded.policy.canonical_digest,
        kernel_issued.policy_id,
        kernel_issued.canonical_digest,
    )
    assert verdict.value == "IDEMPOTENT_DUP"


def test_load_order_construction_policy_wire_codec_mapping(tmp_path: Path) -> None:
    text = ocp_yaml(wire_codec='{kind: "kis-order-cash-v1", wire_fields: ["a", "b"]}')
    path = write_fixture_ocp(tmp_path, text)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.wire_codec_kind == "kis-order-cash-v1"
    assert loaded.wire_fields == frozenset({"a", "b"})


# ===========================================================================
# order_construction_policy.yaml — negative / fail-closed cases
# ===========================================================================


def test_load_order_construction_policy_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VenuePolicyConfigError, match="not found"):
        load_order_construction_policy(tmp_path / "nope.yaml", scheme=SCHEME)


def test_load_order_construction_policy_wrong_artifact_type_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        "artifact_type: ORDER_CONSTRUCTION_POLICY",
        "artifact_type: VENUE_CONSTRAINT_POLICY",
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="artifact_type"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_draft_status_refused(tmp_path: Path) -> None:
    text = ocp_yaml(status="DRAFT")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ISSUED"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_tbd_policy_id_refused(tmp_path: Path) -> None:
    text = ocp_yaml().replace('policy_id: "ocp-fixture-1"', "policy_id: TBD")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="policy_id"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_tampered_digest_refused(tmp_path: Path) -> None:
    text = ocp_yaml(canonical_digest='"deadbeef"')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="canonical_digest"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_scope_empty_singleton_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace('environments: ["paper"]', "environments: []")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="EXACTLY one"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_model_view_generation_mismatch_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(model_view_policy_generation=99)
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="policy_generation"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_missing_model_view_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml()
    idx = text.index("_model_view:")
    end_idx = text.index("_runtime:")
    text = text[:idx] + text[end_idx:]
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="_model_view"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_missing_wire_codec_key_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace("  wire_codec: null\n", "")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="wire_codec"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_canonicalization_version_mismatch_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(canonicalization_version="not-the-real-scheme-version")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="canonicalization_version"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_malformed_wire_codec_mapping_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(wire_codec='{kind: "kis-order-cash-v1"}')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="wire_fields"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_missing_template_list_key_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace("intent_schema_versions: []\n", "")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="intent_schema_versions"):
        load_order_construction_policy(path, scheme=SCHEME)
