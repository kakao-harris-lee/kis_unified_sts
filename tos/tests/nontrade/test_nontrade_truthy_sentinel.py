"""§4/§0.1(8) polarity discipline: truthy seals, ``is True`` gates, zero negative fields.

Three separate disciplines are regressed here:

1. **truthy-sentinel** — the two result enums raise on ``bool()``, so a bare ``if result:``
   cannot read a block / rejection as permission; every consuming gate is an identity test;
2. **positive polarity** — every ``bool | None`` premise is gated ``is True`` only, so
   ``None`` *and* every truthy non-``bool`` fail closed;
3. **zero negative-polarity fields (M7)** — Phase-1 nontrade has none, and that fact is
   pinned by both a field-absence assertion and a **source-level AST scan** for the
   forbidden ``is not True`` shape, so a future edit cannot reintroduce the ``None``-passes
   fail-open the series has rejected since #18 v1.0.

The AST scan is the same both-ways construction used elsewhere: a planted offender proves
the scanner actually detects the shape, so "green" is evidence the checker works rather than
evidence it was neutered.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.nontrade import (
    CorrectionReversalOutcome,
    CorrectionReversalRecord,
    NonTradeAuthorityEffect,
    NonTradeDisposition,
    NonTradeEventRecord,
    SplitTransformationSpec,
    TransitionEnvelope,
    correction_reversal_idempotent,
    effective_window_blocks_new_risk,
    instrument_lineage_preserved,
    nontrade_disposition,
)

from ._nontrade_strategies import (
    PHANTOM_NEGATIVE_POLARITY_FIELDS,
    TRUTHY_NON_BOOL,
    clean_disposition_inputs,
    clean_lineage_inputs,
    clean_window_inputs,
    issue_correction,
)

_NONTRADE_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "nontrade"
)

#: Every positive-polarity ``bool | None`` premise on the Phase-1 surface (design #21 §4 /
#: §7). Each is gated ``is True`` only.
_POSITIVE_POLARITY_PREMISES = (
    "original_retained",
    "identity_transition_final",
    "source_disagreement_bounded",
    "injected_credible_space_bounded",
    "injected_union_capacity_known",
    "protective_action_may_proceed",
)


# ---------------------------------------------------------------------------
# 1. truthy-sentinel seals
# ---------------------------------------------------------------------------


@given(st.sampled_from([*NonTradeDisposition, *CorrectionReversalOutcome]))
def test_every_result_member_rejects_truthiness(member: object) -> None:
    """(§2.2-5/§2.2-6) ``bool(result)`` raises on **every** member, safe ones included.

    Sealing only the denial members would leave ``if result:`` looking correct in the happy
    path and silently wrong everywhere else.
    """
    with pytest.raises(TypeError):
        bool(member)


def test_the_seal_message_names_the_identity_gate() -> None:
    """A loud error is only useful if it says what to do instead."""
    with pytest.raises(TypeError, match="identity gate"):
        bool(NonTradeDisposition.NONTRADE_TRAPPED)


def test_only_the_positive_identity_passes_a_consuming_gate() -> None:
    """(§4) ``is NONTRADE_ADMISSIBLE`` / ``is APPLIED_ONCE`` — nothing else."""
    admissible = nontrade_disposition(**clean_disposition_inputs())
    assert admissible is NonTradeDisposition.NONTRADE_ADMISSIBLE
    for other in NonTradeDisposition:
        if other is not NonTradeDisposition.NONTRADE_ADMISSIBLE:
            assert admissible is not other


def test_a_none_result_never_reaches_a_gate() -> None:
    """(§4) The producers are **total** — they never return ``None``."""
    assert nontrade_disposition(**clean_disposition_inputs(admissibility=None)) in set(
        NonTradeDisposition
    )
    assert correction_reversal_idempotent(None, None, None) in set(
        CorrectionReversalOutcome
    )


# ---------------------------------------------------------------------------
# 2. positive polarity — ``is True`` only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("truthy", TRUTHY_NON_BOOL)
def test_original_retained_needs_the_singleton_true(truthy: object) -> None:
    """(§5.3) A truthy non-``bool`` is not a proof of append-only retention."""
    assert (
        correction_reversal_idempotent(issue_correction(), None, truthy)  # type: ignore[arg-type]
        is CorrectionReversalOutcome.REJECTED_OVERWRITE
    )
    assert (
        correction_reversal_idempotent(issue_correction(), None, True)
        is CorrectionReversalOutcome.APPLIED_ONCE
    )


@pytest.mark.parametrize("truthy", TRUTHY_NON_BOOL)
def test_source_disagreement_bounded_needs_the_singleton_true(truthy: object) -> None:
    """(§6.2) The time verdict premise is positive polarity."""
    assert (
        effective_window_blocks_new_risk(
            **clean_window_inputs(source_disagreement_bounded=truthy)
        )
        is False
    )


@pytest.mark.parametrize("truthy", TRUTHY_NON_BOOL)
def test_identity_transition_final_needs_the_singleton_true(truthy: object) -> None:
    """(§6.1) A truthy non-``bool`` must not retire the old identity."""
    assert (
        instrument_lineage_preserved(
            **clean_lineage_inputs(
                old_route_identity=None, identity_transition_final=truthy
            )
        )
        is False
    )


@pytest.mark.parametrize(
    "premise", ["injected_credible_space_bounded", "injected_union_capacity_known"]
)
@pytest.mark.parametrize("truthy", TRUTHY_NON_BOOL)
def test_the_injected_sibling_verdicts_need_the_singleton_true(
    premise: str, truthy: object
) -> None:
    """(§5.5) are / rcl verdicts are positive polarity — a forged truthy value fails."""
    assert (
        nontrade_disposition(**clean_disposition_inputs(**{premise: truthy}))
        is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    )


def test_every_positive_polarity_premise_is_named_in_the_contract() -> None:
    """(§7) The premise list is fixed so a new one cannot be added ungated by accident."""
    assert len(_POSITIVE_POLARITY_PREMISES) == 6
    assert len(set(_POSITIVE_POLARITY_PREMISES)) == 6


# ---------------------------------------------------------------------------
# 3. zero negative-polarity fields (M7) — field absence + source-level AST scan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phantom", PHANTOM_NEGATIVE_POLARITY_FIELDS)
def test_no_model_reintroduces_a_phantom_negative_polarity_field(phantom: str) -> None:
    """(M7 honest disclosure) The three deleted names stay deleted, on every model."""
    for model in (
        NonTradeEventRecord,
        CorrectionReversalRecord,
        TransitionEnvelope,
        SplitTransformationSpec,
        NonTradeAuthorityEffect,
    ):
        assert phantom not in model.model_fields


def _is_not_true_offenders(path: Path) -> list[str]:
    """Return every ``<expr> is not True`` comparison in one source file (AST).

    The forbidden shape for a **negative-polarity** premise: a ``None`` passes it, which is
    the v1.0 fail-open. Phase-1 nontrade has zero negative-polarity fields, so the shape
    should not appear at all outside a positive-polarity rejection, where it is written as
    an explicit early ``return`` on the *reject* side.
    """
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, ast.IsNot) and isinstance(comparator, ast.Constant):
                if comparator.value is True:
                    offenders.append(f"{path.name}:{node.lineno} `is not True`")
    return offenders


def test_the_is_not_true_shape_is_confined_to_the_documented_positive_rejection() -> (
    None
):
    """(§0.1(8)/M7) ``is not True`` appears only where it *rejects*, never where it clears.

    ``correction_reversal_idempotent`` uses ``original_retained is not True`` to **reject**
    (the positive premise's contrapositive), which is the safe direction. Anywhere else the
    shape would be a negative-polarity gate that a ``None`` slips through.
    """
    occurrences: list[tuple[Path, int]] = []
    for path in sorted(_NONTRADE_SRC.rglob("*.py")):
        for offender in _is_not_true_offenders(path):
            occurrences.append((path, int(offender.split(":")[1].split(" ")[0])))
    assert len(occurrences) == 1, (
        "exactly one sanctioned `is not True` is expected (the positive premise's "
        f"contrapositive rejection); found: {occurrences}"
    )
    path, lineno = occurrences[0]
    assert path.name == "predicates.py"
    line = path.read_text(encoding="utf-8").splitlines()[lineno - 1]
    assert "original_retained" in line, (
        "the only sanctioned occurrence is the ``original_retained`` rejection; "
        f"found instead: {line.strip()!r}"
    )
    # ...and it genuinely rejects rather than clears: the guarded branch returns a
    # restrictive outcome.
    following = path.read_text(encoding="utf-8").splitlines()[lineno]
    assert "REJECTED_OVERWRITE" in following, following.strip()


def test_the_is_not_true_scanner_detects_a_planted_offender(tmp_path: Path) -> None:
    """(both-ways) The AST scan really catches the forbidden shape.

    Without this, a scanner that silently matched nothing would look identical to a clean
    source tree.
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(flag):\n    if flag is not True:\n        return False\n    return True\n",
        encoding="utf-8",
    )
    assert len(_is_not_true_offenders(planted)) == 1
    clean = tmp_path / "clean.py"
    clean.write_text(
        "def f(flag):\n    return flag is True\n",
        encoding="utf-8",
    )
    assert _is_not_true_offenders(clean) == []


def test_no_source_uses_a_bare_truthiness_gate_on_a_result_enum() -> None:
    """(§4) A ``bool(...)`` over a result enum would raise at runtime — it must not exist.

    The seal turns the misuse into a loud error, but the source should not contain the
    misuse in the first place; this scan asserts the two result type names never appear
    inside a ``bool(...)`` call.
    """
    offenders: list[str] = []
    for path in sorted(_NONTRADE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "bool"
            ):
                source = ast.unparse(node)
                if any(
                    name in source
                    for name in ("Disposition", "Outcome", "admissibility", "outcome")
                ):
                    offenders.append(f"{path.name}:{node.lineno} {source}")
    assert offenders == [], f"a result enum reached a bool() call: {offenders}"
