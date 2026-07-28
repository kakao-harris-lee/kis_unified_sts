"""§7.2 (b) anchor-resolution property — every cited ADR line and sibling symbol really resolves.

The #27 FD lesson has **two** halves. The named defect class ``anti-phantom`` was that an *absence*
claim ("no sibling owns this") was asserted without a grep; its symmetric blind spot, found during that
implementation, was that an *existence* claim was equally unverified — a contract had turned prose into
a symbol name that did not exist.

design #30 §7.2 (b) answers both halves for this package, and adds the **M7** requirement that made this
contract's own v1.0 wrong: an anchor is verified not only by *line number* but by the **text really
being on that line**, so an off-by-one (a citation landing on a blank line) cannot pass. Every
``§N line M`` this package cites is re-resolved against ADR-002-028 itself here:

* the line exists;
* the cited text is on it, verbatim;
* the line is inside the cited section.

The **absence** half is asserted alongside: everything design #30 §0.2 says ``tos.stm`` does not author
must be absent from the package — checked against the union of the module namespaces **and** an AST
sweep of every source, so a symbol buried in a class body or left out of ``__all__`` cannot slip through
(the #27 adversarial-review MAJOR-1 lesson: lock authorship, not the export surface).

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import ModuleType

import pytest
import tos.stm as s
import tos.stm._base
import tos.stm.predicates
import tos.stm.records
import tos.stm.state
import tos.stm.vocabulary

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOS_SRC = _REPO_ROOT / "tos" / "src" / "tos"
_STM_SRC = _TOS_SRC / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


_ADR = (
    _REPO_ROOT
    / "tos-spec"
    / "src"
    / "part-1-foundation"
    / "ADR-002-028-Safety-Telemetry-Integrity-Continuous-Conformance-Monitoring-and-Alert-Escalation-Governance.md"
)

_SUBMODULES: dict[str, ModuleType] = {
    "_base": tos.stm._base,
    "predicates": tos.stm.predicates,
    "records": tos.stm.records,
    "state": tos.stm.state,
    "vocabulary": tos.stm.vocabulary,
}


def _adr_lines() -> list[str]:
    """The ADR as 1-indexed lines (index 0 is a sentinel)."""
    return [""] + _ADR.read_text(encoding="utf-8").splitlines()


def _section_of(line_number: int) -> str | None:
    """The ``## N.`` / ``### N.M`` heading a line belongs to."""
    heading: str | None = None
    for index, text in enumerate(_adr_lines()):
        if index > line_number:
            break
        match = re.match(r"^#{2,3}\s+(?:STM-(?:INV|AC)-\d+|(\d+(?:\.\d+)?))", text)
        if match:
            heading = text.strip()
    return heading


