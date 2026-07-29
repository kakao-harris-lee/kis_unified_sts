"""Pure spg predicates (design #12 §5, §6).

The EV-L1 *functions* the property tests verify — none is a stored field; all are computed
on demand over **injected** state (design #12 §0.2: no clock, no egress, no persistence, no
capacity mutation, no activation commit — those are runtime EV-L2/L3). Every predicate is
conservative / **fail-closed** (design #12 §4.1): a missing / undeclared / mixed / stale /
unproven / expired input never becomes ``valid`` / ``COMMITTABLE`` / ``True`` — live
admission requires **positive proof**, and there is deliberately no permissive fallthrough.

Produced-value seam (design #12 §3.4): spg imports **none** of its seven consumers
(``tos.liveauth`` / ``tos.authority`` / ``tos.rcl`` / ``tos.time`` / ``tos.capsule`` /
``tos.evidence`` / ``tos.protective``) — it produces plain ``bool`` / ``str`` / ``int`` /
``CanonicalDecimal`` outputs their already-ratified predicates consume as injected
``bool | None`` / ``str | None`` / ``int | None`` flags. Polarity / fail-closed alignment:

* :func:`hard_and_runtime_versions_match` ``True`` <=> liveauth ``continuous_validity`` may
  hold its ``hard_and_runtime_versions_match`` condition (``state.py:135``); ``False`` fails
  it closed.
* :func:`envelope_not_expanded` ``True`` <=> liveauth ``Safe053VariantAttestation``'s
  ``hard_safety_envelope_not_expanded`` (``state.py:164``).
* :func:`envelope_profile_covers_enlarged` ``True`` <=> liveauth ``InPlaceExpansionInputs``'s
  ``envelope_profile_covers_enlarged`` (``state.py:205``).
* the four :class:`~tos.spg.records.ActivationInputs` bools feed liveauth
  ``atomic_activation_ok`` (``predicates.py:454``); spg's own ``activation_atomic`` folds the
  same four to an :class:`~tos.spg.vocabulary.ActivationVerdict` (design #12 §5.3 dual-layer).
* :func:`envelope_incompatible` ``True`` -> authority ``degraded_lease_invalidated``'s
  ``hard_envelope_incompatible`` ``is not False`` invalidation (``predicates.py:640/701``).
* :func:`envelope_limit_operand` / :func:`profile_limit_operand` produce the **two operand
  scalars**; the authoritative ``min`` is rcl ``effective_limit`` (``vector.py:139``) — spg
  performs **no** min (design #12 §3.5 / MAJOR-1).

Numbers are never hardcoded: every bound / interval / age is an injected parameter, and a
``None`` bound fails closed (design #12 §8). Broker-agnostic: no predicate names a concrete
broker (design #12 §0.1). spg activates / authorizes / transmits / releases **nothing** —
representation != enforcement (design #12 §4.5).

Pure module: ``pydantic`` + stdlib + ``tos.spg`` only; no ``shared.*``, no sibling ``tos.*``
beyond the core ``tos.canonical`` / ``tos.ordering`` (design #12 §0.3).
"""

from __future__ import annotations

from tos.canonical import CanonicalDecimal
from tos.spg.records import (
    ActivationInputs,
    ActivationRecord,
    ChangeDirectionInputs,
    CompatibilityQuery,
    ConsumerCompatibilityManifest,
    HardSafetyEnvelope,
    RestrictiveOverrideInputs,
    RollbackInputs,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
    SemanticValidationInputs,
    SemanticValidationResult,
)
from tos.spg.vocabulary import (
    BREAK_GLASS_ALLOWED_ACTIONS,
    MODELED_BUNDLE_MEMBERS,
    ActivationVerdict,
    BreakGlassAction,
    BundleMemberKind,
    ChangeDirection,
    EnvelopeState,
    ProfileState,
    ValidationReason,
)

# ===========================================================================
# §2.2 — lifecycle transition tables (non-revival; design #12 §2.2)
# ===========================================================================

#: The exact ADR-002-014 §12.1 (line 325-334) envelope arrows — the ONLY allowed
#: transitions. Terminal states ({RESTRICTED, SUPERSEDED, REVOKED, REJECTED}) have no
#: outgoing arrow to ACTIVE (§12.1 line 334 non-revival). Transcribed verbatim and
#: double-checked (the #6 v1.2 erratum lesson: an arrow table must match the ADR).
_ENVELOPE_TRANSITIONS: frozenset[tuple[EnvelopeState, EnvelopeState]] = frozenset(
    {
        (EnvelopeState.DRAFT, EnvelopeState.VALIDATED),
        (EnvelopeState.VALIDATED, EnvelopeState.APPROVED),
        (EnvelopeState.APPROVED, EnvelopeState.STAGED),
        (EnvelopeState.STAGED, EnvelopeState.ACTIVE),
        (EnvelopeState.DRAFT, EnvelopeState.REJECTED),
        (EnvelopeState.VALIDATED, EnvelopeState.REJECTED),
        (EnvelopeState.APPROVED, EnvelopeState.REJECTED),
        (EnvelopeState.STAGED, EnvelopeState.REJECTED),
        (EnvelopeState.ACTIVE, EnvelopeState.RESTRICTED),
        (EnvelopeState.ACTIVE, EnvelopeState.SUPERSEDED),
        (EnvelopeState.ACTIVE, EnvelopeState.REVOKED),
    }
)

#: The exact ADR-002-014 §12.2 (line 338-348) profile arrows. Terminal states ({SUSPENDED,
#: SUPERSEDED, REVOKED, EXPIRED, REJECTED}) have no outgoing arrow to ACTIVE (§12.2 line 348
#: non-revival + no-content-reuse). Verbatim + double-checked.
_PROFILE_TRANSITIONS: frozenset[tuple[ProfileState, ProfileState]] = frozenset(
    {
        (ProfileState.DRAFT, ProfileState.VALIDATED),
        (ProfileState.VALIDATED, ProfileState.APPROVED),
        (ProfileState.APPROVED, ProfileState.STAGED),
        (ProfileState.STAGED, ProfileState.ACTIVATION_READY),
        (ProfileState.ACTIVATION_READY, ProfileState.ACTIVE),
        (ProfileState.DRAFT, ProfileState.REJECTED),
        (ProfileState.VALIDATED, ProfileState.REJECTED),
        (ProfileState.APPROVED, ProfileState.REJECTED),
        (ProfileState.STAGED, ProfileState.REJECTED),
        (ProfileState.ACTIVATION_READY, ProfileState.REJECTED),
        (ProfileState.ACTIVE, ProfileState.SUSPENDED),
        (ProfileState.ACTIVE, ProfileState.SUPERSEDED),
        (ProfileState.ACTIVE, ProfileState.REVOKED),
        (ProfileState.ACTIVE, ProfileState.EXPIRED),
    }
)


