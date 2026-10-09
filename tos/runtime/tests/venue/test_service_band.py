"""``VenueConstraintService`` with a declared band source — CP-3 band 원천 웨이브 plan §8 items
2 (unit half), 4, 4b (the ADMISSIBLE half), 4c and 5
(``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §4.3/§4.4a/§4.4b).

**What each class pins, and what goes red without it:**

* :class:`TestNoBandReaderIsYesterdaysBehaviour` — plan §8 1's unit half: a service with no
  reader issues the same rows, with the same keys, as before this wave. The compose half
  (against the REAL resident file) lives in
  ``tests/compose/test_venue_band_source_wiring.py``.
* :class:`TestEffectiveConstraints` — the band reaches the kernel predicate, and step 3's two
  folds read the SAME object between re-issues.
* :class:`TestTradingDateBond` — plan §4.4a's reachable sequence. Its red proof is the one
  #838 asks for: the clause is reached with the two OTHER mechanisms (the out-of-session
  ``None`` phase and the phase-change re-read) deliberately removed from the input, so the
  date comparison is the ONLY thing that can drop the band.
* :class:`TestWrongContractBandWouldAdmit` — plan §4.4b's fail-open input, stated as the
  ADMISSIBLE it produces. The loader is what prevents it
  (``test_band_source_loader.py::TestContractBond``); this class is why that matters.
* :class:`TestReissueOnlyOnTransition` / :class:`TestBandChangeIsANewGeneration` — plan §4.3's
  review L3 and ADR-002-019 §18.

Hermetic: ``tmp_path`` only; the band "reader" is a list-driven double, so no socket exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityResult,
    OrderShapeFields,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.venue.band_source import BandObservation
from tos_runtime.venue.config import load_venue_constraint_policy
from tos_runtime.venue.service import (
    VENUE_POLICY_BOUND_KIND,
    VENUE_SNAPSHOT_ISSUED_KIND,
    VenueConstraintService,
)

from ._documents import (
    PVL_A05611_LOWER,
    PVL_A05611_UPPER,
    SCHEME,
    band_source_runtime_extra,
    venue_policy_yaml,
    write_fixture_venue_policy,
)

_INSTRUMENT = "K200F"
_TRADING_DATE = "20261008"
#: The measured ``A05610`` band, scaled (see ``test_band_source.py``).
_LOWER, _UPPER = 98746, 115918


class _FakeReader:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __call__(self) -> Any:
        return self.value


def _band(
    *,
    price_min: int = _LOWER,
    price_max: int = _UPPER,
    trading_date: str = _TRADING_DATE,
    continuity: str = "boot-1:0",
) -> BandObservation:
    return BandObservation(
        instrument=_INSTRUMENT,
        price_min=price_min,
        price_max=price_max,
        trading_date=trading_date,
        raw_payload_digest=f"raw-{price_min}-{price_max}-{trading_date}",
        source_continuity_id=continuity,
        as_of_ms=1_000,
        basis=(price_min + price_max) // 2,
        stage_hint=True,
    )


def _rows(evidence_store: SqliteEvidenceStore, kind: str) -> list[dict[str, Any]]:
    cursor = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
    )
    return [json.loads(row[0])["payload"] for row in cursor.fetchall()]


def _build(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    *,
    declare_band_source: bool = True,
    bands: list[BandObservation | None] | None = None,
    trading_date: Any = _TRADING_DATE,
    initial_phase: str | None = "REGULAR",
    initial_generation: int | None = 1,
    tick_size: str = "2",
):
    """A service whose policy declares (or does not declare) a band source.

    ``bands`` is consumed one per READ — the service's own read instants (first snapshot and
    phase change) are what pull from it, so a test never has to simulate them.
    """
    runtime_extra = (
        band_source_runtime_extra(instrument=_INSTRUMENT) if declare_band_source else ""
    )
    path = write_fixture_venue_policy(
        tmp_path,
        venue_policy_yaml(
            price_min="null" if declare_band_source else "100",
            price_max="null" if declare_band_source else "500",
            tick_size=tick_size,
            min_quantity="1",
            max_quantity="10",
            runtime_extra=runtime_extra,
        ),
    )
    loaded = load_venue_constraint_policy(
        path,
        scheme=SCHEME,
        band_transport_instrument=_INSTRUMENT if declare_band_source else None,
    )
    queue = list(bands or [])

    def _read_band() -> BandObservation | None:
        return queue.pop(0) if len(queue) > 1 else (queue[0] if queue else None)

    date_reader = _FakeReader(trading_date)
    phase_reader = _FakeReader(initial_phase)
    generation_reader = _FakeReader(initial_generation)
    service = VenueConstraintService(
        loaded_policy=loaded,
        scheme=SCHEME,
        session_phase_reader=phase_reader,
        tick_generation_reader=generation_reader,
        evidence_store=evidence_store,
        environment_label="test-env",
        route_fields=InstrumentRouteFields(),
        broker_capability_profile_version=None,
        broker_capability_profile_digest=None,
        activated_member_digest="fixture-activation-digest",
        band_reader=_read_band if bands is not None else None,
        trading_date_reader=date_reader,
    )
    return service, phase_reader, generation_reader, date_reader, loaded


def _shape(price: int) -> OrderShapeFields:
    return OrderShapeFields(
        price=price,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )


class TestNoBandReaderIsYesterdaysBehaviour:
    def test_rows_carry_no_band_keys_and_the_three_fields_stay_absent(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, _phase, _gen, _date, _loaded = _build(
            tmp_path, evidence_store, declare_band_source=False, bands=None
        )

        snapshot = service.snapshot()

        assert snapshot.critical_input_snapshot_digest is None
        assert snapshot.source_continuity_id is None
        assert snapshot.max_age is None
        (policy_row,) = _rows(evidence_store, VENUE_POLICY_BOUND_KIND)
        assert set(policy_row) == {
            "policy_id",
            "policy_generation",
            "canonical_digest",
            "activated_member_digest",
            "null_shape_bounds",
        }
        (snapshot_row,) = _rows(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND)
        assert set(snapshot_row) == {
            "snapshot_id",
            "canonical_digest",
            "constraint_generation",
            "observed_session_phase",
            "policy_digest",
            "absent_fields",
        }
        assert snapshot_row["absent_fields"] == [
            "critical_input_snapshot_digest",
            "source_continuity_id",
            "max_age",
        ]

    def test_the_effective_constraints_are_the_policy_object_itself(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, _phase, _gen, _date, loaded = _build(
            tmp_path, evidence_store, declare_band_source=False, bands=None
        )

        assert service.shape_constraints is loaded.policy.shape_constraints


class TestEffectiveConstraints:
    def test_a_band_fills_the_two_bounds_and_nothing_else(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, _phase, _gen, _date, loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        service.snapshot()
        effective = service.shape_constraints

        assert (effective.price_min, effective.price_max) == (_LOWER, _UPPER)
        assert loaded.policy.shape_constraints.price_min is None
        assert effective.tick_size == loaded.policy.shape_constraints.tick_size
        assert effective.lot_size == loaded.policy.shape_constraints.lot_size
        assert effective.max_quantity == loaded.policy.shape_constraints.max_quantity

    def test_the_kernel_predicate_now_answers_on_the_observed_band(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Before a band, the kernel answers UNKNOWN on a null bound
        (``predicates.py``'s required-bound check); with one, it judges."""
        service, _phase, _gen, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        inside = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(100_000),
            candidate_command=None,
        )
        outside = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(_UPPER + 2),
            candidate_command=None,
        )

        assert inside.result is OrderAdmissibilityResult.ADMISSIBLE
        assert outside.result is OrderAdmissibilityResult.INADMISSIBLE

    def test_the_same_constraints_object_is_served_between_reissues(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Plan §8 2: step 3's decision and the gateway's item 11 re-fold must see the same
        values. They read the same property, so what has to hold is that the property does not
        mint a NEW ``model_copy`` per access — which would also make every comparison a
        different object and hide a genuine mid-attempt change."""
        service, _phase, _gen, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        service.snapshot()

        assert service.shape_constraints is service.shape_constraints

    def test_the_three_snapshot_fields_bind_the_observation(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        observation = _band()
        service, _phase, _gen, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[observation]
        )

        snapshot = service.snapshot()

        assert snapshot.critical_input_snapshot_digest == observation.record_digest
        assert snapshot.source_continuity_id == observation.source_continuity_id
        assert snapshot.max_age == f"trading_date_kst:{_TRADING_DATE}"
        (row,) = _rows(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND)
        assert row["band_digest"] == observation.record_digest
        assert row["critical_input_snapshot_digest_role"] == "stand-in"
        assert row["absent_fields"] == []

    def test_the_policy_bound_row_carries_the_band_source_digest(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        _service, _phase, _gen, _date, loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        (row,) = _rows(evidence_store, VENUE_POLICY_BOUND_KIND)

        assert row["band_source_digest"] == loaded.band_source_digest
        assert row["price_scale"] == 100


class TestTradingDateBond:
    """Plan §4.4a — the §8 4 input, with the two masking mechanisms removed."""

    def test_a_band_from_a_previous_trading_date_is_dropped_on_the_first_call_of_the_next(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The reachable sequence: a process reads a band on D, is never asked for a snapshot
        during the out-of-session window, and is asked again on D+1 — same session phase, same
        tick generation. Neither the phase-change re-read nor the out-of-session ``None`` phase
        can fire here, so the date comparison is the ONLY thing standing between the D band
        and a D+1 decision."""
        service, _phase, _gen, date_reader, _loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        service.snapshot()
        assert service.shape_constraints.price_max == _UPPER
        inside_on_d = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(110_000),
            candidate_command=None,
        )
        assert inside_on_d.result is OrderAdmissibilityResult.ADMISSIBLE

        # D+1: same phase, same tick generation, no new read.
        date_reader.value = "20261012"
        second = service.snapshot()

        assert service.shape_constraints.price_max is None
        assert second.max_age is None
        assert second.critical_input_snapshot_digest is None
        stale_price = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(110_000),
            candidate_command=None,
        )
        assert stale_price.result is OrderAdmissibilityResult.UNKNOWN

    def test_an_unavailable_current_trading_date_also_drops_the_band(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, _phase, _gen, date_reader, _loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        service.snapshot()
        date_reader.value = None
        service.snapshot()

        assert service.shape_constraints.price_max is None

    def test_the_bond_runs_before_the_tick_generation_cache(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Plan §4.4a's placement clause, as its own assertion: the second call above uses the
        SAME tick generation as the first, so a bond evaluated after the cache early return
        would never run at all. Asserted on the generation counter rather than on the dropped
        band, so moving the check behind the cache fails HERE specifically."""
        service, _phase, generation, date_reader, _loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        first = service.snapshot()
        assert generation.value == 1  # unchanged across both calls
        date_reader.value = "20261012"
        second = service.snapshot()

        assert second.constraint_generation == first.constraint_generation + 1


class TestWrongContractBandWouldAdmit:
    """Plan §4.4b — the fail-open this wave would otherwise open, stated as the verdict."""

    def test_a_neighbouring_contracts_band_admits_a_price_the_venue_would_reject(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """``A05611``'s measured band (990.48/1162.72) passes every §4.2 clause, so the reader
        cannot tell it apart from ``A05610``'s (987.46/1159.18). Folded onto an ``A05610``
        policy it ADMITS 1160.00 — a price above that contract's own upper limit. Nothing
        downstream catches this; only the loader's scope rule does."""
        wrong = _band(
            price_min=int(float(PVL_A05611_LOWER) * 100),
            price_max=int(float(PVL_A05611_UPPER) * 100),
        )
        service, _phase, _gen, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[wrong]
        )

        service.snapshot()
        verdict = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(116_000),
            candidate_command=None,
        )

        assert verdict.result is OrderAdmissibilityResult.ADMISSIBLE
        assert _UPPER < 116_000  # above A05610's own measured upper limit


