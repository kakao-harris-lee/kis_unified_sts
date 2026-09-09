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

**FINDING — detector 3 (the gateway's real execution order) closes that 12-variant blind spot
entirely (2026-09-09, KW3-GW, commit 9de02dcc).** Steps 15-19 are constitutionally the Send
Boundary, and are *executed* — not by ``run_commitment_flow``, which explicitly refuses to host
them — by ``BrokerEgressGateway.__call__`` (``tos/src/tos/egressgw/gateway.py``), the real
``Transmit`` implementation in non-test wiring. So the tail's *executable* order lives there, not
in the vocabulary tuple. Before KW3-GW, that executable order was not driven by ``CommitmentStep``
at all and was not auditable from evidence (this lane's own ffaafcb4 finding: ``kind`` was a
free-form ``str``, step 18 recorded nothing, ``SEND_SEALED`` sat at an undocumented "step 15½").
KW3-GW closed this at the production layer: ``GatewayEvidenceRecord`` gained a
``step: CommitmentStep | None`` field (``records.py:608-639``), a ``FIXED_KIND_STEPS`` map the
gateway stamps every non-``SEND_REFUSED`` record from, a new ``NETWORK_CALL_ENTERED`` record
emitted right before ``send_once`` (closing the step-18 gap), and a
``_step_matches_fixed_kind_when_given`` model validator that rejects a stamped step disagreeing
with its kind — so the correspondence is now enforced structurally, not merely documented. Two
points remain true even after the fix:

- Because the gateway still consumes no ``CommitmentStep`` data (it only ever *stamps* one on
  outgoing records — grepped, zero reads of ``COMMITMENT_FLOW_ORDER``/``SEQUENCED_STEPS``
  anywhere in ``tos/src/tos/egressgw/*.py``), **no alias exists to patch on the gateway side** —
  unlike detector 2, detector 3 cannot be made "mutation-sensitive" by monkeypatching; its own real
  execution order is the *same fixed constant* for every one of the 56 variants (verified:
  :func:`_run_gateway_happy_path_steps` is called once, not per variant). Detector 3 is therefore
  structurally closer to detector 1 (a static reference sequence) than to detector 2 (an execution
  that actually consumes the mutated order) — its distinct value is that the reference sequence is
  *extracted from one real gateway run* rather than hand-transcribed, so it would also catch the
  gateway's own code drifting away from the ADR order someday, which detector 1 cannot.
- Step 15 legitimately produces **two** distinct real evidence moments (the ``VERIFY_ITEM`` cluster
  and a separate ``SEND_SEALED`` record — ``SEND_SEALED`` is step 15's own output per
  ``FIXED_KIND_STEPS``, not a separate un-enumerated phase any more). :func:`_gateway_projection`
  accounts for this with an explicit per-step moment count (:data:`_STEP_MOMENT_MULTIPLICITY`)
  rather than silently collapsing it away, so a genuine mutation duplicate of any observable step
  (including step 15 itself) still produces a distinguishable, differently-shaped sequence.

Net effect: detector 3 now catches every one of detector 2's 12-variant blind spot, including step
18 (via the new ``NETWORK_CALL_ENTERED`` record) and every duplication of an observable step
(detector 2's ``SEND_BOUNDARY_STEPS`` ``frozenset`` dedupes a duplicate for free; detector 3's
expansion-based projection does not). :data:`_EXPECTED_ORDER_PIN_ONLY` is therefore **empty** —
verified empirically, not assumed (see its own docstring) — so every one of the 56 variants is now
caught by at least two of the three detectors, not merely one. RFC-005 §7:192 ("SHALL NOT reorder")
is a contract over the whole 19-step order, and as of this lane's second round it is enforced, for
the Send-Boundary tail specifically, by real executable code (the gateway) rather than only by a
hand-transcribed anchor.

Runtime: 57 engine runs (1 control + 56 variants) through :func:`_run_variant`, each a single
``DECISION_TICK`` through the slice-1 stand-in wiring, plus exactly 1 real gateway run through
:func:`_run_gateway_happy_path_steps` (detector 3's reference sequence is a fixed constant, so it
is computed once, not per variant) — well under the ~60s budget (see the lane's own measurement in
its commit message).

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

#: How many distinct real evidence *moments* one occurrence of an observable step produces on a
#: real send (production field, Phase 3 wave 3 KW3-GW — ``GatewayEvidenceRecord.step`` /
#: ``FIXED_KIND_STEPS``, ``tos/src/tos/egressgw/records.py:608-639``). Step 15 alone produces
#: two: the 17 ``VERIFY_ITEM`` records (collapsed to one representative entry — see
#: :func:`_run_gateway_happy_path_steps`) and a separate ``SEND_SEALED`` record, both legitimately
#: ``CommitmentStep.SEND_BOUNDARY_VERIFICATION`` per ``FIXED_KIND_STEPS`` — ``SEND_SEALED`` is step
#: 15's own output (KW3-GW's commit message), not the unenumerated "step 15½" this lane's earlier
#: finding (commit ffaafcb4) described before KW3-GW folded it back into step 15 proper. Every
#: other observable step produces exactly one moment; step 18 (``NETWORK_CALL``) now has one too,
#: via the new ``NETWORK_CALL_ENTERED`` record KW3-GW added right before ``send_once`` — the
#: no-evidence-for-step-18 finding this lane raised in ffaafcb4 is resolved.
_STEP_MOMENT_MULTIPLICITY: dict[CommitmentStep, int] = {
    CommitmentStep.SEND_BOUNDARY_VERIFICATION: 2,
    CommitmentStep.SEND_STARTED_DURABLE: 1,
    CommitmentStep.POTENTIALLY_LIVE_TRANSITION: 1,
    CommitmentStep.NETWORK_CALL: 1,
    CommitmentStep.EVIDENCE_RECORD: 1,
}

#: All five Send-Boundary steps are now observable (KW3-GW closed the step-18 gap) — this is no
#: longer a strict subset of the tail the way it was in ffaafcb4.
_GATEWAY_OBSERVABLE_STEPS: frozenset[CommitmentStep] = frozenset(
    _STEP_MOMENT_MULTIPLICITY
)


def _gateway_projection(
    order: tuple[CommitmentStep, ...],
) -> tuple[CommitmentStep, ...]:
    """Expand every observable occurrence in ``order`` by its :data:`_STEP_MOMENT_MULTIPLICITY`,
    so the result is directly comparable to :func:`_run_gateway_happy_path_steps`'s collapsed
    output on the unmutated control (both produce ``[15, 15, 16, 17, 18, 19]``).

    Nothing here collapses a genuine order-mutation duplicate: a mutation that duplicates an
    observable step in ``order`` (e.g. ``dup_16_SEND_STARTED_DURABLE``) still produces two
    separate — each further expanded — occurrences, so it remains distinguishable from the
    control. Only the *intrinsic* step-15 multiplicity (constant, independent of any mutation
    here) is folded into the per-step expansion factor.
    """
    projected: list[CommitmentStep] = []
    for step in order:
        multiplicity = _STEP_MOMENT_MULTIPLICITY.get(step)
        if multiplicity is not None:
            projected.extend([step] * multiplicity)
    return tuple(projected)


def _run_gateway_happy_path_steps() -> tuple[CommitmentStep, ...]:
    """Drive one real, fully-admitting send through :class:`BrokerEgressGateway`, reusing the
    egressgw suite's own baseline fixtures (the same ``happy_context`` / ``build_gateway`` that
    back ``test_the_baseline_send_records_the_commitment_step_sequence_exactly`` in
    ``tos/tests/egressgw/test_egressgw_gateway.py`` — imported, not copied), and return the
    ordered, stamped :attr:`~tos.egressgw.records.GatewayEvidenceRecord.step` sequence, reading
    the production field directly rather than re-deriving a kind→step correspondence by hand (the
    approach ffaafcb4 used before KW3-GW added the field).

    Mirrors that test's own collapse idiom exactly: only *consecutive* ``VERIFY_ITEM`` records
    fold into one representative entry (17 -> 1); ``SEND_SEALED`` stays its own separate entry
    even though it shares the same step, because it is a distinct real evidence moment, not a
    repeat of the same one (see :data:`_STEP_MOMENT_MULTIPLICITY`).

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
    collapsed: list[CommitmentStep] = []
    previous_kind: str | None = None
    for record in sink.records:
        assert record.step is not None, (
            f"gateway record kind={record.kind!r} was never stamped with a step — KW3-GW "
            "(records.py:608-639) should have made every non-SEND_REFUSED kind on the happy "
            "path carry one"
        )
        if record.kind == "VERIFY_ITEM" and previous_kind == "VERIFY_ITEM":
            previous_kind = record.kind
            continue
        collapsed.append(record.step)
        previous_kind = record.kind
    return tuple(collapsed)


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


#: The variants where NEITHER executable detector (2, ``run_commitment_flow`` e2e; 3, the
#: gateway's real execution order) can tell the mutation apart from the control — i.e. the actual
#: "생존" (survivor) set the plan's exit condition names. Empty: KW3-GW (commit 9de02dcc) stamped
#: ``CommitmentStep`` on every gateway record and closed the step-18 gap this lane's ffaafcb4
#: finding raised, so detector 3 — with the expansion-aware :func:`_gateway_projection` above —
#: now catches every one of detector 2's 12-variant blind spot (verified empirically both
#: directions: see :func:`test_order_mutation_matrix_has_zero_survivors`'s docstring and this
#: lane's commit messages for the exact 12/29-name reproductions). Kept as a named constant,
#: rather than inlined as a bare ``[]`` in the assertion below, so a future regression that
#: reopens any gap reads as "the expected empty survivor set drifted" rather than a bare,
#: unexplained list literal.
_EXPECTED_ORDER_PIN_ONLY: frozenset[str] = frozenset()

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

    A "생존" (survivor) is a variant neither **executable** detector notices:

    2. ``run_commitment_flow``'s own execution differing from the control (a raised exception, an
       unreachable derivation, or a differing :func:`_fingerprint`) — reaches steps 1-14 fully, but
       is structurally blind to internal reordering/duplication within the Send-Boundary tail
       (steps 15-19), which it never walks (see the module docstring FINDING);
    3. the egress gateway's own real, stamped send-boundary execution order
       (:func:`_gateway_projection` compared against one real run via
       :func:`_run_gateway_happy_path_steps`, reading the production
       ``GatewayEvidenceRecord.step`` field KW3-GW added) — since KW3-GW (commit 9de02dcc) this
       fully closes detector 2's 12-variant Send-Boundary blind spot; see the module docstring
       FINDING.

    ``survivors`` (the plan's exit-condition name) is defined over *exactly* these two — **not**
    over detector 1 (the ADR order-pin) as well. Detector 1 is red for every one of the 56
    variants by construction (each is a genuine tuple mutation, so it can never equal
    :data:`_ADR_002_002_SECTION_11_ORDER`), so folding it into the same OR-of-three-booleans the
    original F-K-1/2 draft used made ``survivors`` structurally empty regardless of what detectors
    2 and 3 actually caught — the assertion could never fail, which is exactly what wave-3 review
    finding 4 (LOW) flagged: the line carrying the plan's «생존 0» name was not load-bearing; the
    real gate was the separate ``order_pin_only`` comparison below it. Detector 1 is still run and
    still asserted — as ``anchor_sanity``, a *sanity check on the variant generator itself* (every
    variant must actually BE a mutation) — but it is not allowed to make the "생존 0" line vacuous.

    ``validate_stage_map`` ("detector 0") is not counted at all: it takes no order argument and
    rejects a stage map only for *which* steps it hosts, never *in what sequence* — see the module
    docstring FINDING. It passes trivially for every variant in this matrix.

    The test pins the survivor set at **empty** (:data:`_EXPECTED_ORDER_PIN_ONLY`) and the 1
    unreachable variant against hand-derived expectations, so a future change that reopens either
    execution detector's blind spot shows up as a failing ``assert not survivors`` naming the
    reopened variants, not merely a set-equality diff further down.
    """
    control = _run_variant(COMMITMENT_FLOW_ORDER)
    assert control[0] == "FLOW" and control[1] is True, (
        f"the control (unmutated order, run through the identical patch-and-execute harness) "
        f"must hand off cleanly — a failure here means the harness itself is broken, not that a "
        f"mutation was caught: {control!r}"
    )
    gateway_control = _run_gateway_happy_path_steps()
    assert gateway_control == _gateway_projection(COMMITMENT_FLOW_ORDER), (
        "the gateway's real, unmutated stamped-step sequence must match the ADR anchor's own "
        f"expanded projection onto the observable steps — gateway={gateway_control!r} "
        f"anchor_projection={_gateway_projection(COMMITMENT_FLOW_ORDER)!r} (this re-derives "
        "test_egressgw_gateway.py::test_the_baseline_send_records_the_commitment_step_"
        "sequence_exactly through this module's own expansion, as a cross-check)"
    )

    survivors: list[str] = []
    anchor_sanity_failures: list[str] = []
    unreachable: list[str] = []
    for name, order in _ALL_VARIANTS:
        order_pin_red, e2e_red, gateway_red, is_unreachable = _classify(
            name, order, control, gateway_control
        )
        if is_unreachable:
            unreachable.append(name)
        if not order_pin_red:
            anchor_sanity_failures.append(name)
        if not e2e_red and not gateway_red:
            survivors.append(name)

    assert not anchor_sanity_failures, (
        f"{len(anchor_sanity_failures)} variant(s) did not even differ from the independently-"
        "transcribed ADR anchor — the variant generator produced a non-mutation (a bug in "
        f"_adjacent_swaps/_omissions/_duplications, not a caught mutation): {anchor_sanity_failures}"
    )
    assert not survivors, (
        f"{len(survivors)}/{len(_ALL_VARIANTS)} order-mutation variants survived BOTH executable "
        f"detectors (run_commitment_flow e2e AND gateway execution order) — plan §3.2/§5 «생존 0» "
        f"requires 0: {survivors}"
    )
    assert set(survivors) == _EXPECTED_ORDER_PIN_ONLY, (
        "the survivor set (caught by neither executable detector) drifted from the expected set "
        f"— actual={sorted(survivors)} expected={sorted(_EXPECTED_ORDER_PIN_ONLY)}"
    )
    assert set(unreachable) == _EXPECTED_UNREACHABLE, (
        f"the set of variants whose derivation formula itself raises drifted — "
        f"actual={sorted(unreachable)} expected={sorted(_EXPECTED_UNREACHABLE)}"
    )
