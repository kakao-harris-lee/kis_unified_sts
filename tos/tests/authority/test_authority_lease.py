"""Degraded lease exclusivity / validity / invalidation / reassignment (§6.1-§6.4).

The v1.1 seams closed here: (M1) ``lease_scope_exclusive`` requires the claimant to be
present and the UNIQUE owner of its (scope, capacity) key — empty / absent / duplicate =>
False (the ``0 <= 1`` vacuous-True fail-open is gone), and ``degraded_lease_valid``
composes it internally instead of trusting an injected ``exclusivity_ok`` bool; the
lease-validity time terms compose ``tos.time`` so the negative-injected-term fail-closed
guard (Time v1.2 REJECT) is inherited (regression-locked). SA-EV-004/005/006/007/011
substrate.
"""

from __future__ import annotations

from tos.authority import (
    AuthorityState,
    LeaseReassignmentInputs,
    degraded_lease_invalidated,
    degraded_lease_valid,
    lease_scope_exclusive,
    overlapping_reassignment_forbidden,
)
from tos.time import HealthState

from ._authority_strategies import anchor, issue_lease, valid_lease_kwargs

# ---- §6.1 exclusivity (claimant-present + unique; M1) ----------------------


def test_exclusivity_empty_set_is_false() -> None:
    """(canary M1) An empty owner set => False (no vacuous True from ``0 <= 1``)."""
    assert lease_scope_exclusive("lo-1", []) is False


def test_exclusivity_claimant_absent_is_false() -> None:
    """(canary M1) A claimant not present in the view => False (fail-open removed)."""
    other = issue_lease(lease_ownership_id="lo-2")
    assert lease_scope_exclusive("lo-1", [other]) is False


def test_exclusivity_none_claimant_is_false() -> None:
    """(canary M1) A None claimant id => False (fail-closed)."""
    only = issue_lease(lease_ownership_id="lo-1")
    assert lease_scope_exclusive(None, [only]) is False


def test_exclusivity_two_owners_same_key_is_false() -> None:
    """(canary M1) Two owners of the same (scope, capacity) key => False (overlapping)."""
    a = issue_lease(
        lease_ownership_id="lo-1",
        exclusive_scope="S",
        referenced_capacity_lease_id="L",
    )
    b = issue_lease(
        lease_ownership_id="lo-2",
        exclusive_scope="S",
        referenced_capacity_lease_id="L",
    )
    assert lease_scope_exclusive("lo-1", [a, b]) is False
    # Overlapping ownership is representable (both records preserved) so it is DETECTED.
    assert a is not b


def test_exclusivity_sole_claimant_is_true() -> None:
    """(canary M1, guard fires True) A sole present owner of its key => True."""
    only = issue_lease(
        lease_ownership_id="lo-1", exclusive_scope="S", referenced_capacity_lease_id="L"
    )
    assert lease_scope_exclusive("lo-1", [only]) is True


def test_exclusivity_distinct_keys_each_unique() -> None:
    """Two owners of DIFFERENT keys are each the sole owner of their own key (not overlap)."""
    a = issue_lease(
        lease_ownership_id="lo-1",
        exclusive_scope="S1",
        referenced_capacity_lease_id="L1",
    )
    b = issue_lease(
        lease_ownership_id="lo-2",
        exclusive_scope="S2",
        referenced_capacity_lease_id="L2",
    )
    assert lease_scope_exclusive("lo-1", [a, b]) is True
    assert lease_scope_exclusive("lo-2", [a, b]) is True


def test_exclusivity_unestablished_key_coordinate_is_false() -> None:
    """(canary M1) A claimant whose scope / capacity key is unestablished => False.

    ``referenced_capacity_lease_id`` is required-covered, so a null one keeps the record
    DRAFT; a DRAFT claimant (never a ledger citizen) cannot prove exclusivity.
    """
    from tos.authority import DegradedLeaseOwnershipRecord

    draft = DegradedLeaseOwnershipRecord(
        lease_ownership_id="lo-1",
        exclusive_scope="S",
        referenced_capacity_lease_id=None,
    )
    assert lease_scope_exclusive("lo-1", [draft]) is False


# ---- §6.3 degraded lease validity (time + exclusivity composed) ------------


def test_degraded_lease_valid_positive_path() -> None:
    """A fully-valid degraded lease is valid (guard not const-False)."""
    lease = issue_lease()
    assert degraded_lease_valid(lease, [lease], **valid_lease_kwargs()) is True


def test_degraded_lease_invalid_when_protective_classification_absent() -> None:
    """(canary cond 1) protective_classification_present None/False => invalid."""
    lease = issue_lease()
    for value in (False, None):
        kwargs = valid_lease_kwargs(protective_classification_present=value)
        assert degraded_lease_valid(lease, [lease], **kwargs) is False


