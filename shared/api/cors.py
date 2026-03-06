"""Shared CORS configuration utilities.

Provides a single source of truth for CORS settings used by both
the API server (`services/api/app.py`) and the dashboard
(`services/dashboard/app.py`).

Security:
- Never combines wildcard origins (`["*"]`) with `allow_credentials=True`.
- Explicit methods and headers only — no wildcard.
- Development mode defaults to localhost origins.
- Production mode defaults to empty origins (no access until configured).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# Allowed HTTP methods — explicit list for security
CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

# Allowed headers — explicit list for security
CORS_ALLOWED_HEADERS = [
    "Content-Type",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
    "Accept",
    "Accept-Language",
]

# Default localhost origins for development
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge *override* into *base* (mutates *base*)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_api_config() -> dict[str, Any]:
    """Load the ``api`` section from ``config/api.yaml``.

    Applies ``development`` overlay when ``ENVIRONMENT=development``.

    Returns:
        API configuration dictionary (empty dict on failure).
    """
    try:
        from shared.config.loader import ConfigLoader

        config = ConfigLoader.load("api.yaml")

        env = os.getenv("ENVIRONMENT", "production")
        if env == "development" and "development" in config:
            dev_config = config["development"].get("api", {})
            api_config = config.get("api", {})
            _deep_merge(api_config, dev_config)
            return api_config

        return config.get("api", {})
    except Exception as e:
        logger.warning(f"Failed to load api.yaml, using defaults: {e}")
        return {}


def get_cors_config(api_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build CORS middleware kwargs from config.

    Uses ``ENVIRONMENT`` env-var for dev-mode detection.
    Always uses explicit methods and headers for security.
    Rejects wildcard origins when credentials are enabled.

    Args:
        api_config: API configuration dict (``api`` section of api.yaml).

    Returns:
        Dictionary suitable for ``CORSMiddleware(**cors_config)``.
    """
    if api_config is None:
        api_config = {}

    env = os.getenv("ENVIRONMENT", "production")
    cors = api_config.get("cors", {})

    if env == "development":
        origins = cors.get("allowed_origins", _DEV_ORIGINS)
        credentials = True
    else:
        origins = cors.get("allowed_origins", [])
        credentials = cors.get("allow_credentials", False)

    # Security guard: never combine wildcard with credentials
    if credentials and "*" in origins:
        logger.warning(
            "CORS: wildcard origins with allow_credentials=True blocked — "
            "falling back to default dev origins"
        )
        origins = [o for o in origins if o != "*"] or _DEV_ORIGINS

    return {
        "allow_origins": origins,
        "allow_credentials": credentials,
        "allow_methods": cors.get("allowed_methods", CORS_ALLOWED_METHODS),
        "allow_headers": cors.get("allowed_headers", CORS_ALLOWED_HEADERS),
    }


__all__ = [
    "CORS_ALLOWED_METHODS",
    "CORS_ALLOWED_HEADERS",
    "load_api_config",
    "get_cors_config",
]
