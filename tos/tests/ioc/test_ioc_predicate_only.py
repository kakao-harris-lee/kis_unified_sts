"""Predicate-only rules (design #14 §6.1-§6.6; IOC-EV-007..012 substrate).

Both-ways canaries + the forbidden-verb canaries: "mutate" (§6.2 mutation fence), "revive"
(§6.6 non-revival), "expire" (§6.6 economic continuity), "headroom" (§6.5 all-false authority).
Closes no IOC-EV.
"""

from __future__ import annotations

from tos.ioc import (
    AxisBinding,
    ConformanceAxis,
    ConformanceResult,
    MutationClass,
    OrderConstructionAuthorityEffect,
    Ordering,
    OrderingEvent,
    canonicalization_deterministic,
    compare_order,
    construction_generation_fences,
    construction_grants_no_authority,
    derived_command_conformance,
    economic_effect_outlives,
    mutation_fence_holds,
    protective_creates_nothing,
    recovery_revives_nothing,
)

from ._ioc_strategies import issue_command, issue_proof

# ---------------------------------------------------------------------------
# canonicalization_deterministic (§6.1 / §14 line 406)
# ---------------------------------------------------------------------------


def test_command_recanonicalizes_to_its_digest() -> None:
    """(canary +) An issued command recanonicalizes to its bound digest => True."""
    assert canonicalization_deterministic(issue_command()) is True


def test_none_command_fails_closed() -> None:
    """(fail-closed) A None command => False."""
    assert canonicalization_deterministic(None) is False


# ---------------------------------------------------------------------------
# mutation_fence_holds (§6.2 / §15 line 414) — "mutate" verb
# ---------------------------------------------------------------------------


def test_proof_fences_the_exact_command() -> None:
    """(canary +) A proof binding the exact command digest => fence holds (True)."""
    command = issue_command()
    proof = issue_proof(command_digest=command.canonical_digest)
    assert mutation_fence_holds(command, proof) is True


def test_proof_binding_wrong_digest_fails() -> None:
    """(canary - 'mutate') A proof binding a different digest (a post-proof mutation) => False."""
    command = issue_command()
    proof = issue_proof(command_digest="different-digest")
    assert mutation_fence_holds(command, proof) is False


def test_mutation_fence_none_fails_closed() -> None:
    """(fail-closed) A None command / proof => False."""
    assert mutation_fence_holds(None, issue_proof()) is False
    assert mutation_fence_holds(issue_command(), None) is False


def test_command_is_structurally_unmutable_post_proof() -> None:
    """(§6.2 structural) The command is frozen — a post-proof economic-field mutation is impossible."""
    from pydantic import ValidationError

    command = issue_command()
    try:
        command.command_generation = 7  # type: ignore[misc]
    except ValidationError:
        return
    raise AssertionError(
        "a frozen command must reject post-proof mutation (§15 line 414)"
    )


# ---------------------------------------------------------------------------
# derived_command_conformance (§6.3 / §16) — no blind retry
# ---------------------------------------------------------------------------


def test_new_child_with_own_identity_is_conformant() -> None:
    """(canary +) A derived command with its own distinct identity => CONFORMANT."""
    parent = issue_command(command_id="cmd-parent")
    child = issue_command(command_id="cmd-child", command_generation=2)
    result = derived_command_conformance(parent, child, MutationClass.REPLACE)
    assert result is ConformanceResult.CONFORMANT


def test_reused_parent_identity_is_non_conformant() -> None:
    """(canary - §16 line 429) A derived command reusing the parent's identity => NON_CONFORMANT."""
    parent = issue_command(command_id="cmd-parent")
    result = derived_command_conformance(parent, parent, MutationClass.AMEND)
    assert result is ConformanceResult.NON_CONFORMANT


def test_aggregate_is_default_denied() -> None:
    """(canary - §16 line 437) Aggregation is default-denied => NON_CONFORMANT."""
    parent = issue_command(command_id="cmd-parent")
    child = issue_command(command_id="cmd-child", command_generation=2)
    result = derived_command_conformance(parent, child, MutationClass.AGGREGATE)
    assert result is ConformanceResult.NON_CONFORMANT


def test_retry_needs_proven_idempotency() -> None:
    """(§16 line 431 no-blind-retry) A RETRY with proven idempotency + retry-permitting attempt passes."""
    parent = issue_command(command_id="cmd-parent")
    child = issue_command(command_id="cmd-retry", command_generation=2)
    assert (
        derived_command_conformance(
            parent,
            child,
            MutationClass.RETRY,
            idempotency_capability_proven=True,
            original_attempt_permits_retry=True,
        )
        is ConformanceResult.CONFORMANT
    )


def test_blind_retry_is_non_conformant() -> None:
    """(canary - §16 line 431) A RETRY without proven idempotency => NON_CONFORMANT (no blind resubmit)."""
    parent = issue_command(command_id="cmd-parent")
    child = issue_command(command_id="cmd-retry", command_generation=2)
    assert (
        derived_command_conformance(
            parent,
            child,
            MutationClass.RETRY,
            idempotency_capability_proven=False,
            original_attempt_permits_retry=True,
        )
        is ConformanceResult.NON_CONFORMANT
    )


