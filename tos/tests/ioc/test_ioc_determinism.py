"""compiler_deterministic + numerical_safety (design #14 §4.2/§5.2; IOC-EV-003 substrate).

The compiler-determinism property (the near-tautology digest equality, plus the load-bearing
hermetic + denial-is-total + generation-fence discipline) and the numerical-safety axis. Closes
no IOC-EV (§9 line 268 hidden-input absence is enforced by the §7.1 import-closure test, not
here). Consume gate for ``numerical_safety`` is ``is ConformanceResult.CONFORMANT`` (§4.7).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.canonical import ArtifactIntegrityError
from tos.ioc import (
    AxisBinding,
    ConformanceAxis,
    ConformanceResult,
    compile_command,
    compiler_deterministic,
    numerical_safety,
)

from ._ioc_strategies import (
    AUTHORIZED_AXES,
    SCHEME,
    issue_envelope,
    issue_intent,
    issue_policy,
)

# ---------------------------------------------------------------------------
# compiler determinism — same complete inputs => same canonical digest (§4.2)
# ---------------------------------------------------------------------------

#: Strategy over per-axis registry values so a random-but-valid intent/envelope agree on values.
_AXIS_VALUE = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789", min_size=1, max_size=6
)


@given(
    values=st.fixed_dictionaries(dict.fromkeys(AUTHORIZED_AXES, _AXIS_VALUE)),
    generation=st.integers(min_value=1, max_value=1000),
)
def test_compile_is_digest_deterministic(
    values: dict[ConformanceAxis, str], generation: int
) -> None:
    """(§4.2 property) The same complete inputs compile to the same canonical digest."""
    intent = issue_intent(values)
    envelope = issue_envelope(values)
    policy = issue_policy()
    first = compile_command(
        intent=intent,
        policy=policy,
        envelope=envelope,
        generation=generation,
        scheme=SCHEME,
        command_id="cmd-a",
    )
    second = compile_command(
        intent=intent,
        policy=policy,
        envelope=envelope,
        generation=generation,
        scheme=SCHEME,
        command_id="cmd-b",  # different id — excluded from digest, so digest must still match
    )
    assert first.canonical_digest is not None
    assert first.canonical_digest == second.canonical_digest
    assert compiler_deterministic(
        intent=intent,
        policy=policy,
        envelope=envelope,
        generation=generation,
        scheme=SCHEME,
    )


def test_compiler_deterministic_positive_side() -> None:
    """(canary +) A complete, conformant input set is compiler-deterministic."""
    assert (
        compiler_deterministic(
            intent=issue_intent(),
            policy=issue_policy(),
            envelope=issue_envelope(),
            generation=1,
            scheme=SCHEME,
        )
        is True
    )


# ---------------------------------------------------------------------------
# denial is total (§9 line 270) — no best-effort / fallback
# ---------------------------------------------------------------------------


def test_missing_axis_denies_no_fallback() -> None:
    """(canary 'fallback' §9 line 270) An axis absent on the intent => construction raises (denial)."""
    dropped = {**AUTHORIZED_AXES, ConformanceAxis.SIDE: None}
    try:
        compile_command(
            intent=issue_intent(dropped),
            policy=issue_policy(),
            envelope=issue_envelope(),
            generation=1,
            scheme=SCHEME,
            command_id="cmd-x",
        )
    except ArtifactIntegrityError:
        pass
    else:
        raise AssertionError(
            "compile must deny an undetermined axis, never fall back (§9 line 270)"
        )


def test_absent_envelope_denies_construction() -> None:
    """(∅ §5.3 line 125) An open-ended (empty) envelope raises — permits no construction."""
    try:
        compile_command(
            intent=issue_intent(),
            policy=issue_policy(),
            envelope=issue_envelope(values={}),
            generation=1,
            scheme=SCHEME,
            command_id="cmd-x",
        )
    except ArtifactIntegrityError:
        pass
    else:
        raise AssertionError(
            "an open-ended envelope permits no construction (§5.3 line 125)"
        )


def test_deterministic_denial_is_deterministic() -> None:
    """(§4.2 denial-is-total) A deterministically-denying input set is 'deterministic' (both deny)."""
    dropped = {**AUTHORIZED_AXES, ConformanceAxis.SIDE: None}
    assert (
        compiler_deterministic(
            intent=issue_intent(dropped),
            policy=issue_policy(),
            envelope=issue_envelope(),
            generation=1,
            scheme=SCHEME,
        )
        is True
    )


def test_value_outside_envelope_denies() -> None:
    """(§9) An intent value disagreeing with the envelope's authorized value => denial."""
    intent = issue_intent({**AUTHORIZED_AXES, ConformanceAxis.ACCOUNT: "ACCT-OTHER"})
    try:
        compile_command(
            intent=intent,
            policy=issue_policy(),
            envelope=issue_envelope(),  # authorizes ACCT-1
            generation=1,
            scheme=SCHEME,
            command_id="cmd-x",
        )
    except ArtifactIntegrityError:
        pass
    else:
        raise AssertionError(
            "a value outside the authorized envelope must be denied (§9)"
        )


