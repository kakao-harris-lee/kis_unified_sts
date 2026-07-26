"""afg action-flow decision predicates + the produced-seam producers (design #16 §5/§6).

Pure, fail-closed decision rules over injected frozen models (design #16 §0.2/§4.6): afg
is **not** a capacity engine and **not** a rate limiter — the capacity arithmetic,
serialization, and the atomic economic + action-flow commit are rcl-owned (ADR-002-022 §1
line 19 "The Risk Capacity Ledger is the sole serialization and mutation authority for
every governed action-flow capacity dimension"; AFG-INV-004). afg authors the
**complete-scope / bounded-amplification / exact-binding / no-manufactured-refill /
no-blind-retry / reserve-exclusivity / currentness / non-revival** decision rules and
combines injected magnitudes only by comparison. There is **no** "assume-zero" /
"assume-within" / "assume-grant" path anywhere: a positive result comes only from positive
proof, everything else is ``UNKNOWN`` / ``DENY`` / ``False`` (design #16 §4.1 — the
structural seal against the #6 fail-open lesson).

**Truthy-sentinel discipline (design #16 §2.2-1, both axes).** Every
:class:`~tos.afg.vocabulary.ActionFlowResult` member is a truthy ``StrEnum``, so every
gate here tests ``result is ActionFlowResult.GRANT`` (identity), never ``if result:``.
Injected protective ``Admissibility`` verdicts are 3-token StrEnums (M2 — **not**
``bool | None``), so their gate admits only the ``ADMISSIBLE`` token; ``TRAPPED`` /
``PROHIBITED`` / ``None`` all deny. Injected ``bool | None`` flags are normalized with
``is True`` / ``is not True`` (the orthostate ``predicates.py:461`` precedent).

The module is split by role:

* **core §5** — ``scope_graph_complete`` / ``shared_limit_conservative`` /
  ``envelope_not_enlarged`` / ``amplification_bounded`` / ``cause_lineage_complete`` /
  ``changed_command_is_new_action`` / ``headroom_within_limits`` /
  ``atomic_economic_flow_coverage`` / ``action_flow_decision``
  (AFG-EV-001/002/007 substrate).
* **predicate-only §6** — ``no_blind_retry`` (§6.1),
  ``cancel_ack_not_final_quantity_proof`` / ``oscillation_bounded`` (§6.2, the AFG-EV-004
  core L1 slice whose ``+Broker`` integration is deferred), ``action_class_conservative``
  (§6.3), ``reserve_exclusive`` / ``priority_is_not_reserve`` (§6.4),
  ``partition_lease_exclusive`` (§6.6), ``governor_grants_no_authority`` (§6.7). The
  §5.4 / §5.3-lifecycle / §6.5 / §6.8 temporal predicates live in :mod:`tos.afg.state`.
* **produced rcl seam (§3.4)** — ``decision_content_ref`` /
  ``applicable_action_flow_scopes_of`` / ``action_flow_vector_of``. Every produced value
  has a **defining predicate** here (design #16 §3.4(b) — no produced value without a
  definition, and no phantom slot for a sibling field that does not exist).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` + the rcl ``CapacityVector`` type
and its ``aggregate_usage`` / ``effective_limit`` arithmetic only; no ``shared.*``, no
other sibling ``tos.*`` (design #16 §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.afg.records import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionFlowDecision,
    ActionFlowGovernorEffect,
    ActionFlowPolicy,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    ObservedAmplification,
    ProtectiveFlowReserveClaim,
)
from tos.afg.vocabulary import (
    ADMISSIBILITY_ADMISSIBLE,
    ATTEMPT_STATE_SEND_FAILED_PROVEN,
    BROKER_ORDER_STATE_UNKNOWN,
    RESERVED_GUARANTEE_TOKENS,
    ActionClassKind,
    ActionFlowResult,
    ActionFlowScopeKind,
    DocumentedScopeStatus,
    broadest_scope,
    is_action_flow_dimension_id,
    most_conservative_action_class,
    narrowest_scope,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityVector, aggregate_usage, effective_limit

__all__ = [
    # core §5.1 — scope graph / shared limits / no local headroom
    "scope_graph_complete",
    "shared_limit_conservative",
    "envelope_not_enlarged",
    # core §5.2 — amplification / cause lineage
    "amplification_bounded",
    "cause_lineage_complete",
    "changed_command_is_new_action",
    # core §5.3 — headroom / atomic coverage / decision issuance
    "headroom_within_limits",
    "atomic_economic_flow_coverage",
    "action_flow_decision",
    # predicate-only §6
    "no_blind_retry",
    "cancel_ack_not_final_quantity_proof",
    "oscillation_bounded",
    "action_class_conservative",
    "reserve_exclusive",
    "priority_is_not_reserve",
    "partition_lease_exclusive",
    "governor_grants_no_authority",
    # produced rcl seam (§3.4)
    "decision_content_ref",
    "applicable_action_flow_scopes_of",
    "action_flow_vector_of",
]


# ===========================================================================
# core §5.1 — scope-graph completeness + no local headroom (AFG-EV-001 substrate)
# ===========================================================================


def scope_graph_complete(
    snapshot: ActionFlowStateSnapshot | None,
    required_scopes: frozenset[ActionFlowScopeKind],
    *,
    producer_self_declared_scope: bool | None,
) -> bool:
    """Whether the scope graph is complete over every applicable shared scope (§10).

    AFG-INV-001 line 157 / §1 line 25: "Action flow SHALL be bounded over every applicable
    shared scope ... A component may not select a narrower scope merely because it cannot
    observe another producer or because a broker documents limits incompletely." ``True``
    **only** when:

    1. the snapshot exists (a ``None`` snapshot proves nothing);
    2. ``required_scopes`` is **non-empty** — a vacuous "complete over nothing" is not
       completeness, and an empty scope set means the shared limit cannot be established,
       so it fails closed (design #16 §4.7; the §1 line 25 unknown-dependency rule then
       expands to the smallest conservative containing scope, see
       :func:`shared_limit_conservative`);
    3. ``producer_self_declared_scope`` is positively ``False`` — §8 line 248 forbids
       delegating materiality / scope / reserve classification to a producer, so a
       producer-declared scope (or an unknown ``None``) fails closed;
    4. every required scope is covered by the snapshot (an omitted scope fails closed —
       "account-local success is not credential / session / IP / route / broker-global
       independence", §10 line 276);
    5. every required scope carries positive independence evidence on **all six** §10 line
       278 axes (:meth:`~tos.afg.records.ScopeIndependenceEvidence.is_independent` —
       allocation / refill / broker-enforcement / **credential-session-state** /
       failure-domain / final-route separation). A local counter, separate process, or
       scheduler priority creates **no** headroom (the rcl ``records.py:127-128``
       isomorph), so an evidence record whose basis is local-counter-only / priority-only
       fails closed.

    Args:
        snapshot: The action-flow state snapshot (``None`` => ``False``).
        required_scopes: The applicable shared scopes that MUST be covered (empty =>
            fail-closed).
        producer_self_declared_scope: Whether the scope was self-declared by the producer
            (only a positive ``False`` passes, §8 line 248).

    Returns:
        ``True`` iff the scope graph is complete and every scope is evidenced independent.
    """
    if snapshot is None:
        return False
    if not required_scopes:
        return False
    if producer_self_declared_scope is not False:
        return False
    covered = frozenset(snapshot.covered_scopes)
    if not required_scopes <= covered:
        return False
    for scope in required_scopes:
        evidence = snapshot.independence_for(scope)
        if evidence is None or not evidence.is_independent():
            return False
    return True


def shared_limit_conservative(
    documented_scope_status: DocumentedScopeStatus | str | None,
    claimed_scope: ActionFlowScopeKind | None,
    credible_containing_scopes: frozenset[ActionFlowScopeKind],
    independence_evidence: bool | None,
) -> ActionFlowScopeKind | ActionFlowResult:
    """The conservative scope a shared limit is enforced over (design #16 §5.1, C1).

    **Two conservative rules that point in opposite directions** (C1 — the v1.0 fail-open
    transcription of §10 line 276 as "smallest" was the CRITICAL defect this predicate
    seals):

    1. **Broker documentation not verified-complete** (incomplete / contradictory / stale /
       unverified / ``None`` / any unrecognized token) => the limit is "treated as shared
       across the **largest** credible containing scope" (§10 line 276). Sharing the limit
       as widely as credible is conservative: it prevents two producers each believing
       they own a private budget.
    2. **Independence not positively evidenced** (``independence_evidence is not True``)
       => the claimed scope is not trusted and the limit expands to the **smallest**
       conservative containing scope (§1 line 25 "Unknown dependency or limit scope expands
       to the smallest conservative containing scope and blocks new normal risk").

    The claimed scope is kept **only** when the documentation is positively
    ``VERIFIED_COMPLETE`` **and** independence is positively evidenced. An empty
    ``credible_containing_scopes`` yields ``ActionFlowResult.UNKNOWN`` — no containing
    scope can be established, and UNKNOWN is restrictive, never permissive (design #16
    §4.7; AFG-INV-007 line 181).

    **Truthy seal:** the returned union is ``ActionFlowScopeKind | ActionFlowResult`` and
    *both* arms are truthy ``StrEnum`` members, so a consumer MUST test
    ``verdict is ActionFlowResult.UNKNOWN`` (identity), never a bare truthiness check.

    Args:
        documented_scope_status: The broker's documented-scope status (only
            :attr:`~tos.afg.vocabulary.DocumentedScopeStatus.VERIFIED_COMPLETE` is
            positive; ``None`` / any other token widens).
        claimed_scope: The scope the component claims the limit applies to.
        credible_containing_scopes: The credible containing scopes (empty => ``UNKNOWN``).
        independence_evidence: Whether independence is positively evidenced (``None`` /
            ``False`` => expand).

    Returns:
        The governing :class:`~tos.afg.vocabulary.ActionFlowScopeKind`, or
        ``ActionFlowResult.UNKNOWN`` when no conservative scope can be established.
    """
    if not credible_containing_scopes:
        return ActionFlowResult.UNKNOWN

    # §10 line 276 — unverified / incomplete broker documentation => LARGEST credible scope.
    if documented_scope_status is not DocumentedScopeStatus.VERIFIED_COMPLETE:
        widest = broadest_scope(credible_containing_scopes)
        return widest if widest is not None else ActionFlowResult.UNKNOWN

    # §1 line 25 — unknown dependency / unproven independence => SMALLEST containing scope.
    if independence_evidence is not True:
        smallest = narrowest_scope(credible_containing_scopes)
        return smallest if smallest is not None else ActionFlowResult.UNKNOWN

    # Documented verified-complete AND independence evidenced => the claim stands.
    if claimed_scope is None:
        return ActionFlowResult.UNKNOWN
    return claimed_scope


def envelope_not_enlarged(
    *,
    requested_limit: CapacityVector,
    injected_envelope_max: CapacityVector | None,
    limit_source_is_injected_envelope: bool | None,
) -> bool:
    """Whether the admission limit does not enlarge the Hard Safety Envelope (§8 line 248).

    §8 line 248 verbatim: runtime configuration "may narrow ... but cannot enlarge" the
    envelope. ``True`` **only** when the limit source is positively the injected envelope
    (a runtime / broker / model / strategy source fails closed), the injected envelope is
    present, and every requested dimension is declared by the envelope and ``<=`` its
    maximum. A ``None`` on either side, or a requested value above the envelope maximum,
    fails closed. Unenumerated (non-afg) dimension ids also fail closed — an unknown
    dimension is ``UNKNOWN``, never unbounded (design #16 §2.2-4/§4.1).

    An **empty** ``requested_limit`` declares zero dimensions — zero headroom, the most
    restrictive possible bound, never a wildcard — so it enlarges nothing and returns
    ``True`` *only after* the positive source gate has passed (the are
    ``envelope_bound_not_enlarged`` precedent).

    Args:
        requested_limit: The limit the admission would apply.
        injected_envelope_max: The injected Hard Safety Envelope maxima (``None`` =>
            fail-closed).
        limit_source_is_injected_envelope: Whether the limit came from the injected
            envelope (``None`` / ``False`` => fail-closed).

    Returns:
        ``True`` iff the requested limit does not enlarge the injected envelope.
    """
    if injected_envelope_max is None:
        return False
    if limit_source_is_injected_envelope is not True:
        return False
    for component in requested_limit.components:
        dimension = component.dimension_id
        if not is_action_flow_dimension_id(dimension):
            return False
        requested = component.magnitude
        if requested is None:
            return False
        envelope_max = injected_envelope_max.magnitude(dimension)  # type: ignore[arg-type]
        if envelope_max is None:
            return False
        if requested > envelope_max:
            return False
    return True


# ===========================================================================
# core §5.2 — bounded amplification + cause lineage (AFG-EV-002 substrate)
# ===========================================================================

#: The (envelope bound, observed count) field pairs that must both be concrete and
#: satisfy ``observed <= bound`` (§11 line 284-292). Every axis is governed: an
#: undeclared bound is *unbounded* and an unobserved count is *unknown*, and §5.8 line 141
#: makes both a denial.
_AMPLIFICATION_AXES: tuple[tuple[str, str], ...] = (
    ("max_fan_out", "fan_out"),
    ("max_depth", "depth"),
    ("max_attempts", "attempts"),
    ("max_mutations", "mutations"),
    ("max_queries", "queries"),
    ("max_queue_depth", "queue_depth"),
    ("max_in_flight", "in_flight"),
    ("max_elapsed_monotonic", "elapsed_monotonic"),
    ("max_duplicate_redelivery_expansion", "duplicate_redelivery_expansion"),
    (
        "max_failover_reconnect_replay_expansion",
        "failover_reconnect_replay_expansion",
    ),
    ("max_amplification_per_cause", "amplification_per_cause"),
)


def amplification_bounded(
    envelope: ActionAmplificationEnvelope | None,
    observed: ObservedAmplification | None,
) -> bool:
    """Whether every amplification axis stays within its injected bound (§11; AFG-INV-002).

    §5.8 line 141 verbatim: "unknown or unbounded amplification is denial." ``True``
    **only** when:

    * both the envelope and the observation exist;
    * **every** axis carries a concrete injected bound (an ``None`` bound is *unbounded*
      — the ∅-envelope guard, design #16 §4.7) and a concrete observed count (an unknown
      count is *unknown*);
    * every observed count is ``<=`` its bound (fan-out, depth, attempts, mutations,
      queries, queue depth, in-flight, elapsed monotonic time, duplicate / redelivery
      expansion, failover / reconnect / replay expansion, per-cause amplification —
      §11 line 284-292);
    * ``duplicate_event_created_new_allowance`` is positively ``False`` and
      ``envelope_reset_on_duplicate`` is positively ``False`` — "A duplicate event does
      not create another allowance" (§11 line 294), so a repeated observation of the same
      root cause can never reset the budget;
    * ``concurrent_consumers_share_one_envelope`` is positively ``True`` — "Concurrent
      consumers of the same cause share one envelope" (§11 line 294).

    Every bound is **injected** (design #16 §8; VP-002
    ``MAX_action_amplification_per_cause`` is present-and-null) — nothing numeric is
    hardcoded here.

    Args:
        envelope: The injected amplification envelope (``None`` => ``False``).
        observed: The observed amplification counts (``None`` => ``False``).

    Returns:
        ``True`` iff amplification is positively bounded on every axis.
    """
    if envelope is None or observed is None:
        return False
    if observed.duplicate_event_created_new_allowance is not False:
        return False
    if observed.envelope_reset_on_duplicate is not False:
        return False
    if observed.concurrent_consumers_share_one_envelope is not True:
        return False
    for bound_field, observed_field in _AMPLIFICATION_AXES:
        bound = getattr(envelope, bound_field)
        count = getattr(observed, observed_field)
        if bound is None or count is None:
            return False
        if count > bound:
            return False
    return True


def cause_lineage_complete(cause: ActionCause | None) -> bool:
    """Whether the cause carries a root identity and a complete parent lineage (§11:284).

    §11 line 284: every action carries an immutable root-cause identity and a **complete**
    parent lineage. ``True`` **only** when the cause exists, the root identity is concrete,
    the parent lineage is **non-empty** (an empty lineage is UNKNOWN, never "no parents
    therefore complete" — design #16 §4.7), completeness is positively attested, and the
    three defect witnesses (cyclic / forked-beyond-bound / inconsistent) are each
    positively ``False``. A missing, cyclic, forked-beyond-bound, or inconsistent lineage
    is ``False`` here and drives the decision to ``UNKNOWN`` + containment (§11 line 296;
    :func:`action_flow_decision`).

    Args:
        cause: The action cause (``None`` => ``False``).

    Returns:
        ``True`` iff the root cause and its complete parent lineage are established.
    """
    if cause is None:
        return False
    if cause.root_cause_identity is None or cause.root_cause_identity == "TBD":
        return False
    if not cause.parent_lineage:
        return False
    if cause.lineage_attested is not True:
        return False
    if cause.cyclic is not False:
        return False
    if cause.forked_beyond_bound is not False:
        return False
    return cause.inconsistent is False


def changed_command_is_new_action(
    *,
    command_changed: bool | None,
    fresh_cause_and_artifacts: bool | None,
) -> bool:
    """Whether a changed command was treated as a **new** action (§11 line 294; AFG-AC-002).

    §11 line 294: a change to quantity, price, route, account, instrument, action class,
    effect, session, credential, or broker identity makes the command a **new** action
    requiring fresh construction, risk, flow, authority, and capability — it is never a
    continuation of the previous allowance. ``True`` when:

    * the command positively did **not** change (``command_changed is False``) — nothing
      to re-derive; or
    * the command changed **and** fresh cause + artifacts were positively produced.

    An unknown (``None``) change status, or a changed command without positively fresh
    artifacts, fails closed.

    Args:
        command_changed: Whether the command changed (``None`` => fail-closed).
        fresh_cause_and_artifacts: Whether a fresh cause + fresh artifacts were produced.

    Returns:
        ``True`` iff the change discipline holds.
    """
    if command_changed is False:
        return True
    if command_changed is not True:
        return False
    return fresh_cause_and_artifacts is True


# ===========================================================================
# core §5.3 — headroom + atomic economic/flow coverage (AFG-EV-007 substrate)
# ===========================================================================


def headroom_within_limits(
    usage_vectors: Sequence[CapacityVector],
    hard_limit: CapacityVector | None,
    runtime_limit: CapacityVector | None,
) -> ActionFlowResult:
    """Whether aggregate action-flow usage stays within the effective limit (§13 item 6).

    The headroom check REUSES the rcl arithmetic rather than re-deriving it (design #16
    §0.4c reason 2): ``aggregate_usage`` (``vector.py:103``) sums dimension-wise and
    propagates ``None`` as UNKNOWN (``:132``), and ``effective_limit`` (``:139``) is
    ``min(hard, runtime)`` with ``None`` on either side yielding ``None`` (``:164``) —
    "The Runtime Safety Profile may reduce but never enlarge the Hard Safety Envelope."
    Reusing them removes any chance of transposing the inequality (the #6 lesson).

    **Direction (design #16 §4.1 item 3):** admission requires
    ``aggregate_usage <= effective_limit`` per dimension. Truth table: usage ``None`` =>
    ``UNKNOWN``; limit ``None`` => ``UNKNOWN``; ``usage <= limit`` => pass;
    ``usage > limit`` => ``DENY``.

    An **empty** ``usage_vectors``, an empty aggregate, an absent limit vector, or an
    unenumerated (non-afg) dimension id all yield ``UNKNOWN`` — never a vacuous pass
    (design #16 §4.7/§2.2-4).

    Args:
        usage_vectors: The committed + proposed action-flow usage vectors.
        hard_limit: The Hard Safety Envelope limit vector (``None`` => ``UNKNOWN``).
        runtime_limit: The Runtime Safety Profile limit vector (``None`` => ``UNKNOWN``).

    Returns:
        ``GRANT`` when every dimension is within its effective limit, ``DENY`` on a proven
        exceedance, else ``UNKNOWN``.
    """
    if not usage_vectors:
        return ActionFlowResult.UNKNOWN
    if hard_limit is None or runtime_limit is None:
        return ActionFlowResult.UNKNOWN

    usage = aggregate_usage(list(usage_vectors))
    limits = effective_limit(hard_limit, runtime_limit)
    dimension_ids = usage.dimension_ids()
    if not dimension_ids:
        return ActionFlowResult.UNKNOWN

    verdict = ActionFlowResult.GRANT
    for dimension in dimension_ids:
        if not is_action_flow_dimension_id(dimension):
            return ActionFlowResult.UNKNOWN
        used = usage.magnitude(dimension)
        limit = limits.magnitude(dimension)
        if used is None or limit is None:
            return ActionFlowResult.UNKNOWN
        if used > limit:
            verdict = ActionFlowResult.DENY
    return verdict


def atomic_economic_flow_coverage(
    economic_ref: str | None,
    flow_vector: ActionFlowVector | None,
    *,
    committed_flow_vectors: Sequence[CapacityVector] = (),
    hard_limit: CapacityVector | None = None,
    runtime_limit: CapacityVector | None = None,
    economic_commitment_exclusive: bool | None = None,
    flow_commitment_exclusive: bool | None = None,
) -> ActionFlowResult:
    """Whether economic **and** action-flow coverage are both established (AFG-INV-005).

    AFG-INV-005 line 173 / §13 line 330: the RCL must "commit both in one deterministic
    transaction or ... cannot leave a live-send-capable partial state". This is the
    **both, not either** rule (design #16 §2.2-5): the economic vector and the action-flow
    vector must **both** be exclusively committed, or neither. ``GRANT`` **only** when:

    * ``economic_ref`` is concrete (an absent economic commitment reference means the
      economic half is unproven => no permit, §13 line 330);
    * ``flow_vector`` exists and declares at least one dimension (an **empty** flow vector
      cannot prove coverage => restrictive, design #16 §4.7);
    * both exclusivity witnesses are positively ``True`` (neither half may be "committed"
      non-exclusively);
    * :func:`headroom_within_limits` over the committed + proposed vectors is ``GRANT``.

    Anything unproven yields ``UNKNOWN``; a proven exceedance yields ``DENY``. The **atomic
    transaction itself is rcl runtime** (ADR §29 q2 — the non-cyclic commit protocol);
    afg only decides whether both coverages are established. Note the §13 line 342 release
    asymmetry, realized in :func:`~tos.afg.state.economic_effect_persists`: "Releasing
    action-flow capacity never releases economic capacity without its separate Final
    Quantity Proof rules."

    Args:
        economic_ref: The economic-capacity commitment reference (``None`` => ``UNKNOWN``).
        flow_vector: The proposed action-flow vector (``None`` / empty => ``UNKNOWN``).
        committed_flow_vectors: Already-committed action-flow usage vectors.
        hard_limit: The Hard Safety Envelope limit vector.
        runtime_limit: The Runtime Safety Profile limit vector.
        economic_commitment_exclusive: Whether the economic commitment is exclusive.
        flow_commitment_exclusive: Whether the flow commitment is exclusive.

    Returns:
        ``GRANT`` iff both coverages are established and within limits, else ``DENY`` /
        ``UNKNOWN``.
    """
    if economic_ref is None or economic_ref == "TBD":
        return ActionFlowResult.UNKNOWN
    if flow_vector is None or not flow_vector.dimension_ids():
        return ActionFlowResult.UNKNOWN
    if economic_commitment_exclusive is not True:
        return ActionFlowResult.UNKNOWN
    if flow_commitment_exclusive is not True:
        return ActionFlowResult.UNKNOWN
    return headroom_within_limits(
        [*committed_flow_vectors, flow_vector], hard_limit, runtime_limit
    )


def _decide_action_flow_result(
    *,
    coverage: ActionFlowResult,
    scope_complete: bool,
    lineage_complete: bool,
    amplification_ok: bool,
    envelope_ok: bool,
    generation_current: bool,
    applicable_action_flow_scopes: tuple[str, ...],
) -> ActionFlowResult:
    """The pure GRANT / DENY / UNKNOWN verdict (§5.3/§13); restrictive-by-default.

    Gate order is deliberately **unknown-first**: every unproven premise resolves to
    ``UNKNOWN`` (which "consumes conservative capacity and blocks new normal risk",
    AFG-INV-007 line 181) before any ``DENY`` / ``GRANT`` conclusion is drawn, so a missing
    input can never be read as a proven rejection.

    **``GRANT`` is reached only by positive proof, never by fall-through (design #16 §4.1).**
    Two structural seals enforce that:

    1. *Every* boolean premise is gated with ``is not True`` — **not** ``if not X:``. The
       premises are ``bool``-typed by annotation only; Python does not enforce that at
       runtime, so a truthy non-``bool`` (``"UNKNOWN"``, ``1``, ``[1]``, even the string
       ``"False"``) would pass a ``if not X:`` gate and reach ``GRANT``. ``is not True``
       admits the singleton ``True`` and nothing else.
    2. The ``coverage`` verdict must be **positively** ``ActionFlowResult.GRANT``. Testing
       only for the ``UNKNOWN`` / ``DENY`` members and letting everything else fall through
       would make ``GRANT`` the residual outcome: a forged / raw-string / ``None`` coverage
       would be granted. The final gate therefore demands the ``GRANT`` member by identity
       (``ActionFlowResult`` is a truthy ``StrEnum``, so no truthiness test is admissible).
    """
    if scope_complete is not True:
        return ActionFlowResult.UNKNOWN
    if lineage_complete is not True:
        return ActionFlowResult.UNKNOWN
    if amplification_ok is not True:
        return ActionFlowResult.UNKNOWN
    if generation_current is not True:
        return ActionFlowResult.UNKNOWN
    if coverage is ActionFlowResult.UNKNOWN:
        return ActionFlowResult.UNKNOWN
    # An empty requested scope is restrictive, never a wildcard grant (§4.7).
    if not applicable_action_flow_scopes:
        return ActionFlowResult.DENY
    if envelope_ok is not True:
        return ActionFlowResult.DENY
    if coverage is ActionFlowResult.DENY:
        return ActionFlowResult.DENY
    # Positive-proof seal: anything that is not the GRANT member itself (a forged token, a
    # raw ``"GRANT"`` string, ``None``, ``0``, ``""``) is UNKNOWN — never a fall-through GRANT.
    if coverage is not ActionFlowResult.GRANT:
        return ActionFlowResult.UNKNOWN
    return ActionFlowResult.GRANT


def action_flow_decision(
    *,
    coverage: ActionFlowResult,
    scope_complete: bool,
    lineage_complete: bool,
    amplification_ok: bool,
    envelope_ok: bool,
    generation_current: bool,
    applicable_action_flow_scopes: tuple[str, ...],
    decision_id: str,
    decision_generation: int,
    scheme: CanonicalizationScheme,
    policy: ActionFlowPolicy | None = None,
    snapshot: ActionFlowStateSnapshot | None = None,
    action_class: ActionClassKind | None = None,
    action_flow_vector: ActionFlowVector | None = None,
    decision_effective_limit: ActionFlowVector | None = None,
    command_identity: str | None = None,
    command_digest: str | None = None,
    cause_digest: str | None = None,
    lineage_digest: str | None = None,
    amplification_envelope_digest: str | None = None,
    protective_classification_digest: str | None = None,
) -> ActionFlowDecision:
    """Decide GRANT / DENY / UNKNOWN and issue the forward-only decision (§5.4 / §13).

    The composer that turns the §5 core predicate results into the immutable, non-
    authorizing :class:`~tos.afg.records.ActionFlowDecision` (§5.4 line 123). Every
    unproven premise resolves to ``UNKNOWN``; an empty requested scope or an enlarged
    envelope is ``DENY``; ``GRANT`` requires positive proof on every premise, and even
    then "A ``GRANT`` is not capacity or permission to send" (§1 line 17) — the issued
    decision's ``authority_effect`` is all-false (AFG-INV-011).

    The decision is **forward-only** (design #16 §2.3/§5.3): it carries **no** permit /
    reservation / commitment coordinate, so the pipeline stays non-cyclic (rcl charges
    ``bound_reservation_*`` post-commit, ``authority.py:56-58``; ADR §29 q2). The
    ``scheme`` is the injected provisional canonicalizer (REUSE, §3.1; no new scheme).

    Args:
        coverage: The :func:`atomic_economic_flow_coverage` result.
        scope_complete: Whether :func:`scope_graph_complete` held.
        lineage_complete: Whether :func:`cause_lineage_complete` held.
        amplification_ok: Whether :func:`amplification_bounded` held.
        envelope_ok: Whether :func:`envelope_not_enlarged` held.
        generation_current: Whether :func:`~tos.afg.state.generation_fenced` held (a stale
            generation cannot allocate, consume, or transmit — AFG-INV-013 line 205).
        applicable_action_flow_scopes: The exact scopes the decision applies to (empty =>
            restrictive).
        decision_id: The evaluation-assigned independent decision identity (id ⊥ digest).
        decision_generation: The monotonic Action Flow Generation (required covered).
        scheme: The injected canonicalization scheme.
        policy: The bound policy (for the policy digest / generation).
        snapshot: The bound state snapshot (for the snapshot digest).
        action_class: The governing action class (see :func:`action_class_conservative`).
        action_flow_vector: The decided action-flow vector (the rcl ``CapacityVector``).
        decision_effective_limit: The decision's effective-limit vector.
        command_identity: The exact command identity scalar (no command bytes, §0.2).
        command_digest: The exact command digest scalar.
        cause_digest: The bound cause digest.
        lineage_digest: The bound lineage digest.
        amplification_envelope_digest: The bound amplification-envelope digest.
        protective_classification_digest: The injected protective classification digest.

    Returns:
        The issued forward-only :class:`~tos.afg.records.ActionFlowDecision`.
    """
    result = _decide_action_flow_result(
        coverage=coverage,
        scope_complete=scope_complete,
        lineage_complete=lineage_complete,
        amplification_ok=amplification_ok,
        envelope_ok=envelope_ok,
        generation_current=generation_current,
        applicable_action_flow_scopes=applicable_action_flow_scopes,
    )
    decision = ActionFlowDecision.issue(
        scheme=scheme,
        decision_id=decision_id,
        decision_generation=decision_generation,
        result=result,
        policy_digest=policy.canonical_digest if policy is not None else None,
        policy_generation=policy.policy_generation if policy is not None else None,
        snapshot_digest=snapshot.canonical_digest if snapshot is not None else None,
        cause_digest=cause_digest,
        lineage_digest=lineage_digest,
        command_identity=command_identity,
        command_digest=command_digest,
        action_class=action_class,
        applicable_action_flow_scopes=applicable_action_flow_scopes,
        action_flow_vector=(
            action_flow_vector if action_flow_vector is not None else ActionFlowVector()
        ),
        effective_limit=(
            decision_effective_limit
            if decision_effective_limit is not None
            else ActionFlowVector()
        ),
        amplification_envelope_digest=amplification_envelope_digest,
        protective_classification_digest=protective_classification_digest,
    )
    assert isinstance(decision, ActionFlowDecision)
    return decision


# ===========================================================================
# predicate-only §6.1 — no blind retry (AFG-EV-003 substrate)
# ===========================================================================


def no_blind_retry(
    attempt_state: str | None,
    broker_order_state: str | None,
    idempotency_proven: bool | None,
    budget_remaining: int | None,
    *,
    complete_evidence_capability_coverage_authority: bool | None = None,
    blind_failover_attempted: bool | None = None,
    retry_count: int | None = None,
    elapsed_ms: int | None = None,
    backoff_ms: int | None = None,
    repeated_identical_response: bool | None = None,
) -> bool:
    """Whether a **governed** (non-blind) retry is admissible (§14; AFG-INV-008).

    §14 line 350 verbatim: a missing ACK, timeout, reset, proxy failure, SDK exception,
    redirect, or rate-limit response is **not** proof of non-acceptance — the attempt stays
    **potentially live** (orthostate ``SENT_UNCONFIRMED``, ``vocabulary.py:86``). The only
    attempt-axis positive counterpart is ``SEND_FAILED_PROVEN`` (``:88``): positive
    evidence the broker did not and cannot accept. ``True`` **only** when:

    * ``attempt_state`` is exactly ``SEND_FAILED_PROVEN`` (every other state — including
      ``SENT_UNCONFIRMED`` and ``None`` — keeps the attempt potentially live);
    * ``broker_order_state`` is concrete and not ``UNKNOWN`` (an UNKNOWN broker order is
      capacity-consuming and never "safe to retry", orthostate ``vocabulary.py:118``);
    * ``idempotency_proven is True`` — broker-side idempotency for the **exact** identity
      and retry window (injected from brokercap ``same_order_retry_allowed``
      ``predicates.py:377`` / ``SUBMISSION_IDEMPOTENCY`` ``vocabulary.py:71``); the proof
      itself is ``+Broker`` evidence, not authored here;
    * ``budget_remaining`` is concrete and ``> 0`` (injected from the protective
      bounded-retry budget, ``predicates.py:590-615``: ``None`` / ``<= 0`` => no retry);
    * the completeness witness (evidence / capability / coverage / authority) is ``True``;
    * ``blind_failover_attempted`` is positively ``False`` — §14 line 352 forbids blind
      failover across session, endpoint, route, credential, broker, or client-order-id.

    **Structural seal for §14 line 352.** ``retry_count`` / ``elapsed_ms`` / ``backoff_ms``
    / ``repeated_identical_response`` are accepted **and discarded**: no accumulation of
    retries, elapsed time, backoff, or repeated identical responses can convert an
    ``UNKNOWN`` into a known rejection. They cannot influence the result because the
    result never reads them (the are ``concurrent_not_reservation(headroom_observed)``
    precedent), which is a stronger guarantee than a flag would give.

    **∅ / None canary (Gap-5):** with every argument ``None`` this returns ``False``
    (unproven => no retry).

    Args:
        attempt_state: The injected orthostate ``TransmissionAttemptState`` token.
        broker_order_state: The injected orthostate ``BrokerOrderState`` token.
        idempotency_proven: Whether broker-side idempotency is proven for this identity.
        budget_remaining: The injected protective bounded-retry budget.
        complete_evidence_capability_coverage_authority: Positive completeness witness.
        blind_failover_attempted: Whether a blind failover was attempted (must be ``False``).
        retry_count: Accepted and discarded (§14 line 352).
        elapsed_ms: Accepted and discarded (§14 line 352).
        backoff_ms: Accepted and discarded (§14 line 352).
        repeated_identical_response: Accepted and discarded (§14 line 352).

    Returns:
        ``True`` iff a governed, non-blind retry is admissible.
    """
    # §14 line 352 — none of these may convert UNKNOWN into a known rejection.
    del retry_count, elapsed_ms, backoff_ms, repeated_identical_response

    if attempt_state != ATTEMPT_STATE_SEND_FAILED_PROVEN:
        return False
    if broker_order_state is None or broker_order_state == BROKER_ORDER_STATE_UNKNOWN:
        return False
    if idempotency_proven is not True:
        return False
    if budget_remaining is None or budget_remaining <= 0:
        return False
    if complete_evidence_capability_coverage_authority is not True:
        return False
    return blind_failover_attempted is False


# ===========================================================================
# predicate-only §6.2 — cancel ACK is not FQP + bounded oscillation (AFG-EV-004)
# ===========================================================================


def cancel_ack_not_final_quantity_proof(
    broker_order_state: str | None,
    *,
    final_quantity_proof_present: bool | None,
    original_and_replacement_covered: bool | None,
    capacity_release_claimed: bool | None = None,
    replacement_reuse_claimed: bool | None = None,
    retry_claimed: bool | None = None,
) -> bool:
    """Whether the cancel-ACK-is-not-a-Final-Quantity-Proof rule holds (§15; AFG-INV-009).

    §15 line 358 verbatim: a cancel acknowledgement is **not** a Final Quantity Proof —
    it does not justify capacity release, replacement reuse, or retry; and the original
    **and** its replacement must stay covered for the worst credible overlap, late fill,
    reversal, and protection gap. orthostate records the coordinate: a later valid fill
    "SHALL be accepted even after a locally observed ``CANCELLED``"
    (``vocabulary.py:121``), so ``CANCELLED`` never terminates the exposure by itself.

    ``True`` **only** when the broker-order state is concrete, the original + replacement
    are positively covered, and — if **any** release / reuse / retry is claimed (or its
    status is unknown) — a separate Final Quantity Proof is positively present. A claim
    resting on the cancel ACK alone is ``False`` (the guard fires).

    Args:
        broker_order_state: The injected orthostate ``BrokerOrderState`` token (``None``
            => ``False``).
        final_quantity_proof_present: Whether a separate FQP exists (the only thing that
            can justify a release / reuse / retry).
        original_and_replacement_covered: Whether both legs stay covered for the worst
            credible overlap / late fill / reversal / protection gap.
        capacity_release_claimed: Whether a capacity release is claimed.
        replacement_reuse_claimed: Whether replacement reuse is claimed.
        retry_claimed: Whether a retry is claimed.

    Returns:
        ``True`` iff the invariant holds (no release / reuse / retry rests on a cancel ACK).
    """
    if broker_order_state is None:
        return False
    if original_and_replacement_covered is not True:
        return False
    claims = (capacity_release_claimed, replacement_reuse_claimed, retry_claimed)
    if any(claim is not False for claim in claims):
        return final_quantity_proof_present is True
    return True


def oscillation_bounded(
    cause: ActionCause | None,
    envelope: ActionAmplificationEnvelope | None,
    observed: ObservedAmplification | None,
    *,
    new_cause_created_for_budget_reset: bool | None,
    reserve_present: bool | None,
) -> bool:
    """Whether cancel/submit oscillation stays bounded (§15 line 360-362; AFG-INV-009).

    §15 line 360: infinite cancel <-> submit oscillation is forbidden and a **new cause
    may not be minted to reset the budget** — oscillation shares the same §11
    amplification envelope as every other expansion (design #16 §6.2). §15 line 362: when
    the protective reserve is absent, the exposure is recorded as **trapped** and
    contained, never transmitted.

    ``True`` **only** when the cause, envelope, and observation all exist, no new cause
    was minted for a budget reset (positively ``False``), the lineage is complete, the
    amplification is bounded on every axis, and the protective reserve is positively
    present.

    Args:
        cause: The action cause (``None`` => ``False``).
        envelope: The injected amplification envelope (``None`` => ``False``).
        observed: The observed amplification counts (``None`` => ``False``).
        new_cause_created_for_budget_reset: Must be positively ``False`` (§15 line 360).
        reserve_present: Whether the protective reserve is present (``None`` / ``False``
            => trapped + contained, §15 line 362).

    Returns:
        ``True`` iff oscillation is bounded and the reserve is present.
    """
    if cause is None or envelope is None or observed is None:
        return False
    if new_cause_created_for_budget_reset is not False:
        return False
    if not cause_lineage_complete(cause):
        return False
    if not amplification_bounded(envelope, observed):
        return False
    return reserve_present is True


# ===========================================================================
# predicate-only §6.3 — complete action / resource classification (AFG-EV-005)
# ===========================================================================


def action_class_conservative(
    claimed_class: ActionClassKind | None,
    applicable_classes: frozenset[ActionClassKind],
    vector: CapacityVector | None = None,
) -> ActionClassKind | ActionFlowResult:
    """The governing action class when classifications conflict (§9 line 268).

    §9 line 268 verbatim: "the more conservative applicable class and vector govern when
    classification conflicts" — an exit can zero-cross / reverse / overlap, a cancel can
    remove protection, and a query / reconnect can exhaust a shared resource, so a benign
    label buys nothing. §7 line 218: "Producer label cannot create a more permissive
    class." §9 line 254: cancel / amend / replace / query / session / reconnect / SDK retry
    are all counted, not just submissions.

    Returns the most conservative member of ``applicable_classes`` **unioned with** the
    claimed class — so a claim can only ever make the outcome *more* conservative, never
    less. An **empty** ``applicable_classes`` yields ``ActionFlowResult.UNKNOWN`` (a
    vacuous "classified over nothing" is not a classification — design #16 §4.7), as does
    a vector declaring an unenumerated (non-afg) dimension (§2.2-4 fail-closed).

    **Truthy seal:** both arms of the returned union are truthy ``StrEnum`` members, so a
    consumer MUST test ``verdict is ActionFlowResult.UNKNOWN`` (identity).

    Args:
        claimed_class: The class the producer claims (may only tighten the outcome).
        applicable_classes: The classes that structurally apply (empty => ``UNKNOWN``).
        vector: The action-flow vector, if any (unknown dimension => ``UNKNOWN``).

    Returns:
        The governing :class:`~tos.afg.vocabulary.ActionClassKind`, or
        ``ActionFlowResult.UNKNOWN``.
    """
    if not applicable_classes:
        return ActionFlowResult.UNKNOWN
    if vector is not None:
        for dimension in vector.dimension_ids():
            if not is_action_flow_dimension_id(dimension):
                return ActionFlowResult.UNKNOWN
    candidates = set(applicable_classes)
    if claimed_class is not None:
        candidates.add(claimed_class)
    governing = most_conservative_action_class(candidates)
    return governing if governing is not None else ActionFlowResult.UNKNOWN


# ===========================================================================
# predicate-only §6.4 — protective flow reserve exclusivity (AFG-EV-006)
# ===========================================================================


def reserve_exclusive(
    claim: ProtectiveFlowReserveClaim | None,
    is_reserved: bool | None,
    *,
    normal_traffic_borrowed: bool | None,
    normal_traffic_consumed: bool | None,
    relabelled_as_normal: bool | None,
    repay_reserve_later_claimed: bool | None,
) -> bool:
    """Whether the protective flow reserve is exclusively preserved (§16; AFG-INV-006).

    AFG-INV-006 line 177: normal traffic may **not** borrow, consume, or relabel the
    minimum protective reserve, and §16 line 370 gives no "repay the reserve later" path.
    afg does **not** classify the reserve — protective owns ``GuaranteeLevel``
    (``vocabulary.py:32``, M1: there is no ``ReserveGuaranteeLevel``) and
    ``is_reserved_guarantee`` (``predicates.py:129``, which returns ``True`` only for
    ``PHYSICALLY_RESERVED`` / ``LOGICALLY_RESERVED`` with the required evidence). afg
    consumes the produced ``bool`` by injection with an ``is not True`` normalization: an
    unproven (``None``) reserve is **not** reserved (truthy-sentinel seal, design #16
    §2.2-1).

    ``True`` **only** when the claim exists, its dimension is a governed afg action-flow
    dimension, its reserved magnitude is concrete and finite, ``is_reserved is True``, and
    all four encroachment witnesses are positively ``False``.

    **∅ / None canary (Gap-5):** ``is_reserved=None`` => ``False`` (an unproven reserve
    cannot be borrowed against).

    Args:
        claim: The protective flow reserve claim (``None`` => ``False``).
        is_reserved: The injected protective ``is_reserved_guarantee`` result.
        normal_traffic_borrowed: Must be positively ``False`` (AFG-INV-006).
        normal_traffic_consumed: Must be positively ``False`` (AFG-INV-006).
        relabelled_as_normal: Must be positively ``False`` (AFG-INV-006).
        repay_reserve_later_claimed: Must be positively ``False`` (§16 line 370).

    Returns:
        ``True`` iff the reserve is positively exclusive and un-encroached.
    """
    if claim is None:
        return False
    if not is_action_flow_dimension_id(claim.dimension_id):
        return False
    magnitude = claim.reserved_magnitude
    if magnitude is None or not magnitude.is_finite():
        return False
    if is_reserved is not True:
        return False
    if normal_traffic_borrowed is not False:
        return False
    if normal_traffic_consumed is not False:
        return False
    if relabelled_as_normal is not False:
        return False
    return repay_reserve_later_claimed is False


def priority_is_not_reserve(
    guarantee_level_token: str | None,
    *,
    exclusive_capacity_present: bool | None,
    high_priority_queue: bool | None = None,
) -> bool:
    """Whether a declared guarantee is backed by **exclusive capacity** (§16 line 372).

    §16 line 372 verbatim: "A high-priority queue without exclusive capacity is
    ``PRIORITIZED_ONLY``" — priority alone is never a reservation (protective §3.1.4 line
    144 "A prioritized resource is not a reserved resource"). ``True`` **only** when the
    injected protective ``GuaranteeLevel`` token is one of
    :data:`~tos.afg.vocabulary.RESERVED_GUARANTEE_TOKENS`
    (``PHYSICALLY_RESERVED`` / ``LOGICALLY_RESERVED``) **and** exclusive capacity is
    positively present. ``PRIORITIZED_ONLY`` / ``BEST_EFFORT`` / ``UNAVAILABLE`` / ``None``
    all fail closed, and a *reserved-looking label* without exclusive capacity also fails
    closed (the guard fires).

    ``high_priority_queue`` is accepted **and discarded**: a queue priority can never
    upgrade a guarantee level, and the result cannot read it.

    Args:
        guarantee_level_token: The injected protective ``GuaranteeLevel`` token.
        exclusive_capacity_present: Whether exclusive capacity is positively present.
        high_priority_queue: Accepted and discarded (§16 line 372).

    Returns:
        ``True`` iff the guarantee is a genuine, exclusively-backed reservation.
    """
    del high_priority_queue  # a priority queue never upgrades a guarantee (§16 line 372)
    if guarantee_level_token is None:
        return False
    if guarantee_level_token not in RESERVED_GUARANTEE_TOKENS:
        return False
    return exclusive_capacity_present is True


# ===========================================================================
# predicate-only §6.6 — partition / stale writer / protective lease (AFG-EV-010)
# ===========================================================================


def partition_lease_exclusive(
    lease_admissible: str | None,
    remaining_budget: int | None,
    monotonic_continuity_id: str | None,
    *,
    reference_continuity_id: str | None,
    new_normal_permit_during_partition: bool | None,
    lease_refilled_remotely_or_by_wall_clock: bool | None,
    exclusivity_retained: bool | None,
    stale_writer_hard_fenced: bool | None,
) -> bool:
    """Whether a partition-time protective lease may still be consumed (§20; AFG-EV-010).

    §20 line 425: during a control-plane partition **no new normal permit** may be issued.
    §20 line 427: only an exclusive, pre-issued, scope-limited lease plus a **monotonic
    local** sub-budget may be consumed, and a lease can never be refilled remotely or by
    wall clock. §20 line 429: a stale writer (old RCL / governor / scheduler / egress)
    stays **potentially active** until it is hard-fenced.

    The lease admissibility verdict is **produced by protective**
    (``partition_lease_admissible`` ``predicates.py:460``) and returns the 3-token
    ``Admissibility`` StrEnum (``vocabulary.py:118/137``) — **not** ``bool | None`` (design
    #16 M2). Every member of that StrEnum is truthy, so this gate admits **only** the
    ``ADMISSIBLE`` token: ``TRAPPED``, ``PROHIBITED``, and ``None`` all deny. (afg does not
    import ``tos.protective``; the token equality is locked against the real enum by the
    MANDATED ``test_seam_protective`` cross-check, design #16 §3.4(d).)

    **∅ / None canary (Gap-5):** ``lease_admissible=None`` or a ``None`` / ``<= 0``
    remaining budget => ``False``.

    Args:
        lease_admissible: The injected protective ``Admissibility`` token (only
            ``ADMISSIBLE`` passes).
        remaining_budget: The monotonic local sub-budget (``None`` / ``<= 0`` => ``False``).
        monotonic_continuity_id: The lease's monotonic continuity id.
        reference_continuity_id: The consumer's continuity id (must match — no cross-host
            comparison, §18 line 403).
        new_normal_permit_during_partition: Must be positively ``False`` (§20 line 425).
        lease_refilled_remotely_or_by_wall_clock: Must be positively ``False`` (§20:427).
        exclusivity_retained: Must be positively ``True`` (loss of exclusivity => deny).
        stale_writer_hard_fenced: Must be positively ``True`` (§20 line 429).

    Returns:
        ``True`` iff the exclusive lease may still be consumed under partition.
    """
    if lease_admissible != ADMISSIBILITY_ADMISSIBLE:
        return False
    if remaining_budget is None or remaining_budget <= 0:
        return False
    if monotonic_continuity_id is None or reference_continuity_id is None:
        return False
    if monotonic_continuity_id != reference_continuity_id:
        return False
    if new_normal_permit_during_partition is not False:
        return False
    if lease_refilled_remotely_or_by_wall_clock is not False:
        return False
    if exclusivity_retained is not True:
        return False
    return stale_writer_hard_fenced is True


# ===========================================================================
# predicate-only §6.7 — authority separation / all-false (AFG-EV-011)
# ===========================================================================


def governor_grants_no_authority(effect: ActionFlowGovernorEffect) -> bool:
    """Whether the governor effect grants nothing (§7 line 220/229; AFG-INV-011).

    ``True`` **only** when every authority flag is ``False``. Because
    :class:`~tos.afg.records.ActionFlowGovernorEffect` is unconstructable with any ``True``
    flag, a *validated* effect always grants nothing — this is the defining predicate that
    states it, and the defence-in-depth re-check for a block that reached the consumer via
    an unvalidated path (``model_construct``). §7 line 220: the Governor "SHALL NOT mutate
    a budget, issue authority, or transmit"; §7 line 229: it "SHALL NOT hold a live broker
    credential, signer, session, route, or endpoint capability". The +Security enforcement
    proof (no egress bypass, no common-mode privilege) is AFG-EV-011 runtime, not authored
    here.

    The check iterates **every declared field** rather than naming the six flags inline, so
    a flag added to the block in future is covered automatically — a hardcoded disjunction
    would silently stop covering it (an under-realization defect class).

    **Each flag must be positively ``False``, not merely "not ``True``".** This predicate's
    whole reason to exist is defence in depth against a block that reached the consumer
    **without** validation (``pydantic.BaseModel.model_construct`` skips validators). Such a
    block can carry *any* object, so an ``is not True`` test would pass a forged truthy
    ``1`` / ``1.0`` / ``"yes"`` / ``[1]`` and report "grants no authority" for an artifact
    that plainly does. Demanding the singleton ``False`` is the only test that cannot be
    satisfied by forgery.

    Args:
        effect: The governor authority effect.

    Returns:
        ``True`` iff the effect grants no authority.
    """
    declared = type(effect).model_fields
    if not declared:
        # A block declaring no flag proves nothing; a vacuous "grants nothing over
        # nothing" is not a proof of authority separation (design #16 §4.7).
        return False
    return all(getattr(effect, name) is False for name in declared)


# ===========================================================================
# produced rcl seam (§3.4) — forward-only decision content ref
# ===========================================================================


def decision_content_ref(
    decision: ActionFlowDecision,
) -> tuple[str | None, int | None, str | None]:
    """The forward-only ``(decision_id, decision_generation, canonical_digest)`` (§3.4).

    The exact content-ref scalars rcl ``GrantDecisionRef`` consumes
    (``authority.py:53-55``, the slot ``:40`` names an "Aggregate Risk / **Action Flow**
    decision reference"); ``canonical_decision_digest`` is the decision's own
    ``canonical_digest`` (id ⊥ digest, §3.1). **No** reservation coordinate is produced —
    rcl charges ``bound_reservation_*`` post-commit, which is what keeps the pipeline
    non-cyclic (design #16 §5.3; ADR §29 q2).

    Args:
        decision: The action flow decision.

    Returns:
        The ``(decision_id, decision_generation, canonical_decision_digest)`` tuple.
    """
    return (
        decision.decision_id,
        decision.decision_generation,
        decision.canonical_digest,
    )


def applicable_action_flow_scopes_of(decision: ActionFlowDecision) -> tuple[str, ...]:
    """The exact action-flow scopes the decision applies to (rcl seam, §3.4)."""
    return decision.applicable_action_flow_scopes


def action_flow_vector_of(decision: ActionFlowDecision) -> ActionFlowVector:
    """The decided action-flow vector — the rcl ``CapacityVector`` type (§3.4 / §0.4c).

    The exact type rcl commits, so the value drops into the ledger without a reduction
    reducer and the action-flow coordinate cannot collapse onto the economic one
    (design #16 §0.4c / Gap-1).
    """
    return decision.action_flow_vector
