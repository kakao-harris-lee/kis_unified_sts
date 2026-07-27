"""Malformed-model self-defence — positive-claim + incomplete coexistence seal (design #26 §2.3 / #20).

Three artifacts carry a construction-time coexistence seal that makes a positive claim coexisting with
an incomplete / boundary-hitting shape **unconstructable** on the normal path; the ``model_construct``
escape hatch that skips validators is re-caught by the §5 predicate layer (defence in depth, 2 layers).

Regime tag: malformed-model substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.wdr as w

from ._wdr_strategies import clean_scope, construct_request

WS = w.WaivedEvidenceStatus


# --- layer 1: construction-time coexistence seal (normal path unconstructable) ---


def test_eligible_request_with_boundary_hit_unconstructable() -> None:
    """(§2.3) WAIVABLE_ELIGIBLE + a §8 boundary hit ⇒ ArtifactIntegrityError at construction."""
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.SafetyDeviationRequest.issue(
            scheme=_scheme(),
            request_id="r",
            request_version=1,
            request_digest="d",
            policy_id="p",
            policy_generation=1,
            deviation_scope=clean_scope(),
            non_waivable_classification=w.NonWaivableClassification.WAIVABLE_ELIGIBLE,
            applicability_resolved=True,
            boundary_hits=frozenset({"rfc_000_constitutional"}),
        )


def test_eligible_request_with_blank_scope_unconstructable() -> None:
    """(§2.3) WAIVABLE_ELIGIBLE + an incomplete scope ⇒ ArtifactIntegrityError at construction."""
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.SafetyDeviationRequest.issue(
            scheme=_scheme(),
            request_id="r",
            request_version=1,
            request_digest="d",
            policy_id="p",
            policy_generation=1,
            deviation_scope=clean_scope(account=None),
            non_waivable_classification=w.NonWaivableClassification.WAIVABLE_ELIGIBLE,
            applicability_resolved=True,
        )


def test_eligible_decision_with_blank_scope_unconstructable() -> None:
    """(§2.3) ELIGIBLE decision + an incomplete reduced scope ⇒ ArtifactIntegrityError."""
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.SafetyDeviationDecision.issue(
            scheme=_scheme(),
            decision_id="dec",
            decision_generation=1,
            request_id="r",
            request_digest="d",
            deviation_generation=5,
            reduced_scope=clean_scope(venue=None),
            result=w.DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION,
        )


def test_accepted_acceptance_without_compensation_unconstructable() -> None:
    """(§2.3/§11) WAIVED_WITH_RESIDUAL_RISK acceptance with no compensating control ⇒ error."""
    with pytest.raises((w.ArtifactIntegrityError, ValueError)):
        w.ResidualRiskAcceptanceRecord.issue(
            scheme=_scheme(),
            acceptance_id="acc",
            acceptance_generation=1,
            request_id="r",
            evidence_status=WS.WAIVED_WITH_RESIDUAL_RISK,
            explicit_scope=clean_scope(),
            compensating_controls=(),
        )


# --- layer 2: model_construct bypass re-caught by the predicate (defence in depth) ---


def test_model_construct_boundary_hit_recaught_by_predicate() -> None:
    """(§2.3 defence in depth) A model_construct'd eligible+boundary-hit request is denied by the yolk."""
    from ._wdr_strategies import clean_boundary

    malformed = construct_request(boundary_hits=frozenset({"rcl_exclusivity"}))
    assert w.boundary_denies_non_waivable(malformed, clean_boundary()) is False


def test_model_construct_blank_scope_recaught_by_predicate() -> None:
    """(§2.3 defence in depth) A model_construct'd eligible+blank-scope request is denied by the yolk."""
    malformed = construct_request(deviation_scope=clean_scope(account=None))
    assert w.scope_exact_and_complete(malformed, w.MANDATED_SCOPE_FLOOR) is False


def _scheme():
    """The injected provisional canonicalizer (REUSE)."""
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

    return get_scheme(EV_L1_PROVISIONAL_VERSION)
