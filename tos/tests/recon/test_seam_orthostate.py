"""MANDATED test-only seam cross-check: recon bools <-> orthostate injected flags (m2).

Design #9 §3.4 / §7 / §9.1 (v1.1 m2). recon does NOT import ``tos.orthostate`` at runtime
(the import-closure test asserts its absence from recon's package closure); this file
imports **both** packages as a **test** to lock the produced-bool seam. It asserts that
recon's produced bools have the polarity + fail-closed behavior orthostate's
``knowledge_transition_allowed`` expects of its injected ``corroboration`` /
``final_quantity_proof_where_broker_involved`` / ``freshness_lost`` flags
(``orthostate/predicates.py:502-504``):

* recon ``field_reconciled_proof_ok`` / ``is_corroborated`` + ``field_specific_release_proof_ok``
  True  <=> orthostate may take ``RECONCILING -> RECONCILED`` (corroboration ∧ FQP).
* recon ``freshness_lost`` True  <=> orthostate may take a ``* -> STALE`` transition.
* recon ``any_field_conflicted`` is the Knowledge-CONFLICTED (CPL-5) antecedent.

This test is NOT a package edge — a test-only cross-import is not counted in the
``import tos.recon`` closure (design #9 §3.4).
"""

from __future__ import annotations

from tos.orthostate import KnowledgeState, knowledge_transition_allowed
from tos.recon import (
    FieldConfidence,
    FieldConfidenceClass,
    SafetyRelevantField,
    any_field_conflicted,
    field_reconciled_proof_ok,
    field_specific_release_proof_ok,
    freshness_lost,
    is_corroborated,
)

from ._recon_strategies import (
    field_confidence,
    fresh_marker,
    observation,
    release_inputs,
    stale_marker,
)

_CAP = SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY
_C = FieldConfidenceClass


def _corroborated_scenario():
    """A capacity-releasing field: 2 independent agreeing paths, fresh, with an FQP token."""
    obs = (
        observation(field=_CAP, independence_class="A", agrees_within_tolerance=True),
        observation(field=_CAP, independence_class="B", agrees_within_tolerance=True),
    )
    conf = field_confidence(field=_CAP, confidence_class=_C.CORROBORATED)
    inputs = release_inputs(final_quantity_proof_token=True, freshness=fresh_marker())
    return obs, conf, inputs


def test_reconciled_positive_alignment() -> None:
    """recon proof True => orthostate RECONCILING->RECONCILED (corroboration ∧ FQP) allowed."""
    obs, conf, inputs = _corroborated_scenario()
    corroboration = is_corroborated(obs, fresh_marker())
    fqp = field_specific_release_proof_ok(_CAP, conf, inputs)
    assert field_reconciled_proof_ok(_CAP, conf, inputs) is True
    assert corroboration is True and fqp is True
    # Wire recon's produced bools into orthostate's injected flags.
    assert (
        knowledge_transition_allowed(
            KnowledgeState.RECONCILING,
            KnowledgeState.RECONCILED,
            corroboration=corroboration,
            final_quantity_proof_where_broker_involved=fqp,
        )
        is True
    )


def test_reconciled_single_source_fails_closed_on_both_sides() -> None:
    """recon single-source => corroboration False => orthostate denies RECONCILED (aligned)."""
    single_obs = (observation(field=_CAP),)  # one path => SINGLE_SOURCE
    conf = field_confidence(field=_CAP, confidence_class=_C.SINGLE_SOURCE)
    inputs = release_inputs()
    corroboration = is_corroborated(single_obs, fresh_marker())
    assert field_reconciled_proof_ok(_CAP, conf, inputs) is False
    assert corroboration is False
    assert (
        knowledge_transition_allowed(
            KnowledgeState.RECONCILING,
            KnowledgeState.RECONCILED,
            corroboration=corroboration,
            final_quantity_proof_where_broker_involved=True,
        )
        is False
    )


def test_reconciled_missing_fqp_fails_closed_on_both_sides() -> None:
    """recon no-FQP => release proof False => orthostate denies RECONCILED (FQP conjunct)."""
    obs, conf, _ = _corroborated_scenario()
    inputs = release_inputs(final_quantity_proof_token=None)  # no FQP
    fqp = field_specific_release_proof_ok(_CAP, conf, inputs)
    assert fqp is False
    assert (
        knowledge_transition_allowed(
            KnowledgeState.RECONCILING,
            KnowledgeState.RECONCILED,
            corroboration=is_corroborated(obs, fresh_marker()),
            final_quantity_proof_where_broker_involved=fqp,
        )
        is False
    )


def test_freshness_lost_stale_alignment() -> None:
    """recon freshness_lost True => orthostate may take CONSISTENT->STALE; fresh => denied."""
    assert freshness_lost(stale_marker()) is True
    assert (
        knowledge_transition_allowed(
            KnowledgeState.CONSISTENT,
            KnowledgeState.STALE,
            freshness_lost=freshness_lost(stale_marker()),
        )
        is True
    )
    # Both-ways: a fresh marker => freshness_lost False => orthostate denies STALE.
    assert freshness_lost(fresh_marker()) is False
    assert (
        knowledge_transition_allowed(
            KnowledgeState.CONSISTENT,
            KnowledgeState.STALE,
            freshness_lost=freshness_lost(fresh_marker()),
        )
        is False
    )


def test_none_flags_fail_closed_matches_recon_conservative_false() -> None:
    """orthostate None flags fail closed — recon's definite False is at least as safe."""
    # recon never emits None; it emits a conservative bool. The seam's None-fails-closed
    # direction means a recon False and a caller None both deny the transition.
    assert (
        knowledge_transition_allowed(
            KnowledgeState.RECONCILING,
            KnowledgeState.RECONCILED,
            corroboration=None,
            final_quantity_proof_where_broker_involved=None,
        )
        is False
    )
    assert (
        knowledge_transition_allowed(
            KnowledgeState.CONSISTENT, KnowledgeState.STALE, freshness_lost=None
        )
        is False
    )


def test_any_field_conflicted_polarity() -> None:
    """recon any_field_conflicted is the Knowledge-CONFLICTED (CPL-5) antecedent — polarity."""
    conflicted = FieldConfidence(field=_CAP, confidence_class=_C.CONFLICTED)
    corroborated = FieldConfidence(field=_CAP, confidence_class=_C.CORROBORATED)
    assert any_field_conflicted((corroborated, conflicted)) is True
    assert any_field_conflicted((corroborated,)) is False
    # The produced True is orthostate's CONFLICTED antecedent — CONSISTENT->CONFLICTED is a
    # valid arrow (no positive-proof guard), so the antecedent enables it.
    assert (
        knowledge_transition_allowed(
            KnowledgeState.CONSISTENT, KnowledgeState.CONFLICTED
        )
        is True
    )


def test_recon_produced_bools_are_plain_bool() -> None:
    """recon produces plain ``bool`` (type-matches orthostate's ``bool | None`` injected flags)."""
    obs, conf, inputs = _corroborated_scenario()
    assert isinstance(field_reconciled_proof_ok(_CAP, conf, inputs), bool)
    assert isinstance(field_specific_release_proof_ok(_CAP, conf, inputs), bool)
    assert isinstance(freshness_lost(fresh_marker()), bool)
    assert isinstance(is_corroborated(obs, fresh_marker()), bool)
    assert isinstance(any_field_conflicted((conf,)), bool)
