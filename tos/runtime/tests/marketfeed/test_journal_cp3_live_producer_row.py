"""A CP-3 ③ live-producer row, fed to the REAL ``JsonLinesObservationJournal``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cp3-live-producer-row.jsonl"
)

INSTRUMENT = "A05611"

FIELD_ORDER = (
    "open_x100",
    "high_x100",
    "low_x100",
    "close_x100",
    "volume",
    "session_token",
    "vwap_x100",
    "atr14_x100",
    "z_x1000",
    "hi_vol",
    "stall_ok",
    "reversal_ok",
    "entry_window",
    "vwap_reverted",
    "eod",
)


def _only_observation():
    observations = JsonLinesObservationJournal(FIXTURE).poll(
        instrument=INSTRUMENT, after_as_of_ms=None
    )
    assert len(observations) == 1
    return observations[0]


def test_the_reader_accepts_a_live_producer_row() -> None:
    observation = _only_observation()

    assert observation.instrument == INSTRUMENT
    assert isinstance(observation.as_of_ms, int)
    assert tuple(key for key, _value in observation.fields) == FIELD_ORDER
    assert all(
        isinstance(value, (bool, int, float, str)) for _key, value in observation.fields
    )


def test_the_row_names_the_approved_real_producer() -> None:
    """``tools/tos_cp3/bootproof_guard.py``'s allowlist is keyed on this prefix."""
    observation = _only_observation()

    assert observation.source_id.startswith("tos-cp3-live/")
    assert observation.source_id.split("/", 1)[1]


def test_received_ms_survives_the_round_trip() -> None:
    """The third key that differs from B1a (plan §1), and it is not optional here."""
    observation = _only_observation()
    row = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert observation.received_ms == row["received_ms"]
    assert observation.received_ms is not None
    assert observation.as_of_ms > observation.received_ms


def test_the_stamp_is_the_write_time_not_the_bar_label() -> None:
    """Operator decision 2026-10-09 (#887), restated as a reader-side fact."""
    observation = _only_observation()
    label = observation.raw_event_id.split(":1m:")[1]

    assert label.endswith("+0900")
    assert observation.as_of_ms > 1_792_283_000_000
    assert str(observation.as_of_ms).startswith("17922864")


def test_the_reader_filters_a_row_written_for_another_contract_month() -> None:
    """A journal for the wrong contract month is not an error — it is an empty"""
    assert (
        JsonLinesObservationJournal(FIXTURE).poll(
            instrument="A05612", after_as_of_ms=None
        )
        == ()
    )


def test_a_row_missing_one_key_refuses_the_whole_poll(tmp_path: Path) -> None:
    """The cost of drift, stated rather than assumed: the reader does not drop a"""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload.pop("source_id")
    broken = tmp_path / "journal.jsonl"
    broken.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(JournalError, match="source_id"):
        JsonLinesObservationJournal(broken).poll(
            instrument=INSTRUMENT, after_as_of_ms=None
        )


def test_a_half_written_final_line_refuses_the_whole_poll(tmp_path: Path) -> None:
    """Why the producer replaces the journal file WHOLE (plan §2 3)."""
    text = FIXTURE.read_text(encoding="utf-8")
    truncated = tmp_path / "journal.jsonl"
    truncated.write_text(text + text[: len(text) // 2], encoding="utf-8")

    with pytest.raises(JournalError):
        JsonLinesObservationJournal(truncated).poll(
            instrument=INSTRUMENT, after_as_of_ms=None
        )


def test_an_as_of_ms_that_does_not_advance_is_never_returned() -> None:
    """Why the producer refuses a non-advancing stamp instead of writing it."""
    observation = _only_observation()

    assert (
        JsonLinesObservationJournal(FIXTURE).poll(
            instrument=INSTRUMENT, after_as_of_ms=observation.as_of_ms
        )
        == ()
    )
    assert (
        len(
            JsonLinesObservationJournal(FIXTURE).poll(
                instrument=INSTRUMENT, after_as_of_ms=observation.as_of_ms - 1
            )
        )
        == 1
    )
