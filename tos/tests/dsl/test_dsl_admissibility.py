"""Static-admissibility property tests — DCE-EV-001/003/004/006 (design §6.1).

Each property produces *authoring evidence* for an EV static facet; none completes
an EV (design §1/§6). DCE-EV-002 (layered non-self-trust) and DCE-EV-005 (mechanism
verification) have **no L1 property** (design §1/§6) and are intentionally absent.

DCE-EV → property map:

* **DCE-EV-001** (default-deny = absent-from-surface): the closed typed algebra
  cannot *express* a forbidden construct (a non-member ``DecisionKind``/``CompareOp``
  is unconstructable), and a metamorphic flip — an admissible program plus one
  escape node — turns ADMISSIBLE → INADMISSIBLE.
* **DCE-EV-003** (no ambient authority, static naming): any ambient
  clock/rand/net/fs/global/builtin *source* or *symbol* reference is INADMISSIBLE;
  hypothesis injects the ambient names.
* **DCE-EV-004** (escape-closure): import / dynamic-eval / reflection / FFI /
  extension nodes are INADMISSIBLE by default-deny node-membership. (Source-form
  scanning is a Phase-0 concern the design defers; design §3.2.)
* **DCE-EV-006** (fail-closed / conservative): a novel/unknown kind, an empty
  candidate, and any ``programs_with_escape`` sample are INADMISSIBLE — never
  optimistically admitted.

★ fail-open guards realized here (see also ``test_dsl_required_covered.py``):

* **★2 producer-optimism**: an ``AdmissibilityResult`` cannot store a verdict the
  pure predicate did not yield (forged ADMISSIBLE / forged INADMISSIBLE / dropped
  reasons all reject).
* **★3 vacuous-True**: an empty ``CandidateProgram`` is unconstructable, and a
  validation-bypassed empty program fails closed in ``analyze``.
* **★4 real violations**: ``programs_with_escape`` / ``escape_nodes`` /
  novel-kind strategies actively *generate* inadmissible inputs, so the negatives
  are non-vacuous (not a positive-only coverage illusion).
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from pydantic import ValidationError
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


# ---------------------------------------------------------------------------
# DCE-EV-001 — default-deny is absent-from-surface, not a blocklist
# ---------------------------------------------------------------------------


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
    assert is_admissible(prog)  # baseline is genuinely admissible (non-vacuous)
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


# ---------------------------------------------------------------------------
# DCE-EV-003 — no ambient authority (static naming facet)
# ---------------------------------------------------------------------------


@given(symbol=st.sampled_from(sorted(AMBIENT_SYMBOLS)))
def test_ambient_symbol_reference_is_inadmissible(symbol: str) -> None:
    """Any ambient symbol on an otherwise-admissible node is INADMISSIBLE (DCE-EV-003)."""
    # kind=const is admissible, so the ambient symbol is the *only* rejection cause.
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


# ---------------------------------------------------------------------------
# DCE-EV-004 — escape-closure (candidate node-membership)
# ---------------------------------------------------------------------------


@given(kind=st.sampled_from(sorted(ESCAPE_KINDS)))
def test_escape_kind_is_inadmissible(kind: str) -> None:
    """import / dynamic-eval / reflection / FFI / extension kinds are INADMISSIBLE (DCE-EV-004)."""
    prog = CandidateProgram(nodes=(CandidateNode(kind=kind),))
    analysis = analyze(prog)
    assert analysis.verdict is AdmissibilityVerdict.INADMISSIBLE
    assert f"non_vocabulary_kind:{kind}" in analysis.reasons


# ---------------------------------------------------------------------------
# DCE-EV-006 — inadmissible is conservative (fail-closed) + ★3 vacuous-True
# ---------------------------------------------------------------------------


@given(prog=programs_with_escape())
@settings(deadline=None, max_examples=75)
def test_any_program_with_an_escape_is_inadmissible(prog: CandidateProgram) -> None:
    """A program carrying ≥1 escape is never optimistically admitted (DCE-EV-006, ★4)."""
    assert not is_admissible(prog)
    assert analyze(prog).reasons  # non-empty reasons for an inadmissible program


@given(prog=programs_with_buried_escape())
@settings(deadline=None, max_examples=75)
def test_escape_buried_in_children_is_inadmissible(prog: CandidateProgram) -> None:
    """An escape nested below the root is caught by the recursive walk (DCE-EV-006, M-2).

    The root and its wrapping parents are all admissible; the only cause is the
    escape buried in ``children``, so this fails unless ``iter_nodes`` recurses —
    guarding against a silent regression to a top-level-only scan.
    """
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


# ---------------------------------------------------------------------------
# ★2 producer-optimism — AdmissibilityResult cannot outrun the pure predicate
# ---------------------------------------------------------------------------


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
            reasons=(),  # predicate yields a non-empty reason set
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
