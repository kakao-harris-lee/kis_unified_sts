"""Pure derived predicates and conservative aggregations (design §2.5, §4.5, §5)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from tos.capsule._base import ArtifactStatus, FrozenModel
from tos.capsule.capsule import DecisionContextCapsule
from tos.capsule.field_state import FieldState, restrictiveness, worst
from tos.capsule.lineage import TransformationLineage
from tos.capsule.observation import AdmissionResult, Observation
from tos.capsule.snapshot import CorroborationPath, CriticalInputSnapshot


def cut_compatible(snapshot: CriticalInputSnapshot) -> bool:
    """Derived (non-stored) consistency-cut predicate (design §2.5, m3)."""
    cut = snapshot.consistency_cut
    if cut.uncertainty != FieldState.VALID:
        return False
    if not cut.atomicity_proven:
        return False
    if not cut.source_continuity_vector:
        return False
    if any(entry.continuity_gap for entry in cut.source_continuity_vector):
        return False
    for evaluation in snapshot.field_evaluations:
        if evaluation.blocking and evaluation.state in (
            FieldState.CONFLICTED,
            FieldState.INVALID,
        ):
            return False
    return True


def aggregate_snapshot_validity(
    snapshot: CriticalInputSnapshot, *, required_independent_paths: int
) -> FieldState:
    """Conservatively aggregate a snapshot's validity result (design §5.1)."""
    blocking = [fe.state for fe in snapshot.field_evaluations if fe.blocking]
    cut_ok = cut_compatible(snapshot)
    common_ok = not has_unresolved_common_mode(snapshot)
    corroboration_ok = (
        effective_independent_path_count(snapshot.corroboration_paths)
        >= required_independent_paths
    )
    gates_pass = cut_ok and common_ok and corroboration_ok
    if gates_pass and blocking and all(state == FieldState.VALID for state in blocking):
        return FieldState.VALID
    candidates = list(blocking)
    if not cut_ok:
        candidates.append(FieldState.CONFLICTED)
    if (not common_ok) or (not corroboration_ok) or (not blocking):
        candidates.append(FieldState.UNKNOWN)
    result = worst(candidates)
    return result if result != FieldState.VALID else FieldState.UNKNOWN


def verify_validity_result_conservative(snapshot: CriticalInputSnapshot) -> bool:
    """Whether a stored ``validity.result`` is conservative (design §5.1)."""
    intrinsic = aggregate_snapshot_validity(snapshot, required_independent_paths=0)
    return restrictiveness(snapshot.validity.result) >= restrictiveness(intrinsic)


class AdmissionExpectation(FrozenModel):
    """Injected policy expectation for admission (design §2.2, §8)."""

    environment: str | None = None
    account: str | None = None
    venue: str | None = None
    instrument: str | None = None
    currency: str | None = None
    unit: str | None = None
    scale: str | None = None
    multiplier: str | None = None
    sign: str | None = None
    trusted_endpoints: tuple[str, ...] = ()


def compute_admission(
    observation: Observation, expectation: AdmissionExpectation
) -> tuple[AdmissionResult, tuple[str, ...]]:
    """Compute the admission decision for one observation (design §2.2)."""
    reasons: list[str] = []
    uncertain = False

    if observation.continuity.continuity_gap:
        reasons.append("continuity_gap")

    if expectation.trusted_endpoints:
        endpoint = observation.source.endpoint
        if endpoint is None:
            uncertain = True
        elif endpoint not in expectation.trusted_endpoints:
            reasons.append("out_of_trust_endpoint")

    mapping = observation.mapping
    comparisons = (
        ("environment", observation.source.environment, expectation.environment),
        ("account", mapping.account, expectation.account),
        ("venue", mapping.venue, expectation.venue),
        ("instrument", mapping.instrument, expectation.instrument),
        ("currency", mapping.currency, expectation.currency),
        ("unit", mapping.unit, expectation.unit),
        ("scale", mapping.scale, expectation.scale),
        ("multiplier", mapping.multiplier, expectation.multiplier),
        ("sign", mapping.sign, expectation.sign),
    )
    for name, observed, expected in comparisons:
        if expected is None:
            continue
        if observed is None:
            uncertain = True
        elif observed != expected:
            reasons.append(f"{name}_mismatch")

    if reasons:
        return AdmissionResult.REJECTED, tuple(reasons)
    if uncertain:
        return AdmissionResult.UNCERTAIN, ()
    return AdmissionResult.ADMITTED, ()


def admitted_field_state(result: AdmissionResult) -> FieldState:
    """Map an admission result to a conservative field state (design §2.2)."""
    if result == AdmissionResult.REJECTED:
        return FieldState.INVALID
    if result == AdmissionResult.UNCERTAIN:
        return FieldState.UNKNOWN
    return FieldState.VALID


def derive_lineage_state(lineage: TransformationLineage) -> FieldState:
    """Derive a lineage node's field state (design §2.3, CII-EV-004)."""
    if not lineage.reproducible:
        return FieldState.INVALID
    if not lineage.parents:
        return FieldState.INVALID
    if any(p.parent_id is None or p.digest is None for p in lineage.parents):
        return FieldState.INVALID
    stochastic = lineage.stochastic
    if stochastic.is_stochastic and (
        stochastic.random_seed is None and stochastic.nondeterminism_declaration is None
    ):
        return FieldState.INVALID
    return FieldState.VALID


