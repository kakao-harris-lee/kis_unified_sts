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

**FINDING — detector 0, ``validate_stage_map``, cannot detect an order mutation at all, by
design.** It takes only ``stages: Mapping[CommitmentStep, Stage]`` (sequencer.py:141) — no order
argument — and rejects a stage map only for *which* steps it hosts (a hosting/seal check), never
*in what sequence* they run. Every one of our 56 variants supplies the same, unchanged stage map
(steps 2-11, 13, 14, built from whatever ``INJECTED_STAGE_STEPS`` the mutated order derives — which
by construction never includes steps 1, 12, or a Send-Boundary step, exactly like the unmutated
case). So ``validate_stage_map`` passes trivially for every variant in this matrix; it is named as
a candidate detector in the lane brief but is not counted as one of the three that actually fire
below.

**FINDING — one variant cannot even be represented: omitting step 15
(``SEND_BOUNDARY_VERIFICATION``).** ``SEND_BOUNDARY_STEPS`` is derived by
``COMMITMENT_FLOW_ORDER[COMMITMENT_FLOW_ORDER.index(SEND_BOUNDARY_VERIFICATION):]``
(vocabulary.py:237-238). Remove that step from the order and the production formula's own
``.index()`` call raises ``ValueError`` — the mutation cannot be patched through to the sequencer
because the *vocabulary module itself* cannot be reconstructed for that order. :func:`_derive`
reproduces this and the harness reports it as its own ``"UNREACHABLE"`` outcome, distinct from
"ran and matched the control" and "ran and differed" — a stronger, construction-time fail-closed
than either. (Detector 3, below, has no such fragility: :func:`_gateway_projection` is a plain
membership filter with no ``.index()`` call, so it still catches this variant on its own merits.)

**FINDING — detector 2 (``run_commitment_flow``) is blind to 12 of the 56 variants; detector 1
(the ADR order-pin) is the only one that reaches them.** ``run_commitment_flow``'s own execution is
provably *insensitive* to how the five Send-Boundary steps (15-19) are internally ordered among
themselves, and to duplicates of any of them, as long as none of them displaces
``SEND_BOUNDARY_VERIFICATION``'s own position: the post-loop send-boundary hand-off
(sequencer.py:520-580, ``mark_potentially_live`` / ``transmit`` / ``SEND_HANDED_OFF``) is
unconditional Python that never looks any of steps 16-19 up by identity, and
``SEND_BOUNDARY_STEPS`` — the only thing that reads their identities — converts the trailing slice
to a ``frozenset`` (vocabulary.py:239), which is insensitive to internal order and dedupes an
inserted duplicate for free. This is the exact shape of the drift the 2026-07-29 adversarial
review's MINOR-1 finding names for steps 2/3 (test_engine_package.py:134-146) — except here the
*positional* fingerprint (this module records each verdict's own ``step`` field in tuple order, so
a pure position swap among behaviourally-independent steps still differs) closes MINOR-1's specific
gap for steps 1-14; the residual dead zone is confined to the Send-Boundary segment 15-19, which the
sequencer never even walks.

