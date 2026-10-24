"""Per-pass Safety Authority witness heartbeat (B5, 2026-10-24 stock MOCK dry-run).

**The incident.** The rendered stock tree, booted ``--transport kis-mock`` offline, reached the
send boundary with every verify item SATISFIED but one: CURRENTNESS was UNKNOWN because the
SAFETY_AUTHORITY currentness dimension was not positively established. Measured cause:
:meth:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService.witness` ran at boot and next
at the send boundary, ~1.6 s later. Its age is measured between time-service snapshot anchors,
``authority.yaml::containment_bound_ms`` is 1000, and an expired window never recovers by
design (that method's docstring — the 2026-09-08 review closed the resettable baseline as a
fail-open). Every real signal arrives minutes after boot, so every send was refused.

**What this does.** Re-verifies the witness once per scheduler pass, as the first step of the
pass's post-pass hook (:func:`with_authority_heartbeat` — before the fill observer, so an
observer failure cannot skip it), i.e. right after that pass's time evaluation and decision. Each call is the method's own full online check (time ``TRUSTED``, a fresh
``read_linearizable`` on the RCL, age within the bound); a call within the bound ratchets the
baseline forward, exactly as a send-boundary call would. It never establishes what boot did not
— the baseline only moves on a call that is itself within the bound of the last good one — and
an expired window stays expired, so a missed heartbeat is still a permanent refusal (fail
closed, now by intent rather than by accident).

**The bound it needs.** While the session is known closed, the time pacer evaluates only every
``marketfeed.yaml::time_evaluate_closed_interval_ms`` (60000), so with a 1000 ms bound a witness
held across a closed period expires at the open whatever this does. Operator decision
2026-10-24 (option (A)): the stock tree's ``authority.yaml::containment_bound_ms`` is 90000 (the
closed cadence + one pass); paper / LONG / SHORT stay at 1000 until their step-4 path exists.

**Cost.** One ``current_snapshot()`` read plus one SQLite ``read_linearizable`` per pass —
measured on a composed stock render: median 0.048 ms, p99 0.125 ms, max 0.28 ms (2000 calls)
against a 400 ms pass. It runs in the post-pass hook, which the #949 pass budget already times
as its own segment, so the cost lands on the pass-overrun accounting with no new clock.

**Evidence.** One ``AUTHORITY_WITNESS_LOST`` row each time the witness goes from present to
absent — the instant authority was lost, which is otherwise visible only as a refused send
later. Nothing is recorded while it stays present or stays absent.
"""

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

#: The evidence kind for a present -> absent witness transition (module docstring).
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
        """Wire the heartbeat.

        Args:
            epoch_service: The composed :class:`~tos_runtime.authority.epoch
                .SafetyAuthorityEpochService` — the SAME instance the SAFETY_AUTHORITY
                dimension reader and capability validity call, so the baseline this ratchets is
                the one they read.
            evidence: The evidence store the loss row is appended to.
        """
        self._epoch_service = epoch_service
        self._evidence = evidence
        # Boot already established the witness (compose's own epoch transition reads it), so
        # the first absent heartbeat is a loss, not a "never had it".
        self._present = True

    def __call__(self) -> bool:
        """One heartbeat. Returns the witness's ``present`` — informational only: nothing in
        the pass branches on it; the send boundary reads the witness itself."""
        witness = self._epoch_service.witness()
        present = witness.present is True
        if self._present and not present:
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
    """The scheduler's post-pass hook: the heartbeat over ``composed``'s own epoch service (the
    instance the send boundary reads), then ``after_pass`` when there is one."""
    heartbeat = AuthorityWitnessHeartbeat(
        composed.authority_epoch_service, composed.evidence_store
    )

    def _pass() -> None:
        heartbeat()
        if after_pass is not None:
            after_pass()

    return _pass
