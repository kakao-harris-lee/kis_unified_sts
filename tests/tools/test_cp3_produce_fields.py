"""Tests for the CP-3 B1a shared indicator producer (``tools/tos_cp3``).

Hermetic: synthetic minute bars written to a ``tmp_path`` Parquet tree, the
repo's own Setup D strategy YAML, no Redis / KIS / network.

What is pinned here:

* **Wire shape** — the five top-level keys the only JSONL observation reader in
  the repo requires, and that ``fields`` carries the bar itself so a
  ``tos.backtest.Bar`` can be built from this file alone.
* **Parity of math** — every published field agrees, bar by bar, with what the
  legacy ``SetupDVWAPReversion`` itself decided on the same series. The test
  restates the mapping (reject reason → which field is false) independently of
  the producer, and asserts the synthetic series actually reaches every branch,
  so a vacuous pass is visible.
* **Causality** — fields for ``bars[:n]`` are a prefix of fields for
  ``bars[:n+k]``, with a **red proof** that a look-ahead variant breaks it.
* **Quantization** — symmetric, conservative truncation for ``z_x1000``.
* **Determinism** — two runs write byte-identical JSONL and lineage.
* **Refusals** — NaN input, ``trend_filter_enabled``, a straddling open-anchor
  window, and a float field each abort rather than ship something quietly wrong.

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
import math
import warnings
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setups.vwap_reversion import SetupDVWAPReversion
from shared.instruments.contract_spec import (
    ContractSpecRegistry,
    resolve_contract_spec,
)
from shared.strategy.exit.setup_target_exit import SetupTargetExit
from shared.strategy.market_time import is_trading_day_kst
from tools.tos_cp3 import produce_fields

SYMBOL = "101S6000"
#: Four consecutive 2026-03 weekdays. 2026-03-02 is a Korean substitute holiday
#: (삼일절), which is used deliberately in the eod test below; the replay drops
#: that first session anyway for lack of a prior-session close.
SESSIONS = (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5))
BARS_PER_SESSION = 421  # 08:45..15:45 KST inclusive, 1-minute bars
#: Seed chosen so the legacy setup reaches every one of its branches on this
#: series, ``low_confidence`` on more than one bar — see the coverage assertions
#: in :func:`test_fields_match_legacy_setup_evaluation`.
SEED = 20261008
#: The volatility burst sits in the THIRD session so it falls inside the longer
#: prefix of the causality pair and outside the shorter one. That is what makes
#: the look-ahead red proof red for the mechanism its docstring names: the
#: full-series ATR peak differs between the two prefixes.
BURST_SESSION_INDEX = 2

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
    plus a volatility burst in the third session) so the legacy setup reaches
    each of its branches.
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
            if session_idx == BURST_SESSION_INDEX and 200 <= minute <= 230:
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
def anchor() -> produce_fields.OpenAnchor:
    """The open anchor the producer resolves for this window — the era rule.

    Restating 09:00 here would let the era rule rot while this suite stayed
    green; resolving it the way ``run()`` does keeps the two in step.
    """
    return produce_fields.resolve_open_anchor(
        cli_value="auto", first_session=SESSIONS[0], last_session=SESSIONS[-1]
    )


def _contract_spec():
    registry = ContractSpecRegistry.from_yaml(
        str(produce_fields.REPO_ROOT / "config" / "execution.yaml")
    )
    return resolve_contract_spec(SYMBOL, registry)


def _produce(
    df: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
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
            anchor=anchor,
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
# Wire shape: the journal's required keys, and the bar B1b needs
# ---------------------------------------------------------------------------

#: MIRRORS ``tos/runtime/src/tos_runtime/marketfeed/journal.py::_REQUIRED_KEYS``.
#: The import firewall forbids importing it (``tools/`` and ``tests/`` are both
#: outside ``tos/``), so the five names are restated here as a literal. That
#: reader refuses the WHOLE poll on a missing key, so a silently dropped key is
#: not a degraded line — it is no data at all.
JOURNAL_REQUIRED_KEYS_MIRROR = frozenset(
    {"raw_event_id", "instrument", "as_of_ms", "fields", "source_id"}
)

#: MIRRORS the required fields of ``tos/src/tos/backtest/bars.py::Bar`` that must
#: come from this JSONL for B1b to build one without a second path to Parquet.
#: ``bar_index`` and ``timestamp_coordinate`` are the runner's to assign.
BAR_REQUIRED_FROM_JSONL = ("open", "high", "low", "close", "volume", "session_token")


def test_line_shape_matches_journal_required_keys(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    records = _produce(bars, strategy, anchor)
    for record in (records[0], records[len(records) // 2], records[-1]):
        payload = json.loads(record.to_json_line())
        assert set(payload) == JOURNAL_REQUIRED_KEYS_MIRROR
        assert payload["source_id"] == produce_fields.SOURCE_ID
        assert payload["source_id"].startswith("tos-cp3-b1a/")
        assert payload["instrument"] == SYMBOL
        assert isinstance(payload["as_of_ms"], int)
        assert isinstance(payload["fields"], dict)
    # The producer's own mirrored tuple must agree with this test's literal, so
    # the two cannot drift apart silently.
    assert set(produce_fields.JOURNAL_REQUIRED_KEYS) == JOURNAL_REQUIRED_KEYS_MIRROR


def test_fields_carry_the_bar_so_b1b_needs_no_second_parquet_path(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    """Every ``Bar`` input is present, and the invariants ``Bar`` enforces hold."""
    records = _produce(bars, strategy, anchor)
    by_stamp = {
        pd.Timestamp(row.timestamp): row for row in bars.itertuples(index=False)
    }

    for name in BAR_REQUIRED_FROM_JSONL:
        suffixed = name if name in {"volume", "session_token"} else f"{name}_x100"
        assert suffixed in produce_fields.FIELD_ORDER, name

    for record in records:
        fields = record.fields
        low = fields["low_x100"]
        high = fields["high_x100"]
        # Mirrors Bar's own model validator (bars.py::_bar_is_well_formed):
        # positive prices, a non-inverted range, open/close inside it, a
        # non-negative volume and a non-blank session token.
        assert isinstance(low, int) and isinstance(high, int)
        assert low > 0 and high > 0
        assert high >= low
        for edge in ("open_x100", "close_x100"):
            assert low <= fields[edge] <= high, (edge, record.raw_event_id)
        assert isinstance(fields["volume"], int) and fields["volume"] >= 0
        assert isinstance(fields["session_token"], str)
        assert fields["session_token"].strip()
        assert fields["session_token"] == record.bar_kst.date().isoformat()

        row = by_stamp[pd.Timestamp(record.bar_kst).tz_localize(None)]
        assert fields["open_x100"] == produce_fields.scaled_int_half_up(
            row.open, produce_fields.PRICE_SCALE
        )
        assert fields["high_x100"] == produce_fields.scaled_int_half_up(
            row.high, produce_fields.PRICE_SCALE
        )
        assert fields["low_x100"] == produce_fields.scaled_int_half_up(
            row.low, produce_fields.PRICE_SCALE
        )
        assert fields["volume"] == int(row.volume)


# ---------------------------------------------------------------------------
# Parity of math against the legacy object's own evaluation
# ---------------------------------------------------------------------------


def test_fields_match_legacy_setup_evaluation(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    records = _produce(bars, strategy, anchor)

    # A SECOND, independent legacy instance replayed over the same series.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        replay = MarketContextReplay(
            df=bars.reset_index(drop=True),
            symbol=SYMBOL,
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=_contract_spec(),
            market_open_hour=anchor.hour,
            market_open_minute=anchor.minute,
            min_volume=0,
        )
        contexts = list(replay.iter_contexts())
    setup = SetupDVWAPReversion(config=strategy.entry_config)
    cfg = strategy.entry_config
    extreme_x1000 = produce_fields.scaled_int_toward_zero(
        cfg.extreme_atr_mult, produce_fields.Z_SCALE
    )

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
        assert fields["close_x100"] == produce_fields.scaled_int_half_up(
            ctx.current_price, produce_fields.PRICE_SCALE
        )
        assert fields["vwap_x100"] == produce_fields.scaled_int_half_up(
            ctx.vwap, produce_fields.PRICE_SCALE
        )
        assert fields["atr14_x100"] == produce_fields.scaled_int_half_up(
            ctx.atr_14, produce_fields.PRICE_SCALE
        )
        expected_z = SetupDVWAPReversion.vwap_extension_z(
            ctx.current_price, ctx.vwap, ctx.atr_14
        )
        assert fields["z_x1000"] == produce_fields.scaled_int_toward_zero(
            expected_z, produce_fields.Z_SCALE
        )

        # Session window: independently restated from the YAML parameters.
        minutes = ctx.minutes_since_open()
        assert fields["entry_window"] is (
            cfg.valid_minutes_min <= minutes <= cfg.no_entry_after_minutes_since_open
        )
        # vwap_reverted: the declared band form (lineage D3).
        assert fields["vwap_reverted"] is (abs(expected_z) <= strategy.vwap_revert_band)

        # Gate fields vs the legacy outcome on this very bar.
        if outcome == "FIRED":
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is True
            assert fields["reversal_ok"] is True
            assert fields["entry_window"] is True
            assert abs(fields["z_x1000"]) >= extreme_x1000
        elif outcome in {"before_window", "after_cutoff"}:
            assert fields["entry_window"] is False
            # Never evaluated past step 1 — fail-closed.
            assert fields["hi_vol"] is False
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome == "vol_below_gate":
            # D5: an IN-WINDOW reject keeps entry_window true; the AND is false
            # through the gate that actually rejected.
            assert fields["entry_window"] is True
            assert fields["hi_vol"] is False
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome == "not_extreme":
            assert fields["entry_window"] is True
            assert fields["hi_vol"] is True
            # Truncation toward zero makes this exact rather than a near-tie:
            # abs(z_x1000) < trunc(extreme*1000) iff abs(z) < extreme.
            assert abs(fields["z_x1000"]) < extreme_x1000
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome in {"still_trending_up", "still_trending_down"}:
            assert fields["entry_window"] is True
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is False
            assert fields["reversal_ok"] is False
        elif outcome == "awaiting_reversal_confirm":
            assert fields["entry_window"] is True
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is True
            assert fields["reversal_ok"] is False
        elif outcome == "low_confidence":
            # Declared difference D1: no published field carries the confidence
            # gate, so every field reads as a pass here.
            assert fields["entry_window"] is True
            assert fields["hi_vol"] is True
            assert fields["stall_ok"] is True
            assert fields["reversal_ok"] is True
        else:  # pragma: no cover - a new reject reason must be mapped
            pytest.fail(f"unmapped legacy outcome {outcome!r}")

    # Branch coverage: a clause this series never reaches is a clause this test
    # does not actually check, so require each one to occur — and more than once
    # for low_confidence, whose single-bar coverage was a one-sample accident.
    for required in (
        "FIRED",
        "before_window",
        "after_cutoff",
        "vol_below_gate",
        "not_extreme",
        "awaiting_reversal_confirm",
    ):
        assert outcomes[required] > 0, (required, dict(outcomes))
    assert outcomes["low_confidence"] >= 2, dict(outcomes)
    assert outcomes["still_trending_up"] + outcomes["still_trending_down"] > 0, dict(
        outcomes
    )
    assert sum(outcomes.values()) == len(
        records
    ), "this series is meant to have no unusable-input bars"


# ---------------------------------------------------------------------------
# EOD against the legacy exit's own decision
# ---------------------------------------------------------------------------


def test_eod_matches_the_legacy_exit_decision(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    """Compare ``eod`` to ``SetupTargetExit`` itself, not to the producer's rule."""
    records = _produce(bars, strategy, anchor)
    exit_gen = SetupTargetExit(strategy.exit_config)

    emitted_sessions = sorted({record.bar_kst.date() for record in records})
    # The premise of the comparison below, asserted rather than assumed: the
    # legacy helper returns False all day on a non-trading day, so an equality
    # check would be meaningless on one.
    for session in emitted_sessions:
        probe = datetime.combine(session, time(12, 0)).replace(
            tzinfo=records[0].bar_kst.tzinfo
        )
        assert is_trading_day_kst(probe), session

    for record in records:
        assert record.fields["eod"] is exit_gen._should_eod_close(record.bar_kst)

    # Declared difference D4, with its concrete input: 2026-03-02 is a Korean
    # substitute holiday, so the legacy helper refuses all day there while this
    # producer's bar-time rule would say True after the cutoff. The real futures
    # dataset carries no bars on a non-trading day, which is why D4 states the
    # clause cannot move the cutoff in practice — but the difference is real and
    # is pinned here rather than asserted in prose only.
    holiday_bar = datetime.combine(SESSIONS[0], time(15, 20)).replace(
        tzinfo=records[0].bar_kst.tzinfo
    )
    assert not is_trading_day_kst(holiday_bar)
    assert exit_gen._should_eod_close(holiday_bar) is False
    assert holiday_bar.time() >= strategy.exit_config.eod_close_time
    assert SESSIONS[0] not in emitted_sessions


