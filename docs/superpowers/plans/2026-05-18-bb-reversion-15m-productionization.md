# bb_reversion_15m Productionization (paper) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire 15-minute Bollinger-Band/RSI indicators through the live + backtest indicator path so `bb_reversion_15m` runs correctly (on closed 15m bars, not 1-min) in paper trading, then validate it in paper against an explicit significance gate — without changing `mean_reversion.generate()` and keeping backtest == live == the probe that passed the robust gate.

**Architecture:** Option B (smallest correct). Add a timeframe-tagged *base-indicator* request that mirrors the existing `momentum_<tf>` mechanism: a strategy declares a grouping key `mtf_base_15m`; the resolver computes 15m BB/RSI from the engine's existing `MultiTimeframeCandleAccumulator` **closed** candles (already proven bar-for-bar identical to the probe's resample — de-risk checkpoint, `scripts/derisk_live_vs_probe_15m.py`, 5615/5615) and injects them under the plain `bb_lower/bb_upper/bb_middle/rsi` keys, overriding the 1-min base. `mean_reversion` consumes the same plain keys unchanged (DRY). `BacktestStrategyAdapter` derives the 15m timeframe from the same contract, so the registered backtest path feeds 15m candles — backtest == live == probe. `mean_reversion.required_indicators` becomes timeframe-aware (default = 1-min, unchanged for stock `bb_reversion`). Paper activation only; live stays gated.

**Tech Stack:** Python 3.11, pytest (`source .venv/bin/activate`), the existing `StreamingIndicatorEngine` / `StreamingIndicatorResolver` / `IndicatorContract` / `BacktestStrategyAdapter`, Optuna gate harness (`scripts/probe_bb_reversion_15m_gate.py`, `_rescoped_gate`), Redis DB 1, ClickHouse native 9000.

---

## Context the implementer must read first

- Re-scoped robust gate + verdict: `reports/optuna/BB_REVERSION_15M_PROBE.md` (this branch). bb_reversion_15m PASSED (median valid Sharpe 10.69, basin 100%, OOS holds) — but **backtest return/Sharpe magnitudes are inflated by a futures P&L-accounting artifact**; only *robustness/sign* transfers, not magnitude. Paper is the real bar.
- De-risk checkpoint (DONE — Task 0 below is already complete on this branch): `scripts/derisk_live_vs_probe_15m.py` proved live `MultiTimeframeCandleAccumulator` 15m bars == the probe's `_resample_15m` bars, 5615/5615, 100.000%. **Do not redo it; it is the precondition this whole plan relies on.**
- Existing pattern to mirror exactly: `momentum_<tf>` keys → `IndicatorContract.from_required_keys` (`shared/indicators/contracts.py:98-120`) → `StreamingIndicatorResolver.collect_entry_indicators` (`shared/indicators/resolver.py:50-54`) → `engine.get_momentum_indicators(symbol, timeframe=N)`. We add an analogous `mtf_base_<tf>` for BB/RSI.
- Hard rule: read **closed** MTF candles only (`mtf_acc.candles`), never the in-progress `_buffer` — acting on an incomplete 15m bar = look-ahead (recreates the catastrophic failure mode).
- `config/strategies/futures/bb_reversion_15m.yaml` stays `enabled: false` until Task 8. Live stays gated (`config/futures_live.yaml::enabled: false`, Redis `futures:live:suspended`) throughout — this plan is paper-only.
- Run all pytest via `source .venv/bin/activate && pytest ...`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `shared/indicators/contracts.py` | Parse `mtf_base_<tf>` → BASE request w/ timeframe | Modify |
| `services/trading/indicator_engine.py` | `get_indicators_tf(symbol, tf)` — BB/RSI over closed MTF candles | Modify |
| `shared/indicators/resolver.py` | Route `mtf_base` requests; inject 15m bb_*/rsi over 1m base | Modify |
| `shared/backtest/adapter.py` | Include `mtf_base` timeframes in engine `mtf_timeframes` | Modify |
| `shared/strategy/entry/mean_reversion.py` | Timeframe-aware `required_indicators` (default 1m) | Modify |
| `config/strategies/futures/bb_reversion_15m.yaml` | `entry.params.timeframe_minutes: 15`; enable in Task 8 | Modify |
| `tests/unit/indicators/test_contracts_mtf_base.py` | Contract parsing | Create |
| `tests/unit/indicators/test_resolver_mtf_base.py` | Resolver routing + override | Create |
| `tests/unit/trading/test_engine_get_indicators_tf.py` | 15m BB/RSI, closed-bars-only | Create |
| `tests/unit/strategy/entry/test_mean_reversion_timeframe.py` | Timeframe-aware contract | Create |
| `tests/integration/test_bb_reversion_15m_parity.py` | Registered backtest == probe gate metrics | Create |
| `docs/runbooks/bb-reversion-15m-paper.md` | Paper gate + ops | Create |

