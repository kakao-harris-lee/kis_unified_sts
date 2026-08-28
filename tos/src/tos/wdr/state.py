"""wdr injected inputs + value models + generation-order ordering REUSE (design #26 §2.1/§3.2).

Two roles:

* **value / injected input models (design #26 §2.1)** — the exact scope tuple
  (:class:`DeviationScope` — §5.7, every §5.7 line 128 dimension as a ``str | None`` coordinate), the
  compensating control (:class:`CompensatingControl` — §5.5/§11), the dependency closure
  (:class:`DeviationDependencyClosure` — §5.10, the affected closure set), the non-waivable boundary
  anchor (:class:`NonWaivableBoundaryAnchor` — §5.6/§8, the 15-item union anchor), the waived
  verification-item view (:class:`WaivedEvidenceItem` — §19), the gate-separation ladder
  (:class:`GateSeparationLadder` — §26 AC-012, six distinct explicit states), and the §8 classification
  input (:class:`DeviationClassification`). Every one is a **pydantic v2 frozen model**
  (``frozen=True, extra="forbid"`` via :class:`~tos.wdr._base.FrozenModel`): ``extra="forbid"`` is the
  schema-level "omission is restrictive" and frozen is the append-only realization — there is **no**
  update / delete / mutate method on any model (design #26 §2.3/§4.1).

* **generation order (design #26 §3.2 ordering REUSE)** — :func:`deviation_generation_advances` REUSES
  ``tos.ordering.compare_order`` (no re-authored order) for the Deviation Generation monotonic fence
  (§5.8 / §14 line 386 "a newer generation SHALL restrict future authority monotonically") and the
  predecessor floor (§10 line 284). wdr owns the fence *meaning* (a newer Deviation Generation retires
  a predecessor decision / active set); ordering only carries the monotonic order. **A wall clock never
  orders — wdr reads no clock**: a Deviation Generation is an ordering identity, not wall-clock time
  (§3.2/§0.4h), so this package is clock-free (``MAX_deviation_*_ms`` wall-clock age is a secondary
  +Security / INSTANCE bound, §8).

**Numeric-bound freedom (design #26 §8; ADR §8 non-scope).** wdr carries no numeric size / duration /
threshold constant: every such value is an **injected** opaque scalar (null in Phase 1, fail-closed at
the consuming predicate). The **wildcard sentinel set** (:data:`WILDCARD_SENTINELS`) plus the
:data:`WILDCARD_METACHARACTERS` glob / regex / SQL-``LIKE`` metacharacter set are a structural
placeholder catalogue (``*`` / ``latest`` / ...), never a numeric bound (§10 line 299 "missing,
wildcard, inferred, stale, conflicting ... fields is ineligible").

**Wildcard detection is a best-effort, non-exhaustive value-model denylist (honesty — #25 MAJOR-1
lesson).** :func:`is_wildcard_value` normalizes (``strip().casefold()``) and catches catalogued
sentinels (case variants included) plus common metacharacters only. It is authored **locally** here
(no rlp import — sibling edge 0, design #26 §3.3/§3.4). The §10 *patched* / *widened* / *stale* /
*conflicting* axes, and any novel wildcard notation outside this catalogue / metacharacter set, are
**not** value-model-decidable — they are owned by +Security and the runtime (carried separately as the
negative-polarity ``scope_patched`` / ``scope_widened`` / ``scope_stale`` / ``scope_conflicting``
request flags, §4.3). This module does **not** guarantee the full §10 property; it provides a
structural first line only.

**Injected-verdict discipline (design #26 §1/§3.5 over-realization + duplication boundary).** Every
sibling owner's produced verdict / generation / digest is an **injected** coordinate: wdr
does **not** re-decide any owner's business content (spg Hard Safety Envelope / ``residual_risk_ceiling``
/ break-before-make, hag effective-principal / quorum, rcl ``CapacityVector`` / worst-credible-effect,
egress final-egress enforcement, cur Safety Currentness Vector, evidence custody / causal-chain,
liveauth Live Authorization, iap single-use consumption shape, authority epoch / non-revival, -027
incident generation) — it consumes the produced fact and judges only the boundary / scope / UNKNOWN /
status / set / gate structure (§3.5).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.wdr.*`` only; no ``shared.*``, no other
sibling ``tos.*`` (design #26 §0.3). Clock-free.
"""

