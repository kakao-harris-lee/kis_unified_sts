"""CP-3 §3.6 — the two session-derived B3 inputs, all hermetic.

No sqlite file outside ``tmp_path``, no network, no ``tos`` import. Every
refusal in :mod:`tools.tos_cp3.session_inputs` has a red proof here: a concrete
input that makes it fire, and the test goes green only because the guard is
there.

The fixture stores are built from the COMMITTED hinge
``tos/runtime/tests/fixtures/cp3-session-store-reads.json`` — the same file
``tos/runtime/tests/operations/test_cp3_session_store_reads.py`` checks against
the real migrations. So a column this extractor reads but the hinge does not
declare is a sqlite error here, and a column the runtime stops declaring is red
there.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
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
    """Bar *index*'s durable handling window, as the driver would write it.

    ``(EVENT_HANDLING_STARTED seq, EVENT_CONSUMED seq)``, 100 apart so each
    bar has room for its own records and the windows cannot overlap by
    accident. Bar 0 opens at ``0`` deliberately: a real driver's first receipt
    IS seq 0 (measured —
    ``tos/runtime/tests/operations/test_cp3_session_store_reads.py``'s driver
    test), so any code that tests this stamp for truthiness instead of
    ``is None`` drops bar 0's whole window.
    """
    return (100 * index, 100 * index + 99)


def _seq(index: int, offset: int = 1) -> int:
    """An evidence seq INSIDE bar *index*'s handling window."""
    assert 1 <= offset <= 99, "an offset outside the window is another bar's seq"
    return 100 * index + offset


def _snapshot_json(hinge: dict[str, Any], name: str, *, snapshot_id: str) -> str:
    """One committed snapshot's bytes, re-keyed to *snapshot_id*.

    ``name`` is the FieldState shape (``valid`` / ``stale`` / ``unknown``) the
    real :class:`SqliteSnapshotStore` wrote in the hinge. Only the id is
    rewritten — the ``field_evaluations`` and ``observations`` the extractor
    counts are the store's own.
    """
    document = json.loads(
        hinge["payloads"]["marketfeed_snapshots"][name]["snapshot_json"]
    )
    document["snapshot_id"] = snapshot_id
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def _write_session(
    tmp_path: Path,
    hinge: dict[str, Any],
    *,
    snapshots: list[tuple[str, str, int]] | list[tuple[str, str, int, str]],
    preimages: list[tuple[str, str]],
    entries: list[tuple[int, str, str]] | None = None,
    ticks: (
        list[tuple[int, str]] | list[tuple[int, str, int | None, int | None]] | None
    ) = None,
    marketfeed_version: int | None = None,
    evidence_version: int | None = None,
    inbox_version: int | None = None,
    skip_inbox: bool = False,
) -> Path:
    """A session data dir holding the three stores, with the given rows.

    ``entries`` and ``ticks`` carry ``payload_json`` as a STRING, never as an
    object this file would re-serialise: the point of the hinge is that the
    extractor parses the bytes the real stores write (see
    :func:`_real_entry`), and a helper that rebuilt them from a dict would be
    testing the rebuild.

    A ``snapshots`` row may omit ``snapshot_json`` and a ``ticks`` row the two
    receipt stamps; the first then carries the committed all-VALID snapshot
    and the second a window from :func:`_window`, so a test that is not about
    field states or attribution does not have to spell them out.
    """
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
                    else (*row, _snapshot_json(hinge, "valid", snapshot_id=row[0]))
                )
                for row in snapshots
            ],
        )
        conn.executemany(
            "INSERT INTO preimages (snapshot_id, raw_event_id) VALUES (?, ?)",
            preimages,
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


# ---------------------------------------------------------------------------
# The committed bytes the real stores wrote (the hinge's second half)
# ---------------------------------------------------------------------------


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
    """Re-wrap a (possibly edited) engine record the way the store does.

    Only for the variations a test needs — the unedited cases use
    :func:`_real_entry`, so the baseline is never a reconstruction.
    """
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
    #: The committed snapshot bytes this bar's row carries, re-keyed to its
    #: own id — the FieldStates M5 counts live in here.
    snapshot_json: str
    #: ``(handling_started_evidence_seq, consumed_evidence_seq)``: the durable
    #: bracket a capsule-less decision record is attributed by. ``None`` for
    #: either end is a real shape (never ran / never finished) and some tests
    #: build one deliberately.
    window: tuple[int | None, int | None]


def _bars(
    hinge: dict[str, Any], count: int, *, states: list[str] | None = None
) -> list[Bar]:
    """``count`` bars whose ticks are the COMMITTED ones where there are any.

    The first two carry the real inbox bytes (capsule and snapshot ids
    included), so the keyed join is exercised against what the runtime writes;
    any further bar is that same event with its two ids replaced, which keeps
    the shape real even where the fixture runs out.

    ``states`` names each bar's committed snapshot shape (``valid`` /
    ``stale`` / ``unknown``); the default is all-``valid``.
    """
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
                    "valid" if states is None else states[index],
                    snapshot_id=snapshot_id,
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
        preimages=[(bar.snapshot_id, bar.raw_event_id) for bar in bars],
        ticks=_tick_rows(bars),
        entries=entries,
        **kwargs,
    )


