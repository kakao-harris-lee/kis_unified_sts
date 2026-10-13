"""A CP-3 ③ live-producer row, fed to the REAL ``JsonLinesObservationJournal``.

Plan ``docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md`` §3 builds a
host process that appends one observation per completed minute bar; the writer
is ``tools/tos_cp3/live_producer``. That package is legacy-side and the import
firewall is bidirectional, so **no single test can hold both ends**: ``tools/``
may not import ``tos_runtime``, and this package may not import ``tools``.

The committed fixture is the hinge:

* here — the real reader accepts it and hands back the fifteen fields, plus the
  ``received_ms`` that distinguishes a live line from B1a's offline one;
* in ``tests/tools/test_cp3_live_producer.py``
  (``test_item6_the_producer_reproduces_the_committed_fixture``) — the producer
  still makes exactly these bytes.

Either half failing alone is a drift this repo would otherwise only find at the
first tenant session, where a missing key refuses the WHOLE poll rather than
degrading one line (``journal.py``'s fail-closed docstring).

Hermetic (D1.4): reads one committed file, writes nothing, opens no socket.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal

#: Written by ``tools/tos_cp3/live_producer``; regenerate with
#: ``python tests/tools/test_cp3_live_producer.py``, never by hand.
FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "cp3-live-producer-row.jsonl"
)

#: The mini front month the producer is given as an argument (plan §3.5: the
#: runner computes the roll once and hands render, data dir and producer the
#: same value).
INSTRUMENT = "A05611"

#: B1a's ``FIELD_ORDER`` (``tools/tos_cp3/produce_fields.py``), restated as a
#: literal because the firewall forbids importing it. The tenant tree's
#: ``critical_input_policy.yaml`` declares exactly these fifteen.
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
    """``tools/tos_cp3/bootproof_guard.py``'s allowlist is keyed on this prefix.

    It held nothing until ③'s PR-2 added ``tos-cp3-live``, and that addition is
    what makes a first real genesis possible — so a row whose ``source_id``
    drifted from the prefix is a row that cannot create the corpus it was
    written for. The delimiter rule there means the prefix must be followed by
    ``/``, not by more name.
    """
    observation = _only_observation()

    assert observation.source_id.startswith("tos-cp3-live/")
    assert observation.source_id.split("/", 1)[1]  # a version, not a bare prefix


def test_received_ms_survives_the_round_trip() -> None:
    """The third key that differs from B1a (plan §1), and it is not optional here.

    ``RawObservation.received_ms`` defaults to ``None``, so a reader that simply
    ignored the key would look identical on this fixture. Asserting the value
    is what makes the line's "when did the REST response arrive" claim
    observable on the kernel side.
    """
    observation = _only_observation()
    row = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert observation.received_ms == row["received_ms"]
    assert observation.received_ms is not None
    # the stamp is the WRITE time, strictly after the response arrived
    assert observation.as_of_ms > observation.received_ms


def test_the_stamp_is_the_write_time_not_the_bar_label() -> None:
    """Operator decision 2026-10-09 (#887), restated as a reader-side fact.

    The tenant tree's ``critical_input_policy.yaml`` declares ``max_age_ms:
    800`` for all fifteen, and the kernel measures ``now_ms - as_of_ms``. A
    bar-label stamp gives every observation a minimum age of 60,000 ms, so a
    label stamp would make every field STALE no matter how fast the producer
    is. ``as_of_ms`` must therefore NOT be the label the ``raw_event_id``
    carries.
    """
    observation = _only_observation()
    label = observation.raw_event_id.split(":1m:")[1]

    assert label.endswith("+0900")
    # 20261019T092000+0900 -> 1792283... ; the stamp is well past it
    assert observation.as_of_ms > 1_792_283_000_000
    assert str(observation.as_of_ms).startswith("17922864")


def test_the_reader_filters_a_row_written_for_another_contract_month() -> None:
    """A journal for the wrong contract month is not an error — it is an empty
    result, i.e. a session that boots cleanly and consumes nothing. That is why
    ``bootproof_guard.require_journal_instrument`` exists, and why the runner
    hands the producer the same instrument it renders."""
    assert (
        JsonLinesObservationJournal(FIXTURE).poll(
            instrument="A05612", after_as_of_ms=None
        )
        == ()
    )


def test_a_row_missing_one_key_refuses_the_whole_poll(tmp_path: Path) -> None:
    """The cost of drift, stated rather than assumed: the reader does not drop a
    bad line and return the rest."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload.pop("source_id")
    broken = tmp_path / "journal.jsonl"
    broken.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(JournalError, match="source_id"):
        JsonLinesObservationJournal(broken).poll(
            instrument=INSTRUMENT, after_as_of_ms=None
        )


def test_a_half_written_final_line_refuses_the_whole_poll(tmp_path: Path) -> None:
    """Why the producer replaces the journal file WHOLE (plan §2 3).

    The reader has no trailing-partial-line special case by decision, so an
    append that can be observed mid-write loses the complete lines too, not
    just the partial one.
    """
    text = FIXTURE.read_text(encoding="utf-8")
    truncated = tmp_path / "journal.jsonl"
    truncated.write_text(text + text[: len(text) // 2], encoding="utf-8")

    with pytest.raises(JournalError):
        JsonLinesObservationJournal(truncated).poll(
            instrument=INSTRUMENT, after_as_of_ms=None
        )


def test_an_as_of_ms_that_does_not_advance_is_never_returned() -> None:
    """Why the producer refuses a non-advancing stamp instead of writing it.

    ``poll`` filters STRICTLY greater than ``after_as_of_ms``, so a line stamped
    equal to the newest already issued can never be consumed — it is silent
    loss, which is what the producer's monotonicity refusal exists to turn into
    a loud one.
    """
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
