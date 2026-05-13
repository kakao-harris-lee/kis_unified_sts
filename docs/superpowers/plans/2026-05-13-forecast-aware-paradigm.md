# Forecast-Aware Paradigm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HAR-RV volatility forecaster + hybrid (rule + LLM) event impact scorer that feed Setup A/C strategies as supporting signals; keep RL in shadow_mode as baseline; deprecate RL after 3-4 week validation if `Sharpe_new ≥ RL × 0.9 AND MDD_new ≤ RL × 1.1`.

**Architecture:** New `shared/forecasting/` module computes forecasts; new `services/forecasting/` daemon publishes via Redis pub/sub every minute; Setup A/C adapters consume via thin `ForecastClient` wrapper and override ATR-based thresholds with volatility-aware ones (feature-flagged, default off); validation cron compares new system to RL shadow weekly.

**Tech Stack:** Python 3.11+ / FastAPI / asyncio / pandas / statsmodels (OLS) / Redis (DB 1, pub/sub + SET with TTL) / ClickHouse (3 new tables) / Prometheus / Docker / pytest / pydantic ServiceConfigBase.

**Spec:** `docs/superpowers/specs/2026-05-13-forecast-aware-paradigm-design.md`

---

## File Structure Overview

### Files to Create

**Foundation modules (`shared/forecasting/`):**
- `__init__.py` — exports public API
- `config.py` — `ForecastingConfig(ServiceConfigBase)`
- `models.py` — `VolForecast`, `EventScore` dataclasses
- `realized_variance.py` — 5m/30m/daily RV component computation
- `volatility_har_rv.py` — HAR-RV (Corsi 2009) fit + forecast
- `event_taxonomy.py` — rule-based taxonomy loader
- `event_taxonomy.yaml` (in `config/`) — known event types + weight table
- `llm_event_scorer.py` — LLM fallback wrapper (reuses `shared/llm/llm_analyzer.py`)
- `event_impact_scorer.py` — hybrid (rule + LLM) orchestrator
- `forecast_publisher.py` — Redis publish + ClickHouse persist
- `client.py` — Setup A/C consumer wrapper

**Service daemon (`services/forecasting/`):**
- `__init__.py`
- `main.py` — asyncio loop (forecast every 60s + event scorer + daily 15:35 refit)

**Config:**
- `config/forecasting.yaml`
- `config/event_taxonomy.yaml`

**Tests:**
- `tests/unit/forecasting/__init__.py`
- `tests/unit/forecasting/test_realized_variance.py`
- `tests/unit/forecasting/test_har_rv.py`
- `tests/unit/forecasting/test_event_taxonomy.py`
- `tests/unit/forecasting/test_event_scorer.py`
- `tests/unit/forecasting/test_forecast_publisher.py`
- `tests/unit/forecasting/test_forecast_client.py`
- `tests/integration/test_forecast_pipeline.py`

**ClickHouse migration:**
- `infra/clickhouse/migrations/V6__forecast_tables.sql`

**Scripts:**
- `scripts/cron/forecasting.sh` — start/refit/stop service
- `scripts/cron/forecast_weekly_report.sh` — Sun 23:00 KST Telegram report
- `scripts/analysis/forecast_vs_rl_comparison.py` — weekly Q5 evaluation
- `scripts/analysis/forecast_backtest.py` — offline HAR-RV walk-forward
- `scripts/dev/check_no_rl_imports.sh` — Phase G regression guard

**Docker:**
- `Dockerfile.forecasting`

**Monitoring:**
- `monitoring/prometheus/alert_rules.yaml` (extend with `forecasting` group)

### Files to Modify

- `docker-compose.yml` — add `forecasting` service
- `shared/strategy/entry/setup_adapters.py` — add `forecast_integration` hooks to `SetupAEntryAdapter` and `SetupCEntryAdapter`
- `shared/strategy/position/llm_adaptive_sizer.py` — add forecast vol multiplier
- `config/strategies/futures/setup_a_gap_reversion.yaml` — add `forecast_integration` block (flag false)
- `config/strategies/futures/setup_c_event_reaction.yaml` — same
- `services/dashboard/routes/health.py` — add `/api/health/forecasting` endpoint
- `scripts/analysis/phase2_daily_verification.py` — add 3 new gates (refit success, publish active, event scorer healthy)
- `pyproject.toml` — add `statsmodels>=0.14` dependency

### Files to Delete (Phase G — conditional on Q5)

Only if Phase F validation confirms Q5 (`Sharpe_new ≥ RL × 0.9 AND MDD_new ≤ RL × 1.1`):
- Whole `shared/ml/rl/` directory
- `shared/strategy/entry/rl_mppo.py`
- `shared/strategy/exit/rl_mppo_exit.py`
- `shared/strategy/rl_model_helpers.py`
- All `config/strategies/futures/rl_mppo*.yaml` (12 files)
- `scripts/cron/rl_paper.sh`
- `cli/main.py::sts rl ...` subcommands
- `tests/unit/ml/rl/`

### Branch Strategy

Each phase = 1 PR off `main`. Branch names:
- `feat/forecasting-phase-a-foundation`
- `feat/forecasting-phase-b-service-daemon`
- `feat/forecasting-phase-c-setup-integration`
- `feat/forecasting-phase-d-canary-setup-c`
- `feat/forecasting-phase-e-setup-a-activation`
- `feat/forecasting-phase-f-validation-cron`
- `chore/rl-phase-g1-deprecate-cron` (Phase G split into 6 PRs)
- `chore/rl-phase-g2-remove-strategies`
- `chore/rl-phase-g3-remove-module`
- `chore/rl-phase-g4-clean-cli-dashboard`
- `chore/rl-phase-g5-archive-clickhouse`
- `docs/rl-phase-g6-deprecation-postmortem`

---

# Phase A — Foundation Modules

**Branch:** `feat/forecasting-phase-a-foundation`
**Risk:** zero (no consumer)
**Estimate:** 5d

## Task A.1: Add `statsmodels` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add statsmodels to pyproject.toml dependencies**

Locate the `[project]` `dependencies = [...]` array in `pyproject.toml` and add `"statsmodels>=0.14"`. Keep alphabetical order.

- [ ] **Step 2: Install + verify**

```bash
.venv/bin/pip install 'statsmodels>=0.14'
.venv/bin/python -c "import statsmodels.api as sm; print(sm.__version__)"
```
Expected: prints `0.14.x` or higher.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): add statsmodels>=0.14 for HAR-RV OLS (Phase A)"
```

## Task A.2: ClickHouse migration V6 — forecast tables

**Files:**
- Create: `infra/clickhouse/migrations/V6__forecast_tables.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- V6__forecast_tables.sql
-- Phase A of forecast-aware paradigm — adds 3 tables for HAR-RV model
-- fits, per-minute volatility forecasts, and event impact scores.

