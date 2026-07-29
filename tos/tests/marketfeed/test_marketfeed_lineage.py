"""§7.2-10 — derived indicators: lineage reproducibility and the look-ahead boundary (design #32 §5).

RFC-008 §9:290-301 puts every derived value *outside and before* DSL evaluation: the DSL algebra has
no arithmetic node and no bar history, so a band or a moving average is computed upstream and
arrives as an admitted observation carrying a ``TransformationLineage`` (design #32 §5.1). Two
independent judgements then decide whether it may be exposed:

* **reproducibility**, delegated verbatim to the shipped
  :func:`tos.capsule.predicates.derive_lineage_state` (design #32 §12.1 REUSE — the predicate is
  *not* re-authored here). Non-reproducible, empty parent set, or a parent missing its id/digest ⇒
  ``INVALID`` (ADR-002-018 §10:288);
* **causality**, owned here: every recorded parent's as-of must be at or before the derived value's
  as-of (RFC-004 §6:162-165 — "no forward-fill or last-known-good substitution").

The two failure polarities are deliberately different, and that difference is asserted: a parent
*later* than its child is a proven look-ahead (``INVALID``), while a parent that cannot be resolved
at all is merely unestablished (``UNKNOWN``). Both block; only one is an accusation.

⚠ **Honest boundary** (design #32 §5.4). This checks what the lineage **records**. Runtime
enforcement that a producer did not peek at a future bar while computing is D-E3's
(``LookaheadGuard``), and design #32 says so rather than claiming it here.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

from tos.capsule import FieldState
from tos.capsule.lineage import ParentRef, TransformationLineage
from tos.capsule.predicates import derive_lineage_state
from tos.marketfeed import (
    ValueRejectionReason,
    index_observations,
    lineage_state_for_output,
    publish_context_value_view,
)

from ._marketfeed_fixtures import (
    BAR_ONE_AS_OF,
    BAR_TWO_AS_OF,
    CLOSE_BAR_ONE,
    SCHEME,
    candidate,
    evaluation,
    issue_capsule,
    issue_snapshot,
    lineage_node,
    observation,
    preimage,
)

_BAND = 4_500_000


def _derived_bar(
    *,
    parent_as_of: int = BAR_ONE_AS_OF,
    derived_as_of: int = BAR_ONE_AS_OF,
    reproducible: bool = True,
    parents: tuple[str, ...] = ("raw-close",),
    lineage_field_state: FieldState = FieldState.VALID,
):
    """A snapshot with one parent close observation and one derived band observation."""
    close_payload = preimage(close=CLOSE_BAR_ONE)
    band_payload = preimage(lower_band=_BAND)
    parent = observation(
        raw_event_id="raw-close", payload=close_payload, as_of=parent_as_of
    )
    derived = observation(raw_event_id="raw-band", payload=band_payload, as_of=derived_as_of)
    snapshot = issue_snapshot(
        observations=(parent, derived),
        field_evaluations=(evaluation("close"), evaluation("lower_band")),
        transformation_lineage=(
            lineage_node(
                output_id="raw-band",
                parents=parents,
                reproducible=reproducible,
                field_state=lineage_field_state,
            ),
        ),
    )
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("lower_band", "raw-band", band_payload),),
        scheme=SCHEME,
    )
    return snapshot, resolution


def _reasons(resolution) -> set[ValueRejectionReason]:
    """The named rejection reasons in a resolution."""
    return {entry.reason for entry in resolution.rejected}


# ---------------------------------------------------------------------------
# A derived value with sound lineage publishes
# ---------------------------------------------------------------------------


def test_a_reproducible_derived_value_publishes() -> None:
    """(§5.1/§5.2) A band computed upstream reaches the DSL as an admitted Critical Input."""
    _, resolution = _derived_bar()
    assert [value.field_key for value in resolution.values] == ["lower_band"]
    assert resolution.rejected == ()


def test_a_parent_strictly_before_its_child_is_sound_causality() -> None:
    """(§5.4) Parent as-of < derived as-of is the ordinary, admitted case."""
    _, resolution = _derived_bar(parent_as_of=BAR_ONE_AS_OF, derived_as_of=BAR_TWO_AS_OF)
    assert [value.field_key for value in resolution.values] == ["lower_band"]


def test_a_direct_observation_needs_no_lineage_at_all() -> None:
    """(§5, ∅ discipline) A non-derived value has no derivation to be unreproducible about.

    This is *not* the vacuous-∅ case §2.2 seals: the applicable side ("is this value derived?") is
    checked before the empty set is interpreted, which is the #26 WDR MAJOR-1 lesson — an
    over-rejecting fail-closed guard is its own defect class.
    """
    payload = preimage(close=CLOSE_BAR_ONE)
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(observations=(obs,), field_evaluations=(evaluation("close"),))
    observations, _ = index_observations(snapshot)
    state, reason = lineage_state_for_output("raw-1", BAR_ONE_AS_OF, (), observations)
    assert state is FieldState.VALID
    assert reason is None


# ---------------------------------------------------------------------------
# Reproducibility (REUSE — design #32 §12.1)
# ---------------------------------------------------------------------------


def test_a_non_reproducible_lineage_blocks_the_value() -> None:
    """(§5.2, ADR-002-018 §10:288) ``reproducible=False`` ⇒ INVALID ⇒ not exposed."""
    _, resolution = _derived_bar(reproducible=False)
    assert resolution.values == ()
    assert _reasons(resolution) == {ValueRejectionReason.LINEAGE_NOT_REPRODUCIBLE}


def test_an_empty_parent_set_blocks_the_value() -> None:
    """(§5.2) A derivation from nothing is not a derivation."""
    _, resolution = _derived_bar(parents=())
    assert resolution.values == ()
    assert _reasons(resolution) == {ValueRejectionReason.LINEAGE_NOT_REPRODUCIBLE}


def test_reproducibility_is_delegated_not_re_authored() -> None:
    """(§12.1 REUSE) The shipped capsule predicate is the authority on the same nodes."""
    sound = TransformationLineage(
        output_id="raw-band",
        parents=(ParentRef(parent_id="raw-close", digest="d"),),
        reproducible=True,
    )
    unsound = sound.model_copy(update={"reproducible": False})
    assert derive_lineage_state(sound) is FieldState.VALID
    assert derive_lineage_state(unsound) is FieldState.INVALID
    parentless = sound.model_copy(update={"parents": ()})
    assert derive_lineage_state(parentless) is FieldState.INVALID


def test_a_blocking_lineage_field_state_propagates() -> None:
    """(§5.2) The node's own recorded state participates in the aggregate."""
    _, resolution = _derived_bar(lineage_field_state=FieldState.CONFLICTED)
    assert resolution.values == ()
    assert resolution.rejected


