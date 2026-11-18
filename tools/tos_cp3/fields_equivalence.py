#!/usr/bin/env python3
"""P2-b — byte-identity harness: legacy-driven fields vs. the declarative ones."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.indicators.fields import (  # noqa: E402
    FieldBar,
    FieldEvalError,
    FieldEvaluator,
    FieldsDocument,
    load_fields_file,
)
from shared.instruments.contract_spec import (  # noqa: E402
    ContractSpec,
    ContractSpecRegistry,
    resolve_contract_spec,
)
from tools.tos_cp3.minute_probe import seed_capacity  # noqa: E402
from tools.tos_cp3.produce_fields import (  # noqa: E402
    DEFAULT_MIN_BARS_PER_DAY,
    AssetClass,
    OpenAnchor,
    ProduceFieldsError,
    StrategyInputs,
    _inputs_unusable,
    derive_raw_event_id,
    load_bars,
    load_stitched_bars,
    load_strategy_inputs,
    produce_bars,
    replay_admission_offset,
    resolve_open_anchor,
)
from tools.tos_cp3.stitch import load_manifest  # noqa: E402

DEFAULT_STRATEGY_YAML = (
    REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)

SESSION_MARKET_SUBDIR = "producer/market"
SESSION_JOURNAL = "journal.jsonl"
SESSION_STITCH = "stitch.json"

PRODUCER_CONFIG_GLOB = "config/tos_probes/cp3-live-producer*.yaml"


class EquivalenceError(RuntimeError):
    """The harness cannot run the comparison it was asked for."""


@dataclass(frozen=True)
class Divergence:
    """One bar × field where the two producers disagree."""

    raw_event_id: str
    bar_kst: str
    published_field: str
    legacy: Any
    declared: Any
    legacy_eval: dict[str, Any]

    def render(self) -> str:
        """One line per the plan's required shape: field · bar · both values."""
        reached = ",".join(sorted(self.legacy_eval))
        return (
            f"{self.published_field}  {self.bar_kst}  "
            f"legacy={self.legacy!r} declared={self.declared!r}  "
            f"last_eval_keys=[{reached}]"
        )