# ---------------------------------------------------------------------------
# Causality / prefix property
# ---------------------------------------------------------------------------

PREFIX_N = BARS_PER_SESSION * 2 + 100
PREFIX_K = BARS_PER_SESSION


def test_prefix_of_longer_run_equals_shorter_run(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    short = _produce(bars.iloc[:PREFIX_N], strategy, anchor)
    long = _produce(bars.iloc[: PREFIX_N + PREFIX_K], strategy, anchor)

    assert 0 < len(short) < len(long)
    short_lines = [record.to_json_line() for record in short]
    long_lines = [record.to_json_line() for record in long]
    assert long_lines[: len(short_lines)] == short_lines


_ORIGINAL_ITER_CONTEXTS = MarketContextReplay.iter_contexts


def test_lookahead_variant_breaks_the_prefix_property(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replace ATR with the FULL-SERIES peak — the classic look-ahead.

    ``MarketContextReplay``'s own ``atr_90th_percentile`` is look-ahead for
    exactly this reason (its docstring says so), which is why Setup D refuses to
    read it. Injecting the same shape of dependency must break the prefix
    assertion; if it did not, that test would be proving nothing.

    The series' volatility burst sits in the THIRD session
    (:data:`BURST_SESSION_INDEX`), i.e. inside the longer prefix and outside the
    shorter one, so the injected peak genuinely differs between the two runs —
    the mechanism this docstring names, not incidental noise.
    """

    def lookahead_iter_contexts(self: MarketContextReplay):
        contexts = list(_ORIGINAL_ITER_CONTEXTS(self))
        peak = max(ctx.atr_14 for ctx in contexts)  # depends on FUTURE bars
        for ctx in contexts:
            yield replace(ctx, atr_14=peak)

    # The burst must actually move the peak between the two prefixes, otherwise
    # this test would be red for the wrong reason.
    def peak_for(rows: int) -> float:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replay = MarketContextReplay(
                df=bars.iloc[:rows].reset_index(drop=True),
                symbol=SYMBOL,
                macro_snapshot=None,
                scheduled_events=[],
                contract_spec=_contract_spec(),
                market_open_hour=anchor.hour,
                market_open_minute=anchor.minute,
                min_volume=0,
            )
            return max(ctx.atr_14 for ctx in _ORIGINAL_ITER_CONTEXTS(replay))

    assert peak_for(PREFIX_N + PREFIX_K) > peak_for(PREFIX_N)

    monkeypatch.setattr(MarketContextReplay, "iter_contexts", lookahead_iter_contexts)

    short = _produce(bars.iloc[:PREFIX_N], strategy, anchor)
    long = _produce(bars.iloc[: PREFIX_N + PREFIX_K], strategy, anchor)

    short_lines = [record.to_json_line() for record in short]
    long_lines = [record.to_json_line() for record in long]
    assert 0 < len(short_lines) < len(long_lines)
    assert long_lines[: len(short_lines)] != short_lines


# ---------------------------------------------------------------------------
# Scalars only, and the quantization rules
# ---------------------------------------------------------------------------


def test_no_float_in_any_field(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    records = _produce(bars, strategy, anchor)
    assert records
    for record in records:
        assert set(record.fields) == set(produce_fields.FIELD_ORDER)
        for key, value in record.fields.items():
            assert not isinstance(value, float), (key, value)
            assert isinstance(value, (bool, int, str)), (key, type(value))
        reloaded = json.loads(record.to_json_line())["fields"]
        for key, value in reloaded.items():
            assert not isinstance(value, float), (key, value)


def test_float_field_is_refused() -> None:
    """The no-float guard names a concrete failing input, not a hope."""
    with pytest.raises(produce_fields.ProduceFieldsError, match="not int/bool/str"):
        produce_fields._assert_scalar_fields(
            {"close_x100": 559.45},  # type: ignore[dict-item]
            "probe",
        )


def test_z_quantization_is_symmetric_and_conservative() -> None:
    """``z_x1000`` truncates toward zero; prices round half-up (D8)."""
    scale = produce_fields.Z_SCALE
    # Symmetric at the near-tie that half-up resolved asymmetrically: half-up
    # gave 1800 / -1799, which both widened the trigger and broke the mirror.
    assert produce_fields.scaled_int_toward_zero(1.7995, scale) == 1799
    assert produce_fields.scaled_int_toward_zero(-1.7995, scale) == -1799
    assert produce_fields.scaled_int_half_up(1.7995, scale) == 1800  # the old rule

    # Conservative at the trigger: the integer comparison never admits a bar the
    # real comparison would reject.
    threshold = produce_fields.scaled_int_toward_zero(1.8, scale)
    assert threshold == 1800
    for z in (1.7, 1.7995, 1.79999, -1.7995, 1.8, -1.8, 2.5, -2.5):
        integer_fires = (
            abs(produce_fields.scaled_int_toward_zero(z, scale)) >= threshold
        )
        real_fires = abs(z) >= 1.8
        assert not (integer_fires and not real_fires), z

    # Prices keep half-up, and it stays monotone so Bar's OHLC relations hold.
    assert (
        produce_fields.scaled_int_half_up(559.45, produce_fields.PRICE_SCALE) == 55945
    )
    assert (
        produce_fields.scaled_int_half_up(559.455, produce_fields.PRICE_SCALE) == 55946
    )
    low, high = 100.0049, 100.0051
    assert produce_fields.scaled_int_half_up(
        high, produce_fields.PRICE_SCALE
    ) >= produce_fields.scaled_int_half_up(low, produce_fields.PRICE_SCALE)


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_non_finite_input_aborts_rather_than_being_omitted() -> None:
    """NaN is a corrupt dataset, not a quiet bar — it must not become a count."""
    with pytest.raises(produce_fields.ProduceFieldsError, match="non-finite"):
        produce_fields._inputs_unusable(math.nan, 400.0, 0.5)
    with pytest.raises(produce_fields.ProduceFieldsError, match="non-finite"):
        produce_fields._inputs_unusable(400.0, 400.0, math.inf)
    # The ordinary unusable cases still return a reason (an omission, not a raise).
    assert produce_fields._inputs_unusable(400.0, 400.0, 0.0) is not None
    assert produce_fields._inputs_unusable(400.0, 400.0, 0.5) is None


def test_trend_filter_enabled_is_refused(tmp_path: Path) -> None:
    """No trend field is published, so a run with the gate on must not proceed."""
    source = yaml_text = STRATEGY_YAML.read_text(encoding="utf-8")
    assert "trend_filter_enabled: false" in source
    patched = tmp_path / "setup_d_trend_on.yaml"
    patched.write_text(
        yaml_text.replace("trend_filter_enabled: false", "trend_filter_enabled: true"),
        encoding="utf-8",
    )
    with pytest.raises(
        produce_fields.ProduceFieldsError, match="trend_filter_enabled is true"
    ):
        produce_fields.load_strategy_inputs(patched)


def test_band_premise_is_asserted(tmp_path: Path) -> None:
    """The vwap_reverted note's premise is a guard, not a comment."""
    text = STRATEGY_YAML.read_text(encoding="utf-8")
    patched = tmp_path / "setup_d_flat_trigger.yaml"
    patched.write_text(
        text.replace("extreme_atr_mult: 1.8", "extreme_atr_mult: 1.2"), encoding="utf-8"
    )
    with pytest.raises(produce_fields.ProduceFieldsError, match="is not greater than"):
        produce_fields.load_strategy_inputs(patched)


def test_open_anchor_era_rule() -> None:
    """Pre-cutover data gets 09:00; a straddling window is refused."""
    pre = produce_fields.resolve_open_anchor(
        cli_value="auto",
        first_session=date(2025, 12, 1),
        last_session=date(2026, 4, 30),
    )
    assert (pre.hour, pre.minute, pre.source) == (9, 0, "era-rule")

    post = produce_fields.resolve_open_anchor(
        cli_value="auto", first_session=date(2026, 7, 1), last_session=date(2026, 8, 1)
    )
    assert post.source == "config"

    override = produce_fields.resolve_open_anchor(
        cli_value="08:45",
        first_session=date(2025, 12, 1),
        last_session=date(2026, 4, 30),
    )
    assert (override.hour, override.minute, override.source) == (8, 45, "cli")

    with pytest.raises(produce_fields.ProduceFieldsError, match="straddles"):
        produce_fields.resolve_open_anchor(
            cli_value="auto",
            first_session=date(2026, 6, 1),
            last_session=date(2026, 7, 1),
        )
    with pytest.raises(produce_fields.ProduceFieldsError, match="HH:MM"):
        produce_fields.resolve_open_anchor(
            cli_value="nine",
            first_session=date(2026, 7, 1),
            last_session=date(2026, 8, 1),
        )


# ---------------------------------------------------------------------------
# Bars with no publishable ATR are omitted, not filled with a sentinel
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
    strategy: produce_fields.StrategyInputs, anchor: produce_fields.OpenAnchor
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        produced = produce_fields.produce_bars(
            _bars_with_flat_run(),
            symbol=SYMBOL,
            strategy=strategy,
            contract_spec=_contract_spec(),
            anchor=anchor,
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
    # "ATR missing".
    for record in produced.records:
        assert record.fields["atr14_x100"] > 0


# ---------------------------------------------------------------------------
# Determinism, lineage and the density gate
# ---------------------------------------------------------------------------


def _run(root: Path, out: Path, **kwargs) -> produce_fields.RunResult:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return produce_fields.run(
            data_root=root,
            symbol=SYMBOL,
            start=SESSIONS[0],
            end=SESSIONS[-1],
            strategy_yaml=STRATEGY_YAML,
            out_dir=out,
            **kwargs,
        )


def test_jsonl_and_lineage_are_byte_deterministic(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    data_root = _write_parquet_tree(bars, tmp_path / "market")

    first = _run(data_root, tmp_path / "out-1", min_bars_per_day=0)
    second = _run(data_root, tmp_path / "out-2", min_bars_per_day=0)

    assert first.jsonl_bytes == second.jsonl_bytes
    assert first.lineage_bytes == second.lineage_bytes
    assert first.jsonl_path.read_bytes() == first.jsonl_bytes
    assert (
        first.lineage["output"]["jsonl_sha256"]
        == second.lineage["output"]["jsonl_sha256"]
    )

    lineage = first.lineage
    dataset = lineage["dataset"]
    assert dataset["input_file_count"] == len(SESSIONS)
    assert all(len(item["sha256"]) == 64 for item in dataset["input_files"])
    assert dataset["bars_emitted"] == len(first.records)
    assert dataset["bars_loaded"] == len(bars)
    assert dataset["min_bars_per_day"] == 0
    assert dataset["min_volume"] == 0
    omitted = dataset["omitted_bars"]
    assert omitted["count"] == 0
    assert omitted["raw_event_ids"] == []
    assert omitted["raw_event_ids_truncated"] is False
    # Bar accounting reconciles explicitly (the producer raises if it does not).
    assert (
        dataset["bars_after_density_gate"]
        - dataset["replay_warmup_bars_skipped"]
        - dataset["first_session_bars_dropped_no_prior_close"]
        == dataset["bars_replayed"]
    )
    assert dataset["bars_replayed"] == dataset["bars_emitted"] + omitted["count"]

    assert (
        lineage["strategy"]["sha256"]
        == produce_fields.load_strategy_inputs(STRATEGY_YAML).sha256
    )
    assert lineage["strategy"]["market_open_kst"] == "09:00"
    assert lineage["strategy"]["market_open_source"] == "era-rule"
    assert lineage["strategy"]["vwap_revert_band_source"].startswith(
        "strategy.entry.params.reversal_confirm_atr_mult"
    )

    # ADR-002-018 §10 lineage: versions, parents, type/sign/range, common mode.
    runtime = lineage["tool"]["runtime"]
    assert runtime["python"] and runtime["numpy"] != "unavailable"
    assert runtime["pandas"] != "unavailable"
    assert "shared/decision/setups/vwap_reversion.py" in lineage["common_mode"]
    assert "NOT independent" in lineage["common_mode"]
    assert lineage["tool"]["source_id"] == produce_fields.SOURCE_ID
    assert lineage["encoding"]["journal_required_keys"] == list(
        produce_fields.JOURNAL_REQUIRED_KEYS
    )

    assert set(lineage["fields"]) == set(produce_fields.FIELD_ORDER)
    for name, spec in lineage["fields"].items():
        assert {
            "unit",
            "scale",
            "multiplier",
            "sign",
            "type",
            "quantization",
            "formula_id",
            "window_bars",
            "parents",
            "range_observed",
        } <= set(spec), name
        # scale is a TOKEN and multiplier the number, as
        # config/tos_runtime/paper/critical_input_policy.yaml writes them.
        assert isinstance(spec["scale"], str), name
        assert isinstance(spec["multiplier"], str), name
        assert spec["sign"] in {"signed", "unsigned"}, name
        assert spec["type"] in {"int", "bool", "str"}, name
        assert spec["parents"], name
    assert lineage["fields"]["z_x1000"]["sign"] == "signed"
    assert lineage["fields"]["z_x1000"]["quantization"] == "truncate_toward_zero"
    assert lineage["fields"]["close_x100"]["quantization"] == "half_up"
    assert "min" in lineage["fields"]["close_x100"]["range_observed"]
    assert set(lineage["fields"]["hi_vol"]["range_observed"]) == {"true", "false"}
    assert lineage["fields"]["session_token"]["range_observed"]["distinct"] >= 1

    assert {entry["id"] for entry in lineage["declared_differences"]} == {
        f"D{index}" for index in range(1, 11)
    }
    # No run timestamp anywhere: a changed lineage must mean changed inputs.
    assert "timestamp" not in json.dumps(lineage["tool"])


def test_min_bars_per_day_gate_changes_the_output(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    """The density gate is a real knob, defaulted to the walk-forward's 330."""
    assert produce_fields.DEFAULT_MIN_BARS_PER_DAY == 330
    data_root = _write_parquet_tree(bars, tmp_path / "market")

    off = _run(data_root, tmp_path / "off", min_bars_per_day=0)
    # Every synthetic session has 421 bars, so a gate above that drops them all.
    gated = _run(data_root, tmp_path / "gated", min_bars_per_day=400)
    assert gated.lineage["dataset"]["bars_after_density_gate"] == len(bars)
    assert off.jsonl_bytes == gated.jsonl_bytes  # nothing dropped at 400 either

    with pytest.raises(produce_fields.ProduceFieldsError, match="density gate dropped"):
        _run(data_root, tmp_path / "all-dropped", min_bars_per_day=500)

    default_run = _run(data_root, tmp_path / "default")
    assert default_run.lineage["dataset"]["min_bars_per_day"] == 330
