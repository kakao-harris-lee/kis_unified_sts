"""Tests for :mod:`tos_runtime.nontrade.processor` (Phase 5 W5 plan §2 decision
6, lane f3): the four synthetic fixtures' dispositions, the split-polarity and
envelope-completeness conservative mutations, correction/reversal idempotency,
the LIFECYCLE restrictive+latch_reason path, evidence-append-once, the
unevaluated-predicate bookkeeping, the M7-prep non-constant-restrictive proof,
and the package's own no-write structural pin.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tos.nontrade import NonTradeDisposition, NonTradeEventClass
from tos_runtime.nontrade import NonTradeEventProcessor

from .conftest import FakeEvidenceRecorder
from .fixtures.synthetic_observations import (
    cash_dividend,
    cash_dividend_missing_leg,
    correction_pair,
    futures_lifecycle_expiry,
    stock_split_forward,
    symbol_route_change,
)

_NONTRADE_SRC_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "tos_runtime" / "nontrade"
)


def _processor(
    required_legs_by_class,
    *,
    admissible_provider=None,
    fresh_time_provider=None,
    dep_graph_provider=None,
) -> tuple[NonTradeEventProcessor, FakeEvidenceRecorder]:
    recorder = FakeEvidenceRecorder()
    processor = NonTradeEventProcessor(
        recorder,
        required_legs_by_class,
        dep_graph_provider=dep_graph_provider,
        venue_admissibility_provider=admissible_provider,
        time_freshness_provider=fresh_time_provider,
    )
    return processor, recorder


# ============================================================================
# (1) each of the four synthetic fixtures -> disposition + predicate table
# ============================================================================


def test_stock_split_forward_reaches_admissible(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    outcome = processor.process(stock_split_forward())
    assert outcome.disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE
    assert outcome.restrictive is False
    assert outcome.latch_reason is None
    assert outcome.predicate_results["split_polarity_coherent"] is True
    assert outcome.predicate_results["transition_envelope_complete"] is True
    assert recorder.kinds() == ["NONTRADE_DISPOSITION"]


def test_cash_dividend_reaches_block_new_risk_on_empty_triggers(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, _recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    outcome = processor.process(cash_dividend())
    assert outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    assert outcome.restrictive is True
    assert outcome.predicate_results["material_change_trigger_nonempty"] is False
    # the split triad is genuinely not applicable here (no split_spec) — never a
    # fabricated False
    assert outcome.predicate_results["split_polarity_coherent"] is None


def test_symbol_route_change_reaches_block_new_risk(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, _recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    outcome = processor.process(symbol_route_change())
    assert outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    assert outcome.restrictive is True
    # lineage itself is preserved (both routes present, admissible token) even
    # though the overall disposition is conservative for the envelope reason
    assert outcome.predicate_results["instrument_lineage_preserved"] is True


def test_lifecycle_expiry_reaches_trapped_with_latch_reason(
    required_legs_by_class, fresh_time_provider
) -> None:
    """(5) The rollover observation, with NO venue-admissibility provider wired
    (honestly reflecting "no fresh exact decision" — plan §2 decision 7): rank 3
    of :func:`~tos.nontrade.predicates.nontrade_disposition` is unconditional, so
    this lands at ``NONTRADE_TRAPPED``, restrictive, with a latch_reason."""
    processor, _recorder = _processor(
        required_legs_by_class, fresh_time_provider=fresh_time_provider
    )
    outcome = processor.process(futures_lifecycle_expiry())
    assert outcome.disposition is NonTradeDisposition.NONTRADE_TRAPPED
    assert outcome.restrictive is True
    assert outcome.latch_reason == "NONTRADE_TRAPPED"


# ============================================================================
# (2) the split fixture with reversed quantities -> polarity False -> conservative
# ============================================================================


def test_reversed_split_quantities_break_polarity_coherence(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, _recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    outcome = processor.process(stock_split_forward(reversed_quantities=True))
    assert outcome.predicate_results["split_polarity_coherent"] is False
    assert outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    assert outcome.restrictive is True


# ============================================================================
# (3) envelope missing a required leg -> not complete -> conservative
# ============================================================================


def test_envelope_missing_a_required_leg_is_not_complete(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, _recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    complete_outcome = processor.process(cash_dividend())
    incomplete_outcome = processor.process(cash_dividend_missing_leg())
    assert complete_outcome.predicate_results["transition_envelope_complete"] is True
    assert incomplete_outcome.predicate_results["transition_envelope_complete"] is False
    assert incomplete_outcome.disposition is NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK
    assert incomplete_outcome.restrictive is True


# ============================================================================
# (4) correction / reversal pair -> idempotent outcome
# ============================================================================


def test_correction_then_replay_is_applied_once_then_idempotent(
    required_legs_by_class,
) -> None:
    processor, _recorder = _processor(required_legs_by_class)
    first, replay = correction_pair()
    first_outcome = processor.process(first)
    replay_outcome = processor.process(replay)
    assert first_outcome.predicate_results["correction_reversal_idempotent"] == (
        "APPLIED_ONCE"
    )
    assert replay_outcome.predicate_results["correction_reversal_idempotent"] == (
        "IDEMPOTENT_REPLAY"
    )
    assert "correction_reversal_idempotent" not in first_outcome.unevaluated
    assert "correction_reversal_idempotent" not in replay_outcome.unevaluated


# ============================================================================
# (6) evidence appended once per process()
# ============================================================================


def test_disposition_evidence_appended_exactly_once_per_process_call(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    processor.process(stock_split_forward())
    disposition_appends = [
        kind for kind in recorder.kinds() if kind == "NONTRADE_DISPOSITION"
    ]
    assert len(disposition_appends) == 1


def test_material_change_evidence_only_appended_when_dep_graph_provided(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor_without_graph, recorder_without_graph = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    outcome_without_graph = processor_without_graph.process(symbol_route_change())
    assert "NONTRADE_MATERIAL_CHANGE" not in recorder_without_graph.kinds()
    assert outcome_without_graph.material_change_closure is None

    dep_graph = {"instrument:KRX:005930": frozenset({"decision:KRX:005930:001"})}
    processor_with_graph, recorder_with_graph = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
        dep_graph_provider=lambda: dep_graph,
    )
    outcome_with_graph = processor_with_graph.process(symbol_route_change())
    assert recorder_with_graph.kinds().count("NONTRADE_MATERIAL_CHANGE") == 1
    assert outcome_with_graph.material_change_closure is not None
    assert "decision:KRX:005930:001" in outcome_with_graph.material_change_closure


# ============================================================================
# (7) unevaluated names exactly the predicates whose inputs were None
# ============================================================================


def test_unevaluated_names_exactly_the_skipped_predicates(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    processor, _recorder = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    # stock_split_forward carries a split_spec but no correction, and its event
    # class HAS a required_legs_by_class entry — only the correction predicate
    # should be unevaluated.
    outcome = processor.process(stock_split_forward())
    assert outcome.unevaluated == ("correction_reversal_idempotent",)

    # futures_lifecycle_expiry carries neither an envelope-config entry for its
    # class, nor a split_spec, nor a correction — all four skip.
    lifecycle_outcome = processor.process(futures_lifecycle_expiry())
    assert set(lifecycle_outcome.unevaluated) == {
        "transition_envelope_complete",
        "split_polarity_coherent",
        "transformation_units_and_rounding_explicit",
        "transformation_residual_conservative",
        "correction_reversal_idempotent",
    }
    # predicates that ARE always evaluated (never appear here even with all-None
    # observation inputs) still produced a concrete (non-None) result:
    always_evaluated = (
        "favorable_netting_absent",
        "instrument_lineage_preserved",
        "effective_window_blocks_new_risk",
        "material_change_trigger_nonempty",
        "nontrade_authority_effect_all_false",
    )
    for name in always_evaluated:
        assert name not in lifecycle_outcome.unevaluated
        assert lifecycle_outcome.predicate_results[name] is not None


# ============================================================================
# (8) M7-prep: restrictive is not a hardcoded constant
# ============================================================================


def test_restrictive_is_not_a_constant_across_fixtures(
    required_legs_by_class, admissible_provider, fresh_time_provider
) -> None:
    admissible_processor, _r = _processor(
        required_legs_by_class,
        admissible_provider=admissible_provider,
        fresh_time_provider=fresh_time_provider,
    )
    not_restrictive = admissible_processor.process(stock_split_forward())
    trapped_processor, _r2 = _processor(
        required_legs_by_class, fresh_time_provider=fresh_time_provider
    )
    restrictive = trapped_processor.process(futures_lifecycle_expiry())
    assert not_restrictive.restrictive is False
    assert restrictive.restrictive is True
    assert not_restrictive.restrictive != restrictive.restrictive


# ============================================================================
# (9) no-write structural pin: nontrade/ never reserves, commits, releases,
# remaps, or writes capacity/composite state (rcl is the sole authority).
# Mirrors tests/operator/test_no_write_port.py's two-part idiom.
# ============================================================================

_FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "tos_runtime.rcl",
    "tos_runtime.engine",
    "tos_runtime.recovery",
    "tos_runtime.transport",
)

_WRITE_RECEIVER = re.compile(r"[\w.]*\.(reserve|commit|release|remap|write)\(")


def _nontrade_python_files() -> list[Path]:
    return sorted(
        path
        for path in _NONTRADE_SRC_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _is_forbidden_module(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in _FORBIDDEN_IMPORT_PREFIXES
    )


def test_nontrade_package_has_python_files_to_scan() -> None:
    files = _nontrade_python_files()
    assert files, f"expected .py files under {_NONTRADE_SRC_ROOT}"


def test_no_forbidden_capacity_or_engine_imports_under_nontrade() -> None:
    offenders: list[str] = []
    for path in _nontrade_python_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_module(alias.name):
                        offenders.append(f"{path}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _is_forbidden_module(module):
                    offenders.append(f"{path}:{node.lineno}: from {module} import ...")
    assert not offenders, (
        "tos_runtime.nontrade must never import tos_runtime.rcl / .engine / "
        ".recovery / .transport (Phase 5 W5 plan §2 decision 6 — nontrade "
        "applies nothing, rcl is the sole capacity authority); offenders:\n"
        + "\n".join(offenders)
    )


def test_no_capacity_write_receiver_call_shapes_under_nontrade() -> None:
    offenders: list[str] = []
    for path in _nontrade_python_files():
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if _WRITE_RECEIVER.search(line):
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, (
        "tos_runtime.nontrade must hold zero capacity-write receiver shapes; "
        "offending call shapes:\n" + "\n".join(offenders)
    )


def test_the_receiver_shape_regex_catches_every_real_write_shape() -> None:
    should_match = (
        "rcl_log.reserve(scope)",
        "rcl_log.commit(entry)",
        "self._ledger.release(scope)",
        "capacity.remap(cause)",
        "store.write(payload)",
    )
    should_not_match = (
        "# never call reserve() here",
        "def reserve(self, scope):",
        "text about how remap works, not a call",
        "self._evidence.append(payload, kind=kind, record_class=record_class)",
    )
    for line in should_match:
        assert _WRITE_RECEIVER.search(line), f"expected the regex to match: {line!r}"
    for line in should_not_match:
        assert not _WRITE_RECEIVER.search(
            line
        ), f"expected the regex NOT to match: {line!r}"


def test_stock_split_and_cash_dividend_event_classes_are_distinct() -> None:
    """Sanity: the fixtures span more than one ``NonTradeEventClass`` (a cheap
    guard against an accidental fixture typo collapsing coverage)."""
    assert stock_split_forward().event_class is NonTradeEventClass.CORPORATE_ACTION
    assert (
        symbol_route_change().event_class is NonTradeEventClass.INSTRUMENT_TRADABILITY
    )
    assert futures_lifecycle_expiry().event_class is NonTradeEventClass.LIFECYCLE