def envelope_transition_allowed(frm: EnvelopeState, to: EnvelopeState) -> bool:
    """Whether an envelope ``frm -> to`` transition is allowed (ADR §12.1; design #12 §2.2).

    ``True`` **only** for an arrow in :data:`_ENVELOPE_TRANSITIONS`. No terminal state
    (``RESTRICTED`` / ``SUPERSEDED`` / ``REVOKED`` / ``REJECTED``) returns to ``ACTIVE``
    (§12.1 line 334 non-revival). Pure set membership; every unlisted pair is ``False``.
    """
    return (frm, to) in _ENVELOPE_TRANSITIONS


def profile_transition_allowed(frm: ProfileState, to: ProfileState) -> bool:
    """Whether a profile ``frm -> to`` transition is allowed (ADR §12.2; design #12 §2.2).

    ``True`` **only** for an arrow in :data:`_PROFILE_TRANSITIONS`. No terminal state
    (``SUSPENDED`` / ``SUPERSEDED`` / ``REVOKED`` / ``EXPIRED`` / ``REJECTED``) returns to
    ``ACTIVE`` (§12.2 line 348 non-revival + no-content-reuse). Pure set membership.
    """
    return (frm, to) in _PROFILE_TRANSITIONS


# ===========================================================================
# §5.1 — envelope dominance / non-silent expansion (SPG-EV-001 substrate)
# ===========================================================================

#: The ADR-002-014 §11 step 3 (**line 304**) "boundary inclusion" tokens carried by
#: :attr:`~tos.spg.records.GovernedDimensionLimit.boundary`.
BOUNDARY_INCLUSIVE = "INCLUSIVE"
BOUNDARY_EXCLUSIVE = "EXCLUSIVE"

#: The closed set of boundary tokens this model can evaluate. Membership is **exact** —
#: no casefolding, no whitespace stripping — because normalizing an unknown declaration
#: into a known one is precisely how a permission gets granted by a typo (design #12
#: §4.1). Anything outside this set is unreadable, and an unreadable containment rule is
#: unproven containment (:func:`_exceeds_envelope_maximum`), never a lenient default.
BOUNDARY_TOKENS: frozenset[str] = frozenset({BOUNDARY_INCLUSIVE, BOUNDARY_EXCLUSIVE})


def _exceeds_envelope_maximum(
    profile_value: CanonicalDecimal,
    envelope_max: CanonicalDecimal,
    boundary: str | None,
) -> bool:
    """Boundary-inclusion-aware breach test (ADR §11 step 3 line 304; design §5 H-2).

    ADR-002-014 §11 step 3 (line 304) SHALL-validates "**boundary inclusion**" and
    SPG-AC-002 (line 621) requires those semantic defects to "fail closed before
    activation", so a magnitude comparison that ignores the declared boundary cannot
    honour either. Arms:

    * :data:`BOUNDARY_EXCLUSIVE` — the maximum is itself **outside** the permitted set,
      so ``profile == envelope_max`` is already a breach (``>=``). Before this seal that
      exact pair returned ``valid=True`` with an empty rejected-dimension set (the
      measured fail-open, EV-L2 pilot design §5 H-2 / C2 / SPG-08).
    * :data:`BOUNDARY_INCLUSIVE`, or an **undeclared** (``None``) boundary — the plain
      reading of a "maximum" admits equality (``>``); this is the pre-existing L1
      comparison, kept unchanged so an envelope declaring no boundary is not
      retroactively narrowed.
    * any **other** token — unrecognized, therefore not positive proof of inclusiveness,
      so it falls to the more restrictive ``>=`` arm (design #12 §4.1 fail-closed: there
      is no permissive fallthrough for an unreadable declaration). Recognition is exact
      membership in :data:`BOUNDARY_TOKENS` — no casefolding, no stripping — so
      ``"inclusive"``, ``"INCLUSIVE "`` and ``"OPEN"`` all take the restrictive arm
      rather than being normalized into a permission.

    A same-named envelope/profile pair whose ``boundary`` tokens *disagree* is separately
    rejected as ``UNIT_OR_MULTIPLIER_MISMATCH`` by :data:`_UNIT_METADATA_KEYS`, so the
    boundary read here is either agreed by both sides or declared only by the envelope —
    the constraint-owning side.

    Args:
        profile_value: The profile's concrete operating value.
        envelope_max: The envelope's concrete maximum for the same dimension.
        boundary: The envelope-declared boundary token (``None`` => inclusive maximum).

    Returns:
        ``True`` iff the profile value breaches the envelope maximum under ``boundary``.
    """
    if boundary is not None and boundary not in BOUNDARY_TOKENS:
        # An unreadable boundary declaration establishes nothing: the envelope states a
        # containment rule this code cannot evaluate, so containment is unproven for the
        # dimension regardless of the magnitudes. Breach, not a silent arm choice.
        return True
    if boundary == BOUNDARY_EXCLUSIVE:
        return profile_value >= envelope_max
    return profile_value > envelope_max


