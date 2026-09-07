"""Central runtime defaults for process entrypoints."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_REDIS_URL = "redis://localhost:6379/1"
DEFAULT_DASHBOARD_HOST_PORT = "5081"

# The bind mount every trading-runtime compose service shares (see
# docker-compose.yml x-trading-runtime-volumes: ./data/runtime:/app/data/runtime).
# Config values such as config/kill_switch.yaml::sentinel_path /
# recovery_sentinel_path are written in the container-side form because that
# is what the containerized consumers (order_router, kill_switch) actually
# check; a host-run script needs the host-side equivalent instead.
_CONTAINER_RUNTIME_MOUNT = "/app/data/runtime"
_HOST_RUNTIME_MOUNT_RELATIVE = ("data", "runtime")
_REPO_ROOT = Path(__file__).resolve().parents[2]


def redis_url_from_env() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def dashboard_host_port_from_env() -> str:
    return os.environ.get("DASHBOARD_HOST_PORT", DEFAULT_DASHBOARD_HOST_PORT)


def host_path_for_container_runtime_path(container_path: str) -> Path:
    """Map a container-side ``/app/data/runtime/...`` path to its host path.

    Host-run scripts (e.g. ``scripts/trading/recover_positions.py``) run
    directly on the host, outside any container, but must write to the same
    file a containerized consumer (e.g. ``services/order_router/main.py``)
    reads via ``config/kill_switch.yaml``. Both processes need to agree on
    exactly one file — deriving the host path from the single configured
    container path (rather than hardcoding a second host-side literal) keeps
    the read and write paths from silently diverging.

    Raises:
        ValueError: ``container_path`` is not under the shared runtime mount
            prefix (``/app/data/runtime``) — nothing to derive.
    """
    prefix = _CONTAINER_RUNTIME_MOUNT + "/"
    if not container_path.startswith(prefix):
        raise ValueError(
            f"{container_path!r} is not under the shared runtime mount "
            f"{_CONTAINER_RUNTIME_MOUNT!r} (docker-compose.yml "
            "x-trading-runtime-volumes) — cannot derive a host path."
        )
    relative = container_path[len(prefix) :]
    return _REPO_ROOT.joinpath(*_HOST_RUNTIME_MOUNT_RELATIVE, relative)
