"""``tos_runtime.backtest`` tests — the paper/backtest calibration report (Phase 3 wave 3 §3.1
slice E, runtime half; plan §3.1 / §5).

Covers: config load (fill/null-leaf/unknown-key), attempt-id pairing (matching + the two
one-sided unpaired cases), the three kernel verdict branches reached through injected budgets,
the price-unobservable-always-INSUFFICIENT consequence, the expectancy-claim withholding, and the
loader reading typed :class:`~tos.engine.records.EngineEvidenceRecord` rows back out of a real
:class:`~tos_runtime.evidence.store.SqliteEvidenceStore`.

**Pairing-key limitation (see ``calibration_report.py`` module docstring for the full
statement).** The plan asks to pair paper/backtest observations by the same
``(strategy_digest, capsule_digest)`` scope. Neither side of this runtime slice's pairing carries
that: :class:`~tos.engine.records.EngineEvidenceRecord` (the paper ``EGRESS_RESULT_CONSUMED`` row)
has ``capsule_digest`` but no ``strategy_digest`` field at all, and
:class:`~tos.backtest.records.LocalFillRecord` (the backtest fill) has neither. Pairing is
therefore by ``attempt_id`` alone, unconditionally — every test below reflects that.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.backtest.calibration import CalibrationVerdict, DeviationBudget
from tos.backtest.records import LocalFillRecord
from tos.backtest.vocabulary import QuantityProvenance, SettlementStatus
from tos.engine.records import EngineEvidenceRecord, InstrumentKey
from tos.engine.vocabulary import EgressResultKind, EvidenceKind
from tos_runtime.backtest.calibration_report import (
    build_calibration_report,
    read_egress_result_consumed_records,
)
from tos_runtime.backtest.config import (
    BacktestCalibrationConfigError,
    load_backtest_calibration_config,
)
from tos_runtime.evidence.store import SqliteEvidenceStore

# ---------------------------------------------------------------------------
# fixtures / small builders
# ---------------------------------------------------------------------------


class _FixedKeyProvider:
    """A local :class:`KeyProvider` double — this test file owns no shared conftest fixture."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes")

    def generations(self) -> tuple[int, ...]:
        return (1,)


@pytest.fixture
def store(tmp_path: Path) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=_FixedKeyProvider()
    )
    yield instance
    instance.close()


def _budget(
    *,
    max_price_bps: Decimal = Decimal(10),
    max_fill_ratio_shortfall: Decimal = Decimal(10),
    max_latency_bars: int = 10,
    min_observations: int = 1,
) -> DeviationBudget:
    return DeviationBudget(
        max_price_bps=max_price_bps,
        max_fill_ratio_shortfall=max_fill_ratio_shortfall,
        max_latency_bars=max_latency_bars,
        min_observations=min_observations,
    )


def _paper_row(attempt_id: str, *, filled: Decimal | None) -> EngineEvidenceRecord:
    return EngineEvidenceRecord(
        kind=EvidenceKind.EGRESS_RESULT_CONSUMED,
        attempt_id=attempt_id,
        filled_quantity=filled,
        remaining_quantity=Decimal(0) if filled is not None else None,
    )


_KEY = InstrumentKey(account="acct-1", instrument="instr-1")


def _backtest_fill(attempt_id: str, *, filled: Decimal | None) -> LocalFillRecord:
    is_positive_fill = filled is not None and filled > 0
    return LocalFillRecord(
        attempt_id=attempt_id,
        instrument_key=_KEY,
        decision_bar_index=0,
        settlement_bar_index=0,
        settlement_status=SettlementStatus.SETTLED,
        result_kind=(
            EgressResultKind.FULL_FILL if is_positive_fill else EgressResultKind.REJECT
        ),
        side="BUY",
        quantity_provenance=QuantityProvenance.SCENARIO_PARAMETER,
        filled_quantity=filled,
        remaining_quantity=Decimal(0) if filled is not None else None,
    )


# ---------------------------------------------------------------------------
# pairing
# ---------------------------------------------------------------------------


def test_matching_attempt_id_produces_one_paired_observation() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    assert len(report.observations) == 1
    assert report.unpaired_paper_count == 0
    assert report.unpaired_backtest_count == 0


