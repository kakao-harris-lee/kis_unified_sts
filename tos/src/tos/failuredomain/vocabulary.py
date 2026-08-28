"""Failure-domain coordinate vocabulary — the taxonomy / behavior / status / kind enums.

Spec terms = code terms (design #27 §2; boundary design #1 §2.4). This module authors the
**only** thing ADR-002-009 leaves unowned by a sibling (design #27 §3.4): the isolation-domain
**coordinate vocabulary**. ``safety_cell`` and ``failure_domain`` **scalars / enum members are
already sibling-owned** (capsule ``safety_cell: str | None``; afg / are ``SAFETY_CELL``; afg
``failure_domain_separated``; rlp ``ScopeDimension.SAFETY_CELL`` / ``FAILURE_DOMAIN``) and are
**not** redefined here — only the taxonomy, the failure-behavior catalogue, the claim-status
axis, and the physical/logical/common-mode classification are new (design #27 §2/§3.4).

All four enums are **plain, closed** ``StrEnum`` structural identifiers (design #27 §2.1A/§2.1E,
m5 — the rlp ``ScopeDimension`` "plain, closed StrEnum" precedent): they are consumed by
``is`` identity / set membership, never read as a gate result with ``if key:``, so they are
deliberately not truthy-sealed; an unregistered value is a construction failure. Enumerating a
closed spec catalogue is a **structural** transcription, never a numeric threshold — there is
**no** number anywhere in ``tos.failuredomain`` (design #27 §0.2: every blast-radius /
broker-session / partition bound is injected or deferred; CLAUDE.md configuration-driven).

Every member is broker-agnostic (project memory ``tos-spec-broker-agnostic``): broker session,
account, and rate-limit sharing appear only as **capability classes**, never as a named broker.

Regime tag: **EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.**

Pure module: stdlib only; no ``pydantic``, no ``shared.*``, no sibling ``tos.*`` (design #27
§0.3).
"""

from __future__ import annotations

from enum import Enum, StrEnum

__all__ = [
    "SIBLING_OWNER_TOKENS",
    "ExplicitlyAnalyzedEmpty",
    "FailureBehaviorKind",
    "FailureDomainKind",
    "IsolationClaimStatus",
    "IsolationKind",
]


class FailureDomainKind(StrEnum):
    """The failure-domain taxonomy — 22 = ADR §4.1 line 80 (18) + RFC-002 §24.1 (4).

    ADR-002-009 §4.1 line 78 defines a failure domain as "A set of components that may fail,
    become stale, be corrupted, or become unreachable together because of one causal event",
    and line 80 enumerates eighteen: "process, runtime, node, zone, region, datastore, event
    infrastructure, cache, network path, broker session, account, credential, workload
    identity, deployment pipeline, clock, configuration distribution, parser, and shared risk
    library."

    ADR §5 line 132 additionally binds a **normative floor**: "The matrix SHALL cover at
    minimum the failure-domain categories listed in RFC-002 §24.1." RFC-002 §24.1
    (``RFC-002-Architecture.md`` line 1888) lists four **supply-chain** categories the ADR §4.1
    sentence does not spell out — "source-code repository and review workflow"; "isolated build
    runner and dependency/toolchain resolver"; "artifact signer, key custody, and transparency
    or admission service"; "content-addressed artifact registry and restore path" — so they are
    members here (design #27 §2.1A, M1). Deployment-provenance / supply-chain **governance** is
    ADR-002-029's; ``tos.failuredomain`` owns only the **coordinate** (ADR §10 line 270 defers
    provenance — no conflict).

    **Closed at 22.** Extending the taxonomy is a Phase-0 profile amendment (design #27 §8.2-1),
    not an ad-hoc code edit: a member that is not in this enum cannot be constructed, so an
    unclassified domain can never be silently smuggled into a matrix row.
    """

    # --- ADR §4.1 line 80, in ADR order (18) ---------------------------------
    PROCESS = "PROCESS"
    RUNTIME = "RUNTIME"
    NODE = "NODE"
    ZONE = "ZONE"
    REGION = "REGION"
    DATASTORE = "DATASTORE"
    EVENT_INFRASTRUCTURE = "EVENT_INFRASTRUCTURE"
    CACHE = "CACHE"
    NETWORK_PATH = "NETWORK_PATH"
    BROKER_SESSION = "BROKER_SESSION"
    ACCOUNT = "ACCOUNT"
    CREDENTIAL = "CREDENTIAL"
    WORKLOAD_IDENTITY = "WORKLOAD_IDENTITY"
    DEPLOYMENT_PIPELINE = "DEPLOYMENT_PIPELINE"
    CLOCK = "CLOCK"
    CONFIGURATION_DISTRIBUTION = "CONFIGURATION_DISTRIBUTION"
    PARSER = "PARSER"
    SHARED_RISK_LIBRARY = "SHARED_RISK_LIBRARY"
    # --- RFC-002 §24.1 supply-chain floor (4; ADR §5 line 132 mandates it) ----
    #: "source-code repository and review workflow"
    SOURCE_REPOSITORY = "SOURCE_REPOSITORY"
    #: "isolated build runner and dependency/toolchain resolver"
    BUILD_TOOLCHAIN = "BUILD_TOOLCHAIN"
    #: "artifact signer, key custody, and transparency or admission service"
    ARTIFACT_SIGNING = "ARTIFACT_SIGNING"
    #: "content-addressed artifact registry and restore path"
    ARTIFACT_REGISTRY = "ARTIFACT_REGISTRY"


