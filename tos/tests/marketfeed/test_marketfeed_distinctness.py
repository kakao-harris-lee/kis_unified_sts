"""§7.2-2 — per-bar distinctness as a structural corollary (design #32 §4; the D-E1 Gap-1 residue).

The chain the design claims, tested link by link on shipped artifacts::

    distinct bar
      -> distinct observation ``time.source_event_time``      (the as-of anchor, covered)
      -> distinct Critical Input Snapshot ``canonical_digest`` (observations ∈ _COVERED_FIELDS)
      -> distinct Decision Context Capsule ``canonical_digest`` (the SnapshotRef is covered)
      -> distinct value-view ``canonical_digest``              (the as-of is in the preimage)

The load sits on the **covered ``source_event_time``**, not on the payload digest (design #32 §4.1,
MINOR-1): the payload preimage's exact production form is still deferred (§2.3, 미결-3), so a claim
resting on it would rest on something unfixed. Two bars carrying the *same* value but different
as-of times therefore still differ everywhere downstream — asserted directly below.

The converse matters as much: identical inputs reproduce identical digests. Distinctness without
reproducibility would just be noise.

⚠ **Honest boundary** (design #32 §4.3). This is a corollary of a producer stamping distinct bars
with distinct as-of times. A producer that stamps two bars identically collapses the chain, and
that is a producer-honesty problem the publication gate cannot close — it can only refuse an
*absent* as-of, which it does.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

from tos.capsule.snapshot import CriticalInputSnapshot
from tos.marketfeed import (
    ValueRejectionReason,
    context_value_view_digest,
    publish_context_value_view,
)

from ._marketfeed_fixtures import (
    BAR_ONE_AS_OF,
    BAR_TWO_AS_OF,
    CLOSE_BAR_ONE,
    CLOSE_BAR_TWO,
    SCHEME,
    candidate,
    evaluation,
    issue_capsule,
    issue_snapshot,
    observation,
    one_bar,
    preimage,
)


def _bar(*, as_of: int, close: int):
    """One bar's (capsule, snapshot, resolution) triple."""
    payload = preimage(close=close)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=as_of)
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("close", "raw-1", payload),),
        scheme=SCHEME,
    )
    return capsule, snapshot, resolution


# ---------------------------------------------------------------------------
# The chain (design #32 §4.1)
# ---------------------------------------------------------------------------


def test_the_as_of_anchor_is_a_covered_snapshot_field() -> None:
    """(§4.1 link 2) ``observations`` is in ``_COVERED_FIELDS`` — read off the shipped model."""
    assert "observations" in CriticalInputSnapshot._COVERED_FIELDS


def test_distinct_bars_yield_distinct_snapshot_capsule_and_view_digests() -> None:
    """(§4.1 ★ the whole chain) Every downstream identity separates."""
    _, snapshot_one, resolution_one = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    _, snapshot_two, resolution_two = _bar(as_of=BAR_TWO_AS_OF, close=CLOSE_BAR_TWO)

    assert snapshot_one.canonical_digest != snapshot_two.canonical_digest
    assert snapshot_one.snapshot_id != snapshot_two.snapshot_id
    assert resolution_one.view is not None and resolution_two.view is not None
    assert resolution_one.view.canonical_digest != resolution_two.view.canonical_digest


def test_the_as_of_alone_separates_two_bars_carrying_the_same_value() -> None:
    """(§4.1 MINOR-1 ★) The distinctness load is the covered as-of, not the value or its digest.

    Same close, different bar. If the chain depended on the value (or on the payload preimage's
    still-deferred form) these two would collide; because it depends on ``source_event_time``, they
    do not.
    """
    _, snapshot_one, resolution_one = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    _, snapshot_two, resolution_two = _bar(as_of=BAR_TWO_AS_OF, close=CLOSE_BAR_ONE)

    assert resolution_one.values[0].value == resolution_two.values[0].value
    assert resolution_one.values[0].as_of != resolution_two.values[0].as_of
    assert snapshot_one.canonical_digest != snapshot_two.canonical_digest
    assert resolution_one.view is not None and resolution_two.view is not None
    assert resolution_one.view.canonical_digest != resolution_two.view.canonical_digest


def test_the_capsule_digest_separates_because_the_snapshot_reference_is_covered() -> None:
    """(§4.1 link 3) The Capsule binds the snapshot's digest, so it moves when the snapshot moves."""
    capsule_one, _, _ = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    capsule_two, _, _ = _bar(as_of=BAR_TWO_AS_OF, close=CLOSE_BAR_ONE)
    assert "critical_input_snapshot" in type(capsule_one)._COVERED_FIELDS
    assert capsule_one.canonical_digest != capsule_two.canonical_digest
    assert capsule_one.capsule_id != capsule_two.capsule_id


# ---------------------------------------------------------------------------
# Reproducibility — the converse (design #32 §7.2-2)
# ---------------------------------------------------------------------------


def test_identical_inputs_reproduce_an_identical_view_digest() -> None:
    """(§4.1 converse) Same bar, same values ⇒ same view digest. No nonce, no clock."""
    _, _, first = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    _, _, second = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    assert first.view is not None and second.view is not None
    assert first.view.canonical_digest == second.view.canonical_digest


