"""iap value models + the four digest-bound artifacts (design #15 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True, extra="forbid")``
via :class:`~tos.iap._base.FrozenModel`): ``extra="forbid"`` is the schema-level realization of
the §9 line 255 **unknown-top-level-field** rejection only. It does **not** cover a surplus /
substituted / missing member of the *artifact tuple* a request binds — that is enforced by the
:func:`~tos.iap.predicates.request_is_complete` / :func:`~tos.iap.predicates.exact_binding_holds`
structural guards (bidirectional set comparison, §5.1/§5.3), **not** by ``extra="forbid"`` (design
#15 §2.0 — no over-claim). Frozen is the record-level realization of append-only immutability
(§2.1): a corrected / newer artifact is a **new** generation (a fresh id + a supersede link),
never an in-place mutation — there is **no** update / delete / mutate / transmit / sign /
approve-side-effect method on any model (design #15 §2.0/§4.6). Enum values / field names use the
ADR §5-§20 terms verbatim (spec terms = code terms; the erratum seal, design #15 §2.2).

The iap model structure carries **no numeric bound** (design #15 §8.0): every age / bound is an
**injected opaque** ``int | None`` param (hardcoded numeric 0), and every decision rule is over
StrEnum / boolean / set / graph logic. A missing value fails closed at the consuming predicate
(§4/§19). Timing validity is an injected opaque flag / marker — iap reads **no** clock (§3.4/§19).

The four digest-bound citizens are each an :class:`~tos.iap._base.IndependentIdArtifact` with an
independent governance / issuance-assigned id (``id != f(digest)``, design #15 §0.4d) so a same-id
/ different-bytes forged / re-issued / substituted request / decision / consumption record is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. Each generation is an immutable record;
a legitimate re-issuance is a **new** generation (§2.1). Decision / consumption records are
**forward-only** (§2.3): they carry **no** future aggregate-risk / authority / capability
identity — later gates remain independently mandatory (§1 line 21; non-cyclic). ``TradingApprovalPolicy``
is an spg-governed member (ADR-002-014; §8 line 232): iap references it by digest scalar and spg
owns its governance (design #15 §3.5). The upstream dsl ``Proposal`` / capsule Capsule / Snapshot /
ioc envelope / command / ``ApprovedIntentContract`` are content-addressed siblings iap does **not**
redefine — it binds their digests by scalar (design #15 §3.4, sibling edge 0).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.iap._base``) only; no
``shared.*``, no sibling ``tos.*`` (design #15 §0.3 — sibling edge 0).
"""

from __future__ import annotations

from typing import ClassVar

