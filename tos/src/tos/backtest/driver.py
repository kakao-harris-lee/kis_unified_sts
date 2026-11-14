"""The interleaving re-injection driver + the global yield-order counter (design #33 §3.4/§4.1)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from tos.backtest._base import BacktestIntegrityError
from tos.backtest.bars import (
    Bar,
    BarStream,
    merge_bar_streams,
    validate_bar_stream,
    validate_bar_stream_mapping,
)
from tos.backtest.converter import CausalBarConverter, ConvertedTick
from tos.backtest.fills import DeterministicFillModel, EgressResultSource
from tos.backtest.records import HaltRecord, LocalFillRecord, TraceEntry, WiringTrace
from tos.backtest.results import BacktestRun, MultiSymbolBacktestRun
from tos.backtest.vocabulary import ScenarioId
from tos.engine import (
    AttemptRequest,
    EgressResultPayload,
    EngineCore,
    EngineEvent,
    EventKind,
    EventResult,
    InstrumentKey,
    SendHandoff,
    TransportNatureLike,
)
from tos.ordering import OrderingEvent

__all__ = [
    "BacktestDriver",
    "CoreReinstantiationError",
    "MultiSymbolBacktestDriver",
    "NonBrokerTransportNature",
    "SyntheticNonLivePreconditions",
    "YieldOrderCounter",
]


class CoreReinstantiationError(BacktestIntegrityError):
    """A driver was asked to run against a second, different :class:`~tos.engine.EngineCore`."""


class SyntheticNonLivePreconditions:
    """Backtest's :class:`~tos.engine.CoordinatorPreconditions` (Phase 3 wave 2 KW2-B; plan §2.1)."""

    def __init__(self, *, authority_epoch_current: bool | None) -> None:
        """Configure the stand-in's explicitly injected authority verdict."""
        self._authority_epoch_current = authority_epoch_current

    def authority_epoch_current(self) -> bool | None:
        """Return the explicitly injected authority verdict, unchanged."""
        return self._authority_epoch_current

    def live_scope_authorized(
        self, transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Whether the wired transport is structurally non-broker-reaching."""
        if transport_nature is None:
            return False
        return transport_nature.reaches_broker is False


@dataclass(frozen=True)
class NonBrokerTransportNature:
    """A structurally honest, non-broker :class:`~tos.engine.core.TransportNatureLike`."""

    reaches_broker: bool | None = False


class YieldOrderCounter:
    """The driver-owned global monotone yield-order counter (design #33 §3.4, MAJOR-1)."""

    def __init__(self, *, continuity_id: str) -> None:
        """Create the counter."""
        if not continuity_id.strip():
            raise BacktestIntegrityError(
                "YieldOrderCounter.continuity_id must be concrete — source-native sequences are "
                "compared only within the same continuity (ordering/_ordering.py:112-127)"
            )
        self._continuity_id = continuity_id
        self._issued = 0

    @property
    def continuity_id(self) -> str:
        """The stream continuity every issued coordinate carries."""
        return self._continuity_id

    @property
    def issued(self) -> int:
        """How many coordinates have been issued so far."""
        return self._issued

    def next_reference(self) -> OrderingEvent:
        """Issue the next strictly-greater coordinate (design #33 §3.4)."""
        self._issued += 1
        sequence = self._issued
        return OrderingEvent(
            event_id=f"{self._continuity_id}-{sequence}",
            source_continuity_id=self._continuity_id,
            source_native_sequence=sequence,
        )


def _stamped_tick(
    tick: ConvertedTick,
    *,
    fill_model: EgressResultSource,
    counter: YieldOrderCounter,
) -> EngineEvent:
    """Bind the lane's settlement context and stamp the bar's tick (design #33 §4.1)."""
    fill_model.bind_settlement_context(tick.bar)
    payload = tick.payload.model_copy(update={"reference": counter.next_reference()})
    return EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=payload)


def _stamped_egress(
    payload: EgressResultPayload, *, counter: YieldOrderCounter
) -> EngineEvent:
    """Stamp one settled result as a re-injected ``EGRESS_RESULT`` event (design #33 §4.1)."""
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=payload.model_copy(
            update={"reference": counter.next_reference()}
        ),
    )


