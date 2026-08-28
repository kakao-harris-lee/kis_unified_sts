"""§8-8 / §8-9 — the performance / admissibility surface is structurally absent (design #33 §1.2).

This is the design's B1 judgement in test form. ADR-DEV-010 §7:157 makes a Backtest *Admissible*
only when **all five** conjuncts hold; D-E3 realizes three structurally and explicitly defers
population/significance and not-overfit — and §8:191-192 makes a single favourable run a
*disqualifier*, with §8:196-197 refusing even the "weaker evidence" framing: "it is out."

So the harness does not promise to make no performance claim. It has **nowhere to put one**. Every
result / trace / fill / scenario type runs its own field names through
:func:`~tos.backtest.seal_performance_surface` at construction, so a ``sharpe_ratio``,
``total_return``, ``realized_pnl``, or ``admissibility_verdict`` field makes the type
unconstructable. The seal's own detector is canaried in both directions here: it must catch planted
performance names *and* must not over-reject legitimate ones — the #26 WDR MAJOR-1 lesson, since a
guard that swallows correct cases is its own defect class.

The differential-oracle artifact is sealed the same way (§8-8 / §6.2): its scope is **structural
wiring agreement**, the numeric decision-agreement layer is gated on D-E2's value surface, and the
document carries neither prices nor magnitudes to be mistaken for a performance comparison.

Regime tag: orchestration authoring evidence only; closes no EV (design #33 §1.1).
"""

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

#: Every pydantic record type the package ships. Listed explicitly and cross-checked against the
#: module namespace below, so a *new* record type cannot quietly escape the seal (#27 FD lesson).
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


#: Every run-result dataclass the package ships. Listed explicitly and cross-checked against the
#: module namespace below, exactly as ``_SEALED_MODELS`` is for the pydantic side — an N-lane run is
#: still a run, and a run type that escaped the seal would escape the whole §1.2 B1 judgement
#: (design #37 §3.5/§4 M16).
_RUN_RESULTS = (BacktestRun, MultiSymbolBacktestRun)


@pytest.mark.parametrize("run_type", _RUN_RESULTS, ids=lambda item: item.__name__)
def test_the_run_result_itself_carries_no_performance_field(run_type: type) -> None:
    """(§1.2 B1) The top-level products have no Sharpe / return / verdict field — every one of them.

    ``instrument_keys`` is a scope list, not a performance name, and the token-wise detector says so
    rather than the reader (design #37 §4 M16).
    """
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
    """(anti-phantom §0.5) The run-result *dataclass* family has its own drift detector.

    ``_SEALED_MODELS`` watches pydantic ``FrozenModel`` subclasses only, so the run results — frozen
    **dataclasses** — had no set-drift canary at all while there was just one of them. There are now
    two, and a third landing without its ``__post_init__`` seal would be exactly the silent escape
    the #27 FD lesson names. The membership predicate is structural (``is_dataclass`` ∧ carries
    ``closes_no_ev``), never a hardcoded census of what someone remembered to add.
    """
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
    """(anti-phantom §0.5) The sealed-model list matches what the package exports — no stale subset.

    The existence direction of the discipline: it is not enough that the listed models are clean, the
    list itself must be the shipped set. A new record type that forgot the seal would show up here.
    """
    import tos.backtest as package
    from tos.backtest._base import FrozenModel

    exported_models = {
        value
        for value in vars(package).values()
        if isinstance(value, type) and issubclass(value, FrozenModel) and value is not FrozenModel
    }
    assert exported_models == set(_SEALED_MODELS), (
        "the shipped record types and this suite's sealed list have drifted: "
        f"exported={sorted(model.__name__ for model in exported_models)}"
    )


def test_a_run_reports_that_it_closes_no_ev_and_cannot_say_otherwise() -> None:
    """(§1.1) ``closes_no_ev`` is a property, not a constructor argument — nobody can flip it.

    Asserted for every shipped run type: replaying N symbols instead of one changes nothing about
    the four converging reasons, so an N-lane run that could claim otherwise would be a hole in the
    same seal (design #37 §3.5).
    """
    run, _core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_ACK))
    assert run.closes_no_ev is True
    assert run.label == "MECHANISM_PARITY_DEMONSTRATION_CLOSES_NO_EV"
    for run_type in _RUN_RESULTS:
        assert "closes_no_ev" not in {field.name for field in fields(run_type)}, (
            f"{run_type.__name__} takes closes_no_ev as a parameter — it must be a property no "
            "caller can flip (design #33 §1.1)"
        )


# ---------------------------------------------------------------------------
# the seal's own detector — both directions
# ---------------------------------------------------------------------------


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
    """(#26 WDR MAJOR-1) Token-wise matching, never substring — an over-rejecting guard is a defect.

    ``acknowledged`` contains the substring ``edge`` and ``yield_sequence`` contains ``yield``; a
    naive substring check would refuse both, breaking correct code in the name of a seal.
    """
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


# ---------------------------------------------------------------------------
# §8-8 — the differential oracle's scope seal
# ---------------------------------------------------------------------------


def test_the_oracle_artifact_declares_its_narrow_scope() -> None:
    """(§6.2 ①/②) Structural wiring agreement only; the numeric layer is D-E2-gated and says so."""
    run, _core, _fill_model, _sink = run_scenario(scenario_for(ScenarioId.ENTRY_FULL_FILL))
    document = trace_document(run)
    assert document["oracle_scope"] == "STRUCTURAL_WIRING_AGREEMENT_ONLY"
    assert document["numeric_decision_agreement"] == "DEFERRED_PENDING_D_E2_VALUE_SURFACE"


def test_the_oracle_artifact_carries_no_price_or_magnitude() -> None:
    """(§6.2/§1.2) Nothing in the comparison artifact could be mistaken for a performance figure."""
    run, _core, _fill_model, _sink = run_scenario(
        scenario_for(ScenarioId.ENTRY_PARTIAL_FILL)
    )
    assert run.fill_records[0].execution_price is not None, "the run really did price a fill"

    serialized = repr(trace_document(run))
    for forbidden in ("execution_price", "filled_quantity", "slippage", "cost_component"):
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
