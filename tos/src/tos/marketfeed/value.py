"""Value production + verification — the pure layer (design #32 §2/§3.2/§4/§5)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tos.capsule import (
    CriticalInputSnapshot,
    DecisionContextCapsule,
    FieldEvaluation,
    FieldState,
    Observation,
    TransformationLineage,
    worst,
)
from tos.capsule.predicates import admitted_field_state, derive_lineage_state
from tos.dsl import (
    VALUE_NAMESPACE,
    ContextValue,
    ContextValueView,
    ScalarValue,
    is_wildcard_field_key,
)
from tos.marketfeed._base import CanonicalizationScheme
from tos.marketfeed.records import (
    AdmittedValue,
    RejectedValue,
    ValueResolution,
)
from tos.marketfeed.vocabulary import ValueRejectionReason, ValueViewDisposition

__all__ = [
    "capsule_top_level_keys",
    "context_value_view_digest",
    "index_observations",
    "lineage_state_for_output",
    "project_scalar",
    "publish_context_value_view",
    "snapshot_binds_capsule_reference",
    "value_field_state",
    "value_namespace_is_disjoint",
    "view_digest_matches",
]


def capsule_top_level_keys(
    capsule: DecisionContextCapsule | None = None,
) -> frozenset[str]:
    """The Capsule's actual top-level key set (design #32 §3.2 (1))."""
    if capsule is not None:
        return frozenset(capsule.model_dump(mode="json"))
    return frozenset(DecisionContextCapsule.model_fields)


def value_namespace_is_disjoint(capsule: DecisionContextCapsule | None = None) -> bool:
    """Whether the reserved value namespace collides with no Capsule top-level key."""
    return VALUE_NAMESPACE not in capsule_top_level_keys(capsule)


def snapshot_binds_capsule_reference(
    capsule: DecisionContextCapsule, snapshot: CriticalInputSnapshot
) -> bool:
    """Whether a snapshot body is *the exact one* the Capsule references (design #32 §3.3)."""
    ref = capsule.critical_input_snapshot
    if ref.snapshot_id is None or ref.canonical_digest is None:
        return False
    if snapshot.snapshot_id is None or snapshot.canonical_digest is None:
        return False
    return (
        ref.snapshot_id == snapshot.snapshot_id
        and ref.canonical_digest == snapshot.canonical_digest
    )


def value_field_state(
    observation: Observation,
    field_key: str,
    field_evaluations: Sequence[FieldEvaluation],
) -> FieldState:
    """The single three-way VALID gate for one value (design #32 §2.2/§6)."""
    states: list[FieldState] = [
        admitted_field_state(observation.admission.result),
        observation.field_state,
    ]
    matching = [
        evaluation.state
        for evaluation in field_evaluations
        if evaluation.field_ref == field_key
    ]
    if not matching:
        states.append(FieldState.UNKNOWN)
    else:
        states.extend(matching)
    return worst(states)


def index_observations(
    snapshot: CriticalInputSnapshot,
) -> tuple[dict[str, Observation], frozenset[str]]:
    """Index a snapshot's observations by raw-event identity (design #32 §2.3)."""
    index: dict[str, Observation] = {}
    ambiguous: set[str] = set()
    for observation in snapshot.observations:
        raw_event_id = observation.raw.raw_event_id
        if raw_event_id is None:
            continue
        if raw_event_id in index:
            ambiguous.add(raw_event_id)
            continue
        index[raw_event_id] = observation
    for raw_event_id in ambiguous:
        index.pop(raw_event_id, None)
    return index, frozenset(ambiguous)


def lineage_state_for_output(
    output_id: str,
    output_as_of: int,
    lineage: Sequence[TransformationLineage],
    observations: Mapping[str, Observation],
) -> tuple[FieldState, ValueRejectionReason | None]:
    """The field state a value inherits from its transformation lineage (design #32 §5)."""
    nodes = [node for node in lineage if node.output_id == output_id]
    if not nodes:
        return FieldState.VALID, None
    states: list[FieldState] = []
    reason: ValueRejectionReason | None = None
    for node in nodes:
        derived = derive_lineage_state(node)
        if derived is not FieldState.VALID:
            states.append(derived)
            reason = reason or ValueRejectionReason.LINEAGE_NOT_REPRODUCIBLE
            continue
        for parent in node.parents:
            parent_id = parent.parent_id
            parent_observation = (
                None if parent_id is None else observations.get(parent_id)
            )
            if parent_observation is None:
                states.append(FieldState.UNKNOWN)
                reason = reason or ValueRejectionReason.LINEAGE_PARENT_UNRESOLVED
                continue
            parent_as_of = parent_observation.time.source_event_time
            if parent_as_of is None:
                states.append(FieldState.UNKNOWN)
                reason = reason or ValueRejectionReason.LINEAGE_PARENT_UNRESOLVED
                continue
            if parent_as_of > output_as_of:
                states.append(FieldState.INVALID)
                reason = reason or ValueRejectionReason.LINEAGE_LOOKAHEAD
        states.append(node.field_state)
    aggregate = worst(states)
    return aggregate, (None if aggregate is FieldState.VALID else reason)


