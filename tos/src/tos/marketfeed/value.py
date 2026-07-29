"""Value production + verification — the pure layer (design #32 §2/§3.2/§4/§5).

This module turns a producer's candidate claims into a published
:class:`~tos.dsl.ContextValueView`, or refuses them with a named reason. It is the whole of D-E2's
substantive content, and it is **pure**: its import closure is
``{tos, tos.canonical, tos.capsule, tos.dsl, tos.marketfeed}`` — deliberately **no** ``tos.engine``,
which lives one layer up in :mod:`tos.marketfeed.resolver` (design #32 §3.4).

Four gates run, in this order, and every one of them is fail-closed:

1. **Binding integrity** (design #32 §3.3, ADR-002-018 §15:386). The snapshot body's
   ``snapshot_id`` / ``canonical_digest`` must equal the Capsule's ``SnapshotRef`` exactly. A
   disagreement is refused, never silently substituted with something more permissive.

2. **Value ⟺ digest binding** (design #32 §2.3, RFC-004 §9:244). The candidate's payload preimage
   must digest to the attributed observation's ``raw.payload_digest``, and the value must be an
   entry of that preimage. This is what makes the value an *attributed* Critical Input rather than
   a side channel: change the value and the preimage digest changes, so it no longer matches the
   observation the snapshot covers, and the snapshot digest itself would have to change with it.

3. **The VALID gate** (design #32 §2.2, MINOR-4). A single definition, positive, three-way:
   ``worst(admitted_field_state(admission), observation.field_state, ⋃ matching field evaluations)``
   must be ``VALID``. With **no** matching field evaluation an explicit ``UNKNOWN`` floor is
   supplied, because :func:`tos.capsule.worst` aggregates an empty iterable to ``VALID``
   (``field_state.py:70-87`` — "callers must supply explicit UNKNOWN floor"): an unevaluated field
   is not a valid one. The gate is ``is FieldState.VALID``, never ``!= INVALID``.

4. **Lineage** (design #32 §5). A derived value's lineage node must be reproducible with exact
   parents (reusing :func:`tos.capsule.predicates.derive_lineage_state`), and every recorded parent's
   as-of must be **at or before** the derived value's as-of. A parent that cannot be resolved fails
   closed rather than being assumed sound.

⚠ **Honest limits, stated as limits.**

* The value ⟺ digest check happens **here, at publication**. The environment-injection point does
  not re-verify it (design #32 §2.3/§4.3 trust seam). Detection downstream comes from the view
  digest joining the recorded signature, not from a second verification.
* Look-ahead is checked against what the lineage **records**. A producer that simply omits a parent
  link is caught only insofar as ``derive_lineage_state`` rejects an empty parent set; a producer
  that fabricates a plausible-looking parent set is not. Runtime look-ahead enforcement over a real
  replay is D-E3's (design #32 §5.4).
* Per-bar distinctness is a **structural corollary** of distinct as-of times riding a covered
  snapshot field, plus the concreteness gate here. A producer that stamps two different bars with
  the same as-of collapses it, and that is a producer-honesty problem this layer cannot close
  (design #32 §4.3).

⚠ **Provisional; closes no EV** (design #32 §1.1): every digest here rides ``ev-l1-provisional-0``.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only. No ``tos.engine``, no clock, no RNG, no network.
"""

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


# ---------------------------------------------------------------------------
# Namespace disjointness — measured, never declared (design #32 §3.2 (1), MINOR-3)
# ---------------------------------------------------------------------------


def capsule_top_level_keys(capsule: DecisionContextCapsule | None = None) -> frozenset[str]:
    """The Capsule's actual top-level key set (design #32 §3.2 (1)).

    Read off the shipped model rather than transcribed into a constant: a hand-copied list of
    seventeen field names is a snapshot of a moment, and the moment a Capsule field is added the
    list is silently wrong. When a concrete ``capsule`` is supplied the keys come from its real
    ``model_dump(mode="json")`` — the very mapping :func:`~tos.dsl.build_environment` merges into —
    so the check is on the object at hand, not on a class-level approximation.

    Args:
        capsule: The Capsule whose dump is inspected; ``None`` falls back to the declared field
            names of the model class.

    Returns:
        The top-level key set.
    """
    if capsule is not None:
        return frozenset(capsule.model_dump(mode="json"))
    return frozenset(DecisionContextCapsule.model_fields)


