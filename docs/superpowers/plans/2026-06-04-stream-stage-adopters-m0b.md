# StreamStage Adopters — risk_filter + order_router (M0b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the two order-path daemons `risk_filter` and `order_router` onto the shared `StreamStage` base (merged in M0a), deleting their hand-rolled consume loops — behavior-preserving, gated by their existing test suites.

**Architecture:** Each daemon subclasses `StreamStage` (`shared/streaming/stage.py`): the hand-rolled `run()`/`stop()`/`_stop` are deleted; `_process` becomes `handle_message(msg_id, fields) -> bool` (True ⇒ base XACKs; False ⇒ leave pending). risk_filter overrides `on_shutdown` (flush signals_writer). order_router maps its kill-switch sentinel guards to `on_startup` (startup refusal) + `pre_iteration_gate` (mid-run refusal), keeping its counter fields and inline size-clamp / fail-open branches. `_build_and_run`/`main` are UNCHANGED in both.

**Tech Stack:** Python 3.11 asyncio, `redis.asyncio`, pytest + `fakeredis`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (§4.2). This is increment **M0b**. Ingest daemon (M1) is a separate plan.

**StreamStage contract (already on main, do not change):** `__init__(*, redis, input_stream, consumer_group, worker_id, xread_block_ms, batch_size, xreadgroup_error_sleep_seconds=0.5)`; `@final run()` owns the loop (on_startup → xgroup_create → while: pre_iteration_gate, xreadgroup, post_poll(count), per-message handle_message → XACK if True → finally on_shutdown); `stop()` sets `self._stop`; abstract `handle_message(self, msg_id, fields) -> bool`; no-op hooks `on_startup`, `pre_iteration_gate()->bool` (False aborts loop), `post_poll(count)`, `on_shutdown`.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `services/risk_filter/main.py` | Modify | `RiskFilterDaemon(StreamStage)`; `_process`→`handle_message`; `on_shutdown`→flush; delete run/stop/_stop |
| `services/order_router/main.py` | Modify | `OrderRouterDaemon(StreamStage)`; sentinel guards→`on_startup`/`pre_iteration_gate`; `_process`→`handle_message`; delete run/stop/_stop |

Existing test gates (do not modify): `tests/unit/services/test_risk_filter_main.py` (7), `tests/unit/services/test_order_router_main.py` (24). Both use `fakeredis` (no real Redis). Run via the worktree using the main venv: `cd /tmp/m0b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest <path> -q`.

---

## Task A: Migrate `RiskFilterDaemon` onto `StreamStage`

Behavior-preserving refactor; the existing `test_risk_filter_main.py` (7 tests) is the gate.

**Files:** Modify `services/risk_filter/main.py` (`RiskFilterDaemon` class only; module helpers + `_build_and_run`/`main` UNCHANGED).

- [ ] **Step 1: Establish the green baseline**

Run: `cd /tmp/m0b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_risk_filter_main.py -q`
Expected: 7 passed. (If not green at baseline, STOP and report BLOCKED.)

- [ ] **Step 2: Subclass StreamStage + delegate constructor**

(a) Add to the imports near the other `shared` imports at the top of `services/risk_filter/main.py`:
```python
from shared.streaming.stage import StreamStage
```
(b) Change `class RiskFilterDaemon:` to `class RiskFilterDaemon(StreamStage):`.
(c) Replace the `__init__` body so the loop params go to the base. The keyword-only signature stays IDENTICAL (tests construct with these exact kwargs). Replace the whole `__init__` with:
```python
    def __init__(
        self,
        *,
        redis: Any,
        layer: RiskFilterLayer,
        signals_writer: Any,
        runtime_state: RuntimeRiskState,
        candidate_stream: str,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        final_maxlen: int,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=candidate_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.layer = layer
        self.signals_writer = signals_writer
        self.runtime_state = runtime_state
        self.final_stream = final_stream
        self.final_maxlen = final_maxlen
```
> The base now owns `self.redis`, `self.consumer_group`, `self.worker_id`, `self.xread_block_ms`, `self.batch_size`, and exposes the candidate stream as `self.input_stream`. Drop the old `self.redis = ... / self.candidate_stream = ... / self._stop = asyncio.Event()` assignments. Keep `self.final_stream` and `self.final_maxlen` (used by `handle_message`).

