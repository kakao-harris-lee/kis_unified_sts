"""The two things ③ writes: the observation journal and B3's offline input."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import IO, Any

from tools.tos_cp3.live_producer.config import LiveProducerRefused

BAR_COLUMNS = ["code", "datetime", "open", "high", "low", "close", "volume"]


def acquire_session_lock(market_root: Path) -> IO[str]:
    """Take an exclusive, non-blocking ``flock`` on the SESSION, before any check."""
    market_root.mkdir(parents=True, exist_ok=True)
    handle = (market_root / ".session.lock").open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise LiveProducerRefused(
            f"another producer holds the session lock under {market_root} — two "
            "producers on one session would duplicate partitions and drop each "
            "other's journal lines (plan §3.5)"
        ) from exc
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


def refuse_if_journal_exists(path: Path) -> None:
    """The producer creates its journal; it never writes into somebody else's."""
    if path.exists() and path.stat().st_size > 0:
        raise LiveProducerRefused(
            f"{path} already holds {path.stat().st_size} byte(s). Every write "
            "here replaces the file whole, so an existing journal would be "
            "destroyed. Start a new session directory (plan §3.6)"
        )


JOURNAL_KEY_ORDER = (
    "raw_event_id",
    "source_id",
    "instrument",
    "as_of_ms",
    "received_ms",
    "fields",
)


def _wall_clock_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass(frozen=True)
class AppendOutcome:
    """What one append did, including the M6 interval and any refusal."""

    written: bool
    as_of_ms: int
    stamp_to_replace_s: float
    reason: str | None = None


@dataclass
class ObservationJournal:
    """Append-only content, atomic whole-file writes, monotone ``as_of_ms``."""

    path: Path
    clock: Callable[[], int] = _wall_clock_ms
    key_order: tuple[str, ...] = JOURNAL_KEY_ORDER
    lines: list[str] = field(default_factory=list)
    last_as_of_ms: int | None = None

    def __post_init__(self) -> None:
        if "as_of_ms" not in self.key_order:
            raise LiveProducerRefused(
                f"key_order {self.key_order} has no 'as_of_ms'; this journal "
                "owns the stamp, so a key order without it would write lines "
                "no reader can order or consume"
            )

    def append(self, row: dict[str, Any]) -> AppendOutcome:
        """Stamp *row*, add one line, and replace the file whole."""
        if "as_of_ms" in row:
            raise LiveProducerRefused(
                "the caller supplied as_of_ms; the journal owns the stamp so it "
                "can be taken immediately before the replace (plan §2 1-2)"
            )
        missing = [key for key in self.key_order if key != "as_of_ms"]
        absent = [key for key in missing if key not in row]
        if absent:
            raise LiveProducerRefused(f"journal row is missing {absent}")

        as_of_ms = self.clock()
        if self.last_as_of_ms is not None and as_of_ms <= self.last_as_of_ms:
            return AppendOutcome(
                written=False,
                as_of_ms=as_of_ms,
                stamp_to_replace_s=0.0,
                reason="clock_regression",
            )
        began = time.perf_counter()
        stamped = {**row, "as_of_ms": as_of_ms}
        ordered = {key: stamped[key] for key in self.key_order}
        self.lines.append(json.dumps(ordered, separators=(",", ":"), ensure_ascii=True))
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text("".join(f"{line}\n" for line in self.lines), encoding="utf-8")
        os.replace(tmp, self.path)
        elapsed = time.perf_counter() - began
        self.last_as_of_ms = as_of_ms
        return AppendOutcome(
            written=True, as_of_ms=as_of_ms, stamp_to_replace_s=elapsed
        )


def partition_dir(
    market_root: Path, *, asset_class: str, symbol: str, day: date
) -> Path:
    """The store's own minute-partition path for one day."""
    return (
        market_root
        / asset_class
        / "minute"
        / f"code={symbol}"
        / f"year={day.year}"
        / f"month={day.month:02d}"
        / f"day={day.isoformat()}"
    )


def refuse_if_partitions_exist(
    market_root: Path, *, asset_class: str, symbol: str
) -> None:
    """A session directory is used once (plan §3.6, v4 review L2)."""
    base = market_root / asset_class / "minute"
    existing = sorted(base.glob("code=*/year=*/month=*/day=*/*.parquet"))
    if existing:
        raise LiveProducerRefused(
            f"{base} already holds {len(existing)} partition file(s), e.g. "
            f"{existing[0].relative_to(base)} (this session trades {symbol}). "
            "The writes here are append-only, so reusing a session directory "
            "duplicates timestamps and B1a refuses the whole window. Start a "
            "new session directory (plan §3.6)"
        )


def append_bar_part(
    market_root: Path,
    *,
    asset_class: str,
    symbol: str,
    bars: Sequence[tuple],
) -> tuple[Path, ...]:
    """Write *bars* as one new part file per day, atomically."""
    import pandas as pd

    if not bars:
        return ()
    by_day: dict[date, list[tuple]] = {}
    for bar in bars:
        by_day.setdefault(bar[1].date(), []).append(bar)

    written: list[Path] = []
    for day, day_bars in sorted(by_day.items()):
        directory = partition_dir(
            market_root, asset_class=asset_class, symbol=symbol, day=day
        )
        directory.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        frame = pd.DataFrame(
            [
                {
                    "code": bar[0],
                    "datetime": pd.Timestamp(bar[1]),
                    "open": float(bar[2]),
                    "high": float(bar[3]),
                    "low": float(bar[4]),
                    "close": float(bar[5]),
                    "volume": int(bar[6]),
                }
                for bar in day_bars
            ]
        )[BAR_COLUMNS]
        tmp = directory / f".part-{token}.tmp"
        frame.to_parquet(tmp, index=False)
        final = directory / f"part-{token}.parquet"
        os.replace(tmp, final)
        written.append(final)
    return tuple(written)


def store_unadjusted_seed(
    market_root: Path,
    *,
    asset_class: str,
    instrument: str,
    kept: Sequence[Any],
    junction_new_bars: Sequence[tuple],
) -> None:
    """Write every seed day under ITS OWN contract's partition, unadjusted."""
    for entry in kept:
        append_bar_part(
            market_root,
            asset_class=asset_class,
            symbol=entry.contract,
            bars=entry.bars,
        )
    if junction_new_bars:
        append_bar_part(
            market_root,
            asset_class=asset_class,
            symbol=instrument,
            bars=junction_new_bars,
        )


def market_digest(market_root: Path) -> dict[str, str]:
    """sha256 of every written part file, keyed by its path under *market_root*."""
    return {
        str(path.relative_to(market_root)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(market_root.rglob("*.parquet"))
    }
