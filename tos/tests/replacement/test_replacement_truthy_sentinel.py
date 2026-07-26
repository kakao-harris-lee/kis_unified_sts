"""Truthy-sentinel + **polarity-split** properties (design #18 §0.1(j) / §10.2(10)).

The v1.1 C1 lesson is that a single polarity is not enough. Three shapes cross this
package's surface and each needs a *different* gate:

1. **truthy StrEnums** — ``ReplacementOutcome`` (5 members) and the injected protective
   ``Admissibility`` (3 members). Every member is truthy, so only an identity / single-token
   test may pass.
2. **positive-polarity ``bool | None``** (safe value ``True``) — ``within_hard_envelope``,
   ``new_protection_sufficiency_current``, ``protective_classification_present``,
   ``cancellation_admissible``, ``leg_admissibility``, ``fill_recognized``,
   ``economic_effect_persists``. Gate: ``is True``.
3. **negative-polarity ``bool | None``** (safe value ``False``) —
   ``hides_uncovered_or_reversing``, ``material_change``, ``expired``,
   ``became_risk_increasing``, ``bound_exceeded``, ``economic_effect_release_claimed``.
   Gate: ``is False`` **only**. Writing ``is not True`` on one of these lets ``None``
   through, which is the exact v1.0 fail-open.

Behavioural properties drive the real predicates; a **source-level AST scan** then proves
the shapes are absent from the code itself, and planted-offender canaries prove the scans
are not vacuous.
"""

from __future__ import annotations

import ast
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    ReplacementMode,
    ReplacementOutcome,
    no_hiding_clamp,
    overlap_first_reservation_complete,
    overlap_first_sequencing_valid,
    partial_fill_egress_disposition,
    partition_replacement_admissible,
    replacement_authorization_current,
    replacement_mode_admissible,
)

from ._replacement_strategies import (
    ALL_OUTCOMES,
    NON_FALSE_VALUES,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    clean_claim,
    clean_mode_inputs,
    clean_sequencing_inputs,
)

_REPLACEMENT_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "replacement"
)

#: The negative-polarity parameter names: safe value ``False``, so an ``is not True``
#: comparison against any of them would be the v1.0 fail-open (design #18 §10.2(10)).
_NEGATIVE_POLARITY_NAMES = frozenset(
    {
        "hides_uncovered_or_reversing",
        "material_change",
        "expired",
        "became_risk_increasing",
        "bound_exceeded",
        "economic_effect_release_claimed",
        "netting_applied",  # the removed v1.0 flag — must never come back
    }
)

#: Result-shaped locals that must be identity-gated, never truthiness-gated.
_RESULT_SHAPED_NAMES = frozenset(
    {
        "outcome",
        "result",
        "verdict",
        "mode",
        "partition_lease_verdict",
        "leg_admissibility",
        "within_hard_envelope",
        "cancellation_admissible",
        "new_protection_sufficiency_current",
        "protective_classification_present",
        "atomic_proven",
        "fill_recognized",
        "economic_effect_persists",
    }
)


# ===========================================================================
# Axis 1 — truthy StrEnum identity gating
# ===========================================================================


def test_every_replacement_outcome_member_is_truthy() -> None:
    """(the trap itself) A bare ``if outcome:`` would admit DENIED / UNKNOWN / TRAPPED."""
    for member in ReplacementOutcome:
        assert (
            bool(member) is True
        ), f"{member} is truthy — identity gating is mandatory"