def value_namespace_is_disjoint(capsule: DecisionContextCapsule | None = None) -> bool:
    """Whether the reserved value namespace collides with no Capsule top-level key.

    Args:
        capsule: The Capsule to measure; ``None`` measures the model class.

    Returns:
        ``True`` iff :data:`~tos.dsl.VALUE_NAMESPACE` is absent from the Capsule's top-level keys.
    """
    return VALUE_NAMESPACE not in capsule_top_level_keys(capsule)


# ---------------------------------------------------------------------------
# Snapshot binding (design #32 §3.3; ADR-002-018 §15:373-386)
# ---------------------------------------------------------------------------


def snapshot_binds_capsule_reference(
    capsule: DecisionContextCapsule, snapshot: CriticalInputSnapshot
) -> bool:
    """Whether a snapshot body is *the exact one* the Capsule references (design #32 §3.3).

    Both the id and the digest must be concrete on both sides and equal. Concreteness is required
    positively: a ``None`` on either side is not a match, so a reference-less Capsule and a
    digest-less snapshot cannot accidentally "agree" by both being empty — the ADR-002-018 §15:386
    "no silent substitute that is more permissive" rule in its smallest form.

    Args:
        capsule: The Capsule carrying the ``SnapshotRef``.
        snapshot: The resolved snapshot body.

    Returns:
        ``True`` iff the body is exactly the referenced snapshot.
    """
    ref = capsule.critical_input_snapshot
    if ref.snapshot_id is None or ref.canonical_digest is None:
        return False
    # ★ Redundant defence — a *provably equivalent* mutant, kept deliberately (review MINOR-2 N4).
    #
    # Two corrections to the review's reasoning, both measured 2026-07-29 against the shipped
    # models. (a) The premise "an IdDerivedArtifact can never carry a None id/digest" is false: a
    # pre-issuance ``CriticalInputSnapshot()`` *is* constructible through ordinary construction —
    # ``status=DRAFT`` leaves both ``None`` — as is a pre-issuance ``DecisionContextCapsule()``. So
    # this line does get executed. (b) It nevertheless cannot change the result, which is the
    # stronger statement: control only reaches here once the reference side is positively concrete,
    # and for a concrete ``ref`` against any ``None`` snapshot field the equality below is already
    # ``False`` (``"cis-1" == None``). Deleting these two lines is therefore behaviour-preserving —
    # no test can kill it, and one that appeared to would be testing something else.
    #
    # It stays because the equality's fail-closed behaviour would then be *incidental* (a property
    # of ``==`` against ``None``) rather than *stated*. The both-None case — a DRAFT capsule against
    # a DRAFT snapshot — is caught one branch earlier by the reference-side guard; this makes the
    # symmetric claim explicit on the body side rather than leaving it to be re-derived.
    if snapshot.snapshot_id is None or snapshot.canonical_digest is None:
        return False
    return (
        ref.snapshot_id == snapshot.snapshot_id
        and ref.canonical_digest == snapshot.canonical_digest
    )


# ---------------------------------------------------------------------------
# The VALID gate (design #32 §2.2, MINOR-4)
# ---------------------------------------------------------------------------


def value_field_state(
    observation: Observation,
    field_key: str,
    field_evaluations: Sequence[FieldEvaluation],
) -> FieldState:
    """The single three-way VALID gate for one value (design #32 §2.2/§6).

    ``worst`` over three sources: the observation's admission result mapped conservatively
    (:func:`~tos.capsule.predicates.admitted_field_state`), the observation's own recorded
    ``field_state``, and the states of every field evaluation whose ``field_ref`` names this
    ``field_key``.

    **The ∅ seal.** When no field evaluation names the key, an explicit ``UNKNOWN`` is added to the
    aggregate. Without it, ``worst(())`` returns ``VALID`` (the lattice identity, ``field_state.py``
    lines 70-87) and an *unevaluated* field would sail through the gate — vacuous validity, the
    exact fail-open this seals. The value's governance therefore comes from the snapshot's own
    evaluations, not from the value's say-so (구조 파생 > 자기신고).

    Args:
        observation: The attributed observation.
        field_key: The DSL-visible field name, matched against ``FieldEvaluation.field_ref``.
        field_evaluations: The snapshot's field evaluations.

    Returns:
        The aggregate :class:`~tos.capsule.FieldState`; only ``VALID`` admits.
    """
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
        # ★ explicit UNKNOWN floor — an unevaluated field is not a valid one (design #32 §2.2).
        states.append(FieldState.UNKNOWN)
    else:
        states.extend(matching)
    return worst(states)