def profile_within_envelope(
    envelope: HardSafetyEnvelope | None,
    profile: RuntimeSafetyProfile | None,
) -> SemanticValidationResult:
    """Whether a profile stays within its Hard Safety Envelope (ADR §9; SPG-INV-001; §5.1).

    SPG-INV-001 line 153 verbatim: "No Runtime Safety Profile ... may exceed, redefine,
    disable, omit, or reinterpret a Hard Safety Envelope constraint." §1 line 21-26:
    ``... <= active Runtime Safety Profile <= active Hard Safety Envelope``. ``valid=True``
    **only** from positive proof of **all**:

    * ``envelope`` and ``profile`` are both present;
    * the profile pins **this** envelope (``target_envelope_id`` / ``target_envelope_generation``
      equal the envelope's id / generation — §10 line 281 "one exact envelope");
    * the envelope declares **at least one** governed dimension — an envelope with an empty
      governed-dimension set grants zero authority and cannot vacuously dominate **any**
      profile (§5.1 line 148 "빈 governed-dimension ⇒ vacuous-dominant 금지");
    * **(envelope -> profile coverage, SPG-INV-001 "omit" limb)** the profile supplies a
      concrete value for **every** envelope-declared (mandatory) dimension — a vacuously
      empty or partial profile that **omits** a mandatory dimension disables an envelope
      constraint (§9 line 257 mandatory dimensions; SPG-INV-001 line 153 "may [not] ...
      omit ..."), so a zero-iteration / partial profile can never pass vacuously;
    * **(profile -> envelope, no exceed / redefine)** every profile governed dimension is
      **declared** by the envelope (an undeclared dimension is zero-authority — the ∅-seal;
      design #12 §4.1 / §5.1), and every profile value and its envelope maximum are concrete
      and within the maximum **under the envelope's declared boundary inclusion**
      (:func:`_exceeds_envelope_maximum`; ADR §11 step 3 line 304, SPG-AC-002 line 621): an
      ``EXCLUSIVE`` boundary rejects ``value == max``, an ``INCLUSIVE`` / undeclared one
      admits it, and an unrecognized token falls to the restrictive arm;
    * the profile scope is a subset of the envelope's permitted scope.

    Any violation => ``valid=False`` with ``EXCEEDS_ENVELOPE`` and the offending dimensions
    (§9 line 264 "prohibited fallbacks, implicit defaults, wildcard scope"; an omitted
    mandatory dimension exceeds the envelope's mandatory coverage — the existing reason is
    reused, no new enum value, the vocabulary is the ratified verbatim set). A ``None``
    envelope / profile / id-mismatch fails closed. There is **no** "assume-within" path
    (design #12 §4.1 — the #6 fail-open REJECT seal).

    Args:
        envelope: The Hard Safety Envelope (``None`` => invalid).
        profile: The Runtime Safety Profile (``None`` => invalid).

    Returns:
        A rich :class:`~tos.spg.records.SemanticValidationResult` (valid + rejected dims +
        reason set).
    """
    if envelope is None or profile is None:
        return SemanticValidationResult(
            valid=False, reason_set=frozenset({ValidationReason.EXCEEDS_ENVELOPE})
        )
    if (
        profile.target_envelope_id is None
        or envelope.envelope_id is None
        or profile.target_envelope_id != envelope.envelope_id
        or profile.target_envelope_generation is None
        or envelope.envelope_generation is None
        or profile.target_envelope_generation != envelope.envelope_generation
    ):
        return SemanticValidationResult(
            valid=False, reason_set=frozenset({ValidationReason.EXCEEDS_ENVELOPE})
        )

    rejected: set[str] = set()

    # (envelope -> profile) SPG-INV-001 "omit" limb + empty-envelope zero-authority.
    declared_env_dims = {
        gdl.dimension
        for gdl in envelope.governed_dimensions
        if gdl.dimension is not None
    }
    if not declared_env_dims:
        # An envelope declaring zero governed dimensions grants zero authority — it cannot
        # vacuously dominate ANY profile, including an empty one (§5.1 line 148; SPG-INV-001).
        rejected.add("<no-envelope-dimensions>")
    for env_dim in declared_env_dims:
        # The profile may not OMIT a mandatory (envelope-declared) dimension — a missing /
        # None value disables an envelope constraint (SPG-INV-001 line 153 "omit"). This is
        # what rejects a vacuously empty or partial profile (the fix's core direction).
        if profile.value_for(env_dim) is None:
            rejected.add(env_dim)

    # (profile -> envelope) no exceed / redefine: every referenced dimension is declared and
    # within its maximum.
    for gdl in profile.governed_dimensions:
        dim = gdl.dimension
        if dim is None:
            rejected.add("<unnamed-dimension>")
            continue
        # Undeclared envelope dimension => zero authority (∅-dominant forbidden, §5.1).
        if not envelope.declares(dim):
            rejected.add(dim)
            continue
        env_max = envelope.max_for(dim)
        prof_value = gdl.profile_value
        if (
            env_max is None
            or prof_value is None
            or _exceeds_envelope_maximum(
                prof_value, env_max, envelope.boundary_for(dim)
            )
        ):
            rejected.add(dim)

    # Profile scope must be a subset of the envelope permitted scope.
    scope_ok = set(profile.scope) <= set(envelope.permitted_scope)

    if rejected or not scope_ok:
        if not scope_ok:
            rejected.add("<scope>")
        return SemanticValidationResult(
            valid=False,
            rejected_dimensions=frozenset(rejected),
            reason_set=frozenset({ValidationReason.EXCEEDS_ENVELOPE}),
        )
    return SemanticValidationResult(valid=True)


def envelope_bounded(
    envelope: HardSafetyEnvelope | None,
    profile: RuntimeSafetyProfile | None,
) -> bool:
    """The ``envelope_bounded`` seam bool (design #12 §3.4 / §5.3).

    ``True`` **only** when :func:`profile_within_envelope` is valid. Feeds liveauth
    ``atomic_activation_ok``'s ``envelope_bounded`` argument (``predicates.py:454``);
    ``None``-fed / invalid fails closed. Pure delegation — no min, no mutation.
    """
    return profile_within_envelope(envelope, profile).valid


def envelope_expansion_enlarges_nothing(
    old_envelope: HardSafetyEnvelope | None,
    new_envelope: HardSafetyEnvelope | None,
    active_profile: RuntimeSafetyProfile | None,
) -> bool:
    """Whether an envelope expansion enlarges no active profile (ADR §9 line 269; SPG-INV-007).

    §9 line 269 verbatim: "An envelope expansion does not enlarge existing profiles
    automatically." An immutable active profile's values cannot change when a wider envelope
    generation is activated, so ``True`` **only** when every active-profile governed value is
    still within the **old** envelope maximum (the profile was not silently expanded to the
    new, wider ceiling). Any ``None`` / undeclared / missing value fails closed. A profile
    value that has grown to exploit the new envelope => ``False``.

    The containment test is the **same** boundary-inclusion-aware comparison dominance
    uses (:func:`_exceeds_envelope_maximum`; ADR §11 step 3 line 304). Sharing it is
    load-bearing rather than tidy: this predicate feeds the ``envelope_not_expanded``
    seam bool that liveauth ``Safe053VariantAttestation`` (``state.py:164``) and its
    downstream consumers read, so a boundary-blind comparison here would report "nothing
    was enlarged" for a profile sitting exactly on an ``EXCLUSIVE`` maximum — the very
    value that maximum excludes — and hand a ``True`` to the re-arm path while dominance
    was separately rejecting the same pair (EV-L2 pilot design §5 H-2).

    Args:
        old_envelope: The pre-expansion envelope (``None`` => ``False``).
        new_envelope: The post-expansion envelope (present for symmetry / future use; the
            active profile's non-enlargement is proved against ``old_envelope``).
        active_profile: The active profile that must not silently enlarge (``None`` => ``False``).

    Returns:
        ``True`` iff the active profile stays within the old envelope (enlarges nothing).
    """
    if old_envelope is None or new_envelope is None or active_profile is None:
        return False
    for gdl in active_profile.governed_dimensions:
        dim = gdl.dimension
        if dim is None:
            return False
        old_max = old_envelope.max_for(dim)
        value = gdl.profile_value
        if (
            old_max is None
            or value is None
            or _exceeds_envelope_maximum(value, old_max, old_envelope.boundary_for(dim))
        ):
            return False
    return True


