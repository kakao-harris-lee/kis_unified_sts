"""Pure derived predicates and conservative aggregations (design §2.5, §4.5, §5).

These are the EV-L1 *functions* whose contract the property tests verify. None is
a stored artifact field; all are computed on demand from the frozen models. They
are monotone toward restriction — no function here can turn a non-``VALID`` input
into a ``VALID`` result except by every gate passing (CII-INV-005).

Contents:

* :func:`cut_compatible` — the non-stored consistency-cut predicate (design §2.5).
* :func:`aggregate_snapshot_validity` — conservative ``validity.result`` (§5.1).
* :func:`compute_admission` / :func:`admitted_field_state` — observation admission
  (design §2.2, CII-EV-003).
* :func:`derive_lineage_state` — reproducibility -> INVALID (design §2.3, CII-EV-004).
* :func:`freshness_state`, :func:`observation_validity_stale`,
  :func:`capsule_observation_stale` — injected-bound freshness + Validity-Window
  as-of anchor / re-wrap invariance (design §2.4, §5.1, §6.2).
* :func:`effective_independent_path_count`, :func:`has_unresolved_common_mode` —
  common-mode collapse (design §5.2, CII-EV-006 core).
* :func:`correction_invalidation_closure`,
  :func:`economic_effects_after_invalidation` — correction fan-out + economic-effect
  orthogonality (design §4.5, CII-EV-008).
* :func:`classification_complete`, :func:`is_material` — classification completeness
  with conservative unknown-materiality (design §5.8, CII-EV-001).
* :func:`capsule_can_authorize_new_risk`, :func:`non_revival_holds` — non-revival
  state predicates (design §4.4/§7, CII-EV-012 core).
* :func:`grants_no_authority` — authority-absence predicate (design §4.4, CII-EV-011).
* :func:`continuity_admissible`, :func:`egress_currentness_ok` — predicate-only
  surfaces for CII-EV-002 / -009 (design §7, gap 6).

Pure module: ``pydantic`` + stdlib only; no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from tos.capsule._base import ArtifactStatus, FrozenModel
from tos.capsule.capsule import DecisionContextCapsule
from tos.capsule.field_state import FieldState, restrictiveness, worst
from tos.capsule.lineage import TransformationLineage
from tos.capsule.observation import AdmissionResult, Observation
from tos.capsule.snapshot import CorroborationPath, CriticalInputSnapshot

# ===========================================================================
# Consistency cut + snapshot validity aggregation (design §2.5, §5.1, §5.3)
# ===========================================================================


def cut_compatible(snapshot: CriticalInputSnapshot) -> bool:
    """Derived (non-stored) consistency-cut predicate (design §2.5, m3).

    The cut is compatible only when the read is atomically coherent: cut
    uncertainty is ``VALID``, atomicity is proven, an established continuity
    vector exists with no gaps, and no blocking field evaluation is conflicted or
    invalid. Otherwise fields cannot be combined into one coherent state (CII-
    INV-007, ADR §11 line 309): equality between reads or absence from a query is
    not a completeness proof.

    Args:
        snapshot: The snapshot whose cut is evaluated.

    Returns:
        ``True`` iff the cut can bind the fields into one coherent state.
    """
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
    """Conservatively aggregate a snapshot's validity result (design §5.1).

    ``VALID`` is reached only when **all four** §5.1 conjuncts hold:

    1. there is at least one blocking field evaluation and every blocking
       evaluation is ``VALID`` — an *empty* blocking set is not evidence of
       validity and fails closed to ``UNKNOWN`` (MAJOR-3b), so silence is never
       mistaken for health;
    2. the consistency cut is compatible (``cut_compatible``);
    3. there is no unresolved common-mode dependency
       (``has_unresolved_common_mode``);
    4. the effective independent corroboration-path count meets the **injected**
       ``required_independent_paths`` bound (design §8 — never hard-coded).

    This is not an average, majority, or field-ignoring vote (ADR §11 line 311).
    On any gate failure the result is the most restrictive observed state, with a
    ``CONFLICTED`` floor when the cut is incoherent (CII-INV-007, MINOR-4) and an
    ``UNKNOWN`` floor otherwise — so a gate failure can never resolve to ``VALID``
    even when every field is individually fresh ("individually fresh != valid
    snapshot", ADR §11 line 309; CII-INV-005/007).

    Args:
        snapshot: The snapshot to aggregate.
        required_independent_paths: The injected minimum number of effectively
            independent corroboration paths required (§8 policy bound). Use ``0``
            only for the model-intrinsic conservatism check; consumers inject the
            policy value.

    Returns:
        The conservative :class:`FieldState` result.
    """
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
        # An incoherent (non-atomic) cut is a conflict, not mere uncertainty.
        candidates.append(FieldState.CONFLICTED)
    if (not common_ok) or (not corroboration_ok) or (not blocking):
        candidates.append(FieldState.UNKNOWN)  # fail-closed floor
    result = worst(candidates)
    return result if result != FieldState.VALID else FieldState.UNKNOWN


def verify_validity_result_conservative(snapshot: CriticalInputSnapshot) -> bool:
    """Whether a stored ``validity.result`` is conservative (design §5.1).

    A stored result is conservative iff it is at least as restrictive as the
    model-intrinsic aggregate (computed with ``required_independent_paths=0``, the
    neutral floor — the policy corroboration bound is an additional
    consumption-time gate, not a stored property). This is the invariant the
    snapshot construction guard enforces.

    Args:
        snapshot: The snapshot to check.

    Returns:
        ``True`` iff ``restrictiveness(stored) >= restrictiveness(intrinsic)``.
    """
    intrinsic = aggregate_snapshot_validity(snapshot, required_independent_paths=0)
    return restrictiveness(snapshot.validity.result) >= restrictiveness(intrinsic)


# ===========================================================================
# Observation admission (design §2.2, CII-EV-003)
# ===========================================================================


class AdmissionExpectation(FrozenModel):
    """Injected policy expectation for admission (design §2.2, §8).

    Only non-``None`` fields are checked. Mismatch of any concrete expectation is
    a reject (CII-EV-003); an expected-but-unverifiable field yields ``UNCERTAIN``
    (fail-closed, never silently admitted).
    """

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
    """Compute the admission decision for one observation (design §2.2).

    Pure function over a single observation and an injected policy expectation.
    A declared continuity gap, an out-of-trust endpoint, or any concrete
    unit/scale/mapping mismatch rejects; an expected-but-missing field is
    uncertain; otherwise the observation is admitted (ADR §9 line 263-272).

    Args:
        observation: The observation to evaluate.
        expectation: The injected policy expectation.

    Returns:
        A ``(result, reject_reasons)`` tuple.
    """
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
    """Map an admission result to a conservative field state (design §2.2).

    Args:
        result: The admission result.

    Returns:
        ``INVALID`` for ``REJECTED``, ``UNKNOWN`` for ``UNCERTAIN``, ``VALID`` for
        ``ADMITTED`` (a VALID *candidate*, still subject to other gates).
    """
    if result == AdmissionResult.REJECTED:
        return FieldState.INVALID
    if result == AdmissionResult.UNCERTAIN:
        return FieldState.UNKNOWN
    return FieldState.VALID


# ===========================================================================
# Transformation lineage reproducibility (design §2.3, CII-EV-004)
# ===========================================================================


def derive_lineage_state(lineage: TransformationLineage) -> FieldState:
    """Derive a lineage node's field state (design §2.3, CII-EV-004).

    A derived input is ``INVALID`` for new risk if it is non-reproducible, if any
    exact parent is missing (empty parent set, or an entry lacking an id or
    digest), or if a stochastic transform declares neither a random seed nor a
    nondeterminism declaration (ADR §10 line 285, 288). Otherwise ``VALID``.

    Args:
        lineage: The transformation-lineage node.

    Returns:
        The derived :class:`FieldState`.
    """
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


# ===========================================================================
# Freshness + Validity Window as-of anchor (design §2.4, §5.1, §6.2)
# ===========================================================================


def freshness_state(source_age_ms: int | None, max_age_ms: int | None) -> FieldState:
    """Field state from an injected freshness bound (design §2.4, §5.1, §8).

    Fail-closed: a missing age or a missing bound yields ``UNKNOWN`` (an absent
    window blocks new risk, design §6.2). Otherwise the state is ``VALID`` within
    the bound and ``STALE`` beyond it. No last-known-good / cache / TTL /
    heartbeat argument exists that could upgrade a non-fresh field (ADR §14 line
    367).

    Args:
        source_age_ms: Age of the value in milliseconds.
        max_age_ms: The injected maximum-age bound in milliseconds.

    Returns:
        ``UNKNOWN``, ``VALID``, or ``STALE``.
    """
    if source_age_ms is None or max_age_ms is None:
        return FieldState.UNKNOWN
    return FieldState.VALID if source_age_ms <= max_age_ms else FieldState.STALE


def observation_validity_stale(
    source_event_time: int | None, now_ms: int, window_ms: int | None
) -> bool:
    """Whether a captured value is stale against its as-of anchor (design §6.2).

    Staleness is measured from the value's recorded as-of / production time
    (``source_event_time``), never from a capsule wrap time (EXV-INV-002). A
    missing anchor or window is fail-closed (stale/blocked, design §6.2 line 197).

    Args:
        source_event_time: The value's as-of / production time (epoch ms).
        now_ms: The current time (epoch ms).
        window_ms: The Validity Window in milliseconds.

    Returns:
        ``True`` if the value is stale (or its window/anchor is unknown).
    """
    if source_event_time is None or window_ms is None:
        return True
    return (now_ms - source_event_time) > window_ms


def capsule_observation_stale(
    capsule: DecisionContextCapsule,
    observation: Observation,
    now_ms: int,
    window_ms: int | None,
) -> bool:
    """Staleness of an observation *as wrapped by* a capsule (design §6.2).

    Deliberately ignores ``capsule.validity.issued_at``: the Validity Window is
    anchored on the observation as-of time, so re-wrapping the same observation
    in a later capsule does not reset currentness (re-wrap invariance,
    EXV-INV-002 §12.6). ``capsule`` is present only to make the ignored wrap-time
    dependency explicit at the call site.

    Args:
        capsule: The capsule wrapping the observation (wrap time ignored).
        observation: The wrapped observation.
        now_ms: The current time (epoch ms).
        window_ms: The Validity Window in milliseconds.

    Returns:
        ``True`` if the observation is stale by its as-of anchor.
    """
    del capsule  # wrap time is intentionally not an input to staleness (§6.2)
    return observation_validity_stale(
        observation.time.source_event_time, now_ms, window_ms
    )


# ===========================================================================
# Common-mode collapse (design §5.2, CII-EV-006 core)
# ===========================================================================


def effective_independent_path_count(paths: Sequence[CorroborationPath]) -> int:
    """Count effectively independent corroboration paths (design §5.2).

    Two paths sharing any effective resource tag (control / origin / parser /
    mapping / library / cache / administrator / failure-domain) are not counted
    independent (ADR §13 line 344; §10 line 290). A path with an empty tag set has
    undetermined scope and is treated as shared with every other path
    (conservative, ADR §22 line 522). The result is the number of connected
    components under the "shares a tag" relation.

    Args:
        paths: The corroboration paths.

    Returns:
        The number of effectively independent paths.
    """
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
        if not path.tags:  # undetermined scope -> shared with all
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
    """Whether corroboration independence is collapsed by common mode (design §5.2).

    With two or more corroboration paths, any collapse (effective independent
    count below the declared path count) is unresolved common mode.

    Args:
        snapshot: The snapshot whose corroboration paths are analysed.

    Returns:
        ``True`` if independence is collapsed among multiple declared paths.
    """
    paths = snapshot.corroboration_paths
    if len(paths) <= 1:
        return False
    return effective_independent_path_count(paths) < len(paths)


# ===========================================================================
# Correction / invalidation fan-out (design §4.5, CII-EV-008)
# ===========================================================================


def transitive_dependents(
    roots: Iterable[str], edges: Mapping[str, Iterable[str]]
) -> frozenset[str]:
    """Transitive closure of dependents reachable from ``roots`` (design §4.5).

    Args:
        roots: The starting node ids.
        edges: A directed adjacency map from a node id to the ids that depend on
            it (``node -> dependents``).

    Returns:
        Every dependent id reachable from ``roots`` (excluding the roots unless a
        root is itself a dependent of another visited node).
    """
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        for dependent in edges.get(node, ()):  # type: ignore[call-overload]
            if dependent not in seen:
                seen.add(dependent)
                stack.append(dependent)
    return frozenset(seen)


def correction_invalidation_closure(
    correction: Observation, edges: Mapping[str, Iterable[str]]
) -> frozenset[str]:
    """Downstream ids a correction invalidates (design §4.5, CII-INV-008).

    A material correction/retraction/supersession invalidates every affected,
    unconsumed downstream permission before any future new-risk send. Roots are
    the ids the correction links to (a correction is a new immutable record
    linked to prior records, not a destructive overwrite, ADR §17 line 415).

    Args:
        correction: The correcting observation (its ``correction_links`` supply
            the roots).
        edges: The dependency adjacency map (``node -> dependents``).

    Returns:
        The transitive set of invalidated downstream ids.
    """
    links = correction.correction_links
    roots: set[str] = set(links.predecessor_ids)
    for ref in (links.correction_of, links.retraction_of, links.supersedes):
        if ref is not None:
            roots.add(ref)
    return transitive_dependents(roots, edges)


def economic_effects_after_invalidation(
    economic_effects: Iterable[str], invalidated_context_ids: Iterable[str]
) -> frozenset[str]:
    """Economic effects surviving a context invalidation (design §4.5, CII-INV-009).

    Snapshot/capsule/policy expiry or invalidation changes only context-artifact
    validity; it does not expire orders, fills, exposure, UNKNOWN, or capacity.
    Economic effect is orthogonal to the context lifecycle, so this returns the
    economic effects unchanged.

    Args:
        economic_effects: The existing economic-effect record ids.
        invalidated_context_ids: The invalidated context-artifact ids (ignored).

    Returns:
        The economic-effect ids, unchanged.
    """
    del invalidated_context_ids  # orthogonal — invalidation never erases effects
    return frozenset(economic_effects)


# ===========================================================================
# Classification completeness (design §5.8, CII-EV-001)
# ===========================================================================


class InputClassification(FrozenModel):
    """A critical-input classification record (design §5.8)."""

    input_id: str | None = None
    could_change_decision: bool | None = None  # None = unknown materiality
    classified_critical: bool = False


def is_material(could_change_decision: bool | None) -> bool:
    """Conservative materiality (design §5.8).

    Unknown materiality (``None``) is treated as material (ADR §5.8; "unknown
    materiality => material").

    Args:
        could_change_decision: Whether the input could change the decision, or
            ``None`` if unknown.

    Returns:
        ``True`` if the input is material.
    """
    return True if could_change_decision is None else could_change_decision


def classification_complete(inputs: Iterable[InputClassification]) -> bool:
    """Whether every material input is classified critical (design §5.8).

    Args:
        inputs: The input classifications.

    Returns:
        ``True`` iff every material input has ``classified_critical`` set.
    """
    return all(
        inp.classified_critical
        for inp in inputs
        if is_material(inp.could_change_decision)
    )


# ===========================================================================
# Non-revival + authority absence (design §4.4, §7, CII-EV-011/012)
# ===========================================================================


def grants_no_authority(artifact: object) -> bool:
    """Whether an artifact's authority block grants nothing (design §4.4).

    Args:
        artifact: Any artifact exposing an ``authority`` block.

    Returns:
        ``True`` iff every authority flag is ``False``.
    """
    authority = artifact.authority  # type: ignore[attr-defined]
    return not any(getattr(authority, name) for name in type(authority).model_fields)


def capsule_can_authorize_new_risk(
    capsule: DecisionContextCapsule, now_ms: int | None = None
) -> bool:
    """Whether a capsule may still ground new risk (design §7, CII-EV-012).

    Fail-closed: a capsule may ground new risk only when it is ``ISSUED``, has
    **every** required safety-load-bearing covered field concrete
    (``missing_required_fields`` empty — the same completeness the construction
    guard enforces, but re-checked here so a capsule assembled via a
    validation-bypassing path such as ``model_construct`` still cannot authorize),
    carries no invalidation generation, and has not passed expiry. A
    ``DRAFT``/``SUPERSEDED``/``INVALIDATED`` capsule cannot.

    Args:
        capsule: The capsule to test.
        now_ms: The current time (epoch ms); expiry is checked only when given.

    Returns:
        ``True`` iff the capsule is currently a valid grounding context.
    """
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
    """Whether restart/restore respects non-revival (design §4.4/§7, CII-INV-013).

    A restart or restore must not resurrect a restricted (invalidated/superseded)
    prior capsule's authorizing ability under the *same* identity; new risk
    requires a new capsule (new continuity => new digest => new id). The predicate
    *holds* (returns ``True``) unless the restored capsule reuses the prior id and
    can authorize new risk.

    Args:
        prior: The restricted prior capsule.
        restored: The capsule produced by restart/restore.

    Returns:
        ``True`` if non-revival is respected, ``False`` if a revival is detected.
    """
    if prior.status in (ArtifactStatus.INVALIDATED, ArtifactStatus.SUPERSEDED):
        if restored.capsule_id == prior.capsule_id and capsule_can_authorize_new_risk(
            restored
        ):
            return False
    return True


# ===========================================================================
# Predicate-only surfaces (design §7, gap 6): CII-EV-002 / -009
# ===========================================================================


def continuity_admissible(observation: Observation) -> bool:
    """Predicate-only continuity admissibility (design §7, CII-EV-002).

    Transport-healthy reset/rollback/gap/replay detection is EV-L2 fault
    injection; the L1 predicate only fails closed on a declared continuity gap or
    a non-admitted observation.

    Args:
        observation: The observation to test.

    Returns:
        ``True`` iff no continuity gap is declared and the observation is admitted.
    """
    if observation.continuity.continuity_gap:
        return False
    return observation.admission.result == AdmissionResult.ADMITTED


def egress_currentness_ok(
    source_event_time: int | None, now_ms: int, window_ms: int | None
) -> bool:
    """Predicate-only final-egress currentness (design §7, CII-EV-009).

    Race/partition/suppression at the irreversible boundary is EV-L2/L3, and
    egress is non-transmitting here (design §0.2). The L1 predicate is the
    fail-closed staleness check against the as-of anchor.

    Args:
        source_event_time: The value's as-of / production time (epoch ms).
        now_ms: The current time (epoch ms).
        window_ms: The Validity Window in milliseconds.

    Returns:
        ``True`` iff the value is not stale at egress time.
    """
    return not observation_validity_stale(source_event_time, now_ms, window_ms)
