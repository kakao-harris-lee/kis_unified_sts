# StreamStage Framework (M0a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the duplicated Redis consumer-group loop (XGROUP_CREATE → XREADGROUP → per-message handle → XACK) into one tested `StreamStage` base class, and migrate `news_scorer` onto it behavior-preservingly — the DRY foundation every streaming daemon (existing + the future ingest/indicator/decision daemons) will share.

**Architecture:** `shared/streaming/stage.py` defines an abstract `StreamStage` owning the consume loop. Subclasses implement `handle_message(msg_id, fields) -> bool` (return `True` ⇒ the base XACKs; `False` ⇒ leave pending for retry) and may override optional hooks `on_startup` / `pre_iteration_gate` / `post_poll` / `on_shutdown`. `NewsScorerDaemon` becomes the first adopter — its hand-rolled loop is deleted; its `_process` becomes `handle_message`. Existing news_scorer tests are the refactor safety net.

**Tech Stack:** Python 3.11 asyncio, `redis.asyncio`, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md` (§4.2 shared framework). This plan = increment **M0a** only (framework + 1 adopter). risk_filter/order_router adoption (M0b) and the ingest daemon (M1) are separate plans.

---

## File Structure

| Path | Responsibility | Action |
|---|---|---|
| `shared/streaming/stage.py` | `StreamStage` ABC: owns the consumer-group consume loop + XACK; defines `handle_message` (abstract) + optional hooks | Create |
| `tests/unit/streaming/test_stream_stage.py` | Unit tests for the loop using a fake async redis + fake subclass | Create |
| `services/news_scorer/main.py` | `NewsScorerDaemon` subclasses `StreamStage`; `_process` → `handle_message` (bool return); add `post_poll`/`on_shutdown`; delete hand-rolled `run`/`stop`/`_stop` | Modify |

Notes:
- `tests/unit/streaming/` is a NEW dir — do **NOT** add an `__init__.py` (repo uses namespace packages; sibling `__init__.py` previously caused collection collisions).
- `shared/streaming/` already exists (has `client.py`, `trading_state.py`); add `stage.py` beside them.
- Run tests via the worktree using the main repo venv: `cd <worktree> && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest <path> -q`.

---

## Task 1: `StreamStage` base + unit tests

**Files:**
- Create: `shared/streaming/stage.py`
- Test: `tests/unit/streaming/test_stream_stage.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/streaming/test_stream_stage.py` with EXACTLY this content:

```python
"""Unit tests for shared.streaming.stage.StreamStage (consume loop)."""
from __future__ import annotations

import asyncio

import pytest

from shared.streaming.stage import StreamStage


class FakeRedis:
    """Minimal async Redis double for the consume loop.

    `xreadgroup` serves each queued batch once (FIFO), then returns [] forever.
    Records xgroup_create args and xack calls.
    """

    def __init__(self, batches: list[list[tuple[bytes, dict[bytes, bytes]]]]):
        self._batches = list(batches)
        self.group_created: tuple | None = None
        self.acked: list[bytes] = []
        self.xreadgroup_calls = 0

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        self.group_created = (stream, group, id, mkstream)

    async def xreadgroup(self, *, groupname, consumername, streams, count, block):
        self.xreadgroup_calls += 1
        if self._batches:
            msgs = self._batches.pop(0)
            stream_key = next(iter(streams))
            return [(stream_key, msgs)]
        await asyncio.sleep(0)
        return []

    async def xack(self, stream, group, msg_id):
        self.acked.append(msg_id)


class RecordingStage(StreamStage):
    """Concrete stage that records hook calls; handle_message return is configurable."""

    def __init__(self, *, ack_result=True, gate_result=True, **kw):
        super().__init__(**kw)
        self._ack_result = ack_result
        self._gate_result = gate_result
        self.handled: list[bytes] = []
        self.startup_calls = 0
        self.shutdown_calls = 0
        self.post_poll_counts: list[int] = []
        self.gate_calls = 0

    async def handle_message(self, msg_id, fields):
        self.handled.append(msg_id)
        return self._ack_result

    async def on_startup(self):
        self.startup_calls += 1

    async def pre_iteration_gate(self):
        self.gate_calls += 1
        return self._gate_result

    async def post_poll(self, message_count):
        self.post_poll_counts.append(message_count)

    async def on_shutdown(self):
        self.shutdown_calls += 1


