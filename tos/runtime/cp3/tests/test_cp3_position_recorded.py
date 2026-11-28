"""A RECORDED session shows the position the engine read, never a simulation (plan P4 S3)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
from tos.dsl import PositionSide, flat_position_context, project_position_context
from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME, INBOX_FILE_NAME

from ..inspect_evidence import DECISION_TICK_KIND, POSITION_CONTEXT_ABSENT_KIND
from ..inspect_report import InspectReport, position_text, render_json, render_text
from ..inspect_session import inspect_session
from ..position_sim import POSITION_MODE_RECORDED, SCHEME
from . import _position_tree as tree

_BASE_AS_OF_MS = 1_794_268_800_000

_MINUTE_MS = 60_000

_ENTRY_PRICE = 100_000

# SAFETY: 기록된 포지션이 보고 있던 가격은 봉의 close_x100 과 다르게 둔다 — 같으면 점검이 기록을 읽었는지 시뮬레이션을 돌렸는지 이 테스트가 구별하지 못한다
_RECORDED_MARK_PRICE = 99_500

_UNSETTLED = "QUANTITY_UNSETTLED"

_PRESENT = "PRESENT"

_STORE_READ_FAILED = "STORE_READ_FAILED"

_BARS: tuple[tuple[bool, int, int], ...] = (
    (True, 11, 14),
    (False, 21, 24),
    (False, 31, 34),
    (False, 41, 44),
    (False, 51, 54),
)


def _raw_event_id(index: int) -> str:
    """One bar's join key."""
    return f"{tree.INSTRUMENT}:1m:synthetic-{index:05d}"


def _as_of(index: int) -> int:
    """One bar's labelled minute."""
    return _BASE_AS_OF_MS + index * _MINUTE_MS


# SAFETY: each row carries ITS OWN bar's as_of, exactly as the scheduler stamps it (the view's newest as_of) — stamping every row with one bar's as_of would leave the join rule this fixture exists to pin untested
_ABSENCE_ROWS: tuple[tuple[int, str, int], ...] = (
    (30, _UNSETTLED, _as_of(2)),
    (50, _PRESENT, _as_of(4)),
)


def _journal(root: Path, bars: Sequence[tuple[bool, int, int]] = _BARS) -> Path:
    """The journal for ``bars``, in the producer's own five-key line shape."""
    lines = [
        json.dumps(
            {
                "raw_event_id": _raw_event_id(index),
                "source_id": "tos-cp3-s3-test/0.1.0",
                "instrument": tree.INSTRUMENT,
                "as_of_ms": _as_of(index),
                "fields": {
                    tree.PRICE_FIELD: _ENTRY_PRICE,
                    "entry_window": window,
                },
            },
            sort_keys=True,
        )
        for index, (window, _started, _consumed) in enumerate(bars)
    ]
    path = root / "journal.jsonl"
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def _value_view(index: int, window: bool) -> dict[str, Any]:
    """One tick's stored value view, in its dumped shape."""
    return {
        "snapshot_id": f"cis-{index}",
        "snapshot_canonical_digest": f"digest-{index}",
        "canonical_digest": f"view-digest-{index}",
        "canonicalization_version": SCHEME.version,
        "values": [
            {
                "field_key": key,
                "value": value,
                "as_of": _as_of(index),
                "payload_digest": f"payload-{index}",
                "observation_ref": _raw_event_id(index),
            }
            for key, value in sorted(
                {tree.PRICE_FIELD: _ENTRY_PRICE, "entry_window": window}.items()
            )
        ],
    }


def _dumped(context: Any) -> dict[str, Any]:
    """One kernel-built position context in the shape the inbox payload stores."""
    payload: dict[str, Any] = context.model_dump(mode="json")
    return payload


def _tampered(payload: dict[str, Any]) -> dict[str, Any]:
    """A stored context whose digest no longer binds its own content."""
    return {**payload, "unrealized_bp": 0}


