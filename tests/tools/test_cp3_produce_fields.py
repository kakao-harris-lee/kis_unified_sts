"""Tests for the CP-3 B1a shared indicator producer (``tools/tos_cp3``).

Hermetic: synthetic minute bars written to a ``tmp_path`` Parquet tree, the
repo's own Setup D strategy YAML, no Redis / KIS / network. Five properties,
matching the B1a acceptance list:

(a) **Parity of math** — every published field agrees, bar by bar, with what
    the legacy ``SetupDVWAPReversion`` itself decided on the same series. The
    test restates the mapping (reject reason → which field is false)
    independently of the producer, and asserts the synthetic series actually
    reaches every branch, so a vacuous pass is visible.
(b) **Causality** — fields for ``bars[:n]`` are a prefix of fields for
    ``bars[:n+k]``.
(c) **No float** in any ``fields`` value (the kernel rejects floats at the
    border, silently dropping the field).
(d) **Determinism** — two runs over the same inputs write byte-identical JSONL
    and an identical lineage digest.
(e) **Red proof** — a deliberately look-ahead variant fails (b), so (b) is
    shown to have teeth rather than being true by construction.

File name: deliberately NOT ``test_tos_cp3_*``. ``tos-firewall.yml`` runs
``pytest tests/tools/test_tos_*.py`` in a job that installs a minimal
dependency set (``tos[test]`` + the repo root with ``--no-deps``) — no pyarrow,
no duckdb — and ``test.yml``'s path filter negates ``tests/tools/test_tos_*``
for the same reason. This suite needs the full runtime stack, so it belongs to
the legacy ``test`` job; a ``test_tos_`` prefix would have put it in the
governance battery, where it fails on import, and outside the one job that can
actually run it.
"""

from __future__ import annotations

import json
import warnings
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.context import load_futures_open_from_config
from shared.decision.setups.vwap_reversion import SetupDVWAPReversion
from shared.instruments.contract_spec import (
    ContractSpecRegistry,
    resolve_contract_spec,
)
from tools.tos_cp3 import produce_fields

SYMBOL = "101S6000"
SESSIONS = (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5))
BARS_PER_SESSION = 421  # 08:45..15:45 KST inclusive, 1-minute bars
SEED = 20261007

STRATEGY_YAML = (
    produce_fields.REPO_ROOT
    / "config"
    / "strategies"
    / "futures"
    / "setup_d_vwap_reversion.yaml"
)


# ---------------------------------------------------------------------------
# Synthetic series
# ---------------------------------------------------------------------------


