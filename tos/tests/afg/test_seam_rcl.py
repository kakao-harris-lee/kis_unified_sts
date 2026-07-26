"""MANDATED test-only seam cross-check: afg <-> rcl (design #16 §3.4(d) / §0.4c).

afg imports the rcl ``CapacityVector`` type plus ``aggregate_usage`` / ``effective_limit``
at runtime — the **one** sanctioned sibling edge. It does **not** re-author rcl's binding
or capacity arithmetic. This file imports the rcl ``GrantDecisionRef`` /
``RclAuthorityEffect`` / ``grant_authorizes_exact_request`` / ``CommittedReservation``
consumers as a **test** to lock:

(a) the forward-only decision-content-ref seam (rcl ``authority.py:53-55``, whose slot
    ``:40`` is literally named an "Aggregate Risk / **Action Flow** decision reference");
(b) the non-cyclic pipeline — afg supplies no reservation coordinate, so a grant built from
    afg content alone is **not** authorized until rcl charges ``bound_reservation_*``
    post-commit (ADR §29 q2);
(c) the all-false authority isomorphism (afg ``ActionFlowGovernorEffect`` <->
    ``RclAuthorityEffect``);
(d) the type-level coordinate parity — the action-flow vector IS the ``CapacityVector`` rcl
    commits, and the headroom check REUSES rcl's own fail-closed arithmetic.

Causal isolation: each polarity assertion fixes a valid baseline and flips exactly one flag.

A test-only cross-import is **not** a runtime package edge (design #16 §3.4(d)/§7.1); the
``CapacityVector`` type edge is the single sanctioned ``afg -> rcl`` import.
"""

from __future__ import annotations

from decimal import Decimal

from tos.afg import (
    ActionFlowGovernorEffect,
    ActionFlowResult,
    ActionFlowVector,
    action_flow_vector_of,
    decision_content_ref,
    governor_grants_no_authority,
    headroom_within_limits,
)
from tos.rcl import (
    CapacityComponent,
    CapacityVector,
    CommittedReservation,
    GrantDecisionRef,
    RclAuthorityEffect,
    aggregate_usage,
    effective_limit,
    grant_authorizes_exact_request,
)

from ._afg_strategies import flow_vector, issue_decision, limit_vector


def test_afg_content_ref_fills_the_action_flow_slot_of_grant_decision_ref() -> None:
    """(seam a) afg's forward-only content ref populates rcl's three separate ref fields."""
    decision = issue_decision()
    decision_id, generation, digest = decision_content_ref(decision)
    ref = GrantDecisionRef(
        decision_id=decision_id,
        decision_generation=generation,
        canonical_decision_digest=digest,
    )
    assert ref.decision_id == decision.decision_id
    assert ref.decision_generation == decision.decision_generation
    assert ref.canonical_decision_digest == decision.canonical_digest
    # id ⊥ digest: the consumer carries them as separate fields precisely because the
    # decision id is NOT f(digest) (design #16 §3.1 / §0.4e).
    assert ref.decision_id != ref.canonical_decision_digest


def test_forward_only_afg_supplies_no_reservation_binding() -> None:
    """(seam b, non-cyclic) A grant built from afg content alone is not authorized."""
    decision_id, generation, digest = decision_content_ref(issue_decision())
    ref = GrantDecisionRef(
        decision_id=decision_id,
        decision_generation=generation,
        canonical_decision_digest=digest,
    )
    assert ref.bound_reservation_revision is None
    assert ref.bound_reservation_digest is None
    assert ref.bound_generation is None
    assert (
        grant_authorizes_exact_request(
            ref, CommittedReservation(), current_generation=1
        )
        is False
    )


def test_afg_all_false_authority_is_isomorphic_to_rcl() -> None:
    """(seam c) Both all-false blocks reject any ``True`` flag and grant nothing."""
    assert governor_grants_no_authority(ActionFlowGovernorEffect()) is True
    assert RclAuthorityEffect().creates_capacity is False
    for cls in (ActionFlowGovernorEffect, RclAuthorityEffect):
        raised = False
        try:
            cls(creates_capacity=True)  # type: ignore[call-arg]
        except Exception:
            raised = True
        assert raised, f"{cls.__name__}(creates_capacity=True) must be unconstructable"


def test_action_flow_vector_is_the_exact_type_rcl_commits() -> None:
    """(seam d) The action-flow vector IS the rcl ``CapacityVector`` — no reduction reducer."""
    assert ActionFlowVector is CapacityVector
    decision = issue_decision()
    vector = action_flow_vector_of(decision)
    assert isinstance(vector, CapacityVector)
    # The rcl commit coordinate is the same container type, so an afg-produced vector
    # drops straight into the ledger (design #16 §0.4c).
    reservation = CommittedReservation()
    assert isinstance(reservation.adverse_increment, CapacityVector)


def test_headroom_reuses_rcl_arithmetic_rather_than_re_deriving_it() -> None:
    """(seam d, #6 inequality seal) afg's verdict agrees with rcl's own usage / limit math."""
    committed = flow_vector(magnitude=Decimal("60"))
    proposed = flow_vector(magnitude=Decimal("50"))
    hard = limit_vector(magnitude=Decimal("100"))
    runtime = limit_vector(magnitude=Decimal("100"))

    rcl_usage = aggregate_usage([committed, proposed])
    rcl_limit = effective_limit(hard, runtime)
    dimension = rcl_usage.dimension_ids()[0]
    assert rcl_usage.magnitude(dimension) == Decimal("110")
    assert rcl_limit.magnitude(dimension) == Decimal("100")
    # afg's verdict is exactly `usage <= limit` over those rcl-computed values.
    assert (
        headroom_within_limits([committed, proposed], hard, runtime)
        is ActionFlowResult.DENY
    )
    # Causal isolation: shrink ONLY the proposal, everything else fixed => GRANT.
    assert (
        headroom_within_limits(
            [committed, flow_vector(magnitude=Decimal("40"))], hard, runtime
        )
        is ActionFlowResult.GRANT
    )


def test_rcl_none_propagation_reaches_the_afg_verdict_unchanged() -> None:
    """(seam d, fail-closed parity) rcl propagates ``None`` as UNKNOWN; afg does not soften it."""
    unknown = CapacityVector(
        components=(CapacityComponent(dimension_id="BROKER_REQUEST", magnitude=None),)
    )
    assert aggregate_usage([unknown]).magnitude("BROKER_REQUEST") is None
    assert (
        effective_limit(limit_vector(magnitude=None), limit_vector()).magnitude(
            "BROKER_REQUEST"
        )
        is None
    )
    assert (
        headroom_within_limits([unknown], limit_vector(), limit_vector())
        is ActionFlowResult.UNKNOWN
    )


def test_rcl_does_not_import_afg_so_the_edge_is_acyclic() -> None:
    """(§0.4c acyclicity) No rcl source references ``tos.afg`` — the single edge is one-way."""
    from pathlib import Path

    rcl_src = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "rcl"
    for path in sorted(rcl_src.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert (
            "tos.afg" not in text
        ), f"{path.name} imports tos.afg — the edge is cyclic"