**FINDING — detector 3 (the gateway's real execution order) narrows that 12-variant blind spot to
4.** Steps 15-19 are constitutionally the Send Boundary, and are *executed* — not by
``run_commitment_flow``, which explicitly refuses to host them — by ``BrokerEgressGateway.__call__``
(``tos/src/tos/egressgw/gateway.py``), the real ``Transmit`` implementation in non-test wiring. So
the tail's *executable* order lives there, not in the vocabulary tuple. But that executable order is
**not driven by ``CommitmentStep`` at all**: ``GatewayEvidenceRecord.kind`` is a free-form ``str``
(``records.py:564`` — no ``CommitmentStep`` field anywhere on it or on ``SendBoundaryContext``), and
grepping ``tos/src/tos/egressgw/*.py`` for ``CommitmentStep``/``COMMITMENT_FLOW_ORDER`` finds zero
matches in ``gateway.py`` or ``seal.py`` — the gateway's step 15-19 sequence is hardcoded Python
control flow, entirely independent of ``COMMITMENT_FLOW_ORDER``. Two consequences, both FINDINGs in
their own right:

- The executable send order is **not fully auditable from evidence** in a ``CommitmentStep``-identity
  sense: mapping ``GatewayEvidenceRecord.kind`` strings onto the ADR's five steps is a lossy,
  best-effort correspondence (:data:`_GATEWAY_KIND_TO_STEP`), grounded in the gateway's own inline
  step-number comments, not a structural guarantee. ``SEND_SEALED`` (the ``SendSeal``, Phase 4 작업
  6) belongs to a phase the gateway's own comment calls "step 15½" — it has **no** ``CommitmentStep``
  counterpart in the closed 19-step enum at all. Step 18 (``NETWORK_CALL``) has **no evidence kind of
  its own** on the success path — ``__call__``'s "step 18" block calls
  ``self._transport.send_once(...)`` directly and records nothing before the next (step 19)
  record, so the network-call moment itself is unobservable from evidence, full stop.
- Because the gateway consumes no ``CommitmentStep`` data, **no alias exists to patch on the gateway
  side** — unlike detector 2, detector 3 cannot be made "mutation-sensitive" by monkeypatching; its
  own real execution order is the *same fixed constant* for every one of the 56 variants (verified:
  :func:`_run_gateway_happy_path_kinds` is called once, not per variant). Detector 3 is therefore
  structurally closer to detector 1 (a static reference sequence) than to detector 2 (an
  execution that actually consumes the mutated order) — its distinct value is that the reference
  sequence is *extracted from one real gateway run* rather than hand-transcribed, so it would also
  catch the gateway's own code drifting away from the ADR order someday, which detector 1 cannot.

Net effect: of detector 2's 12-variant blind spot, detector 3 additionally catches every variant
that touches an *observable* boundary step (15, 16, 17, or 19) — including, notably, every
duplication of an observable step, which detector 2 cannot see (its ``SEND_BOUNDARY_STEPS``
``frozenset`` dedupes a duplicate for free) but detector 3's ``_gateway_projection`` does not
(no deduplication on the mutated-order side — see its docstring). What remains, in
:data:`_EXPECTED_ORDER_PIN_ONLY`, is exactly the 4 variants confined to step 18 alone (2 swaps with
a neighbour, its own omission, its own duplication): the one step neither execution path can ever
observe. Detector 1 catches all 4 (any swap/omission/duplication changes the tuple away from the
fixed 19-member ADR sequence), so **all 56 variants are caught by at least one detector** — "생존 0"
holds — but those 4 are, honestly, detector-1-only: a mutation confined to the network-call moment
is a real, joint blind spot of both execution paths today, not merely a weak test. RFC-005 §7:192
("SHALL NOT reorder") is what makes this a *contract* violation rather than a don't-care.

Runtime: 57 engine runs (1 control + 56 variants) through :func:`_run_variant`, each a single
``DECISION_TICK`` through the slice-1 stand-in wiring, plus exactly 1 real gateway run through
:func:`_run_gateway_happy_path_kinds` (detector 3's reference sequence is a fixed constant, so it is
computed once, not per variant) — well under the ~60s budget (see the lane's own measurement in its
commit message).

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

from ..egressgw._egressgw_fixtures import build_gateway, happy_context
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
# detector 3: the gateway's own real execution order for steps 15-19
# ---------------------------------------------------------------------------

#: Grounded in ``gateway.py``'s OWN inline step-number comments (not an independently invented
#: correspondence): "# -- step 15: the 17-item verify list --" (``VERIFY_ITEM``), the
#: ``SEND_STARTED`` record's own detail text citing "ADR-002-002 §11.4:606" (step 16's ADR line),
#: "# -- step 17: the POTENTIALLY_LIVE projection is observed --" (``POTENTIALLY_LIVE_OBSERVED``),
#: and "# -- step 19: evidence --" (``EGRESS_RESULT_RECORDED``). Two kinds have deliberately no
#: entry — see the two FINDINGs in the module docstring on ``SEND_SEALED`` ("step 15½", no
#: ``CommitmentStep`` counterpart at all) and step 18 (``NETWORK_CALL``, no evidence kind of its
#: own on the success path).
_GATEWAY_KIND_TO_STEP: dict[str, CommitmentStep] = {
    "VERIFY_ITEM": CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    "SEND_STARTED": CommitmentStep.SEND_STARTED_DURABLE,
    "POTENTIALLY_LIVE_OBSERVED": CommitmentStep.POTENTIALLY_LIVE_TRANSITION,
    "EGRESS_RESULT_RECORDED": CommitmentStep.EVIDENCE_RECORD,
}

#: The four ``CommitmentStep`` members the gateway's evidence can distinguish at all. Step 18
#: (``NETWORK_CALL``) and the unenumerated "step 15½" (``SEND_SEALED``) are excluded on purpose.
_GATEWAY_OBSERVABLE_STEPS: frozenset[CommitmentStep] = frozenset(
    _GATEWAY_KIND_TO_STEP.values()
)


def _gateway_projection(
    order: tuple[CommitmentStep, ...],
) -> tuple[CommitmentStep, ...]:
    """``order`` restricted to :data:`_GATEWAY_OBSERVABLE_STEPS`, preserving exact multiplicity.

    Deliberately **not** deduplicated: a genuine duplication mutation of an observable step (e.g.
    ``dup_16_SEND_STARTED_DURABLE``) must survive this filter as a real duplicate so the comparison
    in :func:`test_order_mutation_matrix_has_zero_survivors` can tell it apart from the control —
    only :func:`_translate_gateway_kinds` (the *real execution* side) collapses anything, and only
    because ``VERIFY_ITEM`` legitimately repeats 17 times for one step, an intrinsic multiplicity
    of the gateway's own design that has nothing to do with any mutation here.
    """
    return tuple(step for step in order if step in _GATEWAY_OBSERVABLE_STEPS)


def _run_gateway_happy_path_kinds() -> tuple[str, ...]:
    """Drive one real, fully-admitting send through :class:`BrokerEgressGateway`, reusing the
    egressgw suite's own baseline fixtures (the same ``happy_context`` / ``build_gateway`` that
    back ``test_the_baseline_send_is_accepted_and_records_every_step_in_order`` in
    ``tos/tests/egressgw/test_egressgw_gateway.py`` — imported, not copied), and return the raw,
    ordered ``kind`` strings its evidence sink recorded.

    Note what this does **not** exercise: the gateway never reads ``COMMITMENT_FLOW_ORDER`` /
    ``SEQUENCED_STEPS`` / any of the aliases :func:`_run_variant` patches (grepped: zero matches
    for any of those names in ``tos/src/tos/egressgw/*.py``) — its steps 15-19 order is hardcoded
    Python control flow in ``BrokerEgressGateway.__call__``. So unlike :func:`_run_variant`, this
    call's result is the **same constant** for every one of the 56 variants; the mutation-sensitive
    part of detector 3 is entirely in :func:`_gateway_projection` reading the mutated tuple, not in
    re-running the gateway per variant (see the module docstring FINDING on why this makes detector
    3 structurally closer to detector 1 than to detector 2).
    """
    attempt, context = happy_context()
    gateway, sink = build_gateway(attempt=attempt, context=context)
    handoff = gateway(attempt)
    assert handoff.accepted_for_transmission is True, (
        "the egressgw suite's own happy-path fixture must accept the send — got "
        f"{handoff!r}; a failure here means that fixture's shape changed, not that a mutation "
        "was caught"
    )
    return sink.kinds


def _translate_gateway_kinds(kinds: tuple[str, ...]) -> tuple[CommitmentStep, ...]:
    """Map ``kinds`` through :data:`_GATEWAY_KIND_TO_STEP`, dropping unmapped kinds (``SEND_SEALED``
    and anything else outside the table), then collapse consecutive repeats of the *same* step.

    The collapse exists solely to fold the 17 consecutive ``VERIFY_ITEM`` records into one
    ``SEND_BOUNDARY_VERIFICATION`` entry; it is a no-op for the other three mapped kinds, which a
    real send emits at most once each.
    """
    translated: list[CommitmentStep] = []
    for kind in kinds:
        step = _GATEWAY_KIND_TO_STEP.get(kind)
        if step is not None and (not translated or translated[-1] != step):
            translated.append(step)
    return tuple(translated)


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


#: The 4 variants where NEITHER detector 2 (``run_commitment_flow`` e2e) NOR detector 3 (the
#: gateway's real execution order) can tell the mutation apart from the control — only detector 1
#: (the ADR anchor) catches these. All four are confined to step 18 (``NETWORK_CALL``): detector 2
#: is blind to the whole Send-Boundary tail (the sequencer never runs it at all), and detector 3 is
#: blind to step 18 specifically because the gateway records no evidence kind for the network-call
#: moment itself (see ``_GATEWAY_OBSERVABLE_STEPS``). This is markedly narrower than detector 2's
#: own 12-variant blind spot (see the module docstring) — adding detector 3 shrinks the residual
#: from 12 to these 4, all attributable to the one genuinely un-instrumented step.
_EXPECTED_ORDER_PIN_ONLY: frozenset[str] = frozenset(
    {
        "swap_17_18",
        "swap_18_19",
        "omit_18_NETWORK_CALL",
        "dup_18_NETWORK_CALL",
    }
)

#: The one variant :func:`_derive` cannot even compute (see the module docstring FINDING).
_EXPECTED_UNREACHABLE: frozenset[str] = frozenset(
    {"omit_15_SEND_BOUNDARY_VERIFICATION"}
)


def _classify(
    name: str,
    order: tuple[CommitmentStep, ...],
    control: tuple[Any, ...],
    gateway_control: tuple[CommitmentStep, ...],
) -> tuple[bool, bool, bool, bool]:
    """Run all three detectors for one variant.

    Returns:
        ``(order_pin_red, e2e_red, gateway_red, unreachable)``.
    """
    mutant = _run_variant(order)
    order_pin_red = tuple(order) != _ADR_002_002_SECTION_11_ORDER
    e2e_red = mutant != control
    gateway_red = _gateway_projection(order) != gateway_control
    unreachable = mutant[0] == "UNREACHABLE"
    del name  # only used by the caller for bookkeeping
    return order_pin_red, e2e_red, gateway_red, unreachable


def test_order_mutation_matrix_has_zero_survivors() -> None:
    """(plan §3.2/§5 «순서 뮤테이션 매트릭스 생존 0») The load-bearing assertion.

    Runs the control (identity order) and all 56 variants through three detectors and requires, for
    every variant, at least one to be red:

    1. the independently-transcribed ADR order-pin (:data:`_ADR_002_002_SECTION_11_ORDER`) —
       always red for a genuine mutation, but by itself proves only that the *vocabulary tuple*
       drifted, not that any executable code path noticed;
    2. ``run_commitment_flow``'s own execution differing from the control (a raised exception, an
       unreachable derivation, or a differing :func:`_fingerprint`) — reaches steps 1-14 fully, but
       is structurally blind to internal reordering/duplication within the Send-Boundary tail
       (steps 15-19), which it never walks (see the module docstring FINDING);
    3. the egress gateway's own real send-boundary execution order (:func:`_gateway_projection`
       compared against one real run via :func:`_run_gateway_happy_path_kinds` /
       :func:`_translate_gateway_kinds`) — narrows detector 2's blind spot to just step 18
       (``NETWORK_CALL``), which the gateway records no evidence for on the success path.

    ``validate_stage_map`` ("detector 0") is not counted here: it takes no order argument at all
    and rejects a stage map only for *which* steps it hosts, never *in what sequence* — see the
    module docstring FINDING. It passes trivially for every variant in this matrix.

    The test pins the *shape* of the order-pin-only residual (now 4 variants, all step 18) and the
    1 unreachable variant against hand-derived expectations, so a future change that widens or
    narrows either execution detector's blind spot shows up as a failing assertion here rather than
    silently.
    """
    control = _run_variant(COMMITMENT_FLOW_ORDER)
    assert control[0] == "FLOW" and control[1] is True, (
        f"the control (unmutated order, run through the identical patch-and-execute harness) "
        f"must hand off cleanly — a failure here means the harness itself is broken, not that a "
        f"mutation was caught: {control!r}"
    )
    gateway_control = _translate_gateway_kinds(_run_gateway_happy_path_kinds())
    assert gateway_control == _gateway_projection(COMMITMENT_FLOW_ORDER), (
        "the gateway's real, unmutated execution order must match the ADR anchor's own "
        f"projection onto the observable steps — gateway={gateway_control!r} "
        f"anchor_projection={_gateway_projection(COMMITMENT_FLOW_ORDER)!r} (this re-derives "
        "test_egressgw_gateway.py::test_the_baseline_send_is_accepted_and_records_every_"
        "step_in_order through this module's own mapping, as a cross-check)"
    )

    survivors: list[str] = []
    order_pin_only: list[str] = []
    unreachable: list[str] = []
    for name, order in _ALL_VARIANTS:
        order_pin_red, e2e_red, gateway_red, is_unreachable = _classify(
            name, order, control, gateway_control
        )
        if is_unreachable:
            unreachable.append(name)
        elif not e2e_red and not gateway_red:
            order_pin_only.append(name)
        if not order_pin_red and not e2e_red and not gateway_red:
            survivors.append(name)

    assert not survivors, (
        f"{len(survivors)}/{len(_ALL_VARIANTS)} order-mutation variants survived ALL THREE "
        f"detectors (ADR order-pin, run_commitment_flow e2e, gateway execution order) — plan "
        f"§3.2/§5 requires 0 survivors: {survivors}"
    )
    assert set(order_pin_only) == _EXPECTED_ORDER_PIN_ONLY, (
        "the set of variants only the ADR order-pin catches (both execution detectors identical "
        f"to their controls) drifted from the expected set — actual={sorted(order_pin_only)} "
        f"expected={sorted(_EXPECTED_ORDER_PIN_ONLY)}"
    )
    assert set(unreachable) == _EXPECTED_UNREACHABLE, (
        f"the set of variants whose derivation formula itself raises drifted — "
        f"actual={sorted(unreachable)} expected={sorted(_EXPECTED_UNREACHABLE)}"
    )
