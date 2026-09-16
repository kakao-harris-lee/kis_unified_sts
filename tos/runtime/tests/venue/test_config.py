"""tos_runtime.venue.config — loader unit tests (hermetic, tmp_path only)."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.egressgw import EffectBasis, EffectDimensionSpec, LotRoundingPolicy
from tos.ioc import AxisBinding, ConformanceAxis, OrderConstructionPolicy
from tos.venue import ActionClass, VenueConstraintPolicy, classify_record_pair
from tos_runtime.venue.config import (
    LoadedOrderConstructionPolicy,
    LoadedVenuePolicy,
    VenuePolicyConfigError,
    load_order_construction_policy,
    load_venue_constraint_policy,
)
from tos_runtime.venue.construction_rules import ActionClassShape

from .conftest import (
    SCHEME,
    ocp_yaml,
    venue_policy_yaml,
    write_fixture_ocp,
    write_fixture_venue_policy,
)

#: The shipped production paper OCP instance — same coordinate as
#: ``tests/compose/test_deploy_policies.py``'s own ``_REAL_OCP`` (parallel depth:
#: ``tos/runtime/tests/venue/test_config.py`` and
#: ``tos/runtime/tests/compose/test_deploy_policies.py`` are both 4 ``parents[]`` from the repo
#: root).
_REAL_OCP_PATH = (
    Path(__file__).resolve().parents[4]
    / "config"
    / "tos_runtime"
    / "paper"
    / "order_construction_policy.yaml"
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


def test_load_venue_constraint_policy_old_scalar_scope_shape_refused(
    tmp_path: Path,
) -> None:
    """Team-lead review, 2026-09-15: the pre-correction singular-scalar
    ``scope`` shape (``environment: "paper"`` etc, the v1 §4.1 draft this
    module no longer speaks) must be REJECTED outright, never silently
    accepted alongside the template's own plural-list shape — the loader
    reads ONLY ``environments``/``brokers``/.../``instruments`` (explicit
    lists), so a document still carrying the old singular keys is missing
    every required plural key and refuses on the first one."""
    text = venue_policy_yaml().replace(
        (
            "scope:\n"
            '  environments: ["paper"]\n'
            "  safety_cells: []\n"
            '  brokers: ["kis"]\n'
            '  accounts: ["acct-1"]\n'
            '  venues: ["krx"]\n'
            '  market_segments: ["futures"]\n'
            '  instruments: ["K200F"]\n'
            "  contracts: []\n"
            '  action_classes: ["NEW_LONG", "NEW_SHORT"]\n'
        ),
        (
            "scope:\n"
            '  environment: "paper"\n'
            '  broker: "kis"\n'
            '  account: "acct-1"\n'
            '  venue: "krx"\n'
            '  market_segment: "futures"\n'
            '  instrument: "K200F"\n'
        ),
    )
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="environments"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_old_scalar_scope_shape_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        (
            "scope:\n"
            '  environments: ["paper"]\n'
            "  safety_cells: []\n"
            '  brokers: ["kis"]\n'
            '  accounts: ["acct-1"]\n'
            "  venues: []\n"
            "  market_segments: []\n"
            '  instruments: ["K200F"]\n'
            "  contracts: []\n"
            "  action_classes: []\n"
            '  order_types: ["LIMIT"]\n'
        ),
        (
            "scope:\n"
            '  environment: "paper"\n'
            '  broker: "kis"\n'
            '  account: "acct-1"\n'
            '  instrument: "K200F"\n'
        ),
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="environments"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_effective_from_refused(
    tmp_path: Path,
) -> None:
    """Team-lead review MEDIUM, 2026-09-15: ``effective_from`` (may be
    ``null``, but the KEY must be present per DR-0002 §2.1 "every template
    key is present") was previously unchecked."""
    text = venue_policy_yaml().replace('effective_from: "2026-09-15"\n', "")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="effective_from"):
        load_venue_constraint_policy(path, scheme=SCHEME)


