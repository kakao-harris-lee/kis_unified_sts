"""Phase 5 W5 session/calendar compose wiring (plan §2 decisions 1-5,
``docs/plans/2026-09-12-tos-phase5-w5-scenarios-plan.md``).

Builds the :class:`~tos_runtime.calendar.owner.SessionFactsOwner` and attaches
it to a composed runtime, replacing the retired
``venue_session_account_facts_current`` operator attestation
(:mod:`tos_runtime.compose._egress_attestations`, deleted — plan §2 decision
4) with a real runtime owner.

**Two-phase construction, mirroring ``_safety_wiring.py``'s own inbox-cell
idiom.** The owner is built EARLY in :func:`~tos_runtime.compose.root
.compose_paper_runtime` — right after ``_boot_services`` returns — because
step 3's ``VenueConstraintStage`` (built by ``_build_construction_stages``,
which runs before ``_finalize``) needs a live phase reader at construction
time. But the owner's own ``tick_generation_reader`` needs the durable event
inbox, which does not exist until ``_finalize`` builds it
(:mod:`tos_runtime.compose._engine_wiring`). :class:`SessionInboxCell` is the
same "construct now, fill in once the dependency exists" cell
:class:`~tos_runtime.compose._safety_wiring._InboxCell` already uses for the
identical reason — :func:`apply_session_wiring`, called immediately after
``_finalize`` returns (mirroring ``apply_release_wiring``/
``apply_recovery_barrier``), fills it in and attaches the owner to
:attr:`~tos_runtime.compose._types.ComposedRuntime.session_facts`.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``pathlib``, ``sys``) + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from tos_runtime.calendar.config import CalendarConfig
from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.calendar.ports import (
    FreshTrustedWallClockReference,
    TrustedWallClockReference,
    WallClockReference,
)
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "CALENDAR_CONFIG_NAME",
    "RETIRED_EGRESS_ATTESTATIONS_CONFIG_NAME",
    "RetiredConfigPresent",
    "SessionInboxCell",
    "apply_session_wiring",
    "build_egress_trading_date_reader",
    "build_session_facts_owner",
]

#: The calendar config file name (mirrors every other ``tos_runtime.*.config``
#: loader's own ``_*_CONFIG_NAME`` convention).
CALENDAR_CONFIG_NAME = "calendar.yaml"

#: The retired attestation config's file name (plan §2 decision 4 M9) — a
#: config directory that still carries this file refuses to boot, so a stale
#: file left over from before the attestation was retired is never silently
#: ignored.
RETIRED_EGRESS_ATTESTATIONS_CONFIG_NAME = "egress_attestations.yaml"


class RetiredConfigPresent(RuntimeError):
    """Raised at boot when ``config_dir`` still carries a retired config file
    (plan §2 decision 4, mutation M9) — the attestation this file used to
    hold now has a real runtime owner (:class:`SessionFactsOwner`); a leftover
    file must never be silently ignored, since an operator could otherwise
    believe an attestation is still in effect when nothing reads it anymore.
    """


class SessionInboxCell:
    """Late-bound tick-generation reader (module docstring) — filled in by
    :func:`apply_session_wiring` once the durable inbox exists."""

    def __init__(self) -> None:
        self.inbox: SqliteEventInbox | None = None

    def read(self) -> int | None:
        """The inbox's own ``count`` (the SAME tick-generation formula
        :mod:`tos_runtime.compose._safety_wiring`'s own
        ``_current_tick_generation`` uses), or ``None`` before the inbox is
        wired in (module docstring — a boot-order fact, not a runtime error)."""
        inbox = self.inbox
        if inbox is None:
            return None
        return inbox.count


def build_session_facts_owner(
    *,
    config_dir: Path,
    calendar: CalendarConfig,
    wall_clock: WallClockReference | None,
    evidence_store: SqliteEvidenceStore,
    time_config: TrustworthyTimeConfig,
    time_service: TrustworthyTimeService,
    tick_generation_reader: Callable[[], int | None],
) -> SessionFactsOwner:
    """Refuse a leftover ``egress_attestations.yaml`` (mutation M9) and construct the
    :class:`SessionFactsOwner` over the ALREADY-loaded ``calendar``.

    Args:
        config_dir: The SAME directory ``compose_paper_runtime`` was given — used only for
            the retired-config check below; ``calendar.yaml`` itself is loaded exactly once by
            the caller (TOS venue constraint service wave, plan §2 decision 9 — the SAME
            loaded ``CalendarConfig`` also feeds ``build_venue_service``'s own admitting-phase
            token cross-check, so this module never re-reads the file a second time).
        calendar: The already-loaded, validated calendar
            (:func:`~tos_runtime.calendar.config.load_calendar_config`).
        wall_clock: The injected wall-clock reference, or ``None`` to use the
            production default (G-1, runtime operations wiring plan §2
            decision 1):
            :class:`~tos_runtime.calendar.ports.TrustedWallClockReference`
            bound to ``time_service`` — reads a real value once that
            service's own boot-time ``evaluate()`` cycles have reached
            ``HealthState.TRUSTED``, and honestly ``None`` otherwise (never
            the permanently-absent pre-G-1 default).
        evidence_store: Where the owner's boot-time evidence rows land.
        time_config: The loaded ``time.yaml`` (``_Infra.time_config``) — the
            source of ``tz_db_version``/``trading_calendar_version`` the
            owner cross-checks against ``calendar.yaml``.
        time_service: The SAME ``TrustworthyTimeService`` instance
            ``_boot_services`` already started and ran its two boot-time
            ``evaluate()`` cycles on (``_Infra.time_service``) — the source
            :class:`~tos_runtime.calendar.ports.TrustedWallClockReference`
            reads when ``wall_clock`` is not explicitly injected.
        tick_generation_reader: Zero-argument callable (typically
            :meth:`SessionInboxCell.read`) returning the current tick
            generation, or ``None`` before the inbox is wired.

    Raises:
        RetiredConfigPresent: ``config_dir/egress_attestations.yaml`` still
            exists.
        tos_runtime.calendar.owner.SessionCalendarMismatch: the two configs'
            calendar-version labels disagree.
    """
    retired_path = config_dir / RETIRED_EGRESS_ATTESTATIONS_CONFIG_NAME
    if retired_path.is_file():
        raise RetiredConfigPresent(
            f"{retired_path}: egress_attestations.yaml is retired (plan §2 "
            "decision 4) -- venue_session_account_facts_current now has a "
            "real runtime owner (tos_runtime.calendar.owner.SessionFactsOwner); "
            "remove this file"
        )
    effective_wall_clock = (
        wall_clock
        if wall_clock is not None
        else TrustedWallClockReference(time_service)
    )
    return SessionFactsOwner(
        calendar=calendar,
        wall_clock=effective_wall_clock,
        # The egress trading date turns "now" into half of an ODNO identity, so it reads a
        # reference that is trusted AND fresh (plan 2026-09-26 egress trading date, review
        # finding 1) — the boot-time snapshot the session phase reads can be days old. An
        # explicitly injected wall_clock (tests) is used as-is.
        trading_date_wall_clock=(
            wall_clock
            if wall_clock is not None
            else FreshTrustedWallClockReference(
                time_service,
                max_age_ms=time_config.max_time_conservative_freshness_age_ms,
            )
        ),
        evidence_store=evidence_store,
        tick_generation_reader=tick_generation_reader,
        time_tz_db_version=time_config.tz_db_version,
        time_trading_calendar_version=time_config.trading_calendar_version,
    )


def build_egress_trading_date_reader(
    trading_date_reader: Callable[[], str | None],
    *,
    time_service: TrustworthyTimeService,
) -> Callable[[], str | None]:
    """The EGRESS stamp's trading-date reader: ``trading_date_reader``, with the trusted
    reading re-established at the stamp when this pass's own earlier work aged it out.

    ⛔ **Incident 2026-11-13** (CP-3 stock MOCK ``cp3-setup-d-stock-005930``). An entry order
    was acknowledged and the fill observer recorded ``FILL_OBSERVER_ACK_UNTRACKABLE`` reason
    ``no_trading_date``: an undated ACK cannot be joined to a broker row by ODNO (a per-day
    sequence), so the fill went unobserved. Measured, in ms since that pass's
    ``EVENT_HANDLING_STARTED``: the pre-send GETs took two app-key pacer slots (2161, 4161),
    ``SEND_STARTED`` was at 4287, the ACK at 7107. A pass evaluates time ONCE
    (:class:`~tos_runtime.marketfeed.time_pacer.TimeEvaluationPacer`, plan 2026-09-26), so by
    send start that evaluation was ~4.2 s old against ``time.yaml::
    max_time_conservative_freshness_age_ms`` (1000) and
    :class:`~tos_runtime.calendar.ports.FreshTrustedWallClockReference` answered ``None``.
    #1033 had already moved the read to send start — which stops the transport's OWN wait from
    staling a reading, and can do nothing about the pass's work BEFORE it.

    **What this does.** ``None`` from the reader means "no trusted reading of now" (stale, not
    TRUSTED, or no date at this instant at all). This asks the time service for ONE fresh
    health-check cycle — the same ``evaluate()`` the pass's own pacer runs, nothing weaker —
    and reads the date again. The reading is therefore genuinely re-derived at the stamp,
    through the SAME calendar and the SAME wall clock as every other date in the runtime.

    **What this refuses to do.** It never extrapolates "now" from a cached reading plus elapsed
    monotonic time (rejected by design — :meth:`~tos_runtime.time.service
    .TrustworthyTimeService.wall_clock_at_monotonic`'s own docstring, plan 2026-09-26 §3), it
    never widens or re-states the freshness bound (the bound stays
    ``max_time_conservative_freshness_age_ms``, read once in
    :func:`build_session_facts_owner`), and it never guesses a date: an untrusted clock, a
    failed evaluation, and an instant outside every declared session window all still answer
    ``None``. The alternative of capturing the date earlier in the pass (at attempt creation,
    where the snapshot is provably fresh) and carrying it to the stamp was rejected: showing
    the date cannot have changed in between needs an upper bound on elapsed WALL time, and the
    only bound available without a clock is elapsed monotonic time, which a process suspension
    makes smaller than the wall interval — the one case a date boundary would be crossed is
    exactly the case that bound fails to cover.

    **Why only the egress stamp.** :func:`~tos_runtime.compose.root.compose_paper_runtime`
    keeps every other consumer (band source, venue service, standing approval, post-trade
    witness, held-position bridge) on the plain reader, for two reasons. (1) This wrapper WRITES
    to the time service, and the egress stamp is on the loop thread — the one the pass's own
    evaluation already runs on; some other consumers read a date from the fill observer's FETCH
    thread (:mod:`tos_runtime.posttrade.fill_fetch`), and wrapping those would put a second
    writer on the service (their plain READS already overlap the loop's evaluation today, which
    this changes neither way). (2) The two readers cannot disagree about which day it is: a
    stale plain reader abstains (``None``), it never answers a different date.

    **Side effects of the extra cycle, and where it lands.** ``evaluate()`` may append a
    ``TIME_HEALTH_SNAPSHOT`` row, may move the health state (an honest judgement, a pass
    earlier than the next scheduler pass would make it), and re-bases the
    ``wall_clock_at_monotonic`` mapping's domain onto this cycle. All three are reached only at
    a send, which happens after that pass's ``_anchor_polled`` and after step 3's own session
    fold and the send-boundary context are built — so no observation this pass already mapped,
    and no judgement this attempt already made, is disturbed.

    Args:
        trading_date_reader: The runtime's ONE trading-date reading
            (:meth:`~tos_runtime.calendar.owner.SessionFactsOwner.trading_date_now` bound to
            this boot's instrument class) — wrapped, never replaced, so the egress stamp and
            the rest of the runtime read the same calendar through the same wall clock.
        time_service: The SAME :class:`~tos_runtime.time.service.TrustworthyTimeService` that
            reader's own :class:`~tos_runtime.calendar.ports.FreshTrustedWallClockReference`
            is bound to.

    Returns:
        A zero-argument reader answering the KST trading date (``YYYYMMDD``) or ``None``.
    """

    def _egress_trading_date_now() -> str | None:
        trading_date = trading_date_reader()
        if trading_date is not None:
            return trading_date
        try:
            time_service.evaluate()
        except Exception as exc:  # noqa: BLE001 - an unevaluable clock is "no date"
            # Reported, never raised: the same convention TimeEvaluationPacer uses for a failed
            # evaluation. The send's own disposition for an absent date is unchanged (the KIS
            # ACK goes out undated and says so; the synthetic venue row refuses to be written).
            print(
                "egress trading date: time evaluation failed, stamping no date — "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return None
        return trading_date_reader()

    return _egress_trading_date_now


def apply_session_wiring(
    runtime: ComposedRuntime,
    *,
    session_inbox_cell: SessionInboxCell,
    session_facts_owner: SessionFactsOwner,
) -> ComposedRuntime:
    """Late-bind ``session_inbox_cell`` now the durable inbox exists, and
    attach ``session_facts_owner`` to ``runtime`` (module docstring).

    Args:
        runtime: The just-``_finalize``d :class:`~tos_runtime.compose._types
            .ComposedRuntime` — mutated in place and returned (same discipline
            as ``apply_release_wiring``/``apply_recovery_barrier``).
        session_inbox_cell: The SAME cell passed to :func:`build_session_facts_owner`
            (via its ``tick_generation_reader``) when the owner was built,
            earlier in ``compose_paper_runtime``.
        session_facts_owner: The owner built earlier in
            ``compose_paper_runtime`` (module docstring — built early because
            step 3 needs a phase reader before ``_finalize`` runs).

    Returns:
        ``runtime`` itself, with :attr:`~tos_runtime.compose._types.ComposedRuntime
        .session_facts` set.
    """
    session_inbox_cell.inbox = runtime.inbox
    runtime.session_facts = session_facts_owner
    return runtime
