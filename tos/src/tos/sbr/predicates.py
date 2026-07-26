"""sbr recovery decision predicates (design #17 §5/§6) — pure, fail-closed.

Pure decision rules over injected frozen models (design #17 §0.2/§4.6): SBR is a **recovery
orchestrator, not a per-dimension judge** — state reconstruction is orthostate-owned,
per-field confidence is recon-owned, capacity mutation is rcl-owned, protective
classification is protective-owned, and re-arm admissibility / Live Authorization are
authority / liveauth-owned (§3.5). SBR **folds** those injected results into inventory
completeness, obligation-graph closure, scope / invalidation reachability, convergence, and
readiness; it re-authors none of them. There is **no** "assume-complete" / "assume-isolated"
/ "timeout-fallback" / "promote-UNKNOWN" path anywhere: a positive result comes only from
positive proof, everything else is ``NOT_READY`` / ``False`` / non-satisfied (design #17
§4.1 — the structural seal against the #6 fail-open lesson).

**Truthy-sentinel discipline (design #17 §4.7).** ``ReadinessVerdict`` / ``SessionState`` /
``RecoveryBarrierState`` / ``ObligationResult`` are truthy-untestable ``StrEnum``s
(``__bool__`` raises), so every gate uses ``x is ENUM.SAFE_VALUE`` (e.g.
``result is ObligationResult.SATISFIED``); injected ``bool | None`` flags are normalized
with ``is True`` / ``is not True`` (the orthostate ``predicates.py:461`` precedent) — a
``None`` is UNKNOWN, never a soft pass.

**Shared reachability kernel (design #17 §5.3 / MINOR-5).** §5.3 scope closure and §5.6
readiness invalidation share the single private :func:`_reachability_closure` — the same
pure transitive-reachability the iap ``invalidation_closure`` (``iap/predicates.py:347``)
authors, **re-authored locally** (import of ``tos.iap`` is forbidden — sibling edge 0; the
DRY is preserved at the property-test-contract level, not by code sharing, design #17
§0.4d). Its axioms: ``trigger`` is always in its own closure; monotone (adding uncertain
edges only widens); a cycle terminates (visited set); an uncertain / unproven edge is
**expanded** (under-count is a fail-open); an empty graph yields the minimal closure
``{trigger}``.

Pure module: ``pydantic`` + stdlib + ``tos.sbr.*`` (records / vocabulary) only; no
``shared.*``, no other sibling ``tos.*`` (design #17 §0.3).
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.sbr.records import (
    BrokerReadSequence,
    IsolationFacts,
    RecoveryAuthorityEffect,
    RecoveryBarrierPolicy,
    RecoveryInventoryCut,
    RecoveryObligation,
    RecoveryScope,
)
from tos.sbr.vocabulary import (
    ObligationResult,
    OwnerStatus,
    RecoveryBarrierState,
    SelectionBasis,
)

__all__ = [
    # core §5 (SBR-EV-004/006/007/009/012 substrate)
    "recovery_inventory_complete",
    "obligation_graph_closed",
    "recovery_scope_closure",
    "unknown_stays_conservative",
    "timeout_is_restrictive",
    "restricted_isolation_proven",
    "readiness_invalidated_by_change",
    "recovery_completion_revives_nothing",
    # predicate-only §6 (SBR-EV-001/002/003/005/008/010/011 substrate)
    "start_closed",
    "stale_generation_rejected_at_egress",
    "competing_owner_fenced",
    "non_atomic_broker_conservative",
    "halt_dominates_recovery",
    "restore_worst_credible_union",
    "recovery_authority_separated",
]


# ===========================================================================
# Shared reachability kernel (design #17 §5.3 / §5.6 / MINOR-5)
# ===========================================================================


def _reachability_closure(
    graph: Mapping[str, frozenset[str]],
    trigger: str,
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The transitive-reachability closure from ``trigger`` (design #17 §5.3 / §0.4d).

    The single kernel shared by :func:`recovery_scope_closure` (§8 scope expansion) and
    :func:`readiness_invalidated_by_change` (§18 invalidation) — isomorphic to the iap
    ``invalidation_closure`` (``iap/predicates.py:347``), re-authored locally (sibling edge
    0). Axioms (regressed by the §7 shared-closure property contract):

    * ``trigger`` is always in its own closure (an empty graph yields ``{trigger}`` — a
      "nothing reachable" is not a vacuous empty set, design #17 §4.7);
    * an **uncertain / unproven** edge is followed exactly like a definite edge — an
      under-count would let a dependent escape (a fail-open; §8 line 240 "included unless
      isolation is positively proven");
    * a **proven-disconnected** node (absent from both adjacencies) is excluded (the
      availability side — over-expansion is safe, a spurious block is an availability defect);
    * a cycle terminates (visited set) and includes the cycle.

    Args:
        graph: The definite dependency adjacency ``{node: {dependents}}``.
        trigger: The trigger node (always in its own closure).
        unproven: Optional uncertain-edge adjacency ``{node: {maybe-dependents}}``, followed
            (expanded) exactly like ``graph`` (fail-closed tie-break — under-count is
            prohibited, design #17 §4.7).

    Returns:
        The frozenset of every node reachable from ``trigger`` (incl. ``trigger``).
    """
    unproven_adj: Mapping[str, frozenset[str]] = unproven or {}
    closure: set[str] = set()
    stack: list[str] = [trigger]
    while stack:
        node = stack.pop()
        if node in closure:
            continue
        closure.add(node)
        for dependent in graph.get(node, frozenset()):
            if dependent not in closure:
                stack.append(dependent)
        for dependent in unproven_adj.get(node, frozenset()):
            # 불확정 edge => 확장 (treat as reachable — under-count is a fail-open, §8 line 240).
            if dependent not in closure:
                stack.append(dependent)
    return frozenset(closure)


