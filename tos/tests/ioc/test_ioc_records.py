"""Digest-bound artifact invariants (design #14 §2/§3.1; IOC-EV-001..006 substrate).

id ⊥ digest => a same-id / different-bytes contradictory command / proof is a detectable
``CRITICAL_CONFLICT``; ISSUED is reachable under Phase-1 null bounds; every artifact is frozen
(append-only, no mutate); ``extra="forbid"`` rejects unknown / duplicate fields (§14 line 406);
the ``EconomicEffectEnvelope`` is the rcl ``CapacityVector`` type; ``required_authority_scope`` is
restrictive (never zero / wildcard); the authority effect is all-false.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.canonical import ArtifactIntegrityError, RecordPairKind, classify_record_pair
from tos.ioc import (
    ApprovedIntentContract,
    CanonicalBrokerCommand,
    EconomicEffectEnvelope,
    MaterialCommandChange,
    OrderConformanceProof,
    OrderConstructionAuthorityEffect,
)
from tos.rcl import CapacityVector

from ._ioc_strategies import (
    SCHEME,
    issue_command,
    issue_envelope,
    issue_intent,
    issue_policy,
    issue_proof,
)

# ---------------------------------------------------------------------------
# digest binding — issuance is reachable under Phase-1 null bounds
# ---------------------------------------------------------------------------


def test_all_five_artifacts_issue_under_null_bounds() -> None:
    """(§2.1) Every digest-bound artifact reaches ISSUED with only structural fields concrete."""
    for artifact in (
        issue_policy(),
        issue_envelope(),
        issue_intent(),
        issue_command(),
        issue_proof(),
    ):
        assert artifact.canonical_digest is not None
        assert artifact.status.value == "ISSUED"


def test_command_digest_substitution_is_unconstructable() -> None:
    """(§4.1) A tampered canonical_digest cannot be constructed (mutate / substitute sealed)."""
    good = issue_command()
    tampered = {**good.model_dump(), "canonical_digest": "deadbeef"}
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        CanonicalBrokerCommand(**tampered)


def test_issued_intent_requires_concrete_generation_and_version() -> None:
    """(§5.1 required-covered) An issued intent missing its generation is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        ApprovedIntentContract.issue(scheme=SCHEME, intent_id="i", intent_version="v")


# ---------------------------------------------------------------------------
# id ⊥ digest — same-id / different-bytes is CRITICAL_CONFLICT (forgery / re-issue)
# ---------------------------------------------------------------------------


