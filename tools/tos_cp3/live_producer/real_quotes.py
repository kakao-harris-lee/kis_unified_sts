"""The one function in ③ that resolves REAL credentials. Reached only by ``--confirm``."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from tools.broker_probes.common import resolve_credentials, secret_fingerprint
from tools.tos_cp3.live_producer.calendar import load_runtime_calendar
from tools.tos_cp3.live_producer.config import (
    QUOTE_CURSOR_SESSION_END,
    LiveProducerConfig,
)
from tools.tos_cp3.live_producer.session_log import EventLog
from tools.tos_cp3.quote_client import Quotes


def real_quotes(config: LiveProducerConfig, log: EventLog) -> Quotes:
    """The real transport. Only reached with ``--confirm``."""
    creds = resolve_credentials(config.asset_class, is_real=True)
    transport = {**config.transport, "initial_cursor": resolve_initial_cursor(config)}
    return Quotes(
        creds,
        log,
        transport,
        token_cache=config.token_cache_dir / secret_fingerprint(creds.app_key),
    )


def resolve_initial_cursor(config: LiveProducerConfig) -> str | Callable[[date], str]:
    """The first page's ``FID_INPUT_HOUR_1``: the config's literal, or per day."""
    if config.quote_initial_cursor != QUOTE_CURSOR_SESSION_END:
        return config.quote_initial_cursor
    calendar = load_runtime_calendar(
        config.calendar_yaml, covered_years=config.calendar_covered_years
    )

    def close_of(day: date) -> str:
        window = calendar.window(
            config.calendar_session_id, config.calendar_session_phase, day
        )
        return window.end.strftime("%H%M00")

    return close_of
