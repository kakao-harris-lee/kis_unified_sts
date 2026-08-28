"""Polarity exhaustive regression — ``None`` ⇒ deny convergence (design #28 §4.3; #18/#22/#23/#25 seal).

The #18/#22 MAJOR-2 lesson, inherited through #23 and #25: a ``bool | None`` field read with ``if
field:`` / ``is not True`` fails open on ``None`` depending on polarity. Every sir field declares its
polarity in :data:`~tos.sir.predicates.POSITIVE_POLARITY_FIELDS` /
:data:`~tos.sir.predicates.NEGATIVE_POLARITY_FIELDS` and is normalized with ``is True`` / ``is False``.

This suite property-checks that **every negative-polarity field's ``None`` converges to deny** (never
fail-opens to "not unknown" / "not consumed" / "not collapsed") and **every positive-polarity field's
``None`` / ``False`` converges to deny. The polarity expectations here are read off the design #28 §4.3
table, **not** back-derived from the implementation (the #25 MAJOR-2 lesson).

It also greps the sources for the one banned construction: ``<negative field> is not True``. That form
admits a ``None`` and is the exact re-opening of the #18/#22/#23/#25 fail-open. The grep is precise —
``is not True`` on a *positive*-polarity field is the sanctioned deny normalization and stays legal.

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import tos.sir as s
from hypothesis import given

from ._sir_strategies import (
    TRIBOOL,
    clean_broker_tokens,
    clean_closure_decision,
    clean_external_activity,
    clean_handoff,
    clean_independence_ladder,
    clean_obligation,
    clean_plan,
    clean_revival_inputs,
    clean_shutdown_procedure,
    clean_unknown_state,
)

_SIR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sir"


# --- the banned construction: `is not True` on a negative-polarity field ----


def _target_name(node: ast.expr) -> str | None:
    """The identifier a comparison's left operand names, if it names one."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_true_constant(node: ast.expr) -> bool:
    """Whether an expression is the literal ``True``."""
    return isinstance(node, ast.Constant) and node.value is True


