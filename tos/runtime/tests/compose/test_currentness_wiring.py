"""Tests for :mod:`tos_runtime.compose._dimension_readers`'s late-bound dimension
readers (Phase 5 W3-b; module moved out of ``_currentness_wiring`` 2026-09-12 for
the size budget — this test file's own name is unchanged).

Covers W3.1 independent review MEDIUM-5 (mutation M9 survived): nothing pinned that a
not-yet-late-bound cell yields an ABSENT dimension (``None``) rather than a fabricated
positive. This is the single most load-bearing contract of these cells, and until now
it had no test — flipping ``_recovery_dimension_reader_for`` to return
``DimensionReport(positively_established=True)`` before the cell was filled left the
whole runtime suite green.
"""

from __future__ import annotations

import pytest
from tos.brokercap import (
    Admissibility,
    AssetScope,
    AuthorizationClass,
    BrokerEnvironment,
    CapabilityTuple,
    EconomicEffect,
    OperationClass,
    ProfileKey,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import MANDATED_DIMENSION_FLOOR, CurrentnessPolicy, DimensionKey
from tos.egressgw import TransportNature
from tos.sbr import ReadinessVerdict, RecoveryAuthorityEffect
from tos_runtime.brokercap.scopes import (
    BrokerScope,
    EndpointClass,
    PrincipalClass,
    ScopeInstanceBinding,
)
from tos_runtime.compose import _dimension_readers
from tos_runtime.compose._dimension_readers import (
    _currentness_policy_dimension_reader_for,
    _environment_scope_dimension_reader_for,
    _EnvironmentScopeDimensionState,
    _post_trade_dimension_reader_for,
    _PostTradeDimensionState,
    _recovery_dimension_reader_for,
    _RecoveryDimensionState,
    _release_dimension_reader_for,
    _ReleaseDimensionState,
)
from tos_runtime.recovery.barrier import RecoveryVerdict

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class _FakePostTradeConsumer:
    """Duck-typed double for ``FinalityReleaseConsumer`` — the reader only ever calls
    ``.latest_release_is_conflict_free()``."""

    def __init__(self, *, conflict_free: bool) -> None:
        self._conflict_free = conflict_free

    def latest_release_is_conflict_free(self) -> bool:
        return self._conflict_free


def _recovery_verdict(*, ready: bool) -> RecoveryVerdict:
    return RecoveryVerdict(
        readiness_verdict=(
            ReadinessVerdict.READY if ready else ReadinessVerdict.NOT_READY
        ),
        ready=ready,
        reason="test",
        possibly_live_reconciliation={},
        authority_effect=RecoveryAuthorityEffect(),
    )


# ============================================================================
# RECOVERY
# ============================================================================


def test_recovery_reader_is_none_before_the_cell_is_filled() -> None:
    """MEDIUM-5 / mutation M9: the honest pre-fill contract."""
    state = _RecoveryDimensionState()
    reader = _recovery_dimension_reader_for(state)
    assert reader() is None


def test_recovery_reader_reports_true_once_filled_with_a_ready_verdict() -> None:
    state = _RecoveryDimensionState()
    reader = _recovery_dimension_reader_for(state)
    state.verdict = _recovery_verdict(ready=True)
    report = reader()
    assert report is not None
    assert report.positively_established is True


def test_recovery_reader_reports_false_once_filled_with_a_not_ready_verdict() -> None:
    state = _RecoveryDimensionState()
    reader = _recovery_dimension_reader_for(state)
    state.verdict = _recovery_verdict(ready=False)
    report = reader()
    assert report is not None
    assert report.positively_established is False


# ============================================================================
# TRADING_APPROVAL
# ============================================================================


# ============================================================================
# ENVIRONMENT_SCOPE (W3.1 independent review MEDIUM-2 — three genuinely distinct
# sources instead of one variable read three times)
# ============================================================================


def _synthetic_scope() -> BrokerScope:
    """A non-broker-reaching scope (mirrors the compose root's own default
    SYNTHETIC_FUTURES_ORDER fixture scope) — no instance binding at all."""
    return BrokerScope(
        name="SYNTHETIC_TEST",
        capability_tuples=(
            CapabilityTuple(
                environment=BrokerEnvironment.SYNTHETIC,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.NONE,
                asset_scope=AssetScope.FUTURES,
                authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
            ),
        ),
        profile_key=ProfileKey(),
        principal_class=PrincipalClass.SYNTHETIC,
        principal="synthetic-test",
        endpoint_class=EndpointClass.SYNTHETIC,
        allowed_methods=("SUBMIT",),
        admissibility=Admissibility.ADMISSIBLE,
        provenance=(),
        inside_boundary=True,
        environment_binding={},
        asset_binding={},
        instance=None,
    )


def _broker_reaching_scope(
    *,
    instance: ScopeInstanceBinding | None,
    bound_environment: str | None = "MOCK_VTS",
) -> BrokerScope:
    return BrokerScope(
        name="MOCK_ORDER_TEST",
        capability_tuples=(
            CapabilityTuple(
                environment=BrokerEnvironment.BROKER_SIMULATION,
                operation_class=OperationClass.ORDER_SEND,
                economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
                asset_scope=AssetScope.STOCK,
                authorization_class=AuthorizationClass.MOCK_ORDER,
            ),
        ),
        profile_key=ProfileKey(),
        principal_class=PrincipalClass.ORDER,
        principal="kis-mock-order-test",
        endpoint_class=EndpointClass.BROKER_ORDER,
        allowed_methods=("SUBMIT",),
        admissibility=Admissibility.ADMISSIBLE,
        provenance=(),
        inside_boundary=True,
        environment_binding=(
            {BrokerEnvironment.BROKER_SIMULATION: bound_environment}
            if bound_environment is not None
            else {}
        ),
        asset_binding={},
        instance=instance,
    )


def test_environment_scope_reader_is_none_before_the_cell_is_filled() -> None:
    """MEDIUM-5 / mutation M9: the honest pre-fill contract, now also pinned for
    ENVIRONMENT_SCOPE's own late-bound cell."""
    state = _EnvironmentScopeDimensionState()
    reader = _environment_scope_dimension_reader_for("paper", state)
    assert reader() is None


def test_environment_scope_reader_is_vacuously_true_for_a_non_broker_reaching_scope() -> (
    None
):
    """A SYNTHETIC/NONE endpoint-class scope has no environment-binding evidence to
    check at all (mirrors derive_item6_item12's own item-12 "no generation exists to be
    stale" discipline) — never a fabricated comparison, and never a deny either."""
    state = _EnvironmentScopeDimensionState(active_scope=_synthetic_scope())
    reader = _environment_scope_dimension_reader_for("paper", state)
    report = reader()
    assert report is not None
    assert report.positively_established is True


def test_environment_scope_reader_is_true_when_the_instance_agrees_with_the_binding() -> (
    None
):
    state = _EnvironmentScopeDimensionState(
        active_scope=_broker_reaching_scope(
            instance=ScopeInstanceBinding(environment="MOCK_VTS"),
            bound_environment="MOCK_VTS",
        )
    )
    reader = _environment_scope_dimension_reader_for("paper", state)
    report = reader()
    assert report is not None
    assert report.positively_established is True


def test_environment_scope_reader_is_false_when_the_instance_disagrees_with_the_binding() -> (
    None
):
    state = _EnvironmentScopeDimensionState(
        active_scope=_broker_reaching_scope(
            instance=ScopeInstanceBinding(environment="REAL_PROD"),
            bound_environment="MOCK_VTS",
        )
    )
    reader = _environment_scope_dimension_reader_for("paper", state)
    report = reader()
    assert report is not None
    assert report.positively_established is False


def test_environment_scope_reader_is_false_when_a_broker_reaching_scope_has_no_instance() -> (
    None
):
    """A broker-reaching scope with no instance binding is a genuine gap — never
    papered over as established."""
    state = _EnvironmentScopeDimensionState(
        active_scope=_broker_reaching_scope(instance=None)
    )
    reader = _environment_scope_dimension_reader_for("paper", state)
    report = reader()
    assert report is not None
    assert report.positively_established is False


def test_environment_scope_reader_never_takes_the_vacuous_pass_on_an_unknown_reachability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """W3.1 independent review LOW-8: ``reaches_broker`` is typed ``bool | None`` on the
    kernel's own ``TransportNature`` — the reader's ``is False`` identity check must
    never let ``None`` (unknown reachability) fall into the vacuous-True branch meant
    only for a scope PROVEN not to reach a broker. Simulated via a monkeypatched
    ``transport_nature`` (the real runtime helper always derives a concrete bool from
    ``endpoint_class``, so this case cannot otherwise be driven through a real scope).
    """
    scope = _broker_reaching_scope(instance=None)
    monkeypatch.setattr(
        _dimension_readers,
        "transport_nature",
        lambda _scope: TransportNature(reaches_broker=None),
    )
    state = _EnvironmentScopeDimensionState(active_scope=scope)
    reader = _environment_scope_dimension_reader_for("paper", state)
    report = reader()
    assert report is not None
    # Falls through to the real (broker-reaching) check, which denies here (no
    # instance) -- never the vacuous True the SYNTHETIC/NONE branch would give.
    assert report.positively_established is False


# ============================================================================
# CURRENTNESS_POLICY (W3.1 independent review LOW-9 — the consumer-side pin MEDIUM-3's
# fix needed: an operator config that genuinely under-declares must genuinely deny)
# ============================================================================


def test_currentness_policy_reader_is_false_when_the_operator_config_under_declares() -> (
    None
):
    """MEDIUM-3 fixed the tautology by sourcing ``required_dimensions`` from operator
    config instead of ``MANDATED_DIMENSION_FLOOR`` itself -- this pins that an operator
    config missing one mandated key now genuinely flips the CURRENTNESS_POLICY
    dimension's ``positively_established`` to ``False``, never silently passing."""
    under_declared = tuple(
        key for key in MANDATED_DIMENSION_FLOOR if key is not DimensionKey.RELEASE
    )
    assert DimensionKey.RELEASE not in under_declared  # the missing mandated key
    policy = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="test-under-declared-policy",
        policy_generation=1,
        required_dimensions=under_declared,
    )
    assert isinstance(policy, CurrentnessPolicy)
    reader = _currentness_policy_dimension_reader_for(policy)
    report = reader()
    assert report is not None
    assert report.positively_established is False


