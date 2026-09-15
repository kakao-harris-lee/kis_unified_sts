"""Hermetic fixtures for tos_runtime.venue tests (tmp_path only, no external
network, no ambient env — same discipline as tos/runtime/tests/calendar
/conftest.py and tos/runtime/tests/compose/conftest.py).

The venue/OCP YAML VALUES below are FIXTURE DATA authored for this test
suite only — they are NOT the operator-signed production policy (plan §6
②, still an open operator decision). Each fixture copies the FULL key set
of ``tos-spec/src/part-1-foundation/verification/VENUE-CONSTRAINT-POLICY-
template.yaml`` / ``.../ORDER-CONSTRUCTION-POLICY-template.yaml`` (every
rule-list key present as ``[]``, ``authority``/``evidence`` present as their
template-shaped mappings) plus the two sibling ``_model_view``/``_runtime``
blocks the loader actually reads kernel-typed content from (team-lead
correction, 2026-09-15 — see ``tos_runtime/venue/config.py``'s own module
docstring for the discipline this mirrors,
:mod:`tos_runtime.brokercap.instance`'s ``_model_view`` convention).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore

#: The one registered kernel canonicalization scheme (mirrors
#: tos_runtime.compose._wiring's own ``_SCHEME`` constant).
SCHEME: CanonicalizationScheme = get_scheme(EV_L1_PROVISIONAL_VERSION)

FIXTURE_POLICY_ID = "vcp-fixture-1"
FIXTURE_POLICY_GENERATION = 1
FIXTURE_OCP_POLICY_ID = "ocp-fixture-1"
FIXTURE_OCP_POLICY_GENERATION = 1
FIXTURE_OCP_POLICY_VERSION = "1.0.0"

#: Copied verbatim (key order and all) from
#: ``tos-spec/src/part-1-foundation/verification/VENUE-CONSTRAINT-POLICY-template.yaml``'s
#: own rule-list run, ``authority``, and ``evidence`` blocks — the part of
#: the document the loader only checks for shape/presence, never interprets.
_VENUE_TEMPLATE_TAIL = textwrap.dedent("""\
    approved_sources: []
    source_continuity_rules: []
    session_phase_state_machines: []
    halt_suspension_and_tradability_rules: []
    instrument_and_contract_rules: []
    price_band_tick_and_lot_rules: []
    quantity_notional_and_rounding_rules: []
    order_type_time_in_force_and_routing_rules: []
    account_permission_rules: []
    margin_collateral_and_buying_power_rules: []
    borrow_locate_and_short_sale_rules: []
    settlement_currency_and_expiration_rules: []
    broker_capability_requirements: []
    corroboration_and_independence_rules: []
    dependency_and_invalidation_rules: []
    conservative_failure_responses: []
    protective_only_restrictions: []
    residual_risks: []
    authority:
      grants_approval: false
      creates_capacity: false
      releases_capacity: false
      creates_live_authorization: false
      creates_protective_classification: false
      creates_transmission_capability: false
      permits_broker_transmission: false
      clears_halt: false
      permits_rearm: false
      permits_automatic_rearm: false
    evidence:
      activation_record_id: TBD
      independent_review_id: TBD
      evidence_location: TBD
    """)

#: The equivalent template-tail for ORDER-CONSTRUCTION-POLICY-template.yaml.
_OCP_TEMPLATE_TAIL = textwrap.dedent("""\
    intent_schema_versions: []
    authorized_construction_envelope_schema_versions: []
    canonical_broker_command_schema_versions: []
    economic_effect_envelope_schema_versions: []
    order_conformance_proof_schema_versions: []
    field_presence_and_mapping_rules: []
    account_instrument_contract_and_route_rules: []
    direction_side_and_position_effect_rules: []
    unit_multiplier_currency_and_numeric_rules: []
    price_tick_lot_quantity_and_rounding_rules: []
    order_type_time_in_force_expiration_and_mode_rules: []
    split_aggregation_retry_cancel_amend_and_replace_rules: []
    canonicalization_and_duplicate_field_rules: []
    serializer_sdk_signer_and_actual_outbound_rules: []
    compiler_dependency_and_compatibility_rules: []
    economic_effect_and_capacity_rules: []
    invalidation_and_failure_responses: []
    common_mode_requirements: []
    residual_risks: []
    approved_by: []
    authority:
      grants_approval: false
      creates_capacity: false
      releases_capacity: false
      creates_live_authorization: false
      creates_protective_classification: false
      creates_transmission_capability: false
      permits_broker_transmission: false
      clears_halt: false
      permits_rearm: false
      permits_automatic_rearm: false
    evidence:
      activation_record_id: TBD
      independent_review_id: TBD
      evidence_location: TBD
    """)


def venue_policy_yaml(
    *,
    policy_id: str = FIXTURE_POLICY_ID,
    policy_generation: int = FIXTURE_POLICY_GENERATION,
    status: str = "ISSUED",
    canonical_digest: str = "TBD",
    max_quantity: str = "null",
    admitting_phases: str = '["REGULAR"]',
    action_classes: str = '["NEW_LONG", "NEW_SHORT"]',
) -> str:
    """The standard fixture ``venue_constraint_policy.yaml`` INSTANCE
    document — a full VENUE-CONSTRAINT-POLICY-template.yaml key set plus
    ``_model_view``/``_runtime``. Every numeric bound present EXCEPT
    ``max_quantity`` (left ``null`` by default, the loader's "honestly
    nullable" discipline), one ``NEW_LONG``/``NEW_SHORT`` admitting-phase
    rule each, no dependency edges."""
    head = textwrap.dedent(f"""\
        artifact_type: VENUE_CONSTRAINT_POLICY
        schema_version: "1.0-DRAFT"
        policy_id: "{policy_id}"
        policy_generation: {policy_generation}
        canonical_digest: {canonical_digest}
        status: {status}
        approved_by: ["ops-owner"]
        effective_from: "2026-09-15"
        review_due: null
        scope:
          environments: ["paper"]
          safety_cells: []
          brokers: ["kis"]
          accounts: ["acct-1"]
          venues: ["krx"]
          market_segments: ["futures"]
          instruments: ["K200F"]
          contracts: []
          action_classes: {action_classes}
        """)
    model_view = textwrap.dedent(f"""\
        _model_view:
          admitting_phase_rules:
            - action: "NEW_LONG"
              admitting_phases: {admitting_phases}
            - action: "NEW_SHORT"
              admitting_phases: {admitting_phases}
          required_constraint_classes: []
          shape_constraints:
            price_min: 100
            price_max: 500
            tick_size: 5
            lot_size: 1
            min_quantity: 1
            max_quantity: {max_quantity}
            allowed_order_types: ["LIMIT"]
            allowed_tifs: ["DAY"]
            allowed_sides: ["BUY", "SELL"]
            allowed_position_effects: ["OPEN", "CLOSE"]
          dependency_closure:
            edges: []
        _runtime:
          instrument_class: "krx-futures"
          quantity_unit: "CONTRACTS"
          currency: "KRW"
        """)
    return head + _VENUE_TEMPLATE_TAIL + model_view


def ocp_yaml(
    *,
    policy_id: str = FIXTURE_OCP_POLICY_ID,
    policy_generation: int = FIXTURE_OCP_POLICY_GENERATION,
    construction_generation: str = "1",
    status: str = "ISSUED",
    canonical_digest: str = "TBD",
    model_view_policy_generation: int | None = None,
    policy_version: str = FIXTURE_OCP_POLICY_VERSION,
    canonicalization_version: str | None = None,
    wire_codec: str = "null",
) -> str:
    """The standard fixture ``order_construction_policy.yaml`` INSTANCE
    document — a full ORDER-CONSTRUCTION-POLICY-template.yaml key set plus
    ``_model_view``/``_runtime``."""
    version = (
        SCHEME.version if canonicalization_version is None else canonicalization_version
    )
    mv_generation = (
        policy_generation
        if model_view_policy_generation is None
        else model_view_policy_generation
    )
    head = textwrap.dedent(f"""\
        artifact_type: ORDER_CONSTRUCTION_POLICY
        schema_version: "1.0-DRAFT"
        policy_id: "{policy_id}"
        policy_generation: {policy_generation}
        construction_generation: {construction_generation}
        canonical_digest: {canonical_digest}
        status: {status}
        scope:
          environments: ["paper"]
          safety_cells: []
          brokers: ["kis"]
          accounts: ["acct-1"]
          venues: []
          market_segments: []
          instruments: ["K200F"]
          contracts: []
          action_classes: []
          order_types: []
        """)
    tail_blocks = textwrap.dedent(f"""\
        _model_view:
          policy_generation: {mv_generation}
          policy_version: "{policy_version}"
        _runtime:
          canonicalization_version: "{version}"
          wire_codec: {wire_codec}
        """)
    return head + _OCP_TEMPLATE_TAIL + tail_blocks


def write_fixture_venue_policy(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(venue_policy_yaml() if text is None else text, encoding="utf-8")
    return path


def write_fixture_ocp(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "order_construction_policy.yaml"
    path.write_text(ocp_yaml() if text is None else text, encoding="utf-8")
    return path


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed
    bytes (mirrors ``tos/runtime/tests/calendar/test_owner.py``'s own
    re-declared double; cross-suite imports are forbidden per that module's
    convention)."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-venue-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-venue-suite"


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(tmp_path: Path, key_provider: KeyProvider):
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


def kind_count(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    return sum(1 for entry in evidence_store.iter_entry_meta() if entry.kind == kind)
