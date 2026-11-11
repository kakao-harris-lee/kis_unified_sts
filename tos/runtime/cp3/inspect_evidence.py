"""Read-only evidence join — one recorded session bar → what the runtime did with it.

Part of the CP-3 ``cp3`` package (roadmap
``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1: «왜 이 바에서 이 결정이었나»).
Its one job is the KEY join from a journal bar's ``raw_event_id`` to the
decision records the engine wrote for that bar — **and to the value set the
engine actually evaluated on it** — so :mod:`cp3.inspect_session` re-evaluates
the policy on the engine's own inputs rather than on a look-alike.

**Why this lives inside ``tos/`` and not beside the journal reader in
``tools/``.** The import firewall is bidirectional
(``tools/tos_firewall_check.py`` TOS-FW-R): nothing outside ``tos/`` may import
``tos``/``tos_runtime``, so a legacy-side joiner must MIRROR the store
literals it reads — which is what
:mod:`tools.tos_cp3.session_inputs` does, pinned against a committed hinge.
This module is the other side of that trade: it is in RUNTIME scope, so it
imports the real file-name and schema-version constants from the stores
themselves, and parses the stored value view through the kernel's own
:class:`~tos.dsl.ContextValueView` — no literal and no projection can drift.

**The join (three durable rows).** Identical in shape to
:mod:`tools.tos_cp3.session_inputs`'s own documented chain, read here from the
source constants instead of mirrored ones:

1. ``marketfeed.sqlite3``'s ``preimages(snapshot_id, raw_event_id)`` — the bar's
   ``raw_event_id`` names the Critical Input Snapshot the issuer built from it;
2. ``inbox.sqlite3``'s ``events`` — the ``DECISION_TICK`` whose
   ``decision_tick.capsule.critical_input_snapshot.snapshot_id`` is that
   snapshot, carrying the ``event_id``, the two evidence ``seq`` stamps the
   driver writes around the handler
   (``tos_runtime.engine.driver.EngineDriver._process_next``), **and** that
   tick's ``decision_tick.value_view`` — the published
   :class:`~tos.dsl.ContextValueView` the engine evaluated;
3. ``evidence.sqlite3``'s ``entries`` — every record in that tick's
   ``(handling_started_evidence_seq, consumed_evidence_seq]`` window.

**The value view is the point of the join, not a bonus.** A production
evaluation reads ``env["capsule"]["resolved_values"]`` built from the view
``tos.engine.pipeline`` passed it, NOT from the producer's journal line. The
two normally agree (measured 2026-11-10: 351 of 352 bars identical), and where
they do not, the journal is the wrong answer — so this module hands the view
up and :mod:`cp3.inspect_session` evaluates on it. An **explicit-empty** view
(``values == ()``) is a defined outcome, materially different from no view at
all (``tos.dsl.context_value.ContextValueView`` class docstring: "design #32 §6
∅ 양방향"), and that difference is carried, not flattened: an empty view is the
shape a withheld tick has, and a bar whose policy was never meaningfully
evaluated must not land in a per-comparison denominator.

**Nothing is guessed.** A bar whose chain breaks at any link gets an
:class:`BarEvidence` whose ``unjoined_reason`` names the broken link, never a
positional pairing: pairing by position is the inference the stores can
contradict silently (session_inputs' own module docstring, Claude lane MEDIUM
R1 2026-10-14). An ambiguous link — one ``raw_event_id`` behind two snapshots,
one snapshot bound by two ticks — is also "unjoined, and here is why", because
an inspector that silently picks one would be reporting a guess as a reading.
A tick the driver admitted but never finished handling says exactly that,
rather than looking like a tick that was never admitted.

**Read-only, always.** Every connection is opened as a ``file:…?mode=ro`` URI
derived from :meth:`~pathlib.Path.as_uri` (so a path holding ``?`` or ``#`` is
percent-encoded rather than silently truncating the query string), so this
module cannot create, migrate, or WAL-checkpoint an operator's durable set;
every store's ``PRAGMA user_version`` is pinned against the constant the
writing store declares; and every statement runs through :func:`_query`, so a
sqlite failure mid-read is a named refusal rather than a raw driver traceback.

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

from pydantic import ValidationError
from tos.canonical import ArtifactIntegrityError
from tos.dsl import ContextValueView, ScalarValue
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


@dataclass(frozen=True)
class BarEvidence:
    """What the engine recorded for one bar, or why that could not be read.

    Attributes:
        raw_event_id: The journal bar this record is about.
        snapshot_id: The Critical Input Snapshot built from that bar.
        event_id: The inbox event the driver admitted for that snapshot.
        value_view: The engine's own ``{field_key: scalar}`` evaluation inputs,
            projected by :meth:`~tos.dsl.ContextValueView.as_environment_mapping`.
            An empty mapping is an **explicit-empty view** — "the binding
            resolved and nothing was admissible" — and is a real answer.
            ``None`` means the tick payload carried no ``value_view`` at all, or
            carried one this reader refused (see ``value_view_refusal``).
        value_view_refusal: Why a present ``value_view`` could not be read as a
            :class:`~tos.dsl.ContextValueView`, or ``None``.
        outcome_type: ``DECISION_OUTCOME_EMITTED``'s ``outcome_type`` (e.g.
            ``NoActionOutcome``, ``Proposal``), or ``None`` when none was emitted.
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
    value_view: Mapping[str, ScalarValue] | None = None
    value_view_refusal: str | None = None
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

    @property
    def view_is_explicitly_empty(self) -> bool:
        """Whether the engine published a view that admitted no value at all.

        That is the usual shape a withheld tick has: every DSL operand resolves
        to ``UNKNOWN``, so no rule can fire for a reason that has nothing to do
        with the authored thresholds. It is not the ONLY such shape — see
        :attr:`withheld`.
        """
        return self.value_view is not None and not self.value_view

    @property
    def withheld(self) -> bool:
        """Whether the engine declined to decide on this bar at all.

        Two shapes, and either one is enough (LOW-B, round-2 review of #1058):

        * an **explicit-empty** value view (:attr:`view_is_explicitly_empty`);
        * a recorded ``DECISION_WITHHELD`` (:attr:`withheld_reason`), which says
          the pipeline never reached an input signature.

        The second is the one the empty-view test alone misses. A tick can
        publish a view carrying values and STILL be withheld — freshness
        refused, a coordinator precondition refused — and re-evaluating the
        policy on those values would produce a decision the engine never made.
        That is precisely the phantom the ``V``/``D`` markers exist to prevent,
        so such a bar is not evaluated and not counted either.
        """
        return self.view_is_explicitly_empty or self.withheld_reason is not None


