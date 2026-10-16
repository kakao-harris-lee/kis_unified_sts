"""``ProducerJournalBandReader`` — CP-3 band 원천 경로 변경 PR-B
(``docs/plans/2026-10-15-tos-cp3-band-via-producer-plan.md`` §3.2/§3.3/§3.4).

**One test per CLAUSE** (#838): every input below differs from the line this reader ACCEPTS in
exactly ONE respect, and :meth:`TestTheMeasuredLineIsAccepted` pins that baseline. Without the
baseline a clause test proves only "this returns ``None``", which a broken fixture also
satisfies.

**The accepted line is not written here — it is PR-A's writer's own output.**
``fixtures/band_probe_line.jsonl`` was produced by driving
``tools.tos_cp3.live_producer.sinks.ObservationJournal`` with
``band_line.BAND_KEY_ORDER`` exactly as ``band_probe._publish`` does, over a
``FHMIF10000000``-shaped body carrying the 2026-10-08 P-VL ``A05611`` measurement
(990.48/1162.72, basis 1076.60). The runtime may not import ``tools`` (firewall R1), so
:meth:`TestTheLineSchemaMatchesTheWriter` compares this package's own
:data:`~tos_runtime.venue.band_journal.BAND_JOURNAL_LINE_KEYS` against that file's keys — which
is what makes "the two definitions are the same shape" a MEASUREMENT rather than two files that
happen to agree today.

Hermetic (``tos/runtime/tests/conftest.py`` D1.4): no socket is ever opened — this reader has
none to open, which is the point of the path (plan §3.5). Every file it reads is under
``tmp_path`` or is the committed fixture, read-only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.venue.band_journal import (
    BAND_JOURNAL_LINE_KEYS,
    BAND_JOURNAL_LINE_KIND,
    ProducerJournalBandReader,
    ProducerJournalBandSource,
)
from tos_runtime.venue.band_source import VENUE_BAND_OBSERVED_KIND

#: PR-A's writer output, byte-for-byte (module docstring).
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "band_probe_line.jsonl"

_INSTRUMENT = "A05611"
_TRADING_DATE = "20261016"
#: ``990.48 × 100`` and ``1162.72 × 100`` — the exact scaled ints the measured band becomes.
_SCALED_LOWER = 99048
_SCALED_UPPER = 116272
_SCALED_BASIS = 107660
_APPROVED = ("tos-cp3-live",)


def _writer_line() -> dict[str, Any]:
    """The fixture's single line, parsed."""
    text = _FIXTURE.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 1, lines
    parsed = json.loads(lines[0])
    assert isinstance(parsed, dict)
    return parsed


def _line(**overrides: Any) -> dict[str, Any]:
    """The writer's own line with exactly the named leaves replaced.

    Built FROM the fixture rather than typed out again: a clause test that varied one leaf of a
    hand-written baseline would stop being "one respect different from what the producer
    writes" the moment the writer changed.
    """
    line = _writer_line()
    line.update(overrides)
    return line


class _FakeMonotonic:
    def __init__(self) -> None:
        self._now = 1_000

    def now_ms(self) -> int:
        self._now += 1
        return self._now


class _Sink:
    def __init__(self) -> None:
        self.rows: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.rows.append((kind, dict(fields)))

    def only(self) -> dict[str, Any]:
        assert len(self.rows) == 1, self.rows
        kind, fields = self.rows[0]
        assert kind == VENUE_BAND_OBSERVED_KIND
        return fields


def _band_source(path: Path, **overrides: Any) -> ProducerJournalBandSource:
    base: dict[str, Any] = {
        "kind": "producer_journal",
        "instrument": _INSTRUMENT,
        "price_scale": 100,
        "bound": "trading_date_kst",
        "read_on": ("boot", "phase_change"),
        "failure": "unknown",
        "band_journal_path": str(path),
        "approved_source_prefixes": _APPROVED,
    }
    base.update(overrides)
    return ProducerJournalBandSource(**base)


