"""``cp3.inspect_session`` — the recorded-session inspection, pinned to a fixture."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
from tos.dsl import ScalarValue
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME, INBOX_FILE_NAME

from .._base import Cp3RunnerRefusal
from ..inspect_evidence import DECISION_TICK_KIND, read_bar_evidence
from ..inspect_report import (
    EVALUATION_ENGINE_VIEW,
    EVALUATION_JOURNAL_ONLY,
    EVALUATION_JOURNAL_UNJOINED,
    EVALUATION_WITHHELD,
    InspectReport,
    render_json,
    render_text,
)
from ..inspect_session import inspect_session
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

_BARS: tuple[tuple[str, int, Any], ...] = (
    ("20261110T090000+0900", 1_794_268_862_186, neutral_fields),
    ("20261110T090100+0900", 1_794_268_922_132, entry_fields),
    ("20261110T090200+0900", 1_794_268_982_140, near_miss_entry_fields),
    ("20261110T090300+0900", 1_794_269_042_150, reverted_fields),
    ("20261110T090400+0900", 1_794_269_102_160, eod_fields),
    ("20261110T090500+0900", 1_794_269_162_170, neutral_fields),
    ("20261110T090600+0900", 1_794_269_222_180, reverted_fields),
    ("20261110T090700+0900", 1_794_269_282_190, neutral_fields),
)

_VIEW_OVERRIDES: Mapping[int, Mapping[str, ScalarValue]] = {5: {"hi_vol": True}}

_TICKS: Mapping[int, tuple[int, int | None]] = {
    0: (1, 4),
    1: (11, 14),
    2: (21, 24),
    5: (51, 54),
    6: (61, 64),
    7: (71, None),
}

_EVIDENCE_ROWS: tuple[tuple[int, str, dict[str, Any]], ...] = (
    (1, "EVENT_HANDLING_STARTED", {}),
    (2, "DECISION_WITHHELD", {"halt_reason": "TIME_NOT_ADMITTED"}),
    (
        4,
        "EVENT_CONSUMED",
        {"halt_reason": "TIME_NOT_ADMITTED", "flow_fingerprint": {"halt_step": None}},
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
    (
        22,
        "DECISION_OUTCOME_EMITTED",
        {"outcome_type": "NoActionOutcome", "halt_reason": "NO_ACTION_OUTCOME"},
    ),
    (
        24,
        "EVENT_CONSUMED",
        {"halt_reason": "NO_ACTION_OUTCOME", "flow_fingerprint": {"halt_step": None}},
    ),
    (51, "EVENT_HANDLING_STARTED", {}),
    (
        52,
        "DECISION_OUTCOME_EMITTED",
        {"outcome_type": "NoActionOutcome", "halt_reason": "NO_ACTION_OUTCOME"},
    ),
    (
        54,
        "EVENT_CONSUMED",
        {"halt_reason": "NO_ACTION_OUTCOME", "flow_fingerprint": {"halt_step": None}},
    ),
    (61, "EVENT_HANDLING_STARTED", {}),
    (
        62,
        "DECISION_OUTCOME_EMITTED",
        {"outcome_type": "NoActionOutcome", "halt_reason": "NO_ACTION_OUTCOME"},
    ),
    (
        64,
        "EVENT_CONSUMED",
        {"halt_reason": "NO_ACTION_OUTCOME", "flow_fingerprint": {"halt_step": None}},
    ),
)


def _raw_event_id(stamp: str) -> str:
    """The fixture bar's join key."""
    return f"{INSTRUMENT}:1m:{stamp}"


def _journal_fields(index: int) -> dict[str, Any]:
    """The producer's journal fields for bar ``index``."""
    return dict(_BARS[index][2](index))


