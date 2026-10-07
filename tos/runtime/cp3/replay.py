"""The replay itself — one bar stream through ONE engine core, plus the per-bar trace.

Part of the CP-3 B1b runner (``cp3`` package). The runner was one module until the
2026-10-08 review: at 1,820 lines it broke ``config/tos_size_budget.yaml``'s
1,000-line module cap and its 100-line function cap three times over, and
registering four day-one exceptions against a budget whose own header calls
registration "가시성, 면허가 아니라" would have been the wrong answer for NEW code.
So the module was decomposed along the seams it already had, and
``tos/runtime/cp3`` was added to that budget's ``scope`` so the caps are actually
enforced here (the review's fourth gate).

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*``, no clock, no RNG, no ``subprocess``, no network. Intra-package
imports are RELATIVE — the allowlist does not name ``cp3``, so an absolute
``import cp3.…`` from a file under ``tos/`` is a TOS-FW-A violation while a
relative import carries no absolute name for the gate to classify.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from tos.backtest import BacktestDriver as _BacktestDriver
from tos.backtest import (
    BarTimeProjection,
    CausalBarConverter,
    DeterministicFillModel,
    FillMode,
    FillParameters,
    FillSide,
    NonBrokerTransportNature,
    SyntheticNonLivePreconditions,
)
from tos.backtest import trace_digest as _trace_digest
from tos.backtest.results import BacktestRun
from tos.canonical import EV_L1_PROVISIONAL_VERSION
from tos.engine import (
    EngineConfiguration,
    EngineCore,
    EventKind,
    HaltReason,
    RecordingEvidenceSink,
    provisional_stage_map,
)
from tos.time import HealthState, SessionContext

from . import __version__ as CP3_VERSION
from ._base import SCHEME, Cp3RunnerRefusal
from .bars import build_bars
from .contract import FieldRecord
from .seam import Cp3CapsuleSource, Cp3FieldResolver
from .strategy import LoadedStrategyContent

__all__ = [
    "DEFAULT_BUDGET_STEPS",
    "DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE",
    "PROVISIONAL_TIME_BOUNDS",
    "RunArtifacts",
    "run_replay",
]

# ===========================================================================
# The run
# ===========================================================================

#: The bounds this module injects into the harness. ``tos.backtest`` hardcodes
#: none (design #33 §10) and names its caller as the injection site — this is
#: that site, so the literals live here by design. What they are NOT is uniformly
#: "injected and therefore fine", so each one's status is stated (2026-10-08
#: review item 17 — the previous docstring blurred the three):
#:
#: * ``max_age_bound = 1000`` is the ONLY value bound 1:1 to an APPROVED
#:   VERIFICATION-PROFILE-002 key — ``MAX_time_conservative_freshness_age_ms``,
#:   registered and valued 1000 ms on 2026-09-04 (UNCHK-024 disposition).
#: * ``future_tolerance`` and ``maximum_consumer_age_ms`` are bound 1:1 to
#:   profile keys (``MAX_future_timestamp_tolerance_ms``,
#:   ``MAX_critical_input_consumer_receipt_age_ms``) but the values used here are
#:   **this module's own**, not reads of the profile — the profile binding is on
#:   the FIELD, not on these numbers.
#: * ``delay_bounds = (5,)`` is a **deliberate under-use** of a composite bind:
#:   ``BarTimeProjection`` binds the field to the SUM of four ADR-002-008 §9
#:   delay-class keys, and the profile carries 50 ms each (200 ms total), which
#:   this single 5 does not reproduce. It is kept because ``freshness_verdict``
#:   sums the tuple unconditionally and a *smaller* total is the restrictive
#:   direction for the FRESH gate — i.e. the run is judged under a tighter
#:   freshness budget than the profile allows, never a looser one. Reproducing
#:   the profile's 4x50 would be the faithful choice for a paper comparison and
#:   is left to B3, where the comparison is actually made.
#: * ``source_age`` / ``snapshot_age_bound`` / ``interval_width`` /
#:   ``boundary_lag`` / ``health_state`` are **structurally not profile keys at
#:   all** (``BarTimeProjection``'s own docstring: a bar-derived observation, a
#:   derived composite, a reference-frame construction parameter, or an enum —
#:   never a ``MAX_*``/``MIN_*`` threshold a key could hold).
#:
#: The values are the ones the shipped canary suite injects
#: (``tos/tests/backtest/_backtest_fixtures.py::time_projection``), i.e. bounds
#: that positively admit. A run built on them closes no EV, which this harness
#: already declares for four independent reasons.
PROVISIONAL_TIME_BOUNDS: Mapping[str, Any] = {
    "source_age": 10,
    "delay_bounds": (5,),
    "max_age_bound": 1000,
    "future_tolerance": 50,
    "snapshot_age_bound": 20,
    "maximum_consumer_age_ms": 1000,
    "interval_width": 2,
    "boundary_lag": 10,
}

#: The default DSL work-step budget. Source:
#: ``config/tos_runtime/paper/engine.yaml`` 26행
#: ``dsl_evaluation_budget_steps: 64``. Overridable on the CLI so the value
#: stays injected rather than owned here.
DEFAULT_BUDGET_STEPS = 64

#: The default at-most-one-unresolved-send bound. Source: the same paper
#: ``engine.yaml`` discipline the shipped suite injects (1) — and the B4 cap
#: this run demonstrates (kickoff §3 B4 / design #33 §2.2-§2.3).
DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

#: The two stand-in bindings the Coordinator's step-12 attempt request consumes.
#: NON-AUTHORITATIVE PROVISIONAL, exactly as ``provisional_stage_map`` declares.
_PROOF_DIGEST = "cp3-b1b-provisional-conformance-proof"
_PERMIT_IDENTITY = "cp3-b1b-provisional-action-flow-permit"


@dataclass(frozen=True)
class RunArtifacts:
    """One replay's outputs — the trace lines, the counts, and the digests."""

    run: BacktestRun
    #: One JSON-native mapping per bar, in bar order.
    trace_lines: tuple[dict[str, Any], ...]
    trace_digest: str
    #: The one producer identity every line carried (``read_field_records``
    #: refuses a file that mixes two) — recorded so the lineage block can name
    #: the parent's producer by VALUE rather than by a pointer string.
    source_id: str
    #: How many JSONL records were read.
    bars_read: int
    #: How many bars actually reached the core as a ``DECISION_TICK`` — counted
    #: from the trace, **not** from ``BacktestRun.bars_consumed``, which is
    #: ``len(stream)`` by construction (``driver.py`` 565행) and would therefore
    #: reconcile against ``bars_read`` vacuously.
    bars_driven: int
    #: ``BacktestRun.bars_consumed``, recorded as the harness reports it.
    bars_consumed_reported: int
    outcome_counts: Mapping[str, int]
    rule_fire_counts: Mapping[str, int]
    capacity_denials: int
    halt_counts: Mapping[str, int]
    #: Every bar whose decision actually reached the send boundary, in processing
    #: order — empty for a run in which none did. Recorded explicitly because the
    #: B4 cap spends its order budget on the **first firing(s) of ANY rule**,
    #: which need not be entries: reading "handoffs=1" beside "ACTION=N" invites
    #: the misreading that an entry was realized.
    #:
    #: A LIST, not a single slot (2026-10-08 review item 6): the budget is
    #: ``max_unresolved_send_per_scope``, which is **injected** on the CLI, so a
    #: run with the bound at 2 legitimately realizes two orders. The previous
    #: revision hardcoded at-most-one and would have refused such a run as a
    #: seal breach — a guard accusing a correctly-configured run.
    realized_orders: tuple[Mapping[str, Any], ...]


