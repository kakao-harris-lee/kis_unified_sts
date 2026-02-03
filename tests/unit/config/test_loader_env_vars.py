"""ConfigLoader env var substitution tests."""

from shared.config.loader import ConfigLoader


def test_loader_resolves_env_vars_with_defaults(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "clickhouse.yaml").write_text(
        "\n".join(
            [
                "clickhouse:",
                "  host: ${CLICKHOUSE_HOST:localhost}",
                "  port: ${CLICKHOUSE_PORT:9000}",
                "  password: ${CLICKHOUSE_PASSWORD:}",
                "  missing: ${MISSING_VAR:abc}",
            ]
        )
        + "\n"
    )

    monkeypatch.setenv("CLICKHOUSE_HOST", "example-host")
    monkeypatch.setenv("CLICKHOUSE_PORT", "1234")
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)

    ConfigLoader.set_config_dir(config_dir)

    loaded = ConfigLoader.load("clickhouse.yaml")
    assert loaded["clickhouse"]["host"] == "example-host"
    assert loaded["clickhouse"]["port"] == "1234"
    assert loaded["clickhouse"]["password"] == ""
    assert loaded["clickhouse"]["missing"] == "abc"


def test_loader_resolves_simple_env_var(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "simple.yaml").write_text("value: ${SOME_ENV}\n")

    monkeypatch.setenv("SOME_ENV", "hello")
    ConfigLoader.set_config_dir(config_dir)

    loaded = ConfigLoader.load("simple.yaml")
    assert loaded["value"] == "hello"