def _snapshot_rows(bars: list[Bar]) -> list[tuple[str, str, int, str]]:
    """The ``snapshots`` rows for *bars*, carrying each one's committed bytes."""
    return [
        (bar.snapshot_id, INSTRUMENT, bar.as_of_ms, bar.snapshot_json) for bar in bars
    ]


def _tick_rows(bars: list[Bar]) -> list[tuple[int, str, int | None, int | None]]:
    """The ``events`` rows for *bars*, each with its own handling window."""
    return [
        (index + 1, bar.tick_payload, bar.window[0], bar.window[1])
        for index, bar in enumerate(bars)
    ]


def _three_bar_session(tmp_path: Path, hinge: dict[str, Any], **kwargs: Any) -> Path:
    """Three consumed bars: 09:00, 09:01, 09:02, in that order."""
    return _session(tmp_path, hinge, _bars(hinge, 3), **kwargs)


# ===========================================================================
# consumed-ids
# ===========================================================================


def test_consumed_ids_are_the_preimage_rows(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """The id filter is what the runtime actually covered, nothing inferred."""
    data_dir = _three_bar_session(tmp_path, hinge)
    document = si.build_consumed_ids_document(data_dir=data_dir)

    assert document["raw_event_ids"] == [
        _event_id("0900"),
        _event_id("0901"),
        _event_id("0902"),
    ]
    assert document["instrument"] == INSTRUMENT
    assert document["counts"]["snapshots"] == 3
    assert document["counts"]["consumed_raw_event_ids"] == 3
    # with no producer log there are no reasons at all — not guessed ones
    assert document["unpaired_reasons"] == {}
    assert document["counts"]["unpaired"] == 0
    assert document["generated_from"]["marketfeed_sqlite3"]["sha256"]


@pytest.mark.parametrize("store", ["marketfeed", "evidence", "inbox"])
def test_red_a_store_at_another_schema_version_is_refused(
    tmp_path: Path, hinge: dict[str, Any], store: str
) -> None:
    """**Guard: the mirrored schema version, on each of the three stores.**

    Concrete input: the store file stamps ``PRAGMA user_version`` one past what
    this extractor was written for — exactly what a ``migrate`` run does. The
    queries would still "work" (sqlite does not mind extra columns), so without
    this pin the extractor would answer a question about a store shape nobody
    checked. Remove the version comparison in ``_connect_ro`` and all three
    cases pass silently.
    """
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
    """**Guard: one snapshot covers one observation.**

    Two concrete inputs. ``0`` is the restore-path loss the store's own
    docstring describes — a snapshot id in hand and every value UNKNOWN — and
    the id this decision was about is simply gone. ``2`` means a snapshot
    covered several observations, so "the bar" is not a question with one
    answer and the ordered pairing below would be joining decisions to a
    guess. Drop the length check and ``covered=0`` silently shortens the id
    filter while ``covered=2`` silently keeps whichever row sqlite returned
    first.
    """
    extra = [("snap-1", _event_id("0859"))] if covered == 2 else []
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[("snap-1", INSTRUMENT, 1_760_000_000_000)],
        preimages=([("snap-1", _event_id("0900"))] if covered else []) + extra,
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.build_consumed_ids_document(data_dir=data_dir)
    assert f"covers {covered} preimage row(s)" in str(excinfo.value)


def test_red_two_instruments_in_one_session_are_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: a tenant session is one instrument.**

    Concrete input: a second contract month's snapshot in the same durable set
    — the shape a roll-day session gets if the contract is derived twice
    instead of once (runbook §7.3 5-a). Without the check the id filter mixes
    two instruments' bars and B3 compares one month's offline stream against
    another month's live decisions.
    """
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
        si.build_consumed_ids_document(data_dir=data_dir)
    assert "A05612" in str(excinfo.value)


def test_red_a_session_that_consumed_nothing_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: an empty filter is not a filter.**

    Concrete input: a store with no snapshots — a session that booted and never
    TICKed. An empty id set would restrict B3's comparison to zero bars, and
    "UNRESOLVED 0 over zero bars" is the acceptance criterion passing
    vacuously.
    """
    data_dir = _write_session(tmp_path, hinge, snapshots=[], preimages=[])
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.build_consumed_ids_document(data_dir=data_dir)
    assert "holds no snapshots" in str(excinfo.value)


def test_unpaired_bars_carry_the_producers_own_reason(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """Plan §5: pre-boot / ``skipped_behind`` / ``produce_error`` /
    ``omitted_unusable`` bars have no live counterpart, and that is normal —
    so each is counted under its own name, and a published line the runtime
    did NOT consume after boot is NOT folded in with them.
    """
    data_dir = _three_bar_session(tmp_path, hinge)
    producer_log = tmp_path / "producer-log.jsonl"
    producer_log.write_text(
        "\n".join(
            json.dumps(event)
            for event in [
                # consumed — no reason row at all
                {"stage": "published", "raw_event_id": _event_id("0900")},
                {"stage": "published", "raw_event_id": _event_id("0901")},
                {"stage": "published", "raw_event_id": _event_id("0902")},
                # published before the runtime booted
                {"stage": "published", "raw_event_id": _event_id("0858")},
                # published after boot and never consumed — the M5 defect shape
                {"stage": "published", "raw_event_id": _event_id("0903")},
                # never published, each for its own reason
                {"stage": "skipped_behind", "raw_event_id": _event_id("0845")},
                {"stage": "produce_error", "raw_event_id": _event_id("0846")},
                {"stage": "omitted_unusable", "raw_event_id": _event_id("0847")},
                # a bar that missed its boundary and completed late: the LAST
                # dispositive stage is how the session left it
                {"stage": "missing_no_successor", "raw_event_id": _event_id("0848")},
                {"stage": "late_completed", "raw_event_id": _event_id("0848")},
                # not a disposition — must not become a reason
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


def test_red_a_boot_snapshot_without_the_pre_boot_list_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: the boot snapshot must be the runner's own.**

    Concrete input: a JSON object with everything but
    ``pre_boot_raw_event_ids`` — a truncated or hand-made file. Read
    permissively it would mean "no pre-boot lines", which moves every
    structurally-unconsumable pre-boot line into
    ``published_not_consumed``: the benign case reported as the defect shape.
    """
    data_dir = _three_bar_session(tmp_path, hinge)
    boot_snapshot = tmp_path / "boot.json"
    boot_snapshot.write_text(json.dumps({"captured_at_kst": "09:05"}), encoding="utf-8")
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.build_consumed_ids_document(data_dir=data_dir, boot_snapshot=boot_snapshot)
    assert "pre_boot_raw_event_ids" in str(excinfo.value)


# ===========================================================================
# live-decisions — the keyed join, on the bytes the real stores write
# ===========================================================================


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
    """**The join (Claude-lane MEDIUM M1), on real bytes (BLOCKER B1).**

    Each decision names the capsule it consumed; the inbox says which snapshot
    that capsule bound; the snapshot's preimage is the bar. Nothing here
    counts positions.

    The entries are the committed ``payload_json`` the real
    ``SqliteEvidenceStore`` wrote, wrapper and all — which is what the first
    cut got wrong: it read the wrapper as the record, found no
    ``outcome_type`` and no ``capsule_id``, and would have refused every
    genesis session. Its tests passed because they wrote flat rows.
    """
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
    # the keys B3 reads from a trace line are all present
    for record in records:
        assert set(record) >= {
            "raw_event_id",
            "as_of_ms",
            "outcome_kind",
            "rule_id",
            "capacity_denied",
        }
        assert record["rule_id"] is None  # not derivable; the sidecar says so
        assert record["capacity_denied"] is False
    assert records[0]["as_of_ms"] == bars[0].as_of_ms


def test_red_the_store_wrapper_is_read_through_not_as_the_record(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**BLOCKER B1's own red proof.**

    Concrete input: an entry whose ``payload_json`` is the engine record with
    NO wrapper — exactly what this suite used to write, and exactly what the
    broken reader expected. A reader that takes the outer object as the record
    accepts it happily; the fixed one refuses, because a row the store did not
    write is a row whose shape it cannot vouch for.
    """
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
    """**MEDIUM M1's red proof: the shift the ordered pairing could not see.**

    Concrete input: the middle tick produced no decision (a held runtime
    drains it later) and an unrelated decision sits where it would have been.
    Pairing by position hands bar 2's record to bar 3 and every later record
    moves with it — silently, because the counts still line up.

    Both keys answer: bar 1 and bar 3 get the decisions that NAME them, and
    the withheld record — which names no capsule — lands in the one handling
    window that contains its evidence seq, bar 2's.
    """
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
    # the two keyed decisions landed on the bars they NAME, not on positions
    # 1 and 2
    assert attributed[bars[0].raw_event_id]["attributed_by"] == "capsule_id"
    assert attributed[bars[2].raw_event_id]["attributed_by"] == "capsule_id"
    assert attributed[bars[2].raw_event_id]["evidence_seq"] == _seq(2)
    # and the unkeyed one landed in the window that holds it
    assert attributed[bars[1].raw_event_id]["attributed_by"] == "evidence_seq_range"
    assert attributed[bars[1].raw_event_id]["outcome_kind"] == si.NO_OUTCOME_KIND


def test_red_an_unkeyed_decision_goes_to_the_window_that_holds_it_not_the_next_bar(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R1's red proof — the reviewer's own sequence.**

    Three ticks c1–c3 over bars 1–3. The runtime withheld on bar 1, DROPPED
    tick 2 on recovery (it ran, wrote no decision), and withheld again on bar
    3. Neither withheld record names a capsule, so the positional pairing took
    "the next unclaimed tick in file order" and put bar 3's record on **bar
    2** — with the counts still matching, no refusal, and B3 then comparing
    the live decision of one bar against the offline decision of another.

    The durable bracket cannot shift: B's evidence seq is inside c3's
    ``(handling_started, consumed]`` window and no other, so it is c3's.
    Bar 2 is left with no decision, which the lineage reports as
    ``ticks_without_a_decision``.

    Red on the positional cut: it asserts bar 2 carries B.
    """
    bars = _bars(hinge, 3)
    data_dir = _session(
        tmp_path,
        hinge,
        bars,
        entries=[
            (_seq(0), "DECISION_WITHHELD", _withheld(hinge, detail="A_FOR_BAR1")),
            # tick 2 ran and was dropped on recovery: a real entry, not a
            # decision kind, inside c2's own window
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
    )
    assert lineage["counts"]["ticks_without_a_decision"] == 1


def test_red_a_tick_queued_and_never_run_takes_no_record(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R1, the other shape: the held tick that never started.**

    Concrete input: tick 2 is admitted and never handled — both receipt
    stamps NULL, which is exactly what a tick still in the queue at shutdown
    looks like. Positionally it is "the next unclaimed tick", so the withheld
    record written while bar 3 was handled landed on it. A row that never
    started handling brackets nothing, so it takes nothing, and the record
    goes where its seq says.
    """
    bars = _bars(hinge, 3)
    held = bars[1]
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=[(bar.snapshot_id, bar.raw_event_id) for bar in bars],
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
    """**Guard (MEDIUM R1's cross-check).**

    Concrete input: a decision that NAMES bar 1's capsule but whose evidence
    seq falls inside bar 2's handling window — the shape a replayed record, a
    copied store or a mis-stamped row produces. The two durable keys then
    disagree about which event wrote the record, and preferring either one
    (the capsule, as the second cut did, or the window) would be a choice
    recorded as a fact.
    """
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
    """**Guard.** Concrete input: a decision naming a capsule whose inbox row
    has a NULL ``handling_started_evidence_seq``. The driver writes that stamp
    before the handler can write any decision record, so the two cannot both
    be true — and without a window there is nothing to cross-check the key
    against, which is where a silent mis-attribution would re-enter."""
    bars = _bars(hinge, 1)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=[(bars[0].snapshot_id, bars[0].raw_event_id)],
        ticks=[(1, bars[0].tick_payload, None, None)],
        entries=[(_seq(0), "DECISION_OUTCOME_EMITTED", _emitted(hinge, bars[0]))],
    )
    with pytest.raises(si.SessionInputsError, match="is NULL"):
        si.live_decision_records(data_dir)


def test_red_an_unkeyed_record_in_two_windows_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: bar 1's row was never marked consumed (a
    crash inside handling), so its window has no upper end and bar 2's lies
    inside it. A capsule-less record after that point belongs to either, and
    picking the narrower — or the later — would be this module deciding what
    the receipts do not say."""
    bars = _bars(hinge, 2)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=[(bar.snapshot_id, bar.raw_event_id) for bar in bars],
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
    """**Guard.** Concrete input: a decision whose capsule id is not in the
    inbox — the two stores disagree about what this session processed. Falling
    back to position here would paper over exactly the disagreement the key
    exists to surface.
    """
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
    """**Guard.** Concrete input: two emitted records naming the SAME capsule
    — a replayed decision, or a recovery that re-ran one tick. One bar cannot
    have two live decisions, and silently keeping the last would hide the
    re-run."""
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
    """**Guard.** Concrete input: a withheld record whose evidence seq is
    after every admitted tick's window closed — a record from a run whose
    inbox rows are not these, or a store pair that was mixed. It names no
    capsule, so there is nothing to key on either, and handing it the last
    bar (what "the next unclaimed tick" amounts to once the list runs out)
    would be inventing the attribution this join exists to avoid."""
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
    """**Guard.** Concrete input: two withheld records inside ONE tick's
    handling window. Exactly one decision terminates one pass, so a second is
    a replay or a re-run; keeping either silently would report one bar's
    outcome as the other's."""
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
    """**Guard.** Concrete input: the inbox admitted a tick whose snapshot the
    marketfeed store does not hold — the restore-path loss the store's own
    docstring describes, seen from the other side. The decision is real and
    the bar it was about is not knowable."""
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


def test_a_tick_without_a_decision_is_reported_not_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """The held-runtime shape, which the keyed join can now answer.

    A tick enqueued and drained later leaves fewer decisions than ticks. The
    first cut refused the whole document for it (the counts had to match,
    because position was the only link); with a key, every decision that DID
    run has a real answer and the gap is a number in the sidecar.
    """
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
    """**Guard: a flow record belongs to the decision that started it.**

    Concrete input: a ``FLOW_HALTED`` row at a lower ``seq`` than the first
    decision — what a replayed or recovered flow looks like in the store.
    Attributing it forward would put one tick's capacity denial on another
    tick's bar.
    """
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
    """**MEDIUM M3.** ACTION vs FLAT is not in the durable record — measured:
    ``position_effect`` occurs nowhere in ``tos/src/tos/engine``.

    So the live side says PROPOSAL: "an outcome was emitted and it was not a
    no-action". The first cut refused the whole document over one such bar,
    which threw away every other bar's answer with it; guessing ACTION or FLAT
    would make this module the thing that decided.
    """
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
    # the other bars keep their answers — the point of not refusing
    assert records[0]["raw_event_id"] == bars[0].raw_event_id


def test_red_an_emitted_record_without_an_outcome_type_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: an emitted-outcome record with no
    ``outcome_type`` — the shape a wrapper-read-as-record produces, and the
    only way PROPOSAL could become a bucket for "I could not read this".
    """
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
    """A withheld decision is ``NO_OUTCOME``, not a fourth decision kind.

    B1b refuses to call it one (``replay.py::_attribute_rule``), so the live
    side records the same token and B3's closed-set check surfaces it rather
    than this module quietly calling it NO_ACTION — which would report a
    withheld tick as agreement with an offline no-action.
    """
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
    """**Guard.** Concrete input: a ``DECISION_TICK`` whose capsule block lost
    its ``capsule_id`` — the shape a moved field in ``EngineEvent`` would
    produce. Without those two ids the join is back to guessing by position,
    and doing that silently is what this whole item replaced.
    """
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
    """**Guard.** Concrete input: two admitted ticks with one capsule id. The
    key would then name two bars, and a key that is sometimes ambiguous is not
    a key — picking either would be a coin toss recorded as an attribution."""
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


# ===========================================================================
# CLI, hinge, firewall
# ===========================================================================


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
                "--out",
                str(out / "consumed-ids.json"),
            ]
        )
        == 0
    )
    assert (
        si.main(
            ["live-decisions", "--data-dir", str(data_dir), "--out", str(out / "live")]
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
    # the sidecar states the three things a reader must not assume
    assert "rationale" in lineage["join"]["rule_id"]
    assert "NOT B1a's bar label" in lineage["join"]["as_of_ms"]
    assert "capsule_id" in lineage["join"]["key"]


def test_cli_refusal_is_exit_2_and_writes_nothing(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    data_dir = _write_session(tmp_path, hinge, snapshots=[], preimages=[])
    out = tmp_path / "b3-inputs" / "consumed-ids.json"
    assert (
        si.main(["consumed-ids", "--data-dir", str(data_dir), "--out", str(out)]) == 2
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
    """The second half of the hinge, stated here so it cannot quietly lapse.

    Every evidence row these tests feed the extractor starts from
    ``payloads.evidence_entries`` — bytes
    ``tos/runtime/tests/operations/test_cp3_session_store_reads.py`` proves the
    REAL store writes. If a future edit went back to hand-rolled rows, the
    wrapper could be dropped again and nothing here would notice.
    """
    wrapped = json.loads(_real_entry(hinge, "DECISION_OUTCOME_EMITTED"))
    assert set(wrapped) == {"payload", "masked_keys"}
    assert si.EVIDENCE_PAYLOAD_KEY in wrapped
    assert wrapped[si.EVIDENCE_PAYLOAD_KEY]["outcome_type"] == "NoActionOutcome"
    tick = json.loads(_real_tick(hinge, 0))
    assert si._dig(tick, si.TICK_CAPSULE_PATH)
    assert si._dig(tick, si.TICK_SNAPSHOT_PATH)


def test_the_extractor_imports_neither_tos_nor_the_runtime() -> None:
    """Sqlite read-only, by construction: the module's own import list.

    The firewall's reverse scan already refuses ``import tos`` anywhere outside
    ``tos/``; this states the stronger property this module claims — it reaches
    the three stores as FILES, through stdlib only, so nothing here can be
    satisfied by "the kernel happened to be importable".
    """
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
    """That bar's committed tick with a resolved ``value_view`` attached.

    The committed events publish none (``value_view: null``), which is one of
    the three shapes M5 counts; the other two are built here from the same
    bytes rather than from a hand-written event.
    """
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
    """**Claude-lane LOW L3, corrected by MEDIUM R2.**

    The three shapes of the resolver's ``value_view`` are still reported —
    they say what the resolver did — but the block no longer claims to be
    M5's STALE count, and its note points at the one that is. An empty view
    has ten possible reasons (``_admit_one``), only one of which is
    state-shaped, and that one folds STALE in with UNKNOWN, CONFLICTED and
    INVALID.
    """
    bars = _bars(hinge, 3)
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=_snapshot_rows(bars),
        preimages=[(bar.snapshot_id, bar.raw_event_id) for bar in bars],
        ticks=[
            (1, bars[0].tick_payload, *bars[0].window),  # value_view: null
            (
                2,
                _tick_with_view(hinge, bars[1], values=[]),
                *bars[1].window,
            ),  # -> empty_view
            (
                3,
                _tick_with_view(hinge, bars[2], values=[{"field_key": "close_x100"}]),
                *bars[2].window,
            ),
        ],
    )
    document = si.build_consumed_ids_document(data_dir=data_dir)
    view = document["consumed_value_view"]
    assert view["counts"] == {"no_view": 1, "empty_view": 1, "values_admitted": 1}
    assert view["raw_event_ids_with_admitted_values"] == [bars[2].raw_event_id]
    # the note says what the store says, and refuses the inference it used to
    # make
    assert "nothing was admissible" in view["note"]
    assert "NOT the STALE count" in view["note"]
    assert "m5_post_boot_consumed_ids_with_a_stale_field_evaluation" in view["note"]


# ===========================================================================
# M5's first count — STALE from the snapshot's own field states (MEDIUM R2)
# ===========================================================================


def _boot_snapshot(tmp_path: Path, ids: list[str]) -> Path:
    path = tmp_path / "boot-journal-snapshot.json"
    path.write_text(json.dumps({"pre_boot_raw_event_ids": ids}), encoding="utf-8")
    return path


def test_m5s_stale_count_is_the_snapshots_own_field_state(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R2.** Plan §5 M5's first number, from the word the store writes.

    Three consumed bars, each carrying a snapshot the REAL store wrote: one
    all-VALID, one with a STALE field evaluation, one with an UNKNOWN
    evaluation over a STALE observation. M5 counts the STALE one; the UNKNOWN
    is reported by its own name; the observation-level STALE is reported on
    its own surface, because ``value_field_state`` takes the worst of both and
    neither stands for the other.
    """
    bars = _bars(hinge, 3, states=["valid", "stale", "unknown"])
    data_dir = _session(tmp_path, hinge, bars)
    document = si.build_consumed_ids_document(data_dir=data_dir)
    states = document["consumed_field_states"]

    assert states["m5_post_boot_consumed_ids_with_a_stale_field_evaluation"] == 1
    assert states["post_boot_raw_event_ids_with_a_stale_field_evaluation"] == [
        bars[1].raw_event_id
    ]
    assert states["counts"]["consumed_ids"] == 3
    assert states["counts"]["pre_boot_consumed_ids"] == 0
    assert states["counts"]["post_boot_consumed_ids"] == 3
    assert states["counts"]["consumed_ids_without_field_evaluations"] == 0
    # the other non-VALID states, by name, NOT summed into the STALE number
    assert states["other_field_evaluation_states"] == {
        "UNKNOWN": {"post_boot": 1, "pre_boot": 0}
    }
    assert states["observation_field_states_not_valid"] == {
        "STALE": {"post_boot": 1, "pre_boot": 0}
    }
    assert "field_evaluations[*].state == 'STALE'" in states["definition"]


def test_red_a_non_stale_rejection_is_not_counted_as_stale(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R2's first red proof.**

    Concrete input: every consumed bar carries an UNKNOWN field evaluation
    and NO stale one. The resolver admits no value for any of them, so the
    count this replaces (``empty_view + no_view``) would report three "lines
    consumed STALE" — a defect the session did not have, on the acceptance
    criterion that decides whether ③ worked. M5's number is 0 here, and the
    three UNKNOWNs are visible under their own name.
    """
    bars = _bars(hinge, 3, states=["unknown", "unknown", "unknown"])
    data_dir = _session(tmp_path, hinge, bars)
    states = si.build_consumed_ids_document(data_dir=data_dir)["consumed_field_states"]
    assert states["m5_post_boot_consumed_ids_with_a_stale_field_evaluation"] == 0
    assert states["post_boot_raw_event_ids_with_a_stale_field_evaluation"] == []
    assert states["other_field_evaluation_states"]["UNKNOWN"]["post_boot"] == 3


def test_red_a_pre_boot_stale_line_is_not_in_the_post_boot_count(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**MEDIUM R2's second red proof.**

    Concrete input: two consumed bars with STALE field evaluations, one of
    them listed in the runner's boot-journal snapshot. Plan §5 M5 excludes
    pre-boot lines from both of its counts — they are structurally
    unconsumable-fresh — so counting it would report a defect the acceptance
    criterion does not ask about, on every genesis session that consumed its
    first journal line.
    """
    bars = _bars(hinge, 2, states=["stale", "stale"])
    data_dir = _session(tmp_path, hinge, bars)
    document = si.build_consumed_ids_document(
        data_dir=data_dir,
        boot_snapshot=_boot_snapshot(tmp_path, [bars[0].raw_event_id]),
    )
    states = document["consumed_field_states"]
    assert states["m5_post_boot_consumed_ids_with_a_stale_field_evaluation"] == 1
    assert states["post_boot_raw_event_ids_with_a_stale_field_evaluation"] == [
        bars[1].raw_event_id
    ]
    assert states["pre_boot_raw_event_ids_with_a_stale_field_evaluation"] == [
        bars[0].raw_event_id
    ]
    assert states["counts"]["pre_boot_consumed_ids"] == 1
    assert states["counts"]["post_boot_consumed_ids"] == 1


def test_red_a_field_evaluation_without_a_state_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard.** Concrete input: a ``field_evaluations`` entry with no
    ``state`` key — what a renamed field in ``FieldEvaluation`` would produce.
    Read permissively it is "not STALE", so M5's number would silently drop to
    0 on a session full of stale lines: the undercount the whole criterion
    exists to catch."""
    bars = _bars(hinge, 1, states=["stale"])
    broken = json.loads(bars[0].snapshot_json)
    broken["field_evaluations"][0].pop("state")
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[
            (bars[0].snapshot_id, INSTRUMENT, bars[0].as_of_ms, json.dumps(broken))
        ],
        preimages=[(bars[0].snapshot_id, bars[0].raw_event_id)],
        ticks=_tick_rows(bars),
    )
    with pytest.raises(si.SessionInputsError, match="silent undercount"):
        si.build_consumed_ids_document(data_dir=data_dir)


def test_a_snapshot_with_no_field_evaluations_is_counted_not_read_as_valid(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """A snapshot that evaluated nothing is its own shape.

    Not a refusal (it is a legal snapshot) and not VALID either — the kernel's
    own gate floors an unevaluated field at UNKNOWN. It is counted, so a
    session whose snapshots carry no evaluations reads as "M5 measured
    nothing" instead of "M5 passed".
    """
    bars = _bars(hinge, 1)
    empty = json.loads(bars[0].snapshot_json)
    empty["field_evaluations"] = []
    data_dir = _write_session(
        tmp_path,
        hinge,
        snapshots=[
            (bars[0].snapshot_id, INSTRUMENT, bars[0].as_of_ms, json.dumps(empty))
        ],
        preimages=[(bars[0].snapshot_id, bars[0].raw_event_id)],
        ticks=_tick_rows(bars),
    )
    states = si.build_consumed_ids_document(data_dir=data_dir)["consumed_field_states"]
    assert states["counts"]["consumed_ids_without_field_evaluations"] == 1
    assert states["m5_post_boot_consumed_ids_with_a_stale_field_evaluation"] == 0


def test_hinge_the_committed_snapshot_rows_carry_the_states_m5_counts(
    hinge: dict[str, Any],
) -> None:
    """The tools half of the snapshot hinge (the tos half is in ``tos/runtime``).

    Stated here so a regeneration that lost the STALE row turns red where the
    counting is tested, not only where the bytes are compared: without it
    every assertion above would pass against a fixture that cannot produce a
    stale line at all.
    """
    rows = hinge["payloads"]["marketfeed_snapshots"]
    states = {
        name: [
            evaluation[si.FIELD_EVALUATION_STATE_KEY]
            for evaluation in json.loads(row["snapshot_json"])[
                si.SNAPSHOT_FIELD_EVALUATIONS_KEY
            ]
        ]
        for name, row in rows.items()
    }
    assert states["stale"] == [si.STALE_FIELD_STATE]
    assert states["valid"] == [si.VALID_FIELD_STATE]
    assert si.STALE_FIELD_STATE not in states["unknown"]
    assert [
        observation[si.OBSERVATION_FIELD_STATE_KEY]
        for observation in json.loads(rows["unknown"]["snapshot_json"])[
            si.SNAPSHOT_OBSERVATIONS_KEY
        ]
    ] == [si.STALE_FIELD_STATE]
