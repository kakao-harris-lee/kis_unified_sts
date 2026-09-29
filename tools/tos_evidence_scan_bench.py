#!/usr/bin/env python3
"""Evidence-store `kind` scan benchmark (evidence growth plan §2 A1).

Answers ONE question, reproducibly: **how much wall time do the runtime's own
boot/recovery `SELECT ... FROM entries WHERE kind ...` queries cost as the evidence
history grows**, and how much of that an `entries(kind, seq)` index removes.

Three subcommands:

``profile``
    Read a REAL ``evidence.sqlite3`` (read-only; never written to) and report its
    per-``kind`` row/byte distribution — the distribution ``build`` replicates.

``build``
    Write a SYNTHETIC ``evidence.sqlite3`` holding ``--days`` trading days of that
    distribution. ⚠ **The synthetic chain is NOT valid.** Rows are copied verbatim from
    the reference file (payload, ``entry_digest``, ``chain_digest``, ``key_generation``)
    with only ``seq`` reassigned, so ``chain_digest`` values repeat and
    ``SqliteEvidenceStore.verify()`` on a synthetic file returns ``False``. That is
    deliberate and sufficient: the thing being measured is SCAN COST over the real byte
    distribution, and chain verification is not on the boot path at all (it runs only on
    restore — ``tos_runtime/operations/backup_set.py``'s own ``restore_set``). Nothing
    here is a substitute for a real chain; a synthetic file is measurement material and
    never a restore source.

``measure``
    Time every distinct boot/recovery query SHAPE (:data:`QUERY_SHAPES` — each one
    carries the reader modules it mirrors) against a given file, and optionally print
    each shape's ``EXPLAIN QUERY PLAN`` so index use is shown, not assumed.

**Why this file duplicates the ``entries`` DDL instead of importing it.** The import
firewall forbids anything outside ``tos/`` from importing ``tos`` or ``tos_runtime``
(``tools/tos_firewall_check.py`` rule (e)/TOS-FW-R), so this tool is pure stdlib and
carries its own copy of the ``entries`` DDL — the same "duplicate the literal, do not
reach across the boundary" discipline
``tos_runtime/operations/schema_migrations.py`` already documents for its own baseline
statements. Two checks keep that copy from silently drifting:

* at runtime, ``profile`` and ``build`` compare the reference file's FULL ``PRAGMA
  table_info`` — name, declared type, ``notnull``, ``pk``, not just the column names —
  against the copy below, and refuse on any disagreement;
* in the suite, ``tests/tools/test_tos_evidence_scan_bench.py`` READS
  ``tos/runtime/src/tos_runtime/evidence/store.py`` as text and asserts the real
  ``_CREATE_ENTRIES_TABLE_SQL`` literal still matches this module's copy. Reading that
  file is firewall-safe; importing it would not be.

Paths, day counts, session length and repeat counts are all arguments — nothing about a
particular host, run or threshold is written into this file.
"""

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

#: The live ``entries`` DDL, duplicated from ``tos_runtime/evidence/store.py``'s own
#: ``_CREATE_ENTRIES_TABLE_SQL`` (see the module docstring on why it is copied, and on the
#: drift check that keeps the copy honest). Triggers are deliberately NOT created on a
#: synthetic file: ``build`` never issues an ``UPDATE``/``DELETE``, and their absence keeps
#: the bulk insert path from paying a per-row trigger check that the real append path pays
#: once per row anyway.
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
#: column, in on-disk order. Names alone are not enough — a reference whose ``payload_json`` had
#: become nullable, or whose ``seq`` had stopped being the primary key, would pass a name-only
#: check while making the synthetic file a different thing from what the runtime uses (review
#: MEDIUM-HIGH-3). ``dflt_value`` is deliberately excluded: no column here declares one, and it
#: is the one field a harmless future default would move.
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

#: One reference kind's rows, in commit order — re-executed per synthetic repeat and streamed
#: (review HIGH-2). Named here rather than inlined so the "no ``fetchall``" property is visible
#: at the one place the query lives.
_TEMPLATE_SQL = (
    "SELECT segment_id, kind, record_class, runtime_identity_json, payload_json, "
    "entry_digest, chain_digest, key_generation, appended_at_monotonic_ns "
    "FROM entries WHERE kind = ? AND record_class = ? ORDER BY seq ASC"
)

