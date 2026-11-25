"""Issue #960 — step 2 derives the command SIDE from the proposal, never the boot action class."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import FLAT_QUANTITY_BASIS
from tos.egressgw import (
    AdmittedPriceObservation,
    EconomicEffectStage,
    EffectBasis,
    EffectDimensionSpec,
    VenueQuantityConstraint,
)
from tos.engine import CommitmentStep, StageOutcome
from tos.engine.vocabulary import CAPSULE_CONTEXT_SOURCE
from tos.venue import ActionClass
from tos_runtime.compose._attempt_arm import (
    attempt_action_class,
    attempt_reader,
    attempt_side,
)
from tos_runtime.compose._attempt_shape import (
    ProposalShapedConstructionStage,
    build_attempt_arms,
    select_attempt_arm,
)
from tos_runtime.compose._envelope_wiring import build_construction_envelope
from tos_runtime.riskstate.close_bound import CloseBoundRefusal, EntryCloseBound
from tos_runtime.venue import load_order_construction_policy

from . import _fixtures as fx
from .test_deploy_policies import _filled

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO = Path(__file__).resolve().parents[4]
_LONG_OCP = "LONG"
_SHORT_OCP = "SHORT"
_TREES = {
    _LONG_OCP: _REPO / "config/tos_runtime/cp3-setup-d-long",
    _SHORT_OCP: _REPO / "config/tos_runtime/cp3-setup-d-short",
}


@dataclass(frozen=True)
class _ShapeConstraints:
    allowed_sides: frozenset[str]


@dataclass(frozen=True)
class _VenueService:
    """The two attributes ``build_attempt_arms`` reads off a real venue service."""

    quantity_constraint: VenueQuantityConstraint
    shape_constraints: _ShapeConstraints


@pytest.fixture(scope="module")
def ocps(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """The shipped LONG/SHORT tenant OCPs, named-TBD coordinates filled (deploy-test idiom)."""
    out: dict[str, object] = {}
    for direction, tree in _TREES.items():
        raw = _filled(
            tree / "order_construction_policy.yaml",
            environment="paper",
            account="a",
            instrument="i",
            direction=direction,
            admits_flat_exit=True,
        )
        path = tmp_path_factory.mktemp(direction.lower()) / "ocp.yaml"
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        out[direction] = load_order_construction_policy(path, scheme=_SCHEME)
    return out


_VENUE = _VenueService(
    quantity_constraint=VenueQuantityConstraint(
        lot_size=None, min_quantity=None, max_quantity=None, quantity_unit=None
    ),
    shape_constraints=_ShapeConstraints(allowed_sides=frozenset({"BUY", "SELL"})),
)


def _arms(ocp, boot: ActionClass):
    arms = build_attempt_arms(
        ocp, boot_action_class=boot, venue_service=_VENUE  # type: ignore[arg-type]
    )
    return ocp, arms


def _select(ocp, boot: ActionClass, effect: str | None, direction: str | None):
    ocp, arms = _arms(ocp, boot)
    return select_attempt_arm(arms, ocp, position_effect=effect, direction=direction)


@pytest.mark.parametrize(
    ("path", "boot", "effect", "direction", "expected"),
    [
        (_LONG_OCP, ActionClass.NEW_LONG, "OPEN", "LONG", ("NEW_LONG", "LONG", "BUY")),
        (_LONG_OCP, ActionClass.NEW_LONG, "CLOSE", "SHORT", ("CLOSE", "LONG", "SELL")),
        (
            _SHORT_OCP,
            ActionClass.NEW_SHORT,
            "OPEN",
            "SHORT",
            ("NEW_SHORT", "SHORT", "SELL"),
        ),
        (_SHORT_OCP, ActionClass.NEW_SHORT, "CLOSE", "LONG", ("CLOSE", "SHORT", "BUY")),
    ],
    ids=["long-open", "long-close", "short-open", "short-close"],
)
def test_the_proposal_selects_the_arm_and_side(
    ocps, path, boot, effect, direction, expected
):
    arm = _select(ocps[path], boot, effect, direction)
    assert not isinstance(arm, str), arm
    assert (arm.action_class.value, arm.direction, arm.side) == expected
    assert arm.position_effect == effect
    side_binding = {
        b.axis.value: b.value for b in arm.envelope.authorized_axis_bindings
    }
    assert side_binding["SIDE"] == expected[2]


def test_a_close_of_a_long_never_resolves_to_buy(ocps) -> None:
    arm = _select(ocps[_LONG_OCP], ActionClass.NEW_LONG, "CLOSE", "SHORT")
    assert not isinstance(arm, str)
    assert arm.side == "SELL"


def test_the_open_arm_envelope_is_the_one_boot_always_built(ocps) -> None:
    """No behaviour change for entries: the OPEN arm's envelope is byte-equal to the boot"""
    ocp, arms = _arms(ocps[_LONG_OCP], ActionClass.NEW_LONG)
    before = build_construction_envelope(
        ocp.construction_rules,
        loaded_ocp=ocp,
        action_class=ActionClass.NEW_LONG,
        venue_quantity_constraint=_VENUE.quantity_constraint,
        venue_allowed_sides=_VENUE.shape_constraints.allowed_sides,
    )
    arm = select_attempt_arm(arms, ocp, position_effect="OPEN", direction="LONG")
    assert not isinstance(arm, str)
    assert arm.envelope == before == arms[0].envelope


