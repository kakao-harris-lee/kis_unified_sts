"""``sts tos inspect`` core — «왜 이 바에서 이 결정이었나», per recorded bar.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1. The operator
question this answers is the one §1's 관측 row says nobody could see: M2 에서
진입이 0 건이었는데 **어느 비교식이 몇 % 의 바에서 막았나**. The tool reads a
recorded CP-3 tenant session and prints, per bar, the field values the producer
published, every authored rule's firing with **each comparison's own pass/fail**,
the first-match decision, and the engine's own recorded outcome / halt beside it.

**Nothing is re-authored.** The comparison semantics are
:func:`tos.dsl.vocabulary.eval_compare` and the first-match order is
:func:`tos.dsl.vocabulary.evaluate_policy`, called verbatim — a second
implementation of either would make this screen's answer a property of the
inspector rather than of the strategy (and ``EQ`` is type-strict, which a
hand-rolled comparison gets wrong on the first ``1`` vs ``True``). The strategy
file is loaded, admitted and bound through :func:`cp3.strategy.load_strategy_content`,
i.e. the PRODUCTION loader and the production five bindings rules; the journal is
read by the shipped :class:`~tos_runtime.marketfeed.journal.JsonLinesObservationJournal`,
the one reader of that wire shape; the evidence join is
:mod:`cp3.inspect_evidence`. This module owns the *environment shape*, the
per-bar table, and the summary — nothing else.

**The environment.** A production evaluation reads
``env["capsule"]["resolved_values"][field_key]`` (merged there by
:func:`tos.dsl.determinism.build_environment`) and ``env["config"][key]`` (the
bindings). This module builds exactly those two namespaces from the journal
line's ``fields`` and the resolved bindings — it does NOT mint a per-bar
:class:`~tos.capsule.DecisionContextCapsule`, because a recorded paper session's
Capsules already exist in its own stores and re-issuing look-alikes under a
replay label would be a second, differently-labelled identity for the same bar.
The cost of the narrower environment is stated as a **refusal, not a silent
UNKNOWN**: a policy naming any operand ref other than
``capsule.resolved_values.<key>`` or ``config.<key>`` refuses by name
(:func:`_refuse_unsupported_refs`), because ``UNKNOWN`` is indistinguishable
from "the field was legitimately false" and an inspector that cannot tell those
apart is worse than one that says so.

**Read-only.** The journal, the strategy tree and the three sqlite stores are
opened for reading only (the stores as ``file:…?mode=ro`` URIs), and this module
writes nothing anywhere. It reads no clock: the window is operator-supplied and
every timestamp printed comes from the bar's own ``as_of_ms``.

CLI (the legacy-side ``sts tos inspect`` wrapper invokes exactly this)::

    PYTHONPATH=tos/src:tos/runtime/src:tos/runtime \\
      .venv/bin/python -m cp3.inspect_session \\
        --journal  <session>/journal.jsonl \\
        --strategy <session>/render/strategies/<name>.strategy.yaml \\
        --bindings <session>/render/strategy_bindings.yaml \\
        --data-dir <tenant durable leaf> \\
        [--from HH:MM] [--to HH:MM] [--json]

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml``(transitively, via
the loaders) only. No ``shared.*``, no RNG, no ``subprocess``, no network.
Intra-package imports are RELATIVE (see :mod:`cp3._base`).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tos.dsl import VALUE_NAMESPACE, DecisionPolicy, Operand, ScalarValue
from tos.dsl.vocabulary import UNKNOWN, eval_compare, evaluate_policy, resolve_operand
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal

from ._base import Cp3RunnerRefusal
from .inspect_evidence import BarEvidence, read_bar_evidence
from .strategy import load_strategy_content

__all__ = [
    "DISPLAY_TZ_ID",
    "BarRow",
    "CompareSummary",
    "CompareView",
    "InspectReport",
    "RuleSummary",
    "RuleView",
    "inspect_session",
    "main",
    "render_json",
    "render_text",
]

#: The display timezone. Session and trading logic in this repo is KST-native
#: (root ``CLAUDE.md`` 비협상 규칙 «Timezone»), and this package already fixes
#: the same id for the same reason (``cp3.replay`` 178행), so the one printed
#: clock is KST and there is no knob to point it elsewhere.
DISPLAY_TZ_ID = "Asia/Seoul"

#: The two operand ref shapes a recorded-session environment can resolve: the
#: per-bar published values, and the resolved config bindings.
_CAPSULE_VALUE_PREFIX: tuple[str, ...] = ("capsule", VALUE_NAMESPACE)
_CONFIG_PREFIX: tuple[str, ...] = ("config",)

#: Numeric field keys the per-bar table prints as columns. The boolean gates are
#: deliberately NOT repeated here: every one of them is already visible as its
#: own comparison mark, and printing it twice would widen the row for nothing.
_NUMERIC_COLUMNS: tuple[str, ...] = ("close_x100", "vwap_x100", "z_x1000")

#: The timestamp format inside a producer join key
#: (``tools/tos_cp3/produce_fields.py::derive_raw_event_id`` —
#: ``<symbol>:1m:<YYYYmmddTHHMMSS±HHMM>``). It is restated rather than imported
#: for the same reason :mod:`cp3.contract` restates the journal key set: the
#: firewall forbids importing ``tools`` from inside ``tos/``, and the two sides
#: meet through the file.
#:
#: **Why the key and not ``as_of_ms``.** On the OFFLINE path B1a stamps
#: ``as_of_ms`` with the bar's labelled minute
#: (``produce_fields.derive_raw_event_id``'s sibling ``derive_as_of_ms``), but on
#: the LIVE path the producer does not set it at all — the journal sink stamps it
#: immediately before the write (``tools/tos_cp3/live_producer/line.py``), so a
#: 2026-11-10 09:00 bar carries an ``as_of_ms`` of 09:01:02. ``as_of_ms`` is that
#: path's freshness anchor, not the bar's identity; the join key is the identity.
#: A key this does not parse is NOT a refusal — the printed minute is a display
#: convenience — but it is marked (``~HH:MM`` and ``time_source=as_of_ms``) so a
#: reader is never shown a derived time as if it were the labelled one.
_BAR_KEY_STAMP_FORMAT = "%Y%m%dT%H%M%S%z"

#: The timeframe separator inside that key. Splitting on it rather than on the
#: last ``:`` is what makes a key for some other timeframe fall into the marked
#: fallback instead of being mis-read as a one-minute bar (the legacy side splits
#: on the same token — ``tools/tos_cp3/session_inputs.py``
#: ``_RAW_EVENT_ID_SEPARATOR``).
_BAR_KEY_SEPARATOR = ":1m:"


@dataclass(frozen=True)
class CompareView:
    """One comparison of one rule, on one bar."""

    index: int
    expression: str
    left_value: str
    right_value: str
    passed: bool


@dataclass(frozen=True)
class RuleView:
    """One authored rule's evaluation on one bar."""

    position: int
    label: str
    rule_id: str
    decision_kind: str
    fired: bool
    compares: tuple[CompareView, ...]


