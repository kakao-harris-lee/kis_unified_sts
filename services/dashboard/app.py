"""FastAPI dashboard application.

Serves the React SPA frontend and provides API endpoints for trading data.
The React app is built from dashboard-frontend/ and served as static files.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shared.api.cors import get_cors_config, load_api_config
from shared.strategy.registry import register_builtin_components

logger = logging.getLogger(__name__)

# React SPA build output directory
# Docker: /app/static (copied from build stage)
# Local dev: dashboard-frontend/dist (after bun run build)
_STATIC_DIR = Path(
    os.environ.get(
        "DASHBOARD_STATIC_DIR",
        "/app/static" if Path("/app/static").exists() else "dashboard-frontend/dist",
    )
)

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
    """Register API routes and React SPA static file serving."""
    from services.dashboard.routes import (
        health,
        kis_builder,
        metrics,
        signals,
        strategies,
        strategy_builder,
        strategy_lab,
        trades,
        trading,
    )
    from services.dashboard.websocket import websocket_endpoint

    # Include API routers (registered first — take priority over SPA catch-all)
    app.include_router(trading.router)
    app.include_router(signals.router)
    app.include_router(strategy_builder.router)
    app.include_router(kis_builder.router)
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

    # React SPA static files
    static_dir = _STATIC_DIR
    assets_dir = static_dir / "assets"
    index_html = static_dir / "index.html"

    if assets_dir.exists():
        app.mount(
            "/assets", StaticFiles(directory=str(assets_dir)), name="static-assets"
        )
        logger.info(f"Serving React SPA assets from {assets_dir}")

    if index_html.exists():
        # SPA catch-all: any non-API path → index.html (React Router handles routing)
        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            # Serve actual static files if they exist (e.g. vite.svg, favicon)
            file_path = static_dir / path
            if path and file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(index_html))

        logger.info(f"React SPA enabled: {index_html}")
    else:
        logger.warning(
            f"React SPA not found at {static_dir}. "
            "Build the frontend: cd dashboard-frontend && bun run build"
        )

        @app.get("/")
        async def no_frontend():
            return {
                "message": "Dashboard frontend not built. Run: cd dashboard-frontend && bun run build",
                "api_docs": "/docs",
            }
