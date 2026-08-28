"""MANDATED test-only seam: §6.2 sibling-token drift-lock + §0.5 anti-phantom negatives.

``tos.failuredomain`` holds **sibling edge 0** (design #27 §0.3/§3.1): it never imports a sibling
and never calls a sibling predicate. Instead, the design #27 §3.5 ownership table attributes each
ADR-002-009 clause to its real owner, and a matrix row *points at* that owner with an **injected
owner token** (a bare dotted string — design #27 §3.2/§5).

A bare string rots silently. This file is the **drift-lock** (design #27 §6.2, the #24 §3.4
precedent): it imports the **real** siblings as a **test** and resolves **every** token in
:data:`~tos.failuredomain.vocabulary.SIBLING_OWNER_TOKENS` against the live symbol — a function, a
class, an enum member, a model field, or a predicate parameter, whichever the §3.5 table cited. A
rename, a moved parameter, or a deleted field in any sibling breaks this file loudly. The
test-only import is **not** counted in the §6.1 runtime closure, which separately proves
``tos.failuredomain`` imports none of them.

**Missing-token count is enforced at 0**: the resolution table and the package's token set are
asserted equal in both directions, so a token cannot be added to one without the other.

It also carries the design #27 §0.5 **anti-phantom negatives** — the absence claims the v1.1
contract makes, locked as regression assertions rather than left as prose.

Regime tag: structural / injected-token seam substrate only; closes no FD-EV; EV-L1-complete claim
forbidden.
"""

from __future__ import annotations

import inspect
from enum import Enum
from types import ModuleType

import pytest
import tos.afg
import tos.are
import tos.authority
import tos.brokercap
import tos.canonical
import tos.capsule
import tos.cur
import tos.dsl
import tos.egress
import tos.evidence
import tos.failuredomain as fd
import tos.hag
import tos.iap
import tos.ioc
import tos.liveauth
import tos.nontrade
import tos.ordering
import tos.orthostate
import tos.posttrade
import tos.protective
import tos.rcl
import tos.recon
import tos.replacement
import tos.rlp
import tos.sbr
import tos.spg
import tos.time
import tos.venue
import tos.wdr
from tos.failuredomain import SIBLING_OWNER_TOKENS

