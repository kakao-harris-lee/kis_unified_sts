"""The venue band capture: when it reads, what it writes, what it never does.

Band plan ``docs/plans/2026-10-15-tos-cp3-band-via-producer-plan.md`` §3.1-§3.2.
The producer already holds the one real-key GET-only transport in this system,
so the band's three fields come from here — the runtime keeps zero sockets and
zero credentials (③ plan §3.4), and band and price come from the SAME real
domain instead of a MOCK band around real prices.

**When** (§3.1, review HIGH-1): once, at the first boundary after the open,
immediately after the day's first price line is appended — not at boot. The
producer is built to come up BEFORE the open (``_first_boundary`` is
``max(open + 1min, now)``) and the runner's first-line wait allows 600 s, so a
boot-time GET is normally a PRE-OPEN response, and pre-open is exactly the hour
band plan §4.4a's residual risk ("the broker hands out yesterday's band") is
largest. A late start is not a problem — §2's monotonicity makes that hour's
band the widest CURRENT band.

**Bounded by the next price poll** (§5 PR-A, v2 re-review LOW): every attempt,
retries included, must end before ``next boundary - first_poll_delay_s``, so
the next minute's first poll still lands at its own ``+δ``. "The price journal
bytes are identical" does not cover this — that compares CONTENT and says
nothing about when the next poll started.

**What it never does.** A band failure is not a price-feed failure: it writes no
line, logs ``band_fetch_failed`` and is counted HERE, never in the producer's
``max_consecutive_fetch_error_minutes`` (§3.1 — that give-up counts minute-bar
polling). Band absence folds to ``UNKNOWN`` in the runtime and therefore to
zero sends, which is the conservative direction and no reason to stop
collecting prices.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tools.broker_probes.common import SafetyViolation
from tools.tos_cp3.live_producer.band_line import (
    BAND_JOURNAL_NAME,
    BAND_KEY_ORDER,
    BAND_LINE_KIND,
    BandLineError,
    band_values_from_payload,
    trading_date_text,
)
from tools.tos_cp3.live_producer.line import SOURCE_ID
from tools.tos_cp3.live_producer.sinks import ObservationJournal
from tools.tos_cp3.quote_client import BAND_TR

#: Log stages. ``band_fetch_failed`` is the plan's own name (§3.1); the others
#: exist so a session that wrote no band line still says WHY.
STAGE_BAND_PUBLISHED = "band_published"
STAGE_BAND_FETCH_FAILED = "band_fetch_failed"
STAGE_BAND_BEFORE_OPEN = "band_skipped_before_open"
STAGE_BAND_NO_ROOM = "band_window_had_no_room"
STAGE_BAND_CLOCK_REGRESSION = "band_clock_regression"

#: Why this window ran.
TRIGGER_FIRST = "first_boundary_after_open"
#: The ONE extra window a day gets when the first one produced no line
#: (review round 1 LOW-3). Bounded at one by :attr:`BandCapture.retried`.
TRIGGER_RETRY = "retry_after_a_failed_window"
TRIGGER_REREAD = "reread"


def band_journal_path(session_dir: Path) -> Path:
    """Where the band journal lives for a producer session directory."""
    return session_dir / BAND_JOURNAL_NAME


@dataclass
class BandCapture:
    """One session's band reads, and the journal they land in.

    Args:
        quotes: anything with ``band(symbol) -> BandRead``. The real one is
            :meth:`tools.tos_cp3.quote_client.Quotes.band`; the tests pass a
            fake with no socket behind it.
        journal: an :class:`~tools.tos_cp3.live_producer.sinks
            .ObservationJournal` opened on the band file with
            :data:`~tools.tos_cp3.live_producer.band_line.BAND_KEY_ORDER`. The
            same object as the price journal's class on purpose — whole-file
            atomic replace, the journal owns the stamp, a non-advancing stamp
            is refused (§3.2).
        session_start: the session OPEN as a naive KST datetime, from the
            tenant calendar the producer already loaded. Never a literal.
        reread_minutes: ``band_reread_minutes`` — MEASUREMENT ONLY (§3.1,
            review HIGH-2). The runtime reads the band on ``boot`` and
            ``phase_change`` only and the tenant calendar has one intraday
            phase, so an intraday re-read line cannot reach a decision before
            the close. Its only use is leaving evidence of an intraday
            widening in ``band.jsonl``.
    """

    quotes: Any
    journal: ObservationJournal
    log: Any
    instrument: str
    target: date
    session_start: datetime
    reread_minutes: int | None
    request_timeout_s: float
    #: The pace sleep ``Quotes.band`` takes before its request (5 rps limit).
    #: Charged in :meth:`attempt_budget` — review round 1 LOW-1.
    pace_s: float
    retry_pause_s: float
    #: δ, and "the next whole minute at least one bar past the open" — the two
    #: halves of :meth:`_deadline`. Taken as a callable and a number rather
    #: than as a deadline computed by the caller so the bound is stated once,
    #: here, next to the reason for it.
    first_poll_delay_s: float
    next_boundary: Callable[[], datetime]
    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    #: New on every producer boot (§3.2): a reader that sees two lines with
    #: different ids knows two processes wrote them.
    continuity_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attempted: bool = False
    #: Whether the one extra window (LOW-3) has been spent. Set, never cleared.
    retried: bool = False
    last_window_at: datetime | None = None
    attempts: int = 0
    #: Windows ENTERED. A day spends at most two (§3.1's one, plus LOW-3's one
    #: extra when the first produced nothing) plus any configured re-reads, so
    #: this is what tells "bounded at one extra" from "one per boundary".
    windows: int = 0
    lines: int = 0
    failures: int = 0

    # -- the trigger -----------------------------------------------------

    def after_price_line(self) -> None:
        """Called right after a price line was WRITTEN. Reads at most once."""
        trigger = self._trigger()
        if trigger is None:
            return
        self._window(self._deadline(), trigger)

    def _deadline(self) -> datetime:
        """The instant every attempt of this window must have finished by.

        The next boundary minus δ, so the next minute's first poll still lands
        at its own ``+δ`` whether or not a band read happened (band plan §5
        PR-A, v2 re-review LOW). The boundary is READ here rather than
        remembered: it is "the next whole minute at least one bar past the
        open" as of now, which is the one the producer's loop will use.
        """
        return self.next_boundary() - timedelta(seconds=self.first_poll_delay_s)

    def _trigger(self) -> str | None:
        """Is a band read due now, and why — or ``None``.

        ⛔ **Never before the open.** The concrete input: a boot before 08:45
        whose first response carries today-stamped pre-open rows (night-session
        or auction rows). ``_boot_today`` publishes the newest already-complete
        bar, so that publication would carry the band read with it — a pre-open
        band for the whole day. Deleting this clause makes
        ``test_red_the_band_is_never_read_before_the_open`` fetch one.
        """
        now = self.now()
        if now < self.session_start:
            self.log.event(
                {
                    "stage": STAGE_BAND_BEFORE_OPEN,
                    "now": str(now),
                    "session_start": str(self.session_start),
                }
            )
            return None
        if not self.attempted:
            return TRIGGER_FIRST
        # ONE extra window, and only when the first one got nothing (review
        # round 1 LOW-3). Without it a single bad minute — a 429 burst, one
        # expired token — costs the WHOLE day's band, because the first window
        # is the only one §3.1 allows. With it the day still has at most two
        # windows: this flag is set here and never cleared, so a second failure
        # is final. `after_price_line` is called once per published price line,
        # so "the next one" is the next boundary.
        if self.lines == 0 and not self.retried:
            # NOT marked spent here (review round 2 item D). `_room` may refuse
            # every attempt of this window, and a window that made no attempt
            # has used nothing: marking it here let one boundary with no room
            # swallow the single extra window and ask the broker nothing at
            # all. `_window` sets the flag when an attempt actually starts.
            return TRIGGER_RETRY
        if self.reread_minutes is None or self.last_window_at is None:
            return None
        if now - self.last_window_at < timedelta(minutes=self.reread_minutes):
            return None
        return TRIGGER_REREAD

    # -- one bounded window ----------------------------------------------

    def _window(self, deadline: datetime, trigger: str) -> None:
        """Attempt until one succeeds, one fails past the bound, or no room.

        A window that made NO attempt leaves :attr:`attempted` alone, so the
        next price line tries again: "no room this minute" is not "the band was
        read". A window that made at least one attempt is the one read §3.1
        allows, whatever its outcome.

        ⛔ ``SafetyViolation`` is re-raised by the clause ABOVE the
        ``RuntimeError`` one, and the order is the whole point.

        **The first cut of this docstring was false** (PR #906 review round 1,
        MEDIUM-1). It claimed the gate's refusal propagated while the code
        caught it: ``SafetyViolation`` is a subclass of ``ProbeError``, which
        is a subclass of ``RuntimeError``
        (``tools/broker_probes/common.py``) — so ``except (RuntimeError,
        BandLineError)`` swallowed it, and the reviewer measured the result:
        a transport whose every call the gate refused produced 24
        ``band_fetch_failed`` events reading "gate refused" and the producer
        still ended **rc 0**. The class's own docstring says "Never caught".

        Why it must propagate: the two band failures §3.1 names —
        transport/``rt_cd``, and an absent field — are conditions of the
        BROKER's answer. A gate refusal is not; it means the code and the
        allowlist disagree about what this process may call, which is a defect
        in THIS repo and the one place "zero real futures orders" is enforced.
        Folded into ``band_fetch_failed`` it is a log line nobody reads on a
        session that reports success. Propagated, the producer ends rc 1 and
        the runner reports exit 5.
        """
        made = 0
        self.windows += 1
        while self._room(deadline):
            if trigger == TRIGGER_RETRY and not made:
                # The extra window is spent by its first ATTEMPT, not by being
                # scheduled (review round 2 item D).
                self.retried = True
            self.attempts += 1
            made += 1
            attempt = self.attempts
            try:
                read = self.quotes.band(self.instrument)
                values = band_values_from_payload(read.payload)
            except SafetyViolation:
                # BEFORE the RuntimeError clause, because it IS a RuntimeError.
                raise
            except (RuntimeError, BandLineError) as exc:
                self.failures += 1
                self.attempted = True
                self.last_window_at = self.now()
                self.log.event(
                    {
                        "stage": STAGE_BAND_FETCH_FAILED,
                        "trigger": trigger,
                        "attempt": attempt,
                        "tr_id": BAND_TR,
                        "why": str(exc),
                        # Said out loud because it is the whole point: this
                        # failure is NOT counted toward the producer's
                        # max_consecutive_fetch_error_minutes (§3.1).
                        "counts_toward_fetch_give_up": False,
                    }
                )
                self.sleep(self.retry_pause_s)
                continue
            self.attempted = True
            self.last_window_at = self.now()
            self._write(values, read.raw_payload_digest, trigger, attempt)
            return
        if not made:
            self.log.event(
                {
                    "stage": STAGE_BAND_NO_ROOM,
                    "trigger": trigger,
                    "now": str(self.now()),
                    "deadline": str(deadline),
                    "request_timeout_s": self.request_timeout_s,
                }
            )

    def _room(self, deadline: datetime) -> bool:
        """Can a whole attempt finish before *deadline*?

        The question is ``now + attempt_budget <= deadline``, not
        ``now < deadline``: asking the weaker one is how an attempt started at
        ``deadline - 0.1 s`` spends its whole timeout and pushes the next
        minute's first poll past its own ``+δ``.

        :meth:`attempt_budget` is what one attempt can cost, and it charges
        the PACE sleep as well as the transport timeout (review round 1
        LOW-1): ``Quotes.band`` sleeps up to ``pace_s`` before the request to
        stay inside the 5 rps limit, and a budget that ignored it was short by
        that much on every attempt.
        """
        return self.now() + timedelta(seconds=self.attempt_budget()) <= deadline

    def attempt_budget(self) -> float:
        """Seconds one attempt may cost: the pace sleep plus the transport cap.

        The transport half is enforced by a **wall clock**, not by httpx's
        phase timeouts: ``Quotes.band`` streams the response and closes it the
        moment ``request_timeout_s`` is gone.

        ⚠ The first version of this docstring said the phase timeouts made the
        total "true by construction" because they sum to ``request_timeout_s``.
        That was wrong, and Codex caught it (review round 2 item A): httpx's
        ``read`` timeout bounds the wait for ONE chunk, so a response that
        trickles chunks inside each read timeout has no total bound at all.
        The phases remain as inactivity guards; the total is the deadline.

        ⚠ **What this still does NOT bound, stated rather than implied.** The
        OAuth token call runs through ``KISAuthManager`` on ``requests`` and is
        bounded by that manager, not by this budget; it only runs when the
        cached token is cold or expired. So an attempt CAN overrun this number
        by a token fetch. What the bound guarantees is the thing that matters:
        after an overrunning attempt, the next one is refused rather than
        compounding — :func:`test_red_an_attempt_that_overruns_its_budget_does_
        not_get_a_second` is that proof.
        """
        return self.pace_s + self.request_timeout_s

    # -- the line --------------------------------------------------------

    def _write(
        self, values: dict[str, str], digest: str, trigger: str, attempt: int
    ) -> None:
        """One band line. No conversion, no validation of the three values.

        §3.1: the three fields travel as STRINGS exactly as they arrived and
        the scale/grid/ordering checks stay in the runtime's existing
        validation set, so there is one place that decides whether a band is
        admissible (band plan §4.2).
        """
        row = {
            "kind": BAND_LINE_KIND,
            "source_id": SOURCE_ID,
            "instrument": self.instrument,
            "trading_date": trading_date_text(self.target),
            "tr_id": BAND_TR,
            "raw_payload_digest": digest,
            "producer_continuity_id": self.continuity_id,
            **values,
        }
        outcome = self.journal.append(row)
        if not outcome.written:
            # Same disposition as a price line's refused stamp (③ plan §2 5):
            # refuse THAT write, log it, do not adjust the clock.
            self.log.event(
                {
                    "stage": STAGE_BAND_CLOCK_REGRESSION,
                    "trigger": trigger,
                    "as_of_ms": outcome.as_of_ms,
                    "last_as_of_ms": self.journal.last_as_of_ms,
                    "written": False,
                }
            )
            return
        self.lines += 1
        self.log.event(
            {
                "stage": STAGE_BAND_PUBLISHED,
                "trigger": trigger,
                "attempt": attempt,
                "tr_id": BAND_TR,
                "instrument": self.instrument,
                "trading_date": row["trading_date"],
                "as_of_ms": outcome.as_of_ms,
                "raw_payload_digest": digest,
                "producer_continuity_id": self.continuity_id,
                "stamp_to_replace_s": outcome.stamp_to_replace_s,
            }
        )

    def report(self) -> dict[str, Any]:
        """What the session summary says about the band."""
        return {
            "journal": str(self.journal.path),
            "attempts": self.attempts,
            "windows": self.windows,
            "lines": self.lines,
            "failures": self.failures,
            "producer_continuity_id": self.continuity_id,
            "reread_minutes": self.reread_minutes,
            "retry_window_used": self.retried,
            "attempt_budget_s": self.attempt_budget(),
        }


def build_capture(
    *,
    quotes: Any,
    log: Any,
    session_dir: Path,
    instrument: str,
    target: date,
    session_start: datetime,
    reread_minutes: int | None,
    request_timeout_s: float,
    pace_s: float,
    retry_pause_s: float,
    first_poll_delay_s: float,
    next_boundary: Callable[[], datetime],
    clock_ms: Callable[[], int],
    now: Callable[[], datetime],
    sleep: Callable[[float], None],
) -> BandCapture:
    """Wire one :class:`BandCapture`, journal included.

    Here rather than in ``producer.py``: that module sits against
    ``config/tos_size_budget.yaml``'s 1,000-line cap, and the journal's key
    order and file name are facts about the BAND, not about the loop.
    """
    return BandCapture(
        quotes=quotes,
        journal=ObservationJournal(
            band_journal_path(session_dir), clock=clock_ms, key_order=BAND_KEY_ORDER
        ),
        log=log,
        instrument=instrument,
        target=target,
        session_start=session_start,
        reread_minutes=reread_minutes,
        request_timeout_s=request_timeout_s,
        pace_s=pace_s,
        retry_pause_s=retry_pause_s,
        first_poll_delay_s=first_poll_delay_s,
        next_boundary=next_boundary,
        now=now,
        sleep=sleep,
    )