@dataclass(frozen=True)
class BarRow:
    """One recorded bar: its fields, every rule's verdict, and what the engine did."""

    raw_event_id: str
    as_of_ms: int
    time_kst: str
    time_source: str
    fields: Mapping[str, ScalarValue]
    rules: tuple[RuleView, ...]
    decision_rule_id: str
    decision_kind: str
    evidence: BarEvidence | None


@dataclass(frozen=True)
class CompareSummary:
    """How often one comparison was the thing that was false."""

    index: int
    expression: str
    failed_bars: int
    bars: int

    @property
    def failed_pct(self) -> float:
        """Share of inspected bars on which this comparison was false."""
        return 0.0 if not self.bars else 100.0 * self.failed_bars / self.bars


@dataclass(frozen=True)
class RuleSummary:
    """How often one rule fired, and which of its comparisons blocked it."""

    position: int
    label: str
    rule_id: str
    decision_kind: str
    fired_bars: int
    bars: int
    compares: tuple[CompareSummary, ...]

    @property
    def fired_pct(self) -> float:
        """Share of inspected bars on which this rule fired."""
        return 0.0 if not self.bars else 100.0 * self.fired_bars / self.bars


@dataclass(frozen=True)
class InspectReport:
    """Everything one ``inspect`` run read, as data a caller can render or serve."""

    session_name: str
    instrument: str
    strategy_path: Path
    strategy_sha256: str
    bindings_path: Path
    bindings: Mapping[str, ScalarValue]
    data_dir: Path | None
    window_from: str | None
    window_to: str | None
    default_rule_id: str
    default_decision_kind: str
    bars: tuple[BarRow, ...]
    rules: tuple[RuleSummary, ...]
    decision_counts: Mapping[str, int]
    outcome_counts: Mapping[str, int]
    halt_counts: Mapping[str, int]
    unjoined_counts: Mapping[str, int]


