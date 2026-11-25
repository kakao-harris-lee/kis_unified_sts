"""CP-3 §3.6 — the two session-derived B3 inputs, all hermetic."""

from __future__ import annotations

import ast
import json
import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import session_inputs as si

_REPO_ROOT = Path(__file__).resolve().parents[2]

HINGE = (
    _REPO_ROOT
    / "tos"
    / "runtime"
    / "tests"
    / "fixtures"
    / "cp3-session-store-reads.json"
)

INSTRUMENT = "A05611"


def _event_id(minute: str) -> str:
    """B1a's join key shape for a 2026-10-19 minute (``HHMM``)."""
    return f"{INSTRUMENT}:1m:20261019T{minute}00+0900"


@pytest.fixture(scope="module")
def hinge() -> dict[str, Any]:
    return json.loads(HINGE.read_text(encoding="utf-8"))


def _create_store(path: Path, spec: dict[str, Any], *, user_version: int) -> None:
    """A store carrying exactly the columns the hinge declares."""
    conn = sqlite3.connect(path)
    try:
        for table, columns in spec["reads"].items():
            body = ", ".join(f"{name} {kind}" for name, kind in columns.items())
            conn.execute(f"CREATE TABLE {table} ({body})")
        conn.execute(f"PRAGMA user_version = {user_version}")
        conn.commit()
    finally:
        conn.close()


def _window(index: int) -> tuple[int, int]:
    """Bar *index*'s durable handling window, as the driver would write it."""
    return (100 * index, 100 * index + 99)


def _seq(index: int, offset: int = 1) -> int:
    """An evidence seq INSIDE bar *index*'s handling window."""
    assert 1 <= offset <= 99, "an offset outside the window is another bar's seq"
    return 100 * index + offset


SNAPSHOT_SHAPES = ("fresh", "stale_by_age", "absent_field", "unprojectable")


def _snapshot_json(hinge: dict[str, Any], name: str, *, snapshot_id: str) -> str:
    """One committed snapshot's bytes, re-keyed to *snapshot_id*."""
    document = json.loads(
        hinge["payloads"]["marketfeed_snapshots"][name]["snapshot_json"]
    )
    document["snapshot_id"] = snapshot_id
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def _preimage_json(hinge: dict[str, Any], name: str) -> str:
    """The tokens that snapshot's observation attested, as the store wrote them."""
    return str(hinge["payloads"]["marketfeed_snapshots"][name]["preimage_json"])


def _write_session(
    tmp_path: Path,
    hinge: dict[str, Any],
    *,
    snapshots: list[tuple[str, str, int]] | list[tuple[str, str, int, str]],
    preimages: list[tuple[str, str]] | list[tuple[str, str, str]],
    entries: list[tuple[int, str, str]] | None = None,
    ticks: (
        list[tuple[int, str]] | list[tuple[int, str, int | None, int | None]] | None
    ) = None,
    marketfeed_version: int | None = None,
    evidence_version: int | None = None,
    inbox_version: int | None = None,
    skip_inbox: bool = False,
) -> Path:
    """A session data dir holding the three stores, with the given rows."""
    data_dir = tmp_path / "data" / INSTRUMENT
    data_dir.mkdir(parents=True, exist_ok=True)

    market = data_dir / hinge["marketfeed"]["file_name"]
    _create_store(
        market,
        hinge["marketfeed"],
        user_version=(
            hinge["marketfeed"]["schema_version"]
            if marketfeed_version is None
            else marketfeed_version
        ),
    )
    conn = sqlite3.connect(market)
    try:
        conn.executemany(
            "INSERT INTO snapshots "
            "(snapshot_id, instrument, as_of_ms, snapshot_json) VALUES (?, ?, ?, ?)",
            [
                (
                    row
                    if len(row) == 4
                    else (*row, _snapshot_json(hinge, "fresh", snapshot_id=row[0]))
                )
                for row in snapshots
            ],
        )
        conn.executemany(
            "INSERT INTO preimages (snapshot_id, raw_event_id, preimage_json) "
            "VALUES (?, ?, ?)",
            [
                row if len(row) == 3 else (*row, _preimage_json(hinge, "fresh"))
                for row in preimages
            ],
        )
        conn.commit()
    finally:
        conn.close()

    if not skip_inbox:
        inbox = data_dir / hinge["inbox"]["file_name"]
        _create_store(
            inbox,
            hinge["inbox"],
            user_version=(
                hinge["inbox"]["schema_version"]
                if inbox_version is None
                else inbox_version
            ),
        )
        conn = sqlite3.connect(inbox)
        try:
            conn.executemany(
                "INSERT INTO events (seq, kind, payload_json, "
                "handling_started_evidence_seq, consumed_evidence_seq) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        row[0],
                        "DECISION_TICK",
                        row[1],
                        *(row[2:] if len(row) == 4 else _window(index)),
                    )
                    for index, row in enumerate(ticks or [])
                ],
            )
            conn.commit()
        finally:
            conn.close()

    if entries is not None or evidence_version is not None:
        evidence = data_dir / hinge["evidence"]["file_name"]
        _create_store(
            evidence,
            hinge["evidence"],
            user_version=(
                hinge["evidence"]["schema_version"]
                if evidence_version is None
                else evidence_version
            ),
        )
        conn = sqlite3.connect(evidence)
        try:
            conn.executemany("INSERT INTO entries VALUES (?, ?, ?)", entries or [])
            conn.commit()
        finally:
            conn.close()
    return data_dir


def _real_entry(hinge: dict[str, Any], kind: str) -> str:
    """The committed ``payload_json`` string for one evidence kind."""
    for entry in hinge["payloads"]["evidence_entries"]:
        if entry["kind"] == kind:
            return str(entry["payload_json"])
    raise AssertionError(f"the fixture carries no {kind} entry")


def _real_record(hinge: dict[str, Any], kind: str) -> dict[str, Any]:
    """That entry's ENGINE RECORD — one level inside the store's wrapper."""
    record: dict[str, Any] = json.loads(_real_entry(hinge, kind))["payload"]
    return record


def _entry(record: Mapping[str, Any]) -> str:
    """Re-wrap a (possibly edited) engine record the way the store does."""
    return json.dumps(
        {"payload": dict(record), "masked_keys": []},
        sort_keys=True,
        separators=(",", ":"),
    )


def _real_tick(hinge: dict[str, Any], index: int) -> str:
    """The committed ``payload_json`` of one admitted ``DECISION_TICK``."""
    return str(hinge["payloads"]["inbox_events"][index]["payload_json"])


def _tick_ids(hinge: dict[str, Any], index: int) -> tuple[str, str]:
    """``(capsule_id, snapshot_id)`` of that committed tick."""
    capsule = json.loads(_real_tick(hinge, index))["decision_tick"]["capsule"]
    return capsule["capsule_id"], capsule["critical_input_snapshot"]["snapshot_id"]


def _tick_with(hinge: dict[str, Any], index: int, **capsule_fields: Any) -> str:
    """A committed tick with its capsule ids replaced — for the join's reds."""
    event = json.loads(_real_tick(hinge, index))
    capsule = event["decision_tick"]["capsule"]
    for key, value in capsule_fields.items():
        if key == "snapshot_id":
            capsule["critical_input_snapshot"]["snapshot_id"] = value
        else:
            capsule[key] = value
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Bar:
    """One consumed bar, as the three stores jointly describe it."""

    capsule_id: str
    snapshot_id: str
    raw_event_id: str
    as_of_ms: int
    tick_payload: str
    snapshot_json: str
    preimage_json: str
    window: tuple[int | None, int | None]


