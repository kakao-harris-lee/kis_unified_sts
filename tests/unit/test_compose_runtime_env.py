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

    assert live["COMPOSE_PROJECT_NAME"] == "kis_live"
    assert live["KIS_IS_REAL"] == "true"
    assert live["KIS_REAL_TRADING"] == "true"
    assert live["KIS_STOCK_MARKET"] == "real"
    assert live["KIS_FUTURES_MARKET"] == "real"
    assert live["TRADING_MODE"] == "live"
    assert live["TRADING_LIVE_CONFIRM"] == ""
    assert live["KIS_TOKEN_CACHE_DIR"] == "/app/.cache"


def test_compose_app_passes_kis_market_env_to_trading_runtime():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    app_env = compose["services"]["app"]["environment"]

    assert "KIS_IS_REAL" in app_env
    assert "KIS_REAL_TRADING" in app_env
    assert "KIS_MARKET" in app_env
    assert "KIS_STOCK_MARKET" in app_env
    assert "KIS_FUTURES_MARKET" in app_env
    assert app_env["KIS_TOKEN_CACHE_DIR"] == "${KIS_TOKEN_CACHE_DIR:-/app/.cache}"


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
