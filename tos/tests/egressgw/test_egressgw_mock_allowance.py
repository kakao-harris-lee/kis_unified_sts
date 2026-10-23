"""Item 6 under PR-3 option (a) (operator decision 2026-10-23, "K").

A broker-resource-consuming send normally needs brokercap ``capability_admissible`` to be
``ADMISSIBLE`` — for the KIS MOCK_VTS draft profile it is ``PROHIBITED`` (no dimension
VERIFIED). Option (a) skips that check for a scope whose every tuple is a BROKER_SIMULATION
mock order / read with no position or cash effect, judged from the context's own tuples. The
runtime allowance flags still gate the verdict.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from tos.brokercap import (
    AssetScope,
    AuthorizationClass,
    BrokerCapabilityProfile,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
)
from tos.egressgw import SendBoundaryContext
from tos.egressgw.gateway import _check_allowance
from tos.egressgw.vocabulary import BrokerApplicability, VerifyOutcome

from ..brokercap._brokercap_strategies import issue_profile, live_scope, profile_key

#: A simulation-class profile (its own environment_class, a non-live scope) and a production
#: one. The profile key strings are opaque: nothing reads them to classify the profile.
_NON_LIVE = live_scope(mode="NON_LIVE", action_classes=())
_SIM_PROFILE = issue_profile(
    profile_key=profile_key(environment="SIM", instrument_class="EQ"),
    live_scope=_NON_LIVE,
    environment_class=BrokerEnvironment.BROKER_SIMULATION,
)
_PROD_PROFILE = issue_profile(
    profile_key=profile_key(environment="PROD", instrument_class="EQ"),
    live_scope=_NON_LIVE,
    environment_class=BrokerEnvironment.BROKER_PRODUCTION,
)
#: A production profile whose KEY strings say "SIM" — the key is never the classifier.
_PROD_PROFILE_NAMED_SIM = issue_profile(
    profile_key=profile_key(environment="SIM", instrument_class="EQ"),
    live_scope=_NON_LIVE,
    environment_class=BrokerEnvironment.BROKER_PRODUCTION,
)
_UNDECLARED_PROFILE = issue_profile(
    profile_key=profile_key(environment="SIM", instrument_class="EQ"),
    live_scope=_NON_LIVE,
)


_MOCK_SEND = CapabilityTuple(
    environment=BrokerEnvironment.BROKER_SIMULATION,
    operation_class=OperationClass.ORDER_SEND,
    economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
    asset_scope=AssetScope.STOCK,
    authorization_class=AuthorizationClass.MOCK_ORDER,
)


def _judge(
    tuples: tuple[CapabilityTuple, ...],
    *,
    applicability: BrokerApplicability = BrokerApplicability.BROKER_RESOURCE_CONSUMING,
    profile: BrokerCapabilityProfile | None = _SIM_PROFILE,
    **flags: Any,
) -> VerifyOutcome:
    # Any profile here has no VERIFIED dimension for an unset required set: the normal path
    # is PROHIBITED -> DENIED, so SATISFIED can only come from the mock-class skip.
    context = SendBoundaryContext(
        capability_tuples=tuples,
        broker_capability_profile=profile,
        account_instrument_action_allowed=flags.get("allowed", True),
        max_quantity_within_allowance=flags.get("max_qty", True),
    )
    return _check_allowance(None, context, applicability).outcome  # type: ignore[arg-type]


def test_the_mock_order_class_skips_the_profile_check() -> None:
    assert _judge((_MOCK_SEND,)) is VerifyOutcome.SATISFIED


def test_without_tuples_the_profile_check_still_denies() -> None:
    """Before option (a) every broker-consuming send took this path; it still does."""
    assert _judge(()) is VerifyOutcome.DENIED


@pytest.mark.parametrize(
    "mutated",
    [
        _MOCK_SEND.model_copy(
            update={"environment": BrokerEnvironment.BROKER_PRODUCTION}
        ),
        _MOCK_SEND.model_copy(
            update={"economic_effect": EconomicEffect.POSITION_OR_CASH}
        ),
        _MOCK_SEND.model_copy(
            update={"authorization_class": AuthorizationClass.REAL_ORDER}
        ),
        CapabilityTuple.model_construct(
            **{**_MOCK_SEND.model_dump(), "environment": None}
        ),
    ],
)
def test_a_real_money_or_unknown_tuple_takes_the_profile_check(
    mutated: CapabilityTuple,
) -> None:
    assert _judge((mutated,)) is VerifyOutcome.DENIED
    assert _judge((_MOCK_SEND, mutated)) is VerifyOutcome.DENIED


@pytest.mark.parametrize(
    "profile",
    [
        # #932 Codex r2: a production profile beside mock tuples — DENIED however it is named
        _PROD_PROFILE,
        _PROD_PROFILE_NAMED_SIM,
        # an undeclared class is never read as simulation; no profile, nothing to read
        _UNDECLARED_PROFILE,
        None,
    ],
)
def test_mock_tuples_beside_a_non_simulation_profile_take_the_profile_check(
    profile: BrokerCapabilityProfile | None,
) -> None:
    assert _judge((_MOCK_SEND,), profile=profile) is VerifyOutcome.DENIED


def test_no_send_time_context_field_can_classify_a_profile() -> None:
    """#932 Codex r2: the round-1 binding tables are gone — a context that tries to carry one
    (the bypass ``BROKER_SIMULATION -> "PROD"``) does not even construct."""
    with pytest.raises(ValidationError):
        SendBoundaryContext(
            capability_tuples=(_MOCK_SEND,),
            broker_capability_profile=_PROD_PROFILE,
            capability_environment_binding=(  # type: ignore[call-arg]
                (BrokerEnvironment.BROKER_SIMULATION, "PROD"),
            ),
        )


def test_a_simulation_read_tuple_beside_the_mock_send_still_skips() -> None:
    """A scope may also carry a non-authorizing read at the same simulation environment."""
    read = _MOCK_SEND.model_copy(
        update={
            "operation_class": OperationClass.ACCOUNT_READ,
            "economic_effect": EconomicEffect.NONE,
            "authorization_class": AuthorizationClass.NON_AUTHORIZING_READ,
        }
    )
    assert _judge((_MOCK_SEND, read)) is VerifyOutcome.SATISFIED


@pytest.mark.parametrize(
    ("flag", "value"), [("allowed", None), ("allowed", False), ("max_qty", None)]
)
def test_the_runtime_allowance_flags_still_gate_the_mock_class(
    flag: str, value: bool | None
) -> None:
    flags: dict[str, Any] = {flag: value}
    assert _judge((_MOCK_SEND,), **flags) is VerifyOutcome.UNKNOWN