from tos.iap._base import (
    AllFalseApprovalAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.iap.vocabulary import ApprovalResult, ConsumptionStatus, MaterialityVerdict

__all__ = [
    "ApprovalAuthorityEffect",
    "MaterialApprovalChange",
    "TradingApprovalPolicy",
    "ProposalApprovalRequest",
    "IndependentApprovalDecision",
    "ApprovalConsumptionRecord",
]


# ===========================================================================
# All-false authority effect (IAP-INV-005 / §7)
# ===========================================================================


class ApprovalAuthorityEffect(AllFalseApprovalAuthority):
    """Authority effect of Independent Approval — every flag false (IAP-INV-005 line 150 / §7).

    IAP-INV-005 line 150 verbatim: "Approval cannot mutate capacity, create headroom, issue
    authority, classify protection, transmit, clear HALT, or re-arm." The pure-model realization
    of ``approval != authority`` (ioc ``OrderConstructionAuthorityEffect`` / rcl
    ``RclAuthorityEffect`` ``authority.py:19`` / are ``AggregateRiskAuthorityEffect`` isomorph): a
    request's explicit no-authority declaration, and a ``APPROVE`` decision / consumption record,
    ``mutates_capacity`` nothing, ``creates_headroom`` nothing, ``issues_authority`` nothing,
    ``classifies_protection`` nothing, ``transmits`` nothing, ``clears_halt`` nothing, and
    ``rearms`` nothing. Any ``True`` value makes the artifact unconstructable (the full runtime
    "no live credential anywhere" enforcement is +Security EV-L2/L3, IAP-EV-006).
    """

    mutates_capacity: bool = False
    creates_headroom: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    transmits: bool = False
    clears_halt: bool = False
    rearms: bool = False


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class MaterialApprovalChange(FrozenModel):
    """Whether an approval-relevant change is material (ADR-002-023 §5.7 line 124-126).

    §5.7 line 126 verbatim: "Unknown materiality is material." ``verdict`` is an injected
    :class:`~tos.iap.vocabulary.MaterialityVerdict`; :meth:`resolved_material` treats ``UNKNOWN``
    — and ``MATERIAL`` — as material, so only a positively-``IMMATERIAL`` verdict is non-material
    (fail-closed, §4). Materiality is the entry condition for the invalidation closure (§5.4).
    """

    verdict: MaterialityVerdict = MaterialityVerdict.UNKNOWN

    def resolved_material(self) -> bool:
        """Whether the change is material — unknown materiality is material (§5.7 line 126)."""
        return self.verdict is not MaterialityVerdict.IMMATERIAL


# ===========================================================================
# Digest-bound append-only artifacts
# ===========================================================================


class TradingApprovalPolicy(IndependentIdArtifact):
    """An append-only, spg-governed Trading Approval Policy (ADR-002-023 §5.1 / §8).

    §8 line 232: "The policy is an immutable safety artifact under ADR-002-014" — a member of the
    spg Safety Configuration Bundle (``BundleMemberKind.TRADING_APPROVAL_POLICY``
    ``spg/vocabulary.py:180``); iap references it by digest scalar and **spg owns its governance /
    activation** (design #15 §3.5 — iap does not activate or govern it). A digest-bound
    :class:`~tos.iap._base.IndependentIdArtifact` with an independent ``policy_id`` (``id !=
    f(digest)``) so a same-id / different-bytes re-issuance is a detectable ``CRITICAL_CONFLICT``;
    a legitimate revalidation is a **new** generation (§2.1). Isomorphic to the ioc
    ``OrderConstructionPolicy`` (``ioc/records.py:259``).

    ``_REQUIRED_COVERED`` lists structural identity / generation / version only (design #15 §2.3);
    the concrete materiality / required-field declarations are Phase-0-injected and excluded so a
    policy is ISSUED-reachable under Phase-1 null bounds (a missing declaration fails closed at the
    consuming predicate). Non-transmitting, non-authorizing (design #15 §4.6).
    """

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    policy_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.1 / §8) ------------------------------
    policy_generation: int | None = None
    policy_version: str | None = None
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    policy_order: int | None = None