@dataclass(frozen=True)
class _Tick:
    """One inbox ``DECISION_TICK`` row, reduced to what the join needs.

    The two evidence stamps are optional because a tick the driver admitted but
    never finished handling really exists in the store, and saying so is a
    different fact from "no tick bound this snapshot" (LOW-3, review of #1057).
    """

    event_id: str
    handling_started_seq: int | None
    consumed_seq: int | None
    value_view_raw: Any

    @property
    def complete(self) -> bool:
        """Whether both driver stamps are present, so the tick has a window."""
        return self.handling_started_seq is not None and self.consumed_seq is not None


@contextmanager
def _read_only(path: Path) -> Iterator[sqlite3.Connection]:
    """Open ``path`` read-only and yield the connection.

    The URI comes from :meth:`~pathlib.Path.as_uri`, so a path containing ``?``
    or ``#`` is percent-encoded instead of being read by sqlite as the start of
    the query string — an f-string would silently open a DIFFERENT file, or open
    this one read-WRITE because the ``mode=ro`` landed inside a filename.

    Raises:
        Cp3RunnerRefusal: The file is absent or sqlite refuses to open it.
    """
    if not path.is_file():
        raise Cp3RunnerRefusal(f"{path}: durable store does not exist")
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise Cp3RunnerRefusal(f"{path}: cannot open read-only: {exc}") from exc
    with closing(connection):
        yield connection


