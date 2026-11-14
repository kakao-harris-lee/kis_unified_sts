"""Re-applying the live engine's projection releases during boot replay (PR-3b)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tos.engine import EngineEvent
from tos.engine.state import FinalityProofRef

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["EngineReleases", "RclCommitted"]

RclCommitted = Callable[[str], "tuple[int, str | None] | None"]

_RELEASED_KIND = "ENGINE_PROJECTION_RELEASED"
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
_RCL_KIND = "RCL_RESERVATION_TRANSITION"
_RCL_RELEASE_COMMAND_KIND = "ReleaseReservation"


def _release_command_id(attempt_id: str) -> str:
    return f"release-{attempt_id}"


@dataclass(frozen=True)
class _Row:
    seq: int
    ref: FinalityProofRef | None
    refusal: str | None
    attempt_id: str


class _Index:
    """The durable rows a release row is checked against, read once."""

    def __init__(self, evidence_store: SqliteEvidenceStore) -> None:
        conn = evidence_store.connection
        self.proofs: dict[str, tuple[int, dict[str, Any]]] = {}
        self.intents: dict[int, dict[str, Any]] = {}
        self.rcl_rows: dict[str, list[tuple[int, Any, Any]]] = {}
        self.intents_by_attempt: dict[str, list[int]] = {}
        for seq, kind, payload_json in conn.execute(
            "SELECT seq, kind, payload_json FROM entries WHERE kind IN (?, ?, ?) "
            "ORDER BY seq ASC",
            (_PROOF_KIND, _INTENT_KIND, _RCL_KIND),
        ):
            payload = json.loads(payload_json).get("payload", {})
            if kind == _PROOF_KIND and isinstance(payload.get("proof_id"), str):
                self.proofs.setdefault(payload["proof_id"], (seq, payload))
            elif kind == _INTENT_KIND:
                self.intents[seq] = payload
                self.intents_by_attempt.setdefault(
                    str(payload.get("attempt_id")), []
                ).append(seq)
            elif kind == _RCL_KIND and payload.get("kind") == _RCL_RELEASE_COMMAND_KIND:
                command_id = payload.get("command_id")
                if isinstance(command_id, str):
                    self.rcl_rows.setdefault(command_id, []).append(
                        (seq, payload.get("seq"), payload.get("command_digest"))
                    )

    def refusal(
        self, seq: int, ref: FinalityProofRef, committed: tuple[int, Any] | None
    ) -> str | None:
        """Why the release row at ``seq`` is NOT corroborated, or ``None`` (module docstring)."""
        proof = self.proofs.get(ref.proof_digest)
        if proof is None:
            return "no proof row with this proof_digest"
        proof_seq, proof_payload = proof
        if not str(proof_payload.get("idempotency_key", "")).endswith(
            f":{ref.attempt_id}"
        ):
            return "the proof row belongs to another attempt"
        intent = self.intents.get(ref.evidence_seq)
        if intent is None:
            return "evidence_seq is not a release-intent row"
        if (
            intent.get("attempt_id") != ref.attempt_id
            or intent.get("proof_id") != ref.proof_digest
            or intent.get("resolution_generation") != ref.resolution_generation
        ):
            return "the release-intent row disagrees with the release row"
        if not proof_seq < ref.evidence_seq:
            return "the release intent precedes its proof"
        if committed is None:
            return "the RCL holds no committed release for this attempt"
        committed_seq, committed_digest = committed
        matching = [
            evidence_seq
            for evidence_seq, rcl_seq, digest in self.rcl_rows.get(
                _release_command_id(ref.attempt_id), []
            )
            if rcl_seq == committed_seq and digest == committed_digest
        ]
        if not matching:
            return "no transition evidence matches the committed RCL release"
        transition_seq = matching[-1]
        if not ref.evidence_seq < transition_seq < seq:
            return "the committed release is out of order with its intent or this row"
        if any(
            ref.evidence_seq < later < transition_seq
            for later in self.intents_by_attempt.get(ref.attempt_id, [])
        ):
            return "a later release intent precedes the committed transition"
        return None


class EngineReleases:
    """Pending release rows, applied to the replay core in live order (module docstring)."""

    def __init__(
        self,
        rows: list[_Row],
        consumed_seq: dict[str, int],
        on_divergence: Callable[[dict[str, Any]], None],
    ) -> None:
        self._pending = rows
        self._consumed_seq = consumed_seq
        self._on_divergence = on_divergence
        self._seen_attempts: set[str] = set()

    @classmethod
    def load(
        cls,
        evidence_store: SqliteEvidenceStore,
        *,
        rcl_committed: RclCommitted | None,
        on_divergence: Callable[[dict[str, Any]], None],
    ) -> EngineReleases:
        """Read every release row and check each against the durable chain."""
        conn = evidence_store.connection
        raw = conn.execute(
            "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (_RELEASED_KIND,),
        ).fetchall()
        rows: list[_Row] = []
        consumed: dict[str, int] = {}
        if raw:
            index = _Index(evidence_store)
            for seq, payload_json in raw:
                payload = json.loads(payload_json).get("payload", {})
                attempt_id = str(payload.get("attempt_id"))
                try:
                    ref = FinalityProofRef.model_validate(payload)
                except ValueError:
                    rows.append(_Row(seq, None, "malformed release row", attempt_id))
                    continue
                committed = (
                    None
                    if rcl_committed is None
                    else rcl_committed(_release_command_id(ref.attempt_id))
                )
                refusal = (
                    "no RCL committed state was given to replay"
                    if rcl_committed is None
                    else index.refusal(seq, ref, committed)
                )
                rows.append(_Row(seq, ref, refusal, attempt_id))
            for seq, payload_json in conn.execute(
                "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
                (_EVENT_CONSUMED_KIND,),
            ):
                event_id = json.loads(payload_json).get("payload", {}).get("event_id")
                if isinstance(event_id, str):
                    consumed.setdefault(event_id, seq)
        return cls(rows, consumed, on_divergence)

    def before(
        self, event: EngineEvent | None, event_id: str | None, core: object
    ) -> list[str]:
        """Apply every pending release recorded before ``event_id``'s receipt (``None``: all of"""
        bound = self._consumed_seq.get(event_id) if event_id is not None else None
        ledger = getattr(core, "ledger", None)
        diverged: list[str] = []
        while self._pending and (
            event_id is None or (bound is not None and self._pending[0].seq < bound)
        ):
            row = self._pending.pop(0)
            if row.refusal is None and row.attempt_id not in self._seen_attempts:
                continue
            refusal = row.refusal
            if refusal is None and (
                ledger is None or row.ref is None or not ledger.release(row.ref)
            ):
                refusal = "the replayed projection refused the release"
            if refusal is None:
                continue
            marker = f"engine-release:{row.attempt_id}"
            self._on_divergence(
                {
                    "event_id": marker,
                    "replay_result_state": "ENGINE_RELEASE_NOT_REPRODUCED",
                    "attempt_id": row.attempt_id,
                    "release_row_seq": row.seq,
                    "reason": refusal,
                }
            )
            diverged.append(marker)
        if event is not None and event.egress_result is not None:
            self._seen_attempts.add(event.egress_result.attempt_id)
        return diverged