def _is_not_true_targets(tree: ast.AST) -> list[tuple[int, str]]:
    """Every "admits a ``None`` alongside ``False``" read of a named coordinate, in its known forms.

    **Non-exhaustive, and deliberately honest about it** (the #25 MAJOR-1 wildcard-denylist lesson).
    Four syntactic shapes are detected — they are the ones a refactor realistically produces:

    * ``x is not True``           — the canonical banned form;
    * ``x != True``               — the same predicate through ``__ne__``;
    * ``not (x is True)``         — the same predicate through De Morgan;
    * ``x not in (True,)`` / ``[True]`` — the same predicate through membership.

    What it **cannot** see: a value routed through an intermediate variable
    (``flag = obj.field`` then ``flag is not True``), through a helper function, through
    ``getattr``/``operator.is_not``, or through a comprehension binding. Those are not
    value-model-decidable from one AST pass, and claiming otherwise would be the false-completeness
    this project has been bitten by before. The **primary** seal is therefore the polarity property
    suite in this file — every negative-polarity field is asserted to deny on ``None`` through the real
    predicate — and this scan is the cheap structural second line, not the guarantee.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        # form 3: not (x is True)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            inner = node.operand
            if (
                isinstance(inner, ast.Compare)
                and len(inner.ops) == 1
                and isinstance(inner.ops[0], ast.Is)
                and _is_true_constant(inner.comparators[0])
            ):
                name = _target_name(inner.left)
                if name is not None:
                    found.append((node.lineno, name))
            continue
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        operator, comparator = node.ops[0], node.comparators[0]
        name = _target_name(node.left)
        if name is None:
            continue
        # forms 1 and 2: x is not True / x != True
        if isinstance(operator, (ast.IsNot, ast.NotEq)) and _is_true_constant(
            comparator
        ):
            found.append((node.lineno, name))
        # form 4: x not in (True,) / [True]
        elif isinstance(operator, ast.NotIn) and isinstance(
            comparator, (ast.Tuple, ast.List, ast.Set)
        ):
            if comparator.elts and all(
                _is_true_constant(element) for element in comparator.elts
            ):
                found.append((node.lineno, name))
    return found


def test_no_negative_polarity_field_is_read_with_is_not_true() -> None:
    """(§4.3 the banned form) ``is not True`` never appears on a negative-polarity field.

    ``x is not True`` admits a ``None``. On a **negative**-polarity field (whose clear is ``is False``)
    that is the #18/#22/#23/#25 fail-open — an UNKNOWN read as "not set". On a **positive**-polarity
    field it is the sanctioned deny normalization, so the check targets polarity, not the token.
    """
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, name in _is_not_true_targets(tree):
            if name in s.NEGATIVE_POLARITY_FIELDS:
                offenders.append(f"{path.name}:{lineno} {name} is not True")
    assert offenders == [], (
        "negative-polarity field read with `is not True` — a None would fail open "
        f"(design #28 §4.3): {offenders}"
    )


@pytest.mark.parametrize(
    "expression",
    [
        "x.single_use_consumed is not True",
        "x.single_use_consumed != True",  # noqa: E712 - the form under test
        "not (x.single_use_consumed is True)",
        "x.single_use_consumed not in (True,)",
        "x.single_use_consumed not in [True]",
    ],
)
def test_is_not_true_scan_detects_every_known_equivalent_form(
    tmp_path: Path, expression: str
) -> None:
    """(canary) Each of the four detected equivalent forms is actually caught — not vacuous."""
    planted = tmp_path / "planted.py"
    planted.write_text(f"def f(x):\n    return {expression}\n", encoding="utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    names = {name for _, name in _is_not_true_targets(tree)}
    assert "single_use_consumed" in names, f"form not detected: {expression}"
    assert "single_use_consumed" in s.NEGATIVE_POLARITY_FIELDS


def test_the_scan_is_documented_as_non_exhaustive() -> None:
    """(honesty) The detector states its own limits — an indirection can route around it.

    The property suite below, not this scan, is the seal: every negative-polarity field is exercised
    through its real predicate with a ``None`` and asserted to deny. Documenting the scan's ceiling
    keeps a future reader from mistaking a green canary for a proof (the #25 MAJOR-1 lesson).
    """
    doc = _is_not_true_targets.__doc__ or ""
    assert "Non-exhaustive" in doc
    assert "intermediate variable" in doc
    # the indirection the scan cannot see, demonstrated rather than asserted away
    planted = ast.parse(
        "def f(obj):\n    flag = obj.single_use_consumed\n    return flag is not True\n"
    )
    assert ("single_use_consumed",) not in {
        (name,) for _, name in _is_not_true_targets(planted)
    }


def test_polarity_sets_are_disjoint_and_non_empty() -> None:
    """(§4.3 registry) A field cannot be both polarities, and neither set is empty."""
    assert s.POSITIVE_POLARITY_FIELDS
    assert s.NEGATIVE_POLARITY_FIELDS
    assert not (s.POSITIVE_POLARITY_FIELDS & s.NEGATIVE_POLARITY_FIELDS)
    assert not (s.DERIVED_NEGATIVE_POLARITY_NAMES & s.POSITIVE_POLARITY_FIELDS)


# --- negative polarity: only explicit False admits; None / True deny --------


@pytest.mark.parametrize("field", sorted(s.IncidentUnknownState.UNKNOWN_FIELDS))
@given(flag=TRIBOOL)
def test_unknown_axis_negative_polarity_none_denies(
    field: str, flag: bool | None
) -> None:
    """(SIR-INV-009; §4.3 negative) Each §13/§16 UNKNOWN axis admits only on explicit ``False``."""
    state = clean_unknown_state(**{field: flag})
    assert s.unknown_remains_conservative(state) is (flag is False)
    assert field in s.NEGATIVE_POLARITY_FIELDS


@pytest.mark.parametrize("field", sorted(s.RecoveryRevivalInputs.REVIVAL_FIELDS))
@given(flag=TRIBOOL)
def test_revival_axis_negative_polarity_none_denies(
    field: str, flag: bool | None
) -> None:
    """(SIR-INV-015; §4.3 negative) Each §21 non-revival axis admits only on explicit ``False``."""
    inputs = clean_revival_inputs(**{field: flag})
    assert s.recovery_revives_nothing(inputs) is (flag is False)
    assert field in s.NEGATIVE_POLARITY_FIELDS


_BROKER_NEGATIVE_FIELDS = (
    "missing_ack_treated_as_non_acceptance",
    "cancel_ack_treated_as_final_quantity_proof",
    "query_omission_treated_as_absence_proof",
    "blind_retry_authorized",
    "premature_release_authorized",
    "optimistic_reconciliation_authorized",
)


@pytest.mark.parametrize("field", _BROKER_NEGATIVE_FIELDS)
@given(flag=TRIBOOL)
def test_broker_finality_negative_polarity_none_denies(
    field: str, flag: bool | None
) -> None:
    """(SIR-INV-010; §4.3 negative) Each §13 broker-finality token admits only on explicit ``False``."""
    tokens = clean_broker_tokens(**{field: flag})
    assert s.broker_finality_unchanged(tokens) is (flag is False)
    assert field in s.NEGATIVE_POLARITY_FIELDS


_EXTERNAL_NEGATIVE_FIELDS = (
    "retroactively_compliant_transmission",
    "proves_execution_or_final_quantity",
    "releases_capacity_by_operator_statement",
    "clears_halt_or_closes_incident",
    "re_arms",
)


@pytest.mark.parametrize("field", _EXTERNAL_NEGATIVE_FIELDS)
@given(flag=TRIBOOL)
def test_external_activity_negative_polarity_none_denies(
    field: str, flag: bool | None
) -> None:
    """(§15 line 407-412; §4.3 negative) Each external-activity claim admits only on ``False``."""
    activity = clean_external_activity(**{field: flag})
    assert s.external_activity_conservative(activity) is (flag is False)
    assert field in s.NEGATIVE_POLARITY_FIELDS


@given(collapsed=TRIBOOL)
def test_principals_collapsed_negative_polarity(collapsed: bool | None) -> None:
    """(SIR-INV-016; §4.3 negative, hag-injected) Only an explicit ``False`` clears; ``None`` denies."""
    ladder = clean_independence_ladder(principals_collapsed=collapsed)
    assert s.closure_independence_non_self_exemption(ladder) is (collapsed is False)


@given(cancelled=TRIBOOL)
def test_protection_blindly_cancelled_negative_polarity(cancelled: bool | None) -> None:
    """(§14 line 388; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    plan = clean_plan(protection_blindly_cancelled=cancelled)
    assert s.obligations_survive_shutdown(plan) is (cancelled is False)


@given(reported=TRIBOOL)
def test_exposure_reported_safely_closed_negative_polarity(
    reported: bool | None,
) -> None:
    """(§14 line 397; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    plan = clean_plan(exposure_reported_safely_closed=reported)
    assert s.obligations_survive_shutdown(plan) is (reported is False)


@given(assumed=TRIBOOL)
def test_assumed_executable_negative_polarity(assumed: bool | None) -> None:
    """(§11 line 333; §4.3 negative) Only an explicit ``False`` clears; ``None`` denies."""
    from ._sir_strategies import clean_action

    plan = clean_plan(proposed_actions=(clean_action(assumed_executable=assumed),))
    assert s.containment_uses_normal_authority(plan) is (assumed is False)


# --- positive polarity: only explicit True admits; None / False deny --------


@given(approved=TRIBOOL)
def test_cancellation_arbiter_approved_positive_polarity(approved: bool | None) -> None:
    """(§12 step 6; §4.3 positive, protective-injected) Only an explicit ``True`` admits."""
    plan = clean_plan(cancellation_arbiter_approved=approved)
    assert s.obligations_survive_shutdown(plan) is (approved is True)


@given(deny_first=TRIBOOL)
def test_deny_before_stop_positive_polarity(deny_first: bool | None) -> None:
    """(§12 step 1; §4.3 positive) Only an explicit ``True`` admits; ``None`` denies."""
    procedure = clean_shutdown_procedure(deny_before_stop=deny_first)
    assert s.controlled_shutdown_not_broker_finality(procedure) is (deny_first is True)


@given(closed=TRIBOOL, accepted=TRIBOOL)
def test_recovery_barrier_and_acceptance_positive_polarity(
    closed: bool | None, accepted: bool | None
) -> None:
    """(§5.9 / §21 line 511; §4.3 positive, sbr-injected) Both need an explicit ``True``."""
    package = clean_handoff(
        recovery_barrier_closed=closed, accepted_by_recovery_session=accepted
    )
    assert s.recovery_handoff_requires_accepted_barrier(package) is (
        closed is True and accepted is True
    )


@given(resolved=TRIBOOL)
def test_independence_resolved_positive_polarity_naming_inversion(
    resolved: bool | None,
) -> None:
    """(SIR-INV-016 line 218; §4.3 positive with a naming inversion) Unknown independence denies."""
    ladder = clean_independence_ladder(independence_resolved=resolved)
    assert s.closure_independence_non_self_exemption(ladder) is (resolved is True)
    assert "independence_resolved" in s.POSITIVE_POLARITY_FIELDS
    assert "principals_collapsed" in s.NEGATIVE_POLARITY_FIELDS


@given(resolved=TRIBOOL, transferred=TRIBOOL)
def test_obligation_survival_is_positively_gated(
    resolved: bool | None, transferred: bool | None
) -> None:
    """(§5.11 / §20 item 4/9; §4.3 positive) An obligation survives unless positively disposed of."""
    plan = clean_plan(
        protection_obligations=(
            clean_obligation(
                resolved=resolved, transferred_with_owner_and_evidence=transferred
            ),
        )
    )
    assert s.obligations_survive_shutdown(plan) is (
        resolved is True or transferred is True
    )


@given(present=TRIBOOL)
def test_final_quantity_proof_positive_polarity_keeps_attempts_live(
    present: bool | None,
) -> None:
    """(§20 item 3 / SIR-INV-010; §4.3 positive) Without a positive proof the attempt stays live."""
    # provable RESTRICT(1) < SEND(2) and no recorded first byte: only the proof decides.
    assert s.attempt_potentially_live(1, 2, None, present) is (present is not True)
    # send(1) < restriction(2) IS the §16 line 431 race — potentially live regardless of the proof.
    assert s.attempt_potentially_live(2, 1, 3, present) is True
    assert "final_quantity_proof_present" in s.POSITIVE_POLARITY_FIELDS
    # the model-side counterpart carries the same positive polarity.
    assert s.final_quantity_proof_absent(
        clean_broker_tokens(final_quantity_proof_present=present)
    ) is (present is not True)


@given(verdict=TRIBOOL)
def test_effective_principal_verdict_positive_polarity(verdict: bool | None) -> None:
    """(§20 item 10; §4.3 positive, hag-injected) The injected verdict gates closure on its own.

    The verdict is the fact **hag produced** (``hag/predicates.py:283``
    ``quorum_independence_satisfied``); §20 item 10 is *also* a self-reported contract slot, and a
    record that self-certifies item 10 while hag denied (or could not decide) independence must not
    close. Positive polarity — a ``False`` **and** an unknown ``None`` both deny.
    """
    decision = clean_closure_decision(effective_principal_verdict=verdict)
    assert s.closure_administrative_non_permissive(decision) is (verdict is True)
    assert "effective_principal_verdict" in s.POSITIVE_POLARITY_FIELDS


@given(completed=TRIBOOL)
def test_shutdown_step_completion_is_positively_proven(completed: bool | None) -> None:
    """(§17 line 451) "assume not completed where that is safer" — only a positive ``True`` counts."""
    step = s.ShutdownStep(
        step_ordinal=1, step_kind=s.SHUTDOWN_STEP_KINDS[0], completed=completed
    )
    assert s.step_completion_proven(step) is (completed is True)
    assert "completed" in s.NEGATIVE_POLARITY_FIELDS


@given(expands=TRIBOOL)
def test_external_expansion_positive_polarity(expands: bool | None) -> None:
    """(§15 line 412; §4.3 positive) The mandatory reconciliation expansion needs an explicit ``True``."""
    activity = clean_external_activity(expands_reconciliation_and_closure=expands)
    assert s.external_activity_conservative(activity) is (expands is True)
