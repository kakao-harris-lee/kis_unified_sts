"""Live Authorization ledger-citizen records (ADR-002-007 §7, §8, §13, §18).

Every record is a digest-bound :class:`~tos.liveauth._base.IndependentIdArtifact` with
an independent, service-assigned identity (``id != f(digest)``, design §3.1) so an
append-only ledger can represent and detect a same-id / different-content forgery /
replay (§8.3 line 250-252; REARM-AC-004/012) as a ``classify_record_pair``
CRITICAL_CONFLICT. There is **no** update / delete / mutate method on any record — a
lifecycle change is expressed by appending a new :class:`LiveAuthorizationTransitionRecord`
(append-only, §2.0/§18). ``_REQUIRED_COVERED`` lists **structural identity / scope /
epoch / version** fields only — numeric bounds (``maximum_validity`` / the constraint
layering) are excluded so an authorization is ISSUED-reachable under Phase-1 null profile
bounds (§2.2); a missing numeric claim fails closed at the consuming validity /
layering predicate instead (§5.2/§6.1).

**Coordinate non-collapse (design §2.2/§4.4):** the :class:`LiveAuthorization` record
carries only its **immutable §7 claims** in the covered digest preimage; the mutable
``LiveAuthorizationState`` (REQUESTED..terminal) is deliberately **NOT** covered, so a
legitimate lifecycle transition (e.g. ACTIVE → SUSPENDED) does not change the digest and
is never mis-flagged as a same-id / different-bytes CRITICAL_CONFLICT. The current state
is injected into the ``is_live`` / continuous-validity predicates (§5.1/§5.4), and each
transition is recorded append-only by a separate transition record (§2.3).

Cross-ADR artifacts (Hard Safety Envelope / Runtime Safety Profile = ADR-002-014;
Recovery = ADR-002-017; Decision Context Capsule = ADR-002-018; RCL capacity) are
referenced only as **scalars** (``tos.rcl`` / ``tos.capsule`` / ``tos.evidence`` are NOT
imported, §0.3/§3.3).

Spec terms = code terms (boundary design #1 §2.4).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.liveauth._base``) +
``tos.liveauth`` only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.liveauth._base import IndependentIdArtifact, LiveAuthorizationEffect
from tos.liveauth.state import LimitLayering, LiveAuthorizationScope
from tos.liveauth.vocabulary import LiveAuthorizationState, ReArmPathKind


class LiveAuthorization(IndependentIdArtifact):
    """Live Authorization (ADR-002-007 §4.5 line 102-104; §7 line 186-220; §8 line 224-252).

    ``authorization_id`` (+ the non-covered ``authorization_version``) is independent of
    ``canonical_digest`` (§3.1) so a same-id / different-bytes authorization is a
    detectable Critical conflict (§8.3 replay / forgery). ``authority_effect`` is
    all-false: issuing or holding an authorization is **not** live — ``ACTIVE`` requires
    every continuous-validity condition to *currently* pass and is not inferred from the
    artifact being issued (§8.1 line 242-244). The numeric claims (``maximum_validity`` /
    ``maximum_quantity_notional_risk_margin_concentration_rate_constraints``) are covered
    but NOT required for ISSUED (§2.2) — they are enforced fail-closed at consumption by
    ``continuous_validity`` / ``layering_within_bounds`` (§5.2/§6.1). The many cross-ADR
    version / digest bindings are scalar-reference blocks (ADR-002-014/017/018/029/030
    owned; ``tos`` does not author them). The mutable ``LiveAuthorizationState`` is NOT a
    field here — it is injected into the predicates and recorded by the transition record.
    """

    _ID_FIELD: ClassVar[str] = "authorization_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "issuer_identity",
        "authority_domain",
        "safety_authority_epoch",
        "live_authorization_scope",
        "hard_safety_envelope_version",
        "runtime_safety_profile_version",
        "broker_capability_profile_version",
        "issue_sequence",
        "activation_condition",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # identification / issuance (§7 line 188-214)
            "issuer_identity",
            "approval_record_identity",
            "issue_sequence",
            "activation_condition",
            "maximum_validity",
            # epoch / scope (§7)
            "authority_domain",
            "safety_authority_epoch",
            "live_authorization_scope",
            "maximum_quantity_notional_risk_margin_concentration_rate_constraints",
            # version bindings (scalar references, §7 line 202-210)
            "hard_safety_envelope_version",
            "runtime_safety_profile_version",
            "broker_capability_profile_version",
            "broker_conformance_class",
            "software_artifact_digest",
            "configuration_digest",
            "deployment_provenance",
            "recovery_evidence_package_identity",
            "recovery_generation",
            "decision_context_capsule_identity",
            "context_generation",
            # invalidation / residual (§9 line 282; §7)
            "revocation_generation",
            "residual_risk_approvals",
            "restricted_scope_conditions",
            "integrity_evidence",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    authorization_id: str | None = None
    authorization_version: str | None = None

    # ---- Layer-1 covered claims (§7 immutable claims) --------------------------
    issuer_identity: str | None = None
    approval_record_identity: str | None = None
    issue_sequence: int | None = None
    activation_condition: str | None = None
    maximum_validity: int | None = None
    authority_domain: str | None = None
    safety_authority_epoch: int | None = None
    live_authorization_scope: LiveAuthorizationScope | None = None
    maximum_quantity_notional_risk_margin_concentration_rate_constraints: (
        LimitLayering | None
    ) = None
    hard_safety_envelope_version: str | None = None
    runtime_safety_profile_version: str | None = None
    broker_capability_profile_version: str | None = None
    broker_conformance_class: str | None = None
    software_artifact_digest: str | None = None
    configuration_digest: str | None = None
    deployment_provenance: str | None = None
    recovery_evidence_package_identity: str | None = None
    recovery_generation: int | None = None
    decision_context_capsule_identity: str | None = None
    context_generation: int | None = None
    revocation_generation: int | None = None
    residual_risk_approvals: tuple[str, ...] = ()
    restricted_scope_conditions: str | None = None
    integrity_evidence: str | None = None
    authority_effect: LiveAuthorizationEffect = LiveAuthorizationEffect()


class LiveAuthorizationTransitionRecord(IndependentIdArtifact):
    """Live Authorization Transition Record (ADR-002-007 §8 line 224-252; §18 line 566).

    An element of the append-only audit sequence — one per Live Authorization lifecycle
    transition (§18 "every Live Authorization lifecycle transition"; REARM-EV-012 replay
    substrate). ``from_state`` / ``to_state`` are the ``LiveAuthorizationState`` endpoints;
    transition **legality** is judged by the ``live_authorization_transition_allowed``
    predicate (§5.4), never by the record. ``restrictive_or_revocation_generation`` is a
    monotonically-ordered generation (§9 line 282); the model provides no decrease / reuse
    operation, but the actual across-record serialization / monotonicity is runtime (§0.2)
    — a single record carries no old/new pair to compare in place.
    """

    _ID_FIELD: ClassVar[str] = "transition_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "authorization_id",
        "from_state",
        "to_state",
        "transition_reason",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "authorization_id",
            "from_state",
            "to_state",
            "transition_reason",
            "restrictive_or_revocation_generation",
            "evidence_reference",
            "operator_context",
        }
    )

    transition_id: str | None = None

    authorization_id: str | None = None
    from_state: LiveAuthorizationState | None = None
    to_state: LiveAuthorizationState | None = None
    transition_reason: str | None = None
    restrictive_or_revocation_generation: int | None = None
    evidence_reference: str | None = None
    operator_context: str | None = None


class ReArmApprovalRecord(IndependentIdArtifact):
    """Re-arm Approval Record (ADR-002-007 §4.4 line 98-100; §13 line 422-435; §18).

    ``approver_principals`` are the human dual-control principals (identity coordinates
    only — §13 authentication is ADR-002-015 runtime). ``authority_effect`` is all-false:
    **approval ≠ authorization** (§5 SoD table line 126 "Assemble recovery readiness …
    Prohibited: Issuing Live Authorization or approving itself"; §11 readiness ≠
    authority). ``requested_scope``, the evidence-package / capsule scalars, and the
    ``dual_control_path`` are covered, so — per §13 line 431-432 — changed evidence or
    scope changes the digest and invalidates a prior approval (a same-approval-id /
    different-scope pair is a ``classify_record_pair`` CRITICAL_CONFLICT).
    """

    _ID_FIELD: ClassVar[str] = "approval_record_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "requested_scope",
        "dual_control_path",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "approver_principals",
            "requested_scope",
            "reason",
            "residual_risk_acknowledgements",
            "recovery_evidence_package_identity",
            "decision_context_capsule_identity",
            "dual_control_path",
            "authority_effect",
        }
    )

    approval_record_id: str | None = None

    approver_principals: tuple[str, ...] = ()
    requested_scope: LiveAuthorizationScope | None = None
    reason: str | None = None
    residual_risk_acknowledgements: tuple[str, ...] = ()
    recovery_evidence_package_identity: str | None = None
    decision_context_capsule_identity: str | None = None
    dual_control_path: ReArmPathKind | None = None
    authority_effect: LiveAuthorizationEffect = LiveAuthorizationEffect()
