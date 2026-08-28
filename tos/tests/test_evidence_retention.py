"""Retention / tombstone / supersession — ERI-EV-010, ERI-INV-011 (design #4 §4.5/§2.6).

Retention is orthogonal to economic effect: expiry / compaction / deletion never
erase an order, exposure, UNKNOWN, or commitment. A Tombstone over a record that
supports live/economic state is inadmissible; a supersession preserves the
original (append-only lineage).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.evidence import (
    RetentionHorizon,
    RetentionRecordClassRule,
    RetentionSubject,
    economic_effects_after_retention,
    effective_retention_horizon,
)
from tos.evidence.predicates import tombstone_admissible

from ._evidence_strategies import SCHEME, issue_envelope

_EFFECT_IDS = st.lists(st.text(min_size=1, max_size=6), max_size=6, unique=True)


@given(effects=_EFFECT_IDS, expired=_EFFECT_IDS)
def test_economic_effect_survives_retention_expiry(
    effects: list[str], expired: list[str]
) -> None:
    """Retention expiry never erases an economic effect (ERI-INV-011, §4.5)."""
    survivors = economic_effects_after_retention(effects, expired)
    assert survivors == frozenset(effects)


def test_economic_effect_horizon_dominates() -> None:
    """The economic-effect horizon dominates a shorter idempotency horizon (§17 432)."""
    rule = RetentionRecordClassRule(
        record_class="INTENT",
        horizons=(
            RetentionHorizon.IDEMPOTENCY_REPLAY,
            RetentionHorizon.ECONOMIC_EFFECT,
        ),
    )
    assert effective_retention_horizon(rule) is RetentionHorizon.ECONOMIC_EFFECT


def test_legal_hold_dominates_economic_effect() -> None:
    """An incident legal hold dominates the economic-effect horizon (longest applicable)."""
    rule = RetentionRecordClassRule(
        record_class="INTENT",
        horizons=(
            RetentionHorizon.ECONOMIC_EFFECT,
            RetentionHorizon.INCIDENT_LEGAL_HOLD,
        ),
    )
    assert effective_retention_horizon(rule) is RetentionHorizon.INCIDENT_LEGAL_HOLD


def test_no_horizon_is_none() -> None:
    """A rule with no horizons has no effective horizon."""
    assert (
        effective_retention_horizon(RetentionRecordClassRule(record_class="x")) is None
    )


def test_injected_durations_determine_longest_applicable() -> None:
    """(MINOR-3) Injected per-horizon durations are authoritative over the rank fallback.

    "Longest applicable" (§17) is ultimately a duration decision; when injected
    durations are supplied they win, and the documented rank is only a fallback.
    """
    rule = RetentionRecordClassRule(
        record_class="INTENT",
        horizons=(
            RetentionHorizon.ECONOMIC_EFFECT,
            RetentionHorizon.IDEMPOTENCY_REPLAY,
        ),
    )
    # By rank alone, ECONOMIC_EFFECT dominates.
    assert effective_retention_horizon(rule) is RetentionHorizon.ECONOMIC_EFFECT
    # With injected durations, the longer duration wins even against the rank.
    injected = {
        RetentionHorizon.ECONOMIC_EFFECT: 10,
        RetentionHorizon.IDEMPOTENCY_REPLAY: 10_000,
    }
    assert (
        effective_retention_horizon(rule, horizon_durations_ms=injected)
        is RetentionHorizon.IDEMPOTENCY_REPLAY
    )


# ---- tombstone admissibility (§2.6) ----------------------------------------


def test_tombstone_admissible_for_inert_subject() -> None:
    """A Tombstone is admissible only when the target supports no live/economic state."""
    assert tombstone_admissible(RetentionSubject()) is True


@given(
    flag=st.sampled_from(sorted(RetentionSubject.model_fields)),
)
def test_tombstone_inadmissible_when_any_live_state(flag: str) -> None:
    """Any live/economic-state flag makes a Tombstone over the target inadmissible."""
    subject = RetentionSubject(**{flag: True})
    assert tombstone_admissible(subject) is False


def test_tombstone_record_class_is_an_envelope() -> None:
    """A Tombstone is an appended envelope with record_class=TOMBSTONE (§2.6)."""
    tombstone = issue_envelope(record_class="TOMBSTONE")
    assert tombstone.record_class == "TOMBSTONE"
    assert tombstone.canonical_digest == SCHEME.compute_digest(
        tombstone.covered_content()
    )


# ---- supersession lineage (append-only) ------------------------------------


def test_supersession_preserves_original() -> None:
    """A superseding record links back; the original stays immutable (§2.0/§17 443)."""
    original = issue_envelope(evidence_record_id="er-1")
    from tos.evidence.envelope import Lifecycle

    superseder = issue_envelope(
        evidence_record_id="er-2",
        lifecycle=Lifecycle(retention_class="standard", supersedes_record_id="er-1"),
    )
    assert superseder.lifecycle.supersedes_record_id == "er-1"
    # The original is untouched (append-only, not overwritten).
    assert original.evidence_record_id == "er-1"
    assert original.lifecycle.supersedes_record_id is None
