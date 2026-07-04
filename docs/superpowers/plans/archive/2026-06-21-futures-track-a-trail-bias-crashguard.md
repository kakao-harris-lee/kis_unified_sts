# Futures Track A — Trailing Exit + Daily Directional Bias + Crash Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-06-21-futures-track-a-trail-bias-crashguard-design.md`

**Goal:** Keep mean-reversion entries (Setup A/C); replace the fixed-bracket exit with an ATR trailing exit, add a once-per-day LLM directional bias entry filter, and an ATR-spike crash guard so the normal stop can widen — config-driven, long/short symmetric, paper-only.

**Architecture:** A new `TrackAExit` composed intraday exit (crash → catastrophic → trail → EOD) drops in for `setup_target_exit`; a new `DailyBiasProvider` computes once-per-day direction from LLM context (Redis-persisted, TTL=EOD); the Setup A/C entry adapters gain a bias filter after existing gates. Crash cooldown reuses the orchestrator's existing reentry guard via `ExitReason.FORCE_CLOSE`.

**Tech Stack:** Python 3.12, async/await, pytest + pytest-asyncio, `fakeredis`, dataclass+`ConfigMixin` (exit) / Pydantic `ServiceConfigBase` (entry), `ExitSignalGenerator[TConfig]`, `ExitRegistry`.

## Global Constraints

- **Config-driven only.** All thresholds, enable flags, Redis keys in YAML/env. No hardcoded values in logic modules.
- **Long/short symmetry.** Every exit/filter treats long and short identically; favorable extreme = `highest_price` (LONG) / `lowest_price` (SHORT).
- **KST for all time logic.** `now_kst()`, `to_kst()`, `effective_close_time()` from `shared/strategy/market_time.py`.
- **Redis DB 1.** New keys need TTLs: `trading:futures:daily_bias` TTL=EOD; `trading:futures:setup_eval` TTL 86400s (existing).
- **Paper-only.** No live without Phase-5 gates (`config/futures_live.yaml::enabled` + Redis `futures:live:suspended`). `enabled:false` on the new YAML blocks restores legacy `setup_target_exit`.
- **No ClickHouse, no RL.**
- **DRY.** Bias filter reuses `_publish_setup_eval()` / `SETUP_EVAL_KEY`; regime veto reuses `llm_tuning.long_blocked_regimes`; crash cooldown reuses `entry_reentry_guard`.
- **Test runner:** `.venv/bin/pytest` (not system pytest). Async tests `@pytest.mark.asyncio`. Redis tests use `fakeredis`.
- **Rollback:** set `enabled:false`/`type: setup_target_exit` on the new YAML blocks.

## Resolved Interface Notes (verified 2026-06-21 against the codebase — supersede any assumption in task bodies)

- **`ExitReason`** (`shared/models/signal.py`): `FORCE_CLOSE="force_close"`, `TRAILING_STOP`, `STOP_LOSS`, `EOD_CLOSE`, `TARGET_REACHED`, `TIME_CUT` all exist. Crash uses `FORCE_CLOSE`.
- **`Position`** (`shared/models/position.py`): `highest_price` and `lowest_price` (default `inf`, reset to `entry_price` in post-init); `update_price()` tracks both. SHORT trailing uses `lowest_price`.
- **`acquire_infra_clients()`** (`shared/strategy/gates/adapter_helper.py`) → `(redis|None, event_reader|None)`; never raises. Patch this symbol in `DailyBiasProvider` tests.
- **Registry** (`shared/strategy/registry.py`): `ExitRegistry.register_class/.is_registered/.create/.clear`; `StrategyFactory.create_from_file(asset,name)`; `register_builtin_components()`. Strategy YAML loads via `shared/config/loader.py::load_strategy` / `load_strategy_config(asset,name)` — verify exact callable at Task 5a.
- **Adapter symbols** (`shared/strategy/entry/setup_adapters.py`): `SETUP_EVAL_KEY="trading:futures:setup_eval"`, `_publish_setup_eval(name,outcome,reason)`, `_get_llm_context(context)`, `llm_tuning.long_blocked_regimes`, `SetupAEntryConfig`, `SetupCEntryConfig`, `decision_signal.direction` ("long"/"short"). `atr_14` computed via `_get_float(["atr","atr_14","atr14"])`.
- **Q1 entry_atr (concrete):** orchestrator copies a fixed key list from `signal_meta`→`pos_metadata` at `services/trading/orchestrator.py:~7092` (`pos_metadata[key]=signal_meta[key]`). Make the exit ATR fallback live by (a) adapter emitting `entry_atr=atr_14` in signal metadata and (b) adding `"entry_atr"` to that key list. **Folded into Task 2.**
- **Q4 exit ATR:** exits read `atr` from per-symbol `market_data` (pattern: `shared/strategy/exit/mean_reversion_exit.py:277-279`); `TrackAExit._get_atr()` prefers snapshot ATR, falls back to `position.metadata["entry_atr"]`. Entry-time ATR is **static for the hold** (documented v1 simplification).
- **Q3 crash cooldown:** `config/execution.yaml:35 entry_reentry_guard.reason_cooldown_seconds` read by `EntryReentryGuardConfig.from_dict()` (`orchestrator.py:129`), keyed by exit-reason string. Add `force_close: 1800`. Verify nesting at Task 5e.
- **Q2 bias_min_confidence:** config-driven via new `daily_bias_min_confidence` field on `SetupAEntryConfig`/`SetupCEntryConfig` (default 0.5), passed to `DailyBiasProvider`.

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `shared/decision/daily_bias.py` | CREATE | `DailyBiasProvider`: pure mapping + Redis persist/read |
| `shared/strategy/exit/track_a_exit.py` | CREATE | `TrackAExit`: trailing + crash + catastrophic + EOD |
| `shared/strategy/entry/setup_adapters.py` | EDIT | bias filter; `daily_bias_*` fields; emit `entry_atr` |
| `services/trading/orchestrator.py` | EDIT | add `"entry_atr"` to signal→position metadata copy (~L7092) |
| `shared/strategy/registry.py` | EDIT | register `"track_a_exit"` |
| `config/strategies/futures/track_a_exit.yaml` | CREATE | shared Track A knobs |
| `config/strategies/futures/setup_a_gap_reversion.yaml` | EDIT | exit → `track_a_exit`; `daily_bias_filter_enabled: true` |
| `config/strategies/futures/setup_c_event_reaction.yaml` | EDIT | same |
| `config/execution.yaml` | EDIT | `entry_reentry_guard.reason_cooldown_seconds.force_close: 1800` |
| `tests/unit/decision/test_daily_bias.py` | CREATE | DailyBiasProvider tests |
| `tests/unit/strategy/exit/test_track_a_exit.py` | CREATE | TrackAExit tests |
| `tests/unit/strategy/entry/test_setup_adapters_bias.py` | CREATE | bias filter tests |
| `tests/unit/strategy/test_track_a_wiring.py` | CREATE | registry + YAML + integration smoke |