def envelope_not_expanded(
    old_envelope: HardSafetyEnvelope | None,
    new_envelope: HardSafetyEnvelope | None,
    active_profile: RuntimeSafetyProfile | None,
) -> bool:
    """The ``envelope_not_expanded`` seam bool (design #12 §3.4; SPG-INV-007).

    Alias-polarity producer for :func:`envelope_expansion_enlarges_nothing` that fills
    liveauth ``Safe053VariantAttestation.hard_safety_envelope_not_expanded``
    (``state.py:164``): ``True`` iff the active profile is not silently enlarged by the new
    envelope; ``None``-fed / unproven fails closed to ``False``.
    """
    return envelope_expansion_enlarges_nothing(
        old_envelope, new_envelope, active_profile
    )


def envelope_incompatible(
    active_envelope: HardSafetyEnvelope | None,
    presented_envelope_generation: int | None,
) -> bool:
    """Whether a presented envelope generation is incompatible (ADR §9; authority seam; §5.1).

    ``True`` (incompatible) when the active envelope is absent, the presented generation is
    absent, or they differ. Polarity: a ``True`` feeds authority
    ``degraded_lease_invalidated``'s ``hard_envelope_incompatible`` where
    ``is not False`` => invalidated (``predicates.py:640/701``) — so an incompatible /
    unknown envelope invalidates the dependent lease (fail-closed). Only a matching, concrete
    generation returns ``False`` (compatible).

    Args:
        active_envelope: The active Hard Safety Envelope (``None`` => incompatible).
        presented_envelope_generation: The generation presented for compatibility (``None``
            => incompatible).

    Returns:
        ``True`` iff the presented generation is incompatible with the active envelope.
    """
    if active_envelope is None or active_envelope.envelope_generation is None:
        return True
    if presented_envelope_generation is None:
        return True
    return active_envelope.envelope_generation != presented_envelope_generation


# ===========================================================================
# §5.2 — semantic validation (rich verdict; SPG-EV-002/003 substrate)
# ===========================================================================

#: The §11 step 3 semantic-metadata keys compared between an envelope dimension and the
#: same-named profile dimension (a mismatch => UNIT_OR_MULTIPLIER_MISMATCH; design #12 §5.2).
#:
#: ADR-002-014 §11 step 3 (**line 304**) SHALL-validates "types, units, currencies,
#: multipliers, signs, **precision, rounding**, overflow, underflow, NaN, infinity, and
#: **boundary inclusion**", and SPG-AC-002 (**line 621**) requires that "Unit, multiplier,
#: currency, sign, precision, rounding, overflow, and cross-field semantic defects fail
#: closed before activation". ``precision`` / ``rounding`` / ``boundary`` are therefore
#: compared beside ``unit`` / ``multiplier`` / ``sign``: a profile stated at
#: ``precision=8`` / ``FLOOR`` / ``EXCLUSIVE`` is **not** semantically comparable with an
#: envelope stated at ``precision=2`` / ``HALF_UP`` / ``INCLUSIVE``, and before this seal
#: that pair validated ``valid=True`` with an empty reason set (a measured fail-open —
#: EV-L2 pilot design §5 H-2 / C2). The **ratified** reason vocabulary is reused verbatim
#: (no new :class:`~tos.spg.vocabulary.ValidationReason` value is minted) per design
#: §5 H-3's reason-vocabulary drift-lock.
_UNIT_METADATA_KEYS: tuple[str, ...] = (
    "unit",
    "multiplier",
    "sign",
    "precision",
    "rounding",
    "boundary",
)