def test_retry_unknown_capability_is_unknown() -> None:
    """(fail-closed) A RETRY with unknown (None) idempotency capability => UNKNOWN (no blind retry)."""
    parent = issue_command(command_id="cmd-parent")
    child = issue_command(command_id="cmd-retry", command_generation=2)
    assert (
        derived_command_conformance(
            parent,
            child,
            MutationClass.RETRY,
            idempotency_capability_proven=None,
            original_attempt_permits_retry=None,
        )
        is ConformanceResult.UNKNOWN
    )


def test_derived_missing_identity_is_unknown() -> None:
    """(fail-closed) A derived command with no own identity / digest => UNKNOWN."""
    parent = issue_command(command_id="cmd-parent")
    from tos.ioc import CanonicalBrokerCommand

    draft = CanonicalBrokerCommand()  # DRAFT — no id / digest
    assert (
        derived_command_conformance(parent, draft, MutationClass.CANCEL)
        is ConformanceResult.UNKNOWN
    )


def test_derived_duplicate_axis_is_non_conformant() -> None:
    """(MAJOR-1 §14 line 406) A derived command repeating a semantic axis => NON_CONFORMANT.

    The lineage predicate inherits the command_conforms duplicate-axis structural guard; the
    surplus-vs-envelope check is command_conforms's domain (a derived command gets its own pass).
    """
    parent = issue_command(command_id="cmd-parent")
    dup_bindings = tuple(
        AxisBinding(axis=axis, value=str(i))
        for i, axis in enumerate((ConformanceAxis.SIDE, ConformanceAxis.SIDE))
    )
    derived = issue_command(command_id="cmd-child", axis_bindings=dup_bindings)
    result = derived_command_conformance(parent, derived, MutationClass.REPLACE)
    assert result is ConformanceResult.NON_CONFORMANT


# ---------------------------------------------------------------------------
# protective_creates_nothing (§6.4 / §19 line 481)
# ---------------------------------------------------------------------------


def test_protective_label_bypasses_nothing() -> None:
    """(canary +) A label bypassing nothing (all False) => True."""
    assert (
        protective_creates_nothing(
            label_bypasses_envelope=False,
            label_bypasses_admissibility=False,
            label_bypasses_capacity=False,
            label_bypasses_egress=False,
        )
        is True
    )


def test_protective_label_bypassing_envelope_rejected() -> None:
    """(canary - §19 line 483) A label claiming to bypass the envelope => False."""
    assert (
        protective_creates_nothing(
            label_bypasses_envelope=True,
            label_bypasses_admissibility=False,
            label_bypasses_capacity=False,
            label_bypasses_egress=False,
        )
        is False
    )


def test_protective_unknown_bypass_fails_closed() -> None:
    """(fail-closed) An unknown (None) bypass claim => False."""
    assert (
        protective_creates_nothing(
            label_bypasses_envelope=None,
            label_bypasses_admissibility=False,
            label_bypasses_capacity=False,
            label_bypasses_egress=False,
        )
        is False
    )


# ---------------------------------------------------------------------------
# construction_grants_no_authority (§6.5 / IOC-INV-011) — "headroom" verb
# ---------------------------------------------------------------------------


def test_default_authority_grants_nothing() -> None:
    """(canary + 'headroom') A default all-false effect grants no authority / creates no headroom => True."""
    assert construction_grants_no_authority(OrderConstructionAuthorityEffect()) is True


# ---------------------------------------------------------------------------
# recovery_revives_nothing (§6.6 / §21 line 515) — "revive" verb
# ---------------------------------------------------------------------------


def test_non_revival_is_unconditional() -> None:
    """(canary 'revive' §21 line 515) Nothing revives a prior proof / capability — unconditionally True."""
    assert recovery_revives_nothing() is True


# ---------------------------------------------------------------------------
# economic_effect_outlives (§6.6 / §18 / IOC-INV-012) — "expire" verb
# ---------------------------------------------------------------------------


def test_expiry_does_not_expire_economic_effect() -> None:
    """(canary 'expire' IOC-INV-012 line 201) Proof / capability expiry (no terminal proof) => effect outlives."""
    assert economic_effect_outlives(terminal_release_proven=None) is True
    assert economic_effect_outlives(terminal_release_proven=False) is True


def test_proven_terminal_release_ends_effect() -> None:
    """(§20 line 482) A positively proven defined RCL transition ends persistence."""
    assert economic_effect_outlives(terminal_release_proven=True) is False


# ---------------------------------------------------------------------------
# construction_generation_fences (§5.7 / §3.2 ordering REUSE)
# ---------------------------------------------------------------------------


def test_newer_generation_fences_older() -> None:
    """(canary +) An earlier generation provably precedes (is fenced by) a later one."""
    older = OrderingEvent(event_id="g1", quorum_commit_index=1)
    newer = OrderingEvent(event_id="g2", quorum_commit_index=2)
    assert construction_generation_fences(older, newer) is True
    assert compare_order(older, newer) is Ordering.BEFORE


def test_ambiguous_generation_order_fails_closed() -> None:
    """(fail-closed) An unorderable (ambiguous) generation pair => not fenced (a wall clock never orders)."""
    a = OrderingEvent(event_id="g1")
    b = OrderingEvent(event_id="g2")
    assert construction_generation_fences(a, b) is False
