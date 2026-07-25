"""ioc value models + injected inputs + the five digest-bound artifacts (design #14 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True, extra="forbid")``
via :class:`~tos.ioc._base.FrozenModel`): ``extra="forbid"`` is the schema-level realization of
the §14 line 406 / §9 line 263 **unknown-top-level-field** rejection only. It does **not** cover
a duplicate / surplus *semantic axis* inside the ``axis_bindings`` tuple — that half of §14 line
406 "duplicate semantic fields ... are rejection" is enforced by the
:func:`~tos.ioc.predicates.command_conforms` structural guard (§5.1), not by ``extra="forbid"``.
Frozen is the record-level realization of append-only immutability (§5.7 Construction
Generation; §22 evidence) — there is **no** update / delete / mutate / transmit / sign method on
any model (design #14 §2.0/§4.6). Enum values / field names use the ADR §5-§21 terms verbatim
(spec terms = code terms; the erratum-defect-class seal, design #14 §2.2).

Every multiplier / price scale / quantity / limit is an **injected**
:data:`~tos.canonical.CanonicalDecimal` (design #14 §8 — hardcoded numeric 0) so ``1.0`` and
``1.00`` share one artifact digest and a NaN / infinity is **unconstructable** (§14 line 423);
a missing value fails closed at the consuming predicate.

``EconomicEffectEnvelope`` is the rcl :class:`~tos.rcl.CapacityVector` type (``vector.py:74``,
ADR-002-002 §6 — the type owner) via the single ``ioc -> rcl`` sibling edge (design #14 §0.4c):
the envelope is the exact coordinate rcl commits (``ReservationRecord.proposed_adverse_increment``)
and are consumes (MaximumCredibleCommandEffect), so dominance is sealed at the **type level** and
no reduction reducer is needed. ioc REUSES the type only — capacity commit / serialize stays
rcl-owned (§3.5; ioc mutates nothing).

The five digest-bound citizens are each an :class:`~tos.ioc._base.IndependentIdArtifact` with an
independent governance / issuance-assigned id (``id != f(digest)``, design #14 §3.1) so a same-id
/ different-bytes forged / re-issued / contradictory command / proof is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``. Each Construction Generation is an immutable
record; a legitimate recompilation is a **new** generation (a fresh id), never an in-place
mutation (design #14 §2.3). The command / proof are **forward-only** (§14 line 402): they carry
**no** future Live Authorization / capability / Commit Proof identity. The dsl ``Proposal`` is
``IdDerivedArtifact`` (content-addressed); ioc does **not** redefine it — it binds its digest by
scalar (design #14 §0.4d).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via ``tos.ioc._base``) + the rcl
``CapacityVector`` type only; no ``shared.*``, no other sibling ``tos.*`` (design #14 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.ioc._base import (
    AllFalseConstructionAuthority,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.ioc.vocabulary import ConformanceAxis, ConformanceResult
from tos.rcl import CapacityVector

__all__ = [
    "OrderConstructionAuthorityEffect",
    "AxisBinding",
    "MaterialCommandChange",
    "EconomicEffectEnvelope",
    "ApprovedIntentContract",
    "AuthorizedConstructionEnvelope",
    "OrderConstructionPolicy",
    "CanonicalBrokerCommand",
    "OrderConformanceProof",
]


#: ``EconomicEffectEnvelope`` IS the rcl :class:`~tos.rcl.CapacityVector` type (design #14
#: §0.4c / §5.5): the per-(scope, dimension) conservative effect vector rcl commits and are
#: projects, REUSED so dominance is sealed at the type level (no self-authored vector, no
#: reduction reducer). The single ``ioc -> rcl`` sibling edge exists only for this alias.
EconomicEffectEnvelope = CapacityVector


# ===========================================================================
# All-false authority effect (IOC-INV-011 / §7)
# ===========================================================================


class OrderConstructionAuthorityEffect(AllFalseConstructionAuthority):
    """Authority effect of order construction — every flag false (IOC-INV-011 / §7 line 219).

    IOC-INV-011 line 197 verbatim: "Order construction cannot approve, mutate capacity, issue
    authority, classify protection, choose permissive admissibility, transmit, clear HALT, or
    re-arm." The pure-model realization of ``construction != authority`` (rcl ``RclAuthorityEffect``
    ``authority.py:19-36`` / are ``AggregateRiskAuthorityEffect`` ``records.py:83`` isomorph): a
    ``CanonicalBrokerCommand`` / ``OrderConformanceProof`` ``approves`` nothing, ``mutates_capacity``
    nothing, ``issues_authority`` nothing, ``classifies_protection`` nothing, ``chooses_admissibility``
    nothing, ``transmits`` nothing, ``clears_halt`` nothing, and ``rearms`` nothing. Any ``True``
    value makes the artifact unconstructable (the full "no live credential / broker route anywhere"
    proof is +Security EV-L2/L3, IOC-EV-011).
    """

    approves: bool = False
    mutates_capacity: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    chooses_admissibility: bool = False
    transmits: bool = False
    clears_halt: bool = False
    rearms: bool = False


# ===========================================================================
# Value models (plain frozen)
# ===========================================================================


class AxisBinding(FrozenModel):
    """One conformance axis' bound value (design #14 §5.1 — the exact-match unit).

    A ``(axis, value)`` pair: the exact authorized / declared value on one
    :class:`~tos.ioc.vocabulary.ConformanceAxis`. ``value`` is the injected registry token
    (a Phase-0 INSTANCE supplies concrete per-broker values, §28 q3); a ``None`` value is
    UNKNOWN and never silently treated as present (fail-closed, §4.1). Order-significant tuples
    of these carry the identity / direction / price / mode axes an intent authorizes, an envelope
    permits, and a command declares — the structural analogue of the rcl
    :class:`~tos.rcl.CapacityComponent` (a distinct coordinate; §2.3 non-collapse).
    """

    axis: ConformanceAxis | None = None
    value: str | None = None


class MaterialCommandChange(FrozenModel):
    """Whether a command change is material (ADR-002-020 §5.8 line 145).

    §5.8 line 145 verbatim: "Unknown materiality is material." ``is_material`` is an injected
    ``bool | None``; :meth:`resolved_material` treats a ``None`` (unknown) — and a ``True`` — as
    material, so only a positively-``False`` materiality is non-material (fail-closed, §4).
    """

    is_material: bool | None = None

    def resolved_material(self) -> bool:
        """Whether the change is material — unknown materiality is material (§5.8 line 145)."""
        return self.is_material is not False


# ===========================================================================
# Digest-bound append-only artifacts
# ===========================================================================


class ApprovedIntentContract(IndependentIdArtifact):
    """An append-only, generation-immutable Approved Intent Contract (ADR-002-020 §5.1 / §8).

    The immutable Intent identity / version / digest / issuer / approval an order construction
    binds (§8 line 236). A digest-bound :class:`~tos.ioc._base.IndependentIdArtifact` with an
    independent ``intent_id`` (``id != f(digest)``, design #14 §0.4d) — the issuer / approval
    identity is a governance identity orthogonal to the digest, so a same-id / different-bytes
    forged / re-issued Intent is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. It
    is the **landing point** for the ADR-002-020 §8 field set that dsl ``Proposal`` deferred
    downstream (dsl ``proposal.py:6-9`` "an anchor, not a redefinition of ADR-002-020"): it binds
    the dsl ``Proposal`` by ``proposal_id`` + ``proposal_digest`` scalar (IOC-INV-001), and the
    capsule / snapshot / orthostate seams by digest / identity scalar — importing **none** of
    those siblings (design #14 §3.4). Independent Approval + immutable Intent Registration remain
    ADR-002-023 (IAP); this models the approved field set, not the registration (§3.5).

    ``_REQUIRED_COVERED`` lists structural identity / generation / version only (design #14 §2.3);
    the concrete authorized-axis values are Phase-0-injected and excluded so a contract is
    ISSUED-reachable under Phase-1 null bounds — a missing axis fails closed at the consuming
    predicate. Non-transmitting, non-authorizing (design #14 §4.6).
    """

    _ID_FIELD: ClassVar[str] = "intent_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "intent_generation",
        "intent_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_generation",
            "intent_version",
            "proposal_id",
            "proposal_digest",
            "decision_context_capsule_id",
            "decision_context_capsule_digest",
            "critical_input_snapshot_digest",
            "orthostate_intent_identity",
            "authorized_axis_bindings",
            "issuer_identity",
            "approval_identity",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    intent_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.1 / §8) ------------------------------
    intent_generation: int | None = None
    intent_version: str | None = None
    proposal_id: str | None = None
    proposal_digest: str | None = None
    decision_context_capsule_id: str | None = None
    decision_context_capsule_digest: str | None = None
    critical_input_snapshot_digest: str | None = None
    orthostate_intent_identity: str | None = None
    authorized_axis_bindings: tuple[AxisBinding, ...] = ()
    issuer_identity: str | None = None
    approval_identity: str | None = None
    authority_effect: OrderConstructionAuthorityEffect = (
        OrderConstructionAuthorityEffect()
    )

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    intent_order: int | None = None

    def axis_value(self, axis: ConformanceAxis) -> str | None:
        """Return the authorized value for ``axis`` (``None`` if absent / UNKNOWN)."""
        for binding in self.authorized_axis_bindings:
            if binding.axis == axis:
                return binding.value
        return None


class AuthorizedConstructionEnvelope(IndependentIdArtifact):
    """An append-only Authorized Construction Envelope (ADR-002-020 §5.3 / §8).

    The closed set of authorized per-axis values and permitted bounded transformations a command
    must fall inside (§8 line 243). §5.3 line 125 verbatim: "An absent or open-ended envelope
    permits no construction" — so an envelope with **no** authorized axis bindings is the ∅ case
    that denies construction (design #14 §4.7). A digest-bound
    :class:`~tos.ioc._base.IndependentIdArtifact`; a legitimate re-scope is a new generation, never
    an in-place mutation (design #14 §2.3).

    ``_REQUIRED_COVERED`` lists structural identity / generation only; the concrete authorized-axis
    values are Phase-0-injected and excluded (a missing bound fails closed downstream).
    """

    _ID_FIELD: ClassVar[str] = "envelope_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("envelope_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "envelope_generation",
            "authorized_axis_bindings",
            "policy_binding_id",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    envelope_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.3 / §8) ------------------------------
    envelope_generation: int | None = None
    authorized_axis_bindings: tuple[AxisBinding, ...] = ()
    policy_binding_id: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    envelope_order: int | None = None

    def authorized_axes(self) -> dict[ConformanceAxis, str | None]:
        """The closed set of authorized ``{axis: value}`` (empty => open/absent => denial)."""
        return {
            binding.axis: binding.value
            for binding in self.authorized_axis_bindings
            if binding.axis is not None
        }


class OrderConstructionPolicy(IndependentIdArtifact):
    """An append-only, spg-governed Order Construction Policy (ADR-002-020 §5.2 / §9).

    §5.2 line 121: an "immutable, authenticated, separately governed artifact" — a member of the
    spg Safety Configuration Bundle (§7 line 217); ioc references it by digest and spg owns its
    governance (design #14 §3.5). A digest-bound :class:`~tos.ioc._base.IndependentIdArtifact`
    with an independent ``policy_id`` so a same-id / different-bytes re-issuance is a detectable
    ``CRITICAL_CONFLICT``; a legitimate revalidation is a **new** generation (design #14 §2.3).

    ``_REQUIRED_COVERED`` lists structural identity / generation / version only; the concrete
    per-broker mapping / registry values are Phase-0-injected and excluded (design #14 §2.3/§8).
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

    # ---- Layer-1 covered content (ADR §5.2 / §9) ------------------------------
    policy_generation: int | None = None
    policy_version: str | None = None
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    policy_order: int | None = None


class CanonicalBrokerCommand(IndependentIdArtifact):
    """An append-only Canonical Broker Command (ADR-002-020 §5.4 / §14).

    §5.4 line 129 verbatim: "one canonical representation and digest, complete field presence,
    explicit units and defaults, exact proposal lineage". §14 line 353: "command identity ... and
    digest". A digest-bound :class:`~tos.ioc._base.IndependentIdArtifact` — ``command_id`` is
    orthogonal to the canonical digest, so a same-id / different-bytes forged command is a
    detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``. It carries the exact declared
    per-axis values (the digest-preimage broker mutation fields), the exact proposal lineage
    (``proposal_id`` + ``proposal_digest``), and **explicit non-authorizing flags**
    (``authority_effect`` all-false, §5.4 line 129 / §14 line 359). Unknown top-level fields are
    rejected by ``extra="forbid"``; a duplicate / surplus semantic axis inside ``axis_bindings``
    is rejected by the :func:`~tos.ioc.predicates.command_conforms` structural guard (§5.1 / §14
    line 406), **not** by ``extra="forbid"``. **Forward-only**: it carries no future Live
    Authorization / capability identity (§14 line 402).

    ``_REQUIRED_COVERED`` lists structural identity / generation only; the concrete axis values are
    Phase-0-injected and excluded so a command is ISSUED-reachable under Phase-1 null bounds.
    """

    _ID_FIELD: ClassVar[str] = "command_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("command_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "command_generation",
            "proposal_id",
            "proposal_digest",
            "axis_bindings",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    command_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.4 / §14) -----------------------------
    command_generation: int | None = None
    proposal_id: str | None = None
    proposal_digest: str | None = None
    axis_bindings: tuple[AxisBinding, ...] = ()
    # §5.4 line 129 / §14 line 359 — explicit non-authorizing flags (all-false).
    authority_effect: OrderConstructionAuthorityEffect = (
        OrderConstructionAuthorityEffect()
    )

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    command_order: int | None = None

    def axis_value(self, axis: ConformanceAxis) -> str | None:
        """Return the declared value for ``axis`` (``None`` if absent / UNKNOWN)."""
        for binding in self.axis_bindings:
            if binding.axis == axis:
                return binding.value
        return None


class OrderConformanceProof(IndependentIdArtifact):
    """An append-only, non-authorizing Order Conformance Proof (ADR-002-020 §5.6 / §14).

    §5.6 line 137: an "immutable non-authorizing artifact"; §14 line 365: a proof with
    "deterministic input and output digests" and (line 372) a final
    :class:`~tos.ioc.vocabulary.ConformanceResult`. A digest-bound
    :class:`~tos.ioc._base.IndependentIdArtifact` binding, by **digest scalar** (design #14 §3.4),
    the policy / envelope / command / economic-effect digests, the deterministic input / output
    digests, the ADR-002-021 are ``AggregateRiskDecision`` content ref (id / generation / digest),
    the venue Order Admissibility Decision digest, and the brokercap ``BrokerCapabilityProfile``
    digest — importing **none** of those siblings. Its ``authority_effect`` is all-false: a
    ``CONFORMANT`` result "grants no approval or authority ... usable only as one current input"
    (§14 line 376).

    ``required_authority_scope`` is mandatory / restrictive (§14 line 374): a missing / empty /
    unknown scope means ``UNKNOWN`` / ``NON_CONFORMANT`` at the consuming gate, **never** zero /
    wildcard / unconstrained authority (design #14 §4.7). ``_REQUIRED_COVERED`` lists structural
    identity / generation only; the digests are Phase-1-null-reachable and excluded.
    """

    _ID_FIELD: ClassVar[str] = "proof_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("proof_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "proof_generation",
            "policy_digest",
            "envelope_digest",
            "command_digest",
            "effect_digest",
            "input_digest",
            "output_digest",
            "aggregate_risk_decision_id",
            "aggregate_risk_decision_generation",
            "aggregate_risk_decision_digest",
            "venue_admissibility_decision_digest",
            "broker_capability_profile_digest",
            "required_authority_scope",
            "conformance_result",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    proof_id: str | None = None

    # ---- Layer-1 covered content (ADR §5.6 / §14) -----------------------------
    proof_generation: int | None = None
    policy_digest: str | None = None
    envelope_digest: str | None = None
    command_digest: str | None = None
    effect_digest: str | None = None
    input_digest: str | None = None
    output_digest: str | None = None
    # ADR-002-021 are decision content ref — digest scalar seam (§14 line 369; §3.4).
    aggregate_risk_decision_id: str | None = None
    aggregate_risk_decision_generation: int | None = None
    aggregate_risk_decision_digest: str | None = None
    venue_admissibility_decision_digest: str | None = None
    broker_capability_profile_digest: str | None = None
    # §14 line 374 — mandatory restrictive scope (missing/empty => UNKNOWN, never wildcard).
    required_authority_scope: tuple[str, ...] = ()
    conformance_result: ConformanceResult | None = None
    # §14 line 376 — a CONFORMANT proof grants no authority (all-false).
    authority_effect: OrderConstructionAuthorityEffect = (
        OrderConstructionAuthorityEffect()
    )

    # ---- ledger-placement (self-excluded from the digest, §2.3/§3.2) ----------
    proof_order: int | None = None
