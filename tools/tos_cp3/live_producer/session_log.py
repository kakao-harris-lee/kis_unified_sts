"""What the session records about itself: the process log and the counters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STAGE_ALREADY_FROZEN = "already_frozen_not_published"


class EventLog:
    """Append-only JSONL process log; also the ``Quotes`` recorder."""

    def __init__(self, output: Path, name: str = "producer-log.jsonl"):
        """*name* is the log's basename."""
        output.mkdir(parents=True, exist_ok=True)
        self.output = output
        self.path = output / name

    def event(self, value: dict[str, Any]) -> None:
        payload = dict(value)
        rows = payload.pop("rows", None)
        if rows is not None:
            payload["row_count"] = len(rows)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


@dataclass
class Counters:
    """What the session reports back to the runner."""

    published: int = 0
    skipped_behind: int = 0
    late_completed: int = 0
    missing_no_successor: int = 0
    no_raw_row_for_minute: int = 0
    already_published: int = 0
    omitted_unusable: int = 0
    produce_error: int = 0
    clock_regression: int = 0
    fetch_error: int = 0
    pre_boot_lines: int = 0
    max_stamp_to_replace_s: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "skipped_behind": self.skipped_behind,
            "late_completed": self.late_completed,
            "missing_no_successor": self.missing_no_successor,
            "no_raw_row_for_minute": self.no_raw_row_for_minute,
            "already_published": self.already_published,
            "omitted_unusable": self.omitted_unusable,
            "produce_error": self.produce_error,
            "clock_regression": self.clock_regression,
            "fetch_error": self.fetch_error,
            "pre_boot_lines": self.pre_boot_lines,
            "max_stamp_to_replace_s": self.max_stamp_to_replace_s,
        }
