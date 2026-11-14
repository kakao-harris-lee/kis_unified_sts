"""Per-pass Safety Authority witness heartbeat (B5, 2026-10-24 stock MOCK dry-run)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from tos.authority import CurrentnessWitness

if TYPE_CHECKING:
    from tos_runtime.compose._types import ComposedRuntime

__all__ = [
    "AUTHORITY_WITNESS_LOST_KIND",
    "AuthorityWitnessHeartbeat",
    "with_authority_heartbeat",
]

AUTHORITY_WITNESS_LOST_KIND = "AUTHORITY_WITNESS_LOST"


class _WitnessSource(Protocol):
    def witness(self) -> CurrentnessWitness: ...


class _EvidenceAppend(Protocol):
    def append(
        self, payload: dict[str, object], *, kind: str, record_class: str
    ) -> object: ...


class AuthorityWitnessHeartbeat:
    """Call :meth:`witness` once per pass; record the moment it is lost (module docstring)."""

    def __init__(
        self, epoch_service: _WitnessSource, evidence: _EvidenceAppend
    ) -> None:
        """Wire the heartbeat."""
        self._epoch_service = epoch_service
        self._evidence = evidence
        self._present: bool | None = None

    def __call__(self) -> bool:
        """One heartbeat. Returns the witness's ``present`` — informational only: nothing in"""
        witness = self._epoch_service.witness()
        present = witness.present is True
        if self._present is True and not present:
            self._evidence.append(
                {
                    "witness_source": witness.witness_source,
                    "within_containment_bound": witness.within_containment_bound,
                },
                kind=AUTHORITY_WITNESS_LOST_KIND,
                record_class=AUTHORITY_WITNESS_LOST_KIND,
            )
        self._present = present
        return present


def with_authority_heartbeat(
    composed: ComposedRuntime, after_pass: Callable[[], None] | None
) -> Callable[[], None]:
    """The scheduler's post-pass hook: the heartbeat over ``composed``'s own epoch service (the"""
    heartbeat = AuthorityWitnessHeartbeat(
        composed.authority_epoch_service, composed.evidence_store
    )

    def _pass() -> None:
        heartbeat()
        if after_pass is not None:
            after_pass()

    return _pass