@pytest.mark.parametrize(
    ("effect", "direction", "fragment"),
    [
        ("OPEN", "SHORT", "no single construction arm"),
        (
            "CLOSE",
            "LONG",
            "no single construction arm",
        ),
        ("CLOSE", None, "declares no position_effect/direction"),
        (None, "SHORT", "declares no position_effect/direction"),
        ("CLOSE", "SIDEWAYS", "names no side for an action in direction"),
        ("REDUCE", "SHORT", "no single construction arm"),
    ],
    ids=[
        "open-short",
        "close-long",
        "no-direction",
        "no-effect",
        "unknown-dir",
        "unknown-eff",
    ],
)
def test_no_arm_is_a_refusal_never_the_boot_class(
    ocps, effect, direction, fragment
) -> None:
    refused = _select(ocps[_LONG_OCP], ActionClass.NEW_LONG, effect, direction)
    assert isinstance(refused, str) and fragment in refused


def _stage(ocp, arms=None, *, price=None, entry_close_bound_reader=None):
    ocp, built = _arms(ocp, ActionClass.NEW_LONG)
    return ProposalShapedConstructionStage(
        arms=built if arms is None else arms,
        loaded_ocp=ocp,
        entry_close_bound_reader=entry_close_bound_reader,
        price=price,
        venue_constraint=_VENUE.quantity_constraint,
        scheme=_SCHEME,
        intent_id="intent-1",
        intent_version="1",
        envelope_id="env-1",
        policy_id="ocp-1",
        policy_version="1",
        policy_generation=1,
        command_id="cmd-1",
        generation=1,
    )


def _request(*, effect: str, direction: str, basis: str = "RISK", held=None):
    base = fx.stage_request(step=CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION)
    proposal = base.proposal.model_copy(
        update={
            "position_effect": effect,
            "direction": direction,
            "quantity_basis": basis,
        }
    )
    return base.model_copy(
        update={"proposal": proposal, "held_position_magnitude": held}
    )


def test_a_close_with_no_arm_is_denied_at_step_2_with_its_reason(ocps) -> None:
    stage = _stage(ocps[_LONG_OCP])
    verdict = stage(_request(effect="CLOSE", direction="LONG"))
    assert verdict.outcome is StageOutcome.DENY
    assert stage.construction is not None and stage.construction.command is None
    assert "no single construction arm" in (stage.construction.denial_reason or "")
    assert stage.attempt is None
    assert attempt_reader(stage)() is None


