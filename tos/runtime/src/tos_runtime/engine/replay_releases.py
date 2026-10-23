"""Re-applying the live engine's projection releases during boot replay (PR-3b).

The live engine releases a reservation in its in-memory projection after the RCL commits the
release (:mod:`tos_runtime.engine.finality_projection` — the driver's finality hook, or the fill
observer's finality re-run). That is not an inbox event, so a replay that only re-handles inbox
events would end with the reservation still held, and from then on answer step 8's
``admits_new_exposure`` differently from the live engine (Codex r2 claim 2). Each live release is
therefore recorded (``ENGINE_PROJECTION_RELEASED``) and re-applied here at the same point: before
the first event whose ``EVENT_CONSUMED`` row is newer than the release row, or at the end.

**A release row is never trusted on its own (Codex r2 HIGH 2).** Before it is applied, the
durable chain it claims must exist, for the same attempt, in this order:

1. a ``POSTTRADE_FINALITY_PROOF`` row whose ``proof_id`` is the row's ``proof_digest`` and whose
   idempotency key names the attempt;
2. the ``CAPACITY_RELEASE_INTENT`` row at exactly the row's ``evidence_seq``, after the proof,
   naming the same attempt, proof and ``resolution_generation``;
3. the RCL's own ``RCL_RESERVATION_TRANSITION`` evidence for the attempt's release command
   (``release-<attempt_id>``, kind ``ReleaseReservation``), after the intent;
4. the release row itself, after the RCL transition.

Anything missing, mismatched or out of order is a divergence — as is a corroborated release the
replayed projection refuses. A corroborated release for an attempt this replay never re-handled
(outside a windowed replay) has nothing to reproduce and is skipped.

Firewall: stdlib + ``tos.engine`` + ``tos_runtime.evidence`` only. Evidence-kind and command-id
literals are cited, not imported (the replay modules' own convention).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tos.engine import EngineEvent
from tos.engine.state import FinalityProofRef

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["EngineReleases"]

_RELEASED_KIND = "ENGINE_PROJECTION_RELEASED"
_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"
_PROOF_KIND = "POSTTRADE_FINALITY_PROOF"
_INTENT_KIND = "CAPACITY_RELEASE_INTENT"
_RCL_KIND = "RCL_RESERVATION_TRANSITION"
#: ``tos.rcl.CommandType.RELEASE_RESERVATION.value`` and ``release_consumer.release_command_id``.
_RCL_RELEASE_COMMAND_KIND = "ReleaseReservation"


def _release_command_id(attempt_id: str) -> str:
    return f"release-{attempt_id}"


@dataclass(frozen=True)
class _Row:
    seq: int
    ref: FinalityProofRef | None
    #: ``None`` when the durable chain corroborates the row; otherwise why it does not.
    refusal: str | None
    attempt_id: str


class _Index:
    """The durable rows a release row is checked against, read once."""

    def __init__(self, evidence_store: SqliteEvidenceStore) -> None:
        conn = evidence_store.connection
        self.proofs: dict[str, tuple[int, dict[str, Any]]] = {}
        self.intents: dict[int, dict[str, Any]] = {}
        self.rcl_releases: dict[str, int] = {}
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
            elif kind == _RCL_KIND and payload.get("kind") == _RCL_RELEASE_COMMAND_KIND:
                command_id = payload.get("command_id")
                if isinstance(command_id, str):
                    self.rcl_releases.setdefault(command_id, seq)

    def refusal(self, seq: int, ref: FinalityProofRef) -> str | None:
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
        rcl_seq = self.rcl_releases.get(_release_command_id(ref.attempt_id))
        if rcl_seq is None:
            return "no committed RCL release transition for this attempt"
        if not ref.evidence_seq < rcl_seq < seq:
            return "the RCL release is out of order with its intent or this row"
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
        on_divergence: Callable[[dict[str, Any]], None],
    ) -> EngineReleases:
        """Read every release row and check each against the durable chain.

        Args:
            evidence_store: The store the live run recorded into.
            on_divergence: Records one divergence (the caller's ``REPLAY_DIVERGED`` halt).
        """
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
                rows.append(_Row(seq, ref, index.refusal(seq, ref), attempt_id))
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
        """Apply every pending release recorded before ``event_id``'s receipt (``None``: all of
        them — the ones after the last event), then note ``event``'s attempt as replayed.

        Returns:
            The divergence ids recorded this call: an uncorroborated row, or a corroborated one
            the replayed projection refused.
        """
        bound = self._consumed_seq.get(event_id) if event_id is not None else None
        ledger = getattr(core, "ledger", None)
        diverged: list[str] = []
        while self._pending and (
            event_id is None or (bound is not None and self._pending[0].seq < bound)
        ):
            row = self._pending.pop(0)
            if row.refusal is None and row.attempt_id not in self._seen_attempts:
                continue  # outside a windowed replay: nothing to reproduce
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
