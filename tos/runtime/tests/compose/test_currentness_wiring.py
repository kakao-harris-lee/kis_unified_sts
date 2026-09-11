"""Tests for :mod:`tos_runtime.compose._currentness_wiring`'s late-bound dimension
readers (Phase 5 W3-b).

Covers W3.1 independent review MEDIUM-5 (mutation M9 survived): nothing pinned that a
not-yet-late-bound cell yields an ABSENT dimension (``None``) rather than a fabricated
positive. This is the single most load-bearing contract of these cells, and until now
it had no test — flipping ``_recovery_dimension_reader_for`` to return
``DimensionReport(positively_established=True)`` before the cell was filled left the
whole runtime suite green.
"""

from __future__ import annotations

import types
from typing import Any

import pytest
from tos.are import RiskDecisionResult
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
from tos.engine import StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.ioc import ConformanceResult
from tos.sbr import ReadinessVerdict, RecoveryAuthorityEffect
from tos_runtime.brokercap.scopes import (
    BrokerScope,
    EndpointClass,
    PrincipalClass,
    ScopeInstanceBinding,
)
from tos_runtime.compose import _currentness_wiring
from tos_runtime.compose._currentness_wiring import (
    _aggregate_risk_dimension_reader_for,
    _constraint_dimension_reader_for,
    _ConstraintDimensionState,
    _construction_dimension_reader_for,
    _ConstructionDimensionState,
    _currentness_policy_dimension_reader_for,
    _decision_proof_intent_dimension_reader_for,
    _DecisionProofIntentDimensionState,
    _environment_scope_dimension_reader_for,
    _EnvironmentScopeDimensionState,
    _post_trade_dimension_reader_for,
    _PostTradeDimensionState,
    _recovery_dimension_reader_for,
    _RecoveryDimensionState,
    _release_dimension_reader_for,
    _ReleaseDimensionState,
    _trading_approval_dimension_reader_for,
    _TradingApprovalDimensionState,
)
from tos_runtime.compose.context import VerdictRecorder
from tos_runtime.recovery.barrier import RecoveryVerdict

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _bind_verification_verdict(outcome: StageOutcome) -> StageVerdict:
    return StageVerdict(
        step=CommitmentStep.ATTEMPT_BIND_VERIFICATION,
        outcome=outcome,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
    )


def _venue_verdict(outcome: StageOutcome) -> StageVerdict:
    return StageVerdict(
        step=CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
        outcome=outcome,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
    )


class _FakeRiskService:
    """Duck-typed double for ``RecordingAggregateRiskService`` — the reader only ever
    reads ``.last_decision``, so this stub carries nothing else (mirrors this test
    module's own ``_stage_verdict``/``VerdictRecorder`` doubles above)."""

    def __init__(self) -> None:
        self.last_decision: Any = None


def _aggregate_risk_decision(
    *, result: RiskDecisionResult, decision_generation: int
) -> types.SimpleNamespace:
    """A minimal stand-in for ``tos.are.AggregateRiskDecision`` carrying only the two
    fields :func:`_aggregate_risk_dimension_reader_for` reads."""
    return types.SimpleNamespace(result=result, decision_generation=decision_generation)


def _candidate_construction(
    *,
    conformance_result: ConformanceResult | None,
    numerical_result: ConformanceResult | None,
    no_silent_widening_ok: bool | None,
) -> types.SimpleNamespace:
    """A minimal stand-in for ``tos.egressgw.CandidateConstruction`` carrying only the
    three fields :func:`_construction_dimension_reader_for` reads."""
    return types.SimpleNamespace(
        conformance_result=conformance_result,
        numerical_result=numerical_result,
        no_silent_widening_ok=no_silent_widening_ok,
    )


class _FakeConstructionStage:
    """Duck-typed double for ``tos.egressgw.OrderConstructionStage`` — the reader only
    ever reads ``.construction``."""

    def __init__(self, construction: Any = None) -> None:
        self.construction = construction


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


