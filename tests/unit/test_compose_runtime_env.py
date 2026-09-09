from __future__ import annotations

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_env_template(name: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (_REPO_ROOT / name).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_paper_and_live_env_templates_separate_kis_markets():
    paper = _read_env_template(".env.paper.example")
    live = _read_env_template(".env.live.example")

    assert paper["COMPOSE_PROJECT_NAME"] == "kis_paper"
    assert paper["KIS_IS_REAL"] == "false"
    assert paper["KIS_REAL_TRADING"] == "false"
    assert paper["KIS_STOCK_MARKET"] == "mock"
    assert paper["KIS_FUTURES_MARKET"] == "real"
    assert paper["TRADING_MODE"] == "paper"
    assert paper["TRADING_LIVE_CONFIRM"] == ""
    assert paper["KIS_TOKEN_CACHE_DIR"] == "/app/.cache"
    assert paper["NEXT_PUBLIC_API_KEY"] == "CHANGE_ME_PAPER_DASHBOARD_API_KEY"
    assert paper["STOCK_PIPELINE_MODE"] == "shadow"
    assert paper["STOCK_POSITIONS_KEY"] == "stock:daemon:positions"
    assert paper["STOCK_TICK_STREAM"] == "market:ticks"
    assert paper["KIS_STOCK_APP_KEY"] == "CHANGE_ME_PAPER_KIS_APP_KEY"
    assert paper["KIS_STOCK_APP_SECRET"] == "CHANGE_ME_PAPER_KIS_APP_SECRET"
    assert paper["KIS_FUTURES_APP_KEY"] == "CHANGE_ME_PAPER_KIS_APP_KEY"
    assert paper["KIS_FUTURES_APP_SECRET"] == "CHANGE_ME_PAPER_KIS_APP_SECRET"
    assert paper["TELEGRAM_STOCK_BOT_TOKEN"] == "CHANGE_ME_PAPER_TELEGRAM_BOT_TOKEN"
    assert paper["TELEGRAM_STOCK_CHAT_ID"] == "CHANGE_ME_PAPER_TELEGRAM_CHAT_ID"
    assert paper["TELEGRAM_FUTURES_BOT_TOKEN"] == "CHANGE_ME_PAPER_TELEGRAM_BOT_TOKEN"
    assert paper["TELEGRAM_FUTURES_CHAT_ID"] == "CHANGE_ME_PAPER_TELEGRAM_CHAT_ID"
    assert paper["FUTURES_PIPELINE_MODE"] == "shadow"
    assert paper["FUTURES_ORDER_ROUTER_MODE"] == "paper"
    # order_router consumes the tick stream by default and opens no KIS WS —
    # `ws` is the opt-in self-fed path (one futures WS per KIS account).
    assert paper["FUTURES_ORDER_ROUTER_FEED"] == "stream"
    assert paper["FUTURES_TICK_STREAM"] == "raw_data"
    assert paper["FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS"] == "10"
    assert paper["FUTURES_ROUTER_SLIPPAGE_GATE"] == "true"
    assert paper["FUTURES_ORDER_ROUTER_SEED_COUNT"] == "50"
    assert paper["FUTURES_STRATEGY_SYMBOL"] == ""
    # Empty = every setup whose strategy.enabled is true; the knob exists so an
    # operator can narrow the DECOUPLED roster without touching the switch
    # trader-futures shares.
    assert paper["FUTURES_DECISION_ENGINE_SETUPS"] == ""
    assert paper["FUTURES_EXECUTOR_TRADING_MODE"] == "PAPER"
    assert paper["OPENAI_API_KEY"] == ""
    assert paper["DART_API_KEY"] == ""
    assert paper["MARKETAUX_API_TOKEN"] == ""
    assert paper["NAVER_SEARCH_CLIENT_ID"] == ""
    assert paper["NAVER_SEARCH_CLIENT_SECRET"] == ""
    assert paper["NEWS_SCORER_CONSUMER_GROUP"] == "news_scorer-v1"

    assert live["COMPOSE_PROJECT_NAME"] == "kis_live"
    assert live["KIS_IS_REAL"] == "true"
    assert live["KIS_REAL_TRADING"] == "true"
    assert live["KIS_STOCK_MARKET"] == "real"
    assert live["KIS_FUTURES_MARKET"] == "real"
    assert live["TRADING_MODE"] == "live"
    assert live["TRADING_LIVE_CONFIRM"] == ""
    assert live["KIS_TOKEN_CACHE_DIR"] == "/app/.cache"
    assert live["NEXT_PUBLIC_API_KEY"] == "CHANGE_ME_LIVE_DASHBOARD_API_KEY"
    assert live["STOCK_PIPELINE_MODE"] == "shadow"
    assert live["STOCK_POSITIONS_KEY"] == "stock:daemon:positions"
    assert live["STOCK_TICK_STREAM"] == "market:ticks"
    assert live["KIS_STOCK_APP_KEY"] == "CHANGE_ME_LIVE_KIS_APP_KEY"
    assert live["KIS_STOCK_APP_SECRET"] == "CHANGE_ME_LIVE_KIS_APP_SECRET"
    assert live["KIS_FUTURES_APP_KEY"] == "CHANGE_ME_LIVE_KIS_APP_KEY"
    assert live["KIS_FUTURES_APP_SECRET"] == "CHANGE_ME_LIVE_KIS_APP_SECRET"
    assert live["TELEGRAM_STOCK_BOT_TOKEN"] == "CHANGE_ME_LIVE_TELEGRAM_BOT_TOKEN"
    assert live["TELEGRAM_STOCK_CHAT_ID"] == "CHANGE_ME_LIVE_TELEGRAM_CHAT_ID"
    assert live["TELEGRAM_FUTURES_BOT_TOKEN"] == "CHANGE_ME_LIVE_TELEGRAM_BOT_TOKEN"
    assert live["TELEGRAM_FUTURES_CHAT_ID"] == "CHANGE_ME_LIVE_TELEGRAM_CHAT_ID"
    assert live["FUTURES_PIPELINE_MODE"] == "shadow"
    assert live["FUTURES_ORDER_ROUTER_MODE"] == "paper"
    assert live["FUTURES_ORDER_ROUTER_FEED"] == "stream"
    assert live["FUTURES_TICK_STREAM"] == "raw_data"
    assert live["FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS"] == "10"
    assert live["FUTURES_ROUTER_SLIPPAGE_GATE"] == "true"
    assert live["FUTURES_ORDER_ROUTER_SEED_COUNT"] == "50"
    assert live["FUTURES_STRATEGY_SYMBOL"] == ""
    assert live["FUTURES_DECISION_ENGINE_SETUPS"] == ""
    assert live["FUTURES_EXECUTOR_TRADING_MODE"] == "PAPER"
    assert live["OPENAI_API_KEY"] == ""
    assert live["DART_API_KEY"] == ""
    assert live["MARKETAUX_API_TOKEN"] == ""
    assert live["NAVER_SEARCH_CLIENT_ID"] == ""
    assert live["NAVER_SEARCH_CLIENT_SECRET"] == ""
    assert live["NEWS_SCORER_CONSUMER_GROUP"] == "news_scorer-v1"


def test_compose_trader_passes_kis_market_env_to_trading_runtime():
    # The legacy services/api `app` container was removed in the dashboard-API
    # consolidation; the trader (trading loop) is now the KIS trading runtime
    # that must receive the KIS market env.
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    trader_env = compose["services"]["trader"]["environment"]

    assert "KIS_IS_REAL" in trader_env
    assert "KIS_REAL_TRADING" in trader_env
    assert "KIS_MARKET" in trader_env
    assert "KIS_STOCK_MARKET" in trader_env
    assert "KIS_FUTURES_MARKET" in trader_env
    assert "KIS_STOCK_APP_KEY" in trader_env
    assert "KIS_STOCK_APP_SECRET" in trader_env
    assert "KIS_FUTURES_APP_KEY" in trader_env
    assert "KIS_FUTURES_APP_SECRET" in trader_env
    assert "TELEGRAM_STOCK_BOT_TOKEN" in trader_env
    assert "TELEGRAM_FUTURES_BOT_TOKEN" in trader_env
    assert trader_env["KIS_TOKEN_CACHE_DIR"] == "${KIS_TOKEN_CACHE_DIR:-/app/.cache}"


def test_compose_trader_is_profile_gated_and_uses_runtime_env():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    trader = compose["services"]["trader"]
    trader_env = trader["environment"]

    assert trader["profiles"] == ["trading"]
    assert trader["command"] == ["bash", "scripts/docker/trading_loop_entrypoint.sh"]
    assert trader["depends_on"]["redis"]["condition"] == "service_healthy"
    assert trader_env["TRADING_MODE"] == "${TRADING_MODE:-paper}"
    assert trader_env["TRADING_ASSET_CLASS"] == "${TRADING_ASSET_CLASS:-stock}"
    assert trader_env["TRADING_LIVE_CONFIRM"] == "${TRADING_LIVE_CONFIRM:-}"
    assert trader_env["KIS_TOKEN_CACHE_DIR"] == "${KIS_TOKEN_CACHE_DIR:-/app/.cache}"


def test_strategy_builder_ui_receives_dashboard_public_api_key():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    service = compose["services"]["strategy-builder-ui"]

    assert (
        service["build"]["args"]["NEXT_PUBLIC_API_KEY"]
        == "${NEXT_PUBLIC_API_KEY:-${DASHBOARD_API_KEY:-}}"
    )
    assert (
        "NEXT_PUBLIC_API_KEY=${NEXT_PUBLIC_API_KEY:-${DASHBOARD_API_KEY:-}}"
        in service["environment"]
    )


def test_stock_pipeline_compose_services_are_profile_gated():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    ingest = services["stock-market-ingest"]
    assert ingest["profiles"] == ["stock-ingest"]
    assert ingest["command"] == ["python", "-m", "services.market_ingest.main"]
    assert ingest["environment"]["INGEST_ASSET"] == "stock"
    assert ingest["environment"]["INGEST_MAX_SYMBOLS"] == "${INGEST_MAX_SYMBOLS:-40}"
    assert "KIS_STOCK_APP_KEY" in ingest["environment"]
    assert "KIS_STOCK_APP_SECRET" in ingest["environment"]

    expected_pipeline = {
        "stock-strategy": (
            ["python", "-m", "services.stock_strategy.main"],
            "STOCK_STRATEGY_DAEMON",
        ),
        "stock-risk-filter": (
            ["python", "-m", "services.stock_risk_filter.main"],
            "STOCK_RISK_FILTER",
        ),
        "stock-order-router": (
            ["python", "-m", "services.stock_order_router.main"],
            "STOCK_ORDER_ROUTER",
        ),
        "stock-exit": (
            ["python", "-m", "services.stock_exit.main"],
            "STOCK_EXIT_DAEMON",
        ),
        "stock-monitor": (
            ["python", "-m", "services.stock_monitor.main"],
            "STOCK_MONITOR_DAEMON",
        ),
    }
    for service_name, (command, mode_env_key) in expected_pipeline.items():
        service = services[service_name]
        service_env = service["environment"]

        assert service["profiles"] == ["stock-pipeline"]
        assert service["command"] == command
        assert service["depends_on"]["redis"]["condition"] == "service_healthy"
        assert service_env[mode_env_key] == "${STOCK_PIPELINE_MODE:-shadow}"

    assert (
        services["stock-risk-filter"]["environment"]["STOCK_POSITIONS_KEY"]
        == "${STOCK_POSITIONS_KEY:-stock:daemon:positions}"
    )
    assert (
        services["stock-order-router"]["environment"]["STOCK_PAPER_SLIPPAGE_RATE"]
        == "${STOCK_PAPER_SLIPPAGE_RATE:-0.0001}"
    )
    assert (
        services["stock-monitor"]["environment"]["TRADING_STATE_KEY_SUFFIX"]
        == "${STOCK_TRADING_STATE_KEY_SUFFIX:-}"
    )
    assert "TELEGRAM_STOCK_BOT_TOKEN" in services["stock-monitor"]["environment"]
    assert "TELEGRAM_STOCK_CHAT_ID" in services["stock-monitor"]["environment"]


def test_news_llm_compose_services_are_profile_gated():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    collector = services["news-collector"]
    collector_env = collector["environment"]
    assert collector["profiles"] == ["news"]
    assert collector["command"] == ["python", "-m", "services.news_collector.main"]
    assert collector["depends_on"]["redis"]["condition"] == "service_healthy"
    assert collector["container_name"] == "${COMPOSE_PROJECT_NAME:-kis}-news-collector"
    assert (
        collector_env["REDIS_URL"]
        == "${REDIS_URL:-redis://:${REDIS_PASSWORD-changeme}@redis:6379/1}"
    )
    assert collector_env["DART_API_KEY"] == "${DART_API_KEY:-}"
    assert collector_env["MARKETAUX_API_TOKEN"] == "${MARKETAUX_API_TOKEN:-}"
    assert collector_env["NAVER_SEARCH_CLIENT_ID"] == "${NAVER_SEARCH_CLIENT_ID:-}"
    assert (
        collector_env["NAVER_SEARCH_CLIENT_SECRET"] == "${NAVER_SEARCH_CLIENT_SECRET:-}"
    )

    scorer = services["news-scorer"]
    scorer_env = scorer["environment"]
    assert scorer["profiles"] == ["news"]
    assert scorer["command"] == ["python", "-m", "services.news_scorer.main"]
    assert scorer["depends_on"]["redis"]["condition"] == "service_healthy"
    assert scorer["container_name"] == "${COMPOSE_PROJECT_NAME:-kis}-news-scorer"
    assert (
        scorer_env["REDIS_URL"]
        == "${REDIS_URL:-redis://:${REDIS_PASSWORD-changeme}@redis:6379/1}"
    )
    assert scorer_env["OPENAI_API_KEY"] == "${OPENAI_API_KEY:-}"
    assert (
        scorer_env["NEWS_SCORER_CONSUMER_GROUP"]
        == "${NEWS_SCORER_CONSUMER_GROUP:-news_scorer-v1}"
    )


def test_futures_pipeline_compose_services_are_profile_gated():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    ingest = services["futures-market-ingest"]
    assert ingest["profiles"] == ["futures-ingest"]
    assert ingest["command"] == ["python", "-m", "services.market_ingest.main"]
    assert ingest["environment"]["INGEST_ASSET"] == "futures"
    assert "KIS_FUTURES_APP_KEY" in ingest["environment"]
    assert "KIS_FUTURES_APP_SECRET" in ingest["environment"]

    # shadow|live daemons share FUTURES_PIPELINE_MODE; order_router uses paper|live.
    expected_pipeline = {
        "futures-decision-engine": (
            ["python", "-m", "services.decision_engine.main"],
            "FUTURES_STRATEGY_DAEMON",
            "${FUTURES_PIPELINE_MODE:-shadow}",
        ),
        "futures-risk-filter": (
            ["python", "-m", "services.risk_filter.main"],
            "FUTURES_RISK_FILTER",
            "${FUTURES_PIPELINE_MODE:-shadow}",
        ),
        "futures-order-router": (
            ["python", "-m", "services.order_router.main"],
            "FUTURES_ORDER_ROUTER",
            "${FUTURES_ORDER_ROUTER_MODE:-paper}",
        ),
        "futures-monitor": (
            ["python", "-m", "services.futures_monitor.main"],
            "FUTURES_MONITOR_DAEMON",
            "${FUTURES_PIPELINE_MODE:-shadow}",
        ),
    }
    for service_name, (command, mode_env_key, mode_value) in expected_pipeline.items():
        service = services[service_name]
        service_env = service["environment"]
        assert service["profiles"] == ["futures-pipeline"]
        assert service["command"] == command
        assert service["depends_on"]["redis"]["condition"] == "service_healthy"
        assert service_env[mode_env_key] == mode_value

    # The decision_engine's roster/parameters come from
    # config/strategies/futures/*.yaml (strategy.enabled + strategy.entry.params).
    # This env is the optional DAEMON-ONLY subset: it narrows the decoupled
    # roster without flipping the strategy.enabled switch that trader-futures
    # shares. It must be plumbed in compose because `.env.paper` is
    # interpolation-only, and it must default to empty (= every enabled setup).
    assert (
        services["futures-decision-engine"]["environment"][
            "FUTURES_DECISION_ENGINE_SETUPS"
        ]
        == "${FUTURES_DECISION_ENGINE_SETUPS:-}"
    )

    # order_router keeps the futures creds in both feed modes: the REST order
    # path needs them, and `ws` additionally needs them for market data.
    order_env = services["futures-order-router"]["environment"]
    assert "KIS_FUTURES_APP_KEY" in order_env
    assert "KIS_FUTURES_APP_SECRET" in order_env
    # Feed source defaults to the tick stream (no second KIS futures WS beside
    # trader-futures); the stream name must match what futures-monitor and the
    # producer use, or the router reads an empty stream and never quotes.
    assert (
        order_env["FUTURES_ORDER_ROUTER_FEED"] == "${FUTURES_ORDER_ROUTER_FEED:-stream}"
    )
    assert order_env["FUTURES_TICK_STREAM"] == "${FUTURES_TICK_STREAM:-raw_data}"
    assert (
        order_env["FUTURES_TICK_STREAM"]
        == services["futures-monitor"]["environment"]["FUTURES_TICK_STREAM"]
    )
    # Executor real/paper gate (dedicated knob, safe PAPER default).
    assert order_env["TRADING_MODE"] == "${FUTURES_EXECUTOR_TRADING_MODE:-PAPER}"

    # monitor needs futures Telegram (live alerts).
    monitor_env = services["futures-monitor"]["environment"]
    assert "TELEGRAM_FUTURES_BOT_TOKEN" in monitor_env
    assert "TELEGRAM_FUTURES_CHAT_ID" in monitor_env

    # kill_switch is live-only safety, isolated in its own profile.
    kill = services["futures-kill-switch"]
    assert kill["profiles"] == ["futures-killswitch"]
    assert kill["command"] == ["python", "-m", "services.kill_switch.main"]
    assert "TELEGRAM_FUTURES_BOT_TOKEN" in kill["environment"]
    assert (
        kill["environment"]["KIS_FUTURES_EQUITY_KRW"]
        == "${KIS_FUTURES_EQUITY_KRW:-100000000}"
    )


def test_futures_daemons_share_contract_resolution_env_with_orchestrator():
    """Every futures daemon that calls resolve_futures_instrument_from_env()
    must receive the same FUTURES_TRADING_PRODUCT / FUTURES_STRATEGY_SYMBOL
    knobs as `trader-futures`, or it silently defaults to `mini` and shadows a
    different contract than the orchestrator's raw_data ticks (F-9 Gate 1,
    2026-09-07: A05609 vs A01609). `.env.paper` is interpolation-only, so the
    knob has to be plumbed in compose. TZ keeps their logs KST like the stock
    daemons (logging-only)."""
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    orchestrator_env = services["trader-futures"]["environment"]
    product = orchestrator_env["FUTURES_TRADING_PRODUCT"]
    symbol = orchestrator_env["FUTURES_STRATEGY_SYMBOL"]
    assert product == "${FUTURES_TRADING_PRODUCT:-mini}"
    assert symbol == "${FUTURES_STRATEGY_SYMBOL:-}"

    instrument_resolvers = (
        "futures-market-ingest",
        "futures-decision-engine",
        "futures-order-router",
        "futures-monitor",
    )
    for service_name in instrument_resolvers:
        env = services[service_name]["environment"]
        assert env["FUTURES_TRADING_PRODUCT"] == product, service_name
        assert env["FUTURES_STRATEGY_SYMBOL"] == symbol, service_name

    # order_router runs the send-time slippage gate (F-9 Gate 1b) from the same
    # execution.yaml as the orchestrator; tick size and the paper spread cap are
    # env-interpolated inside the container and MUST travel with the product
    # (mini 0.02 / F200 0.05) — otherwise spread_ticks = spread / tick_size is
    # mis-scaled and every entry is blocked.
    router_env = services["futures-order-router"]["environment"]
    for knob in ("FUTURES_SLIPPAGE_TICK_SIZE", "FUTURES_PAPER_MAX_SPREAD_TICKS"):
        assert router_env[knob] == orchestrator_env[knob], knob
    # Router-only quote-freshness reject: the monolith ignores the YAML key, so
    # unlike the two above it is plumbed here and NOT to trader-futures. Without
    # it the container is stuck on the YAML default (`.env.*` is
    # interpolation-only) and the knob cannot be tuned per deployment.
    assert (
        router_env["FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS"]
        == "${FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS:-10}"
    )
    # The gate's own rollback switch, same router-only shape.
    assert (
        router_env["FUTURES_ROUTER_SLIPPAGE_GATE"]
        == "${FUTURES_ROUTER_SLIPPAGE_GATE:-true}"
    )
    assert (
        router_env["FUTURES_ORDER_ROUTER_SEED_COUNT"]
        == "${FUTURES_ORDER_ROUTER_SEED_COUNT:-50}"
    )
    assert (
        router_env["FUTURES_SLIPPAGE_TICK_SIZE"]
        == "${FUTURES_SLIPPAGE_TICK_SIZE:-0.02}"
    )
    assert (
        router_env["FUTURES_PAPER_MAX_SPREAD_TICKS"]
        == "${FUTURES_PAPER_MAX_SPREAD_TICKS:-6}"
    )

    for service_name in instrument_resolvers + (
        "futures-risk-filter",
        "futures-kill-switch",
    ):
        assert services[service_name]["environment"]["TZ"] == "Asia/Seoul", service_name


def test_scheduler_mounts_data_market_and_reports_writable():
    """The scheduler runs EOD backfills + report jobs, so data/market and reports
    must be writable (the shared pipeline-service mount is data/market:ro and does
    not mount reports — see fix/scheduler-writable-data-reports)."""
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    scheduler = compose["services"]["scheduler"]
    volumes = scheduler["volumes"]

    # data/market writable (NOT :ro) — EOD parquet backfills write here.
    assert "./data/market:/app/data/market" in volumes
    assert "./data/market:/app/data/market:ro" not in volumes

    # reports mounted + writable — verification/counterfactual/rotate jobs persist here.
    assert "./reports:/app/reports" in volumes

    # config stays read-only (jobs only read config).
    assert "./config:/app/config:ro" in volumes


def test_recovery_sentinel_path_is_under_a_volume_mounted_into_order_router():
    """LEGACY-007: config/kill_switch.yaml::kill_switch.recovery_sentinel_path is
    read by services/order_router/main.py, which runs *inside* the
    futures-order-router container — a container-local path (e.g. /var/run)
    would never be visible to it. The sentinel's parent directory must be
    inside a bind mount actually attached to that service, exactly like
    sentinel_path (the kill-switch sentinel) already is."""
    from services.kill_switch.config import KillSwitchConfig

    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    order_router_volumes = compose["services"]["futures-order-router"]["volumes"]

    cfg = KillSwitchConfig.from_yaml()
    for container_path in (cfg.sentinel_path, cfg.recovery_sentinel_path):
        container_dir = str(Path(container_path).parent)
        mounted_container_dirs = [
            v.split(":")[1] for v in order_router_volumes if ":" in v
        ]
        assert any(
            container_dir == mount_dir or container_dir.startswith(mount_dir + "/")
            for mount_dir in mounted_container_dirs
        ), (
            f"{container_path} (dir {container_dir}) is not under any volume "
            f"mounted into futures-order-router: {order_router_volumes}"
        )

    # And the two sentinels are genuinely distinct files, not accidental aliases.
    assert cfg.sentinel_path != cfg.recovery_sentinel_path


def test_runtime_mount_helper_agrees_with_the_actual_compose_volume():
    """shared.config.runtime_defaults.host_path_for_container_runtime_path()
    hardcodes BOTH halves of the docker-compose.yml x-trading-runtime-volumes
    bind mount (the container prefix it matches, and the host-relative dir
    it derives). scripts/trading/recover_positions.py (host-run) uses that
    helper to compute where to *write* the sentinel that order_router (in
    the futures-order-router container) *reads* via config — if the two
    halves of the mapping ever drift apart (someone edits docker-compose.yml
    without touching the helper, or vice versa), the write and read paths
    silently diverge and the guard never arms. This test derives the actual
    mounted volume from docker-compose.yml (not a re-hardcoded literal) and
    checks the helper's derived host path against it, so changing either
    side alone fails CI."""
    from shared.config.runtime_defaults import host_path_for_container_runtime_path

    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    order_router_volumes = compose["services"]["futures-order-router"]["volumes"]

    # Find the volume(s) whose container-side prefix the helper actually
    # matches — probed via the public helper, not by importing its private
    # prefix constant, so this test exercises the same code path
    # recover_positions.py does.
    matches: list[tuple[str, str, Path]] = []
    for entry in order_router_volumes:
        if ":" not in entry:
            continue
        host_part, container_part = entry.split(":")[0], entry.split(":")[1]
        try:
            derived = host_path_for_container_runtime_path(
                container_part.rstrip("/") + "/__probe__"
            )
        except ValueError:
            continue
        matches.append((entry, host_part, derived.parent))

    assert matches, (
        "No volume mounted into futures-order-router matches the container "
        "prefix host_path_for_container_runtime_path() expects — the helper "
        f"and docker-compose.yml have drifted apart. volumes={order_router_volumes}"
    )
    assert len(matches) == 1, (
        f"Ambiguous: more than one mounted volume matches the helper's "
        f"container prefix: {matches}"
    )

    entry, host_part, derived_host_dir = matches[0]
    assert host_part.startswith("./"), f"expected a repo-relative mount, got {entry!r}"
    expected_host_dir = (_REPO_ROOT / host_part[2:]).resolve()

    assert derived_host_dir == expected_host_dir, (
        f"host_path_for_container_runtime_path() derives {derived_host_dir} "
        f"but docker-compose.yml volume {entry!r} actually mounts "
        f"{expected_host_dir} on the host — the two halves of the runtime "
        "mount mapping have drifted apart."
    )


def test_producer_and_consumer_futures_tick_stream_defaults_agree():
    """The producers publish to MONITOR_FUTURES_TICK_STREAM and the consumers
    read FUTURES_TICK_STREAM. Two names, one stream: if they ever drift apart
    the consumers read an empty stream and block every signal, with no error
    anywhere. Pinned per the #622 F2 pattern.

    Reads the pydantic default rather than ``from_env()`` so the test does not
    depend on the ambient environment.
    """
    from services.monitoring.tick_stream_publisher import TickStreamPublisherConfig
    from shared.models.stream_models import DEFAULT_FUTURES_TICK_STREAM

    producer_default = TickStreamPublisherConfig().futures_stream
    assert producer_default == DEFAULT_FUTURES_TICK_STREAM

    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    expression = "${FUTURES_TICK_STREAM:-" + producer_default + "}"

    producers = ("trader-futures", "futures-market-ingest")
    for name in producers:
        assert services[name]["environment"]["MONITOR_FUTURES_TICK_STREAM"] == (
            expression
        ), name

    consumers = ("futures-order-router", "futures-monitor", "futures-decision-engine")
    for name in consumers:
        assert services[name]["environment"]["FUTURES_TICK_STREAM"] == expression, name

    for name in (".env.paper.example", ".env.live.example"):
        assert _read_env_template(name)["FUTURES_TICK_STREAM"] == producer_default
