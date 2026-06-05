"""ConfigLoader env var substitution tests."""

from shared.config.loader import ConfigLoader


def test_loader_resolves_env_vars_with_defaults(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "storage.yaml").write_text(
        "\n".join(
            [
                "runtime_storage:",
                "  backend: ${RUNTIME_STORAGE_BACKEND:sqlite}",
                "  path: ${RUNTIME_STORAGE_SQLITE_PATH:data/runtime/dev/runtime.db}",
                "  missing: ${MISSING_VAR:abc}",
            ]
        )
        + "\n"
    )

    monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", "data/runtime/test/runtime.db")

    ConfigLoader.set_config_dir(config_dir)

    loaded = ConfigLoader.load("storage.yaml")
    assert loaded["runtime_storage"]["backend"] == "sqlite"
    assert loaded["runtime_storage"]["path"] == "data/runtime/test/runtime.db"
    assert loaded["runtime_storage"]["missing"] == "abc"


def test_loader_resolves_simple_env_var(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "simple.yaml").write_text("value: ${SOME_ENV}\n")

    monkeypatch.setenv("SOME_ENV", "hello")
    ConfigLoader.set_config_dir(config_dir)

    loaded = ConfigLoader.load("simple.yaml")
    assert loaded["value"] == "hello"