---

## Task 1 — Pure trailing math + crash detection helpers

**Files:** Create `shared/strategy/exit/track_a_exit.py` (helpers + config + class stub); Test `tests/unit/strategy/exit/test_track_a_exit.py`.

**Produces:** `trail_stop_price(side, favorable_extreme, atr, trail_atr_mult)`, `trail_activated(side, entry_price, favorable_extreme, atr, trail_activate_atr_mult)`, `crash_triggered(side, current_price, prev_price, atr, crash_atr_mult)`, `catastrophic_stop_hit(side, entry_price, current_price, atr, catastrophic_atr_mult)`, `TrackAExitConfig`, `TrackAExit` (stub).

- [ ] **Step 1a — Write failing tests** `tests/unit/strategy/exit/test_track_a_exit.py`:

```python
"""Unit tests for TrackAExit pure math helpers."""
from __future__ import annotations
import pytest
from shared.models.position import PositionSide
from shared.strategy.exit.track_a_exit import (
    catastrophic_stop_hit, crash_triggered, trail_activated, trail_stop_price,
)

def test_trail_stop_long():
    assert trail_stop_price(PositionSide.LONG, favorable_extreme=105.0, atr=2.0, trail_atr_mult=3.0) == pytest.approx(99.0)
def test_trail_stop_short():
    assert trail_stop_price(PositionSide.SHORT, favorable_extreme=95.0, atr=2.0, trail_atr_mult=3.0) == pytest.approx(101.0)
def test_trail_not_activated_at_entry_long():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=100.0, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_trail_activated_long():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=102.5, atr=2.0, trail_activate_atr_mult=1.0) is True
def test_trail_not_activated_long_below_threshold():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=101.5, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_trail_activated_short():
    assert trail_activated(PositionSide.SHORT, entry_price=100.0, favorable_extreme=97.5, atr=2.0, trail_activate_atr_mult=1.0) is True
def test_trail_not_activated_short_adverse():
    assert trail_activated(PositionSide.SHORT, entry_price=100.0, favorable_extreme=102.0, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_crash_triggered_long():
    assert crash_triggered(PositionSide.LONG, current_price=93.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is True
def test_crash_not_triggered_long_small_move():
    assert crash_triggered(PositionSide.LONG, current_price=97.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is False
def test_crash_triggered_short():
    assert crash_triggered(PositionSide.SHORT, current_price=107.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is True
def test_crash_not_triggered_on_favorable_spike_long():
    assert crash_triggered(PositionSide.LONG, current_price=103.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is False
def test_catastrophic_long():
    assert catastrophic_stop_hit(PositionSide.LONG, entry_price=100.0, current_price=88.0, atr=2.0, catastrophic_atr_mult=6.0) is True
def test_catastrophic_short():
    assert catastrophic_stop_hit(PositionSide.SHORT, entry_price=100.0, current_price=112.0, atr=2.0, catastrophic_atr_mult=6.0) is True
def test_catastrophic_not_triggered_within_threshold():
    assert catastrophic_stop_hit(PositionSide.LONG, entry_price=100.0, current_price=90.0, atr=2.0, catastrophic_atr_mult=6.0) is False
```

