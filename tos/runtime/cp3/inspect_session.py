"""``sts tos inspect`` core — «왜 이 바에서 이 결정이었나», per recorded bar."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tos.dsl import (
    POSITION_NAMESPACE,
    VALUE_NAMESPACE,
    DecisionPolicy,
    Operand,
    PositionSide,
    ScalarValue,
)
from tos.dsl.vocabulary import eval_compare, evaluate_policy, resolve_operand
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal
from tos_runtime.strategy.resolve import POSITION_DSL_FIELDS

from ._base import Cp3RunnerRefusal
from .inspect_evidence import BarEvidence, read_bar_evidence
from .inspect_report import (
    ENGINE_OUTCOME_SHAPES,
    EVALUATION_ENGINE_VIEW,
    EVALUATION_JOURNAL_ONLY,
    EVALUATION_JOURNAL_UNJOINED,
    EVALUATION_WITHHELD,
    BarRow,
    CompareSummary,
    CompareView,
    InspectReport,
    RuleSummary,
    RuleView,
    halt_label,
    render_json,
    render_text,
    value_text,
)
from .position_sim import (
    POSITION_MODE_RECORDED,
    POSITION_MODE_SIMULATED,
    PositionSimulation,
    SimulationConfig,
    load_simulation_config,
)
from .strategy import LoadedStrategyContent, load_strategy_content

__all__ = [
    "DISPLAY_TZ_ID",
    "inspect_session",
    "main",
]

DISPLAY_TZ_ID = "Asia/Seoul"

_CAPSULE_VALUE_PREFIX: tuple[str, ...] = ("capsule", VALUE_NAMESPACE)
_CAPSULE_POSITION_PREFIX: tuple[str, ...] = ("capsule", POSITION_NAMESPACE)
_CONFIG_PREFIX: tuple[str, ...] = ("config",)

_BAR_KEY_STAMP_FORMAT = "%Y%m%dT%H%M%S%z"

_BAR_KEY_SEPARATOR = ":1m:"

_NO_ACTION_KIND = "NO_ACTION"


def _operand_text(operand: Operand) -> str:
    """The authored operand, as the legend prints it."""
    if operand.ref is None:
        return value_text(operand.const)
    path = tuple(operand.ref)
    if path[: len(_CAPSULE_VALUE_PREFIX)] == _CAPSULE_VALUE_PREFIX:
        return ".".join(path[len(_CAPSULE_VALUE_PREFIX) :])
    if path[: len(_CAPSULE_POSITION_PREFIX)] == _CAPSULE_POSITION_PREFIX:
        return ".".join(path[len(_CAPSULE_POSITION_PREFIX) - 1 :])
    return ".".join(path)


def _compare_expression(left: Operand, op: str, right: Operand) -> str:
    """One comparison as a single legend line."""
    return f"{_operand_text(left)} {op} {_operand_text(right)}"


def _refuse_unsupported_refs(policy: DecisionPolicy, *, strategy_path: Path) -> None:
    """Refuse a policy whose operands this environment shape cannot resolve."""
    for position, rule in enumerate(policy.rules, start=1):
        for index, compare in enumerate(rule.all_of, start=1):
            for operand in (compare.left, compare.right):
                if operand.ref is None:
                    continue
                path = tuple(operand.ref)
                supported = (
                    (
                        len(path) == len(_CAPSULE_VALUE_PREFIX) + 1
                        and path[: len(_CAPSULE_VALUE_PREFIX)] == _CAPSULE_VALUE_PREFIX
                    )
                    or (
                        len(path) == len(_CAPSULE_POSITION_PREFIX) + 1
                        and path[: len(_CAPSULE_POSITION_PREFIX)]
                        == _CAPSULE_POSITION_PREFIX
                        and path[-1] in POSITION_DSL_FIELDS
                    )
                    or (
                        len(path) == len(_CONFIG_PREFIX) + 1
                        and path[: len(_CONFIG_PREFIX)] == _CONFIG_PREFIX
                    )
                )
                if not supported:
                    raise Cp3RunnerRefusal(
                        f"{strategy_path}: rule #{position} compare #{index} names "
                        f"operand ref {path} — this inspector builds only "
                        f"capsule.{VALUE_NAMESPACE}.<key>, "
                        f"capsule.{POSITION_NAMESPACE}.<one of "
                        f"{sorted(POSITION_DSL_FIELDS)}> and config.<key>, so that "
                        "ref would resolve to UNKNOWN and print as a failed "
                        "comparison for a value never built. Refusing instead."
                    )


def _environment(
    values: Mapping[str, ScalarValue],
    bindings: Mapping[str, ScalarValue],
    position: Mapping[str, ScalarValue] | None = None,
) -> dict[str, object]:
    """The Decision Context environment for one bar, in ``build_environment``'s shape."""
    capsule: dict[str, object] = {VALUE_NAMESPACE: dict(values)}
    # SAFETY: the position goes under the SAME reserved capsule key the kernel's build_environment merges it into — a differently-placed namespace would make every authored capsule.position.* comparison UNKNOWN here while live resolved it
    if position is not None:
        capsule[POSITION_NAMESPACE] = dict(position)
    return {"capsule": capsule, "config": dict(bindings)}


