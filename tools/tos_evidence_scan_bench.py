#!/usr/bin/env python3
"""Evidence-store `kind` scan benchmark (evidence growth plan §2 A1)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "QUERY_SHAPES",
    "BuildReport",
    "KindProfile",
    "Measurement",
    "QueryShape",
    "build_synthetic",
    "validate_shape_kinds",
    "main",
    "measure",
    "profile_kinds",
]

_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY,
    segment_id TEXT,
    kind TEXT NOT NULL,
    record_class TEXT NOT NULL,
    runtime_identity_json TEXT,
    payload_json TEXT NOT NULL,
    entry_digest TEXT NOT NULL,
    chain_digest TEXT NOT NULL,
    key_generation INTEGER NOT NULL,
    appended_at_monotonic_ns INTEGER NOT NULL
)
"""

#: The ``entries`` shape as ``PRAGMA table_info`` reports it: ``(name, type, notnull, pk)`` per
_ENTRIES_SHAPE: tuple[tuple[str, str, int, int], ...] = (
    ("seq", "INTEGER", 0, 1),
    ("segment_id", "TEXT", 0, 0),
    ("kind", "TEXT", 1, 0),
    ("record_class", "TEXT", 1, 0),
    ("runtime_identity_json", "TEXT", 0, 0),
    ("payload_json", "TEXT", 1, 0),
    ("entry_digest", "TEXT", 1, 0),
    ("chain_digest", "TEXT", 1, 0),
    ("key_generation", "INTEGER", 1, 0),
    ("appended_at_monotonic_ns", "INTEGER", 1, 0),
)

_TEMPLATE_SQL = (
    "SELECT segment_id, kind, record_class, runtime_identity_json, payload_json, "
    "entry_digest, chain_digest, key_generation, appended_at_monotonic_ns "
    "FROM entries WHERE kind = ? AND record_class = ? ORDER BY seq ASC"
)

KIND_SEQ_INDEX_SQL = "CREATE INDEX IF NOT EXISTS entries_kind_seq ON entries(kind, seq)"


class BenchRefused(RuntimeError):
    """Raised when an input is not what this tool needs (a missing file, a reference whose"""


@dataclass(frozen=True)
class KindProfile:
    """One ``kind``'s share of a reference file."""

    kind: str
    record_class: str
    rows: int
    payload_bytes: int


@dataclass(frozen=True)
class BuildReport:
    """What one :func:`build_synthetic` call produced."""

    path: str
    days: int
    rows: int
    file_bytes: int
    seconds: float
    recurring_repeats: int
    boot_repeats: int


@dataclass(frozen=True)
class QueryShape:
    """One distinct ``FROM entries`` query shape the runtime actually issues."""

    name: str
    sql: str
    params: tuple[object, ...]
    readers: tuple[str, ...]
    boot_path: bool


_HOT_KIND = "TIME_HEALTH_SNAPSHOT"
_WARM_KIND = "EVENT_CONSUMED"
_ABSENT_KIND = "REARM_APPROVED"

_SEND_KINDS = ("SEND_STARTED", "SEND_HANDED_OFF")
_TIP_EXCLUDED_KINDS = ("STM_ALERT",)
_RELEASE_KINDS = ("CAPACITY_RELEASE_INTENT", "CAPACITY_RELEASE_HELD")

