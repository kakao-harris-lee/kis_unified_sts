"""Failure-Domain Allocation Matrix + Isolation Claim record shapes (design #27 §5).

Two **document-level** frozen record shapes transcribed 1:1 from ADR-002-009 §5 line 116-132
(the matrix row) and §4.4 line 96 (the isolation claim), plus the §2.2 all-false authority
block they both carry.

**This is not a runtime matrix** (design #27 §0.2): allocation, common-mode analysis,
enforcement-point wiring, and containment measurement belong to the approved deployment profile
(ADR §22 gate 1) and the runtime. Every artifact is a pydantic v2 frozen model
(``ConfigDict(frozen=True, extra="forbid")`` via :class:`~tos.failuredomain._base.FrozenModel`):
frozen is the record-level realization of append-only — there is **no** update / delete / mutate
method on any model (design #4 §2.0 discipline, inherited).

**Q1 — plain frozen, not digest-bound** (design #27 §0.4b/§3.1): there is no Phase-1 runtime
digest consumer and no forgery-detection path for a matrix row, so ``DigestBoundArtifact`` /
``IndependentIdArtifact`` / ``IdDerivedArtifact`` are **not** adopted and matrix identity /
digest binding / registry stay deferred to the deployment-profile approval and the evidence
layer.

**No number lives here** (design #27 §0.2/§7): the blast-radius ceiling, the broker-session
budget, the partition bound, and the detection/containment bounds are all **injected slots**
whose values are Phase-0 Bounds-Approver business (``B_failure_domain_detect`` /
``B_failure_domain_contain``, both currently ``null`` in VERIFICATION-PROFILE-002 — design #27
§7); ``tos.failuredomain`` hardcodes none of them and authors **no new VP-002 key**.

Regime tag: **EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.**

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via :mod:`tos.failuredomain._base`) +
``tos.failuredomain`` only; no ``shared.*``, no sibling ``tos.*`` (design #27 §0.3).
"""

from __future__ import annotations

from tos.failuredomain._base import AllFalseFailureDomainAuthority, FrozenModel
from tos.failuredomain.state import SafetyCellScope
from tos.failuredomain.vocabulary import (
    ExplicitlyAnalyzedEmpty,
    FailureBehaviorKind,
    FailureDomainKind,
    IsolationKind,
)

__all__ = [
    "FailureDomainAllocationEntry",
    "FailureDomainAuthorityEffect",
    "IsolationClaim",
]


class FailureDomainAuthorityEffect(AllFalseFailureDomainAuthority):
    """The all-false authority block both failure-domain records carry (design #27 §2.2).

    ADR-002-009 §1 line 15: "**Separate processes, services, containers, nodes, or names do not
    by themselves prove isolation.**" §1 line 32: an isolation property that cannot be
    positively established "SHALL NOT be converted into permission by redundancy count,
    operator confidence, a healthy dashboard, replay capability, or an audit trail." §1 line 30:
    "The Broker Adapter/Egress Gateway remains the final transmission enforcement point. The
    Risk Capacity Ledger remains the sole capacity mutation and serialization authority."

    Each flag is therefore pinned ``False`` and a ``True`` makes the record unconstructable
    (:meth:`~tos.failuredomain._base.AllFalseFailureDomainAuthority._all_authority_false`):

    * ``grants_authority`` — a matrix row / cell scope / claim grants no safety authority
      (owner: ``tos.authority``, design #27 §3.5 §6.1);
    * ``releases_capacity`` — it releases no capacity (owner: ``tos.rcl``, §6.2 — RCL-only
      mutation, ADR §1 line 30);
    * ``transmits_to_broker`` — it transmits nothing (``tos`` is non-transmitting by
      construction, boundary design #1 §4; owner: ``tos.egress``, §6.3);
    * ``establishes_permission`` — it establishes no permission (ADR §1 line 32, §8.2 "absence
      of a deny event is not proof of permission");
    * ``proves_isolation`` — a filled coordinate proves no isolation (ADR §1 line 15, §4.3 line
      92 "A cell boundary is not proven merely by labels or namespaces"; the positive proof is
      sbr ``IsolationFacts.all_proven``, §3.5-1);
    * ``enforces_containment`` — it enforces nothing; the fences, partitions, and credential
      isolation mechanisms are the siblings' and the runtime's (design #27 §0.2, and the six
      distinct sibling hard-fence owners in §3.5-3).
    """

    grants_authority: bool = False
    releases_capacity: bool = False
    transmits_to_broker: bool = False
    establishes_permission: bool = False
    proves_isolation: bool = False
    enforces_containment: bool = False


