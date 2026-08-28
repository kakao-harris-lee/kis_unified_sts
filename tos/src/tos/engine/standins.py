"""⚠ NON-AUTHORITATIVE PROVISIONAL stand-ins for the absent authority runtimes (design #31 §4.4).

Steps 4 (Independent Approval), 6 (Aggregate Risk Authority), 7 (Action Flow Governor), 8-10 (the
RCL verification / atomic commit / unavailability), and 13-14 (attempt bind / Transmission
Capability) all belong to **owning runtimes that do not exist yet** (``tos.are.__init__`` lines
17-18; ``tos.afg.__init__`` lines 28-29; ADR-002-002 §8 for the ledger). Slice #1 fills them with
in-memory stand-ins so the *wiring* — the call order, the binding hand-off, the fail-closed stop —
is demonstrable.

**What a stand-in is.** It produces the *shape* of the step's verdict and nothing else. It performs
no stateful authority act: no independent human/service approval, no linearizable commit, no
fencing epoch, no CAS, no capability issuance, no nonce consumption.

**What a stand-in is therefore not.** It does not demonstrate ADR-002-002 INV-004:164 (No
Transmission Without Capacity), INV-006:174, or INV-008:187 (Stale Authority Cannot Mutate); it
does not model concurrency, crash recovery, or epoch fencing; and it **closes no capacity or
approval EV** (design #31 §1.1/§4.4). Every verdict it emits is labelled
:data:`~tos.engine.vocabulary.StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL`, and there is no
``AUTHORITATIVE`` member it could be promoted to.

The stand-ins deliberately admit **only** on a positively supplied injected decision: a stand-in
that admitted by default would be the "assume-grant" fall-through the series has rejected twice
(#6, #16 C1). ``None`` is always ``UNKNOWN``, never a pass.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.engine.records import StageRequest, StageVerdict
from tos.engine.sequencer import Stage
from tos.engine.vocabulary import (
    INJECTED_STAGE_STEPS,
    CommitmentStep,
    StageAuthorityClass,
    StageOutcome,
)

__all__ = ["ProvisionalStandIn", "provisional_stage_map"]


class ProvisionalStandIn:
    """A single non-authoritative stand-in for one commitment step (design #31 §4.4).

    ⚠ **NON-AUTHORITATIVE PROVISIONAL.** It admits only when ``admit`` is positively ``True`` and
    the caller has supplied the bindings the step is supposed to produce; otherwise it is
    ``UNKNOWN`` (absent decision) or ``DENY`` (an explicit refusal). There is no default-admit
    path.
    """

    def __init__(
        self,
        step: CommitmentStep,
        *,
        admit: bool | None = None,
        denied: bool | None = None,
        bound_digest: str | None = None,
        bound_identity: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Configure the stand-in.

        Args:
            step: The commitment step it answers.
            admit: Positive polarity — only ``True`` admits. ``None`` (no decision was produced)
                and ``False`` are both restrictive.
            denied: Negative polarity — an explicit refusal is recorded **only** on ``is True``;
                ``None`` never means "not denied" (the ``is False``-only discipline in its
                positive-mirror form).
            bound_digest: The digest this step's artifact would carry.
            bound_identity: The identity this step's artifact would carry (e.g. a permit id).
            reason: A recorded reason.
        """
        self._step = step
        self._admit = admit
        self._denied = denied
        self._bound_digest = bound_digest
        self._bound_identity = bound_identity
        self._reason = reason

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Produce the step's non-authoritative verdict.

        Args:
            request: The sequencer's stage request (its ``step`` is answered verbatim).

        Returns:
            The :class:`~tos.engine.records.StageVerdict`.
        """
        reason: str | None
        if self._denied is True:
            outcome = StageOutcome.DENY
            reason = self._reason or "provisional stand-in refused this step"
        elif self._admit is True:
            outcome = StageOutcome.ADMIT
            reason = self._reason
        else:
            outcome = StageOutcome.UNKNOWN
            reason = self._reason or (
                "no decision was produced by the provisional stand-in — UNKNOWN is restrictive, "
                "never an assumed grant (design #31 §4.4)"
            )
        return StageVerdict(
            step=request.step,
            outcome=outcome,
            authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
            native_verdict_type=None,
            bound_digest=self._bound_digest,
            bound_identity=self._bound_identity,
            reason=reason,
        )


def provisional_stage_map(
    *,
    conformance_proof_digest: str,
    action_flow_permit_identity: str,
    denied_steps: Mapping[CommitmentStep, str] | None = None,
    unknown_steps: frozenset[CommitmentStep] | None = None,
) -> dict[CommitmentStep, Stage]:
    """Build a complete stand-in map for every injected step (design #31 §4.4).

    ⚠ Every entry is **NON-AUTHORITATIVE PROVISIONAL**: this map demonstrates the wiring, never
    the safety. Step 11 carries the conformance-proof digest and step 9 the Action Flow Permit
    identity, because those are the two bindings the Coordinator's step-12 attempt request must
    consume (ADR-002-002 §11.3:599) — supplying them here is what makes the *binding hand-off*
    observable.

    Args:
        conformance_proof_digest: The digest the step-11 stand-in reports.
        action_flow_permit_identity: The permit identity the step-9 stand-in reports.
        denied_steps: Steps that should explicitly deny, mapped to their reason.
        unknown_steps: Steps that should produce no decision (restrictive ``UNKNOWN``).

    Returns:
        A step → stage mapping covering exactly
        :data:`~tos.engine.vocabulary.INJECTED_STAGE_STEPS`.
    """
    denied = dict(denied_steps or {})
    unknown = frozenset(unknown_steps or frozenset())
    stages: dict[CommitmentStep, Stage] = {}
    for step in INJECTED_STAGE_STEPS:
        if step in denied:
            stages[step] = ProvisionalStandIn(step, denied=True, reason=denied[step])
            continue
        if step in unknown:
            stages[step] = ProvisionalStandIn(step)
            continue
        bound_digest = (
            conformance_proof_digest
            if step is CommitmentStep.ORDER_CONFORMANCE_PROOF
            else None
        )
        bound_identity = (
            action_flow_permit_identity if step is CommitmentStep.ATOMIC_COMMIT else None
        )
        stages[step] = ProvisionalStandIn(
            step,
            admit=True,
            bound_digest=bound_digest,
            bound_identity=bound_identity,
            reason="NON-AUTHORITATIVE PROVISIONAL stand-in — wiring only, closes no EV",
        )
    return stages
