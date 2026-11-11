"""The inspection's result shape, and the two renderings of it.

Part of the CP-3 ``cp3`` package (roadmap
``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1). Split out of
:mod:`cp3.inspect_session` when the value-view join (review of #1057, MEDIUM-1)
pushed that module past ``config/tos_size_budget.yaml``'s 1,000-line cap. The
dependency runs one way — ``inspect_session -> inspect_report`` — so the
dataclasses a future Control Plane API reuses carry no evaluation machinery.

**What the table has to make visible, and why each marker exists.**

* ``V`` — the engine's own value view disagreed with the producer's journal line
  for this bar. The engine evaluated the view; the journal is the wrong answer
  when they differ, so the difference is a finding, not a detail. The summary
  names which field keys differed and on how many bars.
* ``D`` — the re-evaluated decision disagrees with the outcome the engine
  recorded. On a session where the inspector and the engine read the same
  inputs through the same evaluator this must be zero; a non-zero count means
  the screen is lying about something, so it is counted rather than smoothed.
* ``W`` — the engine published an **explicit-empty** value view for this bar, so
  every operand resolved to ``UNKNOWN`` and no rule could fire for reasons that
  have nothing to do with the authored thresholds (that is the shape a
  ``DECISION_WITHHELD`` tick has). Such a bar is NOT evaluated and is **outside
  every per-comparison denominator** — counting it would report "entry_window
  was false" about a bar where nothing was read.
* ``U`` — an engine view was asked for and is not usable (the chain broke, or
  the recorded view is one this reader refused), so the rules were evaluated on
  the **journal** line as a substitute. Shown, because the fields are still
  worth reading, but outside the denominators: a bar whose evaluation inputs
  stand in for inputs that should have been there cannot carry a claim about
  what blocked a rule. ``substituted_bars`` counts these; ``unjoined_counts``
  separately names the chain breaks among them.

So the denominators are the **counted** bars, and the header and the summary
state every population so the excluded ones are visible rather than merely
absent.

**A run that asked for no evidence at all is a different case** and is counted.
With ``--no-evidence`` there is no engine view to be a substitute *for*: the
operator asked what the authored policy does to the producer's own fields, the
header says ``evidence (not read — no --data-dir)``, and there is no second
source the reader could mistake the numbers for. Excluding those bars would
leave every denominator at zero, which answers nothing. That is
:data:`EVALUATION_JOURNAL_ONLY`, and it carries no ``U``.

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib only. Intra-package imports are
RELATIVE (see :mod:`cp3._base`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from tos.dsl import ScalarValue
from tos.dsl.vocabulary import UNKNOWN

from .inspect_evidence import BarEvidence

__all__ = [
    "EVALUATION_ENGINE_VIEW",
    "EVALUATION_JOURNAL_ONLY",
    "EVALUATION_JOURNAL_UNJOINED",
    "EVALUATION_WITHHELD",
    "BarRow",
    "CompareSummary",
    "CompareView",
    "InspectReport",
    "RuleSummary",
    "RuleView",
    "halt_label",
    "render_json",
    "render_text",
    "value_text",
]

#: Rules were evaluated on the engine's own published value view — the only
#: population a per-comparison denominator may contain.
EVALUATION_ENGINE_VIEW = "engine_view"

#: The engine published an explicit-empty view, so nothing was evaluated.
EVALUATION_WITHHELD = "withheld"

#: The evidence chain broke; rules were evaluated on the journal line instead of
#: the engine view that should have been there. Outside the denominators.
EVALUATION_JOURNAL_UNJOINED = "journal_unjoined"

#: No durable set was asked for (``--no-evidence``), so the journal line is the
#: only input there is and the only one the numbers could mean. Counted.
EVALUATION_JOURNAL_ONLY = "journal_only"

#: Numeric field keys the per-bar table prints as columns. The boolean gates are
#: deliberately NOT repeated here: every one of them is already visible as its
#: own comparison mark, and printing it twice would widen the row for nothing.
_NUMERIC_COLUMNS: tuple[str, ...] = ("close_x100", "vwap_x100", "z_x1000")

#: The engine ``outcome_type`` values this inspector can compare its own
#: first-match decision against. Anything else is "not comparable" rather than a
#: disagreement — inventing a verdict for an outcome shape nobody has measured
#: is exactly the phantom finding ``D`` exists to avoid.
ENGINE_OUTCOME_SHAPES: Mapping[str, str] = {
    "NoActionOutcome": "no_action",
    "Proposal": "proposal",
}


def value_text(value: object) -> str:
    """A resolved scalar as the table prints it (``UNKNOWN`` included)."""
    if value is UNKNOWN:
        return "UNKNOWN"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "-"
    return str(value)


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
    """One recorded bar: its inputs, every rule's verdict, and what the engine did.

    Attributes:
        fields: The producer's journal line for this bar.
        env_values: What the rules were ACTUALLY evaluated on — the engine's
            value view for a counted bar, the journal line for an unjoined one,
            and empty for a withheld one.
        evaluation: One of :data:`EVALUATION_ENGINE_VIEW` /
            :data:`EVALUATION_WITHHELD` / :data:`EVALUATION_JOURNAL_UNJOINED`.
        counted: Whether this bar is inside the per-comparison denominators.
        view_diff: ``field_key -> (engine view, journal)`` for every key the two
            disagree on; empty when they agree or only one of them exists.
        engine_shape: ``"no_action"`` / ``"proposal"`` from the recorded
            outcome, or ``None`` when there is nothing comparable.
        decision_disagrees: Whether the re-evaluated decision's shape differs
            from ``engine_shape``.
    """

    raw_event_id: str
    as_of_ms: int
    time_kst: str
    time_source: str
    fields: Mapping[str, ScalarValue]
    env_values: Mapping[str, ScalarValue]
    evaluation: str
    counted: bool
    rules: tuple[RuleView, ...]
    decision_rule_id: str | None
    decision_kind: str | None
    view_diff: Mapping[str, tuple[str, str]]
    engine_shape: str | None
    decision_disagrees: bool
    evidence: BarEvidence | None

    @property
    def flags(self) -> str:
        """The four fixed-position markers, ``-`` where the concern is absent."""
        return "".join(
            (
                "V" if self.view_diff else "-",
                "D" if self.decision_disagrees else "-",
                "W" if self.evaluation == EVALUATION_WITHHELD else "-",
                "U" if self.evaluation == EVALUATION_JOURNAL_UNJOINED else "-",
            )
        )


@dataclass(frozen=True)
class CompareSummary:
    """How often one comparison was the thing that was false."""

    index: int
    expression: str
    failed_bars: int
    bars: int

    @property
    def failed_pct(self) -> float:
        """Share of COUNTED bars on which this comparison was false."""
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
        """Share of COUNTED bars on which this rule fired."""
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
    counted_bars: int
    withheld_bars: int
    substituted_bars: int
    view_diff_bars: int
    view_diff_fields: Mapping[str, int]
    disagreement_bars: int
    not_comparable_bars: int
    decision_counts: Mapping[str, int]
    outcome_counts: Mapping[str, int]
    halt_counts: Mapping[str, int]
    unjoined_counts: Mapping[str, int]
    view_refusal_counts: Mapping[str, int]


# ===========================================================================
# Text rendering
# ===========================================================================


def _marks(row: BarRow, position: int) -> str:
    """One rule's cell for one bar: fired flag plus a mark per comparison."""
    if not row.rules:
        return "?"
    view = row.rules[position - 1]
    marks = "".join("+" if compare.passed else "-" for compare in view.compares)
    return f"{'Y' if view.fired else 'n'} {marks}"


