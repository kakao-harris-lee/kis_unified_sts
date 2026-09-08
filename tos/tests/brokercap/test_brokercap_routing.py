"""Broker environment/operation capability axes + closed routing whitelist (plan §5).

Covers ``tos.brokercap.routing`` per the Phase 4 slice #1 plan
(``docs/plans/2026-09-07-tos-phase4-capability-axes-slice-plan.md`` §3, amended by the v1.2
§3-A review dispositions R-1..R-4): the 5 §5.1 axis StrEnums, the ``CapabilityTuple``
combined-contradiction validator (including the BROKER_PRODUCTION x
ORDER_SEND/CANCEL_REPLACE x FUTURES two-layer validated-construction seal — §3-A R-1), the
closed whitelist DERIVED from rules rather than transcribed from §5.2's use-case table
(§3-A R-2), and the two kernel-representable §5.3 routing-invariant predicates.

TDD: this file is authored *before* ``tos/src/tos/brokercap/routing.py`` exists, so the
first run is RED on the import (module not found) — expected per plan §3.6.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import hypothesis.strategies as st
import pydantic
import pytest
import tos.brokercap.routing as routing_module
from hypothesis import given, settings
from tos.brokercap import Admissibility, CapabilityDimension, ProfileKey
from tos.brokercap.routing import (
    AssetScope,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
    ProbeManifest,
    credential_principal_separation_ok,
    endpoint_binding_from_profile_ok,
    routing_admissibility,
)

# ---------------------------------------------------------------------------
# Enum member-count / verbatim pins (plan §5.1; slice plan §3.2)
# ---------------------------------------------------------------------------


def test_broker_environment_three_verbatim() -> None:
    """BrokerEnvironment is the 3 broker-agnostic tokens (slice plan §3 decision 2 — no
    concrete-broker mock/real example tokens in tos/)."""
    assert [e.value for e in BrokerEnvironment] == [
        "SYNTHETIC",
        "BROKER_SIMULATION",
        "BROKER_PRODUCTION",
    ]


def test_operation_class_five_verbatim() -> None:
    """OperationClass is the 5 plan §5.1 tokens verbatim."""
    assert [o.value for o in OperationClass] == [
        "MARKET_DATA_READ",
        "ACCOUNT_READ",
        "CAPABILITY_PROBE",
        "ORDER_SEND",
        "CANCEL_REPLACE",
    ]


def test_economic_effect_three_verbatim() -> None:
    """EconomicEffect is the 3 plan §5.1 tokens verbatim."""
    assert [e.value for e in EconomicEffect] == [
        "NONE",
        "BROKER_RESOURCE_ONLY",
        "POSITION_OR_CASH",
    ]


def test_asset_scope_two_verbatim() -> None:
    """AssetScope is the 2 plan §5.1 tokens verbatim."""
    assert [a.value for a in AssetScope] == ["STOCK", "FUTURES"]


def test_authorization_class_four_verbatim() -> None:
    """AuthorizationClass is the 3 plan §5.1 tokens plus the v1.1 correction's 4th member
    SYNTHETIC_ORDER (slice plan §3 decision 3, v1.1 정정 2026-09-07 — without it §5.2 row 1
    'synthetic backtest/fill' is unrepresentable, since rule 1 forbids ORDER_SEND with
    EconomicEffect.NONE and a synthetic fill has no economic effect by definition)."""
    assert [a.value for a in AuthorizationClass] == [
        "NON_AUTHORIZING_READ",
        "MOCK_ORDER",
        "REAL_ORDER",
        "SYNTHETIC_ORDER",
    ]


def test_capability_dimension_still_seventeen() -> None:
    """(slice plan §2 survey) The new routing module does not touch the ADR-002-004
    CapabilityDimension axis — the 17-member pin stays unchanged."""
    assert len(list(CapabilityDimension)) == 17


# ---------------------------------------------------------------------------
# CapabilityTuple — required axes, None disallowed
# ---------------------------------------------------------------------------


def _base_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "environment": BrokerEnvironment.SYNTHETIC,
        "operation_class": OperationClass.MARKET_DATA_READ,
        "economic_effect": EconomicEffect.NONE,
        "asset_scope": AssetScope.STOCK,
        "authorization_class": AuthorizationClass.NON_AUTHORIZING_READ,
    }
    base.update(overrides)
    return base


def test_capability_tuple_all_five_axes_required() -> None:
    """Every axis is required — a valid combination constructs cleanly."""
    tup = CapabilityTuple(**_base_kwargs())
    assert tup.environment is BrokerEnvironment.SYNTHETIC


@pytest.mark.parametrize(
    "axis",
    [
        "environment",
        "operation_class",
        "economic_effect",
        "asset_scope",
        "authorization_class",
    ],
)
def test_capability_tuple_rejects_none_axis(axis: str) -> None:
    """None is disallowed on every one of the 5 axes (plan §3 decision 3 — 'None 불허')."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(**_base_kwargs(**{axis: None}))


