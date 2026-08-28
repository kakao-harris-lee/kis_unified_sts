"""Forbidden-verb + clock-free + cur-direct-wiring constructive-absence canary (design #30 §4.1/§7).

stm is **pure, non-transmitting, non-collecting, non-mutating, and clock-free** (§4.1). The
constructive-absence canary asserts the package defines **no** send / transmit / emit / scrape / collect
/ publish / deliver / page / escalate / sign / arm / mutate / reserve / release / clear-halt / connect /
socket function. stm performs telemetry-integrity *structural judgement* only; the real collection,
evaluation, delivery, escalation and suppression are runtime, vendor and sibling-owned (design #30
§0.2/§6c).

The verb rule is deliberately **shape-aware** (design #30 §4.1): a *nominal* predicate name
(``deterministic_evaluation_bound_integrity`` / ``critical_coverage_complete_or_gap`` /
``alert_state_is_orthogonal``) is a judgement and is allowed; an *imperative* signature (``def
deliver(``, ``def scrape(``, ``def escalate(``, ``def page_oncall(``) is a capability and is forbidden.
The one nominal name that collides with a forbidden verb prefix is whitelisted **explicitly**, by exact
name, with its §4.1 justification — never by weakening the rule.

The second canary is the **cur direct-wiring ban** (design #30 §3.6 / §4.1): cur owns the MONITORING
currentness dimension's completeness judgement (``cur/vocabulary.py:144`` inside the mandated floor at
``:172``); stm produces only that dimension's *value*. So cur's ``DimensionKey`` / ``vector_complete`` /
``MANDATED_DIMENSION_FLOOR`` names must be **absent** from every stm source — stm may not usurp cur's
judgement, which is the #28 C1 defect this contract faces head-on.

Regime tag: coverage-completeness / deterministic-evaluation substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.stm import (
    AlertEscalationRecord,
    ContinuousConformanceSnapshot,
    CriticalTelemetryManifest,
    MonitorCoverageManifest,
    SafetyAlertRecord,
    SafetyMonitoringGap,
    SafetyMonitoringPolicy,
)
from tos.stm._base import DigestBoundArtifact

_STM_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


#: Unambiguous capability verbs — any function whose name **starts with** one of these is a capability.
_FORBIDDEN_VERB_PREFIXES = (
    "send",
    "transmit",
    "emit",
    "dispatch",
    "publish",
    "deliver",
    "scrape",
    "ingest",
    "sign",
    "arm",
    "rearm",
    "re_arm",
    "mutate",
    "reserve",
    "release",
    "transfer",
    "commit_capacity",
    "authorize",
    "activate",
    "clear_halt",
    "clearhalt",
    "connect",
    "socket",
    "revoke_",
    "quarantine_",
    "fence_",
    "latch_",
    "notify_",
    "render_",
)

#: Verbs with a legitimate **nominal** form in this ADR's vocabulary. Only the *imperative* shape is
#: forbidden: the bare verb, or the verb followed by ``_`` (``collect_metrics`` / ``alert_oncall`` /
#: ``escalate_page`` / ``suppress_signal`` / ``page_owner`` / ``open_route``).
_FORBIDDEN_IMPERATIVE_VERBS = (
    "collect",
    "alert",
    "escalate",
    "page",
    "suppress",
    "acknowledge",
    "evaluate",
    "close",
    "open",
    "approve",
)

#: The **only** nominal exceptions, each an explicit judgement predicate the design #30 §4.1 canary rule
#: names verbatim as allowed ("술어 이름의 명사형 ... 은 허용"). Asserted as an exact set so it can never
#: grow silently, and each entry is checked to be a real declared function.
_NOMINAL_JUDGEMENT_WHITELIST = frozenset({"alert_state_is_orthogonal"})

#: Real-clock call fragments a clock-free package must never reference (design #30 §8/§9.1).
_FORBIDDEN_CLOCK_FRAGMENTS = (
    "time.time",
    "time.monotonic",
    "datetime.now",
    "datetime.utcnow",
    "perf_counter",
    "monotonic()",
)

#: cur-owned names stm must never author or reference (design #30 §3.6 / §4.1 — the #28 C1 seal).
_CUR_OWNED_NAMES = ("DimensionKey", "vector_complete", "MANDATED_DIMENSION_FLOOR")

#: Ambient-environment / dynamic-escape fragments (mirrored by the import-closure AST scan).
_FORBIDDEN_ESCAPE_FRAGMENTS = (
    "os.environ",
    "os.getenv",
    "importlib",
    "__import__",
    "eval(",
    "exec(",
)

_ARTIFACTS = (
    SafetyMonitoringPolicy,
    CriticalTelemetryManifest,
    MonitorCoverageManifest,
    ContinuousConformanceSnapshot,
    SafetyMonitoringGap,
    SafetyAlertRecord,
    AlertEscalationRecord,
)


def _is_forbidden_name(name: str) -> bool:
    """Whether a defined function name is a capability rather than a judgement (§4.1)."""
    lowered = name.lstrip("_").lower()
    if lowered in _NOMINAL_JUDGEMENT_WHITELIST:
        return False
    if lowered.startswith(_FORBIDDEN_VERB_PREFIXES):
        return True
    return any(
        lowered == verb or lowered.startswith(f"{verb}_")
        for verb in _FORBIDDEN_IMPERATIVE_VERBS
    )


def _defined_functions() -> list[tuple[str, str, int]]:
    """Every function / method any stm source defines, at any nesting depth."""
    found: list[tuple[str, str, int]] = []
    sources = _stm_sources()
    assert sources, f"no tos.stm source found under {_STM_SRC}"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((path.name, node.name, node.lineno))
    return found


def test_no_capability_function_is_defined() -> None:
    """(§4.1) The package defines no send / collect / deliver / escalate / suppress capability."""
    offenders = [
        f"{file}:{line} def {name}("
        for file, name, line in _defined_functions()
        if _is_forbidden_name(name)
    ]
    assert offenders == [], (
        "capability function defined in tos.stm — stm judges telemetry integrity structurally and "
        f"collects / evaluates / delivers / escalates nothing (design #30 §0.2/§4.1): {offenders}"
    )


def test_the_verb_rule_really_fires() -> None:
    """(canary) The shape-aware rule catches imperatives and admits nominal judgements — not vacuous."""
    for imperative in (
        "send",
        "send_alert",
        "collect",
        "collect_telemetry",
        "deliver_page",
        "escalate",
        "escalate_alert",
        "page",
        "suppress_signal",
        "publish_snapshot",
        "scrape_metrics",
        "activate_policy",
        "release_capacity",
        "clear_halt",
    ):
        assert _is_forbidden_name(imperative) is True, imperative
    for nominal in (
        "critical_coverage_complete_or_gap",
        "deterministic_evaluation_bound_integrity",
        "evaluation_is_deterministic",
        "suppression_cannot_suppress_safety",
        "escalation_single_binding",
        "monitor_generation_advances",
        "handoff_is_non_authorizing",
        "alert_state_is_orthogonal",
    ):
        assert _is_forbidden_name(nominal) is False, nominal


def test_the_nominal_whitelist_is_exact_and_real() -> None:
    """(§4.1) The nominal exception list cannot grow silently and names only real functions."""
    defined = {name for _, name, _ in _defined_functions()}
    assert frozenset({"alert_state_is_orthogonal"}) == _NOMINAL_JUDGEMENT_WHITELIST
    for name in _NOMINAL_JUDGEMENT_WHITELIST:
        assert name in defined, f"{name} is whitelisted but is not a declared function"


@pytest.mark.parametrize("fragment", _FORBIDDEN_CLOCK_FRAGMENTS)
def test_no_source_reads_a_real_clock(fragment: str) -> None:
    """(§8 clock-free) A Monitor Generation is an ordering identity, never wall-clock."""
    offenders = [
        path.name
        for path in _stm_sources()
        if fragment in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"real-clock fragment {fragment!r} found in: {offenders}"


@pytest.mark.parametrize("fragment", _FORBIDDEN_ESCAPE_FRAGMENTS)
def test_no_source_uses_an_ambient_env_or_dynamic_escape(fragment: str) -> None:
    """(§0.3) No ``os.environ`` / ``importlib`` / ``eval`` / ``exec`` anywhere in the package."""
    offenders = [
        path.name
        for path in _stm_sources()
        if fragment in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"escape fragment {fragment!r} found in: {offenders}"


@pytest.mark.parametrize("name", _CUR_OWNED_NAMES)
def test_no_source_wires_curs_monitoring_dimension_judgement(name: str) -> None:
    """(**#28 C1 seal**, §3.6/§4.1) cur owns the MONITORING dimension's completeness judgement.

    stm produces the dimension's **value** (a Monitor Generation and a Continuous Conformance Snapshot
    digest); filling cur's vector slot and judging its completeness is downstream's. If any of cur's
    judgement names ever appeared in an stm source, stm would be usurping that judgement — the exact
    same-name / different-owner defect the #28 review found in SIR.
    """
    offenders = [
        path.name for path in _stm_sources() if name in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"cur-owned name {name!r} appears in: {offenders} — cur owns the MONITORING currentness "
        "dimension's completeness judgement (cur/vocabulary.py:144, :172); stm produces only its value"
    )


@pytest.mark.parametrize("artifact", _ARTIFACTS)
def test_no_artifact_has_a_mutating_or_transmitting_method(artifact: type) -> None:
    """(§2.3/§4.1) The artifacts are frozen append-only records with no imperative method."""
    inherited = set(dir(DigestBoundArtifact))
    own = [
        name
        for name in dir(artifact)
        if name not in inherited and not name.startswith("__")
    ]
    offenders = [name for name in own if _is_forbidden_name(name)]
    assert (
        offenders == []
    ), f"{artifact.__name__} exposes a capability method: {offenders}"
    assert artifact.model_config.get("frozen") is True
    assert artifact.model_config.get("extra") == "forbid"


def test_no_stm_ev_or_acceptance_is_declared_anywhere() -> None:
    """(§0.2 / §1) The package declares no STM-EV, no STM-AC and no acceptance — closes **nothing**."""
    offenders: list[str] = []
    for path in _stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            for name in names:
                upper = name.upper()
                if upper.startswith(("STM_EV", "STM_AC")) or upper in {
                    "ACCEPTED",
                    "EV_L1_COMPLETE",
                    "EV_COMPLETE",
                }:
                    offenders.append(f"{path.name} {name}")
    assert offenders == [], (
        f"an STM-EV / STM-AC / acceptance declaration is authored in tos.stm: {offenders} — "
        "authoring is not evidence (ADR-002-028 §27 line 594; §30 line 698)"
    )


def test_no_numeric_bound_constant_is_authored() -> None:
    """(§8) The eleven §29 OQ 12 keys are injected Profile-INSTANCE values, never constants here."""
    forbidden = (
        "B_safety_telemetry_loss_detect",
        "B_monitoring_gap_to_authority_restrict",
        "B_monitoring_gap_to_egress_deny",
        "B_critical_alert_delivery",
        "B_alert_escalation",
        "B_monitoring_generation_fence",
        "MAX_critical_telemetry_age_ms",
        "MAX_continuous_conformance_snapshot_age_ms",
        "MAX_safety_alert_age_ms",
        "MAX_monitoring_suppression_duration_ms",
        "MAX_alert_acknowledgement_age_ms",
    )
    authored: set[str] = set()
    for path in _stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                authored |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                authored.add(node.target.id)
    assert authored.isdisjoint(
        forbidden
    ), f"a VP-002 numeric bound key is authored in tos.stm: {sorted(authored & set(forbidden))}"


def test_no_broker_proper_noun_appears() -> None:
    """(broker-agnostic) No concrete broker or vendor name anywhere (project memory)."""
    forbidden = ("KIS", "한국투자", "Interactive Brokers", "Datadog", "PagerDuty")
    offenders: list[str] = []
    for path in _stm_sources():
        text = path.read_text(encoding="utf-8")
        offenders.extend(f"{path.name}:{name}" for name in forbidden if name in text)
    assert offenders == [], f"broker / vendor proper noun found: {offenders}"
