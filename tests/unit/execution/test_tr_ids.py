"""Tests for shared/execution/tr_ids.py — Phase 5 Gate-2 prep.

Verifies that:
  - tr_id() returns the YAML-overridden value when present.
  - tr_id() falls back to the baked _DEFAULTS when YAML is absent or
    incomplete.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    from shared.config.loader import ConfigLoader
    from shared.execution.tr_ids import get_tr_ids

    ConfigLoader.clear_cache()
    get_tr_ids.cache_clear()
    yield
    ConfigLoader.clear_cache()
    get_tr_ids.cache_clear()


def test_defaults_match_documented_values():
    """Baked defaults must match the historical Field defaults so that
    deleting kis/tr_ids.yaml leaves runtime behaviour unchanged."""
    from shared.execution.tr_ids import _DEFAULTS

    assert _DEFAULTS["stock_krx_buy_real"] == "TTTC0802U"
    assert _DEFAULTS["stock_krx_sell_real"] == "TTTC0801U"
    assert _DEFAULTS["stock_ats_buy_real"] == "TTTC0852U"
    assert _DEFAULTS["futures_order_day_real"] == "TTTO1101U"
    assert _DEFAULTS["futures_order_night_real"] == "STTN1101U"
    assert _DEFAULTS["futures_cancel_day_real"] == "TTTO1103U"
    assert _DEFAULTS["futures_inquire_day_real"] == "TTTO5201R"


def test_tr_id_loads_yaml_overrides(tmp_path, monkeypatch):
    """When YAML defines a key, tr_id() returns the YAML value."""
    from shared.execution.tr_ids import tr_id

    cfg_dir = tmp_path / "config"
    (cfg_dir / "kis").mkdir(parents=True)
    (cfg_dir / "kis" / "tr_ids.yaml").write_text(
        "kis_tr_ids:\n"
        "  futures:\n"
        "    order:\n"
        "      day_real: 'TTTO9999U'\n"
        "      night_real: 'STTN9999U'\n"
    )
    monkeypatch.setenv("KIS_CONFIG_DIR", str(cfg_dir))
    assert tr_id("futures_order_day_real") == "TTTO9999U"
    assert tr_id("futures_order_night_real") == "STTN9999U"
    # Unrelated keys still fall back to defaults
    assert tr_id("stock_krx_buy_real") == "TTTC0802U"


def test_tr_id_falls_back_when_yaml_missing(tmp_path, monkeypatch):
    """No YAML → tr_id() returns baked default."""
    from shared.execution.tr_ids import tr_id

    cfg_dir = tmp_path / "empty_config"
    cfg_dir.mkdir()
    monkeypatch.setenv("KIS_CONFIG_DIR", str(cfg_dir))
    assert tr_id("futures_order_day_real") == "TTTO1101U"


def test_tr_id_unknown_key_raises():
    from shared.execution.tr_ids import tr_id

    with pytest.raises(KeyError, match="unknown TR ID key"):
        tr_id("does_not_exist")
