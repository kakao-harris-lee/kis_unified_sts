"""Macro event collector for futures analysis."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from .collector_base import DataCollector
from .data_classes import EconomicEvent
from .errors import DataUnavailableError

logger = logging.getLogger("shared.llm.collectors")


class FuturesEventCollector(DataCollector):
    """경제 이벤트 수집"""

    def collect(self, days_ahead: int = 3) -> list[EconomicEvent]:
        """경제 이벤트 수집 (외부 스냅샷 사용)"""
        snapshot_json = os.environ.get("LLM_EVENT_SNAPSHOT_JSON", "").strip()
        snapshot_path = os.environ.get("LLM_EVENT_SNAPSHOT_PATH", "").strip()

        payload = None
        if snapshot_json:
            try:
                payload = json.loads(snapshot_json)
            except Exception as e:
                logger.debug(f"Invalid LLM_EVENT_SNAPSHOT_JSON: {e}")
        elif snapshot_path:
            try:
                with open(snapshot_path, encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load event snapshot file: {e}")

        if not payload:
            raise DataUnavailableError("macro_events", "snapshot_missing")

        events = []
        for item in payload:
            try:
                events.append(
                    EconomicEvent(
                        date=str(item.get("date", "")),
                        time=str(item.get("time", "")),
                        country=str(item.get("country", "")),
                        event=str(item.get("event", "")),
                        importance=str(item.get("importance", "")),
                        impact_analysis=str(item.get("impact_analysis", "")),
                    )
                )
            except Exception:
                continue

        if not events:
            raise DataUnavailableError("macro_events", "snapshot_empty")

        # limit by days_ahead
        if days_ahead:
            cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            events = [e for e in events if e.date <= cutoff]

        events.sort(key=lambda x: (x.date, x.time))
        return events
