"""§6 substrate / not-Phase-1 boundary + the staged-EV honesty discipline.

Design #24 §1 classifies every ADR clause **core (an EV-L1 slice) / substrate (vocabulary
only, claiming no EV) / not-Phase-1 (sibling-owned or deferred runtime)**, and §6 spells out
what each deferral leaves unbuilt. This module asserts the deferrals are real — that the
package does **not** quietly contain the thing it says it deferred — and that the honesty tags
are present rather than merely intended.

What is asserted:

* **PTF-EV-003 settlement / cash availability** (``EV-L2/3+Broker``) — the six cash kinds and
  the non-substitution identity exist; the **availability proof** does not, and an L1-only
  fold therefore lands on ``POST_TRADE_TRAPPED``;
* **PTF-EV-005 borrow** (``EV-L2/3+Broker``) — the borrow dimension exists on the finality
  axis; no discharge predicate does;
* **PTF-EV-007 custody / legal title** (``EV-L2/3+Broker+Security``) — likewise;
* **PTF-EV-009 breaks** (``EV-L2/3+Broker+Security``) — the frozen record shape and the
  append-only discipline exist; no break judgment or closure does;
* **PTF-EV-010 RCL coupling / generation fencing / currentness** and **PTF-EV-011
  partition / security** — nothing at all;
* **PTF-EV-012 evidence / recovery / non-revival** (``EV-L2/3+Broker+Security``) — the frozen
  digest-bound record exists; no replay engine, recovery workflow, or re-arm does;
* the **discipline tag** is present in the package docstring and states the two required
  things: no EV-L1-complete claim, and **closing PTF-EV = 0**.
"""

from __future__ import annotations

import inspect

import pytest
import tos.posttrade as posttrade
import tos.posttrade.predicates as posttrade_predicates
import tos.posttrade.records as posttrade_records
import tos.posttrade.state as posttrade_state
import tos.posttrade.vocabulary as posttrade_vocabulary
from tos.posttrade import (
    CashKind,
    FinalityDimensionKind,
    MarginCollateralState,
    PostTradeBreakRecord,
    PostTradeDisposition,
    cash_kind_matches_requirement,
    post_trade_disposition,
)

from ._posttrade_strategies import clean_break_record, clean_disposition_kwargs

_MODULES = (
    posttrade,
    posttrade_predicates,
    posttrade_records,
    posttrade_state,
    posttrade_vocabulary,
)


def _package_has(name: str) -> bool:
    """Whether any posttrade module exposes ``name``."""
    return any(hasattr(module, name) for module in _MODULES)


# --- the 19 predicates, counted ----------------------------------------------


def test_the_package_exposes_exactly_the_nineteen_predicates() -> None:
    """(§9.1) Nineteen decision predicates, individually counted, no more and no fewer."""
    expected = {
        "finality_dimensions_orthogonal",
        "obligation_leg_set_complete",
        "obligation_commit_idempotent",
        "monetary_leg_conservative",
        "netting_requires_positive_proof",
        "missing_counterleg_is_adverse",
        "collateral_no_double_use",
        "margin_collateral_states_distinct",
        "cash_kind_matches_requirement",
        "obligation_legs_from_event_complete",
        "event_state_not_obligation_finality",
        "statement_coverage_complete",
        "statement_sources_independent",
        "absence_is_negative_evidence_only",
        "finality_proof_class_specific",
        "finality_proof_non_transferable",
        "finality_proof_current",
        "post_trade_consequence_all_false",
        "post_trade_disposition",
    }
    assert len(expected) == 19
    exported = {
        name
        for name in posttrade_predicates.__all__
        if inspect.isfunction(getattr(posttrade_predicates, name, None))
    }
    assert exported == expected


def test_every_predicate_is_pure_in_shape() -> None:
    """(§0.2) Each predicate returns a plain ``bool`` or a posttrade StrEnum — never an effect."""
    for name in sorted(
        n
        for n in posttrade_predicates.__all__
        if inspect.isfunction(getattr(posttrade_predicates, n, None))
    ):
        function = getattr(posttrade_predicates, name)
        annotation = inspect.signature(function).return_annotation
        assert annotation in (
            "bool",
            "ObligationCommitOutcome",
            "PostTradeDisposition",
        ), f"{name}() returns {annotation!r}"


# --- PTF-EV-003: settlement / cash availability (EV-L2/3+Broker) -------------


def test_cash_kind_substrate_exists_but_the_availability_proof_does_not() -> None:
    """(§6.1) The vocabulary and the non-substitution identity are L1; the proof is not."""
    assert len(list(CashKind)) == 6
    assert (
        cash_kind_matches_requirement(CashKind.SETTLED_CASH, CashKind.SETTLED_CASH)
        is True
    )
    for deferred in (
        "cash_available",
        "settlement_complete",
        "instruction_accepted",
        "prove_availability",
        "buying_power_converts",
    ):
        assert not _package_has(deferred), f"{deferred} is PTF-EV-003 EV-L2/3, not L1"