class FailureBehaviorKind(StrEnum):
    """The nine failure behaviors a matrix row records (ADR §5 line 122, verbatim).

    ADR-002-009 §5 line 122, the "Failure behavior" matrix field: "Crash, omission, delay,
    duplication, corruption, partition, stale survival, Byzantine input, or exhaustion."

    **Closed at 9** — the ADR sentence is an exhaustive "or" list for that field, so an
    unlisted behavior is a construction failure rather than a silently accepted free-form
    string.
    """

    CRASH = "CRASH"
    OMISSION = "OMISSION"
    DELAY = "DELAY"
    DUPLICATION = "DUPLICATION"
    CORRUPTION = "CORRUPTION"
    PARTITION = "PARTITION"
    STALE_SURVIVAL = "STALE_SURVIVAL"
    BYZANTINE_INPUT = "BYZANTINE_INPUT"
    EXHAUSTION = "EXHAUSTION"


class IsolationClaimStatus(StrEnum):
    """The isolation-claim status axis (ADR §1 line 32, §4.4 line 96; design #27 §2.1C).

    ADR §4.4 line 96: "A versioned claim that one failure cannot defeat specified controls
    together. Every claim SHALL state assumptions, excluded common modes, enforcement
    mechanisms, verification cases, and residual risk." ADR §1 line 32: "If an asserted
    isolation property **cannot be positively established**, the affected paths SHALL be
    classified as common-mode."

    **Polarity discipline** (design #27 §2.1C/§4.1): ``ESTABLISHED`` is reachable **only** when
    every one of the §4.4 five fields is positively present; everything else — a missing field,
    a bare unmarked ``∅``, an unknown, an untested or an undocumented sharing — is
    ``COMMON_MODE`` (ADR §5 line 130: "Unknown, untested, or undocumented sharing SHALL be
    recorded as common-mode. It SHALL NOT be recorded as independent with an explanatory
    footnote."). ``UNKNOWN`` is the *absent-claim* value — no claim was supplied at all — and is
    treated exactly as conservatively as ``COMMON_MODE`` by every predicate in
    :mod:`tos.failuredomain.predicates`; the two are kept distinct so a matrix reviewer can
    tell "analysed and found common-mode" from "never claimed".

    This is the **general cross-domain isolation-claim** axis. It is **not** the sbr
    recovery-readiness proof (``restricted_isolation_proven`` / ``IsolationFacts.all_proven``,
    ADR-002-017 §17 eight axes), **not** the authority cross-environment isolation (§18.4), and
    **not** the time-source ``common_mode_group`` collapse — different grain, different scope
    (design #27 §3.3/§3.5; the seam tests pin each boundary).
    """

    ESTABLISHED = "ESTABLISHED"
    COMMON_MODE = "COMMON_MODE"
    UNKNOWN = "UNKNOWN"


