"""Runtime owner for the monitor coverage and conformance snapshot.

``MonitoringService.clear`` loads a validated coverage manifest and evaluates
three injected self-observations: evidence-tip progress and continuity,
trustworthy-time health, and unconsumed inbox rows. It delegates coverage and
conformance predicates to ``tos.stm`` and does not author an independent
health verdict. The first evidence-tip observation has unknown continuity
until a prior ``(seq, digest)`` pair exists.

A non-true result emits one ``STM_ALERT`` through the injected recorder.
Recorder failures propagate and are remembered for the next tick, so a
delivery failure cannot be silently treated as healthy. The evidence observer
must exclude this service's own alert rows; otherwise its alerts would reset
the stall detector. Ports remain injected so this module does not depend on
the concrete evidence, time, or engine services.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError
from tos.cur import DimensionKey
from tos.stm import (
    AggregateConformanceResult,
    ContinuousConformanceSnapshot,
    CoverageItem,
    MonitorCoverageManifest,
    MonitorEvaluation,
    NumericInputState,
    TelemetryCriticality,
    conformance_requires_complete_current_valid,
    critical_coverage_complete_or_gap,
)

from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.safety._policy_loader import (
    load_yaml_document,
    require_bool_field,
    require_int_field,
    require_list_field,
    require_mapping_field,
    require_str_field,
)
from tos_runtime.safety.ports import MeshClearance

__all__ = [
    "MonitoringConfigError",
    "EvidenceTipObserver",
    "TimeHealthObserver",
    "InboxUnconsumedObserver",
    "MonotonicClock",
    "AlertRecorder",
    "MonitoringService",
]

#: The code-constant ``owner_identity`` this service stamps (plan §2 decision 1 — an
#: identity is a code constant, never configuration).
_IDENTITY = "monitoring-service-stm-v1"

#: The three fixed obligations this service's self-observations cover (module docstring).
#: A closed catalogue: the config loader refuses a document that does not carry EXACTLY
#: these three ``coverage_items`` keys, so the manifest and the observation code can never
#: silently drift apart.
_OBLIGATION_EVIDENCE_TIP = "evidence-tip-currency"
_OBLIGATION_TIME_HEALTH = "time-service-health"
_OBLIGATION_INBOX_BACKLOG = "inbox-backlog"
_OBLIGATION_REFS: tuple[str, ...] = (
    _OBLIGATION_EVIDENCE_TIP,
    _OBLIGATION_TIME_HEALTH,
    _OBLIGATION_INBOX_BACKLOG,
)

#: Deterministic, fixed-order reason tokens (ports.py "reasons" contract).
_REASON_COVERAGE_GAP = "critical_coverage_complete_or_gap"
_REASON_SNAPSHOT_DISHONEST = "conformance_requires_complete_current_valid"
_REASON_EVIDENCE_TIP_UNKNOWN = "evidence_tip_never_observed"
_REASON_EVIDENCE_TIP_STALL = "evidence_tip_stalled"
_REASON_CONTINUITY_UNESTABLISHED = "source_continuity_unestablished"
_REASON_CONTINUITY_BROKEN = "source_continuity_broken"
_REASON_TIME_UNHEALTHY = "time_health_not_in_healthy_states"
_REASON_INBOX_BACKLOG = "inbox_unconsumed_over_bound"
_REASON_ALERT_DELIVERY_FAILED = "stm_alert_delivery_failed"

#: ``STM_ALERT`` evidence kind (module docstring "STM_ALERT emission").
_EVIDENCE_KIND_STM_ALERT = "STM_ALERT"

_NS_PER_MS = 1_000_000


class MonitoringConfigError(Exception):
    """Raised when the Monitor Coverage Manifest policy document is missing, malformed,
    still carries an unfilled (named-TBD) required field, does not carry exactly the three
    fixed obligations, or fails the kernel record's own schema validation — fail-closed at
    construction, never a lazily-discovered ``None`` inside :meth:`MonitoringService
    .clear`."""


class EvidenceTipObserver(Protocol):
    """Port returning ``(last_seq, last_chain_digest, last_key_generation)``.

    The compose layer must exclude this service's own ``STM_ALERT`` rows.
    """

    def __call__(self) -> tuple[int | None, str, int | None]:
        """Return the evidence store's own ``(last_seq, last_chain_digest,
        last_key_generation)`` tip observation."""
        ...


class TimeHealthObserver(Protocol):
    """Port returning the Trustworthy Time health-state token name."""

    def __call__(self) -> str:
        """Return the Trustworthy Time service's current health-state token name."""
        ...


