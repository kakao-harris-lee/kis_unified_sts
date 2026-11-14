"""Shared synthetic-input builders for the CP-3 B1b suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INSTRUMENT = "101S6000"

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_PATH = _PACKAGE_ROOT / "strategies" / "setup_d_long.strategy.yaml"
BINDINGS_PATH = _PACKAGE_ROOT / "strategy_bindings.yaml"

MINUTE_MS = 60_000

BASE_AS_OF_MS = 1_765_151_100_000

BASE_CLOSE_X100 = 58_000


def neutral_fields(index: int) -> dict[str, Any]:
    """One bar's fields with every gate FALSE — the default no-action shape."""
    close = BASE_CLOSE_X100 + index
    return {
        "open_x100": close,
        "high_x100": close + 50,
        "low_x100": close - 50,
        "close_x100": close,
        "volume": 100 + index,
        "session_token": "2025-12-08",
        "vwap_x100": close + 20,
        "atr14_x100": 1_000,
        "z_x1000": -300,
        "hi_vol": False,
        "stall_ok": False,
        "reversal_ok": False,
        "entry_window": False,
        "vwap_reverted": False,
        "eod": False,
    }


def entry_fields(index: int) -> dict[str, Any]:
    """One bar's fields satisfying every conjunct of R1-ENTRY-LONG."""
    fields = neutral_fields(index)
    fields.update(
        {
            "hi_vol": True,
            "stall_ok": True,
            "reversal_ok": True,
            "entry_window": True,
            "z_x1000": -1_800,
        }
    )
    return fields


def near_miss_entry_fields(index: int) -> dict[str, Any]:
    """Every entry gate true but ``z_x1000`` one unit SHORT of the threshold."""
    fields = entry_fields(index)
    fields["z_x1000"] = -1_799
    return fields


def reverted_fields(index: int) -> dict[str, Any]:
    """One bar's fields satisfying R2-EXIT-VWAP-REVERTED and nothing else."""
    fields = neutral_fields(index)
    fields["vwap_reverted"] = True
    fields["z_x1000"] = 100
    return fields


def eod_fields(index: int) -> dict[str, Any]:
    """One bar's fields satisfying R3-EXIT-EOD and nothing else."""
    fields = neutral_fields(index)
    fields["eod"] = True
    return fields


def record_line(index: int, fields: dict[str, Any]) -> dict[str, Any]:
    """One JSONL line in B1a's five-key journal shape."""
    return {
        "raw_event_id": f"{INSTRUMENT}:1m:synthetic-{index:05d}",
        "source_id": "tos-cp3-b1b-test/0.1.0",
        "instrument": INSTRUMENT,
        "as_of_ms": BASE_AS_OF_MS + index * MINUTE_MS,
        "fields": fields,
    }


def write_jsonl(path: Path, lines: list[dict[str, Any]]) -> Path:
    """Write the synthetic field JSONL and return its path."""
    path.write_text(
        "".join(json.dumps(line, sort_keys=True) + "\n" for line in lines),
        encoding="utf-8",
    )
    return path


def synthetic_stream(
    *, bar_count: int = 50, entry_at: tuple[int, ...] = (), special: Any = None
) -> list[dict[str, Any]]:
    """A ``bar_count``-bar synthetic stream, neutral except where told otherwise."""
    overrides = dict(special or {})
    lines: list[dict[str, Any]] = []
    for index in range(bar_count):
        if index in overrides:
            fields = overrides[index](index)
        elif index in entry_at:
            fields = entry_fields(index)
        else:
            fields = neutral_fields(index)
        lines.append(record_line(index, fields))
    return lines
