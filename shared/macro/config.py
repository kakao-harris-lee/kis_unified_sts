"""Pydantic config model for macro overnight collector."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase

# Default Yahoo Finance ticker map — key = MacroSnapshot field prefix,
# value = Yahoo symbol. Mirrors the legacy hardcoded map in
# shared/macro/sources/yahoo.py so configs without a `yahoo_symbols:`
# section keep the exact pre-existing behavior. The shipped
# config/macro_sources.yaml extends this with pre-market symbols
# (es_futures/nq_futures/sox/usdkrw_realtime); adding a symbol is
# config-only — no code change needed here.
DEFAULT_YAHOO_SYMBOLS: dict[str, str] = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
}


class MacroCollectorConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "macro_sources.yaml"
    _default_section: ClassVar[str] = "macro_overnight_collector"

    redis_stream: str = Field(default="stream:macro.overnight")
    redis_maxlen: int = Field(default=5000, gt=0)
    yahoo_symbols: dict[str, str] = Field(
        default_factory=lambda: dict(DEFAULT_YAHOO_SYMBOLS),
        description=(
            "MacroSnapshot field prefix -> Yahoo Finance ticker. Falls back "
            "to the legacy hardcoded map when the YAML section is absent."
        ),
    )