def test_an_l1_only_fold_is_trapped_not_admissible() -> None:
    """(§5.8 honest disclosure) Without an availability proof the obligation stays trapped.

    Every L1 structural property holding is not the same thing as the obligation being
    admissible — and the package says so rather than quietly admitting.
    """
    assert (
        post_trade_disposition(**clean_disposition_kwargs(availability_proven=None))
        is PostTradeDisposition.POST_TRADE_TRAPPED
    )


# --- PTF-EV-005 borrow / PTF-EV-007 custody (EV-L2/3[+Security]) -------------


def test_the_borrow_and_custody_dimensions_exist_with_no_discharge_predicate() -> None:
    """(§6.2/§6.3) The finality axis names them; no predicate proves either."""
    assert FinalityDimensionKind.BORROW_DISCHARGE in set(FinalityDimensionKind)
    assert FinalityDimensionKind.CUSTODY_TITLE in set(FinalityDimensionKind)
    for deferred in (
        "borrow_discharged",
        "recall_satisfied",
        "buy_in_complete",
        "custody_chain_complete",
        "legal_title_transferred",
    ):
        assert not _package_has(deferred), f"{deferred} is EV-L2/3, not L1"


# --- PTF-EV-009 breaks (EV-L2/3+Broker+Security) -----------------------------


def test_the_break_record_is_shape_substrate_with_no_judgment() -> None:
    """(§6.4) A frozen append-only record shape — and deliberately nothing that closes it."""
    record = clean_break_record()
    assert record.break_id == "BRK-1"
    assert "old_obligation_version" in PostTradeBreakRecord.model_fields
    assert "new_obligation_version" in PostTradeBreakRecord.model_fields
    for deferred in (
        "break_detected",
        "break_resolved",
        "close_break",
        "propagate_break",
        "recompute_from_correction",
        "restrict_on_break",
    ):
        assert not _package_has(deferred), f"{deferred} is PTF-EV-009 EV-L2/3, not L1"


# --- PTF-EV-010 / 011: coupling, fencing, partition, security ----------------


def test_no_rcl_coupling_generation_fence_or_partition_logic_exists() -> None:
    """(§6.5/§6.6) Every one of these is sibling-owned runtime, deferred entirely."""
    for deferred in (
        "safe_transition_order",
        "ordered_transfer",
        "generation_fence",
        "stale_writer_rejected",
        "partition_contained",
        "route_bypass_detected",
        "compromise_contained",
    ):
        assert not _package_has(deferred)


# --- PTF-EV-012 evidence / recovery / non-revival ----------------------------


def test_no_replay_recovery_or_re_arm_exists() -> None:
    """(§6.6 / §24 line 548) A successful replay "is not executed verification evidence"."""
    for deferred in (
        "replay",
        "replay_matches",
        "recovery_inventory_complete",
        "restore_worst_credible_union",
        "no_automatic_rearm",
        "re_arm",
        "revive",
    ):
        assert not _package_has(deferred)


# --- margin substrate ---------------------------------------------------------


def test_the_margin_state_vocabulary_is_substrate_with_no_transition_rule() -> None:
    """(§15 line 385) Eight states, no implication table, and no transition predicate.

    Whether an ``INSTRUCTION_ACKNOWLEDGEMENT`` may become ``ACCEPTED_COLLATERAL`` is a
    broker-stage question (EV-L2/3), not an L1 one.
    """
    assert len(list(MarginCollateralState)) == 8
    for deferred in (
        "margin_transition_valid",
        "advance_margin_state",
        "collateral_accepted",
        "haircut_applied",
    ):
        assert not _package_has(deferred)


# --- the honesty tags ---------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    ["Closing PTF-EV = 0", "No EV-L1-complete claim", "Phase 1, EV-L1"],
)
def test_the_package_docstring_carries_the_discipline_tag(phrase: str) -> None:
    """(§1 / §7) The tag is present in the code, not only in the design document."""
    assert posttrade.__doc__ is not None
    assert phrase in posttrade.__doc__


def test_the_docstring_names_the_five_rows_that_hold_an_l1_slice() -> None:
    """(§1) The five PTF-EV rows with an ``EV-L1`` slice — and no claim about the rest."""
    assert posttrade.__doc__ is not None
    for row in ("001", "002", "004", "006", "008"):
        assert row in posttrade.__doc__
    assert "NOT_IMPLEMENTED" in posttrade.__doc__


def test_the_docstring_disclaims_acceptance_and_live_operation() -> None:
    """(§0.2) Authoring is not acceptance; nothing here authorizes live operation."""
    assert posttrade.__doc__ is not None
    for phrase in (
        "Registration is not execution",
        "restricted-live",
        "capacity release",
    ):
        assert phrase in posttrade.__doc__


@pytest.mark.parametrize(
    "module",
    [posttrade_vocabulary, posttrade_predicates],
    ids=["vocabulary", "predicates"],
)
def test_the_module_docstrings_carry_the_discipline_tag(module: object) -> None:
    """(§1) The two decision modules carry the tag too — a reader cannot miss it."""
    assert module.__doc__ is not None
    assert (
        "Closing\nPTF-EV = 0" in module.__doc__
        or "Closing PTF-EV = 0" in module.__doc__
    )
