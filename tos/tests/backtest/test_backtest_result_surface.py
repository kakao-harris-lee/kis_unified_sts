"""§8-8 / §8-9 — the performance / admissibility surface is structurally absent (design #33 §1.2)."""

from __future__ import annotations

from dataclasses import fields

import pytest
from tos.backtest import (
    PERFORMANCE_SURFACE_TOKENS,
    BacktestIntegrityError,
    BacktestRun,
    Bar,
    BarTimeProjection,
    FillParameters,
    HaltRecord,
    LocalFillRecord,
    MultiSymbolBacktestRun,
    ScenarioId,
    ScenarioSpec,
    TraceEntry,
    WiringTrace,
    performance_surface_offenders,
    scenario_for,
    seal_performance_surface,
    trace_document,
)

from ._backtest_fixtures import INTEGRITY_ERRORS, run_scenario

_SEALED_MODELS = (
    Bar,
    BarTimeProjection,
    FillParameters,
    HaltRecord,
    LocalFillRecord,
    ScenarioSpec,
    TraceEntry,
    WiringTrace,
)


def test_no_shipped_record_type_carries_a_performance_field() -> None:
    """(§8-9) Every pydantic record's declared fields are clean of the forbidden tokens."""
    for model in _SEALED_MODELS:
        offenders = performance_surface_offenders(model.model_fields)
        assert offenders == (), f"{model.__name__} carries {offenders}"


_RUN_RESULTS = (BacktestRun, MultiSymbolBacktestRun)


@pytest.mark.parametrize("run_type", _RUN_RESULTS, ids=lambda item: item.__name__)
def test_the_run_result_itself_carries_no_performance_field(run_type: type) -> None:
    """(§1.2 B1) The top-level products have no Sharpe / return / verdict field — every one of them."""
    names = tuple(field.name for field in fields(run_type))
    assert performance_surface_offenders(names) == ()
    for forbidden in (
        "sharpe",
        "sharpe_ratio",
        "total_return",
        "net_return",
        "realized_pnl",
        "edge",
        "drawdown",
        "win_rate",
        "admissible",
        "admissibility_verdict",
    ):
        assert forbidden not in names, (
            f"{run_type.__name__} declares {forbidden!r} — a single-run slice backtest is "
            "disqualified by ADR-DEV-010 §8:191-192, so the structure must have nowhere to record "
            "such a claim"
        )


def test_every_run_result_dataclass_is_actually_covered_by_this_test() -> None:
    """(anti-phantom §0.5) The run-result *dataclass* family has its own drift detector."""
    import dataclasses

    import tos.backtest as package

    exported_runs = {
        value
        for value in vars(package).values()
        if isinstance(value, type)
        and dataclasses.is_dataclass(value)
        and hasattr(value, "closes_no_ev")
    }
    assert exported_runs == set(_RUN_RESULTS), (
        "the shipped run-result dataclasses and this suite's list have drifted: "
        f"exported={sorted(run.__name__ for run in exported_runs)}"
    )


def test_every_sealed_model_is_actually_covered_by_this_test() -> None:
    """(anti-phantom §0.5) The sealed-model list matches what the package exports — no stale subset."""
    import tos.backtest as package
    from tos.backtest._base import FrozenModel

    exported_models = {
        value
        for value in vars(package).values()
        if isinstance(value, type)
        and issubclass(value, FrozenModel)
        and value is not FrozenModel
    }
    assert exported_models == set(_SEALED_MODELS), (
        "the shipped record types and this suite's sealed list have drifted: "
        f"exported={sorted(model.__name__ for model in exported_models)}"
    )


def test_a_run_reports_that_it_closes_no_ev_and_cannot_say_otherwise() -> None:
    """(§1.1) ``closes_no_ev`` is a property, not a constructor argument — nobody can flip it."""
    run, _core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))
    assert run.closes_no_ev is True
    assert run.label == "MECHANISM_PARITY_DEMONSTRATION_CLOSES_NO_EV"
    for run_type in _RUN_RESULTS:
        assert "closes_no_ev" not in {field.name for field in fields(run_type)}, (
            f"{run_type.__name__} takes closes_no_ev as a parameter — it must be a property no "
            "caller can flip (design #33 §1.1)"
        )