def _write_journal(tmp_path: Path) -> Path:
    """The eight-bar journal, in B1a's five-key line shape."""
    return write_jsonl(
        tmp_path / "journal.jsonl",
        [
            {
                "raw_event_id": _raw_event_id(stamp),
                "source_id": "tos-cp3-inspect-test/0.1.0",
                "instrument": INSTRUMENT,
                "as_of_ms": as_of_ms,
                "fields": _journal_fields(index),
            }
            for index, (stamp, as_of_ms, _builder) in enumerate(_BARS)
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


def _view_values(index: int) -> dict[str, Any]:
    """The values the ENGINE saw for bar ``index`` — the journal plus overrides."""
    values = _journal_fields(index)
    values.update(_VIEW_OVERRIDES.get(index, {}))
    return values


def _value_view(index: int, *, empty: bool = False) -> dict[str, Any]:
    """One tick's stored :class:`~tos.dsl.ContextValueView`, in its dumped shape."""
    snapshot_id = f"cis-{index}"
    raw_event_id = _raw_event_id(_BARS[index][0])
    as_of = _BARS[index][1]
    values = {} if empty else _view_values(index)
    return {
        "snapshot_id": snapshot_id,
        "snapshot_canonical_digest": f"digest-{index}",
        "canonical_digest": f"view-digest-{index}",
        "canonicalization_version": "ev-l1-provisional-0",
        "values": [
            {
                "field_key": key,
                "value": value,
                "as_of": as_of,
                "payload_digest": f"payload-{index}",
                "observation_ref": raw_event_id,
            }
            for key, value in sorted(values.items())
        ],
    }


def _tick_payload(index: int) -> str:
    """One inbox ``DECISION_TICK`` payload: the bound capsule and the value view."""
    return json.dumps(
        {
            "decision_tick": {
                "capsule": {"critical_input_snapshot": {"snapshot_id": f"cis-{index}"}},
                "value_view": _value_view(index, empty=index == 0),
            }
        }
    )


def _entry_payload(payload: dict[str, Any]) -> str:
    """The stored evidence envelope: a ``masked_keys`` wrapper around the payload."""
    return json.dumps({"masked_keys": [], "payload": payload})


def _write_marketfeed(data_dir: Path) -> None:
    """``preimages``: one row per ticked bar, none for bar 3, two for bar 4."""
    with _store(
        data_dir / MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
    ) as marketfeed:
        marketfeed.execute(
            "CREATE TABLE preimages (snapshot_id TEXT NOT NULL, "
            "raw_event_id TEXT NOT NULL, preimage_json TEXT NOT NULL, "
            "PRIMARY KEY (snapshot_id, raw_event_id))"
        )
        rows = [
            (f"cis-{index}", _raw_event_id(_BARS[index][0]), "{}") for index in _TICKS
        ]
        rows += [
            ("cis-4a", _raw_event_id(_BARS[4][0]), "{}"),
            ("cis-4b", _raw_event_id(_BARS[4][0]), "{}"),
        ]
        marketfeed.executemany("INSERT INTO preimages VALUES (?, ?, ?)", rows)


def _write_inbox(data_dir: Path) -> None:
    """One ``DECISION_TICK`` per :data:`_TICKS` entry, bar 7's half-stamped."""
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
                    _tick_payload(index),
                    consumed,
                    started,
                )
                for index, (started, consumed) in _TICKS.items()
            ],
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
    """A three-store durable set matching :data:`_BARS`' eight declared shapes."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_marketfeed(data_dir)
    _write_inbox(data_dir)
    _write_evidence(data_dir)
    return data_dir


@pytest.fixture
def report(tmp_path: Path) -> InspectReport:
    """The inspection of the eight-bar fixture against the committed strategy."""
    return inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        data_dir=_write_stores(tmp_path),
        session_name="fixture-20261110",
    )


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

_EXPECTED_BARS = """bars (+ true · - false; rule Y fired · n not · ? not evaluated; flags V=view≠journal D=decision≠engine W=withheld U=journal-substituted):
time   VDWU  close_x100   vwap_x100     z_x1000 R1      R2  R3  decision                 outcome              halt
09:00  --W-       58000       58020        -300 ?       ?   ?   (not evaluated)          TIME_NOT_ADMITTED    -
09:01  ----       58001       58021       -1800 Y +++++ n - n - R1-ENTRY-LONG            Proposal             STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION
09:02  ----       58002       58022       -1799 n ++++- n - n - R0-DEFAULT-NO-ACTION     NoActionOutcome      -
09:03  ---U       58003       58023         100 n ----- Y + n - R2-EXIT-VWAP-REVERTED    UNJOINED             no preimage row names this raw_event_id
09:04  ---U       58004       58024        -300 n ----- n - Y + R3-EXIT-EOD              UNJOINED             2 snapshots name this raw_event_id — which one the engine decided on is ambiguous
09:05  V---       58005       58025        -300 n -+--- n - n - R0-DEFAULT-NO-ACTION     NoActionOutcome      -
09:06  -D--       58006       58026         100 n ----- Y + n - R2-EXIT-VWAP-REVERTED    NoActionOutcome      -
09:07  ---U       58007       58027        -300 n ----- n - n - R0-DEFAULT-NO-ACTION     UNJOINED             tick event-7 exists but handling never completed (handling_started_evidence_seq=71, consumed_evidence_seq=None)"""

_EXPECTED_SUMMARY = """summary — 8 bars · 4 counted on the engine's value view · 1 withheld · 3 journal-substituted
  R1 R1-ENTRY-LONG            fired     1 / 4       25.0%
      1 entry_window EQ true                             false     2 / 4       50.0%
      2 hi_vol EQ true                                   false     1 / 4       25.0%
      3 stall_ok EQ true                                 false     2 / 4       50.0%
      4 reversal_ok EQ true                              false     2 / 4       50.0%
      5 z_x1000 LE config.z_entry_max_x1000              false     3 / 4       75.0%
  R2 R2-EXIT-VWAP-REVERTED    fired     1 / 4       25.0%
      1 vwap_reverted EQ true                            false     3 / 4       75.0%
  R3 R3-EXIT-EOD              fired     0 / 4        0.0%
      1 eod EQ true                                      false     4 / 4      100.0%
  decisions: R0-DEFAULT-NO-ACTION 3 · R2-EXIT-VWAP-REVERTED 2 · R1-ENTRY-LONG 1 · R3-EXIT-EOD 1
  value view ≠ journal: 1 bars · hi_vol 1
  decision ≠ engine outcome: 1 bars (0 not comparable)
  withheld (empty view or DECISION_WITHHELD): 1 bars
  evidence outcomes: NoActionOutcome 3 · Proposal 1 · TIME_NOT_ADMITTED 1
  evidence halts: STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION 1
  unjoined: 2 snapshots name this raw_event_id — which one the engine decided on is ambiguous 1 · no preimage row names this raw_event_id 1 · tick event-7 exists but handling never completed (handling_started_evidence_seq=71, consumed_evidence_seq=None) 1"""


def _block(text: str, first_line: str) -> str:
    """The rendered block starting at ``first_line``, up to the next blank line."""
    lines = text.splitlines()
    start = lines.index(first_line)
    end = start
    while end + 1 < len(lines) and lines[end + 1] != "":
        end += 1
    return "\n".join(lines[start : end + 1])


def test_legend_is_the_authored_comparison_order(report: InspectReport) -> None:
    """The legend names every rule and every comparison, in the authored order."""
    assert _block(render_text(report), _EXPECTED_LEGEND.splitlines()[0]) == (
        _EXPECTED_LEGEND
    )


def test_bar_table_matches_the_golden_text(report: InspectReport) -> None:
    """One line per bar: flags, fields, marks, decision, the engine's own answer."""
    assert _block(render_text(report), _EXPECTED_BARS.splitlines()[0]) == _EXPECTED_BARS