class ProposalApprovalRequest(IndependentIdArtifact):
    """An append-only, immutable Proposal Approval Request (ADR-002-023 §5.3 / §9).

    §5.3 line 108: an "immutable canonical request"; §9 line 240: bound by a "canonical digest".
    The full request contract iap owns (the -023 side; dsl ``Proposal`` is the upstream anchor,
    not a redefinition — §3.5). A digest-bound :class:`~tos.iap._base.IndependentIdArtifact` with
    an independent ``request_id`` (``id != f(digest)``, design #15 §0.4d): the proposer selects
    the id and a same-id / different-bytes substitution is a detectable
    ``classify_record_pair`` ``CRITICAL_CONFLICT`` (§18 line 419 request substitution). It binds
    every §9 upstream artifact — the dsl proposal, the capsule / snapshot, the ioc construction
    envelope / canonical command, the venue snapshot / admissibility decision, the brokercap
    profile, and the spg-governed policy — by **id + digest scalar** (§9 line 242-247), importing
    **none** of those siblings (design #15 §3.4, sibling edge 0).

    §9 line 255 verbatim: "The request is immutable. Any field change creates a new identity and
    restarts approval. Requests cannot be patched, partially refreshed, intersected, unioned, or
    widened." — realized by frozen + a fresh id per generation.

    ``_REQUIRED_COVERED`` lists structural identity / generation only; the §9 binding fields are
    Phase-1-null-reachable and excluded, so a request is ISSUED-reachable under Phase-1 null
    bounds. Their presence / non-wildcard / non-UNKNOWN completeness is the
    :func:`~tos.iap.predicates.request_is_complete` guard's job (§5.1), **not** required-covered
    (which would make an incomplete request unconstructable rather than a denial). ``action_class``
    / ``operating_mode`` default ``None`` (absent => incomplete), mirroring the template's
    fail-closed ``UNKNOWN`` default (§9 / §4.1). ``authority_declaration`` is the explicit
    no-authority declaration (§9 line 251; all-false).
    """

    _ID_FIELD: ClassVar[str] = "request_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("request_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_generation",
            "proposer_identity",
            # scope (§9 line 240-243)
            "environment",
            "account",
            "instrument",
            "action_class",
            "operating_mode",
            "direction",
            "position_effect",
            "quantity_basis",
            "required_scope_complete",
            # bound upstream artifacts — id + digest scalar (§9 line 242-247)
            "proposal_id",
            "proposal_digest",
            "decision_context_capsule_id",
            "decision_context_capsule_digest",
            "critical_input_snapshot_digest",
            "construction_envelope_id",
            "construction_envelope_digest",
            "canonical_broker_command_id",
            "canonical_broker_command_digest",
            "venue_snapshot_digest",
            "venue_admissibility_decision_digest",
            "broker_capability_profile_digest",
            "trading_approval_policy_id",
            "trading_approval_policy_generation",
            "trading_approval_policy_digest",
            # independent-facts / common-mode (§9 line 249)
            "required_independent_facts",
            "common_mode_declarations",
            # validity / consumption / invalidation (§9 line 250-251)
            "max_request_age_ms",
            "single_use",
            "exact_intent_only",
            "invalidation_set",
            "authority_declaration",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    request_id: str | None = None

    # ---- Layer-1 covered content (ADR §9) -------------------------------------
    request_generation: int | None = None
    proposer_identity: str | None = None
    # scope — absent / empty / wildcard / UNKNOWN action-class-or-mode => incomplete (§9 line 253).
    environment: str | None = None
    account: str | None = None
    instrument: str | None = None
    action_class: str | None = None
    operating_mode: str | None = None
    direction: str | None = None
    position_effect: str | None = None
    quantity_basis: str | None = None
    required_scope_complete: bool | None = None
    # bound upstream artifacts (id + digest scalar; sibling edge 0)
    proposal_id: str | None = None
    proposal_digest: str | None = None
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    critical_input_snapshot_digest: str | None = None
    construction_envelope_id: str | None = None
    construction_envelope_digest: str | None = None
    canonical_broker_command_id: str | None = None
    canonical_broker_command_digest: str | None = None
    venue_snapshot_digest: str | None = None
    venue_admissibility_decision_digest: str | None = None
    broker_capability_profile_digest: str | None = None
    trading_approval_policy_id: str | None = None
    trading_approval_policy_generation: int | None = None
    trading_approval_policy_digest: str | None = None
    # required independent facts + common-mode declarations (§9 line 249)
    required_independent_facts: tuple[str, ...] = ()
    common_mode_declarations: tuple[str, ...] = ()
    # validity / consumption / invalidation (injected opaque age; §9 line 250-251)
    max_request_age_ms: int | None = None
    single_use: bool | None = None
    exact_intent_only: bool | None = None
    invalidation_set: tuple[str, ...] = ()
    # explicit no-authority declaration (§9 line 251; all-false)
    authority_declaration: ApprovalAuthorityEffect = ApprovalAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    request_order: int | None = None


