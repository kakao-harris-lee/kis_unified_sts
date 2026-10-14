#!/usr/bin/env python3
"""CP-3 §3.6 — the two session-derived inputs B3 did not have.

Plan ``docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md`` §3.6, PR-3
row. Before this module B3 (:mod:`tools.tos_cp3.diff_decisions`) read three
offline artifacts — B1a's fields, B2's legacy outcomes, B1b's offline trace —
and therefore answered only "did the offline replay agree with the legacy
rule". It could not see the live session at all: not which bars the runtime
actually consumed, and not what the runtime decided on them. This module reads
the session's own durable stores and produces those two inputs:

``consumed-ids``
    The ``raw_event_id`` set the runtime really consumed, from the session
    ``marketfeed.sqlite3``'s ``preimages(snapshot_id, raw_event_id)`` table —
    one row per observation each issued snapshot covers. Given the producer's
    own log (and the runner's boot snapshot), it also says, for every bar the
    offline stream has and the runtime did NOT consume, WHY: the plan's
    pre-boot / ``skipped_behind`` / ``produce_error`` / ``omitted_unusable``
    reasons, each from the producer's own label rather than from a guess here.

``live-decisions``
    One record per live decision, shaped like B1b's offline trace line, from
    the session ``evidence.sqlite3``'s ``entries`` table.

**Read-only, and no ``tos`` import.** The firewall is bidirectional —
``tools/`` is in its reverse scan (``tools/tos_firewall_check.py`` TOS-FW-R) —
so both stores are opened as plain sqlite files in ``mode=ro``, and the four
runtime literals this needs (two file names, two schema versions) are MIRRORED
here with the constant each mirrors named beside it. A mirrored literal that
drifts is caught rather than assumed: every read pins ``PRAGMA user_version``
against the mirrored version and refuses a store the extractor was not written
for, instead of reading a changed shape as if it were the old one.

**How a live decision is tied to a bar, and what that costs.** The engine's
durable evidence record (``tos.engine.records.EngineEvidenceRecord``) carries
``capsule_id``/``capsule_digest`` — never the ``raw_event_id`` and never the
snapshot id. The capsule binds its snapshot by content digest, and recomputing
that digest here would need the kernel, which this side may not import. So the
pairing is ORDERED, not keyed: the scheduler issues exactly one snapshot per
TICKed pass and hands exactly one ``DECISION_TICK`` event to the engine before
the next pass (``tos_runtime.marketfeed.scheduler.MarketFeedScheduler.
tick_once``), so the k-th decision record belongs to the k-th snapshot. That is
an inference, and it is guarded rather than trusted: the counts must be equal,
every snapshot must name the same instrument, and every snapshot must carry
exactly one preimage row. Any of those failing is a refusal naming both counts
— this module never pairs a decision with a bar it cannot account for.

Usage::

    .venv/bin/python tools/tos_cp3/session_inputs.py consumed-ids \\
        --data-dir   /path/session/data/A05611 \\
        --producer-log /path/session/producer-log.jsonl \\
        --boot-snapshot /path/session/boot-journal-snapshot.json \\
        --out        /path/session/b3-inputs/consumed-ids.json

    .venv/bin/python tools/tos_cp3/session_inputs.py live-decisions \\
        --data-dir /path/session/data/A05611 \\
        --out      /path/session/b3-inputs/live

``live-decisions`` writes a directory holding ``live.jsonl`` and the
``lineage.json`` sidecar B3 auto-discovers beside an artifact, the same layout
B1a, B2 and B1b use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Repo root of the checkout this file belongs to, at the FRONT of
#: ``sys.path`` for the same reason B1a/B2/B3 do it: an editable install of
#: another checkout must not shadow this worktree's ``tools/``.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402

#: Stable identity stamped on every document this module writes.
SOURCE_ID = f"tos-cp3-session-inputs/{TOS_CP3_VERSION}"

#: Document schema version — bumped when a produced document changes shape, so
#: a consumer reads "shaped differently" rather than "values differ".
SCHEMA_VERSION = 1

#: Mirrors ``tos_runtime.marketfeed.store.MARKETFEED_FILE_NAME`` and
#: ``tos_runtime.operations.backup_set.EVIDENCE_FILE_NAME``. Mirrored, not
#: imported: the firewall forbids importing either from here.
MARKETFEED_FILE_NAME = "marketfeed.sqlite3"
EVIDENCE_FILE_NAME = "evidence.sqlite3"

#: Mirrors ``tos_runtime.marketfeed.store.MARKETFEED_SCHEMA_VERSION`` and
#: ``tos_runtime.evidence.store.EVIDENCE_SCHEMA_VERSION`` — each store stamps
#: its own value into ``PRAGMA user_version``. Pinned rather than read-and-
#: accepted: a bumped version means the tables changed shape, and reading a new
#: shape with these queries would answer a question about a store that no
#: longer exists (the migration note is runbook ``tos-paper-boot.md`` §4-A).
PINNED_MARKETFEED_SCHEMA_VERSION = 1
PINNED_EVIDENCE_SCHEMA_VERSION = 2

#: The engine evidence kinds that TERMINATE one decision pass — exactly one of
#: these is recorded per ``DECISION_TICK`` (``tos.engine.vocabulary
#: .EvidenceKind``; ``pipeline.py`` records ``DECISION_OUTCOME_EMITTED`` or
#: ``DECISION_WITHHELD``, ``core.py`` the withheld pre-dispatch case, and the
#: Coordinator gate its own refusal). They delimit the per-tick blocks.
DECISION_KINDS: tuple[str, ...] = (
    "DECISION_OUTCOME_EMITTED",
    "DECISION_WITHHELD",
    "DECISION_DEGRADED",
    "COORDINATOR_PRECONDITION_REFUSED",
)

#: The commitment-flow kinds that may follow a decision inside the same tick
#: block. Anything else in ``entries`` (boot records, backup observations, key
#: rotations, non-trade dispositions) is not part of a decision and is ignored
#: by name rather than by position.
FLOW_KINDS: tuple[str, ...] = (
    "FLOW_STEP_ADMITTED",
    "FLOW_HALTED",
    "ATTEMPT_REQUEST_CREATED",
    "SEND_HANDED_OFF",
    "EGRESS_RESULT_CONSUMED",
    "RESULT_UNMATCHED",
)

#: ``tos.engine.vocabulary.HaltReason.AT_MOST_ONE_EXPOSURE_HELD`` — the one
#: flow halt B1b calls ``capacity_denied`` (``tos/runtime/cp3/replay.py``'s own
#: ``denied = flow_halt is HaltReason.AT_MOST_ONE_EXPOSURE_HELD``).
CAPACITY_DENIAL_HALT_REASON = "AT_MOST_ONE_EXPOSURE_HELD"

#: ``outcome_type`` (the emitted outcome's class name) -> B1b's ``outcome_kind``
#: token. Only the no-action case is derivable from the durable record: a
#: ``Proposal`` is ACTION or FLAT depending on its ``position_effect``, which
#: the evidence record does not carry (it records ``outcome_type`` and
#: ``outcome_digest`` only). :func:`_live_outcome_kind` refuses rather than
#: guessing, and says what would have to change.
OUTCOME_TYPE_TO_KIND: Mapping[str, str] = {"NoActionOutcome": "NO_ACTION"}

#: A tick that ended without an emitted outcome is not one of B1b's three
#: decision kinds, and B1b itself refuses to call it a fourth
#: (``replay.py::_attribute_rule``'s ``NO_OUTCOME``). The live side records the
#: same token so the two sides disagree visibly rather than silently.
NO_OUTCOME_KIND = "NO_OUTCOME"

#: Producer log stages that DISPOSE of a bar, newest-wins, with ``published``
#: overriding everything: a bar can miss its own boundary
#: (``missing_no_successor``) and complete later (``late_completed``), so the
#: last dispositive stage is the one that describes how the session left it.
PRODUCER_DISPOSITION_STAGES: tuple[str, ...] = (
    "published",
    "skipped_behind",
    "late_completed",
    "missing_no_successor",
    "no_raw_row_for_minute",
    "omitted_unusable",
    "produce_error",
    "clock_regression",
)

#: The reason recorded for a bar the producer DID publish, the runtime did not
#: consume, and the runner's boot snapshot shows was already in the journal
#: when the runtime booted. Plan §5 M5: those lines are structurally
#: unconsumable (the scheduler takes only the newest observation of a poll), so
#: they are excluded from the two M5 counts and recorded under their own name.
REASON_PRE_BOOT = "pre_boot"

#: A line the producer published AFTER boot that the runtime never consumed.
#: This is the M5 defect shape and gets its own name — never folded into a
#: benign reason, which is the whole point of counting by reason.
REASON_UNCONSUMED_AFTER_BOOT = "published_not_consumed"

#: An offline bar with no producer-log disposition at all. Not refused: a B3
#: run whose producer log is missing or truncated still has something to say,
#: and a silent drop is what the reason counts exist to prevent.
REASON_UNEXPLAINED = "unexplained"


class SessionInputsError(RuntimeError):
    """A refusal. Nothing is written when one is raised."""


# ---------------------------------------------------------------------------
# sqlite, read-only
# ---------------------------------------------------------------------------


def _connect_ro(path: Path, *, label: str, pinned_version: int) -> sqlite3.Connection:
    """Open *path* read-only and refuse a store shape this was not written for."""
    if not path.is_file():
        raise SessionInputsError(
            f"{label} store not found: {path}. A session that never ticked "
            "writes no marketfeed store at all (runbook tos-paper-boot.md §4), "
            "which is a different fact from an empty one"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    except sqlite3.Error as exc:  # pragma: no cover - a corrupt file
        conn.close()
        raise SessionInputsError(f"{label} store {path} is unreadable: {exc}") from exc
    if version != pinned_version:
        conn.close()
        raise SessionInputsError(
            f"{label} store {path} declares PRAGMA user_version={version}, this "
            f"extractor is pinned to {pinned_version}. A different version means "
            "the tables changed shape, and these queries would answer a question "
            "about a store that no longer exists"
        )
    return conn


def sha256_file(path: Path) -> str:
    """Streaming sha256 of a file — the stores can be large."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_ref(path: Path | None) -> dict[str, Any] | None:
    """``{path, sha256}`` for a file that was read, or ``None``."""
    if path is None:
        return None
    return {"path": str(path), "sha256": sha256_file(path)}