- [ ] **Step 1b — Run (expect FAIL):** `.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py -x -v 2>&1 | head -30` → `ModuleNotFoundError: shared.strategy.exit.track_a_exit`.

- [ ] **Step 1c — Implement** `shared/strategy/exit/track_a_exit.py` (helpers + config + stub):

```python
"""Track A composed exit: ATR trailing + crash guard + catastrophic backstop + EOD.

Replaces ``setup_target_exit`` for futures Setup A/C.
Precedence: crash guard → catastrophic backstop → trail stop → EOD.
Long/short symmetric; all thresholds config-driven.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import time
from typing import Any
from shared.config.mixins import ConfigMixin
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason, ExitSignal
from shared.strategy.base import ExitContext, ExitSignalGenerator, MarketStateProtocol
from shared.strategy.market_data import get_price_from_snapshot, get_symbol_snapshot
from shared.strategy.market_time import effective_close_time, is_trading_day_kst, now_kst, to_kst

logger = logging.getLogger(__name__)


def trail_stop_price(side: PositionSide, favorable_extreme: float, atr: float, trail_atr_mult: float) -> float:
    """LONG: extreme - mult*atr ; SHORT: extreme + mult*atr."""
    offset = trail_atr_mult * atr
    return favorable_extreme - offset if side == PositionSide.LONG else favorable_extreme + offset


def trail_activated(side: PositionSide, entry_price: float, favorable_extreme: float, atr: float, trail_activate_atr_mult: float) -> bool:
    """True when profit in ATR units >= trail_activate_atr_mult."""
    threshold = trail_activate_atr_mult * atr
    if side == PositionSide.LONG:
        return (favorable_extreme - entry_price) >= threshold
    return (entry_price - favorable_extreme) >= threshold


def crash_triggered(side: PositionSide, current_price: float, prev_price: float, atr: float, crash_atr_mult: float) -> bool:
    """True when a single adverse move >= crash_atr_mult*atr."""
    threshold = crash_atr_mult * atr
    if side == PositionSide.LONG:
        return (prev_price - current_price) >= threshold
    return (current_price - prev_price) >= threshold


def catastrophic_stop_hit(side: PositionSide, entry_price: float, current_price: float, atr: float, catastrophic_atr_mult: float) -> bool:
    """True when loss from entry >= catastrophic_atr_mult*atr."""
    threshold = catastrophic_atr_mult * atr
    if side == PositionSide.LONG:
        return (entry_price - current_price) >= threshold
    return (current_price - entry_price) >= threshold


@dataclass
class TrackAExitConfig(ConfigMixin):
    trail_atr_mult: float = 3.0
    trail_activate_atr_mult: float = 1.0
    crash_atr_mult: float = 3.5
    crash_cooldown_minutes: int = 30
    catastrophic_atr_mult: float = 6.0
    eod_close_enabled: bool = True
    eod_close_hour: int = 15
    eod_close_minute: int = 15
    default_exit_confidence: float = 0.9
    enabled: bool = True

    @property
    def eod_close_time(self) -> time:
        return time(self.eod_close_hour, self.eod_close_minute)

    def validate(self) -> None:
        assert self.trail_atr_mult > 0
        assert self.trail_activate_atr_mult >= 0
        assert self.crash_atr_mult > 0
        assert self.crash_cooldown_minutes >= 0
        assert self.catastrophic_atr_mult > 0
        assert 0.0 < self.default_exit_confidence <= 1.0


class TrackAExit(ExitSignalGenerator[TrackAExitConfig]):
    """Placeholder — full implementation in Task 2."""
    CONFIG_CLASS = TrackAExitConfig

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "track_a_exit"

    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        raise NotImplementedError

    async def scan_positions(self, positions: list[Position], market_data: dict[str, Any], market_state: MarketStateProtocol | None = None) -> list[ExitSignal]:
        raise NotImplementedError
```

- [ ] **Step 1d — Run (expect PASS):** `.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py -x -v` → 14 math tests green.
- [ ] **Step 1e — Commit:** `feat(futures): Track A pure math helpers (trail/crash/catastrophic)` (+ Co-Authored-By footer).

---

## Task 2 — `TrackAExit` generator + `entry_atr` wiring

**Files:** complete `shared/strategy/exit/track_a_exit.py`; extend `tests/unit/strategy/exit/test_track_a_exit.py`; EDIT `shared/strategy/entry/setup_adapters.py` (emit `entry_atr`) + `services/trading/orchestrator.py:~7092` (copy `entry_atr`).

**Precedence:** crash `FORCE_CLOSE` p1 (`exit_type="crash_guard"`) > catastrophic `STOP_LOSS` p2 (`"catastrophic_stop"`) > trail `TRAILING_STOP` p3 (`"trail_stop"`) > EOD `EOD_CLOSE` p4 (`"eod_close"`). `prev_price` read from then written to `position.metadata["prev_price"]` each tick. Favorable extreme = `highest_price`/`lowest_price`. ATR: snapshot then `position.metadata["entry_atr"]` fallback; ATR=0 → skip ATR exits, only EOD.

