"""The engine-admission escape-checker gate (design #31 §3.5/§9-4 seam closure).

Design #31 §3.5 explicitly deferred this: Slice #1 accepted in-process typed
``AuthoredStrategy`` objects without ever calling the DSL escape-checker
(``tos.dsl.admissibility.analyze``), because there was no ``lower_strategy``
function to bridge the typed algebra into the candidate-AST domain the checker
consumes (DSL spike memo G11). ``tos.dsl.lowering.lower_strategy`` (lane D-K-1)
closes that gap; this module proves ``tos.engine.admission.strategy_admissible``
actually calls it — both for the in-process typed path and for a strategy built
through ``tos.dsl.serialization.parse_strategy`` (the "두 경로 동형" claim,
design #31 §1.2).

Because the typed authoring algebra cannot itself express an escape (that is the
whole point of design #31 §3.5's "admissible by construction"), a genuinely
escaping ``AuthoredStrategy`` is unconstructable — the ``lower_strategy`` seam is
exercised here two ways: (1) end-to-end with real (escape-free) fixture strategies,
proving the gate runs and passes them, and (2) with ``lower_strategy`` monkeypatched
to return an adversarial program, proving the gate actually consumes whatever
``lower_strategy`` hands it and refuses on the checker's own reasons — the only way
to observe the gate reject anything, short of forging module-private state.
"""

from __future__ import annotations

import pytest
from tos.dsl import AdmissibilityResult, CandidateNode, CandidateProgram
from tos.dsl.serialization import parse_strategy
from tos.engine import admission as admission_module
from tos.engine.admission import strategy_admissible
from tos.engine.vocabulary import AdmissionVerdict

from ._engine_fixtures import ACCOUNT, INSTRUMENT, capsule_gated_policy, issue_strategy


def test_an_admissible_typed_strategy_carries_a_positive_escape_checker_binding() -> (
    None
):
    """(iii) A passing strategy's ``AdmissionResult`` binds an ADMISSIBLE ``AdmissibilityResult``."""
    result = strategy_admissible(issue_strategy(capsule_gated_policy()))
    assert result.verdict is AdmissionVerdict.ADMISSIBLE
    assert result.admissibility_result is not None
    assert isinstance(result.admissibility_result, AdmissibilityResult)
    from tos.dsl import AdmissibilityVerdict

    assert result.admissibility_result.verdict is AdmissibilityVerdict.ADMISSIBLE
    assert result.admissibility_result.reasons == ()


def test_the_bound_admissibility_result_names_the_exact_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(iii) G12 binding: the bound record's ``strategy_id``/``strategy_digest`` match the strategy."""
    del monkeypatch  # not used — kept for signature symmetry with the escape test below
    strategy = issue_strategy(capsule_gated_policy())
    result = strategy_admissible(strategy)
    assert result.admissibility_result is not None
    assert result.admissibility_result.strategy_id == strategy.strategy_id
    assert result.admissibility_result.strategy_digest == strategy.canonical_digest


def test_a_lowered_program_carrying_an_escape_is_refused_with_the_checkers_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(ii) A strategy whose lowered program carries an escape is INADMISSIBLE with the checker's reason.

    The typed algebra cannot construct an escaping strategy, so ``lower_strategy``
    is monkeypatched to hand back an adversarial candidate for this one call —
    the only way to observe the gate actually reject on the escape-checker's own
    output rather than merely trust that it would.
    """
    strategy = issue_strategy(capsule_gated_policy())

    def _adversarial_lowering(_: object) -> CandidateProgram:
        return CandidateProgram(nodes=(CandidateNode(kind="import"),))

    monkeypatch.setattr(admission_module, "lower_strategy", _adversarial_lowering)
    result = strategy_admissible(strategy)
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("escape-checker" in reason for reason in result.reasons)
    assert any("non_vocabulary_kind:import" in reason for reason in result.reasons)
    assert result.admissibility_result is not None
    from tos.dsl import AdmissibilityVerdict

    assert result.admissibility_result.verdict is AdmissibilityVerdict.INADMISSIBLE


def test_removing_the_escape_checker_call_would_make_this_test_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation-testing canary: an admission gate that ignores the lowered analysis passes an escape.

    This test does not mutate the source; it documents the RED this lane captured
    by hand (report body quotes the actual pytest RED output from a
    temporarily-commented-out escape-checker call). Kept here as a permanent,
    always-green positive so a future regression that silently drops the gate is
    caught by ``test_a_lowered_program_carrying_an_escape_is_refused_with_the_
    checkers_reason`` above, not only by a one-time manual RED capture.
    """
    strategy = issue_strategy(capsule_gated_policy())

    def _adversarial_lowering(_: object) -> CandidateProgram:
        return CandidateProgram(nodes=(CandidateNode(kind="dynamic_eval"),))

    monkeypatch.setattr(admission_module, "lower_strategy", _adversarial_lowering)
    result = strategy_admissible(strategy)
    # If the gate stopped calling analyze() over the lowered program, this would
    # read ADMISSIBLE (the capsule-operand walk and key derivation alone still
    # pass for `capsule_gated_policy()`) — the assertion below is the live tripwire.
    assert result.verdict is AdmissionVerdict.INADMISSIBLE


def test_a_non_issued_strategy_never_reaches_get_scheme_and_does_not_raise() -> None:
    """A DRAFT strategy with a policy set is refused via the status reason, not a get_scheme(None) crash.

    ``strategy.canonicalization_version`` is null on a manually-constructed DRAFT
    instance; the escape-checker gate must not attempt to resolve a canonicalization
    scheme for it (that would raise ``ArtifactIntegrityError`` from
    ``tos.canonical.get_scheme``, turning admission into an uncaught exception
    instead of a returned ``AdmissionResult``).
    """
    from tos.dsl import AuthoredStrategy

    draft_with_policy = AuthoredStrategy(
        dsl_version="dsl-0",
        config_binding_version="cfg-0",
        policy=capsule_gated_policy(),
    )
    assert draft_with_policy.canonicalization_version is None
    result = strategy_admissible(draft_with_policy)  # must not raise
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("strategy status is" in reason for reason in result.reasons)


def test_the_parsed_path_and_the_in_process_path_go_through_the_same_gate() -> None:
    """Both authoring paths converge on one gate (design #31 §1.2 "두 경로 동형")."""
    mapping = {
        "dsl_version": "dsl-0",
        "config_binding_version": "cfg-bind-0",
        "policy": {
            "rules": (
                {
                    "all_of": (
                        {
                            "left": {"ref": ("capsule", "scope", "decision_class")},
                            "op": "EQ",
                            "right": {"const": "entry"},
                        },
                    ),
                    "decision": {
                        "kind": "ACTION",
                        "rationale": "fired",
                        "target": {
                            "kind": "ACTION",
                            "account": ACCOUNT,
                            "instrument": INSTRUMENT,
                            "direction": "LONG",
                            "position_effect": "OPEN",
                            "quantity_basis": "RISK",
                            "rationale": "fired",
                        },
                    },
                },
            ),
            "default": {"kind": "NO_ACTION", "rationale": "hold"},
        },
    }
    parsed_strategy = parse_strategy(mapping)
    parsed_result = strategy_admissible(parsed_strategy)
    typed_result = strategy_admissible(issue_strategy(capsule_gated_policy()))
    assert parsed_result.verdict is AdmissionVerdict.ADMISSIBLE
    assert typed_result.verdict is AdmissionVerdict.ADMISSIBLE
    assert parsed_result.admissibility_result is not None
    assert typed_result.admissibility_result is not None