def _stage(redis, **kw):
    params = dict(
        redis=redis,
        input_stream="s:in",
        consumer_group="g",
        worker_id="w",
        xread_block_ms=5,
        batch_size=10,
    )
    params.update(kw)
    return RecordingStage(**params)


async def _run_briefly(stage, seconds=0.05):
    task = asyncio.create_task(stage.run())
    await asyncio.sleep(seconds)
    await stage.stop()
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_creates_consumer_group_with_mkstream():
    redis = FakeRedis([])
    stage = _stage(redis)
    await _run_briefly(stage)
    assert redis.group_created == ("s:in", "g", "0", True)


@pytest.mark.asyncio
async def test_handle_message_called_and_acks_on_true():
    redis = FakeRedis([[(b"1-0", {b"k": b"v"})]])
    stage = _stage(redis, ack_result=True)
    await _run_briefly(stage)
    assert stage.handled == [b"1-0"]
    assert redis.acked == [b"1-0"]


@pytest.mark.asyncio
async def test_no_ack_when_handle_returns_false():
    redis = FakeRedis([[(b"1-0", {b"k": b"v"})]])
    stage = _stage(redis, ack_result=False)
    await _run_briefly(stage)
    assert stage.handled == [b"1-0"]
    assert redis.acked == []


@pytest.mark.asyncio
async def test_pre_iteration_gate_false_stops_loop_before_read():
    redis = FakeRedis([[(b"1-0", {b"k": b"v"})]])
    stage = _stage(redis, gate_result=False)
    await _run_briefly(stage)
    assert redis.xreadgroup_calls == 0  # gate aborted before any read
    assert stage.handled == []
    assert stage.shutdown_calls == 1  # on_shutdown still runs (finally)


@pytest.mark.asyncio
async def test_on_startup_runs_before_loop_and_shutdown_in_finally():
    redis = FakeRedis([])
    stage = _stage(redis)
    await _run_briefly(stage)
    assert stage.startup_calls == 1
    assert stage.shutdown_calls == 1


@pytest.mark.asyncio
async def test_post_poll_receives_message_count_including_idle():
    redis = FakeRedis([[(b"1-0", {}), (b"2-0", {})]])
    stage = _stage(redis)
    await _run_briefly(stage)
    # first poll returns 2 messages, later polls are idle (0)
    assert stage.post_poll_counts[0] == 2
    assert 0 in stage.post_poll_counts[1:]


@pytest.mark.asyncio
async def test_handle_message_exception_propagates_but_shutdown_runs():
    class Boom(RecordingStage):
        async def handle_message(self, msg_id, fields):
            raise RuntimeError("boom")

    redis = FakeRedis([[(b"1-0", {})]])
    stage = Boom(
        redis=redis, input_stream="s:in", consumer_group="g", worker_id="w",
        xread_block_ms=5, batch_size=10,
    )
    task = asyncio.create_task(stage.run())
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(task, timeout=1.0)
    assert stage.shutdown_calls == 1