- [ ] **Step 2a — Append generator tests** to `tests/unit/strategy/exit/test_track_a_exit.py`:

```python
from datetime import UTC, datetime, timedelta
from shared.models.position import Position, PositionSide
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.track_a_exit import TrackAExit, TrackAExitConfig

def _long_position(entry_price=100.0, highest_price=None, stop_price=0.0, **md):
    meta = {"entry_atr": 2.0, "prev_price": entry_price, **md}
    return Position(id="pos-long-1", code="A05603", name="KOSPI200 Mini", side=PositionSide.LONG,
        quantity=1, entry_price=entry_price, entry_time=datetime.now(UTC) - timedelta(minutes=30),
        current_price=entry_price, stop_price=stop_price,
        highest_price=highest_price if highest_price is not None else entry_price, metadata=meta)

def _short_position(entry_price=100.0, lowest_price=None, stop_price=0.0, **md):
    meta = {"entry_atr": 2.0, "prev_price": entry_price, **md}
    return Position(id="pos-short-1", code="A05603", name="KOSPI200 Mini", side=PositionSide.SHORT,
        quantity=1, entry_price=entry_price, entry_time=datetime.now(UTC) - timedelta(minutes=30),
        current_price=entry_price, stop_price=stop_price,
        lowest_price=lowest_price if lowest_price is not None else entry_price, metadata=meta)

def _cfg(**kw):
    d = dict(trail_atr_mult=3.0, trail_activate_atr_mult=1.0, crash_atr_mult=3.5, crash_cooldown_minutes=30,
        catastrophic_atr_mult=6.0, eod_close_enabled=False, default_exit_confidence=0.9, enabled=True)
    d.update(kw)
    return TrackAExitConfig(**d)

def _ctx(position, close, atr=2.0):
    return ExitContext(position=position, market_data={"close": close, "atr": atr}, timestamp=datetime.now(UTC))

@pytest.mark.asyncio
async def test_crash_guard_long_fires():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=100.0), close=92.0))
    assert fired and sig.reason == ExitReason.FORCE_CLOSE and sig.priority == 1 and sig.metadata.get("exit_type") == "crash_guard"
@pytest.mark.asyncio
async def test_crash_guard_short_fires():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_short_position(prev_price=100.0), close=108.0))
    assert fired and sig.reason == ExitReason.FORCE_CLOSE
@pytest.mark.asyncio
async def test_crash_guard_no_trigger_on_favorable_spike():
    fired, _ = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=100.0), close=108.0))
    assert fired is False
@pytest.mark.asyncio
async def test_catastrophic_stop_long():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=99.0), close=88.0))
    assert fired and sig.reason == ExitReason.STOP_LOSS and sig.priority == 2 and sig.metadata.get("exit_type") == "catastrophic_stop"
@pytest.mark.asyncio
async def test_catastrophic_stop_short():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_short_position(prev_price=101.0), close=112.0))
    assert fired and sig.reason == ExitReason.STOP_LOSS
@pytest.mark.asyncio
async def test_trail_not_activated_before_threshold():
    fired, _ = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=101.0, prev_price=101.0), close=99.5))
    assert fired is False
@pytest.mark.asyncio
async def test_trail_fires_after_activation_long():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=106.0, prev_price=105.0), close=99.0))
    assert fired and sig.reason == ExitReason.TRAILING_STOP and sig.priority == 3 and sig.metadata.get("exit_type") == "trail_stop"
@pytest.mark.asyncio
async def test_trail_does_not_fire_above_trail_long():
    fired, _ = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=106.0, prev_price=105.0), close=100.5))
    assert fired is False
@pytest.mark.asyncio
async def test_trail_fires_short():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_short_position(lowest_price=94.0, prev_price=95.0), close=101.0))
    assert fired and sig.reason == ExitReason.TRAILING_STOP
@pytest.mark.asyncio
async def test_crash_takes_precedence_over_catastrophic():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(prev_price=100.0), close=86.0))
    assert fired and sig.reason == ExitReason.FORCE_CLOSE and sig.priority == 1
@pytest.mark.asyncio
async def test_catastrophic_beats_trail():
    fired, sig = await TrackAExit(_cfg()).should_exit(_ctx(_long_position(highest_price=110.0, prev_price=100.0), close=88.0))
    assert fired and sig.reason == ExitReason.STOP_LOSS and sig.priority == 2
@pytest.mark.asyncio
async def test_no_atr_skips_all_atr_exits():
    pos = _long_position(prev_price=70.0); pos.metadata.pop("entry_atr", None)
    fired, _ = await TrackAExit(_cfg(eod_close_enabled=False)).should_exit(_ctx(pos, close=70.0, atr=0.0))
    assert fired is False
@pytest.mark.asyncio
async def test_scan_positions_returns_signals_for_triggered():
    signals = await TrackAExit(_cfg()).scan_positions(positions=[_long_position(prev_price=100.0)], market_data={"A05603": {"close": 92.0, "atr": 2.0}})
    assert len(signals) == 1 and signals[0].reason == ExitReason.FORCE_CLOSE
```