- [ ] **Step 3: Delete run/stop; convert `_process` → `handle_message`**

(a) DELETE the existing `async def run(self)` and `async def stop(self)` methods entirely (the base provides both).
(b) Replace `_process` with `handle_message` returning a bool (the base owns XACK). Use EXACTLY:
```python
    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]
    ) -> bool:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
        except Exception:
            logger.exception("Unparseable candidate; ACKing as poison-pill")
            return True  # poison-pill: consume (base XACKs)

        try:
            snapshot = await self.runtime_state.snapshot()
            result = self.layer.evaluate(signal, snapshot)
        except Exception:
            logger.exception(
                "Filter evaluation failed signal_id=%s; leaving pending", signal_id
            )
            return False  # leave pending (base does NOT XACK)

        # Audit row first — every candidate, accepted or rejected.
        try:
            await self.signals_writer.enqueue(
                signal,
                result,
                executed=result.passed,
                signal_id=signal_id,
            )
        except Exception:
            logger.exception(
                "signals_all enqueue failed signal_id=%s; leaving pending", signal_id
            )
            return False

        if result.passed:
            try:
                fields_out = signal.to_stream_dict()
                fields_out["signal_id"] = signal_id
                fields_out["size_multiplier"] = str(result.size_multiplier)
                fields_out["filtered_at_ms"] = str(int(time.time() * 1000))
                await self.redis.xadd(
                    self.final_stream,
                    fields_out,
                    maxlen=self.final_maxlen,
                    approximate=True,
                )
                await self.redis.expire(self.final_stream, _STREAM_TTL_SECONDS)
            except Exception:
                logger.exception(
                    "final stream XADD failed signal_id=%s; leaving pending",
                    signal_id,
                )
                return False

        return True  # passed+XADD ok, or rejected (audit-only): consume
```
> Only changes vs `_process`: renamed to `handle_message`; the two `await self.redis.xack(self.candidate_stream, ...)` calls removed; each `return` mapped to True/False (parse→True, eval-fail→False, enqueue-fail→False, XADD-fail→False, pass-or-reject success→True). The `final_stream` XADD/expire and `_signal_from_stream_fields` are unchanged.

- [ ] **Step 4: Add `on_shutdown` (preserve the old `finally` flush)**
```python
    async def on_shutdown(self) -> None:
        await self.signals_writer.flush()
```

- [ ] **Step 5: Verify behavior preserved**

Run: `cd /tmp/m0b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_risk_filter_main.py tests/unit/streaming -q`
Expected: 7 (risk_filter) + 9 (streaming) green; same risk_filter count as Step-1 baseline. The behaviors that must hold: passed→final XADD + enqueue(executed=True); rejected→no final + enqueue(executed=False); size_multiplier/signal_id threaded; final TTL; xpending==0 on success; signal_id threaded to enqueue.

If anything fails: do NOT edit tests — recheck the bool mapping, `super().__init__(input_stream=candidate_stream, ...)`, and that run/stop/_stop were removed.

- [ ] **Step 6: Commit**
```bash
cd /tmp/m0b
git add services/risk_filter/main.py
git commit -m "refactor: migrate RiskFilterDaemon onto StreamStage (behavior-preserving)"
```

---

## Task B: Migrate `OrderRouterDaemon` onto `StreamStage`

Behavior-preserving refactor of the wallet-authority daemon; the existing `test_order_router_main.py` (24 tests) is the gate. The kill-switch sentinel guards become hooks; counter fields and the inline size-clamp / daily-INCR-fail-open branches are preserved exactly.

