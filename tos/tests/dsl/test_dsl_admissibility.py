"""Static-admissibility property tests — DCE-EV-001/003/004/006 (design §6.1)."""

from __future__ import annotations

from typing import TypedDict

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from pydantic import ValidationError
from tos.canonical import CanonicalizationScheme
from tos.dsl import (
    ADMISSIBLE_KINDS,
    AMBIENT_SYMBOLS,
    ESCAPE_KINDS,
    WILDCARD_TOKENS,
    AdmissibilityResult,
    AdmissibilityVerdict,
    CandidateNode,
    CandidateProgram,
    Compare,
    Decision,
    Operand,
    analyze,
    analyze_candidate,
    is_admissible,
)
from tos.dsl.vocabulary import ADMISSIBLE_CONTEXT_SOURCES, KIND_CONTEXT_REF

from ._dsl_strategies import (
    ENFORCEMENT_VERSION,
    SCHEME,
    admissible_program,
    admissible_programs,
    escape_nodes,
    programs_with_buried_escape,
    programs_with_escape,
)

_AMBIENT_SOURCES = (
    "clock",
    "network",
    "filesystem",
    "env",
    "global",
    "builtin",
    "os",
    "random",
    "socket",
)


def test_non_member_decision_kind_is_unconstructable() -> None:
    """A forbidden outcome kind is not a vocabulary member — the type rejects it (DCE-EV-001)."""
    with pytest.raises(ValidationError):
        Decision(kind="IMPORT", rationale="x")  # type: ignore[arg-type]


def test_non_member_compare_op_is_unconstructable() -> None:
    """A forbidden comparison operator cannot be expressed in the algebra (DCE-EV-001)."""
    with pytest.raises(ValidationError):
        Compare(
            left=Operand(const=1),
            op="REFLECT",  # type: ignore[arg-type]
            right=Operand(const=2),
        )


@given(prog=admissible_programs(), esc=escape_nodes())
@settings(deadline=None, max_examples=75)
def test_adding_escape_node_flips_admissible_to_inadmissible(
    prog: CandidateProgram, esc: CandidateNode
) -> None:
    """Metamorphic: an admissible program + one escape node flips to INADMISSIBLE (DCE-EV-001)."""
    assert is_admissible(prog)
    flipped = CandidateProgram(nodes=(*prog.nodes, esc))
    assert not is_admissible(flipped)


@given(prog=admissible_programs())
@settings(deadline=None, max_examples=75)
def test_admissible_programs_are_admissible_without_reasons(
    prog: CandidateProgram,
) -> None:
    """A fully in-vocabulary program is ADMISSIBLE with an empty reason set (positive)."""
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.ADMISSIBLE
    assert analysis.reasons == ()
    assert is_admissible(prog)


@given(symbol=st.sampled_from(sorted(AMBIENT_SYMBOLS)))
def test_ambient_symbol_reference_is_inadmissible(symbol: str) -> None:
    """Any ambient symbol on an otherwise-admissible node is INADMISSIBLE (DCE-EV-003)."""
    prog = CandidateProgram(nodes=(CandidateNode(kind="const", symbol=symbol),))
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert any(r.startswith("ambient_symbol:") for r in analysis.reasons)


@given(source=st.sampled_from(_AMBIENT_SOURCES))
def test_ambient_context_ref_source_is_inadmissible(source: str) -> None:
    """A context_ref naming a non-{capsule,config} source is an ambient reach (DCE-EV-003)."""
    assert source not in ADMISSIBLE_CONTEXT_SOURCES
    prog = CandidateProgram(
        nodes=(CandidateNode(kind=KIND_CONTEXT_REF, source=source),)
    )
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert any(r.startswith("ambient_source:") for r in analysis.reasons)


@given(token=st.sampled_from(sorted(WILDCARD_TOKENS)))
def test_wildcard_scope_is_inadmissible(token: str) -> None:
    """A wildcard / 'latest' scope token is INADMISSIBLE (RFC-008 §11 item 13)."""
    prog = CandidateProgram(nodes=(CandidateNode(kind="const", scope=token),))
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert any(r.startswith("wildcard_scope:") for r in analysis.reasons)


@given(kind=st.sampled_from(sorted(ESCAPE_KINDS)))
def test_escape_kind_is_inadmissible(kind: str) -> None:
    """import / dynamic-eval / reflection / FFI / extension kinds are INADMISSIBLE (DCE-EV-004)."""
    prog = CandidateProgram(nodes=(CandidateNode(kind=kind),))
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert f"non_vocabulary_kind:{kind}" in analysis.reasons


