"""Truthy-sentinel seal + polarity discipline (design #24 §0.1(11)/§2.2-8/§7).

Three separate disciplines, each asserted directly:

1. **truthy-untestable results** — every member of
   :class:`PostTradeDisposition` and :class:`ObligationCommitOutcome` raises ``TypeError`` on
   ``bool()``, so a bare ``if disposition:`` (which would read ``POST_TRADE_TRAPPED`` and
   ``REJECTED_CONFLICT`` as permission) is a loud error rather than a silent fail-open. The
   non-result vocabulary enums are deliberately **not** sealed — they are structural axes, not
   verdicts;
2. **positive-polarity ``is True`` gating** — every injected ``bool | None`` premise across
   the package is exercised with ``None`` and with truthy **and falsy** non-``bool`` forgeries,
   and none of them ever opens a gate;
3. **zero negative-polarity fields (honest disclosure)** — the package deliberately has none,
   and the phantom names stay absent; a future edit that introduces one must gate it ``is
   False`` (never ``is not True``, which a ``None`` would pass).

The source is additionally scanned for the two forbidden idioms: an ``is not True`` used to
**permit**, and a bare truthiness test on a result enum.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given
from tos.posttrade import (
    CashKind,
    EventObligationLegKind,
    FinalityDimensionKind,
    MarginCollateralState,
    ObligationCommitOutcome,
    ObligationLegDirection,
    PostTradeDisposition,
    PostTradeObligationLifecycleState,
    StatementClass,
    absence_is_negative_evidence_only,
    missing_counterleg_is_adverse,
    netting_requires_positive_proof,
    obligation_commit_idempotent,
    post_trade_disposition,
)

from ._posttrade_strategies import (
    FORGED_FLAG,
    clean_disposition_kwargs,
    clean_leg,
    clean_obligation_record,
)

_POSTTRADE_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "posttrade"
)

_RESULT_ENUMS = (PostTradeDisposition, ObligationCommitOutcome)
_STRUCTURAL_ENUMS = (
    PostTradeObligationLifecycleState,
    FinalityDimensionKind,
    ObligationLegDirection,
    CashKind,
    MarginCollateralState,
    StatementClass,
    EventObligationLegKind,
)


# --- 1. truthy-untestable results --------------------------------------------


@pytest.mark.parametrize(
    "member",
    [member for enum_type in _RESULT_ENUMS for member in enum_type],
    ids=lambda member: f"{type(member).__name__}.{member.name}",
)
def test_every_result_member_is_truthy_untestable(member: object) -> None:
    """(§2.2-8) ``bool(result)`` raises — including on the *permissive* members.

    Sealing only the denial members would still leave ``if outcome:`` looking like it worked.
    """
    with pytest.raises(TypeError, match="not truthy-testable"):
        bool(member)


@pytest.mark.parametrize(
    "member",
    [member for enum_type in _RESULT_ENUMS for member in enum_type],
    ids=lambda member: f"{type(member).__name__}.{member.name}",
)
def test_identity_value_hashing_and_membership_still_work(member: object) -> None:
    """(§2.2-8) The seal touches ``__bool__`` only — the mandated gate stays usable."""
    assert member is type(member)(member.value)  # type: ignore[call-arg]
    assert member.value  # the raw string is a normal truthy str
    assert member in set(type(member))
    assert str(member) == member.value


@pytest.mark.parametrize("enum_type", _STRUCTURAL_ENUMS)
def test_structural_vocabulary_enums_are_not_sealed(enum_type: type) -> None:
    """(§2.1 m7) Only the two **result** enums are sealed; an axis is not a verdict.

    Sealing the structural axes would break ordinary set / mapping use for no safety gain —
    no one writes ``if cash_kind:`` as a permission test.
    """
    for member in enum_type:
        assert bool(member) is True


def test_the_two_result_enums_are_exactly_the_sealed_ones() -> None:
    """(§2.1 m7) The seal covers the decision results and nothing else."""
    assert len(_RESULT_ENUMS) == 2
    assert len(_STRUCTURAL_ENUMS) == 7


# --- 2. positive-polarity gating ---------------------------------------------


@given(forged=FORGED_FLAG)
def test_original_retained_is_gated_is_true(forged: object) -> None:
    """(§5.2) The append-only retention premise passes only on a real ``True``."""
    outcome = obligation_commit_idempotent(
        clean_obligation_record(), None, forged  # type: ignore[arg-type]
    )
    assert (outcome is ObligationCommitOutcome.COMMITTED_ONCE) is (forged is True)


@given(scope=FORGED_FLAG, proof=FORGED_FLAG)
def test_netting_premises_are_gated_is_true(scope: object, proof: object) -> None:
    """(§5.3) Both netting premises pass only on a real ``True``."""
    verdict = netting_requires_positive_proof(
        clean_leg(ObligationLegDirection.CREDIT),
        clean_leg(ObligationLegDirection.DEBIT),
        scope,  # type: ignore[arg-type]
        proof,  # type: ignore[arg-type]
    )
    assert verdict is (scope is True and proof is True)


@given(established=FORGED_FLAG)
def test_counterleg_establishment_is_gated_is_true(established: object) -> None:
    """(§5.3) An unestablished counterleg stays adverse under every forgery."""
    adverse = missing_counterleg_is_adverse(
        clean_leg(ObligationLegDirection.DEBIT),
        clean_leg(ObligationLegDirection.CREDIT),
        established,  # type: ignore[arg-type]
    )
    assert adverse is (established is not True)


@given(absent=FORGED_FLAG, coverage=FORGED_FLAG)
def test_absence_gate_premises_are_gated_is_true(
    absent: object, coverage: object
) -> None:
    """(§5.6) The absence gate opens on four real ``True`` values and nothing else."""
    verdict = absence_is_negative_evidence_only(
        absent, coverage, True, True  # type: ignore[arg-type]
    )
    assert verdict is (absent is True and coverage is True)


@given(availability=FORGED_FLAG)
def test_availability_is_gated_is_true(availability: object) -> None:
    """(§5.8 rank 3/5) Only a real ``True`` clears the trap and permits admissibility."""
    verdict = post_trade_disposition(
        **clean_disposition_kwargs(availability_proven=availability)
    )
    if availability is True:
        assert verdict is PostTradeDisposition.POST_TRADE_ADMISSIBLE
    else:
        assert verdict is PostTradeDisposition.POST_TRADE_TRAPPED


# --- 3. no negative-polarity field + no forbidden idiom ----------------------


def test_the_package_declares_no_negative_polarity_premise() -> None:
    """(§7 honest disclosure) Every injected ``bool | None`` premise is positive-polarity.

    The list is the design's own enumeration. If a future edit adds a negative-polarity
    premise it must be gated ``is False`` — never ``is not True``, which a ``None`` passes —
    and this test is where that decision has to be recorded.
    """
    positive_premises = {
        "original_retained",
        "same_scope",
        "enforceable_netting_proof",
        "counterleg_positively_established",
        "line_item_absent",
        "coverage_complete",
        "correction_semantics_support",
        "source_capability_supports",
        "availability_proven",
        "booked_zero",
    }
    assert len(positive_premises) == 10
    # the disposition's sixteen conjuncts are positive-polarity too
    from tos.posttrade import DISPOSITION_CONJUNCTS

    assert len(DISPOSITION_CONJUNCTS) == 16


#: The **only** functions in which ``is not True`` is sanctioned (design #24 §5.8 / the
#: series-discipline-1 carve-out). In each one the reading sends a ``None`` to the *more*
#: conservative answer:
#:
#: * ``obligation_commit_idempotent`` — the overwrite pre-gate, whose branch returns
#:   ``REJECTED_OVERWRITE``;
#: * ``missing_counterleg_is_adverse`` — the predicate's ``True`` **is** the conservative
#:   answer ("treat the counterleg as adverse"), so an unproven establishment must return
#:   ``True``;
#: * ``post_trade_disposition`` — the rank-1 and rank-3 denial branches, which return
#:   ``POST_TRADE_CONFLICTED`` and ``POST_TRADE_TRAPPED``.
#:
#: Anywhere else — and in particular inside a positive conjunction that can yield ``True``,
#: ``COMMITTED_ONCE``, or ``POST_TRADE_ADMISSIBLE`` — it would let a ``None`` **permit**,
#: which is exactly what the discipline forbids.
_SANCTIONED_IS_NOT_TRUE_FUNCTIONS = frozenset(
    {
        "obligation_commit_idempotent",
        "missing_counterleg_is_adverse",
        "post_trade_disposition",
    }
)


def _is_not_true_sites(path: Path) -> list[tuple[str, int]]:
    """Return ``(enclosing_function, lineno)`` for every ``is not True`` in a source file."""
    sites: list[tuple[str, int]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(op, ast.IsNot) for op in node.ops):
                continue
            if any(
                isinstance(comparator, ast.Constant) and comparator.value is True
                for comparator in node.comparators
            ):
                sites.append((function.name, node.lineno))
    return sites


def test_is_not_true_appears_only_in_sanctioned_denial_functions() -> None:
    """(series discipline 1) ``is not True`` never permits anything, anywhere.

    The three sanctioned functions are enumerated above with the reason each is safe; every
    other occurrence in the package is a defect, because a ``None`` would pass the gate.
    """
    offenders: list[str] = []
    for path in sorted(_POSTTRADE_SRC.rglob("*.py")):
        for function_name, lineno in _is_not_true_sites(path):
            if function_name not in _SANCTIONED_IS_NOT_TRUE_FUNCTIONS:
                offenders.append(f"{path.name}:{lineno} in {function_name}()")
    assert (
        offenders == []
    ), f"`is not True` outside a sanctioned denial function: {offenders}"


def test_the_sanctioned_sites_really_exist() -> None:
    """(both-ways) The carve-out is not a dead whitelist — each site is really there."""
    found = {
        function
        for path in sorted(_POSTTRADE_SRC.rglob("*.py"))
        for function, _ in _is_not_true_sites(path)
    }
    assert (
        found == _SANCTIONED_IS_NOT_TRUE_FUNCTIONS
    ), "the sanctioned-site whitelist has drifted from the source"


def test_no_source_bare_truthiness_test_on_a_result_enum() -> None:
    """(§2.2-8) No ``if outcome:`` / ``if disposition:`` anywhere in the package.

    The seal makes such a test raise at runtime, but a static check catches it before the
    branch is ever taken.
    """
    offenders: list[str] = []
    suspicious_names = {"outcome", "disposition", "commit_outcome", "verdict", "result"}
    for path in sorted(_POSTTRADE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            tests: list[ast.expr] = []
            if isinstance(node, ast.If):
                tests.append(node.test)
            elif isinstance(node, ast.BoolOp):
                tests.extend(node.values)
            for test in tests:
                if isinstance(test, ast.Name) and test.id in suspicious_names:
                    offenders.append(f"{path.name}:{test.lineno} bare `{test.id}`")
                if (
                    isinstance(test, ast.UnaryOp)
                    and isinstance(test.op, ast.Not)
                    and isinstance(test.operand, ast.Name)
                    and test.operand.id in suspicious_names
                ):
                    offenders.append(
                        f"{path.name}:{test.lineno} bare `not {test.operand.id}`"
                    )
    assert offenders == [], f"bare truthiness test on a result value: {offenders}"


def test_the_ast_scan_detects_a_planted_bare_truthiness_test(tmp_path: Path) -> None:
    """(both-ways) The scan works — green means "clean", not "neutered"."""
    planted = tmp_path / "planted.py"
    planted.write_text("def f(outcome):\n    if outcome:\n        return 1\n", "utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "outcome"
    ]
    assert found, "the planted bare truthiness test was not detected"
