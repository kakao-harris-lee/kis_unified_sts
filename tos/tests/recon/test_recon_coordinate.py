"""3-axis coordinate non-collapse (design #9 §4.2; #6 §4.7 / #8 §0.4e precedent).

recon ``FieldConfidenceClass`` (per-field evidence confidence) is a distinct axis from
orthostate ``KnowledgeState`` (per-action aggregate knowledge) and capsule ``FieldState``
(per-field context freshness). The three deliberately SHARE the tokens
``UNKNOWN`` / ``CONFLICTED`` / ``STALE`` (ADR uses the same words per-field and
per-action), so non-collapse rests on **distinct types + non-import**, not on global
string distinctness. This is a **test-only** cross-import (recon does not import the other
two at runtime — verified by the import-closure test); it document-locks the axis
distinctness as a regression.
"""

from __future__ import annotations

from tos.capsule import FieldState
from tos.orthostate import KnowledgeState
from tos.recon import FieldConfidenceClass


def test_conflicted_token_is_shared_but_types_are_distinct() -> None:
    """The string ``"CONFLICTED"`` is shared, but the three enum members are distinct types."""
    assert (
        FieldConfidenceClass.CONFLICTED.value
        == KnowledgeState.CONFLICTED.value
        == FieldState.CONFLICTED.value
        == "CONFLICTED"
    )
    assert FieldConfidenceClass.CONFLICTED is not KnowledgeState.CONFLICTED
    assert FieldConfidenceClass.CONFLICTED is not FieldState.CONFLICTED
    assert KnowledgeState.CONFLICTED is not FieldState.CONFLICTED


def test_stale_and_unknown_tokens_shared_but_distinct() -> None:
    """``STALE`` / ``UNKNOWN`` are shared tokens across the axes, but never the same member."""
    assert FieldConfidenceClass.STALE is not KnowledgeState.STALE
    assert FieldConfidenceClass.STALE is not FieldState.STALE
    assert FieldConfidenceClass.UNKNOWN is not FieldState.UNKNOWN


def test_field_confidence_class_has_no_reconciled() -> None:
    """(§2.2) Per-field confidence tops out at CORROBORATED — RECONCILED is the aggregate axis."""
    members = {m.value for m in FieldConfidenceClass}
    assert "RECONCILED" not in members
    assert "RECONCILED" in {m.value for m in KnowledgeState}  # aggregate axis owns it


def test_axes_are_three_separate_types() -> None:
    """The three confidence/knowledge/freshness axes are three separate StrEnum classes."""
    assert FieldConfidenceClass is not KnowledgeState
    assert FieldConfidenceClass is not FieldState
    assert KnowledgeState is not FieldState


def test_field_confidence_class_membership() -> None:
    """FieldConfidenceClass is exactly the ADR §5 five-member set."""
    assert {m.value for m in FieldConfidenceClass} == {
        "UNKNOWN",
        "SINGLE_SOURCE",
        "CORROBORATED",
        "CONFLICTED",
        "STALE",
    }
