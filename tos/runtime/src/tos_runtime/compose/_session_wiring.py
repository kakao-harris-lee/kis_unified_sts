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
(``pathlib``) + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.calendar.ports import AbsentWallClockReference, WallClockReference
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.config import TrustworthyTimeConfig

__all__ = [
    "CALENDAR_CONFIG_NAME",
    "RETIRED_EGRESS_ATTESTATIONS_CONFIG_NAME",
    "RetiredConfigPresent",
    "SessionInboxCell",
    "apply_session_wiring",
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
    wall_clock: WallClockReference | None,
    evidence_store: SqliteEvidenceStore,
    time_config: TrustworthyTimeConfig,
    tick_generation_reader: Callable[[], int | None],
) -> SessionFactsOwner:
    """Load ``calendar.yaml``, refuse a leftover ``egress_attestations.yaml``
    (mutation M9), and construct the :class:`SessionFactsOwner`.

    Args:
        config_dir: The SAME directory ``compose_paper_runtime`` was given.
        wall_clock: The injected wall-clock reference, or ``None`` to use the
            honest production default
            (:class:`~tos_runtime.calendar.ports.AbsentWallClockReference` —
            plan §2 decision 2, G-1).
        evidence_store: Where the owner's boot-time evidence rows land.
        time_config: The loaded ``time.yaml`` (``_Infra.time_config``) — the
            source of ``tz_db_version``/``trading_calendar_version`` the
            owner cross-checks against ``calendar.yaml``.
        tick_generation_reader: Zero-argument callable (typically
            :meth:`SessionInboxCell.read`) returning the current tick
            generation, or ``None`` before the inbox is wired.

    Raises:
        RetiredConfigPresent: ``config_dir/egress_attestations.yaml`` still
            exists.
        tos_runtime.calendar.config.CalendarConfigError: ``calendar.yaml`` is
            missing/malformed/still named-TBD.
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
    calendar = load_calendar_config(config_dir / CALENDAR_CONFIG_NAME)
    effective_wall_clock = (
        wall_clock if wall_clock is not None else AbsentWallClockReference()
    )
    return SessionFactsOwner(
        calendar=calendar,
        wall_clock=effective_wall_clock,
        evidence_store=evidence_store,
        tick_generation_reader=tick_generation_reader,
        time_tz_db_version=time_config.tz_db_version,
        time_trading_calendar_version=time_config.trading_calendar_version,
    )


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
