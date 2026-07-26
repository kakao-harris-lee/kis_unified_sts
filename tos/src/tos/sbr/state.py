"""sbr session state machine + the produced seam scalars (design #17 §10 / §3.4).

Two roles:

* **session state machine (§10 line 280-293)** — the ADR-002-017 §10 transition arrows as a
  ``frozenset`` (the spg ``_ENVELOPE_TRANSITIONS`` ``predicates.py:78`` precedent), plus
  :func:`session_transition_allowed` and the non-revival terminal set
  :data:`_TERMINAL_STATES`. A terminal state ({``NOT_READY``, ``INVALIDATED``, ``ABORTED``,
  ``EXPIRED``, ``SUPERSEDED``}) has **no** outgoing arrow to a ready state (§10 line 293), and
  every unlisted pair is ``False`` (fail-closed set membership). Retry is a **new** session
  identity, never a re-activation of an old one (§10 line 293);

* **produced seam scalars (§3.4)** — SBR is the **producer**; downstream siblings consume
  these injected scalars (they do **not** import ``tos.sbr``):

  - :func:`recovery_coordinator_evidence_complete` → the authority ``_REARM_PREREQUISITES``
    item 12 ``recovery_coordinator_evidence_complete`` field (``authority/state.py:133``),
    consumed by ``rearm_gate`` with ``getattr(checklist, name) is True``
    (``authority/predicates.py:769``). Producing this bool is **not** re-arm: it is one of 14
    prerequisites, and re-arm admissibility is authority / liveauth-owned (§3.5 — readiness is
    the first input, never the permission; SBR-INV-003/014);
  - :func:`recovery_current` → the liveauth ``ContinuousValidityInputs.recovery_current`` slot
    (``liveauth/state.py:139``);
  - :func:`recovery_readiness_enlarged` → the liveauth SAFE-053
    ``recovery_readiness_enlarged`` slot (``liveauth/state.py:208``);
  - :func:`recovery_generation_of` → the ``recovery_generation`` reference coordinate the
    authority ``GenerationVector`` carries (``authority/state.py:50``; reference-only,
    ``state.py:42-43`` "their owning ADR fences them" — SBR owns the fence meaning, authority
    only carries the scalar, §0.4e).

Every produced value has a **defining predicate** here (design #17 §3.4 — no produced value
without a definition, no phantom slot for a sibling field that does not exist; each cited
field / line is grep-verified). The monotonic recovery generation order is REUSED from
:mod:`tos.ordering` (:func:`recovery_generation_monotone`), not re-authored (§3.2).

**Truthy-sentinel discipline (design #17 §4.7).** ``ReadinessVerdict`` / ``SessionState`` are
truthy-untestable; every gate uses ``x is ENUM.SAFE_VALUE`` (never ``if verdict:``), and
injected ``bool | None`` flags are normalized with ``is True`` / ``is not True``.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.sbr.*`` only; no ``shared.*``,
no other sibling ``tos.*`` (design #17 §0.3). Clock-free — no wall clock orders (§8).
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.sbr.records import RecoveryReadinessDecision
from tos.sbr.vocabulary import ObligationResult, ReadinessVerdict, SessionState

__all__ = [
    # §10 session state machine
    "session_transition_allowed",
    "is_terminal_state",
    # §3.2 ordering REUSE
    "recovery_generation_monotone",
    # §3.4 produced seam scalars
    "recovery_coordinator_evidence_complete",
    "recovery_current",
    "recovery_readiness_enlarged",
    "recovery_generation_of",
]


# ===========================================================================
# §10 — session state machine (§10 line 280-293; SBR-INV-013)
# ===========================================================================

#: The §10 progress states (TRIGGERED..DECISION_CANDIDATE), each of which may be
#: invalidated / aborted / superseded (§10 line 283-285).
_PROGRESS_STATES: tuple[SessionState, ...] = (
    SessionState.TRIGGERED,
    SessionState.FENCING,
    SessionState.INVENTORYING,
    SessionState.RECONCILING,
    SessionState.VALIDATING,
    SessionState.DECISION_CANDIDATE,
)

#: The exact ADR-002-017 §10 line 281-291 session arrows — the ONLY allowed transitions
#: (the spg ``_ENVELOPE_TRANSITIONS`` ``predicates.py:78`` precedent). Transcribed verbatim
#: and double-checked. The terminal set (:data:`_TERMINAL_STATES`) has no outgoing arrow to a
#: ready state (§10 line 293 non-revival); ``READY`` / ``READY_RESTRICTED`` are ready states
#: that may only be invalidated / expired / superseded, never re-entered into candidacy.
_SESSION_TRANSITIONS: frozenset[tuple[SessionState, SessionState]] = frozenset(
    {
        # linear progression (§10 line 281-282)
        (SessionState.TRIGGERED, SessionState.FENCING),
        (SessionState.FENCING, SessionState.INVENTORYING),
        (SessionState.INVENTORYING, SessionState.RECONCILING),
        (SessionState.RECONCILING, SessionState.VALIDATING),
        (SessionState.VALIDATING, SessionState.DECISION_CANDIDATE),
        # decision fan-out (§10 line 283)
        (SessionState.DECISION_CANDIDATE, SessionState.READY),
        (SessionState.DECISION_CANDIDATE, SessionState.READY_RESTRICTED),
        (SessionState.DECISION_CANDIDATE, SessionState.NOT_READY),
        # any progress state may be invalidated / aborted / superseded (§10 line 284)
        *((state, SessionState.INVALIDATED) for state in _PROGRESS_STATES),
        *((state, SessionState.ABORTED) for state in _PROGRESS_STATES),
        *((state, SessionState.SUPERSEDED) for state in _PROGRESS_STATES),
        # a ready state may be invalidated / expired / superseded (§10 line 285)
        (SessionState.READY, SessionState.INVALIDATED),
        (SessionState.READY, SessionState.EXPIRED),
        (SessionState.READY, SessionState.SUPERSEDED),
        (SessionState.READY_RESTRICTED, SessionState.INVALIDATED),
        (SessionState.READY_RESTRICTED, SessionState.EXPIRED),
        (SessionState.READY_RESTRICTED, SessionState.SUPERSEDED),
    }
)

#: The §10 line 293 non-revival terminal set — no outgoing arrow to a ready state. A retry is
#: a NEW session identity (§10 line 293), never a re-activation of one of these.
_TERMINAL_STATES: frozenset[SessionState] = frozenset(
    {
        SessionState.NOT_READY,
        SessionState.INVALIDATED,
        SessionState.ABORTED,
        SessionState.EXPIRED,
        SessionState.SUPERSEDED,
    }
)


def session_transition_allowed(frm: SessionState, to: SessionState) -> bool:
    """Whether a session ``frm -> to`` transition is allowed (§10 line 281-293).

    ``True`` **only** for an arrow in :data:`_SESSION_TRANSITIONS`. No terminal state
    (``NOT_READY`` / ``INVALIDATED`` / ``ABORTED`` / ``EXPIRED`` / ``SUPERSEDED``) has any
    outgoing arrow, so none can transition to a ready state (§10 line 293 non-revival). Pure
    set membership; every unlisted pair is ``False`` (fail-closed).

    Args:
        frm: The current session state.
        to: The proposed next session state.

    Returns:
        ``True`` iff the transition is one of the §10 arrows.
    """
    return (frm, to) in _SESSION_TRANSITIONS


def is_terminal_state(state: SessionState) -> bool:
    """Whether ``state`` is a non-revival terminal (§10 line 293).

    ``True`` for a state in :data:`_TERMINAL_STATES` — none of which can transition to a ready
    state. Pure set membership.

    Args:
        state: The session state.

    Returns:
        ``True`` iff the state is terminal and non-revivable.
    """
    return state in _TERMINAL_STATES


# ===========================================================================
# §3.2 — recovery generation monotonic order (ordering REUSE)
# ===========================================================================


def recovery_generation_monotone(earlier: OrderingEvent, later: OrderingEvent) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.5).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic
    Recovery Generation order (§5.5 line 118-120 "A monotonic generation ... A newer
    generation invalidates every older in-progress or terminal readiness artifact"). ``True``
    **only** when the order is unambiguously ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair
    fails closed. A wall clock never orders — SBR reads no clock (§8).

    Args:
        earlier: The earlier ordering event.
        later: The later ordering event.

    Returns:
        ``True`` iff ``earlier`` provably precedes ``later``.
    """
    return compare_order(earlier, later) is Ordering.BEFORE