def test_paper_only_attempt_is_counted_unpaired_not_a_zero_deviation() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    assert report.observations == ()
    assert report.unpaired_paper_count == 1
    assert report.unpaired_backtest_count == 0


def test_backtest_only_attempt_is_counted_unpaired_not_a_zero_deviation() -> None:
    """Mutation to quote: if the report treated an unpaired backtest fill as
    ``fill_ratio=0`` instead of a plain unpaired count, ``report.observations`` here would be
    non-empty (one manufactured ``FillDeviation(fill_ratio=Decimal(0), ...)``) and this
    assertion goes red."""
    report = build_calibration_report(
        evidence_rows=(),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    assert report.observations == ()
    assert report.unpaired_paper_count == 0
    assert report.unpaired_backtest_count == 1


def test_multiple_disjoint_attempts_pair_only_the_matching_ids() -> None:
    report = build_calibration_report(
        evidence_rows=(
            _paper_row("a1", filled=Decimal(10)),
            _paper_row("a2", filled=Decimal(5)),
        ),
        backtest_fills=(
            _backtest_fill("a2", filled=Decimal(5)),
            _backtest_fill("a3", filled=Decimal(1)),
        ),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    assert len(report.observations) == 1
    assert report.unpaired_paper_count == 1
    assert report.unpaired_backtest_count == 1


# ---------------------------------------------------------------------------
# fill_ratio / latency_bars / price_bps semantics
# ---------------------------------------------------------------------------


def test_fill_ratio_is_a_shortfall_magnitude_when_paper_underfills() -> None:
    """[E-R-3] shortfall = abs(backtest - paper) / backtest, matching
    ``FillDeviation.fill_ratio``'s own "shortfall magnitude, not a signed ratio" contract.
    """
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(8)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.fill_ratio == Decimal(2) / Decimal(10)


def test_fill_ratio_is_symmetric_when_paper_overfills_relative_to_backtest() -> None:
    """[E-R-3] "below the backtest's, or vice versa" (kernel docstring) — paper filling MORE
    than backtest is the same deviation dimension, reported as the same non-negative magnitude
    a matching under-fill would produce, never a negative value (FillDeviation would refuse to
    construct one — see calibration_report.py's ``_fill_ratio`` docstring)."""
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(12)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.fill_ratio == Decimal(2) / Decimal(10)
    assert observation.fill_ratio >= 0


def test_fill_ratio_is_zero_on_an_exact_match() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.fill_ratio == Decimal(0)


def test_fill_ratio_is_none_when_backtest_filled_quantity_is_zero() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(8)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(0)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.fill_ratio is None


def test_fill_ratio_is_none_when_either_side_never_filled() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=None),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.fill_ratio is None


def test_latency_bars_is_always_none_no_bar_coordinate_on_paper_evidence() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.latency_bars is None


def test_price_bps_is_always_none_no_price_on_synthetic_paper_transport() -> None:
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    (observation,) = report.observations
    assert observation.price_bps is None


def test_price_unobservable_forces_insufficient_because_budget_requires_all_four_fields() -> (
    None
):
    """Every :class:`DeviationBudget` field is required (no "unbounded" representation) — so
    with ``price_bps`` always ``None`` on this runtime's observations, the verdict is
    unconditionally INSUFFICIENT_OBSERVATIONS today, regardless of how forgiving the injected
    budget otherwise is."""
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(
            max_price_bps=Decimal(999999),
            max_fill_ratio_shortfall=Decimal(999999),
            max_latency_bars=999999,
            min_observations=0,
        ),
        observed_expectancy=Decimal(1),
    )
    assert report.verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS


# ---------------------------------------------------------------------------
# expectancy claim gating
# ---------------------------------------------------------------------------


def test_expectancy_claim_withheld_when_verdict_is_insufficient() -> None:
    report = build_calibration_report(
        evidence_rows=(),
        backtest_fills=(),
        budget=_budget(),
        observed_expectancy=Decimal("0.42"),
    )
    assert report.verdict is CalibrationVerdict.INSUFFICIENT_OBSERVATIONS
    assert report.expectancy_claim.value is None
    assert report.expectancy_claim.withheld_reason is not None
    assert "INSUFFICIENT_OBSERVATIONS" in report.expectancy_claim.withheld_reason