def _populations(report: InspectReport) -> str:
    """The one line that says which bars the denominators contain, and on what.

    The source is named rather than assumed: with ``--no-evidence`` the counted
    bars were evaluated on the producer's journal, and calling that "the
    engine's value view" would be the exact confusion the ``V`` marker exists to
    prevent.
    """
    source = (
        "the journal (no engine view read)"
        if report.data_dir is None
        else "the engine's value view"
    )
    return (
        f"{report.counted_bars} counted on {source} · "
        f"{report.withheld_bars} withheld · {report.substituted_bars} journal-substituted"
    )


def _header_lines(report: InspectReport) -> list[str]:
    """The header + legend block: what was read, and the compare order per rule."""
    window = (
        f"{report.window_from or report.bars[0].time_kst}"
        f"–{report.window_to or report.bars[-1].time_kst}"
    )
    bindings = (
        " · ".join(
            f"{key}={value_text(value)}" for key, value in report.bindings.items()
        )
        or "(none)"
    )
    lines = [
        f"TOS inspect — session {report.session_name} · instrument "
        f"{report.instrument} · {len(report.bars)} bars · {window} KST · read-only",
        f"strategy  {report.strategy_path} (sha256 {report.strategy_sha256[:12]})",
        f"bindings  {report.bindings_path} · {bindings}",
    ]
    if report.data_dir is None:
        lines.append("evidence  (not read — no --data-dir)")
    else:
        lines.append(f"evidence  {report.data_dir}")
    lines.append(f"bars      {_populations(report)}")
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


