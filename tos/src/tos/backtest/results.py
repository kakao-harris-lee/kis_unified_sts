"""The run result + the serialisable trace artifact (design #33 §1.2/§6.1)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from tos.backtest._base import CanonicalizationScheme, seal_performance_surface
from tos.backtest.records import (
    DEMONSTRATION_LABEL,
    HaltRecord,
    LocalFillRecord,
    WiringTrace,
)
from tos.backtest.vocabulary import ScenarioId
from tos.engine import EventResult, InstrumentKey

__all__ = [
    "BacktestRun",
    "MultiSymbolBacktestRun",
    "multi_symbol_trace_digest",
    "multi_symbol_trace_document",
    "trace_digest",
    "trace_document",
]


@dataclass(frozen=True)
class BacktestRun:
    """Everything one D-E3 run produced (design #33 §1.2) — and structurally nothing more."""

    instrument_key: InstrumentKey
    scenario_id: ScenarioId | None
    bars_consumed: int
    events_yielded: int
    event_results: tuple[EventResult, ...]
    trace: WiringTrace
    halts: tuple[HaltRecord, ...]
    fill_records: tuple[LocalFillRecord, ...]
    unsettled_fill_records: tuple[LocalFillRecord, ...]
    handoff_count: int
    label: str = DEMONSTRATION_LABEL

    def __post_init__(self) -> None:
        """Seal the performance / admissibility surface structurally (design #33 §1.2 B1)."""
        seal_performance_surface(
            type(self).__name__, tuple(field.name for field in fields(self))
        )

    @property
    def closes_no_ev(self) -> bool:
        """Always ``True`` — a slice-1 run is a mechanism / parity demonstration (design #33 §1.1)."""
        return True


@dataclass(frozen=True)
class MultiSymbolBacktestRun:
    """Everything one **N-lane** D-E3 run produced (design #37 §3.5) — and nothing more."""

    instrument_keys: tuple[InstrumentKey, ...]
    scenario_id: ScenarioId | None
    bars_consumed: int
    events_yielded: int
    event_results: tuple[EventResult, ...]
    trace: WiringTrace
    halts: tuple[HaltRecord, ...]
    fill_records: tuple[LocalFillRecord, ...]
    unsettled_fill_records: tuple[LocalFillRecord, ...]
    handoff_count: int
    label: str = DEMONSTRATION_LABEL

    def __post_init__(self) -> None:
        """Seal the performance / admissibility surface structurally (design #33 §1.2 B1)."""
        seal_performance_surface(
            type(self).__name__, tuple(field.name for field in fields(self))
        )

    @property
    def closes_no_ev(self) -> bool:
        """Always ``True`` — N lanes is still a mechanism / parity demonstration (design #33 §1.1)."""
        return True


def trace_document(run: BacktestRun) -> dict[str, Any]:
    """Serialise a run's wiring trace into a pure JSON-native mapping (design #33 §6.1)."""
    return {
        "artifact_type": "tos.backtest.wiring_trace",
        "label": DEMONSTRATION_LABEL,
        "closes_no_ev": run.closes_no_ev,
        "oracle_scope": "STRUCTURAL_WIRING_AGREEMENT_ONLY",
        "numeric_decision_agreement": "DEFERRED_PENDING_D_E2_VALUE_SURFACE",
        "instrument_key": run.instrument_key.model_dump(mode="json"),
        "scenario_id": None if run.scenario_id is None else run.scenario_id.value,
        "bars_consumed": run.bars_consumed,
        "events_yielded": run.events_yielded,
        "trace": run.trace.model_dump(mode="json"),
        "halts": [halt.model_dump(mode="json") for halt in run.halts],
    }


def trace_digest(run: BacktestRun, *, scheme: CanonicalizationScheme) -> str:
    """The canonical digest of a run's trace document (design #33 §5.2 replay identity)."""
    return scheme.compute_digest(trace_document(run))


def multi_symbol_trace_document(run: MultiSymbolBacktestRun) -> dict[str, Any]:
    """Serialise an N-lane run's wiring trace into a pure JSON-native mapping (design #37 §3.5)."""
    return {
        "artifact_type": "tos.backtest.multi_symbol_wiring_trace",
        "label": DEMONSTRATION_LABEL,
        "closes_no_ev": run.closes_no_ev,
        "oracle_scope": "STRUCTURAL_WIRING_AGREEMENT_ONLY",
        "numeric_decision_agreement": "DEFERRED_PENDING_D_E2_VALUE_SURFACE",
        "instrument_keys": [
            key.model_dump(mode="json")
            for key in sorted(
                run.instrument_keys, key=lambda item: (item.account, item.instrument)
            )
        ],
        "scenario_id": None if run.scenario_id is None else run.scenario_id.value,
        "bars_consumed": run.bars_consumed,
        "events_yielded": run.events_yielded,
        "trace": run.trace.model_dump(mode="json"),
        "halts": [halt.model_dump(mode="json") for halt in run.halts],
    }


def multi_symbol_trace_digest(
    run: MultiSymbolBacktestRun, *, scheme: CanonicalizationScheme
) -> str:
    """The canonical digest of an N-lane run's trace document (design #37 §1.6)."""
    return scheme.compute_digest(multi_symbol_trace_document(run))