def test_the_stage_records_the_close_arm_for_downstream_reads(ocps) -> None:
    stage = _stage(ocps[_LONG_OCP])
    stage(_request(effect="CLOSE", direction="SHORT"))
    assert stage.attempt is not None
    assert attempt_side(stage, "BUY") == "SELL"
    assert attempt_action_class(stage, ActionClass.NEW_LONG) is ActionClass.CLOSE
    stage(_request(effect="CLOSE", direction="LONG"))
    assert stage.attempt is None
    stage(_request(effect="OPEN", direction="LONG"))
    assert attempt_side(stage, "SELL") == "BUY"
    assert attempt_action_class(stage, ActionClass.CLOSE) is ActionClass.NEW_LONG


_CLOSE_EFFECT_SPEC = EffectDimensionSpec(
    dimension_id="INSTRUMENT::CLOSE_ONLY_DIMENSION",
    basis=EffectBasis.QUANTITY,
    unit="CONTRACTS",
    scale="1",
)


def _arms_with_distinct_close_specs(ocp):
    """The shipped arms, with the CLOSE arm's envelope declaring its OWN effect dimension."""
    ocp, arms = _arms(ocp, ActionClass.NEW_LONG)
    arms = tuple(
        (
            arm
            if arm.action_class is not ActionClass.CLOSE
            else replace(
                arm,
                envelope=arm.envelope.model_copy(
                    update={"effect_dimensions": (_CLOSE_EFFECT_SPEC,)}
                ),
            )
        )
        for arm in arms
    )
    return ocp, arms


def test_step_5_derives_the_close_arms_effect_envelope_not_the_boot_arms(ocps) -> None:
    ocp, arms = _arms_with_distinct_close_specs(ocps[_LONG_OCP])
    boot_specs = arms[0].envelope.effect_dimensions
    assert boot_specs != (
        _CLOSE_EFFECT_SPEC,
    ), "the two arms must differ to prove anything"
    stage = _stage(ocp, arms)
    economic_stage = EconomicEffectStage(construction_stage=stage)

    stage(_request(effect="CLOSE", direction="SHORT"))
    assert stage.effect_specs == (_CLOSE_EFFECT_SPEC,)
    economic_stage(fx.stage_request(step=CommitmentStep.ECONOMIC_EFFECT_ENVELOPE))
    assert economic_stage.envelope is not None
    assert [c.dimension_id for c in economic_stage.envelope.components] == [
        _CLOSE_EFFECT_SPEC.dimension_id
    ]

    stage(_request(effect="OPEN", direction="LONG"))
    assert stage.effect_specs == boot_specs
    stage(_request(effect="CLOSE", direction="LONG"))
    assert stage.attempt is None and stage.effect_specs == boot_specs


_PRICE = AdmittedPriceObservation(
    source=CAPSULE_CONTEXT_SOURCE, value=Decimal("100"), snapshot_digest="cis-1025"
)

_NO_HELD_POSITION = "closes a position but no held position was observed"


def _bound(*, remaining: Decimal | None, refusal: str | None) -> EntryCloseBound:
    """An :class:`EntryCloseBound` in the exact shape its own reader returns."""
    return EntryCloseBound(
        account="88888888-01",
        instrument="101W09",
        entry_reservation_id=None if refusal is not None else "res-1025",
        entry_attempt_id=None if refusal is not None else "attempt-1025",
        entry_quantity=remaining,
        prior_closed=None if remaining is None else Decimal("0"),
        rcl_writer_epoch=None if refusal is not None else 1,
        rcl_last_seq=None if refusal is not None else 7,
        refusal=refusal,
    )


