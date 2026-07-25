"""Shared valid-artifact builders + strategies for the ioc property tests.

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #14 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 REJECT lesson):

* a **CONFORMANT** fixture has intent / command / envelope carrying the *same* concrete
  authorized axis value on every axis, so a CONFORMANT verdict is genuinely earned;
* a **NON_CONFORMANT** fixture flips one named axis (e.g. SIDE ``BUY`` -> ``SELL``) so the
  mismatch is a real, identified mismatch — the test states which axis;
* an **UNKNOWN** fixture drops one axis value to ``None`` (a genuine missing determination input);
* a **dominating** committed vector strictly exceeds the envelope on every governed dimension;
  an under-dominating one is strictly below on one dimension.

The reserved ``"TBD"`` placeholder is excluded from required-field text.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.ioc import (
    ApprovedIntentContract,
    AuthorizedConstructionEnvelope,
    AxisBinding,
    CanonicalBrokerCommand,
    ConformanceAxis,
    OrderConformanceProof,
    OrderConstructionPolicy,
)
from tos.rcl import CapacityComponent, CapacityVector

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Text bound to a required-covered field must be concrete (never the reserved ``"TBD"``).
REQUIRED_FIELD_TEXT = st.text(max_size=8).filter(lambda s: s != "TBD")
#: Injected ``bool | None`` flag (fail-closed on ``None`` / ``False``).
TRIBOOL = st.sampled_from([True, False, None])
#: A finite decimal magnitude (never NaN / infinity — those are unconstructable, §14 line 423).
FINITE_MAGNITUDE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: The authorized axis set used across the conformance tests (the identity + direction axes).
AUTHORIZED_AXES: dict[ConformanceAxis, str] = {
    ConformanceAxis.ENVIRONMENT: "PAPER",
    ConformanceAxis.ACCOUNT: "ACCT-1",
    ConformanceAxis.INSTRUMENT: "INSTR-1",
    ConformanceAxis.DIRECTION: "LONG",
    ConformanceAxis.SIDE: "BUY",
    ConformanceAxis.POSITION_EFFECT: "OPEN",
}


def _bindings(values: dict[ConformanceAxis, str | None]) -> tuple[AxisBinding, ...]:
    """Build a sorted tuple of :class:`AxisBinding` from an ``{axis: value}`` map."""
    return tuple(
        AxisBinding(axis=axis, value=values[axis])
        for axis in sorted(values, key=lambda a: a.value)
    )


# ---------------------------------------------------------------------------
# Digest-bound artifact builders
# ---------------------------------------------------------------------------


def issue_policy(**overrides: Any) -> OrderConstructionPolicy:
    """Issue a valid :class:`OrderConstructionPolicy` (all required covered fields concrete)."""
    base: dict[str, Any] = {
        "policy_id": "pol-1",
        "policy_generation": 1,
        "policy_version": "v1",
    }
    base.update(overrides)
    return OrderConstructionPolicy.issue(scheme=SCHEME, **base)


def issue_envelope(
    values: dict[ConformanceAxis, str | None] | None = None, **overrides: Any
) -> AuthorizedConstructionEnvelope:
    """Issue an envelope authorizing ``values`` (defaults to the full clean axis set)."""
    axis_values = dict(AUTHORIZED_AXES) if values is None else values
    base: dict[str, Any] = {
        "envelope_id": "env-1",
        "envelope_generation": 1,
        "authorized_axis_bindings": _bindings(axis_values),
        "policy_binding_id": "pol-1",
    }
    base.update(overrides)
    return AuthorizedConstructionEnvelope.issue(scheme=SCHEME, **base)


def issue_intent(
    values: dict[ConformanceAxis, str | None] | None = None, **overrides: Any
) -> ApprovedIntentContract:
    """Issue an intent authorizing ``values`` (defaults to the full clean axis set)."""
    axis_values = dict(AUTHORIZED_AXES) if values is None else values
    base: dict[str, Any] = {
        "intent_id": "int-1",
        "intent_generation": 1,
        "intent_version": "v1",
        "proposal_id": "prop-1",
        "proposal_digest": "prop-digest-1",
        "authorized_axis_bindings": _bindings(axis_values),
    }
    base.update(overrides)
    return ApprovedIntentContract.issue(scheme=SCHEME, **base)


def issue_command(
    values: dict[ConformanceAxis, str | None] | None = None, **overrides: Any
) -> CanonicalBrokerCommand:
    """Issue a command declaring ``values`` (defaults to the full clean axis set)."""
    axis_values = dict(AUTHORIZED_AXES) if values is None else values
    base: dict[str, Any] = {
        "command_id": "cmd-1",
        "command_generation": 1,
        "proposal_id": "prop-1",
        "proposal_digest": "prop-digest-1",
        "axis_bindings": _bindings(axis_values),
    }
    base.update(overrides)
    return CanonicalBrokerCommand.issue(scheme=SCHEME, **base)


def issue_proof(**overrides: Any) -> OrderConformanceProof:
    """Issue a valid :class:`OrderConformanceProof` (concrete generation)."""
    base: dict[str, Any] = {
        "proof_id": "proof-1",
        "proof_generation": 1,
    }
    base.update(overrides)
    return OrderConformanceProof.issue(scheme=SCHEME, **base)


# ---------------------------------------------------------------------------
# Value-model builders
# ---------------------------------------------------------------------------


def capacity_vector(
    dimension: str = "notional", magnitude: Decimal | None = Decimal("10")
) -> CapacityVector:
    """A one-dimension rcl :class:`~tos.rcl.CapacityVector` (for envelope / dominance checks)."""
    return CapacityVector(
        components=(CapacityComponent(dimension_id=dimension, magnitude=magnitude),)
    )
