"""Restricted-live / promotion vocabulary — the RLP StrEnums (design #25 §2.2).

Spec terms = code terms (design #25 §2.2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-025 (§9 plan result, §5.9/§18 promotion result, §14 run state, §17
coverage verdict, §9 line 263 scope catalogue, §16 evidence element catalogue).

**Truthy-sentinel structural seal (design #25 §2.2/§4.2 — #13/#14 M1 adopted from the start).**
``PlanResult`` (INELIGIBLE / HOLD / ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION), ``PromotionResult``
(DENY / HOLD / ELIGIBLE_TO_REQUEST_NEW_SCOPE), ``TrialRunState`` (the 7-state machine), and
``CoverageVerdict`` (COVERED / UNCOVERED / UNKNOWN) are non-empty ``StrEnum`` strings, so
``if result:`` / ``bool(state)`` would read a **denial / non-permissive** member (``INELIGIBLE`` /
``HOLD`` / ``DENY`` / ``ABORTING`` / ``TERMINATED`` / ``UNCOVERED`` / ``UNKNOWN``) as **truthy** — a
catastrophic silent fail-open that reads a *rejection* / *terminal* state as a *go* (ADR §9 line 275
"The last result is **non-authorizing**"; §14 line 378 "``ABORTING`` ... are **non-permissive**").
Each subclasses :class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises**
``TypeError``, making them *truthy-untestable*. The mandated consume gates are the explicit positive-
identity comparison (``result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` /
``result is PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE`` / ``verdict is CoverageVerdict.COVERED``)
— everything else is denial. Isomorphic to the iap ``ApprovalResult`` seal
(``iap/vocabulary.py:79``), the cur ``ProofResult`` seal, and the egress seal; authored
**locally-fresh** here (sibling edge 0 — no iap / cur / egress import, design #25 §3.3).

``ScopeDimension`` and ``EvidenceClass`` are **plain, closed** ``StrEnum``s (ADR §9 line 263 scope
catalogue / §16 evidence element catalogue): structural identifier tokens consumed by set
membership / subset checks (:func:`~tos.rlp.predicates.plan_scope_exact_and_complete` /
:func:`~tos.rlp.predicates.evidence_package_complete`), never gate results read with ``if key:``, so
they do not need the truthy seal. Each is a **structural identifier**, never a threshold / bound —
hardcoding it is **not** a numeric hardcode (design #25 §2.2/§8; the cur ``DimensionKey`` / ioc / spg
field-enumeration precedent). They are **manually-transcribed regression anchors** (design #25 §0.4h):
the §7.2 anchor-drift property asserts the enum equals the ADR-§9 / ADR-§16 reference set so a drift
is caught immediately (cur v1.1 §7.2 enum-drift precedent).

This module names **no** concrete broker (broker-agnostic — project memory ``tos-spec-broker-
agnostic``; design #25 §0.2) and hardcodes **no** numeric floor / size / duration / threshold (ADR
§8): every bound is an injected Profile-INSTANCE value (design #25 §8). An enum member is a
structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #25 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "PlanResult",
    "PromotionResult",
    "TrialRunState",
    "CoverageVerdict",
    "ScopeDimension",
    "EvidenceClass",
    "MANDATED_SCOPE_FLOOR",
    "MANDATED_EVIDENCE_FLOOR",
    "NEGATIVE_RESULT_CLASSES",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #25 §2.2/§4.2).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(state)`` would read a
    denial / non-permissive member (``INELIGIBLE`` / ``HOLD`` / ``DENY`` / ``ABORTING`` /
    ``TERMINATED`` / ``UNCOVERED`` / ``UNKNOWN``) as truthy — a catastrophic silent fail-open that
    reads a rejection / terminal state as a go. :meth:`__bool__` therefore raises ``TypeError`` on
    every member, so the misuse surfaces as a loud runtime error rather than a silent pass. Consumers
    MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to the iap
    ``ApprovalResult`` / cur ``ProofResult`` / egress seals; authored **locally-fresh** here (sibling
    edge 0, no iap / cur / egress import — design #25 §3.3). ``is`` identity, ``.value``, hashing, set
    membership, and ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #25 §2.2/§4.2).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION``);
                a bare ``if result:`` / ``bool(result)`` would fail open on the truthy denial /
                non-permissive strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is "
            "PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`; `result is "
            "PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE`; `verdict is "
            "CoverageVerdict.COVERED`) per the truthy-sentinel seal (design #25 §2.2/§4.2). The "
            "denial / non-permissive members are non-empty strings and a bare `if result:` would "
            "fail open — reading a rejection or a terminal state as a go."
        )


class PlanResult(_NonTruthyStrEnum):
    """The Exact Trial Plan result (ADR-002-025 §9 line 275, non-truthy — critical seal).

    §9 line 275 verbatim: "The plan result is ``INELIGIBLE``, ``HOLD``, or
    ``ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION``. The last result is **non-authorizing**."
    **Truthy-untestable** (``__bool__`` raises): ``INELIGIBLE`` / ``HOLD`` are non-empty strings, so
    ``if result:`` would read a *denial* as an *eligibility* — the catastrophic fail-open this seal
    blocks. The mandated consume gate is
    ``result is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION``; every other value is denial.
    ``ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`` itself grants **no** authority (§9 line 275
    "non-authorizing"; all-false :class:`~tos.rlp._base.AllFalseTrialAuthority`, §6.4) — it is only
    eligibility to *request* a Live Authorization from liveauth (§0.4g).
    """

    INELIGIBLE = "INELIGIBLE"
    HOLD = "HOLD"
    ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION = "ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION"


class PromotionResult(_NonTruthyStrEnum):
    """The Production Scope Promotion decision result (ADR-002-025 §5.9/§18, non-truthy).

    §5.9 verbatim: "A single-use, **non-authorizing** independent decision of ``DENY``, ``HOLD``, or
    ``ELIGIBLE_TO_REQUEST_NEW_SCOPE``." §18 line 464: "Only ``ELIGIBLE_TO_REQUEST_NEW_SCOPE`` may be
    consumed, once." **Truthy-untestable** (``__bool__`` raises): ``DENY`` / ``HOLD`` are non-empty
    strings ⇒ ``if result:`` misuse is a fail-open. The mandated consume gate is
    ``result is PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE`` plus single-use. It is **not**
    approval of an order or production permission (§18 line 464; all-false, §6.4).
    """

    DENY = "DENY"
    HOLD = "HOLD"
    ELIGIBLE_TO_REQUEST_NEW_SCOPE = "ELIGIBLE_TO_REQUEST_NEW_SCOPE"


class TrialRunState(_NonTruthyStrEnum):
    """The Trial Run state machine (ADR-002-025 §14, non-truthy — 7-state).

    §14 line 374 "``RUNNING`` requires current Live Authorization and **does not itself grant
    transmission permission**"; line 378 "``ABORTING``, ``TERMINATED``, ``COMPLETED_PENDING_REVIEW``,
    and ``INVALIDATED`` are **non-permissive**. No terminal state returns to ``RUNNING``."
    **Truthy-untestable** (``__bool__`` raises): a non-permissive state is a non-empty string so
    ``if state:`` would read a terminal / aborting state as a truthy "go" — a fail-open. **No** state
    grants transmission authority (all-false, §6.4): the state is a lifecycle marker, not a permit.
    """

    NOT_STARTED = "NOT_STARTED"
    AUTHORIZED_NOT_STARTED = "AUTHORIZED_NOT_STARTED"
    RUNNING = "RUNNING"
    ABORTING = "ABORTING"
    TERMINATED = "TERMINATED"
    COMPLETED_PENDING_REVIEW = "COMPLETED_PENDING_REVIEW"
    INVALIDATED = "INVALIDATED"


class CoverageVerdict(_NonTruthyStrEnum):
    """The coverage verdict (ADR-002-025 §17, non-truthy).

    §5.8 "Unexercised or ambiguously observed behavior is **uncovered**"; §17 line 444 "**Unknown
    equivalence is non-equivalence**." **Truthy-untestable** (``__bool__`` raises): ``UNCOVERED`` /
    ``UNKNOWN`` are non-empty strings ⇒ ``if verdict:`` misuse is a fail-open. The mandated consume
    gate is ``verdict is CoverageVerdict.COVERED``; every other value is denial.
    """

    COVERED = "COVERED"
    UNCOVERED = "UNCOVERED"
    UNKNOWN = "UNKNOWN"


class ScopeDimension(StrEnum):
    """The Exact Trial Plan scope catalogue (ADR-002-025 §9 line 263, closed structural token).

    §9 line 263 enumerates the exact scope dimensions a pre-registered trial plan must bind
    concretely (no wildcard / inferred / patched / unioned / stale / conflicting). A **plain, closed**
    ``StrEnum`` structural identifier consumed by set membership / subset checks
    (:func:`~tos.rlp.predicates.plan_scope_exact_and_complete`), never a gate result read with
    ``if key:``, so it is deliberately **not** truthy-sealed. It is a **structural dimension
    identifier**, never a numeric threshold / bound — enumerating it is **not** a numeric hardcode
    (design #25 §2.2/§8; the cur ``DimensionKey`` / ioc / spg field-enumeration precedent).

    Each member's lowercased name is the matching :class:`~tos.rlp.state.TrialScope` field
    (``ENVIRONMENT`` ↔ ``environment``), a correspondence the §7.2 anchor-drift property asserts so a
    scope field can never drift from the catalogue. This set is a **manually-transcribed regression
    anchor** of ADR §9 line 263 (design #25 §0.4h) — not a derivation.
    """

    ENVIRONMENT = "ENVIRONMENT"
    SAFETY_CELL = "SAFETY_CELL"
    CAPACITY_DOMAIN = "CAPACITY_DOMAIN"
    PORTFOLIO = "PORTFOLIO"
    ACCOUNT = "ACCOUNT"
    BROKER = "BROKER"
    VENUE = "VENUE"
    INSTRUMENT = "INSTRUMENT"
    STRATEGY = "STRATEGY"
    ACTION_CLASS = "ACTION_CLASS"
    ORDER_SHAPE = "ORDER_SHAPE"
    SOFTWARE_RELEASE = "SOFTWARE_RELEASE"
    CONFIGURATION = "CONFIGURATION"
    IDENTITY = "IDENTITY"
    CREDENTIAL = "CREDENTIAL"
    ROUTE = "ROUTE"
    SESSION = "SESSION"
    TIME_INTERVAL = "TIME_INTERVAL"
    FAILURE_DOMAIN = "FAILURE_DOMAIN"


class EvidenceClass(StrEnum):
    """The Trial Evidence Package element catalogue (ADR-002-025 §16 line 417-424, closed token).

    §16 line 417-424 enumerates the element classes a complete trial evidence package must carry: the
    event classes (proposed / denied / committed / transmitted / ... / abort / recovery), the
    capacity / flow transitions, the coverage / **negative-result** classes (negative / failed /
    inconclusive / aborted / conflicting / superseded — the retention gate, §16 line 426), the broker
    evidence classes, and the generation / review classes. A **plain, closed** ``StrEnum`` structural
    identifier consumed by set membership / subset checks
    (:func:`~tos.rlp.predicates.evidence_package_complete`), never a gate result read with
    ``if class:`` — deliberately **not** truthy-sealed. A structural identifier, never a numeric
    bound.

    **Deliberate manifest scope (honesty — §8 / §16).** This catalogue is the *element-class
    manifest* axis only. Two §16 concerns are intentionally **outside** it: (a) the §16 line 421
    **measured bounds** (detection / containment / abort / fence / evidence / reconciliation /
    recovery) are numeric Profile-INSTANCE values (§8) — they are not manifest element classes and so
    are excluded from the manifest-completeness axis (a null Phase-1 bound is not a missing element
    class); (b) the §16 line 440 **fault / boundary-condition** taxonomy (nominal / boundary /
    missing / stale / crash / restart / partition / broker-rejection / partial-fill / conflict) is
    tracked per-claim by the :class:`~tos.rlp.state.CoverageClaim` ``exercised_conditions`` /
    ``unexercised_conditions`` condition catalogue, not as a manifest element class. This class
    enumerates only the element classes a complete package must *carry*. This set is a
    **manually-transcribed regression anchor** of ADR §16 line 417-424 (design #25 §0.4h); the §7.2
    anchor-drift property asserts it.
    """

    # event classes (§16 line 417)
    PROPOSED = "PROPOSED"
    DENIED = "DENIED"
    COMMITTED = "COMMITTED"
    TRANSMITTED = "TRANSMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    CORRECTED = "CORRECTED"
    EXTERNAL = "EXTERNAL"
    PROTECTIVE = "PROTECTIVE"
    ABORT = "ABORT"
    RECOVERY = "RECOVERY"
    # capacity / flow (§16 line 418)
    RCL_TRANSITIONS = "RCL_TRANSITIONS"
    ACTION_FLOW_TRANSITIONS = "ACTION_FLOW_TRANSITIONS"
    POTENTIALLY_LIVE_INTERVALS = "POTENTIALLY_LIVE_INTERVALS"
    FINAL_QUANTITY_EVIDENCE = "FINAL_QUANTITY_EVIDENCE"
    # coverage / negative (§16 line 419-422)
    COVERAGE_CLAIMS = "COVERAGE_CLAIMS"
    UNEXERCISED_CONDITIONS = "UNEXERCISED_CONDITIONS"
    DEVIATIONS = "DEVIATIONS"
    COMMON_MODES = "COMMON_MODES"
    NEGATIVE_RESULTS = "NEGATIVE_RESULTS"
    FAILED_RESULTS = "FAILED_RESULTS"
    INCONCLUSIVE_RESULTS = "INCONCLUSIVE_RESULTS"
    ABORTED_RESULTS = "ABORTED_RESULTS"
    CONFLICTING_RESULTS = "CONFLICTING_RESULTS"
    SUPERSEDED_RESULTS = "SUPERSEDED_RESULTS"
    # broker evidence (§16 line 420)
    RAW_BROKER_EVIDENCE = "RAW_BROKER_EVIDENCE"
    NORMALIZED_BROKER_EVIDENCE = "NORMALIZED_BROKER_EVIDENCE"
    SOURCE_CONTINUITY = "SOURCE_CONTINUITY"
    GAPS = "GAPS"
    # generations / review (§16 line 423-424)
    SOFTWARE_GENERATION = "SOFTWARE_GENERATION"
    CONFIGURATION_GENERATION = "CONFIGURATION_GENERATION"
    BROKER_PROFILE = "BROKER_PROFILE"
    IDENTITIES = "IDENTITIES"
    REVIEWER_DECISIONS = "REVIEWER_DECISIONS"
    INDEPENDENT_REPRODUCTION = "INDEPENDENT_REPRODUCTION"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"


#: The §16 line 422 negative-result classes whose retention is the promotion gate (§5.2 / RLP-INV-009
#: "Failed, aborted, conflicting, incomplete, and inconclusive trials remain retained"). §16 line 422
#: enumerates **six** verbatim: "negative, failed, inconclusive, aborted, superseded, and conflicting
#: results" — ``SUPERSEDED_RESULTS`` is retained alongside the others (a superseded run is negative
#: evidence, not erasable). A complete package must carry **all** of these — a passing subset cannot
#: erase them (§16 line 426).
NEGATIVE_RESULT_CLASSES: frozenset[EvidenceClass] = frozenset(
    {
        EvidenceClass.NEGATIVE_RESULTS,
        EvidenceClass.FAILED_RESULTS,
        EvidenceClass.INCONCLUSIVE_RESULTS,
        EvidenceClass.ABORTED_RESULTS,
        EvidenceClass.SUPERSEDED_RESULTS,
        EvidenceClass.CONFLICTING_RESULTS,
    }
)

#: The §9 mandated scope floor: **every** ``ScopeDimension`` member.
#: :func:`~tos.rlp.predicates.plan_scope_exact_and_complete` floors its ``mandated_scope`` argument to
#: at least this set — a caller may require *more* but **never fewer** (design #25 §5.1; the cur
#: ``MANDATED_DIMENSION_FLOOR`` v1.1 MINOR-1 precedent). Derived from the enum so it can never drift
#: below the catalogue (the §7.2 anchor-drift property asserts the derivation equals the ADR §9
#: line 263 reference set).
MANDATED_SCOPE_FLOOR: frozenset[ScopeDimension] = frozenset(ScopeDimension)

#: The §16 mandated evidence floor: **every** ``EvidenceClass`` member (a complete package proves
#: what occurred across every element class; §16 line 428). :func:`~tos.rlp.predicates.evidence_
#: package_complete` floors its ``mandated_classes`` argument to at least this set (design #25 §5.2).
MANDATED_EVIDENCE_FLOOR: frozenset[EvidenceClass] = frozenset(EvidenceClass)
