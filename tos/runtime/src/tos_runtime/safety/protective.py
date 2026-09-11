"""``ProtectiveActionService`` — a verdict-only surface over the kernel ``tos.protective`` /
``tos.replacement`` packages (Phase 5 W3.2 plan
``docs/plans/2026-09-11-tos-phase5-w32-remaining-owners-plan.md`` §2 decision 8; lane d2).

**Why "verdict-only".** A repo-wide search (``grep -rn "send_once" tos/runtime/src``) shows
exactly three ``EgressResultPayload`` producers, all inside
:mod:`tos_runtime.transport.kis_mock.adapter` / :mod:`tos_runtime.engine.driver`, and the
mock transport's only send method (``send_once``) can only ACK / REJECT / TIMEOUT / UNKNOWN a
NEW attempt — there is no cancel / replace send path anywhere in this runtime (W3.2 survey
§3). So this service can classify — it can never execute. It owns no transport port, issues
no order, and mutates no RCL state; every method here is read-only over already-decided
runtime facts, exactly like the other Phase 5 W3 safety-mesh services
(:mod:`tos_runtime.safety.profile` / ``.deviation`` / ``.incident`` / ``.monitoring``), but
this class is deliberately **not** a :class:`~tos_runtime.safety.ports.SafetyMeshService` —
it owns no §9 currentness dimension (the W3.2 survey found no honest runtime CONTEXT/
CRITICAL_INPUT source either — see the ``critical_input_trust_restored`` disclosure below,
which is the same capsule-chain gap), so it exposes only :meth:`verdict` / :meth:`describe`.

**This module authors no verdict of its own** — it calls exactly two kernel ``tos.protective``
predicates over real, injected runtime facts and reports, field-by-field, which of the
remaining kernel inputs/predicates have NO real runtime source yet (kernel round #1 §0
"판정은 커널 술어만 한다"; the M6 lesson from ``tos-phase4-scopes-round-2026-09-09``: a
constant fed where a real fact belongs silences the predicate it is fed to — this module
supplies ``None``, never a stand-in constant, for every fact it cannot establish).

**Honest-source table (per-field, plan "Report back" requirement).**

* :func:`~tos.protective.derestriction_admissible` — called over
  :class:`~tos.protective.DeRestrictionInputs`:

  - the five forbidden-sole-basis ``*_only`` bools stay at the kernel default (``False`` —
    "not the sole basis"); this service asserts none of them as the trigger (it has no
    concept of "why" a transition might be attempted at all).
  - ``safety_authority_current`` = the injected time-health port's
    ``health_state() is HealthState.TRUSTED`` — a real, always-concrete (never ``None``)
    fact (:mod:`tos.time.domains.HealthState` has no third "unknown" reading between its
    five members).
  - ``hard_and_runtime_profile_valid`` = the injected
    :class:`~tos_runtime.safety.latch.RestrictiveLatchOwner`'s
    ``state() is RestrictiveLatchState.CLEAR`` — also real and always-concrete (the kernel
    ``RestrictiveLatchState`` enum has exactly two members, no ``UNKNOWN``).
  - ``reconciled_authoritative_state`` — **``None``, disclosed.** No ``tos.orthostate``
    reader is wired into this lane; there is no runtime producer of an orthostate
    ``RECONCILED`` fact this service can read.
  - ``critical_input_trust_restored`` — **``None``, disclosed.** This is the same gap the
    W3.2 survey found for the CONTEXT / CRITICAL_INPUT currentness dimensions: zero
    ``tos.capsule`` runtime imports exist anywhere in this runtime (the capsule input chain
    is unimplemented — a future, separate wave, not this lane's to fake).
  - ``explicit_safety_authority_decision`` — **``None``, disclosed.** No governed-decision
    producer exists (a real Safety-Authority explicit-decision record, distinct from any
    automatic signal) — inventing one would be exactly the "explicit decision" §8.5 line
    403-407 forbids reducing to (strategy / ordinary-execution / readiness inference).
  - ``dominating_halt_or_incident`` = the injected incident-mesh clearance's
    ``clear is not True`` — i.e. this service reads the SAME per-tick
    :class:`~tos_runtime.safety.incident.IncidentService` clearance every other W3
    consumer reads (never re-derives, never independently re-calls ``.clear()`` outside
    the tick snapshot's own consistency discipline — the caller is expected to supply this
    from the SAME :class:`~tos_runtime.compose._safety_wiring.SafetyMeshSnapshot` the
    latch owner's own ``incident_clear`` closure reads). A non-``True`` incident clearance
    (``False`` OR ``None`` — a positive dominating incident, or an unresolved one) is
    conservatively read as "a dominating halt/incident IS present" (fail-closed: an
    unresolved incident-mesh reading never relaxes toward "no dominating incident").

  With three of the five load-bearing facts ``None`` (only ``safety_authority_current`` and
  ``hard_and_runtime_profile_valid`` have a real source today), :func:`derestriction_admissible`
  returns ``False`` on every call this service makes — an honest, disclosed consequence of
  the missing sources, not a bug: this service grants no de-restriction in Phase 5 W3.2.

* :func:`~tos.protective.protective_capacity_exhausted` — called as
  ``protective_capacity_exhausted(None, budget_remaining=None)``. Neither argument has a
  runtime producer: no :class:`~tos.protective.ProtectiveCapacityProfile` policy-document
  loader exists yet (unlike :class:`~tos_runtime.safety.profile.SafetyProfileService` /
  :class:`~tos_runtime.safety.incident.IncidentService`'s own YAML loaders — building one is
  new scope, not this lane's "verdict-only" mandate), and no bounded protective-retry-budget
  tracker exists either. The kernel predicate's own fail-closed rule (a ``None`` profile, or
  a ``None`` budget, is "exhausted") makes this an honest, always-``True`` (exhausted)
  reading given the genuinely-absent sources — never a fabricated ``False`` credit of
  capacity that was never proven to exist.

* :func:`~tos.protective.protective_classification` — **NOT called.** It needs an injected
  :class:`~tos.protective.AggregateRiskComparison` / :class:`~tos.protective.IntermediateStateWitness`
  pair (final/current/no-action conservative risk magnitudes, worst-intermediate-risk,
  credible-space-bounded); no Phase 5 W3 runtime service produces conservative aggregate-risk
  comparisons at this classification layer (the AGGREGATE_RISK currentness dimension reader,
  lane d1, reads a DIFFERENT decision — ``RecordingAggregateRiskService.last_decision``'s own
  overall ``ADMIT``/``DENY`` result — not the raw comparison magnitudes this predicate itself
  needs). Fabricating either input would be exactly the "digest of nothing" anti-pattern.

* :func:`~tos.protective.mode_permits_protective` — **NOT called.** It needs an injected
  ``mode_rank`` (the authority ``PRECEDENCE_RANK`` verdict); the W3.2 survey found no runtime
  supplier of this coordinate anywhere.

* ``tos.replacement`` predicates (``overlap_first_reservation_outcome`` /
  ``cancel_first_admission_gate`` / ...) — **NOT called.** Every one needs an
  :class:`~tos.replacement.OverlapReservationClaim`, whose 9
  ``CredibleIntermediateOutcomeKind`` fields + structural no-netting judgements have no
  runtime producer; the RCL reservation projection
  (:mod:`tos_runtime.rcl.projection`) was investigated as a candidate real source (the
  same read :class:`~tos_runtime.safety.latch.CapacityOwner` already uses) and reports only
  a single scope's outstanding/absent reservation state — it carries none of the
  overlap-claim's required structural facts (netting proof, credible-intermediate-outcome
  classification), so building an ``OverlapReservationClaim`` from it would be invention,
  not derivation.

**Execution path is zero (module docstring, repeated at the class).** This service takes no
transport / adapter / RCL-mutation port in its constructor — there is structurally nothing
here that could ever call ``send_once`` or mutate an RCL reservation; :meth:`verdict` and
:meth:`describe` are the entire public surface, and both are pure reads.

**RCL projection (descriptive only, not wired here).** The W3.2 lane scope
(:mod:`tos_runtime.compose._safety_wiring`, this module's sole construction site) has no
access to a live :class:`~tos_runtime.rcl.projection.ReservationProjectionReader` +
:class:`~tos.engine.records.InstrumentKey` scope pair — that pairing is only assembled inside
``tos_runtime.compose._wiring``'s own ``_build_context_resolver`` (see
:func:`~tos_runtime.safety.latch.build_capacity_owner`'s own docstring for why), a file this
lane does not own. A future wiring change threading a
:class:`~tos_runtime.safety.latch.CapacityOwner` into this service's construction (for
``describe()`` enrichment ONLY — no kernel protective predicate here consumes RCL projection
data directly) is a disclosed follow-up, not done in this lane.

Pure module beyond stdlib: ``tos.canonical`` (digest scheme) + ``tos.egress``
(``RestrictiveLatchState``, for the injected latch-state port's return type) + ``tos.protective``
+ ``tos.time`` (``HealthState``, for the injected time-health port's return type). No
``shared.*``, no ``os.environ``, no network I/O, no transport import.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egress import RestrictiveLatchState
from tos.protective import (
    DeRestrictionInputs,
    ProtectiveActionOutcome,
    derestriction_admissible,
    protective_capacity_exhausted,
)
from tos.time import HealthState

__all__ = [
    "ProtectiveActionService",
    "ProtectiveEvidenceRecorder",
    "ProtectiveVerdict",
]

#: The evidence kind this service's sole evidence record is stamped with (plan §2
#: decision 8 "evidence PROTECTIVE_VERDICT").
_PROTECTIVE_VERDICT_KIND = "PROTECTIVE_VERDICT"

#: The exact, deterministic set of kernel facts/predicates this service could NOT
#: establish from a real runtime source (module docstring's own "Honest-source table") —
#: a fixed tuple, never re-derived per call, so a caller / test can pin it exactly.
UNEVALUATED_PROTECTIVE_FACTS: tuple[str, ...] = (
    "reconciled_authoritative_state",
    "critical_input_trust_restored",
    "explicit_safety_authority_decision",
    "protective_capacity_profile",
    "protective_capacity_budget_remaining",
    "protective_classification",
    "mode_permits_protective",
    "replacement_predicates",
)


class ProtectiveEvidenceRecorder(Protocol):
    """The injected ``PROTECTIVE_VERDICT`` evidence sink (module docstring). Mirrors
    :class:`~tos_runtime.safety.monitoring.AlertRecorder`'s own ``(kind, fields) -> None``
    shape exactly, so one evidence-store adapter can serve every safety-mesh-adjacent
    service."""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one evidence entry — never a
        secret / bearer token in ``fields``."""
        ...


