from pathlib import Path

import pytest

from shared.config.runtime_defaults import (
    DEFAULT_DASHBOARD_HOST_PORT,
    DEFAULT_REDIS_URL,
    dashboard_host_port_from_env,
    host_path_for_container_runtime_path,
    redis_url_from_env,
)


def test_default_redis_url_uses_db_1() -> None:
    assert DEFAULT_REDIS_URL == "redis://localhost:6379/1"


def test_default_dashboard_host_port_is_5081() -> None:
    assert DEFAULT_DASHBOARD_HOST_PORT == "5081"


def test_redis_url_from_env_prefers_override(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379/1")

    assert redis_url_from_env() == "redis://redis.internal:6379/1"


def test_dashboard_host_port_from_env_prefers_override(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_HOST_PORT", "15081")

    assert dashboard_host_port_from_env() == "15081"


class TestHostPathForContainerRuntimePath:
    """Maps the container-side ``/app/data/runtime`` mount (shared by every
    trading-runtime compose service via ``x-trading-runtime-volumes`` in
    docker-compose.yml, ``./data/runtime:/app/data/runtime``) back to its
    host-side path — used by host-run scripts (not containerized) that must
    write to the same file a containerized consumer reads via its config."""

    def test_maps_container_runtime_path_to_repo_relative_host_path(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]

        result = host_path_for_container_runtime_path(
            "/app/data/runtime/kis_position_recovery.tripped"
        )

        assert (
            result == repo_root / "data" / "runtime" / "kis_position_recovery.tripped"
        )

    def test_maps_nested_container_runtime_path(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]

        result = host_path_for_container_runtime_path(
            "/app/data/runtime/sub/dir/file.txt"
        )

        assert result == repo_root / "data" / "runtime" / "sub" / "dir" / "file.txt"

    def test_rejects_path_outside_the_mounted_prefix(self) -> None:
        with pytest.raises(ValueError, match="not under"):
            host_path_for_container_runtime_path("/var/run/kis_kill_switch.tripped")

    def test_rejects_the_bare_mount_root_without_a_relative_component(self) -> None:
        with pytest.raises(ValueError, match="not under"):
            host_path_for_container_runtime_path("/app/data/runtime")
