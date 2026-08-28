"""Shared valid-artifact builders + strategies for the RCL property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (RCL design §0.3). The
``issue_*`` / ``*_required_kwargs`` builders populate every safety-load-bearing
covered field each artifact's issuance guard demands, so a "valid" fixture is
genuinely valid (never the all-null coverage illusion). The reserved ``"TBD"``
placeholder is excluded from required-field text (a past flaky-test lesson).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.rcl import (
    AuthoritativeSnapshot,
    CapacityComponent,
    CapacityState,
    CapacityVector,
    CommandType,
    CommittedReservation,
    FenceCoordinates,
    LedgerCommandRecord,
    ProtectiveLease,
    ProtectivePool,
    RclTransitionRecord,
    ReservationRecord,
    SnapshotCompleteness,
    TransmissionCapability,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved
#: ``"TBD"`` placeholder the issuance guard rejects — design §3.2).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

#: A magnitude strategy over non-negative Decimals (no float; §0.3).
MAGNITUDE = st.integers(min_value=0, max_value=1000).map(Decimal)


def vec(**dims: Decimal | int | None) -> CapacityVector:
    """Build a Capacity Vector from ``dimension_id=magnitude`` kwargs.

    A ``None`` value is an UNKNOWN (unbounded) dimension; an int is coerced to
    ``Decimal``.
    """
    components = tuple(
        CapacityComponent(
            dimension_id=name,
            magnitude=None if value is None else Decimal(str(value)),
        )
        for name, value in dims.items()
    )
    return CapacityVector(components=components)


# ---------------------------------------------------------------------------
# Reservation / Commitment Record
# ---------------------------------------------------------------------------


def reservation_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Reservation issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "reservation_id": "rsv-1",
        "parent_intent_id": "intent-1",
        "account_and_portfolio_scope": "acct-1",
        "instrument_and_underlying_scope": "ES",
        "action_class": "OPEN",
        "pool_identity": "normal",
        "aggregate_risk_authority_grant_identity": "grant-1",
        "evidence_snapshot_identity": "esnap-1",
        "hard_safety_envelope_version": "h-1",
        "runtime_safety_profile_version": "r-1",
        "ledger_epoch": 1,
    }
    base.update(overrides)
    return base


def issue_reservation(**overrides: Any) -> ReservationRecord:
    """Issue a valid :class:`ReservationRecord`."""
    return ReservationRecord.issue(
        scheme=SCHEME, **reservation_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Ledger Command Record
# ---------------------------------------------------------------------------


def command_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Command issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "command_identity": "cmd-1",
        "command_type": CommandType.COMMIT_RESERVATION,
        "canonical_schema_version": "cmd-schema-0",
        "capacity_domain": "cd-1",
        "cluster_identity": "cluster-1",
        "actor_identity": "actor-1",
        "permitted_command_role": "writer",
        "requested_transition": "commit-reservation",
    }
    base.update(overrides)
    return base


def issue_command(**overrides: Any) -> LedgerCommandRecord:
    """Issue a valid :class:`LedgerCommandRecord`."""
    return LedgerCommandRecord.issue(
        scheme=SCHEME, **command_required_kwargs(**overrides)
    )


def commit_reservation_command(
    *,
    command_identity: str,
    expected_revision: int,
    reservation_id: str,
    increment: CapacityVector,
    producer_local_counter: int | None = None,
    scheduler_priority: int | None = None,
) -> LedgerCommandRecord:
    """A CommitReservation command binding a proposed adverse increment (reducer input)."""
    return issue_command(
        command_identity=command_identity,
        command_type=CommandType.COMMIT_RESERVATION,
        fence=FenceCoordinates(expected_revision=expected_revision),
        proposed_reservation_id=reservation_id,
        proposed_adverse_increment=increment,
        producer_local_counter=producer_local_counter,
        scheduler_priority=scheduler_priority,
    )


# ---------------------------------------------------------------------------
# RCL Transition Record
# ---------------------------------------------------------------------------


def transition_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Transition issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "transition_id": "tr-1",
        "new_state": CapacityState.COMMITTED_UNBOUND,
        "command_identity": "cmd-1",
        "actor_identity": "actor-1",
    }
    base.update(overrides)
    return base


def issue_transition(**overrides: Any) -> RclTransitionRecord:
    """Issue a valid :class:`RclTransitionRecord`."""
    return RclTransitionRecord.issue(
        scheme=SCHEME, **transition_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Transmission Capability
# ---------------------------------------------------------------------------


def capability_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Capability issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "capability_id": "cap-1",
        "nonce": "nonce-1",
        "reservation_identity": "rsv-1",
        "attempt_identity": "att-1",
        "account_scope": "acct-1",
        "instrument_scope": "ES",
        "side_action_scope": "BUY",
        "ledger_epoch": 1,
    }
    base.update(overrides)
    return base


def issue_capability(**overrides: Any) -> TransmissionCapability:
    """Issue a valid :class:`TransmissionCapability`."""
    return TransmissionCapability.issue(
        scheme=SCHEME, **capability_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Protective Pool / Lease
# ---------------------------------------------------------------------------


def pool_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Protective-pool issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "pool_id": "pool-1",
        "pool_scope": "acct-1",
        "owner_epoch": 1,
    }
    base.update(overrides)
    return base


def issue_pool(**overrides: Any) -> ProtectivePool:
    """Issue a valid :class:`ProtectivePool`."""
    return ProtectivePool.issue(scheme=SCHEME, **pool_required_kwargs(**overrides))


def lease_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Protective-lease issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "lease_id": "lease-1",
        "parent_pool_identity": "pool-1",
        "allowed_scope": "acct-1/ES/BUY",
        "current_owner_identity": "owner-1",
        "lease_owner_epoch": 1,
        "safety_authority_epoch_binding": 1,
        "hard_safety_envelope_version": "h-1",
        "runtime_safety_profile_version": "r-1",
    }
    base.update(overrides)
    return base


def issue_lease(**overrides: Any) -> ProtectiveLease:
    """Issue a valid :class:`ProtectiveLease`."""
    return ProtectiveLease.issue(scheme=SCHEME, **lease_required_kwargs(**overrides))


# ---------------------------------------------------------------------------
# Authoritative Snapshot
# ---------------------------------------------------------------------------


def complete_completeness(**overrides: Any) -> SnapshotCompleteness:
    """A snapshot completeness block with every element present (admissible)."""
    base: dict[str, Any] = {
        "non_terminal_reservations": ("rsv-1",),
        "command_idempotency_keys": ("cmd-1",),
        "generation_fences": FenceCoordinates(
            expected_writer_epoch=1,
            membership_generation=1,
            restore_generation=1,
            expected_revision=1,
        ),
        "capability_use_state": ("cap-1",),
        "proof_gated_release_state": ("rsv-1",),
        "history_commitment": "digest-commit-1",
    }
    base.update(overrides)
    return SnapshotCompleteness(**base)


def snapshot_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Snapshot issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "snapshot_id": "snap-1",
        "cluster_identity": "cluster-1",
        "capacity_domain": "cd-1",
        "writer_epoch": 1,
        "completeness": complete_completeness(),
    }
    base.update(overrides)
    return base


def issue_snapshot(**overrides: Any) -> AuthoritativeSnapshot:
    """Issue a valid :class:`AuthoritativeSnapshot`."""
    return AuthoritativeSnapshot.issue(
        scheme=SCHEME, **snapshot_required_kwargs(**overrides)
    )


# ---------------------------------------------------------------------------
# Committed reservation view (reducer / binding predicate input)
# ---------------------------------------------------------------------------


def committed_reservation(
    *,
    reservation_id: str = "rsv-1",
    revision: int = 1,
    digest: str = "rsv-digest-1",
    increment: CapacityVector | None = None,
    capacity_state: CapacityState = CapacityState.ATTEMPT_BOUND,
    attempt_bound: bool = True,
    attempt_unused: bool = True,
) -> CommittedReservation:
    """A committed-reservation view for the binding / grant predicates."""
    return CommittedReservation(
        reservation_id=reservation_id,
        current_reservation_revision=revision,
        canonical_record_digest=digest,
        adverse_increment=increment if increment is not None else vec(d=10),
        capacity_state=capacity_state,
        attempt_bound=attempt_bound,
        attempt_unused=attempt_unused,
    )
