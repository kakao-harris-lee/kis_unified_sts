"""posttrade decision predicates — the 19 pure, fail-closed post-trade rules (§5).

Pure, fail-closed decision rules over injected frozen models (design #24 §0.2/§4.4):
``tos.posttrade`` is **not** a capacity ledger, **not** an aggregate-risk projector, **not**
a per-field evidence classifier, **not** a broker-capability arbiter, **not** a non-trade
event identifier, **not** a currentness fence, and **not** an egress. The capacity
reservation, commit, transfer, quarantine, and release arithmetic is rcl-owned (ADR-002-030
§1 line 21 verbatim "The Risk Capacity Ledger remains the sole capacity mutation and
serialization authority ... an obligation compiler, Reconciliation Service, PTOL, position
or cash projection, statement processor, evidence service, recovery workflow, operator, or
finality proof SHALL NOT create, change, quarantine, transfer, remap, or release capacity";
PTF-INV-008); the aggregate-risk projection and the netting **benefit** are are-owned (§21;
``BenefitKind.NETTING``); the per-field evidence confidence is recon-owned (§11;
PTF-INV-005 "confidence score ... cannot replace exact per-field proof"); broker / clearing
/ custodian / banking capability and Final-Quantity-Proof adequacy are brokercap-owned (the
``+Broker`` premise on **all twelve** PTF-EV rows); the non-trade event and transformation
identity plus the event workflow lifecycle are nontrade-owned (ADR-002-010 §16 line 309 ↔
ADR-002-030 §17 line 414, a **mutual** deferral); currentness fencing is cur-owned
(``DimensionKey.POST_TRADE``); external economic transmission is egress-owned (§1 line 31;
PTF-INV-016); the order / knowledge state axes are orthostate-owned (§10 line 303-310);
authority re-arm is authority / liveauth-owned (§22); recovery is sbr-owned (§24); and
trustworthy time is time-owned (§22). This module **consumes every one of those as an
injected produced bool / token / magnitude and re-authors none of them** (design #24
§0.2/§3.5).

What it *does* author is the post-trade **decision layer**: finality-dimension
orthogonality, obligation-leg set completeness, fill-to-obligation commit idempotency,
no-favourable-default (absence is not zero, netting needs positive proof, a missing
counterleg is adverse), collateral conservation and cash-kind non-substitution,
event-state-is-not-obligation-finality, statement coverage completeness and source
independence, finality-proof class specificity / non-transferability / currency, the
finality-grants-nothing seal, and the single
:class:`~tos.posttrade.vocabulary.PostTradeDisposition` producer. There is no
"assume-complete" / "assume-final" / "assume-independent" path anywhere: a permissive result
comes only from **positive conjunction identity**, and the residual branch of every dispatch
is restrictive (design #24 §4 — the structural seal against the #6 fail-open REJECT and the
#16 CRITICAL "a GRANT must not be the fall-through residue" lesson).

**Polarity discipline (design #24 §0.1(11) — the #18 / #21 v1.1 lessons).**

* :class:`~tos.posttrade.vocabulary.PostTradeDisposition` and
  :class:`~tos.posttrade.vocabulary.ObligationCommitOutcome` are **truthy-untestable**
  (``__bool__`` raises), so every gate is an **identity** test
  (``is PostTradeDisposition.POST_TRADE_ADMISSIBLE``), never ``if disposition:``.
* An injected **sibling token** (the recon ``FieldConfidenceClass``, the nontrade
  ``NonTradeEventWorkflowState``, the cur ``CurrentnessAdmission``) crosses the seam as a
  bare string and is compared with ``==`` against a **local constant** — never with
  ``bool(token)``, and never against an imported type (sibling edge 0).
* **Positive-polarity** ``bool | None`` (safe value ``True``: ``original_retained``,
  ``same_scope``, ``enforceable_netting_proof``, ``counterleg_positively_established``,
  ``dimension_proof_present[*]``, ``line_item_absent``, ``coverage_complete``,
  ``correction_semantics_support``, ``source_capability_supports``, ``booked_zero``,
  ``availability_proven``, and every one of the sixteen
  :func:`post_trade_disposition` conjuncts) is gated with ``is True`` **only**, so a
  ``None`` and a truthy non-``bool`` both fail closed.
* **Negative-polarity** ``bool | None`` (safe value ``False``) would be gated with ``is
  False`` **only** (``is not True`` is forbidden *there* because a ``None`` would pass it) —
  but **Phase-1 posttrade has zero negative-polarity fields** (design #24 §7, honest
  disclosure): no-netting is a structural coexistence of two gross magnitudes, collateral
  conservation is a magnitude sum, history preservation is the positive
  ``original_retained``, and a capacity release / external send is unrepresentable. A §7
  property asserts the phantom names stay absent from the models.
* The one place ``is not True`` appears is inside :func:`post_trade_disposition`'s **denial**
  ranks, where it makes a ``None`` fall to the *more* conservative member. Using it to
  **permit** anything is what the series discipline forbids, and it is used to permit
  nothing here.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; **no sibling** ``tos.*``
(sibling edge 0, design #24 §0.3/§0.4b), no ``shared.*``.

**Discipline tag (design #24 §1).** *Predicate / coordinate substrate only. Closing
PTF-EV = 0; no EV-L1-complete claim.*
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.canonical import CanonicalDecimal
from tos.posttrade.records import (
    ObligationLegScope,
    PostTradeFinalityProof,
)
from tos.posttrade.vocabulary import (
    FinalityDimensionKind,
    ObligationLegDirection,
)

__all__ = [
    "finality_dimensions_orthogonal",
    "finality_proof_class_specific",
    "finality_proof_current",
    "finality_proof_non_transferable",
    "obligation_leg_set_complete",
]


# ===========================================================================
# Shared fail-closed helpers
# ===========================================================================


def _is_present_non_negative(magnitude: CanonicalDecimal | None) -> bool:
    """Whether a magnitude is present, finite, and non-negative (fail-closed helper).

    ``None`` is UNKNOWN — **never zero** (§13 line 355 "A missing line item or zero estimate
    is not proof of zero") — a non-finite value is unconstructable content that must not
    reach a comparison, and a negative magnitude on a *gross* obligation / collateral axis is
    a sign error (a direction carries the sign, a magnitude does not). All three are
    ``False``.

    Args:
        magnitude: The injected magnitude.

    Returns:
        ``True`` iff the magnitude is present, finite, and ``>= 0``.
    """
    if magnitude is None:
        return False
    if not magnitude.is_finite():
        return False
    return magnitude >= 0


def _scope_fully_specified(scope: ObligationLegScope | None) -> bool:
    """Whether every one of the six §11 line 328 scope components is concrete.

    A scope with an absent component describes a **set** of legs, and a proof over a set is
    exactly the union §11 line 328 ("non-transferable and non-unionable") forbids. So an
    under-specified scope is not a weaker proof — it is no proof at all.

    Args:
        scope: The scope tuple to check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff leg, account, currency, value date, source revision, and finality class
        are all present (and the string components non-empty).
    """
    if scope is None:
        return False
    if scope.leg is None or scope.finality_class is None:
        return False
    return all(
        bool(component)
        for component in (
            scope.account,
            scope.currency,
            scope.value_date,
            scope.source_revision,
        )
    )


# ===========================================================================
# §5.1 finality-dimension orthogonality + obligation-leg set completeness
# (ADR §12 / §9; PTF-EV-001 substrate, core L1 slice; PTF-INV-001/002; PTF-AC-001)
# ===========================================================================


def finality_dimensions_orthogonal(
    claimed_final_dimension: FinalityDimensionKind | None,
    dimension_proof_present: Mapping[FinalityDimensionKind, bool | None],
) -> bool:
    """Whether the claimed finality dimension rests on **its own** proof (PTF-INV-002).

    PTF-INV-002 line 156 verbatim: the ten dimensions — "Order FQP, trade capture,
    instruction acceptance, settlement, cash availability, collateral eligibility, custody
    title, fee finality, borrow discharge, and corporate-action finality" — "**do not imply
    one another**". §1 line 23 verbatim: "Final Quantity Proof establishes only final
    cumulative filled quantity and zero remaining executable quantity ... **It does not prove
    any post-trade obligation final.**" §12 line 340-345 lists the **six** things it
    explicitly does not prove (:data:`~tos.posttrade.vocabulary.FQP_DOES_NOT_PROVE`).

    **The proposition, in one sentence (design #24 §5.1 M1):** *the claimed dimension is
    final only by its own dimension-specific proof, and no other dimension's proof is
    consulted at all.*

    Non-implication is therefore **structural, not enforced**: the function reads exactly one
    entry of ``dimension_proof_present`` — the claimed one — so ``ORDER_FQP`` PROVEN has no
    code path by which it could make ``SETTLEMENT``, ``CASH_AVAILABILITY``,
    ``FEE_FINALITY``, ``CUSTODY_TITLE``, or ``BORROW_DISCHARGE`` final. There is no
    implication table to get wrong and no aggregate "all final" promotion to fall through
    into (§5.10 line 144 forbids a "universal trade-level boolean"; PTF-INV-005 forbids a
    global ``SETTLED`` / ``CLOSED`` standing in for per-field proof).

    **∅ structural guard (design #24 §5.1 M1 / §4.8 row 2).** An absent claim or an **empty**
    proof map is ``False``: an empty map is "no dimension has any proof", which must never
    read as "the claim holds vacuously". Every dimension defaults to UNKNOWN (PTF-INV-006).
    The guard is written explicitly even though ``Mapping.get`` would also return ``None`` on
    an empty map, because it states the ∅ rule as a **standing invariant** rather than as a
    consequence of one lookup: a later edit that introduced a default (``get(claimed, True)``,
    a ``defaultdict``, or an injected mapping with its own fallback) would otherwise turn the
    vacuous case permissive with no line to review.

    **Positive polarity.** The per-dimension entry is gated ``is True`` only, so ``None``
    (never asserted) and ``False`` (asserted absent) are both not-proven, and a truthy
    non-``bool`` forged past the annotation is not proof either.

    This predicate proves finality of a **leg dimension**, never a consequence: even a
    ``True`` here releases no capacity and makes no cash available (§10 line 312, sealed by
    :func:`post_trade_consequence_all_false`).
    [PTF-EV-001 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-004; SAFE-020; SAFE-021]

    Args:
        claimed_final_dimension: The dimension whose finality is being claimed (``None`` ⇒
            ``False``: nothing is claimed, so nothing is proven).
        dimension_proof_present: The injected per-dimension proof presence map (**positive**
            polarity ``bool | None``). An empty map ⇒ ``False``.

    Returns:
        ``True`` iff the claimed dimension carries its own positive proof.
    """
    if claimed_final_dimension is None or not dimension_proof_present:
        return False
    return dimension_proof_present.get(claimed_final_dimension) is True


def obligation_leg_set_complete(
    required_legs: frozenset[ObligationLegDirection],
    present_legs: frozenset[ObligationLegDirection],
    leg_magnitudes: Mapping[ObligationLegDirection, CanonicalDecimal | None],
) -> bool:
    """Whether the obligation's exact leg set is complete (ADR §9; PTF-INV-001).

    §9 line 273 requires the record to carry its exact "debit, credit, delivery, receipt,
    encumbrance, release, return, and contingent" legs, and §9 line 279 requires the
    **greatest credible adverse union** where a balanced pair cannot be positively
    established. Completeness is therefore a two-part judgment: every *applicable* leg is
    present, **and** each one carries a concrete gross magnitude — an enumerated leg with an
    UNKNOWN magnitude proves nothing about the obligation's size.

    **∅ structural guard (design #24 §5.1; the #21 C1 lesson).** An **empty**
    ``required_legs`` set is ``False``, never a vacuous ``True``: ``∅ <= present`` holds for
    every possible ``present``, so an empty requirement would certify any obligation as
    complete. An empty requirement is not "no risk" — it is "we do not know what must be
    proven". The isomorphic sibling proposition is rcl's ``credible_union_capacity``
    (``rcl/predicates.py:739``), whose empty input raises ``ValueError``; this package
    expresses the same fail-closed rule as ``False``.

    The *applicable* subset is obligation-class-parametric and is **injected** by the caller;
    this package deliberately publishes no default required set, because defaulting to the
    full eight-member universe would silently redefine every caller's obligation.
    [PTF-EV-001 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-012; SAFE-013]

    Args:
        required_legs: The applicable leg directions (**injected**; empty ⇒ ``False``).
        present_legs: The leg directions actually enumerated on the obligation.
        leg_magnitudes: The per-direction gross magnitudes (``None`` is UNKNOWN, never zero).

    Returns:
        ``True`` iff every required leg is present with a concrete, finite, non-negative
        magnitude.
    """
    if not required_legs:
        return False
    if not required_legs <= present_legs:
        return False
    return all(
        _is_present_non_negative(leg_magnitudes.get(leg)) for leg in required_legs
    )


# ===========================================================================
# §5.2 fill-to-obligation commit idempotency
# (ADR §12 line 336/347; PTF-EV-001 substrate, core L1 slice; PTF-AC-001)
# ===========================================================================


# ===========================================================================
# §5.3 no-favourable-default — monetary, netting, counterleg
# (ADR §13 / §9 line 279; PTF-EV-002 substrate, core L1 slice; PTF-INV-004/007)
# ===========================================================================


# ===========================================================================
# §5.4 collateral conservation, margin-state non-implication, cash-kind identity
# (ADR §15 / §14; PTF-EV-004 substrate, core L1 slice; PTF-INV-010/011)
# ===========================================================================


# ===========================================================================
# §5.5 event obligation legs + event-state non-implication
# (ADR §17; PTF-EV-006 substrate, core L1 slice; the nontrade ownership boundary)
# ===========================================================================


# ===========================================================================
# §5.6 statement coverage, source independence, absence-as-negative-evidence
# (ADR §19; PTF-EV-008 substrate, core L1 slice; +Security deferred; PTF-INV-014)
# ===========================================================================


# ===========================================================================
# §5.7 finality proof class-specificity / non-transferability / currency
#      + finality-grants-nothing (ADR §11 / §10 line 312; core substrate)
# ===========================================================================


def finality_proof_class_specific(proof: PostTradeFinalityProof | None) -> bool:
    """Whether a finality proof is exact and class-specific (ADR §11 line 320-326).

    §11 line 320-326 requires a proof to bind the exact obligation identity, version, leg,
    scope, amount, account, currency, value date, generation, and finality class — **and what
    it does not prove**. PTF-INV-005 verbatim: "One global ``SETTLED``, ``CLOSED``,
    confidence score, statement flag, or operator decision cannot replace exact per-field
    proof."

    **The substitution is structurally impossible, not merely rejected.**
    :class:`~tos.posttrade.records.PostTradeFinalityProof` carries no
    ``global_settled_flag``, no ``confidence_score``, no ``statement_flag``, and no
    ``operator_decision`` field, so a global claim has no field to travel in. What such a
    "proof" looks like in practice is one with no ``finality_class``, no ``leg_scope``, and an
    empty ``does_not_prove`` — and this conjunction rejects it. A §7 property asserts the four
    phantom field names stay absent, so the absence cannot be undone by a later edit.

    The conjunction:

    * the obligation reference and version are present;
    * the ``leg_scope`` is **fully specified** — all six §11 line 328 components
      (:func:`_scope_fully_specified`). An under-specified scope covers a *set* of legs, and
      a proof over a set is the union §11 line 328 forbids;
    * the amount is a present, finite, non-negative magnitude;
    * the ``finality_class`` is present **and equals the scope's** finality class (an
      incoherent proof that claims one class while scoping another is rejected);
    * the ``bound_generation`` is present (the reopen coordinate,
      :func:`finality_proof_current`);
    * ``does_not_prove`` is **non-empty** — §11 line 320-326 makes the negative space part of
      the proof, and a proof that never declared its own limits is exactly how a
      single-dimension proof gets read as global finality.

    A failure here is a **contradiction**, not a mere gap: a global flag was offered in place
    of an exact proof, so :func:`post_trade_disposition` maps it to
    ``POST_TRADE_CONFLICTED`` (design #24 §4.8 row 21).
    [SAFE-005; SAFE-010; SAFE-011; SAFE-020]

    Args:
        proof: The finality proof (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the proof binds an exact, coherent, self-limiting class-specific claim.
    """
    if proof is None:
        return False
    if not _scope_fully_specified(proof.leg_scope):
        return False
    if not proof.obligation_ref or not proof.obligation_version:
        return False
    if proof.finality_class is None:
        return False
    scope = proof.leg_scope
    if scope is None or proof.finality_class is not scope.finality_class:
        return False
    if proof.bound_generation is None:
        return False
    if not _is_present_non_negative(proof.amount):
        return False
    return bool(proof.does_not_prove)


def finality_proof_non_transferable(
    proof: PostTradeFinalityProof | None,
    target_leg_scope: ObligationLegScope | None,
    *,
    target_obligation_ref: str | None = None,
    target_obligation_version: str | None = None,
) -> bool:
    """Whether a finality proof applies to exactly this leg scope (§11 line 328; §11 line 320).

    §11 line 328 verbatim: a finality proof is "**non-transferable and non-unionable**" — the
    proof of one leg, account, currency, value date, source revision, or finality class SHALL
    NOT be patched onto or reused for another.

    The judgment is whole-scope structural equality: the proof's
    :class:`~tos.posttrade.records.ObligationLegScope` must equal ``target_leg_scope``
    component for component. Comparing the scope **as a value** rather than field by field is
    deliberate — a hand-rolled conjunction is exactly the thing a later edit shortens, and a
    shortened one is a transfer.

    Both scopes must additionally be **fully specified** (:func:`_scope_fully_specified`):
    two scopes that agree only because both leave the currency ``None`` have not been shown
    to be the same leg, they have been shown to be equally undescribed. Without that guard a
    pair of empty scopes would compare equal and certify a transfer of a proof about nothing
    onto anything.

    **The cross-obligation seal (design #24 v1.2 erratum; adversarial code review MAJOR).**
    The six §11 line 328 scope components name a *leg within an account, currency, value date,
    source revision, and finality class* — they do **not** name the obligation. Two distinct
    obligations can therefore legitimately share one scope tuple (the same account settling
    the same currency on the same value date), and a scope-only comparison would accept one
    obligation's proof as covering the other's identical leg. §11 line 320 requires the proof
    to bind the "exact obligation identity" and version, so when the caller supplies the
    target obligation's identity, it is compared as well.

    The two keyword arguments are **optional for backwards compatibility**: a caller that
    supplies neither gets the original scope-only comparison. Supplying either **narrows**
    the verdict and can only turn a ``True`` into a ``False`` — the conservative direction. A
    supplied identity that the proof does not carry (``proof.obligation_ref is None``) is a
    mismatch, so an unbound proof cannot be waved onto a named obligation.

    A failure here is a **contradiction** (a proof was reused across legs or across
    obligations), so :func:`post_trade_disposition` maps it to ``POST_TRADE_CONFLICTED``
    (design #24 §4.8 row 10).
    [SAFE-005; SAFE-020]

    Args:
        proof: The finality proof (``None`` ⇒ ``False``).
        target_leg_scope: The scope the caller wishes to apply it to (``None`` ⇒ ``False``).
        target_obligation_ref: The identity of the obligation the caller wishes to apply the
            proof to (§11 line 320). ``None`` ⇒ not compared (legacy scope-only behaviour).
        target_obligation_version: The version of that obligation. ``None`` ⇒ not compared.

    Returns:
        ``True`` iff the proof's fully-specified scope equals the fully-specified target and
        every supplied obligation identity component matches the proof's.
    """
    if proof is None or target_leg_scope is None:
        return False
    if not _scope_fully_specified(proof.leg_scope):
        return False
    if not _scope_fully_specified(target_leg_scope):
        return False
    if proof.leg_scope != target_leg_scope:
        return False
    if (
        target_obligation_ref is not None
        and proof.obligation_ref != target_obligation_ref
    ):
        return False
    return (
        target_obligation_version is None
        or proof.obligation_version == target_obligation_version
    )


def finality_proof_current(
    proof: PostTradeFinalityProof | None,
    active_generation: int | None,
) -> bool:
    """Whether a finality proof is still current (§11 line 330; PTF-INV-013).

    §11 line 330 verbatim: "A later correction supersedes the proof, **advances generation**
    ... it does not erase history." PTF-INV-013: a correction **reopens** the affected
    finality.

    So "finality is monotone" is emphatically **not** the naive "once proven, always proven"
    (design #24 §4.5-B, the ninth truth-table row). The four things that really are monotone
    are: the generation increases and never reverts; ``UNKNOWN -> PROVEN`` happens only
    through dimension-specific proof; history is append-only; and a ``PROVEN`` never implies a
    consequence. On top of those, a proof is **current** only while the generation it bound
    is still the active one — the moment a correction advances the generation, the earlier
    proof falls behind and finality reopens.

    A pure integer comparison, L1-decidable: the generation is a ``tos.ordering`` coordinate
    (design #24 §3.2), never a clock and never a duration, so no bound is consulted and none
    is hardcoded. An absent bound generation or an absent active generation is UNKNOWN and
    fails closed — a proof that never declared which generation it bound can never be shown to
    be current.
    [SAFE-020; SAFE-032; SAFE-033]

    Args:
        proof: The finality proof (``None`` ⇒ ``False``).
        active_generation: The current Post-Trade Obligation Generation (``None`` ⇒
            ``False``).

    Returns:
        ``True`` iff the proof's bound generation equals the active generation.
    """
    if proof is None or active_generation is None:
        return False
    if proof.bound_generation is None:
        return False
    return proof.bound_generation == active_generation


# ===========================================================================
# §5.8 the single PostTradeDisposition producer (design #24 C1)
# ===========================================================================
