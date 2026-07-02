"""FastAPI dashboard application.

API-only service: provides trading-data endpoints under /api/* plus /health,
/docs, /metrics, and the /ws WebSocket. The UI is served separately by the
Next.js app (strategy-builder-ui) and reaches these endpoints through Caddy on
the host-published DASHBOARD_HOST_PORT. (The Vite SPA that used to be served
from here was removed in the Next.js consolidation — see
docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md.)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from shared.api.cors import get_cors_config, load_api_config
from shared.config.runtime_defaults import dashboard_host_port_from_env
from shared.strategy.registry import register_builtin_components

logger = logging.getLogger(__name__)

# All dashboard UI is served through Caddy on DASHBOARD_HOST_PORT. Internally,
# Caddy routes API traffic to this FastAPI service on dashboard:8001 and UI
# traffic to strategy-builder-ui:3100. Neither internal service port is
# host-published.

# OpenAPI tags for documentation organization
OPENAPI_TAGS = [
    {
        "name": "trading",
        "description": "Trading operations and status management",
    },
    {
        "name": "signals",
        "description": "Trading signals and entry/exit alerts",
    },
    {
        "name": "trades",
        "description": "Trade history and performance statistics",
    },
    {
        "name": "strategies",
        "description": "Strategy configuration management",
    },
    {
        "name": "strategy-lab",
        "description": "Visual strategy builder, generated signals, and paper orders",
    },
    {
        "name": "strategy-builder",
        "description": "No-code technical indicator strategy builder",
    },
    {
        "name": "metrics",
        "description": "Performance and execution venue metrics",
    },
    {
        "name": "health",
        "description": "Operational health and observability endpoints",
    },
    {
        "name": "coverage",
        "description": "Universe, data, and experiment coverage diagnostics",
    },
    {
        "name": "event-context",
        "description": "Event score, news, macro, and Setup C diagnostics",
    },
    {
        "name": "evidence",
        "description": "Per-asset strategy evidence and promotion-readiness diagnostics",
    },
]


def create_app(
    title: str = "KIS Unified Trading Dashboard",
    debug: bool = False,
    require_auth: bool | None = None,
    api_key: str | None = None,
    rate_limit: int = 0,
    rate_limit_window: int = 60,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        title: Application title.
        debug: Enable debug mode.
        require_auth: If True, require API key authentication. If None (default), enables auth if api_key is available.
        api_key: The API key to use for authentication. Reads from DASHBOARD_API_KEY env var if not provided.
        rate_limit: Maximum requests per window. 0 disables rate limiting.
        rate_limit_window: Rate limit window in seconds.
    """
    # Read API key from environment if not provided
    if api_key is None:
        api_key = os.environ.get("DASHBOARD_API_KEY")

    # Check if dev mode is enabled (disables authentication)
    dev_mode = os.environ.get("DASHBOARD_DEV_MODE", "").lower() == "true"
    if dev_mode:
        logger.warning("Dev mode enabled - authentication disabled")
        require_auth = False
    elif require_auth is None:
        # Honor DASHBOARD_REQUIRE_AUTH env var (documented in .env.example)
        env_require = os.environ.get("DASHBOARD_REQUIRE_AUTH", "").lower()
        if env_require == "true":
            require_auth = True
        elif env_require == "false":
            require_auth = False
        else:
            # Fallback: enable auth if API key is available
            require_auth = bool(api_key)

    # Warn if auth is required but no API key is configured
    if require_auth and not api_key:
        logger.critical(
            "DASHBOARD_REQUIRE_AUTH=true but DASHBOARD_API_KEY is not set. "
            "All dashboard requests will be rejected."
        )

    # Initialize strategy registries
    register_builtin_components()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        # Startup: spawn WebSocket publisher (Redis pubsub + periodic ticks)
        publisher = None
        try:
            from services.dashboard.websocket import ws_manager
            from services.dashboard.websocket_publisher import WebSocketPublisher

            publisher = WebSocketPublisher(manager=ws_manager)
            await publisher.start()
            app.state.ws_publisher = publisher
            logger.info("WebSocket publisher started")
        except Exception as exc:  # noqa: BLE001
            logger.warning("WebSocket publisher failed to start: %s", exc)
            app.state.ws_publisher = None

        try:
            yield
        finally:
            # Shutdown: stop publisher
            publisher = getattr(app.state, "ws_publisher", None)
            if publisher is not None:
                try:
                    await publisher.stop()
                    logger.info("WebSocket publisher stopped")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("WebSocket publisher shutdown error: %s", exc)
                app.state.ws_publisher = None

    app = FastAPI(
        title=title,
        description="Real-time trading dashboard for KIS unified platform",
        version="1.0.0",
        debug=debug,
        openapi_tags=OPENAPI_TAGS,
        lifespan=_lifespan,
    )

    # Load CORS configuration (never uses wildcard origins)
    api_config = load_api_config()
    cors_config = get_cors_config(api_config)

    # CORS middleware - secure configuration without wildcard origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
    )

    # Rate limiting middleware (add first so it runs before auth)
    if rate_limit > 0:
        from services.dashboard.middleware.rate_limit import RateLimitMiddleware

        app.add_middleware(
            RateLimitMiddleware,
            requests_per_window=rate_limit,
            window_seconds=rate_limit_window,
        )

    # API key authentication middleware
    if require_auth and api_key:
        from services.dashboard.middleware.auth import APIKeyMiddleware

        app.add_middleware(APIKeyMiddleware, api_key=api_key)

    # HTML view middleware (renders HTML for browser requests to API endpoints)
    from services.dashboard.middleware.html_view import HTMLViewMiddleware

    app.add_middleware(HTMLViewMiddleware)

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register API routers, the /ws WebSocket, and the root pointer endpoint."""
    from services.dashboard.routes import (
        coverage,
        evidence,
        event_context,
        experiments,
        health,
        kis_builder,
        metrics,
        signals,
        strategies,
        strategy_builder,
        strategy_lab,
        trades,
        trading,
        universe,
    )
    from services.dashboard.websocket import websocket_endpoint

    # Include API routers (registered first — take priority over SPA catch-all)
    app.include_router(trading.router)
    app.include_router(universe.router)
    app.include_router(signals.router)
    app.include_router(strategy_builder.router)
    app.include_router(kis_builder.router)
    app.include_router(experiments.router)
    app.include_router(coverage.router)
    app.include_router(evidence.router)
    app.include_router(event_context.router)
    app.include_router(strategy_lab.router)
    app.include_router(trades.router)
    app.include_router(strategies.router)
    app.include_router(metrics.router, tags=["metrics"])
    app.include_router(health.router)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket_endpoint(websocket)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }

    # Dashboard FastAPI is API-only after the Vite → Next.js migration.
    # Direct hits to / return a minimal pointer; UI traffic is served by
    # strategy-builder-ui:3100 through Caddy.
    @app.get("/")
    async def root():
        dashboard_host_port = dashboard_host_port_from_env()
        return {
            "service": "kis-dashboard",
            "ui": f"http://localhost:{dashboard_host_port}/",
            "api_docs": "/docs",
        }
