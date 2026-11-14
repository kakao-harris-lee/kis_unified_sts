"""``ProducerJournalBandReader`` — CP-3 band 원천 경로 변경 PR-B"""

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

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "band_probe_line.jsonl"

_INSTRUMENT = "A05611"
_TRADING_DATE = "20261016"
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
    """The writer's own line with exactly the named leaves replaced."""
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
    """Write ``lines`` as a band journal. A ``str`` entry is written verbatim (that is how an"""
    path = tmp_path / name
    path.write_text(
        "".join(
            (entry if isinstance(entry, str) else json.dumps(entry)) + "\n"
            for entry in lines
        ),
        encoding="utf-8",
    )
    return path


_BAD_TAIL_REASONS: dict[str, str] = {
    "unparseable": "line_unparseable",
    "not_utf8": "journal_not_utf8",
    "deeply_nested": "line_too_deeply_nested",
    "overflowing_bound": "non_integral_scale",
}


def _bad_tail(key: str) -> bytes:
    """The raw BYTES of one unusable last line — bytes, because one of them is not text."""
    if key == "unparseable":
        return b"{not json"
    if key == "not_utf8":
        return b"\xff\xfe"
    if key == "deeply_nested":
        return (b"[" * 100_000) + (b"]" * 100_000)
    if key == "overflowing_bound":
        return json.dumps(_line(upper="1e999999999")).encode("utf-8")
    raise AssertionError(key)


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
        monotonic=_FakeMonotonic(),
        evidence_sink=evidence,
        trading_date_reader=lambda: trading_date,
        tick_size=tick_size,
    )
    return reader, evidence


class TestTheLineSchemaMatchesTheWriter:
    """Plan §3.3 — the runtime cannot import ``tools``, so the line's shape is defined twice."""

    def test_the_key_set_equals_the_writers_own_output(self) -> None:
        assert set(_writer_line()) == BAND_JOURNAL_LINE_KEYS

    def test_the_kind_token_equals_the_writers_own(self) -> None:
        assert _writer_line()["kind"] == BAND_JOURNAL_LINE_KIND


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
        """Plan §3.3 / review MEDIUM-1 — NOT re-stamped with ``trading_date_now()``."""
        line = _writer_line()
        reader, _ = _reader(_write(tmp_path, line))

        observation = reader.read()

        assert observation is not None
        assert observation.trading_date == line["trading_date"]

    def test_as_of_ms_is_the_runtimes_clock_and_the_lines_goes_to_evidence(
        self, tmp_path: Path
    ) -> None:
        """Two clocks, never mixed (plan §3.3). The line's ``as_of_ms`` is the PRODUCER's wall"""
        line = _writer_line()
        reader, sink = _reader(_write(tmp_path, line))

        observation = reader.read()

        assert observation is not None
        assert observation.as_of_ms != line["as_of_ms"]
        assert observation.as_of_ms == 1_001
        assert sink.only()["producer_as_of_ms"] == line["as_of_ms"]

    def test_the_digest_and_the_continuity_come_from_the_line_and_say_so(
        self, tmp_path: Path
    ) -> None:
        """Plan §3.3 — the digest is the producer's claim about bytes this process never saw,"""
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
        """A NECESSARY condition of the stage-1 formula, never a stage judgement (band plan"""
        reader, sink = _reader(_write(tmp_path, _writer_line()))

        observation = reader.read()

        assert observation is not None
        assert observation.symmetric_about_basis is True
        assert sink.only()["symmetric_about_basis"] is True


