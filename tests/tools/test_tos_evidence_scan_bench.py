"""Focused tests for the evidence `kind`-scan benchmark (evidence growth plan §2 A1,
``tools/tos_evidence_scan_bench.py``).

The tool's job is to produce NUMBERS that a plan then records, so what has to be tested is not
"is it fast" but "is what it measured really what it claims": the reference file is never
written to, the synthetic distribution scales the way the tool documents, a reference whose
``entries`` shape has drifted from the tool's own duplicated DDL is refused rather than
silently replicated, and the before/after index measurement really does change the query plan.

Hermetic: every file this module writes goes into ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_evidence_scan_bench.py"


def _load_bench_module():
    spec = importlib.util.spec_from_file_location(
        "tos_evidence_scan_bench", _MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bench = _load_bench_module()


def _write_reference(path: Path, *, hot_rows: int = 20, boot_rows: int = 1) -> None:
    """A miniature stand-in for a real ``evidence.sqlite3``: one high-volume kind, one warm
    kind, and one once-per-boot kind, in the real ``entries`` shape."""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(bench._ENTRIES_TABLE_SQL)
        rows = []
        seq = 1
        for kind, count, payload in (
            ("TIME_HEALTH_SNAPSHOT", hot_rows, "x" * 200),
            ("EVENT_CONSUMED", 5, "y" * 50),
            ("RECOVERY_BARRIER", boot_rows, "z" * 10),
        ):
            for _ in range(count):
                rows.append(
                    (
                        seq,
                        None,
                        kind,
                        kind,
                        None,
                        payload,
                        hashlib.sha256(str(seq).encode()).hexdigest(),
                        hashlib.sha256(f"c{seq}".encode()).hexdigest(),
                        1,
                        seq,
                    )
                )
                seq += 1
        conn.executemany(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
        conn.commit()
    finally:
        conn.close()


def test_profile_reports_every_kind_and_leaves_the_reference_untouched(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    before = hashlib.sha256(reference.read_bytes()).hexdigest()

    profiles = bench.profile_kinds(reference)

    assert {p.kind: p.rows for p in profiles} == {
        "TIME_HEALTH_SNAPSHOT": 20,
        "EVENT_CONSUMED": 5,
        "RECOVERY_BARRIER": 1,
    }
    # Sorted by row count descending — the shape the plan's distribution table is read from.
    assert profiles[0].kind == "TIME_HEALTH_SNAPSHOT"
    assert profiles[0].payload_bytes == 20 * 200
    # A reference file is opened read-only; a profile run must not even create a journal.
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == before
    assert not (tmp_path / "evidence.sqlite3-journal").exists()


def test_a_reference_whose_entries_shape_drifted_is_refused(tmp_path: Path) -> None:
    """The drift guard on the duplicated DDL, proven red.

    ``tools/`` cannot import ``tos_runtime`` (the import firewall's reverse rule), so this tool
    carries its own copy of the ``entries`` DDL. Without this check the copy could fall behind
    the real store's shape and the tool would go on building synthetic files in a shape the
    runtime no longer uses — measuring the wrong thing, silently.
    """
    reference = tmp_path / "drifted.sqlite3"
    conn = sqlite3.connect(str(reference))
    conn.execute("CREATE TABLE entries (seq INTEGER PRIMARY KEY, kind TEXT)")
    conn.execute("INSERT INTO entries VALUES (1, 'TIME_HEALTH_SNAPSHOT')")
    conn.commit()
    conn.close()

    with pytest.raises(bench.BenchRefused, match="disagree with this tool's own copy"):
        bench.profile_kinds(reference)


def test_an_empty_reference_is_refused(tmp_path: Path) -> None:
    reference = tmp_path / "empty.sqlite3"
    conn = sqlite3.connect(str(reference))
    conn.execute(bench._ENTRIES_TABLE_SQL)
    conn.commit()
    conn.close()

    with pytest.raises(bench.BenchRefused, match="nothing to replicate"):
        bench.profile_kinds(reference)


def test_build_scales_recurring_kinds_by_session_and_boot_kinds_by_day(
    tmp_path: Path,
) -> None:
    """The two scaling rules, asserted separately.

    A single factor for every kind would inflate the once-per-boot records 28-fold, which is
    wrong in kind rather than in magnitude: a trading day holds one ``RECOVERY_BARRIER``,
    not one per polling window.
    """
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out = tmp_path / "synth.sqlite3"

    report = bench.build_synthetic(
        reference,
        out,
        days=3,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=7,  # deliberately smaller than one kind's batch — exercises the flush path
    )

    assert report.recurring_repeats == 84  # 3 days * 7 h * 60 / 15
    assert report.boot_repeats == 3
    conn = sqlite3.connect(str(out))
    try:
        counts = dict(
            conn.execute("SELECT kind, COUNT(*) FROM entries GROUP BY kind").fetchall()
        )
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        seqs = [row[0] for row in conn.execute("SELECT seq FROM entries ORDER BY seq")]
    finally:
        conn.close()

    assert counts == {
        "TIME_HEALTH_SNAPSHOT": 20 * 84,
        "EVENT_CONSUMED": 5 * 84,
        "RECOVERY_BARRIER": 3,
    }
    assert report.rows == sum(counts.values())
    # seq is a dense 1..N — the same "no caller-supplied seq, no gaps" shape the real store has.
    assert seqs == list(range(1, report.rows + 1))


def test_build_refuses_to_overwrite_an_existing_file(tmp_path: Path) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out = tmp_path / "synth.sqlite3"
    out.write_bytes(b"")

    with pytest.raises(bench.BenchRefused, match="refusing to overwrite"):
        bench.build_synthetic(
            reference,
            out,
            days=1,
            session_hours=7.0,
            reference_minutes=15.0,
            boot_once_max_rows=1,
            batch_rows=100,
        )


def test_build_refuses_a_non_positive_day_count(tmp_path: Path) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)

    with pytest.raises(bench.BenchRefused, match="must be >= 1"):
        bench.build_synthetic(
            reference,
            tmp_path / "synth.sqlite3",
            days=0,
            session_hours=7.0,
            reference_minutes=15.0,
            boot_once_max_rows=1,
            batch_rows=100,
        )


def _measure(db: Path, *, explain: bool = True):
    return {m.shape: m for m in bench.measure(db, repeats=1, explain=explain)}


def test_measure_covers_every_shape_and_the_index_changes_the_plan(
    tmp_path: Path,
) -> None:
    """The before/after the plan's §7 table is built from, on one file.

    The "before" half is what keeps this honest: asserting only that the indexed plan mentions
    the index would still pass if the unindexed plan had mentioned it too.
    """
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    db = tmp_path / "synth.sqlite3"
    bench.build_synthetic(
        reference,
        db,
        days=1,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=1000,
    )

    before = _measure(db)
    assert set(before) == {shape.name for shape in bench.QUERY_SHAPES}
    assert before["by_kind_payload_asc__hot"].rows_returned == 20 * 28
    for name in ("by_kind_payload_asc__hot", "count_by_kind__absent"):
        assert "SCAN entries" in " ".join(before[name].plan), name
        assert "entries_kind_seq" not in " ".join(before[name].plan), name

    assert bench.create_kind_index(db) >= 0.0

    after = _measure(db)
    for name in ("by_kind_payload_asc__hot", "count_by_kind__absent"):
        assert "entries_kind_seq" in " ".join(after[name].plan), name
    # The two unfiltered full scans are the control group: an index on `kind` cannot help them,
    # so they must be unchanged — which is what makes the improvement above attributable.
    assert "entries_kind_seq" not in " ".join(after["full_scan_chain_control"].plan)
    # Row counts are identical before and after: an index changes cost, never results.
    assert {name: m.rows_returned for name, m in after.items()} == {
        name: m.rows_returned for name, m in before.items()
    }


def test_measure_refuses_a_non_positive_repeat_count(tmp_path: Path) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    db = tmp_path / "synth.sqlite3"
    bench.build_synthetic(
        reference,
        db,
        days=1,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=1000,
    )

    with pytest.raises(bench.BenchRefused, match="must be >= 1"):
        bench.measure(db, repeats=0, explain=False)


def test_every_query_shape_names_at_least_one_real_reader_module() -> None:
    """A shape with no reader behind it is a benchmark of something nothing does.

    Each ``readers`` entry is a ``path:line`` into ``tos/runtime/src/tos_runtime`` — checked
    here for existence of the FILE (line numbers drift; a deleted module does not).
    """
    runtime_src = _REPO_ROOT / "tos" / "runtime" / "src" / "tos_runtime"
    for shape in bench.QUERY_SHAPES:
        assert shape.readers, shape.name
        for reader in shape.readers:
            module_path, _, line = reader.partition(":")
            assert line.isdigit(), reader
            assert (runtime_src / module_path).is_file(), reader


def test_main_profile_and_build_round_trip_through_the_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    out = tmp_path / "synth.sqlite3"

    assert bench.main(["profile", "--reference", str(reference)]) == 0
    assert "TIME_HEALTH_SNAPSHOT" in capsys.readouterr().out

    assert (
        bench.main(
            ["build", "--reference", str(reference), "--out", str(out), "--days", "1"]
        )
        == 0
    )
    assert out.is_file()

    json_out = tmp_path / "measured.json"
    assert (
        bench.main(
            [
                "measure",
                "--db",
                str(out),
                "--repeats",
                "1",
                "--json-out",
                str(json_out),
            ]
        )
        == 0
    )
    assert json_out.is_file()


def test_main_reports_a_refusal_as_exit_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bench.main(["profile", "--reference", str(tmp_path / "absent.sqlite3")]) == 1
    assert "no sqlite file at" in capsys.readouterr().err