def semantic_validation(
    bundle: SafetyConfigurationBundle | None,
    inputs: SemanticValidationInputs,
) -> SemanticValidationResult:
    """Validate a Safety Configuration Bundle (ADR §11 line 300-317; SPG-EV-002/003; §5.2).

    Folds the L1 spg-owned steps (computed from the nested envelope + profile) with the
    injected sibling-owned fold steps into a rich :class:`~tos.spg.records.SemanticValidationResult`
    (§11 line 315 "deterministic result **and reason set**"):

    * **step 6** — profile <= envelope (:func:`profile_within_envelope`): ``EXCEEDS_ENVELOPE``.
    * **step 3 semantic metadata** — a same-``dimension`` mismatch on any
      :data:`_UNIT_METADATA_KEYS` axis (unit / multiplier / sign / **precision** /
      **rounding** / **boundary**) between the envelope and profile:
      ``UNIT_OR_MULTIPLIER_MISMATCH`` (ADR §11 step 3 line 304 "precision, rounding ...
      boundary inclusion"; SPG-AC-002 line 621; EV-L2 pilot design §5 H-2 sealed the
      precision/rounding/boundary fail-open).
    * **step 3 numeric** — NaN / infinity / overflow is enforced **structurally at
      construction** by the ``allow_inf_nan=False`` pin tos owns explicitly on
      :class:`~tos.canonical.FrozenModel` (EV-L2 pilot design §5 H-1 — the pin is tos's,
      not an inherited pydantic default); the reused core
      :data:`~tos.canonical.CanonicalDecimal` adds only scale-normalization and carries no
      finite check of its own, so a non-finite limit is *unconstructable* — strictly
      stronger than a post-hoc reason. The ``OVERFLOW_UNDERFLOW_NAN_INFINITY`` reason stays
      in the vocabulary for any future non-model-sourced input (design #12 §5.2 deviation).
    * **step 12** — a duplicate governed dimension: ``UNKNOWN_OR_DUPLICATE_FIELD``
      (``extra="forbid"`` already rejects unknown *fields* at construction).
    * **step 5** — ``inputs.cross_field_consistent`` not ``True``: ``CROSS_FIELD_CONSTRAINT_VIOLATION``.
    * **step 11** — ``inputs.change_direction`` not ``RESTRICTIVE``: ``UNORDERABLE_DIRECTION``
      (unorderable / permissive / authority-increasing / ``None`` all fail; §11 line 317).
    * **step 2** — ``inputs.canonical_reproducible`` not ``True``: ``CANONICAL_DIGEST_IRREPRODUCIBLE``.
    * **step 9** — ``inputs.bundle_member_digests_match`` not ``True``: ``FLOATING_REFERENCE``.
    * **steps 1/7/8/10** — ``signature_and_revocation_ok`` / ``aggregate_effect_within`` /
      ``software_deployment_ok`` / ``time_validity_ok`` not ``True``:
      ``SCHEMA_INCOMPLETE_OR_DOWNGRADE`` (an injected precondition could not be established).

    A ``valid`` result carries an **empty** reason set; any defect => ``valid=False`` with a
    **non-empty** reason set (design #12 §4.2). ∅-seal: an absent bundle, or a bundle missing
    its envelope / profile, is invalid (``SCHEMA_INCOMPLETE_OR_DOWNGRADE``) — a vacuous
    "empty bundle is valid" is impossible.

    Args:
        bundle: The Safety Configuration Bundle (``None`` / incomplete => invalid).
        inputs: The injected fold-step results.

    Returns:
        The rich semantic-validation verdict.
    """
    reasons: set[ValidationReason] = set()
    rejected: set[str] = set()

    # ∅-seal: an absent / incomplete bundle can never be vacuously valid (§4.2 / §5.2).
    if bundle is None or bundle.envelope is None or bundle.profile is None:
        reasons.add(ValidationReason.SCHEMA_INCOMPLETE_OR_DOWNGRADE)
        return SemanticValidationResult(valid=False, reason_set=frozenset(reasons))

    envelope = bundle.envelope
    profile = bundle.profile

    # step 6 — profile <= envelope.
    dominance = profile_within_envelope(envelope, profile)
    if not dominance.valid:
        reasons.add(ValidationReason.EXCEEDS_ENVELOPE)
        rejected |= dominance.rejected_dimensions

    # step 3 semantic metadata — same-dimension unit / multiplier / sign / precision /
    # rounding / boundary mismatch (ADR §11 step 3 line 304; design §5 H-2).
    env_by_dim = {
        gdl.dimension: gdl
        for gdl in envelope.governed_dimensions
        if gdl.dimension is not None
    }
    for gdl in profile.governed_dimensions:
        dim = gdl.dimension
        if dim is None:
            continue
        env_gdl = env_by_dim.get(dim)
        if env_gdl is not None:
            for key in _UNIT_METADATA_KEYS:
                if getattr(env_gdl, key) != getattr(gdl, key):
                    reasons.add(ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH)
                    rejected.add(dim)
                    break

    # step 3 numeric — NaN / infinity is enforced structurally at construction by the
    # explicit allow_inf_nan=False pin tos owns on FrozenModel (EV-L2 pilot design §5 H-1);
    # the core CanonicalDecimal only scale-normalizes. A non-finite limit is
    # unconstructable, so no runtime magnitude here can be non-finite (design #12 §5.2
    # deviation — stronger guarantee).

    # step 12 — duplicate governed dimension (a covered-field-level ambiguity).
    for source in (envelope.governed_dimensions, profile.governed_dimensions):
        seen: set[str] = set()
        for gdl in source:
            if gdl.dimension is None:
                continue
            if gdl.dimension in seen:
                reasons.add(ValidationReason.UNKNOWN_OR_DUPLICATE_FIELD)
                rejected.add(gdl.dimension)
            seen.add(gdl.dimension)

    # step 5 — cross-field constraint (injected observation; fail-closed).
    if inputs.cross_field_consistent is not True:
        reasons.add(ValidationReason.CROSS_FIELD_CONSTRAINT_VIOLATION)

    # step 11 — direction; only RESTRICTIVE passes (unorderable folds here, §11 line 317).
    if inputs.change_direction is not ChangeDirection.RESTRICTIVE:
        reasons.add(ValidationReason.UNORDERABLE_DIRECTION)

    # step 2 — canonical reproducibility (injected).
    if inputs.canonical_reproducible is not True:
        reasons.add(ValidationReason.CANONICAL_DIGEST_IRREPRODUCIBLE)

    # step 9 — bundle-member digest resolution (injected).
    if inputs.bundle_member_digests_match is not True:
        reasons.add(ValidationReason.FLOATING_REFERENCE)

    # steps 1/7/8/10 — injected preconditions (signature / aggregate / software / time).
    if (
        inputs.signature_and_revocation_ok is not True
        or inputs.aggregate_effect_within is not True
        or inputs.software_deployment_ok is not True
        or inputs.time_validity_ok is not True
    ):
        reasons.add(ValidationReason.SCHEMA_INCOMPLETE_OR_DOWNGRADE)

    if reasons:
        return SemanticValidationResult(
            valid=False,
            rejected_dimensions=frozenset(rejected),
            reason_set=frozenset(reasons),
            bundle_digest=bundle.canonical_digest,
        )
    return SemanticValidationResult(valid=True, bundle_digest=bundle.canonical_digest)


def units_compatible(
    bundle: SafetyConfigurationBundle | None,
    inputs: SemanticValidationInputs,
) -> bool:
    """The ``units_compatible`` seam bool (design #12 §3.4 / §5.3).

    ``True`` **only** when :func:`semantic_validation` produces no
    ``UNIT_OR_MULTIPLIER_MISMATCH`` reason — i.e. every :data:`_UNIT_METADATA_KEYS` axis
    (unit / multiplier / sign / precision / rounding / boundary) agrees, so the two sides
    are semantically **comparable** (NaN / infinity is already unconstructable at the
    ``FrozenModel`` ``allow_inf_nan=False`` pin — §5.2 deviation). Feeds liveauth
    ``atomic_activation_ok``'s ``units_compatible`` argument (``predicates.py:454``).
    Fail-closed: an absent bundle => ``False``.
    """
    if bundle is None:
        return False
    result = semantic_validation(bundle, inputs)
    return ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH not in result.reason_set


# ===========================================================================
# §5.3 — atomic mixed-generation activation (SPG-EV-004 substrate)
# ===========================================================================


def activation_atomic(inputs: ActivationInputs) -> ActivationVerdict:
    """The spg-internal atomic-activation verdict (ADR §13; SPG-INV-005; design #12 §5.3).

    The dual-layer companion of liveauth ``atomic_activation_ok`` (which folds the same four
    seam bools): spg folds them to an :class:`~tos.spg.vocabulary.ActivationVerdict` for its
    own SPG-EV-004 property (design #12 §5.3, not a duplicate — spg verifies its own fold,
    liveauth folds for the re-arm gate). Order:

    * ``DEFERRED`` when staging / attestation collection is incomplete (``staging_complete``
      or ``attestation_complete`` not ``True``) — checked **first** because a not-yet-staged
      activation is not-live regardless of the four content bools (there is nothing to commit
      yet), pending the runtime quorum commit (§13 line 383). spg does **not** commit.
    * ``COMMITTABLE`` **only** when ``version_fully_active is True`` **and**
      ``mixed_versions_present is False`` **and** ``units_compatible is True`` **and**
      ``envelope_bounded is True`` (§13; SPG-INV-005 line 169 "Partial or mixed activation
      cannot create the union of permissions").
    * ``DENIED`` otherwise — mixed generation / partial / missing value / incompatible unit /
      unverifiable (§13 line 385). This is the most-restrictive default; there is **no**
      "assume-committable" path (design #12 §4.1).

    Args:
        inputs: The injected activation inputs (four seam bools + two staging gates).

    Returns:
        The activation verdict.
    """
    if inputs.staging_complete is not True or inputs.attestation_complete is not True:
        return ActivationVerdict.DEFERRED
    if (
        inputs.version_fully_active is True
        and inputs.mixed_versions_present is False
        and inputs.units_compatible is True
        and inputs.envelope_bounded is True
    ):
        return ActivationVerdict.COMMITTABLE
    return ActivationVerdict.DENIED


