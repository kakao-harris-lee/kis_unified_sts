"""Central runtime defaults for process entrypoints."""

from __future__ import annotations

import os

DEFAULT_REDIS_URL = "redis://localhost:6379/1"
DEFAULT_DASHBOARD_HOST_PORT = "5081"


def redis_url_from_env() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def dashboard_host_port_from_env() -> str:
    return os.environ.get("DASHBOARD_HOST_PORT", DEFAULT_DASHBOARD_HOST_PORT)