#: Every token in :data:`SIBLING_OWNER_TOKENS`, mapped to the **kind** of symbol the design #27
#: §3.5 table cited it as. Hand-maintained alongside the vocabulary constant; the two are asserted
#: equal so neither can drift from the other.
_TOKEN_KINDS: dict[str, str] = {
    # egress (ADR-002-013) — §6.3 final egress, §10.1 item 2 credential/route disjointness
    "egress.credential_route_authority_disjoint": "callable",
    "egress.CredentialRouteInventoryEntry": "class",
    # rcl (ADR-002-002) — §6.2 serialization, §10.1 item 3 claim record, §13 aggregate
    "rcl.writer_fenced": "callable",
    "rcl.credible_union_capacity": "callable",
    "rcl.ClaimRecord": "class",
    "rcl.CapacityState": "class",
    # spg (ADR-002-014) — §10 / §11 deployment, config atomicity, rollback fencing (§3.5-2)
    "spg.activation_atomic": "callable",
    "spg.activation_serializable": "callable",
    "spg.envelope_incompatible": "callable",
    "spg.hard_and_runtime_versions_match": "callable",
    "spg.rollback_requires_new_generation": "callable",
    "spg.rollback_revives_nothing": "callable",
    "spg.compatibility_manifest_matches": "callable",
    # authority (ADR-002-003 / -007) — §6.1, §7 rule 6, §8.1, §8.4, §10 no-auto-rearm
    "authority.GenerationVector": "class",
    "authority.rearm_gate": "callable",
    "authority.partition_authority_verdict.control_plane_verifiable": "parameter",
    "authority.PartitionAuthorityVerdict.automatic_rearm_denied": "model_field",
    "authority.LeaseReassignmentInputs.hard_fence_proven": "model_field",
    # sbr (ADR-002-017) — §6.6 / §15 recovery isolation (the largest proposition trap, §3.5-1)
    "sbr.restricted_isolation_proven": "callable",
    "sbr.restore_worst_credible_union": "callable",
    "sbr.competing_owner_fenced": "callable",
    "sbr.recovery_generation_monotone": "callable",
    "sbr.IsolationFacts.all_proven": "method",
    # time (ADR-002-008) — §12 shared time common mode
    "time.independent_reference_count": "callable",
    "time.ReferenceSource.common_mode_group": "model_field",
    "time.source_disagreement_within_bound": "callable",
    "time.freshness_verdict": "callable",
    # cur (ADR-002-024) — §8.2 event infrastructure, §8.3 cache fail-closed
    "cur.CurrentnessAdmission": "class",
    "cur.ProofResult": "class",
    "cur.fence_advances_floor": "callable",
    # orthostate (ADR-002-005) — §14 retain-UNKNOWN, §10.1 item 3 send boundary
    "orthostate.KnowledgeState": "class",
    "orthostate.TransmissionAttemptState.SEND_STARTED": "enum_member",
    # brokercap — §9 broker session / limit / rate capability class, §6.5 environment binding
    "brokercap.CapabilityStatus": "class",
    "brokercap.ConformanceClass.CLASS_D_NON_LIVE": "enum_member",
    "brokercap.environment_binding_ok": "callable",
    # ioc (ADR-002-020) — §6.5 live/non-live axis, mutation fence
    "ioc.ConformanceAxis.LIVE_NONLIVE": "enum_member",
    "ioc.mutation_fence_holds": "callable",
    # afg (ADR-002-022) — action-flow stale-writer hard fence
    "afg.partition_lease_exclusive.stale_writer_hard_fenced": "parameter",
    # hag — §6.5 / §15 human-approval environment scope
    "hag.ApprovalScope.environments": "model_field",
    # venue — §6.4 / §7 gate authority != execution authority
    "venue.gate_authority_separated": "callable",
    # rlp (ADR-002-025) — trial-plan scope catalogue (token overlap, different proposition)
    "rlp.ScopeDimension.SAFETY_CELL": "enum_member",
    "rlp.ScopeDimension.FAILURE_DOMAIN": "enum_member",
}

#: Every landed sibling package, statically imported (the tos import-firewall forbids
#: ``importlib.import_module`` / ``__import__`` even in tests — TOS-FW-D). Used both by the
#: drift-lock resolver and by the tos-wide absence sweeps (§0.5).
_ALL_SIBLINGS: dict[str, ModuleType] = {
    "afg": tos.afg,
    "are": tos.are,
    "authority": tos.authority,
    "brokercap": tos.brokercap,
    "canonical": tos.canonical,
    "capsule": tos.capsule,
    "cur": tos.cur,
    "dsl": tos.dsl,
    "egress": tos.egress,
    "evidence": tos.evidence,
    "hag": tos.hag,
    "iap": tos.iap,
    "ioc": tos.ioc,
    "liveauth": tos.liveauth,
    "nontrade": tos.nontrade,
    "ordering": tos.ordering,
    "orthostate": tos.orthostate,
    "posttrade": tos.posttrade,
    "protective": tos.protective,
    "rcl": tos.rcl,
    "recon": tos.recon,
    "replacement": tos.replacement,
    "rlp": tos.rlp,
    "sbr": tos.sbr,
    "spg": tos.spg,
    "time": tos.time,
    "venue": tos.venue,
    "wdr": tos.wdr,
}


def _resolve(token: str) -> object:
    """Resolve the owning symbol a token names (``AttributeError`` if the sibling renamed it)."""
    package, symbol = token.split(".")[:2]
    return getattr(_ALL_SIBLINGS[package], symbol)


# --- the drift-lock ----------------------------------------------------------