---

## Task 0: De-risk checkpoint — ALREADY DONE ✅

`scripts/derisk_live_vs_probe_15m.py` on this branch proved live MTF 15m bars == probe `_resample_15m` (5615/5615, 100.000%). No action. Listed so the dependency is explicit: every later task assumes this parity. If any later change alters bucketing, re-run:
`source .venv/bin/activate && python scripts/derisk_live_vs_probe_15m.py --data data/kospi200f_1m_ch_101S6000.csv` — expected `MATCH ✅`.

---

## Task 1: Contract — parse `mtf_base_<tf>` keys

**Files:**
- Modify: `shared/indicators/contracts.py`
- Test: `tests/unit/indicators/test_contracts_mtf_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/indicators/test_contracts_mtf_base.py
from shared.indicators.contracts import IndicatorContract, IndicatorKind


def test_mtf_base_key_parsed_as_base_with_timeframe():
    c = IndicatorContract.from_required_keys(
        ["bb_lower", "bb_upper", "bb_middle", "rsi", "mtf_base_15m"]
    )
    base_tf = [
        r for r in c.requests
        if r.kind == IndicatorKind.BASE and r.timeframe is not None
    ]
    assert len(base_tf) == 1
    assert base_tf[0].timeframe.minutes == 15
    assert base_tf[0].source_key == "mtf_base_15m"
    # plain base keys still parsed as 1m BASE (no timeframe)
    assert any(
        r.name == "bb_lower" and r.timeframe is None for r in c.requests
    )


def test_mtf_base_requests_property_exposes_only_tf_base():
    c = IndicatorContract.from_required_keys(["rsi", "mtf_base_60m"])
    reqs = c.mtf_base_requests
    assert len(reqs) == 1 and reqs[0].timeframe.minutes == 60


def test_no_mtf_base_key_means_empty_property():
    c = IndicatorContract.from_required_keys(["bb_lower", "rsi"])
    assert c.mtf_base_requests == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/indicators/test_contracts_mtf_base.py -q`
Expected: FAIL (`mtf_base_requests` attribute does not exist / key parsed as plain BASE).

- [ ] **Step 3: Implement**

In `shared/indicators/contracts.py`, inside `from_required_keys` (after the `momentum_` branch, before the final plain-BASE append at ~line 121), add:

```python
            if key.startswith("mtf_base_"):
                token = key[len("mtf_base_") :]
                try:
                    tf = Timeframe.from_token(token)
                except ValueError:
                    requests.append(
                        IndicatorRequest(
                            kind=IndicatorKind.BASE,
                            name=key,
                            source_key=key,
                        )
                    )
                    continue
                requests.append(
                    IndicatorRequest(
                        kind=IndicatorKind.BASE,
                        name="mtf_base",
                        timeframe=tf,
                        source_key=key,
                    )
                )
                continue
```

Add to `IndicatorContract` (next to `momentum_requests`, ~line 79):

```python
    @property
    def mtf_base_requests(self) -> tuple[IndicatorRequest, ...]:
        return tuple(
            req
            for req in self.requests
            if req.kind == IndicatorKind.BASE and req.timeframe is not None
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/indicators/test_contracts_mtf_base.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/indicators/contracts.py tests/unit/indicators/test_contracts_mtf_base.py
git commit -m "feat(indicators): parse mtf_base_<tf> as timeframe-tagged BASE request"
```

