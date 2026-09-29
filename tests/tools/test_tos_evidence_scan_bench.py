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

    with pytest.raises(bench.BenchRefused, match="disagrees with this tool's own copy"):
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


# -- review 2026-09-30 dispositions -------------------------------------------------------------


class _NoFetchAllCursor:
    """A cursor proxy that iterates normally but explodes on ``fetchall``."""

    def __init__(self, inner) -> None:
        self._inner = inner

    def __iter__(self):
        return iter(self._inner)

    def fetchall(self):
        raise AssertionError("fetchall() called — this module must stream")

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _NoFetchAllConnection:
    def __init__(self, inner) -> None:
        self._inner = inner

    def execute(self, *args, **kwargs):
        return _NoFetchAllCursor(self._inner.execute(*args, **kwargs))

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _NoFetchAllSqlite:
    """Stands in for the module's own ``sqlite3`` so every cursor it opens refuses
    ``fetchall``. ``sqlite3.Cursor`` is a C type and cannot be monkeypatched directly.
    """

    def __init__(self, real) -> None:
        self._real = real

    def connect(self, *args, **kwargs):
        return _NoFetchAllConnection(self._real.connect(*args, **kwargs))

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_the_module_never_calls_fetchall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HIGH-2, structurally.

    The memory bound this tool documents is only real if nothing materializes a result set. An
    earlier revision claimed the bound while ``build_synthetic`` held a whole kind's rows in a
    list, and its ``measure`` had already been killed at 16 GB RSS for exactly that. A docstring
    cannot enforce it; this can — it goes red the moment any path reverts to ``fetchall``.
    """
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    monkeypatch.setattr(bench, "sqlite3", _NoFetchAllSqlite(sqlite3))

    bench.profile_kinds(reference)
    db = tmp_path / "synth.sqlite3"
    bench.build_synthetic(
        reference,
        db,
        days=2,
        session_hours=7.0,
        reference_minutes=15.0,
        boot_once_max_rows=1,
        batch_rows=7,
    )
    bench.validate_shape_kinds(db)
    bench.measure(db, repeats=1, explain=True)


def test_the_duplicated_entries_ddl_still_matches_the_real_store(
    tmp_path: Path,
) -> None:
    """MEDIUM-HIGH-3: the copy is checked against the source of truth, by READING it.

    The firewall forbids ``tools/`` from importing ``tos_runtime`` (rule TOS-FW-R), so the DDL
    is duplicated. Reading the real module as text is firewall-safe and closes the drift the
    duplication otherwise invites: this goes red if ``_CREATE_ENTRIES_TABLE_SQL`` changes and
    the copy does not.
    """
    del tmp_path
    store_src = (
        _REPO_ROOT / "tos" / "runtime" / "src" / "tos_runtime" / "evidence" / "store.py"
    ).read_text()
    marker = "_CREATE_ENTRIES_TABLE_SQL = "
    start = store_src.index(marker) + len(marker)
    literal = store_src[start:]
    quote = literal[:3]
    assert quote == '"""', f"unexpected literal form: {literal[:20]!r}"
    real_ddl = literal[3 : literal.index('"""', 3)]

    assert _normalized(real_ddl) == _normalized(bench._ENTRIES_TABLE_SQL)


def _normalized(sql: str) -> str:
    """Whitespace-insensitive SQL comparison — indentation differs between the two files, the
    column list must not."""
    return " ".join(sql.split())


def test_the_entries_shape_copy_matches_what_the_real_store_creates(
    tmp_path: Path,
) -> None:
    """The runtime half of the same guard: the ``(name, type, notnull, pk)`` tuple this tool
    compares against must be what the DDL it carries actually produces."""
    path = tmp_path / "shape.sqlite3"
    conn = sqlite3.connect(str(path))
    conn.execute(bench._ENTRIES_TABLE_SQL)
    conn.commit()
    try:
        assert bench._entries_shape(conn) == bench._ENTRIES_SHAPE
    finally:
        conn.close()


def test_a_reference_whose_column_type_changed_is_refused(tmp_path: Path) -> None:
    """A name-only drift check passes this; the full ``table_info`` comparison does not
    (review MEDIUM-HIGH-3). ``payload_json`` losing NOT NULL is the shape of change that would
    quietly make the synthetic file a different thing from the runtime's own."""
    reference = tmp_path / "loosened.sqlite3"
    conn = sqlite3.connect(str(reference))
    conn.execute(
        bench._ENTRIES_TABLE_SQL.replace(
            "payload_json TEXT NOT NULL", "payload_json TEXT"
        )
    )
    conn.execute(
        "INSERT INTO entries VALUES (1, NULL, 'K', 'K', NULL, 'p', 'd', 'c', 1, 1)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(bench.BenchRefused, match="disagrees with this tool's own copy"):
        bench.profile_kinds(reference)


def test_measure_refuses_when_the_absent_kind_is_not_absent(tmp_path: Path) -> None:
    """MEDIUM-6. ``__absent`` is only the index's best case if the kind really is absent."""
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
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO entries VALUES (999999, NULL, 'REARM_APPROVED', 'REARM_APPROVED', "
        "NULL, 'p', 'd', 'c', 1, 1)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(bench.BenchRefused, match="supposed to be ABSENT"):
        bench.measure(db, repeats=1, explain=False)


def test_measure_refuses_when_the_hot_kind_is_not_the_most_frequent(
    tmp_path: Path,
) -> None:
    """MEDIUM-6, the other half. ``__hot`` is only the worst case it claims to bound if the
    kind really is the dominant one."""
    reference = tmp_path / "evidence.sqlite3"
    # EVENT_CONSUMED outnumbers TIME_HEALTH_SNAPSHOT here — a distribution that would make the
    # '__hot' shape measure something other than the worst case.
    _write_reference(reference, hot_rows=2)
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

    with pytest.raises(bench.BenchRefused, match="most frequent kind"):
        bench.measure(db, repeats=1, explain=False)


def test_json_out_refuses_to_overwrite_a_previous_measurement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """L6: a measurement run is evidence a plan record cites."""
    reference = tmp_path / "evidence.sqlite3"
    _write_reference(reference)
    db = tmp_path / "synth.sqlite3"
    assert (
        bench.main(
            ["build", "--reference", str(reference), "--out", str(db), "--days", "1"]
        )
        == 0
    )
    capsys.readouterr()
    json_out = tmp_path / "measured.json"
    argv = ["measure", "--db", str(db), "--repeats", "1", "--json-out", str(json_out)]

    assert bench.main(argv) == 0
    first = json_out.read_text()

    assert bench.main(argv) == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert json_out.read_text() == first