def test_load_venue_constraint_policy_missing_review_due_refused(
    tmp_path: Path,
) -> None:
    text = venue_policy_yaml().replace("review_due: null\n", "")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="review_due"):
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


@pytest.mark.parametrize("marker", ['"TBD"', '""'])
def test_load_venue_constraint_policy_scope_named_tbd_singleton_refused(
    tmp_path: Path, marker: str
) -> None:
    """An operator-fill gate: a scope coordinate still at the template's
    ``TBD`` marker (or empty) must not boot as a phantom scope — the real
    deploy files under ``config/tos_runtime/paper/`` ship exactly this way
    until the operator fills them."""
    text = venue_policy_yaml().replace('accounts: ["acct-1"]', f"accounts: [{marker}]")
    path = write_fixture_venue_policy(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="named-TBD"):
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


def test_load_order_construction_policy_missing_effective_from_refused(
    tmp_path: Path,
) -> None:
    """Team-lead review MEDIUM, 2026-09-15 (mirrors the venue-policy case)."""
    text = ocp_yaml().replace("effective_from: null\n", "")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="effective_from"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_missing_review_due_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace("review_due: null\n", "")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="review_due"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_scope_action_classes_null_refused(
    tmp_path: Path,
) -> None:
    """Team-lead review MEDIUM, 2026-09-15: ``scope.action_classes`` was
    previously unvalidated on the OCP loader entirely (the VCP loader always
    validated it) — a ``null`` value must refuse, not silently pass."""
    text = ocp_yaml().replace("action_classes: []\n", "action_classes: null\n")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="action_classes"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_scope_action_classes_unknown_token_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace("action_classes: []\n", 'action_classes: ["NOPE"]\n')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ActionClass"):
        load_order_construction_policy(path, scheme=SCHEME)


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


def test_load_order_construction_policy_scope_named_tbd_singleton_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace('instruments: ["K200F"]', 'instruments: ["TBD"]')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="named-TBD"):
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


# ===========================================================================
# order_construction_policy.yaml — (a′) wave, lane A: _runtime.construction
# ===========================================================================
#
# ``ocp_yaml()``'s default construction block (tos_runtime/tests/venue/_documents.py) is
# well-formed FIXTURE DATA (max_quantity=10 etc — NOT the operator-adopted production values,
# see that module's own docstring). Every mutation test below starts from that default text and
# breaks exactly one leaf via ``.replace()``/regex, mirroring this file's existing idiom for
# every other OCP negative case above.


def test_load_order_construction_policy_construction_happy_path(tmp_path: Path) -> None:
    path = write_fixture_ocp(tmp_path)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    rules = loaded.construction_rules
    assert rules.sizing_bound.max_quantity == Decimal(10)
    assert rules.sizing_bound.min_quantity == Decimal(1)
    assert rules.sizing_bound.lot_size == Decimal(1)
    assert rules.sizing_bound.lot_rounding is LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED
    assert rules.sizing_bound.risk_budget == Decimal(100)
    assert rules.sizing_bound.per_unit_risk == Decimal(10)
    assert rules.sizing_bound.max_notional is None
    assert (
        rules.sizing_bound.quantity_unit is None
    )  # not OCP's data source — see loader docstring
    assert rules.sizing_bound.admitted_quantity_bases == frozenset({"RISK"})
    assert rules.admitted_quantity_bases == frozenset({"RISK"})
    assert rules.authorized_axes == (
        AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value="paper"),
        AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
        AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
    )
    assert rules.action_class_shape == {
        (ActionClass.NEW_LONG, "LONG"): ActionClassShape(
            side="BUY", position_effect="OPEN"
        ),
        (ActionClass.NEW_SHORT, "SHORT"): ActionClassShape(
            side="SELL", position_effect="OPEN"
        ),
    }
    assert rules.effect_dimensions == ()


def test_load_order_construction_policy_construction_missing_block_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(construction="")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="construction"):
        load_order_construction_policy(path, scheme=SCHEME)