class IndependentApprovalDecision(IndependentIdArtifact):
    """An append-only, immutable Independent Approval Decision (ADR-002-023 §5.4 / §11).

    §5.4 line 114: an "immutable signed or strongly bound" decision; §11 line 291: bound by
    "signature or strong binding". A digest-bound :class:`~tos.iap._base.IndependentIdArtifact`
    with an independent ``decision_id`` **orthogonal to** the canonical digest (``id != f(digest)``,
    design #15 §0.4d) — so a same-id / different-bytes contradictory / substituted decision is a
    detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (§11 line 298 supersede; §18 line
    419 decision substitution; isomorphic to are ``AggregateRiskDecision`` ``records.py:451``).

    §11 line 298 verbatim: "A corrected or newer result is a new decision and explicitly
    supersedes the prior decision without erasing its evidence." — realized by a fresh id +
    ``supersedes_decision_id`` link, never an in-place edit. The ``APPROVE`` result **grants
    nothing** (``authority_effect`` all-false; §11 line 294 non-authorizing business gate). It
    binds the request (id + digest), the spg-governed policy (id + generation + digest), and the
    ioc ``ApprovedIntentContract`` approved-Intent-envelope (id + digest; §11 line 288) by
    **scalar** — importing none of those siblings (design #15 §3.4, sibling edge 0).

    **Forward-only** (§2.3): it carries no future aggregate-risk / authority / capability identity
    — later gates remain independently mandatory (§1 line 21).
    """

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("decision_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "request_id",
            "request_digest",
            "trading_approval_policy_id",
            "trading_approval_policy_generation",
            "trading_approval_policy_digest",
            "result",
            "reason_codes",
            "approved_intent_envelope_id",
            "approved_intent_envelope_digest",
            "max_decision_age_ms",
            "invalidation_generation",
            "supersedes_decision_id",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    decision_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.4 / §11) -----------------------------
    decision_generation: int | None = None
    request_id: str | None = None
    request_digest: str | None = None
    trading_approval_policy_id: str | None = None
    trading_approval_policy_generation: int | None = None
    trading_approval_policy_digest: str | None = None
    result: ApprovalResult | None = None
    reason_codes: tuple[str, ...] = ()
    # ioc ApprovedIntentContract approved-Intent-envelope ref — scalar seam (§11 line 288; §3.4).
    approved_intent_envelope_id: str | None = None
    approved_intent_envelope_digest: str | None = None
    # injected opaque validity age (§11 / §19); iap reads no clock.
    max_decision_age_ms: int | None = None
    invalidation_generation: int | None = None
    # §11 line 298 supersede link (a corrected / newer decision is a NEW record).
    supersedes_decision_id: str | None = None
    # §11 line 294 — an APPROVE decision grants no authority (all-false).
    authority_effect: ApprovalAuthorityEffect = ApprovalAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    decision_order: int | None = None


class ApprovalConsumptionRecord(IndependentIdArtifact):
    """An append-only, immutable Approval Consumption Record (ADR-002-023 §5.5 / §12).

    §5.5 line 118: "the Intent Registry's authoritative immutable proof" of single-use
    consumption. Owned by iap (the -023 side; §3.5). A digest-bound
    :class:`~tos.iap._base.IndependentIdArtifact` with an independent ``consumption_record_id``
    (``id != f(digest)``) so a same-id / different-bytes duplicate is a detectable
    ``classify_record_pair`` ``CRITICAL_CONFLICT`` (§12 duplicate consumption).

    §12 line 318: it binds the decision, the request, the Intent, the policy generation, the
    writer epoch, the transaction revision, the receipt-time marker, the invalidation generation,
    and the result. The ``intent_identity`` is the orthostate ``CompositeState.intent_identity``
    scalar (``orthostate/records.py:93``) — the PROPOSED->APPROVED **transition itself** is
    orthostate's (``intent_transition_allowed`` ``predicates.py:432``), never re-authored here; the
    runtime Intent Registry binds the two in one linearizable transaction (§3.4 (c)/§6.2). It
    **grants no downstream authority** (``authority_effect`` all-false; §12 line 318). The
    ``receipt_time_marker`` is an **injected opaque marker**, not a clock read (§3.4/§19).

    **Forward-only** (§2.3): no future authority / capability identity. The real linearizable
    serialization / writer-epoch fencing is +Security runtime (§12 line 316; IAP-EV-005) — this is
    the record substrate only.
    """

    _ID_FIELD: ClassVar[str] = "consumption_record_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("consumption_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "consumption_generation",
            "decision_id",
            "decision_digest",
            "request_id",
            "request_digest",
            "intent_identity",
            "policy_generation",
            "writer_epoch",
            "txn_revision",
            "receipt_time_marker",
            "invalidation_generation",
            "result",
            "consumption_status",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    consumption_record_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.5 / §12 line 318) --------------------
    consumption_generation: int | None = None
    decision_id: str | None = None
    decision_digest: str | None = None
    request_id: str | None = None
    request_digest: str | None = None
    # orthostate CompositeState.intent_identity scalar (orthostate/records.py:93; §3.4).
    intent_identity: str | None = None
    policy_generation: int | None = None
    writer_epoch: int | None = None
    txn_revision: int | None = None
    # injected opaque receipt marker — NOT a clock read (§3.4/§19).
    receipt_time_marker: str | None = None
    invalidation_generation: int | None = None
    result: ApprovalResult | None = None
    consumption_status: ConsumptionStatus | None = None
    # §12 line 318 — a consumption record grants no downstream authority (all-false).
    authority_effect: ApprovalAuthorityEffect = ApprovalAuthorityEffect()

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    consumption_order: int | None = None