class TestTheLastLineOnly:
    """Plan §3.3 / review LOW-1."""

    def test_the_last_line_wins_over_an_earlier_one(self, tmp_path: Path) -> None:
        """A re-read line is appended, so "latest" is the one in force."""
        wider = _line(upper="1200.00", lower="950.00")
        reader, _ = _reader(_write(tmp_path, _writer_line(), wider))

        observation = reader.read()

        assert observation is not None
        assert (observation.price_min, observation.price_max) == (95000, 120000)

    @pytest.mark.parametrize("tail", sorted(_BAD_TAIL_REASONS))
    def test_an_invalid_last_line_does_NOT_fall_back_to_the_valid_one_before_it(
        self, tmp_path: Path, tail: str
    ) -> None:
        """**The red proof for "never a fallback."** The first line is the accepted baseline,"""
        path = tmp_path / "band.jsonl"
        path.write_bytes(
            json.dumps(_writer_line()).encode("utf-8") + b"\n" + _bad_tail(tail) + b"\n"
        )

        reader, sink = _reader(path)
        observation = reader.read()

        assert observation is None
        assert sink.only()["reason"] == _BAD_TAIL_REASONS[tail]

    def test_a_trailing_blank_line_is_not_the_last_line(self, tmp_path: Path) -> None:
        "``ObservationJournal`` terminates every row with ``\\n``, so the raw tail of a"
        path = tmp_path / "band.jsonl"
        path.write_text(json.dumps(_writer_line()) + "\n\n", encoding="utf-8")

        assert _reader(path)[0].read() is not None


class TestTheFileItself:
    """Plan §3.3 — absence, an unparseable tail and an I/O error are all band ``None`` plus a"""

    def test_an_absent_journal_is_a_named_refusal(self, tmp_path: Path) -> None:
        reader, sink = _reader(tmp_path / "never-written.jsonl")

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_absent"

    def test_an_empty_journal_is_a_named_refusal(self, tmp_path: Path) -> None:
        reader, sink = _reader(_write(tmp_path))

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_empty"

    def test_an_io_error_is_a_named_refusal_not_an_escape(self, tmp_path: Path) -> None:
        """A DIRECTORY at the journal's path: ``read_text`` raises ``IsADirectoryError``, an"""
        path = tmp_path / "band.jsonl"
        path.mkdir()

        reader, sink = _reader(path)

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_io_error"

    def test_a_non_utf8_journal_is_a_named_refusal_not_an_escape(
        self, tmp_path: Path
    ) -> None:
        """PR #907 review MEDIUM-1 — a byte no UTF-8 decoder accepts."""
        path = tmp_path / "band.jsonl"
        path.write_bytes(_bad_tail("not_utf8") + b"\n")

        reader, sink = _reader(path)

        assert reader.read() is None
        assert sink.only()["reason"] == "journal_not_utf8"

    def test_a_deeply_nested_tail_is_a_named_refusal_not_an_escape(
        self, tmp_path: Path
    ) -> None:
        """PR #907 review MEDIUM-1 — ``json.loads`` recurses per nesting level, so a tail of"""
        path = tmp_path / "band.jsonl"
        path.write_bytes(_bad_tail("deeply_nested") + b"\n")

        reader, sink = _reader(path)

        assert reader.read() is None
        assert sink.only()["reason"] == "line_too_deeply_nested"

    def test_a_json_scalar_tail_is_a_named_refusal(self, tmp_path: Path) -> None:
        """Valid JSON that is not an object — ``json.loads`` succeeds, so the parse check"""
        reader, sink = _reader(_write(tmp_path, "42"))

        assert reader.read() is None
        assert sink.only()["reason"] == "line_not_a_mapping"

    def test_an_unavailable_trading_date_refuses_before_the_file_is_opened(
        self, tmp_path: Path
    ) -> None:
        """A band that cannot be bound to a date cannot be invalidated when the date turns, so"""
        reader, sink = _reader(_write(tmp_path, _writer_line()), trading_date=None)

        assert reader.read() is None
        assert sink.only()["reason"] == "trading_date_unavailable"


class TestTheLineShape:
    """``kind`` and the key set — the two clauses that run before anything is read OUT of the"""

    def test_another_line_kind_is_refused(self, tmp_path: Path) -> None:
        """A future ``cp3-band/2``, or a price line that wandered into this file: the keys"""
        reader, sink = _reader(_write(tmp_path, _line(kind="cp3-band/2")))

        assert reader.read() is None
        assert sink.only()["reason"] == "line_kind_unknown"

    def test_a_line_missing_one_key_is_refused(self, tmp_path: Path) -> None:
        """**The concrete input**: a line claiming ``cp3-band/1`` without"""
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
        """``as_of_ms`` lands in an evidence row as an integer; a string there would be"""
        reader, sink = _reader(_write(tmp_path, _line(as_of_ms="1760577960000")))

        assert reader.read() is None
        assert sink.only()["reason"] == "producer_as_of_ms_not_an_int"