def _bars(
    hinge: dict[str, Any], count: int, *, states: list[str] | None = None
) -> list[Bar]:
    """``count`` bars whose ticks are the COMMITTED ones where there are any."""
    bars: list[Bar] = []
    committed = len(hinge["payloads"]["inbox_events"])
    for index in range(count):
        if index < committed:
            capsule_id, snapshot_id = _tick_ids(hinge, index)
            payload = _real_tick(hinge, index)
        else:
            capsule_id = f"dcc-fixture-{index}"
            snapshot_id = f"cis-fixture-{index}"
            payload = _tick_with(
                hinge, 0, capsule_id=capsule_id, snapshot_id=snapshot_id
            )
        bars.append(
            Bar(
                capsule_id=capsule_id,
                snapshot_id=snapshot_id,
                raw_event_id=_event_id(f"09{index:02d}"),
                as_of_ms=1_760_000_000_000 + index * 60_000,
                tick_payload=payload,
                snapshot_json=_snapshot_json(
                    hinge,
                    "fresh" if states is None else states[index],
                    snapshot_id=snapshot_id,
                ),
                preimage_json=_preimage_json(
                    hinge, "fresh" if states is None else states[index]
                ),
                window=_window(index),
            )
        )
    return bars


def _session(
    tmp_path: Path,
    hinge: dict[str, Any],
    bars: list[Bar],
    *,
    entries: list[tuple[int, str, str]] | None = None,
    **kwargs: Any,
) -> Path:
    """A session dir whose three stores agree about *bars*."""
    return _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=_preimage_rows(bars),
        ticks=_tick_rows(bars),
        entries=entries,
        **kwargs,
    )


def _snapshot_rows(bars: list[Bar]) -> list[tuple[str, str, int, str]]:
    """The ``snapshots`` rows for *bars*, carrying each one's committed bytes."""
    return [
        (bar.snapshot_id, INSTRUMENT, bar.as_of_ms, bar.snapshot_json) for bar in bars
    ]


def _preimage_rows(bars: list[Bar]) -> list[tuple[str, str, str]]:
    """The ``preimages`` rows for *bars*, each with its own committed tokens."""
    return [(bar.snapshot_id, bar.raw_event_id, bar.preimage_json) for bar in bars]


def _tick_rows(bars: list[Bar]) -> list[tuple[int, str, int | None, int | None]]:
    """The ``events`` rows for *bars*, each with its own handling window."""
    return [
        (index + 1, bar.tick_payload, bar.window[0], bar.window[1])
        for index, bar in enumerate(bars)
    ]


def _three_bar_session(tmp_path: Path, hinge: dict[str, Any], **kwargs: Any) -> Path:
    """Three consumed bars: 09:00, 09:01, 09:02, in that order."""
    return _session(tmp_path, hinge, _bars(hinge, 3), **kwargs)


