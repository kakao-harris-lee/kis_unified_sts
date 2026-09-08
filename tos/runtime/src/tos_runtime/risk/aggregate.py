"""``AggregateRiskService`` — runtime realization of the Aggregate Risk Authority
(ARA) snapshot derivation + ``risk_decision`` composition (design #40 §5 order 5
item 1; slice plan §2 item 1).

**This service does not judge.** ``snapshot()`` reads the RCL reservation
projection (``tos_runtime.rcl.projection.ReservationProjectionReader``) and
:meth:`decide` prepares :func:`tos.are.risk_decision`'s boolean witnesses by
calling the *other* ``tos.are`` §5 predicates (:func:`tos.are.snapshot_scope_complete`
/ :func:`tos.are.adverse_increment` / :func:`tos.are.envelope_bound_not_enlarged`)
— never computing a boolean itself — and then calls
:func:`tos.are.risk_decision` exactly once for the final verdict (the
``tos_runtime.authority.stages.IndependentApprovalStage`` precedent: the stage
routes inputs into a kernel judgement call, it never judges).

**Reported gap: no per-dimension usage magnitude in the landed RCL projection.**
:class:`~tos_runtime.rcl.projection.ReservationProjectionReader` (lane M,
already landed) tracks only :class:`~tos.rcl.CapacityState` per reservation —
not a :class:`~tos.rcl.CapacityVector` magnitude. So
:meth:`AggregateRiskService.snapshot`'s ``conservative_current_usage`` field
cannot be *derived* from the ledger and stays the empty ``CapacityVector()``
(zero declared dimensions — a legitimate, non-invented value; are's own
``AggregateRiskStateSnapshot`` does not require it non-empty,
``tos/src/tos/are/records.py`` ``_REQUIRED_COVERED``). The per-cell magnitudes
:func:`tos.are.adverse_increment` needs (:class:`~tos.are.ProjectedCell`) are
Phase-0 / broker-capability-profile valuation inputs this slice does not own
either way (design #13 §4 non-scope) — they arrive via the caller-injected
:class:`AggregateRiskDecisionInputs`, never computed here. A future kernel/
runtime change that persists committed adverse-increment vectors on the
``reservations`` table (``tos_runtime/rcl/schema.py``, out of this lane's
write surface) would let a later revision populate this field from the ledger
instead of leaving it empty; that change is reported, not made here.

**Single-node quorum honesty (R-RCL-F0).** This service claims no quorum
certificate — see ``RESIDUAL-RISK-REGISTER-002`` R-RCL-F0 and
``tos_runtime.rcl.log.SqliteCommitLog``'s own module docstring for the
single-writer-epoch fencing discipline this service reads through
(:class:`~tos_runtime.rcl.projection.ReservationProjectionReader`).

**Time gate.** Callers (``tos_runtime.risk.ledger_stages.AggregateRiskDecisionStage``)
are responsible for refusing to admit new risk unless the injected
``TrustworthyTimeService.current_snapshot()`` reports
``tos.time.state_permits_new_normal_risk(snapshot.health_state) is True`` — this
service itself holds no time reference (module docstring's own "이 서비스가
만족하는 장애 계약" convention: the time gate is a cross-cutting Stage concern,
not an ``AggregateRiskService``-local one, since steps 6, 7, and 9 all need it
identically; see ``ledger_stages._time_gate``).

Firewall: stdlib + ``pydantic`` (transitively) + ``pyyaml`` + ``tos.are`` /
``tos.canonical`` / ``tos.engine.records`` (``InstrumentKey`` only) / ``tos.rcl``
(``CapacityVector`` only) + ``tos_runtime.evidence`` (``EvidenceAppendPort`` seam)
+ ``tos_runtime.rcl`` (``ReservationProjectionReader`` seam) only (R1 allowlist).
No ``tos_runtime.authority`` / ``tos_runtime.currentness`` / ``tos_runtime.release``
import (slice plan §5 cross-lane isolation) — a future composition root
injects any cross-lane fact this service needs as a plain argument.
"""

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
from tos.rcl import CapacityVector

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.rcl.projection import ReservationProjectionReader

__all__ = [
    "AggregateRiskConfigError",
    "AggregateRiskDecisionInputs",
    "AggregateRiskService",
    "load_adverse_scenario_set",
    "load_required_scenario_kinds",
]

_EVIDENCE_KIND_SNAPSHOT = "ARE_SNAPSHOT"
_EVIDENCE_KIND_DECISION = "ARE_DECISION"