class InboxUnconsumedObserver(Protocol):
    """Port returning the count of currently-unconsumed inbox rows."""

    def __call__(self) -> int:
        """Return the count of currently-unconsumed inbox rows."""
        ...


class MonotonicClock(Protocol):
    """Port returning the stall detector's monotonic nanosecond clock."""

    def __call__(self) -> int:
        """Return the current monotonic nanosecond count."""
        ...


class AlertRecorder(Protocol):
    """Sink for one ``STM_ALERT`` evidence record."""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one ``STM_ALERT`` evidence
        entry — never a secret / bearer token in ``fields``."""
        ...


@dataclass(frozen=True)
class _Bounds:
    max_evidence_tip_stall_ms: int
    healthy_time_states: tuple[str, ...]
    max_inbox_unconsumed: int


@dataclass(frozen=True)
class _LoadedCoverage:
    manifest: MonitorCoverageManifest
    bounds: _Bounds
    config_path: Path


@dataclass(frozen=True)
class _Observation:
    """One :meth:`MonitoringService.clear` tick's raw self-observation results.

    The same record feeds snapshot construction and reason derivation, so the
    two cannot disagree about what was observed.

    ``freshness_ok`` is ``None`` only when the evidence tip has not been
    observed (``seq is None``). ``continuity_ok`` is ``None`` on the first
    real observation because there is no prior pair to compare against. It is
    left uncomputed when freshness is unknown.
    """

    freshness_ok: bool | None
    continuity_ok: bool | None
    evidence_numeric_state: NumericInputState
    last_seq: int | None
    time_state: str
    time_ok: bool
    unconsumed: int
    inbox_ok: bool


def _require_item_flags(
    raw: dict[str, Any], obligation_ref: str, path: Path
) -> CoverageItem:
    criticality_raw = require_str_field(raw, "criticality", path, MonitoringConfigError)
    try:
        criticality = TelemetryCriticality(criticality_raw)
    except ValueError as exc:
        raise MonitoringConfigError(
            f"{path}: items.{obligation_ref}.criticality {criticality_raw!r} is not a "
            f"valid TelemetryCriticality ({[m.value for m in TelemetryCriticality]!r})"
        ) from exc
    return CoverageItem(
        obligation_ref=obligation_ref,
        scope_dimensions=frozenset(),
        dependency_closure_dimensions=frozenset(),
        restrictive_response_present=require_bool_field(
            raw, "restrictive_response_present", path, MonitoringConfigError
        ),
        alert_path_present=require_bool_field(
            raw, "alert_path_present", path, MonitoringConfigError
        ),
        evidence_path_present=require_bool_field(
            raw, "evidence_path_present", path, MonitoringConfigError
        ),
        currentness_rule_present=require_bool_field(
            raw, "currentness_rule_present", path, MonitoringConfigError
        ),
        closure_1_to_12_complete=require_bool_field(
            raw, "closure_1_to_12_complete", path, MonitoringConfigError
        ),
        excluded=False,
        approved_exclusion_proof_present=None,
        criticality=criticality,
    )


def _load_manifest(body: dict[str, Any], path: Path) -> MonitorCoverageManifest:
    manifest_body = require_mapping_field(body, "manifest", path, MonitoringConfigError)
    items_body = require_mapping_field(body, "items", path, MonitoringConfigError)
    if frozenset(items_body) != frozenset(_OBLIGATION_REFS):
        raise MonitoringConfigError(
            f"{path}: items must carry EXACTLY the three fixed obligations "
            f"{_OBLIGATION_REFS!r} (got {tuple(sorted(items_body))!r}) — this service's "
            "self-observation code only knows how to evaluate these three (module "
            "docstring)"
        )
    coverage_items = tuple(
        _require_item_flags(
            require_mapping_field(items_body, ref, path, MonitoringConfigError),
            ref,
            path,
        )
        for ref in _OBLIGATION_REFS
    )
    try:
        return MonitorCoverageManifest(
            coverage_manifest_id=require_str_field(
                manifest_body, "coverage_manifest_id", path, MonitoringConfigError
            ),
            coverage_generation=require_int_field(
                manifest_body, "coverage_generation", path, MonitoringConfigError
            ),
            coverage_manifest_digest=require_str_field(
                manifest_body, "coverage_manifest_digest", path, MonitoringConfigError
            ),
            policy_digest=require_str_field(
                manifest_body, "policy_digest", path, MonitoringConfigError
            ),
            coverage_items=coverage_items,
            approved_exclusions=(),
            submitted_monitored_assumptions=(),
            is_complete=require_bool_field(
                manifest_body, "is_complete", path, MonitoringConfigError
            ),
            # A score cannot replace item-level closure; this service has no
            # score-based coverage shortcut.
            coverage_score_present=False,
        )
    except ValidationError as exc:
        raise MonitoringConfigError(
            f"{path}: manifest does not satisfy MonitorCoverageManifest — {exc}"
        ) from exc


def _load_bounds(body: dict[str, Any], path: Path) -> _Bounds:
    bounds_body = require_mapping_field(body, "bounds", path, MonitoringConfigError)
    healthy_states_raw = require_list_field(
        bounds_body, "healthy_time_states", path, MonitoringConfigError
    )
    if not healthy_states_raw or not all(
        isinstance(v, str) and v.strip() for v in healthy_states_raw
    ):
        raise MonitoringConfigError(
            f"{path}: bounds.healthy_time_states must be a non-empty list of non-blank "
            f"strings (got {healthy_states_raw!r})"
        )
    return _Bounds(
        max_evidence_tip_stall_ms=require_int_field(
            bounds_body, "max_evidence_tip_stall_ms", path, MonitoringConfigError
        ),
        healthy_time_states=tuple(healthy_states_raw),
        max_inbox_unconsumed=require_int_field(
            bounds_body, "max_inbox_unconsumed", path, MonitoringConfigError
        ),
    )


def _load_coverage(path: Path) -> _LoadedCoverage:
    raw = load_yaml_document(path, MonitoringConfigError)
    body = require_mapping_field(raw, "coverage", path, MonitoringConfigError)
    manifest = _load_manifest(body, path)
    bounds = _load_bounds(body, path)
    return _LoadedCoverage(manifest=manifest, bounds=bounds, config_path=path)


def _applicable_obligations(manifest: MonitorCoverageManifest) -> frozenset[str]:
    return frozenset(
        item.obligation_ref
        for item in manifest.coverage_items
        if item.obligation_ref is not None
    )


class MonitoringService:
    """The MONITORING :class:`~tos_runtime.safety.ports.SafetyMeshService` (module
    docstring). Construction loads and validates the Monitor Coverage Manifest policy
    document — a missing / still-null / schema-invalid / wrong-obligation-set document
    refuses construction outright (never a ``None`` service instance)."""

    def __init__(
        self,
        *,
        config_path: Path,
        evidence_tip_observer: EvidenceTipObserver,
        time_health_observer: TimeHealthObserver,
        inbox_unconsumed_observer: InboxUnconsumedObserver,
        monotonic_ns: MonotonicClock,
        evidence_recorder: AlertRecorder,
    ) -> None:
        """Load + validate the Monitor Coverage Manifest policy document, fail-closed.

        Args:
            config_path: Path to a policy YAML document (top-level key ``coverage``,
                carrying ``manifest`` + ``items`` + ``bounds`` — see
                ``tos/runtime/config/monitor_coverage.example.yaml``).
            evidence_tip_observer: The evidence-tip self-observation port.
            time_health_observer: The Trustworthy Time health-state port.
            inbox_unconsumed_observer: The unconsumed-inbox count port.
            monotonic_ns: The stall detector's monotonic clock.
            evidence_recorder: The ``STM_ALERT`` evidence sink.

        Raises:
            MonitoringConfigError: The file is missing, unreadable, not valid YAML, not a
                mapping, missing a required field, still null (named-TBD), does not carry
                exactly the three fixed obligations, or fails the kernel record's own
                schema validation.
        """
        self._docs = _load_coverage(config_path)
        self._applicable_obligations = _applicable_obligations(self._docs.manifest)
        self._evidence_tip_observer = evidence_tip_observer
        self._time_health_observer = time_health_observer
        self._inbox_unconsumed_observer = inbox_unconsumed_observer
        self._monotonic_ns = monotonic_ns
        self._evidence_recorder = evidence_recorder

        # Last observed sequence and the monotonic timestamp at which it last
        # changed. This is internal staleness memory.
        self._evidence_tip_last_seq: int | None = None
        self._evidence_tip_last_advance_ns: int | None = None
        # Raw previous (seq, chain_digest), updated on every observation. A
        # continuity break is a mismatch between sequence and digest movement.
        self._continuity_last_seq: int | None = None
        self._continuity_last_chain_digest: str | None = None
        # The previous STM_ALERT delivery failure, cleared after a successful
        # subsequent delivery attempt.
        self._last_delivery_failure: str | None = None
        self._snapshot_generation = 0

    @property
    def identity(self) -> str:
        return _IDENTITY

    @property
    def dimension_key(self) -> DimensionKey:
        return DimensionKey.MONITORING

    def _observe(self, now_ns: int) -> _Observation:
        """Read each self-observation port exactly once for this tick."""
        seq, chain_digest, _key_generation = self._evidence_tip_observer()

        if seq is None:
            # Never observed: this is a gap, not an unknown. Continuity is
            # left unjudged because the gap already covers this tick.
            freshness_ok: bool | None = None
            continuity_ok: bool | None = None
            evidence_numeric_state = NumericInputState.MISSING_SAMPLE
        else:
            if seq != self._evidence_tip_last_seq:
                self._evidence_tip_last_seq = seq
                self._evidence_tip_last_advance_ns = now_ns
            assert self._evidence_tip_last_advance_ns is not None
            stall_ms = (now_ns - self._evidence_tip_last_advance_ns) // _NS_PER_MS
            freshness_ok = stall_ms <= self._docs.bounds.max_evidence_tip_stall_ms
            evidence_numeric_state = NumericInputState.WELL_FORMED

            if self._continuity_last_seq is None:
                # First real observation: there is no prior pair to compare.
                continuity_ok = None
            else:
                seq_advanced = seq > self._continuity_last_seq
                seq_regressed = seq < self._continuity_last_seq
                digest_changed = chain_digest != self._continuity_last_chain_digest
                # A regression is always a break; otherwise "advanced" and "digest
                # changed" must agree (both, an ordinary append; neither, an idle tick) —
                # disagreement (an append with no digest movement, or a digest movement
                # with no append) is exactly a torn/rewritten chain.
                continuity_ok = (
                    False if seq_regressed else (seq_advanced == digest_changed)
                )
            self._continuity_last_seq = seq
            self._continuity_last_chain_digest = chain_digest

        time_state = self._time_health_observer()
        time_ok = time_state in self._docs.bounds.healthy_time_states
        unconsumed = self._inbox_unconsumed_observer()
        inbox_ok = unconsumed <= self._docs.bounds.max_inbox_unconsumed

        return _Observation(
            freshness_ok=freshness_ok,
            continuity_ok=continuity_ok,
            evidence_numeric_state=evidence_numeric_state,
            last_seq=self._evidence_tip_last_seq,
            time_state=time_state,
            time_ok=time_ok,
            unconsumed=unconsumed,
            inbox_ok=inbox_ok,
        )

    def _build_snapshot(self, obs: _Observation) -> ContinuousConformanceSnapshot:
        self._snapshot_generation += 1

        active_violations: list[str] = []
        active_unknowns: list[str] = []
        active_gaps: list[str] = []

        if obs.freshness_ok is None:
            active_gaps.append(_OBLIGATION_EVIDENCE_TIP)
        else:
            if obs.freshness_ok is False:
                active_violations.append(_OBLIGATION_EVIDENCE_TIP)
            if obs.continuity_ok is None:
                active_unknowns.append(_OBLIGATION_EVIDENCE_TIP)
            elif obs.continuity_ok is False:
                active_violations.append(_OBLIGATION_EVIDENCE_TIP)

        if obs.time_ok is False:
            active_violations.append(_OBLIGATION_TIME_HEALTH)
        if obs.inbox_ok is False:
            active_violations.append(_OBLIGATION_INBOX_BACKLOG)

        delivery_failures = (
            (self._last_delivery_failure,) if self._last_delivery_failure else ()
        )

        if active_gaps or active_unknowns:
            aggregate_result = AggregateConformanceResult.UNKNOWN
        elif active_violations or delivery_failures:
            aggregate_result = AggregateConformanceResult.NON_CONFORMING
        else:
            aggregate_result = AggregateConformanceResult.CONFORMING

        def _eval_result(values: tuple[bool | None, ...]) -> AggregateConformanceResult:
            if any(v is None for v in values):
                return AggregateConformanceResult.UNKNOWN
            if any(v is False for v in values):
                return AggregateConformanceResult.NON_CONFORMING
            return AggregateConformanceResult.CONFORMING

        manifest = self._docs.manifest
        evaluations = (
            MonitorEvaluation(
                evaluator_digest="stm-evaluator-evidence-tip-v1",
                canonical_input_digest=f"last_seq={obs.last_seq!r}",
                result=_eval_result((obs.freshness_ok, obs.continuity_ok)),
                numeric_input_state=obs.evidence_numeric_state,
            ),
            MonitorEvaluation(
                evaluator_digest="stm-evaluator-time-health-v1",
                canonical_input_digest=f"health_state={obs.time_state!r}",
                result=_eval_result((obs.time_ok,)),
                numeric_input_state=NumericInputState.WELL_FORMED,
            ),
            MonitorEvaluation(
                evaluator_digest="stm-evaluator-inbox-backlog-v1",
                canonical_input_digest=f"unconsumed={obs.unconsumed!r}",
                result=_eval_result((obs.inbox_ok,)),
                numeric_input_state=NumericInputState.WELL_FORMED,
            ),
        )

        return ContinuousConformanceSnapshot(
            snapshot_id=f"{manifest.coverage_manifest_id}-snapshot",
            snapshot_generation=self._snapshot_generation,
            monitor_generation=manifest.coverage_generation,
            policy_digest=manifest.policy_digest,
            critical_telemetry_manifest_digest=manifest.coverage_manifest_digest,
            coverage_manifest_digest=manifest.coverage_manifest_digest,
            scope=manifest.coverage_manifest_id,
            owner_epoch=self.identity,
            monitor_results=evaluations,
            source_continuity_present=obs.continuity_ok,
            active_violations=tuple(active_violations),
            active_unknowns=tuple(active_unknowns),
            active_gaps=tuple(active_gaps),
            active_suppressions=(),
            delivery_failures=delivery_failures,
            aggregate_result=aggregate_result,
        )

    def _reasons_from_observation(self, obs: _Observation) -> list[str]:
        reasons: list[str] = []
        if obs.freshness_ok is None:
            reasons.append(_REASON_EVIDENCE_TIP_UNKNOWN)
        else:
            if obs.freshness_ok is False:
                reasons.append(_REASON_EVIDENCE_TIP_STALL)
            if obs.continuity_ok is None:
                reasons.append(_REASON_CONTINUITY_UNESTABLISHED)
            elif obs.continuity_ok is False:
                reasons.append(_REASON_CONTINUITY_BROKEN)
        if obs.time_ok is False:
            reasons.append(_REASON_TIME_UNHEALTHY)
        if obs.inbox_ok is False:
            reasons.append(_REASON_INBOX_BACKLOG)
        if self._last_delivery_failure is not None:
            reasons.append(_REASON_ALERT_DELIVERY_FAILED)
        return reasons

    def clear(self) -> MeshClearance:
        """The deferred-item / Coordinator verdict (module docstring)."""
        reasons: list[str] = []

        coverage_ok = critical_coverage_complete_or_gap(
            self._docs.manifest,
            self._applicable_obligations,
            frozenset(),
            frozenset(),
        )
        if coverage_ok is not True:
            reasons.append(_REASON_COVERAGE_GAP)

        obs = self._observe(self._monotonic_ns())
        reasons.extend(self._reasons_from_observation(obs))
        snapshot = self._build_snapshot(obs)

        honest = conformance_requires_complete_current_valid(snapshot)
        if honest is not True:
            reasons.append(_REASON_SNAPSHOT_DISHONEST)

        if coverage_ok is not True or honest is not True:
            overall: bool | None = False
        elif snapshot.aggregate_result is AggregateConformanceResult.CONFORMING:
            overall = True
        elif snapshot.aggregate_result is AggregateConformanceResult.UNKNOWN:
            overall = None
        else:
            overall = False

        if overall is True:
            reasons = []

        clearance = MeshClearance(
            identity=self.identity, clear=overall, reasons=tuple(reasons)
        )
        if overall is not True:
            try:
                self._evidence_recorder(
                    _EVIDENCE_KIND_STM_ALERT,
                    {
                        "identity": self.identity,
                        "clear": overall,
                        "reasons": clearance.reasons,
                        "aggregate_result": (
                            snapshot.aggregate_result.value
                            if snapshot.aggregate_result is not None
                            else None
                        ),
                    },
                )
            except Exception as exc:
                # Propagate the failure now and expose it on the next tick.
                self._last_delivery_failure = (
                    f"{_EVIDENCE_KIND_STM_ALERT}_delivery_failed: {exc!r}"
                )
                raise
            else:
                self._last_delivery_failure = None
        else:
            self._last_delivery_failure = None
        return clearance

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for MONITORING (module docstring).
        ``restrictive_floor`` is ``0`` — a **deliberate** statement, not an invented
        default: Phase 5 has no floor-governance runtime yet (the same "an owner
        reporting 0 is that owner's own choice" discipline
        :class:`~tos_runtime.currentness.vector.DimensionReport`'s own docstring
        states)."""
        return DimensionReport(
            bound_generation=self._docs.manifest.coverage_generation,
            positively_established=self.clear().clear is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy document — names,
        generations, and bounds only; never a secret / bearer token
        (:class:`~tos_runtime.safety.ports.SafetyMeshService.describe` contract)."""
        manifest = self._docs.manifest
        bounds = self._docs.bounds
        return {
            "identity": self.identity,
            "config_path": str(self._docs.config_path),
            "coverage_manifest_id": manifest.coverage_manifest_id,
            "coverage_generation": manifest.coverage_generation,
            "obligation_refs": sorted(self._applicable_obligations),
            "max_evidence_tip_stall_ms": bounds.max_evidence_tip_stall_ms,
            "healthy_time_states": list(bounds.healthy_time_states),
            "max_inbox_unconsumed": bounds.max_inbox_unconsumed,
        }
