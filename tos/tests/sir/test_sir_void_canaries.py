"""Forbidden-verb + clock-free + forward-seam constructive-absence canary (design #28 §4.1/§7).

sir is **pure, non-transmitting, non-mutating, and clock-free** (§4.1). The constructive-absence canary
asserts the package defines **no** send / transmit / emit / sign / arm / rearm (execution), **no**
mutate / reserve / release / transfer / commit_capacity (capacity), **no** clear-halt / open / connect /
socket, and — specific to SIR — **no imperative** ``declare`` / ``contain`` / ``shutdown`` / ``close``
action. sir performs incident *structural judgement* only; the real declaration, containment, shutdown
and closure are runtime, human and sibling-owned (design #28 §0.2/§6c).

The verb rule is deliberately **shape-aware** (design #28 §4.1): a *nominal* predicate name
(``restrictive_declaration_non_authorizing`` / ``containment_uses_normal_authority`` /
``controlled_shutdown_not_broker_finality`` / ``closure_administrative_non_permissive``) is a judgement
and is allowed; an *imperative* signature (``def declare(``, ``def contain_scope(``, ``def shutdown(``,
``def close_incident(``) is a capability and is forbidden.

The second canary is the **forward-seam direct-wiring ban** (design #28 §3.6 / §4.1): sir produces only
the *incident component* (:func:`~tos.sir.predicates.dominating_open_incident_present`). The HALT
component is authority-owned and the *combined* consumer coordinate belongs downstream, so the
consumers' combined coordinate name must be **absent** from every sir source — sir may not usurp a
consumer's slot.

Regime tag: structural substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tos.sir import (
    ActiveSafetyIncidentSet,
    IncidentClosureDecision,
    IncidentContainmentPlan,
    IncidentRecoveryHandoffPackage,
    SafetyIncidentPolicy,
    SafetyIncidentRecord,
)
from tos.sir._base import DigestBoundArtifact

_SIR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sir"

#: Unambiguous capability verbs — any function whose name **starts with** one of these is a capability.
_FORBIDDEN_VERB_PREFIXES = (
    "send",
    "transmit",
    "emit",
    "dispatch",
    "publish",
    "deliver",
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
    "escalate_",
    "notify_",
)

#: SIR's four incident verbs. These have legitimate **nominal** forms (declaration / containment /
#: shutdown / closure), so only the **imperative** shape is forbidden: the bare verb, or the verb
#: followed by ``_`` (``declare_incident`` / ``close_incident`` / ``contain_scope`` / ``open_route``).
_FORBIDDEN_IMPERATIVE_VERBS = (
    "declare",
    "contain",
    "shutdown",
    "shut_down",
    "close",
    "open",
    "approve",
)

#: Real-clock call fragments a clock-free package must never reference (design #28 §8/§9.1).
_FORBIDDEN_CLOCK_FRAGMENTS = (
    "time.time",
    "time.monotonic",
    "datetime.now",
    "datetime.utcnow",
    "perf_counter",
    "monotonic()",
)

#: The downstream consumers' **combined** dominance coordinate. sir produces only the incident
#: component, so this exact name must never appear in a sir source (design #28 §3.6 / §4.1).
_CONSUMER_COMBINED_COORDINATE = "dominating_halt_or_incident"

_ARTIFACTS = (
    SafetyIncidentPolicy,
    SafetyIncidentRecord,
    ActiveSafetyIncidentSet,
    IncidentContainmentPlan,
    IncidentRecoveryHandoffPackage,
    IncidentClosureDecision,
)


def _is_forbidden_name(name: str) -> bool:
    """Whether a defined function name is a capability rather than a judgement (§4.1)."""
    lowered = name.lstrip("_").lower()
    if lowered.startswith(_FORBIDDEN_VERB_PREFIXES):
        return True
    return any(
        lowered == verb or lowered.startswith(f"{verb}_")
        for verb in _FORBIDDEN_IMPERATIVE_VERBS
    )


def _defined_function_names(path: Path) -> list[str]:
    """Return every def / async def name in a source file (module + method level)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def test_artifacts_have_no_capability_method() -> None:
    """(§4.1 constructive absence) No artifact exposes a send / mutate / declare / close method."""
    base_names = set(dir(DigestBoundArtifact))
    for artifact in _ARTIFACTS:
        for name in dir(artifact):
            if name in base_names:
                continue
            assert not _is_forbidden_name(name), (
                f"{artifact.__name__}.{name} looks like a sir capability — the structural absence "
                "of a transmit / mutate / declare / contain / shutdown / close method is this "
                "package's identity (design #28 §4.1; SIR-INV-001)"
            )


