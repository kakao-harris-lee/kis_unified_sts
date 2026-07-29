"""§7.2-6/-11 — the resolver: binding integrity, ∅ both ways, and the D-E1 slot (design #32 §3.3).

:class:`~tos.marketfeed.MarketFeedContextResolver` fills the plug D-E1 declared but deliberately
left empty (``core.py:86-105`` — "the slot only"). These tests exercise the four gates that make it
a resolver rather than an inventor:

* it **binds exactly**: a snapshot whose id/digest disagree with the Capsule's ``SnapshotRef`` is
  refused, never silently substituted with something more permissive (ADR-002-018 §15:386);
* it **fails closed**: a store that produces nothing yields ``value_view=None``, and a ``None`` view
  makes every value operand ``UNKNOWN`` — there is no last-known-good fallback (§14:367);
* it **distinguishes ∅ both ways**: an explicit-empty view (bound, nothing admissible) and no view
  at all are separate recorded dispositions, though both are equally restrictive;
* it **invents nothing**: the payload it returns carries only what the injected surfaces supplied.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

from tos.capsule import CriticalInputSnapshot
from tos.engine import DecisionContextResolver, DecisionTickPayload, InstrumentKey
from tos.engine.pipeline import time_admits
from tos.marketfeed import (
    ADMITTING_DISPOSITIONS,
    MarketFeedContextResolver,
    ValueViewDisposition,
    snapshot_binds_capsule_reference,
)
from tos.time import HealthState, SessionContext, UncertaintyInterval

from ._marketfeed_fixtures import (
    ACCOUNT,
    BAR_ONE_AS_OF,
    INSTRUMENT,
    SCHEME,
    issue_snapshot,
    one_bar,
)

KEY = InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def _resolver(*, snapshot, candidates, time_projection=None) -> MarketFeedContextResolver:
    """A resolver over fixed injected surfaces."""

    def store(*, snapshot_id: str | None, canonical_digest: str | None):
        del snapshot_id, canonical_digest
        return snapshot

    def source(resolved: CriticalInputSnapshot, *, instrument_key: InstrumentKey):
        del resolved, instrument_key
        return candidates

    return MarketFeedContextResolver(
        snapshot_store=store,
        candidate_source=source,
        scheme=SCHEME,
        time_projection=time_projection,
    )


# ---------------------------------------------------------------------------
# The D-E1 slot (design #32 §3.3; core.py:86-105)
# ---------------------------------------------------------------------------


def test_the_resolver_satisfies_the_shipped_engine_protocol() -> None:
    """(§3.3) ``(capsule, *, instrument_key) -> DecisionTickPayload`` — the declared slot, filled."""
    capsule, snapshot, candidates = one_bar()
    resolver = _resolver(snapshot=snapshot, candidates=candidates)
    assert isinstance(resolver, DecisionContextResolver)
    payload = resolver(capsule, instrument_key=KEY)
    assert isinstance(payload, DecisionTickPayload)
    assert payload.instrument_key == KEY
    assert payload.capsule is capsule


def test_the_resolved_payload_carries_the_value_surface_d_e1_deferred() -> None:
    """(§3.2 (3)) The payload field D-E1 left for D-E2 is now populated by D-E2."""
    capsule, snapshot, candidates = one_bar()
    payload = _resolver(snapshot=snapshot, candidates=candidates)(capsule, instrument_key=KEY)
    assert payload.value_view is not None
    assert {value.field_key for value in payload.value_view.values} == {"close", "session"}
    assert payload.value_view.snapshot_id == snapshot.snapshot_id
    assert payload.value_view.snapshot_canonical_digest == snapshot.canonical_digest


# ---------------------------------------------------------------------------
# Binding integrity (design #32 §3.3 step 2; ADR-002-018 §15:386)
# ---------------------------------------------------------------------------


def test_a_snapshot_that_is_not_the_referenced_one_is_refused() -> None:
    """(§3.3 ★ mutation canary) A different snapshot body is never substituted for the bound one."""
    capsule, _, candidates = one_bar()
    impostor = issue_snapshot(intended_use="something-else")
    resolved = _resolver(snapshot=impostor, candidates=candidates).resolve(
        capsule, instrument_key=KEY
    )
    assert resolved.resolution.disposition is ValueViewDisposition.BINDING_MISMATCH
    assert resolved.payload.value_view is None
    assert resolved.value_surface_published is False


def test_two_pre_issuance_artifacts_do_not_match_by_both_being_empty() -> None:
    """(§3.3, review MINOR-2 N4) A DRAFT capsule against a DRAFT snapshot does not "agree".

    Both artifacts are constructible pre-issuance through ordinary construction — ``status=DRAFT``
    leaves ``snapshot_id`` and ``canonical_digest`` ``None`` on each — so "both sides are empty" is
    a reachable input, not a hypothetical. It must not read as a match: an unissued snapshot is not
    "exactly the referenced one" (ADR-002-018 §15:386). The reference-side concreteness guard is
    what catches it, and the resolver turns it into a refused binding rather than an empty view.
    """
    from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule

    draft_capsule = DecisionContextCapsule()
    draft_snapshot = CriticalInputSnapshot()
    assert draft_capsule.critical_input_snapshot.snapshot_id is None
    assert draft_capsule.critical_input_snapshot.canonical_digest is None
    assert draft_snapshot.snapshot_id is None
    assert draft_snapshot.canonical_digest is None

    assert snapshot_binds_capsule_reference(draft_capsule, draft_snapshot) is False
    resolved = _resolver(snapshot=draft_snapshot, candidates=()).resolve(
        draft_capsule, instrument_key=KEY
    )
    assert resolved.resolution.disposition is ValueViewDisposition.BINDING_MISMATCH
    assert resolved.payload.value_view is None


def test_a_pre_issuance_snapshot_against_a_concrete_reference_also_fails_closed() -> None:
    """(§3.3, review MINOR-2 N4) The asymmetric half — and why its guard is an *equivalent* mutant.

    Deleting the snapshot-side concreteness guard is provably behaviour-preserving: control reaches
    it only once the reference side is concrete, and a concrete reference compared against any
    ``None`` snapshot field is already unequal. This test therefore pins the *behaviour* (a DRAFT
    body never binds) rather than pretending to kill a mutant that cannot be killed — the review's
    N4 survivor is correctly classified as redundant defence, for this reason rather than for the
    unreachability the review assumed. The source comment records the same proof.
    """
    from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule

    capsule, snapshot, _ = one_bar()
    assert snapshot_binds_capsule_reference(capsule, CriticalInputSnapshot()) is False
    assert snapshot_binds_capsule_reference(DecisionContextCapsule(), snapshot) is False


def test_an_unresolvable_snapshot_reference_is_fail_closed() -> None:
    """(§3.3/§6) A store with no such snapshot yields no view — no fallback, no last-known-good."""
    capsule, _, candidates = one_bar()
    resolved = _resolver(snapshot=None, candidates=candidates).resolve(capsule, instrument_key=KEY)
    assert resolved.resolution.disposition is ValueViewDisposition.SNAPSHOT_UNRESOLVED
    assert resolved.payload.value_view is None


def test_the_two_no_view_dispositions_stay_distinguishable() -> None:
    """(§6 ∅ 양방향) "no such snapshot" and "wrong snapshot" are different facts, both restrictive."""
    capsule, _, candidates = one_bar()
    missing = _resolver(snapshot=None, candidates=candidates).resolve(capsule, instrument_key=KEY)
    mismatched = _resolver(
        snapshot=issue_snapshot(intended_use="something-else"), candidates=candidates
    ).resolve(capsule, instrument_key=KEY)
    assert missing.resolution.disposition is not mismatched.resolution.disposition
    assert missing.payload.value_view is mismatched.payload.value_view is None


def test_an_explicit_empty_view_is_published_and_distinguishable_from_no_view() -> None:
    """(§6 ∅ 양방향 ★) Bound-with-nothing is a published artifact; unbound is not."""
    capsule, snapshot, _ = one_bar()
    empty = _resolver(snapshot=snapshot, candidates=()).resolve(capsule, instrument_key=KEY)
    assert empty.resolution.disposition is ValueViewDisposition.EXPLICIT_EMPTY
    assert empty.payload.value_view is not None
    assert empty.payload.value_view.values == ()
    assert empty.value_surface_published is True
    assert ValueViewDisposition.EXPLICIT_EMPTY in ADMITTING_DISPOSITIONS
    assert ValueViewDisposition.BINDING_MISMATCH not in ADMITTING_DISPOSITIONS


# ---------------------------------------------------------------------------
# Injected time coordinates (design #32 §3.3 step 4)
# ---------------------------------------------------------------------------


def test_without_an_injected_projection_the_time_coordinates_deny() -> None:
    """(§3.3) Absence is restrictive: an unprojected tick does not pass the engine's time gate."""
    capsule, snapshot, candidates = one_bar()
    payload = _resolver(snapshot=snapshot, candidates=candidates)(capsule, instrument_key=KEY)
    admitted, reason = time_admits(payload.time)
    assert admitted is False
    assert reason is not None


