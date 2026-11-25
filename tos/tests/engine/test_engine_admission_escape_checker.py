"""The engine-admission escape-checker gate (design #31 §3.5/§9-4 seam closure)."""

from __future__ import annotations

import pytest
from tos.dsl import AdmissibilityResult, CandidateNode, CandidateProgram
from tos.dsl.serialization import parse_strategy
from tos.dsl.vocabulary import KIND_CONTEXT_REF
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
    del monkeypatch
    strategy = issue_strategy(capsule_gated_policy())
    result = strategy_admissible(strategy)
    assert result.admissibility_result is not None
    assert result.admissibility_result.strategy_id == strategy.strategy_id
    assert result.admissibility_result.strategy_digest == strategy.canonical_digest


def test_a_lowered_program_carrying_an_escape_is_refused_with_the_checkers_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(ii) A strategy whose lowered program carries an escape is INADMISSIBLE with the checker's reason."""
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


def test_an_ambient_sourced_context_ref_in_the_lowered_program_is_still_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """([K2-p3-#10] finding #10) The escape-checker independently catches an ambient ``context_ref``."""
    strategy = issue_strategy(capsule_gated_policy())

    def _adversarial_lowering(_: object) -> CandidateProgram:
        return CandidateProgram(
            nodes=(CandidateNode(kind=KIND_CONTEXT_REF, source="ambient"),)
        )

    monkeypatch.setattr(admission_module, "lower_strategy", _adversarial_lowering)
    result = strategy_admissible(strategy)
    assert result.verdict is AdmissionVerdict.INADMISSIBLE
    assert any("ambient_source:ambient" in reason for reason in result.reasons)


def test_removing_the_escape_checker_call_would_make_this_test_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation-testing canary: an admission gate that ignores the lowered analysis passes an escape."""
    strategy = issue_strategy(capsule_gated_policy())

    def _adversarial_lowering(_: object) -> CandidateProgram:
        return CandidateProgram(nodes=(CandidateNode(kind="dynamic_eval"),))

    monkeypatch.setattr(admission_module, "lower_strategy", _adversarial_lowering)
    result = strategy_admissible(strategy)
    assert result.verdict is AdmissionVerdict.INADMISSIBLE


def test_a_non_issued_strategy_never_reaches_get_scheme_and_does_not_raise() -> None:
    """A DRAFT strategy with a policy set is refused via the status reason, not a get_scheme(None) crash."""
    from tos.dsl import AuthoredStrategy

    draft_with_policy = AuthoredStrategy(
        dsl_version="dsl-0",
        config_binding_version="cfg-0",
        policy=capsule_gated_policy(),
    )
    assert draft_with_policy.canonicalization_version is None
    result = strategy_admissible(draft_with_policy)
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
