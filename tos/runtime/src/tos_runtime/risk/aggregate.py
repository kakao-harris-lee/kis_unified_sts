"""``AggregateRiskService`` — runtime realization of the Aggregate Risk Authority"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from tos.are import (
    AdverseScenarioKind,
    AdverseScenarioSet,
    AggregateRiskDecision,
    AggregateRiskPolicy,
    AggregateRiskStateSnapshot,
    ProjectedCell,
    RiskDecisionResult,
    RiskScopeKind,
    adverse_increment,
    envelope_bound_not_enlarged,
    risk_decision,
    snapshot_scope_complete,
)
from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    ArtifactIntegrityError,
    CanonicalizationScheme,
    derive_id,
    get_scheme,
)
from tos.engine.records import InstrumentKey
from tos.rcl import CapacityComponent, CapacityVector, aggregate_usage

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    ScopeReservation,
    outstanding_reservations,
)

__all__ = [
    "AggregateRiskConfigError",
    "AggregateRiskDecisionInputs",
    "AggregateRiskService",
    "load_adverse_scenario_set",
    "load_required_scenario_kinds",
]

_EVIDENCE_KIND_SNAPSHOT = "ARE_SNAPSHOT"
_EVIDENCE_KIND_DECISION = "ARE_DECISION"

_TBD_STR = "TBD"


class AggregateRiskConfigError(Exception):
    """Raised when the ``AdverseScenarioSet`` / coverage-floor config is"""


def _load_raw_mapping(path: Path) -> dict[str, Any]:
    """Read + parse ``path`` into a mapping (shared by both loaders below)."""
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise AggregateRiskConfigError(f"cannot read {path}: {exc}") from exc
    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise AggregateRiskConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise AggregateRiskConfigError(
            f"{path} must parse to a mapping (got {type(raw).__name__})"
        )
    return raw


def _parse_scenario_kinds(
    path: Path, raw: Any, *, field_name: str
) -> tuple[AdverseScenarioKind, ...]:
    """Parse a list of ``AdverseScenarioKind`` member names, fail-closed."""
    if not raw:
        return ()
    try:
        return tuple(AdverseScenarioKind(kind) for kind in raw)
    except ValueError as exc:
        raise AggregateRiskConfigError(
            f"{path}: {field_name} has an unrecognized AdverseScenarioKind member: {exc}"
        ) from exc


def load_adverse_scenario_set(
    path: Path, *, scheme: CanonicalizationScheme | None = None
) -> AdverseScenarioSet:
    """Load + issue the :class:`~tos.are.AdverseScenarioSet` from ``path``."""
    scheme = scheme or get_scheme(EV_L1_PROVISIONAL_VERSION)
    raw = _load_raw_mapping(path)
    covered = _parse_scenario_kinds(
        path, raw.get("covered_scenario_kinds"), field_name="covered_scenario_kinds"
    )
    for field_name in ("scenario_set_id", "policy_binding_id", "evidence_package_ref"):
        if raw.get(field_name) == _TBD_STR:
            raise AggregateRiskConfigError(
                f"{path}: {field_name!r} is still the template placeholder {_TBD_STR!r} — "
                "operator-fill before activation, never a value this loader treats as concrete"
            )
    try:
        scenario_set = AdverseScenarioSet.issue(
            scheme=scheme,
            scenario_set_id=raw.get("scenario_set_id"),
            scenario_set_generation=raw.get("scenario_set_generation"),
            policy_binding_id=raw.get("policy_binding_id"),
            covered_scenario_kinds=covered,
            evidence_package_ref=raw.get("evidence_package_ref"),
        )
    except (ArtifactIntegrityError, ValidationError) as exc:
        raise AggregateRiskConfigError(
            f"{path}: AdverseScenarioSet cannot be issued from this config (a "
            f"required covered field is still null/named-TBD, or malformed) — "
            f"refusing to start: {exc}"
        ) from exc
    assert isinstance(scenario_set, AdverseScenarioSet)
    return scenario_set


def load_required_scenario_kinds(path: Path) -> frozenset[AdverseScenarioKind]:
    """Load the injected adverse-scenario min-coverage floor from ``path``."""
    raw = _load_raw_mapping(path)
    required = raw.get("required_scenario_kinds")
    if not required:
        raise AggregateRiskConfigError(
            f"{path}: required_scenario_kinds is null/empty — an empty coverage "
            "floor always fails tos.are.adverse_increment closed (§11/§4.7); "
            "refusing to start"
        )
    return frozenset(
        _parse_scenario_kinds(path, required, field_name="required_scenario_kinds")
    )


@dataclass(frozen=True)
class AggregateRiskDecisionInputs:
    """Every injected witness :func:`tos.are.risk_decision` needs beyond what"""

    cells: tuple[ProjectedCell, ...]
    required_scenario_kinds: frozenset[AdverseScenarioKind]
    applicable_risk_scopes: tuple[str, ...]
    all_fields_attributed: bool | None
    required_scopes: frozenset[RiskScopeKind]
    numerically_safe: RiskDecisionResult | bool | None
    valuation_ok: bool | None
    injected_envelope_max: CapacityVector | None
    limit_source_is_injected_envelope: bool | None
    effective_limit: CapacityVector | None = None
    policy: AggregateRiskPolicy | None = None
    grant_identity: str | None = None
    effect_digest: str | None = None
    lineage_ref: str | None = None
    reason_context: dict[str, Any] = field(default_factory=dict)


class AggregateRiskService:
    """Runtime realization of ARA snapshot derivation + decide (module docstring)."""

    def __init__(
        self,
        projection: ReservationProjectionReader,
        scenario_set: AdverseScenarioSet,
        evidence: EvidenceAppendPort,
        *,
        canonicalization_version: str = EV_L1_PROVISIONAL_VERSION,
    ) -> None:
        """Compose the service over its injected ports."""
        self._projection = projection
        self._scenario_set = scenario_set
        self._evidence = evidence
        self._scheme = get_scheme(canonicalization_version)
        self._snapshot_seq = 0

    @property
    def scenario_set(self) -> AdverseScenarioSet:
        return self._scenario_set

    def snapshot(
        self,
        key: InstrumentKey,
        *,
        snapshot_generation: int,
        required_scopes: frozenset[RiskScopeKind],
        all_fields_attributed: bool | None,
        lineage_ref: str | None = None,
    ) -> AggregateRiskStateSnapshot:
        """Derive an :class:`~tos.are.AggregateRiskStateSnapshot` from the RCL"""
        return self._issue_snapshot(
            key,
            snapshot_generation=snapshot_generation,
            required_scopes=required_scopes,
            all_fields_attributed=all_fields_attributed,
            lineage_ref=lineage_ref,
        )[0]

    def _scope_usage(
        self, outstanding: tuple[ScopeReservation, ...]
    ) -> tuple[CapacityVector, tuple[str, ...]]:
        """The dimension-wise usage of ``outstanding`` and the ids of the rows that carry no"""
        recorded: list[CapacityVector] = []
        unrecorded: list[str] = []
        for row in outstanding:
            vector = self._projection.reservation_committed_vector(row.reservation_id)
            if vector is None:
                unrecorded.append(row.reservation_id)
            else:
                recorded.append(vector)
        usage = aggregate_usage(recorded)
        if unrecorded:
            usage = CapacityVector(
                components=tuple(
                    CapacityComponent(dimension_id=dimension, magnitude=None)
                    for dimension in usage.dimension_ids()
                )
            )
        return usage, tuple(unrecorded)

    def _issue_snapshot(
        self,
        key: InstrumentKey,
        *,
        snapshot_generation: int,
        required_scopes: frozenset[RiskScopeKind],
        all_fields_attributed: bool | None,
        lineage_ref: str | None,
    ) -> tuple[AggregateRiskStateSnapshot, bool | None]:
        """:meth:`snapshot`'s body; also returns the attribution :meth:`decide` must judge"""
        rows = self._projection.scope_reservations(key)
        outstanding = outstanding_reservations(rows)
        last_seq = max((row.last_seq for row in rows), default=None)
        committed_vector, unrecorded = self._scope_usage(outstanding)
        attributed = False if unrecorded else all_fields_attributed
        self._snapshot_seq += 1
        cut_digest = self._scheme.compute_digest(
            {
                "account": key.account,
                "instrument": key.instrument,
                "last_seq": last_seq,
                "snapshot_generation": snapshot_generation,
                "ordinal": self._snapshot_seq,
            }
        )
        snapshot = AggregateRiskStateSnapshot.issue(
            scheme=self._scheme,
            snapshot_id=derive_id("are-snapshot", cut_digest),
            snapshot_generation=snapshot_generation,
            consistency_cut_identity=derive_id("are-cut", cut_digest),
            covered_scopes=tuple(sorted(required_scopes, key=lambda s: s.value)),
            conservative_current_usage=committed_vector,
            lineage_ref=lineage_ref,
        )
        assert isinstance(snapshot, AggregateRiskStateSnapshot)
        self._evidence.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_digest": snapshot.canonical_digest,
                "instrument_scope": {
                    "account": key.account,
                    "instrument": key.instrument,
                },
                "outstanding_reservations": [
                    {"reservation_id": row.reservation_id, "state": row.state.value}
                    for row in outstanding
                ],
                "unrecorded_vector_reservations": list(unrecorded),
                "all_fields_attributed": attributed,
            },
            kind=_EVIDENCE_KIND_SNAPSHOT,
            record_class=_EVIDENCE_KIND_SNAPSHOT,
        )
        return snapshot, attributed

    def decide(
        self,
        key: InstrumentKey,
        inputs: AggregateRiskDecisionInputs,
        *,
        snapshot_generation: int,
        decision_generation: int,
    ) -> AggregateRiskDecision:
        """Prepare :func:`tos.are.risk_decision`'s witnesses via the other"""
        snapshot, attributed = self._issue_snapshot(
            key,
            snapshot_generation=snapshot_generation,
            required_scopes=inputs.required_scopes,
            all_fields_attributed=inputs.all_fields_attributed,
            lineage_ref=inputs.lineage_ref,
        )
        snapshot_complete = snapshot_scope_complete(
            snapshot,
            inputs.required_scopes,
            all_fields_attributed=attributed,
        )
        projection = adverse_increment(
            list(inputs.cells),
            self._scenario_set,
            required_scenario_kinds=inputs.required_scenario_kinds,
        )
        effective_limit = (
            inputs.effective_limit
            if inputs.effective_limit is not None
            else CapacityVector()
        )
        envelope_not_enlarged = envelope_bound_not_enlarged(
            decision_effective_limit=effective_limit,
            injected_envelope_max=inputs.injected_envelope_max,
            limit_source_is_injected_envelope=inputs.limit_source_is_injected_envelope,
        )
        decision_digest_seed = self._scheme.compute_digest(
            {
                "account": key.account,
                "instrument": key.instrument,
                "decision_generation": decision_generation,
                "snapshot_digest": snapshot.canonical_digest,
                "projection_result": projection.result.value,
            }
        )
        decision_id = derive_id("are-decision", decision_digest_seed)
        decision = risk_decision(
            projection=projection,
            snapshot=snapshot,
            applicable_risk_scopes=inputs.applicable_risk_scopes,
            snapshot_complete=snapshot_complete,
            numerically_safe=inputs.numerically_safe,
            valuation_ok=inputs.valuation_ok,
            envelope_not_enlarged=envelope_not_enlarged,
            decision_id=decision_id,
            decision_generation=decision_generation,
            scheme=self._scheme,
            policy=inputs.policy,
            scenario_set=self._scenario_set,
            effective_limit=effective_limit,
            grant_identity=inputs.grant_identity,
            effect_digest=inputs.effect_digest,
        )
        self._evidence.append(
            {
                "decision_id": decision.decision_id,
                "decision_digest": decision.canonical_digest,
                "result": None if decision.result is None else decision.result.value,
            },
            kind=_EVIDENCE_KIND_DECISION,
            record_class=_EVIDENCE_KIND_DECISION,
        )
        return decision