def _write(tmp_path: Path, *lines: Any, name: str = "band.jsonl") -> Path:
    """Write ``lines`` as a band journal. A ``str`` entry is written verbatim (that is how an
    unparseable tail is produced); anything else is JSON-encoded."""
    path = tmp_path / name
    path.write_text(
        "".join(
            (entry if isinstance(entry, str) else json.dumps(entry)) + "\n"
            for entry in lines
        ),
        encoding="utf-8",
    )
    return path


def _reader(
    path: Path,
    *,
    tick_size: int | None = 2,
    trading_date: str | None = _TRADING_DATE,
    sink: _Sink | None = None,
    **source_overrides: Any,
) -> tuple[ProducerJournalBandReader, _Sink]:
    evidence = sink if sink is not None else _Sink()
    reader = ProducerJournalBandReader(
        band_source=_band_source(path, **source_overrides),
        # `MonotonicSource` is a Protocol, so the double satisfies it structurally and mypy
        # checks that here.
        monotonic=_FakeMonotonic(),
        evidence_sink=evidence,
        trading_date_reader=lambda: trading_date,
        tick_size=tick_size,
    )
    return reader, evidence


# ---------------------------------------------------------------------------
# The schema pin — the duplication firewall R1 forces, measured
# ---------------------------------------------------------------------------


class TestTheLineSchemaMatchesTheWriter:
    """Plan §3.3 — the runtime cannot import ``tools``, so the line's shape is defined twice.

    These two assertions are what keeps the second definition honest. Delete them and a key
    added to ``band_line.BAND_KEY_ORDER`` lands in a file this reader then rejects with
    ``line_key_set`` — a band permanently absent for a reason that reads like a corrupted
    journal.
    """

    def test_the_key_set_equals_the_writers_own_output(self) -> None:
        assert set(_writer_line()) == BAND_JOURNAL_LINE_KEYS

    def test_the_kind_token_equals_the_writers_own(self) -> None:
        assert _writer_line()["kind"] == BAND_JOURNAL_LINE_KIND


# ---------------------------------------------------------------------------
# The baseline
# ---------------------------------------------------------------------------


class TestTheMeasuredLineIsAccepted:
    """The writer's own line, read by the reader the policy would wire."""

    def test_the_band_is_the_exactly_scaled_measurement(self, tmp_path: Path) -> None:
        reader, sink = _reader(_write(tmp_path, _writer_line()))

        observation = reader.read()

        assert observation is not None
        assert (observation.price_min, observation.price_max) == (
            _SCALED_LOWER,
            _SCALED_UPPER,
        )
        assert observation.basis == _SCALED_BASIS
        assert observation.instrument == _INSTRUMENT
        assert sink.only()["outcome"] == "OBSERVED"

    def test_the_trading_date_is_the_lines_own_stamp(self, tmp_path: Path) -> None:
        """Plan §3.3 / review MEDIUM-1 — NOT re-stamped with ``trading_date_now()``.

        ⚠ **This assertion does not discriminate, and says so rather than pretending.** Past
        the G2 clause the line's stamp and the runtime's reading are EQUAL, so
        ``trading_date=trading_date`` passes it too — measured 2026-10-16: that single
        mutation is GREEN across the whole suite. Writing it as if it were a red proof would
        be the "guard that admits what it names" shape this repo keeps rediscovering.

        What the expression actually is: the INPUT to a SECOND layer, whose own red proof is
        :class:`~tests.venue.test_service_band.TestTradingDateBond`. The layering is measured
        as a compound (2026-10-16), against one input — a D-1 line read by a D runtime, the
        clock staying at D:

        ====================================  ==========================================
        world                                 result
        ====================================  ==========================================
        shipped                               refused at the first snapshot
        read-side clause deleted              accepted, then DROPPED by the service bond
        read-side clause deleted + restamped  accepted and NEVER dropped — the D-1 band
                                              stays in force all session (price_max 115918)
        ====================================  ==========================================

        So this test pins the VALUE, and the table above is why the value matters.
        """
        line = _writer_line()
        reader, _ = _reader(_write(tmp_path, line))

        observation = reader.read()

        assert observation is not None
        assert observation.trading_date == line["trading_date"]

    def test_as_of_ms_is_the_runtimes_clock_and_the_lines_goes_to_evidence(
        self, tmp_path: Path
    ) -> None:
        """Two clocks, never mixed (plan §3.3). The line's ``as_of_ms`` is the PRODUCER's wall
        clock in a different process; the observation's is this runtime's monotonic reading,
        the same rule the ``kis_quote_get`` reader applies to its own request instant.
        """
        line = _writer_line()
        reader, sink = _reader(_write(tmp_path, line))

        observation = reader.read()

        assert observation is not None
        assert observation.as_of_ms != line["as_of_ms"]
        assert observation.as_of_ms == 1_001  # the double's first reading
        assert sink.only()["producer_as_of_ms"] == line["as_of_ms"]

    def test_the_digest_and_the_continuity_come_from_the_line_and_say_so(
        self, tmp_path: Path
    ) -> None:
        """Plan §3.3 — the digest is the producer's claim about bytes this process never saw,
        and the evidence row records whose it is rather than letting a reader assume the
        runtime hashed a response itself."""
        line = _writer_line()
        reader, sink = _reader(_write(tmp_path, line))

        observation = reader.read()

        assert observation is not None
        assert observation.raw_payload_digest == line["raw_payload_digest"]
        assert observation.source_continuity_id == line["producer_continuity_id"]
        row = sink.only()
        assert row["raw_payload_digest"] == line["raw_payload_digest"]
        assert row["raw_payload_digest_source"] == "producer"
        assert row["producer_source_id"] == line["source_id"]

    def test_the_measured_band_is_symmetric_about_its_basis(
        self, tmp_path: Path
    ) -> None:
        """A NECESSARY condition of the stage-1 formula, never a stage judgement (band plan
        2026-10-08 §4.5's implementation-time correction)."""
        reader, sink = _reader(_write(tmp_path, _writer_line()))

        observation = reader.read()

        assert observation is not None
        assert observation.symmetric_about_basis is True
        assert sink.only()["symmetric_about_basis"] is True