def test_the_resolution_table_and_the_token_set_are_the_same_set() -> None:
    """(§6.2 missing-token count 0) The kind table and SIBLING_OWNER_TOKENS agree exactly."""
    assert set(_TOKEN_KINDS) == set(SIBLING_OWNER_TOKENS)
    assert len(_TOKEN_KINDS) == len(SIBLING_OWNER_TOKENS)


@pytest.mark.parametrize("token", sorted(_TOKEN_KINDS))
def test_every_owner_token_resolves_to_a_live_sibling_symbol(token: str) -> None:
    """(§6.2 drift-lock) Each §3.5-cited sibling symbol still exists, with the cited shape."""
    kind = _TOKEN_KINDS[token]
    parts = token.split(".")
    module = _ALL_SIBLINGS[parts[0]]
    assert hasattr(module, parts[1]), f"{token}: tos.{parts[0]}.{parts[1]} is gone"
    owner = getattr(module, parts[1])

    if kind == "callable":
        assert callable(owner), f"{token} is no longer callable"
        return
    if kind == "class":
        assert isinstance(owner, type), f"{token} is no longer a type"
        return

    leaf = parts[2]
    if kind == "enum_member":
        assert issubclass(owner, Enum), f"{token}: {parts[1]} is not an Enum"
        assert leaf in owner.__members__, f"{token}: member {leaf} is gone"
    elif kind == "model_field":
        assert leaf in owner.model_fields, f"{token}: field {leaf} is gone"
    elif kind == "parameter":
        assert (
            leaf in inspect.signature(owner).parameters
        ), f"{token}: parameter {leaf} is gone"
    elif kind == "method":
        assert callable(getattr(owner, leaf)), f"{token}: method {leaf} is gone"
    else:  # pragma: no cover - the table is closed
        raise AssertionError(f"unknown token kind {kind!r}")


def test_drift_lock_detects_a_renamed_symbol() -> None:
    """(both-ways) The resolver really fails on a symbol that does not exist."""
    with pytest.raises(AttributeError):
        _resolve("sbr.restricted_isolation_proven_v2")


def test_tokens_are_never_imported_by_the_package_itself() -> None:
    """(§3.2) The tokens are inert strings in the package — never resolved at runtime."""
    for token in SIBLING_OWNER_TOKENS:
        assert isinstance(token, str)
    # the package exposes the token set and nothing sibling-shaped derived from it.
    assert isinstance(fd.SIBLING_OWNER_TOKENS, frozenset)


# --- §0.5 anti-phantom negatives ---------------------------------------------


def test_egress_does_not_own_send_started() -> None:
    """(§0.5 negative token / C3) ``SEND_STARTED`` is orthostate's, NOT egress's.

    The design #27 v1.0 claim that egress "exactly owns" ADR §10.1 was a phantom: item 3's
    ``SEND_STARTED`` boundary lives in ``tos.orthostate`` (with rcl's claim record), and a grep of
    ``tos.egress`` for ``SEND_STARTED`` is empty. This locks that negative so the re-attribution
    cannot silently regress.
    """
    assert not hasattr(tos.egress, "SEND_STARTED")
    assert "SEND_STARTED" not in dir(tos.egress)
    assert "SEND_STARTED" in tos.orthostate.TransmissionAttemptState.__members__


@pytest.mark.parametrize("package", _ALL_SIBLINGS)
def test_no_sibling_owns_isolation_kind(package: str) -> None:
    """(§0.5 negative token / M2) ``IsolationKind`` is a genuine failuredomain original.

    The tos-wide ``git grep -l IsolationKind tos/src/tos`` was empty before this package landed;
    this sweep keeps it that way, so the M2 authorship claim stays measured rather than asserted.
    """
    module = _ALL_SIBLINGS[package]
    assert not hasattr(module, "IsolationKind"), (
        f"tos.{package} now owns IsolationKind — the design #27 §2.1E authorship claim "
        "(negative-grep confirmed) has regressed"
    )
    assert fd.IsolationKind.__module__.startswith("tos.failuredomain")


