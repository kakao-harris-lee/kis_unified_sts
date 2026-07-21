"""Replay Capsule + divergence result (design #4 §2.5 D, §6, template SoT).

Models ``REPLAY-CAPSULE-template.yaml`` (89 lines). A digest-bound artifact
(``content_digest == H_ver(canonicalize(baseline + inputs + determinism +
expected))``, design §3.2) with an **independent** ``replay_capsule_id``.

**Interpretations (design deviations, reported):** the inherited
``canonical_digest`` realizes the template ``content_digest``; covered =
{baseline, inputs, determinism, expected} (design §3.2). ``isolation`` (runtime
environment assertion), ``result`` (outcome), ``version`` / ``created_by`` /
``review`` (meta) are self-excluded from the digest.

Divergence (design §6.1, ERI-INV-009): :func:`compute_replay_result` is a pure
function whose result is **never** ``MATCH`` if any of {unsupported baseline,
missing/corrupt input, digest mismatch, schema incompatibility, unbounded
nondeterminism} holds. A tolerance can never turn a safety-relevant DIVERGED into
a MATCH (design §6); "MATCH establishes reproducibility, not adequacy" (§6.3).

Pure module: ``pydantic`` + stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, ArtifactStatus, FrozenModel
from tos.evidence._base import EvidenceArtifact
from tos.evidence.elements import (
    NondeterministicBoundary,
    NormalizedViewVersion,
    SourceContinuityVector,
    Tolerance,
)

_ISOLATION_ENV_DEFAULT = "non-live-replay"  # template line 61
_REVIEW_RESULT_DEFAULT = "NOT_REVIEWED"  # template line 85
_ISOLATION_LIVE_FLAGS = (
    "live_credentials_present",
    "live_broker_route_reachable",
    "production_mutation_endpoint_reachable",
    "live_approval_or_authorization_consumable",
)
_RESULT_AUTHORITY_FLAGS = ("creates_authority", "may_mutate_live_state", "may_rearm")


class ReplayResultState(StrEnum):
    """Replay result states (design §6.1, ADR §15 line 399-405)."""

    NOT_RUN = "NOT_RUN"
    MATCH = "MATCH"
    DIVERGED = "DIVERGED"
    INCONCLUSIVE = "INCONCLUSIVE"
    CORRUPT_INPUT = "CORRUPT_INPUT"
    UNSUPPORTED_BASELINE = "UNSUPPORTED_BASELINE"


def compute_replay_result(
    *,
    baseline_supported: bool,
    input_complete: bool,
    schema_compatible: bool,
    nondeterminism_bounded: bool,
    expected_state_digest: str | None,
    actual_state_digest: str | None,
) -> ReplayResultState:
    """Compute a replay result from declared fields (design §6.1, ERI-INV-009).

    Pure function. The result is ``MATCH`` only when the baseline is supported,
    inputs are complete, the schema is compatible, all nondeterminism is bounded,
    and the expected/actual state digests are present and equal. Any single
    failure yields a non-``MATCH`` result — so an unsupported baseline, a
    missing/corrupt input, a digest mismatch, a schema incompatibility, or
    unbounded nondeterminism can never be reported as reproduced.

    Args:
        baseline_supported: Whether the exact baseline is supported (§6.2).
        input_complete: Whether every required raw input is present.
        schema_compatible: Whether the record/migration schema is compatible.
        nondeterminism_bounded: Whether every declared boundary is bounded (§2.5 D).
        expected_state_digest: The expected end-state digest (``None`` if absent).
        actual_state_digest: The actual end-state digest (``None`` if not run to
            completion).

    Returns:
        The conservative :class:`ReplayResultState`.
    """
    if not baseline_supported:
        return ReplayResultState.UNSUPPORTED_BASELINE
    if not input_complete:
        return ReplayResultState.CORRUPT_INPUT
    if expected_state_digest is None or actual_state_digest is None:
        return ReplayResultState.INCONCLUSIVE
    if expected_state_digest != actual_state_digest:
        return ReplayResultState.DIVERGED
    if not schema_compatible:
        return ReplayResultState.INCONCLUSIVE
    if not nondeterminism_bounded:
        return ReplayResultState.INCONCLUSIVE
    return ReplayResultState.MATCH


class ReplayBaseline(FrozenModel):
    """Exact baseline binding (template lines 7-26, design §6.2)."""

    repository_commit_sha: str | None = None
    build_artifact_digest: str | None = None
    rfc_adr_versions: tuple[str, ...] = ()
    hard_safety_envelope_digest: str | None = None
    runtime_safety_profile_digest: str | None = None
    safety_configuration_activation_record_digest: str | None = None
    human_authority_policy_digest: str | None = None
    effective_principal_graph_digest: str | None = None
    broker_capability_profile_digest: str | None = None
    evidence_integrity_policy_digest: str | None = None
    recovery_barrier_policy_digest: str | None = None
    critical_input_policy_digest: str | None = None
    venue_constraint_policy_digest: str | None = None
    order_construction_policy_digest: str | None = None
    verification_profile_version: str | None = None
    schema_and_migration_digests: tuple[str, ...] = ()
    deployment_manifest_digest: str | None = None
    workload_identity_and_key_generations: tuple[str, ...] = ()
    test_harness_digest: str | None = None


class ReplayInputs(FrozenModel):
    """Exact input binding (template lines 28-51). Raw digests, never raw overwrite."""

    raw_evidence_record_ids: tuple[str, ...] = ()
    raw_evidence_record_digests: tuple[str, ...] = ()
    integrity_anchor_ids: tuple[str, ...] = ()
    normalized_view_versions: tuple[NormalizedViewVersion, ...] = ()
    initial_authoritative_snapshot_digests: tuple[str, ...] = ()
    committed_prefixes: tuple[str, ...] = ()
    time_health_snapshot_ids: tuple[str, ...] = ()
    random_seeds: tuple[str, ...] = ()
    fault_schedule_digest: str | None = None
    broker_stub_or_archive_digest: str | None = None
    external_input_digests: tuple[str, ...] = ()
    source_continuity_vectors: tuple[SourceContinuityVector, ...] = ()
    critical_input_observation_digests: tuple[str, ...] = ()
    transformation_lineage_digests: tuple[str, ...] = ()
    critical_input_snapshot_digests: tuple[str, ...] = ()
    decision_context_capsule_digests: tuple[str, ...] = ()
    context_invalidation_digests: tuple[str, ...] = ()
    venue_constraint_snapshot_digests: tuple[str, ...] = ()
    order_admissibility_decision_digests: tuple[str, ...] = ()
    canonical_broker_command_digests: tuple[str, ...] = ()
    economic_effect_envelope_digests: tuple[str, ...] = ()
    order_conformance_proof_digests: tuple[str, ...] = ()
    constraint_invalidation_digests: tuple[str, ...] = ()


class ReplayDeterminism(FrozenModel):
    """Determinism declaration (template lines 53-58, design §2.5 D)."""

    scheduler_identity: str | None = None
    dependency_archive_digest: str | None = None
    documented_nondeterministic_boundaries: tuple[NondeterministicBoundary, ...] = ()
    comparison_rule_id: str | None = None
    tolerances: tuple[Tolerance, ...] = ()


class ReplayIsolation(FrozenModel):
    """Isolation assertion (template lines 60-65, design §6.3, ERI-INV-008).

    Every ``live_*`` reachability flag is forced ``false``: the replay principal
    can reach no live credential, broker route, production mutation endpoint, or
    consumable authorization. The full "no live path" proof over a real topology
    is EV-L2+/Security (design §6.3).
    """

    environment_id: str = _ISOLATION_ENV_DEFAULT
    live_credentials_present: bool = False
    live_broker_route_reachable: bool = False
    production_mutation_endpoint_reachable: bool = False
    live_approval_or_authorization_consumable: bool = False

    @model_validator(mode="after")
    def _isolation_flags_false(self) -> ReplayIsolation:
        """Reject any true live-reachability flag (design §6.3)."""
        for name in _ISOLATION_LIVE_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"ReplayIsolation.{name} must be false (isolated replay — §6.3)"
                )
        return self


class ReplayExpected(FrozenModel):
    """Expected outputs (template lines 67-72)."""

    state_digest: str | None = None
    decision_digests: tuple[str, ...] = ()
    denial_digests: tuple[str, ...] = ()
    transmission_attempt_digests: tuple[str, ...] = ()
    invariant_report_digest: str | None = None


class ReplayResult(FrozenModel):
    """Result block (template lines 74-80, design §6.3).

    ``state`` defaults ``NOT_RUN``. Authority flags are forced ``false``:
    "MATCH establishes reproducibility, not adequacy" (§6.3).
    """

    state: ReplayResultState = ReplayResultState.NOT_RUN
    actual_state_digest: str | None = None
    divergence_report_digest: str | None = None
    creates_authority: bool = False
    may_mutate_live_state: bool = False
    may_rearm: bool = False

    @model_validator(mode="after")
    def _result_authority_false(self) -> ReplayResult:
        """Reject any true result-authority flag (design §6.3/§4.6)."""
        for name in _RESULT_AUTHORITY_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"ReplayResult.{name} must be false (reproducibility is not "
                    "adequacy/authority — §6.3)"
                )
        return self


class ReplayReview(FrozenModel):
    """Independent-review governance block (template lines 82-85). Excluded meta."""

    independent_reviewer: str | None = None
    evidence_location: str | None = None
    review_result: str = _REVIEW_RESULT_DEFAULT


class ReplayCapsule(EvidenceArtifact):
    """A digest-bound Replay Capsule (design #4 §2.5 D, §6).

    Binds baseline + inputs + determinism + expected under ``content_digest``;
    ``replay_capsule_id`` is the independent id. The divergence/baseline predicates
    (:func:`compute_replay_result`,
    :func:`tos.evidence.predicates.replay_baseline_supported`) are pure EV-L1
    functions over the declared fields.
    """

    _ID_FIELD: ClassVar[str] = "replay_capsule_id"
    # Exact-bind requirement (§6.2/§15, ERI-EV-008): an issued capsule must bind a
    # concrete baseline commit and an expected end-state digest. The non-empty
    # input binding is enforced in ``_replay_issuance_invariants`` (a required
    # covered path cannot express tuple non-emptiness). Sibling artifacts
    # (Envelope/Receipt/EIP) likewise carry a real ``_REQUIRED_COVERED``.
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "baseline.repository_commit_sha",
        "expected.state_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"baseline", "inputs", "determinism", "expected"}
    )

    # ---- Layer-0 identity + meta (self-excluded) ----
    # canonical_digest (= template content_digest) / status / canonicalization_version
    # inherited.
    replay_capsule_id: str | None = None
    version: str | None = None
    created_by: str | None = None

    # ---- Covered content ----
    baseline: ReplayBaseline = ReplayBaseline()
    inputs: ReplayInputs = ReplayInputs()
    determinism: ReplayDeterminism = ReplayDeterminism()
    expected: ReplayExpected = ReplayExpected()

    # ---- Excluded runtime/outcome/meta ----
    isolation: ReplayIsolation = ReplayIsolation()
    result: ReplayResult = ReplayResult()
    review: ReplayReview = ReplayReview()

    @model_validator(mode="after")
    def _replay_issuance_invariants(self) -> ReplayCapsule:
        """Enforce exact input binding + fail-closed stored MATCH (§6.2/§15, ERI-INV-009).

        Cross-field checks that ``ReplayResult`` alone cannot make (it has no
        access to the capsule's baseline / inputs / determinism):

        * **MAJOR-1** — an issued capsule must bind at least one raw-evidence
          record digest (an exact input binding is what makes replay meaningful;
          §6.2/§15/ERI-EV-008). A degenerate empty capsule is rejected.
        * **MAJOR-2** — a stored ``result.state == MATCH`` is fail-closed: it is
          rejected unless every declared nondeterministic boundary is bounded and
          the expected end-state digest + baseline commit are present. This binds
          the (correct) pure divergence predicate to the stored outcome so a false
          MATCH under unbounded nondeterminism / missing binding is unconstructable
          (ERI-INV-009), closing the bypass for consumers that trust ``result``.
        """
        if self.status == ArtifactStatus.DRAFT:
            return self
        if not self.inputs.raw_evidence_record_digests:
            raise ArtifactIntegrityError(
                "issued ReplayCapsule must bind at least one raw evidence record "
                "digest (inputs.raw_evidence_record_digests) — §6.2/§15/ERI-EV-008"
            )
        if self.result.state is ReplayResultState.MATCH:
            if any(
                not b.bounded
                for b in self.determinism.documented_nondeterministic_boundaries
            ):
                raise ArtifactIntegrityError(
                    "result.state=MATCH is unconstructable with an unbounded "
                    "nondeterministic boundary (never MATCH) — ERI-INV-009 §6.1"
                )
            if self.expected.state_digest is None:
                raise ArtifactIntegrityError(
                    "result.state=MATCH requires a concrete expected.state_digest "
                    "— ERI-INV-009 §6.1"
                )
            if self.baseline.repository_commit_sha is None:
                raise ArtifactIntegrityError(
                    "result.state=MATCH requires a bound baseline "
                    "(baseline.repository_commit_sha) — §6.2"
                )
        return self