@pytest.mark.parametrize(
    "field",
    ["max_quantity", "min_quantity", "lot_size", "risk_budget", "per_unit_risk"],
)
def test_load_order_construction_policy_construction_sizing_missing_leaf_refused(
    tmp_path: Path, field: str
) -> None:
    default = ocp_yaml()
    text, count = re.subn(
        rf"^(\s*){field}: .*\n", "", default, count=1, flags=re.MULTILINE
    )
    assert count == 1
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match=field):
        load_order_construction_policy(path, scheme=SCHEME)


@pytest.mark.parametrize(
    "field",
    ["max_quantity", "min_quantity", "lot_size", "risk_budget", "per_unit_risk"],
)
def test_load_order_construction_policy_construction_sizing_null_leaf_refused(
    tmp_path: Path, field: str
) -> None:
    default = ocp_yaml()
    text, count = re.subn(
        rf"^(\s*{field}): .*$", r"\1: null", default, count=1, flags=re.MULTILINE
    )
    assert count == 1
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match=field):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_max_notional_null_accepted(
    tmp_path: Path,
) -> None:
    """Team-lead directive: an optional ceiling — ``null`` is legitimate, NOT a refusal
    (``egressgw/construction.py:525`` guards it ``is not None``)."""
    path = write_fixture_ocp(tmp_path)  # default already carries max_notional: null
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.construction_rules.sizing_bound.max_notional is None


