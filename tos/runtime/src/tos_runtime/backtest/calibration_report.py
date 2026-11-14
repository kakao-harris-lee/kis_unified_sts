"""``tos_runtime.backtest.calibration_report`` — the runtime half of the paper/backtest"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tos.backtest.calibration import (
    CalibrationVerdict,
    DeviationBudget,
    ExpectancyClaim,
    FillDeviation,
    calibration_within_budget,
    claim_expectancy,
)
from tos.backtest.records import LocalFillRecord
from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalDecimal, get_scheme
from tos.engine.records import EngineEvidenceRecord
from tos.engine.vocabulary import EvidenceKind

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = [
    "CalibrationReport",
    "build_calibration_report",
    "read_egress_result_consumed_records",
]

_BUDGET_DIGEST_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


@dataclass(frozen=True)
class CalibrationReport:
    """The paired paper-vs-backtest calibration result for one run (module docstring)."""

    observations: tuple[FillDeviation, ...]
    unpaired_paper_count: int
    unpaired_backtest_count: int
    verdict: CalibrationVerdict
    expectancy_claim: ExpectancyClaim
    budget_config_digest: str


def read_egress_result_consumed_records(
    store: SqliteEvidenceStore,
) -> tuple[EngineEvidenceRecord, ...]:
    """The thin loader: read every ``EGRESS_RESULT_CONSUMED`` row back out of ``store``, typed."""
    rows = store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (EvidenceKind.EGRESS_RESULT_CONSUMED.value,),
    ).fetchall()
    return tuple(
        EngineEvidenceRecord.model_validate(json.loads(payload_json)["payload"])
        for (payload_json,) in rows
    )


def _latest_paper_by_attempt(
    evidence_rows: Sequence[EngineEvidenceRecord],
) -> dict[str, EngineEvidenceRecord]:
    """Index ``EGRESS_RESULT_CONSUMED`` rows by ``attempt_id``, last commit wins."""
    by_attempt: dict[str, EngineEvidenceRecord] = {}
    for row in evidence_rows:
        if row.kind is not EvidenceKind.EGRESS_RESULT_CONSUMED:
            continue
        if row.attempt_id is None:
            continue
        by_attempt[row.attempt_id] = row
    return by_attempt


def _latest_backtest_by_attempt(
    backtest_fills: Sequence[LocalFillRecord],
) -> dict[str, LocalFillRecord]:
    """Index backtest fills by ``attempt_id`` (required, non-``None`` on this record), last wins."""
    by_attempt: dict[str, LocalFillRecord] = {}
    for fill in backtest_fills:
        by_attempt[fill.attempt_id] = fill
    return by_attempt


def _fill_ratio(
    paper: EngineEvidenceRecord, backtest: LocalFillRecord
) -> CanonicalDecimal | None:
    """``abs(backtest.filled_quantity - paper.filled_quantity) / backtest.filled_quantity`` —"""
    paper_filled = paper.filled_quantity
    backtest_filled = backtest.filled_quantity
    if paper_filled is None or backtest_filled is None or backtest_filled == 0:
        return None
    return abs(backtest_filled - paper_filled) / backtest_filled


def _pair_deviation(
    paper: EngineEvidenceRecord, backtest: LocalFillRecord
) -> FillDeviation:
    """One paired observation — ``price_bps``/``latency_bars`` always ``None`` (module docstring)."""
    return FillDeviation(
        price_bps=None,
        fill_ratio=_fill_ratio(paper, backtest),
        latency_bars=None,
    )


def _budget_config_digest(budget: DeviationBudget) -> str:
    """The injected budget's own canonical digest (module: ``CalibrationReport.budget_config_digest``)."""
    covered: Mapping[str, object] = budget.model_dump(mode="json")
    return _BUDGET_DIGEST_SCHEME.compute_digest(dict(covered))


def build_calibration_report(
    *,
    evidence_rows: Sequence[EngineEvidenceRecord],
    backtest_fills: Sequence[LocalFillRecord],
    budget: DeviationBudget,
    observed_expectancy: CanonicalDecimal,
) -> CalibrationReport:
    """Pair paper evidence against backtest fills and gate the calibration verdict + claim."""
    paper_by_attempt = _latest_paper_by_attempt(evidence_rows)
    backtest_by_attempt = _latest_backtest_by_attempt(backtest_fills)

    paper_ids = set(paper_by_attempt)
    backtest_ids = set(backtest_by_attempt)
    paired_ids = sorted(paper_ids & backtest_ids)

    observations = tuple(
        _pair_deviation(paper_by_attempt[attempt_id], backtest_by_attempt[attempt_id])
        for attempt_id in paired_ids
    )
    verdict = calibration_within_budget(observations, budget)
    expectancy_claim = claim_expectancy(observed_expectancy, verdict)

    return CalibrationReport(
        observations=observations,
        unpaired_paper_count=len(paper_ids - backtest_ids),
        unpaired_backtest_count=len(backtest_ids - paper_ids),
        verdict=verdict,
        expectancy_claim=expectancy_claim,
        budget_config_digest=_budget_config_digest(budget),
    )
