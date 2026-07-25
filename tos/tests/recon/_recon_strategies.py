"""Shared valid-artifact builders + strategies for the recon property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #9 §0.3). The
``issue_*`` / ``*_required_kwargs`` builders populate every safety-load-bearing covered
field the assessment issuance guard demands, so a "valid" fixture is genuinely valid
(never the all-null coverage illusion). ``fresh_marker`` is the positive (all-proof, same
generation) freshness side; ``stale_marker`` is aged. The reserved ``"TBD"`` placeholder
is excluded from required-field text (a past flaky-test lesson).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.recon import (
    CAPACITY_RELEASING_FIELDS,
    ConservativeBound,
    EvidencePathObservation,
    FieldConfidence,
    FieldConfidenceClass,
    FieldReconciliationAssessment,
    FreshnessMarker,
    ReleaseProofInputs,
    SafetyRelevantField,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``
#: placeholder the issuance guard rejects — design #9 §2.3/§3.2).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")

# ---------------------------------------------------------------------------
# Enum / scalar strategies
# ---------------------------------------------------------------------------

FIELDS = st.sampled_from(list(SafetyRelevantField))
CLASSES = st.sampled_from(list(FieldConfidenceClass))
CAPACITY_RELEASING = st.sampled_from(sorted(CAPACITY_RELEASING_FIELDS))
#: The non-capacity-releasing fields (no release proof possible — design #9 §6.2).
NON_RELEASING = st.sampled_from(
    [f for f in SafetyRelevantField if f not in CAPACITY_RELEASING_FIELDS]
)
#: A magnitude over non-negative Decimals (no float; §0.3).
MAGNITUDE = st.integers(min_value=0, max_value=1000).map(Decimal)
OPT_MAGNITUDE = st.none() | MAGNITUDE
#: Injected bool | None flag (fail-closed on None / False).
TRIBOOL = st.sampled_from([True, False, None])
#: A small pool of independence-class labels (+ None for the fail-closed direction).
INDEPENDENCE = st.sampled_from(["A", "B", "C", None])


# ---------------------------------------------------------------------------
# ConservativeBound
# ---------------------------------------------------------------------------


@st.composite
def bounds(draw: st.DrawFn) -> ConservativeBound:
    """A well-formed conservative bound (lower <= upper when both present)."""
    lo = draw(OPT_MAGNITUDE)
    hi = draw(OPT_MAGNITUDE)
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return ConservativeBound(lower=lo, upper=hi)


# ---------------------------------------------------------------------------
# FreshnessMarker
# ---------------------------------------------------------------------------


def fresh_marker(**overrides: Any) -> FreshnessMarker:
    """A definitely-fresh marker (in-horizon, time held, same generation)."""
    base: dict[str, Any] = {
        "fresh_within_horizon": True,
        "time_confidence_held": True,
        "time_generation": 1,
        "anchored_generation": 1,
    }
    base.update(overrides)
    return FreshnessMarker(**base)


def stale_marker(**overrides: Any) -> FreshnessMarker:
    """An aged marker (past horizon; time held; same generation) — STALE, not time-lost."""
    return fresh_marker(fresh_within_horizon=False, **overrides)


@st.composite
def markers(draw: st.DrawFn) -> FreshnessMarker:
    """An arbitrary freshness marker over the injected flag space."""
    return FreshnessMarker(
        fresh_within_horizon=draw(TRIBOOL),
        time_confidence_held=draw(TRIBOOL),
        time_generation=draw(st.none() | st.integers(min_value=0, max_value=5)),
        anchored_generation=draw(st.none() | st.integers(min_value=0, max_value=5)),
    )


# ---------------------------------------------------------------------------
# EvidencePathObservation
# ---------------------------------------------------------------------------


def observation(**overrides: Any) -> EvidencePathObservation:
    """A single evidence-path observation with sensible positive defaults."""
    base: dict[str, Any] = {
        "field": SafetyRelevantField.ORDER_EXISTENCE,
        "independence_class": "A",
        "agrees_within_tolerance": True,
        "asserted_bound": ConservativeBound(),
        "is_absence": False,
        "freshness_marker": fresh_marker(),
    }
    base.update(overrides)
    return EvidencePathObservation(**base)


@st.composite
def observations(draw: st.DrawFn) -> EvidencePathObservation:
    """A hypothesis strategy over arbitrary constructible observations."""
    return EvidencePathObservation(
        field=draw(FIELDS),
        source_ref=draw(st.none() | REQUIRED_FIELD_TEXT),
        independence_class=draw(INDEPENDENCE),
        agrees_within_tolerance=draw(TRIBOOL),
        asserted_bound=draw(bounds()),
        is_absence=draw(st.booleans()),
        freshness_marker=draw(markers()),
    )


# ---------------------------------------------------------------------------
# FieldConfidence
# ---------------------------------------------------------------------------


def field_confidence(**overrides: Any) -> FieldConfidence:
    """A per-field confidence value with positive defaults."""
    base: dict[str, Any] = {
        "field": SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
        "confidence_class": FieldConfidenceClass.CORROBORATED,
        "bound": ConservativeBound(),
        "contributing_path_refs": (),
        "freshness_marker": fresh_marker(),
    }
    base.update(overrides)
    return FieldConfidence(**base)


@st.composite
def field_confidences(draw: st.DrawFn) -> FieldConfidence:
    """A hypothesis strategy over arbitrary constructible field confidences."""
    return FieldConfidence(
        field=draw(FIELDS),
        confidence_class=draw(st.none() | CLASSES),
        bound=draw(bounds()),
        freshness_marker=draw(markers()),
    )


# ---------------------------------------------------------------------------
# ReleaseProofInputs
# ---------------------------------------------------------------------------


def release_inputs(**overrides: Any) -> ReleaseProofInputs:
    """Release-proof inputs with the positive (FQP present, fresh) defaults."""
    base: dict[str, Any] = {
        "final_quantity_proof_token": True,
        "freshness": fresh_marker(),
    }
    base.update(overrides)
    return ReleaseProofInputs(**base)


# ---------------------------------------------------------------------------
# FieldReconciliationAssessment
# ---------------------------------------------------------------------------


def assessment_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Assessment issuance kwargs with every required covered field concrete."""
    base: dict[str, Any] = {
        "assessment_id": "asmt-1",
        "scope_ref": "scope-1",
        "state_model_version": "smv-1",
    }
    base.update(overrides)
    return base


def issue_assessment(**overrides: Any) -> FieldReconciliationAssessment:
    """Issue a valid :class:`FieldReconciliationAssessment`."""
    return FieldReconciliationAssessment.issue(
        scheme=SCHEME, **assessment_required_kwargs(**overrides)
    )
