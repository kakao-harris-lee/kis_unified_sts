"""``VenueConstraintService`` with a declared band source — CP-3 band 원천 웨이브 plan §8 items"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityResult,
    OrderShapeFields,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.venue.band_journal import (
    ProducerJournalBandReader,
    ProducerJournalBandSource,
)
from tos_runtime.venue.band_source import BandObservation
from tos_runtime.venue.config import load_venue_constraint_policy
from tos_runtime.venue.service import (
    VENUE_POLICY_BOUND_KIND,
    VENUE_SNAPSHOT_ISSUED_KIND,
    VenueConstraintService,
)

from ._documents import (
    PVL_A05610_BASIS,
    PVL_A05610_LOWER,
    PVL_A05610_UPPER,
    PVL_A05611_LOWER,
    PVL_A05611_UPPER,
    SCHEME,
    band_source_runtime_extra,
    producer_journal_band_source_runtime_extra,
    venue_policy_yaml,
    write_fixture_venue_policy,
)

_INSTRUMENT = "K200F"
_TRADING_DATE = "20261008"
_LOWER, _UPPER = 98746, 115918


class _FakeReader:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __call__(self) -> Any:
        return self.value


class _Monotonic:
    """Satisfies ``MonotonicSource`` structurally (it is a Protocol), for the one test class"""

    def __init__(self) -> None:
        self._now = 1_000

    def now_ms(self) -> int:
        self._now += 1
        return self._now


class _Reads:
    """How many times the band reader was actually called — the observable ``read_on`` acts"""

    def __init__(self) -> None:
        self.count = 0


class _Sink:
    """The ``EvidenceRecorder`` a REAL band reader writes its ``VENUE_BAND_OBSERVED`` rows"""

    def __init__(self) -> None:
        self.rows: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Any) -> None:
        self.rows.append((kind, dict(fields)))

    def only(self) -> dict[str, Any]:
        assert len(self.rows) == 1, self.rows
        kind, fields = self.rows[0]
        assert kind == "VENUE_BAND_OBSERVED"
        return fields


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
        symmetric_about_basis=True,
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
    read_on: str = '["boot", "phase_change"]',
):
    """A service whose policy declares (or does not declare) a band source."""
    runtime_extra = (
        band_source_runtime_extra(instrument=_INSTRUMENT, read_on=read_on)
        if declare_band_source
        else ""
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
        band_transport_instrument_reader=(
            (lambda: _INSTRUMENT) if declare_band_source else None
        ),
    )
    queue = list(bands or [])
    reads = _Reads()

    def _read_band() -> BandObservation | None:
        reads.count += 1
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
    return service, phase_reader, generation_reader, date_reader, loaded, reads


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
        service, _phase, _gen, _date, _loaded, _reads = _build(
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
        service, _phase, _gen, _date, loaded, _reads = _build(
            tmp_path, evidence_store, declare_band_source=False, bands=None
        )

        assert service.shape_constraints is loaded.policy.shape_constraints


class TestEffectiveConstraints:
    def test_a_band_fills_the_two_bounds_and_nothing_else(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, _phase, _gen, _date, loaded, _reads = _build(
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
        """Before a band, the kernel answers UNKNOWN on a null bound"""
        service, _phase, _gen, _date, _loaded, _reads = _build(
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
        """Plan §8 2: step 3's decision and the gateway's item 11 re-fold must see the same"""
        service, _phase, _gen, _date, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        service.snapshot()

        assert service.shape_constraints is service.shape_constraints

    def test_the_three_snapshot_fields_bind_the_observation(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        observation = _band()
        service, _phase, _gen, _date, _loaded, _reads = _build(
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
        _service, _phase, _gen, _date, loaded, _reads = _build(
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
        """The reachable sequence: a process reads a band on D, is never asked for a snapshot"""
        service, _phase, _gen, date_reader, _loaded, _reads = _build(
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
        service, _phase, _gen, date_reader, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        service.snapshot()
        date_reader.value = None
        service.snapshot()

        assert service.shape_constraints.price_max is None

    def test_the_bond_runs_before_the_tick_generation_cache(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Plan §4.4a's placement clause, as its own assertion: the second call above uses the"""
        service, _phase, generation, date_reader, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        first = service.snapshot()
        assert generation.value == 1
        date_reader.value = "20261012"
        second = service.snapshot()

        assert second.constraint_generation == first.constraint_generation + 1


