"""ioc conformance / determinism / economic-fencing predicates + the deterministic compiler.

Pure, fail-closed decision rules over injected frozen models (design #14 §0.2/§4.6): ioc is a
**conformance-decision kernel, not a serializer / signer / egress engine** — it authors the
intent-to-order conformance rules, the deterministic-compiler property, and the economic-effect
dominance / no-silent-widening rules over injected registry values, ``CanonicalDecimal``
magnitudes, and the rcl ``CapacityVector``. There is **no** "assume-match" / "assume-within" /
"default / alias / substitute / coerce" path anywhere: a ``CONFORMANT`` / ``True`` comes only
from positive exact-match proof, everything else is ``NON_CONFORMANT`` / ``UNKNOWN`` / ``False``
(design #14 §4.1 — the structural seal against the #6 fail-open REJECT lesson).

**Truthy-sentinel consume contract (design #14 §4.7, MANDATED):** the ``ConformanceResult``
returned by :func:`command_conforms` / :func:`numerical_safety` / :func:`derived_command_conformance`
is **not** truthy-testable (``ConformanceResult.__bool__`` raises), so a consumer MUST gate on
``result is ConformanceResult.CONFORMANT``. The ``bool | None`` predicates
(:func:`economic_effect_dominated` / :func:`no_silent_widening` / ...) MUST be gated ``is True``.

The module authors L1-decidable substrate for IOC-EV-001..006 (core) and IOC-EV-007/009/010/011
(predicate-only) but closes **no** IOC-EV item (authoring is not evidence, VER-002-001 §5;
design #14 §1) — the ``/3`` / ``+Security`` / ``+Broker`` residue remains.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` + the rcl ``CapacityVector`` type only;
no ``shared.*``, no other sibling ``tos.*`` (design #14 §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.canonical import ArtifactIntegrityError, CanonicalizationScheme, get_scheme
from tos.ioc.records import (
    ApprovedIntentContract,
    AuthorizedConstructionEnvelope,
    AxisBinding,
    CanonicalBrokerCommand,
    OrderConformanceProof,
    OrderConstructionAuthorityEffect,
    OrderConstructionPolicy,
)
from tos.ioc.vocabulary import ConformanceAxis, ConformanceResult, MutationClass
from tos.rcl import CapacityVector

__all__ = [
    # core §5
    "command_conforms",
    "compile_command",
    "compiler_deterministic",
    "numerical_safety",
    "economic_effect_dominated",
    "no_silent_widening",
    # predicate-only §6
    "canonicalization_deterministic",
    "mutation_fence_holds",
    "derived_command_conformance",
    "protective_creates_nothing",
    "construction_grants_no_authority",
]


# ===========================================================================
# internal structural guards over the axis_bindings tuple (§5.1 / §14 line 406)
# ===========================================================================


def _has_duplicate_axis(bindings: tuple[AxisBinding, ...]) -> bool:
    """Whether any conformance axis appears more than once in ``bindings`` (§14 line 406).

    A repeated semantic axis inside the ``axis_bindings`` tuple is a duplicate semantic field —
    §14 line 406 verbatim "duplicate semantic fields ... are rejection". A first-match
    :meth:`~tos.ioc.records.CanonicalBrokerCommand.axis_value` read would silently pick one value
    and pass, so this guard makes the duplicate a structural denial. ``None``-axis bindings are
    ignored (an absent axis is not a semantic field). ``extra="forbid"`` on the model covers only
    unknown *top-level* fields, never a repeated axis inside the tuple — hence this guard.
    """
    seen: set[ConformanceAxis] = set()
    for binding in bindings:
        if binding.axis is None:
            continue
        if binding.axis in seen:
            return True
        seen.add(binding.axis)
    return False


def _declared_axes(bindings: tuple[AxisBinding, ...]) -> set[ConformanceAxis]:
    """The set of (non-``None``) conformance axes declared by ``bindings`` (§5.3 subset check)."""
    return {binding.axis for binding in bindings if binding.axis is not None}


# ===========================================================================
# core §5.1 — intent-to-command conformance (IOC-EV-001/002 substrate)
# ===========================================================================


def command_conforms(
    intent: ApprovedIntentContract | None,
    command: CanonicalBrokerCommand | None,
    policy: OrderConstructionPolicy | None,
    envelope: AuthorizedConstructionEnvelope | None,
) -> ConformanceResult:
    """Whether the command conforms to the approved intent inside the envelope (§5.1 / §10-§12).

    IOC-INV-003 line 165 / IOC-INV-004 line 169: every §10-§12 axis MUST be present, an
    envelope member, and **exactly equal** to the intent's authorized value — it "cannot be
    defaulted, aliased, or substituted outside the authorized envelope" and must be "explicit
    and proven without lossy or ambiguous coercion". Returns:

    * ``CONFORMANT`` **only** when every authorized axis (the envelope's closed set) is present
      on both intent and command, all three values are exactly equal, the command declares no
      axis outside the authorized set, and neither the command nor the intent nor the envelope
      repeats an axis;
    * ``NON_CONFORMANT`` when any axis is a definite mismatch (an alias / default / substitute /
      flipped side — direction / side / position-effect are independent axes, so a signed
      quantity cannot silently flip a side, §11 line 301), when the command declares a **surplus
      axis** outside the authorized closed set (a silent widening — §5.3 "must fall inside",
      §12 line 321 widening is material), when the command / intent / envelope carries a
      **duplicate semantic axis** (§14 line 406 "duplicate semantic fields ... are rejection";
      §10 line 284 ambiguity is denial), or when the envelope is absent / open-ended (``permits
      no construction``, §5.3 line 125 — the ∅ denial, §4.7);
    * ``UNKNOWN`` when a determination input is missing (a ``None`` policy / intent / command, or
      an axis whose authorized / intent / command value is absent) — never a permissive default.

    Structural rejects (surplus / duplicate axis) and a definite mismatch dominate a missing axis
    (a hard reject over an undecidable one); all are denial (the consume gate is ``result is
    ConformanceResult.CONFORMANT``, §4.7).

    Args:
        intent: The approved intent contract (``None`` => UNKNOWN).
        command: The canonical broker command (``None`` => UNKNOWN).
        policy: The governing construction policy (``None`` => UNKNOWN).
        envelope: The authorized construction envelope (absent / empty => NON_CONFORMANT).

    Returns:
        The :class:`~tos.ioc.vocabulary.ConformanceResult`.
    """
    if envelope is None:
        return ConformanceResult.NON_CONFORMANT
    # An ambiguous authorization — the same axis declared twice on the envelope — is denial
    # (§10 line 284 ambiguity is denial; §14 line 406 duplicate semantic field is rejection).
    if _has_duplicate_axis(envelope.authorized_axis_bindings):
        return ConformanceResult.NON_CONFORMANT
    authorized = envelope.authorized_axes()
    if (
        not authorized
    ):  # absent / open-ended envelope permits no construction (§5.3 line 125)
        return ConformanceResult.NON_CONFORMANT
    if intent is None or command is None or policy is None:
        return ConformanceResult.UNKNOWN
    # A duplicate semantic axis on the command OR the intent is a structural rejection: a
    # first-match ``axis_value`` read would silently pick one value and pass (§14 line 406
    # "duplicate semantic fields ... are rejection"). extra="forbid" covers only unknown
    # top-level model fields, never a repeated axis inside the axis_bindings tuple.
    if _has_duplicate_axis(command.axis_bindings) or _has_duplicate_axis(
        intent.authorized_axis_bindings
    ):
        return ConformanceResult.NON_CONFORMANT
    # A surplus axis — declared by the command but not authorized by the closed envelope — is a
    # silent widening the envelope-only iteration would never inspect (§5.3 "must fall inside";
    # §12 line 321 widening is material), so it is denial, never checked-and-passed.
    if not _declared_axes(command.axis_bindings) <= set(authorized):
        return ConformanceResult.NON_CONFORMANT

    saw_unknown = False
    for axis, authorized_value in authorized.items():
        intent_value = intent.axis_value(axis)
        command_value = command.axis_value(axis)
        if authorized_value is None or intent_value is None or command_value is None:
            saw_unknown = True  # undecidable axis — missing determination input
            continue
        if command_value != authorized_value or command_value != intent_value:
            return (
                ConformanceResult.NON_CONFORMANT
            )  # alias / default / substitute / flip
    if saw_unknown:
        return ConformanceResult.UNKNOWN
    return ConformanceResult.CONFORMANT


# ===========================================================================
# core §5.2 — deterministic compiler + numerical safety (IOC-EV-003 substrate)
# ===========================================================================


def compile_command(
    *,
    intent: ApprovedIntentContract | None,
    policy: OrderConstructionPolicy | None,
    envelope: AuthorizedConstructionEnvelope | None,
    generation: int,
    scheme: CanonicalizationScheme,
    command_id: str,
) -> CanonicalBrokerCommand:
    """Compile the canonical broker command from complete approved inputs (§5.2 / §9).

    IOC-INV-002 line 161 verbatim: "The same complete approved inputs and Construction
    Generation produce the same canonical semantic command and digest, or construction fails."
    A pure function: it declares, for each envelope-authorized axis, the **exact** intent value
    (no default / alias / substitute), and issues a :class:`~tos.ioc.records.CanonicalBrokerCommand`
    over the injected ``scheme`` (``EVL1ProvisionalCanonicalizer`` REUSE; the production canonical
    form is Phase-0). Because the command id is excluded from the digest preimage, the digest is a
    pure function of the covered content — recompiling identical inputs yields an identical digest.

    **Denial is total (§9 line 270):** an absent / open-ended envelope, a missing input, or an
    axis whose authorized / intent value is absent or disagrees raises
    :class:`~tos.canonical.ArtifactIntegrityError` — the compiler "must not 'best effort' an
    unsupported field or fall back to a prior mapping".

    Args:
        intent: The approved intent contract.
        policy: The governing construction policy.
        envelope: The authorized construction envelope.
        generation: The Construction Generation (monotonic; §5.7).
        scheme: The injected canonicalization scheme.
        command_id: The independent command identity to assign.

    Returns:
        The issued canonical broker command.

    Raises:
        ArtifactIntegrityError: On any incomplete / non-conforming input (denial, no fallback).
    """
    if intent is None or policy is None or envelope is None:
        raise ArtifactIntegrityError(
            "construction requires complete approved inputs — denial, no fallback (§9 line 270)"
        )
    # An ambiguous (duplicate-axis) envelope or intent is denial, not a last-wins collapse: the
    # ``authorized_axes`` dict silently last-wins a repeat, so guard the raw tuples first
    # (§10 line 284 ambiguity is denial; §14 line 406 duplicate semantic field; denial-is-total).
    if _has_duplicate_axis(envelope.authorized_axis_bindings):
        raise ArtifactIntegrityError(
            "ambiguous envelope: a duplicate authorized axis — denial (§10 line 284 / §14 line 406)"
        )
    if _has_duplicate_axis(intent.authorized_axis_bindings):
        raise ArtifactIntegrityError(
            "ambiguous intent: a duplicate authorized axis — denial (§14 line 406)"
        )
    authorized = envelope.authorized_axes()
    if not authorized:
        raise ArtifactIntegrityError(
            "absent / open-ended envelope permits no construction (§5.3 line 125)"
        )
    # Deterministic axis order: sort by the axis token (no unordered-map iteration, §9 line 268).
    bindings: list[AxisBinding] = []
    for axis in sorted(authorized, key=lambda a: a.value):
        authorized_value = authorized[axis]
        intent_value = intent.axis_value(axis)
        if authorized_value is None or intent_value is None:
            raise ArtifactIntegrityError(
                f"unsupported / undetermined axis {axis.value} — denial, no fallback (§9 line 270)"
            )
        if intent_value != authorized_value:
            raise ArtifactIntegrityError(
                f"axis {axis.value} outside the authorized envelope — denial (§9)"
            )
        bindings.append(AxisBinding(axis=axis, value=intent_value))
    command = CanonicalBrokerCommand.issue(
        scheme=scheme,
        command_id=command_id,
        command_generation=generation,
        proposal_id=intent.proposal_id,
        proposal_digest=intent.proposal_digest,
        axis_bindings=tuple(bindings),
    )
    assert isinstance(command, CanonicalBrokerCommand)
    return command


def compiler_deterministic(
    *,
    intent: ApprovedIntentContract | None,
    policy: OrderConstructionPolicy | None,
    envelope: AuthorizedConstructionEnvelope | None,
    generation: int,
    scheme: CanonicalizationScheme,
) -> bool:
    """Whether compiling the same inputs twice yields the same canonical digest (§4.2 / §5.2).

    IOC-INV-002 (§4.2): the load-bearing property is not the digest-equality (a near-tautology
    for a pure function of a deterministic canonicalizer) but **hermeticity** (no hidden clock /
    randomness / locale / env / mutable cache / unordered map / float variation / network /
    "latest"-registry / SDK default — §9 line 268, actively enforced by the §7.1 import-closure
    test) and **denial-is-total** (a construction failure recompiles to the *same* failure, never
    a fallback — §9 line 270). ``True`` **only** when two compilations agree: either both succeed
    with an identical canonical digest, or both deny — a first-denies / second-succeeds (or
    digest-drift) pair is non-deterministic and returns ``False``.

    Args:
        intent: The approved intent contract.
        policy: The governing construction policy.
        envelope: The authorized construction envelope.
        generation: The Construction Generation.
        scheme: The injected canonicalization scheme.

    Returns:
        ``True`` iff the compiler is deterministic on the inputs (equal digest or equal denial).
    """
    try:
        first = compile_command(
            intent=intent,
            policy=policy,
            envelope=envelope,
            generation=generation,
            scheme=scheme,
            command_id="ioc-cmp-a",
        )
    except ArtifactIntegrityError:
        # Deterministic denial: a recompile MUST also deny (never fall back to success).
        try:
            compile_command(
                intent=intent,
                policy=policy,
                envelope=envelope,
                generation=generation,
                scheme=scheme,
                command_id="ioc-cmp-b",
            )
        except ArtifactIntegrityError:
            return True
        return False
    second = compile_command(
        intent=intent,
        policy=policy,
        envelope=envelope,
        generation=generation,
        scheme=scheme,
        command_id="ioc-cmp-b",
    )
    return (
        first.canonical_digest is not None
        and first.canonical_digest == second.canonical_digest
    )


def numerical_safety(
    magnitudes: Sequence[Decimal | None],
    *,
    units_consistent: bool | None,
) -> ConformanceResult:
    """Whether the magnitudes are numerically safe (§5.2 / §11 line 301 / §14 line 423).

    §14 line 423: numeric exponent variants, NaN / infinity, negative zero, integer overflow,
    silent truncation SHALL fail closed; §11 line 301: an ``abs`` / clamp / cast / truncation /
    binary-float / unit mismatch is prohibited unless policy-approved. Returns:

    * ``NON_CONFORMANT`` when the units are positively **inconsistent** (a definite wrong-unit /
      multiplier / scale mismatch — a hard reject, never a smaller permissive value);
    * ``UNKNOWN`` when unit consistency is unknown (``None``), the magnitude sequence is **empty**
      (a vacuous "safe over nothing" is not safety, §4.7), or any magnitude is absent / non-finite
      (a non-finite ``CanonicalDecimal`` is already unconstructable, so this also covers raw
      injected magnitudes);
    * ``CONFORMANT`` otherwise.

    Args:
        magnitudes: The magnitudes to check (empty / ``None`` / non-finite => UNKNOWN).
        units_consistent: Whether the units are consistent (``False`` => NON_CONFORMANT;
            ``None`` => UNKNOWN).

    Returns:
        The :class:`~tos.ioc.vocabulary.ConformanceResult`.
    """
    if units_consistent is False:
        return ConformanceResult.NON_CONFORMANT
    if units_consistent is None:
        return ConformanceResult.UNKNOWN
    if not magnitudes:
        return ConformanceResult.UNKNOWN
    for magnitude in magnitudes:
        if magnitude is None or not magnitude.is_finite():
            return ConformanceResult.UNKNOWN
    return ConformanceResult.CONFORMANT


# ===========================================================================
# core §5.5 — economic-effect envelope dominance (IOC-EV-006 substrate)
# ===========================================================================


def economic_effect_dominated(
    envelope: CapacityVector,
    committed: CapacityVector,
) -> bool:
    """Whether committed capacity dominates every governed dimension of the envelope (§5.5 / §13).

    IOC-INV-005 line 173 verbatim: "The committed capacity dominates every credible effect in the
    command's Economic Effect Envelope." ``True`` **only** when, for every dimension the envelope
    governs, both magnitudes are present (finite) and ``committed >= envelope``. Fail-closed both
    ways (design #14 §4.3/§4.7):

    * a ``None`` / UNKNOWN magnitude on either side => not-dominated (never assume-zero);
    * an **empty envelope** governs no dimension, but a vacuous "dominates nothing" is not
      dominance proof — it returns ``False`` (∅ fail-closed);
    * an **empty committed** vector leaves every governed dimension ``None`` => not-dominated.

    Compiler confidence, expected broker rejection, a protective label, human approval, or
    historical behavior cannot shrink the envelope (§13 line 343) — none is an argument here, so
    none can. ioc decides dominance only; capacity commit / serialize stays rcl-owned (§13 line
    341; design #14 §3.5).

    Args:
        envelope: The economic-effect envelope (the rcl ``CapacityVector`` type).
        committed: The committed capacity vector (the rcl ``CapacityVector`` type).

    Returns:
        ``True`` iff committed capacity dominates every governed dimension.
    """
    governed = envelope.dimension_ids()
    if (
        not governed
    ):  # empty envelope => vacuous dominance is not dominance (∅ fail-closed)
        return False
    for dimension in governed:
        envelope_magnitude = envelope.magnitude(dimension)
        committed_magnitude = committed.magnitude(dimension)
        if envelope_magnitude is None or committed_magnitude is None:
            return False  # None / UNKNOWN => not-dominated
        if committed_magnitude < envelope_magnitude:
            return False  # committed must dominate (>=) every governed dimension
    return True


# ===========================================================================
# core §5.3 — no silent widening / narrowing (IOC-EV-004 substrate)
# ===========================================================================


def no_silent_widening(
    *,
    exact_bounded_within_envelope: bool | None,
    every_dependent_gate_evaluated: bool | None,
) -> bool:
    """Whether a transformation changes no authorized meaning silently (§5.3 / §11 / IOC-INV-006).

    IOC-INV-006 line 177 verbatim: "No mapping, rounding, split, aggregation, default, or
    normalization changes authorized meaning unless the exact bounded transformation is inside
    the envelope and every dependent gate evaluated it." ``True`` **only** when both injected
    witnesses are positively ``True`` — the transformation is an exact bounded result inside the
    envelope **and** every dependent gate evaluated that choice set. A ``None`` / ``False`` on
    either fails closed: even a risk-reducing rounding is rejected when it can leave protection
    insufficient, violate a min / lot constraint, change exposure direction, or alter approved
    economic effect (§11 line 303; §24.4).

    Args:
        exact_bounded_within_envelope: Whether the transformation is an exact bounded result
            inside the envelope (``None`` / ``False`` => fail-closed).
        every_dependent_gate_evaluated: Whether every dependent gate evaluated the choice set
            (``None`` / ``False`` => fail-closed).

    Returns:
        ``True`` iff no authorized meaning is silently widened / narrowed.
    """
    return (
        exact_bounded_within_envelope is True and every_dependent_gate_evaluated is True
    )


# ===========================================================================
# predicate-only §6.1 — canonicalization determinism (IOC-EV-007 substrate)
# ===========================================================================


def canonicalization_deterministic(command: CanonicalBrokerCommand | None) -> bool:
    """Whether the command's canonical digest matches a recanonicalization (§6.1 / §14 line 406).

    §14 line 406: "Unknown fields, duplicate semantic fields, alternate encodings ... are
    rejection. A byte digest alone is insufficient if two byte sequences or parser behaviors can
    produce different broker meaning." The L1 substrate: the digest self-verifies by
    recomputing the canonical form over the covered content (unknown / duplicate fields are
    already structurally rejected by ``extra="forbid"``, so a deterministic recanonicalization
    is the L1-decidable slice). ``True`` **only** when the command is present, ISSUED (a concrete
    digest), and the recomputed digest matches. The parser-differential / byte-vs-semantic /
    malicious-encoding detection is EV-L2 component-fault / +Security (§23 line 555) — not closed
    here.

    Args:
        command: The canonical broker command (``None`` / DRAFT => ``False``).

    Returns:
        ``True`` iff the command canonicalizes deterministically to its bound digest.
    """
    if command is None or command.canonical_digest is None:
        return False
    scheme = get_scheme(command.canonicalization_version)
    return scheme.compute_digest(command.covered_content()) == command.canonical_digest


# ===========================================================================
# predicate-only §6.2 — post-proof mutation fence (IOC-EV-008 substrate)
# ===========================================================================


def mutation_fence_holds(
    command: CanonicalBrokerCommand | None,
    proof: OrderConformanceProof | None,
) -> bool:
    """Whether the post-proof economic / security fields are structurally frozen (§6.2 / §15).

    IOC-INV-007 line 181 / §15 line 414: "no economic- or security-relevant semantic field may
    change" after the proof is issued. The L1 structural realization: the command and proof are
    frozen (``extra="forbid"``), so a post-proof mutation is **construction-impossible** — a new
    mutation is a new command identity + a new proof (§16 line 429). ``True`` **only** when the
    proof binds the exact command's canonical digest (``proof.command_digest ==
    command.canonical_digest``), so the fenced pair is provably the same command the proof
    covered; a ``None`` command / proof / digest, or a mismatch, fails closed. The actual-outbound
    wire equivalence (§15 line 418 / §17 line 452) is +Security runtime (ADR-002-013 Egress
    Gateway) — not closed here.

    Args:
        command: The canonical broker command (``None`` / DRAFT => ``False``).
        proof: The order conformance proof (``None`` => ``False``).

    Returns:
        ``True`` iff the proof fences the exact command it covered.
    """
    if command is None or proof is None:
        return False
    if command.canonical_digest is None or proof.command_digest is None:
        return False
    return proof.command_digest == command.canonical_digest


# ===========================================================================
# predicate-only §6.3 — derived-command lineage / no blind retry (IOC-EV-009 substrate)
# ===========================================================================


def derived_command_conformance(
    parent: CanonicalBrokerCommand | None,
    derived: CanonicalBrokerCommand | None,
    mutation_class: MutationClass | None,
    *,
    idempotency_capability_proven: bool | None = None,
    original_attempt_permits_retry: bool | None = None,
) -> ConformanceResult:
    """Whether a derived (retry / cancel / amend / replace / split / aggregate) command conforms (§6.3 / §16).

    §16 line 429 verbatim: "Every broker mutation has its own command identity and proof." A
    derived command is conformant **only** when it carries its **own** identity + digest, distinct
    from the parent's. Returns:

    * ``UNKNOWN`` when a determination input is missing (``None`` parent / derived / class, or a
      derived command with no own identity / digest) — never a permissive default;
    * ``NON_CONFORMANT`` for an ``AGGREGATE`` (default-denied, §16 line 437), a ``RETRY`` without
      **positively proven** deterministic broker idempotency + an original attempt that permits
      retry (**no blind resubmission**, §16 line 431), or a non-retry mutation that reuses the
      parent's exact identity (not its own command identity);
    * ``CONFORMANT`` when a non-retry mutation carries its own distinct identity, or a retry has
      proven idempotency + a retry-permitting attempt.

    It inherits the :func:`command_conforms` **duplicate-axis** structural guard: a derived (or
    parent) command that repeats a semantic axis is ``NON_CONFORMANT`` (§14 line 406). The
    **surplus-axis-vs-envelope** check is :func:`command_conforms`'s domain — a derived command
    gets its own :func:`command_conforms` pass against its own envelope, which this lineage-only
    predicate does not carry.

    The broker deterministic-idempotency / replace semantics are **injected** capability results
    (brokercap ``ReplaceSemantics`` ``vocabulary.py:202``); the real broker integration is
    +Broker (ADR-002-004), not closed here.

    Args:
        parent: The parent command (``None`` => UNKNOWN).
        derived: The derived command (``None`` / no own identity => UNKNOWN).
        mutation_class: The mutation class (``None`` => UNKNOWN).
        idempotency_capability_proven: Injected proven-idempotency capability (retry only).
        original_attempt_permits_retry: Injected original-attempt-permits-retry state (retry only).

    Returns:
        The :class:`~tos.ioc.vocabulary.ConformanceResult`.
    """
    if parent is None or derived is None or mutation_class is None:
        return ConformanceResult.UNKNOWN
    if derived.command_id is None or derived.canonical_digest is None:
        return (
            ConformanceResult.UNKNOWN
        )  # a derived command with no own identity / proof
    if _has_duplicate_axis(derived.axis_bindings) or _has_duplicate_axis(
        parent.axis_bindings
    ):
        return (
            ConformanceResult.NON_CONFORMANT
        )  # duplicate semantic axis on derived / parent (§14 line 406)
    if mutation_class is MutationClass.AGGREGATE:
        return (
            ConformanceResult.NON_CONFORMANT
        )  # aggregation default-denied (§16 line 437)
    if mutation_class is MutationClass.RETRY:
        if (
            idempotency_capability_proven is None
            or original_attempt_permits_retry is None
        ):
            return (
                ConformanceResult.UNKNOWN
            )  # missing capability determination => no blind retry
        if (
            idempotency_capability_proven is True
            and original_attempt_permits_retry is True
        ):
            return ConformanceResult.CONFORMANT
        return (
            ConformanceResult.NON_CONFORMANT
        )  # blind resubmission denied (§16 line 431)
    # NEW / CANCEL / AMEND / REPLACE / SPLIT_CHILD / EXERCISE: needs its own distinct identity.
    if derived.command_id == parent.command_id:
        return (
            ConformanceResult.NON_CONFORMANT
        )  # not its own command identity (§16 line 429)
    return ConformanceResult.CONFORMANT


# ===========================================================================
# predicate-only §6.4 — protective construction creates nothing (IOC-EV-010 substrate)
# ===========================================================================


def protective_creates_nothing(
    *,
    label_bypasses_envelope: bool | None,
    label_bypasses_admissibility: bool | None,
    label_bypasses_capacity: bool | None,
    label_bypasses_egress: bool | None,
) -> bool:
    """Whether a protective / exit label bypasses nothing (§6.4 / §19 line 481-483).

    §19 line 481 verbatim: "Protective, reduction, cancel, or containment commands are not
    exempt." A label / urgency / priority cannot bypass the exact envelope, admissibility,
    capacity, or egress (§19 line 483). ``True`` **only** when every "bypasses X" claim is
    positively ``False`` (a ``True`` claim is inadmissible; a ``None`` is UNKNOWN and fails
    closed). The partition / broker-alive / pre-committed protective lease is runtime
    (ADR-002-001/002), not closed here.

    Args:
        label_bypasses_envelope: Whether the label bypasses the envelope (``True`` / ``None`` => False).
        label_bypasses_admissibility: Whether it bypasses admissibility (``True`` / ``None`` => False).
        label_bypasses_capacity: Whether it bypasses capacity (``True`` / ``None`` => False).
        label_bypasses_egress: Whether it bypasses egress (``True`` / ``None`` => False).

    Returns:
        ``True`` iff the protective label bypasses nothing.
    """
    return (
        label_bypasses_envelope is False
        and label_bypasses_admissibility is False
        and label_bypasses_capacity is False
        and label_bypasses_egress is False
    )


# ===========================================================================
# predicate-only §6.5 — authority separation / all-false (IOC-EV-011 substrate)
# ===========================================================================


def construction_grants_no_authority(
    effect: OrderConstructionAuthorityEffect,
) -> bool:
    """Whether the construction authority effect grants nothing (§6.5 / IOC-INV-011 / §7 line 219).

    ``True`` **only** when every authority flag is ``False``. Because
    :class:`~tos.ioc.records.OrderConstructionAuthorityEffect` is unconstructable with any
    ``True`` flag, a constructed effect always grants nothing — this is the defining predicate
    that states it (§7 line 228: the compiler and its policy / schema / mapping / test / evidence
    identities SHALL NOT hold a usable live broker credential or broker-order route; the
    +Security enforcement proof is IOC-EV-011).

    Args:
        effect: The order-construction authority effect.

    Returns:
        ``True`` iff the effect grants no authority.
    """
    return not (
        effect.approves
        or effect.mutates_capacity
        or effect.issues_authority
        or effect.classifies_protection
        or effect.chooses_admissibility
        or effect.transmits
        or effect.clears_halt
        or effect.rearms
    )