def _stored_position(
    index: int, *, positions: bool = True, tamper: int | None = None
) -> dict[str, Any] | None:
    """The position the ENGINE recorded for bar ``index``, built by the kernel itself."""
    if not positions:
        return None
    if index == tamper:
        held = _stored_position(index)
        return None if held is None else _tampered(held)
    if index in (0, 4):
        return _dumped(
            flat_position_context(
                source_ref=(
                    f"scope:{tree.ACCOUNT}::{tree.INSTRUMENT}@evidence:{index + 1}"
                ),
                as_of=_as_of(index),
                scheme=SCHEME,
            )
        )
    if index == 1:
        return _dumped(
            project_position_context(
                side=PositionSide.LONG,
                held_qty=1,
                entry_price=_ENTRY_PRICE,
                entry_price_basis="ORDER",
                entry_as_of=_as_of(0),
                price=_RECORDED_MARK_PRICE,
                as_of=_as_of(index),
                bar_interval_ms=tree.BAR_INTERVAL_MS,
                source_ref="attempt:att-1@rcl:1:7",
                scheme=SCHEME,
            )
        )
    # SAFETY: 봉 2·3 은 키가 없다 — 라이브에서 이름공간이 빠진 봉이 그렇고, 빈 매핑을 넣으면 «형이 다 비어 있는 포지션» 이 되어 부재와 구별되지 않는다
    return None


def _tick_payload(
    index: int, *, window: bool, positions: bool, tamper: int | None
) -> str:
    """One inbox ``DECISION_TICK`` payload: its capsule, view, and stored position."""
    tick: dict[str, Any] = {
        "capsule": {"critical_input_snapshot": {"snapshot_id": f"cis-{index}"}},
        "value_view": _value_view(index, window),
    }
    position = _stored_position(index, positions=positions, tamper=tamper)
    if position is not None:
        tick["position_context"] = position
    return json.dumps({"decision_tick": tick})


@contextmanager
def _store(path: Path, version: int) -> Iterator[sqlite3.Connection]:
    """A fresh store file stamped with ``version``, committed and closed on exit."""
    connection = sqlite3.connect(path)
    with closing(connection):
        connection.execute(f"PRAGMA user_version = {version}")
        yield connection
        connection.commit()


def _write_stores(
    root: Path,
    *,
    bars: Sequence[tuple[bool, int, int]] = _BARS,
    absence: Sequence[tuple[int, str, int]] = _ABSENCE_ROWS,
    positions: bool = True,
    tamper: int | None = None,
) -> Path:
    """The three-store durable set the recorded bars need."""
    data_dir = root / "data"
    data_dir.mkdir()
    with _store(
        data_dir / MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
    ) as marketfeed:
        marketfeed.execute(
            "CREATE TABLE preimages (snapshot_id TEXT NOT NULL, "
            "raw_event_id TEXT NOT NULL, preimage_json TEXT NOT NULL, "
            "PRIMARY KEY (snapshot_id, raw_event_id))"
        )
        marketfeed.executemany(
            "INSERT INTO preimages VALUES (?, ?, ?)",
            [
                (f"cis-{index}", _raw_event_id(index), "{}")
                for index in range(len(bars))
            ],
        )
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
                    _tick_payload(
                        index, window=window, positions=positions, tamper=tamper
                    ),
                    consumed,
                    started,
                )
                for index, (window, started, consumed) in enumerate(bars)
            ],
        )
    with _store(data_dir / EVIDENCE_FILE_NAME, EVIDENCE_SCHEMA_VERSION) as evidence:
        evidence.execute(
            "CREATE TABLE entries (seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, "
            "payload_json TEXT NOT NULL)"
        )
        evidence.executemany(
            "INSERT INTO entries VALUES (?, ?, ?)",
            list(_evidence_rows(bars, absence)),
        )
    return data_dir


