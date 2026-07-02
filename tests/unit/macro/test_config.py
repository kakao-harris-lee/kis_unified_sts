"""Tests for MacroCollectorConfig — yahoo_symbols config-driven ticker map.

Wave 2a: symbol additions must be config-only, with a hardcoded-map
fallback when the YAML section is absent (backward compat).
"""

from __future__ import annotations

from pathlib import Path

from shared.macro.config import DEFAULT_YAHOO_SYMBOLS, MacroCollectorConfig

_REPO_ROOT = Path(__file__).resolve().parents[3]

_LEGACY_MAP = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
}


def test_default_yahoo_symbols_match_legacy_hardcoded_map():
    """The fallback default must equal the pre-existing _TICKER_MAP exactly."""
    assert DEFAULT_YAHOO_SYMBOLS == _LEGACY_MAP


def test_config_without_yahoo_symbols_falls_back_to_legacy_map(tmp_path):
    yaml_path = tmp_path / "macro_sources.yaml"
    yaml_path.write_text(
        "macro_overnight_collector:\n"
        '  redis_stream: "stream:macro.overnight"\n'
        "  redis_maxlen: 5000\n",
        encoding="utf-8",
    )
    cfg = MacroCollectorConfig.from_yaml(str(yaml_path))
    assert cfg.yahoo_symbols == _LEGACY_MAP


def test_config_parses_yahoo_symbols_section(tmp_path):
    yaml_path = tmp_path / "macro_sources.yaml"
    yaml_path.write_text(
        "macro_overnight_collector:\n"
        "  yahoo_symbols:\n"
        '    sp500: "^GSPC"\n'
        '    es_futures: "ES=F"\n'
        '    usdkrw_realtime: "KRW=X"\n',
        encoding="utf-8",
    )
    cfg = MacroCollectorConfig.from_yaml(str(yaml_path))
    assert cfg.yahoo_symbols == {
        "sp500": "^GSPC",
        "es_futures": "ES=F",
        "usdkrw_realtime": "KRW=X",
    }
    # Untouched fields keep their defaults.
    assert cfg.redis_stream == "stream:macro.overnight"


def test_default_instances_do_not_share_the_map():
    """default_factory must yield independent dicts (no shared mutable state)."""
    a = MacroCollectorConfig()
    b = MacroCollectorConfig()
    a.yahoo_symbols["extra"] = "X"
    assert "extra" not in b.yahoo_symbols
    assert "extra" not in DEFAULT_YAHOO_SYMBOLS


def test_shipped_repo_config_has_legacy_and_premarket_symbols():
    """Regression: config/macro_sources.yaml must carry the full expanded map."""
    cfg = MacroCollectorConfig.from_yaml(
        str(_REPO_ROOT / "config" / "macro_sources.yaml")
    )
    # Legacy overnight_us_close symbols unchanged.
    for key, symbol in _LEGACY_MAP.items():
        assert cfg.yahoo_symbols.get(key) == symbol
    # Wave 2a pre-market additions.
    assert cfg.yahoo_symbols.get("es_futures") == "ES=F"
    assert cfg.yahoo_symbols.get("nq_futures") == "NQ=F"
    assert cfg.yahoo_symbols.get("sox") == "^SOX"
    assert cfg.yahoo_symbols.get("usdkrw_realtime") == "KRW=X"
    assert cfg.redis_stream == "stream:macro.overnight"
