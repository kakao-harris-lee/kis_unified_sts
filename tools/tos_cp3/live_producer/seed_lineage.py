"""What the session records about the frame it seeded itself from.

Split out of :mod:`~tools.tos_cp3.live_producer.producer` for the same reason
:mod:`~tools.tos_cp3.live_producer.session_log` was (PR #904 review round 1,
item A.5): that module sits at ``config/tos_size_budget.yaml``'s 1,000-line
cap, and the right answer to "no room left" is a seam, not shorter lines.

The seam is the one the module already had. Everything here is a REPORT — one
dict, assembled from values the boot already resolved — and nothing here
decides anything, fetches anything or writes anything. ``producer.py`` keeps
the deciding and the I/O.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from tools.tos_cp3.live_producer.calendar import RuntimeCalendar, SessionWindow
from tools.tos_cp3.live_producer.config import LiveProducerConfig
from tools.tos_cp3.live_producer.frame import (
    SEED_DROP_DENSITY,
    SEED_DROP_NO_RAW_ROWS,
    Seed,
)
from tools.tos_cp3.live_producer.stitch_seed import StitchedSeed
from tools.tos_cp3.stitch import STITCH_FILENAME, StitchManifest


def seed_lineage(
    *,
    instrument: str,
    target: date,
    calendar: RuntimeCalendar,
    window: SessionWindow,
    seed: Seed,
    config: LiveProducerConfig,
    manifest: StitchManifest,
    assembler: StitchedSeed,
    market_root: Path,
    source_id: str,
) -> dict[str, Any]:
    """The ``seed`` log record: where this session's frame came from.

    ``session_window`` is the one field downstream tooling DECIDES on — the
    §3.6 extractor reads the close out of it to tell the session's own last
    bar from a bar the runtime really missed
    (``tools/tos_cp3/session_inputs.py``'s ``REASON_PUBLISHED_AFTER_CLOSE``).
    It is written as ``"<start>..<end>"`` of two ``datetime.time``
    isoformats, from the tenant calendar the runtime also loads.
    """
    return {
        "instrument": instrument,
        "calendar_version": calendar.calendar_version,
        "session_window": f"{window.start}..{window.end}",
        "days_used": [str(day) for day in seed.days_used],
        "contracts_used": list(seed.contracts_used),
        "capacity": seed.capacity,
        "required": seed.required,
        "min_bars_per_day": seed.min_bars_per_day,
        # Reason-tagged, not one count (review L3): a day the calendar calls a
        # trading day that returned ZERO rows may be a holiday the calendar is
        # missing, which is the defect plan §3.2 moved off
        # `shared/collector/historical/calendar.py` to avoid. Merged into a
        # density count it would be invisible.
        "dropped_days": [
            {
                "day": str(s.day),
                "raw_rows": s.raw_rows,
                "parsed_rows": s.parsed_rows,
                "reason": s.drop_reason,
            }
            for s in seed.sessions
            if not s.density_pass
        ],
        "dropped_no_raw_rows": sum(
            1 for s in seed.sessions if s.drop_reason == SEED_DROP_NO_RAW_ROWS
        ),
        "dropped_density": sum(
            1 for s in seed.sessions if s.drop_reason == SEED_DROP_DENSITY
        ),
        "calendar_covered_years": list(config.calendar_covered_years),
        "parser_env": dict(config.parser_env),
        "config_sha256": config.sha256,
        "source_id": source_id,
        # Plan §3.2a. ``junctions`` is [] on a session with no splice and the
        # manifest is still written and still digested — B1a and B2 read it
        # either way.
        "front_month_product": config.front_month_product,
        "stitch_manifest": str(market_root / STITCH_FILENAME),
        "stitch_manifest_sha256": manifest.sha256,
        "stitch_segments": [s.to_payload() for s in manifest.segments],
        "stitch_junctions": [j.to_payload() for j in manifest.junctions],
        "junction_new_contract_bars_stored_not_framed": len(
            assembler.junction_new_bars
        ),
    }