def test_the_projection_receives_the_newest_admitted_as_of() -> None:
    """(§3.3 step 4) The value surface's as-of anchor is what the injected projection is handed."""
    seen: list[int | None] = []

    def projection(*, as_of: int | None):
        seen.append(as_of)
        return _admitting_time_inputs(as_of)

    capsule, snapshot, candidates = one_bar()
    payload = _resolver(
        snapshot=snapshot, candidates=candidates, time_projection=projection
    )(capsule, instrument_key=KEY)
    assert seen == [BAR_ONE_AS_OF]
    assert time_admits(payload.time)[0] is True


def test_an_empty_view_projects_a_none_anchor() -> None:
    """(§6) With nothing admitted there is no as-of to anchor on, and that is passed honestly."""
    seen: list[int | None] = []

    def projection(*, as_of: int | None):
        seen.append(as_of)
        return _admitting_time_inputs(as_of)

    capsule, snapshot, _ = one_bar()
    _resolver(snapshot=snapshot, candidates=(), time_projection=projection)(
        capsule, instrument_key=KEY
    )
    assert seen == [None]


def _admitting_time_inputs(as_of: int | None):
    """Injected coordinates that positively admit — every bound supplied, no clock read."""
    from tos.engine import TimeAdmissionInputs

    anchor = 0 if as_of is None else as_of
    return TimeAdmissionInputs(
        source_age=0,
        max_age_bound=60_000,
        future_tolerance=1_000,
        snapshot_age_bound=1_000,
        maximum_consumer_age_ms=60_000,
        session_context=SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase="CONTINUOUS",
            is_open=True,
            tz_version_conflict=False,
            boundary_value=anchor - 1_000,
        ),
        uncertainty_interval=UncertaintyInterval(lo=anchor, hi=anchor + 100),
        health_state=HealthState.TRUSTED,
    )


