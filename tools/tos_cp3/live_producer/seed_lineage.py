"""What the session records about the frame it seeded itself from."""

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
    """The ``seed`` log record: where this session's frame came from."""
    return {
        "instrument": instrument,
        "calendar_version": calendar.calendar_version,
        "session_window": f"{window.start}..{window.end}",
        "days_used": [str(day) for day in seed.days_used],
        "contracts_used": list(seed.contracts_used),
        "capacity": seed.capacity,
        "required": seed.required,
        "min_bars_per_day": seed.min_bars_per_day,
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
        "front_month_product": config.front_month_product,
        "stitch_manifest": str(market_root / STITCH_FILENAME),
        "stitch_manifest_sha256": manifest.sha256,
        "stitch_segments": [s.to_payload() for s in manifest.segments],
        "stitch_junctions": [j.to_payload() for j in manifest.junctions],
        "junction_new_contract_bars_stored_not_framed": len(
            assembler.junction_new_bars
        ),
    }