#: The index A2 adds through the real ``migrate`` path. ``measure --with-index`` creates it
#: on a COPY so a before/after pair can be taken without rebuilding the synthetic file.
KIND_SEQ_INDEX_SQL = "CREATE INDEX IF NOT EXISTS entries_kind_seq ON entries(kind, seq)"


class BenchRefused(RuntimeError):
    """Raised when an input is not what this tool needs (a missing file, a reference whose
    ``entries`` shape disagrees with this module's own copy, an empty reference)."""


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
    """One distinct ``FROM entries`` query shape the runtime actually issues.

    Args:
        name: Stable identifier used in the report.
        sql: The SQL, verbatim in shape (parameter placeholders included).
        params: The bound parameters to time it with.
        readers: The runtime modules that issue this shape — the audit trail that keeps
            this table tied to real code rather than to a plausible guess.
        boot_path: Whether the runtime reaches this shape during boot/recovery (as opposed
            to an operator-triggered or post-trade path).
    """

    name: str
    sql: str
    params: tuple[object, ...]
    readers: tuple[str, ...]
    boot_path: bool


#: A kind the runtime writes constantly (77 % of rows in the 2026-09-28 reference run) and
#: **never reads back** — ``git grep`` finds no runtime reader for it at all (evidence growth
#: plan §1). Shapes parameterized with it are therefore a deliberate WORST CASE for the index,
#: not a query any module issues: pulling 77 % of the table through a non-covering index means
#: a random row lookup per hit instead of one sequential scan, so these shapes are expected to
#: get SLOWER once `entries_kind_seq` exists. They are measured precisely to put a number on
#: that regression's bound, and must never be read as a boot cost the index imposes.
_HOT_KIND = "TIME_HEALTH_SNAPSHOT"
#: A kind with a small but non-trivial share.
_WARM_KIND = "EVENT_CONSUMED"
#: A kind a real store may legitimately hold ZERO of — the worst case for an unindexed
#: scan (it reads every page and finds nothing) and the clearest case for the index.
_ABSENT_KIND = "REARM_APPROVED"

_SEND_KINDS = ("SEND_STARTED", "SEND_HANDED_OFF")
#: The EXACT set the real callers exclude — ``compose/_safety_wiring.py``'s stall observer and
#: ``compose/_operations_wiring.py`` both pass ``frozenset({"STM_ALERT"})``, one kind. An earlier
#: revision paired it with an invented ``STALL_ALERT`` that does not exist anywhere in ``tos/``
#: (review MEDIUM-6), which measured a two-parameter ``NOT IN`` no caller ever issues.
_TIP_EXCLUDED_KINDS = ("STM_ALERT",)
_RELEASE_KINDS = ("CAPACITY_RELEASE_INTENT", "CAPACITY_RELEASE_HELD")

