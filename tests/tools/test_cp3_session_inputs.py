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


def _write_session(
    tmp_path: Path,
    hinge: dict[str, Any],
    *,
    snapshots: list[tuple[str, str, int]],
    preimages: list[tuple[str, str]],
    entries: list[tuple[int, str, dict[str, Any]]] | None = None,
    marketfeed_version: int | None = None,
    evidence_version: int | None = None,
) -> Path:
    """A session data dir holding the two stores, with the given rows."""
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
        conn.executemany("INSERT INTO snapshots VALUES (?, ?, ?)", snapshots)
        conn.executemany("INSERT INTO preimages VALUES (?, ?)", preimages)
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
            conn.executemany(
                "INSERT INTO entries VALUES (?, ?, ?)",
                [
                    (seq, kind, json.dumps(payload))
                    for seq, kind, payload in (entries or [])
                ],
            )
            conn.commit()
        finally:
            conn.close()
    return data_dir


def _no_action(**extra: Any) -> dict[str, Any]:
    payload = {
        "kind": "DECISION_OUTCOME_EMITTED",
        "outcome_type": "NoActionOutcome",
        "halt_reason": "NO_ACTION_OUTCOME",
        "outcome_digest": "sha256:no-action",
        "capsule_id": "cap-1",
    }
    payload.update(extra)
    return payload


def _three_bar_session(tmp_path: Path, hinge: dict[str, Any], **kwargs: Any) -> Path:
    """Three ticks: 09:00, 09:01, 09:02 — consumed, in that order."""
    return _write_session(
        tmp_path,
        hinge,
        snapshots=[
            ("snap-1", INSTRUMENT, 1_760_000_000_000),
            ("snap-2", INSTRUMENT, 1_760_000_060_000),
            ("snap-3", INSTRUMENT, 1_760_000_120_000),
        ],
        preimages=[
            ("snap-1", _event_id("0900")),
            ("snap-2", _event_id("0901")),
            ("snap-3", _event_id("0902")),
        ],
        **kwargs,
    )


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


@pytest.mark.parametrize("store", ["marketfeed", "evidence"])
def test_red_a_store_at_another_schema_version_is_refused(
    tmp_path: Path, hinge: dict[str, Any], store: str
) -> None:
    """**Guard: the mirrored schema version.**

    Concrete input: the store file stamps ``PRAGMA user_version`` one past what
    this extractor was written for — exactly what a ``migrate`` run does. The
    queries would still "work" (sqlite does not mind extra columns), so without
    this pin the extractor would answer a question about a store shape nobody
    checked. Remove the version comparison in ``_connect_ro`` and both cases
    pass silently.
    """
    bumped = hinge[store]["schema_version"] + 1
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[(1, "DECISION_OUTCOME_EMITTED", _no_action())] * 1,
        **{f"{'marketfeed' if store == 'marketfeed' else 'evidence'}_version": bumped},
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        if store == "marketfeed":
            si.build_consumed_ids_document(data_dir=data_dir)
        else:
            si.live_decision_records(data_dir)
    assert f"user_version={bumped}" in str(excinfo.value)


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
# live-decisions
# ===========================================================================


def test_live_decisions_pair_with_the_snapshots_in_order(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """One record per decision, in B1b's trace shape, keyed by the bar."""
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "ATTESTED_INPUTS", {"ignored": True}),
            (2, "DECISION_OUTCOME_EMITTED", _no_action(capsule_id="cap-1")),
            (3, "DECISION_OUTCOME_EMITTED", _no_action(capsule_id="cap-2")),
            (4, "DECISION_OUTCOME_EMITTED", _no_action(capsule_id="cap-3")),
        ],
    )
    records = si.live_decision_records(data_dir)

    assert [record["raw_event_id"] for record in records] == [
        _event_id("0900"),
        _event_id("0901"),
        _event_id("0902"),
    ]
    assert {record["outcome_kind"] for record in records} == {"NO_ACTION"}
    assert [record["capsule_id"] for record in records] == ["cap-1", "cap-2", "cap-3"]
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
    assert records[0]["as_of_ms"] == 1_760_000_000_000


def test_capacity_denial_comes_from_the_flow_halt_in_the_same_block(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """B1b's ``capacity_denied`` is one flow halt reason, and only that one."""
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _no_action()),
            (2, "FLOW_HALTED", {"halt_reason": si.CAPACITY_DENIAL_HALT_REASON}),
            (3, "DECISION_OUTCOME_EMITTED", _no_action()),
            (4, "FLOW_HALTED", {"halt_reason": "SOMETHING_ELSE"}),
            (5, "DECISION_OUTCOME_EMITTED", _no_action()),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["capacity_denied"] for record in records] == [True, False, False]
    assert records[1]["flow_halt_reason"] == "SOMETHING_ELSE"
    assert records[2]["flow_halt_reason"] is None


