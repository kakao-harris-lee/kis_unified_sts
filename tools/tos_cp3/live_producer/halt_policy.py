"""When the producer stops trying — plan §3.5's give-ups, in one place.

Split out of :mod:`~tools.tos_cp3.live_producer.producer` with
:mod:`~tools.tos_cp3.live_producer.seed_lineage` (PR #904 review round 1 item
A.5): that module is at ``config/tos_size_budget.yaml``'s 1,000-line cap, and
the answer to "no room" is a seam, not shorter lines.

This is the right seam because the three predicates below answer ONE question
— *is it still worth running?* — and each of them was written as a different
answer to it in a different part of that file. Nothing here reads a clock, a
socket or a file: every input is passed in, so each refusal can be driven from
a test by its own concrete input.

**Why there are three and not one.** They are different failures and an
operator acts on them differently:

* ``produce_error`` — the feed answers and the bars it returns cannot be
  turned into a line (non-finite values, duplicate stamps). The defect is in
  the data or in B1a's math.
* a fetch-error MINUTE — the feed does not answer at all. The defect is the
  transport: a revoked token, a blocked account, a partition.
* a boot past the close — nothing is wrong with anything; the session simply
  cannot happen, and the producer must say so instead of returning 0 having
  published nothing.

Folding the first two into one counter is what hid the second until PR #904's
review: ``consecutive_produce_errors`` counts only ``ProduceFieldsError``, so
a dead feed failed every poll of every minute and the session still ended
rc 0 (measured: ``fetch_error`` 324, ``published`` 0, rc 0).
"""

from __future__ import annotations

from datetime import date, datetime

from tools.tos_cp3.live_producer.calendar import SessionWindow
from tools.tos_cp3.live_producer.config import LiveProducerRefused

#: The log stage a boundary writes when no poll of it came back. It is NOT a
#: disposition stage: it names a MINUTE, carries no ``raw_event_id``, and the
#: §3.6 extractor keys its reason map on that field
#: (``tools/tos_cp3/session_inputs.py::producer_log_facts``).
STAGE_FETCH_ERROR_MINUTE = "fetch_error_minute"


def next_fetch_error_minutes(current: int, *, polled_ok: bool) -> int:
    """The consecutive-dead-minute run after one boundary's polling.

    The distinction the counter rests on is "a poll came back", never "a bar
    was published": a minute can poll perfectly and legitimately hold no row
    (``no_raw_row_for_minute`` — the lunch lull and the closing call
    auction). The genesis session is the concrete input for that: 12:39-13:08
    was 30 consecutive minutes of exactly that shape with ``fetch_error: 0``
    for the whole day, so a counter that folded the two would have aborted a
    clean session.
    """
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
    """Raise once either give-up is reached. Called after every boundary.

    Raises:
        LiveProducerRefused: either run has reached its configured bound. The
            runner turns the resulting non-zero exit into its ABORT (exit 5);
            the runtime is deliberately NOT killed for it, because truncating
            a durable set loses the evidence the session exists to leave.
    """
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
    """Refuse a session whose loop could not run even once.

    PR #904 review round 1 item A.2. ``run_session`` walks
    ``while boundary <= end``, so when the first boundary is already past
    ``end_boundary`` the loop body never executes and the producer returns 0
    having published nothing — a session that measured nothing, reported as
    clean. The condition is that loop's own zero-iteration condition, taken
    from it rather than re-derived from a clock comparison that could drift.

    ⚠ Called TWICE, and neither call is redundant (review round 2 LOW 3):
    once in ``boot()``, before the seed walk, and once at the top of
    ``run_session`` on the boundary that loop will actually use. The walk
    between them is tens of paginated GETs and can carry the clock past the
    close on its own — measured: a boot at 09:18:30 against a 09:21 end, a
    seed that advanced the clock to 09:23, and a loop that ran ZERO
    iterations and returned 0. The first call saves a walk the session cannot
    use; the second is the one that actually guarantees a boundary exists.

    ⚠ Asked by the PRODUCER and not by the runner. Two reasons, the first
    load-bearing: the runner never loads a calendar — it has only
    ``TENANT_STOP_AT`` — so a runner-side check would need its own copy of the
    session window, which is exactly the second source of truth
    ``calendar.py``'s module docstring refuses ("a hardcoded 15:45 would be a
    second source of truth that drifts the first time the exchange moves the
    close"). Second: the seed walk is tens of paginated GETs, and a session
    that cannot publish one bar should not spend them.

    Raises:
        LiveProducerRefused: the first boundary is at or past the close.
    """
    end = window.end_boundary(target)
    if first_boundary > end:
        raise LiveProducerRefused(
            f"the first boundary {first_boundary} is already past the session "
            f"end {end} ({window.phase} {window.start}..{window.end} on "
            f"{target}), so the session loop would not run once and no bar "
            "could be published. A producer that publishes nothing is not a "
            "clean session (plan §3.5)"
        )