@pytest.mark.parametrize(
    "name",
    [
        "FailureDomainKind",
        "FailureBehaviorKind",
        "IsolationClaimStatus",
        "SafetyCellScope",
        "FailureDomainAllocationEntry",
        "IsolationClaim",
        "ExplicitlyAnalyzedEmpty",
    ],
)
def test_no_sibling_owns_a_failuredomain_original(name: str) -> None:
    """(§0.5) Every symbol this package authors was measured absent tos-wide beforehand."""
    for package, module in _ALL_SIBLINGS.items():
        assert not hasattr(module, name), f"tos.{package} also exposes {name}"
    assert hasattr(fd, name)


def test_rcl_has_no_capability_claim_symbol() -> None:
    """(§0.5 / contract-code deviation) rcl owns ``ClaimRecord``, not ``CapabilityClaim``.

    The design #27 §3.5 / §6.2 text cites the §10.1 item-3 rcl half as ``CapabilityClaim`` at
    ``rcl/state.py:133``. Measured: line **132** is ``class ClaimRecord``; line **133** is its
    docstring, "A recorded capability claim" — the contract **name-ified the prose**, turning a
    description into a symbol that never existed (``git grep -l CapabilityClaim tos/src/tos`` is
    empty). The drift-lock therefore locks the real ``ClaimRecord``, and this negative pins the
    erratum (design doc v1.2 ①) so a future reader does not go looking for the phantom.
    """
    assert not hasattr(tos.rcl, "CapabilityClaim")
    assert hasattr(tos.rcl, "ClaimRecord")
    assert "rcl.ClaimRecord" in SIBLING_OWNER_TOKENS
    assert "rcl.CapabilityClaim" not in SIBLING_OWNER_TOKENS


# --- proposition-identity seams (design #27 §3.3 / §3.5) ---------------------


def test_fd_isolation_claim_is_not_sbr_isolation_facts() -> None:
    """(§3.5-1, the largest trap) general 5-field claim != recovery-readiness 8-axis proof.

    sbr ``IsolationFacts`` (ADR-002-017 §17 line 438-445) is an eight-axis **positive proof** of
    *recovery* isolation; the failuredomain ``IsolationClaim`` is the general cross-domain ADR
    §4.4 **claim structure**. Different grain, different scope, no shared type, no import — the
    relation is a **reference token** in ``verification_cases`` (Q2, design #27 §9.4-1).
    """
    from tos.sbr import IsolationFacts

    assert len(IsolationFacts.model_fields) == 8
    assert len(fd.IsolationClaim.model_fields) == 6  # the §4.4 five + the §2.2 block
    assert (
        len(set(IsolationFacts.model_fields) & set(fd.IsolationClaim.model_fields)) == 0
    )
    assert fd.IsolationClaim is not IsolationFacts
    assert not issubclass(fd.IsolationClaim, IsolationFacts)
    # the reference is a bare token, never a type.
    assert "sbr.IsolationFacts.all_proven" in SIBLING_OWNER_TOKENS


def test_fd_taxonomy_is_not_the_rlp_scope_catalogue() -> None:
    """(§3.5 / M6) rlp ``ScopeDimension`` enumerates trial-scope axes; FD enumerates domains.

    The two catalogues overlap on tokens in **both** directions — rlp holds ``SAFETY_CELL`` and
    ``FAILURE_DOMAIN`` (which FD does not), and both hold ``ACCOUNT`` and ``CREDENTIAL`` — which
    is exactly why the §3.3 proposition-identity trap needed sealing. Because both are plain
    ``StrEnum``s, a shared token even compares **equal** across the two types; separation
    therefore rests on **distinct types + non-import + ``is`` identity**, never on global string
    distinctness (the recon ``FieldConfidenceClass`` precedent).
    """
    from tos.rlp import ScopeDimension

    # rlp owns the cell / failure-domain *scope dimensions*; FD does not enumerate them.
    assert "SAFETY_CELL" in ScopeDimension.__members__
    assert "FAILURE_DOMAIN" in ScopeDimension.__members__
    assert "SAFETY_CELL" not in fd.FailureDomainKind.__members__
    assert "FAILURE_DOMAIN" not in fd.FailureDomainKind.__members__

    shared = {member.value for member in ScopeDimension} & {
        member.value for member in fd.FailureDomainKind
    }
    assert shared == {"ACCOUNT", "CREDENTIAL"}
    for token in sorted(shared):
        rlp_member = ScopeDimension[token]
        fd_member = fd.FailureDomainKind[token]
        assert (
            rlp_member == fd_member
        )  # both are plain StrEnums — string equality crosses
        assert rlp_member is not fd_member  # identity does not
        assert type(rlp_member) is not type(fd_member)
    assert fd.FailureDomainKind.__module__.startswith("tos.failuredomain")
    assert ScopeDimension.__module__.startswith("tos.rlp")