_TABLE_LEGEND = (
    "bars (+ true · - false; rule Y fired · n not · ? not evaluated; flags "
    "V=view≠journal D=decision≠engine W=withheld U=journal-substituted):"
)


def _bar_cells(
    report: InspectReport, row: BarRow, widths: Mapping[str, int]
) -> list[str]:
    """One bar's table cells, left to right."""
    cells = [f"{row.time_kst:<6}", row.flags]
    cells += [f"{value_text(row.fields.get(key)):>11}" for key in _NUMERIC_COLUMNS]
    cells += [
        f"{_marks(row, rule.position):<{widths[rule.label]}}" for rule in report.rules
    ]
    cells.append(f"{row.decision_rule_id or '(not evaluated)':<24}")
    evidence = row.evidence
    if evidence is None:
        cells += [f"{'-':<20}", "-"]
    elif not evidence.joined:
        cells += [f"{'UNJOINED':<20}", evidence.unjoined_reason or "-"]
    else:
        outcome = evidence.outcome_type or evidence.withheld_reason or "-"
        cells += [f"{outcome:<20}", halt_label(evidence) or "-"]
    return cells


def halt_label(evidence: BarEvidence) -> str | None:
    """The engine's halt for one bar as ``REASON@STEP``, or ``None``."""
    if evidence.halt_reason is None and evidence.halt_step is None:
        return None
    return f"{evidence.halt_reason or '-'}@{evidence.halt_step or '-'}"


def _bar_table(report: InspectReport) -> list[str]:
    """The per-bar table: one line per bar, marks in the legend's order."""
    widths = {
        rule.label: max(len(rule.label), 2 + len(rule.compares))
        for rule in report.rules
    }
    head = [f"{'time':<6}", "VDWU"]
    head += [f"{key:>11}" for key in _NUMERIC_COLUMNS]
    head += [f"{rule.label:<{widths[rule.label]}}" for rule in report.rules]
    head += [f"{'decision':<24}", f"{'outcome':<20}", "halt"]
    lines = ["", _TABLE_LEGEND, " ".join(head).rstrip()]
    for row in report.bars:
        lines.append(" ".join(_bar_cells(report, row, widths)).rstrip())
    return lines


def _tally_line(label: str, counts: Mapping[str, int]) -> str:
    """One ``label: key N · key N`` summary line."""
    body = " · ".join(f"{key} {value}" for key, value in counts.items()) or "(none)"
    return f"  {label}: {body}"


