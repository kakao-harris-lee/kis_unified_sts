"""Shared CLI command defaults."""

from shared.config.dotenv_guard import load_project_dotenv
from shared.config.runtime_defaults import dashboard_host_port_from_env

# Load .env before command modules capture shared Click defaults at import time.
# Bounded to this checkout (and the working directory) and switched off during
# tests: the argument-less load_dotenv() that used to live here walked up past
# a nested worktree into the primary checkout's .env and put real KIS
# credentials in the pytest process (#698).
load_project_dotenv()

DEFAULT_DASHBOARD_HOST_PORT = dashboard_host_port_from_env()
DEFAULT_DASHBOARD_URL = f"http://localhost:{DEFAULT_DASHBOARD_HOST_PORT}"