@given(mode=st.sampled_from(list(ReplacementMode)))
def test_only_a_positive_conjunction_yields_the_admissible_member(
    mode: ReplacementMode,
) -> None:
    """(#16 CRITICAL) ADMISSIBLE is a proven identity, never a fall-through residue."""
    unproven = clean_mode_inputs(
        atomic_proven=None,
        overlap_reservation_complete=None,
        overlap_sequencing_valid=None,
        cancel_first_gate_passed=None,
    )
    assert (
        replacement_mode_admissible(mode, **unproven)
        is not ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


def test_raw_outcome_strings_are_not_the_members() -> None:
    """(the trap itself) A ``StrEnum`` member equals its value but is not it under ``is``."""
    for member in ReplacementOutcome:
        assert member == member.value
        assert member is not member.value


def test_only_the_admissible_admissibility_token_passes_the_partition_gate() -> None:
    """(axis 1, injected) ``TRAPPED`` / ``PROHIBITED`` are truthy but must never pass."""
    assert (
        partition_replacement_admissible(
            "ADMISSIBLE", mode=ReplacementMode.OVERLAP_FIRST
        )
        is True
    )
    for token in ("TRAPPED", "PROHIBITED"):
        assert bool(token) is True, "the trap: a non-admissible verdict is still truthy"
        assert (
            partition_replacement_admissible(token, mode=ReplacementMode.OVERLAP_FIRST)
            is False
        )
    assert (
        partition_replacement_admissible(None, mode=ReplacementMode.OVERLAP_FIRST)
        is False
    )


# ===========================================================================
# Axis 2 — positive polarity (``is True`` only)
# ===========================================================================


@given(flag=TRIBOOL)
def test_positive_polarity_fields_pass_only_on_true(flag: bool | None) -> None:
    """(axis 2) ``False`` and ``None`` both block every positive-polarity conjunct."""
    for conjunct in (
        "new_protection_sufficiency_current",
        "protective_classification_present",
        "cancellation_admissible",
        "leg_admissibility",
    ):
        result = overlap_first_sequencing_valid(
            **clean_sequencing_inputs(**{conjunct: flag})
        )
        assert result is (flag is True)


@given(forged=st.sampled_from(TRUTHY_NON_BOOL))
def test_a_truthy_non_bool_never_satisfies_a_positive_polarity_field(
    forged: object,
) -> None:
    """(axis 2) ``1`` / ``"UNKNOWN"`` / ``[1]`` are truthy but are not the singleton."""
    for conjunct in (
        "new_protection_sufficiency_current",
        "protective_classification_present",
        "cancellation_admissible",
        "leg_admissibility",
    ):
        assert (
            overlap_first_sequencing_valid(
                **clean_sequencing_inputs(**{conjunct: forged})
            )
            is False
        )
    assert (
        overlap_first_reservation_complete(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=forged,  # type: ignore[arg-type]
        )
        is False
    )


# ===========================================================================
# Axis 3 — negative polarity (``is False`` only; the v1.1 C1 regression)
# ===========================================================================


@given(non_false=st.sampled_from(NON_FALSE_VALUES))
def test_negative_polarity_fields_are_not_cleared_by_a_non_false_value(
    non_false: object,
) -> None:
    """(axis 3, C1) An ``is not True`` gate would clear every one of these; ``is False`` does not."""
    # hides_uncovered_or_reversing
    assert (
        no_hiding_clamp(
            clamp_applied=True,
            hides_uncovered_or_reversing=non_false,  # type: ignore[arg-type]
        )
        is False
    )
    # became_risk_increasing
    assert (
        partial_fill_egress_disposition(
            became_risk_increasing=non_false,  # type: ignore[arg-type]
            already_transmitted=False,
        )
        is not ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )
    # material_change / expired
    assert (
        replacement_authorization_current(
            material_change=non_false,  # type: ignore[arg-type]
            expired=False,
            economic_effect_persists=True,
        )
        is False
    )
    assert (
        replacement_authorization_current(
            material_change=False,
            expired=non_false,  # type: ignore[arg-type]
            economic_effect_persists=True,
        )
        is False
    )
    # bound_exceeded
    assert (
        replacement_mode_admissible(
            ReplacementMode.OVERLAP_FIRST,
            **clean_mode_inputs(bound_exceeded=non_false),
        )
        is ReplacementOutcome.REPLACEMENT_CONTAINED
    )


# ===========================================================================
# Source-level scans + planted-offender canaries
# ===========================================================================


def _negative_polarity_is_not_true_offenders(path: Path) -> list[str]:
    """Return ``<negative-polarity name> is not True`` comparisons (AST)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name):
            continue
        if node.left.id not in _NEGATIVE_POLARITY_NAMES:
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, ast.IsNot):
                continue
            if isinstance(comparator, ast.Constant) and comparator.value is True:
                offenders.append(
                    f"{path.name}:{node.lineno} {node.left.id} is not True "
                    "(negative polarity — None would pass; use `is False`)"
                )
    return offenders


def test_no_source_uses_is_not_true_on_a_negative_polarity_field() -> None:
    """(C1 source seal) The v1.0 fail-open shape is absent from every module."""
    sources = sorted(_REPLACEMENT_SRC.rglob("*.py"))
    assert sources, f"no tos.replacement source files found under {_REPLACEMENT_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_negative_polarity_is_not_true_offenders(path))
    assert offenders == [], f"negative-polarity fail-open reachable: {offenders}"


def test_negative_polarity_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The scan actually catches ``material_change is not True``."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(material_change, bound_exceeded):\n"
        "    if material_change is not True:\n"
        "        return False\n"
        "    return bound_exceeded is not True\n",
        encoding="utf-8",
    )
    offenders = _negative_polarity_is_not_true_offenders(planted)
    joined = " ".join(offenders)
    assert "material_change is not True" in joined
    assert "bound_exceeded is not True" in joined


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a result-shaped local (AST)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        if isinstance(test, ast.Name) and test.id in _RESULT_SHAPED_NAMES:
            offenders.append(f"{path.name}:{node.lineno} bare truthiness on {test.id}")
    return offenders


def test_no_source_uses_bare_truthiness_on_a_result_value() -> None:
    """(source seal) No module tests a result-shaped value for bare truthiness."""
    sources = sorted(_REPLACEMENT_SRC.rglob("*.py"))
    assert sources
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_bare_truthiness_offenders(path))
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"


def test_bare_truthiness_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan actually catches a planted ``if outcome:``."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(outcome):\n    if outcome:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truthiness_offenders(planted) != []


def _equality_gated_enum_offenders(path: Path) -> list[str]:
    """Return ``<name> == ReplacementOutcome.X`` / ``== ReplacementMode.X`` comparisons."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, (ast.Eq, ast.NotEq)):
                continue
            if (
                isinstance(comparator, ast.Attribute)
                and isinstance(comparator.value, ast.Name)
                and comparator.value.id in {"ReplacementOutcome", "ReplacementMode"}
            ):
                offenders.append(
                    f"{path.name}:{node.lineno} equality-gated "
                    f"{comparator.value.id}.{comparator.attr} (use `is` — a raw string "
                    "compares equal to a StrEnum member)"
                )
    return offenders


def test_no_source_equality_gates_a_replacement_strenum() -> None:
    """(identity seal) A raw ``"OVERLAP_FIRST"`` must not pass a mode gate."""
    offenders: list[str] = []
    for path in sorted(_REPLACEMENT_SRC.rglob("*.py")):
        offenders.extend(_equality_gated_enum_offenders(path))
    assert offenders == [], f"equality-gated StrEnum found: {offenders}"


def test_equality_gate_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The scan catches ``mode == ReplacementMode.OVERLAP_FIRST``."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(mode):\n" "    return mode == ReplacementMode.OVERLAP_FIRST\n",
        encoding="utf-8",
    )
    assert _equality_gated_enum_offenders(planted) != []
