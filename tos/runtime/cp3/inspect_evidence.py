"""Read-only evidence join — one recorded session bar → what the runtime did with it.

Part of the CP-3 ``cp3`` package (roadmap
``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1: «왜 이 바에서 이 결정이었나»).
Its one job is the KEY join from a journal bar's ``raw_event_id`` to the
decision records the engine wrote for that bar, so
:mod:`cp3.inspect_session` can print the engine's own answer beside the
re-evaluated rules.

**Why this lives inside ``tos/`` and not beside the journal reader in
``tools/``.** The import firewall is bidirectional
(``tools/tos_firewall_check.py`` TOS-FW-R): nothing outside ``tos/`` may import
``tos``/``tos_runtime``, so a legacy-side joiner must MIRROR the store
literals it reads — which is what
:mod:`tools.tos_cp3.session_inputs` does, pinned against a committed hinge.
This module is the other side of that trade: it is in RUNTIME scope, so it
imports the real file-name and schema-version constants from the stores
themselves and no literal can drift.

**The join (three durable rows).** Identical in shape to
:mod:`tools.tos_cp3.session_inputs`'s own documented chain, read here from the
source constants instead of mirrored ones:

1. ``marketfeed.sqlite3``'s ``preimages(snapshot_id, raw_event_id)`` — the bar's
   ``raw_event_id`` names the Critical Input Snapshot the issuer built from it;
2. ``inbox.sqlite3``'s ``events`` — the ``DECISION_TICK`` whose
   ``decision_tick.capsule.critical_input_snapshot.snapshot_id`` is that
   snapshot, carrying the ``event_id`` and the two evidence ``seq`` stamps the
   driver writes around the handler
   (``tos_runtime.engine.driver.EngineDriver._process_next``);
3. ``evidence.sqlite3``'s ``entries`` — every record in that tick's
   ``(handling_started_evidence_seq, consumed_evidence_seq]`` window.

**Nothing is guessed.** A bar whose chain breaks at any link gets an
:class:`BarEvidence` whose ``unjoined_reason`` names the broken link, never a
positional pairing: pairing by position is the inference the stores can
contradict silently (session_inputs' own module docstring, Claude lane MEDIUM
R1 2026-10-14). An ambiguous link — one ``raw_event_id`` behind two snapshots,
one snapshot bound by two ticks — is also "unjoined, and here is why", because
an inspector that silently picks one would be reporting a guess as a reading.

**Read-only, always.** Every connection is opened as ``file:…?mode=ro`` over a
URI, so this module cannot create, migrate, or WAL-checkpoint an operator's
durable set; and every store's ``PRAGMA user_version`` is pinned against the
constant the writing store declares, so a schema the reader does not understand
refuses instead of being parsed optimistically.

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib only. No ``shared.*``, no
clock, no RNG, no ``subprocess``, no network. Intra-package imports are
RELATIVE (see :mod:`cp3._base`).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos_runtime.engine.inbox import INBOX_SCHEMA_VERSION
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION
from tos_runtime.marketfeed.store import MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION
from tos_runtime.operations.backup_set import EVIDENCE_FILE_NAME, INBOX_FILE_NAME

from ._base import Cp3RunnerRefusal

__all__ = [
    "DECISION_TICK_KIND",
    "EVIDENCE_KINDS_OF_INTEREST",
    "BarEvidence",
    "read_bar_evidence",
]

#: The inbox event kind a market bar arrives as
#: (``tos_runtime.engine.inbox``'s own stored ``kind`` for a decision tick; the
#: value is also what the live stores hold — measured on the 2026-11-10 stock
#: session's ``inbox.sqlite3``).
DECISION_TICK_KIND = "DECISION_TICK"

#: The evidence record kinds this module reads back per tick. Everything else in
#: the window (``TIME_HEALTH_SNAPSHOT`` dominates it by two orders of magnitude)
#: is filtered in SQL rather than in Python, so a full trading day's window is
#: one bounded query.
EVIDENCE_KINDS_OF_INTEREST: tuple[str, ...] = (
    "DECISION_OUTCOME_EMITTED",
    "DECISION_WITHHELD",
    "FLOW_HALTED",
    "EVENT_CONSUMED",
)

#: ``(file name, declared schema version)`` per store this module opens. The
#: version is the writing store's own constant, never a literal here.
_STORE_VERSIONS: tuple[tuple[str, int], ...] = (
    (MARKETFEED_FILE_NAME, MARKETFEED_SCHEMA_VERSION),
    (INBOX_FILE_NAME, INBOX_SCHEMA_VERSION),
    (EVIDENCE_FILE_NAME, EVIDENCE_SCHEMA_VERSION),
)


@dataclass(frozen=True)
class BarEvidence:
    """What the engine recorded for one bar, or why that could not be read.

    Attributes:
        raw_event_id: The journal bar this record is about.
        snapshot_id: The Critical Input Snapshot built from that bar, when the
            marketfeed store holds exactly one.
        event_id: The inbox event the driver admitted for that snapshot.
        outcome_type: ``DECISION_OUTCOME_EMITTED``'s ``outcome_type`` (e.g.
            ``NoActionOutcome``), or ``None`` when no outcome was emitted.
        outcome_halt_reason: That record's own ``halt_reason``.
        consumed_halt_reason: The ``EVENT_CONSUMED`` receipt's ``halt_reason`` —
            the driver's last word on the tick.
        consumed_halt_step: That receipt's ``flow_fingerprint.halt_step``.
        withheld_reason: ``DECISION_WITHHELD``'s ``halt_reason``, when the
            pipeline never reached a signature.
        halt_step: The first ``FLOW_HALTED``'s ``step``.
        halt_reason: That record's ``halt_reason``.
        halt_detail: That record's ``detail`` sentence.
        unjoined_reason: ``None`` when the three-row chain held; otherwise the
            broken or ambiguous link, named.
    """

    raw_event_id: str
    snapshot_id: str | None = None
    event_id: str | None = None
    outcome_type: str | None = None
    outcome_halt_reason: str | None = None
    consumed_halt_reason: str | None = None
    consumed_halt_step: str | None = None
    withheld_reason: str | None = None
    halt_step: str | None = None
    halt_reason: str | None = None
    halt_detail: str | None = None
    unjoined_reason: str | None = None

    @property
    def joined(self) -> bool:
        """Whether the bar reached its evidence window."""
        return self.unjoined_reason is None


@dataclass(frozen=True)
class _Tick:
    """One inbox ``DECISION_TICK`` row, reduced to what the join needs."""

    event_id: str
    handling_started_seq: int
    consumed_seq: int


@contextmanager
def _read_only(path: Path) -> Iterator[sqlite3.Connection]:
    """Open ``path`` read-only and yield the connection.

    Raises:
        Cp3RunnerRefusal: The file is absent or sqlite refuses to open it.
    """
    if not path.is_file():
        raise Cp3RunnerRefusal(f"{path}: durable store does not exist")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise Cp3RunnerRefusal(f"{path}: cannot open read-only: {exc}") from exc
    with closing(connection):
        yield connection


def _pin_schema_version(
    connection: sqlite3.Connection, *, path: Path, expected: int
) -> None:
    """Refuse a store whose ``PRAGMA user_version`` is not ``expected``.

    Raises:
        Cp3RunnerRefusal: The stored version differs from the writing store's
            own declared constant — the columns this module reads may have
            moved, and reading them anyway would publish a value whose meaning
            is unknown.
    """
    found = connection.execute("PRAGMA user_version").fetchone()[0]
    if found != expected:
        raise Cp3RunnerRefusal(
            f"{path}: PRAGMA user_version is {found}, not {expected} — this "
            "reader is pinned to the schema version the writing store declares "
            "(tos_runtime's own constant), so a different version refuses "
            "rather than being parsed optimistically"
        )


def _snapshot_ids_by_bar(
    connection: sqlite3.Connection, raw_event_ids: Sequence[str]
) -> dict[str, list[str]]:
    """``raw_event_id -> snapshot ids`` from ``preimages``, for the asked bars."""
    wanted = set(raw_event_ids)
    found: dict[str, list[str]] = {}
    for snapshot_id, raw_event_id in connection.execute(
        "SELECT snapshot_id, raw_event_id FROM preimages"
    ):
        if raw_event_id in wanted:
            found.setdefault(raw_event_id, []).append(snapshot_id)
    return found


def _bound_snapshot_id(payload_json: str) -> str | None:
    """The snapshot id a stored inbox payload's capsule binds, or ``None``."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    cursor: Any = payload
    for key in ("decision_tick", "capsule", "critical_input_snapshot", "snapshot_id"):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor if isinstance(cursor, str) else None


