"""``sts tos inspect`` core — «왜 이 바에서 이 결정이었나», per recorded bar.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1. The operator
question this answers is the one §1's 관측 row says nobody could see: M2 에서
진입이 0 건이었는데 **어느 비교식이 몇 % 의 바에서 막았나**. The tool reads a
recorded CP-3 tenant session and prints, per bar, the values the engine
evaluated, every authored rule's firing with **each comparison's own
pass/fail**, the first-match decision, and the engine's own recorded outcome /
halt beside it.

**Nothing is re-authored.** The comparison semantics are
:func:`tos.dsl.vocabulary.eval_compare` and the first-match order is
:func:`tos.dsl.vocabulary.evaluate_policy`, called verbatim — a second
implementation of either would make this screen's answer a property of the
inspector rather than of the strategy (and ``EQ`` is type-strict, which a
hand-rolled comparison gets wrong on the first ``1`` vs ``True``). The strategy
file is loaded, admitted and bound through :func:`cp3.strategy.load_strategy_content`,
i.e. the PRODUCTION loader and the production five bindings rules; the journal is
read by the shipped :class:`~tos_runtime.marketfeed.journal.JsonLinesObservationJournal`,
the one reader of that wire shape; the evidence join and the value-view
projection are :mod:`cp3.inspect_evidence`; the result shape and both
renderings are :mod:`cp3.inspect_report`.

**The environment is the ENGINE's, not the producer's** (review of #1057,
MEDIUM-1). A production evaluation reads
``env["capsule"]["resolved_values"]`` built from the
:class:`~tos.dsl.ContextValueView` ``tos.engine.pipeline`` handed it — the view
recorded on that bar's own inbox tick — and ``env["config"][key]`` from the
resolved bindings. This module builds exactly those two namespaces, and for a
joined bar it takes the values from **that recorded view**. The producer's
``journal.jsonl`` line is still read (it is what names the bar and what the
``close/vwap/z`` columns print) but it is not what the rules are evaluated on:
where the two disagree, the journal is the wrong answer, and the disagreement is
reported per bar (``V``) and counted per field key in the summary.

Three populations follow from that, and only the first carries the percentages
(the reasoning is in :mod:`cp3.inspect_report`'s module docstring):

* **counted** — joined, non-empty engine view. The per-comparison denominators.
* **withheld** (``W``) — the engine published an *explicit-empty* view, which is
  a defined outcome (``tos.dsl.context_value`` "design #32 §6 ∅ 양방향") and the
  shape a ``DECISION_WITHHELD`` tick has. Rules are not evaluated at all; the
  bar is reported on its own summary line.
* **unjoined** (``U``) — the chain broke; the rules are evaluated on the journal
  line so the bar is still readable, marked, and left out of the denominators.

This module does NOT mint a per-bar
:class:`~tos.capsule.DecisionContextCapsule`: a recorded paper session's
Capsules already exist in its own stores, and re-issuing look-alikes under a
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
every timestamp printed comes from the bar's own identity.

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
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tos.dsl import VALUE_NAMESPACE, DecisionPolicy, Operand, ScalarValue
from tos.dsl.vocabulary import eval_compare, evaluate_policy, resolve_operand
from tos_runtime.marketfeed.journal import JournalError, JsonLinesObservationJournal

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
from .strategy import load_strategy_content

__all__ = [
    "DISPLAY_TZ_ID",
    "inspect_session",
    "main",
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

#: The decision shape a ``NO_ACTION`` policy outcome has, for the comparison
#: against the engine's recorded ``outcome_type`` (:data:`ENGINE_OUTCOME_SHAPES`).
_NO_ACTION_KIND = "NO_ACTION"


# ===========================================================================
# Operand rendering
# ===========================================================================


def _operand_text(operand: Operand) -> str:
    """The authored operand, as the legend prints it.

    ``capsule.resolved_values.hi_vol`` prints as ``hi_vol`` (the field key is
    what an operator recognizes); a ``config`` ref keeps its namespace so a
    threshold is never mistaken for a market value.
    """
    if operand.ref is None:
        return value_text(operand.const)
    path = tuple(operand.ref)
    if path[: len(_CAPSULE_VALUE_PREFIX)] == _CAPSULE_VALUE_PREFIX:
        return ".".join(path[len(_CAPSULE_VALUE_PREFIX) :])
    return ".".join(path)


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
    values: Mapping[str, ScalarValue], bindings: Mapping[str, ScalarValue]
) -> dict[str, object]:
    """The two-namespace Decision Context environment for one bar."""
    return {"capsule": {VALUE_NAMESPACE: dict(values)}, "config": dict(bindings)}


def _view_diff(
    view: Mapping[str, ScalarValue], fields: Mapping[str, ScalarValue]
) -> dict[str, tuple[str, str]]:
    """``field_key -> (view, journal)`` for every key the two disagree on.

    The comparison is type-aware on purpose: the DSL's ``EQ`` is type-strict
    (``vocabulary.eval_compare``), so a ``1`` where the engine saw ``True`` is a
    real difference even though ``1 == True`` in Python.
    """
    diff: dict[str, tuple[str, str]] = {}
    for key in sorted(set(view) | set(fields)):
        left, right = view.get(key), fields.get(key)
        if left is right:
            continue
        if type(left) is type(right) and left == right:
            continue
        diff[key] = (value_text(left), value_text(right))
    return diff


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


def _engine_shape(evidence: BarEvidence | None) -> str | None:
    """``"no_action"`` / ``"proposal"`` from the recorded outcome, or ``None``.

    ``None`` is "nothing comparable here" — no outcome was emitted, or its
    ``outcome_type`` is one :data:`ENGINE_OUTCOME_SHAPES` has never been
    measured against. Guessing a shape for an unmeasured outcome type would
    manufacture a ``D`` marker out of this inspector's own ignorance.
    """
    if evidence is None or not evidence.joined or evidence.outcome_type is None:
        return None
    return ENGINE_OUTCOME_SHAPES.get(evidence.outcome_type)


def _evaluation_source(
    bar: _JournalBar, evidence: BarEvidence | None, *, evidence_asked: bool
) -> tuple[str, dict[str, ScalarValue]]:
    """``(evaluation source, the values the rules are evaluated on)`` for one bar.

    The order matters. A readable, non-empty engine view wins outright — it is
    what the engine evaluated. An explicit-empty view is the withheld shape and
    evaluates nothing. Everything else falls back to the journal line, and
    whether that counts depends on whether an engine view was ever asked for
    (see :data:`~cp3.inspect_report.EVALUATION_JOURNAL_ONLY`).
    """
    if evidence is not None and evidence.joined and evidence.value_view:
        return EVALUATION_ENGINE_VIEW, dict(evidence.value_view)
    if evidence is not None and evidence.view_is_explicitly_empty:
        return EVALUATION_WITHHELD, {}
    if not evidence_asked:
        return EVALUATION_JOURNAL_ONLY, dict(bar.fields)
    return EVALUATION_JOURNAL_UNJOINED, dict(bar.fields)


def _bar_row(
    bar: _JournalBar,
    evidence: BarEvidence | None,
    policy: DecisionPolicy,
    bindings: Mapping[str, ScalarValue],
    rule_index: Mapping[str, tuple[str, object]],
    *,
    evidence_asked: bool,
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
        env = _environment(values, bindings)
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
    )


def _summarize(
    policy: DecisionPolicy,
    rows: Sequence[BarRow],
    rule_index: Mapping[str, tuple[str, object]],
) -> tuple[RuleSummary, ...]:
    """Per-rule firing and per-comparison failure counts over the COUNTED rows.

    A withheld or unjoined bar is not in ``counted``, so it is in no
    denominator: the percentages answer "of the bars the engine actually
    evaluated, how often did this comparison block the rule". The rule id and
    the comparison text come from the authored policy and its ``rule_index``,
    not from a row, so they are right even for a window where every bar was
    withheld and no row carries a view.
    """
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
        data_dir: The tenant durable-set leaf to read the engine's value views
            and decision records from, or ``None`` to evaluate the journal line
            alone (every bar then falls outside the denominators).
        window_from: Inclusive KST ``HH:MM`` lower bound, or ``None``.
        window_to: Inclusive KST ``HH:MM`` upper bound, or ``None``.
        session_name: A label for the header; defaults to the journal's parent
            directory name.

    Returns:
        The :class:`~cp3.inspect_report.InspectReport`.

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
    rows = [
        _bar_row(
            bar,
            evidence_by_bar.get(bar.raw_event_id),
            policy,
            content.bindings,
            content.rule_index,
            evidence_asked=data_dir is not None,
        )
        for bar in bars
    ]
    tallies = _tallies(rows)
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


# ===========================================================================
# CLI
# ===========================================================================


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
    """Render one inspection to stdout. ``0`` on success, ``2`` on any refusal.

    Refusals go to stderr and nothing else does, so a ``--json`` run's stdout is
    a valid document or empty — never a document with a warning glued to it
    (review of #1057, LOW-2; the legacy-side driver keeps the two streams apart
    for the same reason).
    """
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