class TestReissueOnlyOnTransition:
    """Plan §4.3's review L3 / §8 4c."""

    def test_repeated_out_of_session_calls_advance_the_generation_once(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, phase, generation, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[None], trading_date=None
        )

        first = service.snapshot()
        for step in range(2, 8):
            generation.value = step
            service.snapshot()
        last = service.snapshot()

        assert last.constraint_generation == first.constraint_generation
        assert len(_rows(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND)) == 1
        assert phase.value == "REGULAR"

    def test_a_band_that_reads_identically_does_not_reissue(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, phase, generation, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[_band(), _band()]
        )

        first = service.snapshot()
        phase.value = "CLOSED"
        generation.value = 2
        second = service.snapshot()
        phase.value = "REGULAR"
        generation.value = 3
        third = service.snapshot()

        # Two phase changes => two re-issues, and NOT a third for an unchanged band.
        assert [s.constraint_generation for s in (first, second, third)] == [1, 2, 3]
        generation.value = 4
        assert service.snapshot().constraint_generation == 3


class TestBandChangeIsANewGeneration:
    """ADR-002-019 §18 / plan §8 5 — a band change is a material change ⇒ new Constraint
    Generation.

    **Plan §8 5 says "phase 동일 · band 값만 다른 두 읽기", and a same-phase VALUE change is
    not reachable.** ``read_on`` carries exactly two tokens, so a READ only ever happens at
    boot or on a phase change — two reads with the same phase cannot occur, and a test that
    staged one would be testing a sequence the runtime cannot produce. The same correction
    plan §4.4a already made for its own v1 input applies here: the reachable form of "the
    phase did not change but the band did" is the trading-date bond dropping it, and
    :meth:`test_a_same_phase_band_transition_takes_a_new_generation` is that test — the one
    that goes red if ``band_transition`` is dropped from the re-issue condition. The two
    phase-change tests below pin what the new generation BINDS, which is a different claim.
    """

    def test_a_same_phase_band_transition_takes_a_new_generation(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The clause-specific test (#838): same phase, same tick generation, band present →
        absent. Deleting ``band_transition`` from ``snapshot()``'s re-issue condition leaves
        the phase check alone, which answers "nothing changed" — and the constraint generation
        stops moving even though the kernel is now judging on a different constraint set.
        """
        service, phase, generation, date_reader, _loaded = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        first = service.snapshot()
        date_reader.value = "20261012"
        second = service.snapshot()

        assert phase.value == "REGULAR" and generation.value == 1
        assert second.constraint_generation == first.constraint_generation + 1
        assert len(_rows(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND)) == 2

    def test_a_changed_band_reissues_even_though_the_phase_did_not_change(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        widened = _band(price_min=_LOWER - 200, price_max=_UPPER + 200)
        service, phase, generation, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[_band(), widened]
        )

        first = service.snapshot()
        # A phase change is what triggers the second READ; the band it returns is different,
        # and the assertion below is about the BAND being bound, not about the phase.
        phase.value = "CLOSED"
        generation.value = 2
        second = service.snapshot()

        assert second.constraint_generation == first.constraint_generation + 1
        assert service.shape_constraints.price_max == _UPPER + 200
        assert second.critical_input_snapshot_digest == widened.record_digest

    def test_a_continuity_change_alone_reissues(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Plan §4.3 lists continuity among the three transition triggers. A token reissue
        produces the SAME numbers under a NEW continuity id — if only the values were
        compared, the snapshot would keep claiming the old continuity."""
        reissued = _band(continuity="boot-1:1")
        service, phase, generation, _date, _loaded = _build(
            tmp_path, evidence_store, bands=[_band(), reissued]
        )

        first = service.snapshot()
        phase.value = "CLOSED"
        generation.value = 2
        second = service.snapshot()

        assert second.constraint_generation == first.constraint_generation + 1
        assert second.source_continuity_id == "boot-1:1"