# ---------------------------------------------------------------------------
# The marketfeed side: snapshots and the ids they covered
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """One issued snapshot and the single observation it covered."""

    snapshot_id: str
    instrument: str
    as_of_ms: int
    raw_event_id: str


def read_snapshots(data_dir: Path) -> tuple[Snapshot, ...]:
    """Every issued snapshot of the session, in issue order, with its id.

    Issue order is ``rowid`` order: ``snapshots`` has a TEXT primary key, so
    sqlite keeps its own rowid and that is insertion order. Ordering by
    ``as_of_ms`` instead would reorder two snapshots that share a stamp, and
    the ordered pairing below depends on this being the order the scheduler
    wrote them in.

    Raises:
        SessionInputsError: A snapshot covers no preimage row, or more than
            one. Both break the pairing: the first is the restore-path failure
            the store's own docstring describes (a snapshot id in hand, every
            value UNKNOWN), the second means a snapshot covered several
            observations and "the bar this decision was about" is not a
            question with one answer.
    """
    conn = _connect_ro(
        data_dir / MARKETFEED_FILE_NAME,
        label="marketfeed",
        pinned_version=PINNED_MARKETFEED_SCHEMA_VERSION,
    )
    try:
        rows = list(
            conn.execute(
                "SELECT snapshot_id, instrument, as_of_ms FROM snapshots ORDER BY rowid"
            )
        )
        preimages: dict[str, list[str]] = {}
        for snapshot_id, raw_event_id in conn.execute(
            "SELECT snapshot_id, raw_event_id FROM preimages"
        ):
            preimages.setdefault(str(snapshot_id), []).append(str(raw_event_id))
    finally:
        conn.close()

    snapshots: list[Snapshot] = []
    for snapshot_id, instrument, as_of_ms in rows:
        covered = preimages.get(str(snapshot_id), [])
        if len(covered) != 1:
            raise SessionInputsError(
                f"snapshot {snapshot_id} covers {len(covered)} preimage row(s), "
                "expected exactly 1. One journal line is one observation and one "
                "snapshot (marketfeed/journal.py's own line shape), so another "
                "count means this session was not produced by ③ or the preimages "
                "were lost — either way the id this decision was about is not "
                "decidable here"
            )
        snapshots.append(
            Snapshot(
                snapshot_id=str(snapshot_id),
                instrument=str(instrument),
                as_of_ms=int(as_of_ms),
                raw_event_id=covered[0],
            )
        )
    return tuple(snapshots)