def test_the_view_digest_does_not_depend_on_candidate_order() -> None:
    """(§2.2) The digest binds the value *set*; a producer's emission order is not a decision input."""
    capsule, snapshot, candidates = one_bar()
    forward = publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    reversed_ = publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=tuple(reversed(candidates)), scheme=SCHEME
    )
    assert forward.view is not None and reversed_.view is not None
    assert forward.view.canonical_digest == reversed_.view.canonical_digest


def test_the_view_digest_moves_when_any_value_moves() -> None:
    """(§3.2 (3b)) A different value set is a different digest — the signature append's whole point."""
    _, _, base = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    _, _, moved = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_TWO)
    assert base.view is not None and moved.view is not None
    assert base.view.canonical_digest != moved.view.canonical_digest


def test_the_view_digest_is_sensitive_to_every_value_field_under_one_binding() -> None:
    """(§2.2/§3.2 3b ★ review MINOR-1) The digest depends on the **values**, not only the binding.

    The honest publication path propagates a value change through the snapshot digest, so the
    end-to-end tests above cannot tell a values-sensitive digest from a values-*blind* one: both
    would separate two real bars. This canary pins the property directly — one fixed
    ``(snapshot_id, snapshot_canonical_digest)`` binding, and each of the five ``ContextValue``
    fields perturbed in turn. ``context_value_view_digest`` is a public export, so its
    value-sensitivity is a contract, not an incidental consequence of how the caller happens to
    build its inputs.

    Without it, a mutant whose digest preimage omits ``values`` entirely survives the whole suite.
    """
    from tos.dsl import ContextValue

    base = ContextValue(
        field_key="close",
        value=CLOSE_BAR_ONE,
        as_of=BAR_ONE_AS_OF,
        payload_digest="pay-1",
        observation_ref="raw-1",
    )
    perturbations = {
        "value": base.model_copy(update={"value": CLOSE_BAR_TWO}),
        "as_of": base.model_copy(update={"as_of": BAR_TWO_AS_OF}),
        "field_key": base.model_copy(update={"field_key": "open"}),
        "payload_digest": base.model_copy(update={"payload_digest": "pay-2"}),
        "observation_ref": base.model_copy(update={"observation_ref": "raw-2"}),
    }

    def digest_of(*values: ContextValue) -> str:
        return context_value_view_digest(
            snapshot_id="cis-fixed",
            snapshot_canonical_digest="sd-fixed",
            values=values,
            scheme=SCHEME,
        )

    baseline = digest_of(base)
    for field, perturbed in perturbations.items():
        assert digest_of(perturbed) != baseline, (
            f"the view digest ignores ContextValue.{field} — a values-blind digest would let two "
            "different value sets sign identically (design #32 §3.2 (3b))"
        )
    assert digest_of() != baseline, "an empty value set must not digest like a populated one"
    assert digest_of(base, perturbations["field_key"]) != baseline, (
        "adding a second value must move the digest"
    )
    assert digest_of(base) == baseline, "the digest is a pure function of its inputs"


def test_the_view_digest_binds_the_snapshot_identity_too() -> None:
    """(§2.2) Two views over identical values but different snapshots are different views."""
    _, snapshot, resolution = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    assert resolution.view is not None
    rebound = context_value_view_digest(
        snapshot_id="cis-somewhere-else",
        snapshot_canonical_digest=snapshot.canonical_digest or "",
        values=resolution.view.values,
        scheme=SCHEME,
    )
    assert rebound != resolution.view.canonical_digest


# ---------------------------------------------------------------------------
# The publication gate's own share (design #32 §4.2)
# ---------------------------------------------------------------------------


def test_an_absent_as_of_is_refused_so_the_chain_cannot_start_unanchored() -> None:
    """(§4.2) The gate refuses what it *can* refuse: a missing as-of anchor."""
    from tos.capsule.observation import ObservationTime

    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF).model_copy(
        update={"time": ObservationTime(source_event_time=None)}
    )
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("close", "raw-1", payload),),
        scheme=SCHEME,
    )
    assert {entry.reason for entry in resolution.rejected} == {ValueRejectionReason.AS_OF_ABSENT}


def test_the_honest_boundary_is_recorded_a_stale_producer_still_collapses_the_chain() -> None:
    """(§4.3 ⚠ over-claim seal) Same as-of on two bars ⇒ same digests. Stated, not hidden.

    This test asserts the *limit*, not a guarantee: the publication gate cannot tell that a producer
    reused an as-of, so the chain collapses and the design says so. Complete enforcement is upstream
    (the Context Integrity Service) plus the signature append's detectability.
    """
    _, snapshot_one, resolution_one = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    _, snapshot_two, resolution_two = _bar(as_of=BAR_ONE_AS_OF, close=CLOSE_BAR_ONE)
    assert snapshot_one.canonical_digest == snapshot_two.canonical_digest
    assert resolution_one.view is not None and resolution_two.view is not None
    assert resolution_one.view.canonical_digest == resolution_two.view.canonical_digest
