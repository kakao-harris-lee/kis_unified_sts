from shared.config.runtime_defaults import (
    DEFAULT_DASHBOARD_HOST_PORT,
    DEFAULT_REDIS_URL,
    dashboard_host_port_from_env,
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
