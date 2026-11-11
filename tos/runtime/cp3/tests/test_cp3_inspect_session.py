"""``cp3.inspect_session`` — the recorded-session inspection, pinned to a fixture.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1 완료 판정's second
half: «수치 테스트: 기록된 세션 하나를 fixture 로 고정해 출력 표의 정답 비교». The
fixture here is synthetic rather than a copy of a real session — the real
session's journal is 352 lines and its durable set is an operator's append-only
store, neither of which belongs in the repo — but it is the same SHAPE on both
sides: B1a's journal lines through the committed B1b strategy content, and three
sqlite stores with the real schema versions and the real row shapes.

What the golden text pins, and why each is worth pinning:

* the **comparison order** in the legend and the per-bar marks are the authored
  order, so a reordering of the rendered rules cannot pass silently;
* the boundary bar (``z_x1000 == -1800``) fires R1 and its neighbour
  (``-1799``) does not — the inclusive ``LE`` edge is what makes "which
  comparison blocked R1" a true statement rather than an off-by-one;
* a bar with no preimage row and a bar behind two snapshots are both
  ``UNJOINED`` with their reason printed, never silently paired to a tick;
* the summary's per-comparison false counts are the numbers the roadmap's
  completion question is asked in.

Hermetic: every file this writes is under ``tmp_path`` (the suite's autouse
write guard enforces it), it opens no socket, and it reads no clock — the bar
stamps are injected literals, as :mod:`cp3.tests._cp3_fixtures` already requires.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME, INBOX_FILE_NAME

from .._base import Cp3RunnerRefusal
from ..inspect_evidence import DECISION_TICK_KIND, read_bar_evidence
from ..inspect_session import inspect_session, render_json, render_text
from ._cp3_fixtures import (
    BINDINGS_PATH,
    INSTRUMENT,
    STRATEGY_PATH,
    entry_fields,
    eod_fields,
    near_miss_entry_fields,
    neutral_fields,
    reverted_fields,
    write_jsonl,
)

#: The five fixture bars: labelled minute, field builder. The stamps are literal
#: KST wall-clock strings in the producer's own join-key format
#: (``tools/tos_cp3/produce_fields.py::derive_raw_event_id``), so the printed
#: time column is the labelled minute rather than the marked ``~`` fallback.
_BARS: tuple[tuple[str, int, Any], ...] = (
    ("20261110T090000+0900", 1_794_268_862_186, neutral_fields),
    ("20261110T090100+0900", 1_794_268_922_132, entry_fields),
    ("20261110T090200+0900", 1_794_268_982_140, near_miss_entry_fields),
    ("20261110T090300+0900", 1_794_269_042_150, reverted_fields),
    ("20261110T090400+0900", 1_794_269_102_160, eod_fields),
)


def _raw_event_id(stamp: str) -> str:
    """The fixture bar's join key."""
    return f"{INSTRUMENT}:1m:{stamp}"


def _write_journal(tmp_path: Path) -> Path:
    """The five-bar journal, in B1a's five-key line shape."""
    return write_jsonl(
        tmp_path / "journal.jsonl",
        [
            {
                "raw_event_id": _raw_event_id(stamp),
                "source_id": "tos-cp3-inspect-test/0.1.0",
                "instrument": INSTRUMENT,
                "as_of_ms": as_of_ms,
                "fields": builder(index),
            }
            for index, (stamp, as_of_ms, builder) in enumerate(_BARS)
        ],
    )


@contextmanager
def _store(path: Path, version: int) -> Iterator[sqlite3.Connection]:
    """A fresh store file stamped with ``version``, committed and closed on exit."""
    connection = sqlite3.connect(path)
    with closing(connection):
        connection.execute(f"PRAGMA user_version = {version}")
        yield connection
        connection.commit()


def _tick_payload(snapshot_id: str) -> str:
    """The one inbox payload path the join reads, in the stored shape."""
    return json.dumps(
        {
            "decision_tick": {
                "capsule": {"critical_input_snapshot": {"snapshot_id": snapshot_id}}
            }
        }
    )


def _entry_payload(payload: dict[str, Any]) -> str:
    """The stored evidence envelope: a ``masked_keys`` wrapper around the payload."""
    return json.dumps({"masked_keys": [], "payload": payload})


