"""Currentness-axis vocabulary — the CUR StrEnums (design #23 §2.2).

Spec terms = code terms (design #23 §2.2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-024 (§12 proof result, §13 admission verdict, §9 dimension catalogue).

**Truthy-sentinel structural seal (design #23 §2.2/§4.2 — #13/#14 M1 adopted from the start).**
``ProofResult`` (CURRENT / RESTRICTED / UNKNOWN) and ``CurrentnessAdmission`` (ADMIT / DENY) are
non-empty ``StrEnum`` strings, so ``if result:`` / ``bool(admission)`` would read a **denial**
member (``RESTRICTED`` / ``UNKNOWN`` / ``DENY``) as **truthy** — a catastrophic silent fail-open
that reads a *rejection* as an *admission* (ADR §6 CUR-INV-011 line 183 "Unknown ... blocks new
risk"; §12 line 316 "Only ``CURRENT`` ... can satisfy this one conformance check"). Each subclasses
:class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``,
making them *truthy-untestable*. The mandated consume gates are the explicit positive-identity
comparison (``result is ProofResult.CURRENT`` / ``admission is CurrentnessAdmission.ADMIT``) —
everything else is denial. Isomorphic to the iap ``_NonTruthyStrEnum`` seal (``iap/vocabulary.py:50``)
and the egress seal (``egress/vocabulary.py:48``); authored locally-fresh here (sibling edge 0 — no
iap / egress import).

``DimensionKey`` is a **plain, closed** ``StrEnum`` (ADR §9 dimension catalogue): it is a structural
identifier token consumed by set membership / subset checks
(:func:`~tos.cur.predicates.policy_covers_mandated_dimensions`), never a gate result read with
``if key:``, so it does not need the truthy seal. It is a **structural dimension identifier**, never
a threshold / bound — hardcoding it is **not** a numeric hardcode (design #23 §2.2/§8; the ioc / spg
field-enumeration precedent). ``CONTEXT`` is a **separate** dimension from ``CRITICAL_INPUT`` (ADR
§9:259 / §26:617 — v1.1 MAJOR-2: omitting it would let a CONTEXT-absent vector vacuously pass
:func:`~tos.cur.predicates.vector_complete`).

This module names **no** concrete broker (broker-agnostic — project memory ``tos-spec-broker-
agnostic``; design #23 §0.2) and hardcodes **no** numeric floor / age / bound (ADR §8): every bound
is an injected Profile-INSTANCE value (design #23 §8). An enum member is a structural label, never a
limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #23 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ProofResult",
    "CurrentnessAdmission",
    "DimensionKey",
    "CONDITIONAL_DIMENSION_KEYS",
    "MANDATED_DIMENSION_FLOOR",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #23 §2.2/§4.2).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(admission)`` would read a
    denial member (``RESTRICTED`` / ``UNKNOWN`` / ``DENY``) as truthy — a catastrophic silent
    fail-open that reads a rejection as an admission. :meth:`__bool__` therefore raises
    ``TypeError`` on every member, so the misuse surfaces as a loud runtime error rather than a
    silent pass. Consumers MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``).
    Isomorphic to the iap ``_NonTruthyStrEnum`` seal (``iap/vocabulary.py:50``) and the egress seal
    (``egress/vocabulary.py:48``); authored locally-fresh here (sibling edge 0, no iap / egress
    import — design #23 §0.4). ``is`` identity, ``.value``, hashing, set membership, and
    ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #23 §2.2/§4.2).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is ProofResult.CURRENT``;
                ``admission is CurrentnessAdmission.ADMIT``); a bare ``if result:`` /
                ``bool(result)`` would fail open on the truthy denial strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is ProofResult.CURRENT`; "
            "`admission is CurrentnessAdmission.ADMIT`) per the truthy-sentinel seal "
            "(design #23 §2.2/§4.2/M1). The denial members are non-empty strings and a bare "
            "`if result:` would fail open — reading RESTRICTED / UNKNOWN / DENY as an admission."
        )


class ProofResult(_NonTruthyStrEnum):
    """The Egress Currentness Proof conformance result (ADR-002-024 §12, non-truthy — critical seal).

    §12 line 316 verbatim: "The proof result is ``CURRENT``, ``RESTRICTED``, or ``UNKNOWN``. **Only
    ``CURRENT``**, together with every separately required authority and commitment, can satisfy
    this one conformance check." **Truthy-untestable** (``__bool__`` raises): ``RESTRICTED`` /
    ``UNKNOWN`` are non-empty strings, so ``if result:`` would read a *denial* as *conformance* —
    the catastrophic fail-open this seal blocks (ADR §6 CUR-INV-011 line 183 "Unknown ... blocks new
    risk"). Currentness is fundamentally DENY-biased: the mandated consume gate is
    ``result is ProofResult.CURRENT`` — every other value is denial. ``CURRENT`` itself grants **no**
    authority (§12 line 316; all-false :class:`~tos.cur._base.AllFalseCurrentnessAuthority`, §6.13);
    this L1 model owns the **vocabulary** of the verdict, not its per-send runtime production
    (design #23 §1/§6.6 over-realization boundary).
    """

    CURRENT = "CURRENT"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class CurrentnessAdmission(_NonTruthyStrEnum):
    """The final currentness admission verdict (ADR-002-024 §13, non-truthy).

    §13 resolves to admit or deny a per-send transmission on currentness grounds. **Truthy-
    untestable** (``__bool__`` raises): ``DENY`` is a non-empty string, so ``if admission:`` would
    read a *denial* as an *admission* (CUR-INV-001 line 143 "partial ... vectors are denial"). The
    mandated consume gate is ``admission is CurrentnessAdmission.ADMIT`` — every other value is
    denial. The actual per-send admission is an ADR-002-024 §13 runtime transaction (+Security,
    design #23 §6c); this L1 model owns the **vocabulary** of that verdict, not its runtime
    production.
    """

    ADMIT = "ADMIT"
    DENY = "DENY"


class DimensionKey(StrEnum):
    """The Safety Currentness Vector dimension catalogue (ADR-002-024 §9, closed structural token).

    §9 line 250-262 enumerates the dependency dimensions a complete action-scoped vector must carry.
    A **plain, closed** ``StrEnum`` structural identifier consumed by set membership / subset checks
    (:func:`~tos.cur.predicates.policy_covers_mandated_dimensions` /
    :func:`~tos.cur.predicates.vector_complete`), never a gate result read with ``if key:``, so it is
    deliberately **not** truthy-sealed. It is a **structural dimension identifier**, never a numeric
    threshold / bound — enumerating it is **not** a numeric hardcode (design #23 §2.2/§8; the ioc /
    spg field-enumeration precedent).

    ``CONTEXT`` (capsule CII) is a **separate** dimension from ``CRITICAL_INPUT`` (ADR §9:259 /
    §26:617 — v1.1 MAJOR-2: without this member a CONTEXT-absent vector would vacuously pass
    :func:`~tos.cur.predicates.vector_complete`, defeating the unrepresented-dimension seal the
    yolk predicate exists to enforce). ``RESTRICTED_LIVE_TRIAL`` is the **conditional** dimension
    (§9:258; RLP-deferred content — design #23 §0.4f) and is the **only** member outside the
    :data:`MANDATED_DIMENSION_FLOOR`. The set is closed ("at least" floor — a policy may require
    *more*, never fewer; §5.5).
    """

    ENVIRONMENT_SCOPE = "ENVIRONMENT_SCOPE"
    CURRENTNESS_POLICY = "CURRENTNESS_POLICY"
    COMMIT_LOG = "COMMIT_LOG"
    SAFETY_AUTHORITY = "SAFETY_AUTHORITY"
    SAFETY_ENVELOPE_PROFILE = "SAFETY_ENVELOPE_PROFILE"
    DEVIATION = "DEVIATION"
    INCIDENT = "INCIDENT"
    MONITORING = "MONITORING"
    RELEASE = "RELEASE"
    POST_TRADE = "POST_TRADE"
    TRUSTWORTHY_TIME = "TRUSTWORTHY_TIME"
    RECOVERY = "RECOVERY"
    CRITICAL_INPUT = "CRITICAL_INPUT"
    CONTEXT = "CONTEXT"
    CONSTRAINT = "CONSTRAINT"
    CONSTRUCTION = "CONSTRUCTION"
    TRADING_APPROVAL = "TRADING_APPROVAL"
    AGGREGATE_RISK = "AGGREGATE_RISK"
    ACTION_FLOW = "ACTION_FLOW"
    DECISION_PROOF_INTENT = "DECISION_PROOF_INTENT"
    EGRESS_IDENTITY = "EGRESS_IDENTITY"
    #: Conditional (restricted-live trial only; §9:258) — the ONLY non-mandated member.
    RESTRICTED_LIVE_TRIAL = "RESTRICTED_LIVE_TRIAL"


#: The conditional dimension keys (excluded from the mandated floor; §9:258 / design #23 §5.1).
CONDITIONAL_DIMENSION_KEYS: frozenset[DimensionKey] = frozenset(
    {DimensionKey.RESTRICTED_LIVE_TRIAL}
)

#: The §9 mandated floor: every **non-conditional** ``DimensionKey`` member (CONTEXT included).
#: :func:`~tos.cur.predicates.vector_complete` floors its ``mandated`` argument to at least this
#: set — a caller can require *more* but **never fewer** (design #23 §5.1 v1.1 MINOR-1). Derived
#: from the enum so it can never drift below the catalogue (the §7.2 enum-drift property asserts
#: the derivation equals the ADR §9-derived reference set, CONTEXT included).
MANDATED_DIMENSION_FLOOR: frozenset[DimensionKey] = (
    frozenset(DimensionKey) - CONDITIONAL_DIMENSION_KEYS
)