#: Every distinct shape the 19 evidence-reading runtime modules issue (21 files match
#: ``FROM entries`` under ``tos/runtime/src``; ``rcl/gates.py`` and ``rcl/log.py`` query the
#: RCL commit log's own separate ``entries`` table, not this one), plus the two
#: unfiltered full scans (``replay``/``iter_entry_meta``) kept as the control group: an
#: index on ``kind`` cannot help those, and showing them unchanged is what proves the
#: measured improvement elsewhere is the index and not a warmer cache.
#:
#: A shape's ``readers`` names the modules that issue that SQL SHAPE; the bound ``params`` are
#: this benchmark's own choice of kind, spanning the three selectivity regimes that decide
#: whether an index helps: ``__hot`` (:data:`_HOT_KIND` — the worst case, no reader),
#: ``__warm`` (a kind boot genuinely reads in full), and ``__absent`` (a kind a real store may
#: hold zero of, which is both the commonest boot case and the index's best case).
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
    """Open ``path`` through sqlite's own read-only URI — a reference file is never
    written to, not even by an accidental journal creation."""
    if not path.is_file():
        raise BenchRefused(f"no sqlite file at {path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _entries_shape(conn: sqlite3.Connection) -> tuple[tuple[str, str, int, int], ...]:
    """``(name, type, notnull, pk)`` per column, in on-disk order — what the drift check compares.

    ``PRAGMA table_info`` rows are ``(cid, name, type, notnull, dflt_value, pk)``.
    """
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
        # Iterated, not `fetchall()`-ed — this module calls `fetchall` nowhere at all, which
        # is what lets `test_the_module_never_calls_fetchall` state the bound absolutely
        # instead of carving out exceptions the next edit could widen (review HIGH-2).
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
    """Write ``days`` trading days of the reference distribution to ``out``.

    Two scaling rules, because a real day is not simply "the reference window N times":

    * A kind the reference window holds MORE than ``boot_once_max_rows`` of is a recurring
      writer — replicated ``days * session_hours * 60 / reference_minutes`` times.
    * A kind at or below that count is a once-per-boot record (``RECOVERY_BARRIER``,
      ``TIME_SERVICE_STARTUP``, the ``*_POLICY_BOUND`` set) — replicated ``days`` times,
      one boot per trading day, never scaled by the within-session factor.

    ⚠ The resulting chain is NOT valid — see the module docstring.

    **Memory is bounded by** ``batch_rows``, **not by** ``days`` **or by the reference file's
    size.** Nothing is materialized: the reference kind is RE-QUERIED per repeat and streamed
    straight into the ``batch_rows``-sized insert batch, which is committed and cleared before
    the next is built. A 365-day build costs the same RSS as a 1-day one, against any reference.

    This is not a micro-optimization, and "the reference window is only minutes long" is not a
    bound — it is an assumption about the caller's input. An earlier revision of this tool's
    ``measure`` reached 16 GB RSS on a 90-day file and was SIGTERM'd by the host's earlyoom,
    taking an unrelated build down with it; the same revision's ``build`` held a whole kind's
    rows in a list while claiming this bound (review HIGH-2).

    Raises:
        BenchRefused: ``out`` already exists, or the reference shape disagrees with this
            tool's own DDL copy.
    """
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
                # Re-executed per repeat, and ITERATED — never `fetchall()`. The cursor is the
                # only thing standing between this loop and holding a whole kind in memory.
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
    """Refuse to report timings whose parameters do not mean what :data:`QUERY_SHAPES` claims.

    The three selectivity regimes are the whole point of the table: ``__absent`` is only the
    index's best case if the kind really is absent, and ``__hot`` is only the worst case if the
    kind really is the dominant one. Both were hardcoded strings that nothing checked against
    the file being measured (review MEDIUM-6), so a reference whose distribution had shifted —
    or a typo — would have produced a table that looked fine and meant something else.

    Raises:
        BenchRefused: The absent kind is present, or the hot kind is not the most frequent.
    """
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
    """Time every shape against ``db_path``, each repeat on a FRESH connection.

    A fresh connection per repeat drops sqlite's own per-connection page cache, so a
    repeat never reads the previous repeat's cached pages. The OS page cache is NOT
    dropped (this tool never asks for root) — every number is therefore a warm-OS-cache
    number, which understates the unindexed cost on a cold host rather than overstating
    the index's benefit.

    **Rows are STREAMED, never materialized with** ``fetchall()`` **— a deliberate difference
    from the readers this mirrors.** The real modules do call ``fetchall()``; at 365 days the hot
    kind is ~22 M rows of ~1.7 KB payload, so materializing them measures Python list/str
    allocation (and, measured here, gets the process killed at 16 GB RSS by the host's
    earlyoom) rather than the query cost this benchmark exists to compare. Iterating keeps
    memory bounded and still pays sqlite's own scan/seek and per-row decode — the part an
    index changes. The caller-side retention cost the readers additionally pay is real, but it
    is identical before and after an index, so it cannot affect the comparison.
    """
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
    """Create :data:`KIND_SEQ_INDEX_SQL` on ``db_path`` and return the wall seconds it took.

    A convenience for taking a before/after pair on ONE synthetic file. The production path
    is the ``migrate`` CLI — this function exists so the measurement does not have to stand
    up a custody root just to time an index build.
    """
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
            # Never overwrite: a measurement run is evidence a plan record cites, and silently
            # replacing an earlier run's numbers with a later run's is exactly the drift the
            # before/after table exists to make visible (review L6).
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