class IsolationKind(StrEnum):
    """Physical / logical / common-mode classification (RFC-002 §24.1 line 1910; ADR §7 line 192).

    RFC-002 §24.1 line 1910: "For each shared dependency, the matrix SHALL identify affected
    authorities, failure consequence, containment behavior, **physical/logical/common-mode
    classification**, residual risk, and verification method." ADR-002-009 §7 line 192:
    "**Logical separation on one runtime or node SHALL be described as logical separation, not
    physical independence.**" RFC-002 §24.1 line 1912 likewise: "Logical service separation
    SHALL NOT be presented as proof of physical failure independence."

    Carried by
    :attr:`~tos.failuredomain.records.FailureDomainAllocationEntry.isolation_kind`, where
    ``None`` (unclassified) is read **fail-closed as** :attr:`COMMON_MODE` — an unclassified
    dependency is never treated as ``PHYSICAL`` or ``LOGICAL`` (design #27 §2.1E).

    **negative-grep confirmed (anti-phantom, design #27 §0.5)**: ``git grep -l IsolationKind
    tos/src/tos`` returned empty before this package landed — no sibling owns this
    classification, so it is a genuine ``tos.failuredomain`` original rather than a re-authoring
    (the regression is locked by the ``test_seam_siblings`` negative-token assertion).
    """

    PHYSICAL = "PHYSICAL"
    LOGICAL = "LOGICAL"
    COMMON_MODE = "COMMON_MODE"


class ExplicitlyAnalyzedEmpty(Enum):
    """The positively-declared-empty ``∅`` marker (design #27 §4.1 — ``∅`` both ways).

    An empty collection is **ambiguous**: it can mean "nobody analysed this" or "this was
    analysed and the answer is genuinely nothing". ADR §5 line 130 forces the conservative
    reading of the first ("Unknown, untested, or undocumented sharing SHALL be recorded as
    common-mode"), while ADR §4.4 still allows a claim whose analysis positively excluded no
    common mode to be complete. This marker separates the two, so that

    * ``None``                       => not analysed          => not positively present,
    * ``frozenset()`` (bare ``∅``)   => nothing listed, unmarked => not positively present,
    * ``ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY`` => analysed, nothing to exclude
      => **positively present**,
    * a non-empty ``frozenset``      => positively present.

    A vacuous ``∅`` can therefore never buy an ``ESTABLISHED``, and a legitimate
    positively-empty analysis is not blocked either (both directions are canaried in
    ``test_failuredomain_isolation_claim``).

    Deliberately a **plain** :class:`enum.Enum`, **not** a ``StrEnum`` (unlike the four
    coordinate vocabularies above), because the field it inhabits is a union with
    ``frozenset[str]``. **Measured**: pydantic 2.12.5 in its default (smart) union mode already
    refuses to validate a bare ``str`` into ``frozenset[str]``, so a ``StrEnum`` marker is *not*
    silently split into single characters today. The plain ``Enum`` is chosen to remove the
    **dependence on that behaviour** — union resolution is version- and mode-specific, whereas a
    non-``str`` member is unambiguous under any of them, and it keeps the marker structurally
    outside the taxonomy's string space rather than merely distinguishable within it. The marker
    is compared with ``is`` identity only.
    """

    EXPLICITLY_ANALYZED_EMPTY = "EXPLICITLY_ANALYZED_EMPTY"