- [ ] **Step 2b — Run (expect FAIL):** `.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py::test_crash_guard_long_fires -x -v` → `NotImplementedError`.

- [ ] **Step 2c — Implement** `TrackAExit` (replace the stub body) with `should_exit`, `scan_positions`, `_check_position`, `_get_atr`, `_should_eod_close`, `_calc_profit_pct/_amount`, `_create_exit_signal`:

```python
    async def should_exit(self, context: ExitContext) -> tuple[bool, ExitSignal | None]:
        signal = self._check_position(context.position, context.market_data or {})
        return (signal is not None, signal)

    async def scan_positions(self, positions, market_data, market_state=None):
        signals: list[ExitSignal] = []
        for position in positions:
            snapshot = get_symbol_snapshot(market_data, position.code)
            signal = self._check_position(position, snapshot)
            if signal is not None:
                signals.append(signal)
        return signals

    def _check_position(self, position, snapshot):
        current_price = get_price_from_snapshot(snapshot)
        if current_price is None:
            current_price = position.current_price if position.current_price > 0 else None
        if current_price is None or position.entry_price <= 0:
            return None
        now = now_kst()
        atr = self._get_atr(snapshot, position)
        prev_price = float(position.metadata.get("prev_price", current_price))
        profit_pct = self._calc_profit_pct(position, current_price)
        profit_amount = self._calc_profit_amount(position, current_price)
        holding_minutes = int((to_kst(now) - to_kst(position.entry_time)).total_seconds() / 60)
        favorable_extreme = position.highest_price if position.side == PositionSide.LONG else position.lowest_price
        position.metadata["prev_price"] = current_price  # update before any return

        if atr > 0 and crash_triggered(position.side, current_price, prev_price, atr, self.config.crash_atr_mult):
            return self._create_exit_signal(position=position, current_price=current_price, profit_pct=profit_pct,
                profit_amount=profit_amount, reason=ExitReason.FORCE_CLOSE, priority=1, holding_minutes=holding_minutes,
                metadata={"exit_type": "crash_guard", "prev_price": prev_price, "atr": atr,
                          "crash_cooldown_minutes": self.config.crash_cooldown_minutes})
        if atr > 0 and catastrophic_stop_hit(position.side, position.entry_price, current_price, atr, self.config.catastrophic_atr_mult):
            return self._create_exit_signal(position=position, current_price=current_price, profit_pct=profit_pct,
                profit_amount=profit_amount, reason=ExitReason.STOP_LOSS, priority=2, holding_minutes=holding_minutes,
                metadata={"exit_type": "catastrophic_stop", "atr": atr})
        if atr > 0 and trail_activated(position.side, position.entry_price, favorable_extreme, atr, self.config.trail_activate_atr_mult):
            trail = trail_stop_price(position.side, favorable_extreme, atr, self.config.trail_atr_mult)
            crossed = current_price <= trail if position.side == PositionSide.LONG else current_price >= trail
            if crossed:
                return self._create_exit_signal(position=position, current_price=current_price, profit_pct=profit_pct,
                    profit_amount=profit_amount, reason=ExitReason.TRAILING_STOP, priority=3, holding_minutes=holding_minutes,
                    metadata={"exit_type": "trail_stop", "trail_price": trail, "favorable_extreme": favorable_extreme, "atr": atr})
        if self._should_eod_close(now):
            return self._create_exit_signal(position=position, current_price=current_price, profit_pct=profit_pct,
                profit_amount=profit_amount, reason=ExitReason.EOD_CLOSE, priority=4, holding_minutes=holding_minutes,
                metadata={"exit_type": "eod_close"})
        return None

    def _get_atr(self, snapshot, position):
        for key in ("atr", "atr_14", "atr14"):
            val = snapshot.get(key)
            if val is not None:
                try:
                    f = float(val)
                    if f > 0:
                        return f
                except (TypeError, ValueError):
                    pass
        entry_atr = position.metadata.get("entry_atr")
        if entry_atr is not None:
            try:
                f = float(entry_atr)
                if f > 0:
                    return f
            except (TypeError, ValueError):
                pass
        return 0.0

    def _should_eod_close(self, now):
        if not self.config.eod_close_enabled:
            return False
        now_local = to_kst(now)
        if not is_trading_day_kst(now_local):
            return False
        return now_local.time() >= effective_close_time(self.config.eod_close_time)

    @staticmethod
    def _calc_profit_pct(position, current_price):
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) / position.entry_price
        return (current_price - position.entry_price) / position.entry_price

    @staticmethod
    def _calc_profit_amount(position, current_price):
        if position.side == PositionSide.SHORT:
            return (position.entry_price - current_price) * position.quantity
        return (current_price - position.entry_price) * position.quantity

    def _create_exit_signal(self, *, position, current_price, profit_pct, profit_amount, reason, priority, holding_minutes, metadata):
        logger.info("[%s] Exit: %s reason=%s price=%.2f pnl=%+.2f%%", self.name, position.code, reason.value, current_price, profit_pct * 100)
        return ExitSignal(code=position.code, name=position.name, position_id=position.id, reason=reason,
            strategy=self.name, current_price=current_price, exit_price=current_price, entry_price=position.entry_price,
            profit_amount=profit_amount, profit_pct=profit_pct, confidence=self.config.default_exit_confidence,
            priority=priority, timestamp=now_kst(), stage=PositionState.SURVIVAL.value,
            high_since_entry=position.highest_price, holding_minutes=holding_minutes, quantity=position.quantity, metadata=metadata)
```