@dataclass(frozen=True)
class ProtectiveVerdict:
    """One :meth:`ProtectiveActionService.verdict` evaluation (module docstring).

    Attributes:
        derestriction_admissible: :func:`~tos.protective.derestriction_admissible`'s
            result over this service's real + disclosed-``None`` inputs (always ``False``
            today — module docstring).
        capacity_exhausted: :func:`~tos.protective.protective_capacity_exhausted`'s
            result over the genuinely-absent profile/budget (always ``True`` today —
            module docstring).
        classification: Always ``None`` — :func:`~tos.protective.protective_classification`
            is not called (module docstring); never a fabricated outcome.
        unevaluated: The exact facts/predicates this service could not establish
            (:data:`UNEVALUATED_PROTECTIVE_FACTS`).
        reasons: Deterministic, ordered reason tokens naming every real (non-``None``)
            input that was NOT positively established (empty exactly when
            ``derestriction_admissible`` is ``True`` and ``capacity_exhausted`` is
            ``False``) — mirrors :class:`~tos_runtime.safety.ports.MeshClearance`'s own
            "reasons" contract.
        protective_classification_digest: The canonical digest of this verdict's own
            covered fields (``derestriction_admissible`` / ``capacity_exhausted`` /
            ``classification`` / ``unevaluated``) — what
            :meth:`ProtectiveActionService.protective_classification_digest` returns, and
            what a caller supplies to ``tos_runtime.risk.flow.ActionFlowDecisionInputs
            .protective_classification_digest`` (module docstring's "afg inputs" seam).
    """

    derestriction_admissible: bool | None
    capacity_exhausted: bool | None
    classification: ProtectiveActionOutcome | None
    unevaluated: tuple[str, ...]
    reasons: tuple[str, ...]
    protective_classification_digest: str | None