def test_capability_tuple_is_frozen() -> None:
    """A CapabilityTuple is immutable (FrozenModel discipline)."""
    tup = CapabilityTuple(**_base_kwargs())
    with pytest.raises(pydantic.ValidationError):
        tup.environment = BrokerEnvironment.BROKER_PRODUCTION  # type: ignore[misc]


def test_capability_tuple_extra_field_forbidden() -> None:
    """extra='forbid' — an unknown field is rejected."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(**_base_kwargs(), unexpected=1)  # type: ignore[call-arg]


def test_capability_tuple_hashable_for_whitelist_membership() -> None:
    """CapabilityTuple must be hashable — the whitelist is a frozenset (decision 4)."""
    a = CapabilityTuple(**_base_kwargs())
    b = CapabilityTuple(**_base_kwargs())
    assert a == b
    assert {a, b} == {a}


# ---------------------------------------------------------------------------
# CapabilityTuple — exhaustive contradiction matrix (negative; decision 3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "operation_class", [OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE]
)
def test_order_mutating_rejects_economic_effect_none(
    operation_class: OperationClass,
) -> None:
    """ORDER_SEND/CANCEL_REPLACE cannot coexist with EconomicEffect.NONE — except the v1.1
    SYNTHETIC x SYNTHETIC_ORDER exemption (covered separately below/row 1b)."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                operation_class=operation_class,
                economic_effect=EconomicEffect.NONE,
                authorization_class=AuthorizationClass.MOCK_ORDER,
                environment=BrokerEnvironment.BROKER_SIMULATION,
            )
        )


@pytest.mark.parametrize(
    "operation_class", [OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE]
)
def test_non_authorizing_read_rejects_order_mutating_operation(
    operation_class: OperationClass,
) -> None:
    """NON_AUTHORIZING_READ cannot coexist with ORDER_SEND/CANCEL_REPLACE."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                operation_class=operation_class,
                economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
                authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
                environment=BrokerEnvironment.BROKER_SIMULATION,
            )
        )


@pytest.mark.parametrize(
    "authorization_class",
    [AuthorizationClass.REAL_ORDER, AuthorizationClass.MOCK_ORDER],
)
def test_synthetic_environment_rejects_real_or_mock_order(
    authorization_class: AuthorizationClass,
) -> None:
    """SYNTHETIC environment cannot coexist with REAL_ORDER/MOCK_ORDER."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                environment=BrokerEnvironment.SYNTHETIC,
                authorization_class=authorization_class,
            )
        )


@pytest.mark.parametrize(
    "operation_class", [OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE]
)
@pytest.mark.parametrize(
    "authorization_class",
    [AuthorizationClass.REAL_ORDER, AuthorizationClass.MOCK_ORDER],
)
def test_broker_production_order_mutating_futures_rejected_by_validated_construction(
    operation_class: OperationClass, authorization_class: AuthorizationClass
) -> None:
    """(§3-A R-1) BROKER_PRODUCTION x ORDER_SEND/CANCEL_REPLACE x FUTURES is rejected by
    *validated* construction — layer ① of the two-layer seal (root CLAUDE.md non-negotiable:
    the real futures account is never funded; real futures order paths are policy-blocked).
    Layer ②'s bypass-proof half is pinned separately below (``model_construct`` /
    ``model_copy(update=...)`` skip this validator, so the closed whitelist is what still
    denies a bypass-constructed tuple)."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                environment=BrokerEnvironment.BROKER_PRODUCTION,
                operation_class=operation_class,
                economic_effect=EconomicEffect.POSITION_OR_CASH,
                asset_scope=AssetScope.FUTURES,
                authorization_class=authorization_class,
            )
        )


@pytest.mark.parametrize(
    "environment",
    [BrokerEnvironment.BROKER_SIMULATION, BrokerEnvironment.BROKER_PRODUCTION],
)
def test_synthetic_order_rejects_non_synthetic_environment(
    environment: BrokerEnvironment,
) -> None:
    """(v1.1 rule 3′) SYNTHETIC_ORDER cannot coexist with any non-SYNTHETIC environment —
    a synthetic (non-authoritative) fill is only meaningful inside the SYNTHETIC
    environment."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                environment=environment,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
                authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
            )
        )