def _write_marketfeed(data_dir: Path) -> None:
    """``preimages`` for bars 0-2, none for bar 3, and TWO rows for bar 4."""
    with _store(
        data_dir / MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
    ) as marketfeed:
        marketfeed.execute(
            "CREATE TABLE preimages (snapshot_id TEXT NOT NULL, "
            "raw_event_id TEXT NOT NULL, preimage_json TEXT NOT NULL, "
            "PRIMARY KEY (snapshot_id, raw_event_id))"
        )
        rows = [
            (f"cis-{index}", _raw_event_id(_BARS[index][0]), "{}")
            for index in (0, 1, 2)
        ]
        rows += [
            ("cis-4a", _raw_event_id(_BARS[4][0]), "{}"),
            ("cis-4b", _raw_event_id(_BARS[4][0]), "{}"),
        ]
        marketfeed.executemany("INSERT INTO preimages VALUES (?, ?, ?)", rows)


def _write_inbox(data_dir: Path) -> None:
    """One ``DECISION_TICK`` per joinable snapshot, with both evidence stamps."""
    with _store(data_dir / INBOX_FILE_NAME, INBOX_SCHEMA_VERSION) as inbox:
        inbox.execute(
            "CREATE TABLE events (seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL "
            "UNIQUE, kind TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "consumed_evidence_seq INTEGER, handling_started_evidence_seq INTEGER)"
        )
        inbox.executemany(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    index + 1,
                    f"event-{index}",
                    DECISION_TICK_KIND,
                    _tick_payload(f"cis-{index}"),
                    10 * index + 4,
                    10 * index + 1,
                )
                for index in (0, 1, 2)
            ],
        )


#: The three ticks' evidence windows: an outcome, an outcome plus a halt, and a
#: withheld decision — the three shapes the per-bar ``outcome``/``halt`` columns
#: have to tell apart.
_EVIDENCE_ROWS: tuple[tuple[int, str, dict[str, Any]], ...] = (
    (1, "EVENT_HANDLING_STARTED", {}),
    (
        2,
        "DECISION_OUTCOME_EMITTED",
        {"outcome_type": "NoActionOutcome", "halt_reason": "NO_ACTION_OUTCOME"},
    ),
    (
        4,
        "EVENT_CONSUMED",
        {
            "halt_reason": "NO_ACTION_OUTCOME",
            "flow_fingerprint": {"halt_step": None},
        },
    ),
    (11, "EVENT_HANDLING_STARTED", {}),
    (
        12,
        "DECISION_OUTCOME_EMITTED",
        {"outcome_type": "Proposal", "halt_reason": "STAGE_DENIED"},
    ),
    (
        13,
        "FLOW_HALTED",
        {
            "step": "CANDIDATE_COMMAND_CONSTRUCTION",
            "halt_reason": "STAGE_DENIED",
            "detail": "no held position was observed",
        },
    ),
    (
        14,
        "EVENT_CONSUMED",
        {
            "halt_reason": "STAGE_DENIED",
            "flow_fingerprint": {"halt_step": "CANDIDATE_COMMAND_CONSTRUCTION"},
        },
    ),
    (21, "EVENT_HANDLING_STARTED", {}),
    (22, "DECISION_WITHHELD", {"halt_reason": "TIME_NOT_ADMITTED"}),
    (
        24,
        "EVENT_CONSUMED",
        {"halt_reason": "TIME_NOT_ADMITTED", "flow_fingerprint": {"halt_step": None}},
    ),
)


def _write_evidence(data_dir: Path) -> None:
    """The append-only ``entries`` rows :data:`_EVIDENCE_ROWS` declares."""
    with _store(data_dir / EVIDENCE_FILE_NAME, EVIDENCE_SCHEMA_VERSION) as evidence:
        evidence.execute(
            "CREATE TABLE entries (seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, "
            "payload_json TEXT NOT NULL)"
        )
        evidence.executemany(
            "INSERT INTO entries VALUES (?, ?, ?)",
            [
                (seq, kind, _entry_payload(payload))
                for seq, kind, payload in _EVIDENCE_ROWS
            ],
        )