def test_a_real_foreign_axis_member_cannot_cross_the_volatile_predicate() -> None:
    """(MAJOR-2 / §3.3) rlp ``ScopeDimension.ACCOUNT`` is refused by the guard, not answered.

    This is the seam in its most concrete form: a **real** sibling's member that shares the token
    ``ACCOUNT`` with this taxonomy compares and hashes equal to
    ``FailureDomainKind.ACCOUNT``, so an unguarded set operation would have accepted it and
    returned a plausible verdict computed across two different propositions.
    """
    from tos.rlp import ScopeDimension as RlpScopeDimension

    assert RlpScopeDimension.ACCOUNT == fd.FailureDomainKind.ACCOUNT
    assert hash(RlpScopeDimension.ACCOUNT) == hash(fd.FailureDomainKind.ACCOUNT)
    with pytest.raises(TypeError):
        fd.decision_sole_sourced_from_volatile(
            frozenset({RlpScopeDimension.ACCOUNT}),  # type: ignore[arg-type]
            frozenset({fd.FailureDomainKind.ACCOUNT}),
        )


def test_fd_common_mode_is_not_the_time_common_mode_group() -> None:
    """(§3.5 §12) time's ``common_mode_group`` is a time-source axis, not the FD classification."""
    from tos.time import ReferenceSource

    assert "common_mode_group" in ReferenceSource.model_fields
    assert ReferenceSource.model_fields["common_mode_group"].annotation == (str | None)
    # FD's COMMON_MODE is a closed enum member on two distinct axes, not a free-form group id.
    assert fd.IsolationKind.COMMON_MODE.value == "COMMON_MODE"
    assert "common_mode_group" not in dir(fd)


def test_the_six_sibling_hard_fence_owners_are_all_distinct() -> None:
    """(§3.5-3) "hard fence" is six different sibling propositions — FD re-authors none of them.

    ADR §4.5 line 100-102 defines what a hard fence is **not** ("Process convention, leader
    belief, a dashboard flag, or cooperative shutdown is not a hard fence"); the mechanisms are
    owned separately by authority (stale authority), rcl (RCL writer), afg (action-flow writer),
    sbr (recovery competing owner), cur (currentness floor) and ioc (mutation).
    """
    import tos.afg as afg
    import tos.authority as authority
    import tos.cur as cur
    import tos.ioc as ioc
    import tos.rcl as rcl
    import tos.sbr as sbr

    owners = {
        "authority": authority.LeaseReassignmentInputs.model_fields[
            "hard_fence_proven"
        ],
        "rcl": rcl.writer_fenced,
        "afg": inspect.signature(afg.partition_lease_exclusive).parameters[
            "stale_writer_hard_fenced"
        ],
        "sbr": sbr.competing_owner_fenced,
        "cur": cur.fence_advances_floor,
        "ioc": ioc.mutation_fence_holds,
    }
    assert len(owners) == 6
    assert len({id(owner) for owner in owners.values()}) == 6
    # failuredomain authors no fence of its own.
    for forbidden in ("hard_fence", "hard_fence_proven", "fence", "fenced"):
        assert not hasattr(fd, forbidden)