def test_load_order_construction_policy_construction_max_notional_int_accepted(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace("max_notional: null", "max_notional: 5000")
    path = write_fixture_ocp(tmp_path, text)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.construction_rules.sizing_bound.max_notional == Decimal(5000)


def test_load_order_construction_policy_construction_lot_rounding_unknown_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        'lot_rounding: "EXACT_MULTIPLE_REQUIRED"', 'lot_rounding: "ROUND_HALF_UP"'
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="LotRoundingPolicy"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_lot_rounding_null_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        'lot_rounding: "EXACT_MULTIPLE_REQUIRED"', "lot_rounding: null"
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="lot_rounding"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_admitted_quantity_bases_tbd_refused(
    tmp_path: Path,
) -> None:
    """The load-bearing rule: ``admitted_quantity_bases: ["TBD"]`` must refuse the same way
    ``scope.accounts: ["TBD"]`` already does (team-lead directive)."""
    text = ocp_yaml().replace(
        'admitted_quantity_bases: ["RISK"]', 'admitted_quantity_bases: ["TBD"]'
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="admitted_quantity_bases"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_admitted_quantity_bases_empty_accepted(
    tmp_path: Path,
) -> None:
    """An empty (but present, non-TBD) admitted set is a LOADABLE, always-denying state
    (SizingBound's own docstring: "∅ authorizes nothing") — not a load-time refusal; only the
    literal template placeholder ``"TBD"`` refuses at load."""
    text = ocp_yaml().replace(
        'admitted_quantity_bases: ["RISK"]', "admitted_quantity_bases: []"
    )
    path = write_fixture_ocp(tmp_path, text)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.construction_rules.admitted_quantity_bases == frozenset()


@pytest.mark.parametrize("axis_token", ["QUANTITY", "PRICE", "UNIT"])
def test_load_order_construction_policy_construction_axes_derived_axis_refused(
    tmp_path: Path, axis_token: str
) -> None:
    """A :data:`~tos.egressgw.DERIVED_AXES` member declared under ``axes`` refuses at load
    (team-lead directive: catch it here, not only later at the kernel envelope validator).
    """
    text = ocp_yaml().replace(
        '    axes:\n      - axis: "TIF"\n        value: "DAY"\n',
        f'    axes:\n      - axis: "{axis_token}"\n        value: "5"\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="derived axis"):
        load_order_construction_policy(path, scheme=SCHEME)


@pytest.mark.parametrize(
    "axis_token, value", [("ORDER_TYPE", "MARKET"), ("ENVIRONMENT", "live")]
)
def test_load_order_construction_policy_construction_axes_restated_refused(
    tmp_path: Path, axis_token: str, value: str
) -> None:
    """ENVIRONMENT/ORDER_TYPE are derived from ``scope`` — restating either under
    ``_runtime.construction.axes`` refuses rather than risk the two silently drifting apart.
    """
    text = ocp_yaml().replace(
        '    axes:\n      - axis: "TIF"\n        value: "DAY"\n',
        f'    axes:\n      - axis: "{axis_token}"\n        value: "{value}"\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="restates"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_axes_unknown_token_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace('axis: "TIF"', 'axis: "NOPE"')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ConformanceAxis"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_action_class_shape_unknown_token_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace("      NEW_LONG:\n", "      NOPE:\n")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="ActionClass"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_action_class_shape_not_a_mapping_refused(
    tmp_path: Path,
) -> None:
    """``action_class_shape.<ActionClass>`` must itself be a mapping (direction -> shape), not
    a flattened ``{side, position_effect}`` — the (ActionClass, direction) key shape (contract
    amendment 2026-09-16) requires the extra nesting level."""
    text = ocp_yaml().replace(
        '      NEW_LONG:\n        LONG: {side: "BUY", position_effect: "OPEN"}\n',
        '      NEW_LONG: {side: "BUY", position_effect: "OPEN"}\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="mapping"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_action_class_shape_new_long_without_new_short_refused(
    tmp_path: Path,
) -> None:
    """Long/short symmetry is a repo non-negotiable (CLAUDE.md) — a mapping with
    ``(NEW_LONG, LONG)`` but no ``(NEW_SHORT, SHORT)`` mirror refuses, naming both (team-lead
    directive). This is the CROSS-class mirror: NEW_LONG/NEW_SHORT are separate ActionClass
    members, each single-direction by construction."""
    text = ocp_yaml().replace(
        '      NEW_SHORT:\n        SHORT: {side: "SELL", position_effect: "OPEN"}\n',
        "",
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match=r"NEW_LONG.*NEW_SHORT"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_action_class_shape_new_short_without_new_long_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        '      NEW_LONG:\n        LONG: {side: "BUY", position_effect: "OPEN"}\n',
        "",
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match=r"NEW_SHORT.*NEW_LONG"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_action_class_shape_close_long_without_close_short_refused(
    tmp_path: Path,
) -> None:
    """The WITHIN-class mirror (contract amendment 2026-09-16, the fix for lane A's original
    finding): ``ActionClass.CLOSE`` has one member for both a long-close and a short-close, so a
    document declaring ``(CLOSE, LONG)`` without its ``(CLOSE, SHORT)`` mirror must refuse too —
    this mirror pair did not exist to violate before the amendment (mutation proof)."""
    text = ocp_yaml().replace(
        "    action_class_shape:\n"
        '      NEW_LONG:\n        LONG: {side: "BUY", position_effect: "OPEN"}\n'
        '      NEW_SHORT:\n        SHORT: {side: "SELL", position_effect: "OPEN"}\n',
        "    action_class_shape:\n"
        '      NEW_LONG:\n        LONG: {side: "BUY", position_effect: "OPEN"}\n'
        '      NEW_SHORT:\n        SHORT: {side: "SELL", position_effect: "OPEN"}\n'
        '      CLOSE:\n        LONG: {side: "SELL", position_effect: "CLOSE"}\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match=r"CLOSE, LONG.*CLOSE, SHORT"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_action_class_shape_close_both_directions_accepted(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        "    action_class_shape:\n"
        '      NEW_LONG:\n        LONG: {side: "BUY", position_effect: "OPEN"}\n'
        '      NEW_SHORT:\n        SHORT: {side: "SELL", position_effect: "OPEN"}\n',
        "    action_class_shape:\n"
        '      NEW_LONG:\n        LONG: {side: "BUY", position_effect: "OPEN"}\n'
        '      NEW_SHORT:\n        SHORT: {side: "SELL", position_effect: "OPEN"}\n'
        '      CLOSE:\n        LONG: {side: "SELL", position_effect: "CLOSE"}\n'
        '        SHORT: {side: "BUY", position_effect: "CLOSE"}\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.construction_rules.action_class_shape[
        (ActionClass.CLOSE, "LONG")
    ] == (ActionClassShape(side="SELL", position_effect="CLOSE"))
    assert loaded.construction_rules.action_class_shape[
        (ActionClass.CLOSE, "SHORT")
    ] == (ActionClassShape(side="BUY", position_effect="CLOSE"))


def test_load_order_construction_policy_construction_effect_dimensions_unknown_basis_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        "    effect_dimensions: []\n",
        '    effect_dimensions:\n      - dimension_id: "d1"\n        basis: "NOPE"\n'
        '        unit: "KRW"\n        scale: "1"\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="EffectBasis"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_construction_effect_dimensions_well_formed(
    tmp_path: Path,
) -> None:
    text = ocp_yaml().replace(
        "    effect_dimensions: []\n",
        '    effect_dimensions:\n      - dimension_id: "notional"\n        basis: "NOTIONAL"\n'
        '        unit: "KRW"\n        scale: "1"\n',
    )
    path = write_fixture_ocp(tmp_path, text)
    loaded = load_order_construction_policy(path, scheme=SCHEME)
    assert loaded.construction_rules.effect_dimensions == (
        EffectDimensionSpec(
            dimension_id="notional", basis=EffectBasis.NOTIONAL, unit="KRW", scale="1"
        ),
    )


def test_load_order_construction_policy_scope_order_types_empty_refused(
    tmp_path: Path,
) -> None:
    """``order_types`` joined the OCP single-live-scope singleton set in the (a′) wave — the
    ``ORDER_TYPE`` authorized axis is derived from it, so it needs exactly one value like
    ``environments``/``accounts`` already do."""
    text = ocp_yaml(order_types="[]")
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="EXACTLY one"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_scope_order_types_multiple_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(order_types='["LIMIT", "MARKET"]')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="EXACTLY one"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_load_order_construction_policy_scope_order_types_named_tbd_refused(
    tmp_path: Path,
) -> None:
    text = ocp_yaml(order_types='["TBD"]')
    path = write_fixture_ocp(tmp_path, text)
    with pytest.raises(VenuePolicyConfigError, match="named-TBD"):
        load_order_construction_policy(path, scheme=SCHEME)


def test_real_paper_ocp_carries_the_new_generation(tmp_path: Path) -> None:
    """Pins the (a′) wave's generation bump on the shipped file itself (mirrors
    ``tests/compose/test_deploy_policies.py``'s own "real policy files" pins)."""
    raw = yaml.safe_load(_REAL_OCP_PATH.read_text(encoding="utf-8"))
    assert raw["policy_generation"] == 2
    assert raw["_model_view"]["policy_generation"] == 2
    assert raw["_runtime"]["construction"]["sizing"]["admitted_quantity_bases"] == [
        "TBD"
    ]


def test_real_paper_ocp_refuses_on_admitted_quantity_bases_tbd_even_when_scope_is_filled(
    tmp_path: Path,
) -> None:
    """The shipped ``config/tos_runtime/paper/order_construction_policy.yaml`` pins its own
    intentional not-yet-bootable state (OCP sizing proposal §4 ②): even with the
    scope.accounts/scope.instruments operator-fill gate satisfied, the document still refuses
    to load — now for admitted_quantity_bases, not merely for the scope gate this file already
    pinned before the (a′) wave."""
    raw = yaml.safe_load(_REAL_OCP_PATH.read_text(encoding="utf-8"))
    assert raw["scope"]["accounts"] == ["TBD"]
    assert raw["scope"]["instruments"] == ["TBD"]
    raw["scope"]["accounts"] = ["acct-x"]
    raw["scope"]["instruments"] = ["inst-x"]
    text = yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
    path = tmp_path / "order_construction_policy.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(VenuePolicyConfigError, match="admitted_quantity_bases"):
        load_order_construction_policy(path, scheme=SCHEME)
