"""No-blended-release is a STRUCTURAL invariant (design #9 §4.1; ADR §1/§5/§11).

The central safety property realized as *impossibility of construction*, not narrative:
there is **no** numeric confidence-score type or field anywhere in ``tos.recon``, and no
averaging / midpoint / blend / weight function on the public surface. Confidence is
exactly a :class:`FieldConfidenceClass` + a :class:`ConservativeBound` (a Decimal
lower/upper pair). Isomorphic to the orthostate no-normalize module-reflection canary.
"""

from __future__ import annotations

import inspect
from typing import get_args

import pydantic
import tos.recon as recon
from tos.recon import (
    ConservativeBound,
    EvidencePathObservation,
    FieldConfidence,
    FieldReconciliationAssessment,
    FreshnessMarker,
    ReleaseProofInputs,
)
from tos.recon import predicates as recon_predicates
from tos.recon import records as recon_records
from tos.recon import state as recon_state
from tos.recon import vocabulary as recon_vocabulary

#: Substrings whose appearance in a public name would signal a blended / averaged /
#: point-estimate confidence path (design #9 §4.1). ``mean`` is matched as a whole-ish
#: token to avoid false hits.
_FORBIDDEN_NAME_TOKENS = (
    "score",
    "average",
    "midpoint",
    "blend",
    "weight",
    "aggregate_confidence",
)

_RECON_MODELS = [
    ConservativeBound,
    FreshnessMarker,
    FieldConfidence,
    FieldReconciliationAssessment,
    EvidencePathObservation,
    ReleaseProofInputs,
]

_RECON_MODULES = [
    recon,
    recon_predicates,
    recon_records,
    recon_state,
    recon_vocabulary,
]


def _referenced_types(annotation: object) -> set[object]:
    """Flatten a type annotation to the set of all types it references."""
    seen: set[object] = set()
    stack = [annotation]
    while stack:
        current = stack.pop()
        seen.add(current)
        stack.extend(get_args(current))
    return seen


def test_no_float_field_anywhere() -> None:
    """No recon model carries a ``float`` field — confidence is enum + Decimal bound only."""
    for model in _RECON_MODELS:
        for name, field in model.model_fields.items():
            referenced = _referenced_types(field.annotation)
            assert float not in referenced, f"{model.__name__}.{name} references float"


def test_conservative_bound_has_only_lower_upper() -> None:
    """A ConservativeBound is exactly a lower/upper pair — no midpoint / point / score field."""
    assert set(ConservativeBound.model_fields) == {"lower", "upper"}


def test_field_confidence_has_no_numeric_score_field() -> None:
    """FieldConfidence carries a class + bound + refs + marker — never a numeric score."""
    fields = set(FieldConfidence.model_fields)
    assert fields == {
        "field",
        "confidence_class",
        "bound",
        "contributing_path_refs",
        "freshness_marker",
    }


def test_no_forbidden_name_on_public_surface() -> None:
    """No public callable / attribute name suggests an averaging / blended-score path."""
    offenders: list[str] = []
    for module in _RECON_MODULES:
        for name in dir(module):
            if name.startswith("_"):
                continue
            lowered = name.lower()
            for token in _FORBIDDEN_NAME_TOKENS:
                if token in lowered:
                    offenders.append(f"{module.__name__}.{name}")
    assert (
        offenders == []
    ), f"forbidden blended-score names on public surface: {offenders}"


def test_no_public_function_returns_float() -> None:
    """No public recon function is annotated to return a float (no numeric confidence output)."""
    offenders: list[str] = []
    for module in _RECON_MODULES:
        for name, obj in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(obj):
                continue
            ret = inspect.signature(obj).return_annotation
            if float in _referenced_types(ret):
                offenders.append(f"{module.__name__}.{name}")
    assert offenders == [], f"public functions returning float: {offenders}"


def test_recon_models_are_all_frozen() -> None:
    """Every recon model is frozen (append-only; no in-place mutation — design #9 §2.0/§4.7)."""
    for model in _RECON_MODELS:
        assert issubclass(model, pydantic.BaseModel)
        assert model.model_config.get("frozen") is True, model.__name__
