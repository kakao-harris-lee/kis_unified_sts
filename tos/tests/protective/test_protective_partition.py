"""§9 partition-time lease-admissibility (design #11 §6.2; ADR line 448 "ADR-002-001 owns").

Overlap-first / add-only within a pre-proven scope + staleness + a valid lease => ADMISSIBLE;
cancel-first / removal outside scope or past staleness => TRAPPED (conservatively covered, not
transmitted on stale admissibility); no valid lease => PROHIBITED; an unknown partition verdict
=> TRAPPED. RC-EV-012 / SA-EV-004 / PR-EV-001/002 substrate — closes nothing.
"""

from __future__ import annotations

from typing import TypedDict, Unpack

from tos.protective import (
    Admissibility,
    ProtectiveActionKind,
    partition_lease_admissible,
)

from ._protective_strategies import lease_scope

_ADD_ONLY = ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY
_CANCEL_FIRST = ProtectiveActionKind.CANCEL_FIRST_OR_REMOVAL


class _AdmissibleKwargs(TypedDict):
    """1:1 with :func:`partition_lease_admissible`'s keyword-only signature (plan §1.1
    A-fn) — a ``**_admissible_kwargs(...)`` splat is checked key-by-key and type-by-type,
    not swallowed by a ``**dict[str, object]`` splat."""

    within_pre_proven_scope: bool | None
    staleness_ok: bool | None
    lease_valid_for_new_transmission: bool | None
    partition_new_commitment_denied: bool | None


class _AdmissibleKwargsPartial(TypedDict, total=False):
    """Same fields as :class:`_AdmissibleKwargs`, all optional — the override-kwargs
    shape for :func:`_admissible_kwargs`."""

    within_pre_proven_scope: bool | None
    staleness_ok: bool | None
    lease_valid_for_new_transmission: bool | None
    partition_new_commitment_denied: bool | None


def _admissible_kwargs(
    **overrides: Unpack[_AdmissibleKwargsPartial],
) -> _AdmissibleKwargs:
    base: _AdmissibleKwargs = {
        "within_pre_proven_scope": True,
        "staleness_ok": True,
        "lease_valid_for_new_transmission": True,
        "partition_new_commitment_denied": True,
    }
    base.update(overrides)
    return base


def test_overlap_first_in_scope_is_admissible() -> None:
    """(§9 line 448 canary b) Add-only within scope + fresh + valid lease => ADMISSIBLE."""
    verdict = partition_lease_admissible(
        _ADD_ONLY, lease_scope(), **_admissible_kwargs()
    )
    assert verdict is Admissibility.ADMISSIBLE


def test_cancel_first_outside_scope_is_trapped() -> None:
    """(§9 line 448 canary a) Cancel-first outside the pre-proven scope => TRAPPED."""
    verdict = partition_lease_admissible(
        _CANCEL_FIRST,
        lease_scope(),
        **_admissible_kwargs(within_pre_proven_scope=False),
    )
    assert verdict is Admissibility.TRAPPED


def test_cancel_first_even_in_scope_is_trapped() -> None:
    """(§9 line 448) A cancel-first / removal action cannot proceed on a lease during partition."""
    verdict = partition_lease_admissible(
        _CANCEL_FIRST, lease_scope(), **_admissible_kwargs()
    )
    assert verdict is Admissibility.TRAPPED


def test_stale_add_only_is_trapped() -> None:
    """(§9 line 448) Add-only past staleness (None) => TRAPPED (no stale-admissibility send)."""
    verdict = partition_lease_admissible(
        _ADD_ONLY, lease_scope(), **_admissible_kwargs(staleness_ok=None)
    )
    assert verdict is Admissibility.TRAPPED


def test_out_of_scope_add_only_is_trapped() -> None:
    """(§9 line 448) Add-only outside the pre-proven scope => TRAPPED."""
    verdict = partition_lease_admissible(
        _ADD_ONLY, lease_scope(), **_admissible_kwargs(within_pre_proven_scope=None)
    )
    assert verdict is Admissibility.TRAPPED


def test_no_valid_lease_is_prohibited() -> None:
    """(§9 canary) No valid lease (None / False) => PROHIBITED."""
    for value in (None, False):
        verdict = partition_lease_admissible(
            _ADD_ONLY,
            lease_scope(),
            **_admissible_kwargs(lease_valid_for_new_transmission=value),
        )
        assert verdict is Admissibility.PROHIBITED


def test_unknown_partition_verdict_is_trapped() -> None:
    """(§9 / §12.2) An unknown rcl partition new-commitment verdict (None) => TRAPPED."""
    verdict = partition_lease_admissible(
        _ADD_ONLY,
        lease_scope(),
        **_admissible_kwargs(partition_new_commitment_denied=None),
    )
    assert verdict is Admissibility.TRAPPED


def test_none_scope_marker_does_not_widen_admissibility() -> None:
    """(§9) A None scope marker never widens admissibility (verdicts are injected)."""
    # A None scope with all verdicts positive still ADMISSIBLE (scope is representation only),
    # but a None scope can never *rescue* an out-of-scope verdict.
    assert (
        partition_lease_admissible(_ADD_ONLY, None, **_admissible_kwargs())
        is Admissibility.ADMISSIBLE
    )
    assert (
        partition_lease_admissible(
            _ADD_ONLY, None, **_admissible_kwargs(within_pre_proven_scope=None)
        )
        is Admissibility.TRAPPED
    )