# ===========================================================================
# Operand / value rendering
# ===========================================================================


def _operand_text(operand: Operand) -> str:
    """The authored operand, as the legend prints it.

    ``capsule.resolved_values.hi_vol`` prints as ``hi_vol`` (the field key is
    what an operator recognizes); a ``config`` ref keeps its namespace so a
    threshold is never mistaken for a market value.
    """
    if operand.ref is None:
        return _value_text(operand.const)
    path = tuple(operand.ref)
    if path[: len(_CAPSULE_VALUE_PREFIX)] == _CAPSULE_VALUE_PREFIX:
        return ".".join(path[len(_CAPSULE_VALUE_PREFIX) :])
    return ".".join(path)


def _value_text(value: object) -> str:
    """A resolved scalar as the table prints it (``UNKNOWN`` included)."""
    if value is UNKNOWN:
        return "UNKNOWN"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "-"
    return str(value)


def _compare_expression(left: Operand, op: str, right: Operand) -> str:
    """One comparison as a single legend line."""
    return f"{_operand_text(left)} {op} {_operand_text(right)}"


# ===========================================================================
# Environment + refusals
# ===========================================================================


def _refuse_unsupported_refs(policy: DecisionPolicy, *, strategy_path: Path) -> None:
    """Refuse a policy whose operands this environment shape cannot resolve.

    Raises:
        Cp3RunnerRefusal: An operand names a ref outside
            ``capsule.resolved_values.<key>`` / ``config.<key>``. Resolving it
            to ``UNKNOWN`` instead would print "this comparison was false" for a
            value the inspector simply did not build, which is the one reading
            an operator must never be handed.
    """
    for position, rule in enumerate(policy.rules, start=1):
        for index, compare in enumerate(rule.all_of, start=1):
            for operand in (compare.left, compare.right):
                if operand.ref is None:
                    continue
                path = tuple(operand.ref)
                supported = (
                    len(path) == len(_CAPSULE_VALUE_PREFIX) + 1
                    and path[: len(_CAPSULE_VALUE_PREFIX)] == _CAPSULE_VALUE_PREFIX
                ) or (
                    len(path) == len(_CONFIG_PREFIX) + 1
                    and path[: len(_CONFIG_PREFIX)] == _CONFIG_PREFIX
                )
                if not supported:
                    raise Cp3RunnerRefusal(
                        f"{strategy_path}: rule #{position} compare #{index} names "
                        f"operand ref {path} — this inspector builds only "
                        f"capsule.{VALUE_NAMESPACE}.<key> and config.<key>, so that "
                        "ref would resolve to UNKNOWN and print as a failed "
                        "comparison for a value never built. Refusing instead."
                    )


def _environment(
    fields: Mapping[str, ScalarValue], bindings: Mapping[str, ScalarValue]
) -> dict[str, object]:
    """The two-namespace Decision Context environment for one bar."""
    return {"capsule": {VALUE_NAMESPACE: dict(fields)}, "config": dict(bindings)}


# ===========================================================================
# Per-bar evaluation
# ===========================================================================


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
                    left_value=_value_text(resolve_operand(compare.left, env)),
                    right_value=_value_text(resolve_operand(compare.right, env)),
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
    """One bar's ``(HH:MM, time source, minutes since KST midnight)``.

    The labelled minute comes from the join key (see
    :data:`_BAR_KEY_STAMP_FORMAT`). A key whose stamp does not parse falls back
    to ``as_of_ms``, marked with a leading ``~`` so the reader can see that the
    printed minute is derived rather than labelled.
    """
    parts = raw_event_id.split(_BAR_KEY_SEPARATOR, 1)
    try:
        labelled = datetime.strptime(parts[1], _BAR_KEY_STAMP_FORMAT)
    except (IndexError, ValueError):
        derived = datetime.fromtimestamp(as_of_ms / 1000, tz=ZoneInfo(DISPLAY_TZ_ID))
        return f"~{derived:%H:%M}", "as_of_ms", derived.hour * 60 + derived.minute
    local = labelled.astimezone(ZoneInfo(DISPLAY_TZ_ID))
    return f"{local:%H:%M}", "raw_event_id", local.hour * 60 + local.minute