def _query(
    connection: sqlite3.Connection,
    *,
    path: Path,
    sql: str,
    params: Sequence[Any] = (),
) -> list[Any]:
    """Run one read and return its rows, or refuse naming the store.

    Every statement in this module goes through here: an I/O error, a locked
    database or a missing table partway through a read is an operator-visible
    fact about THAT store, not a raw driver traceback from somewhere in a loop.

    Raises:
        Cp3RunnerRefusal: sqlite failed the statement.
    """
    try:
        return connection.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error as exc:
        raise Cp3RunnerRefusal(f"{path}: read failed ({exc}): {sql}") from exc


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
    rows = _query(connection, path=path, sql="PRAGMA user_version")
    found = rows[0][0] if rows else None
    if found != expected:
        raise Cp3RunnerRefusal(
            f"{path}: PRAGMA user_version is {found}, not {expected} — this "
            "reader is pinned to the schema version the writing store declares "
            "(tos_runtime's own constant), so a different version refuses "
            "rather than being parsed optimistically"
        )


def _snapshot_ids_by_bar(
    connection: sqlite3.Connection, *, path: Path, raw_event_ids: Sequence[str]
) -> dict[str, list[str]]:
    """``raw_event_id -> snapshot ids`` from ``preimages``, for the asked bars."""
    wanted = set(raw_event_ids)
    found: dict[str, list[str]] = {}
    for snapshot_id, raw_event_id in _query(
        connection, path=path, sql="SELECT snapshot_id, raw_event_id FROM preimages"
    ):
        if raw_event_id in wanted:
            found.setdefault(raw_event_id, []).append(snapshot_id)
    return found


def _decision_tick(payload_json: str) -> Mapping[str, Any] | None:
    """The stored tick payload's ``decision_tick`` mapping, or ``None``."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    tick = payload.get("decision_tick")
    return tick if isinstance(tick, dict) else None


def _bound_snapshot_id(tick: Mapping[str, Any]) -> str | None:
    """The snapshot id a tick's capsule binds, or ``None``."""
    cursor: Any = tick
    for key in ("capsule", "critical_input_snapshot", "snapshot_id"):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor if isinstance(cursor, str) else None


def _ticks_by_snapshot(
    connection: sqlite3.Connection, *, path: Path
) -> dict[str, list[_Tick]]:
    """``snapshot_id -> ticks`` from the inbox's ``DECISION_TICK`` rows.

    A row whose stamps are half-present is KEPT (with ``None`` stamps) so the
    bar can be told "the tick exists but handling never completed" rather than
    "no tick bound this snapshot" — the two are different operational facts and
    the first one is actionable (LOW-3, review of #1057).
    """
    ticks: dict[str, list[_Tick]] = {}
    for event_id, payload_json, started, consumed in _query(
        connection,
        path=path,
        sql=(
            "SELECT event_id, payload_json, handling_started_evidence_seq, "
            "consumed_evidence_seq FROM events WHERE kind = ?"
        ),
        params=(DECISION_TICK_KIND,),
    ):
        tick = _decision_tick(payload_json)
        if tick is None:
            continue
        snapshot_id = _bound_snapshot_id(tick)
        if snapshot_id is None:
            continue
        ticks.setdefault(snapshot_id, []).append(
            _Tick(
                event_id=event_id,
                handling_started_seq=None if started is None else int(started),
                consumed_seq=None if consumed is None else int(consumed),
                value_view_raw=tick.get("value_view"),
            )
        )
    return ticks