def _trace_entry(
    *,
    sequence: int,
    event: EngineEvent,
    bar_index: int | None,
    result: EventResult,
) -> TraceEntry:
    """Build one wiring-trace entry from the core's own result (design #33 §6.1)."""
    flow = result.flow
    reservation = result.reservation
    egress = event.egress_result
    return TraceEntry(
        yield_sequence=sequence,
        event_kind=result.kind,
        bar_index=bar_index,
        instrument_key=result.instrument_key,
        ordering_admission=result.ordering,
        reference=event.reference(),
        halt_reason=result.halt_reason,
        halt_step=None if flow is None else flow.halt_step,
        handed_off=False if flow is None else flow.handed_off,
        attempt_id=(
            egress.attempt_id
            if egress is not None
            else (
                None
                if flow is None or flow.attempt is None
                else flow.attempt.attempt_id
            )
        ),
        egress_result_kind=None if egress is None else egress.kind,
        capacity_state=None if reservation is None else reservation.capacity_state,
        knowledge=None if reservation is None else reservation.knowledge,
        proposal_digest=(
            None
            if result.pipeline is None or result.pipeline.proposal is None
            else result.pipeline.proposal.canonical_digest
        ),
        outcome_digest=(
            None if result.pipeline is None else result.pipeline.outcome_digest
        ),
    )


def _assemble_trace(
    *,
    yielded: Sequence[tuple[EngineEvent, int | None]],
    results: Sequence[EventResult],
    start: int,
) -> tuple[tuple[TraceEntry, ...], tuple[HaltRecord, ...]]:
    """Pair this run's yielded events with the core's results (design #33 §6.1)."""
    entries: list[TraceEntry] = []
    halts: list[HaltRecord] = []
    for offset, ((event, bar_index), result) in enumerate(
        zip(yielded, results), start=1
    ):
        sequence = start + offset
        entry = _trace_entry(
            sequence=sequence, event=event, bar_index=bar_index, result=result
        )
        entries.append(entry)
        if result.halt_reason is not None:
            halts.append(
                HaltRecord(
                    yield_sequence=sequence,
                    event_kind=entry.event_kind,
                    bar_index=bar_index,
                    instrument_key=entry.instrument_key,
                    halt_reason=result.halt_reason,
                    halt_step=entry.halt_step,
                    detail=result.detail,
                )
            )
    return tuple(entries), tuple(halts)


