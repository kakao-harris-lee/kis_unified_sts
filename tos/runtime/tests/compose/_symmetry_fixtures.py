"""Mirrored long/short compose fixtures for the W5 §2 decision 8 symmetry suite (lane f4).

Every construct here is a **mirror** of an existing ``tests/compose/_fixtures.py`` (``fx``)
builder — same magnitudes, same instrument/account/decision-class, same crossing event — with
only the side-bearing fields flipped: ``ActionClass.NEW_LONG`` -> ``NEW_SHORT``, ``"BUY"`` ->
``"SELL"``, ``TargetSpec.direction`` ``"LONG"`` -> ``"SHORT"``. Nothing here re-derives a NEW
concept of side; it is the exact set of fields TOS Phase 5 W5 plan §2 decision 8 names
("픽스처 side·action_class·venue_shape_constraints.allowed_sides 미러"), extended to the two
fixtures that would otherwise silently disagree with a flipped order shape: the Order
Construction Policy's own authorized ``DIRECTION``/``SIDE`` axis bindings (``proposed_envelope``)
and the Venue Constraint Policy's admitting-phase rule (keyed by the exact ``ActionClass``,
``tos.venue.state.session_phase_admits``) — both must admit the mirrored action or the SHORT run
would halt at a different step than the LONG one, which would make this suite's own "identical
verdict sequence" assertion vacuous rather than a real symmetry proof.

Does not import ``tos.tests`` (kernel test-private modules) and does not copy
``_fixtures.py``'s content wholesale — it imports the side-agnostic builders directly (``fx``'s
own account/instrument/pricing/sizing fixtures do not depend on side at all) and re-derives only
the handful of builders that do.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import (
    VALUE_NAMESPACE,
    AuthoredStrategy,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.egressgw import ProposedConstructionEnvelope
from tos.ioc import AxisBinding, ConformanceAxis
from tos.venue import (
    ActionClass,
    ActionPhaseAdmission,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)
from tos_runtime.compose.root import ConstructionConfig

from . import _fixtures as fx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: The mirrored side's own identity suffix ("short") — every SHORT-side artifact id below is the
#: LONG one's id with this suffix appended, so a stray id COLLISION between the two sides (which
#: would make the pair not genuinely independent) is visible on sight rather than needing a diff.
_SHORT_SUFFIX = "-short"


def _value_ref(field_key: str) -> Operand:
    """Re-derived locally rather than reaching into ``fx``'s underscore-private helper (same
    one-liner :func:`~._fixtures._value_ref` builds)."""
    return Operand(ref=("capsule", VALUE_NAMESPACE, field_key))


def mirrored_policy() -> DecisionPolicy:
    """``close < lower_band`` -> ``SHORT``/``OPEN`` — the exact same trigger
    :func:`~._fixtures.band_reversion_policy` uses, so the SAME crossing event
    (:func:`~._fixtures.crossing_event`) drives both sides through the identical DSL branch; only
    the fired :class:`~tos.dsl.records.TargetSpec` differs, in ``direction`` alone."""
    entry = Decision(
        kind=DecisionKind.ACTION,
        rationale="close pierced the lower band — compose e2e SHORT mirror",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=fx.ACCOUNT,
            instrument=fx.INSTRUMENT,
            direction="SHORT",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="compose-e2e-short",
            rationale="close pierced the lower band — compose e2e SHORT mirror",
        ),
    )
    hold = Decision(
        kind=DecisionKind.NO_ACTION,
        rationale="close is inside the band — hold, no proposal",
    )
    return DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=_value_ref("close"),
                        op=CompareOp.LT,
                        right=_value_ref("lower_band"),
                    ),
                ),
                decision=entry,
            ),
        ),
        default=hold,
    )


def mirrored_strategy() -> AuthoredStrategy:
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-compose",
        config_binding_version="cfg-bind-compose",
        policy=mirrored_policy(),
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def mirrored_strategy_mapping() -> dict[str, object]:
    """The raw-mapping equivalent of :func:`mirrored_strategy`, mirroring
    :func:`~._fixtures.band_reversion_strategy_mapping` field-for-field."""
    return {
        "dsl_version": "dsl-compose",
        "config_binding_version": "cfg-bind-compose",
        "policy": {
            "rules": [
                {
                    "all_of": [
                        {
                            "left": {"ref": ["capsule", VALUE_NAMESPACE, "close"]},
                            "op": "LT",
                            "right": {
                                "ref": ["capsule", VALUE_NAMESPACE, "lower_band"]
                            },
                        }
                    ],
                    "decision": {
                        "kind": "ACTION",
                        "rationale": "close pierced the lower band — compose e2e SHORT mirror",
                        "target": {
                            "kind": "ACTION",
                            "account": fx.ACCOUNT,
                            "instrument": fx.INSTRUMENT,
                            "direction": "SHORT",
                            "position_effect": "OPEN",
                            "quantity_basis": "RISK",
                            "edge_or_confidence": "compose-e2e-short",
                            "rationale": "close pierced the lower band — compose e2e SHORT mirror",
                        },
                    },
                }
            ],
            "default": {
                "kind": "NO_ACTION",
                "rationale": "close is inside the band — hold, no proposal",
            },
        },
    }


#: The mirrored strategy file name — distinct from :data:`~._fixtures.BAND_STRATEGY_FILE_NAME` so
#: a LONG-side ``strategies/`` directory and a SHORT-side one never collide if a caller ever
#: wanted both on disk at once (today's tests use one runtime per side, never both at once).
MIRRORED_STRATEGY_FILE_NAME = "band-short.strategy.yaml"


def write_mirrored_strategy_file(config_dir: Path) -> Path:
    """Write :func:`mirrored_strategy_mapping` — the SHORT-side counterpart of
    :func:`~._fixtures.write_band_strategy_file`."""
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(exist_ok=True)
    path = strategies_dir / MIRRORED_STRATEGY_FILE_NAME
    path.write_text(
        yaml.safe_dump(mirrored_strategy_mapping(), sort_keys=False),
        encoding="utf-8",
    )
    return path


def mirrored_proposed_envelope() -> ProposedConstructionEnvelope:
    """:func:`~._fixtures.proposed_envelope`, mirrored: the ``DIRECTION``/``SIDE`` authorized axis
    bindings are the ONE place besides ``order_shape``/``venue_shape_constraints`` that carry side
    content — an un-mirrored envelope here would desynchronize the Order Construction Policy's
    conformance axis bindings from the mirrored order shape, and the run would halt at a
    DIFFERENT step than the LONG run (a conformance mismatch, not a venue admissibility one),
    which is exactly the kind of "looks symmetric but silently isn't" this suite exists to catch.
    """
    return fx.proposed_envelope(
        policy_binding_id="ocp-compose-short",
        authorized_axis_bindings=(
            AxisBinding(axis=ConformanceAxis.ACCOUNT, value=fx.ACCOUNT),
            AxisBinding(axis=ConformanceAxis.INSTRUMENT, value=fx.INSTRUMENT),
            AxisBinding(axis=ConformanceAxis.DIRECTION, value="SHORT"),
            AxisBinding(axis=ConformanceAxis.SIDE, value="SELL"),
            AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
            AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
            AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value="non-live-test"),
        ),
    )


def mirrored_venue_policy() -> VenueConstraintPolicy:
    """:func:`~._fixtures.venue_policy`, mirrored: the admitting-phase rule is keyed by
    ``ActionClass.NEW_SHORT`` instead of ``NEW_LONG`` — ``session_phase_admits`` looks the
    action class up **exactly** (``tos.venue.state.session_phase_admits``: "per-exact-phase and
    per-exact-action"), so a policy that still only admitted ``NEW_LONG`` would make the SHORT
    run INADMISSIBLE at step 3 while the LONG run is ADMISSIBLE — a real divergence this fixture
    exists to prevent, not paper over."""
    issued = VenueConstraintPolicy.issue(
        scheme=SCHEME,
        policy_id="vpol-compose" + _SHORT_SUFFIX,
        policy_generation=1,
        scope="scope-compose-short",
        admitting_phase_rules=(
            ActionPhaseAdmission(
                action=ActionClass.NEW_SHORT,
                admitting_phases=frozenset({fx.SESSION_PHASE}),
            ),
        ),
    )
    assert isinstance(issued, VenueConstraintPolicy)
    return issued


def mirrored_venue_snapshot() -> VenueConstraintSnapshot:
    """:func:`~._fixtures.venue_snapshot`, mirrored — ``policy_id``/``policy_generation`` point at
    :func:`mirrored_venue_policy`, never the LONG policy (a snapshot referencing the wrong policy
    would be its own, different kind of bug from an un-mirrored admitting rule)."""
    issued = VenueConstraintSnapshot.issue(
        scheme=SCHEME,
        snapshot_id="vsnap-compose" + _SHORT_SUFFIX,
        constraint_generation=1,
        policy_id="vpol-compose" + _SHORT_SUFFIX,
        policy_generation=1,
        observed_session_phase=fx.SESSION_PHASE,
    )
    assert isinstance(issued, VenueConstraintSnapshot)
    return issued


def mirrored_venue_admissible_decision() -> OrderAdmissibilityDecision:
    from tos.venue import OrderAdmissibilityResult

    issued = OrderAdmissibilityDecision.issue(
        scheme=SCHEME,
        decision_id="vdec-compose" + _SHORT_SUFFIX,
        decision_generation=1,
        result=OrderAdmissibilityResult.ADMISSIBLE,
    )
    assert isinstance(issued, OrderAdmissibilityDecision)
    return issued


def mirrored_order_shape() -> OrderShapeFields:
    """:func:`~._fixtures.order_shape` with ``side`` flipped to ``"SELL"`` — every OTHER field
    (price/quantity/order_type/tif/position_effect) is the identical value, so a divergence
    anywhere else in the run is a real asymmetry, not an artifact of two differently-shaped
    fixtures."""
    return fx.order_shape().model_copy(update={"side": "SELL"})


def mirrored_venue_shape_constraints() -> VenueShapeConstraints:
    """:func:`~._fixtures.venue_shape_constraints` with ``allowed_sides`` flipped to
    ``{"SELL"}`` — every other bound (price/tick/lot/quantity/order-type/tif/position-effect) is
    the identical value."""
    return fx.venue_shape_constraints().model_copy(
        update={"allowed_sides": frozenset({"SELL"})}
    )


def mirrored_construction_config() -> ConstructionConfig:
    """:func:`~._fixtures.construction_config`, mirrored (plan §2 decision 8: "픽스처
    side·action_class·venue_shape_constraints.allowed_sides 미러", extended to
    ``venue_policy``/``venue_snapshot``/``venue_decision``/``envelope`` per this module's own
    docstring — everything a flipped ``ActionClass``/side touches). ``envelope``/``price``/
    ``venue_constraint``/``instrument_class``/the two price-field keys are the exact SAME
    fx-derived values as the LONG side: nothing about sizing, pricing, or the calendar lookup key
    is side-dependent."""
    return ConstructionConfig(
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
        envelope=mirrored_proposed_envelope(),
        price=fx.admitted_price(),
        venue_constraint=fx.venue_quantity_constraint(),
        venue_snapshot=mirrored_venue_snapshot(),
        venue_policy=mirrored_venue_policy(),
        venue_decision=mirrored_venue_admissible_decision(),
        order_shape=mirrored_order_shape(),
        venue_shape_constraints=mirrored_venue_shape_constraints(),
        action_class=ActionClass.NEW_SHORT,
        instrument_class=fx.INSTRUMENT_CLASS,
        outbound_side="SELL",
        price_field_key=fx.PRICE_FIELD_KEY,
        shape_price_field_key=fx.PRICE_FIELD_KEY,
    )