- [ ] **Step 2d — Wire `entry_atr`:** in `setup_adapters.py`, where the entry signal metadata is built (the dict carrying `stop_loss`/`take_profit`), add `"entry_atr": atr_14`. In `services/trading/orchestrator.py:~7092`, add `"entry_atr"` to the key list copied `signal_meta`→`pos_metadata`. (Read the exact list first; append the string.)
- [ ] **Step 2e — Run (expect PASS):** `.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py -x -v` → 27 tests green.
- [ ] **Step 2f — Commit:** `feat(futures): TrackAExit generator + entry_atr wiring` (+ footer).

---

## Task 3 — `DailyBiasProvider`

**Files:** Create `shared/decision/daily_bias.py`, `tests/unit/decision/test_daily_bias.py`. **Consumes:** LLM context (`overall_signal.name`, `confidence`, `regime`), `acquire_infra_clients`, `now_kst`. **Produces:** `bias_from_context(...) -> "long"|"short"|"flat"`, `DailyBiasProvider(bias_min_confidence, non_long_regimes).get_or_compute_bias(market_context, now_kst_dt)`.

- [ ] **Step 3a — Failing tests** `tests/unit/decision/test_daily_bias.py`:

```python
"""Unit tests for DailyBiasProvider."""
from __future__ import annotations
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
import pytest
from shared.decision.daily_bias import DailyBiasProvider, bias_from_context

def test_strong_bullish_maps_to_long(): assert bias_from_context("STRONG_BULLISH", confidence=0.7) == "long"
def test_bullish_maps_to_long(): assert bias_from_context("BULLISH", confidence=0.7) == "long"
def test_strong_bearish_maps_to_short(): assert bias_from_context("STRONG_BEARISH", confidence=0.7) == "short"
def test_bearish_maps_to_short(): assert bias_from_context("BEARISH", confidence=0.7) == "short"
def test_neutral_maps_to_flat(): assert bias_from_context("NEUTRAL", confidence=0.7) == "flat"
def test_low_confidence_maps_to_flat(): assert bias_from_context("STRONG_BULLISH", confidence=0.3, bias_min_confidence=0.5) == "flat"
def test_confidence_exactly_at_threshold_passes(): assert bias_from_context("BULLISH", confidence=0.5, bias_min_confidence=0.5) == "long"
def test_non_long_regime_converts_long_to_flat(): assert bias_from_context("STRONG_BULLISH", confidence=0.8, non_long_regimes=["BEAR_STRONG"], regime="BEAR_STRONG") == "flat"
def test_non_long_regime_does_not_affect_short(): assert bias_from_context("STRONG_BEARISH", confidence=0.8, non_long_regimes=["BEAR_STRONG"], regime="BEAR_STRONG") == "short"
def test_non_long_regime_not_matching_passes_through(): assert bias_from_context("BULLISH", confidence=0.8, non_long_regimes=["BEAR_STRONG"], regime="BULL_STRONG") == "long"

def _fake_context(name="BULLISH", confidence=0.7):
    ctx = MagicMock(); ctx.confidence = confidence; ctx.overall_signal.name = name; ctx.regime = "NEUTRAL"; return ctx
def _now_kst(): return datetime(2026, 6, 21, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

def test_compute_and_persist_first_call():
    import fakeredis, json
    r = fakeredis.FakeRedis(); p = DailyBiasProvider(bias_min_confidence=0.5)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        assert p.get_or_compute_bias(_fake_context("BULLISH", 0.8), _now_kst()) == "long"
    stored = json.loads(r.get("trading:futures:daily_bias")); assert stored["bias"] == "long" and "computed_at" in stored
def test_idempotent_second_call_reads_redis():
    import fakeredis, json
    r = fakeredis.FakeRedis(); r.set("trading:futures:daily_bias", json.dumps({"bias": "short", "computed_at": "2026-06-21T10:00:00+09:00", "date": "2026-06-21"}), ex=3600)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("BULLISH", 0.9), _now_kst()) == "short"
def test_stale_date_forces_recompute():
    import fakeredis, json
    r = fakeredis.FakeRedis(); r.set("trading:futures:daily_bias", json.dumps({"bias": "short", "computed_at": "2026-06-20T10:00:00+09:00", "date": "2026-06-20"}), ex=3600)
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("STRONG_BULLISH", 0.9), _now_kst()) == "long"
def test_redis_unavailable_falls_back_to_flat():
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(None, None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("BULLISH", 0.9), _now_kst()) == "flat"
def test_no_context_returns_flat():
    import fakeredis
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(fakeredis.FakeRedis(), None)):
        assert DailyBiasProvider(0.5).get_or_compute_bias(None, _now_kst()) == "flat"
def test_ttl_set_to_eod():
    import fakeredis
    r = fakeredis.FakeRedis()
    with patch("shared.decision.daily_bias.acquire_infra_clients", return_value=(r, None)):
        DailyBiasProvider(0.5).get_or_compute_bias(_fake_context("BULLISH", 0.8), _now_kst())
    assert r.ttl("trading:futures:daily_bias") > 0
```

