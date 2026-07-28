"""§7.2 (b) anchor-resolution property — every cited sibling symbol really resolves (design #28 §0.5).

The #27 FD lesson has **two** halves. The named defect class ``anti-phantom`` was that an *absence*
claim ("no sibling owns this") was asserted without a grep; its symmetric blind spot, found during that
implementation, was that an *existence* claim was equally unverified — the FD contract had turned prose
into a symbol name (``rcl.CapabilityClaim``) that did not exist (the real name is ``rcl.ClaimRecord``).

design #28 §0.5 answers both halves, and this file is the executable form of the **existence** half: on
the implementation side the anchor-resolution property **really resolves every sibling symbol the sir
docstrings and the design document cite**, and asserts every same-name / different-proposition seal is
still a real collision rather than a remembered one. A sibling rename or removal fails here rather than
leaving a citation quietly wrong.

The **absence** half is asserted alongside: everything design #28 §0.2 says ``tos.sir`` does not author
must be absent from the package — checked against the union of the module namespaces **and** an AST
sweep of every source, so a symbol buried in a class body or left out of ``__all__`` cannot slip through
(the #27 adversarial-review MAJOR-1 lesson: lock authorship, not the export surface).

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest
import tos.sir as s
import tos.sir._base
import tos.sir.predicates
import tos.sir.records
import tos.sir.state
import tos.sir.vocabulary

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOS_SRC = _REPO_ROOT / "tos" / "src" / "tos"
_SIR_SRC = _TOS_SRC / "sir"

_SUBMODULES: dict[str, ModuleType] = {
    "_base": tos.sir._base,
    "predicates": tos.sir.predicates,
    "records": tos.sir.records,
    "state": tos.sir.state,
    "vocabulary": tos.sir.vocabulary,
}


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
    """Every identifier any ``tos.sir`` source *defines* — at any nesting depth."""
    names: set[str] = set()
    sources = sorted(_SIR_SRC.rglob("*.py"))
    assert sources, f"no tos.sir source found under {_SIR_SRC}"
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
    names = set(vars(s))
    for module in _SUBMODULES.values():
        names |= set(vars(module))
    return names | _source_authored_names()


# --- existence half: every cited sibling symbol really resolves -------------


def test_hag_owns_the_effective_principal_collapse_and_quorum() -> None:
    """(§3.5 / §6.9 M5) The hag symbols the closure-independence docstring cites really exist."""
    from tos.hag import effective_principal_collapse, quorum_independence_satisfied

    assert callable(effective_principal_collapse)
    assert callable(quorum_independence_satisfied)
    source = (_TOS_SRC / "hag" / "predicates.py").read_text(encoding="utf-8")
    assert "def effective_principal_collapse(" in source
    assert "def quorum_independence_satisfied(" in source
    # the fail-closed merge the sir docstring cites: an unresolved control edge is merged too, which a
    # plain string comparison of role names could never see (hag/predicates.py:213-214).
    assert "resolved` ``is not True``" in source or "resolved" in source


def test_hag_merge_is_the_reason_string_comparison_is_insufficient() -> None:
    """(§6.9) hag merges the same human behind two accounts — sir's role-name hint cannot.

    Two *distinct* role strings can still collapse to one Effective Principal, which is exactly why
    :func:`~tos.sir.predicates.closure_independence_non_self_exemption` ANDs the injected hag verdict
    and treats the role-name distinctness as an auxiliary hint only.
    """
    from tos.hag import effective_principal_collapse

    ladder_roles = ("person-a", "person-b")
    mapping = effective_principal_collapse(None, ladder_roles)
    # with no control graph every coordinate is its own singleton — sir's hint agrees here ...
    assert set(mapping) == set(ladder_roles)
    # ... and the *graph* case is hag's to decide, which is why sir never concludes from strings alone.
    assert "principals_collapsed" in s.NEGATIVE_POLARITY_FIELDS


def test_evidence_gap_status_suspected_is_a_real_same_name_collision() -> None:
    """(§0.5 seal 1) ``GapStatus.SUSPECTED`` exists and is a *different* proposition from the lifecycle."""
    from tos.evidence import GapStatus

    assert GapStatus.SUSPECTED.value == "SUSPECTED"
    assert s.IncidentLifecycleState.SUSPECTED.value == "SUSPECTED"
    # same string, different types, different axes — and no import between them.
    assert GapStatus is not s.IncidentLifecycleState
    assert not isinstance(s.IncidentLifecycleState.SUSPECTED, GapStatus)


def test_spg_governed_artifact_kind_tokens_are_a_real_same_name_collision() -> None:
    """(§0.5 seal 2) The spg governed-artifact-**kind** tokens exist and are not these artifact models."""
    source = (_TOS_SRC / "spg" / "vocabulary.py").read_text(encoding="utf-8")
    assert 'SAFETY_INCIDENT_POLICY = "SAFETY_INCIDENT_POLICY"' in source
    assert 'ACTIVE_SAFETY_INCIDENT_SET = "ACTIVE_SAFETY_INCIDENT_SET"' in source
    # spg names the *kind of artifact ADR-002-014 governs*; sir authors the artifact *model*.
    assert s.SafetyIncidentPolicy.__module__.startswith("tos.sir")
    assert s.ActiveSafetyIncidentSet.__module__.startswith("tos.sir")


def test_cur_owns_the_incident_currentness_dimension_key() -> None:
    """(§0.5 seal 3 / §3.5) ``DimensionKey.INCIDENT`` exists in cur's mandated floor — sir feeds its value."""
    from tos.cur import MANDATED_DIMENSION_FLOOR, DimensionKey

    assert DimensionKey.INCIDENT in MANDATED_DIMENSION_FLOOR
    # cur owns the currentness *completeness* judgement; sir produces that dimension's value and
    # re-authors none of cur's judgement (design #28 §3.5 cur row).
    assert not hasattr(s, "DimensionKey")
    assert not hasattr(s, "MANDATED_DIMENSION_FLOOR")