# ===========================================================================
# §5.4 — concurrent / stale-base activation (SPG-EV-005 substrate; ordering REUSE)
# ===========================================================================


def activation_serializable(
    candidate: ActivationRecord | None,
    current_active_generation: int | None,
) -> bool:
    """Whether an activation serializes against the current generation (ADR §15; SPG-INV-003).

    ``True`` **only** when ``candidate.predecessor_generation`` and
    ``current_active_generation`` are both concrete and **equal** — the candidate activates
    against the exact current predecessor (§15 line 415-422). A stale base
    (``predecessor != current``), a ``None`` predecessor, or a ``None`` current
    (``latest`` / local file / cache is not authority — SPG-INV-003 line 161) fails closed.
    Two successful activations for the same predecessor + overlapping scope resolve to one
    winner (no last-write-wins / partial patch); the append-only order itself is
    ``tos.ordering.compare_order`` (REUSE, design #12 §3.2).

    Args:
        candidate: The candidate activation record (``None`` => ``False``).
        current_active_generation: The current active generation (``None`` => ``False``).

    Returns:
        ``True`` iff the candidate's predecessor equals the current active generation.
    """
    if candidate is None or current_active_generation is None:
        return False
    if candidate.predecessor_generation is None:
        return False
    return candidate.predecessor_generation == current_active_generation


# ===========================================================================
# §5.5 — restrictive precedence + change direction (SPG-EV-006 substrate)
# ===========================================================================


def change_direction(inputs: ChangeDirectionInputs) -> ChangeDirection:
    """Classify a change's authority direction (ADR §5.9/§14; SPG-INV-008; design #12 §5.5).

    Restrictive-only classification requires **positive proof** on every axis; anything
    unproven / widening / semantics-altering folds to ``AUTHORITY_INCREASING`` (§5.9 line 145
    "When monotonic direction cannot be proven, the change is authority increasing"). Order:

    * ``previously_denied_now_permitted is True`` => ``AUTHORITY_INCREASING`` (§5.9 line 143).
    * ``all_dimensions_ordered_conservative`` not ``True`` => ``AUTHORITY_INCREASING`` — the
      unorderable / unproven fold (§11 line 317; the ``UNORDERABLE`` enum value was removed,
      v1.1 MINOR-1).
    * ``semantics_changed`` not ``False`` => ``AUTHORITY_INCREASING`` — a nominal reduction
      that changes unit / aggregation / scope-exclusion / fallback / protective-ownership /
      broker-capability / state-confidence / calculation semantics cannot be presumed
      restrictive (§14 line 405 verbatim).
    * ``any_dimension_widened is True`` => ``PERMISSIVE`` (§5.9 line 143).
    * ``all_narrowing_or_equal is True`` => ``RESTRICTIVE`` (the sole positive path; §14 line 393).
    * otherwise => ``AUTHORITY_INCREASING`` (fail-closed default — monotonic not proven).

    Args:
        inputs: The injected change-direction observations.

    Returns:
        The change direction.
    """
    if inputs.previously_denied_now_permitted is True:
        return ChangeDirection.AUTHORITY_INCREASING
    if inputs.all_dimensions_ordered_conservative is not True:
        return ChangeDirection.AUTHORITY_INCREASING
    if inputs.semantics_changed is not False:
        return ChangeDirection.AUTHORITY_INCREASING
    if inputs.any_dimension_widened is True:
        return ChangeDirection.PERMISSIVE
    if inputs.all_narrowing_or_equal is True:
        return ChangeDirection.RESTRICTIVE
    return ChangeDirection.AUTHORITY_INCREASING


def restrictive_override_admissible(
    direction: ChangeDirection,
    inputs: RestrictiveOverrideInputs,
) -> bool:
    """Whether a restrictive override is admissible (ADR §14 line 395-403; SPG-INV-008; §5.5).

    ``True`` **only** when ``direction is RESTRICTIVE`` **and** every preservation flag is
    positively ``True``: no auto-revert (§14 line 402), and capacity / orders / exposure /
    UNKNOWN / protective coverage all preserved (§14 line 401). A ``PERMISSIVE`` /
    ``AUTHORITY_INCREASING`` direction, or any ``None`` / ``False`` preservation flag, fails
    closed. A monotonic tightening that cannot be proven is classified
    ``AUTHORITY_INCREASING`` upstream (:func:`change_direction`) and rejected here. Economic
    continuity magnitudes are rcl-owned (§19); spg carries only the verdict + booleans.

    Args:
        direction: The change direction (must be ``RESTRICTIVE``).
        inputs: The injected preservation flags.

    Returns:
        ``True`` iff a proven restrictive change preserves all protected state.
    """
    if direction is not ChangeDirection.RESTRICTIVE:
        return False
    return (
        inputs.no_auto_revert is True
        and inputs.capacity_preserved is True
        and inputs.orders_preserved is True
        and inputs.exposure_preserved is True
        and inputs.unknown_preserved is True
        and inputs.protective_preserved is True
    )


# ===========================================================================
# §5.6 — expiry non-revival (SPG-EV-008 substrate)
# ===========================================================================


def expiry_suspends_new_risk(
    not_expired: bool | None,
    time_verifiable: bool | None,
) -> bool:
    """Whether expiry / unverifiable time suspends new risk (ADR §18; SPG-INV-011; §5.6).

    ``True`` (new risk suspended) unless **both** ``not_expired is True`` and
    ``time_verifiable is True``: an expired configuration, or one whose time cannot be
    verified (``None`` / ``False`` on either), suspends future new-risk authority (§18 line
    470). Time validity is an **injected** flag — spg performs no time arithmetic (design #12
    §3.5); a ``None`` fails closed (suspends).

    Args:
        not_expired: Whether the configuration has not expired (``None`` / ``False`` => suspend).
        time_verifiable: Whether time is verifiable (``None`` / ``False`` => suspend).

    Returns:
        ``True`` iff new risk must be suspended.
    """
    return not (not_expired is True and time_verifiable is True)


def expiry_revives_nothing() -> bool:
    """Whether expiry revives anything — unconditionally ``False`` for every effect (§18; SPG-INV-013).

    §18 line 472-482: expiry / invalidation does **not** cancel orders, release capacity,
    expire an economic effect, resolve UNKNOWN, restore a predecessor profile, auto-widen a
    grace period, or re-arm on time recovery. The model has **no** expiry -> restoration
    mapping operation (a structural absence, design #12 §4.5), so this predicate is
    **unconditionally ``True``**: "expiry revives nothing" (the liveauth
    ``authorization_revived_by_nothing`` / rcl ``recovery_generation_revives_nothing``
    isomorph). It takes no revival lever because none exists.

    Returns:
        Always ``True`` — expiry creates no revival of any authority / capacity / order.
    """
    return True


