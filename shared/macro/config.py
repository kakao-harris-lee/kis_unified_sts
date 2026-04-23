"""Pydantic config model for macro overnight collector."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase


class MacroCollectorConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "macro_sources.yaml"
    _default_section: ClassVar[str] = "macro_overnight_collector"

    redis_stream: str = Field(default="stream:macro.overnight")
    redis_maxlen: int = Field(default=5000, gt=0)