def _write_stores(tmp_path: Path) -> Path:
    """A three-store durable set covering bars 0-2, plus two broken chains.

    * bars 0-2 join cleanly, with an outcome / an outcome-and-halt / a withheld
      decision respectively;
    * bar 3 has no ``preimages`` row at all;
    * bar 4 is named by TWO snapshots, so which one the engine decided on is
      ambiguous.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_marketfeed(data_dir)
    _write_inbox(data_dir)
    _write_evidence(data_dir)
    return data_dir


@pytest.fixture
def report(tmp_path: Path):  # type: ignore[no-untyped-def]
    """The inspection of the five-bar fixture against the committed strategy."""
    return inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        data_dir=_write_stores(tmp_path),
        session_name="fixture-20261110",
    )


# ===========================================================================
# The golden table
# ===========================================================================

_EXPECTED_LEGEND = """rules (comparison order, as authored):
  R1 = R1-ENTRY-LONG (ACTION)
       1 entry_window EQ true
       2 hi_vol EQ true
       3 stall_ok EQ true
       4 reversal_ok EQ true
       5 z_x1000 LE config.z_entry_max_x1000
  R2 = R2-EXIT-VWAP-REVERTED (FLAT)
       1 vwap_reverted EQ true
  R3 = R3-EXIT-EOD (FLAT)
       1 eod EQ true
  default = R0-DEFAULT-NO-ACTION (NO_ACTION)"""

_EXPECTED_BARS = """bars (+ = comparison true, - = false; rule Y = fired):
time    close_x100   vwap_x100     z_x1000 R1      R2  R3  decision                 outcome              halt
09:00        58000       58020        -300 n ----- n - n - R0-DEFAULT-NO-ACTION     NoActionOutcome      -
09:01        58001       58021       -1800 Y +++++ n - n - R1-ENTRY-LONG            Proposal             STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION
09:02        58002       58022       -1799 n ++++- n - n - R0-DEFAULT-NO-ACTION     TIME_NOT_ADMITTED    -
09:03        58003       58023         100 n ----- Y + n - R2-EXIT-VWAP-REVERTED    UNJOINED             no preimage row names this raw_event_id
09:04        58004       58024        -300 n ----- n - Y + R3-EXIT-EOD              UNJOINED             2 snapshots name this raw_event_id — which one the engine decided on is ambiguous"""

_EXPECTED_SUMMARY = """summary — 5 bars
  R1 R1-ENTRY-LONG            fired     1 / 5       20.0%
      1 entry_window EQ true                             false     3 / 5       60.0%
      2 hi_vol EQ true                                   false     3 / 5       60.0%
      3 stall_ok EQ true                                 false     3 / 5       60.0%
      4 reversal_ok EQ true                              false     3 / 5       60.0%
      5 z_x1000 LE config.z_entry_max_x1000              false     4 / 5       80.0%
  R2 R2-EXIT-VWAP-REVERTED    fired     1 / 5       20.0%
      1 vwap_reverted EQ true                            false     4 / 5       80.0%
  R3 R3-EXIT-EOD              fired     1 / 5       20.0%
      1 eod EQ true                                      false     4 / 5       80.0%
  decisions: R0-DEFAULT-NO-ACTION 2 · R1-ENTRY-LONG 1 · R2-EXIT-VWAP-REVERTED 1 · R3-EXIT-EOD 1
  evidence outcomes: NoActionOutcome 1 · Proposal 1 · TIME_NOT_ADMITTED 1
  evidence halts: STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION 1
  unjoined: 2 snapshots name this raw_event_id — which one the engine decided on is ambiguous 1 · no preimage row names this raw_event_id 1"""


def _block(text: str, first_line: str) -> str:
    """The rendered block starting at ``first_line``, up to the next blank line."""
    lines = text.splitlines()
    start = lines.index(first_line)
    end = start
    while end + 1 < len(lines) and lines[end + 1] != "":
        end += 1
    return "\n".join(lines[start : end + 1])


def test_legend_is_the_authored_comparison_order(report: Any) -> None:
    """The legend names every rule and every comparison, in the authored order."""
    assert _block(render_text(report), _EXPECTED_LEGEND.splitlines()[0]) == (
        _EXPECTED_LEGEND
    )


def test_bar_table_matches_the_golden_text(report: Any) -> None:
    """One line per bar: fields, marks, first-match decision, engine's own answer."""
    assert _block(render_text(report), _EXPECTED_BARS.splitlines()[0]) == _EXPECTED_BARS


def test_summary_matches_the_golden_text(report: Any) -> None:
    """The per-comparison false shares — the roadmap §P1 completion question."""
    assert _block(render_text(report), _EXPECTED_SUMMARY.splitlines()[0]) == (
        _EXPECTED_SUMMARY
    )


def test_le_threshold_edge_is_inclusive_and_its_neighbour_is_not(report: Any) -> None:
    """``-1800`` fires R1; ``-1799`` fails exactly the threshold comparison.

    Without the second half, a binding the stream never crosses would be
    indistinguishable from the authored one.
    """
    on_edge, inside = report.bars[1], report.bars[2]
    assert on_edge.rules[0].fired is True
    assert inside.rules[0].fired is False
    assert [compare.passed for compare in inside.rules[0].compares] == [
        True,
        True,
        True,
        True,
        False,
    ]
    assert inside.rules[0].compares[4].left_value == "-1799"
    assert inside.rules[0].compares[4].right_value == "-1800"


