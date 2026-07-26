"""core §5.3 — exact binding, single-use permit, atomic economic+flow coverage, §12 trio.

AFG-EV-007 substrate (ADR-002-022 §13 line 319-342; AFG-INV-003/004/005) plus the §12
line 300-313 queue / merge / backlog rules (design #16 M8). Both-ways canaries throughout
(design #16 §4.3/§4.7): permit replay, an economic-only or flow-only coverage, a merged
permit, a queue-expired prerequisite, and a backlog-as-authority all fire the guard, while
a single exact binding with both coverages proven passes.

The **both, not either** rule (AFG-INV-005 line 173 / §13 line 330) is exercised in both
asymmetric directions: economic present + flow absent, and flow present + economic absent.

Closes **no** AFG-EV: predicate / coordinate substrate only (design #16 §1).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.afg import (
    ActionFlowResult,
    ActionFlowScopeKind,
    ActionFlowVector,
    action_flow_decision,
    atomic_economic_flow_coverage,
    backlog_is_not_authority,
    decision_content_ref,
    headroom_within_limits,
    permit_not_merged,
    permit_release_admissible,
    permit_single_use,
    queue_does_not_extend_validity,
)
from tos.rcl import CapacityComponent, CapacityVector

from ._afg_strategies import (
    SCHEME,
    flow_vector,
    issue_permit,
    issue_policy,
    issue_snapshot,
    limit_vector,
    unclaimed_consumption,
)


def _grant_kwargs(**overrides: object) -> dict[str, object]:
    """Fully-proven decision inputs (the clean fixture — genuinely GRANT-able)."""
    base: dict[str, object] = {
        "coverage": ActionFlowResult.GRANT,
        "scope_complete": True,
        "lineage_complete": True,
        "amplification_ok": True,
        "envelope_ok": True,
        "generation_current": True,
        "applicable_action_flow_scopes": (ActionFlowScopeKind.BROKER.value,),
        "decision_id": "afg-dec-1",
        "decision_generation": 1,
        "scheme": SCHEME,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# permit_single_use (§13 line 342; AFG-INV-003)
# ---------------------------------------------------------------------------


def test_exact_unclaimed_single_use_permit_is_consumable() -> None:
    """(canary + §5.3) An exact, single-use, unclaimed permit => True."""
    assert permit_single_use(issue_permit(), unclaimed_consumption()) is True


def test_none_permit_or_unknown_consumption_fails_closed() -> None:
    """(fail-closed) A ``None`` permit, or an unknown consumption state, => False."""
    assert permit_single_use(None, unclaimed_consumption()) is False
    assert permit_single_use(issue_permit(), None) is False


def test_replayed_permit_is_rejected() -> None:
    """(canary 'replay' AFG-INV-003:165) An already-claimed permit => False."""
    assert (
        permit_single_use(issue_permit(), unclaimed_consumption(claimed=True)) is False
    )


def test_ambiguous_lost_or_conflicting_permit_stays_quarantined() -> None:
    """(canary - §13:342 / §17:395) Ambiguous / lost / conflicting => False (quarantined)."""
    for field in ("ambiguous", "lost", "conflicting"):
        for value in (True, None):
            assert (
                permit_single_use(
                    issue_permit(), unclaimed_consumption(**{field: value})
                )
                is False
            )


def test_non_single_use_permit_is_rejected() -> None:
    """(canary - §13:342) A permit declaring ``single_use=False`` => False."""
    assert (
        permit_single_use(issue_permit(single_use=False), unclaimed_consumption())
        is False
    )


def test_structurally_incomplete_permit_is_rejected() -> None:
    """(canary - AFG-INV-003) A permit missing its command identity / nonce => False."""
    from tos.afg import ActionFlowPermit

    incomplete = ActionFlowPermit(permit_id="p", permit_generation=1)
    assert permit_single_use(incomplete, unclaimed_consumption()) is False


# ---------------------------------------------------------------------------
# permit_release_admissible (§13 line 342 — the "release" forbidden verb)
# ---------------------------------------------------------------------------


def test_release_requires_positive_never_claimed_and_unreachable_proof() -> None:
    """(canary + §13:342) Proven never-claimed + unreachable => release admissible."""
    assert (
        permit_release_admissible(
            issue_permit(),
            unclaimed_consumption(never_claimed_and_unreachable_proven=True),
        )
        is True
    )


def test_release_without_proof_is_refused() -> None:
    """(canary 'release' §13:342) No positive unreachability proof => False."""
    for value in (False, None):
        assert (
            permit_release_admissible(
                issue_permit(),
                unclaimed_consumption(never_claimed_and_unreachable_proven=value),
            )
            is False
        )


def test_claimed_permit_cannot_be_released() -> None:
    """(canary 'release') A claimed permit stays consumed / quarantined => False."""
    assert (
        permit_release_admissible(
            issue_permit(),
            unclaimed_consumption(
                claimed=True, never_claimed_and_unreachable_proven=True
            ),
        )
        is False
    )


# ---------------------------------------------------------------------------
# headroom_within_limits (§13 item 6; the rcl arithmetic REUSE + §4.1 direction)
# ---------------------------------------------------------------------------


def test_usage_within_the_effective_limit_grants() -> None:
    """(canary + §4.1 item 3) usage <= effective_limit per dimension => GRANT."""
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("10"))],
            limit_vector(magnitude=Decimal("100")),
            limit_vector(magnitude=Decimal("100")),
        )
        is ActionFlowResult.GRANT
    )


def test_usage_above_the_effective_limit_denies() -> None:
    """(canary - §4.1 item 3) usage > effective_limit => DENY (the inequality direction)."""
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("101"))],
            limit_vector(magnitude=Decimal("100")),
            limit_vector(magnitude=Decimal("100")),
        )
        is ActionFlowResult.DENY
    )


def test_runtime_profile_narrows_but_never_enlarges_the_limit() -> None:
    """(rcl ``effective_limit`` REUSE) min(hard, runtime) governs — a runtime cannot enlarge."""
    # Runtime narrower than hard => the narrower value binds.
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("50"))],
            limit_vector(magnitude=Decimal("100")),
            limit_vector(magnitude=Decimal("10")),
        )
        is ActionFlowResult.DENY
    )
    # Runtime wider than hard => the hard value still binds (no enlargement).
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("50"))],
            limit_vector(magnitude=Decimal("10")),
            limit_vector(magnitude=Decimal("1000")),
        )
        is ActionFlowResult.DENY
    )


def test_none_usage_or_limit_magnitude_is_unknown() -> None:
    """(∅ §4.7 row 6) A ``None`` usage or limit magnitude => UNKNOWN, never assume-zero."""
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=None)],
            limit_vector(magnitude=Decimal("100")),
            limit_vector(magnitude=Decimal("100")),
        )
        is ActionFlowResult.UNKNOWN
    )
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("1"))],
            limit_vector(magnitude=None),
            limit_vector(magnitude=Decimal("100")),
        )
        is ActionFlowResult.UNKNOWN
    )


def test_empty_usage_or_empty_dimension_set_is_unknown() -> None:
    """(∅ §4.7 rows 2/7) Empty usage vectors or an empty dimension set => UNKNOWN."""
    assert (
        headroom_within_limits([], limit_vector(), limit_vector())
        is ActionFlowResult.UNKNOWN
    )
    assert (
        headroom_within_limits([ActionFlowVector()], limit_vector(), limit_vector())
        is ActionFlowResult.UNKNOWN
    )


def test_absent_limit_vector_is_unknown() -> None:
    """(fail-closed) A ``None`` hard or runtime limit vector => UNKNOWN."""
    assert (
        headroom_within_limits([flow_vector()], None, limit_vector())
        is ActionFlowResult.UNKNOWN
    )
    assert (
        headroom_within_limits([flow_vector()], limit_vector(), None)
        is ActionFlowResult.UNKNOWN
    )


def test_unknown_dimension_id_is_unknown() -> None:
    """(§2.2-4) An unenumerated (economic) dimension id => UNKNOWN, never a silent pass."""
    alien = CapacityVector(
        components=(
            CapacityComponent(dimension_id="GROSS_NOTIONAL", magnitude=Decimal("1")),
        )
    )
    limit = CapacityVector(
        components=(
            CapacityComponent(dimension_id="GROSS_NOTIONAL", magnitude=Decimal("100")),
        )
    )
    assert headroom_within_limits([alien], limit, limit) is ActionFlowResult.UNKNOWN


def test_committed_usage_aggregates_with_the_proposal() -> None:
    """(rcl ``aggregate_usage`` REUSE) Committed + proposed usage sum before the comparison."""
    committed = flow_vector(magnitude=Decimal("60"))
    proposed = flow_vector(magnitude=Decimal("50"))
    assert (
        headroom_within_limits(
            [committed, proposed],
            limit_vector(magnitude=Decimal("100")),
            limit_vector(magnitude=Decimal("100")),
        )
        is ActionFlowResult.DENY
    )


@given(usage=st.integers(min_value=0, max_value=200))
def test_headroom_direction_is_exactly_usage_le_limit(usage: int) -> None:
    """(property, #6 inequality seal) GRANT iff usage <= limit; DENY strictly above."""
    verdict = headroom_within_limits(
        [flow_vector(magnitude=Decimal(usage))],
        limit_vector(magnitude=Decimal("100")),
        limit_vector(magnitude=Decimal("100")),
    )
    expected = ActionFlowResult.GRANT if usage <= 100 else ActionFlowResult.DENY
    assert verdict is expected


# ---------------------------------------------------------------------------
# atomic_economic_flow_coverage (AFG-INV-005 — both, not either)
# ---------------------------------------------------------------------------


def _coverage(**overrides: object) -> ActionFlowResult:
    base: dict[str, object] = {
        "economic_ref": "econ-commit-1",
        "flow_vector": flow_vector(magnitude=Decimal("5")),
        "hard_limit": limit_vector(),
        "runtime_limit": limit_vector(),
        "economic_commitment_exclusive": True,
        "flow_commitment_exclusive": True,
    }
    base.update(overrides)
    economic_ref = base.pop("economic_ref")
    vector = base.pop("flow_vector")
    return atomic_economic_flow_coverage(economic_ref, vector, **base)  # type: ignore[arg-type]


def test_both_coverages_proven_grants() -> None:
    """(canary + AFG-INV-005) Economic ref + flow vector both exclusively committed => GRANT."""
    assert _coverage() is ActionFlowResult.GRANT


def test_economic_only_is_not_a_grant() -> None:
    """(canary - §13:330) Economic present + flow vector absent => no GRANT (both, not either)."""
    assert _coverage(flow_vector=None) is ActionFlowResult.UNKNOWN


def test_flow_only_is_not_a_grant() -> None:
    """(canary - §13:330, the mirror direction) Flow present + economic absent => no GRANT."""
    assert _coverage(economic_ref=None) is ActionFlowResult.UNKNOWN
    assert _coverage(economic_ref="TBD") is ActionFlowResult.UNKNOWN


def test_empty_flow_vector_is_restrictive() -> None:
    """(∅ §4.7 row 7) An empty flow vector cannot prove coverage => UNKNOWN."""
    assert _coverage(flow_vector=ActionFlowVector()) is ActionFlowResult.UNKNOWN


def test_non_exclusive_commitment_on_either_side_is_restrictive() -> None:
    """(canary - §13:330) A non-exclusive (or unknown) commitment on either side => UNKNOWN."""
    for field in ("economic_commitment_exclusive", "flow_commitment_exclusive"):
        for value in (False, None):
            assert _coverage(**{field: value}) is ActionFlowResult.UNKNOWN


def test_over_limit_coverage_denies() -> None:
    """(canary -) Both coverages present but over the effective limit => DENY."""
    assert (
        _coverage(flow_vector=flow_vector(magnitude=Decimal("101")))
        is ActionFlowResult.DENY
    )


# ---------------------------------------------------------------------------
# action_flow_decision (§5.4 / §13) — the composed verdict + forward-only ref
# ---------------------------------------------------------------------------


def test_fully_proven_inputs_produce_a_grant() -> None:
    """(canary +) Every premise positively proven => GRANT (a genuinely reachable fixture)."""
    decision = action_flow_decision(**_grant_kwargs())  # type: ignore[arg-type]
    assert decision.result is ActionFlowResult.GRANT


def test_any_unproven_premise_yields_unknown_not_deny() -> None:
    """(fail-closed) An unproven premise is UNKNOWN — never read as a proven rejection."""
    for field in (
        "scope_complete",
        "lineage_complete",
        "amplification_ok",
        "generation_current",
    ):
        decision = action_flow_decision(**_grant_kwargs(**{field: False}))  # type: ignore[arg-type]
        assert decision.result is ActionFlowResult.UNKNOWN, field


def test_unknown_coverage_propagates_to_unknown() -> None:
    """(AFG-INV-007:181) An UNKNOWN coverage never becomes a GRANT."""
    decision = action_flow_decision(
        **_grant_kwargs(coverage=ActionFlowResult.UNKNOWN)  # type: ignore[arg-type]
    )
    assert decision.result is ActionFlowResult.UNKNOWN


def test_empty_requested_scope_is_denied_not_granted() -> None:
    """(∅ §4.7 row 1) An empty requested scope is restrictive, never a wildcard grant."""
    decision = action_flow_decision(
        **_grant_kwargs(applicable_action_flow_scopes=())  # type: ignore[arg-type]
    )
    assert decision.result is ActionFlowResult.DENY


def test_enlarged_envelope_denies() -> None:
    """(canary 'enlarge-envelope') A limit that enlarged the envelope => DENY."""
    decision = action_flow_decision(**_grant_kwargs(envelope_ok=False))  # type: ignore[arg-type]
    assert decision.result is ActionFlowResult.DENY


def test_denied_coverage_denies() -> None:
    """(canary -) A determinate over-limit coverage => DENY."""
    decision = action_flow_decision(
        **_grant_kwargs(coverage=ActionFlowResult.DENY)  # type: ignore[arg-type]
    )
    assert decision.result is ActionFlowResult.DENY


def test_decision_binds_policy_and_snapshot_digests() -> None:
    """(§5.3 exact binding) The issued decision carries the bound policy / snapshot digests."""
    policy = issue_policy()
    snapshot = issue_snapshot()
    decision = action_flow_decision(
        **_grant_kwargs(policy=policy, snapshot=snapshot)  # type: ignore[arg-type]
    )
    assert decision.policy_digest == policy.canonical_digest
    assert decision.policy_generation == policy.policy_generation
    assert decision.snapshot_digest == snapshot.canonical_digest


def test_decision_content_ref_is_forward_only() -> None:
    """(§3.4 rcl seam) The produced ref is (id, generation, digest) — no reservation coordinate."""
    decision = action_flow_decision(**_grant_kwargs())  # type: ignore[arg-type]
    decision_id, generation, digest = decision_content_ref(decision)
    assert decision_id == decision.decision_id
    assert generation == decision.decision_generation
    assert digest == decision.canonical_digest
    assert digest != decision_id  # id ⊥ digest


# ---------------------------------------------------------------------------
# §12 trio (M8) — queue / merge / backlog
# ---------------------------------------------------------------------------


def test_queue_does_not_extend_validity_positive_side() -> None:
    """(canary + §12:311) A current prerequisite with no silent refresh => True."""
    assert (
        queue_does_not_extend_validity(
            "queued-1", 7, 7, silently_refreshed_in_queue=False
        )
        is True
    )


def test_queue_expired_prerequisite_is_denied() -> None:
    """(canary - §12:311) A prerequisite that expired in queue => False."""
    assert (
        queue_does_not_extend_validity(
            "queued-1", 6, 7, silently_refreshed_in_queue=False
        )
        is False
    )


def test_silent_in_queue_refresh_is_rejected() -> None:
    """(canary - §12:311) A silent in-queue refresh => False; unknown status too."""
    for value in (True, None):
        assert (
            queue_does_not_extend_validity(
                "queued-1", 7, 7, silently_refreshed_in_queue=value
            )
            is False
        )


def test_unidentified_queue_item_is_restrictive() -> None:
    """(∅ §4.7 row 8) An unidentified / "TBD" queue item => False."""
    assert (
        queue_does_not_extend_validity(None, 7, 7, silently_refreshed_in_queue=False)
        is False
    )
    assert (
        queue_does_not_extend_validity("TBD", 7, 7, silently_refreshed_in_queue=False)
        is False
    )


def test_single_exact_permit_is_not_merged() -> None:
    """(canary + §12:313) Exactly one exact, single-use permit => True."""
    assert permit_not_merged([issue_permit()]) is True


def test_two_permits_are_a_merge_attempt() -> None:
    """(canary 'merge-permits' §12:313) Two permits presented for one action => False."""
    assert (
        permit_not_merged([issue_permit(), issue_permit(permit_id="afg-permit-2")])
        is False
    )


def test_empty_permit_list_is_restrictive() -> None:
    """(∅ §4.7 row 8) No permit is not a permit => False."""
    assert permit_not_merged([]) is False


def test_incomplete_or_multi_use_permit_is_not_exact() -> None:
    """(canary - AFG-INV-003) A non-single-use permit fails the exactness check."""
    assert permit_not_merged([issue_permit(single_use=False)]) is False


def test_backlog_reorder_with_valid_prereqs_passes() -> None:
    """(canary + §12:313) A reorder of an action whose independent prereqs are valid => True."""
    assert (
        backlog_is_not_authority(
            True,
            True,
            command_regenerated=False,
            backlog_treated_as_authority=False,
        )
        is True
    )


def test_backlog_cannot_become_authority() -> None:
    """(canary 'backlog→authority' §12:313) Treating backlog as authority => False."""
    for value in (True, None):
        assert (
            backlog_is_not_authority(
                True,
                True,
                command_regenerated=False,
                backlog_treated_as_authority=value,
            )
            is False
        )


def test_scheduler_cannot_regenerate_a_command() -> None:
    """(canary 'regenerate-command' §12:313) A regenerated command => False."""
    for value in (True, None):
        assert (
            backlog_is_not_authority(
                True,
                True,
                command_regenerated=value,
                backlog_treated_as_authority=False,
            )
            is False
        )


def test_invalid_or_unknown_prereqs_block_reorder() -> None:
    """(fail-closed §12:313) Invalid / unknown independent prerequisites => False."""
    for value in (False, None):
        assert (
            backlog_is_not_authority(
                True,
                value,
                command_regenerated=False,
                backlog_treated_as_authority=False,
            )
            is False
        )


def test_unknown_reorder_status_fails_closed() -> None:
    """(fail-closed) An unknown (``None``) reorder status => False."""
    assert (
        backlog_is_not_authority(
            None,
            True,
            command_regenerated=False,
            backlog_treated_as_authority=False,
        )
        is False
    )