def _evidence_rows(
    bars: Sequence[tuple[bool, int, int]],
    absence: Sequence[tuple[int, str, int]],
) -> Iterator[tuple[int, str, str]]:
    """Every evidence row: the per-tick window marks plus the absence-reason changes."""
    for _window, started, consumed in bars:
        yield started, "EVENT_HANDLING_STARTED", _entry({})
        yield (
            consumed,
            "EVENT_CONSUMED",
            _entry({"halt_reason": None, "flow_fingerprint": {"halt_step": None}}),
        )
    for seq, reason, as_of_ms in absence:
        yield (
            seq,
            POSITION_CONTEXT_ABSENT_KIND,
            _entry(
                {
                    "instrument": tree.INSTRUMENT,
                    "reason": reason,
                    "bound_refusal": None,
                    "as_of_ms": as_of_ms,
                }
            ),
        )


def _entry(payload: dict[str, Any]) -> str:
    """The stored evidence envelope: a ``masked_keys`` wrapper around the payload."""
    return json.dumps({"masked_keys": [], "payload": payload})


@pytest.fixture
def recorded(tmp_path: Path) -> InspectReport:
    """The five recorded bars, inspected against a position-enabled tenant tree."""
    config_dir = tree.write_tree(tmp_path)
    return inspect_session(
        journal_path=_journal(tmp_path),
        strategy_path=config_dir / "strategies" / tree.STRATEGY_FILE_NAME,
        bindings_path=config_dir / "strategy_bindings.yaml",
        data_dir=_write_stores(tmp_path),
        session_name="s3-recorded",
    )


def test_a_recorded_session_is_read_not_simulated(recorded: InspectReport) -> None:
    """The stored context is marked recorded, and no fill model is published."""
    assert recorded.position_mode == POSITION_MODE_RECORDED
    assert recorded.position_simulation is None
    assert recorded.round_trips == ()
    assert {row.position_source for row in recorded.bars} == {POSITION_MODE_RECORDED}


def test_the_stored_position_decides_the_bar_a_simulation_would_not(
    recorded: InspectReport,
) -> None:
    """Bar 1's view shows no loss; the engine's own stored context shows -50bp."""
    row = recorded.bars[1]
    assert row.env_values[tree.PRICE_FIELD] == _ENTRY_PRICE
    assert row.position is not None
    assert row.position["unrealized_bp"] == tree.STOP_LOSS_BP
    assert row.rules[0].compares[1].passed is True
    assert row.decision_rule_id == tree.STOP_RULE_ID


def test_a_tick_with_no_stored_position_carries_the_recorded_reason_forward(
    recorded: InspectReport,
) -> None:
    """The row is written on CHANGE only, so bars 2 and 3 share the one reason."""
    assert [row.position_absent_reason for row in recorded.bars] == [
        None,
        None,
        _UNSETTLED,
        _UNSETTLED,
        None,
    ]
    assert recorded.bars[2].position is None
    assert recorded.bars[3].position is None
    assert recorded.position_absence_counts == {_UNSETTLED: 2}


def test_a_present_row_clears_the_absence(recorded: InspectReport) -> None:
    """``PRESENT`` ends the streak, so the later bar shows its stored FLAT context."""
    assert recorded.bars[4].position == {"side": "FLAT", "held_qty": 0}
    assert recorded.bars[4].position_absent_reason is None


def test_absent_position_rules_are_all_false_not_an_error(
    recorded: InspectReport,
) -> None:
    """No namespace means every position comparison narrows to False, and nothing fires."""
    row = recorded.bars[2]
    assert [compare.passed for compare in row.rules[0].compares] == [False, False]
    assert row.decision_rule_id == tree.DEFAULT_RULE_ID


def test_a_recorded_report_prints_no_round_trip_block(recorded: InspectReport) -> None:
    """A round-trip block here would read as a session that traded, not one not simulated."""
    text = render_text(recorded)
    assert "position absent" in text
    assert "simulated round trips" not in text
    assert f"position  {POSITION_MODE_RECORDED}" in text


