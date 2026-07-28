"""Safety-telemetry vocabulary — the STM StrEnums + transcribed ADR anchors (design #30 §2.2).

Spec terms = code terms (design #30 §2.2; boundary design #1 §2.4). The eight enums are authored
**verbatim** from ADR-002-028 (§12 line 335 aggregate result, §23 line 499 dashboard status, §5.7 line
135 monitoring-gap taxonomy, §11 line 316 numeric input state, §11 line 314 + STM-INV-007 line 183
bound semantics, §8 line 249 telemetry criticality, §15 line 365 suppression lifecycle, §12 line 327 +
§13 line 347 coverage / dependency-closure dimension).

**Truthy-sentinel structural seal (design #30 §2.2/§4.2 — adopted from the start).** All eight are
non-empty ``StrEnum`` strings, so a bare ``if result:`` / ``bool(state)`` would read a **denial /
restrictive / malformed** member (``RESTRICTED`` / ``NON_CONFORMING`` / ``UNKNOWN`` / ``STALE`` /
``GAP`` / ``UNVERIFIED`` / ``NAN`` / ``PERCENTILE``) as **truthy** — a catastrophic silent fail-open
that reads a *rejection* as a *go*. Each subclasses :class:`_NonTruthyStrEnum`, whose
:meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``, making them *truthy-untestable*. The
**highest-risk case** is :class:`AggregateConformanceResult`: ``if snapshot.aggregate_result:`` would
read ``RESTRICTED`` / ``NON_CONFORMING`` / ``UNKNOWN`` — every one of which "denies dependent new risk"
(§12 line 335) — as a ``CONFORMING`` go. The mandated consume gates are the explicit positive-identity
comparisons (``result is AggregateConformanceResult.CONFORMING``; ``state is
NumericInputState.WELL_FORMED``; ``token is DashboardStatusToken.CURRENT_CONFORMING``). Isomorphic to
the ioc ``ConformanceResult.__bool__`` seal (``ioc/vocabulary.py:40-72``) and to the eleven
``_NonTruthyStrEnum`` packages (cur / egress / hag / iap / nontrade / posttrade / rlp / sbr / sir /
venue / wdr); authored **locally-fresh** here (sibling edge 0 — no sibling import, design #30 §3.3).

**Same-name / different-proposition seals (design #30 §0.5 — four witnessed collisions).**

* ``cur/vocabulary.py:144`` — cur's ``MONITORING`` currentness dimension key, a member of cur's
  mandated dimension floor (``cur/vocabulary.py:172``). Its completeness judgement stays **cur-owned**;
  stm produces that dimension's **value** (a Monitor Generation and a Continuous Conformance Snapshot
  digest) and re-authors none of cur's judgement. :class:`CoverageDimension` is a different axis
  entirely — the stm *coverage / dependency-closure* catalogue of §12 line 327 / §13 line 347.
* ``spg/vocabulary.py:217-219`` ``SAFETY_MONITORING_POLICY`` / ``CRITICAL_TELEMETRY_MANIFEST`` /
  ``MONITOR_COVERAGE_MANIFEST`` are governed-artifact-**kind** string tokens naming the *kind of
  artifact ADR-002-014 governs*, not the artifact models authored in :mod:`tos.stm.records`.
* ``ioc/vocabulary.py:40-72`` ``ConformanceResult`` {CONFORMANT / NON_CONFORMANT / UNKNOWN} is
  *intent-to-order command* conformance (ADR-002-020); :class:`AggregateConformanceResult` {CONFORMING
  / RESTRICTED / NON_CONFORMING / UNKNOWN} is *continuous conformance monitoring* (§12). Members and
  propositions both differ; only the truthy-sentinel **pattern** is reused.
* ``wdr/vocabulary.py:268`` ``CompensatingControlKind.MONITORING`` and ``brokercap/vocabulary.py:110``
  ``AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED`` share the "monitoring" string only.

That seal list is **representative, not exhaustive** — "conformance" / "escalation" / "monitoring"
tokens are shared across several siblings on different axes, which is why the
``tos/tests/stm/test_stm_anchor_resolution.py`` property re-fixes each collision mechanically rather
than by memory (design #30 §0.5 / FD §10.2 lesson). None of the four is imported (sibling edge 0).

**Manually-transcribed regression anchors (design #30 §7.2 / appendices A-M).** The 12-item coverage
closure, the 8-fact final-egress currentness vector, the 8 preserved-active suppression functions, the
12-row partition/failure matrix, the 12 Critical Telemetry binding groups, the 17-item shared-dependency
catalogue, the 14 all-false authority verbs, the 6 suppression prohibitions and the 4 restrictive-signal
prohibitions are **hand transcriptions** of the ADR, not derivations. The
``tos/tests/stm/test_stm_adr_enumeration_closure.py`` property re-parses ADR-002-028 itself and asserts
each transcription still equals its reference enumeration, both ways (過 0 · 不 0).

This module names **no** concrete broker (broker-agnostic — project memory ``tos-spec-broker-agnostic``;
design #30 §0.2) and hardcodes **no** numeric bound / age / duration / threshold: all eleven §29 OQ 12
keys are injected Profile-INSTANCE values, null in Phase 1 (design #30 §8). An enum member is a
structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #30 §0.3). Clock-free.

Regime tag: coverage-completeness / deterministic-evaluation predicate substrate only; closes **no**
STM-EV; ``STM-EV-001..012`` all remain NOT_IMPLEMENTED; **EV-L1-complete claim forbidden**.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "AggregateConformanceResult",
    "DashboardStatusToken",
    "MonitoringGapKind",
    "NumericInputState",
    "BoundSemanticKind",
    "TelemetryCriticality",
    "SuppressionLifecycleState",
    "CoverageDimension",
    "HARD_BOUND_KINDS",
    "NEUTRAL_BOUND_KINDS",
    "WEAK_BOUND_KINDS",
    "MALFORMED_NUMERIC_STATES",
    "DENYING_AGGREGATE_RESULTS",
    "RESTRICTIVE_SUPPRESSION_STATES",
    "IN_FORCE_SUPPRESSION_STATES",
    "COVERAGE_CLOSURE_ITEMS",
    "COVERAGE_CLOSURE_ITEM_COUNT",
    "FINAL_EGRESS_CURRENTNESS_FACTS",
    "SUPPRESSION_PRESERVED_FUNCTIONS",
    "PARTITION_FAILURE_MODES",
    "CRITICAL_TELEMETRY_BINDING_GROUPS",
    "SHARED_DEPENDENCY_ANCHOR",
    "ALL_FALSE_AUTHORITY_VERBS",
    "MONITORING_SUPPRESSION_PROHIBITIONS",
    "RESTRICTIVE_SIGNAL_PROHIBITIONS",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #30 §2.2/§4.2).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(state)`` would read a denial
    / restrictive / malformed member (``RESTRICTED`` / ``NON_CONFORMING`` / ``UNKNOWN`` / ``STALE`` /
    ``GAP`` / ``UNVERIFIED`` / ``NAN`` / ``PERCENTILE``) as truthy — a catastrophic silent fail-open
    that reads a rejection as a go. :meth:`__bool__` therefore raises ``TypeError`` on every member, so
    the misuse surfaces as a loud runtime error rather than a silent pass. Consumers MUST use the
    explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to the ioc
    ``ConformanceResult`` seal (``ioc/vocabulary.py:63``) and the eleven ``_NonTruthyStrEnum``
    packages; authored **locally-fresh** here (sibling edge 0 — design #30 §3.3). ``is`` identity,
    ``.value``, hashing, set membership, sorting and ``model_dump`` are all unaffected (none calls
    ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #30 §2.2/§4.2).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is AggregateConformanceResult.CONFORMING``; ``state is
                NumericInputState.WELL_FORMED``; ``token is
                DashboardStatusToken.CURRENT_CONFORMING``); a bare ``if result:`` / ``bool(result)``
                would fail open on the truthy denial / restrictive / malformed strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is AggregateConformanceResult.CONFORMING`; "
            "`state is NumericInputState.WELL_FORMED`) per the truthy-sentinel seal (design "
            "#30 §2.2/§4.2). The denial / restrictive / malformed members are non-empty strings "
            "and a bare `if result:` would fail open — reading a rejection as a go."
        )


class AggregateConformanceResult(_NonTruthyStrEnum):
    """The Continuous Conformance Snapshot aggregate result (§12 line 335, non-truthy — 4-token).

    §12 line 335 verbatim: "Allowed aggregate results are ``CONFORMING``, ``RESTRICTED``,
    ``NON_CONFORMING``, and ``UNKNOWN``. ``CONFORMING`` requires every required item to be current,
    complete, and independently valid under policy. ``RESTRICTED``, ``NON_CONFORMING``, or ``UNKNOWN``
    denies dependent new risk for the affected scope."

    **Even ``CONFORMING`` grants nothing** (§1 line 25: it "does not approve an action, create
    headroom, mark an RFC requirement ``PASS``, satisfy preventive control, establish broker finality,
    activate configuration, issue authority, permit transmission, close an incident, establish recovery
    readiness, restore scope, or re-arm") — the all-false
    :class:`~tos.stm._base.AllFalseMonitoringAuthority` holds on every artifact regardless of result.

    **This enum is the truthy-sentinel's first-priority defence** (design #30 §4.2): the three denying
    members are non-empty strings, so ``if snapshot.aggregate_result:`` would read a *denial* as a *go*.
    ``__bool__`` raises; the mandated gate is ``result is AggregateConformanceResult.CONFORMING``.

    **Name-collision seal** (design #30 §0.5 seal 3): ioc ``ConformanceResult``
    (``ioc/vocabulary.py:40-72``, CONFORMANT / NON_CONFORMANT / UNKNOWN) is *intent-to-order command*
    conformance (ADR-002-020) — different members, different proposition; only the seal pattern is
    reused, and ``tos.ioc`` is not imported.

    A **manually-transcribed regression anchor** of ADR §12 line 335 (design #30 §7.2 / appendix A).
    """

    CONFORMING = "CONFORMING"
    RESTRICTED = "RESTRICTED"
    NON_CONFORMING = "NON_CONFORMING"
    UNKNOWN = "UNKNOWN"


class DashboardStatusToken(_NonTruthyStrEnum):
    """The dashboard status token (§23 line 499, non-truthy — 7-token, no-green-default).

    §23 line 499 verbatim: "Dashboards SHALL distinguish at minimum ``CURRENT_CONFORMING``,
    ``RESTRICTED``, ``NON_CONFORMING``, ``UNKNOWN``, ``STALE``, ``GAP``, and ``UNVERIFIED``. Rendering
    failures or unknown state SHALL NOT default to green." The seven statuses are mutually
    **distinguished** — none may be abbreviated into or promoted to another — and a rendering failure or
    unknown state is **never** ``CURRENT_CONFORMING``
    (:func:`~tos.stm.predicates.evidence_and_status_honest`).

    **Truthy-untestable** (``__bool__`` raises): ``STALE`` / ``GAP`` / ``UNVERIFIED`` are non-empty
    strings, so ``if token:`` would read an *unverified* view as a *green* one.

    A **manually-transcribed regression anchor** of ADR §23 line 499 (design #30 §7.2 / appendix D).
    """

    CURRENT_CONFORMING = "CURRENT_CONFORMING"
    RESTRICTED = "RESTRICTED"
    NON_CONFORMING = "NON_CONFORMING"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    GAP = "GAP"
    UNVERIFIED = "UNVERIFIED"


class MonitoringGapKind(_NonTruthyStrEnum):
    """The Safety Monitoring Gap taxonomy (§5.7 line 135, non-truthy — 10-kind).

    §5.7 line 135 verbatim: "An immutable record of **missing, stale, conflicting, ambiguous,
    discontinuous, incomplete, unverified, common-mode, failed, or suppressed** monitoring coverage and
    its greatest credible affected scope and restrictive disposition."

    **Every kind carries a restrictive disposition** (§13): a gap is "a gap, not an exemption"
    (STM-INV-002 line 163) and "Monitoring recovery does not close the gap by itself" (§13 line 349).
    Consumed by :func:`~tos.stm.predicates.gap_is_restrictive_not_exemption`.

    **Honest anchor note** (design #30 §2.2, MINOR-1): §1 line 27 lists a *separate*, longer set of
    gap-**triggering conditions**; it is not this classification anchor. The single classification
    anchor is §5.7 line 135.

    A **manually-transcribed regression anchor** of ADR §5.7 line 135 (design #30 §7.2 / appendix E).
    """

    MISSING = "MISSING"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    AMBIGUOUS = "AMBIGUOUS"
    DISCONTINUOUS = "DISCONTINUOUS"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIED = "UNVERIFIED"
    COMMON_MODE = "COMMON_MODE"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


class NumericInputState(_NonTruthyStrEnum):
    """The monitor-evaluation numeric input state (§11 line 316, non-truthy — 12-token).

    §11 line 316 verbatim: "**Unknown numeric input, NaN, infinity, overflow, underflow,
    non-convergence, unit mismatch, parser differential, missing sample, insufficient history, or
    evaluator disagreement** yields ``UNKNOWN`` or a restrictive result. It never yields ``CONFORMING``
    by default." Eleven malformed states plus the one well-formed state = 12.

    :data:`MALFORMED_NUMERIC_STATES` is **derived** from the enum (every member except
    ``WELL_FORMED``), so it can never drift below the catalogue.
    :func:`~tos.stm.predicates.numeric_result_not_conforming_by_default` denies any evaluation whose
    result is ``CONFORMING`` while its numeric input state is not ``WELL_FORMED`` — the fail-closed
    direction §11 line 316 mandates.

    **Truthy-untestable** (``__bool__`` raises): ``NAN`` / ``OVERFLOW`` / ``PARSER_DIFFERENTIAL`` are
    non-empty strings, so ``if state:`` would read a *malformed* input as a *well-formed* one.

    A **manually-transcribed regression anchor** of ADR §11 line 316 (design #30 §7.2 / appendix B).
    """

    WELL_FORMED = "WELL_FORMED"
    UNKNOWN = "UNKNOWN"
    NAN = "NAN"
    INFINITY = "INFINITY"
    OVERFLOW = "OVERFLOW"
    UNDERFLOW = "UNDERFLOW"
    NON_CONVERGENT = "NON_CONVERGENT"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    PARSER_DIFFERENTIAL = "PARSER_DIFFERENTIAL"
    MISSING_SAMPLE = "MISSING_SAMPLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    EVALUATOR_DISAGREEMENT = "EVALUATOR_DISAGREEMENT"


class BoundSemanticKind(_NonTruthyStrEnum):
    """The approved-bound semantic kind (§11 line 314 + STM-INV-007 line 183, non-truthy — 12-token).

    §11 line 314 verbatim: "An approved hard maximum cannot be implemented as a **percentile, average,
    best-effort target**, or window that permits an individual exceedance." STM-INV-007 line 183
    verbatim: hard maxima and their semantics "cannot be replaced by a percentile, average, **local
    threshold, hidden grace period, or favorable sampling rule**." The union of the two weak-form lists
    is the six-member :data:`WEAK_BOUND_KINDS`.

    The catalogue is partitioned into three **explicit membership sets** — :data:`HARD_BOUND_KINDS`
    (4), :data:`NEUTRAL_BOUND_KINDS` (2), :data:`WEAK_BOUND_KINDS` (6). The partition is a
    **membership** statement, never a total strength order: no "which kind outranks which" ranking is
    invented here (design #30 §2.2/§4.3 three-value discipline).

    **Whitelist, not denylist** (design #30 §2.2 M3 — the #25 RLP MAJOR-1 isomorph):
    :func:`~tos.stm.predicates.bound_integrity_preserved` admits only an implemented kind that is
    **identical to the approved kind and inside a declared partition**; every other combination,
    **including a future enum member nobody has classified yet**, denies. A denylist of
    ``{PERCENTILE, AVERAGE, BEST_EFFORT_TARGET}`` would have leaked the moment ``LOCAL_THRESHOLD``
    was added — which is exactly the drift STM-INV-007 line 183 names.

    **Truthy-untestable** (``__bool__`` raises). A **manually-transcribed regression anchor** of ADR
    §11 line 314 + STM-INV-007 line 183 (design #30 §7.2 / appendix C).
    """

    # HARD (4) — exact-preservation kinds
    HARD_MAXIMUM = "HARD_MAXIMUM"
    HARD_MINIMUM = "HARD_MINIMUM"
    EXACT_MATCH = "EXACT_MATCH"
    MONOTONIC_SEQUENCE = "MONOTONIC_SEQUENCE"
    # NEUTRAL (2)
    RANGE = "RANGE"
    RATE = "RATE"
    # WEAK (6) — §11 line 314 (3) + STM-INV-007 line 183 (3)
    PERCENTILE = "PERCENTILE"
    AVERAGE = "AVERAGE"
    BEST_EFFORT_TARGET = "BEST_EFFORT_TARGET"
    LOCAL_THRESHOLD = "LOCAL_THRESHOLD"
    HIDDEN_GRACE_PERIOD = "HIDDEN_GRACE_PERIOD"
    FAVORABLE_SAMPLING_RULE = "FAVORABLE_SAMPLING_RULE"


class TelemetryCriticality(_NonTruthyStrEnum):
    """The Critical Telemetry criticality classification (§8 line 249, non-truthy — 3-token).

    §8 line 249 verbatim: "**Unknown materiality is Critical.** A producer, monitor owner, dashboard
    owner, or consumer SHALL NOT self-classify a telemetry item as non-Critical merely because the
    underlying preventive control exists elsewhere."

    ``UNKNOWN_MATERIALITY`` therefore **folds to ``CRITICAL``** and can never be excluded from
    coverage, with or without a proof (:func:`~tos.stm.predicates.critical_coverage_complete_or_gap`
    conjunct 4). ``NON_CRITICAL_APPROVED_EXCLUSION`` still requires the §9 line 290
    independent-governance proof before it excludes anything.

    **Truthy-untestable** (``__bool__`` raises): ``UNKNOWN_MATERIALITY`` is a non-empty string, so
    ``if criticality:`` would read an *unknown* materiality as a settled one.
    """

    CRITICAL = "CRITICAL"
    NON_CRITICAL_APPROVED_EXCLUSION = "NON_CRITICAL_APPROVED_EXCLUSION"
    UNKNOWN_MATERIALITY = "UNKNOWN_MATERIALITY"


class SuppressionLifecycleState(_NonTruthyStrEnum):
    """The Monitoring Suppression lifecycle state (§15 line 365, non-truthy — 4-token).

    §15 line 365 verbatim: Critical monitoring suppression is "deny-by-default, immutable, exact-scope,
    purpose-bound, short-lived, independently approved, generation-bound, visible, evidenced, and
    **automatically restrictive on expiry or uncertainty**." §21 line 458: "suppression state missing,
    stale, or expired -> treat monitoring state as restricted and unsuppressed."

    ``EXPIRED`` and ``UNKNOWN`` are therefore the two :data:`RESTRICTIVE_SUPPRESSION_STATES`.

    **``ACTIVE`` means only that the suppression window is in force — never that safety monitoring is
    disabled**: all eight §15 line 367-376 :data:`SUPPRESSION_PRESERVED_FUNCTIONS` stay active
    throughout (:func:`~tos.stm.predicates.suppression_cannot_suppress_safety`).

    **Truthy-untestable** (``__bool__`` raises): ``EXPIRED`` / ``UNKNOWN`` are non-empty strings, so
    ``if state:`` would read an expired suppression as a live governed one.
    """

    REQUESTED = "REQUESTED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class CoverageDimension(_NonTruthyStrEnum):
    """The coverage / dependency-closure dimension (§12 line 327 + §13 line 347, non-truthy — 11-dim).

    §12 line 327 binds the snapshot to "exact scope and dependency closure"; §13 line 347 names the
    axes verbatim: "the scope expands across shared **accounts, Capacity Domains, Safety Cells, broker
    sessions, credentials, routes, datastores, clocks, deployments, policies, or failure domains** until
    isolation is positively proven." A **closed** 11-member catalogue consumed by the subset math of
    :func:`~tos.stm.predicates.critical_coverage_complete_or_gap` conjunct 6; it is a **structural
    dimension identifier**, never a numeric threshold — enumerating it is **not** a numeric hardcode
    (design #30 §2.2/§8).

    **Different axis from cur** (design #30 §0.5 seal 1): ``cur/vocabulary.py:144``
    the ``MONITORING`` member of cur's dimension-key enum is a *currentness* key inside cur's floor
    (``cur/vocabulary.py:172``) and cur owns that dimension's completeness judgement; this enum is the
    stm *coverage / dependency-closure* catalogue. stm produces the MONITORING dimension's **value**
    and re-authors none of cur's judgement. Neither imports the other.

    **Truthy-sealed** (design #30 §4.2 lists it among the eight sealed enums) even though it is
    consumed by membership rather than as a gate result — the seal is free and removes a whole class of
    misuse.

    A **manually-transcribed regression anchor** of ADR §13 line 347 (design #30 §7.2 / appendix L).
    """

    ACCOUNT = "ACCOUNT"
    CAPACITY_DOMAIN = "CAPACITY_DOMAIN"
    SAFETY_CELL = "SAFETY_CELL"
    BROKER_SESSION = "BROKER_SESSION"
    CREDENTIAL = "CREDENTIAL"
    ROUTE = "ROUTE"
    DATASTORE = "DATASTORE"
    CLOCK = "CLOCK"
    DEPLOYMENT = "DEPLOYMENT"
    POLICY = "POLICY"
    FAILURE_DOMAIN = "FAILURE_DOMAIN"


# ===========================================================================
# derived membership sets (never hand-listed twice — drift-proof by construction)
# ===========================================================================

#: The four **exact-preservation** bound kinds (§11 line 314 "an approved hard maximum";
#: STM-INV-007 line 183 "Hard maxima, units, scope, trigger, start and stop events, composition,
#: uncertainty, and failure response"). Membership, **not** a strength order.
HARD_BOUND_KINDS: frozenset[BoundSemanticKind] = frozenset(
    {
        BoundSemanticKind.HARD_MAXIMUM,
        BoundSemanticKind.HARD_MINIMUM,
        BoundSemanticKind.EXACT_MATCH,
        BoundSemanticKind.MONOTONIC_SEQUENCE,
    }
)

#: The two neutral bound kinds — neither a hard bound nor one of the §11 line 314 / INV-007 line 183
#: weak forms. They are still held to exact preservation by the whitelist.
NEUTRAL_BOUND_KINDS: frozenset[BoundSemanticKind] = frozenset(
    {BoundSemanticKind.RANGE, BoundSemanticKind.RATE}
)

#: The six **weak-form** bound kinds a hard bound may never be implemented as: §11 line 314
#: "percentile, average, best-effort target" + STM-INV-007 line 183 "percentile, average, local
#: threshold, hidden grace period, or favorable sampling rule". 過 0 · 不 0 against appendix C.
WEAK_BOUND_KINDS: frozenset[BoundSemanticKind] = frozenset(
    {
        BoundSemanticKind.PERCENTILE,
        BoundSemanticKind.AVERAGE,
        BoundSemanticKind.BEST_EFFORT_TARGET,
        BoundSemanticKind.LOCAL_THRESHOLD,
        BoundSemanticKind.HIDDEN_GRACE_PERIOD,
        BoundSemanticKind.FAVORABLE_SAMPLING_RULE,
    }
)

#: The eleven malformed numeric states of §11 line 316 — **derived** from the enum (everything except
#: ``WELL_FORMED``), so a new malformed member is covered the moment it is declared.
MALFORMED_NUMERIC_STATES: frozenset[NumericInputState] = frozenset(
    NumericInputState
) - {NumericInputState.WELL_FORMED}

#: The three aggregate results that "deny dependent new risk for the affected scope" (§12 line 335) —
#: **derived** from the enum (everything except ``CONFORMING``).
DENYING_AGGREGATE_RESULTS: frozenset[AggregateConformanceResult] = frozenset(
    AggregateConformanceResult
) - {AggregateConformanceResult.CONFORMING}

#: The suppression lifecycle states that are automatically restrictive and unsuppressed (§15 line 365
#: "automatically restrictive on expiry or uncertainty"; §21 line 458).
RESTRICTIVE_SUPPRESSION_STATES: frozenset[SuppressionLifecycleState] = frozenset(
    {SuppressionLifecycleState.EXPIRED, SuppressionLifecycleState.UNKNOWN}
)

#: The **positive whitelist** of lifecycle states under which a suppression is genuinely in force.
#: Today it is the exact complement of :data:`RESTRICTIVE_SUPPRESSION_STATES`, but it is authored as an
#: explicit positive set rather than derived, so a future member nobody has classified is **auto-denied**
#: instead of silently admitted (the #25 RLP MAJOR-1 denylist-leak lesson, applied the same way as
#: :data:`HARD_BOUND_KINDS`). The §7.2 drift property asserts the two sets still partition the enum.
IN_FORCE_SUPPRESSION_STATES: frozenset[SuppressionLifecycleState] = frozenset(
    {SuppressionLifecycleState.REQUESTED, SuppressionLifecycleState.ACTIVE}
)


# ===========================================================================
# manually-transcribed ADR anchors (design #30 §7.2 (b)/(c) — appendices F-M)
# ===========================================================================

#: ADR §9 line 275-286 — the twelve items every Monitor Coverage Manifest entry SHALL identify.
#: Structural labels for the item-level closure; never a numeric bound. 計 12 (過 0 · 不 0).
COVERAGE_CLOSURE_ITEMS: tuple[str, ...] = (
    "EXACT_REQUIREMENT_HAZARD_INVARIANT_GATE_BOUND_OR_OBLIGATION",
    "SCOPE_AND_DEPENDENCY_CLOSURE",
    "UNDERLYING_PREVENTIVE_OR_RESTRICTIVE_OWNER",
    "REQUIRED_TELEMETRY_AND_SOURCE_CONTINUITY",
    "DETERMINISTIC_EVALUATOR_AND_EXPECTED_STATES",
    "DETECTION_TRIGGER_BOUND_MEASUREMENT_START_STOP_AND_UNCERTAINTY",
    "REQUIRED_RESTRICTIVE_ACTION_AND_CONTAINMENT_OWNER",
    "ALERT_DELIVERY_AND_ESCALATION_STAGES",
    "EVIDENCE_AND_INDEPENDENT_REVIEW_OBLIGATIONS",
    "FAILURE_DOMAIN_AND_COMMON_MODE_ANALYSIS",
    "FINAL_EGRESS_OR_RECOVERY_CURRENTNESS_DEPENDENCY",
    "APPROVED_EXCLUSIONS_WITH_PROOF",
)

#: The §9 closure cardinality (12 items, ADR line 275-286). ``過 0 · 不 0``.
COVERAGE_CLOSURE_ITEM_COUNT: int = len(COVERAGE_CLOSURE_ITEMS)

#: ADR §18 line 410-417 — the eight monitoring facts the Broker Egress Gateway includes in the
#: ADR-002-024 Safety Currentness Vector. The *judgement* is cur / egress transaction-owned; this
#: transcription exists only as the not-Phase-1 §6b honesty anchor (STM-EV-009, ``EV-L3+Security``).
FINAL_EGRESS_CURRENTNESS_FACTS: tuple[str, ...] = (
    "POLICY_IDENTITY_GENERATION_AND_DIGEST",
    "CRITICAL_TELEMETRY_AND_COVERAGE_MANIFEST_DIGESTS",
    "CURRENT_MONITOR_GENERATION_AND_FENCED_OWNER_EPOCH",
    "ACTION_SCOPE_COVERAGE_COMPLETENESS",
    "CONFORMANCE_RESULT_AND_ABSENCE_OF_UNRESOLVED_GAPS",
    "SUPPRESSION_STATE_AND_NO_DISABLE_PROOF",
    "RESTRICTIVE_SIGNAL_FENCE_INCIDENT_AND_TRIAL_ABORT_GENERATIONS",
    "SNAPSHOT_AGE_TRUSTWORTHY_TIME_AND_INVALIDATION_STATE",
)

#: ADR §15 line 367-376 — the eight functions that SHALL remain active throughout any suppression.
#: :func:`~tos.stm.predicates.suppression_cannot_suppress_safety` floors a suppression's declared
#: ``preserved_functions`` to at least this set: a suppression may preserve *more* but **never fewer**.
SUPPRESSION_PRESERVED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "TELEMETRY_COLLECTION_AND_CONTINUITY",
        "MONITOR_EVALUATION_AND_VIOLATION_STATE",
        "MONITORING_GAP_CREATION",
        "RESTRICTIVE_SIGNALING_AND_LOCAL_DENY_LATCHING",
        "INCIDENT_SIGNAL_HANDOFF",
        "EVIDENCE_CAPTURE_AND_AUDIT",
        "ESCALATION_ON_SUPPRESSION_FAILURE_OR_EXPIRY",
        "FINAL_EGRESS_CURRENTNESS_AND_DENIAL",
    }
)

#: ADR §21 line 451-462 — the twelve partition / backpressure / failure rows and their mandatory
#: results. A transcription anchor only: the runtime behaviour is L3 (design #30 §6b). 計 12.
PARTITION_FAILURE_MODES: tuple[str, ...] = (
    "TELEMETRY_SOURCE_OR_CONTINUITY_LOST",
    "COLLECTOR_PARSER_EVALUATOR_OR_REGISTRY_UNAVAILABLE",
    "MONITOR_OWNER_OR_GENERATION_CONFLICT",
    "MONITORING_PLANE_PARTITIONED_WHILE_BROKER_EGRESS_REACHABLE",
    "QUEUE_OVERFLOW_OR_BACKPRESSURE",
    "ALERT_DELIVERY_OR_ESCALATION_UNPROVEN",
    "COMMON_MODE_INDEPENDENCE_CLAIM_FAILS",
    "SUPPRESSION_STATE_MISSING_STALE_OR_EXPIRED",
    "TIME_CONFIDENCE_OR_RECEIPT_AGE_PROOF_LOST",
    "EVIDENCE_PATH_UNAVAILABLE",
    "DASHBOARD_OR_PAGING_SYSTEM_COMPROMISED",
    "RECOVERY_OR_BACKLOG_DRAIN_COMPLETES",
)

#: ADR §8 line 253-265 — the twelve field groups the Critical Telemetry Manifest SHALL bind. Carried
#: by :class:`~tos.stm.state.CriticalTelemetryIdentity`. 計 12 (過 0 · 不 0).
CRITICAL_TELEMETRY_BINDING_GROUPS: tuple[str, ...] = (
    "RELEASE_LINEAGE_ADMISSION_AND_FENCING",
    "POST_TRADE_FINALITY_OBLIGATION_AND_CURRENTNESS",
    "CANONICAL_TELEMETRY_AND_SEMANTIC_IDENTITY",
    "OWNER_AND_PUBLISHER_IDENTITY_AND_EPOCH",
    "EXACT_ENVIRONMENTS_CELLS_DOMAINS_ACCOUNTS_BROKERS_VENUES_INSTRUMENTS_SCOPES",
    "VALUE_TYPE_UNITS_SCALE_SIGN_CARDINALITY_STATES_AND_MISSING_SEMANTICS",
    "SOURCE_IDENTITIES_CONTINUITY_SEQUENCE_SCHEMA_AND_LINEAGE",
    "TRUSTWORTHY_TIME_EVENT_OBSERVATION_RECEIPT_AGE_SKEW_AND_UNCERTAINTY",
    "EXPECTED_CADENCE_COMPLETENESS_AGGREGATION_SAMPLING_AND_LOSS",
    "APPROVED_DERIVATION_AND_INVARIANT_EVALUATOR_DIGESTS",
    "DEPENDENCY_CLOSURE_CONSUMERS_RESTRICTIVE_RESPONSE_AND_EVIDENCE_CLASS",
    "FAILURE_DOMAINS_COMMON_MODES_ACCESS_RETENTION_AND_SECURITY",
)

#: ADR §14 line 355 — the seventeen shared dependencies that are a **disclosed common mode**. The
#: :class:`~tos.stm.state.CommonModeDisclosure` field stays an open ``frozenset[str]`` because §14 line
#: 357 keeps "remaining common mode ... recorded as residual risk" open-ended; this closed transcription
#: exists as the honesty anchor only. 計 17 (過 0 · 不 0).
SHARED_DEPENDENCY_ANCHOR: tuple[str, ...] = (
    "SOURCE",
    "COLLECTOR",
    "EXPORTER",
    "PARSER",
    "SCHEMA_REGISTRY",
    "LIBRARY",
    "TIME_SOURCE",
    "MESSAGE_BUS",
    "DATASTORE",
    "NETWORK",
    "REGION",
    "CREDENTIAL",
    "ADMINISTRATOR",
    "CI_PIPELINE",
    "DEPLOYMENT",
    "NOTIFICATION_PROVIDER",
    "POLICY_OWNER",
)

#: ADR §1 line 25 (twelve verbs) + STM-INV-001 line 159 (``create capacity``) + §7 line 236 (``classify
#: protective action``) — the fourteen things a monitoring artifact does **not** do, in the declaration
#: order of :class:`~tos.stm._base.AllFalseMonitoringAuthority`. The §7.2 (c) ADR-enumeration-closure
#: property asserts a 1:1 correspondence with that model's fourteen fields. 計 14 (過 0 · 不 0).
ALL_FALSE_AUTHORITY_VERBS: tuple[str, ...] = (
    "CREATE_CAPACITY",
    "APPROVE_AN_ACTION",
    "CREATE_HEADROOM",
    "MARK_AN_RFC_REQUIREMENT_PASS",
    "SATISFY_PREVENTIVE_CONTROL",
    "ESTABLISH_BROKER_FINALITY",
    "ACTIVATE_CONFIGURATION",
    "ISSUE_AUTHORITY",
    "PERMIT_TRANSMISSION",
    "CLOSE_AN_INCIDENT",
    "ESTABLISH_RECOVERY_READINESS",
    "RESTORE_SCOPE",
    "RE_ARM",
    "CLASSIFY_PROTECTIVE_ACTION",
)

#: ADR §5.11 line 151 — the six things a Monitoring Suppression "SHALL NOT disable ... for a Critical
#: condition", in the declaration order of :class:`~tos.stm.state.MonitoringSuppression`'s six
#: negative-polarity ``disables_*`` fields. 計 6 (過 0 · 不 0).
MONITORING_SUPPRESSION_PROHIBITIONS: tuple[str, ...] = (
    "SOURCE_COLLECTION",
    "INVARIANT_EVALUATION",
    "RESTRICTIVE_SIGNALING",
    "EVIDENCE",
    "GENERATION_ADVANCEMENT",
    "FINAL_EGRESS_DENIAL",
)

#: ADR §17 line 402 — "No monitor or alert may downgrade an existing fence or incident, select a
#: narrower scope, clear a local latch, or publish ``NO_INCIDENT``", in the declaration order of
#: :class:`~tos.stm.state.RestrictiveMonitoringSignal`'s four negative-polarity fields. 計 4.
RESTRICTIVE_SIGNAL_PROHIBITIONS: tuple[str, ...] = (
    "DOWNGRADE_EXISTING_FENCE_OR_INCIDENT",
    "SELECT_NARROWER_SCOPE",
    "CLEAR_LOCAL_LATCH",
    "PUBLISH_NO_INCIDENT",
)