def project_scalar(
    token: ScalarValue,
) -> tuple[ScalarValue | None, ValueRejectionReason | None]:
    """Project a preimage token onto a DSL-comparable scalar, or refuse it (design #32 §2.5)."""
    if isinstance(token, bool):
        return token, None
    if isinstance(token, int):
        return token, None
    if isinstance(token, str):
        return token, None
    return None, ValueRejectionReason.NON_DETERMINISTIC_NUMERIC


def _covered_view_content(
    *,
    snapshot_id: str,
    snapshot_canonical_digest: str,
    values: Sequence[ContextValue],
) -> dict[str, Any]:
    """The digest preimage of a value view — the binding plus the value set, key-sorted."""
    return {
        "snapshot_id": snapshot_id,
        "snapshot_canonical_digest": snapshot_canonical_digest,
        "values": [
            {
                "field_key": value.field_key,
                "value": value.value,
                "as_of": value.as_of,
                "payload_digest": value.payload_digest,
                "observation_ref": value.observation_ref,
            }
            for value in sorted(values, key=lambda item: item.field_key)
        ],
    }


def context_value_view_digest(
    *,
    snapshot_id: str,
    snapshot_canonical_digest: str,
    values: Sequence[ContextValue],
    scheme: CanonicalizationScheme,
) -> str:
    """The canonical digest of a value set (design #32 §2.2/§3.2 (3b))."""
    return scheme.compute_digest(
        _covered_view_content(
            snapshot_id=snapshot_id,
            snapshot_canonical_digest=snapshot_canonical_digest,
            values=values,
        )
    )


def view_digest_matches(view: ContextValueView, scheme: CanonicalizationScheme) -> bool:
    """Whether a view's recorded digest is the digest of its own content (design #32 §2.2)."""
    return view.canonical_digest == context_value_view_digest(
        snapshot_id=view.snapshot_id,
        snapshot_canonical_digest=view.snapshot_canonical_digest,
        values=view.values,
        scheme=scheme,
    )


def _reject(
    candidate: AdmittedValue, reason: ValueRejectionReason, detail: str | None = None
) -> RejectedValue:
    """Build one named rejection record."""
    return RejectedValue(
        field_key=candidate.field_key,
        observation_ref=candidate.observation_ref,
        reason=reason,
        detail=detail,
    )


def _admit_one(
    candidate: AdmittedValue,
    *,
    snapshot: CriticalInputSnapshot,
    observations: Mapping[str, Observation],
    ambiguous: frozenset[str],
    scheme: CanonicalizationScheme,
) -> tuple[ContextValue | None, RejectedValue | None]:
    """Run every per-value gate for one candidate (design #32 §2.2/§2.3/§4.2/§5)."""
    if is_wildcard_field_key(
        candidate.field_key
    ):  # pragma: no cover - blocked at construction
        return None, _reject(candidate, ValueRejectionReason.WILDCARD_FIELD_KEY)
    if candidate.observation_ref in ambiguous:
        return None, _reject(
            candidate,
            ValueRejectionReason.OBSERVATION_AMBIGUOUS,
            "more than one observation carries this raw-event identity",
        )
    observation = observations.get(candidate.observation_ref)
    if observation is None:
        return None, _reject(candidate, ValueRejectionReason.OBSERVATION_NOT_FOUND)

    payload_digest = observation.raw.payload_digest
    if payload_digest is None:
        return None, _reject(candidate, ValueRejectionReason.PAYLOAD_DIGEST_ABSENT)
    as_of = observation.time.source_event_time
    if as_of is None:
        return None, _reject(candidate, ValueRejectionReason.AS_OF_ABSENT)

    recomputed = scheme.compute_digest(candidate.preimage.as_mapping())
    if recomputed != payload_digest:
        return None, _reject(
            candidate,
            ValueRejectionReason.DIGEST_MISMATCH,
            f"preimage digests to {recomputed!r}, observation attests {payload_digest!r}",
        )

    token = candidate.preimage.lookup(candidate.field_key)
    if token is None:
        return None, _reject(candidate, ValueRejectionReason.VALUE_NOT_IN_PAYLOAD)
    value, projection_reason = project_scalar(token)
    if value is None or projection_reason is not None:
        return None, _reject(
            candidate,
            projection_reason or ValueRejectionReason.NON_DETERMINISTIC_NUMERIC,
        )

    state = value_field_state(
        observation, candidate.field_key, snapshot.field_evaluations
    )
    if state is not FieldState.VALID:
        return None, _reject(
            candidate,
            ValueRejectionReason.FIELD_STATE_NOT_VALID,
            f"aggregate field state is {state.value}",
        )

    lineage_state, lineage_reason = lineage_state_for_output(
        candidate.observation_ref,
        as_of,
        snapshot.transformation_lineage,
        observations,
    )
    if lineage_state is not FieldState.VALID:
        return None, _reject(
            candidate,
            lineage_reason or ValueRejectionReason.LINEAGE_NOT_REPRODUCIBLE,
            f"lineage state is {lineage_state.value}",
        )

    return (
        ContextValue(
            field_key=candidate.field_key,
            value=value,
            as_of=as_of,
            payload_digest=payload_digest,
            observation_ref=candidate.observation_ref,
        ),
        None,
    )


