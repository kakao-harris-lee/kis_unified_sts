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
    assert paper["FUTURES_ORDER_ROUTER_FEED"] == "stream"
    assert paper["FUTURES_TICK_STREAM"] == "raw_data"
    assert paper["FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS"] == "10"
    assert paper["FUTURES_ROUTER_SLIPPAGE_GATE"] == "true"
    assert paper["FUTURES_ORDER_ROUTER_SEED_COUNT"] == "50"
    assert paper["FUTURES_STRATEGY_SYMBOL"] == ""
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


def _read_compose() -> dict:
    return yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )


def test_strategy_builder_ui_receives_dashboard_public_api_key():
    compose = _read_compose()
    service = compose["services"]["strategy-builder-ui"]

    assert (
        service["build"]["args"]["NEXT_PUBLIC_API_KEY"]
        == "${NEXT_PUBLIC_API_KEY:-${DASHBOARD_API_KEY:-}}"
    )
    assert (
        "NEXT_PUBLIC_API_KEY=${NEXT_PUBLIC_API_KEY:-${DASHBOARD_API_KEY:-}}"
        in service["environment"]
    )


def test_default_stack_is_exactly_the_unprofiled_services():
    # `docker compose up -d` starts every service with no `profiles:` key. This
    # pins that set, so a service added behind a profile (cloudflared, tests)
    # cannot drift into the default stack — and one added with no profile at all
    # has to say so here.
    compose = _read_compose()
    unprofiled = {
        name
        for name, service in compose["services"].items()
        if not service.get("profiles")
    }
    assert unprofiled == {
        "dashboard",
        "strategy-builder-ui",
        "caddy",
        "redis",
        "prometheus",
    }


def test_cloudflare_tunnel_is_profile_gated_and_publishes_no_host_port():
    compose = _read_compose()
    service = compose["services"]["cloudflared"]

    # Profile-gated: the tunnel is opt-in, so a checkout without a token brings
    # the stack up unchanged.
    assert service["profiles"] == ["tunnel"]

    # The whole point of a tunnel is that nothing is published: cloudflared
    # dials out. A `ports:` key here would open an inbound host port and break
    # the single-entrypoint rule in docs/ports.md.
    assert "ports" not in service
    assert "expose" not in service

    assert service["networks"] == ["trading-network"]
    assert service["depends_on"] == ["caddy"]
    assert service["restart"] == "unless-stopped"
    assert service["command"] == "tunnel --no-autoupdate run"


def test_cloudflare_tunnel_image_is_pinned_and_token_comes_from_the_env_file():
    compose = _read_compose()
    service = compose["services"]["cloudflared"]

    repository, _, tag = service["image"].partition(":")
    assert repository == "cloudflare/cloudflared"
    # A moving tag would change the binary under a resident operator stack on an
    # unrelated `up -d`.
    assert tag not in {"", "latest"}
    assert tag[0].isdigit()

    # The token is a credential: it is interpolated from the (uncommitted) env
    # file and never written into the committed file. `:-` rather than `:?` so
    # an unset token cannot break `docker compose config` or the default stack.
    assert service["environment"] == {"TUNNEL_TOKEN": "${CLOUDFLARE_TUNNEL_TOKEN:-}"}


def test_env_example_ships_an_empty_cloudflare_tunnel_token():
    env_example = _read_env_template(".env.example")

    # Placeholder only. A non-empty value here would be a committed credential.
    assert env_example["CLOUDFLARE_TUNNEL_TOKEN"] == ""
    assert env_example["TOS_PUBLIC_HOSTNAME"]
