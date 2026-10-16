"""What the session records about itself: the process log and the counters.

Split out of :mod:`~tools.tos_cp3.live_producer.producer` when PR-3's label
fixes took that module past ``config/tos_size_budget.yaml``'s 1,000-line cap
(measured 1,008). Decomposed rather than registered as an exception: that
file's own header calls registration 「면허가 아니라 가시성」, which is the right
stance for inherited code and the wrong one for code written this month — the
same call ``tos/runtime/cp3`` made on 2026-10-08.

The seam is one the module already had: everything here is what the producer
*says about* a session — one JSONL line per event, one integer per disposition
— and nothing here decides anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The log stage a boundary writes when its own bar is already in the frame but
#: was never published (PR #898 round-3 review I2). It increments no counter:
#: whatever stopped that publication — ``omitted_unusable``, ``produce_error``,
#: a refused stamp, ``skipped_behind`` — counted the bar when it happened, and a
#: second counter here would report one bar twice.
STAGE_ALREADY_FROZEN = "already_frozen_not_published"


class EventLog:
    """Append-only JSONL process log; also the ``Quotes`` recorder.

    The raw ``rows`` payload is replaced by its length: PR-1's own request log
    was 14 MB for one session, and the rows that matter are retained as the
    frozen Parquet frame (plan §3.6), not twice. Nothing here ever receives a
    header, a token or ``msg1`` — ``Quotes.page`` does not pass them.
    """

    def __init__(self, output: Path, name: str = "producer-log.jsonl"):
        """*name* is the log's basename.

        The default is the producer's own. The band probe (band plan v3) passes
        ``band-log.jsonl``: it is a SEPARATE process appending independently, and
        two processes appending to one file can interleave a partial line. The
        post-session TR check reads both files (runbook §7.2-d).
        """
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
    """What the session reports back to the runner.

    The unpublished reasons are kept apart on purpose — merged, none of them
    says anything an operator can act on:

    * ``missing_no_successor`` — the minute TRADED (a raw row exists) but no
      strictly later row arrived inside G, so publication is skipped (plan
      §3.3). This is the 15:34 shape.
    * ``no_raw_row_for_minute`` — the minute produced no raw row at all, so
      there is no bar to publish. This is the 15:35-15:44 call-auction shape,
      and it is NOT a late feed (review M1).
    * ``late_completed`` — an OLDER bar completed after its own boundary had
      already passed. It is frozen into the frame and written to Parquet so B1a
      parity holds, but it is not published: a line stamped now would carry a
      fresh ``as_of_ms`` for a stale bar, and the runtime would consume it as
      the current observation (review M1).
    * ``skipped_behind`` — more than one bar completed in ONE poll; only the
      newest is published (plan §2 4), and the older ones — this boundary's own
      bar among them when a poll came back after the next bar had completed
      too — are counted here.
    * ``already_published`` — this boundary's bar was already published, as the
      catch-up of an earlier boundary whose poll returned late (review N1), so
      the boundary polls nothing. Without it the bar is frozen and unpublishable
      and the boundary would wait the full G and then claim
      ``missing_no_successor`` for a bar sitting in the frame. ⚠ It counts a
      PUBLICATION this boundary found already done — never a bar that merely
      reached the frame. A frozen bar that was not published was already
      counted at freeze time under its own reason, so counting it here too
      would report one bar twice (PR #898 round-3 review I2); that boundary
      logs the stage :data:`STAGE_ALREADY_FROZEN` and increments nothing.
    """

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
