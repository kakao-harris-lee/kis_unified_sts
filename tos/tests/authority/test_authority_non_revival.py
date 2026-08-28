"""Non-revival + structural absences + append-only (§4.1-§4.5; SA-INV-004/011).

The model provides NO operation that revives an invalidated capability / lease, decreases
or reuses an epoch, releases capacity from an epoch advance, derives a blind cancel-all,
or grants a grace period; records are frozen with no lifecycle mutator; and every authority
artifact's authority_effect is all-false (authority != enforcement).
"""

from __future__ import annotations

import pytest
import tos.authority as authority
from pydantic import ValidationError
from tos.authority import (
    AuthorityEffect,
    recovery_generation_revives_nothing,
)

from ._authority_strategies import issue_capability, issue_lease, issue_transition


def test_recovery_generation_revives_nothing() -> None:
    """A new generation never revives an earlier invalidation (always True; SA-INV-011)."""
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=1, new_generation=5
        )
        is True
    )
    assert (
        recovery_generation_revives_nothing(
            invalidated_under_generation=None, new_generation=None
        )
        is True
    )


def test_no_revive_or_rearm_restoring_operation_exists() -> None:
    """(canary §4.4) The package exposes no 'generation/epoch increase => validity restored' op.

    The only name mentioning revival is ``recovery_generation_revives_nothing`` — the
    predicate that *documents* the absence (returns True) — not a revive / re-arm-restore
    operation. ``rearm_gate`` is non-authorizing (its verdict is all-false), not a restore.
    """
    revive_names = [
        name
        for name in dir(authority)
        if name != "recovery_generation_revives_nothing"
        and any(
            token in name.lower()
            for token in ("revive", "reactivate", "restore_authority", "uninvalidate")
        )
    ]
    assert revive_names == []


def test_no_epoch_decrease_release_or_cancel_all_operation_exists() -> None:
    """(canary §4.2/§5.5) No epoch-decrease, capacity-release, cancel-all, or grace operation."""
    forbidden = [
        name
        for name in dir(authority)
        if any(
            token in name.lower()
            for token in (
                "advance_epoch",
                "decrease_epoch",
                "reuse_epoch",
                "release_capacity",
                "cancel_all",
                "grace",
                "reconstruct",
            )
        )
    ]
    assert forbidden == [], f"unexpected operation surface: {forbidden}"


def test_epoch_advance_does_not_release_economic_effect() -> None:
    """(canary SA-INV-004) There is no operation mapping an epoch advance to a capacity release.

    RCL capacity is referenced only by scalar; the authority package has no function that
    consumes an epoch and mutates / releases any capacity coordinate.
    """
    epoch_ops = [
        name
        for name in dir(authority)
        if "epoch" in name.lower()
        and ("release" in name.lower() or "cancel" in name.lower())
    ]
    assert epoch_ops == []


def test_records_are_frozen() -> None:
    """An issued authority record cannot be mutated in place (frozen; append-only §2.0)."""
    capability = issue_capability()
    with pytest.raises(ValidationError):
        capability.capability_type = None  # type: ignore[misc]


def test_no_update_or_delete_methods_on_records() -> None:
    """No authority record exposes a lifecycle-mutation method (append-only §2.0/§19)."""
    for record in (issue_capability(), issue_transition(), issue_lease()):
        forbidden = [
            name
            for name in dir(record)
            if not name.startswith("_")
            and any(
                token in name.lower()
                for token in (
                    "delete",
                    "mutate",
                    "release",
                    "revoke",
                    "reassign",
                    "revive",
                )
            )
        ]
        assert forbidden == [], f"{type(record).__name__} mutation surface: {forbidden}"


def test_every_record_authority_effect_is_all_false() -> None:
    """(canary §4.1) Every authority ledger citizen grants no runtime effect (all-false)."""
    for record in (issue_capability(), issue_transition(), issue_lease()):
        effect = getattr(record, "authority_effect", None)
        if effect is None:
            continue  # not every record carries one; those that do must be all-false
        assert all(getattr(effect, name) is False for name in type(effect).model_fields)
    # The capability carries an explicit AuthorityEffect and it is all-false.
    cap_effect = issue_capability().authority_effect
    assert all(
        getattr(cap_effect, name) is False for name in type(cap_effect).model_fields
    )


def test_authority_effect_rejects_any_true_flag() -> None:
    """(canary §4.1) Any True authority flag makes the block unconstructable (SA-INV-003)."""
    for flag in (
        "is_current_authority_by_possession",
        "self_transmits",
        "self_mutates_capacity",
        "self_releases_capacity",
        "self_rearms",
    ):
        with pytest.raises(ValidationError):
            AuthorityEffect(**{flag: True})