def _synthetic_bars() -> pd.DataFrame:
    """Four KST futures sessions of 1-minute bars, seeded and deterministic.

    Shaped (quiet stretches punctuated by an impulse and a partial pullback,
    plus a volatility burst late in the last session) so the legacy setup
    actually reaches each of its branches — asserted in
    :func:`test_fields_match_legacy_setup_evaluation`. The late burst also
    makes the look-ahead red proof detectable: the full-series ATR peak lands
    in the final session, so truncating the series changes it.
    """
    rng = np.random.default_rng(SEED)
    rows: list[dict[str, object]] = []
    price = 400.0
    period = 53
    impulse = 0.9
    for session_idx, day in enumerate(SESSIONS):
        base = datetime.combine(day, time(8, 45))
        price += float(rng.normal(0.0, 0.5))
        for minute in range(BARS_PER_SESSION):
            phase = minute % period
            vol = 0.30 if phase < 12 else 0.03
            sign = 1.0 if (minute // period + session_idx) % 2 == 0 else -1.0
            step = float(rng.normal(0.0, vol))
            if phase == 4:
                step += impulse * sign
            if phase == 5:
                step += impulse * 0.8 * sign
            if phase in (7, 8, 9):
                step -= impulse * 0.45 * sign
            if session_idx == len(SESSIONS) - 1 and 200 <= minute <= 230:
                step *= 3.0
            open_ = price
            price = price + step
            high = max(open_, price) + abs(float(rng.normal(0.0, vol))) * 0.6
            low = min(open_, price) - abs(float(rng.normal(0.0, vol))) * 0.6
            rows.append(
                {
                    "code": SYMBOL,
                    "timestamp": base + timedelta(minutes=minute),
                    "open": round(open_, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(price, 2),
                    "volume": int(50 + abs(step) * 400),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    return _synthetic_bars()


@pytest.fixture(scope="module")
def strategy() -> produce_fields.StrategyInputs:
    return produce_fields.load_strategy_inputs(STRATEGY_YAML)


@pytest.fixture(scope="module")
def market_open() -> tuple[int, int]:
    """The futures open anchor, read from the SAME source the producer reads.

    Restating 08:45 here would let a config change pass this suite while
    silently shifting every ``entry_window`` the tool publishes.
    """
    return load_futures_open_from_config(
        str(produce_fields.REPO_ROOT / "config" / "market_schedule.yaml")
    )


def _contract_spec():
    registry = ContractSpecRegistry.from_yaml(
        str(produce_fields.REPO_ROOT / "config" / "execution.yaml")
    )
    return resolve_contract_spec(SYMBOL, registry)


def _produce(
    df: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    market_open: tuple[int, int],
) -> list[produce_fields.FieldRecord]:
    with warnings.catch_warnings():
        # MarketContextReplay warns on synthetic series whose 1-min returns are
        # large; the warning is about research trustworthiness, not correctness.
        warnings.simplefilter("ignore")
        return produce_fields.produce_records(
            df.reset_index(drop=True),
            symbol=SYMBOL,
            strategy=strategy,
            contract_spec=_contract_spec(),
            market_open_hour=market_open[0],
            market_open_minute=market_open[1],
        )


def _write_parquet_tree(df: pd.DataFrame, root: Path) -> Path:
    """Write *df* in the ``ParquetMarketDataStore`` partition layout."""
    for day, chunk in df.groupby(df["timestamp"].dt.date):
        part = (
            root
            / "futures"
            / "minute"
            / f"code={SYMBOL}"
            / f"year={day.year}"
            / f"month={day.month:02d}"
            / f"day={day.isoformat()}"
        )
        part.mkdir(parents=True, exist_ok=True)
        chunk.rename(columns={"timestamp": "datetime"}).reset_index(
            drop=True
        ).to_parquet(part / "part-0.parquet", index=False)
    return root


# ---------------------------------------------------------------------------
# (a) parity of math against the legacy object's own evaluation
# ---------------------------------------------------------------------------


def test_fields_match_legacy_setup_evaluation(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    market_open: tuple[int, int],
) -> None:
    records = _produce(bars, strategy, market_open)

    # A SECOND, independent legacy instance replayed over the same series.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        replay = MarketContextReplay(
            df=bars.reset_index(drop=True),
            symbol=SYMBOL,
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=_contract_spec(),
            market_open_hour=market_open[0],
            market_open_minute=market_open[1],
            min_volume=0,
        )
        contexts = list(replay.iter_contexts())
    setup = SetupDVWAPReversion(config=strategy.entry_config)
    cfg = strategy.entry_config

    # Bars with no publishable ATR are omitted, so align by bar instant rather
    # than by position (this series has none, which the loop asserts).
    by_bar = {record.bar_kst: record for record in records}
    assert len(by_bar) == len(records)

    outcomes: Counter[str] = Counter()
    for ctx in contexts:
        signal = setup.check(ctx)
        record = by_bar.get(ctx.now)
        if record is None:
            assert (
                produce_fields._inputs_unusable(ctx.current_price, ctx.vwap, ctx.atr_14)
                is not None
            )
            continue
        reason = setup.last_reject_reason
        outcome = "FIRED" if signal is not None else (reason or "").split("(")[0]
        outcomes[outcome] += 1
        fields = record.fields

        # Prices and indicators: the replay's values, scaled.
        assert fields["close"] == produce_fields.scaled_int(
            ctx.current_price, produce_fields.PRICE_SCALE
        )
        assert fields["vwap_x100"] == produce_fields.scaled_int(
            ctx.vwap, produce_fields.PRICE_SCALE
        )
        assert fields["atr14_x100"] == produce_fields.scaled_int(
            ctx.atr_14, produce_fields.PRICE_SCALE
        )
        if ctx.atr_14 > 0:
            expected_z = SetupDVWAPReversion.vwap_extension_z(
                ctx.current_price, ctx.vwap, ctx.atr_14
            )
            assert fields["z_x1000"] == produce_fields.scaled_int(
                expected_z, produce_fields.Z_SCALE
            )

        # Session window: independently restated from the YAML parameters.
        minutes = ctx.minutes_since_open()
        assert fields["entry_window"] is (
            cfg.valid_minutes_min <= minutes <= cfg.no_entry_after_minutes_since_open
        )
        # EOD: independently restated from the exit parameters.
        assert fields["eod"] is (
            strategy.eod_enabled and ctx.now.time() >= strategy.eod_time
        )
        # vwap_reverted: the declared band form (lineage D3).
        if ctx.atr_14 > 0:
            assert fields["vwap_reverted"] is (
                abs(expected_z) <= cfg.reversal_confirm_atr_mult
            )

        # Gate fields vs the legacy outcome on this very bar.
        if outcome == "FIRED":
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is True
            assert fields["reversal_ok"] is True
            assert fields["entry_window"] is True
            assert abs(fields["z_x1000"]) >= produce_fields.scaled_int(
                cfg.extreme_atr_mult, produce_fields.Z_SCALE
            )
        elif outcome in {"before_window", "after_cutoff"}:
            assert fields["entry_window"] is False
            # Never evaluated past step 1 — fail-closed.
            assert fields["hi_vol"] is False
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome == "vol_below_gate":
            assert fields["hi_vol"] is False
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome == "not_extreme":
            assert fields["hi_vol"] is True
            assert abs(fields["z_x1000"]) < produce_fields.scaled_int(
                cfg.extreme_atr_mult, produce_fields.Z_SCALE
            )
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome in {"still_trending_up", "still_trending_down"}:
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome == "awaiting_reversal_confirm":
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is True
            assert fields["reversal_ok"] is False
        elif outcome == "low_confidence":
            # Declared difference D1: no published field carries the
            # confidence gate, so every field reads as a pass here.
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is True
            assert fields["reversal_ok"] is True
        else:  # pragma: no cover - a new reject reason must be mapped
            pytest.fail(f"unmapped legacy outcome {outcome!r}")

    # Branch coverage: a clause this series never reaches is a clause this test
    # does not actually check, so require each one to occur at least once.
    for required in (
        "FIRED",
        "before_window",
        "after_cutoff",
        "vol_below_gate",
        "not_extreme",
        "awaiting_reversal_confirm",
        "low_confidence",
    ):
        assert outcomes[required] > 0, (required, dict(outcomes))
    assert outcomes["still_trending_up"] + outcomes["still_trending_down"] > 0, dict(
        outcomes
    )
    assert sum(outcomes.values()) == len(
        records
    ), "this series is meant to have no unusable-input bars"


# ---------------------------------------------------------------------------
# bars with no publishable ATR are omitted, not filled with a sentinel
# ---------------------------------------------------------------------------


def _bars_with_flat_run() -> pd.DataFrame:
    """Two sessions whose second session holds a perfectly flat 41-bar run.

    Every true range in that run is 0, so ``atr_partial`` reaches exactly 0 and
    ``z = (close - vwap) / atr`` is undefined — the concrete input the omission
    rule exists for.
    """
    rows: list[dict[str, object]] = []
    price = 400.0
    for session_idx, day in enumerate(SESSIONS[:2]):
        base = datetime.combine(day, time(8, 45))
        for minute in range(BARS_PER_SESSION):
            if session_idx == 1 and 100 <= minute <= 140:
                open_ = high = low = close = 400.0
            else:
                price += 0.05 if minute % 2 else -0.03
                open_ = close = price
                high, low = price + 0.05, price - 0.05
            rows.append(
                {
                    "code": SYMBOL,
                    "timestamp": base + timedelta(minutes=minute),
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": 10,
                }
            )
    return pd.DataFrame(rows)


def test_zero_atr_bars_are_omitted_not_filled(
    strategy: produce_fields.StrategyInputs, market_open: tuple[int, int]
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        produced = produce_fields.produce_bars(
            _bars_with_flat_run(),
            symbol=SYMBOL,
            strategy=strategy,
            contract_spec=_contract_spec(),
            market_open_hour=market_open[0],
            market_open_minute=market_open[1],
        )

    assert produced.omitted, "the flat run must produce unusable-ATR bars"
    assert {reason for _, reason in produced.omitted} == {
        "atr_14 <= 0 (z is undefined)"
    }
    assert len(produced.records) + len(produced.omitted) == produced.bars_replayed

    omitted_ids = {raw_event_id for raw_event_id, _ in produced.omitted}
    assert not (omitted_ids & {record.raw_event_id for record in produced.records})
    # The invariant a sentinel would have broken: a published bar never carries
    # an undefined extension, so z_x1000 == 0 always means "at VWAP", never
    # "ATR missing" — and the exact LONG revert comparison (z_x1000 >= 0) can
    # be trusted.
    for record in produced.records:
        assert record.fields["atr14_x100"] > 0


# ---------------------------------------------------------------------------
# (b) causality / prefix property
# ---------------------------------------------------------------------------

PREFIX_N = BARS_PER_SESSION * 2 + 100
PREFIX_K = BARS_PER_SESSION


def test_prefix_of_longer_run_equals_shorter_run(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    market_open: tuple[int, int],
) -> None:
    short = _produce(bars.iloc[:PREFIX_N], strategy, market_open)
    long = _produce(bars.iloc[: PREFIX_N + PREFIX_K], strategy, market_open)

    assert 0 < len(short) < len(long)
    short_lines = [record.to_json_line() for record in short]
    long_lines = [record.to_json_line() for record in long]
    assert long_lines[: len(short_lines)] == short_lines


# ---------------------------------------------------------------------------
# (c) no float anywhere in fields
# ---------------------------------------------------------------------------


def test_no_float_in_any_field(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    market_open: tuple[int, int],
) -> None:
    records = _produce(bars, strategy, market_open)
    assert records
    for record in records:
        assert set(record.fields) == set(produce_fields.FIELD_ORDER)
        for key, value in record.fields.items():
            assert not isinstance(value, float), (key, value)
            assert isinstance(value, (bool, int)), (key, type(value))
        # The serialized form must not carry a float literal either.
        reloaded = json.loads(record.to_json_line())["fields"]
        for key, value in reloaded.items():
            assert not isinstance(value, float), (key, value)


def test_float_field_is_refused() -> None:
    """The no-float guard names a concrete failing input, not a hope."""
    with pytest.raises(produce_fields.ProduceFieldsError, match="not int/bool"):
        produce_fields._assert_no_floats({"close": 559.45}, "probe")  # type: ignore[dict-item]


# ---------------------------------------------------------------------------
# (d) determinism of JSONL bytes and lineage digest
# ---------------------------------------------------------------------------


def test_jsonl_and_lineage_are_byte_deterministic(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    data_root = _write_parquet_tree(bars, tmp_path / "market")

    def one(out_name: str) -> produce_fields.RunResult:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return produce_fields.run(
                data_root=data_root,
                symbol=SYMBOL,
                start=SESSIONS[0],
                end=SESSIONS[-1],
                strategy_yaml=STRATEGY_YAML,
                out_dir=tmp_path / out_name,
            )

    first = one("out-1")
    second = one("out-2")

    assert first.jsonl_bytes == second.jsonl_bytes
    assert first.lineage_bytes == second.lineage_bytes
    assert first.jsonl_path.read_bytes() == first.jsonl_bytes
    assert (
        first.lineage["output"]["jsonl_sha256"]
        == second.lineage["output"]["jsonl_sha256"]
    )

    lineage = first.lineage
    # Lineage must carry the provenance B1a owes the comparison report.
    assert lineage["dataset"]["input_file_count"] == len(SESSIONS)
    assert all(len(item["sha256"]) == 64 for item in lineage["dataset"]["input_files"])
    assert lineage["dataset"]["bars_emitted"] == len(first.records)
    assert lineage["dataset"]["bars_loaded"] == len(bars)
    omitted = lineage["dataset"]["omitted_bars"]
    assert omitted["count"] == 0
    assert omitted["raw_event_ids"] == []
    assert omitted["raw_event_ids_truncated"] is False
    assert (
        lineage["dataset"]["bars_replayed"]
        == lineage["dataset"]["bars_emitted"] + omitted["count"]
    )
    assert (
        lineage["strategy"]["sha256"]
        == produce_fields.load_strategy_inputs(STRATEGY_YAML).sha256
    )
    assert set(lineage["fields"]) == set(produce_fields.FIELD_ORDER)
    for spec in lineage["fields"].values():
        assert {"unit", "scale", "formula_id", "window_bars"} <= set(spec)
    assert {entry["id"] for entry in lineage["declared_differences"]} == {
        "D1",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
    }
    # No run timestamp anywhere: a changed lineage must mean changed inputs.
    assert "timestamp" not in json.dumps(lineage["tool"])


# ---------------------------------------------------------------------------
# (e) red proof: a look-ahead variant must fail (b)
# ---------------------------------------------------------------------------

_ORIGINAL_ITER_CONTEXTS = MarketContextReplay.iter_contexts


def test_lookahead_variant_breaks_the_prefix_property(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    market_open: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replace ATR with the FULL-SERIES peak — the classic look-ahead.

    ``MarketContextReplay``'s own ``atr_90th_percentile`` is look-ahead for
    exactly this reason (its docstring says so), which is why Setup D refuses
    to read it. Injecting the same shape of dependency must make the prefix
    assertion in :func:`test_prefix_of_longer_run_equals_shorter_run` fail; if
    it still passed, that test would be proving nothing.
    """

    def lookahead_iter_contexts(self: MarketContextReplay):
        contexts = list(_ORIGINAL_ITER_CONTEXTS(self))
        peak = max(ctx.atr_14 for ctx in contexts)  # depends on FUTURE bars
        for ctx in contexts:
            yield replace(ctx, atr_14=peak)

    monkeypatch.setattr(MarketContextReplay, "iter_contexts", lookahead_iter_contexts)

    short = _produce(bars.iloc[:PREFIX_N], strategy, market_open)
    long = _produce(bars.iloc[: PREFIX_N + PREFIX_K], strategy, market_open)

    short_lines = [record.to_json_line() for record in short]
    long_lines = [record.to_json_line() for record in long]
    assert 0 < len(short_lines) < len(long_lines)
    assert long_lines[: len(short_lines)] != short_lines
