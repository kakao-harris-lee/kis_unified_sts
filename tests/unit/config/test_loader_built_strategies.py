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
    """Point ``ConfigLoader`` at ``tmp_path`` in a way that actually takes effect."""
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
    """The latent bug, pinned with the input that triggers it."""
    ConfigLoader.get_config_dir()
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
