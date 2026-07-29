"""rlp injected inputs + value models + generation-order ordering REUSE (design #25 §2.1/§3.2).

Two roles:

* **value / injected input models (design #25 §2.1)** — the exact scope tuple (:class:`TrialScope` —
  §5.3, every §9 line 263 dimension as a ``str | None`` coordinate), the request envelope
  (:class:`TrialBudget` — §5.4, an upper request envelope, **NOT** capacity, §10), the coverage claim
  (:class:`CoverageClaim` — §5.8, claimed vs observed scope), the gate-status ladder
  (:class:`GateStatusLadder` — §26 AC-012, nine distinct explicit states), and the seam mirror
  (:class:`TrialClaimGroup` — the 6-scalar restricted-live trial claim group egress / cur carry
  downstream as an opaque optional scalar group, re-expressed here as the RLP-owned content view,
  **not** an egress / cur re-authoring, §0.4b/c). Every one is a **pydantic v2 frozen model**
  (``frozen=True, extra="forbid"`` via :class:`~tos.rlp._base.FrozenModel`): ``extra="forbid"`` is the
  schema-level "omission is restrictive" and frozen is the append-only realization — there is **no**
  update / delete / mutate method on any model (design #25 §2.3/§4.1).

* **generation order (design #25 §3.2 ordering REUSE)** — :func:`promotion_generation_advances`
  REUSES ``tos.ordering.compare_order`` (no re-authored order) for the Promotion Generation monotonic
  fence (§5.10 / §18 line 466 "after ... a newer Promotion Generation") and the predecessor floor
  (§9 line 261). rlp owns the fence *meaning* (a newer Promotion Generation retires a predecessor
  decision); ordering only carries the monotonic order. **A wall clock never orders — rlp reads no
  clock**: a Promotion Generation is an ordering identity, not wall-clock time (§3.2/§0.4g), so this
  package is clock-free (``MAX_trial_*_ms`` wall-clock age is a secondary +Security / INSTANCE bound,
  §8).

**Numeric-bound freedom (design #25 §8; ADR §8 non-scope).** rlp carries no numeric size / duration /
threshold constant: every such value is an **injected** opaque scalar (null in Phase 1, fail-closed
at the consuming predicate). Nothing numeric is hardcoded — the rlp logic is over StrEnums, booleans,
set / coordinate membership, and injected values only. The **wildcard sentinel set**
(:data:`WILDCARD_SENTINELS`) plus the :data:`WILDCARD_METACHARACTERS` glob / regex / SQL-LIKE
metacharacter set are a structural placeholder catalogue (``*`` / ``latest`` / ...), never a numeric
bound (RLP-INV-002 line 154 "wildcard, inferred, patched, unioned, stale, or conflicting scope is
denial").

**Wildcard detection is a best-effort, non-exhaustive value-model denylist (honesty).**
:func:`is_wildcard_value` normalizes (``strip().casefold()``) and catches catalogued sentinels (case
variants included) plus common metacharacters only. The RLP-INV-002 *patched* / *unioned* / *stale* /
*conflicting* axes, and any novel wildcard notation outside this catalogue / metacharacter set, are
**not** value-model-decidable — they are owned by +Security and the runtime. This module does **not**
guarantee the full RLP-INV-002 property; it provides a structural first line only (design #25 §0.4 /
RLP-INV-002 line 154).

**Injected-verdict discipline (design #25 §1/§0.4b over-realization + duplication boundary).** Every
sibling owner's produced verdict / generation / digest is an **injected** coordinate:
rlp does **not** re-decide any owner's business content (egress QCC / TrialClaims boundary seal, cur
RESTRICTED_LIVE_TRIAL dimension, hag effective-principal / quorum, evidence SegmentCommitmentScheme /
causal-chain, rcl CapacityVector / worst-credible-effect, liveauth Live Authorization, spg policy
activation, 026-030 governance) — it consumes the produced fact and judges only exact-scope /
package / coverage / gate structure (§3.5).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.rlp.*`` only; no ``shared.*``, no
other sibling ``tos.*`` (design #25 §0.3). Clock-free.
"""

from __future__ import annotations

from typing import ClassVar

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.rlp._base import AllFalseTrialAuthority, FrozenModel
from tos.rlp.vocabulary import CoverageVerdict, ScopeDimension

__all__ = [
    "WILDCARD_SENTINELS",
    "WILDCARD_METACHARACTERS",
    "is_wildcard_value",
    "TrialScope",
    "TrialBudget",
    "CoverageClaim",
    "GateStatusLadder",
    "TrialClaimGroup",
    "promotion_generation_advances",
]

