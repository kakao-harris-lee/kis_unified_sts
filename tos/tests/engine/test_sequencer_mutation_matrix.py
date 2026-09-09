"""19-step commitment-flow order mutation matrix (Phase 3 wave 3 slice F; plan §3.2/§5).

Plan text says "13 adjacent pairs"; the tuple (:data:`~tos.engine.vocabulary.COMMITMENT_FLOW_ORDER`)
has 19 steps, so there are **18** adjacent pairs, not 13 (the plan's arithmetic is wrong; this
module's docstring is the corrected count, per the lane brief). The matrix is therefore
18 swaps + 19 omissions + 19 duplications = **56 variants**, plus one control (the identity order).

**Why monkeypatching ``COMMITMENT_FLOW_ORDER`` alone does nothing.** Nothing in the runtime path
reads that name at call time. ``tos/src/tos/engine/vocabulary.py`` computes
``SEND_BOUNDARY_STEPS``, ``SEQUENCED_STEPS``, and ``INJECTED_STAGE_STEPS`` **once, at import
time**, by slicing/filtering ``COMMITMENT_FLOW_ORDER`` (vocabulary.py:236-256). Every consumer then
does ``from tos.engine.vocabulary import SEQUENCED_STEPS`` (etc.) — a *name binding*, copied into
the consumer's own module namespace at *its* import time, not a live reference back to
``vocabulary``. Patching ``tos.engine.vocabulary.COMMITMENT_FLOW_ORDER`` after both modules have
loaded therefore reaches nobody: ``tos.engine.sequencer.SEQUENCED_STEPS`` (the tuple
``run_commitment_flow`` actually iterates, sequencer.py:319) keeps pointing at the *original* tuple
object. To make a mutation reach the code under test, every copied alias has to be repatched
**with the same value the production formula would compute for the mutated order** — recomputed
here in :func:`_derive`, replicating vocabulary.py:236-256 verbatim, not reused via
``importlib.reload`` (a reload would mint new ``CommitmentStep``/enum objects and break every
``is`` identity check the sequencer relies on — design #31 §4.2's positive-identity gates — so it
would silently invalidate the whole harness rather than testing anything).

**Patched names** (see :func:`_run_variant`):

- ``tos.engine.sequencer.SEQUENCED_STEPS`` — the loop ``run_commitment_flow`` walks
  (sequencer.py:319). This is the load-bearing patch; nothing else changes traversal order.
- ``tos.engine.sequencer.SEND_BOUNDARY_STEPS`` / ``COORDINATOR_REALIZED_STEPS`` — read by
  ``validate_stage_map`` (sequencer.py:141-163). For every one of our 56 variants this check ends
  up a no-op: it only rejects a *stage map* that hosts a step outside its class, and the stage map
  we pass never contains steps 1, 12, or 15-19 regardless of how the order is mutated (see the
  module-level FINDING below on why ``validate_stage_map`` cannot detect an order mutation at all).
  Patched anyway for honesty/consistency with the derivation.
- ``tos.engine.standins.INJECTED_STAGE_STEPS`` — the set :func:`provisional_stage_map` iterates to
  build the stand-in map handed to ``run_commitment_flow`` as its ``stages`` argument
  (standins.py:144). This is the *second* load-bearing patch: without it, a mutation that changes
  which steps are "injected" (e.g. a swap that moves ``SEND_BOUNDARY_VERIFICATION``, pulling a
  Send-Boundary step into the sequenced range) would run through the *original* stand-in map and
  never notice.
- ``tos.engine.vocabulary.{COMMITMENT_FLOW_ORDER, SEQUENCED_STEPS, SEND_BOUNDARY_STEPS,
  COORDINATOR_REALIZED_STEPS, INJECTED_STAGE_STEPS, _STEP_NUMBERS}`` — the source module itself.
  Nothing in the runtime path reads these names fresh (every consumer already copied its own
  alias), **except** ``step_number()`` (vocabulary.py:272-283), which is a *function* whose global
  lookups resolve against ``tos.engine.vocabulary.__dict__`` at *call* time, not at the call site's
  import time — so patching ``vocabulary_module._STEP_NUMBERS`` **is** live and keeps halt/error
  text readable under a mutated order. The rest of the vocabulary-level patches are informational
  (nobody left to reach through them at runtime) but are applied anyway so a future consumer that
  reads ``tos.engine.vocabulary`` directly is exercised too, and so the module is internally
  consistent for the duration of the patch.
- **Deliberately NOT patched**: ``tos.engine.__init__``'s re-exports (``tos.engine.SEQUENCED_STEPS``
  etc., ``tos/src/tos/engine/__init__.py:200-237``). Grepped: the only consumers of that
  package-level path are test modules' ``@pytest.mark.parametrize(..., list(INJECTED_STAGE_STEPS))``
  decorators, evaluated once at collection time, long before any test body (ours included) runs —
  patching them would have no observable effect and would misleadingly suggest they matter to the
  mutation's reach.

**FINDING — ``validate_stage_map`` cannot detect an order mutation at all.** It takes only
``stages: Mapping[CommitmentStep, Stage]`` (sequencer.py:141), no order argument, and rejects a
stage map only for *which* steps it hosts, never *in what sequence* they run. Every one of our 56
variants supplies the same, unchanged stage map (steps 2-11, 13, 14, built from whatever
``INJECTED_STAGE_STEPS`` the mutated order derives — which by construction never includes steps 1,
12, or a Send-Boundary step, exactly like the unmutated case). So ``validate_stage_map`` passes
trivially for every variant in this matrix; it is not one of the two detectors that actually fire
below, despite being named as a candidate in the lane brief.

**FINDING — one variant cannot even be represented: omitting step 15
(``SEND_BOUNDARY_VERIFICATION``).** ``SEND_BOUNDARY_STEPS`` is derived by
``COMMITMENT_FLOW_ORDER[COMMITMENT_FLOW_ORDER.index(SEND_BOUNDARY_VERIFICATION):]``
(vocabulary.py:237-238). Remove that step from the order and the production formula's own
``.index()`` call raises ``ValueError`` — the mutation cannot be patched through to the sequencer
because the *vocabulary module itself* cannot be reconstructed for that order. :func:`_derive`
reproduces this and the harness reports it as its own ``"UNREACHABLE"`` outcome, distinct from
"ran and matched the control" and "ran and differed" — a stronger, construction-time fail-closed
than either.

**FINDING — the ADR order-pin is the only detector that reaches 12 of the 56 variants.**
``run_commitment_flow``'s own execution is provably *insensitive* to how the five Send-Boundary
steps (15-19) are internally ordered among themselves, and to duplicates of any of them, as long as
none of them displaces ``SEND_BOUNDARY_VERIFICATION``'s own position: the post-loop
send-boundary hand-off (sequencer.py:520-580, ``mark_potentially_live`` / ``transmit`` /
``SEND_HANDED_OFF``) is unconditional Python that never looks any of steps 16-19 up by identity,
and ``SEND_BOUNDARY_STEPS`` — the only thing that reads their identities — converts the trailing
slice to a ``frozenset`` (vocabulary.py:239), which is insensitive to internal order and dedupes an
inserted duplicate for free. Exactly 12 variants hit this dead zone (3 adjacent swaps confined to
{16,17,18,19}, 4 omissions of {16,17,18,19}, and 5 duplications of {15,16,17,18,19} — see
``_EXPECTED_ORDER_PIN_ONLY``): ``run_commitment_flow`` produces a **byte-identical** outcome to the
control for every one of them. This is the exact shape of the drift the 2026-07-29 adversarial
review's MINOR-1 finding names for steps 2/3 (test_engine_package.py:134-146) — except here the
*positional* fingerprint (this module records each verdict's own ``step`` field in tuple order, so
a pure position swap among behaviourally-independent steps still differs) closes MINOR-1's specific
gap for steps 1-14; the residual dead zone is confined to the Send-Boundary segment 15-19, which the
sequencer never even walks. Only the independently-transcribed ADR anchor
(:data:`_ADR_002_002_SECTION_11_ORDER`, duplicated from test_engine_package.py's own anchor rather
than imported — an anchor proves nothing if it is derived from, or shares a live binding with, the
thing it is supposed to catch) catches these 12. The remaining 43 reachable variants, plus the 1
unreachable one, are also caught by the ADR anchor (any swap/omission/duplication changes the tuple
away from the fixed 19-member ADR sequence), so **all 56 are caught by at least one detector** —
"생존 0" holds — but 12 of the 56 are, honestly, order-pin-only: reordering/duplicating the
Send-Boundary tail is a real behavioural blind spot in ``run_commitment_flow`` today, not merely a
weak test. RFC-005 §7:192 ("SHALL NOT reorder") is what makes this a *contract* violation rather
than a don't-care; ``run_commitment_flow``'s honesty about its own scope (steps 1-14 only, design
#31 §4.5 item-7) is exactly why it cannot be the sole guard for steps 15-19.

Runtime: 57 engine runs (1 control + 56 variants), each a single ``DECISION_TICK`` through the
slice-1 stand-in wiring — well under the ~60s budget (see the lane's own measurement in its commit
message).

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from tos.engine import sequencer as sequencer_module
from tos.engine import standins as standins_module
from tos.engine import vocabulary as vocabulary_module
from tos.engine.vocabulary import COMMITMENT_FLOW_ORDER, CommitmentStep

from ._engine_fixtures import admitting_stages, build_core, decision_tick

# ---------------------------------------------------------------------------
# the independent order anchor
# ---------------------------------------------------------------------------

#: Transcribed independently from ADR-002-002 §11 (spec lines 582-609), duplicating (not
#: importing) test_engine_package.py's own ``_ADR_002_002_SECTION_11_ORDER``. Duplicated on
#: purpose: importing the other module's copy would make this test's "order pin" detector share a
#: single set of typed characters with the thing it exists to catch drift in, which is exactly the
#: self-reference the 2026-07-29 review's MINOR-1 finding rejected (test_engine_package.py:134-146).
_ADR_002_002_SECTION_11_ORDER: tuple[CommitmentStep, ...] = (
    CommitmentStep.DECISION_PROPOSAL,
    CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
    CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    CommitmentStep.INDEPENDENT_APPROVAL,
    CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
    CommitmentStep.AGGREGATE_RISK_DECISION,
    CommitmentStep.ACTION_FLOW_DECISION,
    CommitmentStep.LEDGER_VERIFICATION,
    CommitmentStep.ATOMIC_COMMIT,
    CommitmentStep.COMMITMENT_UNAVAILABILITY,
    CommitmentStep.ORDER_CONFORMANCE_PROOF,
    CommitmentStep.ATTEMPT_REQUEST,
    CommitmentStep.ATTEMPT_BIND_VERIFICATION,
    CommitmentStep.TRANSMISSION_CAPABILITY,
    CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    CommitmentStep.SEND_STARTED_DURABLE,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
    CommitmentStep.NETWORK_CALL,
    CommitmentStep.EVIDENCE_RECORD,
)

assert len(_ADR_002_002_SECTION_11_ORDER) == 19
assert set(_ADR_002_002_SECTION_11_ORDER) == set(CommitmentStep)


# ---------------------------------------------------------------------------
# recomputing vocabulary.py's derived structures for a mutated order
# ---------------------------------------------------------------------------


class _DerivationUnreachable(Exception):
    """The production derivation formula itself cannot be recomputed for this order.

    Raised when ``order.index(CommitmentStep.SEND_BOUNDARY_VERIFICATION)`` fails exactly as the
    shipped ``vocabulary.py:237-238`` would fail — this mutation cannot be patched through to the
    sequencer at all, which is a stronger (construction-time) fail-closed than any halt the
    sequencer itself could produce.
    """


@dataclass(frozen=True)
class _Derived:
    """The vocabulary.py-derived structures recomputed for one candidate order."""

    send_boundary_steps: frozenset[CommitmentStep]
    sequenced_steps: tuple[CommitmentStep, ...]
    coordinator_realized_steps: frozenset[CommitmentStep]
    injected_stage_steps: tuple[CommitmentStep, ...]
    step_numbers: dict[CommitmentStep, int]


#: Not order-derived in production (vocabulary.py:263-266 is a literal), so it is identical for
#: every variant and never needs recomputing from the mutated order.
_COORDINATOR_REALIZED_STEPS: frozenset[CommitmentStep] = frozenset(
    {CommitmentStep.DECISION_PROPOSAL, CommitmentStep.ATTEMPT_REQUEST}
)


def _derive(order: tuple[CommitmentStep, ...]) -> _Derived:
    """Recompute ``SEND_BOUNDARY_STEPS`` / ``SEQUENCED_STEPS`` / ``INJECTED_STAGE_STEPS`` for
    ``order``, replicating vocabulary.py:236-256's formulas verbatim so a mutation's effect
    propagates through the identical derivation the shipped module performs once at import time.

    Args:
        order: A candidate (possibly mutated) commitment-flow order.

    Returns:
        The recomputed derived structures.

    Raises:
        _DerivationUnreachable: If ``order`` has no ``SEND_BOUNDARY_VERIFICATION`` member — the
            same case in which the shipped formula's own ``.index()`` call would raise.
    """
    try:
        boundary_start = order.index(CommitmentStep.SEND_BOUNDARY_VERIFICATION)
    except ValueError as exc:
        raise _DerivationUnreachable(
            "COMMITMENT_FLOW_ORDER.index(SEND_BOUNDARY_VERIFICATION) raised ValueError for "
            f"this mutated order ({exc}) — vocabulary.py's own formula (lines 237-238) cannot "
            "locate the Send Boundary anchor, so SEND_BOUNDARY_STEPS/SEQUENCED_STEPS/"
            "INJECTED_STAGE_STEPS cannot be recomputed and this mutation cannot be patched "
            "through to the sequencer at all"
        ) from exc
    send_boundary = frozenset(order[boundary_start:])
    sequenced = tuple(step for step in order if step not in send_boundary)
    injected = tuple(
        step for step in sequenced if step not in _COORDINATOR_REALIZED_STEPS
    )
    step_numbers = {step: number for number, step in enumerate(order, start=1)}
    return _Derived(
        send_boundary_steps=send_boundary,
        sequenced_steps=sequenced,
        coordinator_realized_steps=_COORDINATOR_REALIZED_STEPS,
        injected_stage_steps=injected,
        step_numbers=step_numbers,
    )


# ---------------------------------------------------------------------------
# running the slice-1 e2e fixture under a patched order
# ---------------------------------------------------------------------------


def _fingerprint(result: Any) -> tuple[Any, ...]:
    """A canonical, order-sensitive fingerprint of one ``EventResult`` (the sequencer's outcome
    "digest" surrogate — the sequencer emits no single hash of its own, so this closes the
    behavioural comparison the lane brief asks for: "outcome digest ... differs from the control").

    Deliberately includes each verdict's own ``step`` field *in the tuple's own position order* —
    not compared as a set — so a pure positional swap among behaviourally-independent steps (the
    2026-07-29 review's MINOR-1 gap, test_engine_package.py:134-146) still produces a different
    fingerprint here, even where it would not have differed under an order-blind comparison.
    """
    flow = result.flow
    if flow is None:
        return ("NO_FLOW", result.halt_reason)
    verdict_trace = tuple(
        (verdict.step, verdict.outcome, verdict.bound_digest, verdict.bound_identity)
        for verdict in flow.verdicts
    )
    return (
        "FLOW",
        flow.handed_off,
        flow.halt_step,
        flow.halt_reason,
        verdict_trace,
        None if flow.attempt is None else flow.attempt.attempt_id,
        None if flow.handoff is None else flow.handoff.accepted_for_transmission,
    )


def _run_variant(order: tuple[CommitmentStep, ...]) -> tuple[Any, ...]:
    """Patch every alias :func:`_derive` can reach for ``order``, run one clean ``DECISION_TICK``
    through the slice-1 stand-in wiring, and fingerprint the outcome.

    Returns:
        ``("FLOW", ...)`` from :func:`_fingerprint` on a normal (possibly halted) run,
        ``("RAISED", exc_type_name, str(exc))`` if the run itself raised uncaught, or
        ``("UNREACHABLE", detail)`` if :func:`_derive` could not even be recomputed.
    """
    try:
        derived = _derive(order)
    except _DerivationUnreachable as exc:
        return ("UNREACHABLE", str(exc))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sequencer_module, "SEQUENCED_STEPS", derived.sequenced_steps)
        mp.setattr(sequencer_module, "SEND_BOUNDARY_STEPS", derived.send_boundary_steps)
        mp.setattr(
            sequencer_module,
            "COORDINATOR_REALIZED_STEPS",
            derived.coordinator_realized_steps,
        )
        mp.setattr(
            standins_module, "INJECTED_STAGE_STEPS", derived.injected_stage_steps
        )
        mp.setattr(vocabulary_module, "COMMITMENT_FLOW_ORDER", order)
        mp.setattr(vocabulary_module, "SEQUENCED_STEPS", derived.sequenced_steps)
        mp.setattr(
            vocabulary_module, "SEND_BOUNDARY_STEPS", derived.send_boundary_steps
        )
        mp.setattr(
            vocabulary_module,
            "COORDINATOR_REALIZED_STEPS",
            derived.coordinator_realized_steps,
        )
        mp.setattr(
            vocabulary_module, "INJECTED_STAGE_STEPS", derived.injected_stage_steps
        )
        mp.setattr(vocabulary_module, "_STEP_NUMBERS", derived.step_numbers)
        try:
            core, _sink = build_core(stages=admitting_stages())
            result = core.handle(decision_tick(sequence=1))
        except (
            Exception
        ) as exc:  # noqa: BLE001 - an uncaught raise IS a detector signal here
            return ("RAISED", type(exc).__name__, str(exc))
    return _fingerprint(result)


# ---------------------------------------------------------------------------
# the 56-variant matrix
# ---------------------------------------------------------------------------


def _adjacent_swaps() -> list[tuple[str, tuple[CommitmentStep, ...]]]:
    """The 18 adjacent-pair swaps (19 steps -> 18 adjacencies; the plan's "13" is arithmetic
    error, corrected here per the lane brief)."""
    variants: list[tuple[str, tuple[CommitmentStep, ...]]] = []
    for index in range(len(COMMITMENT_FLOW_ORDER) - 1):
        order = list(COMMITMENT_FLOW_ORDER)
        order[index], order[index + 1] = order[index + 1], order[index]
        variants.append((f"swap_{index + 1}_{index + 2}", tuple(order)))
    return variants


def _omissions() -> list[tuple[str, tuple[CommitmentStep, ...]]]:
    """The 19 single-step omissions."""
    variants: list[tuple[str, tuple[CommitmentStep, ...]]] = []
    for index, step in enumerate(COMMITMENT_FLOW_ORDER):
        order = list(COMMITMENT_FLOW_ORDER)
        del order[index]
        variants.append((f"omit_{index + 1}_{step.value}", tuple(order)))
    return variants


def _duplications() -> list[tuple[str, tuple[CommitmentStep, ...]]]:
    """The 19 single-step duplications (the duplicate immediately follows the original)."""
    variants: list[tuple[str, tuple[CommitmentStep, ...]]] = []
    for index, step in enumerate(COMMITMENT_FLOW_ORDER):
        order = list(COMMITMENT_FLOW_ORDER)
        order.insert(index + 1, step)
        variants.append((f"dup_{index + 1}_{step.value}", tuple(order)))
    return variants


_ALL_VARIANTS: tuple[tuple[str, tuple[CommitmentStep, ...]], ...] = tuple(
    _adjacent_swaps() + _omissions() + _duplications()
)


def test_the_matrix_has_exactly_fifty_six_variants() -> None:
    """(§3.2 correction) 18 adjacent swaps + 19 omissions + 19 duplications = 56, not the plan's
    "13 adjacent pairs" (a 19-step tuple has 18 adjacencies, not 13)."""
    assert len(_adjacent_swaps()) == 18
    assert len(_omissions()) == 19
    assert len(_duplications()) == 19
    assert len(_ALL_VARIANTS) == 56
    assert (
        len({name for name, _order in _ALL_VARIANTS}) == 56
    ), "variant names must be unique"


# The 12 variants where run_commitment_flow's own execution is byte-identical to the control (see
# the module docstring FINDING on the Send-Boundary dead zone) — caught only by the ADR order-pin.
_EXPECTED_ORDER_PIN_ONLY: frozenset[str] = frozenset(
    {
        "swap_16_17",
        "swap_17_18",
        "swap_18_19",
        "omit_16_SEND_STARTED_DURABLE",
        "omit_17_POTENTIALLY_LIVE_TRANSITION",
        "omit_18_NETWORK_CALL",
        "omit_19_EVIDENCE_RECORD",
        "dup_15_SEND_BOUNDARY_VERIFICATION",
        "dup_16_SEND_STARTED_DURABLE",
        "dup_17_POTENTIALLY_LIVE_TRANSITION",
        "dup_18_NETWORK_CALL",
        "dup_19_EVIDENCE_RECORD",
    }
)

#: The one variant :func:`_derive` cannot even compute (see the module docstring FINDING).
_EXPECTED_UNREACHABLE: frozenset[str] = frozenset(
    {"omit_15_SEND_BOUNDARY_VERIFICATION"}
)


def test_order_mutation_matrix_has_zero_survivors() -> None:
    """(plan §3.2/§5 «순서 뮤테이션 매트릭스 생존 0») The load-bearing assertion.

    Runs the control (identity order) and all 56 variants through the same harness
    (:func:`_run_variant`) and requires, for every variant, at least one of two detectors to be
    red: the independently-transcribed ADR order-pin (:data:`_ADR_002_002_SECTION_11_ORDER`), or
    ``run_commitment_flow``'s own execution differing from the control (a raised exception, an
    unreachable derivation, or a differing :func:`_fingerprint`). ``validate_stage_map`` is not a
    third detector here — see the module docstring FINDING on why it cannot see an order mutation
    at all.

    The test also pins the *shape* of the 12 order-pin-only survivors and the 1 unreachable
    variant against hand-derived expectations, so a future change that widens or narrows
    ``run_commitment_flow``'s Send-Boundary blind spot shows up as a failing assertion here rather
    than silently.
    """
    control = _run_variant(COMMITMENT_FLOW_ORDER)
    assert control[0] == "FLOW" and control[1] is True, (
        f"the control (unmutated order, run through the identical patch-and-execute harness) "
        f"must hand off cleanly — a failure here means the harness itself is broken, not that a "
        f"mutation was caught: {control!r}"
    )

    survivors: list[str] = []
    order_pin_only: list[str] = []
    unreachable: list[str] = []
    for name, order in _ALL_VARIANTS:
        mutant = _run_variant(order)
        order_pin_red = tuple(order) != _ADR_002_002_SECTION_11_ORDER
        e2e_red = mutant != control
        if mutant[0] == "UNREACHABLE":
            unreachable.append(name)
        elif not e2e_red:
            order_pin_only.append(name)
        if not order_pin_red and not e2e_red:
            survivors.append(f"{name}: mutant={mutant!r}")

    assert not survivors, (
        f"{len(survivors)}/{len(_ALL_VARIANTS)} order-mutation variants survived BOTH detectors "
        f"(ADR order-pin AND run_commitment_flow e2e) — plan §3.2/§5 requires 0 survivors: "
        f"{survivors}"
    )
    assert set(order_pin_only) == _EXPECTED_ORDER_PIN_ONLY, (
        "the set of variants only the ADR order-pin catches (run_commitment_flow's own execution "
        "is identical to the control — the Send-Boundary dead zone documented in this module's "
        f"docstring) drifted from the expected set — actual={sorted(order_pin_only)} "
        f"expected={sorted(_EXPECTED_ORDER_PIN_ONLY)}"
    )
    assert set(unreachable) == _EXPECTED_UNREACHABLE, (
        f"the set of variants whose derivation formula itself raises drifted — "
        f"actual={sorted(unreachable)} expected={sorted(_EXPECTED_UNREACHABLE)}"
    )