def test_synthetic_order_send_none_mock_order_still_rejected() -> None:
    """(rule 3, unchanged by v1.1) SYNTHETIC x ORDER_SEND x NONE x MOCK_ORDER stays
    rejected — the v1.1 rule-1 exemption is scoped to SYNTHETIC_ORDER only, and rule 3
    (SYNTHETIC environment cannot coexist with REAL_ORDER/MOCK_ORDER) still independently
    fires for MOCK_ORDER."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                environment=BrokerEnvironment.SYNTHETIC,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.NONE,
                authorization_class=AuthorizationClass.MOCK_ORDER,
            )
        )


def test_synthetic_order_send_none_non_authorizing_read_still_rejected() -> None:
    """(rule 2, unchanged by v1.1) SYNTHETIC x ORDER_SEND x NONE x NON_AUTHORIZING_READ
    stays rejected — the v1.1 rule-1 exemption is scoped to SYNTHETIC_ORDER only, and rule 2
    (NON_AUTHORIZING_READ cannot coexist with ORDER_SEND/CANCEL_REPLACE) still independently
    fires."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityTuple(
            **_base_kwargs(
                environment=BrokerEnvironment.SYNTHETIC,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.NONE,
                authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
            )
        )


def test_synthetic_synthetic_order_exempt_from_economic_effect_none_rule() -> None:
    """(v1.1 rule 1 exemption, positive) SYNTHETIC x ORDER_SEND/CANCEL_REPLACE x NONE x
    SYNTHETIC_ORDER constructs cleanly — a synthetic fill has no economic effect by
    definition (§5.2 row 1b)."""
    for operation_class in (OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE):
        for asset_scope in AssetScope:
            tup = CapabilityTuple(
                environment=BrokerEnvironment.SYNTHETIC,
                operation_class=operation_class,
                economic_effect=EconomicEffect.NONE,
                asset_scope=asset_scope,
                authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
            )
            assert tup.authorization_class is AuthorizationClass.SYNTHETIC_ORDER


# ---------------------------------------------------------------------------
# routing_admissibility — closed whitelist DERIVED from rules (positive; §3-A R-2)
#
# §5.2 is a use-case table, not an exhaustive routing matrix (review finding accepted).
# The rows below are reconstructed as the derived rules' own extension — independently of
# routing.py's private whitelist constants (anti-phantom: this test does not import
# routing's private sets) — so a bidirectional hypothesis test can compare "the rule admits
# it" against "routing_admissibility says ADMISSIBLE/REDUCED" without circularity.
# ---------------------------------------------------------------------------

_READ_CLASS_OPERATIONS = (
    OperationClass.MARKET_DATA_READ,
    OperationClass.ACCOUNT_READ,
    OperationClass.CAPABILITY_PROBE,
)
_ORDER_MUTATING_OPS = (OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE)


def _read_class_rule_admits(tup: CapabilityTuple) -> bool:
    """(§3-A R-2) Read never authorizes an order: any environment, any of the three
    read-class operations, no economic effect, either asset, NON_AUTHORIZING_READ."""
    return (
        tup.operation_class in _READ_CLASS_OPERATIONS
        and tup.economic_effect is EconomicEffect.NONE
        and tup.authorization_class is AuthorizationClass.NON_AUTHORIZING_READ
    )


def _synthetic_order_rule_admits(tup: CapabilityTuple) -> bool:
    """(§3-A R-2, v1.1 unchanged) A synthetic fill has no economic effect by definition:
    SYNTHETIC x {ORDER_SEND, CANCEL_REPLACE} x NONE x either asset x SYNTHETIC_ORDER."""
    return (
        tup.environment is BrokerEnvironment.SYNTHETIC
        and tup.operation_class in _ORDER_MUTATING_OPS
        and tup.economic_effect is EconomicEffect.NONE
        and tup.authorization_class is AuthorizationClass.SYNTHETIC_ORDER
    )


