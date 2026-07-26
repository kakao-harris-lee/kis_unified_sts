"""nontrade decision predicates — envelope, split polarity, correction idempotency.

Pure, fail-closed decision rules over injected frozen models (design #21 §0.2/§4.4):
``tos.nontrade`` is **not** a capacity ledger, **not** an aggregate-risk projector, **not**
an admissibility issuer, **not** a per-field evidence classifier, and **not** an egress.
The capacity arithmetic, remap commit, and release are rcl-owned (ADR-002-010 §1 line 19
"The Risk Capacity Ledger remains the sole authority that reserves, commits, releases,
transfers, or remaps capacity"; §10 line 217 "the event processor ... may propose a remap
but SHALL NOT update capacity independently"); the aggregate-risk projection over the
credible state space is are-owned (ADR-002-021); the material-change invalidation closure
and order admissibility are venue-owned (ADR-002-019; §10 line 221); the per-field evidence
confidence is recon-owned (ADR-002-006; §7); the order / knowledge state axes are
orthostate-owned (§6 line 123); protective cancel / replace / gap / overlap is
replacement-owned (§13 line 272 "ADR-002-011 governs cancellation, replacement, gap,
overlap, and capacity"); authority re-arm is authority / liveauth-owned (§17 line 334);
recovery obligations are sbr-owned (§19 line 359); trustworthy time is time-owned (§8); and
the obligation-lifecycle serialization is ADR-002-030's (§16 line 309). This module
**consumes every one of those as an injected produced bool / token / magnitude and
re-authors none of them** (design #21 §0.2/§3.5).

What it *does* author is the non-trade **decision layer**: transition-envelope leg
completeness + structural no-netting, split polarity coherence + units/rounding
explicitness + residual conservatism, correction / reversal idempotency + lineage, the
label-grants-nothing seal, and the single :class:`~tos.nontrade.vocabulary
.NonTradeDisposition` producer. There is no "assume-complete" / "assume-coherent" /
"assume-admissible" path anywhere: a permissive result comes only from **positive
conjunction identity**, and the residual branch of every dispatch is restrictive (design
#21 §4 — the structural seal against the #6 fail-open REJECT and the #16 CRITICAL "a GRANT
must not be the fall-through residue" lesson).

**Polarity discipline (design #21 §0.1(8)/(j) — the v1.1 C1/C2 lessons).**

* :class:`~tos.nontrade.vocabulary.NonTradeDisposition` and
  :class:`~tos.nontrade.vocabulary.CorrectionReversalOutcome` are **truthy-untestable**
  (``__bool__`` raises), so every gate is an **identity** test
  (``is NonTradeDisposition.NONTRADE_ADMISSIBLE``), never ``if disposition:``.
* An injected **sibling token** (the venue ``OrderAdmissibilityResult``, the recon
  ``FieldConfidenceClass``, the time ``FreshnessVerdict``) crosses the seam as a bare
  string and is compared with ``==`` against a **local constant** — never with
  ``bool(token)``, and never against an imported type (sibling edge 0).
* **Positive-polarity** ``bool | None`` (safe value ``True``: ``original_retained``,
  ``identity_transition_final``, ``source_disagreement_bounded``,
  ``injected_credible_space_bounded``, ``injected_union_capacity_known``,
  ``protective_action_may_proceed``) is gated with ``is True`` **only**, so a ``None`` and
  a truthy non-``bool`` both fail closed.
* **Negative-polarity** ``bool | None`` (safe value ``False``) would be gated with ``is
  False`` **only** (``is not True`` is forbidden there because a ``None`` would pass it) —
  but **Phase-1 nontrade has zero negative-polarity fields** (design #21 M7, honest
  disclosure): no-netting is a structural magnitude derivation, history preservation is the
  positive ``original_retained``, and capacity release is unrepresentable. A §7 property
  asserts the three phantom names stay absent from the models.
* ``event_is_material`` is the one **relaxation-condition** field (its *safe* value is
  ``True``): the exemption is granted **only** on the positive ``is False`` proof of
  non-materiality. ``None`` is material — venue §5.8 "Unknown materiality is material"
  (``venue/predicates.py:379``) — so ``is not True`` must never be used to exempt.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; **no sibling** ``tos.*``
(sibling edge 0, design #21 §0.3/§0.4b), no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Mapping

from tos.canonical import CanonicalDecimal, RecordPairKind, classify_record_pair
from tos.nontrade.records import (
    CorrectionReversalRecord,
    NonTradeAuthorityEffect,
    SplitTransformationSpec,
    TransitionEnvelope,
)
from tos.nontrade.vocabulary import (
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    FRESHNESS_VERDICT_FRESH,
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS,
    RECIPROCAL_DIRECTION_PAIRS,
    SPLIT_KIND_DIRECTIONS,
    CorrectionReversalOutcome,
    CredibleTransitionLegKind,
    NonTradeDisposition,
    SplitTransformationKind,
    TransformationDirection,
)

__all__ = [
    # §5.1 transition envelope (NT-EV-002 substrate, core L1 slice)
    "transition_envelope_complete",
    "favorable_netting_absent",
    # §5.2 split polarity / units / residual (NT-EV-001 substrate, core L1 slice)
    "split_polarity_coherent",
    "transformation_units_and_rounding_explicit",
    "transformation_residual_conservative",
    # §5.3 correction / reversal idempotency (NT-EV-010 substrate, core L1 slice)
    "correction_reversal_idempotent",
    # §5.4 label-grants-nothing (core substrate)
    "nontrade_authority_effect_all_false",
    # §5.5 the single disposition producer (core substrate, C1)
    "nontrade_disposition",
    # §6.1-§6.3 predicate-only (NT-EV-003/007 substrate; claims no EV)
    "instrument_lineage_preserved",
    "effective_window_blocks_new_risk",
    "material_change_trigger_nonempty",
]


#: The **exhaustive** ``RecordPairKind`` -> :class:`CorrectionReversalOutcome` mapping
#: (design #21 §4.6 truth table; the v1.0 C2 defect was an inverted / incomplete mapping).
#: All **five** canonical members are bound explicitly — a §7 property asserts
#: ``set(_RECORD_PAIR_OUTCOME) == set(RecordPairKind)``, so a future canonical member
#: cannot silently fall through to a permissive default.
#:
#: * ``IDEMPOTENT_DUP`` (``canonical/record_pair.py:94``/``:101``) — same primary **or**
#:   idempotency id with the **same** canonical bytes: a harmless re-apply (effect + 0).
#: * ``CRITICAL_CONFLICT`` (``:96``) — same **primary** id, **different** bytes: record
#:   forgery / a contradictory event. Contain both, never last-write-wins (``:68``).
#: * ``DIVERGENT_EMISSION`` (``:103``) — same **idempotency** id, **different** bytes: two
#:   different corrections claiming one key. **Also** contained — the two forgery axes are
#:   distinct kinds that fold to one rejection, and neither is ever double-applied.
#: * ``DISTINCT`` (``:105``) — the prior shares neither identity axis, so it is not the
#:   prior at all: a caller contract violation ⇒ undecidable ⇒ fail closed.
#: * ``NOT_COMPARABLE`` (``:87``) — at least one record is pre-issuance (null digest) ⇒
#:   not a ledger citizen ⇒ undecidable ⇒ fail closed.
_RECORD_PAIR_OUTCOME: Mapping[RecordPairKind, CorrectionReversalOutcome] = {
    RecordPairKind.IDEMPOTENT_DUP: CorrectionReversalOutcome.IDEMPOTENT_REPLAY,
    RecordPairKind.CRITICAL_CONFLICT: CorrectionReversalOutcome.REJECTED_CONFLICT,
    RecordPairKind.DIVERGENT_EMISSION: CorrectionReversalOutcome.REJECTED_CONFLICT,
    RecordPairKind.DISTINCT: CorrectionReversalOutcome.REJECTED_UNKNOWN,
    RecordPairKind.NOT_COMPARABLE: CorrectionReversalOutcome.REJECTED_UNKNOWN,
}

#: The **only** correction outcomes that satisfy the §5.5 positive conjunction: a
#: legitimately applied first correction and a harmless idempotent re-apply. Every
#: ``REJECTED_*`` member is excluded, and the check is an identity membership test — never
#: ``if outcome:`` (which would read a rejection as permission).
_ACCEPTABLE_CORRECTION_OUTCOMES: frozenset[CorrectionReversalOutcome] = frozenset(
    {
        CorrectionReversalOutcome.APPLIED_ONCE,
        CorrectionReversalOutcome.IDEMPOTENT_REPLAY,
    }
)


def _is_present_non_negative(magnitude: CanonicalDecimal | None) -> bool:
    """Whether a magnitude is present, finite, and non-negative (fail-closed helper).

    ``None`` is UNKNOWN — never zero (design #21 §0.4d) — a non-finite value is
    unconstructable content that must not reach a comparison, and a negative magnitude on
    an exposure / residual axis is a sign error. All three are ``False``.

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


def _derive_direction(
    pre: CanonicalDecimal | None, post: CanonicalDecimal | None
) -> TransformationDirection | None:
    """Derive one polarity axis from its pre / post magnitudes (design #21 §2.2-4 M2).

    The **structural** replacement for a caller-declared direction flag: the direction is
    a three-way comparison of the post-event magnitude against the pre-event magnitude,
    i.e. against the **multiplicative identity** ratio ``post / pre == 1``. ``post > pre``
    is :attr:`~tos.nontrade.vocabulary.TransformationDirection.AMPLIFY`, ``post < pre`` is
    ``ATTENUATE``, ``post == pre`` is ``IDENTITY``. **No ratio is hardcoded** — the "2" of
    a 2-for-1 appears nowhere; only ``>`` / ``<`` / ``==`` are used, and
    :data:`~tos.canonical.CanonicalDecimal` scale normalization makes ``1.0`` and ``1.00``
    one value (design #21 §8.0).

    Returns ``None`` (⇒ the consuming predicate fails closed, design #21 §4.7 row 3) when
    either magnitude is absent, non-finite, or negative: an undeclared magnitude is UNKNOWN
    rather than zero, a non-finite value would make every comparison ``False`` and silently
    look like a mismatch, and a negative quantity / basis is a sign error on these axes.

    Args:
        pre: The pre-event magnitude on this axis.
        post: The post-event magnitude on this axis.

    Returns:
        The derived direction, or ``None`` when it cannot be derived.
    """
    if pre is None or post is None:
        return None
    if not pre.is_finite() or not post.is_finite():
        return None
    if pre < 0 or post < 0:
        return None
    if post > pre:
        return TransformationDirection.AMPLIFY
    if post < pre:
        return TransformationDirection.ATTENUATE
    return TransformationDirection.IDENTITY


# ===========================================================================
# §5.1 transition-envelope completeness + structural no-netting
# (ADR §9 line 179-198; NT-EV-002; NT-AC-002)
# ===========================================================================


def favorable_netting_absent(envelope: TransitionEnvelope | None) -> bool:
    """Whether no netting was applied — derived **structurally** (design #21 §0.4d/M7).

    ADR §9 line 196 verbatim: "Risk capacity SHALL cover the maximum aggregate risk across
    the envelope. **Favorable effects SHALL NOT be netted against uncertain adverse
    effects.**" §9 line 187 / §12 line 248: both the old and the new instrument stay active
    in the envelope until the identity transition is final, so the envelope SHALL count
    both — never the net of the two.

    This predicate proves that **structurally** rather than trusting a caller-supplied
    ``netting_applied`` flag (there is no such field — design #21 M7): ``True`` **only**
    when :attr:`~tos.nontrade.records.TransitionEnvelope.pre_event_exposure` **and**
    :attr:`~tos.nontrade.records.TransitionEnvelope.post_event_credible_exposure` are both
    **present (not ``None``), finite, and non-negative**. Netting offsets the old exposure
    against the new, which erases or reduces one of the two; their coexistence as separate
    non-negative magnitudes therefore makes netting structurally impossible. Any ``None``
    (UNKNOWN, never zero) or negative magnitude ⇒ ``False`` (netting suspected / unproven ⇒
    fail closed).

    ``tos.nontrade`` does **not** sum these magnitudes: the dimension-wise union and the
    hard-envelope enforcement are rcl-owned (``credible_union_capacity``
    ``rcl/predicates.py:739``) and the aggregate-risk projection is are-owned
    (``worst_intermediate_risk`` ``are/predicates.py:186``). The resulting double count is
    the conservative requirement, not a defect (design #21 §0.4d). [SAFE-002; SAFE-004;
    SAFE-013]

    **Guarantee scope**: this is a *signature* detector — it proves that netting **cannot
    have been applied** to the envelope's shape (a flag is unforgeable because there is no
    flag), not that the magnitudes are numerically correct. Accounting accuracy of the
    values themselves is evidence / runtime territory (ADR-002-006), never this predicate's.

    Args:
        envelope: The injected transition envelope (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the absence of netting is structurally proven.
    """
    if envelope is None:
        return False
    return _is_present_non_negative(
        envelope.pre_event_exposure
    ) and _is_present_non_negative(envelope.post_event_credible_exposure)


def transition_envelope_complete(
    envelope: TransitionEnvelope | None,
    required_legs: frozenset[CredibleTransitionLegKind],
) -> bool:
    """Whether the transition envelope is complete (ADR §9; NT-EV-002; NT-AC-002).

    §9 line 181: the envelope contains "all credible economic states during the event";
    line 183: it "SHALL include **where applicable**" the ten
    :class:`~tos.nontrade.vocabulary.CredibleTransitionLegKind` legs. The applicable subset
    is event-class-parametric and is therefore **injected** by the caller rather than
    fixed here (§2.2-3 non-closed minimum set).

    ``True`` **only** as one positive conjunction (no fall-through ``return True``):

    * ``required_legs`` is **non-empty** — the ∅ **structural guard**, checked on the first
      line **before** anything else (design #21 §5.1 C1). An empty required set is not
      "nothing to prove"; it is "**we do not know what must be proven**", and
      ``∅ <= anything`` is vacuously ``True``, which is exactly the fail-open seam the
      series has rejected since #6 v1.0. The proposition is identical to rcl
      ``credible_union_capacity``, whose empty input **raises** ``ValueError``
      (``rcl/predicates.py:768`` verbatim "an empty history set must not be read as zero
      capacity to cover (fail-closed)"); this package returns ``False`` instead of raising
      because it is a pure ``bool`` predicate whose caller folds the result into a
      :class:`~tos.nontrade.vocabulary.NonTradeDisposition` — an exception would break that
      fold and push error handling onto the caller;
    * the envelope exists;
    * ``required_legs <= envelope.present_leg_set()`` — a missing leg leaves an
      unenumerated credible state, which is conservatively UNKNOWN, never "no risk";
    * :func:`favorable_netting_absent` holds structurally (the §9 line 196 no-netting
      conjunct, proven by coexisting magnitudes rather than by a flag).

    **What this does not claim (design #21 §3.4(b) M5 / §10.4 G6 — honest disclosure).**
    Completeness is enforced **inside this package's own leg set** only. A caller who
    narrows the applicable subset too far is still under-counting, and whether the declared
    legs cover the ``ProjectedCell`` set handed to are's ``worst_intermediate_risk`` is
    **not** verified in Phase 1 and is **not** claimed. Capacity union, headroom, and risk
    projection are rcl / are verdicts consumed at
    :func:`nontrade_disposition`. [SAFE-002; SAFE-004; SAFE-013]

    Args:
        envelope: The injected transition envelope.
        required_legs: The event-class-applicable legs that must be present. **Empty ⇒
            ``False``** (the C1 structural guard).

    Returns:
        ``True`` iff the envelope is positively proven complete and netting-free.
    """
    if not required_legs:
        # C1 ∅ structural guard — never delegated to a downstream "handled elsewhere".
        return False
    if envelope is None:
        return False
    return required_legs <= envelope.present_leg_set() and favorable_netting_absent(
        envelope
    )


# ===========================================================================
# §5.2 split polarity + units/rounding + residual
# (ADR §11 line 225-240; NT-EV-001; NT-AC-001)
# ===========================================================================


def split_polarity_coherent(spec: SplitTransformationSpec | None) -> bool:
    """Whether a split transformation's polarity is coherent (ADR §11; NT-EV-001).

    A forward split raises quantity and lowers price / cost basis; a reverse split does the
    opposite. They are **opposite-direction rules**, and modelling one as the other is a
    sign error that silently mis-states notional (design #21 §4.5 — the #16 C1
    direction-inversion lesson). Both directions of the error are rejected: a
    both-``ATTENUATE`` spec *under*-estimates and loses risk, a both-``AMPLIFY`` spec
    *over*-estimates; a mis-specification is blocked either way, because an unexplained
    over-estimate is not evidence of anything.

    Two **separate** conjunctions, never a fall-through (design #21 §4.5):

    * **truth table A (reciprocal)** — the derived ``(quantity, basis)`` direction pair is
      one of the three coherent cells of the 3x3
      (:data:`~tos.nontrade.vocabulary.RECIPROCAL_DIRECTION_PAIRS`); the other six are sign
      errors or asymmetries;
    * **truth table B (declared kind vs derived direction)** —
      :data:`~tos.nontrade.vocabulary.SPLIT_KIND_DIRECTIONS` pins ``FORWARD_SPLIT`` to
      ``(AMPLIFY, ATTENUATE)`` and ``REVERSE_SPLIT`` to ``(ATTENUATE, AMPLIFY)``, so a
      caller who declares ``REVERSE_SPLIT`` over forward magnitudes is rejected. A
      ``kind is None`` declares the identity **no-op**, which is coherent **only** with
      ``(IDENTITY, IDENTITY)`` magnitudes; a forged / unrecognized kind token matches no
      row and fails closed.

    **The direction is derived, not declared (design #21 §2.2-4 M2).** There is no
    direction field to forge: :func:`_derive_direction` computes each axis from the pre /
    post magnitudes by a multiplicative-identity comparison. If any of the four magnitudes
    is absent, non-finite, or negative the direction cannot be derived at all and the
    predicate is ``False`` (design #21 §4.7 row 3). **No split ratio is hardcoded**
    anywhere.

    A coherent polarity is **not** permission: §11 line 238 verbatim "Economic equivalence
    SHALL NOT be assumed from a theoretical ratio." Units / rounding
    (:func:`transformation_units_and_rounding_explicit`) and the fractional residual
    (:func:`transformation_residual_conservative`) are **separate conjuncts**, and the
    actual multiplier arithmetic is the rcl remap's (design #21 §3.5). In particular an
    identity no-op passing here never reaches
    :attr:`~tos.nontrade.vocabulary.NonTradeDisposition.NONTRADE_ADMISSIBLE` on its own
    (design #21 §10.4 G2). [SAFE-015; SAFE-025]

    Args:
        spec: The injected split transformation spec (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff truth table A **and** truth table B both hold.
    """
    if spec is None:
        return False
    quantity_direction = _derive_direction(spec.pre_quantity, spec.post_quantity)
    basis_direction = _derive_direction(spec.pre_basis, spec.post_basis)
    if quantity_direction is None or basis_direction is None:
        return False
    derived = (quantity_direction, basis_direction)
    # Truth table A — reciprocal directions (3 of the 9 cells).
    if derived not in RECIPROCAL_DIRECTION_PAIRS:
        return False
    # Truth table B — the declared kind must match the derived directions.
    if spec.kind is None:
        # The identity no-op row: no split kind is declared, so only identity magnitudes
        # are coherent. (Table A already admits only reciprocal pairs, so this rejects a
        # real split whose kind was simply omitted.)
        return derived == (
            TransformationDirection.IDENTITY,
            TransformationDirection.IDENTITY,
        )
    if not isinstance(spec.kind, SplitTransformationKind):
        # A forged / unrecognized kind token matches no row (annotations are not enforced
        # at runtime, so this is reachable from a ``model_construct`` payload).
        return False
    return SPLIT_KIND_DIRECTIONS[spec.kind] == derived


def transformation_units_and_rounding_explicit(
    spec: SplitTransformationSpec | None,
) -> bool:
    """Whether the transformation declares exact units and rounding (ADR §11 line 227).

    §11 line 227 verbatim: "**Every** transformation SHALL specify exact units and rounding
    rules." A **separate conjunct** from :func:`split_polarity_coherent` and
    :func:`transformation_residual_conservative` (design #21 §5.2 M1 — a coherent polarity
    must never promote an unspecified transformation by fall-through), realizing the §11
    line 231 position-quantity vs executable-order-quantity distinction and the §11 line 232
    raw-ratio vs broker-applied-rounded-quantity distinction
    (:data:`~tos.nontrade.vocabulary.TRANSFORMATION_DISTINCTION_OWNERSHIP` items 1 and 2).

    ``True`` **only** when :attr:`~tos.nontrade.records.SplitTransformationSpec.unit_spec`
    and :attr:`~tos.nontrade.records.SplitTransformationSpec.rounding_rule` are both
    present. An **empty / whitespace-only token is also rejected**: a blank string
    specifies nothing, and the ADR requires the units and rounding to be *exact*. (Design
    #21 §5.2 phrases the rule as "both not-``None``"; rejecting the blank token is a
    strictly narrower reading in the same direction and can only fail closed.)

    The *values* the tokens name are policy content — this package validates neither the
    unit system nor the rounding mode, and hardcodes no numeric rounding increment (design
    #21 §8.0). [SAFE-025]

    Args:
        spec: The injected split transformation spec (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff both the unit spec and the rounding rule are explicitly declared.
    """
    if spec is None:
        return False
    unit_spec = spec.unit_spec
    rounding_rule = spec.rounding_rule
    if unit_spec is None or rounding_rule is None:
        return False
    return bool(unit_spec.strip()) and bool(rounding_rule.strip())


def transformation_residual_conservative(spec: SplitTransformationSpec | None) -> bool:
    """Whether the transformation residual is explicit and conservative (ADR §11 line 240).

    §11 line 233 distinguishes the fractional entitlement from the tradable whole quantity,
    and §11 line 240 requires the residual to be **explicit and capacity-consuming** where
    the transformed state cannot be represented exactly. §11 line 238: "Economic
    equivalence SHALL NOT be assumed from a theoretical ratio" — broker rounding,
    cash-in-lieu, fees, taxes, and margin all change risk, and hiding them inside an assumed
    ratio is the failure this predicate blocks.

    ``True`` **only** when
    :attr:`~tos.nontrade.records.SplitTransformationSpec.fractional_residual` **and**
    :attr:`~tos.nontrade.records.SplitTransformationSpec.cash_in_lieu` are both present,
    finite, and non-negative. A ``None`` residual is a **hidden** residual (UNKNOWN, never
    zero) and fails closed; an exact transformation declares an explicit zero rather than
    omitting the field.

    The *capacity consumption* of the residual is rcl's (§10 line 217); this predicate
    proves only that the residual was declared rather than netted away (design #21 §3.5).
    [SAFE-025]

    Args:
        spec: The injected split transformation spec (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff both residual magnitudes are explicit and non-negative.
    """
    if spec is None:
        return False
    return _is_present_non_negative(
        spec.fractional_residual
    ) and _is_present_non_negative(spec.cash_in_lieu)


# ===========================================================================
# §5.3 correction / reversal idempotency + lineage
# (ADR §10 line 219 · §16 line 313; NT-EV-010; NT-AC-010)
# ===========================================================================


def correction_reversal_idempotent(
    incoming: CorrectionReversalRecord | None,
    prior: CorrectionReversalRecord | None,
    original_retained: bool | None,
) -> CorrectionReversalOutcome:
    """Classify a correction / reversal application (ADR §10 line 219; NT-EV-010).

    §10 line 219 verbatim: "History SHALL be corrected by new versioned facts, not
    destructive overwrite. A correction or reversal is a **new event linked to** the event
    it supersedes." §16 line 313: "local history SHALL preserve both the original
    observation and correcting event." §19 line 366: replay SHALL "reapply events only
    through idempotent version checks." §16 line 311: a component "SHALL not relabel an
    unexplained position change as a correction merely to make reconciliation pass."

    **Three pre-gates, then the canonical classifier** (design #21 §4.6, in order):

    1. no ``incoming`` at all ⇒ ``REJECTED_UNKNOWN`` (nothing to decide, fail closed);
    2. ``incoming.supersedes_ref is None`` ⇒ ``REJECTED_NO_LINEAGE`` (§16 line 311);
    3. ``original_retained is not True`` ⇒ ``REJECTED_OVERWRITE`` (§10 line 219). The flag
       is **positive polarity**: ``None`` (unknown) and ``False`` (overwritten) both
       reject, and a truthy non-``bool`` forged past the annotation is not proof;
    4. ``prior is None`` ⇒ **``APPLIED_ONCE``** — the legitimate *first* correction. This
       branch must precede the classifier: with no prior there is no pair to classify, and
       routing it through ``classify_record_pair`` would return ``NOT_COMPARABLE`` and
       reject every legitimate first correction forever (the v1.0 C2 defect — an
       ``APPLIED_ONCE`` that was structurally unreachable).

    Then the **exhaustive** ``classify_record_pair`` mapping (design #21 §4.6 /
    :data:`_RECORD_PAIR_OUTCOME`), called with the measured canonical signature — four
    positional arguments plus two keyword-only idempotency ids
    (``canonical/record_pair.py:52``)::

        IDEMPOTENT_DUP     -> IDEMPOTENT_REPLAY   (effect + 0, harmless re-apply)
        CRITICAL_CONFLICT  -> REJECTED_CONFLICT   (same PRIMARY id, different bytes)
        DIVERGENT_EMISSION -> REJECTED_CONFLICT   (same IDEMPOTENCY key, different bytes)
        DISTINCT           -> REJECTED_UNKNOWN
        NOT_COMPARABLE     -> REJECTED_UNKNOWN

    **Only ``APPLIED_ONCE`` increases the economic effect count** (design #21 §4.6): a
    correction applied N >= 2 times yields ``APPLIED_ONCE`` once and ``IDEMPOTENT_REPLAY``
    thereafter, so the cumulative effect count is exactly 1 (re-application is harmless).
    The **two** forgery axes are distinct canonical kinds and both fold to
    ``REJECTED_CONFLICT``: both records are preserved, there is no last-write-wins merge
    (``canonical/record_pair.py:68``), and neither is ever silently double-applied.

    **Anchored directly on the canonical primitive** (design #21 §0.4e): the iap
    ``ConsumptionOutcome.IDEMPOTENT_REPLAY`` (authorization-token single-use consumption)
    and rcl ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command) are **different
    propositions** on different axes, so neither sibling is imported or consumed — the
    phantom edge is blocked at the source. The rcl recomputation of capacity from the
    corrected envelope (§16 line 313) is likewise rcl's, not this predicate's.
    [SAFE-020; SAFE-051; SAFE-052]

    Args:
        incoming: The incoming correction / reversal record.
        prior: The existing record sharing ``incoming``'s idempotency key, or ``None`` when
            this is the first correction in the series.
        original_retained: Whether the original observation is retained append-only
            (**positive polarity**: only ``True`` passes).

    Returns:
        The :class:`~tos.nontrade.vocabulary.CorrectionReversalOutcome`.
    """
    if incoming is None:
        return CorrectionReversalOutcome.REJECTED_UNKNOWN
    if incoming.supersedes_ref is None:
        return CorrectionReversalOutcome.REJECTED_NO_LINEAGE
    if original_retained is not True:
        return CorrectionReversalOutcome.REJECTED_OVERWRITE
    if prior is None:
        return CorrectionReversalOutcome.APPLIED_ONCE
    kind = classify_record_pair(
        incoming.correction_id,
        incoming.canonical_digest,
        prior.correction_id,
        prior.canonical_digest,
        a_idempotency_id=incoming.idempotency_key,
        b_idempotency_id=prior.idempotency_key,
    )
    # Exhaustive by construction (a §7 property locks the mapping against RecordPairKind);
    # the ``.get`` default is a defence-in-depth restrictive residue for a future member.
    return _RECORD_PAIR_OUTCOME.get(kind, CorrectionReversalOutcome.REJECTED_UNKNOWN)


# ===========================================================================
# §5.4 label-grants-nothing (ADR §6 line 144; core substrate)
# ===========================================================================


def nontrade_authority_effect_all_false(
    effect: NonTradeAuthorityEffect | None,
) -> bool:
    """Whether a non-trade label / record grants no authority (ADR §6 line 144).

    §6 line 144 verbatim: "**No workflow state by itself releases capacity, closes an
    instrument, proves final quantity, or grants authority.**" §6 line 142: "``APPLIED_LOCAL``
    is not proof that the broker or venue applied the same effect." §6 line 143:
    "``RECONCILED`` requires evidence sufficient under ADR-002-006" — a label never
    substitutes for the recon proof. §10 line 217 / §10 line 221 / §15 line 299 extend the
    seal to capacity mutation, capacity release, and transmission.

    :class:`~tos.nontrade.records.NonTradeAuthorityEffect` already rejects any ``True`` flag
    at construction, so on the normal validation path this predicate is unconditionally
    ``True`` for every constructible block **and for every workflow state, including
    ``RECONCILED``**. It exists as **defence in depth**: ``model_construct`` skips
    validators, so a forged block can carry a ``True`` — or a truthy non-``bool`` such as
    ``1`` / ``"yes"`` / ``[1]`` — flag. The re-check therefore demands every declared flag
    be the singleton ``False``, so a truthy non-``bool`` is rejected too, and a ``None``
    block (nothing to prove) is ``False`` rather than a vacuous pass.
    [SAFE-011; SAFE-041]

    Args:
        effect: The authority-effect block to re-check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every declared flag is the singleton ``False``.
    """
    if effect is None:
        return False
    field_names = type(effect).model_fields
    if not field_names:
        # An effect block that declares no flag proves nothing (∅-vacuous guard).
        return False
    return all(getattr(effect, name, None) is False for name in field_names)


# ===========================================================================
# §5.5 the single NonTradeDisposition producer (design #21 C1)
# ===========================================================================


def nontrade_disposition(
    *,
    envelope_complete: bool,
    netting_absent: bool,
    polarity_coherent: bool | None,
    units_and_rounding_explicit: bool | None,
    residual_conservative: bool | None,
    correction_outcome: CorrectionReversalOutcome | None,
    lineage_preserved: bool | None,
    effective_window_blocks: bool | None,
    material_change_triggers_present: bool | None,
    event_is_material: bool | None,
    field_confidences: frozenset[str],
    admissibility: str | None,
    protective_action_may_proceed: bool | None,
    injected_worst_intermediate_risk: CanonicalDecimal | None,
    injected_credible_space_bounded: bool | None,
    injected_union_capacity_known: bool | None,
) -> NonTradeDisposition:
    """Fold every non-trade signal into one disposition (design #21 §5.5; **sole producer**).

    This is the **only** producer of
    :class:`~tos.nontrade.vocabulary.NonTradeDisposition` (design #21 C1): every row of the
    §4.7 void table folds through it, so no guard is left delegating to an ownerless
    "handled elsewhere" step — the v1.0 defect in which the vocabulary existed but nothing
    returned it.

    **Five ranks, a total order, first match wins** (most conservative first)::

        1  a CONFLICTED field confidence, or REJECTED_CONFLICT   -> NONTRADE_CONFLICTED
        2  an UNKNOWN field confidence, or REJECTED_UNKNOWN      -> NONTRADE_QUARANTINED_UNKNOWN
        3  the admissibility token is neither ADMISSIBLE nor
           RESTRICTED_PROTECTIVE_ONLY (INADMISSIBLE / UNKNOWN /
           None / any unrecognized token) — UNCONDITIONALLY     -> NONTRADE_TRAPPED
        4  any positive conjunct unproven                        -> NONTRADE_BLOCK_NEW_RISK
        5  every conjunct positively proven AND the token is
           exactly ADMISSIBLE                                    -> NONTRADE_ADMISSIBLE

    **Rank 3 is unconditional on purpose (design #21 §5.5).** Gating it on
    ``protective_action_may_proceed is not True`` would let an **inconsistent injection**
    (``INADMISSIBLE`` together with ``True``) *relax* a trap into a block. The venue
    producer ``protective_label_no_bypass`` (``venue/predicates.py:599``) returns ``True``
    only when the exact admissibility is ``ADMISSIBLE`` or ``RESTRICTED_PROTECTIVE_ONLY``,
    so the combination cannot arise through venue — but this package imports no sibling and
    therefore trusts no injected pair, absorbing the inconsistency conservatively.
    ``protective_action_may_proceed`` consequently **cannot change this function's result at
    all**; it is deleted below and a §7 property asserts the invariance. (Design #21 §5.5
    keeps it in the signature so the protective coordinate travels with the decision for the
    consuming runtime; §4.4 forbids the disposition itself from ever authorizing a
    protective action.)

    ``RESTRICTED_PROTECTIVE_ONLY`` deliberately lands at rank **4**, not rank 3 (design #21
    M6): ordinary new risk is blocked, but the exposure is *not* trapped — a separately
    authorized protective / recovery action may still proceed through the **venue-owned**
    four-condition ``protective_label_no_bypass``, which this package consumes and never
    re-decides (§18 line 348 "permit **only** newly authorized recovery or protective
    action").

    **The positive conjunction of rank 5** (every element an identity / ``is True`` proof —
    ``NONTRADE_ADMISSIBLE`` is never a fall-through residue, the #16 CRITICAL lesson):

    * ``envelope_complete is True`` and ``netting_absent is True`` (§9);
    * *if a transformation accompanies the event* (any of the three transformation verdicts
      is not ``None``): ``polarity_coherent``, ``units_and_rounding_explicit``, and
      ``residual_conservative`` are **each** ``is True`` (§11);
    * *if a correction accompanies the event*: ``correction_outcome`` is ``APPLIED_ONCE``
      or ``IDEMPOTENT_REPLAY`` (§10 line 219);
    * ``lineage_preserved is True`` (§12) and ``effective_window_blocks is True`` (§8);
    * unless non-materiality is **positively proven** (``event_is_material is False``),
      ``material_change_triggers_present is True`` (§10 line 221 — "Unknown materiality is
      material", so ``None`` grants no exemption);
    * ``injected_credible_space_bounded is True`` and ``injected_worst_intermediate_risk``
      is a present finite magnitude (are, §9) and ``injected_union_capacity_known is True``
      (rcl);
    * ``field_confidences`` is **non-empty** and every member is ``CORROBORATED`` (recon,
      §7). The non-emptiness is the same ∅ structural guard as
      :func:`transition_envelope_complete`: ``∅ <= {CORROBORATED}`` is vacuously ``True``,
      and "no field has any evidence" must never read as "every field is corroborated"
      (design #21 §5.1 C1, applied to the evidence axis).

    A new signal added to this contract must be woven into the conjunction explicitly; until
    it is, its ``None`` default falls to rank 4 and blocks **conservatively**.

    **A disposition grants nothing** (§6 line 144 / §4.4): even ``NONTRADE_ADMISSIBLE``
    releases no capacity, transmits nothing, issues no admissibility, and mutates no
    capacity — the consuming runtime (rcl remap-admission, venue invalidation, final
    egress) enforces. The return value is truthy-untestable; the consume gate is
    ``disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE``.

    Args:
        envelope_complete: :func:`transition_envelope_complete` output.
        netting_absent: :func:`favorable_netting_absent` output.
        polarity_coherent: :func:`split_polarity_coherent` output, or ``None`` when no
            transformation accompanies the event.
        units_and_rounding_explicit: :func:`transformation_units_and_rounding_explicit`
            output, or ``None``.
        residual_conservative: :func:`transformation_residual_conservative` output, or
            ``None``.
        correction_outcome: :func:`correction_reversal_idempotent` output, or ``None`` when
            no correction accompanies the event.
        lineage_preserved: :func:`instrument_lineage_preserved` output.
        effective_window_blocks: :func:`effective_window_blocks_new_risk` output.
        material_change_triggers_present: :func:`material_change_trigger_nonempty` output.
        event_is_material: Whether the event is material. ``None`` is **material**
            (venue §5.8 "Unknown materiality is material"); the exemption needs ``is False``.
        field_confidences: The injected recon ``FieldConfidenceClass`` **tokens** for the
            event's material fields.
        admissibility: The injected venue ``OrderAdmissibilityResult`` **token**.
        protective_action_may_proceed: The injected venue ``protective_label_no_bypass``
            output. Carried for the consuming runtime; it **cannot** relax any rank here.
        injected_worst_intermediate_risk: The injected are ``worst_intermediate_risk``.
        injected_credible_space_bounded: The injected are ``credible_space_bounded``.
        injected_union_capacity_known: Whether the injected rcl credible-union capacity is
            known (not UNKNOWN).

    Returns:
        The :class:`~tos.nontrade.vocabulary.NonTradeDisposition`.
    """
    # Structurally inert here (see the rank-3 rationale above); a §7 property asserts that
    # the result is invariant under every value of this argument.
    del protective_action_may_proceed

    # --- rank 1: contradiction ---------------------------------------------------
    if (
        FIELD_CONFIDENCE_CONFLICTED in field_confidences
        or correction_outcome is CorrectionReversalOutcome.REJECTED_CONFLICT
    ):
        return NonTradeDisposition.NONTRADE_CONFLICTED

    # --- rank 2: unattributable / undecidable ------------------------------------
    if (
        FIELD_CONFIDENCE_UNKNOWN in field_confidences
        or correction_outcome is CorrectionReversalOutcome.REJECTED_UNKNOWN
    ):
        return NonTradeDisposition.NONTRADE_QUARANTINED_UNKNOWN

    # --- rank 3: no fresh exact decision => trapped (unconditional) ---------------
    if admissibility not in ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS:
        return NonTradeDisposition.NONTRADE_TRAPPED

    # --- rank 5 premises (positive conjunction) ----------------------------------
    transformation_present = not (
        polarity_coherent is None
        and units_and_rounding_explicit is None
        and residual_conservative is None
    )
    transformation_proven = not transformation_present or (
        polarity_coherent is True
        and units_and_rounding_explicit is True
        and residual_conservative is True
    )
    correction_proven = (
        correction_outcome is None
        or correction_outcome in _ACCEPTABLE_CORRECTION_OUTCOMES
    )
    materiality_conjunct = (
        event_is_material is False or material_change_triggers_present is True
    )
    risk_known = (
        injected_worst_intermediate_risk is not None
        and injected_worst_intermediate_risk.is_finite()
    )
    evidence_corroborated = bool(field_confidences) and field_confidences <= frozenset(
        {FIELD_CONFIDENCE_CORROBORATED}
    )

    positively_proven = (
        envelope_complete is True
        and netting_absent is True
        and transformation_proven
        and correction_proven
        and lineage_preserved is True
        and effective_window_blocks is True
        and materiality_conjunct
        and injected_credible_space_bounded is True
        and risk_known
        and injected_union_capacity_known is True
        and evidence_corroborated
    )

    # --- rank 5: positive conjunction AND the exact ADMISSIBLE identity ----------
    if positively_proven and admissibility == ORDER_ADMISSIBILITY_ADMISSIBLE:
        return NonTradeDisposition.NONTRADE_ADMISSIBLE

    # --- rank 4: the restrictive residue (RESTRICTED_PROTECTIVE_ONLY lands here) --
    return NonTradeDisposition.NONTRADE_BLOCK_NEW_RISK


# ===========================================================================
# §6.1 instrument identity lineage (ADR §12; NT-EV-003 substrate, predicate-only)
# ===========================================================================


def instrument_lineage_preserved(
    old_route_identity: str | None,
    new_route_identity: str | None,
    admissibility: str | None,
    protective_action_may_proceed: bool | None,
    identity_transition_final: bool | None,
) -> bool:
    """Whether instrument identity lineage is preserved (ADR §12; NT-EV-003).

    §12 line 246: "Symbol text is not instrument identity." §12 line 248: "Both identities
    remain active in the transition envelope until broker and reference-data evidence
    establish the final mapping." §12 line 250: an instrument "SHALL not be silently
    reassigned". §10 line 221: "Every material event, correction, or reversal SHALL
    invalidate affected ADR-002-019 Venue Constraint Snapshots and Order Admissibility
    Decisions ... requires a fresh exact order decision before future transmission."

    Two positive conjuncts:

    * **old / new coexistence** — while ``identity_transition_final is not True`` (the
      positive-polarity gate: ``None`` is *not final*), **both** route identities must be
      present; one alone is a silent reassignment. Once the transition is positively final,
      the new identity must still be present.
    * **a fresh exact decision** — the injected venue token folded **three ways** (design
      #21 §6.1 M6): ``ADMISSIBLE`` satisfies the ordinary conjunct;
      ``RESTRICTED_PROTECTIVE_ONLY`` does **not** (it permits no ordinary new risk,
      ADR-002-019 §1 line 29 / §19 line 426) yet is not a trap — :func:`nontrade_disposition`
      lands it at ``NONTRADE_BLOCK_NEW_RISK`` so a separately authorized protective action
      can still proceed; ``INADMISSIBLE`` / ``UNKNOWN`` / ``None`` / any unrecognized token
      is no fresh decision at all and the disposition returns ``NONTRADE_TRAPPED`` — trapped
      exposure, **never** zero risk (§12 line 252 "inability to exit SHALL be represented as
      trapped exposure ... not zero risk"; §22.4 rejects "expired or delisted means no
      risk").

    ``tos.nontrade`` re-decides **neither** the admissibility **nor** the four-condition
    protective carve-out: venue owns ``material_change_closure``
    (``venue/predicates.py:361``), ``OrderAdmissibilityResult``, and
    ``protective_label_no_bypass`` (``predicates.py:599``); this package produces the change
    trigger (:func:`material_change_trigger_nonempty`) and consumes the results (design #21
    §3.5). The route *fields* themselves (``InstrumentRouteFields``, ``venue/records.py:83``)
    likewise cross the seam as opaque injected identity tokens — this package holds sibling
    edge 0 and cannot name the type.

    ``protective_action_may_proceed`` is accepted so the venue coordinate travels with the
    decision, and is **structurally unable to relax this result**: it is deleted below and a
    §7 property asserts invariance under all three of its values. A protective label never
    bypasses a constraint (ADR-002-019 §19 line 426), and this predicate is not where that
    carve-out is decided. [SAFE-020; SAFE-030; SAFE-032]

    Args:
        old_route_identity: The injected old instrument route identity token.
        new_route_identity: The injected new instrument route identity token.
        admissibility: The injected venue ``OrderAdmissibilityResult`` token.
        protective_action_may_proceed: The injected venue ``protective_label_no_bypass``
            output — carried, never a relaxation here.
        identity_transition_final: Whether the identity transition is positively final
            (**positive polarity**: only ``True`` counts as final).

    Returns:
        ``True`` iff lineage coexistence and an ordinary fresh exact decision both hold.
    """
    # Deliberately inert: the protective path is a disposition-level coordinate, never a
    # relaxation of the ordinary lineage conjunct (design #21 §6.1 M6 / §4.4).
    del protective_action_may_proceed

    if identity_transition_final is True:
        if new_route_identity is None:
            return False
    elif old_route_identity is None or new_route_identity is None:
        # Not final => both identities remain active (§12 line 248); one alone would be a
        # silent reassignment (§12 line 250).
        return False
    return admissibility == ORDER_ADMISSIBILITY_ADMISSIBLE


# ===========================================================================
# §6.2 effective-time window (ADR §8; NT-EV-007 substrate, predicate-only)
# ===========================================================================


def effective_window_blocks_new_risk(
    earliest_credible_boundary: str | None,
    latest_completion_boundary: str | None,
    time_freshness: str | None,
    source_disagreement_bounded: bool | None,
) -> bool:
    """Whether the effective-time window is established (ADR §8; NT-EV-007).

    §8 line 173: a system SHALL "block new risk before the earliest credible effective
    boundary and remain restricted through the latest credible completion boundary". §8
    line 171: the announcement, observation, record, ex, effective, payable, and settlement
    times "SHALL NOT" be collapsed "into one 'corporate action date'" — which is why
    :class:`~tos.nontrade.records.NonTradeEventRecord` keeps seven separate time fields. §8
    line 175: clock recovery or a later source update SHALL NOT grant retroactive authority
    to an action denied during the uncertainty interval.

    ``True`` **only** as one positive conjunction: both boundaries are present, the injected
    time ``FreshnessVerdict`` token is exactly ``FRESH`` (``STALE`` / ``UNKNOWN`` /
    ``CONFLICTED`` / ``None`` all fail — the token is compared, never truthy-tested), and
    ``source_disagreement_bounded is True`` (positive polarity). Anything unestablished
    leaves the **whole** interval restricted, which is the conservative reading: an
    unbounded window blocks, it never opens.

    This package reads **no clock** (design #21 §7.2): the boundaries are opaque injected
    tokens and the trustworthiness verdict is time's (``freshness_verdict``
    ``time/predicates.py:375``; ``source_disagreement_within_bound`` ``:709``;
    ``recovery_generation_revives_nothing``). This predicate composes them and re-authors
    none. The numeric freshness / detection bounds are VP-002 injected and **null** in
    Phase 1 (``B_non_trade_event_detect`` / ``B_non_trade_reconcile``, both ``owner: TBD``),
    so nothing numeric is defaulted here. [SAFE-035; SAFE-023]

    Args:
        earliest_credible_boundary: The injected earliest credible effective boundary token.
        latest_completion_boundary: The injected latest credible completion boundary token.
        time_freshness: The injected time ``FreshnessVerdict`` token.
        source_disagreement_bounded: The injected time source-disagreement verdict
            (**positive polarity**: only ``True`` passes).

    Returns:
        ``True`` iff the window is positively established on all four conjuncts.
    """
    return (
        earliest_credible_boundary is not None
        and latest_completion_boundary is not None
        and time_freshness == FRESHNESS_VERDICT_FRESH
        and source_disagreement_bounded is True
    )


# ===========================================================================
# §6.3 material-change trigger non-emptiness (ADR §10 line 221; venue seam, M3)
# ===========================================================================


def material_change_trigger_nonempty(
    event_is_material: bool | None,
    change_triggers: frozenset[str],
) -> bool:
    """Whether a material event carries a non-empty invalidation trigger set (§10 line 221).

    §10 line 221: "Every material event, correction, or reversal SHALL invalidate affected
    ADR-002-019 Venue Constraint Snapshots and Order Admissibility Decisions ... requires a
    fresh exact order decision before future transmission."

    **Why this predicate exists (design #21 §6.3 M3 — an ∅ direction the v1.0 contract left
    open).** The invalidation closure is venue's, and its measured docstring
    (``venue/predicates.py:361``) states: "An **empty** ``change_triggers`` yields the empty
    set — no change, nothing invalidated (the availability side)." That is correct **on the
    venue side**: a valid decision must not be spuriously invalidated. But it means that if
    this package recognizes a material event and hands venue an **empty** trigger set, venue
    invalidates nothing and every stale Venue Constraint Snapshot and Order Admissibility
    Decision survives — a head-on fail-open against §10 line 221. The non-emptiness is
    therefore **this** package's obligation to prove, on **this** side of the seam.

    **Polarity — "Unknown materiality is material".** The exemption is granted **only** on
    the positive proof ``event_is_material is False``. Everything else — ``is True`` **and
    ``None``** — is treated as material and requires a non-empty ``change_triggers``.
    ``is not True`` must **never** be used to exempt: a ``None`` would pass it and skip the
    invalidation wholesale. The rule is measured from venue §5.8 "Unknown materiality is
    material" (``venue/predicates.py:379``; the same phrase at ``:137``). Note that
    ``event_is_material`` is a **relaxation-condition** field whose safe value is ``True``,
    not one of the negative-polarity fields the series gates with ``is False`` — Phase-1
    nontrade has **zero** of those (design #21 M7).

    This package does **not** compute the closure: the invalidation reach, the unproven-edge
    expansion, and the admissibility issuance are all venue's (design #21 §3.5). It judges
    only that the trigger set it is about to hand over is non-empty. [SAFE-020; SAFE-030;
    SAFE-032]

    Args:
        event_is_material: Whether the event is material. Only the positive ``False``
            exempts; ``True`` and ``None`` both require triggers.
        change_triggers: The trigger nodes to hand to venue ``material_change_closure``.

    Returns:
        ``True`` iff non-materiality is positively proven, or the trigger set is non-empty.
    """
    if event_is_material is False:
        # Non-materiality positively proven: an empty trigger set is legitimate here, and
        # venue's empty closure is the availability side, not a fail-open.
        return True
    return len(change_triggers) > 0