- [ ] **Step 3b — Run (FAIL):** `.venv/bin/pytest tests/unit/decision/test_daily_bias.py -x -v 2>&1 | head -20`.
- [ ] **Step 3c — Implement** `shared/decision/daily_bias.py`:

```python
"""Daily directional bias from LLM market context (compute-once, Redis-persisted)."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo
from shared.strategy.gates.adapter_helper import acquire_infra_clients

logger = logging.getLogger(__name__)
DAILY_BIAS_KEY = "trading:futures:daily_bias"
_LONG_SIGNALS = {"STRONG_BULLISH", "BULLISH"}
_SHORT_SIGNALS = {"STRONG_BEARISH", "BEARISH"}
_KST = ZoneInfo("Asia/Seoul")


def bias_from_context(overall_signal_name, confidence, bias_min_confidence=0.5, non_long_regimes=None, regime=""):
    if confidence < bias_min_confidence:
        return "flat"
    signal = overall_signal_name.upper()
    if signal in _LONG_SIGNALS:
        raw: Literal["long", "short", "flat"] = "long"
    elif signal in _SHORT_SIGNALS:
        raw = "short"
    else:
        return "flat"
    if raw == "long" and non_long_regimes and regime in non_long_regimes:
        return "flat"
    return raw


def _eod_ttl_seconds(now: datetime) -> int:
    eod = datetime(now.year, now.month, now.day, 15, 45, 0, tzinfo=_KST)
    return max(60, int((eod - now).total_seconds()))


class DailyBiasProvider:
    def __init__(self, bias_min_confidence: float = 0.5, non_long_regimes: list[str] | None = None) -> None:
        self._bias_min_confidence = bias_min_confidence
        self._non_long_regimes = non_long_regimes or []

    def get_or_compute_bias(self, market_context: Any | None, now_kst_dt: datetime) -> Literal["long", "short", "flat"]:
        today_str = now_kst_dt.date().isoformat()
        cached = self._read_redis(today_str)
        if cached is not None:
            return cached
        if market_context is None:
            return "flat"
        try:
            name = market_context.overall_signal.name
            confidence = float(market_context.confidence)
            regime = str(getattr(market_context, "regime", ""))
        except (AttributeError, TypeError, ValueError) as exc:
            logger.warning("[DailyBias] bad market_context: %s", exc)
            return "flat"
        bias = bias_from_context(name, confidence, self._bias_min_confidence, self._non_long_regimes, regime)
        logger.info("[DailyBias] %s (signal=%s conf=%.2f regime=%s)", bias, name, confidence, regime)
        self._write_redis(bias, now_kst_dt)
        return bias

    def _read_redis(self, today_str):
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return None
            raw = redis.get(DAILY_BIAS_KEY)
            if raw is None:
                return None
            data = json.loads(raw)
            if data.get("date") != today_str:
                return None
            bias = data.get("bias")
            return bias if bias in ("long", "short", "flat") else None
        except Exception:
            logger.debug("[DailyBias] read failed", exc_info=True)
            return None

    def _write_redis(self, bias, now_kst_dt):
        try:
            redis, _ = acquire_infra_clients()
            if redis is None:
                return
            payload = json.dumps({"bias": bias, "computed_at": now_kst_dt.isoformat(), "date": now_kst_dt.date().isoformat()})
            redis.set(DAILY_BIAS_KEY, payload, ex=_eod_ttl_seconds(now_kst_dt))
        except Exception:
            logger.debug("[DailyBias] write failed", exc_info=True)
```

- [ ] **Step 3d — Run (PASS):** `.venv/bin/pytest tests/unit/decision/test_daily_bias.py -x -v` → 17 tests green.
- [ ] **Step 3e — Commit:** `feat(futures): DailyBiasProvider — once-per-day bias from LLM context` (+ footer).

---

## Task 4 — Entry bias filter in `setup_adapters.py`

Add to `SetupAEntryConfig`/`SetupCEntryConfig`: `daily_bias_filter_enabled: bool = Field(default=True)` and `daily_bias_min_confidence: float = Field(default=0.5)`. In each adapter `__init__`: `self._daily_bias_provider = DailyBiasProvider(bias_min_confidence=config.daily_bias_min_confidence, non_long_regimes=list(config.llm_tuning.long_blocked_regimes))`. After the RegimeGate block in `generate()` (before the fired-publish):

```python
        if self.config.daily_bias_filter_enabled:
            bias = self._daily_bias_provider.get_or_compute_bias(_get_llm_context(context), now_kst())
            direction = decision_signal.direction
            if bias == "flat":
                _publish_setup_eval(self.name, "reject", "daily_bias_flat")
                return None
            if direction != bias:
                _publish_setup_eval(self.name, "reject", "daily_bias_misaligned")
                return None
```

