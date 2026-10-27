"""Issue #960 — step 2 derives the command SIDE from the proposal, never the boot action class.

Against the SHIPPED order construction policies (the CP-3 LONG and SHORT tenant trees), not a hand-built mapping: the rule must hold for the documents that actually deploy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egressgw import VenueQuantityConstraint
from tos.engine import CommitmentStep, StageOutcome
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


# ===========================================================================
# the rule: (position_effect, direction) -> arm
# ===========================================================================


@pytest.mark.parametrize(
    ("path", "boot", "effect", "direction", "expected"),
    [
        # the long tree: entry BUY/OPEN unchanged, a long is closed by direction SHORT -> SELL
        (_LONG_OCP, ActionClass.NEW_LONG, "OPEN", "LONG", ("NEW_LONG", "LONG", "BUY")),
        (_LONG_OCP, ActionClass.NEW_LONG, "CLOSE", "SHORT", ("CLOSE", "LONG", "SELL")),
        # the short tree (mirror): entry SELL/OPEN, a short is closed by direction LONG -> BUY
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
    """No behaviour change for entries: the OPEN arm's envelope is byte-equal to the boot
    envelope the stage was built with before #960."""
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
        ("OPEN", "SHORT", "no single construction arm"),  # a short entry in a long tree
        (
            "CLOSE",
            "LONG",
            "no single construction arm",
        ),  # a BUY "close" of the held long
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


# ===========================================================================
# the stage: a refused attempt carries no command and no arm
# ===========================================================================


def _stage(ocp) -> ProposalShapedConstructionStage:
    ocp, arms = _arms(ocp, ActionClass.NEW_LONG)
    return ProposalShapedConstructionStage(
        arms=arms,
        loaded_ocp=ocp,
        price=None,
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


def _request(*, effect: str, direction: str):
    base = fx.stage_request(step=CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION)
    proposal = base.proposal.model_copy(
        update={"position_effect": effect, "direction": direction}
    )
    return base.model_copy(update={"proposal": proposal})


def test_a_close_with_no_arm_is_denied_at_step_2_with_its_reason(ocps) -> None:
    stage = _stage(ocps[_LONG_OCP])
    verdict = stage(_request(effect="CLOSE", direction="LONG"))
    assert verdict.outcome is StageOutcome.DENY
    assert stage.construction is not None and stage.construction.command is None
    assert "no single construction arm" in (stage.construction.denial_reason or "")
    assert stage.attempt is None
    # downstream reads fall back to the boot values only because there is nothing to send
    assert attempt_reader(stage)() is None


def test_the_stage_records_the_close_arm_for_downstream_reads(ocps) -> None:
    stage = _stage(ocps[_LONG_OCP])
    stage(_request(effect="CLOSE", direction="SHORT"))
    assert stage.attempt is not None
    assert attempt_side(stage, "BUY") == "SELL"
    assert attempt_action_class(stage, ActionClass.NEW_LONG) is ActionClass.CLOSE
    # the next attempt never inherits the previous arm
    stage(_request(effect="CLOSE", direction="LONG"))
    assert stage.attempt is None
    stage(_request(effect="OPEN", direction="LONG"))
    assert attempt_side(stage, "SELL") == "BUY"
    assert attempt_action_class(stage, ActionClass.CLOSE) is ActionClass.NEW_LONG