# ===========================================================================
# §3.4 — produced seam scalars (SBR is the producer; siblings inject-consume)
# ===========================================================================


def _positive_verdict(decision: RecoveryReadinessDecision) -> bool:
    """Whether the decision's verdict is a positive readiness (READY / READY_RESTRICTED).

    Uses explicit ``is`` identity on the truthy-untestable ``ReadinessVerdict`` (never
    ``if verdict:``): ``NOT_READY`` and ``None`` are non-positive (design #17 §4.7).
    """
    return (
        decision.verdict is ReadinessVerdict.READY
        or decision.verdict is ReadinessVerdict.READY_RESTRICTED
    )


def recovery_coordinator_evidence_complete(
    decision: RecoveryReadinessDecision | None,
) -> bool:
    """Produce the authority ``_REARM_PREREQUISITES`` item 12 bool (§21 handoff; §3.4).

    The exact bool the authority re-arm checklist field
    ``recovery_coordinator_evidence_complete`` (``authority/state.py:133``) carries and
    ``rearm_gate`` consumes with ``getattr(checklist, name) is True``
    (``authority/predicates.py:769``, one of the 14 ``_REARM_PREREQUISITES`` at
    ``predicates.py:108``). **Producing this is not re-arm** (§3.5 핵심 판정 2): it reports
    only that SBR's recovery evidence is complete — re-arm admissibility (and the remaining 13
    prerequisites, including ``fresh_live_authorization_issued`` and
    ``explicit_human_dual_control_complete``) is authority / liveauth-owned; readiness is the
    first input, never the permission (SBR-INV-003/014 line 198 "fresh governed re-arm is
    mandatory"). ``True`` **only** when the decision positively exists, its verdict is a
    positive readiness (``READY`` / ``READY_RESTRICTED`` — explicit identity, not
    ``if verdict:``), the evidence-package / inventory-cut / obligation-set digests are all
    present, and **every** obligation result is ``SATISFIED``. A ``None`` / ``NOT_READY`` /
    any non-``SATISFIED`` result fails closed.

    Args:
        decision: The readiness decision (``None`` => ``False``).

    Returns:
        ``True`` iff SBR's recovery coordinator evidence is complete (item 12 prerequisite).
    """
    if decision is None:
        return False
    if not _positive_verdict(decision):
        return False
    if decision.package_digest is None:
        return False
    if decision.inventory_cut_digest is None:
        return False
    if decision.obligation_set_digest is None:
        return False
    if not decision.all_results:
        return False
    return all(result is ObligationResult.SATISFIED for result in decision.all_results)


