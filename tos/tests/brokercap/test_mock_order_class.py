"""``mock_order_without_position_or_cash`` — PR-3 option (a), operator decision 2026-10-23.

The predicate is the whole relaxation boundary, so every axis gets a mutation: flipping the
environment to production, the economic effect to position/cash, or the authorization to a
real order must each turn it ``False``; so must an unknown or ``None`` axis (only reachable
through ``model_construct``, which bypasses the tuple's own validator).
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
    mock_order_without_position_or_cash,
)

_MOCK_SEND = CapabilityTuple(
    environment=BrokerEnvironment.BROKER_SIMULATION,
    operation_class=OperationClass.ORDER_SEND,
    economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
    asset_scope=AssetScope.STOCK,
    authorization_class=AuthorizationClass.MOCK_ORDER,
)
_MOCK_AMEND = _MOCK_SEND.model_copy(
    update={"operation_class": OperationClass.CANCEL_REPLACE}
)
_MOCK_READ = CapabilityTuple(
    environment=BrokerEnvironment.BROKER_SIMULATION,
    operation_class=OperationClass.ACCOUNT_READ,
    economic_effect=EconomicEffect.NONE,
    asset_scope=AssetScope.STOCK,
    authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
)


def _bypass(**update: Any) -> CapabilityTuple:
    """A tuple the validator never saw — the only way to hold a contradictory one."""
    return CapabilityTuple.model_construct(**{**_MOCK_SEND.model_dump(), **update})


def test_the_mock_stock_order_scope_is_admitted() -> None:
    """The shipped MOCK_STOCK_ORDER scope's two tuples, and the same with a read added."""
    assert mock_order_without_position_or_cash((_MOCK_SEND, _MOCK_AMEND))
    assert mock_order_without_position_or_cash((_MOCK_SEND, _MOCK_READ))


def test_an_empty_tuple_set_is_not_admitted() -> None:
    assert not mock_order_without_position_or_cash(())


@pytest.mark.parametrize(
    "mutated",
    [
        # environment -> production (the validator refuses a production FUTURES order, but a
        # production STOCK order constructs — it must still be refused here)
        _MOCK_SEND.model_copy(
            update={"environment": BrokerEnvironment.BROKER_PRODUCTION}
        ),
        _bypass(environment=BrokerEnvironment.BROKER_PRODUCTION),
        _bypass(environment=BrokerEnvironment.SYNTHETIC),
        # economic effect -> position/cash
        _MOCK_SEND.model_copy(
            update={"economic_effect": EconomicEffect.POSITION_OR_CASH}
        ),
        # authorization -> a real order
        _MOCK_SEND.model_copy(
            update={"authorization_class": AuthorizationClass.REAL_ORDER}
        ),
        _bypass(authorization_class=AuthorizationClass.SYNTHETIC_ORDER),
        # unknown / None axes
        _bypass(environment=None),
        _bypass(economic_effect=None),
        _bypass(authorization_class=None),
        _bypass(environment="BROKER_SIMULATION"),  # the string, not the enum member
        _bypass(economic_effect="NONE"),
        _bypass(authorization_class="MOCK_ORDER"),
    ],
)
def test_each_axis_mutation_is_refused(mutated: CapabilityTuple) -> None:
    assert not mock_order_without_position_or_cash((mutated,))
    # one bad tuple poisons the whole scope — "every tuple", not "any tuple"
    assert not mock_order_without_position_or_cash((_MOCK_SEND, mutated))


def test_a_non_tuple_member_is_refused() -> None:
    assert not mock_order_without_position_or_cash(
        (_MOCK_SEND, _MOCK_SEND.model_dump())  # type: ignore[arg-type]
    )
