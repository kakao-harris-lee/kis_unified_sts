"""Re-applying the live engine's never-sent discards during boot replay (2026-11-01 plan §3.2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tos.engine.records import UnsentDiscardRef
from tos.engine.vocabulary import RESERVATION_DISCARDED_UNSENT_KIND

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["EngineDiscards"]

_EVENT_CONSUMED_KIND = "EVENT_CONSUMED"


@dataclass(frozen=True)
class _Row:
    seq: int
    ref: UnsentDiscardRef | None
    proposal_id: str


class EngineDiscards:
    """Pending discard rows, applied to the replay core in live order (module docstring)."""

    def __init__(
        self,
        rows: list[_Row],
        consumed_seq: dict[str, int],
        on_divergence: Callable[[dict[str, Any]], None],
    ) -> None:
        self._pending = rows
        self._consumed_seq = consumed_seq
        self._on_divergence = on_divergence

    @classmethod
    def load(
        cls,
        evidence_store: SqliteEvidenceStore,
        *,
        on_divergence: Callable[[dict[str, Any]], None],
    ) -> EngineDiscards:
        """Read every recorded discard row, in ``seq`` order."""
        conn = evidence_store.connection
        raw = conn.execute(
            "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (RESERVATION_DISCARDED_UNSENT_KIND,),
        ).fetchall()
        rows: list[_Row] = []
        consumed: dict[str, int] = {}
        if raw:
            for seq, payload_json in raw:
                payload = json.loads(payload_json).get("payload", {})
                proposal_id = str(payload.get("proposal_id"))
                try:
                    ref: UnsentDiscardRef | None = UnsentDiscardRef.model_validate(
                        payload
                    )
                except ValueError:
                    ref = None
                rows.append(_Row(seq, ref, proposal_id))
            for seq, payload_json in conn.execute(
                "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
                (_EVENT_CONSUMED_KIND,),
            ):
                event_id = json.loads(payload_json).get("payload", {}).get("event_id")
                if isinstance(event_id, str):
                    consumed.setdefault(event_id, seq)
        return cls(rows, consumed, on_divergence)

    def before(self, event_id: str | None, core: object) -> list[str]:
        """Apply every pending discard recorded before ``event_id``'s receipt (``None``: all of"""
        bound = self._consumed_seq.get(event_id) if event_id is not None else None
        ledger = getattr(core, "ledger", None)
        diverged: list[str] = []
        while self._pending and (
            event_id is None or (bound is not None and self._pending[0].seq < bound)
        ):
            row = self._pending.pop(0)
            if row.ref is None:
                refusal: str | None = "malformed discard row"
            elif ledger is None or not ledger.discard_unsent(row.ref):
                refusal = "the replayed projection refused the discard"
            else:
                continue
            marker = f"engine-discard:{row.proposal_id}"
            self._on_divergence(
                {
                    "event_id": marker,
                    "replay_result_state": "ENGINE_DISCARD_NOT_REPRODUCED",
                    "proposal_id": row.proposal_id,
                    "discard_row_seq": row.seq,
                    "reason": refusal,
                }
            )
            diverged.append(marker)
        return diverged