@pytest.mark.asyncio
async def test_xreadgroup_error_sleeps_and_continues():
    class FlakyRedis(FakeRedis):
        def __init__(self):
            super().__init__([[(b"9-0", {})]])
            self._raised = False

        async def xreadgroup(self, **kw):
            if not self._raised:
                self._raised = True
                raise ConnectionError("transient")
            return await super().xreadgroup(**kw)

    redis = FlakyRedis()
    stage = _stage(redis, xreadgroup_error_sleep_seconds=0.0)
    await _run_briefly(stage)
    # survived the transient error and still processed the message afterwards
    assert stage.handled == [b"9-0"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /tmp/spld && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/streaming/test_stream_stage.py -q`
Expected: collection error / failures — `shared.streaming.stage` does not exist yet.

- [ ] **Step 3: Write `StreamStage`**

Create `shared/streaming/stage.py` with EXACTLY this content:

```python
"""Shared Redis consumer-group stage framework.

Extracts the consumer-group loop (XGROUP_CREATE → XREADGROUP → per-message
handle → XACK) that news_scorer / risk_filter / order_router each reimplemented,
so every streaming daemon shares one tested loop.

Subclasses implement ``handle_message`` (return ``True`` ⇒ the framework XACKs;
``False`` ⇒ leave the message pending for retry) and may override the optional
hooks ``on_startup`` / ``pre_iteration_gate`` / ``post_poll`` / ``on_shutdown``.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class StreamStage(ABC):
    """Abstract base for a Redis consumer-group daemon stage."""

    def __init__(
        self,
        *,
        redis: Any,
        input_stream: str,
        consumer_group: str,
        worker_id: str,
        xread_block_ms: int,
        batch_size: int,
        xreadgroup_error_sleep_seconds: float = 0.5,
    ) -> None:
        self.redis = redis
        self.input_stream = input_stream
        self.consumer_group = consumer_group
        self.worker_id = worker_id
        self.xread_block_ms = xread_block_ms
        self.batch_size = batch_size
        self._xreadgroup_error_sleep = xreadgroup_error_sleep_seconds
        self._stop = asyncio.Event()

    # -- subclass contract ------------------------------------------------ #

    @abstractmethod
    async def handle_message(self, msg_id: bytes, fields: dict[bytes, bytes]) -> bool:
        """Process one message.

        Returns:
            ``True``  → the framework XACKs the message after this returns.
            ``False`` → the framework does NOT XACK (stays pending for retry).

        Deliberate skips (poison-pill parse error, gate-blocked) should return
        ``True`` so the message is consumed; transient failures should return
        ``False`` so it is retried. Exceptions raised here propagate out of the
        loop (``on_shutdown`` still runs); subclasses should catch their own
        recoverable errors and map them to a bool.
        """
        ...

    # -- optional hooks (no-op defaults) --------------------------------- #

    async def on_startup(self) -> None:
        """Called once before the consume loop. Override for startup guards."""

    async def pre_iteration_gate(self) -> bool:
        """Called at the top of each loop iteration, before XREADGROUP.

        Return ``False`` to abort the loop (e.g. a kill-switch sentinel
        appeared). Default: always proceed.
        """
        return True

    async def post_poll(self, message_count: int) -> None:
        """Called after each XREADGROUP returns (``message_count == 0`` when idle).

        Override for per-cycle observability (e.g. backlog gauge update).
        """

    async def on_shutdown(self) -> None:
        """Called in the loop's ``finally`` (even on exception).

        Override to flush writers/publishers.
        """

    # -- framework loop (not overridden) --------------------------------- #

    async def run(self) -> None:
        await self.on_startup()

        with contextlib.suppress(Exception):
            await self.redis.xgroup_create(
                self.input_stream, self.consumer_group, id="0", mkstream=True
            )

        try:
            while not self._stop.is_set():
                if not await self.pre_iteration_gate():
                    return

                try:
                    messages = await self.redis.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.worker_id,
                        streams={self.input_stream: ">"},
                        count=self.batch_size,
                        block=self.xread_block_ms,
                    )
                except Exception:
                    logger.exception(
                        "xreadgroup error; sleeping %.1fs",
                        self._xreadgroup_error_sleep,
                    )
                    await asyncio.sleep(self._xreadgroup_error_sleep)
                    continue

                count = (
                    sum(len(msgs) for _stream, msgs in messages) if messages else 0
                )
                await self.post_poll(count)

                if not messages:
                    await asyncio.sleep(0)
                    continue

                for _stream, msgs in messages:
                    for msg_id, data in msgs:
                        should_ack = await self.handle_message(msg_id, data)
                        if should_ack:
                            await self.redis.xack(
                                self.input_stream, self.consumer_group, msg_id
                            )
        finally:
            await self.on_shutdown()

    async def stop(self) -> None:
        self._stop.set()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /tmp/spld && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/streaming/test_stream_stage.py -q`
Expected: 8 passed.

(If `pytest.mark.asyncio` is unrecognized, confirm `pytest-asyncio` is configured — the repo already uses async tests, e.g. `tests/unit/dashboard`; the marker should work. If a strict-markers error appears, run with `-p asyncio` is not needed; the repo's `pyproject`/`pytest.ini` enables asyncio mode.)

- [ ] **Step 5: Commit**

```bash
cd /tmp/spld
git add shared/streaming/stage.py tests/unit/streaming/test_stream_stage.py
git commit -m "feat: add StreamStage consumer-group base (XREADGROUP loop + XACK + hooks)"
```

---

## Task 2: Migrate `NewsScorerDaemon` onto `StreamStage`

This is a **behavior-preserving refactor**. The safety net is the existing news_scorer test suite — it must stay green. We do NOT add new behavior.

**Files:**
- Modify: `services/news_scorer/main.py` (`NewsScorerDaemon` class only; `_build_and_run`/`main` UNCHANGED)
- Existing tests (do not modify): `tests/integration/test_news_scorer_e2e.py`, `tests/unit/services/test_news_scorer_main.py`

- [ ] **Step 1: Establish the green baseline**

Run the existing news_scorer tests BEFORE changing anything, to confirm they pass on this branch (Redis on DB 1 must be reachable for the e2e file; start it if needed with `docker compose --env-file .env.dev up -d redis` or use an already-running Redis):

Run: `cd /tmp/spld && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/integration/test_news_scorer_e2e.py tests/unit/services/test_news_scorer_main.py -q`
Expected: all pass (this is the baseline the refactor must preserve). Record the pass count.

- [ ] **Step 2: Refactor the class declaration + constructor**

In `services/news_scorer/main.py`:

(a) Add the import near the other `shared` imports at the top of the file:

```python
from shared.streaming.stage import StreamStage
```

(b) Change the class declaration `class NewsScorerDaemon:` to `class NewsScorerDaemon(StreamStage):`.

(c) In `__init__`, delegate the loop params to the base via `super().__init__(...)` and stop storing them directly. Replace the body lines that assign `self.redis`, `self.input_stream`, `self.consumer_group`, `self.worker_id`, `self.batch_size`, `self.xread_block_ms`, and `self._stop = asyncio.Event()` with a single `super().__init__(...)` call. The constructor signature (the keyword-only params) stays IDENTICAL so callers and tests are unchanged. Concretely, the `__init__` becomes:

```python
    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        scorer: Scorer,
        fallback: Scorer,
        input_stream: str,
        output_stream: str,
        consumer_group: str,
        worker_id: str,
        output_maxlen: int,
        ch_batch_size: int,
        xread_block_ms: int,
        batch_size: int,
    ) -> None:
        super().__init__(
            redis=redis,
            input_stream=input_stream,
            consumer_group=consumer_group,
            worker_id=worker_id,
            xread_block_ms=xread_block_ms,
            batch_size=batch_size,
            xreadgroup_error_sleep_seconds=1.0,
        )
        self.scorer = scorer
        self.fallback = fallback
        self.publisher = ScoredPublisher(
            redis=redis,
            ch_client=ch_client,
            output_stream=output_stream,
            output_maxlen=output_maxlen,
            ch_batch_size=ch_batch_size,
        )
```

> Keep whatever `self.publisher = ScoredPublisher(...)` construction the current `__init__` already has — copy its exact argument list from the existing file; the block above mirrors the current fields (`ch_client`, `output_stream`, `output_maxlen`, `ch_batch_size`). Do not invent new ScoredPublisher args; match the file. Remove any now-duplicated `self.redis = redis` / `self.input_stream = ...` / `self._stop = asyncio.Event()` lines (the base owns them).

- [ ] **Step 3: Delete the hand-rolled loop and rename `_process` → `handle_message`**

(a) DELETE the existing `async def run(self)` method and the `async def stop(self)` method entirely (the base provides both).

(b) Convert `_process` into `handle_message` that **returns a bool instead of calling XACK**. Replace the whole `_process` method with:

```python
    async def handle_message(
        self, msg_id: bytes, fields: dict[bytes, bytes]
    ) -> bool:
        """Score one stream message and publish the result.

        Returns True ⇒ framework XACKs (parse poison-pill, fallback, success);
        False ⇒ leave pending for retry (unknown scorer error, publish error).
        """
        # --- parse ---
        try:
            news = _news_from_stream_fields(fields)
        except Exception:
            record_news_scoring_error("parse_error")
            logger.exception(
                "Unparseable stream message; ACKing to avoid poison-pill loop"
            )
            return True  # poison-pill: consume (base XACKs)

        # --- score ---
        start = asyncio.get_event_loop().time()
        used_fallback = False
        fallback_reason: str | None = None

        try:
            item = await self.scorer.score(news)
            record_news_scored(self.scorer.version, item.category)
        except BudgetExceeded:
            item = await self.fallback.score(news)
            used_fallback = True
            fallback_reason = "budget"
            record_news_scoring_fallback("budget")
        except ScoringValidationError:
            item = await self.fallback.score(news)
            used_fallback = True
            fallback_reason = "json_error"
            record_news_scoring_fallback("json_error")
        except TimeoutError:
            item = await self.fallback.score(news)
            used_fallback = True
            fallback_reason = "timeout"
            record_news_scoring_fallback("timeout")
        except Exception:
            record_news_scoring_error("scorer_unknown")
            logger.exception(
                "Unhandled scorer error news_id=%s; leaving message pending",
                news.news_id,
            )
            return False  # leave pending for retry (base does NOT XACK)

        record_news_scoring_duration(
            self.scorer.version, asyncio.get_event_loop().time() - start
        )

        if used_fallback:
            logger.debug(
                "Fallback scorer used reason=%s news_id=%s",
                fallback_reason,
                news.news_id,
            )
        item = _attach_raw_news_context(item, news, msg_id)

        # --- publish ---
        try:
            await self.publisher.publish(item)
        except Exception:
            record_news_scoring_error("publish_error")
            logger.exception(
                "Publisher failed news_id=%s; leaving message pending", news.news_id
            )
            return False  # leave pending for retry (base does NOT XACK)

        return True  # success: framework XACKs
```

> The ONLY changes vs the original `_process`: (1) signature renamed to `handle_message`; (2) every internal `await self.redis.xack(...)` removed; (3) each `return` replaced with `return True`/`return False` per the mapping (parse→True, unknown-scorer→False, publish→False, success→True). The fallback branches still fall through to the final `return True`. The helpers `_news_from_stream_fields` and `_attach_raw_news_context` are unchanged.

- [ ] **Step 4: Wire the two per-cycle/shutdown hooks**

(a) Add `post_poll` so the backlog metric still updates every cycle (the old loop called `self._update_backlog_metric()` after each poll):

```python
    async def post_poll(self, message_count: int) -> None:
        await self._update_backlog_metric()
```

(b) Add `on_shutdown` so the publisher still flushes (the old `run()` did `finally: await self.publisher.flush()`):

```python
    async def on_shutdown(self) -> None:
        await self.publisher.flush()
```

> Keep the existing `_update_backlog_metric` method as-is. Do not remove it.

- [ ] **Step 5: Run the existing tests to verify behavior is preserved**

Run: `cd /tmp/spld && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/integration/test_news_scorer_e2e.py tests/unit/services/test_news_scorer_main.py -q`
Expected: SAME pass count as the Step-1 baseline (all green). In particular the 8 e2e behaviors must hold: happy-path scored+ACKed; fallback on validation/budget/timeout (ACKed); unknown exception → NOT ACKed (`xpending==1`); parse error → ACKed; multi-message; CH/publish failure → NOT ACKed.

If anything fails: do NOT edit the tests. Re-check the bool mapping in `handle_message` and that `super().__init__` got the right params and `run`/`stop`/`_stop` were removed.

- [ ] **Step 6: Run the new StreamStage unit tests too (regression)**

Run: `cd /tmp/spld && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/streaming tests/unit/services/test_news_scorer_main.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd /tmp/spld
git add services/news_scorer/main.py
git commit -m "refactor: migrate NewsScorerDaemon onto StreamStage (behavior-preserving)"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** Implements spec §4.2 `shared/streaming/stage.py` `StreamStage` extraction (the DRY core) and validates it on one real adopter (news_scorer). risk_filter/order_router adoption + ingest daemon are explicitly deferred to later plans (M0b / M1) per the spec's "increment별 plan" note — not gaps.
- **Placeholder scan:** No TBD/TODO. Task 1 code is complete (full class + full tests). Task 2 shows the full converted `handle_message`, the exact `__init__`/hook edits, and the deletions. The one soft instruction ("match the current `ScoredPublisher(...)` arg list") is a fidelity guard, not a placeholder — the existing constructor is right there in the file.
- **Type/name consistency:** `handle_message(msg_id, fields) -> bool` matches between `StreamStage` (abstract), the tests (`RecordingStage`), and `NewsScorerDaemon`. Hooks `on_startup`/`pre_iteration_gate`/`post_poll`/`on_shutdown` are named identically across base, tests, and the news_scorer override. Constructor keyword params for `NewsScorerDaemon` are unchanged, so `_build_and_run` and the e2e `_make_daemon` harness keep working.
- **Refactor safety:** Task 2 is behavior-preserving; the existing e2e suite (8 XACK/xpending behaviors) + the unit glue test are the gate. `_build_and_run`/`main` are untouched (the legacy-CH-patch unit test concern the spec research flagged is pre-existing and out of scope).
- **Risk:** the e2e file may require a running Redis (DB 1); Step 1 establishes the baseline so a Redis-availability issue is caught before refactoring, not blamed on it.