# ---------------------------------------------------------------------------
# The last line, and never a fallback
# ---------------------------------------------------------------------------


class TestTheLastLineOnly:
    """Plan §3.3 / review LOW-1."""

    def test_the_last_line_wins_over_an_earlier_one(self, tmp_path: Path) -> None:
        """A re-read line is appended, so "latest" is the one in force."""
        wider = _line(upper="1200.00", lower="950.00")
        reader, _ = _reader(_write(tmp_path, _writer_line(), wider))

        observation = reader.read()

        assert observation is not None
        assert (observation.price_min, observation.price_max) == (95000, 120000)

    def test_an_invalid_last_line_does_NOT_fall_back_to_the_valid_one_before_it(
        self, tmp_path: Path
    ) -> None:
        """**The red proof for "never a fallback."** The first line is the accepted baseline,
        so a reader that fell back would return a band and this test would see one. It must see
        ``None``: falling back believes "a band that was once valid" instead of "the band that
        is valid now", and on a reused session directory the line before is yesterday's.
        """
        path = _write(tmp_path, _writer_line(), "{not json")

        reader, sink = _reader(path)
        observation = reader.read()

        assert observation is None
        assert sink.only()["reason"] == "line_unparseable"

    def test_a_trailing_blank_line_is_not_the_last_line(self, tmp_path: Path) -> None:
        """``ObservationJournal`` terminates every row with ``\\n``, so the raw tail of a
        correct file is empty. Treating that as the last line would make EVERY well-written
        journal unreadable."""
        path = tmp_path / "band.jsonl"
        path.write_text(json.dumps(_writer_line()) + "\n\n", encoding="utf-8")

        assert _reader(path)[0].read() is not None