---

## Task 2: Engine — `get_indicators_tf(symbol, tf)` over closed MTF candles

**Files:**
- Modify: `services/trading/indicator_engine.py`
- Test: `tests/unit/trading/test_engine_get_indicators_tf.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/trading/test_engine_get_indicators_tf.py
from services.trading.indicator_engine import (
    Candle,
    StreamingIndicatorEngine,
)


def _feed(engine, sym, n, base=400.0):
    # n one-minute candles, monotonic minutes; feed via the public tick path
    for i in range(n):
        m = 900 + i  # not real HHMM math; minute attr only used for bucketing
        engine.on_tick(sym, price=base + (i % 7), volume=1.0,
                        timestamp=None)  # see note
```

> NOTE: the engine's MTF accumulators are fed by `_feed_mtf_candle` from completed 1m candles. The test must drive completed 1m candles. Use the same construction the de-risk harness uses (`scripts/derisk_live_vs_probe_15m.py::_live_15m`): build `Candle(open,high,low,close,volume,minute)` and push through the engine's 1m→MTF path. Concretely:

```python
def test_get_indicators_tf_uses_closed_15m_candles_only():
    eng = StreamingIndicatorEngine(
        bb_period=5, bb_std=2.0, rsi_period=5, mtf_timeframes=[15]
    )
    sym = "101S6000"
    # 90 one-minute candles = 6 closed 15m candles + an in-progress bucket
    closes = []
    for i in range(95):
        hh = 9 + (i // 60)
        mm = i % 60
        minute = hh * 100 + mm
        c = Candle(open=400.0 + i, high=401.0 + i, low=399.0 + i,
                   close=400.5 + i, volume=1.0, minute=minute)
        eng._feed_mtf_candle(sym, c)
        closes.append(c.close)

    res = eng.get_indicators_tf(sym, 15)
    assert set(res) >= {"bb_lower", "bb_middle", "bb_upper", "rsi"}
    # Must be computed from CLOSED 15m candles only — i.e. the count of
    # 15m closes used == len(mtf_acc.candles), NOT including _buffer.
    mtf = eng._mtf_accumulators[sym][15]
    assert len(mtf.candles) >= eng.bb_period  # closed bars sufficient
    # bb_middle == SMA of last bb_period CLOSED 15m closes
    closed_closes = [c.close for c in mtf.candles]
    expected_mid = sum(closed_closes[-5:]) / 5
    assert abs(res["bb_middle"] - expected_mid) < 1e-6


def test_get_indicators_tf_empty_when_insufficient_closed():
    eng = StreamingIndicatorEngine(
        bb_period=20, bb_std=2.0, rsi_period=14, mtf_timeframes=[15]
    )
    sym = "X"
    for i in range(10):  # < 1 closed 15m candle
        eng._feed_mtf_candle(
            sym, Candle(open=1, high=1, low=1, close=1, volume=1,
                        minute=900 + i)
        )
    assert eng.get_indicators_tf(sym, 15) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/trading/test_engine_get_indicators_tf.py -q`
Expected: FAIL (`get_indicators_tf` not defined).

- [ ] **Step 3: Implement**

In `services/trading/indicator_engine.py`, add a method on `StreamingIndicatorEngine` mirroring `get_indicators` but sourced from the **closed** MTF accumulator (place it next to `get_momentum_indicators`, ~line 1023):

