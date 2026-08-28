"""§4.7 ∅-void fail-closed regression — the nine-row table, **both ways**, 1:1 with §7.

Design #16 §4.7 tabulates nine empty-input cases with an explicit *forbidden* direction
(the vacuous-permissive reading that must be blocked) and an explicit *permitted* direction
(the complete input that must still pass). §7 lists the same nine as property targets, and
m10 requires the two lists to correspond **1:1**. This file is that correspondence: one
test pair per row, named for the row, so a future edit that drops a row is visible.

Both directions are load-bearing: a vacuous grant is a **safety** defect, and a vacuous
block (refusing a legitimate, fully-proven admission) is an **availability** defect
(the #12 both-ways lesson).

It also carries the §4.7 **forbidden-verb** canary sweep, asserting that each named verb
has a predicate that positively refuses it.

Closes **no** AFG-EV: predicate / coordinate substrate only (design #16 §1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.afg import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionFlowResult,
    ActionFlowScopeKind,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    DocumentedScopeStatus,
    action_flow_decision,
    amplification_bounded,
    atomic_economic_flow_coverage,
    backlog_is_not_authority,
    cause_lineage_complete,
    envelope_not_enlarged,
    headroom_within_limits,
    no_blind_retry,
    permit_not_merged,
    permit_release_admissible,
    queue_does_not_extend_validity,
    reserve_exclusive,
    scope_graph_complete,
    shared_limit_conservative,
)

from ._afg_strategies import (
    REQUIRED_SCOPES,
    SCHEME,
    clean_cause,
    flow_vector,
    full_envelope,
    issue_permit,
    issue_snapshot,
    limit_vector,
    reserve_claim,
    unclaimed_consumption,
    within_observation,
)

_CREDIBLE = frozenset(
    {
        ActionFlowScopeKind.GLOBAL,
        ActionFlowScopeKind.BROKER,
        ActionFlowScopeKind.ACCOUNT,
    }
)


# ---------------------------------------------------------------------------
# §4.7 row 1 — empty scope set
# ---------------------------------------------------------------------------


def test_row1_empty_scope_set_forbidden_direction() -> None:
    """(row 1 -) An empty evaluation scope is NOT "no shared limit" => restrictive."""
    assert (
        scope_graph_complete(
            issue_snapshot(), frozenset(), producer_self_declared_scope=False
        )
        is False
    )
    empty_snapshot = ActionFlowStateSnapshot.issue(
        scheme=SCHEME,
        snapshot_id="empty-1",
        snapshot_generation=1,
        consistency_cut_identity="cut-empty",
    )
    assert (
        scope_graph_complete(
            empty_snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
        )
        is False
    )


def test_row1_empty_scope_set_permitted_direction() -> None:
    """(row 1 +) Every applicable scope covered + independence evidenced => evaluable."""
    assert (
        scope_graph_complete(
            issue_snapshot(), REQUIRED_SCOPES, producer_self_declared_scope=False
        )
        is True
    )


# ---------------------------------------------------------------------------
# §4.7 row 2 — empty dimension set
# ---------------------------------------------------------------------------


def test_row2_empty_dimension_set_forbidden_direction() -> None:
    """(row 2 -) An empty governed dimension set is NOT "no resource use" => restrictive."""
    assert (
        headroom_within_limits([ActionFlowVector()], limit_vector(), limit_vector())
        is ActionFlowResult.UNKNOWN
    )


def test_row2_empty_dimension_set_permitted_direction() -> None:
    """(row 2 +) A complete governed dimension set is evaluable."""
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("1"))], limit_vector(), limit_vector()
        )
        is ActionFlowResult.GRANT
    )


# ---------------------------------------------------------------------------
# §4.7 row 3 — empty required scope (the consumer specified none)
# ---------------------------------------------------------------------------


def _decision(**overrides: object) -> ActionFlowResult:
    base: dict[str, object] = {
        "coverage": ActionFlowResult.GRANT,
        "scope_complete": True,
        "lineage_complete": True,
        "amplification_ok": True,
        "envelope_ok": True,
        "generation_current": True,
        "applicable_action_flow_scopes": (ActionFlowScopeKind.BROKER.value,),
        "decision_id": "afg-dec-void",
        "decision_generation": 1,
        "scheme": SCHEME,
    }
    base.update(overrides)
    return action_flow_decision(**base).result  # type: ignore[arg-type]


def test_row3_empty_required_scope_forbidden_direction() -> None:
    """(row 3 -) An unspecified consumer scope must not be a vacuous wildcard grant."""
    assert _decision(applicable_action_flow_scopes=()) is ActionFlowResult.DENY


def test_row3_empty_required_scope_permitted_direction() -> None:
    """(row 3 +) A consumer that names its required scope, fully covered, passes."""
    assert _decision() is ActionFlowResult.GRANT


# ---------------------------------------------------------------------------
# §4.7 row 4 — empty amplification envelope
# ---------------------------------------------------------------------------


def test_row4_empty_amplification_envelope_forbidden_direction() -> None:
    """(row 4 -) No declared bound means *unbounded* => denial (§5.8 line 141)."""
    assert (
        amplification_bounded(ActionAmplificationEnvelope(), within_observation())
        is False
    )


def test_row4_empty_amplification_envelope_permitted_direction() -> None:
    """(row 4 +) Every bound injected + counts within => evaluable and admissible."""
    assert amplification_bounded(full_envelope(), within_observation()) is True


# ---------------------------------------------------------------------------
# §4.7 row 5 — empty lineage
# ---------------------------------------------------------------------------


def test_row5_empty_lineage_forbidden_direction() -> None:
    """(row 5 -) A missing root / empty parent lineage => contained, never complete."""
    assert cause_lineage_complete(ActionCause()) is False
    assert cause_lineage_complete(clean_cause(parent_lineage=())) is False
    assert _decision(lineage_complete=False) is ActionFlowResult.UNKNOWN


def test_row5_empty_lineage_permitted_direction() -> None:
    """(row 5 +) A root plus a complete attested parent lineage is evaluable."""
    assert cause_lineage_complete(clean_cause()) is True


# ---------------------------------------------------------------------------
# §4.7 row 6 — None magnitude / limit
# ---------------------------------------------------------------------------


def test_row6_none_magnitude_or_limit_forbidden_direction() -> None:
    """(row 6 -) A ``None`` magnitude or limit is UNKNOWN, never assume-zero / assume-within."""
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=None)], limit_vector(), limit_vector()
        )
        is ActionFlowResult.UNKNOWN
    )
    assert (
        headroom_within_limits(
            [flow_vector()], limit_vector(magnitude=None), limit_vector()
        )
        is ActionFlowResult.UNKNOWN
    )
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(magnitude=None),
            injected_envelope_max=limit_vector(),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_row6_none_magnitude_or_limit_permitted_direction() -> None:
    """(row 6 +) A finite magnitude and a finite limit are comparable."""
    assert (
        headroom_within_limits(
            [flow_vector(magnitude=Decimal("1"))], limit_vector(), limit_vector()
        )
        is ActionFlowResult.GRANT
    )


# ---------------------------------------------------------------------------
# §4.7 row 7 — empty flow vector (m10)
# ---------------------------------------------------------------------------


def test_row7_empty_flow_vector_forbidden_direction() -> None:
    """(row 7 -) An absent / empty flow vector cannot prove atomic coverage => no GRANT."""
    for vector in (None, ActionFlowVector()):
        assert (
            atomic_economic_flow_coverage(
                "econ-1",
                vector,
                hard_limit=limit_vector(),
                runtime_limit=limit_vector(),
                economic_commitment_exclusive=True,
                flow_commitment_exclusive=True,
            )
            is not ActionFlowResult.GRANT
        )


def test_row7_empty_flow_vector_permitted_direction() -> None:
    """(row 7 +) An economic ref plus a covered flow vector can GRANT."""
    assert (
        atomic_economic_flow_coverage(
            "econ-1",
            flow_vector(magnitude=Decimal("2")),
            hard_limit=limit_vector(),
            runtime_limit=limit_vector(),
            economic_commitment_exclusive=True,
            flow_commitment_exclusive=True,
        )
        is ActionFlowResult.GRANT
    )


# ---------------------------------------------------------------------------
# §4.7 row 8 — empty permits (m10 / M8)
# ---------------------------------------------------------------------------


def test_row8_empty_permits_forbidden_direction() -> None:
    """(row 8 -) No permit, and no identified queue item, are both restrictive."""
    assert permit_not_merged([]) is False
    assert (
        queue_does_not_extend_validity(None, 1, 1, silently_refreshed_in_queue=False)
        is False
    )


def test_row8_empty_permits_permitted_direction() -> None:
    """(row 8 +) A single valid permit whose prerequisites are current may be reordered."""
    assert permit_not_merged([issue_permit()]) is True
    assert (
        queue_does_not_extend_validity(
            "queued-1", 1, 1, silently_refreshed_in_queue=False
        )
        is True
    )
    assert (
        backlog_is_not_authority(
            True,
            True,
            command_regenerated=False,
            backlog_treated_as_authority=False,
        )
        is True
    )


# ---------------------------------------------------------------------------
# §4.7 row 9 — empty credible containing scopes (m10 / C1)
# ---------------------------------------------------------------------------


def test_row9_empty_credible_containing_scopes_forbidden_direction() -> None:
    """(row 9 -) No credible containing scope => UNKNOWN (no "largest" is establishable)."""
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.INCOMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            frozenset(),
            True,
        )
        is ActionFlowResult.UNKNOWN
    )


def test_row9_empty_credible_containing_scopes_permitted_direction() -> None:
    """(row 9 +) A present credible set resolves to its largest member."""
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.INCOMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE,
            True,
        )
        is ActionFlowScopeKind.GLOBAL
    )


# ---------------------------------------------------------------------------
# §4.7 forbidden-verb sweep (Gap-4) — each verb has a predicate that refuses it
# ---------------------------------------------------------------------------


def test_forbidden_verb_narrower_scope_select() -> None:
    """('narrower-scope-select' §1:25) An unproven-independence claim cannot stay narrow."""
    verdict = shared_limit_conservative(
        DocumentedScopeStatus.VERIFIED_COMPLETE,
        ActionFlowScopeKind.GLOBAL,
        _CREDIBLE,
        None,
    )
    assert verdict is ActionFlowScopeKind.ACCOUNT


def test_forbidden_verb_patch_union_widen_replay() -> None:
    """('patch / union / widen / replay' AFG-INV-003:165) A replayed / merged permit is refused."""
    assert (
        permit_not_merged([issue_permit(), issue_permit(permit_id="afg-permit-2")])
        is False
    )


def test_forbidden_verb_borrow_reserve() -> None:
    """('borrow / consume / relabel reserve' AFG-INV-006:177) Encroachment is refused."""
    assert (
        reserve_exclusive(
            reserve_claim(),
            True,
            normal_traffic_borrowed=True,
            normal_traffic_consumed=False,
            relabelled_as_normal=False,
            repay_reserve_later_claimed=False,
        )
        is False
    )


def test_forbidden_verb_blind_retry() -> None:
    """('blind-retry' AFG-INV-008) An unproven retry is refused."""
    assert no_blind_retry(None, None, None, None) is False


def test_forbidden_verb_release() -> None:
    """('release' AFG-INV-012:201) An unproven permit release is refused."""
    assert permit_release_admissible(issue_permit(), unclaimed_consumption()) is False


def test_forbidden_verb_enlarge_envelope() -> None:
    """('enlarge Hard Safety Envelope' §8:248) A limit above the envelope maximum is refused."""
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(magnitude=Decimal("1000")),
            injected_envelope_max=limit_vector(magnitude=Decimal("100")),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_forbidden_verb_backlog_to_authority_and_regenerate_command() -> None:
    """('backlog→authority / regenerate-command' §12:313) Both are refused."""
    assert (
        backlog_is_not_authority(
            True, True, command_regenerated=True, backlog_treated_as_authority=False
        )
        is False
    )
    assert (
        backlog_is_not_authority(
            True, True, command_regenerated=False, backlog_treated_as_authority=True
        )
        is False
    )


def test_forbidden_verb_delegate_to_producer() -> None:
    """('delegate materiality / scope to producer' §8:248) A self-declared scope is refused."""
    assert (
        scope_graph_complete(
            issue_snapshot(), REQUIRED_SCOPES, producer_self_declared_scope=True
        )
        is False
    )
