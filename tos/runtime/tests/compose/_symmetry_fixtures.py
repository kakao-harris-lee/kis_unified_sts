"""Mirrored long/short compose fixtures for the W5 §2 decision 8 symmetry suite (lane f4).

Every construct here is a **mirror** of an existing ``tests/compose/_fixtures.py`` (``fx``)
builder — same magnitudes, same instrument/account/decision-class, same crossing event — with
only the side-bearing fields flipped: ``ActionClass.NEW_LONG`` -> ``NEW_SHORT``, ``"BUY"`` ->
``"SELL"``, ``TargetSpec.direction`` ``"LONG"`` -> ``"SHORT"``. Nothing here re-derives a NEW
concept of side; it is the exact set of fields TOS Phase 5 W5 plan §2 decision 8 names
("픽스처 side·action_class·venue_shape_constraints.allowed_sides 미러"). ``action_class`` alone
now drives the Order Construction Policy's own authorized ``DIRECTION``/``SIDE`` derivation AND
the Venue Constraint Policy's admitting-phase rule (``tos.venue.state.session_phase_admits``) —
((a′) wave lane D removed the two hand-authored envelope/order-shape fixtures this module used
to carry SEPARATELY for exactly the same fact, see :func:`mirrored_construction_config`'s own
docstring) — both must admit the mirrored action or the SHORT run would halt at a different step
than the LONG one, which would make this suite's own "identical verdict sequence" assertion
vacuous rather than a real symmetry proof.

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
from tos.venue import ActionClass
from tos_runtime.compose.root import ConstructionConfig

from . import _fixtures as fx

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


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


def mirrored_construction_config() -> ConstructionConfig:
    """:func:`~._fixtures.construction_config`, mirrored (plan §2 decision 8: "픽스처
    side·action_class·venue_shape_constraints.allowed_sides 미러").

    **``envelope``/``order_shape`` are gone** ((a′) wave lane D — ``ConstructionConfig`` no
    longer carries either field, plan §4.7). Before lane D this module hand-authored a mirrored
    ``ProposedConstructionEnvelope``/``OrderShapeFields`` here (``mirrored_proposed_envelope``/
    ``mirrored_order_shape``, now removed) purely to flip their DIRECTION/SIDE content to SHORT
    — but neither injected literal was ever read on the SHORT run either: the envelope comes
    from ``build_construction_envelope`` (the loaded OCP's own ``construction_rules``, keyed by
    ``action_class``) and every ``order_shape`` field is sourced downstream of
    ``VenueServiceStage``, both driven by ``action_class`` alone. ``action_class=NEW_SHORT``
    below is the ONE thing that needs to flip; removing the two dead fields makes that the
    single, real, live driver instead of a second, silently-ignored declaration of the same
    fact — exactly what a symmetry suite should pin (§4.7's own dynamic evidence: this was one
    of the four call sites a merged round found still injecting into a dead surface).

    **Venue facts are no longer per-side fixture content** (TOS venue constraint service wave,
    plan §2 decision 5) — ``conftest.py``'s ONE governed ``venue_constraint_policy.yaml``
    admits BOTH ``NEW_LONG``/``NEW_SHORT`` and BOTH ``BUY``/``SELL`` (the same "mirror the
    admitting rule and the allowed side" intent decision 8 originally named for the fixture
    hand-issued snapshot/policy/decision, now realized at the governed-policy layer instead —
    see ``conftest.py``'s own ``venue_constraint_policy.yaml`` write for the shared admission).
    ``price``/``instrument_class``/the two price-field keys are the exact SAME fx-derived values
    as the LONG side: nothing about sizing, pricing, or the calendar lookup key is
    side-dependent."""
    return ConstructionConfig(
        account=fx.ACCOUNT,
        instrument=fx.INSTRUMENT,
        price=fx.admitted_price(),
        action_class=ActionClass.NEW_SHORT,
        instrument_class=fx.INSTRUMENT_CLASS,
        outbound_side="SELL",
        price_field_key=fx.PRICE_FIELD_KEY,
        shape_price_field_key=fx.PRICE_FIELD_KEY,
    )
