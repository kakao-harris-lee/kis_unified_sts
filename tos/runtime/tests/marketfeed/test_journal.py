"""Hermetic tests for tos_runtime.marketfeed.journal (TOS 틱 원천 웨이브 §2 decision 4, lane C).

D1.4 hermetic: every write goes through ``tmp_path`` (the suite's own autouse write guard,
``tos/runtime/tests/conftest.py``, refuses anything else); no network, no ambient env.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal
from tos_runtime.marketfeed.ports import RawObservation

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


def _write_lines(path: Path, lines: list[object]) -> None:
    """Write ``lines`` as JSON Lines — a ``str`` line is written verbatim (for malformed-input
    tests), any other object is ``json.dumps``-ed first."""
    rendered = [line if isinstance(line, str) else json.dumps(line) for line in lines]
    path.write_text("\n".join(rendered) + "\n", encoding="utf-8")


def _observation(
    *,
    raw_event_id: str = "evt-1",
    instrument: str = "005930",
    as_of_ms: int = 1_700_000_000_000,
    fields: dict[str, object] | None = None,
    source_id: str = "kis-mock",
    received_ms: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "raw_event_id": raw_event_id,
        "instrument": instrument,
        "as_of_ms": as_of_ms,
        "fields": fields if fields is not None else {"close": 4512500},
        "source_id": source_id,
    }
    if received_ms is not None:
        payload["received_ms"] = received_ms
    return payload


# ----------------------------------------------------------------------------
# missing file
# ----------------------------------------------------------------------------


def test_missing_file_is_a_typed_refusal_not_an_empty_poll(tmp_path: Path) -> None:
    journal = JsonLinesObservationJournal(path=tmp_path / "does-not-exist.jsonl")
    with pytest.raises(JournalError, match="does not exist"):
        journal.poll(instrument="005930", after_as_of_ms=None)


# ----------------------------------------------------------------------------
# strictly-newer filter
# ----------------------------------------------------------------------------


def test_after_as_of_ms_is_strictly_newer_not_gte(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(raw_event_id="e-equal", as_of_ms=1000),
            _observation(raw_event_id="e-newer", as_of_ms=1001),
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=1000)

    assert [o.raw_event_id for o in result] == ["e-newer"]


def test_after_as_of_ms_none_returns_everything(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(raw_event_id="e-1", as_of_ms=1000),
            _observation(raw_event_id="e-2", as_of_ms=2000),
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert [o.raw_event_id for o in result] == ["e-1", "e-2"]


def test_no_new_observations_is_an_empty_sequence_not_a_refusal(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(path, [_observation(raw_event_id="e-1", as_of_ms=1000)])
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=1000)

    assert result == ()


# ----------------------------------------------------------------------------
# instrument filter
# ----------------------------------------------------------------------------


def test_instrument_filter_excludes_other_instruments(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(raw_event_id="e-samsung", instrument="005930", as_of_ms=1000),
            _observation(raw_event_id="e-sk", instrument="000660", as_of_ms=1000),
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert [o.raw_event_id for o in result] == ["e-samsung"]


# ----------------------------------------------------------------------------
# ordering
# ----------------------------------------------------------------------------


def test_result_is_ordered_oldest_first_regardless_of_file_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(raw_event_id="e-late", as_of_ms=3000),
            _observation(raw_event_id="e-early", as_of_ms=1000),
            _observation(raw_event_id="e-mid", as_of_ms=2000),
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert [o.raw_event_id for o in result] == ["e-early", "e-mid", "e-late"]


# ----------------------------------------------------------------------------
# malformed input — fail-closed on the WHOLE poll, never a partial skip
# ----------------------------------------------------------------------------


def test_invalid_json_line_refuses_the_whole_poll(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(path, [_observation(raw_event_id="e-1"), "{not valid json"])
    journal = JsonLinesObservationJournal(path=path)

    with pytest.raises(JournalError, match=r"journal\.jsonl:2.*not valid JSON"):
        journal.poll(instrument="005930", after_as_of_ms=None)


def test_missing_required_key_refuses_the_whole_poll(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    bad = _observation()
    del bad["source_id"]
    _write_lines(path, [bad])
    journal = JsonLinesObservationJournal(path=path)

    with pytest.raises(JournalError, match="missing required key"):
        journal.poll(instrument="005930", after_as_of_ms=None)


def test_non_scalar_field_value_refuses_the_whole_poll(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(path, [_observation(fields={"close": {"nested": "object"}})])
    journal = JsonLinesObservationJournal(path=path)

    with pytest.raises(JournalError, match="unsupported value type"):
        journal.poll(instrument="005930", after_as_of_ms=None)


def test_null_field_value_refuses_the_whole_poll(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(path, [_observation(fields={"close": None})])
    journal = JsonLinesObservationJournal(path=path)

    with pytest.raises(JournalError, match="unsupported value type"):
        journal.poll(instrument="005930", after_as_of_ms=None)


def test_malformed_line_for_a_different_instrument_still_refuses(
    tmp_path: Path,
) -> None:
    """A journal is one shared fault domain — a malformed line for an instrument NOT being
    polled still refuses the call (module docstring: the whole file is validated before any
    instrument filtering happens)."""
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(raw_event_id="e-1", instrument="005930"),
            "{not valid json for 000660",
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    with pytest.raises(JournalError, match="not valid JSON"):
        journal.poll(instrument="005930", after_as_of_ms=None)


def test_malformed_trailing_line_is_not_treated_specially(tmp_path: Path) -> None:
    """Pins the module docstring's explicit decision: a malformed LAST line (the shape a
    non-atomic concurrent writer could produce) refuses the poll exactly like a malformed line
    anywhere else — this journal does not guess that a trailing malformed line is merely
    "not yet fully written"."""
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(raw_event_id="e-1"),
            _observation(raw_event_id="e-2"),
            '{"raw_event_id": "e-3", "instrument": "005930", "as_of_ms": 3000, "fields": {',
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    with pytest.raises(JournalError, match=r"journal\.jsonl:3.*not valid JSON"):
        journal.poll(instrument="005930", after_as_of_ms=None)


def test_blank_lines_are_skipped_not_treated_as_malformed(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    path.write_text(
        json.dumps(_observation(raw_event_id="e-1", as_of_ms=1000))
        + "\n\n   \n"
        + json.dumps(_observation(raw_event_id="e-2", as_of_ms=2000))
        + "\n",
        encoding="utf-8",
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert [o.raw_event_id for o in result] == ["e-1", "e-2"]


# ----------------------------------------------------------------------------
# field shape — fields are carried as a flat, order-independent tuple of (key, value)
# ----------------------------------------------------------------------------


def test_fields_are_carried_as_key_value_pairs(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path,
        [
            _observation(
                raw_event_id="e-1",
                fields={"close": 4512500, "volume": 123, "flag": True, "label": "x"},
            )
        ],
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert len(result) == 1
    observation = result[0]
    assert isinstance(observation, RawObservation)
    assert dict(observation.fields) == {
        "close": 4512500,
        "volume": 123,
        "flag": True,
        "label": "x",
    }


def test_received_ms_defaults_to_none_when_absent(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(path, [_observation(raw_event_id="e-1")])
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert result[0].received_ms is None


def test_received_ms_is_carried_when_present(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    _write_lines(
        path, [_observation(raw_event_id="e-1", received_ms=1_700_000_000_120)]
    )
    journal = JsonLinesObservationJournal(path=path)

    result = journal.poll(instrument="005930", after_as_of_ms=None)

    assert result[0].received_ms == 1_700_000_000_120
