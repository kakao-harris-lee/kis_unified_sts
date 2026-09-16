"""``tos_runtime.marketfeed.snapshot`` — the Critical Input Snapshot issuer (TOS tick-source
wave, plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decisions 2/3/5).

:class:`SnapshotIssuer` turns one :class:`~tos_runtime.marketfeed.ports.RawObservation` into one
kernel-issued :class:`~tos.capsule.CriticalInputSnapshot` — **one observation, one snapshot**
(design #32 §4.1 distinct-as-of-per-bar; this is what makes a distinct as-of yield a distinct
snapshot digest, so per-observation distinctness — the obligation
``tos/tests/marketfeed/test_marketfeed_cis_port.py:46-49`` leaves upstream — is discharged by
construction rather than by a separate check). It never stamps ``FieldState.VALID``: every
declared field's state is **derived** from the loaded :class:`~tos_runtime.marketfeed.policy
.LoadedCriticalInputPolicy` (plan §2 decision 2) — see :func:`_derive_field_state`.

**No transformation lineage.** This wave ships direct observations only (plan §1 비범위 — derived/
indicator values need :class:`~tos.capsule.TransformationLineage` + parent causality, a separate
design). A value with no lineage node inherits ``VALID`` from the kernel's own lineage gate
(``tos/src/tos/marketfeed/value.py:309-311`` — "a value with no lineage node is a *direct*
observation... there is no derivation to be unreproducible about"), which is exactly the shape a
direct observation has, so this module constructs no :class:`~tos.capsule.TransformationLineage`
node at all.

**The ``Observation.mapping`` "primary field" reading (deviation, reported).** ``tos.capsule
.observation.Mapping`` (``tos/src/tos/capsule/observation.py``) carries ONE
``unit``/``scale``/``multiplier``/``sign`` slot per :class:`~tos.capsule.Observation`, but the CIP
declares those four per **field_key** and one observation's payload may carry several
policy-declared keys at once (``tos/tests/marketfeed/_marketfeed_fixtures.py``'s ``one_bar()``
bundles ``close`` + ``session`` under one raw event id). There is no kernel slot to hold more than
one field's mapping. This module resolves the tension by using the **first policy-declared field
(in the policy's own declaration order) actually present in the observation's payload** as the
observation's ``mapping`` source (:func:`_primary_field_spec`) — a deterministic, structurally
derived choice, not a self-reported one, but it is a real interpretation call the plan text did not
spell out for the multi-field case. ``FieldEvaluation`` — the artifact that actually gates
admission per :func:`tos.marketfeed.value.value_field_state` — is unaffected: every declared field
gets its own derived evaluation regardless of which one is "primary" for ``mapping``.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.marketfeed.ports`` only — no
``shared.*``, no network, no clock (the caller supplies ``now_ms``; this module never reads one).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.capsule import (
    AdmissionResult,
    ConsistencyCut,
    CriticalInputSnapshot,
    FieldEvaluation,
    FieldState,
    Observation,
    PolicyRef,
    worst,
)
from tos.capsule.observation import (
    Admission,
    ObservationTime,
    RawRef,
    SourceIdentity,
)
from tos.capsule.observation import (
    Mapping as ObservationMapping,
)
from tos.capsule.snapshot import SnapshotScope
from tos.marketfeed import RawPayloadPreimage, project_scalar
from tos.marketfeed.records import PreimageEntry

from tos_runtime.marketfeed.policy import (
    CriticalInputFieldPolicy,
    LoadedCriticalInputPolicy,
)
from tos_runtime.marketfeed.ports import RawObservation

__all__ = [
    "FieldEvaluationReport",
    "IssuedSnapshot",
    "SnapshotIssuer",
]


@dataclass(frozen=True)
class FieldEvaluationReport:
    """Why one policy-declared field landed at the state it did (module docstring — so tests and
    a future evidence row can read the reason without re-deriving it)."""

    field_key: str
    state: FieldState
    #: ``None`` iff ``state is FieldState.VALID``; otherwise one of ``"absent_from_payload"``,
    #: ``"now_ms_unknown"``, ``"stale"``, ``"unprojectable"``.
    reason: str | None


@dataclass(frozen=True)
class IssuedSnapshot:
    """One issued snapshot plus what a durable store needs to keep it reproducible (plan §2
    decision 3) and what an evidence consumer needs to read why (module docstring)."""

    snapshot: CriticalInputSnapshot
    #: ``raw_event_id -> preimage`` — exactly the one entry this snapshot's single observation
    #: addresses (one observation per snapshot, module docstring).
    preimages: Mapping[str, RawPayloadPreimage]
    field_reports: tuple[FieldEvaluationReport, ...]


def _primary_field_spec(
    policy: LoadedCriticalInputPolicy, payload: RawPayloadPreimage
) -> CriticalInputFieldPolicy | None:
    """The first policy-declared field (declaration order) actually present in ``payload`` — see
    module docstring "primary field" note. ``None`` when the payload carries no declared field.
    """
    for spec in policy.fields:
        if payload.lookup(spec.field_key) is not None:
            return spec
    return None


def _derive_field_state(
    field_key: str,
    spec: CriticalInputFieldPolicy,
    payload: RawPayloadPreimage,
    *,
    now_ms: int | None,
    as_of_ms: int,
) -> tuple[FieldState, str | None]:
    """The worst of three derived checks (plan §2 decision 2): present in this payload, fresh as
    of ``now_ms``, and scalar-projectable — never a declared/constant ``VALID`` (mutation M1).
    """
    token = payload.lookup(field_key)
    if token is None:
        return FieldState.UNKNOWN, "absent_from_payload"
    if now_ms is None:
        # An unestablishable freshness bound is never a satisfied one (module docstring).
        return FieldState.UNKNOWN, "now_ms_unknown"
    if now_ms - as_of_ms > spec.max_age_ms:
        return FieldState.UNKNOWN, "stale"
    value, projection_reason = project_scalar(token)
    if value is None or projection_reason is not None:
        # Reuse the kernel's own projection rule (module docstring) — a value the kernel gate
        # would refuse at publication is not VALID here either.
        return FieldState.UNKNOWN, "unprojectable"
    return FieldState.VALID, None


class SnapshotIssuer:
    """Issues one :class:`~tos.capsule.CriticalInputSnapshot` per
    :class:`~tos_runtime.marketfeed.ports.RawObservation` (module docstring)."""

    def __init__(
        self,
        *,
        policy: LoadedCriticalInputPolicy,
        scheme: CanonicalizationScheme,
        account: str,
    ) -> None:
        self._policy = policy
        self._scheme = scheme
        self._account = account

    def issue(
        self, observation: RawObservation, *, now_ms: int | None
    ) -> IssuedSnapshot:
        """Issue a snapshot covering exactly ``observation`` (module docstring).

        Args:
            observation: The raw observation to snapshot.
            now_ms: The wall-clock reading to evaluate freshness against, or ``None`` when no
                trustworthy time is available (every declared field then derives ``UNKNOWN`` —
                an unestablished bound is never satisfied).

        Returns:
            The issued snapshot, its one preimage, and the per-field derivation report.
        """
        payload = RawPayloadPreimage(
            entries=tuple(
                PreimageEntry(key=key, value=value) for key, value in observation.fields
            )
        )
        payload_digest = self._scheme.compute_digest(payload.as_mapping())

        field_evaluations: list[FieldEvaluation] = []
        field_reports: list[FieldEvaluationReport] = []
        for field_key, spec in self._policy.fields_by_key.items():
            state, reason = _derive_field_state(
                field_key, spec, payload, now_ms=now_ms, as_of_ms=observation.as_of_ms
            )
            field_evaluations.append(
                FieldEvaluation(field_ref=field_key, state=state, blocking=True)
            )
            field_reports.append(
                FieldEvaluationReport(field_key=field_key, state=state, reason=reason)
            )
        aggregate_field_state = worst(
            evaluation.state for evaluation in field_evaluations
        )

        admission_result = (
            AdmissionResult.ADMITTED
            if observation.instrument.strip() and observation.fields
            else AdmissionResult.REJECTED
        )

        primary = _primary_field_spec(self._policy, payload)
        observation_record = Observation(
            source=SourceIdentity(provider=observation.source_id),
            raw=RawRef(
                raw_event_id=observation.raw_event_id, payload_digest=payload_digest
            ),
            time=ObservationTime(
                source_event_time=observation.as_of_ms,
                receipt_trustworthy_time_anchor=observation.received_ms,
            ),
            mapping=ObservationMapping(
                instrument=observation.instrument,
                unit=primary.unit if primary is not None else None,
                scale=primary.scale if primary is not None else None,
                multiplier=primary.multiplier if primary is not None else None,
                sign=primary.sign if primary is not None else None,
            ),
            admission=Admission(result=admission_result),
            field_state=aggregate_field_state,
        )

        snapshot = CriticalInputSnapshot.issue(
            scheme=self._scheme,
            issuer_principal_id=self._policy.issuer_principal_id,
            critical_input_policy=PolicyRef(
                policy_id=self._policy.policy_id,
                policy_generation=self._policy.policy_generation,
                canonical_digest=self._policy.canonical_digest,
            ),
            scope=SnapshotScope(
                environment=self._policy.environment,
                accounts=(self._account,),
                instruments=(observation.instrument,),
                decision_class=self._policy.decision_class,
            ),
            intended_use=self._policy.intended_use,
            consistency_cut=ConsistencyCut(
                cut_id=f"cut-{observation.instrument}-{observation.as_of_ms}"
            ),
            observations=(observation_record,),
            field_evaluations=tuple(field_evaluations),
        )
        assert isinstance(snapshot, CriticalInputSnapshot)

        return IssuedSnapshot(
            snapshot=snapshot,
            preimages={observation.raw_event_id: payload},
            field_reports=tuple(field_reports),
        )