def _session_template() -> SessionContext:
    """The injected calendar/session determination — never recomputed here.

    ``is_open=True`` with ``phase="CONTINUOUS"`` is an **injected** stance, not
    a derivation from the bars: the kernel reads no market hours and
    ``session_token`` stays opaque. The bars are a replay of a session that did
    trade; asserting the phase here is how the harness states that rather than
    inferring it.
    """
    return SessionContext(
        tz_id="Asia/Seoul",
        tz_db_version="injected-provisional",
        trading_calendar_version="injected-provisional",
        phase="CONTINUOUS",
        is_open=True,
        tz_version_conflict=False,
        boundary_value=0,
    )


def _outcome_rationale(result: Any) -> str | None:
    """The emitted outcome's rationale, or ``None`` when nothing was emitted."""
    pipeline = getattr(result, "pipeline", None)
    if pipeline is None:
        return None
    outcome = pipeline.outcome
    if outcome is None:
        return None
    return getattr(outcome, "rationale", None)


def _wire(
    *,
    records: Sequence[FieldRecord],
    content: LoadedStrategyContent,
    budget_steps: int,
    max_unresolved_send_per_scope: int,
) -> tuple[Any, Any, Any, dict[int, FieldRecord]]:
    """Build the bar stream, the converter/driver, and the ONE engine core.

    Split from :func:`run_replay` for the 100-line function cap
    ``config/tos_size_budget.yaml`` enforces over this tree. The split is along a
    real seam: everything here is wiring (pure construction from injected
    values), everything left in ``run_replay`` is the run and its trace.

    Returns:
        ``(driver, core, bars, by_bar_index)``.
    """
    bars, by_bar_index = build_bars(records)
    resolver = Cp3FieldResolver(
        records_by_snapshot_id={record.snapshot_id: record for record in records}
    )
    converter = CausalBarConverter(
        instrument_key=content.instrument_key,
        resolver=resolver,
        capsule_source=Cp3CapsuleSource(
            instrument_key=content.instrument_key,
            direction=content.direction,
            records_by_bar_index=by_bar_index,
        ),
        time_projection=BarTimeProjection(
            session_template=_session_template(),
            health_state=HealthState.TRUSTED,
            **PROVISIONAL_TIME_BOUNDS,
        ),
    )
    fill_model = DeterministicFillModel(
        instrument_key=content.instrument_key,
        # ACKNOWLEDGE carries no magnitude and no price (records.py 201-207행):
        # the B4 disposition is "체결 비교 포기", so inventing a settlement
        # price for a comparison that will not use it would be a phantom.
        parameters=FillParameters(mode=FillMode.ACKNOWLEDGE, side=FillSide.BUY),
        scenario_id=None,
    )
    driver = _BacktestDriver(
        converter=converter,
        fill_model=fill_model,
        continuity_id=f"cp3-b1b:{content.instrument_key.instrument}",
        # No mandated ScenarioId: this run is not one of design #33 §5.1's seven
        # rows, and labelling it with one would claim a scenario it does not
        # realize.
        scenario_id=None,
    )
    core = EngineCore(
        registry=content.registry,
        stages=provisional_stage_map(
            conformance_proof_digest=_PROOF_DIGEST,
            action_flow_permit_identity=_PERMIT_IDENTITY,
        ),
        configuration=EngineConfiguration(
            dsl_evaluation_budget_steps=budget_steps,
            max_unresolved_send_per_scope=max_unresolved_send_per_scope,
            canonicalization_version=EV_L1_PROVISIONAL_VERSION,
            enforcement_mechanism_version=CP3_VERSION,
        ),
        preconditions=SyntheticNonLivePreconditions(authority_epoch_current=True),
        transmit=fill_model,
        transport_nature=NonBrokerTransportNature(),
        sink=RecordingEvidenceSink(),
    )
    return driver, core, bars, by_bar_index