from __future__ import annotations

from typing import ClassVar

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.wdr._base import AllFalseDeviationAuthority, FrozenModel
from tos.wdr.vocabulary import (
    CompensatingControlKind,
    NonWaivableClassification,
    ScopeDimension,
    WaivedEvidenceStatus,
)

__all__ = [
    "WILDCARD_SENTINELS",
    "WILDCARD_METACHARACTERS",
    "is_wildcard_value",
    "DeviationScope",
    "CompensatingControl",
    "DeviationDependencyClosure",
    "NonWaivableBoundaryAnchor",
    "WaivedEvidenceItem",
    "GateSeparationLadder",
    "DeviationClassification",
    "deviation_generation_advances",
]

#: Forbidden scope-placeholder sentinels a scope coordinate may never use (§10 line 299 / §5.7 line
#: 128). A scope dimension bearing any of these — matched case-insensitively via
#: :func:`is_wildcard_value` — is **not** an exact reduced scope: it is a wildcard / inferred / stale
#: sentinel and denies the request. A **best-effort, non-exhaustive** structural placeholder catalogue,
#: never a numeric bound (design #26 §8; authored locally, the rlp ``WILDCARD_SENTINELS`` /
#: cur ``_FORBIDDEN_PLACEHOLDERS`` precedent — no rlp import, sibling edge 0). Deliberately incomplete:
#: the §10 *patched* / *widened* / *stale* / *conflicting* axes and any novel wildcard notation outside
#: it are +Security / runtime-owned, not value-model-decidable (see :func:`is_wildcard_value`).
WILDCARD_SENTINELS: frozenset[str] = frozenset(
    {
        "*",
        "?",
        "latest",
        "LATEST",
        "@latest",
        "any",
        "ANY",
        "all",
        "ALL",
        "everything",
        "null-as-scope",
        "NULL_AS_SCOPE",
        "inferred",
        "INFERRED",
        "inherit",
        "fallback",
        "wildcard",
    }
)

#: Glob / regex / SQL-``LIKE`` / fullwidth-asterisk metacharacters whose presence anywhere in a scope
#: coordinate makes it non-exact (a partial-match pattern is never an exact scope, even when the
#: surrounding token is not a catalogued sentinel — e.g. ``*.KOSPI`` / ``KOSPI*`` / ``%`` / ``**``).
#: Best-effort, non-exhaustive (design #26 §0.4 / §10 line 299).
WILDCARD_METACHARACTERS: frozenset[str] = frozenset({"*", "?", "%", "[", "]", "＊"})

#: :data:`WILDCARD_SENTINELS` normalized with ``casefold`` so a case variant ("All" / "aLL") of a
#: catalogued sentinel is caught (the membership test normalizes the candidate the same way).
_WILDCARD_SENTINELS_CASEFOLD: frozenset[str] = frozenset(
    sentinel.strip().casefold() for sentinel in WILDCARD_SENTINELS
)


def is_wildcard_value(value: str | None) -> bool:
    """Whether a scope coordinate is a wildcard placeholder (best-effort, non-exhaustive).

    A value is **not exact** — a wildcard / inferred / stale placeholder — when, after a
    ``strip().casefold()`` normalization, it is (a) **empty** (whitespace-only is not a scope), (b) a
    member of the :data:`WILDCARD_SENTINELS` catalogue matched **case-insensitively** (so ``"All"`` /
    ``"aLL"`` / ``" * "`` are caught, not only the exact-cased list members), or (c) contains any
    :data:`WILDCARD_METACHARACTERS` glob / regex / SQL-``LIKE`` / fullwidth metacharacter (so
    ``"*.KOSPI"`` / ``"KOSPI*"`` / ``"%"`` / ``"**"`` / ``".*"`` / fullwidth ``＊`` are caught). A
    ``None`` is **absent** (the dimension is not bound — the caller treats that case separately) and
    returns ``False``.

    **Best-effort, non-exhaustive denylist (honesty — design #26 §0.4 / §10 line 299 / #25 MAJOR-1
    lesson).** This value-model check catches catalogued sentinels and common metacharacters only. The
    §10 *patched* / *widened* / *stale* / *conflicting* axes, and any novel wildcard notation outside
    this catalogue / metacharacter set, are **not** value-model-decidable: they are owned by +Security
    and the runtime (carried separately as the negative-polarity request flags). This helper does
    **not** guarantee the full §10 property.

    Args:
        value: The scope coordinate (``None`` ⇒ absent, returns ``False``).

    Returns:
        ``True`` iff the value is a (detectable) wildcard / placeholder / non-exact coordinate.
    """
    if value is None:
        return False
    normalized = value.strip().casefold()
    if not normalized:
        return True
    if normalized in _WILDCARD_SENTINELS_CASEFOLD:
        return True
    return any(metacharacter in value for metacharacter in WILDCARD_METACHARACTERS)


