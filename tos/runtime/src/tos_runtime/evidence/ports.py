"""The runtime-side append port lane K's Trustworthy Time service depends on.

Design #40 (``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md``) §5 sequence item 2 (lane L, durable Evidence Store) and the
slice plan (``docs/plans/2026-09-08-tos-phase2-runtime-slice1-time-evidence-
plan.md`` §3 "레인 간 계약") fix the inter-lane contract exactly here: lane L
(this package) authors this Protocol FIRST, before any other evidence module,
so lane K's Trustworthy Time service (``tos_runtime.time``) can depend on it
by import alone — never on :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`
directly, so K's own tests can satisfy the port with an in-memory double
instead of standing up a real sqlite store.

The signature is fixed by the slice plan and MUST NOT drift once lane K has
started importing it: ``append(payload, *, kind, record_class) ->
EvidenceAppendReceipt``. :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`
is the durable production implementation; it structurally satisfies this
Protocol (a wider signature — optional ``segment_id``/``runtime_identity``/
``outbox_targets`` keyword-only extras — is still a satisfying implementation
of a narrower Protocol, since a caller using only the Protocol's own three
arguments never observes them).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from tos.evidence import EvidenceAppendReceipt

__all__ = ["EvidenceAppendPort"]


@runtime_checkable
class EvidenceAppendPort(Protocol):
    """The durable-append seam a runtime service evidences its state through.

    A conforming ``append()`` returns an :class:`~tos.evidence.EvidenceAppendReceipt`
    **only after** durable commit (design #40 §D3.1 line 88's "영수증이 없는
    «기록됨» 주장은 존재하지 않는다") — every implementation of this Protocol
    carries that obligation even though the Protocol itself, being structural,
    cannot enforce it at the type level.
    """

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        """Durably append one evidence record and return its commit receipt.

        Args:
            payload: The record's own fields, prior to any secret-field
                scrubbing the implementation applies.
            kind: The record kind (implementation-defined vocabulary).
            record_class: The record's retention/durability class label.

        Returns:
            The receipt proving durable commit — never returned on failure.
        """
        ...