QUERY_SHAPES: tuple[QueryShape, ...] = (
    QueryShape(
        name="by_kind_payload_asc__hot",
        sql="SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        params=(_HOT_KIND,),
        readers=(
            "engine/replay.py:194",
            "recovery/legacy_receipts.py:134",
            "recovery/reconciliation.py:226",
            "riskstate/flow_observation.py:216",
            "riskstate/position.py:146",
            "posttrade/release_consumer.py:576",
            "backtest/calibration_report.py:168",
        ),
        boot_path=True,
    ),
    QueryShape(
        name="by_kind_payload_asc__warm",
        sql="SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        params=(_WARM_KIND,),
        readers=("engine/replay.py:194", "engine/driver.py:447"),
        boot_path=True,
    ),
    QueryShape(
        name="by_kind_payload_unordered__absent",
        sql="SELECT payload_json FROM entries WHERE kind = ?",
        params=(_ABSENT_KIND,),
        readers=(
            "safety/rearm.py:682",
            "safety/ack.py:208",
            "compose/_operations_wiring.py:363",
            "evidence/store.py:337",
            "posttrade/release_consumer.py:747",
            "engine/replay_transmit.py:94",
        ),
        boot_path=True,
    ),
    QueryShape(
        name="by_kind_payload_desc__warm",
        sql="SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq DESC",
        params=(_WARM_KIND,),
        readers=(
            "posttrade/release_consumer.py:689",
            "posttrade/release_consumer.py:703",
        ),
        boot_path=False,
    ),
    QueryShape(
        name="by_kinds_in_payload_asc",
        sql=("SELECT payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq ASC"),
        params=_RELEASE_KINDS,
        readers=(
            "recon/evidence_reader.py:150",
            "recon/witness_synthetic.py:162",
            "engine/replay_stage.py:124",
        ),
        boot_path=True,
    ),
    QueryShape(
        name="by_kinds_in_payload_desc",
        sql="SELECT kind, payload_json FROM entries WHERE kind IN (?, ?) ORDER BY seq DESC",
        params=_RELEASE_KINDS,
        readers=("posttrade/release_consumer.py:369",),
        boot_path=False,
    ),
    QueryShape(
        name="exists_by_kind",
        sql="SELECT 1 FROM entries WHERE kind = ? LIMIT 1",
        params=(_ABSENT_KIND,),
        readers=("engine/replay_transmit.py:114",),
        boot_path=True,
    ),
    QueryShape(
        name="exists_by_kinds_after_seq",
        sql="SELECT 1 FROM entries WHERE kind IN (?, ?) AND seq > ? LIMIT 1",
        params=(*_SEND_KINDS, 0),
        readers=("engine/driver.py:477",),
        boot_path=True,
    ),
    QueryShape(
        name="count_by_kind__hot",
        sql="SELECT COUNT(*) FROM entries WHERE kind = ?",
        params=(_HOT_KIND,),
        readers=(
            "recovery/inputs.py:98",
            "recovery/inputs.py:104",
            "venue/service.py:126",
            "operations/backup_set.py:325",
        ),
        boot_path=True,
    ),
    QueryShape(
        name="count_by_kind__absent",
        sql="SELECT COUNT(*) FROM entries WHERE kind = ?",
        params=(_ABSENT_KIND,),
        readers=("recovery/inputs.py:98", "venue/service.py:126"),
        boot_path=True,
    ),
    QueryShape(
        name="by_kind_and_seq",
        sql="SELECT payload_json FROM entries WHERE kind = ? AND seq = ?",
        params=(_WARM_KIND, 1),
        readers=("riskstate/flow_observation.py:369",),
        boot_path=True,
    ),
    QueryShape(
        name="exists_seq_and_kind",
        sql="SELECT 1 FROM entries WHERE seq = ? AND kind = ?",
        params=(1, _WARM_KIND),
        readers=("safety/ack.py:195",),
        boot_path=True,
    ),
    QueryShape(
        name="tip_excluding_kinds",
        sql=(
            "SELECT seq, chain_digest, key_generation FROM entries "
            "WHERE kind NOT IN (?) ORDER BY seq DESC LIMIT 1"
        ),
        params=_TIP_EXCLUDED_KINDS,
        readers=("evidence/store.py:869",),
        boot_path=True,
    ),
    QueryShape(
        name="tip_unfiltered",
        sql="SELECT seq, chain_digest FROM entries ORDER BY seq DESC LIMIT 1",
        params=(),
        readers=("evidence/store.py:525", "evidence/store.py:835"),
        boot_path=True,
    ),
    QueryShape(
        name="full_scan_chain_control",
        sql=(
            "SELECT entry_digest, key_generation, chain_digest FROM entries "
            "ORDER BY seq ASC"
        ),
        params=(),
        readers=("evidence/store.py:777", "evidence/store.py:883"),
        boot_path=False,
    ),
)