# ===========================================================================
# core §5.1 — recovery inventory completeness (SBR-EV-004 substrate, L1 slice)
# ===========================================================================


def recovery_inventory_complete(
    cut: RecoveryInventoryCut | None,
    policy: RecoveryBarrierPolicy | None,
) -> bool:
    """Whether the inventory cut is complete over every required dependency (§12; SBR-INV-005).

    SBR-INV-005 line 162 verbatim: "Recovery cannot be ready while any required order,
    attempt, fill, position, capacity, external, non-trade, protective, broker, or evidence
    dependency is **omitted or unbounded**." SBR decides only **completeness** (omission /
    unbounded); each dependency's **value** is judged by the owning sibling (§3.5). ``True``
    **only** when:

    1. both the cut and the policy exist (a ``None`` proves nothing);
    2. the **required dependency kinds are non-empty** — a cut proving "complete over
       nothing" is vacuous, so an empty required set fails closed (design #17 §4.7; the afg
       ``scope_graph_complete`` precedent). The required set is the union of the policy's
       declared kinds and the cut's own required kinds;
    3. every required kind is positively **observed** (an omitted dependency fails closed —
       "omission creates NOT_READY", SBR-AC-004 line 641);
    4. **no** dependency is unbounded (``unbounded_dependency_kinds`` is empty — an unbounded
       window is incomplete, §12 line 162);
    5. the time is not ambiguous (``time_ambiguous is False`` — a time-ambiguous cut stays
       non-permissive, §12 line 335; monotonic clocks are never compared across continuities);
    6. the conservative-evidence witnesses are positively present — the unobserved-window
       assumptions, the max-adverse bounds, and the required repeat observations (§12 line
       332); a flat snapshot without them is not completeness (§12 line 128 / line 172).

    Args:
        cut: The recovery inventory cut (``None`` => ``False``).
        policy: The recovery barrier policy declaring the required kinds (``None`` / empty =>
            ``False``).

    Returns:
        ``True`` iff the cut is complete and bounded over every required dependency.
    """
    if cut is None or policy is None:
        return False
    required = frozenset(policy.required_dependency_kinds) | frozenset(
        cut.required_dependency_kinds
    )
    if not required:
        return False
    if not required <= frozenset(cut.observed_dependency_kinds):
        return False
    if cut.unbounded_dependency_kinds:
        return False
    if cut.time_ambiguous is not False:
        return False
    if cut.unobserved_window_assumptions_present is not True:
        return False
    if cut.max_adverse_bounds_present is not True:
        return False
    return cut.required_repeat_observations_met is True


# ===========================================================================
# core §5.2 — obligation-graph closure + acyclicity (SBR-EV-004 substrate, L1 slice)
# ===========================================================================