class DeviationScope(FrozenModel):
    """The exact reduced deviation scope tuple (ADR-002-026 §5.7 line 126-128; design #26 §2.4).

    §5.7 line 128: the complete 21-dimension scope one decision applies to — one ``str | None``
    coordinate per :class:`~tos.wdr.vocabulary.ScopeDimension` (environment / safety cell / capacity
    domain / legal portfolio / account / broker / venue / instrument / strategy / action class /
    software / configuration / identity / route / session / failure domain / time interval / evidence /
    requirement / hazard / dependency closure). Each field's name is the lowercased ``ScopeDimension``
    member (the §7.2 anchor-drift correspondence). A ``None`` coordinate is **absent** and a coordinate
    that :func:`is_wildcard_value` judges non-exact (a catalogued sentinel, a glob / regex / ``LIKE``
    metacharacter, or a whitespace-only blank) is a **wildcard** — either one means the dimension is not
    exact (§10 line 299). Consumed by :func:`~tos.wdr.predicates.scope_exact_and_complete`.
    """

    environment: str | None = None
    safety_cell: str | None = None
    capacity_domain: str | None = None
    legal_portfolio: str | None = None
    account: str | None = None
    broker: str | None = None
    venue: str | None = None
    instrument: str | None = None
    strategy: str | None = None
    action_class: str | None = None
    software: str | None = None
    configuration: str | None = None
    identity: str | None = None
    route: str | None = None
    session: str | None = None
    failure_domain: str | None = None
    time_interval: str | None = None
    evidence: str | None = None
    requirement: str | None = None
    hazard: str | None = None
    dependency_closure: str | None = None

    def concrete_dimensions(self) -> frozenset[ScopeDimension]:
        """The dimensions bound to an exact (non-``None``, non-wildcard) value (§5.2/§5.7).

        A dimension is concrete only when its coordinate is present **and** not a wildcard per
        :func:`is_wildcard_value` (a catalogued sentinel — case-insensitively — a glob / regex /
        ``LIKE`` metacharacter, or a whitespace-only blank is not exact; §10 line 299). Consumed by the
        subset check in :func:`~tos.wdr.predicates.scope_exact_and_complete`.

        Returns:
            The frozenset of ``ScopeDimension`` members bound to an exact concrete value.
        """
        concrete: set[ScopeDimension] = set()
        for dimension in ScopeDimension:
            value = getattr(self, dimension.name.lower())
            if value is not None and not is_wildcard_value(value):
                concrete.add(dimension)
        return frozenset(concrete)

    def wildcard_dimensions(self) -> frozenset[ScopeDimension]:
        """The dimensions bound to a (detectable) wildcard placeholder (§10 line 299; §5.2).

        A dimension is a wildcard when its coordinate is a string that :func:`is_wildcard_value` judges
        non-exact — a catalogued sentinel (case-insensitively), a glob / regex / ``LIKE`` metacharacter
        (``*.KOSPI`` / ``KOSPI*`` / ``%`` / ...), or a whitespace-only blank. Best-effort and
        non-exhaustive (see :func:`is_wildcard_value`).

        Returns:
            The frozenset of ``ScopeDimension`` members whose coordinate is a detectable wildcard.
        """
        wildcards: set[ScopeDimension] = set()
        for dimension in ScopeDimension:
            value = getattr(self, dimension.name.lower())
            if isinstance(value, str) and is_wildcard_value(value):
                wildcards.add(dimension)
        return frozenset(wildcards)