- [ ] **Step 4a — Failing tests** `tests/unit/strategy/entry/test_setup_adapters_bias.py` (flat blocks, misaligned blocks short-when-bias-long, disabled bypasses `get_or_compute_bias`, both reject reasons published via patched `_publish_setup_eval`). Use `SetupAEntryAdapter` with `llm_tuning.enabled=False`, patch `adapter._daily_bias_provider.get_or_compute_bias` and `adapter._setup.check`. (Test bodies in the design draft; mirror the 5 cases.)
- [ ] **Step 4b — Run (FAIL):** `.venv/bin/pytest tests/unit/strategy/entry/test_setup_adapters_bias.py -x -v 2>&1 | head -20`.
- [ ] **Step 4c — Implement** the config fields, `__init__` wiring, import (`from shared.decision.daily_bias import DailyBiasProvider`, `now_kst`), and the gate block in BOTH adapters.
- [ ] **Step 4d — Run (PASS):** `.venv/bin/pytest tests/unit/strategy/entry/test_setup_adapters_bias.py tests/unit/strategy/ -k setup -x -v`.
- [ ] **Step 4e — Commit:** `feat(futures): daily bias filter in setup_adapters` (+ footer).

---

## Task 5 — Config YAML + registry + execution.yaml cooldown

- [ ] **Step 5a — Failing wiring tests** `tests/unit/strategy/test_track_a_wiring.py`: `track_a_exit` registered after `register_builtin_components()`; `ExitRegistry.create("track_a_exit", {}).name == "track_a_exit"`; both setup configs load with `exit.type == "track_a_exit"` (use the verified loader callable); `track_a_exit.yaml` defaults (`trail_atr_mult==3.0`, `crash_atr_mult==3.5`, `catastrophic_atr_mult==6.0`, eod 15:15); `setup_target_exit` still registered (rollback). Run → FAIL.
- [ ] **Step 5b — Create** `config/strategies/futures/track_a_exit.yaml`:
```yaml
track_a_exit:
  params:
    trail_atr_mult: 3.0
    trail_activate_atr_mult: 1.0
    crash_atr_mult: 3.5
    crash_cooldown_minutes: 30
    catastrophic_atr_mult: 6.0
    eod_close_enabled: true
    eod_close_hour: 15
    eod_close_minute: 15
    default_exit_confidence: 0.9
    enabled: true
```
- [ ] **Step 5c — Edit** both `setup_a_gap_reversion.yaml` and `setup_c_event_reaction.yaml`: replace the `exit:` block with `type: track_a_exit` + the params above; add `daily_bias_filter_enabled: true` and `daily_bias_min_confidence: 0.5` to entry params.
- [ ] **Step 5d — Register** in `shared/strategy/registry.py::register_builtin_components()` after the `setup_target_exit` block:
```python
    try:
        from shared.strategy.exit.track_a_exit import TrackAExit
        ExitRegistry.register_class("track_a_exit", TrackAExit)
    except ImportError:
        logger.debug("TrackAExit not available")
```
- [ ] **Step 5e — Edit** `config/execution.yaml` `entry_reentry_guard.reason_cooldown_seconds` (verify exact nesting first): add `force_close: 1800`.
- [ ] **Step 5f — Run (PASS):** `.venv/bin/pytest tests/unit/strategy/test_track_a_wiring.py -x -v` then `.venv/bin/pytest tests/unit/ -q --timeout=60`.
- [ ] **Step 5g — Commit:** `feat(futures): Track A YAML config + registry + cooldown wiring` (+ footer).

---

## Task 6 — Integration smoke

- [ ] Append to `test_track_a_wiring.py`: `StrategyFactory.create_from_file("futures","setup_a_gap_reversion").exit` is `TrackAExit`; `TrackAExit(...).scan_positions([crash long pos], {"A05603": {"close": 362.0, "atr": 2.0}})` emits one `FORCE_CLOSE`. Run (PASS). Commit `test(futures): Track A integration smoke` (+ footer).

---

## Rollback
1. Both setup YAMLs: `exit.type` → `setup_target_exit` (restore original params).
2. `daily_bias_filter_enabled: false` in both entry params.
3. No code change — new modules inert when unreferenced.

## Validation & Promotion (NOT implementation tasks)
1. **Backtest with holdout** (`LookaheadGuard`): `TrackAExit` vs `SetupTargetExit` on the same Setup A/C signals — test the central hypothesis (trailing exit on mean-reversion entry); tune `trail_atr_mult`; consider a momentum-decay assist if trailing exits revert too slowly.
2. **Paper observation** on `trader-futures`: holding-time distribution (target ≫ 5.7-min median), PnL, crash-guard frequency. Observability: `redis-cli -n 1 hgetall trading:futures:setup_eval`, `redis-cli -n 1 get trading:futures:daily_bias`.
3. **No live** without Phase-5 gates + operator written approval.
</content>