#: ``(line, section-prefix, verbatim fragment)`` for every anchor this package cites (design #30 §7.2
#: (b)). The fragment is asserted to be **on that exact line** — the M7 off-by-one seal.
_ANCHORS: tuple[tuple[int, str, str], ...] = (
    (23, "## 1.", "Dashboard labels, aggregate scores, heartbeats"),
    (25, "## 1.", "It does not approve an action, create headroom"),
    (25, "## 1.", "satisfy preventive control"),
    (135, "### 5.7", "missing, stale, conflicting, ambiguous, discontinuous"),
    (139, "### 5.8", "An immutable non-authorizing record of one alert identity"),
    (143, "### 5.9", "records cannot be unioned, substituted"),
    (147, "### 5.10", "It cannot clear a restriction or create permission"),
    (151, "### 5.11", "SHALL NOT disable source collection, invariant evaluation"),
    (159, "### STM-INV-001", "creates capacity, approval, live authority"),
    (163, "### STM-INV-002", "Missing or unknown coverage is a gap, not an exemption"),
    (167, "### STM-INV-003", "A consumer cannot reinterpret or silently default them"),
    (171, "### STM-INV-004", "empty query, or green dashboard proves safety"),
    (
        175,
        "### STM-INV-005",
        "blocks dependent new risk and expands to the greatest credible scope",
    ),
    (179, "### STM-INV-006", "do not count as independent paths"),
    (
        183,
        "### STM-INV-007",
        "local threshold, hidden grace period, or favorable sampling rule",
    ),
    (187, "### STM-INV-008", "cannot disable a required restrictive path"),
    (191, "### STM-INV-009", "Advancement of one never implies another"),
    (195, "### STM-INV-010", "cannot preferentially discard adverse state"),
    (
        199,
        "### STM-INV-011",
        "Monitoring may request restriction and incident evaluation only",
    ),
    (203, "### STM-INV-012", "A successful check can only avoid denial"),
    (207, "### STM-INV-013", "Cancel ACK is not Final Quantity Proof"),
    (
        211,
        "### STM-INV-014",
        "cannot replace a preventive or restrictive enforcement point",
    ),
    (215, "### STM-INV-015", "cannot restore prior authority or automatically re-arm"),
    (219, "### STM-INV-016", "cannot publish or accept a prior Monitor Generation"),
    (236, "## 7.", "alert severity is not protective classification"),
    (249, "## 8.", "Unknown materiality is Critical"),
    (267, "## 8.", "does not establish semantic equivalence"),
    (288, "## 9.", "never as an out-of-band addition"),
    (290, "## 9.", "independent policy governance proves"),
    (292, "## 9.", "cannot replace item-level closure"),
    (
        300,
        "## 10.",
        "Identical values before and after a discontinuity do not prove continuity",
    ),
    (302, "## 10.", "Cross-host monotonic values SHALL NOT be directly subtracted"),
    (312, "## 11.", "deterministic for identical inputs"),
    (314, "## 11.", "window that permits an individual exceedance"),
    (316, "## 11.", "It never yields `CONFORMING` by default"),
    (327, "## 12.", "exact scope and dependency closure"),
    (335, "## 12.", "`CONFORMING` requires every required item to be current"),
    (
        337,
        "## 12.",
        "A stale owner is treated as potentially active until hard fencing is proven",
    ),
    (347, "## 13.", "until isolation is positively proven"),
    (349, "## 13.", "Monitoring recovery does not close the gap by itself"),
    (355, "## 14.", "is a disclosed common mode"),
    (357, "## 14.", "remaining common mode is recorded as residual risk"),
    (359, "## 14.", "treat its own health endpoint as proof"),
    (365, "## 15.", "automatically restrictive on expiry or uncertainty"),
    (384, "## 16.", "bound to exactly that alert"),
    (388, "## 16.", "It is not containment, remediation, broker finality"),
    (390, "## 16.", "preserves the original deadline"),
    (400, "## 17.", "ADR-002-027 remains responsible for materiality"),
    (402, "## 17.", "clear a local latch, or publish `NO_INCIDENT`"),
    (419, "## 18.", "Cached green state, TTL, heartbeat"),
    (421, "## 18.", "ordered before the capability claim, the send is denied"),
    (427, "## 19.", "cannot set an order to rejected"),
    (429, "## 19.", "Missing broker ACK remains possible acceptance"),
    (431, "## 19.", "It never expires existing economic effect"),
    (458, "## 21.", "treat monitoring state as restricted and unsuppressed"),
    (474, "## 22.", "raw and derived telemetry integrity and continuity"),
    (499, "## 23.", "SHALL NOT default to green"),
    (507, "## 24.", "occurs behind the ADR-002-017 Recovery Barrier"),
    (511, "## 24.", "a fresh ADR-002-007/015 governed re-arm chain remains mandatory"),
    (594, "## 27.", "They are not completed evidence"),
    (674, "## 29.", "B_safety_telemetry_loss_detect"),
    (698, "## 30.", "does not satisfy these gates"),
)


# --- the M7 seal: line number AND text AND section ------------------------


@pytest.mark.parametrize("line_number,section,fragment", _ANCHORS)
def test_every_cited_anchor_resolves_to_its_line_text_and_section(
    line_number: int, section: str, fragment: str
) -> None:
    """(§7.2 (b), M7) The cited text is really on that line, inside that section."""
    lines = _adr_lines()
    assert line_number < len(lines), f"ADR has no line {line_number}"
    assert fragment in lines[line_number], (
        f"ADR line {line_number} does not contain {fragment!r} — an off-by-one or a drifted "
        f"citation.\n  actual: {lines[line_number]!r}"
    )
    heading = _section_of(line_number)
    assert heading is not None and heading.startswith(
        section
    ), f"ADR line {line_number} is under {heading!r}, not {section!r} — a misattributed citation"