class CompensatingControl(FrozenModel):
    """An enforceable preventive or containment mechanism (ADR-002-026 §5.5/§11; design #26 §2.4).

    §5.5 verbatim: "An independently governed, enforceable **preventive or containment** mechanism that
    reduces the exact added risk of an allowed deviation. A document, alert, dashboard, audit, replay,
    priority label, or operator promise is **not by itself** a compensating control." The judgement is
    carried by the polarity fields — ``is_preventive_or_containment`` / ``objective_evidence`` /
    ``fails_closed`` / ``independent_of_failed_control`` are **positive-polarity** (only ``is True``
    admits; §11 item 1/3/4/5), and ``observation_only`` is **negative-polarity** (only ``is False``
    admits; §11 item 8 "not rely solely on documentation, alerting, replay, operator attention, expected
    broker rejection, or priority"). ``kind`` is a descriptive
    :class:`~tos.wdr.vocabulary.CompensatingControlKind` label only. Consumed by
    :func:`~tos.wdr.predicates.compensating_control_not_observation` (§6.1).
    """

    control_id: str | None = None
    kind: CompensatingControlKind | None = None
    owner: str | None = None
    scope: str | None = None
    state_machine: str | None = None
    currentness_rule: str | None = None
    failure_response: str | None = None
    #: Positive-polarity (§11 item 1 / §5.5) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    is_preventive_or_containment: bool | None = None
    #: Positive-polarity (§11 item 3) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    objective_evidence: bool | None = None
    #: Positive-polarity (§11 item 4) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    fails_closed: bool | None = None
    #: Positive-polarity (§11 item 5) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    independent_of_failed_control: bool | None = None
    #: Negative-polarity (§11 item 8 / §5.5) — ``is not False`` (True / None) ⇒ not-a-control.
    observation_only: bool | None = None


class DeviationDependencyClosure(FrozenModel):
    """The affected dependency closure (ADR-002-026 §5.10 line 138-140; design #26 §2.4).

    §5.10 verbatim: "Every component, artifact, account, shared limit, authority, capacity, credential,
    route, failure domain, economic effect, verification claim, and downstream consumer that may be
    affected by the missing control or its compensating controls." Each §5.10 category is a
    ``tuple[str, ...]`` of the affected coordinates (order-significant / deterministic for the covered
    digest — no unstable frozenset serialization). ``closure_complete`` is a **positive-polarity**
    injected proof that the runtime enumeration is complete: the *actual* completeness proof is a
    +Security / runtime judgement (design #26 §5.2 honesty), so L1 checks only that the closure is
    non-empty **and** the positive completeness proof is present. Consumed by
    :func:`~tos.wdr.predicates.dependency_closure_complete`.
    """

    #: The 12 §5.10 line 138-140 closure categories (a manually-transcribed reference of the ADR set).
    CLOSURE_CATEGORIES: ClassVar[tuple[str, ...]] = (
        "components",
        "artifacts",
        "accounts",
        "shared_limits",
        "authorities",
        "capacities",
        "credentials",
        "routes",
        "failure_domains",
        "economic_effects",
        "verification_claims",
        "downstream_consumers",
    )

    components: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()
    shared_limits: tuple[str, ...] = ()
    authorities: tuple[str, ...] = ()
    capacities: tuple[str, ...] = ()
    credentials: tuple[str, ...] = ()
    routes: tuple[str, ...] = ()
    failure_domains: tuple[str, ...] = ()
    economic_effects: tuple[str, ...] = ()
    verification_claims: tuple[str, ...] = ()
    downstream_consumers: tuple[str, ...] = ()
    #: Positive-polarity (§5.10) injected completeness proof — only ``is True`` clears; the real
    #: completeness is +Security / runtime (design #26 §5.2). ``None`` / ``False`` ⇒ deny.
    closure_complete: bool | None = None

    def affected_total(self) -> frozenset[str]:
        """The union of every affected coordinate across the §5.10 categories.

        Returns:
            The frozenset of every affected coordinate (empty ⇒ a trivial / absent closure).
        """
        total: set[str] = set()
        for category in self.CLOSURE_CATEGORIES:
            total.update(getattr(self, category))
        return frozenset(total)


