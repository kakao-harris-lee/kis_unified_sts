"""Re-applying the live engine's never-sent discards during boot replay (2026-11-01 plan §3.2).

The live runtime discards a reservation whose flow halted after step 9's atomic commit but before
the Send Boundary (``tos.engine.state.ProvisionalReservationLedger.discard_unsent``; the wiring
that decides *when* is plan §3.3 — Q2, not here). That is not an inbox event, so a replay which
only re-handles inbox events would end with the reservation still held, and from then on answer
step 8's ``admits_new_exposure`` differently from the live engine — exactly the divergence
:mod:`tos_runtime.engine.replay_releases` exists to prevent for the release path. Each accepted
discard is therefore recorded (``RESERVATION_DISCARDED_UNSENT``) and re-applied here at the same
point: before the first event whose ``EVENT_CONSUMED`` row is newer than the discard row, or at
the end.

**The kernel's own gate is the corroboration.** A discard row needs no RCL chain behind it the way
a release row does: ``discard_unsent`` accepts only a reservation the *replayed* projection itself
still holds as ``NOT_SENT`` and pre-``POTENTIALLY_LIVE``, and removes nothing else, so a row naming
anything else is refused by the kernel and reported here as a divergence. The runtime-side evidence
predicate that decides whether a discard was legitimate in the first place (plan §3.1) belongs to
the writer, not to this reader.

**One case this cannot distinguish**, where :class:`~tos_runtime.engine.replay_releases
.EngineReleases` can: the record carries a proposal id and the kernel looks it up across every
scope, answering a single ``False`` both for "the replayed projection refused" and for "this replay
never re-derived that proposal at all" (a window that excludes the committing flow). Both are
reported. That is the conservative answer, and a window is already unsound for a ledger-carrying
stream — see :func:`tos_runtime.engine.replay.replay_engine`'s own caveat.

Firewall: stdlib + ``tos.engine`` + ``tos_runtime.evidence`` only. ``EVENT_CONSUMED`` is cited as
a literal (the replay modules' own convention for a kind the *runtime* declares); the discard kind
is imported instead, because the kernel declares that one and importing it is what keeps the
writer and this reader from drifting apart on the name.
"""

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
    #: ``None`` when the row's payload is not a well-formed :class:`UnsentDiscardRef`.
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
        """Read every recorded discard row, in ``seq`` order.

        Args:
            evidence_store: The store the live run recorded into.
            on_divergence: Records one divergence (the caller's ``REPLAY_DIVERGED`` halt).
        """
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
        """Apply every pending discard recorded before ``event_id``'s receipt (``None``: all of
        them — the ones after the last event).

        Returns:
            The divergence ids recorded this call: a malformed row, or one the replayed projection
            refused (module docstring — the kernel's gate is what corroborates the row).
        """
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