```python
    def get_indicators_tf(
        self, symbol: str, timeframe: int
    ) -> dict[str, float]:
        """BB/RSI computed from the symbol's CLOSED `timeframe`-minute
        candles (never the in-progress buffer — acting on an incomplete
        higher-TF bar is look-ahead). Same _calc_bb/_calc_rsi as the 1m
        path so backtest == live. Empty dict until >= bb_period closed
        higher-TF candles exist.
        """
        mtf_map = self._mtf_accumulators.get(symbol)
        if not mtf_map:
            return {}
        mtf = mtf_map.get(timeframe)
        if mtf is None or len(mtf.candles) < self.bb_period:
            return {}

        cache_key = (symbol, timeframe)
        count = mtf.total_appended
        cached = self._mtf_base_cache.get(cache_key)
        if cached and cached[0] == count:
            return cached[1].copy()

        closes = [c.close for c in mtf.candles]
        bb_lower, bb_middle, bb_upper = self._calc_bb(closes)
        rsi = self._calc_rsi(closes)
        result: dict[str, float] = {
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "bb_upper": bb_upper,
            "rsi": rsi,
        }
        self._mtf_base_cache[cache_key] = (count, result)
        return result.copy()
```

In `StreamingIndicatorEngine.__init__` (where other caches like `self._indicator_cache` are initialized, ~line 248-266), add:

```python
        self._mtf_base_cache: dict[tuple[str, int], tuple[int, dict]] = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/trading/test_engine_get_indicators_tf.py -q`
Expected: PASS (2 passed). If `_feed_mtf_candle` signature differs, adjust the test feed to match it (it takes `(symbol, candle)` — confirmed at `indicator_engine.py:939`).

- [ ] **Step 5: Commit**

```bash
git add services/trading/indicator_engine.py tests/unit/trading/test_engine_get_indicators_tf.py
git commit -m "feat(engine): get_indicators_tf — BB/RSI over closed MTF candles only"
```

---

## Task 3: Resolver — route `mtf_base` and override 1m base with 15m

**Files:**
- Modify: `shared/indicators/resolver.py`
- Test: `tests/unit/indicators/test_resolver_mtf_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/indicators/test_resolver_mtf_base.py
from shared.indicators.resolver import StreamingIndicatorResolver


class _FakeEngine:
    def get_indicators(self, symbol):
        return {"bb_lower": 1.0, "bb_middle": 2.0, "bb_upper": 3.0,
                "rsi": 10.0, "vwap": 99.0}

    def get_indicators_tf(self, symbol, timeframe):
        assert timeframe == 15
        return {"bb_lower": 11.0, "bb_middle": 12.0, "bb_upper": 13.0,
                "rsi": 55.0}

    def get_rl_features(self, symbol):
        return {}

    def get_recent_candles(self, symbol, limit=240):
        return []

    def get_momentum_indicators(self, symbol, timeframe=5):
        return {}


def test_mtf_base_overrides_1m_base_for_bb_and_rsi():
    r = StreamingIndicatorResolver(
        engine=_FakeEngine(),
        required_keys=["bb_lower", "bb_upper", "bb_middle", "rsi",
                       "vwap", "mtf_base_15m"],
    )
    out = r.collect_entry_indicators("101S6000")
    # 15m values win for bb_*/rsi; non-overlapping 1m keys (vwap) survive
    assert out["bb_lower"] == 11.0 and out["bb_middle"] == 12.0
    assert out["bb_upper"] == 13.0 and out["rsi"] == 55.0
    assert out["vwap"] == 99.0


def test_no_mtf_base_keeps_1m_base_unchanged():
    r = StreamingIndicatorResolver(
        engine=_FakeEngine(),
        required_keys=["bb_lower", "rsi"],
    )
    out = r.collect_entry_indicators("X")
    assert out["bb_lower"] == 1.0 and out["rsi"] == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/indicators/test_resolver_mtf_base.py -q`
Expected: FAIL (`bb_lower` == 1.0, 1m not overridden).

- [ ] **Step 3: Implement**

In `shared/indicators/resolver.py::collect_entry_indicators`, after the `momentum_requests` loop (after line 54, before `return result`), add:

```python
        for req in self.contract.mtf_base_requests:
            tf = req.timeframe.minutes if req.timeframe else 15
            tf_base = self.engine.get_indicators_tf(symbol, tf)
            if tf_base:
                # Higher-TF BB/RSI replace the 1m base under the same
                # plain keys so mean_reversion.generate() is unchanged.
                result.update(tf_base)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/indicators/test_resolver_mtf_base.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/indicators/resolver.py tests/unit/indicators/test_resolver_mtf_base.py
git commit -m "feat(resolver): mtf_base requests override 1m base bb_*/rsi"
```