class IsolationClaim(FrozenModel):
    """The ADR §4.4 line 96 versioned isolation claim — five fields, verbatim.

    ADR-002-009 §4.4 (heading line 94) line 96: "A versioned claim that one failure cannot defeat specified
    controls together. Every claim SHALL state **assumptions, excluded common modes,
    enforcement mechanisms, verification cases, and residual risk**."

    A claim is **general and cross-domain**. It is *not* the sbr recovery-readiness proof:
    ``IsolationFacts`` (ADR-002-017 §17 line 438-445) is an eight-axis positive proof of
    *recovery* isolation with a different grain and a different scope, and it is **never
    re-authored here** (design #27 §3.5-1, the largest proposition-identity trap in this
    package). The relationship is a **reference**: ``verification_cases`` may carry the token
    ``"sbr.IsolationFacts.all_proven"`` (Q2, design #27 §9.4-1) — a bare string naming the
    owner of the executed proof, never an imported sbr type and never a re-implementation.

    Whether the five fields are positively present is decided **only** by
    :func:`~tos.failuredomain.predicates.unproven_isolation_is_common_mode`; there is
    deliberately **no** ``independent`` / ``established`` boolean on this record, so an
    independence assertion cannot be forged by setting a flag.

    Attributes:
        assumptions: The assumptions the claim rests on. ``None`` / bare ``∅`` / a blank
            entry => not positively stated => common-mode.
        excluded_common_modes: The common modes the claim positively excludes. This is the one
            field where a *positively analysed* empty result is meaningful, so it additionally
            accepts the :class:`~tos.failuredomain.vocabulary.ExplicitlyAnalyzedEmpty` marker:
            ``None`` and a bare ``frozenset()`` are **not** positively present (ADR §5 line 130
            "Unknown, untested, or undocumented sharing SHALL be recorded as common-mode"),
            while ``ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY`` is (design #27 §4.1,
            ``∅`` both ways).
        enforcement_mechanisms: The non-bypassable enforcement points that hold the claim up.
            The mechanisms themselves are sibling / runtime owned (design #27 §3.5); this field
            only names them.
        verification_cases: The executed verification cases, as **reference tokens** (e.g.
            ``"sbr.IsolationFacts.all_proven"``). Registration is not execution (ADR §17 line
            394) — naming a case here closes no evidence item.
        residual_risk: The remaining risk statement. A blank or whitespace-only string is not a
            statement (design #27 §4.1 polarity — no falsy / blank forgery).
        authority_effect: The §2.2 all-false authority block. A claim grants nothing.
    """

    assumptions: frozenset[str] | None = None
    excluded_common_modes: ExplicitlyAnalyzedEmpty | frozenset[str] | None = None
    enforcement_mechanisms: frozenset[str] | None = None
    verification_cases: frozenset[str] | None = None
    residual_risk: str | None = None
    authority_effect: FailureDomainAuthorityEffect = FailureDomainAuthorityEffect()