def test_red_unequal_snapshot_and_decision_counts_are_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: the ordered pairing is counted, never assumed.**

    Concrete input: three snapshots and two decisions — the held-runtime shape,
    where a tick is enqueued and run later (the scheduler's own
    ``queued_until_recovery`` branch). Without the count check the third bar's
    decision would be read off the second bar's record and every later record
    would be one bar out, which is precisely the silent misattribution B3
    exists to rule out.
    """
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _no_action()),
            (2, "DECISION_OUTCOME_EMITTED", _no_action()),
        ],
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.live_decision_records(data_dir)
    assert "3 snapshot(s)" in str(excinfo.value)
    assert "2 decision(s)" in str(excinfo.value)


def test_red_a_flow_record_before_any_decision_is_refused(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: a flow record belongs to the decision that started it.**

    Concrete input: a ``FLOW_HALTED`` row at a lower ``seq`` than the first
    decision — what a replayed or recovered flow looks like in the store.
    Attributing it forward would put one tick's capacity denial on another
    tick's bar.
    """
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "FLOW_HALTED", {"halt_reason": si.CAPACITY_DENIAL_HALT_REASON}),
            (2, "DECISION_OUTCOME_EMITTED", _no_action()),
            (3, "DECISION_OUTCOME_EMITTED", _no_action()),
            (4, "DECISION_OUTCOME_EMITTED", _no_action()),
        ],
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.live_decision_records(data_dir)
    assert "no decision record before it" in str(excinfo.value)


def test_red_a_proposal_outcome_is_refused_rather_than_labelled(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """**Guard: ACTION vs FLAT is not derivable from the durable record.**

    Concrete input: a ``DECISION_OUTCOME_EMITTED`` whose ``outcome_type`` is
    ``Proposal``. B1b resolves ACTION/FLAT from the authored policy's rule
    index via the outcome's rationale; the evidence record carries neither.
    Guessing either label would make this module, not the engine, the thing
    that decided — and B3 would report the guess as agreement or as a
    difference with equal confidence.
    """
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _no_action()),
            (2, "DECISION_OUTCOME_EMITTED", _no_action(outcome_type="Proposal")),
            (3, "DECISION_OUTCOME_EMITTED", _no_action()),
        ],
    )
    with pytest.raises(si.SessionInputsError) as excinfo:
        si.live_decision_records(data_dir)
    assert "'Proposal'" in str(excinfo.value)


def test_a_tick_that_emitted_no_outcome_keeps_b1bs_own_token(
    tmp_path: Path, hinge: dict[str, Any]
) -> None:
    """A withheld decision is ``NO_OUTCOME``, not a fourth decision kind.

    B1b refuses to call it one (``replay.py::_attribute_rule``), so the live
    side records the same token and B3's closed-set check surfaces it rather
    than this module quietly calling it NO_ACTION — which would report a
    withheld tick as agreement with an offline no-action.
    """
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _no_action()),
            (2, "DECISION_WITHHELD", {"halt_reason": "VECTOR_OUTCOME_UNSUPPORTED"}),
            (3, "COORDINATOR_PRECONDITION_REFUSED", {"halt_reason": "GATE"}),
        ],
    )
    records = si.live_decision_records(data_dir)
    assert [record["outcome_kind"] for record in records] == [
        "NO_ACTION",
        si.NO_OUTCOME_KIND,
        si.NO_OUTCOME_KIND,
    ]
    assert records[1]["pipeline_halt_reason"] == "VECTOR_OUTCOME_UNSUPPORTED"


# ===========================================================================
# CLI, hinge, firewall
# ===========================================================================


def test_cli_writes_both_inputs(tmp_path: Path, hinge: dict[str, Any]) -> None:
    """Both subcommands land their files, and the sidecar describes the bytes."""
    data_dir = _three_bar_session(
        tmp_path,
        hinge,
        entries=[
            (1, "DECISION_OUTCOME_EMITTED", _no_action()),
            (2, "DECISION_OUTCOME_EMITTED", _no_action()),
            (3, "DECISION_OUTCOME_EMITTED", _no_action()),
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
    # the sidecar states the two things a reader must not assume
    assert "rationale" in lineage["join"]["rule_id"]
    assert "NOT B1a's bar label" in lineage["join"]["as_of_ms"]


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
    assert hinge["marketfeed"]["schema_version"] == si.PINNED_MARKETFEED_SCHEMA_VERSION
    assert hinge["evidence"]["schema_version"] == si.PINNED_EVIDENCE_SCHEMA_VERSION


def test_the_extractor_imports_neither_tos_nor_the_runtime() -> None:
    """Sqlite read-only, by construction: the module's own import list.

    The firewall's reverse scan already refuses ``import tos`` anywhere outside
    ``tos/``; this states the stronger property this module claims — it reaches
    the two stores as FILES, through stdlib only, so nothing here can be
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