# ---------------------------------------------------------------------------
# Lineage: reproducibility + look-ahead (design #32 §5)
# ---------------------------------------------------------------------------


def index_observations(
    snapshot: CriticalInputSnapshot,
) -> tuple[dict[str, Observation], frozenset[str]]:
    """Index a snapshot's observations by raw-event identity (design #32 §2.3).

    Args:
        snapshot: The snapshot whose observations are indexed.

    Returns:
        ``(index, ambiguous)`` — the ``raw_event_id -> Observation`` mapping, and the set of ids
        carried by **more than one** observation. An ambiguous id is excluded from the index: two
        observations under one identity give a value no single attributable provenance, and picking
        either would be an arbitrary fold.
    """
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
    # ★ Second seal, and load-bearing beyond the publication path (review MINOR-2 L7).
    # :func:`_admit_one` already refuses a candidate whose ``observation_ref`` is in the returned
    # ``ambiguous`` set, so for *that* caller this pop is defence in depth. It is **not** redundant
    # for the others: this function is a public export, and :func:`lineage_state_for_output`
    # resolves lineage parents through the index alone, with no access to the ambiguous set. Leaving
    # an ambiguous id in the index would hand that path the *first* observation under a contested
    # identity — an arbitrary fold. Popping it makes the parent unresolvable, so causality fails
    # closed to ``UNKNOWN`` instead (design #32 §5.4/§6).
    for raw_event_id in ambiguous:
        index.pop(raw_event_id, None)
    return index, frozenset(ambiguous)


def lineage_state_for_output(
    output_id: str,
    output_as_of: int,
    lineage: Sequence[TransformationLineage],
    observations: Mapping[str, Observation],
) -> tuple[FieldState, ValueRejectionReason | None]:
    """The field state a value inherits from its transformation lineage (design #32 §5).

    A value with no lineage node is a *direct* observation, not a derived one, and inherits
    ``VALID`` — there is no derivation to be unreproducible about. This is deliberate and is **not**
    the vacuous-∅ case §2.2 seals: the applicable side (is this value derived at all?) is checked
    before the empty set is interpreted, which is the #26 WDR MAJOR-1 lesson (a fail-closed guard
    that swallows a case the contract explicitly permits is its own defect).

    For a value that *is* derived, two independent judgements combine:

    * reproducibility — delegated verbatim to
      :func:`~tos.capsule.predicates.derive_lineage_state` (non-reproducible, empty parent set, a
      parent missing its id or digest, or an undeclared stochastic transform ⇒ ``INVALID``;
      ADR-002-018 §10:288);
    * causality — every recorded parent's ``source_event_time`` must be **≤** the derived value's
      as-of. A strictly later parent is look-ahead (``INVALID``: proven bad). A parent that resolves
      to no observation is ``UNKNOWN`` (cannot be established — fail-closed, but not slandered as a
      proven violation; the polarity distinction is the honest one).

    Args:
        output_id: The derived value's observation reference (matched against ``output_id``).
        output_as_of: The derived value's as-of time.
        lineage: The snapshot's transformation-lineage nodes.
        observations: The ``raw_event_id -> Observation`` index.

    Returns:
        ``(state, reason)`` — ``reason`` names the first blocking cause, or ``None`` when ``VALID``.
    """
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


# ---------------------------------------------------------------------------
# Scalar projection (design #32 §2.5, MINOR-2)
# ---------------------------------------------------------------------------


def project_scalar(token: ScalarValue) -> tuple[ScalarValue | None, ValueRejectionReason | None]:
    """Project a preimage token onto a DSL-comparable scalar, or refuse it (design #32 §2.5).

    Three admitted shapes and one refusal:

    * ``bool`` — exposed; the DSL compares it with ``EQ``/``NE`` only and never orders it
      (``vocabulary.py:366-368``), which is the correct treatment of a flag;
    * ``int`` — exposed; this is the **preferred** numeric form. Integer minor/tick units are exact
      and platform-independent, so ordering comparisons have no binary-representation edge cases at
      all. Unit / scale / multiplier / sign stay in the observation's ``mapping`` provenance
      (``observation.py:107-115``), where they are separate safety-significant fields;
    * ``str`` — exposed as a string, and **not** parsed. A numeric-looking string stays a string: a
      silent string → number coercion is exactly the hidden conversion §2.5 forbids. State values
      (``session == "REGULAR"``) are this shape;
    * ``float`` — **refused** (``NON_DETERMINISTIC_NUMERIC``). The fractional path needs a *fixed*
      deterministic decimal → float projection rule, and that rule is not yet ratified. Until it is,
      a fractional magnitude is structurally UNKNOWN rather than silently exposed under an
      unspecified rounding. An integral-valued float is refused for the same reason and not
      quietly narrowed to ``int`` — that narrowing would itself be the silent coercion.

    Args:
        token: The preimage token.

    Returns:
        ``(value, None)`` when the token projects, ``(None, reason)`` when it does not.
    """
    if isinstance(token, bool):
        return token, None
    if isinstance(token, int):
        return token, None
    if isinstance(token, str):
        return token, None
    return None, ValueRejectionReason.NON_DETERMINISTIC_NUMERIC