def _view_diff(
    view: Mapping[str, ScalarValue], fields: Mapping[str, ScalarValue]
) -> dict[str, tuple[str, str]]:
    """``field_key -> (view, journal)`` for every key the two disagree on."""
    diff: dict[str, tuple[str, str]] = {}
    for key in sorted(set(view) | set(fields)):
        left, right = view.get(key), fields.get(key)
        if left is right:
            continue
        if type(left) is type(right) and left == right:
            continue
        diff[key] = (value_text(left), value_text(right))
    return diff


def _evaluate_rules(
    policy: DecisionPolicy,
    env: dict[str, object],
    rule_index: Mapping[str, tuple[str, object]],
) -> tuple[RuleView, ...]:
    """Evaluate every rule's guard on one bar, comparison by comparison."""
    views: list[RuleView] = []
    for position, rule in enumerate(policy.rules, start=1):
        compares: list[CompareView] = []
        for index, compare in enumerate(rule.all_of, start=1):
            compares.append(
                CompareView(
                    index=index,
                    expression=_compare_expression(
                        compare.left, str(compare.op), compare.right
                    ),
                    left_value=value_text(resolve_operand(compare.left, env)),
                    right_value=value_text(resolve_operand(compare.right, env)),
                    passed=eval_compare(compare, env),
                )
            )
        rule_id, _kind = rule_index[rule.decision.rationale]
        views.append(
            RuleView(
                position=position,
                label=f"R{position}",
                rule_id=rule_id,
                decision_kind=str(rule.decision.kind),
                fired=all(view.passed for view in compares),
                compares=tuple(compares),
            )
        )
    return tuple(views)


def _bar_clock(raw_event_id: str, as_of_ms: int) -> tuple[str, str, int]:
    """One bar's ``(HH:MM, time source, minutes since KST midnight)``."""
    parts = raw_event_id.split(_BAR_KEY_SEPARATOR, 1)
    try:
        labelled = datetime.strptime(parts[1], _BAR_KEY_STAMP_FORMAT)
    except (IndexError, ValueError):
        derived = datetime.fromtimestamp(as_of_ms / 1000, tz=ZoneInfo(DISPLAY_TZ_ID))
        return f"~{derived:%H:%M}", "as_of_ms", derived.hour * 60 + derived.minute
    local = labelled.astimezone(ZoneInfo(DISPLAY_TZ_ID))
    return f"{local:%H:%M}", "raw_event_id", local.hour * 60 + local.minute


def _parse_window(value: str | None, *, flag: str) -> int | None:
    """``HH:MM`` as minutes since KST midnight, or ``None``."""
    if value is None:
        return None
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise Cp3RunnerRefusal(f"{flag} must be HH:MM (got {value!r})")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise Cp3RunnerRefusal(f"{flag} must be a valid HH:MM time (got {value!r})")
    return hour * 60 + minute


def _in_window(minutes: int, low: int | None, high: int | None) -> bool:
    """Whether a bar's labelled KST minute falls in the inclusive ``[low, high]``."""
    if low is not None and minutes < low:
        return False
    return not (high is not None and minutes > high)


@dataclass(frozen=True)
class _JournalBar:
    """One in-window journal line, with its labelled clock already derived."""

    raw_event_id: str
    as_of_ms: int
    time_kst: str
    time_source: str
    fields: Mapping[str, ScalarValue]