#: Forbidden scope-placeholder sentinels a scope coordinate may never use (RLP-INV-002 line 154 /
#: §9 line 263). A scope dimension bearing any of these — matched case-insensitively via
#: :func:`is_wildcard_value` — is **not** an exact pre-registered scope: it is a wildcard / inferred /
#: stale sentinel and denies the plan. A **best-effort, non-exhaustive** structural placeholder
#: catalogue, never a numeric bound (design #25 §8; the cur ``_FORBIDDEN_PLACEHOLDERS`` precedent).
#: This catalogue is deliberately incomplete: the RLP-INV-002 *patched* / *unioned* / *stale* /
#: *conflicting* axes and any novel wildcard notation outside it are +Security / runtime-owned, not
#: value-model-decidable (see :func:`is_wildcard_value`).
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
#: or baseline coordinate makes it non-exact (a partial-match pattern is never an exact scope, even
#: when the surrounding token is not a catalogued sentinel — e.g. ``*.KOSPI`` / ``KOSPI*`` / ``%`` /
#: ``**``). Best-effort, non-exhaustive (design #25 §0.4 / RLP-INV-002 line 154).
WILDCARD_METACHARACTERS: frozenset[str] = frozenset({"*", "?", "%", "[", "]", "＊"})

#: :data:`WILDCARD_SENTINELS` normalized with ``casefold`` so a case variant ("All" / "aLL") of a
#: catalogued sentinel is caught (the membership test normalizes the candidate the same way).
_WILDCARD_SENTINELS_CASEFOLD: frozenset[str] = frozenset(
    sentinel.strip().casefold() for sentinel in WILDCARD_SENTINELS
)


def is_wildcard_value(value: str | None) -> bool:
    """Whether a scope / baseline coordinate is a wildcard placeholder (best-effort, non-exhaustive).

    A value is **not exact** — a wildcard / inferred / stale placeholder — when, after a
    ``strip().casefold()`` normalization, it is (a) **empty** (whitespace-only is not a scope),
    (b) a member of the :data:`WILDCARD_SENTINELS` catalogue matched **case-insensitively** (so
    ``"All"`` / ``"aLL"`` / ``" * "`` are caught, not only the exact-cased list members), or (c)
    contains any :data:`WILDCARD_METACHARACTERS` glob / regex / SQL-``LIKE`` / fullwidth metacharacter
    (so ``"*.KOSPI"`` / ``"KOSPI*"`` / ``"%"`` / ``"**"`` / ``".*"`` / fullwidth ``＊`` are caught). A
    ``None`` is **absent** (the dimension is not bound — the caller treats that case separately) and
    returns ``False``.

    **Best-effort, non-exhaustive denylist (honesty — design #25 §0.4 / RLP-INV-002 line 154).** This
    value-model check catches catalogued sentinels and common metacharacters only. The RLP-INV-002
    *patched* / *unioned* / *stale* / *conflicting* axes, and any novel wildcard notation outside this
    catalogue / metacharacter set, are **not** value-model-decidable: they are owned by +Security and
    the runtime. This helper does **not** guarantee the full RLP-INV-002 property.

    Args:
        value: The scope / baseline coordinate (``None`` ⇒ absent, returns ``False``).

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


class TrialScope(FrozenModel):
    """The exact pre-registered trial scope tuple (ADR-002-025 §5.3/§9 line 263; design #25 §2.4).

    §9 line 263: the exact scope a pre-registered trial plan binds — one ``str | None`` coordinate per
    :class:`~tos.rlp.vocabulary.ScopeDimension` (environment / safety cell / capacity domain /
    portfolio / account / broker / venue / instrument / strategy / action class / order shape /
    software release / configuration / identity / credential / route / session / time interval /
    failure domain). Each field's name is the lowercased ``ScopeDimension`` member (the §7.2
    anchor-drift correspondence). A ``None`` coordinate is **absent** and a coordinate that
    :func:`is_wildcard_value` judges non-exact (a catalogued sentinel, a glob / regex / ``LIKE``
    metacharacter, or a whitespace-only blank) is a **wildcard** — either one means the dimension is
    not exact (RLP-INV-002 line 154). Consumed by
    :func:`~tos.rlp.predicates.plan_scope_exact_and_complete`.
    """

    environment: str | None = None
    safety_cell: str | None = None
    capacity_domain: str | None = None
    portfolio: str | None = None
    account: str | None = None
    broker: str | None = None
    venue: str | None = None
    instrument: str | None = None
    strategy: str | None = None
    action_class: str | None = None
    order_shape: str | None = None
    software_release: str | None = None
    configuration: str | None = None
    identity: str | None = None
    credential: str | None = None
    route: str | None = None
    session: str | None = None
    time_interval: str | None = None
    failure_domain: str | None = None

    def concrete_dimensions(self) -> frozenset[ScopeDimension]:
        """The dimensions bound to an exact (non-``None``, non-wildcard) value (§5.1/§5.3).

        A dimension is concrete only when its coordinate is present **and** not a wildcard per
        :func:`is_wildcard_value` (a catalogued sentinel — case-insensitively — a glob / regex /
        ``LIKE`` metacharacter, or a whitespace-only blank is not exact; RLP-INV-002 line 154).
        Consumed by the subset check in
        :func:`~tos.rlp.predicates.plan_scope_exact_and_complete`.

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
        """The dimensions bound to a (detectable) wildcard placeholder (RLP-INV-002 line 154; §5.1).

        A dimension is a wildcard when its coordinate is a string that :func:`is_wildcard_value`
        judges non-exact — a catalogued sentinel (case-insensitively), a glob / regex / ``LIKE``
        metacharacter (``*.KOSPI`` / ``KOSPI*`` / ``%`` / ...), or a whitespace-only blank. Best-effort
        and non-exhaustive (see :func:`is_wildcard_value`).

        Returns:
            The frozenset of ``ScopeDimension`` members whose coordinate is a detectable wildcard.
        """
        wildcards: set[ScopeDimension] = set()
        for dimension in ScopeDimension:
            value = getattr(self, dimension.name.lower())
            if isinstance(value, str) and is_wildcard_value(value):
                wildcards.add(dimension)
        return frozenset(wildcards)