@pytest.mark.parametrize(
    "refusal",
    [
        CloseBoundRefusal.ENTRY_NOT_SOLE_CONSUMED_POSITION.value,
        "FILL_UNPROVEN",
        CloseBoundRefusal.SCOPE_READ_FAILED.value,
    ],
    ids=["entry-not-sole-consumed", "prior-close-unproven", "scope-unreadable"],
)
def test_a_refused_durable_bound_denies_the_flat_at_rule_4(ocps, refusal) -> None:
    """Every refusal leaves step 2 with NO held position, so the kernel denies — fail-closed."""
    stage = _stage(
        ocps[_LONG_OCP],
        price=_PRICE,
        entry_close_bound_reader=lambda: _bound(remaining=None, refusal=refusal),
    )
    verdict = stage(
        _request(effect="CLOSE", direction="SHORT", basis=FLAT_QUANTITY_BASIS)
    )
    assert verdict.outcome is StageOutcome.DENY
    assert _NO_HELD_POSITION in (stage.construction.denial_reason or "")


def test_a_reader_that_raises_denies_the_flat_rather_than_propagating(ocps) -> None:
    """An unreadable bound proves nothing, and a raising reader must not become a stage crash."""

    def _raises() -> EntryCloseBound:
        raise RuntimeError("the projection is unreadable")

    stage = _stage(ocps[_LONG_OCP], price=_PRICE, entry_close_bound_reader=_raises)
    verdict = stage(
        _request(effect="CLOSE", direction="SHORT", basis=FLAT_QUANTITY_BASIS)
    )
    assert verdict.outcome is StageOutcome.DENY
    assert _NO_HELD_POSITION in (stage.construction.denial_reason or "")


def test_no_reader_at_all_denies_the_flat_exactly_as_before(ocps) -> None:
    """The control: with no reader wired, the FLAT denial is the pre-#1025 one, unchanged."""
    stage = _stage(ocps[_LONG_OCP], price=_PRICE)
    verdict = stage(
        _request(effect="CLOSE", direction="SHORT", basis=FLAT_QUANTITY_BASIS)
    )
    assert verdict.outcome is StageOutcome.DENY
    assert _NO_HELD_POSITION in (stage.construction.denial_reason or "")


def test_a_proven_bound_carries_the_flat_past_rule_4(ocps) -> None:
    """A proven remainder is the held position, so rule 4 no longer denies."""
    stage = _stage(
        ocps[_LONG_OCP],
        price=_PRICE,
        entry_close_bound_reader=lambda: _bound(remaining=Decimal("10"), refusal=None),
    )
    stage(_request(effect="CLOSE", direction="SHORT", basis=FLAT_QUANTITY_BASIS))
    assert _NO_HELD_POSITION not in (stage.construction.denial_reason or "")


def test_an_action_proposals_request_is_never_shaped_and_never_reads_the_bound(
    ocps,
) -> None:
    """An ACTION proposal's request is passed through untouched (plan §2)."""
    calls: list[int] = []

    def _counting() -> EntryCloseBound:
        calls.append(1)
        return _bound(remaining=Decimal("10"), refusal=None)

    stage = _stage(ocps[_LONG_OCP], price=_PRICE, entry_close_bound_reader=_counting)

    stage(_request(effect="OPEN", direction="LONG"))
    assert calls == []
    stage(_request(effect="CLOSE", direction="SHORT"))
    assert calls == []

    stage(_request(effect="CLOSE", direction="SHORT", basis=FLAT_QUANTITY_BASIS))
    assert calls == [1]


def test_a_refused_arm_never_reaches_the_bound_reader(ocps) -> None:
    """A FLAT whose (effect, direction) selects no arm is refused BEFORE any durable read."""
    calls: list[int] = []

    def _counting() -> EntryCloseBound:
        calls.append(1)
        return _bound(remaining=Decimal("10"), refusal=None)

    stage = _stage(ocps[_LONG_OCP], price=_PRICE, entry_close_bound_reader=_counting)
    verdict = stage(
        _request(effect="CLOSE", direction="LONG", basis=FLAT_QUANTITY_BASIS)
    )
    assert verdict.outcome is StageOutcome.DENY
    assert "no single construction arm" in (stage.construction.denial_reason or "")
    assert calls == []
