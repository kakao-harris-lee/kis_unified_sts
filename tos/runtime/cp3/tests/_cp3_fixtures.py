"""Shared synthetic-input builders for the CP-3 B1b suite.

Deterministic and clock-free: no ``time`` / ``datetime`` / ``random`` / ``uuid``
anywhere, because the runner forbids them and a suite must not model something
the code under test forbids (the ``tos/tests/backtest`` suite's own rule).

The synthetic bars are **not** market data and do not pretend to be: they are
the minimum shape that exercises the loader, the value seam, the policy, and
the capacity cap. Real-data numbers come from the real run, not from here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: The instrument the committed strategy file declares. A synthetic stream must
#: use it, because the runner refuses a replay whose JSONL instrument disagrees
#: with the strategy's dispatch scope.
INSTRUMENT = "101S6000"

#: The committed strategy content, relative to the package root.
#:
#: The two directions sit in **different config_dirs** and that is load-bearing:
#: ``load_strategy_content`` refuses a ``strategies/`` directory holding more
#: than the one requested file ("this replay drives one scope through one
#: core"), so a SHORT file beside the LONG one would refuse the LONG run too.
#: LONG stays at the package root — moving it would stop the recorded
#: 2026-10-08 artifact (``cp3-b1b-run1``) reproducing its
#: ``parents.strategy_file.path`` — and SHORT lives under ``short/``.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
STRATEGY_PATH = _PACKAGE_ROOT / "strategies" / "setup_d_long.strategy.yaml"
BINDINGS_PATH = _PACKAGE_ROOT / "strategy_bindings.yaml"
SHORT_STRATEGY_PATH = (
    _PACKAGE_ROOT / "short" / "strategies" / "setup_d_short.strategy.yaml"
)
SHORT_BINDINGS_PATH = _PACKAGE_ROOT / "short" / "strategy_bindings.yaml"

#: One minute in milliseconds — the bar cadence B1a produces.
MINUTE_MS = 60_000

#: The first bar's ``as_of_ms``. An arbitrary injected constant, not a clock
#: read; only the strict increase matters to ``validate_bar_stream``.
BASE_AS_OF_MS = 1_765_151_100_000

#: The base price in hundredths of an index point (B1a's ``*_x100`` encoding).
BASE_CLOSE_X100 = 58_000


def neutral_fields(index: int) -> dict[str, Any]:
    """One bar's fields with every gate FALSE — the default no-action shape.

    ``vwap_reverted`` is false here (``abs(z) > 0.2`` at ``z_x1000 = -300``), so
    a neutral bar fires no rule at all and takes the policy default.
    """
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
    """One bar's fields satisfying every conjunct of R1-ENTRY-LONG.

    ``z_x1000 = -1800`` sits exactly ON the threshold, which is the boundary the
    ``LE`` operator admits — the inclusive edge is deliberately the one the
    fixture exercises.
    """
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


def short_entry_fields(index: int) -> dict[str, Any]:
    """One bar's fields satisfying every conjunct of ``R1-ENTRY-SHORT``.

    The mirror of :func:`entry_fields`: ``z_x1000 = +1800`` sits exactly ON the
    SHORT threshold, which is the boundary the ``GE`` operator admits. A LONG
    entry bar must NOT satisfy this rule and vice versa, which is what makes
    the two renders different strategies rather than one with a sign flip.
    """
    fields = entry_fields(index)
    fields["z_x1000"] = 1_800
    return fields


def short_near_miss_entry_fields(index: int) -> dict[str, Any]:
    """Every SHORT entry gate true but ``z_x1000`` one unit inside the band."""
    fields = short_entry_fields(index)
    fields["z_x1000"] = 1_799
    return fields


def near_miss_entry_fields(index: int) -> dict[str, Any]:
    """Every entry gate true but ``z_x1000`` one unit SHORT of the threshold.

    The red half of the threshold's proof: ``-1799 <= -1800`` is false, so this
    bar must take the default. Without it, a binding of ``0`` (or any value the
    stream never crosses) would be indistinguishable from the authored one.
    """
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
    """A ``bar_count``-bar synthetic stream, neutral except where told otherwise.

    Args:
        bar_count: How many bars the stream carries.
        entry_at: Bar indices whose fields satisfy the entry rule.
        special: Optional ``{index: builder}`` mapping, applied after
            ``entry_at`` so a test can place a FLAT-firing bar precisely.

    Returns:
        The JSONL lines, in bar order.
    """
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