def _parse_window(value: str | None, *, flag: str) -> int | None:
    """``HH:MM`` as minutes since KST midnight, or ``None``.

    Raises:
        Cp3RunnerRefusal: The value is not ``HH:MM`` in range.
    """
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


# ===========================================================================
# The pure entry point
# ===========================================================================


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
    """The in-window journal bars, oldest first.

    Raises:
        Cp3RunnerRefusal: The journal is missing, unreadable, or malformed, or
            the window selected no bar at all.
    """
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


def _summarize(
    policy: DecisionPolicy, rows: Sequence[BarRow]
) -> tuple[RuleSummary, ...]:
    """Per-rule firing counts and per-comparison failure counts over ``rows``."""
    bars = len(rows)
    summaries: list[RuleSummary] = []
    for position, rule in enumerate(policy.rules, start=1):
        views = [row.rules[position - 1] for row in rows]
        first = views[0]
        compares = tuple(
            CompareSummary(
                index=index,
                expression=first.compares[index - 1].expression,
                failed_bars=sum(
                    1 for view in views if not view.compares[index - 1].passed
                ),
                bars=bars,
            )
            for index in range(1, len(rule.all_of) + 1)
        )
        summaries.append(
            RuleSummary(
                position=position,
                label=first.label,
                rule_id=first.rule_id,
                decision_kind=first.decision_kind,
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


def _halt_label(evidence: BarEvidence) -> str | None:
    """The engine's halt for one bar as ``REASON@STEP``, or ``None``."""
    if evidence.halt_reason is None and evidence.halt_step is None:
        return None
    return f"{evidence.halt_reason or '-'}@{evidence.halt_step or '-'}"


def _evidence_tallies(
    rows: Sequence[BarRow],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """``(outcome counts, halt counts, unjoined counts)`` over the joined rows.

    Split from :func:`inspect_session` for the 100-line function cap
    ``config/tos_size_budget.yaml`` enforces over this tree.
    """
    found = [row.evidence for row in rows if row.evidence is not None]
    joined = [item for item in found if item.joined]
    return (
        _tally([item.outcome_type or item.withheld_reason or "-" for item in joined]),
        _tally(
            [
                label
                for label in (_halt_label(item) for item in joined)
                if label is not None
            ]
        ),
        _tally(
            [item.unjoined_reason for item in found if item.unjoined_reason is not None]
        ),
    )


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
    """Inspect one recorded session's bars against its own authored policy.

    Args:
        journal_path: The session's ``journal.jsonl`` (the producer's output).
        strategy_path: The strategy file the session was rendered with, inside
            its ``strategies/`` directory.
        bindings_path: The ``strategy_bindings.yaml`` beside that directory.
        data_dir: The tenant durable-set leaf to join evidence from, or ``None``
            to report rule evaluation only.
        window_from: Inclusive KST ``HH:MM`` lower bound, or ``None``.
        window_to: Inclusive KST ``HH:MM`` upper bound, or ``None``.
        session_name: A label for the header; defaults to the journal's parent
            directory name.

    Returns:
        The :class:`InspectReport`.

    Raises:
        Cp3RunnerRefusal: Any loader/bindings/journal/store refusal, an operand
            ref this environment shape cannot resolve, a malformed window, or a
            window selecting no bar.
    """
    content = load_strategy_content(
        strategy_path=strategy_path, bindings_path=bindings_path
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
    rows: list[BarRow] = []
    for bar in bars:
        env = _environment(bar.fields, content.bindings)
        decision = evaluate_policy(policy, env)
        rule_id, _kind = content.rule_index[decision.rationale]
        rows.append(
            BarRow(
                raw_event_id=bar.raw_event_id,
                as_of_ms=bar.as_of_ms,
                time_kst=bar.time_kst,
                time_source=bar.time_source,
                fields=bar.fields,
                rules=_evaluate_rules(policy, env, content.rule_index),
                decision_rule_id=rule_id,
                decision_kind=str(decision.kind),
                evidence=evidence_by_bar.get(bar.raw_event_id),
            )
        )
    outcome_counts, halt_counts, unjoined_counts = _evidence_tallies(rows)
    default_rule_id, _default_kind = content.rule_index[policy.default.rationale]
    return InspectReport(
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
        rules=_summarize(policy, rows),
        decision_counts=_tally([row.decision_rule_id for row in rows]),
        outcome_counts=outcome_counts,
        halt_counts=halt_counts,
        unjoined_counts=unjoined_counts,
    )


# ===========================================================================
# Rendering
# ===========================================================================


def _marks(view: RuleView) -> str:
    """One rule's per-bar cell: fired flag plus a mark per comparison."""
    marks = "".join("+" if compare.passed else "-" for compare in view.compares)
    return f"{'Y' if view.fired else 'n'} {marks}"


def _header_lines(report: InspectReport) -> list[str]:
    """The header + legend block: what was read, and the compare order per rule."""
    window = (
        f"{report.window_from or report.bars[0].time_kst}"
        f"–{report.window_to or report.bars[-1].time_kst}"
    )
    bindings = (
        " · ".join(
            f"{key}={_value_text(value)}" for key, value in report.bindings.items()
        )
        or "(none)"
    )
    lines = [
        f"TOS inspect — session {report.session_name} · instrument {report.instrument} "
        f"· {len(report.bars)} bars · {window} KST · read-only",
        f"strategy  {report.strategy_path} (sha256 {report.strategy_sha256[:12]})",
        f"bindings  {report.bindings_path} · {bindings}",
    ]
    if report.data_dir is None:
        lines.append("evidence  (not read — no --data-dir)")
    else:
        unjoined = sum(report.unjoined_counts.values())
        lines.append(
            f"evidence  {report.data_dir} · {len(report.bars) - unjoined} joined "
            f"· {unjoined} unjoined"
        )
    lines.append("")
    lines.append("rules (comparison order, as authored):")
    for rule in report.rules:
        lines.append(f"  {rule.label} = {rule.rule_id} ({rule.decision_kind})")
        for compare in rule.compares:
            lines.append(f"       {compare.index} {compare.expression}")
    lines.append(
        f"  default = {report.default_rule_id} ({report.default_decision_kind})"
    )
    return lines


def _bar_table(report: InspectReport) -> list[str]:
    """The per-bar table: one line per bar, marks in the legend's order."""
    rule_width = {
        rule.label: max(len(rule.label), 2 + len(rule.compares))
        for rule in report.rules
    }
    head = [f"{'time':<6}"] + [f"{key:>11}" for key in _NUMERIC_COLUMNS]
    head += [f"{rule.label:<{rule_width[rule.label]}}" for rule in report.rules]
    head += [f"{'decision':<24}", f"{'outcome':<20}", "halt"]
    lines = [
        "",
        "bars (+ = comparison true, - = false; rule Y = fired):",
        " ".join(head).rstrip(),
    ]
    for row in report.bars:
        cells = [f"{row.time_kst:<6}"]
        cells += [f"{_value_text(row.fields.get(key)):>11}" for key in _NUMERIC_COLUMNS]
        cells += [f"{_marks(view):<{rule_width[view.label]}}" for view in row.rules]
        cells.append(f"{row.decision_rule_id:<24}")
        evidence = row.evidence
        if evidence is None:
            cells.append(f"{'-':<20}")
            cells.append("-")
        elif not evidence.joined:
            cells.append(f"{'UNJOINED':<20}")
            cells.append(evidence.unjoined_reason or "-")
        else:
            outcome = evidence.outcome_type or evidence.withheld_reason or "-"
            cells.append(f"{outcome:<20}")
            cells.append(_halt_label(evidence) or "-")
        lines.append(" ".join(cells).rstrip())
    return lines


def _summary_lines(report: InspectReport) -> list[str]:
    """The summary block — which comparison blocked which rule, how often."""
    bars = len(report.bars)
    lines = ["", f"summary — {bars} bars"]
    for rule in report.rules:
        lines.append(
            f"  {rule.label} {rule.rule_id:<24} fired {rule.fired_bars:>5} / "
            f"{rule.bars:<5} {rule.fired_pct:6.1f}%"
        )
        for compare in rule.compares:
            lines.append(
                f"      {compare.index} {compare.expression:<48} false "
                f"{compare.failed_bars:>5} / {compare.bars:<5} "
                f"{compare.failed_pct:6.1f}%"
            )

    def tally_line(label: str, counts: Mapping[str, int]) -> str:
        body = " · ".join(f"{key} {value}" for key, value in counts.items()) or "(none)"
        return f"  {label}: {body}"

    lines.append(tally_line("decisions", report.decision_counts))
    if report.data_dir is not None:
        lines.append(tally_line("evidence outcomes", report.outcome_counts))
        lines.append(tally_line("evidence halts", report.halt_counts))
        lines.append(tally_line("unjoined", report.unjoined_counts))
    return lines


def render_text(report: InspectReport) -> str:
    """The whole report as the operator table (header + legend + bars + summary)."""
    lines = _header_lines(report) + _bar_table(report) + _summary_lines(report)
    return "\n".join(lines) + "\n"


def render_json(report: InspectReport) -> str:
    """The whole report as one JSON document, for a machine consumer."""
    document = {
        "session": report.session_name,
        "instrument": report.instrument,
        "strategy": {
            "path": str(report.strategy_path),
            "sha256": report.strategy_sha256,
        },
        "bindings": {
            "path": str(report.bindings_path),
            "values": dict(report.bindings),
        },
        "data_dir": None if report.data_dir is None else str(report.data_dir),
        "window": {"from": report.window_from, "to": report.window_to},
        "default": {
            "rule_id": report.default_rule_id,
            "decision_kind": report.default_decision_kind,
        },
        "bars": [
            {
                "raw_event_id": row.raw_event_id,
                "as_of_ms": row.as_of_ms,
                "time_kst": row.time_kst,
                "time_source": row.time_source,
                "fields": dict(row.fields),
                "decision_rule_id": row.decision_rule_id,
                "decision_kind": row.decision_kind,
                "rules": [
                    {
                        "label": view.label,
                        "rule_id": view.rule_id,
                        "decision_kind": view.decision_kind,
                        "fired": view.fired,
                        "compares": [
                            {
                                "index": compare.index,
                                "expression": compare.expression,
                                "left_value": compare.left_value,
                                "right_value": compare.right_value,
                                "passed": compare.passed,
                            }
                            for compare in view.compares
                        ],
                    }
                    for view in row.rules
                ],
                "evidence": (
                    None if row.evidence is None else _evidence_json(row.evidence)
                ),
            }
            for row in report.bars
        ],
        "summary": {
            "bars": len(report.bars),
            "rules": [
                {
                    "label": rule.label,
                    "rule_id": rule.rule_id,
                    "fired_bars": rule.fired_bars,
                    "bars": rule.bars,
                    "fired_pct": round(rule.fired_pct, 4),
                    "compares": [
                        {
                            "index": compare.index,
                            "expression": compare.expression,
                            "failed_bars": compare.failed_bars,
                            "bars": compare.bars,
                            "failed_pct": round(compare.failed_pct, 4),
                        }
                        for compare in rule.compares
                    ],
                }
                for rule in report.rules
            ],
            "decisions": dict(report.decision_counts),
            "evidence_outcomes": dict(report.outcome_counts),
            "evidence_halts": dict(report.halt_counts),
            "unjoined": dict(report.unjoined_counts),
        },
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _evidence_json(evidence: BarEvidence) -> dict[str, object]:
    """One bar's evidence join as JSON-native fields."""
    return {
        "joined": evidence.joined,
        "unjoined_reason": evidence.unjoined_reason,
        "event_id": evidence.event_id,
        "snapshot_id": evidence.snapshot_id,
        "outcome_type": evidence.outcome_type,
        "outcome_halt_reason": evidence.outcome_halt_reason,
        "consumed_halt_reason": evidence.consumed_halt_reason,
        "consumed_halt_step": evidence.consumed_halt_step,
        "withheld_reason": evidence.withheld_reason,
        "halt_step": evidence.halt_step,
        "halt_reason": evidence.halt_reason,
        "halt_detail": evidence.halt_detail,
    }


# ===========================================================================
# CLI
# ===========================================================================


def _parser() -> argparse.ArgumentParser:
    """The CLI the legacy-side wrapper builds an argv for."""
    parser = argparse.ArgumentParser(
        prog="cp3.inspect_session",
        description=(
            "Read-only per-bar inspection of a recorded CP-3 tenant session: "
            "field values, every rule's comparison pass/fail, the first-match "
            "decision, and the engine's own recorded outcome/halt."
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
