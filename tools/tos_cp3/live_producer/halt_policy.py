"""When the producer stops trying — plan §3.5's give-ups, in one place."""

from __future__ import annotations

from datetime import date, datetime

from tools.tos_cp3.live_producer.calendar import SessionWindow
from tools.tos_cp3.live_producer.config import LiveProducerRefused

STAGE_FETCH_ERROR_MINUTE = "fetch_error_minute"


def next_fetch_error_minutes(current: int, *, polled_ok: bool) -> int:
    """The consecutive-dead-minute run after one boundary's polling."""
    return 0 if polled_ok else current + 1


def assert_worth_continuing(
    *,
    consecutive_produce_errors: int,
    max_consecutive_produce_errors: int,
    consecutive_fetch_error_minutes: int,
    max_consecutive_fetch_error_minutes: int,
    fetch_error_total: int,
    published_total: int,
) -> None:
    """Raise once either give-up is reached. Called after every boundary."""
    if consecutive_produce_errors >= max_consecutive_produce_errors:
        raise LiveProducerRefused(
            f"{consecutive_produce_errors} consecutive produce_error(s) — "
            "stopping the producer (plan §3.5); the runner reports ABORT"
        )
    if consecutive_fetch_error_minutes >= max_consecutive_fetch_error_minutes:
        raise LiveProducerRefused(
            f"{consecutive_fetch_error_minutes} consecutive minute(s) in which "
            "NO poll succeeded — the feed is not answering "
            f"(fetch_error={fetch_error_total}, published={published_total}). "
            "Stopping the producer (plan §3.5); the runner reports ABORT"
        )


def assert_the_session_can_still_happen(
    *, first_boundary: datetime, window: SessionWindow, target: date
) -> None:
    """Refuse a session whose loop could not run even once."""
    end = window.end_boundary(target)
    if first_boundary > end:
        raise LiveProducerRefused(
            f"the first boundary {first_boundary} is already past the session "
            f"end {end} ({window.phase} {window.start}..{window.end} on "
            f"{target}), so the session loop would not run once and no bar "
            "could be published. A producer that publishes nothing is not a "
            "clean session (plan §3.5)"
        )