def publish_context_value_view(
    *,
    capsule: DecisionContextCapsule,
    snapshot: CriticalInputSnapshot | None,
    candidates: Sequence[AdmittedValue],
    scheme: CanonicalizationScheme,
) -> ValueResolution:
    """Publish the value view for one decision, or refuse with a named reason (design #32 §3.3)."""
    if snapshot is None:
        return ValueResolution(
            disposition=ValueViewDisposition.SNAPSHOT_UNRESOLVED,
            detail=(
                "the Capsule's SnapshotRef resolved to no snapshot body — no value surface is "
                "published and every value operand stays UNKNOWN (design #32 §3.3/§6)"
            ),
        )
    if not snapshot_binds_capsule_reference(capsule, snapshot):
        return ValueResolution(
            disposition=ValueViewDisposition.BINDING_MISMATCH,
            detail=(
                "the resolved snapshot's id/digest does not match the Capsule's SnapshotRef — a "
                "more-permissive substitute is refused (ADR-002-018 §15:386)"
            ),
        )
    if not value_namespace_is_disjoint(capsule):
        return ValueResolution(
            disposition=ValueViewDisposition.NAMESPACE_COLLISION,
            detail=(
                f"the reserved value namespace {VALUE_NAMESPACE!r} collides with a Capsule "
                "top-level key — merging would overwrite covered Capsule content "
                "(design #32 §3.2 (1))"
            ),
        )

    observations, ambiguous = index_observations(snapshot)
    admitted: list[ContextValue] = []
    rejected: list[RejectedValue] = []
    for candidate in candidates:
        value, rejection = _admit_one(
            candidate,
            snapshot=snapshot,
            observations=observations,
            ambiguous=ambiguous,
            scheme=scheme,
        )
        if rejection is not None:
            rejected.append(rejection)
            continue
        if (
            value is not None
        ):  # pragma: no branch - _admit_one returns exactly one of the two
            admitted.append(value)

    counts: dict[str, int] = {}
    for value in admitted:
        counts[value.field_key] = counts.get(value.field_key, 0) + 1
    contested = {key for key, count in counts.items() if count > 1}
    if contested:
        for value in admitted:
            if value.field_key in contested:
                rejected.append(
                    RejectedValue(
                        field_key=value.field_key,
                        observation_ref=value.observation_ref,
                        reason=ValueRejectionReason.DUPLICATE_FIELD_KEY,
                        detail=(
                            "two admitted observations claim this field — disagreement is never "
                            "resolved by average, majority, or arbitrary choice"
                        ),
                    )
                )
        admitted = [value for value in admitted if value.field_key not in contested]

    snapshot_id = snapshot.snapshot_id
    snapshot_digest = snapshot.canonical_digest
    if (
        snapshot_id is None or snapshot_digest is None
    ):  # pragma: no cover - binding gate precedes
        return ValueResolution(
            disposition=ValueViewDisposition.BINDING_MISMATCH,
            detail="the resolved snapshot carries no concrete identity/digest",
        )
    ordered = tuple(sorted(admitted, key=lambda item: item.field_key))
    view = ContextValueView(
        snapshot_id=snapshot_id,
        snapshot_canonical_digest=snapshot_digest,
        values=ordered,
        canonical_digest=context_value_view_digest(
            snapshot_id=snapshot_id,
            snapshot_canonical_digest=snapshot_digest,
            values=ordered,
            scheme=scheme,
        ),
        canonicalization_version=scheme.version,
    )
    disposition = (
        ValueViewDisposition.RESOLVED
        if ordered
        else ValueViewDisposition.EXPLICIT_EMPTY
    )
    return ValueResolution(
        disposition=disposition,
        view=view,
        rejected=tuple(rejected),
        detail=(
            None
            if ordered
            else (
                "the snapshot bound and no candidate passed the gates — a defined no-value "
                "context, materially different from an unresolved binding (design #32 §6)"
            )
        ),
    )
