"""FastAPI dashboard application — the Control Plane API (BFF) for ``/tos``.

After the legacy-removal plan's L4
(``docs/plans/2026-11-07-legacy-removal-plan.md`` §3) this app mounts exactly
three things:

* ``GET /api/tos/projection`` (``routes/tos_projection.py``) — the read-only
  tos_runtime operator projection the Next.js ``/tos`` page polls.
* ``GET /api/tos/sessions/{id}/bars`` (``routes/tos_bars.py``) — the read-only
  per-bar inspection of a recorded CP-3 session, exported on the host by
  ``tools/tos_cp3/export_bars.py`` (roadmap
  ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1). Same boundary as the
  projection: a file opened by path, no ``tos``/``tos_runtime`` import.
* ``GET /health`` — the container health check. ``Dockerfile.dashboard``'s
  ``HEALTHCHECK`` and ``docker-compose.yml`` both curl it, and
  ``strategy-builder-ui`` / ``caddy`` wait on ``service_healthy``, so it stays
  unauthenticated (``middleware/auth.py::PUBLIC_PATHS``).

Everything else — the trading/signals/trades/strategy/health/metrics routers,
the ``/ws`` WebSocket with its manager and publisher, the HTML view middleware
and the strategy-registry startup call — was deleted with the legacy runtime
it served. The UI is served separately by the Next.js app
(``strategy-builder-ui``) and reaches these endpoints through Caddy on the
host-published ``DASHBOARD_HOST_PORT``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.api.cors import get_cors_config, load_api_config

logger = logging.getLogger(__name__)

# All dashboard UI is served through Caddy on DASHBOARD_HOST_PORT. Internally,
# Caddy routes API traffic to this FastAPI service on dashboard:8001 and UI
# traffic to strategy-builder-ui:3100. Neither internal service port is
# host-published.

# OpenAPI tags for documentation organization
OPENAPI_TAGS = [
    {
        "name": "tos",
        "description": (
            "Read-only tos_runtime operator projection (Phase 5 W4; not an "
            "authority source)"
        ),
    },
]


def create_app(
    title: str = "KIS Unified Trading Dashboard",
    debug: bool = False,
    require_auth: bool | None = None,
    api_key: str | None = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        title: Application title.
        debug: Enable debug mode.
        require_auth: If True, require API key authentication. If None (default), enables auth if api_key is available.
        api_key: The API key to use for authentication. Reads from DASHBOARD_API_KEY env var if not provided.
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

    app = FastAPI(
        title=title,
        description="Real-time trading dashboard for KIS unified platform",
        version="1.0.0",
        debug=debug,
        openapi_tags=OPENAPI_TAGS,
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

    # API key authentication middleware
    if require_auth and api_key:
        from services.dashboard.middleware.auth import APIKeyMiddleware

        app.add_middleware(APIKeyMiddleware, api_key=api_key)

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register the two TOS read-model routers and the container health endpoint."""
    from services.dashboard.routes import tos_bars, tos_projection

    app.include_router(tos_projection.router)
    app.include_router(tos_bars.router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
        }