def _trace_line(
    *,
    record: FieldRecord,
    bar_index: int,
    entry: Any,
    flow: Any,
    pipeline_halt: Any,
    flow_halt: Any,
    denied: bool,
    rule_id: str,
    kind_label: str,
) -> dict[str, Any]:
    """One bar's trace line — the artifact B3 reads, bar by bar.

    Split from :func:`run_replay` for the 100-line function cap
    ``config/tos_size_budget.yaml`` enforces over this tree. The decision kind
    and the capacity denial are recorded as TWO independent facts on purpose: a
    FLAT that was denied is still a FLAT, and collapsing them would make the B4
    cap indistinguishable from the rule not firing.
    """
    return {
        "raw_event_id": record.raw_event_id,
        "as_of_ms": record.as_of_ms,
        "bar_index": bar_index,
        "outcome_kind": kind_label,
        "rule_id": rule_id,
        "pipeline_halt_reason": (
            None if pipeline_halt is None else pipeline_halt.value
        ),
        "flow_halt_reason": None if flow_halt is None else flow_halt.value,
        "flow_halt_step": (
            None if flow is None or flow.halt_step is None else flow.halt_step.value
        ),
        "capacity_denied": denied,
        "handed_off": entry.handed_off,
        "ordering_admission": entry.ordering_admission.value,
        "yield_sequence": entry.yield_sequence,
        "proposal_digest": entry.proposal_digest,
        "outcome_digest": entry.outcome_digest,
        "trace_entry_digest": SCHEME.compute_digest(entry.model_dump(mode="json")),
    }


@dataclass(frozen=True)
class _Collected:
    """What one pass over the trace produced, before the run-level refusals."""

    lines: list[dict[str, Any]]
    outcome_counts: dict[str, int]
    rule_fire_counts: dict[str, int]
    halt_counts: dict[str, int]
    capacity_denials: int
    no_outcome_bars: list[str]
    realized_orders: list[dict[str, Any]]