def _mock_stock_order_rule_admits(tup: CapabilityTuple) -> bool:
    """(§3-A R-2, upstream plan §5.2 row 3 + §6 Phase 3 작업 5 cancel-replace join)
    BROKER_SIMULATION x {ORDER_SEND, CANCEL_REPLACE} x BROKER_RESOURCE_ONLY x STOCK x
    MOCK_ORDER — the REDUCED-ceiling rule (evidence-gated separately)."""
    return (
        tup.environment is BrokerEnvironment.BROKER_SIMULATION
        and tup.operation_class in _ORDER_MUTATING_OPS
        and tup.economic_effect is EconomicEffect.BROKER_RESOURCE_ONLY
        and tup.asset_scope is AssetScope.STOCK
        and tup.authorization_class is AuthorizationClass.MOCK_ORDER
    )


#: The read-class rule's extension: 3 environments x 3 operations x 2 assets = 18 tuples.
_SANCTIONED_READ_CLASS = [
    CapabilityTuple(
        environment=environment,
        operation_class=operation,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )
    for environment in BrokerEnvironment
    for operation in _READ_CLASS_OPERATIONS
    for asset in AssetScope
]

#: The synthetic-order rule's extension: 1 environment x 2 operations x 2 assets = 4 tuples.
_SANCTIONED_SYNTHETIC_ORDER = [
    CapabilityTuple(
        environment=BrokerEnvironment.SYNTHETIC,
        operation_class=operation,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
    )
    for operation in _ORDER_MUTATING_OPS
    for asset in AssetScope
]

#: The full ADMISSIBLE extension: 18 + 4 = 22 tuples (§3-A R-2 explicit pin).
_SANCTIONED_ADMISSIBLE = _SANCTIONED_READ_CLASS + _SANCTIONED_SYNTHETIC_ORDER

#: The MOCK-stock-order rule's extension: 1 environment x 2 operations x 1 asset = 2 tuples.
_SANCTIONED_REDUCED = [
    CapabilityTuple(
        environment=BrokerEnvironment.BROKER_SIMULATION,
        operation_class=operation,
        economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.MOCK_ORDER,
    )
    for operation in _ORDER_MUTATING_OPS
]


def test_admissible_and_reduced_counts_pinned() -> None:
    """(§3-A R-2 explicit pin) 18 (read-class: 3 envs x 3 ops x 2 assets) + 4
    (synthetic-order: 1 env x 2 ops x 2 assets) = 22 ADMISSIBLE; 2 (MOCK stock order: 1 env
    x 2 ops x 1 asset) REDUCED."""
    assert len(_SANCTIONED_ADMISSIBLE) == 22
    assert len(set(_SANCTIONED_ADMISSIBLE)) == 22  # no accidental duplicate tuple
    assert len(_SANCTIONED_REDUCED) == 2
    assert len(set(_SANCTIONED_REDUCED)) == 2


@pytest.mark.parametrize("tup", _SANCTIONED_ADMISSIBLE)
def test_sanctioned_rows_are_admissible(tup: CapabilityTuple) -> None:
    """The read-class rule and the synthetic-order rule are unconditionally ADMISSIBLE."""
    assert routing_admissibility(tup) is Admissibility.ADMISSIBLE
    # profile_evidence_ok is irrelevant to the unconditional rules.
    assert (
        routing_admissibility(tup, profile_evidence_ok=False)
        is Admissibility.ADMISSIBLE
    )


@pytest.mark.parametrize("tup", _SANCTIONED_REDUCED)
def test_mock_stock_order_rule_is_reduced_only_when_evidence_ok(
    tup: CapabilityTuple,
) -> None:
    """The MOCK-stock-order rule (both ORDER_SEND and CANCEL_REPLACE — §3-A R-2's
    cancel-replace join) admits at the REDUCED ceiling, and only when profile_evidence_ok is
    positively True — None/False stay PROHIBITED (fail-closed)."""
    assert routing_admissibility(tup, profile_evidence_ok=True) is Admissibility.REDUCED
    assert (
        routing_admissibility(tup, profile_evidence_ok=False)
        is Admissibility.PROHIBITED
    )
    assert (
        routing_admissibility(tup, profile_evidence_ok=None) is Admissibility.PROHIBITED
    )
    assert routing_admissibility(tup) is Admissibility.PROHIBITED