def test_the_anchor_scan_detects_an_off_by_one(tmp_path: Path) -> None:
    """(canary) An off-by-one really fails — a blank neighbouring line would have passed a count check."""
    lines = _adr_lines()
    line_number, _, fragment = _ANCHORS[0]
    assert fragment in lines[line_number]
    assert fragment not in lines[line_number - 1]
    assert fragment not in lines[line_number + 1]


def test_the_inv_anchors_are_body_lines_not_headings() -> None:
    """(M7) The sixteen STM-INV citations point at the invariant **text**, not the heading line."""
    lines = _adr_lines()
    for line_number, section, _ in _ANCHORS:
        if not section.startswith("### STM-INV"):
            continue
        assert not lines[line_number].startswith("#"), (
            f"ADR line {line_number} is a heading — the design #30 v1.1 M7 correction moved every "
            "STM-INV citation onto its body line"
        )
        assert lines[line_number].strip(), f"ADR line {line_number} is blank"


def test_all_sixteen_invariants_are_cited() -> None:
    """(§12) STM-INV-001..016 — 過 0 · 不 0, each with a verbatim body-line anchor."""
    cited = {section for _, section, _ in _ANCHORS if section.startswith("### STM-INV")}
    assert cited == {f"### STM-INV-{n:03d}" for n in range(1, 17)}


# --- existence half: every cited sibling symbol really resolves ------------


def test_canonical_and_ordering_reuse_targets_resolve() -> None:
    """(§3.1/§3.2 REUSE) The core symbols stm actually imports resolve, and PROMOTE is 0."""
    from tos.canonical import (
        EVL1ProvisionalCanonicalizer,
        IndependentIdArtifact,
        classify_record_pair,
    )
    from tos.ordering import compare_order

    assert callable(classify_record_pair)
    assert callable(compare_order)
    assert EVL1ProvisionalCanonicalizer is not None
    for artifact in (
        s.SafetyMonitoringPolicy,
        s.CriticalTelemetryManifest,
        s.MonitorCoverageManifest,
        s.ContinuousConformanceSnapshot,
        s.SafetyMonitoringGap,
        s.SafetyAlertRecord,
        s.AlertEscalationRecord,
    ):
        assert issubclass(artifact, IndependentIdArtifact)


def test_ioc_conformance_result_is_a_real_same_name_collision() -> None:
    """(§0.5 seal 3) ioc's enum exists, seals truthiness the same way, and is a different proposition."""
    from tos.ioc import ConformanceResult

    assert {member.value for member in ConformanceResult} == {
        "CONFORMANT",
        "NON_CONFORMANT",
        "UNKNOWN",
    }
    assert {member.value for member in s.AggregateConformanceResult} != {
        member.value for member in ConformanceResult
    }
    with pytest.raises(TypeError):
        bool(ConformanceResult.CONFORMANT)
    assert ConformanceResult is not s.AggregateConformanceResult


def test_the_monitoring_string_collisions_are_real_and_on_other_axes() -> None:
    """(§0.5 seal 4) wdr and brokercap really carry a "monitoring" member — a different axis each."""
    from tos.brokercap import AssuranceLevel
    from tos.wdr import CompensatingControlKind

    assert CompensatingControlKind.MONITORING.value == "MONITORING"
    assert AssuranceLevel.LEVEL_4_CONTINUOUSLY_MONITORED.value.startswith("LEVEL_4")
    assert CompensatingControlKind is not s.CoverageDimension
    assert "MONITORING" not in {member.value for member in s.CoverageDimension}


def test_iap_single_use_shape_is_the_reused_precedent() -> None:
    """(§3.3 / §5.9) The iap single-use gate exists — stm re-expresses its shape, never imports it."""
    source = (_TOS_SRC / "iap" / "predicates.py").read_text(encoding="utf-8")
    assert "single_use is not True" in source
    assert "unioned_or_substituted" in s.NEGATIVE_POLARITY_FIELDS
    assert not hasattr(s, "ApprovalResult")