def _read_bars(
    journal_path: Path, instrument: str, low: int | None, high: int | None
) -> tuple[_JournalBar, ...]:
    """The in-window journal bars, oldest first."""
    try:
        observations = JsonLinesObservationJournal(journal_path).poll(
            instrument=instrument, after_as_of_ms=None
        )
    except JournalError as exc:
        raise Cp3RunnerRefusal(f"journal refused: {exc}") from exc
    clocked = [
        (observation, _bar_clock(observation.raw_event_id, observation.as_of_ms))
        for observation in observations
    ]
    bars = tuple(
        _JournalBar(
            raw_event_id=observation.raw_event_id,
            as_of_ms=observation.as_of_ms,
            time_kst=time_kst,
            time_source=time_source,
            fields=dict(observation.fields),
        )
        for observation, (time_kst, time_source, minutes) in clocked
        if _in_window(minutes, low, high)
    )
    if not bars:
        raise Cp3RunnerRefusal(
            f"{journal_path}: no bar for instrument {instrument!r} falls in the "
            "requested window — an empty table would not say whether the window "
            "or the instrument was wrong"
        )
    return bars


def _engine_shape(evidence: BarEvidence | None) -> str | None:
    """``"no_action"`` / ``"proposal"`` from the recorded outcome, or ``None``."""
    if evidence is None or not evidence.joined or evidence.outcome_type is None:
        return None
    return ENGINE_OUTCOME_SHAPES.get(evidence.outcome_type)


def _evaluation_source(
    bar: _JournalBar, evidence: BarEvidence | None, *, evidence_asked: bool
) -> tuple[str, dict[str, ScalarValue]]:
    """``(evaluation source, the values the rules are evaluated on)`` for one bar."""
    if evidence is not None and evidence.withheld:
        return EVALUATION_WITHHELD, {}
    if evidence is not None and evidence.joined and evidence.value_view:
        return EVALUATION_ENGINE_VIEW, dict(evidence.value_view)
    if not evidence_asked:
        return EVALUATION_JOURNAL_ONLY, dict(bar.fields)
    return EVALUATION_JOURNAL_UNJOINED, dict(bar.fields)


@dataclass(frozen=True)
class _BarPosition:
    """One bar's position inputs, as the environment and the row both carry them."""

    values: Mapping[str, ScalarValue] | None = None
    absent_reason: str | None = None
    source: str | None = None


def _simulated_position(
    simulation: PositionSimulation, bar: _JournalBar
) -> tuple[_BarPosition, int | None]:
    """``(this bar's simulated position, its declared price)`` — nothing is applied yet."""
    price = simulation.price_of(bar.fields)
    context, reason = simulation.context(
        price=price, as_of_ms=bar.as_of_ms, raw_event_id=bar.raw_event_id
    )
    return (
        _BarPosition(
            values=None if context is None else context.as_environment_mapping(),
            absent_reason=reason,
            source=POSITION_MODE_SIMULATED,
        ),
        price,
    )


def _recorded_position(evidence: BarEvidence | None) -> _BarPosition:
    """The position the ENGINE read for this bar, straight off its inbox payload."""
    if evidence is None:
        return _BarPosition(source=POSITION_MODE_RECORDED)
    return _BarPosition(
        values=evidence.position_context,
        absent_reason=evidence.position_absent_reason,
        source=POSITION_MODE_RECORDED,
    )