@dataclass(frozen=True)
class Measurement:
    """One shape's timing against one file."""

    shape: str
    boot_path: bool
    rows_returned: int
    best_seconds: float
    seconds: tuple[float, ...]
    plan: tuple[str, ...]


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Open ``path`` through sqlite's own read-only URI — a reference file is never"""
    if not path.is_file():
        raise BenchRefused(f"no sqlite file at {path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _entries_shape(conn: sqlite3.Connection) -> tuple[tuple[str, str, int, int], ...]:
    """``(name, type, notnull, pk)`` per column, in on-disk order — what the drift check compares."""
    return tuple(
        (str(row[1]), str(row[2]), int(row[3]), int(row[5]))
        for row in conn.execute("PRAGMA table_info(entries)")
    )


def profile_kinds(reference: Path) -> tuple[KindProfile, ...]:
    """The per-``kind`` distribution of a real evidence file (read-only)."""
    conn = _connect_readonly(reference)
    try:
        shape = _entries_shape(conn)
        if shape != _ENTRIES_SHAPE:
            raise BenchRefused(
                f"{reference}: entries shape {shape!r} disagrees with this tool's own copy "
                f"{_ENTRIES_SHAPE!r} — refusing rather than building a synthetic file in a "
                "shape the runtime does not use"
            )
        rows = list(
            conn.execute(
                "SELECT kind, record_class, COUNT(*), SUM(LENGTH(payload_json)) "
                "FROM entries GROUP BY kind, record_class ORDER BY COUNT(*) DESC, kind ASC"
            )
        )
    finally:
        conn.close()
    if not rows:
        raise BenchRefused(f"{reference}: entries is empty — nothing to replicate")
    return tuple(
        KindProfile(
            kind=str(kind),
            record_class=str(record_class),
            rows=int(count),
            payload_bytes=int(payload_bytes or 0),
        )
        for kind, record_class, count, payload_bytes in rows
    )


def build_synthetic(
    reference: Path,
    out: Path,
    *,
    days: int,
    session_hours: float,
    reference_minutes: float,
    boot_once_max_rows: int,
    batch_rows: int,
) -> BuildReport:
    """Write ``days`` trading days of the reference distribution to ``out``."""
    if out.exists():
        raise BenchRefused(f"{out} already exists — refusing to overwrite")
    if days < 1:
        raise BenchRefused(f"--days must be >= 1, got {days}")
    profiles = profile_kinds(reference)
    recurring_repeats = round(days * session_hours * 60.0 / reference_minutes)
    boot_repeats = days

    started = time.monotonic()
    source = _connect_readonly(reference)
    out.parent.mkdir(parents=True, exist_ok=True)
    dest = sqlite3.connect(str(out))
    try:
        dest.execute("PRAGMA journal_mode=OFF")
        dest.execute("PRAGMA synchronous=OFF")
        dest.execute(_ENTRIES_TABLE_SQL)
        dest.execute("PRAGMA user_version = 1")
        insert_sql = (
            "INSERT INTO entries (seq, segment_id, kind, record_class, "
            "runtime_identity_json, payload_json, entry_digest, chain_digest, "
            "key_generation, appended_at_monotonic_ns) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        next_seq = 1
        total = 0
        for profile in profiles:
            repeats = (
                boot_repeats
                if profile.rows <= boot_once_max_rows
                else recurring_repeats
            )
            batch: list[tuple[object, ...]] = []
            for _ in range(repeats):
                for row in source.execute(
                    _TEMPLATE_SQL, (profile.kind, profile.record_class)
                ):
                    batch.append((next_seq, *row))
                    next_seq += 1
                    if len(batch) >= batch_rows:
                        dest.executemany(insert_sql, batch)
                        dest.commit()
                        total += len(batch)
                        batch.clear()
            if batch:
                dest.executemany(insert_sql, batch)
                dest.commit()
                total += len(batch)
    finally:
        dest.close()
        source.close()

    return BuildReport(
        path=str(out),
        days=days,
        rows=total,
        file_bytes=out.stat().st_size,
        seconds=time.monotonic() - started,
        recurring_repeats=recurring_repeats,
        boot_repeats=boot_repeats,
    )


def validate_shape_kinds(db_path: Path) -> None:
    """Refuse to report timings whose parameters do not mean what :data:`QUERY_SHAPES` claims."""
    conn = _connect_readonly(db_path)
    try:
        rows = list(
            conn.execute(
                "SELECT kind, COUNT(*) FROM entries GROUP BY kind ORDER BY COUNT(*) DESC"
            )
        )
    finally:
        conn.close()
    if not rows:
        raise BenchRefused(f"{db_path}: entries is empty — nothing to measure")
    counts = {str(kind): int(count) for kind, count in rows}
    if counts.get(_ABSENT_KIND):
        raise BenchRefused(
            f"{db_path}: {_ABSENT_KIND!r} is supposed to be ABSENT (it is the index's best "
            f"case) but the file holds {counts[_ABSENT_KIND]} row(s) — the shape named "
            "'__absent' would not measure what it claims"
        )
    most_frequent = str(rows[0][0])
    if most_frequent != _HOT_KIND:
        raise BenchRefused(
            f"{db_path}: the most frequent kind is {most_frequent!r} "
            f"({rows[0][1]} rows), not {_HOT_KIND!r} — the shape named '__hot' would not "
            "measure the worst case it claims to bound"
        )


def measure(
    db_path: Path,
    *,
    shapes: Sequence[QueryShape] = QUERY_SHAPES,
    repeats: int,
    explain: bool,
) -> tuple[Measurement, ...]:
    """Time every shape against ``db_path``, each repeat on a FRESH connection."""
    if repeats < 1:
        raise BenchRefused(f"--repeats must be >= 1, got {repeats}")
    if not db_path.is_file():
        raise BenchRefused(f"no sqlite file at {db_path}")
    validate_shape_kinds(db_path)
    results: list[Measurement] = []
    for shape in shapes:
        timings: list[float] = []
        rows_returned = 0
        plan: tuple[str, ...] = ()
        for _ in range(repeats):
            conn = _connect_readonly(db_path)
            try:
                started = time.perf_counter()
                streamed = 0
                for _row in conn.execute(shape.sql, shape.params):
                    streamed += 1
                timings.append(time.perf_counter() - started)
                rows_returned = streamed
                if explain and not plan:
                    plan = tuple(
                        " ".join(str(part) for part in row)
                        for row in conn.execute(
                            f"EXPLAIN QUERY PLAN {shape.sql}", shape.params
                        )
                    )
            finally:
                conn.close()
        results.append(
            Measurement(
                shape=shape.name,
                boot_path=shape.boot_path,
                rows_returned=rows_returned,
                best_seconds=min(timings),
                seconds=tuple(timings),
                plan=plan,
            )
        )
    return tuple(results)


def create_kind_index(db_path: Path) -> float:
    """Create :data:`KIND_SEQ_INDEX_SQL` on ``db_path`` and return the wall seconds it took."""
    started = time.monotonic()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(KIND_SEQ_INDEX_SQL)
        conn.commit()
    finally:
        conn.close()
    return time.monotonic() - started


def _print_profile(profiles: Sequence[KindProfile]) -> None:
    total_rows = sum(p.rows for p in profiles)
    total_bytes = sum(p.payload_bytes for p in profiles)
    print(f"{'kind':<34}{'rows':>9}{'payload_bytes':>15}{'row %':>9}{'byte %':>9}")
    for profile in profiles:
        print(
            f"{profile.kind:<34}{profile.rows:>9}{profile.payload_bytes:>15}"
            f"{100.0 * profile.rows / total_rows:>8.1f}%"
            f"{100.0 * profile.payload_bytes / total_bytes:>8.1f}%"
        )
    print(f"{'TOTAL':<34}{total_rows:>9}{total_bytes:>15}")


def _print_measurements(measurements: Sequence[Measurement]) -> None:
    print(f"{'shape':<34}{'boot':>6}{'rows':>12}{'best_ms':>12}")
    for m in measurements:
        print(
            f"{m.shape:<34}{'yes' if m.boot_path else 'no':>6}{m.rows_returned:>12}"
            f"{m.best_seconds * 1000.0:>12.3f}"
        )
        for line in m.plan:
            print(f"    plan: {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evidence-store kind-scan benchmark (evidence growth plan §2 A1). Synthetic "
            "files carry an INVALID chain by construction — measurement material only."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    profile_parser = sub.add_parser(
        "profile",
        help="Report a real evidence file's per-kind distribution (read-only).",
    )
    profile_parser.add_argument("--reference", required=True, type=Path)

    build_parser_ = sub.add_parser(
        "build", help="Write a synthetic evidence file of --days trading days."
    )
    build_parser_.add_argument("--reference", required=True, type=Path)
    build_parser_.add_argument("--out", required=True, type=Path)
    build_parser_.add_argument("--days", required=True, type=int)
    build_parser_.add_argument("--session-hours", default=7.0, type=float)
    build_parser_.add_argument("--reference-minutes", default=15.0, type=float)
    build_parser_.add_argument("--boot-once-max-rows", default=1, type=int)
    build_parser_.add_argument("--batch-rows", default=10000, type=int)

    measure_parser = sub.add_parser(
        "measure", help="Time every boot/recovery query shape against a file."
    )
    measure_parser.add_argument("--db", required=True, type=Path)
    measure_parser.add_argument("--repeats", default=3, type=int)
    measure_parser.add_argument("--explain", action="store_true")
    measure_parser.add_argument(
        "--create-index",
        action="store_true",
        help=(
            "Create entries_kind_seq on --db before measuring (the A2 'after' half of a "
            "before/after pair). Mutates --db; run it on a copy, never on live data."
        ),
    )
    measure_parser.add_argument("--json-out", default=None, type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "profile":
            _print_profile(profile_kinds(args.reference))
            return 0
        if args.command == "build":
            report = build_synthetic(
                args.reference,
                args.out,
                days=args.days,
                session_hours=args.session_hours,
                reference_minutes=args.reference_minutes,
                boot_once_max_rows=args.boot_once_max_rows,
                batch_rows=args.batch_rows,
            )
            print(json.dumps(report.__dict__, indent=2))
            return 0
        if args.create_index:
            print(f"index built in {create_kind_index(args.db):.3f} s")
        measurements = measure(args.db, repeats=args.repeats, explain=args.explain)
        _print_measurements(measurements)
        if args.json_out is not None:
            if args.json_out.exists():
                raise BenchRefused(
                    f"{args.json_out} already exists — refusing to overwrite a previous "
                    "measurement"
                )
            args.json_out.write_text(
                json.dumps([m.__dict__ for m in measurements], indent=2)
            )
        return 0
    except BenchRefused as exc:
        print(f"tos_evidence_scan_bench: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