class TestTheFileItself:
    """Plan §3.3 — absence, an unparseable tail and an I/O error are all band ``None`` plus a
    reason (band plan 2026-10-08 §4.6: every failure is ``UNKNOWN`` ⇒ 송신 0)."""

    def test_an_absent_journal_is_a_named_refusal(self, tmp_path: Path) -> None:
        reader, sink = _reader(tmp_path / "never-written.jsonl")

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_absent"

    def test_an_empty_journal_is_a_named_refusal(self, tmp_path: Path) -> None:
        reader, sink = _reader(_write(tmp_path))

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_empty"

    def test_an_io_error_is_a_named_refusal_not_an_escape(self, tmp_path: Path) -> None:
        """A DIRECTORY at the journal's path: ``read_text`` raises ``IsADirectoryError``, an
        ``OSError`` that is not ``FileNotFoundError``. Without the catch it would leave
        ``read()`` and surface inside ``snapshot()``/``decide()``."""
        path = tmp_path / "band.jsonl"
        path.mkdir()

        reader, sink = _reader(path)

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_io_error"

    def test_a_json_scalar_tail_is_a_named_refusal(self, tmp_path: Path) -> None:
        """Valid JSON that is not an object — ``json.loads`` succeeds, so the parse check
        alone would pass it to the field reads."""
        reader, sink = _reader(_write(tmp_path, "42"))

        assert reader.read() is None
        assert sink.only()["reason"] == "line_not_a_mapping"

    def test_an_unavailable_trading_date_refuses_before_the_file_is_opened(
        self, tmp_path: Path
    ) -> None:
        """A band that cannot be bound to a date cannot be invalidated when the date turns, so
        it is refused outright rather than stamped with a guess. The journal here is the
        ACCEPTED one, so only the missing date can be the reason."""
        reader, sink = _reader(_write(tmp_path, _writer_line()), trading_date=None)

        assert reader.read() is None
        assert sink.only()["reason"] == "trading_date_unavailable"


class TestTheLineShape:
    """``kind`` and the key set — the two clauses that run before anything is read OUT of the
    line."""

    def test_another_line_kind_is_refused(self, tmp_path: Path) -> None:
        """A future ``cp3-band/2``, or a price line that wandered into this file: the keys
        would not mean what this reader thinks they mean."""
        reader, sink = _reader(_write(tmp_path, _line(kind="cp3-band/2")))

        assert reader.read() is None
        assert sink.only()["reason"] == "line_kind_unknown"

    def test_a_line_missing_one_key_is_refused(self, tmp_path: Path) -> None:
        """**The concrete input**: a line claiming ``cp3-band/1`` without
        ``raw_payload_digest``. Without the key-set clause the observation would carry ``None``
        there, and the snapshot's ``critical_input_snapshot_digest`` stand-in would read
        exactly like "no band at all" for a band that IS in force.
        """
        line = _writer_line()
        del line["raw_payload_digest"]

        reader, sink = _reader(_write(tmp_path, line))

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "line_key_set"
        assert "raw_payload_digest" in row["detail"]

    def test_a_line_with_an_extra_key_is_refused(self, tmp_path: Path) -> None:
        reader, sink = _reader(_write(tmp_path, _line(stage_hint="1")))

        assert reader.read() is None
        assert sink.only()["reason"] == "line_key_set"

    def test_a_non_integer_producer_stamp_is_refused(self, tmp_path: Path) -> None:
        """``as_of_ms`` lands in an evidence row as an integer; a string there would be
        recorded as one and silently compared against nothing."""
        reader, sink = _reader(_write(tmp_path, _line(as_of_ms="1760577960000")))

        assert reader.read() is None
        assert sink.only()["reason"] == "producer_as_of_ms_not_an_int"


# ---------------------------------------------------------------------------
# G2 / G3 / C1 — the read-side clauses, each varying exactly one leaf
# ---------------------------------------------------------------------------


class TestG2TradingDateReadSide:
    """Plan §3.4 G2 ② — a D-dated line read by a D+1 runtime.

    ⚠ **The red proof is HERE and in the first snapshot, deliberately not in a two-snapshot
    integration test** (plan §3.4's 가려진 절 note). ``VenueConstraintService.snapshot`` runs
    its own trading-date bond at the head of every call, so deleting this clause still leaves
    the SECOND snapshot dropping the band — a two-call test cannot tell the two layers apart.
    The service-level half is
    ``tests/venue/test_service_band.py::TestProducerJournalG2ReadSide``.
    """

    def test_a_line_from_another_trading_date_is_refused(self, tmp_path: Path) -> None:
        """Only ``trading_date`` differs from the accepted line: yesterday's, left in a reused
        session directory. The producer's own ``refuse_if_journal_exists`` is the structural
        half; this is the read-side layer."""
        reader, sink = _reader(_write(tmp_path, _line(trading_date="20261015")))

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "trading_date_mismatch"
        assert "20261015" in row["detail"]