# ---------------------------------------------------------------------------
# Look-ahead (design #32 §5.4) — and its polarity
# ---------------------------------------------------------------------------


def test_a_parent_later_than_its_child_is_look_ahead() -> None:
    """(§5.4 ★) A band claiming a parent from the future is refused, named as look-ahead."""
    _, resolution = _derived_bar(parent_as_of=BAR_TWO_AS_OF, derived_as_of=BAR_ONE_AS_OF)
    assert resolution.values == ()
    assert _reasons(resolution) == {ValueRejectionReason.LINEAGE_LOOKAHEAD}


def test_look_ahead_is_invalid_while_an_unresolvable_parent_is_only_unknown() -> None:
    """(§5.4 ★ polarity) A proven violation and an unestablished one are different facts.

    Both block. Collapsing them would either slander an incomplete snapshot as a look-ahead
    violation, or downgrade a real violation to mere uncertainty.
    """
    snapshot, _ = _derived_bar()
    observations, _ = index_observations(snapshot)

    future_parent = lineage_node(output_id="raw-band", parents=("raw-close",))
    invalid, invalid_reason = lineage_state_for_output(
        "raw-band", BAR_ONE_AS_OF - 1, (future_parent,), observations
    )
    assert invalid is FieldState.INVALID
    assert invalid_reason is ValueRejectionReason.LINEAGE_LOOKAHEAD

    dangling = lineage_node(output_id="raw-band", parents=("raw-nowhere",))
    unknown, unknown_reason = lineage_state_for_output(
        "raw-band", BAR_ONE_AS_OF, (dangling,), observations
    )
    assert unknown is FieldState.UNKNOWN
    assert unknown_reason is ValueRejectionReason.LINEAGE_PARENT_UNRESOLVED


