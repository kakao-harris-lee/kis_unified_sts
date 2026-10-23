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
from tos.brokercap import (
    AssetScope,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
)
from tos.egressgw import SendBoundaryContext
from tos.egressgw.gateway import _check_allowance
from tos.egressgw.vocabulary import BrokerApplicability, VerifyOutcome

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
    **flags: Any,
) -> VerifyOutcome:
    context = SendBoundaryContext(
        capability_tuples=tuples,
        # No profile at all: the normal path is PROHIBITED -> DENIED.
        broker_capability_profile=None,
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
    ("flag", "value"), [("allowed", None), ("allowed", False), ("max_qty", None)]
)
def test_the_runtime_allowance_flags_still_gate_the_mock_class(
    flag: str, value: bool | None
) -> None:
    flags: dict[str, Any] = {flag: value}
    assert _judge((_MOCK_SEND,), **flags) is VerifyOutcome.UNKNOWN