def _bar_row(
    bar: _JournalBar,
    evidence: BarEvidence | None,
    policy: DecisionPolicy,
    bindings: Mapping[str, ScalarValue],
    rule_index: Mapping[str, tuple[str, object]],
    *,
    evidence_asked: bool,
    position: _BarPosition = _BarPosition(),
) -> BarRow:
    """Build one bar's row, evaluating on the inputs the engine itself used."""
    evaluation, values = _evaluation_source(
        bar, evidence, evidence_asked=evidence_asked
    )
    withheld = evaluation == EVALUATION_WITHHELD
    counted = evaluation in (EVALUATION_ENGINE_VIEW, EVALUATION_JOURNAL_ONLY)

    if withheld:
        rules: tuple[RuleView, ...] = ()
        rule_id: str | None = None
        kind: str | None = None
    else:
        env = _environment(values, bindings, position.values)
        decision = evaluate_policy(policy, env)
        rules = _evaluate_rules(policy, env, rule_index)
        rule_id, _registered = rule_index[decision.rationale]
        kind = str(decision.kind)

    shape = _engine_shape(evidence)
    own_shape = (
        None
        if kind is None
        else ("no_action" if kind == _NO_ACTION_KIND else "proposal")
    )
    return BarRow(
        raw_event_id=bar.raw_event_id,
        as_of_ms=bar.as_of_ms,
        time_kst=bar.time_kst,
        time_source=bar.time_source,
        fields=bar.fields,
        env_values=values,
        evaluation=evaluation,
        counted=counted,
        rules=rules,
        decision_rule_id=rule_id,
        decision_kind=kind,
        view_diff=(
            _view_diff(evidence.value_view, bar.fields)
            if evidence is not None and evidence.value_view
            else {}
        ),
        engine_shape=shape,
        decision_disagrees=(
            counted
            and shape is not None
            and own_shape is not None
            and shape != own_shape
        ),
        evidence=evidence,
        position=position.values,
        position_absent_reason=position.absent_reason,
        position_source=position.source,
    )


def _summarize(
    policy: DecisionPolicy,
    rows: Sequence[BarRow],
    rule_index: Mapping[str, tuple[str, object]],
) -> tuple[RuleSummary, ...]:
    """Per-rule firing and per-comparison failure counts over the COUNTED rows."""
    counted = [row for row in rows if row.counted]
    bars = len(counted)
    summaries: list[RuleSummary] = []
    for position, rule in enumerate(policy.rules, start=1):
        views = [row.rules[position - 1] for row in counted]
        compares = tuple(
            CompareSummary(
                index=index,
                expression=_compare_expression(
                    compare.left, str(compare.op), compare.right
                ),
                failed_bars=sum(
                    1 for view in views if not view.compares[index - 1].passed
                ),
                bars=bars,
            )
            for index, compare in enumerate(rule.all_of, start=1)
        )
        rule_id, _kind = rule_index[rule.decision.rationale]
        summaries.append(
            RuleSummary(
                position=position,
                label=f"R{position}",
                rule_id=rule_id,
                decision_kind=str(rule.decision.kind),
                fired_bars=sum(1 for view in views if view.fired),
                bars=bars,
                compares=compares,
            )
        )
    return tuple(summaries)


def _tally(values: Sequence[str]) -> dict[str, int]:
    """A count per distinct value, ordered by count then name."""
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


@dataclass(frozen=True)
class _Tallies:
    """The report's count blocks, folded over the rows in one pass."""

    outcome_counts: dict[str, int]
    halt_counts: dict[str, int]
    unjoined_counts: dict[str, int]
    view_refusal_counts: dict[str, int]
    view_diff_fields: dict[str, int]


def _tallies(rows: Sequence[BarRow]) -> _Tallies:
    """Fold the evidence-derived count blocks over ``rows``."""
    found = [row.evidence for row in rows if row.evidence is not None]
    joined = [item for item in found if item.joined]
    diff_fields: list[str] = []
    for row in rows:
        diff_fields.extend(row.view_diff)
    return _Tallies(
        outcome_counts=_tally(
            [item.outcome_type or item.withheld_reason or "-" for item in joined]
        ),
        halt_counts=_tally(
            [
                label
                for label in (halt_label(item) for item in joined)
                if label is not None
            ]
        ),
        unjoined_counts=_tally(
            [item.unjoined_reason for item in found if item.unjoined_reason is not None]
        ),
        view_refusal_counts=_tally(
            [
                item.value_view_refusal
                for item in found
                if item.value_view_refusal is not None
            ]
        ),
        view_diff_fields=_tally(diff_fields),
    )