def test_contradictory_same_id_command_is_critical_conflict() -> None:
    """(§3.1 / §5.4) Two same-id commands with different bytes => CRITICAL_CONFLICT (forgery seal)."""
    from tos.ioc import AxisBinding, ConformanceAxis

    a = issue_command(command_id="cmd-1")
    b = issue_command(
        command_id="cmd-1",
        axis_bindings=(AxisBinding(axis=ConformanceAxis.SIDE, value="SELL"),),
    )
    assert (
        classify_record_pair(
            a.command_id, a.canonical_digest, b.command_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_identical_reissue_is_idempotent_dup() -> None:
    """A byte-identical re-emission is an idempotent duplicate, not a conflict."""
    a = issue_proof()
    b = issue_proof()
    assert (
        classify_record_pair(
            a.proof_id, a.canonical_digest, b.proof_id, b.canonical_digest
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )


def test_distinct_generation_ids_are_distinct() -> None:
    """(§2.3) A legitimate new generation (fresh id) is DISTINCT — never mis-flagged as conflict."""
    a = issue_command(command_id="cmd-1")
    b = issue_command(command_id="cmd-2", command_generation=2)
    assert (
        classify_record_pair(
            a.command_id, a.canonical_digest, b.command_id, b.canonical_digest
        )
        is RecordPairKind.DISTINCT
    )


# ---------------------------------------------------------------------------
# EconomicEffectEnvelope is the rcl CapacityVector type (§0.4c / §5.5)
# ---------------------------------------------------------------------------


def test_economic_effect_envelope_is_rcl_capacity_vector() -> None:
    """(§0.4c type-seal) EconomicEffectEnvelope IS the rcl CapacityVector type — no self vector."""
    assert EconomicEffectEnvelope is CapacityVector


def test_ioc_defines_no_own_capacity_vector_type() -> None:
    """(§0.4c anti-regression) tos.ioc exposes no self-authored capacity / effect vector type."""
    import tos.ioc as ioc

    banned = ("EffectVector", "IocCapacityVector", "EconomicVector")
    for name in dir(ioc):
        for token in banned:
            assert (
                token not in name
            ), f"tos.ioc unexpectedly defines its own vector type: {name}"


# ---------------------------------------------------------------------------
# required-authority-scope restrictive (§14 line 374) — never zero / wildcard
# ---------------------------------------------------------------------------


def test_proof_required_authority_scope_defaults_empty_restrictive() -> None:
    """(§14 line 374 / §4.7) The default required-authority-scope is empty — never a wildcard."""
    proof = issue_proof()
    # An empty scope is the ∅ case a consumer treats as UNKNOWN / NON_CONFORMANT, never zero /
    # wildcard / unconstrained authority — it is a plain empty tuple, not a "*" grant.
    assert proof.required_authority_scope == ()
    assert "*" not in proof.required_authority_scope


def test_proof_carries_exact_bounded_scope_when_present() -> None:
    """(§14 line 374) A present required-authority-scope is an exact bounded tuple."""
    proof = issue_proof(required_authority_scope=("send:ACCT-1:INSTR-1",))
    assert proof.required_authority_scope == ("send:ACCT-1:INSTR-1",)


# ---------------------------------------------------------------------------
# all-false authority + MaterialCommandChange (§7 / §5.8)
# ---------------------------------------------------------------------------


def test_command_and_proof_authority_effect_is_all_false() -> None:
    """(§7 / IOC-INV-011) The command / proof carry an all-false authority effect."""
    for artifact in (issue_command(), issue_proof()):
        effect = artifact.authority_effect
        assert effect.transmits is False
        assert effect.issues_authority is False
        assert effect.mutates_capacity is False


def test_true_authority_flag_is_unconstructable() -> None:
    """(IOC-INV-011 line 197) Any True authority flag makes the effect unconstructable."""
    for field in (
        "approves",
        "mutates_capacity",
        "issues_authority",
        "classifies_protection",
        "chooses_admissibility",
        "transmits",
        "clears_halt",
        "rearms",
    ):
        with pytest.raises((ArtifactIntegrityError, ValidationError)):
            OrderConstructionAuthorityEffect(**{field: True})


def test_unknown_materiality_is_material() -> None:
    """(§5.8 line 145) 'Unknown materiality is material' — None / True => material; False => not."""
    assert MaterialCommandChange(is_material=None).resolved_material() is True
    assert MaterialCommandChange(is_material=True).resolved_material() is True
    assert MaterialCommandChange(is_material=False).resolved_material() is False


# ---------------------------------------------------------------------------
# frozen / append-only + extra=forbid (§14 line 406)
# ---------------------------------------------------------------------------


def test_command_is_frozen_no_mutate() -> None:
    """(§2.0 / §6.2) A command is frozen — post-proof mutation is construction-impossible."""
    command = issue_command()
    with pytest.raises(ValidationError):
        command.command_generation = 99  # type: ignore[misc]


def test_extra_field_is_forbidden() -> None:
    """(extra=forbid) An unknown top-level model field is rejected.

    NB: ``extra="forbid"`` covers only unknown *model fields*. A duplicate / surplus semantic
    *axis* inside ``axis_bindings`` is NOT caught here — it is the ``command_conforms`` structural
    guard's job (§5.1 / §14 line 406), regression-tested in ``test_ioc_conformance.py``.
    """
    with pytest.raises(ValidationError):
        OrderConformanceProof(proof_id="p", unknown_field=1)  # type: ignore[call-arg]