def _ticks_by_snapshot(connection: sqlite3.Connection) -> dict[str, list[_Tick]]:
    """``snapshot_id -> ticks`` from the inbox's ``DECISION_TICK`` rows.

    A row whose two evidence stamps are not both present is skipped: a tick the
    driver admitted but never finished handling has no window to read, and
    treating its absent stamp as a bound would read another tick's records.
    """
    ticks: dict[str, list[_Tick]] = {}
    for event_id, payload_json, started, consumed in connection.execute(
        "SELECT event_id, payload_json, handling_started_evidence_seq, "
        "consumed_evidence_seq FROM events WHERE kind = ?",
        (DECISION_TICK_KIND,),
    ):
        snapshot_id = _bound_snapshot_id(payload_json)
        if snapshot_id is None or started is None or consumed is None:
            continue
        ticks.setdefault(snapshot_id, []).append(
            _Tick(
                event_id=event_id,
                handling_started_seq=int(started),
                consumed_seq=int(consumed),
            )
        )
    return ticks


def _records_in_window(
    connection: sqlite3.Connection, *, low: int, high: int
) -> list[tuple[int, str, Mapping[str, Any]]]:
    """``(seq, kind, payload)`` for the kinds of interest within ``[low, high]``.

    One bounded query for the whole asked range; the per-tick windows are cut
    out of the result in Python, which keeps a trading day at a single scan
    instead of one query per bar.
    """
    placeholders = ",".join("?" * len(EVIDENCE_KINDS_OF_INTEREST))
    rows = connection.execute(
        f"SELECT seq, kind, payload_json FROM entries "  # noqa: S608 - fixed kinds
        f"WHERE seq >= ? AND seq <= ? AND kind IN ({placeholders}) ORDER BY seq",
        (low, high, *EVIDENCE_KINDS_OF_INTEREST),
    ).fetchall()
    out: list[tuple[int, str, Mapping[str, Any]]] = []
    for seq, kind, payload_json in rows:
        try:
            envelope = json.loads(payload_json)
        except json.JSONDecodeError:
            envelope = {}
        payload = envelope.get("payload") if isinstance(envelope, dict) else None
        out.append((int(seq), kind, payload if isinstance(payload, dict) else {}))
    return out


