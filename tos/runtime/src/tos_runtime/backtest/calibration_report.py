"""``tos_runtime.backtest.calibration_report`` — the runtime half of the paper/backtest
calibration gate (Phase 3 wave 3 §3.1 slice E, runtime half; plan §3.1/§5).

The kernel (:mod:`tos.backtest.calibration`, lane E-K) supplies the pure gate:
:class:`~tos.backtest.calibration.FillDeviation`,
:class:`~tos.backtest.calibration.DeviationBudget`,
:func:`~tos.backtest.calibration.calibration_within_budget`, and
:func:`~tos.backtest.calibration.claim_expectancy`. This module supplies the one thing the kernel
deliberately does not: the OBSERVATIONS. It pairs a paper ``EGRESS_RESULT_CONSUMED`` evidence row
(the synthetic paper transport's applied fill) against a backtest
:class:`~tos.backtest.records.LocalFillRecord` for the same attempt, and reports what deviation,
if any, is honestly observable between them.

**Pairing key — attempt_id alone, not (strategy_digest, capsule_digest) (deviation from the
plan, stated here per the assigning brief).** The plan's §3.1 line asks to pair by
``(strategy_digest, capsule_digest)``. Neither side of this runtime's pairing carries that
key:

* :class:`~tos.engine.records.EngineEvidenceRecord` (the paper ``EGRESS_RESULT_CONSUMED`` row)
  carries ``capsule_digest`` but has **no** ``strategy_digest`` field at all — only
  ``strategy_version``/``config_version`` (``tos/src/tos/engine/records.py``).
* :class:`~tos.backtest.records.LocalFillRecord` (the backtest fill) carries **neither**
  ``capsule_digest`` nor a strategy digest of any kind.

A scope-bound pairing key is therefore not constructible from either side's own fields today.
Pairing is by ``attempt_id`` alone — the one identity both sides always carry
(``EngineEvidenceRecord.attempt_id`` / ``LocalFillRecord.attempt_id``), content-addressed from the
same Coordinator attempt in both the paper and backtest runs (design #31 §4.3). This is a
narrower correlation than the plan asked for: two DIFFERENT (strategy, capsule) runs that
happened to reuse the same attempt id (which should not occur under the kernel's own
content-addressed identity scheme, but this module cannot verify that absence) would pair here.
Widening ``EngineEvidenceRecord``/``LocalFillRecord`` to carry a strategy digest is kernel work,
out of this runtime-only lane's file scope.

**price_bps is always None (by construction, not by observation gap).** The synthetic paper
transport's :class:`~tos.engine.records.EgressResultPayload` carries no price field at all, and
the backtest side is never consulted for a price here either — this module never fabricates one
from ``LocalFillRecord.execution_price`` to pair against a paper price that structurally cannot
exist (module docstring of :mod:`tos.backtest.calibration`: "absence is not zero"). Because
every :class:`~tos.backtest.calibration.DeviationBudget` field is REQUIRED (no way to express
"price unbounded"), :func:`~tos.backtest.calibration.calibration_within_budget` is therefore
UNCONDITIONALLY ``INSUFFICIENT_OBSERVATIONS`` for every report this module produces today,
regardless of how forgiving the other three bounds are — this is the intended fail-closed outcome
until a price surface exists (Phase 4 작업 2 / Phase 7), not a bug in this module.

**latency_bars is always None (no settlement-bar coordinate on the paper side).**
:class:`~tos.engine.records.EngineEvidenceRecord` carries no bar-index / settlement-bar
coordinate of any kind — the runtime engine has no concept of "bars" at all, only the backtest
driver does. There is therefore no derivable latency deviation between a paper observation and a
backtest one in this runtime slice; every observation's ``latency_bars`` is ``None``.

**fill_ratio is a shortfall per** :class:`~tos.backtest.calibration.FillDeviation` **[E-R-3
correction — an earlier draft of this module computed a plain quotient; that was wrong and is
fixed here].** The kernel's own docstring frames it as "the fill-ratio shortfall ... below the
backtest's, or vice versa" — a non-negative MAGNITUDE that is 0 for a perfect match, symmetric for
either direction of deviation; :class:`~tos.backtest.calibration.FillDeviation`'s own
``model_validator`` refuses to construct with a negative ``fill_ratio`` at all ("a shortfall
magnitude, not a signed ratio"). This module computes exactly that: ``abs(backtest.filled_quantity
- paper.filled_quantity) / backtest.filled_quantity`` (see :func:`_fill_ratio`) — 0 on a match,
the same non-negative value whether paper under- or over-filled relative to backtest (this single
field carries no direction). ``None`` when either side never carries a fill magnitude, or the
backtest side's magnitude is zero (division is not attempted).

**Unpaired attempts are counts, never fabricated observations.** An attempt present on only one
side produces NO :class:`~tos.backtest.calibration.FillDeviation` — reporting one (with any
dimension defaulted, e.g. ``fill_ratio=0``) would silently manufacture a deviation observation
for a pairing that never happened. Unpaired attempts are reported only as
``unpaired_paper_count`` / ``unpaired_backtest_count``.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``json``) + ``tos.canonical``
+ ``tos.backtest.calibration`` (submodule path — see that module's own docstring on why it is
never re-exported from the ``tos.backtest`` package) + ``tos.backtest.records`` + ``tos.engine.records``
+ ``tos.engine.vocabulary`` + ``tos_runtime.evidence.store`` only.
"""

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
    """The paired paper-vs-backtest calibration result for one run (module docstring).

    ``observations`` holds one :class:`~tos.backtest.calibration.FillDeviation` per attempt id
    present on BOTH sides — never one for an unpaired attempt (see ``unpaired_*_count``).
    ``expectancy_claim`` carries a value only when ``verdict`` is
    :attr:`~tos.backtest.calibration.CalibrationVerdict.WITHIN` — this report never computes the
    observed expectancy itself (:func:`build_calibration_report`'s ``observed_expectancy``
    parameter is the caller-supplied, already-computed value; module docstring's "the report does
    not compute expectancy").
    """

    observations: tuple[FillDeviation, ...]
    unpaired_paper_count: int
    unpaired_backtest_count: int
    verdict: CalibrationVerdict
    expectancy_claim: ExpectancyClaim
    #: The injected :class:`~tos.backtest.calibration.DeviationBudget`'s own canonical digest —
    #: so a report can be traced back to exactly which budget it was measured against, without
    #: re-embedding the budget's own fields (which would duplicate, rather than identify, it).
    budget_config_digest: str