# ---------------------------------------------------------------------------
# numerical_safety (§5.2 / §11 line 301 / §14 line 423)
# ---------------------------------------------------------------------------


def test_finite_consistent_magnitudes_are_conformant() -> None:
    """(canary +) Finite magnitudes with consistent units => CONFORMANT."""
    result = numerical_safety([Decimal("1.00"), Decimal("2.50")], units_consistent=True)
    assert result is ConformanceResult.CONFORMANT


def test_inconsistent_units_are_non_conformant() -> None:
    """(canary - 'coerce' §11 line 301) A definite unit / scale mismatch => NON_CONFORMANT."""
    result = numerical_safety([Decimal("1")], units_consistent=False)
    assert result is ConformanceResult.NON_CONFORMANT


def test_unknown_units_are_unknown() -> None:
    """(fail-closed) Unknown (None) unit consistency => UNKNOWN."""
    result = numerical_safety([Decimal("1")], units_consistent=None)
    assert result is ConformanceResult.UNKNOWN


def test_empty_magnitudes_are_unknown() -> None:
    """(∅ §4.7) A vacuous 'safe over nothing' is not safety => UNKNOWN."""
    result = numerical_safety([], units_consistent=True)
    assert result is ConformanceResult.UNKNOWN


def test_none_magnitude_is_unknown() -> None:
    """(fail-closed) A missing (None) magnitude => UNKNOWN (never a smaller permissive value)."""
    result = numerical_safety([Decimal("1"), None], units_consistent=True)
    assert result is ConformanceResult.UNKNOWN


# ---------------------------------------------------------------------------
# MAJOR-1 regression — compile denies an ambiguous (duplicate-axis) envelope / intent
# ---------------------------------------------------------------------------


def _dup_bindings() -> tuple[AxisBinding, ...]:
    """The full clean bindings + a duplicate SIDE binding (an ambiguous authorization)."""
    return tuple(
        AxisBinding(axis=axis, value=value) for axis, value in AUTHORIZED_AXES.items()
    ) + (
        AxisBinding(axis=ConformanceAxis.SIDE, value="BUY"),
    )


def test_duplicate_envelope_axis_denies_compile() -> None:
    """(§10 line 284 / denial-is-total) An ambiguous (duplicate-axis) envelope denies compilation.

    Resolves the ``authorized_axes`` last-wins collapse: compile raises rather than silently
    picking one authorized value.
    """
    dup_env = issue_envelope(authorized_axis_bindings=_dup_bindings())
    try:
        compile_command(
            intent=issue_intent(),
            policy=issue_policy(),
            envelope=dup_env,
            generation=1,
            scheme=SCHEME,
            command_id="cmd-x",
        )
    except ArtifactIntegrityError:
        pass
    else:
        raise AssertionError(
            "an ambiguous (duplicate-axis) envelope must deny compilation"
        )


def test_duplicate_intent_axis_denies_compile() -> None:
    """(§14 line 406 / denial-is-total) An ambiguous (duplicate-axis) intent denies compilation."""
    dup_intent = issue_intent(authorized_axis_bindings=_dup_bindings())
    try:
        compile_command(
            intent=dup_intent,
            policy=issue_policy(),
            envelope=issue_envelope(),
            generation=1,
            scheme=SCHEME,
            command_id="cmd-x",
        )
    except ArtifactIntegrityError:
        pass
    else:
        raise AssertionError(
            "an ambiguous (duplicate-axis) intent must deny compilation"
        )