class TestWrongContractBandWouldAdmit:
    """Plan §4.4b — the fail-open this wave would otherwise open, stated as the verdict."""

    def test_a_neighbouring_contracts_band_admits_a_price_the_venue_would_reject(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """``A05611``'s measured band (990.48/1162.72) passes every §4.2 clause, so the reader"""
        wrong = _band(
            price_min=int(float(PVL_A05611_LOWER) * 100),
            price_max=int(float(PVL_A05611_UPPER) * 100),
        )
        service, _phase, _gen, _date, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[wrong]
        )

        service.snapshot()
        verdict = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(116_000),
            candidate_command=None,
        )

        assert verdict.result is OrderAdmissibilityResult.ADMISSIBLE
        assert _UPPER < 116_000


class TestReissueOnlyOnTransition:
    """Plan §4.3's review L3 / §8 4c."""

    def test_repeated_out_of_session_calls_advance_the_generation_once(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, phase, generation, _date, _loaded, _reads = _build(
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

    def test_a_new_tick_generation_without_a_phase_change_does_not_reissue(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Renamed from "a band that reads identically does not reissue" (independent review"""
        service, phase, generation, _date, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band(), _band()]
        )

        first = service.snapshot()
        phase.value = "CLOSED"
        generation.value = 2
        second = service.snapshot()
        phase.value = "REGULAR"
        generation.value = 3
        third = service.snapshot()

        assert [s.constraint_generation for s in (first, second, third)] == [1, 2, 3]
        generation.value = 4
        assert service.snapshot().constraint_generation == 3


class TestReadOnIsHonoured:
    """Independent review M2 — ``read_on`` is CONSULTED, not merely validated by the loader."""

    def test_boot_only_reads_once_and_never_again(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, phase, generation, _date, _loaded, reads = _build(
            tmp_path, evidence_store, bands=[_band()], read_on='["boot"]'
        )

        assert reads.count == 1
        service.snapshot()
        assert reads.count == 1

        for step, next_phase in enumerate(("CLOSED", "REGULAR", "CLOSED"), start=2):
            phase.value = next_phase
            generation.value = step
            service.snapshot()

        assert reads.count == 1
        assert service.shape_constraints.price_max == _UPPER

    def test_phase_change_only_does_not_read_at_boot(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service, phase, generation, _date, _loaded, reads = _build(
            tmp_path, evidence_store, bands=[_band()], read_on='["phase_change"]'
        )
        assert reads.count == 0

        service.snapshot()

        assert reads.count == 0
        assert service.shape_constraints.price_max is None

        phase.value = "CLOSED"
        generation.value = 2
        service.snapshot()

        assert reads.count == 1
        assert service.shape_constraints.price_max == _UPPER

    def test_both_tokens_read_at_boot_and_on_each_phase_change(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The baseline the two tests above differ from — without it they would also pass"""
        service, phase, generation, _date, _loaded, reads = _build(
            tmp_path, evidence_store, bands=[_band()]
        )
        assert reads.count == 1

        service.snapshot()
        assert reads.count == 1
        phase.value = "CLOSED"
        generation.value = 2
        service.snapshot()

        assert reads.count == 2


class TestBandChangeIsANewGeneration:
    """ADR-002-019 §18 / plan §8 5 — a band change is a material change ⇒ new Constraint"""

    def test_a_same_phase_band_transition_takes_a_new_generation(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The clause-specific test (#838): same phase, same tick generation, band present →"""
        service, phase, generation, date_reader, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band()]
        )

        first = service.snapshot()
        date_reader.value = "20261012"
        second = service.snapshot()

        assert phase.value == "REGULAR" and generation.value == 1
        assert second.constraint_generation == first.constraint_generation + 1
        assert len(_rows(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND)) == 2

    def test_the_reissued_snapshot_binds_the_band_read_at_that_moment(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The phase change is what re-issues; this pins that the NEW snapshot carries the"""
        widened = _band(price_min=_LOWER - 200, price_max=_UPPER + 200)
        service, phase, generation, _date, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band(), widened]
        )

        first = service.snapshot()
        phase.value = "CLOSED"
        generation.value = 2
        second = service.snapshot()

        assert second.constraint_generation == first.constraint_generation + 1
        assert service.shape_constraints.price_max == _UPPER + 200
        assert second.critical_input_snapshot_digest == widened.record_digest

    def test_the_reissued_snapshot_binds_the_new_continuity_id(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """A token reissue produces the SAME band numbers under a NEW continuity id. The"""
        reissued = _band(continuity="boot-1:1")
        service, phase, generation, _date, _loaded, _reads = _build(
            tmp_path, evidence_store, bands=[_band(), reissued]
        )

        first = service.snapshot()
        phase.value = "CLOSED"
        generation.value = 2
        second = service.snapshot()

        assert second.constraint_generation == first.constraint_generation + 1
        assert second.source_continuity_id == "boot-1:1"


def _producer_journal_line(
    *, trading_date: str = _TRADING_DATE, **overrides: Any
) -> dict[str, Any]:
    """One ``cp3-band/1`` line carrying the measured ``A05610`` band."""
    line: dict[str, Any] = {
        "kind": "cp3-band/1",
        "source_id": "tos-cp3-live/0.1.0",
        "instrument": _INSTRUMENT,
        "trading_date": trading_date,
        "tr_id": "FHMIF10000000",
        "upper": PVL_A05610_UPPER,
        "lower": PVL_A05610_LOWER,
        "basis": PVL_A05610_BASIS,
        "raw_payload_digest": "d" * 64,
        "producer_continuity_id": "band-probe/1",
        "as_of_ms": 1_760_577_960_000,
    }
    line.update(overrides)
    return line


def _producer_journal_service(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    *,
    journal_bytes: bytes,
    band_sink: _Sink | None = None,
) -> VenueConstraintService:
    """A service whose band comes from a REAL :class:`ProducerJournalBandReader` over a"""
    journal = tmp_path / "band.jsonl"
    journal.write_bytes(journal_bytes)
    path = write_fixture_venue_policy(
        tmp_path,
        venue_policy_yaml(
            price_min="null",
            price_max="null",
            tick_size="2",
            min_quantity="1",
            max_quantity="10",
            runtime_extra=producer_journal_band_source_runtime_extra(
                instrument=_INSTRUMENT, band_journal_path=str(journal)
            ),
        ),
    )
    loaded = load_venue_constraint_policy(path, scheme=SCHEME)
    assert isinstance(loaded.band_source, ProducerJournalBandSource)
    reader = ProducerJournalBandReader(
        band_source=loaded.band_source,
        monotonic=_Monotonic(),
        evidence_sink=band_sink if band_sink is not None else _Sink(),
        trading_date_reader=lambda: _TRADING_DATE,
        tick_size=loaded.policy.shape_constraints.tick_size,
    )
    return VenueConstraintService(
        loaded_policy=loaded,
        scheme=SCHEME,
        session_phase_reader=_FakeReader("REGULAR"),
        tick_generation_reader=_FakeReader(1),
        evidence_store=evidence_store,
        environment_label="test-env",
        route_fields=InstrumentRouteFields(),
        broker_capability_profile_version=None,
        broker_capability_profile_digest=None,
        activated_member_digest="fixture-activation-digest",
        band_reader=reader.read,
        trading_date_reader=_FakeReader(_TRADING_DATE),
    )


class TestProducerJournalG2ReadSide:
    """2026-10-15 plan §3.4 G2 ② — the SERVICE half of the read-side trading-date clause."""

    def _service(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        *,
        line_trading_date: str,
        band_sink: _Sink | None = None,
    ) -> VenueConstraintService:
        return _producer_journal_service(
            tmp_path,
            evidence_store,
            journal_bytes=json.dumps(
                _producer_journal_line(trading_date=line_trading_date)
            ).encode("utf-8")
            + b"\n",
            band_sink=band_sink,
        )

    def test_todays_line_reaches_the_first_snapshot(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The baseline, without which the refusal below proves only "returns nothing"."""
        service = self._service(
            tmp_path, evidence_store, line_trading_date=_TRADING_DATE
        )

        snapshot = service.snapshot()

        assert snapshot.critical_input_snapshot_digest is not None
        assert snapshot.max_age == f"trading_date_kst:{_TRADING_DATE}"
        assert service.shape_constraints.price_max == _UPPER

    def test_a_line_from_another_trading_date_is_refused_by_the_reader_not_the_bond(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The clause-level assertion (class docstring): WHICH layer rejected the line."""
        sink = _Sink()
        self._service(
            tmp_path, evidence_store, line_trading_date="20261007", band_sink=sink
        )

        row = sink.only()

        assert row["outcome"] == "REFUSED"
        assert row["reason"] == "trading_date_mismatch"
        assert "20261007" in row["detail"]

    def test_a_line_from_another_trading_date_leaves_the_first_snapshot_bandless(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The COMPOUND (class docstring): whichever layer caught it, no band is in force."""
        service = self._service(tmp_path, evidence_store, line_trading_date="20261007")

        snapshot = service.snapshot()

        assert snapshot.critical_input_snapshot_digest is None
        assert snapshot.source_continuity_id is None
        assert snapshot.max_age is None
        assert service.shape_constraints.price_max is None


class TestProducerJournalFailsClosedIntoTheFirstSnapshot:
    """PR #907 review MEDIUM-1 / Codex medium — the SERVICE half of the three inputs that"""

    def _service(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore, *, tail: bytes
    ) -> VenueConstraintService:
        return _producer_journal_service(
            tmp_path, evidence_store, journal_bytes=tail + b"\n"
        )

    def test_todays_line_is_the_baseline(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Without this, "the band is absent" below would also be what a broken fixture"""
        service = self._service(
            tmp_path,
            evidence_store,
            tail=json.dumps(_producer_journal_line()).encode("utf-8"),
        )

        assert service.snapshot().critical_input_snapshot_digest is not None
        assert service.shape_constraints.price_max == _UPPER

    @pytest.mark.parametrize(
        "tail",
        [
            pytest.param(b"\xff\xfe", id="not_utf8"),
            pytest.param(b"[" * 100_000 + b"]" * 100_000, id="deeply_nested"),
            pytest.param(
                json.dumps(_producer_journal_line(upper="1e999999999")).encode("utf-8"),
                id="overflowing_bound",
            ),
        ],
    )
    def test_an_unusable_last_line_leaves_the_first_snapshot_bandless(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore, tail: bytes
    ) -> None:
        """``snapshot()`` RETURNS — it does not raise — and the band is absent."""
        service = self._service(tmp_path, evidence_store, tail=tail)

        snapshot = service.snapshot()

        assert snapshot.critical_input_snapshot_digest is None
        assert snapshot.source_continuity_id is None
        assert snapshot.max_age is None
        assert service.shape_constraints.price_max is None

    @pytest.mark.parametrize(
        "tail",
        [
            pytest.param(b"\xff\xfe", id="not_utf8"),
            pytest.param(b"[" * 100_000 + b"]" * 100_000, id="deeply_nested"),
            pytest.param(
                json.dumps(_producer_journal_line(upper="1e999999999")).encode("utf-8"),
                id="overflowing_bound",
            ),
        ],
    )
    def test_decide_answers_unknown_rather_than_dying(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore, tail: bytes
    ) -> None:
        """The verdict the kernel owes on an absent bound (``predicates.py``'s required-bound"""
        service = self._service(tmp_path, evidence_store, tail=tail)

        verdict = service.decide(
            action_class=ActionClass.NEW_LONG,
            shape=_shape(100_000),
            candidate_command=None,
        )

        assert verdict.result is OrderAdmissibilityResult.UNKNOWN


class TestProducerJournalNullProvenance:
    """PR #907 review MEDIUM-2 — "a band in force whose provenance reads exactly like no"""

    def test_a_line_with_null_provenance_leaves_the_first_snapshot_bandless(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        service = _producer_journal_service(
            tmp_path,
            evidence_store,
            journal_bytes=json.dumps(
                _producer_journal_line(
                    raw_payload_digest=None, producer_continuity_id=None
                )
            ).encode("utf-8")
            + b"\n",
        )

        snapshot = service.snapshot()

        assert service.shape_constraints.price_min is None
        assert service.shape_constraints.price_max is None
        assert snapshot.critical_input_snapshot_digest is None
        assert snapshot.source_continuity_id is None


class TestTheBandIsReadAtBoot:
    """Rescope plan M1 (``docs/plans/2026-10-22-tos-rescope-plan.md`` §3) — the band is"""

    def _sink_and_service(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore, *, tail: bytes
    ) -> tuple[_Sink, VenueConstraintService]:
        sink = _Sink()
        service = _producer_journal_service(
            tmp_path, evidence_store, journal_bytes=tail, band_sink=sink
        )
        return sink, service

    def test_a_valid_journal_lands_one_observed_row_with_no_snapshot_at_all(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        line = _producer_journal_line()
        sink, service = self._sink_and_service(
            tmp_path, evidence_store, tail=json.dumps(line).encode("utf-8") + b"\n"
        )

        row = sink.only()

        assert row["outcome"] == "OBSERVED"
        assert row["raw_payload_digest"] == line["raw_payload_digest"]
        assert (row["price_min"], row["price_max"]) == (_LOWER, _UPPER)
        assert row["trading_date"] == _TRADING_DATE
        assert service.shape_constraints.price_max == _UPPER
        assert _rows(evidence_store, VENUE_SNAPSHOT_ISSUED_KIND) == []

    @pytest.mark.parametrize(
        ("tail", "reason"),
        [
            pytest.param(b"", "journal_empty", id="empty_journal"),
            pytest.param(b"{not json\n", "line_unparseable", id="malformed_line"),
            pytest.param(
                json.dumps(_producer_journal_line(upper="not-a-number")).encode("utf-8")
                + b"\n",
                "non_integral_scale",
                id="unscalable_bound",
            ),
        ],
    )
    def test_an_unusable_line_lands_one_refused_row_naming_the_reason(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        tail: bytes,
        reason: str,
    ) -> None:
        sink, service = self._sink_and_service(tmp_path, evidence_store, tail=tail)

        row = sink.only()

        assert row["outcome"] == "REFUSED"
        assert row["reason"] == reason
        assert service.shape_constraints.price_max is None

    def test_an_absent_journal_lands_one_refused_row_too(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """Separate from the parametrization above because the journal file must NOT be"""
        sink = _Sink()
        path = write_fixture_venue_policy(
            tmp_path,
            venue_policy_yaml(
                price_min="null",
                price_max="null",
                tick_size="2",
                min_quantity="1",
                max_quantity="10",
                runtime_extra=producer_journal_band_source_runtime_extra(
                    instrument=_INSTRUMENT,
                    band_journal_path=str(tmp_path / "never-written.jsonl"),
                ),
            ),
        )
        loaded = load_venue_constraint_policy(path, scheme=SCHEME)
        assert isinstance(loaded.band_source, ProducerJournalBandSource)
        reader = ProducerJournalBandReader(
            band_source=loaded.band_source,
            monotonic=_Monotonic(),
            evidence_sink=sink,
            trading_date_reader=lambda: _TRADING_DATE,
            tick_size=loaded.policy.shape_constraints.tick_size,
        )

        VenueConstraintService(
            loaded_policy=loaded,
            scheme=SCHEME,
            session_phase_reader=_FakeReader("REGULAR"),
            tick_generation_reader=_FakeReader(1),
            evidence_store=evidence_store,
            environment_label="test-env",
            route_fields=InstrumentRouteFields(),
            broker_capability_profile_version=None,
            broker_capability_profile_digest=None,
            activated_member_digest="fixture-activation-digest",
            band_reader=reader.read,
            trading_date_reader=_FakeReader(_TRADING_DATE),
        )

        row = sink.only()

        assert row["outcome"] == "REFUSED"
        assert row["reason"] == "journal_absent"

    def test_the_first_snapshot_does_not_add_a_second_row_for_the_same_instant(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """One instant, one row. The boot read is ``__init__``'s; the first snapshot must not"""
        sink, service = self._sink_and_service(
            tmp_path,
            evidence_store,
            tail=json.dumps(_producer_journal_line()).encode("utf-8") + b"\n",
        )
        assert len(sink.rows) == 1

        snapshot = service.snapshot()

        assert len(sink.rows) == 1
        assert snapshot.critical_input_snapshot_digest is not None
        assert sink.only()["band_digest"] == snapshot.critical_input_snapshot_digest

    def test_a_clock_stale_boot_is_refused_and_then_retried_at_the_first_snapshot(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """⛔ The regression this wave could have shipped (independent review MEDIUM-1)."""
        journal = tmp_path / "band.jsonl"
        journal.write_bytes(
            json.dumps(_producer_journal_line()).encode("utf-8") + b"\n"
        )
        path = write_fixture_venue_policy(
            tmp_path,
            venue_policy_yaml(
                price_min="null",
                price_max="null",
                tick_size="2",
                min_quantity="1",
                max_quantity="10",
                runtime_extra=producer_journal_band_source_runtime_extra(
                    instrument=_INSTRUMENT, band_journal_path=str(journal)
                ),
            ),
        )
        loaded = load_venue_constraint_policy(path, scheme=SCHEME)
        assert isinstance(loaded.band_source, ProducerJournalBandSource), (
            "the fixture policy above declares `kind: producer_journal`, so the loader must "
            f"have produced that source — got {type(loaded.band_source).__name__}"
        )
        sink = _Sink()
        dates: list[str | None] = [None]
        reader = ProducerJournalBandReader(
            band_source=loaded.band_source,
            monotonic=_Monotonic(),
            evidence_sink=sink,
            trading_date_reader=lambda: dates.pop(0) if dates else _TRADING_DATE,
            tick_size=loaded.policy.shape_constraints.tick_size,
        )
        service = VenueConstraintService(
            loaded_policy=loaded,
            scheme=SCHEME,
            session_phase_reader=_FakeReader("REGULAR"),
            tick_generation_reader=_FakeReader(1),
            evidence_store=evidence_store,
            environment_label="test-env",
            route_fields=InstrumentRouteFields(),
            broker_capability_profile_version=None,
            broker_capability_profile_digest=None,
            activated_member_digest="fixture-activation-digest",
            band_reader=reader.read,
            trading_date_reader=_FakeReader(_TRADING_DATE),
        )

        assert [(k, f["outcome"], f.get("reason")) for k, f in sink.rows] == [
            ("VENUE_BAND_OBSERVED", "REFUSED", "trading_date_unavailable")
        ]
        assert service.shape_constraints.price_max is None

        snapshot = service.snapshot()

        assert [f["outcome"] for _, f in sink.rows] == ["REFUSED", "OBSERVED"]
        assert service.shape_constraints.price_max == _UPPER
        assert snapshot.critical_input_snapshot_digest is not None
        service.snapshot()
        assert [f["outcome"] for _, f in sink.rows] == ["REFUSED", "OBSERVED"]

    def test_a_boot_that_already_holds_a_band_is_not_owed_a_retry(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The flag's other half: the retry is reached ONLY when the boot read came back"""
        sink, service = self._sink_and_service(
            tmp_path,
            evidence_store,
            tail=json.dumps(_producer_journal_line()).encode("utf-8") + b"\n",
        )
        assert sink.only()["outcome"] == "OBSERVED"

        service.snapshot()
        service.snapshot()

        assert len(sink.rows) == 1

    def test_a_tree_that_declares_no_band_source_never_reads(
        self, tmp_path: Path, evidence_store: SqliteEvidenceStore
    ) -> None:
        """The resident ``paper`` tree and the SHORT tenant tree (band ``null``, plan §5): no"""
        service, phase, generation, _date, _loaded, reads = _build(
            tmp_path, evidence_store, declare_band_source=False, bands=[_band()]
        )
        assert reads.count == 0

        service.snapshot()
        phase.value = "CLOSED"
        generation.value = 2
        service.snapshot()

        assert reads.count == 0
        assert service.shape_constraints.price_max == 500