def _assert_one_instrument(snapshots: Sequence[Snapshot]) -> str:
    instruments = sorted({snapshot.instrument for snapshot in snapshots})
    if len(instruments) != 1:
        raise SessionInputsError(
            f"the session's snapshots name {instruments} — a tenant session is "
            "one instrument (the runner derives the contract month once and "
            "gives render, data dir and producer the same value), so more than "
            "one means two deployments wrote into one durable set"
        )
    return instruments[0]


# ---------------------------------------------------------------------------
# The producer side: why a bar was never consumed
# ---------------------------------------------------------------------------


def _iter_json_lines(path: Path, *, label: str) -> Iterator[dict[str, Any]]:
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SessionInputsError(
                f"{label} line {index} is not JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise SessionInputsError(f"{label} line {index} is not an object")
        yield payload


def producer_dispositions(producer_log: Path) -> dict[str, str]:
    """``raw_event_id -> the stage that disposed of that bar``.

    ``published`` wins over everything; otherwise the LAST dispositive stage
    wins, because a bar can miss its own boundary and complete afterwards. Only
    events carrying a ``raw_event_id`` are read — the producer stamps one on
    every per-bar event with B1a's own deriver, so nothing here reconstructs a
    join key (plan §3.6).
    """
    disposed: dict[str, str] = {}
    for payload in _iter_json_lines(producer_log, label="producer log"):
        stage = payload.get("stage")
        raw_event_id = payload.get("raw_event_id")
        if not isinstance(raw_event_id, str) or stage not in (
            PRODUCER_DISPOSITION_STAGES
        ):
            continue
        if disposed.get(raw_event_id) == "published":
            continue
        disposed[raw_event_id] = str(stage)
    return disposed


def read_boot_snapshot(path: Path) -> frozenset[str]:
    """The ids already in the journal when the runtime booted (runner step 9b).

    Raises:
        SessionInputsError: The file does not carry the runner's own
            ``pre_boot_raw_event_ids`` list. An empty list is a legitimate
            value only if the runner wrote one; a MISSING key is a different
            file, and reading it as "no pre-boot lines" would move every
            pre-boot line into :data:`REASON_UNCONSUMED_AFTER_BOOT` — turning
            the structurally-expected case into the defect shape.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids = payload.get("pre_boot_raw_event_ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
        raise SessionInputsError(
            f"{path} carries no pre_boot_raw_event_ids list — that key is the "
            "runner's record of what was already in the journal at boot, and "
            "without it a pre-boot line is indistinguishable from a line the "
            "runtime failed to consume"
        )
    return frozenset(ids)


def unpaired_reasons(
    *,
    consumed: frozenset[str],
    dispositions: Mapping[str, str],
    pre_boot: frozenset[str],
) -> dict[str, str]:
    """Why each produced-but-unconsumed bar has no live counterpart."""
    reasons: dict[str, str] = {}
    for raw_event_id, stage in dispositions.items():
        if raw_event_id in consumed:
            continue
        if stage == "published":
            reasons[raw_event_id] = (
                REASON_PRE_BOOT
                if raw_event_id in pre_boot
                else REASON_UNCONSUMED_AFTER_BOOT
            )
        else:
            reasons[raw_event_id] = stage
    return reasons


def build_consumed_ids_document(
    *,
    data_dir: Path,
    producer_log: Path | None = None,
    boot_snapshot: Path | None = None,
) -> dict[str, Any]:
    """The ``consumed-ids`` document: the id filter plus the reason map."""
    snapshots = read_snapshots(data_dir)
    if not snapshots:
        raise SessionInputsError(
            f"{data_dir / MARKETFEED_FILE_NAME} holds no snapshots — the runtime "
            "consumed nothing, so an id filter built from it would silently "
            "empty every comparison"
        )
    instrument = _assert_one_instrument(snapshots)
    consumed = frozenset(snapshot.raw_event_id for snapshot in snapshots)
    dispositions = (
        producer_dispositions(producer_log) if producer_log is not None else {}
    )
    pre_boot = (
        read_boot_snapshot(boot_snapshot)
        if boot_snapshot is not None
        else (frozenset())
    )
    reasons = unpaired_reasons(
        consumed=consumed, dispositions=dispositions, pre_boot=pre_boot
    )
    reason_counts: dict[str, int] = {}
    for reason in reasons.values():
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "kind": "consumed_raw_event_ids",
        "instrument": instrument,
        "generated_from": {
            "data_dir": str(data_dir),
            "marketfeed_sqlite3": _file_ref(data_dir / MARKETFEED_FILE_NAME),
            "marketfeed_schema_version": PINNED_MARKETFEED_SCHEMA_VERSION,
            "producer_log": _file_ref(producer_log),
            "boot_snapshot": _file_ref(boot_snapshot),
        },
        "counts": {
            "snapshots": len(snapshots),
            "consumed_raw_event_ids": len(consumed),
            "producer_disposed_bars": len(dispositions),
            "unpaired": len(reasons),
            "pre_boot_lines_at_boot": len(pre_boot),
        },
        "raw_event_ids": sorted(consumed),
        "unpaired_reasons": dict(sorted(reasons.items())),
        "unpaired_reason_counts": dict(sorted(reason_counts.items())),
    }


# ---------------------------------------------------------------------------
# The evidence side: what the live runtime decided
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionBlock:
    """One tick's engine records: the decision, then its commitment flow."""

    seq: int
    kind: str
    payload: dict[str, Any]
    flow: tuple[tuple[str, dict[str, Any]], ...]


def read_decision_blocks(data_dir: Path) -> tuple[DecisionBlock, ...]:
    """Group the session's engine records into one block per decision pass.

    A block opens at a :data:`DECISION_KINDS` record and runs to the next one;
    the :data:`FLOW_KINDS` records between them are that decision's commitment
    flow, which is the order the engine writes them in (the proposal is
    recorded before the flow it starts).

    Raises:
        SessionInputsError: A flow record appears before any decision record.
            Nothing it could belong to has been seen, so attributing it to the
            NEXT decision would attach one tick's send to another tick's bar.
    """
    conn = _connect_ro(
        data_dir / EVIDENCE_FILE_NAME,
        label="evidence",
        pinned_version=PINNED_EVIDENCE_SCHEMA_VERSION,
    )
    wanted = (*DECISION_KINDS, *FLOW_KINDS)
    placeholders = ",".join("?" * len(wanted))
    try:
        rows = list(
            conn.execute(
                "SELECT seq, kind, payload_json FROM entries "
                f"WHERE kind IN ({placeholders}) ORDER BY seq",
                wanted,
            )
        )
    finally:
        conn.close()

    blocks: list[DecisionBlock] = []
    current: dict[str, Any] | None = None
    flow: list[tuple[str, dict[str, Any]]] = []
    for seq, kind, payload_json in rows:
        payload = json.loads(payload_json)
        if kind in DECISION_KINDS:
            if current is not None:
                blocks.append(
                    DecisionBlock(
                        seq=current["seq"],
                        kind=current["kind"],
                        payload=current["payload"],
                        flow=tuple(flow),
                    )
                )
            current, flow = {"seq": int(seq), "kind": str(kind), "payload": payload}, []
            continue
        if current is None:
            raise SessionInputsError(
                f"evidence seq {seq} is a {kind} record with no decision record "
                "before it — a commitment-flow record belongs to the decision "
                "that started it, and attributing it to the next one would put "
                "one tick's flow on another tick's bar"
            )
        flow.append((str(kind), payload))
    if current is not None:
        blocks.append(
            DecisionBlock(
                seq=current["seq"],
                kind=current["kind"],
                payload=current["payload"],
                flow=tuple(flow),
            )
        )
    return tuple(blocks)


def _live_outcome_kind(block: DecisionBlock) -> str:
    """B1b's ``outcome_kind`` token for one live decision block."""
    if block.kind != "DECISION_OUTCOME_EMITTED":
        return NO_OUTCOME_KIND
    outcome_type = block.payload.get("outcome_type")
    kind = OUTCOME_TYPE_TO_KIND.get(str(outcome_type))
    if kind is None:
        raise SessionInputsError(
            f"evidence seq {block.seq}: outcome_type {outcome_type!r} is not one "
            "this extractor can map to a B1b decision kind. Only "
            f"{sorted(OUTCOME_TYPE_TO_KIND)} is derivable from the durable "
            "record: a Proposal is ACTION or FLAT by its position_effect, which "
            "EngineEvidenceRecord does not carry (it records outcome_type and "
            "outcome_digest). Labelling it either way would be this module "
            "deciding what the engine decided"
        )
    return kind


def _flow_halt_reason(block: DecisionBlock) -> str | None:
    for kind, payload in block.flow:
        if kind == "FLOW_HALTED":
            reason = payload.get("halt_reason")
            return None if reason is None else str(reason)
    return None


def live_decision_records(data_dir: Path) -> list[dict[str, Any]]:
    """One record per live decision, in B1b's trace shape.

    The keys B3 reads from a trace line — ``raw_event_id``, ``as_of_ms``,
    ``outcome_kind``, ``rule_id``, ``capacity_denied`` — are all present.
    ``rule_id`` is always ``null`` and says so in the sidecar: B1b resolves it
    from the emitted outcome's ``rationale`` through the authored policy's rule
    index, and the rationale is on the in-memory outcome, not in the durable
    record. B3's live comparison therefore compares the decision KIND and the
    capacity denial, never the rule id.

    ``as_of_ms`` is the snapshot's — the WRITE stamp the producer put on the
    journal line — and is deliberately not comparable to B1a's label-derived
    ``as_of_ms``; B3 does not compare them.
    """
    snapshots = read_snapshots(data_dir)
    blocks = read_decision_blocks(data_dir)
    if len(snapshots) != len(blocks):
        raise SessionInputsError(
            f"the session issued {len(snapshots)} snapshot(s) but recorded "
            f"{len(blocks)} decision(s). The pairing is ordered — the k-th "
            "decision belongs to the k-th snapshot — so unequal counts mean a "
            "tick was queued without being run (a held runtime), or a decision "
            "was recorded for something other than a market tick. Either way "
            "the bar each decision was about is not decidable from these two "
            "stores"
        )
    _assert_one_instrument(snapshots)
    records: list[dict[str, Any]] = []
    for index, (snapshot, block) in enumerate(zip(snapshots, blocks)):
        flow_halt = _flow_halt_reason(block)
        records.append(
            {
                "raw_event_id": snapshot.raw_event_id,
                "as_of_ms": snapshot.as_of_ms,
                "bar_index": index,
                "outcome_kind": _live_outcome_kind(block),
                "rule_id": None,
                "pipeline_halt_reason": block.payload.get("halt_reason"),
                "flow_halt_reason": flow_halt,
                "capacity_denied": flow_halt == CAPACITY_DENIAL_HALT_REASON,
                "handed_off": any(kind == "SEND_HANDED_OFF" for kind, _ in block.flow),
                "evidence_seq": block.seq,
                "evidence_kind": block.kind,
                "snapshot_id": snapshot.snapshot_id,
                "outcome_digest": block.payload.get("outcome_digest"),
                "capsule_id": block.payload.get("capsule_id"),
            }
        )
    return records


def build_live_lineage(
    *, data_dir: Path, records: Sequence[Mapping[str, Any]], payload: bytes
) -> dict[str, Any]:
    """The sidecar B3 reads beside ``live.jsonl``."""
    kinds: dict[str, int] = {}
    for record in records:
        kind = str(record["outcome_kind"])
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": SOURCE_ID,
        "kind": "live_decisions",
        "generated_from": {
            "data_dir": str(data_dir),
            "evidence_sqlite3": _file_ref(data_dir / EVIDENCE_FILE_NAME),
            "evidence_schema_version": PINNED_EVIDENCE_SCHEMA_VERSION,
            "marketfeed_sqlite3": _file_ref(data_dir / MARKETFEED_FILE_NAME),
            "marketfeed_schema_version": PINNED_MARKETFEED_SCHEMA_VERSION,
        },
        "join": {
            "method": "ordered_snapshot_to_decision",
            "guard": (
                "equal counts, one instrument, exactly one preimage row per "
                "snapshot — any of these failing is a refusal"
            ),
            "rule_id": (
                "always null: B1b resolves it from the emitted outcome's "
                "rationale, which the durable evidence record does not carry"
            ),
            "as_of_ms": (
                "the snapshot's write stamp, NOT B1a's bar label — the two are "
                "different quantities and B3 does not compare them"
            ),
        },
        "output": {
            "live_jsonl_sha256": hashlib.sha256(payload).hexdigest(),
            "live_jsonl_lines": len(records),
        },
        "counts": {"outcome_kinds": dict(sorted(kinds.items()))},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def render_jsonl(records: Sequence[Mapping[str, Any]]) -> bytes:
    """One canonical JSON object per line — stable bytes for a digest."""
    return "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    ).encode("utf-8")


def render_json(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/tos_cp3/session_inputs.py",
        description=(
            "CP-3 §3.6 — extract B3's two session-derived inputs from a tenant "
            "session's durable stores (read-only, no tos import)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    consumed = sub.add_parser(
        "consumed-ids",
        help="the raw_event_id set the runtime consumed, plus the unpaired reasons",
    )
    consumed.add_argument("--data-dir", type=Path, required=True)
    consumed.add_argument(
        "--producer-log",
        type=Path,
        default=None,
        help=(
            "the producer's own producer-log.jsonl; without it the document "
            "carries no unpaired reasons at all rather than guessed ones"
        ),
    )
    consumed.add_argument(
        "--boot-snapshot",
        type=Path,
        default=None,
        help=(
            "the runner's boot-journal-snapshot.json; without it a pre-boot "
            "line cannot be told from one the runtime failed to consume"
        ),
    )
    consumed.add_argument("--out", type=Path, required=True)

    live = sub.add_parser(
        "live-decisions",
        help="one record per live decision, shaped like B1b's offline trace",
    )
    live.add_argument("--data-dir", type=Path, required=True)
    live.add_argument(
        "--out",
        type=Path,
        required=True,
        help="a directory; live.jsonl and lineage.json are written into it",
    )
    return parser


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main(argv: list[str] | None = None) -> int:
    """CLI. Exit codes: ``0`` ok, ``2`` refusal."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "consumed-ids":
            document = build_consumed_ids_document(
                data_dir=args.data_dir,
                producer_log=args.producer_log,
                boot_snapshot=args.boot_snapshot,
            )
            _write(args.out, render_json(document))
            print(
                f"consumed-ids: {document['counts']['consumed_raw_event_ids']} id(s), "
                f"{document['counts']['unpaired']} unpaired -> {args.out}"
            )
            return 0
        records = live_decision_records(args.data_dir)
        payload = render_jsonl(records)
        lineage = build_live_lineage(
            data_dir=args.data_dir, records=records, payload=payload
        )
        _write(args.out / "live.jsonl", payload)
        _write(args.out / "lineage.json", render_json(lineage))
        print(f"live-decisions: {len(records)} record(s) -> {args.out}")
        return 0
    except SessionInputsError as exc:
        print(f"session_inputs: REFUSED — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI tests
    raise SystemExit(main())
