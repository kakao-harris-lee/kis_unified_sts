"""tos.backtest — the event-backtest harness + deterministic paper fill model (D-E3)."""

from __future__ import annotations

from tos.backtest._base import (
    PERFORMANCE_SURFACE_TOKENS,
    BacktestIntegrityError,
    performance_surface_offenders,
    seal_performance_surface,
)
from tos.backtest.bars import (
    Bar,
    BarStream,
    merge_bar_streams,
    settlement_price,
    validate_bar_stream,
    validate_bar_stream_mapping,
)
from tos.backtest.converter import CausalBarConverter, ConvertedTick
from tos.backtest.driver import (
    BacktestDriver,
    CoreReinstantiationError,
    MultiSymbolBacktestDriver,
    NonBrokerTransportNature,
    SyntheticNonLivePreconditions,
    YieldOrderCounter,
)
from tos.backtest.fills import (
    DeterministicFillModel,
    EgressResultSource,
    FillParameters,
    GatewayResultReinjector,
    RetainedEgressResults,
    SettledFill,
    StagedFill,
)
from tos.backtest.records import (
    DEMONSTRATION_LABEL,
    HaltRecord,
    LocalFillRecord,
    TraceEntry,
    WiringTrace,
)
from tos.backtest.resolver import (
    BarTimeProjection,
    ProvisionalContextResolver,
    resolved_value_surface_absent,
)
from tos.backtest.results import (
    BacktestRun,
    MultiSymbolBacktestRun,
    multi_symbol_trace_digest,
    multi_symbol_trace_document,
    trace_digest,
    trace_document,
)
from tos.backtest.scenarios import (
    MANDATED_SCENARIOS,
    REFERENCE_BASE_PRICE,
    REFERENCE_VOLUME,
    ScenarioSpec,
    reference_bars,
    scenario_for,
)
from tos.backtest.vocabulary import (
    MANDATED_SCENARIO_IDS,
    ExecutionPriceBasis,
    FillMode,
    FillSide,
    QuantityProvenance,
    ScenarioId,
    SettlementPolicy,
    SettlementStatus,
    settleable_result_kinds,
)

__all__ = [
    "PERFORMANCE_SURFACE_TOKENS",
    "BacktestIntegrityError",
    "performance_surface_offenders",
    "seal_performance_surface",
    "MANDATED_SCENARIO_IDS",
    "ExecutionPriceBasis",
    "FillMode",
    "FillSide",
    "QuantityProvenance",
    "ScenarioId",
    "SettlementPolicy",
    "SettlementStatus",
    "settleable_result_kinds",
    "Bar",
    "BarStream",
    "merge_bar_streams",
    "settlement_price",
    "validate_bar_stream",
    "validate_bar_stream_mapping",
    "BarTimeProjection",
    "ProvisionalContextResolver",
    "resolved_value_surface_absent",
    "CausalBarConverter",
    "ConvertedTick",
    "DeterministicFillModel",
    "FillParameters",
    "SettledFill",
    "StagedFill",
    "EgressResultSource",
    "GatewayResultReinjector",
    "RetainedEgressResults",
    "DEMONSTRATION_LABEL",
    "HaltRecord",
    "LocalFillRecord",
    "TraceEntry",
    "WiringTrace",
    "BacktestDriver",
    "CoreReinstantiationError",
    "MultiSymbolBacktestDriver",
    "NonBrokerTransportNature",
    "SyntheticNonLivePreconditions",
    "YieldOrderCounter",
    "BacktestRun",
    "MultiSymbolBacktestRun",
    "multi_symbol_trace_digest",
    "multi_symbol_trace_document",
    "trace_digest",
    "trace_document",
    "MANDATED_SCENARIOS",
    "REFERENCE_BASE_PRICE",
    "REFERENCE_VOLUME",
    "ScenarioSpec",
    "reference_bars",
    "scenario_for",
]