def _stage_verdict(outcome: StageOutcome) -> StageVerdict:
    return StageVerdict(
        step=CommitmentStep.INDEPENDENT_APPROVAL,
        outcome=outcome,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
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


def test_trading_approval_reader_is_none_before_the_cell_is_filled() -> None:
    """MEDIUM-5 / mutation M9: the honest pre-fill contract."""
    state = _TradingApprovalDimensionState()
    reader = _trading_approval_dimension_reader_for(state)
    assert reader() is None


def test_trading_approval_reader_is_none_when_the_recorder_has_no_verdict_yet() -> None:
    """Filled with a real recorder, but that recorder has not yet recorded anything —
    still honestly absent, not a fabricated positive."""
    state = _TradingApprovalDimensionState()
    reader = _trading_approval_dimension_reader_for(state)
    state.step4_recorder = VerdictRecorder(
        lambda _request: _stage_verdict(StageOutcome.ADMIT)
    )
    assert reader() is None


def test_trading_approval_reader_reports_true_after_an_admit_verdict() -> None:
    state = _TradingApprovalDimensionState()
    reader = _trading_approval_dimension_reader_for(state)
    recorder = VerdictRecorder(lambda _request: _stage_verdict(StageOutcome.ADMIT))
    recorder(None)  # populate .last_verdict
    state.step4_recorder = recorder
    report = reader()
    assert report is not None
    assert report.positively_established is True


def test_trading_approval_reader_reports_false_after_a_deny_verdict() -> None:
    state = _TradingApprovalDimensionState()
    reader = _trading_approval_dimension_reader_for(state)
    recorder = VerdictRecorder(lambda _request: _stage_verdict(StageOutcome.DENY))
    recorder(None)
    state.step4_recorder = recorder
    report = reader()
    assert report is not None
    assert report.positively_established is False


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
        _currentness_wiring,
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


def test_aggregate_risk_reader_is_none_before_any_decision() -> None:
    """Mutation M9 discipline (module docstring): no decision recorded yet is honestly
    absent, never a fabricated positive."""
    reader = _aggregate_risk_dimension_reader_for(_FakeRiskService())
    assert reader() is None


def test_aggregate_risk_reader_reports_true_and_a_real_generation_after_grant() -> None:
    service = _FakeRiskService()
    reader = _aggregate_risk_dimension_reader_for(service)
    service.last_decision = _aggregate_risk_decision(
        result=RiskDecisionResult.GRANT, decision_generation=7
    )
    report = reader()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 7


@pytest.mark.parametrize(
    "result", [RiskDecisionResult.DENY, RiskDecisionResult.UNKNOWN]
)
def test_aggregate_risk_reader_reports_false_for_non_grant_results(
    result: RiskDecisionResult,
) -> None:
    """Positive-identity check (``is GRANT``), never truthiness -- DENY and UNKNOWN both
    deny."""
    service = _FakeRiskService()
    reader = _aggregate_risk_dimension_reader_for(service)
    service.last_decision = _aggregate_risk_decision(
        result=result, decision_generation=1
    )
    report = reader()
    assert report is not None
    assert report.positively_established is False


# ============================================================================
# CONSTRUCTION (Phase 5 W3.2, plan §2 decision 3)
# ============================================================================


def test_construction_reader_is_none_before_the_cell_is_filled() -> None:
    state = _ConstructionDimensionState()
    reader = _construction_dimension_reader_for(state)
    assert reader() is None


def test_construction_reader_is_none_before_step_2_has_a_candidate() -> None:
    state = _ConstructionDimensionState(construction_stage=_FakeConstructionStage())
    reader = _construction_dimension_reader_for(state)
    assert reader() is None


def test_construction_reader_reports_true_when_all_three_ioc_verdicts_are_positive() -> (
    None
):
    stage = _FakeConstructionStage(
        _candidate_construction(
            conformance_result=ConformanceResult.CONFORMANT,
            numerical_result=ConformanceResult.CONFORMANT,
            no_silent_widening_ok=True,
        )
    )
    state = _ConstructionDimensionState(construction_stage=stage)
    reader = _construction_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is True
    # M1 discipline (plan §5): a real, disclosed 0 -- never an invented per-attempt
    # counter this reader has no honest source for.
    assert report.bound_generation == 0


@pytest.mark.parametrize(
    ("conformance_result", "numerical_result", "no_silent_widening_ok"),
    [
        (ConformanceResult.NON_CONFORMANT, ConformanceResult.CONFORMANT, True),
        (ConformanceResult.CONFORMANT, ConformanceResult.UNKNOWN, True),
        (ConformanceResult.CONFORMANT, ConformanceResult.CONFORMANT, False),
        (None, None, None),
    ],
)
def test_construction_reader_reports_false_unless_all_three_verdicts_are_positive(
    conformance_result: ConformanceResult | None,
    numerical_result: ConformanceResult | None,
    no_silent_widening_ok: bool | None,
) -> None:
    stage = _FakeConstructionStage(
        _candidate_construction(
            conformance_result=conformance_result,
            numerical_result=numerical_result,
            no_silent_widening_ok=no_silent_widening_ok,
        )
    )
    state = _ConstructionDimensionState(construction_stage=stage)
    reader = _construction_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is False


# ============================================================================
# CONSTRAINT (Phase 5 W3.2, plan §2 decisions 2/3)
# ============================================================================


def test_constraint_reader_is_none_before_the_cell_is_filled() -> None:
    state = _ConstraintDimensionState()
    reader = _constraint_dimension_reader_for(state)
    assert reader() is None


def test_constraint_reader_is_none_when_the_recorder_has_no_verdict_yet() -> None:
    state = _ConstraintDimensionState(
        venue_recorder=VerdictRecorder(lambda _r: _venue_verdict(StageOutcome.ADMIT))
    )
    reader = _constraint_dimension_reader_for(state)
    assert reader() is None


def test_constraint_reader_reports_true_after_an_admit_verdict() -> None:
    recorder = VerdictRecorder(lambda _r: _venue_verdict(StageOutcome.ADMIT))
    recorder(None)
    state = _ConstraintDimensionState(venue_recorder=recorder)
    reader = _constraint_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 0


def test_constraint_reader_reports_false_after_a_deny_verdict() -> None:
    recorder = VerdictRecorder(lambda _r: _venue_verdict(StageOutcome.DENY))
    recorder(None)
    state = _ConstraintDimensionState(venue_recorder=recorder)
    reader = _constraint_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is False


# ============================================================================
# DECISION_PROOF_INTENT (Phase 5 W3.2, plan §2 decision 2)
# ============================================================================


def test_decision_proof_intent_reader_is_none_before_the_cell_is_filled() -> None:
    state = _DecisionProofIntentDimensionState()
    reader = _decision_proof_intent_dimension_reader_for(state)
    assert reader() is None


def test_decision_proof_intent_reader_is_none_when_the_recorder_has_no_verdict_yet() -> (
    None
):
    state = _DecisionProofIntentDimensionState(
        step13_recorder=VerdictRecorder(
            lambda _r: _bind_verification_verdict(StageOutcome.ADMIT)
        )
    )
    reader = _decision_proof_intent_dimension_reader_for(state)
    assert reader() is None


def test_decision_proof_intent_reader_reports_true_after_an_admit_verdict() -> None:
    recorder = VerdictRecorder(
        lambda _r: _bind_verification_verdict(StageOutcome.ADMIT)
    )
    recorder(None)
    state = _DecisionProofIntentDimensionState(step13_recorder=recorder)
    reader = _decision_proof_intent_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is True
    assert report.bound_generation == 0


def test_decision_proof_intent_reader_reports_false_after_a_deny_verdict() -> None:
    recorder = VerdictRecorder(lambda _r: _bind_verification_verdict(StageOutcome.DENY))
    recorder(None)
    state = _DecisionProofIntentDimensionState(step13_recorder=recorder)
    reader = _decision_proof_intent_dimension_reader_for(state)
    report = reader()
    assert report is not None
    assert report.positively_established is False


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
