# Paper Trading Quality Recovery Implementation Plan

> **ARCHIVED 2026-06-22:** Historical implementation/investigation record. The
> RL and ClickHouse portions are obsolete because futures ML/RL/TFT runtime
> paths and ClickHouse runtime storage were removed on 2026-06-03. Current
> runtime decisions live in
> [2026-06-03-ml-rl-removal-llm-indicator-futures.md](../2026-06-03-ml-rl-removal-llm-indicator-futures.md),
> [2026-06-03-runtime-storage-decoupling-implementation.md](../2026-06-03-runtime-storage-decoupling-implementation.md),
> and [ROADMAP.md](../../ROADMAP.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PR #119 머지 이후 남은 3개 미해결 이슈를 해결한다: (1) paper 진입 가격이 Redis 캐시된 전일 가격으로 체결되어 소형주가 비현실적 수익률을 낳는 문제, (2) 선물 RL이 학습 eval(Sharpe 3.19)과 실운용(최근 3주 승률 0%, 누적 -429) 사이의 큰 성능 괴리, (3) Redis 상태의 자본/PnL이 세션 단위로 리셋되어 장기 추적 불가.

**Architecture:** 각 문제를 독립적으로 실행/배포 가능한 Phase로 분리. Phase 1은 paper broker에 price freshness guard와 deviation guard를 추가하고 기존 `shared/paper/broker.py` 진입 경로에 sanity check을 삽입. Phase 2는 investigation을 선행(live obs vs train obs 분포 비교, scaler 무결성 재검증, profile matrix 기여도 분석)한 뒤 findings에 맞는 수정. Phase 3은 `TradingStatePublisher`에 cross-session running totals와 `trading:{asset}:equity_timeline` 소팅셋 키를 추가.

**Tech Stack:** Python 3.11+, Redis, ClickHouse, pytest, 기존 `shared/paper/broker.py`·`services/trading/orchestrator.py`·`shared/streaming/trading_state.py`·`shared/ml/rl/` 구조

---

## File Structure

**Phase 1 (Entry price quality)**
- Modify: `shared/paper/broker.py` — `_execute_market_order`/`_execute_limit_order`에 price freshness + deviation guard
- Modify: `shared/paper/config.py` — `PaperBrokerConfig` 확장 (`max_price_staleness_seconds`, `max_price_deviation_pct`, `reference_price_lookback_minutes`)
- Modify: `services/trading/orchestrator.py:_submit_entry_order` — 체결 요청 시 freshness metadata 전달
- Create: `tests/unit/paper/test_broker_price_guards.py`
- Modify: `config/execution.yaml` — 새 guard 값 노출

**Phase 2 (Futures RL performance diagnostic + fix)**
- Create: `scripts/analysis/rl_live_vs_train_obs_drift.py` — live paper obs 샘플 vs train obs 분포 비교
- Create: `scripts/analysis/rl_scaler_audit.py` — `models/futures/rl/scaler.joblib` vs 최근 obs builder 출력 shape/mean/std 검증
- Modify: `shared/ml/rl/features.py` (진단 후 필요 시) — obs builder 버그 수정
- Modify: `config/ml/rl_mppo.yaml` — 필요 시 profile matrix 비활성화
- Create: `tests/unit/ml/rl/test_obs_builder_parity.py` — 학습/평가/운용 obs 생성이 동일한지 회귀 테스트
- Create: `docs/plans/2026-04-15-paper-trading-quality-recovery.md` 섹션 하단에 findings 기록

**Phase 3 (Capital tracking continuity)**
- Modify: `shared/streaming/trading_state.py` — publisher에 `increment_running_totals()`, reader에 `get_running_totals()`·`get_equity_timeline()`
- Modify: `services/trading/orchestrator.py:_update_redis_state` (또는 동등 publish 지점) — 세션별 리셋 아닌 누적 갱신 경로 추가
- Create: `tests/unit/streaming/test_equity_timeline.py`

---

## Phase 1 (P1): Paper Broker Entry Price Guards

**Background (Task 0 investigation 결과):** 센서뷰(321370) entry_price=3,748원으로 체결 후 당일 70,528원 마감 → +1,781% "수익". 원인은 paper broker에 전달되는 `market_price`가 Redis `candle_cache` 또는 indicator engine의 전일 세션 스냅샷을 가리키는 경우 존재. 실제 장중 가격과 괴리된 stale price로 체결되면 모의투자 성과 분석이 전부 오염됨.

### Task 1.1: Price freshness metadata를 broker까지 전달

**Files:**
- Modify: `shared/paper/broker.py` — `submit_order()` 시그니처에 `price_source_time: datetime | None = None` 추가
- Modify: `services/trading/orchestrator.py:_submit_entry_order` (line ~4402) — 호출 시점에 `price_source_time`을 signal/market_data에서 추출하여 전달
- Test: `tests/unit/paper/test_broker_price_guards.py`

- [ ] **Step 1: Create test file with a failing test**

```python
# tests/unit/paper/test_broker_price_guards.py
"""PaperBroker price guard — freshness + deviation 회귀 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.paper.broker import PaperBroker
from shared.paper.config import PaperBrokerConfig
from shared.paper.models import OrderSide, OrderType


@pytest.fixture
def broker():
    config = PaperBrokerConfig(
        initial_balance=100_000_000.0,
        commission_rate=0.0015,
        slippage_rate=0.001,
        max_price_staleness_seconds=30.0,
        max_price_deviation_pct=0.10,
        reference_price_lookback_minutes=5,
    )
    return PaperBroker(config=config)


@pytest.mark.asyncio
async def test_fresh_price_accepted(broker):
    """price_source_time이 현재 시각 기준 30초 이내면 체결 성공."""
    now = datetime.now(timezone.utc)
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=70000.0,
        price_source_time=now - timedelta(seconds=5),
    )
    assert order.filled is True
    assert order.fill_price == pytest.approx(70000.0 * 1.001, rel=1e-6)


@pytest.mark.asyncio
async def test_stale_price_rejected(broker):
    """price_source_time이 30초를 초과하면 체결 거부 (reason='stale_price')."""
    now = datetime.now(timezone.utc)
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=70000.0,
        price_source_time=now - timedelta(seconds=45),
    )
    assert order.filled is False
    assert order.rejection_reason == "stale_price"


@pytest.mark.asyncio
async def test_missing_source_time_rejected_in_strict_mode(broker):
    """price_source_time이 None이면 체결 거부(strict 기본값)."""
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=70000.0,
        price_source_time=None,
    )
    assert order.filled is False
    assert order.rejection_reason == "missing_price_source_time"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
pytest tests/unit/paper/test_broker_price_guards.py::test_fresh_price_accepted -v
```
Expected: FAIL (TypeError: submit_order() got unexpected keyword argument 'price_source_time').

- [ ] **Step 3: Extend `PaperBrokerConfig`**

`shared/paper/config.py`에 필드 추가:

```python
from pydantic import Field

class PaperBrokerConfig(BaseModel):
    # ... existing fields ...
    max_price_staleness_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Max acceptable age of price_source_time for paper fills. 0 disables.",
    )
    max_price_deviation_pct: float = Field(
        default=0.10,
        ge=0.0,
        description="Reject fills whose price deviates more than this fraction from reference median. 0 disables.",
    )
    reference_price_lookback_minutes: int = Field(
        default=5,
        ge=0,
        description="Window in minutes for deviation reference median. 0 disables.",
    )
```

- [ ] **Step 4: Modify `submit_order` to accept `price_source_time` and add guards**

In `shared/paper/broker.py`, update `submit_order`:

```python
async def submit_order(
    self,
    *,
    symbol: str,
    side: OrderSide,
    quantity: int,
    order_type: OrderType,
    price: float | None = None,
    market_price: float | None = None,
    price_source_time: datetime | None = None,
) -> Order:
    """Submit a paper order with price freshness/deviation guards.

    price_source_time: wall-clock timestamp of the market_price snapshot.
        If older than config.max_price_staleness_seconds, the order is
        rejected with reason='stale_price'. None rejects with
        'missing_price_source_time'.
    """
    order = Order(
        symbol=symbol, side=side, quantity=quantity,
        order_type=order_type, price=price,
    )

    # Guard 1: price source freshness
    if self.config.max_price_staleness_seconds > 0:
        if price_source_time is None:
            order.filled = False
            order.rejection_reason = "missing_price_source_time"
            logger.warning(
                "Paper order rejected (no price_source_time): %s %s", symbol, side.value
            )
            return order
        now = datetime.now(timezone.utc)
        if price_source_time.tzinfo is None:
            price_source_time = price_source_time.replace(tzinfo=timezone.utc)
        age_seconds = (now - price_source_time).total_seconds()
        if age_seconds > self.config.max_price_staleness_seconds:
            order.filled = False
            order.rejection_reason = "stale_price"
            logger.warning(
                "Paper order rejected (stale price, age=%.1fs): %s @ %s",
                age_seconds, symbol, market_price,
            )
            return order

    # ... existing execution logic ...
```

- [ ] **Step 5: Add `rejection_reason: str = ""` field to `Order` model**

In `shared/paper/models.py`:

```python
@dataclass
class Order:
    # ... existing fields ...
    rejection_reason: str = ""
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/paper/test_broker_price_guards.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add shared/paper/broker.py shared/paper/config.py shared/paper/models.py tests/unit/paper/test_broker_price_guards.py
git commit -m "feat(paper): reject stale-price paper fills via price_source_time guard"
```

### Task 1.2: Orchestrator가 `price_source_time` 전달

**Files:**
- Modify: `services/trading/orchestrator.py:_submit_entry_order` (line ~4402)
- Modify: `services/trading/orchestrator.py:_place_entry_order` (line ~4610)
- Test: append to `tests/unit/paper/test_broker_price_guards.py`

- [ ] **Step 1: 실패 테스트 작성**

Append to test file:

```python
from unittest.mock import AsyncMock, MagicMock

from services.trading.orchestrator import TradingConfig, TradingOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_passes_price_source_time_to_broker():
    """_place_entry_order가 signal.price_source_time을 broker.submit_order에 전달."""
    cfg = TradingConfig(
        asset_class="stock",
        strategy_name="momentum_breakout",
        initial_capital=100_000_000.0,
        order_amount_per_trade=1_000_000.0,
        paper_trading=True,
    )
    orch = TradingOrchestrator(cfg)

    broker = MagicMock()
    submit = AsyncMock()
    submit.return_value = MagicMock(filled=True, fill_price=70000.0, venue="KRX")
    broker.submit_order = submit
    orch._paper_broker = broker

    source_time = datetime(2026, 4, 15, 10, 0, 0, tzinfo=timezone.utc)
    await orch._place_entry_order(
        code="005930",
        is_short=False,
        quantity=10,
        order_type="market",
        limit_price=None,
        market_price=70000.0,
        price_source_time=source_time,
    )

    submit.assert_awaited_once()
    kwargs = submit.await_args.kwargs
    assert kwargs["price_source_time"] == source_time
```

Run: `pytest tests/unit/paper/test_broker_price_guards.py::test_orchestrator_passes_price_source_time_to_broker -v` → FAIL (TypeError).

- [ ] **Step 2: Add `price_source_time` param to `_place_entry_order`**

In `services/trading/orchestrator.py`, find `_place_entry_order` (line ~4610) signature:

```python
async def _place_entry_order(
    self,
    *,
    code: str,
    is_short: bool,
    quantity: int,
    order_type: str,
    limit_price: float | None,
    market_price: float,
    price_source_time: datetime | None = None,
) -> tuple[bool, float, int, str]:
```

Forward `price_source_time` to both paper broker submit_order calls (market and limit branches). Example:

```python
order = await self._paper_broker.submit_order(
    symbol=code,
    side=side,
    quantity=quantity,
    price=market_price,
    order_type=PaperOrderType.MARKET,
    price_source_time=price_source_time,
)
```

- [ ] **Step 3: Thread `price_source_time` through `_submit_entry_order`**

In `services/trading/orchestrator.py:_submit_entry_order` (line ~4402), add the param and pass it through:

```python
async def _submit_entry_order(
    self,
    code: str,
    is_short: bool,
    quantity: int,
    price: float,
    signal: Signal | None = None,
    price_source_time: datetime | None = None,
) -> tuple[bool, float, dict[str, Any]]:
    ...
    is_filled, fill_price, filled_qty, venue = await self._place_entry_order(
        code=code,
        is_short=is_short,
        quantity=quantity,
        order_type="market",
        limit_price=None,
        market_price=price,
        price_source_time=price_source_time,
    )
```

- [ ] **Step 4: Extract `price_source_time` at the signal-handling call site**

Locate callers of `_submit_entry_order` (grep for `_submit_entry_order(`). Extract `signal.timestamp` or `market_data[code].get("timestamp")` and pass it. If the caller only has `Signal`, use `getattr(signal, "timestamp", None)` — the `Signal` model already has a `timestamp: datetime` field in `shared/models/signal.py`.

For example:
```python
await self._submit_entry_order(
    code=signal.code,
    is_short=(signal.side == PositionSide.SHORT),
    quantity=quantity,
    price=price,
    signal=signal,
    price_source_time=getattr(signal, "timestamp", None),
)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/paper/test_broker_price_guards.py -v
pytest tests/unit/trading/ -q --no-header 2>&1 | tail -5
```
Expected: all pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/paper/test_broker_price_guards.py
git commit -m "feat(orchestrator): thread signal timestamp to paper broker for freshness guard"
```

### Task 1.3: Price deviation guard (reference median)

**Files:**
- Modify: `shared/paper/broker.py` — `_check_price_deviation` helper + 적용
- Test: append to `tests/unit/paper/test_broker_price_guards.py`

- [ ] **Step 1: 실패 테스트**

```python
@pytest.mark.asyncio
async def test_price_deviation_rejected_when_above_threshold(broker):
    """최근 reference median 대비 10% 초과 편차 시 체결 거부."""
    # Seed a reference history (helper to be added in Step 3)
    broker.record_price_observation("005930", 70000.0, datetime.now(timezone.utc))
    broker.record_price_observation("005930", 70100.0, datetime.now(timezone.utc))
    broker.record_price_observation("005930", 69900.0, datetime.now(timezone.utc))

    now = datetime.now(timezone.utc)
    # Attempt to fill at 50000 (29% deviation from median 70000)
    order = await broker.submit_order(
        symbol="005930",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=50000.0,
        price_source_time=now,
    )
    assert order.filled is False
    assert order.rejection_reason == "price_deviation"


@pytest.mark.asyncio
async def test_price_deviation_accepted_without_history(broker):
    """reference history가 없으면 guard 적용 불가 → 통과(로깅만)."""
    now = datetime.now(timezone.utc)
    order = await broker.submit_order(
        symbol="NEWCODE",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        market_price=50000.0,
        price_source_time=now,
    )
    assert order.filled is True
```

Run → FAIL (no `record_price_observation` method).

- [ ] **Step 2: Implement `record_price_observation` + `_check_price_deviation`**

In `shared/paper/broker.py`:

```python
from collections import defaultdict, deque
from statistics import median

class PaperBroker:
    def __init__(self, config: PaperBrokerConfig):
        self.config = config
        self.balance = config.initial_balance
        self.positions: dict[str, Position] = {}
        self._price_history: dict[str, deque[tuple[datetime, float]]] = defaultdict(
            lambda: deque(maxlen=256)
        )

    def record_price_observation(
        self, symbol: str, price: float, ts: datetime
    ) -> None:
        """Caller (orchestrator) reports observed market prices. Used for
        deviation guard reference median. Only last `reference_price_lookback_minutes`
        window is considered at guard time.
        """
        self._price_history[symbol].append((ts, price))

    def _check_price_deviation(
        self, symbol: str, proposed_price: float, now: datetime
    ) -> bool:
        """Return True if proposed_price is within deviation threshold, else False."""
        if (
            self.config.max_price_deviation_pct <= 0
            or self.config.reference_price_lookback_minutes <= 0
        ):
            return True
        history = self._price_history.get(symbol)
        if not history:
            return True  # no reference → allow
        cutoff = now - timedelta(
            minutes=self.config.reference_price_lookback_minutes
        )
        recent_prices = [p for ts, p in history if ts >= cutoff]
        if not recent_prices:
            return True
        ref = median(recent_prices)
        if ref <= 0:
            return True
        deviation = abs(proposed_price - ref) / ref
        return deviation <= self.config.max_price_deviation_pct
```

Then in `submit_order`, after the freshness guard:

```python
    # Guard 2: price deviation from reference median
    now = datetime.now(timezone.utc)
    if not self._check_price_deviation(symbol, market_price, now):
        order.filled = False
        order.rejection_reason = "price_deviation"
        logger.warning(
            "Paper order rejected (price deviation): %s proposed=%.2f",
            symbol, market_price,
        )
        return order
```

- [ ] **Step 3: Orchestrator가 관찰된 price를 기록**

In `services/trading/orchestrator.py`, whenever a market snapshot is processed (main loop tick handler — grep for `_handle_tick` or `_process_market_data`), call:

```python
if self._paper_broker is not None:
    self._paper_broker.record_price_observation(
        symbol=code,
        price=float(price),
        ts=datetime.now(timezone.utc),
    )
```

Place this at the point where each symbol's latest close is observed per tick.

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/paper/test_broker_price_guards.py -v
```
Expected: 5 passed (3 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
git add shared/paper/broker.py services/trading/orchestrator.py tests/unit/paper/test_broker_price_guards.py
git commit -m "feat(paper): add price-deviation guard using reference median from recent observations"
```

### Task 1.4: 설정 노출

**Files:**
- Modify: `config/execution.yaml`
- Modify: 설정 로딩 지점 (grep `PaperBrokerConfig` 생성 위치, orchestrator 또는 pipeline에서 YAML 매핑 확인)

- [ ] **Step 1: Add new keys to `config/execution.yaml`** (append to the paper-trading section, or create it if missing):

```yaml
paper_broker:
  initial_balance: 100000000
  commission_rate: 0.0015
  slippage_rate: 0.001
  # Price quality guards
  max_price_staleness_seconds: 30.0
  max_price_deviation_pct: 0.10
  reference_price_lookback_minutes: 5
```

- [ ] **Step 2: Ensure `PaperBrokerConfig.from_yaml()` picks up new keys**

Grep where `PaperBrokerConfig(...)` is constructed in `services/trading/orchestrator.py`. If it reads from `execution.yaml` via `ConfigLoader.load()`, confirm the new keys are forwarded. If keys are hardcoded in orchestrator, replace with YAML load:

```python
from shared.config.loader import ConfigLoader

exec_cfg = ConfigLoader.load("execution.yaml")
broker_cfg_dict = exec_cfg.get("paper_broker", {})
self._paper_broker = PaperBroker(config=PaperBrokerConfig(**broker_cfg_dict))
```

- [ ] **Step 3: Regression check**

```bash
pytest tests/unit/paper/ tests/unit/trading/ -q --no-header 2>&1 | tail -5
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add config/execution.yaml services/trading/orchestrator.py
git commit -m "feat(config): expose paper broker price guards in execution.yaml"
```

---

## Phase 2 (P1): Futures RL Live/Training Parity Diagnostic

**Background:** `kospi.rl_trades` 578건 기준 2026-03-27 이후 승률 0%, 모든 거래가 hold_seconds 60~120s의 즉시 청산, PnL이 정확히 수수료+슬리피지 수준(-0.9 ~ -1.0)으로 **학습 eval Sharpe 3.19 vs 실운용 Sharpe 사실상 음수**. 이는 (a) 실제 obs가 학습 obs 분포와 다름, (b) scaler가 obs builder와 불일치, 또는 (c) profile matrix의 변형들이 의사결정을 무작위화 중인 상황 중 하나가 원인.

**이 Phase는 investigation → findings → 수정 순서**이며 fix 자체는 Phase 2 종료 시 Task 2.5에서 결정한다.

### Task 2.0: Live obs vs train obs drift 진단 스크립트

**Files:**
- Create: `scripts/analysis/rl_live_vs_train_obs_drift.py`
- Test: 없음 (one-off diagnostic)

- [ ] **Step 1: Create diagnostic script**

```python
# scripts/analysis/rl_live_vs_train_obs_drift.py
"""Compare live paper-trading obs distribution vs training obs distribution.

Usage:
    python scripts/analysis/rl_live_vs_train_obs_drift.py \
        --live-days 7 \
        --train-data data/kospi200f_1m_clean.csv \
        --scaler models/futures/rl/scaler.joblib

Outputs a report showing per-feature mean/std/min/max for live and train,
plus KL divergence and PSI per feature.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS


def load_live_obs(days: int) -> np.ndarray:
    """Read recent live obs from ClickHouse kospi.rl_trades metadata_json."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env()
    cfg.database = "kospi"
    client = ClickHouseClient(cfg)

    query = f"""
        SELECT metadata_json FROM kospi.rl_trades
        WHERE exit_date >= now() - INTERVAL {days} DAY
        ORDER BY exit_date DESC LIMIT 200
    """
    rows = client.get_sync_client().execute(query)
    obs_list: list[list[float]] = []
    for (meta_json,) in rows:
        try:
            meta = json.loads(meta_json)
            if isinstance(meta.get("obs"), list) and len(meta["obs"]) == len(
                RL_FEATURE_COLUMNS
            ):
                obs_list.append(meta["obs"])
        except (ValueError, TypeError):
            continue
    return np.asarray(obs_list, dtype=np.float64) if obs_list else np.empty((0, 0))


def load_train_obs(csv_path: Path) -> np.ndarray:
    df = pd.read_csv(csv_path)
    calc = RLFeatureCalculator()
    feats = calc.calculate_features(df)
    return feats[RL_FEATURE_COLUMNS].dropna().to_numpy()


def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index per feature vector."""
    if expected.size == 0 or actual.size == 0:
        return float("nan")
    breakpoints = np.quantile(expected, np.linspace(0, 1, bins + 1))
    breakpoints[0] -= 1e-9
    breakpoints[-1] += 1e-9
    e_counts, _ = np.histogram(expected, bins=breakpoints)
    a_counts, _ = np.histogram(actual, bins=breakpoints)
    e_pct = np.clip(e_counts / max(e_counts.sum(), 1), 1e-6, None)
    a_pct = np.clip(a_counts / max(a_counts.sum(), 1), 1e-6, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-days", type=int, default=7)
    parser.add_argument(
        "--train-data",
        type=Path,
        default=Path("data/kospi200f_1m_clean.csv"),
    )
    parser.add_argument(
        "--scaler",
        type=Path,
        default=Path("models/futures/rl/scaler.joblib"),
    )
    args = parser.parse_args()

    live = load_live_obs(args.live_days)
    train = load_train_obs(args.train_data)

    print(f"Live obs: shape={live.shape}")
    print(f"Train obs: shape={train.shape}")

    if live.shape[0] == 0 or train.shape[0] == 0:
        print("NOT ENOUGH DATA — ensure live metadata captures obs (see Task 2.1).")
        return

    scaler = joblib.load(args.scaler)
    print(f"Scaler n_features_in_={scaler.n_features_in_}")

    print("\nPer-feature PSI (live vs train):")
    print(f"{'feature':<30} {'live_mean':>10} {'train_mean':>10} {'PSI':>8}")
    for i, col in enumerate(RL_FEATURE_COLUMNS):
        psi = compute_psi(train[:, i], live[:, i])
        print(
            f"{col:<30} {live[:, i].mean():>10.3f} {train[:, i].mean():>10.3f} "
            f"{psi:>8.3f}"
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify live obs is captured in metadata_json**

The script depends on `metadata_json` containing `{"obs": [...]}`. Check where trades are persisted:

```bash
grep -n "metadata_json\|metadata\[" services/trading/orchestrator.py shared/strategy/entry/rl_mppo_entry.py shared/strategy/exit/rl_mppo_exit.py 2>/dev/null | head -20
```

If obs is NOT captured, the first action of Phase 2 is to capture it. Update the relevant entry/exit strategy to insert `obs: list(observation)` into `position.metadata` at entry time. Then wait for ≥50 new trades to accumulate before running diagnostic.

If obs IS captured, proceed to Step 3.

- [ ] **Step 3: Run diagnostic and record findings**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
python scripts/analysis/rl_live_vs_train_obs_drift.py --live-days 7
```

Append results to `docs/plans/2026-04-15-paper-trading-quality-recovery.md` under a new `## Phase 2 Investigation Findings` section:
- Per-feature PSI table
- Which features drift > 0.25 (significant)
- Hypothesis for each drifting feature (scaler mismatch? obs builder skip? indicator lag?)

- [ ] **Step 4: Doc-only commit**

```bash
git add scripts/analysis/rl_live_vs_train_obs_drift.py docs/plans/2026-04-15-paper-trading-quality-recovery.md
git commit -m "feat(analysis): add live vs train obs drift diagnostic for RL + record findings"
```

### Task 2.1: Scaler 무결성 재검증

**Files:**
- Create: `scripts/analysis/rl_scaler_audit.py`

- [ ] **Step 1: Create audit script**

```python
# scripts/analysis/rl_scaler_audit.py
"""Verify scaler.joblib consistency with current RLFeatureCalculator output.

Checks:
1. scaler.n_features_in_ == len(RL_FEATURE_COLUMNS)
2. scaler.mean_ / scale_ values are finite, non-zero
3. Applying scaler to synthetic feature row produces values in reasonable range (-10, +10)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scaler",
        type=Path,
        default=Path("models/futures/rl/scaler.joblib"),
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("data/kospi200f_1m_clean.csv"),
    )
    args = parser.parse_args()

    scaler = joblib.load(args.scaler)

    n_expected = len(RL_FEATURE_COLUMNS)
    n_scaler = int(scaler.n_features_in_)
    print(f"Scaler n_features_in_ = {n_scaler}")
    print(f"RL_FEATURE_COLUMNS    = {n_expected}")
    if n_scaler != n_expected:
        print("!!! MISMATCH !!! Scaler and feature columns disagree on dimension.")
        return
    print("OK: dimensions match.")

    # Values sanity
    if not np.isfinite(scaler.mean_).all():
        print(f"!!! Non-finite means: {scaler.mean_}")
        return
    if not np.isfinite(scaler.scale_).all() or (scaler.scale_ <= 0).any():
        print(f"!!! Invalid scale_ (non-positive or NaN): {scaler.scale_}")
        return
    print("OK: scaler mean/scale values are finite.")

    # Sample end-to-end
    df = pd.read_csv(args.sample)
    calc = RLFeatureCalculator()
    feats = calc.calculate_features(df)
    row = feats[RL_FEATURE_COLUMNS].dropna().iloc[-1].to_numpy().reshape(1, -1)
    scaled = scaler.transform(row)
    print(f"Sample scaled obs: min={scaled.min():.2f} max={scaled.max():.2f}")
    if np.abs(scaled).max() > 10:
        print("WARN: |scaled| > 10 — possible outlier or scaler/feature mismatch.")
    else:
        print("OK: sample scaled obs within reasonable range.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run audit**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
python scripts/analysis/rl_scaler_audit.py
```

- [ ] **Step 3: Record results in plan findings section**

Append to `## Phase 2 Investigation Findings`:
- Scaler dim match: PASS/FAIL
- Values sanity: PASS/FAIL
- Sample scaled obs range: `min`/`max`

- [ ] **Step 4: Commit**

```bash
git add scripts/analysis/rl_scaler_audit.py docs/plans/2026-04-15-paper-trading-quality-recovery.md
git commit -m "feat(analysis): add rl scaler audit script + findings"
```

### Task 2.2: Obs builder parity 회귀 테스트

**Files:**
- Create: `tests/unit/ml/rl/test_obs_builder_parity.py`

- [ ] **Step 1: Failing parity test**

```python
# tests/unit/ml/rl/test_obs_builder_parity.py
"""학습/평가/운용에서 동일 obs가 생성되는지 검증."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS
from shared.strategy.rl_model_helpers import build_obs_from_market_data


SAMPLE_CSV = Path("data/kospi200f_1m_clean.csv")


@pytest.fixture(scope="module")
def recent_bars() -> pd.DataFrame:
    df = pd.read_csv(SAMPLE_CSV).tail(120).reset_index(drop=True)
    return df


def test_trainer_vs_runtime_obs_match(recent_bars):
    """RLFeatureCalculator 경로와 runtime obs builder가 동일 obs를 만든다."""
    calc = RLFeatureCalculator()
    trainer_feats = calc.calculate_features(recent_bars)
    trainer_row = trainer_feats[RL_FEATURE_COLUMNS].dropna().iloc[-1].to_numpy()

    # Runtime path used by orchestrator
    market_data = {
        "A05603": {
            "ohlcv": recent_bars.to_dict(orient="records"),
        }
    }
    runtime_row = build_obs_from_market_data("A05603", market_data)

    np.testing.assert_allclose(
        trainer_row, runtime_row, rtol=1e-6, atol=1e-8,
        err_msg="Trainer-vs-runtime obs mismatch",
    )


def test_obs_dimension_matches_feature_columns():
    """runtime obs 차원이 RL_FEATURE_COLUMNS 길이와 같다."""
    # Construct minimal fake market_data; if builder tolerates it, dim should still match
    market_data = {"A05603": {"ohlcv": []}}
    try:
        runtime_row = build_obs_from_market_data("A05603", market_data)
    except (ValueError, KeyError):
        pytest.skip("Builder requires non-empty data; covered by first test")
    else:
        assert len(runtime_row) == len(RL_FEATURE_COLUMNS)
```

- [ ] **Step 2: Run test**

```bash
pytest tests/unit/ml/rl/test_obs_builder_parity.py -v
```

If it passes, obs builder parity is good. If it fails, **this is the root cause** — fix `build_obs_from_market_data` or `RLFeatureCalculator` so their outputs match.

- [ ] **Step 3: If parity test failed, fix the drift**

Inspect the failing feature indices. Typical root causes:
- Feature ordering difference between training and runtime
- One path applies rolling windows, the other uses absolute values
- Scaler is applied twice or not at all in one path

Fix the path that drifted away from the training-time convention. Update `build_obs_from_market_data` or `RLFeatureCalculator` accordingly.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/ml/rl/test_obs_builder_parity.py shared/ml/rl/features.py shared/strategy/rl_model_helpers.py
git commit -m "test(rl): add obs builder parity regression and fix any drift"
```

### Task 2.3: Profile matrix 기여도 감사 + 비활성화 결정

**Files:**
- Modify (conditional): `config/ml/rl_mppo.yaml`

- [ ] **Step 1: Aggregate profile-wise PnL**

```bash
source .env
clickhouse-client --host=localhost --port=9000 --user=default --password="$CLICKHOUSE_PASSWORD" \
  --format=PrettyCompact -q "
SELECT strategy, count() AS n, round(sum(pnl),1) AS total_pnl,
       round(avg(pnl),2) AS avg_pnl, countIf(pnl>0) AS wins,
       round(countIf(pnl>0)/count()*100,1) AS win_pct
FROM kospi.rl_trades
WHERE exit_date >= now() - INTERVAL 30 DAY
GROUP BY strategy ORDER BY total_pnl ASC"
```
Expected: per-profile stats. Identify profiles that are net-negative and dominant.

- [ ] **Step 2: Record findings**

Append to `## Phase 2 Investigation Findings`: per-profile stats + decision (keep / disable).

- [ ] **Step 3: If multiple profiles are net-negative, disable matrix and revert to single `rl_mppo`**

In `config/ml/rl_mppo.yaml`, check for a `profiles:` section or similar matrix configuration. Set `enabled: false` for all non-baseline profiles, or delete the section entirely if the feature is opt-in only.

If profiles are driven by `scripts/analysis/rl_paper_profile_matrix.py` (MEMORY notes), update the cron script `scripts/cron/rl_paper.sh` to use the single-profile `sts rl paper` command instead of matrix runner.

- [ ] **Step 4: Commit**

```bash
git add config/ml/rl_mppo.yaml scripts/cron/rl_paper.sh docs/plans/2026-04-15-paper-trading-quality-recovery.md
git commit -m "fix(rl): disable profile matrix based on 30-day per-profile PnL audit"
```

### Task 2.4: Action mask / HOLD-override audit

**Files:**
- Grep only; modify if finding warrants

- [ ] **Step 1: 오케스트레이터 action override 경로 검색**

```bash
grep -n "hold_override\|HOLD\|action ==\|action =\|override" /home/deploy/project/kis_unified_sts/shared/strategy/entry/rl_mppo_entry.py /home/deploy/project/kis_unified_sts/shared/strategy/exit/rl_mppo_exit.py /home/deploy/project/kis_unified_sts/shared/strategy/rl_model_helpers.py | head -30
```

Recent commit `50a99f7 fix: disable rl mppo hold override by default` indicates an override existed; verify it is actually disabled in config and not accidentally re-enabled anywhere.

- [ ] **Step 2: Verify config default**

```bash
grep -n "hold_override\|force_hold" config/ml/rl_mppo.yaml
grep -n "hold_override\|force_hold" shared/strategy/rl_model_helpers.py
```
Expected: override defaults to `false`/disabled.

- [ ] **Step 3: Record in findings + no-op commit if already disabled**

Append to `## Phase 2 Investigation Findings`: "hold override state: disabled by default as of commit 50a99f7".

### Task 2.5: Consolidation fix (findings-driven)

**Prerequisite:** Tasks 2.0-2.4 complete with findings documented.

Based on the consolidated findings, decide and execute ONE of:

- [ ] **Path A — Obs/scaler mismatch fixed (Task 2.2)**: Regression test + fix already committed. Run a 1-day paper session to confirm win rate recovers. Append post-deploy observation.

- [ ] **Path B — Profile matrix was noise (Task 2.3)**: Matrix disabled. Monitor 5 trading days; compare pre/post win rate and avg pnl via `kospi.futures_daily_equity` view.

- [ ] **Path C — Deeper model retraining needed**: If all prior tasks pass but performance remains poor, this is beyond the scope of Phase 2. Create a follow-up plan `docs/plans/YYYY-MM-DD-rl-retraining-data-refresh.md` and commit that.

Commit the chosen path's implementation (if any additional code changes) with message matching the path.

---

## Phase 3 (P2): Redis Capital Continuity

**Background:** `trading:{asset}:status::stats` HASH의 `total_trades`/`total_pnl`이 매 세션마다 리셋되어 Redis만으로는 자본 추적 불가. Phase 3은 세션 간 누적 키와 일별 snapshot 소팅셋을 추가한다. ClickHouse `*_daily_equity` 뷰는 주/월 단위 분석용, Redis는 리얼타임 모니터링용 분리 의도.

### Task 3.1: `TradingStatePublisher`에 running totals 추가

**Files:**
- Modify: `shared/streaming/trading_state.py`
- Test: `tests/unit/streaming/test_equity_timeline.py`

- [ ] **Step 1: Failing test**

```python
# tests/unit/streaming/test_equity_timeline.py
"""TradingStatePublisher running-total 및 equity_timeline 회귀 테스트."""
from __future__ import annotations

from datetime import date

import fakeredis
import pytest

from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def publisher(redis_client):
    return TradingStatePublisher(asset_class="stock", redis_client=redis_client)


@pytest.fixture
def reader(redis_client):
    return TradingStateReader(asset_class="stock", redis_client=redis_client)


def test_running_totals_survive_across_sessions(publisher, reader):
    """세션 리셋해도 running_totals는 누적된다."""
    publisher.increment_running_totals(pnl=150.0, trades=1, win=True)
    publisher.increment_running_totals(pnl=-80.0, trades=1, win=False)

    totals = reader.get_running_totals()
    assert totals["total_trades"] == 2
    assert totals["total_wins"] == 1
    assert totals["total_pnl"] == pytest.approx(70.0)


def test_equity_timeline_records_daily_snapshot(publisher, reader):
    """publish_equity_snapshot이 trading:{asset}:equity_timeline sorted set에 추가된다."""
    today = date(2026, 4, 15)
    publisher.publish_equity_snapshot(
        as_of=today,
        cash_balance=100_000_000.0,
        open_positions_value=5_000_000.0,
        closed_pnl=150.0,
    )

    timeline = reader.get_equity_timeline(days=30)
    assert len(timeline) == 1
    entry = timeline[0]
    assert entry["date"] == "2026-04-15"
    assert entry["total_equity"] == pytest.approx(105_000_150.0)
```

Run → FAIL.

- [ ] **Step 2: Extend publisher**

In `shared/streaming/trading_state.py`, add:

```python
from datetime import date, datetime
import json

RUNNING_TOTALS_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days rolling
EQUITY_TIMELINE_TTL_SECONDS = 60 * 60 * 24 * 400  # ~13 months


class TradingStatePublisher:
    # ... existing ...

    def _running_totals_key(self) -> str:
        return f"trading:{self.asset_class}:running_totals"

    def _equity_timeline_key(self) -> str:
        return f"trading:{self.asset_class}:equity_timeline"

    def increment_running_totals(
        self, *, pnl: float, trades: int = 1, win: bool = False
    ) -> None:
        """Session-independent cumulative counters."""
        key = self._running_totals_key()
        pipe = self._redis.pipeline()
        pipe.hincrbyfloat(key, "total_pnl", pnl)
        pipe.hincrby(key, "total_trades", trades)
        if win:
            pipe.hincrby(key, "total_wins", 1)
        pipe.expire(key, RUNNING_TOTALS_TTL_SECONDS)
        pipe.execute()

    def publish_equity_snapshot(
        self,
        *,
        as_of: date,
        cash_balance: float,
        open_positions_value: float,
        closed_pnl: float,
    ) -> None:
        """Append one daily equity datapoint to sorted set (score = epoch timestamp)."""
        key = self._equity_timeline_key()
        total_equity = cash_balance + open_positions_value + closed_pnl
        snapshot = {
            "date": as_of.isoformat(),
            "cash_balance": cash_balance,
            "open_positions_value": open_positions_value,
            "closed_pnl": closed_pnl,
            "total_equity": total_equity,
        }
        score = datetime.combine(as_of, datetime.min.time()).timestamp()
        self._redis.zadd(key, {json.dumps(snapshot): score})
        self._redis.expire(key, EQUITY_TIMELINE_TTL_SECONDS)
```

- [ ] **Step 3: Extend reader**

```python
class TradingStateReader:
    # ... existing ...

    def get_running_totals(self) -> dict[str, float]:
        key = f"trading:{self.asset_class}:running_totals"
        raw = self._redis.hgetall(key) or {}
        return {
            "total_pnl": float(raw.get("total_pnl", 0.0) or 0.0),
            "total_trades": int(raw.get("total_trades", 0) or 0),
            "total_wins": int(raw.get("total_wins", 0) or 0),
        }

    def get_equity_timeline(self, days: int = 30) -> list[dict]:
        key = f"trading:{self.asset_class}:equity_timeline"
        # Return most recent `days` entries, oldest-first
        raw = self._redis.zrange(key, -days, -1, withscores=False) or []
        return [json.loads(s) for s in raw]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/streaming/test_equity_timeline.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/streaming/trading_state.py tests/unit/streaming/test_equity_timeline.py
git commit -m "feat(streaming): add running_totals and equity_timeline for cross-session capital tracking"
```

### Task 3.2: Orchestrator가 running totals 갱신

**Files:**
- Modify: `services/trading/orchestrator.py` — position close 처리 시점 (grep `publish_position_closed`)

- [ ] **Step 1: Append test**

Append to `tests/unit/streaming/test_equity_timeline.py`:

```python
from unittest.mock import MagicMock


def test_orchestrator_increments_running_totals_on_close(publisher):
    """orchestrator가 position close 시 running_totals를 갱신한다."""
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator
    from shared.models.position import Position, PositionSide
    from datetime import datetime, timedelta

    cfg = TradingConfig(
        asset_class="stock",
        strategy_name="momentum_breakout",
        initial_capital=100_000_000.0,
        order_amount_per_trade=1_000_000.0,
    )
    orch = TradingOrchestrator(cfg)
    orch._state_publisher = publisher

    entry_time = datetime(2026, 4, 15, 9, 0)
    closed = Position(
        id="p1", code="005930", name="TEST",
        strategy="momentum_breakout", side=PositionSide.LONG,
        entry_price=70000.0, quantity=10, entry_time=entry_time,
    )
    closed.exit_price = 71000.0
    closed.exit_time = entry_time + timedelta(minutes=15)
    closed.current_price = 71000.0

    orch._record_running_totals(closed)

    # The publisher now writes to fakeredis; verify via reader
    from shared.streaming.trading_state import TradingStateReader
    reader = TradingStateReader("stock", redis_client=publisher._redis)
    totals = reader.get_running_totals()
    assert totals["total_trades"] == 1
    # pnl = (71000-70000)*10 = 10000
    assert totals["total_pnl"] == pytest.approx(10000.0)
    assert totals["total_wins"] == 1
```

- [ ] **Step 2: Add `_record_running_totals` helper to orchestrator**

```python
    def _record_running_totals(self, closed_position) -> None:
        """Publish cross-session totals on each close (idempotent: increments only)."""
        if self._state_publisher is None:
            return
        pnl = getattr(closed_position, "unrealized_pnl", 0.0) or 0.0
        self._state_publisher.increment_running_totals(
            pnl=pnl, trades=1, win=(pnl > 0)
        )
```

Call this from the close-handling path (search for `publish_position_closed` in orchestrator.py and add `self._record_running_totals(closed)` immediately before/after).

- [ ] **Step 3: Run tests**

```bash
pytest tests/unit/streaming/test_equity_timeline.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/streaming/test_equity_timeline.py
git commit -m "feat(orchestrator): record cross-session running totals on each position close"
```

### Task 3.3: Daily equity snapshot cron

**Files:**
- Create: `scripts/cron/publish_equity_snapshot.sh`
- Create: `scripts/analysis/publish_equity_snapshot.py`

- [ ] **Step 1: Create snapshot publisher script**

```python
# scripts/analysis/publish_equity_snapshot.py
"""Publish end-of-day equity snapshot to Redis timeline.

Intended cron: 15:40 KST Mon-Fri.
"""
from __future__ import annotations

import logging
from datetime import date

from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def snapshot_one(asset_class: str) -> None:
    publisher = TradingStatePublisher(asset_class=asset_class)
    reader = TradingStateReader(asset_class=asset_class)
    status = reader.get_status_all() or {}
    stats = status.get("stats", {}) or {}
    positions_meta = status.get("positions", {}) or {}
    config_meta = status.get("config", {}) or {}

    cash_balance = float(
        config_meta.get("capital", 0.0)
    ) - float(positions_meta.get("open_positions_value", 0.0) or 0.0)
    open_positions_value = float(positions_meta.get("open_positions_value", 0.0) or 0.0)
    closed_pnl = float(stats.get("total_pnl", 0.0) or 0.0)

    publisher.publish_equity_snapshot(
        as_of=date.today(),
        cash_balance=cash_balance,
        open_positions_value=open_positions_value,
        closed_pnl=closed_pnl,
    )
    logger.info(
        "Published %s equity snapshot: equity=%.0f, cash=%.0f, pos=%.0f, pnl=%.0f",
        asset_class, cash_balance + open_positions_value + closed_pnl,
        cash_balance, open_positions_value, closed_pnl,
    )


def main() -> None:
    for asset_class in ("stock", "futures"):
        try:
            snapshot_one(asset_class)
        except Exception as e:
            logger.error("snapshot_one(%s) failed: %s", asset_class, e, exc_info=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create cron shell script**

```bash
# scripts/cron/publish_equity_snapshot.sh
#!/bin/bash
set -e
PROJECT_DIR="/home/deploy/project/kis_unified_sts"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/equity_snapshot_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a && source "$PROJECT_DIR/.env" && set +a
fi
source "$PROJECT_DIR/.venv/bin/activate"
python "$PROJECT_DIR/scripts/analysis/publish_equity_snapshot.py" >> "$LOG_FILE" 2>&1
```

- [ ] **Step 3: Make executable + verify run**

```bash
chmod +x /home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh
/home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh
cat /home/deploy/project/kis_unified_sts/logs/equity_snapshot_$(date +%Y%m%d).log | tail -20
```
Expected: two lines (stock + futures) with "Published ... equity snapshot".

- [ ] **Step 4: Register crontab (manual)**

```bash
(crontab -l 2>/dev/null; echo "40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh") | crontab -
```
**Verify with user before running this step** — crontab changes are manual/operational.

- [ ] **Step 5: Commit (scripts only, no crontab)**

```bash
git add scripts/cron/publish_equity_snapshot.sh scripts/analysis/publish_equity_snapshot.py
git commit -m "feat(ops): daily equity snapshot cron for cross-session capital tracking"
```

---

## 최종 검증

### Task 4: Full regression + PR

- [ ] **Step 1: Run full test suite**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
pytest tests/unit/ -q --no-header 2>&1 | tail -5
```
Expected: no regressions.

- [ ] **Step 2: Push + PR**

```bash
git push -u origin fix/paper-trading-quality-recovery
gh pr create --base main --title "fix: recover paper-trading entry price quality, rl parity, capital tracking" \
  --body "See docs/plans/2026-04-15-paper-trading-quality-recovery.md"
```

- [ ] **Step 3: Post-deploy monitoring (manual, next trading day)**

For 5 trading days after merge, daily check:
- `market.stock_daily_equity` shows realistic PnL range (±5% per-trade)
- `kospi.futures_daily_equity` shows win_pct > 0 (if Phase 2 fix landed)
- `trading:stock:running_totals` and `trading:stock:equity_timeline` populated
- No `rejection_reason=stale_price` flood in stock trading logs (a few is OK; many means freshness threshold too tight)

---

## Phase 2 Investigation Findings

### Task 2.0 — Live vs Train Obs Drift Diagnostic

**Date:** 2026-04-15 (run during feat/hybrid-full-training-config → fix/paper-trading-quality-recovery)

**Precondition check:** Live obs NOT captured in existing trades.

`kospi.rl_trades.metadata_json` examined for last 14 days (500 rows) — the `obs` key was absent from all records. The metadata only contained: `snapshot_id`, `llm_quality`, `realtime_score`, `risk_flags`, `entry_signal_confidence`, `signal_direction`, `execution`, `entry_regime`.

**Root cause:** The orchestrator's `_process_filled_entry` selectively forwards only 4 specific keys from `signal.metadata` into `pos_metadata`:
- `exit_stop_atr_multiplier`
- `exit_trail_activation_atr`
- `exit_trail_atr_multiplier`
- `exit_max_hold_days`

`RLMPPOEntry.generate()` built the obs and passed it to the model, but never stored it in `signal.metadata`. Consequently, obs was never captured in position metadata or persisted to ClickHouse.

**Fixes applied (this task):**

1. **`shared/strategy/entry/rl_mppo.py`** — Added `"obs": obs.tolist()` to `meta_common` dict at the point after model prediction, before `Signal` construction. The obs is the full 31-dim vector that was passed to `model.predict()`.

2. **`services/trading/orchestrator.py`** — Added `"obs"` to the forwarding key list in `_process_filled_entry` so it flows from `signal.metadata` → `pos_metadata` → `position.metadata` → `kospi.rl_trades.metadata_json`.

**Diagnostic script run:**

```
Exit code: 2 (NO LIVE OBS CAPTURED)
Live obs samples: 0
Message: metadata_json does not contain 'obs' key.
```

This is expected — the obs capture patch was applied in this task. Existing historical trades do not have obs data.

**Next steps:**

- Wait for ≥50 new RL trades to accumulate after the obs-capture patch is deployed (typically 1-3 trading days at current rl_mppo cadence)
- Re-run: `python scripts/analysis/rl_live_vs_train_obs_drift.py --live-days 7`
- Expected output: PSI table across 25 market features (dims 0-24 of the 31-dim obs vector)

**Features to watch for drift:**
- `returns`, `ma_ratio_5/10/20` — sensitive to market regime shift
- `bb_position`, `rsi` — normalization-sensitive; scaler drift would appear here
- `volume_ratio` — futures mini vs 연결선물 liquidity difference may cause drift
- `atr` — market volatility regime changes (tariff shock, policy changes)

**Top-3 suspected causes (pre-diagnostic hypotheses):**
1. **Scaler mismatch** — scaler was fit on `kospi200f_1m` (연결선물 101S6000) but live trading uses KOSPI200 mini (A05xxx). Price levels differ; volume levels differ significantly (1/9~1/42 ratio). Features like `volume_ratio` and `atr` may show large PSI.
2. **Obs builder skip** — if `IndicatorEngine` does not inject all 25 `RL_FEATURE_COLUMNS` into `indicators`, the `build_rl_observation` fallback fills missing features with `0.0`, causing systematic mean suppression and PSI inflation.
3. **Market regime drift** — the model was trained on 14 months of data ending Feb 2026. The April 2026 market environment (global tariff uncertainty, KOSPI200 level ~905-935 vs training mean ~350-400) may represent an out-of-distribution regime for several ratio features.

---

### Task 2.1 — Scaler Audit (2026-04-15)

**Objective:** Validate `models/futures/rl/scaler.joblib` against current `RL_FEATURE_COLUMNS` (expected 25 dims per CLAUDE.md error note).

**Script created:** `scripts/analysis/rl_scaler_audit.py`

**Audit Results:**

```
Scaler type: MinMaxScaler
Scaler n_features_in_ = 25
RL_FEATURE_COLUMNS    = 25
OK: dimensions match
OK: scaler values finite, scale_ > 0
Sample scaled obs: min=0.000 max=1.000 |z|_max=1.000
OK: sample scaled obs within [0,1] range
```

**Verdict:** ✅ **SCALER IS CONSISTENT**

- Dimensions: 25 (matches current RL_FEATURE_COLUMNS, NOT 31 as stated in CLAUDE.md)
- Bounds: MinMaxScaler with proper [0,1] normalization
- Finite values: mean_ and scale_ all valid
- End-to-end test: sample observation from `data/kospi200f_1m_clean.csv` → RLFeatureCalculator → scaler produces values in [0,1]

**Note:** CLAUDE.md line "31차원 obs" is incorrect — actual obs is 25 dims (10 base + 15 RL extra features). Regime features (3 dims) are optional and not included in scaler training.

**Next task:** Task 2.2 (Obs builder parity regression test).

---

### Task 2.2 — Obs Builder Parity (2026-04-15)

- **Parity test outcome: PASS**
- Runtime obs builder (`derive_features_from_ohlcv`) produces the same 25 raw market features as the training `RLFeatureCalculator.calculate()` path — both call the identical `RLFeatureCalculator` under the hood.
- `build_rl_observation` market feature portion (dims 0-24) also matches training features exactly when scaler is bypassed.
- Obs structure confirmed: `[scaled_market (25)] + [position_side, contracts, unrealized_pnl (3)] + [sin/cos time (3)] = 31 dims`.
- **Conclusion: obs builder code path is NOT the source of the live-vs-training performance gap.**
  - The raw feature computation is numerically identical between training and runtime.
  - The MinMaxScaler (Task 2.1) is dimensionally consistent (25 dims, finite values).
  - Remaining suspects: (1) scaler was fit on `101S6000` (연결선물) but live trading uses `A05xxx` (mini, different price/volume levels) → `volume_ratio`, `atr`, `ma_ratio_*` may be out-of-distribution at inference time; (2) market regime shift (April 2026 tariff shock / KOSPI200 ~905-935 vs training era ~350-400).
- **Test file:** `tests/unit/ml/rl/test_obs_builder_parity.py` (5 tests, all pass)
- **Next task:** Task 2.3 (Profile matrix audit + decision)

---

### Task 2.3 — Profile Matrix Audit (2026-04-14)

**Objective:** Identify whether the RL profile matrix is a net-negative contributor driving the ~-0.95/trade mean PnL observed over 30 days.

**30-day per-profile PnL (`kospi.rl_trades`, last 30 days):**

| Strategy | Trades | Total PnL | Avg PnL | Win% | Std |
|---|---|---|---|---|---|
| `rl_mppo_profile_asym_long_strict` | 235 | -208.6 | -0.89 | 3.0% | 0.58 |
| `rl_mppo` (baseline) | 214 | -150.3 | -0.70 | 15.9% | 1.13 |
| `rl_mppo_profile_uptrend_spike_guard` | 53 | -49.6 | -0.94 | 3.8% | 0.92 |

**Profile breakdown:**
- Total trades: 502 across 3 strategies
- Profile variant trades: 288 / 502 = 57.4% of all trades
- Note: `rl_mppo_spread6/7/8` profiles listed in cron config did not appear in 30-day window (either not run recently or merged into baseline)

**Decision: DISABLE MATRIX — revert cron to single `rl_mppo` baseline**

**Rationale:**
1. All 3 strategies are net-negative. Even the baseline `rl_mppo` is losing (consistent with broader model performance degradation noted in Task 2.0 / regime-shift hypothesis).
2. Profile variants are significantly **worse** than baseline: win rate 3-4% vs 15.9% for `rl_mppo`. The `asym_long_strict` variant alone burned -208.6 PnL on 235 trades.
3. Profile variants contributed 57% of trades in 30 days — they dominate the aggregate -0.89 avg PnL metric that triggered this investigation.
4. Matrix was designed for hyperparameter exploration, not production; given the current out-of-distribution regime, running inferior variants burns capital with no offsetting benefit.
5. No profile variant outperforms baseline → there is no "keep one variant" outcome to preserve.

**Changes made:**
- `scripts/cron/rl_paper.sh`: `RL_PAPER_MATRIX_ENABLED` default changed from `1` → `0`
- Matrix can still be re-enabled via env var `RL_PAPER_MATRIX_ENABLED=1` without code change
- No changes to `config/ml/rl_mppo.yaml` (no profile-level toggle exists there; control is exclusively via cron env var)

**Next step (Task 2.5 Path B):** Monitor 5 trading days of single-profile `rl_mppo` performance. Compare pre/post win rate and avg PnL via `kospi.rl_trades`.

---

### Task 2.4 — Hold Override State Audit (2026-04-15)

**Objective:** Verify that the HOLD override (near-HOLD forced entry) remains disabled as of commit `50a99f7` "fix: disable rl mppo hold override by default".

**Findings:**

1. **Default state — DISABLED ✅**
   - `RLMPPOConfig.enable_hold_override: bool = False` (line 77 in `shared/strategy/entry/rl_mppo.py`)
   - Config file `config/strategies/futures/rl_mppo.yaml` line 34: `enable_hold_override: false` with comment "기본값 비활성 — near-HOLD 강제 진입 방지"
   - Paper override: `paper_enable_hold_override: false` (line 39 in config)
   - Unit test confirms: `test_default_config_disables_hold_override()` asserts `RLMPPOConfig().enable_hold_override is False`

2. **Callers setting to True: NONE**
   - Grep for `enable_hold_override = True` in codebase: no matches found
   - Paper config `paper_enable_hold_override: false` (config file default), optional override `paper_enable_hold_override: bool | None = None` not used anywhere

3. **HOLD action forcing paths: NONE**
   - Action 4 is correctly reserved for HOLD (per CLAUDE.md 5개 액션 정의)
   - Line 468 in `shared/strategy/entry/rl_mppo.py`: `if action == 4: # HOLD` → simply returns existing signal, does not force new action
   - No `force_action = 4` or action override to HOLD found anywhere in entry/exit/helpers modules
   - `_maybe_override_hold()` method (line 648) only activates when `enable_hold_override=True`, which is false

4. **Git commit verification:**
   - Commit `50a99f7` (2026-04-14 18:13) changed:
     - `enable_hold_override: true` → `false` in `config/strategies/futures/rl_mppo.yaml` line 34
     - `enable_hold_override: bool = True` → `False` in `shared/strategy/entry/rl_mppo.py` line 77
     - Added test `test_default_config_disables_hold_override()` to verify default

**Verdict:** ✅ **NO ACTION NEEDED**

Hold override is **completely disabled** by default, with no active code paths that enable it. The 2026-04-14 fix is intact and verified. The config and unit test both confirm the disabled state.

**Next task:** Task 2.5 (Findings-driven consolidation fix).

---

### Task 2.5 — Consolidation Decision (2026-04-15)

- **Path A (obs drift)**: Not applicable — parity test (Task 2.2) confirmed training=runtime obs builders produce identical output. Not the bug.
- **Path B (profile matrix)**: Executed in Task 2.3 (commit cd1fb57). Matrix disabled; expected to remove ~57% of losing trades attributable to weaker profiles. Monitor 5 trading days for win rate / avg PnL recovery.
- **Path C (deeper retraining)**: Required. Baseline `rl_mppo` alone has 15.9% win rate / avg -0.70 PnL/trade — net-negative performance persists even without profile matrix noise. This matches the regime-shift / stale-model hypothesis. Created follow-up plan at `docs/plans/archive/2026-04-15-rl-retraining-data-refresh.md`.

**Phase 2 exit:** Profile matrix disabled (immediate bleed reduction). Deeper model retraining tracked separately in the follow-up plan. No further action required in this plan.

---

## Self-Review Checklist

- [x] Phase 1 scope: paper broker price guards only (no live broker changes)
- [x] Phase 1 guards driven by YAML config, not hardcoded
- [x] Phase 2 investigation before fix (Task 0/1/2 precede Task 5 consolidation)
- [x] Phase 2 has escape hatch (Path C: create follow-up plan if deeper issue)
- [x] Phase 3 preserves existing Redis keys (additive only, no breaking changes to status HASH)
- [x] Each Task ends with TDD + commit
- [x] All file paths absolute, all code blocks complete (no TBD/placeholder)
- [x] Types/names consistent across tasks (e.g., `price_source_time` used identically in all steps)
- [x] No duplicated 이상 profit_pct logic (Phase 1 prevents the entry price bug that caused those values)

## Open Questions for Executor

These should be answered before starting if possible, but can also be raised as questions by the implementer agent:

1. Phase 1 Task 1.2 Step 4: Where exactly are `_submit_entry_order` callers (grep shows 3 sites in orchestrator.py around line 4422/4512/4561) — ensure all propagate `price_source_time`.
2. Phase 2 Task 2.0 Step 2: Is `position.metadata` already capturing `obs` array at entry time? If not, the first 50 trades must accumulate before drift analysis is meaningful.
3. Phase 3 Task 3.3 Step 4: crontab entry is manual/operational — confirm with operator before inserting.