def test_summary_matches_the_golden_text(report: InspectReport) -> None:
    """The per-comparison false shares — the roadmap §P1 completion question."""
    assert _block(render_text(report), _EXPECTED_SUMMARY.splitlines()[0]) == (
        _EXPECTED_SUMMARY
    )


def test_rules_are_evaluated_on_the_engine_view_not_the_journal(
    report: InspectReport,
) -> None:
    """Bar 5's ``hi_vol`` is false in the journal and true in the engine's view."""
    row = report.bars[5]
    assert row.fields["hi_vol"] is False
    assert row.env_values["hi_vol"] is True
    assert row.evaluation == EVALUATION_ENGINE_VIEW
    assert row.rules[0].compares[1].passed is True
    assert row.rules[0].compares[1].left_value == "true"


def test_a_view_journal_difference_is_flagged_and_named(report: InspectReport) -> None:
    """Per-bar ``V`` plus the field key and bar count in the summary."""
    assert report.bars[5].flags == "V---"
    assert report.bars[5].view_diff == {"hi_vol": ("true", "false")}
    assert report.view_diff_bars == 1
    assert report.view_diff_fields == {"hi_vol": 1}
    assert [row.flags for row in report.bars if row.view_diff] == ["V---"]


def test_an_explicit_empty_view_is_withheld_and_not_evaluated(
    report: InspectReport,
) -> None:
    """Bar 0's view admitted nothing, so no rule is evaluated and none is shown."""
    row = report.bars[0]
    assert row.evaluation == EVALUATION_WITHHELD
    assert row.counted is False
    assert row.rules == ()
    assert (row.decision_rule_id, row.decision_kind) == (None, None)
    assert row.env_values == {}
    assert row.flags == "--W-"
    assert report.withheld_bars == 1


