"""The CP-3 tenant boot-proof row, fed to the REAL ``JsonLinesObservationJournal``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cp3-bootproof-row.jsonl"

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


def test_the_reader_accepts_the_boot_proof_row() -> None:
    observations = JsonLinesObservationJournal(FIXTURE).poll(
        instrument=INSTRUMENT, after_as_of_ms=None
    )

    assert len(observations) == 1
    observation = observations[0]
    assert observation.instrument == INSTRUMENT
    assert isinstance(observation.as_of_ms, int)
    assert tuple(key for key, _value in observation.fields) == FIELD_ORDER
    assert all(
        isinstance(value, (bool, int, float, str)) for _key, value in observation.fields
    )


def test_the_row_announces_itself_as_synthetic() -> None:
    """``tools/tos_cp3/bootproof_guard.py`` refuses to let this marker near a"""
    observation = JsonLinesObservationJournal(FIXTURE).poll(
        instrument=INSTRUMENT, after_as_of_ms=None
    )[0]

    assert observation.source_id.startswith("cp3-bootproof-synthetic:")
    assert observation.source_id.split(":", 2)[1] == "101S6000"


def test_the_reader_filters_a_row_written_for_another_contract_month() -> None:
    """Why ``bootproof_guard.require_journal_instrument`` exists: a journal for"""
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