def test_the_eleven_non_truthy_precedent_packages_still_carry_the_pattern() -> None:
    """(§2.2 / §3.3) The ``_NonTruthyStrEnum`` precedent is real — stm re-expresses it locally."""
    precedents = (
        "cur",
        "egress",
        "hag",
        "iap",
        "nontrade",
        "posttrade",
        "rlp",
        "sbr",
        "sir",
        "venue",
        "wdr",
    )
    for package in precedents:
        text = (_TOS_SRC / package / "vocabulary.py").read_text(encoding="utf-8")
        assert (
            "_NonTruthyStrEnum" in text
        ), f"{package} no longer carries the seal precedent"
    local = (_STM_SRC / "vocabulary.py").read_text(encoding="utf-8")
    assert (
        "class _NonTruthyStrEnum(StrEnum):" in local
    )  # locally authored, not imported


def test_the_all_false_authority_precedent_is_real() -> None:
    """(§3.3) The ``AllFalse*Authority`` convention exists across the series — re-expressed locally."""
    precedents = ("cur", "egress", "rlp", "sir", "wdr", "rcl", "liveauth")
    for package in precedents:
        sources = sorted((_TOS_SRC / package).rglob("*.py"))
        assert (
            sources
        ), f"no source found for the {package} precedent — the sweep would be vacuous"
        found = any("AllFalse" in path.read_text(encoding="utf-8") for path in sources)
        assert found, f"{package} no longer carries an AllFalse*Authority block"
    local = (_STM_SRC / "_base.py").read_text(encoding="utf-8")
    assert "class AllFalseMonitoringAuthority(FrozenModel):" in local


# --- absence half: everything design #30 §0.2 forbids is unauthored --------


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
    """Every identifier any ``tos.stm`` source *defines* — at any nesting depth."""
    names: set[str] = set()
    sources = _stm_sources()
    assert sources, f"no tos.stm source found under {_STM_SRC}"
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


@pytest.mark.parametrize(
    "forbidden",
    [
        # §0.2 — no collection / transport mechanism (runtime / vendor owned)
        "TelemetryCollector",
        "MetricScraper",
        "MonitorEvaluator",
        "CoverageCompiler",
        "AlertDispatcher",
        "EscalationEngine",
        "NotificationRoute",
        "DashboardRenderer",
        # §0.2 — no enforcement mechanism (egress / authority / spg owned)
        "enforce_restriction",
        "restrictive_ingress",
        "writer_fence",
        "HardFence",
        "MonitorGenerationRegistry",
        # §0.2 — no capacity arithmetic (rcl edge 0; §7 line 235)
        "CapacityVector",
        "worst_credible_effect",
        "reserve_capacity",
        "capacity_headroom",
        # §0.2 — no authority issuance (liveauth / authority / hag owned)
        "issue_live_authorization",
        "LiveAuthorization",
        "SafetyAuthority",
        "EffectivePrincipalGraph",
        # §0.2 — cur's judgement stays cur's
        "DimensionKey",
        "vector_complete",
        "MANDATED_DIMENSION_FLOOR",
        "SafetyCurrentnessVector",
        # §0.2 / §8 — no VP-002 key authorship
        "VP_002_KEYS",
        "B_safety_telemetry_loss_detect",
        "MAX_critical_telemetry_age_ms",
    ],
)
def test_forbidden_concept_is_unauthored(forbidden: str) -> None:
    """(§0.2 absence lock) Each concept design #30 §0.2 excludes is absent from *authorship*.

    Checked against module ``vars()`` **plus** an AST sweep of every source, so a symbol nested inside a
    class body or omitted from ``__all__`` is caught too — the #27 lesson that an export-surface check
    would have waved such a symbol through.
    """
    assert forbidden not in _authored_names(), (
        f"{forbidden} is authored in tos.stm — design #30 §0.2 assigns it to a sibling, the runtime, "
        "a vendor, a human governance step, or Phase-0"
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


def test_no_stm_ev_is_declared_anywhere() -> None:
    """(§0.2 / §1) The package declares no STM-EV, no STM-AC and no acceptance — closes **nothing**."""
    authored = _authored_names()
    offenders = sorted(
        name
        for name in authored
        if name.upper().startswith(("STM_EV", "STM_AC"))
        or name.upper() in {"ACCEPTED", "EV_L1_COMPLETE", "EV_COMPLETE"}
    )
    assert offenders == [], (
        f"a STM-EV / STM-AC / acceptance declaration is authored in tos.stm: {offenders} — "
        "authoring is not evidence (ADR-002-028 §27 line 594; §30 line 698)"
    )
