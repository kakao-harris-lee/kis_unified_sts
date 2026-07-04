# LLM Market-Call Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a validation-first scorecard that captures each day's structured LLM pre-market call, scores it against realized outcomes, and reports a baseline-relative track record (does it beat naive + is confidence calibrated).

**Architecture:** An extensible *facet* registry (one scorable prediction type each) drives a capture→score→aggregate→report loop. Predictions persist to the SQLite runtime ledger at the time they are made; a post-close cron scores each registered facet against no-look-ahead outcome data; an aggregator computes rolling baseline-relative metrics; a reporter posts a daily/weekly Telegram scorecard. New facets plug in via the registry without touching the pipeline.

**Tech Stack:** Python 3.12, SQLite runtime ledger (`shared/storage/runtime_ledger.py`), Redis DB1, pydantic-style config (`shared/config/base.py`), pandas, pytest + fakeredis, supercronic (`deploy/scheduler.crontab`).

## Global Constraints

- KST-native everywhere (timestamps, trading-day keys, cron); convert at boundaries, never introduce naive-UTC.
- Runtime ledger = SQLite via `shared/storage/runtime_ledger.py`; Redis = DB1; every new Redis key needs a TTL.
- Config-driven only: thresholds/windows/facet toggles in `config/llm_scorecard.yaml`, never hardcoded branches.
- No-look-ahead: outcomes read ONLY from data timestamped after the prediction's `captured_at` (use the `OutcomeData` accessor; `LookaheadGuard` where applicable).
- `unscorable` (data gap) = `correct=None`, never counted as wrong.
- Capture is best-effort: a recorder failure MUST NOT break the briefing or screener (try/except + log).
- Baseline-relative: each facet reports `edge = value − baseline`.
- No ClickHouse. No new heavy deps. Hermetic tests (fakes / fakeredis; clocks pinned).
- venv mandatory: `.venv/bin/pytest`. Branch off `main`; do not commit to main.

---

## File Structure

- `config/llm_scorecard.yaml` — facet toggles, rolling windows, per-facet params, baselines, report toggles/channel.
- `shared/llm_scorecard/__init__.py` — exports.
- `shared/llm_scorecard/config.py` — `ScorecardConfig` (from_yaml).
- `shared/llm_scorecard/facets/base.py` — `FacetPrediction`, `FacetScore`, `PredictionFacet` Protocol, `CaptureContext`, `register_facet`, `FACET_REGISTRY`, `enabled_facets(config)`.
- `shared/llm_scorecard/outcome_data.py` — `OutcomeData` (no-look-ahead market accessor).
- `shared/llm_scorecard/facets/direction.py` — `DirectionFacet`.
- `shared/llm_scorecard/facets/themes.py` — `ThemesFacet`.
- `shared/llm_scorecard/facets/movers.py` — `MoversFacet`.
- `shared/llm_scorecard/facets/volume_surge.py` — `VolumeSurgeFacet`.
- `shared/llm_scorecard/recorder.py` — `capture_predictions(ctx, config, ledger)` (iterates registered facets).
- `shared/llm_scorecard/scorer.py` — `score_day(date_kst, config, ledger, outcome)` (iterates registered facets).
- `shared/llm_scorecard/aggregator.py` — `rolling_metrics(scores, window)`, `calibration_bins(scores)`.
- `shared/llm_scorecard/reporter.py` — `format_daily(...)`, `format_weekly(...)` (pure str builders).
- `shared/storage/runtime_ledger.py` — add `llm_predictions` + `prediction_scores` tables + accessors.
- `scripts/analysis/llm_scorecard_score.py` — post-close cron entry (score the day + daily Telegram).
- `scripts/analysis/llm_scorecard_weekly.py` — weekly digest cron entry.
- `scripts/llm_premarket_briefing.py` — add capture hook (direction/themes).
- `deploy/scheduler.crontab` — scorer + weekly crons (post-close, KST).
- `tests/unit/llm_scorecard/` — one test file per module.

---

## Phase 1 — Foundation

### Task 1: ScorecardConfig

**Files:**
- Create: `config/llm_scorecard.yaml`
- Create: `shared/llm_scorecard/__init__.py` (empty), `shared/llm_scorecard/config.py`
- Test: `tests/unit/llm_scorecard/test_config.py`

**Interfaces:**
- Produces: `ScorecardConfig.from_yaml(path: str | None = None) -> ScorecardConfig` with fields `enabled_facets: list[str]`, `rolling_windows: list[int]`, `facet_params: dict[str, dict]`, `report_daily: bool`, `report_weekly: bool`, `telegram_domain: str`.

- [ ] **Step 1: Write `config/llm_scorecard.yaml`**

```yaml
llm_scorecard:
  enabled_facets: ["direction"]   # add themes/movers/volume_surge as built
  rolling_windows: [20, 60]
  report_daily: true
  report_weekly: true
  telegram_domain: "briefing"
  facet_params:
    direction:
      symbol: "101S6000"              # KOSPI200 futures continuous
      neutral_band_pct: 0.15          # |return| below this = NEUTRAL outcome
    themes:
      top_n: 3
    movers:
      horizon: "session"
    volume_surge:
      horizon: "flag_to_close"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/llm_scorecard/test_config.py
from shared.llm_scorecard.config import ScorecardConfig

def test_loads_defaults_from_yaml():
    cfg = ScorecardConfig.from_yaml("config/llm_scorecard.yaml")
    assert "direction" in cfg.enabled_facets
    assert cfg.rolling_windows == [20, 60]
    assert cfg.telegram_domain == "briefing"
    assert cfg.facet_params["direction"]["symbol"] == "101S6000"

def test_missing_file_uses_safe_defaults():
    cfg = ScorecardConfig.from_yaml("/nonexistent.yaml")
    assert cfg.enabled_facets == ["direction"]
    assert cfg.report_daily is True
```