---

## Task 4: Adapter — feed 15m candles in backtest (parity)

**Files:**
- Modify: `shared/backtest/adapter.py`
- Test: extend `tests/unit/indicators/test_resolver_mtf_base.py` (adapter MTF derivation is pure)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/indicators/test_resolver_mtf_base.py
from shared.indicators.contracts import IndicatorContract


def test_contract_mtf_base_timeframes_for_adapter():
    c = IndicatorContract.from_required_keys(
        ["bb_lower", "rsi", "mtf_base_15m"]
    )
    tfs = sorted(
        {r.timeframe.minutes for r in c.mtf_base_requests
         if r.timeframe is not None}
    )
    assert tfs == [15]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/indicators/test_resolver_mtf_base.py::test_contract_mtf_base_timeframes_for_adapter -q`
Expected: PASS already (contract from Task 1) — this guards the value the adapter must use. Now make the adapter consume it.

- [ ] **Step 3: Implement**

In `shared/backtest/adapter.py`, where `mtf_timeframes` is derived (~line 287-293), include `mtf_base_requests` timeframes:

```python
        mtf_timeframes = sorted(
            {
                req.timeframe.minutes
                for req in (
                    *self._indicator_contract.momentum_requests,
                    *self._indicator_contract.mtf_base_requests,
                )
                if req.timeframe is not None
            }
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/indicators/test_resolver_mtf_base.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/backtest/adapter.py tests/unit/indicators/test_resolver_mtf_base.py
git commit -m "feat(backtest): adapter feeds mtf_base timeframes (backtest==live)"
```

---

## Task 5: mean_reversion — timeframe-aware required_indicators

**Files:**
- Modify: `shared/strategy/entry/mean_reversion.py`
- Test: `tests/unit/strategy/entry/test_mean_reversion_timeframe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/strategy/entry/test_mean_reversion_timeframe.py
from shared.strategy.entry.mean_reversion import (
    MeanReversionEntry,
    MeanReversionConfig,
)


def test_default_is_1m_no_mtf_base_key():
    e = MeanReversionEntry(MeanReversionConfig())
    assert "mtf_base_15m" not in e.required_indicators
    assert "bb_lower" in e.required_indicators


def test_timeframe_minutes_adds_mtf_base_key():
    e = MeanReversionEntry(MeanReversionConfig(timeframe_minutes=15))
    ri = e.required_indicators
    assert "mtf_base_15m" in ri
    # plain keys still present (resolver overrides them with 15m values)
    assert {"bb_lower", "bb_upper", "bb_middle", "rsi"} <= set(ri)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_mean_reversion_timeframe.py -q`
Expected: FAIL (`MeanReversionConfig` has no `timeframe_minutes`).

- [ ] **Step 3: Implement**

In `shared/strategy/entry/mean_reversion.py`: add to `MeanReversionConfig` (with the other dataclass fields):

```python
    timeframe_minutes: int = 0  # 0 = 1-minute base; N = N-min MTF base
```

Modify `required_indicators` (lines ~118-126) to append the grouping key when set:

```python
    @property
    def required_indicators(self) -> list[str]:
        indicators = ["bb_lower", "bb_upper", "bb_middle", "rsi"]
        if self.config.volume_confirm:
            indicators.extend(["volume", "volume_ma"])
        if self.config.vwap_filter:
            indicators.append("vwap")
        if self.config.adx_filter:
            indicators.append("adx")
        if self.config.timeframe_minutes and self.config.timeframe_minutes > 1:
            indicators.append(f"mtf_base_{self.config.timeframe_minutes}m")
        return indicators
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/unit/strategy/entry/test_mean_reversion_timeframe.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/mean_reversion.py tests/unit/strategy/entry/test_mean_reversion_timeframe.py
git commit -m "feat(mean_reversion): timeframe-aware required_indicators (default 1m)"
```

---

## Task 6: Config — wire bb_reversion_15m to 15m base (still disabled)

**Files:**
- Modify: `config/strategies/futures/bb_reversion_15m.yaml`
- Test: `tests/integration/test_bb_reversion_15m_parity.py` (Task 7 covers behavior; this step only adds the param + a load assertion)

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_bb_reversion_15m_parity.py  (create; parity body added in Task 7)
from shared.config.loader import ConfigLoader
from shared.strategy.registry import (
    StrategyFactory, register_builtin_components,
)

register_builtin_components()


def test_bb_reversion_15m_entry_declares_mtf_base_15m():
    cfg = ConfigLoader.load_strategy("futures", "bb_reversion_15m")
    strat = StrategyFactory.create(cfg)
    assert "mtf_base_15m" in strat.entry.required_indicators
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/integration/test_bb_reversion_15m_parity.py::test_bb_reversion_15m_entry_declares_mtf_base_15m -q`
Expected: FAIL (`timeframe_minutes` not in config → no `mtf_base_15m`).

- [ ] **Step 3: Implement**

In `config/strategies/futures/bb_reversion_15m.yaml`, under `strategy.entry.params`, add (keep `enabled: false`):

```yaml
      timeframe_minutes: 15   # MTF base: BB/RSI computed on closed 15m bars
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/integration/test_bb_reversion_15m_parity.py::test_bb_reversion_15m_entry_declares_mtf_base_15m -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/strategies/futures/bb_reversion_15m.yaml tests/integration/test_bb_reversion_15m_parity.py
git commit -m "feat(config): bb_reversion_15m declares 15m MTF base (still enabled:false)"
```

---

## Task 7: Parity gate — registered backtest reproduces the probe verdict

**Files:**
- Modify: `tests/integration/test_bb_reversion_15m_parity.py`

The point: after Tasks 1-6 the *registered* path (`StrategyFactory` → `BacktestStrategyAdapter` → `BacktestEngine` on the **1m** CSV) must reproduce the probe's 15m result, because the adapter now feeds 15m candles and the resolver injects 15m BB/RSI. This proves backtest == probe end-to-end (the probe used a bespoke offline resample; this proves the production path matches it).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/integration/test_bb_reversion_15m_parity.py
import copy
from shared.backtest.adapter import BacktestStrategyAdapter
from shared.backtest.config import BacktestConfig
from shared.backtest.engine import BacktestEngine
from shared.validation.cli_validators import validate_csv_file

_CSV = "data/kospi200f_1m_ch_101S6000.csv"
_CSV_KW = {
    "reject_duplicate_datetime": True,
    "require_monotonic_datetime": True,
    "max_zero_volume_ratio": 0.95,
    "max_zero_volume_price_move_ratio": 0.20,
}


def test_registered_backtest_matches_probe_15m_profile():
    """Registered path on the 1m CSV must now behave like a 15m strategy
    (hundreds of trades, strongly positive Sharpe) — NOT the 1-min
    catastrophic profile. Tolerant thresholds: this guards the WIRING,
    not exact numbers (engine magnitudes are inflated; only the regime
    transfers)."""
    df1 = validate_csv_file(_CSV, **_CSV_KW)
    cfg = ConfigLoader.load_strategy("futures", "bb_reversion_15m")
    strat = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strat, cfg)
    bt = BacktestConfig.futures(initial_capital=10_000_000,
                                point_value=50_000)
    m = BacktestEngine(adapter, bt).run(df1.copy()).to_metrics_dict()
    # 15m wiring => few-hundred trades & positive Sharpe (probe baseline
    # was ~345 trades / Sharpe ~8). 1m (broken) wiring => ~1832 trades
    # or near-zero / negative. Assert the 15m regime:
    assert 150 <= m["total_trades"] <= 800, m["total_trades"]
    assert m["sharpe_ratio"] > 1.0, m["sharpe_ratio"]
    assert m["profit_factor"] > 1.2, m["profit_factor"]
