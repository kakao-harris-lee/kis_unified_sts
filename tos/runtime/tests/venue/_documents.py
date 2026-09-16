"""Shared Venue Constraint Policy / Order Construction Policy INSTANCE document builders
(TOS venue constraint service wave, plan §2 decisions 1/2/6, ``docs/plans/
2026-09-15-tos-venue-constraint-service-plan.md``).

Factored out of ``tests/venue/conftest.py`` (team-lead directive, lane b compose wiring dispatch
2026-09-15) purely so :mod:`tests.compose.conftest` can reuse the SAME template-shaped document
builders rather than re-typing the full template key set a second time — the venue/compose
suites are otherwise independent (module docstring of ``tests/venue/conftest.py``'s own
``FixedKeyProvider`` cites the general "cross-suite imports are forbidden" convention for
re-declared test doubles; this module is the deliberate, named exception for document
CONTENT, not doubles, because the two suites must agree on exactly what a loadable INSTANCE
document looks like).

The YAML VALUES below are FIXTURE DATA authored for these test suites only — they are NOT the
operator-signed production policy (plan §6 ②, still an open operator decision). Each fixture
copies the FULL key set of ``tos-spec/src/part-1-foundation/verification/
VENUE-CONSTRAINT-POLICY-template.yaml`` / ``.../ORDER-CONSTRUCTION-POLICY-template.yaml`` (every
rule-list key present as ``[]``, ``authority``/``evidence`` present as their template-shaped
mappings) plus the two sibling ``_model_view``/``_runtime`` blocks the loader actually reads
kernel-typed content from (see ``tos_runtime/venue/config.py``'s own module docstring for the
discipline this mirrors, :mod:`tos_runtime.brokercap.instance`'s ``_model_view`` convention).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalizationScheme, get_scheme

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
    environment: str = "paper",
    broker: str = "kis",
    account: str = "acct-1",
    venue: str = "krx",
    market_segment: str = "futures",
    instrument: str = "K200F",
    action_classes: str = '["NEW_LONG", "NEW_SHORT"]',
    instrument_class: str = "krx-futures",
    quantity_unit: str = "CONTRACTS",
    currency: str = "KRW",
    price_min: str = "100",
    price_max: str = "500",
    tick_size: str = "5",
    lot_size: str = "1",
    min_quantity: str = "1",
    max_quantity: str = "null",
    admitting_phases: str = '["REGULAR"]',
    admitting_phases_short: str | None = None,
) -> str:
    """The standard fixture ``venue_constraint_policy.yaml`` INSTANCE
    document — a full VENUE-CONSTRAINT-POLICY-template.yaml key set plus
    ``_model_view``/``_runtime``. Every numeric bound present EXCEPT
    ``max_quantity`` (left ``null`` by default, the loader's "honestly
    nullable" discipline), one ``NEW_LONG``/``NEW_SHORT`` admitting-phase
    rule each (independently overridable via ``admitting_phases``/
    ``admitting_phases_short``), no dependency edges.

    Every scope/``_runtime`` coordinate is independently overridable (added for
    ``tests.compose.conftest`` reuse, 2026-09-15 — the compose suite's own account/instrument/
    environment/instrument-class fixture constants differ from this module's own defaults, and
    the loader's scope cross-check requires an exact match)."""
    short_phases = (
        admitting_phases if admitting_phases_short is None else admitting_phases_short
    )
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
          environments: ["{environment}"]
          safety_cells: []
          brokers: ["{broker}"]
          accounts: ["{account}"]
          venues: ["{venue}"]
          market_segments: ["{market_segment}"]
          instruments: ["{instrument}"]
          contracts: []
          action_classes: {action_classes}
        """)
    model_view = textwrap.dedent(f"""\
        _model_view:
          admitting_phase_rules:
            - action: "NEW_LONG"
              admitting_phases: {admitting_phases}
            - action: "NEW_SHORT"
              admitting_phases: {short_phases}
          required_constraint_classes: []
          shape_constraints:
            price_min: {price_min}
            price_max: {price_max}
            tick_size: {tick_size}
            lot_size: {lot_size}
            min_quantity: {min_quantity}
            max_quantity: {max_quantity}
            allowed_order_types: ["LIMIT"]
            allowed_tifs: ["DAY"]
            allowed_sides: ["BUY", "SELL"]
            allowed_position_effects: ["OPEN", "CLOSE"]
          dependency_closure:
            edges: []
        _runtime:
          instrument_class: "{instrument_class}"
          quantity_unit: "{quantity_unit}"
          currency: "{currency}"
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
    environment: str = "paper",
    broker: str = "kis",
    account: str = "acct-1",
    instrument: str = "K200F",
    action_classes: str = "[]",
    order_types: str = '["LIMIT"]',
    construction: str | None = None,
) -> str:
    """The standard fixture ``order_construction_policy.yaml`` INSTANCE
    document — a full ORDER-CONSTRUCTION-POLICY-template.yaml key set plus
    ``_model_view``/``_runtime``.

    ``order_types`` defaults to a single-entry list (``["LIMIT"]``), not the
    template's own empty default: the (a′) wave's loader now DERIVES the
    ``ORDER_TYPE`` authorized-axis binding from ``scope.order_types`` (a
    single-live-scope singleton, like ``environments``/``accounts``), so an
    empty list would refuse to load — same reason ``environment``/``account``
    already default to non-empty singletons above.

    ``construction`` is the raw YAML text for the ``_runtime.construction``
    block (2-space-indented, as it appears directly under ``_runtime:``,
    fixture data only — not the operator-adopted production values, see this
    module's own docstring). Defaults to a well-formed block so every
    existing ``ocp_yaml()`` caller keeps loading without having to know about
    the (a′) wave; override wholesale (including ``""`` to omit the block
    entirely) for tests that exercise ``_runtime.construction`` itself."""
    version = (
        SCHEME.version if canonicalization_version is None else canonicalization_version
    )
    mv_generation = (
        policy_generation
        if model_view_policy_generation is None
        else model_view_policy_generation
    )
    if construction is None:
        construction = textwrap.indent(
            textwrap.dedent("""\
                construction:
                  sizing:
                    # max_quantity/min_quantity/lot_size are CROSS-CHECKED at boot against the
                    # venue constraint policy's own shape_constraints (lane B's
                    # _cross_check_ocp_sizing_bound, tos_runtime/compose/_riskstate_wiring.py):
                    # OCP max_quantity must not EXCEED the venue's, OCP min_quantity must not be
                    # BELOW the venue's, and OCP lot_size must be a whole multiple of the
                    # venue's. tests/compose/conftest.py's own venue_policy_yaml() fixture (the
                    # ONE both suites' e2e tests boot against) sets
                    # lot_size=2/min_quantity=2/max_quantity=100 — these three values were
                    # picked to satisfy that cross-check (95 boot refusals, PR #719 delta
                    # review, surfaced the pre-wave disagreement: OCP sizing did not exist
                    # before this wave, so nobody had ever checked the two fixtures agreed).
                    # max_quantity is deliberately NOT narrower than the venue's: this is the
                    # SHARED baseline every compose e2e test boots against, and a narrower OCP
                    # ceiling here would silently cap the derived quantity in every one of
                    # them — a test asserting a specific derived value would then be pinning
                    # the OCP ceiling by accident, not the thing it means to pin (integration
                    # review, 2026-09-16: lane C's own test_derived_quantity_reaches_the_fold_
                    # not_the_literal expected 20 and got 10, capped by this fixture's OCP
                    # bound rather than the venue's [2, 100] range its comment reasons from).
                    # A test that specifically wants a narrower OCP should override this
                    # parameter/construction locally, never shrink the shared default. If you
                    # change ONE of these two fixtures' sizing values, change the other too, or
                    # the cross-check will refuse every compose e2e boot.
                    max_quantity: 100
                    min_quantity: 2
                    lot_size: 2
                    lot_rounding: "EXACT_MULTIPLE_REQUIRED"
                    risk_budget: 100
                    per_unit_risk: 10
                    max_notional: null
                    admitted_quantity_bases: ["RISK"]
                  axes:
                    - axis: "TIF"
                      value: "DAY"
                    - axis: "DIRECTION"
                      value: "LONG"
                  action_class_shape:
                    NEW_LONG:
                      LONG: {side: "BUY", position_effect: "OPEN"}
                    NEW_SHORT:
                      SHORT: {side: "SELL", position_effect: "OPEN"}
                  effect_dimensions:
                    # dimension_id MEASURED off aggregate_risk_policy.yaml's own
                    # _runtime.dimension_ids (the composed-id spelling RCL actually looks up
                    # by, rcl/predicates.py:104-105 / riskstate/service.py:145-151) --
                    # NOT the unprefixed _model_view.governed_dimensions spelling (proposal
                    # 2026-09-16-tos-ocp-effect-dimensions-proposal.md §2.1). A wrong spelling
                    # here passes step 5 while the capacity lookup finds nothing -- the exact
                    # phantom the withdrawn fixture-injected "notional"/"units" values were.
                    - dimension_id: "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
                      basis: "QUANTITY"
                      unit: "CONTRACTS"
                      scale: "1"
                """),
            "  ",
        )
    head = textwrap.dedent(f"""\
        artifact_type: ORDER_CONSTRUCTION_POLICY
        schema_version: "1.0-DRAFT"
        policy_id: "{policy_id}"
        policy_generation: {policy_generation}
        construction_generation: {construction_generation}
        canonical_digest: {canonical_digest}
        status: {status}
        effective_from: null
        review_due: null
        scope:
          environments: ["{environment}"]
          safety_cells: []
          brokers: ["{broker}"]
          accounts: ["{account}"]
          venues: []
          market_segments: []
          instruments: ["{instrument}"]
          contracts: []
          action_classes: {action_classes}
          order_types: {order_types}
        """)
    tail_blocks = textwrap.dedent(f"""\
        _model_view:
          policy_generation: {mv_generation}
          policy_version: "{policy_version}"
        _runtime:
          canonicalization_version: "{version}"
          wire_codec: {wire_codec}
        """)
    return head + _OCP_TEMPLATE_TAIL + tail_blocks + construction


def write_fixture_venue_policy(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(venue_policy_yaml() if text is None else text, encoding="utf-8")
    return path


def write_fixture_ocp(tmp_path: Path, text: str | None = None) -> Path:
    path = tmp_path / "order_construction_policy.yaml"
    path.write_text(ocp_yaml() if text is None else text, encoding="utf-8")
    return path