class NonWaivableBoundaryAnchor(FrozenModel):
    """The 15-item Non-Waivable Boundary union anchor (ADR-002-026 §5.6/§8 line 234-248; design #26 §2.4).

    §8 line 234-248 "At minimum, no deviation may waive, reinterpret, or bypass:" the 15-item union
    (RFC-000 constitutional / RFC-001 no-waiver set / fail-closed unknown / RCL exclusivity / egress
    final enforcement / generation fencing / broker-finality semantics / economic continuity / Hard
    Safety Envelope / independent HALT / live-non-live segregation / priority-not-capacity /
    docs-not-prevention / no-auto-rearm / this-ADR rules). Each item is a ``bool`` declaring the anchor
    item is present in the active boundary; a boundary is **complete** only when **all 15 are declared**
    (:meth:`is_complete`). §5.6 "Policy may add prohibitions but **cannot remove them**" — so the
    boundary is UNION-only: a boundary that dropped any of the 15 is a shrunk / forged boundary
    (:func:`~tos.wdr.predicates.boundary_is_union_only`). The 15-item field set is a
    **manually-transcribed regression anchor** of ADR §8 line 234-248 (design #26 §0.4h / appendix C);
    the §7.2 anchor-drift property asserts :data:`BOUNDARY_ITEMS` equals the model's bool fields.
    """

    #: The 15 §8 line 234-248 boundary item field names (manually-transcribed anchor; §0.4h / appendix
    #: C). The §7.2 anchor-drift property asserts this equals the model's bool fields.
    BOUNDARY_ITEMS: ClassVar[tuple[str, ...]] = (
        "rfc_000_constitutional",
        "rfc_001_no_waiver_set",
        "fail_closed_unknown",
        "rcl_exclusivity",
        "egress_final_enforcement",
        "generation_fencing",
        "broker_finality_semantics",
        "economic_continuity",
        "hard_safety_envelope",
        "independent_halt",
        "live_nonlive_segregation",
        "priority_not_capacity",
        "docs_not_prevention",
        "no_auto_rearm",
        "this_adr_rules",
    )

    rfc_000_constitutional: bool = False
    rfc_001_no_waiver_set: bool = False
    fail_closed_unknown: bool = False
    rcl_exclusivity: bool = False
    egress_final_enforcement: bool = False
    generation_fencing: bool = False
    broker_finality_semantics: bool = False
    economic_continuity: bool = False
    hard_safety_envelope: bool = False
    independent_halt: bool = False
    live_nonlive_segregation: bool = False
    priority_not_capacity: bool = False
    docs_not_prevention: bool = False
    no_auto_rearm: bool = False
    this_adr_rules: bool = False

    def is_complete(self) -> bool:
        """Whether every one of the 15 §8 boundary items is declared present (union floor).

        Returns:
            ``True`` iff all 15 :data:`BOUNDARY_ITEMS` are ``True`` — a boundary that dropped any is a
            shrunk / forged boundary (§5.6 "cannot make this list smaller").
        """
        return all(getattr(self, name) is True for name in self.BOUNDARY_ITEMS)


class WaivedEvidenceItem(FrozenModel):
    """A verification-item status view under a deviation (ADR-002-026 §19; design #26 §2.4).

    §19 line 484-490: an evidence item covered by an allowed deviation must remain honestly labeled — it
    may never be relabeled ``PASS`` merely because a deviation exists, historical failures stay visible,
    and ``WAIVED_WITH_RESIDUAL_RISK`` is permitted **only** with the exact current decision, reduced
    scope, compensation, and review record present. ``deviation_exists`` is **negative-polarity** (a
    deviation ``is not False`` — present or unknown — blocks a PASS relabel);
    ``exact_current_decision_present`` / ``reduced_scope_present`` / ``compensation_present`` /
    ``review_record_present`` are **positive-polarity** (only ``is True`` satisfies the WAIVED gate).
    Consumed by :func:`~tos.wdr.predicates.evidence_status_honest` (§5.4).
    """

    measured_status: WaivedEvidenceStatus | None = None
    #: Negative-polarity (§19 line 490) — ``is not False`` (True / None) blocks a PASS relabel.
    deviation_exists: bool | None = None
    #: Positive-polarity (§19 line 488) — only ``is True`` satisfies the WAIVED gate.
    exact_current_decision_present: bool | None = None
    #: Positive-polarity (§19 line 488) — only ``is True`` satisfies the WAIVED gate.
    reduced_scope_present: bool | None = None
    #: Positive-polarity (§19 line 488) — only ``is True`` satisfies the WAIVED gate.
    compensation_present: bool | None = None
    #: Positive-polarity (§19 line 488) — only ``is True`` satisfies the WAIVED gate.
    review_record_present: bool | None = None
    relabeled_status: WaivedEvidenceStatus | None = None


