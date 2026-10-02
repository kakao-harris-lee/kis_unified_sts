"""ConfigLoader env var substitution tests."""

from shared.config.loader import ConfigLoader


def test_loader_resolves_env_vars_with_defaults(config_dir, monkeypatch):
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

    loaded = ConfigLoader.load("storage.yaml")
    assert loaded["runtime_storage"]["backend"] == "sqlite"
    assert loaded["runtime_storage"]["path"] == "data/runtime/test/runtime.db"
    assert loaded["runtime_storage"]["missing"] == "abc"


def test_loader_resolves_simple_env_var(config_dir, monkeypatch):
    (config_dir / "simple.yaml").write_text("value: ${SOME_ENV}\n")

    monkeypatch.setenv("SOME_ENV", "hello")

    loaded = ConfigLoader.load("simple.yaml")
    assert loaded["value"] == "hello"
