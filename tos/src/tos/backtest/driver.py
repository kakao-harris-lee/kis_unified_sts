"""The interleaving re-injection driver + the global yield-order counter (design #33 §3.4/§4.1).

This module is the design's load-bearing content. Four things live here and nothing else does.

**1. The driver-owned global monotone yield-order counter (design #33 §3.4, MAJOR-1).**

The engine's causal gate does **not** compare an event against its triggering tick: it holds a
single global ``_last_reference`` (``core.py:246``), compares every incoming event against it
(``core.py:280``), and updates it for **every** non-``REVERSED`` event (``core.py:301``) — including
a tick that goes on to halt at the capacity stage, because line 301 runs *before* the handler.

So a coordinate scheme bound to ``bar_index`` is broken. With ``2i / 2i+1``, a next-bar settlement
is processed as ``tick_0(0), tick_1(2), egress_0(1)`` — and ``compare_order(1, 2)`` is ``BEFORE``,
so the re-injected result is refused as a **false ``REVERSED``** halt (``core.py:281``). The fix is
structural: the driver stamps **every** event it yields — tick or egress alike — with the next value
of one global counter at yield time. Because the driver's yield order *is* the core's processing
order, the coordinates are strictly increasing by construction, and the admission is always
``MONOTONE`` regardless of same-bar or next-bar settlement. The coordinate is therefore
**decoupled** from ``bar_index``, which is recorded separately for settlement lookup and oracle
alignment (design #33 §3.4/§4.3/§6).

There is deliberately **no reset / rewind method**: a counter that could go backwards is the defect
the design removed.

**2. The interleaving ``EventSource`` generator (design #33 §4.1 B3).**

``EngineCore.run`` consumes its argument **lazily** (``core.py:262`` — a generator expression over
``events``), which is what makes the re-injection model work at all: the driver yields a tick, the
core processes it to completion (the sequencer calls ``transmit``, the fill model *stages*), and
only then does the core pull the next event — at which point the driver can yield the staged fill as
an ``EGRESS_RESULT``. Same core, same sequencer, same ledger lifetime.

Two rejected alternatives, both from the design: re-authoring ``run`` to apply fills inline (forbidden
core re-authoring, and it destroys the re-injection model that paper shares), and pre-building a
static ``EventBatch`` (impossible — a fill depends on what the core decided). The stateful generator
is the only consistent shape.

**3. The core re-instantiation prohibition (design #33 §2.4 — a hard constraint).**

Rebuilding an ``EngineCore`` per bar would reset the ``ProvisionalReservationLedger`` and make the
scope look free every bar, so repeated sends would appear to work. It is forbidden twice over: it
destroys the single-core backtest/paper parity that is the whole point (design #31 §2.1/§12), and it
forges capacity headroom that does not exist in the real system — the harness-layer form of
RFC-002 §9.1:558's "producer-local counters SHALL NOT create headroom". The no-release constraint is
an honest reflection of the RCL runtime's absence, not something to route around.

Two independent seals enforce it: :class:`BacktestDriver` binds the first core it is run against and
refuses a different one, and the package's own sources construct no ``EngineCore`` at all (an AST
canary asserts it — design #33 §9).

**4. The N-lane multi-symbol driver + the single-``Transmit``-slot demux (design #37 §3.2).**

A multi-symbol replay is N per-instrument lanes on **one** continuity and **one** yield counter, so
the engine core is untouched: its single global ``_last_reference`` is exactly right when every
event shares a continuity, and per-symbol continuities would instead make every cross-lane adjacent
pair ``AMBIGUOUS`` — ordering detection switched *off* precisely where multi-symbol adds risk
(design #37 §1.2/§1.3).

The wiring problem multi-symbol really poses is narrower and is the module's second load-bearing
invariant. ``EngineCore`` has **one** ``transmit`` slot (``core.py:216``/``:243``), and the
``AttemptRequest`` it hands over carries no instrument and no scope (``records.py:347-351``) — so
demultiplexing N lanes *from the attempt* is structurally impossible. Sharing one fill model across
lanes is worse than useless: it stamps every fill with one ``instrument_key``
(``fills.py:372``/``:452``) and matches settlements by a lane-local ``bar_index``
(``fills.py:473-474``), shipping cross-symbol settlement contamination silently.

So :class:`MultiSymbolBacktestDriver` occupies the slot itself and demultiplexes onto the lane it is
**currently processing**. That is correct because of a property the core states on its own first
line: *"One event is processed to completion before the next"* (``core.py:1-3``). The driver
generator suspends at its ``yield``, the core runs the whole flow — including the single ``transmit``
call — before pulling again, so at hand-off time the current lane is unambiguously the one bound
just before the tick. **This module now depends on that synchronous completion guarantee for
correctness, not merely for determinism** (design #37 §0.4/§3.2).

⚠ **The single global slot is right only while the stream is single-continuity**, and the backtest
driver is what makes that true here. A *live* multi-symbol ``EventSource`` (D-E4's sender, a real
transport) would owe the core the same single-continuity ingest order — an obligation that is
**new**, not already ratified: design #33 §3.4's coordinate principle is a backtest-driver
prescription, and nothing on the live side has been ratified in its place (design #37 §1.4,
FORWARD-OBLIGATION-MS1). The core is left agnostic rather than hard-guarded on purpose, so that a
broker which genuinely forces per-symbol continuities can still be met by the sealing design the
contract keeps in reserve.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no network.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence

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
)
from tos.ordering import OrderingEvent

__all__ = [
    "BacktestDriver",
    "CoreReinstantiationError",
    "MultiSymbolBacktestDriver",
    "YieldOrderCounter",
]


class CoreReinstantiationError(BacktestIntegrityError):
    """A driver was asked to run against a second, different :class:`~tos.engine.EngineCore`.

    Raised — never tolerated. Per-bar re-instantiation resets the reservation projection, forging
    capacity headroom the real system does not have and destroying single-core backtest/paper
    parity (design #33 §2.4; RFC-002 §9.1:558).
    """


class YieldOrderCounter:
    """The driver-owned global monotone yield-order counter (design #33 §3.4, MAJOR-1).

    One counter for the whole run, across **both** event kinds. Its invariant is stated as an
    identity rather than a hope: *coordinate order ≡ processing order*, because the only way to
    obtain a coordinate is to be the next event yielded.

    It emits :class:`~tos.ordering.OrderingEvent` coordinates on a single continuity, so
    :func:`~tos.ordering.compare_order` resolves them by ``source_native_sequence``
    (``ordering/_ordering.py:112-127``) — the same-continuity branch, never a cross-continuity
    subtraction and never a wall clock. ``time_lo`` / ``time_hi`` are deliberately left unset:
    trustworthy-time intervals do not participate in this ordering (design #33 §3.4 정직), and
    freshness travels separately on ``TimeAdmissionInputs``.
    """

    def __init__(self, *, continuity_id: str) -> None:
        """Create the counter.

        Args:
            continuity_id: The single stream continuity every coordinate is issued on.

        Raises:
            BacktestIntegrityError: If the continuity id is not concrete — coordinates are only
                comparable within a named continuity.
        """
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
        """Issue the next strictly-greater coordinate (design #33 §3.4).

        Returns:
            The :class:`~tos.ordering.OrderingEvent` for the event about to be yielded. There is no
            way to obtain a coordinate without advancing the counter, and no method rewinds it.
        """
        self._issued += 1
        sequence = self._issued
        return OrderingEvent(
            event_id=f"{self._continuity_id}-{sequence}",
            source_continuity_id=self._continuity_id,
            source_native_sequence=sequence,
        )


# ===========================================================================
# the per-lane replay steps, shared by both drivers (design #37 §3.1)
# ===========================================================================
#
# A pure extraction, performed so the multi-symbol driver replays a lane *the same way* the
# single-symbol driver replays its only lane rather than by a second, drifting transcription. It
# changes no behaviour: the single-symbol public surface, the yielded event sequence, and every
# existing scenario's ``trace_digest`` are unchanged, and the suite's digest canary is what proves
# that (design #37 §3.1 게이트).


def _stamped_tick(
    tick: ConvertedTick,
    *,
    fill_model: EgressResultSource,
    counter: YieldOrderCounter,
) -> EngineEvent:
    """Bind the lane's settlement context and stamp the bar's tick (design #33 §4.1).

    The binding happens **before** the coordinate is issued and before the event is yielded,
    because the fill model cannot read a settlement bar off an economics-free ``AttemptRequest``.

    Args:
        tick: The lane's converted tick.
        fill_model: That lane's re-injection source.
        counter: The run's single yield-order counter.

    Returns:
        The ``DECISION_TICK`` event, stamped with the next yield-order coordinate.
    """
    fill_model.bind_settlement_context(tick.bar)
    payload = tick.payload.model_copy(update={"reference": counter.next_reference()})
    return EngineEvent(kind=EventKind.DECISION_TICK, decision_tick=payload)


def _stamped_egress(
    payload: EgressResultPayload, *, counter: YieldOrderCounter
) -> EngineEvent:
    """Stamp one settled result as a re-injected ``EGRESS_RESULT`` event (design #33 §4.1).

    Args:
        payload: The settled result's engine payload, forwarded unchanged apart from the
            coordinate.
        counter: The run's single yield-order counter.

    Returns:
        The ``EGRESS_RESULT`` event, stamped with the next yield-order coordinate.
    """
    return EngineEvent(
        kind=EventKind.EGRESS_RESULT,
        egress_result=payload.model_copy(update={"reference": counter.next_reference()}),
    )


def _trace_entry(
    *,
    sequence: int,
    event: EngineEvent,
    bar_index: int | None,
    result: EventResult,
) -> TraceEntry:
    """Build one wiring-trace entry from the core's own result (design #33 §6.1).

    Everything recorded is read off the engine's :class:`~tos.engine.EventResult` and the event
    itself — the harness restates no verdict of its own, so the trace cannot disagree with what
    the core actually did.

    Args:
        sequence: The event's global yield-order coordinate.
        event: The yielded event.
        bar_index: The bar the event belongs to (lane-local for a multi-symbol run).
        result: The core's own result for that event.

    Returns:
        The :class:`~tos.backtest.records.TraceEntry`.
    """
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
            else (None if flow is None or flow.attempt is None else flow.attempt.attempt_id)
        ),
        egress_result_kind=None if egress is None else egress.kind,
        capacity_state=None if reservation is None else reservation.capacity_state,
        knowledge=None if reservation is None else reservation.knowledge,
        proposal_digest=(
            None
            if result.pipeline is None or result.pipeline.proposal is None
            else result.pipeline.proposal.canonical_digest
        ),
        outcome_digest=(None if result.pipeline is None else result.pipeline.outcome_digest),
    )


def _assemble_trace(
    *,
    yielded: Sequence[tuple[EngineEvent, int | None]],
    results: Sequence[EventResult],
    start: int,
) -> tuple[tuple[TraceEntry, ...], tuple[HaltRecord, ...]]:
    """Pair this run's yielded events with the core's results (design #33 §6.1).

    Args:
        yielded: This run's ``(event, bar_index)`` pairs, in yield order.
        results: The core's per-event results, in the same order.
        start: How many events the driver had already yielded before this run — the yield-order
            coordinate continues across runs and never restarts (design #33 §3.4).

    Returns:
        ``(entries, halts)``. A halt is recorded whenever the core reported one; the reason is the
        core's own, never a harness restatement.
    """
    entries: list[TraceEntry] = []
    halts: list[HaltRecord] = []
    for offset, ((event, bar_index), result) in enumerate(zip(yielded, results), start=1):
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
    """Drives one bar stream through **one** engine core, interleaving re-injected fills (§4.1).

    The driver owns: the yield-order counter (§3.4), the settlement-context binding the fill model
    cannot derive from an ``AttemptRequest`` (§4.1), the interleaving of ticks and re-injected
    egress results, and the assembly of the run's D-E3-local artifacts.

    It owns **nothing** of the engine: it constructs no core, injects no stage, and re-authors no
    sequencer step (design #33 §0.2-1).
    """

    def __init__(
        self,
        *,
        converter: CausalBarConverter,
        fill_model: EgressResultSource,
        continuity_id: str,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the driver.

        Args:
            converter: The causal bar → tick converter (§3.1).
            fill_model: The re-injection source (§4) — any
                :class:`~tos.backtest.fills.EgressResultSource`. The parameter name is kept
                because the deterministic fill band is still the reference satisfier, but the
                type is the structural port, so a send boundary's retained results can be
                re-injected through the same loop (design #35 §2.1).
            continuity_id: The stream continuity for the yield-order coordinates (§3.4).
            scenario_id: The mandated scenario this run realizes, recorded on the result.
        """
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

    # -- the interleaving EventSource ----------------------------------------

    def events(self, bars: Iterable[Bar]) -> Iterator[EngineEvent]:
        """Yield ``DECISION_TICK`` / ``EGRESS_RESULT`` events in causal processing order (§4.1).

        The generator's shape *is* the re-injection contract:

        1. bind the current bar as the fill model's settlement context — synchronously, **before**
           the tick is yielded, because the model cannot read a settlement bar off an economics-free
           ``AttemptRequest`` (design #33 §4.1);
        2. yield the tick, stamped with the next yield-order coordinate;
        3. the core processes it to completion — the sequencer's step-14 hand-off calls the fill
           model, which *stages* a pending fill;
        4. when the core pulls again, settle every fill whose settlement bar has now arrived and
           yield each as an ``EGRESS_RESULT``, each stamped with the next coordinate.

        With ``NEXT_BAR`` settlement this produces ``tick_0, tick_1, egress_0`` — coordinates
        ``1, 2, 3`` — and every admission is ``MONOTONE``. Under the rejected ``2i / 2i+1`` scheme
        the same sequence would be ``0, 2, 1`` and the re-injected result would be refused as a
        false ``REVERSED`` (design #33 §3.4 MAJOR-1).

        Args:
            bars: The validated bar stream.

        Yields:
            The interleaved engine events.
        """
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

    # -- the run -------------------------------------------------------------

    def run(self, core: EngineCore, bars: Sequence[Bar] | None) -> BacktestRun:
        """Replay ``bars`` through ``core`` and assemble the run's D-E3-local artifacts.

        Args:
            core: The **single** engine core for the whole run. The same core must be reused across
                every bar and across repeated runs of this driver — see :class:`CoreReinstantiationError`.
            bars: The injected bar stream. ``None`` is fail-closed; ``()`` is a defined empty run
                (design #33 §13 ∅ 양방향).

        Returns:
            The :class:`~tos.backtest.results.BacktestRun`.

        Raises:
            CoreReinstantiationError: If a *different* core is supplied after the driver has already
                run — the harness-layer seal against per-bar ledger resets (design #33 §2.4).
            BacktestIntegrityError: If the bar stream is missing or not causally ordered.
        """
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
            trace=WiringTrace(continuity_id=self._counter.continuity_id, entries=entries),
            halts=halts,
            fill_records=self._fill_model.records,
            unsettled_fill_records=self._fill_model.unsettled_records(),
            handoff_count=len(self._fill_model.handoffs),
        )


class MultiSymbolBacktestDriver:
    """Drives **N instrument lanes** through one engine core on one continuity (design #37 §3.2).

    A lane is a ``(CausalBarConverter, DeterministicFillModel)`` pair keyed by its
    :class:`~tos.engine.InstrumentKey`. Everything *below* the driver is reused unchanged: one core,
    one registry (N entries — no interface change, ``registry.py:59``), one per-scope reservation
    ledger (lane capacity independence is the ledger's own keying, not something this driver
    arranges), one converter and one fill band per lane, and **one**
    :class:`YieldOrderCounter` shared by every lane.

    The single counter is the design judgement, not an economy. Every event in the run therefore
    shares one continuity, so ``compare_order`` resolves *every* adjacent pair — including
    cross-lane pairs — by ``source_native_sequence``. Per-symbol continuities would make each
    cross-lane pair ``same_continuity=False`` and hence ``AMBIGUOUS``: ordering detection disabled
    exactly at the boundary multi-symbol introduces. The engine core is untouched as a consequence,
    not as a goal (design #37 §1.2/§1.3).

    ⚠ **This driver occupies the core's single ``Transmit`` slot.** It is passed as
    ``transmit=`` and demultiplexes each hand-off onto the lane currently being processed — see
    :meth:`__call__`. Handing the core one *shared* fill model instead would stamp every fill with
    one instrument key and match settlements across symbols by a lane-local bar index, which is
    silent contamination rather than a visible failure (design #37 §3.2/§5-T10).

    What this driver does **not** do is as load-bearing as what it does: it constructs no core, no
    ledger and no registry (they are injected, and an AST canary proves the package builds none),
    it re-authors no sequencer step, it holds no net position, and it releases no capacity — a
    lane that has sent stays occupied for the run, exactly as the single-symbol driver's scope does
    (``state.py:22``).
    """

    def __init__(
        self,
        *,
        converters: Mapping[InstrumentKey, CausalBarConverter],
        fill_models: Mapping[InstrumentKey, DeterministicFillModel],
        continuity_id: str,
        scenario_id: ScenarioId | None = None,
    ) -> None:
        """Wire the lanes.

        Args:
            converters: The per-lane causal converters, keyed by instrument. The mapping's
                iteration order is the lane declaration order.
            fill_models: The per-lane deterministic fill bands, keyed by the **same** instruments.
                Slice-scope judgement: a lane's re-injection source is a
                :class:`~tos.backtest.fills.DeterministicFillModel`. The
                :class:`~tos.backtest.fills.GatewayResultReinjector` is deliberately out of scope
                here, because draining a send boundary's retained results collapses symbol
                attribution (design #37 §3.2/§7-8).
            continuity_id: The **single** stream continuity every lane's coordinates are issued on
                (design #37 §3.4).
            scenario_id: The mandated scenario this run realizes, recorded run-level.

        Raises:
            BacktestIntegrityError: If the converter and fill-model lane sets differ, or if a
                converter's own declared scope disagrees with the key it is filed under — the lane
                key is read off the converter, never asserted alongside it (구조 파생 > 자기신고).
        """
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

    # -- the single Transmit slot, demultiplexed -----------------------------

    def __call__(self, attempt: AttemptRequest) -> SendHandoff:
        """Hand ``attempt`` to the **current lane's** fill band (design #37 §3.2, the C1 seam).

        The core has one ``transmit`` slot and the ``AttemptRequest`` it passes carries no
        instrument and no scope (``records.py:347-351``), so the lane cannot be recovered from the
        attempt. It is recovered from *processing position* instead, and that is sound because the
        core processes one event to completion before pulling the next (``core.py:1-3``): this
        driver's generator is suspended inside the very tick whose flow is calling here, so the
        current lane is the one bound immediately before that tick was yielded.

        Args:
            attempt: The engine's step-12 content-addressed attempt request.

        Returns:
            The current lane's :class:`~tos.engine.SendHandoff`, stamped by that lane's own fill
            band with that lane's ``instrument_key``.

        Raises:
            BacktestIntegrityError: If no lane is bound. Unreachable on the nominal path, and
                fail-closed rather than guessed: the sequencer records the raise as a
                ``TRANSMIT_RAISED`` halt with the reservation left ``POTENTIALLY_LIVE``
                (``sequencer.py:534-545``), the same treatment an unbound settlement context
                already gets (``fills.py:441-446``).
        """
        key = self._current_key
        if key is None:
            raise BacktestIntegrityError(
                "a hand-off arrived while no lane was bound — the multi-symbol driver demultiplexes "
                "the core's single Transmit slot by *which lane it is currently processing*, and an "
                "attempt carries no scope to fall back on (records.py:347-351). Guessing a lane "
                "here would stamp a fill with the wrong instrument (design #37 §3.2)"
            )
        return self._fill_models[key](attempt)

    # -- the interleaving EventSource ----------------------------------------

    def events(
        self, lanes: Sequence[tuple[InstrumentKey, BarStream]]
    ) -> Iterator[EngineEvent]:
        """Yield every lane's events in one merged causal order (design #37 §3.2/§3.3).

        Per merged ``(key, bar)``, the shape is the single-symbol one applied to that lane — the
        same private steps, not a second transcription (design #37 §3.1):

        1. bind the lane as **current**, so the core's single ``transmit`` reaches its fill band;
        2. bind the bar as that lane's settlement context and yield the stamped tick;
        3. the core processes the tick to completion (its hand-off lands in :meth:`__call__`);
        4. settle that lane's due fills, appending each record to the run-level accumulator **at
           settlement time** and yielding each stamped ``EGRESS_RESULT``.

        Step 4's accumulation order is the contract: ``LocalFillRecord`` carries no global order
        field and its ``settlement_bar_index`` is lane-local, so concatenating per-lane records
        after the run cannot reconstruct the global settlement order (design #37 §3.3).

        Args:
            lanes: The validated ``(key, stream)`` pairs for this run.

        Yields:
            The merged, interleaved engine events.

        Raises:
            BacktestIntegrityError: If a lane's converter and the merged order disagree about which
                bar comes next — a merge that reordered a lane's own stream.
        """
        ticks = {
            key: iter(self._converters[key].stream(stream)) for key, stream in lanes
        }
        for key, bar in merge_bar_streams(lanes):
            tick = next(ticks[key], None)
            if tick is None or tick.bar is not bar:  # pragma: no cover - merge is lane-preserving
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

    # -- the run -------------------------------------------------------------

    def run(
        self,
        core: EngineCore,
        streams: Mapping[InstrumentKey, Sequence[Bar] | None] | None,
    ) -> MultiSymbolBacktestRun:
        """Replay every lane through ``core`` and assemble the run's D-E3-local artifacts.

        Args:
            core: The **single** engine core for the whole run — one core for all N lanes, for the
                same reason one core serves all bars (design #33 §2.4).
            streams: The injected per-lane bar streams. ``None`` is fail-closed; ``{}`` is a defined
                zero-lane run; a lane mapped to ``None`` is fail-closed; a lane mapped to ``()`` is
                a defined empty lane (design #37 §3.6).

        Returns:
            The :class:`~tos.backtest.results.MultiSymbolBacktestRun`.

        Raises:
            CoreReinstantiationError: If a *different* core is supplied after this driver has run.
            BacktestIntegrityError: If the mapping or a lane stream is missing, if a lane stream is
                not causally ordered, or if the streams and the declared lanes do not correspond
                exactly.
        """
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
            trace=WiringTrace(continuity_id=self._counter.continuity_id, entries=entries),
            halts=halts,
            fill_records=tuple(self._fill_records),
            # No settlement moment orders these, so the order is declared rather than observed:
            # lanes in (account, instrument) order, each lane's pending fills in staging order
            # (design #37 §3.5). Sorting by key rather than by declaration order keeps it
            # independent of how the caller happened to build the mapping.
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