def _attribute_rule(
    *,
    result: Any,
    record: FieldRecord,
    content: LoadedStrategyContent,
    no_outcome_bars: list[str],
) -> tuple[str, str]:
    """Map the emitted outcome back to ``(rule id, decision kind)``.

    No re-evaluation of the policy happens anywhere in this package — the engine
    stays the only evaluator. The emitted outcome's rationale is looked up in the
    index built from the authored file, so an attribution this function cannot
    make is a refusal rather than a guess.

    Split from :func:`_collect_trace` for the 100-line function cap.
    """
    rationale = _outcome_rationale(result)
    if rationale is None:
        # Recorded, then refused after the loop. A tick that emitted no
        # outcome at all (a Coordinator-gate refusal, a withheld decision, a
        # budget degradation) is NOT a decision this trace can compare: B3
        # would read "NO_OUTCOME" as a third decision kind beside
        # NO_ACTION/ACTION/FLAT, which it is not. Collected rather than
        # raised inline so the refusal can name how many bars and which
        # first, instead of stopping at the first one.
        no_outcome_bars.append(record.raw_event_id)
        rule_id, kind_label = "none", "NO_OUTCOME"
    else:
        resolved = content.rule_index.get(rationale)
        if resolved is None:
            raise Cp3RunnerRefusal(
                f"{record.raw_event_id}: the emitted outcome's rationale "
                f"{rationale!r} is not one the authored policy declares — "
                "rule attribution must come from the strategy file, never "
                "from a runner-side guess"
            )
        rule_id, kind = resolved
        kind_label = kind.value
    return rule_id, kind_label


def _collect_trace(
    *,
    run: BacktestRun,
    by_bar_index: Mapping[int, FieldRecord],
    content: LoadedStrategyContent,
    max_unresolved_send_per_scope: int,
) -> _Collected:
    """Walk the run's trace once and build every per-bar line and tally.

    Split from :func:`run_replay` for the 100-line function cap
    ``config/tos_size_budget.yaml`` enforces over this tree. It raises only the
    refusals that are decidable mid-walk (an unattributable entry, a rationale
    the policy never declared, a hand-off past the injected budget); the
    run-level refusals stay in ``run_replay``, which can see the totals.
    """
    lines: list[dict[str, Any]] = []
    outcome_counts: dict[str, int] = {}
    rule_fire_counts: dict[str, int] = {}
    halt_counts: dict[str, int] = {}
    capacity_denials = 0
    no_outcome_bars: list[str] = []
    realized_orders: list[dict[str, Any]] = []
    for entry, result in zip(run.trace.entries, run.event_results):
        if entry.event_kind is not EventKind.DECISION_TICK:
            continue
        bar_index = entry.bar_index
        if bar_index is None:  # pragma: no cover - a tick entry always carries one
            raise Cp3RunnerRefusal(
                "a DECISION_TICK trace entry carries no bar_index — the trace "
                "could not be attributed to a bar"
            )
        record = by_bar_index[bar_index]
        rule_id, kind_label = _attribute_rule(
            result=result,
            record=record,
            content=content,
            no_outcome_bars=no_outcome_bars,
        )
        flow = getattr(result, "flow", None)
        flow_halt = None if flow is None else flow.halt_reason
        denied = flow_halt is HaltReason.AT_MOST_ONE_EXPOSURE_HELD
        if denied:
            capacity_denials += 1
        pipeline_halt = None if result.pipeline is None else result.pipeline.halt_reason
        outcome_counts[kind_label] = outcome_counts.get(kind_label, 0) + 1
        rule_fire_counts[rule_id] = rule_fire_counts.get(rule_id, 0) + 1
        if entry.handed_off:
            realized_orders.append(
                {
                    "raw_event_id": record.raw_event_id,
                    "bar_index": bar_index,
                    "rule_id": rule_id,
                    "outcome_kind": kind_label,
                }
            )
            if len(realized_orders) > max_unresolved_send_per_scope:
                raise Cp3RunnerRefusal(
                    f"{record.raw_event_id}: hand-off #{len(realized_orders)} "
                    "reached the send boundary but the injected "
                    "max_unresolved_send_per_scope is "
                    f"{max_unresolved_send_per_scope} — the capacity seal did "
                    "not hold, which would mean the capacity denials recorded "
                    "beside it are not what they appear. (The bound is the "
                    "injected one, never a hardcoded 1: a run configured with a "
                    "larger budget realizes that many orders legitimately.)"
                )
        # Counted ONCE per bar per distinct reason: ``result.halt_reason`` is
        # the core's own restatement of whichever stage halted, so adding all
        # three sources naively double-counts every halt.
        for reason in {
            value
            for value in (pipeline_halt, flow_halt, result.halt_reason)
            if value is not None
        }:
            halt_counts[reason.value] = halt_counts.get(reason.value, 0) + 1
        lines.append(
            _trace_line(
                record=record,
                bar_index=bar_index,
                entry=entry,
                flow=flow,
                pipeline_halt=pipeline_halt,
                flow_halt=flow_halt,
                denied=denied,
                rule_id=rule_id,
                kind_label=kind_label,
            )
        )
    return _Collected(
        lines=lines,
        outcome_counts=outcome_counts,
        rule_fire_counts=rule_fire_counts,
        halt_counts=halt_counts,
        capacity_denials=capacity_denials,
        no_outcome_bars=no_outcome_bars,
        realized_orders=realized_orders,
    )


