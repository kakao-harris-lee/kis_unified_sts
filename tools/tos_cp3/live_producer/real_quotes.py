"""The one function in ③ that resolves REAL credentials. Reached only by ``--confirm``.

Split out of :mod:`~tools.tos_cp3.live_producer.producer` in PR #906 review
round 1: that module sits against ``config/tos_size_budget.yaml``'s
1,000-line cap and the MEDIUM-1 fix needed room, so something had to move.
This is the right thing to move rather than the smallest: ③ plan §3.4's whole
design is that exactly one process holds the two real futures QUERY keys, and
this is the only place in the package that asks for them. A reader auditing
that claim now has one short file to read instead of a function buried at the
bottom of the loop.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

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
    """The real transport. Only reached with ``--confirm``.

    The cache path carries the app-key FINGERPRINT (③ review L2). Dropping
    that segment is what PR-1's own derivation exists to prevent: the stock
    ``KISToken`` cache keys on the domain alone, so two different app keys
    would share one token file and a reissue for one would hand the other a
    token its key never minted. ``secret_fingerprint`` is irreversible, so the
    path names the key without carrying it.
    """
    creds = resolve_credentials(config.asset_class, is_real=True)
    transport = {**config.transport, "initial_cursor": resolve_initial_cursor(config)}
    return Quotes(
        creds,
        log,
        transport,
        token_cache=config.token_cache_dir / secret_fingerprint(creds.app_key),
    )


def resolve_initial_cursor(config: LiveProducerConfig) -> str | Callable[[date], str]:
    """The first page's ``FID_INPUT_HOUR_1``: the config's literal, or per day.

    :data:`~tools.tos_cp3.live_producer.config.QUOTE_CURSOR_SESSION_END` becomes
    "that day's session close as ``HHMM00``", read from the same calendar and
    session the producer reads — so a seed day or target day carrying a dated
    override (issue #924) is fetched back from ITS close, and a regular day
    from the regular one (15:30 -> ``153000``, the value the config named
    before the token existed).
    """
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