class TestG3ContractReadSide:
    """Plan §3.4 G3 — a roll-day session directory reused across contracts."""

    def test_a_line_for_another_contract_is_refused(self, tmp_path: Path) -> None:
        """**Only ``instrument`` differs** — date and source stay valid, and the band values
        stay the ones the broker really returned for THAT contract. Both measured bands pass
        every §4.2 clause (``A05610`` 987.46/1159.18 vs ``A05611`` 990.48/1162.72, P-VL
        2026-10-08), so without this clause the session trades admissibly against another
        contract's band and nothing anywhere says so.
        """
        reader, sink = _reader(_write(tmp_path, _line(instrument="A05610")))

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "instrument_mismatch"
        assert "A05610" in row["detail"]

    def test_the_other_contracts_own_band_would_otherwise_be_admissible(
        self, tmp_path: Path
    ) -> None:
        """The other half of the same input, measured: an ``A05610`` line whose POLICY is also
        ``A05610`` is accepted and yields 98746/115918 — so the refusal above is about the
        contract bond and not about those numbers being unusable.

        Without it the pair would prove nothing: "returns ``None``" is also what a line this
        reader simply cannot parse does.
        """
        reader, _ = _reader(
            _write(
                tmp_path, _line(instrument="A05610", upper="1159.18", lower="987.46")
            ),
            instrument="A05610",
        )

        observation = reader.read()

        assert observation is not None
        assert (observation.price_min, observation.price_max) == (98746, 115918)