@given(prog=programs_with_escape())
@settings(deadline=None, max_examples=75)
def test_any_program_with_an_escape_is_inadmissible(prog: CandidateProgram) -> None:
    """A program carrying ≥1 escape is never optimistically admitted (DCE-EV-006, ★4)."""
    assert not is_admissible(prog)
    assert analyze(prog).reasons


@given(prog=programs_with_buried_escape())
@settings(deadline=None, max_examples=75)
def test_escape_buried_in_children_is_inadmissible(prog: CandidateProgram) -> None:
    """An escape nested below the root is caught by the recursive walk (DCE-EV-006, M-2)."""
    assert not is_admissible(prog)
    assert analyze(prog).reasons


@given(
    kind=st.text(min_size=1, max_size=12).filter(lambda s: s not in ADMISSIBLE_KINDS)
)
def test_novel_unknown_kind_fails_closed(kind: str) -> None:
    """A kind outside the vocabulary is INADMISSIBLE by default-deny, not by blocklist (DCE-EV-006)."""
    prog = CandidateProgram(nodes=(CandidateNode(kind=kind),))
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert f"non_vocabulary_kind:{kind}" in analysis.reasons


def test_empty_candidate_program_is_unconstructable() -> None:
    """An empty candidate proves nothing inside the surface — unconstructable (★3 vacuous-True)."""
    with pytest.raises(ValidationError):
        CandidateProgram(nodes=())


def test_bypassed_empty_program_fails_closed_in_analyze() -> None:
    """A validation-bypassed empty program is INADMISSIBLE, never vacuously admitted (★3/DCE-EV-006)."""
    bypassed = CandidateProgram.model_construct(nodes=())
    analysis = analyze(bypassed)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert "empty_candidate" in analysis.reasons


def test_admissibility_result_rejects_forged_admissible_verdict() -> None:
    """An inadmissible candidate stored as ADMISSIBLE is unconstructable (★2 producer-optimism)."""
    bad = CandidateProgram(nodes=(CandidateNode(kind="import"),))
    assert analyze(bad).verdict is AdmissibilityVerdict.INADMISSIBLE
    with pytest.raises(ValidationError):
        AdmissibilityResult.issue(
            scheme=SCHEME,
            result_id="forge-adm",
            candidate=bad,
            verdict=AdmissibilityVerdict.ADMISSIBLE,
            reasons=(),
            enforcement_mechanism_version=ENFORCEMENT_VERSION,
            dsl_version="dsl-0",
        )


def test_admissibility_result_rejects_forged_inadmissible_verdict() -> None:
    """An admissible candidate stored as INADMISSIBLE is unconstructable (★2 producer-optimism)."""
    good = admissible_program()
    assert analyze(good).verdict is AdmissibilityVerdict.ADMISSIBLE
    with pytest.raises(ValidationError):
        AdmissibilityResult.issue(
            scheme=SCHEME,
            result_id="forge-inadm",
            candidate=good,
            verdict=AdmissibilityVerdict.INADMISSIBLE,
            reasons=("fabricated_reason",),
            enforcement_mechanism_version=ENFORCEMENT_VERSION,
            dsl_version="dsl-0",
        )


def test_admissibility_result_rejects_dropped_reasons() -> None:
    """An INADMISSIBLE verdict with an emptied reason set is unconstructable (★2)."""
    bad = CandidateProgram(nodes=(CandidateNode(kind="ffi"),))
    with pytest.raises(ValidationError):
        AdmissibilityResult.issue(
            scheme=SCHEME,
            result_id="drop-reasons",
            candidate=bad,
            verdict=AdmissibilityVerdict.INADMISSIBLE,
            reasons=(),
            enforcement_mechanism_version=ENFORCEMENT_VERSION,
            dsl_version="dsl-0",
        )