# ===========================================================================
# §6.1 — rollback = new proposal, non-revival (SPG-EV-007 substrate, predicate-only)
# ===========================================================================


def rollback_requires_new_generation(inputs: RollbackInputs) -> bool:
    """Whether a rollback is a lawful new proposal (ADR §17 line 452-458; SPG-EV-007; §6.1).

    §17 line 452 verbatim: "Rollback is a new proposal, never a state reversal." ``True``
    **only** when **all** hold: a new generation is issued, schema/software/broker/time
    validation is current, approval is current, break-before-make holds, and a fresh re-arm
    is performed (§17 line 452-458). Reusing an old broader profile as-is (without a new
    generation + current validation + approval + re-arm) fails closed. The restore-generation
    fence is rcl-owned (``restore_generation``); +Security historical-signature replay is
    not-Phase-1 (design #12 §1).

    Args:
        inputs: The injected rollback preconditions.

    Returns:
        ``True`` iff the rollback is a lawful new proposal.
    """
    return (
        inputs.new_generation_issued is True
        and inputs.current_schema_valid is True
        and inputs.current_approval is True
        and inputs.break_before_make is True
        and inputs.fresh_rearm is True
    )


def rollback_revives_nothing() -> bool:
    """Whether a rollback revives an old generation / approval — unconditionally ``False`` (§17; §6.1).

    A rollback never revives an old generation or approval (§17 line 452 "never a state
    reversal"; the :func:`expiry_revives_nothing` isomorph). Unconditionally ``True``: the
    model has no old-generation revival lever.

    Returns:
        Always ``True`` — rollback revives no old generation or approval.
    """
    return True


# ===========================================================================
# §6.2 — break-glass directional confinement (SPG-EV-009 substrate, predicate-only)
# ===========================================================================


def break_glass_confined(action: BreakGlassAction | None) -> bool:
    """Whether a break-glass action is directionally confined (ADR §8 line 251; SPG-EV-009; §6.2).

    §8 line 251 verbatim: break-glass authority may **only** HALT or apply a proven
    Restrictive Override. ``True`` **only** when ``action`` is in
    :data:`~tos.spg.vocabulary.BREAK_GLASS_ALLOWED_ACTIONS` (``HALT`` /
    ``RESTRICTIVE_OVERRIDE``). Every other action — expand envelope, expand profile, waive
    validation, activate a generation, re-arm — and a ``None`` action fail closed. The
    effective-principal independence enforcement ("Splitting labels across roles while one
    principal controls all underlying credentials does not establish separation", §8 line
    249) is ADR-002-015 HAG-EV +Security — not-Phase-1 (design #12 §1).

    Args:
        action: The break-glass action (``None`` => ``False``).

    Returns:
        ``True`` iff the action is HALT or a restrictive override.
    """
    if action is None:
        return False
    return action in BREAK_GLASS_ALLOWED_ACTIONS


# ===========================================================================
# §6.3 — consumer compatibility manifest match (SPG-EV-010 substrate, predicate-only)
# ===========================================================================


def compatibility_manifest_matches(
    manifest: ConsumerCompatibilityManifest | None,
    query: CompatibilityQuery | None,
) -> bool:
    """Whether a consumer manifest covers the bundle requirements (ADR §16; SPG-EV-010; §6.3).

    ``True`` **only** when the consumer declares a concrete identity, declares a non-empty
    schema / field surface (an **empty** manifest is a vacuous non-match — the ∅-seal, §6.3;
    §16 line 442 "inability to establish currentness is denial"), and each required set is a
    subset of the corresponding declared set (schemas / fields / units / calculations /
    constraints / failure-semantics; §16 line 434-436). Any missing / floating declaration
    fails closed. Software drift is ADR-002-029, broker drift is brokercap #10, final-egress
    binding is ADR-002-013 — all not-Phase-1 injected / runtime (design #12 §1).

    Args:
        manifest: The consumer compatibility manifest (``None`` / empty => ``False``).
        query: The bundle's compatibility requirements (``None`` => ``False``).

    Returns:
        ``True`` iff the manifest covers every requirement.
    """
    if manifest is None or query is None:
        return False
    if manifest.consumer_identity is None:
        return False
    # ∅-seal: an empty manifest declares nothing => cannot establish currentness => deny.
    if not manifest.declared_schemas and not manifest.declared_fields:
        return False
    return (
        set(query.required_schemas) <= set(manifest.declared_schemas)
        and set(query.required_fields) <= set(manifest.declared_fields)
        and set(query.required_units) <= set(manifest.declared_units)
        and set(query.required_calculations) <= set(manifest.declared_calculations)
        and set(query.required_constraints) <= set(manifest.declared_constraints)
        and set(query.required_failure_semantics)
        <= set(manifest.declared_failure_semantics)
    )


# ===========================================================================
# §6.4 — missing / contradictory configuration containment (SPG-EV-011 substrate)
# ===========================================================================


def bundle_complete(
    bundle: SafetyConfigurationBundle | None,
    required_members: frozenset[BundleMemberKind] = frozenset(),
) -> bool:
    """Whether a bundle is complete + closed (ADR §20; SPG-INV-002 line 157; §6.4).

    SPG-INV-002 line 157 verbatim: "No new-risk authority is created from a partial,
    unresolved, mutable, or open-ended Safety Configuration Bundle." ``True`` **only** when
    the bundle is present and, for **every** required member kind, a member ref is present,
    ``resolved is True``, ``immutable is True``, and its ``member_id`` is concrete (design
    #12 §6.4). An **empty** ``required_members`` is treated as **all 29 modeled members**
    (∅ = all-needed, most-restrictive — a zero-iteration loop must never vacuously pass;
    design #12 §4.1 / §5.3). Any missing / unresolved / mutable / floating member fails
    closed. The 7 deferred sub-generation refs ride as Phase-0-injected members in the same
    tuple and are checked identically.

    Args:
        bundle: The Safety Configuration Bundle (``None`` => ``False``).
        required_members: The required member kinds (**empty** => all 29 modeled).

    Returns:
        ``True`` iff every required member is present, resolved, immutable, and identified.
    """
    if bundle is None:
        return False
    required = required_members if required_members else MODELED_BUNDLE_MEMBERS
    for kind in required:
        ref = bundle.member_for(kind)
        if ref is None:
            return False
        if (
            ref.member_id is None
            or ref.resolved is not True
            or ref.immutable is not True
        ):
            return False
    return True