def test_real_broker_production_order_has_no_rule_stock_or_futures() -> None:
    """No derived rule ever admits a BROKER_PRODUCTION order tuple — not even for STOCK
    (§3-A R-2: the upstream plan has no real-stock-order row either; a review-confirmed
    finding). FUTURES is additionally excluded by the validated-construction seal (rule 4).
    """
    stock_real_order = CapabilityTuple(
        environment=BrokerEnvironment.BROKER_PRODUCTION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.POSITION_OR_CASH,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.REAL_ORDER,
    )
    assert routing_admissibility(stock_real_order) is Admissibility.PROHIBITED
    assert (
        routing_admissibility(stock_real_order, profile_evidence_ok=True)
        is Admissibility.PROHIBITED
    )


# ---------------------------------------------------------------------------
# routing_admissibility — bypass-proof layer ② of the R-1 validated-construction seal
# ---------------------------------------------------------------------------


def test_model_construct_bypass_of_rule_4_is_still_prohibited_by_the_whitelist() -> (
    None
):
    """(§3-A R-1, layer ②) ``model_construct`` skips every validator, including rule 4 — but
    the resulting BROKER_PRODUCTION x ORDER_SEND x FUTURES tuple is still not a member of
    any whitelist, so routing_admissibility still returns PROHIBITED."""
    bypassed = CapabilityTuple.model_construct(
        environment=BrokerEnvironment.BROKER_PRODUCTION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.POSITION_OR_CASH,
        asset_scope=AssetScope.FUTURES,
        authorization_class=AuthorizationClass.REAL_ORDER,
    )
    assert routing_admissibility(bypassed) is Admissibility.PROHIBITED
    assert (
        routing_admissibility(bypassed, profile_evidence_ok=True)
        is Admissibility.PROHIBITED
    )


def test_model_copy_update_bypass_of_rule_4_is_still_prohibited_by_the_whitelist() -> (
    None
):
    """(§3-A R-1, layer ②) ``model_copy(update=...)`` also skips validators. Starting from a
    *legally constructed* STOCK real-order tuple and updating only ``asset_scope`` to
    FUTURES produces the same rule-4-violating tuple without ever calling the validator —
    the closed whitelist is still what denies it."""
    legal = CapabilityTuple(
        environment=BrokerEnvironment.BROKER_PRODUCTION,
        operation_class=OperationClass.ORDER_SEND,
        economic_effect=EconomicEffect.POSITION_OR_CASH,
        asset_scope=AssetScope.STOCK,
        authorization_class=AuthorizationClass.REAL_ORDER,
    )
    bypassed = legal.model_copy(update={"asset_scope": AssetScope.FUTURES})
    assert bypassed.asset_scope is AssetScope.FUTURES  # the bypass actually took effect
    assert routing_admissibility(bypassed) is Admissibility.PROHIBITED
    assert (
        routing_admissibility(bypassed, profile_evidence_ok=True)
        is Admissibility.PROHIBITED
    )


def test_probe_manifest_model_construct_bypasses_the_literal_seal() -> None:
    """(§3-A R-1) ``ProbeManifest`` is record-shape-only with no consumer (slice plan §3
    decision 5.iv) — its ``Literal[False]`` seal on ``emits_orders`` is a *validated*-
    construction guarantee like ``CapabilityTuple``'s rule 4, and the same library-global
    bypass applies: ``model_construct`` can still produce a manifest claiming
    ``emits_orders=True``. Documented here because there is no whitelist-style second layer
    for this record (no consumer exists yet to enforce it) — the limitation is real, not
    hidden."""
    bypassed = ProbeManifest.model_construct(
        emits_orders=True,
        allowed_methods=("GET",),
        retention="180d",
        ttl="24h",
        provenance="official-spec",
    )
    assert bypassed.emits_orders is True


# ---------------------------------------------------------------------------
# routing_admissibility — bidirectional agreement with the derived rules (hypothesis)
# ---------------------------------------------------------------------------

_ENV_ST = st.sampled_from(list(BrokerEnvironment))
_OP_ST = st.sampled_from(list(OperationClass))
_ECO_ST = st.sampled_from(list(EconomicEffect))
_ASSET_ST = st.sampled_from(list(AssetScope))
_AUTH_ST = st.sampled_from(list(AuthorizationClass))