def test_degraded_lease_invalid_when_rcl_scalars_missing() -> None:
    """(canary cond 2) A missing pre-committed protective capacity reference => invalid."""
    lease = issue_lease(referenced_protective_pool_identity=None)
    assert degraded_lease_valid(lease, [lease], **valid_lease_kwargs()) is False


def test_degraded_lease_invalid_when_broker_capability_absent() -> None:
    """(canary cond 6) broker_capability_permits None/False => invalid."""
    lease = issue_lease()
    for value in (False, None):
        kwargs = valid_lease_kwargs(broker_capability_permits=value)
        assert degraded_lease_valid(lease, [lease], **kwargs) is False


def test_degraded_lease_invalid_under_dominating_safer_state() -> None:
    """(canary cond 7) A strictly-safer dominating state (CONTAINED / HALTED) => invalid."""
    lease = issue_lease()
    for state in (AuthorityState.CONTAINED, AuthorityState.HALTED):
        kwargs = valid_lease_kwargs(dominating_state=state)
        assert degraded_lease_valid(lease, [lease], **kwargs) is False


def test_degraded_lease_invalid_under_untrusted_time_health() -> None:
    """(canary) An UNTRUSTED / non-holdover time-health state => invalid (§15.3)."""
    lease = issue_lease()
    for health in (
        HealthState.UNTRUSTED,
        HealthState.UNINITIALIZED,
        HealthState.SYNCHRONIZING,
    ):
        kwargs = valid_lease_kwargs(health_state=health)
        assert degraded_lease_valid(lease, [lease], **kwargs) is False


def test_degraded_lease_invalid_when_overlapping() -> None:
    """(canary cond 5) A second owner of the same key makes the lease non-exclusive => invalid."""
    lease = issue_lease(
        lease_ownership_id="lo-1", exclusive_scope="S", referenced_capacity_lease_id="L"
    )
    overlap = issue_lease(
        lease_ownership_id="lo-2", exclusive_scope="S", referenced_capacity_lease_id="L"
    )
    assert (
        degraded_lease_valid(lease, [lease, overlap], **valid_lease_kwargs()) is False
    )


def test_degraded_lease_invalid_on_anchor_restart() -> None:
    """(canary cond 4 / SA-EV-006) A restart (changed boot id) invalidates the anchor => invalid."""
    lease = issue_lease()
    kwargs = valid_lease_kwargs(continuity_now=anchor(boot_id="boot-2"))
    assert degraded_lease_valid(lease, [lease], **kwargs) is False


# ---- negative-injected-term regression lock (Time v1.2 REJECT inherited) ----


def test_negative_time_term_cannot_extend_lease() -> None:
    """(canary regression) A negative injected time term => lifetime None => invalid (Time v1.2).

    A negative elapsed / drift / transport / suspension / margin must never *extend* a
    lease; composition inherits ``conservative_usable_lifetime``'s fail-closed guard.
    """
    lease = issue_lease()
    for term in (
        "elapsed_monotonic",
        "max_drift_error",
        "source_transport_uncertainty",
        "suspension_uncertainty",
        "safety_margin",
    ):
        kwargs = valid_lease_kwargs(**{term: -1})
        assert (
            degraded_lease_valid(lease, [lease], **kwargs) is False
        ), f"negative {term} extended the lease (fail-open regression)"


def test_monotonic_exceeded_invalidates_even_if_wall_looks_valid() -> None:
    """(canary SA-EV-005) elapsed beyond issued lifetime => non-positive => invalid.

    The strongest substrate: a signed wall deadline that appears valid does not matter —
    once monotonic usable lifetime is non-positive the lease is invalid.
    """
    lease = issue_lease()
    kwargs = valid_lease_kwargs(issued_lifetime=100, elapsed_monotonic=100)
    assert degraded_lease_valid(lease, [lease], **kwargs) is False


# ---- §6.4 invalidating events ---------------------------------------------


def _invalidation_kwargs(**overrides: object) -> dict[str, object]:
    """Kwargs for ``degraded_lease_invalidated`` describing a still-valid lease."""
    base: dict[str, object] = {
        "continuity_now": anchor(),
        "suspension_ms": 0,
        "max_suspension_ms": 2000,
        "issued_lifetime": 5000,
        "elapsed_monotonic": 100,
        "source_transport_uncertainty": 10,
        "max_drift_error": 10,
        "suspension_uncertainty": 10,
        "safety_margin": 10,
        "protective_capacity_exhausted": False,
        "hard_envelope_incompatible": False,
        "broker_profile_revoked": False,
        "dominating_state": AuthorityState.DEGRADED_PROTECTIVE,
    }
    base.update(overrides)
    return base


