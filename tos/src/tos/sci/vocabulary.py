"""Supply-chain vocabulary — the SCI tri-state enums, the mutable-name helper, and the ADR
transcription anchors (design #29 §2.2/§4).

Spec terms = code terms (design #29 §2.2; boundary design #1 §2.4). The two enums are authored
**verbatim** from ADR-002-029 (§5.7 line 127 admission result; §9 line 267 / SCI-INV-007 line 179
effective-principal independence).

**Truthy-sentinel structural seal (design #29 §0.5-3 / §2.2 — the #13/#14 M1 lesson adopted from the
start).** ``AdmissionResult`` (``ADMIT`` / ``DENY`` / ``UNKNOWN``) and ``IndependenceResult``
(``INDEPENDENT`` / ``COMMON_MODE`` / ``UNKNOWN``) are non-empty ``StrEnum`` strings, so ``if
result:`` / ``bool(result)`` would read a **denial / unproven** member (``DENY`` / ``UNKNOWN`` /
``COMMON_MODE``) as **truthy** — a catastrophic silent fail-open that reads a *rejection* as a *go*.
Each subclasses :class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises**
``TypeError``, making them truthy-untestable. The mandated consume gates are the explicit
positive-identity comparisons ``result is AdmissionResult.ADMIT`` and ``result is
IndependenceResult.INDEPENDENT`` — everything else is denial, and ``ADMIT`` / ``INDEPENDENT`` are
never a residual space reached by a fall-through (the AFG C1 lesson, design #29 §0.5-4). Isomorphic
to the iap ``ApprovalResult`` / cur ``ProofResult`` / rlp ``PlanResult`` / wdr ``DecisionResult``
seals; authored **locally-fresh** here (sibling edge 0 — no iap / cur / rlp / wdr import, design #29
§3.3).

``ADMIT`` grants nothing on its own: §1 line 21 verbatim — "``ADMIT`` means only that the exact
artifact is eligible to be included in one new **Admitted Release Set**."

The ADR transcription tuples (:data:`SCI_INVARIANT_TITLES`, :data:`AUTHORITY_OWNERSHIP_ACTIONS`,
:data:`SOFTWARE_RELEASE_POLICY_FIELD_GROUPS`, :data:`ADMISSION_PROTOCOL_STEPS`,
:data:`ACTIVE_CURRENTNESS_ITEMS`, :data:`PARTITION_FAILURE_MODES`,
:data:`SCI_ACCEPTANCE_CASE_TITLES`, :data:`APPROVAL_GATE_ITEMS`) are **manually transcribed
regression anchors** (design #29 §6.2; the wdr ``ScopeDimension`` anchor precedent): the §6.2
anchor-drift properties assert their counts and names against the ADR so a whole field-group being
dropped — the WDR MAJOR-1 defect class — fails loudly instead of silently. Each entry is a
**structural label**, never a threshold or a bound: transcribing one is **not** a numeric hardcode
(design #29 §8 — the ten VERIFICATION-PROFILE-002 keys are all ``null`` / ``owner: TBD`` and are
injected, never written here).

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #29 §0.1) and hardcodes **no** numeric floor, size, duration, or
threshold (ADR §8 line 257 "approved numeric bounds and age limits"): every bound is an injected
Profile-INSTANCE value (design #29 §8).

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV**; all 12 register
rows carry ``+Security`` — the organisational gate is entirely unmet; an EV-L1-complete claim is
forbidden.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #29 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ACTIVE_CURRENTNESS_ITEMS",
    "ADMISSION_PROTOCOL_STEPS",
    "APPROVAL_GATE_ITEMS",
    "AUTHORITY_OWNERSHIP_ACTIONS",
    "AdmissionResult",
    "IndependenceResult",
    "MUTABLE_NAME_METACHARACTERS",
    "MUTABLE_NAME_SENTINELS",
    "PARTITION_FAILURE_MODES",
    "SCI_ACCEPTANCE_CASE_TITLES",
    "SCI_INVARIANT_TITLES",
    "SOFTWARE_RELEASE_POLICY_FIELD_GROUPS",
    "UNKNOWN_RESTRICTION_STATE",
    "is_mutable_name_notation",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #29 §2.2/§0.5-3).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(result)`` would read a
    denial / unproven member (``DENY`` / ``UNKNOWN`` / ``COMMON_MODE``) as truthy — a catastrophic
    silent fail-open that reads a rejection as a go. :meth:`__bool__` therefore raises ``TypeError``
    on every member, so the misuse surfaces as a loud runtime error rather than a silent pass.
    Consumers MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to
    the iap ``ApprovalResult`` / cur ``ProofResult`` / rlp ``PlanResult`` / wdr ``DecisionResult``
    seals; authored **locally-fresh** here (sibling edge 0 — design #29 §3.3). ``is`` identity,
    ``.value``, hashing, set membership, and ``model_dump`` are all unaffected (none calls
    ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #29 §2.2).

        Raises:
            TypeError: Always — a supply-chain result must be compared by explicit
                positive identity, never read as a boolean.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — a DENY / UNKNOWN / COMMON_MODE "
            "member is a non-empty string and would read as truthy, silently turning a "
            "rejection into a go. Use the explicit positive-identity gate "
            "(x is AdmissionResult.ADMIT / x is IndependenceResult.INDEPENDENT) "
            "— design #29 §2.2 / ADR-002-029 §5.7 line 127."
        )


class AdmissionResult(_NonTruthyStrEnum):
    """The single-use non-authorizing artifact-admission result (ADR-002-029 §5.7 line 127).

    §5.7 line 127 verbatim: "An immutable single-use non-authorizing result of ``ADMIT``, ``DENY``,
    or ``UNKNOWN`` for one exact Release Artifact Manifest, Software Release Policy, compatibility
    graph, target scope, and predecessor Release Generation."

    ``ADMIT`` is a **positive identity**, never a residual space: §1 line 21 — "``ADMIT`` means only
    that the exact artifact is eligible to be included in one new **Admitted Release Set**. It does
    not deploy software, activate configuration, issue Safety Authority or Live Authorization,
    mutate or release Risk Capacity Ledger capacity, classify protection, create a Transmission
    Capability, permit broker transmission, clear HALT, close an incident, establish recovery
    readiness, restore production scope, or re-arm." Consumed **only** through ``result is
    AdmissionResult.ADMIT`` (design #29 §0.5-4).

    Carried by the ARTIFACT-ADMISSION-DECISION (``result``, template line 8) and ADMITTED-RELEASE-SET
    (``result``, template line 9) templates **only** (design #29 §2.2 MINOR-2): the
    BUILD-PROVENANCE-ATTESTATION and RUNTIME-ARTIFACT-ATTESTATION ``result`` fields are **not**
    admission results — §7 line 232 "attestation is a fact, not permission" — and are carried as an
    opaque ``str | None``.
    """

    ADMIT = "ADMIT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class IndependenceResult(_NonTruthyStrEnum):
    """The injected effective-principal independence verdict (SCI-INV-007 line 179; §9 line 267).

    SCI-INV-007 line 179 verbatim: "Source author, reviewer, builder, signer, registry
    administrator, admission reviewer, deployer, configuration activator, and live armer are
    evaluated by effective control and common mode before independence or quorum is credited." §9
    line 267: "Repository administration, branch protection, signed commits, review count, or merge
    status alone does not prove independence when one person controls the underlying accounts,
    recovery paths, automation, or signing identities."

    The verdict itself is **hag-owned** (ADR-002-015 effective-principal collapse; design #29 §0.4e)
    — SCI is an *instance consumer*, never a producer: it re-authors no collapse, quorum, or
    account-graph logic and consumes this token as an injected coordinate. The template fields are
    ``effective_principal_independence_result`` (SOURCE-REVISION-MANIFEST line 23,
    ARTIFACT-ADMISSION-DECISION line 29) and ``attestor_independence_result``
    (RUNTIME-ARTIFACT-ATTESTATION line 42).

    ``INDEPENDENT`` is a **positive identity**: ``COMMON_MODE``, ``UNKNOWN``, and ``None`` are all
    restrictive (unproven independence *is* common mode, design #29 §5.1 / §0.4e).
    """

    INDEPENDENT = "INDEPENDENT"
    COMMON_MODE = "COMMON_MODE"
    UNKNOWN = "UNKNOWN"


#: The template placeholder for an unresolved ``restriction_state``
#: (ADMITTED-RELEASE-SET line 42 ``restriction_state: UNKNOWN``). The **clear** value set is a
#: Phase-0 template INSTANCE decision (design #29 §5.0) — no member is invented here; SCI decides
#: only "``UNKNOWN`` / absent ⇒ deny" (§5.5 item 4).
UNKNOWN_RESTRICTION_STATE = "UNKNOWN"

#: Mutable-name sentinels that are **not** artifact identity (SCI-INV-002 line 159: "Tags, branches,
#: package names, registry paths, service names, deployment labels, timestamps, ``latest``, and local
#: cache state are not identity or currentness proof"; §1 line 19). Matched **case-insensitively**
#: after a ``strip().casefold()`` normalization (the rlp ``WILDCARD_SENTINELS`` shape, design #25
#: §0.4 — a case variant such as ``"Latest"`` must not slip through).
MUTABLE_NAME_SENTINELS: frozenset[str] = frozenset(
    {
        "latest",
        "head",
        "main",
        "master",
        "stable",
        "current",
        "edge",
    }
)

#: Glob / tag / path / registry-reference metacharacters whose presence anywhere in a value makes it
#: a mutable *name notation* rather than an exact content digest (``registry/image:tag``,
#: ``pkg@version``, ``release-*``). Best-effort, non-exhaustive (design #29 §0.5-8).
MUTABLE_NAME_METACHARACTERS: frozenset[str] = frozenset({"*", "?", ":", "/", "@"})

#: :data:`MUTABLE_NAME_SENTINELS` normalized with ``casefold`` so a case variant of a catalogued
#: sentinel is caught (the membership test normalizes the candidate the same way).
_MUTABLE_NAME_SENTINELS_CASEFOLD: frozenset[str] = frozenset(
    sentinel.strip().casefold() for sentinel in MUTABLE_NAME_SENTINELS
)

#: The reserved canonical-template placeholder for an unfilled field (design #4 §3.2).
_TEMPLATE_PLACEHOLDER = "TBD"
#: The placeholder normalized the same way every other denylist member is (strip + casefold).
_TEMPLATE_PLACEHOLDER_NORMALIZED = _TEMPLATE_PLACEHOLDER.strip().casefold()


def _is_template_placeholder(value: object) -> bool:
    """Whether a value is the reserved ``"TBD"`` placeholder, **case- and padding-insensitively**.

    Single-sourced here (the lowest layer both :mod:`tos.sci.records` and
    :mod:`tos.sci.predicates` import) so the model-layer coexistence seals and the predicate layer
    cannot drift apart — a two-layer defence whose two layers normalize differently is a one-layer
    defence.

    An **exact** ``value == "TBD"`` comparison would accept ``"tbd"``, ``" TBD "``, and ``"Tbd"`` as
    concrete identities, which is the same defect class the mutable-name denylist normalizes away
    (design #29 §0.5-8 / the RLP #25 ``"All"`` case-variant lesson): a producer that emits a
    lower-cased placeholder would satisfy every mandated-binding check at once. Non-strings are
    never the placeholder (an ``int`` ordering scalar is handled by its own ``None`` check).
    """
    return (
        isinstance(value, str)
        and value.strip().casefold() == _TEMPLATE_PLACEHOLDER_NORMALIZED
    )


def is_mutable_name_notation(value: str | None) -> bool:
    """Whether a value is a mutable *name* notation rather than exact identity (best-effort).

    SCI-INV-002 line 159: "Safety-relevant identity uses exact canonical content digests. Tags,
    branches, package names, registry paths, service names, deployment labels, timestamps,
    ``latest``, and local cache state are not identity or currentness proof." §1 line 19: "A branch,
    tag, package name, registry path, service label, mutable image tag, ``latest``, local cache,
    successful build, passing scan, or historical signature is not artifact identity and is not
    current admission proof."

    A value is a mutable-name notation when, after a ``strip().casefold()`` normalization, it is
    (a) **empty** (whitespace-only is not an identity), (b) a member of the
    :data:`MUTABLE_NAME_SENTINELS` catalogue matched **case-insensitively** (so ``"Latest"`` /
    ``"  HEAD "`` are caught, not only the exact-cased list members), or (c) contains any
    :data:`MUTABLE_NAME_METACHARACTERS` glob / tag / path / registry metacharacter (so
    ``"registry/image:tag"`` / ``"pkg@1"`` / ``"release-*"`` are caught). A ``None`` is **absent**
    (the coordinate is not bound — the caller treats that case separately, see
    :func:`~tos.sci.predicates.mutable_name_is_not_identity`) and returns ``False``.

    **Best-effort, non-exhaustive denylist (honesty — design #29 §0.5-8 / the RLP #25 lesson).**
    This value-model check catches the catalogued sentinels and common metacharacters only. Novel
    mutable notations, registry manifest-list resolution, mirror divergence, and local cache
    substitution (§14) are **not** value-model-decidable: they are owned by +Security and the
    runtime. This helper does **not** guarantee the full SCI-INV-002 property.

    Args:
        value: The candidate identity coordinate (``None`` ⇒ absent, returns ``False``).

    Returns:
        ``True`` iff the value is a (detectable) mutable-name notation.
    """
    if value is None:
        return False
    normalized = value.strip().casefold()
    if not normalized:
        return True
    if normalized in _MUTABLE_NAME_SENTINELS_CASEFOLD:
        return True
    return any(metacharacter in value for metacharacter in MUTABLE_NAME_METACHARACTERS)


#: ADR §6 line 153-215 — the sixteen SCI safety-invariant titles, verbatim (design #29 §4.1). A
#: manually-transcribed regression anchor: the §6.2 drift property asserts the count and the exact
#: titles, so a dropped invariant is loud.
SCI_INVARIANT_TITLES: tuple[str, ...] = (
    "Supply-Chain Artifacts Are Not Authority",
    "Artifact Identity Is Exact and Immutable",
    "Source-to-Artifact Lineage Is Closed",
    "Provenance Is Not Correctness",
    "Dependency and Toolchain Closure Is Complete",
    "Admission Is Deterministic and Exact-Scope",
    "Effective Independence Is Required",
    "Signature Is Not Current Admission",
    "One Complete Release Generation Governs Scope",
    "Actual Runtime Bytes Must Match",
    "Unknown Compatibility Is Incompatibility",
    "Rollback and Restore Are New Generations",
    "Active Release Currentness Is a Negative Gate",
    "Restriction Dominates Send Races",
    "Economic Effect Outlives Artifact State",
    "Evidence and Recovery Do Not Revive",
)

#: ADR §7 line 221-241 — the seventeen authority-ownership rows' ``Action`` column, verbatim
#: (design #29 §4.2). **Every one of them is a sibling / runtime / human owner**: SCI re-authors
#: none of them and carries an all-false authority block instead (§5.6a).
AUTHORITY_OWNERSHIP_ACTIONS: tuple[str, ...] = (
    "Propose source change",
    "Approve exact source revision",
    "Build artifact and provenance",
    "Resolve dependency/toolchain closure",
    "Sign artifact or attestation",
    "Store and retrieve artifact",
    "Decide artifact admission",
    "Commit Release Generation",
    "Deploy exact admitted artifact",
    "Attest actual runtime bytes",
    "Activate configuration",
    "Restrict current use",
    "Mutate or release capacity",
    "Classify protection",
    "Declare or close incident",
    "Transmit",
    "Establish readiness and re-arm",
)

#: ADR §8 line 249-257 — the nine Software Release Policy prose field groups (design #29 §4.3). The
#: seventeen ``*_policy_digest`` template fields that realize them are anchored separately on
#: :class:`~tos.sci.state.SoftwareReleasePolicyFieldGroups`.
SOFTWARE_RELEASE_POLICY_FIELD_GROUPS: tuple[str, ...] = (
    "exact policy identity, generation, canonical digest, predecessor, and scope",
    "approved source repositories, review policies, effective-principal rules, and history "
    "protections",
    "approved build recipes, builders, network policy, deterministic settings, and allowed "
    "nondeterminism",
    "dependency, toolchain, package-source, base-image, plugin, code-generation, and "
    "runtime-loading rules",
    "provenance, independent-build, reproducibility, differential, scan, test, and evidence "
    "requirements",
    "signer, key, threshold, rotation, revocation, registry, and custody rules",
    "artifact-manifest, admission, compatibility, deployment, runtime-attestation, and Release "
    "Generation contracts",
    "restriction, incident, rollback, restore, hotfix, recovery, and final-egress currentness "
    "behavior",
    "approved numeric bounds and age limits",
)

#: ADR §15 line 325-336 — the ten ordered admission-protocol steps, verbatim (design #29 §4.4).
#: Steps 1-7 are the binding set :func:`~tos.sci.predicates.admission_admits_only_positive` reads
#: structurally; steps 8-10 (issue / commit / invalidate) are the runtime's, never L1's.
ADMISSION_PROTOCOL_STEPS: tuple[str, ...] = (
    "bind one exact current Software Release Policy and target scope",
    "verify Source Revision Manifest identity, review, continuity, and effective-principal "
    "independence",
    "verify the complete dependency and toolchain closure and correction state",
    "verify Build Provenance Attestation, builder epoch, output digest, and required independent "
    "reproduction",
    "verify Release Artifact Manifest, signature, registry custody, schemas, protocols, "
    "migrations, and compatibility graph",
    "verify required scans, tests, evidence receipts, and unresolved findings without treating "
    "them as authority",
    "verify predecessor Release Generation and every current restriction floor",
    "issue one immutable `ADMIT`, `DENY`, or `UNKNOWN` decision for the exact candidate",
    "independently commit any eligible `ADMIT` decision into one new complete Admitted Release Set "
    "and Release Generation",
    "invalidate the single-use decision and every stale competing candidate",
)

#: ADR §19 line 376-385 — the eight Safety Currentness Vector items, verbatim (design #29 §4.5).
#: **Owned by cur (ADR-002-024) and egress (ADR-002-013)**: SCI produces the release facts those
#: items name and re-authors no per-send currentness transaction (§3.5).
ACTIVE_CURRENTNESS_ITEMS: tuple[str, ...] = (
    "exact Software Release Policy identity, generation, and digest",
    "exact Release Generation and Admitted Release Set digest",
    "exact applicable Release Artifact Manifest and lineage-graph digests",
    "current artifact-signing trust-bundle and key-status generation",
    "exact deployment, workload, environment, Safety Cell, and runtime-attestation identities",
    "current compatibility result for every consumer and broker-egress edge",
    "current restriction floors, incident scope, and stale-owner fences",
    "approved ages, trustworthy-time evidence, and invalidation state",
)

#: ADR §21 line 412-425 — the twelve partition / backpressure / failure rows' ``Failure`` column,
#: verbatim (design #29 §4.6). Every mandatory result is restrictive; §21 line 427: "No retry,
#: mirror, cache, alternate registry, previous artifact, emergency signer, manual copy, or operator
#: assertion may select a more permissive state when provenance, ordering, currentness, or scope is
#: unknown."
PARTITION_FAILURE_MODES: tuple[str, ...] = (
    "source or review history unavailable or conflicting",
    "builder, dependency source, toolchain, signer, or registry unavailable",
    "admission registry or Release Generation conflict",
    "supply-chain control plane partitioned while broker egress is reachable",
    "artifact retrieval digest, platform, layer, or signature mismatch",
    "runtime attestation missing, stale, mixed, or conflicting",
    "deployment queue or rollout backpressure",
    "revocation delivery delayed or lost",
    "signer or registry compromise suspected",
    "evidence or scanner unavailable",
    "unknown instance remains after rollout",
    "recovery completes",
)

#: ADR §27 line 552-598 — the twelve acceptance-case titles, verbatim (design #29 §4.7). §27 line
#: 550: "Written cases define obligations only. They are not completed evidence." **No SCI-AC is
#: discharged by Phase 1.**
SCI_ACCEPTANCE_CASE_TITLES: tuple[str, ...] = (
    "Source Identity and Review Integrity",
    "Build Isolation, Provenance, and Reproducibility",
    "Dependency and Toolchain Closure",
    "Signer, Key, and Attestation Compromise",
    "Registry Custody and Artifact Substitution",
    "Independent Admission and Compatibility",
    "Release Generation and Stale Fencing",
    "Deployment Attestation and Environment Confinement",
    "Mixed Version, Promotion, Rollback, and Restore",
    "Active Currentness, Revocation, Partition, and Send Race",
    "Authority Separation, Broker Finality, and Economic Continuity",
    "Evidence, Recovery, Hotfix, and Non-Revival",
)

#: ADR §30 line 643-656 — the fourteen approval-and-operational-gate conditions (design #29 §4.8),
#: abbreviated to their subject. **Phase 1 authors a slice of gate 1's shapes and gate 11's EV-L1
#: layer only; gates 2-10 and 12-14 remain entirely open**, and §30 line 658: "This ADR authorizes
#: architecture and implementation planning only."
APPROVAL_GATE_ITEMS: tuple[str, ...] = (
    "all eight canonical schemas approved",
    "source identity, review independence, history integrity, and closure security-reviewed",
    "isolated build, closure, provenance, reproducibility, and common-mode independently reviewed",
    "signing, key custody, revocation, registry custody, and compromise response security-reviewed",
    "deterministic independent admission, compatibility, Release Generation, and stale-writer "
    "fencing implemented",
    "deployment promotion, mixed-version denial, break-before-make, and runtime attestation "
    "implemented",
    "ADR-002-024 currentness and ADR-002-013 final-egress verification implemented without bypass",
    "rollback, restore, hotfix, partition, compromise, send race, and non-revival fault-injected",
    "supply-chain identities cannot mutate capacity, create authority, hold a route, or re-arm",
    "numeric bounds and age limits approved in the Verification Profile and measured",
    "SCI-EV-001 through SCI-EV-012 executed, retained, and independently reviewed",
    "all evidence retains negative, missing, conflicting, compromised, and stale outcomes",
    "no Critical or Major finding remains open",
    "Architecture Gate acceptance remains explicit",
)
