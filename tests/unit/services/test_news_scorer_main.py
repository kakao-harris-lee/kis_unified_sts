"""CLI-glue coverage for services.news_scorer.main.

The integration test (tests/integration/test_news_scorer_e2e.py) covers
NewsScorerDaemon business logic end-to-end.  These unit tests cover the
CLI wiring (_build_and_run) and the main() synchronous entry-point, with
ALL external I/O monkeypatched so no real infra is touched.

Monkeypatched surfaces:
  - redis.asyncio.from_url          → returns a mock with aclose()
  - shared.db.config.ClickHouseConfig.from_env → MagicMock
  - shared.db.client.AsyncClickHouseClient     → AsyncMock (connect + close)
  - openai.AsyncOpenAI              → AsyncMock with close()
  - shared.scoring.config.NewsScorerConfig.from_yaml  → pre-built config obj
  - shared.scoring.budget.DailyBudget          → MagicMock
  - shared.scoring.fallback.FallbackScorer     → MagicMock
  - shared.scoring.llm_scorer.LLMScorer       → MagicMock
  - NewsScorerDaemon.run            → instant coroutine (no event-loop block)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.news_scorer.main import NewsScorerDaemon, _build_and_run, main

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_scorer_cfg() -> MagicMock:
    """Return a minimal NewsScorerConfig-compatible mock."""
    cfg = MagicMock()
    cfg.consumer_group = "news_scorer-v1"
    cfg.worker_id_prefix = "scorer"
    cfg.batch_size = 10
    cfg.xread_block_ms = 5000
    cfg.input_stream = "stream:news.raw"
    cfg.output_stream = "stream:news.scored"
    cfg.output_stream_maxlen = 100_000
    cfg.ch_batch_size = 20
    cfg.ch_flush_interval_seconds = 10
    cfg.body_truncate_chars = 2000
    # scorer sub-section
    cfg.scorer.model = "gpt-4o-mini"
    cfg.scorer.version = "gpt-4o-mini-v1"
    cfg.scorer.temperature = 0.0
    cfg.scorer.max_tokens = 250
    cfg.scorer.timeout_seconds = 5.0
    cfg.scorer.retries = 2
    cfg.scorer.api_key_env = "OPENAI_API_KEY"
    # budget sub-section
    cfg.budget.daily_usd_limit = 5.0
    cfg.budget.key_prefix = "scorer:cost"
    return cfg


async def _instant_run(self: NewsScorerDaemon) -> None:  # type: ignore[misc]
    """Drop-in replacement for NewsScorerDaemon.run that returns immediately."""
    return


# ---------------------------------------------------------------------------
# _build_and_run — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_and_run_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_and_run() wires up all deps and returns 0 on success."""
    cfg = _make_scorer_cfg()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-unit")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "false")

    # --- NewsScorerConfig.from_yaml -----------------------------------------
    monkeypatch.setattr(
        "shared.scoring.config.NewsScorerConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )

    # --- redis.asyncio.from_url ---------------------------------------------
    fake_redis = AsyncMock()
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_kw: fake_redis)

    # --- ClickHouseConfig.from_env + AsyncClickHouseClient ------------------
    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, **_kw: MagicMock()),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )

    # --- openai.AsyncOpenAI -------------------------------------------------
    fake_openai = AsyncMock()
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *_a, **_kw: fake_openai)

    # --- DailyBudget / FallbackScorer / LLMScorer ---------------------------
    monkeypatch.setattr(
        "shared.scoring.budget.DailyBudget",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.fallback.FallbackScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.llm_scorer.LLMScorer",
        lambda *_a, **_kw: MagicMock(),
    )

    # --- NewsScorerDaemon.run ------------------------------------------------
    monkeypatch.setattr(NewsScorerDaemon, "run", _instant_run)

    rc = await _build_and_run()

    assert rc == 0
    fake_ch.connect.assert_not_awaited()