def test_a_recorded_withheld_decision_is_withheld_even_with_a_full_view(
    tmp_path: Path,
) -> None:
    """A tick whose view carried values can still have been withheld."""
    data_dir = _write_stores(tmp_path)
    with closing(sqlite3.connect(data_dir / EVIDENCE_FILE_NAME)) as evidence:
        evidence.execute(
            "INSERT INTO entries VALUES (?, ?, ?)",
            (
                23,
                "DECISION_WITHHELD",
                _entry_payload({"halt_reason": "TIME_NOT_ADMITTED"}),
            ),
        )
        evidence.commit()
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        data_dir=data_dir,
    )
    row = report.bars[2]
    assert row.evidence is not None
    assert row.evidence.value_view
    assert row.evidence.view_is_explicitly_empty is False
    assert row.evidence.withheld_reason == "TIME_NOT_ADMITTED"
    assert row.evidence.withheld is True
    assert row.evaluation == EVALUATION_WITHHELD
    assert row.counted is False
    assert row.rules == ()
    assert row.decision_rule_id is None
    assert row.flags == "--W-"
    assert (report.withheld_bars, report.counted_bars) == (2, 3)
    assert all(rule.bars == 3 for rule in report.rules)


def test_withheld_and_substituted_bars_leave_every_denominator(
    report: InspectReport,
) -> None:
    """The denominators are the four counted bars, not the eight rendered ones."""
    assert len(report.bars) == 8
    assert (report.counted_bars, report.withheld_bars, report.substituted_bars) == (
        4,
        1,
        3,
    )
    assert [row.counted for row in report.bars] == [
        False,
        True,
        True,
        False,
        False,
        True,
        True,
        False,
    ]
    for rule in report.rules:
        assert rule.bars == 4
        for compare in rule.compares:
            assert compare.bars == 4


def test_an_unjoined_bar_is_evaluated_on_the_journal_and_marked(
    report: InspectReport,
) -> None:
    """Bar 3 has no preimage row: the fields still read, the claim does not."""
    row = report.bars[3]
    assert row.evaluation == EVALUATION_JOURNAL_UNJOINED
    assert row.counted is False
    assert row.flags == "---U"
    assert row.env_values == dict(row.fields)
    assert row.decision_rule_id == "R2-EXIT-VWAP-REVERTED"