def read_egress_result_consumed_records(
    store: SqliteEvidenceStore,
) -> tuple[EngineEvidenceRecord, ...]:
    """The thin loader: read every ``EGRESS_RESULT_CONSUMED`` row back out of ``store``, typed.

    **No typed/payload read API exists on :class:`SqliteEvidenceStore` today (finding, not a
    choice this module made).** The store's own read surface is: :meth:`~SqliteEvidenceStore
    .replay` (digest/chain fields only, for :func:`tos.evidence.chain.verify_chain` — no
    payload), :meth:`~SqliteEvidenceStore.iter_entry_meta` (row metadata only — kind/
    record_class/seq/digests — no payload either), and the public
    :attr:`~SqliteEvidenceStore.connection` property, which the module docstring of
    :mod:`tos_runtime.evidence.backup` already documents as reused by another package for its own
    raw reads (``store.connection.backup(dest_conn)``), and which the store's own test suite
    queries directly for a payload field
    (``tos/runtime/tests/evidence/test_sinks.py``'s
    ``test_adapters_bind_runtime_identity_onto_every_record``). This function follows that same
    established precedent — reading through the already-public ``connection`` — rather than
    adding a new method to a store this lane does not own (``tos_runtime/evidence/store.py`` is
    outside this lane's file scope; other lanes may be editing it concurrently).

    Round-trip correctness: :class:`~tos_runtime.evidence.sinks.EngineEvidenceSinkAdapter` writes
    each record's payload from ``record.model_dump(mode="json")``
    (``tos_runtime/evidence/sinks.py``), and :meth:`SqliteEvidenceStore.append` wraps that in
    ``{"payload": scrubbed_payload, "masked_keys": [...]}`` before serializing it into the
    ``payload_json`` column (``tos_runtime/evidence/store.py``'s ``_append_with_scheme`` —
    confirmed by reading that method, not assumed). This function un-wraps the same shape
    (``json.loads(payload_json)["payload"]``) so ``EngineEvidenceRecord.model_validate(...)`` is
    an exact inverse of what the sink adapter wrote — verified in this module's own test suite.
    No secret field on this record is scrubbed today (``secret_keys`` is empty for the engine
    sink's own store), so unwrapping never needs to reconcile a masked value.

    Args:
        store: The evidence store to read from.

    Returns:
        Every ``EGRESS_RESULT_CONSUMED`` record, in commit (``seq``) order.
    """
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
    """Index ``EGRESS_RESULT_CONSUMED`` rows by ``attempt_id``, last commit wins.

    An attempt may be APPLIED more than once (e.g. a ``PARTIAL_FILL`` followed by a
    ``FULL_FILL``) — the most recently committed row is that attempt's current observed state.
    A row with no ``attempt_id`` (defensive — the field is optional on the model even though the
    engine always populates it for this kind) cannot be paired or counted and is skipped, never
    treated as an unpaired attempt of its own.
    """
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
    """``abs(backtest.filled_quantity - paper.filled_quantity) / backtest.filled_quantity`` —
    ``None`` if either magnitude is absent, or the backtest magnitude is zero (module docstring
    — never fabricate a divide).

    [E-R-3 correction] a non-negative SHORTFALL magnitude, matching
    :class:`~tos.backtest.calibration.FillDeviation.fill_ratio`'s own contract ("a shortfall
    magnitude, not a signed ratio" — its ``model_validator`` raises on a negative value) and its
    docstring's "below the backtest's, **or vice versa**" framing (paper under- or over-filling
    relative to backtest are the same deviation dimension here; this module has no separate field
    to carry direction). ``abs()`` is applied here, before construction — never inside
    :func:`~tos.backtest.calibration.calibration_within_budget`, which compares the (already
    non-negative, by construction) value directly (``> budget.max_fill_ratio_shortfall``, no
    ``abs()`` of its own). There is no kernel gap this papers over: a raw signed value can never
    reach that comparison, because :class:`~tos.backtest.calibration.FillDeviation` itself refuses
    to construct with ``fill_ratio < 0`` (verified directly: constructing one with
    ``Decimal("-0.2")`` raises ``pydantic.ValidationError`` wrapping the model's own
    ``BacktestIntegrityError``). 0 on an exact match; symmetric for over- or under-fill.
    """
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
    """Pair paper evidence against backtest fills and gate the calibration verdict + claim.

    Pure function — no I/O; :func:`read_egress_result_consumed_records` is the (only) impure
    counterpart a caller composes this with.

    Args:
        evidence_rows: Paper evidence rows (only ``EGRESS_RESULT_CONSUMED`` kinds are
            considered; anything else is ignored, not an error — a caller may pass an
            unfiltered evidence stream).
        backtest_fills: The backtest run's local fill records.
        budget: The injected tolerance (module docstring: this runtime slice's own observations
            always leave ``price_bps``/``latency_bars`` unobservable — see there for the
            resulting verdict consequence).
        observed_expectancy: The already-computed value the caller wishes to claim, gated by
            the resulting verdict (:func:`~tos.backtest.calibration.claim_expectancy`) — this
            function computes no expectancy of its own.

    Returns:
        The :class:`CalibrationReport`.
    """
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