def _projected_view(
    raw: Any,
) -> tuple[Mapping[str, ScalarValue] | None, str | None]:
    """``(the engine's {field_key: scalar}, refusal)`` from a stored value view.

    The projection is the kernel's own
    :meth:`~tos.dsl.ContextValueView.as_environment_mapping` over a model
    validated by the kernel's own :class:`~tos.dsl.ContextValueView`, so neither
    the field-key shape nor the duplicate-key rule is restated here. A view the
    model refuses yields ``(None, reason)`` rather than a partial mapping: half
    of an evaluation's inputs is not a smaller evaluation, it is a wrong one.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, f"value_view is {type(raw).__name__}, not a JSON object"
    try:
        view = ContextValueView.model_validate(raw)
    except (ValidationError, ArtifactIntegrityError) as exc:
        return None, f"value_view is not a readable ContextValueView: {exc}"
    return view.as_environment_mapping(), None


def _records_in_window(
    connection: sqlite3.Connection, *, path: Path, low: int, high: int
) -> list[tuple[int, str, Mapping[str, Any]]]:
    """``(seq, kind, payload)`` for the kinds of interest within ``[low, high]``.

    One bounded query for the whole asked range; the per-tick windows are cut
    out of the result in Python, which keeps a trading day at a single scan
    instead of one query per bar.
    """
    placeholders = ",".join("?" * len(EVIDENCE_KINDS_OF_INTEREST))
    rows = _query(
        connection,
        path=path,
        sql=(
            "SELECT seq, kind, payload_json FROM entries "  # noqa: S608 - fixed kinds
            f"WHERE seq >= ? AND seq <= ? AND kind IN ({placeholders}) ORDER BY seq"
        ),
        params=(low, high, *EVIDENCE_KINDS_OF_INTEREST),
    )
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


@dataclass(frozen=True)
class _WindowFacts:
    """The decision records one tick's evidence window carries."""

    outcome_type: str | None = None
    outcome_halt_reason: str | None = None
    consumed_halt_reason: str | None = None
    consumed_halt_step: str | None = None
    withheld_reason: str | None = None
    halt_step: str | None = None
    halt_reason: str | None = None
    halt_detail: str | None = None


def _window_facts(
    records: Iterable[tuple[int, str, Mapping[str, Any]]],
) -> _WindowFacts:
    """Fold one tick's evidence records into :class:`_WindowFacts`."""
    facts: dict[str, str | None] = {}
    for _seq, kind, payload in records:
        if kind == "DECISION_OUTCOME_EMITTED" and "outcome_type" not in facts:
            facts["outcome_type"] = _text(payload, "outcome_type")
            facts["outcome_halt_reason"] = _text(payload, "halt_reason")
        elif kind == "DECISION_WITHHELD" and "withheld_reason" not in facts:
            facts["withheld_reason"] = _text(payload, "halt_reason")
        elif kind == "FLOW_HALTED" and "halt_step" not in facts:
            facts["halt_step"] = _text(payload, "step")
            facts["halt_reason"] = _text(payload, "halt_reason")
            facts["halt_detail"] = _text(payload, "detail")
        elif kind == "EVENT_CONSUMED":
            facts["consumed_halt_reason"] = _text(payload, "halt_reason")
            facts["consumed_halt_step"] = _flow_fingerprint_step(payload)
    return _WindowFacts(**facts)


def _unjoined(
    raw_event_id: str, reason: str, snapshot_id: str | None = None
) -> BarEvidence:
    """One bar's record saying which link of the chain broke."""
    return BarEvidence(
        raw_event_id=raw_event_id, snapshot_id=snapshot_id, unjoined_reason=reason
    )