@given(
    environment=_ENV_ST,
    operation_class=_OP_ST,
    economic_effect=_ECO_ST,
    asset_scope=_ASSET_ST,
    authorization_class=_AUTH_ST,
)
@settings(max_examples=1000)
def test_derived_rules_agree_with_routing_admissibility_bidirectionally(
    environment: BrokerEnvironment,
    operation_class: OperationClass,
    economic_effect: EconomicEffect,
    asset_scope: AssetScope,
    authorization_class: AuthorizationClass,
) -> None:
    """(hypothesis, §3-A R-2 bidirectional check) Over the full 5-axis product: a derived
    rule admits a tuple IFF routing_admissibility reports the matching verdict for it — not
    just "whitelist => rule" (the old one-directional check) but "rule => whitelist" too, so
    a rule and the whitelist it builds cannot silently drift apart. Also re-confirms that no
    constructible tuple ever carries BROKER_PRODUCTION x ORDER_SEND/CANCEL_REPLACE x
    FUTURES (rule 4)."""
    try:
        tup = CapabilityTuple(
            environment=environment,
            operation_class=operation_class,
            economic_effect=economic_effect,
            asset_scope=asset_scope,
            authorization_class=authorization_class,
        )
    except pydantic.ValidationError:
        return  # structurally unrepresentable — not a routing case
    assert not (
        environment is BrokerEnvironment.BROKER_PRODUCTION
        and operation_class in _ORDER_MUTATING_OPS
        and asset_scope is AssetScope.FUTURES
    )
    admissible_by_rule = _read_class_rule_admits(tup) or _synthetic_order_rule_admits(
        tup
    )
    reduced_by_rule = _mock_stock_order_rule_admits(tup)
    assert admissible_by_rule == (
        routing_admissibility(tup) is Admissibility.ADMISSIBLE
    )
    assert reduced_by_rule == (
        routing_admissibility(tup, profile_evidence_ok=True) is Admissibility.REDUCED
    )
    if not admissible_by_rule and not reduced_by_rule:
        assert routing_admissibility(tup) is Admissibility.PROHIBITED
        assert (
            routing_admissibility(tup, profile_evidence_ok=True)
            is Admissibility.PROHIBITED
        )


# ---------------------------------------------------------------------------
# endpoint_binding_from_profile_ok — §5.3 (i); polarity None => False
# ---------------------------------------------------------------------------


def _binding_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "capability_tuple": CapabilityTuple(**_base_kwargs()),
        "profile_key": ProfileKey(
            environment="synthetic-env", instrument_class="stock"
        ),
        "environment_binding": {BrokerEnvironment.SYNTHETIC: "synthetic-env"},
        "asset_binding": {AssetScope.STOCK: "stock"},
    }
    base.update(overrides)
    return base


def test_endpoint_binding_matches() -> None:
    assert endpoint_binding_from_profile_ok(**_binding_kwargs()) is True


def test_endpoint_binding_profile_key_none_is_false() -> None:
    assert (
        endpoint_binding_from_profile_ok(**_binding_kwargs(profile_key=None)) is False
    )


def test_endpoint_binding_missing_environment_binding_entry_is_false() -> None:
    assert (
        endpoint_binding_from_profile_ok(**_binding_kwargs(environment_binding={}))
        is False
    )


def test_endpoint_binding_missing_asset_binding_entry_is_false() -> None:
    assert (
        endpoint_binding_from_profile_ok(**_binding_kwargs(asset_binding={})) is False
    )


def test_endpoint_binding_profile_key_environment_none_is_false() -> None:
    assert (
        endpoint_binding_from_profile_ok(
            **_binding_kwargs(
                profile_key=ProfileKey(environment=None, instrument_class="stock")
            )
        )
        is False
    )


def test_endpoint_binding_profile_key_instrument_class_none_is_false() -> None:
    assert (
        endpoint_binding_from_profile_ok(
            **_binding_kwargs(
                profile_key=ProfileKey(
                    environment="synthetic-env", instrument_class=None
                )
            )
        )
        is False
    )


def test_endpoint_binding_mismatch_is_false() -> None:
    assert (
        endpoint_binding_from_profile_ok(
            **_binding_kwargs(
                profile_key=ProfileKey(
                    environment="wrong-env", instrument_class="stock"
                )
            )
        )
        is False
    )