@dataclass(frozen=True)
class EquivalenceResult:
    """What one comparison measured. Rendered as the PR's one table (R7)."""

    mode: str
    symbol: str
    asset_class: str
    emit_days: tuple[date, ...]
    bars_replayed: int
    bars_compared: int
    published_fields: tuple[str, ...]
    divergences: tuple[Divergence, ...]
    legacy_omitted: tuple[tuple[str, str], ...]
    declared_omitted: tuple[tuple[str, str], ...]
    legacy_only_ids: tuple[str, ...]
    declared_only_ids: tuple[str, ...]
    capacity_before_first_compared_day: int
    capacity_required: int
    legacy_missing_fields: tuple[tuple[str, str], ...] = field(default=())
    journal_rows: int = 0
    journal_compared: int = 0
    journal_divergences: tuple[Divergence, ...] = field(default=())
    journal_unmatched_ids: tuple[str, ...] = field(default=())
    journal_missing_fields: tuple[tuple[str, str], ...] = field(default=())
    journal_declared_only_ids: tuple[str, ...] = field(default=())

    @property
    def cells_compared(self) -> int:
        """Bar × field cells actually compared."""
        return self.bars_compared * len(self.published_fields)

    @property
    def capacity_satisfied(self) -> bool:
        """Was the causal vol window FILLED before the first compared day?"""
        return self.capacity_before_first_compared_day >= self.capacity_required

    @property
    def journal_fully_matched(self) -> bool:
        """Did every journal row find a counterpart, with every field present?"""
        return not self.journal_unmatched_ids and not self.journal_missing_fields

    @property
    def omitted_lists_agree(self) -> bool:
        """Do both sides omit exactly the same BARS?"""
        return sorted(bar for bar, _ in self.legacy_omitted) == sorted(
            bar for bar, _ in self.declared_omitted
        )

    @property
    def bar_sets_agree(self) -> bool:
        return not self.legacy_only_ids and not self.declared_only_ids

    @property
    def passed(self) -> bool:
        """Every way this comparison can fail, including failing to compare."""
        return (
            not self.divergences
            and not self.journal_divergences
            and self.omitted_lists_agree
            and self.bar_sets_agree
            and self.bars_compared > 0
            and not self.legacy_missing_fields
            and self.journal_fully_matched
            and self.capacity_satisfied
            and (self.mode != "session" or self.journal_compared > 0)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "emit_days": [day.isoformat() for day in self.emit_days],
            "bars_replayed": self.bars_replayed,
            "bars_compared": self.bars_compared,
            "published_fields": list(self.published_fields),
            "cells_compared": self.cells_compared,
            "divergences": len(self.divergences),
            "first_divergences": [
                {
                    "field": d.published_field,
                    "bar_kst": d.bar_kst,
                    "legacy": d.legacy,
                    "declared": d.declared,
                    "legacy_eval_keys": sorted(d.legacy_eval),
                }
                for d in self.divergences[:20]
            ],
            "legacy_omitted": len(self.legacy_omitted),
            "declared_omitted": len(self.declared_omitted),
            "omitted_bars": [
                {"bar": bar, "legacy_reason": reason}
                for bar, reason in self.legacy_omitted[:20]
            ],
            "declared_omitted_reasons": [
                {"bar": bar, "reason": reason}
                for bar, reason in self.declared_omitted[:20]
            ],
            "omitted_lists_agree": self.omitted_lists_agree,
            "legacy_only_bars": list(self.legacy_only_ids[:20]),
            "declared_only_bars": list(self.declared_only_ids[:20]),
            "capacity_before_first_compared_day": (
                self.capacity_before_first_compared_day
            ),
            "capacity_required": self.capacity_required,
            "capacity_satisfied": self.capacity_satisfied,
            "legacy_missing_fields": len(self.legacy_missing_fields),
            "first_legacy_missing_fields": [
                {"bar": bar, "field": name}
                for bar, name in self.legacy_missing_fields[:20]
            ],
            "journal_rows": self.journal_rows,
            "journal_compared": self.journal_compared,
            "journal_divergences": len(self.journal_divergences),
            "first_journal_divergences": [
                {
                    "field": d.published_field,
                    "bar_kst": d.bar_kst,
                    "journal": d.legacy,
                    "declared": d.declared,
                }
                for d in self.journal_divergences[:20]
            ],
            "journal_unmatched_ids": len(self.journal_unmatched_ids),
            "first_journal_unmatched_ids": list(self.journal_unmatched_ids[:20]),
            "journal_missing_fields": len(self.journal_missing_fields),
            "first_journal_missing_fields": [
                {"bar": bar, "field": name}
                for bar, name in self.journal_missing_fields[:20]
            ],
            "journal_declared_only_ids": len(self.journal_declared_only_ids),
            "first_journal_declared_only_ids": list(
                self.journal_declared_only_ids[:20]
            ),
            "journal_fully_matched": self.journal_fully_matched,
            "passed": self.passed,
        }

    def render(self) -> str:
        """The measurement record: command's numbers, one block (R7)."""
        lines = [
            f"mode                 {self.mode}",
            f"symbol               {self.symbol} ({self.asset_class})",
            f"emit days            {len(self.emit_days)}"
            + (
                f"  {self.emit_days[0]}..{self.emit_days[-1]}" if self.emit_days else ""
            ),
            f"bars replayed        {self.bars_replayed}",
            f"bars compared        {self.bars_compared}",
            f"fields per bar       {len(self.published_fields)}",
            f"cells compared       {self.cells_compared}",
            f"divergences          {len(self.divergences)}",
            f"omitted (legacy)     {len(self.legacy_omitted)}",
            f"omitted (declared)   {len(self.declared_omitted)}",
            f"omitted lists agree  {self.omitted_lists_agree}",
            f"bar sets agree       {self.bar_sets_agree}",
            f"seed capacity        {self.capacity_before_first_compared_day} "
            f"(required {self.capacity_required}, "
            f"{'OK' if self.capacity_satisfied else 'SHORT'})",
        ]
        if self.mode == "session" or self.journal_rows:
            lines += [
                f"journal rows         {self.journal_rows}",
                f"journal bars         {self.journal_compared}",
                f"journal divergences  {len(self.journal_divergences)}",
                f"journal unmatched    {len(self.journal_unmatched_ids)}",
                f"journal missing flds {len(self.journal_missing_fields)}",
                f"declared-only bars   {len(self.journal_declared_only_ids)} "
                "(reported, not fatal — frame bars the journal never carried: "
                "the session's stop, or a publication gap inside it)",
            ]
        lines.append(f"VERDICT              {'PASS' if self.passed else 'FAIL'}")
        for divergence in self.divergences[:20]:
            lines.append(f"  ! {divergence.render()}")
        for divergence in self.journal_divergences[:20]:
            lines.append(f"  !journal {divergence.render()}")
        for bar, name in self.legacy_missing_fields[:20]:
            lines.append(
                f"  ! the legacy record for {bar} carries no published field {name!r}"
            )
        for extra in self.journal_unmatched_ids[:20]:
            lines.append(
                f"  ! the journal published a bar the declaration did not: {extra}"
            )
        for bar, name in self.journal_missing_fields[:20]:
            lines.append(f"  ! the journal row {bar} carries no field {name!r}")
        for extra in self.legacy_only_ids[:10]:
            lines.append(f"  ! legacy emitted a bar the declaration did not: {extra}")
        for extra in self.declared_only_ids[:10]:
            lines.append(f"  ! declaration emitted a bar the legacy did not: {extra}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Inputs:
    """The frame and the three things both producers need to run on it."""

    df: Any
    symbol: str
    asset_class: AssetClass
    strategy: StrategyInputs
    contract_spec: ContractSpec
    anchor: OpenAnchor
    document: FieldsDocument
    emit_days: frozenset[date]


def producer_open_anchor(asset_class: AssetClass) -> str:
    """The ``open_anchor`` the live producer config for *asset_class* declares."""
    matches: list[tuple[Path, str]] = []
    for path in sorted(REPO_ROOT.glob(PRODUCER_CONFIG_GLOB)):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("market") != asset_class:
            continue
        anchor = raw.get("open_anchor")
        if not isinstance(anchor, str) or not anchor:
            raise EquivalenceError(
                f"{path}: market {asset_class!r} declares no usable open_anchor "
                f"(got {anchor!r})"
            )
        matches.append((path, anchor))
    if len(matches) != 1:
        raise EquivalenceError(
            f"expected exactly one {PRODUCER_CONFIG_GLOB} declaring "
            f"market {asset_class!r}, found {len(matches)} "
            f"({[str(p) for p, _ in matches]}). Pass --market-open explicitly "
            "rather than letting the harness pick an anchor."
        )
    return matches[0][1]


def _contract_spec(
    symbol: str, *, asset_class: AssetClass, execution_yaml: Path
) -> ContractSpec:
    """Resolve the spec the same way the live producer does."""
    block = (
        "futures_contract_spec" if asset_class == "futures" else "stock_contract_spec"
    )
    registry = ContractSpecRegistry.from_yaml(str(execution_yaml), block=block)
    return resolve_contract_spec(symbol, registry)


def _session_days(df: Any) -> list[date]:
    return sorted({stamp.date() for stamp in df["timestamp"]})


def _capacity_before(
    df: Any, *, first_compared: date, strategy: StrategyInputs, anchor: OpenAnchor
) -> int:
    """``seed_capacity`` of the frame standing BEFORE *first_compared*."""
    seed = df[df["timestamp"].dt.date < first_compared]
    return int(seed_capacity(seed, strategy, anchor))


def load_inputs(
    *,
    mode: str,
    data_root: Path,
    symbol: str,
    asset_class: AssetClass,
    fields_yaml: Path,
    strategy_yaml: Path,
    execution_yaml: Path,
    market_open: str,
    min_bars_per_day: int,
    start: date | None = None,
    end: date | None = None,
    stitch_manifest: Path | None = None,
    emit_days: Iterable[date] | None = None,
    seed_sessions: int = 0,
) -> Inputs:
    """Load the frame and resolve everything both producers read."""
    strategy = load_strategy_inputs(strategy_yaml)
    document = load_fields_file(fields_yaml)

    if mode == "window":
        if start is None or end is None:
            raise EquivalenceError("mode 'window' needs --start and --end")
        df, _loaded = load_bars(
            data_root,
            asset_class=asset_class,
            symbol=symbol,
            start=start,
            end=end,
            min_bars_per_day=min_bars_per_day,
        )
    else:
        if stitch_manifest is None:
            raise EquivalenceError(f"mode {mode!r} needs a stitch manifest")
        manifest = load_manifest(stitch_manifest)
        df, _loaded, _files, _stitched = load_stitched_bars(
            data_root,
            asset_class=asset_class,
            manifest=manifest,
            min_bars_per_day=min_bars_per_day,
        )

    days = _session_days(df)
    if not days:
        raise EquivalenceError("the loaded frame has no bars")
    if emit_days is not None:
        targets = frozenset(emit_days)
    else:
        targets = frozenset(days[seed_sessions:])
    if not targets:
        raise EquivalenceError(
            f"no days left to compare: the frame has {len(days)} session(s) and "
            f"{seed_sessions} were dropped as seed"
        )

    anchor = resolve_open_anchor(
        cli_value=market_open, first_session=days[0], last_session=days[-1]
    )
    _assert_anchor_agrees(document, anchor=anchor, fields_yaml=fields_yaml)
    return Inputs(
        df=df,
        symbol=symbol,
        asset_class=asset_class,
        strategy=strategy,
        contract_spec=_contract_spec(
            symbol, asset_class=asset_class, execution_yaml=execution_yaml
        ),
        anchor=anchor,
        document=document,
        emit_days=targets,
    )


def _assert_anchor_agrees(
    document: FieldsDocument, *, anchor: OpenAnchor, fields_yaml: Path
) -> None:
    """Refuse a declaration whose open anchor is not the run's anchor."""
    declared = [
        spec for spec in document.fields if spec.op_name == "session.minutes_since_open"
    ]
    if not declared:
        raise EquivalenceError(
            f"{fields_yaml}: declares no session.minutes_since_open, so the "
            "entry window cannot be reproduced"
        )
    for spec in declared:
        hour = int(spec.params["open_hour"])
        minute = int(spec.params["open_minute"])
        if (hour, minute) != (anchor.hour, anchor.minute):
            raise EquivalenceError(
                f"{fields_yaml}: field {spec.name!r} pins the open anchor at "
                f"{hour:02d}:{minute:02d}, but this window resolves to "
                f"{anchor.hour:02d}:{anchor.minute:02d} ({anchor.source}). "
                "Every minutes_since_open would be shifted, so the comparison "
                "would measure the anchor rather than the fields."
            )


def run_declarative(
    inputs: Inputs,
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]]]:
    """Evaluate ``fields.yaml`` over the frame and emit the same bars B1a would."""
    evaluator = FieldEvaluator(inputs.document)
    records: dict[str, dict[str, Any]] = {}
    omitted: list[tuple[str, str]] = []
    admitted_from = replay_admission_offset(inputs.df)
    for index, row in enumerate(inputs.df.itertuples(index=False)):
        bar = FieldBar.create(
            row.timestamp,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        if index < admitted_from:
            evaluator.warm(bar)
            continue
        raw_event_id = derive_raw_event_id(inputs.symbol, bar.ts_kst)
        try:
            evaluated = evaluator.step(bar)
        except FieldEvalError as exc:
            if bar.ts_kst.date() in inputs.emit_days:
                omitted.append((raw_event_id, f"evaluator refused: {exc}"))
            continue
        if bar.ts_kst.date() not in inputs.emit_days:
            continue
        values = evaluated.values
        unusable = _inputs_unusable(
            *(_number(values, name) for name in ("close", "vwap", "atr"))
        )
        if unusable is not None:
            omitted.append((raw_event_id, unusable))
            continue
        records[raw_event_id] = dict(evaluated.published)
    return records, omitted


def _number(values: Mapping[str, Any], name: str) -> float:
    """Read a declared NUMBER field, refusing a shape the omission gate cannot use."""
    value = values.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EquivalenceError(
            f"the declaration's {name!r} is {value!r}, which the omission gate "
            "cannot read as a price — fields.yaml must declare close, vwap and "
            "atr as numbers"
        )
    return float(value)


def run_legacy(
    inputs: Inputs,
) -> tuple[
    dict[str, dict[str, Any]], list[tuple[str, str]], int, dict[str, dict[str, Any]]
]:
    """Drive the legacy setup bar by bar and collect what it publishes."""
    traces: dict[str, dict[str, Any]] = {}

    def observe(bar_kst: Any, evaluation: Any) -> None:
        traces[bar_kst.isoformat()] = dict(evaluation)

    produced = produce_bars(
        inputs.df,
        symbol=inputs.symbol,
        strategy=inputs.strategy,
        contract_spec=inputs.contract_spec,
        anchor=inputs.anchor,
        emit_days=inputs.emit_days,
        observer=observe,
    )
    records = {record.raw_event_id: dict(record.fields) for record in produced.records}
    return records, list(produced.omitted), produced.bars_replayed, traces


def _bar_kst_of(raw_event_id: str) -> str:
    """The timestamp token of a join key, for a readable report."""
    return raw_event_id.rsplit(":", 1)[-1]


def compare(
    inputs: Inputs,
    *,
    mode: str,
    journal: Path | None = None,
) -> EquivalenceResult:
    """Run both producers over one frame and compare every emitted cell."""
    legacy, legacy_omitted, replayed, traces = run_legacy(inputs)
    declared, declared_omitted = run_declarative(inputs)

    published_fields = tuple(entry.name for entry in inputs.document.publish)
    shared_ids = sorted(set(legacy) & set(declared))
    divergences: list[Divergence] = []
    legacy_missing_fields: list[tuple[str, str]] = []
    for raw_event_id in shared_ids:
        legacy_fields = legacy[raw_event_id]
        declared_fields = declared[raw_event_id]
        for name in published_fields:
            if name not in legacy_fields:
                legacy_missing_fields.append((raw_event_id, name))
                continue
            left = legacy_fields[name]
            right = declared_fields[name]
            if type(left) is not type(right) or left != right:
                bar_kst = _bar_kst_of(raw_event_id)
                divergences.append(
                    Divergence(
                        raw_event_id=raw_event_id,
                        bar_kst=bar_kst,
                        published_field=name,
                        legacy=left,
                        declared=right,
                        legacy_eval=_trace_for(traces, bar_kst),
                    )
                )

    first_compared = min(inputs.emit_days)
    journal_result = (
        _compare_journal(journal, declared=declared, published_fields=published_fields)
        if journal is not None
        else JournalComparison(
            rows=0,
            compared=0,
            divergences=(),
            unmatched_ids=(),
            missing_fields=(),
            declared_only_ids=(),
        )
    )

    return EquivalenceResult(
        mode=mode,
        symbol=inputs.symbol,
        asset_class=inputs.asset_class,
        emit_days=tuple(sorted(inputs.emit_days)),
        bars_replayed=replayed,
        bars_compared=len(shared_ids),
        published_fields=published_fields,
        divergences=tuple(divergences),
        legacy_omitted=tuple(legacy_omitted),
        declared_omitted=tuple(declared_omitted),
        legacy_only_ids=tuple(sorted(set(legacy) - set(declared))),
        declared_only_ids=tuple(sorted(set(declared) - set(legacy))),
        capacity_before_first_compared_day=_capacity_before(
            inputs.df,
            first_compared=first_compared,
            strategy=inputs.strategy,
            anchor=inputs.anchor,
        ),
        capacity_required=int(inputs.strategy.entry_config.vol_window_bars),
        legacy_missing_fields=tuple(legacy_missing_fields),
        journal_rows=journal_result.rows,
        journal_compared=journal_result.compared,
        journal_divergences=journal_result.divergences,
        journal_unmatched_ids=journal_result.unmatched_ids,
        journal_missing_fields=journal_result.missing_fields,
        journal_declared_only_ids=journal_result.declared_only_ids,
    )


def _trace_for(traces: dict[str, dict[str, Any]], bar_kst: str) -> dict[str, Any]:
    for key, value in traces.items():
        if key.replace("-", "").replace(":", "").startswith(bar_kst[:15]):
            return value
    return {}


@dataclass(frozen=True)
class JournalComparison:
    """What comparing against one session's published journal measured."""

    rows: int
    compared: int
    divergences: tuple[Divergence, ...]
    unmatched_ids: tuple[str, ...]
    missing_fields: tuple[tuple[str, str], ...]
    declared_only_ids: tuple[str, ...]


def _compare_journal(
    path: Path,
    *,
    declared: dict[str, dict[str, Any]],
    published_fields: Sequence[str],
) -> JournalComparison:
    """Compare the declarative output against a session's PUBLISHED journal."""
    divergences: list[Divergence] = []
    unmatched: list[str] = []
    missing_fields: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    rows = 0
    compared = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows += 1
        row = json.loads(line)
        raw_event_id = row["raw_event_id"]
        seen_ids.add(raw_event_id)
        mine = declared.get(raw_event_id)
        if mine is None:
            unmatched.append(raw_event_id)
            continue
        compared += 1
        theirs = row["fields"]
        for name in published_fields:
            if name not in theirs:
                missing_fields.append((raw_event_id, name))
                continue
            left = theirs[name]
            right = mine[name]
            if type(left) is not type(right) or left != right:
                divergences.append(
                    Divergence(
                        raw_event_id=raw_event_id,
                        bar_kst=_bar_kst_of(raw_event_id),
                        published_field=name,
                        legacy=left,
                        declared=right,
                        legacy_eval={},
                    )
                )
    return JournalComparison(
        rows=rows,
        compared=compared,
        divergences=tuple(divergences),
        unmatched_ids=tuple(sorted(unmatched)),
        missing_fields=tuple(missing_fields),
        declared_only_ids=tuple(sorted(set(declared) - seen_ids)),
    )


@dataclass(frozen=True)
class RecordedSession:
    """A session directory the live producer wrote, read ONLY."""

    root: Path
    market_root: Path
    stitch_manifest: Path
    journal: Path
    symbol: str
    asset_class: AssetClass
    target_day: date

    @classmethod
    def open(cls, root: Path) -> RecordedSession:
        """Locate a recorded session's frozen frame, manifest and journal."""
        market_root = root / SESSION_MARKET_SUBDIR
        manifest_path = market_root / SESSION_STITCH
        journal = root / SESSION_JOURNAL
        for required in (market_root, manifest_path, journal):
            if not required.exists():
                raise EquivalenceError(
                    f"{root}: not a recorded producer session ({required} missing)"
                )
        manifest = load_manifest(manifest_path)
        asset_class: AssetClass = (
            "stock" if (market_root / "stock").is_dir() else "futures"
        )
        days = sorted(day for segment in manifest.segments for day in segment.days)
        return cls(
            root=root,
            market_root=market_root,
            stitch_manifest=manifest_path,
            journal=journal,
            symbol=manifest.symbol,
            asset_class=asset_class,
            target_day=days[-1],
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the legacy-driven CP-3 field producer with the declarative "
            "fields.yaml evaluator, bar by bar and field by field."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("window", "stitched", "session"),
        required=True,
        help=(
            "window: a plain [start, end] Parquet window. stitched: exactly a "
            "stitch manifest's (contract, day) pairs — the live producer's "
            "invocation shape. session: a recorded session directory, which also "
            "compares against its published journal.jsonl."
        ),
    )
    parser.add_argument("--fields-yaml", type=Path, required=True)
    parser.add_argument("--strategy-yaml", type=Path, default=DEFAULT_STRATEGY_YAML)
    parser.add_argument(
        "--execution-yaml", type=Path, default=REPO_ROOT / "config" / "execution.yaml"
    )
    parser.add_argument("--data-root", type=Path, default=REPO_ROOT / "data" / "market")
    parser.add_argument("--symbol")
    parser.add_argument("--asset-class", choices=("futures", "stock"))
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--stitch-manifest", type=Path)
    parser.add_argument(
        "--session-dir",
        type=Path,
        help="mode 'session': a recorded cp3-sessions/<id> directory (read-only)",
    )
    parser.add_argument(
        "--seed-sessions",
        type=int,
        default=0,
        help=(
            "mode 'window': leading sessions to leave out of the compared set. "
            "The capacity the run actually had is reported regardless."
        ),
    )
    parser.add_argument(
        "--market-open",
        default=None,
        help=(
            "HH:MM, or 'auto' for the era rule "
            "(produce_fields.resolve_open_anchor). Left out: 'auto' in window "
            "and stitched mode; in session mode the anchor the live producer "
            "config for the session's own market declares, so a stock session "
            "needs no flag"
        ),
    )
    parser.add_argument(
        "--min-bars-per-day", type=int, default=DEFAULT_MIN_BARS_PER_DAY
    )
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "session":
            if args.session_dir is None:
                raise EquivalenceError("mode 'session' needs --session-dir")
            session = RecordedSession.open(args.session_dir)
            inputs = load_inputs(
                mode="session",
                data_root=session.market_root,
                symbol=session.symbol,
                asset_class=session.asset_class,
                fields_yaml=args.fields_yaml,
                strategy_yaml=args.strategy_yaml,
                execution_yaml=args.execution_yaml,
                market_open=(
                    args.market_open
                    if args.market_open is not None
                    else producer_open_anchor(session.asset_class)
                ),
                min_bars_per_day=args.min_bars_per_day,
                stitch_manifest=session.stitch_manifest,
                emit_days=[session.target_day],
            )
            result = compare(inputs, mode="session", journal=session.journal)
        else:
            if not args.symbol or not args.asset_class:
                raise EquivalenceError(
                    f"mode {args.mode!r} needs --symbol and --asset-class"
                )
            inputs = load_inputs(
                mode=args.mode,
                data_root=args.data_root,
                symbol=args.symbol,
                asset_class=args.asset_class,
                fields_yaml=args.fields_yaml,
                strategy_yaml=args.strategy_yaml,
                execution_yaml=args.execution_yaml,
                market_open=args.market_open or "auto",
                min_bars_per_day=args.min_bars_per_day,
                start=args.start,
                end=args.end,
                stitch_manifest=args.stitch_manifest,
                seed_sessions=args.seed_sessions,
            )
            result = compare(inputs, mode=args.mode)
    except (EquivalenceError, ProduceFieldsError) as exc:
        print(f"fields_equivalence: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_payload(), indent=2, ensure_ascii=False))
    else:
        print(result.render())
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
