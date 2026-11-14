"""ioc conformance / determinism / economic-fencing predicates + the deterministic compiler."""

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
    "command_conforms",
    "compile_command",
    "compiler_deterministic",
    "numerical_safety",
    "economic_effect_dominated",
    "no_silent_widening",
    "canonicalization_deterministic",
    "mutation_fence_holds",
    "derived_command_conformance",
    "protective_creates_nothing",
    "construction_grants_no_authority",
]


def _has_duplicate_axis(bindings: tuple[AxisBinding, ...]) -> bool:
    """Whether any conformance axis appears more than once in ``bindings`` (§14 line 406)."""
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


def command_conforms(
    intent: ApprovedIntentContract | None,
    command: CanonicalBrokerCommand | None,
    policy: OrderConstructionPolicy | None,
    envelope: AuthorizedConstructionEnvelope | None,
) -> ConformanceResult:
    """Whether the command conforms to the approved intent inside the envelope (§5.1 / §10-§12)."""
    if envelope is None:
        return ConformanceResult.NON_CONFORMANT
    if _has_duplicate_axis(envelope.authorized_axis_bindings):
        return ConformanceResult.NON_CONFORMANT
    authorized = envelope.authorized_axes()
    if not authorized:
        return ConformanceResult.NON_CONFORMANT
    if intent is None or command is None or policy is None:
        return ConformanceResult.UNKNOWN
    if _has_duplicate_axis(command.axis_bindings) or _has_duplicate_axis(
        intent.authorized_axis_bindings
    ):
        return ConformanceResult.NON_CONFORMANT
    if not _declared_axes(command.axis_bindings) <= set(authorized):
        return ConformanceResult.NON_CONFORMANT

    saw_unknown = False
    for axis, authorized_value in authorized.items():
        intent_value = intent.axis_value(axis)
        command_value = command.axis_value(axis)
        if authorized_value is None or intent_value is None or command_value is None:
            saw_unknown = True
            continue
        if command_value != authorized_value or command_value != intent_value:
            return ConformanceResult.NON_CONFORMANT
    if saw_unknown:
        return ConformanceResult.UNKNOWN
    return ConformanceResult.CONFORMANT


def compile_command(
    *,
    intent: ApprovedIntentContract | None,
    policy: OrderConstructionPolicy | None,
    envelope: AuthorizedConstructionEnvelope | None,
    generation: int,
    scheme: CanonicalizationScheme,
    command_id: str,
) -> CanonicalBrokerCommand:
    """Compile the canonical broker command from complete approved inputs (§5.2 / §9)."""
    if intent is None or policy is None or envelope is None:
        raise ArtifactIntegrityError(
            "construction requires complete approved inputs — denial, no fallback (§9 line 270)"
        )
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
    """Whether compiling the same inputs twice yields the same canonical digest (§4.2 / §5.2)."""
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
    """Whether the magnitudes are numerically safe (§5.2 / §11 line 301 / §14 line 423)."""
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


def economic_effect_dominated(
    envelope: CapacityVector,
    committed: CapacityVector,
) -> bool:
    """Whether committed capacity dominates every governed dimension of the envelope (§5.5 / §13)."""
    governed = envelope.dimension_ids()
    if not governed:
        return False
    for dimension in governed:
        envelope_magnitude = envelope.magnitude(dimension)
        committed_magnitude = committed.magnitude(dimension)
        if envelope_magnitude is None or committed_magnitude is None:
            return False
        if committed_magnitude < envelope_magnitude:
            return False
    return True


def no_silent_widening(
    *,
    exact_bounded_within_envelope: bool | None,
    every_dependent_gate_evaluated: bool | None,
) -> bool:
    """Whether a transformation changes no authorized meaning silently (§5.3 / §11 / IOC-INV-006)."""
    return (
        exact_bounded_within_envelope is True and every_dependent_gate_evaluated is True
    )


def canonicalization_deterministic(command: CanonicalBrokerCommand | None) -> bool:
    """Whether the command's canonical digest matches a recanonicalization (§6.1 / §14 line 406)."""
    if command is None or command.canonical_digest is None:
        return False
    scheme = get_scheme(command.canonicalization_version)
    return scheme.compute_digest(command.covered_content()) == command.canonical_digest


def mutation_fence_holds(
    command: CanonicalBrokerCommand | None,
    proof: OrderConformanceProof | None,
) -> bool:
    """Whether the post-proof economic / security fields are structurally frozen (§6.2 / §15)."""
    if command is None or proof is None:
        return False
    if command.canonical_digest is None or proof.command_digest is None:
        return False
    return proof.command_digest == command.canonical_digest


def derived_command_conformance(
    parent: CanonicalBrokerCommand | None,
    derived: CanonicalBrokerCommand | None,
    mutation_class: MutationClass | None,
    *,
    idempotency_capability_proven: bool | None = None,
    original_attempt_permits_retry: bool | None = None,
) -> ConformanceResult:
    """Whether a derived (retry / cancel / amend / replace / split / aggregate) command conforms (§6.3 / §16)."""
    if parent is None or derived is None or mutation_class is None:
        return ConformanceResult.UNKNOWN
    if derived.command_id is None or derived.canonical_digest is None:
        return ConformanceResult.UNKNOWN
    if _has_duplicate_axis(derived.axis_bindings) or _has_duplicate_axis(
        parent.axis_bindings
    ):
        return ConformanceResult.NON_CONFORMANT
    if mutation_class is MutationClass.AGGREGATE:
        return ConformanceResult.NON_CONFORMANT
    if mutation_class is MutationClass.RETRY:
        if (
            idempotency_capability_proven is None
            or original_attempt_permits_retry is None
        ):
            return ConformanceResult.UNKNOWN
        if (
            idempotency_capability_proven is True
            and original_attempt_permits_retry is True
        ):
            return ConformanceResult.CONFORMANT
        return ConformanceResult.NON_CONFORMANT
    if derived.command_id == parent.command_id:
        return ConformanceResult.NON_CONFORMANT
    return ConformanceResult.CONFORMANT


def protective_creates_nothing(
    *,
    label_bypasses_envelope: bool | None,
    label_bypasses_admissibility: bool | None,
    label_bypasses_capacity: bool | None,
    label_bypasses_egress: bool | None,
) -> bool:
    """Whether a protective / exit label bypasses nothing (§6.4 / §19 line 481-483)."""
    return (
        label_bypasses_envelope is False
        and label_bypasses_admissibility is False
        and label_bypasses_capacity is False
        and label_bypasses_egress is False
    )


def construction_grants_no_authority(
    effect: OrderConstructionAuthorityEffect,
) -> bool:
    """Whether the construction authority effect grants nothing (§6.5 / IOC-INV-011 / §7 line 219)."""
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
