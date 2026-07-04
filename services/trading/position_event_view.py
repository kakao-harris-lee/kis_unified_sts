from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("services.trading.position_tracker")


class PositionEventViewMixin:
    def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent events (most recent first)"""
        # Convert deque to list for slicing, get last N items
        events_list = list(self._events)
        recent = events_list[-limit:] if len(events_list) > limit else events_list

        return [
            {
                "type": e.event_type,
                "position_id": e.position_id[:8],
                "timestamp": e.timestamp.isoformat(),
                "details": e.details,
            }
            for e in recent
        ]
