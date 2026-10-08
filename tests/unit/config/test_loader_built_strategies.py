"""ConfigLoader picks up builder_v1 strategies from config/strategies/built/."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config.loader import ConfigLoader


def _write_yaml(path: Path, name: str, asset_class: str, enabled: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "strategy:\n"
        f"  name: {name}\n"
        f"  asset_class: {asset_class}\n"
        f"  enabled: {str(enabled).lower()}\n"
        "  entry: {type: dummy, params: {}}\n"
        "  exit: {type: dummy, params: {}}\n"
        "  position: {type: fixed, params: {}}\n",
        encoding="utf-8",
    )


@pytest.fixture
def _loader_config_dir(tmp_path, monkeypatch):
    """Point ``ConfigLoader`` at ``tmp_path`` in a way that actually takes effect.

    ``KIS_CONFIG_DIR`` is read ONCE, by ``_initialize_config_dir`` on the first
    access to the class-level ``_config_dir`` (``shared/config/loader.py:97-108``).
    ``clear_cache()`` clears ``_cache`` and deliberately leaves ``_config_dir``
    alone (``:156-162``), so ``monkeypatch.setenv`` + ``clear_cache()`` is a NO-OP
    once anything in the process has already touched the loader — the env var is
    never re-read and the real ``config/`` stays pinned.

    That is not hypothetical. It is the CI failure of 2026-10-07 on run
    37698111242: ``test_built_dir_missing_is_not_an_error`` asserted
    ``names == ["only"]`` and got ``['momentum_breakout', 'pattern_pullback',
    'williams_r']`` — the repo's three real active stock strategies. The test
    passes when its file runs alone and fails when an earlier test in the same
    xdist worker initialised the loader first, so which way it lands depends on
    the shard boundaries, i.e. on the total test count elsewhere in the suite.

    ``set_config_dir`` is the supported API: it assigns ``_config_dir`` AND
    clears the cache (``:127-140``). Teardown resets ``_config_dir`` to ``None``
    rather than to its previous value, so the next consumer re-initialises from
    the environment instead of inheriting a path that is about to be deleted.

    The env var is still set, so code that reads it directly agrees with the
    loader, and a fresh initialisation inside the test also lands on ``tmp_path``.
    """
    monkeypatch.setenv("KIS_CONFIG_DIR", str(tmp_path))
    ConfigLoader.set_config_dir(tmp_path)
    yield tmp_path
    ConfigLoader._config_dir = None
    ConfigLoader.clear_cache()


@pytest.fixture
def fake_config(_loader_config_dir, tmp_path):
    _write_yaml(
        tmp_path / "strategies" / "stock" / "native_stock.yaml", "native_stock", "stock"
    )
    _write_yaml(
        tmp_path / "strategies" / "stock" / "disabled.yaml",
        "disabled_stock",
        "stock",
        enabled=False,
    )
    _write_yaml(
        tmp_path / "strategies" / "futures" / "native_fut.yaml", "native_fut", "futures"
    )
    _write_yaml(
        tmp_path / "strategies" / "built" / "built_stock.yaml", "built_stock", "stock"
    )
    _write_yaml(
        tmp_path / "strategies" / "built" / "built_fut.yaml", "built_fut", "futures"
    )
    return tmp_path


def _names(configs):
    return sorted(c["strategy"]["name"] for c in configs)


def test_stock_load_includes_built_stock(fake_config) -> None:
    names = _names(ConfigLoader.load_all_strategies(asset_class="stock"))
    assert "native_stock" in names
    assert "built_stock" in names
    # built futures must not leak into stock filter
    assert "built_fut" not in names


def test_futures_load_includes_built_futures(fake_config) -> None:
    names = _names(ConfigLoader.load_all_strategies(asset_class="futures"))
    assert "native_fut" in names
    assert "built_fut" in names
    assert "built_stock" not in names


def test_unfiltered_load_returns_everything_enabled(fake_config) -> None:
    names = _names(ConfigLoader.load_all_strategies(asset_class=None))
    assert sorted(names) == ["built_fut", "built_stock", "native_fut", "native_stock"]


def test_disabled_strategy_skipped_when_enabled_only(fake_config) -> None:
    names = _names(
        ConfigLoader.load_all_strategies(asset_class="stock", enabled_only=True)
    )
    assert "disabled_stock" not in names


def test_disabled_strategy_visible_when_enabled_only_false(fake_config) -> None:
    names = _names(
        ConfigLoader.load_all_strategies(asset_class="stock", enabled_only=False)
    )
    assert "disabled_stock" in names


def test_built_dir_missing_is_not_an_error(_loader_config_dir) -> None:
    """If config/strategies/built/ does not exist, stock load still works."""
    tmp_path = _loader_config_dir
    _write_yaml(tmp_path / "strategies" / "stock" / "only.yaml", "only", "stock")

    names = _names(ConfigLoader.load_all_strategies(asset_class="stock"))

    assert names == ["only"]


def test_setenv_alone_cannot_redirect_an_initialised_loader(
    tmp_path, monkeypatch
) -> None:
    """The latent bug, pinned with the input that triggers it.

    This is why :func:`_loader_config_dir` exists and why every test in this file
    goes through it. Without this test the trap stays invisible: the other
    assertions here are membership checks (``"disabled_stock" not in names``),
    which hold against the REAL config too, so they would keep passing for the
    wrong reason while silently measuring the wrong directory.
    """
    ConfigLoader.get_config_dir()  # any earlier test in the worker does this
    real_dir = ConfigLoader._config_dir
    try:
        monkeypatch.setenv("KIS_CONFIG_DIR", str(tmp_path))
        ConfigLoader.clear_cache()

        assert ConfigLoader.get_config_dir() == real_dir, (
            "clear_cache() must not be expected to re-read KIS_CONFIG_DIR; if "
            "this now passes, loader.py gained an env re-read and "
            "_loader_config_dir can be simplified."
        )

        ConfigLoader.set_config_dir(tmp_path)

        assert ConfigLoader.get_config_dir() == tmp_path
    finally:
        ConfigLoader._config_dir = None
        ConfigLoader.clear_cache()