**Files:** Modify `services/order_router/main.py` (`OrderRouterDaemon` class only; module helpers `_DAILY_TRADE_KEY_PREFIX`/`_kst_date_key`/`_seconds_until_next_kst_midnight`/`_resolve_quantity` + `_build_and_run`/`main` UNCHANGED).

- [ ] **Step 1: Establish the green baseline**

Run: `cd /tmp/m0b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_order_router_main.py -q`
Expected: 24 passed. (If not green, STOP and report BLOCKED.)

- [ ] **Step 2: Subclass StreamStage + delegate constructor (keep all extra state)**

(a) Add to imports near the other `shared` imports:
```python
from shared.streaming.stage import StreamStage
```
(b) Change `class OrderRouterDaemon:` to `class OrderRouterDaemon(StreamStage):`.
(c) Replace the `__init__` body to delegate loop params; keep ALL other fields (passive_maker, pseudo_oco, contract_spec, passive_timeout_seconds, base_quantity, sentinel_path, live_mode_guard, locked_symbol, the four counter fields, and `refused_due_to_sentinel`). The keyword-only signature stays IDENTICAL. Replace the whole `__init__` with:
```python
    def __init__(
        self,
        *,
        redis: Any,
        passive_maker: PassiveMaker,
        pseudo_oco: PseudoOCO,
        contract_spec: ContractSpec,
        final_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        passive_timeout_seconds: int,
        base_quantity: int = 1,
        kill_switch_sentinel_path: str | None = None,
        live_mode_guard: LiveModeGuard | None = None,
        locked_symbol: str | None = None,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=final_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=0.5,
        )
        self.passive_maker = passive_maker
        self.pseudo_oco = pseudo_oco
        self.contract_spec = contract_spec
        self.passive_timeout_seconds = passive_timeout_seconds
        self.base_quantity = base_quantity
        self.sentinel_path = (
            Path(kill_switch_sentinel_path) if kill_switch_sentinel_path else None
        )
        self.live_mode_guard = live_mode_guard
        self.locked_symbol = locked_symbol
        self.refused_due_to_sentinel: bool = False
        self.live_suspended_count: int = 0
        self.symbol_lock_blocked_count: int = 0
        self.daily_trade_blocked_count: int = 0
        self.position_size_capped_count: int = 0

    def _sentinel_present(self) -> bool:
        return self.sentinel_path is not None and self.sentinel_path.exists()
```
> The base owns `self.redis`, `self.consumer_group`, `self.worker_id`, `self.xread_block_ms`, `self.batch_size`, and exposes the final stream as `self.input_stream`. Drop the old `self.redis = ... / self.final_stream = ... / self._stop = asyncio.Event()` assignments. Keep `_sentinel_present` exactly. (The final stream is referenced only via the base's `self.input_stream` now; `handle_message` no longer needs `self.final_stream` because XACK moved to the base.)

- [ ] **Step 3: Map the kill-switch sentinel guards to hooks**

Delete the hand-rolled `async def run(self)` and `async def stop(self)`. Add these two hooks (the base calls `on_startup()` before the loop and `pre_iteration_gate()` at the top of each iteration):
```python
    async def on_startup(self) -> None:
        # Startup guard: refuse to consume if the kill switch tripped previously
        # and an operator has not yet run scripts/kill_switch_clear.sh.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel exists at %s — refusing to start. "
                "Run scripts/kill_switch_clear.sh after operator review.",
                self.sentinel_path,
            )
            self._stop.set()  # prevent the consume loop from running any iteration

    async def pre_iteration_gate(self) -> bool:
        # Per-iteration guard: a mid-session trip must drain pre-trip messages
        # without placing further orders.
        if self._sentinel_present():
            self.refused_due_to_sentinel = True
            logger.critical(
                "Kill switch sentinel appeared at %s during run; exiting.",
                self.sentinel_path,
            )
            return False
        return True
```
> Behavior parity: on startup-sentinel, `on_startup` sets `refused_due_to_sentinel=True` and `self._stop.set()` so `while not self._stop.is_set()` exits immediately — no `xreadgroup`, no orders. (The base's `xgroup_create` runs harmlessly; the gate test does not assert it is skipped.) On mid-run trip, `pre_iteration_gate` returns False → the base `return`s out of the loop. `refused_due_to_sentinel` stays public.

- [ ] **Step 4: Convert `_process` → `handle_message` (preserve every branch incl. inline clamp/fail-open)**

Replace `_process` with `handle_message` returning a bool. Branches 1/2/3/6/8/10 map to a bool return; branches 4 (size clamp) and 5 (daily-INCR fail-open) stay INLINE (no return — they mutate `quantity`/counters and continue). Use EXACTLY:
```python
    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]
    ) -> bool:
        try:
            signal_id, signal = _signal_from_stream_fields(fields)
            size_multiplier = float(
                fields.get(b"size_multiplier", b"1.0").decode(errors="replace") or 1.0
            )
        except Exception:
            logger.exception("Unparseable final signal; ACK as poison-pill")
            return True  # poison-pill: consume

        quantity = _resolve_quantity(
            base_quantity=self.base_quantity, size_multiplier=size_multiplier
        )

        if (
            self.live_mode_guard is not None
            and await self.live_mode_guard.is_live_suspended(self.redis)
        ):
            self.live_suspended_count += 1
            logger.warning(
                "live_mode suspended; skipping signal_id=%s symbol=%s",
                signal_id,
                signal.symbol,
            )
            return True  # skip (consumed, no retry)

        guard = self.live_mode_guard

        if (
            guard is not None
            and guard.symbol_lock_enabled
            and self.locked_symbol is not None
            and signal.symbol != self.locked_symbol
        ):
            self.symbol_lock_blocked_count += 1
            logger.warning(
                "symbol_lock: signal.symbol=%s != locked=%s; skipping signal_id=%s",
                signal.symbol,
                self.locked_symbol,
                signal_id,
            )
            return True  # skip (consumed)

        if guard is not None and quantity > guard.max_position_size_contracts:
            self.position_size_capped_count += 1
            logger.warning(
                "position_size_cap: signal=%s quantity %d → %d (gate3)",
                signal_id,
                quantity,
                guard.max_position_size_contracts,
            )
            quantity = guard.max_position_size_contracts

        if guard is not None:
            counter_key = f"{_DAILY_TRADE_KEY_PREFIX}{_kst_date_key()}"
            try:
                count = await self.redis.incr(counter_key)
                if int(count) == 1:
                    await self.redis.expire(
                        counter_key, _seconds_until_next_kst_midnight()
                    )
            except Exception:
                logger.exception(
                    "daily_trade counter INCR failed; allowing signal_id=%s",
                    signal_id,
                )
            else:
                if int(count) > guard.max_daily_trades:
                    self.daily_trade_blocked_count += 1
                    logger.warning(
                        "daily_trade_cap: count=%d > max=%d; skipping signal_id=%s",
                        int(count),
                        guard.max_daily_trades,
                        signal_id,
                    )
                    return True  # cap hit: skip (consumed)

        try:
            result = await self.passive_maker.place_passive_limit_futures(
                signal=signal,
                signal_id=signal_id,
                quantity=quantity,
                spec=self.contract_spec,
                timeout_seconds=self.passive_timeout_seconds,
            )
        except Exception:
            logger.exception(
                "passive_maker raised signal_id=%s; leaving pending", signal_id
            )
            return False  # leave pending (no XACK)

        if not result.is_filled:
            logger.info(
                "passive limit not filled signal_id=%s reason=%s",
                signal_id,
                result.reason,
            )
            return True  # final state, consumed, no bracket

        try:
            from shared.execution.passive_maker import Fill

            fill = Fill(
                order_id=result.order_id or "",
                price=result.filled_price or 0.0,
                quantity=quantity,
                filled_at_ms=0,
            )
            await self.pseudo_oco.register_bracket(
                signal=signal,
                signal_id=signal_id,
                fill=fill,
                tick_size_points=self.contract_spec.tick_size_points,
            )
        except Exception:
            logger.exception(
                "OCO register failed signal_id=%s order_id=%s; leaving pending",
                signal_id,
                result.order_id,
            )
            return False  # leave pending

        return True  # success: consume
```
> Only changes vs `_process`: renamed to `handle_message`; every `await self.redis.xack(self.final_stream, ...)` removed; each disposition mapped to `return True`/`return False` per the branch map (parse→True, live_suspended→True, symbol_lock→True, daily_cap→True, passive-raises→False, not-filled→True, oco-raises→False, success→True). Branches 4 (clamp) and 5 (INCR fail-open) keep NO return, mutating `quantity`/counters and continuing. All comments may be kept or trimmed; the control flow + counter increments + `quantity` clamp must be identical.

- [ ] **Step 5: Verify behavior preserved**

Run: `cd /tmp/m0b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_order_router_main.py tests/unit/streaming -q`
Expected: 24 (order_router) + 9 (streaming) green; same order_router count as Step-1 baseline. Critical behaviors: routes to passive_maker + OCO on fill; not-filled cancels, no OCO; xpending==0 on success; **startup sentinel → refused_due_to_sentinel True, no order**; **mid-run sentinel → refused_due_to_sentinel True**; no-sentinel runs normally; live-mode disabled/redis-flag → skip + `live_suspended_count==1`; live enabled no-flag / guard None → routes, count 0; symbol_lock blocks non-locked (+count) / disabled allows / None noop; **position-size clamp → quantity==1, position_size_capped_count==1**; daily-cap blocks after max (+count); daily TTL on first INCR; **daily INCR failure fails-open** (order placed, count 0).

If anything fails: do NOT edit tests — recheck the branch→bool mapping (esp. branches 4/5 must NOT return), that the counter increments are in the same branches, that `refused_due_to_sentinel` is set by both hooks, and that `_stop.set()` is used (not an early `return`) in `on_startup`.

- [ ] **Step 6: Commit**
```bash
cd /tmp/m0b
git add services/order_router/main.py
git commit -m "refactor: migrate OrderRouterDaemon onto StreamStage (behavior-preserving)"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** Completes the M0b half of spec §4.2 (risk_filter + order_router adopt the StreamStage extracted in M0a). Ingest/indicator/decision daemons are later increments (M1+), not gaps.
- **Placeholder scan:** No TBD/TODO. Both `handle_message` bodies are shown in full; the constructor/hook edits and deletions are explicit.
- **Type/name consistency:** `handle_message(self, msg_id, fields) -> bool` matches the base abstract signature and the news_scorer adopter. risk_filter passes `input_stream=candidate_stream`; order_router passes `input_stream=final_stream`. Constructor keyword signatures are unchanged, so `_build_and_run` and the test `_make_daemon` harnesses keep working. Module helpers (`_signal_from_stream_fields`, `_DAILY_TRADE_KEY_PREFIX`, `_kst_date_key`, `_seconds_until_next_kst_midnight`, `_resolve_quantity`, `_sentinel_present`) stay at their import paths.
- **Behavior preservation hazards addressed:** order_router branches 4/5 stay inline (no early return); both sentinel guards set `refused_due_to_sentinel`; `on_startup` uses `self._stop.set()` (not `return`) to prevent the loop while staying within the base's call sequence; risk_filter keeps the `signals_writer.flush()` via `on_shutdown`. order_router has no `on_shutdown` override (its flush lives in `_build_and_run`'s unchanged `finally`).
- **Lint:** new code uses no unused args / no `dict()` literals / no empty-ABC-method patterns, so it should satisfy the repo's `ruff` (E,W,F,I,B,C4,UP,ARG,SIM) + `black`. After each task, the implementer should also run `ruff check` + `black --check` on the modified file and fix any deviation before committing.