def recovery_current(
    decision: RecoveryReadinessDecision | None,
    *,
    newer_generation_observed: bool | None,
    within_max_age: bool | None,
) -> bool:
    """Produce the liveauth ``ContinuousValidityInputs.recovery_current`` bool (§18; §3.4).

    The exact ``bool | None`` slot the liveauth continuous-validity inputs carry
    (``liveauth/state.py:139``), consumed by injection (liveauth does not import ``tos.sbr``;
    the liveauth ``protective_coverage_valid`` injected-bool precedent, §0.4c). §18 line 463:
    "A consumer cannot continue using a cached readiness decision beyond
    ``MAX_recovery_readiness_age`` or after a newer generation is observed." ``True`` **only**
    when a positive readiness decision exists, **no** newer generation has been observed
    (``newer_generation_observed is False``), and the readiness is within max age
    (``within_max_age is True``). A newer generation invalidates every older readiness (§5.5
    line 120); an unknown age / newer generation fails closed.

    Args:
        decision: The readiness decision (``None`` => ``False``).
        newer_generation_observed: Whether a newer generation was observed (``True`` / ``None``
            => not current).
        within_max_age: Whether the readiness is within max age (``None`` / ``False`` => not
            current).

    Returns:
        ``True`` iff the recovery readiness is still current for continued authority.
    """
    if decision is None:
        return False
    if not _positive_verdict(decision):
        return False
    if newer_generation_observed is not False:
        return False
    return within_max_age is True


def recovery_readiness_enlarged(
    decision: RecoveryReadinessDecision | None,
    *,
    enlarged_scope_freshly_proven: bool | None,
) -> bool:
    """Produce the liveauth SAFE-053 ``recovery_readiness_enlarged`` bool (§18; §3.4).

    The exact slot the liveauth SAFE-053 single-operator re-arm variant carries
    (``liveauth/state.py:208``), consumed by injection. An in-place scope expansion (a delta
    re-arm for an enlarged scope) may **not** inherit the prior readiness: SBR-INV-011 requires
    the enlarged scope's readiness to be **freshly proven**. ``True`` **only** when a positive
    readiness decision exists **and** the enlarged scope was positively freshly proven
    (``enlarged_scope_freshly_proven is True``); a ``None`` / unproven enlargement fails
    closed.

    Args:
        decision: The readiness decision (``None`` => ``False``).
        enlarged_scope_freshly_proven: Whether the enlarged-scope readiness was freshly proven
            (``None`` / ``False`` => ``False``).

    Returns:
        ``True`` iff the readiness positively covers the enlarged scope with fresh proof.
    """
    if decision is None:
        return False
    if not _positive_verdict(decision):
        return False
    return enlarged_scope_freshly_proven is True


def recovery_generation_of(decision: RecoveryReadinessDecision) -> int | None:
    """The ``recovery_generation`` reference coordinate authority carries (§0.4e; §3.4).

    The exact ``recovery_generation`` scalar the authority ``GenerationVector`` carries as a
    **reference-only** field (``authority/state.py:50``; ``state.py:42-43`` "the rest are
    reference-only scalars ... their owning ADR fences them"). SBR owns the fence *meaning*
    (§9 egress rejection / §18 invalidation); authority only carries the coordinate, and the
    Safety Control Plane commits the order (§7 line 208, runtime). Substituting another
    coordinate's value for this one never satisfies a fence (the §4.3 non-collapse canary).

    Args:
        decision: The readiness decision.

    Returns:
        The decision's ``recovery_generation`` reference coordinate.
    """
    return decision.recovery_generation
