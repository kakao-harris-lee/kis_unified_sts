"""Polarity + truthy-sentinel regression (design #31 §6 / §11; the #18/#22/#23/#25 lesson).

Two defect classes, both of which have bitten this series before:

* **truthy sentinel.** Every verdict-shaped ``StrEnum`` has non-empty string members, so
  ``if verdict:`` reads ``DENY`` / ``REJECT`` / ``INADMISSIBLE`` as *truthy* — a silent fail-open.
  The engine's verdict enums are therefore **truthy-untestable** (``__bool__`` raises), and the
  mandated consume gate is the explicit positive identity (design #31 §6/§4.2 rule 1).
* **negated gates.** ``verdict is not DENY`` fails open on ``None`` and on any future member. The
  shipped sources are grepped so the forbidden normalization cannot reappear in a later edit.

The sibling verdict adapters are exercised over their **whole** result vocabularies (not a happy
sample), including venue's four-valued result whose ``RESTRICTED_PROTECTIVE_ONLY`` member is the
one a truthiness read would misread as permission.

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from tos.afg import ActionFlowResult
from tos.are import RiskDecisionResult
from tos.cur import ProofResult
from tos.engine import (
    AdmissionVerdict,
    DispatchResolution,
    EgressResultKind,
    OrderingAdmission,
    StageOutcome,
    action_flow_decision_verdict,
    action_flow_permit_verdict,
    aggregate_risk_decision_verdict,
    conformance_proof_verdict,
    economic_effect_envelope_verdict,
    egress_currentness_verdict,
    transmission_capability_verdict,
    venue_admissibility_verdict,
)
from tos.ioc import ConformanceResult
from tos.rcl import CapacityComponent, CapacityVector
from tos.venue import OrderAdmissibilityResult

_ENGINE_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"

_TRUTHY_UNTESTABLE = (
    StageOutcome,
    EgressResultKind,
    AdmissionVerdict,
    OrderingAdmission,
    DispatchResolution,
)


@pytest.mark.parametrize("enum_type", list(_TRUTHY_UNTESTABLE))
def test_every_verdict_enum_is_truthy_untestable(enum_type) -> None:
    """(§6) ``if verdict:`` raises rather than silently reading a denial as a pass."""
    for member in enum_type:
        with pytest.raises(TypeError, match="not truthy-testable"):
            bool(member)


@pytest.mark.parametrize("enum_type", list(_TRUTHY_UNTESTABLE))
def test_the_seal_covers_the_denial_members_specifically(enum_type) -> None:
    """(§6) The seal is what protects the *denial* members — the pass member matters least."""
    denials = [m for m in enum_type if m.name not in {"ADMIT", "ADMISSIBLE", "DISPATCHED", "ACK"}]
    assert denials
    for member in denials:
        with pytest.raises(TypeError):
            if member:  # noqa: SIM103 - the point is that this expression raises
                pass


def test_no_engine_source_uses_a_negated_denial_gate() -> None:
    """(§6/§4.2 rule 1) ``is not DENY`` / ``is not INADMISSIBLE`` never appears in the sources."""
    forbidden = re.compile(
        r"is\s+not\s+(?:StageOutcome\.DENY|StageOutcome\.UNKNOWN|"
        r"AdmissionVerdict\.INADMISSIBLE|OrderAdmissibilityResult\.INADMISSIBLE|"
        r"ConformanceResult\.NON_CONFORMANT|RiskDecisionResult\.DENY|ActionFlowResult\.DENY|"
        r"ProofResult\.RESTRICTED)"
    )
    offenders: list[str] = []
    for path in sorted(_ENGINE_SRC.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{path.name}:{lineno} {line.strip()}")
    assert offenders == [], (
        "a negated denial gate fails open on None and on any future member — the mandated gate is "
        f"the positive identity (design #31 §4.2 rule 1 / §6); found: {offenders}"
    )


def test_no_engine_source_normalizes_a_negative_flag_with_is_not_true() -> None:
    """(series discipline) A negative-polarity ``bool | None`` is cleared by ``is False`` alone.

    Reading ``is not True`` on a negative-polarity flag turns an *unknown* into a "safe" — the
    #18/#22/#23/#25 MAJOR-2 regression. The engine's own negative-polarity surface is small, so the
    check is a source grep: the normalization simply must not appear.
    """
    offenders: list[str] = []
    for path in sorted(_ENGINE_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and len(node.ops) == 1:
                op = node.ops[0]
                comparator = node.comparators[0]
                if (
                    isinstance(op, ast.IsNot)
                    and isinstance(comparator, ast.Constant)
                    and comparator.value is True
                ):
                    offenders.append(f"{path.name}:{node.lineno} `is not True`")
    assert offenders == [], (
        "`is not True` reads an unknown as cleared; a negative-polarity flag is cleared only by "
        f"`is False` (design #31 §6); found: {offenders}"
    )


# ---------------------------------------------------------------------------
# sibling verdict adapters — exhaustive over each result vocabulary (§5.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (OrderAdmissibilityResult.ADMISSIBLE, StageOutcome.ADMIT),
        (OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY, StageOutcome.DENY),
        (OrderAdmissibilityResult.INADMISSIBLE, StageOutcome.DENY),
        (OrderAdmissibilityResult.UNKNOWN, StageOutcome.UNKNOWN),
        (None, StageOutcome.UNKNOWN),
    ],
)
def test_the_venue_adapter_folds_every_member(result, expected) -> None:
    """(§5.2) Only ADMISSIBLE admits; protective-only denies with its own reason."""
    verdict = venue_admissibility_verdict(result)
    assert verdict.outcome is expected
    if result is OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:
        assert verdict.reason is not None
        assert "protective" in verdict.reason


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (ConformanceResult.CONFORMANT, StageOutcome.ADMIT),
        (ConformanceResult.NON_CONFORMANT, StageOutcome.DENY),
        (ConformanceResult.UNKNOWN, StageOutcome.UNKNOWN),
        (None, StageOutcome.UNKNOWN),
    ],
)
def test_the_conformance_adapter_folds_every_member(result, expected) -> None:
    """(§5.2) Only CONFORMANT admits (ADR-002-020 §14:372-376)."""
    assert conformance_proof_verdict(result).outcome is expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (RiskDecisionResult.GRANT, StageOutcome.ADMIT),
        (RiskDecisionResult.DENY, StageOutcome.DENY),
        (RiskDecisionResult.UNKNOWN, StageOutcome.UNKNOWN),
        (None, StageOutcome.UNKNOWN),
    ],
)
def test_the_aggregate_risk_adapter_folds_every_member(result, expected) -> None:
    """(§5.2) Only GRANT admits; UNKNOWN blocks new risk (ARE-INV-006:173)."""
    assert aggregate_risk_decision_verdict(result).outcome is expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (ActionFlowResult.GRANT, StageOutcome.ADMIT),
        (ActionFlowResult.DENY, StageOutcome.DENY),
        (ActionFlowResult.UNKNOWN, StageOutcome.UNKNOWN),
        (None, StageOutcome.UNKNOWN),
    ],
)
def test_the_action_flow_adapter_folds_every_member(result, expected) -> None:
    """(§5.2) Only GRANT admits; UNKNOWN blocks new normal risk (AFG-INV-007:181)."""
    assert action_flow_decision_verdict(result).outcome is expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (ProofResult.CURRENT, StageOutcome.ADMIT),
        (ProofResult.RESTRICTED, StageOutcome.DENY),
        (ProofResult.UNKNOWN, StageOutcome.UNKNOWN),
        (None, StageOutcome.UNKNOWN),
    ],
)
def test_the_currentness_adapter_folds_every_member(result, expected) -> None:
    """(§12-3) The D-E4 hand-off typing: only CURRENT satisfies (ADR-002-024 §12:316)."""
    assert egress_currentness_verdict(result).outcome is expected


def test_the_permit_and_capability_adapters_need_a_positive_identity() -> None:
    """(§5.2) A missing permit / capability is UNKNOWN, never an assumed pass."""
    assert action_flow_permit_verdict(None).outcome is StageOutcome.UNKNOWN
    assert transmission_capability_verdict(None).outcome is StageOutcome.UNKNOWN


def test_the_economic_effect_adapter_is_empty_and_unknown_aware() -> None:
    """(§5.2) ∅ envelope ⇒ UNKNOWN; an UNKNOWN magnitude ⇒ UNKNOWN; complete ⇒ ADMIT."""
    from decimal import Decimal

    assert economic_effect_envelope_verdict(None).outcome is StageOutcome.UNKNOWN
    assert economic_effect_envelope_verdict(CapacityVector()).outcome is StageOutcome.UNKNOWN
    unknown_magnitude = CapacityVector(
        components=(CapacityComponent(dimension_id="notional", magnitude=None),)
    )
    assert economic_effect_envelope_verdict(unknown_magnitude).outcome is StageOutcome.UNKNOWN
    complete = CapacityVector(
        components=(CapacityComponent(dimension_id="notional", magnitude=Decimal("10")),)
    )
    assert economic_effect_envelope_verdict(complete).outcome is StageOutcome.ADMIT


def test_the_adapters_derive_the_native_type_structurally() -> None:
    """(구조 파생 > 자기신고) The recorded native type comes from the artifact, not a caller label."""
    verdict = venue_admissibility_verdict(OrderAdmissibilityResult.ADMISSIBLE)
    assert verdict.native_verdict_type == "OrderAdmissibilityResult"
    assert verdict.native_verdict_value == "ADMISSIBLE"
