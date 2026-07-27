"""§0.5 anti-phantom locks — every absence claim the contract makes, asserted (design #27 §0.5).

The design #27 v1.0 independent review was rejected for a single defect class, newly named
**anti-phantom**: *existence was grepped, absence was not*. Three claims ("FD has no dedicated VP
key", "egress exactly owns §10.1", "at most three predicates") were unverified absences, and two of
them were false. v1.1's rule is that **an absence claim must be grepped too**.

This file is the executable form of that rule (the nontrade / posttrade
``deliberately_not_claimed`` precedent): each thing design #27 says ``tos.failuredomain`` does
**not** author is asserted absent, so the boundary cannot quietly grow. A package that later
authors a fence, a blast-radius number, a fourth predicate, a VP key, or an environment enum fails
here rather than in a review six cycles later.

**The locks are on authorship, not on the export surface** (adversarial review MAJOR-1). Design
#27 §0.2 forbids *authoring* a fence / a blast-radius predicate / a VP key, and a symbol defined in
a submodule but left out of ``__all__`` is authored just the same — a ``hasattr(fd, ...)`` check
would have waved it through. Every absence assertion therefore runs against the union of

  * ``vars()`` of the package **and of all five submodules** (module-level bindings), and
  * an **AST sweep of every source file** for any ``class`` / ``def`` / assignment target
    (catching names nested inside a class body or a function, which ``vars()`` cannot see).

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import ModuleType

import pytest
import tos.failuredomain as fd
import tos.failuredomain._base
import tos.failuredomain.predicates
import tos.failuredomain.records
import tos.failuredomain.state
import tos.failuredomain.vocabulary
from tos.canonical import DigestBoundArtifact, IdDerivedArtifact, IndependentIdArtifact

_FD_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "failuredomain"
)

#: The five submodules, statically bound (the tos firewall forbids ``__import__``, TOS-FW-D).
_SUBMODULES: dict[str, ModuleType] = {
    "_base": tos.failuredomain._base,
    "predicates": tos.failuredomain.predicates,
    "records": tos.failuredomain.records,
    "state": tos.failuredomain.state,
    "vocabulary": tos.failuredomain.vocabulary,
}


def _public_names() -> set[str]:
    """Every public attribute of the package (the export surface only)."""
    return {name for name in dir(fd) if not name.startswith("_")}


def _assignment_targets(node: ast.AST) -> list[str]:
    """The identifier names a statement binds, if any."""
    names: list[str] = []
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(
                element.id for element in target.elts if isinstance(element, ast.Name)
            )
    return names


def _source_authored_names() -> set[str]:
    """Every identifier any ``tos.failuredomain`` source *defines* — at any nesting depth.

    Classes, functions, enum members, module constants and function-local bindings all count:
    design #27 §0.2 forbids **authoring** these concepts, and burying one inside a class body or
    a helper function is still authoring it.
    """
    names: set[str] = set()
    sources = sorted(_FD_SRC.rglob("*.py"))
    assert sources, f"no tos.failuredomain source found under {_FD_SRC}"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            else:
                names.update(_assignment_targets(node))
    return names


def _authored_names() -> set[str]:
    """Everything this package authors or binds — the target of every absence lock."""
    names = set(vars(fd))
    for module in _SUBMODULES.values():
        names |= set(vars(module))
    return names | _source_authored_names()


# --- §0.2: no hard-fence authorship (the mechanism is six siblings' + runtime) ---


@pytest.mark.parametrize(
    "forbidden",
    [
        "HardFence",
        "HardFenceKind",
        "hard_fence",
        "hard_fence_proven",
        "hard_fence_holds",
        "fence_advances_floor",
        "writer_fenced",
        "competing_owner_fenced",
        "mutation_fence_holds",
        "stale_writer_hard_fenced",
    ],
)
def test_no_hard_fence_vocabulary_is_authored(forbidden: str) -> None:
    """(§0.2 / §3.5-3) ADR §4.5 defines what a fence is NOT; the mechanisms are sibling-owned.

    ADR-002-009 §4.5 line 100-102: "Process convention, leader belief, a dashboard flag, or
    cooperative shutdown is not a hard fence." Six siblings own six different fence propositions
    and the fence itself is runtime + broker; ``tos.failuredomain`` authors none of them.

    The lock is on **authorship**, not export: a fence defined in a submodule and left out of
    ``__all__`` would still be authored (adversarial review MAJOR-1).
    """
    assert forbidden not in _authored_names()


def test_no_symbol_contains_a_fence_concept() -> None:
    """(§0.2) A sweep, not just a name list — nothing fence-shaped is *authored* anywhere."""
    offenders = sorted(name for name in _authored_names() if "fence" in name.lower())
    assert offenders == [], f"failuredomain authored fence vocabulary: {offenders}"


# --- §4.6 / §13: no blast-radius authorship (numeric predicate deferred to rcl) ---


@pytest.mark.parametrize(
    "forbidden",
    [
        "BlastRadius",
        "blast_radius",
        "blast_radius_within_bound",
        "cell_partitioning_within_aggregate",
        "aggregate_limit_not_exceeded",
        "credible_union_capacity",
    ],
)
def test_no_blast_radius_vocabulary_is_authored(forbidden: str) -> None:
    """(C2 / §3.5 §13) The §13 numeric non-expansion predicate is deferred to rcl, not authored.

    ADR §13 line 322: "Aggregate capacity remains serialized by the Risk Capacity Ledger." The
    v1.0 fourth predicate was withdrawn for exactly this reason (design #27 C2), leaving the
    ``SafetyCellScope`` coordinate as the only §13 authorship.
    """
    assert forbidden not in _authored_names()


def test_no_symbol_contains_a_blast_radius_concept() -> None:
    """(C2) Sweep: nothing blast-radius-shaped is *authored*, only the cell coordinate."""
    authored = _authored_names()
    offenders = sorted(
        name for name in authored if "blast" in name.lower() or "radius" in name.lower()
    )
    assert offenders == []
    assert "SafetyCellScope" in authored  # the coordinate IS authored (§13 substrate)
    assert hasattr(fd, "SafetyCellScope")


# --- §7: no VP-002 key is authored (the two real ones stay null, Phase-0) ------


def test_no_verification_profile_key_is_authored() -> None:
    """(§7 / C1) FD authors **zero** new VP-002 keys and re-declares neither existing one.

    ``B_failure_domain_detect`` (VERIFICATION-PROFILE-002 line 611) and
    ``B_failure_domain_contain`` (line 618) both exist already and both hold ``null``; their
    value approval is a Phase-0 Bounds-Approver gate (design #27 §7/§8.2-2). The two *unkeyed*
    candidates — a blast-radius ceiling and a cell-HALT-to-global-HALT escalation condition —
    are flagged as new-key candidates, not authored here.
    """
    authored = _authored_names()
    offenders = sorted(name for name in authored if name.startswith("B_"))
    assert offenders == []
    for key in (
        "B_failure_domain_detect",
        "B_failure_domain_contain",
        "B_rate_limit_recovery",
        "B_authority_partition_detect",
    ):
        assert key not in authored


def test_no_source_mentions_a_bound_value_assignment() -> None:
    """(§0.2) No source assigns a bound — ``detection_and_containment`` is an injected slot."""
    for path in sorted(_FD_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("value_ms", "MAX_", "_MS =", "THRESHOLD"):
            assert forbidden not in text, f"{path.name} carries {forbidden!r}"


# --- deferred authorship (§9.3-4, §8.2-6, §0.4e-c) ---------------------------


@pytest.mark.parametrize(
    "forbidden",
    [
        "partition_new_risk_blocked",
        "partition_severity",
        "partition_high_severity",
        "broker_reachable_but_currentness_lost",
    ],
)
def test_the_section_84_partition_three_boolean_is_not_authored(forbidden: str) -> None:
    """(§9.3-4) The ADR §8.4 line 228 three-boolean is a deliberate deferral, not an omission.

    It is genuinely sibling-unowned (negative-grep), which makes it a *candidate* fourth
    predicate — and design #27 §9.3-4 declines it to keep the surface at exactly three. This
    lock makes the decision visible instead of implicit.
    """
    assert forbidden not in _authored_names()


@pytest.mark.parametrize(
    "forbidden",
    ["EnvironmentClass", "EnvironmentKind", "LiveNonLive", "environment_binding_ok"],
)
def test_no_environment_class_enum_is_authored(forbidden: str) -> None:
    """(M7 / §8.2-6) live-non-live is ioc's + brokercap's axis; only the closed value enum is
    unowned, and that is a Phase-0 INSTANCE deferral (the ioc §28 q3 precedent), not FD's.
    """
    assert forbidden not in _authored_names()
    assert (
        "environment" in fd.SafetyCellScope.model_fields
    )  # only the coordinate is FD's


@pytest.mark.parametrize(
    "forbidden",
    [
        "SafetyCellDeclaration",
        "cell_halt_escalation_required",
        "escalate_cell_halt_to_global",
        "CellHaltEscalation",
        "IdentityInventory",
    ],
)
def test_no_phase_zero_ownerless_item_is_quietly_authored(forbidden: str) -> None:
    """(§0.4e-c / §8.2-3/4) The §13 cell 6-field, the §14 escalation and the §9 identity
    inventory are Phase-0 human-gate items — recording them as sibling-owned would be the one
    structural fail-open this design admits, so they are neither claimed nor authored.
    """
    assert forbidden not in _authored_names()


# --- Q1: no digest-bound artifact, no ordering edge --------------------------


@pytest.mark.parametrize(
    "model",
    ["FailureDomainAllocationEntry", "IsolationClaim", "SafetyCellScope"],
)
def test_records_are_plain_frozen_not_digest_bound(model: str) -> None:
    """(Q1 / §3.1) No record is a DigestBound / IndependentId / IdDerived artifact."""
    klass = getattr(fd, model)
    for artifact in (DigestBoundArtifact, IndependentIdArtifact, IdDerivedArtifact):
        assert not issubclass(klass, artifact), f"{model} adopted {artifact.__name__}"
    for digest_field in ("digest", "record_digest", "artifact_digest", "id"):
        assert digest_field not in klass.model_fields


@pytest.mark.parametrize(
    "forbidden", ["Ordering", "OrderingEvent", "compare_order", "sequence_number"]
)
def test_no_ordering_surface_is_exposed(forbidden: str) -> None:
    """(§0.3) A matrix row carries no causal append-only order — the ordering edge is not taken."""
    assert forbidden not in _authored_names()


# --- §3.5: no sibling-owned symbol is re-authored ----------------------------

#: The sibling-owned predicates / types the design #27 §3.5 table attributes elsewhere. The §6.1
#: closure test proves they are not *imported*; this list proves they are not **re-authored**
#: either — the two are different failures and only the second survives an ``__all__`` omission.
_SIBLING_OWNED_NEVER_REAUTHORED: tuple[str, ...] = (
    "IsolationFacts",  # sbr — the recovery-readiness eight-axis proof (§3.5-1)
    "restricted_isolation_proven",  # sbr
    "restore_worst_credible_union",  # sbr
    "competing_owner_fenced",  # sbr
    "recovery_generation_monotone",  # sbr
    "GenerationVector",  # authority
    "control_plane_verifiable",  # authority
    "rearm_gate",  # authority
    "PartitionAuthorityVerdict",  # authority
    "writer_fenced",  # rcl
    "CapacityState",  # rcl
    "ClaimRecord",  # rcl
    "activation_atomic",  # spg (§3.5-2)
    "rollback_requires_new_generation",  # spg
    "rollback_revives_nothing",  # spg
    "compatibility_manifest_matches",  # spg
    "credential_route_authority_disjoint",  # egress
    "CredentialRouteInventoryEntry",  # egress
    "common_mode_group",  # time (§12)
    "independent_reference_count",  # time
    "ProofResult",  # cur (§8.3)
    "CurrentnessAdmission",  # cur
    "KnowledgeState",  # orthostate
    "TransmissionAttemptState",  # orthostate
    "CapabilityStatus",  # brokercap
    "ConformanceClass",  # brokercap
    "ConformanceAxis",  # ioc
    "ScopeDimension",  # rlp
    "ApprovalScope",  # hag
    "gate_authority_separated",  # venue
)


@pytest.mark.parametrize("name", _SIBLING_OWNED_NEVER_REAUTHORED)
def test_no_sibling_owned_symbol_is_reauthored(name: str) -> None:
    """(§3.5 / MAJOR-1) Re-authoring a sibling's symbol is as forbidden as importing it.

    Design #27 §3.5 says these are owned elsewhere and **재저작 금지**; a local copy under the
    same name would be a silent fork of a safety proposition — worse than an import, because the
    import-closure test would never see it. Authorship, not export, is what is locked.
    """
    assert name not in _authored_names()


def test_the_authorship_sweep_is_strictly_wider_than_the_export_surface() -> None:
    """(MAJOR-1 rationale) ``_authored_names()`` ⊋ ``dir(fd)`` — the locks target the wider set.

    If the two were equal, every absence lock above would collapse back into an export-surface
    check and a submodule-local definition would slip through. The private helpers are the
    witness that they are genuinely different sets.
    """
    authored = _authored_names()
    exported = _public_names()
    assert exported <= authored
    assert authored - exported != set()
    for private in (
        "_isolation_claim_status",
        "_tokens_positively_listed",
        "_reject_foreign_domain_members",
    ):
        assert private in authored
        assert private not in exported


# --- the surface itself: exactly three predicates ----------------------------


def test_exactly_three_public_predicates_are_authored() -> None:
    """(§3.4 / §4) The public predicate surface is exactly three — no fourth, ever."""
    import tos.failuredomain.predicates as predicates

    public_callables = sorted(
        name
        for name, value in vars(predicates).items()
        if not name.startswith("_")
        and inspect.isfunction(value)
        and value.__module__ == predicates.__name__
    )
    assert public_callables == [
        "decision_sole_sourced_from_volatile",
        "new_risk_blocked_by_unproven_isolation",
        "unproven_isolation_is_common_mode",
    ]
    assert predicates.__all__ == public_callables


def test_the_status_classifier_stays_private() -> None:
    """(§4.1) ``_isolation_claim_status`` is an internal helper, not a fourth public predicate."""
    import tos.failuredomain.predicates as predicates

    assert hasattr(predicates, "_isolation_claim_status")
    assert "_isolation_claim_status" not in predicates.__all__
    assert not hasattr(fd, "_isolation_claim_status")
    assert "isolation_claim_status" not in dir(fd)


# --- no EV closure is claimed ------------------------------------------------


def test_no_fd_ev_closure_symbol_exists() -> None:
    """(§1 zero-closure) Nothing here registers, asserts, or closes an FD-EV / FD-AC item."""
    offenders = sorted(
        name
        for name in _authored_names()
        if name.upper().startswith(("FD_EV", "FD_AC", "EV_L"))
    )
    assert offenders == []


def test_the_package_docstring_carries_the_zero_closure_discipline() -> None:
    """(§0.2 / §6) The regime tag is present and says the right thing, verbatim-ish."""
    doc = fd.__doc__ or ""
    assert "closes **no** FD-EV item" in doc
    assert "EV-L1-complete claim forbidden" in doc
    assert "sibling edge 0" in doc
    assert "NOT_IMPLEMENTED" in doc


@pytest.mark.parametrize("module_name", sorted(_SUBMODULES))
def test_every_module_declares_its_purity_and_regime(module_name: str) -> None:
    """(§0.3) Each module states its firewall position — no module is silently unconstrained."""
    doc = _SUBMODULES[module_name].__doc__ or ""
    assert "design #27" in doc
    assert "no ``shared" in doc
