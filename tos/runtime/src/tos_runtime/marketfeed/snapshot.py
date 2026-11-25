"""``tos_runtime.marketfeed.snapshot`` — the Critical Input Snapshot issuer (TOS tick-source"""

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
    """Why one policy-declared field landed at the state it did (module docstring — so tests and"""

    field_key: str
    state: FieldState
    reason: str | None
    max_age_ms: int


@dataclass(frozen=True)
class IssuedSnapshot:
    """One issued snapshot plus what a durable store needs to keep it reproducible (plan §2"""

    snapshot: CriticalInputSnapshot
    preimages: Mapping[str, RawPayloadPreimage]
    field_reports: tuple[FieldEvaluationReport, ...]


_MAPPING_SLOTS: tuple[str, ...] = ("unit", "scale", "multiplier", "sign")


def _mapping_slot_values(
    policy: LoadedCriticalInputPolicy, payload: RawPayloadPreimage
) -> dict[str, str | None]:
    """Fill each of ``Observation.mapping``'s unit/scale/multiplier/sign slots only when"""
    present_specs = [
        spec for spec in policy.fields if payload.lookup(spec.field_key) is not None
    ]
    slots: dict[str, str | None] = {}
    for slot in _MAPPING_SLOTS:
        values = {getattr(spec, slot) for spec in present_specs}
        slots[slot] = values.pop() if len(values) == 1 else None
    return slots


def _derive_field_state(
    field_key: str,
    spec: CriticalInputFieldPolicy,
    payload: RawPayloadPreimage,
    *,
    now_ms: int | None,
    as_of_ms: int,
) -> tuple[FieldState, str | None]:
    """The worst of three derived checks (plan §2 decision 2): present in this payload, fresh as"""
    token = payload.lookup(field_key)
    if token is None:
        return FieldState.UNKNOWN, "absent_from_payload"
    if now_ms is None:
        return FieldState.UNKNOWN, "now_ms_unknown"
    if now_ms - as_of_ms > spec.max_age_ms:
        return FieldState.UNKNOWN, "stale"
    value, projection_reason = project_scalar(token)
    if value is None or projection_reason is not None:
        return FieldState.UNKNOWN, "unprojectable"
    return FieldState.VALID, None


def _derive_observation_state(
    observation: RawObservation,
) -> tuple[FieldState, AdmissionResult]:
    """Record-level well-formedness only (module docstring "Correction 1") — instrument"""
    well_formed = bool(observation.instrument.strip()) and bool(observation.fields)
    if well_formed:
        return FieldState.VALID, AdmissionResult.ADMITTED
    return FieldState.UNKNOWN, AdmissionResult.REJECTED


class SnapshotIssuer:
    """Issues one :class:`~tos.capsule.CriticalInputSnapshot` per"""

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
        """Issue a snapshot covering exactly ``observation`` (module docstring)."""
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
                FieldEvaluationReport(
                    field_key=field_key,
                    state=state,
                    reason=reason,
                    max_age_ms=spec.max_age_ms,
                )
            )
        record_field_state, admission_result = _derive_observation_state(observation)
        mapping_slots = _mapping_slot_values(self._policy, payload)

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
                unit=mapping_slots["unit"],
                scale=mapping_slots["scale"],
                multiplier=mapping_slots["multiplier"],
                sign=mapping_slots["sign"],
            ),
            admission=Admission(result=admission_result),
            field_state=record_field_state,
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
