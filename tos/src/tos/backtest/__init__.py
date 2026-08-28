"""tos.backtest — the event-backtest harness + deterministic paper fill model (D-E3).

Realizes the ratified project-side design contract
``docs/plans/2026-07-29-tos-backtest-design.md`` (#33, D-E3, v1.1, operator-delegated
auto-ratification 2026-07-29): the first harness on the backtest / live parity axis. It replays
historical bars as events through **the** single event core D-E1 shipped (:mod:`tos.engine`),
re-injects synthetic fills as ``EGRESS_RESULT`` events, and emits a wiring trace.

**It re-authors nothing.** ``EngineCore.run``, ``run_commitment_flow``, the event vocabulary, and
the engine records are consumed verbatim; D-E3's product is the surrounding harness only — the bar
model, the causal converter, the fill band, the re-injection driver, the scenario contract, and the
trace artifact (design #33 §0.2-1/§7).

⚠ **Provisional; closes no EV; not an admissible backtest** (design #33 §1.1/§1.2 — the document's
top-level honesty declaration). Four independent reasons converge:

1. production canonicalization is unresolved — every digest rides ``ev-l1-provisional-0``;
2. the Phase-0 bounds approval (P0-1) and independent-reviewer designation (P0-3) are incomplete, so
   every bound consumed here is a provisional value;
3. the authority runtimes the sequencer calls exist only as ``NON_AUTHORITATIVE_PROVISIONAL``
   stand-ins, and the fill model is a **synthetic band**, not a broker;
4. **the single-run disqualifier.** ADR-DEV-010 §8:191-192 names "unrepresentative population — too
   few decisions, a single favorable run" a *disqualifier*, and §8:196-197 settles what that means:
   "it is not 'weaker evidence' … it is out". A slice-1 single-strategy single-run backtest cannot
   pass that bar in principle.

So this package produces a **mechanism / parity demonstration** and nothing else. Of ADR-DEV-010
§7:157's five admissibility conjuncts it realizes three *structurally* — cost realism (injected,
never optimistic), no look-ahead (the converter cannot express it), hermetic and reproducible
(no clock, no RNG) — and it **explicitly defers** population/significance and not-overfit, which is
why it does not meet the bar and does not claim hypothesis-evidence status either (design #33 §1.2).

The seal is **structural, not a disclaimer**: no result, trace, fill, or scenario type in this
package may carry a Sharpe / return / PnL / edge / admissibility-verdict field. Every one of them
runs its own field names through :func:`~tos.backtest._base.seal_performance_surface` at
construction, so smuggling such a field in makes the type unconstructable. There is nowhere to put
the claim (design #33 §1.2 B1). Downstream mark-to-market reconstruction from the emitted raw
material is likewise outside the harness's claim — and would itself be a new single-run backtest,
equally disqualified (§1.2 MINOR-1).

Where the honesty boundaries sit, explicitly:

* **at most one order per scope, for the whole run.** The provisional projection has no release path
  at all (``state.py:22``); ``RELEASED`` is absent (``state.py:57``); even a ``REJECT`` leaves the
  scope occupied (``state.py:83``). Round-trip and repeated sending wait for the real RCL
  (RFC-002 §9.1:557). What the slice demonstrates *positively* is the seal **firing**: a multi-bar
  run yields one realized entry plus N−1 exact capacity denials (design #33 §2.2/§2.3).
* **per-bar core re-instantiation is forbidden.** Rebuilding the core would reset the ledger, forge
  capacity headroom that does not exist (RFC-002 §9.1:558), and destroy single-core parity. Two
  seals enforce it: :class:`~tos.backtest.driver.BacktestDriver` refuses a second core, and this
  package constructs no ``EngineCore`` anywhere (design #33 §2.4).
* **the execution price is D-E3-local.** ``EgressResultPayload`` is quantity-only and the engine
  projection holds no PnL, so slippage / cost / fill price live in
  :class:`~tos.backtest.records.LocalFillRecord` and are never injected into the engine
  (design #33 §4.3).
* **the value surface is D-E2's.** Slice #1 binds the Capsule's ``SnapshotRef`` only, so the
  mechanism runs while the decision starves of real market numerics. The differential oracle's
  numeric layer is gated on D-E2 accordingly; slice-1's oracle scope is **structural wiring
  agreement** (design #33 §3.5/§6.2).
* **next-bar settlement is not look-ahead.** Look-ahead is deciding with future data
  (ADR-DEV-010 §8:182-184); settling later is filling in the future. Decision inputs stay
  prefix-bounded and the two are strictly separated (design #33 §3.6/§12.2-4).
* **the differential comparator is out-of-tree.** ``tos.backtest`` emits its trace and imports
  nothing from ``shared.*``; the comparator that reads both artifacts lives outside ``tos.*`` and is
  deferred placement (design #33 §6.1/§15). Bar loading (parquet / pandas) is likewise out-of-tree
  (§3.1).

The package is **pure, non-transmitting, authority-free, and clock-free**: ``pydantic`` + stdlib +
the allowlisted ``tos.*`` only; no ``shared.*``, no ``numpy`` / ``pandas``, no ``os.environ``, no
socket, no ``importlib`` / ``exec`` / ``eval`` / ``compile``, no wall clock, and no ``random`` /
``secrets`` / ``uuid`` — the fill model is a pure function of ``(bar, injected parameters)`` and the
yield-order coordinate is a counter, so replay identity survives (design #33 §4.4/§9). The stochastic
seed slot RFC-003 §10:360-363 would require is a forward seam and stays unused. All of it is actively
verified by the canaries in ``tos/tests/backtest``.

Public surface groups by module:

* :mod:`tos.backtest.vocabulary` — the closed harness vocabulary (fill modes, settlement, scenarios).
* :mod:`tos.backtest.bars` — the pure ``Bar`` model, ∅-both-ways stream validation, and the
  deterministic multi-symbol lane-mapping validation / merge (design #37 §3.3/§3.6).
* :mod:`tos.backtest.resolver` — the D-E2 resolver slot + the bar → time-coordinate projection.
* :mod:`tos.backtest.converter` — the causal, prefix-bounded bar → ``DECISION_TICK`` converter.
* :mod:`tos.backtest.fills` — the deterministic synthetic ``Transmit`` band (stage + settle), the
  ``EgressResultSource`` re-injection port the driver drains, and the ``GatewayResultReinjector``
  that presents a send boundary's retained results on it (design #35 §2).
* :mod:`tos.backtest.records` — the D-E3-local fill / halt / trace records.
* :mod:`tos.backtest.driver` — the yield-order counter, the interleaving re-injection driver, and
  the N-lane multi-symbol driver that occupies the core's single ``Transmit`` slot and
  demultiplexes each hand-off onto the lane being processed (design #37 §3.2).
* :mod:`tos.backtest.results` — the run result (performance-surface-sealed) + the trace artifact,
  in a single-symbol and an N-lane form (design #37 §3.5).
* :mod:`tos.backtest.scenarios` — the mandated §5.1 scenario contract + a synthetic bar profile.
"""

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
    # base + the §1.2 structural seal
    "PERFORMANCE_SURFACE_TOKENS",
    "BacktestIntegrityError",
    "performance_surface_offenders",
    "seal_performance_surface",
    # vocabulary
    "MANDATED_SCENARIO_IDS",
    "ExecutionPriceBasis",
    "FillMode",
    "FillSide",
    "QuantityProvenance",
    "ScenarioId",
    "SettlementPolicy",
    "SettlementStatus",
    "settleable_result_kinds",
    # bars (§3.1) + the multi-symbol lane mapping / merge (design #37 §3.3/§3.6)
    "Bar",
    "BarStream",
    "merge_bar_streams",
    "settlement_price",
    "validate_bar_stream",
    "validate_bar_stream_mapping",
    # the D-E2 slot + the bar → time projection (§3.3/§3.5)
    "BarTimeProjection",
    "ProvisionalContextResolver",
    "resolved_value_surface_absent",
    # the causal converter (§3.1/§3.6)
    "CausalBarConverter",
    "ConvertedTick",
    # the deterministic fill band (§4)
    "DeterministicFillModel",
    "FillParameters",
    "SettledFill",
    "StagedFill",
    # the re-injection port + the send-boundary result adapter (design #35 §2)
    "EgressResultSource",
    "GatewayResultReinjector",
    "RetainedEgressResults",
    # D-E3-local records (§1.2/§4.3)
    "DEMONSTRATION_LABEL",
    "HaltRecord",
    "LocalFillRecord",
    "TraceEntry",
    "WiringTrace",
    # the driver (§3.4/§4.1) + the §2.4 seal + the N-lane driver (design #37 §3.2)
    "BacktestDriver",
    "CoreReinstantiationError",
    "MultiSymbolBacktestDriver",
    "YieldOrderCounter",
    # the run result + the out-of-tree oracle artifact (§1.2/§6.1) + its N-lane form (#37 §3.5)
    "BacktestRun",
    "MultiSymbolBacktestRun",
    "multi_symbol_trace_digest",
    "multi_symbol_trace_document",
    "trace_digest",
    "trace_document",
    # the mandated scenario contract (§5.1)
    "MANDATED_SCENARIOS",
    "REFERENCE_BASE_PRICE",
    "REFERENCE_VOLUME",
    "ScenarioSpec",
    "reference_bars",
    "scenario_for",
]