def test_no_sir_source_defines_a_capability_verb_function() -> None:
    """(§4.1 constructive absence, source scan) No sir source defines a capability-verb function."""
    offenders: list[str] = []
    sources = sorted(_SIR_SRC.rglob("*.py"))
    assert sources, f"no tos.sir source files found under {_SIR_SRC}"
    for path in sources:
        for name in _defined_function_names(path):
            if _is_forbidden_name(name):
                offenders.append(f"{path.name}: def {name}")
    assert offenders == [], f"forbidden capability-verb function defined: {offenders}"


def test_nominal_predicate_names_are_allowed() -> None:
    """(§4.1 shape rule) The nominal judgement names are **not** offenders — the rule is shape-aware."""
    for allowed in (
        "restrictive_declaration_non_authorizing",
        "declaration_creates_no_authority",
        "containment_uses_normal_authority",
        "controlled_shutdown_not_broker_finality",
        "closure_administrative_non_permissive",
        "closure_contract_complete",
        "closure_single_use_non_authorizing",
        "closure_independence_non_self_exemption",
        "obligations_survive_shutdown",
        "recovery_handoff_requires_accepted_barrier",
    ):
        assert _is_forbidden_name(allowed) is False


def test_verb_scan_detects_planted_imperative_offenders() -> None:
    """(canary) The scan catches every planted imperative — not vacuous."""
    for planted in (
        "declare_incident",
        "declare",
        "contain_scope",
        "shutdown",
        "close_incident",
        "open_route",
        "send_notification",
        "release_capacity",
        "clear_halt",
        "re_arm",
    ):
        assert (
            _is_forbidden_name(planted) is True
        ), f"planted {planted} was NOT detected"


def test_no_sir_source_references_a_real_clock() -> None:
    """(§8/§9.1 clock-free) No sir source references a real clock — an Incident Generation ≠ wall-clock."""
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fragment in _FORBIDDEN_CLOCK_FRAGMENTS:
            if fragment in text:
                offenders.append(f"{path.name}: {fragment}")
    assert offenders == [], f"clock reference in a clock-free package: {offenders}"


def test_no_sir_source_names_the_consumer_combined_coordinate() -> None:
    """(§3.6 / §4.1) sir never authors or assigns the consumers' **combined** dominance coordinate.

    sir produces the incident component only (``dominating_open_incident_present``). The HALT component
    is authority-owned and the combination plus the injection into the consumer's slot is downstream's
    (``protective/predicates.py:395``; ``sbr/predicates.py:731``). If sir named that coordinate it would
    be usurping a consumer's slot and silently owning half a proposition it does not own.
    """
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _CONSUMER_COMBINED_COORDINATE in line:
                offenders.append(f"{path.name}:{lineno}")
    assert offenders == [], (
        f"{_CONSUMER_COMBINED_COORDINATE!r} appears in a sir source — sir owns only the incident "
        f"component (design #28 §3.6 ambiguity prescription): {offenders}"
    )


def test_consumer_coordinate_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The forward-seam scan catches a planted direct wiring — not vacuous."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        f"def f(active_set):\n    {_CONSUMER_COMBINED_COORDINATE} = True\n    "
        f"return {_CONSUMER_COMBINED_COORDINATE}\n",
        encoding="utf-8",
    )
    hits = [
        line
        for line in planted.read_text(encoding="utf-8").splitlines()
        if _CONSUMER_COMBINED_COORDINATE in line
    ]
    assert hits, "the forward-seam scan failed to catch a planted direct wiring"


def test_no_sir_source_names_a_concrete_broker() -> None:
    """(broker-agnostic) No concrete broker, venue or vendor proper noun appears in a sir source.

    Project memory ``tos-spec-broker-agnostic``: broker constraints are capability classes; a concrete
    broker belongs in a Broker Capability Profile instance, never in ``tos.sir``.
    """
    forbidden_tokens = ("kis", "korea investment", "interactive brokers", "binance")
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
        lowered = path.read_text(encoding="utf-8").lower()
        for token in forbidden_tokens:
            if token in lowered:
                offenders.append(f"{path.name}: {token}")
    assert (
        offenders == []
    ), f"concrete broker named in a broker-agnostic package: {offenders}"


def test_no_numeric_bound_constant_is_hardcoded() -> None:
    """(design #28 §8) No ``B_incident_*`` / ``MAX_incident_*`` numeric bound is hardcoded in sir.

    ADR §28 item 12 makes every one of these a Profile-INSTANCE value, measured or approved at Phase-0
    and **null** in Phase 1; a hardcoded default would be a silently invented safety bound.
    """
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id.startswith(("B_incident", "MAX_incident", "B_controlled")):
                    offenders.append(f"{path.name}:{node.lineno} {target.id}")
    assert offenders == [], f"hardcoded Profile-INSTANCE bound in tos.sir: {offenders}"