def test_consumed_ids_are_the_preimage_rows(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """The id filter is what the runtime actually covered, nothing inferred."""
    data_dir = _three_bar_session(tmp_path, hinge)
    document = _document(tmp_path, data_dir)

    assert document["raw_event_ids"] == [
        _event_id("0900"),
        _event_id("0901"),
        _event_id("0902"),
    ]
    assert document["instrument"] == INSTRUMENT
    assert document["counts"]["snapshots"] == 3
    assert document["counts"]["consumed_raw_event_ids"] == 3
    assert document["unpaired_reasons"] == {}
    assert document["counts"]["unpaired"] == 0
    assert document["generated_from"]["marketfeed_sqlite3"]["sha256"]


@pytest.mark.parametrize("store", ["marketfeed", "evidence", "inbox"])
def test_red_a_store_at_another_schema_version_is_refused(
    tmp_path: Path, hinge: dict[str, Any], store: str
) -> None:
    """**Guard: the mirrored schema version, on each of the three stores.**"""
    bumped = hinge[store]["schema_version"] + 1
    bars = _bars(hinge, 1)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[(1, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
        **{f"{store}_version": bumped},
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.live_decision_records(data_dir)
    assert f"user_version={bumped}" in str(excinfo.value)
    assert store in str(excinfo.value)


@pytest.mark.parametrize("covered", [0, 2])
def test_red_a_snapshot_without_exactly_one_preimage_is_refused(
    tmp_path: Path, hinge: dict[str, Any], covered: int
) -> None:
    """**Guard: one snapshot covers one observation.**"""
    extra = [("snap-1", _event_id("0859"))] if covered == 2 else []
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[("snap-1", INSTRUMENT, 1_760_000_000_000)],
        preimages=([("snap-1", _event_id("0900"))] if covered else []) + extra,
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        _document(tmp_path, data_dir)
    assert f"covers {covered} preimage row(s)" in str(excinfo.value)


def test_red_two_instruments_in_one_session_are_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: a tenant session is one instrument.**"""
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[
            ("snap-1", INSTRUMENT, 1_760_000_000_000),
            ("snap-2", "A05612", 1_760_000_060_000),
        ],
        preimages=[
            ("snap-1", _event_id("0900")),
            ("snap-2", "A05612:1m:20261019T090100+0900"),
        ],
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        _document(tmp_path, data_dir)
    assert "A05612" in str(excinfo.value)


def test_red_a_session_that_consumed_nothing_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: an empty filter is not a filter.**"""
    data_dir = _write_session(tmp_path, hinge, snapshots=[], preimages=[])
    with pytest.raises(si.SessionInputsError) as excinfo:
        _document(tmp_path, data_dir)
    assert "holds no snapshots" in str(excinfo.value)


def test_unpaired_bars_carry_the_producers_own_reason(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """Plan §5: pre-boot / ``skipped_behind`` / ``produce_error`` /"""
    data_dir = _three_bar_session(tmp_path, hinge)
    producer_log = tmp_path / "producer-log.jsonl"
    producer_log.write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                {"stage": "published", "raw_event_id": _event_id("0900")},
                {"stage": "published", "raw_event_id": _event_id("0901")},
                {"stage": "published", "raw_event_id": _event_id("0902")},
                {"stage": "published", "raw_event_id": _event_id("0858")},
                {"stage": "published", "raw_event_id": _event_id("0903")},
                {"stage": "skipped_behind", "raw_event_id": _event_id("0845")},
                {"stage": "produce_error", "raw_event_id": _event_id("0846")},
                {"stage": "omitted_unusable", "raw_event_id": _event_id("0847")},
                {"stage": "missing_no_successor", "raw_event_id": _event_id("0848")},
                {"stage": "late_completed", "raw_event_id": _event_id("0848")},
                {
                    "stage": "already_frozen_not_published",
                    "raw_event_id": _event_id("0847"),
                },
                {"stage": "page_did_not_reach_back", "last_frozen": "09:01"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    boot_snapshot = tmp_path / "boot-journal-snapshot.json"
    boot_snapshot.write_text(
        json.dumps({"pre_boot_raw_event_ids": [_event_id("0858")]}), encoding="utf-8"
    )

    document = si.build_consumed_ids_document(
        data_dir=data_dir, producer_log=producer_log, boot_snapshot=boot_snapshot
    )

    assert document["unpaired_reasons"] == {
        _event_id("0845"): "skipped_behind",
        _event_id("0846"): "produce_error",
        _event_id("0847"): "omitted_unusable",
        _event_id("0848"): "late_completed",
        _event_id("0858"): si.REASON_PRE_BOOT,
        _event_id("0903"): si.REASON_UNCONSUMED_AFTER_BOOT,
    }
    assert document["unpaired_reason_counts"] == {
        "late_completed": 1,
        "omitted_unusable": 1,
        "pre_boot": 1,
        "produce_error": 1,
        "published_not_consumed": 1,
        "skipped_behind": 1,
    }
    assert document["counts"]["pre_boot_lines_at_boot"] == 1
    assert document["pre_boot_raw_event_ids"] == [_event_id("0858")]


def test_the_document_carries_an_empty_pre_boot_list_when_the_journal_was_empty(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """``[]`` is a measurement; a MISSING key would be "did not say"."""
    data_dir = _three_bar_session(tmp_path, hinge)

    document = _document(tmp_path, data_dir)

    assert document["pre_boot_raw_event_ids"] == []
    assert document["counts"]["pre_boot_lines_at_boot"] == 0


def _stamp(hhmmss: str) -> int:
    """Epoch ms of a 2026-10-19 KST wall clock — what the journal stamps."""
    return int(
        datetime.strptime(f"20261019T{hhmmss}+0900", "%Y%m%dT%H%M%S%z").timestamp()
        * 1000
    )


def _close_log(tmp_path: Path, *events: dict[str, Any], seeded: bool = True) -> Path:
    producer_log = tmp_path / "producer-log.jsonl"
    seed = [{"stage": "seed", "session_window": "08:45:00..15:45:00"}] if seeded else []
    producer_log.write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                *seed,
                {"stage": "published", "raw_event_id": _event_id("0900")},
                {"stage": "published", "raw_event_id": _event_id("0901")},
                {"stage": "published", "raw_event_id": _event_id("0902")},
                *events,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return producer_log


def test_a_line_stamped_at_or_after_the_close_is_not_counted_as_a_miss(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Plan §5 M5's second count, and the session's own last bar.**"""
    data_dir = _three_bar_session(tmp_path, hinge)
    producer_log = _close_log(
        tmp_path,
        {
            "stage": "published",
            "raw_event_id": _event_id("1543"),
            "as_of_ms": _stamp("154459"),
        },
        {
            "stage": "published",
            "raw_event_id": _event_id("1544"),
            "as_of_ms": _stamp("154500"),
        },
        {
            "stage": "published",
            "raw_event_id": _event_id("1545"),
            "as_of_ms": _stamp("154602"),
        },
    )
    document = _document(tmp_path, data_dir, producer_log=producer_log)

    assert document["unpaired_reasons"] == {
        _event_id("1543"): si.REASON_UNCONSUMED_AFTER_BOOT,
        _event_id("1544"): si.REASON_PUBLISHED_AFTER_CLOSE,
        _event_id("1545"): si.REASON_PUBLISHED_AFTER_CLOSE,
    }
    assert document["unpaired_reason_counts"] == {
        si.REASON_UNCONSUMED_AFTER_BOOT: 1,
        si.REASON_PUBLISHED_AFTER_CLOSE: 2,
    }
    assert document["generated_from"]["producer_session_close"] == "15:45:00"


@pytest.mark.serial
def test_the_close_is_built_in_the_bars_own_offset_not_the_hosts_timezone(
    tmp_path: Path, hinge: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**PR #904 review round 1 LOW 5 — pin the tz handling.**"""
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    try:
        data_dir = _three_bar_session(tmp_path, hinge)
        producer_log = _close_log(
            tmp_path,
            {
                "stage": "published",
                "raw_event_id": _event_id("1545"),
                "as_of_ms": _stamp("154602"),
            },
        )
        document = _document(tmp_path, data_dir, producer_log=producer_log)
    finally:
        monkeypatch.undo()
        time.tzset()

    assert document["unpaired_reasons"] == {
        _event_id("1545"): si.REASON_PUBLISHED_AFTER_CLOSE
    }


@pytest.mark.parametrize(
    ("seeded", "stamped"),
    [
        pytest.param(False, True, id="no-seed-record"),
        pytest.param(True, False, id="no-stamp"),
    ],
)
def test_red_a_close_that_cannot_be_decided_leaves_the_defect_name(
    tmp_path: Path, hinge: dict[str, Any], seeded: bool, stamped: bool
) -> None:
    """**An unanswerable question is not a clean answer.**"""
    data_dir = _three_bar_session(tmp_path, hinge)
    event: dict[str, Any] = {
        "stage": "published",
        "raw_event_id": _event_id("1545"),
    }
    if stamped:
        event["as_of_ms"] = _stamp("154602")
    producer_log = _close_log(tmp_path, event, seeded=seeded)
    document = _document(tmp_path, data_dir, producer_log=producer_log)

    assert document["unpaired_reasons"] == {
        _event_id("1545"): si.REASON_UNCONSUMED_AFTER_BOOT
    }
    assert document["generated_from"]["producer_session_close"] == (
        "15:45:00" if seeded else None
    )


def test_red_a_boot_snapshot_without_the_pre_boot_list_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: the boot snapshot must be the runner's own.**"""
    data_dir = _three_bar_session(tmp_path, hinge)
    boot_snapshot = tmp_path / "boot.json"
    boot_snapshot.write_text(json.dumps({"captured_at_kst": "09:05"}), encoding="utf-8")
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.build_consumed_ids_document(data_dir=data_dir, boot_snapshot=boot_snapshot)
    assert "pre_boot_raw_event_ids" in str(excinfo.value)


def _unscoped(records: list[dict[str, Any]], ticks: Any) -> si.LiveScope:
    """A scope that filters nothing — for the tests whose subject is the COUNTS."""
    return si.LiveScope(
        session_day=None,
        days_present=(),
        records_all_days=len(records),
        ticks_all_days=len(ticks),
        ticks_with_no_resolvable_day=0,
    )


def _event_id_on(day: str, minute: str) -> str:
    """A join key on another KST day — what an accumulating leaf holds."""
    return f"{INSTRUMENT}:1m:{day}T{minute}00+0900"


def _emitted(hinge: dict[str, Any], bar: Bar, **edits: Any) -> str:
    """The committed emitted-outcome entry, re-keyed to *bar*."""
    record = _real_record(hinge, "DECISION_OUTCOME_EMITTED")
    record["capsule_id"] = bar.capsule_id
    record.update(edits)
    return _entry(record)


def _withheld(hinge: dict[str, Any], **edits: Any) -> str:
    """The committed withheld entry — it names no capsule, by construction."""
    record = _real_record(hinge, "DECISION_WITHHELD")
    record.update(edits)
    assert record.get("capsule_id") is None, "the fixture's withheld row grew a capsule"
    return _entry(record)


def _flow_halted(hinge: dict[str, Any], reason: str) -> str:
    record = _real_record(hinge, "FLOW_HALTED")
    record["halt_reason"] = reason
    return _entry(record)


def test_live_decisions_are_keyed_to_their_bar_by_capsule_id(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**The join (Claude-lane MEDIUM M1), on real bytes (BLOCKER B1).**"""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0, 1), "ATTESTED_INPUTS", _entry({"ignored": True})),
            (_seq(0, 2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (_seq(1, 2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[1])),
            (_seq(2, 2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[2])),
        ],
    )
    records = si.live_decision_records(data_dir)

    assert [record["raw_event_id"] for record in records] == [
        bar.raw_event_id for bar in bars
    ]
    assert [record["attributed_by"] for record in records] == ["capsule_id"] * 3
    assert {record["outcome_kind"] for record in records} == {"NO_ACTION"}
    assert [record["capsule_id"] for record in records] == [
        bar.capsule_id for bar in bars
    ]
    for record in records:
        assert set(record) >= {
            "raw_event_id",
            "as_of_ms",
            "outcome_kind",
            "rule_id",
            "capacity_denied",
        }
        assert record["rule_id"] is None
        assert record["capacity_denied"] is False
    assert records[0]["as_of_ms"] == bars[0].as_of_ms


def test_red_the_store_wrapper_is_read_through_not_as_the_record(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER B1's own red proof.**"""
    bars = _bars(hinge, 1)
    record = _real_record(hinge, "DECISION_OUTCOME_EMITTED")
    record["capsule_id"] = bars[0].capsule_id
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (
                1,
                "DECISION_OUTCOME_EMITTED",
                json.dumps(record, sort_keys=True, separators=(",", ":")),
            )
        ],
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.live_decision_records(data_dir)
    assert si.EVIDENCE_PAYLOAD_KEY in str(excinfo.value)


def test_red_a_shifted_sequence_is_attributed_by_key_not_by_position(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM M1's red proof: the shift the ordered pairing could not see.**"""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (_seq(2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[2])),
            (_seq(1), "DECISION_WITHHELD", _withheld(hinge)),
        ],
    )
    records = si.live_decision_records(data_dir)
    attributed = {record["raw_event_id"]: record for record in records}
    assert attributed[bars[0].raw_event_id]["attributed_by"] == "capsule_id"
    assert attributed[bars[2].raw_event_id]["attributed_by"] == "capsule_id"
    assert attributed[bars[2].raw_event_id]["evidence_seq"] == _seq(2)
    assert attributed[bars[1].raw_event_id]["attributed_by"] == "evidence_seq_range"
    assert attributed[bars[1].raw_event_id]["outcome_kind"] == si.NO_OUTCOME_KIND


def test_red_an_unkeyed_decision_goes_to_the_window_that_holds_it_not_the_next_bar(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R1's red proof — the reviewer's own sequence.**"""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0), "DECISION_WITHHELD", _withheld(hinge, detail="A_FOR_BAR1")),
            (
                _seq(1),
                "DECISION_TICK_DROPPED_ON_RECOVERY",
                _entry({"detail": "dropped"}),
            ),
            (_seq(2), "DECISION_WITHHELD", _withheld(hinge, detail="B_FOR_BAR3")),
        ],
    )
    records = si.live_decision_records(data_dir)
    placed = {record["raw_event_id"]: record["evidence_seq"] for record in records}
    assert placed == {bars[0].raw_event_id: _seq(0), bars[2].raw_event_id: _seq(2)}
    assert bars[1].raw_event_id not in placed
    assert [record["attributed_by"] for record in records] == ["evidence_seq_range"] * 2
    lineage = si.build_live_lineage(
        data_dir=data_dir,
        records=records,
        payload=si.render_jsonl(records),
        ticks=len(si.read_decision_ticks(data_dir)),
        scope=_unscoped(records, si.read_decision_ticks(data_dir)),
    )
    assert lineage["counts"]["ticks_without_a_decision"] == 1


def test_red_a_tick_queued_and_never_run_takes_no_record(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R1, the other shape: the held tick that never started.**"""
    bars = _bars(hinge, 3)
    held = bars[1]
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=_preimage_rows(bars),
        ticks=[
            (1, bars[0].tick_payload, *bars[0].window),
            (2, held.tick_payload, None, None),
            (3, bars[2].tick_payload, *bars[2].window),
        ],
        entries=[
            (_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (_seq(2), "DECISION_WITHHELD", _withheld(hinge)),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["raw_event_id"] for record in records] == [
        bars[0].raw_event_id,
        bars[2].raw_event_id,
    ]
    assert records[1]["attributed_by"] == "evidence_seq_range"


def test_red_a_keyed_record_outside_its_own_ticks_window_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard (MEDIUM R1's cross-check).**"""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[(_seq(1), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )
    with pytest.raises(si.SessionInputsError, match="outside it"):
        si.live_decision_records(data_dir)


def test_red_a_keyed_record_whose_tick_never_started_handling_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a decision naming a capsule whose inbox row"""
    bars = _bars(hinge, 1)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=_preimage_rows(bars[:1]),
        ticks=[(1, bars[0].tick_payload, None, None)],
        entries=[(_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )
    with pytest.raises(si.SessionInputsError, match="is NULL"):
        si.live_decision_records(data_dir)


def test_red_an_unkeyed_record_in_two_windows_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: bar 1's row was never marked consumed (a"""
    bars = _bars(hinge, 2)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=_preimage_rows(bars),
        ticks=[
            (1, bars[0].tick_payload, bars[0].window[0], None),
            (2, bars[1].tick_payload, *bars[1].window),
        ],
        entries=[(_seq(1), "DECISION_WITHHELD", _withheld(hinge))],
    )
    with pytest.raises(si.SessionInputsError, match="2 handling windows"):
        si.live_decision_records(data_dir)


def test_red_a_decision_naming_a_capsule_the_inbox_never_admitted_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a decision whose capsule id is not in the"""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (
                2,
                "DECISION_OUTCOME_EMITTED",
                _entry(
                    {
                        **_real_record(hinge, "DECISION_OUTCOME_EMITTED"),
                        "capsule_id": "dcc-never-admitted",
                    }
                ),
            ),
        ],
    )
    with pytest.raises(si.SessionInputsError, match="not one the inbox admitted"):
        si.live_decision_records(data_dir)


def test_red_two_decisions_on_one_tick_are_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: two emitted records naming the SAME capsule"""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (2, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
        ],
    )
    with pytest.raises(si.SessionInputsError, match="one tick, two decisions"):
        si.live_decision_records(data_dir)


def test_red_an_unkeyed_decision_in_no_window_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a withheld record whose evidence seq is"""
    bars = _bars(hinge, 1)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[(_seq(5), "DECISION_WITHHELD", _withheld(hinge))],
    )
    with pytest.raises(si.SessionInputsError, match="lies in NO admitted tick"):
        si.live_decision_records(data_dir)


def test_red_two_unkeyed_decisions_in_one_window_are_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: two withheld records inside ONE tick's"""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0, 1), "DECISION_WITHHELD", _withheld(hinge)),
            (_seq(0, 2), "DECISION_WITHHELD", _withheld(hinge)),
        ],
    )
    with pytest.raises(si.SessionInputsError, match="one tick, two decisions"):
        si.live_decision_records(data_dir)


def test_red_a_tick_whose_snapshot_is_missing_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: the inbox admitted a tick whose snapshot the"""
    bars = _bars(hinge, 1)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[("cis-other", INSTRUMENT, 1_760_000_000_000)],
        preimages=[("cis-other", _event_id("0900"))],
        ticks=[(1, bars[0].tick_payload)],
        entries=[(1, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )
    with pytest.raises(si.SessionInputsError, match="marketfeed store does not hold"):
        si.live_decision_records(data_dir)


def _append_consumed_bar(
    hinge: dict[str, Any], data_dir: Path, bar: Bar, *, tick_seq: int
) -> None:
    """Append one more consumed bar, in the RUNTIME's own write order."""
    conn = sqlite3.connect(data_dir / hinge["marketfeed"]["file_name"])
    try:
        conn.execute(
            "INSERT INTO snapshots "
            "(snapshot_id, instrument, as_of_ms, snapshot_json) VALUES (?, ?, ?, ?)",
            (bar.snapshot_id, INSTRUMENT, bar.as_of_ms, bar.snapshot_json),
        )
        conn.execute(
            "INSERT INTO preimages (snapshot_id, raw_event_id, preimage_json) "
            "VALUES (?, ?, ?)",
            (bar.snapshot_id, bar.raw_event_id, bar.preimage_json),
        )
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(data_dir / hinge["inbox"]["file_name"])
    try:
        conn.execute(
            "INSERT INTO events (seq, kind, payload_json, "
            "handling_started_evidence_seq, consumed_evidence_seq) "
            "VALUES (?, ?, ?, ?, ?)",
            (tick_seq, "DECISION_TICK", bar.tick_payload, *bar.window),
        )
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(data_dir / hinge["evidence"]["file_name"])
    try:
        conn.execute(
            "INSERT INTO entries VALUES (?, ?, ?)",
            (
                _seq(tick_seq - 1),
                "DECISION_OUTCOME_EMITTED",
                _emitted(hinge, bar),
            ),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("appended", [1, 3], ids=["after the first read", "at every"])
def test_a_bar_written_between_two_store_reads_is_not_a_lost_snapshot(
    tmp_path: Path,
    hinge: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    appended: int,
) -> None:
    """**The 2026-11-04 false refusal's red proof.**"""
    bars = _bars(hinge, 1 + appended)
    data_dir = _session(
        tmp_path,
        hinge,
        bars[:1],
        entries=[(_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )

    pending = iter(enumerate(bars[1:], start=2))

    def keeps_ticking(reader: Any) -> Any:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            result = reader(*args, **kwargs)
            queued = next(pending, None)
            if queued is not None:
                tick_seq, bar = queued
                _append_consumed_bar(hinge, data_dir, bar, tick_seq=tick_seq)
            return result

        return wrapped

    for name in ("read_snapshots", "read_decision_ticks", "read_decision_blocks"):
        monkeypatch.setattr(si, name, keeps_ticking(getattr(si, name)))

    records = si.live_decision_records(data_dir)

    assert [record["raw_event_id"] for record in records] == [bars[0].raw_event_id]
    assert [record["attributed_by"] for record in records] == ["capsule_id"]
    assert next(pending, None) is None, "a queued bar was never written"


def test_a_tick_without_a_decision_is_reported_not_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """The held-runtime shape, which the keyed join can now answer."""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (_seq(2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[2])),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["raw_event_id"] for record in records] == [
        bars[0].raw_event_id,
        bars[2].raw_event_id,
    ]
    lineage = si.build_live_lineage(
        data_dir=data_dir,
        records=records,
        payload=si.render_jsonl(records),
        ticks=len(si.read_decision_ticks(data_dir)),
        scope=_unscoped(records, si.read_decision_ticks(data_dir)),
    )
    assert lineage["counts"]["admitted_decision_ticks"] == 3
    assert lineage["counts"]["ticks_without_a_decision"] == 1
    assert lineage["counts"]["attributed_by"] == {"capsule_id": 2}


def test_capacity_denial_comes_from_the_flow_halt_in_the_same_block(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """B1b's ``capacity_denied`` is one flow halt reason, and only that one."""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0, 1), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (
                _seq(0, 2),
                "FLOW_HALTED",
                _flow_halted(hinge, si.CAPACITY_DENIAL_HALT_REASON),
            ),
            (_seq(1, 1), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[1])),
            (_seq(1, 2), "FLOW_HALTED", _flow_halted(hinge, "SOMETHING_ELSE")),
            (_seq(2, 1), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[2])),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["capacity_denied"] for record in records] == [True, False, False]
    assert records[1]["flow_halt_reason"] == "SOMETHING_ELSE"
    assert records[2]["flow_halt_reason"] is None


def test_red_a_flow_record_before_any_decision_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: a flow record belongs to the decision that started it.**"""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (
                _seq(0, 1),
                "FLOW_HALTED",
                _flow_halted(hinge, si.CAPACITY_DENIAL_HALT_REASON),
            ),
            (_seq(0, 2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (_seq(1, 1), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[1])),
        ],
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.live_decision_records(data_dir)
    assert "no decision record before it" in str(excinfo.value)


def test_a_proposal_is_named_proposal_not_guessed_and_not_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM M3.** ACTION vs FLAT is not in the durable record — measured:"""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (
                _seq(1),
                "DECISION_OUTCOME_EMITTED",
                _emitted(hinge, bars[1], outcome_type="Proposal"),
            ),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["outcome_kind"] for record in records] == [
        "NO_ACTION",
        si.PROPOSAL_KIND,
    ]
    assert records[0]["raw_event_id"] == bars[0].raw_event_id


def test_red_an_emitted_record_without_an_outcome_type_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: an emitted-outcome record with no"""
    bars = _bars(hinge, 1)
    record = _real_record(hinge, "DECISION_OUTCOME_EMITTED")
    record["capsule_id"] = bars[0].capsule_id
    record.pop("outcome_type")
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[(_seq(0), "DECISION_OUTCOME_EMITTED", _entry(record))],
    )
    with pytest.raises(si.SessionInputsError, match="no outcome_type"):
        si.live_decision_records(data_dir)


def test_a_tick_that_emitted_no_outcome_keeps_b1bs_own_token(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """A withheld decision is ``NO_OUTCOME``, not a fourth decision kind."""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0])),
            (
                _seq(1),
                "DECISION_WITHHELD",
                _withheld(hinge, halt_reason="VECTOR_OUTCOME_UNSUPPORTED"),
            ),
            (
                _seq(2),
                "COORDINATOR_PRECONDITION_REFUSED",
                _entry({"halt_reason": "GATE"}),
            ),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["outcome_kind"] for record in records] == [
        "NO_ACTION",
        si.NO_OUTCOME_KIND,
        si.NO_OUTCOME_KIND,
    ]
    assert records[1]["pipeline_halt_reason"] == "VECTOR_OUTCOME_UNSUPPORTED"
    assert [record["attributed_by"] for record in records] == [
        "capsule_id",
        "evidence_seq_range",
        "evidence_seq_range",
    ]


def test_red_an_inbox_tick_without_its_two_ids_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a ``DECISION_TICK`` whose capsule block lost"""
    bars = _bars(hinge, 1)
    broken = json.loads(bars[0].tick_payload)
    broken["decision_tick"]["capsule"].pop("capsule_id")
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[(bars[0].snapshot_id, INSTRUMENT, bars[0].as_of_ms)],
        preimages=[(bars[0].snapshot_id, bars[0].raw_event_id)],
        ticks=[(1, json.dumps(broken))],
        entries=[(1, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )
    with pytest.raises(si.SessionInputsError, match="decision_tick.capsule.capsule_id"):
        si.live_decision_records(data_dir)


def test_red_two_inbox_ticks_sharing_a_capsule_id_are_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: two admitted ticks with one capsule id. The"""
    bars = _bars(hinge, 2)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[(bar.snapshot_id, INSTRUMENT, bar.as_of_ms) for bar in bars],
        preimages=[(bar.snapshot_id, bar.raw_event_id) for bar in bars],
        ticks=[
            (1, bars[0].tick_payload),
            (2, _tick_with(hinge, 1, capsule_id=bars[0].capsule_id)),
        ],
        entries=[(1, "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )
    with pytest.raises(si.SessionInputsError, match="was already admitted"):
        si.live_decision_records(data_dir)


def test_cli_writes_both_inputs(tmp_path: Path, hinge: dict[str, Any]) -> None:
    """Both subcommands land their files, and the sidecar describes the bytes."""
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(index), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bar))
            for index, bar in enumerate(bars)
        ],
    )
    out = tmp_path / "b3-inputs"
    assert (
        si.main(
            [
                "consumed-ids",
                "--data-dir",
                str(data_dir),
                "--boot-snapshot",
                str(_boot_snapshot(tmp_path, [])),
                "--out",
                str(out / "consumed-ids.json"),
            ]
        )
        == 0
    )
    assert (
        si.main(
            [
                "live-decisions",
                "--data-dir",
                str(data_dir),
                "--boot-snapshot",
                str(_boot_snapshot(tmp_path, [])),
                "--out",
                str(out / "live"),
            ]
        )
        == 0
    )

    payload = (out / "live" / "live.jsonl").read_bytes()
    lineage = json.loads((out / "live" / "lineage.json").read_text(encoding="utf-8"))
    assert lineage["output"]["live_jsonl_lines"] == 3
    assert (
        lineage["output"]["live_jsonl_sha256"] == si.hashlib.sha256(payload).hexdigest()
    )
    assert lineage["counts"]["outcome_kinds"] == {"NO_ACTION": 3}
    assert lineage["counts"]["attributed_by"] == {"capsule_id": 3}
    assert lineage["counts"]["ticks_without_a_decision"] == 0
    assert "rationale" in lineage["join"]["rule_id"]
    assert "NOT B1a's bar label" in lineage["join"]["as_of_ms"]
    assert "capsule_id" in lineage["join"]["key"]


def test_cli_refusal_is_exit_2_and_writes_nothing(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    data_dir = _write_session(tmp_path, hinge, snapshots=[], preimages=[])
    out = tmp_path / "b3-inputs" / "consumed-ids.json"
    assert (
        si.main(
            [
                "consumed-ids",
                "--data-dir",
                str(data_dir),
                "--boot-snapshot",
                str(_boot_snapshot(tmp_path, [])),
                "--out",
                str(out),
            ]
        )
        == 2
    )
    assert not out.exists()


def test_hinge_the_pinned_reads_are_the_committed_ones(hinge: dict[str, Any]) -> None:
    """The tools half of the hinge (the tos half is in ``tos/runtime/tests``)."""
    assert hinge["marketfeed"]["file_name"] == si.MARKETFEED_FILE_NAME
    assert hinge["evidence"]["file_name"] == si.EVIDENCE_FILE_NAME
    assert hinge["inbox"]["file_name"] == si.INBOX_FILE_NAME
    assert hinge["marketfeed"]["schema_version"] == si.PINNED_MARKETFEED_SCHEMA_VERSION
    assert hinge["evidence"]["schema_version"] == si.PINNED_EVIDENCE_SCHEMA_VERSION
    assert hinge["inbox"]["schema_version"] == si.PINNED_INBOX_SCHEMA_VERSION


def test_hinge_the_committed_payloads_are_the_ones_these_tests_parse(
    hinge: dict[str, Any],
) -> None:
    """The second half of the hinge, stated here so it cannot quietly lapse."""
    wrapped = json.loads(_real_entry(hinge, "DECISION_OUTCOME_EMITTED"))
    assert set(wrapped) == {"payload", "masked_keys"}
    assert si.EVIDENCE_PAYLOAD_KEY in wrapped
    assert wrapped[si.EVIDENCE_PAYLOAD_KEY]["outcome_type"] == "NoActionOutcome"
    tick = json.loads(_real_tick(hinge, 0))
    assert si._dig(tick, si.TICK_CAPSULE_PATH)
    assert si._dig(tick, si.TICK_SNAPSHOT_PATH)


def test_the_extractor_imports_neither_tos_nor_the_runtime() -> None:
    """Sqlite read-only, by construction: the module's own import list."""
    source = Path(si.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not [
        name for name in imported if name.split(".")[0] in {"tos", "tos_runtime"}
    ]
    assert not [name for name in imported if name.startswith("shared.")]
    assert "sqlite3" in imported


def _tick_with_view(hinge: dict[str, Any], bar: Bar, *, values: list[Any]) -> str:
    """That bar's committed tick with a resolved ``value_view`` attached."""
    event = json.loads(bar.tick_payload)
    event["decision_tick"]["value_view"] = {
        "snapshot_id": bar.snapshot_id,
        "snapshot_canonical_digest": f"sd-{bar.snapshot_id}",
        "values": values,
        "canonical_digest": "vv-digest",
        "canonicalization_version": "ev-l1-provisional-0",
    }
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def test_the_value_view_counts_say_what_the_resolver_did_and_not_m5(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Claude-lane LOW L3, corrected by MEDIUM R2.**"""
    bars = _bars(hinge, 3)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=_preimage_rows(bars),
        ticks=[
            (1, bars[0].tick_payload, *bars[0].window),
            (2, bars[1].tick_payload, *bars[1].window),
            (
                3,
                _tick_with_view(hinge, bars[2], values=[]),
                *bars[2].window,
            ),
        ],
    )
    document = _document(tmp_path, data_dir)
    view = document["consumed_value_view"]
    assert view["counts"] == {"no_view": 1, "empty_view": 1, "values_admitted": 1}
    assert view["raw_event_ids_with_admitted_values"] == [bars[1].raw_event_id]
    assert "nothing was admissible" in view["note"]
    assert "NOT M5's first number" in view["note"]
    assert (
        "m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"
        in view["note"]
    )


def _boot_snapshot(tmp_path: Path, ids: list[str]) -> Path:
    path = tmp_path / "boot-journal-snapshot.json"
    path.write_text(json.dumps({"pre_boot_raw_event_ids": ids}), encoding="utf-8")
    return path


def _document(
    tmp_path: Path, data_dir: Path, *, pre_boot: list[str] | None = None, **kwargs: Any
) -> dict[str, Any]:
    """The consumed-ids document, with the now-REQUIRED boot snapshot."""
    return si.build_consumed_ids_document(
        data_dir=data_dir,
        boot_snapshot=_boot_snapshot(tmp_path, pre_boot or []),
        **kwargs,
    )


def test_m5s_first_number_counts_a_value_the_issuer_held_and_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER R2'.** Plan §5 M5's first number, from what the issuer did."""
    bars = _bars(hinge, 4, states=list(SNAPSHOT_SHAPES))
    data_dir = _session(tmp_path, hinge, bars)
    states = _document(tmp_path, data_dir)["consumed_field_states"]

    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 1
    )
    assert states[
        "post_boot_raw_event_ids_with_a_present_value_refused_as_unknown"
    ] == [bars[1].raw_event_id]
    assert states["unknown_field_causes"] == {
        si.CAUSE_PRESENT_REFUSED: {"post_boot": 1, "pre_boot": 0},
        si.CAUSE_ABSENT_FROM_PAYLOAD: {"post_boot": 1, "pre_boot": 0},
        si.CAUSE_UNPROJECTABLE: {"post_boot": 1, "pre_boot": 0},
    }
    assert states["counts"]["consumed_ids"] == 4
    assert states["counts"]["post_boot_consumed_ids"] == 4
    assert states["counts"]["consumed_ids_without_field_evaluations"] == 0
    assert states["other_field_evaluation_states"] == {}
    assert "never STALE" in states["definition"]
    assert "stale, or evaluation clock unknown" in states["definition"]


def test_red_an_absent_field_is_not_counted_as_a_refused_value(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER R2''s first red proof.**"""
    bars = _bars(hinge, 3, states=["absent_field"] * 3)
    data_dir = _session(tmp_path, hinge, bars)
    states = _document(tmp_path, data_dir)["consumed_field_states"]
    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 0
    )
    assert states["unknown_field_causes"][si.CAUSE_ABSENT_FROM_PAYLOAD] == {
        "post_boot": 3,
        "pre_boot": 0,
    }


def test_red_an_unprojectable_token_is_not_counted_as_a_refused_value(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER R2''s second red proof.**"""
    bars = _bars(hinge, 2, states=["unprojectable", "unprojectable"])
    data_dir = _session(tmp_path, hinge, bars)
    states = _document(tmp_path, data_dir)["consumed_field_states"]
    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 0
    )
    assert states["unknown_field_causes"][si.CAUSE_UNPROJECTABLE] == {
        "post_boot": 2,
        "pre_boot": 0,
    }


def test_red_a_fresh_session_counts_nothing(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER R2''s third red proof, and the genesis expectation.**"""
    bars = _bars(hinge, 3)
    data_dir = _session(tmp_path, hinge, bars)
    states = _document(tmp_path, data_dir)["consumed_field_states"]
    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 0
    )
    assert states["unknown_field_causes"] == {
        si.CAUSE_PRESENT_REFUSED: {"post_boot": 0, "pre_boot": 0},
        si.CAUSE_ABSENT_FROM_PAYLOAD: {"post_boot": 0, "pre_boot": 0},
        si.CAUSE_UNPROJECTABLE: {"post_boot": 0, "pre_boot": 0},
    }
    assert states["observation_field_states_not_valid"] == {}


def test_red_a_pre_boot_refused_line_is_not_in_the_post_boot_count(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER R2''s fourth red proof (and MEDIUM R2's, kept).**"""
    bars = _bars(hinge, 2, states=["stale_by_age", "stale_by_age"])
    data_dir = _session(tmp_path, hinge, bars)
    states = _document(tmp_path, data_dir, pre_boot=[bars[0].raw_event_id])[
        "consumed_field_states"
    ]
    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 1
    )
    assert states[
        "post_boot_raw_event_ids_with_a_present_value_refused_as_unknown"
    ] == [bars[1].raw_event_id]
    assert states["pre_boot_raw_event_ids_with_a_present_value_refused_as_unknown"] == [
        bars[0].raw_event_id
    ]
    assert states["unknown_field_causes"][si.CAUSE_PRESENT_REFUSED] == {
        "post_boot": 1,
        "pre_boot": 1,
    }
    assert states["counts"]["pre_boot_consumed_ids"] == 1
    assert states["counts"]["post_boot_consumed_ids"] == 1


def test_red_consumed_ids_without_a_boot_snapshot_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**LOW L-a's red proof.**"""
    bars = _bars(hinge, 1, states=["stale_by_age"])
    data_dir = _session(tmp_path, hinge, bars)
    with pytest.raises(si.SessionInputsError, match="--boot-snapshot"):
        si.build_consumed_ids_document(data_dir=data_dir)
    with pytest.raises(SystemExit):
        si.build_parser().parse_args(
            ["consumed-ids", "--data-dir", str(data_dir), "--out", str(tmp_path / "x")]
        )


def test_red_a_field_evaluation_without_a_state_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a ``field_evaluations`` entry with no"""
    bars = _bars(hinge, 1, states=["stale_by_age"])
    broken = json.loads(bars[0].snapshot_json)
    broken["field_evaluations"][0].pop("state")
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[
            (bars[0].snapshot_id, INSTRUMENT, bars[0].as_of_ms, json.dumps(broken))
        ],
        preimages=_preimage_rows(bars[:1]),
        ticks=_tick_rows(bars),
    )
    with pytest.raises(si.SessionInputsError, match="silent undercount"):
        _document(tmp_path, data_dir)


def test_red_a_field_evaluation_without_a_field_ref_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: an UNKNOWN evaluation with no ``field_ref``."""
    bars = _bars(hinge, 1, states=["stale_by_age"])
    broken = json.loads(bars[0].snapshot_json)
    broken["field_evaluations"][0].pop("field_ref")
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[
            (bars[0].snapshot_id, INSTRUMENT, bars[0].as_of_ms, json.dumps(broken))
        ],
        preimages=_preimage_rows(bars[:1]),
        ticks=_tick_rows(bars),
    )
    with pytest.raises(si.SessionInputsError, match="field_ref"):
        _document(tmp_path, data_dir)


def test_red_a_preimage_row_that_is_not_a_preimage_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a ``preimage_json`` with no ``entries``."""
    bars = _bars(hinge, 1, states=["stale_by_age"])
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=[
            (bars[0].snapshot_id, bars[0].raw_event_id, json.dumps({"rows": []}))
        ],
        ticks=_tick_rows(bars),
    )
    with pytest.raises(si.SessionInputsError, match="entries"):
        _document(tmp_path, data_dir)


def test_a_snapshot_with_no_field_evaluations_is_counted_not_read_as_valid(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """A snapshot that evaluated nothing is its own shape."""
    bars = _bars(hinge, 1)
    empty = json.loads(bars[0].snapshot_json)
    empty["field_evaluations"] = []
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[
            (bars[0].snapshot_id, INSTRUMENT, bars[0].as_of_ms, json.dumps(empty))
        ],
        preimages=_preimage_rows(bars[:1]),
        ticks=_tick_rows(bars),
    )
    states = _document(tmp_path, data_dir)["consumed_field_states"]
    assert states["counts"]["consumed_ids_without_field_evaluations"] == 1
    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 0
    )


def test_hinge_the_committed_snapshots_are_the_issuers_four_outcomes(
    hinge: dict[str, Any],
) -> None:
    """The tools half of the snapshot hinge (the tos half is in ``tos/runtime``)."""
    rows = hinge["payloads"]["marketfeed_snapshots"]
    assert set(rows) == set(SNAPSHOT_SHAPES)

    def evaluations(name: str) -> dict[str, str]:
        return {
            entry[si.FIELD_EVALUATION_FIELD_REF_KEY]: entry[
                si.FIELD_EVALUATION_STATE_KEY
            ]
            for entry in json.loads(rows[name]["snapshot_json"])[
                si.SNAPSHOT_FIELD_EVALUATIONS_KEY
            ]
        }

    def tokens(name: str) -> dict[str, Any]:
        return {
            entry[si.PREIMAGE_ENTRY_KEY_KEY]: entry[si.PREIMAGE_ENTRY_VALUE_KEY]
            for entry in json.loads(rows[name]["preimage_json"])[
                si.PREIMAGE_ENTRIES_KEY
            ]
        }

    assert set(evaluations("fresh").values()) == {si.VALID_FIELD_STATE}
    assert set(evaluations("stale_by_age").values()) == {si.UNKNOWN_FIELD_STATE}
    assert si.STALE_FIELD_STATE not in evaluations("stale_by_age").values()
    assert si._projectable(tokens("stale_by_age")["close"])
    assert "session" not in tokens("absent_field")
    assert evaluations("absent_field")["session"] == si.UNKNOWN_FIELD_STATE
    assert not si._projectable(tokens("unprojectable")["close"])
    assert evaluations("unprojectable")["close"] == si.UNKNOWN_FIELD_STATE


def test_m5_counts_only_this_session_day_not_the_whole_accumulated_leaf(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """⛔ **The measured miscount.** A tenant session writes into a NAMED DURABLE LEAF that is"""
    bars = _bars(hinge, 4, states=["fresh", "fresh", "fresh", "stale_by_age"])
    older = replace(bars[3], raw_event_id=f"{INSTRUMENT}:1m:20261015T090000+0900")
    data_dir = _session(tmp_path, hinge, [*bars[:3], older])
    states = _document(tmp_path, data_dir)["consumed_field_states"]

    assert states["session_day"] == "20261019"
    assert states["days_present"] == ["20261015", "20261019"]
    assert (
        states["m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown"] == 0
    )
    assert (
        states["post_boot_raw_event_ids_with_a_present_value_refused_as_unknown"] == []
    )
    assert states["counts"]["consumed_ids"] == 3
    assert states["counts"]["consumed_ids_all_days"] == 4
    assert states["counts"]["post_boot_consumed_ids"] == 3


def test_live_decisions_are_scoped_to_the_one_session_day(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """⛔ **The 2026-10-22 scope fix covered only the consumed-ids document, and"""
    bars = _bars(hinge, 3)
    older = replace(bars[0], raw_event_id=_event_id_on("20261015", "1001"))
    leaf = [older, *bars[1:]]
    data_dir = _session(
        tmp_path,
        hinge,
        leaf,
        entries=[
            (_seq(index, 2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bar))
            for index, bar in enumerate(leaf)
        ],
    )

    everything = si.live_decision_records(data_dir)
    assert len(everything) == 3, "the store-wide read is still store-wide"

    records, ticks, scope = si.scope_live_decisions(
        everything,
        ticks=si.read_decision_ticks(data_dir),
        snapshots=si.read_snapshots(data_dir),
        pre_boot=frozenset(),
    )
    assert scope.session_day == "20261019"
    assert scope.days_present == ("20261015", "20261019")
    assert [record["raw_event_id"] for record in records] == [
        bars[1].raw_event_id,
        bars[2].raw_event_id,
    ]
    assert (ticks, scope.ticks_all_days) == (2, 3)
    assert scope.records_all_days == 3
    assert [record["bar_index"] for record in records] == [0, 1]

    lineage = si.build_live_lineage(
        data_dir=data_dir,
        records=records,
        payload=si.render_jsonl(records),
        ticks=ticks,
        scope=scope,
    )
    assert lineage["session_scope"] == {
        "session_day": "20261019",
        "days_present": ["20261015", "20261019"],
        "live_jsonl_lines_all_days": 3,
        "admitted_decision_ticks_all_days": 3,
        "admitted_decision_ticks_with_no_resolvable_day": 0,
    }
    assert lineage["counts"]["ticks_without_a_decision"] == 0


def test_the_live_scope_comes_from_the_boot_snapshot_like_the_other_document(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """One source of truth for both session-derived inputs."""
    bars = _bars(hinge, 2)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(index, 2), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bar))
            for index, bar in enumerate(bars)
        ],
    )
    with pytest.raises(si.SessionInputsError, match="not from the same session"):
        si.scope_live_decisions(
            si.live_decision_records(data_dir),
            ticks=si.read_decision_ticks(data_dir),
            snapshots=si.read_snapshots(data_dir),
            pre_boot=frozenset({_event_id_on("20261020", "0845")}),
        )


def test_red_a_live_record_with_no_readable_day_is_refused_not_dropped() -> None:
    """A record that cannot be placed in a day would VANISH from a filtered"""
    with pytest.raises(si.SessionInputsError, match="no readable"):
        si.scope_live_decisions(
            [{"raw_event_id": "A05611-no-stamp"}],
            ticks=(),
            snapshots=(),
            pre_boot=frozenset(),
        )


def test_the_live_cli_requires_the_boot_snapshot(
    tmp_path: Path, hinge: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Required, not optional: an omitted flag would silently write the"""
    data_dir = _session(tmp_path, hinge, _bars(hinge, 2))
    with pytest.raises(SystemExit) as excinfo:
        si.main(
            [
                "live-decisions",
                "--data-dir",
                str(data_dir),
                "--out",
                str(tmp_path / "x"),
            ]
        )
    assert excinfo.value.code == 2
    assert "--boot-snapshot" in capsys.readouterr().err


def test_the_emitted_definition_names_what_the_number_is(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """The emitted document says what the consumed-field-state count counts."""
    bars = _bars(hinge, 2)
    data_dir = _session(tmp_path, hinge, bars)
    definition = _document(tmp_path, data_dir)["consumed_field_states"]["definition"]

    assert "stale, or evaluation clock unknown" in definition


def test_a_session_that_died_before_consuming_refuses_the_previous_days_numbers(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """⛔ **Review MEDIUM-1.** Newest-consumed-day alone answers the WRONG session."""
    bars = _bars(hinge, 2, states=["fresh", "stale_by_age"])
    data_dir = _session(tmp_path, hinge, bars)

    with pytest.raises(si.SessionInputsError) as excinfo:
        _document(
            tmp_path, data_dir, pre_boot=[f"{INSTRUMENT}:1m:20261020T084500+0900"]
        )

    message = str(excinfo.value)
    assert "20261020" in message and "20261019" in message
    assert "died before consuming" in message


def test_the_boot_snapshot_decides_the_session_day_when_both_agree(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """The other side of MEDIUM-1: agreement is silent, and the pre-boot id is still excluded"""
    bars = _bars(hinge, 3)
    data_dir = _session(tmp_path, hinge, bars)
    states = _document(tmp_path, data_dir, pre_boot=[bars[0].raw_event_id])[
        "consumed_field_states"
    ]

    assert states["session_day"] == "20261019"
    assert states["counts"]["pre_boot_consumed_ids"] == 1
    assert states["counts"]["post_boot_consumed_ids"] == 2


def test_an_unreadable_raw_event_id_is_refused_not_silently_dropped(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """⛔ **Review MEDIUM-2.** An id with no ``:1m:`` stamp has no day, so a day filter drops"""
    bars = _bars(hinge, 2)
    malformed = replace(bars[1], raw_event_id=f"{INSTRUMENT}:20261019T151300+0900")
    data_dir = _session(tmp_path, hinge, [bars[0], malformed])

    with pytest.raises(si.SessionInputsError) as excinfo:
        _document(tmp_path, data_dir)

    assert malformed.raw_event_id in str(excinfo.value)
    assert "cannot be scoped to a session" in str(excinfo.value)


def test_the_session_day_is_taken_in_kst_not_in_the_ids_own_offset(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """⛔ **Review LOW-3.** The stamp carries its OWN offset. ``20261019T233000+0000`` is"""
    assert si.session_day_of(f"{INSTRUMENT}:1m:20261019T233000+0000") == "20261020"
    assert si.session_day_of(f"{INSTRUMENT}:1m:20261019T151200+0900") == "20261019"
    assert si.session_day_of(f"{INSTRUMENT}:20261019T151200+0900") is None


def test_every_count_in_the_document_is_this_sessions_not_the_whole_leaf(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """⛔ **Review LOW-4.** The scope is applied ONCE, to the whole document."""
    bars = _bars(hinge, 4)
    older = replace(bars[3], raw_event_id=f"{INSTRUMENT}:1m:20261015T090000+0900")
    data_dir = _session(tmp_path, hinge, [*bars[:3], older])

    document = _document(tmp_path, data_dir)

    assert document["session_day"] == "20261019"
    assert document["days_present"] == ["20261015", "20261019"]
    assert document["counts"]["snapshots"] == 3
    assert document["counts"]["consumed_raw_event_ids"] == 3
    assert document["counts"]["snapshots_all_days"] == 4
    assert older.raw_event_id not in document["raw_event_ids"]
    assert len(document["raw_event_ids"]) == 3