class FailureDomainAllocationEntry(FrozenModel):
    """One Failure-Domain Allocation Matrix row (ADR §5 line 116-132 — 11 fields + §2.1E).

    ADR-002-009 §5 line 112: "The canonical matrix SHALL be versioned, reviewed with every
    topology or authority change, and bound to the Runtime Safety Profile and Live
    Authorization." Line 116: "For each component and shared dependency it SHALL record at
    least:" — the eleven fields transcribed below in ADR table order — plus the RFC-002 §24.1
    line 1910 mandated ``physical/logical/common-mode classification`` as
    :attr:`isolation_kind` (design #27 §2.1E, M2).

    **Structurally un-forgeable independence** (ADR §5 line 130): "Unknown, untested, or
    undocumented sharing SHALL be recorded as common-mode. It SHALL NOT be recorded as
    independent with an explanatory footnote." This row therefore carries **no** ``independent``
    / ``footnote`` / ``exception`` field at all — there is no place to write a
    footnote-qualified independence assertion. The only route to independence is
    :func:`~tos.failuredomain.predicates.unproven_isolation_is_common_mode` returning ``False``
    for a claim whose five §4.4 fields are all positively present.

    Attributes:
        authority_or_state: ADR §5 line 118 — "Exact authority, capacity, knowledge, or
            economic state affected".
        safety_cell: ADR §5 line 119 — "Account, portfolio, broker, environment, and egress
            scope"; carried as the full ADR §4.3 seven-scope
            :class:`~tos.failuredomain.state.SafetyCellScope`.
        failure_domains: ADR §5 line 120 — the domains this component occupies, drawn from the
            closed :class:`~tos.failuredomain.vocabulary.FailureDomainKind` taxonomy (ADR §4.1
            18 + the RFC-002 §24.1 supply-chain floor 4).
        shared_dependencies: ADR §5 line 121 — "Every dependency shared with a purportedly
            independent control". ADR §4.2 line 86 fixes the seven common-mode backdrops a
            shared dependency may collapse onto: "Different endpoints, replicas, or service
            names backed by one **administrator, credential, database, network, clock, library,
            or broker resource** remain common-mode for that dependency." (The time-source axis
            instance of the same idea is time ``common_mode_group`` — sibling-owned, design #27
            §3.5 §12.)
        failure_behavior: ADR §5 line 122 — one of the nine
            :class:`~tos.failuredomain.vocabulary.FailureBehaviorKind` values.
        unsafe_consequence: ADR §5 line 123 — "Authority, capacity, quantity, protection, or
            transmission consequence".
        prevention: ADR §5 line 124 — "Non-bypassable enforcement point and fence", as an
            **injected sibling owner token** (see
            :data:`~tos.failuredomain.vocabulary.SIBLING_OWNER_TOKENS`). This package points at
            the owner and authors no enforcement.
        detection_and_containment: ADR §5 line 125 — "Observable signal and approved upper
            bound". The **bound is injected**: its VP-002 keys ``B_failure_domain_detect`` /
            ``B_failure_domain_contain`` both hold ``null`` pending Phase-0 approval (design #27
            §7), and no number is written here.
        recovery: ADR §5 line 126 — "Required reconciliation, epoch change, and re-arm barrier",
            again an injected owner token (spg / authority / sbr own the mechanisms).
        evidence: ADR §5 line 127 — "Acceptance case and registered evidence identifier". ADR
            §17 line 394: "Registration is not execution" — an id here closes no FD-EV.
        residual_risk: ADR §5 line 128 — "Remaining common mode and approved owner".
        isolation_kind: RFC-002 §24.1 line 1910 physical/logical/common-mode classification.
            ``None`` (unclassified) reads **fail-closed** as
            :attr:`~tos.failuredomain.vocabulary.IsolationKind.COMMON_MODE` — see
            :meth:`effective_isolation_kind`.
        authority_effect: The §2.2 all-false authority block. A matrix row grants nothing.
    """

    authority_or_state: str | None = None
    safety_cell: SafetyCellScope = SafetyCellScope()
    failure_domains: frozenset[FailureDomainKind] = frozenset()
    shared_dependencies: frozenset[str] = frozenset()
    failure_behavior: FailureBehaviorKind | None = None
    unsafe_consequence: str | None = None
    prevention: str | None = None
    detection_and_containment: str | None = None
    recovery: str | None = None
    evidence: str | None = None
    residual_risk: str | None = None
    isolation_kind: IsolationKind | None = None
    authority_effect: FailureDomainAuthorityEffect = FailureDomainAuthorityEffect()

    def effective_isolation_kind(self) -> IsolationKind:
        """The fail-closed reading of :attr:`isolation_kind` (design #27 §2.1E).

        An **unclassified** dependency is never treated as physically or logically isolated:
        RFC-002 §24.1 line 1910 makes the physical/logical/common-mode classification mandatory
        for every shared dependency, and ADR §5 line 130 requires unknown / untested /
        undocumented sharing to be recorded as common-mode. ``None`` therefore reads as
        :attr:`~tos.failuredomain.vocabulary.IsolationKind.COMMON_MODE`, never as
        ``PHYSICAL`` / ``LOGICAL``.

        Returns:
            The declared kind, or ``COMMON_MODE`` when none was declared.
        """
        if self.isolation_kind is None:
            return IsolationKind.COMMON_MODE
        return self.isolation_kind
