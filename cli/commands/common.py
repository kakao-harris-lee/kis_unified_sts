"""Shared CLI command defaults."""

from dotenv import load_dotenv

from shared.config.runtime_defaults import dashboard_host_port_from_env

# Load .env before command modules capture shared Click defaults at import time.
load_dotenv()

DEFAULT_DASHBOARD_HOST_PORT = dashboard_host_port_from_env()
DEFAULT_DASHBOARD_URL = f"http://localhost:{DEFAULT_DASHBOARD_HOST_PORT}"