def obligation_graph_closed(obligations: frozenset[RecoveryObligation]) -> bool:
    """Whether the recovery obligation graph is closed and acyclic (§13; SBR-INV-005).

    §13 line 372 verbatim: "Missing or cyclic obligation dependencies make the session
    NOT_READY", and "An obligation cannot be marked satisfied by its own proposing component
    where independent evidence is required." Returns a **DAG-validity ``bool``** (not the
    reachability *set* the iap ``invalidation_closure`` returns — a different return type,
    so iap reuse would be a category error, design #17 §0.4d). ``True`` **only** when:

    * the set is **non-empty** — an empty obligation set is not "nothing to prove"; the
      minimum obligation set (§13 line 352-370) is mandatory, so empty fails closed (§4.7);
    * every ``obligation_id`` is concrete and **unique** (a ``None`` / duplicate id fails);
    * every ``prerequisite_id`` references an obligation in the set (no **dangling**
      prerequisite — §13 line 372);
    * the prerequisite graph is **acyclic** (a Kahn topological sort consumes every node);
    * every obligation reached ``result is ObligationResult.SATISFIED`` **and** that result
      is in its ``acceptable_results`` (only ``SATISFIED`` passes, §2.2(5); a ``FAILED`` /
      ``UNKNOWN`` / ``TIMED_OUT`` / ``CONFLICTED`` / ``MISSING_SOURCE`` result is not closed);
    * **self-satisfy is forbidden** — an obligation with
      ``independent_review_required is True`` needs ``independent_review_satisfied is True``
      (§13 line 372).

    Args:
        obligations: The recovery obligation set (empty => ``False``).

    Returns:
        ``True`` iff the graph is complete, acyclic, and every obligation is independently
        satisfied.
    """
    if not obligations:
        return False

    by_id: dict[str, RecoveryObligation] = {}
    for obligation in obligations:
        oid = obligation.obligation_id
        if oid is None or oid == "TBD":
            return False
        if oid in by_id:
            return False  # duplicate id — the graph does not silently de-duplicate
        by_id[oid] = obligation

    all_ids = frozenset(by_id)
    for obligation in obligations:
        # Dangling prerequisite (a prerequisite not in the set) => not closed (§13 line 372).
        if not obligation.prerequisite_ids <= all_ids:
            return False
        # Only a SATISFIED result within the declared acceptable set passes (§2.2(5)).
        if obligation.result is not ObligationResult.SATISFIED:
            return False
        if obligation.result not in obligation.acceptable_results:
            return False
        # Self-satisfy forbidden where independent evidence is required (§13 line 372).
        if (
            obligation.independent_review_required is True
            and obligation.independent_review_satisfied is not True
        ):
            return False

    # Acyclicity: Kahn topological sort. An obligation depends on its prerequisites, so its
    # in-degree is the number of prerequisites; a leftover node is a cycle (§13 line 372).
    indegree: dict[str, int] = {
        oid: len(by_id[oid].prerequisite_ids) for oid in all_ids
    }
    dependents: dict[str, list[str]] = {oid: [] for oid in all_ids}
    for oid in all_ids:
        for prerequisite in by_id[oid].prerequisite_ids:
            dependents[prerequisite].append(oid)
    ready = [oid for oid in all_ids if indegree[oid] == 0]
    consumed = 0
    while ready:
        node = ready.pop()
        consumed += 1
        for dependent in dependents[node]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    return consumed == len(all_ids)


# ===========================================================================
# core §5.3 — recovery scope closure (SBR-EV-004/007 substrate, L1 slice)
# ===========================================================================