def test_window_bounds_are_inclusive(tmp_path: Path) -> None:
    """``--from``/``--to`` select by the bar's LABELLED minute, both ends included."""
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        window_from="09:01",
        window_to="09:03",
    )
    assert [row.time_kst for row in report.bars] == ["09:01", "09:02", "09:03"]
    assert all(row.time_source == "raw_event_id" for row in report.bars)
    assert report.rules[0].bars == 3


def test_a_window_selecting_no_bar_refuses(tmp_path: Path) -> None:
    """An empty table would not say whether the window or the instrument was wrong."""
    with pytest.raises(Cp3RunnerRefusal, match="falls in the requested window"):
        inspect_session(
            journal_path=_write_journal(tmp_path),
            strategy_path=STRATEGY_PATH,
            bindings_path=BINDINGS_PATH,
            window_from="13:00",
        )


@pytest.mark.parametrize("value", ["9:00:00", "0900", "24:00", "09:61", "nine"])
def test_a_malformed_window_refuses(tmp_path: Path, value: str) -> None:
    """``--from``/``--to`` are ``HH:MM`` or a refusal, never a best guess."""
    with pytest.raises(Cp3RunnerRefusal, match="--from"):
        inspect_session(
            journal_path=_write_journal(tmp_path),
            strategy_path=STRATEGY_PATH,
            bindings_path=BINDINGS_PATH,
            window_from=value,
        )


def test_an_unparseable_join_key_is_marked_not_silently_derived(tmp_path: Path) -> None:
    """A key outside the producer's format prints ``~HH:MM`` from ``as_of_ms``."""
    journal = write_jsonl(
        tmp_path / "journal.jsonl",
        [
            {
                "raw_event_id": f"{INSTRUMENT}:5m:20261110T090000+0900",
                "source_id": "tos-cp3-inspect-test/0.1.0",
                "instrument": INSTRUMENT,
                "as_of_ms": 1_794_268_862_186,
                "fields": neutral_fields(0),
            }
        ],
    )
    report = inspect_session(
        journal_path=journal, strategy_path=STRATEGY_PATH, bindings_path=BINDINGS_PATH
    )
    assert report.bars[0].time_source == "as_of_ms"
    assert report.bars[0].time_kst == "~09:01"


def test_without_a_data_dir_the_rules_still_render(tmp_path: Path) -> None:
    """``--no-evidence``'s path: no store is opened and no evidence is claimed."""
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
    )
    assert report.data_dir is None
    assert all(row.evidence is None for row in report.bars)
    assert "evidence  (not read — no --data-dir)" in render_text(report)


def test_json_carries_every_comparison_and_the_summary(report: Any) -> None:
    """The machine document is the same data, not a second, thinner answer."""
    document = json.loads(render_json(report))
    assert document["session"] == "fixture-20261110"
    assert len(document["bars"]) == 5
    edge = document["bars"][1]
    assert edge["decision_rule_id"] == "R1-ENTRY-LONG"
    assert [compare["passed"] for compare in edge["rules"][0]["compares"]] == [True] * 5
    assert edge["evidence"]["halt_step"] == "CANDIDATE_COMMAND_CONSTRUCTION"
    assert edge["evidence"]["halt_detail"] == "no held position was observed"
    blocked = document["summary"]["rules"][0]["compares"][4]
    assert (blocked["failed_bars"], blocked["bars"]) == (4, 5)
    assert document["summary"]["unjoined"] == {
        "no preimage row names this raw_event_id": 1,
        "2 snapshots name this raw_event_id — which one the engine decided on is "
        "ambiguous": 1,
    }


def test_a_store_at_an_unpinned_schema_version_refuses(tmp_path: Path) -> None:
    """A schema this reader is not pinned to refuses rather than being parsed."""
    data_dir = _write_stores(tmp_path)
    with closing(sqlite3.connect(data_dir / EVIDENCE_FILE_NAME)) as evidence:
        evidence.execute(f"PRAGMA user_version = {EVIDENCE_SCHEMA_VERSION + 1}")
    with pytest.raises(Cp3RunnerRefusal, match="PRAGMA user_version"):
        read_bar_evidence(data_dir, [_raw_event_id(_BARS[0][0])])


def test_a_missing_store_refuses(tmp_path: Path) -> None:
    """A durable set without its marketfeed store is named, not worked around."""
    data_dir = _write_stores(tmp_path)
    (data_dir / MARKETFEED_FILE_NAME).unlink()
    with pytest.raises(Cp3RunnerRefusal, match="durable store does not exist"):
        read_bar_evidence(data_dir, [_raw_event_id(_BARS[0][0])])