```

- [ ] **Step 2: Run test to verify it fails (before wiring) / passes (after)**

Run: `source .venv/bin/activate && pytest tests/integration/test_bb_reversion_15m_parity.py::test_registered_backtest_matches_probe_15m_profile -q`
Expected: PASS now that Tasks 1-6 are merged (trade count in the 15m band, Sharpe>1, PF>1.2). If it shows ~1832 trades → the adapter is still feeding 1m (revisit Task 4); if ~0 trades → resolver not injecting 15m (revisit Task 3).

- [ ] **Step 3: (no new impl — this is the integration gate for Tasks 1-6)**

- [ ] **Step 4: Run the full affected suites (regression)**

Run:
```bash
source .venv/bin/activate && pytest \
  tests/unit/indicators/ tests/unit/trading/test_engine_get_indicators_tf.py \
  tests/unit/strategy/entry/test_mean_reversion_timeframe.py \
  tests/integration/test_bb_reversion_15m_parity.py \
  tests/unit/strategy/ -q -p no:warnings
```
Expected: all pass; **no regressions** in existing `mean_reversion`/`bb_reversion` (stock) tests (default `timeframe_minutes=0` → unchanged path).

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_bb_reversion_15m_parity.py
git commit -m "test(integration): registered backtest reproduces probe 15m regime"
```

