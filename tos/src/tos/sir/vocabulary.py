"""Safety-incident vocabulary — the SIR StrEnums + transcribed anchors (design #28 §2.2).

Spec terms = code terms (design #28 §2.2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-027 (§9 line 278-286 incident lifecycle, §5.10 line 146 closure decision
result, §5.3 line 116 record version state, §18 line 472 communication honesty ladder, §8 line 250-257
signal classification, §5.6 line 130 dependency-closure dimension catalogue).

**Truthy-sentinel structural seal (design #28 §2.2/§4.2 — #13/#14 M1 adopted from the start).**
``IncidentLifecycleState`` (the 8-state lifecycle), ``ClosureDecisionResult`` (DENY / HOLD /
CLOSE_ADMINISTRATIVELY), ``IncidentRecordState`` (DRAFT / ACTIVE / SUPERSEDED / REOPENED),
``CommunicationAssertionKind`` (the 9-token honesty ladder), ``SignalClassificationClass`` (the 8
classification classes) and ``ClosureDimension`` (the 22 closure dimensions) are non-empty ``StrEnum``
strings, so a bare ``if result:`` / ``bool(state)`` would read a **denial / restrictive / non-permissive**
member (``DENY`` / ``HOLD`` / ``SUSPECTED`` / ``CONTAINING`` / ``STABILIZED_NON_LIVE`` /
``UNESTABLISHED_SCOPE_SEVERITY``) as **truthy** — a catastrophic silent fail-open that reads a
*rejection* or a *restrictive* state as a *go* (ADR §5.10 "An immutable independent result of ``DENY``,
``HOLD``, or ``CLOSE_ADMINISTRATIVELY`` ... It creates no permissive state"; §9 line 290 "``SUSPECTED``
is restrictive for the greatest credible scope; it is not permission to wait"). Each subclasses
:class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``, making
them *truthy-untestable*. The mandated consume gates are the explicit positive-identity comparison
(``result is ClosureDecisionResult.CLOSE_ADMINISTRATIVELY`` / ``state is
IncidentLifecycleState.CLOSED``) — everything else is denial. Isomorphic to the wdr ``DecisionResult``
seal, the cur ``ProofResult`` seal, the rlp ``PlanResult`` seal and the iap ``ApprovalResult`` seal;
authored **locally-fresh** here (sibling edge 0 — no wdr / cur / rlp / iap import, design #28 §3.3).

``CLOSED`` is a member, but it grants nothing: ADR §9 line 295 "``CLOSED`` is administrative only and
does not transition to ``ACTIVE``, ``ARMED``, ``READY``, or any live state" — the all-false
:class:`~tos.sir._base.AllFalseIncidentAuthority` holds on every artifact regardless of lifecycle state.

**Same-name / different-proposition seals (design #28 §0.5 — three witnessed collisions).**
``IncidentLifecycleState.SUSPECTED`` is the *incident* lifecycle and is a different proposition from
the evidence gap lifecycle ``GapStatus.SUSPECTED`` (``evidence/gap.py:41``); ``ClosureDimension`` is the
*incident dependency-closure* catalogue and is a different axis from the cur currentness dimension key
``DimensionKey.INCIDENT`` (``cur/vocabulary.py:143``); and the spg governed-artifact-**kind** string
tokens ``SAFETY_INCIDENT_POLICY`` / ``ACTIVE_SAFETY_INCIDENT_SET`` (``spg/vocabulary.py:215-216``) name
the *kind of artifact ADR-002-014 governs*, not the artifact models authored in
:mod:`tos.sir.records`. None of the three is imported (sibling edge 0).

**Manually-transcribed regression anchors (design #28 §7.2 / appendices A-D).** The 8-state lifecycle
order, the 8 classification classes, the 9 honesty tokens, the 22 closure dimensions, the 12-item
closure contract, the 10 controlled-shutdown steps and the 7 shutdown prohibitions are **hand
transcriptions** of the ADR, not derivations; the ``tos/tests/sir`` anchor-drift properties assert each
one still equals its ADR reference set so a drift is caught immediately (the wdr ``ScopeDimension`` /
cur ``DimensionKey`` precedent).

This module names **no** concrete broker (broker-agnostic — project memory ``tos-spec-broker-
agnostic``; design #28 §0.2) and hardcodes **no** numeric floor / size / duration / threshold: every
bound is an injected Profile-INSTANCE value, null in Phase 1 (design #28 §8). An enum member is a
structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #28 §0.3). Clock-free.

Regime tag: restrictive-declaration / exact-scope-combined / evidence-honesty predicate substrate only;
``SIR-EV-001..012`` all remain NOT_IMPLEMENTED; **EV-L1-complete claim forbidden**.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "IncidentLifecycleState",
    "ClosureDecisionResult",
    "IncidentRecordState",
    "CommunicationAssertionKind",
    "SignalClassificationClass",
    "ClosureDimension",
    "INCIDENT_LIFECYCLE_ORDER",
    "RESTRICTIVE_LIFECYCLE_STATES",
    "MANDATED_CLOSURE_DIMENSION_FLOOR",
    "CLOSURE_CONTRACT_ITEMS",
    "CLOSURE_CONTRACT_ITEM_POLARITY",
    "CLOSURE_CONTRACT_ITEM_COUNT",
    "SHUTDOWN_STEP_KINDS",
    "SHUTDOWN_PROHIBITIONS",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #28 §2.2/§4.2).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(state)`` would read a denial
    / restrictive / non-permissive member (``DENY`` / ``HOLD`` / ``SUSPECTED`` / ``CONTAINING`` /
    ``STABILIZED_NON_LIVE`` / ``UNESTABLISHED_SCOPE_SEVERITY``) as truthy — a catastrophic silent
    fail-open that reads a rejection or a restrictive state as a go. :meth:`__bool__` therefore raises
    ``TypeError`` on every member, so the misuse surfaces as a loud runtime error rather than a silent
    pass. Consumers MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic
    to the wdr / cur / rlp / iap seals; authored **locally-fresh** here (sibling edge 0, no wdr / cur /
    rlp / iap import — design #28 §3.3). ``is`` identity, ``.value``, hashing, set membership, sorting
    and ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #28 §2.2/§4.2).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is ClosureDecisionResult.CLOSE_ADMINISTRATIVELY``;
                ``state is IncidentLifecycleState.CLOSED``); a bare ``if result:`` / ``bool(result)``
                would fail open on the truthy denial / restrictive strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is ClosureDecisionResult.CLOSE_ADMINISTRATIVELY`; "
            "`state is IncidentLifecycleState.CLOSED`) per the truthy-sentinel seal (design "
            "#28 §2.2/§4.2). The denial / restrictive members are non-empty strings and a bare "
            "`if result:` would fail open — reading a rejection or a restrictive state as a go."
        )


class IncidentLifecycleState(_NonTruthyStrEnum):
    """The incident lifecycle state (ADR-002-027 §9 line 278-286, non-truthy — 8-state).

    §9 line 278-286 verbatim flow: ``SUSPECTED -> DECLARED -> CONTAINING -> STABILIZED_NON_LIVE ->
    INVESTIGATING -> REMEDIATION_PENDING -> ELIGIBLE_FOR_CLOSURE -> CLOSED``. §9 line 290 "``SUSPECTED``
    is restrictive for the greatest credible scope; it is not permission to wait"; line 294
    "``ELIGIBLE_FOR_CLOSURE`` is a review input, not closure"; line 295 "``CLOSED`` is administrative
    only and does not transition to ``ACTIVE``, ``ARMED``, ``READY``, or any live state"; line 296 a
    material post-closure signal creates a new Incident Generation and a new or reopened immutable
    record — "it does not edit history". **Truthy-untestable** (``__bool__`` raises): every pre-closure
    state is a non-empty restrictive string, so ``if state:`` would read a *restriction* as a *go*.

    **No state grants authority** — not even ``CLOSED`` (all-false
    :class:`~tos.sir._base.AllFalseIncidentAuthority`, SIR-INV-001 / SIR-INV-012). **Same-name /
    different-proposition seal** (design #28 §0.5): the evidence gap lifecycle also has a ``SUSPECTED``
    member (``evidence/gap.py:41``); that is the *evidence gap* axis, this is the *incident* axis — the
    strings collide, the propositions do not, and ``tos.evidence`` is not imported (sibling edge 0).

    This is a **manually-transcribed regression anchor** of ADR §9 line 278-286 (design #28 §7.2 /
    appendix D): the anchor-drift property asserts the enum equals the ADR 8-state reference set.
    """

    SUSPECTED = "SUSPECTED"
    DECLARED = "DECLARED"
    CONTAINING = "CONTAINING"
    STABILIZED_NON_LIVE = "STABILIZED_NON_LIVE"
    INVESTIGATING = "INVESTIGATING"
    REMEDIATION_PENDING = "REMEDIATION_PENDING"
    ELIGIBLE_FOR_CLOSURE = "ELIGIBLE_FOR_CLOSURE"
    CLOSED = "CLOSED"


class ClosureDecisionResult(_NonTruthyStrEnum):
    """The Incident Closure Decision result (ADR-002-027 §5.10 line 146, non-truthy — critical seal).

    §5.10 verbatim: "An immutable independent result of ``DENY``, ``HOLD``, or
    ``CLOSE_ADMINISTRATIVELY`` for one exact current incident and Active Safety Incident Set digest. **It
    creates no permissive state.**" **Truthy-untestable** (``__bool__`` raises): ``DENY`` / ``HOLD`` are
    non-empty strings, so ``if result:`` would read a *denial* as a *closure* — the catastrophic
    fail-open this seal blocks. The mandated consume gate is ``result is
    ClosureDecisionResult.CLOSE_ADMINISTRATIVELY``; every other value is denial.
    ``CLOSE_ADMINISTRATIVELY`` itself grants **no** authority (§20 line 503 item 12; SIR-INV-012 line 202
    "It does not establish safe state, release capacity, clear UNKNOWN or HALT, validate configuration,
    restore scope, satisfy recovery, or authorize transmission") — it is an administrative record
    transition only, single-use, and never consumable by a live-authority path (§20 line 505).

    **SIR-owned vocabulary** (design #28 §0.5 negative grep: ``ClosureDecisionResult`` /
    ``CLOSE_ADMINISTRATIVELY`` are absent from every other ``tos`` package) — seam conflict 0.
    """

    DENY = "DENY"
    HOLD = "HOLD"
    CLOSE_ADMINISTRATIVELY = "CLOSE_ADMINISTRATIVELY"


class IncidentRecordState(_NonTruthyStrEnum):
    """The append-only incident record version state (ADR-002-027 §5.3 / §9 line 296, non-truthy — 4).

    §5.3 verbatim: "An immutable **versioned** record of one incident identity ... It grants no
    authority." §9 line 296: a material post-closure signal creates "a new or reopened immutable record;
    it does not edit history". The four version states are ``DRAFT`` (not yet the current version),
    ``ACTIVE`` (the current version), ``SUPERSEDED`` (replaced by a newer version) and ``REOPENED`` (a
    §9 line 296 post-closure reopening under a newer Incident Generation).

    **``ACTIVE`` means the record *version* is current — never that the incident is live or
    permissive.** That is a different axis from :class:`IncidentLifecycleState` (where even ``CLOSED``
    is non-permissive, §9 line 295); the all-false authority holds on every combination.
    **Truthy-untestable** (``__bool__`` raises): a non-current version is a non-empty string, so ``if
    state:`` would read ``SUPERSEDED`` as a go.
    """

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REOPENED = "REOPENED"


class CommunicationAssertionKind(_NonTruthyStrEnum):
    """The communication honesty ladder token (ADR-002-027 §18 line 472, non-truthy — 9-token).

    §18 line 472 verbatim: "Communications SHALL distinguish observed fact, conservative assumption,
    unresolved UNKNOWN, planned action, authorized action, transmitted attempt, broker evidence,
    verified result, and administrative decision. A message acknowledgement is never an enforcement
    acknowledgement." The nine kinds are mutually **distinguished**; the ADR states a *distinction*
    obligation, **not** a total strength order — any "which assertion outranks which" judgement is
    policy-owned and Phase-0 (design #28 §5.3 conjunct 2, M7: the v1.0 strength total-order was
    withdrawn as an invention).

    **Truthy-untestable** (``__bool__`` raises): ``UNRESOLVED_UNKNOWN`` / ``CONSERVATIVE_ASSUMPTION``
    are non-empty strings, so ``if kind:`` would read an *unknown* as a *fact*. **SIR-owned
    vocabulary** (design #28 §0.5 negative grep: no ``tos`` package owns a communication-assertion /
    enforcement-ack enum) — the wdr ``WaivedEvidenceStatus`` precedent; evidence custody
    (ADR-002-016) is a different axis and is injected, never re-authored (design #28 §3.5).

    A **manually-transcribed regression anchor** of ADR §18 line 472 (design #28 §7.2 / appendix C).
    """

    OBSERVED_FACT = "OBSERVED_FACT"
    CONSERVATIVE_ASSUMPTION = "CONSERVATIVE_ASSUMPTION"
    UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN"
    PLANNED_ACTION = "PLANNED_ACTION"
    AUTHORIZED_ACTION = "AUTHORIZED_ACTION"
    TRANSMITTED_ATTEMPT = "TRANSMITTED_ATTEMPT"
    BROKER_EVIDENCE = "BROKER_EVIDENCE"
    VERIFIED_RESULT = "VERIFIED_RESULT"
    ADMINISTRATIVE_DECISION = "ADMINISTRATIVE_DECISION"


class SignalClassificationClass(_NonTruthyStrEnum):
    """The Safety Signal classification class (ADR-002-027 §8 line 250-257, non-truthy — 8-class).

    §8 line 248 "The Safety Incident Policy SHALL classify at least:" the eight classes — (250) a
    suspected or actual Hard Safety Envelope violation; (251) an RCL / writer-fence / capacity /
    currentness / authority / credential / route / final-egress bypass; (252) broker / order / fill /
    exposure state that is missing, contradictory, stale, or externally changed; (253) protection loss,
    replacement gap, action-flow exhaustion, venue restriction, or trapped exposure; (254) Critical
    Input, configuration, identity, time, evidence, recovery, or failure-domain compromise; (255)
    unauthorized live / non-live crossover or external broker activity; (256) a failed bound, security
    control, independent approval, or restricted-live gate; (257) "any condition whose scope or severity
    cannot yet be established conservatively".

    ``UNESTABLISHED_SCOPE_SEVERITY`` (line 257) is the **fail-closed convergence point**: a signal whose
    scope or severity cannot yet be established conservatively is still a declaration subject and
    expands to the greatest credible scope (design #28 §5.1). **Truthy-untestable** (``__bool__``
    raises). A **manually-transcribed regression anchor** of ADR §8 line 250-257 (design #28 §7.2 /
    appendix C).
    """

    HARD_ENVELOPE_VIOLATION = "HARD_ENVELOPE_VIOLATION"
    CONTROL_BYPASS = "CONTROL_BYPASS"
    BROKER_STATE_ANOMALY = "BROKER_STATE_ANOMALY"
    PROTECTION_LOSS = "PROTECTION_LOSS"
    CRITICAL_INPUT_COMPROMISE = "CRITICAL_INPUT_COMPROMISE"
    UNAUTHORIZED_CROSSOVER = "UNAUTHORIZED_CROSSOVER"
    FAILED_GATE = "FAILED_GATE"
    UNESTABLISHED_SCOPE_SEVERITY = "UNESTABLISHED_SCOPE_SEVERITY"


class ClosureDimension(_NonTruthyStrEnum):
    """The Incident Dependency Closure dimension (ADR-002-027 §5.6 line 130, non-truthy — 22-dim).

    §5.6 verbatim: "Every Safety Cell, Capacity Domain, legal portfolio, account, broker, venue,
    instrument, strategy, order, position, commitment, protection, credential, route, session,
    generation, component, artifact, failure domain, evidence path, external activity, and downstream
    consumer that may be affected by the signal or response." A **closed** 22-member catalogue consumed
    by the set-membership / subset math of
    :func:`~tos.sir.predicates.dependency_closure_complete`; it is a **structural dimension
    identifier**, never a numeric threshold — enumerating it is **not** a numeric hardcode (design #28
    §2.2/§8; the wdr ``ScopeDimension`` / cur ``DimensionKey`` field-enumeration precedent).

    **Truthy-sealed** (design #28 §4.2 lists it among the six sealed enums) even though it is consumed
    by membership rather than as a gate result — the seal is free and removes one whole class of misuse.
    **Different axis from cur** (design #28 §0.5 seal 3): ``cur/vocabulary.py:143``
    ``DimensionKey.INCIDENT`` is a *currentness* dimension key (cur owns the currentness completeness
    judgement); this enum is the *incident dependency-closure* catalogue. Neither imports the other.

    A **manually-transcribed regression anchor** of ADR §5.6 line 130 (design #28 §7.2 / appendix D).
    """

    SAFETY_CELL = "SAFETY_CELL"
    CAPACITY_DOMAIN = "CAPACITY_DOMAIN"
    LEGAL_PORTFOLIO = "LEGAL_PORTFOLIO"
    ACCOUNT = "ACCOUNT"
    BROKER = "BROKER"
    VENUE = "VENUE"
    INSTRUMENT = "INSTRUMENT"
    STRATEGY = "STRATEGY"
    ORDER = "ORDER"
    POSITION = "POSITION"
    COMMITMENT = "COMMITMENT"
    PROTECTION = "PROTECTION"
    CREDENTIAL = "CREDENTIAL"
    ROUTE = "ROUTE"
    SESSION = "SESSION"
    GENERATION = "GENERATION"
    COMPONENT = "COMPONENT"
    ARTIFACT = "ARTIFACT"
    FAILURE_DOMAIN = "FAILURE_DOMAIN"
    EVIDENCE_PATH = "EVIDENCE_PATH"
    EXTERNAL_ACTIVITY = "EXTERNAL_ACTIVITY"
    DOWNSTREAM_CONSUMER = "DOWNSTREAM_CONSUMER"


#: The §9 line 278-286 lifecycle **order** as transcribed (a regression anchor, design #28 §7.2).
#: Order is documentary only — ADR §9 line 297 "No timer, task count, message acknowledgement, absence
#: of alerts, or human status automatically advances the lifecycle", so no predicate advances a state.
INCIDENT_LIFECYCLE_ORDER: tuple[IncidentLifecycleState, ...] = (
    IncidentLifecycleState.SUSPECTED,
    IncidentLifecycleState.DECLARED,
    IncidentLifecycleState.CONTAINING,
    IncidentLifecycleState.STABILIZED_NON_LIVE,
    IncidentLifecycleState.INVESTIGATING,
    IncidentLifecycleState.REMEDIATION_PENDING,
    IncidentLifecycleState.ELIGIBLE_FOR_CLOSURE,
    IncidentLifecycleState.CLOSED,
)

#: Every lifecycle state that is **not** ``CLOSED`` — i.e. every restrictive, still-open state (§9 line
#: 290 "``SUSPECTED`` is restrictive"; line 295 ``CLOSED`` is administrative only). Derived from the
#: enum so it can never drift; consumed by
#: :func:`~tos.sir.predicates.dominating_open_incident_present` (design #28 §3.6/§6.3).
RESTRICTIVE_LIFECYCLE_STATES: frozenset[IncidentLifecycleState] = frozenset(
    IncidentLifecycleState
) - {IncidentLifecycleState.CLOSED}

#: The §5.6 mandated closure floor: **every** ``ClosureDimension`` member.
#: :func:`~tos.sir.predicates.dependency_closure_complete` floors its ``applicable_dimensions``
#: argument to at least this set — a caller may require *more* but **never fewer** (design #28 §5.2
#: conjunct 4 "전 22차원 ... present"; the wdr ``MANDATED_SCOPE_FLOOR`` / cur ``MANDATED_DIMENSION_FLOOR``
#: precedent). Derived from the enum so it can never drift below the catalogue; the §7.2 anchor-drift
#: property asserts the derivation equals the ADR §5.6 line 130 reference set.
MANDATED_CLOSURE_DIMENSION_FLOOR: frozenset[ClosureDimension] = frozenset(
    ClosureDimension
)

#: The §20 line 492-503 closure-contract items, transcribed in ADR order (design #28 §6.8b / appendix
#: B). Structural labels for the 12 ``closure_contract_items`` slots — never a numeric bound.
CLOSURE_CONTRACT_ITEMS: tuple[str, ...] = (
    "SIGNALS_SEVERITY_SCOPE_CLOSURE_COMMON_MODE_CHRONOLOGY_COMPLETE",
    "RESTRICTION_AND_HARD_FENCE_CURRENT",
    "BROKER_ATTEMPT_FINAL_QUANTITY_PROOF_OR_OBLIGATION",
    "POSITIONS_ORDERS_FILLS_EXTERNAL_MARGIN_SETTLEMENT_PROTECTION_RECONCILED_OR_RETAINED",
    "CONTAINMENT_AND_SHUTDOWN_DISPOSITION_EVIDENCE_BACKED",
    "EVIDENCE_GAPS_RESOLVED_OR_BLOCK",
    "ROOT_CAUSE_RECORDED_NOT_SUBSTITUTING",
    "REMEDIATION_AND_ROLLBACK_FRESH_CONFIGURATION",
    "RECOVERY_OBLIGATIONS_TRANSFERRED_BEHIND_RECOVERY_BARRIER",
    "INDEPENDENT_EFFECTIVE_PRINCIPAL_REVIEW_OR_SINGLE_OPERATOR_VARIANT",
    "OPEN_PARENT_CHILD_OVERLAP_SHARED_CAUSE_OR_COMMON_MODE_INVALIDATES",
    "EXPLICIT_NO_AUTHORITY_STATEMENT",
)

#: The polarity of each ``CLOSURE_CONTRACT_ITEMS`` slot (design #28 §4.3/§6.8b). ``True`` = **positive**
#: polarity (the slot admits only on ``is True``); ``False`` = **negative** polarity (the slot admits
#: only on ``is False``). Item 11 is the single negative slot: its proposition is "an open parent,
#: child, overlapping incident, shared cause, or common mode **invalidates** closure" (§20 line 502;
#: §4.3 row ``open_parent_present`` / ``common_mode_present``), so closure requires it positively
#: ``False``. ``None`` denies on **both** polarities (design #28 §4.3).
CLOSURE_CONTRACT_ITEM_POLARITY: tuple[bool, ...] = (
    True,
    True,
    True,
    True,
    True,
    True,
    True,
    True,
    True,
    True,
    False,
    True,
)

#: The §20 closure contract cardinality (12 items, ADR line 492-503). ``過 0 · 不 0``.
CLOSURE_CONTRACT_ITEM_COUNT: int = len(CLOSURE_CONTRACT_ITEMS)

#: The §12 line 343-352 controlled-shutdown 10-step ordering, transcribed in ADR order (design #28
#: §6.2 / appendix D). Structural step labels; the real ordering **proof** is L3 runtime (§6b).
SHUTDOWN_STEP_KINDS: tuple[str, ...] = (
    "LATCH_DENIAL_OF_NEW_RISK_BEFORE_STOPPING_PRODUCERS",
    "REVOKE_OR_FENCE_STALE_GENERATIONS",
    "ESTABLISH_DISPOSITION_OF_EVERY_PENDING_OR_UNKNOWN_ACTION",
    "PRESERVE_RCL_COMMITMENTS_AND_QUARANTINE_UNCERTAINTY",
    "INVENTORY_POSITIONS_ORDERS_FILLS_CASH_MARGIN_SETTLEMENT_EXPOSURE",
    "PRESERVE_PROTECTION_AND_OBTAIN_CANCELLATION_ARBITER_APPROVAL",
    "PRESERVE_HALT_LATCHES_RECONCILIATION_TIME_EVIDENCE_NOTIFICATION_RECOVERY",
    "HARD_FENCE_UNOBSERVABLE_PATHS",
    "RECORD_EVERY_STOP_FENCE_CHANGE_INTERACTION_AMBIGUITY_AND_TRANSFER",
    "LEAVE_SCOPE_NON_LIVE_BEHIND_THE_RECOVERY_BARRIER",
)

#: The §12 line 354-362 "Shutdown SHALL NOT:" 7-item prohibition set, transcribed (design #28 §6.2 /
#: appendix D). :func:`~tos.sir.predicates.controlled_shutdown_not_broker_finality` floors a
#: procedure's declared ``prohibited`` set to at least this set — a procedure may declare *more*
#: prohibitions but **never fewer**.
SHUTDOWN_PROHIBITIONS: frozenset[str] = frozenset(
    {
        "INFER_BROKER_FINALITY_FROM_PROCESS_OR_CONNECTION_STATE",
        "CANCEL_EVERY_ORDER_WITHOUT_PROTECTION_AND_LATE_FILL_ANALYSIS",
        "FORCE_LIQUIDATION_WHEN_EXIT_FEASIBILITY_UNPROVEN",
        "STOP_THE_ONLY_SURVIVING_SAFETY_PATH_WITHOUT_PROVEN_REPLACEMENT",
        "RELEASE_CAPACITY_BECAUSE_A_LEASE_OR_PROCESS_EXPIRED",
        "DELETE_QUEUES_JOURNALS_RECORDS_OR_IDENTITIES",
        "TREAT_A_CLEAN_DEPLOYMENT_SHUTDOWN_AS_CLOSURE_OR_READINESS",
    }
)