def test_a_decision_disagreeing_with_the_engine_outcome_is_flagged(
    report: InspectReport,
) -> None:
    """Bar 6's view fires R2 while the engine recorded a no-action."""
    row = report.bars[6]
    assert row.decision_rule_id == "R2-EXIT-VWAP-REVERTED"
    assert row.engine_shape == "no_action"
    assert row.decision_disagrees is True
    assert row.flags == "-D--"
    assert report.disagreement_bars == 1


def test_agreeing_bars_are_not_flagged(report: InspectReport) -> None:
    """Every other counted bar's decision shape matches the recorded outcome."""
    agreeing = [report.bars[index] for index in (1, 2, 5)]
    assert [row.engine_shape for row in agreeing] == [
        "proposal",
        "no_action",
        "no_action",
    ]
    assert [row.decision_disagrees for row in agreeing] == [False, False, False]
    assert report.not_comparable_bars == 0


def test_an_unmeasured_outcome_type_is_not_comparable_rather_than_a_disagreement(
    tmp_path: Path,
) -> None:
    """An ``outcome_type`` nobody has measured must not manufacture a ``D``."""
    data_dir = _write_stores(tmp_path)
    with closing(sqlite3.connect(data_dir / EVIDENCE_FILE_NAME)) as evidence:
        evidence.execute(
            "UPDATE entries SET payload_json = ? WHERE seq = 22",
            (_entry_payload({"outcome_type": "SomeFutureOutcome"}),),
        )
        evidence.commit()
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        data_dir=data_dir,
    )
    row = report.bars[2]
    assert row.engine_shape is None
    assert row.decision_disagrees is False
    assert row.flags == "----"
    assert report.not_comparable_bars == 1
    assert report.disagreement_bars == 1


def test_a_half_stamped_tick_says_handling_never_completed(
    report: InspectReport,
) -> None:
    """Bar 7's tick exists; "no tick bound this snapshot" would be a lie."""
    evidence = report.bars[7].evidence
    assert evidence is not None
    reason = evidence.unjoined_reason or ""
    assert "exists but handling never completed" in reason
    assert "event-7" in reason
    assert "consumed_evidence_seq=None" in reason
    assert report.bars[7].flags == "---U"


def test_a_snapshot_no_tick_ever_bound_says_that_instead(tmp_path: Path) -> None:
    """The other half of LOW-3: an absent tick keeps its own distinct reason."""
    data_dir = _write_stores(tmp_path)
    with closing(sqlite3.connect(data_dir / INBOX_FILE_NAME)) as inbox:
        inbox.execute("DELETE FROM events WHERE event_id = ?", ("event-2",))
        inbox.commit()
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        data_dir=data_dir,
    )
    evidence = report.bars[2].evidence
    assert evidence is not None
    assert evidence.unjoined_reason == "no inbox DECISION_TICK bound snapshot cis-2"


def test_le_threshold_edge_is_inclusive_and_its_neighbour_is_not(
    report: InspectReport,
) -> None:
    """``-1800`` fires R1; ``-1799`` fails exactly the threshold comparison."""
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
        data_dir=_write_stores(tmp_path),
        window_from="09:01",
        window_to="09:03",
    )
    assert [row.time_kst for row in report.bars] == ["09:01", "09:02", "09:03"]
    assert all(row.time_source == "raw_event_id" for row in report.bars)
    assert report.rules[0].bars == 2


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


def test_without_a_data_dir_the_journal_is_the_counted_basis(tmp_path: Path) -> None:
    """``--no-evidence``'s path: no store is opened, and the numbers still mean something."""
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
    )
    assert report.data_dir is None
    assert all(row.evidence is None for row in report.bars)
    assert all(row.evaluation == EVALUATION_JOURNAL_ONLY for row in report.bars)
    assert (report.counted_bars, report.substituted_bars) == (8, 0)
    assert all(row.flags == "----" for row in report.bars)
    text = render_text(report)
    assert "evidence  (not read — no --data-dir)" in text
    assert "8 counted on the journal (no engine view read)" in text