def _covered_fields(
    inputs: DeRestrictionInputs,
    derestriction: bool | None,
    capacity_exhausted: bool | None,
    classification: ProtectiveActionOutcome | None,
) -> dict[str, Any]:
    """The digest preimage — every field whose change MUST move the digest (mutation M5:
    "the digest must change when the verdict changes"). Folds in the REAL input facts
    (``safety_authority_current`` / ``hard_and_runtime_profile_valid`` /
    ``dominating_halt_or_incident``), not just the two derived kernel-predicate outputs —
    ``derestriction_admissible`` is ``False`` for every reachable combination of those
    three facts today (three of the five §8.5 conjuncts are permanently ``None``,
    module docstring), so digesting only the final booleans would make the digest
    constant across a genuine, real-fact change (exactly the M5 mutation this folds
    in the raw facts to close). ``unevaluated`` is a fixed constant across every call
    of this service, but is still folded in so a future change to that constant (a new
    real source landing) is itself digest-visible."""
    return {
        "safety_authority_current": inputs.safety_authority_current,
        "hard_and_runtime_profile_valid": inputs.hard_and_runtime_profile_valid,
        "dominating_halt_or_incident": inputs.dominating_halt_or_incident,
        "derestriction_admissible": derestriction,
        "capacity_exhausted": capacity_exhausted,
        "classification": None if classification is None else classification.value,
        "unevaluated": list(UNEVALUATED_PROTECTIVE_FACTS),
    }