# ---------------------------------------------------------------------------
# The resolver invents nothing (design #32 §3.3 ⚠; core.py:93-98)
# ---------------------------------------------------------------------------


def test_the_resolver_publishes_only_what_the_snapshot_governs() -> None:
    """(§3.3 ⚠ over-realization seal) A candidate the snapshot does not govern is not exposed."""
    from ._marketfeed_fixtures import candidate as make_candidate
    from ._marketfeed_fixtures import preimage as make_preimage

    capsule, snapshot, candidates = one_bar()
    invented = make_candidate("lower_band", "raw-1", make_preimage(lower_band=1))
    resolved = _resolver(snapshot=snapshot, candidates=(*candidates, invented)).resolve(
        capsule, instrument_key=KEY
    )
    assert resolved.payload.value_view is not None
    assert {value.field_key for value in resolved.payload.value_view.values} == {
        "close",
        "session",
    }
    assert {entry.field_key for entry in resolved.resolution.rejected} == {"lower_band"}


def test_the_resolver_claims_no_causal_ordering_coordinate() -> None:
    """(§3.3) The reference coordinate is stamped by the event source, not invented here."""
    from tos.ordering import OrderingEvent

    capsule, snapshot, candidates = one_bar()
    payload = _resolver(snapshot=snapshot, candidates=candidates)(capsule, instrument_key=KEY)
    assert payload.reference == OrderingEvent()


def test_the_resolver_is_deterministic_across_repeated_calls() -> None:
    """(§1.1/§7.1) No clock, no RNG: the same inputs resolve to the same view digest."""
    capsule, snapshot, candidates = one_bar()
    resolver = _resolver(snapshot=snapshot, candidates=candidates)
    first = resolver(capsule, instrument_key=KEY)
    second = resolver(capsule, instrument_key=KEY)
    assert first.value_view is not None and second.value_view is not None
    assert first.value_view.canonical_digest == second.value_view.canonical_digest
    assert first == second