- [ ] **Step 3: Run → fail** `.venv/bin/pytest tests/unit/llm_scorecard/test_config.py -v` → FAIL (module missing)

- [ ] **Step 4: Implement `shared/llm_scorecard/config.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
import yaml

@dataclass
class ScorecardConfig:
    enabled_facets: list[str] = field(default_factory=lambda: ["direction"])
    rolling_windows: list[int] = field(default_factory=lambda: [20, 60])
    facet_params: dict = field(default_factory=dict)
    report_daily: bool = True
    report_weekly: bool = True
    telegram_domain: str = "briefing"

    @classmethod
    def from_yaml(cls, path: str | None = None) -> "ScorecardConfig":
        data: dict = {}
        try:
            with open(path or "config/llm_scorecard.yaml") as f:
                data = (yaml.safe_load(f) or {}).get("llm_scorecard", {}) or {}
        except (FileNotFoundError, OSError):
            data = {}
        return cls(
            enabled_facets=data.get("enabled_facets", ["direction"]),
            rolling_windows=data.get("rolling_windows", [20, 60]),
            facet_params=data.get("facet_params", {}),
            report_daily=bool(data.get("report_daily", True)),
            report_weekly=bool(data.get("report_weekly", True)),
            telegram_domain=data.get("telegram_domain", "briefing"),
        )
```

- [ ] **Step 5: Run → pass; commit** `git add config/llm_scorecard.yaml shared/llm_scorecard/ tests/unit/llm_scorecard/test_config.py && git commit -m "feat(scorecard): ScorecardConfig + yaml"`

---

### Task 2: Ledger tables + accessors

**Files:**
- Modify: `shared/storage/runtime_ledger.py` (add 2 tables to the `executescript` schema block near line 261; add accessors near the other `record_*`/`query_*` methods)
- Test: `tests/unit/llm_scorecard/test_ledger_predictions.py`

**Interfaces:**
- Produces on the concrete ledger:
  - `save_prediction(date_kst: str, facet: str, captured_at: str, payload: dict, confidence: float | None) -> None` (idempotent upsert per (date_kst, facet))
  - `load_predictions(date_kst: str) -> list[dict]`
  - `save_score(score: dict) -> None` (keys: date_kst, facet, correct, value, economic_proxy, baseline_value, edge, detail, scored_at; idempotent per (date_kst, facet))
  - `query_scores(facet: str | None = None, start: str | None = None, end: str | None = None) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/llm_scorecard/test_ledger_predictions.py
import tempfile, os
from shared.storage.runtime_ledger import SqliteRuntimeLedger  # confirm concrete class name

def _ledger():
    d = tempfile.mkdtemp(); return SqliteRuntimeLedger(os.path.join(d, "t.db"))

def test_prediction_upsert_idempotent():
    l = _ledger()
    l.save_prediction("2026-06-25", "direction", "2026-06-25T08:40:00+09:00", {"dir": "BULL"}, 0.7)
    l.save_prediction("2026-06-25", "direction", "2026-06-25T08:41:00+09:00", {"dir": "BEAR"}, 0.6)
    rows = l.load_predictions("2026-06-25")
    assert len(rows) == 1 and rows[0]["payload"]["dir"] == "BEAR"

def test_score_upsert_and_query():
    l = _ledger()
    l.save_score({"date_kst": "2026-06-25", "facet": "direction", "correct": True,
                  "value": 0.8, "economic_proxy": 0.8, "baseline_value": 0.0,
                  "edge": 0.8, "detail": {"realized": 0.8}, "scored_at": "2026-06-25T16:00:00+09:00"})
    rows = l.query_scores(facet="direction")
    assert len(rows) == 1 and rows[0]["correct"] is True and rows[0]["edge"] == 0.8
```

- [ ] **Step 2: Run → fail.** First confirm the concrete class name: `grep -n "class .*Ledger" shared/storage/runtime_ledger.py` and use it (Protocol is `RuntimeLedger`; the SQLite impl is the concrete one). Adjust the import in the test if needed.

- [ ] **Step 3: Add tables** in the `executescript` block (after `market_context_history`):

```sql
CREATE TABLE IF NOT EXISTS llm_predictions (
    date_kst TEXT NOT NULL,
    facet TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (date_kst, facet)
);
CREATE TABLE IF NOT EXISTS prediction_scores (
    date_kst TEXT NOT NULL,
    facet TEXT NOT NULL,
    correct INTEGER,          -- 1/0/NULL (NULL = unscorable)
    value REAL NOT NULL,
    economic_proxy REAL NOT NULL,
    baseline_value REAL NOT NULL,
    edge REAL NOT NULL,
    detail_json TEXT NOT NULL,
    scored_at TEXT NOT NULL,
    PRIMARY KEY (date_kst, facet)
);
```

- [ ] **Step 4: Add accessors** (follow the existing `record_*`/`query_trades` style — same connection/lock):