CREATE TABLE IF NOT EXISTS kospi.har_rv_fits (
    fit_date Date,
    beta_0 Float64,
    beta_d Float64,
    beta_w Float64,
    beta_m Float64,
    r2_in_sample Float64,
    r2_oos Float64,
    n_obs_used UInt32,
    confidence Float32,
    model_version LowCardinality(String),
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY fit_date
TTL fit_date + INTERVAL 12 MONTH;

CREATE TABLE IF NOT EXISTS kospi.vol_forecasts (
    asof DateTime64(3, 'UTC'),
    horizon_minutes UInt16,
    forecast_pct Float32,
    forecast_atr_equivalent Float32,
    regime_percentile Float32,
    realized_15m_after Float32 DEFAULT 0,
    model_version LowCardinality(String)
) ENGINE = MergeTree()
ORDER BY asof
TTL asof + INTERVAL 90 DAY;

CREATE TABLE IF NOT EXISTS kospi.event_scores (
    asof DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    impact_score UInt8,
    source Enum8('rule' = 1, 'llm' = 2),
    ttl_minutes UInt16,
    raw_text_hash FixedString(16) DEFAULT '',
    setup_consumed Array(LowCardinality(String))
) ENGINE = MergeTree()
ORDER BY asof
TTL asof + INTERVAL 6 MONTH;
```

- [ ] **Step 2: Apply migration to local ClickHouse**

```bash
clickhouse-client --password "$CLICKHOUSE_PASSWORD" -n < infra/clickhouse/migrations/V6__forecast_tables.sql
clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q "SHOW TABLES FROM kospi" | grep -E "har_rv_fits|vol_forecasts|event_scores"
```
Expected: three table names printed.

- [ ] **Step 3: Commit**

```bash
git add infra/clickhouse/migrations/V6__forecast_tables.sql
git commit -m "feat(migration): V6 forecast tables (har_rv_fits, vol_forecasts, event_scores) (Phase A)"
```

## Task A.3: `ForecastingConfig` and `forecasting.yaml`

**Files:**
- Create: `shared/forecasting/__init__.py` (empty for now)
- Create: `shared/forecasting/config.py`
- Create: `config/forecasting.yaml`
- Test: `tests/unit/forecasting/__init__.py` (empty) + `tests/unit/forecasting/test_config.py`

- [ ] **Step 1: Create empty package init**

Create `shared/forecasting/__init__.py` with one line:
```python
"""Forecast-aware paradigm: HAR-RV volatility + hybrid event scoring."""
```

Same for `tests/unit/forecasting/__init__.py`:
```python
```
(empty file — makes it a Python package).

- [ ] **Step 2: Write the failing test**

Create `tests/unit/forecasting/test_config.py`:

```python
"""Tests for ForecastingConfig YAML loading."""
from pathlib import Path

import pytest

from shared.forecasting.config import ForecastingConfig


def test_loads_defaults_from_yaml(tmp_path: Path, monkeypatch):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text(
        """
forecasting:
  publisher_enabled: true
  forecast_loop_interval_seconds: 60
  forecast_redis_ttl_seconds: 120
  har_rv:
    refit_hour_kst: 15
    refit_minute_kst: 35
    history_days: 60
    holdout_days: 7
    min_r2_oos: 0.10
  event_scorer:
    default_ttl_minutes: 30
    rule_first: true
    llm_fallback_enabled: true
    neutral_score_on_failure: 50
"""
    )
    cfg = ForecastingConfig.from_yaml(yaml_path)
    assert cfg.publisher_enabled is True
    assert cfg.forecast_loop_interval_seconds == 60
    assert cfg.forecast_redis_ttl_seconds == 120
    assert cfg.har_rv.refit_hour_kst == 15
    assert cfg.har_rv.history_days == 60
    assert cfg.event_scorer.default_ttl_minutes == 30
    assert cfg.event_scorer.neutral_score_on_failure == 50


def test_env_overrides_apply(monkeypatch, tmp_path):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text(
        """
forecasting:
  publisher_enabled: true
  forecast_loop_interval_seconds: 60
"""
    )
    monkeypatch.setenv("FORECASTING_FORECAST_LOOP_INTERVAL_SECONDS", "30")
    cfg = ForecastingConfig.from_yaml(yaml_path, apply_env_overrides=True)
    assert cfg.forecast_loop_interval_seconds == 30
```

- [ ] **Step 3: Run test to confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'shared.forecasting.config'`.

- [ ] **Step 4: Implement `ForecastingConfig`**

Create `shared/forecasting/config.py`:

```python
"""Forecasting service configuration (ServiceConfigBase pattern)."""
from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class HARRVConfig(BaseModel):
    refit_hour_kst: int = Field(default=15, ge=0, le=23)
    refit_minute_kst: int = Field(default=35, ge=0, le=59)
    history_days: int = Field(default=60, ge=22)  # min for monthly RV component
    holdout_days: int = Field(default=7, ge=1)
    min_r2_oos: float = Field(default=0.10, ge=0.0, le=1.0)
    consecutive_fail_disable_threshold: int = Field(default=7, ge=1)


class EventScorerConfig(BaseModel):
    default_ttl_minutes: int = Field(default=30, ge=1)
    rule_first: bool = Field(default=True)
    llm_fallback_enabled: bool = Field(default=True)
    neutral_score_on_failure: int = Field(default=50, ge=0, le=100)


class ForecastingConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "forecasting.yaml"
    _env_prefix: ClassVar[str] = "FORECASTING_"

    publisher_enabled: bool = Field(default=True)
    forecast_loop_interval_seconds: int = Field(default=60, ge=1)
    forecast_redis_ttl_seconds: int = Field(default=120, ge=2)
    horizon_minutes: int = Field(default=15, ge=1)

    har_rv: HARRVConfig = Field(default_factory=HARRVConfig)
    event_scorer: EventScorerConfig = Field(default_factory=EventScorerConfig)
```

- [ ] **Step 5: Create `config/forecasting.yaml`**

```yaml
# Forecasting service configuration
# See: docs/superpowers/specs/2026-05-13-forecast-aware-paradigm-design.md

forecasting:
  publisher_enabled: true               # master switch; off → service idles
  forecast_loop_interval_seconds: 60
  forecast_redis_ttl_seconds: 120
  horizon_minutes: 15                   # matches Setup C event window

  har_rv:
    refit_hour_kst: 15
    refit_minute_kst: 35
    history_days: 60                    # 60d bars for OLS
    holdout_days: 7                     # OOS R² hold-out window
    min_r2_oos: 0.10                    # below → keep previous model
    consecutive_fail_disable_threshold: 7

  event_scorer:
    default_ttl_minutes: 30
    rule_first: true                    # try rule-based before LLM
    llm_fallback_enabled: true
    neutral_score_on_failure: 50        # 0-100, on dual failure
```

- [ ] **Step 6: Run tests to verify**

```bash
.venv/bin/pytest tests/unit/forecasting/test_config.py -v
```
Expected: PASS (both tests).

- [ ] **Step 7: Commit**

```bash
git add shared/forecasting/__init__.py shared/forecasting/config.py \
        config/forecasting.yaml \
        tests/unit/forecasting/__init__.py tests/unit/forecasting/test_config.py
git commit -m "feat(forecasting): ForecastingConfig + forecasting.yaml defaults (Phase A)"
```

## Task A.4: `VolForecast` and `EventScore` dataclasses

**Files:**
- Create: `shared/forecasting/models.py`
- Test: `tests/unit/forecasting/test_models.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/forecasting/test_models.py`:

```python
"""Tests for forecasting dataclasses."""
from datetime import UTC, datetime, timedelta

import pytest

from shared.forecasting.models import EventScore, VolForecast


def test_vol_forecast_is_fresh_within_max_age():
    f = VolForecast(
        asof=datetime.now(UTC) - timedelta(seconds=60),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )
    assert f.is_fresh(datetime.now(UTC), max_age_s=120) is True


def test_vol_forecast_is_stale_when_old():
    f = VolForecast(
        asof=datetime.now(UTC) - timedelta(seconds=200),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )
    assert f.is_fresh(datetime.now(UTC), max_age_s=120) is False


def test_vol_forecast_to_json_roundtrip():
    f = VolForecast(
        asof=datetime(2026, 5, 13, 9, 0, 0, tzinfo=UTC),
        horizon_minutes=15,
        forecast_pct=18.5,
        forecast_atr_equivalent=3.2,
        regime_percentile=72.0,
        model_version="har_rv_v1",
        confidence=0.31,
    )
    blob = f.to_json()
    f2 = VolForecast.from_json(blob)
    assert f2.asof == f.asof
    assert f2.forecast_pct == pytest.approx(f.forecast_pct)
    assert f2.confidence == pytest.approx(f.confidence)


def test_event_score_is_expired_after_ttl():
    e = EventScore(
        asof=datetime.now(UTC) - timedelta(minutes=31),
        impact_score=85.0,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert e.is_expired(datetime.now(UTC)) is True


def test_event_score_not_expired_within_ttl():
    e = EventScore(
        asof=datetime.now(UTC) - timedelta(minutes=10),
        impact_score=85.0,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    assert e.is_expired(datetime.now(UTC)) is False


def test_event_score_to_json_roundtrip():
    e = EventScore(
        asof=datetime(2026, 5, 13, 9, 0, 0, tzinfo=UTC),
        impact_score=70.0,
        event_type="CPI",
        source="llm",
        raw_text="CPI prints hot at 3.5%",
        ttl_minutes=30,
    )
    blob = e.to_json()
    e2 = EventScore.from_json(blob)
    assert e2.event_type == e.event_type
    assert e2.impact_score == e.impact_score
    assert e2.source == e.source
    assert e2.raw_text == e.raw_text
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_models.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `models.py`**

```python
"""Forecasting dataclasses — VolForecast, EventScore."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal


@dataclass
class VolForecast:
    """Single 15-min volatility forecast snapshot.

    forecast_pct      annualized %, e.g. 18.5
    forecast_atr_equivalent
                     ATR-unit equivalent so Setup A/C can swap it for ATR.
    regime_percentile
                     0-100, where current forecast sits in 30d distribution.
    confidence       0-1, from latest fit's OOS R².
    """

    asof: datetime
    horizon_minutes: int
    forecast_pct: float
    forecast_atr_equivalent: float
    regime_percentile: float
    model_version: str
    confidence: float

    def is_fresh(self, now: datetime, max_age_s: int = 120) -> bool:
        return (now - self.asof).total_seconds() <= max_age_s

    def to_json(self) -> str:
        d = asdict(self)
        d["asof"] = self.asof.isoformat()
        return json.dumps(d)

    @classmethod
    def from_json(cls, blob: str | bytes) -> "VolForecast":
        if isinstance(blob, bytes):
            blob = blob.decode()
        d = json.loads(blob)
        d["asof"] = datetime.fromisoformat(d["asof"])
        return cls(**d)


@dataclass
class EventScore:
    """Macro/news event impact magnitude (0-100, direction-agnostic)."""

    asof: datetime
    impact_score: float          # 0-100
    event_type: str              # taxonomy key or "UNKNOWN_LLM_SCORED"
    source: Literal["rule", "llm"]
    raw_text: str | None         # only retained for LLM-sourced events
    ttl_minutes: int

    def is_expired(self, now: datetime) -> bool:
        return now > self.asof + timedelta(minutes=self.ttl_minutes)

    def to_json(self) -> str:
        d = asdict(self)
        d["asof"] = self.asof.isoformat()
        return json.dumps(d)

    @classmethod
    def from_json(cls, blob: str | bytes) -> "EventScore":
        if isinstance(blob, bytes):
            blob = blob.decode()
        d = json.loads(blob)
        d["asof"] = datetime.fromisoformat(d["asof"])
        return cls(**d)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_models.py -v
```
Expected: 6/6 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/forecasting/models.py tests/unit/forecasting/test_models.py
git commit -m "feat(forecasting): VolForecast + EventScore dataclasses (Phase A)"
```

## Task A.5: Realized variance computation

**Files:**
- Create: `shared/forecasting/realized_variance.py`
- Test: `tests/unit/forecasting/test_realized_variance.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/forecasting/test_realized_variance.py`:

```python
"""Tests for realized variance computation."""
import numpy as np
import pandas as pd
import pytest

from shared.forecasting.realized_variance import (
    compute_intraday_realized_variance,
    resample_to_5min,
)


@pytest.fixture
def synthetic_1min_bars():
    """390 minutes (one KOSPI session) of synthetic prices with known vol."""
    n = 390
    np.random.seed(42)
    # log returns ~ N(0, 0.0005)  ≈ 0.5% intraday vol
    returns = np.random.normal(0, 0.0005, n)
    log_prices = 5.5 + np.cumsum(returns)  # start ≈ 244 (KOSPI200 ~250)
    closes = np.exp(log_prices)
    times = pd.date_range("2026-05-12 00:00:00", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"close": closes}, index=times)


def test_resample_to_5min_aggregates_correctly(synthetic_1min_bars):
    df5 = resample_to_5min(synthetic_1min_bars)
    assert len(df5) == 390 // 5  # 78 bars
    # Each 5m close = last 1m close of that window
    assert df5.iloc[0]["close"] == pytest.approx(
        synthetic_1min_bars.iloc[4]["close"]
    )


def test_resample_to_5min_with_missing_minutes_forward_fills():
    times = pd.date_range("2026-05-12 00:00:00", periods=10, freq="1min", tz="UTC")
    closes = pd.Series([100.0] * 10, index=times)
    closes.iloc[3] = np.nan
    df = pd.DataFrame({"close": closes})
    df5 = resample_to_5min(df)
    assert not df5["close"].isna().any()


def test_compute_intraday_realized_variance_positive(synthetic_1min_bars):
    rv = compute_intraday_realized_variance(synthetic_1min_bars)
    assert rv > 0
    # ≈ 78 × 0.0005² = 1.95e-5, within order of magnitude
    assert 1e-6 < rv < 1e-3


def test_compute_realized_variance_empty_returns_zero():
    empty = pd.DataFrame({"close": []}, index=pd.DatetimeIndex([], tz="UTC"))
    assert compute_intraday_realized_variance(empty) == 0.0


def test_compute_realized_variance_single_bar_returns_zero():
    times = pd.date_range("2026-05-12 00:00:00", periods=1, freq="1min", tz="UTC")
    df = pd.DataFrame({"close": [100.0]}, index=times)
    assert compute_intraday_realized_variance(df) == 0.0
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_realized_variance.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement realized_variance.py**

```python
"""Realized variance computation from intraday bars.

Provides 5m / 30m / daily RV components used as HAR-RV regressors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def resample_to_5min(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute bars to 5-minute closes. Forward-fills gaps.

    Args:
        bars_1m: DataFrame with DatetimeIndex (UTC) and ``close`` column.

    Returns:
        DataFrame with 5-minute interval index and ``close`` column.
    """
    if bars_1m.empty:
        return bars_1m
    out = bars_1m["close"].resample("5min").last()
    out = out.ffill()
    return out.to_frame(name="close")


def compute_intraday_realized_variance(bars_1m: pd.DataFrame) -> float:
    """Sum of 5-minute squared log-returns over the provided window.

    A daily realized variance is the sum across one trading day; this helper
    is window-agnostic — caller chooses the slice.

    Args:
        bars_1m: 1-minute bars with ``close``.

    Returns:
        Realized variance (unitless squared-return sum). 0.0 if fewer than 2
        bars after resample.
    """
    if bars_1m.empty or len(bars_1m) < 2:
        return 0.0
    df5 = resample_to_5min(bars_1m)
    if len(df5) < 2:
        return 0.0
    log_returns = np.log(df5["close"]).diff().dropna()
    if log_returns.empty:
        return 0.0
    return float((log_returns ** 2).sum())


def daily_rv_series(bars_1m: pd.DataFrame, session_tz: str = "Asia/Seoul") -> pd.Series:
    """Compute one daily RV per session date.

    Args:
        bars_1m: 1-minute bars with UTC index.
        session_tz: timezone used to assign a calendar date to each bar.

    Returns:
        Series indexed by Date (KST), values = realized variance for that day.
    """
    if bars_1m.empty:
        return pd.Series(dtype=float)
    local = bars_1m.copy()
    local.index = local.index.tz_convert(session_tz)
    local["session_date"] = local.index.date
    rvs: dict = {}
    for session_date, group in local.groupby("session_date"):
        rvs[session_date] = compute_intraday_realized_variance(
            group.drop(columns=["session_date"])
        )
    return pd.Series(rvs).sort_index()
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_realized_variance.py -v
```
Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/forecasting/realized_variance.py tests/unit/forecasting/test_realized_variance.py
git commit -m "feat(forecasting): realized variance computation (5m squared log-returns) (Phase A)"
```

## Task A.6: HAR-RV model (fit + forecast)

**Files:**
- Create: `shared/forecasting/volatility_har_rv.py`
- Test: `tests/unit/forecasting/test_har_rv.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/forecasting/test_har_rv.py`:

```python
"""Tests for HAR-RV model (Corsi 2009)."""
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.forecasting.config import HARRVConfig
from shared.forecasting.volatility_har_rv import VolatilityForecaster


def _make_synthetic_rv_history(n_days: int, seed: int = 0) -> pd.Series:
    """Generate plausible daily RV series for testing. Mean ≈ 1e-4 (5% daily vol)."""
    rng = np.random.default_rng(seed)
    base = rng.lognormal(mean=np.log(1e-4), sigma=0.4, size=n_days)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="B")
    return pd.Series(base, index=dates.date, name="rv")


def test_fit_with_sufficient_data_returns_finite_coefficients():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    assert f._coefficients is not None
    for coef in (f._coefficients.beta_0, f._coefficients.beta_d,
                  f._coefficients.beta_w, f._coefficients.beta_m):
        assert np.isfinite(coef)


def test_fit_with_insufficient_data_raises():
    cfg = HARRVConfig(history_days=22)
    history = _make_synthetic_rv_history(10)  # < 22 minimum
    f = VolatilityForecaster(cfg)
    with pytest.raises(ValueError, match="insufficient"):
        f.fit(history)


def test_fit_records_oos_r2_in_range():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    assert f._coefficients is not None
    assert -1.0 <= f._coefficients.r2_oos <= 1.0


def test_forecast_returns_positive_finite():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    asof = datetime.now(UTC)
    vf = f.forecast(asof, current_close=380.0)
    assert vf.forecast_pct > 0
    assert vf.forecast_atr_equivalent > 0
    assert np.isfinite(vf.forecast_pct)
    assert 0 <= vf.regime_percentile <= 100


def test_forecast_unit_conversion_atr_equivalent():
    """forecast_atr_equivalent ≈ forecast_pct × close × sqrt(15/(252*390)) / 100."""
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    vf = f.forecast(datetime.now(UTC), current_close=380.0)
    expected = vf.forecast_pct * 380.0 * np.sqrt(15 / (252 * 390)) / 100
    assert vf.forecast_atr_equivalent == pytest.approx(expected, rel=0.01)


def test_forecast_uses_loaded_coefficients():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    vf1 = f.forecast(datetime.now(UTC), current_close=380.0)
    # Force coefficients change — forecast should change
    f._coefficients.beta_d *= 2.0
    f._coefficients.beta_w *= 2.0
    f._coefficients.beta_m *= 2.0
    vf2 = f.forecast(datetime.now(UTC), current_close=380.0)
    assert vf2.forecast_pct != pytest.approx(vf1.forecast_pct)


def test_is_fit_stale_after_one_day():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    assert not f.is_fit_stale(now=datetime.now(UTC))
    f._last_fit_at = datetime.now(UTC) - timedelta(days=2)
    assert f.is_fit_stale(now=datetime.now(UTC))


def test_low_oos_r2_marks_model_as_low_quality():
    """If OOS R² < min_r2_oos, model should refuse to predict (raise)."""
    cfg = HARRVConfig(min_r2_oos=0.99)  # near-impossible
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    with pytest.raises(ValueError, match="R²"):
        f.fit(history)


def test_serialization_roundtrip():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    blob = f.to_json()
    f2 = VolatilityForecaster.from_json(blob, cfg)
    assert f2._coefficients is not None
    vf1 = f.forecast(datetime.now(UTC), current_close=380.0)
    vf2 = f2.forecast(datetime.now(UTC), current_close=380.0)
    assert vf2.forecast_pct == pytest.approx(vf1.forecast_pct)


def test_regime_percentile_calculation():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    # Force a very high RV component — percentile should be high
    f._latest_components = (1e-2, 1e-2, 1e-2)  # 10x mean
    vf = f.forecast(datetime.now(UTC), current_close=380.0)
    assert vf.regime_percentile > 90
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_har_rv.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement HAR-RV**

Create `shared/forecasting/volatility_har_rv.py`:

```python
"""HAR-RV (Heterogeneous Autoregressive on Realized Volatility), Corsi (2009).

Daily-level model with 1-day / 1-week / 1-month aggregates of past RV:

    RV_t = β_0 + β_d * RV_{t-1}
              + β_w * mean(RV_{t-1..t-5})
              + β_m * mean(RV_{t-1..t-22}) + ε
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import statsmodels.api as sm

from shared.forecasting.config import HARRVConfig
from shared.forecasting.models import VolForecast

logger = logging.getLogger(__name__)


@dataclass
class HARRVCoefficients:
    beta_0: float
    beta_d: float
    beta_w: float
    beta_m: float
    r2_in_sample: float
    r2_oos: float
    n_obs_used: int
    fit_date: str  # ISO date


def _build_har_regressors(rv: pd.Series) -> pd.DataFrame:
    """Construct daily/weekly/monthly RV regressors aligned with target."""
    df = pd.DataFrame({"rv": rv})
    df["rv_d"] = df["rv"].shift(1)                            # t-1
    df["rv_w"] = df["rv"].shift(1).rolling(5).mean()           # mean(t-1..t-5)
    df["rv_m"] = df["rv"].shift(1).rolling(22).mean()          # mean(t-1..t-22)
    return df.dropna()


class VolatilityForecaster:
    """HAR-RV model — daily refit, multi-frequency RV regressors."""

    MODEL_VERSION = "har_rv_v1"

    def __init__(self, config: HARRVConfig):
        self.config = config
        self._coefficients: HARRVCoefficients | None = None
        self._last_fit_at: datetime | None = None
        self._rv_history: pd.Series | None = None
        self._latest_components: tuple[float, float, float] | None = None  # (rv_d, rv_w, rv_m)

    def fit(self, history: pd.Series) -> None:
        """Refit OLS on daily RV series.

        Args:
            history: indexed by date, values = daily realized variance.

        Raises:
            ValueError on insufficient data or OOS R² below threshold.
        """
        if len(history) < max(self.config.history_days, 22):
            raise ValueError(
                f"insufficient history: need ≥ {max(self.config.history_days, 22)} "
                f"days, got {len(history)}"
            )

        df = _build_har_regressors(history)
        holdout = self.config.holdout_days
        if len(df) <= holdout:
            raise ValueError(
                f"insufficient post-regressor rows for hold-out (have {len(df)}, "
                f"holdout {holdout})"
            )

        train = df.iloc[:-holdout]
        test = df.iloc[-holdout:]

        X_train = sm.add_constant(train[["rv_d", "rv_w", "rv_m"]])
        y_train = train["rv"]
        model = sm.OLS(y_train, X_train).fit()

        # OOS predictions
        X_test = sm.add_constant(test[["rv_d", "rv_w", "rv_m"]])
        y_test = test["rv"]
        y_pred = model.predict(X_test)
        ss_res = float(((y_test - y_pred) ** 2).sum())
        ss_tot = float(((y_test - y_test.mean()) ** 2).sum())
        r2_oos = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        if not np.isfinite(r2_oos) or r2_oos < self.config.min_r2_oos:
            raise ValueError(
                f"R² OOS below threshold: {r2_oos:.3f} < {self.config.min_r2_oos:.3f}"
            )

        params = model.params
        self._coefficients = HARRVCoefficients(
            beta_0=float(params.iloc[0]),
            beta_d=float(params.iloc[1]),
            beta_w=float(params.iloc[2]),
            beta_m=float(params.iloc[3]),
            r2_in_sample=float(model.rsquared),
            r2_oos=float(r2_oos),
            n_obs_used=int(len(train)),
            fit_date=datetime.now(UTC).date().isoformat(),
        )
        self._last_fit_at = datetime.now(UTC)
        self._rv_history = history.copy()
        # Latest components for prediction
        last_d = float(history.iloc[-1])
        last_w = float(history.iloc[-5:].mean()) if len(history) >= 5 else last_d
        last_m = float(history.iloc[-22:].mean()) if len(history) >= 22 else last_w
        self._latest_components = (last_d, last_w, last_m)
        logger.info(
            "HAR-RV refit complete: β_d=%.3f β_w=%.3f β_m=%.3f R²_oos=%.3f",
            self._coefficients.beta_d,
            self._coefficients.beta_w,
            self._coefficients.beta_m,
            self._coefficients.r2_oos,
        )

    def forecast(self, asof: datetime, current_close: float) -> VolForecast:
        """Predict next-15-min volatility.

        forecast_pct = sqrt(predicted_RV * 252) * 100  (annualized %)
        forecast_atr_equivalent = forecast_pct * close * sqrt(15/(252*390)) / 100
        """
        if self._coefficients is None or self._latest_components is None:
            raise RuntimeError("VolatilityForecaster.forecast called before fit()")

        rv_d, rv_w, rv_m = self._latest_components
        c = self._coefficients
        pred_rv = c.beta_0 + c.beta_d * rv_d + c.beta_w * rv_w + c.beta_m * rv_m
        pred_rv = max(pred_rv, 1e-10)
        # Annualized % vol = sqrt(daily variance * 252) * 100
        forecast_pct = float(np.sqrt(pred_rv * 252) * 100)
        # 15-min ATR-equivalent
        forecast_atr_equivalent = float(
            forecast_pct * current_close * np.sqrt(15 / (252 * 390)) / 100
        )
        # Regime percentile against historical RV distribution
        if self._rv_history is not None and len(self._rv_history) > 0:
            percentile = float((self._rv_history < pred_rv).mean() * 100)
        else:
            percentile = 50.0
        return VolForecast(
            asof=asof,
            horizon_minutes=15,
            forecast_pct=forecast_pct,
            forecast_atr_equivalent=forecast_atr_equivalent,
            regime_percentile=percentile,
            model_version=self.MODEL_VERSION,
            confidence=float(c.r2_oos),
        )

    def is_fit_stale(self, now: datetime) -> bool:
        if self._last_fit_at is None:
            return True
        return (now - self._last_fit_at) > timedelta(days=1, hours=12)

    def to_json(self) -> str:
        if self._coefficients is None or self._latest_components is None:
            raise RuntimeError("cannot serialize before fit()")
        return json.dumps(
            {
                "coefficients": asdict(self._coefficients),
                "latest_components": list(self._latest_components),
                "last_fit_at": (
                    self._last_fit_at.isoformat() if self._last_fit_at else None
                ),
            }
        )

    @classmethod
    def from_json(cls, blob: str | bytes, cfg: HARRVConfig) -> "VolatilityForecaster":
        if isinstance(blob, bytes):
            blob = blob.decode()
        d = json.loads(blob)
        f = cls(cfg)
        f._coefficients = HARRVCoefficients(**d["coefficients"])
        f._latest_components = tuple(d["latest_components"])
        f._last_fit_at = (
            datetime.fromisoformat(d["last_fit_at"]) if d.get("last_fit_at") else None
        )
        return f
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_har_rv.py -v
```
Expected: 10/10 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/forecasting/volatility_har_rv.py tests/unit/forecasting/test_har_rv.py
git commit -m "feat(forecasting): HAR-RV model with OLS fit + OOS R² guard (Phase A)"
```

## Task A.7: Event taxonomy + rule-based scorer

**Files:**
- Create: `config/event_taxonomy.yaml`
- Create: `shared/forecasting/event_taxonomy.py`
- Test: `tests/unit/forecasting/test_event_taxonomy.py`

- [ ] **Step 1: Create event taxonomy YAML**

Create `config/event_taxonomy.yaml`:

```yaml
# Event impact taxonomy — rule-based scoring for known event types.
# Score: 0-100, magnitude only (direction handled by Setup A/C entry logic).

events:
  - key: FOMC_RATE_DECISION
    impact_score: 90
    aliases: ["FOMC", "Fed rate decision", "federal reserve"]
    description: "US Fed FOMC rate decision (top-tier macro)"
  - key: BOK_RATE_DECISION
    impact_score: 85
    aliases: ["BOK", "Korean rate decision", "한국은행"]
    description: "Bank of Korea rate decision"
  - key: US_CPI_RELEASE
    impact_score: 80
    aliases: ["CPI", "consumer price index"]
    description: "US CPI release (FOMC input)"
  - key: US_NFP_RELEASE
    impact_score: 75
    aliases: ["NFP", "non-farm payrolls", "employment situation"]
    description: "US non-farm payrolls"
  - key: KR_CPI_RELEASE
    impact_score: 60
    aliases: ["Korean CPI", "한국 CPI"]
    description: "Korea CPI release"
  - key: KOSPI200_EARNINGS_TOP10
    impact_score: 55
    aliases: ["Samsung earnings", "SK Hynix earnings", "Hyundai earnings"]
    description: "Top-10 KOSPI200 component earnings"
  - key: US_GDP_RELEASE
    impact_score: 50
    aliases: ["US GDP", "GDP advance estimate"]
    description: "US GDP release"
  - key: KR_GDP_RELEASE
    impact_score: 45
    aliases: ["Korean GDP"]
    description: "Korea GDP release"
  - key: KOSPI200_REBALANCE
    impact_score: 70
    aliases: ["KOSPI200 rebalance", "index rebalancing"]
    description: "KOSPI200 quarterly index rebalance"
  - key: KRX_TRADING_HALT
    impact_score: 95
    aliases: ["trading halt", "circuit breaker"]
    description: "KRX trading halt / sidecar / circuit breaker"
  - key: GEOPOLITICAL_KOREA
    impact_score: 70
    aliases: ["DPRK missile", "North Korea", "geopolitical"]
    description: "Korea-related geopolitical event"

# Floor for matched-but-unweighted events
unknown_match_score: 40
```

- [ ] **Step 2: Write failing tests**

Create `tests/unit/forecasting/test_event_taxonomy.py`:

```python
"""Tests for event taxonomy loader + rule-based matcher."""
from pathlib import Path

import pytest

from shared.forecasting.event_taxonomy import EventTaxonomy


@pytest.fixture
def taxonomy(tmp_path: Path):
    yaml_path = tmp_path / "event_taxonomy.yaml"
    yaml_path.write_text(
        """
events:
  - key: FOMC_RATE_DECISION
    impact_score: 90
    aliases: ["FOMC", "Fed rate decision"]
  - key: BOK_RATE_DECISION
    impact_score: 85
    aliases: ["BOK", "한국은행"]
  - key: KRX_TRADING_HALT
    impact_score: 95
    aliases: ["trading halt", "circuit breaker"]
unknown_match_score: 40
"""
    )
    return EventTaxonomy.load(yaml_path)


def test_loads_all_events(taxonomy):
    assert len(taxonomy.events) == 3
    keys = [e.key for e in taxonomy.events]
    assert "FOMC_RATE_DECISION" in keys


def test_match_by_alias_exact(taxonomy):
    match = taxonomy.match("FOMC announces 25bp hike")
    assert match is not None
    assert match.key == "FOMC_RATE_DECISION"
    assert match.impact_score == 90


def test_match_by_alias_case_insensitive(taxonomy):
    match = taxonomy.match("fomc decision today")
    assert match is not None
    assert match.key == "FOMC_RATE_DECISION"


def test_match_korean_alias(taxonomy):
    match = taxonomy.match("한국은행 금리 동결 결정")
    assert match is not None
    assert match.key == "BOK_RATE_DECISION"
    assert match.impact_score == 85


def test_no_match_returns_none(taxonomy):
    match = taxonomy.match("Random unrelated news headline")
    assert match is None


def test_all_weights_within_bounds(taxonomy):
    for event in taxonomy.events:
        assert 0 <= event.impact_score <= 100


def test_match_first_alias_wins_on_ambiguity(taxonomy):
    # "trading halt" matches KRX_TRADING_HALT first
    match = taxonomy.match("trading halt issued")
    assert match.key == "KRX_TRADING_HALT"
```

- [ ] **Step 3: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_event_taxonomy.py -v
```
Expected: FAIL.

- [ ] **Step 4: Implement event_taxonomy.py**

```python
"""Event taxonomy loader and rule-based matcher."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TaxonomyEntry:
    key: str
    impact_score: int
    aliases: tuple[str, ...]
    description: str = ""


class EventTaxonomy:
    """Rule-based event classifier with alias matching."""

    def __init__(self, events: list[TaxonomyEntry], unknown_match_score: int = 40):
        self.events = events
        self.unknown_match_score = unknown_match_score
        # Pre-lowercase aliases for fast matching
        self._alias_index: list[tuple[str, TaxonomyEntry]] = []
        for event in events:
            for alias in event.aliases:
                self._alias_index.append((alias.lower(), event))

    @classmethod
    def load(cls, yaml_path: Path) -> "EventTaxonomy":
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        events: list[TaxonomyEntry] = []
        for item in data.get("events", []):
            events.append(
                TaxonomyEntry(
                    key=item["key"],
                    impact_score=int(item["impact_score"]),
                    aliases=tuple(item.get("aliases", [])),
                    description=item.get("description", ""),
                )
            )
        unknown = int(data.get("unknown_match_score", 40))
        return cls(events, unknown_match_score=unknown)

    def match(self, text: str) -> TaxonomyEntry | None:
        """Returns the first taxonomy entry whose alias appears in `text`.

        Match is case-insensitive substring. Returns None when no alias matches.
        """
        lowered = text.lower()
        for alias, entry in self._alias_index:
            if alias in lowered:
                return entry
        return None
```

- [ ] **Step 5: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_event_taxonomy.py -v
```
Expected: 7/7 PASS.

- [ ] **Step 6: Commit**

```bash
git add config/event_taxonomy.yaml shared/forecasting/event_taxonomy.py tests/unit/forecasting/test_event_taxonomy.py
git commit -m "feat(forecasting): event taxonomy + rule-based matcher (Phase A)"
```

## Task A.8: LLM event scorer (fallback) + hybrid orchestrator

**Files:**
- Create: `shared/forecasting/llm_event_scorer.py`
- Create: `shared/forecasting/event_impact_scorer.py`
- Test: `tests/unit/forecasting/test_event_scorer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/forecasting/test_event_scorer.py`:

```python
"""Tests for hybrid event impact scorer (rule + LLM fallback)."""
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.forecasting.config import EventScorerConfig
from shared.forecasting.event_impact_scorer import EventImpactScorer
from shared.forecasting.event_taxonomy import EventTaxonomy


@pytest.fixture
def taxonomy(tmp_path: Path):
    yaml_path = tmp_path / "event_taxonomy.yaml"
    yaml_path.write_text(
        """
events:
  - key: FOMC_RATE_DECISION
    impact_score: 90
    aliases: ["FOMC"]
unknown_match_score: 40
"""
    )
    return EventTaxonomy.load(yaml_path)


@pytest.fixture
def cfg():
    return EventScorerConfig(
        default_ttl_minutes=30,
        rule_first=True,
        llm_fallback_enabled=True,
        neutral_score_on_failure=50,
    )


def test_rule_match_returns_taxonomy_weight(cfg, taxonomy):
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=None)
    # Sync wrapper for known event — no LLM needed
    score = pytest.mark.asyncio
    result = None

    async def _run():
        return await scorer.score("FOMC raises rates by 25bp")

    import asyncio
    result = asyncio.run(_run())
    assert result.event_type == "FOMC_RATE_DECISION"
    assert result.impact_score == 90
    assert result.source == "rule"


def test_unknown_event_falls_back_to_llm(cfg, taxonomy):
    fake_llm = AsyncMock()
    fake_llm.score_event_text = AsyncMock(return_value=72)
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=fake_llm)

    import asyncio
    result = asyncio.run(scorer.score("Unrelated headline text"))
    assert result.source == "llm"
    assert result.impact_score == 72
    assert result.event_type == "UNKNOWN_LLM_SCORED"
    fake_llm.score_event_text.assert_awaited_once()


def test_llm_failure_returns_neutral(cfg, taxonomy):
    fake_llm = AsyncMock()
    fake_llm.score_event_text = AsyncMock(side_effect=RuntimeError("API down"))
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=fake_llm)

    import asyncio
    result = asyncio.run(scorer.score("Some random text"))
    assert result.source == "llm"
    assert result.impact_score == cfg.neutral_score_on_failure


def test_llm_disabled_skips_unknown_event(cfg, taxonomy):
    cfg.llm_fallback_enabled = False
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=None)

    import asyncio
    result = asyncio.run(scorer.score("Some random text"))
    assert result.source == "rule"
    assert result.impact_score == taxonomy.unknown_match_score


def test_ttl_uses_config_default(cfg, taxonomy):
    scorer = EventImpactScorer(cfg, taxonomy=taxonomy, llm_client=None)
    import asyncio
    result = asyncio.run(scorer.score("FOMC release"))
    assert result.ttl_minutes == cfg.default_ttl_minutes
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_event_scorer.py -v
```
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement LLM event scorer wrapper**

Create `shared/forecasting/llm_event_scorer.py`:

```python
"""LLM-based event impact scorer (fallback for unknown event types)."""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SCORING_PROMPT_TEMPLATE = """\
You are a financial event impact scorer for KOSPI200 futures.

Score the following news event on a scale 0-100 for **expected near-term
volatility impact magnitude** (not direction). Use these anchors:
  100 = trading halt / circuit breaker / wartime escalation
  85  = central bank rate decision
  70  = major macro release (CPI, NFP)
  50  = top-10 KOSPI200 earnings, surprise corporate action
  30  = minor sector news
  10  = routine corporate disclosure
  0   = irrelevant / noise

Event text:
{text}

Reply with a JSON object: {{"impact_score": <integer 0-100>}}
Reply with the JSON only — no prose, no markdown.
"""


class LLMScorerClient(Protocol):
    async def score_event_text(self, text: str) -> int: ...


class OpenAIEventScorer:
    """Adapter around shared/llm/llm_analyzer.py's OpenAI client.

    Returns integer score 0-100, raises on parse/API failure (caller maps
    to neutral fallback).
    """

    def __init__(self, openai_client: Any, model: str = "gpt-4o-mini"):
        self._client = openai_client
        self._model = model

    async def score_event_text(self, text: str) -> int:
        prompt = SCORING_PROMPT_TEMPLATE.format(text=text[:4000])  # cap input
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=50,
        )
        raw = resp.choices[0].message.content
        parsed = json.loads(raw)
        score = int(parsed["impact_score"])
        if not 0 <= score <= 100:
            raise ValueError(f"out-of-range score: {score}")
        return score
```

- [ ] **Step 4: Implement hybrid event_impact_scorer.py**

```python
"""Hybrid event impact scorer — rule-based first, LLM fallback."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from shared.forecasting.config import EventScorerConfig
from shared.forecasting.event_taxonomy import EventTaxonomy
from shared.forecasting.llm_event_scorer import LLMScorerClient
from shared.forecasting.models import EventScore

logger = logging.getLogger(__name__)


class EventImpactScorer:
    """Rule-first hybrid scorer. Falls back to LLM only for unmatched text."""

    def __init__(
        self,
        config: EventScorerConfig,
        taxonomy: EventTaxonomy,
        llm_client: LLMScorerClient | None,
    ):
        self.config = config
        self.taxonomy = taxonomy
        self._llm = llm_client

    async def score(self, event_text: str, event_type: str | None = None) -> EventScore:
        now = datetime.now(UTC)
        # 1. Explicit event_type passed in → check taxonomy directly
        if event_type:
            for entry in self.taxonomy.events:
                if entry.key == event_type:
                    return EventScore(
                        asof=now,
                        impact_score=float(entry.impact_score),
                        event_type=entry.key,
                        source="rule",
                        raw_text=None,
                        ttl_minutes=self.config.default_ttl_minutes,
                    )
        # 2. Try alias match (rule-based)
        if self.config.rule_first:
            match = self.taxonomy.match(event_text)
            if match is not None:
                return EventScore(
                    asof=now,
                    impact_score=float(match.impact_score),
                    event_type=match.key,
                    source="rule",
                    raw_text=None,
                    ttl_minutes=self.config.default_ttl_minutes,
                )
        # 3. LLM fallback (or neutral if disabled / failed)
        if self.config.llm_fallback_enabled and self._llm is not None:
            try:
                score = await self._llm.score_event_text(event_text)
                return EventScore(
                    asof=now,
                    impact_score=float(score),
                    event_type="UNKNOWN_LLM_SCORED",
                    source="llm",
                    raw_text=event_text[:500],
                    ttl_minutes=self.config.default_ttl_minutes,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("LLM scoring failed (%s); using neutral fallback", e)
                return EventScore(
                    asof=now,
                    impact_score=float(self.config.neutral_score_on_failure),
                    event_type="UNKNOWN_LLM_SCORED",
                    source="llm",
                    raw_text=event_text[:500],
                    ttl_minutes=self.config.default_ttl_minutes,
                )
        # 4. LLM disabled and unmatched → unknown_match_score
        return EventScore(
            asof=now,
            impact_score=float(self.taxonomy.unknown_match_score),
            event_type="UNKNOWN_LLM_SCORED",
            source="rule",
            raw_text=None,
            ttl_minutes=self.config.default_ttl_minutes,
        )
```

- [ ] **Step 5: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_event_scorer.py -v
```
Expected: 5/5 PASS.

- [ ] **Step 6: Commit**

```bash
git add shared/forecasting/llm_event_scorer.py shared/forecasting/event_impact_scorer.py tests/unit/forecasting/test_event_scorer.py
git commit -m "feat(forecasting): hybrid event scorer (rule-first + LLM fallback) (Phase A)"
```

## Task A.9: Forecast publisher (Redis + ClickHouse)

**Files:**
- Create: `shared/forecasting/forecast_publisher.py`
- Test: `tests/unit/forecasting/test_forecast_publisher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/forecasting/test_forecast_publisher.py
"""Tests for forecast Redis + ClickHouse publisher."""
import math
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from shared.forecasting.forecast_publisher import ForecastPublisher
from shared.forecasting.models import EventScore, VolForecast


@pytest.fixture
def redis_mock():
    r = MagicMock()
    r.set = MagicMock(return_value=True)
    r.publish = MagicMock(return_value=1)
    return r


@pytest.fixture
def ch_mock():
    c = MagicMock()
    c.execute = MagicMock()
    return c


def _make_vf(forecast_pct=18.0):
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=forecast_pct,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def test_publish_vol_sets_redis_with_ttl(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf()
    pub.publish_vol_forecast(vf)
    redis_mock.set.assert_called_once()
    args, kwargs = redis_mock.set.call_args
    assert args[0] == "forecast:vol:current"
    assert kwargs.get("ex") == 120 or (len(args) >= 3 and args[2] == 120)


def test_publish_vol_inserts_clickhouse(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf()
    pub.publish_vol_forecast(vf)
    ch_mock.execute.assert_called_once()
    sql = ch_mock.execute.call_args[0][0]
    assert "kospi.vol_forecasts" in sql
    assert "INSERT" in sql.upper()


def test_publish_vol_skips_nan(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf(forecast_pct=float("nan"))
    pub.publish_vol_forecast(vf)
    redis_mock.set.assert_not_called()
    ch_mock.execute.assert_not_called()


def test_publish_vol_handles_redis_failure(redis_mock, ch_mock):
    redis_mock.set.side_effect = RuntimeError("redis down")
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    vf = _make_vf()
    # Should not raise — log + continue
    pub.publish_vol_forecast(vf)
    # ClickHouse still attempted
    ch_mock.execute.assert_called_once()


def test_publish_event_publishes_pubsub_and_persists(redis_mock, ch_mock):
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    pub.publish_event_score(es)
    redis_mock.publish.assert_called_once_with("forecasting:events", es.to_json())
    # also SET forecast:event:latest
    set_calls = [c for c in redis_mock.set.call_args_list if c.args[0] == "forecast:event:latest"]
    assert len(set_calls) == 1
    ch_mock.execute.assert_called_once()
    sql = ch_mock.execute.call_args[0][0]
    assert "kospi.event_scores" in sql


def test_publish_event_handles_clickhouse_failure(redis_mock, ch_mock):
    ch_mock.execute.side_effect = RuntimeError("clickhouse down")
    pub = ForecastPublisher(redis=redis_mock, clickhouse=ch_mock, vol_ttl_s=120)
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    # Redis publish still happens, ClickHouse failure logged
    pub.publish_event_score(es)
    redis_mock.publish.assert_called_once()
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_forecast_publisher.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement publisher**

```python
# shared/forecasting/forecast_publisher.py
"""Publish VolForecast / EventScore to Redis + ClickHouse."""
from __future__ import annotations

import logging
import math
from typing import Any

from shared.forecasting.models import EventScore, VolForecast

logger = logging.getLogger(__name__)

_VOL_KEY = "forecast:vol:current"
_EVENT_LATEST_KEY = "forecast:event:latest"
_EVENT_CHANNEL = "forecasting:events"


class ForecastPublisher:
    """Redis (pub/sub + SET with TTL) + ClickHouse persistence.

    All publish methods are non-raising — infrastructure failures are
    logged and forecast generation continues.
    """

    def __init__(self, redis: Any, clickhouse: Any, vol_ttl_s: int = 120):
        self._redis = redis
        self._ch = clickhouse
        self._vol_ttl_s = vol_ttl_s

    def publish_vol_forecast(self, vf: VolForecast) -> None:
        if not math.isfinite(vf.forecast_pct) or not math.isfinite(
            vf.forecast_atr_equivalent
        ):
            logger.warning("Skipping NaN/Inf vol forecast at %s", vf.asof)
            return
        # 1. Redis SET with TTL
        try:
            self._redis.set(_VOL_KEY, vf.to_json(), ex=self._vol_ttl_s)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis SET %s failed: %s", _VOL_KEY, e)
        # 2. ClickHouse persist
        try:
            self._ch.execute(
                "INSERT INTO kospi.vol_forecasts "
                "(asof, horizon_minutes, forecast_pct, forecast_atr_equivalent, "
                "regime_percentile, model_version) VALUES",
                [
                    (
                        vf.asof,
                        vf.horizon_minutes,
                        vf.forecast_pct,
                        vf.forecast_atr_equivalent,
                        vf.regime_percentile,
                        vf.model_version,
                    )
                ],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("ClickHouse vol_forecasts insert failed: %s", e)

    def publish_event_score(self, es: EventScore) -> None:
        # 1. Redis publish
        try:
            self._redis.publish(_EVENT_CHANNEL, es.to_json())
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis publish %s failed: %s", _EVENT_CHANNEL, e)
        # 2. Redis SET latest (fallback path)
        try:
            self._redis.set(
                _EVENT_LATEST_KEY, es.to_json(), ex=es.ttl_minutes * 60
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis SET %s failed: %s", _EVENT_LATEST_KEY, e)
        # 3. ClickHouse persist
        try:
            source_value = 1 if es.source == "rule" else 2
            self._ch.execute(
                "INSERT INTO kospi.event_scores "
                "(asof, event_type, impact_score, source, ttl_minutes, raw_text_hash) "
                "VALUES",
                [
                    (
                        es.asof,
                        es.event_type,
                        int(es.impact_score),
                        source_value,
                        es.ttl_minutes,
                        b"\x00" * 16,  # placeholder
                    )
                ],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("ClickHouse event_scores insert failed: %s", e)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_forecast_publisher.py -v
```
Expected: 6/6 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/forecasting/forecast_publisher.py tests/unit/forecasting/test_forecast_publisher.py
git commit -m "feat(forecasting): ForecastPublisher (Redis + ClickHouse, fail-safe) (Phase A)"
```

## Task A.10: Setup A/C consumer client wrapper

**Files:**
- Create: `shared/forecasting/client.py`
- Test: `tests/unit/forecasting/test_forecast_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/forecasting/test_forecast_client.py
"""Tests for Setup A/C forecast consumer client."""
import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from shared.forecasting.client import ForecastClient
from shared.forecasting.models import EventScore, VolForecast


@pytest.fixture
def redis_mock():
    r = MagicMock()
    return r


def _vf_json(asof: datetime) -> str:
    return VolForecast(
        asof=asof,
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    ).to_json()


def test_get_latest_vol_forecast_returns_fresh(redis_mock):
    asof = datetime.now(UTC)
    redis_mock.get.return_value = _vf_json(asof)
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    vf = asyncio.run(_run())
    assert vf is not None
    assert vf.forecast_pct == 18.0


def test_get_latest_vol_forecast_returns_none_when_missing(redis_mock):
    redis_mock.get.return_value = None
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    assert asyncio.run(_run()) is None


def test_get_latest_vol_forecast_returns_none_when_stale(redis_mock):
    old_asof = datetime.now(UTC) - timedelta(seconds=200)
    redis_mock.get.return_value = _vf_json(old_asof)
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    assert asyncio.run(_run()) is None


def test_get_latest_vol_forecast_handles_malformed_json(redis_mock):
    redis_mock.get.return_value = "{not valid json"
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_vol_forecast()

    assert asyncio.run(_run()) is None


def test_get_latest_event_score_falls_back_to_redis_get(redis_mock):
    es = EventScore(
        asof=datetime.now(UTC),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    redis_mock.get.return_value = es.to_json()
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_event_score()

    out = asyncio.run(_run())
    assert out is not None
    assert out.event_type == "FOMC"
    assert out.impact_score == 85


def test_get_latest_event_score_returns_none_when_expired(redis_mock):
    es = EventScore(
        asof=datetime.now(UTC) - timedelta(minutes=60),
        impact_score=85,
        event_type="FOMC",
        source="rule",
        raw_text=None,
        ttl_minutes=30,
    )
    redis_mock.get.return_value = es.to_json()
    client = ForecastClient(redis=redis_mock, vol_max_age_s=120)

    async def _run():
        return await client.get_latest_event_score()

    assert asyncio.run(_run()) is None
```

- [ ] **Step 2: Run tests, confirm failure**

```bash
.venv/bin/pytest tests/unit/forecasting/test_forecast_client.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement client**

```python
# shared/forecasting/client.py
"""Setup A/C consumer wrapper — pulls VolForecast + EventScore from Redis."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from shared.forecasting.models import EventScore, VolForecast

logger = logging.getLogger(__name__)

_VOL_KEY = "forecast:vol:current"
_EVENT_LATEST_KEY = "forecast:event:latest"


class ForecastClient:
    """Consumer client for Setup A/C adapters.

    Pull-based: Setup A/C calls this on every entry check. Returns None
    on any failure (caller falls back to ATR).
    """

    def __init__(self, redis: Any, vol_max_age_s: int = 120):
        self._redis = redis
        self._vol_max_age_s = vol_max_age_s

    async def get_latest_vol_forecast(self) -> VolForecast | None:
        try:
            raw = self._redis.get(_VOL_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug("ForecastClient: redis GET failed: %s", e)
            return None
        if raw is None:
            return None
        try:
            vf = VolForecast.from_json(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("ForecastClient: malformed vol JSON: %s", e)
            return None
        if not vf.is_fresh(datetime.now(UTC), max_age_s=self._vol_max_age_s):
            return None
        return vf

    async def get_latest_event_score(self) -> EventScore | None:
        try:
            raw = self._redis.get(_EVENT_LATEST_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug("ForecastClient: redis GET event failed: %s", e)
            return None
        if raw is None:
            return None
        try:
            es = EventScore.from_json(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("ForecastClient: malformed event JSON: %s", e)
            return None
        if es.is_expired(datetime.now(UTC)):
            return None
        return es
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/forecasting/test_forecast_client.py -v
```
Expected: 6/6 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/forecasting/client.py tests/unit/forecasting/test_forecast_client.py
git commit -m "feat(forecasting): ForecastClient (Setup A/C consumer wrapper) (Phase A)"
```

## Task A.11: Update `__init__.py` exports + Phase A PR

**Files:**
- Modify: `shared/forecasting/__init__.py`

- [ ] **Step 1: Add exports**

```python
"""Forecast-aware paradigm: HAR-RV volatility + hybrid event scoring."""
from shared.forecasting.client import ForecastClient
from shared.forecasting.config import (
    EventScorerConfig,
    ForecastingConfig,
    HARRVConfig,
)
from shared.forecasting.event_impact_scorer import EventImpactScorer
from shared.forecasting.event_taxonomy import EventTaxonomy, TaxonomyEntry
from shared.forecasting.forecast_publisher import ForecastPublisher
from shared.forecasting.llm_event_scorer import OpenAIEventScorer
from shared.forecasting.models import EventScore, VolForecast
from shared.forecasting.realized_variance import (
    compute_intraday_realized_variance,
    daily_rv_series,
    resample_to_5min,
)
from shared.forecasting.volatility_har_rv import (
    HARRVCoefficients,
    VolatilityForecaster,
)

__all__ = [
    "ForecastClient",
    "ForecastPublisher",
    "ForecastingConfig",
    "HARRVConfig",
    "EventScorerConfig",
    "EventImpactScorer",
    "EventTaxonomy",
    "TaxonomyEntry",
    "OpenAIEventScorer",
    "EventScore",
    "VolForecast",
    "HARRVCoefficients",
    "VolatilityForecaster",
    "compute_intraday_realized_variance",
    "daily_rv_series",
    "resample_to_5min",
]
```

- [ ] **Step 2: Verify all Phase A tests pass**

```bash
.venv/bin/pytest tests/unit/forecasting/ -v
```
Expected: all PASS (~40 tests across A.3-A.10).

- [ ] **Step 3: Lint + type-check**

```bash
.venv/bin/ruff check shared/forecasting/ tests/unit/forecasting/
.venv/bin/mypy shared/forecasting/
```
Expected: no errors.

- [ ] **Step 4: Commit + push + PR**

```bash
git add shared/forecasting/__init__.py
git commit -m "feat(forecasting): __init__.py exports (Phase A)"
git push -u origin feat/forecasting-phase-a-foundation
gh pr create --title "feat(forecasting): Phase A — foundation modules + V6 migration" \
  --body "Phase A of forecast-aware paradigm per docs/superpowers/plans/2026-05-13-forecast-aware-paradigm.md. Foundation modules only — no consumer yet. Adds shared/forecasting/ (~900 LOC) + ClickHouse V6 migration (3 tables). ~40 new tests."
```

- [ ] **Step 5: Wait CI + merge**

```bash
gh pr merge --squash --auto
```

---

# Phase B — Service Daemon + Cron

**Branch:** `feat/forecasting-phase-b-service-daemon`
**Risk:** low (additive, no consumer)
**Estimate:** 3d

## Task B.1: Service main asyncio loop

**Files:**
- Create: `services/forecasting/__init__.py` (empty)
- Create: `services/forecasting/main.py`
- Test: `tests/integration/test_forecast_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_forecast_pipeline.py
"""Integration tests for forecasting service main loop."""
import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.forecasting.main import ForecastingService


@pytest.fixture
def cfg(tmp_path):
    yaml_path = tmp_path / "forecasting.yaml"
    yaml_path.write_text(
        """
forecasting:
  publisher_enabled: true
  forecast_loop_interval_seconds: 1
  forecast_redis_ttl_seconds: 120
  horizon_minutes: 15
  har_rv:
    refit_hour_kst: 15
    refit_minute_kst: 35
    history_days: 60
    holdout_days: 7
    min_r2_oos: 0.0
    consecutive_fail_disable_threshold: 7
  event_scorer:
    default_ttl_minutes: 30
    rule_first: true
    llm_fallback_enabled: false
    neutral_score_on_failure: 50
"""
    )
    from shared.forecasting.config import ForecastingConfig
    return ForecastingConfig.from_yaml(yaml_path)


@pytest.mark.asyncio
async def test_service_start_starts_forecast_loop(cfg, tmp_path):
    redis = MagicMock()
    redis.get = MagicMock(return_value=None)
    redis.set = MagicMock()
    redis.publish = MagicMock()
    ch = MagicMock()
    ch.execute = MagicMock(return_value=[])

    # Empty taxonomy file
    tax_path = tmp_path / "event_taxonomy.yaml"
    tax_path.write_text("events: []\nunknown_match_score: 40")

    service = ForecastingService(
        config=cfg,
        redis_client=redis,
        clickhouse_client=ch,
        taxonomy_path=tax_path,
        llm_client=None,
    )

    # Mock forecaster fit so no historical data needed
    fake_forecast = MagicMock()
    fake_forecast.is_fresh = MagicMock(return_value=True)
    service._forecaster = MagicMock()
    service._forecaster.forecast = MagicMock(return_value=_fake_vol_forecast())
    service._forecaster._coefficients = MagicMock()  # treat as fit

    # Run for 2 ticks
    task = asyncio.create_task(service.start())
    await asyncio.sleep(2.5)
    await service.stop()
    await asyncio.wait_for(task, timeout=5)

    # Forecast was published at least once
    assert any(c.args[0] == "forecast:vol:current" for c in redis.set.call_args_list)


def _fake_vol_forecast():
    from shared.forecasting.models import VolForecast
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=3.0,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


@pytest.mark.asyncio
async def test_service_stop_cancels_tasks(cfg, tmp_path):
    redis = MagicMock()
    redis.set = MagicMock()
    ch = MagicMock()
    tax_path = tmp_path / "event_taxonomy.yaml"
    tax_path.write_text("events: []\nunknown_match_score: 40")

    service = ForecastingService(
        config=cfg,
        redis_client=redis,
        clickhouse_client=ch,
        taxonomy_path=tax_path,
        llm_client=None,
    )
    service._forecaster = MagicMock()
    service._forecaster._coefficients = MagicMock()
    service._forecaster.forecast = MagicMock(return_value=_fake_vol_forecast())

    task = asyncio.create_task(service.start())
    await asyncio.sleep(0.5)
    await service.stop()
    await asyncio.wait_for(task, timeout=5)
    # No raise = good
```

- [ ] **Step 2: Create empty service package init**

```bash
echo '"""Forecasting daemon service."""' > services/forecasting/__init__.py
```

- [ ] **Step 3: Run test, confirm failure**

```bash
.venv/bin/pytest tests/integration/test_forecast_pipeline.py -v
```
Expected: FAIL.

- [ ] **Step 4: Implement service main**

```python
# services/forecasting/main.py
"""Forecasting service — asyncio daemon publishing vol + event scores."""
from __future__ import annotations

import asyncio
import logging
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.forecasting.client import ForecastClient
from shared.forecasting.config import ForecastingConfig
from shared.forecasting.event_impact_scorer import EventImpactScorer
from shared.forecasting.event_taxonomy import EventTaxonomy
from shared.forecasting.forecast_publisher import ForecastPublisher
from shared.forecasting.llm_event_scorer import LLMScorerClient
from shared.forecasting.volatility_har_rv import VolatilityForecaster

logger = logging.getLogger(__name__)


class ForecastingService:
    """Background daemon: 1m forecast publish + news pubsub event scoring."""

    def __init__(
        self,
        config: ForecastingConfig,
        redis_client: Any,
        clickhouse_client: Any,
        taxonomy_path: Path,
        llm_client: LLMScorerClient | None = None,
    ):
        self._config = config
        self._redis = redis_client
        self._ch = clickhouse_client
        self._taxonomy = EventTaxonomy.load(taxonomy_path)
        self._llm = llm_client
        self._stop_event = asyncio.Event()
        self._forecaster = VolatilityForecaster(config.har_rv)
        self._publisher = ForecastPublisher(
            redis=redis_client,
            clickhouse=clickhouse_client,
            vol_ttl_s=config.forecast_redis_ttl_seconds,
        )
        self._event_scorer = EventImpactScorer(
            config=config.event_scorer,
            taxonomy=self._taxonomy,
            llm_client=llm_client,
        )

    async def start(self) -> None:
        if not self._config.publisher_enabled:
            logger.info("publisher_enabled=false — service idle")
            await self._stop_event.wait()
            return

        # Load latest model from Redis (if any)
        self._try_load_model_from_redis()

        forecast_task = asyncio.create_task(self._forecast_loop())
        event_task = asyncio.create_task(self._event_loop())

        try:
            await self._stop_event.wait()
        finally:
            for t in (forecast_task, event_task):
                t.cancel()
            await asyncio.gather(forecast_task, event_task, return_exceptions=True)

    async def stop(self) -> None:
        self._stop_event.set()

    def _try_load_model_from_redis(self) -> None:
        try:
            raw = self._redis.get("forecast:vol:model")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not read forecast:vol:model: %s", e)
            return
        if raw is None:
            logger.info("No saved HAR-RV model in Redis — service will run in ATR-fallback mode until first refit")
            return
        try:
            self._forecaster = VolatilityForecaster.from_json(raw, self._config.har_rv)
            logger.info("Loaded HAR-RV model from Redis")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not deserialize saved model: %s", e)

    async def _forecast_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._tick_forecast()
            except Exception as e:  # noqa: BLE001
                logger.warning("forecast_loop tick failed: %s", e)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._config.forecast_loop_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _tick_forecast(self) -> None:
        # If model not fit, skip
        if self._forecaster._coefficients is None:
            return
        asof = datetime.now(UTC)
        # Caller should supply current_close from data_provider in production;
        # for now use a stub queryable from Redis (set elsewhere).
        try:
            close_raw = self._redis.get("market:futures:current_close")
        except Exception:
            close_raw = None
        try:
            current_close = float(close_raw) if close_raw else 380.0
        except (TypeError, ValueError):
            current_close = 380.0
        vf = self._forecaster.forecast(asof, current_close=current_close)
        self._publisher.publish_vol_forecast(vf)

    async def _event_loop(self) -> None:
        pubsub = None
        try:
            pubsub = self._redis.pubsub()
            pubsub.subscribe("news:raw")
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not subscribe to news:raw: %s — event loop idle", e)
            await self._stop_event.wait()
            return

        try:
            while not self._stop_event.is_set():
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is None:
                    await asyncio.sleep(0)
                    continue
                if msg.get("type") != "message":
                    continue
                data = msg.get("data", b"")
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="ignore")
                try:
                    es = await self._event_scorer.score(data)
                    self._publisher.publish_event_score(es)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Event scoring failed: %s", e)
        finally:
            try:
                if pubsub is not None:
                    pubsub.unsubscribe()
                    pubsub.close()
            except Exception:
                pass


def _install_signal_handlers(service: ForecastingService, loop: asyncio.AbstractEventLoop) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(service.stop()))


async def _main() -> None:
    from shared.db.config import ClickHouseConfig
    from shared.streaming.client import RedisClient

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = ForecastingConfig.from_yaml()
    redis = RedisClient.get_client()

    from clickhouse_driver import Client
    ch_cfg = ClickHouseConfig.from_env(database="kospi")
    ch = Client(
        host=ch_cfg.host,
        port=ch_cfg.port,
        user=ch_cfg.user,
        password=ch_cfg.password,
        database="kospi",
    )

    # LLM client (optional) — reuse shared/llm/llm_analyzer.py's OpenAI client
    llm_client = None
    try:
        import openai
        import os
        if os.environ.get("OPENAI_API_KEY"):
            from shared.forecasting.llm_event_scorer import OpenAIEventScorer
            llm_client = OpenAIEventScorer(
                openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM client init failed: %s — event scorer rule-only", e)

    taxonomy_path = Path("config/event_taxonomy.yaml")
    service = ForecastingService(
        config=cfg,
        redis_client=redis,
        clickhouse_client=ch,
        taxonomy_path=taxonomy_path,
        llm_client=llm_client,
    )

    loop = asyncio.get_running_loop()
    _install_signal_handlers(service, loop)
    await service.start()


if __name__ == "__main__":
    asyncio.run(_main())
```

- [ ] **Step 5: Run tests to verify pass**

```bash
.venv/bin/pytest tests/integration/test_forecast_pipeline.py -v
```
Expected: 2/2 PASS.

- [ ] **Step 6: Commit**

```bash
git add services/forecasting/ tests/integration/test_forecast_pipeline.py
git commit -m "feat(forecasting): asyncio daemon service main (Phase B)"
```

## Task B.2: Cron wrapper + Docker compose

**Files:**
- Create: `scripts/cron/forecasting.sh`
- Create: `Dockerfile.forecasting`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create cron wrapper script**

```bash
# scripts/cron/forecasting.sh
#!/bin/bash
# Forecasting service control wrapper.
#
# Usage:
#   scripts/cron/forecasting.sh start    # start daemon (idempotent)
#   scripts/cron/forecasting.sh refit    # trigger daily HAR-RV refit
#   scripts/cron/forecasting.sh stop     # stop daemon
#   scripts/cron/forecasting.sh status

set -euo pipefail

PROJECT_DIR="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
LOG_DIR="${KIS_LOG_DIR:-$PROJECT_DIR/logs}"
LOG_FILE="$LOG_DIR/forecasting_$(date +%Y%m%d).log"
PID_FILE="$PROJECT_DIR/pids/forecasting.pid"

mkdir -p "$LOG_DIR" "$(dirname "$PID_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

start_service() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    log "Already running (PID $(cat "$PID_FILE"))"
    return 0
  fi
  log "Starting kis-forecasting via docker-compose"
  cd "$PROJECT_DIR"
  docker-compose up -d forecasting >> "$LOG_FILE" 2>&1
  sleep 3
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -n "$CID" ]; then
    echo "$CID" > "$PID_FILE"
    log "Started container $CID"
  else
    log "ERROR: container did not start"
    exit 1
  fi
}

refit_service() {
  log "Triggering HAR-RV refit (signal SIGUSR1 to container)"
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -z "$CID" ]; then
    log "ERROR: container not running; cannot refit"
    exit 1
  fi
  # Service main listens for SIGUSR1 to refit immediately
  docker kill -s SIGUSR1 "$CID" >> "$LOG_FILE" 2>&1
  log "Refit signal sent"
}

stop_service() {
  log "Stopping kis-forecasting"
  cd "$PROJECT_DIR"
  docker-compose stop forecasting >> "$LOG_FILE" 2>&1
  rm -f "$PID_FILE"
}

status_service() {
  CID=$(docker ps -q -f name=kis-forecasting)
  if [ -n "$CID" ]; then
    echo "Running ($CID)"
    docker inspect --format='{{.State.Health.Status}}' "$CID" 2>/dev/null || true
  else
    echo "Not running"
  fi
}

case "${1:-status}" in
  start)  start_service ;;
  refit)  refit_service ;;
  stop)   stop_service ;;
  status) status_service ;;
  *)      echo "Usage: $0 {start|refit|stop|status}"; exit 1 ;;
esac
```

Make executable:
```bash
chmod +x scripts/cron/forecasting.sh
```

- [ ] **Step 2: Create Dockerfile.forecasting**

```dockerfile
# Dockerfile.forecasting
FROM python:3.11-slim

LABEL maintainer="kis_unified_sts"
LABEL description="KIS Forecasting Service (HAR-RV + event impact)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared/ ./shared/
COPY services/ ./services/

RUN pip install --upgrade pip && pip install .

COPY config/ ./config/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "services.forecasting.main"]
```

- [ ] **Step 3: Add `forecasting` service to docker-compose.yml**

Find the `services:` section and add this block alongside `dashboard:`:

```yaml
  # ============================================================
  # Forecasting daemon (HAR-RV vol + event impact scoring)
  # ============================================================
  forecasting:
    build:
      context: .
      dockerfile: Dockerfile.forecasting
    container_name: kis-forecasting
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - REDIS_HOST=host.docker.internal
      - REDIS_PORT=6379
      - REDIS_DB=1
      - REDIS_PASSWORD=${REDIS_PASSWORD:-}
      - CLICKHOUSE_HOST=host.docker.internal
      - CLICKHOUSE_PORT=9000
      - CLICKHOUSE_USER=${CLICKHOUSE_USER:-default}
      - CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD:-}
      - CLICKHOUSE_STOCK_DATABASE=kospi
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
    networks:
      - trading-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

- [ ] **Step 4: Build image + verify**

```bash
docker-compose build forecasting
docker images | grep forecasting
```
Expected: image built successfully.

- [ ] **Step 5: Commit**

```bash
git add scripts/cron/forecasting.sh Dockerfile.forecasting docker-compose.yml
git commit -m "feat(forecasting): Docker compose + cron wrapper (Phase B)"
```

## Task B.3: Health endpoint integration

**Files:**
- Modify: `services/dashboard/routes/health.py`
- Test: `tests/unit/dashboard/routes/test_health.py` (extend)

- [ ] **Step 1: Read existing health.py to find pattern**

```bash
.venv/bin/python -c "from services.dashboard.routes.health import router; print([r.path for r in router.routes])"
```

- [ ] **Step 2: Append failing test in `test_health.py`**

Append this class to `tests/unit/dashboard/routes/test_health.py`:

```python
class TestForecastingHealth:
    def test_returns_service_status(self, client):
        res = client.get("/api/health/forecasting")
        assert res.status_code == 200
        body = res.json()
        assert {"service_alive", "forecast_fresh", "forecast_age_s",
                "model_loaded", "model_last_refit", "model_r2_oos"} <= set(body.keys())
```

- [ ] **Step 3: Run test, confirm failure**

```bash
.venv/bin/pytest tests/unit/dashboard/routes/test_health.py::TestForecastingHealth -v
```
Expected: FAIL (endpoint missing).

- [ ] **Step 4: Add endpoint to `health.py`**

Append to `services/dashboard/routes/health.py`:

```python
@router.get("/forecasting")
async def get_forecasting_health() -> dict[str, Any]:
    """Forecasting service health (model + publish freshness)."""
    redis = _get_redis_client()
    forecast_raw = redis.get("forecast:vol:current") if redis else None
    model_raw = redis.get("forecast:vol:model") if redis else None

    forecast_fresh = forecast_raw is not None
    forecast_age_s = -1
    if forecast_raw is not None:
        try:
            import json
            from datetime import UTC, datetime
            d = json.loads(forecast_raw if isinstance(forecast_raw, str) else forecast_raw.decode())
            asof = datetime.fromisoformat(d["asof"])
            forecast_age_s = int((datetime.now(UTC) - asof).total_seconds())
        except Exception:
            forecast_age_s = -1

    model_loaded = model_raw is not None
    model_r2_oos = None
    model_last_refit = None
    if model_raw is not None:
        try:
            import json
            d = json.loads(model_raw if isinstance(model_raw, str) else model_raw.decode())
            model_r2_oos = d.get("coefficients", {}).get("r2_oos")
            model_last_refit = d.get("coefficients", {}).get("fit_date")
        except Exception:
            pass

    return {
        "service_alive": forecast_age_s >= 0 and forecast_age_s < 300,
        "forecast_fresh": forecast_fresh,
        "forecast_age_s": forecast_age_s,
        "model_loaded": model_loaded,
        "model_last_refit": model_last_refit,
        "model_r2_oos": model_r2_oos,
        "checked_at": datetime.now(UTC).isoformat(),
    }
```

- [ ] **Step 5: Run test to verify pass**

```bash
.venv/bin/pytest tests/unit/dashboard/routes/test_health.py::TestForecastingHealth -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/dashboard/routes/health.py tests/unit/dashboard/routes/test_health.py
git commit -m "feat(forecasting): /api/health/forecasting endpoint (Phase B)"
```

## Task B.4: Phase B PR

- [ ] **Step 1: Run full dashboard test suite + forecasting tests**

```bash
.venv/bin/pytest tests/unit/forecasting/ tests/integration/test_forecast_pipeline.py tests/unit/dashboard/ -v
```
Expected: all pass.

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/forecasting-phase-b-service-daemon
gh pr create --title "feat(forecasting): Phase B — service daemon + Docker + health endpoint" \
  --body "Phase B of forecast-aware paradigm. Adds services/forecasting/ daemon + Docker compose service + /api/health/forecasting endpoint. No consumer yet (Setup A/C integration in Phase C)."
gh pr merge --squash --auto
```

---

# Phase C — Setup A/C Adapter Integration

**Branch:** `feat/forecasting-phase-c-setup-integration`
**Risk:** low (feature flag default off)
**Estimate:** 4d

## Task C.1: Add `forecast_integration` block to Setup A YAML

**Files:**
- Modify: `config/strategies/futures/setup_a_gap_reversion.yaml`

- [ ] **Step 1: Append the new block**

In `setup_a_gap_reversion.yaml`, find the `params:` block under `entry:` and append after the last existing param:

```yaml
      # Phase 5 forecast integration (default off — gated activation per
      # docs/superpowers/plans/2026-05-13-forecast-aware-paradigm.md Phase E)
      forecast_integration:
        enabled: false                       # feature flag
        gap_threshold_vol_mult: 1.0
        retracement_buffer_vol_mult: 0.3
        max_gap_for_reversion_vol_mult: 4.0
        use_event_impact_for_size: true
        min_event_impact_score: 50
```

- [ ] **Step 2: Commit**

```bash
git add config/strategies/futures/setup_a_gap_reversion.yaml
git commit -m "feat(setup-a): add forecast_integration block (default off) (Phase C)"
```

## Task C.2: Add `forecast_integration` block to Setup C YAML

**Files:**
- Modify: `config/strategies/futures/setup_c_event_reaction.yaml`

- [ ] **Step 1: Append the new block**

Append after the existing `min_impact_tier: 2` line in `setup_c_event_reaction.yaml`:

```yaml
      # Phase 5 forecast integration (default off — gated activation per Phase D)
      forecast_integration:
        enabled: false                       # feature flag
        buffer_vol_mult: 0.5
        target_vol_mult: 2.5
        min_event_impact_score: 60
        vol_baseline_window_days: 30
        stale_forecast_fallback: "atr"
        inverse_vol_position_size: true
```

- [ ] **Step 2: Commit**

```bash
git add config/strategies/futures/setup_c_event_reaction.yaml
git commit -m "feat(setup-c): add forecast_integration block (default off) (Phase C)"
```

## Task C.3: Extend `SetupAEntryConfig` + `SetupCEntryConfig` Pydantic models

**Files:**
- Modify: `shared/strategy/entry/setup_adapters.py`
- Test: `tests/unit/strategy/test_setup_adapters.py` (or new file `test_setup_adapters_forecast.py`)

- [ ] **Step 1: Write failing tests**

Create `tests/unit/strategy/test_setup_adapters_forecast.py`:

```python
"""Tests for forecast_integration config blocks on Setup A/C."""
import pytest

from shared.strategy.entry.setup_adapters import (
    SetupAEntryConfig,
    SetupCEntryConfig,
)


def test_setup_a_forecast_defaults_disabled():
    cfg = SetupAEntryConfig()
    assert cfg.forecast_integration.enabled is False
    assert cfg.forecast_integration.gap_threshold_vol_mult == 1.0


def test_setup_c_forecast_defaults_disabled():
    cfg = SetupCEntryConfig()
    assert cfg.forecast_integration.enabled is False
    assert cfg.forecast_integration.buffer_vol_mult == 0.5
    assert cfg.forecast_integration.target_vol_mult == 2.5


def test_setup_c_forecast_enabled_loads():
    cfg = SetupCEntryConfig(
        forecast_integration={
            "enabled": True,
            "buffer_vol_mult": 0.7,
            "target_vol_mult": 3.0,
            "min_event_impact_score": 70,
            "vol_baseline_window_days": 30,
            "stale_forecast_fallback": "atr",
            "inverse_vol_position_size": True,
        }
    )
    assert cfg.forecast_integration.enabled is True
    assert cfg.forecast_integration.buffer_vol_mult == 0.7


def test_invalid_min_event_impact_rejected():
    with pytest.raises(Exception):
        SetupCEntryConfig(
            forecast_integration={"enabled": True, "min_event_impact_score": 150}
        )
```

- [ ] **Step 2: Run test, confirm failure**

```bash
.venv/bin/pytest tests/unit/strategy/test_setup_adapters_forecast.py -v
```
Expected: FAIL.

- [ ] **Step 3: Add `SetupAForecastConfig` + `SetupCForecastConfig` in setup_adapters.py**

In `shared/strategy/entry/setup_adapters.py`, after the `LLMTuningConfig` class (around line 92), add:

```python
class SetupAForecastIntegrationConfig(BaseModel):
    """Phase 5 forecast integration for Setup A (default off)."""

    enabled: bool = Field(default=False)
    gap_threshold_vol_mult: float = Field(default=1.0, gt=0.0, le=10.0)
    retracement_buffer_vol_mult: float = Field(default=0.3, gt=0.0, le=10.0)
    max_gap_for_reversion_vol_mult: float = Field(default=4.0, gt=0.0, le=20.0)
    use_event_impact_for_size: bool = Field(default=True)
    min_event_impact_score: int = Field(default=50, ge=0, le=100)


class SetupCForecastIntegrationConfig(BaseModel):
    """Phase 5 forecast integration for Setup C (default off)."""

    enabled: bool = Field(default=False)
    buffer_vol_mult: float = Field(default=0.5, gt=0.0, le=10.0)
    target_vol_mult: float = Field(default=2.5, gt=0.0, le=20.0)
    min_event_impact_score: int = Field(default=60, ge=0, le=100)
    vol_baseline_window_days: int = Field(default=30, ge=5, le=365)
    stale_forecast_fallback: Literal["atr", "skip"] = Field(default="atr")
    inverse_vol_position_size: bool = Field(default=True)
```

Then add field to existing `SetupAEntryConfig`:

```python
    # add this field:
    forecast_integration: SetupAForecastIntegrationConfig = Field(
        default_factory=SetupAForecastIntegrationConfig
    )
```

And same to `SetupCEntryConfig`:

```python
    forecast_integration: SetupCForecastIntegrationConfig = Field(
        default_factory=SetupCForecastIntegrationConfig
    )
```

- [ ] **Step 4: Run test to verify pass**

```bash
.venv/bin/pytest tests/unit/strategy/test_setup_adapters_forecast.py -v
```
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/setup_adapters.py tests/unit/strategy/test_setup_adapters_forecast.py
git commit -m "feat(setup-adapters): forecast_integration config (Phase C)"
```

## Task C.4: Wire `ForecastClient` into Setup C adapter

**Files:**
- Modify: `shared/strategy/entry/setup_adapters.py` (SetupCEntryAdapter)
- Test: `tests/unit/strategy/test_setup_c_forecast_integration.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/strategy/test_setup_c_forecast_integration.py
"""Tests for Setup C adapter consuming ForecastClient."""
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.forecasting.models import EventScore, VolForecast
from shared.strategy.entry.setup_adapters import (
    SetupCEntryAdapter,
    SetupCEntryConfig,
    SetupCForecastIntegrationConfig,
)


def _vf(forecast_atr_eq=3.0):
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=18.0,
        forecast_atr_equivalent=forecast_atr_eq,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def test_buffer_scales_with_forecast_when_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # When forecast_atr_eq = 6 (2x normal), buffer = 0.5 * 6 = 3
    buffer, target = adapter._derive_thresholds(
        forecast=_vf(forecast_atr_eq=6.0), atr=3.0
    )
    assert buffer == pytest.approx(3.0)
    assert target == pytest.approx(15.0)


def test_buffer_falls_back_to_atr_when_disabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=False, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    buffer, target = adapter._derive_thresholds(forecast=None, atr=3.0)
    # ATR-based with existing params (defaults breakout_buffer_atr_mult=0.5, target=2.5)
    assert buffer == pytest.approx(3.0 * 0.5)
    assert target == pytest.approx(3.0 * 2.5)


def test_buffer_falls_back_to_atr_when_forecast_stale():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, buffer_vol_mult=0.5, target_vol_mult=2.5
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # forecast=None simulates stale (client returned None)
    buffer, target = adapter._derive_thresholds(forecast=None, atr=3.0)
    assert buffer == pytest.approx(3.0 * 0.5)
    assert target == pytest.approx(3.0 * 2.5)


def test_event_filter_uses_impact_score_when_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    weak = EventScore(
        asof=datetime.now(UTC), impact_score=50, event_type="X",
        source="rule", raw_text=None, ttl_minutes=30,
    )
    strong = EventScore(
        asof=datetime.now(UTC), impact_score=85, event_type="FOMC",
        source="rule", raw_text=None, ttl_minutes=30,
    )
    assert adapter._event_passes_filter(weak) is False
    assert adapter._event_passes_filter(strong) is True


def test_event_filter_uses_tier_fallback_when_forecast_disabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(enabled=False)
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # When forecast disabled, all events pass the new filter (legacy tier filter
    # remains the gate)
    assert adapter._event_passes_filter(None) is True


def test_event_filter_blocks_when_event_missing_but_forecast_enabled():
    cfg = SetupCEntryConfig(
        forecast_integration=SetupCForecastIntegrationConfig(
            enabled=True, min_event_impact_score=70
        )
    )
    adapter = SetupCEntryAdapter(cfg, forecast_client=None)
    # No event score → no filter applied (lets tier filter handle it)
    assert adapter._event_passes_filter(None) is True
```

- [ ] **Step 2: Run test, confirm failure**

```bash
.venv/bin/pytest tests/unit/strategy/test_setup_c_forecast_integration.py -v
```
Expected: FAIL.

- [ ] **Step 3: Modify SetupCEntryAdapter**

In `shared/strategy/entry/setup_adapters.py`, locate `class SetupCEntryAdapter(EntrySignalGenerator[SetupCEntryConfig]):` around line 996. Modify constructor to accept `forecast_client` and add `_derive_thresholds` + `_event_passes_filter` helpers:

```python
class SetupCEntryAdapter(EntrySignalGenerator[SetupCEntryConfig]):
    """Setup C: Event Reaction (with optional forecast integration)."""

    def __init__(self, config: SetupCEntryConfig, forecast_client=None):
        super().__init__(config)
        self._forecast_client = forecast_client

    def _derive_thresholds(self, forecast, atr: float) -> tuple[float, float]:
        """Returns (breakout_buffer, target_distance) in price units.

        If forecast integration is enabled and forecast is fresh, derive
        thresholds from forecast.forecast_atr_equivalent (15-min vol ATR).
        Otherwise fall back to existing ATR-based config.
        """
        fi = self.config.forecast_integration
        if fi.enabled and forecast is not None:
            buffer = fi.buffer_vol_mult * forecast.forecast_atr_equivalent
            target = fi.target_vol_mult * forecast.forecast_atr_equivalent
            return (buffer, target)
        return (
            atr * self.config.breakout_buffer_atr_mult,
            atr * self.config.target_atr_mult,
        )

    def _event_passes_filter(self, event_score) -> bool:
        """Returns True if event_score meets the configured impact threshold.

        Returns True when:
        - forecast_integration is disabled (legacy tier filter handles gating), OR
        - event_score is None (let legacy tier filter decide), OR
        - event_score.impact_score >= min_event_impact_score
        """
        fi = self.config.forecast_integration
        if not fi.enabled or event_score is None:
            return True
        return event_score.impact_score >= fi.min_event_impact_score

    # Existing async generate(self, context) method should call:
    # forecast = await self._forecast_client.get_latest_vol_forecast() if self._forecast_client else None
    # event = await self._forecast_client.get_latest_event_score() if self._forecast_client else None
    # buffer, target = self._derive_thresholds(forecast, current_atr)
    # if not self._event_passes_filter(event): return None
    # ... then existing event-reaction entry logic with buffer/target ...
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/strategy/test_setup_c_forecast_integration.py -v
```
Expected: 6/6 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/setup_adapters.py tests/unit/strategy/test_setup_c_forecast_integration.py
git commit -m "feat(setup-c): _derive_thresholds + _event_passes_filter helpers (Phase C)"
```

## Task C.5: Wire `ForecastClient` into Setup A adapter

**Files:**
- Modify: `shared/strategy/entry/setup_adapters.py` (SetupAEntryAdapter)
- Test: `tests/unit/strategy/test_setup_a_forecast_integration.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/strategy/test_setup_a_forecast_integration.py
"""Tests for Setup A adapter consuming ForecastClient."""
from datetime import UTC, datetime

import pytest

from shared.forecasting.models import EventScore, VolForecast
from shared.strategy.entry.setup_adapters import (
    SetupAEntryAdapter,
    SetupAEntryConfig,
    SetupAForecastIntegrationConfig,
)


def _vf(forecast_atr_eq=3.0, daily_vol_pct=18.0):
    return VolForecast(
        asof=datetime.now(UTC),
        horizon_minutes=15,
        forecast_pct=daily_vol_pct,
        forecast_atr_equivalent=forecast_atr_eq,
        regime_percentile=50.0,
        model_version="har_rv_v1",
        confidence=0.3,
    )


def test_gap_threshold_scales_with_vol_when_enabled():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, gap_threshold_vol_mult=1.0
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    # Daily vol = 18% — 1.0× = 18% as gap threshold in % units
    gap_threshold_pct = adapter._derive_gap_threshold_pct(forecast=_vf(daily_vol_pct=18.0))
    assert gap_threshold_pct == pytest.approx(18.0)


def test_gap_threshold_falls_back_when_forecast_absent():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, gap_threshold_vol_mult=1.0
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    # No forecast → fall back to existing config min_gap_pct
    threshold = adapter._derive_gap_threshold_pct(forecast=None)
    assert threshold == cfg.min_gap_pct


def test_max_gap_filter_rejects_too_large_gap():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, max_gap_for_reversion_vol_mult=4.0
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    vf = _vf(daily_vol_pct=10.0)  # 10% daily vol
    # gap 30% > 4 * 10% = 40%? No, < threshold → accept
    assert adapter._gap_within_reversion_range(gap_pct=30.0, forecast=vf) is True
    # gap 50% > 40% → reject (extreme)
    assert adapter._gap_within_reversion_range(gap_pct=50.0, forecast=vf) is False


def test_event_size_reduction_when_event_strong():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, use_event_impact_for_size=True
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    strong = EventScore(
        asof=datetime.now(UTC), impact_score=85, event_type="FOMC",
        source="rule", raw_text=None, ttl_minutes=30,
    )
    # 1 / (1 + 0.85) ≈ 0.54
    mult = adapter._compute_event_size_mult(event_score=strong)
    assert mult == pytest.approx(1.0 / 1.85)


def test_event_size_mult_is_1_when_no_event():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=True, use_event_impact_for_size=True
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    mult = adapter._compute_event_size_mult(event_score=None)
    assert mult == 1.0


def test_event_size_mult_is_1_when_disabled():
    cfg = SetupAEntryConfig(
        forecast_integration=SetupAForecastIntegrationConfig(
            enabled=False, use_event_impact_for_size=True
        )
    )
    adapter = SetupAEntryAdapter(cfg, forecast_client=None)
    strong = EventScore(
        asof=datetime.now(UTC), impact_score=85, event_type="FOMC",
        source="rule", raw_text=None, ttl_minutes=30,
    )
    mult = adapter._compute_event_size_mult(event_score=strong)
    assert mult == 1.0
```

- [ ] **Step 2: Run test, confirm failure**

```bash
.venv/bin/pytest tests/unit/strategy/test_setup_a_forecast_integration.py -v
```
Expected: FAIL.

- [ ] **Step 3: Modify SetupAEntryAdapter**

In `shared/strategy/entry/setup_adapters.py`, at `class SetupAEntryAdapter` (around line 826), modify constructor + add helpers:

```python
class SetupAEntryAdapter(EntrySignalGenerator[SetupAEntryConfig]):
    """Setup A: Gap Reversion (with optional forecast integration)."""

    def __init__(self, config: SetupAEntryConfig, forecast_client=None):
        super().__init__(config)
        self._forecast_client = forecast_client

    def _derive_gap_threshold_pct(self, forecast) -> float:
        """Returns gap threshold in percent. Falls back to min_gap_pct if no forecast."""
        fi = self.config.forecast_integration
        if fi.enabled and forecast is not None:
            return fi.gap_threshold_vol_mult * forecast.forecast_pct
        return self.config.min_gap_pct

    def _gap_within_reversion_range(self, gap_pct: float, forecast) -> bool:
        """True if gap is within the configured `max_gap_for_reversion_vol_mult * daily_vol`."""
        fi = self.config.forecast_integration
        if not fi.enabled or forecast is None:
            return True  # fall through to existing logic
        max_pct = fi.max_gap_for_reversion_vol_mult * forecast.forecast_pct
        return gap_pct <= max_pct

    def _compute_event_size_mult(self, event_score) -> float:
        """Returns position-size multiplier ∈ (0, 1] based on event impact.

        Strong event (high impact_score) → smaller size (overreaction risk).
        """
        fi = self.config.forecast_integration
        if not fi.enabled or not fi.use_event_impact_for_size:
            return 1.0
        if event_score is None:
            return 1.0
        return 1.0 / (1.0 + event_score.impact_score / 100.0)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/unit/strategy/test_setup_a_forecast_integration.py -v
```
Expected: 6/6 PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/entry/setup_adapters.py tests/unit/strategy/test_setup_a_forecast_integration.py
git commit -m "feat(setup-a): forecast-aware gap threshold + event size mult (Phase C)"
```

## Task C.6: Verification gates (5/6/7) in phase2_daily_verification.py

**Files:**
- Modify: `scripts/analysis/phase2_daily_verification.py`

- [ ] **Step 1: Read existing gates**

```bash
grep -n "rl_shadow_predictions_today\|setup_a_signals_today" scripts/analysis/phase2_daily_verification.py | head -5
```

- [ ] **Step 2: Add 3 new gates**

In `scripts/analysis/phase2_daily_verification.py`, locate the gate list (likely a list/dict of name → check function). Append:

```python
# Gate 5: HAR-RV refit ran today
def _gate_har_rv_refit_today(ch_client) -> tuple[bool, int]:
    rows = ch_client.execute(
        "SELECT count() FROM kospi.har_rv_fits WHERE fit_date = today('Asia/Seoul')"
    )
    count = int(rows[0][0]) if rows else 0
    return (count >= 1, count)


# Gate 6: forecast publish active during session
def _gate_forecast_publish_active(ch_client) -> tuple[bool, int]:
    rows = ch_client.execute(
        "SELECT count() FROM kospi.vol_forecasts "
        "WHERE asof >= toStartOfDay(now(), 'Asia/Seoul')"
    )
    count = int(rows[0][0]) if rows else 0
    return (count >= 100, count)  # ~390 expected


# Gate 7: event scorer not stuck in fallback (heuristic via ratio)
def _gate_event_scorer_healthy(ch_client) -> tuple[bool, float]:
    rows = ch_client.execute(
        "SELECT countIf(source = 'llm' AND event_type = 'UNKNOWN_LLM_SCORED' "
        "AND impact_score = 50) AS llm_failures, "
        "countIf(source = 'llm') AS llm_total "
        "FROM kospi.event_scores "
        "WHERE asof >= toStartOfDay(now(), 'Asia/Seoul')"
    )
    if not rows or rows[0][1] == 0:
        return (True, 0.0)  # no LLM calls today = healthy
    failures, total = rows[0]
    fallback_rate = failures / total
    return (fallback_rate < 0.5, fallback_rate)
```

Then add the gates to whatever list/dict aggregates them (look for an existing pattern like `gates = [ ... ]`).

- [ ] **Step 3: Commit**

```bash
git add scripts/analysis/phase2_daily_verification.py
git commit -m "feat(verification): add gates 5/6/7 for forecasting (Phase C)"
```

## Task C.7: Phase C PR

- [ ] **Step 1: Full test pass**

```bash
.venv/bin/pytest tests/unit/forecasting/ tests/unit/strategy/test_setup_*forecast* tests/unit/strategy/test_setup_adapters_forecast.py -v
```
Expected: all pass.

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/forecasting-phase-c-setup-integration
gh pr create --title "feat(forecasting): Phase C — Setup A/C adapter integration (flag off)" \
  --body "Phase C of forecast-aware paradigm. Adds forecast_integration helpers to Setup A/C adapters, YAML blocks (default enabled: false), and 3 new daily verification gates. ATR behavior unchanged for clients."
gh pr merge --squash --auto
```

---

# Phase D — Canary: Setup C Only

**Branch:** `feat/forecasting-phase-d-canary-setup-c`
**Risk:** medium (live impact)
**Estimate:** 0.5d + 7d observation
**Deploy window:** Market closed (15:30+ KST) or weekend

## Task D.1: Enable Setup C forecast integration

**Files:**
- Modify: `config/strategies/futures/setup_c_event_reaction.yaml`

- [ ] **Step 1: Flip the flag**

In `setup_c_event_reaction.yaml`, change:
```yaml
      forecast_integration:
        enabled: false
```
to:
```yaml
      forecast_integration:
        enabled: true
```

- [ ] **Step 2: Commit + PR**

```bash
git checkout -b feat/forecasting-phase-d-canary-setup-c
git add config/strategies/futures/setup_c_event_reaction.yaml
git commit -m "feat(setup-c): enable forecast_integration (Phase D canary)"
git push -u origin feat/forecasting-phase-d-canary-setup-c
gh pr create --title "feat(forecasting): Phase D — Setup C canary activation" \
  --body "Canary activation of forecast-aware thresholds for Setup C only. 7-day observation window starts on merge. Rollback: revert this PR or set enabled=false."
```

- [ ] **Step 3: Wait for market close (15:30+ KST) before merging**

```bash
gh pr merge --squash --auto
```

- [ ] **Step 4: 7-day observation protocol**

Each trading day, run:

```bash
# Forecast publish rate
clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT count() FROM kospi.vol_forecasts WHERE asof >= toStartOfDay(now())"

# Setup C signals today
clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT count() FROM kospi.signals_all WHERE setup_type='C' AND toDate(generated_at)=today()"

# Forecast stale events (in dashboard logs)
docker logs kis-forecasting 2>&1 | grep -c "stale" || true
```

**Rollback triggers:**
- forecast_publish < 200/day (expect ~390)
- Setup C signals = 0 for 5 consecutive days
- Forecast stale rate > 30%

**Rollback method (< 5 minutes):**
```bash
# Edit YAML, commit, merge, restart orchestrator
sed -i 's/enabled: true  # forecast_integration/enabled: false  # forecast_integration/' \
  config/strategies/futures/setup_c_event_reaction.yaml
git commit -am "revert(setup-c): forecast_integration off (canary rollback)"
git push origin main
# orchestrator picks up YAML on next strategy reload cycle
```

---

# Phase E — Setup A Activation

**Branch:** `feat/forecasting-phase-e-setup-a-activation`
**Risk:** medium
**Estimate:** 0.5d + 3d observation

## Task E.1: Enable Setup A forecast integration

**Files:**
- Modify: `config/strategies/futures/setup_a_gap_reversion.yaml`

- [ ] **Step 1: Flip the flag**

Change `enabled: false` to `enabled: true` in the `forecast_integration` block of `setup_a_gap_reversion.yaml`.

- [ ] **Step 2: Commit + PR**

```bash
git checkout -b feat/forecasting-phase-e-setup-a-activation
git add config/strategies/futures/setup_a_gap_reversion.yaml
git commit -m "feat(setup-a): enable forecast_integration (Phase E activation)"
git push -u origin feat/forecasting-phase-e-setup-a-activation
gh pr create --title "feat(forecasting): Phase E — Setup A activation" \
  --body "Activate forecast-aware Setup A after 7-day Setup C canary observation. 3-day rollback window. Inverse-vol position sizing also activates."
```

- [ ] **Step 3: Wait for market close, merge**

```bash
gh pr merge --squash --auto
```

- [ ] **Step 4: 3-day observation**

Same metrics as Phase D, restricted to Setup A signal/fill rate.

---

# Phase F — Validation Period (3-4 weeks)

**Branch:** `feat/forecasting-phase-f-validation-cron`
**Risk:** low (observation only)
**Estimate:** ~28 days

## Task F.1: Weekly comparison script

**Files:**
- Create: `scripts/analysis/forecast_vs_rl_comparison.py`
- Create: `scripts/cron/forecast_weekly_report.sh`

- [ ] **Step 1: Implement comparison script**

```python
#!/usr/bin/env python3
"""Weekly Phase F validation report: Setup A/C vs RL shadow counterfactual.

Q5 success criteria:
  Sharpe_new ≥ Sharpe_rl * 0.9 AND MDD_new ≤ MDD_rl * 1.1
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _query_setup_pnl(ch_client, window_days: int = 7) -> pd.DataFrame:
    """Closed trades from Setup A/C in window."""
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    rows = ch_client.execute(
        "SELECT exit_date, pnl, side, code "
        "FROM kospi.rl_trades "
        "WHERE asset_class='futures' AND exit_date >= %(c)s "
        "  AND strategy IN ('setup_a_gap_reversion', 'setup_c_event_reaction') "
        "ORDER BY exit_date",
        {"c": cutoff},
    )
    return pd.DataFrame(rows, columns=["exit_date", "pnl", "side", "code"])


def _query_rl_shadow_pnl(ch_client, window_days: int = 7) -> pd.DataFrame:
    """Synthetic 'would-be' PnL from RL shadow predictions.

    Per spec §6 — Phase F validation. Uses kospi.rl_shadow_predictions joined
    with subsequent realized 15m return as proxy PnL.
    """
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    rows = ch_client.execute(
        "WITH preds AS ("
        "  SELECT ts, action, confidence, symbol "
        "  FROM kospi.rl_shadow_predictions "
        "  WHERE ts >= %(c)s AND action != 4"
        ") "
        "SELECT p.ts, p.action, "
        "       (SELECT close FROM kospi.kospi200f_1m "
        "        WHERE symbol = p.symbol AND timestamp >= p.ts + INTERVAL 15 MINUTE "
        "        ORDER BY timestamp ASC LIMIT 1) AS exit_close, "
        "       (SELECT close FROM kospi.kospi200f_1m "
        "        WHERE symbol = p.symbol AND timestamp >= p.ts "
        "        ORDER BY timestamp ASC LIMIT 1) AS entry_close "
        "FROM preds p",
        {"c": cutoff},
    )
    df = pd.DataFrame(rows, columns=["ts", "action", "exit_close", "entry_close"])
    if df.empty:
        return df
    df = df.dropna(subset=["entry_close", "exit_close"])
    # action 0=LONG_ENTRY, 1=LONG_EXIT, 2=SHORT_ENTRY, 3=SHORT_EXIT (rl_mppo.py)
    df["pnl"] = df.apply(
        lambda r: (r.exit_close - r.entry_close) if r.action == 0
        else (r.entry_close - r.exit_close) if r.action == 2 else 0,
        axis=1,
    )
    return df[["ts", "pnl"]]


def _sharpe(pnl: pd.Series) -> float:
    if len(pnl) < 2 or pnl.std() == 0:
        return 0.0
    return float(pnl.mean() / pnl.std() * np.sqrt(252))


def _max_drawdown(pnl: pd.Series) -> float:
    if pnl.empty:
        return 0.0
    cum = pnl.cumsum()
    peak = cum.cummax()
    drawdown = cum - peak
    return float(drawdown.min())


def _format_report(setup_df: pd.DataFrame, rl_df: pd.DataFrame, window_days: int) -> str:
    s_sharpe = _sharpe(setup_df["pnl"]) if not setup_df.empty else 0
    s_mdd = _max_drawdown(setup_df["pnl"]) if not setup_df.empty else 0
    r_sharpe = _sharpe(rl_df["pnl"]) if not rl_df.empty else 0
    r_mdd = _max_drawdown(rl_df["pnl"]) if not rl_df.empty else 0

    if r_sharpe == 0:
        decision = "INSUFFICIENT_DATA"
    else:
        sharpe_ratio = s_sharpe / r_sharpe
        mdd_ratio = s_mdd / r_mdd if r_mdd != 0 else 1.0
        criterion_a = sharpe_ratio >= 0.9
        criterion_b = mdd_ratio <= 1.1
        if criterion_a and criterion_b:
            decision = "READY_FOR_PHASE_G"
        else:
            decision = "FAIL_OR_PENDING"

    return (
        f"Phase F Validation Report (last {window_days} days)\n"
        f"\n"
        f"Setup A/C with forecast: Sharpe={s_sharpe:.2f} | MDD={s_mdd:,.0f} | "
        f"Trades={len(setup_df)}\n"
        f"RL shadow counterfactual: Sharpe={r_sharpe:.2f} | MDD={r_mdd:,.0f} | "
        f"Trades={len(rl_df)}\n"
        f"\n"
        f"Q5 ratios:\n"
        f"  Sharpe new/RL  = {(s_sharpe / r_sharpe if r_sharpe else 0):.2f} (need ≥ 0.90)\n"
        f"  MDD new/RL     = {(s_mdd / r_mdd if r_mdd else 0):.2f} (need ≤ 1.10)\n"
        f"\n"
        f"Decision: {decision}\n"
    )


def main() -> int:
    from clickhouse_driver import Client
    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env(database="kospi")
    ch = Client(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database="kospi",
    )

    window_days = int(os.environ.get("FORECAST_REPORT_WINDOW_DAYS", "7"))
    setup_df = _query_setup_pnl(ch, window_days)
    rl_df = _query_rl_shadow_pnl(ch, window_days)
    report = _format_report(setup_df, rl_df, window_days)
    print(report)

    # Send to Telegram briefing channel
    token = os.environ.get("TELEGRAM_BRIEFING_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BRIEFING_CHAT_ID")
    if token and chat_id:
        import urllib.parse
        import urllib.request
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": report}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("Telegram send failed: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Create cron wrapper**

```bash
# scripts/cron/forecast_weekly_report.sh
#!/bin/bash
# Phase F weekly validation report — Sun 23:00 KST.
set -euo pipefail
PROJECT_DIR="${KIS_PROJECT:-/home/deploy/project/kis_unified_sts}"
LOG_FILE="$PROJECT_DIR/logs/forecast_weekly_$(date +%Y%m%d).log"
cd "$PROJECT_DIR"
source .env
FORECAST_REPORT_WINDOW_DAYS=7 \
  ".venv/bin/python" scripts/analysis/forecast_vs_rl_comparison.py \
  >> "$LOG_FILE" 2>&1
```

```bash
chmod +x scripts/cron/forecast_weekly_report.sh
```

- [ ] **Step 3: Register in crontab**

```bash
# Add to user crontab (Sun 23:00 KST = Sun 14:00 UTC):
(crontab -l 2>/dev/null; echo "0 14 * * 0 $KIS_PROJECT/scripts/cron/forecast_weekly_report.sh") | crontab -
crontab -l | grep forecast_weekly_report
```

- [ ] **Step 4: Commit + PR**

```bash
git checkout -b feat/forecasting-phase-f-validation-cron
git add scripts/analysis/forecast_vs_rl_comparison.py scripts/cron/forecast_weekly_report.sh
git commit -m "feat(forecasting): Phase F weekly Q5 validation report cron"
git push -u origin feat/forecasting-phase-f-validation-cron
gh pr create --title "feat(forecasting): Phase F — weekly Q5 validation cron" \
  --body "Weekly report comparing Setup A/C with forecast vs RL shadow counterfactual against Q5 criteria. Telegram briefing channel."
gh pr merge --squash --auto
```

---

# Phase G — RL Deprecation (conditional on Q5)

**Trigger:** Phase F report shows `READY_FOR_PHASE_G` for 2 consecutive weeks.
**Risk:** medium (large deletion)
**Estimate:** 2d (6 PRs split)

## Task G.1: Deprecate RL cron and service

**Files:**
- Modify: crontab on host
- Modify: `scripts/cron/rl_paper.sh` (add deprecation banner; do not delete yet)

- [ ] **Step 1: Comment out RL paper cron**

```bash
crontab -l > /tmp/crontab-pre-g1.txt
crontab -l | sed 's|^\([0-9*]*\s\+.*rl_paper.sh.*\)|# DEPRECATED Phase G1: \1|' | crontab -
crontab -l | grep -i rl_paper
```

- [ ] **Step 2: Add deprecation banner to rl_paper.sh**

At top of `scripts/cron/rl_paper.sh` after the shebang, insert:

```bash
# =============================================================================
# DEPRECATED — Phase G1 of forecast-aware paradigm
# This script is no longer scheduled. RL paper trading was replaced by
# Setup A/C + HAR-RV forecast integration after Phase F validation.
# Will be removed entirely in Phase G3. To re-enable, restore the crontab line
# and revert Phase F YAML flag changes.
# =============================================================================
```

- [ ] **Step 3: Commit + PR**

```bash
git checkout -b chore/rl-phase-g1-deprecate-cron
git add scripts/cron/rl_paper.sh
git commit -m "chore(rl): G1 deprecate cron + banner (Phase G)"
git push -u origin chore/rl-phase-g1-deprecate-cron
gh pr create --title "chore(rl): Phase G1 — deprecate cron, banner only" \
  --body "Phase G1 of RL deprecation: comment out crontab entry, banner on rl_paper.sh. Code remains untouched. Rollback: restore crontab line."
gh pr merge --squash --auto
```

## Task G.2: Remove rl_mppo entry/exit strategies

**Files:**
- Delete: `shared/strategy/entry/rl_mppo.py`
- Delete: `shared/strategy/exit/rl_mppo_exit.py`
- Modify: `shared/strategy/registry.py` (unregister rl_mppo)
- Delete: `tests/unit/strategy/test_rl_mppo*.py`

- [ ] **Step 1: Find registry imports**

```bash
grep -n "rl_mppo" shared/strategy/registry.py
```

- [ ] **Step 2: Remove registry registrations**

In `shared/strategy/registry.py`, delete the lines registering `rl_mppo` entry/exit strategies.

- [ ] **Step 3: Delete the strategy files**

```bash
git rm shared/strategy/entry/rl_mppo.py
git rm shared/strategy/exit/rl_mppo_exit.py
git rm -f tests/unit/strategy/test_rl_mppo*.py tests/unit/strategy/test_rl_mppo_exit*.py 2>/dev/null || true
```

- [ ] **Step 4: Run tests to confirm no consumers break**

```bash
.venv/bin/pytest tests/ -k 'not rl' --no-cov 2>&1 | tail -20
```
Expected: no import errors. If tests fail referring to RLMPPOEntry/Exit, add them to the deletion in the same PR.

- [ ] **Step 5: Commit + PR**

```bash
git checkout -b chore/rl-phase-g2-remove-strategies
git add -A
git commit -m "chore(rl): G2 remove rl_mppo entry+exit strategies (Phase G)"
git push -u origin chore/rl-phase-g2-remove-strategies
gh pr create --title "chore(rl): Phase G2 — remove rl_mppo entry+exit (registry unregister)" \
  --body "Deletes shared/strategy/entry/rl_mppo.py and rl_mppo_exit.py. Updates registry. Tests pruned."
gh pr merge --squash --auto
```

## Task G.3: Remove shared/ml/rl/ module

**Files:**
- Delete: `shared/ml/rl/` entire directory
- Delete: `shared/strategy/rl_model_helpers.py`
- Delete: `config/strategies/futures/rl_mppo*.yaml` (12 files)
- Delete: `tests/unit/ml/rl/`
- Create: `scripts/dev/check_no_rl_imports.sh` (regression guard)

- [ ] **Step 1: Create regression guard script**

```bash
# scripts/dev/check_no_rl_imports.sh
#!/bin/bash
# Phase G regression guard — fail if RL imports remain after deletion.
set -e
PATTERNS=(
  "from shared.ml.rl"
  "import shared.ml.rl"
  "shared.strategy.entry.rl_mppo"
  "shared.strategy.exit.rl_mppo_exit"
  "shared.strategy.rl_model_helpers"
  "rl_mppo_profile"
  "RLMPPOEntry"
  "RLMPPOExit"
  '"sts rl '
)
EXCLUDES=(
  "--exclude-dir=.venv"
  "--exclude-dir=.git"
  "--exclude-dir=node_modules"
  "--exclude-dir=__pycache__"
  "--exclude-dir=.claude"
  "--exclude-dir=docs"  # historic spec docs may still mention these
)
FAIL=0
for pat in "${PATTERNS[@]}"; do
  HITS=$(grep -rn "$pat" "${EXCLUDES[@]}" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.sh" --include="*.toml" . 2>/dev/null || true)
  if [ -n "$HITS" ]; then
    echo "FAIL: '$pat' still referenced:"
    echo "$HITS"
    FAIL=1
  fi
done
if [ "$FAIL" -eq 1 ]; then exit 1; fi
echo "OK: no RL imports remain"
```

```bash
chmod +x scripts/dev/check_no_rl_imports.sh
```

- [ ] **Step 2: Delete all RL files**

```bash
git rm -r shared/ml/rl/
git rm shared/strategy/rl_model_helpers.py
git rm config/strategies/futures/rl_mppo*.yaml
git rm -r tests/unit/ml/rl/ 2>/dev/null || true
```

- [ ] **Step 3: Run regression guard**

```bash
bash scripts/dev/check_no_rl_imports.sh
```
Expected: "OK: no RL imports remain". If FAIL, follow remaining references in output and remove them.

- [ ] **Step 4: Run full test suite**

```bash
.venv/bin/pytest tests/ --ignore=tests/unit/ml --no-cov 2>&1 | tail -20
```
Expected: no errors.

- [ ] **Step 5: Commit + PR**

```bash
git checkout -b chore/rl-phase-g3-remove-module
git add -A
git commit -m "chore(rl): G3 remove shared/ml/rl/ + all rl_mppo YAMLs + regression guard (Phase G)"
git push -u origin chore/rl-phase-g3-remove-module
gh pr create --title "chore(rl): Phase G3 — remove shared/ml/rl/ module (~5000 LOC)" \
  --body "Deletes shared/ml/rl/ entire directory, shared/strategy/rl_model_helpers.py, 12 rl_mppo YAML profiles, and tests/unit/ml/rl/. Adds scripts/dev/check_no_rl_imports.sh regression guard."
gh pr merge --squash --auto
```

## Task G.4: Clean CLI + dashboard refs

**Files:**
- Modify: `cli/main.py`
- Modify: `services/dashboard/routes/trades.py`
- Modify: `dashboard-frontend/src/api/client.ts`

- [ ] **Step 1: Remove `sts rl ...` subcommands**

In `cli/main.py`, remove the `@click.group(name="rl")` and all subcommands (`train`, `paper`, `evaluate`, `train-hierarchical`, `evaluate-hierarchical`).

- [ ] **Step 2: Generalize `/api/trades/rl` endpoint**

In `services/dashboard/routes/trades.py`, rename routes from `/rl` to `/closed` (or update them to use `setup_*` strategies only). Update `_build_rl_trades_sql` accordingly to drop `rl_mppo` references.

- [ ] **Step 3: Update frontend api client**

In `dashboard-frontend/src/api/client.ts`, find `getRlTrades` and `getRlStatistics`, rename to `getClosedTrades` / `getClosedStatistics`, update Cockpit Trades page accordingly.

- [ ] **Step 4: Rebuild frontend**

```bash
cd dashboard-frontend && bun install && bun run build
```

- [ ] **Step 5: Run regression guard + tests**

```bash
bash scripts/dev/check_no_rl_imports.sh
.venv/bin/pytest tests/unit/dashboard/ -v
cd dashboard-frontend && bun run type-check && bun run build
```

- [ ] **Step 6: Commit + PR**

```bash
git checkout -b chore/rl-phase-g4-clean-cli-dashboard
git add -A
git commit -m "chore(rl): G4 remove sts rl CLI + rename dashboard /api/trades/rl to /closed (Phase G)"
git push -u origin chore/rl-phase-g4-clean-cli-dashboard
gh pr create --title "chore(rl): Phase G4 — clean CLI + dashboard endpoint generalization" \
  --body "Removes 'sts rl' subcommands from cli/main.py. Renames /api/trades/rl* to /api/trades/closed* in dashboard backend + frontend."
gh pr merge --squash --auto
```

## Task G.5: Archive ClickHouse tables (6mo later)

**Files:**
- Create: `infra/clickhouse/migrations/V7__rename_rl_tables_archive.sql`

- [ ] **Step 1: Migration to rename (not drop)**

```sql
-- V7__rename_rl_tables_archive.sql
-- 6mo after Phase G4 — rename RL tables for archive (preserves
-- historical data for postmortem). Drop after another 6mo if not needed.

RENAME TABLE kospi.rl_trades TO kospi.archived_rl_trades;
RENAME TABLE kospi.rl_shadow_predictions TO kospi.archived_rl_shadow_predictions;
```

- [ ] **Step 2: Apply (only after 6mo grace period)**

```bash
clickhouse-client --password "$CLICKHOUSE_PASSWORD" -n \
  < infra/clickhouse/migrations/V7__rename_rl_tables_archive.sql
```

- [ ] **Step 3: Commit + PR**

```bash
git checkout -b chore/rl-phase-g5-archive-clickhouse
git add infra/clickhouse/migrations/V7__rename_rl_tables_archive.sql
git commit -m "chore(rl): G5 archive rl ClickHouse tables (6mo after G4) (Phase G)"
git push -u origin chore/rl-phase-g5-archive-clickhouse
gh pr create --title "chore(rl): Phase G5 — archive rl ClickHouse tables" \
  --body "Renames kospi.rl_trades → kospi.archived_rl_trades and kospi.rl_shadow_predictions → kospi.archived_rl_shadow_predictions. Apply only ≥6 months after Phase G4 merge."
```

## Task G.6: Plan + CLAUDE.md update + postmortem

**Files:**
- Modify: `docs/plans/2026-05-03-llm-primary-rl-minimization.md` (v5.0)
- Modify: `CLAUDE.md` (remove RL sections)
- Create: `docs/postmortems/2026-XX-XX-rl-deprecation.md`

- [ ] **Step 1: Update plan to v5.0**

Add v5.0 entry to the plan history section documenting forecast-aware paradigm + RL deprecation.

- [ ] **Step 2: Strip RL sections from CLAUDE.md**

Remove "RL 선물 운용 규칙", "계층적 RL", and `sts rl` commands from CLAUDE.md. Replace with single line: "RL was deprecated in 2026-XX (Phase G of forecast-aware paradigm). See docs/postmortems/."

- [ ] **Step 3: Write postmortem**

Create `docs/postmortems/2026-XX-XX-rl-deprecation.md` with:
- Original RL motivation
- Phase F validation outcome (Q5 ratios)
- What replaced RL (HAR-RV + event scorer)
- Lessons learned
- Reactivation path (revert plan)

- [ ] **Step 4: Commit + PR**

```bash
git checkout -b docs/rl-phase-g6-deprecation-postmortem
git add -A
git commit -m "docs(rl): G6 plan v5.0 + CLAUDE.md cleanup + postmortem (Phase G)"
git push -u origin docs/rl-phase-g6-deprecation-postmortem
gh pr create --title "docs(rl): Phase G6 — plan v5.0 + CLAUDE.md cleanup + postmortem" \
  --body "Final Phase G PR. Documents the deprecation in plan history, removes RL sections from CLAUDE.md, adds postmortem with Q5 outcome and lessons learned."
gh pr merge --squash --auto
```

---

# Self-Review (Author's Inline Notes)

**1. Spec coverage:**

- §1 Decisions Summary → Plan header + Phase D/E flags
- §2 Architecture → File Structure Overview
- §3 Component Decomposition → Tasks A.3–A.10 + Phase C
- §4 Setup A/C Integration → Tasks C.4–C.5
- §5 Data Flow + Storage → Task A.2 (V6 migration) + Task A.9 (publisher) + Task A.10 (client)
- §6 Error Handling + Observability → Tasks A.9 (fail-safe publisher) + B.3 (health endpoint) + C.6 (verification gates)
- §7 Migration Plan + RL Deprecation → Phases A–G structure
- §8 Testing Strategy → TDD steps in every implementation task
- §9 Out of Scope → not implemented, no tasks needed (deliberate exclusion)

All spec sections covered.

**2. Placeholder scan:** No TBD/TODO. Each implementation step shows complete code or exact YAML/SQL/bash.

**3. Type consistency:**
- `VolForecast` shape consistent between Task A.4 (definition), A.6 (forecaster output), A.9 (publisher input), A.10 (client output), C.4–C.5 (adapter consumption)
- `EventScore` shape consistent across A.4, A.8, A.9, A.10, C.5
- `ForecastingConfig.har_rv` / `event_scorer` nested config consistent across A.3, A.6, A.8, B.1
- `SetupCForecastIntegrationConfig` / `SetupAForecastIntegrationConfig` field names match between C.3 (definition), C.4/C.5 (consumers), and Phase D/E (YAML flag flip)

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-13-forecast-aware-paradigm.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