def missing_config_denies(
    bundle: SafetyConfigurationBundle | None,
    required_members: frozenset[BundleMemberKind] = frozenset(),
) -> bool:
    """Whether a missing / incomplete bundle denies new risk (ADR §20; SPG-EV-011; §6.4).

    ``True`` (new risk denied) whenever the bundle is **not** :func:`bundle_complete` — a
    partial / unresolved / mutable / open-ended bundle blocks new risk (§20 line 500-517;
    §24 SPG-AC-011). The "unresolved economic state remains conservatively capacity-covered"
    part is rcl-owned runtime (design #12 §1); spg produces only the new-risk-block bool.

    Args:
        bundle: The Safety Configuration Bundle (``None`` => denies).
        required_members: The required member kinds (**empty** => all 29 modeled).

    Returns:
        ``True`` iff new risk must be denied.
    """
    return not bundle_complete(bundle, required_members)


# ===========================================================================
# §3.4 — additional produced seam bools / scalars
# ===========================================================================


def hard_and_runtime_versions_match(
    envelope: HardSafetyEnvelope | None,
    profile: RuntimeSafetyProfile | None,
    activation: ActivationRecord | None,
    *,
    mixed_versions_present: bool | None,
) -> bool:
    """Whether the envelope / profile / activation generations agree (design #12 §3.4).

    ``True`` **only** when: the profile pins **this** envelope generation
    (``profile.target_envelope_generation == envelope.envelope_generation``), the activation
    record matches the profile generation (``activation.profile_generation ==
    profile.profile_generation``), and no mixed versions are present
    (``mixed_versions_present is False``). Fills liveauth's injected
    ``hard_and_runtime_versions_match`` continuous-validity condition (``state.py:135``);
    ``None`` / ``False`` fails it closed. Any ``None`` artifact / generation, or a
    ``True`` / ``None`` mixed flag, fails closed.

    Args:
        envelope: The active Hard Safety Envelope (``None`` => ``False``).
        profile: The active Runtime Safety Profile (``None`` => ``False``).
        activation: The activation record binding the generation (``None`` => ``False``).
        mixed_versions_present: Whether mixed versions are present (``True`` / ``None`` => ``False``).

    Returns:
        ``True`` iff the generations agree and no mixed versions are present.
    """
    if envelope is None or profile is None or activation is None:
        return False
    if mixed_versions_present is not False:
        return False
    if (
        envelope.envelope_generation is None
        or profile.target_envelope_generation is None
        or profile.target_envelope_generation != envelope.envelope_generation
    ):
        return False
    return (
        profile.profile_generation is not None
        and activation.profile_generation is not None
        and activation.profile_generation == profile.profile_generation
    )


def envelope_profile_covers_enlarged(
    envelope: HardSafetyEnvelope | None,
    profile: RuntimeSafetyProfile | None,
    delta_scope: tuple[str, ...],
    *,
    not_expanded: bool | None,
) -> bool:
    """Whether a delta scope is covered without enlarging the envelope (ADR §14.1; design #12 §3.4).

    ``True`` **only** when the envelope is not expanded (``not_expanded is True``) and the
    ``delta_scope`` is a subset of **both** the profile scope and the envelope permitted
    scope (the enlarged scope is already covered). Fills liveauth
    ``InPlaceExpansionInputs.envelope_profile_covers_enlarged`` (``state.py:205``).
    Fail-closed: a ``None`` envelope / profile, an unproven ``not_expanded``, or a delta
    reaching outside the current scope => ``False``.

    Args:
        envelope: The active Hard Safety Envelope (``None`` => ``False``).
        profile: The active Runtime Safety Profile (``None`` => ``False``).
        delta_scope: The enlarged scope coordinates that must already be covered.
        not_expanded: Whether the envelope stays un-expanded (``None`` / ``False`` => ``False``).

    Returns:
        ``True`` iff the delta scope is covered and the envelope is not expanded.
    """
    if envelope is None or profile is None:
        return False
    if not_expanded is not True:
        return False
    delta = set(delta_scope)
    return delta <= set(profile.scope) and delta <= set(envelope.permitted_scope)


def active_envelope_version(envelope: HardSafetyEnvelope | None) -> str | None:
    """The active envelope version string, or ``None`` (design #12 §3.4 — scalar producer).

    Fills the covered ``hard_safety_envelope_version`` scalar on liveauth / authority / rcl
    records. ``None`` when the envelope or its version block is absent (fail-closed downstream).
    """
    if envelope is None or envelope.envelope_version is None:
        return None
    return envelope.envelope_version.version


def active_profile_version(profile: RuntimeSafetyProfile | None) -> str | None:
    """The active profile version string, or ``None`` (design #12 §3.4 — scalar producer).

    Fills the covered ``runtime_safety_profile_version`` scalar on liveauth / authority / rcl
    / time records. ``None`` when the profile or its version block is absent.
    """
    if profile is None or profile.profile_version is None:
        return None
    return profile.profile_version.version


def active_envelope_generation(envelope: HardSafetyEnvelope | None) -> int | None:
    """The active envelope generation, or ``None`` (design #12 §3.4 — scalar producer).

    Fills the covered ``hard_safety_envelope_generation`` scalar on authority records.
    """
    return None if envelope is None else envelope.envelope_generation


def active_profile_generation(profile: RuntimeSafetyProfile | None) -> int | None:
    """The active profile generation, or ``None`` (design #12 §3.4 — scalar producer).

    Fills the covered ``profile_generation`` / ``runtime_safety_profile_generation`` scalar
    on authority / rcl / capsule records.
    """
    return None if profile is None else profile.profile_generation


def activation_digest(activation: ActivationRecord | None) -> str | None:
    """The activation record digest, or ``None`` (design #12 §3.4 — scalar producer).

    Fills the evidence ``safety_configuration_activation_record_digest`` scalar
    (``evidence/replay.py:113``). ``None`` when the record is absent / pre-issuance.
    """
    return None if activation is None else activation.canonical_digest


def envelope_limit_operand(
    envelope: HardSafetyEnvelope | None,
    dimension: str,
) -> CanonicalDecimal | None:
    """The **envelope** operand for a dimension's effective limit (design #12 §3.4 / §3.5).

    Produces the Hard-Safety-Envelope maximum for ``dimension`` as one **operand** scalar
    (a :data:`~tos.canonical.CanonicalDecimal`). spg performs **no** min — the authoritative
    ``EffectiveLimit[c] = min(Hard[c], Runtime[c])`` is rcl ``effective_limit``
    (``vector.py:139``, MAJOR-1). ``None`` when undeclared (fail-closed downstream).
    """
    return None if envelope is None else envelope.max_for(dimension)


def profile_limit_operand(
    profile: RuntimeSafetyProfile | None,
    dimension: str,
) -> CanonicalDecimal | None:
    """The **profile** operand for a dimension's effective limit (design #12 §3.4 / §3.5).

    Produces the Runtime-Safety-Profile operating value for ``dimension`` as the second
    **operand** scalar. spg performs **no** min — the authoritative min is rcl
    ``effective_limit`` (``vector.py:139``). ``None`` when absent (fail-closed downstream).
    """
    return None if profile is None else profile.value_for(dimension)
