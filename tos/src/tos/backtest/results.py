"""The run result + the serialisable trace artifact (design #33 §1.2/§6.1).

:class:`BacktestRun` is what a D-E3 run produces, and what it **cannot** produce is the load-bearing
part. It is a frozen dataclass (mirroring the engine's ``EventResult`` / ``FlowResult`` /
``PipelineResult`` style) whose ``__post_init__`` runs its own field names through
:func:`~tos.backtest._base.seal_performance_surface`. A field named ``sharpe_ratio``,
``total_return``, ``realized_pnl``, or ``admissibility_verdict`` makes the class unconstructable at
import time. That is design #33 §1.2 B1 in its structural form:

    "우리는 성과를 주장하지 않습니다"라는 문장(자기신고)이 아니라, 성과를 담을 필드가 결과 구조에
    부재하도록 설계한다.

The reason is ADR-DEV-010, not modesty. §7:157 makes a Backtest *Admissible* only when all five
conjuncts hold; D-E3 realizes three structurally (cost realism, no look-ahead, hermetic /
reproducible) and **explicitly defers** the two that would require a population — and §8:191-192
makes a single favourable run a *disqualifier*, with §8:196-197 stating it is "not 'weaker
evidence' … it is out". A harness that had a Sharpe field would be making a claim the design has
already established it cannot make (design #33 §12.2-1).

:func:`trace_document` is the out-of-tree oracle's input (design #33 §6.1). ``tos.backtest`` emits a
pure JSON-native mapping and **imports nothing from** ``shared.backtest``; the comparator lives
outside ``tos.*`` entirely and no process ever imports both sides. Its scope is **structural wiring
agreement** — bar cadence ↔ tick emission, the structural path to proposal-emit versus no-action,
the fail-closed halt points — never numerics and never performance; the numeric entry-decision
agreement layer is gated on D-E2's value surface (design #33 §6.2 ②/§7.4 (e)).

⚠ The out-of-tree comparator itself is **not** part of this package: it is deferred placement
(``scripts/`` or a dedicated verification lane, design #33 §6.1/§15). What ships here is the
artifact emit.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No file I/O, no clock, no RNG.
"""

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

__all__ = ["BacktestRun", "trace_digest", "trace_document"]


@dataclass(frozen=True)
class BacktestRun:
    """Everything one D-E3 run produced (design #33 §1.2) — and structurally nothing more.

    ``event_results`` is the engine's own per-event result tuple, in processing order, so a consumer
    reads the *core's* verdicts rather than a harness restatement of them. ``trace``, ``halts``, and
    the two fill-record tuples are the harness's own D-E3-local artifacts.

    ``closes_no_ev`` is ``True`` and is not a parameter: there is no constructor argument by which a
    run could claim otherwise (design #33 §1.1 "닫는 EV = 0").
    """

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
        """Always ``True`` — a slice-1 run is a mechanism / parity demonstration (design #33 §1.1).

        Not a parameter, so no caller can flip it. The three converging reasons are on the package
        docstring: non-production canonicalization, incomplete Phase-0 bounds approval, and
        authority runtimes that exist only as ``NON_AUTHORITATIVE_PROVISIONAL`` stand-ins — plus,
        for D-E3 specifically, the ADR-DEV-010 §8:191-192 single-run disqualifier.
        """
        return True


def trace_document(run: BacktestRun) -> dict[str, Any]:
    """Serialise a run's wiring trace into a pure JSON-native mapping (design #33 §6.1).

    The artifact the **out-of-tree** differential comparator reads. Nothing is written to disk here:
    the harness returns the document and the caller (outside ``tos.*``) owns placement, which is
    what keeps the firewall story clean — no process imports both ``tos.backtest`` and
    ``shared.backtest`` (design #33 §6.1 alternative B).

    Args:
        run: The completed run.

    Returns:
        A JSON-native mapping: the scope, the scenario label, the bar / event counts, the ordered
        trace entries, and the halt records. Fill *magnitudes and prices are deliberately excluded*
        — the oracle's slice-1 scope is structural wiring agreement, and shipping prices into a
        comparison artifact would invite exactly the performance-comparison misreading design #33
        §6.2 seals against.
    """
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
    """The canonical digest of a run's trace document (design #33 §5.2 replay identity).

    Two runs over the same ``(bars, injected parameters, stage map, fill scenario)`` produce the
    same digest — the structural form of ADR-DEV-010 §7:167-168 (BTE-INV-005) hermetic /
    reproducible. Its honest scope is **reproducibility**, never **distinctness**: two bars sharing
    a Snapshot digest may collapse to the same proposal identity, and distinctness depends on D-E2
    producing distinct Snapshot digests (design #33 §5.2, D-E1 Gap-1).

    Args:
        run: The completed run.
        scheme: The injected canonicalization scheme.

    Returns:
        The hex digest of the canonicalized trace document.
    """
    return scheme.compute_digest(trace_document(run))
