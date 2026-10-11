"""The CP-3 tenant boot-proof row, fed to the REAL ``JsonLinesObservationJournal``.

Plan ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md`` §2.5
puts a one-row observation journal in front of the first tenant boot, written by
``tools/tos_cp3/bootproof_journal.py``. That tool is legacy-side and the import
firewall is bidirectional, so **no single test can hold both ends**: ``tools/``
may not import ``tos_runtime``, and this package may not import ``tools``.

The committed fixture is the hinge:

* here — the real reader accepts it and hands back the fifteen fields;
* in ``tests/tools/test_cp3_bootproof.py``
  (``test_the_tool_reproduces_the_committed_fixture``) — the tool still produces
  exactly these bytes.

Either half failing alone is a drift this repo would otherwise only find at the
first tenant boot, where a missing key refuses the WHOLE poll rather than
degrading one line (``journal.py``'s fail-closed docstring).

Hermetic (D1.4): reads one committed file, writes nothing, opens no socket.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal

#: Written by ``tools/tos_cp3/bootproof_journal.py``; regenerate with that tool,
#: never by hand.
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cp3-bootproof-row.jsonl"

#: The rendered MINI contract the row is labelled with. The VALUES come from the
#: full contract ``101S6000`` and the relabel is named in ``source_id`` (plan
#: L1) — this boot proves wiring, and its outcome is not a market fact.
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
    """``tools/tos_cp3/bootproof_guard.py`` refuses to let this marker near a
    designated tenant durable set, so a row that lost it would be a row that can
    genesis one (plan §2.5, H2)."""
    observation = JsonLinesObservationJournal(FIXTURE).poll(
        instrument=INSTRUMENT, after_as_of_ms=None
    )[0]

    assert observation.source_id.startswith("cp3-bootproof-synthetic:")
    # The full→mini relabel, named: original contract, then original row.
    assert observation.source_id.split(":", 2)[1] == "101S6000"


def test_the_reader_filters_a_row_written_for_another_contract_month() -> None:
    """Why ``bootproof_guard.require_journal_instrument`` exists: a journal for
    the wrong contract month is not an error here — it is an empty result, i.e.
    a session that boots cleanly and consumes nothing."""
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
