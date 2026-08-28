"""Safe-Startup / Recovery-Barrier vocabulary — the recovery-axis StrEnums (design #17 §2.2).

Spec terms = code terms (design #17 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-017 (§9 barrier states, §10 session states, §16 readiness
verdicts, §13/§14 obligation results, §15 recovery mode). These are the **recovery-
orchestration** axis; they are a distinct coordinate system from the recon
``FieldConfidenceClass`` (per-field confidence axis — ``recon/vocabulary.py:26``), the
orthostate ``KnowledgeState`` (per-action aggregate axis — ``vocabulary.py:149``), and the
rcl ``CapacityState`` (economic-capacity axis — ``vocabulary.py:15``). In particular
``ReadinessVerdict.NOT_READY`` is **not** ``SessionState.NOT_READY`` (§2.2(4)) — they are
the same concept expressed on two axes (a decision verdict vs a session terminal state), and
a runtime commits both together; non-collapse rests on **distinct types + non-import** (SBR
imports none of those sibling axes, sibling edge 0 — design #17 §0.3/§0.4c).

**Truthy-sentinel structural seal (design #17 §2.2(1)/§4.7 — the critical seal, #14 M1
adopted from the start).** Every barrier / session / readiness / obligation member is a
non-empty ``StrEnum`` string, so ``if verdict:`` / ``bool(verdict)`` would read a denial
value (``NOT_READY`` / ``FAILED`` / ``UNKNOWN`` / a ``CLOSED_*`` barrier) as **truthy** — a
catastrophic silent fail-open (a future liveauth re-arm consumer's ``if verdict:`` would
treat "not ready" as "ready"). Every such enum subclasses :class:`_NonTruthyStrEnum`, whose
:meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``, making them
*truthy-untestable*: the misuse surfaces as an immediate runtime error, never a silent pass.
The mandated consume gate is the explicit positive-identity comparison
(``verdict is ReadinessVerdict.READY`` / ``result is ObligationResult.SATISFIED``) —
everything else is denial. Barrier state is especially critical: §9 line 257 verbatim "No
barrier state alone permits live transmission", so **no** ``CLOSED_*`` value may ever be read
as truthy permission. Isomorphic to the iap ``ApprovalResult`` seal
(``iap/vocabulary.py:50``); authored locally-fresh here (sibling edge 0 — no iap import).

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #17 §0.1) and hardcodes **no** numeric recovery bound
(ADR §4 non-scope line 96): every bound / age / generation value is an injected parameter
(design #17 §8). An enum member is a structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #17 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "RecoveryBarrierState",
    "SessionState",
    "ReadinessVerdict",
    "ObligationResult",
    "RecoveryMode",
    "SelectionBasis",
    "OwnerStatus",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #17 §2.2(1)/§4.7/M1).

    Every member is a non-empty string, so a bare ``if verdict:`` / ``bool(verdict)`` would
    read a denial member (``NOT_READY`` / ``FAILED`` / ``UNKNOWN`` / a ``CLOSED_*`` barrier)
    as truthy — a catastrophic silent fail-open. :meth:`__bool__` therefore raises
    ``TypeError`` on every member, so the misuse surfaces as a loud runtime error rather than
    a silent pass. Consumers MUST use the explicit positive-identity gate
    (``x is ENUM.SAFE_VALUE``). Isomorphic to the iap ``_NonTruthyStrEnum``
    (``iap/vocabulary.py:50``); authored locally-fresh here (sibling edge 0, no iap import —
    design #17 §0.4d). ``is`` identity, ``.value``, hashing, set membership, and
    ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #17 §2.2(1)/M1).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``verdict is ReadinessVerdict.READY``;
                ``result is ObligationResult.SATISFIED``); a bare ``if verdict:`` /
                ``bool(verdict)`` would fail open on the truthy denial strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `verdict is ReadinessVerdict.READY`; "
            "`result is ObligationResult.SATISFIED`) per the truthy-sentinel seal "
            "(design #17 §2.2(1)/§4.7/M1). The denial members are non-empty strings and a "
            "bare `if verdict:` would fail open; §9 line 257 — no barrier state alone permits."
        )


class RecoveryBarrierState(_NonTruthyStrEnum):
    """The four recovery-barrier states (ADR-002-017 §9 line 250-255 verbatim).

    §9 line 250-255 gives exactly four values, each describing a new-risk **denial
    context**, not permission. §9 line 257 verbatim: "These names describe new-risk denial
    context, not permission. No barrier state alone permits live transmission." So **no**
    member may ever be read as truthy permission — the truthy-sentinel seal
    (:class:`_NonTruthyStrEnum`) is load-bearing here above all: a bare ``if barrier:`` would
    read ``CLOSED_HALTED`` as "permitted". A barrier state is a denial-context label consumed
    only by explicit identity comparison; fresh live-arming (§21 handoff) is a separate chain
    (:func:`~tos.sbr.predicates.start_closed`).
    """

    CLOSED_NON_LIVE = "CLOSED_NON_LIVE"
    CLOSED_RECOVERY = "CLOSED_RECOVERY"
    CLOSED_CONTAINED = "CLOSED_CONTAINED"
    CLOSED_HALTED = "CLOSED_HALTED"


class SessionState(_NonTruthyStrEnum):
    """The recovery-session lifecycle states (ADR-002-017 §10 line 280-291 verbatim).

    The §10 transition nodes; the allowed arrows are :data:`~tos.sbr.state._SESSION_TRANSITIONS`
    and the non-revival terminal set is :data:`~tos.sbr.state._TERMINAL_STATES`. §10 line 293
    verbatim: "``ABORTED``, ``INVALIDATED``, ``EXPIRED``, ``SUPERSEDED``, and ``NOT_READY``
    cannot transition to a ready state" (terminal non-revival), and "Retry creates a new
    session identity" — an old session is never re-activated. Truthy-untestable
    (``__bool__`` raises); a consumer gates on explicit identity, never ``if state:``.
    """

    TRIGGERED = "TRIGGERED"
    FENCING = "FENCING"
    INVENTORYING = "INVENTORYING"
    RECONCILING = "RECONCILING"
    VALIDATING = "VALIDATING"
    DECISION_CANDIDATE = "DECISION_CANDIDATE"
    READY = "READY"
    READY_RESTRICTED = "READY_RESTRICTED"
    NOT_READY = "NOT_READY"
    INVALIDATED = "INVALIDATED"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ReadinessVerdict(_NonTruthyStrEnum):
    """The three recovery-readiness verdicts (ADR-002-017 §16 line 419 verbatim).

    §16 line 419 gives ``READY`` / ``READY_RESTRICTED`` / ``NOT_READY``. §16 line 426:
    "``READY`` requires all obligations for the exact requested scope to pass with no blocking
    Critical hazard"; §16 line 430: "``NOT_READY`` ... cannot be manually promoted; a new
    session and evidence package are required." This is the **decision-verdict** axis (owned
    by SBR), distinct from :class:`SessionState` (the session-lifecycle axis) — the same
    concept on two axes (§2.2(4)); a runtime commits both together and the readiness is the
    session's product. Truthy-untestable (``__bool__`` raises); the mandated consume gate is
    ``verdict is ReadinessVerdict.READY`` (``READY_RESTRICTED`` requires the separate
    isolation proof :func:`~tos.sbr.predicates.restricted_isolation_proven`).
    """

    READY = "READY"
    READY_RESTRICTED = "READY_RESTRICTED"
    NOT_READY = "NOT_READY"


class ObligationResult(_NonTruthyStrEnum):
    """The recovery-obligation result classes (ADR-002-017 §13 line 346 / §14 line 384).

    §13 line 346 "acceptable result classes" + §14 line 384 "terminal confidence/result":
    ``SATISFIED`` / ``FAILED`` / ``UNKNOWN`` / ``TIMED_OUT`` / ``CONFLICTED`` /
    ``MISSING_SOURCE``. Only ``SATISFIED`` passes an obligation
    (:func:`~tos.sbr.predicates.obligation_graph_closed` gates on
    ``result is ObligationResult.SATISFIED``); every other member is non-satisfied
    (conservative). **Not** the recon ``FieldConfidenceClass`` (per-field confidence) — SBR
    folds recon results into obligation results, it does not re-define confidence (§3.5; the
    ``ObligationResult`` ≠ ``FieldConfidenceClass`` non-collapse, §2.2(5)). Truthy-untestable
    (``__bool__`` raises).
    """

    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    TIMED_OUT = "TIMED_OUT"
    CONFLICTED = "CONFLICTED"
    MISSING_SOURCE = "MISSING_SOURCE"


class RecoveryMode(StrEnum):
    """The recovery operating modes (ADR-002-017 §15 line 397-404).

    ``RECOVERY`` (new risk prohibited) / ``CONTAINED`` / ``HALTED`` — aligned with the §9
    barrier denial-context. A **plain** ``StrEnum``: it is an injected input taxonomy token
    consumed by identity / set membership, never a gate result read with ``if mode:``, so it
    does not need the truthy seal (unlike the four decision enums above).
    """

    RECOVERY = "RECOVERY"
    CONTAINED = "CONTAINED"
    HALTED = "HALTED"


class SelectionBasis(StrEnum):
    """A single-basis branch-selection heuristic that is forbidden for restore (§20 line 497).

    §20 line 497 verbatim: "select no branch by recency label, backup success, administrator
    choice, or wall-clock timestamp alone." Each member names one such forbidden single
    basis; :func:`~tos.sbr.predicates.restore_worst_credible_union` rejects a restore that
    selected a branch by any of them (all branches must be preserved under the worst credible
    union instead). A plain input taxonomy token (compared by identity, not truthiness).
    """

    RECENCY = "RECENCY"
    BACKUP_SUCCESS = "BACKUP_SUCCESS"
    ADMIN_CHOICE = "ADMIN_CHOICE"
    WALL_CLOCK = "WALL_CLOCK"


class OwnerStatus(StrEnum):
    """The status of a competing recovery owner (ADR-002-017 §11 line 303-304).

    §11 line 303-304 verbatim: "only one current owner may advance a session or publish a
    decision for overlapping scope; minority, stale, paused, restored, removed, or partitioned
    owners are rejected." Only :attr:`CURRENT` is admissible;
    :func:`~tos.sbr.predicates.competing_owner_fenced` rejects every other status (and any
    epoch mismatch). A plain input taxonomy token (compared by identity, not truthiness).
    """

    CURRENT = "CURRENT"
    MINORITY = "MINORITY"
    STALE = "STALE"
    PAUSED = "PAUSED"
    RESTORED = "RESTORED"
    REMOVED = "REMOVED"
    PARTITIONED = "PARTITIONED"