def run_replay(
    *,
    records: Sequence[FieldRecord],
    content: LoadedStrategyContent,
    budget_steps: int = DEFAULT_BUDGET_STEPS,
    max_unresolved_send_per_scope: int = DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE,
) -> RunArtifacts:
    """Drive ``records`` through one engine core and assemble the trace.

    Args:
        records: The validated field records.
        content: The admitted strategy content.
        budget_steps: The injected ``dsl_evaluation_budget_steps``.
        max_unresolved_send_per_scope: The injected at-most-one send bound.

    Returns:
        The :class:`RunArtifacts`.

    Raises:
        Cp3RunnerRefusal: The JSONL's instrument disagrees with the strategy's
            declared dispatch scope, the authored policy does not fit the
            injected budget, or any per-bar refusal from the Capsule source /
            resolver.
    """
    instrument = records[0].instrument
    if instrument != content.instrument_key.instrument:
        raise Cp3RunnerRefusal(
            f"the fields JSONL carries instrument {instrument!r} but "
            f"{content.strategy_path} declares dispatch instrument "
            f"{content.instrument_key.instrument!r} — a replay never retargets a "
            "strategy at another instrument"
        )
    if content.work_steps > budget_steps:
        raise Cp3RunnerRefusal(
            f"{content.strategy_path}: policy_work_steps={content.work_steps} "
            f"exceeds the injected dsl_evaluation_budget_steps={budget_steps}; "
            "the engine would fold every tick to DEGRADED_BOUND_EXHAUSTED"
        )

    driver, core, bars, by_bar_index = _wire(
        records=records,
        content=content,
        budget_steps=budget_steps,
        max_unresolved_send_per_scope=max_unresolved_send_per_scope,
    )
    run = driver.run(core, bars)

    collected = _collect_trace(
        run=run,
        by_bar_index=by_bar_index,
        content=content,
        max_unresolved_send_per_scope=max_unresolved_send_per_scope,
    )
    lines = collected.lines
    no_outcome_bars = collected.no_outcome_bars
    if no_outcome_bars:
        raise Cp3RunnerRefusal(
            f"{len(no_outcome_bars)} of {len(records)} bar(s) produced no "
            f"outcome at all (first: {no_outcome_bars[0]}) — a tick that emitted "
            "no Decision is not a decision this trace can compare, and an "
            "all-halt run would otherwise exit 0 with every reconciliation "
            "satisfied. Fix the wiring (stage map, Coordinator gates, budget) "
            "rather than publishing a trace of nothing."
        )
    if len(lines) != len(records):
        raise Cp3RunnerRefusal(
            f"the core produced {len(lines)} DECISION_TICK result(s) for "
            f"{len(records)} record(s) — a replay that did not reach every bar "
            "is not a replay of this dataset, and reporting the stream length "
            "as the driven count would hide it"
        )
    return RunArtifacts(
        run=run,
        source_id=records[0].source_id,
        trace_lines=tuple(lines),
        trace_digest=_trace_digest(run, scheme=SCHEME),
        bars_read=len(records),
        bars_driven=len(lines),
        bars_consumed_reported=run.bars_consumed,
        outcome_counts=dict(sorted(collected.outcome_counts.items())),
        rule_fire_counts=dict(sorted(collected.rule_fire_counts.items())),
        capacity_denials=collected.capacity_denials,
        halt_counts=dict(sorted(collected.halt_counts.items())),
        realized_orders=tuple(collected.realized_orders),
    )