# ---------------------------------------------------------------------------
# credential_principal_separation_ok — §5.3 (ii); polarity
# ---------------------------------------------------------------------------


def test_credential_separation_distinct_nonempty_is_true() -> None:
    assert credential_principal_separation_ok("reader-1", "trader-1") is True


@pytest.mark.parametrize(
    ("read_principal", "order_principal"),
    [
        (None, None),
        (None, "trader-1"),
        ("reader-1", None),
        ("", "trader-1"),
        ("reader-1", ""),
        ("same-principal", "same-principal"),
        ("", ""),
    ],
)
def test_credential_separation_fails_closed(
    read_principal: str | None, order_principal: str | None
) -> None:
    assert credential_principal_separation_ok(read_principal, order_principal) is False


# ---------------------------------------------------------------------------
# ProbeManifest — record shape only (decision 5.iv), no consumer
# ---------------------------------------------------------------------------


def test_probe_manifest_emits_orders_locked_false() -> None:
    manifest = ProbeManifest(
        allowed_methods=("GET",),
        retention="180d",
        ttl="24h",
        provenance="official-spec",
    )
    assert manifest.emits_orders is False


def test_probe_manifest_emits_orders_cannot_be_true() -> None:
    """emits_orders: Literal[False] structurally seals a probe from ever claiming to emit
    orders (mirrors the UncertainSendVerdict all-restrictive-ladder pattern)."""
    with pytest.raises(pydantic.ValidationError):
        ProbeManifest(
            emits_orders=True,  # type: ignore[arg-type]
            allowed_methods=("GET",),
            retention="180d",
            ttl="24h",
            provenance="official-spec",
        )


@pytest.mark.parametrize(
    "missing", ["allowed_methods", "retention", "ttl", "provenance"]
)
def test_probe_manifest_requires_every_descriptive_field(missing: str) -> None:
    kwargs: dict[str, object] = {
        "allowed_methods": ("GET",),
        "retention": "180d",
        "ttl": "24h",
        "provenance": "official-spec",
    }
    del kwargs[missing]
    with pytest.raises(pydantic.ValidationError):
        ProbeManifest(**kwargs)


def test_probe_manifest_is_frozen() -> None:
    manifest = ProbeManifest(
        allowed_methods=("GET",),
        retention="180d",
        ttl="24h",
        provenance="official-spec",
    )
    with pytest.raises(pydantic.ValidationError):
        manifest.ttl = "48h"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# (iii) 'unsupported_is_deny' absence lock — negative-grep, no rewrite-to-REAL function
# ---------------------------------------------------------------------------


def test_no_public_function_returns_a_capability_tuple() -> None:
    """(slice plan §3 decision 5.iii) 'MOCK 미지원은 UNSUPPORTED/DENY다. 같은 요청을 REAL order
    endpoint로 재작성하지 않는다' is represented by *absence*: no function in routing.py takes
    a tuple and hands back a (possibly rewritten) CapabilityTuple at all. If a future edit adds
    one, this regression test forces an explicit, reviewed justification."""
    offenders: list[str] = []
    for name, obj in inspect.getmembers(routing_module, inspect.isfunction):
        if obj.__module__ != routing_module.__name__ or name.startswith("_"):
            continue
        hints = get_type_hints(obj)
        if hints.get("return") is CapabilityTuple:
            offenders.append(name)
    assert offenders == [], (
        "routing.py must not author a function returning CapabilityTuple — the "
        f"'no rewrite to REAL' absence lock (decision 5.iii): {offenders}"
    )


def test_no_public_function_takes_and_returns_capability_tuple() -> None:
    """Stronger absence check: no public routing.py function's signature is (..., tuple,
    ...) -> tuple at all — the narrowest form a 'rewrite' function could take."""
    offenders: list[str] = []
    for name, obj in inspect.getmembers(routing_module, inspect.isfunction):
        if obj.__module__ != routing_module.__name__ or name.startswith("_"):
            continue
        hints = get_type_hints(obj)
        takes_tuple = any(
            value is CapabilityTuple for key, value in hints.items() if key != "return"
        )
        returns_tuple = hints.get("return") is CapabilityTuple
        if takes_tuple and returns_tuple:
            offenders.append(name)
    assert offenders == [], f"a tuple-in/tuple-out rewrite function exists: {offenders}"