def freshness_state(source_age_ms: int | None, max_age_ms: int | None) -> FieldState:
    """Field state from an injected freshness bound (design §2.4, §5.1, §8)."""
    if source_age_ms is None or max_age_ms is None:
        return FieldState.UNKNOWN
    return FieldState.VALID if source_age_ms <= max_age_ms else FieldState.STALE


def observation_validity_stale(
    source_event_time: int | None, now_ms: int, window_ms: int | None
) -> bool:
    """Whether a captured value is stale against its as-of anchor (design §6.2)."""
    if source_event_time is None or window_ms is None:
        return True
    return (now_ms - source_event_time) > window_ms


def capsule_observation_stale(
    capsule: DecisionContextCapsule,
    observation: Observation,
    now_ms: int,
    window_ms: int | None,
) -> bool:
    """Staleness of an observation *as wrapped by* a capsule (design §6.2)."""
    del capsule
    return observation_validity_stale(
        observation.time.source_event_time, now_ms, window_ms
    )


def effective_independent_path_count(paths: Sequence[CorroborationPath]) -> int:
    """Count effectively independent corroboration paths (design §5.2)."""
    n = len(paths)
    if n == 0:
        return 0
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    tag_first: dict[str, int] = {}
    for i, path in enumerate(paths):
        if not path.tags:
            for j in range(n):
                union(i, j)
            continue
        for tag in path.tags:
            if tag in tag_first:
                union(i, tag_first[tag])
            else:
                tag_first[tag] = i
    return len({find(i) for i in range(n)})


def has_unresolved_common_mode(snapshot: CriticalInputSnapshot) -> bool:
    """Whether corroboration independence is collapsed by common mode (design §5.2)."""
    paths = snapshot.corroboration_paths
    if len(paths) <= 1:
        return False
    return effective_independent_path_count(paths) < len(paths)


def transitive_dependents(
    roots: Iterable[str], edges: Mapping[str, Iterable[str]]
) -> frozenset[str]:
    """Transitive closure of dependents reachable from ``roots`` (design §4.5)."""
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        for dependent in edges.get(node, ()):
            if dependent not in seen:
                seen.add(dependent)
                stack.append(dependent)
    return frozenset(seen)


def correction_invalidation_closure(
    correction: Observation, edges: Mapping[str, Iterable[str]]
) -> frozenset[str]:
    """Downstream ids a correction invalidates (design §4.5, CII-INV-008)."""
    links = correction.correction_links
    roots: set[str] = set(links.predecessor_ids)
    for ref in (links.correction_of, links.retraction_of, links.supersedes):
        if ref is not None:
            roots.add(ref)
    return transitive_dependents(roots, edges)


def economic_effects_after_invalidation(
    economic_effects: Iterable[str], invalidated_context_ids: Iterable[str]
) -> frozenset[str]:
    """Economic effects surviving a context invalidation (design §4.5, CII-INV-009)."""
    del invalidated_context_ids
    return frozenset(economic_effects)


class InputClassification(FrozenModel):
    """A critical-input classification record (design §5.8)."""

    input_id: str | None = None
    could_change_decision: bool | None = None
    classified_critical: bool = False


def is_material(could_change_decision: bool | None) -> bool:
    """Conservative materiality (design §5.8)."""
    return True if could_change_decision is None else could_change_decision


def classification_complete(inputs: Iterable[InputClassification]) -> bool:
    """Whether every material input is classified critical (design §5.8)."""
    return all(
        inp.classified_critical
        for inp in inputs
        if is_material(inp.could_change_decision)
    )


def grants_no_authority(artifact: object) -> bool:
    """Whether an artifact's authority block grants nothing (design §4.4)."""
    authority = artifact.authority  # type: ignore[attr-defined]
    return not any(getattr(authority, name) for name in type(authority).model_fields)


def capsule_can_authorize_new_risk(
    capsule: DecisionContextCapsule, now_ms: int | None = None
) -> bool:
    """Whether a capsule may still ground new risk (design §7, CII-EV-012)."""
    if capsule.missing_required_fields():
        return False
    if capsule.status != ArtifactStatus.ISSUED:
        return False
    validity = capsule.validity
    if validity.invalidation_generation is not None:
        return False
    return not (
        now_ms is not None
        and validity.expires_at is not None
        and now_ms > validity.expires_at
    )


def non_revival_holds(
    prior: DecisionContextCapsule, restored: DecisionContextCapsule
) -> bool:
    """Whether restart/restore respects non-revival (design §4.4/§7, CII-INV-013)."""
    if prior.status in (ArtifactStatus.INVALIDATED, ArtifactStatus.SUPERSEDED):
        if restored.capsule_id == prior.capsule_id and capsule_can_authorize_new_risk(
            restored
        ):
            return False
    return True


def continuity_admissible(observation: Observation) -> bool:
    """Predicate-only continuity admissibility (design §7, CII-EV-002)."""
    if observation.continuity.continuity_gap:
        return False
    return observation.admission.result == AdmissionResult.ADMITTED


def egress_currentness_ok(
    source_event_time: int | None, now_ms: int, window_ms: int | None
) -> bool:
    """Predicate-only final-egress currentness (design §7, CII-EV-009)."""
    return not observation_validity_stale(source_event_time, now_ms, window_ms)