def test_expectancy_claim_carries_value_only_when_within() -> None:
    """Because price is always unobservable on this runtime today, WITHIN is unreachable in
    practice — this pins that the gate itself still distinguishes the branches correctly by
    driving ``calibration_within_budget`` (via a paired price-bearing fixture is not possible
    here; this is exercised directly against the kernel gate in
    ``tos/tests/backtest/test_backtest_calibration.py``). Here we only pin that a non-WITHIN
    report never carries a value."""
    report = build_calibration_report(
        evidence_rows=(_paper_row("a1", filled=Decimal(10)),),
        backtest_fills=(_backtest_fill("a1", filled=Decimal(10)),),
        budget=_budget(),
        observed_expectancy=Decimal("0.42"),
    )
    assert report.verdict is not CalibrationVerdict.WITHIN
    assert report.expectancy_claim.value is None


def test_budget_config_digest_is_stable_for_the_same_budget() -> None:
    report_a = build_calibration_report(
        evidence_rows=(),
        backtest_fills=(),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    report_b = build_calibration_report(
        evidence_rows=(),
        backtest_fills=(),
        budget=_budget(),
        observed_expectancy=Decimal(1),
    )
    assert report_a.budget_config_digest == report_b.budget_config_digest
    different = build_calibration_report(
        evidence_rows=(),
        backtest_fills=(),
        budget=_budget(min_observations=5),
        observed_expectancy=Decimal(1),
    )
    assert different.budget_config_digest != report_a.budget_config_digest


# ---------------------------------------------------------------------------
# the thin loader — reads typed records back out of a real evidence store
# ---------------------------------------------------------------------------


def test_loader_reads_egress_result_consumed_rows_back_typed(
    store: SqliteEvidenceStore,
) -> None:
    written = _paper_row("a1", filled=Decimal("3.5"))
    store.append(
        written.model_dump(mode="json"),
        kind=EvidenceKind.EGRESS_RESULT_CONSUMED.value,
        record_class="EGRESS_RESULT_CONSUMED",
    )
    read_back = read_egress_result_consumed_records(store)
    assert read_back == (written,)


def test_loader_ignores_rows_of_a_different_kind(store: SqliteEvidenceStore) -> None:
    store.append(
        EngineEvidenceRecord(kind=EvidenceKind.FLOW_HALTED).model_dump(mode="json"),
        kind=EvidenceKind.FLOW_HALTED.value,
        record_class="FLOW_HALTED",
    )
    assert read_egress_result_consumed_records(store) == ()


def test_loader_preserves_commit_order(store: SqliteEvidenceStore) -> None:
    first = _paper_row("a1", filled=Decimal(1))
    second = _paper_row("a2", filled=Decimal(2))
    for record in (first, second):
        store.append(
            record.model_dump(mode="json"),
            kind=EvidenceKind.EGRESS_RESULT_CONSUMED.value,
            record_class="EGRESS_RESULT_CONSUMED",
        )
    assert read_egress_result_consumed_records(store) == (first, second)


def test_loader_round_trips_a_record_with_masked_keys_non_empty(tmp_path: Path) -> None:
    """[E-R-3] pin the wrapper shape the loader unwraps: ``SqliteEvidenceStore.append`` writes
    ``{"payload": scrubbed_payload, "masked_keys": [...]}`` into ``payload_json`` — this test
    configures a non-empty ``secret_keys`` set so ``masked_keys`` is actually non-empty on the
    written row (not just structurally present-but-empty, as every other test in this file
    exercises), and confirms the loader still reads the (scrubbed) record back typed."""
    scrubbing_store = SqliteEvidenceStore(
        tmp_path / "evidence-scrubbed.sqlite3",
        key_provider=_FixedKeyProvider(),
        secret_keys=frozenset({"detail"}),
    )
    try:
        written = EngineEvidenceRecord(
            kind=EvidenceKind.EGRESS_RESULT_CONSUMED,
            attempt_id="a1",
            filled_quantity=Decimal(1),
            remaining_quantity=Decimal(0),
            detail="a secret value",
        )
        scrubbing_store.append(
            written.model_dump(mode="json"),
            kind=EvidenceKind.EGRESS_RESULT_CONSUMED.value,
            record_class="EGRESS_RESULT_CONSUMED",
        )
        (raw_payload_json,) = scrubbing_store.connection.execute(
            "SELECT payload_json FROM entries WHERE seq = 0"
        ).fetchone()
        wrapper = json.loads(raw_payload_json)
        assert wrapper["masked_keys"] == ["detail"]
        assert wrapper["payload"]["detail"] == "***REDACTED***"

        (read_back,) = read_egress_result_consumed_records(scrubbing_store)
        assert read_back.attempt_id == "a1"
        assert read_back.detail == "***REDACTED***"
    finally:
        scrubbing_store.close()


# ---------------------------------------------------------------------------
# config loader — fill / null-leaf / unknown-key
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, contents: dict[str, object]) -> Path:
    path = tmp_path / "backtest_calibration.yaml"
    path.write_text(yaml.safe_dump(contents), encoding="utf-8")
    return path


