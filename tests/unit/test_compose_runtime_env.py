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