def _summary_lines(report: InspectReport) -> list[str]:
    """The summary block — which comparison blocked which rule, how often."""
    lines = ["", f"summary — {len(report.bars)} bars · {_populations(report)}"]
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
    lines.append(_tally_line("decisions", report.decision_counts))
    if report.data_dir is not None:
        lines.append(
            f"  value view ≠ journal: {report.view_diff_bars} bars"
            + (
                " · "
                + " · ".join(
                    f"{key} {count}" for key, count in report.view_diff_fields.items()
                )
                if report.view_diff_fields
                else ""
            )
        )
        lines.append(
            f"  decision ≠ engine outcome: {report.disagreement_bars} bars "
            f"({report.not_comparable_bars} not comparable)"
        )
        lines.append(f"  withheld (empty value view): {report.withheld_bars} bars")
        lines.append(_tally_line("evidence outcomes", report.outcome_counts))
        lines.append(_tally_line("evidence halts", report.halt_counts))
        lines.append(_tally_line("unjoined", report.unjoined_counts))
        if report.view_refusal_counts:
            lines.append(_tally_line("value view refused", report.view_refusal_counts))
    return lines


def render_text(report: InspectReport) -> str:
    """The whole report as the operator table (header + legend + bars + summary)."""
    lines = _header_lines(report) + _bar_table(report) + _summary_lines(report)
    return "\n".join(lines) + "\n"


# ===========================================================================
# JSON rendering
# ===========================================================================


def _evidence_json(evidence: BarEvidence) -> dict[str, object]:
    """One bar's evidence join as JSON-native fields."""
    return {
        "joined": evidence.joined,
        "unjoined_reason": evidence.unjoined_reason,
        "event_id": evidence.event_id,
        "snapshot_id": evidence.snapshot_id,
        "value_view": (
            None if evidence.value_view is None else dict(evidence.value_view)
        ),
        "value_view_refusal": evidence.value_view_refusal,
        "outcome_type": evidence.outcome_type,
        "outcome_halt_reason": evidence.outcome_halt_reason,
        "consumed_halt_reason": evidence.consumed_halt_reason,
        "consumed_halt_step": evidence.consumed_halt_step,
        "withheld_reason": evidence.withheld_reason,
        "halt_step": evidence.halt_step,
        "halt_reason": evidence.halt_reason,
        "halt_detail": evidence.halt_detail,
    }


def _bar_json(row: BarRow) -> dict[str, object]:
    """One bar as JSON-native fields."""
    return {
        "raw_event_id": row.raw_event_id,
        "as_of_ms": row.as_of_ms,
        "time_kst": row.time_kst,
        "time_source": row.time_source,
        "fields": dict(row.fields),
        "env_values": dict(row.env_values),
        "evaluation": row.evaluation,
        "counted": row.counted,
        "flags": row.flags,
        "view_diff": {
            key: {"value_view": view, "journal": journal}
            for key, (view, journal) in row.view_diff.items()
        },
        "engine_shape": row.engine_shape,
        "decision_disagrees": row.decision_disagrees,
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
        "evidence": None if row.evidence is None else _evidence_json(row.evidence),
    }


def _summary_json(report: InspectReport) -> dict[str, object]:
    """The summary block as JSON-native fields."""
    return {
        "bars": len(report.bars),
        "counted_bars": report.counted_bars,
        "withheld_bars": report.withheld_bars,
        "substituted_bars": report.substituted_bars,
        "view_diff_bars": report.view_diff_bars,
        "view_diff_fields": dict(report.view_diff_fields),
        "disagreement_bars": report.disagreement_bars,
        "not_comparable_bars": report.not_comparable_bars,
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
        "value_view_refused": dict(report.view_refusal_counts),
    }


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
        "bars": [_bar_json(row) for row in report.bars],
        "summary": _summary_json(report),
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