def _flow_fingerprint_step(payload: Mapping[str, Any]) -> str | None:
    """``flow_fingerprint.halt_step`` out of an ``EVENT_CONSUMED`` payload."""
    fingerprint = payload.get("flow_fingerprint")
    if not isinstance(fingerprint, dict):
        return None
    step = fingerprint.get("halt_step")
    return step if isinstance(step, str) else None


def _text(payload: Mapping[str, Any], key: str) -> str | None:
    """A string field of a stored payload, or ``None`` when absent/not a string."""
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _evidence_from_window(
    raw_event_id: str,
    tick: _Tick,
    records: Iterable[tuple[int, str, Mapping[str, Any]]],
) -> BarEvidence:
    """Fold one tick's evidence records into a :class:`BarEvidence`."""
    outcome_type: str | None = None
    outcome_halt: str | None = None
    consumed_halt: str | None = None
    consumed_step: str | None = None
    withheld: str | None = None
    halt_step: str | None = None
    halt_reason: str | None = None
    halt_detail: str | None = None
    for _seq, kind, payload in records:
        if kind == "DECISION_OUTCOME_EMITTED" and outcome_type is None:
            outcome_type = _text(payload, "outcome_type")
            outcome_halt = _text(payload, "halt_reason")
        elif kind == "DECISION_WITHHELD" and withheld is None:
            withheld = _text(payload, "halt_reason")
        elif kind == "FLOW_HALTED" and halt_step is None:
            halt_step = _text(payload, "step")
            halt_reason = _text(payload, "halt_reason")
            halt_detail = _text(payload, "detail")
        elif kind == "EVENT_CONSUMED":
            consumed_halt = _text(payload, "halt_reason")
            consumed_step = _flow_fingerprint_step(payload)
    return BarEvidence(
        raw_event_id=raw_event_id,
        event_id=tick.event_id,
        outcome_type=outcome_type,
        outcome_halt_reason=outcome_halt,
        consumed_halt_reason=consumed_halt,
        consumed_halt_step=consumed_step,
        withheld_reason=withheld,
        halt_step=halt_step,
        halt_reason=halt_reason,
        halt_detail=halt_detail,
    )