def test_the_json_carries_the_stored_position_per_bar(recorded: InspectReport) -> None:
    """``export_bars`` and the dashboard read these keys, so they are additive and typed."""
    document = json.loads(render_json(recorded))
    assert document["position"]["mode"] == POSITION_MODE_RECORDED
    assert document["bars"][1]["position"]["unrealized_bp"] == tree.STOP_LOSS_BP
    assert document["bars"][2]["position"] is None
    assert document["bars"][2]["position_absent_reason"] == _UNSETTLED
    assert document["bars"][1]["evidence"]["position_context"]["side"] == "LONG"
    assert document["summary"]["position_absent"] == {_UNSETTLED: 2}
    assert document["position"]["live_gap"] is None


# SAFETY: both handling windows (20-21, 22-23) sit AFTER both absence rows (seq 5 and 8) on purpose — that is the recovery-queued order this fixture reproduces, and renumbering them ascending would make the test pass under a seq-keyed join too
_QUEUED_BARS: tuple[tuple[bool, int, int], ...] = ((False, 20, 21), (False, 22, 23))


@pytest.mark.parametrize(
    ("absence", "expected"),
    [
        (((5, _UNSETTLED, _as_of(0)), (8, _PRESENT, _as_of(1))), [_UNSETTLED, None]),
        (
            ((5, _UNSETTLED, _as_of(0)), (8, _STORE_READ_FAILED, _as_of(1))),
            [_UNSETTLED, _STORE_READ_FAILED],
        ),
    ],
    ids=("later-bar-present", "later-bar-absent-for-another-reason"),
)
def test_a_tick_handled_at_recovery_keeps_its_own_bars_reason(
    tmp_path: Path,
    absence: tuple[tuple[int, str, int], ...],
    expected: list[str | None],
) -> None:
    """The reason is joined by the row's own as_of, not by the seq recovery handled it at."""
    config_dir = tree.write_tree(tmp_path)
    report = inspect_session(
        journal_path=_journal(tmp_path, _QUEUED_BARS),
        strategy_path=config_dir / "strategies" / tree.STRATEGY_FILE_NAME,
        bindings_path=config_dir / "strategy_bindings.yaml",
        data_dir=_write_stores(
            tmp_path, bars=_QUEUED_BARS, absence=absence, positions=False
        ),
        session_name="s3-queued-until-recovery",
    )
    assert [row.position_absent_reason for row in report.bars] == expected
    assert [row.position for row in report.bars] == [None, None]


@pytest.fixture
def tampered(tmp_path: Path) -> InspectReport:
    """The same five bars, but bar 1's stored context no longer binds its own digest."""
    config_dir = tree.write_tree(tmp_path)
    return inspect_session(
        journal_path=_journal(tmp_path),
        strategy_path=config_dir / "strategies" / tree.STRATEGY_FILE_NAME,
        bindings_path=config_dir / "strategy_bindings.yaml",
        data_dir=_write_stores(tmp_path, tamper=1),
        session_name="s3-tampered",
    )


def test_a_refused_stored_context_says_so_instead_of_reading_as_absent(
    tampered: InspectReport,
) -> None:
    """``absent:-`` would read as «the engine had no position» on a REJECTED record."""
    row = tampered.bars[1]
    assert row.position is None
    assert row.position_absent_reason is None
    assert row.evidence is not None
    assert row.evidence.position_context_refusal is not None
    assert position_text(row) == "refused:NOT_A_READABLE_CONTEXT"
    assert "refused:NOT_A_READABLE_CONTEXT" in render_text(tampered)
    document = json.loads(render_json(tampered))
    refusal = document["bars"][1]["evidence"]["position_context_refusal"]
    assert refusal.startswith("NOT_A_READABLE_CONTEXT:")
    assert row.decision_rule_id == tree.DEFAULT_RULE_ID