@pytest.mark.parametrize(
    "planted",
    [
        "sharpe",
        "sharpe_ratio",
        "annualised_return",
        "returns",
        "realized_pnl",
        "gross_profit",
        "net_loss",
        "expected_edge",
        "max_drawdown",
        "win_rate",
        "winrate",
        "sortino_ratio",
        "cagr",
        "alpha_estimate",
        "equity_curve",
        "admissibility_verdict",
        "is_admissible",
        "backtest_verdict",
        "performance_summary",
        "expectancy",
        "payoff_ratio",
        "qualified_for_promotion",
    ],
)
def test_the_seal_catches_every_planted_performance_name(planted: str) -> None:
    """(§8-9 canary) The detector really detects — "clean" is evidence, not a neutered check."""
    assert performance_surface_offenders([planted]) == (planted,)
    with pytest.raises(BacktestIntegrityError, match="nowhere to put"):
        seal_performance_surface("Planted", [planted])


@pytest.mark.parametrize(
    "legitimate",
    [
        "yield_sequence",
        "acknowledged",
        "remaining_quantity",
        "filled_quantity",
        "execution_price",
        "settlement_bar_index",
        "instrument_key",
        "halt_reason",
        "ordering_admission",
        "handed_off",
        "attempt_id",
        "capacity_state",
        "knowledge",
        "reference_price",
        "cost_component",
        "slippage_component",
        "bars_consumed",
        "scenario_id",
    ],
)
def test_the_seal_does_not_over_reject_a_legitimate_name(legitimate: str) -> None:
    """(#26 WDR MAJOR-1) Token-wise matching, never substring — an over-rejecting guard is a defect."""
    assert performance_surface_offenders([legitimate]) == ()
    seal_performance_surface("Legitimate", [legitimate])


def test_the_token_set_is_non_empty_and_closed() -> None:
    """(§8-9) The seal is not vacuous — an empty token set would pass everything silently."""
    assert len(PERFORMANCE_SURFACE_TOKENS) >= 15
    assert "sharpe" in PERFORMANCE_SURFACE_TOKENS
    assert "verdict" in PERFORMANCE_SURFACE_TOKENS
    assert "yield" not in PERFORMANCE_SURFACE_TOKENS, (
        "'yield' is deliberately excluded — it is both a performance word and the generator verb, "
        "and banning it would over-reject the harness's own yield-order coordinate"
    )


def test_a_smuggled_performance_field_makes_the_model_unconstructable() -> None:
    """(§1.2 B1) The seal is enforced at construction, not by review — planted subclass, real raise."""
    from pydantic import model_validator
    from tos.backtest._base import FrozenModel

    with pytest.raises(INTEGRITY_ERRORS, match="nowhere to put"):

        class _Smuggled(FrozenModel):
            """A record that tries to carry a performance surface."""

            sharpe_ratio: float = 0.0

            @model_validator(mode="after")
            def _seal(self) -> _Smuggled:
                seal_performance_surface(type(self).__name__, type(self).model_fields)
                return self

        _Smuggled()


def test_the_oracle_artifact_declares_its_narrow_scope() -> None:
    """(§6.2 ①/②) Structural wiring agreement only; the numeric layer is D-E2-gated and says so."""
    run, _core, _fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.ENTRY_FULL_FILL)
    )
    document = trace_document(run)
    assert document["oracle_scope"] == "STRUCTURAL_WIRING_AGREEMENT_ONLY"
    assert (
        document["numeric_decision_agreement"] == "DEFERRED_PENDING_D_E2_VALUE_SURFACE"
    )


def test_the_oracle_artifact_carries_no_price_or_magnitude() -> None:
    """(§6.2/§1.2) Nothing in the comparison artifact could be mistaken for a performance figure."""
    run, _core, _fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.ENTRY_PARTIAL_FILL)
    )
    assert (
        run.fill_records[0].execution_price is not None
    ), "the run really did price a fill"

    serialized = repr(trace_document(run))
    for forbidden in (
        "execution_price",
        "filled_quantity",
        "slippage",
        "cost_component",
    ):
        assert forbidden not in serialized, (
            f"the oracle artifact leaked {forbidden!r} — the slice-1 oracle compares structural "
            "wiring, and shipping magnitudes invites the performance-comparison misreading "
            "design #33 §6.2 seals against"
        )


def test_the_oracle_artifact_keys_are_closed_and_declared() -> None:
    """(§6.1) The artifact's shape is fixed, so an out-of-tree comparator can rely on it."""
    run, _core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))
    assert set(trace_document(run)) == {
        "artifact_type",
        "label",
        "closes_no_ev",
        "oracle_scope",
        "numeric_decision_agreement",
        "instrument_key",
        "scenario_id",
        "bars_consumed",
        "events_yielded",
        "trace",
        "halts",
    }