def _resolved_tick(
    raw_event_id: str,
    snapshot_ids: Sequence[str],
    ticks_by_snapshot: Mapping[str, Sequence[_Tick]],
) -> tuple[str, _Tick] | BarEvidence:
    """The one ``(snapshot_id, tick)`` behind a bar, or an unjoined record saying why."""
    if not snapshot_ids:
        return _unjoined(raw_event_id, "no preimage row names this raw_event_id")
    if len(snapshot_ids) > 1:
        return _unjoined(
            raw_event_id,
            f"{len(snapshot_ids)} snapshots name this raw_event_id — which one "
            "the engine decided on is ambiguous",
        )
    snapshot_id = snapshot_ids[0]
    ticks = ticks_by_snapshot.get(snapshot_id, ())
    if not ticks:
        return _unjoined(
            raw_event_id,
            f"no inbox DECISION_TICK bound snapshot {snapshot_id}",
            snapshot_id,
        )
    if len(ticks) > 1:
        return _unjoined(
            raw_event_id,
            f"{len(ticks)} inbox ticks bound snapshot {snapshot_id} — which "
            "tick's records belong to this bar is ambiguous",
            snapshot_id,
        )
    tick = ticks[0]
    if not tick.complete:
        return _unjoined(
            raw_event_id,
            f"tick {tick.event_id} exists but handling never completed "
            f"(handling_started_evidence_seq={tick.handling_started_seq}, "
            f"consumed_evidence_seq={tick.consumed_seq})",
            snapshot_id,
        )
    return snapshot_id, tick


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
        Cp3RunnerRefusal: A store is missing, cannot be opened read-only,
            carries a ``PRAGMA user_version`` this reader is not pinned to, or
            fails a read partway through.
    """
    if not raw_event_ids:
        return {}
    marketfeed_path = data_dir / MARKETFEED_FILE_NAME
    with _read_only(marketfeed_path) as marketfeed:
        _pin_schema_version(
            marketfeed, path=marketfeed_path, expected=MARKETFEED_SCHEMA_VERSION
        )
        snapshots = _snapshot_ids_by_bar(
            marketfeed, path=marketfeed_path, raw_event_ids=raw_event_ids
        )
    inbox_path = data_dir / INBOX_FILE_NAME
    with _read_only(inbox_path) as inbox:
        _pin_schema_version(inbox, path=inbox_path, expected=INBOX_SCHEMA_VERSION)
        ticks_by_snapshot = _ticks_by_snapshot(inbox, path=inbox_path)

    resolved: dict[str, tuple[str, _Tick]] = {}
    out: dict[str, BarEvidence] = {}
    for raw_event_id in raw_event_ids:
        outcome = _resolved_tick(
            raw_event_id, snapshots.get(raw_event_id, []), ticks_by_snapshot
        )
        if isinstance(outcome, BarEvidence):
            out[raw_event_id] = outcome
        else:
            resolved[raw_event_id] = outcome
    if not resolved:
        return out

    # Both stamps are present on every resolved tick (`_Tick.complete`), so the
    # bounds below cannot be None — `_resolved_tick` refused the half-stamped
    # case above rather than letting it reach this arithmetic.
    low = min(tick.handling_started_seq or 0 for _snapshot, tick in resolved.values())
    high = max(tick.consumed_seq or 0 for _snapshot, tick in resolved.values())
    evidence_path = data_dir / EVIDENCE_FILE_NAME
    with _read_only(evidence_path) as evidence:
        _pin_schema_version(
            evidence, path=evidence_path, expected=EVIDENCE_SCHEMA_VERSION
        )
        records = _records_in_window(evidence, path=evidence_path, low=low, high=high)
    for raw_event_id, (snapshot_id, tick) in resolved.items():
        window = [
            record
            for record in records
            if (tick.handling_started_seq or 0) < record[0] <= (tick.consumed_seq or 0)
        ]
        view, view_refusal = _projected_view(tick.value_view_raw)
        out[raw_event_id] = BarEvidence(
            raw_event_id=raw_event_id,
            snapshot_id=snapshot_id,
            event_id=tick.event_id,
            value_view=view,
            value_view_refusal=view_refusal,
            **vars(_window_facts(window)),
        )
    return out