# ---------------------------------------------------------------------------
# _build_and_run — cleanup verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_and_run_cleanup_awaited(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify openai_client.close, redis.aclose, ch.close are all awaited."""
    cfg = _make_scorer_cfg()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-unit")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "true")

    monkeypatch.setattr(
        "shared.scoring.config.NewsScorerConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )

    fake_redis = AsyncMock()
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_kw: fake_redis)

    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, **_kw: MagicMock()),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )

    fake_openai = AsyncMock()
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *_a, **_kw: fake_openai)

    monkeypatch.setattr(
        "shared.scoring.budget.DailyBudget",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.fallback.FallbackScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.llm_scorer.LLMScorer",
        lambda *_a, **_kw: MagicMock(),
    )

    monkeypatch.setattr(NewsScorerDaemon, "run", _instant_run)

    await _build_and_run()

    # All three cleanup coroutines must have been awaited.
    fake_openai.close.assert_awaited_once()
    fake_redis.aclose.assert_awaited_once()
    fake_ch.close.assert_awaited_once()
    # ClickHouse must have been connected before use.
    fake_ch.connect.assert_awaited_once()


# ---------------------------------------------------------------------------
# _build_and_run — cleanup on daemon exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_and_run_cleanup_on_daemon_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even when run() raises, all cleanup helpers are still awaited (finally)."""
    cfg = _make_scorer_cfg()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-unit")
    monkeypatch.setenv("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED", "true")

    monkeypatch.setattr(
        "shared.scoring.config.NewsScorerConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )

    fake_redis = AsyncMock()
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_kw: fake_redis)

    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, **_kw: MagicMock()),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )

    fake_openai = AsyncMock()
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *_a, **_kw: fake_openai)

    monkeypatch.setattr(
        "shared.scoring.budget.DailyBudget",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.fallback.FallbackScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.llm_scorer.LLMScorer",
        lambda *_a, **_kw: MagicMock(),
    )

    async def _boom(self: NewsScorerDaemon) -> None:
        raise RuntimeError("simulated daemon crash")

    monkeypatch.setattr(NewsScorerDaemon, "run", _boom)

    with pytest.raises(RuntimeError, match="simulated daemon crash"):
        await _build_and_run()

    # Cleanup must still run despite the exception.
    fake_openai.close.assert_awaited_once()
    fake_redis.aclose.assert_awaited_once()
    fake_ch.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# _build_and_run — default REDIS_URL when env var absent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_and_run_default_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """When REDIS_URL is not set, falls back to redis://localhost:6379/1."""
    cfg = _make_scorer_cfg()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-unit")
    # Ensure REDIS_URL is absent so the default is exercised.
    monkeypatch.delenv("REDIS_URL", raising=False)

    monkeypatch.setattr(
        "shared.scoring.config.NewsScorerConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )

    captured_urls: list[str] = []

    def _capture_url(url: str, **_kw: object) -> AsyncMock:
        captured_urls.append(url)
        return AsyncMock()

    monkeypatch.setattr("redis.asyncio.from_url", _capture_url)

    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, **_kw: MagicMock()),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *_a, **_kw: AsyncMock())
    monkeypatch.setattr(
        "shared.scoring.budget.DailyBudget",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.fallback.FallbackScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.llm_scorer.LLMScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(NewsScorerDaemon, "run", _instant_run)

    await _build_and_run()

    assert captured_urls == ["redis://localhost:6379/1"]


# ---------------------------------------------------------------------------
# _build_and_run — worker_id includes hostname and pid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_and_run_worker_id_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """worker_id must follow '{prefix}-{hostname}-{pid}' format."""
    cfg = _make_scorer_cfg()
    cfg.worker_id_prefix = "scorer"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-unit")

    monkeypatch.setattr(
        "shared.scoring.config.NewsScorerConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_kw: AsyncMock())

    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, **_kw: MagicMock()),
    )
    fake_ch = AsyncMock()
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: fake_ch,
    )
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *_a, **_kw: AsyncMock())
    monkeypatch.setattr(
        "shared.scoring.budget.DailyBudget",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.fallback.FallbackScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.llm_scorer.LLMScorer",
        lambda *_a, **_kw: MagicMock(),
    )

    captured_worker_ids: list[str] = []

    original_init = NewsScorerDaemon.__init__

    def _capture_worker_id(self: NewsScorerDaemon, **kwargs: object) -> None:
        captured_worker_ids.append(str(kwargs.get("worker_id", "")))
        original_init(self, **kwargs)

    monkeypatch.setattr(NewsScorerDaemon, "__init__", _capture_worker_id)
    monkeypatch.setattr(NewsScorerDaemon, "run", _instant_run)

    await _build_and_run()

    assert len(captured_worker_ids) == 1
    wid = captured_worker_ids[0]
    assert wid.startswith("scorer-"), f"worker_id should start with prefix: {wid!r}"
    # Must contain hostname (non-empty) and pid (numeric suffix)
    parts = wid.split("-")
    assert len(parts) >= 3, f"Expected at least 3 dash-separated parts: {wid!r}"
    assert parts[-1].isdigit(), f"Last segment should be PID: {wid!r}"