class ProtectiveActionService:
    """The verdict-only ``tos.protective`` / ``tos.replacement`` surface (module
    docstring). Construction takes only read ports — no policy document, no transport,
    no RCL-mutation capability."""

    def __init__(
        self,
        *,
        latch_state: Callable[[], RestrictiveLatchState],
        incident_clear: Callable[[], bool | None],
        time_health_state: Callable[[], HealthState],
        evidence_recorder: ProtectiveEvidenceRecorder,
        canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    ) -> None:
        """Compose the service over its injected read ports.

        Args:
            latch_state: The item-16 restrictive-latch owner's ``state()``
                (:meth:`~tos_runtime.safety.latch.RestrictiveLatchOwner.state`) —
                feeds ``hard_and_runtime_profile_valid`` (module docstring).
            incident_clear: The SAME per-tick incident-mesh clearance every other W3
                consumer reads (never re-derived independently) — feeds
                ``dominating_halt_or_incident`` (module docstring).
            time_health_state: The Trustworthy Time service's health-state port —
                feeds ``safety_authority_current`` (module docstring).
            evidence_recorder: The ``PROTECTIVE_VERDICT`` evidence sink (module
                docstring).
            canonicalization_version: The registered ``tos.canonical`` scheme version
                used to digest each verdict.
        """
        self._latch_state = latch_state
        self._incident_clear = incident_clear
        self._time_health_state = time_health_state
        self._evidence_recorder = evidence_recorder
        self._scheme = get_scheme(canonicalization_version)

    def _derestriction_inputs(self) -> DeRestrictionInputs:
        """Build :class:`~tos.protective.DeRestrictionInputs` from real ports only,
        leaving every fact without a real source ``None`` (module docstring)."""
        return DeRestrictionInputs(
            reconciled_authoritative_state=None,
            safety_authority_current=self._time_health_state() is HealthState.TRUSTED,
            hard_and_runtime_profile_valid=(
                self._latch_state() is RestrictiveLatchState.CLEAR
            ),
            critical_input_trust_restored=None,
            explicit_safety_authority_decision=None,
            dominating_halt_or_incident=self._incident_clear() is not True,
        )

    def verdict(self) -> ProtectiveVerdict:
        """Evaluate both kernel predicates fresh, record ``PROTECTIVE_VERDICT`` evidence
        once, and return the resulting :class:`ProtectiveVerdict`."""
        inputs = self._derestriction_inputs()
        derestriction = derestriction_admissible(inputs)
        capacity_exhausted = protective_capacity_exhausted(None, budget_remaining=None)
        classification: ProtectiveActionOutcome | None = None

        reasons: list[str] = []
        if inputs.safety_authority_current is not True:
            reasons.append("safety_authority_current")
        if inputs.hard_and_runtime_profile_valid is not True:
            reasons.append("hard_and_runtime_profile_valid")
        if inputs.dominating_halt_or_incident is not False:
            reasons.append("dominating_halt_or_incident")
        if not derestriction:
            reasons.append("derestriction_admissible")
        if capacity_exhausted:
            reasons.append("capacity_exhausted")

        digest = self._scheme.compute_digest(
            _covered_fields(inputs, derestriction, capacity_exhausted, classification)
        )
        result = ProtectiveVerdict(
            derestriction_admissible=derestriction,
            capacity_exhausted=capacity_exhausted,
            classification=classification,
            unevaluated=UNEVALUATED_PROTECTIVE_FACTS,
            reasons=tuple(reasons),
            protective_classification_digest=digest,
        )
        self._evidence_recorder(
            _PROTECTIVE_VERDICT_KIND,
            {
                "derestriction_admissible": result.derestriction_admissible,
                "capacity_exhausted": result.capacity_exhausted,
                "classification": None,
                "unevaluated": list(result.unevaluated),
                "reasons": list(result.reasons),
                "protective_classification_digest": result.protective_classification_digest,
            },
        )
        return result

    def protective_classification_digest(self) -> str | None:
        """The current :class:`ProtectiveVerdict`'s digest — the ``Callable[[], str |
        None]`` a caller supplies to
        ``tos_runtime.risk.flow.ActionFlowGovernor``'s injected
        ``protective_classification_digest_provider`` (module docstring's "afg inputs"
        seam)."""
        return self.verdict().protective_classification_digest

    def describe(self) -> Mapping[str, Any]:
        """Evidence-facing description — no secrets, and an explicit statement that
        this service has zero execution path (module docstring)."""
        verdict = self.verdict()
        return {
            "identity": "protective-action-service-w32-v1",
            "execution_path": "none — verdict-only, no transport/RCL-mutation port",
            "derestriction_admissible": verdict.derestriction_admissible,
            "capacity_exhausted": verdict.capacity_exhausted,
            "classification": None,
            "unevaluated": list(verdict.unevaluated),
            "reasons": list(verdict.reasons),
            "protective_classification_digest": verdict.protective_classification_digest,
        }