def test_an_unresolvable_parent_blocks_the_value() -> None:
    """(§5.4) Causality that cannot be established is fail-closed, not assumed sound."""
    _, resolution = _derived_bar(parents=("raw-nowhere",))
    assert resolution.values == ()
    assert _reasons(resolution) == {ValueRejectionReason.LINEAGE_PARENT_UNRESOLVED}


def test_a_parent_with_no_as_of_blocks_the_value() -> None:
    """(§5.4/§4.2) A parent with no as-of anchor cannot evidence that it preceded its child."""
    from tos.capsule.observation import ObservationTime

    close_payload = preimage(close=CLOSE_BAR_ONE)
    band_payload = preimage(lower_band=_BAND)
    parent = observation(
        raw_event_id="raw-close", payload=close_payload, as_of=BAR_ONE_AS_OF
    ).model_copy(update={"time": ObservationTime(source_event_time=None)})
    derived = observation(raw_event_id="raw-band", payload=band_payload, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(
        observations=(parent, derived),
        field_evaluations=(evaluation("lower_band"),),
        transformation_lineage=(lineage_node(output_id="raw-band", parents=("raw-close",)),),
    )
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("lower_band", "raw-band", band_payload),),
        scheme=SCHEME,
    )
    assert resolution.values == ()
    assert _reasons(resolution) == {ValueRejectionReason.LINEAGE_PARENT_UNRESOLVED}


def test_a_contested_parent_identity_is_unresolvable_not_arbitrarily_resolved() -> None:
    """(§5.4/§6 ★ review MINOR-2 L7) The ambiguous-id pop is load-bearing on the lineage path.

    :func:`~tos.marketfeed.index_observations` drops any ``raw_event_id`` carried by more than one
    observation. For the publication path that is defence in depth — ``_admit_one`` checks the
    returned ambiguous set directly. For **this** path it is the only seal:
    :func:`~tos.marketfeed.lineage_state_for_output` resolves parents through the index alone and
    never sees the ambiguous set, so leaving a contested id in place would hand it the *first*
    observation under that identity. Here that first observation is the innocent one and the second
    is future-dated: an arbitrary fold would silently clear a look-ahead. Popping makes the parent
    unresolvable, so causality fails closed instead.
    """
    close_payload = preimage(close=CLOSE_BAR_ONE)
    late_payload = preimage(close=CLOSE_BAR_ONE + 1)
    band_payload = preimage(lower_band=_BAND)
    snapshot = issue_snapshot(
        observations=(
            observation(raw_event_id="raw-close", payload=close_payload, as_of=BAR_ONE_AS_OF),
            observation(raw_event_id="raw-close", payload=late_payload, as_of=BAR_TWO_AS_OF),
            observation(raw_event_id="raw-band", payload=band_payload, as_of=BAR_ONE_AS_OF),
        ),
        field_evaluations=(evaluation("lower_band"),),
        transformation_lineage=(lineage_node(output_id="raw-band", parents=("raw-close",)),),
    )
    observations, ambiguous = index_observations(snapshot)
    assert ambiguous == frozenset({"raw-close"})
    assert "raw-close" not in observations, (
        "a contested identity must not survive in the index — the lineage path has no other seal"
    )

    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate("lower_band", "raw-band", band_payload),),
        scheme=SCHEME,
    )
    assert resolution.values == ()
    assert _reasons(resolution) == {ValueRejectionReason.LINEAGE_PARENT_UNRESOLVED}


def test_a_simultaneous_parent_is_admitted_not_over_rejected() -> None:
    """(§5.4, #26 WDR MAJOR-1) The boundary is ``<=``: an equal as-of is not look-ahead."""
    _, resolution = _derived_bar(parent_as_of=BAR_ONE_AS_OF, derived_as_of=BAR_ONE_AS_OF)
    assert [value.field_key for value in resolution.values] == ["lower_band"]
