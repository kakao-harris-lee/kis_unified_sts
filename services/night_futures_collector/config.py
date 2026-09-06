"""Config model for the KRX night-futures close capture collector (O9).

Loads config/night_futures.yaml::night_close_capture. All operational values
(night tr_key, capture window, Redis key/TTL) are config-driven — see the
YAML for the night-code (fo_cme_code.mst) resolution notes.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from datetime import time as dt_time
from typing import ClassVar

from pydantic import Field, field_validator, model_validator

from shared.config.base import ServiceConfigBase

logger = logging.getLogger(__name__)

_HHMM_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_hhmm(value: str) -> dt_time:
    match = _HHMM_PATTERN.match(value)
    if match is None:
        raise ValueError(f"expected KST time as HH:MM, got: {value!r}")
    return dt_time(int(match.group(1)), int(match.group(2)))


class NightCloseCaptureConfig(ServiceConfigBase):
    """Capture window + publication settings for the night close collector."""

    _default_config_file: ClassVar[str] = "night_futures.yaml"
    _default_section: ClassVar[str] = "night_close_capture"

    enabled: bool = Field(default=True)
    # Night-session 8-char code (e.g. "101W9000"); see config YAML for the
    # master-file (fo_cme_code.mst) resolution/roll procedure.
    tr_key: str = Field(default="101W9000", min_length=5, max_length=10)
    product_code: str = Field(default="101W9000")
    # Same-calendar-morning window (KST). Last trade in [start, end) wins.
    window_start_kst: str = Field(default="05:50")
    window_end_kst: str = Field(default="06:00")
    redis_key: str = Field(default="market:structure:night_close")
    # 183600s = 51h (not the 24h operational default): the Friday night
    # session closes ~06:00 KST Saturday, and Monday's premarket read at
    # ~05:48 KST is ~47h48m later — a 24h TTL would expire over that weekend
    # gap, while 51h leaves a missed-capture case a day later (~71h48m)
    # comfortably past the bound. This is also the SINGLE source for the
    # freshness bound both the dashboard (_night_close_summary) and the
    # market-structure collector (_read_night_close) reuse — see
    # config/night_futures.yaml for the full rationale.
    redis_ttl_seconds: int = Field(default=183600, gt=0)

    @classmethod
    def load_or_default(cls, path: str | None = None) -> NightCloseCaptureConfig:
        """Load from YAML when available; defaults on any read/parse problem.

        Same graceful-degradation contract as
        ``MarketRiskGateConfig.load_or_default`` /
        ``DecisionEngineMarketRiskGateWiring.load_or_default`` — used by
        consumers of this config OTHER than the collector's own one-shot
        CLI (``services/night_futures_collector/main.py`` keeps its stricter
        ``from_yaml()`` call: a missing config there is a real operator
        error). The dashboard's staleness bound and the market-structure
        collector's freshness bound both call this so a missing/malformed
        YAML never breaks their (unrelated) read paths.
        """
        try:
            return cls.from_yaml(path)
        except Exception:
            logger.warning("night_futures.yaml load failed; using defaults")
            return cls()

    @field_validator("window_start_kst", "window_end_kst")
    @classmethod
    def _validate_hhmm(cls, value: str) -> str:
        _parse_hhmm(value)
        return value

    @model_validator(mode="after")
    def _validate_window_order(self) -> NightCloseCaptureConfig:
        if _parse_hhmm(self.window_start_kst) >= _parse_hhmm(self.window_end_kst):
            raise ValueError(
                "window_start_kst must be earlier than window_end_kst "
                f"(got {self.window_start_kst} >= {self.window_end_kst}); "
                "the capture window must sit within one calendar morning"
            )
        return self

    def window_bounds(self, now: datetime) -> tuple[datetime, datetime]:
        """Capture window bounds on ``now``'s calendar date (tzinfo preserved).

        Args:
            now: Timezone-aware KST "now" anchoring the capture date.

        Returns:
            (window_start, window_end) as aware datetimes on now's date.
        """
        start = _parse_hhmm(self.window_start_kst)
        end = _parse_hhmm(self.window_end_kst)
        return (
            now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0),
            now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0),
        )