def _resolved_tick(
    raw_event_id: str,
    snapshot_ids: Sequence[str],
    ticks_by_snapshot: Mapping[str, Sequence[_Tick]],
) -> tuple[str, _Tick] | BarEvidence:
    """The one ``(snapshot_id, tick)`` behind a bar, or an unjoined record saying why."""
    if not snapshot_ids:
        return BarEvidence(
            raw_event_id=raw_event_id,
            unjoined_reason="no preimage row names this raw_event_id",
        )
    if len(snapshot_ids) > 1:
        return BarEvidence(
            raw_event_id=raw_event_id,
            unjoined_reason=(
                f"{len(snapshot_ids)} snapshots name this raw_event_id — which "
                "one the engine decided on is ambiguous"
            ),
        )
    snapshot_id = snapshot_ids[0]
    ticks = ticks_by_snapshot.get(snapshot_id, ())
    if not ticks:
        return BarEvidence(
            raw_event_id=raw_event_id,
            snapshot_id=snapshot_id,
            unjoined_reason=(
                "no inbox DECISION_TICK with both evidence stamps bound "
                f"snapshot {snapshot_id}"
            ),
        )
    if len(ticks) > 1:
        return BarEvidence(
            raw_event_id=raw_event_id,
            snapshot_id=snapshot_id,
            unjoined_reason=(
                f"{len(ticks)} inbox ticks bound snapshot {snapshot_id} — which "
                "tick's records belong to this bar is ambiguous"
            ),
        )
    return snapshot_id, ticks[0]


def read_bar_evidence(
    data_dir: Path, raw_event_ids: Sequence[str]
) -> dict[str, BarEvidence]:
    """Join each bar in ``raw_event_ids`` to the records the engine wrote for it.

    Args:
        data_dir: The tenant's durable-set leaf — the directory holding
            ``marketfeed.sqlite3``, ``inbox.sqlite3`` and ``evidence.sqlite3``.
        raw_event_ids: The journal bars to join, in any order.

    Returns:
        One :class:`BarEvidence` per asked ``raw_event_id``. A bar whose chain
        broke carries ``unjoined_reason`` and nothing else.

    Raises:
        Cp3RunnerRefusal: A store is missing, cannot be opened read-only, or
            carries a ``PRAGMA user_version`` this reader is not pinned to.
    """
    if not raw_event_ids:
        return {}
    with _read_only(data_dir / MARKETFEED_FILE_NAME) as marketfeed:
        _pin_schema_version(
            marketfeed,
            path=data_dir / MARKETFEED_FILE_NAME,
            expected=MARKETFEED_SCHEMA_VERSION,
        )
        snapshots = _snapshot_ids_by_bar(marketfeed, raw_event_ids)
    with _read_only(data_dir / INBOX_FILE_NAME) as inbox:
        _pin_schema_version(
            inbox, path=data_dir / INBOX_FILE_NAME, expected=INBOX_SCHEMA_VERSION
        )
        ticks_by_snapshot = _ticks_by_snapshot(inbox)

    resolved: dict[str, _Tick] = {}
    out: dict[str, BarEvidence] = {}
    for raw_event_id in raw_event_ids:
        outcome = _resolved_tick(
            raw_event_id, snapshots.get(raw_event_id, []), ticks_by_snapshot
        )
        if isinstance(outcome, BarEvidence):
            out[raw_event_id] = outcome
        else:
            resolved[raw_event_id] = outcome[1]
    if not resolved:
        return out

    low = min(tick.handling_started_seq for tick in resolved.values())
    high = max(tick.consumed_seq for tick in resolved.values())
    with _read_only(data_dir / EVIDENCE_FILE_NAME) as evidence:
        _pin_schema_version(
            evidence,
            path=data_dir / EVIDENCE_FILE_NAME,
            expected=EVIDENCE_SCHEMA_VERSION,
        )
        records = _records_in_window(evidence, low=low, high=high)
    for raw_event_id, tick in resolved.items():
        window = [
            record
            for record in records
            if tick.handling_started_seq < record[0] <= tick.consumed_seq
        ]
        out[raw_event_id] = _evidence_from_window(raw_event_id, tick, window)
    return out


def assert_store_versions(data_dir: Path) -> None:
    """Pin all three stores' schema versions without reading any rows.

    Raises:
        Cp3RunnerRefusal: Any store is missing or carries an unpinned version.
    """
    for file_name, expected in _STORE_VERSIONS:
        with _read_only(data_dir / file_name) as connection:
            _pin_schema_version(
                connection, path=data_dir / file_name, expected=expected
            )