class GateSeparationLadder(FrozenModel):
    """The six distinct explicit gate states (ADR-002-026 §26 AC-012 line 685-687/§28; design #26 §2.4).

    §26 AC-012 line 687 verbatim: "ADR acceptance, deviation eligibility, configuration activation, Live
    Authorization, restricted-live readiness, and production readiness remain **distinct states**." Each
    is an **independent injected** ``bool | None``: no stage implies another (``deviation_eligible`` ↛
    ``configuration_activated`` / ``live_authorized``, ``configuration_activated`` ↛ ``live_authorized``;
    §12 line 358 / §13 line 378). The six-stage set is a **manually-transcribed regression anchor** of
    ADR §26 line 687 (design #26 §0.4h); the §7.2 anchor-drift property asserts the model fields equal
    :data:`STAGE_FIELDS`. Its :class:`~tos.wdr._base.AllFalseDeviationAuthority` is all-false —
    readiness is a status report, never a permission (§5.5 readiness ≠ authority). Consumed by
    :func:`~tos.wdr.predicates.gate_states_separated`.
    """

    #: The six distinct gate-status field names (manually-transcribed anchor of §26 line 687; §0.4h).
    #: The §7.2 anchor-drift property asserts this equals the model's status fields.
    STAGE_FIELDS: ClassVar[tuple[str, ...]] = (
        "adr_accepted",
        "deviation_eligible",
        "configuration_activated",
        "live_authorized",
        "restricted_live_ready",
        "production_ready",
    )

    adr_accepted: bool | None = None
    deviation_eligible: bool | None = None
    configuration_activated: bool | None = None
    live_authorized: bool | None = None
    restricted_live_ready: bool | None = None
    production_ready: bool | None = None
    #: §5.5 — readiness is a status report, not permission (all-false, WDR-INV-001).
    authority_effect: AllFalseDeviationAuthority = AllFalseDeviationAuthority()


class DeviationClassification(FrozenModel):
    """The §8 non-waivable classification input (ADR-002-026 §8; design #26 §2.1/§2.4).

    The value view of the §8 classification decision for one request: the classification result
    (:class:`~tos.wdr.vocabulary.NonWaivableClassification`), whether the requirement's applicability
    was positively resolved (``applicability_resolved``, **positive-polarity** — §9 line 273 "Unknown
    applicability ... denies"), and which §8 line 234-248 boundary items the request would waive
    (``boundary_hits`` — any hit ⇒ deny; §8 line 234). :class:`~tos.wdr.records.SafetyDeviationRequest`
    carries these as flat fields and exposes this derived view via ``classification_view()``; consumed
    by :func:`~tos.wdr.predicates.classification_admissible` (§5.1).
    """

    classification: NonWaivableClassification | None = None
    #: Positive-polarity (§9 line 273) — only ``is True`` clears; ``None`` / ``False`` ⇒ deny.
    applicability_resolved: bool | None = None
    boundary_hits: frozenset[str] = frozenset()


def deviation_generation_advances(
    predecessor: int | None, candidate: int | None
) -> bool:
    """Whether ``candidate`` strictly advances ``predecessor`` in Deviation Generation order (§5.8).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) for the Deviation Generation monotonic
    fence (§5.8 / §14 line 386 "a newer generation SHALL restrict future authority monotonically" — a
    newer generation retires a predecessor decision / active set) and the predecessor floor (§10 line
    284). The two generations are wrapped as ordering coordinates (an ordering scalar, **not** a clock —
    §3.2/§0.4h) and ``True`` **only** when ``predecessor`` provably precedes ``candidate`` (``BEFORE``);
    an equal / ambiguous / regressing pair fails closed. wdr owns the fence *meaning* (retirement);
    ordering only carries the order. A wall clock never orders — wdr reads no clock (§0.4h).

    Args:
        predecessor: The predecessor Deviation Generation ordering scalar (``None`` ⇒ ``False``).
        candidate: The candidate Deviation Generation ordering scalar (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff ``candidate`` provably strictly exceeds ``predecessor``.
    """
    if predecessor is None or candidate is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=candidate),
        )
        is Ordering.BEFORE
    )
