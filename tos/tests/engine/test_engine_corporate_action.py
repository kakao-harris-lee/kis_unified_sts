"""``EventKind.CORPORATE_ACTION`` — the handler's judgement, its structural seal, and the
``EventResult.outcome_digest`` third branch (kernel round #3 §2 결정 1/2,
``docs/plans/2026-09-12-tos-kernel-round-3-plan.md``).

Four things this file locks that nothing else does:

* **The disposition ranking actually reaches the engine**, including the positive
  ``NONTRADE_ADMISSIBLE`` conjunction — :class:`~tos.engine.records.CorporateActionPayload`
  carries the full injected-coordinate set (same shape as
  :class:`~tos_runtime.nontrade.observations.NonTradeObservation`, Phase 5 W5 plan §2 decision
  6), so a caller that honestly supplies every coordinate reaches ``NONTRADE_ADMISSIBLE`` exactly
  the way :class:`~tos_runtime.nontrade.processor.NonTradeEventProcessor` already does for the
  identical fixture shape (see ``tos/runtime/tests/nontrade/test_engine_processor_equivalence.py``
  for the cross-implementation proof).
* **The handler touches no ledger, no projection, no orthostate** (mutation M1) — an AST scan of
  both the delegate module and the dispatch method itself, with a self-test proving the scanner
  actually catches a planted violation.
* **``outcome_digest`` is real and sensitive** (mutation M2) — reproducible for the same inputs,
  different for different ones, and reachable through ``EventResult.outcome_digest``'s third
  branch.
* **The event is genuinely reachable through the dispatcher** (mutation M9) — ``core.handle(...)``
  on a ``CORPORATE_ACTION`` event returns a populated ``nontrade_outcome``, never an
  ``UnknownEventKindError``.

Regime tag: authoring evidence only; closes no EV (design #21 §1.1 / design #31 §1.1).
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from tos.engine import EventKind
from tos.engine._corporate_action import handle_corporate_action
from tos.engine.records import CorporateActionPayload
from tos.engine.vocabulary import EvidenceKind
from tos.nontrade import (
    CredibleTransitionLegKind,
    NonTradeDisposition,
    NonTradeEventRecord,
    SplitTransformationKind,
    SplitTransformationSpec,
    TransitionEnvelope,
)

from ._engine_fixtures import (
    SCHEME,
    RecordingTransmit,
    build_core,
    corporate_action_event,
    instrument_key,
)

_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"

#: A complete, positively-provable stock-split payload — the SAME shape
#: ``tests/nontrade/fixtures/synthetic_observations.py::stock_split_forward`` builds for
#: ``NonTradeEventProcessor`` (Phase 5 W5 plan §2 decision 6), so the engine handler proves it
#: can reach ``NONTRADE_ADMISSIBLE`` too, not merely the restrictive ranks.
_REQUIRED_LEGS: frozenset[CredibleTransitionLegKind] = frozenset(
    {
        CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER,
        CredibleTransitionLegKind.POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH,
        CredibleTransitionLegKind.FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU,
    }
)


def _admissible_payload(**overrides):
    envelope = overrides.pop(
        "envelope",
        TransitionEnvelope(
            present_legs=tuple(sorted(_REQUIRED_LEGS, key=lambda leg: leg.value)),
            pre_event_exposure=Decimal("2000"),
            post_event_credible_exposure=Decimal("2000"),
        ),
    )
    split_spec = overrides.pop(
        "split_spec",
        SplitTransformationSpec(
            kind=SplitTransformationKind.FORWARD_SPLIT,
            pre_quantity=Decimal("100"),
            post_quantity=Decimal("200"),
            pre_basis=Decimal("20"),
            post_basis=Decimal("10"),
            unit_spec="shares",
            rounding_rule="round-down",
            fractional_residual=Decimal("0"),
            cash_in_lieu=Decimal("0"),
        ),
    )
    base: dict = {
        "instrument_key": instrument_key(),
        "event": NonTradeEventRecord(
            old_instrument_identity="KRX:005930",
            new_instrument_identity="KRX:005930",
        ),
        "envelope": envelope,
        "split_spec": split_spec,
        "required_legs": _REQUIRED_LEGS,
        "identity_transition_final": True,
        "event_is_material": True,
        "change_triggers": frozenset({"instrument:KRX:005930"}),
        "earliest_credible_boundary": "2026-09-10T00:00:00",
        "latest_completion_boundary": "2026-09-12T00:00:00",
        "source_disagreement_bounded": True,
        "field_confidences": frozenset({"CORROBORATED"}),
        "venue_admissibility": "ADMISSIBLE",
        "time_freshness": "FRESH",
        "injected_worst_intermediate_risk": Decimal("5"),
        "injected_credible_space_bounded": True,
        "injected_union_capacity_known": True,
    }
    base.update(overrides)
    return CorporateActionPayload(**base)


def _outcome(**overrides):
    overrides.setdefault("event", NonTradeEventRecord())
    payload = CorporateActionPayload(instrument_key=instrument_key(), **overrides)
    return handle_corporate_action(payload, scheme=SCHEME)


# ===========================================================================
# disposition ranking, including the positive NONTRADE_ADMISSIBLE conjunction
# ===========================================================================


def test_a_complete_payload_reaches_admissible() -> None:
    """(design #21 §5.5 rank 5) Every conjunct positively proven -> NONTRADE_ADMISSIBLE, exactly
    like NonTradeEventProcessor.process(stock_split_forward()) reaches it (see the equivalence
    test in tos/runtime/tests/nontrade/)."""
    outcome = handle_corporate_action(_admissible_payload(), scheme=SCHEME)
    assert outcome.disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE
    assert outcome.restrictive is False
    assert outcome.capacity_remap_proposal is not None
    assert outcome.capacity_remap_proposal.value == "RECOGNIZED_EXTERNAL_CHANGE"


def test_reversed_split_polarity_falls_to_block_new_risk() -> None:
    """A mis-declared split direction fails ``split_polarity_coherent`` — everything else stays
    proven, so this isolates that ONE conjunct's own failure mode."""
    bad_split = SplitTransformationSpec(
        kind=SplitTransformationKind.FORWARD_SPLIT,
        pre_quantity=Decimal("200"),
        post_quantity=Decimal("100"),
        pre_basis=Decimal("20"),
        post_basis=Decimal("10"),
        unit_spec="shares",
        rounding_rule="round-down",
        fractional_residual=Decimal("0"),
        cash_in_lieu=Decimal("0"),
    )
    outcome = handle_corporate_action(
        _admissible_payload(split_spec=bad_split), scheme=SCHEME
    )
    assert outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    assert outcome.predicate_results["polarity_coherent"] is False
    assert outcome.capacity_remap_proposal is None


def test_conflicted_field_confidence_ranks_first() -> None:
    """(design #21 §5.5 rank 1) A CONFLICTED field confidence wins over everything else, even a
    payload that is otherwise a complete admissible one."""
    outcome = handle_corporate_action(
        _admissible_payload(field_confidences=frozenset({"CONFLICTED"})), scheme=SCHEME
    )
    assert outcome.disposition is NonTradeDisposition.NONTRADE_CONFLICTED
    assert outcome.restrictive is True
    assert outcome.capacity_remap_proposal is None


def test_unknown_field_confidence_ranks_second() -> None:
    """(rank 2) An UNKNOWN field confidence is quarantined, not conflicted, not trapped."""
    outcome = handle_corporate_action(
        _admissible_payload(field_confidences=frozenset({"UNKNOWN"})), scheme=SCHEME
    )
    assert outcome.disposition is NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN
    assert outcome.restrictive is True


def test_no_admissibility_is_trapped() -> None:
    """(rank 3, unconditional) No venue admissibility token at all is trapped, never zero risk —
    even when every OTHER conjunct is positively proven."""
    outcome = handle_corporate_action(
        _admissible_payload(venue_admissibility=None), scheme=SCHEME
    )
    assert outcome.disposition is NonTradeDisposition.NONTRADE_TRAPPED
    assert outcome.restrictive is True
    assert outcome.capacity_remap_proposal is None


def test_inadmissible_venue_token_is_trapped() -> None:
    outcome = handle_corporate_action(
        _admissible_payload(venue_admissibility="INADMISSIBLE"), scheme=SCHEME
    )
    assert outcome.disposition is NonTradeDisposition.NONTRADE_TRAPPED


def test_the_minimal_empty_payload_is_trapped() -> None:
    """No coordinates at all (the default-constructed payload) — no admissibility token, so rank
    3 fires unconditionally, regardless of every other axis being honestly absent too.
    """
    outcome = _outcome()
    assert outcome.disposition is NonTradeDisposition.NONTRADE_TRAPPED
    assert outcome.restrictive is True
    assert outcome.capacity_remap_proposal is None


def test_capacity_remap_proposal_requires_both_admissible_and_an_envelope() -> None:
    """(ADR-002-010 §10 line 217) A proposal, never a grant — and only offered when there is an
    envelope to remap capacity over, even if the disposition is otherwise ADMISSIBLE-eligible.
    """
    outcome = handle_corporate_action(
        _admissible_payload(envelope=None, split_spec=None, required_legs=frozenset()),
        scheme=SCHEME,
    )
    # No envelope/split at all -> envelope_complete is False (∅ structural guard), so this
    # actually lands at BLOCK_NEW_RISK, not ADMISSIBLE -- confirms the envelope conjunct is
    # itself load-bearing, not just the remap-proposal gate.
    assert outcome.disposition is not NonTradeDisposition.NONTRADE_ADMISSIBLE
    assert outcome.capacity_remap_proposal is None


def test_unevaluated_names_the_skipped_predicates_for_this_payload() -> None:
    """Mirrors NonTradeEventProcessor's own conditional-evaluation bookkeeping: the
    transformation triad and correction idempotency are each named unevaluated only when their
    OWN artifact (split_spec / correction) is absent from this exact payload — never a fixed,
    payload-independent list."""
    minimal = _outcome()
    assert set(minimal.unevaluated) == {
        "split_polarity_coherent",
        "transformation_units_and_rounding_explicit",
        "transformation_residual_conservative",
        "correction_reversal_idempotent",
    }
    complete = handle_corporate_action(_admissible_payload(), scheme=SCHEME)
    assert "split_polarity_coherent" not in complete.unevaluated
    assert (
        "correction_reversal_idempotent" in complete.unevaluated
    )  # no correction in the fixture


# ===========================================================================
# outcome_digest — real and sensitive (mutation M2)
# ===========================================================================


def test_outcome_digest_is_reproducible_for_the_same_input() -> None:
    a = handle_corporate_action(_admissible_payload(), scheme=SCHEME)
    b = handle_corporate_action(_admissible_payload(), scheme=SCHEME)
    assert a.outcome_digest == b.outcome_digest
    assert a.disposition == b.disposition


def test_outcome_digest_changes_with_a_different_disposition() -> None:
    a = handle_corporate_action(_admissible_payload(), scheme=SCHEME)
    b = handle_corporate_action(
        _admissible_payload(venue_admissibility="INADMISSIBLE"), scheme=SCHEME
    )
    assert a.disposition is not b.disposition
    assert a.outcome_digest != b.outcome_digest


def test_the_core_reaches_a_populated_nontrade_outcome() -> None:
    """(mutation M9) The event is genuinely dispatched — never an UnknownEventKindError, and
    ``EventResult.outcome_digest`` reads the third branch."""
    core, sink = build_core(transmit=RecordingTransmit())
    result = core.handle(corporate_action_event(sequence=1))
    assert result.kind is EventKind.CORPORATE_ACTION
    assert result.nontrade_outcome is not None
    assert result.outcome_digest == result.nontrade_outcome.outcome_digest

    (record,) = [
        entry
        for entry in sink.records
        if entry.kind is EvidenceKind.CORPORATE_ACTION_CONSUMED
    ]
    assert record.nontrade_disposition == result.nontrade_outcome.disposition.value
    assert record.outcome_digest == result.nontrade_outcome.outcome_digest


# ===========================================================================
# structural seal — no ledger / projection / orthostate mutation (mutation M1)
# ===========================================================================

#: Method/attribute-call names that would indicate the handler reached into the ledger,
#: projection, or orthostate — none of these may appear anywhere in the delegate module or the
#: dispatch method's own source (kernel round #3 §2 결정 2(d)).
_FORBIDDEN_CALL_NAMES = frozenset(
    {
        "commit_unbound",
        "bind_attempt",
        "mark_potentially_live",
        "apply_egress_result",
        "release",  # ProvisionalReservationLedger.release (kernel round #3 §2 결정 5)
        "record_new_risk_halt",
        "clear_new_risk_halt",
    }
)


def _call_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def test_the_corporate_action_delegate_module_touches_no_ledger_or_orthostate() -> None:
    path = _SRC / "_corporate_action.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = _call_names(tree) & _FORBIDDEN_CALL_NAMES
    assert offenders == set(), (
        f"engine/_corporate_action.py calls forbidden ledger/orthostate methods: {offenders} — "
        "the CORPORATE_ACTION handler judges and proposes only (ADR-002-010 §10 line 217)"
    )


def test_the_dispatch_method_itself_touches_no_ledger_or_orthostate() -> None:
    """Scans ONLY ``EngineCore._handle_corporate_action``'s own function body in ``core.py`` —
    not the whole file, which legitimately calls ledger methods from ``_handle_egress_result``.
    """
    path = _SRC / "core.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    method = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_handle_corporate_action"
        ):
            method = node
            break
    assert (
        method is not None
    ), "EngineCore._handle_corporate_action not found in core.py"
    offenders = _call_names(method) & _FORBIDDEN_CALL_NAMES
    assert (
        offenders == set()
    ), f"_handle_corporate_action calls forbidden ledger/orthostate methods: {offenders}"


def test_the_structural_scan_actually_catches_a_planted_violation(tmp_path) -> None:
    """Synthetic-string self-test (anti-vacuity): prove the scanner really would have caught a
    handler that reached into the ledger, by planting one in isolation."""
    planted = tmp_path / "planted_handler.py"
    planted.write_text(
        "def _handle_corporate_action(self, event, admission):\n"
        "    self._ledger.commit_unbound(key, proposal_id=None)\n"
        "    return None\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename=str(planted))
    offenders = _call_names(tree) & _FORBIDDEN_CALL_NAMES
    assert offenders == {
        "commit_unbound"
    }, "the scanner failed to catch a planted ledger call"