```python
import json
def save_prediction(self, date_kst, facet, captured_at, payload, confidence):
    with self._lock:
        self._require_conn().execute(
            "INSERT INTO llm_predictions(date_kst,facet,captured_at,payload_json,confidence,created_at)"
            " VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(date_kst,facet) DO UPDATE SET"
            " captured_at=excluded.captured_at, payload_json=excluded.payload_json,"
            " confidence=excluded.confidence",
            (date_kst, facet, captured_at, json.dumps(payload), confidence, _now_kst_iso()),
        )
        self._require_conn().commit()

def load_predictions(self, date_kst):
    with self._lock:
        rows = self._require_conn().execute(
            "SELECT * FROM llm_predictions WHERE date_kst=?", (date_kst,)).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]

def save_score(self, s):
    correct = None if s["correct"] is None else (1 if s["correct"] else 0)
    with self._lock:
        self._require_conn().execute(
            "INSERT INTO prediction_scores(date_kst,facet,correct,value,economic_proxy,"
            "baseline_value,edge,detail_json,scored_at) VALUES(?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(date_kst,facet) DO UPDATE SET correct=excluded.correct,"
            " value=excluded.value, economic_proxy=excluded.economic_proxy,"
            " baseline_value=excluded.baseline_value, edge=excluded.edge,"
            " detail_json=excluded.detail_json, scored_at=excluded.scored_at",
            (s["date_kst"], s["facet"], correct, s["value"], s["economic_proxy"],
             s["baseline_value"], s["edge"], json.dumps(s["detail"]), s["scored_at"]))
        self._require_conn().commit()

def query_scores(self, facet=None, start=None, end=None):
    q = "SELECT * FROM prediction_scores WHERE 1=1"; p = []
    if facet: q += " AND facet=?"; p.append(facet)
    if start: q += " AND date_kst>=?"; p.append(start)
    if end: q += " AND date_kst<=?"; p.append(end)
    q += " ORDER BY date_kst ASC"
    with self._lock:
        rows = self._require_conn().execute(q, p).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["detail"] = json.loads(d.pop("detail_json"))
        d["correct"] = None if d["correct"] is None else bool(d["correct"])
        out.append(d)
    return out
```

