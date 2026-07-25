"""MANDATED test-only seam cross-check: protective <-> authority (design #11 §3.4).

protective does NOT import ``tos.authority`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock the produced-value seam. authority
already declared the injected coordinates protective fills:

* ``protective_classification_present`` — condition 1 of ``degraded_lease_valid``
  (``authority/predicates.py:513``, ``is not True`` fail-closed at :513). protective's
  :func:`~tos.protective.predicates.protective_classification_present` produces the ``bool`` it
  consumes; a ``False`` fails the lease-validity closed on the rejecting side.
* ``protective_capacity_exhausted`` — an invalidating event of ``degraded_lease_invalidated``
  (``authority/predicates.py:639``, ``is not False`` firing at :639 — ``True`` / ``None``
  invalidates). protective's :func:`~tos.protective.predicates.protective_capacity_exhausted`
  produces the firing ``bool``.

Both directions are asserted (rejecting / firing side **and** the legitimate passing side).
This test is NOT a runtime package edge (design #11 §3.4/§7.1).
"""

from __future__ import annotations

import inspect
from decimal import Decimal

from tos.authority import (
    AuthorityState,
    degraded_lease_invalidated,
    degraded_lease_valid,
)
from tos.protective import (
    protective_capacity_exhausted,
    protective_classification_present,
)

from ..authority._authority_strategies import anchor, issue_lease, valid_lease_kwargs
from ._protective_strategies import (
    issue_profile,
    proven_comparison,
    proven_intermediate,
)


def _invalidation_kwargs(**overrides: object) -> dict[str, object]:
    """Kwargs for ``degraded_lease_invalidated`` describing an otherwise still-valid lease."""
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


# ---------------------------------------------------------------------------
# signature integrity
# ---------------------------------------------------------------------------


def test_authority_declares_the_two_injected_protective_conditions() -> None:
    """(§3.4) authority's two degraded-lease predicates declare the protective-produced flags."""
    valid_params = inspect.signature(degraded_lease_valid).parameters
    assert "protective_classification_present" in valid_params
    invalidated_params = inspect.signature(degraded_lease_invalidated).parameters
    assert "protective_capacity_exhausted" in invalidated_params


# ---------------------------------------------------------------------------
# protective_classification_present -> degraded_lease_valid (both ways)
# ---------------------------------------------------------------------------


def test_classification_false_fails_degraded_lease_valid_closed() -> None:
    """protective classification not proven => degraded_lease_valid False (rejecting side)."""
    lease = issue_lease()
    # A move whose final risk is ABOVE current is not protective (RISK_INCREASING_DENIED).
    present = protective_classification_present(
        proven_comparison(
            final_conservative_risk=Decimal("9.0"),
            current_conservative_risk=Decimal("5.0"),
        ),
        proven_intermediate(),
        envelope_within_hard=True,
    )
    assert present is False
    kwargs = valid_lease_kwargs(protective_classification_present=present)
    assert degraded_lease_valid(lease, [lease], **kwargs) is False


def test_classification_true_permits_degraded_lease_valid() -> None:
    """(both-ways) A proven protective classification => degraded_lease_valid True (passing side)."""
    lease = issue_lease()
    present = protective_classification_present(
        proven_comparison(), proven_intermediate(), envelope_within_hard=True
    )
    assert present is True
    kwargs = valid_lease_kwargs(protective_classification_present=present)
    # With every other condition valid, only the protective flag is under test — it passes.
    assert degraded_lease_valid(lease, [lease], **kwargs) is True


def test_classification_is_plain_bool_matching_injected_flag() -> None:
    """protective emits a plain ``bool`` (type-matches authority's ``bool | None`` slot)."""
    present = protective_classification_present(
        proven_comparison(), proven_intermediate(), envelope_within_hard=True
    )
    assert isinstance(present, bool)


# ---------------------------------------------------------------------------
# protective_capacity_exhausted -> degraded_lease_invalidated (both ways)
# ---------------------------------------------------------------------------


def test_exhausted_true_invalidates_degraded_lease() -> None:
    """protective capacity exhausted (True) => degraded_lease_invalidated True (firing side)."""
    lease = issue_lease()
    # An empty-declarations profile => every required domain UNAVAILABLE => exhausted.
    exhausted = protective_capacity_exhausted(
        issue_profile(declarations=()), budget_remaining=5
    )
    assert exhausted is True
    kwargs = _invalidation_kwargs(protective_capacity_exhausted=exhausted)
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


def test_exhausted_none_invalidates_degraded_lease() -> None:
    """(fail-closed) A None exhaustion flag also invalidates (positively-provable validity)."""
    lease = issue_lease()
    kwargs = _invalidation_kwargs(protective_capacity_exhausted=None)
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is True


def test_not_exhausted_does_not_invalidate_on_this_axis() -> None:
    """(both-ways) Not exhausted (False) => not invalidated on the protective-capacity axis."""
    lease = issue_lease()
    not_exhausted = protective_capacity_exhausted(issue_profile(), budget_remaining=5)
    assert not_exhausted is False
    kwargs = _invalidation_kwargs(protective_capacity_exhausted=not_exhausted)
    assert degraded_lease_invalidated(lease, [lease], **kwargs) is False