def recovery_scope_closure(
    graph: Mapping[str, frozenset[str]],
    trigger: str,
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The recovery scope closure from a trigger (§8 line 240; SBR-EV-004/007 substrate).

    §8 line 240 verbatim: "the shared dependency is included **unless isolation is positively
    proven**. Unknown dependency mapping expands to the containing account or broader Safety
    Cell." §8 line 242: "A trigger may narrow only after evidence proves the unaffected
    dependency closure. Operator selection, strategy ownership, organizational boundaries, or
    service labels are not isolation proof." Realized via the shared
    :func:`_reachability_closure`: an ``unproven`` (isolation-not-yet-proven) edge is
    **expanded** (widening the scope), and only a proven-disconnected node is excluded. An
    empty graph yields the minimal closure ``{trigger}`` (design #17 §4.7).

    Args:
        graph: The versioned dependency adjacency ``{node: {dependents}}``.
        trigger: The trigger scope node (always in its own closure).
        unproven: The isolation-not-yet-proven adjacency, expanded (widening) exactly like
            ``graph`` — unknown dependency mapping widens the scope (§8 line 240).

    Returns:
        The recovery scope closure (the set of every dependency in scope).
    """
    return _reachability_closure(graph, trigger, unproven=unproven)


# ===========================================================================
# core §5.4 — convergence: UNKNOWN conservatism + timeout restriction (SBR-EV-006)
# ===========================================================================


def unknown_stays_conservative(
    field_results: Mapping[str, ObligationResult],
    prior: Mapping[str, ObligationResult],
) -> bool:
    """Whether reconciliation converged with every UNKNOWN kept conservative (§14; SBR-INV-006).

    §14 line 393 verbatim: "Repeated identical unknown observations do not convert UNKNOWN
    into known state." Convergence (``True``) requires every required field to have reached a
    terminal, non-``UNKNOWN`` result — a field still ``UNKNOWN`` (whether newly ``UNKNOWN`` or
    a repeated identical ``UNKNOWN`` whose ``prior`` was also ``UNKNOWN``) has **not**
    converged and blocks readiness. Returns ``True`` **only** when:

    * every field tracked in ``prior`` is still present in ``field_results`` (a previously-
      tracked field dropped from observation is not convergence — an absence never resolves a
      dependency, §14 line 386); and
    * **no** field in ``field_results`` is ``UNKNOWN`` — the ``prior``-``UNKNOWN`` +
      current-``UNKNOWN`` case is the §14 line 393 repeated-identical case, and any current
      ``UNKNOWN`` fails closed.

    SBR folds recon's per-field results into these obligation results **without blending**
    (no numeric confidence score — the recon ``predicates.py:10-11`` isomorph); it does not
    re-classify confidence (§3.5).

    Args:
        field_results: The current per-field terminal results.
        prior: The previously-observed per-field results (for the drop / repeat check).

    Returns:
        ``True`` iff every field converged to a terminal, non-``UNKNOWN`` result.
    """
    if not field_results and not prior:
        # ∅-∅: no field was ever observed or tracked — convergence is a POSITIVE claim and
        # cannot be vacuously true (§4.1 "positive only from positive proof"; code-review
        # MAJOR — sibling discipline: obligation_graph_closed/recovery_inventory_complete
        # both refuse the empty set).
        return False
    for field in prior:
        if field not in field_results:
            # A previously-tracked field dropped from observation — not converged (§14 line 386).
            return False
    for result in field_results.values():
        # Any current UNKNOWN (incl. a repeated identical UNKNOWN, §14 line 393) is non-converged.
        if result is ObligationResult.UNKNOWN:
            return False
    return True


def timeout_is_restrictive(
    elapsed: bool | None,
    converged: bool | None,
    obligation_set_size_before: int | None,
    obligation_set_size_after: int | None,
) -> bool:
    """Whether the reconciliation timeout is handled restrictively (§14/§19; SBR-INV-012).

    §14 line 393 / §19 line 478 verbatim: "If convergence cannot be proven within
    ``B_startup_reconciliation``, the bound is an operational target and escalation trigger,
    **not permission**. The barrier stays closed." + "Inventory observations never converge |
    NOT_READY; escalate; **no timeout fallback**." SBR-INV-012 line 190: retry / timeout
    "never reduces the obligation set." The one structural invariant decidable from these
    inputs is the **non-reduction** of the obligation set: ``size_after < size_before`` is a
    violation (``False``); a ``None`` size fails closed (``False``).

    ``elapsed`` and ``converged`` are accepted and **discarded** — the §19 line 478 structural
    seal (the afg ``no_blind_retry`` accept-and-discard precedent): neither the passage of the
    reconciliation deadline nor a bare convergence claim can *relax* the gate or shrink the
    obligation set at this layer (convergence itself is proven by
    :func:`unknown_stays_conservative` + :func:`obligation_graph_closed`, never manufactured
    by elapse, and retry never resets elapsed uncertainty — §19 line 486). The real
    escalation bound ``B_startup_reconciliation`` is injected (VP-002, PROPOSED 60s "not
    relaxation of the gate", §8.1).

    Args:
        elapsed: Whether the reconciliation deadline elapsed (accepted and discarded).
        converged: Whether convergence was claimed (accepted and discarded).
        obligation_set_size_before: The obligation-set size before (``None`` => ``False``).
        obligation_set_size_after: The obligation-set size after (``None`` => ``False``).

    Returns:
        ``True`` iff the obligation set was not reduced (the timeout took no fallback).
    """
    # §19 line 478 — elapse / a bare claim never relaxes the gate (accept-and-discard).
    del elapsed, converged
    if obligation_set_size_before is None or obligation_set_size_after is None:
        return False
    return obligation_set_size_after >= obligation_set_size_before


# ===========================================================================
# core §5.5 — restricted-recovery isolation (SBR-EV-007 substrate, L1 slice)
# ===========================================================================


def restricted_isolation_proven(
    candidate_scope: RecoveryScope | None,
    isolation_facts: IsolationFacts | None,
) -> bool:
    """Whether a ``READY_RESTRICTED`` candidate's isolation is positively proven (§17; SBR-INV-008).

    §17 line 436-445: a ``READY_RESTRICTED`` verdict is admissible **only** when all **eight**
    isolation conditions are positively proven; §17 line 447: "Logical strategy separation,
    different UI labels, separate recovery tickets, distinct process instances, or unused
    nominal capacity do not prove isolation" — so a label / ticket / instance never sets a
    flag ``True`` (:class:`~tos.sbr.records.IsolationFacts` requires a positive ``True`` on
    every condition). ``True`` **only** when the candidate scope exists and is identified, and
    all eight :meth:`~tos.sbr.records.IsolationFacts.all_proven` conditions hold. A single
    unproven condition drops the candidate to a broader ``NOT_READY`` (SBR-INV-008 line 174 —
    ``READY_RESTRICTED`` cannot exclude unresolved shared capacity, aggregate limits, broker
    sessions, credentials, routes, protective dependencies, or common failure domains).

    Args:
        candidate_scope: The restricted candidate scope (``None`` / unidentified => ``False``).
        isolation_facts: The eight isolation proofs (``None`` / any unproven => ``False``).

    Returns:
        ``True`` iff the restricted scope's isolation is positively proven on all eight axes.
    """
    if candidate_scope is None or isolation_facts is None:
        return False
    if candidate_scope.scope_id is None or candidate_scope.scope_id == "TBD":
        return False
    return isolation_facts.all_proven()


# ===========================================================================
# core §5.6 — readiness invalidation closure (SBR-EV-009 substrate, L1 slice)
# ===========================================================================


def readiness_invalidated_by_change(
    dep_graph: Mapping[str, frozenset[str]],
    change_triggers: frozenset[str],
    *,
    unproven: Mapping[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """The readiness invalidated by a material change (§18 line 453-461; SBR-EV-009 substrate).

    §18 line 453-461: any relevant state / evidence / generation / policy / configuration /
    identity / broker / route / credential / time / protection / scope change invalidates the
    affected readiness "before future authority issuance" (SBR-INV-011 line 186). Realized as
    the union, over every material change trigger, of the shared
    :func:`_reachability_closure` — the same iap-isomorphic closure discipline (design #17
    §0.4d): an ``unproven`` edge is **expanded** (an affected readiness must not escape
    invalidation — the under-count fail-open). Each trigger is always in its own closure, so a
    single material change with no graph edges still invalidates itself. An **empty**
    ``change_triggers`` yields the empty set — no change, nothing invalidated (the
    availability side; a valid readiness within max age is not spuriously invalidated, §18
    canary b). The real invalidation-to-egress latency is runtime-measured (§8.1); L1 is the
    closure-completeness discipline only.

    Args:
        dep_graph: The readiness dependency adjacency ``{node: {dependents}}``.
        change_triggers: The material change trigger nodes (empty => empty invalidation set).
        unproven: The uncertain-edge adjacency, expanded (an affected readiness must not
            escape, design #17 §4.7).

    Returns:
        The frozenset of every readiness / scope invalidated by the changes.
    """
    invalidated: set[str] = set()
    for trigger in change_triggers:
        invalidated |= _reachability_closure(dep_graph, trigger, unproven=unproven)
    return frozenset(invalidated)


# ===========================================================================
# core §5.7 — recovery completion revives nothing (SBR-EV-012 substrate, L1 slice)
# ===========================================================================


def recovery_completion_revives_nothing(
    *,
    completion_signal: bool | None = None,
    health_recovered: bool | None = None,
    evidence_repaired: bool | None = None,
    replay_matched: bool | None = None,
    human_acknowledged: bool | None = None,
    prior_authority: object | None = None,
) -> bool:
    """Whether recovery completion revives any prior authority — never (§21/§19; SBR-INV-014).

    SBR-INV-014 line 198 verbatim: "Recovery completion, health restoration, human
    acknowledgement, replay match, or evidence repair never revives prior authority; fresh
    governed re-arm is mandatory." Realized as an **unconditional** ``True`` with every
    revival input **accepted and discarded** (isomorphic to the authority
    ``recovery_generation_revives_nothing`` ``predicates.py:787`` / rcl ``predicates.py:802``
    / spg ``rollback_revives_nothing`` replica pattern, design #17 §0.4d): no revival input
    can influence the answer because the answer never reads them — the model provides **no**
    generation-increase → authority-restoration operation at all, and this predicate documents
    and fixes that absence. A lawful re-arm always requires a fresh artifact plus a governed
    ADR-002-007/015 re-arm workflow (§21 handoff), never a revival of the old one; that
    workflow is runtime (§3.5). Replay match cannot retroactively make a permissive start safe
    (§23.10 line 604).

    Returns:
        ``True`` — nothing revives a prior authority (unconditionally).
    """
    del completion_signal, health_recovered, evidence_repaired
    del replay_matched, human_acknowledged, prior_authority
    return True


# ===========================================================================
# predicate-only §6.1 — closed startup (SBR-EV-001 substrate, min EV-L2)
# ===========================================================================


def start_closed(
    barrier: RecoveryBarrierState | None,
    live_arming_chain_complete: bool | None,
) -> bool:
    """Whether new-risk transmission is denied at start (§8/§9; SBR-INV-001/002).

    SBR-INV-001 line 146 / §1 line 15: "Every Safety Cell begins with new-risk authority
    denied until a current recovery barrier and the separate complete live-arming chain are
    positively satisfied." §9 line 257: "No barrier state alone permits live transmission" —
    every :class:`~tos.sbr.vocabulary.RecoveryBarrierState` is a ``CLOSED_*`` denial-context
    label, so the **only** thing that could lift the denial is a positively-complete
    live-arming chain (a separate fresh chain, §21 handoff — SBR-AC-001 line 638 "no new-risk
    first byte before a complete fresh live-arming chain"). Returns ``True`` (start is
    **closed** / denied) whenever the chain is not positively complete, and — because a
    barrier is never a permission — a ``None`` / unrecognized barrier is also denied. The
    barrier-ordering and fresh-chain **enforcement** is EV-L2 component fault (§1); L1 is the
    "closed-start, chain-incomplete => denied" predicate only.

    Args:
        barrier: The recovery barrier state (``None`` / unrecognized => denied).
        live_arming_chain_complete: Whether the separate live-arming chain is positively
            complete (only ``True`` lifts the denial).

    Returns:
        ``True`` iff new-risk is denied (start is closed).
    """
    if not isinstance(barrier, RecoveryBarrierState):
        return True  # unknown / absent barrier => denied (fail-closed)
    return live_arming_chain_complete is not True


# ===========================================================================
# predicate-only §6.2 — stale generation rejected at egress (SBR-EV-002, +Security)
# ===========================================================================


def stale_generation_rejected_at_egress(
    request_generation: int | None,
    current_generation: int | None,
    current_actively_established: bool | None,
) -> bool:
    """Whether a new-risk egress request must be rejected on generation grounds (§9; SBR-INV-004).

    §9 line 268 verbatim: "Final egress SHALL reject any new-risk request when the current
    Recovery Generation cannot be positively verified, the request references an older
    generation, the barrier is closed, or readiness is absent/invalid." §9 line 270 /
    SBR-INV-004 line 160: cache / TTL / heartbeat / service-health / absence never proves
    currentness — "inability to actively establish current state at authority issuance or
    final egress is denial." Returns ``True`` (**reject**) when:

    * currentness is not **actively** established (``current_actively_established is not True``
      — a cache / heartbeat / absence fails closed); or
    * either generation is unverifiable (``None``); or
    * the request references a **different** generation — an **older** one is stale, and a
      **newer** one is an unrecognized future generation (the §4.3 coordinate non-collapse:
      substituting another coordinate's value never matches).

    Returns ``False`` (admit) **only** when the request references exactly the current
    generation **and** currentness is actively established. The active-currentness protocol
    itself is ADR-002-024 runtime (+Security, §6.2); L1 is the order-comparison + active-
    establish predicate only (the monotonic generation order is REUSED from ``tos.ordering``).

    Args:
        request_generation: The request's referenced generation (``None`` => reject).
        current_generation: The current Recovery Generation (``None`` => reject).
        current_actively_established: Whether currentness is actively established (``None`` /
            ``False`` => reject).

    Returns:
        ``True`` iff the request must be rejected at egress.
    """
    if current_actively_established is not True:
        return True
    if request_generation is None or current_generation is None:
        return True
    return request_generation != current_generation


# ===========================================================================
# predicate-only §6.3 — competing recovery owner fencing (SBR-EV-003, +Security)
# ===========================================================================


def competing_owner_fenced(
    owner_epoch: int | None,
    current_owner_epoch: int | None,
    owner_status: OwnerStatus,
) -> bool:
    """Whether the owner is the single fenced current owner (§11; SBR-INV-004).

    §11 line 303-304 verbatim: "only one current owner may advance a session or publish a
    decision for overlapping scope; minority, stale, paused, restored, removed, or partitioned
    owners are rejected." §11 line 305: "leader election, database primary status, lock TTL,
    cache ownership, heartbeat health, or broker reachability alone is insufficient fencing."
    Returns ``True`` (**fenced / admissible**) **only** when the owner status is positively
    :attr:`~tos.sbr.vocabulary.OwnerStatus.CURRENT` **and** the owner epoch is concrete and
    equals the current owner epoch; a minority / stale / paused / restored / removed /
    partitioned status, or a ``None`` / mismatched epoch, is rejected (an unavailable former
    owner remains potentially active until fenced, §11 line 309). The real owner-epoch /
    quorum / split-brain fencing is ADR-002-012 SCL runtime (+Security, §11 line 311); L1 is
    the owner-status predicate only.

    Args:
        owner_epoch: The owner's epoch (``None`` => not fenced).
        current_owner_epoch: The current owner epoch (``None`` => not fenced).
        owner_status: The owner's status (only ``CURRENT`` is admissible).

    Returns:
        ``True`` iff the owner is the single current fenced owner.
    """
    if owner_status is not OwnerStatus.CURRENT:
        return False
    if owner_epoch is None or current_owner_epoch is None:
        return False
    return owner_epoch == current_owner_epoch


# ===========================================================================
# predicate-only §6.4 — non-atomic broker conservatism (SBR-EV-005, +Broker)
# ===========================================================================


def non_atomic_broker_conservative(
    reads: BrokerReadSequence | None,
    intervening_events: frozenset[str],
) -> bool:
    """Whether a non-atomic broker inventory is treated conservatively (§12/§14; SBR-INV-007).

    SBR-INV-007 line 170 verbatim: "One broker query, flat position, cache agreement, absent
    page result, missing ACK, or cancel ACK cannot establish completeness, non-acceptance,
    Final Quantity Proof, or capacity release." §12 line 333: "Equality between two reads does
    not prove that an unobservable event did not occur." Returns ``True`` (**conservatism
    holds**) **only** when:

    * the read sequence exists; and
    * **bounded convergence** is positively proven (re-read until stable — not a single
      optimistic read); and
    * the field-specific proof is positively stable across reads (§12 line 333); and
    * if there are any ``intervening_events``, they were positively reflected
      (``reads.intervening_events_reflected is True``) — equality between reads is not proof
      that no intervening unobservable event occurred.

    SBR does **not** own the Final Quantity Proof / per-field confidence (recon /
    ADR-002-006/004, +Broker) or the broker page / cursor protocol (§27 q4 runtime, §3.5); L1
    is the "single read ↛ completeness" conservatism predicate only.

    Args:
        reads: The observed broker read sequence (``None`` => ``False``).
        intervening_events: The events that may have intervened between reads (any unreflected
            => ``False``).

    Returns:
        ``True`` iff completeness rests on bounded, stable convergence, not an optimistic read.
    """
    if reads is None:
        return False
    if reads.bounded_convergence_proven is not True:
        return False
    if reads.field_specific_proof_stable is not True:
        return False
    # Equality between reads is not proof — any intervening event must be reflected (§12 line 333).
    return not (intervening_events and reads.intervening_events_reflected is not True)


# ===========================================================================
# predicate-only §6.5 — HALT dominance over recovery (SBR-EV-008, +Security)
# ===========================================================================


def halt_dominates_recovery(
    halt_applied: bool | None,
    dominating_halt_or_incident: bool | None,
    safety_owned_protection_present: bool | None,
) -> bool:
    """Whether a HALT / safety-owned restriction dominates recovery (§15; SBR-INV-009).

    SBR-INV-009 line 178 / §15 line 408 verbatim: "Recovery cannot clear, outrank, defer, or
    reinterpret HALT. ... Where HALT application is ambiguous, treat it as applied until
    reconciled under fresh governance." §15 line 406: "Existing safety-owned protection SHALL
    NOT be cancelled for cleanup, session reset, deployment convenience, or to obtain a clean
    snapshot." Returns ``True`` (**HALT / protection dominates — recovery is blocked and must
    respect it**) when:

    * ``halt_applied`` is not positively ``False`` (``True`` or an **ambiguous** ``None`` =>
      applied, the fail-closed direction §15 line 408); or
    * a dominating halt / incident is present (``dominating_halt_or_incident`` not positively
      ``False`` — the injected protective ``dominating_halt_or_incident`` coordinate,
      ``protective/records.py:202``); or
    * safety-owned protection is present (``safety_owned_protection_present`` not positively
      ``False`` — recovery cleanup may not cancel it, §15 line 406).

    Returns ``False`` **only** when HALT is positively not applied, no dominating incident, and
    no safety-owned protection — recovery is not dominated. Evidence / journal failure does not
    block the restriction (SBR-AC-008 line 645). HALT-downgrade classification / the
    Cancellation Arbiter / the emergency latch are protective / ADR-002-011/015 owned
    (+Security, §3.5); L1 is the "HALT dominates, ambiguous => applied, safety-owned no-cancel"
    predicate only.

    Args:
        halt_applied: Whether HALT is applied (``True`` / ``None`` => applied/ambiguous).
        dominating_halt_or_incident: The injected protective dominance coordinate.
        safety_owned_protection_present: Whether safety-owned protection is present.

    Returns:
        ``True`` iff a HALT / safety-owned restriction dominates recovery.
    """
    if halt_applied is not False:
        return (
            True  # applied or ambiguous (None) => dominates (fail-closed, §15 line 408)
        )
    if dominating_halt_or_incident is not False:
        return True
    return safety_owned_protection_present is not False


# ===========================================================================
# predicate-only §6.6 — restore worst-credible union (SBR-EV-010, +Security)
# ===========================================================================


def restore_worst_credible_union(
    branches: frozenset[str],
    selection_basis: SelectionBasis | None,
    credible_union: object | None,
) -> bool:
    """Whether a restore preserves all branches under the worst credible union (§20; SBR-INV-013).

    §20 line 496-497 verbatim: "compute the worst credible union of economic effects and
    capacity consumption" and "select no branch by recency label, backup success,
    administrator choice, or wall-clock timestamp alone." §20 line 503: "An older backup may
    be recovery input but cannot become authority merely because it is available." Returns
    ``True`` (**worst-credible-union restore is proper**) **only** when:

    * ``branches`` is non-empty (an empty branch set fails closed — no history to union); and
    * **no** single-basis selection was used (``selection_basis is None`` — any
      :class:`~tos.sbr.vocabulary.SelectionBasis` of ``RECENCY`` / ``BACKUP_SUCCESS`` /
      ``ADMIN_CHOICE`` / ``WALL_CLOCK`` rejects the restore); and
    * the ``credible_union`` is present — the worst-credible economic union produced by rcl
      ``credible_union_capacity`` (``rcl/predicates.py:739``; "requires at least one
      reconstructable history", ``:770``), consumed by SBR as an injected object (SBR does
      **not** re-author the capacity-union arithmetic — capacity is rcl-only, SBR-INV-010).

    Conflicting branches keep the affected scope non-live (§20 line 503); a multi-branch
    same-id / different-bytes conflict is detected by canonical ``classify_record_pair``
    ``CRITICAL_CONFLICT`` (§2.1). The predecessor fencing is +Security runtime (§20 line 495,
    §3.5); L1 is the branch-selection-forbidden + union-consumed predicate only.

    Args:
        branches: The conflicting restore branches (empty => ``False``).
        selection_basis: The single basis a branch was selected by (any non-``None`` =>
            ``False``).
        credible_union: The rcl-produced worst-credible union (``None`` => ``False``).

    Returns:
        ``True`` iff all branches are preserved under the worst credible union.
    """
    if not branches:
        return False
    if selection_basis is not None:
        return False
    return credible_union is not None


# ===========================================================================
# predicate-only §6.7 — recovery authority separation (SBR-EV-011, +Security)
# ===========================================================================


def recovery_authority_separated(
    effect: RecoveryAuthorityEffect | None,
    forced_ready_requested: bool | None,
) -> bool:
    """Whether recovery grants no authority and no forced ready was requested (§7/§21; SBR-INV-003).

    SBR-INV-003 line 154 verbatim: "No Recovery Session, package, obligation result, readiness
    decision, operator action, health result, or replay result creates capacity, Live
    Authorization, capability, protective classification, broker transmission, or re-arm
    permission." §19 line 483 / §21 line 517-526: "Operator requests forced ready | reject;
    operator may HALT or request governed containment only", and a human "SHALL NOT ... convert
    READY or READY_RESTRICTED into Live Authorization" or "mutate/release RCL capacity"
    (capacity is rcl-only, SBR-INV-010 line 182). Returns ``True`` (**authority is separated**)
    **only** when the effect exists, no forced-ready was requested
    (``forced_ready_requested is False`` — a ``True`` / ``None`` rejects), and every authority
    flag is ``False``. Because :class:`~tos.sbr._base.RecoveryAuthorityEffect` is
    unconstructable with any ``True`` flag, a *validated* effect always separates authority —
    this is the defining predicate that states it, and the defence-in-depth re-check for a
    block that reached the consumer via an unvalidated ``model_construct`` path. The real SoD /
    bypass-path / common-effective-control proof is +Security runtime (§7 line 220, §3.5).

    Args:
        effect: The recovery authority effect (``None`` => ``False``).
        forced_ready_requested: Whether a forced-ready was requested (``True`` / ``None`` =>
            ``False``).

    Returns:
        ``True`` iff recovery grants no authority and no forced-ready was requested.
    """
    if effect is None:
        return False
    if forced_ready_requested is not False:
        return False
    return not (
        effect.creates_capacity
        or effect.issues_live_auth
        or effect.issues_capability
        or effect.classifies_protective
        or effect.transmits_broker
        or effect.grants_rearm
    )
