"""Composite persistence mixin for PositionTracker."""

from __future__ import annotations

from services.trading.position_auto_flush import PositionAutoFlushMixin
from services.trading.position_event_view import PositionEventViewMixin
from services.trading.position_ledger_persistence import PositionLedgerPersistenceMixin
from services.trading.position_legacy_archive import PositionLegacyArchiveMixin


class PositionPersistenceMixin(
    PositionLedgerPersistenceMixin,
    PositionLegacyArchiveMixin,
    PositionAutoFlushMixin,
    PositionEventViewMixin,
):
    """Combine persistence responsibilities behind the original tracker API."""