class AggregateRiskConfigError(Exception):
    """Raised when the ``AdverseScenarioSet`` / coverage-floor config is
    missing, malformed, or carries an unfilled (missing/null) required value —
    fail-closed at load (CLAUDE.md "configuration-driven only" + slice plan §2
    item 1 "값 null=named-TBD → 서비스 기동 거부")."""


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
    """Load + issue the :class:`~tos.are.AdverseScenarioSet` from ``path``.

    Reuses the kernel's own ``_REQUIRED_COVERED`` enforcement
    (``AdverseScenarioSet.issue`` -> ``DigestBoundArtifact.missing_required_fields``)
    rather than re-deriving a null-check: a still-``null`` (named-TBD)
    ``scenario_set_generation`` makes ``.issue`` itself raise
    :class:`~tos.canonical.ArtifactIntegrityError`, which this function
    re-raises as :class:`AggregateRiskConfigError` (fail-closed startup
    refusal, slice plan §2 item 1).

    Args:
        path: The YAML config file (see ``tos/runtime/config/risk.example.yaml``).
        scheme: The registered canonicalization scheme (defaults to the
            provisional EV-L1 scheme every other runtime module uses).

    Returns:
        The issued, digest-verified :class:`~tos.are.AdverseScenarioSet`.

    Raises:
        AggregateRiskConfigError: The file is unreadable/malformed, or the
            scenario set cannot be issued (a required covered field is still
            null).
    """
    scheme = scheme or get_scheme(EV_L1_PROVISIONAL_VERSION)
    raw = _load_raw_mapping(path)
    covered = _parse_scenario_kinds(
        path, raw.get("covered_scenario_kinds"), field_name="covered_scenario_kinds"
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
        # A model-validator ArtifactIntegrityError (a ValueError subclass, see
        # tos.canonical._base's own docstring) raised inside pydantic
        # construction surfaces to the caller as pydantic.ValidationError, not
        # the original exception type — both are caught here.
        raise AggregateRiskConfigError(
            f"{path}: AdverseScenarioSet cannot be issued from this config (a "
            f"required covered field is still null/named-TBD, or malformed) — "
            f"refusing to start: {exc}"
        ) from exc
    assert isinstance(scenario_set, AdverseScenarioSet)
    return scenario_set


def load_required_scenario_kinds(path: Path) -> frozenset[AdverseScenarioKind]:
    """Load the injected adverse-scenario min-coverage floor from ``path``.

    An empty/absent floor always fails :func:`tos.are.adverse_increment` closed
    anyway (§11/§4.7 "an empty ... floor fails closed"), so this loader
    surfaces the same fact earlier and louder, at startup — the
    ``tos_runtime.time.config`` precedent.

    Raises:
        AggregateRiskConfigError: The floor is missing/empty, or names an
            unrecognized ``AdverseScenarioKind`` member.
    """
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
    """Every injected witness :func:`tos.are.risk_decision` needs beyond what
    :meth:`AggregateRiskService.snapshot` derives from the RCL projection.

    None of these are computable from the landed RCL commit log — valuation /
    numerical-safety / envelope witnesses are Phase-0 / broker-capability-
    profile concerns this slice does not own (design #13 §4 non-scope,
    module docstring). A caller (the
    ``tos_runtime.risk.ledger_stages.AggregateRiskDecisionStage`` inputs
    provider) supplies them; their absence is ``None`` — UNKNOWN, never
    assumed positive.
    """

    cells: tuple[ProjectedCell, ...]
    required_scenario_kinds: frozenset[AdverseScenarioKind]
    applicable_risk_scopes: tuple[str, ...]
    all_fields_attributed: bool | None
    required_scopes: frozenset[RiskScopeKind]
    numerically_safe: RiskDecisionResult | bool
    valuation_ok: bool
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
        """Compose the service over its injected ports.

        Args:
            projection: The read-only RCL reservation projection
                (``tos_runtime.rcl.projection.ReservationProjectionReader``).
            scenario_set: The issued :class:`~tos.are.AdverseScenarioSet` (see
                :func:`load_adverse_scenario_set` — refuses at load time if
                any required config value is still null).
            evidence: The durable append port every snapshot/decision is
                evidenced through (``decision_id`` and ``canonical_digest`` are
                appended as separate, orthogonal fields — never conflated —
                per are's own ``id != f(digest)`` identity discipline).
            canonicalization_version: The registered ``tos.canonical`` scheme
                version used to digest every issued snapshot/decision.
        """
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
        """Derive an :class:`~tos.are.AggregateRiskStateSnapshot` from the RCL
        reservation projection (module docstring — no self-aggregation).

        ``consistency_cut_identity`` is content-addressed from the
        projection's own last-committed-seq observation for ``key`` (never a
        clock, never a counter that could collide across a restart —
        ``tos.engine.sequencer.build_attempt_request``'s own "no uuid4, no
        timestamp nonce" discipline). ``covered_scopes`` is recorded as the
        caller's injected ``required_scopes`` *only after* the read below
        succeeds — a raised exception here (RCL log file inaccessible) is
        never silently read as "covers nothing"; it propagates so the caller
        (a ``Stage``) maps it to ``UNKNOWN`` (fail-closed, never a denial by
        omission).

        Raises:
            Exception: Whatever :meth:`ReservationProjectionReader.instrument_state`
                / ``instrument_last_seq`` raise on an unreachable RCL log — not
                caught here (module docstring's fault-contract table: steps
                8-10 map this to UNKNOWN, not a snapshot-level decision).
        """
        last_seq = self._projection.instrument_last_seq(key)
        state = self._projection.instrument_state(key)
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
            conservative_current_usage=CapacityVector(),
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
                "reservation_state": None if state is None else state.value,
                "all_fields_attributed": all_fields_attributed,
            },
            kind=_EVIDENCE_KIND_SNAPSHOT,
            record_class=_EVIDENCE_KIND_SNAPSHOT,
        )
        return snapshot

    def decide(
        self,
        key: InstrumentKey,
        inputs: AggregateRiskDecisionInputs,
        *,
        snapshot_generation: int,
        decision_generation: int,
    ) -> AggregateRiskDecision:
        """Prepare :func:`tos.are.risk_decision`'s witnesses via the other
        ``tos.are`` §5 predicates, then call it exactly once (module
        docstring).

        Raises:
            Exception: Propagated from :meth:`snapshot` on an unreachable RCL
                projection (never swallowed into a false decision).
        """
        snapshot = self.snapshot(
            key,
            snapshot_generation=snapshot_generation,
            required_scopes=inputs.required_scopes,
            all_fields_attributed=inputs.all_fields_attributed,
            lineage_ref=inputs.lineage_ref,
        )
        snapshot_complete = snapshot_scope_complete(
            snapshot,
            inputs.required_scopes,
            all_fields_attributed=inputs.all_fields_attributed,
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
        # decision_id ⊥ canonical_digest — both appended, never conflated as one key.
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