def test_valid_lease_not_invalidated() -> None:
    """(guard fires) A still-valid lease is NOT invalidated (not constant-True)."""
    lease = issue_lease()
    assert degraded_lease_invalidated(lease, [lease], **_invalidation_kwargs()) is False


def test_restart_invalidates() -> None:
    """(canary SA-EV-006) A process restart (changed boot id) invalidates (§14.4)."""
    lease = issue_lease()
    kwargs = _invalidation_kwargs(continuity_now=anchor(boot_id="boot-2"))
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


def test_discontinuity_invalidates() -> None:
    """(canary SA-EV-011) A monotonic discontinuity (value went backward) invalidates."""
    lease = issue_lease()
    kwargs = _invalidation_kwargs(continuity_now=anchor(monotonic_anchor_value=50))
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


def test_unknown_suspension_invalidates() -> None:
    """(canary SA-EV-011) Unknown suspension (None) invalidates (fail-closed)."""
    lease = issue_lease()
    kwargs = _invalidation_kwargs(suspension_ms=None)
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


def test_holdover_expiry_invalidates() -> None:
    """A non-positive usable lifetime (holdover budget expired) invalidates."""
    lease = issue_lease()
    kwargs = _invalidation_kwargs(issued_lifetime=50, elapsed_monotonic=50)
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


def test_lost_exclusive_owner_proof_invalidates() -> None:
    """(canary) Loss of exclusive owner proof (a second owner appears) invalidates."""
    lease = issue_lease(
        lease_ownership_id="lo-1", exclusive_scope="S", referenced_capacity_lease_id="L"
    )
    overlap = issue_lease(
        lease_ownership_id="lo-2", exclusive_scope="S", referenced_capacity_lease_id="L"
    )
    assert (
        degraded_lease_invalidated(lease, [lease, overlap], **_invalidation_kwargs())
        is True
    )


def test_injected_event_flags_invalidate_on_true_or_none() -> None:
    """(canary) capacity-exhausted / envelope-incompat / profile-revoked True OR None => invalidated."""
    lease = issue_lease()
    for field in (
        "protective_capacity_exhausted",
        "hard_envelope_incompatible",
        "broker_profile_revoked",
    ):
        for bad in (True, None):
            kwargs = _invalidation_kwargs(**{field: bad})
            assert (
                degraded_lease_invalidated(lease, [lease], **kwargs) is True
            ), f"{field}={bad} did not invalidate (fail-closed)"


def test_dominating_safer_state_invalidates() -> None:
    """A dominating CONTAINED / HALTED state invalidates the lease (§14.4)."""
    lease = issue_lease()
    for state in (AuthorityState.CONTAINED, AuthorityState.HALTED):
        kwargs = _invalidation_kwargs(dominating_state=state)
        assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


# ---- §6.2 overlapping reassignment forbidden ------------------------------


def test_reassignment_forbidden_when_both_fences_unknown() -> None:
    """(canary SA-EV-007) hard_fence_proven=None AND lease_expiry_fence_elapsed=None => forbidden."""
    inputs = LeaseReassignmentInputs(
        prior_owner_scope="S", hard_fence_proven=None, lease_expiry_fence_elapsed=None
    )
    assert overlapping_reassignment_forbidden(inputs) is True


def test_reassignment_forbidden_when_both_false() -> None:
    """Both fences False => still forbidden (fail-closed)."""
    inputs = LeaseReassignmentInputs(
        hard_fence_proven=False, lease_expiry_fence_elapsed=False
    )
    assert overlapping_reassignment_forbidden(inputs) is True


def test_reassignment_allowed_with_hard_fence() -> None:
    """(guard fires) A proven hard fence unlocks reassignment."""
    inputs = LeaseReassignmentInputs(hard_fence_proven=True)
    assert overlapping_reassignment_forbidden(inputs) is False


def test_reassignment_allowed_with_expiry_fence() -> None:
    """An elapsed lease-expiry fence unlocks reassignment."""
    inputs = LeaseReassignmentInputs(lease_expiry_fence_elapsed=True)
    assert overlapping_reassignment_forbidden(inputs) is False


def test_epoch_advance_alone_cannot_unlock_reassignment() -> None:
    """(canary §14.5) The predicate reads no epoch — advancing one changes nothing.

    ``LeaseReassignmentInputs`` has no epoch field; only a proven hard fence or an elapsed
    expiry fence unlocks reassignment. Constructing inputs with both fences absent stays
    forbidden regardless of any epoch state elsewhere.
    """
    assert "epoch" not in " ".join(LeaseReassignmentInputs.model_fields)
    inputs = LeaseReassignmentInputs(prior_owner_scope="S")
    assert overlapping_reassignment_forbidden(inputs) is True
