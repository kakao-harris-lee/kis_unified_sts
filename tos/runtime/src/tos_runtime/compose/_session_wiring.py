"""Phase 5 W5 session/calendar compose wiring (plan §2 decisions 1-5,"""

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

CALENDAR_CONFIG_NAME = "calendar.yaml"

RETIRED_EGRESS_ATTESTATIONS_CONFIG_NAME = "egress_attestations.yaml"


class RetiredConfigPresent(RuntimeError):
    """Raised at boot when ``config_dir`` still carries a retired config file"""


class SessionInboxCell:
    """Late-bound tick-generation reader (module docstring) — filled in by"""

    def __init__(self) -> None:
        self.inbox: SqliteEventInbox | None = None

    def read(self) -> int | None:
        """The inbox's own ``count`` (the SAME tick-generation formula"""
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
    """Refuse a leftover ``egress_attestations.yaml`` (mutation M9) and construct the"""
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
    """The EGRESS stamp's trading-date reader: ``trading_date_reader``, with the trusted"""

    def _egress_trading_date_now() -> str | None:
        trading_date = trading_date_reader()
        if trading_date is not None:
            return trading_date
        try:
            time_service.evaluate()
        except Exception as exc:  # noqa: BLE001 - an unevaluable clock is "no date"
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
    """Late-bind ``session_inbox_cell`` now the durable inbox exists, and"""
    session_inbox_cell.inbox = runtime.inbox
    runtime.session_facts = session_facts_owner
    return runtime