class TestC1SourcePrefix:
    """Plan §3.4 C1 — a CONFIG-CONSISTENCY rule, deliberately not counted as a guard.

    No concrete fail-open input can be written for it: one tool writes this file today and a
    hand-written line can copy the prefix. It stays because a line from an unapproved writer is
    an operations error on its face, and because the day a second writer exists (a synthetic
    band harness) it is promoted to a guard with a real input.
    """

    def test_an_unapproved_source_id_is_refused(self, tmp_path: Path) -> None:
        """Only ``source_id`` differs — the date and the contract stay valid."""
        reader, sink = _reader(
            _write(tmp_path, _line(source_id="tos-paper-bootproof-render/0.1.0"))
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "source_id_unapproved"
        assert "tos-paper-bootproof-render" in row["detail"]

    def test_the_prefix_match_requires_a_delimiter(self, tmp_path: Path) -> None:
        """``tos-cp3-live-EVIL`` is not ``tos-cp3-live``. A bare ``startswith`` would approve
        it — a producer name is a namespace, and the separator is what makes the boundary real
        (the same rule ``tools/tos_cp3/bootproof_guard.py::_matches_prefix`` states)."""
        reader, sink = _reader(_write(tmp_path, _line(source_id="tos-cp3-live-EVIL/9")))

        assert reader.read() is None
        assert sink.only()["reason"] == "source_id_unapproved"

    def test_the_bare_prefix_with_no_version_is_approved(self, tmp_path: Path) -> None:
        """The other side of the delimiter rule: an exact match needs no slash."""
        reader, _ = _reader(_write(tmp_path, _line(source_id="tos-cp3-live")))

        assert reader.read() is not None


# ---------------------------------------------------------------------------
# G1 — the shared validation set, reached through this reader
# ---------------------------------------------------------------------------


class TestG1ValidationSetIsReused:
    """Plan §3.4 G1 — "기존 그대로 — 변환이 런타임에 있으므로 재사용".

    The clauses themselves have their own per-clause tests against the ``kis_quote_get`` reader
    (``test_band_source.py::TestValidationSet``) and the function is shared
    (:func:`~tos_runtime.venue.band_source.validate_band_values`). What these pin is that this
    reader REACHES it — with the line's own strings and the policy's own scale and tick.
    """

    def test_an_off_grid_bound_is_refused(self, tmp_path: Path) -> None:
        """Plan §3.4's own example: ``upper: "1162.73"`` is off the 0.02 grid."""
        reader, sink = _reader(_write(tmp_path, _line(upper="1162.73")))

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "off_tick_grid"
        assert "116273" in row["detail"]

    def test_a_bound_that_does_not_scale_exactly_is_refused(
        self, tmp_path: Path
    ) -> None:
        """Three decimals under ``price_scale: 100``. Never rounded."""
        reader, sink = _reader(_write(tmp_path, _line(upper="1162.725")))

        assert reader.read() is None
        assert sink.only()["reason"] == "non_integral_scale"

    def test_an_unordered_band_is_refused(self, tmp_path: Path) -> None:
        reader, sink = _reader(_write(tmp_path, _line(upper="990.48", lower="1162.72")))

        assert reader.read() is None
        assert sink.only()["reason"] == "band_not_ordered"

    def test_an_absent_tick_size_refuses_every_read(self, tmp_path: Path) -> None:
        reader, sink = _reader(_write(tmp_path, _writer_line()), tick_size=None)

        assert reader.read() is None
        assert sink.only()["reason"] == "tick_size_absent"

    def test_a_tick_five_tree_is_caught_here(self, tmp_path: Path) -> None:
        """Why the tick 5→2 correction is a PRECONDITION of enabling, in code: the measured
        band is on the 0.02 grid, so a tree still carrying ``tick_size: 5`` rejects it.
        """
        reader, sink = _reader(_write(tmp_path, _writer_line()), tick_size=5)

        assert reader.read() is None
        assert sink.only()["reason"] == "off_tick_grid"

    def test_an_unusable_basis_leaves_the_field_unknown_without_dropping_the_band(
        self, tmp_path: Path
    ) -> None:
        """Basis is EVIDENCE, never admissibility (band plan 2026-10-08 §4.2/§4.5)."""
        reader, sink = _reader(_write(tmp_path, _line(basis="not-a-number")))

        observation = reader.read()

        assert observation is not None
        assert observation.basis is None
        assert observation.symmetric_about_basis is None
        assert sink.only()["symmetric_about_basis"] is None


class TestNarrowedIntraday:
    """Band plan 2026-10-08 §4.5 / §2's 단서 — recorded, never acted on."""

    def test_a_same_day_narrowing_is_flagged(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _writer_line())
        reader, sink = _reader(path)
        assert reader.read() is not None

        _write(tmp_path, _line(upper="1100.00", lower="1000.00"))
        observation = reader.read()

        assert observation is not None
        assert sink.rows[-1][1]["narrowed_intraday"] is True

    def test_a_same_day_widening_is_not_flagged(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _writer_line())
        reader, sink = _reader(path)
        assert reader.read() is not None

        _write(tmp_path, _line(upper="1200.00", lower="950.00"))
        assert reader.read() is not None

        assert sink.rows[-1][1]["narrowed_intraday"] is False


@pytest.mark.parametrize(
    "reason_key",
    ["journal_absent", "journal_empty", "line_unparseable", "line_kind_unknown"],
)
def test_every_refusal_row_names_the_policy_instrument(
    tmp_path: Path, reason_key: str
) -> None:
    """Whatever went wrong, the row says WHICH contract's band is now ``UNKNOWN`` — an
    evidence row that only said "refused" would not let an operator tell a tenant's band
    outage from a neighbouring session's."""
    writers = {
        "journal_absent": lambda: tmp_path / "missing.jsonl",
        "journal_empty": lambda: _write(tmp_path),
        "line_unparseable": lambda: _write(tmp_path, "{"),
        "line_kind_unknown": lambda: _write(tmp_path, _line(kind="other")),
    }
    reader, sink = _reader(writers[reason_key]())

    assert reader.read() is None
    row = sink.only()
    assert row["reason"] == reason_key
    assert row["instrument"] == _INSTRUMENT
