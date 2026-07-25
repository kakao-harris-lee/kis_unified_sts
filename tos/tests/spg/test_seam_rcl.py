"""MANDATED test-only seam cross-check: spg <-> rcl (design #12 §3.4/§3.5; MAJOR-1).

spg does NOT import ``tos.rcl`` at runtime (the import-closure test asserts its absence);
this file imports **both** as a **test** to lock the effective-limit operand seam. The
central ownership fact (design #12 §3.5 / MAJOR-1): spg produces the **two operand scalars**
(the envelope maximum + the profile operating value); the authoritative
``EffectiveLimit[c] = min(Hard[c], Runtime[c])`` is rcl ``effective_limit`` (``vector.py:139``).
spg performs **no** min — these tests prove spg supplies operands and rcl computes the min,
and that no spg function re-computes it.

A test-only cross-import is NOT a runtime package edge (design #12 §3.4/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.rcl import CapacityComponent, CapacityVector, effective_limit
from tos.spg import envelope_limit_operand, profile_limit_operand

from ._spg_strategies import (
    envelope_dimension,
    issue_envelope,
    issue_profile,
    profile_dimension,
)


def test_spg_produces_two_operand_scalars() -> None:
    """(§3.5) spg produces the envelope-max + profile-value operand scalars for a dimension."""
    env = issue_envelope(
        governed_dimensions=(
            envelope_dimension(dimension="qty", envelope_max=Decimal("10")),
        )
    )
    prof = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty", profile_value=Decimal("5")),
        )
    )
    hard_operand = envelope_limit_operand(env, "qty")
    runtime_operand = profile_limit_operand(prof, "qty")
    assert hard_operand == Decimal("10")
    assert runtime_operand == Decimal("5")


def test_rcl_effective_limit_computes_the_min_not_spg() -> None:
    """(MAJOR-1) The authoritative min is rcl effective_limit — spg supplies operands only.

    spg's two operands are wired into rcl CapacityVectors; rcl's ``effective_limit`` returns
    ``min(10, 5) == 5``. spg never returns the min itself (the operands are the raw 10 / 5).
    """
    env = issue_envelope(
        governed_dimensions=(
            envelope_dimension(dimension="qty", envelope_max=Decimal("10")),
        )
    )
    prof = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty", profile_value=Decimal("5")),
        )
    )
    hard_operand = envelope_limit_operand(env, "qty")
    runtime_operand = profile_limit_operand(prof, "qty")

    hard_vec = CapacityVector(
        components=(CapacityComponent(dimension_id="qty", magnitude=hard_operand),)
    )
    runtime_vec = CapacityVector(
        components=(CapacityComponent(dimension_id="qty", magnitude=runtime_operand),)
    )
    effective = effective_limit(hard_vec, runtime_vec).magnitude("qty")
    assert effective == Decimal("5")  # rcl computed min(10, 5)
    # Neither spg operand is itself the min — spg supplied the raw operands.
    assert hard_operand == Decimal("10")
    assert runtime_operand == Decimal("5")


def test_operand_none_fails_closed_downstream() -> None:
    """(fail-closed §3.5) An undeclared dimension yields a None operand => rcl min is None (UNKNOWN)."""
    env = issue_envelope(governed_dimensions=())  # no 'qty' declared
    prof = issue_profile(
        governed_dimensions=(
            profile_dimension(dimension="qty", profile_value=Decimal("5")),
        )
    )
    hard_operand = envelope_limit_operand(env, "qty")
    runtime_operand = profile_limit_operand(prof, "qty")
    assert hard_operand is None  # undeclared => None (fail-closed)
    assert runtime_operand == Decimal("5")

    hard_vec = CapacityVector(
        components=(CapacityComponent(dimension_id="qty", magnitude=hard_operand),)
    )
    runtime_vec = CapacityVector(
        components=(CapacityComponent(dimension_id="qty", magnitude=runtime_operand),)
    )
    # rcl propagates UNKNOWN (None) — a missing operand never silently becomes the other side.
    assert effective_limit(hard_vec, runtime_vec).magnitude("qty") is None


def test_spg_exposes_no_min_function() -> None:
    """(MAJOR-1) spg exposes no effective-limit / min re-computation — only operand producers."""
    import tos.spg as spg

    banned = ("effective_limit", "min_limit", "effective", "reduce_limit")
    for name in dir(spg):
        for token in banned:
            assert token not in name.lower(), f"spg unexpectedly exposes {name}"
