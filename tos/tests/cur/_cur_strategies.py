"""Shared valid-artifact builders + strategies for the cur property tests (design #23 §7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #23 §0.3). The builders enforce
the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be *genuinely*
complete / established, never a permissive shortcut):

* a **clean** vector carries **every** mandated dimension positively established at **one** revision,
  a matching policy, and a concrete ``vector_digest``, so a genuine ``vector_complete`` is achievable;
* a **clean** proof is genuinely admissible (result CURRENT, single-use unconsumed, unexpired, latch
  clear), so ``proof_admissible`` is genuinely satisfiable (not a shortcut);
* the **polarity strategies** deliberately generate ``None`` / ``False`` / ``True`` tri-bools so the
  polarity seals (the #22 MAJOR-2 lesson) are actually exercised across every ``bool | None`` field.

Every generation / floor value is an explicit fixture int — nothing here is a *policy* number; the
real cur bounds are Verification-Profile injected and all null in Phase 1 (design #23 §8). The
reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    CurrentnessDimension,
    CurrentnessPolicy,
    CurrentnessRevision,
    DimensionKey,
    EgressCurrentnessProof,
    EgressProofCoordinateSet,
    ProofResult,
    RestrictiveFenceRecord,
    SafetyCurrentnessVector,
)

#: The injected provisional canonicalizer (REUSE, design #23 §3.1 — no new scheme).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False`` per polarity).
TRIBOOL = st.sampled_from([True, False, None])

#: The clean single revision every clean dimension sits at.
_CLEAN_COMMIT_INDEX = 10


def clean_revision(
    *, revision_id: str = "rev-1", commit_index: int = _CLEAN_COMMIT_INDEX
) -> CurrentnessRevision:
    """One committed Currentness Revision (ordering identity, not a clock — §5.4)."""
    return CurrentnessRevision(revision_id=revision_id, commit_index=commit_index)


def clean_dimension(
    *,
    dimension_key: DimensionKey,
    revision: CurrentnessRevision | None = None,
    owner_identity: str = "owner-x",
    bound_generation: int = 5,
    bound_digest: str = "dg",
    restrictive_floor: int = 1,
    positively_established: bool | None = True,
) -> CurrentnessDimension:
    """One positively-established dimension coordinate at the given revision (§9)."""
    return CurrentnessDimension(
        dimension_key=dimension_key,
        owner_identity=owner_identity,
        bound_generation=bound_generation,
        bound_digest=bound_digest,
        restrictive_floor=restrictive_floor,
        positively_established=positively_established,
        at_revision=revision if revision is not None else clean_revision(),
    )


def clean_dimensions(
    keys: frozenset[DimensionKey] = MANDATED_DIMENSION_FLOOR,
    *,
    revision: CurrentnessRevision | None = None,
) -> tuple[CurrentnessDimension, ...]:
    """Every key positively established at one shared revision (a genuinely complete vector body)."""
    rev = revision if revision is not None else clean_revision()
    return tuple(
        clean_dimension(dimension_key=key, revision=rev) for key in sorted(keys)
    )


def clean_policy(
    *,
    policy_id: str = "pol-1",
    policy_generation: int = 1,
    required_dimensions: frozenset[DimensionKey] = MANDATED_DIMENSION_FLOOR,
    **overrides: object,
) -> CurrentnessPolicy:
    """A digest-verified policy that declares at least the mandated floor (genuinely complete)."""
    return CurrentnessPolicy.issue(
        scheme=SCHEME,
        policy_id=policy_id,
        policy_generation=policy_generation,
        required_dimensions=required_dimensions,
        **overrides,
    )


def clean_vector(
    *,
    vector_id: str = "vec-1",
    revision: CurrentnessRevision | None = None,
    dimensions: tuple[CurrentnessDimension, ...] | None = None,
    policy_id: str = "pol-1",
    policy_generation: int = 1,
    vector_digest: str = "vd",
    **overrides: object,
) -> SafetyCurrentnessVector:
    """A digest-verified, genuinely complete Safety Currentness Vector (id ⊥ digest, all-false)."""
    rev = revision if revision is not None else clean_revision()
    dims = dimensions if dimensions is not None else clean_dimensions(revision=rev)
    return SafetyCurrentnessVector.issue(
        scheme=SCHEME,
        vector_id=vector_id,
        currentness_revision=rev,
        vector_digest=vector_digest,
        policy_id=policy_id,
        policy_generation=policy_generation,
        dimensions=dims,
        **overrides,
    )


def clean_coordinates(
    *, local_latch_clear: bool | None = True, principal: str = "principal-1"
) -> EgressProofCoordinateSet:
    """The injected egress-scope coordinate mirror with a positively-clear latch (§5.7)."""
    return EgressProofCoordinateSet(
        principal=principal,
        deployment="deploy-1",
        credential="cred-1",
        signer="signer-1",
        route="route-1",
        endpoint="endpoint-1",
        broker_session="session-1",
        local_latch_clear=local_latch_clear,
    )


def clean_proof(
    *,
    proof_id: str = "ecp-1",
    nonce: str = "nonce-1",
    revision: CurrentnessRevision | None = None,
    single_use_consumed: bool | None = False,
    is_expired: bool | None = False,
    result: ProofResult | None = ProofResult.CURRENT,
    coordinates: EgressProofCoordinateSet | None = None,
    bound_generations: tuple[int, ...] = (5,),
    restrictive_floors: tuple[int, ...] = (1,),
    **overrides: object,
) -> EgressCurrentnessProof:
    """A digest-verified, genuinely admissible Egress Currentness Proof (§12).

    ``single_use_consumed`` / ``is_expired`` (mutable lifecycle) and ``egress_coordinates`` (the
    injected latch carrier) are NOT covered by the digest (§2.3), so they are set directly.
    """
    rev = revision if revision is not None else clean_revision()
    coords = coordinates if coordinates is not None else clean_coordinates()
    return EgressCurrentnessProof.issue(
        scheme=SCHEME,
        proof_id=proof_id,
        nonce=nonce,
        vector_id="vec-1",
        vector_digest="vd",
        committed_revision=rev,
        issue_revision=rev,
        send_started_revision=rev,
        bound_generations=bound_generations,
        restrictive_floors=restrictive_floors,
        capability_claim_command="cap-cmd-1",
        claim_committed_result="committed",
        result=result,
        single_use_consumed=single_use_consumed,
        is_expired=is_expired,
        egress_coordinates=coords,
        **overrides,
    )


def clean_fence(
    *,
    fence_id: str = "fence-1",
    owner_identity: str = "owner-x",
    affected_scope: frozenset[str] = frozenset({"scope-a"}),
    predecessor_floor: int | None = 3,
    advanced_floor: int | None = 7,
    terminal_denial: bool | None = False,
    **overrides: object,
) -> RestrictiveFenceRecord:
    """A digest-verified monotonic Restrictive Fence Record (advanced > predecessor)."""
    return RestrictiveFenceRecord.issue(
        scheme=SCHEME,
        fence_id=fence_id,
        owner_identity=owner_identity,
        affected_scope=affected_scope,
        predecessor_floor=predecessor_floor,
        advanced_floor=advanced_floor,
        terminal_denial=terminal_denial,
        **overrides,
    )