class TestTheProvenanceValues:
    """PR #907 review MEDIUM-2 — a PRESENT key is not a USABLE value."""

    @pytest.mark.parametrize(
        "digest",
        [
            pytest.param(None, id="null"),
            pytest.param("", id="empty"),
            pytest.param(
                "1C5B08AA0B75883E77D0DDBBE56989BC58A41FD52B1701286B40B101C73E4AA1",
                id="uppercase",
            ),
            pytest.param("1c5b08aa", id="too_short"),
            pytest.param("z" * 64, id="not_hex"),
            pytest.param(1234, id="not_a_string"),
        ],
    )
    def test_a_raw_payload_digest_that_is_not_sha256_hex_is_refused(
        self, tmp_path: Path, digest: Any
    ) -> None:
        """The field is this band's ``critical_input_snapshot_digest`` stand-in, so "it is a"""
        reader, sink = _reader(_write(tmp_path, _line(raw_payload_digest=digest)))

        assert reader.read() is None
        assert sink.only()["reason"] == "raw_payload_digest_not_a_sha256_hex"

    @pytest.mark.parametrize(
        "continuity",
        [
            pytest.param(None, id="null"),
            pytest.param("", id="empty"),
            pytest.param(31337, id="not_a_string"),
        ],
    )
    def test_a_blank_producer_continuity_id_is_refused(
        self, tmp_path: Path, continuity: Any
    ) -> None:
        """``source_continuity_id`` is ``None`` on a snapshot that has no band, so a band"""
        reader, sink = _reader(
            _write(tmp_path, _line(producer_continuity_id=continuity))
        )

        assert reader.read() is None
        assert sink.only()["reason"] == "producer_continuity_id_not_a_nonempty_string"


class TestG2TradingDateReadSide:
    """Plan §3.4 G2 ② — a D-dated line read by a D+1 runtime."""

    def test_a_line_from_another_trading_date_is_refused(self, tmp_path: Path) -> None:
        """Only ``trading_date`` differs from the accepted line: yesterday's, left in a reused"""
        reader, sink = _reader(_write(tmp_path, _line(trading_date="20261015")))

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "trading_date_mismatch"
        assert "20261015" in row["detail"]


class TestG3ContractReadSide:
    """Plan §3.4 G3 — a roll-day session directory reused across contracts."""

    def test_a_line_for_another_contract_is_refused(self, tmp_path: Path) -> None:
        """**Only ``instrument`` differs** — date and source stay valid, and the band values"""
        reader, sink = _reader(_write(tmp_path, _line(instrument="A05610")))

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "instrument_mismatch"
        assert "A05610" in row["detail"]

    def test_the_other_contracts_own_band_would_otherwise_be_admissible(
        self, tmp_path: Path
    ) -> None:
        """The other half of the same input, measured: an ``A05610`` line whose POLICY is also"""
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
    """Plan §3.4 C1 — a CONFIG-CONSISTENCY rule, deliberately not counted as a guard."""

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
        """``tos-cp3-live-EVIL`` is not ``tos-cp3-live``. A bare ``startswith`` would approve"""
        reader, sink = _reader(_write(tmp_path, _line(source_id="tos-cp3-live-EVIL/9")))

        assert reader.read() is None
        assert sink.only()["reason"] == "source_id_unapproved"

    def test_the_bare_prefix_with_no_version_is_approved(self, tmp_path: Path) -> None:
        """The other side of the delimiter rule: an exact match needs no slash."""
        reader, _ = _reader(_write(tmp_path, _line(source_id="tos-cp3-live")))

        assert reader.read() is not None


class TestG1ValidationSetIsReused:
    """Plan §3.4 G1 — "기존 그대로 — 변환이 런타임에 있으므로 재사용"."""

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

    def test_a_bound_whose_scaled_form_overflows_is_refused(
        self, tmp_path: Path
    ) -> None:
        """PR #907 review MEDIUM-1 — ``"1e999999999"``."""
        path = tmp_path / "band.jsonl"
        path.write_bytes(_bad_tail("overflowing_bound") + b"\n")

        reader, sink = _reader(path)

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
        """Why the tick 5→2 correction is a PRECONDITION of enabling, in code: the measured"""
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
    """Whatever went wrong, the row says WHICH contract's band is now ``UNKNOWN`` — an"""
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