# ---------------------------------------------------------------------------
# View digest (design #32 §2.2/§3.2 (3b))
# ---------------------------------------------------------------------------


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
    """The canonical digest of a value set (design #32 §2.2/§3.2 (3b)).

    Computed with the **injected** scheme — the shipped ``tos.canonical`` substrate, never a
    marketfeed-local hash (design #32 §12.1 REUSE). Values are ordered by ``field_key`` so the
    digest depends on the value *set*, not on the order a producer happened to emit them in, while
    each value's as-of and provenance pointer are inside the preimage so a same-valued, different-bar
    view still digests differently.

    Args:
        snapshot_id: The bound snapshot's id.
        snapshot_canonical_digest: The bound snapshot's digest.
        values: The admitted values.
        scheme: The injected canonicalization scheme.

    Returns:
        The hex digest.
    """
    return scheme.compute_digest(
        _covered_view_content(
            snapshot_id=snapshot_id,
            snapshot_canonical_digest=snapshot_canonical_digest,
            values=values,
        )
    )


def view_digest_matches(view: ContextValueView, scheme: CanonicalizationScheme) -> bool:
    """Whether a view's recorded digest is the digest of its own content (design #32 §2.2).

    The carrier is a lean container that records its digest rather than re-deriving it, so this is
    the predicate that re-derives it. A view whose digest does not match its content is not a view
    of that content, and the recorded signature it would feed would be a fiction.

    Args:
        view: The published view.
        scheme: The injected canonicalization scheme.

    Returns:
        ``True`` iff the recorded digest equals the recomputed one.
    """
    return view.canonical_digest == context_value_view_digest(
        snapshot_id=view.snapshot_id,
        snapshot_canonical_digest=view.snapshot_canonical_digest,
        values=view.values,
        scheme=scheme,
    )


# ---------------------------------------------------------------------------
# Publication (design #32 §2.3/§3.3/§4.2/§6)
# ---------------------------------------------------------------------------


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
    if is_wildcard_field_key(candidate.field_key):  # pragma: no cover - blocked at construction
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

    # ★ value ⟺ covered digest (design #32 §2.3). Recomputed from the producer's preimage and
    # compared against what the *snapshot-covered* observation attests — not against anything the
    # producer also supplied.
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

    state = value_field_state(observation, candidate.field_key, snapshot.field_evaluations)
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
    """Publish the value view for one decision, or refuse with a named reason (design #32 §3.3).

    The full publication gate. Nothing is invented here: every field of every published value is
    read off the snapshot the Capsule already binds, and a candidate that fails any gate is dropped
    with its cause recorded. A dropped value is simply **absent** from the environment, so the
    policy's read of it resolves to ``UNKNOWN`` and every comparison against it is ``False`` — the
    action set can only narrow (RFC-008 §10:347-350).

    Args:
        capsule: The Decision Context Capsule whose ``SnapshotRef`` is being resolved.
        snapshot: The resolved snapshot body, or ``None`` when the store produced none.
        candidates: The producer's candidate values.
        scheme: The injected canonicalization scheme.

    Returns:
        The :class:`~tos.marketfeed.records.ValueResolution`.
    """
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
        if value is not None:  # pragma: no branch - _admit_one returns exactly one of the two
            admitted.append(value)

    # ★ source disagreement: a repeated field_key is refused wholesale, never folded onto one
    # arbitrary winner and never averaged (ADR-002-018 §11:311, §14:365; design #32 §6).
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
    if snapshot_id is None or snapshot_digest is None:  # pragma: no cover - binding gate precedes
        # Unreachable through ``snapshot_binds_capsule_reference``, kept as a fail-closed backstop
        # rather than an unchecked narrowing assumption.
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
        ValueViewDisposition.RESOLVED if ordered else ValueViewDisposition.EXPLICIT_EMPTY
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