class BacktestDriver:
    """Drives one bar stream through **one** engine core, interleaving re-injected fills (§4.1)."""

    def __init__(
        self,
        *,
        converter: CausalBarConverter,
        fill_model: EgressResultSource,
        continuity_id: str,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the driver."""
        self._converter = converter
        self._fill_model = fill_model
        self._counter = YieldOrderCounter(continuity_id=continuity_id)
        self._scenario_id = scenario_id
        self._bound_core: EngineCore | None = None
        self._yielded: list[tuple[EngineEvent, int | None]] = []
        self._bars_consumed = 0

    @property
    def instrument_key(self) -> InstrumentKey:
        """The single scope this driver replays."""
        return self._converter.instrument_key

    @property
    def counter(self) -> YieldOrderCounter:
        """The driver-owned yield-order counter (observation only)."""
        return self._counter

    @property
    def bound_core(self) -> EngineCore | None:
        """The core this driver has been bound to, if it has run (design #33 §2.4)."""
        return self._bound_core

    def events(self, bars: Iterable[Bar]) -> Iterator[EngineEvent]:
        """Yield ``DECISION_TICK`` / ``EGRESS_RESULT`` events in causal processing order (§4.1)."""
        for tick in self._converter.stream(bars):
            self._bars_consumed += 1
            event = _stamped_tick(
                tick, fill_model=self._fill_model, counter=self._counter
            )
            self._yielded.append((event, tick.bar.bar_index))
            yield event

            for settled in self._fill_model.settle_due(tick.bar):
                egress_event = _stamped_egress(settled.payload, counter=self._counter)
                self._yielded.append((egress_event, tick.bar.bar_index))
                yield egress_event

    def run(self, core: EngineCore, bars: Sequence[Bar] | None) -> BacktestRun:
        """Replay ``bars`` through ``core`` and assemble the run's D-E3-local artifacts."""
        if self._bound_core is not None and self._bound_core is not core:
            raise CoreReinstantiationError(
                "this driver is already bound to an EngineCore and was handed a different one — "
                "re-instantiating the core resets the ProvisionalReservationLedger, which forges "
                "capacity headroom the real system does not have (RFC-002 §9.1:558) and destroys "
                "the single-core backtest/paper parity the slice exists to demonstrate "
                "(design #33 §2.4). The at-most-one constraint is an honest reflection of the "
                "absent RCL release path (state.py:22), not something to route around."
            )
        self._bound_core = core

        stream: BarStream = validate_bar_stream(bars)
        start = len(self._yielded)
        results: tuple[EventResult, ...] = core.run(self.events(stream))
        yielded = self._yielded[start:]
        entries, halts = _assemble_trace(yielded=yielded, results=results, start=start)

        return BacktestRun(
            instrument_key=self.instrument_key,
            scenario_id=self._scenario_id,
            bars_consumed=len(stream),
            events_yielded=len(yielded),
            event_results=results,
            trace=WiringTrace(
                continuity_id=self._counter.continuity_id, entries=entries
            ),
            halts=halts,
            fill_records=self._fill_model.records,
            unsettled_fill_records=self._fill_model.unsettled_records(),
            handoff_count=len(self._fill_model.handoffs),
        )


class MultiSymbolBacktestDriver:
    """Drives **N instrument lanes** through one engine core on one continuity (design #37 §3.2)."""

    def __init__(
        self,
        *,
        converters: Mapping[InstrumentKey, CausalBarConverter],
        fill_models: Mapping[InstrumentKey, DeterministicFillModel],
        continuity_id: str,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the lanes."""
        missing = [key for key in converters if key not in fill_models]
        extra = [key for key in fill_models if key not in converters]
        if missing or extra:
            raise BacktestIntegrityError(
                "the converter and fill-model lane sets disagree (converters without a fill "
                f"model: {[(k.account, k.instrument) for k in missing]}; fill models without a "
                f"converter: {[(k.account, k.instrument) for k in extra]}) — a lane is a converter "
                "*and* a fill band, and half a lane is not a lane (design #37 §3.2)"
            )
        for key, converter in converters.items():
            if converter.instrument_key != key:
                raise BacktestIntegrityError(
                    f"the converter filed under {(key.account, key.instrument)} declares the scope "
                    f"{(converter.instrument_key.account, converter.instrument_key.instrument)} — "
                    "the lane key is the scope the converter itself declares, never one asserted "
                    "beside it (design #31 §3.3 구조 파생 > 자기신고)"
                )
        self._converters = dict(converters)
        self._fill_models = dict(fill_models)
        self._counter = YieldOrderCounter(continuity_id=continuity_id)
        self._scenario_id = scenario_id
        self._bound_core: EngineCore | None = None
        self._yielded: list[tuple[EngineEvent, int | None]] = []
        self._fill_records: list[LocalFillRecord] = []
        self._current_key: InstrumentKey | None = None

    @property
    def instrument_keys(self) -> tuple[InstrumentKey, ...]:
        """The lane scopes this driver replays, in declaration order."""
        return tuple(self._converters)

    @property
    def counter(self) -> YieldOrderCounter:
        """The driver-owned yield-order counter, shared by every lane (observation only)."""
        return self._counter

    @property
    def bound_core(self) -> EngineCore | None:
        """The core this driver has been bound to, if it has run (design #33 §2.4)."""
        return self._bound_core

    @property
    def current_instrument_key(self) -> InstrumentKey | None:
        """The lane currently being processed, or ``None`` between lanes (observation only)."""
        return self._current_key

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Hand ``attempt`` to the **current lane's** fill band (design #37 §3.2, the C1 seam)."""
        key = self._current_key
        if key is None:
            raise BacktestIntegrityError(
                "a hand-off arrived while no lane was bound — the multi-symbol driver demultiplexes "
                "the core's single Transmit slot by *which lane it is currently processing*, and an "
                "attempt carries no scope to fall back on (records.py:347-351). Guessing a lane "
                "here would stamp a fill with the wrong instrument (design #37 §3.2)"
            )
        return self._fill_models[key](attempt)

    def events(
        self, lanes: Sequence[tuple[InstrumentKey, BarStream]]
    ) -> Iterator[EngineEvent]:
        """Yield every lane's events in one merged causal order (design #37 §3.2/§3.3)."""
        ticks = {
            key: iter(self._converters[key].stream(stream)) for key, stream in lanes
        }
        for key, bar in merge_bar_streams(lanes):
            tick = next(ticks[key], None)
            if (
                tick is None or tick.bar is not bar
            ):  # pragma: no cover - merge is lane-preserving
                raise BacktestIntegrityError(
                    f"lane {(key.account, key.instrument)} produced no tick for merged bar "
                    f"{bar.bar_index} — the merge preserves each lane's own order and the "
                    "converter is driven in that order (design #37 §3.3)"
                )
            self._current_key = key
            fill_model = self._fill_models[key]
            event = _stamped_tick(tick, fill_model=fill_model, counter=self._counter)
            self._yielded.append((event, tick.bar.bar_index))
            yield event

            for settled in fill_model.settle_due(tick.bar):
                self._fill_records.append(settled.record)
                egress_event = _stamped_egress(settled.payload, counter=self._counter)
                self._yielded.append((egress_event, tick.bar.bar_index))
                yield egress_event
            self._current_key = None

    def run(
        self,
        core: EngineCore,
        streams: Mapping[InstrumentKey, Sequence[Bar] | None] | None,
    ) -> MultiSymbolBacktestRun:
        """Replay every lane through ``core`` and assemble the run's D-E3-local artifacts."""
        if self._bound_core is not None and self._bound_core is not core:
            raise CoreReinstantiationError(
                "this driver is already bound to an EngineCore and was handed a different one — "
                "re-instantiating the core resets the ProvisionalReservationLedger, which forges "
                "capacity headroom the real system does not have (RFC-002 §9.1:558) and destroys "
                "the single-core backtest/paper parity the slice exists to demonstrate "
                "(design #33 §2.4). The at-most-one constraint is an honest reflection of the "
                "absent RCL release path (state.py:22), not something to route around."
            )
        self._bound_core = core

        lanes = validate_bar_stream_mapping(streams)
        supplied = {key for key, _stream in lanes}
        declared = set(self._converters)
        if supplied != declared:
            raise BacktestIntegrityError(
                "the injected streams and the declared lanes do not correspond (streams without a "
                f"lane: {sorted((k.account, k.instrument) for k in supplied - declared)}; lanes "
                f"without a stream: {sorted((k.account, k.instrument) for k in declared - supplied)}"
                ") — a declared lane with no stream is MISSING and fail-closed, materially "
                "different from a lane handed an explicitly empty stream (design #37 §3.6)"
            )

        start = len(self._yielded)
        results: tuple[EventResult, ...] = core.run(self.events(lanes))
        yielded = self._yielded[start:]
        entries, halts = _assemble_trace(yielded=yielded, results=results, start=start)

        return MultiSymbolBacktestRun(
            instrument_keys=self.instrument_keys,
            scenario_id=self._scenario_id,
            bars_consumed=sum(len(stream) for _key, stream in lanes),
            events_yielded=len(yielded),
            event_results=results,
            trace=WiringTrace(
                continuity_id=self._counter.continuity_id, entries=entries
            ),
            halts=halts,
            fill_records=tuple(self._fill_records),
            unsettled_fill_records=tuple(
                record
                for key in sorted(
                    self._fill_models, key=lambda item: (item.account, item.instrument)
                )
                for record in self._fill_models[key].unsettled_records()
            ),
            handoff_count=sum(
                len(model.handoffs) for model in self._fill_models.values()
            ),
        )