def _build_report(
    rows: Sequence[BarRow],
    *,
    policy: DecisionPolicy,
    content: LoadedStrategyContent,
    instrument: str,
    journal_path: Path,
    data_dir: Path | None,
    window_from: str | None,
    window_to: str | None,
    session_name: str | None,
    position_mode: str | None = None,
    simulation: PositionSimulation | None = None,
    simulation_config: SimulationConfig | None = None,
) -> InspectReport:
    """Fold the evaluated rows into the report, counting each population once."""
    tallies = _tallies(rows)
    default_rule_id, _default_kind = content.rule_index[policy.default.rationale]
    return InspectReport(
        position_mode=position_mode,
        position_simulation=(
            None if simulation_config is None else simulation_config.as_json()
        ),
        position_absence_counts=(
            None
            if position_mode is None
            else _tally(
                [
                    row.position_absent_reason
                    for row in rows
                    if row.position_absent_reason is not None
                ]
            )
        ),
        round_trips=(
            ()
            if simulation is None
            else tuple(trip.as_json() for trip in simulation.round_trips)
        ),
        position_open_fill=None if simulation is None else simulation.open_fill,
        position_live_gap=None if simulation is None else simulation.live_gap,
        position_entry_refusals=(
            None if simulation is None else simulation.entry_refusals
        ),
        session_name=session_name or journal_path.parent.name,
        instrument=instrument,
        strategy_path=content.strategy_path,
        strategy_sha256=content.strategy_sha256,
        bindings_path=content.bindings_path,
        bindings=dict(content.bindings),
        data_dir=data_dir,
        window_from=window_from,
        window_to=window_to,
        default_rule_id=default_rule_id,
        default_decision_kind=str(policy.default.kind),
        bars=tuple(rows),
        rules=_summarize(policy, rows, content.rule_index),
        counted_bars=sum(1 for row in rows if row.counted),
        withheld_bars=sum(1 for row in rows if row.evaluation == EVALUATION_WITHHELD),
        substituted_bars=sum(
            1 for row in rows if row.evaluation == EVALUATION_JOURNAL_UNJOINED
        ),
        view_diff_bars=sum(1 for row in rows if row.view_diff),
        view_diff_fields=tallies.view_diff_fields,
        disagreement_bars=sum(1 for row in rows if row.decision_disagrees),
        not_comparable_bars=sum(
            1 for row in rows if row.counted and row.engine_shape is None
        ),
        decision_counts=_tally(
            [row.decision_rule_id for row in rows if row.decision_rule_id is not None]
        ),
        outcome_counts=tallies.outcome_counts,
        halt_counts=tallies.halt_counts,
        unjoined_counts=tallies.unjoined_counts,
        view_refusal_counts=tallies.view_refusal_counts,
    )


def _config_dir(bindings_path: Path) -> Path:
    """The tenant config dir — the one directory a boot derives both strategy paths from."""
    return bindings_path.parent


def _held_side(direction: str, *, strategy_path: Path) -> PositionSide:
    """The side a simulated fill holds — this deployment's one ACTION direction."""
    # SAFETY: an unnamed direction is refused, not defaulted to LONG — the DSL types target.direction as a free string, and a silently-assumed side would flip every unrealized figure a declared stop-loss is compared against
    if direction not in (PositionSide.LONG.value, PositionSide.SHORT.value):
        raise Cp3RunnerRefusal(
            f"{strategy_path}: its ACTION targets declare direction {direction!r}, which is "
            f"neither {PositionSide.LONG.value!r} nor {PositionSide.SHORT.value!r} — a "
            "simulated position cannot be given a side this inspector would have to guess"
        )
    return PositionSide(direction)


def _evaluate_bars(
    bars: Sequence[_JournalBar],
    evidence_by_bar: Mapping[str, BarEvidence],
    *,
    policy: DecisionPolicy,
    content: LoadedStrategyContent,
    evidence_asked: bool,
    position_mode: str | None,
    simulation: PositionSimulation | None,
) -> list[BarRow]:
    """Evaluate every bar in journal order, carrying the simulated position forward."""
    rows: list[BarRow] = []
    for bar in bars:
        evidence = evidence_by_bar.get(bar.raw_event_id)
        price: int | None = None
        position = _BarPosition()
        if simulation is not None:
            position, price = _simulated_position(simulation, bar)
        elif position_mode is not None:
            position = _recorded_position(evidence)
        row = _bar_row(
            bar,
            evidence,
            policy,
            content.bindings,
            content.rule_index,
            evidence_asked=evidence_asked,
            position=position,
        )
        rows.append(row)
        if simulation is not None:
            # SAFETY: the fill is applied AFTER this bar was evaluated — live reads the position when the tick is issued, before that bar's decision, so filling before evaluating would let an entry bar's own stop-loss fire on itself
            simulation.apply(
                decision_kind=row.decision_kind,
                rule_id=row.decision_rule_id,
                price=price,
                values=bar.fields,
                as_of_ms=bar.as_of_ms,
                raw_event_id=bar.raw_event_id,
                time_kst=bar.time_kst,
            )
    return rows