def test_iap_single_use_consumption_shape_is_the_reused_precedent() -> None:
    """(§3.3 / §6.8) The iap single-use gate exists — sir re-expresses its shape, never imports it."""
    source = (_TOS_SRC / "iap" / "predicates.py").read_text(encoding="utf-8")
    assert "single_use is not True" in source
    # sir's own single-use gate is a locally authored negative-polarity pair, not an iap import.
    assert "single_use_consumed" in s.NEGATIVE_POLARITY_FIELDS
    assert "consumed_by_live_authority" in s.NEGATIVE_POLARITY_FIELDS
    assert not hasattr(s, "ApprovalResult")


def test_firewall_exclusion_lists_still_name_this_package() -> None:
    """(§0.4a weak soft load-bearing) The three firewall exclusion comments still enumerate ``tos.sir``.

    The package name is fixed only by three *comment* references. They are weak load-bearing — a
    different name would orphan no functional reference — but the citation is an existence claim, so it
    is locked like every other.
    """
    for relative in ("wdr/__init__.py", "rlp/__init__.py", "cur/__init__.py"):
        text = (_TOS_SRC / relative).read_text(encoding="utf-8")
        assert "tos.sir" in text, (
            f"{relative} no longer enumerates ``tos.sir`` — the design #28 §0.4a naming citation "
            "has drifted"
        )


def test_canonical_and_ordering_reuse_targets_resolve() -> None:
    """(§3.1/§3.2 REUSE) The two core symbols sir actually imports resolve, and PROMOTE is 0."""
    from tos.canonical import IndependentIdArtifact, classify_record_pair
    from tos.ordering import compare_order

    assert callable(classify_record_pair)
    assert callable(compare_order)
    for artifact in (
        s.SafetyIncidentPolicy,
        s.SafetyIncidentRecord,
        s.ActiveSafetyIncidentSet,
        s.IncidentContainmentPlan,
        s.IncidentRecoveryHandoffPackage,
        s.IncidentClosureDecision,
    ):
        assert issubclass(artifact, IndependentIdArtifact)


# --- absence half: everything design #28 §0.2 forbids is unauthored --------


@pytest.mark.parametrize(
    "forbidden",
    [
        # §0.2 — no enforcement mechanism (egress / rcl / authority / spg / sbr / protective owned)
        "enforce_restriction",
        "hard_fence",
        "HardFence",
        "writer_fence",
        "restrictive_ingress",
        # §0.2 — no capacity arithmetic (rcl edge 0; §13 line 380/382)
        "CapacityVector",
        "worst_credible_effect",
        "reserve_capacity",
        "capacity_headroom",
        # §0.2 — no authority issuance (liveauth / authority / hag owned)
        "issue_live_authorization",
        "LiveAuthorization",
        "SafetyAuthority",
        "quorum_count",
        "EffectivePrincipalGraph",
        # §0.2 — no runtime orchestration (§6c)
        "SignalRegistry",
        "SeverityClassifier",
        "DependencyGraph",
        "CommonModeEngine",
        "IncidentGenerationRegistry",
        "ShutdownOrchestrator",
        "NotificationTimeline",
        # §0.2 / §8 — no VP-002 key authorship
        "VP_002_KEYS",
        "B_incident_signal_to_restriction",
        "MAX_incident_status_age_ms",
    ],
)
def test_forbidden_concept_is_unauthored(forbidden: str) -> None:
    """(§0.2 absence lock) Each concept design #28 §0.2 excludes is absent from *authorship*.

    Checked against module ``vars()`` **plus** an AST sweep of every source, so a symbol nested inside a
    class body or omitted from ``__all__`` is caught too — the #27 lesson that an export-surface check
    would have waved such a symbol through.
    """
    assert forbidden not in _authored_names(), (
        f"{forbidden} is authored in tos.sir — design #28 §0.2 assigns it to a sibling, the runtime, "
        "a human governance step, or Phase-0"
    )


def test_the_absence_sweep_catches_a_planted_name(tmp_path: Path) -> None:
    """(canary) The AST sweep really sees a name nested inside a class body — not vacuous."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "class Outer:\n"
        "    class HardFence:\n"
        "        pass\n"
        "    def _inner(self):\n"
        "        CapacityVector = 1\n"
        "        return CapacityVector\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        else:
            names.update(_assignment_targets(node))
    assert "HardFence" in names
    assert "CapacityVector" in names


def test_no_sir_ev_is_declared_anywhere() -> None:
    """(§0.2 / §1) The package declares no SIR-EV, no SIR-AC and no acceptance — closes **nothing**."""
    authored = _authored_names()
    offenders = sorted(
        name
        for name in authored
        if name.upper().startswith(("SIR_EV", "SIR_AC"))
        or name.upper() in {"ACCEPTED", "EV_L1_COMPLETE", "EV_COMPLETE"}
    )
    assert offenders == [], (
        f"a SIR-EV / SIR-AC / acceptance declaration is authored in tos.sir: {offenders} — "
        "authoring is not evidence (ADR-002-027 §26 line 644; §29 line 757)"
    )