#: The design #27 §6.2 drift-lock anchor: every sibling symbol §3.5 attributes an ADR-002-009
#: clause to, as an **injected owner token** (a bare dotted string — design #27 §3.2). A matrix
#: row's ``prevention`` / ``recovery`` / ``evidence`` / ``residual_risk`` field **points at** an
#: owner with one of these tokens; ``tos.failuredomain`` never imports the sibling and never
#: re-authors its predicate (**sibling edge 0**, design #27 §0.3/§3.1). The
#: ``test_seam_siblings`` drift-lock resolves **every** token against the **real** sibling
#: package (a test-only import, not counted in the §6.1 runtime closure) so a rename, a moved
#: parameter, or a deleted field in any sibling breaks this package's documentation loudly
#: instead of silently. **Missing-token count enforced at 0** (design #27 §6.2).
#:
#: Token grammar — ``"<package>.<symbol>"`` for a package-level export,
#: ``"<package>.<Type>.<member-or-field>"`` for an enum member or a model field, and
#: ``"<package>.<function>.<parameter>"`` for a predicate parameter.
SIBLING_OWNER_TOKENS: frozenset[str] = frozenset(
    {
        # egress (ADR-002-013) — §6.3 / §10.1 item 2 final egress + credential boundary
        "egress.credential_route_authority_disjoint",
        "egress.CredentialRouteInventoryEntry",
        # rcl (ADR-002-002) — §6.2 capacity serialization, §10.1 item 3, §13 aggregate
        "rcl.writer_fenced",
        "rcl.credible_union_capacity",
        "rcl.ClaimRecord",
        "rcl.CapacityState",
        # spg (ADR-002-014) — §10 / §11 deployment, config atomicity, rollback fencing
        "spg.activation_atomic",
        "spg.activation_serializable",
        "spg.envelope_incompatible",
        "spg.hard_and_runtime_versions_match",
        "spg.rollback_requires_new_generation",
        "spg.rollback_revives_nothing",
        "spg.compatibility_manifest_matches",
        # authority (ADR-002-003 / -007) — §6.1, §7 rule 6, §8.1, §8.4, §10 no-auto-rearm
        "authority.GenerationVector",
        "authority.rearm_gate",
        "authority.partition_authority_verdict.control_plane_verifiable",
        "authority.PartitionAuthorityVerdict.automatic_rearm_denied",
        "authority.LeaseReassignmentInputs.hard_fence_proven",
        # sbr (ADR-002-017) — §6.6 / §15 recovery isolation (general != recovery, §3.5-1)
        "sbr.restricted_isolation_proven",
        "sbr.restore_worst_credible_union",
        "sbr.competing_owner_fenced",
        "sbr.recovery_generation_monotone",
        "sbr.IsolationFacts.all_proven",
        # time (ADR-002-008) — §12 shared time common mode
        "time.independent_reference_count",
        "time.ReferenceSource.common_mode_group",
        "time.source_disagreement_within_bound",
        "time.freshness_verdict",
        # cur (ADR-002-024) — §8.2 event infrastructure, §8.3 cache fail-closed
        "cur.CurrentnessAdmission",
        "cur.ProofResult",
        "cur.fence_advances_floor",
        # orthostate (ADR-002-005) — §14 retain-UNKNOWN, §10.1 item 3 send boundary
        "orthostate.KnowledgeState",
        "orthostate.TransmissionAttemptState.SEND_STARTED",
        # brokercap — §9 broker session/limit/rate capability class, §6.5 environment
        "brokercap.CapabilityStatus",
        "brokercap.ConformanceClass.CLASS_D_NON_LIVE",
        "brokercap.environment_binding_ok",
        # ioc (ADR-002-020) — §6.5 live/non-live axis, mutation fence
        "ioc.ConformanceAxis.LIVE_NONLIVE",
        "ioc.mutation_fence_holds",
        # afg (ADR-002-022) — action-flow writer hard fence (one of the six fence owners)
        "afg.partition_lease_exclusive.stale_writer_hard_fenced",
        # hag — §6.5 / §15 human-approval environment scope
        "hag.ApprovalScope.environments",
        # venue — §6.4 / §7 gate authority != execution authority
        "venue.gate_authority_separated",
        # rlp (ADR-002-025) — trial-plan scope catalogue (token overlap, proposition differs)
        "rlp.ScopeDimension.SAFETY_CELL",
        "rlp.ScopeDimension.FAILURE_DOMAIN",
    }
)