# ---------------------------------------------------------------------------
# main() — synchronous entry-point
# ---------------------------------------------------------------------------


def test_main_invokes_build_and_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() calls asyncio.run(_build_and_run) and returns its exit code."""
    called: dict[str, bool] = {}

    async def _fake_build_and_run() -> int:
        called["invoked"] = True
        return 0

    monkeypatch.setattr(
        "services.news_scorer.main._build_and_run",
        _fake_build_and_run,
    )

    rc = main()

    assert rc == 0
    assert called.get("invoked") is True


def test_main_propagates_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() forwards any non-zero return code from _build_and_run unchanged."""

    async def _fake_build_and_run() -> int:
        return 42

    monkeypatch.setattr(
        "services.news_scorer.main._build_and_run",
        _fake_build_and_run,
    )

    rc = main()

    assert rc == 42


# ---------------------------------------------------------------------------
# YAML-driven DailyBudget wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_and_run_passes_budget_key_prefix_from_yaml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cfg.budget.key_prefix must flow through to DailyBudget(...)."""
    cfg = _make_scorer_cfg()
    cfg.budget.key_prefix = "staging:scorer:cost"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-unit")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
    monkeypatch.setattr(
        "shared.scoring.config.NewsScorerConfig.from_yaml",
        classmethod(lambda _cls, *_a, **_kw: cfg),
    )
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_a, **_kw: AsyncMock())
    monkeypatch.setattr(
        "shared.db.config.ClickHouseConfig.from_env",
        classmethod(lambda _cls, **_kw: MagicMock()),
    )
    monkeypatch.setattr(
        "shared.db.client.AsyncClickHouseClient",
        lambda *_a, **_kw: AsyncMock(),
    )
    monkeypatch.setattr("openai.AsyncOpenAI", lambda *_a, **_kw: AsyncMock())
    monkeypatch.setattr(
        "shared.scoring.fallback.FallbackScorer",
        lambda *_a, **_kw: MagicMock(),
    )
    monkeypatch.setattr(
        "shared.scoring.llm_scorer.LLMScorer",
        lambda *_a, **_kw: MagicMock(),
    )

    captured_kwargs: list[dict] = []

    def _capture_budget(*_a, **kwargs):
        captured_kwargs.append(kwargs)
        return MagicMock()

    monkeypatch.setattr("shared.scoring.budget.DailyBudget", _capture_budget)
    monkeypatch.setattr(NewsScorerDaemon, "run", _instant_run)

    await _build_and_run()

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["daily_usd_limit"] == 5.0
    assert captured_kwargs[0]["key_prefix"] == "staging:scorer:cost"
