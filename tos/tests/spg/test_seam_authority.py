"""MANDATED test-only seam cross-check: spg <-> authority (design #12 §3.4).

spg does NOT import ``tos.authority`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock the produced-value seam:

* ``hard_envelope_incompatible`` — an injected event flag of authority
  ``degraded_lease_invalidated`` (``predicates.py:640``) where ``is not False`` invalidates
  (``predicates.py:701``). spg :func:`~tos.spg.envelope_incompatible` produces the ``bool``;
  a ``True`` (incompatible / unknown) invalidates the dependent lease (fail-closed polarity).
* ``hard_safety_envelope_version`` / ``runtime_safety_profile_version`` — the scalar version
  coordinates covered on ``SafetyAuthorityCapability`` (``records.py:113-114``), filled by
  spg :func:`~tos.spg.active_envelope_version` / :func:`~tos.spg.active_profile_version`.

Causal isolation: a still-valid (non-invalidated) lease scenario is held fixed and **only**
``hard_envelope_incompatible`` is driven by spg's produced bool — so the invalidation is
attributable to the injected envelope-incompatibility flag. A test-only cross-import of
another test package's strategies is NOT a runtime package edge (design #12 §3.4/§7.1).
"""

from __future__ import annotations

import inspect

from tos.authority import (
    AuthorityState,
    SafetyAuthorityCapability,
    degraded_lease_invalidated,
)
from tos.spg import (
    active_envelope_version,
    active_profile_version,
    envelope_incompatible,
)

from ..authority._authority_strategies import anchor, issue_lease
from ._spg_strategies import issue_envelope, issue_profile


def _valid_invalidation_kwargs(**overrides: object) -> dict[str, object]:
    """Kwargs for ``degraded_lease_invalidated`` describing a still-valid lease (not invalidated).

    Mirrors the authority suite's own non-invalidated fixture; ``hard_envelope_incompatible``
    defaults to ``False`` (not incompatible) so the baseline lease is valid.
    """
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


def test_hard_envelope_incompatible_is_a_lease_invalidation_input() -> None:
    """(§3.4 signature integrity) degraded_lease_invalidated accepts hard_envelope_incompatible."""
    params = inspect.signature(degraded_lease_invalidated).parameters
    assert "hard_envelope_incompatible" in params


def test_spg_incompatible_true_causally_invalidates_lease() -> None:
    """(causal isolation) A still-valid lease is invalidated ONLY when spg's bool flips to True.

    Baseline: a matching envelope generation => envelope_incompatible False => lease valid.
    Then a mismatched presented generation => envelope_incompatible True => lease invalidated
    (authority ``is not False`` polarity, ``predicates.py:701``).
    """
    lease = issue_lease()
    env = issue_envelope(envelope_generation=5)

    compatible = envelope_incompatible(env, 5)  # False
    incompatible = envelope_incompatible(env, 4)  # True (stale presented generation)
    assert compatible is False and incompatible is True

    # Baseline: the guard is genuinely not invalidated with the compatible (False) flag.
    assert (
        degraded_lease_invalidated(
            lease,
            [lease],
            **_valid_invalidation_kwargs(hard_envelope_incompatible=compatible),
        )
        is False
    )
    # Flipping ONLY the spg-produced incompatibility to True invalidates the lease.
    assert (
        degraded_lease_invalidated(
            lease,
            [lease],
            **_valid_invalidation_kwargs(hard_envelope_incompatible=incompatible),
        )
        is True
    )


def test_none_presented_generation_invalidates_fail_closed() -> None:
    """(fail-closed) spg envelope_incompatible(None presented) => True => lease invalidated."""
    lease = issue_lease()
    env = issue_envelope(envelope_generation=5)
    produced = envelope_incompatible(env, None)
    assert produced is True
    assert (
        degraded_lease_invalidated(
            lease,
            [lease],
            **_valid_invalidation_kwargs(hard_envelope_incompatible=produced),
        )
        is True
    )


def test_scalar_versions_fill_authority_capability_fields() -> None:
    """(§3.4 scalar seam) active_envelope_version / active_profile_version fill the covered fields."""
    env = issue_envelope()
    prof = issue_profile()
    e_version = active_envelope_version(env)
    p_version = active_profile_version(prof)
    assert isinstance(e_version, str) and isinstance(p_version, str)
    assert "hard_safety_envelope_version" in SafetyAuthorityCapability.model_fields
    assert "runtime_safety_profile_version" in SafetyAuthorityCapability.model_fields
    cap = SafetyAuthorityCapability(
        hard_safety_envelope_version=e_version,
        runtime_safety_profile_version=p_version,
    )
    assert cap.hard_safety_envelope_version == e_version
    assert cap.runtime_safety_profile_version == p_version
