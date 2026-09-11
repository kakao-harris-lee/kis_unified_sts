"""Operator-attested "pending" currentness dimensions (design #40 §5 order 6;
team-lead follow-up guidance on the slice #3 review, 2026-09-08).

``tos.cur.predicates.vector_complete`` floors its mandated dimension set to
:data:`tos.cur.MANDATED_DIMENSION_FLOOR` — every non-conditional
:class:`~tos.cur.DimensionKey` (21 members). This composition's own live
services structurally establish exactly four of them (``COMMIT_LOG``,
``TRUSTWORTHY_TIME``, ``SAFETY_AUTHORITY``, ``ACTION_FLOW`` —
:mod:`tos_runtime.currentness.vector`'s own ``_owned_dimensions``/
``_injected_dimensions``). The remaining 17 (spg profile / deviation /
incident / monitoring / release / post_trade / critical_input / context /
constraint / construction / trading_approval / egress_identity /
environment_scope / currentness_policy / recovery / decision_proof_intent /
aggregate_risk) have **no runtime owner in Phase 2** — no lane P/Q/R/S
service computes a real ``positively_established`` verdict for them.

Per team-lead's explicit instruction, this module supplies those 17 from
**composition config as explicitly-declared operator-attested revisions**
— never as a kernel-derived judgement, and never fabricated silently: every
field is a named-TBD ``null`` in the example config, and a still-null field
refuses composition at startup (the same fail-closed discipline every other
``tos_runtime.*.config`` loader in this codebase applies). Each dimension's
``owner_identity`` is stamped ``"operator-attestation-pending-phase-5"`` so a
reader of the assembled vector can see, structurally, which coordinates are
a real runtime owner's verdict and which are an interim operator sign-off
standing in for one — this is never presented as if a Phase 5 runtime owner
produced it.

This is a compose-only artifact: it satisfies the SAME
:class:`~tos.cur.state.CurrentnessDimension` shape
:mod:`tos_runtime.currentness.vector`'s own owned/injected dimensions use,
and is passed to :meth:`~tos_runtime.currentness.vector.CurrentnessAssembler.assemble`'s
own ``extra_dimensions`` parameter — never invented inside that module.

**Current count (historical "17" above is this module's ORIGINAL framing, left unedited —
:data:`PENDING_DIMENSION_KEYS` below is the live truth).** Phase 5 W3-a1/a2/b/W3.1/W3.2 have
since landed real dimension-owner readers for fourteen of the original seventeen
(:data:`_READER_OWNED_DIMENSION_KEYS` — each entry's own comment names its reader). Three
remain pending: ``CONTEXT``/``CRITICAL_INPUT`` (no runtime ``tos.capsule`` producer exists at
all — a future capsule-chain wave, not this one) and ``EGRESS_IDENTITY`` (partial kernel
predicate coverage only — see :data:`_READER_OWNED_DIMENSION_KEYS`'s own comment).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.cur import MANDATED_DIMENSION_FLOOR, CurrentnessRevision, DimensionKey
from tos.cur.state import CurrentnessDimension

__all__ = [
    "PendingDimensionConfigError",
    "PendingDimensionSpec",
    "PENDING_DIMENSION_KEYS",
    "load_pending_currentness_dimensions",
    "stamp_pending_dimensions",
]

#: The four dimensions a real Phase 2 runtime service structurally owns
#: (``tos_runtime.currentness.vector``'s own ``_owned_dimensions``/
#: ``_injected_dimensions``) — everything else in the mandated floor is
#: "pending" (module docstring).
_OWNED_DIMENSION_KEYS: frozenset[DimensionKey] = frozenset(
    {
        DimensionKey.COMMIT_LOG,
        DimensionKey.TRUSTWORTHY_TIME,
        DimensionKey.SAFETY_AUTHORITY,
        DimensionKey.ACTION_FLOW,
    }
)

#: Dimensions Phase 5 W3 has since given a real ``dimension_readers`` entry
#: (plan §2 decision 3, "1차원=1커밋") — each key here is deliberately
#: EXCLUDED from :data:`PENDING_DIMENSION_KEYS` below and, symmetrically,
#: refused if a ``currentness_dimensions.yaml`` config still carries a block
#: for it (module docstring; a stale config must never silently pretend to
#: attest a value this runtime now derives on its own — mirrors
#: :mod:`tos_runtime.compose._egress_attestations`'s own
#: ``_RETIRED_DERIVED_KEYS`` idiom). Grown one key at a time, never all at
#: once, so each dimension's own RED test / reader / config-block removal
#: lands as one reviewable commit.
_READER_OWNED_DIMENSION_KEYS: frozenset[DimensionKey] = frozenset(
    {
        #: ``tos_runtime.compose._currentness_wiring``'s own
        #: ``_currentness_policy_dimension_reader_for`` — the assembler's own governing
        #: ``CurrentnessPolicy``/``mandated`` floor, run through the kernel's own
        #: ``tos.cur.predicates.policy_covers_mandated_dimensions`` (no new runtime state
        #: needed — this composition already holds both facts).
        DimensionKey.CURRENTNESS_POLICY,
        #: ``_recovery_dimension_reader_for`` — the TOS Phase 5 W1 recovery barrier's own
        #: ``RecoveryVerdict.readiness_verdict``.
        DimensionKey.RECOVERY,
        #: ``_trading_approval_dimension_reader_for`` — step 4's own recorded
        #: ``IndependentApprovalStage`` verdict.
        DimensionKey.TRADING_APPROVAL,
        #: ``_environment_scope_dimension_reader_for`` — the kernel's own
        #: ``tos.brockercap.predicates.environment_binding_ok`` over the SAME
        #: environment/scope tokens ``tos_runtime.compose.context`` already computes.
        DimensionKey.ENVIRONMENT_SCOPE,
        #: EGRESS_IDENTITY is deliberately NOT here (W3.1 independent review MEDIUM-4,
        #: re-investigated and reconfirmed in Phase 5 W3.2): it was briefly reader-owned
        #: via ``credential_route_authority_disjoint`` alone (1 of 3 kernel predicates),
        #: and asserting ``positively_established`` on that partial coverage was an
        #: over-claim. Still pending — ``stale_principal_structurally_rejected`` and
        #: ``egress_generation_monotonic`` (the other two kernel predicates,
        #: ``tos.egress.predicates``) need an ``ActiveEgressPrincipalSet``/prior
        #: ``OrderingEvent`` this runtime has ZERO production imports of
        #: (``grep -rn ActiveEgressPrincipalSet tos/runtime/src`` — empty); the one real
        #: predicate is recorded as an evidence-only observation, never a dimension
        #: verdict (``_wiring.py``'s ``_record_egress_identity_observation``).
        #: The four Phase 5 W3-a1/a2 safety-mesh services (plan §2 decision 2) —
        #: ``tos_runtime.compose._safety_wiring.build_safety_mesh``'s own
        #: ``dimension_readers``, folded in by ``_build_dimension_readers``.
        DimensionKey.SAFETY_ENVELOPE_PROFILE,
        DimensionKey.DEVIATION,
        DimensionKey.INCIDENT,
        DimensionKey.MONITORING,
        #: Phase 5 W3.2 (plan §2 decisions 2-6) — the six remaining currentness dimension
        #: owners: ``_aggregate_risk_dimension_reader_for`` (step 6's already-computed
        #: ``AggregateRiskDecision.result``), ``_construction_dimension_reader_for``
        #: (step 2's already-computed ioc verdicts), ``_constraint_dimension_reader_for``
        #: (step 3's ``order_shape_admissible`` verdict, partial coverage disclosed),
        #: ``_decision_proof_intent_dimension_reader_for`` (step 13's
        #: ``exact_binding_holds`` verdict), ``_post_trade_dimension_reader_for``
        #: (``FinalityReleaseConsumer.latest_release_is_conflict_free``), and
        #: ``_release_dimension_reader_for`` (boot's own STAGE B release-admission
        #: verdict) — see each reader's own docstring in
        #: ``tos_runtime.compose._currentness_wiring``.
        DimensionKey.AGGREGATE_RISK,
        DimensionKey.CONSTRUCTION,
        DimensionKey.CONSTRAINT,
        DimensionKey.DECISION_PROOF_INTENT,
        DimensionKey.POST_TRADE,
        DimensionKey.RELEASE,
    }
)

#: The mandated-floor dimensions with no Phase 2/5 runtime owner yet, sorted
#: for a deterministic config file / iteration order. Shrinks as
#: :data:`_READER_OWNED_DIMENSION_KEYS` grows.
PENDING_DIMENSION_KEYS: tuple[DimensionKey, ...] = tuple(
    sorted(
        MANDATED_DIMENSION_FLOOR - _OWNED_DIMENSION_KEYS - _READER_OWNED_DIMENSION_KEYS,
        key=lambda k: k.value,
    )
)

#: The operator-attestation owner-identity label stamped on every pending
#: dimension (module docstring — never claims a real runtime owner).
_PENDING_OWNER_IDENTITY = "operator-attestation-pending-phase-5"


class PendingDimensionConfigError(Exception):
    """Raised when the pending-dimensions config is missing, malformed, or
    carries an unfilled (named-TBD) field for any of the 17 pending
    dimensions — fail-closed at load, never a silent default."""


@dataclass(frozen=True)
class PendingDimensionSpec:
    """One operator-attested pending dimension's content, everything except
    the per-assemble-call ``at_revision`` stamp (module docstring)."""

    dimension_key: DimensionKey
    bound_generation: int
    bound_digest: str
    restrictive_floor: int
    positively_established: bool


def _require_dimension_block(raw: Any, key: DimensionKey, path: Path) -> dict[str, Any]:
    block = raw.get(key.value) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise PendingDimensionConfigError(
            f"{path}: pending-dimensions config missing a mapping entry for "
            f"{key.value!r} — refusing to start"
        )
    return block


def _require_field(
    block: dict[str, Any], field: str, key: DimensionKey, path: Path
) -> Any:
    if field not in block or block[field] is None:
        raise PendingDimensionConfigError(
            f"{path}: pending-dimensions config entry {key.value!r} has an "
            f"unfilled (named-TBD) field {field!r} — refusing to start until "
            "an operator attests a concrete value"
        )
    return block[field]


def load_pending_currentness_dimensions(path: Path) -> tuple[PendingDimensionSpec, ...]:
    """Load + fail-closed-validate the 17 operator-attested pending
    dimensions from ``path`` (shaped like
    ``tos/runtime/config/currentness_dimensions.example.yaml``).

    Args:
        path: The YAML config file — one top-level mapping entry per
            :data:`PENDING_DIMENSION_KEYS` member, each with
            ``bound_generation``/``bound_digest``/``restrictive_floor``/
            ``positively_established``.

    Returns:
        One :class:`PendingDimensionSpec` per pending dimension, in
        :data:`PENDING_DIMENSION_KEYS` order.

    Raises:
        PendingDimensionConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, an entry is absent, or any of its
            four fields is still ``null`` (named-TBD).
    """
    if not path.is_file():
        raise PendingDimensionConfigError(
            f"pending-dimensions config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PendingDimensionConfigError(
            f"pending-dimensions config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PendingDimensionConfigError(
            f"pending-dimensions config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise PendingDimensionConfigError(
            f"pending-dimensions config file must be a top-level mapping: {path}"
        )
    stale = sorted(
        key.value for key in _READER_OWNED_DIMENSION_KEYS if key.value in raw
    )
    if stale:
        raise PendingDimensionConfigError(
            f"{path}: {stale!r} are no longer pending — each now has a real "
            "tos_runtime.currentness.vector.CurrentnessAssembler dimension_readers "
            "entry (Phase 5 plan §2 decision 3); remove these blocks from this config"
        )

    specs: list[PendingDimensionSpec] = []
    for key in PENDING_DIMENSION_KEYS:
        block = _require_dimension_block(raw, key, path)
        bound_generation = _require_field(block, "bound_generation", key, path)
        bound_digest = _require_field(block, "bound_digest", key, path)
        restrictive_floor = _require_field(block, "restrictive_floor", key, path)
        positively_established = _require_field(
            block, "positively_established", key, path
        )
        if isinstance(bound_generation, bool) or not isinstance(bound_generation, int):
            raise PendingDimensionConfigError(
                f"{path}: {key.value!r}.bound_generation must be an int "
                f"(got {bound_generation!r})"
            )
        if not isinstance(bound_digest, str) or not bound_digest.strip():
            raise PendingDimensionConfigError(
                f"{path}: {key.value!r}.bound_digest must be a non-blank string "
                f"(got {bound_digest!r})"
            )
        if isinstance(restrictive_floor, bool) or not isinstance(
            restrictive_floor, int
        ):
            raise PendingDimensionConfigError(
                f"{path}: {key.value!r}.restrictive_floor must be an int "
                f"(got {restrictive_floor!r})"
            )
        if not isinstance(positively_established, bool):
            raise PendingDimensionConfigError(
                f"{path}: {key.value!r}.positively_established must be a bool "
                f"(got {positively_established!r})"
            )
        specs.append(
            PendingDimensionSpec(
                dimension_key=key,
                bound_generation=bound_generation,
                bound_digest=bound_digest,
                restrictive_floor=restrictive_floor,
                positively_established=positively_established,
            )
        )
    return tuple(specs)


def stamp_pending_dimensions(
    specs: tuple[PendingDimensionSpec, ...], *, at_revision: CurrentnessRevision
) -> tuple[CurrentnessDimension, ...]:
    """Stamp the loaded, revision-independent specs with the CURRENT
    :class:`~tos.cur.CurrentnessRevision` (read off an already-assembled
    vector — never re-derived from the RCL log's own internal formula,
    which stays private to
    :class:`~tos_runtime.currentness.vector.CurrentnessAssembler`).

    Args:
        specs: The loaded pending-dimension specs.
        at_revision: The revision every OTHER dimension in this same vector
            sits at (``tos.cur.predicates.single_revision_consistent``
            requires every dimension to share exactly one revision).

    Returns:
        One :class:`~tos.cur.state.CurrentnessDimension` per spec, ready to
        pass as ``CurrentnessAssembler.assemble``'s ``extra_dimensions``.
    """
    return tuple(
        CurrentnessDimension(
            dimension_key=spec.dimension_key,
            owner_identity=_PENDING_OWNER_IDENTITY,
            bound_generation=spec.bound_generation,
            bound_digest=spec.bound_digest,
            restrictive_floor=spec.restrictive_floor,
            positively_established=spec.positively_established,
            at_revision=at_revision,
        )
        for spec in specs
    )