(Use the file's existing `_now_kst_iso`/now helper; if none, add `datetime.now().isoformat()` — container TZ=KST.)

- [ ] **Step 5: Run → pass; commit.**

---

### Task 3: Facet contract + registry

**Files:**
- Create: `shared/llm_scorecard/facets/__init__.py`, `shared/llm_scorecard/facets/base.py`
- Test: `tests/unit/llm_scorecard/test_registry.py`

**Interfaces:**
- Produces: `FacetPrediction`, `FacetScore` dataclasses (fields per spec §"Facet abstraction"); `PredictionFacet` Protocol with `name`, `outcome_horizon`, `outcome_source`, `capture(ctx)`, `score(pred, mkt)`, `baseline(pred, mkt)`; `CaptureContext` dataclass (`market_context: dict | None`, `screener: dict | None`, `redis`, `date_kst`, `now_kst`); `register_facet(facet)`; `FACET_REGISTRY: dict[str, PredictionFacet]`; `enabled_facets(cfg) -> list[PredictionFacet]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/llm_scorecard/test_registry.py
from shared.llm_scorecard.facets.base import (
    register_facet, enabled_facets, FACET_REGISTRY, FacetScore)
from shared.llm_scorecard.config import ScorecardConfig

class _Dummy:
    name = "dummy"; outcome_horizon = "same_session"; outcome_source = "stock_daily"
    def capture(self, ctx): return None
    def score(self, pred, mkt): ...
    def baseline(self, pred, mkt): return 0.0

def test_register_and_filter_by_config():
    register_facet(_Dummy())
    assert "dummy" in FACET_REGISTRY
    cfg = ScorecardConfig(enabled_facets=["dummy"])
    assert [f.name for f in enabled_facets(cfg)] == ["dummy"]
    cfg2 = ScorecardConfig(enabled_facets=["other"])
    assert enabled_facets(cfg2) == []
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `base.py`** (dataclasses per spec + registry):

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

@dataclass
class FacetPrediction:
    facet: str; date_kst: str; captured_at: datetime
    payload: dict; confidence: float | None = None

@dataclass
class FacetScore:
    facet: str; date_kst: str
    correct: bool | None; value: float; economic_proxy: float
    baseline_value: float; edge: float
    detail: dict = field(default_factory=dict)
    scored_at: datetime | None = None

@dataclass
class CaptureContext:
    date_kst: str; now_kst: datetime
    market_context: dict | None = None
    screener: dict | None = None
    redis: Any = None

@runtime_checkable
class PredictionFacet(Protocol):
    name: str; outcome_horizon: str; outcome_source: str
    def capture(self, ctx: CaptureContext) -> FacetPrediction | None: ...
    def score(self, pred: FacetPrediction, mkt: "OutcomeData") -> FacetScore: ...
    def baseline(self, pred: FacetPrediction, mkt: "OutcomeData") -> float: ...

FACET_REGISTRY: dict[str, PredictionFacet] = {}
def register_facet(facet: PredictionFacet) -> None:
    FACET_REGISTRY[facet.name] = facet
def enabled_facets(cfg) -> list[PredictionFacet]:
    return [FACET_REGISTRY[n] for n in cfg.enabled_facets if n in FACET_REGISTRY]
```

- [ ] **Step 4: Run → pass; commit.**

---

### Task 4: OutcomeData (no-look-ahead accessor)

**Files:**
- Create: `shared/llm_scorecard/outcome_data.py`
- Test: `tests/unit/llm_scorecard/test_outcome_data.py`

**Interfaces:**
- Produces: `OutcomeData(store, now_kst)` with `session_return(symbol, date_kst, captured_at) -> float | None` (open→close % return using only bars at/after `captured_at`), `bars_after(symbol, date_kst, after: datetime) -> "pd.DataFrame|None"`. Returns `None` when data is missing/insufficient (→ unscorable).

- [ ] **Step 1: Write the failing test** (synthetic bars; assert look-ahead is respected):

```python
# tests/unit/llm_scorecard/test_outcome_data.py
import pandas as pd
from datetime import datetime
from shared.llm_scorecard.outcome_data import OutcomeData

class _Store:
    def __init__(self, df): self._df = df
    def get_minute_bars(self, symbol, start=None, end=None): return self._df

def _df():
    idx = pd.to_datetime(["2026-06-25 08:50","2026-06-25 09:00","2026-06-25 15:20"])
    return pd.DataFrame({"open":[100,101,109],"close":[100,101,110]}, index=idx)

def test_session_return_excludes_pre_capture_bars():
    od = OutcomeData(_Store(_df()), now_kst=datetime(2026,6,25,16,0))
    cap = datetime(2026,6,25,8,55)  # after 08:50 pre-market print
    r = od.session_return("X", "2026-06-25", cap)
    assert round(r, 2) == round((110-101)/101*100, 2)  # open=101 (09:00), close=110

def test_missing_data_returns_none():
    class Empty:
        def get_minute_bars(self, *a, **k): return None
    assert OutcomeData(Empty(), now_kst=datetime(2026,6,25,16,0)).session_return("X","2026-06-25",datetime(2026,6,25,8,55)) is None
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `outcome_data.py`:**

```python
from __future__ import annotations
from datetime import datetime

class OutcomeData:
    def __init__(self, store, now_kst: datetime):
        self._store = store; self._now = now_kst

    def bars_after(self, symbol, date_kst, after: datetime):
        try:
            df = self._store.get_minute_bars(symbol, start=date_kst, end=date_kst)
        except Exception:
            return None
        if df is None or len(df) == 0:
            return None
        df = df[df.index >= after]
        return df if len(df) else None

    def session_return(self, symbol, date_kst, captured_at: datetime):
        df = self.bars_after(symbol, date_kst, captured_at)
        if df is None or len(df) < 2:
            return None
        o = float(df.iloc[0]["open"]); c = float(df.iloc[-1]["close"])
        if o == 0:
            return None
        return (c - o) / o * 100.0
```

- [ ] **Step 4: Run → pass; commit.** (Confirm `get_minute_bars` index is a tz-naive KST DatetimeIndex; if the store returns a `datetime` column instead, set it as index in `bars_after`.)

---

## Phase 2 — Direction facet end-to-end (proves the loop)

### Task 5: DirectionFacet

**Files:**
- Create: `shared/llm_scorecard/facets/direction.py`
- Test: `tests/unit/llm_scorecard/test_direction_facet.py`

**Interfaces:**
- Consumes: `FacetPrediction`, `FacetScore`, `CaptureContext` (Task 3), `OutcomeData` (Task 4), `MarketContext` dict (`shared/llm/market_context.py` `to_dict`: keys `overall_signal`, `confidence`, `risk_mode`).
- Produces: `DirectionFacet(neutral_band_pct=0.15, symbol="101S6000")` registered as `"direction"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/llm_scorecard/test_direction_facet.py
from datetime import datetime
from shared.llm_scorecard.facets.base import CaptureContext, FacetPrediction
from shared.llm_scorecard.facets.direction import DirectionFacet

def test_capture_from_market_context():
    f = DirectionFacet()
    ctx = CaptureContext(date_kst="2026-06-25", now_kst=datetime(2026,6,25,8,40),
                         market_context={"overall_signal":"BULLISH","confidence":0.7,"risk_mode":"RISK_ON"})
    pred = f.capture(ctx)
    assert pred.payload["direction"] == "BULL" and pred.confidence == 0.7

class _OD:
    def __init__(self, ret): self._r = ret
    def session_return(self, *a, **k): return self._r

def test_score_correct_when_direction_matches():
    f = DirectionFacet(neutral_band_pct=0.15)
    pred = FacetPrediction("direction","2026-06-25",datetime(2026,6,25,8,40),{"direction":"BULL"},0.7)
    s = f.score(pred, _OD(ret=1.2))   # realized +1.2%
    assert s.correct is True and s.economic_proxy == 1.2 and s.edge == 1.2  # baseline flat=0

def test_score_unscorable_on_missing_outcome():
    f = DirectionFacet()
    pred = FacetPrediction("direction","2026-06-25",datetime(2026,6,25,8,40),{"direction":"BULL"},0.7)
    s = f.score(pred, _OD(ret=None))
    assert s.correct is None

def test_neutral_outcome_within_band():
    f = DirectionFacet(neutral_band_pct=0.15)
    pred = FacetPrediction("direction","2026-06-25",datetime(2026,6,25,8,40),{"direction":"NEUTRAL"},0.5)
    s = f.score(pred, _OD(ret=0.05))  # |0.05|<0.15 → NEUTRAL realized → correct
    assert s.correct is True
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `direction.py`:**

```python
from __future__ import annotations
from datetime import datetime
from shared.llm_scorecard.facets.base import (
    FacetPrediction, FacetScore, CaptureContext, register_facet)

_SIGNAL_MAP = {"BULLISH":"BULL","BEARISH":"BEAR","NEUTRAL":"NEUTRAL"}

class DirectionFacet:
    name = "direction"; outcome_horizon = "same_session_open_to_close"; outcome_source = "futures_minute"
    def __init__(self, neutral_band_pct: float = 0.15, symbol: str = "101S6000"):
        self.band = neutral_band_pct; self.symbol = symbol

    def capture(self, ctx: CaptureContext) -> FacetPrediction | None:
        mc = ctx.market_context
        if not mc:
            return None
        direction = _SIGNAL_MAP.get(str(mc.get("overall_signal","NEUTRAL")), "NEUTRAL")
        return FacetPrediction(self.name, ctx.date_kst, ctx.now_kst,
                               {"direction": direction, "risk_mode": mc.get("risk_mode")},
                               confidence=float(mc.get("confidence", 0.5)))

    def _realized_dir(self, ret: float) -> str:
        if abs(ret) < self.band: return "NEUTRAL"
        return "BULL" if ret > 0 else "BEAR"

    def baseline(self, pred, mkt) -> float:
        return 0.0  # always-flat directional PnL

    def score(self, pred: FacetPrediction, mkt) -> FacetScore:
        ret = mkt.session_return(self.symbol, pred.date_kst, pred.captured_at)
        if ret is None:
            return FacetScore(self.name, pred.date_kst, None, 0.0, 0.0, 0.0, 0.0,
                              {"reason": "no_outcome_data"}, datetime.now())
        predicted = pred.payload["direction"]
        realized = self._realized_dir(ret)
        sign = {"BULL": 1.0, "BEAR": -1.0, "NEUTRAL": 0.0}[predicted]
        econ = ret * sign  # PnL of taking predicted direction
        base = self.baseline(pred, mkt)
        return FacetScore(self.name, pred.date_kst, predicted == realized, ret * sign,
                          econ, base, (ret * sign) - base,
                          {"predicted": predicted, "realized": realized, "ret_pct": ret}, datetime.now())

register_facet(DirectionFacet())
```

- [ ] **Step 4: Run → pass; commit.**

---

### Task 6: Recorder (capture orchestration)

**Files:**
- Create: `shared/llm_scorecard/recorder.py`
- Test: `tests/unit/llm_scorecard/test_recorder.py`

**Interfaces:**
- Consumes: `enabled_facets(cfg)`, `CaptureContext`, ledger `save_prediction`.
- Produces: `capture_predictions(ctx: CaptureContext, cfg, ledger) -> int` (count captured). Best-effort: never raises.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/llm_scorecard/test_recorder.py
from datetime import datetime
from shared.llm_scorecard.recorder import capture_predictions
from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import CaptureContext

class _Ledger:
    def __init__(self): self.saved = []
    def save_prediction(self, date_kst, facet, captured_at, payload, confidence):
        self.saved.append((facet, payload, confidence))

def test_captures_enabled_direction_facet():
    led = _Ledger()
    ctx = CaptureContext("2026-06-25", datetime(2026,6,25,8,40),
                         market_context={"overall_signal":"BEARISH","confidence":0.6})
    n = capture_predictions(ctx, ScorecardConfig(enabled_facets=["direction"]), led)
    assert n == 1 and led.saved[0][0] == "direction" and led.saved[0][1]["direction"] == "BEAR"

def test_recorder_is_best_effort():
    class Boom:
        def save_prediction(self, *a, **k): raise RuntimeError("redis down")
    ctx = CaptureContext("2026-06-25", datetime(2026,6,25,8,40),
                         market_context={"overall_signal":"BULLISH","confidence":0.7})
    assert capture_predictions(ctx, ScorecardConfig(enabled_facets=["direction"]), Boom()) == 0
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `recorder.py`:**

```python
from __future__ import annotations
import logging
from shared.llm_scorecard.facets.base import enabled_facets
import shared.llm_scorecard.facets.direction  # noqa: F401  (register)
logger = logging.getLogger(__name__)

def capture_predictions(ctx, cfg, ledger) -> int:
    n = 0
    for facet in enabled_facets(cfg):
        try:
            pred = facet.capture(ctx)
            if pred is None:
                continue
            ledger.save_prediction(pred.date_kst, pred.facet, pred.captured_at.isoformat(),
                                   pred.payload, pred.confidence)
            n += 1
        except Exception:
            logger.exception("scorecard capture failed for facet=%s", getattr(facet, "name", "?"))
    return n
```

- [ ] **Step 4: Run → pass; commit.**

---

### Task 7: Scorer + aggregator

**Files:**
- Create: `shared/llm_scorecard/scorer.py`, `shared/llm_scorecard/aggregator.py`
- Test: `tests/unit/llm_scorecard/test_scorer.py`, `tests/unit/llm_scorecard/test_aggregator.py`

**Interfaces:**
- Consumes: `load_predictions`, `save_score`, `query_scores`, `enabled_facets`, `OutcomeData`, `FacetPrediction`.
- Produces: `score_day(date_kst, cfg, ledger, outcome) -> int`; `rolling_metrics(scores: list[dict], window: int) -> dict`; `calibration_bins(scores: list[dict], pred_conf: dict) -> list[dict]`.

- [ ] **Step 1: Write failing `test_scorer.py`**

```python
from datetime import datetime
from shared.llm_scorecard.scorer import score_day
from shared.llm_scorecard.config import ScorecardConfig

class _Ledger:
    def __init__(self, preds): self._p = preds; self.scores = []
    def load_predictions(self, d): return self._p
    def save_score(self, s): self.scores.append(s)
class _OD:
    def session_return(self, *a, **k): return 0.9

def test_score_day_writes_score_per_facet():
    preds = [{"facet":"direction","date_kst":"2026-06-25",
              "captured_at":"2026-06-25T08:40:00+09:00","payload":{"direction":"BULL"},"confidence":0.7}]
    led = _Ledger(preds)
    n = score_day("2026-06-25", ScorecardConfig(enabled_facets=["direction"]), led, _OD())
    assert n == 1 and led.scores[0]["facet"] == "direction" and led.scores[0]["correct"] is True
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `scorer.py`:**

```python
from __future__ import annotations
import logging
from datetime import datetime
from dataclasses import asdict
from shared.llm_scorecard.facets.base import enabled_facets, FacetPrediction
import shared.llm_scorecard.facets.direction  # noqa: F401
logger = logging.getLogger(__name__)

def score_day(date_kst, cfg, ledger, outcome) -> int:
    preds = {p["facet"]: p for p in ledger.load_predictions(date_kst)}
    n = 0
    for facet in enabled_facets(cfg):
        p = preds.get(facet.name)
        if p is None:
            continue
        try:
            pred = FacetPrediction(facet.name, p["date_kst"],
                                   datetime.fromisoformat(p["captured_at"]),
                                   p["payload"], p.get("confidence"))
            fs = facet.score(pred, outcome)
            ledger.save_score({"date_kst": fs.date_kst, "facet": fs.facet, "correct": fs.correct,
                               "value": fs.value, "economic_proxy": fs.economic_proxy,
                               "baseline_value": fs.baseline_value, "edge": fs.edge,
                               "detail": fs.detail,
                               "scored_at": (fs.scored_at or datetime.now()).isoformat()})
            n += 1
        except Exception:
            logger.exception("scorecard scoring failed facet=%s", facet.name)
    return n
```

- [ ] **Step 4: Write failing `test_aggregator.py`** (hit-rate ignores unscorable; edge mean; calibration bins):

```python
from shared.llm_scorecard.aggregator import rolling_metrics, calibration_bins

def test_rolling_metrics_ignores_unscorable():
    scores = [{"correct": True, "edge": 1.0, "economic_proxy": 1.0},
              {"correct": None, "edge": 0.0, "economic_proxy": 0.0},
              {"correct": False, "edge": -0.5, "economic_proxy": -0.5}]
    m = rolling_metrics(scores, window=60)
    assert m["n_scored"] == 2 and m["hit_rate"] == 0.5
    assert round(m["mean_edge"], 3) == round((1.0-0.5+0.0)/3, 3)  # edge over all rows
    assert round(m["econ_proxy_sum"], 2) == 0.5

def test_calibration_bins_group_by_confidence():
    scores = [{"date_kst":"d1","correct":True},{"date_kst":"d2","correct":False}]
    conf = {"d1":0.9,"d2":0.4}
    bins = calibration_bins(scores, conf)
    assert any(b["lo"] <= 0.9 < b["hi"] and b["hit_rate"] == 1.0 for b in bins)
```

- [ ] **Step 5: Implement `aggregator.py`:**

```python
from __future__ import annotations

def rolling_metrics(scores: list[dict], window: int) -> dict:
    rows = scores[-window:] if window else scores
    scored = [r for r in rows if r.get("correct") is not None]
    hits = sum(1 for r in scored if r["correct"])
    edges = [r.get("edge", 0.0) for r in rows]
    return {
        "n": len(rows), "n_scored": len(scored),
        "hit_rate": (hits / len(scored)) if scored else None,
        "mean_edge": (sum(edges) / len(edges)) if edges else 0.0,
        "econ_proxy_sum": sum(r.get("economic_proxy", 0.0) for r in rows),
    }

def calibration_bins(scores: list[dict], pred_conf: dict, n_bins: int = 5) -> list[dict]:
    edges = [(i / n_bins, (i + 1) / n_bins) for i in range(n_bins)]
    out = []
    for lo, hi in edges:
        members = [s for s in scores
                   if s.get("correct") is not None
                   and lo <= (pred_conf.get(s["date_kst"], -1)) < (hi if hi < 1 else 1.01)]
        hr = (sum(1 for s in members if s["correct"]) / len(members)) if members else None
        out.append({"lo": lo, "hi": hi, "n": len(members), "hit_rate": hr})
    return out
```

- [ ] **Step 6: Run both → pass; commit.**

---

### Task 8: Reporter (daily Telegram formatting)

**Files:**
- Create: `shared/llm_scorecard/reporter.py`
- Test: `tests/unit/llm_scorecard/test_reporter.py`

**Interfaces:**
- Consumes: a day's score rows (`query_scores`) + rolling metrics (Task 7).
- Produces: `format_daily(date_kst, day_scores: list[dict], rolling: dict) -> str`; `format_weekly(window: int, by_facet: dict[str, dict]) -> str`. Pure functions (no I/O).

- [ ] **Step 1: Write the failing test**

```python
from shared.llm_scorecard.reporter import format_daily

def test_daily_shows_per_facet_result_and_rolling():
    rows = [{"facet":"direction","correct":True,"edge":1.2,
             "detail":{"predicted":"BULL","realized":"BULL","ret_pct":1.2}}]
    msg = format_daily("2026-06-25", rows, {"hit_rate":0.55,"n_scored":20,"mean_edge":0.3})
    assert "direction" in msg and "✅" in msg and "1.2" in msg and "55" in msg
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `reporter.py`** (KST headers, ✅/❌/⚪ for True/False/None):

```python
from __future__ import annotations

def _mark(correct):
    return "✅" if correct is True else ("❌" if correct is False else "⚪")

def format_daily(date_kst, day_scores, rolling) -> str:
    lines = [f"📊 <b>LLM 콜 채점 {date_kst}</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for s in day_scores:
        d = s.get("detail", {})
        lines.append(f"{_mark(s['correct'])} <b>{s['facet']}</b> "
                     f"edge={s['edge']:+.2f} ({d.get('predicted','?')}→{d.get('realized','?')})")
    hr = rolling.get("hit_rate")
    hr_s = f"{hr*100:.0f}%" if hr is not None else "n/a"
    lines += ["━━━━━━━━━━━━━━━━━━━━",
              f"롤링({rolling.get('n_scored',0)}일) hit-rate={hr_s} mean_edge={rolling.get('mean_edge',0):+.2f}"]
    return "\n".join(lines)

def format_weekly(window, by_facet) -> str:
    lines = [f"🗓️ <b>LLM 스코어카드 주간 ({window}일 롤링)</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for facet, m in by_facet.items():
        hr = m.get("hit_rate"); hr_s = f"{hr*100:.0f}%" if hr is not None else "n/a"
        useful = "유용" if (m.get("mean_edge", 0) > 0 and (hr or 0) > 0.5) else "미입증"
        lines.append(f"<b>{facet}</b>: hit={hr_s} edge={m.get('mean_edge',0):+.2f} "
                     f"econ={m.get('econ_proxy_sum',0):+.1f} n={m.get('n_scored',0)} → {useful}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run → pass; commit.**

---

### Task 9: Cron entry + capture hook (wire the loop)

**Files:**
- Create: `scripts/analysis/llm_scorecard_score.py`
- Modify: `scripts/llm_premarket_briefing.py` (capture hook after analysis, ~line 79)
- Modify: `deploy/scheduler.crontab` (scorer cron, post-close KST)
- Test: `tests/unit/llm_scorecard/test_score_entry.py`

**Interfaces:**
- Consumes: everything above + `MarketContext` Redis (`trading:*:market_context` or the analyzer return), the market data store, `notifier_for_domain`, the concrete ledger constructor.

- [ ] **Step 1: Capture hook** in `llm_premarket_briefing.py` after `if futures_plan: logger.info(...)`:

```python
        # --- scorecard capture (best-effort; must not break the briefing) ---
        try:
            from datetime import datetime
            from shared.llm_scorecard.config import ScorecardConfig
            from shared.llm_scorecard.recorder import capture_predictions
            from shared.llm_scorecard.facets.base import CaptureContext
            from shared.storage.runtime_ledger import get_runtime_ledger  # confirm factory name
            mc = futures_plan.market_context.to_dict() if getattr(futures_plan, "market_context", None) else None
            now = datetime.now()
            ctx = CaptureContext(date_kst=now.strftime("%Y-%m-%d"), now_kst=now, market_context=mc)
            capture_predictions(ctx, ScorecardConfig.from_yaml(), get_runtime_ledger())
        except Exception:
            logger.exception("scorecard capture hook failed (non-fatal)")
```

(Confirm how to obtain the `MarketContext` dict from `run_unified_analysis` — it may be on `futures_plan` or published to Redis `trading:futures:market_context`; read whichever exists. Confirm the ledger factory/singleton name via `grep -n "def get_runtime_ledger\|RuntimeLedger(" shared/storage/runtime_ledger.py services/`.)

- [ ] **Step 2: Write `scripts/analysis/llm_scorecard_score.py`** (cron: score yesterday/today's session + send daily):

```python
"""Post-close LLM scorecard scorer + daily Telegram (cron)."""
import asyncio, logging
from datetime import datetime
from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.scorer import score_day
from shared.llm_scorecard.aggregator import rolling_metrics
from shared.llm_scorecard.reporter import format_daily
from shared.llm_scorecard.outcome_data import OutcomeData
from shared.storage.runtime_ledger import get_runtime_ledger
from shared.storage.market_data_store import get_market_data_store  # confirm accessor
logging.basicConfig(level=logging.INFO); log = logging.getLogger(__name__)

async def main():
    cfg = ScorecardConfig.from_yaml()
    ledger = get_runtime_ledger()
    now = datetime.now(); date_kst = now.strftime("%Y-%m-%d")
    outcome = OutcomeData(get_market_data_store(), now_kst=now)
    n = score_day(date_kst, cfg, ledger, outcome)
    log.info("scored %d facets for %s", n, date_kst)
    if cfg.report_daily:
        day = ledger.query_scores(start=date_kst, end=date_kst)
        roll = rolling_metrics(ledger.query_scores(facet="direction"), cfg.rolling_windows[-1])
        from shared.notification import notifier_for_domain
        notifier = notifier_for_domain(cfg.telegram_domain, notification_start="00:00", notification_end="23:59")
        if notifier and day:
            await notifier.send_message(format_daily(date_kst, day, roll), is_critical=False)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Write `test_score_entry.py`** — import the module, call `score_day` with fakes (the entry's `main` is glue; test the seam via `score_day` already covered — here assert the module imports and `format_daily` is wired). Keep it a smoke test (no live I/O).

- [ ] **Step 4: Add cron** to `deploy/scheduler.crontab` (post-close, after EOD backfill settles; KST). Pick an off-:00 minute:

```cron
7 16 * * 1-5  cd /app && python -m scripts.analysis.llm_scorecard_score >> /app/logs/scorecard_$(date +\%Y\%m\%d).log 2>&1
```

- [ ] **Step 5: Run the suite; full 2-pass; commit.** Deploy note: scheduler.crontab is baked → rebuild scheduler image; the briefing runs in the scheduler too.

---

## Phase 3 — Remaining reference facets

### Task 10: ThemesFacet

**Files:** Create `shared/llm_scorecard/facets/themes.py`; Test `tests/unit/llm_scorecard/test_themes_facet.py`. Register `"themes"`. Add `"themes"` to `enabled_facets` in `config/llm_scorecard.yaml` and to the recorder/scorer imports.

**Interfaces:** Consumes `MarketContext.sector_rotation` (dict theme→bias) + a theme→symbols map (param `facet_params.themes.theme_symbols` OR an existing sector/screener tagging — confirm source). Outcome: each theme's equal-weight constituent `session_return`; `value` = mean(strong-theme returns) − market mean; `baseline` = market mean (≈ random theme); `edge` = spread.

- [ ] **Step 1: Failing test** — capture top-N strong themes from `sector_rotation`; score spread with a fake OutcomeData returning per-symbol returns; assert `correct = spread>0`, `value=spread`, unscorable when no constituent data.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `ThemesFacet.capture` (rank `sector_rotation` to top_n strong themes + attach constituent symbols from the map) and `.score` (equal-weight return per theme via `mkt.session_return`, skip themes with no data; spread = strong mean − market mean; if zero scorable themes → `correct=None`).
- [ ] **Step 4: Run → pass; commit.**

(Confirm the theme→symbols source first: `grep -rn "sector\|theme" shared/screener/ shared/llm/ config/ | grep -i "symbol\|map\|member"`. If none exists, the map lives in `config/llm_scorecard.yaml::facet_params.themes.theme_symbols` and the plan stays config-driven.)

### Task 11: MoversFacet

**Files:** Create `shared/llm_scorecard/facets/movers.py`; Test `tests/unit/llm_scorecard/test_movers_facet.py`. Register `"movers"`; enable in config.

**Interfaces:** Consumes the screener pre-market flagged movers (from `ctx.screener` — populate it from `system:trade_targets:latest` / the screener Redis output at capture time) each with implied direction (long). Outcome: per-symbol `session_return` in the flagged direction. `value` = mean follow-through return; `correct` = follow-through rate > base-rate; `economic_proxy` = mean entry PnL; `baseline` = unconditional base-rate follow-through (param `facet_params.movers.base_rate`, default 0.5 of universe — or computed from universe sample).

- [ ] Steps 1–4 mirror Task 5/10 TDD shape: failing test (flagged movers + fake returns → follow-through rate + edge; unscorable on no data) → implement capture (read flagged movers from `ctx.screener`) + score → pass → commit.

### Task 12: VolumeSurgeFacet

**Files:** Create `shared/llm_scorecard/facets/volume_surge.py`; Test `tests/unit/llm_scorecard/test_volume_surge_facet.py`. Register `"volume_surge"`; enable in config.

**Interfaces:** Consumes early-session volume-surge flags (symbol, flag time, flag price) from `ctx.screener` (the 급등주 Redis output; capture happens during early session, so this facet's `capture` may be invoked from the screener/intraday path with `captured_at = flag time`). Outcome: return from flag price to close via `mkt.bars_after(symbol, date_kst, flag_time)`. `value` = mean post-flag return; `correct` = continuation rate > baseline; `economic_proxy` = flag-entry PnL; `baseline` = random-entry intraday move (param).

- [ ] Steps 1–4 mirror the TDD shape: failing test (flag + fake post-flag bars → continuation return + edge; unscorable on no data) → implement → pass → commit.
- [ ] Add a second capture hook in the screener/intraday path (best-effort, same pattern as Task 9 Step 1) so volume-surge flags are recorded at flag time. Confirm the screener entry: `grep -rn "volume_surge\|급등\|surge" shared/screener/ services/ | head`.

---

## Phase 4 — Weekly digest + calibration

### Task 13: Weekly digest cron

**Files:** Create `scripts/analysis/llm_scorecard_weekly.py`; add weekly cron to `deploy/scheduler.crontab`; Test `tests/unit/llm_scorecard/test_weekly_entry.py` (smoke).

**Interfaces:** For each enabled facet, `rolling_metrics(ledger.query_scores(facet), window)` over the largest configured window → `format_weekly(window, by_facet)` → Telegram BRIEFING.

- [ ] **Step 1:** Implement the entry (loop facets → rolling_metrics → format_weekly → send). Mirror Task 9's entry structure.
- [ ] **Step 2:** Cron (weekly, e.g. Friday post-close, off-:00 KST): `17 16 * * 5 cd /app && python -m scripts.analysis.llm_scorecard_weekly >> ...`.
- [ ] **Step 3:** Smoke test imports + a `format_weekly` assertion with synthetic by_facet. Commit.

### Task 14: Calibration in the weekly digest

**Files:** Modify `shared/llm_scorecard/reporter.py` (append calibration section), `scripts/analysis/llm_scorecard_weekly.py`; extend `tests/unit/llm_scorecard/test_reporter.py`.

**Interfaces:** Consumes `calibration_bins(scores, pred_conf)` (Task 7). The weekly entry builds `pred_conf` = `{date_kst: confidence}` from `ledger.load_predictions` per day (or a new `query_predictions(facet, start, end)` accessor — add it mirroring `query_scores` if absent).

- [ ] **Step 1:** Failing test: `format_weekly` (or a new `format_calibration`) renders bins as "conf 0.8–1.0: hit 70% (n=12)".
- [ ] **Step 2:** Implement `format_calibration(bins) -> str`; call it from the weekly entry for confidence-carrying facets (direction).
- [ ] **Step 3:** Run → pass; commit.

---

## Self-Review

**Spec coverage:** capture (T6,T9), score (T5,T7,T10-12), aggregate (T7), report daily (T8,T9) + weekly (T13) + calibration (T14); extensible registry (T3); 4 reference facets (T5,T10,T11,T12); ledger+Redis+config (T1,T2); no-look-ahead (T4); baseline/edge (every facet); unscorable=None (T5,T7 tested); best-effort capture (T6 tested). Dashboard = out of scope (spec §Scope). ✓ All spec sections map to a task.

**Placeholder scan:** All code steps contain runnable code. Three explicit "confirm during implementation" notes (concrete ledger class name, `MarketContext` access path on `run_unified_analysis`, theme→symbols source, screener surge entry) are real external-dependency verifications, not placeholders — each names the exact `grep` to resolve it.

**Type consistency:** `FacetPrediction`/`FacetScore`/`CaptureContext` defined in T3 and used identically in T5–T12; `score_day`/`rolling_metrics`/`calibration_bins`/`format_daily`/`format_weekly` signatures consistent across T7/T8/T9/T13/T14; ledger `save_prediction`/`load_predictions`/`save_score`/`query_scores` consistent T2→T6/T7/T9.

**Known dependencies to confirm at implementation start (do not block the plan):**
1. Concrete ledger class + how it's constructed/obtained (`get_runtime_ledger`?) — `grep -n "class .*Ledger\|def get_runtime_ledger" shared/storage/runtime_ledger.py`.
2. How to read the day's `MarketContext` from `run_unified_analysis` (return value vs Redis `trading:*:market_context`).
3. Market data store accessor name (`get_market_data_store`?) + minute-bar index shape.
4. theme→symbols source; screener surge-flag entry point.
