"""MANDATED test-only seam cross-check: ioc <-> rcl (design #14 §3.4/§0.4c)."""

from __future__ import annotations

from decimal import Decimal

import tos.ioc as ioc
from tos.ioc import EconomicEffectEnvelope, economic_effect_dominated
from tos.rcl import (
    CapacityComponent,
    CapacityVector,
    GrantDecisionRef,
    LedgerCommandRecord,
)


def test_economic_effect_envelope_is_exact_rcl_capacity_vector() -> None:
    """(§0.4c type-seal) EconomicEffectEnvelope IS the rcl CapacityVector type — no reducer, no self vector."""
    assert EconomicEffectEnvelope is CapacityVector


def test_ioc_reintroduces_no_self_capacity_vector() -> None:
    """(§0.4c anti-regression) ioc defines no *EffectVector / *CapacityVector of its own."""
    banned = ("EffectVector", "IocCapacityVector", "EconomicVector", "AdverseVector")
    for name in dir(ioc):
        for token in banned:
            assert (
                token not in name
            ), f"tos.ioc unexpectedly defines its own vector: {name}"


def test_envelope_coordinate_matches_rcl_commit_coordinate() -> None:
    """(§13 line 341 / §5.5) The envelope drops straight into rcl's proposed_adverse_increment type."""
    envelope = EconomicEffectEnvelope(
        components=(
            CapacityComponent(dimension_id="notional", magnitude=Decimal("10")),
        )
    )
    command = LedgerCommandRecord(proposed_adverse_increment=envelope)
    assert isinstance(command.proposed_adverse_increment, CapacityVector)
    assert (
        LedgerCommandRecord.model_fields["proposed_adverse_increment"].annotation
        is CapacityVector
    )
    # dominance decided over the shared type: committed 20 dominates envelope 10.
    committed = CapacityVector(
        components=(
            CapacityComponent(dimension_id="notional", magnitude=Decimal("20")),
        )
    )
    assert economic_effect_dominated(envelope, committed) is True


def test_grant_decision_ref_accepts_scalar_decision_refs() -> None:
    """(§3.4 scalar seam) rcl GrantDecisionRef accepts the ioc-produced scalar decision refs."""
    ref = GrantDecisionRef(
        decision_id="dec-scalar",
        decision_generation=3,
        canonical_decision_digest="dec-digest",
    )
    assert ref.decision_id == "dec-scalar"
    assert ref.canonical_decision_digest == "dec-digest"
    assert ref.bound_reservation_revision is None
    assert ref.bound_reservation_digest is None
