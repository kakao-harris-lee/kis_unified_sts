"""``CandidateConstruction`` combined-shape validator (design #34 §3.2, TOS-GAP-001).

``construct_candidate_command`` only ever produces two shapes: a **denied** bundle
(``command is None`` with a non-empty ``denial_reason`` and no ioc verdict) or a **built** bundle
(``command`` present alongside ``intent`` / ``envelope`` / ``policy`` and both ioc verdicts). The
model validator under test (``records.py::CandidateConstruction._shape_is_one_of_the_sanctioned_bundles``)
rejects every other combination at construction time, so a partially-formed bundle can never reach
the gateway.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.egressgw import CandidateConstruction, DerivationOutcome, QuantityDerivation
from tos.ioc import ConformanceResult

from ._egressgw_fixtures import admitted_price, construction


def _denied_derivation() -> QuantityDerivation:
    """A ``DENIED`` derivation — the only derivation shape a denied bundle may carry."""
    return QuantityDerivation(
        outcome=DerivationOutcome.DENIED, denial_reason="no admitted price"
    )


def _built() -> CandidateConstruction:
    """A real, fully-built bundle produced by the actual construction sites."""
    built = construction()
    assert built.command is not None
    return built


def _built_kwargs(built: CandidateConstruction) -> dict[str, object]:
    """The exact field set the real "built" construction site (:669) populates."""
    return {
        "derivation": built.derivation,
        "intent": built.intent,
        "envelope": built.envelope,
        "policy": built.policy,
        "command": built.command,
        "conformance_result": built.conformance_result,
        "numerical_result": built.numerical_result,
        "no_silent_widening_ok": built.no_silent_widening_ok,
    }


# ---------------------------------------------------------------------------
# the two sanctioned shapes construct cleanly
# ---------------------------------------------------------------------------


def test_the_denied_shape_construction_site_1_is_sanctioned() -> None:
    """(construction.py:594) A denial from the derivation itself is a valid denied bundle."""
    denied = construction(price=admitted_price(value=None))
    assert denied.command is None
    assert (denied.denial_reason or "").strip()
    assert denied.conformance_result is None
    assert denied.numerical_result is None
    assert denied.no_silent_widening_ok is None


def test_the_built_shape_construction_site_3_is_sanctioned() -> None:
    """(construction.py:669) A successful compile is a valid built bundle."""
    built = _built()
    assert built.denial_reason is None
    assert built.intent is not None
    assert built.envelope is not None
    assert built.policy is not None
    assert built.conformance_result is not None
    assert built.numerical_result is not None
    assert built.no_silent_widening_ok is not None


def test_a_denied_bundle_may_still_carry_partial_intent_envelope_policy() -> None:
    """(construction.py:641) The ioc-exception denial site may bind a partial intent/envelope/
    policy before compile_command raised — that partiality is not itself rejected, only a
    denial that also carries an ioc verdict is."""
    CandidateConstruction(
        derivation=_denied_derivation(),
        intent=_built().intent,
        envelope=_built().envelope,
        policy=_built().policy,
        denial_reason="ioc construction denied the candidate: boom",
    )


# ---------------------------------------------------------------------------
# denied-shape violations (command is None)
# ---------------------------------------------------------------------------


def test_a_denied_bundle_with_no_denial_reason_is_rejected() -> None:
    with pytest.raises(ValidationError, match="denial_reason"):
        CandidateConstruction(derivation=_denied_derivation(), denial_reason=None)


def test_a_denied_bundle_with_a_blank_denial_reason_is_rejected() -> None:
    with pytest.raises(ValidationError, match="denial_reason"):
        CandidateConstruction(derivation=_denied_derivation(), denial_reason="   ")


def test_a_denied_bundle_carrying_a_conformance_verdict_is_rejected() -> None:
    with pytest.raises(ValidationError, match="ioc verdict"):
        CandidateConstruction(
            derivation=_denied_derivation(),
            denial_reason="denied",
            conformance_result=ConformanceResult.CONFORMANT,
        )


def test_a_denied_bundle_carrying_a_numerical_verdict_is_rejected() -> None:
    with pytest.raises(ValidationError, match="ioc verdict"):
        CandidateConstruction(
            derivation=_denied_derivation(),
            denial_reason="denied",
            numerical_result=ConformanceResult.UNKNOWN,
        )


def test_a_denied_bundle_carrying_a_widening_witness_is_rejected() -> None:
    with pytest.raises(ValidationError, match="ioc verdict"):
        CandidateConstruction(
            derivation=_denied_derivation(),
            denial_reason="denied",
            no_silent_widening_ok=True,
        )


# ---------------------------------------------------------------------------
# built-shape violations (command is not None)
# ---------------------------------------------------------------------------


def test_a_built_bundle_carrying_a_denial_reason_is_rejected() -> None:
    kwargs = _built_kwargs(_built())
    kwargs["denial_reason"] = "should not coexist with a command"
    with pytest.raises(ValidationError, match="denial_reason"):
        CandidateConstruction(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "missing_field",
    [
        "intent",
        "envelope",
        "policy",
        "conformance_result",
        "numerical_result",
        "no_silent_widening_ok",
    ],
)
def test_a_built_bundle_missing_a_required_field_is_rejected(
    missing_field: str,
) -> None:
    kwargs = _built_kwargs(_built())
    kwargs[missing_field] = None
    with pytest.raises(ValidationError, match="missing"):
        CandidateConstruction(**kwargs)  # type: ignore[arg-type]


def test_a_built_bundle_with_unknown_conformance_is_still_sanctioned() -> None:
    """UNKNOWN is a decided (non-None) ioc verdict value — the shape validator only demands
    presence, not a particular decided value; the gateway's own item-13 polarity handles what
    UNKNOWN means."""
    kwargs = _built_kwargs(_built())
    kwargs["conformance_result"] = ConformanceResult.UNKNOWN
    CandidateConstruction(**kwargs)  # type: ignore[arg-type]


def test_a_built_bundle_with_false_widening_witness_is_still_sanctioned() -> None:
    """``no_silent_widening_ok=False`` is a decided negative-polarity witness, not an absence —
    the validator must check ``is None``, never bare truthiness."""
    kwargs = _built_kwargs(_built())
    kwargs["no_silent_widening_ok"] = False
    CandidateConstruction(**kwargs)  # type: ignore[arg-type]