def test_config_loads_a_fully_valued_budget(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {
            "max_price_bps": 10,
            "max_fill_ratio_shortfall": 0.05,
            "max_latency_bars": 2,
            "min_observations": 3,
        },
    )
    budget = load_backtest_calibration_config(path)
    assert budget.max_price_bps == Decimal(10)
    assert budget.max_latency_bars == 2
    assert budget.min_observations == 3


def test_config_null_leaf_refuses_naming_the_key(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {
            "max_price_bps": None,
            "max_fill_ratio_shortfall": 0.05,
            "max_latency_bars": 2,
            "min_observations": 3,
        },
    )
    with pytest.raises(BacktestCalibrationConfigError, match="max_price_bps"):
        load_backtest_calibration_config(path)


def test_config_missing_key_refuses(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {
            "max_price_bps": 10,
            "max_fill_ratio_shortfall": 0.05,
            "max_latency_bars": 2,
        },
    )
    with pytest.raises(BacktestCalibrationConfigError, match="min_observations"):
        load_backtest_calibration_config(path)


def test_config_unknown_key_refuses(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        {
            "max_price_bps": 10,
            "max_fill_ratio_shortfall": 0.05,
            "max_latency_bars": 2,
            "min_observations": 3,
            "unexpected_key": 1,
        },
    )
    with pytest.raises(BacktestCalibrationConfigError):
        load_backtest_calibration_config(path)


def test_config_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(BacktestCalibrationConfigError):
        load_backtest_calibration_config(tmp_path / "does-not-exist.yaml")


_EXAMPLE_CONFIG_PATH = (
    Path(__file__).resolve().parents[3]
    / "runtime"
    / "config"
    / "backtest_calibration.example.yaml"
)


def _example_config_comment_block(key: str) -> str:
    """The blank-line-delimited comment block documenting ``key`` in the example config.

    The file is authored as one blank-line-separated block per key (header block first) — this
    walks those blocks rather than parsing YAML, since the value under test is the COMMENT text,
    which ``yaml.safe_load`` discards entirely.
    """
    text = _EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8")
    for block in text.split("\n\n"):
        if f"{key}:" in block:
            return block
    raise AssertionError(
        f"no comment block found for key {key!r} in {_EXAMPLE_CONFIG_PATH}"
    )


def test_example_config_file_is_all_named_tbd_null() -> None:
    raw = yaml.safe_load(_EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
    assert raw == {
        "max_price_bps": None,
        "max_fill_ratio_shortfall": None,
        "max_latency_bars": None,
        "min_observations": None,
    }
    with pytest.raises(BacktestCalibrationConfigError):
        load_backtest_calibration_config(_EXAMPLE_CONFIG_PATH)


def test_example_config_comment_for_max_fill_ratio_shortfall_describes_a_shortfall() -> (
    None
):
    """[E-R-4] Wave 3 review finding 3 (MEDIUM) — doc-drift pin. The comment above
    ``max_fill_ratio_shortfall`` used to describe the pre-E-R-3 quotient formula
    (``paper.filled_quantity / backtest.filled_quantity``, ~1.0 for a match), contradicting the
    shipped ``_fill_ratio`` (``abs(backtest - paper) / backtest``, 0 for a match) — an operator
    reading only the comment could enter e.g. ``0.9`` and pass a 90% underfill as WITHIN. This
    pins that the comment describes a shortfall (0 = exact match, larger = more deviation) and
    never the old quotient wording.
    """
    block = _example_config_comment_block("max_fill_ratio_shortfall").lower()
    assert "shortfall" in block
    assert "quotient" not in block