---

## Task 8: Paper enablement + runbook (paper-only; live stays gated)

**Files:**
- Modify: `config/strategies/futures/bb_reversion_15m.yaml`
- Create: `docs/runbooks/bb-reversion-15m-paper.md`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/integration/test_bb_reversion_15m_parity.py
def test_bb_reversion_15m_enabled_for_paper_but_live_gated():
    import yaml
    with open("config/strategies/futures/bb_reversion_15m.yaml") as f:
        d = yaml.safe_load(f)
    assert d["strategy"]["enabled"] is True  # loaded for PAPER
    with open("config/futures_live.yaml") as f:
        live = yaml.safe_load(f)
    # live execution remains gated regardless of strategy enable
    assert live["futures_live"]["enabled"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/integration/test_bb_reversion_15m_parity.py::test_bb_reversion_15m_enabled_for_paper_but_live_gated -q`
Expected: FAIL (`enabled: false`).

- [ ] **Step 3: Implement**

In `config/strategies/futures/bb_reversion_15m.yaml` set `strategy.enabled: true` and replace the `# DEPRECATED ...` enable-comment with:

```yaml
  enabled: true  # PAPER ONLY. Live execution gated by config/futures_live.yaml::enabled=false + Redis futures:live:suspended. Paper-validation gate: docs/runbooks/bb-reversion-15m-paper.md. Robust-gate evidence: reports/optuna/BB_REVERSION_15M_PROBE.md.
```

Create `docs/runbooks/bb-reversion-15m-paper.md`:

```markdown
# bb_reversion_15m — paper validation runbook

## Status
Paper-only. `config/futures_live.yaml::futures_live.enabled` MUST stay
`false` and Redis `futures:live:suspended` set. This strategy backtest-
passed the re-scoped robust gate (reports/optuna/BB_REVERSION_15M_PROBE.md)
AND its live 15m bars were proven identical to the gated bars
(scripts/derisk_live_vs_probe_15m.py). Backtest magnitudes are inflated
(futures P&L artifact) — paper is the real bar.

## Run
`sts trade start --asset futures --paper` (TradingOrchestrator loads all
`enabled: true` futures strategies; coexists with Setup A/C).

## Paper-validation GATE (operator decision; mirrors Phase 5 Gate-1, extended)
bb_reversion_15m trades ~3/week on 15m. A 2-week window ≈ 6 trades —
statistically meaningless vs the ≥30–50 trade significance bar used by
the probe and the master plan. Therefore:

- **Minimum duration:** ≥ 12 trading weeks AND ≥ 30 completed paper
  trades (target ≥ 50) before any verdict.
- **PASS (→ propose live Phase-5 Gate process):** over the window,
  net-of-cost paper Sharpe > 1.0 AND profit factor > 1.2 AND max
  drawdown within risk policy AND no week with a kill-switch/risk
  breach. (Mirrors the re-scoped non-catastrophic bar — judged on the
  realized paper distribution, NOT inflated backtest numbers.)
- **FAIL/inconclusive:** below thresholds or < 30 trades at 12 weeks →
  do not advance; either extend, retune (re-run the robust gate), or
  deprecate like the prior futures attempts.

## Monitoring
- Weekly: the #256-style signal/fills monitor + Telegram FUTURES channel.
- Confirm signals fire on **closed** 15m bars only (look-ahead guard).
- Activation to LIVE remains behind Phase 5 Gate 1–3 + written operator
  approval (docs/runbooks/phase5-verification.md) — out of scope here.
```

- [ ] **Step 4: Run test to verify it passes + full regression**

Run:
```bash
source .venv/bin/activate && pytest tests/integration/test_bb_reversion_15m_parity.py tests/unit/strategy/ tests/unit/indicators/ tests/unit/trading/test_engine_get_indicators_tf.py -q -p no:warnings
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add config/strategies/futures/bb_reversion_15m.yaml docs/runbooks/bb-reversion-15m-paper.md tests/integration/test_bb_reversion_15m_parity.py
git commit -m "feat(futures): enable bb_reversion_15m for PAPER + validation runbook (live gated)"
```

---

## Task 9: Final regression + de-risk re-verify

**Files:** none (verification only)

- [ ] **Step 1: Re-run the de-risk checkpoint** (bucketing must still match after all changes)

Run: `source .venv/bin/activate && python scripts/derisk_live_vs_probe_15m.py --data data/kospi200f_1m_ch_101S6000.csv`
Expected: `MATCH ✅` 5615/5615 (unchanged — no task altered the accumulator).

- [ ] **Step 2: Broad regression**

Run: `source .venv/bin/activate && pytest tests/unit/strategy tests/unit/indicators tests/unit/trading tests/integration/test_bb_reversion_15m_parity.py -q -p no:warnings`
Expected: all pass, no regressions in stock `bb_reversion`/`mean_reversion` or other strategies (default `timeframe_minutes=0`).

- [ ] **Step 3: ruff**

Run: `source .venv/bin/activate && ruff check shared/ services/ scripts/ tests/ | tail -1`
Expected: `All checks passed!` (or only pre-existing unrelated warnings — do not expand scope).

- [ ] **Step 4: Commit (if ruff auto-fixed anything in scope)**

```bash
git add -u
git commit -m "chore: ruff clean for bb_reversion_15m productionization" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage** — Option B components all covered: contract (T1), engine 15m BB/RSI closed-only (T2), resolver override (T3), backtest parity adapter (T4), timeframe-aware strategy contract (T5), config wiring (T6), end-to-end parity gate (T7), paper enablement + gate runbook (T8), regression + de-risk re-verify (T9). De-risk = T0 (already done). Risks: #1 eliminated (T0); #2 look-ahead = T2 closed-bars-only test + runbook monitoring; #3 thin-sample = T8 runbook gate (≥12wk / ≥30–50 trades). ✅

**2. Placeholder scan** — every code step has concrete code grounded in real signatures (`from_required_keys`, `momentum_requests`, `collect_entry_indicators` line 50-54, adapter 287-293, `get_indicators` 663-722, `_calc_bb`/`_calc_rsi` 1241/1255, `_feed_mtf_candle` 939, mean_reversion 118-126). No TBD/▢. The T2 test NOTE points the implementer to the exact existing pattern (`derisk_live_vs_probe_15m._live_15m`) rather than hand-waving. ✅

**3. Type/name consistency** — `mtf_base_<tf>` key, `IndicatorContract.mtf_base_requests`, `get_indicators_tf(symbol, timeframe)`, `MeanReversionConfig.timeframe_minutes`, `_mtf_base_cache` used consistently across T1→T8. Plain keys (`bb_lower/bb_upper/bb_middle/rsi`) preserved so `mean_reversion.generate()` is untouched (DRY). ✅

**Caveat carried into the plan:** backtest magnitudes are inflated — T7 asserts the *regime* (trade-count band, Sharpe>1/PF>1.2) not exact numbers; the real bar is the T8 paper gate on realized paper distribution.
