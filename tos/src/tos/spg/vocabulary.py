"""Safety-Profile-Governance vocabulary — the governance-CLASS StrEnums (design #12 §2.2).

Spec terms = code terms (design #12 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-014 (§12.1 envelope lifecycle, §12.2 profile lifecycle, §5.9/§11
change direction, §5.3 bundle members, §11/§20 validation reasons, §13 activation verdict).
These are the **safety-configuration governance** axis; they are a distinct coordinate
system from the brokercap ``ProfileVersion`` (broker-capability axis), the rcl generation
(capacity axis), and the time ``safety_profile_version`` (time-snapshot axis). Token overlap
(e.g. "profile version") is intentional (the ADR uses the same word on several axes), so
coordinate non-collapse rests on **distinct types + non-import** (design #12 §4.4): spg
imports none of those sibling axes, so a value from one can never be coerced onto another.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #12 §0.1). The numeric limits / validity intervals /
approver identities of any one deployment belong to a non-normative Safety Profile /
Verification Profile INSTANCE (ADR §4 non-scope / §26 item 12), not here.

Pure module: stdlib only; no ``shared.*`` (design #12 §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class EnvelopeState(StrEnum):
    """The 9 Hard-Safety-Envelope lifecycle states (ADR-002-014 §12.1 line 325-332 verbatim).

    Verbatim from ADR §12.1::

        DRAFT
        VALIDATED
        APPROVED
        STAGED
        ACTIVE
        REJECTED         ({DRAFT, VALIDATED, APPROVED, STAGED} -> REJECTED)
        RESTRICTED       (ACTIVE -> RESTRICTED)
        SUPERSEDED       (ACTIVE -> SUPERSEDED)
        REVOKED          (ACTIVE -> REVOKED)

    §12.1 line 334 verbatim: "``SUPERSEDED``, ``REVOKED``, or restored generations never
    return to ``ACTIVE``." The terminal states have no arrow back to ``ACTIVE`` in
    ``_ENVELOPE_TRANSITIONS`` (non-revival; the liveauth
    ``_LIVE_AUTHORIZATION_TRANSITIONS`` precedent).
    """

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    STAGED = "STAGED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    RESTRICTED = "RESTRICTED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class ProfileState(StrEnum):
    """The 11 Runtime-Safety-Profile lifecycle states (ADR-002-014 §12.2 line 338-346 verbatim).

    Verbatim from ADR §12.2::

        DRAFT
        VALIDATED
        APPROVED
        STAGED
        ACTIVATION_READY
        ACTIVE
        REJECTED         ({DRAFT, VALIDATED, APPROVED, STAGED, ACTIVATION_READY} -> REJECTED)
        SUSPENDED        (ACTIVE -> SUSPENDED)
        SUPERSEDED       (ACTIVE -> SUPERSEDED)
        REVOKED          (ACTIVE -> REVOKED)
        EXPIRED          (ACTIVE -> EXPIRED)

    §12.2 line 348 verbatim: "No transition from ``SUSPENDED``, ``SUPERSEDED``, ``REVOKED``,
    or ``EXPIRED`` returns the same Profile Generation to ``ACTIVE``. Reuse of identical
    content still requires a new generation, current validation, current approvals,
    activation, and re-arm." Non-revival + no-content-reuse — realized by the absence of
    any terminal -> ``ACTIVE`` arrow in ``_PROFILE_TRANSITIONS``.
    """

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    STAGED = "STAGED"
    ACTIVATION_READY = "ACTIVATION_READY"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ChangeDirection(StrEnum):
    """The 3 change directions (ADR-002-014 §5.9 line 141-145 / §11 line 312 / §14; v1.1 MINOR-1).

    ::

        RESTRICTIVE            deny / narrow only on every credible dimension (§14 line 393)
        PERMISSIVE             at least one credible interpretation enlarges (§5.9 line 143)
        AUTHORITY_INCREASING   permits a previously denied / more-constrained scope, OR the
                               direction cannot be ordered conservatively / is unproven
                               (§5.9 line 143/145; §11 line 317)

    §5.9 line 145 verbatim: "**When monotonic direction cannot be proven, the change is
    authority increasing.**" §11 line 317 verbatim: "If one dimension cannot be ordered
    conservatively, **the change is authority increasing** and the scope remains non-live
    until independently resolved."

    There is deliberately **no** ``UNORDERABLE`` enum value (v1.1 MINOR-1): unorderable /
    unproven folds into ``AUTHORITY_INCREASING`` (more faithful to §11:317 "unorderable IS
    authority increasing"), and the unorderable *fact* rides in the reason set as
    :attr:`ValidationReason.UNORDERABLE_DIRECTION`. Removing the enum value seals the
    fail-open adjacency where a consumer's ``direction == AUTHORITY_INCREASING`` check would
    be bypassed by a separate ``UNORDERABLE`` value (design #12 §2.2(3)/§5.5).
    """

    RESTRICTIVE = "RESTRICTIVE"
    PERMISSIVE = "PERMISSIVE"
    AUTHORITY_INCREASING = "AUTHORITY_INCREASING"


class ValidationReason(StrEnum):
    """The §11/§20 semantic-validation reject reasons (ADR-002-014 §11/§20; design #12 §2.2(5)).

    The elements of a :class:`~tos.spg.records.SemanticValidationResult` reason set (the rich
    verdict §11 line 315 "deterministic result **and reason set**" requires; design #12 §5.2).
    Each names one class of §11 step / §20 failure mode:

    * ``UNIT_OR_MULTIPLIER_MISMATCH``       — §11 step 3 / §20 line 505. Carries the whole
      §11 step 3 *comparability* axis: unit / multiplier / sign **and** precision /
      rounding / boundary inclusion (``predicates._UNIT_METADATA_KEYS``), because the
      ``units_compatible`` seam bool that liveauth ``atomic_activation_ok`` consumes is
      keyed on exactly this reason — routing a precision / rounding / boundary mismatch
      to a different reason would leave that seam ``True`` (EV-L2 pilot design §5 H-2/H-3).
    * ``SIGN_PRECISION_ROUNDING_DEFECT``    — §11 step 3. Reserved for a *value-level*
      sign / precision / rounding defect from a future non-model-sourced input; the
      metadata-**comparability** mismatch between an envelope and profile dimension is
      reported as ``UNIT_OR_MULTIPLIER_MISMATCH`` above (no reason is minted or retired —
      the ratified verbatim set is unchanged).
    * ``OVERFLOW_UNDERFLOW_NAN_INFINITY``   — §11 step 3 (a non-finite Decimal; enforced at
      construction by the explicit ``allow_inf_nan=False`` pin tos owns on
      ``tos.canonical.FrozenModel`` — EV-L2 pilot design §5 H-1, §5.2 deviation)
    * ``CROSS_FIELD_CONSTRAINT_VIOLATION``  — §11 step 5
    * ``EXCEEDS_ENVELOPE``                  — §11 step 6 / §9 (SPG-INV-001)
    * ``UNKNOWN_OR_DUPLICATE_FIELD``        — §11 step 12 / §20 line 504
    * ``SCHEMA_INCOMPLETE_OR_DOWNGRADE``    — §11 step 2 / §24 SPG-AC-003
    * ``FLOATING_REFERENCE``                — §7 line 219 (an unresolved / floating ref)
    * ``UNORDERABLE_DIRECTION``             — §11 step 11 / line 317 (folds to AUTHORITY_INCREASING)
    * ``CANONICAL_DIGEST_IRREPRODUCIBLE``   — §7 line 228 / §11 step 2
    """

    UNIT_OR_MULTIPLIER_MISMATCH = "UNIT_OR_MULTIPLIER_MISMATCH"
    SIGN_PRECISION_ROUNDING_DEFECT = "SIGN_PRECISION_ROUNDING_DEFECT"
    OVERFLOW_UNDERFLOW_NAN_INFINITY = "OVERFLOW_UNDERFLOW_NAN_INFINITY"
    CROSS_FIELD_CONSTRAINT_VIOLATION = "CROSS_FIELD_CONSTRAINT_VIOLATION"
    EXCEEDS_ENVELOPE = "EXCEEDS_ENVELOPE"
    UNKNOWN_OR_DUPLICATE_FIELD = "UNKNOWN_OR_DUPLICATE_FIELD"
    SCHEMA_INCOMPLETE_OR_DOWNGRADE = "SCHEMA_INCOMPLETE_OR_DOWNGRADE"
    FLOATING_REFERENCE = "FLOATING_REFERENCE"
    UNORDERABLE_DIRECTION = "UNORDERABLE_DIRECTION"
    CANONICAL_DIGEST_IRREPRODUCIBLE = "CANONICAL_DIGEST_IRREPRODUCIBLE"


class ActivationVerdict(StrEnum):
    """The local 3-token activation verdict (ADR-002-014 §13 realization; design #12 §2.2(6)).

    ::

        COMMITTABLE    every §13 positive condition holds — atomic single-generation, no
                       mixed versions, units compatible, envelope-bounded
        DENIED         mixed generation / partial / incompatible / stale-base / unverifiable
                       (§13 line 385 / §15)
        DEFERRED       staging / attestation collection incomplete — runtime quorum-commit
                       pending; not-live (§13 line 383)

    There is deliberately **no** "assume-committable" construction path: the predicate
    returns ``COMMITTABLE`` only from positive proof, everything else is restrictive (design
    #12 §4.1 — the structural seal against the #6 fail-open REJECT lesson; brokercap
    ``Admissibility`` isomorph). This is the spg-internal SPG-EV-004 property verdict; the
    liveauth seam consumes the four individual bools it folds (design #12 §5.3 dual-layer).
    """

    COMMITTABLE = "COMMITTABLE"
    DENIED = "DENIED"
    DEFERRED = "DEFERRED"


class BundleMemberKind(StrEnum):
    """The 29 top-level Safety-Configuration-Bundle member kinds (ADR-002-014 §5.3 line 119).

    v1.1 MAJOR-3 (선택지 b): ADR §5.3 line 119 lists 36 items and calls them a "complete
    closed set", but the 7 sub-generation / graph / attestation / referenced-object items
    (Release Generation, compatibility graph, runtime-attestation requirements, Post-Trade
    Obligation Generation, obligation/finality compatibility, software compatibility
    manifests, referenced policy objects) are owned by ADR-002-029/030 and **deferred** to
    Phase-0 bundle-binding (§27 item 18-19 / §9.2 item 14). Phase-1 models the **29
    top-level named artifacts** here; the deferred 7 ride as Phase-0-injected
    :class:`~tos.spg.records.BundleMemberRef` (design #12 §2.2(4) two-column table — 29
    included + 7 deferred = 36, so the line-119 enumeration is exhaustively classified and
    an asymmetric omission is structurally impossible, unlike the v1.0 prose列).

    ``bundle_complete`` (design #12 §6.4) checks the present / resolved / immutable status
    of the required members; an **empty** required set is treated as **all** of these (∅ =
    all-needed, most-restrictive — never a vacuous complete; design #12 §4.1).
    """

    HARD_SAFETY_ENVELOPE = "HARD_SAFETY_ENVELOPE"
    RUNTIME_SAFETY_PROFILE = "RUNTIME_SAFETY_PROFILE"
    BROKER_CAPABILITY_PROFILE = "BROKER_CAPABILITY_PROFILE"
    VERIFICATION_PROFILE = "VERIFICATION_PROFILE"
    RECOVERY_BARRIER_POLICY = "RECOVERY_BARRIER_POLICY"
    CRITICAL_INPUT_POLICY = "CRITICAL_INPUT_POLICY"
    VENUE_CONSTRAINT_POLICY = "VENUE_CONSTRAINT_POLICY"
    ORDER_CONSTRUCTION_POLICY = "ORDER_CONSTRUCTION_POLICY"
    AGGREGATE_RISK_POLICY = "AGGREGATE_RISK_POLICY"
    ADVERSE_SCENARIO_SET = "ADVERSE_SCENARIO_SET"
    ACTION_FLOW_POLICY = "ACTION_FLOW_POLICY"
    TRADING_APPROVAL_POLICY = "TRADING_APPROVAL_POLICY"
    CURRENTNESS_POLICY = "CURRENTNESS_POLICY"
    RESTRICTED_LIVE_TRIAL_POLICY = "RESTRICTED_LIVE_TRIAL_POLICY"
    SAFETY_DEVIATION_POLICY = "SAFETY_DEVIATION_POLICY"
    ACTIVE_DEVIATION_SET = "ACTIVE_DEVIATION_SET"
    SAFETY_INCIDENT_POLICY = "SAFETY_INCIDENT_POLICY"
    ACTIVE_SAFETY_INCIDENT_SET = "ACTIVE_SAFETY_INCIDENT_SET"
    SAFETY_MONITORING_POLICY = "SAFETY_MONITORING_POLICY"
    CRITICAL_TELEMETRY_MANIFEST = "CRITICAL_TELEMETRY_MANIFEST"
    MONITOR_COVERAGE_MANIFEST = "MONITOR_COVERAGE_MANIFEST"
    SOFTWARE_RELEASE_POLICY = "SOFTWARE_RELEASE_POLICY"
    ADMITTED_RELEASE_SET = "ADMITTED_RELEASE_SET"
    RELEASE_ARTIFACT_MANIFEST = "RELEASE_ARTIFACT_MANIFEST"
    POST_TRADE_FINALITY_POLICY = "POST_TRADE_FINALITY_POLICY"
    ACTIVE_ECONOMIC_OBLIGATION_SET = "ACTIVE_ECONOMIC_OBLIGATION_SET"
    STATEMENT_COVERAGE_MANIFEST = "STATEMENT_COVERAGE_MANIFEST"
    FAILURE_DOMAIN_ALLOCATION_MATRIX = "FAILURE_DOMAIN_ALLOCATION_MATRIX"
    TIME_CALENDAR_DATA = "TIME_CALENDAR_DATA"


#: The 29 modeled Phase-1 bundle members (design #12 §2.2(4)). An **empty** required set is
#: treated as this whole set (∅ = all-needed, most-restrictive — never a vacuous complete;
#: design #12 §4.1/§6.4). The 7 deferred sub-generation refs are Phase-0-injected.
MODELED_BUNDLE_MEMBERS: frozenset[BundleMemberKind] = frozenset(BundleMemberKind)


class BreakGlassAction(StrEnum):
    """The break-glass action tokens (ADR-002-014 §8 line 251 realization; design #12 §6.2).

    §8 line 251 verbatim: break-glass authority may **only** HALT or apply a proven
    Restrictive Override — it may **not** expand the envelope, expand a profile, waive
    semantic validation, activate a generation, or re-arm. ``HALT`` / ``RESTRICTIVE_OVERRIDE``
    are the two confined actions; every other token is prohibited (``break_glass_confined``
    returns ``False``).
    """

    HALT = "HALT"
    RESTRICTIVE_OVERRIDE = "RESTRICTIVE_OVERRIDE"
    EXPAND_ENVELOPE = "EXPAND_ENVELOPE"
    EXPAND_PROFILE = "EXPAND_PROFILE"
    WAIVE_VALIDATION = "WAIVE_VALIDATION"
    ACTIVATE_GENERATION = "ACTIVATE_GENERATION"
    RE_ARM = "RE_ARM"


#: The two break-glass actions §8 line 251 confines authority to (HALT or proven Restrictive
#: Override). Any other action is prohibited (design #12 §6.2). Not a permissive default —
#: the membership set is exhaustive and every non-member fails closed.
BREAK_GLASS_ALLOWED_ACTIONS: frozenset[BreakGlassAction] = frozenset(
    {BreakGlassAction.HALT, BreakGlassAction.RESTRICTIVE_OVERRIDE}
)