def test_currentness_policy_reader_is_true_when_the_operator_config_covers_the_floor() -> (
    None
):
    policy = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="test-complete-policy",
        policy_generation=1,
        required_dimensions=tuple(
            sorted(MANDATED_DIMENSION_FLOOR, key=lambda k: k.value)
        ),
    )
    assert isinstance(policy, CurrentnessPolicy)
    reader = _currentness_policy_dimension_reader_for(policy)
    report = reader()
    assert report is not None
    assert report.positively_established is True


# ============================================================================
# AGGREGATE_RISK (Phase 5 W3.2, plan §2 decision 4)
# ============================================================================


# ============================================================================
# CONSTRUCTION (Phase 5 W3.2, plan §2 decision 3)
# ============================================================================


# ============================================================================
# CONSTRAINT (Phase 5 W3.2, plan §2 decisions 2/3)
# ============================================================================


# ============================================================================
# DECISION_PROOF_INTENT (Phase 5 W3.2, plan §2 decision 2)
# ============================================================================


# ============================================================================
# POST_TRADE (Phase 5 W3.2, plan §2 decision 5)
# ============================================================================


def test_post_trade_reader_is_none_when_no_consumer_was_ever_wired() -> None:
    """Distinct from "no evidence yet" (which the consumer itself resolves to True,
    module docstring) -- this is the "consumer literally does not exist" case."""
    state = _PostTradeDimensionState()
    reader = _post_trade_dimension_reader_for(state)
    assert reader() is None


def test_post_trade_reader_reports_true_for_a_first_attempt_with_no_conflict() -> None:
    """M2 discipline (plan §5): the first attempt has no post-trade fact at all, which
    the consumer itself resolves to True -- never False and never None."""
    state = _PostTradeDimensionState(
        consumer=_FakePostTradeConsumer(conflict_free=True)
    )
    reader = _post_trade_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 0


def test_post_trade_reader_reports_false_when_the_consumer_reports_a_conflict() -> None:
    state = _PostTradeDimensionState(
        consumer=_FakePostTradeConsumer(conflict_free=False)
    )
    reader = _post_trade_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is False


# ============================================================================
# RELEASE (Phase 5 W3.2, plan §2 decision 6)
# ============================================================================


def test_release_reader_is_none_before_the_cell_is_filled() -> None:
    state = _ReleaseDimensionState()
    reader = _release_dimension_reader_for(state)
    assert reader() is None


def test_release_reader_reports_true_once_boot_admitted_release() -> None:
    """Boot's own STAGE B probe always returns True when it returns at all (a refusal
    raises instead, module docstring) -- this pins the honest, non-invented mapping."""
    state = _ReleaseDimensionState(release_admitted=True)
    reader = _release_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 0