class TrialBudget(FrozenModel):
    """The trial request envelope — NOT capacity (ADR-002-025 §5.4/§10; design #25 §2.4).

    §10 line 296 verbatim: "The plan's Trial Budget is an **upper request envelope**. **Only RCL may
    commit capacity**. Unused plan budget creates **no headroom** and cannot be transferred." So this
    is a *request envelope* the plan carries, **not** capacity: the numeric bounds
    (``max_action_count`` / ``duration_ms``) are injected Profile-INSTANCE values (null in Phase 1,
    §8) and ``credible_economic_effect_envelope`` is an **injected rcl CapacityVector coordinate**
    (§0.4g) — the worst-credible-effect *computation* is rcl + +Broker (§28 open Q #3), never
    re-authored here. Consumed by :func:`~tos.rlp.predicates.trial_budget_is_not_capacity`.
    """

    max_action_count: int | None = None
    duration_ms: int | None = None
    #: Injected rcl-owned broker-resource vector coordinate (§10; not a capacity mutation).
    broker_resource_vector: str | None = None
    #: Injected rcl CapacityVector coordinate for the credible economic effect (§10; rcl computes it).
    credible_economic_effect_envelope: str | None = None


class CoverageClaim(FrozenModel):
    """One coverage claim — claimed vs observed scope (ADR-002-025 §5.8/§17; design #25 §2.4).

    §17 line 434-444: a claim that observed (actually exercised) behavior supports a claimed scope.
    ``claimed_scope`` is what the trial claims to cover; ``observed_scope`` is what was **actually
    exercised** (§17 line 434 "map evidence to exact ... scope"). ``exercised_conditions`` /
    ``unexercised_conditions`` are the §17 line 440 condition catalogue (nominal / boundary / missing
    / stale / duplicate / delayed / crash / restart / partition / broker-rejection / partial-fill /
    UNKNOWN / conflict). ``equivalence_positively_proven`` is **positive-polarity** (§17 line 444
    "Unknown equivalence is non-equivalence"): only a positively-proven equivalence permits any
    cross-scope inference; ``None`` / ``False`` forbids extrapolation. Consumed by
    :func:`~tos.rlp.predicates.coverage_supports_claim`.
    """

    claimed_scope: frozenset[str] = frozenset()
    observed_scope: frozenset[str] = frozenset()
    exercised_conditions: frozenset[str] = frozenset()
    unexercised_conditions: frozenset[str] = frozenset()
    #: Positive-polarity (§17 line 444): only ``is True`` permits a cross-scope inference; ``None`` /
    #: ``False`` ⇒ non-equivalence (no extrapolation).
    equivalence_positively_proven: bool | None = None
    verdict: CoverageVerdict | None = None