def inspect_session(
    *,
    journal_path: Path,
    strategy_path: Path,
    bindings_path: Path,
    data_dir: Path | None = None,
    window_from: str | None = None,
    window_to: str | None = None,
    session_name: str | None = None,
) -> InspectReport:
    """Inspect one recorded session's bars against its own authored policy."""
    declared = load_simulation_config(_config_dir(bindings_path))
    content = load_strategy_content(
        strategy_path=strategy_path,
        bindings_path=bindings_path,
        position_context_enabled=declared is not None,
    )
    policy = content.strategy.policy
    if policy is None:  # pragma: no cover - admission already refused this
        raise Cp3RunnerRefusal(f"{strategy_path}: strategy carries no policy")
    _refuse_unsupported_refs(policy, strategy_path=strategy_path)

    low = _parse_window(window_from, flag="--from")
    high = _parse_window(window_to, flag="--to")
    instrument = content.instrument_key.instrument
    bars = _read_bars(journal_path, instrument, low, high)

    evidence_by_bar: Mapping[str, BarEvidence] = (
        read_bar_evidence(data_dir, [bar.raw_event_id for bar in bars])
        if data_dir
        else {}
    )
    # SAFETY: a recorded session is never simulated — the stored payload is what the engine actually read, so re-deriving a position there would show per-compare verdicts for a holding the engine never saw and hide the very divergence this tool exists to find
    simulation = (
        PositionSimulation(
            declared,
            side=_held_side(content.direction, strategy_path=strategy_path),
        )
        if declared is not None and data_dir is None
        else None
    )
    position_mode = _position_mode(declared, simulation)
    rows = _evaluate_bars(
        bars,
        evidence_by_bar,
        policy=policy,
        content=content,
        evidence_asked=data_dir is not None,
        position_mode=position_mode,
        simulation=simulation,
    )
    return _build_report(
        rows,
        policy=policy,
        content=content,
        instrument=instrument,
        journal_path=journal_path,
        data_dir=data_dir,
        window_from=window_from,
        window_to=window_to,
        session_name=session_name,
        position_mode=position_mode,
        simulation=simulation,
        simulation_config=None if simulation is None else declared,
    )


def _position_mode(
    declared: SimulationConfig | None, simulation: PositionSimulation | None
) -> str | None:
    """``"simulated"`` / ``"recorded"``, or ``None`` when this tree enables no position."""
    if declared is None:
        return None
    return POSITION_MODE_SIMULATED if simulation is not None else POSITION_MODE_RECORDED


def _parser() -> argparse.ArgumentParser:
    """The CLI the legacy-side wrapper builds an argv for."""
    parser = argparse.ArgumentParser(
        prog="cp3.inspect_session",
        description=(
            "Read-only per-bar inspection of a recorded CP-3 tenant session: "
            "the values the engine evaluated, every rule's comparison "
            "pass/fail, the first-match decision, and the engine's own "
            "recorded outcome/halt."
        ),
    )
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--strategy", type=Path, required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--from", dest="window_from", default=None, metavar="HH:MM")
    parser.add_argument("--to", dest="window_to", default=None, metavar="HH:MM")
    parser.add_argument("--session-name", default=None)
    parser.add_argument("--json", dest="as_json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render one inspection to stdout. ``0`` on success, ``2`` on any refusal."""
    args = _parser().parse_args(argv)
    try:
        report = inspect_session(
            journal_path=args.journal,
            strategy_path=args.strategy,
            bindings_path=args.bindings,
            data_dir=args.data_dir,
            window_from=args.window_from,
            window_to=args.window_to,
            session_name=args.session_name,
        )
    except Cp3RunnerRefusal as exc:
        print(f"inspect refused: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(render_json(report) if args.as_json else render_text(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