def test_json_carries_the_view_the_flags_and_the_summary(report: InspectReport) -> None:
    """The machine document is the same data, not a second, thinner answer."""
    document = json.loads(render_json(report))
    assert document["session"] == "fixture-20261110"
    assert len(document["bars"]) == 8
    edge = document["bars"][1]
    assert edge["decision_rule_id"] == "R1-ENTRY-LONG"
    assert [compare["passed"] for compare in edge["rules"][0]["compares"]] == [True] * 5
    assert (edge["evidence"]["snapshot_id"], edge["evidence"]["event_id"]) == (
        "cis-1",
        "event-1",
    )
    assert edge["evidence"]["halt_step"] == "CANDIDATE_COMMAND_CONSTRUCTION"
    assert edge["evidence"]["halt_detail"] == "no held position was observed"
    assert edge["evidence"]["value_view"]["z_x1000"] == -1800
    differing = document["bars"][5]
    assert differing["flags"] == "V---"
    assert differing["view_diff"] == {
        "hi_vol": {"value_view": "true", "journal": "false"}
    }
    summary = document["summary"]
    assert summary["counted_bars"] == 4
    assert summary["withheld_bars"] == 1
    assert summary["substituted_bars"] == 3
    assert summary["view_diff_fields"] == {"hi_vol": 1}
    assert summary["disagreement_bars"] == 1
    blocked = summary["rules"][0]["compares"][4]
    assert (blocked["failed_bars"], blocked["bars"]) == (3, 4)


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


def test_a_failing_read_refuses_naming_the_store(tmp_path: Path) -> None:
    """A store whose table is gone is a named refusal, not a driver traceback."""
    data_dir = _write_stores(tmp_path)
    with closing(sqlite3.connect(data_dir / MARKETFEED_FILE_NAME)) as marketfeed:
        marketfeed.execute("DROP TABLE preimages")
        marketfeed.commit()
    with pytest.raises(Cp3RunnerRefusal, match="read failed"):
        read_bar_evidence(data_dir, [_raw_event_id(_BARS[0][0])])


def test_a_store_path_with_a_query_character_is_still_read_only(
    tmp_path: Path,
) -> None:
    """``as_uri()`` percent-encodes ``?``, so the path is not cut at the query."""
    data_dir = _write_stores(tmp_path)
    odd = tmp_path / "data?x"
    odd.mkdir()
    for name in (MARKETFEED_FILE_NAME, INBOX_FILE_NAME, EVIDENCE_FILE_NAME):
        (data_dir / name).rename(odd / name)
    joined = read_bar_evidence(odd, [_raw_event_id(_BARS[1][0])])
    assert joined[_raw_event_id(_BARS[1][0])].event_id == "event-1"


def test_an_unreadable_value_view_refuses_the_view_not_the_run(tmp_path: Path) -> None:
    """A view the kernel model rejects is named; half of it is never used."""
    data_dir = _write_stores(tmp_path)
    with closing(sqlite3.connect(data_dir / INBOX_FILE_NAME)) as inbox:
        inbox.execute(
            "UPDATE events SET payload_json = ? WHERE event_id = ?",
            (
                json.dumps(
                    {
                        "decision_tick": {
                            "capsule": {
                                "critical_input_snapshot": {"snapshot_id": "cis-2"}
                            },
                            "value_view": {"values": [], "snapshot_id": ""},
                        }
                    }
                ),
                "event-2",
            ),
        )
        inbox.commit()
    report = inspect_session(
        journal_path=_write_journal(tmp_path),
        strategy_path=STRATEGY_PATH,
        bindings_path=BINDINGS_PATH,
        data_dir=data_dir,
    )
    row = report.bars[2]
    assert row.evaluation == EVALUATION_JOURNAL_UNJOINED
    assert row.counted is False
    evidence = row.evidence
    assert evidence is not None
    assert evidence.value_view is None
    assert "not a readable ContextValueView" in (evidence.value_view_refusal or "")
    assert len(report.view_refusal_counts) == 1