class GateStatusLadder(FrozenModel):
    """The nine distinct explicit gate states (ADR-002-025 §26 AC-012/§29; design #25 §2.4).

    §26 RLP-AC-012 line 680: the nine gate states "remain distinct explicit states" — a trial status
    can never masquerade as a production status. Each is an **independent injected** ``bool | None``:
    no stage implies another (``plan_eligible`` ↛ ``live_authorized``, ``promotion_eligible`` ↛
    ``config_activated`` / ``production_ready``; §5.4). The nine-stage set is a **manually-transcribed
    regression anchor** of ADR §26 line 680 (design #25 §0.4h); the §7.2 anchor-drift property asserts
    the model fields equal it. Its :class:`~tos.rlp._base.AllFalseTrialAuthority` is all-false —
    readiness is a status report, never a permission (§5.4 readiness ≠ authority). Consumed by
    :func:`~tos.rlp.predicates.gate_status_separated`.
    """

    evl0_review: bool | None = None
    adr_accepted: bool | None = None
    plan_eligible: bool | None = None
    evl5_complete: bool | None = None
    promotion_eligible: bool | None = None
    config_activated: bool | None = None
    live_authorized: bool | None = None
    restricted_live_ready: bool | None = None
    production_ready: bool | None = None
    #: §5.4 — readiness is a status report, not permission (all-false, RLP-INV-001).
    authority_effect: AllFalseTrialAuthority = AllFalseTrialAuthority()

    #: The nine distinct gate-status field names (manually-transcribed anchor of §26 line 680; §0.4h).
    #: The §7.2 anchor-drift property asserts this equals the model's status fields.
    STAGE_FIELDS: ClassVar[tuple[str, ...]] = (
        "evl0_review",
        "adr_accepted",
        "plan_eligible",
        "evl5_complete",
        "promotion_eligible",
        "config_activated",
        "live_authorized",
        "restricted_live_ready",
        "production_ready",
    )


class TrialClaimGroup(FrozenModel):
    """The RLP-owned content view of the 6-scalar restricted-live trial claim group (design #25 §0.4b).

    The **content owner's** view of the conditional trial claim group that egress
    (``egress/state.py:190-227``, ADR-002-013 §11.1 line 308) and cur (``cur/state.py:134-150``,
    ADR-002-024 §9:258) carry **downstream** as an opaque optional scalar group whose content
    validation both **explicitly defer to RLP by name** (``tos.rlp``). The six scalars are
    **field-set identical** to the two siblings' ``TrialClaims`` — a **manually-transcribed
    regression anchor** of the §11.1 line 308 / §9:258 design-time contract (design #25 §0.4h), **not**
    an egress / cur import (sibling edge 0; the seam cross-check test asserts the field-set match).
    rlp is the **upstream content producer**; egress / cur are downstream consumers, so an ``import
    tos.egress`` / ``import tos.cur`` here would be a cycle (§3.4).

    :meth:`is_complete` is the egress-``is_complete()``-equivalent thin all-present check; the RLP
    authoritative content completeness (:func:`~tos.rlp.predicates.trial_claims_complete`) is
    **thicker** — it AND-s the plan's exact-scope completeness on top (§0.4b/c).
    """

    trial_policy_generation: int | None = None
    trial_plan_generation: int | None = None
    trial_run_generation: int | None = None
    promotion_generation: int | None = None
    remaining_envelope: str | None = None
    abort_generation: int | None = None

    #: The 6 trial-claim scalar names — field-set identical to egress / cur ``TrialClaims``
    #: (manually-transcribed anchor of §11.1 line 308 / §9:258; the seam cross-check asserts equality).
    REQUIRED_SCALARS: ClassVar[tuple[str, ...]] = (
        "trial_policy_generation",
        "trial_plan_generation",
        "trial_run_generation",
        "promotion_generation",
        "remaining_envelope",
        "abort_generation",
    )

    def is_complete(self) -> bool:
        """Whether every conditional trial scalar is concrete (the egress ``is_complete()`` mirror).

        Returns:
            ``True`` iff no :data:`REQUIRED_SCALARS` value is ``None`` — the thin all-present axis
            (fail-closed on any ``None``). This mirrors egress ``TrialClaims.is_complete()``; the
            thicker content completeness is
            :func:`~tos.rlp.predicates.trial_claims_complete` (§0.4b/c).
        """
        return all(getattr(self, name) is not None for name in self.REQUIRED_SCALARS)


def promotion_generation_advances(
    predecessor: int | None, candidate: int | None
) -> bool:
    """Whether ``candidate`` strictly advances ``predecessor`` in Promotion Generation order (§5.10).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) for the Promotion Generation
    monotonic fence (§5.10 / §18 line 466 "after ... a newer Promotion Generation" — a newer
    generation retires a predecessor decision) and the predecessor floor (§9 line 261). The two
    generations are wrapped as ordering coordinates (an ordering scalar, **not** a clock — §3.2/§0.4g)
    and ``True`` **only** when ``predecessor`` provably precedes ``candidate`` (``BEFORE``); an equal
    / ambiguous / regressing pair fails closed. rlp owns the fence *meaning* (retirement); ordering
    only carries the order. A wall clock never orders — rlp reads no clock (§0.4g).

    Args:
        predecessor: The predecessor Promotion Generation ordering scalar (``None`` ⇒ ``False``).
        candidate: The candidate Promotion Generation ordering scalar (``None`` ⇒ ``False``).

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