@given(prog=programs_with_escape())
@settings(deadline=None, max_examples=50)
def test_inadmissible_candidate_cannot_be_recorded_admissible(
    prog: CandidateProgram,
) -> None:
    """For any generated escape program, a forged ADMISSIBLE record rejects; the honest one round-trips."""
    computed = analyze(prog)
    assert computed.verdict is AdmissibilityVerdict.INADMISSIBLE
    with pytest.raises(ValidationError):
        AdmissibilityResult.issue(
            scheme=SCHEME,
            result_id="forge-prop",
            candidate=prog,
            verdict=AdmissibilityVerdict.ADMISSIBLE,
            reasons=(),
            enforcement_mechanism_version=ENFORCEMENT_VERSION,
            dsl_version="dsl-0",
        )
    honest = analyze_candidate(
        prog,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id="honest",
    )
    assert honest.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert honest.reasons == computed.reasons


def test_honest_admissibility_result_round_trips() -> None:
    """A faithful record built by analyze_candidate is constructable (positive)."""
    good = admissible_program()
    rec = analyze_candidate(
        good,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id="honest-good",
    )
    assert rec.verdict is AdmissibilityVerdict.ADMISSIBLE
    assert rec.reasons == ()


def test_analyze_candidate_without_a_strategy_identity_defaults_both_fields_null() -> (
    None
):
    """Backward-compatible default: a bare-candidate analysis names no strategy (★ no forced identity)."""
    rec = analyze_candidate(
        admissible_program(),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id="no-strategy",
    )
    assert rec.strategy_id is None
    assert rec.strategy_digest is None


def test_binding_a_strategy_identity_is_recorded_verbatim() -> None:
    """``strategy_id``/``strategy_digest`` round-trip verbatim onto the issued record."""
    rec = analyze_candidate(
        admissible_program(),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id="with-strategy",
        strategy_id="astrat-abc",
        strategy_digest="digest-abc",
    )
    assert rec.strategy_id == "astrat-abc"
    assert rec.strategy_digest == "digest-abc"


class _CandidateKwargs(TypedDict):
    """1:1 with :func:`analyze_candidate`'s signature minus ``result_id`` (plan §1.1"""

    candidate: CandidateProgram
    scheme: CanonicalizationScheme
    enforcement_mechanism_version: str
    dsl_version: str
    strategy_id: str | None
    strategy_digest: str | None


def test_same_strategy_identity_twice_yields_the_same_digest() -> None:
    """Re-checking the same (candidate, strategy) pair is idempotent at the digest level."""
    kwargs: _CandidateKwargs = {
        "candidate": admissible_program(),
        "scheme": SCHEME,
        "enforcement_mechanism_version": ENFORCEMENT_VERSION,
        "dsl_version": "dsl-0",
        "strategy_id": "astrat-same",
        "strategy_digest": "digest-same",
    }
    first = analyze_candidate(result_id="r1", **kwargs)
    second = analyze_candidate(result_id="r2", **kwargs)
    assert first.canonical_digest == second.canonical_digest
    assert first.result_id != second.result_id


def test_a_different_strategy_identity_over_the_same_candidate_changes_the_digest() -> (
    None
):
    """The G12 fix: an identical lowered candidate attributed to two strategies does not collide."""
    same_candidate = admissible_program()
    rec_a = analyze_candidate(
        same_candidate,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id="strategy-a",
        strategy_id="astrat-a",
        strategy_digest="digest-a",
    )
    rec_b = analyze_candidate(
        same_candidate,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id="strategy-b",
        strategy_id="astrat-b",
        strategy_digest="digest-b",
    )
    assert rec_a.canonical_digest != rec_b.canonical_digest


def test_a_changed_strategy_digest_over_the_same_lowered_program_changes_the_admissibility_digest() -> (
    None
):
    """A strategy rule change (different digest, same lowered candidate shape) is now distinguishable."""
    from tos.dsl.lowering import lower_strategy

    from ._dsl_strategies import flat_policy, issue_strategy, simple_policy

    strategy_a = issue_strategy(policy=simple_policy())
    strategy_b = issue_strategy(policy=flat_policy())
    assert strategy_a.canonical_digest != strategy_b.canonical_digest

    rec_a = analyze_candidate(
        lower_strategy(strategy_a),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id=f"admres-{strategy_a.strategy_id}",
        strategy_id=strategy_a.strategy_id,
        strategy_digest=strategy_a.canonical_digest,
    )
    rec_b = analyze_candidate(
        lower_strategy(strategy_b),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        dsl_version="dsl-0",
        result_id=f"admres-{strategy_b.strategy_id}",
        strategy_id=strategy_b.strategy_id,
        strategy_digest=strategy_b.canonical_digest,
    )
    assert rec_a.canonical_digest != rec_b.canonical_digest
